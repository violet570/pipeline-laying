/* ============================================================================
 * pipe_engine.js —— 给水管道规划引擎（planner.html / matrix_mst.html 共用）
 *
 * 口径与 06_代码/build_bundle_v2.py 完全一致：
 *   1. 路网取 bundle.roads（OSM + 广场环道补描），按道路等级加权 HW_W
 *   2. 每个目标点吸附到最近路网边并打断成新节点（不插入则直接用端点）
 *   3. 在 {水源} ∪ {目标} 的完全图上跑 Kruskal，边权 = 沿路网加权最短路
 *   4. 每栋楼沿生成树上行，把它自己的需求只加到它实际经过的每条管段一次
 *      （这是修过 bug 的写法：按子树累加会把重叠路段重复计入）
 *
 * 复算验证：默认水源 + 45 栋 → MST 8,116.0 m（主数据 8,115.9 m，差 0.1 m 浮点）。
 * ==========================================================================*/
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.PipeEngine = factory();
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  // 供水目标类别：排除无名附属建筑 other 与市政设施 utility（变电站属强电，不入给水管网）
  var TARGET_CATS = {
    dorm: 1, canteen: 1, teaching: 1, college: 1, lab: 1, library: 1,
    office: 1, activity: 1, art: 1, service: 1, sports: 1
  };
  // 道路等级权重（管道只能沿可施工的路由走，人行道/便道加权更大）
  var HW_W = {
    trunk: 1.0, secondary: 1.0, tertiary: 1.0, residential: 1.0,
    unclassified: 1.0, service: 1.15, cycleway: 1.3, footway: 1.3, path: 1.6
  };
  var DN_LIST = [32, 40, 50, 65, 80, 100, 125, 150, 200, 250, 300, 350, 400, 500];
  // 综合单价 元/m（球墨铸铁给水管，含管材、管件、土方、回填、路面恢复）
  var DN_COST = {
    32: 140, 40: 160, 50: 185, 65: 225, 80: 270, 100: 330, 125: 400,
    150: 480, 200: 620, 250: 800, 300: 1000, 350: 1200, 400: 1450, 500: 1900
  };
  var DN_COL = {
    32: '#8d6e63', 40: '#a1887f', 50: '#bcaaa4', 65: '#b0bec5', 80: '#78909c',
    100: '#00e5ff', 125: '#2979ff', 150: '#7c4dff', 200: '#00e676', 250: '#c6ff00',
    300: '#ffd600', 400: '#ff3d00', 500: '#d50000'
  };
  var CAT_COL = {
    dorm: '#ff7043', canteen: '#ffa726', teaching: '#42a5f5', college: '#26c6da',
    lab: '#ab47bc', library: '#ec407a', office: '#66bb6a', activity: '#ffca28',
    art: '#f06292', service: '#90a4ae', sports: '#26c6da', utility: '#78909c',
    other: '#546e7a'
  };
  var CAT_NAME = {
    dorm: '公寓', canteen: '餐厅', teaching: '教学', college: '学院', lab: '实验',
    library: '图书馆', office: '办公', activity: '活动', art: '艺术', service: '服务',
    sports: '体育', utility: '变电', other: '附属'
  };
  var KH = 2.5;                       // 时变化系数
  var PEAK_HOURS = 24.0 / KH;         // 高峰等效小时数 = 9.6 h
  var INF = Infinity;

  /** 按设计流量（L/s）与经济流速选标准公称直径 */
  function pickDN(qLs, v) {
    if (!(qLs > 0)) return 32;
    var dmm = Math.sqrt(4 * (qLs / 1000) / (Math.PI * (v || 1.0))) * 1000;
    for (var i = 0; i < DN_LIST.length; i++) if (DN_LIST[i] >= dmm) return DN_LIST[i];
    return 500;
  }

  /** 二叉堆（按距离） */
  function heapPush(h, d, k) {
    h.push([d, k]);
    var i = h.length - 1;
    while (i > 0) {
      var p = (i - 1) >> 1;
      if (h[p][0] <= h[i][0]) break;
      var t = h[p]; h[p] = h[i]; h[i] = t; i = p;
    }
  }
  function heapPop(h) {
    var top = h[0], last = h.pop();
    if (h.length) {
      h[0] = last;
      var i = 0;
      for (;;) {
        var l = 2 * i + 1, r = l + 1, s = i;
        if (l < h.length && h[l][0] < h[s][0]) s = l;
        if (r < h.length && h[r][0] < h[s][0]) s = r;
        if (s === i) break;
        var t = h[s]; h[s] = h[i]; h[i] = t; i = s;
      }
    }
    return top;
  }

  /** 把 bundle 包装成可反复求解的引擎 */
  function createEngine(B) {
    var M = B.meta;
    var LAT0 = M.origin[0], LON0 = M.origin[1];
    var K_LAT = M.m_per_deg_lat, K_LON = M.m_per_deg_lon;

    function proj(lon, lat) { return [(lon - LON0) * K_LON, (lat - LAT0) * K_LAT]; }
    function lonlat(x, y) { return [LON0 + x / K_LON, LAT0 + y / K_LAT]; }

    // ---------------- 路网图 ----------------
    function Graph() { this.nodes = {}; this.edges = []; this.adj = {}; this.order = []; }

    Graph.prototype.addNode = function (lon, lat) {
      var k = lon.toFixed(7) + ',' + lat.toFixed(7);
      var n = this.nodes[k];
      if (!n) {
        var p = proj(lon, lat);
        n = { key: k, x: p[0], y: p[1], lon: lon, lat: lat };
        this.nodes[k] = n; this.adj[k] = []; this.order.push(k);
      }
      return k;
    };
    Graph.prototype.addEdge = function (a, b, hw) {
      var na = this.nodes[a], nb = this.nodes[b];
      var ln = Math.hypot(nb.x - na.x, nb.y - na.y);
      if (ln < 0.05) return -1;
      var e = {
        a: a, b: b, ax: na.x, ay: na.y, bx: nb.x, by: nb.y,
        len: ln, w: ln * (HW_W[hw] || 1.15), hw: hw, dead: false
      };
      var id = this.edges.length;
      this.edges.push(e);
      this.adj[a].push([b, id]); this.adj[b].push([a, id]);
      return id;
    };
    Graph.prototype.nearestEdge = function (x, y) {
      var best = null;
      for (var i = 0; i < this.edges.length; i++) {
        var e = this.edges[i];
        if (e.dead) continue;
        var vx = e.bx - e.ax, vy = e.by - e.ay, L2 = vx * vx + vy * vy;
        if (L2 < 1e-9) continue;
        var t = ((x - e.ax) * vx + (y - e.ay) * vy) / L2;
        t = t < 0 ? 0 : (t > 1 ? 1 : t);
        var qx = e.ax + t * vx, qy = e.ay + t * vy;
        var d = Math.hypot(x - qx, y - qy);
        if (!best || d < best.d) best = { d: d, t: t, qx: qx, qy: qy, eid: i, e: e };
      }
      return best;
    };
    /** 把点吸附到最近路网边，必要时打断该边并插入新节点；返回节点 key 与吸附距离 */
    Graph.prototype.snap = function (x, y) {
      var sn = this.nearestEdge(x, y);
      if (!sn) return { key: null, dist: INF };
      var e = sn.e, t = sn.t;
      if (t < 1e-4) return { key: e.a, dist: sn.d };
      if (t > 1 - 1e-4) return { key: e.b, dist: sn.d };
      var ll = lonlat(sn.qx, sn.qy);
      var kk = ll[0].toFixed(7) + ',' + ll[1].toFixed(7);
      if (this.nodes[kk]) return { key: kk, dist: sn.d };   // 已有点，别重复打断
      var k = this.addNode(ll[0], ll[1]);
      e.dead = true;
      var self = this;
      [e.a, e.b].forEach(function (o) {
        var on = self.nodes[o];
        var ln = Math.hypot(sn.qx - on.x, sn.qy - on.y);
        if (ln >= 0.05) self.addEdge(k, o, e.hw);
      });
      this.adj[e.a] = this.adj[e.a].filter(function (p) { return p[1] !== sn.eid; });
      this.adj[e.b] = this.adj[e.b].filter(function (p) { return p[1] !== sn.eid; });
      return { key: k, dist: sn.d };
    };
    Graph.prototype.dijkstra = function (s) {
      var dist = {}, prev = {};
      dist[s] = 0; prev[s] = null;
      var pq = [];
      heapPush(pq, 0, s);
      while (pq.length) {
        var top = heapPop(pq), d = top[0], u = top[1];
        if (d > dist[u]) continue;
        var ad = this.adj[u] || [];
        for (var i = 0; i < ad.length; i++) {
          var v = ad[i][0], eid = ad[i][1], e = this.edges[eid];
          if (!e || e.dead) continue;
          var nd = d + e.w;
          if (dist[v] === undefined || nd < dist[v]) {
            dist[v] = nd; prev[v] = [u, eid]; heapPush(pq, nd, v);
          }
        }
      }
      return { dist: dist, prev: prev };
    };

    function buildRoadGraph() {
      var g = new Graph();
      for (var i = 0; i < B.roads.length; i++) {
        var r = B.roads[i], prev = null;
        for (var j = 0; j < r.pts.length; j++) {
          var p = r.pts[j], k = g.addNode(p[0], p[1]);
          if (prev !== null && prev !== k) g.addEdge(prev, k, r.hw);
          prev = k;
        }
      }
      return g;
    }

    /** 沿 prev 回溯出该终点的边序列 */
    function pathEdges(prev, target) {
      var out = [], cur = target, guard = 0;
      while (prev[cur] !== null && prev[cur] !== undefined && guard++ < 100000) {
        var p = prev[cur];
        out.push(p[1]); cur = p[0];
      }
      out.reverse();
      return out;
    }

    // ---------------- 求解 ----------------
    /**
     * @param opt {source:{lat,lon}|null, gates:[{name,lat,lon}], auto:bool,
     *             excluded:[id],
     *             scope:'all'|'picked',       // all=全校；picked=只连 pickedBuildings + extra
     *             pickedBuildings:[id],        // scope=picked 时要接入的建筑编号
     *             extra:[{lat,lon,label,demand,id}],
     *             sourceName:string}
     * @return 方案对象
     */
    function plan(opt) {
      opt = opt || {};
      var excluded = {};
      (opt.excluded || []).forEach(function (id) { excluded[id] = 1; });
      var scope = opt.scope || 'all';
      var picked = null;
      if (scope === 'picked') {
        picked = {};
        (opt.pickedBuildings || []).forEach(function (id) { picked[id] = 1; });
      }

      var g = buildRoadGraph();

      // 目标：有几何的供水建筑（可按编号排除 / 只取选中）
      var items = [];
      for (var i = 0; i < B.buildings.length; i++) {
        var b = B.buildings[i];
        if (!TARGET_CATS[b.cat]) continue;
        if (excluded[b.id]) continue;
        if (picked && !picked[b.id]) continue;   // 模式 C：没点的楼不进方案
        var sp = proj(b.lon, b.lat);
        var s = g.snap(sp[0], sp[1]);
        if (!s.key) continue;
        items.push({
          id: b.id, label: b.short || b.name, name: b.name, cat: b.cat,
          lat: b.lat, lon: b.lon, nid: s.key, demand: b.demand || 0,
          snap: s.dist, isBuilding: true
        });
      }
      var ne = 0;
      (opt.extra || []).forEach(function (p) {
        var pp = proj(p.lon, p.lat);
        var s2 = g.snap(pp[0], pp[1]);
        if (!s2.key) return;
        ne += 1;
        items.push({
          id: p.id || p.label || ('E' + ne), label: p.label || ('接入点 ' + ne),
          name: p.name || p.label || '接入点',
          cat: p.cat || 'other', lat: p.lat, lon: p.lon, nid: s2.key, demand: p.demand || 0,
          snap: s2.dist, isBuilding: !!p.isBuilding
        });
      });

      // ---- 合并落在同一路网节点上的目标 ----
      // 两个目标吸附到同一节点时，Kruskal 的完全图会出现「重复节点」，
      // 生成树永远少一条边。合并成一个节点、需水量相加。
      var byNid = {}, merged = [];
      items.forEach(function (it) {
        var prev = byNid[it.nid];
        if (!prev) { byNid[it.nid] = it; merged.push(it); return; }
        prev.demand += it.demand;
        prev.mergedIds = (prev.mergedIds || [prev.id]).concat(it.id);
        // 楼优先于临时接入点作为代表
        if (!prev.isBuilding && it.isBuilding) {
          prev.id = it.id; prev.label = it.label; prev.name = it.name;
          prev.cat = it.cat; prev.isBuilding = true;
        }
      });
      items = merged;

      // 距离缓存：同一个吸附节点只跑一次 Dijkstra
      var cache = {};
      function dij(k) {
        if (!cache[k]) cache[k] = g.dijkstra(k);
        return cache[k];
      }

      // ---- 选水源 ----
      //   opt.source  给了点 → 用该点
      //   opt.gates + opt.auto           → 在候选门里挑 MST 总长最小的
      //   opt.gates + opt.auto=false     → 用 gates[0]（模式 A：沿用主数据的默认水源）
      var srcRows = [], src = null, srcLabel = '';
      var gates = opt.gates || [];
      var autoPick = (opt.auto === undefined) ? true : !!opt.auto;
      if (opt.source) {
        var sp2 = proj(opt.source.lon, opt.source.lat);
        var ss = g.snap(sp2[0], sp2[1]);
        src = ss.key;
        srcLabel = opt.sourceName || '自定义起点';
      } else if (gates.length) {
        var bestTotal = INF, bestKey = null, bestName = '';
        var baseNids = items.map(function (it) { return it.nid; });
        for (var gi = 0; gi < gates.length; gi++) {
          var gt = gates[gi];
          var gp = proj(gt.lon, gt.lat);
          var gs = g.snap(gp[0], gp[1]);
          if (!gs.key) continue;
          var alln = [gs.key].concat(baseNids);
          var Dg = completeCost(alln, dij);
          var tot = mstTotal(alln, Dg);
          srcRows.push({ name: gt.name, lat: gt.lat, lon: gt.lon, total: tot, ok: tot < INF });
          if (tot < bestTotal) { bestTotal = tot; bestKey = gs.key; bestName = gt.name; }
        }
        if (autoPick) {
          src = bestKey; srcLabel = bestName || '默认水源';
        } else {
          var g0 = gates[0];
          var gp0 = proj(g0.lon, g0.lat);
          src = g.snap(gp0[0], gp0[1]).key;
          srcLabel = g0.name;
        }
        srcRows.sort(function (a, b) { return a.total - b.total; });
      }
      if (!src) return { ok: false, error: '水源吸附失败：该点附近没有可施工路网' };

      var srcNode = g.nodes[src];
      // 目标若就落在起点节点上，直接算已连通，不进生成树
      items = items.filter(function (it) { return it.nid !== src; });
      var allNodes = [src];
      items.forEach(function (it) {
        if (allNodes.indexOf(it.nid) < 0) allNodes.push(it.nid);
      });
      var D = completeCost(allNodes, dij);
      var mst = kruskal(allNodes, D);
      if (mst.length !== allNodes.length - 1) {
        return {
          ok: false,
          error: '有 ' + (allNodes.length - 1 - mst.length) + ' 个目标在路网上不可达，生成树不完整',
          unreachable: items.filter(function (it) { return D[src][it.nid] === undefined; })
        };
      }

      // ---- 树结构：从水源 BFS ----
      var tree = {};
      allNodes.forEach(function (n) { tree[n] = []; });
      mst.forEach(function (e) { tree[e.u].push([e.v, e.w]); tree[e.v].push([e.u, e.w]); });
      var depth = {}, par = {}, q = [src], qi = 0;
      depth[src] = 0; par[src] = null;
      while (qi < q.length) {
        var u = q[qi++];
        for (var ti = 0; ti < tree[u].length; ti++) {
          var v = tree[u][ti][0];
          if (depth[v] === undefined) { depth[v] = depth[u] + 1; par[v] = u; q.push(v); }
        }
      }

      // ---- 流量：每栋楼沿树上行，只加到它实际经过的管段一次 ----
      var eidFlow = {}, eidOrder = {};
      items.forEach(function (it) {
        var used = {}, cur = it.nid, guard = 0;
        while (par[cur] !== null && par[cur] !== undefined && guard++ < 10000) {
          var p = par[cur], d = depth[cur] || 0;
          var pe = pathEdges(dij(p).prev, cur);
          for (var k = 0; k < pe.length; k++) {
            var eid = pe[k];
            if (used[eid] === undefined || d < used[eid]) used[eid] = d;
          }
          cur = p;
        }
        for (var key in used) {
          eidFlow[key] = (eidFlow[key] || 0) + it.demand;
          eidOrder[key] = Math.min(eidOrder[key] === undefined ? 999 : eidOrder[key], used[key]);
        }
      });

      var pipes = [];
      for (var eidS in eidFlow) {
        var e2 = g.edges[+eidS];
        if (!e2) continue;
        var flow = eidFlow[eidS];
        var qLs = flow / (PEAK_HOURS * 3600.0);
        pipes.push({
          a: [g.nodes[e2.a].lon, g.nodes[e2.a].lat],
          b: [g.nodes[e2.b].lon, g.nodes[e2.b].lat],
          length: e2.len, wlen: e2.w, flow: flow, q_ls: qLs,
          dn: pickDN(qLs), order: eidOrder[eidS] === undefined ? 999 : eidOrder[eidS]
        });
      }

      var demand = items.reduce(function (s, it) { return s + it.demand; }, 0);
      var mstLen = mst.reduce(function (s, e) { return s + e.w; }, 0);
      var pipeLen = pipes.reduce(function (s, p) { return s + p.length; }, 0);
      var dnLen = {}, cost = 0;
      pipes.forEach(function (p) {
        dnLen[p.dn] = (dnLen[p.dn] || 0) + p.length;
        cost += p.length * (DN_COST[p.dn] || 500);
      });
      var deg = {};
      mst.forEach(function (e) {
        deg[e.u] = (deg[e.u] || 0) + 1; deg[e.v] = (deg[e.v] || 0) + 1;
      });
      var maxDepth = 0;
      for (var dn in depth) if (depth[dn] > maxDepth) maxDepth = depth[dn];

      return {
        ok: true,
        source: { key: src, lat: srcNode.lat, lon: srcNode.lon, name: srcLabel },
        srcRows: srcRows,
        items: items,
        nodeCount: allNodes.length,
        mst: mst,
        pipes: pipes,
        depth: depth,
        stats: {
          n_targets: items.length,
          mst_length_m: mstLen,
          pipe_length_m: pipeLen,
          total_demand_lpd: demand,
          total_demand_m3d: demand / 1000,
          q_total_ls: demand / (PEAK_HOURS * 3600.0),
          main_dn: pipes.reduce(function (m, p) { return Math.max(m, p.dn); }, 0),
          cost_yuan: cost,
          dn_len: dnLen,
          max_depth: maxDepth,
          n_branch: Object.keys(deg).filter(function (k) { return deg[k] >= 3; }).length,
          snap_max: items.reduce(function (m, it) { return Math.max(m, it.snap || 0); }, 0)
        },
        // 供矩阵页/演示页使用
        labels: [{
          idx: 0, id: '★水源', name: srcLabel + '（当前方案起点）',
          cat: 'source', lat: srcNode.lat, lon: srcNode.lon
        }].concat(items.map(function (it, i) {
          return {
            idx: i + 1, id: it.id, name: it.name, cat: it.cat,
            lat: it.lat, lon: it.lon
          };
        })),
        matrix: allNodes.map(function (a) {
          return allNodes.map(function (b2) {
            var dv = D[a][b2];
            return dv === undefined ? -1 : dv;
          });
        }),
        _dist: D,
        _nodeKeyByIndex: allNodes,
        graph: g
      };
    }

    /** 完全图距离矩阵：{nodeKey: {nodeKey: w}} */
    function completeCost(allNodes, dij) {
      var D = {};
      for (var i = 0; i < allNodes.length; i++) {
        var a = allNodes[i], da = dij(a).dist, row = {};
        for (var j = 0; j < allNodes.length; j++) {
          var b = allNodes[j], v = da[b];
          row[b] = v === undefined ? INF : v;
        }
        D[a] = row;
      }
      return D;
    }
    /** 完全图上 Kruskal，返回 {u,v,w} 列表 */
    function kruskal(allNodes, D) {
      var pairs = [];
      for (var i = 0; i < allNodes.length; i++) {
        for (var j = i + 1; j < allNodes.length; j++) {
          var w = D[allNodes[i]][allNodes[j]];
          if (w < INF) pairs.push([w, allNodes[i], allNodes[j]]);
        }
      }
      pairs.sort(function (x, y) { return x[0] - y[0]; });
      var par = {};
      allNodes.forEach(function (n) { par[n] = n; });
      function find(a) { while (par[a] !== a) { par[a] = par[par[a]]; a = par[a]; } return a; }
      var out = [];
      for (var k = 0; k < pairs.length; k++) {
        var ra = find(pairs[k][1]), rb = find(pairs[k][2]);
        if (ra !== rb) {
          par[ra] = rb;
          out.push({ u: pairs[k][1], v: pairs[k][2], w: pairs[k][0] });
          if (out.length === allNodes.length - 1) break;
        }
      }
      return out;
    }
    function mstTotal(allNodes, D) {
      var m = kruskal(allNodes, D);
      if (m.length !== allNodes.length - 1) return INF;
      return m.reduce(function (s, e) { return s + e.w; }, 0);
    }

    /** 目标建筑清单（按编号排序，供模式 B 的编号按钮使用） */
    function targets(opt) {
      opt = opt || {};
      var excluded = {};
      (opt.excluded || []).forEach(function (id) { excluded[id] = 1; });
      var out = [];
      for (var i = 0; i < B.buildings.length; i++) {
        var b = B.buildings[i];
        if (!TARGET_CATS[b.cat]) continue;
        out.push({
          id: b.id, name: b.name, short: b.short || b.name, cat: b.cat,
          levels: b.levels, area: b.area, demand: b.demand,
          lat: b.lat, lon: b.lon, excluded: !!excluded[b.id]
        });
      }
      return out;
    }

    /** 把方案导出成 graph_matrix.txt 同格式文本（给演示页/导出用） */
    function matrixText(res, headerLines) {
      if (!res || !res.ok) return '';
      var N = res.labels.length, out = [];
      (headerLines || []).forEach(function (l) { out.push('# ' + l); });
      out.push('# 权重：沿路网最短距离，按道路等级加权（单位 m）；-1 表示不可达');
      out.push('# N=' + N);
      out.push('#NODES');
      res.labels.forEach(function (L) {
        out.push(L.idx + '|' + L.id + '|' + L.name + '|' + L.cat + '|'
          + L.lat.toFixed(6) + '|' + L.lon.toFixed(6));
      });
      out.push('#MATRIX');
      for (var i = 0; i < N; i++) {
        var row = [];
        for (var j = 0; j < N; j++) {
          var v = res.matrix[i][j];
          row.push((v < 0 || v >= 1e17 || !isFinite(v)) ? '-1' : v.toFixed(2));
        }
        out.push(row.join(' '));
      }
      return out.join('\n') + '\n';
    }

    return {
      meta: M, buildings: B.buildings, bundle: B,
      proj: proj, lonlat: lonlat,
      plan: plan, targets: targets, matrixText: matrixText,
      pickDN: pickDN, kruskal: kruskal,
      TARGET_CATS: TARGET_CATS, HW_W: HW_W,
      DN_LIST: DN_LIST, DN_COST: DN_COST, DN_COL: DN_COL,
      CAT_COL: CAT_COL, CAT_NAME: CAT_NAME,
      KH: KH, PEAK_HOURS: PEAK_HOURS
    };
  }

  return {
    createEngine: createEngine,
    pickDN: pickDN,
    DN_LIST: DN_LIST, DN_COST: DN_COST, DN_COL: DN_COL,
    CAT_COL: CAT_COL, CAT_NAME: CAT_NAME, TARGET_CATS: TARGET_CATS,
    HW_W: HW_W, KH: KH, PEAK_HOURS: PEAK_HOURS
  };
});
