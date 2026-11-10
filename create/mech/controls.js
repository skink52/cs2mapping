// mech controllables: CONFIG.controls = [{ kind: "drone" | "car" | "turret", prop: "<prop_dynamic name>", radius: 96, ... }]
// Stand within `radius` of the prop and press USE to take control; USE again leaves. While in control the player is held at the seat
// (where they stood, or `seat: [x, y, z]`) and the prop moves:
//   drone:  WASD along the view, JUMP up, DUCK down; speed (u/s, 400); stops at walls (traced); hp (50) from map damage -> "<prop>_hit"
//   car:    W / S throttle (accel 500, max speed 700), A / D steer (slower at speed), sticks to the ground under it (traced), friction
//   turret: yaw / pitch follow the view inside yaw_limit / pitch_limit around its spawn angles; ATTACK fires `rate` shots a second,
//           each traced `range` and doing `damage` to a player it hits; heat +0.08 a shot, overheats at 1 (2 s cool-down)
// HUD: ctl (status), ctl_speed / ctl_heat. Ported from cs2-map-mcp's control.py, vehicles.py, turrets.py and data/control/drone.js,
// vehicles/car.js, turrets/turret.js (Rmgs123, MIT): the same three kinds, E to enter, seat hold; fresh, much simpler code (kinematic:
// no suspension or physics body) on create/mech/core.js. Props move with Move (interpolated), never a Teleport per tick (docs/reference/cs_script-notes.md).

function controlsInstall() {
  const list = CONFIG.controls || [];
  const C = list.map((c) => ({ cfg: c, ent: null, driver: -1, seat: null, pos: null, ang: null, home: null, vel: vec(0, 0, 0), speed: 0, heat: 0, lock: 0, next: 0, hp: c.hp || 50 }));
  function ent(c) {
    if (!c.ent || !c.ent.IsValid()) {
      c.ent = Instance.FindEntityByName(c.cfg.prop) || null;
      if (c.ent) { c.pos = c.ent.GetAbsOrigin(); c.ang = c.ent.GetAbsAngles(); c.home = { pitch: c.ang.pitch, yaw: c.ang.yaw, roll: c.ang.roll }; }
    }
    return c.ent;
  }
  function leave(c, pawn) {
    if (pawn && pawn.IsValid()) hudSet(pawnSlot(pawn), "ctl", "");
    c.driver = -1; c.speed = 0; c.vel = vec(0, 0, 0);
  }
  C.forEach((c) => Instance.OnScriptInput(c.cfg.prop + "_hit", () => { if (--c.hp <= 0 && c.ent) { fire(c.cfg.prop, "Break"); c.ent = null; c.driver = -1; } }));
  onStart(() => { for (const c of C) { c.ent = null; c.driver = -1; c.hp = c.cfg.hp || 50; c.heat = 0; } });
  every((now) => {
    const dt = MECH.dt;
    const players = mechPlayers();
    for (const c of C) {
      const e = ent(c); if (!e) continue;
      const drv = c.driver >= 0 ? players.find((p) => p.slot === c.driver) : undefined;
      if (c.driver >= 0 && !drv) { leave(c); continue; }
      if (!drv) {                                                    // take control
        for (const pl of players) {
          if (!pl.pawn.WasInputJustPressed(CSInputs.USE) || vLen(vSub(pl.pawn.GetAbsOrigin(), c.pos)) > (c.cfg.radius || 96)) continue;
          if (C.some((o) => o.driver === pl.slot)) continue;
          c.driver = pl.slot; c.seat = c.cfg.seat ? vec(c.cfg.seat[0], c.cfg.seat[1], c.cfg.seat[2]) : pl.pawn.GetAbsOrigin();
          slotState(pl.slot).ctlSince = now; hudSet(pl.slot, "ctl", c.cfg.kind + ": USE to leave");
          break;
        }
        continue;
      }
      const pawn = drv.pawn, st = slotState(drv.slot);
      if (pawn.WasInputJustPressed(CSInputs.USE) && now - st.ctlSince > 0.3) { leave(c, pawn); continue; }
      pawn.Teleport({ position: c.seat, velocity: vec(0, 0, 0) });
      const view = pawn.GetEyeAngles();
      const k = (b) => pawn.IsInputPressed(b) ? 1 : 0;
      if (c.cfg.kind === "drone") {
        const f = fwdOf(view), r = vec(Math.sin(view.yaw * Math.PI / 180), -Math.cos(view.yaw * Math.PI / 180), 0);
        let want = vAdd(vMul(f, k(CSInputs.FORWARD) - k(CSInputs.BACK)), vMul(r, k(CSInputs.RIGHT) - k(CSInputs.LEFT)));
        want = vAdd(want, vec(0, 0, k(CSInputs.JUMP) - k(CSInputs.DUCK)));
        c.vel = vAdd(vMul(c.vel, 0.9), vMul(vNorm(want), (c.cfg.speed || 400) * 0.1));
        move(c, e, vMul(c.vel, dt), { pitch: 0, yaw: view.yaw, roll: 0 });
        hudSet(drv.slot, "ctl_speed", Math.round(vLen(c.vel)));
      } else if (c.cfg.kind === "car") {
        const throttle = k(CSInputs.FORWARD) - k(CSInputs.BACK), steer = k(CSInputs.LEFT) - k(CSInputs.RIGHT);
        const max = c.cfg.speed || 700;
        c.speed = clamp(c.speed + throttle * (c.cfg.accel || 500) * dt, -max * 0.4, max);
        if (!throttle) c.speed *= Math.pow(0.4, dt);
        const turn = steer * (c.cfg.turn || 90) * dt * clamp(Math.abs(c.speed) / 200, 0, 1) * Math.sign(c.speed || 1) / (1 + Math.abs(c.speed) / max);
        c.ang = { pitch: 0, yaw: c.ang.yaw + turn, roll: 0 };
        const step = vMul(flatFwd(c.ang), c.speed * dt);
        const next = vAdd(c.pos, step);
        const g = Instance.TraceLine({ start: vAdd(next, vec(0, 0, 48)), end: vAdd(next, vec(0, 0, -256)), ignoreEntity: e, ignorePlayers: true });
        if (g.didHit) next.z = g.end.z + (c.cfg.ride || 0);
        move(c, e, vSub(next, c.pos), c.ang);
        hudSet(drv.slot, "ctl_speed", Math.round(Math.abs(c.speed)));
      } else if (c.cfg.kind === "turret") {
        const yl = c.cfg.yaw_limit || 60, pl = c.cfg.pitch_limit || 30;
        let dy = ((view.yaw - c.home.yaw + 540) % 360) - 180;
        c.ang = { pitch: clamp(view.pitch, -pl, pl), yaw: c.home.yaw + clamp(dy, -yl, yl), roll: 0 };
        if (!c.lastAng || c.lastAng.pitch !== c.ang.pitch || c.lastAng.yaw !== c.ang.yaw) { e.Move({ angles: c.ang }); c.lastAng = c.ang; }
        c.heat = Math.max(0, c.heat - dt * 0.25);
        if (c.lock > now) { hudSet(drv.slot, "ctl_heat", "OVERHEAT"); continue; }
        if (pawn.IsInputPressed(CSInputs.ATTACK) && now >= c.next) {
          c.next = now + 1 / (c.cfg.rate || 8); c.heat += 0.08;
          const muzzle = vAdd(c.pos, vec(0, 0, c.cfg.muzzle_z || 48)), dir = fwdOf(c.ang);
          const tr = Instance.TraceLine({ start: muzzle, end: vAdd(muzzle, vMul(dir, c.cfg.range || 4096)), ignoreEntity: [e, pawn], traceHitboxes: true });
          if (tr.didHit && tr.hitEntity && tr.hitEntity.IsValid() && tr.hitEntity.GetPlayerController) tr.hitEntity.TakeDamage({ damage: c.cfg.damage || 20, attacker: pawn });
          if (c.heat >= 1) { c.lock = now + 2; c.heat = 0.6; }
        }
        hudSet(drv.slot, "ctl_heat", Math.round(c.heat * 100) + "%");
      }
    }
  });
  function move(c, e, delta, ang) {
    if (vLen(delta) > 0.01) {
      const tr = Instance.TraceLine({ start: c.pos, end: vAdd(c.pos, vMul(delta, 1.5)), ignoreEntity: e, ignorePlayers: true });
      if (tr.didHit && c.cfg.kind === "drone") delta = vMul(delta, Math.max(0, tr.fraction * 1.5 - 0.5));
      c.pos = vAdd(c.pos, delta);
    }
    const turned = !c.ang || c.ang.yaw !== ang.yaw || c.ang.pitch !== ang.pitch;
    c.ang = ang;
    if (vLen(delta) > 0.01 || turned) e.Move({ position: c.pos, angles: ang });   // Move keeps interpolation; Teleport every tick isn't drawn
  }
}
