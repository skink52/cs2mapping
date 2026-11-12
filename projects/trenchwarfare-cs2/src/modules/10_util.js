// 10_util: small helpers: entities, players, effects by name, vectors and angles, ground traces

// ------------------------------------------------------------------ helpers
const now = () => Instance.GetGameTime();
function live(e) { try { return e && e.IsValid() ? e : undefined; } catch (err) { return undefined; } }
function v3(x, y, z) { return { x, y, z }; }
function dist2(a, b) { const dx = a.x - b.x, dy = a.y - b.y; return Math.sqrt(dx * dx + dy * dy); }
function dist3(a, b) { const dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z; return Math.sqrt(dx * dx + dy * dy + dz * dz); }
function gauss() { let u = 0, v = 0; while (u === 0) u = Math.random(); while (v === 0) v = Math.random(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
function toPawn(ent) {
  if (!ent) return undefined;
  try { if (typeof ent.GetPlayerPawn === "function") return live(ent.GetPlayerPawn()); } catch (e) {}
  try { if (typeof ent.GetPlayerController === "function") return live(ent); } catch (e) {}
  return undefined;
}
function pawnOf(slot) { const c = Instance.GetPlayerController(slot); return c ? live(c.GetPlayerPawn()) : undefined; }
function nameOf(slot) { const c = Instance.GetPlayerController(slot); return c ? c.GetPlayerName() : "?"; }
function slotOfPawn(pawn) { try { const c = pawn.GetPlayerController(); return c ? c.GetPlayerSlot() : -1; } catch (e) { return -1; } }
function byName(name) { const a = Entities.FindByName(name); return a && a.length ? live(a[0]) : undefined; }   // first entity with the name
function fire(name, input, value, delay) { Entities.FireInput({ name, input, value, delay: delay || 0 }); }
function say(text) { Console.ServerCommand("say " + text); }
// kill / assist credit: the pawn in this slot only while it is the same player (gen, see P) on the same side; otherwise no credit
// (a slot that changed hands or a player who changed sides since the shot must not get the kill, or a team kill)
function creditOf(slot, team, gen) {
  if (!(slot >= 0)) return undefined;
  const q = players.get(slot);
  if (!q || (gen && q.gen !== gen)) return undefined;
  const pawn = pawnOf(slot);
  if (!pawn) return undefined;
  try { return pawn.GetTeamNumber() === team ? pawn : undefined; } catch (e) { return undefined; }
}
// damage dealt by the script, with the source counted when it kills (stats.killsBy: the balance report's kills by source)
function hurt(victim, cfg, src) {
  let was = false; try { was = victim.IsAlive(); } catch (e) { return; }
  try { victim.TakeDamage(cfg); } catch (e) { return; }
  let dead = false; try { dead = !victim.IsAlive(); } catch (e) {}
  if (!(was && dead)) return;
  stats.killsBy[src] = (stats.killsBy[src] || 0) + 1;
  let at = 0; try { at = cfg.attacker ? cfg.attacker.GetTeamNumber() : 0; } catch (e) {}
  const by = stats.killsByTeam[at] || (stats.killsByTeam[at] = {}); by[src] = (by[src] || 0) + 1;
}
const clock = typeof performance !== "undefined" && performance && typeof performance.now === "function" ? () => performance.now() : () => Date.now();
function vadd(a, b, k) { return v3(a.x + b.x * k, a.y + b.y * k, a.z + b.z * k); }
function vlen(a) { return Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z); }
function vnorm(a) { const l = vlen(a) || 1; return v3(a.x / l, a.y / l, a.z / l); }
function vdot(a, b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
function angOf(d) { return { pitch: -Math.asin(Math.max(-1, Math.min(1, d.z))) * 180 / Math.PI, yaw: Math.atan2(d.y, d.x) * 180 / Math.PI, roll: 0 }; }
function park(ac, e) { if (e && live(e)) { try { e.Teleport({ position: ac.void, velocity: v3(0, 0, 0) }); } catch (err) {} } }
// Source AngleVectors: forward / left / up of an entity with these angles
function angleBasis(ang) {
  const p = ang.pitch * Math.PI / 180, y = ang.yaw * Math.PI / 180, r = ang.roll * Math.PI / 180;
  const sp = Math.sin(p), cp = Math.cos(p), sy = Math.sin(y), cy = Math.cos(y), sr = Math.sin(r), cr = Math.cos(r);
  return { f: v3(cp * cy, cp * sy, -sp), l: v3(sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, sr * cp), u: v3(cr * sp * cy + sr * sy, cr * sp * sy - sr * cy, cr * cp) };
}
function dirOf(ang) {
  const p = ang.pitch * Math.PI / 180, y = ang.yaw * Math.PI / 180;
  return v3(Math.cos(p) * Math.cos(y), Math.cos(p) * Math.sin(y), -Math.sin(p));
}
const D2R = Math.PI / 180, R2D = 180 / Math.PI;
function clampN(x, a, b) { return Math.max(a, Math.min(b, x)); }
function vscale(a, k) { return v3(a.x * k, a.y * k, a.z * k); }
function wrap180(x) { return ((x + 180) % 360 + 360) % 360 - 180; }
function finiteV(a) { return !!a && Number.isFinite(a.x) && Number.isFinite(a.y) && Number.isFinite(a.z); }
function angleBetween(a, b) { return Math.acos(clampN(vdot(a, b), -1, 1)); }
// unit f toward unit d by at most maxRad (slerp; nudged off the exact opposite direction)
function rotateToward(f, d, maxRad) {
  let th = angleBetween(f, d);
  if (th < 1e-5) return d;
  if (th > 3.1) { d = vnorm(vadd(d, Math.hypot(f.x, f.y) > 1e-3 ? v3(-f.y * 0.1, f.x * 0.1, 0) : v3(0.1, 0, 0), 1)); th = angleBetween(f, d); }   // (a vertical f has no side: any)
  const t = Math.min(1, maxRad / th), s = Math.sin(th);
  return vnorm(vadd(vscale(f, Math.sin((1 - t) * th) / s), d, Math.sin(t * th) / s));
}
function clampPitch(f, limDeg) {
  const L = Math.sin(limDeg * D2R);
  if (Math.abs(f.z) <= L) return f;
  const h = Math.hypot(f.x, f.y) || 1e-6, k = Math.cos(limDeg * D2R) / h;
  return v3(f.x * k, f.y * k, Math.sign(f.z) * L);
}
// the same rotation as a, written continuous with the angles sent last tick (no +180/-180 yaw or roll jumps)
function anglesNear(a, prev) {
  if (!prev || !Number.isFinite(prev.pitch) || !Number.isFinite(prev.yaw) || !Number.isFinite(prev.roll)) return a;
  const un = (x, q) => q + wrap180(x - q);
  const p1 = un(a.pitch, prev.pitch), y1 = un(a.yaw, prev.yaw), r1 = un(a.roll, prev.roll);
  const p2 = un(180 - a.pitch, prev.pitch), y2 = un(a.yaw + 180, prev.yaw), r2 = un(a.roll + 180, prev.roll);
  const c1 = Math.abs(p1 - prev.pitch) + Math.abs(y1 - prev.yaw) + Math.abs(r1 - prev.roll);
  const c2 = Math.abs(p2 - prev.pitch) + Math.abs(y2 - prev.yaw) + Math.abs(r2 - prev.roll);
  return c2 < c1 - 1e-9 ? { pitch: p2, yaw: y2, roll: r2 } : { pitch: p1, yaw: y1, roll: r1 };
}
let peCache = null, peAt = -1;
function planeEnts() {
  const t = now();
  if (peCache && peAt === t) return peCache;
  const out = [];
  if (points) for (const team of [T, CT]) for (const a of points.aircraft[team] || []) if (live(a.ent)) out.push(a.ent);
  peCache = out; peAt = t;
  return out;
}
function groundZ(x, y) {
  const tr = Instance.TraceLine({ start: v3(x, y, 3000), end: v3(x, y, -600), ignoreEntity: planeEnts(), ignorePlayers: true });
  return tr && tr.didHit ? tr.end.z : 0;
}
