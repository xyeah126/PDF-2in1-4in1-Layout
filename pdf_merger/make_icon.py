"""生成 app.ico：品牌紫底 + 2×2 白页，象征多页合并为一。

运行：python make_icon.py  →  产出 app.ico
"""
from PIL import Image, ImageDraw

BRAND = (75, 63, 227, 255)        # #4B3FE3
OUTLINE = (26, 23, 89, 255)      # 深靛边
WHITE = (255, 255, 255, 255)


def make(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1],
                        radius=max(1, size // 6), fill=BRAND)
    pad = size * 0.20
    gap = size * 0.07
    cell = (size - 2 * pad - gap) / 2
    for r in range(2):
        for c in range(2):
            x0 = pad + c * (cell + gap)
            y0 = pad + r * (cell + gap)
            d.rounded_rectangle([x0, y0, x0 + cell, y0 + cell],
                                radius=max(1, size * 0.04), fill=WHITE,
                                outline=OUTLINE, width=max(1, size // 80))
    return img


if __name__ == "__main__":
    base = make(256)
    base.save("app.ico", sizes=[(256, 256), (128, 128), (64, 64),
                                (48, 48), (32, 32), (16, 16)])
    base.save("app_preview.png")
    print("生成 app.ico（6 档尺寸）+ app_preview.png")
