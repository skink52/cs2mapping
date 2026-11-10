// ===================================================================================================================
// IRONFRAME CS2 adapter, part 1b: arena copies. A map may hold identical copies of its arena: `ifr_arena_2` (.._4)
// info_targets mark them. The offset of copy k is measured from marker pairs (the mapper's duplicated ifr_drop_* /
// ifr_point_* / ifr_flag_* entities: same name, one in each copy), else taken from ifr_arena_k minus ifr_arena_1 (or the
// origin). Each copy runs its own core game (own mode, score, AI; AI slots 64 + 64 k); IfrArenas routes every call by
// player, so the rest of the adapter keeps calling `game.<method>` as with one game.
// Load: up to SPLIT_AT (22) humans play in one copy; above that the humans are dealt evenly over ceil(n / SPLIT_AT) copies at
// round start (T and CT dealt separately so every copy stays balanced); late joiners go to the active copy with fewest.
// ===================================================================================================================
const IFR_SPLIT_AT = 22;   // max humans per arena copy (skink52, 10 Nov 2026: 22 per arena, 3 copies for 64)

function ifrShiftArena(src, off, k) {
  const a = JSON.parse(JSON.stringify(src));
  const sh = (p) => (p ? [p[0] + off.x, p[1] + off.y, p[2] + off.z].concat(p.slice(3)) : p);
  a.id = (src.id || 'arena') + (k ? '_' + (k + 1) : '');
  if (a.bounds) { a.bounds.min = sh(a.bounds.min); a.bounds.max = sh(a.bounds.max); }
  if (a.drops) for (const t of Object.keys(a.drops)) a.drops[t] = (a.drops[t] || []).map(sh);
  for (const p of a.points || []) p.pos = sh(p.pos);
  if (a.flags) { a.flags.t = sh(a.flags.t); a.flags.ct = sh(a.flags.ct); }
  if (a.nav) { a.nav.x0 += off.x; a.nav.y0 += off.y; if (Array.isArray(a.nav.height)) a.nav.height = a.nav.height.map((h) => h + off.z); }
  if (a.landmarks) for (const l of a.landmarks) l.pos = sh(l.pos);
  return a;
}

class IfrArenas {
  constructor(opts) {
    /** @type {{g:any, k:number, off:{x:number,y:number,z:number}, arena:any, active:boolean, done:boolean, humans:number}[]} */
    this.list = [];
    this.slotArena = new Map();      // human / pawn-bot slot -> arena index
    this.plan = null;                // slot -> arena index for the round being started
    this.events = [];
    this.garage = null;
    const offs = ifrArenaOffsets();
    for (let k = 0; k < offs.length; k++) {
      const arena = k === 0 ? opts.arena : ifrShiftArena(opts.arena, offs[k], k);
      ifrArenaMarkers(arena, k, offs);
      const cfg = Object.assign({}, opts.cfg, { npcSlot0: 64 + 64 * k });
      const g = new IF_Game({ parts: opts.parts, arena, cfg, world: opts.world, rng: opts.rng });
      this.list.push({ g, k, off: offs[k], arena, active: k === 0, done: false, humans: 0 });
    }
    this.garage = this.list[0].g.garage;
    const self = this;
    // one Map-like view over every copy's mechs (slots are unique across copies)
    this.mechs = {
      get(slot) { for (const a of self.list) { const m = a.g.mechs.get(slot); if (m) return m; } return undefined; },
      has(slot) { return !!this.get(slot); },
      *values() { for (const a of self.list) yield* a.g.mechs.values(); },
      get size() { let n = 0; for (const a of self.list) n += a.g.mechs.size; return n; },
    };
  }
  get count() { return this.list.length; }
  get projectiles() { return this.cat('projectiles'); }
  get missiles() { return this.cat('missiles'); }
  get beams() { return this.cat('beams'); }
  get effects() { return this.cat('effects'); }
  cat(key) { if (this.list.length === 1) return this.list[0].g[key]; const out = []; for (const a of this.list) for (const o of a.g[key]) out.push(o); return out; }
  get match() { return this.list[0].g.match; }
  get nav() { return this.list[0].g.nav; }
  arenaIndexOf(slot) {
    const k = this.slotArena.get(slot); if (k !== undefined) return k;
    for (const a of this.list) if (a.g.mechs.has(slot)) return a.k;
    return 0;
  }
  of(slot) { return this.list[this.arenaIndexOf(slot)].g; }
  matchFor(slot) { return this.of(slot).match; }
  arenaFor(slot) { return this.list[this.arenaIndexOf(slot)].arena; }
  sameArena(a, b) { return this.arenaIndexOf(a) === this.arenaIndexOf(b); }
  // ---- load: deal the humans over the copies at round start
  planRound(people) {
    const n = people.length, want = Math.max(1, Math.min(this.list.length, Math.ceil(n / IFR_SPLIT_AT)));
    this.plan = new Map();
    const t = people.filter((p) => p.team === 2), ct = people.filter((p) => p.team !== 2);
    t.forEach((p, i) => this.plan.set(p.slot, i % want)); ct.forEach((p, i) => this.plan.set(p.slot, (i + t.length) % want));
    for (const a of this.list) { a.active = a.k < want; a.done = false; a.humans = 0; }
    for (const k of this.plan.values()) this.list[k].humans++;
    return want;
  }
  pickArenaForJoin() {
    let best = 0, bh = Infinity;
    for (const a of this.list) if (a.active && a.humans < bh) { bh = a.humans; best = a.k; }
    return best;
  }
  // ---- the core API, routed
  addPlayer(slot, info) {
    let k = this.plan && this.plan.has(slot) ? this.plan.get(slot) : this.slotArena.get(slot);
    if (k === undefined || !this.list[k].active) { k = this.pickArenaForJoin(); if (info && info.human !== false) this.list[k].humans++; }
    const prev = this.slotArena.get(slot);
    if (prev !== undefined && prev !== k) this.list[prev].g.removePlayer(slot);
    this.slotArena.set(slot, k);
    return this.list[k].g.addPlayer(slot, info);
  }
  removePlayer(slot) { const k = this.slotArena.get(slot); if (k !== undefined) { this.list[k].g.removePlayer(slot); this.slotArena.delete(slot); } }
  setInput(slot, inp) { return this.of(slot).setInput(slot, inp); }
  requestSpawn(slot) { return this.of(slot).requestSpawn(slot); }
  setLoadout(slot, l) { return this.of(slot).setLoadout(slot, l); }
  setPilot(slot, p) { for (const a of this.list) a.g.setPilot(slot, p); }
  pilotSummary(slot) { return this.of(slot).pilotSummary(slot); }
  pilotStats(slot) { return this.of(slot).pilotStats(slot); }
  leaveMech(slot) { const g = this.of(slot); return g.leaveMech ? g.leaveMech(slot) : undefined; }
  killMech(slot, killer) { const g = this.of(slot); return g.killMech ? g.killMech(slot, killer) : undefined; }
  vote(slot, arg) { return this.of(slot).vote(slot, arg); }
  pickMode(humans) { return this.list[0].g.pickMode(this.list[0].humans || humans); }
  setMode(mode, humans) {
    for (const a of this.list) { if (!a.active) continue; a.g.setMode(a.k === 0 ? mode : a.g.pickMode(a.humans), a.humans); }
  }
  startRound(now) { for (const a of this.list) if (a.active) a.g.startRound(now); }   // the plan stays until the next planRound (players are added after this)
  endRound() { for (const a of this.list) if (a.active && a.g.match.phase === 'running') a.g.endRound(true); }
  reset() { for (const a of this.list) if (a.g.reset) a.g.reset(); this.slotArena.clear(); }
  tick(dt, now) {
    for (const a of this.list) {
      if (!a.active) continue;
      a.g.tick(dt, now);
      const ev = a.g.events;
      for (let i = 0; i < ev.length; i++) { ev[i].arena = a.k; this.events.push(ev[i]); }
      ev.length = 0;
    }
  }
  // ---- the runtime world survey, one copy after the other
  probeStart() { this.probeK = 0; for (const a of this.list) if (a.g.nav.probeStart) a.g.nav.probeStart(a.arena.bounds); }
  probeStep(world, budget) {
    while (this.probeK < this.list.length) { if (this.list[this.probeK].g.nav.probeStep(world, budget) === false) return false; this.probeK++; }
    return true;
  }
  probeSummary() { return this.list.map((a, i) => 'arena ' + (i + 1) + ': ' + (a.g.nav.probeSummary ? a.g.nav.probeSummary() : '')).join(' | '); }
  // all active copies finished their round?
  allDone() { for (const a of this.list) if (a.active && !a.done) return false; return true; }
  winner() {
    const s = { 2: 0, 3: 0 }; for (const a of this.list) if (a.active && (a.g.match.winner === 2 || a.g.match.winner === 3)) s[a.g.match.winner]++;
    return s[2] > s[3] ? 2 : s[3] > s[2] ? 3 : 0;
  }
}

// offsets of the arena copies: [ {0,0,0}, copy 2, ... ]
function ifrArenaOffsets() {
  const offs = [v3(0, 0, 0)];
  const base = ifrFind('ifr_arena_1');
  const b0 = base ? base.GetAbsOrigin() : v3(0, 0, 0);
  for (let k = 2; k <= 4; k++) {
    const e = ifrFind('ifr_arena_' + k); if (!e) break;
    let off = vsub(e.GetAbsOrigin(), b0);
    // the duplicated markers measure it exactly: median delta of same-named pairs, the copy being the one nearer e
    const deltas = [];
    for (const name of ifrMarkerNames()) {
      const ents = ifrFindAll(name); if (ents.length < 2) continue;
      const ps = ents.map((x) => x.GetAbsOrigin()).sort((p, q) => vdist(p, vadd(b0, off)) - vdist(q, vadd(b0, off)));
      const orig = ents.map((x) => x.GetAbsOrigin()).sort((p, q) => vdist(p, b0) - vdist(q, b0))[0];
      if (ps[0] !== orig) deltas.push(vsub(ps[0], orig));
    }
    if (deltas.length >= 3) { const med = (key) => deltas.map((d) => d[key]).sort((x, y) => x - y)[deltas.length >> 1]; off = v3(med('x'), med('y'), med('z')); }
    offs.push(off);
    log('arena copy ' + k + ': offset ' + Math.round(off.x) + ' ' + Math.round(off.y) + ' ' + Math.round(off.z) + (deltas.length >= 3 ? ' (from ' + deltas.length + ' marker pairs)' : ' (from ifr_arena_' + k + ')'));
  }
  return offs;
}
function ifrMarkerNames() {
  const out = [];
  for (const t of ['t', 'ct', 'ffa']) for (let i = 0; i <= 32; i++) out.push(CONFIG.DROP_PREFIX + t + '_' + i);
  for (const p of ['A', 'B', 'C', 'D', 'E']) out.push(CONFIG.POINT_PREFIX + p, CONFIG.POINT_PREFIX + p + '_edge');
  out.push('ifr_flag_t', 'ifr_flag_ct');
  return out;
}
// the markers inside copy k's bounds win over the baked arena data (the mapper moves them in Hammer)
function ifrArenaMarkers(arena, k, offs) {
  const b = arena.bounds;
  const inside = (o) => o.x >= b.min[0] - 2000 && o.x <= b.max[0] + 2000 && o.y >= b.min[1] - 2000 && o.y <= b.max[1] + 2000 && o.z >= b.min[2] - 2500 && o.z <= b.max[2] + 2000;
  const pick = (name) => { for (const e of ifrFindAll(name)) { const o = e.GetAbsOrigin(); if (inside(o)) return e; } return undefined; };
  const drops = { t: [], ct: [], ffa: [] };
  for (const t of ['t', 'ct', 'ffa']) for (let i = 0; i <= 32; i++) { const e = pick(CONFIG.DROP_PREFIX + t + '_' + i); if (e) { const o = e.GetAbsOrigin(), a = e.GetAbsAngles(); drops[t].push([o.x, o.y, o.z, a.yaw]); } }
  let n = 0; for (const t of ['t', 'ct', 'ffa']) if (drops[t].length) { arena.drops[t] = drops[t]; n += drops[t].length; }
  // zones (docs/ARENAS.md "Objective markers", shared with the SlimeMG plugin): ifr_point_<A..E> at the centre, an optional
  // ifr_point_<ID>_edge on the edge sets the radius (else 700 / the baked value). When the map has any zone marker, the map's
  // set replaces the baked list (a new point E placed in Hammer counts; a deleted one goes).
  const pts = [];
  for (const id of ['A', 'B', 'C', 'D', 'E']) {
    const e = pick(CONFIG.POINT_PREFIX + id); if (!e) continue;
    const o = e.GetAbsOrigin(), baked = (arena.points || []).find((q) => q.id === id);
    const ed = pick(CONFIG.POINT_PREFIX + id + '_edge');
    let radius = (baked && baked.radius) || 700;
    if (ed) { const eo = ed.GetAbsOrigin(), r = Math.hypot(eo.x - o.x, eo.y - o.y); if (r >= 32 && r <= 10000) radius = Math.round(r); }
    pts.push({ id, pos: [o.x, o.y, o.z], radius, edge: !!ed });
  }
  const p = pts.length; if (p) arena.points = pts;
  const ft = pick('ifr_flag_t'), fc = pick('ifr_flag_ct');
  if (ft && fc) { const a = ft.GetAbsOrigin(), c = fc.GetAbsOrigin(); arena.flags = { t: [a.x, a.y, a.z], ct: [c.x, c.y, c.z] }; }
  log('arena ' + (k + 1) + ': ' + n + ' drop points, ' + p + ' objectives' + (ft && fc ? ', flags' : '') + ' from the map');
}
