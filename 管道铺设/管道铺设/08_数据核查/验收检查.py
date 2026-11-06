# -*- coding: utf-8 -*-
"""主数据验收检查：对 04_数据/derived 下的最终产物做硬性断言。

运行：python 08_数据核查/验收检查.py
输出：每条 PASS/FAIL；有 FAIL 时进程退出码为 1。
"""
import csv
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
D = os.path.join(ROOT, "04_数据")
DER = os.path.join(D, "derived")

B = json.load(open(os.path.join(DER, "pipeline_bundle_conn.json"), encoding="utf-8"))
M, S = B["meta"], B["stats"]
K_LAT, K_LON = M["m_per_deg_lat"], M["m_per_deg_lon"]
LAT0, LON0 = M["origin"]
DN_LIST = [32, 40, 50, 65, 80, 100, 125, 150, 200, 250, 300, 350, 400, 500]
DN_COST = {32: 140, 40: 160, 50: 185, 65: 225, 80: 270, 100: 330, 125: 400,
           150: 480, 200: 620, 250: 800, 300: 1000, 350: 1200, 400: 1450, 500: 1900}

fails = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  " + detail) if detail else ""))
    if not ok:
        fails.append(name)


def dxy(lon, lat):
    return (lon - LON0) * K_LON, (lat - LAT0) * K_LAT


def pdist(p, q):
    return math.hypot((p[0] - q[0]) * K_LON, (p[1] - q[1]) * K_LAT)


print("== 1. 规模 ==")
check("buildings == 61", len(B["buildings"]) == 61, str(len(B["buildings"])))
check("targets == 45", sum(1 for b in B["buildings"] if b["cat"] not in ("utility", "other")) == 45)
check("parts == 78", sum(len(b.get("parts") or [b["footprint"]]) for b in B["buildings"]) == 78)
check("pipes == 220", len(B["pipes"]) == 220, str(len(B["pipes"])))
check("tree_edges == 45", len(B["tree_edges"]) == 45, str(len(B["tree_edges"])))
check("roads == 153", len(B["roads"]) == 153, str(len(B["roads"])))
check("areas == 38", len(B["areas"]) == 38, str(len(B["areas"])))
check("service_connections == 61", len(B["service_connections"]) == 61,
      str(len(B["service_connections"])))

print("== 2. 勾稽 ==")
check("Σpipes.length == stats.pipe_length_m",
      abs(sum(p["length"] for p in B["pipes"]) - S["pipe_length_m"]) < 0.5)
check("Σtree_edges.w == stats.mst_length_m",
      abs(sum(e["w"] for e in B["tree_edges"]) - S["mst_length_m"]) < 0.5)
cost = sum(p["length"] * DN_COST[p["dn"]] for p in B["pipes"])
check("造价复算 == stats.cost_est_yuan", abs(cost - S["cost_est_yuan"]) < 2, "%.0f" % cost)
dem_all = sum(b["demand"] for b in B["buildings"])
check("Σbuildings.demand == stats.total_demand_lpd", abs(dem_all - S["total_demand_lpd"]) < 2)
check("Σfloor_area == stats.total_floor_m2", abs(sum(b["floor_area"] for b in B["buildings"]) - S["total_floor_m2"]) < 2)

print("== 3. 流量与管径 ==")
fmax = max(p["flow"] for p in B["pipes"])
check("最大管段流量 <= 总需水量", fmax <= S["total_demand_lpd"] + 0.5, "%.1f" % fmax)
check("最大管段流量 == 总需水量（主干）", abs(fmax - S["total_demand_lpd"]) < 1.0)
check("q_ls 与 flow 一致（相对误差 <1e-3）",
      max(abs(p["q_ls"] - p["flow"] * 2.5 / 86400) / max(p["q_ls"], 1e-9) for p in B["pipes"]) < 1e-3)
check("所有 DN 在标准档位里", all(p["dn"] in DN_LIST for p in B["pipes"]))

print("== 4. 坐标与几何 ==")
lons = [p[0] for b in B["buildings"] for p in b["footprint"]]
lats = [p[1] for b in B["buildings"] for p in b["footprint"]]
check("所有建筑顶点在东经 119.49~119.55", min(lons) > 119.49 and max(lons) < 119.55)
check("所有建筑顶点在北纬 39.89~39.93", min(lats) > 39.89 and max(lats) < 39.93)
check("footprint 均为 >=3 点闭合多边形", all(len(b["footprint"]) >= 3 for b in B["buildings"]))
check("parts 每个 >=3 点", all(len(pt) >= 3 for b in B["buildings"] for pt in (b.get("parts") or [b["footprint"]])))
check("所有 demand >= 0", all(b["demand"] >= 0 for b in B["buildings"]))
check("61 栋都有面积加权质心", all("centroid" in b for b in B["buildings"]))

print("== 5. 环道 ==")
plaza = json.load(open(os.path.join(DER, "plaza_roads_user.json"), encoding="utf-8"))
ring = plaza["segments"]["plaza_ring"]
check("环道首尾闭合", ring[0] == ring[-1])
check("环道顶点 73（72+闭合点）", len(ring) == 73, str(len(ring)))
L = sum(pdist(ring[i], ring[i + 1]) for i in range(len(ring) - 1))
check("环道长度 750~790 m", 750 < L < 790, "%.1f" % L)


def seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    if L2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / L2))
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


def dist_to_osm_road(lon, lat):
    x, y = dxy(lon, lat)
    best = 1e18
    for r in B["roads"]:
        if r.get("name", "").startswith("plaza"):
            continue
        pts = r["pts"]
        for i in range(len(pts) - 1):
            a = dxy(*pts[i])
            c = dxy(*pts[i + 1])
            best = min(best, seg_dist(x, y, a[0], a[1], c[0], c[1]))
    return best


for nm, pts in plaza["segments"].items():
    if nm == "plaza_ring":
        continue
    d = dist_to_osm_road(*pts[-1])
    check("%s 外端在 OSM 主网上（<2 m）" % nm, d < 2.0, "%.2f m" % d)

print("== 6. 接户 ==")
lat_bad = [c["id"] for c in B["service_connections"]
           if abs(c["lateral_m"] - math.hypot(c["road_tap"][0] - c["edge_point"][0],
                                              c["road_tap"][1] - c["edge_point"][1])) > 0.3]
check("lateral_m == 距离(road_tap, edge_point)", not lat_bad, str(lat_bad[:5]))
check("接户支管 2~110 m", all(2.0 <= c["lateral_m"] <= 110.0 for c in B["service_connections"]))
ids = {b["id"] for b in B["buildings"]}
check("接户 id 都在 buildings 里", all(c["id"] in ids for c in B["service_connections"]))

print("== 7. 距离表 ==")
lines = open(os.path.join(DER, "distances.csv"), encoding="utf-8-sig").read().splitlines()[1:]
keys = set()
for ln in lines:
    parts = ln.split(",")
    keys.update([parts[0], parts[2]])
check("distances.csv 1,830 对", len(lines) == 1830, str(len(lines)))
check("distances.csv 61 个键且都在 bundle", len(keys) == 61 and keys <= ids)

print("== 8. 图 / 衍生文件 ==")
for f in ("pipes_v2.geojson", "targets_v2.csv", "build_report_v2.txt",
          "amap_around_燕山大学.json", "amap_crosscheck_燕山大学.txt",
          "id_validation_registry.json"):
    check("存在 " + f, os.path.exists(os.path.join(DER, f)))

print("== 9. 交互式规划台 ==")
planner = os.path.join(ROOT, "05_图件", "管道方案", "planner.html")
check("planner.html 存在", os.path.exists(planner))
if os.path.exists(planner):
    html = open(planner, encoding="utf-8").read()
    check("planner.html 含三模式与 Dijkstra",
          all(k in html for k in ("模式 A", "模式 B", "模式 C", "Dijkstra")))
    check("planner.html 内联了主要数据", "service_connections" in html and "tree_edges" in html)
    check("planner.html 体积 >100 KB", os.path.getsize(planner) > 100000,
          str(os.path.getsize(planner)))

print("== 10. 算法/数据校验产物 ==")
prim = os.path.join(ROOT, "08_数据核查", "prim_check.txt")
_prim_ok = False
if os.path.exists(prim):
    _raw = open(prim, "rb").read()
    _txt = _raw.decode("utf-16") if _raw[:2] == b"\xff\xfe" else _raw.decode("utf-8", "replace")
    _prim_ok = "PASS" in _txt
check("prim_check.txt 存在且 PASS", _prim_ok)
iv = json.load(open(os.path.join(DER, "id_validation_registry.json"), encoding="utf-8"))
check("注册表 67 个 way id 全部 ok", iv["n_registry_ways"] == 67 and iv["n_bad"] == 0,
      "%s/%s" % (iv["n_ok"], iv["n_registry_ways"]))
check("run_build.py / check_prim.py / validate_registry_ids.py 存在",
      all(os.path.exists(os.path.join(ROOT, "06_代码", f))
          for f in ("run_build.py", "check_prim.py", "validate_registry_ids.py")))

print("== 11. 作业功能：矩阵 + Prim/Kruskal ==")
gm = os.path.join(DER, "graph_matrix.txt")
check("graph_matrix.txt 存在", os.path.exists(gm))
if os.path.exists(gm):
    _lines = open(gm, encoding="utf-8").read().splitlines()
    check("矩阵声明 N=46", any(l.strip().endswith("N=46") for l in _lines))
    _mat = [l for l in _lines if l.strip() and not l.lstrip().startswith("#") and "|" not in l]
    check("矩阵 46 行", len(_mat) == 46, str(len(_mat)))
    check("每行 46 个数", all(len(l.split()) == 46 for l in _mat))
proc = os.path.join(DER, "graph_mst_process.txt")
check("graph_mst_process.txt 存在", os.path.exists(proc))
if os.path.exists(proc):
    _t = open(proc, encoding="utf-8").read()
    check("过程文本含 Kruskal / Prim 且两者差 0",
          "Kruskal" in _t and "Prim" in _t and "0.000000" in _t)
mm = os.path.join(ROOT, "05_图件", "管道方案", "matrix_mst.html")
check("matrix_mst.html 存在且含 Prim/Kruskal",
      os.path.exists(mm) and all(k in open(mm, encoding="utf-8").read() for k in ("Kruskal", "Prim")))
check("graph_matrix.js 存在", os.path.exists(os.path.join(ROOT, "05_图件", "管道方案", "graph_matrix.js")))

print()
if fails:
    print("FAILED %d 项：" % len(fails))
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("全部通过")
