# 燕山大学西校区 Google 地图覆盖情况验证报告

> **调研问题**：能否仅靠 Google 地图，拿到"按学生公寓楼逐栋定位"的燕山大学西校区真实分布图，用于"管道铺设"算法设计课程项目的作图？
>
> **调研时间**：2026-10-26　**执行**：google-verifier（DeepSeek Harness 团队）
> **方法**：web_search / web_fetch 抓取公开网页；第三方地图站点、行业媒体；用 OSM Overpass API 取权威矢量数据做对照。
>
> **⚠️ 首要限制（影响证据等级）**：本次调研所在环境**无法访问 Google 全系域名**（`google.com`、`maps.google.com`、`maps.google.cn`、`support.google.com` 全部 `fetch failed`），也打不开 Google Earth 相关页面。因此**无法直接打开 Google 地图/Google Earth 做截图级验证**；Q1、Q2 的结论由"二手公开来源 + 第三方 Google 底图站点 + OSM 官方数据"交叉得出，下文逐条标注 **事实 / 合理推断 / 待验证**。

---

## 一、结论摘要

**总评级：B 级 —— "只有关键地标 + 卫星影像可用，不能逐栋标注"。**

更准确地说要分两层：

| 用法 | 能否支撑"按公寓楼画管道图" | 评级 |
|---|---|---|
| 只用 Google 地图的 **POI/地名标注**（打开地图看到的点位） | **不能**。没有逐栋公寓标注，只有校区级/少量地标 | **C** |
| 用 Google **卫星影像**当底图，人工描出楼栋轮廓 | **技术上能**（但费工，大陆需代理） | **B～A-（人工工作量换来的 A）** |
| 用 Google **街景**核对 | **不能**，中国大陆基本无街景 | **C** |

四条核心结论：

1. **Google 地图的标注层拿不到西校区逐栋学生公寓。** 本文**未找到直接证据**（既没有任何页面证明"有逐栋标注"，也没有页面明确说"没有"——因为 Google 页面全部打不开）。但间接证据链一致：Google 在中国大陆无测绘资质、不做本地采集，对华地图数据长期由高德供应，且"很多新路、小店都没有"（[泰伯网](https://www.taibo.cn/p/67220)、[壹云科技](https://www.1yun.vip/newdetails/798.html)）；本文找到的所有第三方页面提到燕大时都只到"主校区/校区"这一级（[uniRank](https://www.unirank.org/cn/uni/yanshan-university/map/index.htm)）。→ **合理推断：Google 地图上只能看到"燕山大学（西校区）"这个地点/校区范围，看不到 1-A…13-B2 这类逐栋公寓名称。**（待验证：用能上 Google 的设备搜一次即可确认）
2. **Google 卫星影像在该区域是存在的**：第三方站点有《燕山大学地图-卫星地图》页，页头写明"Google卫星地图"（[地球在线](https://www.earthol.com/fun-2-school-ysu.html)）；bigemap 也有《燕山大学西校区 卫星地图》索引页（标题可证，正文因该站 charset 头错误无法读取）；行业文章认为 Google 卫星影像"数据质量和现势性还是比较好"（[泰伯网](https://www.taibo.cn/p/67220)）；Google Earth 全球大部分区域可达 0.3 m 级（[网易·测绘之家](https://m.163.com/dy/article/HTSR79SK05319UN7.html)）。→ **合理推断：卫星图上能看清校园建筑，可手工逐栋描轮廓**；该校区具体分辨率和拍摄年份**未验证**。
3. **坐标系是本题的关键**：国际版 `google.com/maps` 的**矢量/道路图层用 GCJ-02（火星坐标）**，**卫星影像图层用 WGS-84**，两层互相错位数百米（[Xataka Móvil](https://www.xatakamovil.com/movil-y-sociedad/mapas-china-no-como-resto-mundo-eso-vemos-carreteras-lugares-donde-no-corresponde)，转引 Wikipedia "GPS shift problem" 等）。→ **Google 卫星图可以直接叠 OSM 建筑轮廓（同为 WGS-84），但 Google 自己的道路/POI 坐标不能当基准。**
4. **街景基本无覆盖**：Google 街景在中国大陆只有极少数特例（2013 年成都大熊猫繁育研究基地、北京尤伦斯当代艺术中心、成都金沙遗址博物馆，见维基百科《Google街景服务》与 [pconline 报道](https://pcedu.pconline.com.cn/344/3442772.html)），没有城市级覆盖。→ **合理推断：秦皇岛/燕大校园无 Google 街景。**

**对你作业的直接答复**：**仅靠 Google 地图（点位标注）不能**支撑"按公寓楼位置绘制管道铺设图"；**"Google 卫星图 + 手工描楼 + OSM 坐标校对"技术上可行但性价比低**（大陆要代理、要装桌面版）。**推荐改用 OSM（已有逐栋楼轮廓和中文楼名，WGS-84 直接可用）+ 学校官方校园地图/校园 VR + 实地核对。**

---

## 二、证据表

| # | 来源 | 看到了什么（原文/事实） | 对本题的意义 | 类型 | 可信度 |
|---|---|---|---|---|---|
| 1 | [uniRank·燕山大学地图页](https://www.unirank.org/cn/uni/yanshan-university/map/index.htm) | 原文："uniRank features below the Google map of Yanshan University's main campus location"、"Google Satellite View of Yanshan University's main campus location"、"Google Street View … if available"；地址 "438 Hebei Street West Section, Haigang, Qinhuangdao 066004" | 第三方站点认为 Google 有燕大"主校区"地图/卫星图/（可能的）街景；但全文**只有校区级信息，没有任何公寓名** | 事实（页面原文） | 中（第三方，非 Google 官方） |
| 2 | [泰伯网 2021-01-13《谷歌地图中国服务关闭》](https://www.taibo.cn/p/67220) | "谷歌地图中国区的地图数据由高德地图供应"（2006/2007 起）；2021-01 起 `ditu.google.cn` 302 跳转 `google.com`；"maps.google.com 也同样提供了中国的数据，但后者数据不符合当前中国的政策……同时后者也不包含政府要求的'坐标偏移'"；"在卫星影像方面谷歌的数据质量和现势性还是比较好"；谷歌无中国测绘资质 | ① Google 中国数据靠高德，本地采集能力弱 → POI 稀疏合理；② 国际版不含"政府要求的坐标偏移" → 与"卫星 WGS-84"一致；③ 卫星影像质量被行业认可 | 事实（行业媒体引述） | 中高 |
| 3 | [壹云科技 2026-06-16](https://www.1yun.vip/newdetails/798.html) | Google 服务大陆连不上；Google 用世界标准坐标、国内用火星坐标，"定位直接偏出去一两百米到五百米"；谷歌无法在国内实地采集道路/商铺/公交数据，"地图上很多新路、小店都没有"；即使翻墙"顶多能勉强看一眼静态的地图画面" | 直接支持"Google 中国 POI 不全"，并说明大陆可用性极差 | 事实（技术自媒体，描述合理） | 中低 |
| 4 | [Xataka Móvil 2025-06-17](https://www.xatakamovil.com/movil-y-sociedad/mapas-china-no-como-resto-mundo-eso-vemos-carreteras-lugares-donde-no-corresponde) | "En la web google.cn/maps … se utilizaba el sistema GCJ-02 tanto en la vista predeterminada del mapa como en la imagen por satélite … en el resto del mundo (google.com/maps) se emplea el sistema GCJ-02 para el mapa y el sistema WGS-84 para las imágenes por satélite, lo que provoca el problema"；"la variación no es siempre la misma"；文内转引 Wikipedia「Restrictions on geographic data in China#GPS_shift_problem」、Service Objects 博客、Medium | **Q3 的核心证据**：google.com/maps 矢量=GCJ-02、卫星=WGS-84，两层错位；错位量不是固定值 | 事实（二手技术媒体，转引权威来源） | 中 |
| 5 | [网易·测绘之家 2023-02-18《为什么国内地图的卫星影像达不到谷歌地图的分辨率？》](https://m.163.com/dy/article/HTSR79SK05319UN7.html) | 引自然资源部 2023 年第 22 条："表现地为我国境内的遥感影像，地面分辨率不得优于 0.5 米"；"Google earth 在全球大部分区域都可以做到 0.3m 分辨率，采购的数据大部分来自 DigitalGlobe"；列出 WorldView-3 0.31 m、WorldView-4 0.21 m 等 | 说明 Google 卫星影像**原则上比国内平台更清晰**（国内被 0.5 m 政策封顶）；但属通用论述，未针对秦皇岛 | 事实（自媒体技术分析）+ 通用 | 中 |
| 6 | [地球在线《燕山大学地图-卫星地图》](https://www.earthol.com/fun-2-school-ysu.html) | 页面标题"燕山大学地图-卫星地图"，页头标注"Google卫星地图"，正文含燕大简介 | 证明**存在第三方基于 Google 卫星瓦片的燕大校园卫星视图**（说明该处 Google 影像可获取） | 事实（页面标题/页头） | 中 |
| 7 | Bigemap 索引页：[city-61261](http://www.bigemap.net/city-61261.html)、[city-44822](http://www.bigemap.net/city-44822.html)、[city-40218](http://www.bigemap.net/city-40218.html)、[city-48414](http://www.bigemap.net/city-48414.html) | 搜索索引标题：《BIGEMAP在线地图浏览»燕山大学西校区 卫星地图》《…»海港区燕山大学 卫星地图》《…»燕山大学 卫星地图》《…»燕山大学东校区 卫星地图》 | 第三方 Google 影像浏览站为"燕山大学西校区"单独建了卫星地图页 | 事实（标题级；正文因 `charset "uft-8"` 头错误不可读） | 中低 |
| 8 | 维基百科《Google街景服务》<https://zh.wikipedia.org/zh-hk/Google%E8%A1%97%E6%99%AF%E6%9C%8D%E5%8A%A1> + [pconline](https://pcedu.pconline.com.cn/344/3442772.html) | "2013年8月，Google街景首次進入中國大陸……四川成都大熊貓繁育研究基地的街景，此外Google街景還增加了北京的尤伦斯当代艺术中心街景以及成都金沙遗址博物馆的街景" | 中国大陆街景只有极少数特例 → 秦皇岛校园无街景（推断） | 事实（百科条目，内容为二手） | 中高 |
| 9 | 城市吧 city8（**百度底图，非 Google**）[《燕山大学西校区学生公寓13A》](https://qinhuangdao.city8.com/house/8bb79481jo07ba58da)、[《燕大西区公寓1-B号楼》](https://qinhuangdao.city8.com/house/8bbc2o81jj83bcc20c) | 有逐栋 POI：名称、地址"河北省秦皇岛市海港区西环南路181之4号燕山大学西校区"、坐标 39.917575,119.522616（百度系坐标） | **反证参照**：国内图商确实有逐栋宿舍数据；但这是百度系数据，**不能证明 Google 有** | 事实（页面存在） | 中高 |
| 10 | OSM Overpass API（`overpass.openstreetmap.fr`，数据时间戳 2026-08-10） | 西校区 bbox 内实测存在逐栋命名宿舍 `building=dormitory`：1-A/1-B/2-A/2-B/3-A/3-B/4-A/4-B/5-A/5-B/6-A/6-B/7-A/7-B/8-A/8-B/9-A/9-B/10-A/10-B/11-A/11-B/12-A1/12-A2/12-B1/12-B2/13-A1/13-A2/13-B1/13-B2（共 30 栋），建筑轮廓完整，另有"西校区第1~13组团"landuse | **OSM 已经具备"按公寓楼作图"所需的全部要素**，可直接作为 Google 方案的替代/校对基准 | 事实（API 返回） | 高 |
| 11 | [燕山大学国际教育学院 Campus maps](https://ies.ysu.edu.cn/en/About_us/Campus_maps.htm) | 学校官网"校园地图"页，含校园地图图片，并链接官方手绘地图 `http://map.ysu.edu.cn/index.html` 与校园 VR `https://720yun.com/t/3cbj5phaea6?scene_id=10952137` | 官方权威平面图存在（本次 `map.ysu.edu.cn`、`720yun.com` 直接抓取失败，需用户自己浏览器打开） | 事实（官网页面） | 高 |
| 12 | crawlora 博客（标题级）<https://crawlora.net/blog/china-google-maps-category-mix-2026> | 标题："What Google Maps Actually Sees in China: Real Businesses, Not Landmarks"（正文被截断，只能取标题） | 旁证：Google 地图在中国的 POI 结构以"商业点位"为主、不以地标/建筑为主 | 事实（标题级）→ 含义待验证 | 低 |
| 13 | 本次直接验证尝试（多组 URL） | `google.com/maps`、`maps.google.com`、`maps.google.cn`、`support.google.com`、`earth.google.com` 等均 `fetch failed`；`bigemap.net` 返回 `Error: unsupported charset "uft-8"`（服务器头拼写错误）；`map.ysu.edu.cn` 抓取失败；`720yun.com` 跨域重定向失败；微信文章需验证码 | 说明"直接证据"为何缺失：不是没找，是网络层拿不到 | 事实 | 高 |

---

## 三、分问题详细说明

### Q1. Google 地图上燕山大学西校区是否有各学生公寓楼的 POI/标注？

**直接结论：未找到直接证据。**（Google 全系域名在本环境不可达，无法打开 place 页面或评论区页面核对。）

**间接证据（全部指向"没有逐栋标注"）：**

1. **数据来源决定**：Google 中国区地图数据长期由高德供应（泰伯网，见证据 2）；Google 无中国测绘资质、无实地采集队伍，POI 依赖第三方数据与用户贡献。高德虽有楼栋级数据，但授权给 Google 时通常只到 POI 级，**宿舍楼这类"校园内部建筑"通常不在 Google 的 POI 集合里**（合理推断）。
2. **完整性差**：壹云科技明确指出 Google 中国区"很多新路、小店都没有"，且大陆访问极不稳定（证据 3）。
3. **第三方页面只到校区级**：uniRank 只给出"main campus location"+Google 地图/卫星图/街景入口，全文没有一个公寓名（证据 1）。
4. **对比参照**：城市吧（百度底图）能列出《燕山大学西校区学生公寓13A》这种逐栋 POI（证据 9）——说明"逐栋数据"确实存在，但它在国内图商手里；**这恰好反衬 Google 侧数据更薄**。
5. **与你（用户）用 Codex 查到的观感一致**：只有少数关键地点、没有实体/建筑级标注。

**判断分级：**
- 事实：Google 页面无法在本环境打开（证据 13）。
- 合理推断（置信度较高）：Google 地图能看到"燕山大学（西校区）"这个地点、校园范围，**看不到 1-A…13-B2 逐栋公寓标注**；最多有个别用户随手加的地标，不成体系。
- 待验证（用户 30 秒可做）：用能访问 Google 的设备在 `google.com/maps` 搜索框输入"燕山大学西校区"，缩放到 1:2000 看南侧 13 个宿舍组团是否有文字标注。若只有少数点 → 本报告结论成立。

### Q2. Google 卫星影像覆盖情况 / 能否看清建筑 / 是否有街景？

- **影像存在**（事实）：第三方站点为燕大做了"Google 卫星地图"页面（证据 6）；bigemap 为"燕山大学西校区"建了卫星地图索引页（证据 7）。说明该区域在 Google 卫星瓦片覆盖范围内。
- **清晰度**（合理推断）：Google Earth 全球大部分区域可达 0.3 m 级（采购 DigitalGlobe/WorldView 数据，证据 5），城市建成区通常 0.3–0.5 m。0.5 m 分辨率下，一栋 60 m×20 m 的宿舍楼在图上约 120×40 像素，**描轮廓完全够用**；楼间道路、广场、体育场清晰可辨。
- **拍摄年份/是否最新**（未验证）：没有该校区影像日期的一手信息。Google Earth 桌面版有"历史影像（Historical Imagery）"滑块，可自行挑最清晰的一期——**这是你复核时最该用的功能**。
- **分辨率上限的证据边界**：证据 5 是通用论述（全国/全球级），不能证明秦皇岛这一块的影像一定高分辨率；需上机确认（见 Q5 步骤）。
- **街景**（推断）：中国大陆街景仅 2013 年少数特例地点，无城市级覆盖（证据 8），**秦皇岛校园无 Google 街景**。想用街景核对楼栋外观，国内只能用百度/高德的街景（同样有覆盖不全问题）。

### Q3. GCJ-02 偏移对"Google 卫星图 + OSM 轮廓叠加"的影响

**结论：可以叠加，但只认卫星图层；Google 的矢量/POI 坐标不能当基准。**

- **证据**（证据 4，原文）：旧版 `google.cn/maps` 的**地图视图和卫星影像都用 GCJ-02**；而 `google.com/maps`（国际版）则"**地图用 GCJ-02、卫星影像用 WGS-84**"，因此两者之间出现错位；且"偏移量并非总是相同"（`la variación no es siempre la misma`）。
- **泰伯网佐证**（证据 2）：国际版 Google 地图"不包含政府要求的坐标偏移"——与"卫星图层是原始 WGS-84 坐标"一致。
- **对你的具体含义**：
  - OSM 数据是 **WGS-84（ODbL 开源）**；把它叠到 **Google 卫星图层**上，**理论上对齐**，可直接在 QGIS 里用 2–3 个控制点微调配准。
  - **不要把 Google 地图上看到的点位经纬度（或从 Google place 页面复制的坐标）直接拿去套 OSM/实测点**——那是 GCJ-02 语义，会整体偏 100–500 m（证据 3 的"一两百米到五百米"）。
  - **不要用国内图商（高德/百度）的坐标直接叠 Google 卫星图**：高德是 GCJ-02、百度是 BD-09，需要坐标转换（GCJ-02→WGS-84），转换后仍有米级残差。
- **不确定性（待验证）**：① Google 未公开正式文档说明各图层的坐标系处理，证据 4 是西语技术媒体转引 Wikipedia/博客的二手结论；② 即便是 WGS-84 卫星影像，其正射校正本身可能有几米误差；③ 不同缩放级别的瓦片可能来自不同影像源。**实操时用已知地物（如第三体育场、图书馆）在 OSM 与 Google 卫星图上比对，量出偏差再统一平移**，这比相信任何文章都可靠。

### Q4. 结论分级 + 实操建议

**分级：B（"只有关键地标 + 卫星影像可用"）。**

| 判定项 | 结果 |
|---|---|
| 能否在 Google 地图上逐栋看到/搜到公寓楼 POI？ | **不能**（推断） |
| Google 卫星影像能否看清校园、描出楼栋？ | **能**（推断，需上机确认分辨率/年份） |
| 卫星影像坐标是否与 OSM 一致？ | **能对齐**（卫星=WGS-84，证据 4） |
| 街景能否辅助？ | 不能（中国大陆无城市级街景） |
| **"仅靠 Google 地图"能否完成按公寓楼的管道铺设图？** | **不能**（拿不到逐栋楼名/位置）；仅靠 Google **卫星图**可手工描轮廓，但不满足"逐栋标注"的效率要求，且大陆访问不便 |

**实操建议（按推荐顺序）：**

1. **首选：OSM + QGIS/Overpass**（本次已实测，见附录）。OSM 上西校区 30 栋公寓（1-A…13-B2）**轮廓和中文名都有**，`building=dormitory` 直接筛选；导出 GeoJSON → QGIS 投影到 UTM 50N（EPSG:32650）即可按米制坐标布置管道，图上不需要再问"哪栋是几号楼"。
2. **配合：学校官方地图/VR 核对楼号**：官方手绘地图 <http://map.ysu.edu.cn/index.html>、校园 VR 全景 <https://720yun.com/t/3cbj5phaea6?scene_id=10952137>、国际学院 Campus maps 页 <https://ies.ysu.edu.cn/en/About_us/Campus_maps.htm>（本次直接抓 `map.ysu.edu.cn`、`720yun.com` 失败，用你自己的浏览器打开即可）。另可用小红书《燕大地图来啦！》<https://www.xiaohongshu.com/discovery/item/686e4185000000002201f4dc> 等新生攻略图人工核对 1–13 组团分布。
3. **可选：Google Earth 描轮廓**（可行但不推荐作主方案）：装 Google Earth Pro（桌面版，大陆需代理），搜坐标 → 历史影像挑最清晰一期 → 多边形工具逐栋描 → 导出 KML → 在 QGIS 中与 OSM 叠加，若整体偏移则统一平移。适合"就是想用 Google 影像"或"OSM 某栋楼轮廓缺失"时补。
4. **不推荐：拿高德/百度截图铺底直接画**：坐标是 GCJ-02/BD-09，与 WGS-84 数据混用会错位；如需使用必须先做坐标纠偏，且截图受版权/服务条款限制。
5. **答辩可写的一句话**："Google 地图在中国大陆因数据供应（高德）与测绘资质限制，POI 只到校区/地标级，且大陆无法正常访问；本设计采用 OpenStreetMap（WGS-84、ODbL）逐栋建筑轮廓 + 学校官方校园图核对楼号，坐标与实地一致。"

### Q5. 如何自己复核（1–2 条最有用的操作）

**复核 A：确认 Google 卫星图能否看清楼（2 分钟）**
1. 用能访问 Google 的设备打开 Google Earth Pro（桌面版）或 earth.google.com；
2. 搜索框粘贴：`39.9111, 119.5172`（=西校区中心；或搜"燕山大学西校区"）；
3. 缩放到高度约 500–800 m（比例尺 1:2000 左右），看南侧 13 个宿舍组团、北侧教学楼、东侧图书馆与体育场是否清晰可辨、能否分出单栋楼轮廓；
4. 点"历史影像"（时钟图标）切到最清晰一期，记下日期——这就是你答辩里"影像来源与时间"的依据。

**复核 B：确认 Google 地图有没有逐栋标注（1 分钟）**
1. 打开 `google.com/maps`，搜"燕山大学西校区"；
2. 缩放看 1-A…13-B2 这些楼有没有文字标签（有标签才算 POI）；
3. 在搜索框逐个输入"燕山大学西校区学生公寓13A""燕大西区公寓1-B号楼"，看是否返回 place 结果；
4. 结果只有"燕山大学""燕山大学(西校区)"等 1–3 个点 → 证实"无逐栋标注"。

---

## 四、对项目的建议（管道铺设算法设计）

1. **数据源**：主用 OSM（逐栋楼轮廓 + 中文名，WGS-84）；官方手绘地图/VR 校核楼号；实地拍照确认 1–13 组团的相对位置（尤其 12/13 组团在南端、6-A/6-B 在西侧）。
2. **坐标统一**：所有数据统一到 WGS-84 / EPSG:4326，作图用 UTM 50N（EPSG:32650）算长度与管径布置；**不要混入 GCJ-02 来源的坐标**。
3. **成果图**：底图可用 OSM 栅格或卫星截图（注明来源与年份）；管道走向按"竖井/楼前井—主干管—检查井"拓扑绘制，重点是楼栋相对位置与间距，不追求 Google 那种影像底图。
4. **可验证性**：报告中标注每栋楼的编号来源（OSM way id 或官方图），便于老师抽查；Google 不作为"真实分布图"的唯一依据。
5. **若老师强制要求 Google 地图截图**：用 Google Earth 卫星图 + OSM 轮廓叠加出图，并在图上注明"影像 ©Google，轮廓 ©OpenStreetMap contributors (ODbL)"。

---

## 五、参考链接汇总

- uniRank 燕大 Google 地图页：<https://www.unirank.org/cn/uni/yanshan-university/map/index.htm>
- 泰伯网《谷歌地图中国服务关闭》（2021-01-13）：<https://www.taibo.cn/p/67220>
- 壹云科技《Google 服务在中国》：<https://www.1yun.vip/newdetails/798.html>
- Xataka Móvil（GCJ-02/卫星 WGS-84）：<https://www.xatakamovil.com/movil-y-sociedad/mapas-china-no-como-resto-mundo-eso-vemos-carreteras-lugares-donde-no-corresponde>
- 网易·测绘之家（卫星分辨率与 0.5 m 政策）：<https://m.163.com/dy/article/HTSR79SK05319UN7.html>
- 地球在线·燕山大学卫星地图：<https://www.earthol.com/fun-2-school-ysu.html>
- Bigemap 燕山大学西校区卫星图索引：<http://www.bigemap.net/city-61261.html>
- 维基百科《Google街景服务》：<https://zh.wikipedia.org/zh-hk/Google%E8%A1%97%E6%99%AF%E6%9C%8D%E5%8A%A1>
- pconline《托熊猫的福！谷歌街景首度进入中国大陆》：<https://pcedu.pconline.com.cn/344/3442772.html>
- 城市吧·燕山大学西校区学生公寓13A：<https://qinhuangdao.city8.com/house/8bb79481jo07ba58da>
- 城市吧·燕大西区公寓1-B号楼：<https://qinhuangdao.city8.com/house/8bbc2o81jj83bcc20c>
- 燕山大学国际教育学院 Campus maps：<https://ies.ysu.edu.cn/en/About_us/Campus_maps.htm>
- 官方手绘地图：<http://map.ysu.edu.cn/index.html>（本次抓取失败，需浏览器打开）
- 校园 VR 全景：<https://720yun.com/t/3cbj5phaea6?scene_id=10952137>（需浏览器打开）
- crawlora（标题级旁证）：<https://crawlora.net/blog/china-google-maps-category-mix-2026>

---

## 六、附录：OSM 实测数据（供团队复用）

- 西校区 bbox：西 119.506103 / 北 39.9188458 / 东 119.5309067 / 南 39.9026831；中心 ≈ (119.5172, 39.9111)
- 数据接口：`overpass.openstreetmap.fr`（2026-08-10 数据），OSM 许可 ODbL，坐标 WGS-84
- 逐栋命名宿舍（`building=dormitory`，共 30 栋）：1-A、1-B、2-A、2-B、3-A、3-B、4-A、4-B、5-A、5-B、6-A、6-B、7-A、7-B、8-A、8-B、9-A、9-B、10-A、10-B、11-A、11-B、12-A1、12-A2、12-B1、12-B2、13-A1、13-A2、13-B1、13-B2
- 关键 way id：
  - 燕山大学（西校区）`way/696074149`，中心 39.9107645, 119.5185048
  - 燕山大学图书馆 `way/1226476365`，中心 39.9090027, 119.5269305
  - 6-A（University building）`way/696195042`，中心 39.9054170, 119.5135739
  - 12/13 组团宿舍 `way/1226476367`–`way/1226476374`
  - 东校区五舍 `way/117215243`，中心 39.9026342, 119.5287910
- Overpass 查询示例（可直接在 overpass-turbo 复用）：

```
[out:json][timeout:25];
(
  node["building"="dormitory"](39.9026831,119.506103,39.9188458,119.5309067);
  way["building"="dormitory"](39.9026831,119.506103,39.9188458,119.5309067);
  way["name"~"公寓|宿舍|组团"](39.9026831,119.506103,39.9188458,119.5309067);
);
out center tags;
```

---

## 七、未决事项 / 待验证清单

| # | 待验证项 | 怎么验证 | 影响 |
|---|---|---|---|
| 1 | Google 地图上是否真有逐栋公寓标注 | 能上 Google 的设备搜"燕山大学西校区"及"燕山大学西校区学生公寓13A" | 决定 Q1 最终是"无"还是"个别有"（结论大概率不变） |
| 2 | 该校区 Google 卫星影像分辨率与拍摄日期 | Google Earth Pro 历史影像滑块 | 决定描轮廓是否可行、成果图该注明哪年影像 |
| 3 | Google 卫星图与 OSM 是否真对齐（偏差量） | 在 QGIS 里叠 2–3 个控制点（图书馆、体育场）量偏差 | 若偏差 >10 m，需统一平移校正 |
| 4 | 官方手绘地图/VR 的楼号与 OSM 命名是否一致 | 浏览器打开 map.ysu.edu.cn 与 720yun 对照 | 保证"13 组团"编号写对，答辩不被挑错 |
| 5 | 校园内是否有施工/新建导致 OSM 轮廓过期 | 卫星影像 + 实地核对 | 影响管道走向合理性 |

> 说明：Q1/Q2 若判"未验证"，不代表"不存在"；本报告已把所有能拿到的间接证据列出，并给出 1–2 分钟即可完成的直接核验步骤。建议在你自己的电脑上按 Q5 复核 A/B 各做一遍，把截图留给报告作证据。
