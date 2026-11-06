# -*- coding: utf-8 -*-
"""Wide annotated maps of the NORTH part of the west campus + the 一教/二教 west block,
labelling EVERY building with its OSM name (or id when unnamed) so the user's verbal
description can be matched unambiguously.

Outputs
  docs/fig/verify_north_wide.jpg     north 家属区/里仁 ring, all buildings named
  docs/fig/verify_mech_wide.jpg      the block west of 一教/二教, all buildings named
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


def tile_store():
    s = {}
    for fn in os.listdir(TILES):
        m = re.match(r'(\d+)_(\d+)_(\d+)\.(jpg|png)$', fn)
        if m:
            s[(int(m.group(2)), int(m.group(3)))] = os.path.join(TILES, fn)
    return s


def render(out_name, title, sub, lat0, lon0, half, only_ids=None, min_area=120):
    st = tile_store()
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
        if only_ids and el['id'] not in only_ids:
            continue
        t = el.get('tags') or {}
        g = geo.get(el['id'], {}).get('geometry') or []
        if len(g) >= 3:
            pts = [px(p['lon'], p['lat']) for p in g]
            area = abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] -
                           pts[(i + 1) % len(pts)][0] * pts[i][1]
                           for i in range(len(pts)))) / 2 * (0.458 ** 2)
            if area < min_area:
                continue
            br = (t.get('building') or '')
            col = {'dormitory': (255, 90, 90), 'school': (95, 175, 255),
                   'university': (120, 220, 160), 'apartments': (255, 190, 70),
                   'yes': (200, 200, 210)}.get(br, (160, 170, 185))
            d.line(pts + [pts[0]], fill=col, width=3)
            items.append((t.get('name') or '', el['id'], X, Y, col, area))
        else:
            items.append((t.get('name') or '', el['id'], X, Y, (255, 255, 255), 0))

    items.sort(key=lambda t: t[3])
    used = []
    for name, oid, X, Y, col, area in items:
        lab = name if name else ('#%d' % oid)
        if len(lab) > 16:
            lab = lab[:16]
        yy = Y
        for _ in range(14):
            if all(abs(yy - uy) > 22 or abs(X - ux) > 110 for ux, uy in used):
                break
            yy += 22
        used.append((X, yy))
        fnt = font(19, True)
        tb = d.textbbox((0, 0), lab, font=fnt)
        d.rectangle([X - 2, yy - 1, X + tb[2] + 5, yy + tb[3] + 3], fill=(0, 0, 0))
        d.text((X + 1, yy), lab, font=fnt, fill=col)
        if abs(yy - Y) > 3:
            d.line([(X, Y), (X, yy)], fill=col, width=2)

    pad = 88
    panel = Image.new('RGB', (2 * half, 2 * half + pad), (6, 10, 16))
    panel.paste(img, (0, pad))
    d2 = ImageDraw.Draw(panel)
    d2.text((12, 8), title, font=font(28, True), fill=(255, 255, 255))
    d2.text((12, 48), sub, font=font(19), fill=(185, 200, 220))
    out = os.path.join(FIG, out_name)
    panel.save(out, quality=92)
    print('saved', out, panel.size, 'labelled', len(items))


if __name__ == '__main__':
    render('verify_north_wide.jpg',
           '北侧片区 全建筑标注（里仁学院 / 家属区一圈）',
           '红=宿舍 蓝=school(中/小学) 绿=university 橙=公寓 灰=yes；#id = OSM 无名建筑',
           39.915800, 119.508500, 520)
    render('verify_mech_wide.jpg',
           '一教/二教 西侧 全建筑标注（找"4 栋连在一起的建筑"= 燕山大学机械厂）',
           '红=宿舍 绿=university 灰=yes；#id = OSM 无名建筑',
           39.907500, 119.518500, 470)
