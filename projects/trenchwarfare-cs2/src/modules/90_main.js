// 90_main: think loop, per-player tick, engine events, chat

function keys(pawn) {
  let k = 0;
  for (const b of [CSInputs.FORWARD, CSInputs.BACK, CSInputs.LEFT, CSInputs.RIGHT, CSInputs.WALK, CSInputs.USE, CSInputs.ATTACK, CSInputs.ATTACK2, CSInputs.JUMP]) {
    try { if (pawn.IsInputPressed(b)) k |= b; } catch (e) {}
  }
  return k;
}
// ------------------------------------------------------------------ per tick
let lastTick = 0, tickN = 0;
let errAt = -99;
let perfMs = 0, perfMax = 0, perfTicks = 0, perfAt = -1, gapMax = 0, wallLast = -1;
function logErr(where, e) { stats.errors++; const t = now(); if (t - errAt > 2) { errAt = t; Console.Log("[tw] error in " + where + ": " + e + (e && e.stack ? " " + e.stack : "")); } }
function think() {
  const c0 = clock();
  if (wallLast >= 0 && c0 - wallLast > gapMax) gapMax = c0 - wallLast;   // wall time between thinks: a server hitch shows here (tw35)
  wallLast = c0;
  const t = now(); let dt = t - lastTick; lastTick = t; tickN++;
  if (!(dt > 0) || dt > 0.1) dt = 1 / 64;
  Instance.SetNextThink(t);                 // scheduled first: an exception below can't stop the script for the rest of the round
  try {
    if (!points) loadPoints();
    tickShells();
    tickBombs(dt);
    tickTracers(dt);
    tickAmbient();
    tickUnlocks(t);
    aiThink(t, dt);
  } catch (e) { logErr("world", e); }
  for (let s = 0; s < 64; s++) { try { thinkPlayer(s, t, dt); } catch (e) { logErr("player " + s, e); } }
  perfLine(t, clock() - c0);
}
// "[tw] perf:" once a minute: what the script costs a server (the mock's numbers include its own stand-in engine)
function perfLine(t, ms) {
  perfMs += ms; perfTicks++; if (ms > perfMax) perfMax = ms;
  if (perfAt < 0) perfAt = t;
  if (t - perfAt < CONFIG.PERF_EVERY) return;
  let n = 0, humans = 0, flying = 0, aiP = 0, aiC = 0;
  for (const q of players.values()) { n++; if (!q.bot) humans++; if (q.air) flying++; if (q.aiRole === "pilot") aiP++; if (q.aiRole === "crew") aiC++; }
  Console.Log("[tw] perf: " + (perfMs / Math.max(1, perfTicks)).toFixed(3) + " ms/tick avg, " + perfMax.toFixed(2) + " ms max, " + perfTicks + " ticks, " +
              n + " players (" + humans + " human, AI pilots " + aiP + ", AI crews " + aiC + "), " + flying + " flying, " + shells.length + " shells, " + bombs.length +
              " bombs, longest gap between thinks " + gapMax.toFixed(0) + " ms, errors " + stats.errors);
  stats.perfLines++; perfMs = 0; perfMax = 0; perfTicks = 0; perfAt = t; gapMax = 0;
}
// a slot whose player is gone (disconnect, or the controller vanished without the event): seat, aircraft and HUD are freed
function dropPlayer(p) {
  leaveTeam(p, undefined);
  hudReset(p);
  players.delete(p.slot);
}
// AFK: no key, no turn of the view and no step for CONFIG.AFK seconds. A pilot is brought down to the trench as infantry (his
// aircraft goes home), a mortar crewman gives up his seat. Humans only: script-run bots never idle, and an
// AFK human does not count toward a side's humans for the AI roles (85_ai humansOn).
function tickAfk(p, pawn, t, held) {
  if (held) { p.lastActive = t; return; }
  if (((tickN + p.slot) & 31) !== 0) return;
  let eye, o;
  try { eye = pawn.GetEyeAngles(); o = pawn.GetAbsOrigin(); } catch (e) { return; }
  const le = p.lastEye;
  const moved = !le || Math.abs(wrap180(eye.yaw - le.yaw)) + Math.abs(eye.pitch - le.pitch) > 0.5 || (!p.air && dist3(o, le.o) > 8);
  p.lastEye = { yaw: eye.yaw, pitch: eye.pitch, o };
  if (moved) { p.lastActive = t; return; }
  const idle = t - (p.lastActive || t);
  if (p.air && idle >= CONFIG.AFK.PILOT) {
    endFlight(p, pawn, false); setRole(p, "infantry", p.team); deploy(p, pawn);
    toast(p, "Away from the controls - your aircraft went home", 6);
    stats.afk++; p.lastActive = t;
  } else if (p.role === "mortar" && p.crew >= 0 && idle >= CONFIG.AFK.CREW) {
    if (p.inSight) leaveSight(p, pawn);
    setRole(p, "infantry", p.team);
    toast(p, "Away too long - your mortar seat was given to someone else.", 6);
    stats.afk++; p.lastActive = t;
  }
}
function thinkPlayer(s, t, dt) {
  {
    const ctl = Instance.GetPlayerController(s);
    if (!ctl) { const gone = players.get(s); if (gone) dropPlayer(gone); return; }
    const pawn = live(ctl.GetPlayerPawn());
    const p = P(s);
    try { p.bot = ctl.IsBot(); } catch (e) {}
    // the side, read from the controller as well, so a dead or spectating player who switched also leaves his seat and aircraft
    let side = 0; try { side = ctl.GetTeamNumber(); } catch (e) {}
    if (side !== T && side !== CT && pawn) { try { const pt = pawn.GetTeamNumber(); if (pt === T || pt === CT) side = pt; } catch (e) {} }
    if (p.team && side !== p.team) { leaveTeam(p, pawn); p.team = side === T || side === CT ? side : 0; p.deployAt = t + CONFIG.LOBBY_FIRST; p.uniformDone = false; }
    hClass(p, "tw_info", "show", t < (p.infoUntil || 0));
    if (!pawn || !pawn.IsAlive()) { if (p.air) endFlight(p, pawn, true); if (p.inSight) leaveSight(p, pawn); hClass(p, "tw_target", "show", false); hClass(p, "tw_prompt", "show", false); return; }
    if (!p.sane) { p.sane = true; if (!p.air && !p.inSight) sanitise(p, pawn); }   // first look at this pawn (map start, script reload)
    const team = pawn.GetTeamNumber();
    if (team !== T && team !== CT) return;
    if (p.team !== team) { leaveTeam(p, pawn); p.team = team; p.deployAt = t + CONFIG.LOBBY_FIRST; p.uniformDone = false; }
    uniform(p, pawn, team, t);
    const held = p.bot ? 0 : keys(pawn); const pressed = held & ~p.prevKeys; p.prevKeys = held;
    if (p.deployed && !p.bot) tickAfk(p, pawn, t, held);
    let prompt = "";
    if (!p.deployed) {
      if (!p.role) chooseRole(p, pawn, team);
      hClass(p, "tw_brief", "show", true);
      hText(p, "tw_brief_role", ROLE_NAME[p.role] || "");
      const lines = p.role === "mortar" ? ["Crew " + (p.crew + 1) + " of " + CONFIG.CREWS + ". Plot targets at the map table,", "fetch bombs from the ammunition box,", "load and fire the mortar. Swap jobs freely."]
        : p.role === "air" ? ["Report to the aerodrome.", "Limited lives - then back to the trenches.", ""]
        : ["Hold the fire trench. " + CONFIG.RIFLE_NAME[team] + ", pistol, knife.", CONFIG.STREAK_UPGRADE + " kills without dying earns a " + CONFIG.UPGRADE_NAME[team] + ".", "Dressing stations in the support trench heal you."];
      hText(p, "tw_brief_l1", lines[0]); hText(p, "tw_brief_l2", lines[1]); hText(p, "tw_brief_l3", lines[2]);
      hText(p, "tw_brief_count", "Moving up in " + Math.max(0, p.deployAt - t).toFixed(0) + "s   (chat: !mortar  !infantry  !roles)");
      hClass(p, "tw_toast", "show", t < p.toastUntil);          // answers to role commands in the briefing room (were never shown)
      hClass(p, "tw_banner", "show", t < p.bannerUntil);        // a front headline reaches the briefing room too
      if (t >= p.deployAt) { hClass(p, "tw_brief", "show", false); p.first = false; deploy(p, pawn); }
      return;
    }
    if (p.air) {
      if (p.bot && p.aiRole !== "pilot") { endFlight(p, pawn, false); return; }        // only a script pilot flies a bot
      const pr = tickAir(p, pawn, dt, pressed, held, p.aiRole === "pilot" ? aiSteer(p, p.air, t) : undefined);
      hText(p, "tw_prompt_text", pr); hClass(p, "tw_prompt", "show", !!pr);
      hClass(p, "tw_toast", "show", t < p.toastUntil); hClass(p, "tw_banner", "show", t < p.bannerUntil);
      return;
    }
    if (p.role === "infantry" && p.upgraded && (pressed & CSInputs.USE) && (held & CSInputs.WALK)) swapRifle(p, pawn);
    if (p.bot) tickBot(p, pawn, team, dt);
    p.healing = false;
    const hp = points.heal[team] || [];
    const o = pawn.GetAbsOrigin();
    for (const h of hp) {
      if (dist2(o, h) < CONFIG.HEAL_RADIUS && Math.abs(o.z - h.z) < 120) {
        p.healing = true;
        const H = pawn.GetHealth();
        p.hacc = (p.hacc || 0) + CONFIG.HEAL_HP_PER_S * dt;
        if (H < 100 && p.hacc >= 1) { const add = Math.floor(p.hacc); p.hacc -= add; pawn.SetHealth(Math.min(100, H + add)); stats.heals++; }
        const A = pawn.GetArmor();
        p.aacc = (p.aacc || 0) + CONFIG.HEAL_ARMOR_PER_S * dt;
        if (A < 100 && p.aacc >= 1) { const add = Math.floor(p.aacc); p.aacc -= add; pawn.SetArmor(Math.min(100, A + add)); }
        if (!pawn.HasHelmet()) pawn.SetHasHelmet(true);
        prompt = (H < 100 || A < 100) ? "Dressing station - patching you up" : "Dressing station - fit for duty";
        break;
      }
    }
    if (p.role === "mortar" && p.crew >= 0) {
      const pr = tickMortar(p, pawn, dt, pressed, held);
      if (pr) prompt = pr;
      if (p.inSight) drawSight(p); else hClass(p, "tw_target", "show", false);
    } else {
      if (p.inSight) leaveSight(p, pawn);
      hClass(p, "tw_target", "show", false);
    }
    // HUD: prompt, status, toast, banner
    hText(p, "tw_prompt_text", prompt); hClass(p, "tw_prompt", "show", !!prompt);
    hClass(p, "tw_status", "show", !p.inSight);              // the plotting board carries the crew lines (and covers the card on 4:3)
    hText(p, "tw_st_role", ROLE_NAME[p.role] || "");
    if (p.role === "infantry") {
      hText(p, "tw_st_l1", "Rifle: " + (p.upgraded ? CONFIG.UPGRADE_NAME[team] : CONFIG.RIFLE_NAME[team]));
      hText(p, "tw_st_l2", p.upgraded ? "Marksman: upgrade issued" : "Streak " + p.streak + " / " + CONFIG.STREAK_UPGRADE + " for an upgrade");
      hText(p, "tw_st_l3", "Kills: " + p.kills);
    } else if (p.role === "mortar") {
      const c = crews[team][p.crew];
      const mate = c ? (p.seat === "a" ? c.b : c.a) : -1;
      const mn = mate >= 0 ? nameOf(mate) : "none";
      hText(p, "tw_st_l1", "Crew " + (p.crew + 1) + "  -  mate: " + mn);
      hText(p, "tw_st_l2", "Tube: " + (c && c.loaded ? "LOADED" : "empty") + "   Target: " + (c && c.target ? "set" : "none"));
      hText(p, "tw_st_l3", "Mortar kills: " + p.mortarKills + (p.carrying ? "   (bomb in hand)" : ""));
    } else {
      hText(p, "tw_st_l1", "Lives: " + p.lives); hText(p, "tw_st_l2", ""); hText(p, "tw_st_l3", "");
    }
    hClass(p, "tw_toast", "show", t < p.toastUntil);
    hClass(p, "tw_banner", "show", t < p.bannerUntil);
  }
}

// ------------------------------------------------------------------ events
Instance.OnActivate(() => {
  for (const c of CONFIG.CVARS) Console.ServerCommand(c);
  // bots fill the server to 2 x FILL_PER_SIDE players and leave as humans join (bot_quota_mode fill); off: none (the tw35 setting)
  if (CONFIG.BOTS_ON) { Console.ServerCommand("bot_quota_mode fill"); Console.ServerCommand("bot_quota " + 2 * CONFIG.BOTS.FILL_PER_SIDE); }
  else { Console.ServerCommand("bot_quota 0"); Console.ServerCommand("bot_kick"); }
  points = null; lastTick = now();
  Instance.SetThink(think);
  Instance.SetNextThink(now());
});
Instance.OnRoundStart(() => {
  roundStart = now(); roundKills = 0; unlocked.clear();
  points = null; shells.length = 0; bombs.length = 0; tracers.length = 0;
  // pilots and plotters of the last round: the map's aircraft are new entities, so only the pawn is put right (scale, move type, camera)
  for (const p of players.values()) {
    const pw = (p.air || p.inSight || p.hidden) ? pawnOf(p.slot) : undefined;
    p.air = undefined; p.sortie = false;
    if (pw) sanitise(p, pw);
  }
  for (const team of [T, CT]) for (const c of crews[team]) { c.loaded = false; c.loader = -1; c.loaderGen = 0; c.target = null; c.impacts = []; c.cooldown = 0; c.ai = undefined; }
  for (const p of players.values()) { p.deployed = false; p.deployAt = now() + CONFIG.LOBBY_RESPAWN; p.inSight = false; p.carrying = false; p.stowFrom = undefined; p.leashT = 0;
                                      p.outT = 0; p.aiFly = undefined; p.anchor = undefined; }
  directorAt = 0;
  hudEnt = undefined;
  for (const p of players.values()) p.hud.clear();
  Instance.SetThink(think); Instance.SetNextThink(now());
});
Instance.OnPlayerReset(({ player }) => {
  const pawn = live(player); if (!pawn) return;
  const s = slotOfPawn(pawn); if (s < 0) return;
  const p = P(s);
  if (p.air) endFlight(p, pawn, false);        // a respawn while the record still flies (round restart, a missed death)
  sanitise(p, pawn); p.sane = true;
  p.uniformDone = false; p.uniformAt = now() + CONFIG.UNIFORM_DELAY;
  p.deployed = false; p.inSight = false; p.carrying = false; p.sortie = false; p.stowFrom = undefined; p.lastEye = undefined;
  p.deployAt = now() + (p.first ? CONFIG.LOBBY_FIRST : CONFIG.LOBBY_RESPAWN);
  const team = pawn.GetTeamNumber();
  if (team === T || team === CT) {
    if (p.team !== team) { leaveTeam(p, pawn); p.team = team; }
    chooseRole(p, pawn, team);
  }
});
Instance.OnPlayerDisconnect(({ playerSlot }) => {
  const p = players.get(playerSlot);
  if (p) dropPlayer(p);                        // frees the crew seat and the aircraft (it was left hanging in the air with its engine on)
});
Instance.OnPlayerKill(({ player, attacker, inflictor, weapon }) => {
  const victim = live(player); if (!victim) return;
  const vs = slotOfPawn(victim); const vp = vs >= 0 ? P(vs) : undefined;
  if (vp) {
    if (vp.role === "mortar" && vp.crew >= 0) crewDeathLog(vp, victim, attacker, inflictor, weapon);
    vp.streak = 0; vp.upgraded = false; vp.carrying = false; vp.ammo = {};
    if (vp.inSight) leaveSight(vp, victim);
    // a life is spent only by a death in this life's sortie (dying in the briefing room before take-off cost a life before)
    if (vp.role === "air" && vp.sortie) { vp.sortie = false; vp.lives--; if (vp.lives <= 0) toast(vp, "Shot down - back to the ground war", 4); }
  }
  const ap = toPawn(attacker); if (!ap || ap === victim) return;
  const as = slotOfPawn(ap); if (as < 0) return;
  const a = P(as);
  if (ap.GetTeamNumber() === victim.GetTeamNumber()) return;
  roundKills++;
  a.kills++; a.streak++; a.merit++;
  if (a.role === "mortar") { a.mortarKills++; toast(a, "Direct hit!", 2); }
  if (a.role === "infantry" && !a.upgraded && a.streak >= CONFIG.STREAK_UPGRADE && ap.IsAlive()) {
    const team = ap.GetTeamNumber();
    const w = CONFIG.UPGRADE[team];
    const old = ap.FindWeapon(CONFIG.INF_RIFLE[team]); if (old) { try { ap.DestroyWeapon(old); } catch (e) {} }
    if (w && !ap.FindWeapon(w)) ap.GiveNamedItem(w, true);
    a.upgraded = true; a.ammo = {}; stats.upgrades++;
    banner(a, "MARKSMAN", CONFIG.UPGRADE_NAME[team] + " issued.  SHIFT+E or !swap: back to the " + CONFIG.RIFLE_NAME[team], 5);   // the streak reward is a headline
  }
});
// damage guard: pilots in the air only take damage from the enemy (or their own crash), mortar crews in their pit only from enemy players.
// Everything else (props pushing the hidden pilot, falls, world damage at the pit) is dropped and logged to the console.
Instance.OnModifyPlayerDamage((ev) => {
  const v = ev.player; const vs = slotOfPawn(v); if (vs < 0) return;
  const p = players.get(vs); if (!p) return;
  const ap = toPawn(ev.attacker);
  let enemy = false; try { enemy = !!(ap && ap !== v && ap.GetTeamNumber() !== v.GetTeamNumber()); } catch (e) {}
  if (enemy) { aiCombat(vs); aiCombat(slotOfPawn(ap)); }
  let why = "", d = -1;
  if (p.air && !p.crashing && !enemy) why = "pilot";
  else if (p.role === "mortar" && p.crew >= 0 && !enemy && points) {   // points is null for the first tick of a round (threw here before)
    const pit = pitPos(p.team, p.crew), o = v.GetAbsOrigin();
    if (pit) { d = dist2(o, pit); if (d < 320) why = "mortar pit"; }
  }
  if (why) {
    stats.blocked++;
    Console.Log("[tw] blocked " + Math.round(ev.damage) + " damage to " + why + " (slot " + vs + ", types " + ev.damageTypes + ", flags " + ev.damageFlags +
                ", attacker " + entDesc(ev.attacker) + ", inflictor " + entDesc(ev.inflictor) + (d >= 0 ? ", " + Math.round(d) + " u from the tube" : "") + ")");
    return { abort: true };
  }
});
// what killed a mortar crewman (the "crew dies when firing" report): one console line per death with everything the event knows
function crewDeathLog(p, victim, attacker, inflictor, weapon) {
  stats.crewDeaths++;
  let d = -1, station = "?";
  try {
    const o = victim.GetAbsOrigin(), pit = points ? pitPos(p.team, p.crew) : undefined;
    if (pit) d = Math.round(dist2(o, pit));
    station = p.inSight ? "sight" : p.carrying ? "carrying" : "seat " + p.seat;
  } catch (e) {}
  Console.Log("[tw] crew death: slot " + p.slot + " crew " + tagOf(p.team) + "_" + (p.crew + 1) + " (" + station + ", " + d + " u from the tube), attacker " + entDesc(attacker) +
              ", inflictor " + entDesc(inflictor) + ", weapon " + entDesc(weapon) + ", own tube fired " + (now() - (p.firedAt || -99)).toFixed(1) + " s ago");
}
function entDesc(e) {
  if (!e) return "none";
  try { let t = ""; try { t = " team " + e.GetTeamNumber(); } catch (x) {} return e.GetClassName() + ":" + (e.GetEntityName() || "-") + t; } catch (x) { return "?"; }
}
Instance.OnBulletImpact(({ weapon, hitEntity }) => {
  const ac = planeOfEntity(hitEntity); if (!ac) return;
  let owner; try { owner = toPawn(weapon.GetOwner()); } catch (e) {}
  let dmg = 30; try { const d = weapon.GetData(); if (d) dmg = d.GetDamage() || 30; } catch (e) {}
  hitPilot(ac, Math.max(CONFIG.AIR.HIT_MIN, dmg * CONFIG.AIR.HIT_SCALE), owner);
});
Instance.OnPlayerChat(({ player, text }) => {
  if (!player) return;
  const s = player.GetPlayerSlot(); const p = P(s);
  const t = String(text || "").trim().toLowerCase();
  if (t === "!mortar" || t === "!artillery") { p.pref = "mortar"; roleCard(p, "mortar"); if (p.team === T || p.team === CT) requestRole(p, "mortar"); }
  else if (t === "!infantry" || t === "!rifle") { p.pref = "infantry"; roleCard(p, "infantry"); if (p.team === T || p.team === CT) requestRole(p, "infantry"); }
  else if (t === "!air" || t === "!pilot") { p.pref = "air"; roleCard(p, "air"); if (p.team === T || p.team === CT) requestRole(p, "air"); }
  else if (t === "!swap") { const pw = toPawn(player); if (pw && pw.IsAlive()) swapRifle(p, pw); }
  else if (t === "!pos") {
    const pw = toPawn(player); if (pw) {
      const o = pw.GetAbsOrigin();
      say("[tw] " + nameOf(s) + " at x " + Math.round(o.x) + " y " + Math.round(o.y) + " z " + Math.round(o.z) + "  radar square " + radarSquare(o.x, o.y));
    }
  }
  else if (t === "!uniform") {
    // the model changes only in the briefing room (see uniform()): out in the field it waits for the next deploy
    p.noUniform = !p.noUniform;
    const pw = toPawn(player);
    const lobby = !!(pw && pw.IsAlive() && !p.deployed && !p.air && !p.hidden);
    if (p.noUniform) {
      if (lobby && p.stockModel) { try { pw.SetModel(p.stockModel); } catch (e) {} }
      toast(p, "Standard agent model" + (lobby ? "" : " from your next deploy") + " - !uniform to undo", 4);
    }
    else { p.uniformDone = false; p.uniformAt = now(); toast(p, "Period uniform on" + (lobby ? "" : " from your next deploy"), 3); }
  }
  else if (t === "!random") { p.pref = ""; toast(p, "Roles will be chosen for you", 3); }
  else if (t === "!roles") {
    const cnt = (team, r) => { let n = 0; for (const q of players.values()) if (q.team === team && q.role === r) n++; return n; };
    info(p, "COMBAT ROLES", ["INFANTRY (" + cnt(p.team, "infantry") + ")  -  !infantry", "MORTARS (" + cnt(p.team, "mortar") + "/" + (CONFIG.CREWS * 2) + ")  -  !mortar",
      CONFIG.AIR_ENABLED ? "AIRCRAFT (" + cnt(p.team, "air") + "/" + CONFIG.AIR_SLOTS + ")  -  !air" : "", "!swap  -  switch between unlocked primaries"],
      "Type a role's command to see its orders and ask for it.");
  }
});
// radar square of a point on the overview (resource/overviews: pos_x/pos_y = CONFIG.RADAR x0/y0, 1024 px x scale = span), lettered A-P
// across and 1-16 down like tools/make_radar.py's grid
function radarSquare(x, y) {
  const R = CONFIG.RADAR;
  const c = Math.floor((x - R.x0) / R.span * 16), r = Math.floor((R.y0 - y) / R.span * 16);
  return c >= 0 && c < 16 && r >= 0 && r < 16 ? String.fromCharCode(65 + c) + (r + 1) : "off the map";
}
// script reload in the tools (Hammer / -tools): the new script carries the round clock, unlocks, kill count, where each aircraft parks
// and what each player asked for; every pawn is put back on its feet (sanitise) and deploys again (seats and flights are not carried)
if (typeof Instance.OnScriptReload === "function") {
  Instance.OnScriptReload({
    before: () => ({ since: now() - roundStart, roundKills, unlocked: [...unlocked], parks: parkMemo(), reloads: stats.reloads,
                     prefs: [...players.values()].map((p) => ({ slot: p.slot, pref: p.pref, merit: p.merit, flown: p.flown, noUniform: p.noUniform,
                                                              kills: p.kills, mortarKills: p.mortarKills, team: p.team })) }),
    after: (m) => {
      if (m && typeof m === "object") {
        roundStart = now() - (m.since || 0); roundKills = m.roundKills || 0;
        for (const n of m.unlocked || []) unlocked.add(n);
        parkCarry = m.parks || null; stats.reloads = (m.reloads || 0) + 1;
        for (const q of m.prefs || []) {
          const p = P(q.slot);
          p.pref = q.pref || ""; p.merit = q.merit || 0; p.flown = q.flown || 0; p.noUniform = !!q.noUniform; p.kills = q.kills || 0;
          p.mortarKills = q.mortarKills || 0; p.first = false; p.team = q.team || 0;
        }
      } else stats.reloads++;
      points = null; lastTick = now();
      Instance.SetThink(think); Instance.SetNextThink(now());
    },
  });
}
// test seam (test/mock.mjs set pieces; harmless in game): a few internals and the current points
try {
  Object.assign(globalThis.__twDebug, { fireMortar, impact, radarSquare, worldToSight, sightToWorld, pitPos, pickTrench, humansOn, aiWanted });
  Object.defineProperty(globalThis.__twDebug, "points", { get: () => points, configurable: true });
  Object.defineProperty(globalThis.__twDebug, "unlocked", { get: () => unlocked, configurable: true });
  Object.defineProperty(globalThis.__twDebug, "roundKills", { get: () => roundKills, configurable: true });
} catch (e) {}
