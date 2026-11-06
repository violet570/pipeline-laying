# -*- coding: utf-8 -*-
"""Try several roof-luminance thresholds on the plaza crop and report the components each
one yields, so a threshold that cleanly separates the 5 buildings can be picked.
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fig_campus_all import wgs2gcj, merc_px  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILES = os.path.join(ROOT, 'data', 'tiles', 'campus_sat_z18_full')
Z = 18
LAT0, LON0 = 39.91620, 119.51545
HW, HH = 330, 300


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
    return img


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


img = stitch()
lum = np.asarray(img.convert('RGB')).astype(np.int16).mean(axis=2)
for th in (95, 100, 105, 110, 115, 120, 125, 132):
    lab, n = label(lum < th)
    found = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        if len(xs) < 2000:
            continue
        x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        if bw < 45 or bh < 35:
            continue
        fill = len(xs) / float(bw * bh)
        if fill < 0.55 or bw / float(bh) > 6 or bh / float(bw) > 6:
            continue
        found.append((x0, y0, x1, y1, bw, bh, round(fill, 2), len(xs)))
    found.sort(key=lambda t: (t[1], t[0]))
    print('th=%-4d n=%-2d  %s' % (th, len(found),
          ' | '.join('%dx%d@(%d,%d) f%.2f' % (b[4], b[5], b[0], b[1], b[6]) for b in found)))
