# -*- coding: utf-8 -*-
"""生成程序图标 assets/app.ico。

图标用 Pillow 按几何比例画出来（不依赖美术素材），
每个尺寸都先在 4 倍画布上绘制再缩小，小尺寸下也能保持清晰。

用法：  D:\\python\\python.exe tools\\make_icon.py
"""
import os

from PIL import Image, ImageDraw

SIZES = [16, 24, 32, 48, 64, 128, 256]

BG_TOP = (59, 130, 246)      # 蓝
BG_BOTTOM = (29, 78, 216)    # 深蓝
BODY = (255, 255, 255)
NOTCH = (37, 99, 235)


def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def paint(size):
    """按目标尺寸画一张图（内部 4 倍超采样，缩小时更平滑）。"""
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 1) 背景：圆角方块 + 竖向渐变
    r = int(s * 0.22)
    bg = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bg)
    for y in range(s):
        bd.line([(0, y), (s, y)], fill=_lerp(BG_TOP, BG_BOTTOM, y / max(1, s - 1)))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=r, fill=255)
    img.paste(bg, (0, 0), mask)
    d = ImageDraw.Draw(img)

    # 2) 芯片本体（白色圆角矩形）
    bw, bh = s * 0.42, s * 0.42
    cx, cy = s / 2, s / 2
    body = [cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2]
    _rounded(d, body, int(s * 0.06), BODY)

    # 3) 引脚：左右各 4 根
    pin_len = s * 0.075
    pin_h = max(1, int(s * 0.035))
    gap = bh / 4.0
    for i in range(4):
        y = cy - bh / 2 + gap * (i + 0.5)
        d.rectangle([body[0] - pin_len, y - pin_h / 2,
                     body[0] + s * 0.01, y + pin_h / 2], fill=BODY)
        d.rectangle([body[2] - s * 0.01, y - pin_h / 2,
                     body[2] + pin_len, y + pin_h / 2], fill=BODY)

    # 4) 芯片上的半圆缺口（DIP 封装的定位点）
    nr = s * 0.055
    d.ellipse([cx - nr, body[1] - nr * 0.85, cx + nr, body[1] + nr * 1.15],
              fill=NOTCH)

    return img.resize((size, size), Image.LANCZOS)


def write_ico(out, frames):
    frames[-1].save(out, format="ICO",
                    sizes=[(n, n) for n in SIZES],
                    append_images=frames[:-1])


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(root, "assets")
    os.makedirs(out_dir, exist_ok=True)

    ico = os.path.join(out_dir, "app.ico")
    write_ico(ico, [paint(n) for n in SIZES])
    print("图标已生成：", ico)
    print("包含尺寸：", ", ".join(f"{n}x{n}" for n in SIZES))


if __name__ == "__main__":
    main()
