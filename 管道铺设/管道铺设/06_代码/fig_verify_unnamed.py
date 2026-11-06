# -*- coding: utf-8 -*-
"""Locate the unnamed buildings the user described, by rendering zoomed z18 crops with
every candidate way outlined and its OSM id printed, so the user's verbal description
("4 connected buildings beside the 一教/二教 road", "3 buildings inside the circular
plaza at the very top") can be matched to specific way ids.

Outputs
  docs/fig/verify_A_mechplant.jpg   area west of 一教/二教  (燕山大学机械厂 candidates)
  docs/fig/verify_B_north_circle.jpg  north circular plaza (three 学院 candidates)
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
FONT = 'C:/Windows/Fonts/msyh.ttc'
Z = 18


def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


def store():
    s = {}
    for fn in os.listdir(TILES):
        m = re.match(r'(\d+)_(\d+)_(\d+)\.(jpg|png)$', fn)
        if m:
            s[(int(m.group(2)), int(m.group(3)))] = os.path.join(TILES, fn)
    return s


def render(out_name, title, sub, lat0, lon0, half, draw_ids, extra_polys=()):
    st = store()
    cx, cy = merc_px(*wgs2gcj(lon0, lat0), Z)
    cxi, cyi = int(cx), int(cy)
    img = Image.new('RGB', (2 * half, 2 * half), (18, 20, 24))
    ox, oy = cxi - half, cyi - half
    for tx in range(ox // 256, (cxi + half) // 256 + 1):
        for ty in range(oy // 256, (cyi + half) // 256 + 1):
            fp = st.get((tx, ty))
            if fp:
                img.paste(Image.open(fp).convert('RGB'),
                          (tx * 256 - ox, ty * 256 - oy))
    d = ImageDraw.Draw(img)

    def px(lon, lat):
        X, Y = merc_px(*wgs2gcj(lon, lat), Z)
        return X - ox, Y - oy

    with open(os.path.join(RAW, 'buildings.json'), encoding='utf-8') as f:
        big = json.load(f)['elements']
    with open(os.path.join(RAW, 'verify_2026.json'), encoding='utf-8') as f:
        ver = json.load(f)['buildings']

    # geometry only exists in buildings.json (verify_2026 has center only), so draw from
    # buildings.json and annotate ids; the ids we care about come from verify_2026.
    seen = set()
    for el in big:
        g = [p for p in (el.get('geometry') or []) if p]
        if len(g) < 3 or el['id'] in seen:
            continue
        seen.add(el['id'])
        pts = [px(p['lon'], p['lat']) for p in g]
        if not draw_ids or el['id'] in draw_ids:
            col = (255, 60, 60) if el['id'] in draw_ids else (120, 140, 165)
            wd = 4 if el['id'] in draw_ids else 2
            d.line(pts + [pts[0]], fill=col, width=wd)
            if el['id'] in draw_ids:
                mx = sum(p[0] for p in pts) / len(pts)
                my = sum(p[1] for p in pts) / len(pts)
                lab = str(el['id'])
                tb = d.textbbox((0, 0), lab, font=font(22, True))
                d.rectangle([mx - 3, my - 2, mx + tb[2] + 5, my + tb[3] + 4], fill=(0, 0, 0))
                d.text((mx, my), lab, font=font(22, True), fill=(255, 255, 120))

    pad = 92
    panel = Image.new('RGB', (2 * half, 2 * half + pad), (6, 10, 16))
    panel.paste(img, (0, pad))
    d2 = ImageDraw.Draw(panel)
    d2.text((12, 10), title, font=font(30, True), fill=(255, 255, 255))
    d2.text((12, 52), sub, font=font(20), fill=(185, 200, 220))
    out = os.path.join(FIG, out_name)
    panel.save(out, quality=92)
    print('saved', out, panel.size)


if __name__ == '__main__':
    # A: the 4 connected buildings west of 一教/二教 (candidates from verify)
    render('verify_A_mechplant.jpg',
           '候选 A：一教/二教西侧道路旁的 4 栋连体建筑（燕山大学机械厂？）',
           '红框 = OSM 无名 building=university；核对哪 4 栋是连着的一排',
           39.904300, 119.516400, 300,
           {696279410, 696279411, 696279413, 696279414, 696279416, 1226592983})
    # B: north circular plaza — three 学院
    render('verify_B_north_circle.jpg',
           '候选 B：北侧圆形广场区域（信息科学与工程学院 / 人工智能学院 / 理学院？）',
           'OSM 此处只标了 砺金楼/鹏志楼/艺术楼/体育馆/科技楼，三个学院可能未被标注',
           39.915600, 119.508300, 380, set())
