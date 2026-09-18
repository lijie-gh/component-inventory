# -*- coding: utf-8 -*-
"""修掉 `T(f"...", args)` 这种错误注入形式。

错误：T(f"共 {n} 种元件", n)     模板里是 {n}，format 时找不到 `n` 这个位置参数，
                                异常被 T() 静默吞掉 → 英文界面照样显示中文
正确：T("共 {0} 种元件", n)

只处理 `T(` 后面紧跟 f" / f' 的地方，其余代码不动。
（这个形式是早期版本的注入脚本留下的，新脚本已不会产生。）

    python tools/fix_fstring_calls.py
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from extract_ui_strings import templatize   # noqa: E402

PAT = re.compile(r"\bT\(f([\"'])")


def fix_line(line):
    out, i = [], 0
    while True:
        m = PAT.search(line, i)
        if not m:
            out.append(line[i:])
            break
        q = m.group(1)
        body_at = m.end()
        j, esc = body_at, False
        while j < len(line):
            c = line[j]
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == q:
                break
            j += 1
        if j >= len(line):               # 引号不闭合，保守跳过
            out.append(line[i:])
            break
        body = line[body_at:j]
        tmpl, _args = templatize(body)
        out.append(line[i:m.start()])
        out.append("T(" + q + tmpl + q)
        i = j + 1
    return "".join(out)


def main():
    ui = os.path.join(ROOT, "ui")
    total = 0
    for fn in sorted(os.listdir(ui)):
        if not fn.endswith(".py"):
            continue
        p = os.path.join(ui, fn)
        lines = io.open(p, encoding="utf-8").read().split("\n")
        changed = 0
        for k, ln in enumerate(lines):
            if "T(f" not in ln:
                continue
            new = fix_line(ln)
            if new != ln:
                lines[k] = new
                changed += 1
        if changed:
            io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
            print(f"  {fn}: 修正 {changed} 处")
            total += changed
    print(f"共修正 {total} 处")
    return total


if __name__ == "__main__":
    sys.exit(0 if main() >= 0 else 1)
