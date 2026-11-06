# -*- coding: utf-8 -*-
"""高德 × OSM 数据一致性核查脚本（只读，不修改 04_数据）。

运行：python 08_数据核查/核查脚本.py
输出：报告《数据一致性核查_高德vsOSM.md》中引用的全部数字。

依赖：Pillow、numpy（读取高德 z18 路网图做环路拟合）。
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "04_数据")
DERIVED = os.path.join(DATA, "derived")
AMAP_ROAD = os.path.join(ROOT, "05_图件", "卫星与底图", "amap_west.png")

# ---------------------------------------------------------------- 基础参数
BUNDLE = json.load(open(os.path.join(DERIVED, "pipeline_bundle_conn.json"), encoding="utf-8"))
META = BUNDLE["meta"]
STATS = BUNDLE["stats"]
BLD = BUNDLE["buildings"]
K_LAT = META["m_per_deg_lat"]
K_LON = META["m_per_deg_lon"]
PLAZA = json.load(open(os.path.join(DERIVED, "plaza_roads_user.json"), encoding="utf-8"))

# 高德 z18 路网图（style=8）的拼接参数，见 06_代码/crop_amap.py
Z, TILE = 18, 256
X0, Y0 = 218097, 99317
NPIX = 2.0 ** Z * TILE
RING_C = (119.515700, 39.916330)          # 文档声明的环道圆心 (lon, lat)


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


def gcj2wgs(glon, glat, n=20):
    lon, lat = glon, glat
    for _ in range(n):
        tlon, tlat = wgs2gcj(lon, lat)
        dlon, dlat = glon - tlon, glat - tlat
        lon, lat = lon + dlon, lat + dlat
        if abs(dlon) < 1e-12 and abs(dlat) < 1e-12:
            break
    return lon, lat


def to_px(lon, lat):
    """WGS-84 -> amap_west.png 像素（先转 GCJ-02）。"""
    glon, glat = wgs2gcj(lon, lat)
    mx = (glon + 180.0) / 360.0 * NPIX
    s = math.sin(math.radians(glat))
    my = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * NPIX
    return mx - X0 * TILE, my - Y0 * TILE


def hdist(lon1, lat1, lon2, lat2):
    return math.hypot((lon1 - lon2) * K_LON, (lat1 - lat2) * K_LAT)


# ================================================================ 1. 坐标系
def check_crs():
    print("=" * 64)
    print("1. 坐标系：GCJ-02 偏移与往返")
    lon, lat = 119.5172, 39.9111
    glon, glat = wgs2gcj(lon, lat)
    print("   WGS(%.4f,%.4f) -> GCJ  ΔE=%+.1f m  ΔN=%+.1f m  合成 %.1f m"
          % (lat, lon, (glon - lon) * K_LON, (glat - lat) * K_LAT,
             math.hypot((glon - lon) * K_LON, (glat - lat) * K_LAT)))
    wl, wa = gcj2wgs(glon, glat)
    print("   GCJ -> WGS 往返残差 %.4f m" % hdist(wl, wa, lon, lat))


# ================================================================ 2. 环道
def check_ring():
    print("=" * 64)
    print("2. 广场环道 vs 高德 z18 路网图")
    ring = PLAZA["segments"]["plaza_ring"]
    cx, cy = RING_C
    x0, y0 = to_px(cx, cy)
    mpp = 156543.03392 * math.cos(math.radians(cy)) / (2.0 ** Z)

    # 顶点半径
    radii = [hdist(p[0], p[1], cx, cy) for p in ring]
    print("   现行 v4：圆心 (%.6f,%.6f) 半径约 120.3 m（v3 旧值 145 m 已废弃），%d 顶点"
          % (cy, cx, len(ring)))
    print("   数据顶点半径 min/mean/max = %.1f / %.1f / %.1f m"
          % (min(radii), sum(radii) / len(radii), max(radii)))
    gap = hdist(ring[-1][0], ring[-1][1], ring[0][0], ring[0][1])
    print("   首尾间距 %.2f m（%s）" % (gap, "已闭合" if gap < 0.05 else "未闭合"))

    # 从高德路网图拟合真实环
    if not os.path.exists(AMAP_ROAD):
        print("   [跳过] 找不到 %s" % AMAP_ROAD)
        return
    img = np.asarray(Image.open(AMAP_ROAD).convert("RGB")).astype(int)
    white = (img[:, :, 0] > 248) & (img[:, :, 1] > 248) & (img[:, :, 2] > 248)
    pts = []
    for adeg in range(0, 360, 2):
        a = math.radians(adeg)
        for r in range(100, 140):
            x = int(round(x0 + r * math.cos(a) / mpp))
            y = int(round(y0 - r * math.sin(a) / mpp))
            if white[y, x]:
                pts.append((x, y))
                break
    P = np.array(pts, float)
    Ax = np.c_[2 * P[:, 0], 2 * P[:, 1], np.ones(len(P))]
    b = (P ** 2).sum(1)
    (a0, b0, c0), *_ = np.linalg.lstsq(Ax, b, rcond=None)
    rpx = math.sqrt(c0 + a0 * a0 + b0 * b0)
    # 用反算 mercator 求经纬度
    def px2ll(mx, my):
        lon = mx / NPIX * 360.0 - 180.0
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * my / NPIX))))
        return lon, lat
    glon, glat = px2ll(a0 + X0 * TILE, b0 + Y0 * TILE)
    lon_c, lat_c = gcj2wgs(glon, glat)
    print("   高德路网拟合：圆心 (%.6f,%.6f) 半径 %.1f m（%d 个采样点）"
          % (lat_c, lon_c, rpx * mpp, len(pts)))
    print("   圆心偏差 %.1f m；半径差 %.1f m（数据 / 实际 = %.2f，目标 1.00~1.05）"
          % (hdist(lon_c, lat_c, cx, cy), abs(sum(radii) / len(radii) - rpx * mpp),
             (sum(radii) / len(radii)) / (rpx * mpp)))

    # 顶点到最近道路像素的距离
    offs = []
    for lon, lat in ring:
        px0, py0 = to_px(lon, lat)
        best = 1e9
        for dx in range(-45, 46, 2):
            for dy in range(-45, 46, 2):
                xi = int(round(px0 + dx / mpp))
                yi = int(round(py0 + dy / mpp))
                if white[yi, xi]:
                    best = min(best, math.hypot(dx, dy))
        if best < 1e8:
            offs.append(best)
    offs.sort()
    print("   环道顶点 -> 最近高德道路像素：min %.1f / 中位 %.1f / max %.1f m"
          % (offs[0], offs[len(offs) // 2], offs[-1]))

    # 长度对比
    seg = sum(hdist(ring[i][0], ring[i][1], ring[i + 1][0], ring[i + 1][1])
              for i in range(len(ring) - 1))
    print("   数据环长（含缺口）%.1f m；闭合后 %.1f m；r=%.1f 圆周长 %.1f m（+%.1f%%）"
          % (seg, seg + gap, rpx * mpp, 2 * math.pi * rpx * mpp,
             ((seg + gap) / (2 * math.pi * rpx * mpp) - 1) * 100))


# ================================================================ 3. 多栋组团
def check_multiblock():
    print("=" * 64)
    print("3. 多栋组团：轮廓只保留最大一栋")
    sys.path.insert(0, os.path.join(ROOT, "06_代码"))
    import groups as G
    raw = json.load(open(os.path.join(DATA, "raw", "buildings.json"), encoding="utf-8"))["elements"]
    ways = {e["id"]: e for e in raw}
    by_id = {b["id"]: b for b in BLD}

    def proj_area(pts):
        a = 0.0
        n = len(pts)
        for i in range(n):
            x1, y1 = pts[i][0] * K_LON, pts[i][1] * K_LAT
            x2, y2 = pts[(i + 1) % n][0] * K_LON, pts[(i + 1) % n][1] * K_LAT
            a += x1 * y2 - x2 * y1
        return abs(a) / 2.0

    total_missing = 0.0
    n_missing = 0
    for g in G.GROUPS:
        if g.get("measured") or len(g.get("ways", [])) < 2:
            continue
        b = by_id.get(g["key"])
        if not b:
            continue
        xs = [p[0] for p in b["footprint"]]
        ys = [p[1] for p in b["footprint"]]
        fb = (min(xs), min(ys), max(xs), max(ys))
        for w in g["ways"]:
            el = ways.get(w)
            if not el:
                continue
            pts = [(p["lon"], p["lat"]) for p in el["geometry"] if p]
            x0, y0 = min(p[0] for p in pts), min(p[1] for p in pts)
            x1, y1 = max(p[0] for p in pts), max(p[1] for p in pts)
            inside = (x0 >= fb[0] - 1e-6 and y0 >= fb[1] - 1e-6
                      and x1 <= fb[2] + 1e-6 and y1 <= fb[3] + 1e-6)
            if not inside:
                total_missing += proj_area(pts)
                n_missing += 1
    n_parts = sum(len(b.get("parts") or [b["footprint"]]) for b in BLD)
    print("   多栋组团 13 个；只进 footprint（主楼）之外的栋数 %d，面积 %.0f m²（占全校 %.1f%%）"
          % (n_missing, total_missing, total_missing / STATS["total_area_m2"] * 100))
    print("   parts 覆盖 %d 栋（应 = 67 OSM + 11 量测 = 78）；viz 已按 parts 绘制全部栋"
          % n_parts)


# ================================================================ 4. 统计勾稽
def check_stats():
    print("=" * 64)
    print("4. 统计字段勾稽")
    plen = sum(p["length"] for p in BUNDLE["pipes"])
    mst = sum(e["w"] for e in BUNDLE["tree_edges"])
    cost = sum(p["length"] * {32: 140, 40: 160, 50: 185, 65: 225, 80: 270, 100: 330,
                              125: 400, 150: 480, 200: 620, 250: 800, 300: 1000,
                              350: 1200, 400: 1450, 500: 1900}[p["dn"]]
               for p in BUNDLE["pipes"])
    print("   Σ管道 %.1f = stats %.1f | Σ树边 %.1f = stats %.1f | 造价 %.0f = stats %.0f"
          % (plen, STATS["pipe_length_m"], mst, STATS["mst_length_m"],
             cost, STATS["cost_est_yuan"]))
    all_dem = sum(b["demand"] for b in BLD)
    tgt_dem = sum(b["demand"] for b in BLD if b["cat"] not in ("utility", "other"))
    print("   逐栋 demand 合计 %.1f L/d；45 目标 %.1f；stats %.1f"
          % (all_dem, tgt_dem, STATS["total_demand_lpd"]))
    max_lat = max(c["lateral_m"] for c in BUNDLE["service_connections"])
    print("   最长接户支管 %.1f m；stats.snap_dist_max %.1f m（中心到路，不是支管）"
          % (max_lat, STATS["snap_dist_max"]))
    over = [p for p in BUNDLE["pipes"] if p["flow"] > STATS["total_demand_lpd"]]
    print("   流量超过总需水量的管段：%d 段；最大 %.1f L/d（%.2f L/s，%.1f%%）"
          % (len(over), max(p["flow"] for p in BUNDLE["pipes"]),
             max(p["q_ls"] for p in BUNDLE["pipes"]),
             max(p["flow"] for p in BUNDLE["pipes"]) / STATS["total_demand_lpd"] * 100))


# ================================================================ 5. 衍生文件
def check_derived():
    print("=" * 64)
    print("5. 衍生文件与文档口径")
    import csv
    lines = open(os.path.join(DERIVED, "distances.csv"), encoding="utf-8-sig").read().splitlines()[1:]
    keys = set()
    for ln in lines:
        parts = ln.split(",")
        keys.update([parts[0], parts[2]])
    ids = {b["id"] for b in BLD}
    print("   distances.csv：%d 对 / %d 个键；不在 bundle 的键 %s"
          % (len(lines), len(keys), sorted(keys - ids)))
    print("   61 栋应为 C(61,2)=%d 对" % (61 * 60 // 2))

    # 量测 bbox vs area
    print("   量测条目 bbox 面积 / area 字段：")
    for b in BLD:
        if b["src"] != "measured":
            continue
        xs = [p[0] for p in b["footprint"]]
        ys = [p[1] for p in b["footprint"]]
        bb = (max(xs) - min(xs)) * K_LON * (max(ys) - min(ys)) * K_LAT
        print("     %-4s %-10s bbox %7.0f  area %7.0f  ratio %.2f"
              % (b["id"], b["short"], bb, b["area"], b["area"] / bb))


if __name__ == "__main__":
    check_crs()
    check_ring()
    check_multiblock()
    check_stats()
    check_derived()
    print("=" * 64)
    print("完成（未修改任何数据文件）")
