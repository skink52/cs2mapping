// 85_ai: bots for low population (remaster step 4; docs/REVIEW_SCRIPT_1.md "Step 4: bots").
// CS2 bots are players with their own legs and guns; a script cannot path them. So:
//  - infantry bots are PLACED: each deploy sends a bot to a useful post (the fire trench mostly, the support trench, and once an area
//    is blown open its sap head / ladder post or a point inside it), and a leash sends back a bot that stands beside a still-closed
//    blocker, is found in no man's land or back in the briefing room, or has wandered far from every post;
//  - when a side has fewer active humans than AI.MIN_HUMANS, some of its bots get a role the script runs while the pawn sits in the
//    seat: AI pilot (patrol over the enemy line, gun and bomb runs on enemy infantry) and AI mortar crew (one bot at the table plots a
//    cluster of enemy infantry, "loads" and fires). Slow and inaccurate on purpose. A human who asks for the role takes the aircraft or
//    the seat at once (aiYieldAircraft / aiYieldSeat, the same tick); a side that reaches the threshold gets its bots back as infantry.
// Entry points: chooseRole -> aiChooseRole (bots), deploy -> aiPost (infantry bots), startFlight -> aiYieldAircraft, takeSeat ->
// aiYieldSeat, leaveTeam / deploy -> aiDrop, thinkPlayer -> tickBot (infantry bots) and aiSteer (AI pilots), think -> aiThink (once per tick).

function isBot(pawn) { try { return pawn.GetPlayerController().IsBot(); } catch (e) { return false; } }
// within r (default LEASH) of a blocker of an area that is still closed
function nearLock(o, r) {
  const B = CONFIG.BOTS, R = r || B.LEASH;
  if (!points) return false;
  for (const u of CONFIG.UNLOCKS) {
    if (unlocked.has(u.name)) continue;
    for (const q of (points.locks[u.name] || [])) if (dist2(o, q) < R && Math.abs(o.z - q.z) < B.LEASH_Z) return true;
  }
  return false;
}

// ------------------------------------------------------------------ who gets the script roles
// humans on a side who are not AFK (an AFK human must not keep the AI out of the seats). Read from the controllers, not the records:
// a human who just joined (or every human, in the first second of the map) has no record with a side yet
function humansOn(team, t) {
  let n = 0;
  for (let s = 0; s < 64; s++) {
    const c = Instance.GetPlayerController(s); if (!c) continue;
    try { if (c.IsBot() || c.GetTeamNumber() !== team) continue; } catch (e) { continue; }
    const q = players.get(s);
    if (q && q.deployed && t - (q.lastActive || t) > CONFIG.AFK.PILOT) continue;
    n++;
  }
  return n;
}
function aiWanted(team, t) { return CONFIG.BOTS_ON && humansOn(team, t) < CONFIG.AI.MIN_HUMANS; }
// a bot's role at (re)spawn: an AI pilot keeps flying while his lives last, an AI crewman keeps his seat; every other bot is infantry
function aiChooseRole(p, team) {
  if (p.aiRole === "pilot" && p.role === "air" && p.lives > 0) return;
  if (p.aiRole === "crew" && p.role === "mortar" && p.crew >= 0) return;
  if (p.aiRole) aiDrop(p, pawnOf(p.slot), p.aiRole === "pilot" ? "lives" : "lost");
  if (p.role !== "infantry") setRole(p, "infantry", team);
}
// the script role's own state is dropped (seat and aircraft are the caller's business: leaveTeam, setRole, endFlight)
function aiDrop(p, pawn, why) {
  const was = p.aiRole; if (!was) return;
  p.aiRole = ""; p.aiFly = undefined;
  if (was === "crew") {
    const c = (p.team === T || p.team === CT) && p.crew >= 0 ? crews[p.team][p.crew] : undefined;
    if (c) c.ai = undefined;
    if (pawn) { try { if (pawn.GetMoveType() === CSMoveType.NONE && !p.inSight) pawn.SetMoveType(CSMoveType.WALK); } catch (e) {} }
  }
  if (why) stats.aiReleased[why] = (stats.aiReleased[why] || 0) + 1;
}
// the bot leaves its script role now: the aircraft goes home, the seat is freed, the bot (if alive out there) deploys as infantry
function aiRelease(p, why) {
  const pawn = pawnOf(p.slot);
  if (p.air) endFlight(p, pawn, false);
  aiDrop(p, pawn, why);
  setRole(p, "infantry", p.team);                       // leaves the crew seat
  let alive = false; try { alive = !!pawn && pawn.IsAlive(); } catch (e) {}
  if (alive && p.deployed) deploy(p, pawn);
}
// a human who asked for the air and found no aircraft free: one a script bot holds is handed over in the same call
function aiYieldAircraft(team, h) {
  if (!points) return undefined;
  for (const ac of points.aircraft[team] || []) {
    if (!live(ac.ent) || ac.pilot < 0) continue;
    const q = players.get(ac.pilot);
    if (!q || !q.bot || q.aiRole !== "pilot") continue;
    aiRelease(q, "yield");
    if (ac.pilot >= 0) continue;
    stats.yields.air++;
    toast(h, "A bot pilot handed his aircraft over to you", 4);
    return ac;
  }
  return undefined;
}
// a human takes the seat of crew k, which a script bot runs: the bot leaves first (same tick); true when both seats are free now
function aiYieldSeat(team, k) {
  const c = crews[team][k], q = c && c.a >= 0 ? players.get(c.a) : undefined;
  if (!q || q.aiRole !== "crew") return false;
  aiRelease(q, "yield");
  if (c.a >= 0 || c.b >= 0) return false;
  stats.yields.seat++;
  return true;
}

// ------------------------------------------------------------------ the director (once a second) and the crews (every tick, cheap)
let directorAt = 0;
function aiThink(t, dt) {
  if (!points) return;
  for (const team of [T, CT]) for (let k = 0; k < crews[team].length; k++) if (aiCrew(crews[team][k])) tickAICrew(team, k, t);
  if (t < directorAt) return;
  directorAt = t + CONFIG.AI.DIRECTOR_EVERY;
  for (const team of [T, CT]) direct(team, t);
}
function direct(team, t) {
  const A = CONFIG.AI, bots = [], have = { pilot: [], crew: [] };
  for (const q of players.values()) if (q.bot && q.team === team && q.role) { bots.push(q); if (q.aiRole) have[q.aiRole].push(q); }
  const wanted = aiWanted(team, t), want = { pilot: wanted ? A.PILOTS : 0, crew: wanted ? A.CREWS : 0 };
  // too many: the side reached the human threshold (or CONFIG changed): released at once, in the air or at the table too
  for (const r of ["pilot", "crew"]) {
    const l = have[r].sort((a, b) => (a.deployed ? 1 : 0) - (b.deployed ? 1 : 0));
    while (l.length > want[r]) aiRelease(l.shift(), wanted ? "trim" : "humans");
  }
  if (!wanted) return;
  const cap = Math.floor(bots.length * A.MAX_SHARE);
  let total = have.pilot.length + have.crew.length;
  // a bot in the briefing room first; else one out in the field (bots are exempt from the field role rule: it stops human teleports)
  const free = () => bots.find((q) => !q.aiRole && q.role === "infantry" && !q.deployed) || bots.find((q) => !q.aiRole && q.role === "infantry");
  while (have.pilot.length < want.pilot && total < cap && airFree(team, false)) {
    const q = free(); if (!q) break;
    q.aiRole = "pilot"; setRole(q, "air", team);
    have.pilot.push(q); total++; stats.aiPilots++; aiStart(q);
  }
  while (have.crew.length < want.crew && total < cap) {
    const k = crews[team].findIndex((c) => c.a < 0 && c.b < 0), q = free();
    if (k < 0 || !q) break;
    const c = crews[team][k];
    c.a = q.slot; c.ai = undefined; q.seat = "a"; q.crew = k; q.carrying = false; q.role = "mortar"; q.aiRole = "crew";
    have.crew.push(q); total++; stats.aiCrews++; aiStart(q);
  }
}
function aiStart(q) {
  const pawn = pawnOf(q.slot); let alive = false;
  try { alive = !!pawn && pawn.IsAlive(); } catch (e) {}
  if (alive && q.deployed) deploy(q, pawn);
}

// ------------------------------------------------------------------ AI mortar crew: one bot runs a tube alone, slowly
function tickAICrew(team, k, t) {
  const A = CONFIG.AI, c = crews[team][k], q = players.get(c.a);
  if (!q || !q.deployed || c.b >= 0) return;
  const st = c.ai || (c.ai = { state: "plot", at: t + A.CREW_THINK });
  if (t < st.at) return;
  const pawn = pawnOf(q.slot); let alive = false;
  try { alive = !!pawn && pawn.IsAlive(); } catch (e) {}
  if (!alive) { st.at = t + 1; return; }
  if (st.state === "plot") {
    const g = aiCrewTarget(team);
    if (!g) { st.at = t + A.CREW_THINK; return; }
    const E = CONFIG.TARGET_EXT - 1;
    c.target = { x: clampN(g.x + gauss() * A.CREW_SIGMA, -E, E), y: clampN(g.y + gauss() * A.CREW_SIGMA, -E, E) };
    st.state = c.loaded ? "fire" : "load"; st.at = t + (c.loaded ? 1 : A.CREW_LOAD * (0.8 + 0.4 * Math.random()));
  } else if (st.state === "load") {
    c.loaded = true; c.loader = -1; c.loaderGen = 0;
    st.state = "fire"; st.at = t + 1;
  } else {
    if (fireMortar(team, k, q.slot)) stats.aiShots++;
    st.state = "plot"; st.at = t + A.CREW_THINK + Math.random() * 3;
  }
}
// enemy infantry or crews out in the field (not flying, not in the briefing room): the one with the most others near him, as he stands now
function aiCrewTarget(team) {
  const A = CONFIG.AI, en = [];
  for (const q of players.values()) {
    if (q.team === team || !q.deployed || q.air || (q.role !== "infantry" && q.role !== "mortar")) continue;
    const pw = pawnOf(q.slot); if (!pw) continue;
    try { if (!pw.IsAlive()) continue; const o = pw.GetAbsOrigin(); if (o.z > CONFIG.BOTS.LOBBY_Z && Math.abs(o.x) < CONFIG.TARGET_EXT && Math.abs(o.y) < CONFIG.TARGET_EXT) en.push(o); } catch (e) {}
  }
  let best, bs = -1;
  for (const o of en) {
    let n = Math.random() * 0.5;
    for (const r of en) if (dist2(o, r) < A.CLUSTER_R) n++;
    if (n > bs) { bs = n; best = o; }
  }
  return best;
}

// ------------------------------------------------------------------ AI pilot: the stick for this tick (tickAir does the flying)
function aiStrafeTarget(a, enemy) {
  let best = -1, bd = CONFIG.AI.STRAFE_RANGE;
  for (const q of players.values()) {
    if (q.team !== enemy || !q.deployed || q.air) continue;
    const pw = pawnOf(q.slot); if (!pw) continue;
    try { if (!pw.IsAlive()) continue; const o = pw.GetAbsOrigin(); if (o.z < CONFIG.BOTS.LOBBY_Z) continue; const d = dist2(o, a.pos); if (d < bd) { bd = d; best = q.slot; } } catch (e) {}
  }
  return best;
}
function aiSteer(p, a, t) {
  const A = CONFIG.AI, enemy = enemyOf(p.team), side = enemy === CT ? 1 : -1;      // the enemy's trenches lie at x = side * 1649
  const ai = p.aiFly || (p.aiFly = { state: "patrol", wp: undefined, tgt: -1, tpos: undefined, until: 0, next: t + 3, think: 0, reactAt: 0, bombAt: 0 });
  if (t >= ai.think) {
    ai.think = t + A.THINK;
    if (ai.state === "attack") {
      const q = pawnOf(ai.tgt); let ok = false;
      try { ok = !!q && q.IsAlive() && q.GetTeamNumber() === enemy; if (ok) ai.tpos = q.GetAbsOrigin(); } catch (e) { ok = false; }
      const past = ai.tpos && (ai.tpos.x - a.pos.x) * a.f.x + (ai.tpos.y - a.pos.y) * a.f.y < 0 && dist2(a.pos, ai.tpos) > 700;
      if (!ok || t > ai.until || past) { ai.state = "patrol"; ai.next = t + A.ATTACK_COOLDOWN; ai.wp = undefined; }
    }
    if (ai.state === "patrol") {
      if (!ai.wp || dist2(a.pos, ai.wp) < A.ARRIVE) ai.wp = v3(side * (1500 + Math.random() * 900), (Math.random() * 2 - 1) * 2600, 0);
      if (t >= ai.next) {
        const s = aiStrafeTarget(a, enemy), pw = s >= 0 ? pawnOf(s) : undefined;
        if (pw) { stats.aiAttacks = (stats.aiAttacks || 0) + 1; ai.state = "attack"; ai.tgt = s; ai.tpos = pw.GetAbsOrigin(); ai.until = t + A.ATTACK_TIME; ai.reactAt = t + A.REACT; }
        else ai.next = t + 1;
      }
    }
  }
  const alt = a.pos.z - (a.gz === undefined ? 0 : a.gz);
  let aim, held = 0, pressed = 0, gunAt;
  if (ai.state === "attack" && ai.tpos) {
    // the mock pilots' attack profile: cruise, a shallow dive from 2200 u out, pull out low or once past him
    const q = ai.tpos, dx = q.x - a.pos.x, dy = q.y - a.pos.y, dz = q.z + 40 - a.pos.z, h = Math.hypot(dx, dy) || 1;
    const diving = h < 2200 && alt > 550 && -dz < h * 0.7 && a.f.x * dx + a.f.y * dy > 0;
    aim = diving ? v3(dx, dy, dz) : v3(dx, dy, clampN((A.CRUISE_ALT - alt) / 1500, -0.25, 0.35) * h);
    if (alt < 550 && !diving) aim = v3(dx, dy, h * 0.5);
    const d3 = Math.hypot(h, dz), cosA = vdot(a.f, vnorm(aim));
    if (t >= ai.reactAt && cosA > Math.cos(A.AIM_CONE * D2R) && d3 < A.GUN_MAX && alt > 200) {
      held |= CSInputs.ATTACK;
      const e = A.AIM_ERR * d3;
      gunAt = v3(q.x + gauss() * e, q.y + gauss() * e, q.z + 36 + gauss() * e * 0.5);
    }
    if (a.land && t >= ai.bombAt && Math.hypot(a.land.x - q.x, a.land.y - q.y) < A.BOMB_ERR) { pressed |= CSInputs.ATTACK2; ai.bombAt = t + 2.5; }
  } else {
    const w = ai.wp || v3(side * 1800, 0, 0), dx = w.x - a.pos.x, dy = w.y - a.pos.y, h = Math.hypot(dx, dy) || 1;
    aim = v3(dx, dy, clampN((A.CRUISE_ALT - alt) / 1500, -0.25, 0.35) * h);
  }
  if (alt < A.MIN_ALT || a.pullUp) aim = v3(a.f.x, a.f.y, 0.9);
  if (a.throttle < 0.7) held |= CSInputs.FORWARD;
  return { aim: vnorm(aim), held, pressed, gunAt };
}

// ------------------------------------------------------------------ infantry bots: where they deploy, the leash
// the deploy target of an infantry bot: an opened area (its sap head / ladder post, or a point inside it) for AREA_SHARE of the
// deploys while it has room, else a post: the fire trench (FIRE_SHARE) or the support trench, never beside a still-closed blocker
function aiPost(p, team, pawn) {
  const B = CONFIG.BOTS, sg = team === CT ? 1 : -1, yaw = team === CT ? 180 : 0;
  const open = CONFIG.UNLOCKS.filter((u) => unlocked.has(u.name) && B.AREAS[u.name]);
  if (open.length && Math.random() < B.AREA_SHARE) {
    const u = open[Math.floor(Math.random() * open.length)];
    let n = 0;
    for (const q of players.values()) if (q.bot && q.team === team && q.deployed && q !== p && q.anchor && q.anchor.area === u.name) n++;
    if (n < B.AREA_MAX) {
      let dest;
      const lock = (points.locks[u.name] || []).find((o) => Math.sign(o.x) === sg);
      if (lock && Math.random() < 0.5) dest = pickTrench(team, pawn, false, (s) => dist2(s.pos, lock) < 600);
      if (!dest || dist2(dest.pos, lock) >= 600) {
        const l = B.AREAS[u.name], a = l[Math.floor(Math.random() * l.length)];
        dest = { pos: v3(sg * a.x, a.y, a.z), ang: { pitch: 0, yaw, roll: 0 } };
      }
      p.anchor = { area: u.name, pos: dest.pos }; stats.botDeploys.area++;
      return dest;
    }
  }
  const fire = Math.random() < B.FIRE_SHARE;
  const dest = pickTrench(team, pawn, true, (s) => (Math.abs(s.pos.x) < 1900) === fire);
  if (dest) { p.anchor = { area: "", pos: dest.pos }; stats.botDeploys[Math.abs(dest.pos.x) < 1900 ? "fire" : "support"]++; }
  return dest;
}
// near a post (either side: a raid on the enemy trench is play), a dressing station or a point of an opened area
function nearAnchor(o) {
  const F = CONFIG.BOTS.FAR;
  for (const team of [T, CT]) {
    for (const s of points.trench[team] || []) if (dist2(o, s.pos) < F) return true;
    for (const h of points.heal[team] || []) if (dist2(o, h) < F) return true;
  }
  for (const u of CONFIG.UNLOCKS) {
    if (!unlocked.has(u.name)) continue;
    for (const a of CONFIG.BOTS.AREAS[u.name] || []) if (Math.hypot(Math.abs(o.x) - a.x, o.y - a.y) < F) return true;
  }
  return false;
}
function outOfPlay(p, o, t) {
  const B = CONFIG.BOTS;
  if (o.z < B.LOBBY_Z) return "lobby";
  if (Math.abs(o.x) < B.NML_X && Math.abs(o.y) < B.NML_Y && o.z > B.NML_ZMIN) return "nml";
  if (t - p.lastCombat < B.COMBAT_GRACE) return "";
  return nearAnchor(o) ? "" : "far";
}
function leashBack(p, pawn, team, why) {
  const dest = pickTrench(team, pawn, true);
  if (!dest) return;
  pawn.Teleport({ position: v3(dest.pos.x, dest.pos.y, dest.pos.z + 4), angles: dest.ang, velocity: v3(0, 0, 0) });
  p.anchor = { area: "", pos: dest.pos };
  stats.leash++; stats.botLeash[why]++;
}
// every tick for a live deployed bot out of the air: the blocker leash (cheap, per tick) and, once a CHECK, the out-of-play leash
function tickBot(p, pawn, team, dt) {
  if (p.role !== "infantry") { p.leashT = 0; p.outT = 0; return; }
  const o = pawn.GetAbsOrigin(), B = CONFIG.BOTS;
  if (nearLock(o)) {
    p.leashT = (p.leashT || 0) + dt;
    if (p.leashT >= B.LEASH_TIME) { p.leashT = 0; leashBack(p, pawn, team, "lock"); return; }
  } else p.leashT = 0;
  const t = now();
  if (t < p.checkAt) return;
  p.checkAt = t + B.CHECK;
  const why = outOfPlay(p, o, t);
  if (!why) { p.outT = 0; return; }
  p.outT += B.CHECK;
  if (p.outT >= B.OUT_TIME) { p.outT = 0; leashBack(p, pawn, team, why); }
}
// a bot that hurt or was hurt by an enemy is "in combat" for COMBAT_GRACE (the far leash waits)
function aiCombat(slot) { const q = players.get(slot); if (q && q.bot) q.lastCombat = now(); }
