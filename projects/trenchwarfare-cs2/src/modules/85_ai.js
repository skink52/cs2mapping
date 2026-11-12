// 85_ai: bots. The seam for the bot AI (remaster step 4: infantry deploy targets + leash, script-driven pilots and mortar crews that
// yield to humans). Today: bots are always infantry (chooseRole) and are leashed away from a still-closed area's blocker.
// Entry points the main loop calls: isBot(pawn) when a role is chosen, tickBot(p, pawn, team, dt) every tick for a live deployed bot,
// aiThink(t, dt) once per tick before the players (empty until step 4).

function isBot(pawn) { try { return pawn.GetPlayerController().IsBot(); } catch (e) { return false; } }
// within r (default LEASH) of a blocker of an area that is still closed
function nearLock(o, r) {
  const B = CONFIG.BOTS, R = r || B.LEASH;
  if (!points) return false;
  for (const u of CONFIG.UNLOCKS) {
    if (unlocked.has(u.name)) continue;
    for (const q of (points.locks[u.name] || [])) if (dist2(o, q) < R && Math.abs(o.z - q.z) < B.LEASH_Z) return true;
  }
  return false;
}
function tickBot(p, pawn, team, dt) {
  if (p.role !== "infantry" || !nearLock(pawn.GetAbsOrigin())) { p.leashT = 0; return; }
  p.leashT = (p.leashT || 0) + dt;
  if (p.leashT < CONFIG.BOTS.LEASH_TIME) return;
  p.leashT = 0;
  const dest = pickTrench(team, pawn, true);
  if (dest) { pawn.Teleport({ position: v3(dest.pos.x, dest.pos.y, dest.pos.z + 4), angles: dest.ang, velocity: v3(0, 0, 0) }); stats.leash++; }
}
// step 4 fills this in (AI pilots / crews, deploy targets); called once per tick from think()
function aiThink(t, dt) {}
