// ===================================================================================================================
// IRONFRAME core, part 8: the game. IF_Game owns the mechs, pools, rounds and modes (DESIGN.md section 6): Team Battle,
// Conquest (three points, tickets), Skirmish (free for all) and Sortie (co-op waves, beacon, boss phases). Spawning
// drops from the arena's drop points (rejected when an enemy is within 2 500 u), NPC mechs (slots 64+) for AI fill and
// Sortie enemies, the mode pick and vote, team balance by rating, the round summary. API: docs/INTERFACES.md section 3.
// ===================================================================================================================

function IF_mulberry(seed) {
  let a = seed >>> 0;
  return function () { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

// Team balance by rating: [{slot, rating}] -> {2: [slots], 3: [slots], sum2, sum3, diff (fraction)}; sizes differ by <= 1
function IF_balanceTeams(list) {
  const s = list.slice().sort((a, b) => (b.rating - a.rating) || (a.slot - b.slot));
  const out = { 2: [], 3: [], sum2: 0, sum3: 0, diff: 0 };
  const half = Math.ceil(s.length / 2);
  for (const p of s) {
    const to = (out[2].length >= half) ? 3 : (out[3].length >= half) ? 2 : (out.sum2 <= out.sum3 ? 2 : 3);
    out[to].push(p.slot); if (to === 2) out.sum2 += p.rating; else out.sum3 += p.rating;
  }
  // swap pass: improve the sum difference with one-for-one swaps
  const r = new Map(list.map((p) => [p.slot, p.rating]));
  for (let it = 0; it < 4; it++) {
    let best = null, bd = Math.abs(out.sum2 - out.sum3);
    for (const a of out[2]) for (const b of out[3]) {
      const d = Math.abs((out.sum2 - r.get(a) + r.get(b)) - (out.sum3 - r.get(b) + r.get(a)));
      if (d < bd - 1e-9) { bd = d; best = [a, b]; }
    }
    if (!best) break;
    const [a, b] = best;
    out[2][out[2].indexOf(a)] = b; out[3][out[3].indexOf(b)] = a;
    out.sum2 += r.get(b) - r.get(a); out.sum3 += r.get(a) - r.get(b);
  }
  out.diff = Math.abs(out.sum2 - out.sum3) / Math.max(1, Math.max(out.sum2, out.sum3));
  return out;
}

class IF_Game {
  constructor(opts) {
    opts = opts || {};
    const parts = opts.parts || PARTS, arena = opts.arena || ARENA;
    this.P = IF_indexParts(parts); this.arena = arena;
    this.cfg = IF_mergeCfg(IF_DEFAULT_CFG, opts.cfg || {});
    this.move = Object.assign({}, parts.move, this.cfg.move || {});
    this.world = opts.world || null;
    this.rng = typeof opts.rng === 'function' ? opts.rng : IF_mulberry(opts.seed || 12345);
    this.nav = new IF_Nav(arena.nav, arena.bounds);
    this.grid = new IF_Grid(arena.bounds);
    this.mechs = new Map(); this.alive = []; this.events = [];
    this.bullets = new IF_Bullets(IF_MAX_BULLETS);
    this.projectiles = []; for (let i = 0; i < IF_MAX_BULLETS; i++) this.projectiles.push({ alive: false, pos: IF_v3(), dir: IF_v3(1, 0, 0), heavy: false, kind: 'proj', slot: -1 });
    this.missiles = []; for (let i = 0; i < IF_MAX_MISSILES; i++) this.missiles.push({ alive: false, pos: IF_v3(), dir: IF_v3(1, 0, 0), slot: -1, target: -1, side: 0, wid: 0, key: '', wp: null,
      speed: 0, maxSpeed: 0, accel: 0, turn: 0, dmg: 0, impact: 0, life: 0, age: 0, loft: 0, loftZ: 0, lofting: false, warned: false, range: 0, broke: false, aim: IF_v3() });
    this.beams = []; for (let i = 0; i < IF_MAX_BEAMS; i++) this.beams.push({ alive: false, from: IF_v3(), to: IF_v3(), red: false, slot: -1, life: 0, w: 1 });
    this.effects = []; for (let i = 0; i < IF_MAX_EFFECTS; i++) this.effects.push({ alive: false, kind: 'ring', pos: IF_v3(), radius: 0, slot: -1, life: 0, hp: 0, side: 0, follow: -1, idx: 0, t: 0, wpi: -1, dmg: 0 });
    this.bubbleCount = 0;
    this.garage = new IF_Garage(this);
    this.match = { mode: 'tb', phase: 'over', timeLeft: 0, scores: { 2: 0, 3: 0 }, tickets: { 2: 0, 3: 0 }, points: [], killTarget: 0, winner: 0, podium: [],
      hill: -1, hillT: 0, khAcc: 0, /** @type {any} */ flags: null, /** @type {any[]} */ allPoints: [],
      wave: 0, waves: 0, enemiesLeft: 0, beaconLoss: 0, leader: -1, warmup: 0 };
    this.votes = new Map(); this.lastMode = ''; this.humans = 0;
    this.squads = new Map(); this.pendingLoadouts = new Map(); this.pendingPilots = new Map();
    // the last pilot record given per slot (server or stand-alone garage); survives reset() so a round restart keeps a stand-alone
    // pilot's garage upgrades (the adapter passes pe.pilot, null stand-alone); dropped with removePlayer
    this.keptPilots = new Map();
    this.fillAdj = 0;   // how the humans fare against the AI fill (50_ai.js fillSkill); survives reset() like the pilots
    this.time = 0; this.now = 0; this.tickN = 0; this.combatOn = false; this.eventsFx = true;
    this.so = { state: 'pause', pauseT: 0, toSpawn: 0, spawnT: 0, boss: false, lost: false, done: false };
    this.npcSlot0 = IF_clamp((this.cfg && this.cfg.npcSlot0) || IF_NPC_SLOT0, IF_NPC_SLOT0, IF_MAX_MECHS - 64);
    this.cqAcc = 0; this.fillAcc = 0; /** @type {any[]} */ this.objFx = []; /** @type {any} */ this.hillFx = null;
    this.stats = { traces: 0, traceLines: 0, traceSpheres: 0, mechTicks: 0, ticks: 0, missiles: 0, missileDrops: 0, missileDodges: 0, airbursts: 0, weakHits: 0,
      aiUnstuck: 0, eventsDropped: 0, spawns: 0, deaths: 0 };
    // scratch vectors (no allocation in the hot loops)
    this._ta = IF_v3(); this._tb = IF_v3(); this._dir = IF_v3(1, 0, 0); this._aimPt = IF_v3(); this._lead = IF_v3(); this._mz = IF_v3(); this._spr = IF_v3();
    this._to = IF_v3(); this._hp = IF_v3(); this._src = IF_v3(); this._lag = IF_v3(); this._v1 = IF_v3(); this._aiAim = IF_v3(); this._aiDir = IF_v3(); this._hitT = 0;
    this._weak = { n: 0, s: [0, 1, 2, 3].map(() => ({ x: 0, y: 0, z: 0, r: 0 })) };
  }

  // ---------------------------------------------------------------------------------------------------------- world
  trace(a, b) {
    this.stats.traces++; this.stats.traceLines++;
    try { return this.world.traceLine(a, b); } catch (err) { return null; }
  }
  traceSphere(a, b, r) {
    this.stats.traces++; this.stats.traceSpheres++;
    try { return this.world.traceSphere(a, b, r); } catch (err) { return null; }
  }
  emit(ev) {
    if (this.events.length >= 20000) { this.events.splice(0, 5000); this.stats.eventsDropped += 5000; }
    this.events.push(ev);
  }
  side(m) { const mo = this.match.mode; return mo === 'sk' ? 100 + m.slot : mo === 'so' ? (m.team === 0 ? 1 : 0) : m.team; }
  enemies(a, b) { return a !== b && this.side(a) !== this.side(b); }
  humanCount() { let n = 0; for (const m of this.mechs.values()) if (m.human) n++; return n; }

  // ---------------------------------------------------------------------------------------------------------- modes and votes
  pickMode(humans, votes) {
    if (humans === undefined) humans = this.humanCount();
    const tally = { tb: 0, cq: 0, sk: 0, so: 0, kh: 0, ctf: 0 };
    const src = votes || this.votes;
    for (const v of (src instanceof Map ? src.values() : Object.values(src || {}))) if (tally[v] !== undefined) tally[v]++;
    let allowed;
    if (humans <= 5) allowed = ['so', 'sk'];
    else if (humans <= 16) allowed = ['tb', 'cq', 'sk', 'kh', 'ctf'];
    else allowed = ['tb', 'cq', 'kh', 'ctf'];
    // the operator's rotation (SlimeMG.json IronFrame.Rules.ModeRotation -> IF_Career.setRules) replaces the map's own choice by head count
    const rot = IF_Career.rotationPick(this.lastMode, tally);
    if (rot) return rot;
    let best = '', bv = 0;
    for (const k of allowed) if (tally[k] > bv) { bv = tally[k]; best = k; }
    if (!best) best = humans <= 5 ? 'so' : (this.lastMode === 'tb' ? 'cq' : 'tb');
    return best;
  }
  vote(slot, arg) {
    const a = String(arg || '').toLowerCase().trim();
    const map = { tb: 'tb', team: 'tb', battle: 'tb', tdm: 'tb', cq: 'cq', conquest: 'cq', sk: 'sk', skirmish: 'sk', ffa: 'sk', so: 'so', sortie: 'so', coop: 'so', 'co-op': 'so', kh: 'kh', koth: 'kh', hill: 'kh', ctf: 'ctf', flag: 'ctf', flags: 'ctf', dom: 'cq', domination: 'cq', deathmatch: 'tb' };
    const k = map[a];
    if (!k) return 'Vote: !vote tdm | cq | kh | ctf | ffa | so';
    this.votes.set(slot, k);
    const n = Array.from(this.votes.values()).filter((v) => v === k).length;
    return 'Vote for ' + IF_MODE_NAMES[k] + ' noted (' + n + ' vote' + (n === 1 ? '' : 's') + ')';
  }
  setMode(mode, humans) {
    if (IF_MODES.indexOf(mode) < 0) mode = 'tb';
    this.match.mode = mode; this.lastMode = mode;
    if (humans !== undefined) this.humans = humans | 0;
    const T = this.cfg.tb;
    this.match.killTarget = mode === 'tb' ? IF_clamp(this.humans * T.killsPerHuman, T.killMin, T.killMax) : mode === 'sk' ? this.cfg.sk.target : 0;
  }
  startRound(now) {
    const C = this.cfg, M = this.match, mode = M.mode;
    if (Number.isFinite(now)) this.now = now;
    // NPCs go, pools empty, everyone waits to drop in
    for (const [s, m] of Array.from(this.mechs)) if (m.npc) this.mechs.delete(s);
    this.clearPools();
    this.squads.clear();
    M.phase = C.round.warmup > 0 ? 'warmup' : 'running'; M.warmup = C.round.warmup;
    M.timeLeft = (IF_RULES && IF_RULES.roundS) || C.round[mode] || 600; M.scores = { 2: 0, 3: 0 }; M.winner = 0; M.podium = []; M.podiumInfo = []; M.leader = -1;
    M.tickets = { 2: mode === 'cq' ? C.cq.tickets : 0, 3: mode === 'cq' ? C.cq.tickets : 0 };
    M.points = (mode === 'cq' || mode === 'so') ? (this.arena.points || []).map((p, i) => ({ id: p.id || String.fromCharCode(65 + i), pos: IF_v3(p.pos[0], p.pos[1], p.pos[2]),
      radius: p.radius || 700, owner: 0, progress: 0, value: 0, capTeam: 0, contested: false })) : [];
    if (mode === 'so' && M.points.length > 1) M.points = [M.points[1]];   // the beacon
    if (mode === 'so' && M.points.length) { M.points[0].owner = 2; M.points[0].value = -1; M.points[0].progress = 1; M.points[0].capTeam = 2; }
    M.wave = 0; M.waves = mode === 'so' ? C.so.waves : 0; M.enemiesLeft = 0; M.beaconLoss = 0;
    M.khTarget = C.kh ? C.kh.target : 0; M.ctfCaptures = C.ctf ? C.ctf.captures : 0;   // the round's targets for the HUD's objective line
    /** @type {any} */ (this).objectivesInit(mode);
    /** @type {any} */ (this).featInit(mode);
    this.so = { state: 'pause', pauseT: 3, toSpawn: 0, spawnT: 0, boss: false, lost: false, done: false };
    this.combatOn = M.phase === 'running';
    this.votes.clear();
    let k = 0;
    for (const m of this.mechs.values()) {
      m.alive = false; m.deathT = 0; m.respawnT = 0; m.streak = 0; m.healLeft = 0; m.dmgBy.fill(0);
      for (const key in m.sum) m.sum[key] = typeof m.sum[key] === 'boolean' ? false : 0;
      m.wsum = {};
      if (!m.human) { m.wantSpawn = true; if (!m.ai) IF_Ai.attach(this, m, IF_Ai.fillTier(this)); this.assignSquad(m, k++); }
    }
  }
  clearPools() {
    this.bullets.clear();
    for (const o of this.projectiles) o.alive = false;
    for (const o of this.missiles) o.alive = false;
    for (const o of this.beams) o.alive = false;
    for (const o of this.effects) o.alive = false;
    for (const m of this.mechs.values()) { m.droneN = 0; m.mineN = 0; m.burnT = 0; m.burnAcc = 0; }
    this.bubbleCount = 0;
  }
  reset() {
    this.mechs.clear(); this.alive.length = 0; this.events.length = 0;
    this.clearPools(); this.squads.clear();   // votes survive: the adapter resets the core at CS2's round restart, BEFORE pickMode reads them
    this.match.phase = 'over'; this.combatOn = false;   // (until 10 Nov 2026 every !vote was wiped there, so no vote ever chose a mode)
  }

  // ---------------------------------------------------------------------------------------------------------- players
  addPlayer(slot, info) {
    info = info || {};
    let m = this.mechs.get(slot);
    const fresh = !m;
    if (!m) { m = new IF_Mech(slot); this.mechs.set(slot, m); }
    const team = info.team === 3 ? 3 : info.team === 2 ? 2 : (info.team | 0);
    if (!fresh && m.alive && m.team !== team) { m.alive = false; m.deathT = 0; }
    m.team = team; m.human = info.human !== false; m.npc = slot >= IF_NPC_SLOT0;
    if (info.name) m.name = String(info.name);
    const pilot = info.pilot || this.pendingPilots.get(slot) || m.pilot || this.keptPilots.get(slot) || null;
    this.pendingPilots.delete(slot);
    this.setPilotOn(m, pilot);
    if (fresh) {
      m.alive = false; m.respawnT = 0; m.deathT = 0;
      let lo = this.pendingLoadouts.get(slot); this.pendingLoadouts.delete(slot);
      if (!lo && pilot && pilot.loadouts) { const l = pilot.loadouts[(pilot.active || 1) - 1]; if (l && IF_Progress.validate(l, pilot, this.P) === 0) lo = l; }
      if (!m.human) { IF_Ai.attach(this, m, IF_Ai.fillTier(this)); lo = lo || IF_Ai.loadoutFor(this, m.ai.tierKey); m.wantSpawn = true; this.assignSquad(m, this.mechs.size); }
      m.pendingLoadout = lo || this.P.starter.loadouts[0];
    } else if (!m.human && !m.ai) { IF_Ai.attach(this, m, IF_Ai.fillTier(this)); m.wantSpawn = true; }
    if (m.human) m.ai = null;
    return m;
  }
  removePlayer(slot) {
    const m = this.mechs.get(slot);
    this.keptPilots.delete(slot);
    if (!m) return;
    this.mechs.delete(slot);
    for (const o of this.mechs.values()) if (o.lock.target === slot) { o.lock.target = -1; o.lock.stage = 0; o.lock.t = 0; }
    for (const ms of this.missiles) if (ms.alive && ms.target === slot) ms.target = -1;
    this.votes.delete(slot);
  }
  setPilotOn(m, pilot) {
    m.pilot = pilot || null;
    // a stand-alone garage pilot (pilot.local: upgrades only, no career) has no rank: no rookie shield, no rating
    m.rank = pilot && !pilot.local ? IF_clamp(pilot.rank | 0, 1, this.P.xp.max_rank) : 0;
    m.rating = m.rank * this.cfg.balance.ratingRank;
  }
  setPilot(slot, pilot) {
    if (pilot) this.keptPilots.set(slot, pilot); else this.keptPilots.delete(slot);
    const m = this.mechs.get(slot);
    if (m) this.setPilotOn(m, pilot); else this.pendingPilots.set(slot, pilot);
  }
  setLoadout(slot, str) {
    const m = this.mechs.get(slot);
    const pilot = m ? m.pilot : (this.pendingPilots.get(slot) || null);
    const code = IF_Progress.validate(str, pilot, this.P);
    if (code) return code;
    if (m) m.pendingLoadout = str; else this.pendingLoadouts.set(slot, str);
    return 0;
  }
  requestSpawn(slot) { const m = this.mechs.get(slot); if (m) m.wantSpawn = true; return !!m; }
  setInput(slot, inp) {
    const m = this.mechs.get(slot); if (!m || !inp) return;
    const o = m.input;
    o.mx = IF_fin(inp.mx, 0); o.my = IF_fin(inp.my, 0); o.yaw = IF_fin(inp.yaw, o.yaw); o.pitch = IF_fin(inp.pitch, o.pitch);
    o.boost = !!inp.boost; o.qb = !!inp.qb; o.jump = !!inp.jump; o.cycle = !!inp.cycle; o.cycleHeld = !!inp.cycleHeld; o.any = !!inp.any; o.od = !!inp.od;
    const f = inp.fire || [];
    o.fire[0] = !!f[0]; o.fire[1] = !!f[1]; o.fire[2] = !!f[2]; o.fire[3] = !!f[3];
    o.camPos = inp.camPos || null; o.camDir = inp.camDir || null; o.camDist = IF_fin(inp.camDist, 0);
  }
  leaveMech(slot) {
    const m = this.mechs.get(slot); if (!m) return;
    m.alive = false; m.deathT = 0; m.wantSpawn = false; m.respawnT = this.time + this.cfg.spawn.respawn;
    for (const o of this.alive) if (o.lock.target === slot) { o.lock.target = -1; o.lock.stage = 0; }
  }
  killMech(slot, killer) { const m = this.mechs.get(slot); if (m && m.alive) IF_mechDie(this, m, killer === undefined ? -1 : killer, ''); }
  pilotSummary(slot) {
    const m = this.mechs.get(slot);
    const z = { xp: 0, credits: 0, kills: 0, deaths: 0, assists: 0, captures: 0, damage: 0, pveKills: 0, bossKills: 0, won: false, streakBest: 0 };
    if (!m) return z;
    const s = m.sum;
    if (this.match.phase === 'running' || this.match.phase === 'warmup') { const r = this.xpOf(m, false); s.xp = r.xp; s.credits = r.credits; }
    for (const k in z) z[k] = k === 'damage' ? Math.round(s[k]) : s[k];
    return z;
  }
  // The round's statistics for the server (the adapter sends them as mgstat lines at the round end; SERVER_CONTRACT.md section 2b):
  // counters, the bests, the mode and the frame flown, and kills / damage per weapon part key.
  pilotStats(slot) {
    const m = this.mechs.get(slot); if (!m) return null;
    const s = m.sum, w = {};
    for (const k in m.wsum) { const v = m.wsum[k]; if (v[0] > 0 || v[1] >= 1) w[k] = { kills: v[0], damage: Math.round(v[1]) }; }
    return { mode: this.match.mode, frame: m.frame ? m.frame.key : '', won: !!s.won, kills: s.kills, damage: Math.round(s.damage),
      shots: s.shots, hits: s.hits, qb: s.qb, mslFired: s.mslFired, dodges: s.dodges, staggers: s.staggers, od: s.od, crates: s.crates,
      flagReturns: s.flagReturns, dmgTaken: Math.round(s.dmgTaken), lifeBest: Math.round(Math.max(s.lifeBest, m.alive ? m.aliveT : 0)), weapons: w };
  }
  xpOf(m, won) {
    let ranks = [];
    for (const o of this.mechs.values()) if (o.human && o.rank > 0) ranks.push(o.rank);
    ranks.sort((a, b) => a - b);
    const median = ranks.length ? ranks[ranks.length >> 1] : 0;
    const r = IF_Progress.roundXp(m.sum, { won, rank: m.rank, medianRank: median, parts: this.P, cap: this.cfg.xp.roundCap });
    // the operator's XP rate (an event weekend: IronFrame.Rules.XpRate), after the round cap; credits follow the XP
    if (IF_RULES && IF_RULES.xpRate !== 1) { r.xp = Math.round(r.xp * IF_RULES.xpRate); r.credits = Math.round(r.xp * this.P.xp.credits_per_xp); }
    return r;
  }
  balanceTeams() {
    const list = [];
    for (const m of this.mechs.values()) if (!m.npc && (m.team === 2 || m.team === 3)) list.push({ slot: m.slot, rating: m.rating + (m.sum.kills - m.sum.deaths) * 0 });
    return IF_balanceTeams(list);
  }

  // ---------------------------------------------------------------------------------------------------------- NPCs and squads
  addNpc(team, tierKey, fill, listKey) {
    let slot = -1;
    const s0 = this.npcSlot0;
    for (let s = s0; s < s0 + 64 && s < IF_MAX_MECHS; s++) if (!this.mechs.has(s)) { slot = s; break; }
    if (slot < 0) return null;
    const m = new IF_Mech(slot);
    m.team = team; m.human = false; m.npc = true; m.fill = !!fill; m.name = 'AI-' + (slot - this.npcSlot0 + 1);
    this.mechs.set(slot, m);
    IF_Ai.attach(this, m, tierKey || 'normal');
    m.pendingLoadout = IF_Ai.loadoutFor(this, listKey || tierKey || 'normal');
    m.wantSpawn = true; m.respawnT = 0;
    let n = 0; for (const o of this.mechs.values()) if (!o.human && this.side(o) === this.side(m)) n++;
    this.assignSquad(m, n);
    return m;
  }
  removeNpc(slot) { const m = this.mechs.get(slot); if (m && m.npc) this.removePlayer(slot); }
  assignSquad(m, k) {
    const id = (this.side(m) + 1) * 1000 + Math.floor(k / this.cfg.ai.squadSize);
    m.squad = id;
    if (!this.squads.has(id)) this.squads.set(id, { target: -1, t: -99, goal: IF_v3(), goalT: -99 });
  }

  // ---------------------------------------------------------------------------------------------------------- spawning
  dropList(m) {
    const D = this.arena.drops || {}, mode = this.match.mode;
    let list;
    if (mode === 'sk') list = D.ffa || (D.t || []).concat(D.ct || []);
    else if (mode === 'so') list = m.team === 0 ? (D.ffa || D.ct || []) : (D.t || []).concat(D.ct || []);
    else list = (m.team === 2 ? D.t : D.ct) || D.ffa || [];
    if (!list || !list.length) { const b = this.arena.bounds; list = [[(b.min[0] + b.max[0]) / 2, (b.min[1] + b.max[1]) / 2, b.min[2] + 1500, 0]]; }
    return list;
  }
  pickDrop(m, out) {
    const C = this.cfg, cand = this.dropList(m).slice();
    // forward drops at held Conquest points
    if (this.match.mode === 'cq' && C.cq.forwardDrops) for (const p of this.match.points) if (p.owner === m.team && !p.contested) cand.push([p.pos.x, p.pos.y, p.pos.z + C.spawn.dropHeight, 0, 1]);
    let best = null, bd = -1;
    const ok = [];
    for (const d of cand) {
      let near = Infinity;
      for (const o of this.alive) if (this.enemies(m, o)) { const dd = Math.hypot(o.pos.x - d[0], o.pos.y - d[1]); if (dd < near) near = dd; }
      if (near >= C.spawn.enemyDist) ok.push(d);
      if (near > bd) { bd = near; best = d; }
    }
    const d = ok.length ? ok[Math.floor(this.rng() * ok.length)] : best;
    const a = this.rng() * Math.PI * 2, r = 120 + this.rng() * 260;
    out.x = d[0] + Math.cos(a) * r; out.y = d[1] + Math.sin(a) * r;
    const b = this.arena.bounds;
    out.x = IF_clamp(out.x, b.min[0] + 300, b.max[0] - 300); out.y = IF_clamp(out.y, b.min[1] + 300, b.max[1] - 300);
    const g = this.nav.height(out.x, out.y);
    out.z = IF_clamp(Math.max(d[2], g + C.spawn.dropHeight * (d[4] ? 1 : 0.5)), g + 200, b.max[2] - (m.height || 300) - 50);
    return IF_fin(d[3], 0);
  }
  spawnMech(m) {
    let ids = IF_parseLoadout(m.pendingLoadout || m.loadoutStr);
    if (!ids || !IF_mechApplyLoadout(this, m, ids)) { ids = IF_parseLoadout(this.P.starter.loadouts[0]); IF_mechApplyLoadout(this, m, ids); }
    m.cls.key = m.frame.class;   // the class row's key ('light' | 'medium' | 'heavy' | 'boss') for the adapter
    const yaw = this.pickDrop(m, m.pos);
    m.vel.x = 0; m.vel.y = 0; m.vel.z = -200;
    m.legYaw = yaw; m.torsoYaw = yaw; m.pitch = 0; m.input.yaw = yaw; m.input.pitch = 0;
    m.ap = m.apMax; m.en = m.enMax; m.enStalled = 0; m.enPause = 0; m.stagger = 0; m.staggered = 0; m.staggerDecayT = 0;
    m.protect = this.cfg.spawn.protect; m.landLag = 0; m.decoyT = 0; m.dropT = 1e-3; m.onGround = false; m.airTime = 0;
    m.qbCd = 0; m.qbTime = 0; m.boosting = false; m.hover = false; m.braced = false; m.lungeT = 0; m.lungeHp = -1; m.healLeft = 0; m.bossPhase = 0; m.burnT = 0; m.burnAcc = 0;
    m.lock.target = -1; m.lock.stage = 0; m.lock.t = 0; m.lockedBy = 0; m.threats.length = 0;
    m.histN = 0; m.dmgBy.fill(0); m.streak = 0; /** @type {any} */ (this).featReset(m);
    for (const w of m.weapons) w.setup(w.part, w.part ? IF_upgradeLevel(m.pilot, w.part.id, this.P.caps) : 0, this.P.caps);
    m.alive = true; m.wantSpawn = false; m.deathT = 0; m.spawnT = this.time; m.aliveT = 0; m.killer = -1;
    for (let i = 0; i < 4; i++) m.input.fire[i] = false;
    if (m.ai) { m.ai.yaw = yaw; m.ai.pitch = 0; m.ai.coverT = 0; m.ai.stuckT = 0; m.ai.checkX = m.pos.x; m.ai.checkY = m.pos.y; m.ai.checkT = this.time; m.ai.target = -1; }
    this.stats.spawns++;
    this.emit({ t: 'spawn', slot: m.slot });
  }

  // ---------------------------------------------------------------------------------------------------------- the tick
  tick(dt, now) {
    dt = IF_clamp(IF_fin(dt, 1 / IF_TICKRATE), 0, this.cfg.dtMax);
    if (!(dt > 0)) return;
    this.time += dt; this.now = Number.isFinite(now) ? now : this.time; this.tickN++;
    const M = this.match;
    if (M.phase === 'over') { IF_bulletsStep(this, dt); IF_missilesStep(this, dt); IF_fxStep(this, dt); return; }
    // phases
    if (M.phase === 'warmup') { M.warmup -= dt; if (M.warmup <= 0) { M.phase = 'running'; this.combatOn = true; this.emit({ t: 'say', slot: -1, text: IF_MODE_NAMES[M.mode] + ': fight!', secs: 3 }); } }
    else if (M.phase === 'podium') { M.timeLeft = Math.max(0, M.timeLeft - dt); if (M.timeLeft <= 0) M.phase = 'over'; }
    const playing = M.phase === 'warmup' || M.phase === 'running';
    // spawns and fill
    if (playing) {
      if ((this.fillAcc += dt) >= 1) { this.fillAcc = 0; IF_Ai.fillCheck(this, this.humanCount()); }
      for (const m of this.mechs.values()) {
        if (m.alive) continue;
        if ((m.wantSpawn || !m.human) && this.time >= m.respawnT) {
          if (m.npc && M.mode === 'so' && m.team === 0 && !m.wantSpawn) continue;   // wave enemies spawn once
          if (m.fill && m.ai) IF_Ai.retier(this, m);
          this.spawnMech(m);
        }
      }
    }
    // the live list
    const L = this.alive; L.length = 0;
    for (const m of this.mechs.values()) if (m.alive) L.push(m);
    this.stats.ticks++; this.stats.mechTicks += L.length;
    // AI fills inputs (it reads last tick's threats)
    for (let k = 0; k < L.length; k++) { const m = L[k]; if (!m.human && m.ai) IF_Ai.step(this, m, dt); }
    // movement
    for (let k = 0; k < L.length; k++) {
      const m = L[k];
      IF_mechStep(this, m, dt);
      m.threats.length = 0; m.lockedBy = 0;
      if (playing) m.sum.survive += dt;
    }
    /** @type {any} */ (this).featPre(L, dt);
    IF_separate(this, L, L.length, dt);
    this.grid.build(L, L.length);
    // locks and weapons
    const se = this.cfg.lock.seekEvery;
    for (let k = 0; k < L.length; k++) { const m = L[k]; if (m.alive) IF_lockStep(this, m, dt, ((this.tickN + m.slot) % se) === 0); }
    for (let k = 0; k < L.length; k++) { const m = L[k]; if (m.alive) IF_weaponsStep(this, m, dt); }
    IF_bulletsStep(this, dt);
    IF_missilesStep(this, dt);
    IF_fxStep(this, dt);
    // out of the world (Orbital falls): dead
    const zmin = this.arena.bounds.min[2] - 1500;
    for (let k = 0; k < L.length; k++) { const m = L[k]; if (m.alive && m.pos.z < zmin) IF_mechDie(this, m, -1, 'fall'); }
    if (M.phase === 'running') { /** @type {any} */ (this).featStep(dt); this.modeStep(dt); }
  }

  // ---------------------------------------------------------------------------------------------------------- mode rules
  modeOnKill(v, k) {
    const M = this.match;
    this.stats.deaths++;
    if (M.mode === 'ctf') /** @type {any} */ (this).ctfOnDeath(v);
    switch (M.mode) {
      case 'tb': if (k && this.enemies(k, v) && (k.team === 2 || k.team === 3)) M.scores[k.team]++; break;
      case 'cq': if (v.team === 2 || v.team === 3) M.tickets[v.team] = Math.max(0, M.tickets[v.team] - this.cfg.cq.killCost); break;
      case 'sk': if (k) { if (M.leader < 0 || k.sum.kills > (this.mechs.get(M.leader) || { sum: { kills: -1 } }).sum.kills) M.leader = k.slot; M.scores[2] = Math.max(M.scores[2], k.sum.kills); } break;
      case 'so': if (k && v.team === 0 && k.team !== 0) M.scores[k.team === 3 ? 3 : 2]++; break;
      default: break;
    }
  }
  modeStep(dt) {
    const M = this.match;
    M.timeLeft -= dt;
    if (M.mode === 'cq') {
      this.cqAcc += dt;
      if (this.cqAcc >= 0.125) { this.captureStep(this.cqAcc); this.cqAcc = 0; }
      const C = this.cfg.cq;
      // ticket bleed, majority rule (10 Nov 2026): only the team holding more points bleeds the other, (difference x bleedPerPoint)/s.
      // Every held point used to bleed the enemy, so a 2-1 split cost both sides and 16-bot rounds ended in about 2.5 min (DESIGN: 10).
      let h2 = 0, h3 = 0; for (const p of M.points) { if (p.owner === 2) h2++; else if (p.owner === 3) h3++; }
      M.bleed = { 2: h3 > h2 ? (h3 - h2) * C.bleedPerPoint : 0, 3: h2 > h3 ? (h2 - h3) * C.bleedPerPoint : 0 };   // tickets/s each team is losing (HUD)
      M.tickets[2] = Math.max(0, M.tickets[2] - M.bleed[2] * dt); M.tickets[3] = Math.max(0, M.tickets[3] - M.bleed[3] * dt);
      if (M.tickets[2] <= 0 || M.tickets[3] <= 0) return this.endRound();
    } else if (M.mode === 'kh') { /** @type {any} */ (this).khStep(dt); if (M.phase !== 'running') return;
    } else if (M.mode === 'ctf') { /** @type {any} */ (this).ctfStep(dt); if (M.phase !== 'running') return;
    } else if (M.mode === 'tb') {
      if (M.scores[2] >= M.killTarget || M.scores[3] >= M.killTarget) return this.endRound();
    } else if (M.mode === 'sk') {
      if (M.scores[2] >= M.killTarget) return this.endRound();
    } else if (M.mode === 'so') {
      this.sortieStep(dt);
      if (this.so.lost || this.so.done) return this.endRound();
    }
    if (M.timeLeft <= 0) { M.timeLeft = 0; this.endRound(); }
  }
  // Conquest capture: one team present moves the point's value toward it (signed: T -1, CT +1); 8 s from neutral to owned,
  // faster with more mechs (+50 % each, max x3); contested freezes; empty points drift back toward their owner.
  captureStep(dt) {
    const C = this.cfg.cq, M = this.match;
    for (let i = 0; i < M.points.length; i++) {
      const p = M.points[i];
      let n2 = 0, n3 = 0, first2 = -1, first3 = -1;
      for (const m of this.alive) {
        if (m.dropT > 0 || (m.team !== 2 && m.team !== 3)) continue;
        if (Math.hypot(m.pos.x - p.pos.x, m.pos.y - p.pos.y) > p.radius || Math.abs(m.pos.z - p.pos.z) > 800) continue;
        if (m.team === 2) { n2++; if (first2 < 0) first2 = m.slot; } else { n3++; if (first3 < 0) first3 = m.slot; }
      }
      p.contested = n2 > 0 && n3 > 0;
      p.nT = n2; p.nCT = n3;          // mechs on the point per team (the HUD's capture bar: who is taking it)
      if (p.contested) continue;
      const before = p.owner;
      if (n2 || n3) {
        const team = n2 ? 2 : 3, n = n2 || n3, dir = team === 2 ? -1 : 1;
        const rate = Math.min(C.captureMax, 1 + C.captureBonus * (n - 1)) / C.captureTime;
        p.value = IF_clamp(p.value + dir * rate * dt, -1, 1);
        if (p.owner && p.owner !== team && (p.owner === 2 ? p.value >= 0 : p.value <= 0)) p.owner = 0;   // neutralised
        if (Math.abs(p.value) >= 1 - 1e-9 && p.owner !== team) {
          p.owner = team; p.value = dir;
          const who = team === 2 ? first2 : first3;
          for (const m of this.alive) if (m.team === team && Math.hypot(m.pos.x - p.pos.x, m.pos.y - p.pos.y) <= p.radius) m.sum.captures++;
          this.emit({ t: 'capture', point: p.idx !== undefined ? p.idx : i, id: p.id, team, slot: who });   // point: index into arena.points (KOTH's one-point list used to say A)
        }
      } else if (p.owner) p.value = IF_approach(p.value, p.owner === 2 ? -1 : 1, C.decay * dt);
      else p.value = IF_approach(p.value, 0, C.decay * dt);
      p.capTeam = p.value < 0 ? 2 : p.value > 0 ? 3 : 0;
      p.progress = Math.abs(p.value);
      if (before !== p.owner && p.owner === 0) this.emit({ t: 'sound', key: 'point_lost', pos: IF_v3(p.pos.x, p.pos.y, p.pos.z) });
    }
  }
  // Sortie: waves of NPC enemies (team 0), a boss every third wave, the beacon must stay held
  sortieStep(dt) {
    const C = this.cfg.so, M = this.match, S = this.so;
    let alive = 0;
    for (const m of this.mechs.values()) if (m.npc && m.team === 0) {
      if (m.alive || m.wantSpawn) alive++;
      else if (this.now - m.deathT > 4) this.removeNpc(m.slot);
    }
    M.enemiesLeft = alive + S.toSpawn;
    if (S.state === 'pause') {
      S.pauseT -= dt;
      if (S.pauseT <= 0) {
        if (M.wave >= C.waves) { S.done = true; return; }
        M.wave++; S.state = 'fight';
        const humans = this.humanCount();
        S.toSpawn = Math.min(C.maxEnemies, Math.round(C.baseEnemies + C.perWave * (M.wave - 1) + C.extraPerPlayer * humans));
        S.boss = M.wave % C.bossEvery === 0;
        if (S.boss) S.toSpawn = Math.max(4, S.toSpawn - 6);
        this.emit({ t: 'wave', n: M.wave });
        if (S.boss) { const b = this.addNpc(0, 'hard', false, 'boss'); if (b) b.isBoss = true; }
      }
    } else {
      S.spawnT -= dt;
      while (S.toSpawn > 0 && S.spawnT <= 0) {
        const hard = M.wave >= 4;
        const tier = M.wave >= 7 ? 'hard' : M.wave >= 3 ? 'normal' : 'easy';
        if (!this.addNpc(0, tier, false, hard && this.rng() < 0.5 ? 'pve_hard' : 'pve_easy')) break;
        S.toSpawn--; S.spawnT += 0.5;
      }
      if (S.spawnT < 0) S.spawnT = 0;
      if (S.toSpawn === 0 && alive <= (M.wave >= C.waves ? 0 : C.nextAt)) { S.state = 'pause'; S.pauseT = C.pause; }
    }
    // the beacon
    const p = M.points[0];
    if (p) {
      let pl = 0, en = 0;
      for (const m of this.alive) {
        if (m.dropT > 0 || Math.hypot(m.pos.x - p.pos.x, m.pos.y - p.pos.y) > p.radius) continue;
        if (m.team === 0) en++; else pl++;
      }
      p.contested = pl > 0 && en > 0;
      if (en && !pl) { M.beaconLoss += dt; p.value = IF_clamp(p.value + dt / this.cfg.cq.captureTime, -1, 1); }
      else if (pl && !en) { M.beaconLoss = Math.max(0, M.beaconLoss - dt * 0.5); p.value = IF_clamp(p.value - dt / this.cfg.cq.captureTime, -1, 1); }
      p.owner = p.value <= 0 ? 2 : 0; p.progress = Math.abs(p.value); p.capTeam = p.value <= 0 ? 2 : 0;
      if (M.beaconLoss >= C.beaconLoseTime) S.lost = true;
    }
  }
  // the round ends: winner, podium, per-mech XP and credits; emits round_end
  endRound(force) {
    const M = this.match;
    if (M.phase !== 'running' && M.phase !== 'warmup') return;
    let winner = 0;
    if (M.mode === 'tb' || M.mode === 'kh' || M.mode === 'ctf') winner = M.scores[2] > M.scores[3] ? 2 : M.scores[3] > M.scores[2] ? 3 : 0;
    else if (M.mode === 'cq') winner = M.tickets[2] > M.tickets[3] ? 2 : M.tickets[3] > M.tickets[2] ? 3 : 0;
    else winner = 0;
    const playersWon = M.mode === 'so' && !this.so.lost;
    // podium: every pilot by score, the script's AI fill included (a lobby of one human and AI fill used to get an empty podium:
    // the AI slots were ranked, then dropped); Sortie's wave enemies (team 0) are not pilots. M.podiumInfo carries what the cards show.
    const ranked = Array.from(this.mechs.values()).filter((m) => !m.npc || m.fill || (M.mode === 'so' && m.team !== 0 && !m.isBoss))
      .map((m) => ({ m, s: m.sum.kills * 3 + m.sum.assists + m.sum.captures * 2 + m.sum.pveKills * 2 + m.sum.bossKills * 10 + m.sum.damage / 3000 }))
      .sort((a, b) => (b.s - a.s) || ((a.m.npc ? 1 : 0) - (b.m.npc ? 1 : 0)) || (a.m.slot - b.m.slot));
    M.podium = ranked.slice(0, 3).map((r) => r.m.slot);
    M.podiumInfo = ranked.slice(0, 3).map((r) => ({ slot: r.m.slot, name: r.m.name, team: r.m.team, npc: r.m.npc, kills: r.m.sum.kills + r.m.sum.pveKills + r.m.sum.bossKills, score: Math.round(r.s) }));
    M.winner = winner; M.phase = 'podium'; M.timeLeft = this.cfg.round.podium; this.combatOn = false;
    for (const m of this.mechs.values()) {
      const won = M.mode === 'so' ? (playersWon && m.team !== 0) : M.mode === 'sk' ? (ranked.length > 0 && ranked[0].m === m) : (winner !== 0 && m.team === winner);
      m.sum.won = won;
      const r = this.xpOf(m, won); m.sum.xp = r.xp; m.sum.credits = r.credits;
    }
    this.emit({ t: 'round_end', winner, podium: M.podium.slice(), podiumInfo: M.podiumInfo.slice(), mode: M.mode });
  }
  // where a bot should go (false: no objective, chase the target)
  modeGoal(m, out) {
    const M = this.match;
    if ((M.mode === 'kh' || M.mode === 'ctf') && /** @type {any} */ (this).objectiveGoal(m, out)) return true;
    if (M.mode === 'cq' && M.points.length) {
      let best = null, bs = Infinity;
      for (let i = 0; i < M.points.length; i++) {
        const p = M.points[i];
        const d = Math.hypot(p.pos.x - m.pos.x, p.pos.y - m.pos.y);
        let s = d;
        if (p.owner === m.team && !p.contested) s += 6000;              // ours: low priority
        if (p.contested) s -= 1500;
        s += ((m.squad + i * 7) % 3) * 900;                            // squads spread over the points
        if (s < bs) { bs = s; best = p; }
      }
      IF_vcopy(out, best.pos); return true;
    }
    if (M.mode === 'so' && M.points.length) {
      const p = M.points[0];
      if (m.team === 0 && !m.boss) {
        // enemies: half go for the beacon, half hunt the nearest player
        if (m.slot & 1) { IF_vcopy(out, p.pos); return true; }
        return false;
      }
      if (m.team !== 0) {
        const d = Math.hypot(p.pos.x - m.pos.x, p.pos.y - m.pos.y);
        if (d > p.radius * 1.5 || M.beaconLoss > 0) { IF_vcopy(out, p.pos); return true; }
      }
      return false;
    }
    return false;
  }
}

// internals for the Node tests and the balance tool (not used by the adapter)
IF_Game.lib = { IF_rayWorld, IF_effect, IF_explode, IF_applyDamage, IF_mechDie, IF_parseLoadout, IF_balanceTeams, IF_weaponDps, IF_mulberry, IF_capDist, IF_leadPoint };
