# -*- coding: utf-8 -*-
"""Sync the plan document's figures with the current bundle (61 groups / 45 targets).

Numbers come from data/derived/pipeline_bundle_conn.json produced by
scripts/build_bundle_v2.py + scripts/add_service_points.py.

usage: python scripts/sync_plan_doc.py
"""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, 'docs', '实施方案_算法设计.md')

PAIRS = [
    ('72 组注册表中有 46 个供水目标参与计算', '71 组注册表中有 45 个供水目标参与计算'),
    ('MST 8,680.5 m', 'MST 7,717.9 m'),
    ('8,680.5 m', '7,717.9 m'),
    ('7,880.9 m', '6,936.6 m'),
    ('7,083.7', '6,933.7'),
    ('204.97 L/s', '200.63 L/s'),
    ('522.2 万元', '469.5 万元'),
    ('5,647.7 m', '5,632.2 m'),
    ('46 个供水目标', '45 个供水目标'),
    ('46 个需求点', '45 个需求点'),
    ('1,081 条真实距离边（$\\binom{47}{2}$', '990 条真实距离边（$\\binom{46}{2}$'),
    ('跑 47 次', '跑 46 次'),
    ('962 节点 / 1,074 边', '1,004 节点 / 1,120 边'),
    ('差 3,032.8 m', '差 2,085.7 m'),
    ('62 个建筑群全部按', '61 个建筑群全部按'),
    ('27,309.0', '40,659.5'),
    ('约 27,300 m', '约 40,660 m'),
]

OLD_ACC = ('**最大接路距离 220.3 m**（人工智能学院，校园北侧圆形广场一带 OSM 未标注道路所致，'
           '属底图数据缺失而非算法误差）')
NEW_ACC = ('**最大接路距离 173.1 m**（西校区新体育馆）。原先最长的三个人工智能学院 227.9 m、'
           '理学院、信息学院，在按高德影像补描圆形广场环路后全部降到 100 m 以内——'
           '说明那一段确实是底图缺路，而不是算法选错了路')


def main():
    s = io.open(DOC, encoding='utf-8').read()
    hits = {}
    for a, b in PAIRS:
        n = s.count(a)
        hits[a] = n
        s = s.replace(a, b)
    s = s.replace(OLD_ACC, NEW_ACC)
    io.open(DOC, 'w', encoding='utf-8').write(s)
    for a, n in hits.items():
        print('%3d x  %s' % (n, a[:60]))
    print('->', DOC)


if __name__ == '__main__':
    main()
