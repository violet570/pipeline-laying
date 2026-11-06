# -*- coding: utf-8 -*-
"""把引擎与主数据内联进模板，生成两个单文件页面：
    05_图件/管道方案/planner.html   ← planner_template.html + pipe_engine.js + pipeline_bundle_conn.json
    05_图件/管道方案/matrix_mst.html ← matrix_template.html + 同一引擎 + 同一主数据

内联的好处：两个页面都能双击直接打开（file://），也都能走 python -m http.server，
且引擎只有一份源码（06_代码/pipe_engine.js），改算法不会两个页面各改一遍。

用法：python 06_代码/build_planner.py
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "06_代码")
OUTDIR = os.path.join(BASE, "05_图件", "管道方案")
BUNDLE = os.path.join(BASE, "04_数据", "derived", "pipeline_bundle_conn.json")

JOBS = [
    ("planner_template.html", "planner.html", None),
    ("matrix_template.html", "matrix_mst.html", "matrix_mst_static.html"),
]


def main():
    engine = open(os.path.join(SRC, "pipe_engine.js"), encoding="utf-8").read()
    bundle = json.load(open(BUNDLE, encoding="utf-8"))
    data = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))

    os.makedirs(OUTDIR, exist_ok=True)
    for tpl_name, out_name, _alt in JOBS:
        tpl = open(os.path.join(SRC, tpl_name), encoding="utf-8").read()
        html = (tpl.replace("__ENGINE_JS__", engine)
                   .replace("__BUNDLE_JSON__", data))
        out = os.path.join(OUTDIR, out_name)
        open(out, "w", encoding="utf-8").write(html)
        print("wrote %s  %.1f KB" % (out, len(html.encode("utf-8")) / 1024))


if __name__ == "__main__":
    main()
