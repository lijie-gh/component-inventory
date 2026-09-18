# -*- coding: utf-8 -*-
"""跑完 tests/ 下的全部自检脚本。

用法（在项目根目录下）：
    D:\\python\\python.exe tests\\run_all.py

所有脚本都用临时数据库运行，不会碰 data\\inventory.db。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = [
    "test_core_logic.py",        # 事务/负库存/阶梯价/统计/备份/迁移/缓存
    "test_gui_smoke.py",         # 界面能否正常创建与联动
    "test_export_roundtrip.py",  # 导出 CSV 再导入
]


def main():
    failed = []
    for name in SCRIPTS:
        print("\n" + "#" * 70)
        print(f"# {name}")
        print("#" * 70)
        rc = subprocess.call([sys.executable, os.path.join(HERE, name)])
        if rc != 0:
            failed.append(name)

    print("\n" + "=" * 70)
    if failed:
        print("未通过的脚本：")
        for n in failed:
            print("  -", n)
        return 1
    print(f"全部 {len(SCRIPTS)} 个自检脚本通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
