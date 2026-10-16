"""Generates the launcher icon set for PaintBox-Android (no external deps beyond Pillow)."""
import os
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZES = {"mipmap-mdpi": 48, "mipmap-hdpi": 72, "mipmap-xhdpi": 96,
         "mipmap-xxhdpi": 144, "mipmap-xxxhdpi": 192}
MASTER = 768


def gradient(size, top, bottom):
    img = Image.new("RGB", (1, size))
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / max(1, size - 1)
        d.point((0, y), fill=(int(top[0] + (bottom[0] - top[0]) * t),
                              int(top[1] + (bottom[1] - top[1]) * t),
                              int(top[2] + (bottom[2] - top[2]) * t)))
    return img.resize((size, size), Image.BILINEAR)


def star(d, cx, cy, r, fill, thin=0.30):
    """Four-point sparkle."""
    pts = [(cx, cy - r), (cx + r * thin, cy - r * thin), (cx + r, cy),
           (cx + r * thin, cy + r * thin), (cx, cy + r),
           (cx - r * thin, cy + r * thin), (cx - r, cy),
           (cx - r * thin, cy - r * thin)]
    d.polygon(pts, fill=fill)


def main():
    s = MASTER
    img = gradient(s, (18, 32, 66), (47, 111, 235)).convert("RGBA")

    # rounded mask
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=255)
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)

    d = ImageDraw.Draw(out)
    # GPU board hint
    r = int(s * 0.05)
    box = [int(s * 0.20), int(s * 0.60), int(s * 0.80), int(s * 0.80)]
    d.rounded_rectangle(box, radius=r, outline=(255, 255, 255, 235), width=int(s * 0.030))
    for i in range(4):
        x = int(s * 0.28 + i * s * 0.13)
        d.line([(x, int(s * 0.80)), (x, int(s * 0.86))], fill=(255, 255, 255, 235),
               width=int(s * 0.022))
    # sparkles
    star(d, int(s * 0.50), int(s * 0.35), int(s * 0.22), (255, 255, 255, 255))
    star(d, int(s * 0.75), int(s * 0.22), int(s * 0.10), (255, 255, 255, 220))
    star(d, int(s * 0.26), int(s * 0.30), int(s * 0.075), (255, 255, 255, 200))

    for folder, px in SIZES.items():
        target = os.path.join(ROOT, "res", folder)
        os.makedirs(target, exist_ok=True)
        out.resize((px, px), Image.LANCZOS).save(os.path.join(target, "ic_launcher.png"))
        print("wrote", os.path.join(target, "ic_launcher.png"))


if __name__ == "__main__":
    main()
