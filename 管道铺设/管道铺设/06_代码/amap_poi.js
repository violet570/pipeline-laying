/**
 * Try AMap's keyless POI search endpoint used by ditu.amap.com.
 * usage: node scripts/amap_poi.js "关键词" ["关键词2" ...]
 */
const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    + '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
  'Referer': 'https://ditu.amap.com/',
  'Accept': 'application/json, text/javascript, */*; q=0.01',
  'X-Requested-With': 'XMLHttpRequest',
};

async function search(kw) {
  const q = encodeURIComponent(kw);
  const urls = [
    `https://ditu.amap.com/service/poiInfo?query_type=TQUERY&pagesize=20&pagenum=1&qii=true`
    + `&cluster_state=5&need_utd=true&utd_sceneid=1000&div=PC1000&addr_poi_merge=true`
    + `&is_classify=true&zoom=17&city=130300&keywords=${q}`,
    `https://www.amap.com/service/poiInfo?query_type=TQUERY&pagesize=20&pagenum=1`
    + `&city=130300&keywords=${q}`,
  ];
  for (const u of urls) {
    try {
      const r = await fetch(u, { headers: HEADERS });
      const t = await r.text();
      console.log(`[${kw}] status=${r.status} len=${t.length}`);
      if (t.length > 50) {
        try {
          const j = JSON.parse(t);
          const list = (j.data && j.data.poi_list) || [];
          for (const p of list.slice(0, 6)) {
            console.log('   ', p.name, p.address, JSON.stringify(p.location || p.longitude));
          }
          if (!list.length) console.log('   raw:', t.slice(0, 300));
        } catch (e) {
          console.log('   raw:', t.slice(0, 300));
        }
        return;
      }
    } catch (e) {
      console.log(`[${kw}] ERR ${e.message}`);
    }
  }
}

(async () => {
  for (const kw of process.argv.slice(2)) await search(kw);
})();
