# -*- coding: utf-8 -*-
"""导出 CSV → 再导入：确认改了表头后仍能识别（回归检查）。"""
import os, sys, tempfile
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)
from core import config
TMP = tempfile.mkdtemp(prefix="invrt_")
config.DATA_DIR = TMP
config.DB_PATH = os.path.join(TMP, "inventory.db")
config.EXPORT_DIR = os.path.join(TMP, "导出")
config.BACKUP_DIR = os.path.join(TMP, "backup")
config.SETTINGS_PATH = os.path.join(TMP, "settings.json")
os.makedirs(config.EXPORT_DIR, exist_ok=True)
from core import io_utils, pricing, service, db

TIERS = pricing.tiers_to_text([[1, 999, 0.13536], [500, -1, 0.10512]])
service.add_manual({"name": "贴片电阻 10kΩ", "model": "0603-10K",
                    "ref_price": 0.1354, "price_tiers": TIERS,
                    "supplier": "淘宝"}, quantity=600, location="默认库位")

rows = db.list_parts()
path = io_utils.export_csv(rows, os.path.join(config.EXPORT_DIR, "t.csv"))
print("导出文件:", path)
with open(path, encoding="utf-8-sig") as f:
    print("表头:", f.readline().strip())

items, meta = io_utils.read_table_file(path)
print("识别到的列映射:", {v: k for k, v in (meta.get("mapping") or {}).items()})
m = meta.get("mapping") or {}
ok_price = "ref_price" in m.values()
ok_qty = "total_qty" in m.values()
print("单价列可识别:", ok_price)
print("数量列可识别:", ok_qty)
print("读回第一行:", items[0] if items else None)
ok = bool(ok_price and ok_qty and items)
print()
print("结果:", "往返正常" if ok else "往返异常")
import shutil
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0 if ok else 1)
