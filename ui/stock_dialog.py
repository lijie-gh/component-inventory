# -*- coding: utf-8 -*-
"""出入库 / 盘点 / 调拨 对话框。"""
import tkinter as tk
from tkinter import ttk, messagebox

from core import config, db, service
from . import widgets as W
from core.lang import T


class StockDialog(tk.Toplevel):
    """对单个或多个元件做入库、出库、盘点、调拨。"""

    def __init__(self, master, parts, mode="in", on_done=None):
        super().__init__(master)
        self.parts = list(parts)
        self.mode = mode
        self.on_done = on_done

        titles = {"in": T("入库"), "out": T("出库"), "adjust": T("盘点"), "transfer": T("库位调拨")}
        self.title(titles.get(mode, T("库存操作")))
        self.configure(bg=W.C_BG)
        self.transient(master)
        self.resizable(False, False)

        self.v_qty = tk.StringVar(value="1")
        self.v_loc = tk.StringVar(value=config.DEFAULT_LOCATION)
        self.v_to = tk.StringVar(value="")
        self.v_op = tk.StringVar(value=config.get_setting("operator", "") or "")
        self.v_note = tk.StringVar()
        self.v_neg = tk.BooleanVar(
            value=bool(config.get_setting("allow_negative_out", False)))

        self._build()
        heights = {"transfer": 430, "out": 468}
        W.center_window(self, 470, heights.get(mode, 400))
        self.grab_set()
        self.after(100, lambda: self.e_qty.focus_set())

    def _build(self):
        titles = {"in": T("入库（增加库存）"), "out": T("出库（消耗库存）"),
                  "adjust": T("盘点（把库存改为实际数量）"),
                  "transfer": T("库位调拨（在两个库位之间转移）")}
        tk.Label(self, text=titles.get(self.mode), bg=W.C_BG, fg=W.C_TEXT,
                 font=W.FONT_TITLE).pack(anchor="w", padx=14, pady=(12, 4))

        # 元件清单
        card = tk.Frame(self, bg=W.C_CARD, highlightthickness=1,
                        highlightbackground=W.C_BORDER)
        card.pack(fill="x", padx=12)
        inner = tk.Frame(card, bg=W.C_CARD)
        inner.pack(fill="x", padx=12, pady=10)

        if len(self.parts) == 1:
            p = self.parts[0]
            tk.Label(inner, text=p.get("name") or p.get("model") or p.get("code"),
                     bg=W.C_CARD, fg=W.C_TEXT, font=W.FONT_UI_B,
                     anchor="w", justify="left", wraplength=420).pack(fill="x")
            sub = " ".join(x for x in [p.get("code"), p.get("model"),
                                       p.get("brand"), p.get("package")] if x)
            tk.Label(inner, text=sub or "—", bg=W.C_CARD, fg=W.C_SUBTEXT,
                     font=W.FONT_SMALL, anchor="w", wraplength=420).pack(fill="x", pady=(2, 4))
            rows = db.get_stock_rows(p["id"])
            loc_txt = "　".join(f"{r['location']}：{r['quantity']}" for r in rows) or T("当前无库存")
            tk.Label(inner, text=T("现有库存　{0}", loc_txt), bg=W.C_CARD,
                     fg=W.C_PRIMARY, font=W.FONT_UI, anchor="w",
                     wraplength=420).pack(fill="x")
        else:
            tk.Label(inner, text=T("已选择 {0} 个元件，将统一执行相同操作", len(self.parts)),
                     bg=W.C_CARD, fg=W.C_TEXT, font=W.FONT_UI_B).pack(anchor="w")
            preview = "、".join((p.get("code") or p.get("model") or "?")
                                for p in self.parts[:8])
            if len(self.parts) > 8:
                preview += T(" … 等 {0} 项", len(self.parts))
            tk.Label(inner, text=preview, bg=W.C_CARD, fg=W.C_SUBTEXT,
                     font=W.FONT_SMALL, anchor="w", justify="left",
                     wraplength=420).pack(fill="x", pady=(2, 0))

        # 表单
        form = tk.Frame(self, bg=W.C_BG)
        form.pack(fill="x", padx=12, pady=10)
        form.columnconfigure(1, weight=1)

        labels = {"in": T("入库数量"), "out": T("出库数量"),
                  "adjust": T("实际数量"), "transfer": T("调拨数量")}
        tk.Label(form, text=labels.get(self.mode, T("数量")), bg=W.C_BG,
                 fg=W.C_SUBTEXT, font=W.FONT_UI).grid(row=0, column=0, sticky="e",
                                                      padx=(0, 8), pady=5)
        self.e_qty = ttk.Entry(form, textvariable=self.v_qty, width=18,
                               font=W.FONT_MONO)
        self.e_qty.grid(row=0, column=1, sticky="w", pady=5)
        self.e_qty.bind("<Return>", lambda e: self._ok())

        locs = service.all_locations()
        r = 1
        if self.mode in ("in", "out", "adjust"):
            tk.Label(form, text=T("库位"), bg=W.C_BG, fg=W.C_SUBTEXT,
                     font=W.FONT_UI).grid(row=r, column=0, sticky="e",
                                          padx=(0, 8), pady=5)
            ttk.Combobox(form, textvariable=self.v_loc, values=locs, width=17,
                         font=W.FONT_UI).grid(row=r, column=1, sticky="w", pady=5)
            r += 1
        else:
            tk.Label(form, text=T("源库位"), bg=W.C_BG, fg=W.C_SUBTEXT,
                     font=W.FONT_UI).grid(row=r, column=0, sticky="e",
                                          padx=(0, 8), pady=5)
            ttk.Combobox(form, textvariable=self.v_loc, values=locs, width=17,
                         font=W.FONT_UI).grid(row=r, column=1, sticky="w", pady=5)
            r += 1
            tk.Label(form, text=T("目标库位"), bg=W.C_BG, fg=W.C_SUBTEXT,
                     font=W.FONT_UI).grid(row=r, column=0, sticky="e",
                                          padx=(0, 8), pady=5)
            ttk.Combobox(form, textvariable=self.v_to, values=locs, width=17,
                         font=W.FONT_UI).grid(row=r, column=1, sticky="w", pady=5)
            r += 1

        tk.Label(form, text=T("操作人"), bg=W.C_BG, fg=W.C_SUBTEXT,
                 font=W.FONT_UI).grid(row=r, column=0, sticky="e", padx=(0, 8), pady=5)
        ttk.Entry(form, textvariable=self.v_op, width=18,
                  font=W.FONT_UI).grid(row=r, column=1, sticky="w", pady=5)
        r += 1
        tk.Label(form, text=T("备注"), bg=W.C_BG, fg=W.C_SUBTEXT,
                 font=W.FONT_UI).grid(row=r, column=0, sticky="e", padx=(0, 8), pady=5)
        ttk.Entry(form, textvariable=self.v_note, width=28,
                  font=W.FONT_UI).grid(row=r, column=1, sticky="w", pady=5)

        if self.mode == "adjust":
            tk.Label(self, text=T("提示：盘点会把该库位数量直接改为填写值，并记录差额流水。"),
                     bg=W.C_BG, fg=W.C_SUBTEXT, font=W.FONT_SMALL,
                     wraplength=430, justify="left").pack(anchor="w", padx=14)
        if self.mode == "out":
            tk.Label(self, text=T("提示：库位库存不足时会拒绝出库，避免出现负库存。"),
                     bg=W.C_BG, fg=W.C_SUBTEXT, font=W.FONT_SMALL,
                     wraplength=430, justify="left").pack(anchor="w", padx=14)
            ttk.Checkbutton(
                self, text=T("允许负库存（先出库、后补登记入库）"),
                variable=self.v_neg, style="TCheckbutton").pack(anchor="w", padx=12)
            tk.Label(self, text=T("　　勾选后数量可以出成负数，并在备注里记下欠账，"
                               "库存与流水始终一致。"),
                     bg=W.C_BG, fg=W.C_SUBTEXT, font=W.FONT_SMALL,
                     wraplength=430, justify="left").pack(anchor="w", padx=14)

        bar = tk.Frame(self, bg=W.C_BG)
        bar.pack(fill="x", padx=12, pady=12, side="bottom")
        W.make_button(bar, T("确定"), self._ok, "primary").pack(side="right")
        W.make_button(bar, T("取消"), self.destroy).pack(side="right", padx=8)

    def _ok(self):
        try:
            qty = int(float(self.v_qty.get() or 0))
        except ValueError:
            messagebox.showwarning(T("填写有误"), T("数量必须是数字"), parent=self)
            return
        op = self.v_op.get().strip()
        note = self.v_note.get().strip()
        loc = self.v_loc.get().strip() or config.DEFAULT_LOCATION

        if qty <= 0 and self.mode != "adjust":
            messagebox.showwarning(T("填写有误"), T("数量必须大于 0"), parent=self)
            return
        if self.mode == "adjust" and qty < 0:
            messagebox.showwarning(T("填写有误"), T("数量不能为负数"), parent=self)
            return

        done, errors = 0, []
        for p in self.parts:
            try:
                if self.mode == "in":
                    service.stock_in(p["id"], qty, loc, op, note)
                elif self.mode == "out":
                    service.stock_out(p["id"], qty, loc, op, note,
                                      allow_negative=self.v_neg.get())
                elif self.mode == "adjust":
                    service.adjust_stock(p["id"], loc, qty, op, note or T("盘点调整"))
                else:
                    to = self.v_to.get().strip()
                    if not to:
                        raise service.ServiceError(T("请填写目标库位"))
                    service.transfer(p["id"], loc, to, qty, op)
                done += 1
            except Exception as e:                        # noqa: BLE001
                errors.append(f"{p.get('code') or p.get('model') or p['id']}：{e}")

        if errors:
            messagebox.showwarning(
                T("部分操作未完成"),
                T("成功 {0} 项，失败 {1} 项：\n\n", done, len(errors)) + "\n".join(errors[:8]),
                parent=self)
        if done and not errors:
            W.toast(self.master, T("已处理 {0} 项", done), "ok")
        if self.on_done:
            self.on_done()
        if not errors:
            self.destroy()
