# -*- coding: utf-8 -*-
"""燕山大学西校区管道铺设：数据清洗 + 路网图构建 + MST 管道方案计算。

输入  data/raw/*.json   (Overpass / OSM, WGS84)
输出  data/derived/pipeline_bundle.json   可视化用数据包
      data/derived/build_report.txt       计算报告(UTF-8)
      data/derived/pipes.geojson          管道网(GeoJSON, WGS84)
      data/derived/dorms.csv              公寓楼清单
"""
import json, math, os, csv, heapq, re, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, 'data', 'raw')
OUT = os.path.join(BASE, 'data', 'derived')
os.makedirs(OUT, exist_ok=True)

LAT0, LON0 = 39.9111, 119.5172          # 校园近似中心
K_LAT = 111320.0
K_LON = 111320.0 * math.cos(math.radians(LAT0))
KH = 2.5                                 # 时变化系数
V_PIPE = 1.0                             # 经济流速 m/s
LEVEL_HEIGHT = 3.2                       # 层高 m
DN_LIST = [32, 40, 50, 65, 80, 100, 125, 150, 200, 250, 300, 350, 400, 500]
DN_COST = {32: 60, 40: 75, 50: 90, 65: 120, 80: 150, 100: 190, 125: 240,
           150: 300, 200: 420, 250: 560, 300: 720, 350: 880, 400: 1050, 500: 1400}

WATER_LPM2 = {   # 最高日用水量 L/(m2·d) —— 学术估算，可按实际用水定额调整
    'dormitory': 12.0, 'canteen': 40.0, 'service': 8.0, 'teaching': 5.0,
    'office': 6.0, 'library': 5.0, 'hospital': 8.0, 'sports': 3.0,
    'lab': 6.0, 'art': 3.0, 'utility': 2.0, 'other': 4.0,
}
DEFAULT_LEVELS = {
    'dormitory': 6, 'canteen': 3, 'service': 3, 'teaching': 5, 'office': 5,
    'library': 7, 'hospital': 2, 'sports': 2, 'lab': 5, 'art': 2,
    'utility': 1, 'other': 3,
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
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))

def point_in_poly(lon, lat, poly):
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside

def poly_area_m2(pts):
    xy = [meters(lat, lon) for lon, lat in pts]
    s = 0.0
    n = len(xy)
    for i in range(n):
        x1, y1 = xy[i]
        x2, y2 = xy[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0

def seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    ll = vx * vx + vy * vy
    if ll == 0:
        return math.hypot(px - ax, py - ay), ax, ay, 0.0
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / ll))
    qx, qy = ax + t * vx, ay + t * vy
    return math.hypot(px - qx, py - qy), qx, qy, t

# ---------------------------------------------------------------- 1. 校园边界
bound = load('campus_boundary')['elements']
west = next(e for e in bound if e['id'] == 696074149)
west_poly = [(p['lon'], p['lat']) for p in west['geometry']]

# ---------------------------------------------------------------- 2. 建筑清洗与分类
def is_dorm_name(n):
    return bool(re.match(r'^\d+-\s*[AB]', n))

def classify(tags, name):
    n = name or ''
    b = tags.get('building', '')
    if b == 'dormitory' or is_dorm_name(n) or '宿舍' in n or '公寓' in n or ('舍' in n and len(n) <= 4):
        return 'dormitory'
    for kw, cat in [
        ('餐厅', 'canteen'), ('食堂', 'canteen'), ('浴池', 'service'), ('超市', 'service'),
        ('图书馆', 'library'),
        ('医院', 'hospital'), ('医务', 'hospital'),
        ('体育馆', 'sports'), ('体育场', 'sports'), ('操场', 'sports'), ('运动场', 'sports'),
        ('实验', 'lab'), ('材料', 'lab'), ('电气', 'lab'), ('高压', 'lab'), ('工程训练', 'lab'),
        ('艺术', 'art'), ('美术', 'art'), ('雕塑', 'art'), ('像', 'art'),
        ('办公楼', 'office'), ('行政', 'office'),
        ('服务楼', 'service'),
        ('变电站', 'utility'), ('泵', 'utility'), ('换热站', 'utility'), ('锅炉', 'utility'),
        ('学院', 'teaching'), ('教学', 'teaching'), ('里仁', 'teaching'), ('经管', 'teaching'),
    ]:
        if kw in n:
            return cat
    if b in ('school', 'university', 'college'):
        return 'teaching'
    return 'other'

buildings, excluded = [], []
for el in load('buildings')['elements']:
    t = el.get('tags', {})
    g = [p for p in (el.get('geometry') or []) if p]
    if len(g) < 3:
        continue
    lat = sum(p['lat'] for p in g) / len(g)
    lon = sum(p['lon'] for p in g) / len(g)
    name = (t.get('name') or '').strip()
    if not point_in_poly(lon, lat, west_poly):
        excluded.append((name or '(无名)', round(lat, 6), round(lon, 6), t.get('building', '')))
        continue
    cat = classify(t, name)
    lv = t.get('building:levels')
    try:
        levels = float(lv) if lv else float(DEFAULT_LEVELS.get(cat, 3))
    except ValueError:
        levels = float(DEFAULT_LEVELS.get(cat, 3))
    if levels <= 1.5 and cat == 'dormitory':
        levels = 6
    area = poly_area_m2([(p['lon'], p['lat']) for p in g])
    floor_area = area * levels
    demand = floor_area * WATER_LPM2.get(cat, 4.0)
    buildings.append({
        'id': el['id'], 'name': name, 'cat': cat, 'levels': levels,
        'footprint': [[round(p['lon'], 6), round(p['lat'], 6)] for p in g],
        'lat': lat, 'lon': lon, 'area': area, 'floor_area': floor_area,
        'height': levels * LEVEL_HEIGHT, 'demand': demand,
    })

# 组团多边形（无名公寓归组）
group_polys = []
for el in load('areas')['elements']:
    t = el.get('tags', {})
    nm = t.get('name') or ''
    if '组团' in nm:
        g = [p for p in (el.get('geometry') or []) if p]
        if len(g) >= 3:
            nums = ''.join(ch for ch in nm if ch.isdigit())
            group_polys.append({'num': int(nums) if nums else None, 'name': nm,
                                'poly': [(p['lon'], p['lat']) for p in g],
                                'lat': sum(p['lat'] for p in g) / len(g),
                                'lon': sum(p['lon'] for p in g) / len(g)})

for b in buildings:
    if b['cat'] != 'dormitory':
        continue
    m = re.match(r'^(\d+)-', b['name'])
    if m:
        b['group'] = int(m.group(1))
    else:
        cands = [gp for gp in group_polys
                 if point_in_poly(b['lon'], b['lat'], gp['poly'])]
        if not cands:
            cands = sorted(group_polys, key=lambda gp: haversine(
                b['lat'], b['lon'], gp['lat'], gp['lon']))[:1]
        cands.sort(key=lambda gp: haversine(b['lat'], b['lon'], gp['lat'], gp['lon']))
        b['group'] = cands[0]['num'] if cands else None

dorms = [b for b in buildings if b['cat'] == 'dormitory']
unnamed = sorted([b for b in dorms if not b['name']], key=lambda z: (z['lat'], z['lon']))
for i, b in enumerate(unnamed, 1):
    b['name'] = f'未命名公寓{i}'
named_dorms = [b for b in dorms if is_dorm_name(b['name'])]

# ---------------------------------------------------------------- 3. 路网图（按 OSM 节点坐标全局合并）
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
for el in load('roads')['elements']:
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

# 水源：南主门（7号门）市政给水接入点（假设）
source_lat, source_lon = 39.902950, 119.517905
src_nid, src_d = insert_target(source_lat, source_lon)
print('source snap dist %.4f m, nid=%s, adj=%d' % (src_d or -1, src_nid, len(adj.get(src_nid, []))))
if src_nid is not None:
    for eid in adj.get(src_nid, []):
        e = edges[eid]
        v = e['b'] if e['a'] == src_nid else e['a']
        print('  src edge', eid, e['hw'], 'len %.2f' % e['len'], 'other', v, nodes[v][2:])

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
    out = []
    cur = target
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
    """targets: [(key, lat, lon, demand, meta)] -> dict 方案结果"""
    items = []
    w = []
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
        print('src component size', sum(1 for v in D[src_nid].values() if v < INF), 'of', len(nodes))
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
        return {'label': label, 'items': items, 'alln': alln, 'D': D, 'P': P, 'mst': mst,
                'error': f'MST incomplete {len(mst)}/{len(alln)-1}'}
    tree = {n: [] for n in alln}
    for e in mst:
        tree[e['u']].append((e['v'], e['w']))
        tree[e['v']].append((e['u'], e['w']))
    depth, par = {src_nid: 0}, {src_nid: None}
    order = [src_nid]
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
        q_ls = flow * KH / 86400.0
        pipes.append({
            'a': [round(nodes[e['a']][3], 6), round(nodes[e['a']][2], 6)],
            'b': [round(nodes[e['b']][3], 6), round(nodes[e['b']][2], 6)],
            'length': round(e['len'], 2), 'flow': round(flow, 2),
            'q_ls': round(q_ls, 4), 'dn': pick_dn(q_ls),
            'order': eid_order.get(eid, 999),
        })
    total_len = sum(p['length'] for p in pipes)
    dn_len = {}
    for p in pipes:
        dn_len[p['dn']] = dn_len.get(p['dn'], 0) + p['length']
    cost = sum(p['length'] * DN_COST.get(p['dn'], 500) for p in pipes)
    total_demand = sum(it['demand'] for it in items)
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
    # 井：分支点（度>=3）与接户点
    deg = {}
    for p in pipes:
        for key in (tuple(p['a']), tuple(p['b'])):
            deg[key] = deg.get(key, 0) + 1
    n_branch = sum(1 for d in deg.values() if d >= 3)
    # 建成图来算总长度与连通点
    return {
        'label': label, 'items': items, 'alln': alln, 'D': D, 'P': P, 'mst': mst,
        'depth': depth, 'par': par, 'order': order, 'pipes': pipes,
        'total_len': total_len, 'dn_len': dn_len, 'cost': cost,
        'total_demand': total_demand, 'straight_len': straight_len,
        'n_branch': n_branch, 'n_targets': len(items),
        'max_depth': max(depth.values()) if depth else 0,
    }

def graph_components():
    seen, comps = set(), []
    for n in adj:
        if n in seen:
            continue
        stack, comp = [n], []
        seen.add(n)
        while stack:
            u = stack.pop()
            comp.append(u)
            for eid in adj.get(u, ()):
                e = edges[eid]
                v = e['b'] if e['a'] == u else e['a']
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    return comps

comps = graph_components()
print('graph components:', [len(c) for c in comps[:8]])

dorm_targets = [(b['id'], b['lat'], b['lon'], b['demand'], b) for b in dorms]
sol = solve(dorm_targets, 'dorm_only')
ext_buildings = [b for b in buildings if b['cat'] in ('canteen', 'service')]
sol_ext = solve(dorm_targets + [(b['id'], b['lat'], b['lon'], b['demand'], b) for b in ext_buildings],
                'extended')

if 'error' in sol:
    raise SystemExit('ERROR ' + sol['error'])

# 把 nid 写回 building
nid_of = {it['key']: it['nid'] for it in sol['items']}
snap_of = {it['key']: it['snap'] for it in sol['items']}
for b in dorms:
    b['nid'] = nid_of.get(b['id'])
    b['snap'] = snap_of.get(b['id'])
connected = [b for b in dorms if b.get('nid') is not None]
unconnected = [b for b in dorms if b.get('nid') is None]

# ---------------------------------------------------------------- 5. 输出
def round_pipes(pipes):
    return [{'a': p['a'], 'b': p['b'], 'length': p['length'], 'flow': p['flow'],
             'q_ls': p['q_ls'], 'dn': p['dn'], 'order': p['order']} for p in pipes]

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

bundle = {
    'meta': {
        'title': '燕山大学西校区校园给水管道铺设方案（最小生成树）',
        'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        'crs': 'WGS84',
        'origin': [LAT0, LON0],
        'm_per_deg_lat': K_LAT, 'm_per_deg_lon': K_LON,
        'osm_timestamp': load('pois')['osm3s']['timestamp_osm_base'],
        'source': {'name': '市政给水接入点（假设：南主门/7号门旁）',
                   'lat': round(nodes[src_nid][2], 6), 'lon': round(nodes[src_nid][3], 6)},
        'assumptions': [
            '底图数据：OpenStreetMap（ODbL 协议），道路网作为管道敷设走廊',
            '日用水量按建筑面积×分类用水指标估算；时变化系数 Kh=2.5',
            '管径按经济流速 v=1.0 m/s 计算，并向上取标准公称直径 DN（×10⁻¹ mm）',
            '水源点为南主门市政给水接入点假设（OSM 中无给水泵房数据）',
            '造价按综合单价粗估（含管材、土方、接口），仅用于方案比较',
        ],
    },
    'buildings': [{
        'id': b['id'], 'name': b['name'], 'cat': b['cat'], 'group': b.get('group'),
        'levels': b['levels'], 'height': round(b['height'], 1), 'area': round(b['area'], 1),
        'floor_area': round(b['floor_area'], 1), 'demand': round(b['demand'], 1),
        'lat': round(b['lat'], 6), 'lon': round(b['lon'], 6),
        'footprint': b['footprint'],
    } for b in buildings],
    'dorms': [{
        'id': b['id'], 'name': b['name'], 'group': b.get('group'),
        'lat': round(b['lat'], 6), 'lon': round(b['lon'], 6),
        'levels': b['levels'], 'area': round(b['area'], 1),
        'demand': round(b['demand'], 1), 'nid': b.get('nid'),
    } for b in connected],
    'source_node': src_nid,
    'roads': road_geoms,
    'areas': areas_out,
    'pipes': round_pipes(sol['pipes']),
    'tree_edges': [{'u': e['u'], 'v': e['v'], 'w': round(e['w'], 2),
                    'depth': sol['depth'].get(e['v'] if sol['par'].get(e['v']) == e['u'] else e['u'])}
                   for e in sol['mst']],
    'stats': {
        'n_buildings_in_campus': len(buildings),
        'n_dorms': len(dorms), 'n_named_dorms': len(named_dorms),
        'n_unnamed_dorms': len(unnamed),
        'n_targets': sol['n_targets'], 'n_unconnected': len(unconnected),
        'total_demand_lpd': round(sol['total_demand'], 1),
        'total_demand_m3d': round(sol['total_demand'] / 1000, 1),
        'q_total_ls': round(sol['total_demand'] * KH / 86400, 2),
        'main_dn': max((p['dn'] for p in sol['pipes']), default=0),
        'mst_length_m': round(sum(e['w'] for e in sol['mst']), 1),
        'pipe_length_m': round(sol['total_len'], 1),
        'straight_mst_length_m': round(sol['straight_len'], 1),
        'star_length_m': round(sum(sol['D'][src_nid].get(it['nid'], 0) for it in sol['items']), 1),
        'max_depth': sol['max_depth'],
        'n_branch': sol['n_branch'],
        'cost_est_yuan': round(sol['cost'], 0),
        'dn_len': {str(k): round(v, 1) for k, v in sorted(sol['dn_len'].items(), key=lambda z: -z[0])},
        'snap_dist_max': round(max((it['snap'] for it in sol['items']), default=0), 1),
        'ext_n_targets': sol_ext.get('n_targets', 0),
        'ext_mst_length_m': round(sum(e['w'] for e in sol_ext['mst']), 1) if 'error' not in sol_ext else None,
        'ext_pipe_length_m': round(sol_ext.get('total_len', 0), 1),
        'ext_total_demand_lpd': round(sol_ext.get('total_demand', 0), 1),
        'ext_names': [b['name'] or b['cat'] for b in ext_buildings],
    },
}
with open(os.path.join(OUT, 'pipeline_bundle.json'), 'w', encoding='utf-8') as f:
    json.dump(bundle, f, ensure_ascii=False, separators=(',', ':'))

feats = [{'type': 'Feature', 'properties': {
    'length_m': p['length'], 'dn_mm': p['dn'], 'flow_lpd': p['flow'],
    'q_ls': p['q_ls'], 'layer': p['order']},
    'geometry': {'type': 'LineString', 'coordinates': [p['a'], p['b']]}}
    for p in sol['pipes']]
with open(os.path.join(OUT, 'pipes.geojson'), 'w', encoding='utf-8') as f:
    json.dump({'type': 'FeatureCollection', 'features': feats}, f, ensure_ascii=False)

with open(os.path.join(OUT, 'dorms.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['id', '名称', '组团', '层数', '基底面积m2', '建筑面积m2', '日用水量L/d',
                '纬度', '经度', '接路距离m'])
    for b in sorted(connected, key=lambda z: (z.get('group') or 99, z['name'])):
        w.writerow([b['id'], b['name'], b.get('group'), b['levels'], round(b['area'], 1),
                    round(b['floor_area'], 1), round(b['demand'], 1),
                    round(b['lat'], 6), round(b['lon'], 6), round(b.get('snap') or 0, 1)])

# ---------------------------------------------------------------- 6. 报告
st = bundle['stats']
L = []
L.append('燕山大学西校区管道铺设 —— 数据构建与算法结果报告')
L.append('生成时间：' + bundle['meta']['generated'])
L.append('OSM 数据时间：' + bundle['meta']['osm_timestamp'])
L.append('')
L.append('== 一、建筑清洗 ==')
L.append(f'校园边界内建筑 {len(buildings)} 栋；边界外剔除 {len(excluded)} 栋（含东校区、秦皇岛一中、周边小区）')
L.append(f'学生公寓 {len(dorms)} 栋：有编号 {len(named_dorms)} 栋，未命名 {len(unnamed)} 栋')
L.append('公寓清单（按组团）：')
for b in sorted(connected, key=lambda z: (z.get('group') or 99, z['name'])):
    L.append(f"  {b['name']:12s} 组团{b.get('group')}  {b['levels']:.0f}层  "
             f"底面积{b['area']:6.0f}m2 建筑{b['floor_area']:7.0f}m2  日用水{b['demand']:8.0f}L")
if unconnected:
    L.append('未能接入路网: ' + ', '.join(b['name'] for b in unconnected))
L.append('')
L.append('== 二、路网图 ==')
L.append(f'图节点 {len(nodes)}，边 {len(edges)}（仅保留可通行/可开挖道路：unclassified/tertiary/'
         f'secondary/residential/service/trunk/cycleway/footway/path，排除 steps/construction）')
L.append(f'公寓接入点 {sol["n_targets"]}/{len(dorms)}，最大接路距离 {st["snap_dist_max"]} m')
L.append(f'水源: {bundle["meta"]["source"]["name"]}  ({bundle["meta"]["source"]["lat"]}, '
         f'{bundle["meta"]["source"]["lon"]})')
L.append('')
L.append('== 三、MST 算法结果（公寓方案） ==')
L.append(f'MST 边数 {len(sol["mst"])}，路网加权总长 {st["mst_length_m"]} m')
L.append(f'实际管道总长 {st["pipe_length_m"]} m（沿路网展开的重叠段合并前）')
L.append(f'对照：直线MST {st["straight_mst_length_m"]} m；星形（每楼单独供水）{st["star_length_m"]} m')
L.append(f'总用水量 {st["total_demand_m3d"]} m3/d，设计总流量 {st["q_total_ls"]} L/s，最粗 DN{st["main_dn"]}')
L.append(f'最大树深 {st["max_depth"]} 层，分支点 {st["n_branch"]} 个，估算造价 {st["cost_est_yuan"]:.0f} 元')
L.append('管径-长度分布：' + str(st['dn_len']))
L.append('')
L.append('== 四、扩展方案（公寓+食堂+服务楼） ==')
L.append(f'目标 {st["ext_n_targets"]} 个，MST {st["ext_mst_length_m"]} m，管道 {st["ext_pipe_length_m"]} m，'
         f'总用水量 {st["ext_total_demand_lpd"]/1000:.1f} m3/d')
L.append('扩展节点：' + ', '.join(st['ext_names']))
L.append('')
L.append('== 五、MST 各边（Kruskal 添加顺序） ==')
nm = {it['nid']: it['meta']['name'] for it in sol['items']}
nm[src_nid] = '★水源'
for i, e in enumerate(sol['mst'], 1):
    L.append(f'  {i:2d}. {nm.get(e["u"], e["u"]):12s} -- {nm.get(e["v"], e["v"]):12s}  {e["w"]:7.1f} m')
L.append('')
L.append('== 六、管段清单（按铺设层级，从水源向外） ==')
for p in sorted(sol['pipes'], key=lambda z: (z['order'], -z['dn'], -z['length'])):
    L.append(f"  L{p['order']:2d}  DN{p['dn']:3d}  {p['length']:7.1f}m  流量{p['flow']:9.0f}L/d  {p['q_ls']:6.2f}L/s")
with open(os.path.join(OUT, 'build_report.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(L))

print('OK buildings=%d dorms=%d targets=%d mst=%.1fm pipes=%.1fm nodes=%d edges=%d' % (
    len(buildings), len(dorms), sol['n_targets'], st['mst_length_m'], st['pipe_length_m'],
    len(nodes), len(edges)))
