# -*- coding: utf-8 -*-
"""Re-extract the 5 buildings inside the north circular plaza, properly.

Earlier attempt (plaza_pin.py) used hand-guessed pixel boxes and they were misaligned.
This version segments the plaza crop by roof luminance, keeps compact connected
components of plausible building size, and prints each one's bbox/centroid so the
assignment to 信息学院/人工智能/理学院 can be made from the REAL outlines.

Run: python scripts/plaza_segment.py
Out: docs/fig/plaza_seg.jpg  +  data/derived/plaza_buildings.json
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
LAT0, LON0 = 39.91620, 119.51545
HW, HH = 330, 300


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


def stitch():
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
    return img, ox, oy


def label(mask):
    h, w = mask.shape
    lab = np.zeros((h, w), dtype=np.int32)
    cur = 0
    for y in range(h):
        row = mask[y]
        for x in range(w):
            if row[x] and not lab[y, x]:
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
    img, ox, oy = stitch()
    a = np.asarray(img.convert('RGB')).astype(np.int16)
    lum = a.mean(axis=2)
    mask = lum < 132
    lab, n = label(mask)
    objs = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        cnt = len(xs)
        if cnt < 2500:
            continue
        x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        fill = cnt / float(bw * bh)
        if bw < 45 or bh < 40:
            continue
        if fill < 0.50:
            continue
        if bw / float(bh) > 9 or bh / float(bw) > 9:
            continue
        objs.append(dict(px=int(xs.mean()), py=int(ys.mean()), x0=x0, x1=x1, y0=y0, y1=y1,
                         w=bw, h=bh, area=cnt, fill=round(fill, 2)))
    objs.sort(key=lambda o: o['py'])

    # Two blocks on each side are separated only by a walkway, so they merge into one
    # component.  Split each merged component at the row where the pixel count dips.
    split = []
    for o in objs:
        sub = (lab[o['y0']:o['y1'] + 1, o['x0']:o['x1'] + 1] > 0)
        rows = sub.sum(axis=1)
        mid0, mid1 = int(len(rows) * 0.30), int(len(rows) * 0.70)
        if mid1 - mid0 < 6:
            split.append(o)
            continue
        seg = rows[mid0:mid1]
        cut = mid0 + int(np.argmin(seg))
        if rows[cut] > rows.max() * 0.85:      # no real gap -> keep whole
            split.append(o)
            continue
        for (ya, yb) in ((0, cut), (cut + 1, len(rows) - 1)):
            if yb - ya < 30:
                continue
            sm = sub[ya:yb + 1]
            ys, xs = np.nonzero(sm)
            if len(xs) < 1200:
                continue
            cnt = len(xs)
            x0, x1 = int(xs.min()), int(xs.max())
            y0, y1 = int(ys.min()), int(ys.max())
            bw, bh = x1 - x0 + 1, y1 - y0 + 1
            split.append(dict(px=o['x0'] + int(xs.mean()), py=o['y0'] + ya + int(ys.mean()),
                              x0=o['x0'] + x0, x1=o['x0'] + x1,
                              y0=o['y0'] + ya + y0, y1=o['y0'] + ya + y1,
                              w=bw, h=bh, area=cnt, fill=round(cnt / float(bw * bh), 2)))
    objs = sorted(split, key=lambda o: (o['py'], o['px']))

    print('components after split:', len(objs))
    out = []
    for k, o in enumerate(objs):
        la, lo = px2ll(o['px'], o['py'], ox, oy)
        la0, lo0 = px2ll(o['x0'], o['y0'], ox, oy)
        la1, lo1 = px2ll(o['x1'], o['y1'], ox, oy)
        o['lat'], o['lon'] = round(la, 6), round(lo, 6)
        o['bbox'] = [round(min(lo0, lo1), 6), round(min(la0, la1), 6),
                     round(max(lo0, lo1), 6), round(max(la0, la1), 6)]
        o['area_m2'] = round(o['area'] * 0.458 ** 2)
        print('  P%d px(%d,%d) %dx%d fill=%.2f  lat=%.6f lon=%.6f  %d m2'
              % (k + 1, o['px'], o['py'], o['w'], o['h'], o['fill'], la, lo, o['area_m2']))
        out.append(o)

    d = ImageDraw.Draw(img)
    fnt = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 26)
    for k, o in enumerate(objs):
        d.rectangle([o['x0'], o['y0'], o['x1'], o['y1']], outline=(0, 255, 120), width=3)
        d.text((o['x0'] + 3, o['y0'] + 2), 'P%d' % (k + 1), font=fnt, fill=(255, 255, 0))
    img.save(os.path.join(FIG, 'plaza_seg.jpg'), quality=94)
    with open(os.path.join(ROOT, 'data', 'derived', 'plaza_buildings.json'), 'w',
              encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('saved docs/fig/plaza_seg.jpg and data/derived/plaza_buildings.json')


if __name__ == '__main__':
    main()
