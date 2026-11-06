# -*- coding: utf-8 -*-
"""按当前 72 组注册表（scripts/groups.py）重建管道方案数据包。

与 build_data.py 的区别：
  * 建筑名录 / 名称 / 分类 / 层数 / 几何 全部以 groups.py 为唯一真源
  * 需求点从"34 栋学生公寓"扩展到"全部已定位建筑群 + 水源"
  * OSM 几何从 data/raw/buildings.json 取（setdefault 去重，第三教学楼有重复）
  * 影像量测条目用 measured['bbox'] 矩形代理 footprint，面积取 measured['area_m2']
  * 没有几何的占位条目（Y01-Y11）不参与计算

输出 data/derived/pipeline_bundle.json（覆盖旧版）
      data/derived/build_report_v2.txt
      data/derived/pipes_v2.geojson
      data/derived/targets_v2.csv
"""
import json, math, os, csv, heapq, datetime, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, 'data', 'raw')
OUT = os.path.join(BASE, 'data', 'derived')
sys.path.insert(0, os.path.join(BASE, 'scripts'))
import groups as G

LAT0, LON0 = 39.9111, 119.5172
K_LAT = 111320.0
K_LON = 111320.0 * math.cos(math.radians(LAT0))
KH = 2.5                     # 时变化系数
PEAK_HOURS = 24.0 / KH       # 高峰等效小时数：由 Kh 定义反推（Kh=最高时/平均时 → 平均时流量×Kh = 日量/24×Kh）
V_PIPE = 1.0                 # 经济流速 m/s
LEVEL_HEIGHT = 3.2           # 层高 m
DN_LIST = [32, 40, 50, 65, 80, 100, 125, 150, 200, 250, 300, 350, 400, 500]
# 综合单价 元/m：球墨铸铁给水管（含管材、管件、土方、回填、路面恢复）
DN_COST = {32: 140, 40: 160, 50: 185, 65: 225, 80: 270, 100: 330, 125: 400,
           150: 480, 200: 620, 250: 800, 300: 1000, 350: 1200, 400: 1450, 500: 1900}

# 用水指标 L/(m2·d)；cat 名称与 groups.py 一致
WATER_LPM2 = {
    'dorm': 12.0, 'canteen': 40.0, 'service': 8.0, 'teaching': 5.0,
    'office': 6.0, 'library': 5.0, 'sports': 3.0, 'lab': 6.0, 'art': 3.0,
    'college': 5.0, 'activity': 5.0, 'utility': 2.0, 'other': 4.0,
}
DEFAULT_LEVELS = {
    'dorm': 6, 'canteen': 3, 'service': 3, 'teaching': 5, 'office': 5,
    'library': 7, 'sports': 2, 'lab': 5, 'art': 3, 'college': 5,
    'activity': 4, 'utility': 1, 'other': 3,
}


# ---------------------------------------------------------------- helpers
def load(name):
    with open(os.path.join(RAW, name + '.json'), encoding='utf-8') as f:
        return json.load(f)


def meters(lat, lon):
    return ((lon - LON0) * K_LON, (lat - LAT0) * K_LAT)


def lonlat(x, y):
    return (LAT0 + y / K_LAT, LON0 + x / K_LON)


def haversine(lat1, lon1, lat2, lon2):
    dx = (lon2 - lon1) * K_LON
    dy = (lat2 - lat1) * K_LAT
    return math.hypot(dx, dy)


def point_in_poly(lon, lat, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if ((y1 > lat) != (y2 > lat)) and (lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1):
            inside = not inside
    return inside


def poly_area_m2(pts):
    """pts: [(lon,lat)] -> m²（局部切平面）"""
    if len(pts) < 3:
        return 0.0
    a = 0.0
    n = len(pts)
    for i in range(n):
        x1 = (pts[i][0] - LON0) * K_LON
        y1 = (pts[i][1] - LAT0) * K_LAT
        x2 = (pts[(i + 1) % n][0] - LON0) * K_LON
        y2 = (pts[(i + 1) % n][1] - LAT0) * K_LAT
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    if L2 == 0:
        return math.hypot(px - ax, py - ay), ax, ay, 0.0
    t = ((px - ax) * vx + (py - ay) * vy) / L2
    t = max(0.0, min(1.0, t))
    qx, qy = ax + t * vx, ay + t * vy
    return math.hypot(px - qx, py - qy), qx, qy, t


# ---------------------------------------------------------------- 1. 校园边界
bound = load('campus_boundary')['elements']
west = next(e for e in bound if e['id'] == 696074149)
west_poly = [(p['lon'], p['lat']) for p in west['geometry']]

# ---------------------------------------------------------------- 2. 建筑：以 groups.py 为真源
osm_ways = {}
for el in load('buildings')['elements']:
    el_id = el.get('id')
    if el_id is not None:
        osm_ways.setdefault(el_id, el)   # 第三教学楼等有重复 id，去重

buildings, missing = [], []
for g in G.GROUPS:
    name = g['name']
    cat = g['cat']
    levels = g.get('levels') or DEFAULT_LEVELS.get(cat, 3)
    meas = g.get('measured')
    osm_list = [osm_ways[w] for w in g['ways'] if w in osm_ways]
    geom_ok = [el for el in osm_list if len([p for p in (el.get('geometry') or []) if p]) >= 3]

    if geom_ok:
        # 用第一个 OSM way 的名义轮廓作为 footprint（多 way 时取面积最大者）
        best = max(geom_ok, key=lambda el: poly_area_m2(
            [(p['lon'], p['lat']) for p in el['geometry'] if p]))
        fp = [(round(p['lon'], 6), round(p['lat'], 6)) for p in best['geometry'] if p]
        area = sum(poly_area_m2([(p['lon'], p['lat']) for p in el['geometry'] if p])
                   for el in geom_ok)
        lat = sum(p[1] for p in fp) / len(fp)
        lon = sum(p[0] for p in fp) / len(fp)
        src = 'OSM'
    elif meas:
        x0, y0, x1, y1 = meas['bbox']
        fp = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        area = float(meas['area_m2'])
        lat, lon = meas['lat'], meas['lon']
        src = 'measured'
    else:
        missing.append(name)
        continue

    if not point_in_poly(lon, lat, west_poly):
        missing.append(name + '(边界外)')
        continue

    height = levels * LEVEL_HEIGHT
    floor_area = area * levels
    demand = floor_area * WATER_LPM2.get(cat, 4.0)
    buildings.append({
        'id': g['key'], 'name': name, 'short': g.get('short') or name,
        'cat': cat, 'group': g.get('group') or g['key'],
        'levels': levels, 'height': height, 'area': area, 'floor_area': floor_area,
        'demand': demand, 'lat': lat, 'lon': lon, 'footprint': fp,
        'src': src, 'verified': bool(g.get('verified')),
    })

print('buildings from registry: %d, skipped: %d' % (len(buildings), len(missing)))
for m in missing:
    print('   skip', m)
catcnt = {}
for b in buildings:
    catcnt[b['cat']] = catcnt.get(b['cat'], 0) + 1
print('cat counts', catcnt)

# ---------------------------------------------------------------- 3. 路网图
HW_ALLOW = {
    'trunk': 1.0, 'secondary': 1.0, 'tertiary': 1.0, 'residential': 1.0,
    'unclassified': 1.0, 'service': 1.15, 'cycleway': 1.3, 'footway': 1.3,
    'path': 1.6,
}
nodes, edges, adj = {}, {}, {}
next_node, next_edge = [0], [0]
coord_reg = {}


def add_node(lat, lon):
    nid = next_node[0]; next_node[0] += 1
    x, y = meters(lat, lon)
    nodes[nid] = (x, y, lat, lon)
    adj[nid] = []
    coord_reg[(round(lat, 7), round(lon, 7))] = nid
    return nid


def get_node(lat, lon):
    k = (round(lat, 7), round(lon, 7))
    if k in coord_reg:
        return coord_reg[k]
    return add_node(lat, lon)


def add_edge(a, b, hw):
    ll = math.hypot(nodes[a][0] - nodes[b][0], nodes[a][1] - nodes[b][1])
    eid = next_edge[0]; next_edge[0] += 1
    edges[eid] = {'a': a, 'b': b, 'len': ll, 'w': ll * HW_ALLOW.get(hw, 1.2), 'hw': hw}
    adj[a].append(eid); adj[b].append(eid)
    return eid


road_geoms = []
for el in load('roads_with_plaza')['elements']:
    t = el.get('tags', {})
    hw = t.get('highway')
    if hw not in HW_ALLOW:
        continue
    g = [p for p in (el.get('geometry') or []) if p]
    if len(g) < 2:
        continue
    nids = []
    for p in g:
        nid = get_node(p['lat'], p['lon'])
        if not nids or nids[-1] != nid:
            nids.append(nid)
    for i in range(len(nids) - 1):
        add_edge(nids[i], nids[i + 1], hw)
    road_geoms.append({'hw': hw, 'name': t.get('name') or '',
                       'pts': [[round(p['lon'], 6), round(p['lat'], 6)] for p in g]})


def find_nearest_edge(x, y):
    best = None
    for eid, e in edges.items():
        ax, ay = nodes[e['a']][0], nodes[e['a']][1]
        bx, by = nodes[e['b']][0], nodes[e['b']][1]
        d, qx, qy, t = seg_dist(x, y, ax, ay, bx, by)
        if best is None or d < best[0]:
            best = (d, eid, t, qx, qy)
    return best


def insert_target(lat, lon, max_dist=250.0):
    x, y = meters(lat, lon)
    best = find_nearest_edge(x, y)
    if best is None:
        return None, None
    d, eid, t, qx, qy = best
    if d > max_dist:
        return None, d
    e = edges[eid]
    if t < 1e-4:
        return e['a'], d
    if t > 1 - 1e-4:
        return e['b'], d
    edges.pop(eid)
    adj[e['a']].remove(eid)
    adj[e['b']].remove(eid)
    plat, plon = lonlat(qx, qy)
    nid = add_node(plat, plon)
    add_edge(e['a'], nid, e['hw'])
    add_edge(nid, e['b'], e['hw'])
    return nid, d


source_lat, source_lon = 39.902950, 119.517905
src_nid, src_d = insert_target(source_lat, source_lon)
print('source snap %.2f m nid=%s' % (src_d or -1, src_nid))

# ---------------------------------------------------------------- 4. 图算法
INF = float('inf')


def dijkstra(s):
    dist = {s: 0.0}
    prev = {s: None}
    pq = [(0.0, s)]
    while pq:
        dd, u = heapq.heappop(pq)
        if dd > dist.get(u, INF):
            continue
        for eid in adj[u]:
            e = edges[eid]
            v = e['b'] if e['a'] == u else e['a']
            nd = dd + e['w']
            if nd < dist.get(v, INF):
                dist[v] = nd
                prev[v] = (u, eid)
                heapq.heappush(pq, (nd, v))
    return dist, prev


def path_edges(prev, target):
    out, cur = [], target
    while prev.get(cur) is not None:
        p, eid = prev[cur]
        out.append(eid)
        cur = p
    out.reverse()
    return out


def pick_dn(q_ls):
    if q_ls <= 0:
        return DN_LIST[0]
    d_mm = math.sqrt(4.0 * (q_ls / 1000.0) / (math.pi * V_PIPE)) * 1000.0
    for dn in DN_LIST:
        if dn >= d_mm:
            return dn
    return DN_LIST[-1]


def solve(targets, label):
    items = []
    for key, lat, lon, dem, meta in targets:
        nid, d = insert_target(lat, lon)
        if nid is None:
            continue
        items.append({'key': key, 'nid': nid, 'demand': dem, 'snap': d, 'meta': meta})
    alln = [src_nid] + [it['nid'] for it in items]
    D, P = {n: {} for n in alln}, {}
    for n in alln:
        dist, prev = dijkstra(n)
        P[n] = prev
        for m in alln:
            D[n][m] = dist.get(m, INF)
    unreach = [it['key'] for it in items if D[src_nid][it['nid']] == INF]
    if unreach:
        print('UNREACH', len(unreach), unreach[:20])
    parent = {n: n for n in alln}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    pairs = [(D[a][b], a, b) for i, a in enumerate(alln) for b in alln[i + 1:] if D[a][b] < INF]
    pairs.sort(key=lambda z: z[0])
    mst = []
    for wd, a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
            mst.append({'u': a, 'v': b, 'w': wd})
    if len(mst) != len(alln) - 1:
        return {'label': label, 'items': items, 'alln': alln, 'D': D, 'P': P,
                'mst': mst, 'error': 'MST incomplete %d/%d' % (len(mst), len(alln) - 1)}
    tree = {n: [] for n in alln}
    for e in mst:
        tree[e['u']].append((e['v'], e['w']))
        tree[e['v']].append((e['u'], e['w']))
    depth, par, order = {src_nid: 0}, {src_nid: None}, [src_nid]
    qi = 0
    while qi < len(order):
        u = order[qi]; qi += 1
        for v, wd in tree[u]:
            if v not in depth:
                depth[v] = depth[u] + 1
                par[v] = u
                order.append(v)
    dem_by_nid = {it['nid']: it['demand'] for it in items}
    sub = {n: dem_by_nid.get(n, 0.0) for n in alln}
    for u in reversed(order):
        p = par.get(u)
        if p is not None:
            sub[p] += sub[u]
    eid_flow, eid_order = {}, {}
    for u in order:
        p = par.get(u)
        if p is None:
            continue
        for eid in path_edges(P[p], u):
            eid_flow[eid] = eid_flow.get(eid, 0.0) + sub[u]
            eid_order[eid] = min(eid_order.get(eid, 999), depth[u])
    pipes = []
    for eid, flow in eid_flow.items():
        e = edges[eid]
        q_ls = flow / (PEAK_HOURS * 3600.0)
        pipes.append({
            'a': [round(nodes[e['a']][3], 6), round(nodes[e['a']][2], 6)],
            'b': [round(nodes[e['b']][3], 6), round(nodes[e['b']][2], 6)],
            'length': round(e['len'], 2), 'flow': round(flow, 2),
            'q_ls': round(q_ls, 4), 'dn': pick_dn(q_ls),
            'order': eid_order.get(eid, 999),
        })
    dn_len = {}
    for p in pipes:
        dn_len[p['dn']] = dn_len.get(p['dn'], 0) + p['length']
    cost = sum(p['length'] * DN_COST.get(p['dn'], 500) for p in pipes)
    straight = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            straight.append((haversine(a['meta']['lat'], a['meta']['lon'],
                                       b['meta']['lat'], b['meta']['lon']), a['nid'], b['nid']))
    straight.sort(key=lambda z: z[0])
    sp = {it['nid']: it['nid'] for it in items}

    def sfind(a):
        while sp[a] != a:
            sp[a] = sp[sp[a]]; a = sp[a]
        return a

    straight_len = 0.0
    for d, a, b in straight:
        ra, rb = sfind(a), sfind(b)
        if ra != rb:
            sp[ra] = rb; straight_len += d
    deg = {}
    for p in pipes:
        for key in (tuple(p['a']), tuple(p['b'])):
            deg[key] = deg.get(key, 0) + 1
    return {
        'label': label, 'items': items, 'alln': alln, 'D': D, 'P': P, 'mst': mst,
        'depth': depth, 'par': par, 'order': order, 'pipes': pipes,
        'total_len': sum(p['length'] for p in pipes), 'dn_len': dn_len, 'cost': cost,
        'total_demand': sum(it['demand'] for it in items), 'straight_len': straight_len,
        'n_branch': sum(1 for d in deg.values() if d >= 3),
        'n_targets': len(items), 'max_depth': max(depth.values()) if depth else 0,
    }


# 供水目标：排除无名附属建筑（other）与市政设施（utility 为变电站，属强电不入给水管网）
TARGET_CATS = {'dorm', 'canteen', 'teaching', 'college', 'lab', 'library',
               'office', 'activity', 'art', 'service', 'sports'}
target_bld = [b for b in buildings if b['cat'] in TARGET_CATS]
bg_bld = [b for b in buildings if b['cat'] not in TARGET_CATS]
print('target buildings: %d, background only: %d' % (len(target_bld), len(bg_bld)))
targets = [(b['id'], b['lat'], b['lon'], b['demand'], b) for b in target_bld]
sol = solve(targets, 'all_groups')
if 'error' in sol:
    raise SystemExit('ERROR ' + sol['error'])

dorm_targets = [t for t in targets if t[4]['cat'] == 'dorm']
sol_dorm = solve(dorm_targets, 'dorm_only')

# ---------------------------------------------------------------- 5. 输出
nid_of = {it['key']: it['nid'] for it in sol['items']}
snap_of = {it['key']: it['snap'] for it in sol['items']}
for b in buildings:
    b['nid'] = nid_of.get(b['id'])
    b['snap'] = snap_of.get(b['id'])
connected = [b for b in buildings if b.get('nid') is not None]
unconnected = [b for b in buildings if b.get('nid') is None]

areas_out = []
for el in load('areas')['elements']:
    t = el.get('tags') or {}
    g = [p for p in (el.get('geometry') or []) if p]
    if len(g) < 3:
        continue
    lat = sum(p['lat'] for p in g) / len(g)
    lon = sum(p['lon'] for p in g) / len(g)
    if not point_in_poly(lon, lat, west_poly):
        continue
    areas_out.append({
        'name': t.get('name') or '',
        'type': t.get('landuse') or t.get('leisure') or t.get('natural') or t.get('amenity') or '',
        'pts': [[round(p['lon'], 6), round(p['lat'], 6)] for p in g],
    })

st = {
    'n_buildings': len(buildings),
    'n_osm': sum(1 for b in buildings if b['src'] == 'OSM'),
    'n_measured': sum(1 for b in buildings if b['src'] == 'measured'),
    'n_dorms': sum(1 for b in buildings if b['cat'] == 'dorm'),
    'n_skipped': len(missing),
    'n_targets': sol['n_targets'], 'n_unconnected': len(unconnected),
    'total_area_m2': round(sum(b['area'] for b in buildings), 1),
    'total_floor_m2': round(sum(b['floor_area'] for b in buildings), 1),
    'total_demand_lpd': round(sol['total_demand'], 1),
    'total_demand_m3d': round(sol['total_demand'] / 1000, 1),
    'q_total_ls': round(sol['total_demand'] / (PEAK_HOURS * 3600.0), 2),
    'main_dn': max((p['dn'] for p in sol['pipes']), default=0),
    'mst_length_m': round(sum(e['w'] for e in sol['mst']), 1),
    'pipe_length_m': round(sol['total_len'], 1),
    'straight_mst_length_m': round(sol['straight_len'], 1),
    'star_length_m': round(sum(sol['D'][src_nid].get(it['nid'], 0) for it in sol['items']), 1),
    'max_depth': sol['max_depth'], 'n_branch': sol['n_branch'],
    'cost_est_yuan': round(sol['cost'], 0),
    'dn_len': {str(k): round(v, 1) for k, v in sorted(sol['dn_len'].items(), key=lambda z: -z[0])},
    'snap_dist_max': round(max((it['snap'] for it in sol['items']), default=0), 1),
    'dorm_mst_length_m': round(sum(e['w'] for e in sol_dorm.get('mst', [])), 1),
    'dorm_pipe_length_m': round(sol_dorm.get('total_len', 0), 1),
    'dorm_demand_m3d': round(sol_dorm.get('total_demand', 0) / 1000, 1),
    'cat_count': catcnt,
}

bundle = {
    'meta': {
        'title': '燕山大学西校区校园给水管道铺设方案（最小生成树 · 全建筑群）',
        'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        'crs': 'WGS84',
        'origin': [LAT0, LON0],
        'm_per_deg_lat': K_LAT, 'm_per_deg_lon': K_LON,
        'osm_timestamp': load('pois')['osm3s']['timestamp_osm_base'],
        'registry': 'scripts/groups.py',
        'source': {'name': '市政给水接入点（假设：南主门/7号门旁）',
                   'lat': round(nodes[src_nid][2], 6), 'lon': round(nodes[src_nid][3], 6)},
        'assumptions': [
            '建筑名录与分类取自 scripts/groups.py（72 组注册表，唯一真源）',
            '底图数据：OpenStreetMap（ODbL 协议），道路网作为管道敷设走廊',
            '影像量测条目用 bbox 矩形代理轮廓，面积取实测值',
            '日用水量按建筑面积×分类用水指标估算；时变化系数 Kh=2.5',
            '管径按经济流速 v=1.0 m/s 计算，向上取标准公称直径 DN',
            '水源为南主门市政接入点假设（OSM 无给水泵房数据）',
            '造价按综合单价粗估（含管材、土方、接口），仅用于方案比较',
        ],
    },
    'buildings': [{
        'id': b['id'], 'name': b['name'], 'short': b['short'], 'cat': b['cat'],
        'group': b.get('group'), 'levels': b['levels'], 'height': round(b['height'], 1),
        'area': round(b['area'], 1), 'floor_area': round(b['floor_area'], 1),
        'demand': round(b['demand'], 1), 'lat': round(b['lat'], 6), 'lon': round(b['lon'], 6),
        'footprint': [[round(x, 6), round(y, 6)] for x, y in b['footprint']],
        'src': b['src'], 'verified': b['verified'],
    } for b in buildings],
    'dorms': [{
        'id': b['id'], 'name': b['name'], 'group': b.get('group'),
        'lat': round(b['lat'], 6), 'lon': round(b['lon'], 6),
        'levels': b['levels'], 'area': round(b['area'], 1),
        'demand': round(b['demand'], 1), 'nid': b.get('nid'),
    } for b in connected if b['cat'] == 'dorm'],
    'source_node': src_nid,
    'roads': road_geoms,
    'areas': areas_out,
    'pipes': [{'a': p['a'], 'b': p['b'], 'length': p['length'], 'flow': p['flow'],
               'q_ls': p['q_ls'], 'dn': p['dn'], 'order': p['order']} for p in sol['pipes']],
    'tree_edges': [{'u': e['u'], 'v': e['v'], 'w': round(e['w'], 2),
                    'depth': sol['depth'].get(e['v'] if sol['par'].get(e['v']) == e['u'] else e['u'])}
                   for e in sol['mst']],
    'stats': st,
}

with open(os.path.join(OUT, 'pipeline_bundle.json'), 'w', encoding='utf-8') as f:
    json.dump(bundle, f, ensure_ascii=False, separators=(',', ':'))

feats = [{'type': 'Feature', 'properties': {
    'length_m': p['length'], 'dn_mm': p['dn'], 'flow_lpd': p['flow'],
    'q_ls': p['q_ls'], 'layer': p['order']},
    'geometry': {'type': 'LineString', 'coordinates': [p['a'], p['b']]}}
    for p in sol['pipes']]
with open(os.path.join(OUT, 'pipes_v2.geojson'), 'w', encoding='utf-8') as f:
    json.dump({'type': 'FeatureCollection', 'features': feats}, f, ensure_ascii=False)

with open(os.path.join(OUT, 'targets_v2.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['id', '名称', '分类', '层数', '基底面积m2', '建筑面积m2', '日用水量L/d',
                '纬度', '经度', '接路距离m', '来源'])
    for b in sorted(connected, key=lambda z: -z['demand']):
        w.writerow([b['id'], b['name'], b['cat'], b['levels'], round(b['area'], 1),
                    round(b['floor_area'], 1), round(b['demand'], 1),
                    round(b['lat'], 6), round(b['lon'], 6), round(b.get('snap') or 0, 1), b['src']])

# ---------------------------------------------------------------- 6. 报告
L = []
L.append('燕山大学西校区管道铺设 —— 全建筑群方案计算报告（数据源：scripts/groups.py 72 组注册表）')
L.append('生成时间：' + bundle['meta']['generated'])
L.append('OSM 数据时间：' + bundle['meta']['osm_timestamp'])
L.append('')
L.append('== 一、建筑 ==')
L.append('注册表 72 组；参与计算 %d 个（OSM 轮廓 %d + 影像量测 %d）；跳过 %d（无坐标）'
         % (len(buildings), st['n_osm'], st['n_measured'], st['n_skipped']))
L.append('跳过清单：' + ('、'.join(missing) if missing else '无'))
L.append('基底面积合计 %.0f m2，建筑面积合计 %.0f m2' % (st['total_area_m2'], st['total_floor_m2']))
L.append('分类：' + ', '.join('%s=%d' % (k, v) for k, v in sorted(catcnt.items(), key=lambda z: -z[1])))
L.append('')
L.append('== 二、路网图 ==')
L.append('节点 %d，边 %d（unclassified/tertiary/secondary/residential/service/trunk/cycleway/footway/path）'
         % (len(nodes), len(edges)))
L.append('需求点接入 %d/%d，最大接路距离 %.1f m' % (sol['n_targets'], len(buildings), st['snap_dist_max']))
L.append('水源：%s (%.6f, %.6f)' % (bundle['meta']['source']['name'],
                                bundle['meta']['source']['lat'], bundle['meta']['source']['lon']))
L.append('')
L.append('== 三、MST 结果（全建筑群口径）==')
L.append('MST 边数 %d，路网加权总长 %.1f m' % (len(sol['mst']), st['mst_length_m']))
L.append('管道总长 %.1f m' % st['pipe_length_m'])
L.append('对照：直线MST %.1f m（%.2f×）；星形 %.1f m（%.2f×）'
         % (st['straight_mst_length_m'], st['straight_mst_length_m'] / st['mst_length_m'],
            st['star_length_m'], st['star_length_m'] / st['mst_length_m']))
L.append('总用水量 %.1f m3/d，设计流量 %.2f L/s，最粗 DN%d' % (st['total_demand_m3d'], st['q_total_ls'], st['main_dn']))
L.append('最大树深 %d，分支点 %d，造价 %.0f 元' % (st['max_depth'], st['n_branch'], st['cost_est_yuan']))
L.append('管径-长度分布：' + json.dumps(st['dn_len'], ensure_ascii=False))
L.append('')
L.append('== 四、对照：仅学生公寓口径 ==')
L.append('目标 %d，MST %.1f m，管道 %.1f m，用水 %.1f m3/d'
         % (st['n_dorms'], st['dorm_mst_length_m'], st['dorm_pipe_length_m'], st['dorm_demand_m3d']))
L.append('')
L.append('== 五、MST 各边（Kruskal 添加顺序）==')
nm = {it['nid']: it['meta']['short'] for it in sol['items']}
nm[src_nid] = '★水源'
for i, e in enumerate(sol['mst'], 1):
    L.append('  %2d. %-14s -- %-14s %7.1f m' % (i, nm.get(e['u'], e['u']), nm.get(e['v'], e['v']), e['w']))
L.append('')
L.append('== 六、前 20 大用水户 ==')
for b in sorted(connected, key=lambda z: -z['demand'])[:20]:
    L.append('  %-22s %-9s %5.0f m2  %3.0f 层  日用水 %9.0f L' %
             (b['name'], b['cat'], b['area'], b['levels'], b['demand']))
with open(os.path.join(OUT, 'build_report_v2.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(L))

print('OK buildings=%d targets=%d mst=%.1fm pipes=%.1fm cost=%.0f nodes=%d edges=%d'
      % (len(buildings), sol['n_targets'], st['mst_length_m'], st['pipe_length_m'],
         st['cost_est_yuan'], len(nodes), len(edges)))
