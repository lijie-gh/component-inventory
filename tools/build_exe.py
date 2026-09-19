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
    发布\\1.0.0\\README.md / README_EN.md           该版本自己的说明文档
    发布\\1.0.0\\assets\\*.png                       上面两份 README 引用的截图

版本目录里的 README 是构建时自动放进去的，供手动上传 GitHub 用
（`发布/` 被 .gitignore 排除，它进不了仓库，只能自己拖上去）。
注意它**不是**仓库根目录那两份的复制粘贴：因为换了一层目录，相对路径会错层，
所以落盘时会把 Releases 链接改成绝对地址、并把引用到的截图一起复制进来 ——
这样这份 README 不管放到仓库的哪一层都能正常渲染。
"""
import os
import re
import shutil
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

# 版本目录里那份 README 要把 Releases 相对链接换成绝对地址，仓库地址优先
# 从 git 远程读；读不到（还没建仓库、没装 git）就用下面这个兜底。
FALLBACK_REPO_URL = "https://github.com/lijie-gh/component-inventory"
DOC_FILES = ["README.md", "README_EN.md"]
# 仓库根目录里写法是 [Releases](../../releases)，进了子目录就指错地方
REL_RELEASES = "](../../releases)"

# 源码包里要带上的东西（data / 导出 / 构建产物一律不带）
# 白名单制：这里没列到的文件会被**静默跳过**，打出来的源码包就缺它，
# 而且不会有任何提示。新加仓库根目录的文件（LICENSE、CONTRIBUTING.md 等）
# 记得同步加到这里，加完重打一次源码包并解压确认。
SRC_INCLUDE = ["main.py", "启动程序.bat", "README.md", "README_EN.md", ".gitignore",
               "LICENSE", "CONTRIBUTING.md",
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


def repo_url():
    """仓库地址：优先问 git，拿不到再用兜底常量。"""
    url = ""
    try:
        r = subprocess.run(["git", "config", "--get", "remote.origin.url"],
                           cwd=ROOT, capture_output=True, text=True, timeout=10)
        url = (r.stdout or "").strip()
    except Exception:                                          # noqa: BLE001
        url = ""
    if url.startswith("git@github.com:"):
        url = "https://github.com/" + url[len("git@github.com:"):]
    if url.endswith(".git"):
        url = url[:-4]
    return url or FALLBACK_REPO_URL


def export_docs_to_release():
    """把两份 README 连它们引用的截图一起放进版本目录，供手动上传 GitHub。

    与根目录那两份的差别只有这三处，都是为了「换个位置也能正常显示」：
      1. Releases 链接改成绝对地址（相对路径在子目录里会指到 .../blob/releases）；
      2. 把 README 里引用到的 assets/ 截图一并复制过去（否则图挂掉）；
      3. 版本号跟着目录名改（1.0.0 目录里不该写 v1.0.1）。
    """
    url = repo_url()
    # 目录名就是这一版自己的版本号（发布\1.0.0\ → 1.0.0）
    folder_ver = os.path.basename(RELEASE_DIR.rstrip(os.sep))
    dst_assets = os.path.join(RELEASE_DIR, "assets")
    docs, shots = [], []
    for name in DOC_FILES:
        src = os.path.join(ROOT, name)
        if not os.path.exists(src):
            log(f"[文档] 找不到 {name}，跳过")
            continue
        text = open(src, encoding="utf-8").read()
        text = text.replace(REL_RELEASES, f"]({url}/releases)")
        if f"{url}/releases" not in text:
            log(f"[文档] 注意：{name} 里没找到 Releases 相对链接，未改写（写法可能变了）")
        # 根目录那两份写的是**当前**构建的版本号。放进旧版本目录时要跟着目录改，
        # 否则 1.0.0 目录里的 README 会写 v1.0.1，和旁边躺着的文件名对不上。
        if re.match(r"^\d+(\.\d+)+$", folder_ver) and folder_ver != VER:
            n = text.count(VER_TAG)
            text = text.replace(VER_TAG, "v" + folder_ver)
            log(f"[文档] {name} 版本号 {VER_TAG} → v{folder_ver}（{n} 处）")
        for rel in sorted(set(re.findall(r"\]\((assets/[^)]+)\)", text))):
            p = os.path.join(ROOT, rel.replace("/", os.sep))
            if not os.path.exists(p):
                log(f"[文档] {name} 引用的 {rel} 不存在")
                continue
            os.makedirs(dst_assets, exist_ok=True)
            shutil.copy2(p, os.path.join(dst_assets, os.path.basename(p)))
            shots.append(os.path.basename(p))
        with open(os.path.join(RELEASE_DIR, name), "w", encoding="utf-8") as f:
            f.write(text)
        docs.append(name)
    log(f"[文档] {'、'.join(docs)} + {len(shots)} 张截图 → {RELEASE_DIR}")
    return docs


def main():
    if "--zip-only" in sys.argv:
        # 只重打源码包（改了源码但 exe 不用重建时用）
        os.makedirs(RELEASE_DIR, exist_ok=True)
        log("完成：" + make_source_zip())
        export_docs_to_release()
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

    # 版本目录里也放一份 README（连截图），方便直接拖到 GitHub 上去
    export_docs_to_release()

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
    log("  文档     README.md / README_EN.md + assets\\（可直接传 GitHub）")
    log("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
