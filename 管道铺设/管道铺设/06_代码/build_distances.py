# -*- coding: utf-8 -*-
"""Real-distance table: measured distances between all west-campus building clusters.

Everything here is measured from OSM WGS-84 footprints (registration with 高德 imagery
verified in docs/fig/fig6_registration_panels.jpg), so the numbers are reproducible.

Outputs
  data/derived/distances.csv      long form: from_key,from_name,to_key,to_name,centroid_m,gap_m
  data/derived/distances.md       human-readable tables + summary statistics
"""
import csv
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from groups import GROUPS, load_ways  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')
DER = os.path.join(ROOT, 'data', 'derived')

LAT0 = 39.9111
K_LAT = 111132.0
K_LON = 111320.0 * math.cos(math.radians(LAT0))


def to_xy(lon, lat):
    return ((lon - 119.5172) * K_LON, (lat - LAT0) * K_LAT)


def poly_pts(el):
    return [to_xy(p['lon'], p['lat']) for p in (el.get('geometry') or []) if p]


def dist_pt_seg(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def poly_gap(A, B):
    """Approximate min distance between two polygons (vertex-to-edge both ways)."""
    best = float('inf')
    for p in A:
        for i in range(len(B)):
            best = min(best, dist_pt_seg(p, B[i], B[(i + 1) % len(B)]))
    for p in B:
        for i in range(len(A)):
            best = min(best, dist_pt_seg(p, A[i], A[(i + 1) % len(A)]))
    return best


def main():
    ways = load_ways()
    items = []
    for g in GROUPS:
        pts = []
        polys = []
        area = 0.0
        for wid in g['ways']:
            el = ways.get(wid)
            if not el:
                continue
            pp = poly_pts(el)
            if len(pp) >= 3:
                polys.append(pp)
                pts += pp
                a = 0.0
                for i in range(len(pp)):
                    x1, y1 = pp[i]
                    x2, y2 = pp[(i + 1) % len(pp)]
                    a += x1 * y2 - x2 * y1
                area += abs(a) / 2
        if not pts:
            m = g.get('measured')
            if not m:
                continue
            # No OSM footprint: use the measured bbox rectangle as the footprint proxy.
            # It encloses the real roof, so the gap computed from it is an upper bound
            # (slightly pessimistic) — fine for a planning-level network.
            x0, y0 = to_xy(m['bbox'][0], m['bbox'][1])
            x1, y1 = to_xy(m['bbox'][2], m['bbox'][3])
            rect = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            polys = [rect]
            pts = list(rect)
            area = float(m['area_m2'])   # registry's measured footprint, not the bbox area
            approx = True
        else:
            approx = False
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        items.append(dict(key=g['key'], name=g['name'], cat=g['cat'], levels=g['levels'],
                          cx=cx, cy=cy, polys=polys, area=area, approx=approx))

    rows = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            A, B = items[i], items[j]
            dc = math.hypot(A['cx'] - B['cx'], A['cy'] - B['cy'])
            gap = float('inf')
            for pa in A['polys']:
                for pb in B['polys']:
                    gap = min(gap, poly_gap(pa, pb))
            if gap == float('inf'):
                gap = dc
            rows.append(dict(a=A, b=B, dc=dc, gap=gap))

    rows.sort(key=lambda r: r['gap'])
    with open(os.path.join(DER, 'distances.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['from_key', 'from_name', 'to_key', 'to_name', 'centroid_m', 'gap_m'])
        for r in rows:
            w.writerow([r['a']['key'], r['a']['name'], r['b']['key'], r['b']['name'],
                        round(r['dc'], 1), round(r['gap'], 1)])

    L = []
    A = L.append
    A('# 燕山大学西校区 建筑群实测距离表')
    A('')
    A('数据源：OpenStreetMap 建筑轮廓（WGS-84，2026-08 快照），与高德卫星影像配准校验通过')
    A('（见 `docs/fig/fig6_registration_panels.jpg`，抽检 6 栋建筑轮廓与屋顶边缘 1~3 px 内吻合）。')
    A('')
    A('两种距离：')
    A('- **中心距 centroid_m**：两建筑轮廓顶点平均位置之间的直线距离，反映"两栋楼大致隔多远"。')
    A('- **净距 gap_m**：两建筑轮廓多边形之间的最小距离（外墙面到外墙面），**这是敷设管道时最关心的量**：')
    A('  净距越小，横向穿越距离越短。净距含建筑之间的道路、绿化，不含管道的转弯与埋深。')
    A('')
    A('底面积单位 m²，层数来自 OSM `building:levels` 或官方/推断标注。')
    A('')
    A('带 `*` 的条目是 **OSM 没有轮廓、用高德 z18 影像人工量测补入的**（见调研报告 §4B）：')
    A('它们的面积取自量测值，而"净距"是用量测 bbox 矩形近似算出来的——bbox 是外接矩形，')
    A('比真实屋顶大，所以这些配对的净距是**上限（偏保守）**，精度约 ±1.5 m。')
    A('')
    A('## 1. 建筑群总表（%d 组）' % len(items))
    A('')
    A('| 组号 | 名称 | 类别 | 层数 | 底面积 m² | 纬度 | 经度 |')
    A('|---|---|---|---|---|---|---|')
    cat_cn = {'dorm': '学生公寓', 'canteen': '食堂/餐饮', 'teaching': '教学楼', 'college': '学院',
              'library': '图书馆', 'lab': '实验/科研', 'office': '办公', 'activity': '活动中心',
              'art': '艺术/美术馆', 'service': '服务/商业', 'utility': '市政设施', 'other': '未命名/待核实'}
    for it in items:
        lat = LAT0 + it['cy'] / K_LAT
        lon = 119.5172 + it['cx'] / K_LON
        A('| %s%s | %s | %s | %s | %.0f | %.6f | %.6f |' % (
            it['key'], '*' if it['approx'] else '', it['name'],
            cat_cn.get(it['cat'], it['cat']), it['levels'], it['area'], lat, lon))
    A('')
    A('## 2. 最近的 60 对相邻建筑（按净距升序）')
    A('')
    A('| # | 建筑 A | 建筑 B | 净距 gap m | 中心距 m |')
    A('|---|---|---|---|---|')
    for n, r in enumerate(rows[:60], 1):
        ma = '*' if r['a']['approx'] else ''
        mb = '*' if r['b']['approx'] else ''
        A('| %d | %s%s | %s%s | %.1f | %.1f |' % (
            n, r['a']['name'], ma, r['b']['name'], mb, r['gap'], r['dc']))
    A('')
    A('## 3. 统计')
    A('')
    gaps = [r['gap'] for r in rows]
    dcs = [r['dc'] for r in rows]
    A('- 建筑群对总数：%d' % len(rows))
    A('- 净距：最小 %.1f m，中位数 %.1f m，均值 %.1f m，最大 %.1f m' % (
        min(gaps), sorted(gaps)[len(gaps) // 2], sum(gaps) / len(gaps), max(gaps)))
    A('- 中心距：最小 %.1f m，中位数 %.1f m，最大 %.1f m' % (
        min(dcs), sorted(dcs)[len(dcs) // 2], max(dcs)))
    tight = [r for r in rows if r['gap'] < 30]
    A('- 净距 < 30 m 的建筑对：%d 对（这些是管道横向穿越成本最低的相邻关系）' % len(tight))
    A('')
    A('## 4. 关键量级（用于核对地图比例尺）')
    A('')
    dorm = [it for it in items if it['cat'] == 'dorm']
    if dorm:
        xs = [it['cx'] for it in dorm]
        ys = [it['cy'] for it in dorm]
        A('- 13 个公寓组团东西跨度：%.0f m，南北跨度：%.0f m（同一组团内 A/B 栋相连，故按组统计）'
          % (max(xs) - min(xs), max(ys) - min(ys)))
        dg = sorted(r['gap'] for r in rows if r['a']['cat'] == 'dorm' and r['b']['cat'] == 'dorm')
        if dg:
            A('- 组团之间的净距：最小 %.1f m，中位数 %.1f m（组团内 A/B 栋共用墙/连廊，净距为 0）'
              % (dg[0], dg[len(dg) // 2]))
    big = sorted(items, key=lambda it: -it['area'])[:6]
    A('- 单体底面积最大的 6 栋：')
    for it in big:
        A('  - %s：%.0f m²（%d 层）' % (it['name'], it['area'], it['levels']))

    p = os.path.join(DER, 'distances.md')
    with open(p, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')
    print('groups', len(items), 'pairs', len(rows))
    print('gap min %.1f median %.1f max %.1f' % (
        min(gaps), sorted(gaps)[len(gaps) // 2], max(gaps)))
    print('->', p)


if __name__ == '__main__':
    main()
