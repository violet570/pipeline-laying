# -*- coding: utf-8 -*-
"""Final proof map: every registry group drawn on the z17 satellite mosaic, using OSM
geometry where a way exists and the measured bbox where it does not.

Highlights the user-reported corrections so the map can be checked at a glance:
  C01 燕园餐厅  /  C03 西区大食堂  /  T17 亚稳材料国家重点实验室  /  T18 里仁实验楼  /  P01 办公楼(里仁)
  /  T19 图文信息楼  /  C04 浴池  /  X01–X05 圆形广场五栋
  (M01 机械厂 was removed at the user's request in round 4.)
"""
import json
import math
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fig_campus_all import wgs2gcj, merc_px  # noqa: E402
import groups as G  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILES = os.path.join(ROOT, 'data', 'tiles', 'campus_sat_z17_full')
FIG = os.path.join(ROOT, 'docs', 'fig')
Z = 17
LAT0, LON0 = 39.91090, 119.51800
HW, HH = 1400, 1250

NEW = {'C01', 'C03', 'T17', 'T18', 'T19', 'C04', 'X01', 'X02', 'X03', 'X04', 'X05', 'P01'}
CAT_COL = {
    'dorm': (255, 92, 92), 'canteen': (255, 168, 60), 'service': (255, 214, 92),
    'teaching': (86, 170, 255), 'college': (150, 120, 255), 'library': (120, 110, 255),
    'lab': (200, 110, 240), 'office': (110, 220, 170), 'activity': (255, 130, 200),
    'art': (255, 200, 130), 'utility': (170, 170, 180), 'workshop': (255, 130, 60),
    'sports': (120, 235, 235),
    'other': (140, 150, 165),
}


def main():
    cx, cy = merc_px(*wgs2gcj(LON0, LAT0), Z)
    st = {}
    for fn in os.listdir(TILES):
        p = fn.replace('.jpg', '').split('_')
        if len(p) == 3:
            st[(int(p[1]), int(p[2]))] = os.path.join(TILES, fn)
    ox, oy = int(cx) - HW, int(cy) - HH
    W, H = 2 * HW, 2 * HH
    img = Image.new('RGB', (W, H), (10, 12, 16))
    for tx in range(ox // 256, (int(cx) + HW) // 256 + 1):
        for ty in range(oy // 256, (int(cy) + HH) // 256 + 1):
            fp = st.get((tx, ty))
            if fp:
                img.paste(Image.open(fp).convert('RGB'), (tx * 256 - ox, ty * 256 - oy))
    d = ImageDraw.Draw(img)

    def px(lon, lat):
        X, Y = merc_px(*wgs2gcj(lon, lat), Z)
        return X - ox, Y - oy

    ways = G.load_ways()
    labels = []
    for g in G.GROUPS:
        col = CAT_COL.get(g['cat'], (150, 150, 160))
        isnew = g['key'] in NEW
        lw = 3 if isnew else 2          # 细线：只比底图纹理略粗，避免糊住屋顶
        boxes = []
        if g.get('measured'):
            m = g['measured']
            x0, y0 = px(m['bbox'][0], m['bbox'][3])
            x1, y1 = px(m['bbox'][2], m['bbox'][1])
            d.rectangle([x0, y0, x1, y1], outline=col, width=lw)
            boxes.append((x0, y0, x1, y1))
        else:
            for wid in g['ways']:
                el = ways.get(wid)
                if not el:
                    continue
                gg = [p for p in (el.get('geometry') or []) if p]
                if len(gg) < 3:
                    continue
                pts = [px(p['lon'], p['lat']) for p in gg]
                d.line(pts + [pts[0]], fill=col, width=lw)
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                boxes.append((min(xs), min(ys), max(xs), max(ys)))
        if not boxes:
            continue
        # 一个建筑群只放一个标签：用该组所有多边形的并集外框
        # （未命名小建筑 U01–U15 只画轮廓、不写字，否则宿舍区会被小标签糊死）
        if g['cat'] == 'other':
            continue
        labels.append((g['short'],
                       (min(b[0] for b in boxes), min(b[1] for b in boxes),
                        max(b[2] for b in boxes), max(b[3] for b in boxes)),
                       col, isnew, g['key']))

    fnt = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 19)
    fnt_s = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 15)   # 未命名小建筑用更小字号
    small = {}
    for g in G.GROUPS:
        if g['cat'] == 'other':
            small[g['key']] = True
    used = []
    for lab, (x0, y0, x1, y1), col, isnew, key in sorted(labels, key=lambda t: (t[1][1], t[1][0])):
        f = fnt_s if (small.get(key) and not isnew) else fnt
        step = 18 if small.get(key) and not isnew else 21
        X = (x0 + x1) / 2.0
        Y = (y0 + y1) / 2.0
        yy = Y
        for _ in range(20):
            if all(abs(yy - uy) > step or abs(X - ux) > 110 for ux, uy in used):
                break
            yy += step
        used.append((X, yy))
        tb = d.textbbox((0, 0), lab, font=f)
        d.rectangle([X - 3, yy - 2, X + tb[2] + 6, yy + tb[3] + 4],
                    fill=(72, 22, 8) if isnew else (0, 0, 0))
        d.text((X, yy), lab, font=f, fill=col if not isnew else (255, 245, 200))
        if abs(yy - Y) > 4:
            d.line([(X, Y), (X, yy)], fill=col, width=1)

    pad = 96
    panel = Image.new('RGB', (W, H + pad), (6, 10, 16))
    panel.paste(img, (0, pad))
    d2 = ImageDraw.Draw(panel)
    n_geom = sum(1 for g in G.GROUPS if g['ways'] or g.get('measured'))
    d2.text((14, 8), '燕山大学西校区 建筑群注册表 %d 组（其中 %d 组已有几何、参与计算）'
            % (len(G.GROUPS), n_geom),
            font=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 32), fill=(255, 255, 255))
    d2.text((14, 50), '浅米黄字+深红底 = 按用户口述更正/补入项；另有 11 条官方图上的楼名位置待实测（不参与计算）',
            font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 20), fill=(255, 200, 150))
    # legend
    lx = W - 470
    ly = H + pad - 30
    d2.text((lx - 8, ly - 34), '红=公寓 橙=食堂 蓝=教学 紫=学院 绿=办公', font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 17), fill=(200, 210, 225))
    out = os.path.join(FIG, 'fig8_campus_registry_corrected.jpg')
    panel.save(out, quality=90)
    print('saved', out, panel.size, 'labels', len(labels))


if __name__ == '__main__':
    main()
