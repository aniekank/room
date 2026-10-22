"""Draws the app icon and the menu bar icon. Run by build.sh (needs Pillow)."""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
OUT.mkdir(parents=True, exist_ok=True)
S = 1024


def app_icon():
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    # macOS icon grid: 824px rounded square centred on the 1024 canvas
    bg = Image.new('RGBA', (S, S))
    top, bottom = (42, 29, 51), (13, 11, 16)
    px = bg.load()
    for y in range(S):
        t = y / S
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,)
        for x in range(S):
            px[x, y] = c
    mask = Image.new('L', (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((100, 100, 924, 924), radius=185, fill=255)
    img.paste(bg, (0, 0), mask)
    d = ImageDraw.Draw(img)
    # the TV: cream bezel, dark screen with the three channels as stripes
    d.rounded_rectangle((210, 250, 814, 690), radius=48, fill=(243, 237, 228))
    d.rounded_rectangle((246, 286, 778, 654), radius=22, fill=(26, 18, 32))
    for i, col in enumerate([(246, 194, 107), (159, 224, 168), (236, 132, 150)]):
        y = 340 + i * 98
        d.rounded_rectangle((300, y, 724, y + 62), radius=31, fill=col)
    d.rounded_rectangle((462, 690, 562, 760), radius=6, fill=(243, 237, 228))
    d.rounded_rectangle((352, 752, 672, 790), radius=19, fill=(243, 237, 228))
    return img


def iconset(img):
    d = OUT / 'Room.iconset'
    d.mkdir(exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        img.resize((size, size), Image.LANCZOS).save(d / f'icon_{size}x{size}.png')
        img.resize((size * 2, size * 2), Image.LANCZOS).save(d / f'icon_{size}x{size}@2x.png')
    subprocess.run(['iconutil', '-c', 'icns', str(d), '-o', str(OUT / 'Room.icns')], check=True)


def menubar():
    # Template image: black on transparent, macOS tints it for light and dark menu bars.
    m = Image.new('RGBA', (44, 36), (0, 0, 0, 0))
    d = ImageDraw.Draw(m)
    d.rounded_rectangle((4, 4, 40, 27), radius=4, outline=(0, 0, 0, 255), width=3)
    for i in range(3):
        d.rectangle((11, 10 + i * 5, 33, 11 + i * 5), fill=(0, 0, 0, 255))
    d.rectangle((14, 30, 30, 32), fill=(0, 0, 0, 255))
    m.save(OUT / 'menubar@2x.png')
    m.resize((22, 18), Image.LANCZOS).save(OUT / 'menubar.png')


icon = app_icon()
icon.save(OUT / 'icon.png')
iconset(icon)
menubar()
print('icons in', OUT)
