# -*- coding: utf-8 -*-
"""扫描源码，找出「模块级（或类级）常量里直接调用 T()」的位置。

这类调用在 import 时求值，语言切换后不会刷新 —— 属于隐蔽 bug。
用法：D:\\python\\python.exe tools\\find_module_level_t.py
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def calls_t(node):
    """该表达式里是否出现 T(...) 调用。"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            f = sub.func
            if isinstance(f, ast.Name) and f.id == "T":
                return True
    return False


def scan(path):
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src, filename=path)
    hits = []

    def check_targets(targets, value, scope):
        for tgt in targets:
            if isinstance(tgt, ast.Name):
                if calls_t(value):
                    hits.append((tgt.lineno, scope, tgt.id))

    # ---- 模块级
    for node in tree.body:
        if isinstance(node, ast.Assign):
            check_targets(node.targets, node.value, "模块级")
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            check_targets([node.target], node.value, "模块级")
        elif isinstance(node, ast.ClassDef):
            # ---- 类级（类体里赋值，也是 def 之外）
            for sub in node.body:
                if isinstance(sub, ast.Assign):
                    check_targets(sub.targets, sub.value, f"类 {node.name}")
                elif isinstance(sub, ast.AnnAssign) and sub.value is not None:
                    check_targets([sub.target], sub.value, f"类 {node.name}")
    return hits


def main():
    total = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in ("__pycache__", ".git", "发布", "build", "dist")]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, ROOT)
            if rel.startswith("tools" + os.sep):
                continue
            try:
                hits = scan(path)
            except SyntaxError as e:
                print(f"[语法错误] {rel}: {e}")
                continue
            for line, scope, name in hits:
                print(f"{rel}:{line}  [{scope}] {name} = T(...)")
                total += 1
    if total == 0:
        print("未发现模块级/类级常量里的 T() 调用 —— 干净。")
    else:
        print(f"\n共 {total} 处需要改为「存原文、用时翻译」。")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
