# -*- coding: utf-8 -*-
"""商城英文资料的中文本地化。

为什么需要翻译
    程序按 C 号查的是嘉立创国际站（jlcpcb.com）的 SMT 元件库接口。
    这个接口除了 erpComponentName（内部 ERP 名称）之外几乎全是英文：

        describe          参数串，如 "12V 50mA Black Gull Wing SPST Surface Mount"
        componentTypeEn   元件类型，如 "Tactile Switches"
        attributes[]      属性表，属性名和枚举值都是英文

    而 erpComponentName 已经被用作「名称」（它本身是中文），于是「详细
    描述」直接取 describe 就只剩英文了。不是程序取错字段，是接口本身
    只有英文 —— 国内站（szlcsc.com）的中文接口有 ACL 签名校验，程序
    取不到，所以在这里做本地化。

怎么翻译
    元器件英文术语是个封闭集合（安装方式、端子形式、材质、电气参数……），
    本地词典足够覆盖。好处是离线可用、结果稳定，而且只翻术语，
    12V / 100nF / 4.5mm 这类数值一律原样保留，不会把型号翻坏。

想加词
    直接往下面三张表里加；也可以写 data/i18n_custom.json：

        {"属性名": {"Voltage Rating": "额定电压"},
         "值":     {"Gull Wing": "鸥翼引脚"},
         "类型":   {"Tactile Switches": "轻触开关"}}

    程序启动时自动合并，重启生效。
"""
import json
import os
import re

from . import config


# ------------------------------------------------------------ 属性名对照
ATTR_CN = {
    # 电气参数
    "operating temperature": "工作温度",
    "storage temperature": "存储温度",
    "temperature coefficient": "温度系数",
    "voltage rating": "额定电压",
    "rated voltage": "额定电压",
    "voltage - supply": "供电电压",
    "voltage-supply": "供电电压",
    "voltage - supply (max)": "供电电压上限",
    "voltage-supply(max)": "供电电压上限",
    "supply voltage": "供电电压",
    "breakdown voltage": "击穿电压",
    "forward voltage": "正向压降",
    "reverse voltage": "反向耐压",
    "input voltage": "输入电压",
    "output voltage": "输出电压",
    "current rating": "额定电流",
    "rated current": "额定电流",
    "contact current": "触点电流",
    "forward current": "正向电流",
    "output current": "输出电流",
    "supply current (iq)": "静态电流(Iq)",
    "quiescent current": "静态电流",
    "current - max": "最大电流",
    "power(watts)": "功率(W)",
    "rated power": "额定功率",
    "power": "功率",
    "frequency": "频率",
    "tolerance": "容差/精度",
    "resistance": "阻值",
    "capacitance": "容值",
    "inductance": "感值",
    "impedance": "阻抗",
    "esr": "等效串联电阻(ESR)",
    "ripple current": "纹波电流",
    "insulation resistance": "绝缘电阻",
    "contact resistance": "接触电阻",
    "dielectric strength": "耐压",
    "withstand voltage": "耐压",
    "saturation current": "饱和电流",
    # 封装 / 结构
    "package/case": "封装",
    "package": "封装",
    "encapsulation": "封装",
    "mounting type": "安装方式",
    "mounting": "安装方式",
    "termination style": "端子形式",
    "termination": "端子",
    "number of pins": "引脚数",
    "number of positions": "位数",
    "number of contacts": "触点数",
    "number of rows": "排数",
    "pitch": "间距",
    "gender": "极性",
    "connector type": "连接器类型",
    # 尺寸
    "length": "长度",
    "width": "宽度",
    "height": "高度",
    "switch height": "开关高度",
    "thickness": "厚度",
    "size": "尺寸",
    "dimensions": "尺寸",
    "outer diameter": "外径",
    "inner diameter": "内径",
    "diameter": "直径",
    # 开关 / 按键
    "circuit": "电路",
    "contact form": "触点形式",
    "switch function": "开关功能",
    "switch type": "开关类型",
    "actuator style": "按键形式",
    "actuator/cap color": "按键颜色",
    "actuator": "按键",
    "operating force": "操作力",
    "life": "寿命",
    "operating life": "使用寿命",
    "mechanical life": "机械寿命",
    "electrical life": "电气寿命",
    "with lamp": "指示灯",
    "with bracket": "支架",
    "with led": "带 LED",
    "illumination": "照明",
    "illumination color": "灯光颜色",
    # 颜色 / 材质
    "color": "颜色",
    "colour": "颜色",
    "material": "材质",
    "contact material": "触点材质",
    "housing material": "外壳材质",
    "body material": "本体材质",
    "plating": "镀层",
    # 半导体 / 集成电路
    "type": "类型",
    "features": "特性",
    "function": "功能",
    "interface": "接口",
    "protocol": "协议",
    "data rate": "数据速率",
    "channels": "通道数",
    "number of channels": "通道数",
    "resolution": "分辨率",
    "accuracy": "精度",
    "cpu core": "内核",
    "core size": "内核位数",
    "cpu maximum speed": "最高主频",
    "program storage size": "程序存储容量",
    "program memory type": "程序存储器类型",
    "ram size": "RAM 容量",
    "eeprom": "EEPROM 容量",
    "flash size": "Flash 容量",
    "adc (bit)": "ADC 位数",
    "dac (bit)": "DAC 位数",
    "oscillator type": "振荡器类型",
    "number of i/o": "I/O 数量",
    "gain bandwidth product (gbp)": "增益带宽积",
    "slew rate": "压摆率",
    "input offset voltage": "输入失调电压",
    "output type": "输出类型",
    "logic family": "逻辑系列",
    "gate type": "门类型",
    "number of circuits": "电路数",
    "memory size": "存储容量",
    "memory type": "存储器类型",
    "supply current - max": "最大供电电流",
    "voltage - output": "输出电压",
    # 电池管理
    "type of battery": "电池类型",
    "charge current - max": "最大充电电流",
    "charging saturation voltage": "充电饱和电压",
    "battery temperature detection": "电池温度检测",
    "the chip type": "芯片类型",
    "balance current": "均衡电流",
    "end-off voltage": "终止电压",
    "0v battery charge": "0V 电池充电",
    "number of cells": "电池节数",
    # 其它
    "rohs": "RoHS",
    "lead free": "无铅",
    "halogen free": "无卤",
    "operating humidity": "工作湿度",
    "thread size": "螺纹规格",
    "screw thread": "螺纹规格",
    "head type": "头部类型",
    "drive type": "驱动方式",
    "standoff height": "支撑高度",
    "spacer length": "隔离柱长度",
}


# ------------------------------------------------------------ 枚举值对照
VALUE_CN = {
    # 安装 / 封装方式
    "surface mount": "贴片",
    "surface mount,vertical": "贴片立式",
    "surface mount, horizontal": "贴片卧式",
    "smd": "贴片",
    "smt": "贴片",
    "through hole": "插件",
    "through-hole": "插件",
    "through hole,vertical": "插件立式",
    "dip": "双列直插",
    "radial": "径向引线",
    "radial lead": "径向引线",
    "axial": "轴向引线",
    "vertical": "立式",
    "horizontal": "卧式",
    "right angle": "弯角",
    "straight": "直式",
    "panel mount": "面板安装",
    "screw mount": "螺纹安装",
    "solder": "焊接",
    "crimp": "压接",
    "press-fit": "免焊压接",
    "quick connect": "快接端子",
    "wire wrap": "绕线",
    # 端子 / 引脚形式
    "gull wing": "鸥翼引脚",
    "j-lead": "J 形引脚",
    "solder tab": "焊片",
    "pc pin": "插件引脚",
    "pc pin,straight": "直式插件引脚",
    "pin": "引脚",
    "ball": "球栅",
    "butt": "对焊",
    "land grid array": "平面栅格阵列",
    # 形状 / 外观
    "round button": "圆形按键",
    "square button": "方形按键",
    "rectangular": "长方形",
    "round": "圆形",
    "square": "方形",
    "cylindrical": "圆柱形",
    "flat": "平面",
    "dome": "圆顶",
    "spherical": "球形",
    "tactile": "轻触式",
    # 颜色
    "black": "黑色",
    "white": "白色",
    "red": "红色",
    "blue": "蓝色",
    "green": "绿色",
    "yellow": "黄色",
    "grey": "灰色",
    "gray": "灰色",
    "silver": "银色",
    "gold": "金色",
    "transparent": "透明",
    "natural": "本色",
    "beige": "米色",
    "orange": "橙色",
    "purple": "紫色",
    "brown": "棕色",
    # 材质
    "stainless steel": "不锈钢",
    "steel": "钢",
    "copper": "铜",
    "brass": "黄铜",
    "phosphor bronze": "磷青铜",
    "beryllium copper": "铍铜",
    "nylon": "尼龙",
    "pa66": "尼龙 PA66",
    "pbt": "PBT",
    "silicone": "硅胶",
    "rubber": "橡胶",
    "aluminum": "铝",
    "aluminium": "铝",
    "ceramic": "陶瓷",
    "polyester": "聚酯",
    "polypropylene": "聚丙烯",
    "polycarbonate": "聚碳酸酯",
    "pet": "PET",
    "pvc": "PVC",
    "abs": "ABS",
    "lcp": "LCP",
    "fr-4": "FR-4",
    "metal": "金属",
    "plastic": "塑料",
    # 开关电路 / 动作
    "spst": "单刀单掷",
    "spdt": "单刀双掷",
    "dpst": "双刀单掷",
    "dpdt": "双刀双掷",
    "sp3t": "单刀三掷",
    "momentary": "自复位",
    "latching": "自锁",
    "normally open": "常开",
    "normally closed": "常闭",
    "on-off": "通-断",
    "on-on": "通-通",
    # 电池 / 电源
    "lithium battery": "锂电池",
    "lithium-ion": "锂离子",
    "li-ion": "锂离子",
    "lifepo4": "磷酸铁锂",
    "constant current charging": "恒流充电",
    "constant voltage charging": "恒压充电",
    "trickle charging": "涓流充电",
    "automatic recharge": "自动再充",
    "charge termination": "充电终止",
    "programmable charging current": "可编程充电电流",
    "soft-start": "软启动",
    "under-voltage lockout": "欠压锁定",
    "over-current protection": "过流保护",
    "over-temperature protection": "过温保护",
    "short circuit protection": "短路保护",
    # 电阻 / 电容类型
    "thick film resistor": "厚膜电阻",
    "thin film resistor": "薄膜电阻",
    "wirewound": "绕线",
    "metal film": "金属膜",
    "carbon film": "碳膜",
    "chip resistor": "贴片电阻",
    "ceramic capacitor": "陶瓷电容",
    "electrolytic": "电解",
    "tantalum": "钽",
    "multilayer ceramic": "多层陶瓷",
    "x7r": "X7R",
    "x5r": "X5R",
    "c0g": "C0G",
    "np0": "NP0",
    # 是 / 否（单字的 No / Yes 由 tr_value 结合属性名判断，见 _CIRCUIT_HINT）
    "support": "支持",
    "supported": "支持",
    "not support": "不支持",
    "unsupported": "不支持",
    "charging ic": "充电 IC",
    "power management": "电源管理",
    "protection ic": "保护 IC",
    "motor driver": "电机驱动",
    "gate driver": "栅极驱动",
    "built-in": "内置",
    "built in": "内置",
    "external": "外置",
    "without bracket": "不带支架",
    "with bracket": "带支架",
    "without lamp": "无灯",
    "with lamp": "带灯",
    # 通用状态
    "rohs": "RoHS",
    "lead free": "无铅",
    "halogen free": "无卤",
    "shielded": "屏蔽",
    "unshielded": "非屏蔽",
    "open": "断开",
    "closed": "闭合",
    "active": "有源",
    "passive": "无源",
    "cycles": "次",
    "cycle": "次",
}

# 值为这些内容时视为空（商城的占位符）
_PLACEHOLDER = {"", "-", "--", "---", "n/a", "na", "null", "none", "无", "未知", "/"}

# 属性名里含这些词时，NO/NC 按电路语义翻（常开/常闭），否则按有无翻（无/有）
_CIRCUIT_HINT = ("circuit", "contact form", "switch function", "switch type",
                 "contact type", "contact arrangement")


# ------------------------------------------------------------ 元件类型对照
TYPE_RULES = [
    ("tactile switch", "轻触开关"),
    ("key switch", "按键开关"),
    ("slide switch", "拨动开关"),
    ("toggle switch", "钮子开关"),
    ("rocker switch", "船型开关"),
    ("dip switch", "拨码开关"),
    ("limit switch", "限位开关"),
    ("chip resistor", "贴片电阻"),
    ("resistor network", "排阻"),
    ("wirewound resistor", "绕线电阻"),
    ("potentiometer", "电位器"),
    ("multilayer ceramic", "多层陶瓷电容(MLCC)"),
    ("ceramic capacitor", "陶瓷电容"),
    ("aluminum electrolytic", "铝电解电容"),
    ("aluminium electrolytic", "铝电解电容"),
    ("tantalum capacitor", "钽电容"),
    ("film capacitor", "薄膜电容"),
    ("super capacitor", "超级电容"),
    ("microcontroller", "单片机/微控制器"),
    ("battery management", "电池管理芯片"),
    ("voltage regulator", "稳压器"),
    ("linear regulator", "线性稳压器"),
    ("switching regulator", "开关稳压器"),
    (" dc-dc", "DC-DC 转换器"),
    ("dc-dc", "DC-DC 转换器"),
    ("ldo", "线性稳压器(LDO)"),
    ("mosfet", "MOSFET"),
    ("bipolar transistor", "三极管"),
    ("schottky", "肖特基二极管"),
    ("zener", "稳压二极管"),
    ("tvs", "TVS 管"),
    ("esd", "ESD 保护管"),
    ("rectifier", "整流二极管"),
    ("diode", "二极管"),
    ("light emitting", "发光二极管(LED)"),
    ("led", "发光二极管(LED)"),
    ("crystal oscillator", "有源晶振"),
    ("crystal", "晶振"),
    ("oscillator", "振荡器"),
    ("resonator", "陶瓷谐振器"),
    ("ferrite bead", "磁珠"),
    ("common mode", "共模电感"),
    ("power inductor", "功率电感"),
    ("inductor", "电感"),
    ("connector", "连接器"),
    ("header", "排针/排母"),
    ("terminal", "端子"),
    ("socket", "插座"),
    ("relay", "继电器"),
    ("fuse", "保险丝"),
    ("sensor", "传感器"),
    ("optocoupler", "光耦"),
    ("shift register", "移位寄存器"),
    ("gate driver", "栅极驱动"),
    ("operational amplifier", "运算放大器"),
    ("amplifier", "放大器"),
    ("comparator", "比较器"),
    ("logic", "逻辑芯片"),
    ("memory", "存储器"),
    ("eeprom", "EEPROM 存储器"),
    ("flash", "Flash 存储器"),
    ("interface", "接口芯片"),
    ("microprocessor", "微处理器"),
    ("module", "模块"),
    ("hardware", "结构件"),
    ("screw", "螺丝"),
    ("standoff", "支撑柱"),
    ("spacer", "隔离柱"),
    ("switch", "开关"),
    ("capacitor", "电容"),
]

# 尺寸类属性：单位一致时合并成 4.5×4.5×4.5mm
_DIM_KEYS = ("length", "width", "height", "switch height", "thickness")

# 「参数值」列优先取这些属性，比取前几个更有用
_VALUE_KEYS = (
    "resistance", "capacitance", "inductance", "impedance",
    "voltage rating", "voltage - supply", "supply voltage",
    "tolerance", "power(watts)", "power", "frequency",
    "forward voltage", "output voltage", "charge current - max",
    "cpu maximum speed", "program storage size",
)

_custom_loaded = False
_type_sorted = []


# ------------------------------------------------------------ 内部
def _load_custom():
    """合并 data/i18n_custom.json 里的自定义词条（用户自己加的词）。"""
    global _custom_loaded
    if _custom_loaded:
        return
    _custom_loaded = True

    path = os.path.join(config.DATA_DIR, "i18n_custom.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for section, table in (("属性名", ATTR_CN), ("值", VALUE_CN)):
                for k, v in (data.get(section) or {}).items():
                    if k and v:
                        table[str(k).strip().lower()] = str(v).strip()
            extra = data.get("类型") or {}
            for k, v in extra.items():
                if k and v:
                    key = str(k).strip().lower()
                    if not any(key == r[0] for r in TYPE_RULES):
                        TYPE_RULES.append((key, str(v).strip()))
        except Exception:
            pass

    global _type_sorted
    _type_sorted = sorted(TYPE_RULES, key=lambda kv: -len(kv[0]))


def _term_sorted():
    # 长词优先，避免 "No" 抢在 "Normally Open" 前面替换
    return sorted(VALUE_CN.items(), key=lambda kv: -len(kv[0]))


def _sub_terms(text):
    """把串里的英文术语替换成中文（不动数字和单位）。"""
    for en, cn in _term_sorted():
        if en in text.lower():
            text = re.sub(r"(?<![A-Za-z0-9])" + re.escape(en) + r"(?![A-Za-z0-9])",
                          cn, text, flags=re.I)
    return text


def _cn_number(text):
    """100,000 次 -> 10万次（只对中文量词前的数字做，避免误伤参数值）。"""
    def rep(m):
        n = int(m.group(1).replace(",", ""))
        if n < 10000 or n % 1000:
            return m.group(0)
        w = n / 10000
        w = int(w) if w == int(w) else round(w, 1)
        return f"{w}万{m.group(2)}"
    return re.sub(r"(\d{1,3}(?:,\d{3})+|\d{4,})\s*(次|万次|小时|圈)", rep, text)


# ------------------------------------------------------------ 对外
def tr_attr(name):
    """属性名 -> 中文。"""
    if not name:
        return ""
    _load_custom()
    s = str(name).strip()
    return ATTR_CN.get(s.lower(), s)


def tr_value(value, attr_name=""):
    """属性值 -> 中文。数值和单位原样保留。

    attr_name 用来消歧："No" 在 With Lamp 这类布尔属性里是「无」，
    在 Circuit 这类电路属性里才是「常开」。
    """
    if value is None:
        return ""
    _load_custom()
    s = str(value).strip()
    low = s.lower()
    if low in _PLACEHOLDER:
        return ""

    nm = str(attr_name or "").strip().lower()
    is_circuit = any(k in nm for k in _CIRCUIT_HINT)
    if low in ("no", "n", "yes", "y"):
        if is_circuit:
            return "常开" if low in ("no", "n") else "常闭"
        return "有" if low in ("yes", "y") else "无"
    if low == "nc" and not is_circuit:
        return "无"

    hit = VALUE_CN.get(low)
    if hit:
        return hit

    # 组合值（Surface Mount,Vertical / 18V/1A）：拆开分别翻，再合起来
    # 千分位逗号（100,000）不能当分隔符，用前后看数字的规则排除
    segs = [x.strip() for x in re.split(r"(?<!\d)[,;、]|[,;、](?!\d)", s) if x.strip()]
    if len(segs) > 1:
        out = []
        for seg in segs:
            one = VALUE_CN.get(seg.lower()) or _sub_terms(seg)
            if one and one not in out:
                out.append(one)
        return "、".join(out)

    return _cn_number(_sub_terms(s))


def tr_type(type_en):
    """元件类型 -> 中文（Tactile Switches -> 轻触开关）。"""
    if not type_en:
        return ""
    _load_custom()
    low = str(type_en).strip().lower()
    for key, cn in _type_sorted:
        if key in low:
            return cn
    return str(type_en).strip()


def localize_desc(attrs, describe="", type_en="", limit=320):
    """把商城的英文属性表整理成中文详细描述。

    attrs      接口的 attributes 列表
    describe   接口的 describe 英文参数串（属性表为空时的兜底）
    type_en    componentTypeEn，用于开头标注元件类型
    """
    _load_custom()

    items = []          # (原英文属性名, 中文属性名, 中文值)
    for a in (attrs or []):
        try:
            raw_name = str(a.get("attribute_name_en") or "").strip()
            val = tr_value(a.get("attribute_value_name"), raw_name)
        except Exception:
            continue
        if not val:
            continue
        items.append([raw_name, tr_attr(raw_name) or raw_name, val])

    # 尺寸类属性：单位一致时合并，如 长度/宽度/高度 都是 4.5mm -> 4.5×4.5×4.5mm
    merged = None
    dim_items = [it for it in items if it[0].lower() in _DIM_KEYS]
    if len(dim_items) >= 2:
        units, nums = set(), []
        for it in dim_items:
            m = re.fullmatch(r"([\d.]+)\s*([A-Za-z%]+)", it[2].strip())
            if not m:
                units.clear()
                break
            units.add(m.group(2))
            nums.append(m.group(1))
        if len(units) == 1:
            merged = "×".join(nums) + units.pop()

    out = []
    for it in items:
        if merged and it in dim_items:
            if not any(k == "尺寸" for k, _ in out):
                out.append(("尺寸", merged))
            continue
        out.append((it[1], it[2]))

    if not out and describe:
        # 属性表为空时退回翻译 describe 参数串（键留空，只输出值）
        out = [("", _cn_number(_sub_terms(str(describe).strip())))]

    # 逐条拼接，超长就停在完整条目上
    lines = []
    t = tr_type(type_en)
    if t and t != type_en:
        lines.append("元件类型：" + t)
    if out:
        parts, used = [], 0
        for k, v in out:
            piece = f"{k}：{v}" if k and k != v else str(v)
            if used + len(piece) > limit and parts:
                parts.append("…")
                break
            parts.append(piece)
            used += len(piece) + 1
        lines.append("参数：" + "｜".join(parts))
    return "\n".join(lines)


def pick_value_text(attrs, fallback="", limit=4):
    """给「参数值」列挑几个关键参数（阻值/容值/耐压/精度优先）。"""
    keyed = []
    for a in (attrs or []):
        try:
            nm = str(a.get("attribute_name_en") or "").strip().lower()
            val = tr_value(a.get("attribute_value_name"), nm)
        except Exception:
            continue
        if val:
            keyed.append((nm, val))
    prim = [v for nm, v in keyed if nm in _VALUE_KEYS]
    rest = [v for nm, v in keyed if nm not in _VALUE_KEYS]
    picked, seen = [], []
    for v in prim + rest:
        if v not in seen:
            seen.append(v)
            picked.append(v)
        if len(picked) >= limit:
            break
    text = " ".join(picked)
    return (text[:60] if text else fallback)
