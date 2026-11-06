# -*- coding: utf-8 -*-
"""为 11 个影像量测条目抓高德 z18 卫星瓦片，出「10 m 网格」量测复核底图。

输出：
  data/tiles/amap_sat_z18/z18_x_y.jpg        瓦片缓存（GCJ-02）
  data/tiles/crops/<key>_z18_grid.jpg        每栋一张、带 10 m 网格与米制刻度

用法：python scripts/fetch_z18_measured.py
"""
import math
import os
import sys
import time
import urllib.request

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import groups as G  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILE_DIR = os.path.join(BASE, "04_数据", "tiles", "amap_sat_z18")
CROP_DIR = os.path.join(BASE, "04_数据", "tiles", "crops")
Z, TILE = 18, 256
N = 2.0 ** Z * TILE
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
URL = "https://webst01.is.autonavi.com/appmaptile?style=6&x=%d&y=%d&z=%d"


def wgs2gcj(lon, lat):
    a, ee = 6378245.0, 0.00669342162296594323
    def tlat(x, y):
        r = (-100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x)))
        r += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        r += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
        r += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
        return r
    def tlon(x, y):
        r = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
        r += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        r += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
        r += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
        return r
    dlat, dlon = tlat(lon - 105.0, lat - 35.0), tlon(lon - 105.0, lat - 35.0)
    rad = math.radians(lat)
    m = 1 - ee * math.sin(rad) ** 2
    sq = math.sqrt(m)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (m * sq) * math.pi)
    dlon = (dlon * 180.0) / (a / sq * math.cos(rad) * math.pi)
    return lon + dlon, lat + dlat


def ll2px(lon, lat):
    gl, ga = wgs2gcj(lon, lat)
    mx = (gl + 180.0) / 360.0 * N
    s = math.sin(math.radians(ga))
    my = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * N
    return mx, my


def fetch_tile(x, y):
    os.makedirs(TILE_DIR, exist_ok=True)
    p = os.path.join(TILE_DIR, "z%d_%d_%d.jpg" % (Z, x, y))
    if os.path.exists(p) and os.path.getsize(p) > 500:
        return p
    req = urllib.request.Request(URL % (x, y, Z), headers={"User-Agent": UA, "Referer": "https://ditu.amap.com/"})
    for k in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                data = r.read()
            if len(data) > 500:
                open(p, "wb").write(data)
                return p
        except Exception:  # noqa: BLE001
            time.sleep(0.6 * (k + 1))
    return None


def build(g):
    m = g["measured"]
    lon0, lat0 = m["lon"], m["lat"]
    half_m = 90
    x0, y0 = ll2px(lon0, lat0)
    mpp = 156543.03392 * math.cos(math.radians(lat0)) / (2.0 ** Z)
    xa, ya = int((x0 - half_m / mpp) // TILE), int((y0 - half_m / mpp) // TILE)
    xb, yb = int((x0 + half_m / mpp) // TILE), int((y0 + half_m / mpp) // TILE)
    img = Image.new("RGB", ((xb - xa + 1) * TILE, (yb - ya + 1) * TILE), (10, 12, 16))
    ok = 0
    for tx in range(xa, xb + 1):
        for ty in range(ya, yb + 1):
            p = fetch_tile(tx, ty)
            if p:
                img.paste(Image.open(p).convert("RGB"), ((tx - xa) * TILE, (ty - ya) * TILE))
                ok += 1
    d = ImageDraw.Draw(img, "RGBA")
    try:
        f = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
        fb = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 18)
    except Exception:  # noqa: BLE001
        f = fb = ImageFont.load_default()

    def tp(lon, lat):
        xx, yy = ll2px(lon, lat)
        return (xx - xa * TILE, yy - ya * TILE)

    # 10 m grid in local metres around the building centre
    klat = 111320.0
    klon = 111320.0 * math.cos(math.radians(lat0))
    for gx in range(-half_m, half_m + 1, 10):
        lon = lon0 + gx / klon
        p1 = tp(lon, lat0 - half_m / klat)
        p2 = tp(lon, lat0 + half_m / klat)
        d.line([p1, p2], fill=(255, 255, 255, 45), width=1)
        if gx % 50 == 0:
            d.text((p1[0] + 2, 6), str(gx), font=f, fill=(255, 255, 0, 220))
    for gy in range(-half_m, half_m + 1, 10):
        lat = lat0 + gy / klat
        p1 = tp(lon0 - half_m / klon, lat)
        p2 = tp(lon0 + half_m / klon, lat)
        d.line([p1, p2], fill=(255, 255, 255, 45), width=1)
        if gy % 50 == 0:
            d.text((3, p1[1] + 2), str(gy), font=f, fill=(255, 255, 0, 220))
    # bbox
    x0b, y1b = m["bbox"][0], m["bbox"][3]
    x1b, y0b = m["bbox"][2], m["bbox"][1]
    q = [tp(x0b, y1b), tp(x1b, y1b), tp(x1b, y0b), tp(x0b, y0b)]
    d.line(q + [q[0]], fill=(0, 255, 200, 230), width=2)
    d.rectangle([0, 0, img.width, 30], fill=(8, 10, 14, 220))
    d.text((6, 4), "%s %s  z18 卫星 · 10 m 网格 · 青框=现行 bbox" % (g["key"], g["short"]),
           font=fb, fill=(255, 255, 255))
    os.makedirs(CROP_DIR, exist_ok=True)
    out = os.path.join(CROP_DIR, "%s_z18_grid.jpg" % g["key"])
    img.save(out, quality=90)
    print("%-4s %-12s tiles %d/%d -> %s" % (g["key"], g["short"], ok,
                                            (xb - xa + 1) * (yb - ya + 1), out))


def main():
    for g in G.GROUPS:
        if g.get("measured"):
            build(g)


if __name__ == "__main__":
    main()
