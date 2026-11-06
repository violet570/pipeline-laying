# -*- coding: utf-8 -*-
"""Overlay the building footprints on the plaza so the ring fit can be judged.

Draws the plaza at 2x with a 25 m grid, the r=145 m circle, and every building
footprint that comes within 240 m of the plaza centre -- labelled. This makes it
obvious which buildings actually conflict with a 145 m ring.

usage: python scripts/fig_ring_overlay.py
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from fig_campus_all import wgs2gcj, merc_px  # noqa: E402

Z = 18
TILES = 'data/tiles/campus_sat_z18_full'
C_LAT, C_LON = 39.916330, 119.515700
LAT0, LON0 = 39.9111, 119.5172
K_LAT = 111320.0
K_LON = 111320.0 * math.cos(math.radians(LAT0))


def stitch():
    xs, ys = [], []
    for fn in os.listdir(TILES):
        if fn.endswith('.jpg'):
            z, x, y = fn[:-4].split('_')
            if int(z) == Z:
                xs.append(int(x))
                ys.append(int(y))
    x0, y0 = min(xs), min(ys)
    im = Image.new('RGB', ((max(xs) - x0 + 1) * 256, (max(ys) - y0 + 1) * 256))
    for fn in os.listdir(TILES):
        if not fn.endswith('.jpg'):
            continue
        z, x, y = fn[:-4].split('_')
        if int(z) == Z:
            im.paste(Image.open(os.path.join(TILES, fn)),
                     ((int(x) - x0) * 256, (int(y) - y0) * 256))
    return im, x0, y0


def main():
    im, x0, y0 = stitch()
    g = wgs2gcj(C_LON, C_LAT)
    X, Y = merc_px(g[0], g[1], Z)
    cpx, cpy = X - x0 * 256, Y - y0 * 256

    HW = HH = 520
    SC = 2
    box = (int(cpx - HW), int(cpy - HH), int(cpx + HW), int(cpy + HH))
    crop = im.crop(box).resize(((2 * HW) * SC, (2 * HH) * SC), Image.LANCZOS)
    top = 80
    panel = Image.new('RGB', (crop.width, crop.height + top), (6, 9, 14))
    panel.paste(crop, (0, top))
    dr = ImageDraw.Draw(panel, 'RGBA')

    res = 156543.03392804097 * math.cos(math.radians(C_LAT)) / (2 ** Z)
    scale = SC / res          # px per metre
    cx, cy = crop.width / 2.0, crop.height / 2.0 + top

    def P(lon, lat):
        glon, glat = wgs2gcj(lon, lat)
        gx, gy = merc_px(glon, glat, Z)
        # stitched pixel -> crop pixel -> upscaled panel pixel
        return ((gx - x0 * 256 - box[0]) * SC,
                (gy - y0 * 256 - box[1]) * SC + top)

    # grid
    f = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 14)
    for k in range(-19, 20):
        off = k * 25.0 * scale
        col = (0, 190, 255, 45) if k % 2 else (0, 210, 255, 80)
        dr.line([(cx + off, top), (cx + off, panel.height)], fill=col, width=1)
        dr.line([(0, cy + off), (panel.width, cy + off)], fill=col, width=1)
        if k % 4 == 0 and k:
            dr.text((cx + off + 2, top + 4), str(abs(k) * 25), font=f, fill=(0, 230, 255))
            dr.text((3, cy + off + 1), str(abs(k) * 25), font=f, fill=(0, 230, 255))

    # candidate rings
    for r, col, w in ((92, (255, 210, 90, 190), 2),
                      (145, (255, 60, 200, 235), 3),
                      (160, (120, 255, 140, 170), 2)):
        rr = r * scale
        dr.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=col, width=w)

    # buildings
    b = json.load(open('data/derived/pipeline_bundle_conn.json', encoding='utf-8'))
    fnt = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 22)
    for bb in b['buildings']:
        fp = bb['footprint']
        if len(fp) < 3:
            continue
        cx0 = (bb['lon'] - C_LON) * K_LON
        cy0 = (bb['lat'] - C_LAT) * K_LAT
        if math.hypot(cx0, cy0) > 260:
            continue
        q = [P(p[0], p[1]) for p in fp]
        dr.polygon(q, outline=(0, 245, 235, 240), width=2)
        mx = sum(p[0] for p in q) / len(q)
        my = sum(p[1] for p in q) / len(q)
        lab = bb['short']
        tw = dr.textlength(lab, font=fnt)
        dr.rectangle([mx - tw / 2 - 4, my - 15, mx + tw / 2 + 4, my + 12],
                     fill=(0, 20, 26, 200))
        dr.text((mx - tw / 2, my - 13), lab, font=fnt, fill=(255, 255, 255))

    t = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 26)
    s = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 18)
    dr.text((12, 10), '建筑轮廓 vs 候选环半径：看哪一圈既能包住三栋学院又不穿楼', font=t,
            fill=(255, 255, 255))
    dr.text((12, 48), '黄 r=92 m ／ 洋红 r=145 m ／ 绿 r=160 m  ；青框=建筑轮廓（OSM/影像量测）',
            font=s, fill=(185, 200, 215))

    out = 'docs/fig/ring_fit_overlay.jpg'
    panel.save(out, quality=93)
    print('saved', out, panel.size)


if __name__ == '__main__':
    main()
