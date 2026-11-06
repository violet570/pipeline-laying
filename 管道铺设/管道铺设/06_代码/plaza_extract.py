# -*- coding: utf-8 -*-
"""Extract building footprints for the 5 buildings standing inside the big circular plaza
at the north end of the west campus — these are NOT in OSM at all, yet the user says they
are 信息科学与工程学院 / 人工智能学院(软件学院) / 理学院.

Method: stitch the z18 satellite tiles around the plaza, threshold "dark roof on light
pavement", take connected components, filter by area/shape, and print each component's
centroid + bbox + polygon approximated in lat/lon so they can be written into
scripts/groups.py as measured (not OSM) entries.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fig_campus_all import wgs2gcj, merc_px  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILES = os.path.join(ROOT, 'data', 'tiles', 'campus_sat_z18_full')
FIG = os.path.join(ROOT, 'docs', 'fig')
Z = 18
LAT0, LON0 = 39.9160, 119.5150


def px2ll(X, Y, ox, oy):
    """inverse of merc_px for GCJ-02 -> approximate WGS84 (offset is ~500m but constant,
    so we subtract the local GCJ delta to get back to WGS84)."""
    mx = ox + X
    my = oy + Y
    n = 2.0 ** Z * 256.0
    gx = mx / n * 360.0 - 180.0
    gy = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * my / n))))
    # invert the GCJ shift by a 2-step fixed point
    lon, lat = gx, gy
    for _ in range(30):
        tl, tt = wgs2gcj(lon, lat)
        lon += gx - tl
        lat += gy - tt
    return lat, lon


def stitch(cx, cy, hw, hh):
    st = {}
    for fn in os.listdir(TILES):
        parts = fn.replace('.jpg', '').split('_')
        if len(parts) == 3:
            st[(int(parts[1]), int(parts[2]))] = os.path.join(TILES, fn)
    ox, oy = int(cx) - hw, int(cy) - hh
    img = Image.new('RGB', (2 * hw, 2 * hh), (0, 0, 0))
    for tx in range(ox // 256, (int(cx) + hw) // 256 + 1):
        for ty in range(oy // 256, (int(cy) + hh) // 256 + 1):
            fp = st.get((tx, ty))
            if fp:
                img.paste(Image.open(fp).convert('RGB'), (tx * 256 - ox, ty * 256 - oy))
    return img, ox, oy


def label(mask):
    """4-connected component labelling, pure python on a small mask."""
    h, w = mask.shape
    lab = np.zeros((h, w), dtype=np.int32)
    cur = 0
    for y in range(h):
        for x in range(w):
            if mask[y, x] and not lab[y, x]:
                cur += 1
                stack = [(y, x)]
                lab[y, x] = cur
                while stack:
                    cy2, cx2 = stack.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy2 + dy, cx2 + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not lab[ny, nx]:
                            lab[ny, nx] = cur
                            stack.append((ny, nx))
    return lab, cur


def main():
    cx, cy = merc_px(*wgs2gcj(LON0, LAT0), Z)
    hw, hh = 560, 500
    img, ox, oy = stitch(cx, cy, hw, hh)
    a = np.asarray(img.convert('RGB')).astype(np.int16)
    lum = a.mean(axis=2)
    # roofs are dark (grey ~60-110) against bright pavement (>150)
    mask = lum < 118
    mask, n = label(mask)
    objs = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(mask == i)
        if len(xs) < 900:
            continue
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        fill = len(xs) / float(bw * bh)
        if fill < 0.45 or bw < 25 or bh < 18:
            continue
        objs.append(dict(px=int(xs.mean()), py=int(ys.mean()), x0=int(x0), x1=int(x1),
                         y0=int(y0), y1=int(y1), area=int(len(xs)), fill=round(fill, 2)))
    objs.sort(key=lambda o: o['py'])
    print('components:', len(objs))
    res = []
    for o in objs:
        la, lo = px2ll(o['px'], o['py'], ox, oy)
        res.append(dict(id=None, lat=round(la, 6), lon=round(lo, 6),
                        bbox=[o['x0'], o['y0'], o['x1'], o['y1']],
                        area_px=o['area'], fill=o['fill']))
        print('  px(%d,%d) lat=%.6f lon=%.6f  %dx%d fill=%.2f px=%.0f m2=%.0f'
              % (o['px'], o['py'], la, lo, o['x1'] - o['x0'], o['y1'] - o['y0'],
                 o['fill'], o['area'], o['area'] * 0.458 ** 2))
    with open(os.path.join(ROOT, 'data', 'derived', 'plaza_buildings.json'), 'w',
              encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

    d = ImageDraw.Draw(img)
    fnt = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 26)
    for i, o in enumerate(objs):
        d.rectangle([o['x0'], o['y0'], o['x1'], o['y1']], outline=(0, 255, 120), width=4)
        d.text((o['x0'] + 4, o['y0'] + 4), 'P%d' % (i + 1), font=fnt, fill=(255, 255, 0))
    img.save(os.path.join(FIG, 'plaza_components.jpg'), quality=92)
    print('saved docs/fig/plaza_components.jpg')


if __name__ == '__main__':
    main()
