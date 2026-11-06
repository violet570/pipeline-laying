# -*- coding: utf-8 -*-
"""Figure 5: whole west campus, ALL building clusters labelled, z17 satellite base.

Uses data/tiles/campus_sat_z17_full (110 tiles, covers 119.5045-119.5325 x 39.9010-39.9199)
so that 图书馆 / 里仁楼 / 高压中心 / 活动中心 / 国际学院 / 体育馆 等都在图内。

Outputs
  docs/fig/fig5_campus_all_buildings_z17.jpg   full campus, all 72 buildings + 50 groups
  docs/fig/fig5b_campus_all_buildings_road.png  same, 高德路网底图（中文字标注，便于对外展示）
"""
import json
import math
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from groups import GROUPS, load_ways  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')
TILES = os.path.join(ROOT, 'data', 'tiles')
FIG = os.path.join(ROOT, 'docs', 'fig')
FONT = 'C:/Windows/Fonts/msyh.ttc'
FONTB = 'C:/Windows/Fonts/msyhbd.ttc'


def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


A = 6378245.0
EE = 0.00669342162296594323


def _tlat(x, y):
    r = (-100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x)))
    r += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    r += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    r += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return r


def _tlon(x, y):
    r = (300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x)))
    r += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    r += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    r += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return r


def wgs2gcj(lon, lat):
    dlat, dlon = _tlat(lon - 105.0, lat - 35.0), _tlon(lon - 105.0, lat - 35.0)
    rad = lat / 180.0 * math.pi
    magic = 1 - EE * math.sin(rad) ** 2
    sm = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sm) * math.pi)
    dlon = (dlon * 180.0) / (A / sm * math.cos(rad) * math.pi)
    return lon + dlon, lat + dlat


def load(name):
    with open(os.path.join(RAW, name), encoding='utf-8') as f:
        return json.load(f)


def stitch(job):
    d = os.path.join(TILES, job)
    pos = {}
    z = None
    for fn in os.listdir(d):
        m = re.match(r'(\d+)_(\d+)_(\d+)\.(jpg|png)$', fn)
        if m:
            z, x, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            pos[(x, y)] = os.path.join(d, fn)
    xs = sorted({p[0] for p in pos})
    ys = sorted({p[1] for p in pos})
    x0, y0 = xs[0], ys[0]
    img = Image.new('RGB', ((xs[-1] - x0 + 1) * 256, (ys[-1] - y0 + 1) * 256), (24, 26, 30))
    for (x, y), fp in pos.items():
        img.paste(Image.open(fp).convert('RGB'), ((x - x0) * 256, (y - y0) * 256))
    return img, z, x0, y0


def merc_px(lon, lat, z):
    n = 256.0 * (2 ** z)
    s = math.sin(lat * math.pi / 180.0)
    return (lon + 180.0) / 360.0 * n, (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n


def make_proj(z, x0, y0, ox=0, oy=0):
    def f(lon, lat):
        X, Y = merc_px(*wgs2gcj(lon, lat), z)
        return X - x0 * 256 - ox, Y - y0 * 256 - oy
    return f


CAT_STYLE = {
    'dorm': ((255, 72, 72), 4),
    'canteen': ((255, 170, 30), 4),
    'teaching': ((70, 160, 255), 4),
    'college': ((0, 215, 220), 4),
    'library': ((120, 150, 255), 4),
    'lab': ((200, 130, 255), 4),
    'office': ((150, 210, 90), 4),
    'activity': ((250, 120, 200), 4),
    'art': ((235, 155, 120), 4),
    'service': ((255, 225, 110), 4),
    'utility': ((175, 175, 175), 4),
    'other': ((210, 215, 225), 3),
}


def centroid(g):
    return (sum(p['lat'] for p in g) / len(g), sum(p['lon'] for p in g) / len(g))


def render(bg_job, out_name, blend, title, subtitle):
    ways = load_ways()
    bnd = load('campus_boundary.json')['elements']
    west_el = min(bnd, key=lambda e: (e['bounds']['minlon'] + e['bounds']['maxlon']) / 2)
    west = [(p['lon'], p['lat']) for p in west_el['geometry']]

    img, z, x0, y0 = stitch(bg_job)
    print(bg_job, 'mosaic', img.size, 'z', z)
    proj = make_proj(z, x0, y0)
    canvas = img
    if blend > 0:
        canvas = Image.blend(canvas, Image.new('RGB', canvas.size, (8, 12, 18)), blend)
    d = ImageDraw.Draw(canvas)

    # boundary
    d.line([proj(*p) for p in west] + [proj(*west[0])], fill=(255, 215, 0), width=4)

    # all building outlines (thin)
    for el in ways.values():
        g = [p for p in (el.get('geometry') or []) if p]
        if len(g) >= 3:
            d.line([proj(p['lon'], p['lat']) for p in g] + [proj(g[0]['lon'], g[0]['lat'])],
                   fill=(150, 168, 190), width=2)

    placed = []
    for grp in GROUPS:
        color, w = CAT_STYLE.get(grp['cat'], ((200, 200, 200), 3))
        cs = []
        for wid in grp['ways']:
            el = ways.get(wid)
            if not el:
                continue
            g = [p for p in (el.get('geometry') or []) if p]
            if len(g) < 3:
                continue
            d.line([proj(p['lon'], p['lat']) for p in g] + [proj(g[0]['lon'], g[0]['lat'])],
                   fill=color, width=w)
            cs.append(centroid(g))
        if cs:
            placed.append((grp, proj(sum(c[1] for c in cs) / len(cs), sum(c[0] for c in cs) / len(cs)), color))

    placed.sort(key=lambda t: (t[1][1], t[1][0]))
    used = []
    for grp, (px, py), color in placed:
        dy = py
        for _ in range(16):
            if all(abs(dy - uy) > 24 or abs(px - ux) > 96 for ux, uy in used):
                break
            dy += 24
        used.append((px, dy))
        txt = grp['short']
        fnt = font(21, True)
        tb = d.textbbox((0, 0), txt, font=fnt)
        d.rectangle([px - 2, dy - 1, px + tb[2] + 5, dy + tb[3] + 3], fill=(0, 0, 0))
        d.text((px + 2, dy), txt, font=fnt, fill=color)
        if abs(dy - py) > 2:
            d.line([(px + 2, py), (px + 2, dy)], fill=color, width=2)

    W, H = canvas.size
    d.rectangle([0, 0, W, 118], fill=(6, 10, 16))
    d.text((26, 14), title, font=font(46, True), fill=(255, 255, 255))
    d.text((26, 72), subtitle, font=font(26), fill=(190, 205, 225))

    lx, ly = 26, H - 330
    d.rectangle([lx, ly, lx + 470, H - 54], fill=(6, 10, 16))
    d.text((lx + 14, ly + 8), '图例', font=font(28, True), fill=(255, 255, 255))
    legend = [('dorm', '学生公寓 13 组团 / 34 栋'), ('teaching', '教学·学院 / 实验楼'),
              ('canteen', '食堂 · 服务楼'), ('library', '图书馆'),
              ('office', '办公 / 活动中心 / 美术馆'), ('other', '未命名建筑（待核实）')]
    for i, (cat, txt) in enumerate(legend):
        yy = ly + 50 + i * 36
        d.line([(lx + 18, yy + 10), (lx + 78, yy + 10)], fill=CAT_STYLE[cat][0], width=5)
        d.text((lx + 92, yy), txt, font=font(23), fill=(222, 230, 242))
    d.text((26, H - 40),
           '轮廓/名称：OpenStreetMap © contributors (ODbL) ｜ 影像：高德地图（仅对照/署名）｜ 快照 2026-08',
           font=font(21), fill=(200, 210, 225))

    out = os.path.join(FIG, out_name)
    if canvas.width > 3000:
        canvas = canvas.resize((3000, int(canvas.height * 3000 / canvas.width)), Image.LANCZOS)
    canvas.save(out, quality=90)
    print('saved', out, canvas.size)


if __name__ == '__main__':
    n_ways = len(load_ways())
    render('campus_sat_z17_full', 'fig5_campus_all_buildings_z17.jpg', 0.30,
           '燕山大学西校区 全建筑群调研图（%d 组 / %d 栋单体）' % (len(GROUPS), n_ways),
           'OSM 矢量 × 高德卫星 z17（WGS-84→GCJ-02 校正叠加）；边界黄线 = OSM 西校区范围')
    render('campus_road_z17_full', 'fig5b_campus_all_buildings_road.jpg', 0.0,
           '燕山大学西校区 全建筑群调研图（高德路网底图版）',
           '同一批 OSM 轮廓叠加高德标准路网图，便于与校名/道路名称对照')
