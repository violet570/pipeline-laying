# -*- coding: utf-8 -*-
"""生成可行性验证图：
1) docs/fig/fig1_campus_satellite_z17.png   高德 z17 卫星瓦片拼接（全西校区）+ 校园边界
2) docs/fig/fig2_dorm_satellite_overlay.png 高德 z18 卫星 + OSM 建筑/道路轮廓（WGS84→GCJ-02）
3) docs/fig/fig3_mst_scheme.png             已跑通的 MST 管道方案 2D 预览（管线按管径着色）
"""
import json, math, os, re
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')
DER = os.path.join(ROOT, 'data', 'derived')
TILES = os.path.join(ROOT, 'data', 'tiles')
FIG = os.path.join(ROOT, 'docs', 'fig')
os.makedirs(FIG, exist_ok=True)

FONT = 'C:/Windows/Fonts/msyh.ttc'
FONTB = 'C:/Windows/Fonts/msyhbd.ttc'
def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)

# ---------------- 坐标转换 ----------------
A = 6378245.0
EE = 0.00669342162296594323

def _tlat(x, y):
    r = (-100.0 + 2.0*x + 3.0*y + 0.2*y*y + 0.1*x*y + 0.2*math.sqrt(abs(x)))
    r += (20.0*math.sin(6.0*x*math.pi) + 20.0*math.sin(2.0*x*math.pi)) * 2.0/3.0
    r += (20.0*math.sin(y*math.pi) + 40.0*math.sin(y/3.0*math.pi)) * 2.0/3.0
    r += (160.0*math.sin(y/12.0*math.pi) + 320*math.sin(y*math.pi/30.0)) * 2.0/3.0
    return r

def _tlon(x, y):
    r = (300.0 + x + 2.0*y + 0.1*x*x + 0.1*x*y + 0.1*math.sqrt(abs(x)))
    r += (20.0*math.sin(6.0*x*math.pi) + 20.0*math.sin(2.0*x*math.pi)) * 2.0/3.0
    r += (20.0*math.sin(x*math.pi) + 40.0*math.sin(x/3.0*math.pi)) * 2.0/3.0
    r += (150.0*math.sin(x/12.0*math.pi) + 300.0*math.sin(x/30.0*math.pi)) * 2.0/3.0
    return r

def wgs2gcj(lon, lat):
    dlat, dlon = _tlat(lon-105.0, lat-35.0), _tlon(lon-105.0, lat-35.0)
    rad = lat / 180.0 * math.pi
    magic = math.sin(rad)
    magic = 1 - EE*magic*magic
    sm = math.sqrt(magic)
    dlat = (dlat*180.0) / ((A*(1-EE)) / (magic*sm) * math.pi)
    dlon = (dlon*180.0) / (A/sm*math.cos(rad)*math.pi)
    return lon+dlon, lat+dlat

def _load(name):
    with open(os.path.join(RAW, name), encoding='utf-8') as f:
        return json.load(f)

# 校园边界（取经度较小的西校区）
bnd = _load('campus_boundary.json')['elements']
west = min(bnd, key=lambda e: (e['bounds']['minlon'] + e['bounds']['maxlon']) / 2)
WEST_POLY = [(p['lon'], p['lat']) for p in west['geometry']]

def in_poly(lon, lat, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]; xj, yj = poly[j]
        if (yi > lat) != (yj > lat) and lon < (xj-xi)*(lat-yi)/(yj-yi)+xi:
            inside = not inside
        j = i
    return inside

# ---------------- 瓦片拼接 ----------------
def stitch(job):
    files = os.listdir(os.path.join(TILES, job))
    z = None; pos = {}
    for fn in files:
        m = re.match(r'(\d+)_(\d+)_(\d+)\.(jpg|png)$', fn)
        if not m:
            continue
        z, x, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        pos[(x, y)] = os.path.join(TILES, job, fn)
    xs = sorted({p[0] for p in pos}); ys = sorted({p[1] for p in pos})
    x0, y0 = xs[0], ys[0]
    nx, ny = xs[-1]-x0+1, ys[-1]-y0+1
    img = Image.new('RGB', (nx*256, ny*256), (30, 30, 30))
    for (x, y), fp in pos.items():
        t = Image.open(fp).convert('RGB')
        img.paste(t, ((x-x0)*256, (y-y0)*256))
    return img, z, x0, y0

def merc_px(lon, lat, z):
    n = 256.0 * (2 ** z)
    X = (lon + 180.0) / 360.0 * n
    s = math.sin(lat * math.pi / 180.0)
    Y = (0.5 - math.log((1+s)/(1-s)) / (4*math.pi)) * n
    return X, Y

def to_px(lon, lat, z, x0, y0):
    X, Y = merc_px(*wgs2gcj(lon, lat), z)
    return X - x0*256, Y - y0*256

# 图 1：全校区卫星
img, z, x0, y0 = stitch('campus_sat_z17')
d = ImageDraw.Draw(img)
pts = [to_px(lon, lat, z, x0, y0) for lon, lat in WEST_POLY]
d.line(pts + [pts[0]], fill=(255, 60, 60), width=5)
d.rectangle([0, 0, img.width, 74], fill=(0, 0, 0))
d.text((26, 16), '燕山大学西校区 高德卫星影像 z17（免 key 栅格瓦片拼接）+ OSM 校园边界（红线）',
       font=font(40, True), fill=(255, 255, 255))
d.text((26, img.height-46), '底图：高德地图（仅作对照/署名）｜边界：OpenStreetMap © contributors (ODbL)',
       font=font(24), fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0))
img = img.resize((2000, int(img.height*2000/img.width)), Image.LANCZOS)
img.save(os.path.join(FIG, 'fig1_campus_satellite_z17.jpg'), quality=88)
print('fig1', img.size)

# 图 2：宿舍区卫星 + OSM 轮廓叠加（裁剪到宿舍区，放大更清楚）
img, z, x0, y0 = stitch('dorms_sat_z18')
# 裁剪窗口（经纬度）
CLON0, CLON1, CLAT0, CLAT1 = 119.5050, 119.5230, 39.9010, 39.9130
tl = to_px(CLON0, CLAT1, z, x0, y0)   # 左上
br = to_px(CLON1, CLAT0, z, x0, y0)   # 右下
cx0, cy0 = max(0, int(tl[0])), max(0, int(tl[1]))
cx1, cy1 = min(img.width, int(br[0])), min(img.height, int(br[1]))
img = img.crop((cx0, cy0, cx1, cy1))
ox, oy = cx0, cy0

def to_px_c(lon, lat):
    px, py = to_px(lon, lat, z, x0, y0)
    return px - ox, py - oy

d = ImageDraw.Draw(img)

def draw_poly(geom, color, w):
    p = [to_px_c(g['lon'], g['lat']) for g in geom]
    if len(p) >= 2:
        d.line(p + [p[0]], fill=color, width=w)


buildings = _load('buildings.json')['elements']
dorm_names = []
drawn = 0
for el in buildings:
    g = [p for p in (el.get('geometry') or []) if p] if 'geometry' in el else []
    t = el.get('tags') or {}
    if len(g) < 3:
        continue
    lat0 = sum(p['lat'] for p in g)/len(g); lon0 = sum(p['lon'] for p in g)/len(g)
    if not (CLON0-0.002 <= lon0 <= CLON1+0.002 and CLAT0-0.002 <= lat0 <= CLAT1+0.002):
        continue
    name = t.get('name') or ''
    is_dorm = bool(re.match(r'^\d+\s*-\s*[AB]', name)) or t.get('building') == 'dormitory'
    draw_poly(g, (255, 80, 80) if is_dorm else (0, 230, 255), 4 if is_dorm else 2)
    drawn += 1
    if is_dorm:
        px, py = to_px_c(lon0, lat0)
        dorm_names.append((name, px, py))

for name, px, py in dorm_names:
    d.text((px+5, py+5), name, font=font(26, True), fill=(255, 240, 60),
           stroke_width=3, stroke_fill=(0, 0, 0))
print('fig2 buildings drawn', drawn, 'dorms', len(dorm_names))
d.rectangle([0, 0, img.width, 66], fill=(0, 0, 0))
d.text((24, 16), '宿舍区 高德卫星 z18 + OSM 建筑轮廓（WGS-84→GCJ-02 校正后叠加；红=学生公寓 青=其他建筑）',
       font=font(30, True), fill=(255, 255, 255))
d.text((24, img.height-44), '底图：高德地图卫星瓦片（仅作对照/署名）｜轮廓：OpenStreetMap © contributors (ODbL)',
       font=font(22), fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0))
if img.width > 2400:
    img = img.resize((2400, int(img.height*2400/img.width)), Image.LANCZOS)
img.save(os.path.join(FIG, 'fig2_dorm_satellite_overlay.jpg'), quality=88)
print('fig2', img.size)

# ---------------- 图 3：MST 方案 2D 预览 ----------------
with open(os.path.join(DER, 'pipeline_bundle.json'), encoding='utf-8') as f:
    B = json.load(f)
LAT0, LON0 = B['meta']['origin']
KLAT = B['meta']['m_per_deg_lat']; KLON = B['meta']['m_per_deg_lon']
def xy(lat, lon):
    return ((lon-LON0)*KLON, -(lat-LAT0)*KLAT)

W, H = 2400, 1800
mlat = [p['lat'] for p in B['dorms']] + [b['lat'] for b in B['buildings']]
mlon = [p['lon'] for p in B['dorms']] + [b['lon'] for b in B['buildings']]
xs = [xy(la, lo)[0] for la, lo in zip(mlat, mlon)]
ys = [xy(la, lo)[1] for la, lo in zip(mlat, mlon)]
x0m, x1m = min(xs), max(xs); y0m, y1m = min(ys), max(ys)
pad = 60; scale = min((W-2*pad)/(x1m-x0m), (H-2*pad)/(y1m-y0m))
cx = (W - (x1m-x0m)*scale)/2; cy = (H - (y1m-y0m)*scale)/2
def sx(lat, lon):
    x, y = xy(lat, lon)
    return (cx + (x-x0m)*scale, cy + (y-y0m)*scale)

img = Image.new('RGB', (W, H), (247, 249, 251))
d = ImageDraw.Draw(img)

# 区域内水面/绿地底色
for a in B.get('areas', []):
    if a['type'] in ('water', 'wood', 'grass', 'forest', 'pitch', 'park'):
        p = [sx(la, lo) for lo, la in a['pts']]
        col = {'water': (200, 226, 245), 'pitch': (214, 236, 214), 'wood': (203, 231, 203),
               'grass': (219, 240, 219), 'forest': (199, 226, 199), 'park': (214, 238, 214)}[a['type']]
        d.polygon(p, fill=col)

# 道路
for r in B['roads']:
    p = [sx(la, lo) for lo, la in r['pts']]
    if len(p) > 1:
        d.line(p, fill=(205, 208, 212), width=8, joint='curve')
        d.line(p, fill=(233, 235, 238), width=4, joint='curve')

# 建筑
for b in B['buildings']:
    fp = b.get('footprint') or []
    if len(fp) >= 3:
        p = [sx(la, lo) for lo, la in fp]
        d.polygon(p, fill=(206, 214, 224), outline=(150, 165, 182), width=2)

# 管道：按管径着色/线宽
DN_COLOR = {40: (255, 196, 87), 50: (255, 176, 80), 65: (246, 152, 66), 80: (239, 128, 60),
            100: (229, 102, 74), 125: (214, 84, 104), 150: (192, 74, 131), 200: (132, 76, 173),
            250: (86, 92, 199), 300: (52, 114, 216), 350: (26, 156, 219)}
def dn_w(dn):
    return max(3, min(14, int(round(3 + (dn - 40) * 11.0 / 310.0))))
for p in B['pipes']:
    lon0p, lat0p = p['a']   # build_data.py 输出 [lon, lat]
    lon1p, lat1p = p['b']
    pa, pb = sx(lat0p, lon0p), sx(lat1p, lon1p)
    if p['length'] < 0.5:
        continue
    w = dn_w(p['dn'])
    d.line([pa, pb], fill=(255, 255, 255), width=w+3)
    d.line([pa, pb], fill=DN_COLOR.get(p['dn'], (80, 80, 80)), width=w)

# 水源
sr = B['meta']['source']
sp = sx(sr['lat'], sr['lon'])
r = 16
d.polygon([(sp[0], sp[1]-r), (sp[0]+r*0.5, sp[1]), (sp[0], sp[1]+r), (sp[0]-r*0.5, sp[1])],
          fill=(220, 40, 40), outline=(120, 0, 0), width=2)
d.text((sp[0]+20, sp[1]-38), '水源（假设：南主门市政接入）', font=font(26, True),
       fill=(200, 30, 30), stroke_width=2, stroke_fill=(255, 255, 255))

# 公寓标注
for dm in B['dorms']:
    px, py = sx(dm['lat'], dm['lon'])
    d.ellipse([px-4, py-4, px+4, py+4], fill=(30, 60, 110))
    d.text((px+7, py+3), dm['name'], font=font(20, True), fill=(20, 40, 80),
           stroke_width=2, stroke_fill=(255, 255, 255))

# 标题与统计
d.rectangle([0, 0, W, 96], fill=(21, 44, 76))
d.text((28, 18), '燕山大学西校区给水管道方案 —— 沿路网最小生成树（MST）', font=font(40, True),
       fill=(255, 255, 255))
st = B['stats']
line1 = (f"34 栋公寓 · MST 加权长 {st['mst_length_m']:.0f} m · 管道实长 {st['pipe_length_m']:.0f} m · "
         f"DN40–DN{st['main_dn']} · 设计流量 {st['q_total_ls']} L/s · 估算造价 {st['cost_est_yuan']/10000:.1f} 万元")
line2 = (f"对照：直线 MST {st['straight_mst_length_m']:.0f} m ｜ 星形供水 {st['star_length_m']:.0f} m ｜ "
         f"总用水量 {st['total_demand_m3d']} m³/d ｜ 分支点 {st['n_branch']} 个")
d.text((28, 106), line1, font=font(26), fill=(30, 55, 90))
d.text((28, 142), line2, font=font(26), fill=(30, 55, 90))

# 图例
lx, ly = W-470, H-210
d.rectangle([lx, ly, W-24, H-24], fill=(255, 255, 255), outline=(160, 170, 185), width=2)
d.text((lx+14, ly+8), '管径图例 (DN)', font=font(24, True), fill=(20, 20, 20))
for i, dn in enumerate([40, 80, 125, 200, 250, 350]):
    yy = ly + 48 + i*27
    d.line([(lx+16, yy+8), (lx+96, yy+8)], fill=DN_COLOR[dn], width=dn_w(dn))
    d.text((lx+110, yy-2), f'DN{dn}', font=font(22), fill=(30, 30, 30))
d.line([(lx+16, ly+48+6*27+8), (lx+96, ly+48+6*27+8)], fill=(233, 235, 238), width=4)
d.text((lx+110, ly+48+6*27), '道路', font=font(22), fill=(30, 30, 30))
d.text((28, H-34), '底图数据：OpenStreetMap © contributors (ODbL) ｜ 坐标：WGS-84 ｜ 影像：高德地图（仅作对照）',
       font=font(20), fill=(110, 120, 130))
img.save(os.path.join(FIG, 'fig3_mst_scheme.png'))
print('fig3', img.size)
print('done')
