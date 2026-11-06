# -*- coding: utf-8 -*-
"""Stitch an AMap tile job into one image.

usage: python scripts/stitch_amap.py <job> <out.jpg> [scale]
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(job, out, scale=2):
    d = os.path.join(ROOT, 'data', 'tiles', job)
    tiles = {}
    for fn in os.listdir(d):
        p = fn.rsplit('.', 1)[0].split('_')
        if len(p) == 3:
            tiles[(int(p[1]), int(p[2]))] = os.path.join(d, fn)
    xs = [k[0] for k in tiles]
    ys = [k[1] for k in tiles]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    W = (x1 - x0 + 1) * 256
    H = (y1 - y0 + 1) * 256
    img = Image.new('RGB', (W, H), (240, 240, 240))
    for (x, y), fp in tiles.items():
        img.paste(Image.open(fp).convert('RGB'), ((x - x0) * 256, (y - y0) * 256))
    if scale != 1:
        img = img.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    dst = os.path.join(ROOT, 'docs', 'fig', out)
    img.save(dst, quality=92)
    print('saved', dst, img.size, 'x', x0, x1, 'y', y0, y1)


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], a[1], float(a[2]) if len(a) > 2 else 2)
