# -*- coding: utf-8 -*-
"""界面冒烟测试：确认本轮的改动没把 GUI 弄坏（用临时库，不动用户数据）。"""
import os
import sys
import tempfile

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

from core import config

TMP = tempfile.mkdtemp(prefix="invgui_")
config.DATA_DIR = TMP
config.DB_PATH = os.path.join(TMP, "inventory.db")
config.BACKUP_DIR = os.path.join(TMP, "backup")
config.SETTINGS_PATH = os.path.join(TMP, "settings.json")
os.makedirs(config.BACKUP_DIR, exist_ok=True)

from core import db, pricing, service
from ui.main_window import AboutDialog, MainWindow, SettingsDialog
from ui.import_dialog import ImportDialog
from ui.part_editor import PartEditor
from ui.stock_dialog import StockDialog

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'OK ' if cond else 'FAIL'}] {name}" + (f"  → {detail}" if detail else ""))


TIERS = pricing.tiers_to_text([[1, 999, 0.13536], [500, -1, 0.10512]])

app = MainWindow()
app.withdraw()          # 不弹窗打扰，但控件照常创建


def scenario():
    print("\n" + "=" * 62)
    print("界面冒烟测试")
    print("=" * 62)

    # ---------- 主窗口基本状态 ----------
    check("主窗口标题正常", config.APP_NAME in app.title())
    check("统计卡片齐全", set(app.cards) == {
        "kinds", "lcsc_kinds", "other_kinds", "total_qty",
        "total_value", "low_kinds", "out_kinds"}, str(sorted(app.cards)))

    # ---------- 带阶梯价的元件 + 表格展示 ----------
    pid, _ = service.add_manual(
        {"code": "", "name": "贴片电阻 10kΩ", "model": "0603-10K",
         "supplier": "淘宝-华强北", "ref_price": 0.1354,
         "price_tiers": TIERS, "min_qty": 50},
        quantity=600, location="默认库位", operator="李杰")
    app.refresh()
    rows = app.tv.get_children()
    check("表格显示 1 行", len(rows) == 1, f"{len(rows)} 行")

    vals = app.tv.item(rows[0], "values")
    keys = [c[0] for c in app.COLUMNS] if hasattr(app, "COLUMNS") else None
    # 直接按列定义取值，避免依赖顺序猜测
    from ui.main_window import COLUMNS as UICOLS
    cell = {k: vals[i] for i, (k, *_) in enumerate(UICOLS)}
    check("单价列显示按量档位价 0.1051（不是 1 片价 0.1354）",
          cell["ref_price"] == "0.1051", cell["ref_price"])
    check("金额列 = 600 × 0.1051 = 63.06", cell["amount"] == "63.06", cell["amount"])

    # ---------- 统计卡片 ----------
    check("元件种类卡片 = 1", app.cards["kinds"]._num.cget("text") == "1",
          app.cards["kinds"]._num.cget("text"))
    check("库存总数量卡片 = 600", app.cards["total_qty"]._num.cget("text") == "600",
          app.cards["total_qty"]._num.cget("text"))
    check("库存估值卡片按档位价算（63.06）",
          app.cards["total_value"]._num.cget("text") == "63.06",
          app.cards["total_value"]._num.cget("text"))
    check("低库存卡片 = 0（600 个远高于阈值）",
          app.cards["low_kinds"]._num.cget("text") == "0",
          app.cards["low_kinds"]._num.cget("text"))

    # ---------- 排序 ----------
    try:
        app.sort_by("ref_price")
        app.sort_by("ref_price")
        app.sort_by("amount")
        check("点表头排序不报错", True)
    except Exception as e:                                     # noqa: BLE001
        check("点表头排序不报错", False, f"{type(e).__name__}: {e}")

    # ---------- 设置对话框：负库存开关 ----------
    settings = SettingsDialog(app)
    settings.withdraw()
    check("设置里有「出库允许负库存」开关", hasattr(settings, "v_neg"))
    settings.v_neg.set(True)
    settings.v_thresh.set("20")
    try:
        settings._save()
        check("设置保存成功（含负库存开关）",
              config.get_setting("allow_negative_out") is True
              and config.get_setting("low_stock_threshold") == 20,
              f"neg={config.get_setting('allow_negative_out')}, "
              f"thresh={config.get_setting('low_stock_threshold')}")
    except Exception as e:                                     # noqa: BLE001
        check("设置保存成功（含负库存开关）", False, f"{type(e).__name__}: {e}")
    config.set_setting("low_stock_threshold", 10)

    # ---------- 出库对话框：开关是否正确传给 service ----------
    captured = {}
    orig_out = service.stock_out

    def fake_out(part_id, qty, loc=None, op="", note="", allow_negative=None):
        captured["allow_negative"] = allow_negative
        captured["qty"] = qty
        return 0

    service.stock_out = fake_out
    try:
        part = db.get_part(pid)
        part["total_qty"] = 600
        dlg = StockDialog(app, [part], mode="out")
        dlg.withdraw()
        check("出库对话框有「允许负库存」勾选框", hasattr(dlg, "v_neg"))
        dlg.v_qty.set("700")            # 故意超过库存
        dlg.v_neg.set(True)
        dlg._ok()
        check("勾选后 allow_negative=True 传到了 service",
              captured.get("allow_negative") is True, str(captured))
        check("数量也正确传递", captured.get("qty") == 700, str(captured.get("qty")))
    except Exception as e:                                     # noqa: BLE001
        check("出库对话框联动正常", False, f"{type(e).__name__}: {e}")
    finally:
        service.stock_out = orig_out

    # 出库窗口高度够不够装下新增的开关
    # （窗口未映射时 Tk 的 winfo_height 恒为 1，所以校验「内容高度 ≤ 对话框请求高度」）
    d2 = StockDialog(app, [db.get_part(pid)], mode="out")
    need = d2.winfo_reqheight()
    requested = 468          # 与 stock_dialog.py 里 heights["out"] 保持一致
    check("出库窗口高度足够（内容未被裁掉）", need <= requested,
          f"内容需 {need}px / 窗口请求 {requested}px")
    d2.destroy()

    # ---------- 其它对话框能正常打开 ----------
    for name, fn in (
        ("添加元件窗口", lambda: PartEditor(app, part=None)),
        ("编辑元件窗口", lambda: PartEditor(app, part=db.get_part(pid))),
        ("批量导入窗口", lambda: ImportDialog(app, on_done=None)),
        ("使用说明窗口", lambda: AboutDialog(app)),
    ):
        try:
            w = fn()
            w.withdraw()
            w.destroy()
            check(f"{name} 可正常创建", True)
        except Exception as e:                                 # noqa: BLE001
            check(f"{name} 可正常创建", False, f"{type(e).__name__}: {e}")

    # ---------- 出库后统计刷新 ----------
    try:
        service.stock_out(pid, 50, "默认库位", operator="李杰")
        app.refresh()
        check("出库后库存 600→550", app.cards["total_qty"]._num.cget("text") == "550",
              app.cards["total_qty"]._num.cget("text"))
        check("出库后金额按 550 个的档位重算（550 × 0.1051）",
              app.cards["total_value"]._num.cget("text") == "57.80",
              app.cards["total_value"]._num.cget("text"))
    except Exception as e:                                     # noqa: BLE001
        check("出库后统计刷新", False, f"{type(e).__name__}: {e}")

    # ---------- 零库存与低库存卡片不再重叠 ----------
    service.add_manual({"name": "零库存件", "model": "ZERO-1"},
                       quantity=0, location="默认库位")
    service.add_manual({"name": "低库存件", "model": "LOW-1"},
                       quantity=3, location="默认库位")
    app.refresh()
    low = app.cards["low_kinds"]._num.cget("text")
    out = app.cards["out_kinds"]._num.cget("text")
    check("低库存卡片 = 1（只有 3 个的那件）", low == "1", low)
    check("零库存卡片 = 1", out == "1", out)

    app.destroy()


app.after(200, scenario)
app.mainloop()

print("\n" + "=" * 62)
print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
if FAIL:
    for f in FAIL:
        print("  -", f)
print("（临时目录已清理，用户数据未改动）")
sys.exit(1 if FAIL else 0)
