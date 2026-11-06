# -*- coding: utf-8 -*-
"""Draw the plaza crop with a labelled pixel grid (every 25 px) so the five building
rectangles can be read off precisely, then verify.
Output: docs/fig/plaza_grid.jpg
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
LAT0, LON0 = 39.91620, 119.51545
HW, HH = 330, 300

st = {}
for fn in os.listdir(TILES):
    p = fn.replace('.jpg', '').split('_')
    if len(p) == 3:
        st[(int(p[1]), int(p[2]))] = os.path.join(TILES, fn)
cx, cy = merc_px(*wgs2gcj(LON0, LAT0), Z)
ox, oy = int(cx) - HW, int(cy) - HH
img = Image.new('RGB', (2 * HW, 2 * HH), (0, 0, 0))
for tx in range(ox // 256, (int(cx) + HW) // 256 + 1):
    for ty in range(oy // 256, (int(cy) + HH) // 256 + 1):
        fp = st.get((tx, ty))
        if fp:
            img.paste(Image.open(fp).convert('RGB'), (tx * 256 - ox, ty * 256 - oy))

d = ImageDraw.Draw(img)
f = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 13)
for x in range(0, 2 * HW, 25):
    c = (255, 60, 60) if x % 100 == 0 else (0, 220, 255)
    d.line([(x, 0), (x, 2 * HH)], fill=c, width=1)
    if x % 100 == 0:
        d.text((x + 1, 1), str(x), font=f, fill=(255, 255, 80))
for y in range(0, 2 * HH, 25):
    c = (255, 60, 60) if y % 100 == 0 else (0, 220, 255)
    d.line([(0, y), (2 * HW, y)], fill=c, width=1)
    if y % 100 == 0:
        d.text((2, y + 1), str(y), font=f, fill=(255, 255, 80))
img.save(os.path.join(FIG, 'plaza_grid.jpg'), quality=94)
print('saved', img.size, 'origin offset ox,oy=', ox, oy)
