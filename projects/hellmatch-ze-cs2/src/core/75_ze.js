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
// bots' zombie classes: the share of each class among an arena's zombie players they aim for, by what the stage is
const ZE_BOT_SHARE = { hold: { IMP: 0.4, DEMON: 0.45, LOSTSOUL: 0.15 }, boss: { IMP: 0.5, DEMON: 0.3, LOSTSOUL: 0.2 }, run: { IMP: 0.35, DEMON: 0.35, LOSTSOUL: 0.3 } };
// stage bosses by type: hp x the "players" health, dmg x their hits on humans (on top of aiDamage for the AI). Set from
// sim runs on the four ZE levels (19 Nov 2026): an arachnotron's plasma stream and a tripod's rockets wiped whole sides
const ZE_BOSS_TUNE = {
  BARON: { hp: 1, dmg: 1 }, KNIGHT: { hp: 1, dmg: 1 }, REVENANT: { hp: 0.9, dmg: 0.8 }, CACO: { hp: 1, dmg: 0.9 },
  MANCUBUS: { hp: 0.8, dmg: 0.6 }, ARACHNOTRON: { hp: 0.7, dmg: 0.4 }, CYBERDEMON: { hp: 1, dmg: 0.5 }, MASTERMIND: { hp: 1, dmg: 0.4 },
};
function zeBossTune(mo) {
  const key = mo.info.kind === 'monster' ? mo.info.key : mo.player && ZCLASS[mo.player.zclass] ? ZCLASS[mo.player.zclass].type : null;
  return ZE_BOSS_TUNE[key] || { hp: 1, dmg: 1 };
}
// weapons by the sidecar's ids (humans.loadout, give) and the ammo a weapon comes with (a start load)
const ZE_WEAPONS = { fist: WP_FIST, pistol: WP_PISTOL, shotgun: WP_SHOTGUN, ssg: WP_SUPERSHOTGUN, chaingun: WP_CHAINGUN, rocket: WP_MISSILE, plasma: WP_PLASMA, chainsaw: WP_CHAINSAW, bfg: WP_BFG };
const ZE_START_AMMO = { [WP_PISTOL]: [AM_CLIP, 50], [WP_SHOTGUN]: [AM_SHELL, 24], [WP_SUPERSHOTGUN]: [AM_SHELL, 24], [WP_CHAINGUN]: [AM_CLIP, 100], [WP_MISSILE]: [AM_MISL, 10], [WP_PLASMA]: [AM_CELL, 100], [WP_BFG]: [AM_CELL, 80] };
// ammo drops: the small Doom items by ammo type (AM_CLIP, AM_SHELL, AM_CELL, AM_MISL) and how much each type is wanted
// against the others when the humans use it equally (clips and shells mostly, cells and rockets rarer)
const ZE_DROP_ITEM = ['CLIP', 'SHELL', 'CELL', 'ROCKETAMMO'];
const ZE_DROP_WEIGHT = [1, 1, 0.3, 0.3];
function zeUsesAmmo(p, am) {
  for (let w = 0; w < NUMWEAPONS; w++) if (p.weaponowned[w] && WEAPONINFO[w].ammo === am) return true;
  return false;
}
// does any stage of a sidecar have this action (on_start / on_done)?
function zeHasAction(sc, key) {
  for (const st of (sc && sc.stages) || []) for (const act of (st.on_start || []).concat(st.on_done || [])) if (act && typeof act === 'object' && Object.keys(act)[0] === key) return true;
  return false;
}
const zeStageHas = (d, key) => (d.on_start || []).concat(d.on_done || []).some((act) => act && typeof act === 'object' && Object.keys(act)[0] === key);
const ZE_BOSS_OFFER = 5 * TICRATE;   // how long a new stage boss is up for a zombie player to take over
const ZE_CLASS_PICK_GUARD = 10;   // tics after a death in which the class keys don't change the class (they were the ability)

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

// where an AI zombie chasing a human heads for when Doom's straight line won't do: the next portal of the sector-graph
// route to its target (a point just past it once there). Null: the target is near, in the same sector, or the route
// needs a lift switch or a monster-blocking line (Doom's own chase then)
function zeChaseVia(mo) {
  const t = mo.target;
  if (!t || mo.boss || mo.player) return null;
  const dx = t.x - mo.x, dy = t.y - mo.y;
  if (dx * dx + dy * dy < 256 * 256) return null;
  const e = navNext(G.level, mo.x, mo.y, t.x, t.y);
  if (!e || e.lift || (e.line.flags & ML_BLOCKMONSTERS)) return null;
  if (e.perpetual && G.level.sectors[e.to].floorheight - mo.sector.floorheight > MAXSTEP) return null;
  const l = e.line, pp = portalPoint(l, mo.x, mo.y);
  if (Math.abs(pp.x - mo.x) + Math.abs(pp.y - mo.y) > 40) return pp;
  // at the portal: a point 48 past it, on the side of the next sector
  const len = Math.hypot(l.dx, l.dy) || 1, front = l.frontsector && l.frontsector.id === e.to ? 1 : -1;
  return { x: pp.x + front * l.dy / len * 48, y: pp.y - front * l.dx / len * 48 };
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
    this.navAt = [];              // tics at which the bots' sector graph is rebuilt (doors and lifts the stages move)
    this.offer = null;            // a boss up for takeover: { until, opted: Map(player -> tic it asked) }
    this.bossPlayer = null;       // the zombie player driving the boss
    this.started = false;
    this.spots = null;            // every place a zombie may appear (map things, starts, group points), reachable
    this.progress = null;         // sector id -> distance from the human starts
    this.lastMsg = null;
    this.drops = [];              // ammo dropped by the AI: { mo, until } (gone when picked up or after zcfg.dropTics)
    this.dropW = null; this.dropWAt = -1e9;   // ammo type weights for drops (worked out once a second)
    this.gifts = [];              // weapon ids given this round (a late human gets them too)
    this.ladder = null;           // the default upgrade ladder when the sidecar has no give action
  }

  // ---------------------------------------------------------------- set up (arena context, after load)
  setup() {
    const a = this.a, L = a.level;
    for (const [name, d] of Object.entries(this.sc.spawn_groups || {})) this.groups.set(name, { d, points: this.groupPoints(d), trickled: 0, nextTrickle: 0 });
    // every block starts shut; it opens when its condition is met
    for (const b of this.blocks) this.setBlock(b, true);
    // a sidecar that gives no weapons anywhere gets the default ladder (stage 1 done, stage 2 done, a boss stage starts)
    this.ladder = zeHasAction(this.sc, 'give') ? null : (this.round.zcfg.upgradeLadder || null);
    // candidate zombie spots: the level's own monster and item spots, starts, teleport landings, group points, 96 apart;
    // layout() keeps the ones a walker can reach from the human starts now
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
    for (const p of pts) if (!out.some((q) => Math.abs(q.x - p.x) < 96 && Math.abs(q.y - p.y) < 96)) out.push({ x: p.x, y: p.y, sec: L.sectorAt(p.x, p.y).id });
    this.spotPts = out;
    this.layout();
  }

  // how far along the level each sector is (walking distance from the human starts over the bots' sector graph) and the
  // zombie spots reachable now. Worked out again whenever a block opens or a stage moves a door / lift / floor: a sector
  // behind a door the script opens later is out of reach (Infinity) until then, and so are the spots in it
  layout() {
    const a = this.a, L = a.level;
    const starts = a.humanStarts && a.humanStarts.length ? a.humanStarts : a.dmstarts;
    this.progress = zeProgressMap(L, starts.length ? starts : [{ x: 0, y: 0 }]);
    const out = [];
    for (const p of this.spotPts || []) if (this.progress[p.sec] !== Infinity) out.push({ x: p.x, y: p.y, prog: this.progress[p.sec], sec: p.sec });
    this.spots = out;
    this.layoutDirty = false;
    this.layoutVer = (this.layoutVer || 0) + 1;
  }

  // 4.2: the sectors a zombie can walk from to a live human of this arena now (sector id -> 1), over the bots' sector
  // graph as it stands (blocked lines are out of it; doors a script opens or closes rebuild it, tic()): manual doors open
  // for zombies (zeBumpDoor, E), key doors only once the side holds the key when keys are kept, lifts that need a switch
  // don't count. Worked out at most every 16 tics (sooner after the graph or the layout changed). Null: no live human.
  reachToHumans() {
    const a = this.a, L = a.level, nav = buildNav(L);
    const m = this.reachMemo;
    if (m && m.nav === nav && m.ver === this.layoutVer && m.keys === this.keys.size && a.leveltime - m.t < 16) return m.r;
    const hs = this.humans();
    let r = null;
    if (hs.length) {
      const n = L.sectors.length;
      let rev = nav.zeRev;
      if (!rev || nav.zeRevKeys !== this.keys.size) {
        rev = [];
        for (let i = 0; i < n; i++) rev.push([]);
        for (let u = 0; u < n; u++) for (const e of nav[u]) if (this.zombiePasses(e)) rev[e.to].push(u);
        nav.zeRev = rev; nav.zeRevKeys = this.keys.size;
      }
      r = new Uint8Array(n);
      const q = [];
      for (const p of hs) { const id = p.mo.sector ? p.mo.sector.id : L.sectorAt(p.mo.x, p.mo.y).id; if (!r[id]) { r[id] = 1; q.push(id); } }
      while (q.length) { const v = q.pop(); for (const u of rev[v]) if (!r[u]) { r[u] = 1; q.push(u); } }
    }
    this.reachMemo = { nav, ver: this.layoutVer, keys: this.keys.size, t: a.leveltime, r };
    return r;
  }
  zombiePasses(e) {
    if (e.lift) return false;
    const kc = this.keysKept && e.line ? ZE_KEY_DOORS[e.line.special] : undefined;
    return !kc || this.keys.has(kc);
  }
  // can a zombie at (x, y) (sector id sec, when known) walk to a live human now? (true when nobody is alive to check)
  reachable(x, y, sec) {
    const r = this.reachToHumans();
    if (!r) return true;
    return !!r[sec !== undefined ? sec : this.a.level.sectorAt(x, y).id];
  }
  // the mover thinkers running now (doors, lifts, floors, ceilings), as a number that changes when one starts or stops
  moverSig() {
    let h = 0, n = 0;
    for (const t of this.a.thinkers) if (!t.removed && t.sector && t.type !== 'perpetualRaise') { h = (h * 31 + t.sector.id + 1) | 0; n++; }
    return h * 64 + n;
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
    this.layoutDirty = true;
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
  // where bots head for in a zone: its centre if a walker can reach it now, else the reachable point inside the zone
  // nearest the centre (E1M4's pillar hall box has the pillar itself in the middle). Remembered per layout.
  zoneCentre(z) {
    if (!z) return null;
    const memo = this.centreMemo || (this.centreMemo = new Map());
    const m = memo.get(z);
    if (m && m.v === this.layoutVer) return m.c;
    const c = this.zoneCentreNow(z);
    memo.set(z, { v: this.layoutVer, c });
    return c;
  }
  zoneCentreNow(z) {
    const L = this.a.level, prog = this.progress;
    const ok = (x, y) => !prog || prog[L.sectorAt(x, y).id] !== Infinity;
    let c;
    if (z.box) c = { x: (z.box[0] + z.box[2]) / 2, y: (z.box[1] + z.box[3]) / 2 };
    else {
      const ids = z.sector !== undefined ? [z.sector] : z.sectors || [];
      const cen = zeSectorCentres(L);
      let x = 0, y = 0, n = 0;
      for (const i of ids) if (cen[i]) { x += cen[i].x; y += cen[i].y; n++; }
      if (!n) return null;
      c = { x: x / n, y: y / n };
    }
    if (this.zoneHas(z, c.x, c.y) && ok(c.x, c.y) && this.a.fitSpot(c.x, c.y, 24)) return c;
    // samples inside the zone, nearest the centre first: the first a walker can reach and stand on
    let pts;
    if (z.box) {
      pts = [];
      const b = z.box, x1 = Math.min(b[0], b[2]), x2 = Math.max(b[0], b[2]), y1 = Math.min(b[1], b[3]), y2 = Math.max(b[1], b[3]);
      const step = Math.max(24, Math.ceil(Math.max(x2 - x1, y2 - y1) / 12));
      for (let x = x1 + step / 2; x < x2; x += step) for (let y = y1 + step / 2; y < y2; y += step) pts.push({ x, y });
    } else pts = this.groupPoints({ sectors: z.sector !== undefined ? [z.sector] : z.sectors || [] });
    pts.sort((p, q) => Math.hypot(p.x - c.x, p.y - c.y) - Math.hypot(q.x - c.x, q.y - c.y));
    for (const p of pts) if (ok(p.x, p.y) && this.a.fitSpot(p.x, p.y, 24)) return { x: p.x, y: p.y };
    for (const p of pts) if (ok(p.x, p.y)) return { x: p.x, y: p.y };
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
    if (this.navAt.length && this.navAt.some((t) => a.leveltime >= t)) { this.navAt = this.navAt.filter((t) => a.leveltime < t); a.level.nav = null; a.level.navCache = null; this.layoutDirty = true; }
    if (this.layoutDirty && this.spotPts) this.layout();
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
    if (this.offer) this.offerTic();
    if (this.bossPlayer) this.bossPlayerTic();
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
        if (a.leveltime < g.nextTrickle || g.trickled >= Math.max(1, Math.round((g.d.trickle.max || 10) * (a.director ? a.director.mapScale() : 1)))) continue;
        g.nextTrickle = a.leveltime + Math.round((g.d.trickle.every || 8) * TICRATE);
        if (a.director && a.director.room() > 0) {
          const type = a.director.pickType(g.d.ai);
          if (a.director.spawn(type, { group: name, minDist: 300 })) g.trickled++;
        }
      }
    }
    // blocks
    for (const b of this.blocks) if (b.on && b.d.until && this.met(b.d.until)) this.setBlock(b, false);
    // once a second: dropped ammo nobody took goes, and bullets creep back up to the floor (never fists only)
    if ((a.leveltime % TICRATE) === (a.index * 7) % TICRATE) this.secondTic();
  }

  secondTic() {
    const a = this.a, z = this.round.zcfg;
    // a door, lift or floor the level itself moved (a switch, a walk-over line, a manual door) started or stopped: the
    // sector graph (and the zombie spots, 4.2) follow what is open now; stage actions already schedule their own rebuild
    const sig = this.moverSig();
    if (this.moverWas !== undefined && sig !== this.moverWas) { a.level.nav = null; a.level.navCache = null; this.layoutDirty = true; }
    this.moverWas = sig;
    if (this.drops.length) {
      let keep = 0;
      for (const d of this.drops) {
        if (d.mo.removed) continue;
        if (a.leveltime >= d.until) { removeMobj(d.mo); continue; }
        this.drops[keep++] = d;
      }
      this.drops.length = keep;
    }
    if (z.ammoFloor > 0) for (const p of this.humans()) {
      const n = p.ammo[AM_CLIP];
      if (n >= z.ammoFloor || n >= p.maxammo[AM_CLIP]) continue;
      p.ammo[AM_CLIP] = n + 1;
      // out of everything and on the fist: back to a gun (Doom's giveAmmo switch for a first clip)
      if (n === 0 && p.readyweapon === WP_FIST && p.pendingweapon === WP_NOCHANGE) p.pendingweapon = p.weaponowned[WP_CHAINGUN] ? WP_CHAINGUN : WP_PISTOL;
    }
  }

  // ---------------------------------------------------------------- ammo, weapons, surges (Round 3)
  // an AI zombie died: maybe some ammo where it fell (Doom's dropped items: never respawn), the kind the humans here use
  dropFor(mo) {
    const z = this.round.zcfg, a = this.a;
    if (!(z.dropChance > 0) || P_Random() >= z.dropChance * 256) return null;
    if (a.leveltime - this.dropWAt >= TICRATE) {
      this.dropWAt = a.leveltime;
      const w = this.dropW || (this.dropW = [0, 0, 0, 0]);
      w[0] = w[1] = w[2] = w[3] = 0;
      for (const p of this.humans()) for (let am = 0; am < 4; am++) if (zeUsesAmmo(p, am)) w[am] += ZE_DROP_WEIGHT[am] * (1.3 - p.ammo[am] / (p.maxammo[am] || 1));
    }
    const w = this.dropW, tot = w[0] + w[1] + w[2] + w[3];
    if (!(tot > 0)) return null;
    let r = (P_Random() / 256) * tot, am = 0;
    while (am < 3 && r >= w[am]) { r -= w[am]; am++; }
    const it = spawnMobj(mo.x, mo.y, ONFLOORZ, MT[ZE_DROP_ITEM[am]]);
    it.flags |= MF_DROPPED;
    this.drops.push({ mo: it, until: a.leveltime + (z.dropTics || 30 * TICRATE) });
    // every item is a prop in CS2: the oldest one goes when too many lie about
    if (this.drops.length > (z.dropMax || 40)) { const o = this.drops.shift(); if (!o.mo.removed) removeMobj(o.mo); }
    return it;
  }

  // {"resupply": {"ammo": share, "health": n, "armor": n}}: every live human gets that share of the max of each ammo type
  // they can use, and health / armour up to 100
  resupply(v) {
    const r = Object.assign({}, this.round.zcfg.holdResupply || {}, v && typeof v === 'object' ? v : {});
    const share = Math.max(0, +r.ammo || 0), hp = Math.max(0, +r.health || 0), ar = Math.max(0, +r.armor || 0);
    const got = [];
    for (const p of this.humans()) {
      for (let am = 0; am < 4; am++) if (share > 0 && zeUsesAmmo(p, am)) {
        const old = p.ammo[am];
        p.ammo[am] = Math.min(p.maxammo[am], old + Math.max(1, Math.round(share * p.maxammo[am])));
        if (!old && p.readyweapon === WP_FIST && p.pendingweapon === WP_NOCHANGE) p.pendingweapon = p.weaponowned[WP_CHAINGUN] ? WP_CHAINGUN : WP_PISTOL;
      }
      if (hp > 0 && p.health < 100) { p.health = Math.min(100, p.health + hp); p.mo.health = p.health; }
      if (ar > 0 && p.armorpoints < 100) { p.armorpoints = Math.min(100, p.armorpoints + ar); if (!p.armortype) p.armortype = 1; }
      p.bonuscount += BONUSADD;
      startLocalSound(p, 'itemup');
      got.push(p);
    }
    if (got.length) this.a.events.push({ type: 'zeResupply', players: got });
  }

  // a weapon for a human (Doom's P_GiveWeapon for a weapon you don't have, with a start load of its ammo)
  giveTo(p, w, switchTo) {
    const had = p.weaponowned[w];
    p.weaponowned[w] = true;
    const am = ZE_START_AMMO[w];
    if (am) p.ammo[am[0]] = Math.min(p.maxammo[am[0]], Math.max(p.ammo[am[0]], am[1]));
    if (!had && switchTo) p.pendingweapon = w;
    return !had;
  }

  // {"give": ["chaingun", "ssg"]}: every live human gets these weapons; the first new one is brought up
  give(list) {
    const ids = (Array.isArray(list) ? list : [list]).map((x) => String(x).toLowerCase()).filter((id) => ZE_WEAPONS[id] !== undefined && id !== 'fist');
    if (!ids.length) return;
    for (const id of ids) if (!this.gifts.includes(id)) this.gifts.push(id);
    const got = [];
    for (const p of this.humans()) {
      let sw = true;
      for (const id of ids) if (this.giveTo(p, ZE_WEAPONS[id], sw)) sw = false;
      p.bonuscount += BONUSADD;
      startLocalSound(p, 'wpnup');
      got.push(p);
    }
    if (got.length) this.a.events.push({ type: 'zeGive', players: got, weapons: ids });
  }

  // the default ladder (no give action in the sidecar): entries "done:N" when the Nth stage is done, "start:N" when it
  // starts, "boss" when a boss stage starts
  ladderStep(key) {
    if (!this.ladder) return;
    for (const e of this.ladder) if (e && e.on === key && e.give) this.give(e.give);
  }

  // {"surge": {"group": "<spawn group>", "count": "auto" | n}}: a burst of AI at once, in packs (the group's points, else the
  // active stage's groups, else behind and on the flanks of the humans); "auto" = surgeBase + surgePerHuman x live humans
  surge(v) {
    const a = this.a, z = this.round.zcfg, d = a.director;
    if (!d || a.finished) return 0;
    v = v && typeof v === 'object' ? v : {};
    const h = this.humans().length;
    if (!h) return 0;
    const count = v.count === undefined || v.count === 'auto' ? Math.round(z.surgeBase + z.surgePerHuman * h) : Math.max(0, Math.round(+v.count || 0));
    let groups = v.group ? [v.group] : Array.isArray(v.groups) ? v.groups.slice() : null;
    if (!groups) { const s = this.active(); groups = s && s.d.zombie_spawns ? s.d.zombie_spawns.slice() : []; }
    groups = groups.filter((n) => this.groups.has(n));
    const made = d.burst(count, groups);
    if (made > 0) a.events.push({ type: 'zeSurge', count: made, auto: !!v.auto });
    return made;
  }

  startStage(s) {
    const a = this.a, z = this.round.zcfg;
    s.state = 'active'; s.startedAt = a.leveltime;
    a.events.push({ type: 'zeStage', phase: 'start', stage: s, name: s.name });
    // how far each live human got this round (the best_ze_stage stat)
    const hs = this.humans();
    for (const p of hs) if (p.person && s.i + 1 > (p.person.zeBestStage || 0)) p.person.zeBestStage = s.i + 1;
    if (hs.length) a.events.push({ type: 'zeReach', players: hs, stage: s.i + 1 });
    for (const act of s.d.on_start || []) this.act(act);
    for (const name of s.d.zombie_spawns || []) this.spawnGroup(name);
    this.ladderStep('start:' + (s.i + 1));
    if (s.d.boss) this.ladderStep('boss');
    // a hold, a boss or the escape starts: "HERE THEY COME" a moment later (after the stage's name or BOSS INCOMING),
    // unless the sidecar surges here itself
    if (z.autoSurge !== false && (s.d.boss || s.d.escape || (s.d.zone && s.left > 0)) && !(s.d.on_start || []).some((x) => x && x.surge !== undefined))
      this.queue.push({ at: a.leveltime + (z.surgeDelayTics || 0) + (s.d.boss ? TICRATE : 0), act: { surge: { count: 'auto', auto: true } } });
    if (s.d.boss) this.spawnBoss(s);
    else if (!(s.left > 0)) this.finishStage(s);   // no hold, no boss: a trigger stage, done at once
  }

  finishStage(s) {
    if (s.state === 'done') return;
    s.state = 'done'; s.doneAt = this.a.leveltime;
    const z = s.d.zone;
    const scored = this.humans();
    if (s.d.escape) {
      // the humans inside the zone when the hold ends have escaped (no zone: everyone alive)
      const out = z ? scored.filter((p) => this.zoneHas(z, p.mo.x, p.mo.y)) : scored;
      this.escaped = out.length;
      if (out.length) this.a.events.push({ type: 'zeEscaped', players: out });
    } else if (s.total > 0 && scored.length) this.a.events.push({ type: 'zeHold', players: scored, stage: s.i + 1 });
    if (scored.length) this.a.events.push({ type: 'zeScore', players: scored, points: s.d.escape ? this.round.zcfg.escapeScore : this.round.zcfg.holdScore, why: s.d.escape ? 'escape' : 'hold' });
    this.a.events.push({ type: 'zeStage', phase: 'done', stage: s, name: s.name, escape: !!s.d.escape, escaped: this.escaped });
    for (const act of s.d.on_done || []) this.act(act);
    if (s.d.escape) return;
    // the default ladder's weapons, then a completed hold's resupply (unless the stage has its own)
    this.ladderStep('done:' + (s.i + 1));
    if (s.total > 0 && !zeStageHas(s.d, 'resupply') && this.round.zcfg.holdResupply) this.resupply(this.round.zcfg.holdResupply);
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
      // the bots' sector graph is cached and only knows doors that were open (or usable) when it was built: rebuild it
      // while the door / lift / floor moves and after it has settled
      for (const d of [1, 2, 4, 8]) this.navAt.push(a.leveltime + d * TICRATE);
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
      // perpetual: Doom's perpetual platform (special 87): the lift keeps cycling, so nobody (bots included) needs its switch
      case 'lower_lift': mover((line) => { if (v.perpetual) doPlat(line, 'perpetualRaise', 0); else if (v.stay) doFloor(line, 'lowerFloorToLowest'); else doPlat(line, v.speed === 'fast' ? 'blazeDWUS' : 'downWaitUpStay', 0); }); break;
      case 'raise_floor': mover((line) => doFloor(line, 'raiseFloor')); break;
      case 'lower_floor': mover((line) => doFloor(line, 'lowerFloorToLowest')); break;
      case 'message': a.events.push({ type: 'zeMsg', text: String(typeof act.message === 'string' ? act.message : v.text || '').toUpperCase() }); break;
      case 'spawn_group': this.spawnGroup(typeof act.spawn_group === 'string' ? act.spawn_group : v.name); break;
      case 'teleport_zombies': if (a.director) a.director.relocate(!!v.behind || v.behind === undefined); break;
      case 'unblock': { const id = typeof act.unblock === 'string' ? act.unblock : v.id; for (const b of this.blocks) if (b.d.id === id) this.setBlock(b, false); break; }
      case 'music': a.events.push({ type: 'zeMusic', id: typeof act.music === 'string' ? act.music : v.id }); break;
      case 'resupply': this.resupply(act.resupply); break;
      case 'give': this.give(act.give); break;
      case 'surge': this.surge(act.surge); break;
      case 'score': { const pts = typeof act.score === 'number' ? act.score : v.points || 1; const h = this.humans(); if (h.length) a.events.push({ type: 'zeScore', players: h, points: pts, why: 'score' }); break; }
    }
  }

  spawnGroup(name) {
    const g = this.groups.get(name), d = this.a.director;
    if (!g || !d || !g.d.ai) return;
    const r = d.mapScale();
    for (const [type, n0] of Object.entries(g.d.ai)) {
      if (MT[type] === undefined || MOBJINFO[MT[type]].kind !== 'monster') continue;
      const n = Math.max(1, Math.round(n0 * r));
      for (let i = 0; i < n && d.room() > 0; i++) d.spawn(type, { group: name, minDist: 250 });
    }
  }

  spawnBoss(s) {
    const b = s.d.boss, a = this.a, d = a.director;
    const type = MT[b.type] !== undefined && MOBJINFO[MT[b.type]].kind === 'monster' ? b.type : 'BARON';
    const info = MOBJINFO[MT[type]];
    const n = Math.max(1, this.humans().length);
    // "players": 0.5 + 0.15 x live humans of the type's health; a heavy type (over 1000: tripod 4000, spider 3000) counts
    // 1000 + a quarter of the rest, so its fight lasts a little longer than a pain lord's, not four times as long
    const base = b.health_scale === 'players' || b.health_scale === undefined ? Math.min(info.spawnhealth, 1000 + Math.max(0, info.spawnhealth - 1000) * 0.25) : info.spawnhealth;
    const health = Math.round(base * (ZE_BOSS_TUNE[type] || { hp: 1 }).hp * (b.health_scale === 'none' ? 1 : (b.health_scale === 'players' || b.health_scale === undefined ? 0.5 + 0.15 * n : +b.health_scale || 1)));
    const at = b.at || null;
    let mo = null;
    if (d) mo = at ? d.placeAt(type, at[0], at[1], at[2] || 0, { health, boss: true, awake: true }) : d.spawn(type, { health, boss: true, minDist: 600 });
    this.boss = mo; this.bossMax = health; this.bossStage = s;
    this.bossName = String(b.name || info.name || type).toUpperCase();
    if (!mo) { this.finishStage(s); return; }   // nowhere to put it: the stage is skipped (the build validates the spot)
    a.events.push({ type: 'zeBoss', name: this.bossName, music: b.music || 'boss' });
    // a zombie player may take it over (3.1): offered for ZE_BOSS_OFFER tics
    if (this.round.zcfg.bossTakeover !== false && ZCLASS['B_' + type] && b.takeover !== false) {
      this.offer = { until: a.leveltime + ZE_BOSS_OFFER, opted: new Map() };
      a.events.push({ type: 'zeBossOffer', name: this.bossName });
    }
  }

  // ---------------------------------------------------------------- player bosses (3.1)
  // who may take the boss: a zombie player of this arena (not a bot, not AFK, not already a boss) whose CS2 pawn is up
  bossEligible(p) {
    return !!p && !!p.zclass && !(ZCLASS[p.zclass] && ZCLASS[p.zclass].boss) && !p.spectating && !p.isBot && !!p.person &&
      !p.person.afk && p.person.arena === this.a && p.respawnGate !== false;
  }

  // "near a zombie spawn": rising (a dead zombie comes back at a spawn), or within reach of a spawn point of the
  // active stage, of any zombie spot, or of the boss itself
  nearSpawn(p) {
    const mo = p.mo;
    if (p.playerstate !== 'live' || !mo || mo.removed) return true;
    if (this.boss && !this.boss.removed && Math.hypot(this.boss.x - mo.x, this.boss.y - mo.y) < 384) return true;
    const s = this.active();
    for (const n of (s && s.d.zombie_spawns) || []) { const g = this.groups.get(n); if (g) for (const q of g.points) if (Math.hypot(q.x - mo.x, q.y - mo.y) < 256) return true; }
    for (const q of this.spots || []) if (Math.abs(q.x - mo.x) < 192 && Math.abs(q.y - mo.y) < 192) return true;
    return false;
  }

  // the offer: the first eligible player to press USE near a spawn gets the boss at once; a press anywhere else is an
  // opt-in, and when the offer runs out the opted-in player with the most human kills this round gets it (ties: who
  // asked first). Nobody: the AI keeps it.
  offerTic() {
    const a = this.a, o = this.offer;
    if (!this.boss || this.boss.removed || this.boss.health <= 0 || this.boss.player) { this.offer = null; return; }
    for (const p of a.players.values()) {
      const down = !!(p.cmd.buttons & BT_USE), edge = down && !p.zOfferUse;
      p.zOfferUse = down;
      if (!edge || !this.bossEligible(p)) continue;
      if (this.nearSpawn(p)) { this.takeOver(p, 'first'); return; }
      if (!o.opted.has(p)) { o.opted.set(p, a.leveltime); a.events.push({ type: 'zeBossOptIn', player: p }); }
    }
    if (a.leveltime < o.until) return;
    let best = null, bk = -1, bt = Infinity;
    for (const [p, t] of o.opted) {
      if (!this.bossEligible(p) || a.players.get(p.slot) !== p) continue;
      const k = p.person.zeHumanKills || 0;
      if (k > bk || (k === bk && t < bt)) { best = p; bk = k; bt = t; }
    }
    this.offer = null;
    if (best) this.takeOver(best, 'kills');
    else a.events.push({ type: 'zeBossOfferEnd' });
  }

  // the player gets the boss's body where it stands, with its health; the AI monster goes (no corpse, no kill)
  takeOver(p, why) {
    const a = this.a, m = this.boss;
    const cls = m && ZCLASS['B_' + m.info.key];
    if (!cls || m.removed || m.health <= 0 || m.player) return false;
    const x = m.x, y = m.y, angle = m.angle, health = m.health;
    this.offer = null;
    a.run(() => {
      if (p.mo && !p.mo.removed && p.playerstate === 'live') { const o = p.mo; spawnMobj(o.x, o.y, o.z, MT.TFOG); o.player = null; removeMobj(o); p.mo = null; }
      m.boss = false;
      removeMobj(m);
      if (a.director) { a.director.spawned--; a.director.bossCount--; }
      makeZombie(p, cls.key);
      a.spawnPlayer(p, { x, y, angle, silent: true });
      p.health = health; p.mo.health = health; p.mo.maxHealth = this.bossMax; p.mo.boss = true;
      p.zbossMax = this.bossMax; p.protectUntil = 0;
      startSound(p.mo, p.mo.info.seesound || 'brssit');
    });
    this.boss = p.mo; this.bossPlayer = p;
    a.events.push({ type: 'zeBossTaken', player: p, name: this.bossName, why });
    return true;
  }

  // every tic while a player drives the boss: killed -> the stage's own check ends it; gone, AFK or idle too long ->
  // the Doom AI takes the body back
  bossPlayerTic() {
    const p = this.bossPlayer, a = this.a;
    if (!p.mo || p.mo !== this.boss) { this.bossPlayer = null; return; }
    if (p.mo.health <= 0 || p.playerstate !== 'live') { this.bossPlayer = null; return; }   // killed: the boss is down
    const pe = p.person;
    if (a.players.get(p.slot) !== p || p.spectating || !pe || pe.arena !== a) { this.bossRelease(p, 'left'); return; }
    if (pe.afk) { this.bossRelease(p, 'afk'); return; }
    if (!p.isBot && this.round.time - (pe.lastActive || 0) > this.round.zcfg.bossAfkTics) this.bossRelease(p, 'idle');
  }

  // the AI takes the boss back from its player (who left, went AFK or sat idle): a monster of the boss's type where the
  // body stood, with its health; the player (if still here) rises as their own class again in 2 s
  bossRelease(p, why) {
    if (this.bossPlayer !== p) return false;
    const a = this.a, mo = p.mo, cls = ZCLASS[p.zclass];
    this.bossPlayer = null;
    if (!mo || !cls || !cls.boss) return false;
    const x = mo.x, y = mo.y, angle = mo.angle, health = Math.max(1, mo.health);
    let nm = null;
    a.run(() => {
      if (!mo.removed) { mo.player = null; mo.boss = false; removeMobj(mo); }
      if (p.mo === mo) p.mo = null;
      p.playerstate = 'dead';
      p.deathTime = a.leveltime - this.respawnTics + 2 * TICRATE;
      p.zbossMax = 0;
      if (a.director) {
        nm = a.director.placeAt(cls.type, x, y, angle, { health, boss: true, awake: true });
        if (!nm) nm = a.director.spawn(cls.type, { health, boss: true, minDist: 300, close: true });
      }
      if (nm) { nm.maxHealth = this.bossMax; startSound(nm, nm.info.seesound || 'brssit'); }
    });
    if (nm) this.boss = nm;
    a.events.push({ type: 'zeBossBack', player: p, name: this.bossName, why });
    return true;
  }

  // ---------------------------------------------------------------- humans
  humanLoadout(p) {
    const hu = this.sc.humans || {};
    p.health = hu.health || 100;
    // the smaller side gets Hellmatch's +25% (both sides play the same level against hordes fed by the other side)
    const sizes = this.round.zeSizes || {};
    const mine = sizes[this.side] || 0, theirs = sizes[this.side === 2 ? 3 : 2] || 0;
    if (theirs > mine && mine > 0) p.health = Math.round(p.health * 1.25);
    let last = null;
    for (const name of hu.loadout || ['pistol', 'shotgun']) {
      const w = ZE_WEAPONS[String(name).toLowerCase()];
      if (w === undefined) continue;
      p.weaponowned[w] = true; last = w;
      const am = ZE_START_AMMO[w];
      if (am) p.ammo[am[0]] = Math.max(p.ammo[am[0]], Math.min(p.maxammo[am[0]], am[1]));
    }
    // a late human gets what the others were given this round
    for (const id of this.gifts) this.giveTo(p, ZE_WEAPONS[id], false);
    if (last !== null) { p.readyweapon = last; p.pendingweapon = last; }
    // a late human joining mid-stage has reached that stage too
    if (p.person) {
      let n = 0;
      for (const s of this.stages) if (s.state !== 'pending') n = s.i + 1;
      if (n > (p.person.zeBestStage || 0)) { p.person.zeBestStage = n; this.a.events.push({ type: 'zeReach', players: [p], stage: n }); }
    }
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
      // starts on small pads (MAP03): fitSpot keeps to the start's own sector, so look round it in the next sectors too
      // (walkable from the start); two players on one spot can never move again
      if (!f) for (let r = 64; r <= 320 && !f; r += 64) for (const o of starts) {
        for (let k = 0; k < 8 && !f; k++) {
          const x = o.x + r * Math.cos(k * Math.PI / 4), y = o.y + r * Math.sin(k * Math.PI / 4);
          if (!a.inside(x, y) || !a.run(() => walkableLine(o.x, o.y, x, y))) continue;
          f = a.fitSpot(x, y, 32, taken);
        }
        if (f) break;
      }
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
    // a boss stage: go and fight it (bots keep their distance, bot code)
    else if (s && s.d.boss && this.boss && !this.boss.removed && this.boss.health > 0) g = { x: this.boss.x, y: this.boss.y, boss: this.boss };
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
    super(arena, 'ze', { maxAlive: zcfg.cap || zcfg.capMax || 96 });
    this.ze = ze; this.zcfg = zcfg;
    this.capN = ZeDirector.capFor(zcfg, ze.sc, (ze.round.zeSizes || {})[ze.side] || 0);   // live zombies here (AI + players)
    this.reserve = [];            // map monsters that didn't fit under the cap at the start: they come in later at their own spots
    this.roster = [];             // [type, weight]: what the respawning horde is made of (the map's own mix)
    this.nextFill = 0; this.nextTrim = -1e9;
    this.aliveNow = 0; this.awakeNow = 0;
    this.packNo = 0;              // packs sent so far (they take turns: the stage's spawn groups, behind, the flanks)
    this.begun = false;
  }

  // the arena's cap: capBase + capPerPlayer x the players placed here at round start, within capMin..capMax (cfg.cap: a
  // fixed number instead); a sidecar's zombies.cap is a maximum on top
  static capFor(zcfg, sc, placed) {
    let cap = zcfg.cap > 0 ? zcfg.cap : Math.max(zcfg.capMin || 32, Math.min(zcfg.capMax || 96, (zcfg.capBase || 24) + (zcfg.capPerPlayer || 4) * placed));
    const zs = (sc && sc.zombies) || {};
    if (zs.cap > 0) cap = Math.min(cap, zs.cap);
    return Math.max(8, Math.round(cap));
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

  // the share of a level's monsters (and of each spawn group) used now, by the side's humans at the start: about all
  // of them from 8 humans up, about half for 4, a third for 2 (spawn groups and trickles too)
  mapScale() {
    const h = Math.max(1, this.round().zeSizes[this.ze.side] || this.players().length);
    return Math.max(0.3, Math.min(1, this.zcfg.mapScaleBase + this.zcfg.mapScalePerHuman * h));
  }
  round() { return this.ze.round; }

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
    // a level's monsters are many for a few humans: fewer humans than the map was made for -> an even share of them
    // is placed now and the rest wait in the reserve (they come in as the fill asks for AI)
    const r = this.mapScale();
    let acc = 0, placed = 0;
    for (const m of a.mapMonsters) {
      let key = replace[m.key] || m.key;
      if (drop.has(key) || drop.has(m.key) || MT[key] === undefined) continue;
      if (!ZE_FILL_SKIP.has(key)) mix.set(key, (mix.get(key) || 0) + 1);
      acc += r;
      // (the level's own monsters wait asleep: at most sleepMax of the cap, the horde needs the rest)
      // (4.2: one shut away from the humans for now, e.g. behind MAP06's west doors, waits in the reserve until reachable)
      if (acc < 1 || placed >= this.sleepMax() || !this.walkable(m.x, m.y)) { this.reserve.push(Object.assign({}, m, { key })); continue; }
      placed++;
      acc -= 1;
      a.run(() => this.placeAt(key, m.x, m.y, m.angle, { ambush: m.ambush }));
    }
    this.roster = Array.from(mix.entries());
    this.nextFill = a.leveltime + 3 * TICRATE;
  }

  // a map monster's own spot is in play: reachable from the human starts as the level is open now (4.2: not shut away
  // for good, like MAP06's west wing behind its never-opening doors; an ambush below a drop ahead still counts)
  walkable(x, y) {
    const ze = this.ze;
    return !ze.progress || ze.progress[this.a.level.sectorAt(x, y).id] !== Infinity;
  }

  // how many of the level's own monsters may wait asleep at once (a big level would fill the whole cap with them)
  sleepMax() { return Math.round(this.capN * (this.zcfg.sleepShare === undefined ? 0.3 : this.zcfg.sleepShare)); }

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
  // sight and at least minDist from all of them. close: the nearest such spot behind them (bringing a straggler back).
  // flank: a spot level with the humans (about as far along the level as they are) instead of behind them; groups: false
  // ignores the stage's spawn groups. The spot found carries its candidate point (base) for a pack around it.
  zeSpot(info, opts) {
    const a = this.a, ze = this.ze;
    const minDist = opts && opts.minDist !== undefined ? opts.minDist : 450;
    const hs = this.players();
    let cands = [];
    const groups = [];
    if (opts && opts.group) groups.push(opts.group);
    else if (!(opts && opts.groups === false)) { const s = ze.active(); if (s) for (const n of s.d.zombie_spawns || []) groups.push(n); }
    // 4.2: only places a zombie can walk from to a live human now (a spawn group or spot cut off behind a shut door or a
    // block is skipped; nothing connected: no spot, a zombie player then rises near a human, ZeRound.spawnZombie)
    const reach = hs.length ? ze.reachToHumans() : null;
    const ok = reach ? (p) => !!reach[p.sec !== undefined ? p.sec : (p.sec = a.level.sectorAt(p.x, p.y).id)] : null;
    for (const n of groups) { const g = ze.groups.get(n); if (g) for (const p of g.points) if (!ok || ok(p)) cands.push(p); }
    const fromGroup = cands.length > 0;
    if (fromGroup) shuffle(cands);
    else {
      let spots = ze.spots || [];
      if (ok) spots = spots.filter(ok);
      if (hs.length) {
        let minProg = Infinity, maxProg = -Infinity;
        for (const p of hs) { const v = ze.progress[a.level.sectorAt(p.mo.x, p.mo.y).id]; if (v < minProg) minProg = v; if (v > maxProg && v !== Infinity) maxProg = v; }
        if (opts && opts.flank && minProg !== Infinity) {
          const side = spots.filter((s) => s.prog >= minProg - 500 && s.prog <= maxProg + 400);
          if (side.length >= 3) cands = shuffle(side);
        }
        if (!cands.length) {
          // the nearest few spots behind the humans, in a random order (a pack from the same doorway every time is a
          // conveyor belt, not a horde)
          const behind = spots.filter((s) => s.prog < minProg - 128).sort((x, y) => y.prog - x.prog);
          if (behind.length >= 3) { cands = behind.slice(0, 10); shuffle(cands); cands = cands.concat(behind.slice(10)); }
          else cands = spots.slice().sort((x, y) => (minProg === Infinity ? 0 : Math.abs(x.prog - minProg) - Math.abs(y.prog - minProg)));
        }
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
      const spot = { x: f.x, y: f.y, near, base: c };
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
    return a.run(() => this.spawnAt(type, spot.x, spot.y, opts));
  }

  // an AI zombie at (x, y) if it fits there, awake, out of a teleport fog (quiet: no sound, for the rest of a pack)
  spawnAt(type, x, y, opts) {
    const info = MOBJINFO[MT[type]], a = this.a;
    const mo = spawnMobj(x, y, ONFLOORZ, MT[type]);
    if (!checkPosition(mo, x, y) || TM.ceilingz - TM.floorz < mo.height || TM.floorz - mo.sector.floorheight > MAXSTEP) { removeMobj(mo); return null; }
    mo.floorz = TM.floorz; mo.ceilingz = TM.ceilingz; mo.z = TM.floorz; mo.pz = mo.z;
    if (info.flags & MF_FLOAT) { mo.z = Math.min(mo.ceilingz - mo.height, mo.floorz + 24); mo.pz = mo.z; }
    if (opts && opts.health) { mo.health = opts.health; mo.maxHealth = opts.health; }
    if (opts && opts.boss) { mo.boss = true; this.bossCount++; }
    const fog = spawnMobj(x, y, mo.z, MT.TFOG);
    if (!(opts && opts.quiet)) startSound(fog, 'telept');
    this.wake(mo);
    this.spawned++;
    a.onMonsterSpawned(mo, null);
    return mo;
  }

  // a pack: up to n AI at once around one hidden spot (from a spawn group, behind the humans or on a flank); the types
  // from the group's own mix (else the map's). Returns how many came.
  pack(n, where) {
    const a = this.a, ze = this.ze;
    const g = where.group ? ze.groups.get(where.group) : null;
    const ai = g && g.d.ai ? g.d.ai : null;
    let type = this.pickType(ai);
    const info = MOBJINFO[MT[type]];
    const spot = a.run(() => this.zeSpot(info, { minDist: where.minDist || 450, group: where.group, flank: where.flank, groups: false }));
    if (!spot) return 0;
    let made = 0;
    a.run(() => {
      for (let i = 0; i < n; i++) {
        if (i) type = this.pickType(ai);
        const inf = MOBJINFO[MT[type]];
        const f = i === 0 ? spot : a.fitSpot(spot.base.x, spot.base.y, 192, null, inf.radius, inf.height, inf);
        if (!f) continue;
        if (this.spawnAt(type, f.x, f.y, { quiet: i > 0 })) made++;
      }
    });
    return made;
  }

  // a burst of count AI in packs (packMin..packMax each) taking turns between the given spawn groups and the spots behind
  // and on the flanks of the humans; never over the cap. Returns how many came.
  burst(count, groups) {
    const z = this.zcfg;
    let room = this.capN - this.zombiePlayers() - this.alive();
    let made = 0, fails = 0;
    while (made < count && room > 0 && fails < 4) {
      const n = Math.min(count - made, room, z.packMax || 6);
      const k = this.packNo++;
      const where = groups && groups.length ? (k % 3 === 2 ? { flank: true } : { group: groups[k % groups.length] }) : { flank: (k & 1) === 1 };
      const got = this.pack(n, where);
      if (!got) fails++;
      made += got; room -= got;
    }
    return made;
  }

  // one pass over the horde with each check: live AI, how many are awake (a map monster still asleep where the mapper put
  // it is an ambush ahead, not part of the pressure: it doesn't count against the AI wanted), and the far flags (AI with
  // no live human within farDist thinks every farEvery-th tic only, Arena.tic). Returns the live AI count.
  survey() {
    const far = this.zcfg.farDist || 0, hs = this.a.playerMobjs;
    let alive = 0, awake = 0;
    for (const m of this.a.mobjs) {
      if (m.info.kind !== 'monster') continue;
      if (m.health > 0) { alive++; if (STATES[m.state].action !== 'A_Look') awake++; }
      let f = far > 0 && m.health > 0 && !m.boss;
      if (f) for (const h of hs) if (Math.abs(h.x - m.x) < far && Math.abs(h.y - m.y) < far && Math.hypot(h.x - m.x, h.y - m.y) < far) { f = false; break; }
      m.zfar = f;
    }
    this.awakeNow = awake;
    return alive;
  }

  tic() {
    const a = this.a;
    if (a.finished || !this.begun) return;
    if ((a.leveltime & 7) !== (a.index & 7)) return;   // the horde is checked 4-5 times a second (arenas offset)
    const alive = this.aliveNow = this.survey();
    const zp = this.zombiePlayers();
    // fill: the reserve first (at its own spots, when out of sight), then packs of the map's mix (a few at once from one
    // hidden spot, taking turns: the stage's spawn groups, behind the humans, their flanks). The AI wanted counts the
    // awake AI; everything counts against the cap.
    const want = Math.min(this.aiTarget(), this.capN - zp - (alive - this.awakeNow));
    if (a.leveltime >= this.nextFill && this.awakeNow < want) {
      let ok = null;
      if (this.reserve.length && alive - this.awakeNow < this.sleepMax()) {
        const m = this.reserve[0];
        const hs = this.players();
        const far = hs.every((p) => Math.hypot(p.mo.x - m.x, p.mo.y - m.y) > 700) && this.walkable(m.x, m.y);
        if (far) ok = a.run(() => this.placeAt(m.key, m.x, m.y, m.angle, { ambush: m.ambush }));
        this.reserve.push(this.reserve.shift());
        if (ok) this.reserve.pop();
      }
      const short = want - this.awakeNow - (ok ? 1 : 0);
      const pmin = this.zcfg.packMin || 3, pmax = this.zcfg.packMax || 6;
      // a pack once enough are missing (or a straggler or two after a quiet spell)
      if (!ok && short > 0 && (short >= pmin || a.leveltime - this.nextFill > 4 * TICRATE)) {
        const n = Math.min(short, pmin + (P_Random() % (pmax - pmin + 1)));
        const s = this.ze.active(), groups = s && s.d.zombie_spawns ? s.d.zombie_spawns.filter((g) => this.ze.groups.has(g)) : [];
        const k = this.packNo++;
        const where = groups.length && k % 3 === 0 ? { group: groups[(k / 3 | 0) % groups.length], minDist: 500 } : { flank: k % 3 === 2, minDist: 500 };
        const got = this.pack(n, where);
        ok = got > 0;
        this.nextFill = a.leveltime + (ok ? (this.zcfg.packGapTics || 2 * TICRATE) : 2 * TICRATE);
      } else if (ok) this.nextFill = a.leveltime + (this.zcfg.fillGapTics || TICRATE);
    }
    // over the cap (zombie players joined): the AI furthest from every human and out of the fight goes away (far off,
    // or at least 400 away and out of every human's sight); the further over, the quicker
    const over = alive + zp - this.capN;
    if (over > 0 && a.leveltime >= this.nextTrim + (over > 2 ? 8 : 2 * TICRATE)) {
      this.nextTrim = a.leveltime;   // the last trim
      const hs = this.players();
      const cands = [];
      let far = null;
      for (const m of a.mobjs) {
        if (m.info.kind !== 'monster' || m.health <= 0 || m.boss) continue;
        let near = 1e9;
        for (const p of hs) { const d = Math.hypot(p.mo.x - m.x, p.mo.y - m.y); if (d < near) near = d; }
        if (near > 400) cands.push({ m, near });
        else if (near > 160 && (!far || near > far.near)) far = { m, near };
      }
      cands.sort((x, y) => y.near - x.near);
      if (!cands.length && far) cands.push(far);
      // up to `over` of them at once (a burst of humans dying brings that many zombie players in on one tic)
      const gone = [];
      a.run(() => {
        for (const c of cands.slice(0, 12)) {
          if (gone.length >= over) break;
          if (c.near > 1200 || !hs.some((p) => checkSight(p.mo, c.m))) gone.push(c.m);
        }
      });
      // well over and everything is in sight: the furthest one that isn't right on top of a human goes anyway
      if (!gone.length && over > 2 && cands.length) gone.push(cands[0].m);
      if (gone.length) a.run(() => { for (const m of gone) { this.spawned--; removeMobj(m); } });
    }
    if ((a.leveltime % 88) < 8) this.unstick();   // every 2.5 s
  }

  // stuck AI (Doom's chase is greedy): no headway towards the nearest human for 20 s and not fighting on the same floor ->
  // back in behind the humans. Unlike Boss Battle, a sleeping monster is left asleep: the map's own monsters wait ahead
  // Also the horde's leash (a director's job, like Left 4 Dead's): awake AI that has been 1000+ from every human for 6 s
  // and is out of their sight (or 1600+ away) is recycled: it goes, and as many come back in packs behind the humans
  // and on their flanks. Without it a hold far from where the horde was is fought by a trickle.
  unstick() {
    const a = this.a, players = this.players();
    if (!players.length) return;
    const recycle = [];
    for (const m of Array.from(a.mobjs)) {
      if (m.info.kind !== 'monster' || m.health <= 0 || m.boss) continue;
      if (STATES[m.state].action === 'A_Look') { m.bestNear = undefined; m.zfarAt = undefined; continue; }
      let nearest = null, near = 1e9;
      for (const p of players) { const d = Math.hypot(p.mo.x - m.x, p.mo.y - m.y); if (d < near) { near = d; nearest = p; } }
      if (near > 1000) {
        if (m.zfarAt === undefined) m.zfarAt = a.leveltime;
        else if (a.leveltime - m.zfarAt >= 6 * TICRATE && (near > 1600 || !a.run(() => players.some((p) => checkSight(p.mo, m))))) { recycle.push(m); continue; }
      } else m.zfarAt = undefined;
      if (m.bestNear === undefined || near < m.bestNear - 64) { m.bestNear = near; m.progressAt = a.leveltime; continue; }
      // (left far behind, 1400+ away: back in after 8 s, not 20)
      if (a.leveltime - (m.progressAt || 0) < (near > 1400 ? 8 : 20) * TICRATE) continue;
      const sameFloor = (m.flags & MF_FLOAT) || Math.abs(nearest.mo.z - m.z) <= 2 * MAXSTEP;
      if (sameFloor && (near < 160 || a.run(() => checkSight(m, nearest.mo)))) { m.progressAt = a.leveltime; m.bestNear = near; continue; }
      const re = this.spawn(m.info.key, { health: m.health, minDist: 350, close: true });
      if (re) { this.spawned--; a.run(() => removeMobj(m)); }
      else m.progressAt = a.leveltime;
    }
    if (recycle.length) {
      a.run(() => { for (const m of recycle) { this.spawned--; removeMobj(m); } });
      this.burst(recycle.length, null);
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
      if (!p.zclass || p.playerstate !== 'live' || !p.mo || p.mo.boss || !far(p.mo.x, p.mo.y)) continue;
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
    this.finale = null;          // the escape finale (Round 4): { arena, sides: { 2|3: { at, entered: Map(slot -> person) } }, first, sameTic, fight }
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
    this.zeResult = null; this.wipedAt = {}; this.seen = new Set(); this.zeStarted = false; this.finale = null;
    for (const pe of this.people.values()) { pe.zeHumanKills = 0; pe.zeBestStage = 0; }   // humans killed as a zombie this round (boss takeover), furthest stage reached as a human
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

  // the arena a person plays in: a human in its own side's arena, a zombie in the other one (solo: the only one). The
  // finale arena is never one of these, and a zombie never goes into an arena that is over (its side escaped)
  arenaFor(side, role) {
    let own = null, other = null;
    for (const a of this.arenas) {
      if (a.zeFinale) continue;
      if (a.zeSide === side) { if (!own) own = a; } else if (!other) other = a;
    }
    if (role === 'human') return own;
    if (other) return other.finished ? null : other;
    return this.solo && own && !own.finished ? own : null;
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

  // the classes a zombie player may be in this arena (the sidecar's list, else the config's); never a boss body
  classList(arena) {
    const sc = (arena && arena.ze && arena.ze.sc.zombies) || {};
    const list = (sc.player_classes || this.zcfg.classes).filter((k) => ZCLASS[k] && !ZCLASS[k].boss);
    return list.length ? list : ['IMP'];
  }

  // the class of a zombie's next body: a person's own pick (kept across deaths and rounds; the first one by slot),
  // a bot's by what the horde in that arena lacks
  pickClass(pe, arena) {
    const list = this.classList(arena);
    if (pe.bot) return this.botClass(pe, arena, list);
    if (pe.zeClassPick === undefined || !ZCLASS[pe.zeClassPick]) pe.zeClassPick = list[pe.slot % list.length];
    return list.includes(pe.zeClassPick) ? pe.zeClassPick : list[0];
  }

  // bots pick by need: each class has a share of the zombie players that suits the stage (holds want demons to break
  // the line and imps to shoot over it; open running wants lost souls too); the class furthest below its share wins.
  // A bot that died within 6 s of rising tries something else.
  botClass(pe, arena, list) {
    if (list.length === 1) return list[0];
    const p = pe.player, count = {};
    let n = 0;
    for (const q of arena.players.values()) {
      if (q === p || !q.zclass || q.spectating || !list.includes(q.zclass)) continue;
      count[q.zclass] = (count[q.zclass] || 0) + 1; n++;
    }
    const s = arena.ze && arena.ze.active();
    const want = s && s.d.boss ? ZE_BOT_SHARE.boss : s && s.d.zone ? ZE_BOT_SHARE.hold : ZE_BOT_SHARE.run;
    const last = p && p.zclass, short = !!p && p.zeSpawns > 0 && p.deathTime - p.spawnTime < 6 * TICRATE;
    let best = list[0], bv = -Infinity;
    for (const k of list) {
      let v = (want[k] || 0.2) * (n + 1) - (count[k] || 0) + (P_Random() & 15) / 64;
      if (short && k === last) v -= 1;
      if (v > bv) { bv = v; best = k; }
    }
    return best;
  }

  // a dead zombie player cycles their class (the weapon keys); the next body is that class. dir: +1 / -1
  zeCycleClass(pe, dir) {
    const p = pe && pe.player, a = pe && pe.arena;
    if (!p || !a || !p.zclass || p.spectating || this.zeResult || (ZCLASS[p.zclass] && ZCLASS[p.zclass].boss)) return false;
    if (p.playerstate === 'live' && p.mo && !p.mo.removed) return false;
    if (a.leveltime - (p.deathTime || 0) < ZE_CLASS_PICK_GUARD) return false;   // an ability key pressed at the moment of death
    const list = this.classList(a);
    let i = list.indexOf(p.zclass);
    i = i < 0 ? 0 : (i + (dir < 0 ? -1 : 1) + list.length) % list.length;
    pe.zeClassPick = list[i];
    makeZombie(p, list[i]);
    this.events.push({ type: 'zeClass', person: pe, cls: list[i] });
    return true;
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
    // a new body each time: the person's pick (changed while dead), a bot's by need, back from a boss body
    if (p.zeSpawns > 0 || (ZCLASS[p.zclass] && ZCLASS[p.zclass].boss)) makeZombie(p, this.pickClass(p.person, a));
    p.zbossMax = 0;
    const c = ZCLASS[p.zclass];
    const info = MOBJINFO[c.mt];
    let s = a.director.zeSpot(info, { minDist: 420 }) || a.director.zeSpot(info, { minDist: 250, close: true });
    if (!s) {
      // a start a zombie can walk to the humans from; else a free spot 256-512 from a live human, in a sector connected to
      // the humans (out of sight is not asked for here); else any start (the old fallback)
      const near = a.dmstarts.filter((q) => a.ze.reachable(q.x, q.y));
      let f = null;
      if (near.length) { const st = near[(P_Random() * near.length) >> 8]; f = a.fitSpot(st.x, st.y, 128, null, info.radius, info.height); }
      const hs = a.ze.humans();
      if (!f && hs.length) {
        const h = hs[(P_Random() * hs.length) >> 8].mo;
        for (const r of [512, 384, 256]) {
          for (let k = 0; k < 8 && !f; k++) {
            const x = h.x + r * Math.cos(k * Math.PI / 4), y = h.y + r * Math.sin(k * Math.PI / 4);
            if (!a.inside(x, y) || !a.ze.reachable(x, y)) continue;
            f = a.fitSpot(x, y, 48, null, info.radius, info.height);
          }
          if (f) break;
        }
      }
      if (!f && a.dmstarts.length) { const st = a.dmstarts[(P_Random() * a.dmstarts.length) >> 8]; f = a.fitSpot(st.x, st.y, 128, null, info.radius, info.height); }
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
    // a boss's player leaving (disconnect, team change, AFK, spectate): the AI takes the boss back before the body goes
    if (pe.arena && pe.arena.ze && pe.player && pe.arena.ze.bossPlayer === pe.player) pe.arena.ze.bossRelease(pe.player, why || 'left');
    super.leaveArena(pe, why);
  }

  joinCandidates() { return []; }
  botToReplace() { return null; }

  canJoin(pe) {
    if (this.state !== 'running' || pe.arena || this.zeResult) return false;
    if (pe.csTeam !== 2 && pe.csTeam !== 3) return false;
    if (pe.zeFinaleOut === this.roundNumber) return false;   // died in the finale: out for the round
    return !!(this.arenaFor(pe.csTeam, 'zombie') || (this.lateHumanOk(pe) && this.arenaFor(pe.csTeam, 'human')));
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
    const arena = human ? this.arenaFor(pe.csTeam, 'human') : this.arenaFor(pe.csTeam, 'zombie');
    if (!arena || arena.finished) { this.spectate(pe); return false; }
    this.joinArena(pe, arena, false, human ? 'human' : 'zombie');
    return true;
  }

  // live humans of a side: in its own arena and in the finale
  humansAlive(side) {
    const a = this.arenaFor(side, 'human');
    let n = 0;
    if (a) for (const p of a.players.values()) if (!p.zclass && !p.spectating && p.playerstate === 'live') n++;
    return n + this.finaleAlive(side);
  }
  finaleAlive(side) {
    const F = this.finale && this.finale.arena;
    let n = 0;
    if (F) for (const p of F.players.values()) if (!p.spectating && p.playerstate === 'live' && p.person && p.person.zeSide === side) n++;
    return n;
  }
  // the live humans of a side at the end (the ze_survivor_wins stat): its own arena's and the finale's
  zeSurvivors(side) {
    const out = [];
    const a = this.arenaFor(side, 'human');
    if (a) for (const p of a.players.values()) if (!p.zclass && !p.spectating && p.playerstate === 'live' && p.mo && !p.mo.removed) out.push(p);
    const F = this.finale && this.finale.arena;
    if (F) for (const p of F.players.values()) if (!p.spectating && p.playerstate === 'live' && p.mo && !p.mo.removed && p.person && p.person.zeSide === side) out.push(p);
    return out;
  }
  // tics left on the round's ZE clock (the shortest time limit of the two arenas, from the later fight start)
  zeTimeLeftTics() {
    let limit = Infinity, started = -Infinity;
    for (const a of this.arenas) {
      if (a.zeFinale || !a.ze) continue;
      limit = Math.min(limit, a.ze.timeLimitTics);
      started = Math.max(started, a.startTime + this.cfg.countdownTics);
    }
    return limit === Infinity ? 0 : limit - (this.time - started);
  }

  // ---------------------------------------------------------------- the escape finale (Round 4 contract, docs/STATUS.md)
  // The level record with finale: true is a third arena, built when the first side escapes: no horde, no stages (its
  // monsters are left out, its items kept). An escaping side's live humans move there with what they carry; once both
  // sides are in, T and CT fight (same side can't hurt each other) and a death there is final for the round. The last
  // side standing wins. No record (or a one-side round): an escape wins at once, as before.
  finaleLevel() { for (const L of this.levels) if (L.finale) return L; return null; }

  buildFinale(L) {
    const arena = new Arena(this.arenas.length, Object.assign({}, this.cfg.arena));
    arena.load(L);
    arena.modeKey = 'ze'; arena.mode = MODES.ze;
    arena.teamsActive = true; arena.coop = false; arena.friendlyFire = false;   // T vs CT; same side off
    arena.mapId = L.id; arena.mapTitle = L.title || L.id; arena.zeSide = 0; arena.zeFinale = true;
    // spawn at the deathmatch starts (type 11), then the player starts 1-4 when there are few of them
    if (arena.coopStarts && arena.dmstarts.length < 8) {
      for (const s of arena.coopStarts) if (!arena.dmstarts.some((q) => Math.abs(q.x - s.x) < 1 && Math.abs(q.y - s.y) < 1)) arena.dmstarts.push({ x: s.x, y: s.y, angle: s.angle });
    }
    arena.startTime = this.time; arena.countdown = 0;
    arena.index = this.arenas.length;
    this.arenas.push(arena);
    this.events.push({ type: 'arenaBuilt', arena });
    return arena;
  }

  // the arenas in list have just escaped: their live humans go to the finale; their own arenas are over
  toFinale(list) {
    const S = ZE_SIDE_NAME;
    let F = this.finale;
    if (!F) F = this.finale = { arena: this.buildFinale(this.finaleLevel()), sides: {}, first: 0, sameTic: false, fight: false };
    let last = 0;
    for (const a of list) {
      const side = a.zeSide;
      if (F.sides[side]) continue;
      const movers = a.ze.humans();
      F.sides[side] = { at: this.time, entered: new Map() };
      if (!F.first) F.first = side;
      else if (F.sides[F.first].at === this.time) F.sameTic = true;
      last = side;
      a.finished = true; a.finishedAt = a.time;
      a.result = { text: S[side] + ' ESCAPED', ze: true, winner: 0, why: 'escaped', timeout: false };
      for (const p of a.players.values()) p.frozenEnd = true;
      for (const p of movers) if (p.person) this.moveToFinale(p.person, p, F);
    }
    if (!last) return;
    const first = F.first, other = first === 2 ? 3 : 2;
    let text, short;
    if (F.sides[2] && F.sides[3]) {
      F.fight = true;
      const second = last === first ? other : last;   // (both on one tic: the other side tracked down the first)
      const prey = second === 2 ? 3 : 2;
      text = S[second] + 'S TRACKED DOWN THE REMAINING ' + S[prey] + 'S - FIGHT TO BE THE FINAL SURVIVORS';
      short = 'FINAL FIGHT!';
    } else {
      text = S[first] + "'S ESCAPED - BUT WILL THE " + S[other] + 'S BE HOT ON THEIR TRAIL?';
      short = S[first] + "'S ESCAPED!";
    }
    this.events.push({ type: 'zeFinale', text, short, fight: F.fight, side: last, arena: F.arena });
  }

  // a live human into the finale with their weapons, ammo, health and armour, at a start away from the other side
  moveToFinale(pe, old, F) {
    const A = old.arena || pe.arena, arena = F.arena;
    const keep = {
      health: old.health, armorpoints: old.armorpoints, armortype: old.armortype, backpack: old.backpack,
      weaponowned: old.weaponowned.slice(), ammo: old.ammo.slice(), maxammo: old.maxammo.slice(),
      readyweapon: old.pendingweapon !== WP_NOCHANGE && old.weaponowned[old.pendingweapon] ? old.pendingweapon : old.readyweapon,
    };
    if (A) A.removePlayer(pe.slot);
    const p = arena.addPlayer(pe.slot, pe.name, pe.zeSide === 3 ? 1 : 0, this.colorFor(arena));
    p.person = pe; p.isBot = pe.bot; p.respawnGate = old.respawnGate;
    p.frags = old.frags; p.deaths = old.deaths;
    pe.arena = arena; pe.player = p; pe.status = 'playing'; pe.spec = null; pe.zeRole = 'human';
    const spot = arena.pickSpawnSpot(p);
    arena.spawnPlayer(p, { x: spot.x, y: spot.y, angle: spot.angle });
    arena.run(() => {
      p.health = Math.max(1, keep.health); p.mo.health = p.health;
      p.armorpoints = keep.armorpoints; p.armortype = keep.armortype; p.backpack = keep.backpack;
      for (let w = 0; w < NUMWEAPONS; w++) p.weaponowned[w] = !!keep.weaponowned[w];
      p.ammo = keep.ammo; p.maxammo = keep.maxammo;
      p.readyweapon = p.weaponowned[keep.readyweapon] ? keep.readyweapon : WP_PISTOL;
      p.pendingweapon = WP_NOCHANGE;
      setupPsprites(p);
    });
    F.sides[pe.zeSide].entered.set(pe.slot, pe);
    this.events.push({ type: 'zeFinaleJoin', person: pe, arena });
    return p;
  }

  // per tic in the finale: a death there is final (after the kill delay the player watches; no zombie, no respawn)
  finaleRules(a) {
    if (a.finished) return;
    let outs = null;
    for (const p of a.players.values()) {
      if (p.spectating || p.playerstate !== 'dead') continue;
      if (!p.zeFinaleDeath) { p.zeFinaleDeath = true; p.zeFinaleOutAt = this.time + this.zcfg.killDelayTics; }
      else if (this.time >= p.zeFinaleOutAt && p.person) (outs || (outs = [])).push(p.person);
    }
    if (outs) for (const pe of outs) this.finaleOut(pe);
  }

  finaleOut(pe) {
    const a = pe.arena, p = pe.player;
    if (!a || !p) return;
    a.makeSpectator(p);   // the corpse stays where it fell
    a.players.delete(pe.slot);
    pe.zeFinaleOut = this.roundNumber;
    this.seen.add(this.seenKey(pe));
    pe.arena = null; pe.player = null; pe.status = 'none';
    this.spectate(pe, a);
    this.events.push({ type: 'zeFinaleOut', person: pe, arena: a });
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
        if (p.isBot) { if (a.zeFinale) botThink(a, p); else zeBotThink(a, p); }
        if (p.frozen || a.finished) { p.cmd.forwardmove = 0; p.cmd.sidemove = 0; p.cmd.buttons = 0; }
      }
      a.tic();
      if ((a.leveltime & 31) === 0) a.rescueOutside();
      if (a.zeFinale) this.finaleRules(a); else this.zeArenaRules(a);
    }
    this.checkAfk();
    this.checkZe(remainingSeconds);
    this.checkAllEnds();
  }

  // a dead zombie player's wait: the sidecar's (or the config's) respawn time, longer while zombie players outnumber
  // the arena's live humans (zRespawnCatchup x the ratio over 1, at most zRespawnMax times): the last few humans get room
  // to breathe instead of being buried by every teammate they lost. Worked out once per tic per arena.
  zombieRespawnTics(a) {
    if (a.zRespawnAt === a.leveltime) return a.zRespawnNow;
    const z = this.zcfg;
    let zp = 0, h = 0;
    for (const p of a.players.values()) { if (p.spectating) continue; if (p.zclass) zp++; else if (p.playerstate === 'live') h++; }
    const over = Math.max(0, zp / Math.max(1, h) - 1);
    a.zRespawnAt = a.leveltime;
    a.zRespawnNow = Math.round(a.ze.respawnTics * Math.min(z.zRespawnMax, 1 + z.zRespawnCatchup * over));
    return a.zRespawnNow;
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
      } else if ((p.playerstate === 'dead' || !p.mo) && a.countdown <= 0 && p.respawnGate !== false && a.leveltime - p.deathTime >= this.zombieRespawnTics(a)) {
        a.run(() => this.spawnZombie(a, p));
      }
    }
    if (swaps) for (const pe of swaps) if (!this.zeResult) this.toZombie(pe);
    a.run(() => a.ze.tic());
  }

  checkZe(remainingSeconds) {
    if (this.pending.length || this.zeResult || !this.arenas.length) return;
    const main = this.arenas.filter((a) => !a.zeFinale);
    if (main.some((a) => a.countdown > 0)) return;
    const win = this.zcfg.drawWindowTics;
    // escape: with a finale level (and both sides playing) the side's humans go to the finale; without one, a side that
    // got a human out wins at once (both on one tic: a draw)
    const out = main.filter((a) => !a.finished && a.ze.escaped > 0);
    if (out.length) {
      if (this.solo || !this.finaleLevel()) { this.finishZe(out.length > 1 ? 0 : out[0].zeSide, 'escape'); return; }
      this.toFinale(out);
    }
    // both sides in the finale: the last side standing there wins (both gone on one tic: a draw)
    const F = this.finale;
    if (F && F.sides[2] && F.sides[3]) {
      const n2 = this.finaleAlive(2), n3 = this.finaleAlive(3);
      if (!n2 || !n3) { this.finishZe(n2 ? 2 : n3 ? 3 : 0, 'finale'); return; }
    }
    // the escape hold ended with nobody in the zone: that side failed (its humans are overrun)
    for (const a of main) if (!a.finished && a.ze.stages.some((s) => s.d.escape && s.state === 'done') && !a.ze.escaped && this.wipedAt[a.zeSide] === undefined) this.wipedAt[a.zeSide] = this.time;
    for (const a of main) if (this.wipedAt[a.zeSide] === undefined && this.humansAlive(a.zeSide) === 0) this.wipedAt[a.zeSide] = this.time;
    const w2 = this.wipedAt[2], w3 = this.wipedAt[3];
    if (this.solo) {
      const side = main[0].zeSide;
      if (this.wipedAt[side] !== undefined) { this.finishZe(side === 2 ? 3 : 2, 'wipe'); return; }
    } else if (w2 !== undefined || w3 !== undefined) {
      if (w2 !== undefined && w3 !== undefined && Math.abs(w2 - w3) <= win) { this.finishZe(0, 'wipe'); return; }
      const first = w2 !== undefined && (w3 === undefined || w2 <= w3) ? 2 : 3;
      if (this.time >= this.wipedAt[first] + win) { this.finishZe(first === 2 ? 3 : 2, 'wipe'); return; }
    }
    if (this.zeTimeLeftTics() <= 0 || (remainingSeconds !== undefined && remainingSeconds <= 0)) this.timeUp();
  }

  timeUp() {
    if (this.zeResult || !this.arenas.length) return;
    const h2 = this.humansAlive(2), h3 = this.humansAlive(3);
    let w = h2 > h3 ? 2 : h3 > h2 ? 3 : 0;
    // during the finale a tie goes to the side that escaped first
    if (!w && this.finale && this.finale.first && !this.finale.sameTic) w = this.finale.first;
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
    else if (why === 'finale') text = winner ? S[winner] + ' WIN THE FINAL FIGHT' : 'DRAW - NO SURVIVORS';
    else text = winner ? 'TIME UP - ' + S[winner] + ' WIN' : 'TIME UP - DRAW';
    this.zeResult = { winner, why, text };
    for (const a of this.arenas) {
      if (a.finished) continue;
      a.finished = true; a.finishedAt = a.time;
      a.result = { text, ze: true, winner, why, timeout: why === 'time' };
      for (const p of a.players.values()) p.frozenEnd = true;
      this.events.push({ type: 'arenaEnd', arena: a, result: a.result });
    }
    // the winning side's live humans (the ze_survivor_wins stat), and every human of it who reached the finale, alive or
    // not, and is still here (ze_finale_wins)
    const survivors = winner ? this.zeSurvivors(winner) : [];
    const finaleWinners = [];
    const fs = winner && this.finale ? this.finale.sides[winner] : null;
    if (fs) for (const pe of fs.entered.values()) if (this.people.get(pe.slot) === pe) finaleWinners.push({ slot: pe.slot, isBot: pe.bot, name: pe.name });
    this.events.push({ type: 'zeEnd', winner, why, text, survivors, finaleWinners });
  }
}
