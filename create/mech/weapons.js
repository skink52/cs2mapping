// mech weapons: scripted shots on stock guns. CONFIG.weapons = [{ weapon: "weapon_awp", kind: "pierce" | "explosive" | "burst" | "knockback", ... }]
//   pierce:    the shot goes on through players and thin walls: up to `pierce` (3) hits along `range` (8192), `damage` each, falling
//              off by `falloff` (0.8) per hit (a railgun)
//   explosive: where the bullet lands, players within `radius` (160) take up to `damage` (80) (linear falloff) and are pushed `push` (400)
//   burst:     each shot fires `count` (3) extra traced pellets with `spread` degrees, `damage` each
//   knockback: a player the shot hits is pushed `push` (500) along the shot
// The gun's own bullet still fires; set its damage low in the weapon's vdata if only the scripted shot should count. Ported from
// cs2-map-mcp's weapons.py + mechanics/fire.js (Rmgs123, MIT): the shot-engine kinds; fresh code on create/mech/core.js.

function weaponsInstall() {
  const list = CONFIG.weapons || [];
  if (!list.length) return;
  const byClass = new Map(list.map((w) => [w.weapon, w]));
  const isPlayer = (e) => e && e.IsValid() && !!e.GetPlayerController && e.IsAlive && e.IsAlive();
  Instance.OnGunFire((e) => {
    const w = byClass.get(e.weapon.GetClassName()); if (!w) return;
    const shooter = e.weapon.GetOwner(); if (!shooter || !shooter.IsValid()) return;
    const eye = shooter.GetEyePosition(), ang = shooter.GetEyeAngles();
    if (w.kind === "pierce") {
      let start = eye, dmg = w.damage || 100; const dir = fwdOf(ang), end = vAdd(eye, vMul(dir, w.range || 8192));
      const ignore = [shooter];
      for (let i = 0; i < (w.pierce || 3); i++) {
        const tr = Instance.TraceLine({ start: start, end: end, ignoreEntity: ignore.slice(-2), traceHitboxes: true });
        if (!tr.didHit) break;
        if (isPlayer(tr.hitEntity)) { tr.hitEntity.TakeDamage({ damage: dmg, attacker: shooter, inflictor: e.weapon }); ignore.push(tr.hitEntity); }
        dmg *= w.falloff !== undefined ? w.falloff : 0.8;
        start = vAdd(tr.end, vMul(dir, 8));
      }
    } else if (w.kind === "burst") {
      for (let i = 0; i < (w.count || 3); i++) {
        const s = w.spread || 4;
        const a = { pitch: ang.pitch + (Math.random() * 2 - 1) * s, yaw: ang.yaw + (Math.random() * 2 - 1) * s, roll: 0 };
        const tr = Instance.TraceLine({ start: eye, end: vAdd(eye, vMul(fwdOf(a), w.range || 4096)), ignoreEntity: shooter, traceHitboxes: true });
        if (tr.didHit && isPlayer(tr.hitEntity)) tr.hitEntity.TakeDamage({ damage: w.damage || 15, attacker: shooter, inflictor: e.weapon });
      }
    } else if (w.kind === "knockback") {
      const dir = fwdOf(ang);
      const tr = Instance.TraceLine({ start: eye, end: vAdd(eye, vMul(dir, w.range || 4096)), ignoreEntity: shooter, traceHitboxes: true });
      if (tr.didHit && isPlayer(tr.hitEntity)) tr.hitEntity.Teleport({ velocity: vAdd(tr.hitEntity.GetAbsVelocity(), vAdd(vMul(dir, w.push || 500), vec(0, 0, 150))) });
    }
  });
  Instance.OnBulletImpact((e) => {
    const w = byClass.get(e.weapon.GetClassName()); if (!w || w.kind !== "explosive") return;
    const shooter = e.weapon.GetOwner();
    const now = MECH.now, key = "boom";
    const st = shooter && shooter.IsValid() ? slotState(pawnSlot(shooter)) : {};
    if (st[key] === now) return;                                         // one blast per shot (buckshot lands many pellets)
    st[key] = now;
    const r = w.radius || 160;
    for (const pl of mechPlayers()) {
      const c = vAdd(pl.pawn.GetAbsOrigin(), vec(0, 0, 36)), d = vLen(vSub(c, e.position));
      if (d > r) continue;
      const k = 1 - d / r;
      pl.pawn.TakeDamage({ damage: (w.damage || 80) * k, attacker: shooter && shooter.IsValid() ? shooter : undefined });
      if (pl.pawn.IsValid() && pl.pawn.IsAlive()) pl.pawn.Teleport({ velocity: vAdd(pl.pawn.GetAbsVelocity(), vMul(vNorm(vSub(c, e.position)), (w.push || 400) * k)) });
    }
  });
}
