# -*- coding: utf-8 -*-
"""Proof figure for the 4 buildings the user circled in round 5.

Two panels are saved:
  docs/fig/proof_four_gallery.jpg  - 音乐厅 / 生命健康与智能医学学院 / 艺术与设计学院
  docs/fig/proof_four_gym.jpg      - 西校区第四体育场体育馆
Each measured entry is drawn as a box with its short label inside.
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


def render(out, title, sub, lat0, lon0, hw, hh, keys, legend=()):
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
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 18)

    def px(lon, lat):
        X, Y = merc_px(*wgs2gcj(lon, lat), Z)
        return X - ox, Y - oy

    ways = G.load_ways()
    for g in G.GROUPS:
        if g['key'] not in keys:
            continue
        m = g.get('measured')
        if not m:
            continue
        x0, y0 = px(m['bbox'][0], m['bbox'][3])
        x1, y1 = px(m['bbox'][2], m['bbox'][1])
        d.rectangle([x0, y0, x1, y1], outline=(255, 70, 220), width=4)
        d.rectangle([x0 + 4, y0 + 4, x0 + 16 + 19 * len(g['short']), y0 + 30], fill=(0, 0, 0))
        d.text((x0 + 8, y0 + 6), g['short'], font=f, fill=(255, 240, 160))
    # OSM named neighbours for orientation
    for wid, el in ways.items():
        gg = [p for p in (el.get('geometry') or []) if p]
        if len(gg) < 3:
            continue
        pts = [px(p['lon'], p['lat']) for p in gg]
        if max(p[0] for p in pts) < 0 or min(p[0] for p in pts) > 2 * hw:
            continue
        if max(p[1] for p in pts) < 0 or min(p[1] for p in pts) > 2 * hh:
            continue
        t = el.get('tags') or {}
        d.line(pts + [pts[0]], fill=(110, 235, 150), width=2)
        if t.get('name'):
            mx = sum(p[0] for p in pts) / len(pts)
            my = sum(p[1] for p in pts) / len(pts)
            tb = d.textbbox((0, 0), t['name'], font=f)
            d.rectangle([mx - 2, my - 2, mx + tb[2] + 4, my + tb[3] + 4], fill=(0, 0, 0))
            d.text((mx, my), t['name'], font=f, fill=(200, 255, 200))

    pad = 74
    bot = 30 + 26 * len(legend)
    panel = Image.new('RGB', (2 * hw, 2 * hh + pad + bot), (6, 10, 16))
    panel.paste(img, (0, pad))
    d2 = ImageDraw.Draw(panel)
    d2.text((12, 6), title, font=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 26),
            fill=(255, 255, 255))
    d2.text((12, 44), sub, font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 18),
            fill=(185, 200, 220))
    for i, ln in enumerate(legend):
        d2.text((12, pad + 2 * hh + 8 + i * 26), ln,
                font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 18), fill=(200, 210, 230))
    panel.save(os.path.join(FIG, out), quality=93)
    print('saved', out, panel.size)


if __name__ == '__main__':
    render('proof_four_gallery.jpg',
           '美术馆/经管楼一带三栋（官方 3D 图已核对名称）',
           '洋红框=影像量测位置；绿=OSM 有名建筑（作参照）',
           39.913400, 119.515200, 430, 380, {'N02', 'N03', 'N04'},
           legend=['N02 音乐馆（燕山大学音乐厅）—— 美术馆组群东侧',
                   'N03 生命健康与智能医学学院 —— 经管楼东北、原 OSM「国际学院」那栋',
                   'N04 艺术与设计学院 —— 美术馆组群东北翼'])
    render('proof_four_gym.jpg',
           '第四体育场旁的新体育馆（官方名为「西校区新体育馆」）',
           '洋红框=影像量测位置；绿=OSM 有名建筑（作参照）',
           39.912300, 119.510300, 330, 230, {'N01'},
           legend=['N01 西校区新体育馆 —— 紧邻第四体育场西北侧的白色大跨屋顶建筑'])
