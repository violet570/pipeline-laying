# -*- coding: utf-8 -*-
"""Zoom the top-of-figure circular area and label EVERY building there, to identify the
three 学院 the user described (信息科学与工程学院 / 人工智能学院(软件学院) / 理学院).

The user's description: "图中最上方的圆心区域内的三个建筑 ... 最上方的一个是信息科学与
工程学院，左下方的为人工智能学院，右下方的为理学院".

Output: docs/fig/verify_circle_zoom.jpg
"""
import json
import math
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fig_campus_all import wgs2gcj, merc_px  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILES = os.path.join(ROOT, 'data', 'tiles', 'campus_sat_z18_full')
RAW = os.path.join(ROOT, 'data', 'raw')
FIG = os.path.join(ROOT, 'docs', 'fig')
FONTB = 'C:/Windows/Fonts/msyhbd.ttc'
Z = 18


def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else 'C:/Windows/Fonts/msyh.ttc', sz)


def main():
    st = {}
    for fn in os.listdir(TILES):
        m = re.match(r'(\d+)_(\d+)_(\d+)\.(jpg|png)$', fn)
        if m:
            st[(int(m.group(2)), int(m.group(3)))] = os.path.join(TILES, fn)

    lat0, lon0 = 39.916300, 119.514900
    half = 620
    cx, cy = merc_px(*wgs2gcj(lon0, lat0), Z)
    cxi, cyi = int(cx), int(cy)
    ox, oy = cxi - half, cyi - half
    img = Image.new('RGB', (2 * half, 2 * half), (18, 20, 24))
    for tx in range(ox // 256, (cxi + half) // 256 + 1):
        for ty in range(oy // 256, (cyi + half) // 256 + 1):
            fp = st.get((tx, ty))
            if fp:
                img.paste(Image.open(fp).convert('RGB'), (tx * 256 - ox, ty * 256 - oy))
    d = ImageDraw.Draw(img)

    def px(lon, lat):
        X, Y = merc_px(*wgs2gcj(lon, lat), Z)
        return X - ox, Y - oy

    with open(os.path.join(RAW, 'verify_2026.json'), encoding='utf-8') as f:
        els = json.load(f)['buildings']
    with open(os.path.join(RAW, 'buildings.json'), encoding='utf-8') as f:
        geo = {}
        for e in json.load(f)['elements']:
            geo.setdefault(e['id'], e)

    items = []
    for el in els:
        c = el.get('center') or {}
        if not c:
            continue
        X, Y = px(c['lon'], c['lat'])
        if not (0 <= X <= 2 * half and 0 <= Y <= 2 * half):
            continue
        t = el.get('tags') or {}
        g = geo.get(el['id'], {}).get('geometry') or []
        if len(g) < 3:
            continue
        pts = [px(p['lon'], p['lat']) for p in g]
        area = abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] -
                       pts[(i + 1) % len(pts)][0] * pts[i][1]
                       for i in range(len(pts)))) / 2 * (0.458 ** 2)
        if area < 200:
            continue
        br = t.get('building') or ''
        col = {'university': (110, 235, 150), 'yes': (210, 210, 220),
               'school': (95, 175, 255), 'dormitory': (255, 95, 95),
               'residential': (150, 150, 165), 'apartments': (255, 190, 70)}.get(br, (170, 180, 195))
        d.line(pts + [pts[0]], fill=col, width=4)
        items.append((t.get('name') or '', el['id'], X, Y, col, area, c['lat'], c['lon']))

    items.sort(key=lambda t: t[3])
    used = []
    for name, oid, X, Y, col, area, la, lo in items:
        lab = (name if name else '#%d' % oid) + '  %.0fm2' % area
        yy = Y
        for _ in range(16):
            if all(abs(yy - uy) > 24 or abs(X - ux) > 200 for ux, uy in used):
                break
            yy += 24
        used.append((X, yy))
        fnt = font(21, True)
        tb = d.textbbox((0, 0), lab, font=fnt)
        d.rectangle([X - 3, yy - 2, X + tb[2] + 6, yy + tb[3] + 4], fill=(0, 0, 0))
        d.text((X, yy), lab, font=fnt, fill=col)

    for (X, Y), _ in zip([(px(o['lon'], o['lat'])) for o in
                          [{'lon': e['center']['lon'], 'lat': e['center']['lat']}
                           for e in els if e.get('center')]], []):
        pass

    pad = 92
    panel = Image.new('RGB', (2 * half, 2 * half + pad), (6, 10, 16))
    panel.paste(img, (0, pad))
    d2 = ImageDraw.Draw(panel)
    d2.text((14, 8), '最上方圆形区域放大：找出"信息科学与工程学院 / 人工智能学院 / 理学院"',
            font=font(30, True), fill=(255, 255, 255))
    d2.text((14, 52), '绿=university 灰=yes 蓝=school 红=宿舍；#id = OSM 无名建筑（id 可直接写进注册表）',
            font=font(20), fill=(185, 200, 220))
    out = os.path.join(FIG, 'verify_circle_zoom.jpg')
    panel.save(out, quality=92)
    print('saved', out, panel.size, 'labelled', len(items))
    for it in items:
        print('%-12s %-16s %9.0f m2  %.6f %.6f' % (it[1], (it[0] or '(无名)')[:16], it[5], it[6], it[7]))


if __name__ == '__main__':
    main()
