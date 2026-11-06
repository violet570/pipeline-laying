# -*- coding: utf-8 -*-
"""Crop a window out of the stitched AMap label image by WGS-84 bbox.

usage: python scripts/crop_amap.py <out.jpg> <minLonWGS> <minLatWGS> <maxLonWGS> <maxLatWGS> [scale]
The stitched job must be amap_west_z18 (x0..x1,y0..y1 printed by stitch_amap.py).
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fig_campus_all import wgs2gcj  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Z = 18
X0, Y0 = 218097, 99317
W, H = 5120, 4608


def merc(lon, lat):
    import math
    n = 2.0 ** Z * 256.0
    x = (lon + 180.0) / 360.0 * n
    r = math.radians(lat)
    y = (1.0 - math.log(math.tan(r) + 1.0 / math.cos(r)) / math.pi) / 2.0 * n
    return x, y


def main(out, minLon, minLat, maxLon, maxLat, scale=2):
    src = os.path.join(ROOT, 'docs', 'fig', 'amap_west.png')
    img = Image.open(src).convert('RGB')
    lo0, la0 = wgs2gcj(minLon, minLat)
    lo1, la1 = wgs2gcj(maxLon, maxLat)
    x0, y1 = merc(lo0, la0)
    x1, y0 = merc(lo1, la1)
    px0 = int(x0) - X0 * 256
    px1 = int(x1) - X0 * 256
    py0 = int(y0) - Y0 * 256
    py1 = int(y1) - Y0 * 256
    px0, px1 = max(0, min(W, px0)), max(0, min(W, px1))
    py0, py1 = max(0, min(H, py0)), max(0, min(H, py1))
    if px1 - px0 < 8 or py1 - py0 < 8:
        print('EMPTY', (px0, py0, px1, py1))
        return
    c = img.crop((px0, py0, px1, py1))
    if scale != 1:
        c = c.resize((int(c.width * scale), int(c.height * scale)), Image.LANCZOS)
    dst = os.path.join(ROOT, 'docs', 'fig', out)
    c.save(dst, quality=92)
    print('saved', dst, c.size, 'crop', (px0, py0, px1, py1))


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], float(a[1]), float(a[2]), float(a[3]), float(a[4]),
         float(a[5]) if len(a) > 5 else 2)
