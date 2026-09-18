# -*- coding: utf-8 -*-
"""验证本轮修复：事务原子性 / 负库存 / 阶梯价 / 统计口径 / 备份 / 缓存 / 老库迁移。

全程使用临时目录，不触碰 E:\\元件库存管理\\data\\inventory.db。
"""
import os
import shutil
import sqlite3
import sys
import tempfile

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

from core import config

TMP = tempfile.mkdtemp(prefix="invfix_")
config.DATA_DIR = TMP
config.DB_PATH = os.path.join(TMP, "inventory.db")
config.BACKUP_DIR = os.path.join(TMP, "backup")
config.SETTINGS_PATH = os.path.join(TMP, "settings.json")
os.makedirs(config.BACKUP_DIR, exist_ok=True)

from core import db, io_utils, lcsc, pricing, service

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'OK ' if cond else 'FAIL'}] {name}" + (f"  → {detail}" if detail else ""))


def section(t):
    print("\n" + "=" * 66)
    print(t)
    print("=" * 66)


# ============================================================ 1. 事务原子性
section("1. 库存与流水的事务原子性")

pid = db.add_part({"code": "C100001", "source": "lcsc", "name": "测试件 A",
                   "model": "A-1", "ref_price": 1.0},
                  location="默认库位", quantity=100)
check("建库位初始库存 = 100", db.get_total_qty(pid) == 100)

# 1a. 出库途中「断电」：把 add_txn 换成会抛异常的函数
orig_add_txn = db.add_txn


def boom(*a, **k):
    raise RuntimeError("模拟断电")


db.add_txn = boom
try:
    service.stock_out(pid, 40, "默认库位")
    check("出库途中异常应向上抛", False, "居然没抛异常")
except RuntimeError:
    check("出库途中异常向上抛出", True)
finally:
    db.add_txn = orig_add_txn

qty_after = db.get_total_qty(pid)
txn_cnt = len(db.list_txns(pid))
check("流水写入失败后库存已回滚（仍为 100）", qty_after == 100, f"实际 {qty_after}")
check("没有留下半截流水", txn_cnt == 0, f"实际 {txn_cnt} 条")

# 1b. 正常出库：库存与流水同时生效
service.stock_out(pid, 40, "默认库位", operator="李杰", note="正常出库")
qty_after = db.get_total_qty(pid)
txns = db.list_txns(pid)
out_txn = [t for t in txns if t["kind"] == "OUT"]
check("正常出库后库存 = 60", qty_after == 60, f"实际 {qty_after}")
check("正常出库后流水记 40", len(out_txn) == 1 and out_txn[0]["quantity"] == 40)
check("库存 = 初始 - 流水出库量", 100 - out_txn[0]["quantity"] == qty_after)

# 1c. 入库与调拨也走事务
service.stock_in(pid, 10, "默认库位", operator="李杰")
check("入库后库存 = 70", db.get_total_qty(pid) == 70, f"实际 {db.get_total_qty(pid)}")
service.transfer(pid, "默认库位", "柜子B", 20, operator="李杰")
rows = {r["location"]: r["quantity"] for r in db.get_stock_rows(pid)}
check("调拨后 默认库位=50 / 柜子B=20",
      rows.get("默认库位") == 50 and rows.get("柜子B") == 20, str(rows))

# ============================================================ 2. 负库存
section("2. 出库超量：默认拒绝 / 可选负库存")

pid2 = db.add_part({"code": "C100002", "source": "lcsc", "name": "测试件 B",
                    "model": "B-1"}, location="默认库位", quantity=5)

try:
    service.stock_out(pid2, 20, "默认库位", allow_negative=False)
    check("默认拒绝超量出库", False, "居然放行了")
except service.ServiceError as e:
    check("默认拒绝超量出库", True, str(e))
check("被拒绝后库存不变（仍为 5）", db.get_total_qty(pid2) == 5,
      f"实际 {db.get_total_qty(pid2)}")

new_qty = service.stock_out(pid2, 20, "默认库位", operator="李杰", allow_negative=True)
txns = [t for t in db.list_txns(pid2) if t["kind"] == "OUT"]
check("允许负库存时库存 = -15", db.get_total_qty(pid2) == -15,
      f"实际 {db.get_total_qty(pid2)}")
check("负库存时返回 -15", new_qty == -15, f"实际 {new_qty}")
check("流水仍记实际出库量 20", bool(txns) and txns[0]["quantity"] == 20)
check("备注写明欠账", bool(txns) and "欠账" in (txns[0]["note"] or ""),
      txns[0]["note"] if txns else "")
check("库存 = 5 - 20 = -15，与流水自洽", db.get_total_qty(pid2) == 5 - 20)

# 设置默认值是否生效
config.set_setting("allow_negative_out", True)
pid2b = db.add_part({"code": "C100003", "source": "lcsc", "name": "测试件 C",
                     "model": "C-1"}, location="默认库位", quantity=1)
service.stock_out(pid2b, 5, "默认库位")           # 不传 allow_negative，读设置
check("设置项 allow_negative_out 生效", db.get_total_qty(pid2b) == -4,
      f"实际 {db.get_total_qty(pid2b)}")
config.set_setting("allow_negative_out", False)

# ============================================================ 3. 阶梯价
section("3. 阶梯价与库存金额")

tiers = pricing.build_tiers([
    {"startNumber": 1, "endNumber": 999, "productPrice": 0.0188},
    {"startNumber": 500, "endNumber": 1999, "productPrice": 0.0146},
    {"startNumber": 50000, "endNumber": -1, "productPrice": 0.0091},
], rate=7.2)
check("阶梯表已折算成人民币并排序",
      tiers == [[1, 999, 0.13536], [500, 1999, 0.10512], [50000, -1, 0.06552]], str(tiers))

# 关键：档位是「起始数量起」的区间，必须取起始数量不超过当前量的最后一档
txt = pricing.tiers_to_text(tiers)
part = {"price_tiers": txt, "ref_price": 0.13536}
check("买 100 个 → 命中 1-999 档 ¥0.13536",
      abs(pricing.price_for_qty(part, 100) - 0.13536) < 1e-9,
      str(pricing.price_for_qty(part, 100)))
check("买 600 个 → 命中 500-1999 档 ¥0.10512（不能退回 1 片档）",
      abs(pricing.price_for_qty(part, 600) - 0.10512) < 1e-9,
      str(pricing.price_for_qty(part, 600)))
check("买 60000 个 → 命中 50000+ 档 ¥0.06552",
      abs(pricing.price_for_qty(part, 60000) - 0.06552) < 1e-9,
      str(pricing.price_for_qty(part, 60000)))
check("无阶梯数据时退回 ref_price",
      pricing.price_for_qty({"ref_price": 2.5}, 100) == 2.5)

# 真实场景：嘉立创的档位都是「x+」不封顶形式（endNumber = -1）
real = pricing.build_tiers([
    {"startNumber": 1, "endNumber": -1, "productPrice": 0.0188},
    {"startNumber": 500, "endNumber": -1, "productPrice": 0.0146},
    {"startNumber": 2000, "endNumber": -1, "productPrice": 0.0123},
], rate=7.2)
rp = {"price_tiers": pricing.tiers_to_text(real), "ref_price": 0.1354}
check("不封顶档位：买 1 个 → ¥0.1354",
      abs(pricing.price_for_qty(rp, 1) - 0.13536) < 1e-9, str(pricing.price_for_qty(rp, 1)))
check("不封顶档位：买 600 个 → ¥0.10512",
      abs(pricing.price_for_qty(rp, 600) - 0.10512) < 1e-9, str(pricing.price_for_qty(rp, 600)))
check("不封顶档位：买 5000 个 → ¥0.08856",
      abs(pricing.price_for_qty(rp, 5000) - 0.08856) < 1e-9, str(pricing.price_for_qty(rp, 5000)))

# 旧 bug 对比：以前一律用 1 片价
old_amount = 600 * 0.1354
new_amount = pricing.amount_for_qty(part, 600)
check("600 个的金额不再按 1 片价算",
      abs(new_amount - old_amount) > 1,
      f"旧算法 ¥{old_amount:.2f} → 新算法 ¥{new_amount:.2f}")

# 与界面/导出行保持一致：数量 × 单价 必须等于金额
row = io_utils.part_to_row({"total_qty": 600, **part})
q = int(row["total_qty"])
u = float(row["ref_price"])
a = float(row["amount"])
check("展示行满足 数量 × 单价 = 金额", abs(q * u - a) < 0.005,
      f"{q} × {u} = {q * u:.2f}, 金额列 {a:.2f}")
row0 = io_utils.part_to_row({"total_qty": 0, **part})
check("零库存时单价显示单片挂牌价", row0["ref_price"] == "0.1354", row0["ref_price"])

# ============================================================ 4. 统计口径
section("4. 低库存 / 缺货 统计口径")

config.set_setting("low_stock_threshold", 10)
# 造 3 种：5 个 / 0 个 / 3 个（前面已有一批测试件，这里单独用一个新库更准）
TMP2 = tempfile.mkdtemp(prefix="invfix2_")
db.close()
config.DB_PATH = os.path.join(TMP2, "inventory.db")
for code, qty in (("C200001", 5), ("C200002", 0), ("C200003", 3)):
    db.add_part({"code": code, "source": "lcsc", "name": code, "model": code},
                location="默认库位", quantity=qty)
st = db.stats()
check("共 3 种元件", st["kinds"] == 3, str(st["kinds"]))
check("低库存 = 2（5 和 3，不含零库存）", st["low_kinds"] == 2, str(st["low_kinds"]))
check("缺货 = 1（零库存单独归类）", st["out_kinds"] == 1, str(st["out_kinds"]))
check("低库存与缺货不再重复计数", st["low_kinds"] + st["out_kinds"] == 3,
      f"{st['low_kinds']} + {st['out_kinds']}")

db.add_part({"code": "C200004", "source": "lcsc", "name": "带阶梯", "model": "T-1",
             "ref_price": 0.1354}, location="默认库位", quantity=0)
db.execute("UPDATE parts SET price_tiers=? WHERE code=?",
           (pricing.tiers_to_text(tiers), "C200004"))
db.set_stock(db.get_part_by_code("C200004")["id"], "默认库位", 600)
st = db.stats()
expected = 600 * 0.1051
check("stats 库存金额按档位计算", abs(st["total_value"] - (5 * 0 + 3 * 0 + expected)) < 0.01,
      f"实际 {st['total_value']:.2f}, 预期 {expected:.2f}")

# ============================================================ 5. 备份
section("5. 备份一致性")
dst = service.backup_db()
check("备份文件已生成", os.path.exists(dst), dst)
bc = sqlite3.connect(dst)
try:
    n = bc.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
    ok = bc.execute("PRAGMA integrity_check").fetchone()[0]
finally:
    bc.close()
check("备份可正常打开且通过完整性检查", ok == "ok", str(ok))
check("备份内容与主库一致", n == db.stats()["kinds"], f"备份 {n} 条 / 主库 {db.stats()['kinds']} 条")

# ============================================================ 6. 老库迁移
section("6. 老数据库自动补列（price_tiers）")

OLD = os.path.join(TMP, "old.db")
c = sqlite3.connect(OLD)
c.executescript("""
CREATE TABLE parts (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, source TEXT,
    name TEXT, model TEXT, ref_price REAL, remark TEXT);
INSERT INTO parts (code, source, name, model, ref_price) VALUES
    ('C300001','lcsc','老库存件','OLD-1', 0.5);
""")
c.commit()
c.close()

db.close()
config.DB_PATH = OLD
db.get_conn()
cols = {r["name"] for r in db.query("PRAGMA table_info(parts)")}
check("老库自动补上 price_tiers 列", "price_tiers" in cols)
check("老库自动补上 descr_en 列", "descr_en" in cols)
check("老库原有数据没丢", len(db.list_parts()) == 1)
p = db.get_part_by_code("C300001")
check("老库迁移后仍可用阶梯价模块取值",
      pricing.price_for_qty(p, 10) == 0.5, str(pricing.price_for_qty(p, 10)))

# ============================================================ 7. 联网 + 缓存
section("7. 联网抓取与缓存瘦身")
db.close()
TMP3 = tempfile.mkdtemp(prefix="invfix3_")
config.DB_PATH = os.path.join(TMP3, "inventory.db")
db.get_conn()

try:
    d = lcsc.fetch_part("C1525", use_cache=False)
    check("抓取 C1525 成功", bool(d.get("code")), d.get("code"))
    check("返回里带完整阶梯价表", bool(d.get("price_tiers")), (d.get("price_tiers") or "")[:60])
    n, b = db.cache_size()
    per = b / n if n else 0
    check("缓存已剔除 _raw，单条体积明显变小", per < 4096,
          f"单条 {per:.0f} 字节（修改前约 5200 字节）")
    cached = db.cache_get("C1525")
    check("缓存内容不含 _raw 字段", "_raw" not in (cached["payload"] if cached else ""))

    # 缓存读取仍可用（走缓存路径）
    d2 = lcsc.fetch_part("C1525")
    check("二次查询命中缓存", d2.get("_from_cache") is True)
    check("缓存数据也能算出金额",
          pricing.amount_for_qty(d2, 1000) > 0,
          f"1000 个 ≈ ¥{pricing.amount_for_qty(d2, 1000):.2f}")

    # 过期清理
    removed = db.cache_prune(days=0)
    check("cache_prune(0) 能清掉过期缓存", db.cache_size()[0] == 0,
          f"清掉 {removed} 条，剩 {db.cache_size()[0]} 条")
except Exception as e:
    check("联网测试（网络不可用则跳过）", False, f"{type(e).__name__}: {e}")

# ============================================================ 8. 排序白名单
section("8. 排序字段白名单（防 SQL 注入）")
db.close()
TMP4 = tempfile.mkdtemp(prefix="invfix4_")
config.DB_PATH = os.path.join(TMP4, "inventory.db")
db.add_part({"code": "C400001", "source": "lcsc", "name": "x", "model": "x"},
            location="默认库位", quantity=1)
try:
    rows = db.list_parts(order_by="name; DROP TABLE parts--")
    check("非法排序字段被忽略，未执行注入", len(db.list_parts()) == 1, f"{len(rows)} 行")
except Exception as e:
    check("非法排序字段被忽略", False, f"{type(e).__name__}: {e}")

# ============================================================ 汇总
section("汇总")
print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
if FAIL:
    print("失败项：")
    for f in FAIL:
        print("  -", f)
shutil.rmtree(TMP, ignore_errors=True)
shutil.rmtree(TMP2, ignore_errors=True)
shutil.rmtree(TMP3, ignore_errors=True)
shutil.rmtree(TMP4, ignore_errors=True)
print("（临时目录已清理，用户数据未改动）")
sys.exit(1 if FAIL else 0)
