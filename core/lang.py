# -*- coding: utf-8 -*-
"""界面多语言（简体中文 / English）。

设计约定
--------
1. **中文原文就是 key**：词典只存「中文 → 英文」的映射。漏翻的条目会原样
   显示中文，不会崩、也不会出现 `ui.add_part` 这种给程序员看的 key。
   缺点是多语言共用一份中文原文，但对这个规模的项目是最稳的做法。
2. 只有**界面文案**才包 `T()`。下面三类是「数据」，绝对不要包，包了就坏：
   - `io_utils._HEADER_ALIASES` 的表格表头别名（要跟用户自己的 Excel 对上）
   - `config.CATEGORIES` 的元件分类（要存进数据库）
   - `i18n.py` 的术语词典（要跟商城返回的英文字段对上）
3. 带变量的用位置参数，别自己先拼好再翻译：::

       T("共 {0} 种元件", n)          ✅ 能翻译
       T("共 ") + str(n) + T(" 种元件")   ❌ 翻出来是散的

4. 翻译词典在 `core/lang_en.py`；用户也可用 `data/lang_en.json` 覆盖个别条目。
"""
import json
import os

from . import config

LANG_ZH = "zh"
LANG_EN = "en"

# (代码, 在自己语言里的名字) —— 语言名不翻译，否则英语用户看到的还是中文
LANGUAGES = [
    (LANG_ZH, "简体中文"),
    (LANG_EN, "English"),
]
DEFAULT_LANG = LANG_ZH

_override = {}      # 用户自定义覆盖
_loaded_lang = None


# ---------------------------------------------------------------- 当前语言
def available():
    """可选语言列表 [(代码, 名称)]。"""
    return list(LANGUAGES)


def language_name(code):
    for c, n in LANGUAGES:
        if c == code:
            return n
    return code


def normalize(code):
    """把各种写法归一成受支持的代码；不认识的一律回退中文。"""
    code = (code or "").strip().lower()
    if code.startswith("en"):
        return LANG_EN
    if code.startswith("zh"):
        return LANG_ZH
    return DEFAULT_LANG


def current():
    """当前界面语言（每次读设置，切完立刻生效，不用重启）。"""
    return normalize(config.get_setting("language", DEFAULT_LANG))


def set_language(code):
    return config.set_setting("language", normalize(code))


# ---------------------------------------------------------------- 翻译
def _dict():
    global _loaded_lang, _override
    lang = current()
    if _loaded_lang != lang:
        _override = _load_override(lang)
        _loaded_lang = lang
    return lang, _override


def _load_override(lang):
    """用户可在 data/lang_<code>.json 里覆盖个别词条。"""
    path = os.path.join(config.DATA_DIR, f"lang_{lang}.json")
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def _table(lang):
    if lang == LANG_EN:
        from . import lang_en
        return lang_en.TABLE
    return {}


def translate(text):
    """只查表，不做格式化。"""
    lang, override = _dict()
    if lang == LANG_ZH:
        return text
    if text in override:
        return override[text]
    return _table(lang).get(text, text)


def T(text, *args, **kwargs):
    """翻译 + 格式化。

    用法::

        T("添加元件")
        T("共 {0} 种元件", n)
        T("当前缓存 {0} 条（约 {1:.0f} KB）。", n, kb)

    `T()` 里的 `{0}` 是**位置占位符**，不是 f-string。原中文文案里若本来就有
    花括号（如 CSS/JSON 片段），格式化会失败，此时原样返回，不会抛异常。
    """
    out = translate(text)
    if not args and not kwargs:
        return out
    try:
        return out.format(*args, **kwargs)
    except Exception:
        return out


def missing_in(lang=LANG_EN):
    """返回词典里缺失的条目数（供自检用）。"""
    return len(_table(lang))


def reset_cache():
    """语言或词典文件变了以后，丢弃内存缓存。"""
    global _loaded_lang
    _loaded_lang = None
