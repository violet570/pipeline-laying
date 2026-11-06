# -*- coding: utf-8 -*-
"""Try to grab the official YSU campus map image(s) so we can read building names."""
import re
import ssl
import urllib.request

URL = 'http://xcb.ysu.edu.cn/info/1179/7733.htm'
HDR = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                     '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'}
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(URL, headers=HDR)
try:
    html = urllib.request.urlopen(req, timeout=40, context=ctx).read().decode('utf-8', 'ignore')
except Exception as e:
    print('ERR', e)
    raise SystemExit(1)
print('len', len(html))
imgs = re.findall(r'<img[^>]+src="([^"]+)"', html)
for u in imgs:
    print('IMG', u)
links = re.findall(r'href="([^"]+\.(?:jpg|png|jpeg))"', html)
for u in links:
    print('LINK', u)
