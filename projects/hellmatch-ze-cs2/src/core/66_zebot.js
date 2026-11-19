// ===================================================================================
// Part 6c (Hellmatch ZE): bots in a zombie escape round.
//   human bots: walk to the active stage's zone (or the line / switch the next stage waits for) along the sector graph and
//               hold it, shooting zombies and monsters on the way; moving and aiming are separate (strafe-walk).
//   zombie bots: chase the nearest human through the sector graph and use their class's attacks in range.
// ===================================================================================

function zeBotRoute(arena, p, b, tx, ty) {
  const mo = p.mo;
  if (arena.leveltime >= (b.routeAt || 0) || !b.routeTo || Math.abs(b.routeTo.x - tx) > 64 || Math.abs(b.routeTo.y - ty) > 64) {
    b.routeAt = arena.leveltime + 10 + (p.slot % 7);
    b.routeTo = { x: tx, y: ty };
    b.portal = arena.run(() => navNext(arena.level, mo.x, mo.y, tx, ty));
  }
  const e = b.portal;
  if (!e) return pointToAngle(mo.x, mo.y, tx, ty);
  const pp = portalPoint(e.line, mo.x, mo.y);
  const near = Math.hypot(pp.x - mo.x, pp.y - mo.y);
  if (e.lift && e.line.frontsector && e.line.backsector && Math.abs(e.line.frontsector.floorheight - e.line.backsector.floorheight) > MAXSTEP) {
    // the lift is up: walk to its switch and press use
    const tp = portalPoint(e.trigger, mo.x, mo.y);
    if (Math.hypot(tp.x - mo.x, tp.y - mo.y) < 56) b.use = true;
    return pointToAngle(mo.x, mo.y, tp.x, tp.y);
  }
  if (near < 40) {
    if (NAV_DOORS.has(e.line.special)) b.use = true;
    return pointToAngle(mo.x, mo.y, tx, ty);
  }
  return pointToAngle(mo.x, mo.y, pp.x, pp.y);
}

function zeBotThink(arena, p) {
  const cmd = p.cmd, mo = p.mo;
  cmd.forwardmove = 0; cmd.sidemove = 0; cmd.buttons = 0;
  if (!mo || mo.removed || p.spectating || p.playerstate !== 'live') return;
  const b = p.bot || (p.bot = { target: null, retarget: 0, lastx: mo.x, lasty: mo.y, stuck: 0, strafe: 1, wanderAngle: mo.angle, portal: null, routeAt: 0, routeTo: null, unstickUntil: 0, use: false, reactUntil: 0, aimErr: 0 });
  if (b.skill === undefined) b.skill = Math.max(0, Math.min(1, (arena.cfg.botSkill || 0.35) + ((p.slot * 37) % 7 - 3) * 0.04));
  const skill = b.skill, zombie = !!p.zclass, lt = arena.leveltime;
  b.use = false;
  // ---- who to fight (re-picked a few times a second; the nearest one in sight)
  if (--b.retarget <= 0) {
    b.retarget = 5 + Math.round((1 - skill) * 8);
    b.aimErr = zombie ? 0 : (P_Random() - 128) / 128 * (1 - skill) * 24;
    let best = null;
    arena.run(() => {
      const cands = botCands; cands.length = 0;
      if (zombie) {
        for (const t of arena.playerMobjs) {
          if (!targetable(t)) continue;
          const d = Math.hypot(t.x - mo.x, t.y - mo.y);
          if (d < 3000) cands.push({ d, mo: t, q: null, n: cands.length });
        }
      } else {
        for (const q of arena.players.values()) {
          if (!q.zclass || q.playerstate !== 'live' || !q.mo || q.mo.removed || q.spectating) continue;
          const d = Math.hypot(q.mo.x - mo.x, q.mo.y - mo.y);
          if (d < 1800) cands.push({ d: d * 0.9, mo: q.mo, q, n: cands.length });   // players first on equal distance
        }
        for (const m of arena.mobjs) {
          if (m.info.kind !== 'monster' || m.health <= 0) continue;
          const d = Math.hypot(m.x - mo.x, m.y - mo.y);
          const awake = STATES[m.state].action !== 'A_Look';
          if (d < (awake ? 1600 : 700)) cands.push({ d: awake ? d : d * 1.5, mo: m, q: null, n: cands.length });
        }
      }
      if (cands.length > 1) cands.sort(byDistThenOrder);
      for (let i = 0; i < cands.length && i < 6; i++) if (checkSight(mo, cands[i].mo)) { best = cands[i].mo; break; }
      cands.length = 0;
    });
    if (best !== b.target) b.reactUntil = lt + Math.round((1 - skill) * 25);
    b.target = best;
  }
  const t = b.target && !b.target.removed && b.target.health > 0 && !(b.target.player && b.target.player.playerstate !== 'live') ? b.target : null;
  const dist = t ? Math.hypot(t.x - mo.x, t.y - mo.y) : 0;
  let moveAng = null, face = null;
  if (zombie) {
    if (t) {
      face = pointToAngle(mo.x, mo.y, t.x, t.y);
      moveAng = face;
      const aimed = Math.abs(angleDiff(mo.angle, face)) < 22;
      const reach = MELEERANGE + t.radius + mo.radius - 12;
      const ready = p.zcd <= 0 && lt >= b.reactUntil;
      if (aimed && dist < reach) cmd.buttons |= BT_ATTACK;
      else if (aimed && ready) {
        if (p.zclass === 'IMP' && dist > 180 && dist < 1400 && P_Random() < 60) cmd.buttons |= BT_ALT;
        else if (p.zclass === 'DEMON' && dist > 90 && dist < 260) cmd.buttons |= BT_ALT;     // a lunge carries ~240
        else if (p.zclass === 'LOSTSOUL' && dist > 48 && dist < 300) cmd.buttons |= BT_ALT;  // a dash carries ~290
      }
    } else {
      // hunt: the nearest human by the sector graph
      let near = null, nd = 1e9;
      for (const h of arena.playerMobjs) { if (!targetable(h)) continue; const d = Math.hypot(h.x - mo.x, h.y - mo.y); if (d < nd) { nd = d; near = h; } }
      if (near) moveAng = zeBotRoute(arena, p, b, near.x, near.y);
      else moveAng = b.wanderAngle;
    }
  } else {
    if (t) {
      face = pointToAngle(mo.x, mo.y, t.x, t.y) + b.aimErr;
      const w = botWeaponFor(p, dist);
      if (w !== p.readyweapon && p.pendingweapon === WP_NOCHANGE) p.wantWeapon = w;
      if (Math.abs(angleDiff(mo.angle, face)) < 12 && lt >= b.reactUntil && P_Random() < 70 + skill * 185) cmd.buttons |= BT_ATTACK;
    }
    const g = arena.ze ? arena.ze.botGoal() : null;
    const away = t && dist < 200 ? pointToAngle(t.x, t.y, mo.x, mo.y) : null;   // back off from a zombie at arm's length
    if (g) {
      const dg = Math.hypot(g.x - mo.x, g.y - mo.y);
      const inside = g.zone ? arena.ze.zoneHas(g.zone, mo.x, mo.y) : false;
      if (g.hold && inside && dg < 200) {
        moveAng = away;
        if (moveAng === null && (lt % 50) < 12) moveAng = normAngle(mo.angle + 90 * b.strafe);   // shuffle in place
      } else if (g.boss && dg < 420 && arena.run(() => checkSight(mo, g.boss))) {
        // in sight of the boss: circle it at a distance (backing off when it comes close), shooting
        const toward = pointToAngle(mo.x, mo.y, g.x, g.y);
        moveAng = away !== null ? away : dg < 260 ? normAngle(toward + 180 + 45 * b.strafe) : normAngle(toward + 90 * b.strafe);
        if (!t) face = toward;
      } else moveAng = zeBotRoute(arena, p, b, g.x, g.y);
      if (g.use && dg < 80) {
        const lx = (g.use.x1 + g.use.x2) / 2, ly = (g.use.y1 + g.use.y2) / 2;
        if (!t) face = pointToAngle(mo.x, mo.y, lx, ly);
        if ((lt & 7) === 0) b.use = true;
      }
    } else if (away !== null) moveAng = away;
    else {
      // nothing to do: stay with the group (the nearest other live human more than 300 away)
      let mate = null, md = 300;
      for (const h of arena.playerMobjs) { if (h === mo || !targetable(h)) continue; const d = Math.hypot(h.x - mo.x, h.y - mo.y); if (d > md) { md = d; mate = h; break; } }
      if (mate) moveAng = zeBotRoute(arena, p, b, mate.x, mate.y);
    }
    if ((lt % 40) === 0) b.strafe = P_Random() & 1 ? 1 : -1;
  }
  // ---- stuck: no headway for a second -> turn away for a while
  if (moveAng !== null && (lt % 10) === 0) {
    const moved = Math.hypot(mo.x - b.lastx, mo.y - b.lasty);
    if (moved < 16 && !(t && zombie && dist < 90)) {
      if (++b.stuck >= 3) { b.unstickUntil = lt + Math.round(1.2 * TICRATE); b.wanderAngle = normAngle(moveAng + 90 + (P_Random() & 127) * (P_Random() & 1 ? 1 : -1)); b.stuck = 0; b.routeAt = 0; b.use = true; }
    } else b.stuck = 0;
    b.lastx = mo.x; b.lasty = mo.y;
  }
  if (b.unstickUntil > lt) moveAng = b.wanderAngle;
  if (b.use) cmd.buttons |= BT_USE;
  if (face === null) face = moveAng !== null ? moveAng : mo.angle;
  const turn = angleDiff(mo.angle, face);
  const maxTurn = (zombie ? 18 : 10) + 20 * skill;
  cmd.angle = normAngle(mo.angle + Math.max(-maxTurn, Math.min(maxTurn, turn)));
  if (moveAng !== null) {
    const d = (moveAng - cmd.angle) * DEG;
    cmd.forwardmove = Math.round(50 * Math.cos(d));
    cmd.sidemove = Math.round(-40 * Math.sin(d));
  }
}
