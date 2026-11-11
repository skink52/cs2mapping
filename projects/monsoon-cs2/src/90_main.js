// ------------------------------------------------------------------ 90_main: think loop, per-player tick, events, chat, damage guard
const stats = { rounds: 0, gunShots: 0, rockets: 0, fired: 0, shells: 0, beehive: 0, missions: 0, captures: 0, flights: 0, landings: 0, heliLost: 0, heliDamage: 0, gunsDisabled: 0,
                repairs: 0, mountUses: 0, leash: 0, blocked: 0, aiPilots: 0, aiGunners: 0, aiCrews: 0, aiShots: 0, aiStrafes: 0, aiLandings: 0, aiGunTicks: 0,
                ticks: 0, ms: 0, msMax: 0,
                // review pass 1: what happened, by source and by feature (the mock's coverage table and test/sim_balance.mjs read these)
                killsBy: {}, killsOn: {}, deaths: 0, heliDmgBy: {}, heliLostBy: {}, heliLives: [], gunsDisabledBy: {}, capturesBy: {}, results: [],
                feed: 0, smokeBlocked: 0, smokes: 0, beltReloads: 0, rocketHeliHits: 0, heliGuard: 0, padRepairs: 0, padRearms: 0, recalls: 0, ditched: 0,
                hardLandings: 0, crashLandings: 0, softWall: 0, wrecksCleared: 0, ropes: 0, jumps: 0, beehiveShots: 0, shellHits: 0, missionShells: 0, missionHits: 0,
                flashes: 0, foAssists: 0, kitDenied: 0, flagSpawns: 0, spawnAboard: 0, spawnGuard: 0, afk: 0, joins: 0, lateJoins: 0, perfLines: 0, sanitised: 0,
                teamSwitches: 0, reloads: 0, roleDeferred: 0, botRockets: 0, heliLostTeam: { 2: 0, 3: 0 }, bleedOn: { 2: 0, 3: 0 }, crashSurvivors: 0 };
let roster = [];
const rosterAt = new Array(64).fill(null);
let lastTick = 0, perfAt = 0, perfTicks = 0, perfMs = 0, perfMax = 0, tickNo = 0;
const clock = typeof performance !== "undefined" && performance && typeof performance.now === "function" ? () => performance.now() : () => Date.now();
try { globalThis.__mvDebug = { VERSION, CONFIG, players, helis, guns, flags, game, stats, missions, flashes, shells, rockets, mounts, smokes,
                               fn: { fireGun, setTarget, damageHeli, disableGun, callMission, feed, flagOpen, spawnChoices } }; } catch (e) {}

// forget what a player was sitting in without touching a pawn (death, respawn, disconnect, the slot changing hands)
function dropSeats(p) {
  if (p.heli) { const s = p.heli.seats[p.seat]; if (s && s.slot === p.slot) s.slot = -1; if (p.seat === 0) p.heli.ai = null; p.heli = null; p.seat = -1; }
  if (p.mount >= 0) { const m = mounts[p.mount]; if (m && m.user === p.slot) m.user = -1; p.mount = -1; }
  if (p.board) { const g = guns[p.team] && guns[p.team][p.crew]; if (g && g.aimer === p.slot) g.aimer = -1; p.board = false; }
  restoreCamera(p);
  dropCarry(p);
  p.holdKind = ""; p.holdT = 0; p.ropeUntil = 0;
}
// out of everything a side owns: seats, AI role, gun crew, helicopter, fire missions (a team change, spectating, leaving)
function leaveTeam(p, pawn) {
  let alive = false; try { alive = !!pawn && pawn.IsAlive(); } catch (e) {}
  if (alive) unseat(p, pawn, "role");
  if (p.aiRole) {
    if (alive) aiRelease(p, false);
    else { const g = guns[p.team] && guns[p.team][p.crew]; if (p.aiRole === "crew" && g) { g.ai = null; g.extraSigma = 0; } p.aiRole = ""; p.aiGun = null; }
  }
  dropSeats(p);
  leaveCrew(p);
  if (p.team) leaveHeliRole(p);
  for (const team of TEAMS) for (let i = missions[team].length - 1; i >= 0; i--) if (missions[team][i].owner === p.slot) dropMission(team, i);
  if (alive) { hidePawn(p, pawn, false); freeze(p, pawn, false); }
  p.role = null; p.team = 0; p.deployed = false; p.kit = "rifle"; p.kitNext = ""; p.spawnSel = "base"; p.waitRole = ""; p.afk = false; p.here = "";
}
function forgetPlayer(p) {
  leaveTeam(p, undefined);
  players.delete(p.slot);
}
function buildRoster() {
  roster = [];
  for (let s = 0; s < 64; s++) {
    rosterAt[s] = null;
    const ctl = Instance.GetPlayerController(s);
    if (!ctl) { const old = players.get(s); if (old && old.ctl) forgetPlayer(old); continue; }
    let p = P(s);
    if (p.ctl !== ctl) {                       // a slot can change hands with no disconnect event
      if (p.ctl) { forgetPlayer(p); p = P(s); }
      p.ctl = ctl;
      try { p.bot = ctl.IsBot(); } catch (e) { p.bot = false; }
      stats.joins++; if (game.start && !game.over && TNOW - game.start > 30 && !p.bot) stats.lateJoins++;
      if (!p.bot) hudReset(p);                 // whatever the last player in this slot had on screen
    }
    const pawn = live(ctl.GetPlayerPawn());
    let alive = false, team = 0, pos = null;
    if (pawn) { try { alive = pawn.IsAlive(); team = pawn.GetTeamNumber(); if (alive) pos = pawn.GetAbsOrigin(); } catch (e) { alive = false; } }
    if (alive && !finiteV(pos)) alive = false;
    // a dead or spectating player who left the side: their seats and roles go back at once (a live one is handled in thinkPlayer)
    if (p.team && !alive) { let ct = p.team; try { ct = ctl.GetTeamNumber(); } catch (e) {} if (ct !== p.team) { stats.teamSwitches++; leaveTeam(p, pawn); } }
    const r = { slot: s, p, pawn, alive, team, pos, seated: !!p.heli, bot: p.bot };
    roster.push(r); rosterAt[s] = r;
  }
}

// ------------------------------------------------------------------ rounds
function clearWorld(soft) {
  for (const r of rockets) if (soft && r.ent) parkEnt(r.ent, r.i);
  rockets.length = 0;
  for (const tr of tracers) if (soft) parkEnt(tr.ent, tr.i);
  tracers.length = 0;
  for (const sh of shells) if (soft && sh.ent) parkEnt(sh.ent, 70 + sh.ei);
  shells.length = 0;
  for (const s of smokes) if (soft) fire("mv_smoke_fx_" + s.i, "Stop");
  smokes.length = 0;
  if (soft) for (const team of TEAMS) while (missions[team].length) dropMission(team, 0);
}
// a new round. CS2 re-creates the map entities (hard); when CS2 never restarted, the script resets the same entities itself (soft).
function resetRound(soft) {
  TNOW = now();
  stats.rounds++;
  for (const p of players.values()) {
    const pawn = pawnOf(p.slot);
    if (soft && pawn) { try { unseat(p, pawn, "deploy"); freeze(p, pawn, false); hidePawn(p, pawn, false); } catch (e) {} }
    dropSeats(p);
    p.role = null; p.crew = -1; p.aiRole = ""; p.aiGun = null; p.waitRole = ""; p.carrying = ""; p.carryEnt = -1;
    p.deployed = false; p.deployAt = TNOW + CONFIG.LOBBY_FIRST; p.here = ""; p.msnSel = -1; p.board = false; p.mount = -1; p.protectUntil = 0;
    p.fired = 0; p.hits = 0; p.missions = 0; p.atReadyAt = 0; p.atGiveAt = 0; p.afk = false; p.afkAt = TNOW;
    if (soft && pawn) { let a = false; try { a = pawn.IsAlive(); } catch (e) {} if (a) toLobby(p, pawn); }
  }
  clearWorld(soft);
  if (soft && points) {
    for (const h of allHelis) { for (const s of h.seats) s.slot = -1; h.owner = -1; h.yieldTo = -1; h.ai = null; h.inp = null; setEngine(h, false); setDust(h, false); hideWreck(h); if (h.ent) respawnHeli(h); h.rotorSpeed = 0; }
    for (const team of TEAMS) {
      flashes[team].length = 0;
      for (const g of guns[team]) { g.loaded = []; g.target = null; g.lay = "idle"; g.disabledUntil = 0; g.crew = []; g.aimer = -1; g.loader = -1; g.salvo = 0; g.impacts = []; g.ai = null; g.extraSigma = 0; g.yaw = g.yaw0; g.pitch = 0; g.cooldown = 0; }
    }
    for (const m of mounts) m.user = -1;
    for (const f of flags) { f.owner = 0; f.prog = 0; f.capTeam = 0; f.contested = false; fire("mv_flagpole_" + f.id, "Skin", 0); }
  } else {
    entCache.clear(); missing.clear(); points = null; hudEnt = undefined;
  }
  for (const p of players.values()) hudReset(p);
  startGame();
  directorAt = 0;
}
// back to the briefing room (only needed when the script restarts its own round: CS2 respawns everyone on a real one)
function toLobby(p, pawn) {
  try { pawn.Reset(); } catch (e) {}
}

// ------------------------------------------------------------------ think
function think() {
  const t0 = clock();
  TNOW = now();
  let dt = TNOW - lastTick; lastTick = TNOW;
  if (!(dt > 0) || dt > 0.1) dt = 1 / 64;
  Instance.SetNextThink(TNOW);               // scheduled first: an exception below can't stop the script for the rest of the round
  tickNo++;
  try {
    if (!points) { loadPoints(); if (!game.start || game.over) startGame(); }
    buildRoster();
    tickDirector();
    for (const h of allHelis) if (h.ai) tickAIPilot(h, dt);
  } catch (e) { logErr("world (pre)", e); if (!points) return; }
  for (const r of roster) { try { thinkPlayer(r, dt); } catch (e) { logErr("player " + r.slot, e); } }
  for (const h of allHelis) { try { tickHeli(h, dt); } catch (e) { logErr("helicopter " + h.tag, e); } }
  try {
    for (const team of TEAMS) for (const g of guns[team]) { if (g.ai) tickAICrew(g); tickGun(g, dt); }
    tickShells();
    tickRockets(dt);
    tickTracers(dt);
    tickSmokes();
    tickMissions();
    if (TNOW >= game.flagAt) { const C = CONFIG.CONQUEST; tickFlags(game.flagAt ? Math.min(1, C.TICK + (TNOW - game.flagAt)) : C.TICK); game.flagAt = TNOW + C.TICK; }
    tickTickets(dt);
    tickAmbient();
  } catch (e) { logErr("world", e); }
  // script time, once a minute
  const ms = clock() - t0;
  stats.ticks++; stats.ms += ms; if (ms > stats.msMax) stats.msMax = ms;
  perfTicks++; perfMs += ms; if (ms > perfMax) perfMax = ms;
  if (TNOW - perfAt >= CONFIG.PERF_LOG) {
    if (perfAt) {
      let humans = 0, flying = 0; for (const r of roster) if (!r.bot) humans++; for (const h of allHelis) if (h.state === "flying") flying++;
      stats.perfLines++;
      log("perf: " + (perfMs / Math.max(1, perfTicks)).toFixed(3) + " ms/tick avg, " + perfMax.toFixed(2) + " ms max, " + perfTicks + " ticks, " + (hudCalls / Math.max(1, perfTicks)).toFixed(1) +
          " HUD calls/tick, " + roster.length + " players (" + humans + " human), " + flying + " flying, " + rockets.length + " rockets, " + shells.length + " shells, tickets " +
          game.tickets[T] + "/" + game.tickets[CT] + ", errors " + errCount);
    }
    perfAt = TNOW; perfTicks = 0; perfMs = 0; perfMax = 0; hudCalls = 0;
  }
}
// a human who has not pressed a key, turned or stepped for AFK.TIME: their seat goes back to the team, they stop counting toward
// flags, kit limits and the "enough humans" test of the AI. Any input brings them back (the role returns at the next deploy).
function tickAfk(p, pawn, r, held) {
  const A = CONFIG.AFK;
  if (held) p.afkAt = TNOW;
  if (TNOW >= p.afkCheck) {
    p.afkCheck = TNOW + A.EVERY;
    const e = eyeOf(pawn), k = Math.round(e.yaw * 2) * 1000 + Math.round(e.pitch * 2);
    if (k !== p.afkEye) { p.afkEye = k; p.afkAt = TNOW; }
    if (!p.heli) { if (!p.afkPos || dist2(r.pos, p.afkPos) > A.MOVE) { p.afkPos = r.pos; p.afkAt = TNOW; } }
  }
  if (p.afkAt === TNOW) { if (p.afk) { p.afk = false; toast(p, "Welcome back", 2); } return; }
  if (!p.afk && TNOW - p.afkAt >= A.TIME) { p.afk = true; stats.afk++; toast(p, "AFK: your seat goes back to the team", 6); }
  if (!p.afk) return;
  if (p.board) leaveBoard(p, pawn);
  if (p.mount >= 0) leaveMount(p, pawn);
  if (p.heli && p.heli.landed) leaveHeli(p, pawn, "");            // an AFK pilot's helicopter settles by itself first (no input)
  if (!p.heli && p.role !== "infantry") setRole(p, "infantry", p.team);
}
function lobby(p, pawn, team, pressed) {
  if (p.hidden || p.moveNone) { hidePawn(p, pawn, false); freeze(p, pawn, false); }      // nobody waits in the briefing room shrunk or frozen
  if (!p.role) chooseRole(p, team);
  if (p.bot) { if (TNOW >= p.deployAt) deploy(p, pawn); return; }
  if (p.role === "infantry") {
    const ch = spawnChoices(p);
    if (pressed & CSInputs.RELOAD) p.spawnSel = ch[(Math.max(0, ch.indexOf(p.spawnSel)) + 1) % ch.length];
  }
  drawBrief(p, team);
  if ((tickNo + p.slot) % 16 === 0) drawFeed(p);
  hClass(p, "mv_status", "show", false); hClass(p, "mv_prompt", "show", false);
  hClass(p, "mv_toast", "show", TNOW < p.toastUntil);
  if (TNOW >= p.deployAt) { hClass(p, "mv_brief", "show", false); deploy(p, pawn); }
}
function commonHud(p, prompt) {
  hText(p, "mv_prompt_text", prompt); hClass(p, "mv_prompt", "show", !!prompt);
  hClass(p, "mv_toast", "show", TNOW < p.toastUntil);
  hClass(p, "mv_banner", "show", TNOW < p.bannerUntil);
}
function kitStationNear(p, pos) {
  for (const k of points.kit) {
    if (dist2(pos, k.pos) > CONFIG.STATION_RADIUS || Math.abs(pos.z - k.pos.z) > 100) continue;
    if (k.team ? k.team === p.team : (flagById(k.flag) || {}).owner === p.team) return k;
  }
  return null;
}
function thinkPlayer(r, dt) {
  const p = r.p, pawn = r.pawn;
  if (!p.bot) hClass(p, "mv_info", "show", TNOW < p.infoUntil);
  if (!r.alive) {
    if (p.heli || p.mount >= 0 || p.board || p.carrying) { if (p.heli && pawn) leaveHeli(p, pawn, "dead"); dropSeats(p); }
    if (!p.bot) { hClass(p, "mv_board", "show", false); hClass(p, "mv_prompt", "show", false); hClass(p, "mv_fly", "show", false); hClass(p, "mv_gun", "show", false); hClass(p, "mv_hold", "show", false); hClass(p, "mv_banner", "show", TNOW < p.bannerUntil); }
    return;
  }
  const team = r.team;
  if (team !== T && team !== CT) return;
  if (p.team !== team) {
    if (p.team) { stats.teamSwitches++; leaveTeam(p, pawn); }
    p.role = null; p.team = team; p.deployed = false; p.deployAt = TNOW + CONFIG.LOBBY_FIRST; p.uniformDone = false; p.kit = "rifle"; p.spawnSel = "base";
  }
  if (!p.sane) { sanitise(p, pawn); stats.sanitised++; }
  uniform(p, pawn, team);
  let held = 0, pressed = 0;
  if (!p.bot) { held = keys(pawn); pressed = held & ~p.prevKeys; p.prevKeys = held; }
  if (!p.deployed) { lobby(p, pawn, team, pressed); return; }
  if (!p.bot) {
    if ((tickNo + p.slot) % 16 === 0) { drawObjective(p); drawFeed(p); }
    if (p.protectUntil && ((held & CSInputs.ATTACK) || TNOW >= p.protectUntil)) p.protectUntil = 0;      // the deploy cover ends with the first shot
    tickAfk(p, pawn, r, held);
  }
  if (p.heli) {
    if (p.bot) tickAISeat(p, pawn, dt); else { tickSeat(p, pawn, dt, pressed, held); hClass(p, "mv_hold", "show", false); commonHud(p, ""); }
    return;
  }
  if (p.mount >= 0) {
    if (p.bot) tickAIMount(p, pawn, dt); else { tickMount(p, pawn, dt, pressed, held); hClass(p, "mv_status", "show", false); commonHud(p, ""); }
    return;
  }
  if (p.board) { tickBoard(p, pawn, dt, pressed, held); commonHud(p, ""); return; }
  if (p.ropeUntil) tickRope(p, pawn);
  if (p.bot) { tickBot(p, pawn, r.pos); return; }
  // a human on foot: the first thing in reach gets the prompt and the E key
  const pos = r.pos, use = (pressed & CSInputs.USE) !== 0;
  hClass(p, "mv_fly", "show", false); hClass(p, "mv_board", "show", false); hClass(p, "mv_gun", "show", false);
  if (p.role === "infantry") tickAT(p, pawn, pressed);
  let prompt = tickBattery(p, pawn, pos, dt, pressed, held);
  if (!prompt) {
    const m = mountNear(p, pos);
    if (m) {
      if (!mountFree(m, p)) prompt = m.team && m.team !== p.team ? "" : m.K.name + ": taken";
      else if (use) { takeMount(p, pawn, m); return; }
      else prompt = "[E] Man the " + m.K.name;
    }
  }
  if (!prompt) {
    const b = boardable(p, pos);
    if (b) {
      if (use) { enterHeli(p, pawn, b.h, b.idx); return; }
      prompt = "[E] Board the " + b.h.M.label + " (" + b.h.seats[b.idx].kind + ")";
    }
  }
  if (!prompt && p.role === "infantry") {
    const k = kitStationNear(p, pos);
    if (k) {
      const nx = nextKit(p, !!k.flag);
      if (use && nx) { setKit(p, pawn, nx, !!k.flag); return; }
      prompt = nx ? "[E] Kit: " + CONFIG.KITS[p.kit].label + "  ->  " + CONFIG.KITS[nx].label : "Kit: " + CONFIG.KITS[p.kit].label;
    }
  }
  let holdText = "", holdFrac = 0;
  if (p.holdKind === "repair") { holdText = "REPAIRING THE GUN"; holdFrac = p.holdT / CONFIG.ARTY.REPAIR_HOLD; }
  if (!prompt) {
    const o = tickObserver(p, pawn, dt, held);
    if (o) { holdText = o; holdFrac = p.holdT / CONFIG.ARTY.MISSION.HOLD; }
  } else if (p.holdKind === "mission") { p.holdKind = ""; p.holdT = 0; }
  drawHold(p, holdText, holdFrac);
  if (tickNo >= p.statusAt) { p.statusAt = tickNo + CONFIG.HUDCFG.STATUS_EVERY; drawStatus(p, team); }
  commonHud(p, prompt);
}

// ------------------------------------------------------------------ events
Instance.OnActivate(() => {
  for (const c of CONFIG.CVARS) Console.ServerCommand(c);
  if (CONFIG.BOTS_ON) { Console.ServerCommand("bot_quota_mode " + CONFIG.BOT_QUOTA_MODE); Console.ServerCommand("bot_quota " + CONFIG.BOT_QUOTA); }
  else { Console.ServerCommand("bot_quota 0"); Console.ServerCommand("bot_kick"); }
  log("mg_monsoon script " + VERSION + " - flags " + LAYOUT.flags.length + ", bots " + (CONFIG.BOTS_ON ? "on (quota " + CONFIG.BOT_QUOTA + ")" : "off"));
  entCache.clear(); points = null; lastTick = now(); TNOW = lastTick; game.start = 0;
  Instance.SetThink(think);
  Instance.SetNextThink(now());
});
Instance.OnRoundStart(() => {
  resetRound(false);
  log("round " + stats.rounds + " start (" + VERSION + ")");
  Instance.SetThink(think); Instance.SetNextThink(now());
});
Instance.OnPlayerReset(({ player }) => {
  const pawn = live(player); if (!pawn) return;
  const s = slotOfPawn(pawn); if (s < 0) return;
  const p = P(s);
  TNOW = now();
  dropSeats(p);
  if (p.hidden) hidePawn(p, pawn, false);
  if (p.moveNone) freeze(p, pawn, false);
  p.uniformDone = false; p.uniformAt = TNOW + CONFIG.UNIFORM_DELAY;
  p.deployed = false; p.prevKeys = 0;
  p.deployAt = TNOW + (p.first ? CONFIG.LOBBY_FIRST : CONFIG.LOBBY_RESPAWN);
  p.protectUntil = 0; p.statusAt = 0; p.afk = false; p.afkAt = TNOW;
  const team = pawn.GetTeamNumber();
  if ((team === T || team === CT) && p.team === team && points) { chooseRole(p, team); settleKit(p); }
});
Instance.OnPlayerDisconnect(({ playerSlot }) => {
  const p = players.get(playerSlot);
  if (p) forgetPlayer(p);
});
// which stats bucket a CS2 weapon kill or hit belongs to
function weaponSrc(weapon) {
  let cls = ""; try { cls = weapon ? weapon.GetClassName() : ""; } catch (e) {}
  return cls === "weapon_negev" || cls === "weapon_m249" ? "mg" : "rifle";
}
Instance.OnPlayerKill(({ player, attacker, weapon }) => {
  const victim = live(player); if (!victim) return;
  TNOW = now();
  const vs = slotOfPawn(victim), vp = vs >= 0 ? players.get(vs) : undefined;
  let vteam = 0; try { vteam = victim.GetTeamNumber(); } catch (e) {}
  const counted = !!vp && vp.deployed;
  if (vp) {
    if (vp.heli) leaveHeli(vp, victim, "dead");
    dropSeats(vp);
    if (counted) { stats.deaths++; loseTicket(vteam, CONFIG.CONQUEST.DEATH_COST); try { missionAssist(vteam, victim.GetAbsOrigin()); } catch (e) {} }
  }
  const ap = toPawn(attacker);
  let as = -1, ateam = 0;
  if (ap && ap !== victim) { as = slotOfPawn(ap); try { ateam = ap.GetTeamNumber(); } catch (e) {} }
  const enemyKill = as >= 0 && ateam !== vteam;
  if (counted) {
    const k = dmgSrc || (enemyKill ? weaponSrc(weapon) : "other"), side = stats.killsOn[vteam] || (stats.killsOn[vteam] = {});
    stats.killsBy[k] = (stats.killsBy[k] || 0) + 1; side[k] = (side[k] || 0) + 1;       // killsOn[team] = that team's deaths by source
  }
  if (!enemyKill) return;
  const a = P(as);
  a.kills++; a.merit++;
});
if (typeof Instance.OnPlayerDamage === "function") {
  Instance.OnPlayerDamage(({ player, attacker }) => {
    const t = now();
    const vp = players.get(slotOfPawn(player)); if (vp) vp.lastCombat = t;
    const ap = toPawn(attacker); if (ap) { const q = players.get(slotOfPawn(ap)); if (q) q.lastCombat = t; }
  });
}
// damage guard: nobody aboard a helicopter is hurt except by the crash the script deals (hits on the airframe cost airframe health);
// fast-roping players take no fall damage; crews at the board and players still in the briefing room only take enemy fire.
Instance.OnModifyPlayerDamage((ev) => {
  const v = ev.player, vs = slotOfPawn(v); if (vs < 0) return;
  const p = players.get(vs); if (!p || p.scripted) return;
  const ap = toPawn(ev.attacker);
  let enemy = false; try { enemy = !!(ap && ap !== v && ap.GetTeamNumber() !== v.GetTeamNumber()); } catch (e) {}
  let why = "";
  if (p.heli) why = "aboard";
  else if ((ev.damageTypes & CSDamageTypes.FALL) && now() < p.noFallUntil) why = "fast-rope";
  else if (!p.deployed && !enemy) why = "briefing room";
  else if ((p.board || p.aiRole === "crew") && !enemy) why = "battery crew";
  else if (enemy && p.deployed && now() < p.protectUntil) { stats.spawnGuard++; return { abort: true }; }       // deploy cover: not logged, it is routine
  if (why) {
    stats.blocked++;
    if (stats.blocked <= 40) {
      let cls = "?"; try { cls = ev.inflictor ? ev.inflictor.GetClassName() + ":" + ev.inflictor.GetEntityName() : "none"; } catch (e) {}
      log("blocked " + Math.round(ev.damage) + " damage to " + why + " (slot " + vs + ", types " + ev.damageTypes + ", inflictor " + cls + ")");
    }
    return { abort: true };
  }
});
Instance.OnBulletImpact(({ weapon, hitEntity }) => {
  const h = heliOfEntity(hitEntity); if (!h) return;
  TNOW = now();
  let owner, cls = "";
  try { owner = toPawn(weapon.GetOwner()); cls = weapon.GetClassName(); } catch (e) {}
  if (!owner) return;
  const B = CONFIG.BULLET_VS_HELI;
  damageHeli(h, B[cls] !== undefined ? B[cls] : B.DEFAULT, slotOfPawn(owner), weaponSrc(weapon));
});
if (typeof Instance.OnGunFire === "function") {
  Instance.OnGunFire(({ weapon }) => {
    let cls = "", owner;
    try { cls = weapon.GetClassName(); if (cls === "weapon_taser") owner = toPawn(weapon.GetOwner()); } catch (e) {}
    if (!owner) return;
    const p = players.get(slotOfPawn(owner));
    if (p) { TNOW = now(); fireAT(p, owner); }
  });
}
Instance.OnPlayerChat(({ player, text }) => {
  if (!player) return;
  TNOW = now();
  const s = player.GetPlayerSlot(), p = P(s);
  const words = String(text || "").trim().toLowerCase().split(/\s+/);
  let cmd = words[0] || "";
  if (cmd[0] !== "!" && cmd[0] !== "/") return;
  cmd = cmd.slice(1);
  const pawn = toPawn(player), onTeam = p.team === T || p.team === CT;
  let alive = false; try { alive = !!pawn && pawn.IsAlive(); } catch (e) {}
  if (cmd === "infantry" || cmd === "artillery" || cmd === "arty" || cmd === "air" || cmd === "pilot") {
    const role = cmd === "infantry" ? "infantry" : cmd === "air" || cmd === "pilot" ? "air" : "artillery";
    p.pref = role; roleCard(p, role);
    if (onTeam && points) requestRole(p, role);
  }
  else if (cmd === "rifle" || cmd === "mg" || cmd === "at") {
    if (!onTeam) return;
    if (p.role !== "infantry") { toast(p, "Kits are for the infantry (!infantry)", 3); return; }
    if (alive && p.deployed && !kitStationNear(p, pawn.GetAbsOrigin())) {
      if (kitAllowed(p, cmd, false)) { p.kitNext = cmd === p.kit ? "" : cmd; toast(p, CONFIG.KITS[cmd].label + " at your next deploy (now, at an arms rack)", 4); }
      else { stats.kitDenied++; toast(p, CONFIG.KITS[cmd].label + ": all issued (" + kitLimit(p.team, cmd) + " per team)", 3); }
    } else setKit(p, alive ? pawn : undefined, cmd, false);
  }
  else if (cmd === "swap") {
    if (p.heli && alive) {                          // next free seat in the helicopter (gunner <-> rider)
      const h = p.heli, cur = p.seat;
      if (h.seats[cur].kind === "pilot") { toast(p, "The pilot stays at the controls", 2); return; }
      for (let k = 1; k < h.seats.length; k++) {
        const i = (cur + k) % h.seats.length;
        if (i === 0 || h.seats[i].slot >= 0) continue;
        h.seats[cur].slot = -1; restoreCamera(p);
        h.seats[i].slot = p.slot; p.seat = i; setSeatCamera(p, pawn, h);
        try { pawn.Teleport({ position: seatPos(h, i) }); if (h.seats[i].kind === "gunner") pawn.SetEyeAngles({ pitch: 10, yaw: h.yaw + h.M.GUN.yaw, roll: 0 }); } catch (e) {}
        toast(p, "Moved to the " + h.seats[i].kind + " seat", 2); return;
      }
      toast(p, "No other seat is free", 2);
    } else if (alive && p.deployed && p.role === "infantry") {
      const k = kitStationNear(p, pawn.GetAbsOrigin()), nx = k ? nextKit(p, !!k.flag) : "";
      if (nx) setKit(p, pawn, nx, !!k.flag); else toast(p, "!swap: next kit at an arms rack, or the next seat in a helicopter", 3);
    }
  }
  else if (cmd === "spawn") {
    const w = words[1] || "";
    const f = flagById(w);
    if (w === "base") { p.spawnSel = "base"; toast(p, "Next deploy: the base", 3); }
    else if (w === "heli" || w === "helicopter") { p.spawnSel = "heli"; toast(p, "Next deploy: aboard a waiting helicopter (the base if none waits)", 4); }
    else if (f) { p.spawnSel = f.id; toast(p, f.owner === p.team ? "Next deploy: " + f.id.toUpperCase() + " " + f.name : f.id.toUpperCase() + " " + f.name + " is not ours: the base until it is", 3); }
    else toast(p, "!spawn a | b | c | d | e | base | heli", 3);
  }
  else if (cmd === "pos") {
    if (pawn) { const o = pawn.GetAbsOrigin(); say("[mv] " + nameOf(s) + " at x " + Math.round(o.x) + " y " + Math.round(o.y) + " z " + Math.round(o.z) + "  grid " + gridRef(o.x, o.y)); }
  }
  else if (cmd === "uniform") {
    p.noUniform = !p.noUniform;
    if (p.noUniform) { if (alive && p.stockModel) { try { pawn.SetModel(p.stockModel); } catch (e) {} } toast(p, "Your own agent model (!uniform puts the uniform back on)", 4); }
    else { p.uniformDone = false; p.uniformAt = TNOW; toast(p, "Uniform on", 3); }
  }
  else if (cmd === "bots") {
    const n = parseInt(words[1], 10);
    if (!CONFIG.BOTS_CHAT) { toast(p, "!bots is switched off on this server", 3); return; }
    if (!Number.isFinite(n) || n < 0) { toast(p, "!bots <0-" + CONFIG.BOT_QUOTA_MAX + ">", 3); return; }
    const q = Math.min(CONFIG.BOT_QUOTA_MAX, n);
    CONFIG.BOTS_ON = q > 0; CONFIG.BOT_QUOTA = q;
    Console.ServerCommand("bot_quota_mode " + CONFIG.BOT_QUOTA_MODE);
    Console.ServerCommand("bot_quota " + q);            // bot_* cvars are on the Workshop command allow list
    if (q === 0) Console.ServerCommand("bot_kick");
    say("[mv] bots: " + (q ? "quota " + q : "off") + " (set by " + nameOf(s) + ")");
  }
  else if (cmd === "roles" || cmd === "help") {
    const cnt = (r) => teamCount(p.team, (q) => q.role === r);
    const tm = onTeam ? p.team : CT;
    info(p, "COMBAT ROLES", ["INFANTRY (" + cnt("infantry") + ")  -  !infantry   kits !rifle !mg !at",
      "ARTILLERY (" + cnt("artillery") + "/" + (guns[tm].length * CONFIG.ROLES.ARTY_CREW) + ")  -  !artillery",
      "AIRCREW (" + cnt("air") + "/" + helis[tm].length + ")  -  !air", "!spawn a-e | base | heli    !swap    !pos    !uniform",
      "!bots <n>  -  bots fill the empty roles when few humans play"], "A role's command shows its orders and asks for it.");
  }
});
// the script was edited and reloaded in the tools: carry the match over (tickets, clock, flag owners) and start thinking again.
// Seats are not carried: every pawn is put back on its feet (sanitise) and deploys again.
if (typeof Instance.OnScriptReload === "function") {
  Instance.OnScriptReload({
    before: () => ({ tickets: { 2: game.tickets[T], 3: game.tickets[CT] }, elapsed: now() - game.start, over: game.over, owners: flags.map((f) => f.owner), reloads: stats.reloads,
                     // what each player asked for (role, kit, deploy point) and the running counters (the perf / stats lines keep counting)
                     prefs: [...players.values()].map((p) => ({ slot: p.slot, pref: p.pref, kit: p.kitNext || p.kit, spawnSel: p.spawnSel, merit: p.merit, noUniform: p.noUniform, flown: p.flown })),
                     stats: Object.fromEntries(Object.entries(stats).filter(([, v]) => typeof v === "number")) }),
    after: (m) => {
      TNOW = now(); lastTick = TNOW; entCache.clear(); points = null;
      try {
        loadPoints(); startGame();
        if (m && m.tickets && !m.over) {
          game.tickets[T] = m.tickets[2]; game.tickets[CT] = m.tickets[3]; game.start = TNOW - (Number.isFinite(m.elapsed) ? m.elapsed : 0);
          (m.owners || []).forEach((o, i) => { const f = flags[i]; if (f && (o === T || o === CT)) { f.owner = o; fire("mv_flagpole_" + f.id, "Skin", o === T ? 1 : 2); } });
        }
        const S = /** @type {any} */ (stats);
        const MS = /** @type {any} */ (m && m.stats);
        if (MS) for (const k of Object.keys(MS)) if (typeof S[k] === "number" && Number.isFinite(MS[k]) && k !== "msMax") S[k] += MS[k];
        if (m && Array.isArray(m.prefs)) for (const o of m.prefs) {
          if (!o || !(o.slot >= 0) || !Instance.GetPlayerController(o.slot)) continue;
          const p = P(o.slot);
          p.pref = o.pref || ""; p.kitNext = CONFIG.KITS[o.kit] ? o.kit : ""; p.spawnSel = o.spawnSel || "base"; p.merit = o.merit | 0; p.noUniform = !!o.noUniform; p.flown = o.flown | 0;
        }
        stats.reloads = ((m && m.reloads) || 0) + 1;
      } catch (e) { logErr("reload", e); }
      log("script reloaded (" + VERSION + "): match carried over, everyone deploys again");
      Instance.SetThink(think); Instance.SetNextThink(now());
    },
  });
}
