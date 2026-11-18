// ===================================================================================
// Part 7b (Hellmatch ZE): zombie escape. Two arenas on two copies of one level (ids <map>t for T, <map>c for CT, the
// sidecar in L.ze). Each side starts as humans in its own arena; a human who dies becomes, after the kill delay, a zombie
// in the OTHER side's arena (no CS2 team change). Zombies (AI and players) come back forever, behind the humans.
// Win (ZE_DESIGN.md section 4): a side wiped out -> the other side wins (both within the draw window -> draw); a side
// that completes the escape stage with a human alive wins at once; the clock -> more live humans, then the later stage.
//   ZeArena     the stage engine of one arena (start conditions, zones, holds, actions, blocks, spawn groups, boss)
//   ZeDirector  the AI horde of one arena (the map's own monsters, spawn groups, fill up to the cap behind the humans)
//   ZeRound     the round: the surface the CS2 side uses (startRound, tic, leaveArena, joinArena, lateJoin, people,
//               events, arenas, state), on top of RoundManager's people / spectating / AFK code
// ===================================================================================

MODES.ze = { name: 'ZOMBIE ESCAPE', teams: false, respawn: true, minPlayers: 1, ze: true };
const ZE_SIDE_NAME = { 2: 'T', 3: 'CT' };
const ZE_FILL_SKIP = new Set(['CYBERDEMON', 'MASTERMIND', 'ARCHVILE', 'PAINELEMENTAL']);   // never part of the respawning horde
const ZE_DEFAULT_ROSTER = [['ZOMBIE', 4], ['SHOTGUY', 2], ['IMP', 4], ['DEMON', 2]];

// does the segment a->b cross line l (between its ends)?
function zeSegCross(ax, ay, bx, by, l) {
  const d1 = l.dx * (ay - l.y1) - l.dy * (ax - l.x1), d2 = l.dx * (by - l.y1) - l.dy * (bx - l.x1);
  if ((d1 >= 0) === (d2 >= 0)) return false;
  const ex = bx - ax, ey = by - ay;
  const e1 = ex * (l.y1 - ay) - ey * (l.x1 - ax), e2 = ex * (l.y2 - ay) - ey * (l.x2 - ax);
  return (e1 >= 0) !== (e2 >= 0);
}

// sector "centres" (mean of their line ends) and the walking distance of every sector from the human starts over the
// bots' sector graph: how far along the level a spot is ("behind the humans" = a smaller number)
function zeSectorCentres(level) {
  if (level.zeCentres) return level.zeCentres;
  const c = level.sectors.map(() => ({ x: 0, y: 0, n: 0 }));
  for (const l of level.lines) for (const s of [l.frontsector, l.backsector]) {
    if (!s) continue;
    const q = c[s.id]; q.x += l.x1 + l.x2; q.y += l.y1 + l.y2; q.n += 2;
  }
  for (const q of c) if (q.n) { q.x /= q.n; q.y /= q.n; }
  level.zeCentres = c;
  return c;
}
function zeProgressMap(level, starts) {
  const nav = buildNav(level), cen = zeSectorCentres(level), n = level.sectors.length;
  const dist = new Float64Array(n).fill(Infinity), done = new Uint8Array(n);
  for (const s of starts) dist[level.sectorAt(s.x, s.y).id] = 0;
  for (let it = 0; it < n; it++) {
    let u = -1, best = Infinity;
    for (let i = 0; i < n; i++) if (!done[i] && dist[i] < best) { best = dist[i]; u = i; }
    if (u < 0) break;
    done[u] = 1;
    for (const e of nav[u]) {
      const d = dist[u] + Math.hypot(cen[e.to].x - cen[u].x, cen[e.to].y - cen[u].y) + 1;
      if (d < dist[e.to]) dist[e.to] = d;
    }
  }
  return dist;
}

// ---------------------------------------------------------------------------------- stage engine
class ZeArena {
  constructor(round, arena, side, sidecar) {
    this.round = round; this.a = arena; this.side = side;
    this.sc = sidecar || {};
    const hu = this.sc.humans || {};
    this.keysKept = hu.keys === 'keep';
    this.keys = new Set();
    const zs = this.sc.zombies || {};
    this.respawnTics = zs.respawn_seconds ? Math.round(zs.respawn_seconds * TICRATE) : round.zcfg.zombieRespawnTics;
    this.timeLimitTics = (this.sc.time_limit ? this.sc.time_limit * TICRATE : 0) || round.zcfg.timeLimitTics;
    this.stages = (this.sc.stages || []).map((d, i) => ({ d, i, id: d.id !== undefined ? d.id : i + 1, name: String(d.name || 'STAGE ' + (i + 1)).toUpperCase(),
      readyAt: undefined, state: 'pending', left: Math.round((d.hold || 0) * TICRATE), total: Math.round((d.hold || 0) * TICRATE), startedAt: 0, doneAt: 0 }));
    this.blocks = (this.sc.blocks || []).map((d) => ({ d, on: false, saved: null }));
    this.groups = new Map();      // spawn group name -> { d, points: [{x, y, angle}], trickled, nextTrickle }
    this.queue = [];              // delayed actions { at, act }
    this.used = new Set();        // WAD line ids a live human pressed use on
    this.crossed = new Set();     // WAD line ids a live human walked over (only lines the next stage waits for)
    this.escaped = 0;             // humans who were in the zone when the escape hold ended
    this.boss = null; this.bossMax = 0; this.bossName = ''; this.bossStage = null;
    this.started = false;
    this.spots = null;            // every place a zombie may appear (map things, starts, group points), reachable
    this.progress = null;         // sector id -> distance from the human starts
    this.lastMsg = null;
  }

  // ---------------------------------------------------------------- set up (arena context, after load)
  setup() {
    const a = this.a, L = a.level;
    const starts = a.humanStarts && a.humanStarts.length ? a.humanStarts : a.dmstarts;
    this.progress = zeProgressMap(L, starts.length ? starts : [{ x: 0, y: 0 }]);
    for (const [name, d] of Object.entries(this.sc.spawn_groups || {})) this.groups.set(name, { d, points: this.groupPoints(d), trickled: 0, nextTrickle: 0 });
    // every block starts shut; it opens when its condition is met
    for (const b of this.blocks) this.setBlock(b, true);
    // candidate zombie spots: the level's own monster and item spots, starts, teleport landings, group points; only
    // places a walker can reach from the human starts, 96 apart
    const pts = [];
    for (const m of a.mapMonsters) pts.push({ x: m.x, y: m.y });
    for (const s of a.dmstarts) pts.push({ x: s.x, y: s.y });
    for (const t of L.things) {
      const mt = DOOMEDNUM[t[3]];
      if (mt === undefined) continue;
      const k = MOBJINFO[mt].kind;
      if (k === 'item' || k === 'teleportdest' || k === 'decor') pts.push({ x: t[0], y: t[1] });
    }
    for (const g of this.groups.values()) for (const p of g.points) pts.push({ x: p.x, y: p.y });
    const out = [];
    for (const p of pts) {
      const sid = L.sectorAt(p.x, p.y).id;
      if (this.progress[sid] === Infinity) continue;
      if (!out.some((q) => Math.abs(q.x - p.x) < 96 && Math.abs(q.y - p.y) < 96)) out.push({ x: p.x, y: p.y, prog: this.progress[sid] });
    }
    this.spots = out;
  }

  groupPoints(d) {
    const L = this.a.level, pts = [];
    for (const p of d.points || []) pts.push({ x: p[0], y: p[1], angle: p[2] || 0 });
    const secs = d.sector !== undefined ? [d.sector] : d.sectors || [];
    for (const si of secs) {
      const sec = L.sectors[si];
      if (!sec) continue;
      let x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity;
      for (const l of sec.lines) { x1 = Math.min(x1, l.x1, l.x2); y1 = Math.min(y1, l.y1, l.y2); x2 = Math.max(x2, l.x1, l.x2); y2 = Math.max(y2, l.y1, l.y2); }
      const step = Math.max(48, Math.ceil(Math.max(x2 - x1, y2 - y1) / 6));
      for (let x = x1 + step / 2; x < x2; x += step) for (let y = y1 + step / 2; y < y2; y += step) if (L.sectorAt(x, y) === sec) pts.push({ x, y, angle: 0 });
      if (!pts.length && sec.lines.length) pts.push({ x: (x1 + x2) / 2, y: (y1 + y2) / 2, angle: 0 });
    }
    return pts;
  }

  setBlock(b, on) {
    if (b.on === on) return;
    const L = this.a.level;
    b.on = on;
    // a blocked line blocks everyone and has no special while it is blocked (a manual door behind it can't be opened
    // early, a walk-over trigger doesn't fire); unblocking gives both back
    if (on) b.saved = (b.d.lines || []).map((i) => L.lines[i] ? [i, L.lines[i].flags, L.lines[i].special] : null).filter(Boolean);
    for (const [i, f, sp] of b.saved || []) { L.lines[i].flags = on ? f | ML_BLOCKING | ML_BLOCKMONSTERS : f; L.lines[i].special = on ? 0 : sp; }
    L.nav = null; L.navCache = null;   // the bots' routes change with the block
  }

  // ---------------------------------------------------------------- conditions
  stageById(id) { return this.stages.find((s) => s.id === id || s.id === +id); }
  zoneHas(z, x, y) {
    if (!z) return false;
    if (z.box) { const b = z.box; return x >= Math.min(b[0], b[2]) && x <= Math.max(b[0], b[2]) && y >= Math.min(b[1], b[3]) && y <= Math.max(b[1], b[3]); }
    const id = this.a.level.sectorAt(x, y).id;
    if (z.sector !== undefined) return id === z.sector;
    if (z.sectors) return z.sectors.includes(id);
    return false;
  }
  zoneCentre(z) {
    if (!z) return null;
    if (z.box) return { x: (z.box[0] + z.box[2]) / 2, y: (z.box[1] + z.box[3]) / 2 };
    const ids = z.sector !== undefined ? [z.sector] : z.sectors || [];
    const cen = zeSectorCentres(this.a.level);
    let x = 0, y = 0, n = 0;
    for (const i of ids) if (cen[i]) { x += cen[i].x; y += cen[i].y; n++; }
    if (!n) return null;
    // a centre that falls outside the zone (an L-shaped room): the nearest group-style sample inside it
    const c = { x: x / n, y: y / n };
    if (this.zoneHas(z, c.x, c.y)) return c;
    const pts = this.groupPoints({ sectors: ids });
    return pts.length ? { x: pts[0].x, y: pts[0].y } : c;
  }
  humans() {
    const out = [];
    for (const p of this.a.players.values()) if (!p.zclass && !p.spectating && p.playerstate === 'live' && p.mo && !p.mo.removed) out.push(p);
    return out;
  }
  humansIn(z) { let n = 0; for (const p of this.humans()) if (this.zoneHas(z, p.mo.x, p.mo.y)) n++; return n; }

  met(cond) {
    if (!cond || cond === 'round') return this.started;
    if (typeof cond === 'string') {
      const m = /^(stage|start|done):(\d+)$/.exec(cond);
      if (!m) return false;
      const s = this.stageById(+m[2]);
      return !!s && (m[1] === 'done' ? s.state === 'done' : s.state !== 'pending');
    }
    if (cond.stage_done !== undefined) { const s = this.stageById(cond.stage_done); return !!s && s.state === 'done'; }
    if (cond.stage_started !== undefined) { const s = this.stageById(cond.stage_started); return !!s && s.state !== 'pending'; }
    if (cond.use_line !== undefined) return this.used.has(cond.use_line);
    if (cond.line_crossed !== undefined) return this.crossed.has(cond.line_crossed);
    if (cond.zone_entered) return this.humansIn(cond.zone_entered) > 0;
    return false;
  }

  // ---------------------------------------------------------------- per tic (arena context is set by the caller)
  start() {
    if (this.started) return;
    this.started = true;
    this.tic();
  }

  tic() {
    const a = this.a;
    if (!this.started || a.finished) return;
    // delayed actions
    if (this.queue.length) for (let i = this.queue.length - 1; i >= 0; i--) if (a.leveltime >= this.queue[i].at) { const q = this.queue.splice(i, 1)[0]; this.act(q.act, true); }
    // stages run in order: the next one is looked at once the one before it is done (a line crossed or a switch used
    // earlier doesn't count). A human crossing the line it waits for:
    const next = this.stages.find((s) => s.state === 'pending');
    const ready = next && (next.i === 0 || this.stages[next.i - 1].state === 'done');
    const wl = ready && next.d.start && next.d.start.line_crossed !== undefined ? a.level.lines[next.d.start.line_crossed] : null;
    if (wl && !this.crossed.has(wl.id)) {
      for (const p of this.humans()) {
        const mo = p.mo;
        if (mo.px === mo.x && mo.py === mo.y) continue;
        if (Math.abs(mo.x - mo.px) > 64 || Math.abs(mo.y - mo.py) > 64) continue;   // a teleport, not a walk
        if (zeSegCross(mo.px, mo.py, mo.x, mo.y, wl)) { this.crossed.add(wl.id); break; }
      }
    }
    if (ready && next.d.start && next.d.start.use_line !== undefined && next.readyAt === undefined) { next.readyAt = a.leveltime; this.used.delete(next.d.start.use_line); }
    if (ready && this.met(next.d.start || (next.i === 0 ? 'round' : { stage_done: this.stages[next.i - 1].id }))) this.startStage(next);
    for (const s of this.stages) {
      if (s.state === 'pending') continue;
      if (s.state !== 'active') continue;
      if (s.d.boss) {
        if (this.boss && this.boss.removed && this.boss.health > 0) for (const m of a.mobjs) if (m.boss && m.health > 0) { this.boss = m; break; }   // moved, not killed
        if (!this.boss || this.boss.removed || this.boss.health <= 0) this.finishStage(s);
        continue;
      }
      if (s.left > 0) {
        // a hold counts down while a live human is in the zone, and pauses (never resets) while nobody is
        if (!s.d.zone || this.humansIn(s.d.zone) > 0) s.left--;
        if (s.left <= 0) this.finishStage(s);
      }
    }
    // spawn group trickles of the active stages
    for (const s of this.stages) {
      if (s.state !== 'active') continue;
      for (const name of s.d.zombie_spawns || []) {
        const g = this.groups.get(name);
        if (!g || !g.d.trickle) continue;
        if (a.leveltime < g.nextTrickle || g.trickled >= (g.d.trickle.max || 10)) continue;
        g.nextTrickle = a.leveltime + Math.round((g.d.trickle.every || 8) * TICRATE);
        if (a.director && a.director.room() > 0) {
          const type = a.director.pickType(g.d.ai);
          if (a.director.spawn(type, { group: name, minDist: 300 })) g.trickled++;
        }
      }
    }
    // blocks
    for (const b of this.blocks) if (b.on && b.d.until && this.met(b.d.until)) this.setBlock(b, false);
  }

  startStage(s) {
    s.state = 'active'; s.startedAt = this.a.leveltime;
    this.a.events.push({ type: 'zeStage', phase: 'start', stage: s, name: s.name });
    for (const act of s.d.on_start || []) this.act(act);
    for (const name of s.d.zombie_spawns || []) this.spawnGroup(name);
    if (s.d.boss) this.spawnBoss(s);
    else if (!(s.left > 0)) this.finishStage(s);   // no hold, no boss: a trigger stage, done at once
  }

  finishStage(s) {
    if (s.state === 'done') return;
    s.state = 'done'; s.doneAt = this.a.leveltime;
    const z = s.d.zone;
    if (s.d.escape) {
      // the humans inside the zone when the hold ends have escaped (none inside: everyone alive who held it last)
      this.escaped = z ? this.humansIn(z) : this.humans().length;
      if (!this.escaped && !z) this.escaped = this.humans().length;
    }
    const scored = this.humans();
    if (scored.length) this.a.events.push({ type: 'zeScore', players: scored, points: s.d.escape ? this.round.zcfg.escapeScore : this.round.zcfg.holdScore, why: s.d.escape ? 'escape' : 'hold' });
    this.a.events.push({ type: 'zeStage', phase: 'done', stage: s, name: s.name, escape: !!s.d.escape, escaped: this.escaped });
    for (const act of s.d.on_done || []) this.act(act);
  }

  // ---------------------------------------------------------------- actions (sidecar section 3)
  act(act, now) {
    if (!act || typeof act !== 'object') return;
    const a = this.a;
    const k = Object.keys(act)[0];
    const v = act[k] || {};
    if (!now && v && typeof v === 'object' && v.delay > 0) { this.queue.push({ at: a.leveltime + Math.round(v.delay * TICRATE), act }); return; }
    // doors and lifts by tag, or (an extension for untagged manual doors) by sector: the sectors get a private tag
    // for the call, so Doom's own door / lift / floor movers run exactly as a switch would start them
    const mover = (fn) => {
      const secs = v.sector !== undefined ? [v.sector] : v.sectors;
      if (!secs) { fn({ tag: v.tag, special: 0 }); return; }
      for (const i of secs) {
        const sec = a.level.sectors[i];
        if (!sec) continue;
        const old = sec.tag; sec.tag = -7777;
        try { fn({ tag: -7777, special: 0 }); } finally { sec.tag = old; }
      }
    };
    switch (k) {
      case 'open_door': mover((line) => doDoor(line, v.speed === 'fast' ? 'blazeOpen' : 'open')); break;
      case 'close_door': mover((line) => doDoor(line, v.speed === 'fast' ? 'blazeClose' : 'close')); break;
      case 'lower_lift': mover((line) => { if (v.stay) doFloor(line, 'lowerFloorToLowest'); else doPlat(line, v.speed === 'fast' ? 'blazeDWUS' : 'downWaitUpStay', 0); }); break;
      case 'raise_floor': mover((line) => doFloor(line, 'raiseFloor')); break;
      case 'lower_floor': mover((line) => doFloor(line, 'lowerFloorToLowest')); break;
      case 'message': a.events.push({ type: 'zeMsg', text: String(typeof act.message === 'string' ? act.message : v.text || '').toUpperCase() }); break;
      case 'spawn_group': this.spawnGroup(typeof act.spawn_group === 'string' ? act.spawn_group : v.name); break;
      case 'teleport_zombies': if (a.director) a.director.relocate(!!v.behind || v.behind === undefined); break;
      case 'unblock': { const id = typeof act.unblock === 'string' ? act.unblock : v.id; for (const b of this.blocks) if (b.d.id === id) this.setBlock(b, false); break; }
      case 'music': a.events.push({ type: 'zeMusic', id: typeof act.music === 'string' ? act.music : v.id }); break;
      case 'score': { const pts = typeof act.score === 'number' ? act.score : v.points || 1; const h = this.humans(); if (h.length) a.events.push({ type: 'zeScore', players: h, points: pts, why: 'score' }); break; }
    }
  }

  spawnGroup(name) {
    const g = this.groups.get(name), d = this.a.director;
    if (!g || !d || !g.d.ai) return;
    for (const [type, n] of Object.entries(g.d.ai)) {
      if (MT[type] === undefined || MOBJINFO[MT[type]].kind !== 'monster') continue;
      for (let i = 0; i < n && d.room() > 0; i++) d.spawn(type, { group: name, minDist: 250 });
    }
  }

  spawnBoss(s) {
    const b = s.d.boss, a = this.a, d = a.director;
    const type = MT[b.type] !== undefined && MOBJINFO[MT[b.type]].kind === 'monster' ? b.type : 'BARON';
    const info = MOBJINFO[MT[type]];
    const n = Math.max(1, this.humans().length);
    const health = Math.round(info.spawnhealth * (b.health_scale === 'none' ? 1 : (b.health_scale === 'players' || b.health_scale === undefined ? 0.5 + 0.15 * n : +b.health_scale || 1)));
    const at = b.at || null;
    let mo = null;
    if (d) mo = at ? d.placeAt(type, at[0], at[1], at[2] || 0, { health, boss: true, awake: true }) : d.spawn(type, { health, boss: true, minDist: 600 });
    this.boss = mo; this.bossMax = health; this.bossStage = s;
    this.bossName = String(b.name || info.name || type).toUpperCase();
    if (!mo) { this.finishStage(s); return; }   // nowhere to put it: the stage is skipped (the build validates the spot)
    a.events.push({ type: 'zeBoss', name: this.bossName, music: b.music || 'boss' });
  }

  // ---------------------------------------------------------------- humans
  humanLoadout(p) {
    const hu = this.sc.humans || {};
    p.health = hu.health || 100;
    // the smaller side gets Hellmatch's +25% (both sides play the same level against hordes fed by the other side)
    const sizes = this.round.zeSizes || {};
    const mine = sizes[this.side] || 0, theirs = sizes[this.side === 2 ? 3 : 2] || 0;
    if (theirs > mine && mine > 0) p.health = Math.round(p.health * 1.25);
    const W = { fist: WP_FIST, pistol: WP_PISTOL, shotgun: WP_SHOTGUN, ssg: WP_SUPERSHOTGUN, chaingun: WP_CHAINGUN, rocket: WP_MISSILE, plasma: WP_PLASMA, chainsaw: WP_CHAINSAW, bfg: WP_BFG };
    const AMMO = { [WP_PISTOL]: [AM_CLIP, 50], [WP_SHOTGUN]: [AM_SHELL, 24], [WP_SUPERSHOTGUN]: [AM_SHELL, 24], [WP_CHAINGUN]: [AM_CLIP, 100], [WP_MISSILE]: [AM_MISL, 10], [WP_PLASMA]: [AM_CELL, 100], [WP_BFG]: [AM_CELL, 80] };
    let last = null;
    for (const name of hu.loadout || ['pistol', 'shotgun']) {
      const w = W[String(name).toLowerCase()];
      if (w === undefined) continue;
      p.weaponowned[w] = true; last = w;
      const am = AMMO[w];
      if (am) p.ammo[am[0]] = Math.max(p.ammo[am[0]], Math.min(p.maxammo[am[0]], am[1]));
    }
    if (last !== null) { p.readyweapon = last; p.pendingweapon = last; }
  }

  // distinct start spots around the player starts (1-4) for a whole side
  startSpots(list) {
    const a = this.a;
    const starts = a.humanStarts && a.humanStarts.length ? a.humanStarts : a.dmstarts;
    const out = new Map(), taken = [];
    list.forEach((p, i) => {
      const s = starts.length ? starts[i % starts.length] : { x: 0, y: 0, angle: 0 };
      let f = a.fitSpot(s.x, s.y, 192, taken);
      if (!f) for (const o of starts) { f = a.fitSpot(o.x, o.y, 192, taken); if (f) break; }
      const spot = { x: f ? f.x : s.x, y: f ? f.y : s.y, angle: s.angle, silent: true };
      taken.push(spot);
      out.set(p, spot);
    });
    return out;
  }

  // a late human appears next to a live teammate (else at a start)
  lateHumanSpot() {
    const a = this.a, h = this.humans();
    for (const p of h) { const f = a.fitSpot(p.mo.x, p.mo.y, 128, h.map((q) => q.mo)); if (f) return { x: f.x, y: f.y, angle: p.mo.angle }; }
    const st = this.startSpots([null]).values().next().value;
    return st ? { x: st.x, y: st.y, angle: st.angle } : undefined;
  }

  giveKey(color, player) {
    if (player.zclass) return false;
    if (!this.keys.has(color)) {
      this.keys.add(color);
      this.a.events.push({ type: 'zeMsg', text: hudName(player.name) + ' HAS THE ' + ZE_KEY_NAMES[color] + ' KEY' });
    }
    return true;
  }

  onUse(player, line) {
    if (!player || player.zclass || player.playerstate !== 'live') return;
    this.used.add(line.id);
  }

  // ---------------------------------------------------------------- what the HUD and the bots read
  active() { for (const s of this.stages) if (s.state === 'active') return s; return null; }
  reached() { let n = 0; for (const s of this.stages) n += s.state === 'done' ? 1 : s.state === 'active' ? 0.5 : 0; return n; }

  // the place human bots head for: the active stage's zone, else the line / zone the next stage waits for
  botGoal() {
    if (this.goalMemo && this.goalMemo.t === this.a.leveltime) return this.goalMemo.g;
    let g = null;
    const s = this.active();
    if (s && s.d.zone) { const c = this.zoneCentre(s.d.zone); if (c) g = { x: c.x, y: c.y, zone: s.d.zone, hold: true }; }
    if (!g) {
      for (const p of this.stages) {
        if (p.state !== 'pending') continue;
        const st = p.d.start || {};
        const L = this.a.level;
        if (st.line_crossed !== undefined && L.lines[st.line_crossed]) {
          const l = L.lines[st.line_crossed];
          // aim past the line (to its back side) so a bot really crosses it
          const len = Math.hypot(l.dx, l.dy) || 1, mx = (l.x1 + l.x2) / 2, my = (l.y1 + l.y2) / 2;
          g = { x: mx - l.dy / len * 48, y: my + l.dx / len * 48, cross: l };
        } else if (st.use_line !== undefined && L.lines[st.use_line]) {
          const l = L.lines[st.use_line], len = Math.hypot(l.dx, l.dy) || 1;
          g = { x: (l.x1 + l.x2) / 2 + l.dy / len * 40, y: (l.y1 + l.y2) / 2 - l.dx / len * 40, use: l };
        } else if (st.zone_entered) { const c = this.zoneCentre(st.zone_entered); if (c) g = { x: c.x, y: c.y, zone: st.zone_entered }; }
        if (g) break;
      }
    }
    this.goalMemo = { t: this.a.leveltime, g };
    return g;
  }

  stageInfo() {
    const s = this.active();
    if (!s) {
      const next = this.stages.find((x) => x.state === 'pending');
      return { name: next ? 'FIND THE WAY ON' : this.stages.length ? 'SURVIVE' : 'SURVIVE', frac: -1, left: 0, boss: null };
    }
    const boss = s.d.boss && this.boss && !this.boss.removed ? { name: this.bossName, frac: Math.max(0, this.boss.health) / (this.bossMax || 1) } : null;
    const holding = s.d.zone ? this.humansIn(s.d.zone) > 0 : true;
    return { name: s.name, frac: s.total ? 1 - s.left / s.total : -1, left: Math.ceil(s.left / TICRATE), holding, boss, escape: !!s.d.escape };
  }
}

// ---------------------------------------------------------------------------------- the horde
class ZeDirector extends MonsterDirector {
  constructor(arena, ze, zcfg) {
    super(arena, 'ze', { maxAlive: zcfg.cap });
    this.ze = ze; this.zcfg = zcfg;
    const zs = (ze.sc && ze.sc.zombies) || {};
    this.capN = Math.max(8, Math.min(64, zs.cap || zcfg.cap));   // live zombies here (AI + players)
    this.reserve = [];            // map monsters that didn't fit under the cap at the start: they come in later at their own spots
    this.roster = [];             // [type, weight]: what the respawning horde is made of (the map's own mix)
    this.nextFill = 0; this.nextTrim = 0;
    this.aliveNow = 0;
    this.begun = false;
  }

  players() {
    const out = [];
    for (const p of this.a.players.values()) if (!p.zclass && !p.spectating && p.mo && !p.mo.removed && p.playerstate === 'live') out.push(p);
    return out;
  }
  zombiePlayers() { let n = 0; for (const p of this.a.players.values()) if (p.zclass && !p.spectating) n++; return n; }
  room() { return this.capN - this.zombiePlayers() - this.alive(); }

  // AI wanted now: a base plus some per live human, never above the cap less the zombie players (AI yields to players)
  aiTarget() {
    const h = this.players().length;
    return Math.max(0, Math.min(this.capN - this.zombiePlayers(), this.zcfg.aiBase + this.zcfg.aiPerHuman * h));
  }

  pickType(ai) {
    if (ai) { const e = Object.entries(ai).filter(([k, n]) => MT[k] !== undefined && n > 0); if (e.length) return weightedPick(e); }
    return weightedPick(this.roster.length ? this.roster : ZE_DEFAULT_ROSTER);
  }

  // the map's own monsters, filtered by the sidecar, placed asleep where the mapper put them (up to the cap)
  begin() {
    if (this.begun) return;
    this.begun = true;
    const a = this.a;
    const mm = ((this.ze.sc.zombies || {}).map_monsters) || {};
    const replace = mm.replace || {}, drop = new Set(mm.drop || []);
    const mix = new Map();
    for (const m of a.mapMonsters) {
      let key = replace[m.key] || m.key;
      if (drop.has(key) || drop.has(m.key) || MT[key] === undefined) continue;
      if (!ZE_FILL_SKIP.has(key)) mix.set(key, (mix.get(key) || 0) + 1);
      if (this.alive() >= this.capN) { this.reserve.push(Object.assign({}, m, { key })); continue; }
      a.run(() => this.placeAt(key, m.x, m.y, m.angle, { ambush: m.ambush }));
    }
    this.roster = Array.from(mix.entries());
    this.nextFill = a.leveltime + 3 * TICRATE;
  }

  // a monster at a given spot (the nearest clear one within 96 units); asleep unless awake is asked
  placeAt(type, x, y, angle, opts) {
    const info = MOBJINFO[MT[type]];
    const f = this.a.fitSpot(x, y, 96, null, info.radius, info.height, info);
    if (!f) return null;
    const mo = spawnMobj(f.x, f.y, (info.flags & MF_SPAWNCEILING) ? ONCEILINGZ : ONFLOORZ, MT[type]);
    mo.angle = mo.pangle = angle || 0;
    if (opts && opts.ambush) mo.flags |= MF_AMBUSH;
    if (opts && opts.health) { mo.health = opts.health; mo.maxHealth = opts.health; }
    if (opts && opts.boss) { mo.boss = true; this.bossCount++; }
    if (mo.tics > 0) mo.tics = 1 + (P_Random() % mo.tics);
    if (opts && opts.awake) this.wake(mo);
    this.spawned++;
    this.a.onMonsterSpawned(mo, null);
    return mo;
  }

  wake(mo) {
    const hs = this.players();
    if (!hs.length) return;
    let best = hs[0], bd = 1e9;
    for (const p of hs) { const d = Math.hypot(p.mo.x - mo.x, p.mo.y - mo.y); if (d < bd) { bd = d; best = p; } }
    mo.target = best.mo; mo.threshold = BASETHRESHOLD;
    if (mo.info.seestate !== S_NULL) setMobjState(mo, mo.info.seestate);
  }

  // a spot for a zombie (AI or player): the active stage's spawn groups, else behind the humans; out of the humans'
  // sight and at least minDist from all of them. close: the nearest such spot behind them (bringing a straggler back)
  zeSpot(info, opts) {
    const a = this.a, ze = this.ze;
    const minDist = opts && opts.minDist !== undefined ? opts.minDist : 450;
    const hs = this.players();
    let cands = [];
    const groups = [];
    if (opts && opts.group) groups.push(opts.group);
    else { const s = ze.active(); if (s) for (const n of s.d.zombie_spawns || []) groups.push(n); }
    for (const n of groups) { const g = ze.groups.get(n); if (g) for (const p of g.points) cands.push(p); }
    const fromGroup = cands.length > 0;
    if (fromGroup) shuffle(cands);
    else {
      const spots = ze.spots || [];
      if (hs.length) {
        let minProg = Infinity;
        for (const p of hs) { const v = ze.progress[a.level.sectorAt(p.mo.x, p.mo.y).id]; if (v < minProg) minProg = v; }
        const behind = spots.filter((s) => s.prog < minProg - 128).sort((x, y) => y.prog - x.prog);
        cands = behind.length >= 3 ? behind : spots.slice().sort((x, y) => (minProg === Infinity ? 0 : Math.abs(x.prog - minProg) - Math.abs(y.prog - minProg)));
      } else cands = shuffle(spots.slice());
    }
    let fallback = null;
    let tries = 0;
    for (const c of cands) {
      if (++tries > 20) break;
      let near = 1e9;
      for (const p of hs) { const d = Math.hypot(p.mo.x - c.x, p.mo.y - c.y); if (d < near) near = d; }
      if (near < minDist) continue;
      const f = a.fitSpot(c.x, c.y, 96, null, info.radius, info.height, info.kind === 'monster' ? info : null);
      if (!f) continue;
      let seen = false;
      const probe = { x: f.x, y: f.y, z: a.level.sectorAt(f.x, f.y).floorheight, height: info.height, sector: null };
      for (const p of hs) if (Math.abs(p.mo.x - f.x) < 2500 && Math.abs(p.mo.y - f.y) < 2500 && checkSight(p.mo, probe)) { seen = true; break; }
      const spot = { x: f.x, y: f.y, near };
      if (!seen) return spot;
      if (!fallback) fallback = spot;
    }
    return fromGroup || (opts && opts.close) ? fallback : null;
  }

  // MonsterDirector.spawn (used by unstick) and the fill: a spot from zeSpot, awake and hunting a human
  spawn(type, opts) {
    const info = MOBJINFO[MT[type]];
    if (!info) return null;
    const a = this.a;
    const spot = a.run(() => this.zeSpot(info, opts));
    if (!spot) return null;
    return a.run(() => {
      const mo = spawnMobj(spot.x, spot.y, ONFLOORZ, MT[type]);
      if (!checkPosition(mo, spot.x, spot.y) || TM.ceilingz - TM.floorz < mo.height || TM.floorz - mo.sector.floorheight > MAXSTEP) { removeMobj(mo); return null; }
      mo.floorz = TM.floorz; mo.ceilingz = TM.ceilingz; mo.z = TM.floorz; mo.pz = mo.z;
      if (info.flags & MF_FLOAT) { mo.z = Math.min(mo.ceilingz - mo.height, mo.floorz + 24); mo.pz = mo.z; }
      if (opts && opts.health) { mo.health = opts.health; mo.maxHealth = opts.health; }
      if (opts && opts.boss) { mo.boss = true; this.bossCount++; }
      const fog = spawnMobj(spot.x, spot.y, mo.z, MT.TFOG);
      startSound(fog, 'telept');
      this.wake(mo);
      this.spawned++;
      a.onMonsterSpawned(mo, null);
      return mo;
    });
  }

  tic() {
    const a = this.a;
    if (a.finished || !this.begun) return;
    if ((a.leveltime & 7) !== (a.index & 7)) return;   // the horde is checked 4-5 times a second (arenas offset)
    const alive = this.aliveNow = this.alive();
    const zp = this.zombiePlayers();
    // fill: the reserve first (at its own spots, when out of sight), then the map's mix behind the humans
    if (a.leveltime >= this.nextFill && alive < this.aiTarget() && alive + zp < this.capN) {
      let ok = null;
      if (this.reserve.length) {
        const m = this.reserve[0];
        const hs = this.players();
        const far = hs.every((p) => Math.hypot(p.mo.x - m.x, p.mo.y - m.y) > 700);
        if (far) ok = a.run(() => this.placeAt(m.key, m.x, m.y, m.angle, { ambush: m.ambush }));
        this.reserve.push(this.reserve.shift());
        if (ok) this.reserve.pop();
      }
      if (!ok) ok = this.spawn(this.pickType(null), { minDist: 500 });
      this.nextFill = a.leveltime + (ok ? this.zcfg.fillGapTics : 2 * TICRATE);
    }
    // over the cap (zombie players joined): the AI furthest from every human and out of the fight goes away
    if (alive + zp > this.capN && a.leveltime >= this.nextTrim) {
      this.nextTrim = a.leveltime + 2 * TICRATE;
      const hs = this.players();
      let worst = null, wd = 0;
      for (const m of a.mobjs) {
        if (m.info.kind !== 'monster' || m.health <= 0 || m.boss) continue;
        let near = 1e9;
        for (const p of hs) { const d = Math.hypot(p.mo.x - m.x, p.mo.y - m.y); if (d < near) near = d; }
        if (near > wd && near > 1200) { wd = near; worst = m; }
      }
      if (worst) a.run(() => { this.spawned--; removeMobj(worst); });
    }
    if ((a.leveltime % (5 * TICRATE)) < 8) this.unstick();
  }

  // stuck AI (Doom's chase is greedy): no headway towards the nearest human for 20 s and not fighting on the same floor ->
  // back in behind the humans. Unlike Boss Battle, a sleeping monster is left asleep: the map's own monsters wait ahead
  unstick() {
    const a = this.a, players = this.players();
    if (!players.length) return;
    for (const m of Array.from(a.mobjs)) {
      if (m.info.kind !== 'monster' || m.health <= 0 || m.boss) continue;
      if (STATES[m.state].action === 'A_Look') { m.bestNear = undefined; continue; }
      let nearest = null, near = 1e9;
      for (const p of players) { const d = Math.hypot(p.mo.x - m.x, p.mo.y - m.y); if (d < near) { near = d; nearest = p; } }
      if (m.bestNear === undefined || near < m.bestNear - 64) { m.bestNear = near; m.progressAt = a.leveltime; continue; }
      if (a.leveltime - (m.progressAt || 0) < 20 * TICRATE) continue;
      const sameFloor = (m.flags & MF_FLOAT) || Math.abs(nearest.mo.z - m.z) <= 2 * MAXSTEP;
      if (sameFloor && (near < 160 || a.run(() => checkSight(m, nearest.mo)))) { m.progressAt = a.leveltime; m.bestNear = near; continue; }
      const re = this.spawn(m.info.key, { health: m.health, minDist: 350, close: true });
      if (re) { this.spawned--; a.run(() => removeMobj(m)); }
      else m.progressAt = a.leveltime;
    }
  }

  // teleport_zombies: every zombie (AI, players) far from the humans comes back to the active stage's spawns / behind them
  relocate(behind) {
    const a = this.a, hs = this.players();
    if (!hs.length) return;
    const far = (x, y) => { for (const p of hs) if (Math.hypot(p.mo.x - x, p.mo.y - y) < 1100) return false; return true; };
    for (const m of Array.from(a.mobjs)) {
      if (m.info.kind !== 'monster' || m.health <= 0 || m.boss || !far(m.x, m.y)) continue;
      const re = this.spawn(m.info.key, { health: m.health, minDist: 350, close: true });
      if (re) { this.spawned--; removeMobj(m); }
    }
    for (const p of a.players.values()) {
      if (!p.zclass || p.playerstate !== 'live' || !p.mo || !far(p.mo.x, p.mo.y)) continue;
      const s = this.zeSpot(p.mo.info, { minDist: 350, close: true });
      if (!s) continue;
      const ox = p.mo.x, oy = p.mo.y, oz = p.mo.z;
      if (!teleportMove(p.mo, s.x, s.y)) continue;
      p.mo.z = p.mo.floorz; p.mo.momx = p.mo.momy = p.mo.momz = 0;
      spawnMobj(ox, oy, oz, MT.TFOG); startSound(spawnMobj(s.x, s.y, p.mo.z, MT.TFOG), 'telept');
      a.onTeleport(p, p.mo.angle);
    }
  }
}

// ---------------------------------------------------------------------------------- the round
class ZeRound extends RoundManager {
  constructor(levelData, cfg) {
    super(levelData, cfg);
    this.zcfg = Object.assign({}, DEFAULT_CFG.ze, cfg.ze || {});
    this.zeResult = null;
    this.wipedAt = {};
    this.solo = false;
    this.zeSizes = {};
    this.seen = new Set();       // people who already played this round (a rejoin comes back as a zombie)
    this.base = null;            // the ZE level being played: { id, title, t, c }
  }

  zeLevels() {
    const by = new Map();
    for (const L of this.levels) {
      if (!L.ze || !L.side) continue;
      const b = L.base || L.id.slice(0, -1);
      let e = by.get(b);
      if (!e) by.set(b, e = { id: b, title: L.title, t: null, c: null });
      e[L.side === 'c' ? 'c' : 't'] = L;
    }
    return Array.from(by.values()).filter((e) => e.t || e.c).map((e) => ({ id: e.id, title: e.title, t: e.t || e.c, c: e.c || e.t }));
  }

  pickZeMap() {
    const all = this.zeLevels();
    if (!all.length) return null;
    if (this.zcfg.map) { const f = all.find((e) => e.id === this.zcfg.map); if (f) return f; }
    const recent = this.mapHistory.slice(-Math.max(0, all.length - 1));
    const cands = all.filter((e) => !recent.includes(e.id));
    const pool = cands.length ? cands : all;
    return pool[Math.floor(Math.random() * pool.length)];
  }

  seenKey(pe) { return (pe.bot ? 'b:' : 'h:') + pe.name; }

  startRound() {
    this.endRoundCleanup();
    const eligible = [];
    for (const pe of this.people.values()) {
      if (pe.csTeam !== 2 && pe.csTeam !== 3) continue;
      if (pe.afk && !pe.bot) { pe.status = 'none'; continue; }
      if (pe.notReady) continue;
      eligible.push(pe);
    }
    this.roundNumber++;
    this.time = 0;
    this.zeResult = null; this.wipedAt = {}; this.seen = new Set(); this.zeStarted = false;
    if (eligible.length < this.cfg.minPlayersToStart) {
      this.state = 'idle';
      this.events.push({ type: 'notEnough', count: eligible.length });
      return false;
    }
    const base = this.pickZeMap();
    if (!base) { this.state = 'idle'; this.events.push({ type: 'noZeLevels' }); return false; }
    this.base = base;
    this.mapHistory.push(base.id); if (this.mapHistory.length > 40) this.mapHistory.shift();
    const ts = shuffle(eligible.filter((p) => p.csTeam === 2)), cts = shuffle(eligible.filter((p) => p.csTeam === 3));
    this.solo = !ts.length || !cts.length;
    this.zeSizes = { 2: ts.length, 3: cts.length };
    const plan = [];
    if (ts.length) plan.push({ grp: ts, mk: 'ze', L: base.t, side: 2, loadout: null, monsters: true });
    if (cts.length) plan.push({ grp: cts, mk: 'ze', L: base.c, side: 3, loadout: null, monsters: true });
    this.modeKey = 'ze';
    this.modeHistory.push('ze'); if (this.modeHistory.length > 10) this.modeHistory.shift();
    this.graceEnd = 0;
    this.arenas = [];
    this.plan = plan;
    for (const item of plan) for (const pe of item.grp) pe.status = 'planned';
    this.pending = plan.slice();
    this.state = 'running';
    if (!this.cfg.staggerArenas) while (this.pending.length) this.buildNext();
    this.events.push({ type: 'roundStart', mode: 'ze', plan });
    return true;
  }

  buildNext() {
    const item = this.pending.shift();
    if (!item) return null;
    const L = item.L;
    const grp = item.grp.filter((pe) => this.people.get(pe.slot) === pe && pe.status === 'planned');
    const arena = new Arena(this.arenas.length, Object.assign({}, this.cfg.arena));
    arena.load(L);
    arena.modeKey = 'ze'; arena.mode = MODES.ze;
    arena.teamsActive = false; arena.coop = false; arena.friendlyFire = false;
    arena.mapId = L.id; arena.mapTitle = L.title || L.id; arena.zeSide = item.side;
    arena.ze = new ZeArena(this, arena, item.side, L.ze || {});
    arena.director = new ZeDirector(arena, arena.ze, this.zcfg);
    arena.monsterFrags = false;
    arena.run(() => arena.ze.setup());
    arena.startTime = this.time;
    arena.countdown = this.cfg.countdownTics;
    arena.index = this.arenas.length;
    this.arenas.push(arena);
    grp.forEach((pe) => this.joinArena(pe, arena, true, 'human'));
    const spots = arena.ze.startSpots(grp.map((pe) => pe.player));
    for (const pe of grp) arena.spawnPlayer(pe.player, spots.get(pe.player));
    for (const pe of grp) pe.player.frozen = true;
    this.events.push({ type: 'arenaBuilt', arena });
    return arena;
  }

  // the arena a person plays in: a human in its own side's arena, a zombie in the other one (solo: the only one)
  arenaFor(side, role) {
    const own = this.arenas.find((a) => a.zeSide === side) || null;
    if (role === 'human') return own;
    return this.arenas.find((a) => a.zeSide !== side) || (this.solo ? own : null);
  }

  joinArena(pe, arena, atStart, role) {
    role = role || 'human';
    const human = role === 'human';
    const p = arena.addPlayer(pe.slot, pe.name, human ? 0 : 1, human ? this.colorFor(arena) : 0);
    p.person = pe; p.isBot = pe.bot;
    pe.arena = arena; pe.player = p; pe.status = 'playing'; pe.spec = null;
    pe.lastActive = this.time;
    pe.zeRole = role; pe.zeSide = pe.csTeam === 3 ? 3 : 2;
    this.seen.add(this.seenKey(pe));
    if (!human) {
      makeZombie(p, this.pickClass(pe, arena));
      p.playerstate = 'dead'; p.deathTime = arena.leveltime - (arena.ze ? arena.ze.respawnTics : this.zcfg.zombieRespawnTics) + this.zcfg.zombieFirstTics; p.zeSpawns = 0;
    }
    if (!atStart) {
      if (human) arena.spawnPlayer(p, arena.ze.lateHumanSpot());
      this.events.push({ type: 'join', person: pe, arena, role });
    }
    return p;
  }

  pickClass(pe, arena) {
    const sc = (arena.ze && arena.ze.sc.zombies) || {};
    const list = (sc.player_classes || this.zcfg.classes).filter((k) => ZCLASS[k]);
    const use = list.length ? list : ['IMP'];
    pe.zeClassN = (pe.zeClassN === undefined ? pe.slot : pe.zeClassN + 1);
    return use[pe.zeClassN % use.length];
  }

  // a human dead for the kill delay becomes a zombie in the other arena; the corpse stays where it fell
  toZombie(pe) {
    const A = pe.arena, old = pe.player;
    if (!A || !old) return;
    A.run(() => { if (old.mo && !old.mo.removed) { old.mo.player = null; A.bodyque.push(old.mo); if (A.bodyque.length > 32) { const o = A.bodyque.shift(); if (!o.removed) removeMobj(o); } } });
    old.mo = null;
    A.players.delete(pe.slot);
    const B = this.arenaFor(pe.zeSide, 'zombie');
    pe.arena = null; pe.player = null;
    if (!B) { pe.status = 'none'; this.spectate(pe, A); return; }
    const z = this.joinArena(pe, B, true, 'zombie');
    z.respawnGate = old.respawnGate;
    z.frags = old.frags; z.deaths = old.deaths;
    this.events.push({ type: 'zeSwap', person: pe, from: A, to: B });
  }

  spawnZombie(a, p) {
    if (p.zeSpawns > 0) makeZombie(p, this.pickClass(p.person, a));   // a new body each time: the class rotates
    const c = ZCLASS[p.zclass];
    const info = MOBJINFO[c.mt];
    let s = a.director.zeSpot(info, { minDist: 420 }) || a.director.zeSpot(info, { minDist: 250, close: true });
    if (!s) {
      const st = a.dmstarts.length ? a.dmstarts[(P_Random() * a.dmstarts.length) >> 8] : { x: 0, y: 0 };
      const f = a.fitSpot(st.x, st.y, 128, null, info.radius, info.height);
      if (!f) return false;
      s = { x: f.x, y: f.y };
    }
    // facing the nearest human
    let angle = 0, bd = 1e9;
    for (const h of a.ze.humans()) { const d = Math.hypot(h.mo.x - s.x, h.mo.y - s.y); if (d < bd) { bd = d; angle = pointToAngle(s.x, s.y, h.mo.x, h.mo.y); } }
    a.spawnPlayer(p, { x: s.x, y: s.y, angle });
    p.zeSpawns = (p.zeSpawns || 0) + 1;
    p.respawnNow = false;
    this.events.push({ type: 'zeZombie', person: p.person, arena: a, cls: p.zclass, first: p.zeSpawns === 1 });
    return true;
  }

  leaveArena(pe, why) {
    if (pe.arena) this.seen.add(this.seenKey(pe));
    super.leaveArena(pe, why);
  }

  joinCandidates() { return []; }
  botToReplace() { return null; }

  canJoin(pe) {
    if (this.state !== 'running' || pe.arena || this.zeResult) return false;
    if (pe.csTeam !== 2 && pe.csTeam !== 3) return false;
    return !!(this.arenaFor(pe.csTeam, 'zombie') || this.arenaFor(pe.csTeam, 'human'));
  }

  // late joiners: a human during the first stage of their side's arena (and only once a round), else a zombie
  lateHumanOk(pe) {
    const a = this.arenaFor(pe.csTeam, 'human');
    if (!a || a.finished || this.seen.has(this.seenKey(pe))) return false;
    if (a.countdown > 0) return true;
    const s0 = a.ze.stages[0];
    if (!s0) return a.time < 30 * TICRATE;
    return s0.state !== 'done' && a.time < (this.zcfg.lateHumanTics || 120 * TICRATE);
  }

  lateJoin(pe) {
    if (this.state !== 'running') return false;
    if (pe.arena) return true;
    if (this.pending.length) return false;   // arenas still being built: tried again a moment later
    if (!this.canJoin(pe)) { this.spectate(pe); return false; }
    const human = this.lateHumanOk(pe);
    const arena = human ? this.arenaFor(pe.csTeam, 'human') : this.arenaFor(pe.csTeam, 'zombie') || this.arenaFor(pe.csTeam, 'human');
    if (!arena || arena.finished) { this.spectate(pe); return false; }
    this.joinArena(pe, arena, false, human ? 'human' : 'zombie');
    return true;
  }

  humansAlive(side) {
    const a = this.arenaFor(side, 'human');
    if (!a) return 0;
    let n = 0;
    for (const p of a.players.values()) if (!p.zclass && !p.spectating && p.playerstate === 'live') n++;
    return n;
  }

  tic(remainingSeconds) {
    if (this.state !== 'running') return;
    this.time++;
    if (this.pending && this.pending.length) this.buildNext();
    for (const a of this.arenas) {
      if (a.finished && a.time >= a.finishedAt + this.cfg.arenaEndHoldTics) continue;
      a.time = (a.time || 0) + 1;
      if (a.countdown > 0) {
        a.countdown--;
        if (a.countdown === 0) {
          for (const p of a.players.values()) { p.frozen = false; p.protectUntil = a.leveltime + this.cfg.arena.spawnProtectTics; }
          a.events.push({ type: 'fight' });
          a.run(() => { a.director.begin(); a.ze.start(); });
        }
      }
      for (const p of a.players.values()) {
        if (p.isBot) zeBotThink(a, p);
        if (p.frozen || a.finished) { p.cmd.forwardmove = 0; p.cmd.sidemove = 0; p.cmd.buttons = 0; }
      }
      a.tic();
      if ((a.leveltime & 31) === 0) a.rescueOutside();
      this.zeArenaRules(a);
    }
    this.checkAfk();
    this.checkZe(remainingSeconds);
    this.checkAllEnds();
  }

  zeArenaRules(a) {
    if (a.finished) return;
    let swaps = null;
    for (const p of a.players.values()) {
      if (p.spectating) continue;
      if (!p.zclass) {
        if (p.playerstate !== 'dead') continue;
        if (p.zeSwapAt === undefined) p.zeSwapAt = this.time + this.zcfg.killDelayTics;
        else if (this.time >= p.zeSwapAt && p.person) (swaps || (swaps = [])).push(p.person);
      } else if ((p.playerstate === 'dead' || !p.mo) && a.countdown <= 0 && p.respawnGate !== false && a.leveltime - p.deathTime >= a.ze.respawnTics) {
        a.run(() => this.spawnZombie(a, p));
      }
    }
    if (swaps) for (const pe of swaps) if (!this.zeResult) this.toZombie(pe);
    a.run(() => a.ze.tic());
  }

  checkZe(remainingSeconds) {
    if (this.pending.length || this.zeResult || !this.arenas.length) return;
    if (this.arenas.some((a) => a.countdown > 0)) return;
    const win = this.zcfg.drawWindowTics;
    // escape: a side that got a human out wins at once (both on one tic: a draw)
    const out = this.arenas.filter((a) => a.ze.escaped > 0);
    if (out.length) { this.finishZe(out.length > 1 ? 0 : out[0].zeSide, 'escape'); return; }
    // the escape hold ended with nobody in the zone: that side failed (its humans are overrun)
    for (const a of this.arenas) if (a.ze.stages.some((s) => s.d.escape && s.state === 'done') && !a.ze.escaped && this.wipedAt[a.zeSide] === undefined) this.wipedAt[a.zeSide] = this.time;
    for (const a of this.arenas) if (this.wipedAt[a.zeSide] === undefined && this.humansAlive(a.zeSide) === 0) this.wipedAt[a.zeSide] = this.time;
    const w2 = this.wipedAt[2], w3 = this.wipedAt[3];
    if (this.solo) {
      const side = this.arenas[0].zeSide;
      if (this.wipedAt[side] !== undefined) { this.finishZe(side === 2 ? 3 : 2, 'wipe'); return; }
    } else if (w2 !== undefined || w3 !== undefined) {
      if (w2 !== undefined && w3 !== undefined && Math.abs(w2 - w3) <= win) { this.finishZe(0, 'wipe'); return; }
      const first = w2 !== undefined && (w3 === undefined || w2 <= w3) ? 2 : 3;
      if (this.time >= this.wipedAt[first] + win) { this.finishZe(first === 2 ? 3 : 2, 'wipe'); return; }
    }
    const limit = Math.min(...this.arenas.map((a) => a.ze.timeLimitTics));
    const started = Math.max(...this.arenas.map((a) => a.startTime + this.cfg.countdownTics));
    if (this.time - started >= limit || (remainingSeconds !== undefined && remainingSeconds <= 0)) this.timeUp();
  }

  timeUp() {
    if (this.zeResult || !this.arenas.length) return;
    const h2 = this.humansAlive(2), h3 = this.humansAlive(3);
    let w = h2 > h3 ? 2 : h3 > h2 ? 3 : 0;
    if (!w && !this.solo) {
      const r2 = (this.arenaFor(2, 'human') || { ze: { reached: () => 0 } }).ze.reached(), r3 = (this.arenaFor(3, 'human') || { ze: { reached: () => 0 } }).ze.reached();
      w = r2 > r3 ? 2 : r3 > r2 ? 3 : 0;
    }
    this.finishZe(w, 'time');
  }

  finishZe(winner, why) {
    if (this.zeResult) return;
    const S = ZE_SIDE_NAME;
    let text;
    if (why === 'escape') text = winner ? S[winner] + ' HUMANS ESCAPED!' : 'DRAW - BOTH ESCAPED';
    else if (why === 'wipe') text = winner ? S[winner] + ' WIN - ' + S[winner === 2 ? 3 : 2] + ' OVERRUN' : 'DRAW - ALL OVERRUN';
    else text = winner ? 'TIME UP - ' + S[winner] + ' WIN' : 'TIME UP - DRAW';
    this.zeResult = { winner, why, text };
    for (const a of this.arenas) {
      if (a.finished) continue;
      a.finished = true; a.finishedAt = a.time;
      a.result = { text, ze: true, winner, why, timeout: why === 'time' };
      for (const p of a.players.values()) p.frozenEnd = true;
      this.events.push({ type: 'arenaEnd', arena: a, result: a.result });
    }
    this.events.push({ type: 'zeEnd', winner, why, text });
  }
}
