# -*- coding: utf-8 -*-
"""运行日志与全局异常兜底。

为什么需要它
------------
打包成 `--windowed` 的 exe 后 `sys.stdout/stderr` 都是 `None`
（见 `main.py` 的 `_NullStream`），而 tkinter 默认把界面回调里抛出的异常
写进 stderr —— 于是「点了按钮没反应」这种情况既不弹错、也不崩、更不留痕，
用户来反馈时无从查起。

这里做三件事：
1. 把异常按滚动方式写进 `data/logs/app.log`（超过 512 KB 自动轮转，留 3 份）；
2. 给用户一个明确的提示框（同一次运行最多弹 3 次，避免连环报错刷屏）；
3. 暴露 `last_error_summary()`，让界面能在启动时提醒「上次运行出过错」。
"""
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler

from core import config

LOGGER_NAME = "component_inventory"
_MAX_BYTES = 512 * 1024      # 单个日志文件上限
_KEEP_FILES = 3              # 轮转后保留的旧文件数
_MAX_POPUPS = 3              # 同一次运行最多弹几次错误框

_logger = None
_popups = 0


def log_path():
    """日志文件位置（与数据库同在 data\\ 下，跟着 exe 走）。"""
    return os.path.join(config.LOG_DIR, "app.log")


def get_logger():
    """取得写文件的 logger；重复调用返回同一个，失败也不抛异常。"""
    global _logger
    if _logger is not None:
        return _logger
    import logging
    lg = logging.getLogger(LOGGER_NAME)
    lg.setLevel(logging.INFO)
    lg.propagate = False          # 不要再往 stderr 写（exe 里那是空的）
    if not lg.handlers:
        try:
            os.makedirs(config.LOG_DIR, exist_ok=True)
            handler = RotatingFileHandler(
                log_path(), maxBytes=_MAX_BYTES, backupCount=_KEEP_FILES,
                encoding="utf-8")
            handler.setFormatter(logging.Formatter(
                "%(asctime)s  %(levelname)-7s %(message)s"))
            lg.addHandler(handler)
        except Exception:                                     # noqa: BLE001
            pass
    _logger = lg
    return lg


def info(msg, *args):
    try:
        get_logger().info(msg, *args)
    except Exception:                                         # noqa: BLE001
        pass


def error(msg, *args):
    try:
        get_logger().error(msg, *args)
    except Exception:                                         # noqa: BLE001
        pass


def last_error_summary():
    """上一条错误的摘要（给状态栏提示用）；没有错误则返回空串。

    必须在本次运行的启动日志写进文件**之前**调用，否则会读到自己的记录。
    """
    try:
        path = log_path()
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-300:]
        for line in reversed(lines):
            if " ERROR " in line:
                return line.strip()[:160]
    except Exception:                                         # noqa: BLE001
        pass
    return ""


def _detailed(text):
    """取异常的最后一行（异常类型 + 消息）作为给用户看的短信息。"""
    lines = [l for l in (text or "").strip().splitlines() if l.strip()]
    return lines[-1][:300] if lines else ""


def _show_popup(root, text):
    """出错提示框：告诉用户「出错了、日志在哪」，而不是让界面静默失效。"""
    global _popups
    if _popups >= _MAX_POPUPS:
        return
    _popups += 1
    try:
        from tkinter import messagebox
        from core.lang import T
        messagebox.showerror(
            T("出错了"),
            T("程序在运行时遇到一个错误，本次操作可能没有完成。\n"
              "详细信息已写入日志文件，反馈问题时请一并提供。\n\n"
              "{0}\n\n日志：{1}", _detailed(text), log_path()),
            parent=root)
    except Exception:                                         # noqa: BLE001
        pass


def handle_exception(etype, value, tb):
    """统一的异常出口：写日志，返回格式化后的文本（供弹窗使用）。"""
    try:
        text = "".join(traceback.format_exception(etype, value, tb))
    except Exception:                                         # noqa: BLE001
        text = f"{etype}: {value}"
    error("未捕获的异常\n%s", text.rstrip())
    return text


def install(root=None):
    """挂上全局兜底，返回上一条错误摘要（供调用方提醒用户）。

    - tkinter 界面回调里的异常 → `report_callback_exception`
    - 主线程未捕获的异常       → `sys.excepthook`
    """
    prev = last_error_summary()          # 先读上一轮的，再写本次启动记录

    info("-" * 58)
    info("启动 %s v%s（Python %s，%s）",
         config.APP_NAME, config.VERSION, sys.version.split()[0],
         "打包版" if getattr(sys, "frozen", False) else "源码运行")
    info("数据目录 %s", config.BASE_DIR)

    if root is not None:
        def _cb(etype, value, tb):
            text = handle_exception(etype, value, tb)
            _show_popup(root, text)

        try:
            root.report_callback_exception = _cb
        except Exception:                                     # noqa: BLE001
            pass

    def _hook(etype, value, tb):
        _show_popup(None, handle_exception(etype, value, tb))

    try:
        sys.excepthook = _hook
    except Exception:                                         # noqa: BLE001
        pass

    return prev
