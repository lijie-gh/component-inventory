# -*- coding: utf-8 -*-
"""汇率自动获取。

数据源（都是公开接口，不需要 API key）：

1. ``open.er-api.com``    —— 160+ 币种，每天更新，无需注册
2. ``api.frankfurter.app`` —— 欧洲央行数据，币种较少但很稳，作为备用

取到的汇率会写进设置里的 ``usd_rate``。程序内部**只认这一个值**，
所以断网时照常用上次的汇率，不会因为取不到汇率就罢工。
"""
import json
import ssl
import time
import urllib.request

from . import config

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 大部分家用 Windows 的根证书是齐的，但个别环境证书链不全，
# 这里在失败后允许降级重试一次，避免用户只看到"取不到汇率"。
ENDPOINTS = [
    ("open.er-api.com", "https://open.er-api.com/v6/latest/USD", "open.er-api.com"),
    ("frankfurter.app", "https://api.frankfurter.app/latest?from=USD&to=CNY",
     "European Central Bank"),
]


class FxError(Exception):
    """取汇率失败。"""


def _get_json(url, timeout, verify=True):
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def fetch_rate(currency="CNY", timeout=8):
    """取 1 USD = ? <currency>。

    返回 ``(汇率, 数据源名)``；全部数据源都失败时抛 ``FxError``。
    """
    target = (currency or "CNY").upper()
    errors = []
    for _key, url, src in ENDPOINTS:
        for verify in (True, False):      # 证书链不全时降级重试
            try:
                data = _get_json(url, timeout, verify)
                rates = data.get("rates") or {}
                val = rates.get(target)
                if val:
                    return float(val), src
                errors.append(f"{src}: 返回里没有 {target}")
                break
            except Exception as e:
                last = e
                if verify:
                    continue              # 再试一次不校验证书
                errors.append(f"{src}: {type(e).__name__}")
    raise FxError("；".join(errors) or "未知错误")


def update_rate(currency="CNY", timeout=8):
    """取汇率并写入设置，返回 ``(汇率, 数据源)``。"""
    rate, src = fetch_rate(currency, timeout)
    if rate <= 0:
        raise FxError("取到的汇率不合法")
    rate = round(rate, 4)
    config.set_setting("usd_rate", rate)
    config.set_setting("fx_source", src)
    config.set_setting("fx_updated_at", config.now_str())
    return rate, src


def current_rate():
    """当前使用的汇率（设置里的值，取不到就回退默认值）。"""
    try:
        return float(config.get_setting("usd_rate", 7.2) or 7.2)
    except (TypeError, ValueError):
        return 7.2


def status_text():
    """给设置界面用的一句话说明。"""
    from .lang import T
    rate = current_rate()
    src = config.get_setting("fx_source", "") or ""
    when = config.get_setting("fx_updated_at", "") or ""
    if not when:
        return T("尚未自动获取过（当前用 {0}）", rate)
    return T("当前 {0}　来源 {1}　更新于 {2}", rate, src or "—", when)


def should_auto_update(max_age_hours=12):
    """距离上次更新是否已超过给定小时数。"""
    when = config.get_setting("fx_updated_at", "") or ""
    if not when:
        return True
    try:
        t = time.mktime(time.strptime(when, "%Y-%m-%d %H:%M:%S"))
    except Exception:
        return True
    return (time.time() - t) > max_age_hours * 3600
