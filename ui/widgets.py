# -*- coding: utf-8 -*-
"""界面样式与通用控件。"""
import threading
import tkinter as tk
from tkinter import ttk
from core.lang import T

# ---------------- 配色（浅色专业风） ----------------
C_BG = "#f2f4f7"          # 窗口底色
C_CARD = "#ffffff"        # 卡片
C_BORDER = "#d9dee5"      # 边框
C_TEXT = "#1f2328"        # 主文字
C_SUBTEXT = "#5f6771"     # 次要文字
C_PRIMARY = "#1668dc"     # 主色（蓝）
C_PRIMARY_D = "#0f52ad"
C_GREEN = "#2f9e44"       # 库存充足
C_ORANGE = "#e8590c"      # 低库存
C_RED = "#d63939"         # 缺货
C_TAG_LCSC = "#e7f0ff"    # 嘉立创标签底
C_TAG_OTHER = "#fff3e0"   # 其它渠道标签底
C_STRIPE = "#fafbfc"      # 表格斑马纹

FONT_UI = ("Microsoft YaHei UI", 9)
FONT_UI_B = ("Microsoft YaHei UI", 9, "bold")
FONT_TITLE = ("Microsoft YaHei UI", 13, "bold")
FONT_SMALL = ("Microsoft YaHei UI", 8)
FONT_MONO = ("Consolas", 10)


def setup_style(root):
    """统一配置 ttk 样式。"""
    root.configure(bg=C_BG)
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except Exception:
        pass

    st.configure(".", font=FONT_UI, background=C_BG, foreground=C_TEXT)
    st.configure("TFrame", background=C_BG)
    st.configure("Card.TFrame", background=C_CARD, relief="flat")
    st.configure("TLabel", background=C_BG, foreground=C_TEXT, font=FONT_UI)
    st.configure("Card.TLabel", background=C_CARD, foreground=C_TEXT)
    st.configure("Sub.TLabel", background=C_BG, foreground=C_SUBTEXT, font=FONT_SMALL)
    st.configure("SubCard.TLabel", background=C_CARD, foreground=C_SUBTEXT, font=FONT_SMALL)
    st.configure("Title.TLabel", background=C_BG, foreground=C_TEXT, font=FONT_TITLE)
    st.configure("StatNum.TLabel", background=C_CARD, foreground=C_PRIMARY,
                 font=("Microsoft YaHei UI", 15, "bold"))
    st.configure("StatLbl.TLabel", background=C_CARD, foreground=C_SUBTEXT, font=FONT_SMALL)

    st.configure("TButton", font=FONT_UI, padding=(10, 5), borderwidth=0,
                 background="#e8eaed", foreground=C_TEXT, focuscolor=C_BG)
    st.map("TButton",
           background=[("pressed", "#d5d9de"), ("active", "#dde1e6")],
           foreground=[("disabled", "#a8adb4")])

    st.configure("Primary.TButton", font=FONT_UI_B, padding=(12, 5),
                 background=C_PRIMARY, foreground="#ffffff")
    st.map("Primary.TButton",
           background=[("pressed", C_PRIMARY_D), ("active", "#2a76e0"),
                       ("disabled", "#b6c8e0")],
           foreground=[("disabled", "#eef2f7")])

    st.configure("Danger.TButton", font=FONT_UI, padding=(10, 5),
                 background="#fdecec", foreground=C_RED)
    st.map("Danger.TButton", background=[("active", "#f9d7d7")])

    st.configure("TEntry", fieldbackground=C_CARD, bordercolor=C_BORDER,
                 lightcolor=C_BORDER, darkcolor=C_BORDER, padding=4)
    st.configure("TCombobox", fieldbackground=C_CARD, background=C_CARD,
                 bordercolor=C_BORDER, arrowcolor=C_SUBTEXT, padding=3)
    st.map("TCombobox", fieldbackground=[("readonly", C_CARD)])

    st.configure("TLabelframe", background=C_BG, bordercolor=C_BORDER,
                 relief="solid", borderwidth=1)
    st.configure("TLabelframe.Label", background=C_BG, foreground=C_SUBTEXT,
                 font=FONT_UI_B)

    st.configure("Treeview", background=C_CARD, fieldbackground=C_CARD,
                 foreground=C_TEXT, rowheight=25, borderwidth=0,
                 font=FONT_UI)
    st.configure("Treeview.Heading", background="#eef1f5", foreground=C_SUBTEXT,
                 font=FONT_UI_B, relief="flat", padding=(6, 5))
    st.map("Treeview.Heading", background=[("active", "#e2e6ec")])
    st.map("Treeview", background=[("selected", "#d6e6ff")],
           foreground=[("selected", C_TEXT)])

    st.configure("TNotebook", background=C_BG, borderwidth=0)
    st.configure("TNotebook.Tab", font=FONT_UI, padding=(14, 6),
                 background="#e4e8ed", foreground=C_SUBTEXT)
    st.map("TNotebook.Tab",
           background=[("selected", C_CARD)],
           foreground=[("selected", C_PRIMARY)])

    st.configure("TProgressbar", background=C_PRIMARY, troughcolor="#e4e8ed",
                 borderwidth=0)
    st.configure("TSeparator", background=C_BORDER)
    st.configure("TCheckbutton", background=C_BG, font=FONT_UI)
    st.configure("Card.TCheckbutton", background=C_CARD, font=FONT_UI)
    return st


# ---------------- 异步执行（网络请求不卡界面） ----------------
def run_async(widget, task, on_done=None, on_error=None):
    """在后台线程执行 task()，完成后回到主线程回调。"""
    def worker():
        try:
            result = task()
        except Exception as e:                      # noqa: BLE001
            err = e
            try:
                widget.after(0, lambda: on_error(err) if on_error else None)
            except Exception:
                pass
            return
        try:
            widget.after(0, lambda: on_done(result) if on_done else None)
        except Exception:
            pass

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t


class StatusBar(tk.Frame):
    """底部状态栏。"""

    def __init__(self, master, **kw):
        super().__init__(master, bg="#e9edf2", height=26, **kw)
        self.pack_propagate(False)
        self._left = tk.Label(self, text=T("就绪"), bg="#e9edf2", fg=C_SUBTEXT,
                              font=FONT_SMALL, anchor="w")
        self._left.pack(side="left", padx=10)
        self._right = tk.Label(self, text="", bg="#e9edf2", fg=C_SUBTEXT,
                               font=FONT_SMALL, anchor="e")
        self._right.pack(side="right", padx=10)

    def set(self, text, kind="info"):
        color = {"info": C_SUBTEXT, "ok": C_GREEN,
                 "warn": C_ORANGE, "err": C_RED}.get(kind, C_SUBTEXT)
        self._left.configure(text=text, fg=color)

    def set_right(self, text):
        self._right.configure(text=text)


class StatCard(tk.Frame):
    """统计卡片：大数字 + 小标题。"""

    def __init__(self, master, label, value="0", color=C_PRIMARY, width=118):
        super().__init__(master, bg=C_CARD, highlightthickness=1,
                         highlightbackground=C_BORDER, width=width, height=52)
        self.pack_propagate(False)
        self._num = tk.Label(self, text=value, bg=C_CARD, fg=color,
                             font=("Microsoft YaHei UI", 14, "bold"))
        self._num.pack(anchor="w", padx=10, pady=(5, 0))
        self._lbl = tk.Label(self, text=label, bg=C_CARD, fg=C_SUBTEXT, font=FONT_SMALL)
        self._lbl.pack(anchor="w", padx=10)

    def set(self, value, color=None):
        self._num.configure(text=str(value))
        if color:
            self._num.configure(fg=color)


def make_button(parent, text, command, kind="normal", width=None):
    style = {"primary": "Primary.TButton",
             "danger": "Danger.TButton"}.get(kind, "TButton")
    btn = ttk.Button(parent, text=text, command=command, style=style)
    if width:
        btn.configure(width=width)
    return btn


def center_window(win, w=None, h=None):
    """居中显示窗口。"""
    win.update_idletasks()
    w = w or win.winfo_width()
    h = h or win.winfo_height()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    x = max(0, (sw - w) // 2)
    y = max(0, (sh - h) // 2 - 20)
    win.geometry(f"{w}x{h}+{x}+{y}")


def toast(parent, message, kind="info"):
    """轻量提示：短暂显示的小浮窗（不阻塞操作）。"""
    colors = {"info": C_PRIMARY, "ok": C_GREEN, "warn": C_ORANGE, "err": C_RED}
    top = tk.Toplevel(parent)
    top.overrideredirect(True)
    top.attributes("-topmost", True)
    bg = colors.get(kind, C_PRIMARY)
    frame = tk.Frame(top, bg=bg, padx=14, pady=8)
    frame.pack()
    tk.Label(frame, text=message, bg=bg, fg="#ffffff", font=FONT_UI,
             wraplength=420, justify="left").pack()
    parent.update_idletasks()
    x = parent.winfo_rootx() + parent.winfo_width() // 2 - 150
    y = parent.winfo_rooty() + max(60, parent.winfo_height() // 3)
    top.geometry(f"+{max(0, x)}+{max(0, y)}")
    top.after(2200, top.destroy)
    return top
