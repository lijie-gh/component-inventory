# -*- coding: utf-8 -*-
"""SQLite 数据层：建表、CRUD、查询。

表结构
    parts     元件主表（嘉立创件与其它渠道件统一存放，用 source 字段区分）
    stock     分库位库存
    txns      出入库流水
    cache     嘉立创商城数据缓存
"""
import contextlib
import os
import sqlite3
import threading

from . import config, pricing

_lock = threading.RLock()
_conn = None

# 事务嵌套深度。>0 表示正处在 with transaction() 里，此时单条 execute()
# 不再自己 commit，把提交权交给最外层，多条写操作才能整体成功或整体回滚。
_txn_depth = 0

SCHEMA = """
CREATE TABLE IF NOT EXISTS parts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT,                        -- 嘉立创 C 号，非嘉立创件为空
    source       TEXT NOT NULL DEFAULT 'lcsc',-- lcsc=嘉立创 / other=其它渠道
    supplier     TEXT,                        -- 采购渠道（非嘉立创件填写）
    name         TEXT,                        -- 名称描述
    model        TEXT,                        -- 型号 / MPN
    brand        TEXT,                        -- 厂商
    package      TEXT,                        -- 封装
    category     TEXT,                        -- 分类
    value        TEXT,                        -- 参数值 如 10kΩ / 100nF
    descr        TEXT,                        -- 详细描述（中文）
    descr_en     TEXT,                        -- 商城返回的英文原文，备查
    datasheet    TEXT,                        -- 数据手册链接
    image_url    TEXT,
    lib_type     TEXT,                        -- base/extended 基础库/扩展库
    unit         TEXT DEFAULT '个',
    min_qty      INTEGER DEFAULT 0,           -- 该元件的最小库存预警阈值
    ref_price    REAL,                        -- 参考单价
    price_info   TEXT,                        -- 阶梯价格文本
    remark       TEXT,
    created_at   TEXT,
    updated_at   TEXT,
    last_fetch   TEXT                         -- 最近一次从商城刷新数据的时间
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_parts_code
    ON parts(code) WHERE code IS NOT NULL AND code <> '';

CREATE INDEX IF NOT EXISTS idx_parts_source ON parts(source);
CREATE INDEX IF NOT EXISTS idx_parts_category ON parts(category);

CREATE TABLE IF NOT EXISTS stock (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id  INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
    location TEXT NOT NULL DEFAULT '默认库位',
    quantity INTEGER NOT NULL DEFAULT 0,
    UNIQUE(part_id, location)
);

CREATE TABLE IF NOT EXISTS txns (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id    INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL,      -- IN / OUT / ADJUST
    quantity   INTEGER NOT NULL,
    location   TEXT,
    operator   TEXT,
    note       TEXT,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_txns_part ON txns(part_id);
CREATE INDEX IF NOT EXISTS idx_txns_time ON txns(created_at);

CREATE TABLE IF NOT EXISTS cache (
    code       TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    fetched_at TEXT
);
"""


# parts 表每个字段的建列语句。用于给旧版本建的库自动补列——以前只硬编码了
# 两个新列，一旦旧库缺的是被索引引用的列（如 category），启动时建索引就会崩。
_PART_COLUMN_DDL = (
    ("code", "TEXT"),
    ("source", "TEXT NOT NULL DEFAULT 'lcsc'"),
    ("supplier", "TEXT"),
    ("name", "TEXT"),
    ("model", "TEXT"),
    ("brand", "TEXT"),
    ("package", "TEXT"),
    ("category", "TEXT"),
    ("value", "TEXT"),
    ("descr", "TEXT"),
    ("descr_en", "TEXT"),
    ("datasheet", "TEXT"),
    ("image_url", "TEXT"),
    ("lib_type", "TEXT"),
    ("unit", "TEXT DEFAULT '个'"),
    ("min_qty", "INTEGER DEFAULT 0"),
    ("ref_price", "REAL"),
    ("price_info", "TEXT"),
    ("price_tiers", "TEXT"),          # 完整阶梯价表（JSON），用于算库存金额
    ("remark", "TEXT"),
    ("created_at", "TEXT"),
    ("updated_at", "TEXT"),
    ("last_fetch", "TEXT"),
)


def _migrate(conn):
    """给老版本建的库补上缺失的列（SQLite 只能一列一列加）。"""
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(parts)")}
        if not cols:                 # 还没有 parts 表，交给建表语句去创建
            return
        for name, ddl in _PART_COLUMN_DDL:
            if name not in cols:
                conn.execute(f"ALTER TABLE parts ADD COLUMN {name} {ddl}")
        conn.commit()
    except Exception:
        pass


def get_conn():
    """获取全局连接（自动建库建表）。"""
    global _conn
    with _lock:
        if _conn is None:
            os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
            _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA foreign_keys = ON")
            # 写锁被占用时先等一会儿再报错，避免后台刷新线程与界面操作撞车
            _conn.execute("PRAGMA busy_timeout = 5000")
            _migrate(_conn)          # 老库先补列，免得下面的建索引语句找不到列
            _conn.executescript(SCHEMA)
            _conn.commit()
            _migrate(_conn)
        return _conn


@contextlib.contextmanager
def transaction():
    """把一组写操作包成一个原子事务。

        with db.transaction():
            db.set_stock(...)      # 改库存
            db.add_txn(...)        # 记流水

    中途抛异常则整体回滚，不会留下「库存变了但没流水」这种账实不符。
    支持嵌套：内层复用外层事务，只有最外层真正提交。
    """
    global _txn_depth
    with _lock:
        conn = get_conn()
        outermost = (_txn_depth == 0)
        if not outermost:
            # 已经在事务里，直接复用
            _txn_depth += 1
            try:
                yield conn
            finally:
                _txn_depth -= 1
            return

        # sqlite3 在隔离级别非 None 时会自动 BEGIN，这里靠它隐式开事务，
        # 只要保证期间不提交即可。
        _txn_depth = 1
        try:
            yield conn
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        else:
            try:
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise
        finally:
            _txn_depth = 0


def close():
    global _conn
    with _lock:
        if _conn is not None:
            try:
                _conn.commit()
                _conn.close()
            except Exception:
                pass
            _conn = None


def backup_to(path):
    """把数据库在线备份到指定文件，返回文件路径。

    用 sqlite3 自带的 backup API，而不是直接复制 .db 文件：直接复制一个
    正在被写入的数据库，可能拿到「表结构已更新、数据还没写完」的半成品。
    backup() 在持有读锁的情况下生成一致快照。
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with _lock:
        src = get_conn()
        target = sqlite3.connect(path)
        try:
            src.backup(target)
            target.commit()
        finally:
            target.close()
    return path


def query(sql, args=()):
    with _lock:
        cur = get_conn().execute(sql, args)
        return [dict(r) for r in cur.fetchall()]


def query_one(sql, args=()):
    rows = query(sql, args)
    return rows[0] if rows else None


def execute(sql, args=()):
    with _lock:
        conn = get_conn()
        cur = conn.execute(sql, args)
        if _txn_depth == 0:      # 在事务里就交给最外层统一提交
            conn.commit()
        return cur.lastrowid


def executemany(sql, seq):
    with _lock:
        conn = get_conn()
        conn.executemany(sql, seq)
        if _txn_depth == 0:
            conn.commit()


# ---------------------------------------------------------------- 元件
PART_FIELDS = (
    "code", "source", "supplier", "name", "model", "brand", "package",
    "category", "value", "descr", "descr_en", "datasheet", "image_url",
    "lib_type", "unit", "min_qty", "ref_price", "price_info", "price_tiers",
    "remark",
)

# 允许用于 ORDER BY 的列（白名单，防止 SQL 拼接被注入）
_SORTABLE_COLUMNS = frozenset(PART_FIELDS) | {
    "id", "created_at", "updated_at", "last_fetch",
}


def add_part(data, location=config.DEFAULT_LOCATION, quantity=0):
    """新增元件，返回 part_id。同时建立库位记录。"""
    now = config.now_str()
    payload = {k: data.get(k) for k in PART_FIELDS}
    payload["source"] = payload.get("source") or config.SOURCE_LCSC
    payload["unit"] = payload.get("unit") or "个"
    payload["min_qty"] = int(payload.get("min_qty") or 0)
    payload["created_at"] = now
    payload["updated_at"] = now
    payload["last_fetch"] = data.get("last_fetch")

    cols = ", ".join(payload.keys())
    marks = ", ".join("?" for _ in payload)
    pid = execute(f"INSERT INTO parts ({cols}) VALUES ({marks})",
                  tuple(payload.values()))
    if quantity or location:
        set_stock(pid, location, int(quantity or 0))
    return pid


def update_part(part_id, data):
    if not data:
        return
    fields = [k for k in data if k in PART_FIELDS or k == "last_fetch"]
    if not fields:
        return
    fields.append("updated_at")
    values = [data[k] for k in fields[:-1]]
    values.append(config.now_str())
    sets = ", ".join(f"{k}=?" for k in fields)
    execute(f"UPDATE parts SET {sets} WHERE id=?", tuple(values) + (part_id,))


def delete_part(part_id):
    execute("DELETE FROM parts WHERE id=?", (part_id,))


def get_part(part_id):
    return query_one("SELECT * FROM parts WHERE id=?", (part_id,))


def get_part_by_code(code):
    if not code:
        return None
    code = code.strip().upper()
    return query_one("SELECT * FROM parts WHERE UPPER(code)=?", (code,))


def find_by_code_or_model(text):
    """按 C 号或型号精确找一条（用于导入去重）。"""
    if not text:
        return None
    t = text.strip()
    row = query_one("SELECT * FROM parts WHERE UPPER(code)=?", (t.upper(),))
    if row:
        return row
    return query_one("SELECT * FROM parts WHERE model=?", (t,))


def list_parts(keyword="", source_filter="all", stock_filter="all",
               category="", order_by="category"):
    """核心查询：支持关键词搜索 + 来源筛选 + 库存筛选。

    source_filter: all | lcsc | other
    stock_filter : all | in_stock | out_of_stock | low
    """
    sql = ["""
        SELECT p.*,
               COALESCE(s.total_qty, 0) AS total_qty,
               COALESCE(s.locations, '') AS locations
        FROM parts p
        LEFT JOIN (
            SELECT part_id,
                   SUM(quantity) AS total_qty,
                   GROUP_CONCAT(location || ':' || quantity, ' / ') AS locations
            FROM stock GROUP BY part_id
        ) s ON s.part_id = p.id
        WHERE 1=1
    """]
    args = []

    kw = (keyword or "").strip()
    if kw:
        like = f"%{kw}%"
        # 注意：每个 SQL 片段都以换行开头，拼接后不会粘成 ...ENDORDER
        sql.append("""
            AND (
                p.code LIKE ? OR p.model LIKE ? OR p.name LIKE ? OR p.brand LIKE ?
                OR p.package LIKE ? OR p.value LIKE ? OR p.descr LIKE ?
                OR p.supplier LIKE ? OR p.remark LIKE ? OR p.category LIKE ?
            )
        """)
        args.extend([like] * 10)

    if source_filter in (config.SOURCE_LCSC, config.SOURCE_OTHER):
        sql.append("\n            AND p.source = ?\n")
        args.append(source_filter)

    if category:
        sql.append("\n            AND p.category = ?\n")
        args.append(category)

    if stock_filter == "in_stock":
        sql.append("\n            AND COALESCE(s.total_qty,0) > 0\n")
    elif stock_filter == "out_of_stock":
        sql.append("\n            AND COALESCE(s.total_qty,0) = 0\n")
    elif stock_filter == "low":
        # 低于预警线（元件自身阈值 >0 时用自身阈值，否则用全局阈值）
        g = float(config.get_setting("low_stock_threshold", 10) or 0)
        sql.append("""
            AND COALESCE(s.total_qty,0) <=
                CASE WHEN p.min_qty > 0 THEN p.min_qty ELSE ? END
        """)
        args.append(g)

    # 排序字段走白名单，避免拼进 SQL 的字符串被注入
    col = order_by if order_by in _SORTABLE_COLUMNS else "category"
    sql.append(f"\n        ORDER BY {col}, p.id\n")
    return query("".join(sql), tuple(args))


def all_categories():
    rows = query("SELECT DISTINCT category FROM parts "
                 "WHERE category IS NOT NULL AND category <> '' ORDER BY category")
    return [r["category"] for r in rows]


def all_suppliers():
    rows = query("SELECT DISTINCT supplier FROM parts "
                 "WHERE supplier IS NOT NULL AND supplier <> '' ORDER BY supplier")
    return [r["supplier"] for r in rows]


# ---------------------------------------------------------------- 库存
def get_stock_rows(part_id):
    return query("SELECT * FROM stock WHERE part_id=? ORDER BY location", (part_id,))


def get_total_qty(part_id):
    row = query_one("SELECT COALESCE(SUM(quantity),0) AS q FROM stock WHERE part_id=?",
                    (part_id,))
    return int(row["q"]) if row else 0


def get_stock_qty(part_id, location):
    """取某库位的当前数量（没有该库位记录则为 0）。"""
    row = query_one("SELECT quantity FROM stock WHERE part_id=? AND location=?",
                    (part_id, location))
    return int(row["quantity"]) if row else 0


def set_stock(part_id, location, quantity):
    """把库位数量直接设为指定值。

    数量为 0 时删掉该库位记录；负数会保留成一条负库存记录
    （用于「先出库、后补登记入库」的场景，见 service.stock_out）。
    """
    location = (location or config.DEFAULT_LOCATION).strip() or config.DEFAULT_LOCATION
    quantity = int(quantity)
    if quantity == 0:
        execute("DELETE FROM stock WHERE part_id=? AND location=?", (part_id, location))
        return 0
    execute("""INSERT INTO stock (part_id, location, quantity) VALUES (?,?,?)
               ON CONFLICT(part_id, location) DO UPDATE SET quantity=excluded.quantity""",
            (part_id, location, quantity))
    return quantity


def change_stock(part_id, location, delta, allow_negative=False):
    """在指定库位上增减库存（不产生流水，供内部调用）。

    默认不允许出现负库存，不足时夹到 0；需要负库存请显式传
    allow_negative=True，或直接用 set_stock 设定明确数量。
    """
    location = (location or config.DEFAULT_LOCATION).strip() or config.DEFAULT_LOCATION
    cur = get_stock_qty(part_id, location)
    new = cur + int(delta)
    if new < 0 and not allow_negative:
        new = 0
    set_stock(part_id, location, new)
    return new


def move_stock(part_id, from_loc, to_loc, qty):
    """库位调拨。"""
    qty = int(qty)
    change_stock(part_id, from_loc, -qty)
    change_stock(part_id, to_loc, qty)


# ---------------------------------------------------------------- 流水
def add_txn(part_id, kind, quantity, location="", operator="", note=""):
    return execute(
        """INSERT INTO txns (part_id, kind, quantity, location, operator, note, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (part_id, kind, int(quantity), location, operator, note, config.now_str()))


def list_txns(part_id=None, limit=500):
    if part_id:
        return query("""SELECT t.*, p.code, p.model, p.name FROM txns t
                        LEFT JOIN parts p ON p.id=t.part_id
                        WHERE t.part_id=? ORDER BY t.id DESC LIMIT ?""",
                     (part_id, limit))
    return query("""SELECT t.*, p.code, p.model, p.name FROM txns t
                    LEFT JOIN parts p ON p.id=t.part_id
                    ORDER BY t.id DESC LIMIT ?""", (limit,))


# ---------------------------------------------------------------- 缓存
def cache_put(code, payload_text):
    execute("""INSERT INTO cache (code, payload, fetched_at) VALUES (?,?,?)
               ON CONFLICT(code) DO UPDATE SET payload=excluded.payload,
                                               fetched_at=excluded.fetched_at""",
            (code.strip().upper(), payload_text, config.now_str()))


def cache_get(code, ttl_days=None):
    row = query_one("SELECT * FROM cache WHERE code=?", (code.strip().upper(),))
    if not row:
        return None
    if ttl_days:
        import datetime
        try:
            t = datetime.datetime.strptime(row["fetched_at"], "%Y-%m-%d %H:%M:%S")
            if (datetime.datetime.now() - t).days >= ttl_days:
                return None
        except Exception:
            return None
    return row


def cache_clear():
    execute("DELETE FROM cache")


def cache_prune(days=None):
    """清掉过期缓存，返回删除条数。

    以前缓存只增不减（每条最多几 KB），积累多了白占空间。
    默认沿用 config.CACHE_TTL_DAYS，判定口径与 cache_get 一致（到期即算过期）。
    """
    import datetime
    # 注意不能写 days or 默认值：days=0 会被当成「没传」而回退成 7 天
    days = config.CACHE_TTL_DAYS if days is None else int(days)
    cutoff = (datetime.datetime.now()
              - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with _lock:
        conn = get_conn()
        cur = conn.execute("DELETE FROM cache WHERE fetched_at IS NULL "
                           "OR fetched_at <= ?", (cutoff,))
        if _txn_depth == 0:
            conn.commit()
        return cur.rowcount


def cache_size():
    """缓存条数与总字节数，用于界面提示。"""
    row = query_one("SELECT COUNT(*) AS n, COALESCE(SUM(LENGTH(payload)),0) AS b "
                    "FROM cache") or {}
    return int(row.get("n", 0)), int(row.get("b", 0))


# ---------------------------------------------------------------- 统计
def stats():
    """首页统计。

    口径说明：
      low_kinds  低库存 = 有货但低于预警线（不含零库存，零库存单独归入缺货，
                 否则同一批件会被两张卡片各算一次）
      total_value 库存金额 = Σ(数量 × 该数量对应档位的单价)，而不是统一按 1 片价
    """
    g = float(config.get_setting("low_stock_threshold", 10) or 0)
    rows = query("""
        SELECT p.id, p.source, p.min_qty, p.ref_price, p.price_tiers,
               COALESCE(s.total_qty, 0) AS total_qty
        FROM parts p
        LEFT JOIN (SELECT part_id, SUM(quantity) AS total_qty
                   FROM stock GROUP BY part_id) s ON s.part_id = p.id
    """)
    kinds = len(rows)
    lcsc_kinds = other_kinds = total_qty = 0
    low_kinds = out_kinds = 0
    total_value = 0.0
    for r in rows:
        if r["source"] == config.SOURCE_LCSC:
            lcsc_kinds += 1
        elif r["source"] == config.SOURCE_OTHER:
            other_kinds += 1
        qty = int(r["total_qty"] or 0)
        total_qty += qty
        if qty == 0:
            out_kinds += 1
            continue
        total_value += pricing.amount_for_qty(r, qty)
        line = r["min_qty"] if (r["min_qty"] and int(r["min_qty"]) > 0) else g
        if qty <= line:
            low_kinds += 1
    return {
        "kinds": kinds,
        "lcsc_kinds": lcsc_kinds,
        "other_kinds": other_kinds,
        "total_qty": total_qty,
        "total_value": float(total_value),
        "low_kinds": low_kinds,
        "out_kinds": out_kinds,
    }
