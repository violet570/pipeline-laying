# -*- coding: utf-8 -*-
"""List every named building in buildings_full.json (wide-bbox OSM pull) with area/center."""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
K_LAT = 111320.0
K_LON = 111320.0 * 0.7675


def area(geom):
    if not geom or len(geom) < 3:
        return 0.0
    lat0 = geom[0]['lat']
    lon0 = geom[0]['lon']
    pts = [((p['lon'] - lon0) * K_LON, (p['lat'] - lat0) * K_LAT) for p in geom]
    s = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def main():
    with open(os.path.join(ROOT, 'data', 'raw', 'buildings_full.json'), encoding='utf-8') as f:
        els = json.load(f)['elements']
    seen = {}
    for el in els:
        seen.setdefault(el['id'], el)
    rows = []
    for wid, el in seen.items():
        t = el.get('tags') or {}
        nm = t.get('name')
        if not nm:
            continue
        g = [p for p in (el.get('geometry') or []) if p]
        if len(g) < 3:
            continue
        la = sum(p['lat'] for p in g) / len(g)
        lo = sum(p['lon'] for p in g) / len(g)
        rows.append((nm, wid, area(g), la, lo))
    rows.sort(key=lambda r: -r[3])
    for nm, wid, a, la, lo in rows:
        print('%-28s %-11d %8.0f m2  %.6f,%.6f' % (nm, wid, a, la, lo))
    print('total named', len(rows))


if __name__ == '__main__':
    main()
