# -*- coding: utf-8 -*-
"""Cross-check the campus registry against AMap POIs.

Converts AMap GCJ-02 POI locations to WGS-84 and finds the nearest registry group,
reporting the offset in metres. Also prints AMap POIs that have no registry match.

usage: python scripts/amap_crosscheck.py [json]
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import groups as G  # noqa: E402

K_LAT = 111320.0
K_LON = 111320.0 * 0.7675


def gcj2wgs(lon, lat):
    a = 6378245.0
    ee = 0.00669342162296594323

    def tlat(x, y):
        r = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
        r += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        r += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
        r += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
        return r

    def tlon(x, y):
        r = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
        r += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        r += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
        r += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
        return r

    dlat = tlat(lon - 105.0, lat - 35.0)
    dlon = tlon(lon - 105.0, lat - 35.0)
    rad = math.radians(lat)
    magic = 1 - ee * math.sin(rad) ** 2
    sq = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sq) * math.pi)
    dlon = (dlon * 180.0) / (a / sq * math.cos(rad) * math.pi)
    return lon - dlon, lat - dlat


def group_center(g):
    m = g.get('measured')
    if m:
        return m['lat'], m['lon'], 'measured'
    ways = G.load_ways()
    pts = []
    for w in g['ways']:
        el = ways.get(w)
        if not el:
            continue
        pts += [(p['lat'], p['lon']) for p in (el.get('geometry') or []) if p]
    if not pts:
        return None
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts), 'osm')


def dist_m(lat1, lon1, lat2, lon2):
    dy = (lat1 - lat2) * K_LAT
    dx = (lon1 - lon2) * K_LON
    return math.hypot(dx, dy)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else 'data/derived/amap_around_燕山大学.json'
    with open(os.path.join(ROOT, src), encoding='utf-8') as f:
        pois = json.load(f)
    centres = []
    for g in G.GROUPS:
        c = group_center(g)
        if c:
            centres.append((g, c[0], c[1], c[2]))

    rows = []
    for p in pois:
        loc = p.get('location') or ''
        if ',' not in loc:
            continue
        glon, glat = [float(v) for v in loc.split(',')]
        lon, lat = gcj2wgs(glon, glat)
        best = None
        for g, cla, clo, src2 in centres:
            d = dist_m(lat, lon, cla, clo)
            if best is None or d < best[0]:
                best = (d, g, src2)
        rows.append((best[0], p.get('name', ''), lat, lon, best[1]['name'],
                     best[1]['key'], best[2]))

    rows.sort(key=lambda r: r[0])
    print('%-34s %-12s %-22s %s' % ('高德 POI', 'Δ(m)', '注册表最近条目', 'WGS 坐标'))
    for d, nm, lat, lon, rn, rk, s2 in rows:
        flag = '' if d < 80 else ('  <<<' if d < 300 else '  <<<<<')
        print('%-34s %8.1f %-22s %.6f,%.6f [%s]%s'
              % (nm[:34], d, rn[:22], lat, lon, s2, flag))
    print()
    print('高德 POI 共 %d 个；与注册表最近条目距离 >80 m 的 %d 个'
          % (len(rows), sum(1 for r in rows if r[0] > 80)))


if __name__ == '__main__':
    main()
