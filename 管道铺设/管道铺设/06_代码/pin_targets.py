# -*- coding: utf-8 -*-
"""Pin the buildings the user named but that OSM has NOT drawn (or drew wrongly):

  C03 西区大食堂   — directly south of U02/U03 (user: "u03以及u02下方的大建筑")
  T17 材料A楼      — west of 材料B/C? (need to check; user did not claim this, drop it)
  T18 里仁实验楼   — beside 里仁教学楼
  C04 浴池         — near 8 组团 south / east of the canteen

Renders one graticule crop per target so the block can be read off and pinned, then writes
data/derived/pinned_targets.json.

Usage: python scripts/pin_targets.py
"""
import json
import math
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
HW, HH = 400, 310


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


def render(out, title, lat0, lon0, focus):
    cx, cy = merc_px(*wgs2gcj(lon0, lat0), Z)
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

    def px(lon, lat):
        X, Y = merc_px(*wgs2gcj(lon, lat), Z)
        return X - ox, Y - oy

    # valid OSM buildings around, for context
    with open(os.path.join(ROOT, 'data', 'derived', 'id_validation.json'), encoding='utf-8') as f:
        ok = {e['id']: e for e in json.load(f)['ok']}
    ways = G.load_ways()
    fnt = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 18)
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
        col = (110, 235, 150) if t.get('name') else (255, 190, 60)
        d.line(pts + [pts[0]], fill=col, width=3)
        if t.get('name'):
            d.text((min(p[0] for p in pts), min(p[1] for p in pts) - 20), t['name'][:12],
                   font=fnt, fill=col)

    # graticule 0.0005
    f2 = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 14)
    for k in range(-7, 8):
        la = round(lat0 + k * 0.0005, 5)
        X, Y = px(lon0, la)
        if 0 <= Y <= 2 * HH:
            d.line([(0, Y), (2 * HW, Y)], fill=(0, 230, 255), width=1)
            d.text((2, Y + 1), '%.4f' % la, font=f2, fill=(0, 230, 255))
    for k in range(-9, 10):
        lo = round(lon0 + k * 0.0005, 5)
        X, Y = px(lo, lat0)
        if 0 <= X <= 2 * HW:
            d.line([(X, 0), (X, 2 * HH)], fill=(0, 230, 255), width=1)
            d.text((X + 1, 2), '%.4f' % lo, font=f2, fill=(0, 230, 255))

    if focus:
        x0, y0 = px(focus[1], focus[3])
        x1, y1 = px(focus[2], focus[1])
        d.rectangle([x0, y0, x1, y1], outline=(255, 60, 60), width=4)

    pad = 74
    panel = Image.new('RGB', (2 * HW, 2 * HH + pad), (6, 10, 16))
    panel.paste(img, (0, pad))
    d2 = ImageDraw.Draw(panel)
    d2.text((12, 6), title, font=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 24),
            fill=(255, 255, 255))
    d2.text((12, 40), '青线=0.0005° 网格(约55m/42m)  绿=OSM有名  橙=OSM无名  红框=当前标注位置',
            font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 16), fill=(180, 200, 220))
    panel.save(os.path.join(FIG, out), quality=93)
    print('saved', out, panel.size)


if __name__ == '__main__':
    render('pin_canteen.jpg', '西区大食堂：核实真实位置（U02/U03 正南）',
           39.906100, 119.514600, None)
    render('pin_liren_lab.jpg', '里仁实验楼：核实位置（里仁教学楼旁）',
           39.904500, 119.522800, None)
    render('pin_bath.jpg', '浴池 / 材料A 区域核实',
           39.907300, 119.515800, None)
