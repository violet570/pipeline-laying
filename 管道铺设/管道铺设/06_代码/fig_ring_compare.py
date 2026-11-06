# -*- coding: utf-8 -*-
"""Compare the user-traced plaza ring against the ring road visible in imagery.

Renders the plaza zoom with:
  * the traced ring (radius as drawn by the user, ~66 m) in magenta
  * concentric candidate rings at 100 / 130 / 150 / 170 m in cyan, dashes
so the user can judge which radius actually sits on the asphalt.

usage: python scripts/fig_ring_compare.py
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

FIG = os.path.join(ROOT, 'docs', 'fig')
TILES = os.path.join(ROOT, 'data', 'tiles', 'campus_sat_z18_full')
Z = 18

FONT = 'C:/Windows/Fonts/msyhbd.ttc'
FONT_R = 'C:/Windows/Fonts/msyh.ttc'


def stitch():
    xs, ys = [], []
    for fn in os.listdir(TILES):
        if not fn.endswith('.jpg'):
            continue
        z, x, y = fn[:-4].split('_')
        if int(z) != Z:
            continue
        xs.append(int(x))
        ys.append(int(y))
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    im = Image.new('RGB', ((x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256))
    for fn in os.listdir(TILES):
        if not fn.endswith('.jpg'):
            continue
        z, x, y = fn[:-4].split('_')
        if int(z) != Z:
            continue
        im.paste(Image.open(os.path.join(TILES, fn)),
                 ((int(x) - x0) * 256, (int(y) - y0) * 256))
    return im, x0, y0


def main():
    im, ox, oy = stitch()

    # traced ring -> centroid and mean radius
    d = json.load(open('data/derived/plaza_roads_user.json', encoding='utf-8'))
    ring = d['segments']['plaza_ring']
    LAT0, LON0 = 39.9111, 119.5172
    K = 111320.0
    KL = 111320.0 * math.cos(math.radians(LAT0))

    def m(lon, lat):
        return (lon - LON0) * KL, (lat - LAT0) * K

    pts_m = [m(*p) for p in ring]
    cx = (min(p[0] for p in pts_m) + max(p[0] for p in pts_m)) / 2
    cy = (min(p[1] for p in pts_m) + max(p[1] for p in pts_m)) / 2
    radii = [math.hypot(p[0] - cx, p[1] - cy) for p in pts_m]
    r_traced = sum(radii) / len(radii)

    def back(x, y):
        return (LON0 + x / KL, LAT0 + y / K)

    def px(lon, lat):
        glon, glat = wgs2gcj(lon, lat)
        X, Y = merc_px(glon, glat, Z)
        return X - ox * 256, Y - oy * 256

    cpx, cpy = px(*back(cx, cy))

    # metres -> pixels at this latitude (Web Mercator, z18)
    lat_g = wgs2gcj(*back(cx, cy))[1]
    res = 156543.03392804097 * math.cos(math.radians(lat_g)) / (2 ** Z)
    print('z%d resolution = %.3f m/px ; traced radius %.1f m = %.1f px'
          % (Z, res, r_traced, r_traced / res))

    # crop around the plaza
    HW, HH = 420, 400
    box = (int(cpx - HW), int(cpy - HH), int(cpx + HW), int(cpy + HH))
    crop = im.crop(box)
    SC = 2
    crop = crop.resize((crop.width * SC, crop.height * SC), Image.LANCZOS)
    top = 96
    panel = Image.new('RGB', (crop.width, crop.height + top), (6, 9, 14))
    panel.paste(crop, (0, top))
    dr = ImageDraw.Draw(panel, 'RGBA')

    def P(x, y):
        """local metres -> panel pixel"""
        lon, lat = back(x, y)
        gx, gy = px(lon, lat)
        return ((gx - box[0]) * SC, (gy - box[1]) * SC + top)

    # candidate circles
    cands = [(r_traced, (255, 60, 200, 255), '你的描线 %.0f m' % r_traced, 4),
             (100, (90, 220, 255, 200), '100 m', 2),
             (130, (90, 220, 255, 200), '130 m', 2),
             (150, (120, 255, 140, 230), '150 m', 3),
             (170, (255, 210, 90, 200), '170 m', 2)]
    c0 = P(cx, cy)
    for r, col, lab, w in cands:
        # draw in metres via sampled arc
        path = []
        for k in range(181):
            a = 2 * math.pi * k / 180
            path.append(P(cx + r * math.cos(a), cy + r * math.sin(a)))
        dr.line(path, fill=col, width=w, joint='curve')
        ang = -math.pi / 4
        lx, ly = P(cx + r * math.cos(ang), cy + r * math.sin(ang))
        f = ImageFont.truetype(FONT_R, 26)
        tw = dr.textlength(lab, font=f)
        dr.rectangle([lx - 6, ly - 18, lx + tw + 6, ly + 14], fill=(0, 0, 0, 190))
        dr.text((lx, ly - 16), lab, font=f, fill=col[:3] + (255,))

    # the actual traced polyline on top, thicker
    tp = [P(*m(*p)) for p in ring]
    dr.line(tp + [tp[0]], fill=(255, 60, 200, 255), width=5, joint='curve')
    for p in tp:
        dr.ellipse([p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4], fill=(255, 255, 255, 230))

    # buildings (measured bboxes) for reference
    b = json.load(open('data/derived/pipeline_bundle_conn.json', encoding='utf-8'))
    fnt = ImageFont.truetype(FONT, 24)
    for bb in b['buildings']:
        if bb['src'] != 'measured':
            continue
        x0, y0, x1, y1 = (bb['footprint'][0][0], bb['footprint'][0][1],
                          bb['footprint'][2][0], bb['footprint'][2][1])
        q = [P(*m(x0, y0)), P(*m(x1, y0)), P(*m(x1, y1)), P(*m(x0, y1))]
        dr.polygon(q, outline=(0, 240, 230, 230), width=2)
        mx = (q[0][0] + q[2][0]) / 2
        my = (q[0][1] + q[2][1]) / 2
        dr.text((mx - dr.textlength(bb['short'], font=fnt) / 2, my - 12),
                bb['short'], font=fnt, fill=(255, 255, 255, 255))

    # title
    t1 = ImageFont.truetype(FONT, 34)
    t2 = ImageFont.truetype(FONT_R, 21)
    dr.text((14, 10), '圆形广场：你的描线 vs 影像上的真实环道', font=t1, fill=(255, 255, 255))
    dr.text((14, 52), '洋红粗线 = 你标注的环路（半径 %.0f m）；青色/绿色细圆 = 候选半径。'
                     '看哪一圈正好压在沥青路面上。' % r_traced,
            font=t2, fill=(190, 205, 220))

    out = os.path.join(FIG, 'ring_compare.jpg')
    panel.save(out, quality=93)
    print('saved', out, panel.size)


if __name__ == '__main__':
    main()
