// ---------------------------------------------------------------- small helpers
// the game time of the current server tick (read once per think; it doesn't change within a tick)
let tickTime = 0, tickNo = 0, inThink = false;
function now() { return inThink ? tickTime : Instance.GetGameTime(); }
// warmup / freeze time, read once per tick
let warmTick = -1, warmVal = false, frzTick = -1, frzVal = false;
function isWarmup() { if (warmTick !== tickNo || !inThink) { warmVal = Instance.IsWarmupPeriod(); warmTick = inThink ? tickNo : -1; } return warmVal; }
function isFrozen() { if (frzTick !== tickNo || !inThink) { frzVal = Instance.IsFreezePeriod(); frzTick = inThink ? tickNo : -1; } return frzVal; }

function log(msg) { Instance.Msg('[cs16] ' + msg); }
function dlog(msg) { if (CONFIG.DEBUG) log(msg); }
const warned = new Set();
function warnOnce(key, msg) { if (warned.has(key)) return; warned.add(key); log('WARNING: ' + msg); }

function live(e) {
  try { return e && e.IsValid() ? e : undefined; } catch (err) { return undefined; }
}
// runs fn; an error is logged once per place and kind instead of stopping the script
function guard(what, fn) {
  try { return fn(); } catch (err) {
    const k = what + ':' + String(err);
    if (!warned.has(k)) { warned.add(k); log('error in ' + what + ': ' + err + (err && err.stack ? '\n' + err.stack : '')); }
    return undefined;
  }
}

function controllerOf(slot) { try { return Instance.GetPlayerController(slot); } catch (err) { return undefined; } }
function pawnOf(slot) {
  const c = controllerOf(slot);
  if (!c) return undefined;
  try { return live(c.GetPlayerPawn()); } catch (err) { return undefined; }
}
// a pawn or controller -> its player slot
function slotOf(e) {
  if (!e) return undefined;
  try {
    const x = /** @type {any} */ (e);
    if (typeof x.GetPlayerController === 'function') {
      // (a dead pawn may have no current controller: then the one it was spawned for)
      const c = x.GetPlayerController() || (typeof x.GetOriginalPlayerController === 'function' ? x.GetOriginalPlayerController() : undefined);
      return c ? c.GetPlayerSlot() : undefined;
    }
    if (typeof x.GetPlayerSlot === 'function') return x.GetPlayerSlot();
  } catch (err) { /* ignore */ }
  return undefined;
}
function isPawn(e) { return !!e && typeof (/** @type {any} */ (e)).GetPlayerController === 'function' && typeof (/** @type {any} */ (e)).GetArmor === 'function'; }

function dist3(a, b) { const dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z; return Math.sqrt(dx * dx + dy * dy + dz * dz); }
function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }
function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

// chat lines go out one at a time (CS2 drops chat sent too fast); only for things everyone should read
const sayQueue = [];
let sayNext = 0;
function sayAll(text) { if (CONFIG.CHAT) sayQueue.push('say ' + String(text).replace(/[;"]/g, '')); }
function flushSays() {
  if (!sayQueue.length || now() < sayNext) return;
  Instance.ServerCommand(sayQueue.shift());
  sayNext = now() + CONFIG.SAY_GAP;
}

// the converted maps (tools/convert_map.py writes them to _gen/maps.json; the build bakes them in as MAPS_JSON)
const MAPS = MAPS_JSON.maps;
const MAP_BY_KEY = {};
for (const m of MAPS) MAP_BY_KEY[m.key] = m;
// which map a world position is in (by the maps' bounding boxes, a little padded)
function mapAt(p) {
  for (const m of MAPS) {
    const [lo, hi] = m.bounds;
    if (p.x >= lo[0] - 64 && p.x <= hi[0] + 64 && p.y >= lo[1] - 64 && p.y <= hi[1] + 64 && p.z >= lo[2] - 256 && p.z <= hi[2] + 256) return m.key;
  }
  return undefined;
}
function inBox(p, lo, hi, pad) {
  return p.x >= lo[0] - pad && p.x <= hi[0] + pad && p.y >= lo[1] - pad && p.y <= hi[1] + pad && p.z >= lo[2] - pad - 72 && p.z <= hi[2] + pad;
}
// 1.6 buy zones: func_buyzone boxes, or (maps without any) 200 units around the team's spawn points
function inBuyZone(mapKey, team, p) {
  const m = MAP_BY_KEY[mapKey];
  if (!m) return false;
  for (const z of m.buyzones) if (z.team === team && inBox(p, z.mins, z.maxs, 0)) return true;
  for (const s of m.buyspots) {
    if (s.team !== team) continue;
    const r2 = s.radius * s.radius;
    for (const q of s.points) {
      const dx = p.x - q[0], dy = p.y - q[1], dz = p.z - q[2];
      if (dx * dx + dy * dy + dz * dz <= r2) return true;
    }
  }
  return false;
}
function inBombSite(mapKey, p) {
  const m = MAP_BY_KEY[mapKey];
  if (!m) return false;
  for (const s of m.sites) if (inBox(p, s.mins, s.maxs, 0)) return true;
  return false;
}
