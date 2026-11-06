# -*- coding: utf-8 -*-
"""Sync the final (elliptical-ring) numbers into every delivery document.

The ring re-trace changed the solved values once more, so every report that
quotes MST length / cost / lateral lengths has to move together. Run this last,
after build_bundle_v2.py + add_service_points.py, and check the STALE list at
the end is empty.

usage: python scripts/sync_final_numbers.py
"""
import os
import re

DESK = r'C:\Users\ROD\Desktop\管道铺设'
FILES = [
    os.path.join(DESK, '00_README.md'),
    os.path.join(DESK, '04_数据', '数据结构与字段字典.md'),
    os.path.join(DESK, '03_实施方案', '实施方案_算法设计.md'),
    os.path.join(DESK, '03_实施方案', '技术栈与架构说明.md'),
    os.path.join(DESK, '06_代码', 'README_脚本说明.md'),
    os.path.join(DESK, '07_参考', '代码原样', 'README_代码原样说明.md'),
    os.path.join(DESK, '07_参考', '参考资料与踩坑记录.md'),
    os.path.join(DESK, '01_提示词', 'Codex提示词_主管道铺设项目.md'),
    os.path.join(DESK, '01_提示词', 'Codex提示词_分阶段任务清单.md'),
]

# (old, new) -- applied in order; keep the arrow forms first so the
# "before -> after" comparison tables stay readable
PAIRS = [
    ('7,799.2 m → **7,873.' , 'SKIP'),      # placeholder guard, never matches
    ('7,717.9 m → **7,799.2 m**', '7,717.9 m → **7,799.2 m**'),

    ('7,870.3', '8,163.4'),
    ('7,799.2', '8,163.4'),
    ('7799.2', '8163.4'),
    ('7870.3', '8163.4'),
    ('7,069.2', '7,301.2'),
    ('7,007.4', '7,301.2'),
    ('7007.4', '7301.2'),
    ('7069.2', '7301.2'),
    ('476.7 万', '481.8 万'),
    ('473.7 万', '481.8 万'),
    ('4767185', '4818409'),
    ('4737281', '4818409'),
    ('41,228.8', '41,146.6'),
    ('41,013.0', '41,146.6'),
    ('41013.0', '41146.6'),

    # plaza laterals, final values
    ('国际·生命健康 90.3→**7.3 m**', '国际·生命健康 90.3→**3.3 m**'),
    ('西里西亚 64.3→**4.7 m**', '西里西亚 64.3→**0.9 m**'),
    ('信息学院 ~50→**5.9 m**', '信息学院 ~50→**4.1 m**'),
    ('人工智能 ~40→**13.2 m**', '人工智能 ~40→**9.2 m**'),
    ('理学院 52.8 m', '理学院 56.9 m'),
]

STALE = ['7,799.2', '7799.2', '7,007.4', '7007.4', '473.7 万', '4737281',
         '41,013.0', '469.5 万', '7,717.9', '7717.9', '6,936.6', '6936.6']


def main():
    total = 0
    for path in FILES:
        if not os.path.exists(path):
            print('MISSING', path)
            continue
        with open(path, encoding='utf-8') as f:
            txt = f.read()
        before = txt
        for old, new in PAIRS:
            if new == 'SKIP':
                continue
            if old in txt and old != new:
                txt = txt.replace(old, new)
                total += txt.count(new) and 0
        if txt != before:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(txt)
            print('updated %-46s %+d bytes' % (os.path.basename(path),
                                               len(txt) - len(before)))
    print('replacements applied:', total if total else 'see per-file diff')

    left = []
    for path in FILES:
        if not os.path.exists(path):
            continue
        txt = open(path, encoding='utf-8').read()
        for tok in STALE:
            if tok in txt:
                left.append((os.path.basename(path), tok))
    if left:
        print('\nSTALE tokens still present (check whether they are in a '
              '"before -> after" table, which is legitimate):')
        for name, tok in left:
            print('   %-46s %s' % (name, tok))
    else:
        print('no stale tokens')


if __name__ == '__main__':
    main()
