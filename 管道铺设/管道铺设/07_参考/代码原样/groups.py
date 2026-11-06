# -*- coding: utf-8 -*-
"""Building group registry for YSU west campus (targets of the pipeline network).

This file is the single source of truth for "which building clusters are pipeline
demand points, what is their real name, how many floors".  It is hand-verified
against:
  - OSM building ways (data/raw/buildings.json)  -> geometry & footprint area
  - OSM 13 residential "组团" polygons           -> dorm grouping
  - official campus map / school news            -> names & floor counts
  - 高德/Esri satellite imagery z18               -> visual check

Every group has an explicit `evidence` field.  Keep `verified=False` groups visible
in the report — they are the remaining data gaps, not silent assumptions.

Usage: imported by scripts/build_campus.py ; run  `python scripts/groups.py`  to
print the current registry summary.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')

# ---------------------------------------------------------------------------
# Group registry.
#   pattern : regex on OSM building name ("(anon)" = unnamed building)
#   ways    : explicit OSM way ids (preferred over pattern when both given)
#   levels  : floor count used for height & demand (OSM 有多少用多少，缺失按类默认)
#   levels_src : 'osm' | 'official' | 'assumed:类别默认'
#   cat     : demand category (see DEMAND in build_campus.py)
# ---------------------------------------------------------------------------
GROUPS = [
    # ======================= 学生公寓（13 个组团） =======================
    dict(key='D01', name='1组团公寓(1-A/1-B)', short='1组团', cat='dorm',
         ways=[696199413, 696199410], levels=6, levels_src='official:6层', verified=True,
         evidence='OSM 组团面 1226592978 包含；校方口径"一组团"6层'),
    dict(key='D02', name='2组团公寓(2-A/2-B)', short='2组团', cat='dorm',
         ways=[696199408, 696199411], levels=6, levels_src='official:6层', verified=True,
         evidence='OSM 组团面 1226592979'),
    dict(key='D03', name='3组团公寓(3-A/3-B)', short='3组团', cat='dorm',
         ways=[696199409, 696199412], levels=6, levels_src='official:6层', verified=True,
         evidence='OSM 组团面 1226592980'),
    dict(key='D04', name='4组团公寓(4-A/4-B)', short='4组团', cat='dorm',
         ways=[696195055, 696195060], levels=6, levels_src='official:6层', verified=True,
         evidence='OSM 组团面 1226592977'),
    dict(key='D05', name='5组团公寓(5-A/5-B)', short='5组团', cat='dorm',
         ways=[696279415, 696279412], levels=6, levels_src='official:6层', verified=True,
         evidence='OSM 组团面 1226592976'),
    dict(key='D06', name='6组团公寓(6-A/6-B)', short='6组团', cat='dorm',
         ways=[696195042, 696195054], levels=6, levels_src='official:6层', verified=True,
         evidence='OSM 组团面 1226592975；6-A 的 building 标签误标为 university，按 name 纠正'),
    dict(key='D07', name='7组团公寓(7-A/7-B)', short='7组团', cat='dorm',
         ways=[696182823, 696182822], levels=6, levels_src='official:6层', verified=True,
         evidence='OSM 组团面 1226592974'),
    dict(key='D08', name='8组团公寓(8-A/8-B)', short='8组团', cat='dorm',
         ways=[696195050, 696195049], levels=6, levels_src='official:6层', verified=True,
         evidence='OSM 组团面 1226592973'),
    dict(key='D09', name='9组团公寓(9-A/9-B)', short='9组团', cat='dorm',
         ways=[696195052, 696195058], levels=6, levels_src='official:6层', verified=True,
         evidence='OSM 组团面 1226592972'),
    dict(key='D10', name='10组团公寓(10-A/10-B)', short='10组团', cat='dorm',
         ways=[696195041, 696195044], levels=6, levels_src='official:6层', verified=True,
         evidence='OSM 组团面 1226592971'),
    dict(key='D11', name='11组团公寓(11-A/11-B)', short='11组团', cat='dorm',
         ways=[696195043, 696195045], levels=6, levels_src='official:6层', verified=True,
         evidence='OSM 组团面 1226476377'),
    dict(key='D12', name='12组团公寓(12-A1/A2/B1/B2)', short='12组团', cat='dorm',
         ways=[1226476370, 1226476369, 1226476367, 1226476368], levels=6,
         levels_src='official:2017年新建6层', verified=True,
         evidence='OSM 组团面 1226476376；校方 2017 年建成（冀发改投资核字[2014]95号）'),
    dict(key='D13', name='13组团公寓(13-A1/A2/B1/B2)', short='13组团', cat='dorm',
         ways=[1226476371, 1226476372, 1226476374, 1226476373], levels=6,
         levels_src='official:2017年新建6层', verified=True,
         evidence='OSM 组团面 1226476375'),

    # ======================= 食堂 / 服务 =======================
    # 更正（用户指出，2026-10 核实）：西校区有两个食堂——
    #   燕园餐厅(燕园食堂) way 696280904 在 10/11 组团的东北侧；
    #   西区大食堂     way 9676180    在 U02/U03 的南侧（用户口述位置）。
    dict(key='C01', name='燕园餐厅(燕园食堂)', short='燕园餐厅', cat='canteen',
         ways=[696280904], levels=3, levels_src='osm', verified=True,
         evidence='OSM "燕大西区燕园餐厅" levels=3；用户更正：这不是西区大食堂'),
    dict(key='C02', name='西校区服务楼', short='服务楼', cat='service',
         ways=[696280902], levels=3, levels_src='osm', verified=True,
         evidence='OSM building:levels=3；校内超市/服务综合'),
    dict(key='C03', name='西区大食堂', short='大食堂', cat='canteen',
         ways=[], levels=3, levels_src='assumed:同类食堂3层', verified=False,
         measured=dict(key='canteen-west', lat=39.905820, lon=119.515000,
                       bbox=[119.514100, 39.905300, 119.515900, 39.906350], area_m2=9600),
         evidence='用户指出"U02/U03 下方的大建筑"；OSM 无此建筑，按高德 z18 影像量测'),
    dict(key='C04', name='燕大西区浴池', short='浴池', cat='service',
         ways=[], levels=2, levels_src='assumed:浴池2层', verified=False,
         measured=dict(key='bath', lat=39.907200, lon=119.514400,
                       bbox=[119.513900, 39.906950, 119.514900, 39.907450], area_m2=1800),
         evidence='用户提及；OSM 无此建筑（原 9676079 经核验是北达科他州道路，已剔除）'),

    # ======================= 教学 / 学院 =======================
    dict(key='T01', name='第一教学楼', short='一教', cat='teaching',
         ways=[696278603], levels=5, levels_src='assumed:教学楼默认5层', verified=True,
         evidence='OSM 有名；层数缺失，按同类默认（待实地核对）'),
    dict(key='T02', name='第二教学楼', short='二教', cat='teaching',
         ways=[696278598], levels=5, levels_src='assumed:教学楼默认5层', verified=True,
         evidence='OSM 有名；层数缺失'),
    dict(key='T03', name='第三教学楼', short='三教', cat='teaching',
         ways=[696278600], levels=5, levels_src='assumed:教学楼默认5层', verified=True,
         evidence='OSM 有名；层数缺失'),
    dict(key='T04', name='第四教学楼', short='四教', cat='teaching',
         ways=[696278604], levels=5, levels_src='assumed:教学楼默认5层', verified=True,
         evidence='OSM 有名；底面积 415 m² 偏小，可能只画了主楼或局部'),
    dict(key='T05', name='经管楼(第五教学楼)', short='经管楼', cat='teaching',
         ways=[1226476366], levels=5, levels_src='osm', verified=True,
         evidence='OSM building:levels=5'),
    dict(key='T06', name='里仁教学楼', short='里仁楼', cat='teaching',
         ways=[682903089], levels=6, levels_src='assumed:教学楼默认5层(里仁为大型综合体)', verified=True,
         evidence='OSM 底面积 19586 m²，为西校区最大单体；层数缺失'),
    dict(key='T07', name='电气A楼', short='电气A', cat='teaching',
         ways=[696280903], levels=5, levels_src='osm', verified=True, evidence='OSM levels=5'),
    dict(key='T08', name='电气B楼', short='电气B', cat='teaching',
         ways=[696278599], levels=5, levels_src='osm', verified=True, evidence='OSM levels=5'),
    dict(key='T09', name='电气C楼', short='电气C', cat='teaching',
         ways=[696280901], levels=5, levels_src='osm', verified=True, evidence='OSM levels=5'),
    dict(key='T10', name='电气D楼', short='电气D', cat='teaching',
         ways=[696278597], levels=5, levels_src='osm', verified=True, evidence='OSM levels=5'),
    dict(key='T11', name='材料B楼', short='材料B', cat='lab',
         ways=[696278602], levels=5, levels_src='osm', verified=True, evidence='OSM levels=5'),
    dict(key='T12', name='材料C楼', short='材料C', cat='lab',
         ways=[696278601], levels=5, levels_src='osm', verified=True, evidence='OSM levels=5'),
    dict(key='T13', name='高压科学中心', short='高压中心', cat='lab',
         ways=[1226483925], levels=4, levels_src='assumed:实验楼默认4层', verified=True,
         evidence='OSM 有名；层数缺失'),
    dict(key='T14', name='国际教育学院(欧洲学院)/生命健康与智能医学学院', short='国际·生命健康', cat='college',
         ways=[1317102815], levels=5, levels_src='assumed', verified=True,
         evidence='OSM 有名（国际教育学院）；高德同一栋楼上另标「燕山大学生命健康与智能医学学院」'
                  '（GCJ 119.522585,39.915600 → WGS 39.914376,119.516619，与本楼相距约 40 m，'
                  '是同一条长条楼的不同入口）→ 第七轮用户指认此楼即生命健康学院，故合并为一个节点'),
    dict(key='T15', name='西里西亚智能科学与工程学院', short='西里西亚学院', cat='college',
         ways=[1317102814], levels=5, levels_src='assumed', verified=True, evidence='OSM 有名'),
    dict(key='T16', name='燕山大学图书馆', short='图书馆', cat='library',
         ways=[1226476365], levels=7, levels_src='osm', verified=True,
         evidence='OSM levels=7；位于西校区东侧（东门内）'),
    dict(key='T17', name='材料A楼（亚稳材料国家重点实验室）', short='材料A·亚稳',
         cat='lab', ways=[], levels=3, levels_src='assumed:实验楼默认3层', verified=False,
         measured=dict(key='metastable-lab', lat=39.907115, lon=119.517080,
                       bbox=[119.516690, 39.906930, 119.517470, 39.907300], area_m2=2500),
         evidence='用户指认"材料B楼下方那个半圆形建筑"为国家重点实验室；官方 3D 校园图'
                  '（宣传部 2026-07）把该楼标为「材料A楼」，故按"楼名+机构"双名记录。'
                  '机构官方全称="亚稳材料制备技术与科学国家重点实验室"'
                  '（燕山大学依托，见 mse.ysu.edu.cn/gjzdsys/gjsys.htm）。'
                  'OSM 无此建筑，按影像量测：读点图 docs/fig/loc_lab_grid.jpg，长方形主体 + 南向半圆弧'),
    dict(key='T18', name='里仁实验楼', short='里仁实验楼', cat='lab',
         ways=[], levels=5, levels_src='assumed:实验楼默认5层', verified=False,
         measured=dict(key='liren-lab', lat=39.904240, lon=119.523690,
                       bbox=[119.523260, 39.903475, 119.524120, 39.905000], area_m2=10500),
         evidence='用户两次确认：里仁教学楼**东侧**那栋带庭院的大楼是里仁实验楼'
                  '（此前我先误标"里仁实验楼"、又误改为"办公楼(材料学院)"，现改回）。'
                  'OSM 无此 way，按影像量测；对照图 docs/fig/loc_liren.jpg'),
    # T19 图文信息楼 —— 已删除（2026-10-29）。
    #   这条记录的名字来源是 way 9473738，而 scripts/validate_ids.js 的逐 id 回查
    #   结果是 status='missing'（该 way 在 OSM 中不存在，见 data/derived/id_validation.json）。
    #   当时只是把"OSM 无此 way"改成了"按影像量测"，但量测框是我按经纬网硬凑的
    #   （145x134 m 的方框，框住的是高压科学中心周边连片屋顶+林荫道，实测该处是
    #   停车场与绿化带）。既然没有可靠依据，就不该在方案里留一条杜撰的建筑。
    #   → 待用户指认位置后再补；在此之前不计入统计、不参与供水。

    # ============ 圆形广场内五栋教学楼（OSM 完全没有绘制，影像实测补入） ============
    # 位置：西校区最北端的圆形环路广场内。用户口述（两轮）：
    #   第一轮："三个建筑，最上方一个是信息科学与工程学院，左下方为人工智能学院(软件学院)，
    #           右下方为理学院"
    #   第二轮（更正）："广场 LL 也是人工智能学院，广场 UR 的那个也是理学院"
    #   → 即左列上下两栋都属【人工智能学院(软件学院)】，右列上下两栋都属【理学院】。
    # 影像核对：广场内共 5 栋 —— 最上方 1 栋弧形大楼 + 上下两排各 2 栋。
    # 坐标为高德 z18 影像人工量测，读点图 docs/fig/plaza_grid.jpg，
    # 复核图 docs/fig/plaza_verify.jpg（框与屋顶逐栋吻合）。
    # 精度约 ±1.5 m —— 满足 100 m 量级管网规划，不宜作正式报建依据。
    # bbox 顺序：[minLon, minLat, maxLon, maxLat]。
    dict(key='X01', name='信息科学与工程学院', short='信息学院', cat='college',
         ways=[], levels=5, levels_src='assumed', verified=False,
         measured=dict(key='plaza-top', lat=39.917205, lon=119.515542,
                       bbox=[119.514613, 39.917049, 119.516472, 39.917361], area_m2=5572),
         evidence='用户口述"最上方的一个"；OSM 无此建筑，影像量测（弧形大楼）'),
    dict(key='X02', name='人工智能学院(软件学院)', short='人工智能', cat='college',
         ways=[], levels=5, levels_src='assumed', verified=False,
         measured=dict(key='plaza-left', lat=39.916263, lon=119.514990,
                       bbox=[119.514478, 39.915825, 119.515502, 39.916702], area_m2=7502),
         evidence='用户口述"左下方的"+第二轮"广场 LL 也是人工智能学院"→ 左列上下两栋同属该院；'
                  '第七轮按用户要求合并为一个节点（面积=两栋之和 2,719+4,783）；OSM 无此建筑，影像量测'),
    dict(key='X03', name='理学院', short='理学院', cat='college',
         ways=[], levels=5, levels_src='assumed', verified=False,
         measured=dict(key='plaza-right', lat=39.916206, lon=119.516324,
                       bbox=[119.515744, 39.915829, 119.516903, 39.916689], area_m2=8658),
         evidence='用户口述"右下方的"+第二轮"广场 UR 也是理学院"→ 右列上下两栋同属理学院；'
                  '第七轮按用户要求合并为一个节点（面积=两栋之和 5,412+3,246）；OSM 无此建筑，影像量测'),

    # ============ 燕山大学机械厂：按用户要求不再标注（2026-10-28 第四轮） ============
    # 用户："不用标注机械厂了，去掉吧"。
    # 背景留档（不再出现在任何图与算法节点里）：OSM 全校区无此名；校方资料确认该厂
    # 2002 年对内更名「工程训练中心」、2021-10-09 注销，中心场地 11000 m²
    # （http://gcxlzx.ysu.edu.cn/info/1128/1331.htm、http://gcxlzx.ysu.edu.cn/zxgk/zxjj.htm）；
    # 影像上一教西侧确有一排 4 条平行长条厂房。该处 OSM 现标为 电气C/D 楼，保持 OSM 标注。

    # ======================= 公共建筑 =======================
    dict(key='P01', name='里仁行政楼', short='里仁行政楼', cat='office',
         ways=[682903087], levels=6, levels_src='assumed:办公默认6层', verified=True,
         evidence='OSM 名为「办公楼」；用户指出里仁教学楼西侧这栋要特别标注；'
                  '官方 3D 校园图标注为「里仁行政楼」，故采用官方名（原口述「办公楼（里仁实验楼）」）'),
    dict(key='P02', name='西校区大学生活动中心', short='活动中心', cat='activity',
         ways=[682903088], levels=4, levels_src='assumed', verified=True, evidence='OSM 有名'),
    dict(key='P03', name='美术馆', short='美术馆', cat='art',
         ways=[697150020], levels=3, levels_src='assumed', verified=True, evidence='OSM 有名'),
    dict(key='P04', name='国家电网燕山大学变电站', short='变电站', cat='utility',
         ways=[1226592981], levels=1, levels_src='osm', verified=True, evidence='OSM 有名'),

    # ========== 第五轮：用户截图上圈出的 4 栋（OSM 全部未绘制，影像量测） ==========
    # 用户原话："操场这个为西校区第四体育场体育馆，美术馆旁边那个为音乐管(sic)，
    #   经管楼上方那个为生命健康与智能医学学院，美术馆建筑的最上方的一小块建筑
    #   可以标注艺术与设计学院"。四栋在 OSM 里都没有，坐标为高德 z18 影像人工量测；
    # 读点图 / 复核图见 docs/fig/proof_four_new.jpg。
    dict(key='N01', name='西校区新体育馆', short='新体育馆', cat='sports',
         ways=[], levels=2, levels_src='assumed:大跨度馆2层', verified=False,
         measured=dict(key='gym4', lat=39.911965, lon=119.509559,
                       bbox=[119.509101, 39.911450, 119.510017, 39.912535], area_m2=8915),
         evidence='用户指认"操场旁边的体育馆"；官方 3D 校园图（宣传部 2026-07）标注为「西校区新体育馆」，'
                  '紧邻第四体育场（OSM way 829903378）西北侧。OSM 无此建筑，影像量测'),
    dict(key='N02', name='音乐馆（燕山大学音乐厅）', short='音乐馆', cat='art',
         ways=[], levels=3, levels_src='assumed', verified=False,
         measured=dict(key='music-hall', lat=39.912100, lon=119.514281,
                       bbox=[119.513809, 39.911681, 119.514752, 39.912519], area_m2=7452),
         evidence='用户指认"美术馆旁边那个"；官方 3D 校园图标注为「音乐馆」，南侧另有「燕山大学音乐厅」'
                  '字样，与美术馆同属一个建筑组群。OSM 无此建筑，影像量测'),
    dict(key='N04', name='艺术与设计学院', short='艺术与设计', cat='art',
         ways=[], levels=3, levels_src='assumed', verified=False,
         measured=dict(key='art-design', lat=39.913100, lon=119.513640,
                       bbox=[119.513350, 39.912900, 119.513950, 39.913300], area_m2=2200),
         evidence='用户指认"美术馆建筑最上方的一小块"；官方 3D 校园图把「艺术与设计学院」标在美术馆组群'
                  '东北翼，与「美术馆」「音乐馆」「A/B座展区」「C座办公区」同属一体。OSM 未单独绘制，影像量测'),

    # ==================== 待核实：17 栋无名 building=university ====================
    # 这些是 OSM 里真实存在但未命名的建筑；按面积与位置初步猜测用途，全部标记未核实。
    dict(key='U01', name='未命名建筑-电气A北侧小车棚?', short='U01', cat='other',
         ways=[696195053], levels=2, levels_src='assumed', verified=False,
         evidence='OSM 无名 building=university，面积 135 m²'),
    dict(key='U02', name='未命名建筑-6组团北侧', short='U02', cat='other',
         ways=[696182821], levels=3, levels_src='assumed', verified=False,
         evidence='OSM 无名，面积 340 m²，位于 6 组团北侧'),
    dict(key='U03', name='未命名建筑-6组团北侧(小)', short='U03', cat='other',
         ways=[696182824], levels=2, levels_src='assumed', verified=False,
         evidence='OSM 无名，面积 153 m²'),
    dict(key='U04', name='未命名建筑-6A西侧', short='U04', cat='other',
         ways=[696195046], levels=2, levels_src='assumed', verified=False,
         evidence='OSM 无名，面积 135 m²'),
    dict(key='U05', name='未命名建筑-9组团南', short='U05', cat='other',
         ways=[696195057], levels=3, levels_src='assumed', verified=False,
         evidence='OSM 无名，面积 964 m²（较大，可能是食堂/浴池类）'),
    dict(key='U06', name='未命名建筑-10组团北', short='U06', cat='other',
         ways=[696195059], levels=2, levels_src='assumed', verified=False,
         evidence='OSM 无名，面积 155 m²'),
    dict(key='U07', name='未命名建筑-9A东侧', short='U07', cat='other',
         ways=[696279408], levels=2, levels_src='assumed', verified=False,
         evidence='OSM 无名，面积 135 m²'),
    dict(key='U08', name='未命名建筑-9B东侧', short='U08', cat='other',
         ways=[696279409], levels=2, levels_src='assumed', verified=False,
         evidence='OSM 无名，面积 135 m²'),
    dict(key='U09', name='未命名建筑-4组团南', short='U09', cat='other',
         ways=[696279410], levels=2, levels_src='assumed', verified=False,
         evidence='OSM 无名，面积 133 m²'),
    dict(key='U10', name='未命名建筑-4组团南(2)', short='U10', cat='other',
         ways=[696279411], levels=2, levels_src='assumed', verified=False,
         evidence='OSM 无名，面积 133 m²'),
    dict(key='U11', name='未命名建筑-5B北', short='U11', cat='other',
         ways=[696279413], levels=2, levels_src='assumed', verified=False,
         evidence='OSM 无名，面积 130 m²'),
    dict(key='U12', name='未命名建筑-2A东', short='U12', cat='other',
         ways=[696279414], levels=2, levels_src='assumed', verified=False,
         evidence='OSM 无名，面积 130 m²'),
    dict(key='U13', name='未命名建筑-1B东', short='U13', cat='other',
         ways=[696279416], levels=2, levels_src='assumed', verified=False,
         evidence='OSM 无名，面积 130 m²'),
    dict(key='U14', name='未命名建筑-1B东南', short='U14', cat='other',
         ways=[1226592983], levels=3, levels_src='assumed', verified=False,
         evidence='OSM building=yes 无名，面积 1752 m²（较大，可能是食堂/浴池）'),
    dict(key='U15', name='未命名建筑-高压中心西', short='U15', cat='other',
         ways=[1226592986], levels=2, levels_src='assumed', verified=False,
         evidence='OSM 名"实验室废物暂存处"，按小配套处理'),

    # ================= 第七轮：官方 3D 图上有、卫星图上尚未定位的建筑 =================
    # 这 11 栋来自校方官方 3D 校园地图（燕山大学党委宣传部 2026-07 制作）的标注，但
    # (a) OSM 里没有，(b) 卫星影像上无法单凭形状唯一确定是哪一栋（多为大片同形楼群）。
    # 因此这里只登记"名字与存在性"，measured=None、ways=[]，**不参与距离表与 MST 计算**，
    # 等用户在图上圈出位置后补 bbox 即可（补完 measured 会自动进入计算）。
    dict(key='Y01', name='材料学院中试车间', short='中试车间', cat='lab',
         ways=[], levels=1, levels_src='assumed:车间1层', verified=False,
         evidence='官方 3D 图标注；OSM 无；卫星图上应为 材料C楼 东北侧的长条厂房，位置待实测'),
    dict(key='Y02', name='先进结构材料中心', short='先进结构材料', cat='lab',
         ways=[], levels=3, levels_src='assumed', verified=False,
         measured=dict(key='adv-struct', lat=39.907642, lon=119.517780,
                       bbox=[119.517537, 39.907347, 119.518022, 39.907937], area_m2=2700),
         evidence='官方 3D 图有楼名；OSM 无；高德 POI「燕山大学先进结构材料中心」'
                  '（GCJ 119.524017,39.908899 → WGS 39.907680,119.518058）定位到 材料A楼 东南侧'
                  '白屋顶建筑群，再按影像读点得 bbox（41×65 m ≈ 2,700 m²）'),
    dict(key='Y03', name='里仁学院实验中心', short='里仁实验中心', cat='lab',
         ways=[], levels=4, levels_src='assumed', verified=False,
         evidence='官方 3D 图标注；OSM 无；位于 里仁教学区 与 里仁实验楼 之间，位置待实测'),
    dict(key='Y04', name='国际人才培训中心', short='国际人才培训', cat='college',
         ways=[], levels=4, levels_src='assumed', verified=False,
         evidence='官方 3D 图标注；OSM 无；位于 经管楼 东北侧，位置待实测'),
    dict(key='Y05', name='研究生公寓A', short='研究生公寓A', cat='dorm',
         ways=[], levels=6, levels_src='assumed:公寓6层', verified=False,
         evidence='官方 3D 图标注；OSM 无；西北角（新体育馆一带），位置待实测'),
    dict(key='Y06', name='研究生公寓B', short='研究生公寓B', cat='dorm',
         ways=[], levels=6, levels_src='assumed:公寓6层', verified=False,
         evidence='官方 3D 图标注；OSM 无；西北角（新体育馆一带），位置待实测'),
    dict(key='Y07', name='留学生公寓', short='留学生公寓', cat='dorm',
         ways=[], levels=6, levels_src='assumed:公寓6层', verified=False,
         evidence='官方 3D 图标注；OSM 无；西北角（新体育馆一带），位置待实测'),
    dict(key='Y08', name='教职工公寓', short='教职工公寓', cat='dorm',
         ways=[], levels=6, levels_src='assumed:公寓6层', verified=False,
         evidence='官方 3D 图标注；OSM 无；西北角（新体育馆一带），位置待实测'),
    dict(key='Y09', name='兴龙广场超市', short='兴龙超市', cat='service',
         ways=[], levels=2, levels_src='assumed', verified=False,
         evidence='官方 3D 图标注；OSM 无；位于 西校区浴池 附近，位置待实测'),
    dict(key='Y10', name='拓展中心', short='拓展中心', cat='activity',
         ways=[], levels=2, levels_src='assumed', verified=False,
         evidence='官方 3D 图标注；OSM 无；西南角，位置待实测'),
    dict(key='Y11', name='燕山大学亚稳材料技术融合中心', short='亚稳融合中心', cat='lab',
         ways=[], levels=4, levels_src='assumed', verified=False,
         evidence='官方 3D 图标注在大草坪上，疑似规划/在建；OSM 无；位置待实测'),
]


def load_ways():
    with open(os.path.join(RAW, 'buildings.json'), 'r', encoding='utf-8') as f:
        data = json.load(f)
    out = {}
    for el in data['elements']:
        out.setdefault(el['id'], el)      # 去重：同一 way 在分块合并时可能重复出现
    return out


if __name__ == '__main__':
    ways = load_ways()
    tot = 0
    for g in GROUPS:
        miss = [w for w in g['ways'] if w not in ways]
        tot += len(g['ways'])
        print('%-4s %-28s cat=%-9s ways=%d levels=%s%s %s' % (
            g['key'], g['name'], g['cat'], len(g['ways']), g['levels'],
            ('  MISSING%s' % miss) if miss else '', '' if g['verified'] else '[未核实]'))
    print('groups=%d ways=%d' % (len(GROUPS), tot))
