// mg_trenchwarfare.js - Western Front role manager (cs_script, no plugins)
// AI-generated (Claude) for skink52's mg_trenchwarfare addon.
//
// Roles: INFANTRY (fire trench, respawn, bolt rifle + pistol + knife, 3-kill streak -> Mondragon / Lewis gun, dressing stations heal),
//        MORTAR (5 crews x 2 per side: plot at the map table, fetch a bomb, load, fire; simulated shells with spread),
//        AIR (5 biplanes per side, arcade flight in third person; pilots posted on respawn or by !air, AIR_LIVES lives, then back to the ground).
// Bots are always infantry. Everyone spawns in the briefing room and is sent to their post after a short delay.
//
// Map entities this script uses (all made by tools/make_map.py):
//   trench_<t|ct>_N (point_teleport)            infantry posts, facing the enemy
//   mortarpit_<t|ct>_K (info_target)            mortar tube position of crew K (1..5); place your mortar prefab there
//   mortarcrew_<t|ct>_K_a / _b (point_teleport) crew seats: a = plotting table, b = ammunition box
//   heal_<t|ct>_N (info_target)                 dressing stations
//   plane_<t|ct>_N (info_teleport_destination)  biplane air-spawn points; tw_plane_<t|ct>_N (prop_dynamic) the aircraft
//   tw_hud (custom_hud_layout), tw_boom_fx_N / tw_dirt_fx_N / tw_boom_snd_N / tw_whistle_snd_N / tw_shake_N (effect pools),
//   tw_launch_snd_<tag>_K / tw_launch_fx_<tag>_K (per mortar pit)

import { Instance, CSInputs, CSMoveType, CSDamageTypes, CustomCameraMode } from "cs_script/point_script";

// ------------------------------------------------------------------ settings
const CONFIG = {
  HUD: "tw_hud",
  RADAR: { x0: -4300, y0: 4700, span: 8601.6 },   // tools/make_radar.py region (overview pos_x/pos_y, 1024 px x scale 8.40)
  LOBBY_FIRST: 4.0,          // seconds in the briefing room on first spawn
  LOBBY_RESPAWN: 1.5,        // ... and after every respawn
  MORTAR_CHANCE: 0.4,        // chance a new player is put on a mortar crew (if a seat is free)
  ROTATE_CHANCE: 0.12,       // on respawn, chance to be moved to the other ground role ("a taste of everything")
  CREWS: 5,
  // WW1 weapons come from the addon's weapons.vdata (models, magazines): T Gewehr 98 = weapon_awp, Luger = weapon_glock;
  // CT Lee-Enfield = weapon_ssg08, Colt M1911 = weapon_hkp2000. Streak upgrade: T Mondragon = weapon_g3sg1, CT Lewis gun = weapon_scar20.
  INF_RIFLE: { 2: "weapon_awp", 3: "weapon_ssg08" },
  INF_PISTOL: { 2: "weapon_glock", 3: "weapon_hkp2000" },
  STREAK_UPGRADE: 3,                   // kills without dying -> upgrade
  UPGRADE: { 2: "weapon_g3sg1", 3: "weapon_scar20" },
  RIFLE_NAME: { 2: "Gewehr 98", 3: "Lee-Enfield" }, UPGRADE_NAME: { 2: "Mondragon self-loader", 3: "Lewis gun" },
  INF_ARMOR: 50,
  HEAL_RADIUS: 120, HEAL_HP_PER_S: 12, HEAL_ARMOR_PER_S: 25,
  STATION_RADIUS: 72,
  TARGET_EXT: 4600,                    // targeting map covers x, y in [-EXT, EXT] (render_top.py EXT); includes the wood
  TARGET_STEPS: 192,
  SIGHT_SPEED: 60, SIGHT_FINE: 14,     // steps per second
  SHELL_RADIUS: 330, SHELL_DAMAGE: 170, TRENCH_COVER: 0.35,
  SPREAD_BASE: 70, SPREAD_PER_UNIT: 0.035,
  FLIGHT_BASE: 2.2, FLIGHT_PER_UNIT: 1 / 1500,
  RELOAD_COOLDOWN: 2.0,
  MORTAR_FIRE_ANIM: "fire",
  FRIENDLY_SPLASH: false,
  POOL: 12,
  AMBIENT_MIN: 4, AMBIENT_MAX: 13, AMBIENT_CLEAR: 550,   // cosmetic no man's land bursts (seconds between, min distance to any player)
  AIR_ENABLED: true, AIR_SLOTS: 5, AIR_LIVES: 2,
  AIR_CHANCE: 0.12,          // on respawn, chance a ground player is posted to the aerodrome (if a plane is free; + merit, + first flight)
  // arcade flight (mouse aim: the plane turns toward where the pilot looks; W/S throttle, A/D roll, LMB guns, RMB bomb)
  AIR: {
    SPAWN_ALT: 1100, V_STALL: 420, V_MIN: 520, V_CRUISE: 1150, V_MAX: 1650, ACCEL: 0.6, DIVE_GAIN: 520,
    TURN_SLOW: 0.45, ROLL_SIGN: 1, PITCH_SIGN: -1, MODEL_YAW: 0,              // models' noses point at +x (Source pitch: positive = nose down)
    // tw33 flight feel ported from the Dogfight addon (steerAim / turnRate / flightStick / boundsWeight / anglesNear / cameraRay),
    // retuned for biplanes: the nose slerps toward the aim (proportional, capped by a speed-dependent turn rate), the bank comes
    // from the yaw rate, A/D add a free roll (no auto level) that never fights the mouse.
    STEER: { RATE: 62, REF_SPEED: 1150, MIN_SPEED: 300, MIN_RATE: 40, MAX_RATE: 75, GAIN: 4, PITCH_LIMIT: 75,
             BANK_GAIN: 0.8, BANK_MAX: 65, BANK_RATE: 150 },
    ROLL: { RATE: 120, IN: 0.15, OUT: 0.10 },
    BOUNDS: { AHEAD: 1.5, HARD: 600, HARD_Z: 400, FAR: 1500, HOME_Z: 2000 },     // soft walls = BOX_X / BOX_Y / ALT_MAX
    NOSE: 90, PULLUP_EVERY: 8, PULLUP_SECONDS: 1.5,
    GUN_GIMBAL: 3,                               // guns converge on the crosshair within this many degrees of the nose
    CAM_BACK_FAST: 440, CAM_TAU: 0.35, CAM_MIN_STEP: 4, CAM_EVERY: 2 / 64, CAM_SNAP: 6, CAM_RETURN: 0.3,   // camera eases back with speed
    GUN_AMMO: 500, GUN_RELOAD: 6, SMOKE_HP: 45,
    COCKPIT: { back: -40, up: 84 }, VIEW_DEFAULT: "chase",                     // "cockpit" also supported (camera at the pilot's head)
    BOX_X: 6500, BOX_Y: 5500, ALT_MAX: 5000, ALT_MIN: 120,
    GUN_INTERVAL: 0.09, GUN_DAMAGE: 16, GUN_RANGE: 5200, GUN_SPREAD: 0.014, GUN_FROM: 150,
    BOMBS: 2, BOMB_REARM: 18, BOMB_RADIUS: 420, BOMB_DAMAGE: 240, GRAVITY: 800,
    BSIGHT_RAISE: 260,                           // bomb-sight ring held this far above the landing point on the line to the camera (one-sided, faces the camera)
    HIT_SCALE: 0.4, HIT_MIN: 12,                 // rifle bullets on a plane: weapon damage x scale (at least HIT_MIN) to the pilot
    CRASH_CREDIT: 10,                            // seconds a hit keeps kill credit for a crash
    CAM_FOLLOW: { x: 0, y: 0, z: 70 }, CAM_OFFSET: { x: -380, y: 0, z: 70 },
    PILOT: { back: -46, up: 30 },                // (hidden) pilot pawn relative to the plane origin: in the cockpit
    TRACER_EVERY: 3, TRACER_SPEED: 9000, SIGHT_DIST: 1600, GUN_SOUND_EVERY: 2,   // effects: every Nth round a tracer / gun sound; gun-sight pip distance
  },
  // soldier player models (tools/soldiers.py; each precached by a hidden prop_dynamic tw_uniform_N under the lobby). Applied a moment
  // after every spawn, picked by player slot. UNIFORMS_ON false = stock agents; players can opt out with !uniform.
  UNIFORMS_ON: true, UNIFORM_DELAY: 0.25,
  UNIFORMS: {
    2: ["models/tw/players/tw_de_a/tw_de_a.vmdl", "models/tw/players/tw_de_b/tw_de_b.vmdl"],   // German
    3: ["models/tw/players/tw_gb_a/tw_gb_a.vmdl", "models/tw/players/tw_gb_b/tw_gb_b.vmdl"],   // British
  },
  // blocked areas opened during the round: every map entity with this targetname is blown open (removed + explosion) at whichever
  // comes first, enemy kills by anyone since the round started or seconds since the round started. Map entities return every round.
  UNLOCKS: [
    { name: "woodsopen", kills: 15, time: 240, msg: "THE WAY TO THE WOOD IS OPEN - ladder at the north end of the fire trench" },
    { name: "undergroundopen", kills: 30, time: 480, msg: "THE MINE GALLERIES ARE OPEN - saps at the south end of the support trench" },
  ],
  CVARS: ["mp_respawn_on_death_t 1", "mp_respawn_on_death_ct 1", "mp_respawn_immunitytime 0", "mp_freezetime 0",
          "mp_roundtime 60", "mp_buy_anywhere 0", "mp_buytime 0", "mp_death_drop_gun 0", "mp_weapons_allow_map_placed 1",
          "mp_free_armor 0", "mp_solid_teammates 1", "bot_quota_mode normal", "mp_give_player_c4 0"],
  // bots (infantry only; the map's nav seeds cover the lobby, trenches, woods clearings and tunnels): a bot that hangs around a
  // still-closed area's blocker (woodsopen / undergroundopen) for LEASH_TIME is sent back to a fire-trench post
  BOTS: { LEASH: 170, LEASH_Z: 160, LEASH_TIME: 3 },
  // off by default (their pathing over the 44k-area nav gave a frame hitch every ~0.5 s on a listen server); true = keep the server's bot_quota
  BOTS_ON: false,
};
const T = 2, CT = 3;
const tagOf = (team) => (team === T ? "t" : "ct");
const ROLE_NAME = { infantry: "INFANTRY", mortar: "TRENCH MORTAR CREW", air: "AIRCREW" };

// ------------------------------------------------------------------ helpers
const now = () => Instance.GetGameTime();
function live(e) { try { return e && e.IsValid() ? e : undefined; } catch (err) { return undefined; } }
function v3(x, y, z) { return { x, y, z }; }
function dist2(a, b) { const dx = a.x - b.x, dy = a.y - b.y; return Math.sqrt(dx * dx + dy * dy); }
function dist3(a, b) { const dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z; return Math.sqrt(dx * dx + dy * dy + dz * dz); }
function gauss() { let u = 0, v = 0; while (u === 0) u = Math.random(); while (v === 0) v = Math.random(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
function toPawn(ent) {
  if (!ent) return undefined;
  try { if (typeof ent.GetPlayerPawn === "function") return live(ent.GetPlayerPawn()); } catch (e) {}
  try { if (typeof ent.GetPlayerController === "function") return live(ent); } catch (e) {}
  return undefined;
}
function pawnOf(slot) { const c = Instance.GetPlayerController(slot); return c ? live(c.GetPlayerPawn()) : undefined; }
function nameOf(slot) { const c = Instance.GetPlayerController(slot); return c ? c.GetPlayerName() : "?"; }
function slotOfPawn(pawn) { try { const c = pawn.GetPlayerController(); return c ? c.GetPlayerSlot() : -1; } catch (e) { return -1; } }
function fire(name, input, value, delay) { Instance.EntFireAtName({ name, input, value, delay: delay || 0 }); }
function say(text) { Instance.ServerCommand("say " + text); }

// named map points (cached per round, map entities are re-created every round)
let points = null;
function findList(prefix, max) {
  const out = [];
  for (let i = 1; i <= max; i++) { const e = live(Instance.FindEntityByName(prefix + i)); if (e) out.push(e); }
  return out;
}
function loadPoints() {
  points = { trench: {}, heal: {}, plane: {}, pit: {}, seatA: {}, seatB: {}, aircraft: {}, locks: {} };
  for (const u of CONFIG.UNLOCKS) {
    points.locks[u.name] = [];
    for (const e of Instance.FindEntitiesByName(u.name)) { try { if (e.IsValid()) points.locks[u.name].push(e.GetAbsOrigin()); } catch (err) {} }
  }
  for (const team of [T, CT]) {
    const tg = tagOf(team);
    points.trench[team] = findList("trench_" + tg + "_", 64).map(e => ({ pos: e.GetAbsOrigin(), ang: e.GetAbsAngles(), used: 0 }));
    points.heal[team] = findList("heal_" + tg + "_", 16).map(e => e.GetAbsOrigin());
    points.plane[team] = findList("plane_" + tg + "_", 16).map(e => ({ pos: e.GetAbsOrigin(), ang: e.GetAbsAngles() }));
    points.aircraft[team] = findList("tw_plane_" + tg + "_", 16).map(e => {
      const n = e.GetEntityName().slice("tw_plane_".length), park = e.GetAbsOrigin();
      const ent = (nm) => live(Instance.FindEntityByName(nm));
      return { ent: e, park, parkAng: e.GetAbsAngles(), pilot: -1, void: v3(park.x, park.y, -3600), ti: 0, si: 0,
               bombEnts: [1, 2].map(k => ent("tw_bomb_" + n + "_" + k)).filter(x => x),
               tracerEnts: [1, 2, 3, 4, 5, 6].map(k => ent("tw_tracer_" + n + "_" + k)).filter(x => x),
               bsight: ent("tw_bombsight_" + n), gsight: ent("tw_gunsight_" + n), spin: 0,
               prop: ent("tw_prop_" + n), hub: undefined };
    });
    points.pit[team] = []; points.seatA[team] = []; points.seatB[team] = [];
    for (let k = 1; k <= CONFIG.CREWS; k++) {
      const pit = live(Instance.FindEntityByName("mortarpit_" + tg + "_" + k)) || live(Instance.FindEntityByName("mortar_" + tg + "_" + k));
      const a = live(Instance.FindEntityByName("mortarcrew_" + tg + "_" + k + "_a"));
      const b = live(Instance.FindEntityByName("mortarcrew_" + tg + "_" + k + "_b"));
      points.pit[team].push(pit ? pit.GetAbsOrigin() : undefined);
      points.seatA[team].push(a ? { pos: a.GetAbsOrigin(), ang: a.GetAbsAngles() } : undefined);
      points.seatB[team].push(b ? { pos: b.GetAbsOrigin(), ang: b.GetAbsAngles() } : undefined);
    }
  }
  const n = (o) => o[T].length + "/" + o[CT].length;
  for (const team of [T, CT]) for (const a of points.aircraft[team]) {
    if (!a.prop) continue;
    const w = a.prop.GetAbsOrigin(), y = a.parkAng.yaw * Math.PI / 180, dx = w.x - a.park.x, dy = w.y - a.park.y;
    a.hub = v3(dx * Math.cos(y) + dy * Math.sin(y), -dx * Math.sin(y) + dy * Math.cos(y), w.z - a.park.z);
    a.propParkAng = a.prop.GetAbsAngles();
  }
  Instance.Msg("[tw] points: trench " + n(points.trench) + ", heal " + n(points.heal) + ", plane spawns " + n(points.plane) + ", aircraft " + n(points.aircraft));
}

// ------------------------------------------------------------------ state
const players = new Map();   // slot -> P
function P(slot) {
  let p = players.get(slot);
  if (!p) {
    p = { slot, role: null, team: 0, crew: -1, seat: "", deployAt: 0, deployed: false, first: true, streak: 0, kills: 0, upgraded: false,
          pref: "", carrying: false, inSight: false, u: 0.5, v: 0.3, prevKeys: 0, lives: 0, merit: 0, flown: 0, toastUntil: 0, bannerUntil: 0, infoUntil: 0,
          healing: false, mortarKills: 0, hud: new Map(), uniformAt: 0, uniformDone: false, noUniform: false, stockModel: "" };
    players.set(slot, p);
  }
  return p;
}
const crews = { [T]: [], [CT]: [] };
function resetCrews() {
  for (const team of [T, CT]) {
    crews[team] = [];
    for (let k = 0; k < CONFIG.CREWS; k++) crews[team].push({ a: -1, b: -1, loaded: false, loader: -1, target: null, cooldown: 0, impacts: [] });
  }
}
resetCrews();
const shells = [];           // in flight
try { globalThis.__twDebug = { players, crews, shells }; } catch (e) {}
let poolIdx = 0;

// ------------------------------------------------------------------ HUD (per-player cache, only changes are sent)
let hudEnt;
function hud() {
  if (live(hudEnt)) return hudEnt;
  hudEnt = live(Instance.FindEntityByName(CONFIG.HUD));
  return hudEnt;
}
function hText(p, id, text) {
  text = String(text === undefined || text === null ? "" : text);
  const k = id + "$";
  if (p.hud.get(k) === text) return;
  const h = hud(); if (!h) return;
  h.SetDialogVariableStringForPlayer(p.slot, id, "v", text);
  p.hud.set(k, text);
}
function hClass(p, id, cls, on) {
  const k = id + "#" + cls;
  if (p.hud.get(k) === on) return;
  const h = hud(); if (!h) return;
  h.SetHasClassForPlayer(p.slot, id, cls, on);
  p.hud.set(k, on);
}
function hSwap(p, id, group, cls) {   // one class per group (marker positions, map picture)
  const k = id + "@" + group;
  const old = p.hud.get(k);
  if (old === cls) return;
  const h = hud(); if (!h) return;
  if (old) h.SetHasClassForPlayer(p.slot, id, old, false);
  if (cls) h.SetHasClassForPlayer(p.slot, id, cls, true);
  p.hud.set(k, cls);
}
function hudReset(p) { const h = hud(); if (h) { try { h.ResetForPlayer(p.slot); } catch (e) {} } p.hud.clear(); }
function toast(p, text, secs) { hText(p, "tw_toast_text", text); p.toastUntil = now() + (secs || 3); }
function info(p, title, lines, foot, secs) {
  hText(p, "tw_info_title", title);
  for (let k = 0; k < 5; k++) hText(p, "tw_info_l" + (k + 1), lines[k] || "");
  hText(p, "tw_info_foot", foot || "");
  p.infoUntil = now() + (secs || 9);
}
function roleCard(p, role) {
  const team = p.team === T || p.team === CT ? p.team : CT;
  if (role === "infantry") return info(p, "INFANTRY", [CONFIG.RIFLE_NAME[team], "Hold the line.", "Earn new equipment with multiple kills.",
    "SHIFT+E / !swap to revert to old weapons."], "You'll go to the fire trench when you next deploy.");
  if (role === "mortar") return info(p, "MORTARS", ["Crews of two.", "Aim on the map table: E, then WASD.", "MOUSE1 lock, SPACE fire.", "Load from the ammo box with E."],
    "You'll join a mortar crew when you next deploy (if a seat is free).");
  if (role === "air") return info(p, "AIRCRAFT", ["!air to nominate to be a pilot.", "Mouse steers, W/S throttle, A/D roll.", "MOUSE1 guns, MOUSE2 bombs.", "2 lives, back to ground."],
    CONFIG.AIR_ENABLED ? "Nominated - you're more likely to be posted to the aerodrome." : "No aircraft yet - noted for later.");
}
function banner(p, title, sub, secs) { hText(p, "tw_banner_title", title); hText(p, "tw_banner_sub", sub); p.bannerUntil = now() + (secs || 5); }

// ------------------------------------------------------------------ roles
function seatFree(team) {
  for (const c of crews[team]) if (c.a < 0 || c.b < 0) return true;
  return false;
}
function takeSeat(p, team) {
  // fill half-empty crews first so pairs form, then a random empty one
  const list = crews[team];
  let pick = -1;
  for (let k = 0; k < list.length; k++) if ((list[k].a < 0) !== (list[k].b < 0)) { pick = k; break; }
  if (pick < 0) {
    const empty = []; for (let k = 0; k < list.length; k++) if (list[k].a < 0 && list[k].b < 0) empty.push(k);
    if (empty.length) pick = empty[Math.floor(Math.random() * empty.length)];
  }
  if (pick < 0) return false;
  const c = list[pick];
  if (c.a < 0) { c.a = p.slot; p.seat = "a"; } else { c.b = p.slot; p.seat = "b"; }
  p.crew = pick;
  return true;
}
function leaveSeat(p) {
  if (p.crew >= 0 && p.team) {
    const c = crews[p.team] && crews[p.team][p.crew];
    if (c) { if (c.a === p.slot) c.a = -1; if (c.b === p.slot) c.b = -1; }
  }
  p.crew = -1; p.seat = ""; p.carrying = false;
}
function setRole(p, role, team) {
  if (p.role === "mortar" && role !== "mortar") leaveSeat(p);
  if (role === "mortar" && (p.role !== "mortar" || p.crew < 0)) { if (!takeSeat(p, team)) role = "infantry"; }
  p.role = role;
  if (role === "air") { p.lives = CONFIG.AIR_LIVES; p.flown++; }
}
function isBot(pawn) { try { return pawn.GetPlayerController().IsBot(); } catch (e) { return false; } }
function nearLock(o) {
  const B = CONFIG.BOTS;
  for (const u of CONFIG.UNLOCKS) {
    if (unlocked.has(u.name)) continue;
    for (const q of (points.locks[u.name] || [])) if (dist2(o, q) < B.LEASH && Math.abs(o.z - q.z) < B.LEASH_Z) return true;
  }
  return false;
}
function tickBot(p, pawn, team, dt) {
  if (p.role !== "infantry" || !nearLock(pawn.GetAbsOrigin())) { p.leashT = 0; return; }
  p.leashT = (p.leashT || 0) + dt;
  if (p.leashT < CONFIG.BOTS.LEASH_TIME) return;
  p.leashT = 0;
  const dest = pickTrench(team, pawn);
  if (dest) pawn.Teleport({ position: v3(dest.pos.x, dest.pos.y, dest.pos.z + 4), angles: dest.ang, velocity: v3(0, 0, 0) });
}
function chooseRole(p, pawn, team) {
  if (isBot(pawn)) { if (p.role !== "infantry") setRole(p, "infantry", team); return; }
  if (p.role === "air" && p.lives > 0) return;
  if (p.role === "air") { setRole(p, Math.random() < 0.5 && seatFree(team) ? "mortar" : "infantry", team); return; }
  if (!p.role) {
    if (p.pref === "air" && airFree(team)) setRole(p, "air", team);
    else if (p.pref === "mortar" && seatFree(team)) setRole(p, "mortar", team);
    else if (p.pref === "infantry") setRole(p, "infantry", team);
    else setRole(p, Math.random() < CONFIG.MORTAR_CHANCE && seatFree(team) ? "mortar" : "infantry", team);
    return;
  }
  if (p.pref === "air" && airFree(team)) { setRole(p, "air", team); return; }
  if (p.pref !== "infantry" && p.pref !== "mortar" && airFree(team) &&
      Math.random() < CONFIG.AIR_CHANCE + 0.03 * Math.min(5, p.merit) + (p.flown === 0 ? 0.08 : 0)) { setRole(p, "air", team); p.merit = 0; return; }
  if (p.pref && p.pref !== "air" && p.pref !== p.role && (p.pref !== "mortar" || seatFree(team))) { setRole(p, p.pref, team); return; }
  if (!p.pref && Math.random() < CONFIG.ROTATE_CHANCE) {
    if (p.role === "infantry" && seatFree(team)) setRole(p, "mortar", team);
    else if (p.role === "mortar") setRole(p, "infantry", team);
  }
}

// aircraft: posted on respawn (chooseRole) or by !air; nobody is pulled out of the fight mid-life
function airFree(team) {
  if (!CONFIG.AIR_ENABLED) return false;
  let n = 0; for (const q of players.values()) if (q.team === team && q.role === "air") n++;
  return n < CONFIG.AIR_SLOTS && (!points || (points.aircraft[team] || []).some(a => live(a.ent) && a.pilot < 0));
}
// chat role request: switch now if the role is open, otherwise it is kept as the preference for the next respawn
function requestRole(p, role) {
  const pawn = pawnOf(p.slot);
  const team = p.team;
  if (p.role === role) return;
  const open = role === "air" ? airFree(team) : role === "mortar" ? seatFree(team) : true;
  if (!open) { toast(p, role === "air" ? "All aircraft are up - you're next in line" : "Mortar crews are full - you're next in line", 4); return; }
  if (p.air && pawn) endFlight(p, pawn, false);
  if (p.inSight) leaveSight(p, pawn);
  setRole(p, role, team);
  if (pawn && pawn.IsAlive() && p.deployed) deploy(p, pawn);
}

// ------------------------------------------------------------------ deploy: loadout + teleport
function equip(p, pawn) {
  try { pawn.DestroyWeapons(); } catch (e) {}
  pawn.GiveNamedItem("weapon_knife", false);
  const team = pawn.GetTeamNumber();
  if (p.role !== "air") pawn.GiveNamedItem(CONFIG.INF_PISTOL[team] || "weapon_p250", false);
  if (p.role === "infantry") {
    pawn.GiveNamedItem(CONFIG.INF_RIFLE[team] || "weapon_ssg08", true);
    pawn.SetArmor(CONFIG.INF_ARMOR); pawn.SetHasHelmet(false);
  } else {
    pawn.SetArmor(100); pawn.SetHasHelmet(true);
  }
  p.upgraded = false;
}
function pickTrench(team, pawn) {
  const list = points.trench[team];
  if (!list || !list.length) return undefined;
  let best, bestScore = -1e9;
  for (const s of list) {
    let crowd = 0;
    for (const q of players.values()) {
      if (q.team !== team || q.role !== "infantry" || !q.deployed) continue;
      const qp = pawnOf(q.slot);
      if (!qp || !qp.IsAlive() || qp === pawn) continue;
      const d = dist2(qp.GetAbsOrigin(), s.pos); if (d < 300) crowd += (300 - d);
    }
    const score = -crowd - s.used * 40 + Math.random() * 60;
    if (score > bestScore) { bestScore = score; best = s; }
  }
  best.used++;
  return best;
}
function deploy(p, pawn) {
  const team = pawn.GetTeamNumber();
  equip(p, pawn);
  let dest;
  if (p.role === "mortar") {
    // don't man a tube alone while another crew is also one short: join them
    const mine = crews[team][p.crew];
    if (mine && (mine.a < 0 || mine.b < 0)) {
      for (let k = 0; k < crews[team].length; k++) {
        const c = crews[team][k];
        if (k === p.crew || !((c.a < 0) !== (c.b < 0))) continue;
        leaveSeat(p);
        if (c.a < 0) { c.a = p.slot; p.seat = "a"; } else { c.b = p.slot; p.seat = "b"; }
        p.crew = k; break;
      }
    }
    dest = (p.seat === "a" ? points.seatA : points.seatB)[team][p.crew];
  }
  else if (p.role === "air") { const l = points.plane[team]; dest = l.length ? l[Math.floor(Math.random() * l.length)] : undefined; }
  if (!dest) dest = pickTrench(team, pawn);
  if (dest) {
    pawn.Teleport({ position: v3(dest.pos.x, dest.pos.y, dest.pos.z + 4), angles: dest.ang, velocity: v3(0, 0, 0) });
    try { pawn.SetEyeAngles(dest.ang); } catch (e) {}
  }
  p.deployed = true;
  if (p.role === "air" && !startFlight(p, pawn, dest)) { setRole(p, "infantry", team); deploy(p, pawn); return; }
  const sub = p.role === "infantry" ? "Hold the fire trench. Dressing stations heal you." :
              p.role === "mortar" ? "Crew " + (p.crew + 1) + ": plot at the table, fetch bombs, load and fire." :
              "Mouse aim, A/D roll, W/S throttle, LMB guns, RMB bomb, E view. " + p.lives + " lives.";
  banner(p, ROLE_NAME[p.role], sub, 5);
}

// ------------------------------------------------------------------ aircraft (arcade, mouse aim)
const bombs = [];
function vadd(a, b, k) { return v3(a.x + b.x * k, a.y + b.y * k, a.z + b.z * k); }
function vlen(a) { return Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z); }
function vnorm(a) { const l = vlen(a) || 1; return v3(a.x / l, a.y / l, a.z / l); }
function vdot(a, b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
function angOf(d) { return { pitch: -Math.asin(Math.max(-1, Math.min(1, d.z))) * 180 / Math.PI, yaw: Math.atan2(d.y, d.x) * 180 / Math.PI, roll: 0 }; }
function park(ac, e) { if (e && live(e)) { try { e.Teleport({ position: ac.void, velocity: v3(0, 0, 0) }); } catch (err) {} } }
const tracers = [];
function tickTracers(dt) {
  for (let i = tracers.length - 1; i >= 0; i--) {
    const r = tracers[i];
    const step = Math.min(r.left, CONFIG.AIR.TRACER_SPEED * dt);
    r.pos = vadd(r.pos, r.dir, step); r.left -= step;
    if (r.left <= 0 || !live(r.ent)) { park(r.ac, r.ent); tracers.splice(i, 1); continue; }
    try { r.ent.Teleport({ position: r.pos, angles: angOf(r.dir) }); } catch (e) {}
  }
}
// where a bomb released now would land: ballistic from the plane's velocity, ground looked up twice
function bombLanding(a) {
  const g = CONFIG.AIR.GRAVITY, p0 = v3(a.pos.x, a.pos.y, a.pos.z - 20), v = v3(a.f.x * a.speed, a.f.y * a.speed, a.f.z * a.speed);
  let gz = groundZ(p0.x, p0.y), x = p0.x, y = p0.y;
  for (let k = 0; k < 2; k++) {
    const h = p0.z - gz; if (h <= 0) break;
    const t = (v.z + Math.sqrt(v.z * v.z + 2 * g * h)) / g;
    x = p0.x + v.x * t; y = p0.y + v.y * t; gz = groundZ(x, y);
  }
  return v3(x, y, gz + 3);
}
function drawSights(a, pawn) {
  const A = CONFIG.AIR, ac = a.ac;
  if (ac.gsight && a.aim) {
    const g = a.aim, d = Math.min(g.dist - 20, A.SIGHT_DIST * 3);
    try { ac.gsight.Teleport({ position: vadd(g.s, g.dir, Math.max(200, d)), angles: angOf(g.dir) }); } catch (e) {}
  }
  if (ac.bsight) {
    if (a.bombs > 0) {
      // the ring sits on the line from the chase camera to the landing point, BSIGHT_RAISE above the ground, facing the camera and
      // scaled down by its distance: the pilot sees it on the landing point, players on the ground below see its undrawn back face
      if (!a.land || a.tick % 4 === 0) a.land = bombLanding(a);
      const l = a.land, h = Math.hypot(a.f.x, a.f.y) || 1, C = A.CAM_OFFSET, back = -(a.camBack || -C.x);
      const cam = v3(a.pos.x + a.f.x / h * back, a.pos.y + a.f.y / h * back, a.pos.z + C.z);
      const d = v3(cam.x - l.x, cam.y - l.y, cam.z - l.z), D = vlen(d) || 1;
      const k = d.z > 1 ? Math.min(A.BSIGHT_RAISE / d.z, 0.6) : 0;
      const pitch = Math.acos(Math.max(-1, Math.min(1, d.z / D))) * 180 / Math.PI, yaw = Math.atan2(d.y, d.x) * 180 / Math.PI;
      try {
        ac.bsight.Teleport({ position: vadd(l, d, k), angles: { pitch, yaw, roll: 0 } });
        ac.bsight.SetModelScale(Math.max(0.2, 1 - k));
      } catch (e) {}
    }
    else park(ac, ac.bsight);
  }
}
// Source AngleVectors: forward / left / up of an entity with these angles
function angleBasis(ang) {
  const p = ang.pitch * Math.PI / 180, y = ang.yaw * Math.PI / 180, r = ang.roll * Math.PI / 180;
  const sp = Math.sin(p), cp = Math.cos(p), sy = Math.sin(y), cy = Math.cos(y), sr = Math.sin(r), cr = Math.cos(r);
  return { f: v3(cp * cy, cp * sy, -sp), l: v3(sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, sr * cp), u: v3(cr * sp * cy + sr * sy, cr * sp * sy - sr * cy, cr * cp) };
}
function dirOf(ang) {
  const p = ang.pitch * Math.PI / 180, y = ang.yaw * Math.PI / 180;
  return v3(Math.cos(p) * Math.cos(y), Math.cos(p) * Math.sin(y), -Math.sin(p));
}
const D2R = Math.PI / 180, R2D = 180 / Math.PI;
function clampN(x, a, b) { return Math.max(a, Math.min(b, x)); }
function vscale(a, k) { return v3(a.x * k, a.y * k, a.z * k); }
function wrap180(x) { return ((x + 180) % 360 + 360) % 360 - 180; }
function finiteV(a) { return !!a && Number.isFinite(a.x) && Number.isFinite(a.y) && Number.isFinite(a.z); }
function angleBetween(a, b) { return Math.acos(clampN(vdot(a, b), -1, 1)); }
// unit f toward unit d by at most maxRad (slerp; nudged off the exact opposite direction)
function rotateToward(f, d, maxRad) {
  let th = angleBetween(f, d);
  if (th < 1e-5) return d;
  if (th > 3.1) { d = vnorm(vadd(d, v3(-f.y * 0.1, f.x * 0.1, 0), 1)); th = angleBetween(f, d); }
  const t = Math.min(1, maxRad / th), s = Math.sin(th);
  return vnorm(vadd(vscale(f, Math.sin((1 - t) * th) / s), d, Math.sin(t * th) / s));
}
function clampPitch(f, limDeg) {
  const L = Math.sin(limDeg * D2R);
  if (Math.abs(f.z) <= L) return f;
  const h = Math.hypot(f.x, f.y) || 1e-6, k = Math.cos(limDeg * D2R) / h;
  return v3(f.x * k, f.y * k, Math.sign(f.z) * L);
}
// the same rotation as a, written continuous with the angles sent last tick (no +180/-180 yaw or roll jumps)
function anglesNear(a, prev) {
  if (!prev || !Number.isFinite(prev.pitch) || !Number.isFinite(prev.yaw) || !Number.isFinite(prev.roll)) return a;
  const un = (x, q) => q + wrap180(x - q);
  const p1 = un(a.pitch, prev.pitch), y1 = un(a.yaw, prev.yaw), r1 = un(a.roll, prev.roll);
  const p2 = un(180 - a.pitch, prev.pitch), y2 = un(a.yaw + 180, prev.yaw), r2 = un(a.roll + 180, prev.roll);
  const c1 = Math.abs(p1 - prev.pitch) + Math.abs(y1 - prev.yaw) + Math.abs(r1 - prev.roll);
  const c2 = Math.abs(p2 - prev.pitch) + Math.abs(y2 - prev.yaw) + Math.abs(r2 - prev.roll);
  return c2 < c1 - 1e-9 ? { pitch: p2, yaw: y2, roll: r2 } : { pitch: p1, yaw: y1, roll: r1 };
}
// turn rate (deg/s) for a speed: brisk when slow, wider when fast, mushy near the stall
function turnRate(v) {
  const A = CONFIG.AIR, S = A.STEER;
  const r = clampN(S.RATE * Math.pow(S.REF_SPEED / Math.max(v, S.MIN_SPEED), 0.6), S.MIN_RATE, S.MAX_RATE);
  return r * clampN((v - A.V_STALL) / (A.V_MIN - A.V_STALL), A.TURN_SLOW, 1);
}
// a digital key as a stick: toward want in tIn seconds, back toward 0 (or through it) in tOut
function flightStick(cur, want, dt, tIn, tOut) {
  const growing = want !== 0 && Math.sign(want) === Math.sign(cur || want) && Math.abs(want) >= Math.abs(cur);
  const rate = 1 / Math.max(1e-3, growing ? tIn : tOut);
  return cur + clampN(want - cur, -rate * dt, rate * dt);
}
// 0 inside the flight box, rising to 1 at the hard wall; looks 1.5 turn radii ahead so the turn home starts in time
function boundsWeight(a) {
  const A = CONFIG.AIR, B = A.BOUNDS;
  const ahead = vadd(a.pos, a.f, B.AHEAD * a.speed / (Math.max(1, turnRate(a.speed)) * D2R));
  let w = 0, kind = "";
  for (const q of [a.pos, ahead]) {
    const wxy = Math.max(Math.abs(q.x) - A.BOX_X, Math.abs(q.y) - A.BOX_Y) / B.HARD, wz = (q.z - A.ALT_MAX) / B.HARD_Z;
    if (wxy > w) { w = wxy; kind = "xy"; }
    if (wz > w) { w = wz; kind = "z"; }
  }
  return { w: clampN(w, 0, 1), kind };
}
function capHeading(f, aim, maxRad) {
  const yf = Math.atan2(f.y, f.x), ya = Math.atan2(aim.y, aim.x);
  const dy = Math.atan2(Math.sin(ya - yf), Math.cos(ya - yf));
  if (Math.abs(dy) <= maxRad || Math.hypot(aim.x, aim.y) < 1e-3) return aim;
  const y = yf + Math.sign(dy) * maxRad, pz = clampN(aim.z, -1, 1), h = Math.sqrt(1 - pz * pz);
  return v3(Math.cos(y) * h, Math.sin(y) * h, pz);
}
function farOutside(pos) {
  const A = CONFIG.AIR, F = A.BOUNDS.FAR;
  return Math.abs(pos.x) > A.BOX_X + F || Math.abs(pos.y) > A.BOX_Y + F || pos.z > A.ALT_MAX + F;
}
// the chase camera's position and view (the crosshair), rebuilt the way FOLLOW_POSITION places it: followed point + offset turned
// by the eye angles; guns converge on what the crosshair covers, within GUN_GIMBAL of the nose
function gunAim(a, pawn) {
  const A = CONFIG.AIR, F = A.CAM_FOLLOW;
  let e; try { e = pawn.GetEyeAngles(); } catch (err) {}
  const B = angleBasis({ pitch: e ? e.pitch : 0, yaw: e ? e.yaw : 0, roll: 0 });
  const back = a.camBack || -A.CAM_OFFSET.x;
  const cam = a.view === "cockpit" ? cockpitPos(a) : vadd(vadd(v3(a.pos.x + F.x, a.pos.y + F.y, a.pos.z + F.z), B.f, -back), B.u, A.CAM_OFFSET.z);
  const L = A.GUN_RANGE + back;
  const tr = Instance.TraceLine({ start: cam, end: vadd(cam, B.f, L), ignoreEntity: [a.ac.ent, pawn], traceHitboxes: true });
  const hitD = tr && tr.didHit ? Math.max(back + 150, tr.fraction * L) : L;
  const pt = vadd(cam, B.f, hitD);
  const s = v3(a.pos.x + a.f.x * A.GUN_FROM, a.pos.y + a.f.y * A.GUN_FROM, a.pos.z + 40 + a.f.z * A.GUN_FROM);
  const want = vnorm(v3(pt.x - s.x, pt.y - s.y, pt.z - s.z));
  const g = A.GUN_GIMBAL * D2R;
  const dir = angleBetween(a.f, want) <= g ? want : rotateToward(a.f, want, g);
  return { s, dir, dist: Math.max(200, Math.min(A.SIGHT_DIST * 3, vlen(v3(pt.x - s.x, pt.y - s.y, pt.z - s.z)))) };
}
function planeOfEntity(e) {
  if (!e || !points) return undefined;
  let nm = ""; try { nm = e.GetEntityName(); } catch (err) { return undefined; }
  if (!nm.startsWith("tw_plane_")) return undefined;
  for (const team of [T, CT]) for (const a of points.aircraft[team] || []) if (a.ent === e || a.ent.GetEntityName() === nm) return a;
  return undefined;
}
function startFlight(p, pawn, dest) {
  const team = pawn.GetTeamNumber();
  const list = (points.aircraft[team] || []).filter(a => live(a.ent));
  const ac = list.find(a => a.pilot === p.slot) || list.find(a => a.pilot < 0);
  if (!ac) { toast(p, "No aircraft free - back to the trenches", 4); return false; }
  ac.pilot = p.slot;
  const A = CONFIG.AIR;
  const base = dest ? dest.pos : ac.park;
  const f = v3(team === CT ? -1 : 1, 0, 0);
  p.air = { ac, pos: v3(base.x, base.y, base.z + A.SPAWN_ALT), f, speed: A.V_CRUISE * 0.9, throttle: 0.7, bank: 0, yawRate: 0,
            phi: 0, stick: 0, roll: 0, angSent: undefined, propSent: undefined, camBack: -A.CAM_OFFSET.x, camSentBack: -A.CAM_OFFSET.x, camSentAt: -99,
            pullUp: false, tick: 0, aim: undefined,
            nextGun: 0, bombs: A.BOMBS, rearmAt: 0, lastHitBy: -1, lastHitAt: -99, warned: 0, ammo: A.GUN_AMMO, reloadAt: 0,
            view: A.VIEW_DEFAULT, cam: undefined, camParent: undefined };
  try { pawn.DestroyWeapons(); pawn.GiveNamedItem("weapon_knife", false); } catch (e) {}
  try { pawn.SetMoveType(CSMoveType.NONE); } catch (e) {}
  hidePawn(pawn, true);                                 // the aircraft carries its own pilot figure; hits on the plane go to the pawn
  try { pawn.SetEyeAngles({ pitch: 0, yaw: team === CT ? 180 : 0, roll: 0 }); } catch (e) {}
  placePlane(p, pawn, true);
  setView(p, pawn);
  const nm = ac.ent.GetEntityName(), tg = nm.slice("tw_plane_".length);
  for (const k of ["eng", "gun", "gun2", "gun3"]) fire("tw_plane_" + k + "_" + tg, "SetSourceEntity", nm);
  fire("tw_plane_eng_" + tg, "StartSound", undefined, 0.05);
  return true;
}
function endFlight(p, pawn, crashed) {
  const a = p.air; if (!a) return;
  p.air = undefined;
  if (crashed) impact({ team: p.team, k: -1, firerSlot: a.lastHitBy >= 0 && now() - a.lastHitAt < CONFIG.AIR.CRASH_CREDIT ? a.lastHitBy : p.slot,
                        x: a.pos.x, y: a.pos.y, z: a.pos.z, radius: 260, damage: 60 });
  if (live(a.ac.ent)) {
    fire("tw_plane_eng_" + a.ac.ent.GetEntityName().slice("tw_plane_".length), "StopSound");
    fire("tw_plane_smoke_" + a.ac.ent.GetEntityName().slice("tw_plane_".length), "Stop");
    a.ac.ent.Teleport({ position: a.ac.park, angles: a.ac.parkAng, velocity: v3(0, 0, 0) });
    if (a.ac.prop && a.ac.hub) {
      const y = a.ac.parkAng.yaw * Math.PI / 180, h = a.ac.hub;
      try { a.ac.prop.Teleport({ position: v3(a.ac.park.x + h.x * Math.cos(y) - h.y * Math.sin(y), a.ac.park.y + h.x * Math.sin(y) + h.y * Math.cos(y), a.ac.park.z + h.z),
                                 angles: a.ac.propParkAng, velocity: v3(0, 0, 0) }); } catch (e) {}
    }
  }
  a.ac.pilot = -1;
  park(a.ac, a.ac.gsight); park(a.ac, a.ac.bsight);
  hClass(p, "tw_fly", "show", false);
  if (pawn && live(pawn)) {
    try { const cam = pawn.GetCustomCamera(); if (cam) { cam.SetMode(CustomCameraMode.DISABLED); if (a.camParent) cam.SetParent(a.camParent); } } catch (e) {}
    try { if (pawn.IsAlive()) pawn.SetMoveType(CSMoveType.WALK); } catch (e) {}
    hidePawn(pawn, false);
  }
}
// the pilot rides inside the aircraft model: shrink the pawn rather than touching its render colour/alpha (changing the render
// mode made the local player's own third-person body and weapon draw in first person)
// soldier model: once per life, a moment after the spawn (the engine sets its own agent on reset)
function uniform(p, pawn, team, t) {
  const list = CONFIG.UNIFORMS[team] || [];
  if (!CONFIG.UNIFORMS_ON || p.noUniform || !list.length || p.uniformDone || t < p.uniformAt) return;
  p.uniformDone = true;
  try {
    const cur = pawn.GetModelName();
    if (!list.includes(cur)) p.stockModel = cur;
    const m = list[p.slot % list.length];
    if (cur !== m) pawn.SetModel(m);
  } catch (e) { Instance.Msg("[tw] uniform: " + e); }
}
function hidePawn(pawn, hide) {
  const p = players.get(slotOfPawn(pawn));
  if (!hide && p && !p.hidden) return;
  try { pawn.SetModelScale(hide ? 0.02 : 1); } catch (e) {}
  if (p) p.hidden = hide;
}
function placePlane(p, pawn, snap) {
  const a = p.air, A = CONFIG.AIR, f = a.f;
  const yaw = Math.atan2(f.y, f.x) * 180 / Math.PI, pitch = Math.asin(Math.max(-1, Math.min(1, f.z))) * 180 / Math.PI;
  const ang = anglesNear({ pitch: A.PITCH_SIGN * pitch, yaw: yaw + A.MODEL_YAW, roll: A.ROLL_SIGN * (a.roll || 0) }, snap ? undefined : a.angSent);
  a.angSent = ang;
  const vel = v3(f.x * a.speed, f.y * a.speed, f.z * a.speed);
  if (snap) a.ac.ent.Teleport({ position: a.pos, angles: ang, velocity: vel });
  else a.ac.ent.Move({ position: a.pos, angles: ang, velocity: vel });
  const ac = a.ac;
  if (ac.prop && ac.hub) {
    ac.spin = (ac.spin + (snap ? 0 : (900 + 1500 * a.throttle) * Math.max(0.005, now() - (a.lastSpin || now())))) % 360;
    a.lastSpin = now();
    const Bq = angleBasis(ang), h = ac.hub;
    const hp = v3(a.pos.x + Bq.f.x * h.x + Bq.l.x * h.y + Bq.u.x * h.z, a.pos.y + Bq.f.y * h.x + Bq.l.y * h.y + Bq.u.y * h.z, a.pos.z + Bq.f.z * h.x + Bq.l.z * h.y + Bq.u.z * h.z);
    const pa = anglesNear({ pitch: ang.pitch, yaw: ang.yaw, roll: ang.roll + ac.spin }, snap ? undefined : a.propSent);
    a.propSent = pa;
    try { if (snap) ac.prop.Teleport({ position: hp, angles: pa, velocity: vel }); else ac.prop.Move({ position: hp, angles: pa, velocity: vel }); } catch (e) {}
  }
  const B = planeBasis(a);
  const hp = vadd(vadd(a.pos, f, -A.PILOT.back), B.u, A.PILOT.up);
  if (snap) pawn.Teleport({ position: hp, velocity: vel }); else pawn.Move({ position: hp, velocity: vel });
}
function crashPilot(p, pawn) {
  const a = p.air;
  const killer = a.lastHitBy >= 0 && now() - a.lastHitAt < CONFIG.AIR.CRASH_CREDIT ? pawnOf(a.lastHitBy) : undefined;
  endFlight(p, pawn, true);
  p.crashing = true;
  try { pawn.TakeDamage({ damage: 1000, damageTypes: CSDamageTypes.BLAST, attacker: killer || pawn, inflictor: killer || pawn }); } catch (e) {}
  p.crashing = false;
}
function hitPilot(ac, damage, attackerPawn) {
  if (!ac || ac.pilot < 0) return;
  const vp = pawnOf(ac.pilot); const p = players.get(ac.pilot);
  if (!vp || !vp.IsAlive() || !p || !p.air) return;
  if (attackerPawn && attackerPawn.GetTeamNumber() === vp.GetTeamNumber()) return;
  const as = attackerPawn ? slotOfPawn(attackerPawn) : -1;
  if (as >= 0) { p.air.lastHitBy = as; p.air.lastHitAt = now(); }
  try { vp.TakeDamage({ damage, attacker: attackerPawn, inflictor: attackerPawn }); } catch (e) {}
}
function tickAir(p, pawn, dt, pressed, held) {
  const a = p.air, A = CONFIG.AIR, t = now();
  if (!live(a.ac.ent)) { endFlight(p, pawn, false); return ""; }
  if (held & CSInputs.FORWARD) a.throttle = Math.min(1, a.throttle + A.ACCEL * dt);
  if (held & CSInputs.BACK) a.throttle = Math.max(0, a.throttle - A.ACCEL * dt);
  // aim: where the pilot looks (raw, every tick); near the walls / ceiling blended toward home, nose down in a stall
  let aim = dirOf(pawn.GetEyeAngles());
  if (!finiteV(aim)) aim = a.f;
  let prompt = "";
  const bw = boundsWeight(a);
  if (bw.w > 0) {
    const home = vnorm(v3(-a.pos.x, -a.pos.y, A.BOUNDS.HOME_Z - a.pos.z));
    // blended by heading and climb separately: a vector sum (or slerp) of two nearly opposite directions points straight up
    const ya = Math.atan2(aim.y, aim.x), yh = Math.atan2(home.y, home.x), y = ya + bw.w * Math.atan2(Math.sin(yh - ya), Math.cos(yh - ya));
    const pz = clampN(aim.z + (clampN(home.z, -0.3, 0.3) - aim.z) * bw.w, -1, 1), hz = Math.sqrt(1 - pz * pz);
    aim = v3(Math.cos(y) * hz, Math.sin(y) * hz, pz);
    prompt = bw.kind === "z" ? "Too high - engine starving" : "Leaving the front - turning back";
  }
  if (a.speed < A.V_STALL) { aim = vnorm(v3(aim.x, aim.y, Math.min(aim.z, -0.5))); prompt = "STALL - nose down"; }
  const gz = groundZ(a.pos.x, a.pos.y);
  // look-ahead pull-up warning (trees, hangars, hills), a few planes per tick
  a.tick++;
  if ((a.tick + p.slot) % A.PULLUP_EVERY === 0) {
    const tr = Instance.TraceLine({ start: a.pos, end: vadd(a.pos, a.f, a.speed * A.PULLUP_SECONDS), ignoreEntity: planeEnts(), ignorePlayers: true });
    a.pullUp = !!(tr && tr.didHit);
  }
  if (!prompt && (a.pullUp || (a.pos.z - gz < 320 && a.f.z < 0.05))) prompt = "PULL UP";
  // steer (Dogfight steerAim): the nose slerps toward the aim, proportional (GAIN) and capped by the turn rate
  // a reversal is flown as a level turn: the aim is held within 90 degrees of the heading (two nearly opposite vectors make
  // the slerp's great circle tip over the top, which a jet can loop but a biplane shouldn't)
  aim = capHeading(a.f, aim, Math.PI / 2);
  const S = A.STEER, R = A.ROLL, sdt = Math.max(dt, 1e-3);
  const wMax = turnRate(a.speed) * D2R;
  const th = angleBetween(a.f, aim);
  const step = bw.w >= 1 ? wMax * sdt : Math.min(wMax * sdt, S.GAIN * th * sdt);
  const yawOld = Math.atan2(a.f.y, a.f.x) * R2D;
  const inside = Math.abs(a.f.z) <= Math.sin(S.PITCH_LIMIT * D2R) + 1e-9;
  const nf = rotateToward(a.f, aim, step);
  if (finiteV(nf)) a.f = inside ? clampPitch(nf, S.PITCH_LIMIT) : nf;
  const yawRate = wrap180(Math.atan2(a.f.y, a.f.x) * R2D - yawOld) / sdt;
  a.yawRate = yawRate * D2R;
  a.bank += clampN(clampN(-yawRate * S.BANK_GAIN, -S.BANK_MAX, S.BANK_MAX) - a.bank, -S.BANK_RATE * sdt, S.BANK_RATE * sdt);
  // A/D: a free roll on top of the bank (no auto level; the mouse steers exactly the same rolled or not)
  const rollWant = bw.w >= 1 ? 0 : ((held & CSInputs.RIGHT) ? 1 : 0) - ((held & CSInputs.LEFT) ? 1 : 0);
  a.stick = flightStick(a.stick, rollWant, sdt, R.IN, R.OUT);
  if (a.stick) a.phi = wrap180(a.phi + a.stick * R.RATE * sdt);
  a.roll = a.phi ? a.phi + a.bank * Math.cos(a.phi * D2R) : a.bank;
  // speed: throttle target, gravity along the flight path
  const target = A.V_MIN + (A.V_MAX - A.V_MIN) * a.throttle;
  a.speed += (target - a.speed) * Math.min(1, dt * 0.6) - A.DIVE_GAIN * a.f.z * dt;
  a.speed = Math.max(A.V_STALL * 0.7, Math.min(A.V_MAX * 1.25, a.speed));
  const np = vadd(a.pos, a.f, a.speed * dt);
  if (!finiteV(np) || farOutside(np)) { crashPilot(p, pawn); return ""; }
  // collision with the world along the step (plus the nose), or the ground
  const tr = Instance.TraceLine({ start: a.pos, end: vadd(np, a.f, A.NOSE), ignoreEntity: planeEnts(), ignorePlayers: true });
  if ((tr && tr.didHit) || np.z < gz + A.ALT_MIN * 0.25) { crashPilot(p, pawn); return ""; }
  a.pos = np;
  placePlane(p, pawn, false);
  easeCamera(a, dt, t);
  a.aim = gunAim(a, pawn);
  if (a.view === "cockpit") { const cam = a.cam; if (cam && live(cam)) { try { cam.Move({ position: cockpitPos(a) }); } catch (e) {} } }
  // guns (belt; a short re-arm when empty)
  if (a.ammo <= 0 && t >= a.reloadAt) { a.ammo = A.GUN_AMMO; }
  if ((held & CSInputs.ATTACK) && t >= a.nextGun && a.ammo > 0) {
    a.nextGun = t + A.GUN_INTERVAL;
    if (--a.ammo <= 0) { a.reloadAt = t + A.GUN_RELOAD; toast(p, "Belt empty - re-arming", 2); }
    if ((a.ammo % A.GUN_SOUND_EVERY) === 0) {
      const gk = ["gun", "gun2", "gun3"][a.ac.si++ % 3];
      fire("tw_plane_" + gk + "_" + a.ac.ent.GetEntityName().slice("tw_plane_".length), "StartSound");
    }
    const s = a.aim.s, d0 = a.aim.dir;
    const dir = vnorm(v3(d0.x + gauss() * A.GUN_SPREAD, d0.y + gauss() * A.GUN_SPREAD, d0.z + gauss() * A.GUN_SPREAD));
    const g = Instance.TraceLine({ start: s, end: vadd(s, dir, A.GUN_RANGE), ignoreEntity: [a.ac.ent, pawn], traceHitboxes: true });
    if ((a.ammo % A.TRACER_EVERY) === 0 && a.ac.tracerEnts.length) {
      const te = a.ac.tracerEnts[a.ac.ti++ % a.ac.tracerEnts.length];
      for (let i = tracers.length - 1; i >= 0; i--) if (tracers[i].ent === te) tracers.splice(i, 1);
      tracers.push({ ent: te, ac: a.ac, pos: s, dir, left: g && g.didHit ? g.fraction * A.GUN_RANGE : A.GUN_RANGE });
    }
    if (g && g.didHit && g.hitEntity) {
      const he = g.hitEntity;
      const ac = planeOfEntity(he);
      if (ac) hitPilot(ac, A.GUN_DAMAGE * 1.5, pawn);
      else {
        const hp = toPawn(he);
        if (hp && hp.IsAlive() && hp.GetTeamNumber() !== pawn.GetTeamNumber()) { try { hp.TakeDamage({ damage: A.GUN_DAMAGE, attacker: pawn, inflictor: pawn }); } catch (e) {} }
      }
    }
  }
  // bombs
  if (a.bombs < A.BOMBS && t >= a.rearmAt) { a.bombs++; a.rearmAt = t + A.BOMB_REARM; }
  let bombKey = (pressed & CSInputs.ATTACK2) !== 0;
  try { bombKey = bombKey || pawn.WasInputJustPressed(CSInputs.ATTACK2); } catch (e) {}
  if (bombKey && a.bombs > 0) {
    a.bombs--; if (a.rearmAt < t) a.rearmAt = t + A.BOMB_REARM;
    const be = a.ac.bombEnts.find(e => !bombs.some(b => b.ent === e));
    bombs.push({ pos: v3(a.pos.x, a.pos.y, a.pos.z - 20), vel: v3(a.f.x * a.speed, a.f.y * a.speed, a.f.z * a.speed), team: pawn.GetTeamNumber(), slot: p.slot, ent: be, ac: a.ac });
    toast(p, "Bomb away!", 1.5);
  }
  const smoking = pawn.GetHealth() <= CONFIG.AIR.SMOKE_HP;
  if (smoking !== !!a.smoking) { a.smoking = smoking; fire("tw_plane_smoke_" + a.ac.ent.GetEntityName().slice("tw_plane_".length), smoking ? "Start" : "Stop"); }
  drawSights(a, pawn);
  drawFlight(p, a, gz);
  return prompt;
}
function planeBasis(a) {
  if (a.angSent) { const B = angleBasis(a.angSent); return { f: B.f, r: vscale(B.l, -1), u: B.u }; }
  const f = a.f;
  let r = v3(f.y, -f.x, 0); const rl = vlen(r);
  r = rl < 1e-3 ? v3(0, -1, 0) : v3(r.x / rl, r.y / rl, 0);
  const u = v3(r.y * f.z - r.z * f.y, r.z * f.x - r.x * f.z, r.x * f.y - r.y * f.x);
  const b = a.bank * Math.PI / 180, c = Math.cos(b), s = Math.sin(b);
  return { f, r: vadd(v3(r.x * c, r.y * c, r.z * c), u, -s), u: vadd(v3(u.x * c, u.y * c, u.z * c), r, s) };
}
function cockpitPos(a) {
  const B = planeBasis(a), C = CONFIG.AIR.COCKPIT;
  return vadd(vadd(a.pos, B.f, -C.back), B.u, C.up);
}
function setView(p, pawn) {
  const a = p.air, A = CONFIG.AIR;
  let cam; try { cam = pawn.GetCustomCamera(); } catch (e) {}
  if (!cam) return;
  a.cam = cam;
  try {
    if (a.view === "cockpit") {
      if (a.camParent === undefined) { try { a.camParent = cam.GetParent() || null; cam.SetParent(undefined); } catch (e) { a.camParent = null; } }
      cam.Teleport({ position: cockpitPos(a) });
      cam.SetMode(CustomCameraMode.CONTROLLED_POSITION);
    } else {
      cam.SetFollowConfig({ followEntity: a.ac.ent, followOffset: A.CAM_FOLLOW, cameraOffset: v3(-(a.camBack || -A.CAM_OFFSET.x), A.CAM_OFFSET.y, A.CAM_OFFSET.z), clipCameraOffset: true, cameraOffsetReturnStrength: A.CAM_RETURN });
      a.camSentBack = a.camBack; a.camSentAt = now();
      cam.SetMode(CustomCameraMode.FOLLOW_POSITION);
    }
  } catch (e) {}
}
// chase camera eases back as the speed rises (Dogfight flightBoostCam): sent only when it moved CAM_MIN_STEP, at most every CAM_EVERY
function easeCamera(a, dt, t) {
  const A = CONFIG.AIR;
  if (a.view === "cockpit" || !a.cam || !live(a.cam)) return;
  const base = -A.CAM_OFFSET.x, fast = clampN((a.speed - A.V_CRUISE) / (A.V_MAX - A.V_CRUISE), 0, 1);
  const want = base + (A.CAM_BACK_FAST - base) * fast;
  a.camBack += (want - a.camBack) * (1 - Math.exp(-Math.max(0, dt) / A.CAM_TAU));
  if (Math.abs(want - a.camBack) <= A.CAM_SNAP) a.camBack = want;
  const moved = Math.abs(a.camBack - a.camSentBack);
  if (moved < 1e-6 || t - a.camSentAt < A.CAM_EVERY - 1e-6 || (moved < A.CAM_MIN_STEP && a.camBack !== want)) return;
  try {
    a.cam.SetFollowConfig({ followEntity: a.ac.ent, followOffset: A.CAM_FOLLOW, cameraOffset: v3(-a.camBack, A.CAM_OFFSET.y, A.CAM_OFFSET.z),
                            clipCameraOffset: true, cameraOffsetReturnStrength: A.CAM_RETURN });
    a.camSentBack = a.camBack; a.camSentAt = t;
  } catch (e) {}
}
const NEEDLE = (deg) => "a" + (((Math.round(deg / 5) % 72) + 72) % 72);
function drawFlight(p, a, gz) {
  const A = CONFIG.AIR, t = now();
  const kmh = a.speed * 0.0254 * 3.6, altm = Math.max(0, (a.pos.z - gz) * 0.0254);
  const hdg = ((Math.atan2(a.f.x, a.f.y) * 180 / Math.PI) + 360) % 360;   // north = +y
  hClass(p, "tw_fly", "show", true);
  hClass(p, "tw_status", "show", false);
  hSwap(p, "tw_n_asi", "rot", NEEDLE(-150 + 300 * Math.min(1, kmh / 300)));
  hSwap(p, "tw_n_alt", "rot", NEEDLE((altm % 1000) / 1000 * 360));
  hSwap(p, "tw_n_rpm", "rot", NEEDLE(-150 + 300 * (0.25 + 0.75 * a.throttle)));
  hSwap(p, "tw_card", "rot", NEEDLE(-hdg));
  hSwap(p, "tw_n_bank", "rot", NEEDLE(wrap180(a.roll || 0)));
  hText(p, "tw_alt_drum", String(Math.floor(altm / 1000)) + " " + String(Math.floor(altm % 1000 / 100)));
  hText(p, "tw_hdg_txt", ("00" + Math.round(hdg) % 360).slice(-3));
  hText(p, "tw_ammo_txt", ("000" + Math.max(0, a.ammo)).slice(-4));
  hClass(p, "tw_bomb1", "on", a.bombs >= 1); hClass(p, "tw_bomb2", "on", a.bombs >= 2);
  hText(p, "tw_fly_info", "LIVES " + p.lives + "   KILLS " + p.kills + (a.ammo <= 0 ? "   RE-ARMING " + Math.max(0, a.reloadAt - t).toFixed(0) : "") +
        (a.bombs < A.BOMBS ? "   BOMB " + Math.max(0, a.rearmAt - t).toFixed(0) + "s" : ""));
}
// upgraded infantry can swap between the streak weapon and their scoped rifle (WALK + USE, or !swap); ammo carries over
function swapRifle(p, pawn) {
  if (!p.upgraded || p.role !== "infantry" || now() < (p.swapAt || 0)) return;
  const team = pawn.GetTeamNumber(), base = CONFIG.INF_RIFLE[team], up = CONFIG.UPGRADE[team];
  const have = pawn.FindWeapon(up) ? up : pawn.FindWeapon(base) ? base : undefined;
  if (!have) return;
  const other = have === up ? base : up;
  const w = pawn.FindWeapon(have);
  p.ammo = p.ammo || {};
  try { p.ammo[have] = [w.GetClipAmmo(), w.GetReserveAmmo()]; } catch (e) {}
  try { pawn.DestroyWeapon(w); } catch (e) {}
  if (!pawn.FindWeapon(other)) pawn.GiveNamedItem(other, true);
  const nw = pawn.FindWeapon(other), saved = p.ammo[other];
  if (nw && saved) { try { nw.SetClipAmmo(saved[0]); nw.SetReserveAmmo(saved[1]); } catch (e) {} }
  p.swapAt = now() + 1.5;
  toast(p, (other === up ? CONFIG.UPGRADE_NAME[team] : CONFIG.RIFLE_NAME[team]) + " in hand", 2);
}
// cosmetic shell bursts and dirt showers in no man's land, never near a player
let nextAmbient = 0;
let roundStart = 0, roundKills = 0; const unlocked = new Set();
function tickUnlocks(t) {
  for (const u of CONFIG.UNLOCKS) {
    if (unlocked.has(u.name) || (roundKills < u.kills && t - roundStart < u.time)) continue;
    unlocked.add(u.name);
    let n = 0;
    for (const e of Instance.FindEntitiesByName(u.name)) {
      try { if (!e.IsValid()) continue; effects(vadd(e.GetAbsOrigin(), v3(0, 0, 1), 24), false); e.Remove(); n++; } catch (err) {}
    }
    if (!n) continue;
    say("[tw] " + u.msg);
    for (const p of players.values()) toast(p, u.msg, 7);
  }
}
function tickAmbient() {
  const t = now(); if (t < nextAmbient) return;
  nextAmbient = t + CONFIG.AMBIENT_MIN + Math.random() * (CONFIG.AMBIENT_MAX - CONFIG.AMBIENT_MIN);
  for (let tries = 0; tries < 6; tries++) {
    const x = (Math.random() * 2 - 1) * 1250, y = (Math.random() * 2 - 1) * 3200;
    let near = false;
    for (let s = 0; s < 64 && !near; s++) { const pw = pawnOf(s); if (pw && pw.IsAlive() && dist2(pw.GetAbsOrigin(), { x, y }) < CONFIG.AMBIENT_CLEAR) near = true; }
    if (near) continue;
    effects(v3(x, y, groundZ(x, y) + 8), true);
    return;
  }
}
function tickBombs(dt) {
  const A = CONFIG.AIR;
  for (let i = bombs.length - 1; i >= 0; i--) {
    const b = bombs[i];
    b.vel.z -= A.GRAVITY * dt;
    const np = vadd(b.pos, b.vel, dt);
    const tr = Instance.TraceLine({ start: b.pos, end: np, ignoreEntity: planeEnts(), ignorePlayers: true });
    if (tr && tr.didHit) {
      bombs.splice(i, 1); if (b.ent) park(b.ac, b.ent);
      impact({ team: b.team, k: -1, firerSlot: b.slot, x: tr.end.x, y: tr.end.y, z: tr.end.z, radius: A.BOMB_RADIUS, damage: A.BOMB_DAMAGE });
    } else if (np.z < -2000) { bombs.splice(i, 1); if (b.ent) park(b.ac, b.ent); }
    else { b.pos = np; if (b.ent) { try { b.ent.Teleport({ position: np, angles: angOf(vnorm(b.vel)) }); } catch (e) {} } }
  }
}

// ------------------------------------------------------------------ mortars
function pitPos(team, k) { return points.pit[team][k] || (points.seatA[team][k] && points.seatA[team][k].pos); }
function sightToWorld(team, u, v) {
  const E = CONFIG.TARGET_EXT;
  if (team === CT) return { x: v * 2 * E - E, y: u * 2 * E - E };       // enemy (-x) at the top
  return { x: E - v * 2 * E, y: E - u * 2 * E };                        // enemy (+x) at the top
}
function worldToSight(team, x, y) {
  const E = CONFIG.TARGET_EXT;
  if (team === CT) return { u: (y + E) / (2 * E), v: (x + E) / (2 * E) };
  return { u: (E - y) / (2 * E), v: (E - x) / (2 * E) };
}
function stepOf(t) { return Math.max(0, Math.min(CONFIG.TARGET_STEPS - 1, Math.floor(t * CONFIG.TARGET_STEPS))); }
let peCache = null, peAt = -1;
function planeEnts() {
  const t = now();
  if (peCache && peAt === t) return peCache;
  const out = [];
  if (points) for (const team of [T, CT]) for (const a of points.aircraft[team] || []) if (live(a.ent)) out.push(a.ent);
  peCache = out; peAt = t;
  return out;
}
function groundZ(x, y) {
  const tr = Instance.TraceLine({ start: v3(x, y, 3000), end: v3(x, y, -600), ignoreEntity: planeEnts(), ignorePlayers: true });
  return tr && tr.didHit ? tr.end.z : 0;
}
function fireMortar(team, k, firerSlot) {
  const c = crews[team][k];
  if (!c.loaded || !c.target || now() < c.cooldown) return false;
  const pit = pitPos(team, k); if (!pit) return false;
  c.loaded = false; c.cooldown = now() + CONFIG.RELOAD_COOLDOWN;
  const tg = tagOf(team) + "_" + (k + 1);
  fire("tw_launch_snd_" + tg, "StartSound");
  fire("mortar_" + tg, "SetAnimation", CONFIG.MORTAR_FIRE_ANIM);       // your mortar prop_dynamic, if it has a fire animation
  fire("tw_launch_fx_" + tg, "Stop"); fire("tw_launch_fx_" + tg, "Start", undefined, 0.02);
  const d = dist2(pit, c.target);
  const sig = CONFIG.SPREAD_BASE + d * CONFIG.SPREAD_PER_UNIT;
  const x = c.target.x + gauss() * sig, y = c.target.y + gauss() * sig;
  const t = now() + CONFIG.FLIGHT_BASE + d * CONFIG.FLIGHT_PER_UNIT;
  shells.push({ team, k, firerSlot, loaderSlot: c.loader === undefined ? -1 : c.loader, x, y, t, whistled: false });
  c.loader = -1;
  for (const s of [c.a, c.b]) if (s >= 0) toast(P(s), "Shot out! Splash in " + (t - now()).toFixed(1) + "s", 2.5);
  return true;
}
function effects(pos, quiet) {
  const i = (poolIdx++ % CONFIG.POOL) + 1;
  for (const nm of ["tw_boom_fx_", "tw_dirt_fx_", "tw_boom_snd_", "tw_shake_"]) {
    const e = live(Instance.FindEntityByName(nm + i)); if (e) e.Teleport({ position: pos });
  }
  fire("tw_boom_fx_" + i, "Stop"); fire("tw_boom_fx_" + i, "Start", undefined, 0.02);
  fire("tw_dirt_fx_" + i, "Stop"); fire("tw_dirt_fx_" + i, "Start", undefined, 0.02);
  fire("tw_boom_snd_" + i, "StartSound", undefined, 0.02);
  if (!quiet) fire("tw_shake_" + i, "StartShake", undefined, 0.02);
}
function impact(sh) {
  const z = sh.z !== undefined ? sh.z : groundZ(sh.x, sh.y);
  const pos = v3(sh.x, sh.y, z + 8);
  effects(pos, false);
  if (sh.k >= 0) { const c = crews[sh.team][sh.k]; c.impacts.unshift({ x: sh.x, y: sh.y }); if (c.impacts.length > 3) c.impacts.length = 3; }
  const R = sh.radius || CONFIG.SHELL_RADIUS, DMG = sh.damage || CONFIG.SHELL_DAMAGE;
  // damage: credited to whoever fired
  const firer = pawnOf(sh.firerSlot);
  for (let s = 0; s < 64; s++) {
    const pawn = pawnOf(s);
    if (!pawn || !pawn.IsAlive()) continue;
    const team = pawn.GetTeamNumber();
    if (team !== T && team !== CT) continue;
    if (team === sh.team && !CONFIG.FRIENDLY_SPLASH) continue;
    const o = pawn.GetAbsOrigin(); const chest = v3(o.x, o.y, o.z + 40);
    const d = dist3(chest, pos);
    if (d > R) continue;
    let k = Math.pow(1 - d / R, 1.2);
    const tr = Instance.TraceLine({ start: v3(pos.x, pos.y, pos.z + 16), end: chest, ignorePlayers: true });
    if (tr && tr.didHit && tr.fraction < 0.98) k *= CONFIG.TRENCH_COVER;
    let dmg = DMG * k;
    if (dmg < 1) continue;
    // the loader lands a non-lethal share first (enough for an assist), the firer the rest (the kill)
    const loader = sh.loaderSlot >= 0 && sh.loaderSlot !== sh.firerSlot ? pawnOf(sh.loaderSlot) : undefined;
    if (loader) {
      const share = Math.min(Math.max(55, dmg * 0.4), pawn.GetHealth() - 1, dmg - 1);
      if (share >= 1) { try { pawn.TakeDamage({ damage: share, damageTypes: CSDamageTypes.BLAST, attacker: loader, inflictor: loader }); } catch (e) {} dmg -= share; }
    }
    if (!pawn.IsAlive()) continue;
    try { pawn.TakeDamage({ damage: dmg, damageTypes: CSDamageTypes.BLAST, attacker: firer, inflictor: firer }); } catch (e) {}
  }
}
function tickShells() {
  const t = now();
  for (let i = shells.length - 1; i >= 0; i--) {
    const sh = shells[i];
    if (!sh.whistled && t >= sh.t - 2.0) {
      sh.whistled = true;
      const w = (poolIdx % CONFIG.POOL) + 1;
      const e = live(Instance.FindEntityByName("tw_whistle_snd_" + w));
      if (e) { e.Teleport({ position: v3(sh.x, sh.y, groundZ(sh.x, sh.y) + 300) }); fire("tw_whistle_snd_" + w, "StartSound"); }
    }
    if (t >= sh.t) { shells.splice(i, 1); impact(sh); }
  }
}

function keys(pawn) {
  let k = 0;
  for (const b of [CSInputs.FORWARD, CSInputs.BACK, CSInputs.LEFT, CSInputs.RIGHT, CSInputs.WALK, CSInputs.USE, CSInputs.ATTACK, CSInputs.ATTACK2, CSInputs.JUMP]) {
    try { if (pawn.IsInputPressed(b)) k |= b; } catch (e) {}
  }
  return k;
}
function enterSight(p, pawn) {
  p.inSight = true;
  try { pawn.SetMoveType(CSMoveType.NONE); } catch (e) {}
  pawn.Teleport({ velocity: v3(0, 0, 0) });
  const c = crews[p.team][p.crew];
  if (c.target) { const s = worldToSight(p.team, c.target.x, c.target.y); p.u = s.u; p.v = s.v; }
  hSwap(p, "tw_tmap", "pic", p.team === CT ? "mct" : "mt");
}
function leaveSight(p, pawn) {
  p.inSight = false;
  if (pawn) { try { pawn.SetMoveType(CSMoveType.WALK); } catch (e) {} }
}
function placeMarker(p, id, u, v, on) {
  hClass(p, id, "on", on);
  if (!on) return;
  hSwap(p, id, "x", "x" + stepOf(u));
  hSwap(p, id + "y", "y", "y" + stepOf(v));
}
function gridRef(u, v) { return String.fromCharCode(65 + Math.min(15, Math.floor(u * 16))) + (1 + Math.min(15, Math.floor(v * 16))); }

function tickMortar(p, pawn, dt, pressed, held) {
  const team = p.team, c = crews[team][p.crew];
  if (!c) return "";
  const pos = pawn.GetAbsOrigin();
  const pit = pitPos(team, p.crew);
  const sA = points.seatA[team][p.crew], sB = points.seatB[team][p.crew];
  if (p.inSight) {
    const sp = (held & CSInputs.WALK) ? CONFIG.SIGHT_FINE : CONFIG.SIGHT_SPEED;
    const st = sp * dt / CONFIG.TARGET_STEPS;
    if (held & CSInputs.FORWARD) p.v -= st;
    if (held & CSInputs.BACK) p.v += st;
    if (held & CSInputs.LEFT) p.u -= st;
    if (held & CSInputs.RIGHT) p.u += st;
    p.u = Math.max(0, Math.min(0.9999, p.u)); p.v = Math.max(0, Math.min(0.9999, p.v));
    if (pressed & CSInputs.ATTACK) {
      c.target = sightToWorld(team, p.u, p.v);
      for (const s of [c.a, c.b]) if (s >= 0) toast(P(s), "Target locked: " + gridRef(p.u, p.v), 2);
    }
    if (pressed & CSInputs.JUMP) {
      if (!fireMortar(team, p.crew, p.slot)) toast(p, c.loaded ? (c.target ? "Wait..." : "Lock a target first (MOUSE 1)") : "Tube is empty - fetch a bomb", 2);
    }
    if (pressed & (CSInputs.USE | CSInputs.ATTACK2)) leaveSight(p, pawn);
    return "";
  }
  // the nearest station within reach wins
  const cand = [];
  if (sA) cand.push({ n: "table", d: dist2(pos, sA.pos), r: CONFIG.STATION_RADIUS });
  if (sB) cand.push({ n: "ammo", d: dist2(pos, sB.pos), r: CONFIG.STATION_RADIUS });
  if (pit) cand.push({ n: "tube", d: dist2(pos, pit) - 15, r: 90 });
  let at = ""; let best = 1e9;
  for (const c2 of cand) if (c2.d < c2.r && c2.d < best) { best = c2.d; at = c2.n; }
  if (at === "table") {
    if (pressed & CSInputs.USE) { enterSight(p, pawn); return ""; }
    return "[E] Use the mortar sight";
  }
  if (at === "ammo") {
    if (c.loaded) return "The mortar is already loaded";
    if (p.carrying) return "Carrying a bomb - load it at the mortar";
    if (pressed & CSInputs.USE) { p.carrying = true; toast(p, "Bomb in hand", 1.5); return ""; }
    return "[E] Take a mortar bomb";
  }
  if (at === "tube") {
    if (p.carrying && !c.loaded) {
      if (pressed & CSInputs.USE) { p.carrying = false; c.loaded = true; c.loader = p.slot; for (const s of [c.a, c.b]) if (s >= 0) toast(P(s), "Mortar loaded", 2); return ""; }
      return "[E] Load the bomb";
    }
    if (c.loaded && c.target) {
      if (pressed & CSInputs.USE) { fireMortar(team, p.crew, p.slot); return ""; }
      return now() < c.cooldown ? "Clearing the tube..." : "[E] FIRE";
    }
    if (c.loaded) return "Loaded - plot a target at the table";
    return "Tube empty - fetch a bomb from the ammunition box";
  }
  return p.carrying ? "Carrying a bomb" : "";
}

function drawSight(p) {
  const c = crews[p.team][p.crew];
  hClass(p, "tw_target", "show", true);
  placeMarker(p, "tw_ret", p.u, p.v, true);
  if (c.target) { const s = worldToSight(p.team, c.target.x, c.target.y); placeMarker(p, "tw_lock", s.u, s.v, true); }
  else placeMarker(p, "tw_lock", 0, 0, false);
  for (let i = 0; i < 3; i++) {
    const im = c.impacts[i];
    if (im) { const s = worldToSight(p.team, im.x, im.y); placeMarker(p, "tw_imp" + i, s.u, s.v, true); }
    else placeMarker(p, "tw_imp" + i, 0, 0, false);
  }
  const pit = pitPos(p.team, p.crew);
  if (pit) { const s = worldToSight(p.team, pit.x, pit.y); placeMarker(p, "tw_pit", s.u, s.v, true); }
  const w = sightToWorld(p.team, p.u, p.v);
  const range = pit ? dist2(pit, w) : 0;
  hText(p, "tw_t_range", "RANGE  " + Math.round(range * 0.0254) + " m");
  hText(p, "tw_t_grid", "GRID  " + gridRef(p.u, p.v) + (c.target ? "   LOCKED" : ""));
  hText(p, "tw_t_tube", "TUBE  " + (c.loaded ? "LOADED" : "EMPTY") + (now() < c.cooldown ? " (clearing)" : ""));
  hText(p, "tw_t_state", c.loaded && c.target ? "READY - JUMP TO FIRE" : (!c.target ? "PLOT A TARGET" : "AWAITING BOMB"));
}

// ------------------------------------------------------------------ per tick
let lastTick = 0;
let errAt = -99;
function logErr(where, e) { const t = now(); if (t - errAt > 2) { errAt = t; Instance.Msg("[tw] error in " + where + ": " + e + (e && e.stack ? " " + e.stack : "")); } }
function think() {
  const t = now(); let dt = t - lastTick; lastTick = t;
  if (!(dt > 0) || dt > 0.1) dt = 1 / 64;
  Instance.SetNextThink(t);                 // scheduled first: an exception below can't stop the script for the rest of the round
  try {
    if (!points) loadPoints();
    tickShells();
    tickBombs(dt);
    tickTracers(dt);
    tickAmbient();
    tickUnlocks(t);
  } catch (e) { logErr("world", e); }
  for (let s = 0; s < 64; s++) { try { thinkPlayer(s, t, dt); } catch (e) { logErr("player " + s, e); } }
}
function thinkPlayer(s, t, dt) {
  {
    const ctl = Instance.GetPlayerController(s);
    if (!ctl) return;
    const pawn = live(ctl.GetPlayerPawn());
    const p = P(s);
    hClass(p, "tw_info", "show", t < (p.infoUntil || 0));
    if (!pawn || !pawn.IsAlive()) { if (p.air) endFlight(p, pawn, true); if (p.inSight) leaveSight(p, pawn); hClass(p, "tw_target", "show", false); hClass(p, "tw_prompt", "show", false); return; }
    const team = pawn.GetTeamNumber();
    if (team !== T && team !== CT) return;
    if (p.team !== team) { leaveSeat(p); p.role = null; p.team = team; p.deployed = false; p.deployAt = t + CONFIG.LOBBY_FIRST; p.uniformDone = false; }
    uniform(p, pawn, team, t);
    const held = keys(pawn); const pressed = held & ~p.prevKeys; p.prevKeys = held;
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
      if (t >= p.deployAt) { hClass(p, "tw_brief", "show", false); p.first = false; deploy(p, pawn); }
      return;
    }
    if (p.air) {
      const pr = tickAir(p, pawn, dt, pressed, held);
      hText(p, "tw_prompt_text", pr); hClass(p, "tw_prompt", "show", !!pr);
      hClass(p, "tw_toast", "show", t < p.toastUntil); hClass(p, "tw_banner", "show", t < p.bannerUntil);
      return;
    }
    if (p.role === "infantry" && p.upgraded && (pressed & CSInputs.USE) && (held & CSInputs.WALK)) swapRifle(p, pawn);
    if (isBot(pawn)) tickBot(p, pawn, team, dt);
    p.healing = false;
    const hp = points.heal[team] || [];
    const o = pawn.GetAbsOrigin();
    for (const h of hp) {
      if (dist2(o, h) < CONFIG.HEAL_RADIUS && Math.abs(o.z - h.z) < 120) {
        p.healing = true;
        const H = pawn.GetHealth();
        p.hacc = (p.hacc || 0) + CONFIG.HEAL_HP_PER_S * dt;
        if (H < 100 && p.hacc >= 1) { const add = Math.floor(p.hacc); p.hacc -= add; pawn.SetHealth(Math.min(100, H + add)); }
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
    hClass(p, "tw_status", "show", true);
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
  for (const c of CONFIG.CVARS) Instance.ServerCommand(c);
  if (!CONFIG.BOTS_ON) { Instance.ServerCommand("bot_quota 0"); Instance.ServerCommand("bot_kick"); }
  points = null; lastTick = now();
  Instance.SetThink(think);
  Instance.SetNextThink(now());
});
Instance.OnRoundStart(() => {
  roundStart = now(); roundKills = 0; unlocked.clear();
  points = null; shells.length = 0; bombs.length = 0; tracers.length = 0;
  for (const p of players.values()) p.air = undefined;
  for (const team of [T, CT]) for (const c of crews[team]) { c.loaded = false; c.loader = -1; c.target = null; c.impacts = []; c.cooldown = 0; }
  for (const p of players.values()) { p.deployed = false; p.deployAt = now() + CONFIG.LOBBY_RESPAWN; p.inSight = false; p.carrying = false; }
  hudEnt = undefined;
  for (const p of players.values()) p.hud.clear();
  Instance.SetThink(think); Instance.SetNextThink(now());
});
Instance.OnPlayerReset(({ player }) => {
  const pawn = live(player); if (!pawn) return;
  const s = slotOfPawn(pawn); if (s < 0) return;
  const p = P(s);
  hidePawn(pawn, false);
  p.uniformDone = false; p.uniformAt = now() + CONFIG.UNIFORM_DELAY;
  p.deployed = false; p.inSight = false; p.carrying = false;
  p.deployAt = now() + (p.first ? CONFIG.LOBBY_FIRST : CONFIG.LOBBY_RESPAWN);
  const team = pawn.GetTeamNumber();
  if (team === T || team === CT) {
    if (p.team !== team) { leaveSeat(p); p.role = null; p.team = team; }
    chooseRole(p, pawn, team);
  }
});
Instance.OnPlayerDisconnect(({ playerSlot }) => {
  const p = players.get(playerSlot);
  if (p) { leaveSeat(p); players.delete(playerSlot); }
});
Instance.OnPlayerKill(({ player, attacker }) => {
  const victim = live(player); if (!victim) return;
  const vs = slotOfPawn(victim); const vp = vs >= 0 ? P(vs) : undefined;
  if (vp) {
    vp.streak = 0; vp.upgraded = false; vp.carrying = false; vp.ammo = {};
    if (vp.inSight) leaveSight(vp, victim);
    if (vp.role === "air") { vp.lives--; if (vp.lives <= 0) toast(vp, "Shot down - back to the ground war", 4); }
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
    a.upgraded = true; a.ammo = {};
    toast(a, CONFIG.UPGRADE_NAME[team] + " issued for your streak!  (SHIFT+E or !swap: back to the " + CONFIG.RIFLE_NAME[team] + ")", 5);
  }
});
// damage guard: pilots in the air only take damage from the enemy (or their own crash), mortar crews in their pit only from enemy players.
// Everything else (props pushing the hidden pilot, falls, world damage at the pit) is dropped and logged to the console.
Instance.OnModifyPlayerDamage((ev) => {
  const v = ev.player; const vs = slotOfPawn(v); if (vs < 0) return;
  const p = P(vs); const ap = toPawn(ev.attacker);
  const enemy = !!(ap && ap !== v && ap.GetTeamNumber() !== v.GetTeamNumber());
  let why = "";
  if (p.air && !p.crashing && !enemy) why = "pilot";
  else if (p.role === "mortar" && p.crew >= 0 && !enemy) {
    const pit = pitPos(p.team, p.crew), o = v.GetAbsOrigin();
    if (pit && dist2(o, pit) < 320) why = "mortar pit";
  }
  if (why) {
    let cls = "?"; try { cls = ev.inflictor ? ev.inflictor.GetClassName() + ":" + ev.inflictor.GetEntityName() : "none"; } catch (e) {}
    Instance.Msg("[tw] blocked " + Math.round(ev.damage) + " damage to " + why + " (slot " + vs + ", types " + ev.damageTypes + ", inflictor " + cls + ")");
    return { abort: true };
  }
});
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
      const o = pw.GetAbsOrigin(), R = CONFIG.RADAR;
      const c = Math.floor((o.x - R.x0) / R.span * 16), r = Math.floor((R.y0 - o.y) / R.span * 16);
      const ok = c >= 0 && c < 16 && r >= 0 && r < 16;
      say("[tw] " + nameOf(s) + " at x " + Math.round(o.x) + " y " + Math.round(o.y) + " z " + Math.round(o.z) + "  radar square " + (ok ? String.fromCharCode(65 + c) + (r + 1) : "off the map"));
    }
  }
  else if (t === "!uniform") {
    p.noUniform = !p.noUniform;
    const pw = toPawn(player);
    if (p.noUniform) { if (pw && pw.IsAlive() && p.stockModel) { try { pw.SetModel(p.stockModel); } catch (e) {} } toast(p, "Standard agent model (!uniform to wear the period uniform again)", 4); }
    else { p.uniformDone = false; p.uniformAt = now(); toast(p, "Period uniform on", 3); }
  }
  else if (t === "!random") { p.pref = ""; toast(p, "Roles will be chosen for you", 3); }
  else if (t === "!roles") {
    const cnt = (team, r) => { let n = 0; for (const q of players.values()) if (q.team === team && q.role === r) n++; return n; };
    info(p, "COMBAT ROLES", ["INFANTRY (" + cnt(p.team, "infantry") + ")  -  !infantry", "MORTARS (" + cnt(p.team, "mortar") + "/" + (CONFIG.CREWS * 2) + ")  -  !mortar",
      CONFIG.AIR_ENABLED ? "AIRCRAFT (" + cnt(p.team, "air") + "/" + CONFIG.AIR_SLOTS + ")  -  !air" : "", "!swap  -  switch between unlocked primaries"],
      "Type a role's command to see its orders and ask for it.");
  }
});
