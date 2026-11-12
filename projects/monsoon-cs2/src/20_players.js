// ------------------------------------------------------------------ 20_players: state, roles, kits, spawn flow, uniforms
const players = new Map();   // slot -> P
const ROLE_NAME = { infantry: "INFANTRY", artillery: "ARTILLERY", air: "AIRCREW" };
function P(slot) {
  let p = players.get(slot);
  if (!p) {
    p = { slot, ctl: null, bot: false, team: 0, role: null, pref: "", waitRole: "", kit: "rifle", deployed: false, deployAt: 0, first: true, spawnSel: "base",
          hud: new Map(), toastUntil: 0, bannerUntil: 0, infoUntil: 0, prevKeys: 0, kills: 0, merit: 0, flown: 0, scripted: false,
          // seats: helicopter (heli + seat index), emplaced gun, battery crew / board
          heli: null, seat: -1, cam: null, camParent: undefined, camKind: "", camBack: 0, camSentBack: 0, camSentAt: -99, hidden: false, moveNone: false,
          mount: -1, crew: -1, board: false, u: 0.5, v: 0.5, msnSel: -1, carrying: "", carryEnt: -1, shellSel: 0,
          holdT: 0, holdKind: "", holdShow: false, atReadyAt: 0, atGiveAt: 0, ropeUntil: 0, noFallUntil: 0,
          uniformAt: 0, uniformDone: false, noUniform: false, stockModel: "", kitNext: "", protectUntil: 0, sane: false,
          afk: false, afkAt: 0, afkEye: 0, afkPos: null, afkCheck: 0, statusAt: 0,
          fired: 0, hits: 0, missions: 0, here: "",
          // bots
          aiRole: "", aiGun: null, leashAt: 0, leashPos: null, leashMoved: 0, lastCombat: -99, deployedAt: 0 };
    players.set(slot, p);
  }
  return p;
}
function teamCount(team, pred) { let n = 0; for (const q of players.values()) if (q.team === team && (!pred || pred(q))) n++; return n; }
function humansOn(team) { return teamCount(team, (q) => !q.bot && !q.afk); }     // AFK humans do not keep the AI out of the seats
function atBase(p, pos) { const c = LAYOUT[tagOf(p.team)].centre; return !!pos && Math.hypot(pos.x - c[0], pos.y - c[1]) < CONFIG.BASE_RADIUS; }

// ------------------------------------------------------------------ roles
function crewOpen(team, human) {
  for (const g of guns[team] || []) {
    if (g.crew.length < CONFIG.ROLES.ARTY_CREW) return true;
    if (human && g.crew.some((s) => { const q = players.get(s); return q && q.bot; })) return true;
  }
  return false;
}
function takeCrew(p, team) {
  const list = guns[team] || [], MAXC = CONFIG.ROLES.ARTY_CREW;
  const humansIn = (g) => g.crew.filter((s) => { const q = players.get(s); return q && !q.bot; }).length;
  let best = null, bestScore = -1;
  for (const g of list) {
    const h = humansIn(g);
    const free = g.crew.length < MAXC || (!p.bot && h < g.crew.length);
    if (!free) continue;
    // pairs form first: a gun with one human is the best seat, then an empty one
    const score = (h === 1 ? 10 : 0) + (g.crew.length === 0 ? 5 : 0) + Math.random();
    if (score > bestScore) { bestScore = score; best = g; }
  }
  if (!best) return false;
  if (best.crew.length >= MAXC) {          // a bot gives its seat to a human
    const bs = best.crew.find((s) => { const q = players.get(s); return q && q.bot; });
    const bq = players.get(bs);
    if (bq) aiRelease(bq, true);
  }
  if (best.crew.length >= MAXC) return false;
  best.crew.push(p.slot); p.crew = best.k;
  return true;
}
function leaveCrew(p) {
  if (p.crew >= 0 && p.team && guns[p.team]) {
    const g = guns[p.team][p.crew];
    if (g) { const i = g.crew.indexOf(p.slot); if (i >= 0) g.crew.splice(i, 1); if (g.aimer === p.slot) g.aimer = -1; }
  }
  dropCarry(p);
  p.crew = -1; p.board = false;
}
function ownHeli(p) { for (const h of helis[p.team] || []) if (h.owner === p.slot) return h; return null; }
function airOpen(team, human) {
  for (const h of helis[team] || []) {
    if (!h.ent) continue;
    if (h.owner < 0) return true;
    const q = players.get(h.owner);
    if (human && q && q.bot) return true;
  }
  return false;
}
// give p a helicopter: a free one, or (for a human) one an AI pilot holds. Returns "ok", "wait" (the AI is bringing it home) or "".
function takeHeli(p, team) {
  const list = (helis[team] || []).filter((h) => h.ent);
  let h = list.find((x) => x.owner === p.slot);
  if (h) return "ok";
  // free ones (and one that was coming home for p whose AI pilot has gone meanwhile: it was locked for the round, review 2);
  // an armed one that is standing on its pad first
  const open = list.filter((x) => x.owner < 0 && (x.yieldTo < 0 || x.yieldTo === p.slot));
  h = open.find((x) => x.state !== "dead" && x.M.ROCKETS > 0) || open.find((x) => x.state !== "dead") || open[0];
  if (h) { h.owner = p.slot; cancelAirWait(p); return "ok"; }
  if (p.bot) return "";
  // one AI helicopter comes home per human: a second !air (or a respawn with the air preference) used to call a second one, and
  // every AI pilot after the first landed and quit for nobody (review 2)
  if (list.some((x) => x.yieldTo === p.slot)) return "wait";
  for (const x of list) {
    const q = players.get(x.owner);
    if (!q || !q.bot) continue;
    if (x.yieldTo >= 0) continue;                                          // already coming home for someone else
    if (x.state === "parked" || x.state === "dead") { aiRelease(q, true); x.owner = p.slot; x.yieldTo = -1; return "ok"; }
    x.yieldTo = p.slot; return "wait";
  }
  return "";
}
// a human who asked for a helicopter the AI was flying and then wants something else: the AI keeps it (it no longer comes home)
function cancelAirWait(p) {
  p.waitRole = "";
  for (const h of helis[p.team] || []) if (h.yieldTo === p.slot) h.yieldTo = -1;
}
function leaveHeliRole(p) { for (const h of helis[p.team] || []) { if (h.owner === p.slot) h.owner = -1; if (h.yieldTo === p.slot) h.yieldTo = -1; } }
function setRole(p, role, team) {
  if (p.role === "artillery" && role !== "artillery") leaveCrew(p);
  if (p.role === "air" && role !== "air") leaveHeliRole(p);
  if (role === "artillery" && (p.role !== "artillery" || p.crew < 0)) { if (!takeCrew(p, team)) role = "infantry"; }
  if (role === "air" && takeHeli(p, team) !== "ok") role = "infantry";
  if (role === "air" && p.role !== "air") p.flown++;
  p.role = role;
  if (role !== "infantry") p.waitRole = "";
}
function chooseRole(p, team) {
  const R = CONFIG.ROLES;
  if (p.bot) { if (!p.aiRole && p.role !== "infantry") setRole(p, "infantry", team); else if (!p.role) setRole(p, "infantry", team); return; }
  if (p.pref === "infantry") { setRole(p, "infantry", team); return; }
  const keepAir = p.role === "air" && !!ownHeli(p), keepArty = p.role === "artillery" && p.crew >= 0;
  if (p.pref === "air" && !keepAir && airOpen(team, true)) { const r = takeHeli(p, team); if (r === "ok") { setRole(p, "air", team); return; } if (r === "wait") p.waitRole = "air"; }
  if (p.pref === "artillery" && !keepArty && crewOpen(team, true)) { setRole(p, "artillery", team); if (p.role === "artillery") return; }
  if (keepAir) return;
  if (keepArty) { if (!p.pref && Math.random() < R.ROTATE_CHANCE) setRole(p, "infantry", team); return; }
  if (!p.pref) {
    if (airOpen(team, false) && Math.random() < R.AIR_CHANCE + R.AIR_MERIT * Math.min(R.AIR_MERIT_MAX, p.merit) + (p.flown === 0 ? R.AIR_FIRST : 0)) {
      setRole(p, "air", team); if (p.role === "air") { p.merit = 0; return; }
    }
    if (crewOpen(team, false) && Math.random() < R.ARTY_CHANCE) { setRole(p, "artillery", team); if (p.role === "artillery") return; }
  }
  setRole(p, "infantry", team);
}
// chat role request: switch now if the role is open and the player is in the briefing room or at the base; out in the field it is
// kept as the preference for the next deploy (a role request is not a way out of a fight or a ride home). force = the AI just
// brought a helicopter home for this player.
function requestRole(p, role, force) {
  const team = p.team;
  if (team !== T && team !== CT) return;
  if (role !== "air" && (p.waitRole === "air" || (helis[team] || []).some((h) => h.yieldTo === p.slot))) {
    cancelAirWait(p);                     // !infantry / !artillery after !air: no helicopter is forced on him when the AI lands (review 2)
    toast(p, "Helicopter request cancelled", 3);
    if (p.role === role) return;
  }
  if (p.role === role && (role !== "air" || ownHeli(p))) { toast(p, "You are " + ROLE_NAME[role].toLowerCase() + " already", 2); return; }
  const pawn0 = pawnOf(p.slot);
  let up = false; try { up = !!pawn0 && pawn0.IsAlive(); } catch (e) {}
  if (!force && up && p.deployed && !((!p.heli || p.heli.landed) && atBase(p, pawn0.GetAbsOrigin()))) {
    stats.roleDeferred++;
    toast(p, ROLE_NAME[role] + " at your next deploy (roles change at the base)", 4); return;
  }
  if (role === "air") {
    const r = takeHeli(p, team);
    if (r === "wait") { p.waitRole = "air"; toast(p, "The AI pilot is bringing a helicopter home for you", 5); return; }
    if (r !== "ok") { toast(p, "All helicopters have pilots - you're next in line", 4); return; }
  }
  if (role === "artillery" && !crewOpen(team, true)) { toast(p, "The battery is fully crewed - you're next in line", 4); return; }
  const pawn = pawn0;
  unseat(p, pawn, "role");
  setRole(p, role, team);
  if (up && p.deployed) deploy(p, pawn);
}
// out of every seat (helicopter, emplaced gun, board); the pawn walks again
function unseat(p, pawn, why) {
  if (p.heli) leaveHeli(p, pawn, why || "");
  if (p.mount >= 0) leaveMount(p, pawn);
  if (p.board) leaveBoard(p, pawn);
  dropCarry(p);
}

// ------------------------------------------------------------------ kits
function kitLimit(team, kit) {
  const K = CONFIG.KITS[kit]; if (!K) return 0;
  const n = teamCount(team);
  if (K.per) return Math.max(1, Math.floor(n / K.per));
  if (K.share) return Math.max(1, Math.floor(n * K.share));
  return 99;
}
function kitFree(p, kit) { return teamCount(p.team, (q) => q !== p && q.kit === kit && q.role === "infantry" && !q.afk) < kitLimit(p.team, kit); }
function kitAllowed(p, kit, atFlag) {
  const K = CONFIG.KITS[kit]; if (!K) return false;
  if (K.flagOnly && !atFlag) return false;
  if (p.kit === kit) return true;
  return kitFree(p, kit);
}
// the kit asked for in the field (p.kitNext) is issued at the next deploy; a limited kit someone else took meanwhile becomes a rifle
function settleKit(p) {
  // bots: one in four carries the MG, one in four is the AT man (he keeps his rifle; the script fires his launcher at helicopters: tickBot)
  if (p.bot && CONFIG.BOT_KITS && p.role === "infantry" && !p.aiRole && p.kit === "rifle") {
    const w = ["rifle", "mg", "rifle", "at"][(p.slot >> 1) % 4];
    if (w === "mg" && kitFree(p, w)) p.kit = w;
    if (w === "at" && kitFree(p, w) && teamCount(p.team, (q) => q.bot && q !== p && q.kit === "at") < CONFIG.AI.AT_BOTS) p.kit = w;
  }
  if (p.kitNext) { if (kitAllowed(p, p.kitNext, false)) p.kit = p.kitNext; p.kitNext = ""; }
  if (!CONFIG.KITS[p.kit] || (p.kit !== "rifle" && p.role === "infantry" && !kitFree(p, p.kit))) { p.kit = "rifle"; stats.kitDenied++; }
}
function setKit(p, pawn, kit, atFlag) {
  if (!kitAllowed(p, kit, atFlag)) { stats.kitDenied++; toast(p, CONFIG.KITS[kit] ? CONFIG.KITS[kit].label + ": all issued (" + kitLimit(p.team, kit) + " per team)" : "No such kit", 3); return false; }
  p.kit = kit; p.kitNext = "";
  if (pawn && pawn.IsAlive() && p.deployed && p.role === "infantry" && !p.heli && p.mount < 0 && !p.board) equip(p, pawn, true);
  toast(p, CONFIG.KITS[kit].label + " - " + CONFIG.KITS[kit].name[p.team], 3);
  return true;
}
function nextKit(p, atFlag) {
  const order = CONFIG.KIT_ORDER, i = order.indexOf(p.kit);
  for (let k = 1; k <= order.length; k++) { const kit = order[(i + k) % order.length]; if (kit !== p.kit && kitAllowed(p, kit, atFlag)) return kit; }
  return "";
}
function give(pawn, cls, deployIt) { try { if (!pawn.FindWeapon(cls)) pawn.GiveNamedItem(cls, !!deployIt); } catch (e) {} }
// fresh = a new issue (deploy, kit change at a rack): armour and a loaded launcher. Otherwise the weapons come back as they were
// (leaving a seat does not reload the AT launcher or mend armour).
function equip(p, pawn, fresh) {
  try { pawn.DestroyWeapons(); } catch (e) {}
  const team = pawn.GetTeamNumber();
  give(pawn, "weapon_knife", false);
  let kit = p.role === "infantry" ? (CONFIG.KITS[p.kit] ? p.kit : "rifle") : "rifle";
  if (fresh && kit === "at") p.atReadyAt = TNOW + (p.bot ? CONFIG.AI.AT_FIRST : 0);
  if (p.bot && kit === "at") kit = "rifle";
  const atWait = p.role !== "air" && kit === "at" && TNOW < p.atReadyAt;
  give(pawn, CONFIG.PISTOL[team] || "weapon_p250", p.role === "air" || atWait);
  if (p.role !== "air") {
    if (atWait) p.atGiveAt = p.atReadyAt;
    else { give(pawn, CONFIG.KITS[kit].weapon[team], true); if (kit === "at") p.atGiveAt = 0; }
  }
  if (fresh) { try { pawn.SetArmor(CONFIG.INF_ARMOR); pawn.SetHasHelmet(CONFIG.INF_HELMET); } catch (e) {} }
}
// a seat that reads MOUSE1 (helicopter, emplaced gun, plotting board): the pawn's own weapons are put away so they do not fire too
function stow(pawn) { try { pawn.DestroyWeapons(); } catch (e) {} give(pawn, "weapon_knife", false); }
// the AT kit: the Zeus is only the trigger. OnGunFire (or ATTACK with it in hand) launches the scripted rocket; the Zeus is re-given after RELOAD.
function fireAT(p, pawn) {
  const A = CONFIG.AT;
  if (p.kit !== "at" || p.role !== "infantry" || TNOW < p.atReadyAt || p.heli || p.mount >= 0) return false;
  p.atReadyAt = TNOW + A.RELOAD; p.atGiveAt = TNOW + A.RELOAD;
  const eye = eyeOf(pawn), dir = dirOf(eye);
  let from; try { from = pawn.GetEyePosition(); } catch (e) {}
  if (!finiteV(from)) { const o = pawn.GetAbsOrigin(); from = v3(o.x, o.y, o.z + 60); }
  launchRocket({ pos: vadd(from, dir, 40), vel: vscale(dir, A.SPEED), team: p.team, slot: p.slot, grav: A.GRAVITY, blast: A.BLAST, damage: A.DAMAGE,
                 heli: A.HELI, life: A.LIFE, gunRadius: A.GUN_DISABLE, ignore: pawn, src: "at" });
  toast(p, CONFIG.KITS.at.name[p.team] + " away - reloading " + A.RELOAD + " s", 2.5);
  return true;
}
function tickAT(p, pawn, pressed) {
  if (p.kit !== "at" || p.role !== "infantry") return;
  if (p.atGiveAt && TNOW >= p.atGiveAt) {
    p.atGiveAt = 0;
    try { const w = pawn.FindWeapon("weapon_taser"); if (w) pawn.DestroyWeapon(w); } catch (e) {}
    give(pawn, "weapon_taser", false);
    toast(p, CONFIG.KITS.at.name[p.team] + " reloaded", 2);
  }
  if ((pressed & CSInputs.ATTACK) && TNOW >= p.atReadyAt) {
    let cls = ""; try { const w = pawn.GetActiveWeapon(); cls = w ? w.GetClassName() : ""; } catch (e) {}
    if (cls === "weapon_taser") fireAT(p, pawn);
  }
}

// ------------------------------------------------------------------ uniforms (only models a cache prop holds)
const cachedModels = new Set();
function loadUniforms() {
  cachedModels.clear();
  for (let i = 1; i <= CONFIG.CACHE_PROPS; i++) {
    const e = /** @type {any} */ (ent("mv_cache_" + i)); if (!e) continue;
    try { const m = e.GetModelName(); if (m) cachedModels.add(m); } catch (err) {}
  }
}
function uniform(p, pawn, team) {
  if (!CONFIG.UNIFORMS_ON || p.noUniform || p.uniformDone || TNOW < p.uniformAt) return;
  p.uniformDone = true;
  const list = (CONFIG.UNIFORMS[team] || []).filter((m) => cachedModels.has(m));
  if (!list.length) return;
  try {
    const cur = pawn.GetModelName();
    if (!list.includes(cur)) p.stockModel = cur;
    const m = list[p.slot % list.length];
    if (cur !== m) pawn.SetModel(m);
  } catch (e) { log("uniform: " + e); }
}
// a pawn this script has not seen before (new player, a slot that changed hands, the script reloaded in the tools): make sure nothing
// an earlier script state did to it is left (shrunk, frozen, a seat camera)
function sanitise(p, pawn) {
  p.sane = true;
  if (p.heli || p.mount >= 0 || p.board) return;
  try { pawn.SetModelScale(1); pawn.SetMoveType(CSMoveType.WALK); } catch (e) {}
  try { const cam = typeof pawn.GetCustomCamera === "function" ? pawn.GetCustomCamera() : undefined; if (cam) cam.SetMode(CustomCameraMode.DISABLED); } catch (e) {}
  p.hidden = false; p.moveNone = false;
}
// a seated pawn rides inside the model: shrink it rather than touching its render mode (mg_trenchwarfare)
function hidePawn(p, pawn, hide) {
  if (!pawn || p.hidden === hide) return;
  try { pawn.SetModelScale(hide ? 0.02 : 1); } catch (e) {}
  p.hidden = hide;
}
function freeze(p, pawn, on) {
  if (!pawn || p.moveNone === on) return;
  try { pawn.SetMoveType(on ? CSMoveType.NONE : CSMoveType.WALK); } catch (e) {}
  p.moveNone = on;
}

// ------------------------------------------------------------------ deploy: where, loadout, teleport
let points = null;
function listOf(prefix, max) { const out = []; for (let i = 1; i <= max; i++) { const e = ent(prefix + i); if (e) out.push({ pos: e.GetAbsOrigin(), ang: e.GetAbsAngles(), used: 0 }); } return out; }
function loadPoints() {
  points = { spawn: {}, flagspawn: {}, kit: [], tunnels: listOf("mv_tunnel_", 3) };
  for (const team of TEAMS) {
    const tg = tagOf(team);
    points.spawn[team] = listOf("mv_spawn_" + tg + "_", 16);
    if (!points.spawn[team].length) need("mv_spawn_" + tg + "_1");
    const k = posOf("mv_kit_" + tg); if (k) points.kit.push({ pos: k, team, flag: "" });
  }
  for (const f of LAYOUT.flags) {
    points.flagspawn[f.id] = listOf("mv_flagspawn_" + f.id + "_", 8);
    if (!points.flagspawn[f.id].length) need("mv_flagspawn_" + f.id + "_1");
    const k = posOf("mv_kit_" + f.id); if (k) points.kit.push({ pos: k, team: 0, flag: f.id });
  }
  loadUniforms();
  loadFlags(); loadHelis(); loadGuns(); loadMounts();
  log("points: spawns " + points.spawn[T].length + "/" + points.spawn[CT].length + ", helicopters " + helis[T].length + "/" + helis[CT].length +
      ", guns " + guns[T].length + "/" + guns[CT].length + ", mounts " + mounts.length + ", uniforms cached " + cachedModels.size);
}
function leastCrowded(list, team) {
  let best, bestScore = -1e9;
  for (const s of list) {
    let crowd = 0;
    for (const r of roster) if (r.team === team && r.alive && r.p.deployed) { const d = dist2(r.pos, s.pos); if (d < 200) crowd += 200 - d; }
    const score = -crowd - s.used * 30 + Math.random() * 50;
    if (score > bestScore) { bestScore = score; best = s; }
  }
  if (best) best.used++;
  return best;
}
// a flag is a deploy point for its owner while no enemy stands inside its circle (reinforcements do not appear on top of an attack:
// that froze every capture and no flag ever changed hands twice in the simulations)
function flagOpen(f, team) { return !!f && f.owner === team && !(f.n[otherTeam(team)] > 0) && !!points && points.flagspawn[f.id].length > 0; }
// deploy choices for the lobby prompt: base, every held flag, and a waiting transport
function spawnChoices(p) {
  const out = ["base"];
  for (const f of flags) if (flagOpen(f, p.team)) out.push(f.id);
  if ((helis[p.team] || []).some((h) => h.state === "parked" && h.ent && freeSeat(h, false) >= 0 && h.seats[0].slot >= 0)) out.push("heli");
  return out;
}
function spawnLabel(sel) {
  if (sel === "base") return "BASE";
  if (sel === "heli") return "ABOARD A WAITING HELICOPTER";
  const f = flagById(sel); return f ? f.id.toUpperCase() + " " + f.name.toUpperCase() : "BASE";
}
function spawnPoint(p, team) {
  const sel = p.bot ? botSpawnChoice(p, team) : p.spawnSel;
  const f = flagById(sel);
  if (flagOpen(f, team)) { if (!p.bot) stats.flagSpawns++; return leastCrowded(points.flagspawn[f.id], team); }
  if (f && f.owner === team && !p.bot) toast(p, f.id.toUpperCase() + " " + f.name + " is under attack: deploying at the base", 4);
  return leastCrowded(points.spawn[team], team);
}
function place(pawn, dest, lift) {
  if (!dest) return;
  try {
    pawn.Teleport({ position: v3(dest.pos.x, dest.pos.y, dest.pos.z + (lift === undefined ? 4 : lift)), angles: dest.ang, velocity: v3(0, 0, 0) });
    if (dest.ang) pawn.SetEyeAngles(dest.ang);
  } catch (e) {}
}
function deploy(p, pawn) {
  const team = pawn.GetTeamNumber();
  unseat(p, pawn, "deploy");
  freeze(p, pawn, false); hidePawn(p, pawn, false);
  settleKit(p);
  equip(p, pawn, true);
  p.deployed = true; p.deployedAt = TNOW; p.first = false; p.leashAt = TNOW; p.leashPos = null; p.leashMoved = TNOW;
  p.protectUntil = TNOW + CONFIG.SPAWN_PROTECT; p.afkAt = TNOW; p.afkPos = null;
  let sub = "";
  if (p.bot && p.aiRole) { place(pawn, leastCrowded(points.spawn[team], team)); aiDeploy(p, pawn); return; }
  if (p.role === "artillery" && p.crew >= 0) {
    const g = guns[team][p.crew];
    place(pawn, g.seat || leastCrowded(points.spawn[team], team));
    sub = "Gun " + (g.k + 1) + ": take a round at the rack, load it at the " + (team === T ? "rail" : "breech") + ", aim at the board. All with E.";
  } else if (p.role === "air") {
    const h = ownHeli(p);
    if (!h) { setRole(p, "infantry", team); deploy(p, pawn); return; }
    const B = angleBasis({ pitch: 0, yaw: h.pad.yaw, roll: 0 });
    place(pawn, { pos: local(h.pad.pos, B, [0, 190, 0]), ang: { pitch: 0, yaw: h.pad.yaw, roll: 0 } }, 8);
    if (h.state === "parked") enterHeli(p, pawn, h, 0);
    sub = h.state === "dead" ? "Your helicopter is being replaced - wait at the pad." : "SPACE up, CTRL down, mouse turns, WASD moves. E gets out when landed.";
  } else {
    if (!p.bot && p.spawnSel === "heli") {
      const h = (helis[team] || []).find((x) => x.state === "parked" && x.ent && freeSeat(x, false) >= 0 && x.seats[0].slot >= 0);
      if (h) { place(pawn, { pos: h.pad.pos, ang: { pitch: 0, yaw: h.pad.yaw, roll: 0 } }, 8); if (enterHeli(p, pawn, h, freeSeat(h, false))) stats.spawnAboard++; }
      else place(pawn, leastCrowded(points.spawn[team], team));
    } else place(pawn, spawnPoint(p, team));
    sub = CONFIG.KITS[p.kit].name[team] + ". Take flags. Hold E on far ground to call artillery. E at a helicopter to ride.";
  }
  if (!p.bot) banner(p, ROLE_NAME[p.role] + (p.role === "infantry" ? " - " + CONFIG.KITS[p.kit].label : ""), sub, 6);
}
