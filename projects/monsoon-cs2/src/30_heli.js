// ------------------------------------------------------------------ 30_heli: helicopters (script-moved prop_dynamic), seats, guns, rockets
// A helicopter's pose is (pos = point on the ground under the mast, yaw = nose heading, pitch, roll) in the NOSE frame; the model's own
// nose direction (NOSE_YAW) is applied when the entity angles are written, so every offset below is x forward, y left, z up.
const helis = { 2: [], 3: [] };
let allHelis = [];
const heliByName = new Map();
const isV3 = (q) => Array.isArray(q) && q.length === 3 && q.every(Number.isFinite);
// model numbers: CONFIG.HELI_MODELS holds the defaults; LAYOUT.models[kind] (written by tools/mv_models.py from the models the map was
// built with) overwrites nose yaw, rotor, hubs, seats, exits, pods and the gun's muzzle / camera. Older data (LAYOUT.apache /
// HUDDATA.apache = out/apache.json) is still read for the Apache when the models block is missing.
function heliModel(kind) {
  const M = CONFIG.HELI_MODELS[kind];
  if (!M || M._merged) return M;
  M._merged = true;
  const D = LAYOUT.models && LAYOUT.models[kind];
  try {
    if (D) {
      if (Number.isFinite(D.nose_yaw)) M.NOSE_YAW = D.nose_yaw;
      if (Number.isFinite(D.rotor_r)) M.ROTOR_R = D.rotor_r;
      if (isV3(D.hub)) { M.ROTOR_Z = D.hub[2]; if (!M.ANIMATED) M.HUB = D.hub; }
      if (isV3(D.tail_hub) && !M.ANIMATED) M.TAIL = D.tail_hub;
      if (Array.isArray(D.seats) && D.seats.length && D.seats.every((q) => q && typeof q.kind === "string" && isV3(q.off)) && D.seats[0].kind === "pilot")
        M.SEATS = D.seats.map((q) => ({ kind: q.kind, off: q.off }));
      if (Array.isArray(D.exits) && D.exits.length && D.exits.every(isV3)) M.EXIT = D.exits;
      if (Array.isArray(D.pods) && D.pods.every(isV3) && (D.pods.length >= 2 || !M.ROCKETS)) M.PODS = D.pods;
      if (D.gun) {
        if (isV3(D.gun.muzzle)) M.GUN.muzzle = D.gun.muzzle;
        if (isV3(D.gun.cam)) M.GUN.cam = D.gun.cam;
        for (const k of ["yaw", "cone", "up", "down"]) if (Number.isFinite(D.gun[k])) M.GUN[k] = D.gun[k];
      }
      return M;
    }
    if (kind !== "apache") return M;
    const A = LAYOUT.apache || HUDDATA.apache;
    if (!A) return M;
    if (Number.isFinite(A.nose_yaw)) M.NOSE_YAW = A.nose_yaw;
    if (Number.isFinite(A.rotor_radius)) M.ROTOR_R = A.rotor_radius;
    if (A.rotor_hub && Number.isFinite(A.rotor_hub[2])) M.ROTOR_Z = A.rotor_hub[2];
    const S = A.seats || {}, names = ["pilot_fwd", "gunner_fwd", "wing_left_fwd", "wing_right_fwd"];
    names.forEach((n, i) => { if (isV3(S[n])) M.SEATS[i].off = S[n]; });
    if (A.gun && isV3(A.gun.muzzle_fwd)) M.GUN.muzzle = A.gun.muzzle_fwd;
    if (Array.isArray(A.rocket_pods)) { const pods = A.rocket_pods.map((q) => q.muzzle_fwd).filter(isV3); if (pods.length >= 2) M.PODS = pods; }
  } catch (e) { log("model data ignored for " + kind + ": " + e); }
  return M;
}
// which model sits on which pad: LAYOUT.models.pads ({t: [...], ct: [...]}) when every name is a known model, else CONFIG.HELI_KINDS
function heliKind(team, n) {
  const P = LAYOUT.models && LAYOUT.models.pads && LAYOUT.models.pads[tagOf(team)];
  const k = Array.isArray(P) ? P[n - 1] : undefined;
  return k && CONFIG.HELI_MODELS[k] ? k : CONFIG.HELI_KINDS[team][n - 1];
}
function wreckYaw() { const w = LAYOUT.models && LAYOUT.models.wreck; return w && Number.isFinite(w.yaw) ? w.yaw : CONFIG.WRECK_YAW; }
function loadHelis() {
  const H = CONFIG.HELI;
  helis[T] = []; helis[CT] = []; allHelis = []; heliByName.clear();
  const ign = [];
  for (const team of TEAMS) {
    for (let n = 1; n <= H.COUNT; n++) {
      const tag = tagOf(team) + "_" + n, name = "mv_heli_" + tag;
      const e = need(name), padE = need("mv_pad_" + tag);
      const kind = heliKind(team, n), M = heliModel(kind);
      const lay = LAYOUT[tagOf(team)];
      const padPos = padE ? padE.GetAbsOrigin() : (e ? e.GetAbsOrigin() : v3(lay.pads[n - 1][0], lay.pads[n - 1][1], lay.z));
      const yaw = Number.isFinite(lay.pad_yaw) ? lay.pad_yaw : 0;
      const h = { team, n, tag, name, ent: e, kind, M, pad: { pos: padPos, yaw }, groundOff: 0,
                  rotor: M.ANIMATED ? undefined : need("mv_rotor_" + tag), tail: M.ANIMATED ? undefined : need("mv_tail_" + tag), hubOff: M.HUB, tailOff: M.TAIL,
                  wreck: need("mv_wreck_" + tag), owner: -1, yieldTo: -1,
                  state: "parked", landed: true, pos: v3(padPos.x, padPos.y, padPos.z), vel: v3(0, 0, 0), yaw, pitch: 0, roll: 0,
                  hp: M.HEALTH || H.HEALTH, maxHp: M.HEALTH || H.HEALTH, rockets: M.ROCKETS, rearmAcc: 0, rocketAt: 0, podI: 0,
                  seats: M.SEATS.map((s) => ({ kind: s.kind, off: s.off, slot: -1 })),
                  gun: gunFresh(),
                  rotorSpeed: 0, spin: 0, anim: "", engine: false, engineSet: false, smoking: false, dust: false,
                  angSent: undefined, rotSent: undefined, tailSent: undefined, B: angleBasis({ pitch: 0, yaw, roll: 0 }),
                  lastHitBy: -1, lastHitAt: -99, lastSrc: "", rotorHitAt: 0, padT: 0, crashT: 0, respawnAt: 0, wreckUntil: 0, wreckOut: false,
                  guardUntil: 0, idleT: 0, firstFlightAt: 0, overWater: false, soft: false,
                  tick: n * 3 + team, gz: padPos.z, alt: 0, speed: 0, inp: null, ai: null, warn: "", flights: 0 };
      if (e) {
        // how high the model's origin sits over the pad as placed, and where the Hip's rotor props are on it
        const eo = e.GetAbsOrigin();
        h.groundOff = clampN(eo.z - padPos.z, 0, 120);
        const org = v3(padPos.x, padPos.y, padPos.z + h.groundOff);
        if (h.rotor) { const o = toLocal(org, h.B, h.rotor.GetAbsOrigin()); if (Math.hypot(o[0], o[1], o[2]) < 900 && o[2] > 20) h.hubOff = o; }
        if (h.tail) { const o = toLocal(org, h.B, h.tail.GetAbsOrigin()); if (Math.hypot(o[0], o[1], o[2]) < 900 && o[2] > 20) h.tailOff = o; }
        heliByName.set(name, h);
        ign.push(e); if (h.rotor) ign.push(h.rotor); if (h.tail) ign.push(h.tail); if (h.wreck) ign.push(h.wreck);
        placeHeli(h, true);
        setAnim(h, true);
      }
      helis[team].push(h); allHelis.push(h);
    }
  }
  hitIgnore = ign;
}
function heliCentre(h) { return v3(h.pos.x, h.pos.y, h.pos.z + CONFIG.HELI.HIT_UP); }
function heliOfEntity(e) {
  if (!e) return undefined;
  let nm = ""; try { nm = e.GetEntityName(); } catch (err) { return undefined; }
  return nm ? heliByName.get(nm) : undefined;
}
function heliOrigin(h) { return v3(h.pos.x, h.pos.y, h.pos.z + h.groundOff); }
function seatPos(h, i) { return local(heliOrigin(h), h.B, h.seats[i].off); }

// ------------------------------------------------------------------ pose -> entities
function placeHeli(h, snap) {
  if (!h.ent) return;
  const H = CONFIG.HELI;
  const B = angleBasis({ pitch: h.pitch * H.PITCH_SIGN, yaw: h.yaw, roll: h.roll * H.ROLL_SIGN });
  h.B = B;
  const E = h.M.NOSE_YAW ? yawBasis(B, h.M.NOSE_YAW) : B;
  const ang = anglesNear(anglesFromBasis(E.f, E.l, E.u), snap ? undefined : h.angSent);
  h.angSent = ang;
  const org = heliOrigin(h);
  try { if (snap) h.ent.Teleport({ position: org, angles: ang, velocity: v3(0, 0, 0) }); else h.ent.Move({ position: org, angles: ang, velocity: h.vel }); } catch (e) {}
  if (h.rotor && h.hubOff) {
    const R = yawBasis(B, h.spin), ra = anglesNear(anglesFromBasis(R.f, R.l, R.u), snap ? undefined : h.rotSent);
    h.rotSent = ra;
    try { if (snap) h.rotor.Teleport({ position: local(org, B, h.hubOff), angles: ra }); else h.rotor.Move({ position: local(org, B, h.hubOff), angles: ra }); } catch (e) {}
  }
  if (h.tail && h.tailOff) {
    const R = pitchBasis(B, h.spin * 3), ra = anglesNear(anglesFromBasis(R.f, R.l, R.u), snap ? undefined : h.tailSent);
    h.tailSent = ra;
    try { if (snap) h.tail.Teleport({ position: local(org, B, h.tailOff), angles: ra }); else h.tail.Move({ position: local(org, B, h.tailOff), angles: ra }); } catch (e) {}
  }
}
function placeRiders(h, snap) {
  for (let i = 0; i < h.seats.length; i++) {
    const s = h.seats[i]; if (s.slot < 0) continue;
    const pawn = pawnOf(s.slot); if (!pawn) continue;
    const sp = seatPos(h, i);
    try { if (snap) pawn.Teleport({ position: sp, velocity: v3(0, 0, 0) }); else pawn.Move({ position: sp, velocity: h.vel }); } catch (e) {}
    const p = players.get(s.slot);
    if (p && p.camKind === "gun" && p.cam) { try { p.cam.Move({ position: local(heliOrigin(h), h.B, h.M.GUN.cam) }); } catch (e) {} }
  }
}
function setAnim(h, force) {
  if (!h.M.ANIMATED || !h.ent) return;
  const A = h.M.ANIMS, want = h.rotorSpeed <= 0.03 ? A.off : h.rotorSpeed < 0.75 ? A.slow : A.full;
  if (want === h.anim && !force) return;
  h.anim = want;
  fireEnt(h.ent, h.M.ANIM_INPUT, want);
}
function setEngine(h, on) {
  if (h.engine === on) return;
  h.engine = on;
  const snd = "mv_heli_eng_" + h.tag;
  if (on) {
    if (!h.engineSet) { h.engineSet = true; for (const k of ["eng", "gun", "gun2", "rkt"]) fire("mv_heli_" + k + "_" + h.tag, "SetSourceEntity", h.name); }
    fire(snd, "StartSound", undefined, 0.05);
  } else fire(snd, "StopSound");
}
function setSmoke(h, on) {
  if (h.smoking === on) return;
  h.smoking = on;
  fire("mv_heli_smoke_" + h.tag, on ? "Start" : "Stop");
}
function setDust(h, on) {
  if (h.dust === on) return;
  h.dust = on;
  fire("mv_heli_dust_" + h.tag, on ? "Start" : "Stop");
}

// ------------------------------------------------------------------ seats
function freeSeat(h, pilot, human) {
  const open = (s) => s.slot < 0 || (human && (() => { const q = players.get(s.slot); return !!(q && q.bot); })());
  if (pilot && open(h.seats[0])) return 0;
  for (const kind of ["gunner", "rider"]) for (let i = 1; i < h.seats.length; i++) if (h.seats[i].kind === kind && open(h.seats[i])) return i;
  return -1;
}
function crewCount(h) { let n = 0; for (const s of h.seats) if (s.slot >= 0) n++; return n; }
function setSeatCamera(p, pawn, h) {
  const C = CONFIG.HELI.CAM;
  let cam; try { cam = typeof pawn.GetCustomCamera === "function" ? pawn.GetCustomCamera() : undefined; } catch (e) {}
  if (!cam) return;
  p.cam = cam;
  try {
    if (h.seats[p.seat].kind === "gunner") {
      if (p.camParent === undefined) { try { p.camParent = cam.GetParent() || null; cam.SetParent(undefined); } catch (e) { p.camParent = null; } }
      cam.Teleport({ position: local(heliOrigin(h), h.B, h.M.GUN.cam) });
      cam.SetMode(CustomCameraMode.CONTROLLED_POSITION);
      p.camKind = "gun";
    } else {
      p.camBack = C.BACK; p.camSentBack = C.BACK; p.camSentAt = TNOW;
      cam.SetFollowConfig({ followEntity: h.ent, followOffset: v3(0, 0, C.UP), cameraOffset: v3(-C.BACK, 0, 0), clipCameraOffset: true, cameraOffsetReturnStrength: C.RETURN });
      cam.SetMode(CustomCameraMode.FOLLOW_POSITION);
      p.camKind = "chase";
    }
  } catch (e) {}
}
function restoreCamera(p) {
  const cam = p.cam;
  if (cam && live(cam)) {
    try { cam.SetMode(CustomCameraMode.DISABLED); if (p.camParent) cam.SetParent(p.camParent); } catch (e) {}
  }
  p.cam = null; p.camKind = ""; p.camParent = undefined;
}
// the pilot's chase camera eases back with speed: sent only when it moved MIN_STEP, at most every EVERY
function easeCamera(p, h, dt) {
  const C = CONFIG.HELI.CAM;
  if (p.camKind !== "chase" || !p.cam) return;
  const want = C.BACK + (C.BACK_FAST - C.BACK) * clampN(h.speed / CONFIG.HELI.V_FWD, 0, 1);
  p.camBack += (want - p.camBack) * (1 - Math.exp(-Math.max(0, dt) / C.TAU));
  if (Math.abs(p.camBack - p.camSentBack) < C.MIN_STEP || TNOW - p.camSentAt < C.EVERY) return;
  try {
    p.cam.SetFollowConfig({ followEntity: h.ent, followOffset: v3(0, 0, C.UP), cameraOffset: v3(-p.camBack, 0, 0), clipCameraOffset: true, cameraOffsetReturnStrength: C.RETURN });
    p.camSentBack = p.camBack; p.camSentAt = TNOW;
  } catch (e) {}
}
function enterHeli(p, pawn, h, idx) {
  if (!h || !h.ent || idx < 0 || idx >= h.seats.length || h.state === "dead" || h.state === "crashing") return false;
  const s = h.seats[idx];
  if (s.slot >= 0 && s.slot !== p.slot) {
    const q = players.get(s.slot);
    if (q && q.bot && !p.bot) aiRelease(q, true); else return false;      // a bot gives its seat to a human
    if (s.slot >= 0) return false;
  }
  unseat(p, pawn, "seat");
  s.slot = p.slot; p.heli = h; p.seat = idx; h.idleT = 0;
  stow(pawn);
  freeze(p, pawn, true); hidePawn(p, pawn, true);
  try { pawn.Teleport({ position: seatPos(h, idx), velocity: v3(0, 0, 0) }); } catch (e) {}
  try { pawn.SetEyeAngles({ pitch: s.kind === "gunner" ? 10 : 0, yaw: h.yaw + (s.kind === "gunner" ? h.M.GUN.yaw : 0), roll: 0 }); } catch (e) {}
  setSeatCamera(p, pawn, h);
  if (!p.bot) toast(p, s.kind === "pilot" ? h.M.label + ": you have the controls" : s.kind === "gunner" ? h.M.GUN.name + ": MOUSE1 fires, R reloads, E gets out" : "Aboard. E gets out (rope below " + Math.round(CONFIG.HELI.ROPE_ALT * 0.0254) + " m)", 4);
  return true;
}
function leaveHeli(p, pawn, why) {
  const h = p.heli, idx = p.seat, H = CONFIG.HELI;
  if (!h) return;
  const sp = seatPos(h, idx);
  if (h.seats[idx] && h.seats[idx].slot === p.slot) h.seats[idx].slot = -1;
  p.heli = null; p.seat = -1;
  restoreCamera(p);
  hClass(p, "mv_fly", "show", false); hClass(p, "mv_gun", "show", false);
  if (!pawn || !live(pawn)) { p.hidden = false; return; }
  hidePawn(p, pawn, false);
  let alive = false; try { alive = pawn.IsAlive(); } catch (e) {}
  if (!alive) return;                             // moveNone stays set: OnPlayerReset gives the new life its legs back
  if (why === "crash") return;                    // about to be killed where it sits
  freeze(p, pawn, false);
  if (why === "deploy") return;                   // deploy() places the pawn itself
  const ex = h.M.EXIT[idx] || [0, 160, 0];
  try {
    if (h.landed || h.alt < H.BOARD_ALT) {
      const out = local(h.pos, h.B, ex);
      pawn.Teleport({ position: v3(out.x, out.y, groundZ(out.x, out.y, h.pos.z + 120) + 6), velocity: v3(0, 0, 0) });
    } else if (h.alt < H.ROPE_ALT && h.speed < H.ROPE_SPEED && h.state !== "crashing") {      // no rope from a helicopter that is spinning in
      p.ropeUntil = TNOW + H.ROPE_SAFE; p.noFallUntil = TNOW + H.ROPE_SAFE + 1;
      pawn.Teleport({ position: v3(sp.x, sp.y, sp.z - H.ROPE_DROP), velocity: v3(0, 0, -H.ROPE_FALL) });
      stats.ropes++;
      if (!p.bot) toast(p, "Fast-roping", 2);
    } else {
      pawn.Teleport({ position: v3(sp.x, sp.y, sp.z - H.ROPE_DROP), velocity: v3(h.vel.x, h.vel.y, h.vel.z) });
      stats.jumps++;
      if (!p.bot) toast(p, "Too high or too fast for the rope: you jumped", 3);
    }
  } catch (e) {}
  if (why !== "role") equip(p, pawn, false);
}
// a fast-roping player: fall speed capped until the ground or the timer
function tickRope(p, pawn) {
  if (TNOW >= p.ropeUntil) { p.ropeUntil = 0; return; }
  try {
    if (pawn.GetGroundEntity()) { p.ropeUntil = 0; return; }
    const v = pawn.GetAbsVelocity(), cap = -CONFIG.HELI.ROPE_FALL;
    if (v && v.z < cap - 5) pawn.Teleport({ velocity: v3(v.x * 0.9, v.y * 0.9, cap) });
  } catch (e) {}
}
// the nearest friendly helicopter a walking player can board, with the seat they would get
function boardable(p, pos) {
  const H = CONFIG.HELI;
  let best = null, bd = H.BOARD_RADIUS;
  for (const h of helis[p.team] || []) {
    if (!h.ent || (h.state !== "parked" && h.state !== "flying") || (!h.landed && h.alt > H.BOARD_ALT)) continue;
    const d = dist2(pos, h.pos);
    if (d >= bd || Math.abs(pos.z - h.pos.z) > 220) continue;
    const idx = freeSeat(h, h.owner === p.slot, !p.bot);
    if (idx < 0) continue;
    bd = d; best = { h, idx };
  }
  return best;
}

// ------------------------------------------------------------------ guns shared by door guns, the chin gun and emplaced guns
// st = { heat, locked, next, shots, ammo, reloadAt }. Heat locks the gun at 1 until it cools to 0.25; a belt (G.belt rounds) runs
// out and is changed in G.reload seconds (by itself when empty, or early with RELOAD: gunReload).
function gunTick(st, G, firing, dt) {
  if (st.locked && st.heat <= 0.25) st.locked = false;
  if (G.belt) {
    if (st.ammo === undefined) st.ammo = G.belt;
    if (st.reloadAt) { if (TNOW >= st.reloadAt) { st.reloadAt = 0; st.ammo = G.belt; } else firing = false; }
  }
  const can = firing && !st.locked;
  if (can) { st.heat = Math.min(1, st.heat + dt / G.overheat); if (st.heat >= 1) st.locked = true; }
  else st.heat = Math.max(0, st.heat - dt / G.cool);
  if (can && TNOW >= st.next) {
    st.next = TNOW + G.interval; st.shots++;
    if (G.belt && --st.ammo <= 0) { st.ammo = 0; st.reloadAt = TNOW + G.reload; stats.beltReloads++; }
    return true;
  }
  return false;
}
function gunReload(st, G) { if (G.belt && !st.reloadAt && st.ammo !== undefined && st.ammo < G.belt) { st.reloadAt = TNOW + G.reload; stats.beltReloads++; } }
function gunFresh() { return { heat: 0, locked: false, next: 0, shots: 0, ammo: undefined, reloadAt: 0 }; }
function gunRound(st, G, muzzle, dir, pawn, team, snd, range, spread, src) {
  const s = spread === undefined ? G.spread : spread;
  const d = vnorm(v3(dir.x + gauss() * s, dir.y + gauss() * s, dir.z + gauss() * s));
  const dist = hitscan(muzzle, d, range, pawn, team, G.damage, G.heli, hitIgnore, src);
  if (st.shots % CONFIG.HELI.TRACER_EVERY === 0) tracer(muzzle, d, Math.max(60, dist));
  if (st.shots % CONFIG.HELI.SOUND_EVERY === 0) fire(snd, "StartSound");
  stats.gunShots++;
}
// the helicopter's gunner seat: aim = eye clamped to the gun's cone (relative to the airframe heading, level)
function tickHeliGun(h, pawn, team, eye, firing, dt, spread) {
  const G = h.M.GUN;
  const aim = clampAim(eye, h.yaw + G.yaw, G.cone, G.up, G.down);
  if (gunTick(h.gun, G, firing && h.state !== "crashing", dt)) {
    gunRound(h.gun, G, local(heliOrigin(h), h.B, G.muzzle), dirOf(aim), pawn, team, "mv_heli_" + (h.gun.shots % 4 < 2 ? "gun_" : "gun2_") + h.tag, G.range, spread, "heligun");
  }
}

// ------------------------------------------------------------------ rockets (helicopter pods, the AT kit, battery rockets in their last seconds are shells)
const rockets = [];
function launchRocket(o) {
  const i = (pool.rocket++ % CONFIG.POOL.ROCKET) + 1;
  const e = need("mv_rocket_" + i);
  for (let k = rockets.length - 1; k >= 0; k--) if (rockets[k].ent && rockets[k].ent === e) rockets[k].ent = undefined;
  rockets.push({ pos: o.pos, vel: o.vel, team: o.team, slot: o.slot, grav: o.grav, blast: o.blast, damage: o.damage, heli: o.heli, until: TNOW + o.life,
                 gunRadius: o.gunRadius || 0, ent: e, i, first: true, src: o.src || "helirocket" });
  stats.rockets++;
}
function tickRockets(dt) {
  for (let i = rockets.length - 1; i >= 0; i--) {
    const r = rockets[i];
    r.vel.z -= r.grav * dt;
    const np = vadd(r.pos, r.vel, dt);
    const seg = vsub(np, r.pos), L = vlen(seg) || 1e-6, dir = vscale(seg, 1 / L);
    let hitAt = -1, heli = null;
    if (!finiteV(np) || TNOW >= r.until || Math.abs(np.x) > AIRX + 900 || Math.abs(np.y) > AIRY + 900 || np.z > AIRZ + 700 || np.z < WATER_Z - 400) {
      if (r.ent) parkEnt(r.ent, r.i);
      rockets.splice(i, 1); continue;               // left the world: no burst on the sky shell
    }
    let tr; try { tr = Instance.TraceLine({ start: r.pos, end: np, ignoreEntity: hitIgnore, ignorePlayers: true }); } catch (e) { tr = undefined; }
    if (tr && tr.didHit) hitAt = tr.fraction * L;
    for (const h of allHelis) {
      if (h.team === r.team || h.state === "dead") continue;
      const d = raySphere(r.pos, dir, L, heliCentre(h), CONFIG.HELI.HIT_RADIUS);
      if (d >= 0 && (hitAt < 0 || d < hitAt)) { hitAt = d; heli = h; }
    }
    for (const q of roster) {
      if (!q.alive || q.team === r.team || q.seated || !q.p.deployed) continue;
      const d = raySphere(r.pos, dir, L, v3(q.pos.x, q.pos.y, q.pos.z + 40), 44);
      if (d >= 0 && (hitAt < 0 || d < hitAt)) { hitAt = d; heli = null; }
    }
    if (hitAt >= 0) {
      const at = vadd(r.pos, dir, hitAt);
      if (r.ent) parkEnt(r.ent, r.i);
      rockets.splice(i, 1);
      if (heli) { damageHeli(heli, r.heli, r.slot, r.src); stats.rocketHeliHits++; }
      blast({ pos: at, radius: r.blast, damage: r.damage, team: r.team, slot: r.slot, loader: -1, fo: -1, heliRadius: heli ? 0 : r.blast * 0.6, heliDamage: r.heli * 0.5,
              gunRadius: r.gunRadius, skipHeli: heli, src: r.src });
      continue;
    }
    r.pos = np;
    if (r.ent) {
      const ang = angOf(vnorm(r.vel));
      try { if (r.first) { r.ent.Teleport({ position: np, angles: ang }); r.first = false; } else r.ent.Move({ position: np, angles: ang }); } catch (e) { r.ent = undefined; }
    }
  }
}
// rocket pair from the pods: toward the aim point, held inside the pods' gimbal around the nose
function fireRockets(h, pawn, aimDir, spread) {
  const R = CONFIG.HELI.ROCKET, M = h.M;
  if (h.rockets < 2 || TNOW < h.rocketAt || h.landed || M.PODS.length < 2) return false;
  h.rocketAt = TNOW + R.PAIR_INTERVAL; h.rockets -= 2;
  const a = angOf(aimDir);
  const yaw = h.yaw + clampN(wrap180(a.yaw - h.yaw), -R.GIMBAL_YAW, R.GIMBAL_YAW), pitch = clampN(a.pitch, -R.GIMBAL_UP, R.GIMBAL_DOWN);
  const org = heliOrigin(h), pair = (h.podI++ % Math.floor(M.PODS.length / 2)) * 2;
  for (let k = 0; k < 2; k++) {
    const s = spread || 0.008;
    const d0 = dirOf({ pitch, yaw, roll: 0 }), d = vnorm(v3(d0.x + gauss() * s, d0.y + gauss() * s, d0.z + gauss() * s));
    launchRocket({ pos: vadd(local(org, h.B, M.PODS[pair + k]), d, 30), vel: vadd(vscale(d, R.SPEED), h.vel, 0.5), team: h.team, slot: h.seats[0].slot, grav: R.GRAVITY,
                   blast: R.BLAST, damage: R.DAMAGE, heli: R.HELI, life: R.LIFE, gunRadius: R.GUN_DISABLE, src: "helirocket" });
  }
  fire("mv_heli_rkt_" + h.tag, "StartSound");
  return true;
}
// where the pilot's crosshair points: the FOLLOW_POSITION camera rebuilt from the eye angles, traced along the eye
function pilotAim(p, h, eye) {
  const C = CONFIG.HELI.CAM, B = angleBasis({ pitch: eye.pitch, yaw: eye.yaw, roll: 0 });
  const cam = vadd(v3(h.pos.x, h.pos.y, h.pos.z + h.groundOff + C.UP), B.f, -(p.camBack || C.BACK));
  const L = 9000;
  let tr; try { tr = Instance.TraceLine({ start: vadd(cam, B.f, (p.camBack || C.BACK) + 200), end: vadd(cam, B.f, L), ignoreEntity: hitIgnore, ignorePlayers: true }); } catch (e) {}
  const pt = tr && tr.didHit ? tr.end : vadd(cam, B.f, L);
  const from = local(heliOrigin(h), h.B, h.M.PODS[0] || [0, 0, 60]);
  return vnorm(vsub(pt, from));
}

// ------------------------------------------------------------------ damage, crash, wreck, respawn
// src = what did it, for the stats ("rifle", "mg", "at", "heligun", "helirocket", "arty", "mount"; no attacker = "crash")
function damageHeli(h, dmg, attackerSlot, src) {
  if (!h || !h.ent || h.state === "dead" || h.state === "crashing" || !(dmg > 0)) return;
  if (attackerSlot >= 0) {
    const q = players.get(attackerSlot);
    if (q && q.team === h.team) return;
    if (TNOW < h.guardUntil) { stats.heliGuard++; return; }      // a helicopter just rolled out on its pad: no kills before anyone can reach it
    h.lastHitBy = attackerSlot; h.lastHitAt = TNOW; h.lastSrc = src || "rifle";
  }
  const k = attackerSlot >= 0 ? src || "rifle" : "crash";
  stats.heliDmgBy[k] = (stats.heliDmgBy[k] || 0) + dmg;
  h.hp -= dmg; stats.heliDamage += dmg;
  if (h.hp <= 0) { h.hp = 0; startCrash(h); return; }
  if (h.hp < CONFIG.HELI.SMOKE_HP) setSmoke(h, true);
}
function startCrash(h) {
  if (h.landed) { explodeHeli(h); return; }
  h.state = "crashing"; h.crashT = TNOW;
  setSmoke(h, true);
  for (const s of h.seats) if (s.slot >= 0) toastSlot(s.slot, "GOING DOWN", 3);
}
function explodeHeli(h) {
  const H = CONFIG.HELI;
  let killerSlot = h.lastHitBy >= 0 && TNOW - h.lastHitAt < H.CRASH_CREDIT ? h.lastHitBy : -1;
  const kq = players.get(killerSlot);
  if (!kq || kq.team !== otherTeam(h.team)) killerSlot = -1;          // the slot changed hands or sides since the hit
  const killer = creditOf(killerSlot, otherTeam(h.team)), src = killerSlot >= 0 ? h.lastSrc || "rifle" : "crash";
  stats.heliLostBy[src] = (stats.heliLostBy[src] || 0) + 1; stats.heliLostTeam[h.team]++;
  if (h.firstFlightAt) { if (stats.heliLives.length < 400) stats.heliLives.push(Math.round(TNOW - h.firstFlightAt)); h.firstFlightAt = 0; }
  const pos = v3(h.pos.x, h.pos.y, h.pos.z + 20);
  const victims = [];
  for (const s of h.seats) {
    if (s.slot < 0) continue;
    const q = players.get(s.slot), pw = pawnOf(s.slot);
    if (q) { leaveHeli(q, pw, "crash"); if (pw) victims.push([q, pw]); }
    s.slot = -1;
  }
  h.state = "dead"; h.landed = true; h.respawnAt = TNOW + H.RESPAWN; h.wreckUntil = TNOW + H.WRECK_TIME; h.vel = v3(0, 0, 0);
  h.rotorSpeed = 0; h.pitch = 0; h.roll = 0; h.ai = null; h.inp = null;
  setEngine(h, false); setDust(h, false); setAnim(h, false);
  stats.heliLost++;
  effects(pos, false);
  if (h.wreck) { try { h.wreck.Teleport({ position: v3(h.pos.x, h.pos.y, h.pos.z), angles: { pitch: 0, yaw: h.yaw + wreckYaw(), roll: 0 } }); h.wreckOut = true; } catch (e) {} }
  const sm = ent("mv_heli_smoke_" + h.tag);
  if (sm) { try { sm.Teleport({ position: v3(h.pos.x, h.pos.y, h.pos.z + 40) }); } catch (e) {} }
  h.smoking = false; setSmoke(h, true);
  parkEnt(h.ent, 20 + h.n + h.team * 4); parkEnt(h.rotor, 30 + h.n); parkEnt(h.tail, 40 + h.n);
  for (const [q, pw] of victims) {
    let a = false; try { a = pw.IsAlive(); } catch (e) {}
    if (a) scriptKill(pw, killer, src);
    a = false; try { a = pw.IsAlive(); } catch (e) {}
    if (a) {                                       // the kill was refused (another plugin, god mode): never leave him frozen in the air
      freeze(q, pw, false);
      try { pw.Teleport({ position: v3(h.pos.x, h.pos.y, groundZ(h.pos.x, h.pos.y, h.pos.z + 120) + 6), velocity: v3(0, 0, 0) }); } catch (e) {}
      equip(q, pw, false); stats.crashSurvivors++;
    }
  }
  blast({ pos, radius: H.CRASH_BLAST, damage: H.CRASH_BLAST_DAMAGE, team: otherTeam(h.team), slot: killerSlot, loader: -1, fo: -1, heliRadius: 0, heliDamage: 0, gunRadius: 0, quiet: true, src });
  if (H.LOSS_TICKETS) loseTicket(h.team, H.LOSS_TICKETS);
  if (killerSlot >= 0) {
    kq.merit++; toast(kq, "Helicopter destroyed!", 3);
    feed(otherTeam(h.team), nameOf(killerSlot) + " shot down a " + h.M.label, "good", false);
    feed(h.team, "We lost a " + h.M.label + " to " + nameOf(killerSlot), "bad", false);
  } else feed(h.team, "Our " + h.M.label + " crashed", "bad", false);
}
function respawnHeli(h) {
  const H = CONFIG.HELI;
  h.state = "parked"; h.landed = true; h.hp = h.maxHp; h.rockets = h.M.ROCKETS; h.rearmAcc = 0;
  h.pos = v3(h.pad.pos.x, h.pad.pos.y, h.pad.pos.z); h.vel = v3(0, 0, 0); h.yaw = h.pad.yaw; h.pitch = 0; h.roll = 0; h.spin = 0;
  h.lastHitBy = -1; h.padT = 0; h.gun = gunFresh(); h.alt = 0; h.speed = 0;
  h.guardUntil = TNOW + H.SPAWN_GUARD; h.idleT = 0; h.firstFlightAt = 0; h.overWater = false;
  setSmoke(h, false);
  placeHeli(h, true);
  setAnim(h, true);
  if (h.owner >= 0) toastSlot(h.owner, "A new " + h.M.label + " is on your pad", 4);
}
function hideWreck(h) {
  if (!h.wreckOut) return;
  h.wreckOut = false; stats.wrecksCleared++;
  parkEnt(h.wreck, 50 + h.n + h.team * 4);
  setSmoke(h, false);
}
// an empty, ownerless helicopter standing in the field goes back to its pad as it is (the pad then repairs and re-arms it)
function recallHeli(h) {
  h.pos = v3(h.pad.pos.x, h.pad.pos.y, h.pad.pos.z); h.vel = v3(0, 0, 0); h.yaw = h.pad.yaw; h.pitch = 0; h.roll = 0;
  h.idleT = 0; h.padT = 0; h.rotorSpeed = 0; h.alt = 0; h.speed = 0;
  setEngine(h, false); setDust(h, false);
  placeHeli(h, true); setAnim(h, true);
  stats.recalls++;
}

// ------------------------------------------------------------------ flight (DESIGN 3.2)
function heliBounds(h) {
  const B = CONFIG.HELI.BOUNDS;
  let w = 0, kind = "";
  for (let k = 0; k < 2; k++) {
    const q = k ? vadd(h.pos, h.vel, B.AHEAD) : h.pos;
    const wxy = Math.max(Math.abs(q.x) - AIRX, Math.abs(q.y) - AIRY) / B.HARD, wz = (q.z - AIRZ) / B.HARD;
    if (wxy > w) { w = wxy; kind = "xy"; }
    if (wz > w) { w = wz; kind = "z"; }
  }
  return { w: clampN(w, 0, 1), kind };
}
function tickHeli(h, dt) {
  const H = CONFIG.HELI;
  if (!h.ent) return;
  h.tick++;
  if (h.state === "dead") {
    if (h.wreckOut && TNOW >= h.wreckUntil) hideWreck(h);
    if (TNOW >= h.respawnAt) { hideWreck(h); respawnHeli(h); }
    return;
  }
  if (h.state === "crashing") { tickCrash(h, dt); return; }
  let inp = h.inp; h.inp = null;
  const piloted = !!inp;
  if (!inp) inp = { fwd: 0, side: 0, coll: h.landed ? 0 : H.AUTOLAND_VS / H.VS_MAX, yaw: h.yaw, fire: false, aim: null, spread: 0 };
  // rotor
  const wantSpin = piloted || !h.landed ? 1 : 0;
  h.rotorSpeed += clampN(wantSpin - h.rotorSpeed, -dt / H.SPOOL, dt / H.SPOOL);
  setEngine(h, h.rotorSpeed > 0.05);
  setAnim(h, false);
  if (h.rotorSpeed > 0) h.spin = (h.spin + H.ROTOR_RPM * h.rotorSpeed * dt) % 360;
  h.warn = "";
  if (h.landed) {
    h.alt = 0; h.speed = 0;
    if (inp.coll > 0.1 && h.rotorSpeed > 0.9) {
      h.landed = false; h.state = "flying"; h.vel = v3(0, 0, 60); h.padT = 0; h.idleT = 0; h.flights++; stats.flights++;
      if (!h.firstFlightAt) h.firstFlightAt = TNOW;
    } else {
      // on the own pad: repair and re-arm
      if (dist2(h.pos, h.pad.pos) < H.PAD_RADIUS) {
        h.padT += dt;
        if (h.padT >= H.REPAIR_TIME && h.hp < h.maxHp) { h.hp = h.maxHp; stats.padRepairs++; setSmoke(h, false); for (const s of h.seats) if (s.slot >= 0) toastSlot(s.slot, "Repaired", 2); }
        if (h.rockets < h.M.ROCKETS) { h.rearmAcc += h.M.ROCKETS * dt / (h.M.REARM_TIME || H.REARM_TIME); if (h.rearmAcc >= 2) { h.rearmAcc -= 2; h.rockets = Math.min(h.M.ROCKETS, h.rockets + 2); stats.padRearms++; } }
        h.warn = h.hp < h.maxHp ? "PAD: REPAIR " + Math.max(0, H.REPAIR_TIME - h.padT).toFixed(0) + " s" : h.rockets < h.M.ROCKETS ? "PAD: RE-ARMING " + h.rockets + "/" + h.M.ROCKETS : "";
        h.idleT = 0;
      } else {
        if (inp.coll > 0.1) h.warn = "ROTOR " + Math.round(h.rotorSpeed * 100) + " %";
        // left in the field with nobody aboard and no pilot assigned (the pilot quit, changed role or went AFK): the ground crew fetch it
        if (h.owner < 0 && crewCount(h) === 0) { h.idleT += dt; if (h.idleT >= H.ABANDON) { recallHeli(h); return; } } else h.idleT = 0;
      }
      if (h.rotorSpeed > 0 && (h.rotor || h.tail)) placeHeli(h, false);
      setDust(h, false);
      return;
    }
  }
  // pedals: the nose follows the wanted yaw
  h.yaw = wrap180(h.yaw + clampN(wrap180(inp.yaw - h.yaw) * H.YAW_GAIN, -H.YAW_RATE, H.YAW_RATE) * dt);
  // cyclic: wanted ground velocity in the heading frame
  const cy = Math.cos(h.yaw * D2R), sy = Math.sin(h.yaw * D2R);
  const tf = inp.fwd >= 0 ? inp.fwd * H.V_FWD : inp.fwd * H.V_BACK, ts = inp.side * H.V_SIDE;
  let tx = cy * tf + sy * ts, ty = sy * tf - cy * ts, vsT = inp.coll * H.VS_MAX;
  const bw = heliBounds(h);
  if (bw.w > 0) {
    if (bw.kind === "z") { vsT = Math.min(vsT, -H.VS_MAX * bw.w); h.warn = "CEILING"; }
    else { const d = Math.hypot(h.pos.x, h.pos.y) || 1; tx += (-h.pos.x / d * H.BOUNDS.HOME_SPEED - tx) * bw.w; ty += (-h.pos.y / d * H.BOUNDS.HOME_SPEED - ty) * bw.w; h.warn = "LEAVING THE VALLEY - TURNING BACK"; }
    if (!h.soft) { h.soft = true; stats.softWall++; }
  } else h.soft = false;
  const ax = (tx - h.vel.x) * H.ACCEL, ay = (ty - h.vel.y) * H.ACCEL, k = Math.min(1, H.ACCEL * dt);
  h.vel.x += (tx - h.vel.x) * k; h.vel.y += (ty - h.vel.y) * k;
  h.vel.z += (vsT - h.vel.z) * Math.min(1, dt / (inp.coll !== 0 || bw.kind === "z" ? H.VS_EASE : H.VS_SETTLE));
  // the body tilts into the acceleration and a little with the speed
  const vf = h.vel.x * cy + h.vel.y * sy, vr = h.vel.x * sy - h.vel.y * cy, af = ax * cy + ay * sy, ar = ax * sy - ay * cy;
  const pT = H.TILT_PITCH * clampN(H.TILT_ACC * af / (H.V_FWD * H.ACCEL) + (1 - H.TILT_ACC) * vf / H.V_FWD, -1, 1);
  const rT = H.TILT_ROLL * clampN(H.TILT_ACC * ar / (H.V_SIDE * H.ACCEL) + (1 - H.TILT_ACC) * vr / H.V_SIDE, -1, 1);
  h.pitch += clampN(pT - h.pitch, -H.TILT_RATE * dt, H.TILT_RATE * dt);
  h.roll += clampN(rT - h.roll, -H.TILT_RATE * dt, H.TILT_RATE * dt);
  // ground under the skids; ground effect
  h.gz = groundZ(h.pos.x, h.pos.y, h.pos.z + 150);
  h.overWater = h.gz < WATER_Z;                      // the river: the surface is the floor, and there is no landing on it
  if (h.overWater) h.gz = WATER_Z;
  h.alt = Math.max(0, h.pos.z - h.gz);
  if (h.alt < H.GE_ALT && h.vel.z < -H.GE_VS) h.vel.z = -H.GE_VS;
  const speed = vlen(h.vel);
  h.speed = Math.hypot(h.vel.x, h.vel.y);
  let np = vadd(h.pos, h.vel, dt);
  if (!finiteV(np) || Math.abs(np.x) > AIRX + H.BOUNDS.HARD || Math.abs(np.y) > AIRY + H.BOUNDS.HARD || np.z > AIRZ + H.BOUNDS.HARD) { h.pos.z = Math.min(h.pos.z, AIRZ + H.BOUNDS.HARD); explodeHeli(h); return; }
  // the airframe against the world along its velocity (floors are the landing code's business)
  if (speed > 30) {
    const dir = vscale(h.vel, 1 / speed), c = v3(h.pos.x, h.pos.y, h.pos.z + H.BODY_UP);
    let tr; try { tr = Instance.TraceLine({ start: c, end: vadd(c, dir, speed * dt + H.BODY_AHEAD * (h.speed / speed)), ignoreEntity: hitIgnore, ignorePlayers: true }); } catch (e) {}
    if (tr && tr.didHit && !(tr.normal && tr.normal.z > 0.7)) {
      damageHeli(h, H.HIT_BASE + speed / H.HIT_DIV, -1);
      if (h.state !== "flying") return;
      h.vel = v3(-h.vel.x * 0.35, -h.vel.y * 0.35, Math.max(h.vel.z, 0) * 0.5);
      np = v3(h.pos.x, h.pos.y, h.pos.z);
      h.warn = "COLLISION";
    }
  }
  // rotor disc: two of the four blade-tip traces per tick
  if (h.alt > H.ROTOR_MIN_ALT && TNOW >= h.rotorHitAt) {
    const m = v3(np.x, np.y, np.z + h.groundOff + h.M.ROTOR_Z), R = h.M.ROTOR_R;
    for (let q = 0; q < 2; q++) {
      const a = (h.yaw + 45 + (h.tick % 2) * 90 + q * 180) * D2R, dx = Math.cos(a), dy = Math.sin(a);
      let tr; try { tr = Instance.TraceLine({ start: m, end: v3(m.x + dx * R, m.y + dy * R, m.z), ignoreEntity: hitIgnore, ignorePlayers: true }); } catch (e) {}
      if (tr && tr.didHit) {
        h.rotorHitAt = TNOW + H.ROTOR_COOLDOWN;
        damageHeli(h, H.ROTOR_DAMAGE, -1);
        if (h.state !== "flying") return;
        h.vel.x = -dx * 160; h.vel.y = -dy * 160; h.warn = "ROTOR STRIKE";
        break;
      }
    }
  }
  // touchdown
  if (np.z <= h.gz && h.vel.z <= 0) {
    const tilt = Math.max(Math.abs(h.pitch), Math.abs(h.roll));
    if (h.overWater) { h.pos = v3(np.x, np.y, h.gz); h.hp = 0; stats.ditched++; for (const s of h.seats) if (s.slot >= 0) toastSlot(s.slot, "DITCHED IN THE RIVER", 3); explodeHeli(h); return; }
    if (tilt < H.LAND_TILT && speed < H.LAND_SPEED) {
      h.pos = v3(np.x, np.y, h.gz); h.vel = v3(0, 0, 0); h.pitch = 0; h.roll = 0; h.landed = true; h.state = "parked"; h.alt = 0; h.speed = 0; h.padT = 0;
      placeHeli(h, false); placeRiders(h, false); setDust(h, false);
      stats.landings++;
      return;
    }
    const dmg = H.CRASH_BASE + speed / H.CRASH_DIV;
    if (dmg > H.CRASH_KILL) { h.pos = v3(np.x, np.y, h.gz); h.hp = 0; stats.crashLandings++; explodeHeli(h); return; }
    stats.hardLandings++;
    damageHeli(h, dmg, -1);
    if (h.state !== "flying") { if (h.state === "crashing") { h.pos = v3(np.x, np.y, h.gz); explodeHeli(h); } return; }
    np.z = h.gz + 2; h.vel = v3(h.vel.x * 0.4, h.vel.y * 0.4, 90); h.warn = "HARD LANDING";
  }
  h.pos = np;
  placeHeli(h, false);
  placeRiders(h, false);
  // rockets
  if (inp.fire && inp.aim && h.M.ROCKETS) fireRockets(h, pawnOf(h.seats[0].slot), inp.aim, inp.spread);
  // effects that follow the airframe
  if (h.smoking && h.tick % 2 === 0) { const sm = ent("mv_heli_smoke_" + h.tag); if (sm) { try { sm.Teleport({ position: v3(np.x, np.y, np.z + h.groundOff + 90) }); } catch (e) {} } }
  const dusty = h.alt < H.DUST_ALT && h.rotorSpeed > 0.5;
  if (dusty && h.tick % 8 === 0) { const du = ent("mv_heli_dust_" + h.tag); if (du) { try { du.Teleport({ position: v3(np.x, np.y, h.gz + 4) }); } catch (e) {} } }
  setDust(h, dusty);
  if (!h.warn && h.hp < H.SMOKE_HP) h.warn = "DAMAGED - RETURN TO THE PAD";
}
function tickCrash(h, dt) {
  const H = CONFIG.HELI, t = TNOW - h.crashT;
  h.yaw = wrap180(h.yaw + H.SPIN_RATE * Math.min(1, t / 0.8) * dt);
  h.rotorSpeed = Math.max(0.15, 1 - t / H.SPINDOWN);
  h.spin = (h.spin + H.ROTOR_RPM * h.rotorSpeed * dt) % 360;
  if (t < H.SPINDOWN) h.vel.z += (-220 - h.vel.z) * Math.min(1, dt * 1.5); else h.vel.z -= H.GRAVITY * dt;
  h.vel.x *= 1 - 0.4 * dt; h.vel.y *= 1 - 0.4 * dt;
  h.roll = clampN(h.roll + 25 * dt, -40, 40); h.pitch = clampN(h.pitch + 12 * dt, -30, 30);
  const np = vadd(h.pos, h.vel, dt);
  h.gz = Math.max(WATER_Z, groundZ(h.pos.x, h.pos.y, h.pos.z + 150));
  h.alt = Math.max(0, h.pos.z - h.gz); h.speed = Math.hypot(h.vel.x, h.vel.y);
  let wall = false;
  if (h.speed > 60) {
    const c = v3(h.pos.x, h.pos.y, h.pos.z + H.BODY_UP), d = vnorm(v3(h.vel.x, h.vel.y, 0));
    let tr; try { tr = Instance.TraceLine({ start: c, end: vadd(c, d, h.speed * dt + 100), ignoreEntity: hitIgnore, ignorePlayers: true }); } catch (e) {}
    wall = !!(tr && tr.didHit);
  }
  if (!finiteV(np) || np.z <= h.gz || wall || t > 20) { h.pos = v3(h.pos.x, h.pos.y, Math.max(h.gz, Math.min(h.pos.z, np.z))); explodeHeli(h); return; }
  h.pos = np;
  placeHeli(h, false);
  placeRiders(h, false);
  if (h.tick % 2 === 0) { const sm = ent("mv_heli_smoke_" + h.tag); if (sm) { try { sm.Teleport({ position: v3(np.x, np.y, np.z + h.groundOff + 90) }); } catch (e) {} } }
}

// ------------------------------------------------------------------ a seated player's tick (pilot keys, gunner, rider)
function tickSeat(p, pawn, dt, pressed, held) {
  const h = p.heli, H = CONFIG.HELI, s = h.seats[p.seat];
  if (!h.ent || h.state === "dead") { leaveHeli(p, pawn, ""); return; }
  const eye = eyeOf(pawn);
  if (s.kind === "pilot") {
    const fireKey = (held & CSInputs.ATTACK) !== 0;
    if (!p.afk) h.inp = { fwd: ((held & CSInputs.FORWARD) ? 1 : 0) - ((held & CSInputs.BACK) ? 1 : 0), side: ((held & CSInputs.RIGHT) ? 1 : 0) - ((held & CSInputs.LEFT) ? 1 : 0),
              coll: ((held & CSInputs.JUMP) ? 1 : 0) - ((held & CSInputs.DUCK) ? 1 : 0), yaw: eye.yaw, fire: fireKey,
              aim: fireKey && h.M.ROCKETS && !h.landed ? pilotAim(p, h, eye) : null, spread: 0 };
    // an AFK pilot (no key, no look for AFK.TIME): the stick is let go so it does not fly on with the last keys held. It settles and
    // lets down; over the river it creeps to the bank first (a landing on water is a ditching). tickAfk takes him out once it is down.
    else h.inp = { fwd: h.overWater ? 0.4 : 0, side: 0, coll: h.overWater ? 0 : -0.5, yaw: Math.atan2(h.pad.pos.y - h.pos.y, h.pad.pos.x - h.pos.x) / D2R, fire: false, aim: null, spread: 0 };
    easeCamera(p, h, dt);
    if (pressed & CSInputs.USE) {
      if (h.landed) { leaveHeli(p, pawn, ""); return; }
      toast(p, "Land first: CTRL takes you down", 2);
    }
  } else {
    if (s.kind === "gunner") { if (pressed & CSInputs.RELOAD) gunReload(h.gun, h.M.GUN); tickHeliGun(h, pawn, p.team, eye, (held & CSInputs.ATTACK) !== 0, dt); }
    if (pressed & CSInputs.USE) { leaveHeli(p, pawn, ""); return; }
  }
  drawFlight(p, h, s);
}
