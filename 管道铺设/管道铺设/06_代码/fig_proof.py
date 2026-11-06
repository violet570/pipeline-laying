# -*- coding: utf-8 -*-
"""Two proof crops rendered from the registry itself, so what you see is exactly what the
pipeline will use:
  docs/fig/proof_plaza_5.jpg   the 5 plaza buildings with their assigned names
  docs/fig/proof_canteens.jpg  the two canteens (燕园餐厅 vs 西区大食堂)

Labels: short name is drawn INSIDE each building outline (so it can never float in the
wrong place, which is what went wrong with the earlier hand-guessed figure); full names go
in a legend strip under the image.
"""
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


def render(out, title, sub, lat0, lon0, hw, hh, keys, legend=()):
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
    d = ImageDraw.Draw(img)

    def px(lon, lat):
        X, Y = merc_px(*wgs2gcj(lon, lat), Z)
        return X - ox, Y - oy

    ways = G.load_ways()
    fnt = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 22)
    for g in G.GROUPS:
        if g['key'] not in keys:
            continue
        m = g.get('measured')
        if m:
            x0, y0 = px(m['bbox'][0], m['bbox'][3])
            x1, y1 = px(m['bbox'][2], m['bbox'][1])
            d.rectangle([x0, y0, x1, y1], outline=(0, 255, 130), width=4)
            lx, ly = x0 + 5, y0 + 4
        else:
            el = ways.get(g['ways'][0])
            if not el:
                print('MISSING way', g['key'], g['ways'])
                continue
            gg = [p for p in (el.get('geometry') or []) if p]
            pts = [px(p['lon'], p['lat']) for p in gg]
            d.line(pts + [pts[0]], fill=(0, 255, 130), width=4)
            lx = min(p[0] for p in pts) + 5
            ly = min(p[1] for p in pts) + 4
        lab = g['short']
        tb = d.textbbox((0, 0), lab, font=fnt)
        d.rectangle([lx - 2, ly - 2, lx + tb[2] + 4, ly + tb[3] + 4], fill=(0, 0, 0))
        d.text((lx, ly), lab, font=fnt, fill=(255, 255, 140))

    top, gap = 74, 30
    bot = gap + 26 * len(legend) if legend else 12
    panel = Image.new('RGB', (2 * hw, 2 * hh + top + bot), (6, 10, 16))
    panel.paste(img, (0, top))
    d2 = ImageDraw.Draw(panel)
    d2.text((12, 6), title, font=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 26),
            fill=(255, 255, 255))
    d2.text((12, 42), sub, font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 18),
            fill=(180, 200, 220))
    if legend:
        f3 = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 17)
        for i, line in enumerate(legend):
            d2.text((12, top + 2 * hh + gap + 26 * i - 8), line, font=f3, fill=(210, 220, 235))
    panel.save(os.path.join(FIG, out), quality=93)
    print('saved', out, panel.size)


if __name__ == '__main__':
    render('proof_plaza_5.jpg',
           '圆形广场五栋：按你两轮口述定名（绿框=实测位置）',
           '左列两栋=人工智能学院(软件学院)，右列两栋=理学院；OSM 在此处一栋都没画（±1.5 m）',
           39.916200, 119.515400, 430, 300, {'X01', 'X02', 'X03', 'X04', 'X05'},
           legend=['X01 信息科学与工程学院           最上方弧形大楼，3,718.5 m²',
                   'X02 人工智能学院(软件学院)北楼   左列上，2,719 m²',
                   'X05 人工智能学院(软件学院)南楼   左列下，4,783 m²',
                   'X04 理学院北楼                   右列上，3,246 m²',
                   'X03 理学院南楼                   右列下，5,412 m²'])
    render('proof_canteens.jpg',
           '两个食堂的位置关系（此前混淆，已更正）',
           '上方=燕园餐厅(燕园食堂)  下方=西区大食堂（U02/U03 正南，带弧形南门廊）',
           39.907600, 119.513900, 430, 540, {'C01', 'C03'},
           legend=['C01 燕园餐厅(燕园食堂) — OSM 原有标注，位置一直是对的',
                   'C03 西区大食堂 — 此前被误标成上面那个，实为此处，影像量测'])
    render('proof_lab.jpg',
           '材料B楼下方的半圆建筑 = 亚稳材料实验室',
           '绿框=影像量测；官方全称「亚稳材料制备技术与科学国家重点实验室」',
           39.907200, 119.517200, 300, 250, {'T17'},
           legend=['T17 亚稳材料制备技术与科学国家重点实验室（约 2,500 m²）',
                   '长方形主体 + 南向半圆弧，位于 材料B楼 正下方',
                   '来源 mse.ysu.edu.cn/gjzdsys/gjsys.htm'])
