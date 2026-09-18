# -*- coding: utf-8 -*-
"""元件库存管理 —— 程序入口。

直接运行：  python main.py
也可以双击目录下的「启动程序.bat」。
"""
import os
import sys
import traceback


class _NullStream:
    """哑输出流：打包成无控制台 exe 后 stdout/stderr 是 None。

    这时任何 print() 都会抛 AttributeError，把真正的启动错误盖掉，
    所以先顶上一个什么都不做的流，让错误能走到 MessageBox 去。
    """
    def write(self, *a):
        return 0

    def flush(self):
        pass

    def isatty(self):
        return False

    def readline(self, *a):
        return ""

    def close(self):
        pass


if sys.stdout is None:
    sys.stdout = _NullStream()
if sys.stderr is None:
    sys.stderr = _NullStream()
if sys.stdin is None:
    sys.stdin = _NullStream()

# 保证以任意工作目录启动都能找到包
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def _msgbox(title, text):
    """不依赖 tkinter 的提示框（tkinter 缺失时也能让用户看到原因）。"""
    print(f"[{title}] {text}")
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, str(text), str(title), 0x10)
    except Exception:
        pass


def _check_env():
    """启动前自检：Python 版本与 tkinter 是否可用。"""
    if sys.version_info < (3, 7):
        _msgbox("无法启动",
                f"需要 Python 3.7 或更高版本。\n当前版本：{sys.version.split()[0]}")
        return False
    try:
        import tkinter  # noqa: F401
    except Exception:
        _msgbox("无法启动",
                "当前 Python 缺少 tkinter 图形库，无法显示界面。\n\n"
                "解决办法：到 python.org 安装官方 Python（安装时勾选\n"
                "「tcl/tk and IDLE」），然后重新双击「启动程序.bat」。")
        return False
    return True


def main():
    if not _check_env():
        try:
            input("\n按回车键退出…")
        except Exception:
            pass
        return 1

    from ui.main_window import MainWindow

    app = MainWindow()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback as _tb
        err = _tb.format_exc()
        print("程序启动失败：\n")
        print(err)
        _msgbox("程序启动失败", err[-800:])
        try:
            input("\n按回车键退出…")
        except Exception:
            pass
        sys.exit(1)
