# -*- coding: utf-8 -*-
"""Read-off grid for the lab block: 0.0002 deg graticule (~22 m) so the semicircular
building south of 材料B楼 can be measured to +-1.5 m.

Out: docs/fig/loc_lab_grid.jpg
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fig_campus_all import wgs2gcj, merc_px  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TILES = os.path.join(ROOT, 'data', 'tiles', 'campus_sat_z18_full')
FIG = os.path.join(ROOT, 'docs', 'fig')
Z = 18
LAT0, LON0 = 39.907200, 119.517200
HW, HH = 300, 240
STEP = 0.0002


def main():
    cx, cy = merc_px(*wgs2gcj(LON0, LAT0), Z)
    st = {}
    for fn in os.listdir(TILES):
        p = fn.replace('.jpg', '').split('_')
        if len(p) == 3:
            st[(int(p[1]), int(p[2]))] = os.path.join(TILES, fn)
    ox, oy = int(cx) - HW, int(cy) - HH
    img = Image.new('RGB', (2 * HW, 2 * HH), (0, 0, 0))
    for tx in range(ox // 256, (int(cx) + HW) // 256 + 1):
        for ty in range(oy // 256, (int(cy) + HH) // 256 + 1):
            fp = st.get((tx, ty))
            if fp:
                img.paste(Image.open(fp).convert('RGB'), (tx * 256 - ox, ty * 256 - oy))
    img = img.resize((2 * HW * 2, 2 * HH * 2), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 15)

    def px(lon, lat):
        X, Y = merc_px(*wgs2gcj(lon, lat), Z)
        return ((X - ox) * 2, (Y - oy) * 2)

    for k in range(-6, 7):
        lat = round(LAT0 + k * STEP, 5)
        _, Y = px(LON0, lat)
        d.line([(0, Y), (2 * HW * 2, Y)], fill=(255, 60, 60), width=1)
        d.text((2, Y + 1), '%.4f' % lat, font=f, fill=(255, 255, 90))
        lon = round(LON0 + k * STEP, 5)
        X, _ = px(lon, LAT0)
        d.line([(X, 0), (X, 2 * HH * 2)], fill=(255, 60, 60), width=1)
        d.text((X + 2, 2), '%.4f' % lon, font=f, fill=(255, 255, 90))

    panel = Image.new('RGB', (2 * HW * 2, 2 * HH * 2 + 56), (6, 10, 16))
    panel.paste(img, (0, 56))
    d2 = ImageDraw.Draw(panel)
    d2.text((10, 4), '材料B楼下方：半圆形建筑读点网格（0.0002° ≈ 22 m）',
            font=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 24), fill=(255, 255, 255))
    d2.text((10, 32), '红线 = 经纬网，数字为该线的经纬度（WGS-84）',
            font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 16), fill=(185, 200, 220))
    panel.save(os.path.join(FIG, 'loc_lab_grid.jpg'), quality=94)
    print('saved loc_lab_grid.jpg', panel.size)


if __name__ == '__main__':
    main()
