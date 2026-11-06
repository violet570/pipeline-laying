# -*- coding: utf-8 -*-
"""Locate the 4 buildings the user just circled on two screenshots:
  (a) 西校区第四体育场体育馆  - the hall next to 第四体育场 (the oval track)
  (b) 音乐厅                  - the building next to 美术馆
  (c) 生命健康与智能医学学院   - the building above (north of) 经管楼
  (d) 艺术与设计学院          - the small block at the very top of the 美术馆 complex

Renders every OSM building polygon in the bbox with its name (or #id) so we can match
the screenshots one-to-one.  Out: docs/fig/loc_north_gallery.jpg
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
LAT0, LON0 = 39.912200, 119.512600
HW, HH = 780, 560


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
    f = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 17)

    def px(lon, lat):
        X, Y = merc_px(*wgs2gcj(lon, lat), Z)
        return X - ox, Y - oy

    # pitch / track polygons for orientation
    try:
        import json
        with open(os.path.join(ROOT, 'data', 'raw', 'areas_geom.json'), encoding='utf-8') as fh:
            ar = json.load(fh)
        els = ar['elements'] if isinstance(ar, dict) else ar
    except Exception as e:
        print('areas skipped', e)
        els = []
    for el in els:
        t = el.get('tags') or {}
        if t.get('leisure') not in ('pitch', 'track', 'sports_centre', 'stadium'):
            continue
        gg = [p for p in (el.get('geometry') or []) if p]
        if len(gg) < 3:
            continue
        pts = [px(p['lon'], p['lat']) for p in gg]
        if max(p[0] for p in pts) < 0 or min(p[0] for p in pts) > 2 * HW:
            continue
        if max(p[1] for p in pts) < 0 or min(p[1] for p in pts) > 2 * HH:
            continue
        d.line(pts + [pts[0]], fill=(90, 180, 255), width=2)
        nm = t.get('name') or t.get('sport') or 'pitch'
        mx = sum(p[0] for p in pts) / len(pts)
        my = sum(p[1] for p in pts) / len(pts)
        d.text((mx, my), nm, font=f, fill=(140, 200, 255))
        print('area', el['id'], nm)

    ways = G.load_ways()
    for wid, el in ways.items():
        gg = [p for p in (el.get('geometry') or []) if p]
        if len(gg) < 3:
            continue
        pts = [px(p['lon'], p['lat']) for p in gg]
        if max(p[0] for p in pts) < 0 or min(p[0] for p in pts) > 2 * HW:
            continue
        if max(p[1] for p in pts) < 0 or min(p[1] for p in pts) > 2 * HH:
            continue
        t = el.get('tags') or {}
        name = t.get('name')
        col = (110, 235, 150) if name else (255, 185, 60)
        d.line(pts + [pts[0]], fill=col, width=3)
        lab = name or '#%d' % wid
        mx = sum(p[0] for p in pts) / len(pts)
        my = sum(p[1] for p in pts) / len(pts)
        tb = d.textbbox((0, 0), lab, font=f)
        d.rectangle([mx - 2, my - 2, mx + tb[2] + 4, my + tb[3] + 4], fill=(0, 0, 0))
        d.text((mx, my), lab, font=f, fill=(255, 245, 200) if name else (255, 205, 120))
        print('osm', wid, lab, 'at %.5f,%.5f' % (0, 0))

    pad = 76
    panel = Image.new('RGB', (2 * HW, 2 * HH + pad), (6, 10, 16))
    panel.paste(img, (0, pad))
    d2 = ImageDraw.Draw(panel)
    d2.text((12, 6), '定位四栋：第四体育场体育馆 / 音乐厅 / 生命健康与智能医学学院 / 艺术与设计学院',
            font=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 26), fill=(255, 255, 255))
    d2.text((12, 44), '绿=OSM 有名建筑  橙=OSM 无名建筑(#id)  蓝=运动场地',
            font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 18), fill=(185, 200, 220))
    panel.save(os.path.join(FIG, 'loc_north_gallery.jpg'), quality=92)
    print('saved loc_north_gallery.jpg', panel.size)


if __name__ == '__main__':
    main()
