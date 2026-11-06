# -*- coding: utf-8 -*-
"""Zoom on the 里仁片区 so we can settle which building is which.

Draws: OSM outlines (green, with names), and the two measured boxes that live in this area
(洋红 = T18 拟改 里仁实验楼, 青 = T19 图文信息楼).
Out: docs/fig/loc_liren.jpg
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
LAT0, LON0 = 39.904900, 119.521600
HW, HH = 620, 380


def main():
    cx, cy = merc_px(*wgs2gcj(LON0, LAT0), Z)
    st = {}
    for fn in os.listdir(TILES):
        p = fn.replace('.jpg', '').split('_')
        if len(p) == 3:
            st[(int(p[1]), int(p[2]))] = os.path.join(TILES, fn)
    ox, oy = int(cx) - HW, int(cy) - HH
    img = Image.new('RGB', (2 * HW, 2 * HH), (10, 12, 16))
    for tx in range(ox // 256, (int(cx) + HW) // 256 + 1):
        for ty in range(oy // 256, (int(cy) + HH) // 256 + 1):
            fp = st.get((tx, ty))
            if fp:
                img.paste(Image.open(fp).convert('RGB'), (tx * 256 - ox, ty * 256 - oy))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 19)

    def px(lon, lat):
        X, Y = merc_px(*wgs2gcj(lon, lat), Z)
        return X - ox, Y - oy

    ways = G.load_ways()
    for g in G.GROUPS:
        if not g.get('measured'):
            continue
        m = g['measured']
        x0, y0 = px(m['bbox'][0], m['bbox'][3])
        x1, y1 = px(m['bbox'][2], m['bbox'][1])
        if x1 < 0 or x0 > 2 * HW or y1 < 0 or y0 > 2 * HH:
            continue
        col = (255, 60, 220) if g['key'] == 'T18' else (0, 230, 255)
        d.rectangle([x0, y0, x1, y1], outline=col, width=4)
        d.rectangle([x0 + 4, y0 + 4, x0 + 4 + 13 * len(g['short']) + 8, y0 + 28], fill=(0, 0, 0))
        d.text((x0 + 6, y0 + 6), g['short'], font=f, fill=col)
        print('measured', g['key'], g['name'], 'box', (round(x0), round(y0), round(x1), round(y1)))

    for wid, el in ways.items():
        gg = [p for p in (el.get('geometry') or []) if p]
        if len(gg) < 3:
            continue
        pts = [px(p['lon'], p['lat']) for p in gg]
        if max(p[0] for p in pts) < 0 or min(p[0] for p in pts) > 2 * HW:
            continue
        if max(p[1] for p in pts) < 0 or min(p[1] for p in pts) > 2 * HH:
            continue
        d.line(pts + [pts[0]], fill=(110, 235, 150), width=3)
        name = (el.get('tags') or {}).get('name')
        if not name:
            continue
        if wid == 682903087:
            name = '办公楼（里仁实验楼）'   # 用户第四轮口述改名
        mx = sum(p[0] for p in pts) / len(pts)
        my = sum(p[1] for p in pts) / len(pts)
        tb = d.textbbox((0, 0), name, font=f)
        d.rectangle([mx - 2, my - 2, mx + tb[2] + 4, my + tb[3] + 4], fill=(0, 0, 0))
        d.text((mx, my), name, font=f, fill=(255, 255, 150))
        print('osm', wid, name, 'at', (round(mx), round(my)))

    pad = 74
    panel = Image.new('RGB', (2 * HW, 2 * HH + pad), (6, 10, 16))
    panel.paste(img, (0, pad))
    d2 = ImageDraw.Draw(panel)
    d2.text((12, 6), '里仁片区：东侧=里仁实验楼 vs 西侧=办公楼（里仁实验楼）',
            font=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 26), fill=(255, 255, 255))
    d2.text((12, 44), '绿=OSM 有名建筑；洋红框=T18 里仁实验楼(影像量测)；青框=T19 图文信息楼(影像量测)',
            font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 18), fill=(185, 200, 220))
    panel.save(os.path.join(FIG, 'loc_liren.jpg'), quality=92)
    print('saved loc_liren.jpg', panel.size)


if __name__ == '__main__':
    main()
