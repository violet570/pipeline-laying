# 06_代码 · 脚本说明

本目录是「燕山大学西校区给水管道铺设规划」项目的全部脚本，从工作区 `scripts/` 原样复制（`viz_25d.py.bak` 已跳过）。
下文按**运行顺序**分成五组：抓数 → 清数 → 广场补测 → 算法 → 出图。

> 运行环境：Python 3.13 + Pillow；Node.js 用于 Overpass / 高德抓取。
> 所有脚本都假定**仓库根目录**为当前工作目录，且 `data/raw`、`data/derived`、`docs/fig` 已存在：
> ```powershell
> $env:PYTHONIOENCODING='utf-8'      # 必设，否则中文输出乱码
> cd <项目根目录>
> python scripts/registry_stats.py
> ```
> 高德 Web 服务 key 走环境变量 `AMAP_KEY`（不设则用脚本内默认值）。

---

## 0. 目录与约定的前提

| 路径 | 用途 |
|---|---|
| `data/raw/` | 抓下来的原始 OSM / 高德数据（**只读**） |
| `data/derived/` | 清洗与计算产物 |
| `data/tiles/` | 瓦片（`campus_sat_z17_full` 110 张 + `campus_road_z17_full` 110 张是全校区主底图） |
| `docs/fig/` | 出图输出 |

坐标系：**全流程统一 WGS-84**。高德瓦片是 GCJ-02，出图时用 `wgs2gcj()` 正解过去；从高德拿到的 GCJ-02 坐标要用 `gcj2wgs()` 反解回来再入库。

---

## 1. 数据抓取（Node.js / 少量 Python）

| 脚本 | 用途 / 关键命令 |
|---|---|
| `fetch_osm.js` | 主抓取：经 Overpass（`overpass.openstreetmap.fr`，备用 `maps.mail.ru`）拉西校区 **buildings / roads / areas / pois / boundary**，写 `data/raw/*.json`。`node scripts/fetch_osm.js` |
| `fetch_full_buildings.js` | 用**更大矩形范围**重抓建筑，补上首次 bbox 裁掉的两百多栋（含燕大西区大食堂、里仁实验楼、图文信息楼）。产物 `data/raw/buildings_full.json` |
| `fetch_verify.js` | 复核用户指出的错标/漏标（两个食堂、圆形广场内三栋、机械厂、里仁实验楼、第四体育场）。产物 `data/raw/verify_2026.json` |
| `fetch_way_ids.js` | 按**固定 way id 列表**带几何取回（只给中心点时用），产物 `data/raw/buildings_extra.json` |
| `crosscheck_ids.js` | 同一个 id 在**两个独立 Overpass 实例**上查，比对 tags。用于识别「某实例返回了别的地区数据」 |
| `validate_ids.js` | **id 污染事故的防线**：逐个 id 回查 Overpass，断言其几何真的落在西校区 bbox 内。产物 `data/derived/id_validation.json`。**批量抓取后必须跑** |
| `fetch_way_ids.js` → `validate_ids.js` | 两步成对使用：先抓后验 |
| `fetch_tiles.js` | 通用瓦片下载器（高德路网 7 / 高德卫星 6 / Esri 影像），产物 `data/tiles/<source>/<z>_<x>_<y>.png` |
| `fetch_z18_measured.py` | 为 11 个影像量测条目抓高德 z18 卫星瓦片，出 10 m 网格复核底图 `04_数据/tiles/crops/<key>_z18_grid.jpg`（说明见该目录 `量测复核说明.md`） |
| `fetch_campus_z17.js` | 专门抓**全校区 z17**：`data/tiles/campus_sat_z17_full/`（110 张 jpg）、`data/tiles/campus_road_z17_full/`（110 张 png），并写 `data/raw/campus_overlay_z17.json` |
| `fetch_amap_bbox.js` | 按 bbox 抓高德瓦片并拼接。`node scripts/fetch_amap_bbox.js <job> <style> <z> <minLon> <minLat> <maxLon> <maxLat>`，style `6`=卫星 / `7`=路网 / `8`=路网+中文注记 |
| `amap_around.js` | 按半径**分页枚举**高德 POI（GCJ-02）。`node scripts/amap_around.js <lonGCJ> <latGCJ> <radius> [keywords] [maxPages]`，产物 `data/derived/amap_around_*.json` |
| `amap_search.js` | 高德 Web 服务关键字检索。`node scripts/amap_search.js "关键词1" "关键词2"` |
| `amap_poi.js` | 免 key 的 `ditu.amap.com` POI 端点探测（备用路线） |
| `amap_roadtile_check.js` | 探测高德矢量底图瓦片里有没有校园内部道路几何 |
| `fetch_official_map.py` | 下载燕山大学官方 3D 校园图 → `data/raw/official_campus_map.jpg` |
| `get_campus_map_image.py` | 从官网页面里提取校园图 URL 的辅助脚本 |
| `crop_amap.py` | 按 WGS-84 bbox 从已抓瓦片裁图。`python scripts/crop_amap.py <out.jpg> <minLon> <minLat> <maxLon> <maxLat> [scale]` |
| `stitch_amap.py` | 把 `fetch_amap_bbox.js` 的结果拼成一张大图。`python scripts/stitch_amap.py <job> <out.jpg> [scale]` |

## 2. 数据清洗与核查

| 脚本 | 用途 / 关键函数 |
|---|---|
| `groups.py` | **唯一的建筑注册表真源**。定义 71 组 / 78 单体：组键、正式楼名、类别、层数、面积、OSM way id、影像量测 bbox。下游全部依赖它，改楼名只改这里 |
| `inventory_buildings.py` | 枚举边界内**所有** OSM 建筑，`classify()` 分类、`ring_area_m2()` 算面积。产物 `buildings_inventory.csv/.md` |
| `inspect_data.py` | 快速查看各 raw json 的要素数量与字段 |
| `explore.py` | 探索性统计（有哪些 `amenity`/`landuse`） |
| `list_named.py` / `query_box.py` | 列有名建筑 / 按 bbox 二次查询 Overpass |
| `verify_targets.py` | `xy()` / `area_m2()`：定位用户指出的错标建筑，输出几何供人工判定 |
| `plaza_segment.py` | 按**屋顶亮度分割**圆形广场内 5 栋楼，输出真实 bbox/中心（早期手工框不对，改用此法） |
| `plaza_threshold_scan.py` | 扫描亮度阈值，确定分割参数 |
| `registration_check.py` | **配准验证**：`iou()` 最大化 OSM footprint 掩膜与卫星屋顶掩膜的 IoU，证明 OSM 与高德影像对齐。产物 `registration_check.txt` |
| `build_distances.py` | 真实距离表：`to_xy()` / `dist_pt_seg()` / `poly_gap()` 算所有楼群两两的质心距与间隙。产物 `distances.csv` / `distances.md` |
| `registry_stats.py` | 打印注册表口径统计（组数、单体数、有几何/待定位、目标数），用于报告里的数字不靠手数 |

## 3. 圆形广场环形路补测（用户手描 → WGS-84）

OSM 里缺圆形广场的环形路，导致广场内三栋学院楼接户距离 150–220 m。这一组脚本把它补进来。

| 脚本 | 用途 |
|---|---|
| `measure_grid.py` | 在 z18 截图上叠 25 px 格网并标注**图像像素坐标**。`python scripts/measure_grid.py <lat0> <lon0> <hw> <hh> <out.jpg> <title> [scale]`，会打印裁图原点 `(ox, oy)` |
| `px2ll.py` | 把 `measure_grid.py` 上读到的像素框换成 WGS-84 bbox。`python scripts/px2ll.py <ox> <oy> "x0,y0,x1,y1" ...` |
| `plaza_grid.py` / `plaza_pin.py` / `plaza_verify.py` / `plaza_extract.py` | 广场区的格网、打点、复核、提取小工具（均为 `px2ll()` + `stitch()` 组合） |
| `plaza_road_from_user.py` | 早期版本：用户在 **712×355 预览图**上描线，经 `preview_to_wgs()` 做「预览 → 裁图 → 整图 → 墨卡托 → lon/lat」四级换算 |
| `retrace_plaza_ring_v4.py` | **当前版本（2026-11-01）**：从高德 z18 路网图 `amap_west.png` 的白色道路像素逐 1° 提取环道中心线，平滑后 72 顶点、首尾闭合，等效半径 120.3 m；四条支路内端重挂到新环最近顶点。产物 `data/derived/plaza_roads_user.json` |
| `retrace_plaza_ring.py` | v2/v3（历史）：圆心 + 145 m 正圆，因比真实环道大约 20% 已废弃；保留用于对照 |
| `plaza_road_trace.py` | v1（历史）：直接在整图像素空间定义 5 条路，R=72 px≈66 m，偏小一半 |
| `snap_plaza_roads.py` | `extend_to_road()` / `seg_dist()`：把每条支路的悬空端点沿自身方向延长，直到撞上真实的 OSM 干道 |
| `connect_plaza_ring.py` | 先把 OSM 路网拆成**连通分量**、只保留最大分量（真正的校园路网），再把 4 条支路端点吸附到**该分量**的顶点上（旧版吸到最近的孤立 `path` 顶点，导致 MST 够不到三栋学院楼） |
| `merge_plaza_roads.py` | 把 `plaza_roads_user.json` 5 条线以 `highway=service, source=user_trace` 合成 way 追加进 `data/raw/roads_with_plaza.json`（幂等：先删旧的合成段）。**并把 `build_bundle_v2.py` 的数据源切到 `roads_with_plaza`** |
| `retrace_plaza_ring_v4.py` → `connect_plaza_ring.py` → `merge_plaza_roads.py` | 这三个按顺序跑，就是「重描环 → 支路吸附 → 进路网」的完整流程 |

## 4. 图算法与方案计算

| 脚本 | 用途 / 关键函数 |
|---|---|
| `build_data.py` | **v1 方案**：清洗 + 建图 + MST 定管径。核心函数 `haversine` `point_in_poly` `seg_dist` `add_node/get_node/add_edge` `find_nearest_edge` `insert_target` `dijkstra` `path_edges` `pick_dn` `solve`。产物 `pipeline_bundle.json` `build_report.txt` `pipes.geojson` `dorms.csv` |
| `build_bundle_v2.py` | **v2 / 当前方案**：以 `groups.py` 为**唯一真源**重建数据包。需求点从「34 栋公寓」扩到「全部已定位建筑群 + 水源」，影像量测条目用 bbox 矩形代理 footprint。函数与 v1 同名（`dijkstra` `path_edges` `pick_dn` `solve` `find` `sfind`）。数据源是 `roads_with_plaza`。产物 `pipeline_bundle.json` `build_report_v2.txt` `pipes_v2.geojson` `targets_v2.csv` |
| `add_service_points.py` | 给每个受水建筑补**接户点**：`dist_pt_seg()` / `poly_edges()` / `xy()` 在整条建筑轮廓上搜索与道路距离最小的一对点（支管 ≥2 m、不穿楼），求出路边接入点（tee）、接户支管长度、立管高度、逐层出水口径。产物 `pipeline_bundle_conn.json` |
| `build_bundle_v2.py` → `add_service_points.py` | **方案计算的标准顺序** |
| `run_build.py` | **一键重建**：在临时目录用 junction 把 `04_数据`/`06_代码` 映射成脚本期望的 `data`/`scripts`，顺序跑 build_bundle → add_service_points → viz_25d → build_planner，并出 `viz_25d.png`。在交付目录直接跑这一条即可 |
| `validate_registry_ids.py` | 离线校验注册表实际使用的 67 个 OSM way id（存在/有 building 标签/在框内/无重复引用），产物 `04_数据/derived/id_validation_registry.json` |
| `check_prim.py` | Prim vs Kruskal 对拍：在同一路网图上重算 45 目标 + 水源的 MST，两者差 <1e-6，与 `stats.mst_length_m` 差 <0.5 m |
| `build_matrix.py` | 生成作业要求的无向图距离矩阵：`04_数据/derived/graph_matrix.txt`（46×46 + 节点表）、`graph_mst_process.txt`（Kruskal/Prim 过程）、`05_图件/管道方案/graph_matrix.js`（同文本包装） |

## 规划台三模式（2026-11-06 改版口径）

模式由用户在左栏**自行选择**，不再由点击次数自动推断。

| 模式 | 输入 | 算法 |
|---|---|---|
| **A · 全校（默认起点）** | 无 | 连接全部 45 个供水目标，起点沿用主数据的默认水源（南主门 / 7 号门）。此模式即主数据那套方案，用于对齐 8,115.9 m / 468.3 万元 |
| **B · 选点排除** | 左栏点建筑编号（可多选） | 被排除的建筑移出方案，剩余建筑重新求全局最短铺设；起点在 5/6/7 号门中重新比选 MST 总长最小的 |
| **C · 自定起点 + 多终点** | 图上点 1 个起点 + 若干终点 | **只铺这些点，不铺全校**：起点吸附路网后作水源，终点（点楼=该楼带用水量；点空地=路网接入点）作为仅有的受水目标跑 MST。还没点终点时不画任何管网 |

两个页面（`planner.html` / `matrix_mst.html`）共用 `pipe_engine.js`，矩阵页默认按当前选择实时计算，
规划台右上角「无向图 / 矩阵演示」会把当前模式、排除编号、起点、接入点带进 hash，新标签页打开即同步。

已知边界：两个目标吸附到同一路网节点时会自动合并成一个节点（否则 Kruskal 完全图出现重复节点、生成树少一条边）。

---

## 5. 出图

| 脚本 | 产物 | 说明 |
|---|---|---|
| `make_figures.py` | `fig1` `fig2` `fig3` | 最早的三张图：全校区 z17 卫星 + 边界、z18 卫星 + OSM 轮廓、MST 方案 2D 预览（按管径着色）。内部 `to_px()` / `draw_poly()` 已做 `wgs2gcj`。**注意：其 `fig3_mst_scheme.png` 是早期「34 栋公寓」口径的原型图（MST 3672 m / 造价 104.2 万元），与当前 45 目标正式方案（8,115.9 m / 468.3 万元）不是同一口径，故交付目录 `05_图件/管道方案/` 未收录该图，正式方案见 `viz_25d.png`。** 如需重出，运行 `python scripts/make_figures.py` |
| `fig_two_source.py` | `fig_two_source_campus.jpg` | **双源合成图**（2816×2652）：底图=高德 z17 卫星拼接（`stitch()`），蓝线=OSM 道路，彩色细轮廓=OSM 建筑，青框=影像量测建筑，黄点=高德 POI。<br>**全项目的坐标映射正解就是这里的 `sx(lon, lat)`**：`wgs2gcj()` → `merc_px()` → 减去 `X0*TILE, Y0*TILE`；整图坐标 = 该结果 + 92 px 抬头 |
| **`fig_user_route.py`** | `fig_user_traced_route.jpg` | **本目录新增脚本**：在 `fig_two_source_campus.jpg` 上叠用户手描的 5 条广场道路（洋红粗线 + 白描边 + 顶点），保留 OSM 道路（蓝）与建筑轮廓，三角区域浅黄填充并标「停车场（非道路）」，重写抬头图例。`P(lon,lat)` 直接调 `fig_two_source.sx()` 再加 `HDR=92`，**不自创比例尺**；末尾打印环形路半径自检。`python scripts/fig_user_route.py` |
| `fig_campus_all.py` | `fig5_campus_all_buildings_z17.jpg` / `fig5b_..._road.jpg` | 全校区所有建筑群标注版（z17 底图 + 路网版） |
| `fig_campus_buildings.py` | `fig4_campus_buildings_z18.jpg` / `fig4b_dorm_satellite_z18.jpg` | z18 高清分区标注图（全校区 / 公寓带） |
| `fig_zones.py` | `fig7_zones_z17.jpg` | 功能分区图：50 组按地理位置分 5 个供水区，标各区汇总 |
| `fig_registry_map.py` / `fig_registration_panels.py` | `fig8_campus_registry_corrected.jpg` / `fig6_registration_panels.jpg` | 注册表更正图 / 配准分块对照面板 |
| `fig_proof.py` / `fig_proof_four.py` | `proof_canteens.jpg` `proof_lab.jpg` `proof_plaza_5.jpg` `proof_four_gallery.jpg` `proof_four_gym.jpg` | 「证据图」：每张只放大一处争议建筑，配卫星底图与轮廓 |
| `fig_verify_circle.py` / `fig_verify_wide.py` / `fig_verify_unnamed.py` | `verify_*.jpg` | 圆形广场 / 更大范围 / 无名建筑的核查图 |
| `fig_plaza_amap.py` / `fig_plaza_roads_check.py` | `plaza_amap_roads.jpg` / `plaza_roads_check.jpg` | 广场区高德路网对照 / 补描环路的叠合检查 |
| `loc_lab.py` / `loc_lab_grid.py` / `loc_liren.py` / `loc_north_gallery.py` / `loc_north_gym.py` / `loc_grid2.py` | `loc_*.jpg` | 定位辅助图：给一个经纬度 + 半宽半高，出一张带格网的局部放大 |
| `pin_fine.py` / `pin_targets.py` | `pin_*.jpg` | 精细打点图（`px2ll()` 往返换算 + 十字准星） |
| `viz_25d.py` | `viz_25d.html` `viz_25d.png` | **2.5D 等轴测方案图**（单文件 HTML + SVG）：`proj()` 等轴测投影、`iso()` 坐标、`S()` 缩放、`esc()` 转义；建筑按层高挤出、画家算法排序、侧面按朝向明暗。数据源 `pipeline_bundle_conn.json` |
| `build_planner.py` + `planner_template.html` + `matrix_template.html` + `pipe_engine.js` | `05_图件/管道方案/planner.html` `matrix_mst.html` | **交互式规划台 + 无向图/矩阵页**。`pipe_engine.js` 是两页共用的求解引擎（沿路网加权最短路 + 完全图 Kruskal + 逐楼上行定流量/管径），口径与 `build_bundle_v2.py` 完全一致（复算 8,116.0 m，主数据 8,115.9 m）。`build_planner.py` 把引擎与 bundle 内联进两个模板，产出**两个单文件页面**（双击可用）。三模式定义见下方「规划台三模式」 |
| `patch_viz_service.py` | （就地改 `viz_25d.py`） | `svc_geometry()`：给 2.5D 图补「接户点 tee + 接户支路 + 立管 + 逐层出水口」。**是打补丁脚本，跑一次即可** |
| `sync_plan_doc.py` | （更新方案文档） | 把方案文档里的统计数字同步成当前 bundle 的真实值 |
| `extract_docx.py` | `.txt` | 通用小工具：从 .docx 抽出段落 + 表格 |

---

## 交付目录中 out/ 的说明

`<交付根>/out/` 不是本目录脚本的产物，而是另一路核对工作时留下的**自检脚本**，不影响交付内容：

| 文件 | 是什么 |
|---|---|
| `out/_verify.py` | 从 `pipeline_bundle_conn.json` 重建路网图、复算 MST/接户点，用来交叉核对 `stats` 里的数字 |
| `out/_snap.py` | 复算建筑接路点（snap）与接户支管长度 |
| `out/_njs/smoke.js` | Node.js 端的路网 / Dijkstra / MST 冒烟测试，与 `build_bundle_v2.py` 口径对齐 |

它们都以 `B = r'C:\Users\ROD\Desktop\管道铺设'` 做硬编码路径，属于**一次性核对脚本**，不是可复现流水线的一部分。
若不需要，可整目录删除；不影响 06_代码 里的任何脚本运行。

---

## 最短可复现路径

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:AMAP_KEY='ed947ef3bd8ceef0f7a10b8741102dec'

# 1) 抓数（只需一次）
node scripts/fetch_osm.js
node scripts/fetch_full_buildings.js
node scripts/fetch_campus_z17.js
python scripts/fetch_official_map.py
node scripts/validate_ids.js                     # 必跑：id 污染断言

# 2) 注册表口径统计
python scripts/registry_stats.py
python scripts/registration_check.py             # 配准自检

# 3) 广场环形路补测 → 进路网
python scripts/plaza_road_trace.py
python scripts/connect_plaza_ring.py
python scripts/merge_plaza_roads.py

# 4) 方案计算
python scripts/build_bundle_v2.py
python scripts/add_service_points.py

# 5) 出图
python scripts/fig_two_source.py
python scripts/fig_user_route.py                 # 本目录新增：用户标注路线合成图
python scripts/fig_campus_all.py
python scripts/fig_campus_buildings.py
python scripts/fig_zones.py
python scripts/viz_25d.py
```

## 注意事项

- `merge_plaza_roads.py` 会**改写** `scripts/build_bundle_v2.py`，把数据源从 `roads.json` 换成 `roads_with_plaza.json`。这一点是幂等的，但要知道它会动源码。
- `patch_viz_service.py` 同理，会改写 `viz_25d.py`。二者都是「跑一次」的补丁脚本，不要反复跑。
- `data/derived/plaza_roads_user.json` 里的 5 条路**不是 OSM 原始数据**，标签为 `source=user_trace`，在报告与提示词里必须如此声明。
- `id_validation.json` 记录的是「每个 way id 是否真的落在西校区」——这是 2026-10-28 那次事故（5 个 id 实为美国北达科他州道路）留下的防线，不要删。
