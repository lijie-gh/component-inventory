# -*- coding: utf-8 -*-
"""商城接入点（服务器）自动检测与选择。

嘉立创/LCSC 在不同地区的接入点延迟差别很大，这里列出所有已知的接入点，
启动后并发实测，挑「最快且真的能取到数据」的那个用。

为什么不能只测延迟
------------------
LCSC 国际商城的接口（wmsc.lcsc.com）**能连通、也返回 HTTP 200**，
但内容是一句 `The static resource is unavailable`——它需要页面带出来的
反爬签名。如果只 ping 或者只看状态码，就会把这个「离得近但取不到数据」
的地址当成最优服务器，用户反而查不到任何元件。

所以探测方式是：**真的发一次 C1525 查询，检查返回里有没有商品**。

检测结果会记在设置里（`server_best` / `server_latency`），
`server_profile` 为 `auto` 时用检测结果，也可以手动锁定某个接入点。
"""
import gzip
import json
import time
import urllib.error
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor

from . import config

# 探测用的 C 号（常见、必然有货的电阻）
PROBE_CODE = "C1525"

PROFILES = [
    {
        "id": "jlcpcb",
        "name": "嘉立创国际站 (jlcpcb.com)",
        "endpoint": config.LCSC_ENDPOINT,
        "note": "全球可访问，接口稳定，资料为英文、报价美元",
    },
    {
        "id": "lcsc",
        "name": "LCSC 国际商城 (lcsc.com)",
        "endpoint": "https://wmsc.lcsc.com/wmsc/search/global/result",
        "note": "全球 CDN，但接口要求反爬签名，通常取不到数据",
    },
    {
        "id": "szlcsc",
        "name": "嘉立创国内站 (szlcsc.com)",
        "endpoint": "https://item.szlcsc.com/api/search/global/result",
        "note": "国内访问最快，境外网络通常不可用",
    },
]

DEFAULT_ID = PROFILES[0]["id"]


def by_id(pid):
    for p in PROFILES:
        if p["id"] == pid:
            return p
    return None


# ---------------------------------------------------------------- 探测
def _post(url, payload, timeout):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("User-Agent", config.USER_AGENT)
    req.add_header("Content-Type", "application/json;charset=UTF-8")
    req.add_header("Accept", "application/json, text/plain, */*")
    req.add_header("Accept-Encoding", "gzip, deflate")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        enc = (resp.headers.get("Content-Encoding") or "").lower()
        if "gzip" in enc:
            raw = gzip.decompress(raw)
        elif "deflate" in enc:
            try:
                raw = gzip.decompress(raw)
            except Exception:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        return resp.status, json.loads(raw.decode("utf-8", "replace"))


def probe(profile, timeout=8):
    """真实查询一次，返回 (是否取到数据, 耗时毫秒, 说明)。"""
    payload = {"currentPage": 1, "pageSize": 1, "keyword": PROBE_CODE}
    t0 = time.time()
    try:
        _status, data = _post(profile["endpoint"], payload, timeout)
        ms = (time.time() - t0) * 1000
        if not isinstance(data, dict):
            return False, ms, "返回格式不是 JSON 对象"
        if data.get("code") != 200:
            msg = str(data.get("msg") or data.get("code") or "")[:70]
            return False, ms, msg or "接口返回异常"
        info = ((data.get("data") or {}).get("componentPageInfo")) or {}
        items = info.get("list") or []
        if not items:
            return False, ms, "接口可用但没有返回数据"
        return True, ms, ""
    except urllib.error.HTTPError as e:
        return False, (time.time() - t0) * 1000, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, (time.time() - t0) * 1000, f"无法连接（{e.reason}）"
    except Exception as e:
        return False, (time.time() - t0) * 1000, type(e).__name__


def detect(timeout=8):
    """并发探测全部接入点，按「可用优先、延迟其次」排序返回。"""
    results = []
    with ThreadPoolExecutor(max_workers=len(PROFILES) or 1) as ex:
        futs = {ex.submit(probe, p, timeout): p for p in PROFILES}
        for f, p in futs.items():
            try:
                ok, ms, note = f.result()
            except Exception as e:
                ok, ms, note = False, 0.0, type(e).__name__
            results.append({**p, "ok": ok, "ms": round(ms), "detail": note})
    results.sort(key=lambda r: (not r["ok"], r["ms"]))
    return results


def save_result(results):
    """把检测结果写进设置（只记住最优的那个）。"""
    best = next((r for r in results if r["ok"]), None)
    config.set_setting("server_best", best["id"] if best else "")
    config.set_setting("server_latency", best["ms"] if best else 0)
    return best


# ---------------------------------------------------------------- 选用
def current_profile():
    """当前实际使用的接入点。"""
    mode = config.get_setting("server_profile", "auto") or "auto"
    if mode != "auto":
        p = by_id(mode)
        if p:
            return p
    p = by_id(config.get_setting("server_best", "") or "")
    return p or by_id(DEFAULT_ID)


def current_endpoint():
    """当前使用的接口地址（给 lcsc.py 用）。"""
    return current_profile()["endpoint"]


def is_auto():
    return (config.get_setting("server_profile", "auto") or "auto") == "auto"


def summary():
    """给设置界面显示的一行状态文字。"""
    p = current_profile()
    ms = config.get_setting("server_latency", 0) or 0
    if is_auto():
        if ms:
            return f"{p['name']}　{ms} ms"
        return p["name"]
    return f"{p['name']}"
