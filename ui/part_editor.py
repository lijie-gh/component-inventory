# -*- coding: utf-8 -*-
"""元件编辑 / 新增对话框。

支持两种录入方式，用顶部的模式切换：
    ● 嘉立创商城元件 —— 输入 C 号，一键联网抓取型号/厂商/封装/价格/数据手册
    ● 其它渠道元件   —— 非嘉立创购买的元件，手工填写，不联网
"""
import tkinter as tk
from tkinter import ttk, messagebox

from core import config, db, lcsc, service
from . import widgets as W
from core.lang import T


class PartEditor(tk.Toplevel):
    def __init__(self, master, part=None, on_saved=None):
        super().__init__(master)
        self.part = part
        self.on_saved = on_saved
        self.is_edit = part is not None
        self._fetched = None          # 商城抓取结果
        self._descr_en = ""           # 商城返回的英文原文
        self._auto_job = None         # 自动查询的延时任务
        self._auto_code = ""          # 已自动查询过的 C 号
        self._fetching = False

        self.title(T("编辑元件") if self.is_edit else T("添加元件"))
        self.configure(bg=W.C_BG)
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.var_mode = tk.StringVar(value=config.SOURCE_LCSC)
        self.vars = {}
        self._build()
        # 先定尺寸再锁死：resizable(False) 会把窗口大小冻结在当前值上
        W.center_window(self, 660, 690)
        self.resizable(False, False)
        self.grab_set()
        self._load_part()
        self.after(120, self._focus_first)

    # ------------------------------------------------------------ UI
    def _build(self):
        pad = {"padx": 12, "pady": 4}

        # --- 模式切换 ---
        head = tk.Frame(self, bg=W.C_CARD, highlightthickness=1,
                        highlightbackground=W.C_BORDER)
        head.pack(fill="x", padx=12, pady=(12, 6))
        row = tk.Frame(head, bg=W.C_CARD)
        row.pack(fill="x", padx=12, pady=9)
        tk.Label(row, text=T("元件来源："), bg=W.C_CARD, fg=W.C_TEXT,
                 font=W.FONT_UI_B).pack(side="left")
        self.rb_lcsc = tk.Radiobutton(
            row, text=T("嘉立创商城元件（输入 C 号自动获取资料）"),
            variable=self.var_mode, value=config.SOURCE_LCSC,
            command=self._on_mode_change, bg=W.C_CARD, fg=W.C_TEXT,
            activebackground=W.C_CARD, selectcolor="#ffffff",
            font=W.FONT_UI, cursor="hand2")
        self.rb_lcsc.pack(side="left", padx=(0, 14))
        self.rb_other = tk.Radiobutton(
            row, text=T("其它渠道元件（非嘉立创采购，手工录入）"),
            variable=self.var_mode, value=config.SOURCE_OTHER,
            command=self._on_mode_change, bg=W.C_CARD, fg=W.C_TEXT,
            activebackground=W.C_CARD, selectcolor="#ffffff",
            font=W.FONT_UI, cursor="hand2")
        self.rb_other.pack(side="left")

        # --- 嘉立创查询条 ---
        self.fetch_bar = tk.Frame(self, bg="#eef5ff", highlightthickness=1,
                                  highlightbackground="#c9dcf7")
        self.fetch_bar.pack(fill="x", padx=12, pady=(0, 6))
        fr = tk.Frame(self.fetch_bar, bg="#eef5ff")
        fr.pack(fill="x", padx=10, pady=8)
        tk.Label(fr, text=T("嘉立创 C 号："), bg="#eef5ff", fg=W.C_TEXT,
                 font=W.FONT_UI_B).pack(side="left")
        self.e_code = ttk.Entry(fr, width=16, font=W.FONT_MONO)
        self.e_code.pack(side="left")
        self.e_code.bind("<Return>", lambda e: self._fetch())
        self.e_code.bind("<KeyRelease>", self._on_code_key)
        self.e_code.bind("<FocusOut>", self._on_code_key)
        self.btn_fetch = W.make_button(fr, T("查询商城资料"), self._fetch, "primary")
        self.btn_fetch.pack(side="left", padx=8)
        tk.Label(fr, text=T("例：C1525"), bg="#eef5ff", fg=W.C_SUBTEXT,
                 font=W.FONT_SMALL).pack(side="left")
        self.lbl_fetch = tk.Label(self.fetch_bar, text="", bg="#eef5ff",
                                  fg=W.C_SUBTEXT, font=W.FONT_SMALL,
                                  anchor="w", justify="left", wraplength=600)
        self.lbl_fetch.pack(fill="x", padx=10, pady=(0, 7))

        # --- 表单 ---
        form_wrap = tk.Frame(self, bg=W.C_CARD, highlightthickness=1,
                             highlightbackground=W.C_BORDER)
        form_wrap.pack(fill="both", expand=True, padx=12)
        self._form_wrap = form_wrap
        form = tk.Frame(form_wrap, bg=W.C_CARD)
        form.pack(fill="both", expand=True, padx=12, pady=10)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        def add(row, col, key, label, widget="entry", values=None, width=22):
            tk.Label(form, text=label, bg=W.C_CARD, fg=W.C_SUBTEXT,
                     font=W.FONT_UI).grid(row=row, column=col * 2,
                                          sticky="e", padx=(4, 6), pady=4)
            if widget == "combo":
                v = tk.StringVar()
                w = ttk.Combobox(form, textvariable=v, values=values or [],
                                 width=width, font=W.FONT_UI)
            elif widget == "text":
                v = tk.StringVar()
                w = ttk.Entry(form, textvariable=v, width=width, font=W.FONT_UI)
            else:
                v = tk.StringVar()
                w = ttk.Entry(form, textvariable=v, width=width, font=W.FONT_UI)
            w.grid(row=row, column=col * 2 + 1, sticky="ew", padx=(0, 14), pady=4)
            self.vars[key] = v
            return w

        self.w_name = add(0, 0, "name", T("名称/描述 *"))
        self.w_model = add(0, 1, "model", T("型号 / MPN"))
        self.w_brand = add(1, 0, "brand", T("厂商 / 品牌"))
        self.w_package = add(1, 1, "package", T("封装"))
        self.w_category = add(2, 0, "category", T("分类"), "combo",
                              values=db.all_categories() or config.CATEGORIES)
        self.w_value = add(2, 1, "value", T("参数值"))
        self.w_supplier = add(3, 0, "supplier", T("采购渠道"),
                              "combo", values=db.all_suppliers())
        self.w_unit = add(3, 1, "unit", T("单位"))
        self.w_min = add(4, 0, "min_qty", T("库存预警阈值"))
        self.w_price = add(4, 1, "ref_price", T("参考单价(元)"))
        self.w_ds = add(5, 0, "datasheet", T("数据手册链接"))
        self.w_remark = add(5, 1, "remark", T("备注"))

        # 详细描述
        tk.Label(form, text=T("详细描述"), bg=W.C_CARD, fg=W.C_SUBTEXT,
                 font=W.FONT_UI).grid(row=6, column=0, sticky="ne",
                                      padx=(4, 6), pady=4)
        self.e_descr = tk.Text(form, height=5, font=W.FONT_UI, wrap="word",
                               relief="solid", borderwidth=1,
                               highlightthickness=0, bg="#fcfdff")
        self.e_descr.grid(row=6, column=1, columnspan=3, sticky="ew",
                          padx=(0, 14), pady=4)

        # 商城返回的英文原文（正文已经翻成中文，这里留个底）
        self.lbl_descr_en = tk.Label(form, text="", bg=W.C_CARD,
                                     fg=W.C_SUBTEXT, font=W.FONT_SMALL,
                                     justify="left", anchor="w", wraplength=520)
        self.lbl_descr_en.grid(row=7, column=1, columnspan=3, sticky="w",
                               padx=(0, 14), pady=(0, 4))

        # --- 库存 ---
        tk.Frame(self, bg=W.C_BG, height=4).pack()
        stock_wrap = tk.Frame(self, bg="#fff8e8", highlightthickness=1,
                              highlightbackground="#f0dcae")
        stock_wrap.pack(fill="x", padx=12, pady=(0, 8))
        sr = tk.Frame(stock_wrap, bg="#fff8e8")
        sr.pack(fill="x", padx=10, pady=8)
        tk.Label(sr, text=T("入库数量："), bg="#fff8e8", fg=W.C_TEXT,
                 font=W.FONT_UI_B).pack(side="left")
        self.v_qty = tk.StringVar(value="0")
        self.e_qty = ttk.Entry(sr, textvariable=self.v_qty, width=10)
        self.e_qty.pack(side="left")
        tk.Label(sr, text=T("  存放库位："), bg="#fff8e8", fg=W.C_TEXT,
                 font=W.FONT_UI_B).pack(side="left")
        self.v_loc = tk.StringVar(value=config.DEFAULT_LOCATION)
        ttk.Combobox(sr, textvariable=self.v_loc, width=16,
                     values=service.all_locations(),
                     font=W.FONT_UI).pack(side="left")
        self.lbl_stock_hint = tk.Label(sr, text="", bg="#fff8e8",
                                       fg=W.C_SUBTEXT, font=W.FONT_SMALL)
        self.lbl_stock_hint.pack(side="left", padx=10)

        # --- 按钮 ---
        bar = tk.Frame(self, bg=W.C_BG)
        bar.pack(fill="x", padx=12, pady=(0, 12))
        W.make_button(bar, T("保存"), self._save, "primary").pack(side="right")
        W.make_button(bar, T("取消"), self._on_close).pack(side="right", padx=8)
        self.btn_del = W.make_button(bar, T("删除该元件"), self._delete, "danger")
        self.btn_del.pack(side="left")

    # ------------------------------------------------------------ 逻辑
    def _focus_first(self):
        try:
            if self.var_mode.get() == config.SOURCE_LCSC and not self.is_edit:
                self.e_code.focus_set()
            else:
                self.w_name.focus_set()
        except Exception:
            pass

    def _on_mode_change(self):
        """切换「嘉立创元件 / 其它渠道元件」两种录入模式。"""
        is_lcsc = self.var_mode.get() == config.SOURCE_LCSC
        if is_lcsc:
            # 查询条重新插回「模式条」与「表单」之间
            self.fetch_bar.pack_forget()
            self.fetch_bar.pack(fill="x", padx=12, pady=(0, 6),
                                before=self._form_wrap)
            self.vars["supplier"].set(T("嘉立创商城"))
            if not self.lbl_fetch.cget("text"):
                auto = config.get_setting("auto_fetch_on_add", True)
                tip = (T("填入 C 号后会自动联网查询（可在「设置」菜单里关闭），"
                       "自动带回型号、厂商、封装、价格与数据手册。")) if auto else \
                      (T("填入 C 号后点「查询商城资料」，自动带回型号、厂商、"
                       "封装、价格与数据手册。"))
                self.lbl_fetch.configure(text=tip, fg=W.C_SUBTEXT)
            self.geometry("660x690")
            if not self.is_edit:
                self.e_code.focus_set()
        else:
            self.fetch_bar.pack_forget()
            if self.vars["supplier"].get().strip() in ("", T("嘉立创商城")):
                self.vars["supplier"].set("")
            self.geometry("660x580")
            self.w_name.focus_set()

    def _on_code_key(self, event=None):
        """C 号输入后延时自动查询（可在「设置」菜单里关掉）。"""
        if self.is_edit or self._fetching:
            return
        if not config.get_setting("auto_fetch_on_add", True):
            return
        code = self.e_code.get().strip()
        if not lcsc.is_lcsc_code(code):
            return
        if lcsc._normalize_code(code) == self._auto_code:
            return
        if self._auto_job:
            try:
                self.after_cancel(self._auto_job)
            except Exception:
                pass
        self._auto_job = self.after(650, self._auto_fetch)

    def _auto_fetch(self):
        self._auto_job = None
        code = self.e_code.get().strip()
        if not lcsc.is_lcsc_code(code) or self._fetching:
            return
        self._auto_code = lcsc._normalize_code(code)
        self.lbl_fetch.configure(text=T("已识别 C 号，正在自动查询商城资料…"),
                                 fg=W.C_SUBTEXT)
        # 自动查询走「缓存优先」：7 天内查过的直接命中缓存，断网也能填上资料。
        # 想强制取最新，用户手动点「查询商城资料」按钮即可。
        self._fetch(silent=True, force=False)

    def _fetch(self, silent=False, force=True):
        code = self.e_code.get().strip()
        if not code:
            if not silent:
                W.toast(self, T("请先填写嘉立创 C 号"), "warn")
            return
        if not lcsc.is_lcsc_code(code):
            if not silent:
                W.toast(self, T("“{0}”不是有效的 C 号，应形如 C1525", code), "warn")
            return
        self._fetching = True
        self.btn_fetch.configure(state="disabled", text=T("查询中…"))
        self.lbl_fetch.configure(text=T("正在连接嘉立创商城…"), fg=W.C_SUBTEXT)

        def task():
            return lcsc.fetch_part(code, force=force)

        def done(data):
            self._fetching = False
            self.btn_fetch.configure(state="normal", text=T("查询商城资料"))
            self._fetched = data
            self._apply(data)
            src = T("本地缓存") if data.get("_from_cache") else T("嘉立创商城")
            self.lbl_fetch.configure(
                text=(f"已获取（{src}，{data.get('_fetched_at','')}）："
                      f"{data.get('brand','')} {data.get('model','')} "
                      f"{data.get('package','')}　现货 {data.get('stock_market','-')} 个"),
                fg=W.C_GREEN)
            if not silent:
                W.toast(self, T("已从嘉立创商城获取元件资料"), "ok")

        def failed(err):
            self._fetching = False
            self.btn_fetch.configure(state="normal", text=T("查询商城资料"))
            self.lbl_fetch.configure(text=T("查询失败：{0}", err), fg=W.C_RED)
            if silent:
                return
            messagebox.showwarning(
                T("查询失败"),
                f"{err}\n\n你可以切换到「其它渠道元件」手工录入，"
                f"或检查网络后重试。", parent=self)

        W.run_async(self, task, done, failed)

    def _apply(self, d):
        """把商城数据填进表单。"""
        mapping = [
            ("name", d.get("name")), ("model", d.get("model")),
            ("brand", d.get("brand")), ("package", d.get("package")),
            ("category", d.get("category")), ("value", d.get("value")),
            ("supplier", T("嘉立创商城")), ("unit", d.get("unit") or T("个")),
            ("ref_price", f"{d['ref_price']:g}" if d.get("ref_price") else ""),
            ("datasheet", d.get("datasheet")),
        ]
        for key, val in mapping:
            if val and key in self.vars:
                self.vars[key].set(str(val))
        if d.get("descr") or d.get("descr_en"):
            self._set_descr(d.get("descr"), d.get("descr_en"))

    def _set_descr(self, cn, en=""):
        """填写详细描述：正文用中文，商城英文原文放在下面一行备查。"""
        cn = (cn or "").strip()
        en = (en or "").strip()
        self._descr_en = en if en and en != cn else ""
        self.e_descr.delete("1.0", "end")
        if cn:
            self.e_descr.insert("1.0", cn)
        if self._descr_en:
            short = self._descr_en if len(self._descr_en) <= 150 \
                else self._descr_en[:150] + "…"
            self.lbl_descr_en.configure(text=T("商城英文原文：") + short)
        else:
            self.lbl_descr_en.configure(text="")

    def _load_part(self):
        """编辑模式下回填。"""
        p = self.part
        if not p:
            self.btn_del.pack_forget()
            self._on_mode_change()
            self.vars["unit"].set(T("个"))
            self.vars["min_qty"].set(
                str(config.get_setting("low_stock_threshold", 10)))
            return

        self.var_mode.set(p.get("source") or config.SOURCE_LCSC)
        is_lcsc = self.var_mode.get() == config.SOURCE_LCSC
        if is_lcsc:
            self.e_code.insert(0, p.get("code") or "")
        else:
            self.fetch_bar.pack_forget()
            self.lbl_fetch.configure(text="")

        for key in ("name", "model", "brand", "package", "category", "value",
                    "supplier", "unit", "remark", "datasheet"):
            if key in self.vars:
                self.vars[key].set(p.get(key) or "")
        if p.get("ref_price"):
            self.vars["ref_price"].set(f"{float(p['ref_price']):g}")
        self.vars["min_qty"].set(str(p.get("min_qty") or 0))
        self._set_descr(p.get("descr"), p.get("descr_en"))

        # 编辑时库存走出入库/盘点，这里只读展示
        total = db.get_total_qty(p["id"])
        self.v_qty.set("0")
        self.e_qty.configure(state="disabled")
        locs = db.get_stock_rows(p["id"])
        loc_txt = " 、".join(f"{r['location']}={r['quantity']}" for r in locs) or T("无库存")
        self.v_loc.set(locs[0]["location"] if locs else config.DEFAULT_LOCATION)
        self.lbl_stock_hint.configure(
            text=T("当前库存 {0}（{1}）　库存变更请用「入库/出库/盘点」", total, loc_txt))

    def _collect(self):
        data = {k: v.get().strip() for k, v in self.vars.items()}
        for key in ("min_qty", "ref_price"):
            val = data.get(key, "")
            if val == "":
                data[key] = 0 if key == "min_qty" else None
            else:
                try:
                    data[key] = float(val) if key == "ref_price" else int(float(val))
                except ValueError:
                    raise service.ServiceError(
                        T("「{0}」必须是数字",
                          T("参考单价") if key == "ref_price" else T("预警阈值")))
        data["descr"] = self.e_descr.get("1.0", "end").strip()
        if self._descr_en:
            data["descr_en"] = self._descr_en
        data["source"] = self.var_mode.get()
        return data

    def _save(self):
        try:
            data = self._collect()
        except service.ServiceError as e:
            messagebox.showwarning(T("填写有误"), str(e), parent=self)
            return

        source = data["source"]
        qty = 0
        try:
            if not self.is_edit:
                qty = int(float(self.v_qty.get() or 0))
        except ValueError:
            messagebox.showwarning(T("填写有误"), T("入库数量必须是数字"), parent=self)
            return
        location = self.v_loc.get().strip() or config.DEFAULT_LOCATION

        if source == config.SOURCE_LCSC:
            code = self.e_code.get().strip()
            if not code:
                messagebox.showwarning(T("缺少信息"), T("嘉立创元件必须填写 C 号"), parent=self)
                return
            if not lcsc.is_lcsc_code(code):
                messagebox.showwarning(T("格式有误"),
                                       T("“{0}”不是有效的 C 号，应形如 C1525", code), parent=self)
                return
            if self._fetched is None and not self.is_edit:
                if not messagebox.askyesno(
                        T("尚未获取商城资料"),
                        T("还没有从嘉立创商城获取资料，是否仍然保存？\n"
                        "（建议先点「查询商城资料」自动补全信息）"), parent=self):
                    return

        operator = config.get_setting("operator", "") or ""
        try:
            if self.is_edit:
                payload = dict(data)
                payload.pop("source", None)
                if source == config.SOURCE_LCSC:
                    payload["code"] = lcsc._normalize_code(self.e_code.get())
                    payload["supplier"] = payload.get("supplier") or T("嘉立创商城")
                service.update_part(self.part["id"], payload)
                result = ("edit", self.part["id"])
            elif source == config.SOURCE_LCSC:
                code = lcsc._normalize_code(self.e_code.get())
                extra = {k: v for k, v in data.items()
                         if k not in ("source",) and v not in (None, "")}
                pid, info, is_new = service.add_from_lcsc(
                    code, qty, location, extra=extra, operator=operator)
                result = ("new" if is_new else "merge", pid)
            else:
                data.pop("source", None)
                pid, is_new = service.add_manual(
                    data, qty, location, operator=operator)
                result = ("new" if is_new else "merge", pid)
        except (service.ServiceError, lcsc.LcscError) as e:
            messagebox.showerror(T("保存失败"), str(e), parent=self)
            return
        except Exception as e:                            # noqa: BLE001
            messagebox.showerror(T("保存失败"), T("发生未预期的错误：{0}", e), parent=self)
            return

        if self.on_saved:
            self.on_saved(result)
        self.destroy()

    def _delete(self):
        if not self.part:
            return
        if not messagebox.askyesno(
                T("确认删除"),
                f"确定要删除元件「{self.part.get('name') or self.part.get('code')}」吗？\n"
                f"它的库存记录与出入库流水会一并删除，此操作不可撤销。",
                parent=self, icon="warning"):
            return
        try:
            service.delete_part(self.part["id"])
        except Exception as e:                            # noqa: BLE001
            messagebox.showerror(T("删除失败"), str(e), parent=self)
            return
        if self.on_saved:
            self.on_saved(("delete", self.part["id"]))
        self.destroy()

    def _on_close(self):
        self.grab_release()
        self.destroy()
