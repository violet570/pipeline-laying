"""Stitch the amap plaza z18 tiles and draw the registry buildings on top,
so we can see with our own eyes whether AMap draws internal roads there.
usage: python scripts/fig_plaza_amap.py
"""
import glob
import math
import os

from PIL import Image, ImageDraw, ImageFont

import groups as G

Z = 18
TILE = 256
DIR = 'data/tiles/amap_plaza_z18'
X0, Y0 = 218102, 99318          # top-left tile
NX, NY = 4, 4
OUT = 'docs/fig/plaza_amap_roads.jpg'

FONT = 'C:/Windows/Fonts/msyh.ttc'
FONTB = 'C:/Windows/Fonts/msyhbd.ttc'


def merc_px(lon, lat, z=Z):
    n = 2.0 ** z * TILE
    x = (lon + 180.0) / 360.0 * n
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x, y


def wgs2gcj(lon, lat):
    a = 6378245.0
    ee = 0.00669342162296594323

    def tlat(x, y):
        r = (-100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y
             + 0.2 * math.sqrt(abs(x)))
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

    dlat = tlat(lon - 105.0, lat - 35.0)
    dlon = tlon(lon - 105.0, lat - 35.0)
    rad = math.radians(lat)
    m = 1 - ee * math.sin(rad) ** 2
    sq = math.sqrt(m)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (m * sq) * math.pi)
    dlon = (dlon * 180.0) / (a / sq * math.cos(rad) * math.pi)
    return lon + dlon, lat + dlat


def stitch(kind):
    img = Image.new('RGB', (NX * TILE, NY * TILE), (10, 12, 16))
    for x in range(X0, X0 + NX):
        for y in range(Y0, Y0 + NY):
            p = os.path.join(DIR, f'{kind}_{x}_{y}.png')
            if not os.path.exists(p):
                continue
            t = Image.open(p).convert('RGB')
            img.paste(t, ((x - X0) * TILE, (y - Y0) * TILE))
    return img


def sx(lon, lat):
    glon, glat = wgs2gcj(lon, lat)
    px, py = merc_px(glon, glat)
    return px - X0 * TILE, py - Y0 * TILE


def main():
    road = stitch('webrd')
    sat = stitch('webst')
    # side-by-side: satellite | road-map
    W, H = road.size
    gap = 16
    canvas = Image.new('RGB', (W, H * 2 + gap + 96), (8, 10, 14))
    canvas.paste(sat, (0, 56))
    canvas.paste(road, (0, H + 56 + gap))

    d = ImageDraw.Draw(canvas, 'RGBA')
    fb = ImageFont.truetype(FONTB, 30)
    fs = ImageFont.truetype(FONT, 19)
    d.text((14, 10), '高德 z18 底图 · 圆形广场一带（上=卫星 下=路网注记）', font=fb, fill=(255, 255, 255))

    # draw the three colleges + the two pending buildings
    keys = ['X01', 'X02', 'X03', 'X04', 'X05']
    byk = {g['key']: g for g in G.GROUPS}
    for i, k in enumerate(keys):
        g = byk.get(k)
        if not g:
            continue
        m = g.get('measured')
        if not m:
            continue
        x0, y0, x1, y1 = m['bbox']
        ax, ay = sx(x0, y1)
        bx, by = sx(x1, y0)
        xs, xe = sorted((ax, bx))
        ys, ye = sorted((ay, by))
        for off in (56, H + 56 + gap):
            d.rectangle([xs, ys + off, xe, ye + off], outline=(0, 255, 180, 235), width=3)
            lab = g['short']
            fw = d.textlength(lab, font=fs)
            d.rectangle([xs, ys + off - 22, xs + fw + 8, ys + off], fill=(0, 40, 30, 210))
            d.text((xs + 4, ys + off - 21), lab, font=fs, fill=(180, 255, 230))

    canvas.save(OUT, quality=88)
    print('saved', OUT, canvas.size)


if __name__ == '__main__':
    main()
