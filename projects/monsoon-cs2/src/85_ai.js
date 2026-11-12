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
  // emplaced guns: one at a flag we hold (the front) before the ones at the base, and of those the one whose arc covers a flag (review 3:
  // the first T gun in the list faces the map edge, so the T AI gunner sat at it all round while the CT one covered flag D)
  const ours = (m) => { if (m.team === team) return 1; if (m.team) return 0; let f = null, bd = 1200; for (const q of flags) { const d = dist2(q.pos, m.pos); if (d < bd) { bd = d; f = q; } } return f && f.owner === team ? 2 : 0; };
  const covers = (m) => { let n = 0; for (const f of flags) { const d = dist2(f.pos, m.pos); if (d > 150 && d < CONFIG.AI.GUN_RANGE && Math.abs(wrap180(Math.atan2(f.pos.y - m.pos.y, f.pos.x - m.pos.x) * R2D - m.yaw0)) < m.cone) n++; } return n; };
  let best = null, bs = 0;
  for (const m of mounts) { if (m.user >= 0 || taken((g) => g.mount === m)) continue; const o = ours(m); if (!o) continue; const s = o + 0.4 * Math.min(2, covers(m)); if (s > bs) { bs = s; best = m; } }
  return best ? { heli: null, mount: best, tgt: null, since: 0, next: 0 } : null;
}
function tickDirector() {
  const A = CONFIG.AI;
  if (TNOW < directorAt) return;
  directorAt = TNOW + A.DIRECTOR_EVERY;
  for (const team of TEAMS) {
    const bots = [], have = { pilot: 0, gunner: 0, crew: 0 };
    // (a bot a human has taken over is his for now: no AI role for it, review 3)
    for (const q of players.values()) if (q.team === team && q.bot && q.role && !botTaken.has(q.slot)) { bots.push(q); if (q.aiRole) have[q.aiRole]++; }
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
      // an AI pilot whose helicopter was shot down takes a free one at once instead of waiting HELI.RESPAWN for his own (review 3:
      // a fifth of the AI pilot's round went on waiting for a new airframe while two others stood on their pads)
      for (const q of bots) {
        if (q.aiRole !== "pilot") continue;
        const own = ownHeli(q);
        if (own && own.state !== "dead" && own.state !== "crashing") continue;
        if (q.heli) continue;                                  // still aboard the one going down
        const list = helis[team].filter((h) => h.ent && h.owner < 0 && h.yieldTo < 0 && h.state === "parked" && h.seats[0].slot < 0 && dist2(h.pos, h.pad.pos) < CONFIG.HELI.PAD_RADIUS);
        const h = list.find((x) => x.M.ROCKETS > 0) || list[0];
        if (!h) continue;
        if (own) own.owner = -1;
        h.owner = q.slot; stats.aiHeliSwaps++;
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
      if (helis[team].some((h) => h.ent && h.owner < 0 && (h.yieldTo < 0 || h.yieldTo === q.slot))) handHeli(q, "A helicopter is free: it is yours");
    }
  }
}
// a helicopter the AI brought home (or one that came free) for a human who asked for one. In the briefing room or at the base he gets
// it at once (requestRole moves him to the pad, a short walk at most). Out in the field he is no longer teleported out of whatever he
// is doing (review 3): the helicopter is his and waits on its pad; he walks back to it, or deploys at it next life.
function handHeli(hq, msg) {
  hq.waitRole = "";
  const pawn = pawnOf(hq.slot);
  let up = false, pos = null; try { up = !!pawn && pawn.IsAlive(); if (up) pos = pawn.GetAbsOrigin(); } catch (e) {}
  const field = up && hq.deployed && !atBase(hq, pos);
  if (!field) { requestRole(hq, "air", true); if (hq.role === "air") toast(hq, msg, 4); return; }
  if (hq.board || hq.mount >= 0) unseat(hq, pawn, "role");       // (no plotting board out there; an emplaced gun is left)
  setRole(hq, "air", hq.team);                 // the helicopter is his (owner); he stays where he is, on foot or in a helicopter seat
  if (hq.role !== "air") return;
  hq.pref = "air"; stats.heliHeld++;
  const h = ownHeli(hq);
  toast(hq, (h ? "Your " + h.M.label : "Your helicopter") + " waits on its pad at the base (yours at your next deploy)", 6);
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

// ------------------------------------------------------------------ infantry bots: the team plan, where to deploy, the leash
// Review 3: the old choice scored every flag by its distance from the BASE plus noise and sent each bot to the single best one. Flags
// one hop from a held flag looked far (A is 6700 u from the CT base but 3000 from E), every bot of a side chased the same flag, and a
// flag behind the enemy's front (C) was never anyone's target: T won 75 % of bot-only rounds. Now each side keeps a plan, refreshed by
// the director: a weight per flag from what it is worth (defend a threatened flag, take a neutral or enemy one, keep a small garrison)
// and how far it is from the side's nearest deploy point (the base or a held flag: the front, not the base). Each deploying bot is
// given the flag the plan is shortest of (weight share x bots minus bots already sent there), so squads spread over the lanes and no
// flag is ignored. A side being bled pushes harder on the enemy flag nearest its front.
const plan = { 2: null, 3: null };
function frontCost(team, f) {
  const base = LAYOUT[tagOf(team)].centre;
  let d = Math.hypot(f.pos.x - base[0], f.pos.y - base[1]);
  for (const q of flags) if (q !== f && flagOpen(q, team)) d = Math.min(d, dist2(q.pos, f.pos));
  return d;
}
function threatened(f, team) { const e = otherTeam(team); return f.owner === team && (f.n[e] > 0 || (f.capTeam === e && f.prog > 0)); }
// how central a flag is (1 = the hub, the flag nearest on average to all the others: the bridge): a held hub is a deploy point one short
// run from every other flag, so it is worth more to both sides
let hubOf = null;
function hub(f) {
  if (!hubOf || hubOf.n !== flags.length || !hubOf.v[f.id]) {
    const m = {}; let lo = 1e9;
    for (const a of flags) { let s = 0; for (const b of flags) if (b !== a) s += dist2(a.pos, b.pos); m[a.id] = s / Math.max(1, flags.length - 1); lo = Math.min(lo, m[a.id]); }
    hubOf = { n: flags.length, v: {} };
    for (const a of flags) hubOf.v[a.id] = Math.pow(lo / m[a.id], CONFIG.AI.PLAN.HUB_EXP);
  }
  return hubOf.v[f.id];
}
function teamPlan(team) {
  const A = CONFIG.AI.PLAN, enemy = otherTeam(team);
  let mine = 0, theirs = 0;
  for (const f of flags) { if (f.owner === team) mine++; else if (f.owner === enemy) theirs++; }
  const bled = theirs >= CONFIG.CONQUEST.BLEED_FLAGS, w = {};
  let push = null, pc = 1e9;                                   // the enemy flag nearest our front
  for (const f of flags) if (f.owner === enemy) { const c = frontCost(team, f); if (c < pc) { pc = c; push = f; } }
  for (const f of flags) {
    let v;
    // pace: our run to the flag against the enemy's (each from its nearest deploy point other than this flag). Where the enemy's
    // reinforcements arrive first, a flag is only taken and held with more men: the slower side sends more (the bridge is 500 u
    // nearer the T front than the CT one)
    const ours = frontCost(team, f), pace = Math.pow(clampN(ours / Math.max(1, frontCost(enemy, f)), A.PACE_MIN, A.PACE_MAX), A.PACE);
    if (f.owner === team) v = threatened(f, team) ? A.DEFEND * (1 + f.prog) * pace : A.GARRISON;
    else {
      v = (f.owner === 0 ? A.NEUTRAL : A.ATTACK) * Math.exp(-ours / A.REACH) * pace;
      if (f === push) v *= bled ? A.BLEED_PUSH : A.PUSH;
      v = Math.max(v, A.FLOOR);
    }
    w[f.id] = v * (1 + A.HUB * hub(f));
  }
  // a flag with enemies close round it (more than SAFE_FRIEND x our men there) is no deploy point for a bot: it would appear in the
  // middle of a fight it is losing. A side being bled cannot wait for safe ground: it deploys forward anyway (SAFE_BLED radius). A side
  // with enough humans to run its vehicles and guns (no AI roles) uses SAFE_CROWD: there the bots are reinforcements for the humans'
  // fight, and keeping them off a contested flag left the humans' side short of men there (mixed matches went from 48 to 25-35 % T)
  const hot = {}, safe = !aiWanted(team) ? A.SAFE_CROWD : bled ? A.SAFE_BLED : A.SAFE;
  for (const f of flags) {
    let n = 0;
    if (f.owner === team && safe > 0) for (const r of roster) if (r.alive && !r.seated && r.p.deployed && dist2(r.pos, f.pos) < safe) { if (r.team === enemy) n++; else if (r.team === team) n -= A.SAFE_FRIEND; }
    hot[f.id] = n;
  }
  return { w, hot, at: TNOW, mine, theirs };
}
function botFlagOpen(f, team) { return flagOpen(f, team) && !(planFor(team).hot[f.id] > 0); }
function planFor(team) { let pl = plan[team]; if (!pl || TNOW - pl.at > CONFIG.AI.PLAN.EVERY) pl = plan[team] = teamPlan(team); return pl; }
// the flag this bot is sent to: the one the plan is most short of
function botGoal(p, team) {
  const pl = planFor(team), sent = {};
  let n = 1, sum = 0;
  for (const f of flags) { sent[f.id] = 0; sum += pl.w[f.id]; }
  for (const q of players.values()) {
    if (q === p || q.team !== team || !q.bot || q.aiRole || !q.deployed || !q.goal || sent[q.goal] === undefined) continue;
    const r = rosterAt[q.slot]; if (!r || !r.alive) continue;
    sent[q.goal]++; n++;
  }
  let best = null, bs = -1e9;
  for (const f of flags) {
    const s = pl.w[f.id] / sum * n - sent[f.id] + Math.random() * 0.3;
    if (s > bs) { bs = s; best = f; }
  }
  return best;
}
function botSpawnChoice(p, team) {
  const need = botGoal(p, team); if (!need) return "base";
  p.goal = need.id;
  let sel = "base";
  if (botFlagOpen(need, team)) sel = need.id;
  else {
    const base = LAYOUT[tagOf(team)].centre;
    let bd = Math.hypot(need.pos.x - base[0], need.pos.y - base[1]);
    for (const f of flags) { if (!botFlagOpen(f, team)) continue; const d = dist2(f.pos, need.pos); if (d < bd) { bd = d; sel = f.id; } }
  }
  const g = stats.botGoals[team] || (stats.botGoals[team] = {}), k = need.id + ">" + sel;
  g[k] = (g[k] || 0) + 1;
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
// the next flag to patrol: where the side's plan wants men (a threatened flag of ours, the enemy flag nearest our front), so the AI
// helicopter supports the infantry bots instead of touring the map at random (review 3)
// A flag inside the arc of an enemy-manned emplaced gun is a poor place to loiter (a .50 takes a helicopter apart in seconds): its
// weight is cut to MOUNT_AVOID (review 3: once the AI gunners chose guns that cover flags, mounts became the first killer of AI
// helicopters)
function mountCovers(f, team) {
  for (const m of mounts) {
    if (m.user < 0) continue;
    const q = players.get(m.user); if (!q || q.team === team) continue;
    const d = dist2(f.pos, m.pos);
    if (d < CONFIG.AI.GUN_RANGE && Math.abs(wrap180(Math.atan2(f.pos.y - m.pos.y, f.pos.x - m.pos.x) * R2D - m.yaw0)) < m.cone + 10) return true;
  }
  return false;
}
function aiWaypoint(h, ai) {
  const pl = planFor(h.team);
  let best, bs = -1;
  for (const f of flags) {
    if (f.id === ai.wp) continue;
    const s = (pl.w[f.id] + 0.15 + (f.contested ? 1 : 0)) * (0.4 + Math.random()) * (mountCovers(f, h.team) ? CONFIG.AI.MOUNT_AVOID : 1);
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
      if (hq && !hq.bot && hq.team === h.team && h.owner < 0) handHeli(hq, "Your helicopter is on the pad");
      return;
    }
    if (padD > H.PAD_RADIUS) { ai.state = "takeoff"; return; }           // put down away from home: go again
    // repaired and most rockets back: go (review 3: waiting for the last pair kept the Apache 50 s on the pad every sortie)
    if (h.hp >= h.maxHp && h.rockets >= Math.min(h.M.ROCKETS, 2 * Math.ceil(h.M.ROCKETS * A.REARM_GO / 2)) && TNOW - ai.since > A.PAD_HOLD) ai.state = "takeoff";
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
  // on the pad the rotor keeps turning (a hot turn-round: no spool-down and spool-up every sortie) while the pad works on the airframe;
  // it spools down only when the pilot is about to hand over or quit
  if (ai.state === "pad") { if (!ai.release) h.inp = { fwd: 0, side: 0, coll: 0, yaw: h.yaw, fire: false, aim: null, spread: 0 }; return; }
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
