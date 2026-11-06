# -*- coding: utf-8 -*-
"""Locate the buildings the user says are mislabelled / missing, and dump their geometry
so we can decide which OSM way each one actually is.

Targets from the user's correction:
  1. 西区大食堂 vs 燕园餐厅 — two different canteens
  2. 信息科学与工程学院 / 人工智能学院(软件学院) / 理学院 — 3 buildings inside the
     circular plaza at the TOP of the figure
  3. 燕山大学机械厂 — 4 connected buildings beside the 一教/二教 road
  4. 里仁实验楼 — next to 里仁教学楼
  5. 第四体育场 / 体育馆 — beside the 操场

Method: for each named target we have a coordinate or an anchor; we list every building
whose centroid falls inside a small radius, with area + tags, so the match is auditable.
Output: data/derived/verify_targets.txt
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')
DER = os.path.join(ROOT, 'data', 'derived')

LAT0, LON0 = 39.9111, 119.5172
K_LAT = 111132.0
K_LON = 111320.0 * math.cos(math.radians(LAT0))


def xy(lon, lat):
    return ((lon - LON0) * K_LON, (lat - LAT0) * K_LAT)


def area_m2(geom):
    pts = [xy(p['lon'], p['lat']) for p in geom]
    if len(pts) < 3:
        return 0.0
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2


def load(name):
    with open(os.path.join(RAW, name), encoding='utf-8') as f:
        return json.load(f)


def main():
    v = load('verify_2026.json')
    els = v['buildings']
    L = []
    A = L.append

    def dump(title, lat, lon, r, note=''):
        A('=== %s  (near %.6f, %.6f, r=%.0f m) %s' % (title, lat, lon, r, note))
        A('%-12s %-30s %-10s %6s  %11s %11s' % ('id', 'name', 'building', 'levels', 'lat', 'lon'))
        cx, cy = xy(lon, lat)
        hits = []
        for e in els:
            c = e.get('center') or {}
            if not c:
                continue
            ex, ey = xy(c['lon'], c['lat'])
            d = math.hypot(ex - cx, ey - cy)
            if d <= r:
                t = e.get('tags') or {}
                hits.append((d, e['id'], t.get('name', ''), t.get('building', ''),
                             t.get('building:levels', ''), c['lat'], c['lon']))
        hits.sort()
        for d, i, n, b, lv, la, lo in hits:
            A('%-12s %-30s %-10s %6s  %.6f %.6f   d=%.0f' % (
                i, (n or '(无名)')[:30], b, lv, la, lo, d))
        A('')
        return hits

    # ---- 1. 两个食堂 ----
    dump('燕大西校区大食堂 (真实西区大食堂, 用户指出)', 39.906287, 119.514809, 60)
    dump('燕大西区燕园餐厅 (燕园食堂)', 39.909369, 119.512799, 60)
    # ---- 2. 西侧 4 栋连体 (用户说是一教二教道路旁) 疑似机械厂 ----
    dump('西侧 4 栋连体楼群 (一教二教西侧道路旁)', 39.904500, 119.516100, 170,
         '候选: 未命名 university 一排')
    # ---- 3. 里仁实验楼 / 图文信息楼 ----
    dump('里仁实验楼', 39.904156, 119.523694, 50)
    dump('图文信息楼', 39.903454, 119.521544, 50)
    # ---- 4. 体育场 ----
    dump('操场旁 (第四体育场 / 体育馆)', 39.912542, 119.510683, 130)
    dump('北侧圆形广场区域 (用户说 3 个学院在此)', 39.9155, 119.5095, 260,
         '北侧 里仁学院片区')
    # ---- 5. 材料A / 浴池 ----
    dump('材料A楼', 39.907081, 119.517184, 40)
    dump('燕大西区浴池', 39.907329, 119.514442, 40)
    # ---- 6. 新发现的其它建筑 ----
    dump('图书馆周边', 39.909003, 119.526931, 120)

    p = os.path.join(DER, 'verify_targets.txt')
    with open(p, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')
    print('->', p)
    print('lines', len(L))


if __name__ == '__main__':
    main()
