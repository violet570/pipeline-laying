# -*- coding: utf-8 -*-
"""Download the official YSU campus map (9.5 MB jpg) and report its size."""
import os
import ssl
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = 'http://xcb.ysu.edu.cn/__local/D/7A/C8/8ADAB0AB212F02582A93509F9AC_EFAFC46D_909E89.jpg'
HDR = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                     '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
       'Referer': 'http://xcb.ysu.edu.cn/info/1179/7733.htm'}
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

out = os.path.join(ROOT, 'data', 'raw', 'official_campus_map.jpg')
req = urllib.request.Request(URL, headers=HDR)
data = b''
try:
    with urllib.request.urlopen(req, timeout=180, context=ctx) as r:
        while True:
            chunk = r.read(262144)
            if not chunk:
                break
            data += chunk
            print('  read', len(data), flush=True)
except Exception as e:
    part = getattr(e, 'partial', b'')
    data = data + (part or b'')
    print('WARN', type(e).__name__, e, 'total', len(data))
print('bytes', len(data))
with open(out, 'wb') as f:
    f.write(data)

from PIL import Image
im = Image.open(out)
print('size', im.size, im.mode)
