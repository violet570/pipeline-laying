# -*- coding: utf-8 -*-
"""Generic 'read the coordinates off a graticule' tile renderer with OSM outlines.

usage: python scripts/loc_grid2.py <lat> <lon> <hw> <hh> <out.jpg> <title> [scale]
Prints nothing but the saved path; grid step 0.0002 deg (~22 m lat).
"""
import json
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


def main():
    lat0, lon0 = float(sys.argv[1]), float(sys.argv[2])
    hw, hh = int(sys.argv[3]), int(sys.argv[4])
    out, title = sys.argv[5], sys.argv[6]
    scale = int(sys.argv[7]) if len(sys.argv) > 7 else 1

    cx, cy = merc_px(*wgs2gcj(lon0, lat0), Z)
    st = {}
    for fn in os.listdir(TILES):
        p = fn.replace('.jpg', '').split('_')
        if len(p) == 3:
            st[(int(p[1]), int(p[2]))] = os.path.join(TILES, fn)
    ox, oy = int(cx) - hw, int(cy) - hh
    img = Image.new('RGB', (2 * hw, 2 * hh), (10, 12, 16))
    for tx in range(ox // 256, (int(cx) + hw) // 256 + 1):
        for ty in range(oy // 256, (int(cy) + hh) // 256 + 1):
            fp = st.get((tx, ty))
            if fp:
                img.paste(Image.open(fp).convert('RGB'), (tx * 256 - ox, ty * 256 - oy))
    if scale > 1:
        img = img.resize((2 * hw * scale, 2 * hh * scale), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 15)

    def px(lon, lat):
        X, Y = merc_px(*wgs2gcj(lon, lat), Z)
        return (X - ox) * scale, (Y - oy) * scale

    ways = G.load_ways()
    for wid, el in ways.items():
        gg = [p for p in (el.get('geometry') or []) if p]
        if len(gg) < 3:
            continue
        pts = [px(p['lon'], p['lat']) for p in gg]
        if max(p[0] for p in pts) < 0 or min(p[0] for p in pts) > 2 * hw * scale:
            continue
        if max(p[1] for p in pts) < 0 or min(p[1] for p in pts) > 2 * hh * scale:
            continue
        t = el.get('tags') or {}
        name = t.get('name')
        col = (110, 235, 150) if name else (255, 185, 60)
        d.line(pts + [pts[0]], fill=col, width=3 if scale == 1 else 2)
        lab = name or '#%d' % wid
        mx = sum(p[0] for p in pts) / len(pts)
        my = sum(p[1] for p in pts) / len(pts)
        tb = d.textbbox((0, 0), lab, font=f)
        d.rectangle([mx - 2, my - 2, mx + tb[2] + 4, my + tb[3] + 4], fill=(0, 0, 0))
        d.text((mx, my), lab, font=f, fill=(255, 245, 200) if name else (255, 205, 120))

    # graticule
    step = 0.0002
    g = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 14)
    for k in range(-24, 25):
        la = round(lat0 + k * step, 5)
        if abs(la) > 85:
            continue
        X, Y = px(lon0, la)
        if 0 <= Y <= 2 * hh * scale:
            d.line([(0, Y), (2 * hw * scale, Y)], fill=(0, 220, 220), width=1)
            d.text((2, Y + 1), '%.4f' % la, font=g, fill=(0, 230, 230))
        lo = round(lon0 + k * step, 5)
        X2, Y2 = px(lo, lat0)
        if 0 <= X2 <= 2 * hw * scale:
            d.line([(X2, 0), (X2, 2 * hh * scale)], fill=(0, 220, 220), width=1)
            d.text((X2 + 2, 2), '%.4f' % lo, font=g, fill=(0, 230, 230))

    pad = 70
    panel = Image.new('RGB', (2 * hw * scale, 2 * hh * scale + pad), (6, 10, 16))
    panel.paste(img, (0, pad))
    d2 = ImageDraw.Draw(panel)
    d2.text((10, 6), title, font=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 24),
            fill=(255, 255, 255))
    d2.text((10, 42), '绿=OSM 有名  橙=OSM 无名(#id)  青网格 0.0002°(纬 22 m / 经 17 m)',
            font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 16), fill=(185, 200, 220))
    panel.save(os.path.join(FIG, out), quality=93)
    print('saved', out, panel.size)


if __name__ == '__main__':
    main()
