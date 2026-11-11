// ------------------------------------------------------------------ 90_main: think loop, per-player tick, events, chat, damage guard
const stats = { rounds: 0, gunShots: 0, rockets: 0, fired: 0, shells: 0, beehive: 0, missions: 0, captures: 0, flights: 0, landings: 0, heliLost: 0, heliDamage: 0, gunsDisabled: 0,
                repairs: 0, mountUses: 0, leash: 0, blocked: 0, aiPilots: 0, aiGunners: 0, aiCrews: 0, aiShots: 0, aiStrafes: 0, aiLandings: 0, aiGunTicks: 0,
                ticks: 0, ms: 0, msMax: 0 };
let roster = [];
const rosterAt = new Array(64).fill(null);
let lastTick = 0, perfAt = 0, perfTicks = 0, perfMs = 0, perfMax = 0, tickNo = 0;
const clock = typeof performance !== "undefined" && performance && typeof performance.now === "function" ? () => performance.now() : () => Date.now();
try { globalThis.__mvDebug = { VERSION, CONFIG, players, helis, guns, flags, game, stats, missions, flashes, shells, rockets, mounts, smokes }; } catch (e) {}

// forget what a player was sitting in without touching a pawn (death, respawn, disconnect, the slot changing hands)
function dropSeats(p) {
  if (p.heli) { const s = p.heli.seats[p.seat]; if (s && s.slot === p.slot) s.slot = -1; if (p.seat === 0) p.heli.ai = null; p.heli = null; p.seat = -1; }
  if (p.mount >= 0) { const m = mounts[p.mount]; if (m && m.user === p.slot) m.user = -1; p.mount = -1; }
  if (p.board) { const g = guns[p.team] && guns[p.team][p.crew]; if (g && g.aimer === p.slot) g.aimer = -1; p.board = false; }
  restoreCamera(p);
  dropCarry(p);
  p.holdKind = ""; p.holdT = 0; p.ropeUntil = 0;
}
function forgetPlayer(p) {
  dropSeats(p);
  leaveCrew(p);
  if (p.team) leaveHeliRole(p);
  for (const team of TEAMS) for (let i = missions[team].length - 1; i >= 0; i--) if (missions[team][i].owner === p.slot) dropMission(team, i);
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
    }
    const pawn = live(ctl.GetPlayerPawn());
    let alive = false, team = 0, pos = null;
    if (pawn) { try { alive = pawn.IsAlive(); team = pawn.GetTeamNumber(); if (alive) pos = pawn.GetAbsOrigin(); } catch (e) { alive = false; } }
    if (alive && !finiteV(pos)) alive = false;
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
    p.deployed = false; p.deployAt = TNOW + CONFIG.LOBBY_FIRST; p.here = ""; p.msnSel = -1;
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
    if (TNOW >= game.flagAt) { const C = CONFIG.CONQUEST; tickFlags(game.flagAt ? C.TICK + (TNOW - game.flagAt) : C.TICK); game.flagAt = TNOW + C.TICK; }
    tickTickets(dt);
    tickAmbient();
  } catch (e) { logErr("world", e); }
  // script time, once a minute
  const ms = clock() - t0;
  stats.ticks++; stats.ms += ms; if (ms > stats.msMax) stats.msMax = ms;
  perfTicks++; perfMs += ms; if (ms > perfMax) perfMax = ms;
  if (TNOW - perfAt >= CONFIG.PERF_LOG) {
    if (perfAt) log("script time " + (perfMs / Math.max(1, perfTicks)).toFixed(3) + " ms/tick avg, " + perfMax.toFixed(2) + " max over " + perfTicks + " ticks, " + roster.length + " players, errors " + errCount);
    perfAt = TNOW; perfTicks = 0; perfMs = 0; perfMax = 0;
  }
}
function lobby(p, pawn, team, pressed) {
  if (!p.role) chooseRole(p, team);
  if (p.bot) { if (TNOW >= p.deployAt) deploy(p, pawn); return; }
  if (p.role === "infantry") {
    const ch = spawnChoices(p);
    if (!ch.includes(p.spawnSel)) p.spawnSel = "base";
    if (pressed & CSInputs.RELOAD) p.spawnSel = ch[(ch.indexOf(p.spawnSel) + 1) % ch.length];
  }
  drawBrief(p, team);
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
    if (p.team) { unseat(p, pawn, "role"); if (p.aiRole) aiRelease(p, false); leaveCrew(p); leaveHeliRole(p); }
    p.role = null; p.team = team; p.deployed = false; p.deployAt = TNOW + CONFIG.LOBBY_FIRST; p.uniformDone = false; p.kit = "rifle"; p.spawnSel = "base";
  }
  uniform(p, pawn, team);
  let held = 0, pressed = 0;
  if (!p.bot) { held = keys(pawn); pressed = held & ~p.prevKeys; p.prevKeys = held; }
  if (!p.deployed) { lobby(p, pawn, team, pressed); return; }
  if (!p.bot && (tickNo + p.slot) % 16 === 0) drawObjective(p);
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
  if (p.holdKind === "repair") { holdText = "REPAIRING"; holdFrac = p.holdT / CONFIG.ARTY.REPAIR_HOLD; }
  if (!prompt) {
    const o = tickObserver(p, pawn, dt, held);
    if (o) { holdText = o; holdFrac = p.holdT / CONFIG.ARTY.MISSION.HOLD; }
  } else if (p.holdKind === "mission") { p.holdKind = ""; p.holdT = 0; }
  drawHold(p, holdText, holdFrac);
  drawStatus(p, team);
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
  const team = pawn.GetTeamNumber();
  if ((team === T || team === CT) && p.team === team && points) chooseRole(p, team);
});
Instance.OnPlayerDisconnect(({ playerSlot }) => {
  const p = players.get(playerSlot);
  if (p) forgetPlayer(p);
});
Instance.OnPlayerKill(({ player, attacker }) => {
  const victim = live(player); if (!victim) return;
  TNOW = now();
  const vs = slotOfPawn(victim), vp = vs >= 0 ? players.get(vs) : undefined;
  let vteam = 0; try { vteam = victim.GetTeamNumber(); } catch (e) {}
  if (vp) {
    if (vp.heli) leaveHeli(vp, victim, "dead");
    dropSeats(vp);
    if (vp.deployed) { loseTicket(vteam, CONFIG.CONQUEST.DEATH_COST); try { missionAssist(vteam, victim.GetAbsOrigin()); } catch (e) {} }
  }
  const ap = toPawn(attacker); if (!ap || ap === victim) return;
  const as = slotOfPawn(ap); if (as < 0) return;
  let ateam = 0; try { ateam = ap.GetTeamNumber(); } catch (e) {}
  if (ateam === vteam) return;
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
  damageHeli(h, B[cls] !== undefined ? B[cls] : B.DEFAULT, slotOfPawn(owner));
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
      if (kitAllowed(p, cmd, false)) { p.kit = cmd; toast(p, CONFIG.KITS[cmd].label + " on your next deploy (or now at an arms rack)", 4); }
      else toast(p, CONFIG.KITS[cmd].label + ": none left on the rack", 3);
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
        try { pawn.Teleport({ position: seatPos(h, i) }); } catch (e) {}
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
    if (w === "base") { p.spawnSel = "base"; toast(p, "Deploying at the base", 3); }
    else if (f) { p.spawnSel = f.id; toast(p, f.owner === p.team ? "Deploying at " + f.id.toUpperCase() + " " + f.name : f.id.toUpperCase() + " " + f.name + " is not ours: base until it is", 3); }
    else toast(p, "!spawn a | b | c | d | e | base", 3);
  }
  else if (cmd === "pos") {
    if (pawn) { const o = pawn.GetAbsOrigin(); say("[mv] " + nameOf(s) + " at x " + Math.round(o.x) + " y " + Math.round(o.y) + " z " + Math.round(o.z) + "  grid " + gridRef(o.x, o.y)); }
  }
  else if (cmd === "uniform") {
    p.noUniform = !p.noUniform;
    if (p.noUniform) { if (alive && p.stockModel) { try { pawn.SetModel(p.stockModel); } catch (e) {} } toast(p, "Standard agent model (!uniform to wear the uniform again)", 4); }
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
      "AIRCREW (" + cnt("air") + "/" + helis[tm].length + ")  -  !air", "!spawn a-e | base    !swap    !pos    !uniform",
      "!bots <n>  -  bots fill the empty roles when few humans play"], "Type a role's command to see its orders and ask for it.");
  }
});
