# -*- coding: utf-8 -*-
"""一键重建：在临时目录用 junction 把 04_数据 / 06_代码 映射成脚本期望的 data / scripts，
顺序执行 build_bundle → add_service_points → viz_25d → build_planner，并把图件拷回交付目录。

用法：python 06_代码/run_build.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import uuid

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def junction(link, target):
    os.makedirs(os.path.dirname(link), exist_ok=True)
    r = subprocess.run(["cmd", "/c", "mklink", "/J", link, target],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("mklink failed: " + r.stdout + r.stderr)


def unlink(link):
    subprocess.run(["cmd", "/c", "rmdir", link], capture_output=True, text=True)


def main():
    tmp = os.path.join(tempfile.gettempdir(), "ysu_build_" + uuid.uuid4().hex[:6])
    os.makedirs(os.path.join(tmp, "docs", "fig"))
    junction(os.path.join(tmp, "data"), os.path.join(BASE, "04_数据"))
    junction(os.path.join(tmp, "scripts"), os.path.join(BASE, "06_代码"))
    try:
        for script in ("build_bundle_v2.py", "add_service_points.py", "viz_25d.py"):
            print("== running", script)
            r = subprocess.run([PY, script], cwd=os.path.join(tmp, "scripts"),
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            print(r.stdout.strip()[-1500:])
            if r.returncode != 0:
                print(r.stderr)
                raise SystemExit("failed: " + script)
        src = os.path.join(tmp, "docs", "fig", "viz_25d.html")
        dst = os.path.join(BASE, "05_图件", "管道方案", "viz_25d.html")
        shutil.copyfile(src, dst)
        print("->", dst)
        # screenshot (optional)
        png = os.path.join(BASE, "05_图件", "管道方案", "viz_25d.png")
        if os.path.exists(EDGE):
            uri = "file:///" + dst.replace("\\", "/")
            subprocess.run([EDGE, "--headless", "--disable-gpu", "--no-first-run",
                            "--user-data-dir=" + os.path.join(tmp, "edge"),
                            "--hide-scrollbars", "--window-size=1755,1705",
                            "--virtual-time-budget=8000", "--screenshot=" + png, uri],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("->", png)
        print("== build_matrix")
        r = subprocess.run([PY, os.path.join(BASE, "06_代码", "build_matrix.py")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(r.stdout.strip())
        if r.returncode != 0:
            print(r.stderr)
            raise SystemExit("build_matrix failed")
        print("== build_planner")
        r = subprocess.run([PY, os.path.join(BASE, "06_代码", "build_planner.py")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(r.stdout.strip())
        if r.returncode != 0:
            print(r.stderr)
            raise SystemExit("build_planner failed")
    finally:
        for j in ("data", "scripts"):
            p = os.path.join(tmp, j)
            if os.path.exists(p):
                unlink(p)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
