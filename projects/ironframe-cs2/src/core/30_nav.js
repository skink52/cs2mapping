// ===================================================================================================================
// IRONFRAME core, part 3: the arena heightfield and the nav grid (docs/INTERFACES.md section 2). Ground height is the
// bilinear heightfield away from struct cells; nearStruct() says where the world must be asked instead (a struct cell
// within 2 cells). Bots path with flow fields over `walk` (8-neighbour Dijkstra with a slope cost), cached per target
// cell; cover cells are scored against a threat position. No engine calls.
// ===================================================================================================================

class IF_Nav {
  constructor(nav, bounds) {
    const b = bounds || { min: [-7000, -7000, 0], max: [7000, 7000, 5000] };
    this.ok = !!(nav && nav.w > 0 && nav.h > 0 && Array.isArray(nav.height) && nav.height.length >= nav.w * nav.h);
    this.cell = this.ok ? nav.cell || 256 : 512;
    this.w = this.ok ? nav.w : Math.max(1, Math.ceil((b.max[0] - b.min[0]) / this.cell));
    this.h = this.ok ? nav.h : Math.max(1, Math.ceil((b.max[1] - b.min[1]) / this.cell));
    this.x0 = this.ok ? nav.x0 : b.min[0];
    this.y0 = this.ok ? nav.y0 : b.min[1];
    const n = this.w * this.h;
    this.n = n;
    this.hgt = new Float32Array(n); this.walkable = new Uint8Array(n); this.struct = new Uint8Array(n); this.near = new Uint8Array(n); this.cover = new Uint8Array(n);
    const floor = b.min[2];
    for (let i = 0; i < n; i++) {
      this.hgt[i] = this.ok ? IF_fin(+nav.height[i], floor) : floor;
      this.walkable[i] = this.ok && nav.walk ? (nav.walk[i] ? 1 : 0) : 1;
      this.struct[i] = this.ok && nav.struct ? (nav.struct[i] ? 1 : 0) : 0;
      this.cover[i] = this.ok && nav.cover ? IF_clamp(nav.cover[i] | 0, 0, 255) : 0;
    }
    // near: a struct cell within 2 cells (traces are needed there)
    for (let j = 0; j < this.h; j++) for (let i = 0; i < this.w; i++) {
      if (!this.struct[j * this.w + i]) continue;
      for (let dj = -2; dj <= 2; dj++) for (let di = -2; di <= 2; di++) {
        const ii = i + di, jj = j + dj;
        if (ii >= 0 && jj >= 0 && ii < this.w && jj < this.h) this.near[jj * this.w + ii] = 1;
      }
    }
    this.fields = new Map();      // target cell -> {dist: Float32Array, used}
    this.buildBudget = 2; this.buildsThisTick = 0;
    this.fieldUse = 0;
    this.maxFields = 64;
    this.builds = 0;
    this._heap = new Int32Array(n * 8 + 16); this._hk = new Float32Array(n * 8 + 16);
  }
  // ---- runtime world survey (the adapter calls probeStart once and probeStep every tick until it returns true). The map a
  // mapper edits in Hammer can differ from the baked arena data, so the ground, structures and walkable cells are measured
  // from the real collision: per cell one trace down from the ceiling (top surface) and one from just under it (a second
  // level below means a bridge or overhang). Until it finishes every cell counts as near a structure (always traced).
  probeStart(bounds) {
    const b = bounds || { min: [this.x0, this.y0, 0], max: [this.x0 + this.w * this.cell, this.y0 + this.h * this.cell, 5000] };
    this.pz0 = b.min[2]; this.pz1 = b.max[2]; this.pi = 0; this.probing = true;
    this.pTop = new Float32Array(this.n); this.pMulti = new Uint8Array(this.n); this.pVoid = new Uint8Array(this.n);
    this.near.fill(1); this.pTraces = 0;
  }
  probeStep(world, budget) {
    if (!this.probing) return true;
    if (!world || !world.traceLine) { this.probing = false; return true; }
    const a = { x: 0, y: 0, z: 0 }, b = { x: 0, y: 0, z: 0 }, deep = this.pz0 - 1500;
    let left = Math.max(2, budget | 0);
    while (this.pi < this.n && left >= 2) {
      const i = this.pi++, x = this.cx(i % this.w), y = this.cy((i / this.w) | 0);
      a.x = b.x = x; a.y = b.y = y; a.z = this.pz1 + 100; b.z = deep;
      const t1 = world.traceLine(a, b); left--; this.pTraces++;
      if (!t1 || !t1.hit || !t1.pos || !Number.isFinite(t1.pos.z)) { this.pVoid[i] = 1; this.pTop[i] = deep; continue; }
      const top = t1.pos.z; this.pTop[i] = top;
      a.z = top - 160; b.z = deep;
      const t2 = world.traceLine(a, b); left--; this.pTraces++;
      if (t2 && t2.hit && t2.pos && Number.isFinite(t2.pos.z) && top - t2.pos.z > 300) this.pMulti[i] = 1;
    }
    if (this.pi < this.n) return false;
    // finish: heights, structures (multi-level or a step over 200 u to a neighbour), near (2 cells), walkable, cover
    const w = this.w, h = this.h;
    for (let i = 0; i < this.n; i++) this.hgt[i] = this.pTop[i];
    this.struct.fill(0); this.near.fill(0); this.walkable.fill(0); this.cover.fill(0);
    for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
      const k = j * w + i, z = this.hgt[k];
      let maxStep = 0, higher = 0;
      for (let dj = -1; dj <= 1; dj++) for (let di = -1; di <= 1; di++) {
        if (!di && !dj) continue;
        const ii = i + di, jj = j + dj; if (ii < 0 || jj < 0 || ii >= w || jj >= h) continue;
        const d = this.hgt[jj * w + ii] - z; if (Math.abs(d) > maxStep) maxStep = Math.abs(d); if (d > 250) higher++;
      }
      if (this.pMulti[k] || maxStep > 200) this.struct[k] = 1;
      this.walkable[k] = this.pVoid[k] ? 0 : 1;
      this.cover[k] = Math.min(255, higher * 32);
    }
    for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
      if (!this.struct[j * w + i]) continue;
      for (let dj = -2; dj <= 2; dj++) for (let di = -2; di <= 2; di++) {
        const ii = i + di, jj = j + dj; if (ii >= 0 && jj >= 0 && ii < w && jj < h) this.near[jj * w + ii] = 1;
      }
    }
    this.fields.clear(); this.probing = false; this.ok = true;
    return true;
  }
  probeSummary() {
    let s = 0, v = 0, nr = 0; for (let i = 0; i < this.n; i++) { s += this.struct[i]; v += this.pVoid ? this.pVoid[i] : 0; nr += this.near[i]; }
    return this.n + ' cells, ' + s + ' structure, ' + nr + ' traced near structures, ' + v + ' void, ' + (this.pTraces || 0) + ' traces';
  }
  ci(x) { return IF_clamp(Math.floor((x - this.x0) / this.cell), 0, this.w - 1); }
  cj(y) { return IF_clamp(Math.floor((y - this.y0) / this.cell), 0, this.h - 1); }
  idx(x, y) { return this.cj(y) * this.w + this.ci(x); }
  cx(i) { return this.x0 + (i + 0.5) * this.cell; }
  cy(j) { return this.y0 + (j + 0.5) * this.cell; }
  // bilinear ground height between cell centres
  height(x, y) {
    const fx = IF_clamp((x - this.x0) / this.cell - 0.5, 0, this.w - 1), fy = IF_clamp((y - this.y0) / this.cell - 0.5, 0, this.h - 1);
    const i = Math.min(this.w - 2, Math.floor(fx)), j = Math.min(this.h - 2, Math.floor(fy));
    if (i < 0 || j < 0) return this.hgt[0];
    const tx = fx - i, ty = fy - j, w = this.w, H = this.hgt;
    const a = H[j * w + i], b = H[j * w + i + 1], c = H[(j + 1) * w + i], d = H[(j + 1) * w + i + 1];
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty;
  }
  nearStruct(x, y) { return this.near[this.idx(x, y)] === 1; }
  // The heightfield is the TOP surface of each cell: near a structure (a tower, a highway deck, a tunnel) the bilinear blend makes a
  // phantom ramp from the roof down to the street and says nothing about the space under a deck. Rounds, missiles and sight lines must not
  // collide with that (10 Nov 2026, Sprawl: rockets burst "on the roof" under decks and beside towers): with a world to trace, the
  // heightfield only counts away from structures (heightOpen = no ground there, rayFrac's `open`), and the trace decides near them.
  heightOpen(x, y) { return this.near[this.idx(x, y)] === 1 ? -1e9 : this.height(x, y); }
  walk(x, y) { return this.walkable[this.idx(x, y)] === 1; }
  coverAt(x, y) { return this.cover[this.idx(x, y)]; }
  // the nearest walkable cell index to (x, y) (spiral search, small radius)
  nearestWalk(x, y) {
    const i0 = this.ci(x), j0 = this.cj(y);
    for (let r = 0; r < 8; r++) for (let dj = -r; dj <= r; dj++) for (let di = -r; di <= r; di++) {
      if (Math.max(Math.abs(di), Math.abs(dj)) !== r) continue;
      const i = i0 + di, j = j0 + dj;
      if (i >= 0 && j >= 0 && i < this.w && j < this.h && this.walkable[j * this.w + i]) return j * this.w + i;
    }
    return j0 * this.w + i0;
  }
  // a goal cell snapped to a 3x3-cell block (fewer distinct flow fields; the last 400 u are walked straight)
  coarseGoal(x, y) {
    const i = this.ci(x), j = this.cj(y);
    const bi = Math.min(this.w - 1, i - (i % 3) + 1), bj = Math.min(this.h - 1, j - (j % 3) + 1);
    const c = bj * this.w + bi;
    return this.walkable[c] ? c : this.nearestWalk(this.cx(bi), this.cy(bj));
  }
  // flow field toward a target cell: Dijkstra cost per cell (Infinity where unreachable). Cached (LRU).
  // At most `buildBudget` new fields a tick (the owner resets `buildsThisTick` each tick): a burst of new goals (a round start, a
  // point captured) built ten fields in one tick, 10-40 ms in CS2's script engine (14 Nov 2026 timing test). Over budget: null,
  // and the caller walks straight at the goal this tick and asks again next tick.
  field(target) {
    let f = this.fields.get(target);
    if (f) { f.used = ++this.fieldUse; return f.dist; }
    if (this.buildsThisTick >= this.buildBudget) return null;
    this.buildsThisTick++;
    let dist = null;
    if (this.fields.size >= this.maxFields) {
      let oldK = -1, oldU = Infinity;
      for (const [k, v] of this.fields) if (v.used < oldU) { oldU = v.used; oldK = k; }
      dist = this.fields.get(oldK).dist;
      this.fields.delete(oldK);
    }
    const n = this.n, w = this.w, h = this.h, H = this.hgt, W = this.walkable;
    if (!dist) dist = new Float32Array(n);
    dist.fill(Infinity);
    const heap = this._heap, hk = this._hk; let hn = 0;
    const push = (i, k) => { let c = hn++; while (c > 0) { const p = (c - 1) >> 1; if (hk[p] <= k) break; heap[c] = heap[p]; hk[c] = hk[p]; c = p; } heap[c] = i; hk[c] = k; };
    const pop = () => {
      const top = heap[0], li = heap[--hn], lk = hk[hn]; let c = 0;
      for (;;) { let l = c * 2 + 1; if (l >= hn) break; if (l + 1 < hn && hk[l + 1] < hk[l]) l++; if (hk[l] >= lk) break; heap[c] = heap[l]; hk[c] = hk[l]; c = l; }
      heap[c] = li; hk[c] = lk; return top;
    };
    dist[target] = 0; push(target, 0);
    while (hn > 0) {
      const k0 = hk[0], cur = pop();
      if (k0 > dist[cur]) continue;
      const ci = cur % w, cj = (cur - ci) / w;
      for (let dj = -1; dj <= 1; dj++) for (let di = -1; di <= 1; di++) {
        if (!di && !dj) continue;
        const ni = ci + di, nj = cj + dj;
        if (ni < 0 || nj < 0 || ni >= w || nj >= h) continue;
        const nb = nj * w + ni;
        if (!W[nb]) continue;
        if (di && dj && (!W[cj * w + ni] || !W[nj * w + ci])) continue;   // no corner cutting
        const climb = Math.abs(H[nb] - H[cur]);
        if (climb > this.cell * 1.2) continue;                             // a cliff: jump-only, not a path
        const nd = dist[cur] + (di && dj ? 1.414 : 1) + climb / this.cell * 2;
        if (nd < dist[nb]) { dist[nb] = nd; if (hn < heap.length - 1) push(nb, nd); }
      }
    }
    this.builds++;
    this.fields.set(target, { dist, used: ++this.fieldUse });
    return dist;
  }
  // the direction (unit, xy) to follow from (x, y) toward the target cell, into o; returns false when unreachable / there
  flowDir(target, x, y, o) {
    const dist = this.field(target), w = this.w, h = this.h;
    if (!dist) return false;
    let cur = this.idx(x, y);
    if (!(dist[cur] < Infinity)) cur = this.nearestWalk(x, y);
    if (!(dist[cur] < Infinity)) return false;
    if (cur === target) { o.x = this.cx(target % w) - x; o.y = this.cy((target / w) | 0) - y; const l = Math.hypot(o.x, o.y); if (l < 1) return false; o.x /= l; o.y /= l; return true; }
    const ci = cur % w, cj = (cur - ci) / w;
    let best = cur, bd = dist[cur];
    for (let dj = -1; dj <= 1; dj++) for (let di = -1; di <= 1; di++) {
      const ni = ci + di, nj = cj + dj;
      if (ni < 0 || nj < 0 || ni >= w || nj >= h) continue;
      const nb = nj * w + ni;
      if (dist[nb] < bd) { bd = dist[nb]; best = nb; }
    }
    // look one more step ahead for a smoother line
    const bi = best % w, bj = (best - bi) / w;
    let best2 = best, bd2 = bd;
    for (let dj = -1; dj <= 1; dj++) for (let di = -1; di <= 1; di++) {
      const ni = bi + di, nj = bj + dj;
      if (ni < 0 || nj < 0 || ni >= w || nj >= h) continue;
      const nb = nj * w + ni;
      if (dist[nb] < bd2) { bd2 = dist[nb]; best2 = nb; }
    }
    const tgt = (best2 !== best && Math.abs(this.hgt[best2] - this.hgt[cur]) < this.cell) ? best2 : best;
    o.x = this.cx(tgt % w) - x; o.y = this.cy((tgt / w) | 0) - y;
    const l = Math.hypot(o.x, o.y);
    if (l < 1) return false;
    o.x /= l; o.y /= l;
    return true;
  }
  // path cost (cells) from (x, y) to the target cell, Infinity when unreachable
  pathCost(target, x, y) { const d = this.field(target); if (!d) return Infinity; const c = this.idx(x, y); return d[c] < Infinity ? d[c] : d[this.nearestWalk(x, y)]; }
  // the best cover cell within `radius` of (x, y) against a threat at t: cover value, terrain between, distance; into o
  findCover(x, y, tx, ty, tz, radius, o) {
    const r = Math.ceil(radius / this.cell), i0 = this.ci(x), j0 = this.cj(y), w = this.w;
    let best = -1, bs = -Infinity;
    for (let dj = -r; dj <= r; dj++) for (let di = -r; di <= r; di++) {
      const i = i0 + di, j = j0 + dj;
      if (i < 0 || j < 0 || i >= w || j >= this.h) continue;
      const c = j * w + i;
      if (!this.walkable[c]) continue;
      const px = this.cx(i), py = this.cy(j), pz = this.hgt[c];
      const away = Math.hypot(px - tx, py - ty);
      // something higher than the cell's mech-chest line between it and the threat, sampled at 1/3 and 2/3
      let blocked = 0;
      for (let k = 1; k <= 2; k++) {
        const f = k / 3, sx = px + (tx - px) * f * 0.5, sy = py + (ty - py) * f * 0.5;
        const line = pz + 180 + (tz - pz - 180) * f * 0.5;
        if (this.height(sx, sy) > line) blocked++;
      }
      const s = this.cover[c] / 255 * 2 + blocked * 1.5 + Math.min(away, 4000) / 4000 - Math.hypot(px - x, py - y) / (radius + 1);
      if (s > bs) { bs = s; best = c; }
    }
    if (best < 0) return false;
    o.x = this.cx(best % w); o.y = this.cy((best / w) | 0); o.z = this.hgt[best];
    return true;
  }
  // ray against the heightfield, sampled every `step` units: the first fraction below the ground (1 = clear)
  rayFrac(ax, ay, az, bx, by, bz, step, open) {
    const dx = bx - ax, dy = by - ay, dz = bz - az, len = Math.sqrt(dx * dx + dy * dy + dz * dz);
    const n = Math.max(1, Math.ceil(len / (step || 128)));
    let prevAbove = open && this.near[this.idx(ax, ay)] ? 1e6 : az - this.height(ax, ay);
    for (let k = 1; k <= n; k++) {
      const t = k / n, x = ax + dx * t, y = ay + dy * t, z = az + dz * t;
      const above = open && this.near[this.idx(x, y)] ? 1e6 : z - this.height(x, y);   // open: structures are the world trace's job
      if (above < 0) { const tt = (k - 1 + prevAbove / Math.max(1e-6, prevAbove - above)) / n; return IF_clamp(tt, 0, 1); }
      prevAbove = above;
    }
    return 1;
  }
  // does the segment pass over a near-struct cell (a world trace is needed for it)?
  segNearStruct(ax, ay, bx, by) {
    const dx = bx - ax, dy = by - ay, len = Math.sqrt(dx * dx + dy * dy);
    const n = Math.max(1, Math.ceil(len / (this.cell * 0.75)));
    for (let k = 0; k <= n; k++) { const t = k / n; if (this.near[this.idx(ax + dx * t, ay + dy * t)]) return true; }
    return false;
  }
}
