"""Add explicit service connection points (接入点) to the pipeline bundle.

For every building that receives water, compute:
  * snap point on the road network (where the service pipe leaves the road)
  * the lateral run from that point to the building footprint edge
  * the riser height and a per-floor outlet schedule

Then emit a bundle enriched with `service_connections` so the 2.5D view can
draw the lateral, the tee, and a callout per building instead of a single
line passing by.

usage: python scripts/add_service_points.py
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

BUNDLE = 'data/derived/pipeline_bundle.json'
OUT = 'data/derived/pipeline_bundle_conn.json'

FLOOR_H = 3.2


def dist_pt_seg(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    if L2 == 0.0:
        return math.hypot(px - ax, py - ay), ax, ay
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / L2))
    qx, qy = ax + t * vx, ay + t * vy
    return math.hypot(px - qx, py - qy), qx, qy


def poly_edges(fp):
    """Footprint [lon,lat] list -> list of (lon,lat) segments."""
    n = len(fp)
    return [(fp[i], fp[(i + 1) % n]) for i in range(n)]


def main():
    b = json.load(open(BUNDLE, encoding='utf-8'))
    meta = b['meta']
    lat0, lon0 = meta['origin']
    k_lat = meta['m_per_deg_lat']
    k_lon = meta['m_per_deg_lon']

    def xy(lon, lat):
        return (lon - lon0) * k_lon, (lat - lat0) * k_lat

    # index every road segment once
    segs = []
    for r in b['roads']:
        pts = r['pts']
        for i in range(len(pts) - 1):
            ax, ay = xy(*pts[i])
            bx, by = xy(*pts[i + 1])
            segs.append((ax, ay, bx, by, r.get('name') or '', r.get('hw') or ''))

    conns = []
    for bld in b['buildings']:
        fp = bld.get('footprint') or []
        if not fp:
            continue
        # building centre and the closest footprint edge point
        bx, by = xy(bld['lon'], bld['lat'])
        best_edge = None
        for (l1, l2) in poly_edges(fp):
            ax, ay = xy(*l1)
            cx, cy = xy(*l2)
            d, qx, qy = dist_pt_seg(bx, by, ax, ay, cx, cy)
            if best_edge is None or d < best_edge[0]:
                best_edge = (d, qx, qy)
        if best_edge is None:
            continue

        # nearest road to that edge point
        ex, ey = best_edge[1], best_edge[2]
        best_road = None
        for (ax, ay, cx, cy, nm, hw) in segs:
            d, qx, qy = dist_pt_seg(ex, ey, ax, ay, cx, cy)
            if best_road is None or d < best_road[0]:
                best_road = (d, qx, qy, nm, hw)
        if best_road is None:
            continue

        rl, rx, ry, rname, rhw = best_road
        lateral = math.hypot(ex - rx, ey - ry)
        levels = int(bld.get('levels') or 1)
        floors = []
        for f in range(1, levels + 1):
            floors.append({
                'floor': f,
                'elev_m': round(f * FLOOR_H, 2),
                # main outlet low on each floor, riser continues upward
                'fn': (f'DN{50 if f == 1 else 32}' if f == 1 else f'DN32'),
            })
        conns.append({
            'id': bld['id'],
            'name': bld['name'],
            'short': bld.get('short') or bld['name'],
            'cat': bld['cat'],
            'levels': levels,
            'road_tap': [round(rx, 1), round(ry, 1)],
            'road_name': rname,
            'road_hw': rhw,
            'lateral_m': round(lateral, 1),
            'edge_point': [round(ex, 1), round(ey, 1)],
            'riser_h_m': round(levels * FLOOR_H, 2),
            'floors': floors,
            'demand': bld.get('demand'),
            'approx': bool(bld.get('approx')),
        })

    loads = {}
    for c in conns:
        loads[c['name']] = c['levels']
    top = load_h = None

    b['service_connections'] = conns
    b['stats']['n_service_connections'] = len(conns)
    json.dump(b, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)

    print(f'connections written: {len(conns)}')
    lateral = [c['lateral_m'] for c in conns]
    lateral.sort()
    print(f'lateral  min {lateral[0]:.1f}  median {lateral[len(lateral)//2]:.1f}  '
          f'max {lateral[-1]:.1f} m')
    worst = sorted(conns, key=lambda c: -c['lateral_m'])[:8]
    print('longest laterals:')
    for c in worst:
        print(f"  {c['short']:<18} {c['lateral_m']:>6.1f} m  "
              f"road={c['road_name'] or c['road_hw']}")
    print('->', OUT)


if __name__ == '__main__':
    main()
