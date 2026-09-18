# -*- coding: utf-8 -*-
"""在单个进程生命周期内验证 exe：启动 → 等窗口 → 查数据落点 → 稳定性 → 关闭。

用法：
    python tests/test_exe_build.py            # 测 发布\\<版本>\\ 下全部 exe（x64 + x86）
    python tests/test_exe_build.py x86        # 只测文件名里带 x86 的那个
    python tests/test_exe_build.py <路径>     # 只测指定文件

踩过的坑（别再犯）：
  1. 单文件 exe 的启动器会 fork 子进程跑真正的程序，Popen 拿到的 pid
     不等于窗口所属 pid —— 判据要用窗口标题，不要比对 pid。
  2. tasklist 输出是 GBK，用 UTF-8 匹配中文进程名会永远匹配不到。
  3. 后台进程在命令结束后会被工具清理，检测必须在同一命令内完成。
  4. 同一版本有 x64/x86 两份 exe，两份都必须在**同一条命令里**测完 ——
     分开跑两次不划算，而且第二轮会看到上一轮留下的 data/ 目录。
"""
import ctypes
import ctypes.wintypes as w
import glob
import os
import shutil
import sqlite3
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE_ROOT = os.path.join(ROOT, "发布")


def pick_exes():
    """挑出要测的 exe：命令行给了就按给的，否则两个架构全测。"""
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        out = []
        for a in args:
            if os.path.exists(a):
                out.append(os.path.abspath(a))
                continue
            hits = glob.glob(os.path.join(RELEASE_ROOT, "*", f"*{a}*.exe"))
            hits += glob.glob(os.path.join(RELEASE_ROOT, f"*{a}*.exe"))
            out += sorted(set(hits))
        return out
    # 产物按版本号收在子目录里（发布\1.0.0\…），自动找，升版本不用改这里
    hits = (glob.glob(os.path.join(RELEASE_ROOT, "*", "元件库存管理_v*.exe"))
            or glob.glob(os.path.join(RELEASE_ROOT, "元件库存管理_v*.exe")))
    return sorted(set(hits))


EXES = pick_exes()
if not EXES:
    raise SystemExit(f"没找到 exe，请先构建：{RELEASE_ROOT}\\<版本号>\\")
MARK = "元件库存管理 v"          # 窗口标题特征

user32 = ctypes.windll.user32
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)


def windows():
    res = []

    def cb(h, _):
        if not user32.IsWindowVisible(h):
            return True
        n = user32.GetWindowTextLengthW(h)
        if n == 0:
            return True
        b = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(h, b, n + 1)
        pid = w.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        res.append((pid.value, b.value))
        return True

    user32.EnumWindows(CB(cb), 0)
    return res


def test_one(exe):
    """跑一个 exe 的完整体检，返回 True/False。"""
    release = os.path.dirname(exe)
    print("=" * 62)
    print(f"被测程序：{exe}")
    print(f"数据应落在：{release}")

    print("清理上一轮测试产物…")
    for d in ("data", "导出"):
        p = os.path.join(release, d)
        if os.path.exists(p):
            shutil.rmtree(p)

    t0 = time.time()
    proc = subprocess.Popen([exe], cwd=release)
    print(f"已启动（启动器 PID={proc.pid}），计时中…")

    title = None
    while time.time() - t0 < 60:
        if proc.poll() is not None:
            print(f"启动器已退出，退出码 {proc.returncode}")
            break
        hit = [t for _, t in windows() if MARK in t and release in t]
        if hit:
            title = hit[0]
            break
        time.sleep(0.2)

    elapsed = time.time() - t0
    print(f"\n主窗口出现耗时 {elapsed:.1f} 秒（单文件首次需解压，日常会更快）")
    print("  [窗口]", title if title else "未出现 ❌")

    print("\n稳定性观测 20 秒…")
    alive = True
    for i in range(4):
        time.sleep(5)
        if proc.poll() is not None:
            print(f"  第 {(i + 1) * 5} 秒退出 ❌")
            alive = False
            break
    print("  持续运行 ✅" if alive else "  已退出 ❌")

    # 数据库是首次访问时才创建，必须等界面跑起来之后才能查到
    print("\n数据落点（应全部在 exe 同级目录）:")
    data_ok = True
    for rel in ("data/inventory.db", "data/backup", "导出"):
        p = os.path.join(release, rel)
        hit = os.path.exists(p)
        data_ok = data_ok and hit
        print(f"  {rel:<20} {'存在 ✅' if hit else '缺失 ❌'}")
    print("  data/settings.json   按需生成（未改设置时不落盘，属正常）")

    db = os.path.join(release, "data", "inventory.db")
    if os.path.exists(db):
        c = sqlite3.connect(db)
        tabs = sorted(r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"))
        cols = [r[1] for r in c.execute("PRAGMA table_info(parts)")]
        print(f"\n  [库] 表 {tabs}")
        print(f"  [库] parts {len(cols)} 列，price_tiers={'price_tiers' in cols}")
        print(f"  [库] integrity_check = {c.execute('PRAGMA integrity_check').fetchone()[0]}")
        c.close()

    # 关掉整棵进程树（启动器 + 子进程）
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                   capture_output=True)
    time.sleep(1)

    ok = bool(title) and alive and data_ok
    print("\n结论:", "✅ exe 可正常工作" if ok else "❌ 仍有问题")
    return ok


results = {exe: test_one(exe) for exe in EXES}

print("\n" + "=" * 62)
print("汇总")
for exe, ok in results.items():
    print(f"  {'✅' if ok else '❌'}  {os.path.relpath(exe, ROOT)}")
print("=" * 62)
all_ok = all(results.values())
print("结论:", "✅ 全部可用" if all_ok else "❌ 存在失败项")
sys.exit(0 if all_ok else 1)
