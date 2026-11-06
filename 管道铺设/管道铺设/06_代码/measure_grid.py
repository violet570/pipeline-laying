# -*- coding: utf-8 -*-
"""Render a z18 crop with a 25-pixel graticule labelled in *image pixel* coordinates.

usage: python scripts/measure_grid.py <lat0> <lon0> <hw> <hh> <out.jpg> <title> [scale]

Prints the origin (ox, oy) of the crop in Web Mercator (GCJ-02 corrected) z18 pixels,
so scripts/px2ll.py can convert the pixel boxes you read off the image back to lat/lon.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fig_campus_all import wgs2gcj, merc_px  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILES = os.path.join(ROOT, 'data', 'tiles', 'campus_sat_z18_full')
FIG = os.path.join(ROOT, 'docs', 'fig')
Z = 18


def main(lat0, lon0, hw, hh, out, title, scale=2):
    cx, cy = merc_px(*wgs2gcj(lon0, lat0), Z)
    ox, oy = int(cx) - hw, int(cy) - hh
    st = {}
    for fn in os.listdir(TILES):
        p = fn.replace('.jpg', '').split('_')
        if len(p) == 3:
            st[(int(p[1]), int(p[2]))] = os.path.join(TILES, fn)
    img = Image.new('RGB', (2 * hw, 2 * hh), (0, 0, 0))
    for tx in range(ox // 256, (ox + 2 * hw) // 256 + 1):
        for ty in range(oy // 256, (oy + 2 * hh) // 256 + 1):
            fp = st.get((tx, ty))
            if fp:
                img.paste(Image.open(fp).convert('RGB'), (tx * 256 - ox, ty * 256 - oy))
    if scale != 1:
        img = img.resize((2 * hw * scale, 2 * hh * scale), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 14)
    for x in range(0, 2 * hw, 25):
        X = x * scale
        major = (x % 100 == 0)
        d.line([(X, 0), (X, 2 * hh * scale)],
               fill=(0, 255, 255) if major else (0, 120, 130), width=1)
        if major:
            d.text((X + 2, 2), str(x), font=f, fill=(0, 255, 255))
    for y in range(0, 2 * hh, 25):
        Y = y * scale
        major = (y % 100 == 0)
        d.line([(0, Y), (2 * hw * scale, Y)],
               fill=(0, 255, 255) if major else (0, 120, 130), width=1)
        if major:
            d.text((2, Y + 1), str(y), font=f, fill=(0, 255, 255))
    pad = 74
    panel = Image.new('RGB', (2 * hw * scale, 2 * hh * scale + pad), (6, 10, 16))
    panel.paste(img, (0, pad))
    d2 = ImageDraw.Draw(panel)
    d2.text((12, 6), title, font=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 24),
            fill=(255, 255, 255))
    d2.text((12, 44), '青色网格 25 px = %.1f m（数字是裁剪图像素坐标）；ox=%d oy=%d'
             % (25 * 0.458, ox, oy),
             font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 16), fill=(185, 200, 220))
    panel.save(os.path.join(FIG, out), quality=93)
    print('saved', out, panel.size, 'ox=%d oy=%d Z=%d' % (ox, oy, Z))


if __name__ == '__main__':
    a = sys.argv[1:]
    main(float(a[0]), float(a[1]), int(a[2]), int(a[3]), a[4], a[5],
         int(a[6]) if len(a) > 6 else 2)
