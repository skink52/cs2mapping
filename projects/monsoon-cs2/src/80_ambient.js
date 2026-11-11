// ------------------------------------------------------------------ 80_ambient: distant harassing fire (cosmetic, never near a player)
// The standing ambience (smoke columns, birds, the soundscape) is map entities; this only adds an occasional far burst from the effect pool.
let nextAmbient = 0;
function tickAmbient() {
  const A = CONFIG.AMBIENT;
  if (!A.ON || TNOW < nextAmbient) return;
  nextAmbient = TNOW + A.MIN + Math.random() * (A.MAX - A.MIN);
  for (let tries = 0; tries < 5; tries++) {
    const x = (Math.random() * 2 - 1) * (MAPX - 600), y = (Math.random() * 2 - 1) * (MAPY - 600);
    let near = false;
    for (const r of roster) if (r.alive && dist2(r.pos, { x, y }) < A.CLEAR) { near = true; break; }
    if (near) continue;
    for (const h of allHelis) if (h.state !== "dead" && dist2(h.pos, { x, y }) < A.CLEAR) { near = true; break; }
    if (near) continue;
    effects(v3(x, y, groundZ(x, y) + 8), true);
    return;
  }
}
