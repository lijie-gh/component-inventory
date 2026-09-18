# -*- coding: utf-8 -*-
"""提取界面文案 / 校验词典 / 注入 T()。

用 tokenize 定位（能准确跳过注释与文档字符串），用正则处理 f-string 模板。
替换时按「从后往前」的绝对偏移量做，前面的改动不会影响后面的位置。

关键概念 —— 一个字符串有两种形态：
  * **源码形态**（token.string）：`f"共 {n} 种\\n元件"`
  * **运行时形态**（词典要用这个）：`共 {0} 种<真实换行>元件`

`T()` 在运行时拿到的是后者，所以词典 key 必须是运行时形态。
两者之间的换算就是 `unescape()`。

用法：
    python tools/extract_ui_strings.py list     # 导出待翻译清单
    python tools/extract_ui_strings.py check    # 校验词典覆盖率
    python tools/extract_ui_strings.py apply    # 按词典注入 T()
"""
import ast
import io
import os
import re
import sys
import tokenize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CN = re.compile(r"[\u4e00-\u9fff]")
UI_DIR = os.path.join(ROOT, "ui")

# 这些行的字符串是「数据」不是文案，翻了就对不上外部数据
SKIP_LINE_HINTS = ("FIELD_LABEL", "COLUMNS =", "_HEADER_ALIASES")

# 不值得/不需要翻译的条目：版本行、分隔线、整块帮助文本（改用双语常量）
IGNORE_TMPL = ("{0} v{1}", "━━━")
IGNORE_CONTAINS = ("【嘉立创元件怎么录入】",)


def unescape(s):
    """把源码里的转义序列还原成运行时的字符。"""
    simple = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'",
              "0": "\0", "a": "\a", "b": "\b", "f": "\f", "v": "\v"}
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            c = s[i + 1]
            if c in simple:
                out.append(simple[c]); i += 2; continue
            if c == "u" and i + 6 <= len(s):
                out.append(chr(int(s[i + 2:i + 6], 16))); i += 6; continue
            if c == "x" and i + 4 <= len(s):
                out.append(chr(int(s[i + 2:i + 4], 16))); i += 4; continue
        out.append(s[i]); i += 1
    return "".join(out)


def templatize(body):
    """f-string 正文 -> (可翻译模板, 参数表达式列表)。"""
    args, out, i = [], [], 0
    while i < len(body):
        if body.startswith("{{", i):
            out.append("{{"); i += 2; continue
        if body.startswith("}}", i):
            out.append("}}"); i += 2; continue
        if body[i] == "{":
            j = body.find("}", i)
            if j < 0:
                out.append(body[i]); i += 1; continue
            inner = body[i + 1:j]
            m = re.match(r"^(.*?)(![rsa])?(?::(.*))?$", inner, re.S)
            expr = (m.group(1) if m else inner).strip()
            conv = (m.group(2) or "") if m else ""
            spec = (m.group(3) or "") if m else ""
            out.append("{%d%s%s}" % (len(args), conv, (":" + spec) if spec else ""))
            args.append(expr)
            i = j + 1
            continue
        out.append(body[i]); i += 1
    return "".join(out), args


def _docstrings(src):
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            ds = ast.get_docstring(node, clean=False)
            if ds:
                out.add(ds)
    return out


def scan(path):
    """返回文案条目。

    **相邻的字符串字面量会合并成一条**：代码里长文本常写成
    `("第一段"\n "第二段")` 这种隐式拼接，如果给每段各包一个 T()，
    会变成 `(T("第一段") T("第二段"))` —— 语法直接坏掉。
    正确做法是整组只包一层 T()，key 用拼接后的完整文本。
    """
    src = io.open(path, encoding="utf-8").read()
    docs = _docstrings(src)
    lines = src.splitlines()
    offs, acc = [], 0
    for ln in src.split("\n"):
        offs.append(acc)
        acc += len(ln) + 1

    def abs_pos(row, col):
        return offs[row - 1] + col

    with io.open(path, "r", encoding="utf-8") as f:
        try:
            toks = list(tokenize.generate_tokens(f.readline))
        except tokenize.TokenError:
            return []

    # 只把 NL/注释/缩进当作「可以跨越」，NEWLINE（逻辑行结束）会截断拼接
    TRANSPARENT = (tokenize.NL, tokenize.COMMENT, tokenize.INDENT,
                   tokenize.DEDENT)
    groups, cur, prev_is_str = [], None, False
    for t in toks:
        if t.type in TRANSPARENT:
            continue
        if t.type == tokenize.STRING:
            if prev_is_str and cur is not None:
                cur.append(t)
            else:
                cur = [t]
                groups.append(cur)
            prev_is_str = True
        else:
            prev_is_str = False

    items = []
    for grp in groups:
        segs, ok = [], True
        for t in grp:
            m = re.match(r'^([a-zA-Z]*)(\"\"\"|\'\'\'|\"|\')', t.string)
            if not m:
                ok = False
                break
            prefix, quote = m.group(1), m.group(2)
            if len(quote) == 3:      # 三引号多是文档/大段文本，单独处理
                ok = False
                break
            body = t.string[len(prefix) + len(quote):-len(quote)]
            segs.append((prefix.lower(), body, "r" in prefix.lower(), quote))
        if not ok or not segs:
            continue

        if any(s[1] in docs for s in segs):
            continue
        key = "".join(b if is_raw else unescape(b)
                      for _p, b, is_raw, _q in segs)
        if not CN.search(key):
            continue
        first, last = grp[0], grp[-1]
        line = lines[first.start[0] - 1] if first.start[0] <= len(lines) else ""
        if any(h in line for h in SKIP_LINE_HINTS):
            continue
        if any("f" in p for p, _b, _r, _q in segs):
            if len(segs) != 1:
                continue             # 多段混合 f-string，留给人工处理
            tmpl, args = templatize(segs[0][1])
            kind, key = "f", unescape(tmpl)
            # 替换文本必须去掉 f 前缀、并把 {expr} 换成 {0}。
            # 否则会生成 T(f"共 {n} 种", n)：模板里是 {n}，format 失败
            # 被静默吞掉，结果是英文界面照样显示中文（翻译失效）。
            repl = segs[0][3] + tmpl + segs[0][3]
        else:
            kind, args = "plain", []
            repl = src[abs_pos(*first.start):abs_pos(*last.end)]

        items.append({
            "start": abs_pos(*first.start),
            "end": abs_pos(*last.end),
            "kind": kind,
            "src": repl,
            "key": key,
            "args": args,
        })
    return items


def collect():
    out = {}
    for fn in sorted(os.listdir(UI_DIR)):
        if fn.endswith(".py"):
            items = scan(os.path.join(UI_DIR, fn))
            if items:
                out[fn] = items
    return out


def _ignored(key):
    if key in IGNORE_TMPL:
        return True
    return any(s in key for s in IGNORE_CONTAINS)


# ---------------------------------------------------------------- 命令
def cmd_list():
    all_items = collect()
    plain, dyn = set(), set()
    for items in all_items.values():
        for it in items:
            if _ignored(it["key"]):
                continue
            (dyn if it["kind"] == "f" else plain).add(it["key"].replace("\n", "\\n"))
    dst = os.path.join(ROOT, "build_tmp", "ui_strings.txt")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    txt = ("# 界面文案清单（中文 -> 待翻译英文）\n"
           f"# 纯文本 {len(plain)} 条，动态模板 {len(dyn)} 条\n\n"
           "=== A. 纯文本 ===\n" + "\n".join(sorted(plain)) +
           "\n\n=== B. 动态模板 ===\n" + "\n".join(sorted(dyn)) + "\n")
    io.open(dst, "w", encoding="utf-8", newline="\n").write(txt)
    print(f"清单 -> {dst}")
    print(f"纯文本 {len(plain)} 条，动态模板 {len(dyn)} 条")


def cmd_check():
    from core import lang_en
    all_items = collect()
    need, ignored = set(), 0
    for items in all_items.values():
        for it in items:
            if _ignored(it["key"]):
                ignored += 1
                continue
            need.add(it["key"])
    table = lang_en.TABLE
    miss = sorted(s for s in need if s not in table)
    print(f"界面文案 {len(need)} 条（另有 {ignored} 条走双语常量/忽略）")
    print(f"词典收录 {len(table)} 条，覆盖 {len(need) - len(miss)} 条，缺失 {len(miss)} 条")
    if miss:
        print("\n--- 缺失（漏翻会原样显示中文）---")
        for s in miss:
            print("   缺:", repr(s))
    unused = [k for k in table if k not in need]
    if unused:
        print(f"\n--- 词典里用不上的 {len(unused)} 条（key 可能写错）---")
        for s in unused[:25]:
            print("   多余:", repr(s))
    return len(miss)


def _needs_import(src):
    return "from core.lang import T" not in src and "import T" not in src


def cmd_apply():
    from core import lang_en
    table = lang_en.TABLE
    total, skipped = 0, []
    for fn, items in collect().items():
        path = os.path.join(UI_DIR, fn)
        src = io.open(path, encoding="utf-8").read()

        todo = []
        for it in items:
            if _ignored(it["key"]):
                continue
            if it["key"] not in table:
                continue                      # 没翻译的保持原样
            # 参数里还带中文字面量的（如条件表达式）先不动，人工处理更安全
            if any(CN.search(a) for a in it["args"]):
                skipped.append((fn, it["key"]))
                continue
            todo.append(it)

        if not todo:
            continue
        todo.sort(key=lambda x: x["start"], reverse=True)
        for it in todo:
            inner = it["src"]              # 已含引号；可能是多段拼接的整块
            if it["kind"] == "f":
                call = "T(" + inner + ", " + ", ".join(it["args"]) + ")"
            else:
                call = "T(" + inner + ")"
            src = src[:it["start"]] + call + src[it["end"]:]
            total += 1

        if _needs_import(src):
            # 插到最后一个 import 之后，保持分组整齐
            lines = src.split("\n")
            last = 0
            for i, ln in enumerate(lines[:60]):
                if re.match(r"^(import |from )", ln):
                    last = i
            lines.insert(last + 1, "from core.lang import T")
            src = "\n".join(lines)

        io.open(path, "w", encoding="utf-8", newline="\n").write(src)
        print(f"  {fn}: 注入 {len(todo)} 处")

    print(f"\n共注入 {total} 处 T()")
    if skipped:
        print(f"\n需人工处理的 {len(skipped)} 处（参数里含中文字面量）:")
        for fn, k in skipped:
            print(f"   {fn}: {k!r}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        cmd_list()
    elif cmd == "check":
        sys.exit(0 if cmd_check() == 0 else 0)
    elif cmd == "apply":
        cmd_apply()
