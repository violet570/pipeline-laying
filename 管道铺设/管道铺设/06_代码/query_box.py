# -*- coding: utf-8 -*-
"""List every OSM building whose centroid falls in a small bbox, with name/levels/area.

usage: python scripts/query_box.py <south> <west> <north> <east> [out.txt]
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def poly_area(geom):
    lat0 = sum(p['lat'] for p in geom) / len(geom)
    k = 111320.0
    kl = 111320.0 * math.cos(math.radians(lat0))
    pts = [(p['lon'] * kl, p['lat'] * k) for p in geom]
    s = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def main():
    s, w, n, e = [float(x) for x in sys.argv[1:5]]
    out = sys.argv[5] if len(sys.argv) > 5 else None
    src = sys.argv[6] if len(sys.argv) > 6 else 'buildings.json'
    with open(os.path.join(ROOT, 'data', 'raw', src), encoding='utf-8') as f:
        doc = json.load(f)
    els = doc['elements'] if isinstance(doc, dict) else doc
    seen, rows = set(), []
    for el in els:
        if el['id'] in seen:
            continue
        seen.add(el['id'])
        g = [p for p in (el.get('geometry') or []) if p]
        if len(g) < 3:
            continue
        la = sum(p['lat'] for p in g) / len(g)
        lo = sum(p['lon'] for p in g) / len(g)
        if not (s <= la <= n and w <= lo <= e):
            continue
        t = el.get('tags') or {}
        rows.append((t.get('name') or '(无名)', el['id'], t.get('building') or '',
                     t.get('building:levels') or '', round(poly_area(g)),
                     round(la, 6), round(lo, 6),
                     round(min(p['lon'] for p in g), 6), round(min(p['lat'] for p in g), 6),
                     round(max(p['lon'] for p in g), 6), round(max(p['lat'] for p in g), 6)))
    rows.sort(key=lambda r: -r[5])
    lines = ['%-24s %-12s %-12s %-5s %8s  %9s %9s   bbox' %
             ('name', 'way_id', 'building', 'lv', 'area_m2', 'lat', 'lon')]
    for r in rows:
        lines.append('%-24s %-12s %-12s %-5s %8d  %9.6f %9.6f   [%s, %s, %s, %s]' %
                     (r[0][:24], r[1], r[2][:12], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10]))
    txt = '\n'.join(lines)
    print(txt)
    if out:
        with open(os.path.join(ROOT, 'data', 'derived', out), 'w', encoding='utf-8') as f:
            f.write(txt + '\n')
        print('->', out)


if __name__ == '__main__':
    main()
