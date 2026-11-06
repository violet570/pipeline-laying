# -*- coding: utf-8 -*-
"""Pin the four buildings the user named that OSM does not have (or has wrong), by reading
their outline off the z18 satellite mosaic with a 0.0002-degree graticule.

Targets and what to look for:
  C03 西区大食堂   big rectangular hall with a curved south portico, directly S of U02/U03
  T18 里仁实验楼   block immediately beside 里仁教学楼
  C04 燕大西区浴池 block E of the canteen / S of 8 组团
  T17 材料A楼      block N of 材料B/C (only if visible)

Writes data/derived/pinned_targets.json with a bbox per target; the registry consumes it.

Run: python scripts/pin_fine.py
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fig_campus_all import wgs2gcj, merc_px  # noqa: E402
import groups as G  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILES = os.path.join(ROOT, 'data', 'tiles', 'campus_sat_z18_full')
FIG = os.path.join(ROOT, 'docs', 'fig')
Z = 18


def px2ll(X, Y, ox, oy):
    mx, my = ox + X, oy + Y
    n = 2.0 ** Z * 256.0
    gx = mx / n * 360.0 - 180.0
    gy = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * my / n))))
    lon, lat = gx, gy
    for _ in range(30):
        tl, tt = wgs2gcj(lon, lat)
        lon += gx - tl
        lat += gy - tt
    return lat, lon


def crop(lat0, lon0, hw, hh):
    cx, cy = merc_px(*wgs2gcj(lon0, lat0), Z)
    st = {}
    for fn in os.listdir(TILES):
        p = fn.replace('.jpg', '').split('_')
        if len(p) == 3:
            st[(int(p[1]), int(p[2]))] = os.path.join(TILES, fn)
    ox, oy = int(cx) - hw, int(cy) - hh
    img = Image.new('RGB', (2 * hw, 2 * hh), (10, 12, 16))
    for tx in range(ox // 256, (int(cx) + hw) // 256 + 1):
        for ty in range(oy // 256, (int(cy) + hh) // 256 + 1):
            fp = st.get((tx, ty))
            if fp:
                img.paste(Image.open(fp).convert('RGB'), (tx * 256 - ox, ty * 256 - oy))
    return img, ox, oy


def annotate(img, ox, oy, hw, hh, lat0, lon0, title, boxes=None, subt='/', step=0.0002):
    d = ImageDraw.Draw(img)

    def px(lon, lat):
        X, Y = merc_px(*wgs2gcj(lon, lat), Z)
        return X - ox, Y - oy

    f2 = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 14)
    nlat = int(hh / (step * 111320.0)) + 2
    for k in range(-nlat, nlat + 1):
        la = round(lat0 + k * step, 5)
        if la <= -85 or la >= 85:
            continue
        X, Y = px(lon0, la)
        if 0 <= Y <= 2 * hh:
            d.line([(0, Y), (2 * hw, Y)], fill=(0, 235, 255), width=1)
            d.text((2, Y + 1), '%.4f' % la, font=f2, fill=(0, 235, 255))
    nlon = int(hw / (step * 111320.0 * math.cos(math.radians(lat0)))) + 2
    for k in range(-nlon, nlon + 1):
        lo = round(lon0 + k * step, 5)
        X, Y = px(lo, lat0)
        if 0 <= X <= 2 * hw:
            d.line([(X, 0), (X, 2 * hh)], fill=(0, 235, 255), width=1)
            d.text((X + 1, 2), '%.4f' % lo, font=f2, fill=(0, 235, 255))

    for lab, box in (boxes or []):
        x0, y0 = px(box[0], box[3])
        x1, y1 = px(box[2], box[1])
        d.rectangle([x0, y0, x1, y1], outline=(255, 70, 70), width=3)
        d.text((x0 + 2, y0 + 2), lab, font=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 18),
               fill=(255, 255, 120))

    pad = 70
    panel = Image.new('RGB', (2 * hw, 2 * hh + pad), (6, 10, 16))
    panel.paste(img, (0, pad))
    d2 = ImageDraw.Draw(panel)
    d2.text((12, 6), title, font=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 23),
            fill=(255, 255, 255))
    d2.text((12, 40), subt, font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 16),
            fill=(180, 200, 220))
    return panel


if __name__ == '__main__':
    hw, hh = 360, 280
    img, ox, oy = crop(39.906050, 119.515400, hw, hh)
    annotate(img, ox, oy, hw, hh, 39.906050, 119.515400,
             '西区大食堂 精确定位（底图 z18，网格 0.0002°≈22 m）',
             [], step=0.0002).save(os.path.join(FIG, 'pin_canteen_fine.jpg'), quality=94)
    print('saved pin_canteen_fine.jpg')

    img, ox, oy = crop(39.904300, 119.523000, hw, hh)
    annotate(img, ox, oy, hw, hh, 39.904300, 119.523000,
             '里仁教学楼周边（找里仁实验楼）', [], step=0.0002
             ).save(os.path.join(FIG, 'pin_liren_fine.jpg'), quality=94)
    print('saved pin_liren_fine.jpg')
