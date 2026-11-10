// ===================================================================================================================
// IRONFRAME core, part 5: AI pilots (DESIGN.md section 6, "AI"). Bots fill the same input struct humans do (Dogfight
// pattern): target choice by cost (distance + turn + hysteresis + who hurt me), a human aim model (below), burst
// discipline, missile dodges by time-to-impact (quick boost across the missile), decoys on hard locks, a boost reserve,
// flow-field pathing to the mode objective, cover when staggered or under 40 % AP, weapon choice by range band, squads
// that share a target and a point, stuck recovery. Three tiers (cfg.ai.tiers). Fill: IF_Ai.fillCheck keeps the teams
// topped up with NPC mechs (slots 64+) below the population floor.
// Aim model (Nov 2026 playtest: "AI seem to have very good aim"; DESIGN.md "AI", tier keys in cfg.ai.tiers):
//  - reaction: on a target switch and when a target comes back into sight after `C.aimLostT` s the bot holds its aim and
//    its fire for `react` s (x0.8 on a reacquire), then turns with a first-order lag (`gain` per s, capped at 300/420 deg/s);
//  - perception: the target's velocity is a low-passed estimate (`velLag` s), so a quick boost or a reversal throws the
//    lead off until the estimate catches up; a target's QB also adds `qbErr` deg fading over `qbBlind` s;
//  - error: a smooth wandering offset (an OU walk, sd 1, correlation 1 / `wander` s) times E deg, E = aimErr x (1 + rangeErr x (d - 1500) / 1500)
//    x (1 + settle while tracking is younger than settleT s, fading) + moveErr x the target's lateral angular speed (deg/s),
//    all x the target's width (radius / 90: a pilot aims finer at a small frame; keeps the frames' AP balance);
//  - the FCS assist (IF_fireDir) steers a bot's assisted rounds toward this perceived, offset point, not the true lead,
//    so the error survives the gimbal (a human's error is his crosshair; the gimbal used to erase every bot error).
// ===================================================================================================================

class IF_AiState {
  constructor(tier, tierKey) {
    this.tier = tier; this.tierKey = tierKey;
    this.thinkT = 0; this.target = -1; this.goal = IF_v3(0, 0, 0); this.goalCell = -1; this.hasGoal = false;
    this.strafe = 1; this.strafeT = 0; this.errYaw = 0; this.errPitch = 0; this.dodgeT = 0; this.dodgeX = 0; this.dodgeY = 0;
    this.coverT = 0; this.cover = IF_v3(0, 0, 0); this.stuckT = 0; this.checkX = 0; this.checkY = 0; this.checkT = 0; this.unstuckT = 0;
    this.unX = 0; this.unY = 0; this.burstOn = true; this.burstT = 0; this.jumpT = 0; this.yaw = 0; this.pitch = 0; this.reactT = 0;
    this.band = 2000; this.boostOn = false; this.dist = 1e9; this.los = false; this.lastSeenT = -99; this.dodgedMsl = 0;
    this.fire = [false, false, false, false]; this.wantQb = false; this.chainAt = -99;
    // aim model (header): the target being aimed at, tracking time, perceived velocity, last seen centre, time out of sight,
    // the target's last QB seen, QB surprise left, the wander (yaw, pitch), the error E (deg), the offset (deg), the FCS flag
    this.aimSlot = -1; this.trackT = 0; this.vEst = IF_v3(0, 0, 0); this.lastPos = IF_v3(0, 0, 0); this.lostT = 0;
    this.tgtQbAt = -99; this.surpriseT = 0; this.nY = 0; this.nP = 0; this.errDeg = 0;
    this.offYaw = 0; this.offPitch = 0; this.fcsOn = false; this.perc = IF_v3(0, 0, 0);
  }
}

const IF_Ai = {
  // per-tier loadout list for a bot; pve lists for Sortie enemies
  loadoutFor(game, listKey) {
    const L = game.P.aiLoadouts || {}, list = L[listKey] || L.normal || [];
    for (let tries = 0; tries < 4 && list.length; tries++) {
      const s = list[Math.floor(game.rng() * list.length)], ids = IF_parseLoadout(s);
      if (ids && ids.every((id, i) => id === 0 ? (i >= 1 && i <= 4) : game.P.byId.has(id))) return s;
    }
    return (game.P.starter && game.P.starter.loadouts[0]) || '4,101,103,201,209,301,401,501,601';
  },
  // The fill skill, 0 easy .. 1 normal .. 2 hard: the lobby's average human rank (stand-alone pilots and rookies: easy) plus game.fillAdj,
  // which follows how the humans fare against the fill (a human kill of a fill bot raises it, a human killed by one lowers it three
  // times as much, both divided by the human count: it settles where pilots win about three exchanges in four). 10 Nov 2026 playtest:
  // "if i hold mouse1+2 and look straight at an enemy, they always win": a new pilot's starter kit met normal-tier bots with rank 4-17
  // weapons. The tier of a bot is drawn from the skill (0.7 = 70 % normal, 30 % easy) when it is added and at each respawn (retier).
  fillSkill(game) {
    let n = 0, sum = 0;
    for (const m of game.mechs.values()) if (m.human && m.rank > 0) { n++; sum += m.rank; }
    const T = game.cfg.ai.tierRank, avg = n ? sum / n : 0;
    const base = avg >= T.hard ? 2 : avg >= T.normal ? 1 : 0;
    // the operator's bounds (IronFrame.Rules.AiSkillMin / Max) hold whatever the lobby's rank and the fill's record say
    return IF_clamp(base + (game.fillAdj || 0), IF_RULES ? IF_RULES.aiMin : 0, IF_RULES ? IF_RULES.aiMax : 2);
  },
  fillTier(game) {
    const s = IF_Ai.fillSkill(game), lo = Math.floor(s), k = Math.min(2, lo + (game.rng() < s - lo ? 1 : 0));
    return k >= 2 ? 'hard' : k >= 1 ? 'normal' : 'easy';
  },
  onKill(game, k, v) {
    if (!k || !v || k === v) return;
    const S = game.cfg.ai.skill; if (!S) return;
    let humans = 0; for (const m of game.mechs.values()) if (m.human) humans++;
    const n = Math.max(1, humans);
    if (k.human && v.fill) game.fillAdj = IF_clamp((game.fillAdj || 0) + S.up / n, -2, 2);
    else if (v.human && k.fill) game.fillAdj = IF_clamp((game.fillAdj || 0) - S.down / n, -2, 2);
  },
  // a fill bot about to respawn takes the current skill's tier (and a loadout from that tier's list)
  retier(game, m) {
    if (!m.fill || !m.ai) return;
    const tk = IF_Ai.fillTier(game);
    if (tk === m.ai.tierKey) return;
    IF_Ai.attach(game, m, tk); m.pendingLoadout = IF_Ai.loadoutFor(game, tk);
  },
  attach(game, m, tierKey) {
    const t = game.cfg.ai.tiers[tierKey] || game.cfg.ai.tiers.normal;
    m.ai = new IF_AiState(t, tierKey);
    m.ai.thinkT = (m.slot % t.think) / IF_TICKRATE;
    m.ai.strafe = (m.slot & 1) ? 1 : -1;
    m.tier = tierKey;
  },

  // ---------------------------------------------------------------------------------------------------------- fill
  // Keep the bot population per mode (called by the game once a second). Returns how many NPC mechs were changed.
  fillCheck(game, humans) {
    const A = game.cfg.ai, mode = game.match.mode;
    if (!A.npcFill || game.match.phase === 'podium' || game.match.phase === 'over') return 0;
    if (humans === undefined) humans = game.humanCount();
    const counts = { 2: 0, 3: 0 }, fills = { 2: [], 3: [] };
    for (const m of game.mechs.values()) {
      if (m.npc && m.fill) { (fills[m.team] || (fills[m.team] = [])).push(m); counts[m.team] = (counts[m.team] || 0) + 1; }
      else if (!m.npc && (m.team === 2 || m.team === 3)) counts[m.team]++;
    }
    let want2 = 0, want3 = 0;
    if (mode === 'so') { want2 = Math.max(0, A.sortieAllies - humans); want3 = 0; }
    else if (mode === 'sk') { const tot = humans >= A.floor ? 0 : A.skirmishFill; want2 = Math.ceil(tot / 2); want3 = Math.floor(tot / 2); }
    else if (humans < A.floor) { want2 = A.fillTotal / 2; want3 = A.fillTotal / 2; }
    let changed = 0;
    if (mode === 'so') {
      // allies all on team 2 (side 0 in Sortie); count every non-enemy mech
      const have = counts[2] + counts[3];
      const fillN = fills[2].length + fills[3].length;
      const target = Math.max(A.sortieAllies, humans);
      if (have < target) { if (game.addNpc(2, this.fillTier(game), true)) changed++; }
      else if (have > target && fillN) { game.removeNpc(this.pickDrop(fills[2].concat(fills[3])).slot); changed++; }
      return changed;
    }
    for (const team of [2, 3]) {
      const want = team === 2 ? want2 : want3;
      const nonFill = counts[team] - fills[team].length;
      const goal = Math.max(nonFill, want);
      if (counts[team] < goal && humans < A.floor) { if (game.addNpc(team, this.fillTier(game), true)) changed++; }
      else if (counts[team] > goal && fills[team].length) { game.removeNpc(this.pickDrop(fills[team]).slot); changed++; }
    }
    return changed;
  },
  // the fill bot to drop first: a dead one, else the one with the least AP
  pickDrop(list) {
    let best = list[0];
    for (const m of list) { if (!m.alive) return m; if (m.ap < best.ap) best = m; }
    return best;
  },

  // ---------------------------------------------------------------------------------------------------------- think
  think(game, m) {
    const ai = m.ai, T = ai.tier, C = game.cfg.ai;
    // target by cost: distance + turn + hysteresis + whoever hurt me lately; squads share
    let best = null, bc = Infinity;
    const sq = m.squad >= 0 ? game.squads.get(m.squad) : null;
    for (const o of game.alive) {
      if (o === m || !game.enemies(m, o) || o.dropT > 0) continue;
      const dx = o.pos.x - m.pos.x, dy = o.pos.y - m.pos.y, d = Math.sqrt(dx * dx + dy * dy + (o.pos.z - m.pos.z) ** 2);
      if (d > 12000) continue;
      const turn = Math.abs(IF_angleDiff(m.torsoYaw, IF_yawOf(dx, dy)));
      let c = d + turn * 12 + (o.ap / o.apMax) * 600;
      if (o.slot === ai.target) c -= 900;
      if (m.dmgT[o.slot] > game.time - 3) c -= 700;
      if (sq && sq.target === o.slot) c -= 600;
      if (o.boss) c -= 400;
      if (c < bc) { bc = c; best = o; }
    }
    ai.target = best ? best.slot : -1;
    if (sq && best && (sq.t < game.time - 2 || sq.target < 0)) { sq.target = best.slot; sq.t = game.time; }
    // objective
    ai.hasGoal = game.modeGoal(m, ai.goal);
    if (!ai.hasGoal && best) { IF_vcopy(ai.goal, best.pos); ai.hasGoal = true; }
    if (sq && ai.hasGoal && !m.carrier) { if (sq.goalT < game.time - 3) { IF_vcopy(sq.goal, ai.goal); sq.goalT = game.time; } else if (IF_vdistXY(sq.goal, ai.goal) < 3000) IF_vcopy(ai.goal, sq.goal); }
    if (game.feat && game.feat.crateOn) game.featGoal(m, ai, best);
    ai.goalCell = ai.hasGoal ? game.nav.coarseGoal(ai.goal.x, ai.goal.y) : -1;
    // range band: the longest effective range among loaded attack weapons, scaled by the tier
    let band = 600;
    for (const wp of m.weapons) {
      const w = wp.w; if (!w || w.type === 'shield' || w.type === 'ability') continue;
      if (!IF_hasAmmo(wp) && !(wp.reloading)) continue;
      const r = w.type === 'melee' ? 500 : (w.range || 3000) * T.rangeFrac;
      if (r > band) band = r;
    }
    ai.band = Math.min(band, 4200);
    // a blade build rushes: the band is the lunge range while the EN allows a lunge
    for (const wp of m.weapons) if (wp.w && wp.w.type === 'melee' && wp.cd < 1.5 && m.en > (wp.w.en_shot || 0) + 200) ai.band = Math.max(260, Math.max(wp.w.lunge || 600, game.cfg.weapon.meleeLockRange) * 0.8);   // the homing lunge reaches the lock range
    // aim: line of sight to the target (heightfield; the lock's own when locked)
    if (best) {
      const c = IF_center(best, ai.perc);
      ai.los = m.lock.target === best.slot ? m.lock.los : game.nav.rayFrac(m.aimOrigin.x, m.aimOrigin.y, m.aimOrigin.z, c.x, c.y, c.z, 160, !!(game.world && game.world.traceLine)) >= 0.98;
    } else ai.los = false;
    // cover when staggered or low on AP
    if (ai.coverT <= 0 && best && (m.staggered > 0 || m.ap < C.coverAp * m.apMax) && game.rng() < T.cover) {
      const c = best.pos;
      if (game.nav.findCover(m.pos.x, m.pos.y, c.x, c.y, c.z + best.height * 0.6, 1600, ai.cover)) ai.coverT = C.coverTime;
    }
    // stuck check once a second
    if (game.time - ai.checkT > 1) {
      const moved = Math.hypot(m.pos.x - ai.checkX, m.pos.y - ai.checkY);
      if (m.wishLen > 0.5 && moved < 80 && !m.braced && m.lungeT <= 0) ai.stuckT += game.time - ai.checkT; else ai.stuckT = 0;
      ai.checkX = m.pos.x; ai.checkY = m.pos.y; ai.checkT = game.time;
      if (ai.stuckT > C.stuckTime) {
        ai.stuckT = 0; ai.unstuckT = 1.5; ai.jumpT = 0.8;
        const a = game.rng() * Math.PI * 2; ai.unX = Math.cos(a); ai.unY = Math.sin(a); ai.wantQb = true;
        game.stats.aiUnstuck++;
      }
    }
    // abilities
    for (let hp = 0; hp < 4; hp++) ai.fire[hp] = false;
    for (let hp = 2; hp < 4; hp++) {
      const wp = m.weapons[hp], w = wp.w;
      if (!w || w.type !== 'ability' || wp.cd > 0) continue;
      if (w.charges && wp.charges <= 0) continue;
      if (w.ability === 'decoy' && (m.lockedBy > 0 || m.threats.some((t) => t.kind === 'missile')) && game.rng() < T.decoy) ai.fire[hp] = true;
      if (w.ability === 'repair' && m.ap < m.apMax * 0.55 && m.healLeft <= 0) ai.fire[hp] = true;
      if (w.ability === 'bubble' && game.time - m.lastDamageT < 1 && best && ai.dist < 3500) ai.fire[hp] = true;
      if (w.ability === 'drones' && m.droneN <= 0 && best && m.lock.stage >= 1 && ai.dist < (w.range || 3500) * 0.9) ai.fire[hp] = true;
      if (w.ability === 'mines' && m.mineN < (w.max || 4) && m.onGround && best && ai.dist < 2600 && ai.dist > 500 && m.speed < 400 && game.rng() < 0.15) ai.fire[hp] = true;
    }
  },

  // ---------------------------------------------------------------------------------------------------------- tick
  step(game, m, dt) {
    const ai = m.ai; if (!ai) return;
    const T = ai.tier, C = game.cfg.ai, inp = m.input;
    ai.thinkT -= dt;
    if (ai.thinkT <= 0) { ai.thinkT += T.think / IF_TICKRATE * 4; IF_Ai.think(game, m); }
    if (ai.coverT > 0) ai.coverT -= dt;
    if (ai.dodgeT > 0) ai.dodgeT -= dt;
    if (ai.unstuckT > 0) ai.unstuckT -= dt;
    if (ai.jumpT > 0) ai.jumpT -= dt;
    ai.strafeT -= dt;
    if (ai.strafeT <= 0) { ai.strafe = -ai.strafe; ai.strafeT = C.orbitSwitch * (0.5 + game.rng()); }
    const t = ai.target >= 0 ? game.mechs.get(ai.target) : null;
    const live = t && t.alive ? t : null;
    // ---- aim: the perceived lead point, the tier's error, a reaction delay and a lagging turn (header)
    let wantYaw = m.torsoYaw, wantPitch = 0;
    const aimPt = game._aiAim;
    ai.fcsOn = false;
    if (live) {
      const prim = IF_Ai.primary(m), sp = prim && prim.w.speed ? prim.w.speed : 0;
      IF_Ai.perceive(game, m, live, dt);
      IF_Ai.leadFrom(ai.perc, ai.vEst, m.aimOrigin, sp, T.lead, aimPt);
      const dx = aimPt.x - m.aimOrigin.x, dy = aimPt.y - m.aimOrigin.y, dz = aimPt.z - m.aimOrigin.z;
      ai.dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
      if (ai.reactT > 0) { wantYaw = IF_fin(ai.yaw, m.torsoYaw); wantPitch = IF_fin(ai.pitch, 0); }   // not reacted yet: hold
      else {
        wantYaw = IF_yawOf(dx, dy) + ai.offYaw; wantPitch = IF_pitchOf(dx, dy, dz) + ai.offPitch;
        if (prim && prim.w.type === 'lob') wantPitch -= 4;   // the lob solver handles the arc; keep the crosshair near
        ai.fcsOn = true;
      }
    } else {
      ai.dist = 1e9; ai.aimSlot = -1;
      if (m.speed > 50) wantYaw = IF_yawOf(m.vel.x, m.vel.y);
    }
    const turn = (T.react < 0.3 ? 420 : 300) * dt, cy = IF_fin(ai.yaw, m.torsoYaw), cp = IF_fin(ai.pitch, 0);
    const gain = Math.min(1, (T.gain || 60) * dt);
    ai.yaw = IF_turnAngle(cy, wantYaw, Math.min(turn, Math.abs(IF_angleDiff(cy, wantYaw)) * gain + 0.02));
    ai.pitch = IF_approach(cp, IF_clamp(wantPitch, -60, 60), Math.min(turn * 0.7, Math.abs(wantPitch - cp) * gain + 0.02));
    inp.yaw = ai.yaw; inp.pitch = ai.pitch; inp.camPos = null; inp.camDir = null;
    // ---- movement: a world direction (wx, wy)
    let wx = 0, wy = 0, far = false;
    const fd = game._aiDir;
    if (ai.unstuckT > 0) { wx = ai.unX; wy = ai.unY; }
    else if (ai.dodgeT > 0) { wx = ai.dodgeX; wy = ai.dodgeY; }
    else if (ai.coverT > 0) {
      const dx = ai.cover.x - m.pos.x, dy = ai.cover.y - m.pos.y, d = Math.hypot(dx, dy);
      if (d > 150) { if (game.nav.flowDir(game.nav.idx(ai.cover.x, ai.cover.y), m.pos.x, m.pos.y, fd)) { wx = fd.x; wy = fd.y; } else { wx = dx / d; wy = dy / d; } }
    } else if (live && ai.dist < Math.max(ai.band * 1.5, 2400) && (m.lock.target === live.slot || ai.dist < Math.max(ai.band, 1800))) {
      // engage: hold the range band and strafe
      const dx = live.pos.x - m.pos.x, dy = live.pos.y - m.pos.y, d = Math.max(1, Math.hypot(dx, dy));
      const ux = dx / d, uy = dy / d;
      const radial = d > ai.band * 1.05 ? 1 : d < ai.band * 0.6 ? -0.8 : 0;
      const close = ai.band < 1200;   // shotgun / blade builds close in hard and strafe less
      const sf = close && d > ai.band ? 0.35 : 0.9;
      wx = ux * radial - uy * ai.strafe * sf; wy = uy * radial + ux * ai.strafe * sf;
      far = d > ai.band * 1.3;
      if (close && d > ai.band * 1.2 && d < ai.band * 3.5 && m.qbCd <= 0 && m.en > m.enMax * 0.5 && ai.dodgeT <= 0 && game.rng() < 2 * dt) ai.wantQb = true;
      // a contested objective: drift toward it while fighting
      const op = game.objPull(m, ai);   // src/core/85_objectives.js
      if (op) { wx += op.x; wy += op.y; }
    } else if (ai.hasGoal) {
      const gd = IF_vdistXY(ai.goal, m.pos);
      if (gd > 350) {
        if (game.nav.flowDir(ai.goalCell, m.pos.x, m.pos.y, fd)) { wx = fd.x; wy = fd.y; }
        else { wx = (ai.goal.x - m.pos.x) / gd; wy = (ai.goal.y - m.pos.y) / gd; }
        far = gd > 1500;
      } else { wx = -Math.sin(game.time * 0.5 + m.slot) * 0.5; wy = Math.cos(game.time * 0.5 + m.slot) * 0.5; }   // mill about on the point
    }
    // cliffs ahead on the heightfield: jump
    const ahead = game.nav.height(m.pos.x + wx * 200, m.pos.y + wy * 200);
    if (m.onGround && ahead > m.pos.z + 70 * m.scale && (wx || wy)) ai.jumpT = Math.max(ai.jumpT, 0.6);
    // wish -> camera-relative mx / my (mech: right = (fy, -fx))
    const yr = ai.yaw * IF_D2R, fx = Math.cos(yr), fy = Math.sin(yr);
    inp.my = IF_clamp(wx * fx + wy * fy, -1, 1); inp.mx = IF_clamp(wx * fy - wy * fx, -1, 1);
    // ---- missile dodge by time to impact; incoming locks
    inp.qb = false;
    let tti = 99;
    for (const th of m.threats) if (th.kind === 'missile' && th.tti < tti) tti = th.tti;
    if (tti < C.missileDodgeTti && m.qbCd <= 0 && ai.dodgedMsl < game.time - 0.6) {
      ai.dodgedMsl = game.time;
      if (game.rng() < T.qbDodge) {
        // across the line from the nearest missile threat
        let th = null; for (const x of m.threats) if (x.kind === 'missile' && (!th || x.tti < th.tti)) th = x;
        const mx = m.pos.x - th.x, my = m.pos.y - th.y, ml = Math.hypot(mx, my) || 1;
        const s = game.rng() < 0.5 ? 1 : -1;
        ai.dodgeX = -my / ml * s; ai.dodgeY = mx / ml * s; ai.dodgeT = 0.3;
        inp.my = IF_clamp(ai.dodgeX * fx + ai.dodgeY * fy, -1, 1); inp.mx = IF_clamp(ai.dodgeX * fy - ai.dodgeY * fx, -1, 1);
        inp.qb = true;
      }
    }
    if (ai.wantQb) { inp.qb = true; ai.wantQb = false; }
    // AC4 two-step: a pilot with a missile still closing in chains a second QB across the first one (tier `chain` odds; not for gunfire:
    // chaining against every hard lock burned the bots' EN and lost them rifle duels)
    const MV = game.move;
    if (!inp.qb && T.chain > 0 && MV.qb_chain > 0 && m.qbCd > 0 && !m.qbChained && ai.chainAt !== m.qbAt && game.time - m.qbAt >= MV.qb_chain && game.time - m.qbAt < MV.qb_chain + 0.3) {
      ai.chainAt = m.qbAt;
      if (tti < 1.5 && m.en > m.qbCost * (MV.qb_chain_cost || 1) + 200 && game.rng() < T.chain) {   // a missile still closing in
        const s = game.rng() < 0.5 ? 1 : -1;
        ai.dodgeX = -m.qbDir.y * s; ai.dodgeY = m.qbDir.x * s; ai.dodgeT = 0.3;
        inp.my = IF_clamp(ai.dodgeX * fx + ai.dodgeY * fy, -1, 1); inp.mx = IF_clamp(ai.dodgeX * fy - ai.dodgeY * fx, -1, 1);
        inp.qb = true;
      }
    }
    // a random sidestep under fire
    if (!inp.qb && live && game.time - m.lastDamageT < 0.5 && m.qbCd <= 0 && game.rng() < T.dodge * dt * 2 && m.en > m.enMax * 0.4) inp.qb = true;
    // ---- boost policy: a reserve per tier, hysteresis
    const res = T.boostRes;
    if (ai.boostOn && m.en < res * 0.5) ai.boostOn = false;
    if (!ai.boostOn && m.en > res && (far || ai.dodgeT > 0 || ai.coverT > 0 || ai.unstuckT > 0 || (live && ai.dist < 1200))) ai.boostOn = true;
    if (!far && !(ai.dodgeT > 0) && !(ai.coverT > 0) && !(ai.unstuckT > 0) && !(live && ai.dist < 1200)) ai.boostOn = false;
    inp.boost = ai.boostOn && m.enStalled <= 0;
    inp.jump = (ai.jumpT > 0 && m.en > 400) || (live && !m.onGround && m.en > m.enMax * 0.6 && game.rng() < T.jump);
    // ---- weapons: by range band, burst discipline, locks
    ai.burstT -= dt;
    if (ai.burstT <= 0) { ai.burstOn = !ai.burstOn; ai.burstT = ai.burstOn ? 0.6 + 1.4 * T.burst : 0.2 + 0.8 * (1 - T.burst); }
    const lockedOn = live && m.lock.target === live.slot;
    // the bot judges its aim against the point it perceives (it doesn't know its own error); no fire before it reacted
    const aimOff = live ? IF_angleBetween(m.aimDir.x, m.aimDir.y, m.aimDir.z, aimPt.x - m.aimOrigin.x, aimPt.y - m.aimOrigin.y, aimPt.z - m.aimOrigin.z) : 180;
    const reacted = !(ai.reactT > 0);
    for (let hp = 0; hp < 4; hp++) {
      const wp = m.weapons[hp], w = wp.w;
      let f = false;
      if (w && live && m.dropT <= 0 && (reacted || w.type === 'shield' || w.type === 'ability')) {
        const d = ai.dist;
        switch (w.type) {
          case 'proj': case 'lob': case 'hitscan':
            f = d <= (w.range || 3000) * (w.splash ? 0.95 : 1.05) && aimOff < (w.pellets ? 8 : 6) + (lockedOn ? m.fcs.f.gimbal : 0) && (ai.burstOn || w.cd || w.charge || w.windup || w.splash > 0) && (lockedOn || d < 1500 || m.lock.los);
            if (w.charge && !w.cannon && wp.charging) f = wp.charge < w.charge && aimOff < 10;   // laser: hold to full charge
            if (w.en_shot && m.en < w.en_shot + 300) f = f && wp.charging;
            if (w.cannon && m.speed > 400 && m.cannonMoveAcc < 1) f = f && ai.dist > 1500;
            if (w.no_boost && (m.boosting || ai.dodgeT > 0)) f = false;     // sniper: stand still to shoot
            if (w.cone) f = f && d <= w.range;                              // flamethrower: only inside the cone's reach
            break;
          case 'melee': f = d < Math.max(w.lunge || 600, lockedOn ? game.cfg.weapon.meleeLockRange : 0) + 100 && aimOff < 25 && m.en > (w.en_shot || 0) + 100; break;
          case 'missile':
            if (w.multilock) {      // hold to lock the squad in the cone, release once all are locked (or the lock time passed)
              f = wp.cd <= 0 && IF_hasAmmo(wp) && d <= (w.range || 6000) && aimOff < m.fcs.f.cone && m.lock.los;
              if (f && ((wp.mlDone > 0 && (wp.mlDone >= w.multilock || wp.mlHold > m.lockHard + 0.5)) || wp.mlHold > m.lockHard + 2.5)) f = false;
              break;
            }
            f = lockedOn && m.lock.stage >= (w.lock === 'hard' ? 2 : 1) && d <= (w.range || 6000); break;
          case 'shield': f = game.time - m.lastDamageT < 0.6 && m.en > m.enMax * 0.3 && !(m.weapons[0].w && ai.burstOn && aimOff < 6); break;
          case 'ability': f = ai.fire[hp]; ai.fire[hp] = false; break;
          default: break;
        }
      } else if (w && w.type === 'ability') { f = ai.fire[hp]; ai.fire[hp] = false; }
      inp.fire[hp] = f;
    }
    inp.cycle = false; inp.any = true;
  },
  // what the bot perceives of its target this tick (header): reaction on a switch / reacquire, the low-passed velocity, the QB
  // surprise, the error E and the wandering offset. Fills ai.perc (the centre it aims at), ai.vEst, ai.offYaw / offPitch.
  perceive(game, m, t, dt) {
    const ai = m.ai, T = ai.tier, C = game.cfg.ai;
    if (t.slot !== ai.aimSlot) {          // a new target: react, settle from scratch, no velocity known yet
      ai.aimSlot = t.slot; ai.reactT = T.react; ai.trackT = 0; ai.lostT = 0; ai.surpriseT = 0; ai.tgtQbAt = t.qbAt;
      ai.vEst.x = ai.vEst.y = ai.vEst.z = 0; IF_center(t, ai.lastPos);
    }
    if (ai.los) {
      if (ai.lostT > (C.aimLostT || 0.35)) { ai.reactT = Math.max(ai.reactT, T.react * 0.8); ai.trackT = 0; }   // back in sight
      ai.lostT = 0; IF_center(t, ai.lastPos);
      const k = Math.min(1, dt / Math.max(0.01, T.velLag || 0.01)), vz = t.onGround ? 0 : t.vel.z;
      ai.vEst.x += (t.vel.x - ai.vEst.x) * k; ai.vEst.y += (t.vel.y - ai.vEst.y) * k; ai.vEst.z += (vz - ai.vEst.z) * k;
    } else {
      ai.lostT += dt; const k = Math.min(1, dt * 2); ai.vEst.x -= ai.vEst.x * k; ai.vEst.y -= ai.vEst.y * k; ai.vEst.z -= ai.vEst.z * k;
    }
    IF_vcopy(ai.perc, ai.lastPos);
    if (ai.reactT > 0) ai.reactT -= dt; else if (ai.los) ai.trackT += dt;
    if (t.qbAt !== ai.tgtQbAt) { ai.tgtQbAt = t.qbAt; if (game.time - t.qbAt < 0.2) ai.surpriseT = T.qbBlind || 0; }
    if (ai.surpriseT > 0) ai.surpriseT -= dt;
    // E: base x range x settle + the target's lateral angular speed + a fresh QB; the bot's own QB jet shakes it too
    const dx = ai.perc.x - m.aimOrigin.x, dy = ai.perc.y - m.aimOrigin.y, dz = ai.perc.z - m.aimOrigin.z;
    const d = Math.max(200, Math.sqrt(dx * dx + dy * dy + dz * dz));
    const vr = (t.vel.x * dx + t.vel.y * dy + t.vel.z * dz) / d;
    const vlat = Math.sqrt(Math.max(0, t.vel.x * t.vel.x + t.vel.y * t.vel.y + t.vel.z * t.vel.z - vr * vr));
    const omega = vlat / d * IF_R2D;
    let E = (T.aimErr || 0) * (1 + (T.rangeErr || 0) * Math.max(0, d - 1500) / 1500);
    if (T.settleT > 0) E *= 1 + (T.settle || 0) * Math.max(0, 1 - ai.trackT / T.settleT);
    E += (T.moveErr || 0) * omega;
    if (ai.surpriseT > 0 && T.qbBlind > 0) E += (T.qbErr || 0) * ai.surpriseT / T.qbBlind;
    if (m.qbJet > 0) E *= 1.5;
    // Fitts: a pilot aims finer at a smaller frame (the error scales with the target's width; a medium is 90 u). Without it the
    // light frames dodged everything and won 70-80 % of the round robin (the frames' AP is tuned for equal hit rates)
    E *= IF_clamp((t.radius || 90) / 90, 0.6, 1.4);
    ai.errDeg = E;
    // the wander: an Ornstein-Uhlenbeck walk with unit variance and a 1 / wander s correlation time (smooth, not a jitter)
    const th = Math.min(0.5, (T.wander || 3) * dt), sg = Math.sqrt(2 * th) * 2;
    ai.nY += -ai.nY * th + IF_noise(game.rng) * sg; ai.nP += -ai.nP * th + IF_noise(game.rng) * sg;
    ai.offYaw = ai.nY * E; ai.offPitch = ai.nP * E * 0.5;
  },
  // a lead point from a perceived centre `c` (z at the 0.55 height centre) and velocity `v` (IF_leadPoint with given data)
  leadFrom(c, v, from, speed, frac, o) {
    o.x = c.x; o.y = c.y; o.z = c.z;
    if (!(speed > 0) || frac <= 0) return o;
    let tt = IF_vdist(from, o) / speed;
    for (let k = 0; k < 2; k++) {
      const x = c.x + v.x * tt * frac, y = c.y + v.y * tt * frac, z = c.z + v.z * tt * frac;
      tt = Math.sqrt((x - from.x) ** 2 + (y - from.y) ** 2 + (z - from.z) ** 2) / speed;
    }
    o.x = c.x + v.x * tt * frac; o.y = c.y + v.y * tt * frac; o.z = c.z + v.z * tt * frac;
    return o;
  },
  // the FCS assist point of a bot (IF_fireDir): its perceived lead from the muzzle, turned by its current offset; null when the
  // bot isn't aiming at that target (then the true lead is used, as for a human)
  fcsPoint(m, t, mz, speed, o) {
    const ai = m.ai;
    if (!ai || !ai.fcsOn || ai.aimSlot !== t.slot) return null;
    IF_Ai.leadFrom(ai.perc, ai.vEst, mz, speed, 1, o);
    const dx = o.x - mz.x, dy = o.y - mz.y, dz = o.z - mz.z, d = Math.sqrt(dx * dx + dy * dy + dz * dz);
    const yr = (IF_yawOf(dx, dy) + ai.offYaw) * IF_D2R, pr = (IF_pitchOf(dx, dy, dz) + ai.offPitch) * IF_D2R;
    o.x = mz.x + Math.cos(pr) * Math.cos(yr) * d; o.y = mz.y + Math.cos(pr) * Math.sin(yr) * d; o.z = mz.z - Math.sin(pr) * d;
    return o;
  },
  // the main gun: the first arm weapon with a speed / range (lead uses its speed)
  primary(m) {
    for (let i = 0; i < 4; i++) { const wp = m.weapons[i]; if (wp.w && (wp.w.type === 'proj' || wp.w.type === 'hitscan' || wp.w.type === 'lob')) return wp; }
    return null;
  },
};
