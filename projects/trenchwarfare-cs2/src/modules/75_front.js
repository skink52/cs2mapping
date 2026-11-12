// 75_front: the front: areas blown open during the round, cosmetic no man's land bursts

// cosmetic shell bursts and dirt showers in no man's land, never near a player
let nextAmbient = 0;
let roundStart = 0, roundKills = 0; const unlocked = new Set();
function tickUnlocks(t) {
  for (const u of CONFIG.UNLOCKS) {
    if (unlocked.has(u.name) || (roundKills < u.kills && t - roundStart < u.time)) continue;
    unlocked.add(u.name);
    let n = 0;
    for (const e of Entities.FindByName(u.name)) {
      try { if (!e.IsValid()) continue; effects(vadd(e.GetAbsOrigin(), v3(0, 0, 1), 24), false); e.Remove(); n++; } catch (err) {}
    }
    if (!n) continue;
    stats.unlocks++;
    say("[tw] " + u.msg);
    for (const p of players.values()) headline(p, u.msg, 7);     // "TITLE - where" -> the banner plate
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
    stats.ambient++;
    return;
  }
}
