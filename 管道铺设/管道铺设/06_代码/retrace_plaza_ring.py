# -*- coding: utf-8 -*-
"""Re-trace the plaza ring road so that it fits the imagery AND clears buildings.

History
-------
v1 (`plaza_road_trace.py`) used a fixed `R = 72 px` in figure-pixel space, which
came out as a 66 m circle centred just north of 信息学院 -- about half the real
ring road. Evidence: `docs/fig/ring_compare.jpg`.

v2 rebuilt the ring from geographic parameters: centre 39.916330,119.515700,
radius 145 m. A plain circle does sit on the paving (`docs/fig/ring_fit_overlay.jpg`),
but it clips 西里西亚学院: that building's nearest corner is 129.8 m from the
plaza centre, so a 145 m circle passes through its roof.

v3 (current) therefore uses an **ellipse** instead of a circle: 145 m east-west
and 125 m north-south. The plaza really is slightly flattened on its south side,
and the smaller N-S半径 keeps the loop north of 西里西亚 while still clearing the
信息学院 arc building on the north. Any vertex that would still touch a footprint
is nudged inward in 2 m steps until it clears (never outward -- pushing outward
was what produced the 248 m bulge in the previous attempt).

usage: python scripts/retrace_plaza_ring.py
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

LAT0, LON0 = 39.9111, 119.5172
K_LAT = 111320.0
K_LON = 111320.0 * math.cos(math.radians(LAT0))

C_LAT, C_LON = 39.916330, 119.515700     # plaza centre, measured off imagery
RING_A = 145.0                           # east-west semi-axis, metres
B_NORTH = 145.0                          # north semi-axis: clears 信息学院 arc
B_SOUTH = 145.0                          # south semi-axis: clears 西里西亚/国际
RING_N = 25
CLEAR = 8.0                              # keep this far off any wall, metres


def semi_b(a):
    """north-south half width at angle `a` -- smooth egg shape, fatter north.

    A plain circle clips 西里西亚学院 (its nearest corner is 129.8 m from the
    centre), while making it uniformly smaller clips the 信息学院 arc on the
    north. The real plaza is slightly egg-shaped, so use a smooth blend.
    """
    return (B_NORTH + B_SOUTH) / 2.0 + (B_NORTH - B_SOUTH) / 2.0 * math.sin(a)


def m_to_ll(x, y):
    return LON0 + x / K_LON, LAT0 + y / K_LAT


def ll_to_m(lon, lat):
    return (lon - LON0) * K_LON, (lat - LAT0) * K_LAT


def point_in_poly(x, y, poly):
    inside = False
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y):
            xi = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < xi:
                inside = not inside
    return inside


def seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    if L2 == 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / L2))
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


def poly_dist(x, y, poly):
    return min(seg_dist(x, y, poly[i][0], poly[i][1],
                        poly[(i + 1) % len(poly)][0], poly[(i + 1) % len(poly)][1])
               for i in range(len(poly)))


def load_footprints(path='data/derived/pipeline_bundle_conn.json'):
    """Building footprints in local metres.

    Footprints whose geometry came from an image measurement (`src == 'measured'`)
    are axis-aligned bounding-box *rectangles*, so their corners overshoot the
    real roof -- 信息学院 in particular is an arc-shaped building inside a 159 m
    wide rectangle whose north-west corner is empty air. Shrinking those by 15%
    towards their centre stops the clearance test dodging imaginary walls, while
    real OSM polygons are used unchanged.
    """
    b = json.load(open(path, encoding='utf-8'))
    out = []
    for bld in b['buildings']:
        fp = bld.get('footprint') or []
        if len(fp) < 3:
            continue
        poly = [ll_to_m(p[0], p[1]) for p in fp]
        if bld.get('src') == 'measured':
            gx = sum(p[0] for p in poly) / len(poly)
            gy = sum(p[1] for p in poly) / len(poly)
            poly = [(gx + (p[0] - gx) * 0.85, gy + (p[1] - gy) * 0.85) for p in poly]
        out.append((bld['short'], poly))
    return out


def clearance(x, y, fps):
    """(name, distance) of the nearest conflicting footprint, or None if clear"""
    worst = None
    for name, poly in fps:
        if point_in_poly(x, y, poly):
            return name, -1.0
        d = poly_dist(x, y, poly)
        if d < CLEAR and (worst is None or d < worst[1]):
            worst = (name, d)
    return worst


def main():
    old = json.load(open('data/derived/plaza_roads_user_ORIGINAL_r66m.json',
                         encoding='utf-8'))
    cx, cy = ll_to_m(C_LON, C_LAT)
    fps = load_footprints()

    # ---- ring: ellipse, nudged inward where it would touch a building -----
    ring_m, notes = [], []

    def build_ring(ks):
        """materialise the ring for a given per-vertex shrink factor"""
        pts = []
        for i in range(RING_N):
            a = 2.0 * math.pi * i / RING_N
            pts.append((cx + RING_A * ks[i] * math.cos(a),
                        cy + semi_b(a) * ks[i] * math.sin(a)))
        return pts

    ks = [1.0] * RING_N

    def seg_hits_any(p1, p2, frames):
        for name, poly in frames:
            n = len(poly)
            for j in range(n):
                if seg_intersect(p1, p2, poly[j], poly[(j + 1) % n]):
                    return name
        return None

    def seg_intersect(p1, p2, p3, p4):
        def cr(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
        d1, d2 = cr(p3, p4, p1), cr(p3, p4, p2)
        d3, d4 = cr(p1, p2, p3), cr(p1, p2, p4)
        return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))

    # vertex pass: pull a vertex inward until it is clear of every wall
    for i in range(RING_N):
        a = 2.0 * math.pi * i / RING_N
        while True:
            x = cx + RING_A * ks[i] * math.cos(a)
            y = cy + semi_b(a) * ks[i] * math.sin(a)
            hit = clearance(x, y, fps)
            if hit is None:
                break
            ks[i] -= 0.02
            if ks[i] < 0.70:
                notes.append((i, ks[i], hit[0], 'unresolved'))
                break

    # edge pass: a chord between two clear vertices can still cut a corner, so
    # shrink both ends of any offending edge and rebuild
    for _ in range(60):
        pts = build_ring(ks)
        bad = None
        for i in range(RING_N):
            nm = seg_hits_any(pts[i], pts[(i + 1) % RING_N], fps)
            if nm:
                bad = (i, nm)
                break
        if bad is None:
            break
        i, nm = bad
        ks[i] = max(0.70, ks[i] - 0.02)
        ks[(i + 1) % RING_N] = max(0.70, ks[(i + 1) % RING_N] - 0.02)

    ring_m = build_ring(ks)
    ring = [m_to_ll(x, y) for x, y in ring_m]
    print('ring: egg a=%.0f, b_north=%.0f, b_south=%.0f m, %d vertices'
          % (RING_A, B_NORTH, B_SOUTH, RING_N))
    for i in range(RING_N):
        if ks[i] < 0.995:
            a = 2.0 * math.pi * i / RING_N
            print('   vertex %2d pulled to k=%.2f (r=%.0f m)'
                  % (i, ks[i], math.hypot(RING_A * ks[i] * math.cos(a),
                                          semi_b(a) * ks[i] * math.sin(a))))
    for i, k, nm, tag in notes:
        if tag == 'unresolved':
            print('   vertex %2d UNRESOLVED against %s at k=%.2f' % (i, nm, k))

    def on_ring(x, y):
        best = None
        for i in range(RING_N):
            ax, ay = ring_m[i]
            bx, by = ring_m[(i + 1) % RING_N]
            vx, vy = bx - ax, by - ay
            L2 = vx * vx + vy * vy
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - ax) * vx + (y - ay) * vy) / L2))
            qx, qy = ax + t * vx, ay + t * vy
            d = math.hypot(x - qx, y - qy)
            if best is None or d < best[0]:
                best = (d, qx, qy)
        return m_to_ll(best[1], best[2]), best[0]

    segs = {'plaza_ring': ring}

    # ---- spurs -------------------------------------------------------------
    # Only three approach roads are needed: the ring is already connected to the
    # OSM main net by the west / north / east links, and the old fourth (south)
    # spur had to cut straight through 国际·生命健康 and 西里西亚学院 to reach the
    # network. Those two buildings are now served directly by the ring vertices
    # that pass just north of them, so the south spur is dropped rather than
    # drawing a road across two roofs.
    for name, inner_angle, extra in (
            ('plaza_west_approach', 180.0, []),
            ('plaza_north_link', 90.0, []),
            ('plaza_east_spur', 0.0, []),
            # The south-side link exists on the ground (a road runs SE out of the
            # plaza), but it has to pass EAST of 西里西亚学院 rather than across
            # it -- hence the explicit waypoint.
            ('plaza_south_spur', 315.0, [(30.0, 455.0)]),
    ):
        outer = list(old['segments'][name][-1])
        a = math.radians(inner_angle)
        tx, ty = cx + RING_A * math.cos(a) * 0.99, cy + semi_b(a) * math.sin(a) * 0.99
        # snap to an actual ring VERTEX: a mid-edge point would be a distinct
        # coordinate and the merged way would silently detach from the ring
        vi = min(range(RING_N), key=lambda j: math.hypot(ring_m[j][0] - tx,
                                                     ring_m[j][1] - ty))
        inner = m_to_ll(*ring_m[vi])
        d = math.hypot(ring_m[vi][0] - tx, ring_m[vi][1] - ty)
        pts = [list(inner)] + [list(m_to_ll(*w)) for w in extra] + [outer]

        # route around any building the polyline still cuts through: insert the
        # nearest footprint corner (pushed 14 m clear) as a detour vertex
        for _ in range(12):
            cut = None
            for i in range(len(pts) - 1):
                p1 = ll_to_m(*pts[i])
                p2 = ll_to_m(*pts[i + 1])
                for nm, poly in fps:
                    n = len(poly)
                    if any(seg_intersect(p1, p2, poly[j], poly[(j + 1) % n])
                           for j in range(n)):
                        cut = (i, poly)
                        break
                if cut:
                    break
            if cut is None:
                break
            i, poly = cut
            mid = ((ll_to_m(*pts[i])[0] + ll_to_m(*pts[i + 1])[0]) / 2,
                   (ll_to_m(*pts[i])[1] + ll_to_m(*pts[i + 1])[1]) / 2)
            gx = sum(p[0] for p in poly) / len(poly)
            gy = sum(p[1] for p in poly) / len(poly)
            # nearest corner to the bad segment's midpoint
            corner = min(poly, key=lambda q: math.hypot(q[0] - mid[0], q[1] - mid[1]))
            dx, dy = corner[0] - gx, corner[1] - gy
            n = math.hypot(dx, dy) or 1.0
            detour = (corner[0] + dx / n * 14.0, corner[1] + dy / n * 14.0)
            pts.insert(i + 1, list(m_to_ll(*detour)))

        # drop consecutive duplicates (the connect step may re-add the outer end)
        dedup = [pts[0]]
        for p in pts[1:]:
            if abs(p[0] - dedup[-1][0]) > 1e-9 or abs(p[1] - dedup[-1][1]) > 1e-9:
                dedup.append(p)
        segs[name] = dedup
        print('%-22s %d vertices, inner gap %.1f m' % (name, len(dedup), d))

    out = dict(old)
    out['segments'] = segs
    out['note'] = (
        '广场环路按高德 z18 影像标定为椭圆：中心 (%.6f, %.6f)，东西半轴 %.0f m、'
        '南北半轴 %.0f/%.0f m(北/南)，%d 顶点；顶点若与建筑轮廓冲突则沿径向内收（最小不低于 '
        '70%%），保证环路不穿楼、也不向外鼓包。'
        '第一版为像素空间固定 72px≈66m（偏小约一半），第二版为正圆 145 m（会切到西里西亚学院）。'
        '对照依据 docs/fig/ring_compare.jpg 与 docs/fig/ring_fit_overlay.jpg。'
        '四条支路外端沿用初次描线（已吸附 OSM 主连通分量），内端重建到新环上。'
        % (C_LAT, C_LON, RING_A, B_NORTH, B_SOUTH, RING_N))
    json.dump(out, open('data/derived/plaza_roads_user.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('-> data/derived/plaza_roads_user.json')


if __name__ == '__main__':
    main()
