/**
 * AMap Web Service keyless-free POI search.
 * usage: node scripts/amap_search.js "关键词1" "关键词2" ...
 * env: AMAP_KEY (defaults to the key provided by the user)
 *
 * Returns GCJ-02 locations; use scripts/java/… or scripts/gcj2wgs.py to convert.
 */
const KEY = process.env.AMAP_KEY || 'ed947ef3bd8ceef0f7a10b8741102dec';
const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    + '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
};

async function text(kw, city = '130300') {
  const url = `https://restapi.amap.com/v3/place/text?key=${KEY}&keywords=${encodeURIComponent(kw)}`
    + `&city=${city}&citylimit=false&offset=25&page=1&extensions=base&output=JSON`;
  const r = await fetch(url, { headers: HEADERS });
  const t = await r.text();
  let j;
  try { j = JSON.parse(t); } catch (e) {
    console.log(`[${kw}] NONJSON ${r.status} ${t.slice(0, 200)}`);
    return [];
  }
  if (j.status !== '1') {
    console.log(`[${kw}] ERR ${j.status} ${j.info} ${j.infocode}`);
    return [];
  }
  const pois = j.pois || [];
  console.log(`[${kw}] count=${j.count} got=${pois.length}`);
  for (const p of pois) {
    console.log(`   ${p.name} | ${(p.address || '')} | ${p.location} | ${p.type || ''}`
      + ` | ${p.cityname || ''}${p.adname || ''}`);
  }
  return pois;
}

(async () => {
  const kws = process.argv.slice(2);
  const all = {};
  for (const kw of kws) {
    all[kw] = await text(kw);
    await new Promise((r) => setTimeout(r, 220));
  }
  require('fs').writeFileSync('data/derived/amap_search.json', JSON.stringify(all, null, 1));
  console.log('-> data/derived/amap_search.json');
})();
