"""生成钢琴墙 App 的启动图标：黑白琴键 + L 型转角。"""
import os
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZES = {"mipmap-mdpi": 48, "mipmap-hdpi": 72, "mipmap-xhdpi": 96,
         "mipmap-xxhdpi": 144, "mipmap-xxxhdpi": 192}
MASTER = 768


def rounded(size, radius, color):
    img = Image.new("L", (size, size), 0)
    ImageDraw.Draw(img).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return img


def main():
    s = MASTER
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # 背景：深色渐变 + 圆角
    bg = Image.new("RGB", (1, s))
    d = ImageDraw.Draw(bg)
    top, bot = (16, 22, 32), (10, 13, 19)
    for y in range(s):
        t = y / (s - 1)
        d.point((0, y), fill=(int(top[0] + (bot[0] - top[0]) * t),
                              int(top[1] + (bot[1] - top[1]) * t),
                              int(top[2] + (bot[2] - top[2]) * t)))
    bg = bg.resize((s, s), Image.BILINEAR)
    out.paste(bg, (0, 0), rounded(s, int(s * 0.22), 255))

    dr = ImageDraw.Draw(out)
    # 白键条（斜向排布，像透视中的琴键墙）
    key_w = s * 0.095
    gap = s * 0.018
    x = s * 0.10
    y0, y1 = s * 0.22, s * 0.78
    i = 0
    while x + key_w < s * 0.92:
        dr.rectangle([x, y0, x + key_w, y1], fill=(244, 243, 239, 255))
        # 黑键
        if i % 7 in (0, 1, 3, 4, 5):
            bx = x + key_w - key_w * 0.29 + gap * 0.5
            dr.rectangle([bx, y0, bx + key_w * 0.58, y0 + (y1 - y0) * 0.62],
                         fill=(16, 16, 16, 255))
        x += key_w + gap
        i += 1

    # 底部：黑色踢脚带
    dr.rectangle([s * 0.10, y1 - s * 0.03, s * 0.90, y1], fill=(16, 16, 16, 255))

    for folder, px in SIZES.items():
        target = os.path.join(ROOT, "res", folder)
        os.makedirs(target, exist_ok=True)
        out.resize((px, px), Image.LANCZOS).save(os.path.join(target, "ic_launcher.png"))
        print("wrote", os.path.join(target, "ic_launcher.png"))


if __name__ == "__main__":
    main()
