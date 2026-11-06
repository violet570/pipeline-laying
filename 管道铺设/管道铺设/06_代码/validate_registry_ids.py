# -*- coding: utf-8 -*-
"""离线校验注册表里实际使用的 67 个 OSM way id。

Overpass 在本机不可达（2026-11-01 实测 403/超时），这里退化为对随包 OSM 快照
（04_数据/raw/buildings.json）逐 id 回查：id 是否存在、是否有 building 标签、
几何质心是否落在西校区框内、是否被多个组团重复引用。

输出：04_数据/derived/id_validation_registry.json
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "06_代码"))
import groups as G  # noqa: E402

RAW = os.path.join(BASE, "04_数据", "raw", "buildings.json")
OUT = os.path.join(BASE, "04_数据", "derived", "id_validation_registry.json")
BOX = {"s": 39.890, "w": 119.490, "n": 39.930, "e": 119.550}


def main():
    els = json.load(open(RAW, encoding="utf-8"))["elements"]
    ways = {}
    for e in els:
        if e.get("type") == "way":
            ways.setdefault(e["id"], e)
    used = {}
    for g in G.GROUPS:
        for w in g.get("ways", []):
            used.setdefault(w, []).append(g["key"])
    rows = []
    for w, keys in sorted(used.items()):
        el = ways.get(w)
        if not el:
            rows.append({"id": w, "status": "missing", "groups": keys})
            continue
        tags = el.get("tags") or {}
        geom = [p for p in (el.get("geometry") or []) if p]
        if not geom:
            rows.append({"id": w, "status": "no-geometry", "groups": keys})
            continue
        lat = sum(p["lat"] for p in geom) / len(geom)
        lon = sum(p["lon"] for p in geom) / len(geom)
        inside = BOX["s"] <= lat <= BOX["n"] and BOX["w"] <= lon <= BOX["e"]
        rows.append({
            "id": w,
            "status": "ok" if (inside and tags.get("building")) else ("out-of-box" if not inside else "no-building-tag"),
            "groups": keys,
            "lat": round(lat, 6), "lon": round(lon, 6),
            "building": tags.get("building"),
            "name": tags.get("name"),
            "levels": tags.get("building:levels"),
        })
    bad = [r for r in rows if r["status"] != "ok"]
    dup = {w: ks for w, ks in used.items() if len(ks) > 1}
    out = {
        "checked_at": "2026-11-01",
        "method": "offline: 04_数据/raw/buildings.json snapshot (Overpass unavailable)",
        "box": BOX,
        "n_registry_ways": len(used),
        "n_ok": len(rows) - len(bad),
        "n_bad": len(bad),
        "duplicate_refs": dup,
        "bad": bad,
        "rows": rows,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("registry ways", len(used), "ok", out["n_ok"], "bad", len(bad), "dups", dup)
    for r in bad:
        print("  BAD", r)


if __name__ == "__main__":
    main()
