// ===================================================================================================================
// IRONFRAME core: objective modes added to IF_Game.
//   kh  King of the Hill: one hill (an arena point) at a time, captured like a Conquest point; the owning team scores 1 a
//       second while at least one of its mechs stands on it and it is not contested (an empty hill stays theirs but scores
//       nothing); the hill moves to the next point every cfg.kh.rotate seconds (a warning IF_OBJ.khWarn s before);
//       first to cfg.kh.target or the most at time-out.
//   ctf Capture the Flag: each team's flag sits at its base (ARENA.flags {t:[x,y,z], ct:[x,y,z]} when the map places
//       them, else IF_objFlagBase: the team's drop centroid a quarter of the way toward the arena centre); an enemy
//       touching it carries it (boost drain x carrierDrain); the carrier dying drops it where it falls (a flag dropped
//       over the void goes home); a teammate touching a dropped flag returns it, or it returns by itself after
//       cfg.ctf.returnTime; a carrier reaching their own flag while it is home scores. First to cfg.ctf.captures.
// State the HUD and the world visuals read (additive since 10 Nov 2026, the older fields are unchanged):
//   points[i]  {id, pos, radius, owner, value, progress, capTeam, contested} + nT / nCT (mechs of each team inside, set by
//              captureStep in 80_game.js) + scoring (kh: the owner is on the hill and scores this second) + idx (kh: index into
//              arena.points)
//   match      hill, hillT + hillLeft (s until the hill moves), hillNext (index into allPoints, -1 with one point)
//              bleed {2, 3}: Conquest tickets/s each team is losing (majority rule, modeStep in 80_game.js)
//   capture event {t:'capture', point (index into arena.points), id, team, slot}
//   flags[t]   {team, home, pos, state 'home'|'carried'|'dropped', carrier, returnT, fx} + returnMax (cfg.ctf.returnTime),
//              carrierTeam (the team that can take it)
// Markers: this.objFx (and this.hillFx, flags[t].fx) are plain marker records {alive, kind 'ring', pos, radius,
// objective: true}. Until 10 Nov 2026 they were pushed into game.effects and drawn as the generic lock ring; that pool
// grew by one or two entries a round, the 24-ring render cap could hide them and the ring stood upright at a quarter of
// the zone size. The adapter now draws the objectives itself (src/cs2/45_features.js objTick).
// Events: {t:'hill', point, moved}, {t:'hill', point, soon:true, next}, {t:'flag', team, action:'take'|'drop'|'return'|
// 'capture', slot}.
// AI: objectiveGoal (where to go) and objPull (the drift toward the objective while fighting, called by 50_ai.js).
// ===================================================================================================================
const IF_OBJ = {
  khWarn: 15,                  // s before a hill move: the warning line / event
  flagInset: 0.25,             // flag base without map flags: the drop centroid moved this share toward the arena centre
  // AI drift toward the objective while engaged (added to the fight steering, whose radial + strafe is about 1.3 long)
  pull: { kh: 2.2, cq: 1.5, cqOwned: 0.5, ctf: 1.6, carrier: 3.0, nearFrac: 0.45, ctfNear: 120 },
};

/** the default flag base of a team (no ARENA.flags): the drop centroid moved IF_OBJ.flagInset toward the arena centre,
 *  on walkable ground; falls back to the centroid, then the first drop point */
function IF_objFlagBase(game, team) {
  const d = ((team === 2 ? game.arena.drops.t : game.arena.drops.ct) || []);
  if (!d.length) return IF_v3(0, 0, 0);
  let cx = 0, cy = 0; for (const p of d) { cx += p[0]; cy += p[1]; } cx /= d.length; cy /= d.length;
  const b = game.arena.bounds, mx = (b.min[0] + b.max[0]) / 2, my = (b.min[1] + b.max[1]) / 2;
  const tries = [[cx + (mx - cx) * IF_OBJ.flagInset, cy + (my - cy) * IF_OBJ.flagInset], [cx, cy], [d[0][0], d[0][1]]];
  for (const [x, y] of tries) {
    const h = game.nav.height(x, y);
    if (game.nav.walk(x, y) && Number.isFinite(h) && h > b.min[2] + 1) return IF_v3(x, y, h);
  }
  return IF_v3(d[0][0], d[0][1], game.nav.height(d[0][0], d[0][1]));
}

/** @type {any} */ (IF_Game.prototype).objectivesInit = function (mode) {
  const M = this.match;
  M.hill = -1; M.hillT = 0; M.hillLeft = 0; M.hillNext = -1; M.khWarned = false; M.flags = null;
  for (const e of this.objFx || []) e.alive = false;
  this.objFx = []; this.hillFx = null;
  // a marker record (not in game.effects: the adapter draws objectives itself)
  const ring = (pos, radius) => { const e = { alive: true, kind: 'ring', pos: IF_v3(pos.x, pos.y, pos.z + 20), radius, slot: -1, life: Infinity, objective: true }; this.objFx.push(e); return e; };
  for (const p of M.points || []) { p.nT = 0; p.nCT = 0; p.scoring = false; }
  if (mode === 'kh') {
    const pts = (this.arena.points || []);
    M.allPoints = pts.map((p, i) => ({ id: p.id || String.fromCharCode(65 + i), pos: IF_v3(p.pos[0], p.pos[1], p.pos[2]), radius: p.radius || 700, idx: i,
      owner: 0, value: 0, progress: 0, capTeam: 0, contested: false, nT: 0, nCT: 0, scoring: false }));
    M.hill = M.allPoints.length > 1 ? 1 : 0;   // start on the centre point
    M.points = M.allPoints.length ? [M.allPoints[M.hill]] : [];
    M.hillT = 0; M.hillLeft = this.cfg.kh.rotate; M.hillNext = M.allPoints.length > 1 ? (M.hill + 1) % M.allPoints.length : -1;
    if (M.points.length) this.hillFx = ring(M.points[0].pos, M.points[0].radius);
  } else if (mode === 'ctf') {
    const F = this.arena.flags || {};
    const base = (team) => { const f = team === 2 ? F.t : F.ct; return f ? IF_v3(f[0], f[1], f[2]) : IF_objFlagBase(this, team); };
    M.flags = {};
    for (const team of [2, 3]) {
      const home = base(team);
      M.flags[team] = { team, home, pos: IF_v3(home.x, home.y, home.z), state: 'home', carrier: -1, returnT: 0, returnMax: this.cfg.ctf.returnTime,
        carrierTeam: team === 2 ? 3 : 2, fx: ring(home, 260) };
    }
    M.scores = { 2: 0, 3: 0 };
  }
};

/** @type {any} */ (IF_Game.prototype).khStep = function (dt) {
  const M = this.match, C = this.cfg.kh;
  if (!M.points.length) return;
  this.cqAcc += dt;
  if (this.cqAcc >= 0.125) { this.captureStep(this.cqAcc); this.cqAcc = 0; }
  const p = M.points[0];
  // the owner scores only while one of its mechs is on the hill (an empty hill kept its owner and scored for it until 10 Nov 2026)
  const here = p.owner === 2 ? (p.nT || 0) : p.owner === 3 ? (p.nCT || 0) : 0;
  p.scoring = (p.owner === 2 || p.owner === 3) && !p.contested && here > 0;
  if (p.scoring) { M.khAcc = (M.khAcc || 0) + dt; while (M.khAcc >= 1) { M.khAcc -= 1; M.scores[p.owner]++; } }
  else M.khAcc = 0;
  M.hillT += dt;
  M.hillLeft = Math.max(0, C.rotate - M.hillT);
  if (M.allPoints.length > 1 && !M.khWarned && M.hillLeft <= IF_OBJ.khWarn) {
    M.khWarned = true;
    const n = M.allPoints[M.hillNext];
    this.emit({ t: 'hill', point: M.hill, soon: true, next: M.hillNext });
    this.emit({ t: 'say', slot: -1, text: 'THE HILL MOVES TO ' + n.id + ' IN ' + Math.round(M.hillLeft) + ' S', secs: 4 });
  }
  if (M.allPoints.length > 1 && M.hillT >= C.rotate) {
    M.hillT = 0; M.hillLeft = C.rotate; M.khWarned = false; M.khAcc = 0; p.scoring = false;
    M.hill = (M.hill + 1) % M.allPoints.length; M.hillNext = (M.hill + 1) % M.allPoints.length;
    const n = M.allPoints[M.hill]; n.owner = 0; n.value = 0; n.progress = 0; n.capTeam = 0; n.contested = false; n.nT = 0; n.nCT = 0; n.scoring = false;
    M.points = [n];
    if (this.hillFx) { this.hillFx.pos.x = n.pos.x; this.hillFx.pos.y = n.pos.y; this.hillFx.pos.z = n.pos.z + 20; this.hillFx.radius = n.radius; }
    this.emit({ t: 'hill', point: M.hill, moved: true });
    this.emit({ t: 'say', slot: -1, text: 'THE HILL HAS MOVED TO ' + n.id, secs: 4 });
  }
  if (M.scores[2] >= C.target || M.scores[3] >= C.target) this.endRound();
};

/** @type {any} */ (IF_Game.prototype).ctfStep = function (dt) {
  const M = this.match, C = this.cfg.ctf;
  if (!M.flags) return;
  for (const team of [2, 3]) {
    const f = M.flags[team], enemy = team === 2 ? 3 : 2;
    if (f.state === 'carried') {
      const c = this.mechs.get(f.carrier);
      if (!c || !c.alive) { /** @type {any} */ (this).ctfDrop(f, c ? c.pos : f.pos); continue; }
      f.pos.x = c.pos.x; f.pos.y = c.pos.y; f.pos.z = c.pos.z + c.height;
      const own = M.flags[enemy];   // the carrier's own team flag
      if (own.state === 'home' && Math.hypot(c.pos.x - own.home.x, c.pos.y - own.home.y) <= C.capture && Math.abs(c.pos.z - own.home.z) < 600) {
        M.scores[enemy]++; c.sum.captures++; c.carrier = false;
        this.emit({ t: 'flag', team, action: 'capture', slot: c.slot });
        this.emit({ t: 'say', slot: -1, text: (enemy === 2 ? 'T' : 'CT') + ' CAPTURED THE FLAG (' + M.scores[2] + ' - ' + M.scores[3] + ')', secs: 5 });
        /** @type {any} */ (this).ctfHome(f);
        if (M.scores[enemy] >= C.captures) return this.endRound();
      }
    } else {
      if (f.state === 'dropped') { f.returnT -= dt; if (f.returnT <= 0) { /** @type {any} */ (this).ctfHome(f); this.emit({ t: 'flag', team, action: 'return', slot: -1 }); continue; } }
      for (const m of this.alive) {
        if (m.dropT > 0 || (m.team !== 2 && m.team !== 3)) continue;
        if (Math.hypot(m.pos.x - f.pos.x, m.pos.y - f.pos.y) > C.pickup || Math.abs(m.pos.z - f.pos.z) > 500) continue;
        if (m.team === enemy && !m.carrier) {
          f.state = 'carried'; f.carrier = m.slot; m.carrier = true;
          this.emit({ t: 'flag', team, action: 'take', slot: m.slot });
          this.emit({ t: 'say', slot: -1, text: (m.team === 2 ? 'T' : 'CT') + ' TOOK THE ' + (team === 2 ? 'T' : 'CT') + ' FLAG', secs: 4 });
          break;
        }
        if (m.team === team && f.state === 'dropped') { /** @type {any} */ (this).ctfHome(f); m.sum.flagReturns++; this.emit({ t: 'flag', team, action: 'return', slot: m.slot }); break; }
      }
    }
    if (f.fx) { f.fx.pos.x = f.pos.x; f.fx.pos.y = f.pos.y; f.fx.pos.z = f.state === 'carried' ? f.pos.z : f.pos.z + 20; f.fx.radius = f.state === 'carried' ? 140 : 260; }
  }
};
/** @type {any} */ (IF_Game.prototype).ctfDrop = function (f, pos) {
  const c = this.mechs.get(f.carrier); if (c) c.carrier = false;
  f.state = 'dropped'; f.carrier = -1; f.returnT = this.cfg.ctf.returnTime;
  const h = this.nav.height(pos.x, pos.y);
  // over the void (Orbital: the nav height there is the death height) the flag goes home. Until 10 Nov 2026 this compared the
  // ground with the carrier's height (ground < z - 2000), so a carrier shot down while boosting high returned the flag at once.
  if (!Number.isFinite(h) || h <= this.arena.bounds.min[2] + 1) { /** @type {any} */ (this).ctfHome(f); this.emit({ t: 'flag', team: f.team, action: 'return', slot: -1 }); return; }
  f.pos.x = pos.x; f.pos.y = pos.y; f.pos.z = h;
  this.emit({ t: 'flag', team: f.team, action: 'drop', slot: c ? c.slot : -1 });
};
/** @type {any} */ (IF_Game.prototype).ctfHome = function (f) {
  const c = this.mechs.get(f.carrier); if (c) c.carrier = false;
  f.state = 'home'; f.carrier = -1; f.returnT = 0; f.pos.x = f.home.x; f.pos.y = f.home.y; f.pos.z = f.home.z;
};
/** @type {any} */ (IF_Game.prototype).ctfOnDeath = function (v) {
  const M = this.match; if (!M.flags) return;
  for (const team of [2, 3]) { const f = M.flags[team]; if (f.state === 'carried' && f.carrier === v.slot) /** @type {any} */ (this).ctfDrop(f, v.pos); }
};
// AI goals: KOTH the hill; CTF carriers go home, others take the enemy flag, chase their own flag's carrier, or return it
/** @type {any} */ (IF_Game.prototype).objectiveGoal = function (m, out) {
  const M = this.match;
  if (M.mode === 'kh' && M.points.length) { IF_vcopy(out, M.points[0].pos); return true; }
  if (M.mode === 'ctf' && M.flags && (m.team === 2 || m.team === 3)) {
    const own = M.flags[m.team], enemy = M.flags[m.team === 2 ? 3 : 2];
    if (m.carrier) { IF_vcopy(out, own.home); return true; }
    if (own.state !== 'home' && (m.squad % 2 === 0)) { IF_vcopy(out, own.pos); return true; }   // half the squads defend / chase
    if (enemy.state !== 'carried' || enemy.carrier !== m.slot) { IF_vcopy(out, enemy.state === 'carried' ? own.home : enemy.pos); return true; }
  }
  return false;
};
// AI: the drift toward the objective while fighting (50_ai.js engage steering adds it). Until 10 Nov 2026 the drift was 0.6-0.9
// against a fight steering of about 1.3, so bots held their range band round the zone: 9 % of the mechs stood on a KOTH hill,
// 13 % on a Conquest point (Dunes, 16 bots). The pull stops inside nearFrac of the zone radius so a bot fights from the zone.
/** @type {any} */ (IF_Game.prototype).objPull = function (m, ai) {
  const M = this.match, gm = M.mode, P = IF_OBJ.pull;
  if (!ai.hasGoal || (gm !== 'cq' && gm !== 'kh' && gm !== 'ctf')) return null;
  const gx = ai.goal.x - m.pos.x, gy = ai.goal.y - m.pos.y, gd = Math.hypot(gx, gy);
  let near = P.ctfNear, w = m.carrier ? P.carrier : P.ctf;
  if (gm !== 'ctf') {
    let pt = null, bd = Infinity;
    for (const p of M.points) { const d = Math.hypot(p.pos.x - ai.goal.x, p.pos.y - ai.goal.y); if (d < bd) { bd = d; pt = p; } }
    if (!pt || bd > pt.radius) return null;          // the goal is not a zone (a crate, an enemy): no pull
    near = pt.radius * P.nearFrac;
    w = gm === 'kh' ? P.kh : (pt.owner === m.team && !pt.contested ? P.cqOwned : P.cq);
  }
  if (gd <= near) return null;
  const o = this._objPull || (this._objPull = { x: 0, y: 0 });
  o.x = gx / gd * w; o.y = gy / gd * w;
  return o;
};
