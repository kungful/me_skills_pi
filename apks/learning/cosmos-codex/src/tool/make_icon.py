import os
from PIL import Image, ImageDraw, ImageFont

OUT = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}
FONT = "C:/Windows/Fonts/msyhbd.ttc"
if not os.path.exists(FONT):
    FONT = "C:/Windows/Fonts/msyh.ttc"

BASE = r"C:/Users/hua/Documents/备份代码/CosmosCodex/app/res"


def make(size):
    S = size * 4
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 深空底：径向渐变
    for i in range(S // 2, 0, -1):
        t = i / (S / 2)
        r = int(10 + 26 * (1 - t))
        g = int(16 + 40 * (1 - t))
        b = int(30 + 70 * (1 - t))
        d.ellipse([S / 2 - i, S / 2 - i, S / 2 + i, S / 2 + i], fill=(r, g, b, 255))

    # 星点
    pts = [(0.18, 0.22), (0.78, 0.16), (0.85, 0.62), (0.14, 0.74), (0.5, 0.08), (0.62, 0.88), (0.3, 0.5)]
    for k, (x, y) in enumerate(pts):
        rr = S * (0.012 if k % 2 else 0.007)
        d.ellipse([S * x - rr, S * y - rr, S * x + rr, S * y + rr], fill=(255, 236, 190, 210))

    # 金色轨道环
    pad = S * 0.11
    d.ellipse([pad, pad, S - pad, S - pad], outline=(212, 168, 83, 255), width=max(2, int(S * 0.022)))
    pad2 = S * 0.185
    d.ellipse([pad2, S * 0.30, S - pad2, S * 0.70], outline=(212, 168, 83, 120), width=max(1, int(S * 0.012)))

    # 中心「理」字
    fs = int(S * 0.52)
    font = ImageFont.truetype(FONT, fs)
    txt = "理"
    box = d.textbbox((0, 0), txt, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    d.text((S / 2 - tw / 2 - box[0], S / 2 - th / 2 - box[1]), txt, font=font, fill=(245, 220, 150, 255))

    return img.resize((size, size), Image.LANCZOS)


for folder, size in OUT.items():
    p = os.path.join(BASE, folder)
    os.makedirs(p, exist_ok=True)
    img = make(size)
    img.save(os.path.join(p, "ic_launcher.png"))
    print("wrote", os.path.join(p, "ic_launcher.png"), size)

# 启动图用的中等尺寸
os.makedirs(os.path.join(BASE, "mipmap-xxhdpi"), exist_ok=True)
make(192).save(os.path.join(BASE, "mipmap-xxhdpi", "ic_launcher_round.png"))
print("done")
