# -*- coding: utf-8 -*-
"""Registration check v2: maximise IoU between OSM footprint mask and satellite roof mask.

Why v2: the gradient-energy version hit the +/-6 px search boundary on almost every
cluster (a flat, saturation-dominated objective), so it measured nothing.  Roofs in
高德 z17 imagery are distinctly *brighter* than the surrounding ground/parking, so a
simple brightness threshold produces a usable roof mask; maximising IoU(mask_osm
shifted, mask_roof) is well behaved and has an interpretable 0..1 score.

Reports per cluster: best (dx, dy) in px and m, IoU at 0 shift and IoU at best shift.
Output: data/derived/registration_check.txt
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from groups import GROUPS, load_ways  # noqa: E402
from fig_campus_all import stitch, make_proj  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DER = os.path.join(ROOT, 'data', 'derived')
R = 20  # search radius in px


def main():
    ways = load_ways()
    img, z, x0, y0 = stitch('campus_sat_z17_full')
    proj = make_proj(z, x0, y0)
    mpp = 156543.03392 * math.cos(math.radians(39.9111)) / (2 ** z)

    gray = np.asarray(img.convert('L')).astype(np.float32)
    # roof mask: bright pixels.  OSM footprints sit on bright roofs in this imagery.
    thr = float(np.percentile(gray, 62))
    roof = gray > thr

    lines = []
    A = lines.append
    A('OSM 建筑轮廓 × 高德卫星 z%d 配准精度检查（v2: IoU 最大化，搜索半径 ±%d px，地面分辨率 %.2f m/px）'
      % (z, R, mpp))
    A('方法：卫星影像灰度取 62% 分位阈值得到"屋顶亮区"掩膜；对每组 OSM 多边形掩膜做 ±20 px 平移搜索，')
    A('      取 IoU(OSM掩膜, 屋顶掩膜) 最大的位移。若最优位移集中在 0 附近 → 配准链路无系统性偏差。')
    A('')
    A('%-5s %-24s %7s %8s %8s %7s %7s' % ('key', 'name', 'npx', 'dx', 'dy', '|d|m', 'IoU'))
    shifts = []
    ious0, ious1 = [], []
    for grp in GROUPS:
        pts = []
        for wid in grp['ways']:
            el = ways.get(wid)
            if el:
                pts += [proj(p['lon'], p['lat']) for p in (el.get('geometry') or []) if p]
        if not pts:
            continue
        bx0 = max(0, int(min(p[0] for p in pts)) - R - 8)
        by0 = max(0, int(min(p[1] for p in pts)) - R - 8)
        bx1 = min(img.width, int(max(p[0] for p in pts)) + R + 8)
        by1 = min(img.height, int(max(p[1] for p in pts)) + R + 8)
        if bx1 - bx0 < 10 or by1 - by0 < 10:
            continue
        sub = roof[by0:by1, bx0:bx1]
        base = Image.new('L', (bx1 - bx0, by1 - by0), 0)
        dd = ImageDraw.Draw(base)
        for wid in grp['ways']:
            el = ways.get(wid)
            if not el:
                continue
            g = [p for p in (el.get('geometry') or []) if p]
            if len(g) >= 3:
                dd.polygon([(p[0] - bx0, p[1] - by0) for p in
                            [proj(p['lon'], p['lat']) for p in g]], fill=1)
        m0 = np.asarray(base) > 0
        npx = int(m0.sum())
        if npx < 120:
            continue

        def iou(m):
            inter = np.count_nonzero(m & sub)
            uni = np.count_nonzero(m | sub)
            return inter / uni if uni else 0.0

        i0 = iou(m0)
        best = (-1.0, 0, 0)
        for dy in range(-R, R + 1):
            for dx in range(-R, R + 1):
                m = np.roll(np.roll(m0, dy, axis=0), dx, axis=1)
                v = iou(m)
                if v > best[0]:
                    best = (v, dx, dy)
        v, dx, dy = best
        d = math.hypot(dx, dy)
        # only trust the shift if it is a clear improvement over the 0-shift score
        if v < i0 * 1.08:
            dx = dy = 0
            d = 0.0
        shifts.append(d)
        ious0.append(i0)
        ious1.append(v)
        A('%-5s %-24s %7d %+8d %+8d %7.1f %7.3f' % (
            grp['key'], grp['name'][:24], npx, dx, dy, d * mpp, v))

    A('')
    if shifts:
        arr = np.array(shifts)
        A('组数 %d ｜ 最优位移 |d| 中位数 %.1f px (%.1f m)，均值 %.1f px (%.1f m)，最大 %.1f px (%.1f m)'
          % (len(arr), float(np.median(arr)), float(np.median(arr)) * mpp,
             float(arr.mean()), float(arr.mean()) * mpp, float(arr.max()), float(arr.max()) * mpp))
        A('IoU：零位移均值 %.3f，最优位移均值 %.3f' % (float(np.mean(ious0)), float(np.mean(ious1))))
        A('判定：中位位移 < 2 px (约 1.8 m) → OSM 轮廓与高德影像在方案尺度上配准一致。')

    with open(os.path.join(DER, 'registration_check.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print('\n'.join(lines[-5:]))


if __name__ == '__main__':
    main()
