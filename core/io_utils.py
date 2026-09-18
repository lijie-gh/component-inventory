# -*- coding: utf-8 -*-
"""导入导出：Excel / CSV 读取、CSV 双向同步、BOM 文本解析。"""
import csv
import os
import re

from . import config, db, pricing, xlsread

# 导出/导入统一列名
COLUMNS = [
    ("code", "嘉立创C号"),
    ("source_label", "来源"),
    ("model", "型号"),
    ("name", "名称/描述"),
    ("brand", "厂商"),
    ("package", "封装"),
    ("category", "分类"),
    ("value", "参数值"),
    ("total_qty", "库存总数"),
    ("locations", "库位明细"),
    ("unit", "单位"),
    ("min_qty", "预警阈值"),
    ("ref_price", "参考单价(按量)"),
    ("amount", "库存金额"),
    ("lib_type", "库类型"),
    ("supplier", "采购渠道"),
    ("datasheet", "数据手册"),
    ("remark", "备注"),
    ("last_fetch", "商城同步时间"),
]


def part_to_row(p):
    """整理成界面 / 导出用的展示行。

    单价按「当前库存数量」去匹配阶梯档位（嘉立创报价分档，量越大单价越低），
    库存金额 = 数量 × 该档单价，因此手工用「数量 × 单价」也能对得上。
    零库存的件没有档位可匹配，退回单片挂牌价。
    """
    qty = int(p.get("total_qty") or 0)
    if qty > 0:
        # 与 pricing.amount_for_qty 保持同样的 4 位小数口径，免得显示出来的
        # 单价乘上数量跟金额列差几分钱
        price = round(pricing.price_for_qty(p, qty), 4)
    else:
        try:
            price = round(float(p.get("ref_price") or 0), 4)
        except (TypeError, ValueError):
            price = 0.0
    amount = (qty * price) if price else ""
    return {
        "code": p.get("code") or "",
        "source_label": config.SOURCE_LABEL.get(p.get("source"), ""),
        "model": p.get("model") or "",
        "name": p.get("name") or "",
        "brand": p.get("brand") or "",
        "package": p.get("package") or "",
        "category": p.get("category") or "",
        "value": p.get("value") or "",
        "total_qty": qty,
        "locations": p.get("locations") or "",
        "unit": p.get("unit") or "个",
        "min_qty": p.get("min_qty") or 0,
        "ref_price": f"{price:.4f}" if price else "",
        "amount": f"{amount:.2f}" if amount != "" else "",
        "lib_type": p.get("lib_type") or "",
        "supplier": p.get("supplier") or "",
        "datasheet": p.get("datasheet") or "",
        "remark": p.get("remark") or "",
        "last_fetch": p.get("last_fetch") or "",
    }


def export_csv(parts, path=None):
    """导出元件清单为 CSV（UTF-8-BOM，Excel 直接打开不乱码）。"""
    if path is None:
        name = f"元件库存_{config.today_str()}.csv"
        path = os.path.join(config.EXPORT_DIR, name)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([label for _, label in COLUMNS])
        for p in parts:
            row = part_to_row(p)
            w.writerow([row[k] for k, _ in COLUMNS])
    return path


def export_txns_csv(txns, path=None):
    """导出出入库流水。"""
    if path is None:
        path = os.path.join(config.EXPORT_DIR, f"出入库流水_{config.today_str()}.csv")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    head = ["时间", "类型", "嘉立创C号", "型号", "名称", "数量", "库位", "操作人", "备注"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(head)
        for t in txns:
            w.writerow([
                t.get("created_at", ""),
                config.TXN_LABEL.get(t.get("kind"), t.get("kind")),
                t.get("code") or "", t.get("model") or "", t.get("name") or "",
                t.get("quantity", 0), t.get("location") or "",
                t.get("operator") or "", t.get("note") or "",
            ])
    return path


# ---------------------------------------------------------------- 导入
# 表头别名表：从左到右依次匹配，覆盖程序自身的导出、立创商城 / 嘉立创的
# 订单导出、以及各家网店的购买记录表头。键统一去空格、去括号、转小写。
_HEADER_ALIASES = {
    # C 号
    "嘉立创c号": "code", "c号": "code", "code": "code", "lcsc": "code",
    "lcsc编号": "code", "立创编号": "code", "立创商城编号": "code",
    "嘉立创编号": "code", "商品编号": "code", "商品编码": "code",
    "元件编号": "code", "器件编号": "code", "元件编码": "code",
    "物料编号": "code", "物料编码": "code", "编码": "code", "编号": "code",
    # 来源 / 型号 / 名称
    "来源": "source_label", "source": "source_label",
    "型号": "model", "mpn": "model", "model": "model", "partnumber": "model",
    "制造商编号": "model", "规格型号": "model", "商品型号": "model",
    "产品型号": "model", "型号规格": "model", "器件型号": "model",
    "名称/描述": "name", "名称": "name", "描述": "name", "name": "name",
    "商品名称": "name", "元件名称": "name", "产品名称": "name",
    "物料名称": "name", "器件名称": "name", "商品描述": "name",
    # 厂商 / 封装 / 分类
    "厂商": "brand", "品牌": "brand", "brand": "brand", "制造商": "brand",
    "生产厂商": "brand", "品牌厂商": "brand", "厂家": "brand",
    "封装": "package", "package": "package", "封装形式": "package",
    "封装规格": "package", "footprint": "package",
    "分类": "category", "category": "category", "类别": "category",
    "元件分类": "category", "元件类型": "category",
    # 参数值
    "参数值": "value", "value": "value", "参数": "value", "规格": "value",
    "规格描述": "value",
    # 数量
    "库存总数": "total_qty", "数量": "total_qty", "库存": "total_qty",
    "qty": "total_qty", "quantity": "total_qty", "num": "total_qty",
    "购买数量": "total_qty", "下单数量": "total_qty", "采购数量": "total_qty",
    "订货数量": "total_qty", "订购数量": "total_qty", "出货数量": "total_qty",
    "入库数量": "total_qty", "购买数": "total_qty", "采购数": "total_qty",
    "数量合计": "total_qty",
    # 库位
    "库位明细": "locations", "库位": "locations", "位置": "locations",
    "location": "locations", "存放位置": "locations",
    # 单位 / 阈值 / 单价
    "单位": "unit", "unit": "unit",
    "预警阈值": "min_qty", "预警": "min_qty", "min_qty": "min_qty",
    "最小库存": "min_qty",
    "参考单价": "ref_price", "单价": "ref_price", "price": "ref_price",
    "采购单价": "ref_price", "商品单价": "ref_price", "含税单价": "ref_price",
    "购买单价": "ref_price", "unitprice": "ref_price",
    # 其它
    "库类型": "lib_type",
    "采购渠道": "supplier", "供应商": "supplier", "supplier": "supplier",
    "供货商": "supplier", "来源渠道": "supplier", "购买渠道": "supplier",
    "数据手册": "datasheet", "datasheet": "datasheet", "规格书": "datasheet",
    "备注": "remark", "remark": "remark", "note": "remark",
}

# 字段名 -> 中文列名（提示信息里用）
FIELD_LABEL = {key: label for key, label in COLUMNS}

_C_CODE_RE = re.compile(r"C\d{3,9}", re.I)
_HEADER_SCAN = 12          # 只在前 12 行里找表头


def _map_header(name):
    key = str(name or "").strip().lower()
    key = re.sub(r"[（(][^）)]*[）)]", "", key)        # 去掉「数量(个)」里的单位
    key = re.sub(r"[\s:：*、·．.]+", "", key)          # 去掉空格与分隔符
    return _HEADER_ALIASES.get(key)


def _clean_qty(value):
    """把「1,000 个」「100.0」这类文本转成整数。"""
    s = re.sub(r"[^\d.\-]", "", str(value or ""))
    if not s:
        return 0
    try:
        return int(float(s))
    except Exception:
        return 0


def _clean_price(value):
    s = re.sub(r"[^\d.]", "", str(value or ""))
    if not s:
        return None
    try:
        v = float(s)
    except Exception:
        return None
    return v or None


def _normalize_item(item):
    """规范化一条记录：C 号提纯、数量/单价转数字。"""
    code = str(item.get("code") or "").strip().upper().replace(" ", "")
    if code:
        m = _C_CODE_RE.search(code)
        if m:
            item["code"] = m.group(0).upper()
        else:
            # 「商品编号」列里不是 C 号的，当型号用，避免丢信息
            item.pop("code", None)
            if not item.get("model"):
                item["model"] = code
    for k in ("total_qty", "min_qty"):
        if k in item:
            item[k] = _clean_qty(item[k])
    if "ref_price" in item:
        p = _clean_price(item["ref_price"])
        if p is None:
            item.pop("ref_price", None)
        else:
            item["ref_price"] = p
    for k, v in list(item.items()):
        if isinstance(v, str):
            item[k] = v.strip()
    return item


def _find_header(grid):
    """在前若干行里找表头行，返回 (行号(0基), {列号: 字段名})。"""
    best = (0, {})
    for i, row in enumerate(grid[:_HEADER_SCAN]):
        m, seen = {}, set()
        for c, cell in enumerate(row):
            f = _map_header(cell)
            if f and f not in seen:
                m[c] = f
                seen.add(f)
        if len(m) >= 2 and ({"code", "model", "name"} & seen):
            if len(m) > len(best[1]):
                best = (i, m)
    return best


def _guess_columns(grid):
    """没有表头时的兜底：自己找"像 C 号的列"和"像数量的列"。"""
    ncol = max((len(r) for r in grid), default=0)
    code_col, best_hits = None, 0
    for c in range(ncol):
        vals = [str(r[c]).strip() for r in grid if c < len(r) and str(r[c]).strip()]
        if not vals:
            continue
        hits = sum(1 for v in vals if _C_CODE_RE.fullmatch(v))
        if hits > best_hits:
            code_col, best_hits = c, hits
    qty_col, best_ratio = None, 0.0
    for c in range(ncol):
        if c == code_col:
            continue
        vals = [str(r[c]).strip() for r in grid if c < len(r) and str(r[c]).strip()]
        if not vals:
            continue
        ok = sum(1 for v in vals
                 if re.fullmatch(r"\d{1,7}", v.replace(",", "")))
        ratio = ok / len(vals)
        # 取最靠右且比例达标的那一列（采购表里数量通常在单价/金额之前）
        if ratio >= 0.7 and ratio >= best_ratio:
            qty_col, best_ratio = c, ratio
    m = {}
    if code_col is not None:
        m[code_col] = "code"
    if qty_col is not None:
        m[qty_col] = "total_qty"
    return m


def rows_to_items(grid):
    """原始二维表 -> (记录列表, 识别信息)。"""
    grid = [[("" if c is None else str(c)) for c in row] for row in grid]
    hdr, mapping = _find_header(grid)
    info = {"header_row": hdr + 1 if mapping else 0, "mapping": mapping,
            "guessed": False, "raw_rows": len(grid)}
    if not mapping:
        mapping = _guess_columns(grid)
        info["mapping"] = mapping
        info["guessed"] = True
        info["header_row"] = 0
        body = grid
    else:
        body = grid[hdr + 1:]

    out = []
    for row in body:
        item = {}
        for col, field in mapping.items():
            if col < len(row):
                val = str(row[col]).strip()
                if val and val.lower() not in ("nan", "none", "null", "-"):
                    item[field] = val
        _normalize_item(item)
        if item.get("code") or item.get("model") or item.get("name"):
            out.append(item)
    return out, info


def read_table_file(path, sheet=None):
    """读取 Excel / CSV 等任意表格，返回 (记录列表, 识别信息)。

    识别信息包含：可用工作表名、实际用的表、表头行号、列映射、是否靠猜测。
    """
    sheets = xlsread.read_sheets(path)
    usable = [s for s in sheets if s.get("rows")]
    if not usable:
        raise ValueError("这个文件里没有数据")
    chosen = None
    if sheet:
        chosen = next((s for s in usable if s["name"] == sheet), None)
    if chosen is None:
        # 多个表时挑行数最多的那个（备注页通常很小）
        chosen = max(usable, key=lambda s: len(s["rows"]))
    items, info = rows_to_items(chosen["rows"])
    info["sheets"] = [s["name"] for s in usable]
    info["sheet"] = chosen["name"]
    info["format"] = xlsread.detect_format(path)
    return items, info


def read_csv(path):
    """读取 CSV，返回 dict 列表（键为内部字段名）。自动识别表头。"""
    sheets = xlsread.read_sheets(path)
    if not sheets:
        return []
    return rows_to_items(sheets[0]["rows"])[0]



# ---------------------------------------------------------------- BOM 文本
_CODE_RE = re.compile(r"\bC(\d{3,9})\b", re.I)
_QTY_RE = re.compile(r"(?:x|×|\*|\s)\s*(\d{1,6})\s*$", re.I)


def parse_bom_text(text, default_qty=0):
    """解析粘贴的 BOM / C 号清单。

    支持这些写法（每行一条）：
        C1525
        C1525 100
        C1525 x100
        C1525,100
        CL05B104KO5NNNC,C1525,100      （取其中的 C 号与末尾数量）
        1  C1525  100nF  0402  100     （立创BOM导出，取 C 号与数量）

    返回 [{'code': 'C1525', 'qty': 100}, ...]，按 C 号去重并累加数量。
    """
    seen = {}
    order = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _CODE_RE.search(line)
        if not m:
            continue
        code = "C" + m.group(1)
        # 数量：优先取行尾数字，其次取最后一个独立数字段
        qty = default_qty
        tail = line[m.end():].strip(" \t,;|")
        nums = re.findall(r"\d{1,7}", tail)
        if nums:
            try:
                qty = int(nums[-1])
            except Exception:
                qty = default_qty
        elif default_qty:
            qty = default_qty
        if code in seen:
            seen[code] += int(qty or 0)
        else:
            seen[code] = int(qty or 0)
            order.append(code)
    return [{"code": c, "qty": seen[c]} for c in order]


def parse_any_codes(text):
    """只提取文本里所有 C 号（顺序保留、去重）。"""
    return [d["code"] for d in parse_bom_text(text)]
