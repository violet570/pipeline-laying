# -*- coding: utf-8 -*-
"""Figure 7: functional zoning map — buildings coloured by campus zone, not by category.

The pipe-laying project cares less about "this is a dorm, that is a library" and more
about *groups of buildings that will be served together*.  This figure clusters the 50
groups into 5 service zones (by geography, matching the real campus layout) and shows
per-zone totals, so the MST work can be read zone by zone.

Output: docs/fig/fig7_zones_z17.jpg
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from groups import GROUPS, load_ways  # noqa: E402
from fig_campus_all import stitch, make_proj, wgs2gcj, merc_px  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')
FIG = os.path.join(ROOT, 'docs', 'fig')
FONTB = 'C:/Windows/Fonts/msyhbd.ttc'
FONT = 'C:/Windows/Fonts/msyh.ttc'

LAT0 = 39.9111
K_LAT = 111132.0
K_LON = 111320.0 * math.cos(math.radians(LAT0))

# zone assignment by key prefix / explicit list — geographic reading of the campus
ZONES = [
    ('A', '学生生活区（13 个组团公寓）', (255, 80, 80), [g['key'] for g in GROUPS if g['key'].startswith('D')]),
    ('B', '教学实验区（一~四教 / 里仁 / 电气 / 材料 / 经管）', (80, 165, 255),
     ['T01', 'T02', 'T03', 'T04', 'T05', 'T06', 'T07', 'T08', 'T09', 'T10', 'T11', 'T12', 'T13', 'T14', 'T15']),
    ('C', '公共核心区（图书馆 / 办公楼 / 活动中心 / 美术馆）', (90, 220, 160),
     ['T16', 'P01', 'P02', 'P03']),
    ('D', '后勤保障区（食堂 / 服务楼 / 变电站 / 废物暂存）', (255, 180, 40),
     ['C01', 'C02', 'P04', 'U15']),
    ('E', '待核实建筑（16 栋无名，需实地核对）', (185, 185, 200), None),
]


def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


def to_xy(lon, lat):
    return ((lon - 119.5172) * K_LON, (lat - LAT0) * K_LAT)


def main():
    ways = load_ways()
    img, z, x0, y0 = stitch('campus_sat_z17_full')
    proj = make_proj(z, x0, y0)
    img = Image.blend(img, Image.new('RGB', img.size, (10, 14, 20)), 0.42)
    d = ImageDraw.Draw(img)

    bnd = json.load(open(os.path.join(RAW, 'campus_boundary.json'), encoding='utf-8'))['elements']
    west_el = min(bnd, key=lambda e: (e['bounds']['minlon'] + e['bounds']['maxlon']) / 2)
    west = [(p['lon'], p['lat']) for p in west_el['geometry']]
    d.line([proj(*p) for p in west] + [proj(*west[0])], fill=(255, 215, 0), width=4)

    assigned = set()
    for _, _, _, keys in ZONES:
        if keys:
            assigned |= set(keys)
    rest = [g['key'] for g in GROUPS if g['key'] not in assigned]

    zone_of = {}
    for zk, zn, col, keys in ZONES:
        ks = keys if keys else rest
        for k in ks:
            zone_of[k] = (zk, zn, col)

    stats = {zk: dict(n=0, area=0.0, gh=0.0) for zk, _, _, _ in ZONES}
    labels = []
    for g in GROUPS:
        zk, zn, col = zone_of.get(g['key'], ('E', '待核实', (185, 185, 200)))
        pts = []
        area = 0.0
        for wid in g['ways']:
            el = ways.get(wid)
            if not el:
                continue
            pp = [to_xy(p['lon'], p['lat']) for p in (el.get('geometry') or []) if p]
            if len(pp) >= 3:
                a = 0.0
                for i in range(len(pp)):
                    a += pp[i][0] * pp[(i + 1) % len(pp)][1] - pp[(i + 1) % len(pp)][0] * pp[i][1]
                area += abs(a) / 2
                gpts = [proj(p['lon'], p['lat']) for p in el['geometry'] if p]
                d.line(gpts + [gpts[0]], fill=col, width=5)
                pts += gpts
        if pts:
            stats[zk]['n'] += 1
            stats[zk]['area'] += area
            stats[zk]['gh'] += area * g['levels']
            labels.append((g['short'], sum(p[0] for p in pts) / len(pts),
                           sum(p[1] for p in pts) / len(pts), col))

    labels.sort(key=lambda t: (t[2], t[1]))
    used = []
    for txt, px, py, col in labels:
        dy = py
        for _ in range(18):
            if all(abs(dy - uy) > 23 or abs(px - ux) > 92 for ux, uy in used):
                break
            dy += 23
        used.append((px, dy))
        fnt = font(20, True)
        tb = d.textbbox((0, 0), txt, font=fnt)
        d.rectangle([px - 2, dy - 1, px + tb[2] + 5, dy + tb[3] + 3], fill=(0, 0, 0))
        d.text((px + 2, dy), txt, font=fnt, fill=col)
        if abs(dy - py) > 2:
            d.line([(px + 2, py), (px + 2, dy)], fill=col, width=2)

    W, H = img.size
    d.rectangle([0, 0, W, 120], fill=(6, 10, 16))
    d.text((26, 14), '燕山大学西校区 建筑群分区图（5 个供水分区 / 50 组建筑）',
           font=font(46, True), fill=(255, 255, 255))
    d.text((26, 74), '按地理邻近与功能切成 5 个分区，可直接对应"分区加压 / 分区计量"的真实给水做法',
           font=font(26), fill=(190, 205, 225))

    # stats table
    tx, ty = W - 700, 150
    d.rectangle([tx, ty, W - 24, ty + 44 + 34 * len(ZONES)], fill=(6, 10, 16))
    d.text((tx + 16, ty + 8), '分区规模', font=font(28, True), fill=(255, 255, 255))
    d.text((tx + 16, ty + 44), '分组   栋数   底面积 m²   总建筑面积 m²', font=font(19), fill=(150, 165, 185))
    for i, (zk, zn, col, _) in enumerate(ZONES):
        s = stats[zk]
        yy = ty + 70 + i * 34
        d.line([(tx + 16, yy + 11), (tx + 52, yy + 11)], fill=col, width=6)
        d.text((tx + 62, yy), '%-3s  %3d   %9.0f   %11.0f' % (zk, s['n'], s['area'], s['gh']),
               font=font(20), fill=(225, 232, 242))

    # legend
    ly = H - 300
    d.rectangle([26, ly, 560, H - 54], fill=(6, 10, 16))
    d.text((40, ly + 8), '分区图例', font=font(28, True), fill=(255, 255, 255))
    for i, (zk, zn, col, _) in enumerate(ZONES):
        yy = ly + 50 + i * 46
        d.line([(42, yy + 11), (102, yy + 11)], fill=col, width=7)
        d.text((112, yy), '%s %s' % (zk, zn), font=font(21), fill=(220, 228, 240))
    d.text((26, H - 42),
           '矢量 © OpenStreetMap contributors (ODbL) ｜ 影像 © 高德地图 ｜ 分区为本项目按地理邻近划分',
           font=font(20), fill=(200, 210, 225))

    out = os.path.join(FIG, 'fig7_zones_z17.jpg')
    img.save(out, quality=90)
    print('saved', out, img.size)
    for zk, zn, _, _ in ZONES:
        s = stats[zk]
        print('%-2s %-40s n=%2d area=%7.0f gh=%8.0f' % (zk, zn, s['n'], s['area'], s['gh']))


if __name__ == '__main__':
    main()
