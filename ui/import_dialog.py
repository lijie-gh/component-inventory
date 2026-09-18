# -*- coding: utf-8 -*-
"""批量导入：粘贴 C 号 / BOM 清单，或从 Excel（.xls / .xlsx）/ CSV 文件导入。

Excel 支持由 core/xlsread.py 提供（纯标准库），.xls 也能直接读，
不要求机器上装 xlrd / pandas。
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core import config, db, lcsc, service, io_utils
from . import widgets as W
from core.lang import T

# 文件类型过滤：Excel 放第一位，因为订单/购买记录大多导出成它。
# 标签存中文原文，弹出文件框时才翻译（模块级常量不能提前调 T()）。
FILETYPES = [
    ("Excel / CSV 表格", "*.xls *.xlsx *.xlsm *.csv *.txt *.tsv"),
    ("Excel 工作簿", "*.xls *.xlsx *.xlsm"),
    ("CSV / 文本", "*.csv *.txt *.tsv"),
    ("所有文件", "*.*"),
]

_FORMAT_LABEL = {
    "xls": "Excel 97-2003（.xls）",
    "xlsx": "Excel 工作簿（.xlsx）",
    "html": "网页导出的表格",
    "spreadsheetml": "Excel XML 表格",
    "csv": "CSV / 文本",
}


class ImportDialog(tk.Toplevel):
    def __init__(self, master, on_done=None):
        super().__init__(master)
        self.on_done = on_done
        self.items = []            # 粘贴模式解析出的条目
        self.file_items = []       # 文件模式解析出的记录
        self.file_meta = {}
        self.file_path = ""
        self.mode = "paste"

        self.title(T("批量导入元件"))
        self.configure(bg=W.C_BG)
        self.transient(master)
        self.geometry("840x660")
        W.center_window(self, 840, 660)
        self.grab_set()

        self.v_loc = tk.StringVar(value=config.DEFAULT_LOCATION)
        self.v_default_qty = tk.StringVar(value="0")
        self.v_skip_exist = tk.BooleanVar(value=True)
        self.v_online = tk.BooleanVar(value=True)
        self.v_progress = tk.DoubleVar(value=0)
        self.v_status = tk.StringVar(value="")
        self.v_file = tk.StringVar(value=T("（未选择文件）"))
        self.v_sheet = tk.StringVar(value="")

        self._build()

    # ------------------------------------------------------------ UI
    def _build(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=12, pady=(12, 6))

        # --- Tab1 粘贴 ---
        t1 = tk.Frame(self.nb, bg=W.C_CARD)
        self.nb.add(t1, text=T("  粘贴 C 号 / BOM 清单  "))
        tk.Label(t1, text=T("每行一个元件，支持 C1525、C1525 100、C1525 x100、"
                          "以及立创 BOM 导出的整行文本："),
                 bg=W.C_CARD, fg=W.C_SUBTEXT, font=W.FONT_SMALL,
                 anchor="w", wraplength=760, justify="left").pack(
            fill="x", padx=12, pady=(10, 4))
        self.txt = tk.Text(t1, height=12, font=W.FONT_MONO, wrap="none",
                           relief="solid", borderwidth=1, bg="#fcfdff")
        self.txt.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self.txt.insert("1.0", "C1525 100\nC25804 50\n")
        self.txt.bind("<KeyRelease>", lambda e: self._preview())

        # --- Tab2 文件 ---
        t2 = tk.Frame(self.nb, bg=W.C_CARD)
        self.nb.add(t2, text=T("  从 Excel / CSV 文件导入  "))

        row = tk.Frame(t2, bg=W.C_CARD)
        row.pack(fill="x", padx=12, pady=(12, 6))
        tk.Label(row, text=T("选择文件："), bg=W.C_CARD, fg=W.C_TEXT,
                 font=W.FONT_UI).pack(side="left")
        ttk.Entry(row, textvariable=self.v_file, width=46,
                  state="readonly").pack(side="left", padx=6)
        W.make_button(row, T("浏览…"), self._pick_file).pack(side="left")

        srow = tk.Frame(t2, bg=W.C_CARD)
        srow.pack(fill="x", padx=12)
        self.lbl_sheet = tk.Label(srow, text=T("工作表："), bg=W.C_CARD,
                                  fg=W.C_TEXT, font=W.FONT_UI)
        self.lbl_sheet.pack(side="left")
        self.cb_sheet = ttk.Combobox(srow, textvariable=self.v_sheet, width=22,
                                     state="readonly", font=W.FONT_UI)
        self.cb_sheet.pack(side="left", padx=6)
        self.cb_sheet.bind("<<ComboboxSelected>>", lambda e: self._reload_sheet())
        self.lbl_sheet.pack_forget()
        self.cb_sheet.pack_forget()

        info = tk.Frame(t2, bg="#eef5ff", highlightthickness=1,
                        highlightbackground="#cfe1fb")
        info.pack(fill="x", padx=12, pady=(8, 0))
        self.lbl_info = tk.Label(
            info, text=T("支持 Excel（.xls / .xlsx）、CSV、以及网页导出的表格文件。\n"
                       "表头会自动识别，常见列名（嘉立创C号 / 商品编号 / 编码 / 型号 / "
                       "名称 / 数量 / 购买数量 / 单价 / 采购渠道…）都能直接对上号。"),
            bg="#eef5ff", fg=W.C_SUBTEXT, font=W.FONT_SMALL,
            anchor="w", justify="left", wraplength=700)
        self.lbl_info.pack(fill="x", padx=10, pady=8)

        tk.Label(t2, text=T("核对上面的「识别列」和下方预览无误后，再点「开始导入」。\n"
                          "支持 .xls（Excel 97-2003）、.xlsx、.csv，以及网页导出的表格文件；"
                          "表头不在第一行、前面有标题行都没关系。"),
                 bg=W.C_CARD, fg=W.C_SUBTEXT, font=W.FONT_SMALL,
                 anchor="w", justify="left", wraplength=760).pack(
            fill="x", padx=14, pady=(6, 0))

        # --- 预览 ---
        pv = tk.LabelFrame(self, text=T(" 预览（解析结果） "), bg=W.C_BG,
                           fg=W.C_SUBTEXT, font=W.FONT_UI_B)
        pv.pack(fill="both", expand=True, padx=12, pady=6)
        cols = ("code", "qty", "name", "note")
        self.tv = ttk.Treeview(pv, columns=cols, show="headings", height=7)
        for c, t, w, a in (("code", T("C号 / 型号"), 130, "w"),
                           ("qty", T("数量"), 70, "center"),
                           ("name", T("名称"), 210, "w"),
                           ("note", T("来源 / 说明"), 330, "w")):
            self.tv.heading(c, text=t)
            self.tv.column(c, width=w, anchor=a)
        vs = ttk.Scrollbar(pv, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y", padx=(0, 8), pady=8)
        self.tv.pack(fill="both", expand=True, padx=8, pady=8)

        # --- 选项 ---
        opt = tk.Frame(self, bg=W.C_BG)
        opt.pack(fill="x", padx=12)
        tk.Label(opt, text=T("导入到库位："), bg=W.C_BG, fg=W.C_SUBTEXT,
                 font=W.FONT_UI).pack(side="left")
        ttk.Combobox(opt, textvariable=self.v_loc, width=14,
                     values=service.all_locations()).pack(side="left", padx=(0, 14))
        tk.Label(opt, text=T("未写数量时默认："), bg=W.C_BG, fg=W.C_SUBTEXT,
                 font=W.FONT_UI).pack(side="left")
        ttk.Entry(opt, textvariable=self.v_default_qty, width=8).pack(side="left")

        opt2 = tk.Frame(self, bg=W.C_BG)
        opt2.pack(fill="x", padx=12, pady=(4, 0))
        ttk.Checkbutton(opt2, text=T("已存在的元件只追加库存、不覆盖已录入的资料"),
                        variable=self.v_skip_exist).pack(side="left")
        ttk.Checkbutton(opt2, text=T("新建元件时联网补全嘉立创商城资料"),
                        variable=self.v_online).pack(side="left", padx=16)

        # --- 进度 + 按钮 ---
        bar = tk.Frame(self, bg=W.C_BG)
        bar.pack(fill="x", padx=12, pady=10)
        self.pb = ttk.Progressbar(bar, variable=self.v_progress, maximum=100,
                                  length=280)
        self.pb.pack(side="left")
        self.lbl_prog = tk.Label(bar, textvariable=self.v_status, bg=W.C_BG,
                                 fg=W.C_SUBTEXT, font=W.FONT_SMALL)
        self.lbl_prog.pack(side="left", padx=10)
        self.btn_ok = W.make_button(bar, T("开始导入"), self._run, "primary")
        self.btn_ok.pack(side="right")
        W.make_button(bar, T("关闭"), self.destroy).pack(side="right", padx=8)

        self.nb.bind("<<NotebookTabChanged>>", self._on_tab)
        self._preview()

    def _on_tab(self, event=None):
        self.mode = "file" if self.nb.index("current") == 1 else "paste"
        if self.mode == "paste":
            self._preview()
        else:
            self._preview_file()

    # ------------------------------------------------------------ 文件读取
    def _pick_file(self):
        path = filedialog.askopenfilename(
            title=T("选择 Excel / CSV 文件"),
            filetypes=[(T(label), pat) for label, pat in FILETYPES],
            parent=self)
        if path:
            self._load_file(path)

    def _load_file(self, path, sheet=None):
        try:
            items, meta = io_utils.read_table_file(path, sheet=sheet)
        except Exception as e:                                # noqa: BLE001
            messagebox.showerror(
                T("读取失败"),
                f"无法读取这个文件：\n{path}\n\n{e}\n\n"
                f"如果是 Excel 文件，可以先在 Excel 里另存为 .xlsx 或 .csv 再试。",
                parent=self)
            return
        self.file_path = path
        self.file_items = items
        self.file_meta = meta
        self.v_file.set(os.path.basename(path))
        sheets = meta.get("sheets") or []
        if len(sheets) > 1:
            self.lbl_sheet.pack(side="left")
            self.cb_sheet.pack(side="left", padx=6)
            self.cb_sheet.configure(values=sheets)
            self.v_sheet.set(meta.get("sheet") or sheets[0])
        else:
            self.lbl_sheet.pack_forget()
            self.cb_sheet.pack_forget()
            self.v_sheet.set("")
        self._show_info()
        self._preview_file()

    def _reload_sheet(self):
        if self.file_path and self.v_sheet.get():
            self._load_file(self.file_path, sheet=self.v_sheet.get())

    def _show_info(self):
        meta = self.file_meta
        lines = []
        fmt = T(_FORMAT_LABEL.get(meta.get("format"),
                                  meta.get("format") or "表格"))
        head = T("已识别：{0}", fmt)
        if len(meta.get("sheets") or []) > 1:
            head += T("（该文件有 {0} 个工作表，已选「{1}」）", len(meta['sheets']), meta['sheet'])
        lines.append(head)

        mapping = meta.get("mapping") or {}
        if mapping:
            parts = []
            for col, field in sorted(mapping.items()):
                parts.append(f"第{col + 1}列→{io_utils.FIELD_LABEL.get(field, field)}")
            if meta.get("guessed"):
                lines.append(T("没有识别到表头，已按内容推测：")
                             + "、".join(parts) + T("（可在下方预览里核对）"))
            else:
                lines.append(f"表头在第 {meta.get('header_row')} 行，"
                             f"识别列：{'、'.join(parts)}")
        else:
            lines.append(T("没有找到可用的 C 号 / 型号列，请检查表格内容。"))
        self.lbl_info.configure(
            text="\n".join(lines),
            fg=W.C_GREEN if mapping else W.C_ORANGE)
        self.lbl_info.pack(fill="x", padx=10, pady=8)

    def _preview_file(self):
        self.tv.delete(*self.tv.get_children())
        if not self.file_items:
            if self.mode == "file" and self.file_path:
                self.v_status.set(T("这个工作表里没有可导入的记录，请换一个工作表试试"))
            return
        total = 0
        for it in self.file_items[:400]:
            code = it.get("code") or it.get("model") or it.get("name") or "?"
            qty = int(it.get("total_qty") or 0)
            total += qty
            if it.get("code"):
                src = T("嘉立创 C 号")
            else:
                src = T("其它渠道") + (f"　{it.get('supplier')}" if it.get("supplier") else "")
            note = "　".join(x for x in [it.get("package"), it.get("brand"),
                                         it.get("supplier") if it.get("code") else ""] if x)
            self.tv.insert("", "end", values=(code, qty,
                                              it.get("name") or "",
                                              f"{src}　{note}".strip()))
        self.v_status.set(T("解析出 {0} 条记录，合计 {1} 个", len(self.file_items), total))

    # ------------------------------------------------------------ 粘贴解析
    def _preview(self):
        text = self.txt.get("1.0", "end")
        self.items = io_utils.parse_bom_text(text)
        if self.mode != "paste":
            return
        self.tv.delete(*self.tv.get_children())
        total = 0
        for it in self.items[:400]:
            total += int(it.get("qty") or 0)
            self.tv.insert("", "end",
                           values=(it["code"], it["qty"], "", T("嘉立创商城")))
        self.v_status.set(T("解析出 {0} 个 C 号，合计 {1} 个", len(self.items), total))

    # ------------------------------------------------------------ 执行
    def _run(self):
        loc = self.v_loc.get().strip() or config.DEFAULT_LOCATION
        try:
            default_qty = int(float(self.v_default_qty.get() or 0))
        except ValueError:
            messagebox.showwarning(T("填写有误"), T("默认数量必须是数字"), parent=self)
            return

        if self.mode == "file":
            if not self.file_items:
                messagebox.showinfo(T("没有可导入的内容"),
                                    T("请先选择一个 Excel / CSV 文件。"), parent=self)
                return
            jobs = [{"kind": "row", "row": r} for r in self.file_items]
        else:
            self.items = io_utils.parse_bom_text(self.txt.get("1.0", "end"))
            if not self.items:
                messagebox.showinfo(T("没有可导入的内容"),
                                    T("没有解析到任何 C 号，请检查输入格式。"), parent=self)
                return
            jobs = [{"kind": "code", "code": it["code"],
                     "qty": it["qty"] or default_qty} for it in self.items]

        if not jobs:
            return

        skip_exist = self.v_skip_exist.get()
        online = self.v_online.get()
        operator = config.get_setting("operator", "") or ""
        self.btn_ok.configure(state="disabled", text=T("导入中…"))
        total = len(jobs)
        self.v_progress.set(0)

        def task():
            ok, merged, failed = 0, 0, []
            for i, job in enumerate(jobs, 1):
                try:
                    if job["kind"] == "code":
                        merged += _import_code(job["code"], job.get("qty") or 0,
                                               loc, operator, skip_exist)
                        ok += 1
                    else:
                        merged += _import_row(job["row"], loc, default_qty,
                                              operator, skip_exist, online)
                        ok += 1
                except Exception as e:                        # noqa: BLE001
                    label = job.get("code") or (
                        job.get("row", {}).get("code")
                        or job.get("row", {}).get("model")
                        or job.get("row", {}).get("name") or "?")
                    failed.append(f"{label}：{e}")
                self.after(0, lambda i=i: self._update_progress(i, total))
            return ok, merged, failed

        def done(res):
            ok, merged, failed = res
            self.btn_ok.configure(state="normal", text=T("开始导入"))
            self.v_progress.set(100)
            self.v_status.set(f"完成：成功 {ok} 条（其中更新已有 {merged} 条），"
                              f"失败 {len(failed)} 条")
            if failed:
                detail = "\n".join(failed[:12])
                more = T("\n… 另有 {0} 条", len(failed) - 12) if len(failed) > 12 else ""
                messagebox.showwarning(
                    T("导入完成（有失败项）"),
                    T("成功 {0} 条，失败 {1} 条：\n\n{2}{3}", ok, len(failed), detail, more),
                    parent=self)
            else:
                W.toast(self.master, T("导入完成，共处理 {0} 条", ok), "ok")
            if self.on_done:
                self.on_done()

        def failed_cb(err):
            self.btn_ok.configure(state="normal", text=T("开始导入"))
            messagebox.showerror(T("导入失败"), str(err), parent=self)

        W.run_async(self, task, done, failed_cb)

    def _update_progress(self, i, total):
        self.v_progress.set(i * 100.0 / max(1, total))
        self.v_status.set(T("正在处理 {0}/{1}…", i, total))


# ---------------------------------------------------------------- 单条导入
def _import_code(code, qty, loc, operator, skip_exist):
    """粘贴模式的 C 号：已存在就按选项处理，不存在则联网建档。返回 1 表示合并进已有元件。"""
    exist = db.get_part_by_code(code)
    if exist and skip_exist:
        if qty:
            service.stock_in(exist["id"], qty, loc, operator, T("批量导入（追加库存）"))
        return 1
    service.add_from_lcsc(code, qty, loc, operator=operator)
    return 1 if exist else 0


def _import_row(row, loc, default_qty, operator, skip_exist, online):
    """文件模式的一行。返回 1 表示合并进了已有元件、0 表示新建。"""
    qty = int(row.get("total_qty") or 0) or default_qty
    location = (row.get("locations") or "").strip() or loc
    code = (row.get("code") or "").strip()

    exist = db.get_part_by_code(code) if code else None
    if not exist and not code:
        # 没有 C 号的行：按型号、再按名称去重，避免重复建档
        if row.get("model"):
            exist = db.query_one(
                "SELECT * FROM parts WHERE model=? AND source=?",
                (row["model"], config.SOURCE_OTHER))
        if not exist and row.get("name"):
            exist = db.query_one(
                "SELECT * FROM parts WHERE name=? AND source=?",
                (row["name"], config.SOURCE_OTHER))

    if exist and skip_exist:
        if qty:
            service.stock_in(exist["id"], qty, location, operator,
                             T("批量导入（追加库存，未改资料）"))
        return 1

    if code and lcsc.is_lcsc_code(code) and online:
        service.add_from_lcsc(code, qty, location, operator=operator)
    else:
        service.add_from_row(row, qty, location, operator=operator)
    return 1 if exist else 0
