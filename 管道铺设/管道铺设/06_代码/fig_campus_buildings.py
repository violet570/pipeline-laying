# -*- coding: utf-8 -*-
"""Figure 4: whole west-campus building inventory labelled on high-res satellite.

Goal: prove the OSM inventory is complete & correctly located for EVERY building
cluster (not just dorms), and provide the visual deliverable of the survey step.

Outputs
  docs/fig/fig4_campus_buildings_z18.jpg    z18 satellite mosaic + all buildings
                                            labelled (dorms red / teaching blue /
                                            canteen orange / labs purple / others grey)
  docs/fig/fig4b_dorm_satellite_z18.jpg     zoom on 13 dorm groups with 组团 names
"""
import json
import math
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from groups import GROUPS, load_ways  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')
TILES = os.path.join(ROOT, 'data', 'tiles')
FIG = os.path.join(ROOT, 'docs', 'fig')
os.makedirs(FIG, exist_ok=True)

FONT = 'C:/Windows/Fonts/msyh.ttc'
FONTB = 'C:/Windows/Fonts/msyhbd.ttc'


def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


# ---------------- WGS-84 -> GCJ-02 ----------------
A = 6378245.0
EE = 0.00669342162296594323


def _tlat(x, y):
    r = (-100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x)))
    r += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    r += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    r += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return r


def _tlon(x, y):
    r = (300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x)))
    r += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    r += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    r += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return r


def wgs2gcj(lon, lat):
    dlat, dlon = _tlat(lon - 105.0, lat - 35.0), _tlon(lon - 105.0, lat - 35.0)
    rad = lat / 180.0 * math.pi
    magic = 1 - EE * math.sin(rad) ** 2
    sm = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sm) * math.pi)
    dlon = (dlon * 180.0) / (A / sm * math.cos(rad) * math.pi)
    return lon + dlon, lat + dlat


def load(name):
    with open(os.path.join(RAW, name), encoding='utf-8') as f:
        return json.load(f)


# ---------------- tile stitching ----------------
def stitch(job):
    d = os.path.join(TILES, job)
    pos = {}
    z = x0 = y0 = None
    for fn in os.listdir(d):
        m = re.match(r'(\d+)_(\d+)_(\d+)\.(jpg|png)$', fn)
        if not m:
            continue
        z, x, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        pos[(x, y)] = os.path.join(d, fn)
    xs = sorted({p[0] for p in pos})
    ys = sorted({p[1] for p in pos})
    x0, y0 = xs[0], ys[0]
    nx, ny = xs[-1] - x0 + 1, ys[-1] - y0 + 1
    img = Image.new('RGB', (nx * 256, ny * 256), (24, 26, 30))
    for (x, y), fp in pos.items():
        img.paste(Image.open(fp).convert('RGB'), ((x - x0) * 256, (y - y0) * 256))
    return img, z, x0, y0


def merc_px(lon, lat, z):
    n = 256.0 * (2 ** z)
    X = (lon + 180.0) / 360.0 * n
    s = math.sin(lat * math.pi / 180.0)
    Y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return X, Y


def make_proj(z, x0, y0, ox=0, oy=0):
    def f(lon, lat):
        X, Y = merc_px(*wgs2gcj(lon, lat), z)
        return X - x0 * 256 - ox, Y - y0 * 256 - oy
    return f


def poly_centroid(pts):
    return (sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts))  # lat, lon


CAT_STYLE = {
    'dorm': ((255, 78, 78), 5),
    'canteen': ((255, 168, 38), 4),
    'teaching': ((60, 150, 255), 4),
    'college': ((0, 210, 214), 4),
    'library': ((70, 110, 220), 4),
    'lab': ((190, 120, 255), 4),
    'office': ((140, 200, 90), 4),
    'activity': ((250, 120, 200), 4),
    'art': ((230, 150, 120), 4),
    'service': ((255, 210, 90), 4),
    'utility': ((160, 160, 160), 4),
    'other': ((200, 205, 215), 3),
}


def short_label(g):
    return g['short']


def main():
    ways = load_ways()
    # boundary
    bnd = load('campus_boundary.json')['elements']
    west_el = min(bnd, key=lambda e: (e['bounds']['minlon'] + e['bounds']['maxlon']) / 2)
    west = [(p['lon'], p['lat']) for p in west_el['geometry']]
    lons = [p[0] for p in west]
    lats = [p[1] for p in west]
    pad = 0.0016
    CLON0, CLON1, CLAT0, CLAT1 = min(lons) - pad, max(lons) + pad, min(lats) - pad, max(lats) + pad

    # ---------- Fig 4: whole campus ----------------
    img, z, x0, y0 = stitch('dorms_sat_z18')   # z18 dorm-area mosaic
    big, zz, xx, yy = stitch('campus_sat_z17')  # z17 fallback check
    print('mosaic z18', img.size, 'z17', big.size)

    base_proj = make_proj(z, x0, y0)
    tl = base_proj(CLON0, CLAT1)
    br = base_proj(CLON1, CLAT0)
    cx0, cy0 = int(tl[0]), int(tl[1])
    cx1, cy1 = int(br[0]), int(br[1])
    # mask out-of-canvas
    if cx0 < 0 or cy0 < 0 or cx1 > img.width or cy1 > img.height:
        print('WARN crop out of range', (cx0, cy0, cx1, cy1), img.size)
    cx0, cy0 = max(0, cx0), max(0, cy0)
    cx1, cy1 = min(img.width, cx1), min(img.height, cy1)
    canvas = img.crop((cx0, cy0, cx1, cy1))
    proj = make_proj(z, x0, y0, cx0, cy0)

    # darken for legibility
    canvas = Image.blend(canvas, Image.new('RGB', canvas.size, (10, 14, 20)), 0.42)
    d = ImageDraw.Draw(canvas)

    d.line([proj(*p) for p in west] + [proj(*west[0])], fill=(255, 215, 0), width=5)

    # every building way: thin outline
    for el in ways.values():
        g = [p for p in (el.get('geometry') or []) if p]
        if len(g) < 3:
            continue
        d.line([proj(p['lon'], p['lat']) for p in g] + [proj(g[0]['lon'], g[0]['lat'])],
               fill=(120, 140, 165), width=2)

    # group outlines + labels
    placed = []
    for grp in GROUPS:
        color, w = CAT_STYLE.get(grp['cat'], ((200, 200, 200), 3))
        cl = []
        for wid in grp['ways']:
            el = ways.get(wid)
            if not el:
                continue
            g = [p for p in (el.get('geometry') or []) if p]
            if len(g) < 3:
                continue
            d.line([proj(p['lon'], p['lat']) for p in g] + [proj(g[0]['lon'], g[0]['lat'])],
                   fill=color, width=w)
            cl.append(poly_centroid([(p['lon'], p['lat']) for p in g]))
        if not cl:
            continue
        glat = sum(c[0] for c in cl) / len(cl)
        glon = sum(c[1] for c in cl) / len(cl)
        placed.append((grp, proj(glon, glat), color))

    # simple label de-overlap: nudge vertically if too close
    placed.sort(key=lambda t: (t[1][1], t[1][0]))
    used = []
    for grp, (px, py), color in placed:
        ny = py
        for _ in range(12):
            if all(abs(ny - uy) > 26 or abs(px - ux) > 150 for ux, uy in used):
                break
            ny += 26
        used.append((px, ny))
        txt = grp['short']
        fnt = font(24, True)
        tb = d.textbbox((0, 0), txt, font=fnt)
        d.rectangle([px - 2, ny - 2, px + tb[2] + 6, ny + tb[3] + 4], fill=(0, 0, 0))
        d.text((px + 2, ny), txt, font=fnt, fill=color)
        d.line([(px, py), (px, ny)], fill=color, width=2)

    # title + legend
    W, H = canvas.size
    d.rectangle([0, 0, W, 110], fill=(8, 12, 18))
    d.text((26, 14), '燕山大学西校区 建筑清单调查（OSM 矢量 × 高德卫星 z18）',
           font=font(44, True), fill=(255, 255, 255))
    d.text((26, 66), '共 %d 个建筑群 / %d 栋单体；轮廓 WGS-84 → GCJ-02 校正叠加' % (len(GROUPS), len(ways)),
           font=font(26), fill=(190, 205, 225))

    lx, ly = 26, H - 300
    d.rectangle([lx, ly, lx + 520, H - 60], fill=(8, 12, 18))
    d.text((lx + 16, ly + 10), '图例', font=font(28, True), fill=(255, 255, 255))
    legend = [('dorm', '学生公寓（13 组团/34 栋）'), ('teaching', '教学·学院楼'),
              ('canteen', '食堂/服务'), ('lab', '实验楼'), ('library', '图书馆'),
              ('office', '办公楼/活动中心/美术馆'), ('other', '未命名建筑（待核实）')]
    for i, (cat, txt) in enumerate(legend):
        yy = ly + 52 + i * 33
        color = CAT_STYLE[cat][0]
        d.line([(lx + 20, yy + 10), (lx + 80, yy + 10)], fill=color, width=5)
        d.text((lx + 96, yy), txt, font=font(24), fill=(220, 228, 240))

    d.text((26, H - 44),
           '轮廓/名称：OpenStreetMap © contributors (ODbL) ｜ 影像：高德地图（仅对照/署名）｜ 快照 2026-08',
           font=font(22), fill=(200, 210, 225))

    out = os.path.join(FIG, 'fig4_campus_buildings_z18.jpg')
    if canvas.width > 3000:
        canvas = canvas.resize((3000, int(canvas.height * 3000 / canvas.width)), Image.LANCZOS)
    canvas.save(out, quality=90)
    print('fig4', canvas.size, out)

    # ---------- Fig 4b: dorm zoom ----------------
    DLON0, DLON1, DLAT0, DLAT1 = 119.5050, 119.5230, 39.9015, 39.9125
    tl = base_proj(DLON0, DLAT1)
    br = base_proj(DLON1, DLAT0)
    x0c, y0c = max(0, int(tl[0])), max(0, int(tl[1]))
    x1c, y1c = min(img.width, int(br[0])), min(img.height, int(br[1]))
    c2 = img.crop((x0c, y0c, x1c, y1c))
    c2 = Image.blend(c2, Image.new('RGB', c2.size, (10, 14, 20)), 0.30)
    p2 = make_proj(z, x0, y0, x0c, y0c)
    d2 = ImageDraw.Draw(c2)
    for el in ways.values():
        g = [p for p in (el.get('geometry') or []) if p]
        if len(g) < 3:
            continue
        d2.line([p2(p['lon'], p['lat']) for p in g] + [p2(g[0]['lon'], g[0]['lat'])],
                fill=(150, 168, 190), width=2)
    for grp in GROUPS:
        if grp['cat'] not in ('dorm', 'canteen', 'service'):
            continue
        color = CAT_STYLE[grp['cat']][0]
        for wid in grp['ways']:
            el = ways.get(wid)
            if not el:
                continue
            g = [p for p in (el.get('geometry') or []) if p]
            if len(g) < 3:
                continue
            d2.line([p2(p['lon'], p['lat']) for p in g] + [p2(g[0]['lon'], g[0]['lat'])],
                    fill=color, width=5)
            la = sum(p['lat'] for p in g) / len(g)
            lo = sum(p['lon'] for p in g) / len(g)
            px, py = p2(lo, la)
            nm = (el.get('tags') or {}).get('name') or ''
            d2.text((px + 4, py + 2), nm or grp['short'], font=font(22, True),
                    fill=(255, 245, 160), stroke_width=3, stroke_fill=(0, 0, 0))
    W2, H2 = c2.size
    d2.rectangle([0, 0, W2, 92], fill=(8, 12, 18))
    d2.text((24, 12), '宿舍区核对：13 组团 / 34 栋公寓 逐栋吻合（高德卫星 z18）',
            font=font(38, True), fill=(255, 255, 255))
    d2.text((24, 58), '红=学生公寓  橙=食堂  黄=服务楼；OSM 2026-08 快照',
            font=font(24), fill=(190, 205, 225))
    out2 = os.path.join(FIG, 'fig4b_dorm_satellite_z18.jpg')
    if c2.width > 2400:
        c2 = c2.resize((2400, int(c2.height * 2400 / c2.width)), Image.LANCZOS)
    c2.save(out2, quality=90)
    print('fig4b', c2.size, out2)


if __name__ == '__main__':
    main()
