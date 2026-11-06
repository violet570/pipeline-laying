"""Draw the user-traced plaza roads back onto the map to verify the trace.

usage: python scripts/fig_plaza_roads_check.py
"""
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

Z = 17
TILE = 256
X0, Y0 = 109046, 49659
NX, NY = 11, 10
FONT = 'C:/Windows/Fonts/msyh.ttc'
FONTB = 'C:/Windows/Fonts/msyhbd.ttc'


def merc_px(lon, lat, z=Z):
    n = 2.0 ** z * TILE
    x = (lon + 180.0) / 360.0 * n
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x, y


def wgs2gcj(lon, lat):
    a, ee = 6378245.0, 0.00669342162296594323

    def tlat(x, y):
        r = (-100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x)))
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

    dlat, dlon = tlat(lon - 105.0, lat - 35.0), tlon(lon - 105.0, lat - 35.0)
    rad = math.radians(lat)
    m = 1 - ee * math.sin(rad) ** 2
    sq = math.sqrt(m)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (m * sq) * math.pi)
    dlon = (dlon * 180.0) / (a / sq * math.cos(rad) * math.pi)
    return lon + dlon, lat + dlat


def sx(lon, lat):
    glon, glat = wgs2gcj(lon, lat)
    px, py = merc_px(glon, glat, Z)
    return px - X0 * TILE, py - Y0 * TILE


def main():
    img = Image.new('RGB', (NX * TILE, NY * TILE), (8, 10, 14))
    for x in range(X0, X0 + NX):
        for y in range(Y0, Y0 + NY):
            p = f'data/tiles/campus_sat_z17_full/{Z}_{x}_{y}.jpg'
            if os.path.exists(p):
                img.paste(Image.open(p).convert('RGB'), ((x - X0) * TILE, (y - Y0) * TILE))

    d = ImageDraw.Draw(img, 'RGBA')
    data = json.load(open('data/derived/plaza_roads_user.json', encoding='utf-8'))
    for name, pts in data['segments'].items():
        xy = [sx(lon, lat) for lon, lat in pts]
        d.line(xy, fill=(255, 60, 60, 240), width=5, joint='curve')
        for q in xy:
            d.ellipse([q[0] - 4, q[1] - 4, q[0] + 4, q[1] + 4], fill=(255, 220, 0, 255))

    # crop to plaza
    nw = sx(119.5110, 39.9185)
    se = sx(119.5210, 39.9105)
    box = (int(nw[0]), int(nw[1]), int(se[0]), int(se[1]))
    crop = img.crop(box)
    crop = crop.resize((int(crop.width * 2), int(crop.height * 2)), Image.LANCZOS)
    crop.save('docs/fig/plaza_roads_check.jpg', quality=90)
    print('saved docs/fig/plaza_roads_check.jpg', crop.size)


if __name__ == '__main__':
    main()
