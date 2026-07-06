#!/usr/bin/env python3
"""Generate the 1200x630 social-share (Open Graph) banner -> site/assets/og.png.

Drawn with Pillow so it needs no browser. Re-run after changing brand/tagline:
    python launch-web/scripts/make_og.py
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1200, 630
BG = (10, 10, 10)
GREEN = (30, 215, 96)
WHITE = (255, 255, 255)
GREY = (179, 179, 179)

SITE = Path(__file__).resolve().parents[1] / "site"
ICON = SITE / "assets" / "app-icon.png"
OUT = SITE / "assets" / "og.png"

FONTS = Path("C:/Windows/Fonts")
def font(name, size, index=0):
    return ImageFont.truetype(str(FONTS / name), size, index=index)

f_word = font("segoeuib.ttf", 32)          # "Lyrics Widget" wordmark
f_title = font("msjhbd.ttc", 98)           # big Chinese title
f_accent = font("segoeuib.ttf", 30)        # english accent line
f_sub = font("msjh.ttc", 26)               # grey subtitle
f_pill = font("segoeuib.ttf", 22)          # latin labels (0:58 / 2:16)
f_pill_cjk = font("msjhbd.ttc", 23)        # pill label (has Chinese glyphs)
f_lyric = font("msjhbd.ttc", 26)           # widget mock lyric


def glow(img, cx, cy, rw, rh, alpha, blur):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse([cx - rw, cy - rh, cx + rw, cy + rh], fill=GREEN + (alpha,))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def main():
    img = Image.new("RGBA", (W, H), BG + (255,))

    # ambient green glows
    glow(img, 470, 40, 520, 300, 42, 130)
    glow(img, 980, 330, 300, 230, 60, 110)

    d = ImageDraw.Draw(img)

    # wordmark: icon + name
    icon = Image.open(ICON).convert("RGBA").resize((46, 46), Image.LANCZOS)
    img.alpha_composite(icon, (72, 62))
    d.text((130, 68), "Lyrics Widget", font=f_word, fill=WHITE)

    # main title
    d.text((70, 212), "桌面同步歌詞", font=f_title, fill=WHITE)

    # green accent + grey subtitle
    d.text((74, 352), "Synced Spotify Lyrics", font=f_accent, fill=GREEN)
    d.text((74, 400), "Windows 11 · 逐句同步 · 免費開源", font=f_sub, fill=GREY)

    # pill: free / open source
    pill = "免費 · 開源 · MIT"
    pw = d.textlength(pill, font=f_pill_cjk)
    # opaque dark-green tint (matches the site's rgba(30,215,96,.10) over #0a0a0a)
    d.rounded_rectangle([74, 470, 74 + pw + 40, 470 + 48], radius=24,
                        fill=(12, 31, 19), outline=GREEN, width=2)
    d.text((94, 480), pill, font=f_pill_cjk, fill=GREEN)

    # widget mock card (right)
    cx0, cy0, cx1, cy1 = 792, 214, 1128, 416
    d.rounded_rectangle([cx0, cy0, cx1, cy1], radius=20, fill=(20, 20, 20, 255),
                        outline=GREEN, width=2)
    # top row: title bar + eq bars
    d.rounded_rectangle([cx0 + 28, cy0 + 30, cx0 + 150, cy0 + 40], radius=5, fill=(74, 74, 74))
    for i, hbar in enumerate((14, 22, 12)):
        x = cx1 - 70 + i * 12
        d.rounded_rectangle([x, cy0 + 24 + (24 - hbar), x + 5, cy0 + 48], radius=2, fill=GREEN)
    # highlighted lyric line
    d.text((cx0 + 30, cy0 + 78), "把整座城市調成靜音", font=f_lyric, fill=GREEN)
    # progress bar
    by = cy1 - 46
    d.text((cx0 + 28, by - 4), "0:58", font=f_pill, fill=(106, 106, 106))
    tx0, tx1 = cx0 + 82, cx1 - 82
    d.rounded_rectangle([tx0, by + 6, tx1, by + 12], radius=3, fill=(58, 58, 58))
    d.rounded_rectangle([tx0, by + 6, tx0 + int((tx1 - tx0) * 0.42), by + 12], radius=3, fill=GREEN)
    d.text((cx1 - 74, by - 4), "2:16", font=f_pill, fill=(106, 106, 106))

    img.convert("RGB").save(OUT, "PNG")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
