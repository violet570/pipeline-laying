# -*- coding: utf-8 -*-
"""v4：按高德 z18 路网图重描广场环道（替换 145 m 正圆）。

v1 用旧圆心 + 66 m（偏小一半）；v2 用新圆心 + 145 m 正圆（偏大约 20%）；
本版直接从高德路网图（data/tiles/amap_west.png，z18，GCJ-02）的白色道路像素
提取环道中心线，平滑后转回 WGS-84，并强制首尾闭合。

同时把四条支路的内端重新挂到新环的最近顶点上，外端沿用原描线（已吸附 OSM 主网）。

usage: python scripts/retrace_plaza_ring_v4.py
"""
import json
import math
import os

import numpy as np
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)

# 高德 z18 路网图（style=8）拼接参数，与 06_代码/crop_amap.py 一致
Z, TILE = 18, 256
X0, Y0 = 218097, 99317
NPIX = 2.0 ** Z * TILE
ROAD_IMG = 'data/tiles/amap_west.png'
BUNDLE = 'data/derived/pipeline_bundle_conn.json'
OUT = 'data/derived/plaza_roads_user.json'

LAT0, LON0 = 39.9111, 119.5172
K_LAT = 111320.0
K_LON = 111320.0 * math.cos(math.radians(LAT0))

DECLARED_C = (119.515700, 39.916330)   # 文档原声明的圆心，用于比对
N_VERT = 72                            # 最终环道顶点数（5° 一个）
CLEAR = 6.0                            # 离建筑轮廓的最小净距 m


# ---------------------------------------------------------------- 坐标转换
def wgs2gcj(lon, lat):
    a, ee = 6378245.0, 0.00669342162296594323

    def tlat(x, y):
        r = (-100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y
             + 0.2 * math.sqrt(abs(x)))
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

    dlat, dlon = tlat(lon - 105.0, lat - 35.0), tlon(lon - 105.0, lat - 35.0)
    rad = math.radians(lat)
    m = 1 - ee * math.sin(rad) ** 2
    sq = math.sqrt(m)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (m * sq) * math.pi)
    dlon = (dlon * 180.0) / (a / sq * math.cos(rad) * math.pi)
    return lon + dlon, lat + dlat


def gcj2wgs(glon, glat, n=25):
    lon, lat = glon, glat
    for _ in range(n):
        tlon, tlat = wgs2gcj(lon, lat)
        dlon, dlat = glon - tlon, glat - tlat
        lon, lat = lon + dlon, lat + dlat
        if abs(dlon) < 1e-12 and abs(dlat) < 1e-12:
            break
    return lon, lat


def gcj_to_px(lon, lat):
    mx = (lon + 180.0) / 360.0 * NPIX
    s = math.sin(math.radians(lat))
    my = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * NPIX
    return mx - X0 * TILE, my - Y0 * TILE


def px_to_gcj(mx, my):
    lon = mx / NPIX * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * my / NPIX))))
    return lon, lat


def to_px(lon, lat):
    g = wgs2gcj(lon, lat)
    return gcj_to_px(*g)


def mdist(lon1, lat1, lon2, lat2):
    return math.hypot((lon1 - lon2) * K_LON, (lat1 - lat2) * K_LAT)


def ll2m(lon, lat):
    return (lon - LON0) * K_LON, (lat - LAT0) * K_LAT


def m2ll(x, y):
    return LON0 + x / K_LON, LAT0 + y / K_LAT


# ---------------------------------------------------------------- 几何
def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
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


def seg_intersect(p1, p2, p3, p4):
    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    d1, d2 = cr(p3, p4, p1), cr(p3, p4, p2)
    d3, d4 = cr(p1, p2, p3), cr(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def load_footprints():
    b = json.load(open(BUNDLE, encoding='utf-8'))
    out = []
    for bld in b['buildings']:
        fp = bld.get('footprint') or []
        if len(fp) < 3:
            continue
        poly = [ll2m(p[0], p[1]) for p in fp]
        # 影像量测条目是 bbox 矩形代理（弧形楼四角是空气），不参与避让；
        # 环道本身来自高德道路像素，不会压到真实楼体。
        if bld.get('src') == 'measured':
            continue
        out.append((bld['short'], poly))
    return out


def clearance(x, y, fps):
    for nm, poly in fps:
        if point_in_poly(x, y, poly):
            return nm
        if poly_dist(x, y, poly) < CLEAR:
            return nm
    return None


# ---------------------------------------------------------------- 提取环道
def white_mask():
    img = np.asarray(Image.open(ROAD_IMG).convert('RGB')).astype(int)
    return (img[:, :, 0] > 248) & (img[:, :, 1] > 248) & (img[:, :, 2] > 248)


def fit_centre(white):
    """用 100~140 m 的白像素做代数圆拟合，得到真实环心。"""
    cx, cy = to_px(*DECLARED_C)
    mpp = 156543.03392 * math.cos(math.radians(DECLARED_C[1])) / (2.0 ** Z)
    pts = []
    for adeg in range(0, 360, 2):
        a = math.radians(adeg)
        for r in range(100, 140):
            x = int(round(cx + r * math.cos(a) / mpp))
            y = int(round(cy - r * math.sin(a) / mpp))
            if white[y, x]:
                pts.append((x, y))
                break
    P = np.array(pts, float)
    A = np.c_[2 * P[:, 0], 2 * P[:, 1], np.ones(len(P))]
    b = (P ** 2).sum(1)
    (a0, b0, c0), *_ = np.linalg.lstsq(A, b, rcond=None)
    rpx = math.sqrt(c0 + a0 * a0 + b0 * b0)
    glon, glat = px_to_gcj(a0 + X0 * TILE, b0 + Y0 * TILE)
    lon, lat = gcj2wgs(glon, glat)
    return lon, lat, rpx * mpp


def radial_profile(white, cx, cy, mpp):
    """每个角度找环道中心线半径：取 95~145 m 内第一段白色像素的中点。"""
    rs = [float('nan')] * 360
    for adeg in range(360):
        a = math.radians(adeg)
        hits = []
        r = 95
        while r <= 145:
            x = int(round(cx + r * math.cos(a) / mpp))
            y = int(round(cy - r * math.sin(a) / mpp))
            if white[y, x]:
                hits.append(r)
            r += 1
        # 取第一段足够长（>=3 m，排除建筑细轮廓）的白色像元中点
        if not hits:
            continue
        runs, run = [], [hits[0]]
        for r in hits[1:]:
            if r - run[-1] <= 2:
                run.append(r)
            else:
                runs.append(run)
                run = [r]
        runs.append(run)
        pick = next((q for q in runs if q[-1] - q[0] + 1 >= 3), runs[0])
        rs[adeg] = (pick[0] + pick[-1]) / 2.0 + 0.6
    return rs


def smooth_profile(rs, median_win=9, mean_win=7):
    a = np.array(rs, dtype=float)
    med = np.nanmedian(a)
    a[np.abs(a - med) > 9.0] = np.nan
    idx = np.arange(360)
    good = ~np.isnan(a)
    a = np.interp(idx, idx[good], a[good], period=360)
    # circular median filter
    out = a.copy()
    half = median_win // 2
    for i in range(360):
        out[i] = np.median([a[(i + k) % 360] for k in range(-half, half + 1)])
    a = out
    # circular moving average
    out = a.copy()
    half = mean_win // 2
    for i in range(360):
        out[i] = np.mean([a[(i + k) % 360] for k in range(-half, half + 1)])
    return out


def build_ring(profile, cx, cy):
    """按 5° 重采样，并确保不压楼。"""
    fps = load_footprints()
    ring = []
    for adeg in range(0, 360, 360 // N_VERT):
        a = math.radians(adeg)
        r = float(profile[adeg])
        # 若压到建筑，沿径向内收 1 m 步进
        for _ in range(40):
            x = cx + r * math.cos(a)
            y = cy + r * math.sin(a)
            if clearance(x, y, fps) is None:
                break
            r -= 1.0
        ring.append((cx + r * math.cos(a), cy + r * math.sin(a)))

    # 边也不能切楼：顶点级内收
    for _ in range(60):
        bad = None
        for i in range(len(ring)):
            p1 = ring[i]
            p2 = ring[(i + 1) % len(ring)]
            for nm, poly in fps:
                n = len(poly)
                if any(seg_intersect(p1, p2, poly[j], poly[(j + 1) % n]) for j in range(n)):
                    bad = (i, nm)
                    break
            if bad:
                break
        if not bad:
            break
        i, _ = bad
        for j in (i, (i + 1) % len(ring)):
            x, y = ring[j]
            dx, dy = x - cx, y - cy
            d = math.hypot(dx, dy) or 1.0
            ring[j] = (x - dx / d * 2.0, y - dy / d * 2.0)
    return ring


def build_spurs(old, ring_m):
    """内端挂到新环最近顶点，外端和中途点沿用旧描线。"""
    fps = load_footprints()

    def on_ring_vertex(x, y):
        return min(range(len(ring_m)),
                   key=lambda j: math.hypot(ring_m[j][0] - x, ring_m[j][1] - y))

    segs = {}
    for name, pts in old['segments'].items():
        if name == 'plaza_ring':
            continue
        inner_old = ll2m(*pts[0])
        vi = on_ring_vertex(*inner_old)
        new = [list(m2ll(*ring_m[vi]))] + [list(p) for p in pts[1:]]
        # 若第一段穿楼，插一个绕过最近角点的点
        for _ in range(10):
            cut = None
            for i in range(len(new) - 1):
                p1 = ll2m(*new[i])
                p2 = ll2m(*new[i + 1])
                for nm, poly in fps:
                    n = len(poly)
                    if any(seg_intersect(p1, p2, poly[j], poly[(j + 1) % n]) for j in range(n)):
                        cut = (i, poly)
                        break
                if cut:
                    break
            if cut is None:
                break
            i, poly = cut
            mid = ((ll2m(*new[i])[0] + ll2m(*new[i + 1])[0]) / 2,
                   (ll2m(*new[i])[1] + ll2m(*new[i + 1])[1]) / 2)
            gx = sum(p[0] for p in poly) / len(poly)
            gy = sum(p[1] for p in poly) / len(poly)
            corner = min(poly, key=lambda q: math.hypot(q[0] - mid[0], q[1] - mid[1]))
            dx, dy = corner[0] - gx, corner[1] - gy
            n = math.hypot(dx, dy) or 1.0
            detour = (corner[0] + dx / n * 12.0, corner[1] + dy / n * 12.0)
            new.insert(i + 1, list(m2ll(*detour)))
        segs[name] = new
        print('  %-20s inner vertex %2d, %d pts' % (name, vi, len(new)))
    return segs


def main():
    white = white_mask()
    mpp = 156543.03392 * math.cos(math.radians(DECLARED_C[1])) / (2.0 ** Z)
    clon, clat, r0 = fit_centre(white)
    print('fitted centre %.6f,%.6f  r=%.1f m' % (clat, clon, r0))
    cx, cy = to_px(clon, clat)
    profile = smooth_profile(radial_profile(white, cx, cy, mpp))
    print('profile r: min %.1f  median %.1f  max %.1f m'
          % (profile.min(), np.median(profile), profile.max()))

    cx_m, cy_m = ll2m(clon, clat)
    ring_m = build_ring(profile, cx_m, cy_m)
    ring = [list(m2ll(x, y)) for x, y in ring_m]
    ring.append(ring[0])  # 闭合

    # 校验：环长、闭合、到白色道路的距离
    length = sum(mdist(ring[i][0], ring[i][1], ring[i + 1][0], ring[i + 1][1])
                 for i in range(len(ring) - 1))
    gaps = []
    for lon, lat in ring[:-1]:
        px0, py0 = to_px(lon, lat)
        best = 1e9
        for dx in range(-30, 31, 1):
            for dy in range(-30, 31, 1):
                xi = int(round(px0 + dx / mpp))
                yi = int(round(py0 + dy / mpp))
                if white[yi, xi]:
                    best = min(best, math.hypot(dx, dy))
        gaps.append(best)
    print('ring: %d vertices, length %.1f m, closed gap %.2f m'
          % (len(ring), length, mdist(ring[-1][0], ring[-1][1], ring[0][0], ring[0][1])))
    print('vertex -> white-road: median %.1f m, max %.1f m' % (np.median(gaps), max(gaps)))
    print('circle-equiv radius: %.1f m (declared 145, actual ~120)' % (length / (2 * math.pi)))

    old = json.load(open(OUT, encoding='utf-8'))
    segs = {'plaza_ring': ring}
    segs.update(build_spurs(old, ring_m))

    out = {
        'note': (
            'v4（2026-11-01）：环道不再用圆心+半径，而是从高德 z18 路网图 '
            '(data/tiles/amap_west.png) 的白色道路像素逐 1° 提取中心线，平滑后 72 顶点、'
            '首尾闭合；拟合圆心 (%.6f, %.6f)，等效半径约 %.1f m。'
            'v3 的 145 m 正圆比真实环道大约 20%%（环道顶点中位偏离 19 m），已废弃。'
            '四条支路外端沿用原描线（已吸附 OSM 主网），内端重挂到新环最近顶点。'
            % (clat, clon, length / (2 * math.pi))
        ),
        'frame': 'WGS84; ring sampled from AMap z18 road layer',
        'segments': segs,
    }
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('->', OUT)


if __name__ == '__main__':
    main()
