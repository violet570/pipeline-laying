# -*- coding: utf-8 -*-
"""Convert image-pixel boxes (from measure_grid.py) to WGS-84 lat/lon bboxes.

usage: python scripts/px2ll.py <ox> <oy> "x0,y0,x1,y1" ["x0,y0,x1,y1" ...]
"""
import math
import sys

Z = 18
N = 2.0 ** Z * 256.0


def px2gcj(X, Y):
    lon = X / N * 360.0 - 180.0
    gy = math.pi * (1.0 - 2.0 * Y / N)
    lat = math.degrees(math.atan(math.sinh(gy)))
    return lon, lat


def gcj2wgs(lon, lat):
    a = 6378245.0
    ee = 0.00669342162296594323

    def tlat(x, y):
        r = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
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
    magic = 1 - ee * math.sin(rad) ** 2
    sq = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sq) * math.pi)
    dlon = (dlon * 180.0) / (a / sq * math.cos(rad) * math.pi)
    return lon - dlon, lat - dlat


def main():
    ox, oy = int(sys.argv[1]), int(sys.argv[2])
    for spec in sys.argv[3:]:
        x0, y0, x1, y1 = [float(v) for v in spec.split(',')]
        X0, X1 = ox + x0, ox + x1
        Y0, Y1 = oy + y0, oy + y1
        lon0, lat0 = px2gcj(X0, Y1)   # bottom-left
        lon1, lat1 = px2gcj(X1, Y0)   # top-right
        lon0, lat0 = gcj2wgs(lon0, lat0)
        lon1, lat1 = gcj2wgs(lon1, lat1)
        w = (x1 - x0) * 0.458
        h = (y1 - y0) * 0.458
        print('%s -> bbox=[%.6f, %.6f, %.6f, %.6f]  center=(%.6f, %.6f)  %.0f x %.0f m  ~%.0f m2'
              % (spec, lon0, lat0, lon1, lat1, (lon0 + lon1) / 2, (lat0 + lat1) / 2,
                 w, h, w * h))


if __name__ == '__main__':
    main()
