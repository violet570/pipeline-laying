# -*- coding: utf-8 -*-
"""Locate the semicircular building just south of 材料B楼.

User says it is 国家亚稳态材料国家重点实验室 (name not certain). We also need to re-check
which building is really 材料A楼, since the semicircular one was previously (mis)labelled so.

Out: docs/fig/loc_lab.jpg
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fig_campus_all import wgs2gcj, merc_px  # noqa: E402
import groups as G  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILES = os.path.join(ROOT, 'data', 'tiles', 'campus_sat_z18_full')
FIG = os.path.join(ROOT, 'docs', 'fig')
Z = 18
LAT0, LON0 = 39.907450, 119.516900
HW, HH = 420, 330
SCALE = 2


def main():
    cx, cy = merc_px(*wgs2gcj(LON0, LAT0), Z)
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
    img = img.resize((2 * HW * SCALE, 2 * HH * SCALE), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 18)

    def px(lon, lat):
        X, Y = merc_px(*wgs2gcj(lon, lat), Z)
        return ((X - ox) * SCALE, (Y - oy) * SCALE)

    # 25 px graticule (11.5 m)
    for k in range(0, 2 * HW, 25):
        d.line([(k * SCALE, 0), (k * SCALE, 2 * HH * SCALE)], fill=(0, 190, 230), width=1)
    for k in range(0, 2 * HH, 25):
        d.line([(0, k * SCALE), (2 * HW * SCALE, k * SCALE)], fill=(0, 190, 230), width=1)

    ways = G.load_ways()
    for g in G.GROUPS:
        if g['cat'] not in ('lab', 'teaching', 'other', 'college', 'office'):
            continue
        if g.get('measured'):
            m = g['measured']
            x0, y0 = px(m['bbox'][0], m['bbox'][3])
            x1, y1 = px(m['bbox'][2], m['bbox'][1])
            d.rectangle([x0, y0, x1, y1], outline=(255, 60, 220), width=2)
            d.text((x0 + 3, y0 + 2), g['short'], font=f, fill=(255, 90, 230))
            continue
        for wid in g['ways']:
            el = ways.get(wid)
            if not el:
                continue
            gg = [p for p in (el.get('geometry') or []) if p]
            if len(gg) < 3:
                continue
            pts = [px(p['lon'], p['lat']) for p in gg]
            d.line(pts + [pts[0]], fill=(120, 255, 150), width=2)
            mx = sum(p[0] for p in pts) / len(pts)
            my = sum(p[1] for p in pts) / len(pts)
            d.text((mx, my), g['short'], font=f, fill=(140, 255, 170))

    panel = Image.new('RGB', (2 * HW * SCALE, 2 * HH * SCALE + 64), (6, 10, 16))
    panel.paste(img, (0, 64))
    d2 = ImageDraw.Draw(panel)
    d2.text((10, 6), '材料 A/B/C 区域放大 2×：找"材料B楼下方那栋半圆形建筑"',
            font=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 25), fill=(255, 255, 255))
    d2.text((10, 38), '绿=OSM 轮廓  洋红=影像量测框  青网格 25px≈11.5 m',
            font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 17), fill=(185, 200, 220))
    panel.save(os.path.join(FIG, 'loc_lab.jpg'), quality=94)
    print('saved loc_lab.jpg', panel.size, 'origin', ox, oy)


if __name__ == '__main__':
    main()
