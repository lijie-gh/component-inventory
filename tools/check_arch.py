# -*- coding: utf-8 -*-
"""查看打包产物是 32 位还是 64 位（直接读 PE 头，不靠猜）。

用法：
    python tools/check_arch.py                  # 报告 发布\\<版本>\\ 下所有 exe（x64/x86 一起）
    python tools/check_arch.py <某个 exe 的路径>
    python tools/check_arch.py --interp         # 顺便体检当前解释器自带的组件

纯标准库实现（struct 解析 PE 头），不需要任何第三方包。
PE 头里的 Machine 字段是**唯一权威**的架构声明 —— 文件多大、装在哪台机器上
都没关系，编译器写进去的就是它。
"""
import glob
import os
import re
import struct
import sys

# COFF 文件头里的 Machine 字段
MACHINES = {
    0x014c: ("x86 (Intel 80386)", "32 位"),
    0x8664: ("x64 (AMD64)", "64 位"),
    0xaa64: ("ARM64 (AArch64)", "64 位"),
    0x01c0: ("ARM (32 位)", "32 位"),
    0x0200: ("IA64 (Itanium)", "64 位"),
}
# 可选头 Magic
PE_MAGIC = {
    0x010b: "PE32（32 位容器）",
    0x020b: "PE32+（64 位容器）",
    0x0107: "ROM",
}
# 子系统类型
SUBSYSTEMS = {
    1: "Native",
    2: "Windows GUI（图形界面）",
    3: "Windows Console（控制台）",
    5: "OS/2 Console",
    7: "POSIX Console",
    9: "Windows CE GUI",
    16: "EFI Application",
}
# DllCharacteristics 里的安全开关
DLL_FLAGS = [
    (0x0020, "HIGH_ENTROPY_VA", "高熵 64 位 ASLR"),
    (0x0040, "DYNAMIC_BASE", "ASLR（地址随机化）"),
    (0x0100, "NX_COMPAT", "DEP（数据执行保护）"),
    (0x0400, "NO_SEH", "不使用结构化异常处理"),
    (0x0800, "NO_BIND", "不允许绑定"),
    (0x8000, "TERMINAL_SERVER_AWARE", "兼容终端服务"),
]


def read_pe_arch(path):
    """读 PE 文件架构，返回 dict；不是 PE 文件则返回 None。"""
    with open(path, "rb") as f:
        if f.read(2) != b"MZ":
            return None
        f.seek(0x3C)
        raw = f.read(4)
        if len(raw) < 4:
            return None
        pe_off = struct.unpack("<I", raw)[0]

        f.seek(pe_off)
        sig = f.read(4)
        if sig != b"PE\x00\x00":
            return None
        coff = f.read(20)
        machine, nsec, tstamp, _psym, _nsym, optsz, chars = \
            struct.unpack("<HHIIIHH", coff)

        opt = f.read(optsz)
        magic = struct.unpack("<H", opt[0:2])[0]

    # 这两个字段在 PE32 与 PE32+ 里的偏移恰好相同（PE32 多出的
    # BaseOfData 4 字节，正好被 PE32+ 加宽的 ImageBase 抵消）
    major_subsys, minor_subsys = struct.unpack("<HH", opt[48:52])
    subsystem = struct.unpack("<H", opt[68:70])[0]
    dllchars = struct.unpack("<H", opt[70:72])[0]

    name, bits = MACHINES.get(machine, ("未知（%#06x）" % machine, "未知"))
    return {
        "pe_offset": pe_off,
        "machine": machine,
        "machine_name": name,
        "bits": bits,
        "opt_magic": magic,
        "opt_magic_name": PE_MAGIC.get(magic, "未知（%#06x）" % magic),
        "sections": nsec,
        "timestamp": tstamp,
        "characteristics": chars,
        # 是否可执行文件（COFF Characteristics 的 0x0002 位）
        "is_executable": bool(chars & 0x0002),
        "subsystem": subsystem,
        "subsystem_name": SUBSYSTEMS.get(subsystem, "未知（%d）" % subsystem),
        "os_version": (major_subsys, minor_subsys),
        "dll_characteristics": dllchars,
        "dll_flags": [desc for bit, _n, desc in DLL_FLAGS if dllchars & bit],
    }


def embedded_runtimes(path):
    """扫 exe 里内嵌的运行时 DLL 名（PyInstaller 的目录表是明文的）。"""
    with open(path, "rb") as f:
        data = f.read()
    py = sorted({m.decode("ascii", "replace")
                 for m in re.findall(rb"python3\d{0,2}(?:_d)?\.dll", data, re.I)})
    others = [n.decode() for n in
              (b"_tkinter", b"tcl86t.dll", b"tk86t.dll",
               b"sqlite3.dll", b"VCRUNTIME140.dll")
              if n in data]
    return py, others


def all_exes():
    """找 发布\\<版本>\\ 下所有 exe（同一版本会同时有 x64 / x86 两份）。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pats = [os.path.join(root, "发布", "*", "*.exe"),
            os.path.join(root, "发布", "*.exe")]
    hits = [p for pat in pats for p in glob.glob(pat)]
    # 同一个文件可能被两条 pattern 命中，去重后按名字排（_x64 在 _x86 前）
    return sorted(set(hits), key=lambda p: (os.path.basename(os.path.dirname(p)),
                                            os.path.basename(p)))


def report(path):
    info = read_pe_arch(path)
    print("文件        :", path)
    print("大小        : %.1f MB (%d 字节)"
          % (os.path.getsize(path) / 1048576, os.path.getsize(path)))
    print()
    if info is None:
        print("这不是一个 PE 文件（没有 MZ/PE 头），无法判断架构。")
        return 1

    print("--- PE 头 ---")
    print("PE 头偏移   : %#x" % info["pe_offset"])
    print("Machine     : %#06x  →  %s" % (info["machine"], info["machine_name"]))
    print("位宽        : %s" % info["bits"])
    print("可选头 Magic: %#06x  →  %s" % (info["opt_magic"], info["opt_magic_name"]))
    print("子系统      : %d  →  %s" % (info["subsystem"], info["subsystem_name"]))
    print("最低系统版本: %d.%d" % info["os_version"])
    print("区段数      : %d" % info["sections"])
    print("Characteristics: %#06x  (可执行 %s)"
          % (info["characteristics"], info["is_executable"]))
    print("安全特性    : %s"
          % (", ".join(info["dll_flags"]) if info["dll_flags"] else "（无）"))
    print()

    py, others = embedded_runtimes(path)
    print("--- 内嵌运行时 ---")
    print("Python 运行时:", ", ".join(py) if py else "（未命中，可能已整体压缩）")
    print("关键组件     :", ", ".join(others) if others else "（无）")
    print()

    print("--- 结论 ---")
    print("这是一个 %s Windows 可执行文件。" % info["bits"])
    pyver = None
    for n in py:
        m = re.match(r"python(\d)(\d{1,2})\.dll", n, re.I)
        if m:
            pyver = "%s.%s" % (m.group(1), m.group(2))
    if info["machine"] == 0x8664:
        print("  能在        : 64 位 Windows 8.1 / 10 / 11（现有电脑绝大多数）")
        print("  不能用在    : 32 位 Windows —— 双击会直接报"
              "「不是有效的 Win32 应用程序」")
    elif info["machine"] == 0x014c:
        print("  能在        : 32 位与 64 位 Windows（64 位系统靠 WOW64 兼容运行）")
        print("  注意        : 32 位进程最多用约 2~4 GB 内存")
    elif info["machine"] == 0xaa64:
        print("  能在        : Windows on ARM（ARM64）")
        print("  注意        : 需 ARM 版 Python 打包；x64 模拟下 x64 exe 反而更通用")

    print("  最低系统版本: PE 头里写的 %d.%d 是打包器的保守声明，"
          % info["os_version"])
    if pyver:
        print("                真正的要求由内置的 Python %s 决定"
              "（官方支持 Windows 8.1 及以上）。" % pyver)

    if info["subsystem"] == 2:
        print("  启动形态    : 图形界面程序，双击不会弹黑框（无控制台窗口）。")

    # 混入检测：exe 是 64 位，但内嵌声明的运行时名暗示 32 位（罕见但能查）
    if py and info["machine"] == 0x8664 and any("32" in n for n in py):
        print("  ⚠ 内嵌运行时名疑似 32 位，建议人工复核。")
    return 0


def interp_report():
    """体检当前解释器自带的二进制组件是否清一色同架构。"""
    root = os.path.dirname(os.path.abspath(sys.executable))
    targets = [sys.executable, os.path.join(root, "pythonw.exe")]
    for pat in ("python*.dll", "DLLs\\*.pyd", "DLLs\\*.dll", "tcl\\**\\*.dll"):
        targets += glob.glob(os.path.join(root, pat), recursive=True)

    rows = []
    for t in sorted(set(targets)):
        try:
            info = read_pe_arch(t)
        except OSError:
            info = None
        if info:
            rows.append((os.path.relpath(t, root), info["machine_name"], info["machine"]))

    print("解释器      :", sys.executable)
    print("Python 版本 :", sys.version.split()[0])
    print("位宽        : %d bit" % (struct.calcsize("P") * 8))
    print()
    print("--- 自带二进制组件 ---")
    for rel, name, _ in rows:
        print("  %-36s %s" % (rel, name))
    print()
    want = read_pe_arch(sys.executable)["machine"]
    bad = [r[0] for r in rows if r[2] != want]
    print("组件总数    : %d" % len(rows))
    print("架构一致    : %s" % ("✅ 全部同架构" if not bad
                               else "❌ 混入不同架构：%s" % bad))
    print()
    print("打包时用的是这个解释器 —— 它是什么架构，打出来的 exe 就是什么架构。")
    return 0


def main():
    args = [a for a in sys.argv[1:]]
    if "--interp" in args:
        return interp_report()

    if args:
        paths = args
    else:
        # 同一版本通常有 x64 / x86 两份，干脆全报出来，方便一眼对照
        paths = all_exes()
        if not paths:
            print("找不到 exe。请先构建，或手动指定路径：")
            print(r"  python tools\check_arch.py 发布\1.0.0\元件库存管理_v1.0.0_x64.exe")
            return 1

    rc = 0
    for i, path in enumerate(paths):
        if not os.path.exists(path):
            print("文件不存在：", path)
            rc = 1
            continue
        if i:
            print()
            print("#" * 62)
            print()
        rc = report(path) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
