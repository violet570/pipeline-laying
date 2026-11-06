# -*- coding: utf-8 -*-
"""Visual registration audit: crop individual buildings at z18 and overlay the OSM ring.

Automatic shift-search proves unreliable on z17 (objective saturates), so we do the
honest thing: human-inspectable zoomed crops.  Each panel shows 高德 z18 imagery with
the WGS-84 OSM ring converted to GCJ-02 drawn on top, plus a 5 m scale bar.

Output: docs/fig/fig6_registration_panels.jpg (one strip of 6 panels)
"""
import json
import math
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from groups import load_ways  # noqa: E402
from fig_campus_all import wgs2gcj, merc_px  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILES = os.path.join(ROOT, 'data', 'tiles')
FIG = os.path.join(ROOT, 'docs', 'fig')
FONTB = 'C:/Windows/Fonts/msyhbd.ttc'
FONT = 'C:/Windows/Fonts/msyh.ttc'

PANELS = [
    ('T06', '里仁教学楼', 39.905039, 119.522121, 240),
    ('T16', '图书馆', 39.908875, 119.526734, 240),
    ('C01', '西区大食堂', 39.909437, 119.512755, 200),
    ('D02', '2 组团公寓 (2-A/2-B)', 39.904650, 119.516590, 200),
    ('T09', '电气C楼', 39.909430, 119.514650, 200),
    ('T13', '高压科学中心', 39.903263, 119.520984, 200),
]
Z = 18
BOX = 300  # px per panel

def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


def tile_at(lon, lat, z):
    n = 2 ** z
    X, Y = merc_px(lon, lat, z)
    tx = int(X // 256)
    ty = int(Y // 256)
    return tx, ty


def grab(lon, lat, z, half):
    """Grab a (2*half) square of imagery centred on the GCJ-02 point, from tiles on disk."""
    gx, gy = wgs2gcj(lon, lat)
    X, Y = merc_px(gx, gy, z)
    X, Y = int(X), int(Y)
    out = Image.new('RGB', (2 * half, 2 * half), (20, 22, 26))
    x0, y0 = X - half, Y - half
    tx0, ty0 = x0 // 256, y0 // 256
    for tx in (tx0, tx0 + 1):
        for ty in (ty0, ty0 + 1):
            fp = None
            for fn in os.listdir(os.path.join(TILES, 'campus_sat_z17_full')):
                pass
            break
    return out, (X, Y)


def main():
    ways = load_ways()
    d18 = os.path.join(TILES, 'campus_sat_z18_full')
    # z18 tiles on disk use 高德 numbering; find them all once
    store = {}
    for fn in os.listdir(d18):
        m = re.match(r'(\d+)_(\d+)_(\d+)\.(jpg|png)$', fn)
        if m:
            store[(int(m.group(2)), int(m.group(3)))] = os.path.join(d18, fn)
    zs = {int(re.match(r'(\d+)_', fn).group(1)) for fn in os.listdir(d18)
          if re.match(r'\d+_\d+_\d+\.(jpg|png)$', fn)}
    z = min(zs) if zs else 18
    print('z18 tile set:', len(store), 'z =', z)

    def px(lon, lat):
        gx, gy = wgs2gcj(lon, lat)
        return merc_px(gx, gy, z)

    mpp = 156543.03392 * math.cos(math.radians(39.9111)) / (2 ** z)

    panels = []
    for key, name, lat, lon, half in PANELS:
        grp = next(g for g in __import__('groups').GROUPS if g['key'] == key)
        cx, cy = px(lon, lat)
        cxi, cyi = int(cx), int(cy)
        img = Image.new('RGB', (2 * half, 2 * half), (20, 22, 26))
        tx0, ty0 = (cxi - half) // 256, (cyi - half) // 256
        miss = 0
        for tx in range(tx0, (cxi + half) // 256 + 1):
            for ty in range(ty0, (cyi + half) // 256 + 1):
                fp = store.get((tx, ty))
                if not fp:
                    miss += 1
                    continue
                t = Image.open(fp).convert('RGB')
                img.paste(t, (tx * 256 - (cxi - half), ty * 256 - (cyi - half)))
        if miss:
            print('  %s missing %d tiles' % (key, miss))
        dr = ImageDraw.Draw(img)
        for wid in grp['ways']:
            el = ways.get(wid)
            if not el:
                continue
            g = [p for p in (el.get('geometry') or []) if p]
            if len(g) >= 3:
                pts = [(px(p['lon'], p['lat'])[0] - (cxi - half),
                        px(p['lon'], p['lat'])[1] - (cyi - half)) for p in g]
                dr.line(pts + [pts[0]], fill=(255, 40, 40), width=3)

        # frame + scale bar + caption band
        pad = 46
        panel = Image.new('RGB', (2 * half, 2 * half + pad), (8, 12, 18))
        panel.paste(img, (0, pad))
        d2 = ImageDraw.Draw(panel)
        d2.text((10, 8), '%s  %s' % (key, name), font=font(24, True), fill=(255, 255, 255))
        bar = int(10 / mpp)
        bx, by = 2 * half - bar - 16, 2 * half + pad - 22
        d2.rectangle([bx, by - 18, bx + bar, by], fill=(6, 10, 16))
        d2.line([(bx, by - 6), (bx + bar, by - 6)], fill=(255, 255, 255), width=4)
        d2.text((bx, by - 4), '10 m', font=font(18), fill=(255, 255, 255))
        panels.append(panel)

    W = sum(p.width for p in panels) + 12 * (len(panels) - 1)
    H = max(p.height for p in panels)
    sheet = Image.new('RGB', (W, H + 96), (8, 12, 18))
    x = 0
    for p in panels:
        sheet.paste(p, (x, 96))
        x += p.width + 12
    d = ImageDraw.Draw(sheet)
    d.text((14, 12), '配准抽检：OSM 建筑轮廓（红）叠加高德卫星 z18（WGS-84→GCJ-02 后）',
           font=font(36, True), fill=(255, 255, 255))
    d.text((14, 58), '若红框与屋顶边缘贴合，则"真实距离"取自 OSM 轮廓是可信的；高德影像 © 高德地图，轮廓 © OpenStreetMap contributors',
           font=font(20), fill=(190, 205, 225))
    out = os.path.join(FIG, 'fig6_registration_panels.jpg')
    sheet.save(out, quality=92)
    print('saved', out, sheet.size, 'mpp %.3f m/px' % mpp)


if __name__ == '__main__':
    main()
