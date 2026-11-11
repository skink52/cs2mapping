// ------------------------------------------------------------------ 50_mounted: emplaced guns (mv_mount_N: the gun part pivots on its pintle)
const mounts = [];
// "<kind>:<team>" of mount n. cs_script cannot read the mv_mountinfo_N message key, so tools/build_script.mjs copies those keys from
// out/entities.json into LAYOUT.mountinfo; a layout.json "mounts" list works too. Without either: by where the gun stands.
function mountInfo(n, pos) {
  let kind = "", team = -1;
  const src = (LAYOUT.mountinfo && (LAYOUT.mountinfo[n] || LAYOUT.mountinfo[String(n)])) || (Array.isArray(LAYOUT.mounts) && LAYOUT.mounts[n - 1]) || "";
  const txt = typeof src === "string" ? src : src && src.kind ? src.kind + ":" + (src.team || "any") : "";
  if (txt) {
    const q = txt.toLowerCase().split(":");
    if (CONFIG.MOUNT.KINDS[q[0]]) kind = q[0];
    team = q[1] === "t" ? T : q[1] === "ct" ? CT : q[1] === "any" ? 0 : -1;
  }
  if (team < 0) {
    team = 0;
    for (const tm of TEAMS) { const c = LAYOUT[tagOf(tm)].centre; if (Math.hypot(pos.x - c[0], pos.y - c[1]) < CONFIG.MOUNT.BASE_RADIUS) team = tm; }
  }
  if (!kind) kind = team === CT ? "m2" : "dshk";
  return { kind, team };
}
function mountMuzzle(kind) {
  const g = LAYOUT.models && LAYOUT.models[kind];
  return g && Number.isFinite(g.muzzle) && g.muzzle > 0 ? g.muzzle : CONFIG.MOUNT.MUZZLE;
}
function loadMounts() {
  mounts.length = 0;
  for (let n = 1; n <= CONFIG.MOUNT.MAX; n++) {
    const e = ent("mv_mount_" + n); if (!e) continue;
    const pos = e.GetAbsOrigin(), ang = e.GetAbsAngles(), seat = poseOf("mv_mountseat_" + n), inf = mountInfo(n, pos);
    const B = angleBasis({ pitch: 0, yaw: ang.yaw, roll: 0 });
    need("mv_mount_snd_" + n);
    mounts.push({ n, name: "mv_mount_" + n, ent: e, pos, yaw0: ang.yaw, seat: seat || { pos: local(pos, B, [-50, 0, -30]), ang: { pitch: 0, yaw: ang.yaw, roll: 0 } },
                  kind: inf.kind, K: CONFIG.MOUNT.KINDS[inf.kind], muzzle: mountMuzzle(inf.kind), team: inf.team, user: -1, st: gunFresh(),
                  aimYaw: ang.yaw, aimPitch: 0, sentYaw: ang.yaw, sentPitch: 0, cone: inf.team ? CONFIG.MOUNT.CONE : CONFIG.MOUNT.CONE_ANY });
  }
}
function mountNear(p, pos) {
  let best = null, bd = CONFIG.MOUNT.USE_RADIUS;
  for (const m of mounts) {
    if (Math.abs(pos.z - m.seat.pos.z) > 90) continue;
    const d = dist2(pos, m.seat.pos);
    if (d < bd) { bd = d; best = m; }
  }
  return best;
}
function mountFree(m, p) {
  if (m.team && m.team !== p.team) return false;
  if (m.user < 0) return true;
  const q = players.get(m.user);
  return !p.bot && !!q && q.bot;
}
function takeMount(p, pawn, m) {
  if (!mountFree(m, p)) return false;
  if (m.user >= 0) { const q = players.get(m.user); if (q) aiRelease(q, true); if (m.user >= 0) return false; }
  unseat(p, pawn, "seat");
  m.user = p.slot; p.mount = mounts.indexOf(m);
  stow(pawn);
  freeze(p, pawn, true);
  try { pawn.Teleport({ position: v3(m.seat.pos.x, m.seat.pos.y, m.seat.pos.z + 2), velocity: v3(0, 0, 0) }); pawn.SetEyeAngles({ pitch: 0, yaw: m.yaw0, roll: 0 }); } catch (e) {}
  let cam; try { cam = typeof pawn.GetCustomCamera === "function" ? pawn.GetCustomCamera() : undefined; } catch (e) {}
  if (cam) {
    const C = CONFIG.MOUNT.CAM;
    try {
      cam.SetFollowConfig({ followEntity: m.ent, followOffset: v3(0, 0, C.up), cameraOffset: v3(-C.back, 0, 0), clipCameraOffset: true });
      cam.SetMode(CustomCameraMode.FOLLOW_POSITION);
      p.cam = cam; p.camKind = "mount";
    } catch (e) {}
  }
  if (!p.bot) toast(p, m.K.name + ": MOUSE1 fires, R reloads, E lets go", 3);
  stats.mountUses++;
  return true;
}
function leaveMount(p, pawn) {
  const m = mounts[p.mount];
  if (m && m.user === p.slot) m.user = -1;
  p.mount = -1;
  restoreCamera(p);
  let alive = false; try { alive = !!pawn && pawn.IsAlive(); } catch (e) {}
  if (alive) { freeze(p, pawn, false); equip(p, pawn, false); }
  hClass(p, "mv_gun", "show", false);
}
// aim (clamped to the cone around the gun's rest direction), move the gun part, fire
function mountAim(m, eye, firing, pawn, team, dt, spread) {
  const C = CONFIG.MOUNT;
  const aim = clampAim(eye, m.yaw0, m.cone, C.UP, C.DOWN);
  m.aimYaw = aim.yaw; m.aimPitch = aim.pitch;
  if (Math.abs(aim.yaw - m.sentYaw) > 0.25 || Math.abs(aim.pitch - m.sentPitch) > 0.25) {
    m.sentYaw = aim.yaw; m.sentPitch = aim.pitch;
    try { m.ent.Move({ angles: { pitch: aim.pitch, yaw: aim.yaw, roll: 0 } }); } catch (e) {}
  }
  if (gunTick(m.st, m.K, firing, dt)) {
    const dir = dirOf(aim);
    gunRound(m.st, m.K, vadd(m.pos, dir, m.muzzle), dir, pawn, team, "mv_mount_snd_" + m.n, C.RANGE, spread, "mount");
  }
}
function tickMount(p, pawn, dt, pressed, held) {
  const m = mounts[p.mount];
  if (!m || m.user !== p.slot) { leaveMount(p, pawn); return; }
  if (pressed & CSInputs.RELOAD) gunReload(m.st, m.K);
  mountAim(m, eyeOf(pawn), (held & CSInputs.ATTACK) !== 0, pawn, p.team, dt);
  if (pressed & CSInputs.USE) { leaveMount(p, pawn); return; }
  drawGun(p, m.K.name, m.st, m.K);
}
