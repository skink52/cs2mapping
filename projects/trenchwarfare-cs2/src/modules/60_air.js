// 60_air: aircraft: arcade flight, guns, bombs, tracers, sights, cameras, crash

// ------------------------------------------------------------------ aircraft (arcade, mouse aim)
const bombs = [];
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
// a reversal keeps the side it started on (st.revSide) until it is done: with the aim almost straight behind, the side flipped from
// tick to tick (the bounds blend nudges the aim across 180 degrees), the plane never turned and held its dive into the ground
function capHeading(f, aim, maxRad, st) {
  const yf = Math.atan2(f.y, f.x), ya = Math.atan2(aim.y, aim.x);
  const dy = Math.atan2(Math.sin(ya - yf), Math.cos(ya - yf));
  if (Math.abs(dy) <= maxRad || Math.hypot(aim.x, aim.y) < 1e-3) { if (st) st.revSide = 0; return aim; }
  let side = Math.sign(dy) || 1;
  if (st) { if (st.revSide) side = st.revSide; else st.revSide = side; }
  const y = yf + side * maxRad, pz = clampN(aim.z, -1, 1), h = Math.sqrt(1 - pz * pz);
  return v3(Math.cos(y) * h, Math.sin(y) * h, pz);
}
function farOutside(pos) {
  const A = CONFIG.AIR, F = A.BOUNDS.FAR;
  return Math.abs(pos.x) > A.BOX_X + F || Math.abs(pos.y) > A.BOX_Y + F || pos.z > A.ALT_MAX + F;
}
// the chase camera's position and view (the crosshair), rebuilt the way FOLLOW_POSITION places it: followed point + offset turned
// by the eye angles; guns converge on what the crosshair covers, within GUN_GIMBAL of the nose. A script pilot (85_ai) has no
// crosshair: steer.gunAt is the point it aims at (with its error already in it), held to the same gimbal
function gunAim(a, pawn, steer) {
  const A = CONFIG.AIR, F = A.CAM_FOLLOW;
  if (steer) {
    const s = v3(a.pos.x + a.f.x * A.GUN_FROM, a.pos.y + a.f.y * A.GUN_FROM, a.pos.z + 40 + a.f.z * A.GUN_FROM);
    const pt = steer.gunAt || vadd(s, a.f, A.SIGHT_DIST), want = vnorm(v3(pt.x - s.x, pt.y - s.y, pt.z - s.z)), g = A.GUN_GIMBAL * D2R;
    return { s, dir: angleBetween(a.f, want) <= g ? want : rotateToward(a.f, want, g), dist: Math.max(200, Math.min(A.SIGHT_DIST * 3, dist3(pt, s))) };
  }
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
  // a human takes one a script bot flies when none is free: the bot gives it up in this same call (aiYieldAircraft)
  const ac = list.find(a => a.pilot === p.slot) || list.find(a => a.pilot < 0) || (p.bot ? undefined : aiYieldAircraft(team, p));
  if (!ac) { toast(p, "No aircraft free - back to the trenches", 4); return false; }
  ac.pilot = p.slot;
  const A = CONFIG.AIR;
  const base = dest ? dest.pos : ac.park;
  const f = v3(team === CT ? -1 : 1, 0, 0);
  p.air = { ac, pos: v3(base.x, base.y, base.z + A.SPAWN_ALT), f, speed: A.V_CRUISE * 0.9, throttle: 0.7, bank: 0, yawRate: 0,
            phi: 0, stick: 0, roll: 0, angSent: undefined, propSent: undefined, camBack: -A.CAM_OFFSET.x, camSentBack: -A.CAM_OFFSET.x, camSentAt: -99,
            pullUp: false, tick: 0, aim: undefined,
            nextGun: 0, bombs: A.BOMBS, rearmAt: 0, lastHitBy: -1, lastHitGen: 0, lastHitAt: -99, warned: 0, ammo: A.GUN_AMMO, reloadAt: 0,
            view: A.VIEW_DEFAULT, cam: undefined, camParent: undefined };
  try { pawn.DestroyWeapons(); pawn.GiveNamedItem("weapon_knife", false); } catch (e) {}
  try { pawn.SetMoveType(CSMoveType.NONE); } catch (e) {}
  hidePawn(pawn, true);                                 // the aircraft carries its own pilot figure; hits on the plane go to the pawn
  try { pawn.SetEyeAngles({ pitch: 0, yaw: team === CT ? 180 : 0, roll: 0 }); } catch (e) {}
  placePlane(p, pawn, true);
  if (!p.bot) setView(p, pawn);                         // a bot has no screen: no camera
  const nm = ac.ent.GetEntityName(), tg = nm.slice("tw_plane_".length);
  for (const k of ["eng", "gun", "gun2", "gun3"]) fire("tw_plane_" + k + "_" + tg, "SetSourceEntity", nm);
  fire("tw_plane_eng_" + tg, "StartSound", undefined, 0.05);
  p.sortie = true; p.lastActive = now(); stats.flights++;
  if (p.aiRole === "pilot") { stats.aiSorties++; p.aiFly = undefined; }
  return true;
}
function endFlight(p, pawn, crashed) {
  const a = p.air; if (!a) return;
  p.air = undefined;
  // the wreck hurts the pilot's enemies where it comes down, credited to the pilot. (It was credited to whoever last hit the plane:
  // that is the victims' own team-mate, so every death under a shot-down plane was a team kill. The hitter gets the pilot: crashPilot.)
  if (crashed) {
    stats.crashes++;
    impact({ team: p.team, k: -1, firerSlot: p.slot, firerGen: p.gen, src: "crash", x: a.pos.x, y: a.pos.y, z: a.pos.z, radius: 260, damage: 60 });
  }
  if (live(a.ac.ent)) {
    fire("tw_plane_eng_" + a.ac.ent.GetEntityName().slice("tw_plane_".length), "StopSound");
    fire("tw_plane_smoke_" + a.ac.ent.GetEntityName().slice("tw_plane_".length), "Stop");
    a.ac.ent.Teleport({ position: a.ac.park, angles: a.ac.parkAng, velocity: v3(0, 0, 0) });
    placeProp(a.ac);
  }
  a.ac.pilot = -1;
  park(a.ac, a.ac.gsight); park(a.ac, a.ac.bsight);
  hClass(p, "tw_fly", "show", false); hClass(p, "tw_prompt", "show", false);
  if (pawn && live(pawn)) {
    try { const cam = pawn.GetCustomCamera(); if (cam) { cam.SetMode(CustomCameraMode.DISABLED); if (a.camParent) cam.SetParent(a.camParent); } } catch (e) {}
    try { if (pawn.IsAlive()) pawn.SetMoveType(CSMoveType.WALK); } catch (e) {}
    hidePawn(pawn, false);
  }
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
  const killer = a.lastHitBy >= 0 && now() - a.lastHitAt < CONFIG.AIR.CRASH_CREDIT ? creditOf(a.lastHitBy, enemyOf(p.team), a.lastHitGen) : undefined;
  endFlight(p, pawn, true);
  p.crashing = true;
  hurt(pawn, { damage: 1000, damageTypes: CSDamageTypes.BLAST, attacker: killer || pawn, inflictor: killer || pawn }, killer ? "shot_down" : "crash_self");
  p.crashing = false;
}
function hitPilot(ac, damage, attackerPawn, src) {
  if (!ac || ac.pilot < 0) return;
  const vp = pawnOf(ac.pilot); const p = players.get(ac.pilot);
  if (!vp || !vp.IsAlive() || !p || !p.air) return;
  if (attackerPawn && attackerPawn.GetTeamNumber() === vp.GetTeamNumber()) return;
  const as = attackerPawn ? slotOfPawn(attackerPawn) : -1;
  if (as >= 0) { const q = players.get(as); p.air.lastHitBy = as; p.air.lastHitGen = q ? q.gen : 0; p.air.lastHitAt = now(); }
  stats.planeHits++;
  hurt(vp, { damage, attacker: attackerPawn, inflictor: attackerPawn }, src || "shot_down");
}
// steer: a script pilot's inputs (85_ai aiSteer): { aim, held, pressed, gunAt } in place of the eye angles and the keys
function tickAir(p, pawn, dt, pressed, held, steer) {
  const a = p.air, A = CONFIG.AIR, t = now();
  if (!live(a.ac.ent)) { endFlight(p, pawn, false); return ""; }
  if (steer) { held = steer.held; pressed = steer.pressed; }
  if (held & CSInputs.FORWARD) a.throttle = Math.min(1, a.throttle + A.ACCEL * dt);
  if (held & CSInputs.BACK) a.throttle = Math.max(0, a.throttle - A.ACCEL * dt);
  // aim: where the pilot looks (raw, every tick); near the walls / ceiling blended toward home, nose down in a stall
  let aim = steer ? steer.aim : dirOf(pawn.GetEyeAngles());
  if (!finiteV(aim)) aim = a.f;
  let prompt = "";
  const bw = boundsWeight(a);
  if (bw.w > 0) {
    const home = vnorm(v3(-a.pos.x, -a.pos.y, A.BOUNDS.HOME_Z - a.pos.z));
    // blended by heading and climb separately: a vector sum (or slerp) of two nearly opposite directions points straight up
    // the turn home keeps its side (a.wallSide) while home is nearly behind: flying straight out, the side flipped as the plane
    // crossed the line to the centre, the turn undid itself and the aircraft overflew the wall into farOutside (destroyed)
    const ya = Math.atan2(aim.y, aim.x), yh = Math.atan2(home.y, home.x);
    let dh = Math.atan2(Math.sin(yh - ya), Math.cos(yh - ya));
    if (Math.abs(dh) > 150 * D2R && a.wallSide) dh = a.wallSide * Math.abs(dh); else a.wallSide = Math.sign(dh) || 1;
    const y = ya + bw.w * dh;
    const pz = clampN(aim.z + (clampN(home.z, -0.3, 0.3) - aim.z) * bw.w, -1, 1), hz = Math.sqrt(1 - pz * pz);
    aim = v3(Math.cos(y) * hz, Math.sin(y) * hz, pz);
    prompt = bw.kind === "z" ? "Too high - engine starving" : "Leaving the front - turning back";
  } else a.wallSide = 0;
  if (a.speed < A.V_STALL) { aim = vnorm(v3(aim.x, aim.y, Math.min(aim.z, -0.5))); prompt = "STALL - nose down"; }
  const gz = groundZ(a.pos.x, a.pos.y);
  a.gz = gz;
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
  aim = capHeading(a.f, aim, Math.PI / 2, a);
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
  a.aim = gunAim(a, pawn, steer);
  if (a.view === "cockpit") { const cam = a.cam; if (cam && live(cam)) { try { cam.Move({ position: cockpitPos(a) }); } catch (e) {} } }
  // guns (belt; a short re-arm when empty)
  if (a.ammo <= 0 && t >= a.reloadAt) { a.ammo = A.GUN_AMMO; }
  if ((held & CSInputs.ATTACK) && t >= a.nextGun && a.ammo > 0) {
    a.nextGun = t + A.GUN_INTERVAL; stats.gunRounds++; if (steer) stats.aiGunRounds++;
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
      if (ac) hitPilot(ac, A.GUN_DAMAGE * 1.5, pawn, "plane_gun");
      else {
        const hp = toPawn(he);
        if (hp && hp.IsAlive() && hp.GetTeamNumber() !== pawn.GetTeamNumber()) { stats.gunHits++; hurt(hp, { damage: A.GUN_DAMAGE, attacker: pawn, inflictor: pawn }, "plane_gun"); }
      }
    }
  }
  // bombs
  if (a.bombs < A.BOMBS && t >= a.rearmAt) { a.bombs++; a.rearmAt = t + A.BOMB_REARM; }
  let bombKey = (pressed & CSInputs.ATTACK2) !== 0;
  if (!steer) { try { bombKey = bombKey || pawn.WasInputJustPressed(CSInputs.ATTACK2); } catch (e) {} }   // a bot's own brain must not drop bombs
  if (bombKey && a.bombs > 0) {
    a.bombs--; if (a.rearmAt < t) a.rearmAt = t + A.BOMB_REARM;
    const be = a.ac.bombEnts.find(e => !bombs.some(b => b.ent === e));
    bombs.push({ pos: v3(a.pos.x, a.pos.y, a.pos.z - 20), vel: v3(a.f.x * a.speed, a.f.y * a.speed, a.f.z * a.speed), team: pawn.GetTeamNumber(), slot: p.slot, gen: p.gen, ent: be, ac: a.ac });
    stats.bombs++; if (steer) stats.aiBombs++;
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
function tickBombs(dt) {
  const A = CONFIG.AIR;
  for (let i = bombs.length - 1; i >= 0; i--) {
    const b = bombs[i];
    b.vel.z -= A.GRAVITY * dt;
    const np = vadd(b.pos, b.vel, dt);
    const tr = Instance.TraceLine({ start: b.pos, end: np, ignoreEntity: planeEnts(), ignorePlayers: true });
    if (tr && tr.didHit) {
      bombs.splice(i, 1); if (b.ent) park(b.ac, b.ent);
      impact({ team: b.team, k: -1, firerSlot: b.slot, firerGen: b.gen, src: "bomb", x: tr.end.x, y: tr.end.y, z: tr.end.z, radius: A.BOMB_RADIUS, damage: A.BOMB_DAMAGE });
    } else if (np.z < -2000) { bombs.splice(i, 1); if (b.ent) park(b.ac, b.ent); }
    else { b.pos = np; if (b.ent) { try { b.ent.Teleport({ position: np, angles: angOf(vnorm(b.vel)) }); } catch (e) {} } }
  }
}
