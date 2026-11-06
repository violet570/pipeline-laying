# -*- coding: utf-8 -*-
"""Print summary statistics of the building registry, so the report's headline numbers can
be generated rather than hand-counted.

Run: python scripts/registry_stats.py
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import groups as G  # noqa: E402

CAT_CN = {
    'dorm': '学生公寓', 'canteen': '食堂', 'teaching': '教学/实验楼', 'college': '学院楼',
    'library': '图书馆/信息楼', 'lab': '实验楼', 'office': '办公', 'art': '艺术',
    'activity': '活动中心', 'service': '服务设施', 'utility': '市政/能源设施',
    'workshop': '厂房/车间', 'other': '其他/待核实',
}


def poly_area(geom):
    """Shoelace area in m² on a local tangent plane around the campus."""
    if not geom or len(geom) < 3:
        return 0.0
    k_lat = 111320.0
    k_lon = 111320.0 * 0.7675
    pts = [((p['lon'] - 119.5172) * k_lon, (p['lat'] - 39.9111) * k_lat) for p in geom if p]
    s = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        s += x0 * y1 - x1 * y0
    return abs(s) / 2.0


def main():
    ways = G.load_ways()
    n_group = len(G.GROUPS)
    n_way = sum(len(g['ways']) for g in G.GROUPS)
    measured = [g for g in G.GROUPS if g.get('measured')]
    verified = [g for g in G.GROUPS if g.get('verified')]
    cats = Counter(g['cat'] for g in G.GROUPS)
    area_way = 0.0
    for g in G.GROUPS:
        for wid in g['ways']:
            el = ways.get(wid)
            if el:
                area_way += poly_area(el.get('geometry') or [])
    area_meas = sum(g['measured']['area_m2'] for g in measured)

    print('groups        =', n_group)
    print('OSM ways      =', n_way)
    print('measured      =', len(measured), '(verified=False)')
    print('verified(OSM) =', len(verified))
    print('total items   =', n_way + len(measured))
    print('area OSM  m2  =', round(area_way))
    print('area meas m2  =', area_meas)
    print('area total m2 =', round(area_way + area_meas))
    print()
    for k, v in cats.most_common():
        print('  %-10s %-14s %d' % (k, CAT_CN.get(k, k), v))
    print()
    print('measured list:')
    for g in measured:
        m = g['measured']
        print('  %-4s %-22s lat=%.6f lon=%.6f  %5d m2  %s'
              % (g['key'], g['name'][:22], m['lat'], m['lon'], m['area_m2'],
                 'OK' if g.get('verified') else '待核实'))


if __name__ == '__main__':
    main()
