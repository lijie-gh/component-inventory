# -*- coding: utf-8 -*-
"""一键构建：打包单文件 exe + 生成 GitHub 用的源码压缩包。

用法：  <python> tools\\build_exe.py              # 用哪个解释器跑，就出哪个架构
        <python> tools\\build_exe.py --no-zip     # 只出 exe，不重打源码包
        <python> tools\\build_exe.py --zip-only   # 只重打源码包

**exe 的架构由运行本脚本的解释器决定**，PyInstaller 不能交叉编译：
想同时出 32 位和 64 位，就得各用一份对应位数的 Python 跑一遍，例如

    D:\\python\\python.exe   tools\\build_exe.py --no-zip   →  …_v1.0.0_x64.exe
    D:\\python32\\python.exe tools\\build_exe.py            →  …_v1.0.0_x86.exe

产物都放进**按版本号命名的同一个子目录**里，两个架构并存、互不覆盖：

    发布\\1.0.0\\元件库存管理_v1.0.0_x64.exe        64 位系统用
    发布\\1.0.0\\元件库存管理_v1.0.0_x86.exe        32 位 / 老系统用（64 位也能跑）
    发布\\1.0.0\\元件库存管理_v1.0.0_Source.zip      源码包，解压后可直接传 GitHub
"""
import os
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import config  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_arch  # noqa: E402  同目录下的架构检查工具（读 PE 头）

APP = config.APP_NAME
VER = config.VERSION
# 文件名里的版本用完整版本号（1.0.0），与程序内「关于」显示的一致
VER_TAG = "v" + VER
# 架构后缀取自**当前解释器**：exe 的位数 = 打包解释器的位数，没有别的可能。
# 32 位 Python 的 sys.maxsize 只有 2**31-1，据此判位宽即可。
ARCH_TAG = "x64" if sys.maxsize > 2 ** 32 else "x86"
EXE_NAME = f"{APP}_{VER_TAG}_{ARCH_TAG}"
RELEASE_ROOT = os.path.join(ROOT, "发布")
# 每次发布收进自己的版本目录：发布\1.0.0\、发布\1.0.1\ …
# 这样旧版本不会被新构建覆盖掉，想回退直接翻目录拿。
RELEASE_DIR = os.path.join(RELEASE_ROOT, VER)
WORK_DIR = os.path.join(ROOT, "build_tmp")
ICON = os.path.join(ROOT, "assets", "app.ico")
# 源码包名用英文 Source：这个包是给人下载、解压后直接当仓库推的，
# 英文名在别人的终端里不会变成乱码，链接也好贴。
ZIP_NAME = f"{APP}_{VER_TAG}_Source.zip"

# 源码包里要带上的东西（data / 导出 / 构建产物一律不带）
SRC_INCLUDE = ["main.py", "启动程序.bat", "README.md", "README_EN.md", ".gitignore",
               "core", "ui", "tests", "tools", "assets"]
SRC_SKIP_DIRS = {"__pycache__", "发布", "build_tmp", "build", "dist",
                 "data", "导出", ".git", ".vscode", ".idea"}
SRC_SKIP_EXT = {".pyc", ".pyo", ".db", ".spec"}

# 运行时用不到、但 PyInstaller 可能顺手收进来的包，排掉能显著瘦身
EXCLUDES = [
    "PIL", "numpy", "scipy", "pandas", "matplotlib", "setuptools",
    "pkg_resources", "pip", "wheel", "pydoc", "doctest", "unittest",
    "lib2to3", "distutils", "test", "tkinter.test", "sqlite3.test",
]


def log(msg):
    print(msg, flush=True)


def check_pyinstaller():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        log("缺少 PyInstaller，请先执行：")
        log(r"  D:\python\python.exe -m pip install pyinstaller")
        return False
    return True


def ensure_icon():
    if os.path.exists(ICON):
        return True
    log("[图标] 未找到，正在生成…")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_icon.py")],
                       cwd=ROOT)
    return r.returncode == 0 and os.path.exists(ICON)


def write_version_file():
    """让 exe 的「属性 → 详细信息」里显示产品名与版本号。"""
    path = os.path.join(WORK_DIR, "version_info.txt")
    os.makedirs(WORK_DIR, exist_ok=True)
    ver4 = tuple(int(x) for x in (VER.split(".") + ["0"] * 4)[:4])
    content = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={ver4}, prodvers={ver4},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('080404b0', [
        StringStruct('CompanyName', '李杰'),
        StringStruct('FileDescription', '{APP}'),
        StringStruct('FileVersion', '{VER}'),
        StringStruct('InternalName', '{APP}'),
        StringStruct('OriginalFilename', '{EXE_NAME}.exe'),
        StringStruct('ProductName', '{APP}'),
        StringStruct('ProductVersion', '{VER}'),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def run_pyinstaller(ver_file):
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile", "--windowed",
        "--name", EXE_NAME,
        "--icon", ICON,
        "--add-data", f"{ICON}{os.pathsep}assets",
        "--version-file", ver_file,
        "--distpath", RELEASE_DIR,
        "--workpath", WORK_DIR,
        "--specpath", WORK_DIR,
    ]
    for m in EXCLUDES:
        cmd += ["--exclude-module", m]
    cmd.append(os.path.join(ROOT, "main.py"))

    log("[打包] " + " ".join(cmd[2:6]) + f" … （首次约需 1~3 分钟）")
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        log("打包失败，退出码 " + str(r.returncode))
        return None
    exe = os.path.join(RELEASE_DIR, EXE_NAME + ".exe")
    return exe if os.path.exists(exe) else None


def make_source_zip():
    """打源码包：剔除缓存、数据库、构建产物。"""
    out = os.path.join(RELEASE_DIR, ZIP_NAME)
    top = APP
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for item in SRC_INCLUDE:
            full = os.path.join(ROOT, item)
            if not os.path.exists(full):
                log(f"[源码包] 跳过缺失项：{item}")
                continue
            if os.path.isfile(full):
                if os.path.splitext(full)[1] in SRC_SKIP_EXT:
                    continue
                z.write(full, f"{top}/{item}")
                count += 1
                continue
            for dirpath, dirnames, filenames in os.walk(full):
                dirnames[:] = [d for d in dirnames if d not in SRC_SKIP_DIRS]
                for fn in filenames:
                    if os.path.splitext(fn)[1] in SRC_SKIP_EXT:
                        continue
                    p = os.path.join(dirpath, fn)
                    rel = os.path.relpath(p, ROOT).replace("\\", "/")
                    z.write(p, f"{top}/{rel}")
                    count += 1
    log(f"[源码包] {count} 个文件 → {out}")
    return out


def main():
    if "--zip-only" in sys.argv:
        # 只重打源码包（改了源码但 exe 不用重建时用）
        os.makedirs(RELEASE_DIR, exist_ok=True)
        log("完成：" + make_source_zip())
        return 0

    if not check_pyinstaller():
        return 1
    if not ensure_icon():
        log("图标生成失败，已中止")
        return 1

    os.makedirs(RELEASE_DIR, exist_ok=True)
    old_zip = os.path.join(RELEASE_DIR, ZIP_NAME)
    if os.path.exists(old_zip):
        os.remove(old_zip)

    ver_file = write_version_file()
    exe = run_pyinstaller(ver_file)
    if not exe:
        return 1

    size_mb = os.path.getsize(exe) / 1024 / 1024
    log(f"[打包] 完成 → {exe}  ({size_mb:.1f} MB)")

    # 架构由打包用的解释器决定，干脆在构建时就报出来，省得事后拆 PE 头
    arch = check_arch.read_pe_arch(exe)
    arch_text = (f"{arch['machine_name']}（{arch['bits']}）"
                 if arch else "读取失败")

    # 两个架构各跑一次构建，源码包是同一份内容 —— 第二次加 --no-zip 省时间
    if "--no-zip" in sys.argv:
        zip_path = os.path.join(RELEASE_DIR, ZIP_NAME)
        zip_note = "（本次跳过，沿用上一次）" if os.path.exists(zip_path) else "（本次跳过）"
    else:
        zip_path = make_source_zip()
        zip_note = ""

    log("")
    log("=" * 60)
    log(f"  {APP} {VER} 构建完成")
    log("=" * 60)
    log(f"  输出目录 {RELEASE_DIR}")
    log(f"  目标架构 {arch_text}")
    log(f"  即用版   {os.path.basename(exe)}   {size_mb:.1f} MB")
    if zip_note:
        log(f"  源码包   {os.path.basename(zip_path)} {zip_note}")
    else:
        log(f"  源码包   {os.path.basename(zip_path)}   "
            f"{os.path.getsize(zip_path) / 1024:.0f} KB")
    log("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
