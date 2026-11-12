// 70_mortar: mortars: sight map, firing, shells, impacts and damage, crew stations, the targeting HUD

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
function fireMortar(team, k, firerSlot) {
  const c = crews[team][k];
  if (!c.loaded || !c.target || now() < c.cooldown) return false;
  const pit = pitPos(team, k); if (!pit) return false;
  c.loaded = false; c.cooldown = now() + CONFIG.RELOAD_COOLDOWN;
  const tg = tagOf(team) + "_" + (k + 1);
  fire("tw_launch_snd_" + tg, "StartSound");
  const tube = live(points.mortar[team][k]);                             // the mortar prop_dynamic, when the map has one (fire animation)
  if (tube) { try { tube.FireInput({ input: "SetAnimation", value: CONFIG.MORTAR_FIRE_ANIM }); } catch (e) {} }
  fire("tw_launch_fx_" + tg, "Stop"); fire("tw_launch_fx_" + tg, "Start", undefined, 0.02);
  const d = dist2(pit, c.target);
  const sig = CONFIG.SPREAD_BASE + d * CONFIG.SPREAD_PER_UNIT;
  const x = c.target.x + gauss() * sig, y = c.target.y + gauss() * sig;
  const t = now() + CONFIG.FLIGHT_BASE + d * CONFIG.FLIGHT_PER_UNIT;
  const fp = players.get(firerSlot);
  shells.push({ team, k, firerSlot, firerGen: fp ? fp.gen : 0, loaderSlot: c.loader === undefined ? -1 : c.loader, loaderGen: c.loaderGen || 0,
                src: "mortar", x, y, t, whistled: false });
  c.loader = -1; c.loaderGen = 0;
  for (const s of [c.a, c.b]) { const q = s >= 0 ? players.get(s) : undefined; if (q) q.firedAt = now(); }
  stats.shots++;
  for (const s of [c.a, c.b]) if (s >= 0) toast(P(s), "Shot out! Splash in " + (t - now()).toFixed(1) + "s", 2.5);
  return true;
}
function effects(pos, quiet) {
  const i = (poolIdx++ % CONFIG.POOL) + 1;
  for (const nm of ["tw_boom_fx_", "tw_dirt_fx_", "tw_boom_snd_", "tw_shake_"]) {
    const e = byName(nm + i); if (e) e.Teleport({ position: pos });
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
  const R = sh.radius || CONFIG.SHELL_RADIUS, DMG = sh.damage || CONFIG.SHELL_DAMAGE, src = sh.src || "mortar";
  stats.impacts++;
  // damage: credited to whoever fired, while he is still that player on that side (creditOf); else nobody
  const firer = creditOf(sh.firerSlot, sh.firerTeam || sh.team, sh.firerGen);
  const loader = sh.loaderSlot >= 0 && sh.loaderSlot !== sh.firerSlot ? creditOf(sh.loaderSlot, sh.team, sh.loaderGen) : undefined;
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
    // the loader lands a non-lethal share first (an assist), the firer the rest (the kill). The share ignores armour: it is meant as
    // health damage, and through armour a 55 share took about half that, under the assist line (CONFIG.ASSIST_MIN, assumed CS2 rule)
    if (loader) {
      const share = Math.floor(Math.min(Math.max(55, dmg * 0.4), pawn.GetHealth() - 1, dmg - 1));
      if (share >= 1) {
        hurt(pawn, { damage: share, damageTypes: CSDamageTypes.BLAST, damageFlags: CSDamageFlags.IGNORE_ARMOR, attacker: loader, inflictor: loader }, src);
        dmg -= share;
        if (share >= CONFIG.ASSIST_MIN) stats.assistShares++;
      }
    }
    if (!pawn.IsAlive()) continue;
    hurt(pawn, { damage: dmg, damageTypes: CSDamageTypes.BLAST, attacker: firer, inflictor: firer }, src);
  }
}
function tickShells() {
  const t = now();
  for (let i = shells.length - 1; i >= 0; i--) {
    const sh = shells[i];
    if (!sh.whistled && t >= sh.t - 2.0) {
      sh.whistled = true;
      const w = (poolIdx % CONFIG.POOL) + 1;
      const e = byName("tw_whistle_snd_" + w);
      if (e) { e.Teleport({ position: v3(sh.x, sh.y, groundZ(sh.x, sh.y) + 300) }); fire("tw_whistle_snd_" + w, "StartSound"); }
    }
    if (t >= sh.t) { shells.splice(i, 1); impact(sh); }
  }
}

function enterSight(p, pawn) {
  p.inSight = true;
  try { pawn.SetMoveType(CSMoveType.NONE); } catch (e) {}
  // MOUSE1 locks the target: with the pistol in hand it also fired the pistol at the table. The knife is drawn while plotting.
  try { const kn = pawn.FindWeaponBySlot(CSGearSlot.KNIFE); if (kn) { p.stowFrom = pawn.GetActiveWeapon(); pawn.SwitchToWeapon(kn); stats.stows++; } } catch (e) {}
  pawn.Teleport({ velocity: v3(0, 0, 0) });
  const c = crews[p.team][p.crew];
  if (c.target) { const s = worldToSight(p.team, c.target.x, c.target.y); p.u = s.u; p.v = s.v; }
  hSwap(p, "tw_tmap", "pic", p.team === CT ? "mct" : "mt");
}
function leaveSight(p, pawn) {
  p.inSight = false;
  if (pawn) {
    try { pawn.SetMoveType(CSMoveType.WALK); } catch (e) {}
    try { const w = live(p.stowFrom); if (w && pawn.IsAlive()) pawn.SwitchToWeapon(w); } catch (e) {}
  }
  p.stowFrom = undefined;
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
      c.target = sightToWorld(team, p.u, p.v); stats.sightLocks++;
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
      if (pressed & CSInputs.USE) { p.carrying = false; c.loaded = true; c.loader = p.slot; c.loaderGen = p.gen; stats.loads++; for (const s of [c.a, c.b]) if (s >= 0) toast(P(s), "Mortar loaded", 2); return ""; }
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
