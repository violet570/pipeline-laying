# -*- coding: utf-8 -*-
"""Draw the five read-off rectangles back onto the plaza crop to verify they enclose the
real buildings, then convert to lat/lon and write the registry-ready JSON.

The pixel rectangles were read from docs/fig/plaza_grid.jpg (660x600 crop, origin offset
ox=55834514, oy=25425794 at z18, centre 39.91620,119.51545).

Run: python scripts/plaza_verify.py
"""
import json
import math
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

# read off docs/fig/plaza_grid.jpg
RECTS = {
    'plaza-top':  (175, 18, 520, 95),    # crescent block on the north edge
    'plaza-UL':   (150, 178, 330, 250),  # upper row, west
    'plaza-UR':   (388, 182, 600, 255),  # upper row, east
    'plaza-LL':   (150, 272, 340, 392),  # lower row, west
    'plaza-LR':   (385, 272, 600, 392),  # lower row, east
}
NAMES = {
    'plaza-top': '信息科学与工程学院',
    'plaza-UL': '人工智能学院(软件学院)',
    'plaza-LR': '理学院',
    'plaza-UR': '圆形广场北排东楼(待定名)',
    'plaza-LL': '圆形广场南排西楼(待定名)',
}


def px2ll(X, Y, ox, oy):
    mx, my = ox + X, oy + Y
    n = 2.0 ** Z * 256.0
    gx = mx / n * 360.0 - 180.0
    gy = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * my / n))))
    lon, lat = gx, gy
    for _ in range(30):
        tl, tt = wgs2gcj(lon, lat)
        lon += gx - tl
        lat += gy - tt
    return lat, lon


def main():
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
    f = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 22)
    out = []
    for key, (x0, y0, x1, y1) in RECTS.items():
        d.rectangle([x0, y0, x1, y1], outline=(0, 255, 120), width=3)
        d.text((x0 + 4, y0 + 3), NAMES[key][:10], font=f, fill=(255, 255, 80))
        la0, lo0 = px2ll(x0, y0, ox, oy)
        la1, lo1 = px2ll(x1, y1, ox, oy)
        w_m = (x1 - x0) * 0.458
        h_m = (y1 - y0) * 0.458
        out.append(dict(key=key, name=NAMES[key],
                        lat=round((la0 + la1) / 2, 6), lon=round((lo0 + lo1) / 2, 6),
                        bbox=[round(min(lo0, lo1), 6), round(min(la0, la1), 6),
                              round(max(lo0, lo1), 6), round(max(la0, la1), 6)],
                        area_m2=round(w_m * h_m)))
        print('%-10s %-9s lat=%.6f lon=%.6f  box %.1f x %.1f m = %d m2'
              % (key, NAMES[key][:9], (la0 + la1) / 2, (lo0 + lo1) / 2, w_m, h_m,
                 round(w_m * h_m)))
    img.save(os.path.join(FIG, 'plaza_verify.jpg'), quality=94)
    with open(os.path.join(ROOT, 'data', 'derived', 'plaza_buildings.json'), 'w',
              encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print('saved docs/fig/plaza_verify.jpg')


if __name__ == '__main__':
    main()
