# -*- coding: utf-8 -*-
"""Pin the five plaza buildings precisely.

The plaza image (docs/fig/plaza_components.jpg, 1120x1000, origin px = (cx-560, cy-500) in
Web-Mercator z18) shows five solid buildings inside the ring road:
  - one crescent-shaped block at the top            ("top")
  - two blocks in the upper row, left and right     ("UL", "UR")
  - two blocks in the lower row, left and right     ("LL", "LR")

This script takes, for each block, the pixel bbox read off that render, converts the bbox
corners to lat/lon, and writes data/derived/plaza_buildings.json plus a proof overlay that
draws the resulting polygons back onto the satellite image.
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
LAT0, LON0 = 39.9160, 119.5150
HW, HH = 560, 500


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


def stitch(cx, cy):
    st = {}
    for fn in os.listdir(TILES):
        p = fn.replace('.jpg', '').split('_')
        if len(p) == 3:
            st[(int(p[1]), int(p[2]))] = os.path.join(TILES, fn)
    ox, oy = int(cx) - HW, int(cy) - HH
    img = Image.new('RGB', (2 * HW, 2 * HH), (0, 0, 0))
    for tx in range(ox // 256, (int(cx) + HW) // 256 + 1):
        for ty in range(oy // 256, (int(cy) + HH) // 256 + 1):
            fp = st.get((tx, ty))
            if fp:
                img.paste(Image.open(fp).convert('RGB'), (tx * 256 - ox, ty * 256 - oy))
    return img, ox, oy


# pixel bboxes on the 1120x1000 render, eyeballed from docs/fig/plaza_components.jpg
BOXES = {
    'plaza-top':  (430, 300, 800, 385),   # crescent block, top of the ring
    'plaza-UL':   (445, 420, 640, 480),
    'plaza-UR':   (715, 405, 900, 465),
    'plaza-LL':   (450, 480, 655, 545),
    'plaza-LR':   (715, 465, 905, 530),
}


def main():
    cx, cy = merc_px(*wgs2gcj(LON0, LAT0), Z)
    img, ox, oy = stitch(cx, cy)
    d = ImageDraw.Draw(img)
    fnt = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 24)
    out = []
    for key, (x0, y0, x1, y1) in BOXES.items():
        la0, lo0 = px2ll(x0, y0, ox, oy)
        la1, lo1 = px2ll(x1, y1, ox, oy)
        poly = [[lo0, la0], [lo1, la0], [lo1, la1], [lo0, la1]]
        area = abs((lo1 - lo0) * (la1 - la0)) * (111320.0 ** 2) * math.cos(math.radians(la0))
        rec = dict(key=key, name=None, lat=round((la0 + la1) / 2, 6), lon=round((lo0 + lo1) / 2, 6),
                   ring=poly, bbox=[round(lo0, 6), round(la0, 6), round(lo1, 6), round(la1, 6)],
                   area_m2=round(area))
        out.append(rec)
        d.rectangle([x0, y0, x1, y1], outline=(0, 255, 90), width=4)
        d.text((x0 + 5, y0 + 3), key.replace('plaza-', ''), font=fnt, fill=(255, 255, 0))
        print('%-10s lat=%.6f lon=%.6f  %.0f m2' % (key, rec['lat'], rec['lon'], area))
    with open(os.path.join(ROOT, 'data', 'derived', 'plaza_buildings.json'), 'w',
              encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    img.save(os.path.join(FIG, 'plaza_boxes.jpg'), quality=92)
    print('saved docs/fig/plaza_boxes.jpg', img.size)


if __name__ == '__main__':
    main()
