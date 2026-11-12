// ------------------------------------------------------------------ 85_ai: bots for low population
// CS2 bots are players with their own legs and guns; a script cannot path them. So:
//  - infantry bots are PLACED: they deploy at the held flag nearest the flag their team most needs, and a leash re-deploys a bot that
//    stood still too long (stuck / idle) or left the playable band;
//  - when a team has fewer humans than AI.MIN_HUMANS_FOR_ROLES some bots get a role the script drives completely while their pawn sits
//    in the seat: AI pilot (patrol between flags, rocket runs, back to the pad when hurt), AI gunner (door / chin / emplaced gun), AI crew
//    (answers fire missions, marks enemy clusters). They are slow and inaccurate on purpose and give their seat to any human who asks.
let directorAt = 0;
function aiWanted(team) { return CONFIG.BOTS_ON && humansOn(team) < CONFIG.AI.MIN_HUMANS_FOR_ROLES; }
function aiRelease(q, redeploy) {
  const pawn = pawnOf(q.slot);
  q.aiRole = ""; q.aiGun = null;
  if (q.heli && q.heli.seats[0].slot === q.slot) q.heli.ai = null;
  unseat(q, pawn, "role");
  if (q.role === "artillery") { const g = guns[q.team] && guns[q.team][q.crew]; if (g) { g.ai = null; g.extraSigma = 0; } leaveCrew(q); }
  leaveHeliRole(q);
  q.role = "infantry";
  if (pawn) freeze(q, pawn, false);
  let alive = false; try { alive = !!pawn && pawn.IsAlive(); } catch (e) {}
  if (redeploy && alive && q.deployed) deploy(q, pawn);
}
function aiGunSpot(team) {
  const taken = (pred) => { for (const q of players.values()) if (q.aiRole === "gunner" && q.aiGun && pred(q.aiGun)) return true; return false; };
  for (const h of helis[team]) {
    if (!h.ent || h.owner < 0) continue;
    const gi = h.seats.findIndex((s) => s.kind === "gunner");
    if (gi < 0 || h.seats[gi].slot >= 0 || taken((g) => g.heli === h)) continue;
    return { heli: h, mount: null, tgt: null, since: 0, next: 0 };
  }
  // emplaced guns: one at a flag we hold (the front) before the ones at the base
  const ours = (m) => { if (m.team === team) return 1; if (m.team) return 0; let f = null, bd = 1200; for (const q of flags) { const d = dist2(q.pos, m.pos); if (d < bd) { bd = d; f = q; } } return f && f.owner === team ? 2 : 0; };
  let best = null, bs = 0;
  for (const m of mounts) { if (m.user >= 0 || taken((g) => g.mount === m)) continue; const s = ours(m); if (s > bs) { bs = s; best = m; } }
  return best ? { heli: null, mount: best, tgt: null, since: 0, next: 0 } : null;
}
function tickDirector() {
  const A = CONFIG.AI;
  if (TNOW < directorAt) return;
  directorAt = TNOW + A.DIRECTOR_EVERY;
  for (const team of TEAMS) {
    const bots = [], have = { pilot: 0, gunner: 0, crew: 0 };
    for (const q of players.values()) if (q.team === team && q.bot && q.role) { bots.push(q); if (q.aiRole) have[q.aiRole]++; }
    if (!aiWanted(team)) {
      for (const q of bots) {
        if (!q.aiRole) continue;
        if (q.aiRole === "pilot") { const h = ownHeli(q); if (h && h.state === "flying") { if (h.ai) h.ai.quit = true; continue; } }
        aiRelease(q, true);
      }
    } else {
      const cap = Math.floor(bots.length * A.MAX_ROLE_SHARE);
      let total = have.pilot + have.gunner + have.crew;
      const free = () => bots.find((q) => !q.aiRole && !q.deployed) || bots.find((q) => !q.aiRole && q.role === "infantry" && !q.heli && q.mount < 0);
      while (have.pilot < A.PILOTS && total < cap) {
        const list = helis[team].filter((h) => h.ent && h.owner < 0 && h.yieldTo < 0);
        const h = list.find((x) => x.M.ROCKETS > 0 && x.state !== "dead") || list.find((x) => x.state !== "dead") || list[0];
        const q = free(); if (!h || !q) break;
        h.owner = q.slot; q.aiRole = "pilot"; setRole(q, "air", team);
        if (q.role !== "air") { q.aiRole = ""; h.owner = -1; break; }
        have.pilot++; total++; stats.aiPilots++; aiStart(q);
      }
      while (have.crew < A.CREWS && total < cap) {
        const g = guns[team].find((x) => x.crew.length === 0), q = free(); if (!g || !q) break;
        g.crew.push(q.slot); q.crew = g.k; q.role = "artillery"; q.aiRole = "crew";
        have.crew++; total++; stats.aiCrews++; aiStart(q);
      }
      while (have.gunner < A.GUNNERS && total < cap) {
        const spot = aiGunSpot(team), q = free(); if (!spot || !q) break;
        q.aiRole = "gunner"; q.aiGun = spot;
        have.gunner++; total++; stats.aiGunners++; aiStart(q);
      }
      // seated again after a respawn / a new helicopter
      for (const q of bots) {
        if (!q.aiRole || q.aiRole === "crew" || q.heli || q.mount >= 0 || !q.deployed) continue;
        const r = rosterAt[q.slot]; if (r && r.alive) aiSeatTry(q, r.pawn);
      }
    }
    // a human waiting for a helicopter the AI was flying
    for (const q of players.values()) {
      if (q.team !== team || q.bot || q.waitRole !== "air" || q.role === "air") continue;
      if (helis[team].some((h) => h.ent && h.owner < 0 && (h.yieldTo < 0 || h.yieldTo === q.slot))) { q.waitRole = ""; requestRole(q, "air", true); if (q.role === "air") toast(q, "A helicopter is free: it is yours", 4); }
    }
  }
}
function aiStart(q) { const r = rosterAt[q.slot]; if (r && r.alive && q.deployed) deploy(q, r.pawn); }
function aiSeatTry(p, pawn) {
  if (p.aiRole === "pilot") {
    const h = ownHeli(p);
    if (!h || h.state !== "parked" || h.seats[0].slot >= 0) return false;
    if (!enterHeli(p, pawn, h, 0)) return false;
    h.ai = { state: "pad", since: TNOW, think: 0, goal: v3(h.pos.x, h.pos.y, h.pos.z), wp: "", target: null, reactAt: 0, rocketsAt: 0, attackAt: 0, nextStrafe: TNOW + 10,
             release: false, quit: false, blocked: 0, land: false, yawGoal: h.yaw, alt: CONFIG.AI.CRUISE };
    return true;
  }
  if (p.aiRole === "gunner" && p.aiGun) {
    const g = p.aiGun;
    if (g.heli) {
      const h = g.heli, gi = h.seats.findIndex((s) => s.kind === "gunner");
      if (h.state !== "parked" || h.owner < 0 || gi < 0 || h.seats[gi].slot >= 0) return false;
      return enterHeli(p, pawn, h, gi);
    }
    if (g.mount) return g.mount.user < 0 ? takeMount(p, pawn, g.mount) : false;
  }
  return false;
}
function aiDeploy(p, pawn) {
  if (p.aiRole === "crew") {
    const g = guns[p.team][p.crew];
    if (!g) { aiRelease(p, false); return; }
    place(pawn, g.seat);
    freeze(p, pawn, true);                               // stays at its gun (it still shoots at what comes close)
    if (!g.ai) g.ai = { state: "idle", at: TNOW + CONFIG.AI.CREW_THINK };
    g.extraSigma = CONFIG.AI.CREW_EXTRA_SIGMA;
    return;
  }
  if (p.aiRole === "pilot" && !ownHeli(p)) { aiRelease(p, false); return; }
  aiSeatTry(p, pawn);
}

// ------------------------------------------------------------------ infantry bots: where to deploy, the leash
function neededFlag(team) {
  const base = LAYOUT[tagOf(team)].centre, enemy = otherTeam(team);
  let best, bs = -1e9;
  for (const f of flags) {
    let s = -Math.hypot(f.pos.x - base[0], f.pos.y - base[1]) / 4000;
    if (f.owner === team) s += (f.n[enemy] > 0 || (f.capTeam === enemy && f.prog > 0)) ? 4 : -6;     // defend one under attack
    else s += f.owner === 0 ? 2 : 1.5;
    s += Math.random() * 1.2;
    if (s > bs) { bs = s; best = f; }
  }
  return best;
}
function botSpawnChoice(p, team) {
  const need = neededFlag(team); if (!need) return "base";
  if (flagOpen(need, team)) return need.id;
  const base = LAYOUT[tagOf(team)].centre;
  let sel = "base", bd = Math.hypot(need.pos.x - base[0], need.pos.y - base[1]);
  for (const f of flags) { if (!flagOpen(f, team)) continue; const d = dist2(f.pos, need.pos); if (d < bd) { bd = d; sel = f.id; } }
  return sel;
}
// the bot AT man: CS2's bot brain would only use the Zeus as a Zeus, so the script fires the launcher for him, at helicopters only
function botAT(p, pawn, pos) {
  const A = CONFIG.AI, K = CONFIG.AT;
  if (p.kit !== "at" || p.role !== "infantry" || TNOW < p.atReadyAt) return;
  p.atReadyAt = TNOW + A.AT_EVERY;                          // look again in a second
  const from = v3(pos.x, pos.y, pos.z + 60);
  let best = null, bd = A.AT_RANGE;
  for (const h of helis[otherTeam(p.team)]) { if (h.state !== "flying" || !h.ent) continue; const d = dist3(from, heliCentre(h)); if (d < bd) { bd = d; best = h; } }
  if (!best) return;
  const t = bd / K.SPEED, c = heliCentre(best), aim = v3(c.x + best.vel.x * t, c.y + best.vel.y * t, c.z + best.vel.z * t + 0.5 * K.GRAVITY * t * t);
  let tr; try { tr = Instance.TraceLine({ start: from, end: c, ignoreEntity: hitIgnore, ignorePlayers: true }); } catch (e) {}
  if ((tr && tr.didHit && tr.fraction < 0.97) || smokeBlocks(from, c)) return;
  const d0 = vnorm(vsub(aim, from)), s = A.AT_SPREAD, dir = vnorm(v3(d0.x + gauss() * s, d0.y + gauss() * s, d0.z + gauss() * s));
  p.atReadyAt = TNOW + K.RELOAD;
  launchRocket({ pos: vadd(from, dir, 40), vel: vscale(dir, K.SPEED), team: p.team, slot: p.slot, grav: K.GRAVITY, blast: K.BLAST, damage: K.DAMAGE,
                 heli: K.HELI, life: K.LIFE, gunRadius: K.GUN_DISABLE, src: "at" });
  stats.botRockets++;
}
function tickBot(p, pawn, pos) {
  const A = CONFIG.AI;
  if (!p.aiRole && p.kit === "at") botAT(p, pawn, pos);
  if (p.aiRole || TNOW < p.leashAt) return;
  p.leashAt = TNOW + A.LEASH_CHECK;
  if (!p.leashPos || dist2(pos, p.leashPos) > A.LEASH_MOVE) { p.leashPos = pos; p.leashMoved = TNOW; }
  const out = !inBand(pos, A.BAND_MARGIN) || pos.z < WATER_Z - A.BAND_Z_UNDER;
  let busy = TNOW - p.lastCombat < A.COMBAT_GRACE;
  if (!busy && p.here) { const f = flagById(p.here); busy = !!f && (f.owner !== p.team || f.prog > 0 || f.contested); }
  if (!out && (busy || TNOW - p.leashMoved <= A.LEASH_IDLE)) return;
  stats.leash++;
  place(pawn, spawnPoint(p, p.team));
  p.leashPos = null; p.leashMoved = TNOW;
}

// ------------------------------------------------------------------ AI gunner (helicopter gun seat or emplaced gun)
function aiPickTarget(origin, centreYaw, cone, up, down, team) {
  const A = CONFIG.AI;
  let best = null, bd = A.GUN_RANGE;
  const test = (c, id) => {
    const d = dist3(origin, c); if (d >= bd || d < 1) return;
    const a = angOf(vscale(vsub(c, origin), 1 / d));
    if (Math.abs(wrap180(a.yaw - centreYaw)) > cone || a.pitch < -up || a.pitch > down) return;
    bd = d; best = { pos: c, id };
  };
  for (const r of roster) { if (r.alive && r.team !== team && r.team >= 2 && !r.seated && r.p.deployed) test(v3(r.pos.x, r.pos.y, r.pos.z + 40), r.slot); }
  for (const h of allHelis) { if (h.team !== team && (h.state === "flying" || h.state === "crashing")) test(heliCentre(h), 100 + h.team * 10 + h.n); }
  if (!best) return null;
  if (best.id < 100) {
    let tr; try { tr = Instance.TraceLine({ start: origin, end: best.pos, ignoreEntity: hitIgnore, ignorePlayers: true }); } catch (e) {}
    if (tr && tr.didHit && tr.fraction < 0.97) return null;
  }
  if (smokeBlocks(origin, best.pos)) return null;
  return best;
}
// returns { eye, firing } for this tick: reaction delay after a new target, bursts with pauses, the aim point only refreshed at RETARGET
function aiGunner(g, origin, centreYaw, cone, up, down, team) {
  const A = CONFIG.AI;
  if (TNOW >= g.next) {
    g.next = TNOW + A.GUN_RETARGET;
    const t = aiPickTarget(origin, centreYaw, cone, up, down, team);
    if (!t) g.tgt = null;
    else { if (!g.tgt || g.tgt.id !== t.id) g.since = TNOW; g.tgt = t; }
  }
  if (!g.tgt) return { eye: { pitch: 0, yaw: centreYaw, roll: 0 }, firing: false };
  const el = TNOW - g.since - A.GUN_REACT;
  return { eye: angOf(vnorm(vsub(g.tgt.pos, origin))), firing: el >= 0 && el % (A.GUN_BURST + A.GUN_PAUSE) < A.GUN_BURST };
}
function tickAISeat(p, pawn, dt) {
  const h = p.heli, s = h.seats[p.seat];
  if (!h.ent || h.state === "dead") { leaveHeli(p, pawn, ""); return; }
  if (s.kind === "gunner" && p.aiGun) {
    const G = h.M.GUN, a = aiGunner(p.aiGun, local(heliOrigin(h), h.B, G.muzzle), h.yaw + G.yaw, G.cone, G.up, G.down, p.team);
    tickHeliGun(h, pawn, p.team, a.eye, a.firing, dt, CONFIG.AI.GUN_SPREAD);
    if (a.firing) stats.aiGunTicks++;
  } else if (s.kind !== "pilot" && h.landed && !p.aiRole) leaveHeli(p, pawn, "");
}
function tickAIMount(p, pawn, dt) {
  const m = mounts[p.mount], C = CONFIG.MOUNT;
  if (!m || m.user !== p.slot || !p.aiGun) { leaveMount(p, pawn); return; }
  const a = aiGunner(p.aiGun, m.pos, m.yaw0, m.cone, C.UP, C.DOWN, p.team);
  mountAim(m, a.eye, a.firing, pawn, p.team, dt, CONFIG.AI.GUN_SPREAD);
  if (a.firing) stats.aiGunTicks++;
}

// ------------------------------------------------------------------ AI pilot
function aiWaypoint(h, ai) {
  const enemy = otherTeam(h.team);
  let best, bs = -1;
  for (const f of flags) {
    if (f.id === ai.wp) continue;
    const s = (f.contested ? 3 : f.owner === enemy ? 2.5 : f.owner === 0 ? 2 : 1) * (0.4 + Math.random());
    if (s > bs) { bs = s; best = f; }
  }
  if (!best) return;
  ai.wp = best.id;
  ai.goal = v3(best.pos.x + (Math.random() - 0.5) * 700, best.pos.y + (Math.random() - 0.5) * 700, best.pos.z);
}
function aiStrafeTarget(h) {
  const A = CONFIG.AI;
  let best = null, bd = A.STRAFE_RANGE;
  for (const r of roster) {
    if (!r.alive || r.team === h.team || r.team < 2 || r.seated || !r.p.deployed) continue;
    const d = dist2(r.pos, h.pos); if (d >= bd) continue;
    let near = false;
    for (const f of flags) if (dist2(f.pos, r.pos) < A.CLUSTER_FLAG) { near = true; break; }
    if (!near) continue;
    bd = d; best = { slot: r.slot, pos: v3(r.pos.x, r.pos.y, r.pos.z) };
  }
  return best;
}
function aiPilotThink(h, ai) {
  const A = CONFIG.AI, H = CONFIG.HELI, bot = players.get(h.seats[0].slot);
  // home and out: the director wants the seat back (quit, kept), or a human is waiting for this helicopter (only while he still is:
  // a request withdrawn or a waiting player who left no longer sends the AI home to quit for nobody, review 2)
  ai.release = !!ai.quit || h.yieldTo >= 0;
  const hurtNow = h.hp < A.RTB_HP || (h.M.ROCKETS > 0 && h.rockets < 2);
  const padD = dist2(h.pos, h.pad.pos);
  if (ai.state === "pad") {
    if (!h.landed) { ai.state = "patrol"; aiWaypoint(h, ai); return; }
    if (ai.release) {
      const to = h.yieldTo; h.yieldTo = -1;
      if (bot) aiRelease(bot, true);
      const hq = players.get(to);
      if (hq && !hq.bot && hq.team === h.team && h.owner < 0) { hq.waitRole = ""; requestRole(hq, "air", true); if (hq.role === "air") toast(hq, "Your helicopter is on the pad", 4); }
      return;
    }
    if (padD > H.PAD_RADIUS) { ai.state = "takeoff"; return; }           // put down away from home: go again
    if (h.hp >= h.maxHp && h.rockets >= h.M.ROCKETS && TNOW - ai.since > A.PAD_HOLD) ai.state = "takeoff";
    return;
  }
  if (ai.state === "takeoff") {
    ai.goal = v3(h.pos.x, h.pos.y, h.pos.z); ai.land = false;
    if (!h.landed && h.alt > A.CRUISE * 0.5) { ai.state = hurtNow && padD > H.PAD_RADIUS ? "rtb" : "patrol"; aiWaypoint(h, ai); }
    return;
  }
  if (ai.state === "patrol") {
    if (hurtNow || ai.release) { ai.state = "rtb"; return; }
    if (h.M.ROCKETS > 0 && TNOW >= ai.nextStrafe) {
      const t = aiStrafeTarget(h);
      if (t) { ai.state = "attack"; ai.target = t; ai.reactAt = TNOW + A.REACT; ai.rocketsAt = h.rockets; ai.attackAt = TNOW; return; }
    }
    if (dist2(h.pos, ai.goal) < A.ARRIVE) aiWaypoint(h, ai);
    return;
  }
  if (ai.state === "attack") {
    const r = ai.target ? rosterAt[ai.target.slot] : null;
    if (r && r.alive && r.team !== h.team) ai.target.pos = v3(r.pos.x, r.pos.y, r.pos.z);
    const d = ai.target ? dist2(h.pos, ai.target.pos) : 0;
    const fired = (ai.rocketsAt - h.rockets) / 2;
    if (hurtNow || ai.release || !ai.target || !r || !r.alive || fired >= A.STRAFE_PAIRS || d < A.STRAFE_FIRE_MIN * 0.8 || TNOW - ai.attackAt > 25) {
      ai.state = hurtNow || ai.release ? "rtb" : "patrol"; ai.target = null; ai.nextStrafe = TNOW + A.STRAFE_COOLDOWN; aiWaypoint(h, ai);
      if (fired > 0) stats.aiStrafes++;
      return;
    }
    ai.goal = v3(ai.target.pos.x, ai.target.pos.y, ai.target.pos.z);
    return;
  }
  if (ai.state === "rtb") {
    ai.goal = v3(h.pad.pos.x, h.pad.pos.y, h.pad.pos.z); ai.land = false;
    if (padD < 90 && h.speed < 120) ai.state = "land";
    return;
  }
  if (ai.state === "land") {
    ai.goal = v3(h.pad.pos.x, h.pad.pos.y, h.pad.pos.z); ai.land = true;
    if (padD > 260) { ai.state = "rtb"; ai.land = false; }
    if (h.landed) { ai.state = "pad"; ai.since = TNOW; ai.land = false; stats.aiLandings++; }
  }
}
// every tick: the stick positions that take the helicopter toward ai.goal (the same inputs a human pilot has)
function tickAIPilot(h, dt) {
  const A = CONFIG.AI, H = CONFIG.HELI, ai = h.ai;
  const bot = players.get(h.seats[0].slot);
  if (!bot || !bot.bot || bot.aiRole !== "pilot") { h.ai = null; return; }
  if (h.state !== "parked" && h.state !== "flying") return;
  if (TNOW >= ai.think) { ai.think = TNOW + 0.25; aiPilotThink(h, ai); if (!h.ai) return; }
  if (ai.state === "pad") return;                                            // rotor spools down, the pad works on the airframe
  const inp = { fwd: 0, side: 0, coll: 0, yaw: h.yaw, fire: false, aim: null, spread: A.ROCKET_SPREAD };
  if (ai.state === "takeoff") { inp.coll = 1; h.inp = inp; return; }
  const dx = ai.goal.x - h.pos.x, dy = ai.goal.y - h.pos.y, d = Math.hypot(dx, dy) || 1e-6;
  const attack = ai.state === "attack" && !!ai.target;
  // speed toward the goal, slowing in; an attack run holds off at firing distance
  let sp = Math.min(H.V_FWD * A.CRUISE_SPEED, d * 0.6);
  if (attack) sp = d > A.STRAFE_FIRE_MAX * 0.8 ? H.V_FWD * A.CRUISE_SPEED : H.V_FWD * 0.25;
  const vx = dx / d * sp, vy = dy / d * sp, cy = Math.cos(h.yaw * D2R), sy = Math.sin(h.yaw * D2R);
  inp.fwd = clampN((vx * cy + vy * sy) / H.V_FWD, -1, 1);
  inp.side = clampN((vx * sy - vy * cy) / H.V_SIDE, -1, 1);
  if (d > 250) inp.yaw = Math.atan2(dy, dx) * R2D; else if (ai.land || ai.state === "rtb") inp.yaw = h.pad.yaw;
  // height: over the ground guessed ahead (and the real ground below), down the last metres over the pad
  const la = A.LOOKAHEAD;
  let floor = Math.max(h.gz, approxGround(h.pos.x, h.pos.y), approxGround(h.pos.x + h.vel.x * la * 0.5, h.pos.y + h.vel.y * la * 0.5), approxGround(h.pos.x + h.vel.x * la, h.pos.y + h.vel.y * la));
  let wantZ = floor + (attack ? A.STRAFE_ALT : A.CRUISE);
  if (ai.state === "rtb" && d < 500) wantZ = Math.max(h.gz, h.pad.pos.z) + 200;
  if (ai.land) inp.coll = d < 110 && h.speed < 110 ? -0.6 : clampN((h.pad.pos.z + 160 - h.pos.z) / 150, -0.6, 0.6);
  else inp.coll = clampN((wantZ - h.pos.z) / 150, -0.7, 1);
  // something solid ahead that the guess missed (trees, a tower): climb and slow
  if ((h.tick & 7) === 0 && h.speed > 80) {
    const c = v3(h.pos.x, h.pos.y, h.pos.z + H.BODY_UP), dir = vnorm(v3(h.vel.x, h.vel.y, 0));
    let tr; try { tr = Instance.TraceLine({ start: c, end: vadd(c, dir, h.speed * 2 + 300), ignoreEntity: hitIgnore, ignorePlayers: true }); } catch (e) {}
    if (tr && tr.didHit) ai.blocked = TNOW + 1.2;
  }
  if (TNOW < ai.blocked && !ai.land) { inp.coll = 1; inp.fwd *= 0.15; inp.side *= 0.15; }
  else if (!ai.land && h.pos.z < floor + 120) { inp.fwd *= 0.3; inp.side *= 0.3; }
  if (attack) {
    const t = ai.target.pos;
    inp.yaw = Math.atan2(t.y - h.pos.y, t.x - h.pos.x) * R2D;
    if (TNOW >= ai.reactAt && d < A.STRAFE_FIRE_MAX && d > A.STRAFE_FIRE_MIN && Math.abs(wrap180(inp.yaw - h.yaw)) < A.AIM_YAW && !h.landed) {
      inp.fire = true;
      inp.aim = vnorm(vsub(v3(t.x, t.y, t.z + 30), heliCentre(h)));
    }
  }
  h.inp = inp;
}

// ------------------------------------------------------------------ AI battery crew: one bot runs a gun, slowly
function aiCrewTarget(g) {
  const A = CONFIG.AI, team = g.team;
  let m = null;
  for (const q of missions[team]) if (!q.shot && TNOW - q.at > 2 && (!m || q.at < m.at)) m = q;
  if (m) return { x: m.x, y: m.y, z: m.z, id: m.id };
  // enemies bunched near a flag: marked where they are now, the shell lands later
  let best = null, bn = A.CLUSTER_MIN - 1;
  for (const r of roster) {
    if (!r.alive || r.team === team || r.team < 2 || r.seated || !r.p.deployed || TNOW - r.p.deployedAt < A.MARK_AGE) continue;
    let nearFlag = false; for (const f of flags) if (dist2(f.pos, r.pos) < A.CLUSTER_FLAG) { nearFlag = true; break; }
    if (!nearFlag) continue;
    let n = 0; for (const o of roster) if (o.alive && o.team === r.team && !o.seated && o.p.deployed && dist2(o.pos, r.pos) < A.CLUSTER_RADIUS) n++;
    if (n > bn) { bn = n; best = r; }
  }
  if (best) return { x: best.pos.x, y: best.pos.y, z: best.pos.z, id: -1 };
  const fl = flashes[team].filter((f) => TNOW >= f.from);
  if (fl.length && Math.random() < 0.35) { const f = pick(fl); return { x: f.x, y: f.y, z: f.z, id: -1 }; }
  return null;
}
function tickAICrew(g) {
  const A = CONFIG.AI, ai = g.ai;
  if (!ai || TNOW < ai.at || gunDisabled(g)) return;
  let botSlot = -1;
  for (const s of g.crew) { const q = players.get(s); if (!q) continue; if (!q.bot) { g.extraSigma = 0; return; } if (q.aiRole === "crew") botSlot = s; }   // a human on the gun runs it, with his own aim
  g.extraSigma = A.CREW_EXTRA_SIGMA;
  const r = botSlot >= 0 ? rosterAt[botSlot] : null;
  if (!r || !r.alive || !r.p.deployed) { ai.at = TNOW + 1; return; }
  if (ai.state === "idle") {
    const t = aiCrewTarget(g);
    if (!t) { ai.at = TNOW + A.CREW_THINK; return; }
    setTarget(g, t, t.id);
    ai.state = "load"; ai.at = TNOW + A.CREW_LOAD * (0.8 + 0.4 * Math.random());
  } else if (ai.state === "load") {
    const type = g.team === T ? "rocket" : "he";
    while (g.loaded.length < (g.team === T ? 2 : 1)) g.loaded.push(type);
    g.loader = botSlot;
    ai.state = "fire"; ai.at = Math.max(TNOW + 0.5, g.layEnd + 0.3);
  } else {
    if (!fireBlock(g)) { fireGun(g, botSlot); stats.aiShots++; }
    else if (!g.target) g.loaded.length = Math.min(g.loaded.length, CONFIG.ARTY.MAX_LOAD[g.team]);
    ai.state = "idle"; ai.at = TNOW + A.CREW_THINK + Math.random() * 3;
  }
}
