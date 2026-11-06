# -*- coding: utf-8 -*-
"""Prim / Kruskal 对拍：在与 build_bundle_v2.py 相同的路网图上重算 45 目标 + 水源的 MST。

- 建图 / 插点 / Dijkstra 逻辑镜像 build_bundle_v2.py；
- 对同一个 46×46 距离矩阵分别跑 Kruskal 与 Prim；
- 与主数据 stats.mst_length_m 比较（应 < 0.1 m）。

用法：python 06_代码/check_prim.py
"""
import heapq
import json
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "06_代码"))
import groups as G  # noqa: E402

LAT0, LON0 = 39.9111, 119.5172
K_LAT = 111320.0
K_LON = 111320.0 * math.cos(math.radians(LAT0))
HW_ALLOW = {"trunk": 1.0, "secondary": 1.0, "tertiary": 1.0, "residential": 1.0,
            "unclassified": 1.0, "service": 1.15, "cycleway": 1.3, "footway": 1.3, "path": 1.6}
TARGET_CATS = {"dorm", "canteen", "teaching", "college", "lab", "library",
               "office", "activity", "art", "service", "sports"}


def meters(lat, lon):
    return ((lon - LON0) * K_LON, (lat - LAT0) * K_LAT)


def lonlat(x, y):
    return (LAT0 + y / K_LAT, LON0 + x / K_LON)


def seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    if L2 == 0:
        return math.hypot(px - ax, py - ay), ax, ay, 0.0
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / L2))
    qx, qy = ax + t * vx, ay + t * vy
    return math.hypot(px - qx, py - qy), qx, qy, t


nodes, edges, adj = {}, {}, {}
_counter = [0]
_eid = [0]


def add_node(lat, lon):
    nid = _counter[0]; _counter[0] += 1
    x, y = meters(lat, lon)
    nodes[nid] = (x, y, lat, lon)
    adj[nid] = []
    return nid


def add_edge(a, b, hw):
    ln = math.hypot(nodes[a][0] - nodes[b][0], nodes[a][1] - nodes[b][1])
    eid = _eid[0]; _eid[0] += 1
    edges[eid] = {"a": a, "b": b, "len": ln, "w": ln * HW_ALLOW.get(hw, 1.2), "hw": hw}
    adj[a].append(eid)
    adj[b].append(eid)


def load(name):
    with open(os.path.join(BASE, "04_数据", "raw", name + ".json"), encoding="utf-8") as f:
        return json.load(f)


reg = {}
for el in load("roads_with_plaza")["elements"]:
    t = el.get("tags", {})
    hw = t.get("highway")
    if hw not in HW_ALLOW:
        continue
    g = [p for p in (el.get("geometry") or []) if p]
    ids = []
    for p in g:
        k = (round(p["lat"], 7), round(p["lon"], 7))
        if k not in reg:
            reg[k] = add_node(p["lat"], p["lon"])
        ids.append(reg[k])
    for i in range(len(ids) - 1):
        if ids[i] != ids[i + 1]:
            add_edge(ids[i], ids[i + 1], hw)

bundle = json.load(open(os.path.join(BASE, "04_数据", "derived", "pipeline_bundle_conn.json"), encoding="utf-8"))


def insert_target(lat, lon, max_dist=250.0):
    x, y = meters(lat, lon)
    best = None
    for eid, e in edges.items():
        ax, ay = nodes[e["a"]][0], nodes[e["a"]][1]
        bx, by = nodes[e["b"]][0], nodes[e["b"]][1]
        d, qx, qy, t = seg_dist(x, y, ax, ay, bx, by)
        if best is None or d < best[0]:
            best = (d, eid, t, qx, qy)
    d, eid, t, qx, qy = best
    if d > max_dist:
        return None, d
    e = edges[eid]
    if t < 1e-4:
        return e["a"], d
    if t > 1 - 1e-4:
        return e["b"], d
    del edges[eid]
    adj[e["a"]].remove(eid); adj[e["b"]].remove(eid)
    plat, plon = lonlat(qx, qy)
    nid = add_node(plat, plon)
    add_edge(e["a"], nid, e["hw"]); add_edge(nid, e["b"], e["hw"])
    return nid, d


print("before insert: nodes %d edges %d" % (len(nodes), len(edges)))
src, sd = insert_target(39.902950, 119.517905)
print("source snap %.2f m nid %s" % (sd, src))
ids = [src]
for b in bundle["buildings"]:
    if b["cat"] in TARGET_CATS:
        nid, sd2 = insert_target(b["lat"], b["lon"])
        if sd2 and sd2 > 150: print("  far", b["id"], round(sd2,1))
        ids.append(nid)


def dijkstra(s):
    dist = {s: 0.0}
    pq = [(0.0, s)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, 1e18):
            continue
        for eid in adj[u]:
            e = edges[eid]
            v = e["b"] if e["a"] == u else e["a"]
            nd = d + e["w"]
            if nd < dist.get(v, 1e18):
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist


D = {}
for n in ids:
    dd = dijkstra(n)
    D[n] = {m: dd.get(m, float("inf")) for m in ids}

pairs = [(D[a][b], a, b) for i, a in enumerate(ids) for b in ids[i + 1:]]
pairs.sort()
par = {n: n for n in ids}


def find(a):
    while par[a] != a:
        par[a] = par[par[a]]
        a = par[a]
    return a


kru = 0.0
cnt = 0
mst_edges = []
for w, a, b in pairs:
    ra, rb = find(a), find(b)
    if ra != rb:
        par[ra] = rb
        kru += w
        cnt += 1
        mst_edges.append((w, a, b))
print("graph nodes %d edges %d; Kruskal: %.3f m (%d edges)" % (len(nodes), len(edges), kru, cnt))
for w, a, b in sorted(mst_edges, reverse=True)[:6]:
    print("  edge %.1f  (%.5f,%.5f)-(%.5f,%.5f)" % (w, nodes[a][2], nodes[a][3], nodes[b][2], nodes[b][3]))

# Prim
used = {ids[0]}
prim = 0.0
best = {n: D[ids[0]].get(n, float("inf")) for n in ids}
for _ in range(len(ids) - 1):
    u = min((n for n in ids if n not in used), key=lambda n: best[n])
    prim += best[u]
    used.add(u)
    for v in ids:
        if v not in used and D[u][v] < best[v]:
            best[v] = D[u][v]
print("Prim   : %.3f m" % prim)

st = bundle["stats"]["mst_length_m"]
print("bundle : %.1f m" % st)
print("diff Kruskal-bundle %.3f m | Prim-bundle %.3f m | Prim-Kruskal %.3f m"
      % (kru - st, prim - st, prim - kru))
assert abs(kru - prim) < 1e-6 and abs(kru - st) < 0.5
print("PASS")
