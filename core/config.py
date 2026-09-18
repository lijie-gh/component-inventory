# -*- coding: utf-8 -*-
"""全局配置：路径、常量、默认设置。

所有路径均基于本文件位置自动推导，整个程序可以随意搬动目录。
"""
import os
import sys
import json
import datetime

APP_NAME = "元件库存管理"
VERSION = "1.0.0"


def _frozen():
    """是否运行在打包后的 exe 里。"""
    return bool(getattr(sys, "frozen", False))


def _base_dir():
    """程序基目录：数据、导出、备份都相对它存放。

    源码运行时是项目根目录；打包成单文件 exe 后，``__file__`` 指向的是
    解压出来的临时目录（每次启动都变、退出即删），若仍按它推导，用户
    的数据库会被写进临时目录、一关程序就丢。所以 exe 模式下改用
    **exe 自身所在目录**，这样数据能留住，也能整个文件夹拷走。
    """
    if _frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(*parts):
    """取打包进去的只读资源（图标等）的真实路径。

    单文件 exe 会把资源释放到 ``sys._MEIPASS``，源码运行时则在项目根目录。
    """
    base = getattr(sys, "_MEIPASS", None) or BASE_DIR
    return os.path.join(base, *parts)


def _layout(base):
    return {
        "BASE_DIR": base,
        "DATA_DIR": os.path.join(base, "data"),
        "DB_PATH": os.path.join(base, "data", "inventory.db"),
        "EXPORT_DIR": os.path.join(base, "导出"),
        "BACKUP_DIR": os.path.join(base, "data", "backup"),
        "SETTINGS_PATH": os.path.join(base, "data", "settings.json"),
    }


def _init_dirs(base):
    """按 base 算出各路径并建好目录；目录建不出来时返回 None。"""
    paths = _layout(base)
    try:
        for key in ("DATA_DIR", "EXPORT_DIR", "BACKUP_DIR"):
            os.makedirs(paths[key], exist_ok=True)
    except OSError:
        return None
    return paths


BASE_DIR = _base_dir()
_paths = _init_dirs(BASE_DIR)
if _paths is None:
    # exe 被放在只读位置（Program Files、写保护的U盘等）时，退到用户目录，
    # 至少保证程序能启动、数据不丢。
    _fallback = os.path.join(
        os.environ.get("APPDATA") or os.path.expanduser("~"), APP_NAME)
    _paths = _init_dirs(_fallback) or _layout(_fallback)

BASE_DIR = _paths["BASE_DIR"]
DATA_DIR = _paths["DATA_DIR"]
DB_PATH = _paths["DB_PATH"]
EXPORT_DIR = _paths["EXPORT_DIR"]
BACKUP_DIR = _paths["BACKUP_DIR"]
SETTINGS_PATH = _paths["SETTINGS_PATH"]

# ---------------- 嘉立创商城接口 ----------------
# 嘉立创 SMT 元件库公开查询接口，支持按 C 号 / 型号 / 名称 检索
LCSC_ENDPOINT = (
    "https://jlcpcb.com/api/overseas-pcb-order/v1/"
    "shoppingCart/smtGood/selectSmtComponentList"
)
# 商品详情页（国内站），C 号可直接拼出可读链接
LCSC_ITEM_URL = "https://item.szlcsc.com/search?k={code}"
LCSC_SEARCH_URL = "https://so.szlcsc.com/global.html?k={code}"
REQUEST_TIMEOUT = 15
CACHE_TTL_DAYS = 7          # 商城数据缓存有效期（天）

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# ---------------- 业务枚举 ----------------
SOURCE_LCSC = "lcsc"        # 嘉立创商城采购
SOURCE_OTHER = "other"      # 其它渠道采购（非嘉立创）

SOURCE_LABEL = {
    SOURCE_LCSC: "嘉立创",
    SOURCE_OTHER: "其它渠道",
}

TXN_IN = "IN"               # 入库
TXN_OUT = "OUT"             # 出库
TXN_ADJUST = "ADJUST"       # 盘点调整
TXN_LABEL = {
    TXN_IN: "入库",
    TXN_OUT: "出库",
    TXN_ADJUST: "盘点",
}

DEFAULT_LOCATION = "默认库位"

# 常用元件分类（下拉可编辑）
CATEGORIES = [
    "电阻", "电容", "电感", "磁珠", "二极管", "三极管", "MOS管",
    "晶振", "LED", "连接器", "开关", "继电器", "保险丝",
    "电源芯片", "运放", "比较器", "逻辑芯片", "MCU", "存储器",
    "接口芯片", "传感器", "光耦", "模块", "结构件", "线材", "其它",
]

# ---------------- 默认设置 ----------------
DEFAULT_SETTINGS = {
    "low_stock_threshold": 10,      # 全局低库存预警阈值（当元件未单独设置时生效）
    "operator": "",                 # 默认操作人
    "auto_fetch_on_add": True,      # 输入 C 号时自动联网查询
    "usd_rate": 7.2,                # 美元→人民币汇率（离线兜底值，联网后会被实际汇率覆盖）
    "confirm_delete": True,         # 删除元件前二次确认
    "allow_negative_out": False,    # 出库超过库存时是拒绝，还是记成负库存（先出后补）
    "language": "zh",               # 界面语言：zh / en
    "auto_update_fx": True,         # 启动时自动更新汇率
    "fx_updated_at": "",            # 汇率最后更新时间
    "fx_source": "",                # 汇率来源说明
    "server_profile": "auto",       # 商城接入点：auto 表示自动测速挑选
    "server_best": "",              # 上次自动检测选出的接入点
    "server_latency": 0,            # 该接入点的实测延迟（毫秒）
}


def _load_settings():
    cfg = dict(DEFAULT_SETTINGS)
    try:
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_settings(cfg):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def get_setting(key, default=None):
    return _load_settings().get(key, DEFAULT_SETTINGS.get(key, default))


def set_setting(key, value):
    cfg = _load_settings()
    cfg[key] = value
    return save_settings(cfg)


def reset_settings():
    """恢复出厂默认设置（不影响元件与库存数据）。"""
    return save_settings(dict(DEFAULT_SETTINGS))


def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str():
    return datetime.datetime.now().strftime("%Y-%m-%d")
