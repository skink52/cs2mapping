// 50_roles: roles: crew seats, role choice and requests, loadouts, deploy, uniforms, the streak rifle swap

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
function chooseRole(p, pawn, team) {
  if (isBot(pawn)) { if (p.role !== "infantry") setRole(p, "infantry", team); return; }
  // a pilot keeps flying while lives last, unless he asked for a ground role (it waits for this respawn, see requestRole)
  if (p.role === "air" && p.lives > 0 && (!p.pref || p.pref === "air")) return;
  if (p.role === "air") {
    if (p.pref === "infantry") setRole(p, "infantry", team);
    else if (p.pref === "mortar") setRole(p, seatFree(team) ? "mortar" : "infantry", team);
    else setRole(p, Math.random() < 0.5 && seatFree(team) ? "mortar" : "infantry", team);
    return;
  }
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
// chat role request (the chat command has already made it the preference): in the briefing room it changes the role now if it is
// open; out in the field it waits for the next deploy, as the role cards say (switching at once was a free teleport out of any fight
// with a fresh kit and armour: REVIEW_SCRIPT_1 #2)
function requestRole(p, role) {
  const team = p.team;
  if (p.role === role) return;
  if (p.deployed) { stats.deferred++; return; }
  const open = role === "air" ? airFree(team) : role === "mortar" ? seatFree(team) : true;
  if (!open) { toast(p, role === "air" ? "All aircraft are up - you're next in line" : "Mortar crews are full - you're next in line", 4); return; }
  setRole(p, role, team);
}
// leaving a side (team switch, spectating, disconnect), alive or dead: the crew seat, the aircraft and the sight are given up
function leaveTeam(p, pawn) {
  if (p.air) endFlight(p, pawn, false);
  if (p.inSight) leaveSight(p, pawn);
  leaveSeat(p);
  p.role = null; p.deployed = false; p.sortie = false;
  stats.teamLeft++;
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
function pickTrench(team, pawn, awayFromLocks) {
  const list = points.trench[team];
  if (!list || !list.length) return undefined;
  let best, bestScore = -1e9;
  for (const s of list) {
    if (awayFromLocks && nearLock(s.pos, CONFIG.BOTS.LEASH_AVOID)) continue;   // the leash must not send a bot to a post beside the blocker
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
  if (!best) return awayFromLocks ? pickTrench(team, pawn, false) : undefined;
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
  p.deployed = true; p.deployedAt = now(); p.lastActive = now();
  if (p.role === "air" && !startFlight(p, pawn, dest)) { setRole(p, "infantry", team); deploy(p, pawn); return; }
  stats.deploys[p.role] = (stats.deploys[p.role] || 0) + 1;
  const sub = p.role === "infantry" ? "Hold the fire trench. Dressing stations heal you." :
              p.role === "mortar" ? "Crew " + (p.crew + 1) + ": plot at the table, fetch bombs, load and fire." :
              "Mouse aim, A/D roll, W/S throttle, LMB guns, RMB bomb, E view. " + p.lives + " lives.";
  banner(p, ROLE_NAME[p.role], sub, 5);
}
// the pilot rides inside the aircraft model: shrink the pawn rather than touching its render colour/alpha (changing the render
// mode made the local player's own third-person body and weapon draw in first person)
// soldier model: once per life, a moment after the spawn (the engine sets its own agent on reset), and only in the briefing room:
// never on a shrunk pilot, and never after deploying, when the pawn holds its real weapons (SetModel under drawn weapons is the
// script's only route to the "giant first-person weapon" report; the weapons are issued fresh by deploy, after the model is on)
function uniform(p, pawn, team, t) {
  const list = CONFIG.UNIFORMS[team] || [];
  if (!CONFIG.UNIFORMS_ON || p.noUniform || !list.length || p.uniformDone || t < p.uniformAt) return;
  if (p.air || p.hidden || p.deployed) return;
  p.uniformDone = true;
  try {
    const cur = pawn.GetModelName();
    if (!list.includes(cur)) p.stockModel = cur;
    const m = list[p.slot % list.length];
    if (cur !== m) { pawn.SetModel(m); stats.uniforms++; }
  } catch (e) { Console.Log("[tw] uniform: " + e); }
}
// a pawn the script may have left shrunk, frozen or on a camera (a script reload, a round restart in flight, a record lost with its
// seat): back on its feet. The camera is only touched on a shrunk pawn (GetCustomCamera creates one on demand)
function sanitise(p, pawn) {
  let shrunk = false, frozen = false;
  try { shrunk = pawn.GetModelScale() !== 1; } catch (e) {}
  try { frozen = pawn.GetMoveType() === CSMoveType.NONE; } catch (e) {}
  if (shrunk) {
    try { pawn.SetModelScale(1); } catch (e) {}
    try { const cam = pawn.GetCustomCamera(); if (cam && cam.GetMode() !== CustomCameraMode.DISABLED) cam.SetMode(CustomCameraMode.DISABLED); } catch (e) {}
  }
  if (frozen) { try { pawn.SetMoveType(CSMoveType.WALK); } catch (e) {} }
  p.hidden = false;
  if (shrunk || frozen) stats.sanitised++;
}
function hidePawn(pawn, hide) {
  const p = players.get(slotOfPawn(pawn));
  if (!hide && p && !p.hidden) return;
  try { pawn.SetModelScale(hide ? 0.02 : 1); } catch (e) {}
  if (p) p.hidden = hide;
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
  p.swapAt = now() + 1.5; stats.swaps++;
  toast(p, (other === up ? CONFIG.UPGRADE_NAME[team] : CONFIG.RIFLE_NAME[team]) + " in hand", 2);
}
