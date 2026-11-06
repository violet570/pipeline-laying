"""Add explicit service connection points (接入点) to the pipeline bundle.

For every building that receives water, compute:
  * the closest pair (footprint edge point, road point) -> the real lateral
  * the lateral run from that point to the building footprint edge
  * the riser height and a per-floor outlet schedule

Then emit a bundle enriched with `service_connections` so the 2.5D view can
draw the lateral, the tee, and a callout per building instead of a single
line passing by.

v2 (2026-11-01):
  旧实现只取“离建筑中心最近的边”，再把这一个点吸到最近道路。对
  87x98 m 的人工智能 bbox，这条边背对环道，支管被算成 107~125 m；
  对贴着道路的 bbox 又会算出 0 m。现在改为在整条轮廓上搜索
  (边点, 道路点) 距离最小的一对，并要求：
    * 支管 >= 2 m（避免 0 m 假接户）；
    * 道路点不在楼体轮廓内（排除穿过 bbox 的道路）；
    * 支管不穿过楼体内部。

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
MIN_LATERAL = 2.0


def dist_pt_seg(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    if L2 == 0.0:
        return math.hypot(px - ax, py - ay), ax, ay
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / L2))
    qx, qy = ax + t * vx, ay + t * vy
    return math.hypot(px - qx, py - qy), qx, qy


def poly_edges(fp):
    n = len(fp)
    return [(fp[i], fp[(i + 1) % n]) for i in range(n)]


def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def crosses_footprint(p, q, poly_m, skip_eps=1.0):
    """p 在轮廓边上，q 在路面上；若连线穿过楼体内部则拒绝。"""
    L = math.hypot(q[0] - p[0], q[1] - p[1])
    n = max(2, int(L / 2.0))
    for i in range(1, n):
        t = i / n
        x = p[0] + (q[0] - p[0]) * t
        y = p[1] + (q[1] - p[1]) * t
        if math.hypot(x - p[0], y - p[1]) < skip_eps:
            continue
        if point_in_poly(x, y, poly_m):
            return True
    return False


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
        poly_m = [xy(p[0], p[1]) for p in fp]

        best = None
        for (l1, l2) in poly_edges(fp):
            ax, ay = xy(*l1)
            bx, by = xy(*l2)
            for k in range(11):
                t = k / 10.0
                px, py = ax + (bx - ax) * t, ay + (by - ay) * t
                for (rx1, ry1, rx2, ry2, nm, hw) in segs:
                    d, qx, qy = dist_pt_seg(px, py, rx1, ry1, rx2, ry2)
                    if d < MIN_LATERAL:
                        continue
                    if best is not None and d >= best[0]:
                        continue
                    if point_in_poly(qx, qy, poly_m):
                        continue
                    if crosses_footprint((px, py), (qx, qy), poly_m):
                        continue
                    best = (d, px, py, qx, qy, nm, hw)

        # 兜底：万一所有候选都被挡住，退回“最近边 + 最近路”
        if best is None:
            bx0, by0 = xy(bld['lon'], bld['lat'])
            cand = []
            for (l1, l2) in poly_edges(fp):
                ax, ay = xy(*l1)
                cx, cy = xy(*l2)
                dd, ex0, ey0 = dist_pt_seg(bx0, by0, ax, ay, cx, cy)
                cand.append((dd, ex0, ey0))
            dd, ex0, ey0 = min(cand)
            for (rx1, ry1, rx2, ry2, nm, hw) in segs:
                d, qx, qy = dist_pt_seg(ex0, ey0, rx1, ry1, rx2, ry2)
                if best is None or d < best[0]:
                    best = (d, ex0, ey0, qx, qy, nm, hw)
        if best is None:
            continue

        lateral, ex, ey, rx, ry, rname, rhw = best
        levels = int(bld.get('levels') or 1)
        floors = [{'floor': f, 'elev_m': round(f * FLOOR_H, 2),
                   'fn': ('DN50' if f == 1 else 'DN32')} for f in range(1, levels + 1)]
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

    b['service_connections'] = conns
    b['stats']['n_service_connections'] = len(conns)
    json.dump(b, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)

    print(f'connections written: {len(conns)}')
    lateral = sorted(c['lateral_m'] for c in conns)
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
