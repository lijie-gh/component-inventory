# -*- coding: utf-8 -*-
"""阶梯价与库存金额计算。

嘉立创的报价是分档的（1 片、1000 片、10000 片……数量越大单价越低）。
早期版本只把「1 片档」存下来当参考单价，导致库存金额普遍高估一到两倍，
所以这里把整张阶梯表存起来，按当前库存数量去匹配对应档位。

阶梯表存储格式（JSON 文本，存在 parts.price_tiers）：
    [[起始数量, 结束数量, 人民币单价], ...]
结束数量为 -1 表示该档不封顶（如「50000+」）。
"""
import json


def build_tiers(prices, rate):
    """把商城接口的报价数组转成阶梯表（折算成人民币）。

    prices: [{"startNumber": 1, "endNumber": 999, "productPrice": 0.0188}, ...]
    rate  : 美元兑人民币汇率
    """
    tiers = []
    for p in prices or []:
        try:
            start = int(p.get("startNumber") or 0)
            raw_end = p.get("endNumber")
            end = int(raw_end) if raw_end not in (None, "", "None") else -1
            if end is not None and end < 0:
                end = -1
            usd = float(p.get("productPrice"))
        except (TypeError, ValueError):
            continue
        if start < 0 or usd < 0:
            continue
        tiers.append([start, end, round(usd * float(rate), 6)])
    tiers.sort(key=lambda t: t[0])
    return tiers


def tiers_to_text(tiers):
    """阶梯表 -> 可存库的 JSON 文本（空表存空串）。"""
    if not tiers:
        return ""
    try:
        return json.dumps(tiers, ensure_ascii=False)
    except (TypeError, ValueError):
        return ""


def parse_tiers(value):
    """把库里存的 price_tiers 解析成阶梯表；兼容已经存成 list 的情况。"""
    if not value:
        return []
    if isinstance(value, list):
        data = value
    else:
        try:
            data = json.loads(value)
        except (TypeError, ValueError):
            return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        try:
            start, end, price = item[0], item[1], item[2]
            start = int(start)
            end = int(end)
            price = float(price)
        except (TypeError, ValueError, IndexError):
            continue
        out.append([start, end, price])
    out.sort(key=lambda t: t[0])
    return out


def _field(obj, key, default=None):
    """从 dict 或 sqlite3.Row 里安全取值（Row 没有 .get()）。"""
    if obj is None:
        return default
    getter = getattr(obj, "get", None)
    if callable(getter):
        try:
            return getter(key, default)
        except TypeError:
            pass
    try:
        return obj[key]
    except (KeyError, IndexError, TypeError):
        return default


def price_for_qty(part, qty):
    """按数量匹配单价。

    注意嘉立创的档位大多是「开始数量起、不封顶」的形式（1+ / 500+ / 2000+ …），
    所以不能取第一个满足条件的档，而要取**起始数量不超过当前数量的最后一档**，
    否则买 600 个会错误地按 1 片档计价。
    """
    tiers = parse_tiers(_field(part, "price_tiers"))
    q = int(qty or 0)
    if tiers and q > 0:
        best = None
        for start, end, price in tiers:          # 已按起始数量升序
            if q < start:
                continue
            if end >= 0 and q > end:             # 落在该区间之后，继续往后找
                continue
            best = price                          # 后面的档更优惠，覆盖前面的
        if best is not None:
            return best
    try:
        return float(_field(part, "ref_price") or 0)
    except (TypeError, ValueError):
        return 0.0


def amount_for_qty(part, qty):
    """库存金额 = 数量 × 对应档位单价。

    单价先按 4 位小数取整再相乘，这样界面上「数量 × 单价」能手工对得上金额。
    """
    return int(qty or 0) * round(price_for_qty(part, qty), 4)


def describe_tiers(tiers):
    """把阶梯表渲染成一句人话，用于界面提示。"""
    if not tiers:
        return ""
    parts = []
    for start, end, price in tiers[:6]:
        seg = f"{start}+" if end < 0 else f"{start}-{end}"
        parts.append(f"{seg}：¥{price:g}")
    return "　".join(parts)
