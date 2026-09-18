# -*- coding: utf-8 -*-
"""表格文件读取：.xls / .xlsx / .csv / 伪装成表格的 HTML/XML。

纯标准库实现，不需要 xlrd / openpyxl / pandas —— 保证程序拷到任何一台装了
Python 的电脑上都能直接跑。

实际会遇到的"Excel 文件"有四种，这里全部覆盖：

    ================  ==========================================  ==============
    真实格式           判断依据                                    处理方式
    ================  ==========================================  ==============
    BIFF8 二进制 .xls  文件头 D0 CF 11 E0（OLE2 复合文档）        自己解析
    .xlsx / .xlsm     PK\\x03\\x04（ZIP 容器）                     zipfile+XML
    伪装成 .xls 的      文件头是 <html / <table / <?xml             HTML 解析
    网页导出表           且带 SpreadsheetML 命名空间                或 XML 解析
    CSV / 制表符文本    其它                                         csv 模块
    ================  ==========================================  ==============

对外接口：

    read_sheets(path)  -> [{"name": 表名, "rows": [[单元格文本, ...], ...]}, ...]

单元格一律转成字符串：数字去掉多余小数、日期按 YYYY-MM-DD 输出（而不是
45123 这种序列号），空单元格是空串。
"""
import csv
import io
import os
import re
import struct
import zipfile
from datetime import datetime, timedelta
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

__all__ = ["read_sheets", "detect_format", "TableError"]


class TableError(Exception):
    """读取表格失败。"""


# ==================================================================== 格式判定
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ZIP_MAGIC = b"PK\x03\x04"
_SS_NS = "urn:schemas-microsoft-com:office:spreadsheet"
_ODOC_R_ID = ("{http://schemas.openxmlformats.org/officeDocument/2006/"
              "relationships}id")


def detect_format(path):
    """判断文件真实格式，返回 xls / xlsx / html / spreadsheetml / csv。"""
    with open(path, "rb") as f:
        head = f.read(8)
        f.seek(0)
        raw = f.read(65536)
    if head.startswith(_OLE_MAGIC):
        return "xls"
    if head.startswith(_ZIP_MAGIC):
        return "xlsx"
    text = _decode_text(raw).lstrip("\ufeff \t\r\n")
    low = text[:4000].lower()
    if _SS_NS in low:
        return "spreadsheetml"
    if low.startswith("<") and ("<table" in low or "<html" in low or "<tr" in low
                                or low.startswith("<?xml")):
        return "html"
    return "csv"


def read_sheets(path):
    """读取任意表格文件，返回 [{"name": 表名, "rows": [[...], ...]}]。"""
    if not os.path.exists(path):
        raise TableError(f"文件不存在：{path}")
    fmt = detect_format(path)
    if fmt == "xls":
        return _read_xls(path)
    if fmt == "xlsx":
        return _read_xlsx(path)
    if fmt == "spreadsheetml":
        return _read_spreadsheetml(path)
    if fmt == "html":
        return _read_html(path)
    return _read_csv(path)


# ==================================================================== 通用工具
_TEXT_ENCODINGS = ("utf-8-sig", "gb18030", "utf-16", "cp1252")


def _decode_text(raw):
    """文本文件编码嗅探：优先看 meta charset，其次按常见编码依次尝试。"""
    m = re.search(rb'charset\s*=\s*["\']?\s*([\w\-]+)', raw[:4096], re.I)
    if m:
        enc = m.group(1).decode("ascii", "ignore").lower()
        if enc in ("gb2312", "gbk", "gb18030"):
            enc = "gb18030"
        if enc in ("utf8", "utf-8"):
            enc = "utf-8"
        try:
            return raw.decode(enc)
        except Exception:
            pass
    for enc in _TEXT_ENCODINGS:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")


def _dec(raw, wide):
    """BIFF 字符串字节 -> str。wide=True 表示 16 位字符。"""
    if wide:
        return raw.decode("utf-16-le", "replace")
    try:
        return raw.decode("cp1252")
    except Exception:
        return raw.decode("latin-1", "replace")


def _local(tag):
    """去掉 XML 命名空间前缀。"""
    return str(tag).rsplit("}", 1)[-1]


def _trim(rows):
    """去掉尾部空行、尾部空列、以及中间的全空行。"""
    rows = [list(r) for r in rows]
    while rows and not any(str(c).strip() for c in rows[-1]):
        rows.pop()
    ncol = 0
    for row in rows:
        for i, c in enumerate(row):
            if str(c).strip():
                ncol = max(ncol, i + 1)
    if ncol:
        rows = [row[:ncol] for row in rows]
    return [row for row in rows if any(str(c).strip() for c in row)]


def _base_name(path):
    return os.path.splitext(os.path.basename(path))[0] or "Sheet1"


# ==================================================================== 数字 / 日期
# 内置格式编号 -> 格式串（只列会用到的；日期相关的是 14~22、45~47，
# 27~36 / 50~58 是各地区变体，统一按「年-月-日」处理即可）
_XL_FMT_BUILTIN = {
    0: "General", 1: "0", 2: "0.00", 3: "#,##0", 4: "#,##0.00",
    9: "0%", 10: "0.00%", 11: "0.00E+00", 12: "# ?/?", 13: "# ??/??",
    14: "mm-dd-yy", 15: "d-mmm-yy", 16: "d-mmm", 17: "mmm-yy",
    18: "h:mm AM/PM", 19: "h:mm:ss AM/PM", 20: "h:mm", 21: "h:mm:ss",
    22: "m/d/yy h:mm", 37: "#,##0 ;(#,##0)", 38: "#,##0 ;[Red](#,##0)",
    39: "#,##0.00;(#,##0.00)", 40: "#,##0.00;[Red](#,##0.00)",
    41: "_(* #,##0_);_(* (#,##0);_(* \"-\"_);_(@_)",
    42: "_(\"¥\"* #,##0_);_(\"¥\"* (#,##0);_(\"¥\"* \"-\"_);_(@_)",
    45: "mm:ss", 46: "[h]:mm:ss", 47: "mmss.0", 48: "##0.0E+0", 49: "@",
}
for _i in list(range(27, 37)) + list(range(50, 59)):
    _XL_FMT_BUILTIN.setdefault(_i, "yyyy-m-d")


def _strip_fmt(code):
    """去掉格式串里的引号文字、[条件]/[颜色]、转义符，只留占位符。"""
    s = re.sub(r"\[[^\]]*\]", "", code or "")
    s = re.sub(r'"[^"]*"', "", s)
    s = re.sub(r"_.", "", s)
    s = re.sub(r"\\.", "", s)
    return s.split(";")[0]


def _fmt_kind(code):
    """格式串 -> (是否日期时间, 是否含时间部分)。"""
    s = _strip_fmt(code).strip()
    if not s or s.lower() == "general" or s == "@":
        return False, False
    has_date = bool(re.search(r"[yYmMdD]", s))
    has_time = bool(re.search(r"[hHsS]", s))
    if not has_date and not has_time:
        return False, False
    # 含数字占位符（如 0.00）且不含日期字符的，是普通数字
    return True, has_time


def _serial_to_text(serial, datemode, has_time):
    """Excel 日期序列号 -> 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM:SS'。"""
    try:
        s = float(serial)
    except Exception:
        return str(serial)
    try:
        if datemode:                      # 1904 日期系统（Mac 版 Excel）
            base = datetime(1904, 1, 1)
        elif s < 60:                      # 1900 系统：60 之前要补上闰年 bug
            base = datetime(1899, 12, 31)
        else:
            base = datetime(1899, 12, 30)
        dt = base + timedelta(seconds=round(s * 86400))
    except Exception:
        return "%.10g" % s
    if has_time and (dt.hour or dt.minute or dt.second):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return dt.strftime("%Y-%m-%d")


def _num_to_text(v, kind):
    """普通数字 -> 精简字符串；日期格式则转日期。"""
    if kind[0]:
        return _serial_to_text(v, kind[2], kind[1]) if len(kind) > 2 \
            else _serial_to_text(v, 0, kind[1])
    try:
        f = float(v)
    except Exception:
        return str(v)
    if f == int(f) and abs(f) < 1e15:
        return str(int(f))
    return "%.10g" % f


# ==================================================================== CSV
def _read_csv(path):
    with open(path, "rb") as f:
        text = _decode_text(f.read())
    if not text.strip():
        return [{"name": _base_name(path), "rows": []}]
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except Exception:
        dialect = csv.excel
    rows = [[(c if isinstance(c, str) else "") .strip() for c in r]
            for r in csv.reader(io.StringIO(text), dialect)]
    return [{"name": _base_name(path), "rows": _trim(rows)}]


# ==================================================================== OLE2 容器
def _ole_streams(data):
    """读 OLE2 复合文档，返回 {流名: 字节}。"""
    if data[:8] != _OLE_MAGIC:
        raise TableError("不是有效的 .xls 文件（缺少 OLE2 文件头）")
    if len(data) < 512:
        raise TableError("文件太小，不是有效的 .xls")
    try:
        ssz = 1 << struct.unpack_from("<H", data, 0x1E)[0]
        mssz = 1 << struct.unpack_from("<H", data, 0x20)[0]
        n_fat = struct.unpack_from("<I", data, 0x2C)[0]
        dir_start = struct.unpack_from("<I", data, 0x30)[0]
        mini_cut = struct.unpack_from("<I", data, 0x38)[0]
        mini_start = struct.unpack_from("<I", data, 0x3C)[0]
        difat_start = struct.unpack_from("<I", data, 0x44)[0]
        n_difat = struct.unpack_from("<I", data, 0x48)[0]
    except struct.error:
        raise TableError("OLE2 文件头损坏")
    if ssz not in (512, 4096) or mssz <= 0 or mssz > ssz:
        raise TableError(f"无法识别的 OLE2 扇区大小（{ssz}/{mssz}）")

    def sector(sid):
        off = 512 + sid * ssz
        return data[off:off + ssz]

    per = ssz // 4
    # --- DIFAT -> FAT ---
    fat_sids = list(struct.unpack_from("<109I", data, 0x4C))
    sid = difat_start
    guard = 0
    while sid < 0xFFFFFFFE and guard <= n_difat + 8:
        sec = sector(sid)
        if len(sec) < ssz:
            break
        vals = list(struct.unpack_from("<%dI" % per, sec, 0))
        fat_sids.extend(vals[:-1])
        sid = vals[-1]
        guard += 1
    fat = []
    for fsid in fat_sids:
        if fsid >= 0xFFFFFFFE:
            continue
        if n_fat and len(fat) >= n_fat * per:
            break
        sec = sector(fsid)
        if len(sec) < ssz:
            break
        fat.extend(struct.unpack_from("<%dI" % per, sec, 0))
    if not fat:
        raise TableError("OLE2 结构异常：FAT 表为空")

    def chain(start):
        ids, sid_, seen = [], start, set()
        while sid_ < 0xFFFFFFFE and len(ids) < (1 << 20):
            if sid_ in seen:
                break
            seen.add(sid_)
            ids.append(sid_)
            sid_ = fat[sid_] if sid_ < len(fat) else 0xFFFFFFFE
        return ids

    def read_chain(start):
        out = bytearray()
        for s in chain(start):
            out += sector(s)
        return bytes(out)

    # --- 目录项 ---
    dbytes = read_chain(dir_start)
    entries = []
    for i in range(0, len(dbytes) - 127, 128):
        e = dbytes[i:i + 128]
        typ = e[0x42]
        if typ not in (1, 2, 5):
            continue
        nlen = struct.unpack_from("<H", e, 0x40)[0]
        name = ""
        if 2 <= nlen <= 64:
            name = e[:nlen - 2].decode("utf-16-le", "replace")
        entries.append({
            "name": name, "type": typ,
            "start": struct.unpack_from("<I", e, 0x74)[0],
            "size": struct.unpack_from("<Q", e, 0x78)[0],
        })
    if not entries:
        raise TableError("OLE2 结构异常：目录为空")

    root = entries[0]
    mini_data = b""
    if root["start"] < 0xFFFFFFFE:
        mini_data = read_chain(root["start"])
        if root["size"]:
            mini_data = mini_data[:int(root["size"])]

    # --- MiniFAT（小于 4096 字节的流走这里）---
    minifat = []
    if mini_start < 0xFFFFFFFE:
        mb = read_chain(mini_start)
        n = len(mb) // 4
        if n:
            minifat = list(struct.unpack_from("<%dI" % n, mb, 0))

    def read_mini(start, size):
        out, sid_, seen = bytearray(), start, set()
        while sid_ < 0xFFFFFFFE and len(out) < size:
            if sid_ in seen:
                break
            seen.add(sid_)
            off = sid_ * mssz
            out += mini_data[off:off + mssz]
            sid_ = minifat[sid_] if sid_ < len(minifat) else 0xFFFFFFFE
        return bytes(out[:size])

    streams = {}
    for e in entries:
        if e["type"] != 2:
            continue
        size = int(e["size"])
        if not size or e["start"] >= 0xFFFFFFFE:
            streams[e["name"]] = b""
        elif size < mini_cut:
            streams[e["name"]] = read_mini(e["start"], size)
        else:
            streams[e["name"]] = read_chain(e["start"])[:size]
    return streams


# ==================================================================== BIFF8
def _read_xls(path):
    with open(path, "rb") as f:
        data = f.read()
    streams = _ole_streams(data)
    wb = None
    for key in ("Workbook", "Book", "workbook", "book"):
        if streams.get(key):
            wb = streams[key]
            break
    if wb is None:
        raise TableError("这个 .xls 里找不到 Workbook 数据流，可能不是 Excel 文件")
    return _parse_biff(wb)


def _parse_biff(wb):
    # --- 记录切分 ---
    recs, pos, n = [], 0, len(wb)
    while pos + 4 <= n:
        rt, rl = struct.unpack_from("<HH", wb, pos)
        recs.append((rt, wb[pos + 4:pos + 4 + rl], pos))
        pos += 4 + rl
    if not recs:
        raise TableError("Workbook 数据流为空")

    # --- 全局信息：共享字符串 / 格式 / 工作表目录 ---
    sst, formats, xf_fmt, datemode, sheets = [], {}, [], 0, []
    i = 0
    while i < len(recs):
        rt, body, off = recs[i]
        if rt == 0x00FC:                                  # SST 共享字符串表
            segs = [body]
            j = i + 1
            while j < len(recs) and recs[j][0] == 0x003C:  # CONTINUE
                segs.append(recs[j][1])
                j += 1
            try:
                sst = _parse_sst(segs)
            except Exception:
                sst = []
        elif rt == 0x041E and len(body) >= 4:              # FORMAT 自定义格式
            try:
                formats[struct.unpack_from("<H", body, 0)[0]] = _xl_string(body, 2)[0]
            except Exception:
                pass
        elif rt == 0x00E0 and len(body) >= 4:              # XF 单元格格式索引
            xf_fmt.append(struct.unpack_from("<H", body, 2)[0])
        elif rt == 0x0022 and body:                        # DATEMODE
            datemode = body[0]
        elif rt == 0x0085:                                 # BOUNDSHEET 工作表目录
            sheets.append(_boundsheet(body, len(sheets)))
        i += 1

    name_by_pos = {s["pos"]: s["name"] for s in sheets}

    # --- 按子流切分，只收工作表 ---
    result, cur, order, state = [], None, 0, {"pending": None, "skip": 0}
    for rt, body, off in recs:
        if rt == 0x0809:                                   # BOF
            dt = struct.unpack_from("<H", body, 2)[0] if len(body) >= 4 else 0
            if dt == 0x0010:                               # 工作表子流
                order += 1
                cur = {"name": name_by_pos.get(off) or f"Sheet{order}",
                       "cells": {}}
                state["pending"] = None
            else:                                          # 全局 / 图表 / 宏
                cur = None
        elif rt == 0x000A:                                 # EOF
            if cur is not None:
                result.append(cur)
                cur = None
        elif cur is not None:
            _cell_record(rt, body, cur["cells"], sst, xf_fmt, formats,
                         datemode, state)

    out = [{"name": s["name"], "rows": _cells_to_rows(s["cells"])}
           for s in result]
    return [s for s in out if s["rows"]] or out


def _boundsheet(body, order):
    pos = struct.unpack_from("<I", body, 0)[0] if len(body) >= 4 else 0
    name = ""
    if len(body) >= 8:
        cch, grbit = body[6], body[7]
        wide = bool(grbit & 0x01)
        raw = body[8:8 + (cch * 2 if wide else cch)]
        name = _dec(raw, wide)
    return {"name": name or f"Sheet{order + 1}", "pos": pos}


def _xl_string(data, off):
    """读一个 XLUnicodeString（BIFF8），返回 (字符串, 新偏移)。"""
    if len(data) < off + 3:
        raise ValueError("字符串数据不足")
    cch = struct.unpack_from("<H", data, off)[0]
    grbit = data[off + 2]
    p = off + 3
    nrun = ext = 0
    if grbit & 0x08:                       # 富文本
        nrun = struct.unpack_from("<H", data, p)[0]
        p += 2
    if grbit & 0x04:                       # 远东扩展
        ext = struct.unpack_from("<I", data, p)[0]
        p += 4
    wide = bool(grbit & 0x01)
    nbytes = cch * (2 if wide else 1)
    s = _dec(data[p:p + nbytes], wide)
    p += nbytes + nrun * 4 + ext
    return s, p


class _SegReader:
    """跨 SST / CONTINUE 边界的读取器。

    BIFF8 的共享字符串表会拆成多条记录，如果一条字符串的字符数据正好被
    拆开，续接的记录开头会多出一个字节表示后半段是不是 16 位编码 —— 这是
    手写解析最容易错的地方，这里单独封装。
    """

    def __init__(self, segs):
        self.segs = list(segs)
        self.i = 0
        self.p = 0

    def _norm(self):
        while self.i < len(self.segs) and self.p >= len(self.segs[self.i]):
            self.i += 1
            self.p = 0

    @property
    def eof(self):
        self._norm()
        return self.i >= len(self.segs)

    def raw(self, nbytes):
        self._norm()
        if self.i >= len(self.segs):
            raise EOFError
        b = self.segs[self.i][self.p:self.p + nbytes]
        self.p += nbytes
        return b

    def byte(self):
        return self.raw(1)[0]

    def uint16(self):
        return struct.unpack("<H", self.raw(2))[0]

    def remains(self):
        self._norm()
        return len(self.segs[self.i]) - self.p if self.i < len(self.segs) else 0

    def next_block(self):
        self.i += 1
        self.p = 0
        self._norm()
        return self.i < len(self.segs)

    def skip(self, nbytes):
        while nbytes > 0:
            r = self.remains()
            if r == 0:
                if not self.next_block():
                    return
                continue
            k = min(nbytes, r)
            self.p += k
            nbytes -= k


def _parse_sst(segs):
    r = _SegReader(segs)
    struct.unpack("<I", r.raw(4))[0]              # 总条数（用不上）
    unique = struct.unpack("<I", r.raw(4))[0]     # 去重后的条数
    out = []
    for _ in range(unique):
        if r.eof:
            break
        cch = r.uint16()
        grbit = r.byte()
        nrun = ext = 0
        if grbit & 0x08:
            nrun = r.uint16()
        if grbit & 0x04:
            ext = struct.unpack("<I", r.raw(4))[0]
        wide = bool(grbit & 0x01)
        parts, left = [], cch
        while left > 0:
            rem = r.remains()
            if rem == 0:
                if not r.next_block():
                    break
                grbit = r.byte()                  # 续接块开头的编码标志字节
                wide = bool(grbit & 0x01)
                rem = r.remains()
                if rem == 0:
                    continue
            if wide:
                cnt = min(left, rem // 2)
                if cnt <= 0:
                    r.skip(rem)
                    continue
                parts.append(_dec(r.raw(cnt * 2), True))
            else:
                cnt = min(left, rem)
                parts.append(_dec(r.raw(cnt), False))
            left -= cnt
        out.append("".join(parts))
        r.skip(nrun * 4 + ext)                    # 富文本 / 扩展数据
    return out


def _rk(b4):
    """解码 RK 压缩数字。"""
    if len(b4) < 4:
        raise ValueError("RK 数据不足")
    flags = b4[0]
    if flags & 0x02:                              # 30 位整数
        v = float(struct.unpack("<i", b4)[0] >> 2)
    else:                                         # IEEE double 的高 30 位
        v = struct.unpack("<d", b"\x00\x00\x00\x00"
                          + bytes([flags & 0xFC]) + b4[1:4])[0]
    if flags & 0x01:
        v /= 100.0
    return v


def _fmt_kind_of(xf, xf_fmt, formats):
    i = int(xf) & 0x0FFF
    ifmt = xf_fmt[i] if 0 <= i < len(xf_fmt) else 0
    code = formats.get(ifmt) or _XL_FMT_BUILTIN.get(ifmt, "")
    return _fmt_kind(code)


def _cell_record(rt, body, cells, sst, xf_fmt, formats, datemode, state):
    """解析一条单元格记录，写进 cells[(行, 列)]。"""
    try:
        if rt == 0x00FD and len(body) >= 10:                  # LABELSST
            rw, cl, _xf, isst = struct.unpack_from("<HHHI", body, 0)
            cells[(rw, cl)] = sst[isst] if 0 <= isst < len(sst) else ""
        elif rt in (0x0204, 0x00D6) and len(body) >= 8:       # LABEL / RSTRING
            rw, cl = struct.unpack_from("<HH", body, 0)
            cells[(rw, cl)] = _xl_string(body, 6)[0]
        elif rt == 0x027E and len(body) >= 10:                # RK
            rw, cl, xf = struct.unpack_from("<HHH", body, 0)
            kind = _fmt_kind_of(xf, xf_fmt, formats)
            cells[(rw, cl)] = _num_to_text(_rk(body[6:10]), (kind[0], kind[1], datemode))
        elif rt == 0x0203 and len(body) >= 14:                # NUMBER
            rw, cl, xf = struct.unpack_from("<HHH", body, 0)
            kind = _fmt_kind_of(xf, xf_fmt, formats)
            v = struct.unpack_from("<d", body, 6)[0]
            cells[(rw, cl)] = _num_to_text(v, (kind[0], kind[1], datemode))
        elif rt == 0x00BD and len(body) >= 12:                # MULRK
            rw, c1 = struct.unpack_from("<HH", body, 0)
            for k in range((len(body) - 6) // 6):
                xf = struct.unpack_from("<H", body, 4 + k * 6)[0]
                kind = _fmt_kind_of(xf, xf_fmt, formats)
                cells[(rw, c1 + k)] = _num_to_text(
                    _rk(body[6 + k * 6:10 + k * 6]), (kind[0], kind[1], datemode))
        elif rt == 0x0006 and len(body) >= 20:                # FORMULA
            rw, cl, xf = struct.unpack_from("<HHH", body, 0)
            res = body[6:14]
            if res[6:8] == b"\xff\xff":                       # 字符串结果
                state["pending"] = (rw, cl)
            elif res[6:8] == b"\x00\x00" and res[0] == 0x01:  # 布尔
                state["pending"] = None
                cells[(rw, cl)] = "TRUE" if res[2] else "FALSE"
            elif res[6:8] == b"\x00\x00" and res[0] == 0x02:  # 错误值
                state["pending"] = None
                cells[(rw, cl)] = "#ERR"
            else:
                state["pending"] = None
                kind = _fmt_kind_of(xf, xf_fmt, formats)
                cells[(rw, cl)] = _num_to_text(
                    struct.unpack("<d", res)[0], (kind[0], kind[1], datemode))
        elif rt == 0x0207:                                    # STRING（公式结果）
            txt = _xl_string(body, 0)[0]
            if state.get("pending"):
                cells[state["pending"]] = txt
                state["pending"] = None
        elif rt == 0x0205 and len(body) >= 8:                 # BOOLERR
            rw, cl, _xf, val, iserr = struct.unpack_from("<HHHBB", body, 0)
            cells[(rw, cl)] = ("#ERR" if iserr
                               else ("TRUE" if val else "FALSE"))
    except Exception:
        pass                                                  # 单条坏了不影响整表


def _cells_to_rows(cells):
    if not cells:
        return []
    by_row = {}
    for (rw, cl), v in cells.items():
        by_row.setdefault(rw, {})[cl] = "" if v is None else str(v)
    rows = []
    for rw in sorted(by_row):
        rowd = by_row[rw]
        maxc = min(max(rowd), 511)
        rows.append([rowd.get(c, "") for c in range(maxc + 1)])
    return _trim(rows)


# ==================================================================== HTML 表格
class _TableExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self._t = None
        self._row = None
        self._cell = None
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t == "table":
            self._depth += 1
            if self._depth == 1:
                self._t = []
        elif t == "tr" and self._t is not None:
            self._row = []
        elif t in ("td", "th") and self._t is not None:
            self._cell = []
        elif t == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in ("td", "th") and self._cell is not None:
            if self._row is not None:
                self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif t == "tr" and self._row is not None:
            if self._t is not None:
                self._t.append(self._row)
            self._row = None
        elif t == "table":
            if self._depth == 1 and self._t:
                self.tables.append(self._t)
            self._depth = max(0, self._depth - 1)
            if self._depth == 0:
                self._t = None


def _read_html(path):
    with open(path, "rb") as f:
        text = _decode_text(f.read())
    p = _TableExtractor()
    try:
        p.feed(text)
        p.close()
    except Exception:
        pass
    tabs = [t for t in p.tables if t]
    if not tabs:
        raise TableError("文件里没有找到表格内容，可能不是表格文件")
    tabs.sort(key=lambda t: (len(t), max(len(r) for r in t)))
    return [{"name": _base_name(path), "rows": _trim(tabs[-1])}]


# ==================================================================== SpreadsheetML
def _read_spreadsheetml(path):
    with open(path, "rb") as f:
        text = _decode_text(f.read())
    try:
        root = ET.fromstring(text)
    except Exception as e:
        raise TableError(f"XML 解析失败：{e}")
    sheets, order = [], 0
    for ws in root.iter():
        if _local(ws.tag) != "worksheet":
            continue
        order += 1
        name = ws.get("{%s}Name" % _SS_NS) or f"Sheet{order}"
        rows = []
        for tbl in ws:
            if _local(tbl.tag) != "table":
                continue
            for row in tbl:
                if _local(row.tag) != "row":
                    continue
                cells = []
                for c in row:
                    if _local(c.tag) != "cell":
                        continue
                    try:
                        idx = int(c.get("{%s}Index" % _SS_NS) or 0)
                    except Exception:
                        idx = 0
                    val = ""
                    for d in c:
                        if _local(d.tag) == "data":
                            val = (d.text or "").strip()
                            break
                    if idx > 1 and idx - 1 > len(cells):
                        cells.extend([""] * (idx - 1 - len(cells)))
                    cells.append(val)
                rows.append(cells)
        sheets.append({"name": name, "rows": _trim(rows)})
    if not sheets:
        raise TableError("XML 里没有找到工作表")
    return [s for s in sheets if s["rows"]] or sheets


# ==================================================================== xlsx
def _normalize_part(target):
    if not target:
        return None
    t = str(target).replace("\\", "/").lstrip("/")
    while t.startswith("../"):
        t = t[3:]
    if not t.startswith("xl/"):
        t = "xl/" + t
    return t


def _col_index(ref):
    """'BC12' -> 54（0 基）。"""
    m = re.match(r"([A-Za-z]+)", str(ref or ""))
    if not m:
        return 0
    n = 0
    for ch in m.group(1).upper():
        n = n * 26 + (ord(ch) - 64)
    return max(0, n - 1)


def _read_xlsx(path):
    if not zipfile.is_zipfile(path):
        raise TableError("这个 .xlsx 不是有效的 ZIP 容器（文件可能已损坏）")
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if "xl/workbook.xml" not in names:
            raise TableError("这个文件里找不到 xl/workbook.xml，可能不是 xlsx")
        shared = _xlsx_shared_strings(z, names)
        styles = _xlsx_styles(z, names)
        rels = {}
        if "xl/_rels/workbook.xml.rels" in names:
            try:
                for rel in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")):
                    rels[rel.get("Id")] = rel.get("Target")
            except Exception:
                pass
        try:
            wbroot = ET.fromstring(z.read("xl/workbook.xml"))
        except Exception as e:
            raise TableError(f"workbook.xml 解析失败：{e}")
        datemode = 0
        for el in wbroot.iter():
            if _local(el.tag) == "workbookPr":
                v = str(el.get("date1904") or el.get("dateCompatibility") or "")
                if v.lower() in ("1", "true"):
                    datemode = 1
                break
        parts = sorted(n for n in names
                       if n.startswith("xl/worksheets/") and n.endswith(".xml"))
        sheets, idx = [], 0
        for sh in wbroot.iter():
            if _local(sh.tag) != "sheet":
                continue
            idx += 1
            name = sh.get("name") or f"Sheet{idx}"
            part = _normalize_part(rels.get(sh.get(_ODOC_R_ID))) or ""
            if part not in names:
                part = parts[idx - 1] if len(parts) >= idx else ""
            if not part:
                continue
            try:
                rows = _xlsx_rows(z.read(part), shared, styles, datemode)
            except Exception:
                continue
            sheets.append({"name": name, "rows": rows})
    non_empty = [s for s in sheets if s["rows"]]
    if not non_empty and not sheets:
        raise TableError("这个 xlsx 里没有工作表")
    return non_empty or sheets


def _xlsx_shared_strings(z, names):
    if "xl/sharedStrings.xml" not in names:
        return []
    out = []
    try:
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    except Exception:
        return out
    for si in root:
        if _local(si.tag) != "si":
            continue
        out.append("".join(x.text or "" for x in si.iter()
                           if _local(x.tag) == "t"))
    return out


def _xlsx_styles(z, names):
    """cellXfs 索引 -> (是否日期, 是否含时间)。"""
    out = []
    if "xl/styles.xml" not in names:
        return out
    try:
        root = ET.fromstring(z.read("xl/styles.xml"))
    except Exception:
        return out
    custom = {}
    for nf in root.iter():
        if _local(nf.tag) == "numFmt":
            try:
                custom[int(nf.get("numFmtId"))] = nf.get("formatCode") or ""
            except Exception:
                pass
    for xfs in root.iter():
        if _local(xfs.tag) != "cellXfs":
            continue
        for xf in xfs:
            try:
                nid = int(xf.get("numFmtId") or 0)
            except Exception:
                nid = 0
            out.append(_fmt_kind(custom.get(nid) or _XL_FMT_BUILTIN.get(nid, "")))
    return out


def _xlsx_rows(raw, shared, styles, datemode):
    try:
        root = ET.fromstring(raw)
    except Exception as e:
        raise TableError(f"工作表 XML 解析失败：{e}")
    by_row = {}
    for row in root.iter():
        if _local(row.tag) != "row":
            continue
        try:
            rw = int(row.get("r")) - 1 if row.get("r") else len(by_row)
        except Exception:
            rw = len(by_row)
        cells, cidx = {}, 0
        for c in row:
            if _local(c.tag) != "c":
                continue
            ci = _col_index(c.get("r")) if c.get("r") else cidx
            cidx = ci + 1
            t = c.get("t") or "n"
            s = c.get("s")
            kind = (False, False)
            if s and s.isdigit() and int(s) < len(styles):
                kind = styles[int(s)]
            if t == "inlineStr":
                cells[ci] = "".join(x.text or "" for x in c.iter()
                                    if _local(x.tag) == "t")
                continue
            v = None
            for ch in c:
                if _local(ch.tag) == "v":
                    v = ch.text
                    break
            if v is None:
                continue
            if t == "s":
                try:
                    cells[ci] = shared[int(v)]
                except Exception:
                    cells[ci] = ""
            elif t == "str":
                cells[ci] = v or ""
            elif t == "b":
                cells[ci] = "TRUE" if str(v).strip() in ("1", "true", "TRUE") else "FALSE"
            elif t == "e":
                cells[ci] = str(v)
            else:
                try:
                    num = float(v)
                except Exception:
                    cells[ci] = v or ""
                else:
                    cells[ci] = _num_to_text(num, (kind[0], kind[1], datemode))
        by_row[rw] = cells
    rows = []
    for rw in sorted(by_row):
        rowd = by_row[rw]
        if not rowd:
            rows.append([])
            continue
        maxc = min(max(rowd), 511)
        rows.append([rowd.get(c, "") for c in range(maxc + 1)])
    return _trim(rows)
