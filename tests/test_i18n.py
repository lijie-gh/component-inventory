# -*- coding: utf-8 -*-
"""多语言 / 汇率 / 接入点 自检（全部用临时目录，不碰真实数据）。"""
import os
import sys
import tempfile

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

TMP = tempfile.mkdtemp(prefix="i18ntest_")
from core import config                                    # noqa: E402
config.DATA_DIR = TMP
config.DB_PATH = os.path.join(TMP, "inventory.db")
config.SETTINGS_PATH = os.path.join(TMP, "settings.json")
config.BACKUP_DIR = os.path.join(TMP, "backup")
config.EXPORT_DIR = os.path.join(TMP, "导出")

from core import fx, lang, lang_en, servers                 # noqa: E402

PASS = FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [OK ] {name}" + (f"  → {extra}" if extra else ""))
    else:
        FAIL += 1
        print(f"  [!! ] {name}" + (f"  → {extra}" if extra else ""))


print("=== 1. 语言基础 ===")
check("默认是中文", lang.current() == "zh")
check("中文下 T() 原样返回", lang.T("添加元件") == "添加元件")
check("语言列表含中英", [c for c, _n in lang.available()] == ["zh", "en"])

lang.set_language("en")
lang.reset_cache()
check("切到英文生效", lang.current() == "en")
check("文案被翻译", lang.T("添加元件") == "Add part", lang.T("添加元件"))
check("词库外的文案回退中文", lang.T("这句没翻译过") == "这句没翻译过")
check("大小写/别名容错", lang.normalize("EN_us") == "en" and lang.normalize("zh-CN") == "zh")
check("不认识的语言回退中文", lang.normalize("xx") == "zh")

print("\n=== 2. 占位符 ===")
check("{0} 位置参数", lang.T("共 {0} 种元件", 5) == "5 part types",
      lang.T("共 {0} 种元件", 5))
check("格式说明符 {1:.0f}",
      lang.T("当前缓存 {0} 条（约 {1:.0f} KB）。\n", 3, 2.5)
      == "Cache holds 3 entries (~2 KB).\n")
check("参数不足不抛异常", isinstance(lang.T("共 {0} 种元件"), str))
check("文案里有裸花括号也不炸", isinstance(lang.T("界面文案会立即切换；分类名、库位名属于数据，保持原样"), str))

print("\n=== 3. 词典覆盖率 ===")
sys.path.insert(0, os.path.join(PROJ, "tools"))
import extract_ui_strings as E                            # noqa: E402
need, missing = set(), []
for items in E.collect().values():
    for it in items:
        if not E._ignored(it["key"]):
            need.add(it["key"])
for k in need:
    if k not in lang_en.TABLE:
        missing.append(k)
check(f"界面文案 {len(need)} 条全部有译文", not missing,
      f"缺失 {len(missing)}" + ("：" + "、".join(missing[:3]) if missing else ""))

print("\n=== 4. 汇率 ===")
try:
    rate, src = fx.fetch_rate()
    check("取到实时汇率", rate > 0, f"1 USD = {rate}（{src}）")
except Exception as e:
    check("取到实时汇率", False, str(e))
lang.set_language("zh")
lang.reset_cache()
check("状态文案可用", isinstance(fx.status_text(), str), fx.status_text())
check("should_auto_update 正常", isinstance(fx.should_auto_update(12), bool))

print("\n=== 5. 接入点检测 ===")
results = servers.detect(timeout=6)
check("返回全部接入点", len(results) == len(servers.PROFILES), f"{len(results)} 个")
check("可用的排在前面",
      results == sorted(results, key=lambda r: (not r["ok"], r["ms"])))
for r in results:
    print(f"       {'可用 ' if r['ok'] else '不可用'} {r['name']}  {r['ms']}ms  {r['detail']}")
usable = [r for r in results if r["ok"]]
check("至少有一个可用接入点", bool(usable))
best = servers.save_result(results)
check("选出最优接入点", best is not None, best["name"] if best else "无")
if best:
    check("接口地址跟随最优接入点",
          servers.current_endpoint() == best["endpoint"])
check("手动指定接入点也生效",
      (lambda: (config.set_setting("server_profile", "jlcpcb"),
                servers.current_profile()["id"] == "jlcpcb",
                config.set_setting("server_profile", "auto"))[-2])())

print("\n=== 6. 中文界面（GUI 冒烟）===")
lang.set_language("zh")
lang.reset_cache()
import tkinter as tk                                       # noqa: E402
from ui.main_window import MainWindow                      # noqa: E402


def menu_labels(win):
    """取出所有菜单项文字（分隔线没有 label，跳过）。"""
    m = win.nametowidget(win["menu"])
    out = []
    for i in range(m.index("end") + 1):
        try:
            out.append(m.entrycget(i, "label"))
        except Exception:
            pass
    return out


app = MainWindow()
app.withdraw()
app.update()
labels_zh = menu_labels(app)
check("中文菜单", "文件" in labels_zh and "设置" in labels_zh, str(labels_zh))
check("中文表头", app.tv.heading("model")["text"] == "型号",
      app.tv.heading("model")["text"])
app.destroy()

print("\n=== 7. 英文界面（GUI 冒烟）===")
lang.set_language("en")
lang.reset_cache()
app2 = MainWindow()
app2.withdraw()
app2.update()
labels_en = menu_labels(app2)
check("英文菜单", "File" in labels_en and "Settings" in labels_en, str(labels_en))
check("英文表头", app2.tv.heading("model")["text"] == "Model",
      app2.tv.heading("model")["text"])
check("英文表头(封装)", app2.tv.heading("package")["text"] == "Package",
      app2.tv.heading("package")["text"])
check("窗口标题带版本", "v" in app2.title())
app2.destroy()

lang.set_language("zh")
lang.reset_cache()

print()
print(f"通过 {PASS} 项，失败 {FAIL} 项")
sys.exit(0 if FAIL == 0 else 1)
