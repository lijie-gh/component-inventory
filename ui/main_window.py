# -*- coding: utf-8 -*-
"""主窗口：库存总览、搜索筛选、出入库入口、导入导出。"""
import os
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core import (config, db, fx, lang, lcsc, pricing, servers, service,
                  io_utils)
from . import widgets as W
from .part_editor import PartEditor
from .stock_dialog import StockDialog
from .import_dialog import ImportDialog
from core.lang import T

# 列定义：标题存中文原文，显示时才经 T() 翻译。
# （模块级常量在 import 时求值，若这里就调用 T()，切换语言后不会刷新。）
COLUMNS = [
    ("code", "C号", 80, "w"),
    ("source_label", "来源", 68, "center"),
    ("model", "型号", 130, "w"),
    ("name", "名称 / 描述", 175, "w"),
    ("brand", "厂商", 110, "w"),
    ("package", "封装", 74, "w"),
    ("category", "分类", 62, "w"),
    ("value", "参数值", 100, "w"),
    ("total_qty", "库存", 58, "e"),
    ("locations", "库位明细", 110, "w"),
    ("status", "状态", 52, "center"),
    ("ref_price", "参考单价(按量)", 92, "e"),
    ("amount", "库存金额", 72, "e"),
    ("remark", "备注", 100, "w"),
]

# 表格一次最多渲染多少行。
# Treeview 插入 3000 行实测要 1.8 秒，而搜索框是边打字边刷新的 ——
# 不做上限的话，库一变大打字就像死机（实测 3000 件时敲一个字卡 1.9 秒）。
# 超出部分数据仍在库里，缩小筛选范围就能看到。
MAX_ROWS = 500

# 需要按数值排序的列：降序用「键取负 + 不反转」表达（见 sort_by）
_NUMERIC_COLUMNS = ("total_qty", "ref_price", "amount")


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{config.APP_NAME} v{config.VERSION}　—　{config.BASE_DIR}")
        self.configure(bg=W.C_BG)
        self.geometry("1380x780")
        self.minsize(1040, 620)
        self._set_icon()
        W.setup_style(self)

        self.rows = []              # 当前显示的元件（dict 列表）
        self._search_job = None
        self.sort_key = None
        self.sort_desc = False

        self._build_menu()
        self._build_toolbar()
        self._build_stats()
        self._build_table()
        self._build_detail()
        self._build_status()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Control-n>", lambda e: self.add_part())
        self.bind("<Control-f>", lambda e: self.entry_kw.focus_set())
        self.bind("<Control-comma>", lambda e: self.open_settings())
        self.bind("<F5>", lambda e: self.refresh())
        self.bind("<Delete>", lambda e: self.delete_selected())

        W.center_window(self, 1380, 780)
        self.refresh()
        self.after(300, self._welcome)
        self.after(1500, self._startup_tasks)

    def _set_icon(self):
        """设置窗口与任务栏图标。

        打包成 exe 后图标会随资源释放到临时目录，用 resource_path 定位；
        图标缺失时静默跳过，不影响使用。
        """
        try:
            ico = config.resource_path("assets", "app.ico")
            if os.path.exists(ico):
                self.iconbitmap(default=ico)
        except Exception:
            pass

    def reload_ui(self):
        """语言切换后重建整个界面。

        搜索框内容和排序状态会保留；筛选条件会回到默认（控件被重建），
        但库存数据本身不受任何影响。
        """
        try:
            kw = self.entry_kw.get()
        except Exception:
            kw = ""
        state = (self.sort_key, self.sort_desc)
        for w in self.winfo_children():
            w.destroy()
        self._build_menu()
        self._build_toolbar()
        self._build_stats()
        self._build_table()
        self._build_detail()
        self._build_status()
        self.sort_key, self.sort_desc = state
        try:
            if kw:
                self.entry_kw.insert(0, kw)
        except Exception:
            pass
        self.refresh()
        try:
            W.toast(self, T("界面语言已切换"), "ok")
        except Exception:
            pass

    # =============================================================== 菜单
    def _build_menu(self):
        m = tk.Menu(self)
        self.configure(menu=m)

        fm = tk.Menu(m, tearoff=0)
        fm.add_command(label=T("添加元件"), accelerator="Ctrl+N", command=self.add_part)
        fm.add_command(label=T("批量导入（Excel / CSV / 粘贴 BOM）"),
                       command=self.batch_import)
        fm.add_separator()
        fm.add_command(label=T("导出全部清单为 CSV"), command=lambda: self.export(False))
        fm.add_command(label=T("导出当前筛选结果"), command=lambda: self.export(True))
        fm.add_command(label=T("导出出入库流水"), command=self.export_txns)
        fm.add_separator()
        fm.add_command(label=T("备份数据库"), command=self.backup)
        fm.add_separator()
        fm.add_command(label=T("退出"), command=self._on_close)
        m.add_cascade(label=T("文件"), menu=fm)

        tm = tk.Menu(m, tearoff=0)
        tm.add_command(label=T("刷新列表"), accelerator="F5", command=self.refresh)
        tm.add_command(label=T("刷新选中元件的商城资料"), command=self.refresh_lcsc_selected)
        tm.add_command(label=T("刷新全部嘉立创元件资料（批量联网）"),
                       command=self.refresh_all_lcsc)
        tm.add_separator()
        tm.add_command(label=T("清空商城数据缓存"), command=self.clear_cache)
        m.add_cascade(label=T("工具"), menu=tm)

        # ---- 设置（顶部独立菜单）----
        self.v_set_autofetch = tk.BooleanVar(
            value=bool(config.get_setting("auto_fetch_on_add", True)))
        self.v_set_confirm = tk.BooleanVar(
            value=bool(config.get_setting("confirm_delete", True)))
        sm = tk.Menu(m, tearoff=0)
        sm.add_command(label=T("常规设置…"), accelerator="Ctrl+,",
                       command=self.open_settings)
        sm.add_separator()
        sm.add_checkbutton(label=T("添加元件时自动查询商城资料"),
                           variable=self.v_set_autofetch,
                           command=self._toggle_setting)
        sm.add_checkbutton(label=T("删除元件前二次确认"),
                           variable=self.v_set_confirm,
                           command=self._toggle_setting)
        sm.add_separator()
        sm.add_command(label=T("清空商城数据缓存"), command=self.clear_cache)
        sm.add_command(label=T("打开数据目录"), command=self.open_data_dir)
        sm.add_separator()
        sm.add_command(label=T("恢复默认设置…"), command=self.reset_settings)
        m.add_cascade(label=T("设置"), menu=sm)

        flm = tk.Menu(m, tearoff=0)
        flm.add_command(label=T("仅显示嘉立创元件"), command=lambda: self._set_filter("lcsc"))
        flm.add_command(label=T("仅显示其它渠道元件"), command=lambda: self._set_filter("other"))
        flm.add_command(label=T("显示低库存预警"), command=lambda: self._set_filter("low"))
        flm.add_command(label=T("显示零库存元件"), command=lambda: self._set_filter("out"))
        flm.add_command(label=T("显示全部"), command=lambda: self._set_filter("all"))
        flm.add_separator()
        flm.add_command(label=T("清除所有筛选条件"), command=self.clear_filters)
        m.add_cascade(label=T("筛选"), menu=flm)

        hm = tk.Menu(m, tearoff=0)
        hm.add_command(label=T("出入库流水记录"), command=self.show_txns)
        hm.add_separator()
        hm.add_command(label=T("使用说明 / 关于"), command=self.show_about)
        m.add_cascade(label=T("帮助"), menu=hm)

    def _toggle_setting(self):
        """顶部「设置」菜单里的勾选项。"""
        config.set_setting("auto_fetch_on_add", bool(self.v_set_autofetch.get()))
        config.set_setting("confirm_delete", bool(self.v_set_confirm.get()))

    def reset_settings(self):
        if not messagebox.askyesno(
                T("恢复默认设置"),
                T("将把阈值、操作人、汇率、勾选项全部恢复成出厂默认值。\n"
                "元件资料与库存数据不受影响。是否继续？"), parent=self):
            return
        config.reset_settings()
        self.v_set_autofetch.set(bool(config.get_setting("auto_fetch_on_add", True)))
        self.v_set_confirm.set(bool(config.get_setting("confirm_delete", True)))
        self.refresh()
        W.toast(self, T("设置已恢复默认值"), "ok")

    # =============================================================== 工具栏
    def _build_toolbar(self):
        bar = tk.Frame(self, bg=W.C_BG)
        bar.pack(fill="x", padx=12, pady=(10, 6))

        # 搜索
        box = tk.Frame(bar, bg=W.C_CARD, highlightthickness=1,
                       highlightbackground=W.C_BORDER)
        box.pack(side="left")
        tk.Label(box, text="🔍", bg=W.C_CARD, fg=W.C_SUBTEXT).pack(side="left",
                                                                  padx=(8, 2))
        self.v_kw = tk.StringVar()
        self.entry_kw = ttk.Entry(box, textvariable=self.v_kw, width=34, font=W.FONT_UI)
        self.entry_kw.pack(side="left", padx=(0, 8), pady=4)
        self.entry_kw.bind("<KeyRelease>", self._on_search_key)

        # 筛选
        def combo(label, values, var, width=12):
            tk.Label(bar, text=label, bg=W.C_BG, fg=W.C_SUBTEXT,
                     font=W.FONT_UI).pack(side="left", padx=(12, 4))
            cb = ttk.Combobox(bar, textvariable=var, values=values, width=width,
                              state="readonly", font=W.FONT_UI)
            cb.pack(side="left")
            cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())
            return cb

        self.v_source = tk.StringVar(value=T("全部"))
        self.v_stock = tk.StringVar(value=T("全部"))
        self.v_category = tk.StringVar(value=T("全部分类"))
        combo(T("来源"), [T("全部"), T("仅嘉立创"), T("仅其它渠道")], self.v_source)
        combo(T("库存"), [T("全部"), T("有库存"), T("零库存"), T("低库存预警")], self.v_stock, 11)
        self.cb_cat = combo(T("分类"), [T("全部分类")], self.v_category, 12)

        W.make_button(bar, T("清除筛选"), self.clear_filters).pack(side="left", padx=(10, 0))

        # 右侧操作
        right = tk.Frame(bar, bg=W.C_BG)
        right.pack(side="right")
        W.make_button(right, T("＋ 添加元件"), self.add_part, "primary").pack(side="left")
        W.make_button(right, T("批量导入"), self.batch_import).pack(side="left", padx=6)
        W.make_button(right, T("导出 CSV"), lambda: self.export(True)).pack(side="left")
        W.make_button(right, T("⚙ 设置"), self.open_settings).pack(side="left", padx=(6, 0))

    # =============================================================== 统计
    def _build_stats(self):
        wrap = tk.Frame(self, bg=W.C_BG)
        wrap.pack(fill="x", padx=12, pady=(0, 8))
        self.cards = {}
        specs = [
            ("kinds", T("元件种类"), W.C_PRIMARY),
            ("lcsc_kinds", T("嘉立创件"), W.C_PRIMARY),
            ("other_kinds", T("其它渠道件"), "#9a6b00"),
            ("total_qty", T("库存总数量"), W.C_GREEN),
            ("total_value", T("库存估值(¥)"), W.C_GREEN),
            ("low_kinds", T("低库存预警"), W.C_ORANGE),
            ("out_kinds", T("零库存"), W.C_RED),
        ]
        for key, label, color in specs:
            c = W.StatCard(wrap, label, "0", color)
            c.pack(side="left", padx=(0, 8))
            self.cards[key] = c

    # =============================================================== 表格
    def _build_table(self):
        wrap = tk.Frame(self, bg=W.C_CARD, highlightthickness=1,
                        highlightbackground=W.C_BORDER)
        wrap.pack(fill="both", expand=True, padx=12)

        self.tv = ttk.Treeview(wrap, columns=[c[0] for c in COLUMNS],
                               show="headings", selectmode="extended")
        for key, title, width, anchor in COLUMNS:
            self.tv.heading(key, text=T(title),
                            command=lambda k=key: self.sort_by(k))
            self.tv.column(key, width=width, anchor=anchor,
                           stretch=(key in ("name", "value", "remark")))

        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.tv.yview)
        hs = ttk.Scrollbar(wrap, orient="horizontal", command=self.tv.xview)
        self.tv.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)

        self.tv.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        # 颜色标记：低库存 / 零库存
        self.tv.tag_configure("low", foreground=W.C_ORANGE)
        self.tv.tag_configure("out", foreground=W.C_RED)
        self.tv.tag_configure("odd", background=W.C_STRIPE)

        self.tv.bind("<Double-1>", lambda e: self.edit_selected())
        self.tv.bind("<Button-3>", self._popup_menu)
        self.tv.bind("<<TreeviewSelect>>", lambda e: self._show_detail())

        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label=T("编辑元件"), command=self.edit_selected)
        self.menu.add_command(label=T("从嘉立创商城刷新资料"),
                              command=self.refresh_lcsc_selected)
        self.menu.add_separator()
        self.menu.add_command(label=T("入库"), command=lambda: self.stock_op("in"))
        self.menu.add_command(label=T("出库"), command=lambda: self.stock_op("out"))
        self.menu.add_command(label=T("盘点"), command=lambda: self.stock_op("adjust"))
        self.menu.add_command(label=T("库位调拨"), command=lambda: self.stock_op("transfer"))
        self.menu.add_separator()
        self.menu.add_command(label=T("查看该元件的出入库记录"),
                              command=self.show_part_txns)
        self.menu.add_command(label=T("打开嘉立创商品页"), command=self.open_product_page)
        self.menu.add_command(label=T("打开数据手册"), command=self.open_datasheet)
        self.menu.add_separator()
        self.menu.add_command(label=T("删除元件"), command=self.delete_selected)

        # 操作条
        op = tk.Frame(self, bg=W.C_BG)
        op.pack(fill="x", padx=12, pady=8)
        for text, mode in ((T("入库"), "in"), (T("出库"), "out"),
                           (T("盘点"), "adjust"), (T("库位调拨"), "transfer")):
            W.make_button(op, text, lambda m=mode: self.stock_op(m)).pack(
                side="left", padx=(0, 6))
        W.make_button(op, T("编辑"), self.edit_selected).pack(side="left", padx=(10, 6))
        W.make_button(op, T("刷新商城资料"), self.refresh_lcsc_selected).pack(
            side="left", padx=(0, 6))
        W.make_button(op, T("删除"), self.delete_selected, "danger").pack(side="left")

    # =============================================================== 详情
    def _build_detail(self):
        wrap = tk.Frame(self, bg="#f8fafc", highlightthickness=1,
                        highlightbackground=W.C_BORDER)
        wrap.pack(fill="x", padx=12, pady=(0, 6))
        self.lbl_detail = tk.Label(
            wrap, text=T("选中一行可查看完整信息；双击行进入编辑。"),
            bg="#f8fafc", fg=W.C_SUBTEXT, font=W.FONT_SMALL,
            anchor="w", justify="left", wraplength=1340, height=3)
        self.lbl_detail.pack(fill="x", padx=10, pady=6)

    # =============================================================== 状态栏
    def _build_status(self):
        self.status = W.StatusBar(self)
        self.status.pack(fill="x", side="bottom")

    def _welcome(self):
        # 顺手清掉过期的商城缓存（以前只增不减，会一直占着空间）
        try:
            removed = db.cache_prune()
        except Exception:                                     # noqa: BLE001
            removed = 0
        st = db.stats()
        if st["kinds"] == 0:
            self.status.set(T("数据库是空的 —— 点右上角「＋ 添加元件」，输入嘉立创 C 号即可自动"
                            "抓取资料；非嘉立创购买的元件点选「其它渠道元件」手工录入。"), "warn")
        if removed:
            self.status.set_right(T("已清理 {0} 条过期的商城缓存", removed))
        # 上一轮运行出过错的话明确提醒一句，别让用户只能靠「点了没反应」猜
        if getattr(self, "startup_error", ""):
            self.status.set(T("上次运行出现过错误，可点「帮助 → 打开运行日志」查看详情"),
                            "warn")

    def _startup_tasks(self):
        """启动后的后台任务：自动更新汇率、首次自动检测接入点。

        延迟到界面显示之后再跑，而且全在后台线程里 —— 联网慢不卡界面，
        失败了也只是沿用旧值，不影响任何本地功能。
        """
        # 汇率：超过 12 小时才联网取一次
        try:
            if config.get_setting("auto_update_fx", True) and fx.should_auto_update(12):
                W.run_async(self, fx.update_rate,
                            lambda _r: None, lambda _e: None)
        except Exception:
            pass

        # 接入点：从没检测过就先自动测一轮（之后有结果就不再自动跑）
        try:
            if not (config.get_setting("server_best", "") or ""):
                W.run_async(self, lambda: servers.detect(timeout=6),
                            servers.save_result, lambda _e: None)
        except Exception:
            pass

    # =============================================================== 数据刷新
    def _filters(self):
        return {
            "keyword": self.v_kw.get().strip(),
            "source_filter": {T("全部"): "all", T("仅嘉立创"): config.SOURCE_LCSC,
                              T("仅其它渠道"): config.SOURCE_OTHER}.get(
                self.v_source.get(), "all"),
            "stock_filter": {T("全部"): "all", T("有库存"): "in_stock",
                             T("零库存"): "out_of_stock", T("低库存预警"): "low"}.get(
                self.v_stock.get(), "all"),
            "category": "" if self.v_category.get() in ("", T("全部分类"))
            else self.v_category.get(),
        }

    def refresh(self, keep_selection=True):
        selected_ids = [self._row_id(i) for i in self._selected_indices()]
        f = self._filters()
        try:
            rows = db.list_parts(**f)
        except Exception as e:                                # noqa: BLE001
            messagebox.showerror(T("查询失败"), str(e), parent=self)
            return
        self.rows = rows
        self._fill_table(rows, selected_ids)
        # _update_stats 顺手把统计结果带回来，避免这里再 db.stats() 算一遍
        # （里面有一步会对每个元件解析一遍 JSON 阶梯价，元件多时不便宜）
        st = self._update_stats()
        self._update_category_options()

        n = len(rows)
        if n == st["kinds"]:
            text, kind = T("共 {0} 种元件", n), "ok"
        else:
            text = T("筛选出 {0} 种元件（库中共 {1} 种）", n, st['kinds'])
            kind = "info"
        if n > MAX_ROWS:
            text += T("　—　表格最多显示 {0} 行，请缩小筛选范围", MAX_ROWS)
            kind = "warn"
        self.status.set(text, kind)
        self.status.set_right(T("数据库：{0}", config.DB_PATH))

    def _row_id(self, item_id):
        """取行的内部 id —— 就是数据库主键的字符串形式。

        早先这里读的是第一列的值（C 号），而 Treeview 的 iid 是主键，
        两者永远对不上：刷新时 `exists(iid)` 恒为假，选中行就丢了
        （表现为出库一件后要重新点一次行）。
        """
        return str(item_id) if item_id else None

    def _fill_table(self, rows, reselect_ids=()):
        # 一次删完，比逐行 delete 快
        self.tv.delete(*self.tv.get_children())
        shown = rows[:MAX_ROWS] if len(rows) > MAX_ROWS else rows
        g = float(config.get_setting("low_stock_threshold", 10) or 0)
        for idx, p in enumerate(shown):
            qty = int(p.get("total_qty") or 0)
            thresh = int(p.get("min_qty") or 0) or g
            if qty <= 0:
                status, tag = T("缺货"), "out"
            elif qty <= thresh:
                status, tag = T("偏低"), "low"
            else:
                status, tag = T("充足"), ""
            row = io_utils.part_to_row(p)
            # 按 COLUMNS 定义的顺序取值；来源与状态列做特殊映射
            ordered = []
            for key, _, _, _ in COLUMNS:
                if key == "status":
                    ordered.append(status)
                elif key == "source_label":
                    ordered.append(T(
                        config.SOURCE_LABEL.get(p.get("source"), "")
                        or p.get("source") or ""))
                else:
                    ordered.append(row.get(key, ""))
            tags = [tag] if tag else []
            if idx % 2:
                tags.append("odd")
            self.tv.insert("", "end", iid=str(p["id"]), values=ordered, tags=tags)

        if reselect_ids:
            for iid in reselect_ids:
                if iid and self.tv.exists(iid):
                    self.tv.selection_add(iid)

    def _update_stats(self):
        """刷新顶部卡片，并把统计结果返回给调用方复用。"""
        st = db.stats()
        self.cards["kinds"].set(st["kinds"])
        self.cards["lcsc_kinds"].set(st["lcsc_kinds"])
        self.cards["other_kinds"].set(st["other_kinds"])
        self.cards["total_qty"].set(f"{st['total_qty']:,}")
        val = st["total_value"]
        self.cards["total_value"].set(
            f"{val:,.0f}" if val >= 1000 else f"{val:,.2f}")
        self.cards["low_kinds"].set(st["low_kinds"],
                                    W.C_ORANGE if st["low_kinds"] else W.C_SUBTEXT)
        self.cards["out_kinds"].set(st["out_kinds"],
                                    W.C_RED if st["out_kinds"] else W.C_SUBTEXT)
        return st

    def _update_category_options(self):
        cats = [T("全部分类")] + sorted(set(db.all_categories() + config.CATEGORIES))
        cur = self.v_category.get()
        self.cb_cat.configure(values=cats)
        if cur not in cats:
            self.v_category.set(T("全部分类"))

    # =============================================================== 交互
    def _on_search_key(self, event=None):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(220, self.refresh)

    def _set_filter(self, which):
        if which == "all":
            self.clear_filters()
            return
        if which in (config.SOURCE_LCSC, config.SOURCE_OTHER):
            self.v_source.set(T("仅嘉立创") if which == config.SOURCE_LCSC else T("仅其它渠道"))
            self.v_stock.set(T("全部"))
        else:
            self.v_stock.set({"low": T("低库存预警"),
                              "out": T("零库存")}.get(which, T("全部")))
            self.v_source.set(T("全部"))
        self.refresh()

    def clear_filters(self):
        self.v_kw.set("")
        self.v_source.set(T("全部"))
        self.v_stock.set(T("全部"))
        self.v_category.set(T("全部分类"))
        self.sort_key, self.sort_desc = None, False
        self.refresh()

    def sort_by(self, key):
        if self.sort_key == key:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_key, self.sort_desc = key, False

        numeric = key in _NUMERIC_COLUMNS

        def sort_val(p):
            row = io_utils.part_to_row(p)
            v = row.get(key)
            if key == "total_qty":
                try:
                    n = int(v or 0)
                except (TypeError, ValueError):
                    n = 0
                return -n if self.sort_desc else n
            if numeric:
                try:
                    x = float(v)
                except (TypeError, ValueError):
                    x = 0.0
                return -x if self.sort_desc else x
            return str(v or "")

        # 数值列的降序已经用「键取负」表达，这里就不能再 reverse 一次 ——
        # 两个取反叠在一起正好抵销，会出现「表头是 ↓、数据还是升序」的怪象。
        # 文本列没有取负这一说，只能靠 reverse。
        rows = sorted(self.rows, key=sort_val,
                      reverse=(self.sort_desc and not numeric))
        self._fill_table(rows)
        arrow = " ↓" if self.sort_desc else " ↑"
        for k, title, _, _ in COLUMNS:
            self.tv.heading(k, text=T(title) + (arrow if k == key else ""))

    def _selected_indices(self):
        return self.tv.selection()

    def selected_parts(self):
        out = []
        for iid in self.tv.selection():
            p = db.get_part(int(iid))
            if p:
                rows = db.get_stock_rows(p["id"])
                p["total_qty"] = sum(r["quantity"] for r in rows)
                p["locations"] = " / ".join(f"{r['location']}:{r['quantity']}"
                                            for r in rows)
                out.append(p)
        return out

    def _one_part(self):
        parts = self.selected_parts()
        if not parts:
            W.toast(self, T("请先在列表中选择一个元件"), "warn")
            return None
        if len(parts) > 1:
            W.toast(self, T("此操作一次只能选一个元件"), "warn")
            return None
        return parts[0]

    def _popup_menu(self, event):
        iid = self.tv.identify_row(event.y)
        if iid:
            if iid not in self.tv.selection():
                self.tv.selection_set(iid)
            self.menu.tk_popup(event.x_root, event.y_root)

    def _show_detail(self):
        p = self._one_part() if len(self.tv.selection()) == 1 else None
        if not p:
            n = len(self.tv.selection())
            self.lbl_detail.configure(
                text=(T("已选择 {0} 个元件。右键或点下方按钮可批量入库/出库/盘点。", n)
                      if n else T("选中一行可查看完整信息；双击行进入编辑。")),
                fg=W.C_SUBTEXT)
            return
        rows = db.get_stock_rows(p["id"])
        loc = "　".join(f"{r['location']}={r['quantity']}" for r in rows) or T("无")
        parts = [
            f"[{T(config.SOURCE_LABEL.get(p.get('source'),''))}]",
            p.get("code") or T("（无C号）"),
            p.get("model") or "",
            p.get("name") or "",
            T("厂商 {0}", p.get('brand') or '—'),
            T("封装 {0}", p.get('package') or '—'),
            T("分类 {0}", p.get('category') or '—'),
            T("库存 {0}", sum(r['quantity'] for r in rows)),
            T("库位 {0}", loc),
        ]
        if p.get("ref_price"):
            parts.append(T("参考单价 ¥{0:.4f}", float(p['ref_price'])))
        # 整张阶梯价（1+ ¥0.135 / 500+ ¥0.105 …），核对「买 500 个多少钱」用
        tiers = pricing.parse_tiers(p.get("price_tiers"))
        if tiers:
            parts.append(T("阶梯价 {0}", pricing.describe_tiers(tiers)))
        if p.get("datasheet"):
            parts.append(T("📄 有数据手册"))
        if p.get("last_fetch"):
            parts.append(T("商城同步 {0}", p['last_fetch']))
        if p.get("remark"):
            parts.append(T("备注 {0}", p['remark']))
        self.lbl_detail.configure(text="　|　".join(x for x in parts if x),
                                  fg=W.C_TEXT)

    # =============================================================== 操作
    def add_part(self):
        PartEditor(self, None, on_saved=self._after_change)

    def edit_selected(self):
        p = self._one_part()
        if p:
            PartEditor(self, p, on_saved=self._after_change)

    def _after_change(self, result):
        self.refresh()
        kind = result[0] if isinstance(result, tuple) else ""
        msg = {"new": T("已新建元件"), "merge": T("元件已存在，库存已追加"),
               "edit": T("已保存修改"), "delete": T("已删除")}.get(kind, "")
        if msg:
            self.status.set(msg, "ok")

    def stock_op(self, mode):
        parts = self.selected_parts()
        if not parts:
            W.toast(self, T("请先在列表中选择元件"), "warn")
            return
        StockDialog(self, parts, mode=mode, on_done=self.refresh)

    def delete_selected(self):
        parts = self.selected_parts()
        if not parts:
            return
        names = "、".join((p.get("code") or p.get("name") or str(p["id"]))
                          for p in parts[:5])
        if config.get_setting("confirm_delete", True):
            if not messagebox.askyesno(
                    T("确认删除"),
                    f"确定删除以下 {len(parts)} 个元件吗？\n\n{names}"
                    f"{' …' if len(parts) > 5 else ''}\n\n"
                    f"库存与流水会一并删除，不可撤销。\n"
                    f"（可在「设置」菜单里关闭这个二次确认）",
                    parent=self, icon="warning"):
                return
        try:
            for p in parts:
                service.delete_part(p["id"])
        except Exception as e:                                # noqa: BLE001
            messagebox.showerror(T("删除失败"), str(e), parent=self)
        self.refresh()

    def refresh_lcsc_selected(self):
        parts = [p for p in self.selected_parts() if lcsc.is_lcsc_code(p.get("code"))]
        if not parts:
            W.toast(self, T("请选择带嘉立创 C 号的元件"), "warn")
            return
        self.status.set(T("正在从嘉立创商城刷新 {0} 个元件…", len(parts)))

        def task():
            ok, fail = 0, []
            for p in parts:
                try:
                    service.refresh_from_lcsc(p["id"])
                    ok += 1
                except Exception as e:                        # noqa: BLE001
                    fail.append(f"{p.get('code')}：{e}")
            return ok, fail

        def done(res):
            ok, fail = res
            self.refresh()
            if fail:
                messagebox.showwarning(T("部分刷新失败"),
                                       T("成功 {0} 个，失败 {1} 个：\n\n", ok, len(fail))
                                       + "\n".join(fail[:8]), parent=self)
            else:
                W.toast(self, T("已刷新 {0} 个元件的商城资料", ok), "ok")

        W.run_async(self, task, done,
                    lambda e: messagebox.showerror(T("刷新失败"), str(e), parent=self))

    def refresh_all_lcsc(self):
        codes = [r["code"] for r in db.query(
            "SELECT code FROM parts WHERE source=? AND code IS NOT NULL AND code<>''",
            (config.SOURCE_LCSC,))]
        if not codes:
            W.toast(self, T("库中没有嘉立创元件"), "warn")
            return
        if not messagebox.askyesno(
                T("批量刷新"),
                f"将联网刷新 {len(codes)} 个嘉立创元件的资料（型号/厂商/价格等）。\n"
                f"元件较多时可能需要一点时间，是否继续？", parent=self):
            return
        self.status.set(T("正在刷新 0/{0} …", len(codes)))

        def task():
            return lcsc.fetch_many(
                codes,
                progress=lambda i, t, c: self.after(
                    0, lambda: self.status.set(T("正在刷新 {0}/{1} …{2}", i, t, c))))

        def done(res):
            ok = sum(1 for v in res.values() if v[0])
            fail = [(k, v[1]) for k, v in res.items() if v[1]]
            # 一次一提交在元件多时会慢很多，包进一个事务
            with db.transaction():
                for code, (data, err) in res.items():
                    if not data:
                        continue
                    p = db.get_part_by_code(code)
                    if not p:
                        continue
                    patch = {k: v for k, v in data.items()
                             if not k.startswith("_") and v not in (None, "")}
                    patch["last_fetch"] = config.now_str()
                    patch.pop("source", None)
                    db.update_part(p["id"], patch)
            self.refresh()
            self.status.set(T("刷新完成：成功 {0} 个，失败 {1} 个", ok, len(fail)),
                            "ok" if not fail else "warn")
            if fail:
                messagebox.showwarning(
                    T("部分元件刷新失败"),
                    "\n".join(f"{c}：{e}" for c, e in fail[:10]), parent=self)

        W.run_async(self, task, done,
                    lambda e: messagebox.showerror(T("刷新失败"), str(e), parent=self))

    def batch_import(self):
        ImportDialog(self, on_done=self.refresh)

    def export(self, current_only=False):
        rows = self.rows if current_only else db.list_parts()
        if not rows:
            W.toast(self, T("没有可导出的数据"), "warn")
            return
        default = (T("元件库存_筛选结果_") if current_only else T("元件库存_")) + \
                  f"{config.today_str()}.csv"
        path = filedialog.asksaveasfilename(
            title=T("导出为 CSV"), initialdir=config.EXPORT_DIR,
            initialfile=default, defaultextension=".csv",
            filetypes=[(T("CSV 文件"), "*.csv")])
        if not path:
            return
        try:
            out = io_utils.export_csv(rows, path)
        except Exception as e:                                # noqa: BLE001
            messagebox.showerror(T("导出失败"), str(e), parent=self)
            return
        if messagebox.askyesno(T("导出完成"),
                               T("已导出 {0} 条到：\n{1}\n\n是否打开所在文件夹？", len(rows), out),
                               parent=self):
            self._open_path(os.path.dirname(out))

    def export_txns(self):
        txns = db.list_txns(limit=100000)
        if not txns:
            W.toast(self, T("还没有出入库记录"), "warn")
            return
        path = io_utils.export_txns_csv(txns)
        if messagebox.askyesno(T("导出完成"),
                               T("已导出 {0} 条流水到：\n{1}\n\n是否打开所在文件夹？", len(txns), path),
                               parent=self):
            self._open_path(os.path.dirname(path))

    def backup(self):
        try:
            path = service.backup_db()
        except Exception as e:                                # noqa: BLE001
            messagebox.showerror(T("备份失败"), str(e), parent=self)
            return
        messagebox.showinfo(T("备份完成"), T("数据库已备份到：\n{0}", path), parent=self)

    def clear_cache(self):
        n, b = db.cache_size()
        if not n:
            W.toast(self, T("商城数据缓存是空的"), "warn")
            return
        if not messagebox.askyesno(
                T("清空缓存"),
                f"当前缓存 {n} 条（约 {b / 1024:.0f} KB）。\n"
                f"清空后下次查询会重新联网获取嘉立创数据。是否继续？", parent=self):
            return
        db.cache_clear()
        W.toast(self, T("商城数据缓存已清空"), "ok")

    def show_txns(self):
        TxnsWindow(self)

    def show_part_txns(self):
        """只看选中那一个元件的出入库记录（不用在全局流水里肉眼翻）。"""
        p = self._one_part()
        if not p:
            return
        TxnsWindow(self, part_id=p["id"])

    def open_app_log(self):
        """打开运行日志（出错时给用户一个能直接拿到证据的地方）。"""
        from core import applog
        path = applog.log_path()
        if not os.path.exists(path):
            W.toast(self, T("还没有日志文件"), "warn")
            return
        self._open_path(path)

    def open_product_page(self):
        p = self._one_part()
        if not p:
            return
        url = p.get("code") and lcsc.product_url(p["code"])
        if not url:
            W.toast(self, T("该元件没有嘉立创 C 号"), "warn")
            return
        webbrowser.open(url)

    def open_datasheet(self):
        p = self._one_part()
        if not p:
            return
        if not p.get("datasheet"):
            W.toast(self, T("该元件没有数据手册链接"), "warn")
            return
        webbrowser.open(p["datasheet"])

    def open_data_dir(self):
        self._open_path(config.DATA_DIR)

    def _open_path(self, path):
        try:
            if os.name == "nt":
                os.startfile(path)                            # noqa: S606
            else:
                webbrowser.open(f"file://{path}")
        except Exception as e:                                # noqa: BLE001
            messagebox.showinfo(T("提示"), T("请手动打开：{0}", path), parent=self)

    def open_settings(self):
        SettingsDialog(self, on_saved=self._after_settings)

    def _after_settings(self):
        """设置改完后同步顶部菜单的勾选项并刷新列表。"""
        try:
            self.v_set_autofetch.set(
                bool(config.get_setting("auto_fetch_on_add", True)))
            self.v_set_confirm.set(
                bool(config.get_setting("confirm_delete", True)))
        except Exception:
            pass
        self.refresh()

    def show_about(self):
        AboutDialog(self)

    def _on_close(self):
        try:
            db.close()
        except Exception:
            pass
        self.destroy()


# ==================================================================== 附属窗口
class TxnsWindow(tk.Toplevel):
    """出入库流水查看窗口。"""

    def __init__(self, master, part_id=None):
        super().__init__(master)
        self.part_id = part_id
        self.part = db.get_part(part_id) if part_id else None
        self.title(T("出入库流水记录"))
        self.configure(bg=W.C_BG)
        self.geometry("900x560")
        W.center_window(self, 900, 560)

        head = T("最近 500 条出入库记录")
        if self.part:
            label = (self.part.get("code") or self.part.get("model")
                     or self.part.get("name") or str(part_id))
            head = T("元件 {0} 的出入库记录（最近 500 条）", label)

        top = tk.Frame(self, bg=W.C_BG)
        top.pack(fill="x", padx=12, pady=10)
        tk.Label(top, text=head, bg=W.C_BG, fg=W.C_TEXT,
                 font=W.FONT_TITLE).pack(side="left")
        W.make_button(top, T("导出流水 CSV"),
                      lambda: self._export()).pack(side="right")

        wrap = tk.Frame(self, bg=W.C_CARD, highlightthickness=1,
                        highlightbackground=W.C_BORDER)
        wrap.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        cols = ("time", "kind", "code", "model", "qty", "loc", "op", "note")
        titles = (T("时间"), T("类型"), T("C号"), T("型号"), T("数量"), T("库位"), T("操作人"), T("备注"))
        widths = (140, 60, 80, 130, 70, 90, 80, 200)
        self.tv = ttk.Treeview(wrap, columns=cols, show="headings")
        for c, t, w in zip(cols, titles, widths):
            self.tv.heading(c, text=t)
            self.tv.column(c, width=w, anchor="center" if c in ("kind", "qty") else "w")
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=vs.set)
        self.tv.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        vs.pack(side="right", fill="y", pady=8)

        self.tv.tag_configure("OUT", foreground=W.C_RED)
        self.tv.tag_configure("IN", foreground=W.C_GREEN)

        self.txns = db.list_txns(part_id=part_id, limit=500)
        for t in self.txns:
            kind = T(config.TXN_LABEL.get(t.get("kind"), t.get("kind")))
            self.tv.insert("", "end", values=(
                t.get("created_at", ""), kind, t.get("code") or "",
                t.get("model") or "", t.get("quantity", 0),
                t.get("location") or "", t.get("operator") or "",
                t.get("note") or ""), tags=(t.get("kind"),))

    def _export(self):
        if not self.txns:
            W.toast(self, T("没有可导出的记录"), "warn")
            return
        path = io_utils.export_txns_csv(self.txns)
        messagebox.showinfo(T("导出完成"), T("已导出到：\n{0}", path), parent=self)


class SettingsDialog(tk.Toplevel):
    def __init__(self, master, on_saved=None):
        super().__init__(master)
        self.title(T("设置"))
        self.configure(bg=W.C_BG)
        self.transient(master)
        self.resizable(False, False)
        self.on_saved = on_saved

        self.v_thresh = tk.StringVar(
            value=str(config.get_setting("low_stock_threshold", 10)))
        self.v_op = tk.StringVar(value=config.get_setting("operator", "") or "")
        self.v_rate = tk.StringVar(
            value=str(config.get_setting("usd_rate", 7.2)))
        self.v_auto = tk.BooleanVar(
            value=bool(config.get_setting("auto_fetch_on_add", True)))
        self.v_confirm = tk.BooleanVar(
            value=bool(config.get_setting("confirm_delete", True)))
        self.v_neg = tk.BooleanVar(
            value=bool(config.get_setting("allow_negative_out", False)))
        self.v_lang = tk.StringVar(value=lang.current())
        self.v_auto_fx = tk.BooleanVar(
            value=bool(config.get_setting("auto_update_fx", True)))
        self.v_server = tk.StringVar(
            value=config.get_setting("server_profile", "auto") or "auto")
        self._lang0 = lang.current()

        box = tk.Frame(self, bg=W.C_CARD, highlightthickness=1,
                       highlightbackground=W.C_BORDER)
        box.pack(fill="x", padx=14, pady=(14, 6))
        inner = tk.Frame(box, bg=W.C_CARD)
        inner.pack(fill="x", padx=14, pady=12)
        inner.columnconfigure(1, weight=1)

        tk.Label(inner, text=T("低库存预警阈值"), bg=W.C_CARD, fg=W.C_TEXT,
                 font=W.FONT_UI).grid(row=0, column=0, sticky="e", pady=6)
        ttk.Entry(inner, textvariable=self.v_thresh, width=12).grid(
            row=0, column=1, sticky="w", padx=10)
        tk.Label(inner, text=T("库存数量 ≤ 该值时标红提醒（元件单独设置的阈值优先）"),
                 bg=W.C_CARD, fg=W.C_SUBTEXT, font=W.FONT_SMALL).grid(
            row=0, column=2, sticky="w")

        tk.Label(inner, text=T("默认操作人"), bg=W.C_CARD, fg=W.C_TEXT,
                 font=W.FONT_UI).grid(row=1, column=0, sticky="e", pady=6)
        ttk.Entry(inner, textvariable=self.v_op, width=18).grid(
            row=1, column=1, sticky="w", padx=10)
        tk.Label(inner, text=T("出入库流水里记录的经手人，可留空"),
                 bg=W.C_CARD, fg=W.C_SUBTEXT, font=W.FONT_SMALL).grid(
            row=1, column=2, sticky="w")

        tk.Label(inner, text=T("美元汇率"), bg=W.C_CARD, fg=W.C_TEXT,
                 font=W.FONT_UI).grid(row=2, column=0, sticky="e", pady=6)
        ttk.Entry(inner, textvariable=self.v_rate, width=12).grid(
            row=2, column=1, sticky="w", padx=10)
        tk.Label(inner, text=T("嘉立创商城报价是美元，按此汇率折算成参考单价（元）"),
                 bg=W.C_CARD, fg=W.C_SUBTEXT, font=W.FONT_SMALL).grid(
            row=2, column=2, sticky="w")

        ttk.Separator(inner, orient="horizontal").grid(
            row=3, column=0, columnspan=3, sticky="ew", pady=8)

        ttk.Checkbutton(inner, text=T("添加元件时自动查询商城资料"),
                        variable=self.v_auto).grid(
            row=4, column=0, columnspan=2, sticky="w")
        tk.Label(inner, text=T("填完 C 号自动联网取资料，不用再点按钮"),
                 bg=W.C_CARD, fg=W.C_SUBTEXT, font=W.FONT_SMALL).grid(
            row=4, column=2, sticky="w")

        ttk.Checkbutton(inner, text=T("删除元件前二次确认"),
                        variable=self.v_confirm).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
        tk.Label(inner, text=T("关掉后按 Delete 直接删除，不可恢复"),
                 bg=W.C_CARD, fg=W.C_SUBTEXT, font=W.FONT_SMALL).grid(
            row=5, column=2, sticky="w", pady=(6, 0))

        ttk.Checkbutton(inner, text=T("出库允许负库存"),
                        variable=self.v_neg).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(6, 0))
        tk.Label(inner, text=T("默认关闭（库存不足就拒绝）；开启后可以先出库、后补登记"),
                 bg=W.C_CARD, fg=W.C_SUBTEXT, font=W.FONT_SMALL).grid(
            row=6, column=2, sticky="w", pady=(6, 0))

        # ---------------- 语言与区域 ----------------
        box2 = tk.Frame(self, bg=W.C_CARD, highlightthickness=1,
                        highlightbackground=W.C_BORDER)
        box2.pack(fill="x", padx=14, pady=(0, 6))
        in2 = tk.Frame(box2, bg=W.C_CARD)
        in2.pack(fill="x", padx=14, pady=12)
        in2.columnconfigure(3, weight=1)

        tk.Label(in2, text=T("界面语言"), bg=W.C_CARD, fg=W.C_TEXT,
                 font=W.FONT_UI).grid(row=0, column=0, sticky="e", pady=6)
        _codes = [c for c, _n in lang.available()]
        self.cb_lang = ttk.Combobox(
            in2, state="readonly", width=14,
            values=[n for _c, n in lang.available()])
        self.cb_lang.current(_codes.index(self.v_lang.get())
                             if self.v_lang.get() in _codes else 0)
        self.cb_lang.grid(row=0, column=1, sticky="w", padx=10, columnspan=2)
        tk.Label(in2, text=T("界面文案会立即切换；分类名、库位名属于数据，保持原样"),
                 bg=W.C_CARD, fg=W.C_SUBTEXT, font=W.FONT_SMALL).grid(
            row=0, column=3, sticky="w")

        tk.Label(in2, text=T("汇率"), bg=W.C_CARD, fg=W.C_TEXT,
                 font=W.FONT_UI).grid(row=1, column=0, sticky="e", pady=6)
        fxbar = tk.Frame(in2, bg=W.C_CARD)
        fxbar.grid(row=1, column=1, columnspan=2, sticky="w", padx=10)
        ttk.Checkbutton(fxbar, text=T("启动时自动更新"),
                        variable=self.v_auto_fx).pack(side="left")
        W.make_button(fxbar, T("立即获取"), self._fetch_fx).pack(
            side="left", padx=8)
        tk.Label(in2, text=T("数据来自公开汇率接口，取不到时沿用上一次的值"),
                 bg=W.C_CARD, fg=W.C_SUBTEXT, font=W.FONT_SMALL).grid(
            row=1, column=3, sticky="w")
        self.lbl_fx = tk.Label(in2, text=fx.status_text(), bg=W.C_CARD,
                               fg=W.C_SUBTEXT, font=W.FONT_SMALL)
        self.lbl_fx.grid(row=2, column=1, columnspan=3, sticky="w", padx=10)

        # ---------------- 商城接入点 ----------------
        box3 = tk.Frame(self, bg=W.C_CARD, highlightthickness=1,
                        highlightbackground=W.C_BORDER)
        box3.pack(fill="x", padx=14, pady=(0, 6))
        in3 = tk.Frame(box3, bg=W.C_CARD)
        in3.pack(fill="x", padx=14, pady=12)
        in3.columnconfigure(3, weight=1)

        tk.Label(in3, text=T("商城接入点"), bg=W.C_CARD, fg=W.C_TEXT,
                 font=W.FONT_UI).grid(row=0, column=0, sticky="e", pady=6)
        self.cb_server = ttk.Combobox(in3, state="readonly", width=24,
                                      values=self._server_choices())
        self.cb_server.current(self._server_index())
        self.cb_server.grid(row=0, column=1, sticky="w", padx=10)
        W.make_button(in3, T("自动检测"), self._detect_server).grid(
            row=0, column=2, sticky="w")
        self.lbl_server = tk.Label(
            in3, text=T("检测会真实查询一次，能取到数据才算可用"),
            bg=W.C_CARD, fg=W.C_SUBTEXT, font=W.FONT_SMALL, wraplength=330,
            justify="left")
        self.lbl_server.grid(row=0, column=3, sticky="w")
        self.lbl_server2 = tk.Label(
            in3, text=servers.summary(), bg=W.C_CARD, fg=W.C_SUBTEXT,
            font=W.FONT_SMALL, wraplength=560, justify="left")
        self.lbl_server2.grid(row=1, column=1, columnspan=3, sticky="w",
                              padx=10, pady=(4, 0))

        bar = tk.Frame(self, bg=W.C_BG)
        bar.pack(fill="x", padx=14, pady=12)
        W.make_button(bar, T("保存"), self._save, "primary").pack(side="right")
        W.make_button(bar, T("取消"), self.destroy).pack(side="right", padx=8)

        W.center_window(self, 720, 660)
        self.grab_set()

    # ---------------------------------------------------------- 接入点选择
    def _server_ids(self):
        return ["auto"] + [p["id"] for p in servers.PROFILES]

    def _server_choices(self):
        return [T("自动（推荐）")] + [p["name"] for p in servers.PROFILES]

    def _server_index(self):
        cur = config.get_setting("server_profile", "auto") or "auto"
        ids = self._server_ids()
        return ids.index(cur) if cur in ids else 0

    def _server_selected(self):
        i = self.cb_server.current()
        ids = self._server_ids()
        return ids[i] if 0 <= i < len(ids) else "auto"

    def _detect_server(self):
        """并发实测所有接入点（真发一次查询，能取到数据才算可用）。"""
        self.lbl_server.configure(text=T("正在检测…"))
        self.lbl_server2.configure(text="")

        def done(results):
            best = servers.save_result(results)
            lines = []
            for r in results:
                mark = "✅" if r["ok"] else "❌"
                lines.append("%s %s　%d ms　%s"
                             % (mark, r["name"], r["ms"], r["detail"] or T("可用")))
            self.lbl_server.configure(
                text=T("检测完成，已选用：{0}", best["name"]) if best
                else T("没有检测到可用的接入点"))
            self.lbl_server2.configure(text="\n".join(lines))
            self.cb_server.configure(values=self._server_choices())

        def fail(err):
            self.lbl_server.configure(text=T("检测失败：{0}", err))

        W.run_async(self, lambda: servers.detect(timeout=6), done, fail)

    def _fetch_fx(self):
        """后台取一次实时汇率。"""
        self.lbl_fx.configure(text=T("正在获取汇率…"))

        def done(res):
            rate, src = res
            self.v_rate.set(str(rate))
            self.lbl_fx.configure(
                text=T("已更新：1 美元 = {0}（来源 {1}）", rate, src))

        def fail(err):
            self.lbl_fx.configure(
                text=T("获取失败：{0}（仍在用上一次的值）", err))

        W.run_async(self, fx.update_rate, done, fail)

    def _save(self):
        try:
            th = int(float(self.v_thresh.get() or 0))
        except ValueError:
            messagebox.showwarning(T("填写有误"), T("阈值必须是数字"), parent=self)
            return
        try:
            rate = float(self.v_rate.get() or 7.2)
            if rate <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(T("填写有误"), T("美元汇率必须是大于 0 的数字"), parent=self)
            return
        config.set_setting("low_stock_threshold", th)
        config.set_setting("operator", self.v_op.get().strip())
        config.set_setting("usd_rate", rate)
        config.set_setting("auto_fetch_on_add", bool(self.v_auto.get()))
        config.set_setting("confirm_delete", bool(self.v_confirm.get()))
        config.set_setting("allow_negative_out", bool(self.v_neg.get()))
        config.set_setting("auto_update_fx", bool(self.v_auto_fx.get()))
        config.set_setting("server_profile", self._server_selected())

        # 语言：换算成代码后立即生效
        codes = [c for c, _n in lang.available()]
        idx = self.cb_lang.current()
        new_lang = codes[idx] if 0 <= idx < len(codes) else self._lang0
        lang.set_language(new_lang)
        lang.reset_cache()

        if self.on_saved:
            self.on_saved()
        master = self.master
        self.destroy()
        if new_lang != self._lang0:
            try:
                master.reload_ui()
            except Exception:
                pass


class AboutDialog(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title(T("使用说明 / 关于"))
        self.configure(bg=W.C_BG)
        self.transient(master)
        self.resizable(False, False)

        txt = tk.Text(self, width=76, height=26, font=W.FONT_UI, wrap="word",
                      bg=W.C_CARD, relief="flat", padx=14, pady=12)
        txt.pack(fill="both", expand=True, padx=14, pady=14)
        txt.insert("1.0", about_text())
        txt.configure(state="disabled")

        W.make_button(self, T("知道了"), self.destroy, "primary").pack(
            side="right", padx=14, pady=(0, 14))
        W.center_window(self, 660, 560)
        self.grab_set()


ABOUT_TEXT = f"""{config.APP_NAME} v{config.VERSION}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【嘉立创元件怎么录入】
　点「＋ 添加元件」→ 选择「嘉立创商城元件」→ 输入 C 号（例如 C1525）
　→ 点「查询商城资料」，程序会自动从嘉立创商城带回：
　　 型号、厂商、封装、分类、参数值、阶梯价格、数据手册链接
　→ 填入库数量与库位 → 保存。
　同一个 C 号重复录入不会产生重复记录，只会追加库存。

【非嘉立创购买的元件怎么录入】
　点「＋ 添加元件」→ 切到「其它渠道元件」，手工填写名称、型号、
　供应商（如"淘宝-华强北"）、封装、数量等即可，不联网。
　这些元件会在列表「来源」列显示为「其它渠道」，可以用筛选器单独查看。

【筛选与查找】
　顶部筛选器支持按 来源（仅嘉立创 / 仅其它渠道）、库存状态
　（有库存 / 零库存 / 低库存预警）、分类 组合过滤；
　搜索框可以搜 C 号、型号、名称、厂商、封装、库位、备注，边打边筛。
　点列标题可以排序，再次点击切换升/降序。

【出入库】
　在列表里选中一行（多选按住 Ctrl / Shift），点「入库」「出库」
　「盘点」「库位调拨」。出库时如果库存不够会被拦住，不会出现负库存；
　确实需要「先出库、后补登记」时，可在出库窗口勾选「允许负库存」
　（或在「设置」里默认打开），此时会记成负数并在备注里写明欠账。
　所有变动都会记入流水，可在「帮助 → 出入库流水记录」里查看和导出。
　库存与流水是同一个事务写入的，中途断电也不会只改一半。

【价格与库存金额】
　嘉立创报价是分档的（买得越多单价越低），程序会把整张阶梯价表存下来。
　「参考单价(按量)」显示的是按当前库存数量匹配到的档位单价，
　「库存金额」= 库存数量 × 该档位单价，所以两者相乘能手工对上。
　汇率可在「设置」里调整；改汇率后已入库的旧数据不会自动重算，
　需要点右键「从嘉立创商城刷新资料」更新。

【批量导入】
　支持直接粘贴立创 BOM 清单或一串 C 号（每行一个，可带数量，
　如 C1525 100），也支持导入 CSV 表格。导入时会自动联网补全资料。

【数据存放位置】
　{config.DB_PATH}
　数据库是标准 SQLite 文件，建议定期用「文件 → 备份数据库」留底，
　备份用的是 SQLite 在线备份，即使正有操作也不会拷到半成品。
　换电脑时把整个「元件库存管理」文件夹拷走即可。

【联网说明】
　查询走嘉立创商城的公开接口，查询结果会缓存 7 天；
　程序启动时会自动清掉过期缓存，也可在「工具」菜单里手动清空。
　网络不通时不影响手工录入与出入库，只是无法自动补全资料。
"""

ABOUT_EN = f"""{config.APP_NAME} v{config.VERSION}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Adding an LCSC part]
  Click "＋ Add part" → choose "LCSC part" → enter the C-number (e.g. C1525)
  → click "Fetch LCSC data" and the program retrieves from LCSC:
     model, manufacturer, package, category, value, price tiers, datasheet link
  → fill in quantity and location → Save.
  Entering the same C-number again won't create a duplicate; stock is appended.

[Adding a part bought elsewhere]
  Click "＋ Add part" → switch to "Other-channel part" and fill in name, model,
  supplier (e.g. "Taobao - Huaqiangbei"), package and quantity. No network needed.
  These show as "Other" in the Source column and can be filtered separately.

[Filtering and searching]
  The toolbar filters by source (LCSC only / Other only), stock status
  (in stock / zero stock / low stock) and category, and they combine.
  The search box matches C-number, model, name, manufacturer, package, location
  and remarks, filtering as you type.
  Click a column header to sort; click again to reverse the order.

[Stock in / out]
  Select a row (hold Ctrl / Shift for several) and click Stock in, Stock out,
  Stocktake or Transfer. Issuing more than a location holds is blocked, so stock
  can't go negative. If you really need to ship first and register later, tick
  "Allow negative stock" in the dialog (or enable it in Settings) — the shortfall
  is recorded as a negative and noted in the remark.
  Every change is logged; see Help → Stock transaction log to view or export it.
  Stock and log are written in one transaction, so a power cut can't leave them
  half-updated.

[Price and stock value]
  LCSC quotes in quantity bands (cheaper in bulk) and the whole tier table is
  stored. "Ref. price (by qty)" is the tier price matching the quantity you hold,
  and "Stock value" = quantity × that tier price, so the two multiply out exactly.
  The exchange rate is set in Settings; changing it does not recompute parts
  already in the library — right-click "Refresh data from LCSC" to update them.

[Batch import]
  Paste an LCSC BOM list or a series of C-numbers (one per line, optionally with a
  quantity, e.g. C1525 100), or import a CSV file. Details are filled in online.

[Where data is stored]
  {config.DB_PATH}
  It's a standard SQLite file. Back it up regularly via File → Back up database;
  the backup uses SQLite's online backup, so it never copies a half-written file.
  To move to another machine, copy the whole folder.

[Network]
  Queries use LCSC's public API and results are cached for 7 days; expired
  entries are cleared at startup, or manually from the Tools menu.
  Without a connection you can still enter parts and move stock, you just can't
  auto-fill details.
"""


def about_text():
    """按当前界面语言返回使用说明（大段文本不进词典）。"""
    from core.lang import LANG_EN, current
    return ABOUT_EN if current() == LANG_EN else ABOUT_TEXT


def main():
    app = MainWindow()
    app.mainloop()
