# -*- coding: utf-8 -*-
"""Inventory all OSM buildings inside the YSU west-campus boundary.

Outputs (UTF-8, machine-readable for later steps, human-readable for report):
  data/derived/buildings_inventory.csv   one row per building inside boundary
  data/derived/buildings_inventory.md    grouped table + OSM data gap list

Usage: python scripts/inventory_buildings.py
"""
import json
import math
import os
import re
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')
DER = os.path.join(ROOT, 'data', 'derived')

# WGS-84 local metric approximation around the campus
LAT0 = 39.9111
LON0 = 119.5172
K_LAT = 111320.0
K_LON = 111320.0 * math.cos(math.radians(LAT0))


def load(name):
    with open(os.path.join(RAW, name), 'r', encoding='utf-8') as f:
        return json.load(f)


def poly_from_element(el):
    g = el.get('geometry') or []
    return [(p['lat'], p['lon']) for p in g if p.get('lat') is not None]


def ring_area_m2(pts):
    """Signed-ish planar area in m^2 using the local metric approximation."""
    if len(pts) < 3:
        return 0.0
    acc = 0.0
    xy = [((lon - LON0) * K_LON, (lat - LAT0) * K_LAT) for lat, lon in pts]
    for i in range(len(xy)):
        x1, y1 = xy[i]
        x2, y2 = xy[(i + 1) % len(xy)]
        acc += x1 * y2 - x2 * y1
    return abs(acc) / 2.0


def centroid(pts):
    if not pts:
        return (None, None)
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def point_in_poly(lat, lon, poly):
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        yi, xi = poly[i]
        yj, xj = poly[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-18) + xi):
            inside = not inside
        j = i
    return inside


DORM_RE = re.compile(r'^\s*(\d{1,2})\s*[-–]?\s*([AB])\s*([12])?\s*$', re.I)
NUM_RE = re.compile(r'^\s*(\d{1,2})\s*[-–]\s*([A-Za-z0-9]+)\s*$', re.I)


def classify(name, tags):
    """Return (category, category_note) — rule based, auditable."""
    n = (name or '').strip()
    t = tags or {}
    if t.get('building') == 'dormitory' and not n:
        return 'dorm', 'tag:dormitory（无名）'
    if n and DORM_RE.match(n) and t.get('building') in ('dormitory', 'yes', 'university', None):
        return 'dorm', 'name:楼号 (%s)' % (t.get('building') or '无 building 标签')
    low = n
    for kw, cat in (
        ('公寓', 'dorm'), ('宿舍', 'dorm'), ('餐厅', 'canteen'), ('食堂', 'canteen'),
        ('教学', 'teaching'), ('经管', 'teaching'), ('图书馆', 'library'),
        ('办公', 'office'), ('实验', 'lab'), ('材料', 'lab'), ('高压', 'lab'),
        ('医院', 'hospital'), ('体育馆', 'sports'), ('体育', 'sports'),
        ('艺术', 'art'), ('美术', 'art'), ('活动中心', 'activity'),
        ('服务楼', 'service'), ('超市', 'service'), ('锅炉', 'utility'),
        ('换热', 'utility'), ('泵', 'utility'), ('变电', 'utility'),
        ('学院', 'college'), ('中心', 'center'),
    ):
        if kw in low:
            return cat, 'name:%s' % kw
    if t.get('building') == 'university':
        return 'university', 'tag:building=university'
    if t.get('building') == 'school':
        return 'school', 'tag:building=school'
    if t.get('building') in ('yes', 'office', 'residential', 'commercial'):
        return 'other', 'tag:building=%s' % t['building']
    return 'unknown', 'tag:building=%s' % (t.get('building') or '无')


def tag_str(tags):
    keep = ['name', 'name:en', 'building', 'building:levels', 'height', 'amenity', 'shop',
            'office', 'landuse', 'addr:street', 'addr:housenumber', 'operator', 'description',
            'building:use', 'layer']
    parts = []
    for k in keep:
        if k in tags:
            parts.append('%s=%s' % (k, tags[k]))
    return '; '.join(parts)


def main():
    os.makedirs(DER, exist_ok=True)
    boundary = load('campus_boundary.json')
    west = None
    for el in boundary['elements']:
        tags = el.get('tags') or {}
        if '西' in (tags.get('name') or '') and tags.get('amenity') == 'university':
            west = poly_from_element(el)
            break
    if west is None:
        el = boundary['elements'][0]
        west = poly_from_element(el)

    buildings = load('buildings.json')
    areas = load('areas.json')
    pois = load('pois.json')

    rows = []
    outside = []
    for el in buildings['elements']:
        tags = el.get('tags') or {}
        pts = poly_from_element(el)
        if not pts:
            continue
        clat, clon = centroid(pts)
        inside = point_in_poly(clat, clon, west)
        cat, note = classify(tags.get('name'), tags)
        area = ring_area_m2(pts)
        rec = {
            'osm_id': el['id'],
            'name': tags.get('name') or '',
            'cat': cat,
            'cat_note': note,
            'levels': tags.get('building:levels') or '',
            'height': tags.get('height') or '',
            'footprint_m2': round(area, 1),
            'lat': round(clat, 6),
            'lon': round(clon, 6),
            'inside': inside,
            'tags': tag_str(tags),
        }
        (rows if inside else outside).append(rec)

    # dormitory group polygons for reporting
    groups = []
    for el in areas['elements']:
        tags = el.get('tags') or {}
        nm = tags.get('name') or ''
        if '组团' in nm:
            pts = poly_from_element(el)
            clat, clon = centroid(pts)
            groups.append({'osm_id': el['id'], 'name': nm, 'lat': round(clat, 6),
                           'lon': round(clon, 6), 'area_m2': round(ring_area_m2(pts), 1),
                           'inside': point_in_poly(clat, clon, west)})

    cat_order = ['dorm', 'canteen', 'teaching', 'college', 'library', 'lab', 'office',
                 'hospital', 'sports', 'art', 'activity', 'service', 'utility',
                 'university', 'school', 'other', 'unknown']
    by_cat = defaultdict(list)
    for r in sorted(rows, key=lambda r: (cat_order.index(r['cat']) if r['cat'] in cat_order else 99,
                                         r['name'] or 'zzz')):
        by_cat[r['cat']].append(r)

    # ---- CSV ----
    csv_path = os.path.join(DER, 'buildings_inventory.csv')
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        f.write('osm_id,name,cat,cat_note,levels,height,footprint_m2,lat,lon,inside,tags\n')
        for r in rows + outside:
            f.write(','.join('"%s"' % str(r[k]).replace('"', '""') for k in
                             ('osm_id', 'name', 'cat', 'cat_note', 'levels', 'height',
                              'footprint_m2', 'lat', 'lon', 'inside', 'tags')) + '\n')

    # ---- Markdown ----
    lines = []
    A = lines.append
    A('# 西校区建筑清单调查（OSM 全量，自动化生成）')
    A('')
    A('生成脚本：`scripts/inventory_buildings.py`；数据源：`data/raw/buildings.json`（OSM，2026-08-10 快照）。')
    A('边界：`data/raw/campus_boundary.json` 中西校区多边形（way 696074149）。')
    A('')
    A('## 0 汇总')
    A('')
    A('- 原始建筑 way：**%d** 条' % len(rows + outside))
    A('- 边界内：**%d** 栋；边界外被剔除：**%d** 栋' % (len(rows), len(outside)))
    A('- 面积（投影近似）：%.0f m²（边界内）' % sum(r['footprint_m2'] for r in rows))
    A('')
    A('| 类别 | 栋数 | 底面积合计 m² |')
    A('|---|---|---|')
    cat_cn = {'dorm': '学生公寓/宿舍', 'canteen': '食堂/餐厅', 'teaching': '教学楼',
              'college': '学院/中心', 'library': '图书馆', 'lab': '实验楼', 'office': '办公楼',
              'hospital': '医院', 'sports': '体育馆/场地', 'art': '艺术/美术',
              'activity': '活动中心', 'service': '服务/商业', 'utility': '市政设施（锅炉/换热/泵房/变电）',
              'university': 'building=university（用途未标注）', 'school': '学校（非本校）',
              'other': '其他建筑', 'unknown': '未分类'}
    for cat in cat_order:
        if cat in by_cat:
            A('| %s | %d | %.0f |' % (cat_cn.get(cat, cat), len(by_cat[cat]),
                                       sum(r['footprint_m2'] for r in by_cat[cat])))
    A('')
    for cat in cat_order:
        if cat not in by_cat:
            continue
        A('## %s（%s，%d 栋）' % (cat, cat_cn.get(cat, cat), len(by_cat[cat])))
        A('')
        A('| # | 名称 | OSM way id | 底面积 m² | 层数 | 纬度 | 经度 | 标注依据 |')
        A('|---|---|---|---|---|---|---|---|')
        for i, r in enumerate(by_cat[cat], 1):
            A('| %d | %s | %s | %.0f | %s | %.6f | %.6f | %s |' % (
                i, r['name'] or '（无名）', r['osm_id'], r['footprint_m2'],
                r['levels'] or '-', r['lat'], r['lon'], r['cat_note']))
        A('')

    if groups:
        A('## 附：组团面（areas 中 landuse=residential + residential=university）')
        A('')
        A('| 名称 | OSM way id | 面积 m² | 中心纬度 | 中心经度 | 在边界内 |')
        A('|---|---|---|---|---|---|')
        for g in sorted(groups, key=lambda g: g['name']):
            A('| %s | %s | %.0f | %.6f | %.6f | %s |' % (
                g['name'], g['osm_id'], g['area_m2'], g['lat'], g['lon'],
                '是' if g['inside'] else '否'))
        A('')

    A('## 附：边界外被剔除的建筑（校验用，%d 栋）' % len(outside))
    A('')
    A('| 名称 | OSM way id | 底面积 m² | 纬度 | 经度 |')
    A('|---|---|---|---|---|')
    for r in sorted(outside, key=lambda r: r['name']):
        A('| %s | %s | %.0f | %.6f | %.6f |' % (
            r['name'] or '（无名）', r['osm_id'], r['footprint_m2'], r['lat'], r['lon']))
    A('')

    # --- coverage gap analysis: counts + named ratio ---
    A('## 附：OSM 数据完整度自查')
    A('')
    named = [r for r in rows if r['name']]
    A('- 边界内有名建筑：**%d / %d**（%.0f%%）' % (len(named), len(rows), 100.0 * len(named) / max(1, len(rows))))
    A('- 无名建筑：**%d** 栋（见上表"（无名）"行，多为门卫/小配套）' % (len(rows) - len(named)))
    lv = [r for r in rows if r['levels']]
    A('- 带 `building:levels` 的建筑：**%d / %d**（%.0f%%）——层数缺失者需按类别给默认值' % (
        len(lv), len(rows), 100.0 * len(lv) / max(1, len(rows))))
    A('')
    A('POI 节点总数：%d（`data/raw/pois.json`）' % len(pois['elements']))

    md_path = os.path.join(DER, 'buildings_inventory.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    print('OK inside=%d outside=%d cats=%d' % (len(rows), len(outside), len(by_cat)))
    print('CSV  ->', csv_path)
    print('MD   ->', md_path)


if __name__ == '__main__':
    main()
