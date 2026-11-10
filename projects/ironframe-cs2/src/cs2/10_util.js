// ===================================================================================================================
// IRONFRAME CS2 adapter, part 1: small helpers. Engine calls that CS2 renamed in Oct 2026 (Msg -> Console.Log,
// ServerCommand -> Console, FindEntityByName -> Entities.FindByName, EntFireAtTarget -> ent.FireInput) go through one
// wrapper each, so the migration is a one-line change here when the old names are removed.
// ===================================================================================================================
const IFR_VERSION = (typeof VERSION === 'object' && VERSION && VERSION.version) || '0.0.0';
let ifrTickTime = 0, ifrInThink = false, ifrTickNo = 0;
function gameTime() { return ifrInThink ? ifrTickTime : Instance.GetGameTime(); }

function log(msg) { Instance.Msg('[' + CONFIG.TAG + '] ' + msg); }
function dlog(msg) { if (CONFIG.DEBUG) log(msg); }
const ifrWarned = new Set();
function warnOnce(key, msg) { if (ifrWarned.has(key)) return; ifrWarned.add(key); log('WARNING: ' + msg); }

function live(e) { try { return e && e.IsValid() ? e : undefined; } catch (err) { return undefined; } }

// run fn; an exception is said once per kind and never stops the script
let ifrErrors = 0;
function guard(what, fn) {
  try { return fn(); } catch (err) {
    ifrErrors++;
    const k = what + ':' + String(err);
    if (!ifrWarned.has(k)) { ifrWarned.add(k); log('error in ' + what + ': ' + err + (err && err.stack ? '\n' + err.stack : '')); }
    return undefined;
  }
}

function ifrCmd(line) { Instance.ServerCommand(line); }
function ifrCvars(list) { if (!CONFIG.APPLY_CVARS) return; for (const c of list) guard('cvar ' + c, () => ifrCmd(c)); }
function ifrFind(name) { try { return live(Instance.FindEntityByName(name)); } catch (err) { return undefined; } }
function ifrFindAll(name) { try { return (Instance.FindEntitiesByName(name) || []).filter((e) => live(e)); } catch (err) { return []; } }
function ifrFire(ent, input, value) { Instance.EntFireAtTarget({ target: ent, input, value }); }
function ifrFireName(name, input, value) { Instance.EntFireAtName({ name, input, value }); }

function slotOfEntity(e) {
  if (!e) return undefined;
  try {
    const x = /** @type {any} */ (e);
    if (typeof x.GetPlayerController === 'function') { const c = x.GetPlayerController(); return c ? c.GetPlayerSlot() : undefined; }
    if (typeof x.GetPlayerSlot === 'function') return x.GetPlayerSlot();
  } catch (err) { /* ignore */ }
  return undefined;
}
function controllerOf(slot) { try { return Instance.GetPlayerController(slot); } catch (err) { return undefined; } }
function pawnOf(slot) { const c = controllerOf(slot); if (!c) return undefined; try { return live(c.GetPlayerPawn()); } catch (err) { return undefined; } }
// a player's name; a script AI mech (no controller) by its mech name ("AI-3"), never "slot 64"
function nameOf(slot) {
  if (typeof srvCallsign === 'function') { const cs = srvCallsign(slot); if (cs) return cs; }      // the pilot's callsign, when one is set (70_server.js)
  let c; try { c = controllerOf(slot); if (c) return String(c.GetPlayerName()).slice(0, 24); } catch (err) { /* below */ }
  try { const m = typeof game === 'object' && game && game.mechs ? game.mechs.get(slot) : null; if (m && m.name && !/^slot \d+$/.test(m.name)) return String(m.name).slice(0, 24); } catch (err) { /* below */ }
  return slot >= 64 ? 'AI-' + (slot - 63) : 'slot ' + slot;
}

// ---- vectors and angles (Source: x forward, y left, z up; yaw grows anticlockwise seen from above; pitch + is down)
const D2R = Math.PI / 180, R2D = 180 / Math.PI;
const ZERO = { x: 0, y: 0, z: 0 }, ZERO_ANG = { pitch: 0, yaw: 0, roll: 0 };
function v3(x, y, z) { return { x, y, z }; }
function vadd(a, b) { return { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z }; }
function vsub(a, b) { return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z }; }
function vmul(a, k) { return { x: a.x * k, y: a.y * k, z: a.z * k }; }
function vlen(a) { return Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z); }
function vdist(a, b) { const dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z; return Math.sqrt(dx * dx + dy * dy + dz * dz); }
function vnorm(a) { const l = vlen(a); return l > 1e-6 ? vmul(a, 1 / l) : v3(1, 0, 0); }
function vfinite(a) { return a && Number.isFinite(a.x) && Number.isFinite(a.y) && Number.isFinite(a.z); }
function normAngle(a) { a = a % 360; if (a > 180) a -= 360; if (a < -180) a += 360; return a; }
function angleDiff(a, b) { return normAngle(b - a); }
// forward vector of yaw/pitch (degrees)
function fwdOf(yaw, pitch) { const cp = Math.cos(pitch * D2R); return v3(Math.cos(yaw * D2R) * cp, Math.sin(yaw * D2R) * cp, -Math.sin(pitch * D2R)); }
function rightOf(yaw) { return v3(Math.sin(yaw * D2R), -Math.cos(yaw * D2R), 0); }
// a point given in a frame's local axes (x fwd, y left, z up) turned by yaw (and pitch) into the world
function localToWorld(origin, yaw, pitch, l) {
  const f = fwdOf(yaw, pitch || 0), r = rightOf(yaw);
  const u = v3(-Math.sin(yaw * D2R) * 0 + Math.cos(yaw * D2R) * Math.sin((pitch || 0) * D2R), Math.sin(yaw * D2R) * Math.sin((pitch || 0) * D2R), Math.cos((pitch || 0) * D2R));
  return v3(origin.x + f.x * l[0] - r.x * l[1] + u.x * l[2], origin.y + f.y * l[0] - r.y * l[1] + u.y * l[2], origin.z + f.z * l[0] - r.z * l[1] + u.z * l[2]);
}
function clampWorld(p) {
  return v3(Math.max(-16000, Math.min(16000, p.x)), Math.max(-16000, Math.min(16000, p.y)), Math.max(-16000, Math.min(16000, p.z)));
}

// chat as the host is rate limited by CS2: queue and send SAY_GAP apart
const ifrSayQueue = []; let ifrSayNext = 0;
function sayAll(text) { ifrSayQueue.push('say ' + String(text).replace(/[;"]/g, '')); }
function flushSays() { const now = gameTime(); if (!ifrSayQueue.length || now < ifrSayNext) return; ifrCmd(ifrSayQueue.shift()); ifrSayNext = now + CONFIG.SAY_GAP; }

// deterministic rng for the core (seeded from game time at init; replaced by the mock's Math.random when seeded)
function ifrMakeRng(seed) {
  let s = (seed >>> 0) || 1;
  return () => { s += 0x6D2B79F5; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
