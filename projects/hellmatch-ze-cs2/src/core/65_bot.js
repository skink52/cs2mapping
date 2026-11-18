// ===================================================================================
// Part 6b: simple deathmatch bots (testing and filling small rounds)
// ===================================================================================

// ---------------------------------------------------------------- navigation: sector graph
const NAV_DOORS = new Set([1, 26, 27, 28, 31, 32, 33, 34, 117, 118]);
function buildNav(level) {
  if (level.nav) return level.nav;
  const nav = level.sectors.map(() => []);
  const passable = (a, b, l) => {
    if (NAV_DOORS.has(l.special) && b === l.backsector) return true;   // closed doors open on use
    if (b.floorheight - a.floorheight > MAXSTEP) return false;
    return Math.min(a.ceilingheight, b.ceilingheight) - Math.max(a.floorheight, b.floorheight) >= 56;
  };
  const LIFT_LINES = new Set([62, 123, 21, 122, 88, 120, 10, 121]);
  for (const l of level.lines) {
    // teleporters: walking over the line moves you to the destination sector
    if ((l.special === 97 || l.special === 39) && l.frontsector) {
      for (const t of level.things) {
        if (t[3] !== 14) continue;
        const ds = level.sectorAt(t[0], t[1]);
        if (ds.tag === l.tag) { nav[l.frontsector.id].push({ to: ds.id, line: l, len: 64, teleport: true }); break; }
      }
    }
    // lifts: a lift that is up can be reached from below by triggering it
    if (LIFT_LINES.has(l.special) && l.tag) {
      for (const lift of level.sectors) {
        if (lift.tag !== l.tag) continue;
        for (const l2 of lift.lines) {
          const o = l2.frontsector === lift ? l2.backsector : l2.frontsector;
          if (!o || o === lift || o.floorheight >= lift.floorheight) continue;
          if (Math.hypot(l2.dx, l2.dy) < 34) continue;
          nav[o.id].push({ to: lift.id, line: l2, len: 64, lift: true, trigger: l });
        }
      }
    }
    if (!l.backsector || !l.frontsector || l.backsector === l.frontsector) continue;
    if (l.flags & ML_BLOCKING) continue;
    const len = Math.hypot(l.dx, l.dy);
    if (len < 34) continue;
    const a = l.frontsector, b = l.backsector;
    const e = { line: l, len };
    if (passable(a, b, l)) nav[a.id].push(Object.assign({ to: b.id }, e));
    if (passable(b, a, l)) nav[b.id].push(Object.assign({ to: a.id }, e));
  }
  level.nav = nav;
  return nav;
}

function portalPoint(l, x, y) {
  // closest point on the portal line to (x, y), kept 20 units from its ends
  const len = Math.hypot(l.dx, l.dy);
  let t = ((x - l.x1) * l.dx + (y - l.y1) * l.dy) / (len * len);
  const m = Math.min(0.5, 20 / len);
  t = Math.max(m, Math.min(1 - m, t));
  return { x: l.x1 + l.dx * t, y: l.y1 + l.dy * t };
}

// first portal on the shortest sector path from (fx,fy) to (tx,ty); null if none / same sector
function navNext(level, fx, fy, tx, ty) {
  const nav = buildNav(level);
  const from = level.sectorAt(fx, fy).id, to = level.sectorAt(tx, ty).id;
  if (from === to) return null;
  // the sector graph doesn't change during a round, so each (from, to) answer is worked out once
  const cache = level.navCache || (level.navCache = new Map());
  const key = from * 65536 + to;
  if (cache.has(key)) return cache.get(key);
  const res = navSearch(level, nav, from, to, fx, fy);
  cache.set(key, res);
  return res;
}

function navSearch(level, nav, from, to, fx, fy) {
  const n = level.sectors.length;
  const dist = new Float64Array(n).fill(Infinity), px = new Float64Array(n), py = new Float64Array(n);
  const first = new Array(n).fill(null);
  const done = new Uint8Array(n);
  dist[from] = 0; px[from] = fx; py[from] = fy;
  for (let iter = 0; iter < n; iter++) {
    let u = -1, best = Infinity;
    for (let i = 0; i < n; i++) if (!done[i] && dist[i] < best) { best = dist[i]; u = i; }
    if (u < 0) break;
    if (u === to) break;
    done[u] = 1;
    for (const e of nav[u]) {
      if (done[e.to]) continue;
      const pp = portalPoint(e.line, px[u], py[u]);
      const d = dist[u] + Math.hypot(pp.x - px[u], pp.y - py[u]);
      if (d < dist[e.to]) { dist[e.to] = d; px[e.to] = pp.x; py[e.to] = pp.y; first[e.to] = u === from ? e : first[u]; }
    }
  }
  return first[to];
}

function botWeaponFor(p, dist) {
  const has = (w, am, n) => p.weaponowned[w] && (am === AM_NOAMMO || p.ammo[am] >= n);
  if (dist < 300 && has(WP_SUPERSHOTGUN, AM_SHELL, 2)) return WP_SUPERSHOTGUN;
  if (dist > 200 && has(WP_MISSILE, AM_MISL, 1)) return WP_MISSILE;
  if (has(WP_PLASMA, AM_CELL, 1)) return WP_PLASMA;
  if (has(WP_CHAINGUN, AM_CLIP, 1)) return WP_CHAINGUN;
  if (has(WP_SUPERSHOTGUN, AM_SHELL, 2)) return WP_SUPERSHOTGUN;
  if (has(WP_SHOTGUN, AM_SHELL, 1)) return WP_SHOTGUN;
  if (dist < 80 && has(WP_CHAINSAW, AM_NOAMMO, 0)) return WP_CHAINSAW;
  if (has(WP_PISTOL, AM_CLIP, 1)) return WP_PISTOL;
  return WP_FIST;
}

const botCands = [];
function byDistThenOrder(a, b) { return a.d - b.d || a.n - b.n; }

function botThink(arena, p) {
  const cmd = p.cmd;
  const mo = p.mo;
  cmd.forwardmove = 0; cmd.sidemove = 0; cmd.buttons = 0;
  if (!mo || mo.removed || p.spectating) return;
  if (p.playerstate === 'dead') { if ((arena.leveltime & 15) === 0) cmd.buttons = BT_USE; return; }
  const b = p.bot || (p.bot = { target: null, retarget: 0, lastx: mo.x, lasty: mo.y, stuck: 0, strafe: 1, wanderAngle: mo.angle, goal: null });
  if (b.skill === undefined) b.skill = Math.max(0, Math.min(1, (arena.cfg.botSkill || 0.35) + ((p.slot * 37) % 7 - 3) * 0.04));
  const skill = b.skill;
  if (--b.retarget <= 0) {
    b.retarget = 6 + Math.round((1 - skill) * 8);
    b.aimErr = (P_Random() - 128) / 128 * (1 - skill) * 28;   // a fresh aiming error each time, held until the next
    /** @type {any} */ let best = null;
    arena.run(() => {
      // the nearest visible enemy (players first on equal distance, as the scan order had it): candidates are
      // sight-checked nearest first and the first one seen wins, instead of a sight line to everyone in range
      const cands = botCands; cands.length = 0;
      if (!arena.coop) {
        for (const q of arena.players.values()) {
          if (q === p || q.spectating || q.playerstate !== 'live' || !q.mo) continue;
          if (arena.teamsActive && q.team === p.team) continue;
          const d = Math.hypot(q.mo.x - mo.x, q.mo.y - mo.y);
          if (d < 2500) cands.push({ d, mo: q.mo, q, n: cands.length });
        }
      }
      // monsters: in a deathmatch they only matter when close (no frag for them); in Boss Battle they are the game
      if (arena.monsterCount) {
        for (const m of arena.mobjs) {
          if (m.info.kind !== 'monster' || m.health <= 0) continue;
          let d = Math.hypot(m.x - mo.x, m.y - mo.y);
          if (!arena.coop) { if (d > 700 && m.target !== mo) continue; d *= 1.5; }
          if (d < 2500) cands.push({ d, mo: m, q: null, n: cands.length });
        }
      }
      if (cands.length > 1) cands.sort(byDistThenOrder);
      for (let i = 0; i < cands.length; i++) if (checkSight(mo, cands[i].mo)) { best = { mo: cands[i].mo, q: cands[i].q }; break; }
      cands.length = 0;
      if (!best && (!b.goal || b.goal.removed || (arena.leveltime & 63) === 0)) {
        let gi = null;
        for (const m of arena.mobjs) {
          if (!(m.flags & MF_SPECIAL)) continue;
          const d = Math.hypot(m.x - mo.x, m.y - mo.y);
          if (d < 900 && Math.abs(m.z - mo.z) < 40) cands.push({ d, mo: m, q: null, n: cands.length });
        }
        if (cands.length > 1) cands.sort(byDistThenOrder);
        for (let i = 0; i < cands.length; i++) if (checkSight(mo, cands[i].mo)) { gi = cands[i].mo; break; }
        cands.length = 0;
        if (b.goal && b.goal.isStart && Math.hypot(b.goal.x - mo.x, b.goal.y - mo.y) > 64) gi = gi || b.goal;
        if (!gi) {
          // no item in sight: head for a visible deathmatch start, which spreads bots around the map
          const starts = arena.dmstarts.filter((st) => Math.hypot(st.x - mo.x, st.y - mo.y) > 200);
          for (let k = 0; k < 4 && starts.length; k++) {
            const st = starts[(P_Random() * starts.length) >> 8];
            const probe = { x: st.x, y: st.y, z: mo.z, height: 56, sector: arena.level.sectorAt(st.x, st.y) };
            if (checkSight(mo, probe)) { gi = { x: st.x, y: st.y, z: mo.z, removed: false, isStart: true }; break; }
          }
        }
        b.goal = gi;
      }
    });
    if (!best || !b.target || best.mo !== b.target.mo) b.reactUntil = arena.leveltime + Math.round((1 - skill) * 30);   // reaction time on a new target
    b.target = best;
  }
  let desired = b.wanderAngle;
  const t = b.target;
  const targetAlive = t && t.mo && !t.mo.removed && t.mo.health > 0 && (!t.q || t.q.playerstate === 'live');
  if (targetAlive) {
    const dist = Math.hypot(t.mo.x - mo.x, t.mo.y - mo.y);
    desired = pointToAngle(mo.x, mo.y, t.mo.x, t.mo.y) + (b.aimErr || 0);
    const w = botWeaponFor(p, dist);
    if (w !== p.readyweapon && p.pendingweapon === WP_NOCHANGE) p.wantWeapon = w;
    const diff = Math.abs(angleDiff(mo.angle, desired));
    // fire in bursts: low-skill bots hold the trigger less often and not before their reaction time is up
    if (diff < 12 && arena.leveltime >= (b.reactUntil || 0) && P_Random() < 70 + skill * 185) cmd.buttons |= BT_ATTACK;
    cmd.forwardmove = dist > 380 ? 50 : dist < 160 ? -40 : 0;
    if ((arena.leveltime % 40) === 0) b.strafe = P_Random() & 1 ? 1 : -1;
    cmd.sidemove = 40 * b.strafe;
  } else {
    // hunt: path towards the nearest enemy we can actually reach (a route through the sector graph, or in plain
    // sight in the same sector); otherwise towards an item/start. Walking straight at someone behind a wall gets
    // two bots stuck either side of it.
    if ((arena.leveltime % 17) === (p.slot % 17) && !(b.unstickUntil > arena.leveltime)) {
      b.avoid = b.avoid || new Map();
      const enemies = [];
      if (!arena.coop) {
        for (const q of arena.players.values()) {
          if (q === p || q.spectating || q.playerstate !== 'live' || !q.mo) continue;
          if (arena.teamsActive && q.team === p.team) continue;
          if ((b.avoid.get(q.slot) || 0) > arena.leveltime) continue;
          enemies.push({ q, d: Math.hypot(q.mo.x - mo.x, q.mo.y - mo.y) });
        }
      } else {
        // Boss Battle: hunt the nearest monsters
        for (const m of arena.mobjs) {
          if (m.info.kind !== 'monster' || m.health <= 0) continue;
          if ((b.avoid.get('m' + m.id) || 0) > arena.leveltime) continue;
          enemies.push({ q: { mo: m, slot: 'm' + m.id }, d: Math.hypot(m.x - mo.x, m.y - mo.y) });
        }
      }
      enemies.sort((x, y) => x.d - y.d);
      const route = (tx, ty, tmo) => arena.run(() => {
        const same = arena.level.sectorAt(tx, ty) === arena.level.sectorAt(mo.x, mo.y);
        if (same) return checkSight(mo, tmo || { x: tx, y: ty, z: mo.z, height: 56 }) ? { portal: null } : null;
        const e = navNext(arena.level, mo.x, mo.y, tx, ty);
        return e ? { portal: e } : null;
      });
      let tgt = null, r = null;
      const wantHunt = enemies.length && (!b.goal || b.goal.isStart || P_Random() < 96 || !arena.mode || !arena.mode.respawn);
      if (wantHunt) {
        for (const { q } of enemies.slice(0, 3)) {
          r = route(q.mo.x, q.mo.y, q.mo);
          if (r) { tgt = q.mo; break; }
          b.avoid.set(q.slot, arena.leveltime + 3 * TICRATE);
        }
      }
      if (!tgt && b.goal && !b.goal.removed) { r = route(b.goal.x, b.goal.y, b.goal.isStart ? null : b.goal); if (r) tgt = b.goal; else b.goal = null; }
      if (!tgt) {
        // nothing to chase or pick up: roam to a reachable deathmatch start elsewhere on the map
        const starts = arena.dmstarts.filter((st) => Math.hypot(st.x - mo.x, st.y - mo.y) > 256);
        for (let k = 0; k < 4 && starts.length; k++) {
          const st = starts[(P_Random() * starts.length) >> 8];
          r = route(st.x, st.y, null);
          if (r) { b.goal = tgt = { x: st.x, y: st.y, z: mo.z, removed: false, isStart: true }; break; }
        }
      }
      b.portal = r ? r.portal : null;
      b.huntPos = tgt ? { x: tgt.x, y: tgt.y } : null;
      b.huntSlot = tgt && tgt.player ? tgt.player.slot : null;
    }
    cmd.forwardmove = 50;
    if (b.portal) {
      const pp = portalPoint(b.portal.line, mo.x, mo.y);
      // aim a little past the portal so the bot walks through it
      const ang = pointToAngle(mo.x, mo.y, pp.x, pp.y);
      desired = ang;
      const near = Math.hypot(pp.x - mo.x, pp.y - mo.y);
      if (b.portal.lift && b.portal.line.frontsector && Math.abs(b.portal.line.frontsector.floorheight - b.portal.line.backsector.floorheight) > MAXSTEP) {
        // the lift is up: walk to its trigger and press use, then wait for it
        const tl = b.portal.trigger;
        const tp = portalPoint(tl, mo.x, mo.y);
        desired = pointToAngle(mo.x, mo.y, tp.x, tp.y);
        if (Math.hypot(tp.x - mo.x, tp.y - mo.y) < 56) { cmd.buttons |= BT_USE; cmd.forwardmove = 0; }
      } else if (near < 40) {
        desired = b.huntPos ? pointToAngle(mo.x, mo.y, b.huntPos.x, b.huntPos.y) : ang;
        if (NAV_DOORS.has(b.portal.line.special) && (arena.leveltime & 15) === 0) cmd.buttons |= BT_USE;
      }
    } else if (b.huntPos) desired = pointToAngle(mo.x, mo.y, b.huntPos.x, b.huntPos.y);
    else if (b.goal && !b.goal.removed) desired = pointToAngle(mo.x, mo.y, b.goal.x, b.goal.y);

    const moved = Math.hypot(mo.x - b.lastx, mo.y - b.lasty);
    if ((arena.leveltime % 10) === 0) {
      if (moved < 20) {
        b.stuck++;
        b.wanderAngle = normAngle(mo.angle + 90 + (P_Random() & 127) * (P_Random() & 1 ? 1 : -1));
        // blocked by someone right next to us (usually a teammate in a corridor): step away from them
        let close = null, cd = 80;
        for (const q of arena.players.values()) {
          if (q === p || !q.mo || q.playerstate !== 'live' || q.spectating) continue;
          const d = Math.hypot(q.mo.x - mo.x, q.mo.y - mo.y);
          if (d < cd) { cd = d; close = q; }
        }
        if (close) b.wanderAngle = normAngle(pointToAngle(close.mo.x, close.mo.y, mo.x, mo.y) + ((P_Random() & 63) - 32));
        b.goal = null;
        // blocked for about a second: turn away for 2 s and leave whoever we were chasing alone for a while
        if (b.stuck >= 3) {
          b.unstickUntil = arena.leveltime + 2 * TICRATE;
          if (b.huntSlot !== null && b.huntSlot !== undefined) (b.avoid || (b.avoid = new Map())).set(b.huntSlot, arena.leveltime + 5 * TICRATE);
          b.huntPos = null; b.portal = null; b.stuck = 0;
        }
      } else b.stuck = 0;
      b.lastx = mo.x; b.lasty = mo.y;
      if (b.stuck > 0) { b.portal = null; desired = b.wanderAngle; }
    }
    if (b.unstickUntil > arena.leveltime) desired = b.wanderAngle;
  }
  const turn = angleDiff(mo.angle, desired);
  const maxTurn = 10 + 20 * skill;
  cmd.angle = normAngle(mo.angle + Math.max(-maxTurn, Math.min(maxTurn, turn)));
  if (!targetAlive && !b.goal) b.wanderAngle = normAngle(b.wanderAngle);
}
