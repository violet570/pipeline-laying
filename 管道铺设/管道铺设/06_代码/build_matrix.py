# -*- coding: utf-8 -*-
"""生成作业要求的「无向图距离矩阵」文本 + Prim/Kruskal 生成过程文本。

- 节点：水源 + 45 个供水目标（与 bundle 的 buildings 顺序一致）
- 权重：沿路网的最短距离，按道路等级加权（与 build_bundle_v2.py 的 MST 边权一致）
- 输出：
    04_数据/derived/graph_matrix.txt         矩阵 + 节点表（文本，系统读取的源）
    04_数据/derived/graph_mst_process.txt    Kruskal / Prim 生成过程（文本）
    05_图件/管道方案/graph_matrix.js         同一份文本的 JS 包装（便于 file:// 打开时读取）

用法：python 06_代码/build_matrix.py
"""
import heapq
import json
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "06_代码"))

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


def main():
    bundle = json.load(open(os.path.join(BASE, "04_数据", "derived",
                                         "pipeline_bundle_conn.json"), encoding="utf-8"))
    roads = json.load(open(os.path.join(BASE, "04_数据", "raw",
                                        "roads_with_plaza.json"), encoding="utf-8"))["elements"]

    nodes, edges, adj = {}, {}, {}
    counter = [0]
    eidc = [0]

    def add_node(lat, lon):
        nid = counter[0]; counter[0] += 1
        x, y = meters(lat, lon)
        nodes[nid] = (x, y, lat, lon)
        adj[nid] = []
        return nid

    def add_edge(a, b, hw):
        ln = math.hypot(nodes[a][0] - nodes[b][0], nodes[a][1] - nodes[b][1])
        eid = eidc[0]; eidc[0] += 1
        edges[eid] = {"a": a, "b": b, "len": ln, "w": ln * HW_ALLOW.get(hw, 1.2), "hw": hw}
        adj[a].append(eid); adj[b].append(eid)

    reg = {}
    for el in roads:
        t = el.get("tags", {})
        hw = t.get("highway")
        if hw not in HW_ALLOW:
            continue
        ids = []
        for p in (el.get("geometry") or []):
            k = (round(p["lat"], 7), round(p["lon"], 7))
            if k not in reg:
                reg[k] = add_node(p["lat"], p["lon"])
            ids.append(reg[k])
        for i in range(len(ids) - 1):
            if ids[i] != ids[i + 1]:
                add_edge(ids[i], ids[i + 1], hw)

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

    src_nid, _ = insert_target(39.902950, 119.517905)
    labels = [{"idx": 0, "id": "★水源", "name": "市政给水接入点（南主门假设）",
               "cat": "source", "lat": 39.902950, "lon": 119.517905, "nid": src_nid}]
    nids = [src_nid]
    for b in bundle["buildings"]:
        if b["cat"] not in TARGET_CATS:
            continue
        nid, d = insert_target(b["lat"], b["lon"])
        labels.append({"idx": len(labels), "id": b["id"], "name": b["name"],
                       "cat": b["cat"], "lat": b["lat"], "lon": b["lon"], "nid": nid})
        nids.append(nid)
    N = len(nids)

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

    D = []
    for a in nids:
        dd = dijkstra(a)
        D.append([dd.get(b, float("inf")) for b in nids])

    # Kruskal
    pairs = [(D[i][j], i, j) for i in range(N) for j in range(i + 1, N)]
    pairs.sort()
    par = list(range(N))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    kru, kru_edges = 0.0, []
    for w, a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            par[ra] = rb
            kru += w
            kru_edges.append((a, b, w))

    # Prim
    used = {0}
    best = {j: D[0][j] for j in range(N)}
    best_from = {j: 0 for j in range(N)}
    prim, prim_edges = 0.0, []
    while len(used) < N:
        j = min((k for k in range(N) if k not in used), key=lambda k: best.get(k, float("inf")))
        prim += best[j]
        prim_edges.append((best_from[j], j, best[j]))
        used.add(j)
        for k in range(N):
            if k not in used and D[j][k] < best.get(k, float("inf")):
                best[k] = D[j][k]
                best_from[k] = j

    # text
    out = []
    out.append("# 燕山大学西校区给水管道规划 · 无向图距离矩阵")
    out.append("# 生成：2026-11-05  数据：04_数据/derived/pipeline_bundle_conn.json")
    out.append("# 权重：沿路网最短距离，按道路等级加权（单位 m）；-1 表示不可达")
    out.append("# N=%d" % N)
    out.append("#NODES")
    for L in labels:
        out.append("%d|%s|%s|%s|%.6f|%.6f" % (L["idx"], L["id"], L["name"], L["cat"], L["lat"], L["lon"]))
    out.append("#MATRIX")
    for i in range(N):
        out.append(" ".join(("%.2f" % D[i][j]) if D[i][j] < 1e17 else "-1" for j in range(N)))
    text = "\n".join(out) + "\n"
    p_txt = os.path.join(BASE, "04_数据", "derived", "graph_matrix.txt")
    open(p_txt, "w", encoding="utf-8").write(text)

    # process text
    pt = []
    pt.append("燕山大学西校区给水管道规划 · MST 生成过程")
    pt.append("节点数 %d（0=水源，1..45=供水目标）；权重=沿路网加权距离 m" % N)
    pt.append("")
    pt.append("== Kruskal（按边权升序，并查集）总长 %.3f m，%d 条边 ==" % (kru, len(kru_edges)))
    acc = 0.0
    for k, (a, b, w) in enumerate(kru_edges, 1):
        acc += w
        pt.append("  %2d. %2d(%s) -- %2d(%s)  %7.1f m  累计 %9.1f m" %
                  (k, a, labels[a]["id"], b, labels[b]["id"], w, acc))
    pt.append("")
    pt.append("== Prim（从水源出发，每次选最近节点）总长 %.3f m，%d 条边 ==" % (prim, len(prim_edges)))
    acc = 0.0
    for k, (a, b, w) in enumerate(prim_edges, 1):
        acc += w
        pt.append("  %2d. %2d(%s) -> %2d(%s)  %7.1f m  累计 %9.1f m" %
                  (k, a, labels[a]["id"], b, labels[b]["id"], w, acc))
    pt.append("")
    pt.append("两者差 |Kruskal-Prim| = %.6f m" % abs(kru - prim))
    p_proc = os.path.join(BASE, "04_数据", "derived", "graph_mst_process.txt")
    open(p_proc, "w", encoding="utf-8").write("\n".join(pt) + "\n")

    # js wrapper for file:// reading
    p_js = os.path.join(BASE, "05_图件", "管道方案", "graph_matrix.js")
    open(p_js, "w", encoding="utf-8").write(
        "// 由 06_代码/build_matrix.py 从 04_数据/derived/graph_matrix.txt 生成\n"
        "window.GRAPH_MATRIX_TEXT = " + json.dumps(text, ensure_ascii=False) + ";\n")
    print("matrix %d x %d, Kruskal %.3f m, Prim %.3f m" % (N, N, kru, prim))
    print("->", p_txt)
    print("->", p_proc)
    print("->", p_js)


if __name__ == "__main__":
    main()
