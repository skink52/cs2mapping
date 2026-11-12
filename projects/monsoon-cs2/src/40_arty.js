// ------------------------------------------------------------------ 40_arty: fire missions, the board, laying, loading, shells, counter-battery
const guns = { 2: [], 3: [] };
const missions = { 2: [], 3: [] };     // fire missions called by that team's players
const flashes = { 2: [], 3: [] };      // enemy gun flashes that team's board shows
const shells = [];
const boardPos = { 2: undefined, 3: undefined };
let missionSeq = 0;
const BOARD_EXT = Number.isFinite(HUDDATA.board_ext) ? HUDDATA.board_ext : CONFIG.BOARD.EXT;
const BOARD_STEPS = Number.isFinite(HUDDATA.board_steps) ? HUDDATA.board_steps : CONFIG.BOARD.STEPS;

function loadGuns() {
  const A = CONFIG.ARTY;
  for (const team of TEAMS) {
    guns[team] = []; missions[team] = []; flashes[team] = [];
    const tg = tagOf(team), lay = LAYOUT[tg];
    boardPos[team] = posOf("mv_board_" + tg);
    for (let k = 0; k < A.GUNS[team]; k++) {
      const tag = tg + "_" + (k + 1);
      const car = need("mv_gun_" + tag), tube = need("mv_tube_" + tag), round = team === T ? need("mv_round_t_" + (k + 1)) : undefined;
      const pos = car ? car.GetAbsOrigin() : v3(lay.guns[k] ? lay.guns[k][0] : lay.centre[0], lay.guns[k] ? lay.guns[k][1] : lay.centre[1], lay.z);
      const yaw0 = car ? car.GetAbsAngles().yaw : Math.atan2(-pos.y, -pos.x) * R2D;
      const gm = LAYOUT.models && LAYOUT.models[team === T ? "rocket" : "howitzer"];      // the map's gun model (tools/mv_models.py)
      let tubeOff = gm && Array.isArray(gm.trunnion) && gm.trunnion.length === 3 && gm.trunnion.every(Number.isFinite) ? gm.trunnion : [0, 0, 40];
      if (tube) { const o = toLocal(pos, angleBasis({ pitch: 0, yaw: yaw0, roll: 0 }), tube.GetAbsOrigin()); if (Math.hypot(o[0], o[1], o[2]) < 300) tubeOff = o; }
      need("mv_gun_snd_" + tag); need("mv_gun_fx_" + tag);
      guns[team].push({ team, k, tag, pos, ent: car, tube, round, rack: posOf("mv_rack_" + tag), seat: poseOf("mv_boardseat_" + tag), tubeOff,
                        yaw: yaw0, pitch: 0, yaw0, target: null, mission: -1, lay: "idle", fromYaw: yaw0, fromPitch: 0, toYaw: yaw0, toPitch: 0, layStart: 0, layEnd: 0,
                        loaded: [], loader: -1, aimer: -1, crew: [], disabledUntil: 0, puffAt: 0, recoilAt: -99, cooldown: 0, salvo: 0, salvoAt: 0, salvoBy: -1,
                        impacts: [], ai: null, sentYaw: NaN, sentPitch: NaN, sentRec: NaN, roundShown: false, extraSigma: 0, graceUntil: 0 });
    }
  }
  shells.length = 0;
}
function gunDisabled(g) { return TNOW < g.disabledUntil; }
function tubePose(g, rec) {
  const B = angleBasis({ pitch: 0, yaw: g.yaw, roll: 0 });
  const axis = dirOf({ pitch: -g.pitch, yaw: g.yaw, roll: 0 });
  return { pos: vadd(local(g.pos, B, g.tubeOff), axis, -rec), ang: { pitch: -g.pitch, yaw: g.yaw, roll: 0 }, axis };
}
function placeGun(g, rec, snap) {
  const showRound = !!g.round && g.loaded.length > 0;
  if (!snap && Math.abs(g.yaw - g.sentYaw) < 0.02 && Math.abs(g.pitch - g.sentPitch) < 0.02 && Math.abs(rec - g.sentRec) < 0.05 && showRound === g.roundShown) return;
  const yawMoved = g.yaw !== g.sentYaw;
  g.sentYaw = g.yaw; g.sentPitch = g.pitch; g.sentRec = rec;
  const tp = tubePose(g, rec);
  try {
    if (g.ent && (yawMoved || snap)) g.ent.Move({ angles: { pitch: 0, yaw: g.yaw, roll: 0 } });
    if (g.tube) g.tube.Move({ position: tp.pos, angles: tp.ang });
    if (g.round) {
      if (showRound) { const rp = vadd(tp.pos, tp.axis, 20); if (g.roundShown) g.round.Move({ position: rp, angles: tp.ang }); else g.round.Teleport({ position: rp, angles: tp.ang }); }
      else if (g.roundShown) parkEnt(g.round, 60 + g.k);
      g.roundShown = showRound;
    }
  } catch (e) {}
}
function setTarget(g, target, missionId) {
  const A = CONFIG.ARTY;
  const range = dist2(g.pos, target), yawTo = Math.atan2(target.y - g.pos.y, target.x - g.pos.x) * R2D;
  const direct = g.loaded[g.loaded.length - 1] === "beehive" && range <= A.BEEHIVE.RANGE;
  const elev = direct ? 1 : A.ELEV_MIN + (A.ELEV_MAX - A.ELEV_MIN) * clampN(range / A.RANGE_MAX, 0, 1);
  const turn = Math.max(Math.abs(wrap180(yawTo - g.yaw)), Math.abs(elev - g.pitch));
  g.target = { x: target.x, y: target.y, z: target.z || 0, range }; g.mission = missionId === undefined ? -1 : missionId;
  g.fromYaw = g.yaw; g.fromPitch = g.pitch; g.toYaw = g.yaw + wrap180(yawTo - g.yaw); g.toPitch = elev;
  g.layStart = TNOW; g.layEnd = TNOW + clampN(turn / A.LAY_RATE, A.LAY_MIN, A.LAY_MAX); g.lay = "laying";
}
function sigmaOf(g, range) { const S = CONFIG.ARTY.SIGMA[g.team]; return S[0] + S[1] * range + g.extraSigma; }
// why the gun cannot fire now ("" = it can)
function fireBlock(g) {
  const A = CONFIG.ARTY;
  if (gunDisabled(g)) return "Gun disabled: hold E on it to repair";
  if (!g.loaded.length) return g.team === T ? "Rail empty: fetch a rocket" : "Breech empty: fetch a round";
  if (!g.target) return "No target: lock one on the board";
  if (g.lay !== "laid") return "Laying " + Math.max(0, g.layEnd - TNOW).toFixed(1) + " s";
  if (g.salvo > 0) return "Salvo away";
  if (TNOW < g.cooldown) return "Crew resetting " + Math.max(0, g.cooldown - TNOW).toFixed(1) + " s";
  if (g.loaded[g.loaded.length - 1] === "beehive" && g.target.range > A.BEEHIVE.RANGE) return "Beehive is direct fire: target within " + Math.round(A.BEEHIVE.RANGE * 0.0254) + " m only";
  return "";
}
function fireGun(g, firerSlot) {
  if (fireBlock(g)) return false;
  const A = CONFIG.ARTY;
  if (g.team === T) { g.salvo = g.loaded.length; g.salvoAt = TNOW; g.salvoBy = firerSlot; }
  else fireRound(g, g.loaded.pop(), firerSlot);
  g.cooldown = TNOW + A.COOLDOWN + (g.crew.length < 2 ? A.SOLO_RELOAD : 0) + (g.team === T ? g.salvo * A.SALVO_INTERVAL : 0);
  return true;
}
function fireRound(g, type, firerSlot) {
  const A = CONFIG.ARTY, tg = g.target;
  fire("mv_gun_snd_" + g.tag, "StartSound");
  fire("mv_gun_fx_" + g.tag, "Stop"); fire("mv_gun_fx_" + g.tag, "Start", undefined, 0.02);
  g.recoilAt = TNOW;
  const fp = players.get(firerSlot); if (fp) fp.fired++;
  stats.fired++;
  // the enemy board sees the flash a few seconds later
  const fl = flashes[otherTeam(g.team)];
  const old = fl.findIndex((f) => f.gun === g); if (old >= 0) fl.splice(old, 1);
  fl.push({ x: g.pos.x, y: g.pos.y, z: g.pos.z, from: TNOW + A.FLASH_DELAY, until: TNOW + A.FLASH_DELAY + A.FLASH_TIME, gun: g });
  if (fl.length > A.FLASH_MAX) fl.shift();
  const loader = g.loader;
  if (!g.loaded.length) g.loader = -1;
  if (type === "beehive") { fireBeehive(g, firerSlot); return; }
  const sig = sigmaOf(g, tg.range);
  const x = clampN(tg.x + gauss() * sig, -AIRX, AIRX), y = clampN(tg.y + gauss() * sig, -AIRY, AIRY);
  const t = TNOW + A.FLIGHT_BASE + tg.range * A.FLIGHT_PER_UNIT;
  const m = missionById(g.team, g.mission);
  if (m) { m.until = Math.max(m.until, t + A.MISSION.ASSIST_TIME); if (!m.shot) { m.shot = true; if (fp) fp.missions++; } toastSlot(m.owner, "SHOT - splash in " + (t - TNOW).toFixed(0) + " s", 3); }
  shells.push({ team: g.team, g, firer: firerSlot, loader, fo: m ? m.owner : -1, mission: m ? m.id : -1, x, y, t, type, whistled: false, ent: undefined, ei: 0, from: v3(g.pos.x, g.pos.y, g.pos.z + 60) });
  for (const s of g.crew) toastSlot(s, "Shot out! Splash in " + (t - TNOW).toFixed(1) + " s", 2.5);
}
function fireBeehive(g, firerSlot) {
  const B = CONFIG.ARTY.BEEHIVE, firer = creditOf(firerSlot, g.team);
  // direct fire AT the locked point (men coming up the slope are below the gun: a level cone went over their heads)
  const m0 = v3(g.pos.x, g.pos.y, g.pos.z + 50), tg = g.target;
  const dir = tg && Number.isFinite(tg.z) && dist2(tg, g.pos) > 60 ? vnorm(vsub(v3(tg.x, tg.y, tg.z + 40), m0)) : dirOf({ pitch: 0, yaw: g.yaw, roll: 0 });
  const muzzle = vadd(m0, dir, 70), cosC = Math.cos(B.CONE * 0.5 * D2R);
  stats.beehiveShots++;
  for (let k = 0; k < 5; k++) { const s = B.CONE * 0.5 * D2R * 0.6; tracer(muzzle, vnorm(v3(dir.x + gauss() * s, dir.y + gauss() * s, dir.z + gauss() * s * 0.3)), B.RANGE); }
  for (const r of roster) {
    if (!r.alive || r.team === g.team || r.seated || !r.p.deployed) continue;
    const chest = v3(r.pos.x, r.pos.y, r.pos.z + 40), v = vsub(chest, muzzle), d = vlen(v);
    if (d > B.RANGE || d < 1 || vdot(v, dir) / d < cosC) continue;
    let tr; try { tr = Instance.TraceLine({ start: muzzle, end: chest, ignoreEntity: hitIgnore, ignorePlayers: true }); } catch (e) {}
    if (tr && tr.didHit && tr.fraction < 0.98) continue;
    hurt(r.pawn, B.DAMAGE, firer, CSDamageTypes.BULLET, "arty");
    stats.beehive++;
  }
  for (const h of allHelis) {
    if (h.team === g.team || h.state === "dead") continue;
    const v = vsub(heliCentre(h), muzzle), d = vlen(v);
    if (d <= B.RANGE && d > 1 && vdot(v, dir) / d >= cosC) damageHeli(h, B.HELI, firerSlot, "arty");
  }
}
function tickGun(g, dt) {
  const A = CONFIG.ARTY;
  if (gunDisabled(g)) {
    if (TNOW >= g.puffAt) { g.puffAt = TNOW + A.DISABLE_PUFF; puff(v3(g.pos.x, g.pos.y, g.pos.z + 30)); }
  } else {
    if (g.disabledUntil) { g.disabledUntil = 0; g.graceUntil = TNOW + A.REPAIR_GRACE; for (const s of g.crew) toastSlot(s, "Gun " + (g.k + 1) + " is back in action", 3); }
    if (g.lay === "laying") {
      const f = clampN((TNOW - g.layStart) / Math.max(0.01, g.layEnd - g.layStart), 0, 1), e = f * f * (3 - 2 * f);
      g.yaw = g.fromYaw + (g.toYaw - g.fromYaw) * e; g.pitch = g.fromPitch + (g.toPitch - g.fromPitch) * e;
      if (f >= 1) { g.lay = "laid"; g.yaw = wrap180(g.yaw); for (const s of g.crew) toastSlot(s, "Gun " + (g.k + 1) + " laid", 1.5); }
    }
    if (g.salvo > 0 && TNOW >= g.salvoAt) {
      g.salvo--; g.salvoAt = TNOW + A.SALVO_INTERVAL;
      if (g.loaded.length && g.target) fireRound(g, g.loaded.pop(), g.salvoBy); else g.salvo = 0;
    }
  }
  const r = (TNOW - g.recoilAt) / A.RECOIL_TIME;
  const rec = r >= 1 || r < 0 ? 0 : A.RECOIL * (r < 0.12 ? r / 0.12 : 1 - (r - 0.12) / 0.88);
  placeGun(g, rec, false);
}
function disableGun(g, bySlot, src) {
  const A = CONFIG.ARTY;
  if (TNOW < g.graceUntil) return;                // just repaired: the crew gets a chance to shoot back
  if (gunDisabled(g)) return;                     // already out: more hits do not add time
  stats.gunsDisabled++; stats.gunsDisabledBy[src || "arty"] = (stats.gunsDisabledBy[src || "arty"] || 0) + 1;
  const q = players.get(bySlot);
  if (q && q.team !== g.team) { q.merit++; toast(q, "Enemy gun knocked out", 3); reqEarn(q, CONFIG.REQ.GUN, "gun"); }
  const what = g.team === T ? "rocket launcher " : "howitzer ";
  feed(g.team, "Our " + what + (g.k + 1) + " is knocked out", "bad", false);
  feed(otherTeam(g.team), "Enemy " + what + "knocked out", "good", false);
  g.disabledUntil = TNOW + A.DISABLE_TIME; g.puffAt = TNOW; g.salvo = 0;
  if (g.lay === "laying") { g.lay = "idle"; g.target = null; }
  if (g.aimer >= 0) { const q = players.get(g.aimer); if (q && q.board) leaveBoard(q, pawnOf(q.slot)); }
  for (const s of g.crew) toastSlot(s, "GUN " + (g.k + 1) + " KNOCKED OUT: hold E on it to repair", 4);
}

// ------------------------------------------------------------------ shells in flight, impacts, blast damage
function tickShells() {
  const A = CONFIG.ARTY;
  for (let i = shells.length - 1; i >= 0; i--) {
    const sh = shells[i], left = sh.t - TNOW;
    if (!sh.whistled && left <= A.WHISTLE) {
      sh.whistled = true;
      const w = (pool.boom % CONFIG.POOL.BOOM) + 1, e = need("mv_whistle_snd_" + w);
      if (e) { try { e.Teleport({ position: v3(sh.x, sh.y, approxGround(sh.x, sh.y) + 300) }); } catch (err) {} fire("mv_whistle_snd_" + w, "StartSound"); }
    }
    if (left <= A.FALL_TIME && left > 0) {      // the visible round coming down
      if (!sh.ent) { sh.ei = 7 + (pool.shell++ % Math.max(1, CONFIG.POOL.SHELL - 6)); sh.ent = need("mv_shell_" + sh.ei); sh.z = groundZ(sh.x, sh.y); sh.first = true; }
      if (sh.ent) {
        const f = left / A.FALL_TIME, pos = v3(sh.x + (sh.from.x - sh.x) * f * 0.08, sh.y + (sh.from.y - sh.y) * f * 0.08, sh.z + A.FALL_HEIGHT * f);
        try { if (sh.first) { sh.ent.Teleport({ position: pos, angles: { pitch: 75, yaw: Math.atan2(sh.y - sh.from.y, sh.x - sh.from.x) * R2D, roll: 0 } }); sh.first = false; } else sh.ent.Move({ position: pos }); } catch (err) {}
      }
    }
    if (left <= 0) { shells.splice(i, 1); if (sh.ent) parkEnt(sh.ent, 70 + sh.ei); impactShell(sh); }
  }
}
function impactShell(sh) {
  const A = CONFIG.ARTY;
  const z = sh.z !== undefined ? sh.z : groundZ(sh.x, sh.y), pos = v3(sh.x, sh.y, z + 8);
  stats.shells++;
  const g = sh.g;
  if (g) { g.impacts.unshift({ x: sh.x, y: sh.y }); if (g.impacts.length > A.IMPACTS_SHOWN) g.impacts.length = A.IMPACTS_SHOWN; }
  const m = missionById(sh.team, sh.mission);
  if (m) { m.splashAt = TNOW; toastSlot(m.owner, "SPLASH", 2.5); }
  if (sh.type === "smoke") {
    const i = (pool.smoke++ % CONFIG.POOL.SMOKE) + 1, e = need("mv_smoke_fx_" + i);
    for (let k = smokes.length - 1; k >= 0; k--) if (smokes[k].i === i) smokes.splice(k, 1);
    if (e) { try { e.Teleport({ position: pos }); } catch (err) {} fire("mv_smoke_fx_" + i, "Stop"); fire("mv_smoke_fx_" + i, "Start", undefined, 0.02); }
    smokes.push({ pos: v3(sh.x, sh.y, z + 70), until: TNOW + A.SMOKE_TIME, i });
    stats.smokes++;
    puff(pos);
    return;
  }
  const hits = blast({ pos, radius: A.HE_RADIUS, damage: A.HE_DAMAGE, team: sh.team, slot: sh.firer, loader: sh.loader, fo: sh.fo, cover: A.COVER,
                       heliRadius: A.HELI_RADIUS, heliDamage: A.HELI_DAMAGE, gunRadius: A.DISABLE_RADIUS, src: "arty" });
  stats.shellHits += hits;
  if (sh.mission >= 0) { stats.missionShells++; stats.missionHits += hits; }
  if (hits) { const fp = players.get(sh.firer); if (fp && fp.team === sh.team) fp.hits += hits; }
}
// the attacker entity for a scripted hit: the live pawn, else the controller (dead firers keep their kills). team = the side the
// shot was fired for: a slot that changed hands or sides since gets no credit (and deals no team kill): the hit is the world's.
function creditOf(slot, team) {
  if (slot === undefined || slot < 0) return undefined;
  if (team) { const q = players.get(slot); if (!q || q.team !== team) return undefined; }
  const c = Instance.GetPlayerController(slot); if (!c) return undefined;
  const pw = live(c.GetPlayerPawn());
  let alive = false; try { alive = !!pw && pw.IsAlive(); } catch (e) {}
  return alive ? pw : c;
}
// an explosion: effects, damage to the other team's infantry (helpers get a non-lethal share first = assists), helicopters, enemy guns
function blast(o) {
  const A = CONFIG.ARTY;
  if (!o.quiet) effects(o.pos, false);
  const firer = creditOf(o.slot, o.team), src = o.src || "arty";
  const helpers = [];
  if (o.loader >= 0 && o.loader !== o.slot) helpers.push(creditOf(o.loader, o.team));
  if (o.fo >= 0 && o.fo !== o.slot && o.fo !== o.loader) helpers.push(creditOf(o.fo, o.team));
  let hits = 0;
  for (const r of roster) {
    if (!r.alive || r.seated || !r.p.deployed) continue;
    if (r.team === o.team && !A.FRIENDLY_SPLASH) continue;
    const chest = v3(r.pos.x, r.pos.y, r.pos.z + 40), d = dist3(chest, o.pos);
    if (d > o.radius) continue;
    let k = Math.pow(1 - d / o.radius, 1.2);
    if (o.cover) {
      let tr; try { tr = Instance.TraceLine({ start: v3(o.pos.x, o.pos.y, o.pos.z + 16), end: chest, ignoreEntity: hitIgnore, ignorePlayers: true }); } catch (e) {}
      if (tr && tr.didHit && tr.fraction < 0.98) k *= o.cover;
    }
    let dmg = o.damage * k;
    if (dmg < 1) continue;
    hits++;
    for (const hp of helpers) {
      if (!hp) continue;
      let health = 100; try { health = r.pawn.GetHealth(); } catch (e) {}
      const share = Math.floor(Math.min(Math.max(A.SHARE_MIN, dmg * A.SHARE_FRAC), health - 1, dmg - 1));
      if (share >= 1) { hurt(r.pawn, share, hp, CSDamageTypes.BLAST, src); dmg -= share; }
    }
    let alive = false; try { alive = r.pawn.IsAlive(); } catch (e) {}
    if (alive) hurt(r.pawn, dmg, firer, CSDamageTypes.BLAST, src);
  }
  if (o.heliRadius > 0) for (const h of allHelis) {
    if (h.team === o.team || h.state === "dead" || h === o.skipHeli) continue;
    if (dist3(heliCentre(h), o.pos) < o.heliRadius) damageHeli(h, o.heliDamage, o.slot, src);
  }
  if (o.gunRadius > 0) for (const g of guns[otherTeam(o.team)] || []) {
    if (dist2(g.pos, o.pos) < o.gunRadius && Math.abs(g.pos.z - o.pos.z) < 300) disableGun(g, o.slot, src);
  }
  return hits;
}

// ------------------------------------------------------------------ fire missions (called from the field)
function missionById(team, id) { if (id < 0) return undefined; return (missions[team] || []).find((m) => m.id === id); }
function markerName(m) { return "mv_marker_" + ((m.team === T ? 0 : CONFIG.ARTY.MISSION.PER_TEAM) + m.idx + 1); }
function dropMission(team, i) {
  const m = missions[team][i];
  parkEnt(ent(markerName(m)), 80 + m.idx + (team === T ? 0 : 5));
  missions[team].splice(i, 1);
}
function callMission(p, pos) {
  const M = CONFIG.ARTY.MISSION, list = missions[p.team];
  const mine = list.findIndex((m) => m.owner === p.slot); if (mine >= 0) dropMission(p.team, mine);
  if (list.length >= M.PER_TEAM) { toast(p, "The fire net is full (" + M.PER_TEAM + " missions waiting)", 3); return false; }
  let idx = 0; while (list.some((m) => m.idx === idx)) idx++;
  const m = { id: ++missionSeq, team: p.team, owner: p.slot, x: pos.x, y: pos.y, z: pos.z, until: TNOW + M.TIME, splashAt: -99, idx, shot: false, at: TNOW };
  list.push(m);
  const e = need(markerName(m)); if (e) { try { e.Teleport({ position: v3(pos.x, pos.y, pos.z + 3), angles: { pitch: 0, yaw: 0, roll: 0 } }); } catch (err) {} }
  stats.missions++;
  toast(p, "Fire mission sent: grid " + gridRef(pos.x, pos.y), 4);
  for (const q of players.values()) if (q.team === p.team && q.role === "artillery" && q !== p) toast(q, "FIRE MISSION from " + nameOf(p.slot) + ": grid " + gridRef(pos.x, pos.y), 5);
  return true;
}
function tickMissions() {
  for (const team of TEAMS) {
    const list = missions[team];
    for (let i = list.length - 1; i >= 0; i--) if (TNOW >= list[i].until) dropMission(team, i);
    const fl = flashes[team];
    for (let i = fl.length - 1; i >= 0; i--) { if (TNOW >= fl[i].until) fl.splice(i, 1); else if (!fl[i].seen && TNOW >= fl[i].from) { fl[i].seen = true; stats.flashes++; } }
  }
}
// an enemy died near a mark that was just shelled: the observer gets the credit (merit raises the chance of an air slot)
function missionAssist(victimTeam, pos) {
  const M = CONFIG.ARTY.MISSION;
  for (const m of missions[otherTeam(victimTeam)] || []) {
    if (TNOW - m.splashAt > M.ASSIST_TIME || dist2(m, pos) > M.ASSIST_RADIUS) continue;
    const q = players.get(m.owner); if (q && q.team === m.team) { q.merit++; stats.foAssists++; toast(q, "Fire mission assist +1 merit", 3); reqEarn(q, CONFIG.REQ.FO_ASSIST, "fo"); }
  }
}
// hold USE on open ground: returns the prompt while holding
function tickObserver(p, pawn, dt, held) {
  const M = CONFIG.ARTY.MISSION;
  if (!(held & CSInputs.USE)) { if (p.holdKind === "mission" || p.holdKind === "done") { p.holdKind = ""; p.holdT = 0; } return ""; }
  if (p.holdKind === "done" || (p.holdKind && p.holdKind !== "mission")) return "";
  p.holdKind = "mission"; p.holdT += dt;
  if (p.holdT < M.HOLD) return p.holdT > 0.3 ? "CALLING FIRE MISSION" : "";
  p.holdKind = "done"; p.holdT = 0;
  const eye = eyeOf(pawn), dir = dirOf(eye);
  let from; try { from = pawn.GetEyePosition(); } catch (e) {}
  if (!finiteV(from)) { const o = pawn.GetAbsOrigin(); from = v3(o.x, o.y, o.z + 60); }
  let tr; try { tr = Instance.TraceLine({ start: from, end: vadd(from, dir, M.MAX_DIST), ignoreEntity: hitIgnore, ignorePlayers: true }); } catch (e) {}
  if (!tr || !tr.didHit) { toast(p, "Fire mission: aim at the ground", 2); return ""; }
  const d = tr.fraction * M.MAX_DIST;
  if (d < M.MIN_DIST) { toast(p, "Fire mission: too close, mark ground beyond " + Math.round(M.MIN_DIST * 0.0254) + " m", 2.5); return ""; }
  if (tr.normal && tr.normal.z < 0.5) { toast(p, "Fire mission: mark open ground, not a wall", 2); return ""; }
  if (!inBand(tr.end, 0)) { toast(p, "Fire mission: that is outside the valley", 2); return ""; }
  if (smokeBlocks(from, tr.end)) { stats.smokeBlocked++; toast(p, "Fire mission: you can't see through the smoke", 2.5); return ""; }
  callMission(p, tr.end);
  return "";
}

// ------------------------------------------------------------------ the plotting board (reticle on a map, as mg_trenchwarfare's sight)
function boardToWorld(u, v) { return { x: u * 2 * BOARD_EXT - BOARD_EXT, y: BOARD_EXT - v * 2 * BOARD_EXT }; }
function worldToBoard(x, y) { return { u: clampN((x + BOARD_EXT) / (2 * BOARD_EXT), 0, 0.9999), v: clampN((BOARD_EXT - y) / (2 * BOARD_EXT), 0, 0.9999) }; }
function boardMarks(team) {            // what RELOAD cycles through: missions, then visible flashes
  const out = [];
  for (const m of missions[team]) out.push({ kind: "msn", x: m.x, y: m.y, z: m.z, id: m.id, m });
  for (const f of flashes[team]) if (TNOW >= f.from) out.push({ kind: "flash", x: f.x, y: f.y, z: f.z, id: -1, m: null });
  return out;
}
function enterBoard(p, pawn) {
  const g = guns[p.team][p.crew]; if (!g) return;
  if (g.aimer >= 0 && g.aimer !== p.slot && players.get(g.aimer) && players.get(g.aimer).board) { toast(p, "Your crewmate has the board", 2); return; }
  dropCarryCheck(p);
  g.aimer = p.slot; p.board = true; p.msnSel = -1;
  stow(pawn);
  freeze(p, pawn, true);
  try { pawn.Teleport({ velocity: v3(0, 0, 0) }); } catch (e) {}
  const s = g.target ? worldToBoard(g.target.x, g.target.y) : worldToBoard(g.pos.x * 0.3, g.pos.y * 0.3);
  p.u = s.u; p.v = s.v;
}
function leaveBoard(p, pawn) {
  p.board = false;
  const g = guns[p.team] && guns[p.team][p.crew];
  if (g && g.aimer === p.slot) g.aimer = -1;
  let alive = false; try { alive = !!pawn && pawn.IsAlive(); } catch (e) {}
  if (alive) { freeze(p, pawn, false); equip(p, pawn, false); }
  hClass(p, "mv_board", "show", false);
}
function tickBoard(p, pawn, dt, pressed, held) {
  const g = guns[p.team][p.crew], C = CONFIG.BOARD;
  if (!g || gunDisabled(g)) { leaveBoard(p, pawn); return; }
  const st = ((held & CSInputs.WALK) ? C.FINE : C.SPEED) * dt / BOARD_STEPS;
  if (held & CSInputs.FORWARD) p.v -= st;
  if (held & CSInputs.BACK) p.v += st;
  if (held & CSInputs.LEFT) p.u -= st;
  if (held & CSInputs.RIGHT) p.u += st;
  p.u = clampN(p.u, 0, 0.9999); p.v = clampN(p.v, 0, 0.9999);
  const w = boardToWorld(p.u, p.v);
  if (pressed & CSInputs.RELOAD) {
    const marks = boardMarks(p.team);
    if (!marks.length) toast(p, "No fire missions waiting", 2);
    else { p.msnSel = (p.msnSel + 1) % marks.length; const m = marks[p.msnSel], s = worldToBoard(m.x, m.y); p.u = s.u; p.v = s.v; }
  }
  const onTarget = g.target && dist2(g.target, w) < 2 * BOARD_EXT / BOARD_STEPS * 1.5;
  if ((pressed & CSInputs.JUMP) || ((pressed & CSInputs.ATTACK) && onTarget && g.lay === "laid")) {
    const why = fireBlock(g);
    if (why) toast(p, why, 2); else fireGun(g, p.slot);
  } else if ((pressed & CSInputs.ATTACK) && g.salvo > 0) toast(p, "Salvo away: lock again when it is out", 2);
  else if (pressed & CSInputs.ATTACK) {
    let near = null, nd = CONFIG.ARTY.MISSION.LOCK_RADIUS;
    for (const m of missions[p.team]) { const d = dist2(m, w); if (d < nd) { nd = d; near = m; } }
    const tp = near ? { x: near.x, y: near.y, z: near.z } : { x: w.x, y: w.y, z: groundZ(w.x, w.y) };
    setTarget(g, tp, near ? near.id : -1);
    for (const s of g.crew) toastSlot(s, "Target locked: " + gridRef(tp.x, tp.y) + (near ? " (fire mission)" : ""), 2);
  }
  if (pressed & (CSInputs.USE | CSInputs.ATTACK2)) { leaveBoard(p, pawn); return; }
  drawBoard(p, g);
}

// ------------------------------------------------------------------ crew stations: board seat, ammo rack, breech / rail; repair for everyone
function dropCarry(p) {
  if (p.carryEnt > 0) parkEnt(ent("mv_shell_" + p.carryEnt), 90 + p.carryEnt);
  p.carrying = ""; p.carryEnt = -1;
}
function dropCarryCheck(p) { if (p.carrying) { dropCarry(p); toast(p, "Round put down", 1.5); } }
function takeRound(p, type) {
  p.carrying = type; p.carryEnt = -1;
  for (let i = 1; i <= Math.min(6, CONFIG.POOL.SHELL); i++) {
    let used = false; for (const q of players.values()) if (q.carryEnt === i) { used = true; break; }
    if (!used) { p.carryEnt = i; break; }
  }
}
function tickCarry(p, pawn, pos) {
  const A = CONFIG.ARTY;
  if (p.carryEnt > 0) {
    const e = ent("mv_shell_" + p.carryEnt), eye = eyeOf(pawn), d = dirOf({ pitch: 0, yaw: eye.yaw, roll: 0 });
    if (e) { try { e.Move({ position: v3(pos.x + d.x * 22, pos.y + d.y * 22, pos.z + 38), angles: { pitch: 0, yaw: eye.yaw + 90, roll: 0 } }); } catch (err) {} }
  }
  try {       // the loader walks slower
    const v = pawn.GetAbsVelocity(), sp = Math.hypot(v.x, v.y), cap = A.RUN_SPEED * A.CARRY_SPEED;
    if (sp > cap + 5 && pawn.GetGroundEntity()) pawn.Teleport({ velocity: v3(v.x * cap / sp, v.y * cap / sp, v.z) });
  } catch (e) {}
}
// a deployed, walking player near battery things. Returns the prompt ("" = nothing here).
function tickBattery(p, pawn, pos, dt, pressed, held) {
  const A = CONFIG.ARTY, team = p.team;
  // anyone can repair a disabled friendly gun
  for (const g of guns[team]) {
    if (!gunDisabled(g) || dist2(pos, g.pos) > A.BREECH_RADIUS || Math.abs(pos.z - g.pos.z) > 120) continue;
    if (held & CSInputs.USE) {
      if (p.holdKind !== "repair") { p.holdKind = "repair"; p.holdT = 0; }
      p.holdT += dt;
      if (p.holdT >= A.REPAIR_HOLD) { g.disabledUntil = TNOW; p.holdKind = "done"; p.holdT = 0; p.merit++; stats.repairs++; toast(p, "Gun repaired", 2.5); reqEarn(p, CONFIG.REQ.REPAIR, "repair"); }
      return "REPAIRING GUN " + (g.k + 1);
    }
    if (p.holdKind === "repair") { p.holdKind = ""; p.holdT = 0; }
    return "[hold E] Repair gun " + (g.k + 1) + "  (back by itself in " + Math.ceil(g.disabledUntil - TNOW) + " s)";
  }
  if (p.holdKind === "repair") { p.holdKind = ""; p.holdT = 0; }
  if (p.role !== "artillery" || p.crew < 0) return "";
  const g = guns[team][p.crew]; if (!g) return "";
  if (p.carrying) tickCarry(p, pawn, pos);
  const types = A.SHELLS[team], maxLoad = A.MAX_LOAD[team], use = (pressed & CSInputs.USE) !== 0;
  const dSeat = g.seat ? dist2(pos, g.seat.pos) : 1e9, dBoard = boardPos[team] ? dist2(pos, boardPos[team]) : 1e9;
  const dRack = g.rack ? dist2(pos, g.rack) : 1e9, dGun = dist2(pos, g.pos);
  if (dRack < CONFIG.STATION_RADIUS && dRack <= dGun) {
    if (types.length > 1 && (pressed & CSInputs.ATTACK2)) { p.shellSel = (p.shellSel + 1) % types.length; if (p.carrying) takeRound(p, types[p.shellSel]); }
    const type = types[p.shellSel % types.length];
    if (p.carrying) return "Carrying " + A.SHELL_NAME[p.carrying] + ": load it at the gun" + (types.length > 1 ? "   [MOUSE2] swap type" : "");
    if (g.loaded.length >= maxLoad) return team === T ? "The rail rack is full (" + maxLoad + ")" : "The gun is already loaded";
    if (use) { takeRound(p, type); toast(p, A.SHELL_NAME[type] + " in hand", 1.5); return ""; }
    return "[E] Take " + A.SHELL_NAME[type] + (types.length > 1 ? "   [MOUSE2] next type" : "");
  }
  if (dGun < A.BREECH_RADIUS) {
    if (p.carrying && g.loaded.length < maxLoad) {
      if (use) {
        g.loaded.push(p.carrying); g.loader = p.slot; dropCarry(p);
        if (g.target && g.lay !== "laying") setTarget(g, g.target, g.mission);        // beehive lays flat, the others elevate
        for (const s of g.crew) toastSlot(s, "Gun " + (g.k + 1) + " loaded" + (team === T ? " (" + g.loaded.length + "/" + maxLoad + ")" : ": " + A.SHELL_NAME[g.loaded[g.loaded.length - 1]]), 2);
        return "";
      }
      return "[E] Load " + A.SHELL_NAME[p.carrying];
    }
    const why = fireBlock(g);
    if (!why) { if (use || (pressed & CSInputs.JUMP)) { fireGun(g, p.slot); return ""; } return "[E] or [SPACE] FIRE"; }
    return why;
  }
  if (Math.min(dSeat, dBoard) < CONFIG.STATION_RADIUS + 20) {
    if (use) { enterBoard(p, pawn); return ""; }
    return "[E] Plotting board";
  }
  return p.carrying ? "Carrying " + A.SHELL_NAME[p.carrying] : "";
}
