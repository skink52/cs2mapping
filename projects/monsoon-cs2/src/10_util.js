// ------------------------------------------------------------------ 10_util: vectors, angles, entities, HUD cache, pools
const T = 2, CT = 3, TEAMS = [T, CT];
const tagOf = (team) => (team === T ? "t" : "ct");
const otherTeam = (team) => (team === T ? CT : T);
const TEAM_NAME = { 2: "PAVN", 3: "US" };
const D2R = Math.PI / 180, R2D = 180 / Math.PI;
const MAPX = LAYOUT.map.x, MAPY = LAYOUT.map.y, AIRX = LAYOUT.map.air[0], AIRY = LAYOUT.map.air[1], AIRZ = LAYOUT.map.air[2];
const WATER_Z = LAYOUT.map.water_z, PARK_Z = LAYOUT.map.park_z, LOBBY_Z = LAYOUT.map.lobby_z;

let TNOW = 0;                                    // game time, read once per think
const now = () => Instance.GetGameTime();
function live(e) { try { return e && e.IsValid() ? e : undefined; } catch (err) { return undefined; } }
function v3(x, y, z) { return { x, y, z }; }
function vadd(a, b, k) { return v3(a.x + b.x * k, a.y + b.y * k, a.z + b.z * k); }
function vsub(a, b) { return v3(a.x - b.x, a.y - b.y, a.z - b.z); }
function vscale(a, k) { return v3(a.x * k, a.y * k, a.z * k); }
function vlen(a) { return Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z); }
function vnorm(a) { const l = vlen(a) || 1; return v3(a.x / l, a.y / l, a.z / l); }
function vdot(a, b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
function dist2(a, b) { const dx = a.x - b.x, dy = a.y - b.y; return Math.sqrt(dx * dx + dy * dy); }
function dist3(a, b) { const dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z; return Math.sqrt(dx * dx + dy * dy + dz * dz); }
function clampN(x, a, b) { return Math.max(a, Math.min(b, x)); }
function wrap180(x) { return ((x + 180) % 360 + 360) % 360 - 180; }
function finiteV(a) { return !!a && Number.isFinite(a.x) && Number.isFinite(a.y) && Number.isFinite(a.z); }
function gauss() { let u = 0, v = 0; while (u === 0) u = Math.random(); while (v === 0) v = Math.random(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
function pick(list) { return list[Math.floor(Math.random() * list.length)]; }
function arr3(a) { return v3(a[0], a[1], a[2]); }

// Source AngleVectors: forward / left / up of an entity with these angles (pitch + = nose down)
function angleBasis(ang) {
  const p = ang.pitch * D2R, y = ang.yaw * D2R, r = ang.roll * D2R;
  const sp = Math.sin(p), cp = Math.cos(p), sy = Math.sin(y), cy = Math.cos(y), sr = Math.sin(r), cr = Math.cos(r);
  return { f: v3(cp * cy, cp * sy, -sp), l: v3(sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, sr * cp), u: v3(cr * sp * cy + sr * sy, cr * sp * sy - sr * cy, cr * cp) };
}
// the angles whose basis is (f, l, u): the inverse of angleBasis
function anglesFromBasis(f, l, u) {
  return { pitch: -Math.asin(clampN(f.z, -1, 1)) * R2D, yaw: Math.atan2(f.y, f.x) * R2D, roll: Math.atan2(l.z, u.z) * R2D };
}
function dirOf(ang) { const p = ang.pitch * D2R, y = ang.yaw * D2R; return v3(Math.cos(p) * Math.cos(y), Math.cos(p) * Math.sin(y), -Math.sin(p)); }
function angOf(d) { return { pitch: -Math.asin(clampN(d.z, -1, 1)) * R2D, yaw: Math.atan2(d.y, d.x) * R2D, roll: 0 }; }
// B's frame turned by deg about its own up axis (model nose offsets, rotor spin)
function yawBasis(B, deg) {
  const c = Math.cos(deg * D2R), s = Math.sin(deg * D2R);
  return { f: v3(B.f.x * c + B.l.x * s, B.f.y * c + B.l.y * s, B.f.z * c + B.l.z * s), l: v3(B.l.x * c - B.f.x * s, B.l.y * c - B.f.y * s, B.l.z * c - B.f.z * s), u: B.u };
}
// ... and about its own left axis (tail rotor)
function pitchBasis(B, deg) {
  const c = Math.cos(deg * D2R), s = Math.sin(deg * D2R);
  return { f: v3(B.f.x * c - B.u.x * s, B.f.y * c - B.u.y * s, B.f.z * c - B.u.z * s), l: B.l, u: v3(B.u.x * c + B.f.x * s, B.u.y * c + B.f.y * s, B.u.z * c + B.f.z * s) };
}
function local(pos, B, off) {       // off = [forward, left, up]
  return v3(pos.x + B.f.x * off[0] + B.l.x * off[1] + B.u.x * off[2], pos.y + B.f.y * off[0] + B.l.y * off[1] + B.u.y * off[2], pos.z + B.f.z * off[0] + B.l.z * off[1] + B.u.z * off[2]);
}
function toLocal(pos, B, w) { const d = vsub(w, pos); return [vdot(d, B.f), vdot(d, B.l), vdot(d, B.u)]; }
// the same rotation as a, written continuous with the angles sent last tick (no +180/-180 jumps)
function anglesNear(a, prev) {
  if (!prev || !Number.isFinite(prev.pitch) || !Number.isFinite(prev.yaw) || !Number.isFinite(prev.roll)) return a;
  const un = (x, q) => q + wrap180(x - q);
  const p1 = un(a.pitch, prev.pitch), y1 = un(a.yaw, prev.yaw), r1 = un(a.roll, prev.roll);
  const p2 = un(180 - a.pitch, prev.pitch), y2 = un(a.yaw + 180, prev.yaw), r2 = un(a.roll + 180, prev.roll);
  const c1 = Math.abs(p1 - prev.pitch) + Math.abs(y1 - prev.yaw) + Math.abs(r1 - prev.roll);
  const c2 = Math.abs(p2 - prev.pitch) + Math.abs(y2 - prev.yaw) + Math.abs(r2 - prev.roll);
  return c2 < c1 - 1e-9 ? { pitch: p2, yaw: y2, roll: r2 } : { pitch: p1, yaw: y1, roll: r1 };
}
// a view direction held inside a cone around a centre yaw: returns clamped { pitch, yaw } (pitch + = down)
function clampAim(eye, centreYaw, cone, up, down) {
  const dy = clampN(wrap180(eye.yaw - centreYaw), -cone, cone);
  return { pitch: clampN(wrap180(eye.pitch), -up, down), yaw: centreYaw + dy, roll: 0 };
}
// distance along a ray (unit dir) at which it enters a sphere, or -1
function raySphere(s, dir, len, c, r) {
  const w = vsub(c, s), t = vdot(w, dir);
  if (t < 0 || t > len + r) return -1;
  const d2 = vdot(w, w) - t * t;
  if (d2 > r * r) return -1;
  return Math.max(0, t - Math.sqrt(r * r - d2));
}

// ------------------------------------------------------------------ console
function log(text) { Console.Log("[mv] " + text); }
let errAt = -99, errCount = 0;
function logErr(where, e) {
  errCount++;
  const t = now();
  if (t - errAt > 2) { errAt = t; log("error in " + where + ": " + e + (e && e.stack ? " " + e.stack : "")); }
}
// everything said goes through the server console: `;` would end the command and start another (a player named `x";quit;"`),
// `"` breaks the quoting, and control characters (NUL, ESC, tabs) have no business there either (review 2)
function say(text) { Console.ServerCommand("say " + String(text).replace(/[;"\x00-\x1f\x7f]/g, " ").slice(0, 200)); }
// chat lines that are not answers to a vote: queued and sent one per CHAT.SAY_GAP s (CS2 drops lines over its flood limit); a full queue
// drops the oldest, so a burst of captures never delays a later !help by a minute
const sayQueue = [];
let sayAt = 0;
function sayLater(text) { sayQueue.push(String(text)); while (sayQueue.length > CONFIG.CHAT.SAY_MAX) sayQueue.shift(); }
function tickSay() { if (sayQueue.length && TNOW >= sayAt) { sayAt = TNOW + CONFIG.CHAT.SAY_GAP; say(sayQueue.shift()); } }

// ------------------------------------------------------------------ entities (cached per round: map entities are re-created every round)
const entCache = new Map();
const missing = new Set();
function ent(name) {
  const c = entCache.get(name);
  if (c !== undefined) return c === null ? undefined : c;
  let e;
  try { const list = Entities.FindByName(name); e = list && list.length ? live(list[0]) : undefined; } catch (err) { e = undefined; }
  entCache.set(name, e || null);
  return e;
}
function need(name) {               // a CONTRACT entity: its absence is reported once
  const e = ent(name);
  if (!e && !missing.has(name)) { missing.add(name); log("missing entity " + name); }
  return e;
}
function fire(name, input, value, delay) {
  const e = ent(name); if (!e) return false;
  try { e.FireInput({ input, value, delay: delay || 0 }); return true; } catch (err) { entCache.delete(name); return false; }
}
function fireEnt(e, input, value, delay) { if (!e) return; try { e.FireInput({ input, value, delay: delay || 0 }); } catch (err) {} }
function posOf(name) { const e = need(name); return e ? e.GetAbsOrigin() : undefined; }
function poseOf(name) { const e = need(name); return e ? { pos: e.GetAbsOrigin(), ang: e.GetAbsAngles() } : undefined; }
function parkPos(i) { return v3(CONFIG.PARK_XY.x + (i || 0) * 8, CONFIG.PARK_XY.y, PARK_Z); }
function parkEnt(e, i) { if (e) { try { e.Teleport({ position: parkPos(i), velocity: v3(0, 0, 0) }); } catch (err) {} } }

// ------------------------------------------------------------------ players
function toPawn(e) {
  if (!e) return undefined;
  try { if (typeof e.GetPlayerPawn === "function") return live(e.GetPlayerPawn()); } catch (err) {}
  try { if (typeof e.GetPlayerController === "function") return live(e); } catch (err) {}
  return undefined;
}
// a human who has taken over a bot (OnBotControl, 90_main) plays the bot's pawn: that is his pawn for the script while it lives
function pawnOf(slot) {
  if (slot < 0) return undefined;
  if (botCtl.size) { const bc = botCtl.get(slot); if (bc && live(bc.pawn)) return bc.pawn; }
  const c = Instance.GetPlayerController(slot); return c ? live(c.GetPlayerPawn()) : undefined;
}
function nameOf(slot) { const c = Instance.GetPlayerController(slot); try { return c ? c.GetPlayerName() : "?"; } catch (e) { return "?"; } }
function slotOfPawn(pawn) { try { const c = pawn.GetPlayerController(); return c ? c.GetPlayerSlot() : -1; } catch (e) { return -1; } }
const KEYLIST = [CSInputs.FORWARD, CSInputs.BACK, CSInputs.LEFT, CSInputs.RIGHT, CSInputs.WALK, CSInputs.DUCK, CSInputs.JUMP, CSInputs.USE,
                 CSInputs.ATTACK, CSInputs.ATTACK2, CSInputs.RELOAD, CSInputs.LOOK_AT_WEAPON];      // F: the armory at a rack (batch G)
function keys(pawn) {               // one key per call: masked calls are unconfirmed (cs_script-notes)
  let k = 0;
  for (const b of KEYLIST) { try { if (pawn.IsInputPressed(b)) k |= b; } catch (e) {} }
  return k;
}
function eyeOf(pawn) { try { const e = pawn.GetEyeAngles(); if (e && Number.isFinite(e.pitch) && Number.isFinite(e.yaw)) return e; } catch (err) {} return { pitch: 0, yaw: 0, roll: 0 }; }
// what is dealing script damage right now ("" = CS2's own weapons): OnPlayerKill books the kill under it (stats.killsBy)
let dmgSrc = "";
// a real kill from the script (killfeed, score): let through the damage guard by p.scripted
function scriptKill(victim, attackerPawn, src) {
  const vp = players.get(slotOfPawn(victim));
  const was = dmgSrc; dmgSrc = src || was || "crash";
  if (vp) vp.scripted = true;
  try {
    victim.TakeDamage({ damage: 1000, damageTypes: CSDamageTypes.BLAST, damageFlags: CSDamageFlags.FORCE_DEATH | CSDamageFlags.IGNORE_ARMOR,
                        attacker: attackerPawn || undefined, inflictor: attackerPawn || undefined });
  } catch (e) {}
  if (vp) vp.scripted = false;
  dmgSrc = was;
}
function hurt(victim, damage, attackerPawn, types, src) {
  if (!(damage >= 1)) return;
  const was = dmgSrc; if (src) dmgSrc = src;
  try { victim.TakeDamage({ damage, damageTypes: types || CSDamageTypes.BULLET, attacker: attackerPawn || undefined, inflictor: attackerPawn || undefined }); } catch (e) {}
  dmgSrc = was;
}

// ------------------------------------------------------------------ HUD (per-player cache, only changes are sent)
// Playtest 1: the pass-1 HUD switched itself off for the whole map after 20 throws (from anyone, at any time), and calls for a client that
// had not finished loading went out and were lost while the cache believed them on screen. Now: a client is sent calls only once it is
// ready (OnPlayerActivate, or HUDRUN.READY s after the script first saw it: a listen-server host can miss the event); a call that throws
// holds that one player back for a short, doubling wait, after which his screen is reset and everything is sent again; only when several
// players fail together (the layout itself is broken) does everyone wait. Nothing is ever switched off for good.
let hudEnt;
let hudFails = 0, hudBackoff = 0, hudRetryAt = 0;
const hudRecent = [];                            // [slot, time] of recent failures
function hud() {
  if (TNOW < hudRetryAt) return undefined;
  if (live(hudEnt)) return hudEnt;
  entCache.delete(CONFIG.HUD);                   // never trust a cached layout entity that is no longer valid (a round restart re-creates it)
  hudEnt = /** @type {any} */ (ent(CONFIG.HUD));
  if (!hudEnt) entCache.delete(CONFIG.HUD);
  return hudEnt;
}
function hudReady(p) { return !p.bot && TNOW >= p.hudBlockUntil && (p.hudReady || (p.seenAt > 0 && TNOW - p.seenAt >= CONFIG.HUDRUN.READY)); }
// the layout for calls to p now, or undefined; a player held back after a failure gets his screen reset (and his cache emptied) first
function hudFor(p) {
  if (!hudReady(p)) return undefined;
  const h = hud(); if (!h) return undefined;
  if (p.hudDirty) { p.hudDirty = false; p.hud.clear(); try { h.ResetForPlayer(p.slot); } catch (e) {} }
  return h;
}
function hudFailed(p, e) {
  const R = CONFIG.HUDRUN;
  hudFails++; p.hudErr++;
  p.hudBlockUntil = TNOW + Math.min(R.BACKOFF_MAX, R.BACKOFF * Math.pow(2, Math.min(6, p.hudErr - 1))); p.hudDirty = true; p.hud.clear();
  if (!live(hudEnt)) { hudEnt = undefined; entCache.delete(CONFIG.HUD); }
  hudRecent.push([p.slot, TNOW]);
  while (hudRecent.length && TNOW - hudRecent[0][1] > 2) hudRecent.shift();
  if (new Set(hudRecent.map((x) => x[0])).size >= 3) {            // several players at once: the layout, not a client
    hudBackoff = Math.min(R.BACKOFF_MAX, hudBackoff ? hudBackoff * 2 : R.BACKOFF); hudRetryAt = TNOW + hudBackoff; hudRecent.length = 0;
    hudEnt = undefined; entCache.delete(CONFIG.HUD);
    for (const q of players.values()) { q.hudDirty = true; q.hud.clear(); }
  }
  if (hudFails <= 5 || hudFails % 100 === 0) log("HUD call refused for slot " + p.slot + " (" + hudFails + " so far): " + e + " - that screen is sent again in " + (p.hudBlockUntil - TNOW).toFixed(0) + " s");
}
function hudOk(p) { p.hudErr = 0; hudBackoff = 0; }
// ids added after the HUD was generated ("HUD additions" in docs/SCRIPT.md) are only used when out/hud.json lists them
const HUD_IDS = Array.isArray(HUDDATA.ids) ? new Set(HUDDATA.ids) : null;
function hudHas(id) { return !!HUD_IDS && HUD_IDS.has(id); }
let hudCalls = 0;
// the cache is one record per panel id ({ t: text, c: { class: on }, s: { group: class } }): a lookup builds no key string, which was
// the largest single cost of the script at 64 players (a no-op hClass ran about a thousand times a tick)
function hudRec(p, id) { let r = p.hud.get(id); if (!r) { r = { t: undefined, c: Object.create(null), s: Object.create(null) }; p.hud.set(id, r); } return r; }
function hText(p, id, text) {
  if (p.bot) return;
  text = String(text === undefined || text === null ? "" : text);
  if (hudRec(p, id).t === text) return;
  const h = hudFor(p); if (!h) return;
  const r = hudRec(p, id);                       // (hudFor may have reset this screen and its cache)
  try { h.SetDialogVariableStringForPlayer(p.slot, id, "v", text); hudCalls++; } catch (e) { hudFailed(p, e); return; }
  if (p.hudErr) hudOk(p);
  r.t = text;
}
function hClass(p, id, cls, on) {
  if (p.bot) return;
  on = !!on;
  let old = hudRec(p, id).c[cls];
  if (old === on || (old === undefined && !on)) return;
  const h = hudFor(p); if (!h) return;
  const r = hudRec(p, id); old = r.c[cls];
  if (old === on || (old === undefined && !on)) return;
  try { h.SetHasClassForPlayer(p.slot, id, cls, on); hudCalls++; } catch (e) { hudFailed(p, e); return; }
  if (p.hudErr) hudOk(p);
  r.c[cls] = on;
}
function hSwap(p, id, group, cls) {   // one class per group (marker positions, needles)
  if (p.bot) return;
  if (hudRec(p, id).s[group] === cls) return;
  const h = hudFor(p); if (!h) return;
  const r = hudRec(p, id), old = r.s[group];
  if (old === cls) return;
  try {
    if (old) { h.SetHasClassForPlayer(p.slot, id, old, false); hudCalls++; }
    if (cls) { h.SetHasClassForPlayer(p.slot, id, cls, true); hudCalls++; }
  } catch (e) { hudFailed(p, e); return; }
  if (p.hudErr) hudOk(p);
  r.s[group] = cls;
}
// the texts are gone after a reset, so the timers that keep a toast / banner / card up go too (a round restart left them running:
// the new round opened with an empty banner and toast box on screen, review 2)
// (a screen that cannot take calls yet is reset as soon as it can: hudFor does it first)
function hudReset(p) {
  if (!p.bot) { const h = hudFor(p); if (h) { try { h.ResetForPlayer(p.slot); } catch (e) {} } else p.hudDirty = true; }
  p.hud.clear(); p.toastUntil = 0; p.bannerUntil = 0; p.infoUntil = 0;
}
function toast(p, text, secs) { if (!p || p.bot) return; hText(p, "mv_toast_text", text); p.toastUntil = TNOW + (secs || 3); }
// the event feed (flag taken, helicopter down, gun silenced): the newest line on top, each for FEED.TIME seconds.
// team = who reads it (0 = everyone); tone "good" / "bad" / "" as that reader sees it. Without the feed panels (HUD additions,
// docs/SCRIPT.md) the lines marked fallback go to the toast instead and the rest are dropped.
const feedLines = [];
function feed(team, text, tone, fallback) {
  stats.feed++;
  if (!hudHas("mv_feed_1")) { if (fallback) { for (const p of players.values()) if (!p.bot && (!team || p.team === team)) toast(p, text, 4); } return; }
  feedLines.unshift({ team, text, tone: tone || "", until: TNOW + CONFIG.FEED.TIME });
  if (feedLines.length > 12) feedLines.length = 12;
}
function drawFeed(p) {
  if (!hudHas("mv_feed_1")) return;
  let n = 0;
  for (const f of feedLines) {
    if (n >= CONFIG.FEED.LINES) break;
    if (TNOW >= f.until || (f.team && f.team !== p.team)) continue;
    n++;
    hText(p, "mv_feed_" + n, f.text); hSwap(p, "mv_feed_" + n, "tone", f.tone ? "feed_" + f.tone : ""); hClass(p, "mv_feed_" + n, "show", true);
  }
  for (n++; n <= CONFIG.FEED.LINES; n++) hClass(p, "mv_feed_" + n, "show", false);
}
function toastSlot(slot, text, secs) { const p = players.get(slot); if (p) toast(p, text, secs); }
function toastTeam(team, text, secs) { for (const p of players.values()) if (p.team === team && !p.bot) toast(p, text, secs); }
function info(p, title, lines, foot, secs) {
  if (p.bot) return;
  hText(p, "mv_info_title", title);
  for (let k = 0; k < 5; k++) hText(p, "mv_info_l" + (k + 1), lines[k] || "");
  hText(p, "mv_info_foot", foot || "");
  p.infoUntil = TNOW + (secs || 10);
}
function banner(p, title, sub, secs) { if (p.bot) return; hText(p, "mv_banner_title", title); hText(p, "mv_banner_sub", sub); p.bannerUntil = TNOW + (secs || 5); }

// ------------------------------------------------------------------ world queries
let hitIgnore = [];                              // every helicopter, rotor and wreck prop: world traces look through them
// optional height samples in layout.json: LAYOUT.terrain = { x0, y0, cell, nx, ny, z: [row-major, y then x] }
const TERRAIN = LAYOUT.terrain && Array.isArray(LAYOUT.terrain.z) ? LAYOUT.terrain : null;
// a safe guess of the ground height without a trace (AI altitude planning): samples if the layout has them, else plateaus + karst
function approxGround(x, y) {
  let z = 0;
  if (TERRAIN) {
    const i = clampN(Math.round((x - TERRAIN.x0) / TERRAIN.cell), 0, TERRAIN.nx - 1), j = clampN(Math.round((y - TERRAIN.y0) / TERRAIN.cell), 0, TERRAIN.ny - 1);
    const s = TERRAIN.z[j * TERRAIN.nx + i];
    if (Number.isFinite(s)) z = s;
  } else {
    z = 60 + Math.max(0, Math.abs(y) - 1800) * 0.16;                       // valley floor rising to the slopes
    for (const tg of ["t", "ct"]) { const b = LAYOUT[tg]; const d = Math.hypot(x - b.centre[0], y - b.centre[1]); if (d < 1500) z = Math.max(z, b.z * clampN((1500 - d) / 600, 0, 1)); }
  }
  for (const k of LAYOUT.karst) if (Math.hypot(x - k.x, y - k.y) < k.r + 260) z = Math.max(z, k.top);
  return z;
}
function groundZ(x, y, top) {
  const z0 = top !== undefined ? top : AIRZ + 300;
  const tr = Instance.TraceLine({ start: v3(x, y, z0), end: v3(x, y, WATER_Z - 300), ignoreEntity: hitIgnore, ignorePlayers: true });
  return tr && tr.didHit ? tr.end.z : approxGround(x, y);
}
function inBand(o, margin) { return Math.abs(o.x) < MAPX - margin && Math.abs(o.y) < MAPY - margin; }
function gridRef(x, y) {
  const E = BOARD_EXT, u = clampN((x + E) / (2 * E), 0, 0.9999), v = clampN((E - y) / (2 * E), 0, 0.9999);
  return String.fromCharCode(65 + Math.floor(u * 16)) + (1 + Math.floor(v * 16));
}

// ------------------------------------------------------------------ effect pools
const pool = { boom: 0, tracer: 0, rocket: 0, shell: 0, smoke: 0 };
function effects(pos, quiet) {
  const i = (pool.boom++ % CONFIG.POOL.BOOM) + 1;
  for (const nm of ["mv_boom_fx_", "mv_dirt_fx_", "mv_boom_snd_", "mv_shake_"]) { const e = need(nm + i); if (e) { try { e.Teleport({ position: pos }); } catch (err) {} } }
  fire("mv_boom_fx_" + i, "Stop"); fire("mv_boom_fx_" + i, "Start", undefined, 0.02);
  fire("mv_dirt_fx_" + i, "Stop"); fire("mv_dirt_fx_" + i, "Start", undefined, 0.02);
  fire("mv_boom_snd_" + i, "StartSound", undefined, 0.02);
  if (!quiet) fire("mv_shake_" + i, "StartShake", undefined, 0.02);
}
function puff(pos) {                             // dirt only (disabled gun smouldering, rocket motor)
  const i = (pool.boom++ % CONFIG.POOL.BOOM) + 1;
  const e = need("mv_dirt_fx_" + i); if (!e) return;
  try { e.Teleport({ position: pos }); } catch (err) {}
  fire("mv_dirt_fx_" + i, "Stop"); fire("mv_dirt_fx_" + i, "Start", undefined, 0.02);
}
const tracers = [];
function tracer(start, dir, len) {
  const i = (pool.tracer++ % CONFIG.POOL.TRACER) + 1;
  const e = need("mv_tracer_" + i); if (!e) return;
  for (let k = tracers.length - 1; k >= 0; k--) if (tracers[k].ent === e) tracers.splice(k, 1);
  tracers.push({ ent: e, i, pos: start, dir, left: len, ang: angOf(dir), first: true });
}
function tickTracers(dt) {
  for (let i = tracers.length - 1; i >= 0; i--) {
    const r = tracers[i];
    const step = Math.min(r.left, CONFIG.HELI.TRACER_SPEED * dt);
    r.pos = vadd(r.pos, r.dir, step); r.left -= step;
    if (r.left <= 0) { parkEnt(r.ent, r.i); tracers.splice(i, 1); continue; }
    try { if (r.first) { r.ent.Teleport({ position: r.pos, angles: r.ang }); r.first = false; } else r.ent.Move({ position: r.pos, angles: r.ang }); } catch (e) { tracers.splice(i, 1); }
  }
}
// smoke screens (WP shells): hitscan and observation are blocked through them
const smokes = [];
function smokeBlocks(a, b) { return smokeAt(a, b) >= 0; }
// distance from a at which the line a -> b enters a smoke screen, or -1
function smokeAt(a, b) {
  if (!smokes.length) return -1;
  const d = vsub(b, a), L = vlen(d); if (L < 1) return -1;
  const dir = vscale(d, 1 / L);
  let best = -1;
  for (const s of smokes) { const t = raySphere(a, dir, L, s.pos, CONFIG.ARTY.SMOKE_RADIUS); if (t >= 0 && (best < 0 || t < best)) best = t; }
  return best;
}
function tickSmokes() {
  for (let i = smokes.length - 1; i >= 0; i--) if (TNOW >= smokes[i].until) { fire("mv_smoke_fx_" + smokes[i].i, "Stop"); smokes.splice(i, 1); }
}
// one hitscan round: world / player trace, helicopter spheres, smoke. Returns the distance it travelled. src = the stats source name.
function hitscan(start, dir, range, shooterPawn, team, dmgInf, dmgHeli, ignore, src) {
  const end = vadd(start, dir, range);
  let tr; try { tr = Instance.TraceLine({ start, end, ignoreEntity: ignore, traceHitboxes: true }); } catch (e) { tr = undefined; }
  let d = tr && tr.didHit ? tr.fraction * range : range;
  let heli;
  for (const h of allHelis) {
    if (h.team === team || h.state === "dead") continue;
    const hd = raySphere(start, dir, d, heliCentre(h), CONFIG.HELI.HIT_RADIUS);
    if (hd >= 0 && hd < d) { d = hd; heli = h; }
  }
  const sd = smokeAt(start, vadd(start, dir, d));
  if (sd >= 0) { stats.smokeBlocked++; return Math.max(60, sd + 40); }       // the round is lost in the smoke: nothing behind it is hit
  if (heli) { damageHeli(heli, dmgHeli, slotOfPawn(shooterPawn), src); return d; }
  if (tr && tr.didHit && tr.hitEntity) {
    const h2 = heliOfEntity(tr.hitEntity);
    if (h2) { if (h2.team !== team) damageHeli(h2, dmgHeli, slotOfPawn(shooterPawn), src); return d; }
    const hp = toPawn(tr.hitEntity);
    if (hp && hp.IsAlive() && hp.GetTeamNumber() !== team) hurt(hp, dmgInf, shooterPawn, CSDamageTypes.BULLET, src);
  }
  return d;
}
