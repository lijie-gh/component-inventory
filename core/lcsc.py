# -*- coding: utf-8 -*-
"""嘉立创商城数据客户端。

对接嘉立创 SMT 元件库公开查询接口，按 C 号拉取元件的完整资料：
型号、厂商、封装、分类、库存、阶梯价、数据手册、商品链接等。

设计要点
    1. 零第三方依赖，仅用标准库 urllib，任何 Python 环境可直接跑。
    2. 查询结果按 C 号写入本地缓存，默认 7 天内不再重复联网。
    3. 接口不可用时自动降级到缓存，再不行返回错误信息，不影响手工录入。
"""
import gzip
import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from . import config, db, i18n, pricing, servers


class LcscError(Exception):
    """查询失败。"""


# ---------------------------------------------------------------- 网络
def _post_json(url, payload, timeout=None):
    timeout = timeout or config.REQUEST_TIMEOUT
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("User-Agent", config.USER_AGENT)
    req.add_header("Content-Type", "application/json;charset=UTF-8")
    req.add_header("Accept", "application/json, text/plain, */*")
    req.add_header("Accept-Language", "zh-CN,zh;q=0.9")
    req.add_header("Accept-Encoding", "gzip, deflate")
    req.add_header("Origin", "https://jlcpcb.com")
    req.add_header("Referer", "https://jlcpcb.com/")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            enc = (resp.headers.get("Content-Encoding") or "").lower()
            if "gzip" in enc:
                raw = gzip.decompress(raw)
            elif "deflate" in enc:
                try:
                    raw = gzip.decompress(raw)
                except Exception:
                    import zlib
                    raw = zlib.decompress(raw, -zlib.MAX_WBITS)
            return json.loads(raw.decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        raise LcscError(f"商城返回 HTTP {e.code}，请稍后重试")
    except urllib.error.URLError as e:
        raise LcscError(f"无法连接嘉立创商城（{e.reason}），请检查网络")
    except json.JSONDecodeError:
        raise LcscError("商城返回数据格式异常")
    except Exception as e:
        raise LcscError(f"查询失败：{e}")


# ---------------------------------------------------------------- 解析
def _normalize_code(text):
    """把用户输入规范成 C 号，例如 'c1525' / 'C-1525' / '1525' -> 'C1525'。"""
    if not text:
        return ""
    t = re.sub(r"[^0-9A-Za-z]", "", str(text)).upper()
    m = re.fullmatch(r"C?0*(\d+)", t)
    if m:
        return "C" + m.group(1)
    return t


def is_lcsc_code(text):
    """判断是不是一个合法的嘉立创 C 号。"""
    if not text:
        return False
    return bool(re.fullmatch(r"C\d{3,9}", _normalize_code(text)))


def _parse_item(raw):
    """把接口返回的一条记录整理成程序内部字段。"""
    code = raw.get("componentCode") or ""
    if not code:
        # 部分记录 C 号藏在 urlSuffix 尾巴上，如 "1877-CL05B104KO5NNNC/C1525"
        suffix = raw.get("urlSuffix") or ""
        m = re.search(r"/?(C\d{3,9})$", suffix)
        if m:
            code = m.group(1)

    prices = raw.get("componentPrices") or []
    price_text = _fmt_prices(prices) if prices else ""

    # 这个接口的报价是美元（国际站），按设置里的汇率折成人民币，
    # 免得「参考单价(元)」和库存金额少算好几倍。
    rate = float(config.get_setting("usd_rate", 7.2) or 7.2)
    tiers = pricing.build_tiers(prices, rate)

    # ref_price 只作为「单片参考价」展示；真正算库存金额的是整张阶梯表，
    # 按当前库存数量匹配档位（见 core/pricing.py），否则会高估一到两倍。
    ref_price = None
    if tiers:
        unit = pricing.price_for_qty({"price_tiers": tiers}, 1)
        ref_price = round(unit or tiers[0][2], 4)

    lib = raw.get("componentLibraryType")
    lib_type = {"base": "基础库", "expand": "扩展库",
                "extend": "扩展库", "extended": "扩展库"}.get(
        (lib or "").lower(), lib or "")

    # 描述优先级：erp 名称 > describe > 厂商+型号
    name = (raw.get("erpComponentName") or "").strip()
    descr = (raw.get("describe") or "").strip()
    model = (raw.get("componentModelEn") or "").strip()
    brand = (raw.get("componentBrandEn") or "").strip()

    display = name or descr or f"{brand} {model}".strip()
    if display and len(display) > 120:
        display = display[:120] + "…"

    # 参数值：从商城属性表里挑关键参数（阻值/容值/耐压/精度优先），
    # 让「参数值」列能独立用于检索，而不是简单重复名称。
    value_text = i18n.pick_value_text(raw.get("attributes"), fallback=name)

    # 详细描述：这个接口只提供英文（describe 与属性表都是英文，中文只出现在
    # erpComponentName 里，而它已被用作「名称」），所以在这里用本地术语词典
    # 整理成中文；英文原文一并留着，方便核对。
    descr_cn = i18n.localize_desc(raw.get("attributes"), descr,
                                  raw.get("componentTypeEn"))

    return {
        "code": code,
        "source": config.SOURCE_LCSC,
        "supplier": "嘉立创商城",
        "name": display or model or code,
        "model": model,
        "brand": brand,
        "package": (raw.get("componentSpecificationEn") or "").strip(),
        "category": _guess_category(raw),
        "value": value_text,
        "descr": (descr_cn or descr),
        "descr_en": descr,
        "type_cn": i18n.tr_type(raw.get("componentTypeEn")),
        "datasheet": (raw.get("dataManualUrl")
                      or raw.get("dataManualFileAccessIdUrl")
                      or raw.get("dataManualOfficialLink") or ""),
        "image_url": (raw.get("componentImageUrl")
                      or raw.get("productBigImageAccessIdUrl")
                      or raw.get("minImageAccessIdUrl") or ""),
        "lib_type": lib_type,
        "unit": "个",
        "ref_price": ref_price,
        "price_info": price_text,
        "price_tiers": pricing.tiers_to_text(tiers),
        "stock_market": raw.get("stockCount"),
        "min_purchase": raw.get("minPurchaseNum"),
        "link": raw.get("lcscGoodsUrl") or "",
        "_raw": raw,
    }


def _fmt_prices(prices):
    parts = []
    for p in sorted(prices, key=lambda x: int(x.get("startNumber") or 0)):
        s = p.get("startNumber")
        e = p.get("endNumber")
        v = p.get("productPrice")
        try:
            v = float(v)
        except Exception:
            continue
        seg = f"{s}+" if (e in (-1, None) or int(e) < 0) else f"{s}-{e}"
        parts.append(f"{seg}档 ${v:g}")
    if not parts:
        return ""
    return "（美元原价）" + "  ".join(parts[:6])


_CAT_RULES = [
    ("电阻", ["resistor", "电阻", "chip resistor"]),
    ("电容", ["capacitor", "电容", "mlcc"]),
    ("电感", ["inductor", "电感"]),
    ("磁珠", ["ferrite", "磁珠"]),
    ("二极管", ["diode", "二极管", "rectifier", "tvs", "zener", "schottky"]),
    ("三极管", ["transistor", "三极管", "bjt"]),
    ("MOS管", ["mosfet", "mos", "jfet"]),
    ("晶振", ["crystal", "oscillator", "resonator", "晶振"]),
    ("LED", ["led", "light emitting", "发光"]),
    ("连接器", ["connector", "header", "socket", "terminal", "连接器", "排针", "排母"]),
    ("开关", ["switch", "button", "按键", "开关"]),
    ("继电器", ["relay", "继电器"]),
    ("保险丝", ["fuse", "保险丝", "ptc", "varistor", "压敏"]),
    ("电源芯片", ["ldo", "regulator", "dc-dc", "buck", "boost", "voltage regulator",
                  "pmic", "电源", "稳压"]),
    ("运放", ["op amp", "opamp", "operational amplifier", "运放", "amplifier"]),
    ("比较器", ["comparator", "比较器"]),
    ("逻辑芯片", ["logic", "gate", "inverter", "shift register", "逻辑", "74"]),
    ("MCU", ["microcontroller", "mcu", "arm", "单片机"]),
    ("存储器", ["memory", "flash", "eeprom", "sram", "dram", "存储"]),
    ("接口芯片", ["interface", "uart", "i2c", "spi", "can", "usb", "rs232", "rs485",
                  "can transceiver", "接口"]),
    ("传感器", ["sensor", "传感器"]),
    ("光耦", ["optocoupler", "光耦", "photocoupler"]),
    ("晶振", ["xtal"]),
    ("模块", ["module", "模块"]),
    ("结构件", ["hardware", "standoff", "screw", "结构"]),
]


def _guess_category(raw):
    """根据接口给的元件类型描述猜一个中文分类。"""
    text = " ".join(str(raw.get(k) or "") for k in
                    ("componentTypeEn", "firstSortName", "secondSortName",
                     "describe", "erpComponentName")).lower()
    for cat, keys in _CAT_RULES:
        for k in keys:
            if k in text:
                return cat
    return "其它"


# ---------------------------------------------------------------- 对外
def fetch_part(code, use_cache=True, force=False):
    """按 C 号查询单个元件资料。

    返回 dict（字段同 parts 表）；失败抛 LcscError。
    """
    code = _normalize_code(code)
    if not code:
        raise LcscError("请输入嘉立创 C 号，例如 C1525")
    if not force:
        cached = db.cache_get(code, ttl_days=config.CACHE_TTL_DAYS if use_cache else None)
        if cached:
            try:
                data = json.loads(cached["payload"])
                data["_from_cache"] = True
                data["_fetched_at"] = cached["fetched_at"]
                return data
            except Exception:
                pass

    resp = _post_json(servers.current_endpoint(), {
        "currentPage": 1,
        "pageSize": 25,
        "keyword": code,
    })
    if not isinstance(resp, dict) or resp.get("code") != 200:
        msg = (resp or {}).get("msg") or "商城接口返回异常"
        raise LcscError(f"查询失败：{msg}")

    info = (((resp.get("data") or {}).get("componentPageInfo")) or {})
    items = info.get("list") or []

    # 优先精确匹配 C 号；找不到就退而求其次用第一条
    hit = None
    for it in items:
        if (it.get("componentCode") or "").upper() == code:
            hit = it
            break
    if hit is None:
        for it in items:
            if code in str(it.get("urlSuffix") or "").upper():
                hit = it
                break
    if hit is None:
        raise LcscError(f"嘉立创商城未收录元件 {code}，请确认 C 号是否正确")

    data = _parse_item(hit)
    data["_from_cache"] = False
    data["_fetched_at"] = config.now_str()
    # 缓存只存整理后的字段：原来的 _raw（接口完整原始返回）占了每条约 6 KB
    # 的绝大部分，而且没有任何代码读它，没必要落盘。
    slim = {k: v for k, v in data.items() if not k.startswith("_")}
    try:
        db.cache_put(code, json.dumps(slim, ensure_ascii=False))
    except Exception:
        pass
    return data


def fetch_many(codes, progress=None, force=False):
    """批量查询，返回 {code: (data|None, err|None)}。progress(done, total, code)。"""
    result = {}
    total = len(codes)
    for i, c in enumerate(codes, 1):
        code = _normalize_code(c)
        try:
            result[c] = (fetch_part(code, force=force), None)
        except Exception as e:
            result[c] = (None, str(e))
        if progress:
            try:
                progress(i, total, c)
            except Exception:
                pass
    return result


def suggest(keyword, limit=20):
    """按型号 / 关键词模糊搜索商城元件，返回候选列表。"""
    kw = (keyword or "").strip()
    if not kw:
        return []
    resp = _post_json(servers.current_endpoint(), {
        "currentPage": 1,
        "pageSize": max(1, min(limit, 50)),
        "keyword": kw,
    })
    if not isinstance(resp, dict) or resp.get("code") != 200:
        raise LcscError("商城搜索失败")
    info = (((resp.get("data") or {}).get("componentPageInfo")) or {})
    out = []
    for it in (info.get("list") or []):
        out.append(_parse_item(it))
    return out


def product_url(code):
    """生成国内商城的可读商品链接。"""
    code = _normalize_code(code)
    return config.LCSC_SEARCH_URL.format(code=urllib.parse.quote(code))
