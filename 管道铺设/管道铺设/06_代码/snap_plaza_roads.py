"""Snap user-traced plaza road endpoints onto the existing OSM road network.

The traced polylines come from a screenshot, so their endpoints land tens of
metres off the real arterial roads they should join. This script extends each
dangling endpoint outward along its own final direction until it meets an OSM
highway segment (within a search limit), then inserts that junction point.

usage: python scripts/snap_plaza_roads.py
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

LAT0, LON0 = 39.9111, 119.5172
K_LAT = 111320.0
K_LON = 111320.0 * math.cos(math.radians(LAT0))


def meters(lat, lon):
    return (lon - LON0) * K_LON, (lat - LAT0) * K_LAT


def lonlat(x, y):
    return LAT0 + y / K_LAT, LON0 + x / K_LON


def seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    if L2 == 0:
        return math.hypot(px - ax, py - ay), ax, ay, 0.0
    t = ((px - ax) * vx + (py - ay) * vy) / L2
    t = max(0.0, min(1.0, t))
    qx, qy = ax + t * vx, ay + t * vy
    return math.hypot(px - qx, py - qy), qx, qy, t


def load_osm_roads():
    els = json.load(open('data/raw/roads_with_plaza.json', encoding='utf-8'))['elements']
    out = []
    for el in els:
        t = el.get('tags') or {}
        if t.get('source') == 'user_trace':
            continue
        hw = t.get('highway')
        if hw in ('steps', 'construction'):
            continue
        g = [p for p in (el.get('geometry') or []) if p]
        for i in range(len(g) - 1):
            ax, ay = meters(g[i]['lat'], g[i]['lon'])
            bx, by = meters(g[i + 1]['lat'], g[i + 1]['lon'])
            out.append((ax, ay, bx, by))
    return out


def extend_to_road(px, py, dx, dy, roads, limit=400.0, step=2.0):
    """March from (px,py) along (dx,dy) until we come within `tol` of a road."""
    n = math.hypot(dx, dy)
    if n == 0:
        return None
    dx, dy = dx / n, dy / n
    d = 0.0
    while d <= limit:
        qx, qy = px + dx * d, py + dy * d
        for ax, ay, bx, by in roads:
            dd, _, _, _ = seg_dist(qx, qy, ax, ay, bx, by)
            if dd < 6.0:
                return qx, qy, d
        d += step
    return None


def main():
    data = json.load(open('data/derived/plaza_roads_user.json', encoding='utf-8'))
    roads = load_osm_roads()
    print('osm segments', len(roads))

    segs = data['segments']
    fixed = {}
    for name, pts in segs.items():
        pp = list(pts)
        xy = [meters(lat, lon) for lon, lat in pp]

        # try to extend the FIRST point backward along the first direction
        dx, dy = xy[0][0] - xy[1][0], xy[0][1] - xy[1][1]
        r = extend_to_road(xy[0][0], xy[0][1], dx, dy, roads)
        if r:
            lat, lon = lonlat(r[0], r[1])
            pp.insert(0, [round(lon, 6), round(lat, 6)])
            print(f'{name}: extended head {r[2]:.1f} m -> {lat:.6f},{lon:.6f}')
        else:
            print(f'{name}: head NOT snapped')

        # then the LAST point forward
        xy = [meters(lat, lon) for lon, lat in pp]
        dx, dy = xy[-1][0] - xy[-2][0], xy[-1][1] - xy[-2][1]
        r = extend_to_road(xy[-1][0], xy[-1][1], dx, dy, roads)
        if r:
            lat, lon = lonlat(r[0], r[1])
            pp.append([round(lon, 6), round(lat, 6)])
            print(f'{name}: extended tail {r[2]:.1f} m -> {lat:.6f},{lon:.6f}')
        else:
            print(f'{name}: tail NOT snapped')

        fixed[name] = [list(p) for p in pp]

    data['segments'] = fixed
    data['note'] += '; endpoints extended to meet the OSM network by scripts/snap_plaza_roads.py'
    json.dump(data, open('data/derived/plaza_roads_user.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('-> updated data/derived/plaza_roads_user.json')


if __name__ == '__main__':
    main()
