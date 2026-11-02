// =====================================================================================
//  CS2 ADAPTER - entities, players, camera, HUD, sounds, lifecycle
// =====================================================================================

const TAG = "[puppet_brawl]";
const ZERO = { x: 0, y: 0, z: 0 };
const SOUND_IDS = ["hit", "heavy", "block", "whiff", "kd", "special", "ko", "bell", "tick", "select", "win"];
// CS2 buttons -> game buttons. Each key is tested on its own: IsInputPressed with a
// combined mask means "all of these at once".
const INPUT_MAP = [
  [CSInputs.LEFT, IN.LEFT], [CSInputs.RIGHT, IN.RIGHT],
  [CSInputs.FORWARD, IN.UP], [CSInputs.JUMP, IN.UP],
  [CSInputs.BACK, IN.DOWN], [CSInputs.DUCK, IN.DOWN],
  [CSInputs.ATTACK, IN.PUNCH], [CSInputs.ATTACK2, IN.KICK],
  [CSInputs.WALK, IN.BLOCK], [CSInputs.RELOAD, IN.SPECIAL],
  [CSInputs.LOOK_AT_WEAPON, IN.THROW],
];

let debugOn = CONFIG.DEBUG;
let game = null;
let stage = null;
let ready = false;
let retryAt = 0;
let lastTime = 0;
let acc = 0;
let tickCount = 0;
let errorCount = 0;
let projSlots = [];
let sparkSlots = [];
/** @type {Record<string, any[]>} */
let pool = { ball: [] };
/** @type {Record<string, any[]>} */
let bodyPool = {};
/** @type {any[]} */
let seatBody = [null, null, null, null];
/** @type {Record<string, import("cs_script/point_script").Entity | undefined>} */
let templates = {};
let pads = [null, null, null, null];
let watchSpots = [];
/** @type {import("cs_script/point_script").Entity | undefined | null} */
let exitEnt = null;
/** @type {import("cs_script/point_script").Entity | undefined | null} */
let camEnt = null;
/** @type {import("cs_script/point_script").CustomHudLayout | null} */
let hud = null;
/** @type {Map<number, {seat: number, pawn: import("cs_script/point_script").CSPlayerPawn, watch: boolean, pad: any, useSince: number, useArmed: boolean, held: number, pressed: number, since: number, weapons: string[] | null}>} */
const players = new Map();     // player slot -> seat info
const reentry = new Map();     // player slot -> game time
const camHeld = new Map();     // player slot -> { parent }
const hudCache = new Map();
const hudPlayerCache = new Map();
const hudWidths = new Map();
const soundOk = new Set();
const warned = new Set();      // never cleared: a missing entity is reported once, not every retry
let playedThisTick = new Set();
let hudFailures = 0;

function log(text) { Instance.Msg(`${TAG} ${text}`); }
function dlog(text) { if (debugOn) log(text); }
function warnOnce(key, text) { if (!warned.has(key)) { warned.add(key); log("WARNING: " + text); } }
// Registers an Instance callback only if this CS2 build has it, so one renamed or missing
// hook can't stop the rest of the script from setting up.
/** @param {string} name @param {...any} args */
function hook(name, ...args) {
  const fn = /** @type {any} */ (Instance)[name];
  if (typeof fn === "function") fn.apply(Instance, args);
  else warnOnce("hook:" + name, `this CS2 build has no Instance.${name} - skipping it`);
}
/** @template T @param {T} e @returns {T | undefined} */
function live(e) { return e && typeof /** @type {any} */ (e).IsValid === "function" && /** @type {any} */ (e).IsValid() ? e : undefined; }
/** @param {string} name @returns {import("cs_script/point_script").Entity | undefined} */
function findNamed(name) {
  if (!name) return undefined;
  const exact = live(Instance.FindEntityByName(name));
  if (exact) return exact;
  const cap = name.charAt(0).toUpperCase() + name.slice(1);
  return cap !== name ? live(Instance.FindEntityByName(cap)) : undefined;
}
function copyV(v) { return { x: v.x, y: v.y, z: v.z }; }
function dist2d(a, b) { return Math.hypot(a.x - b.x, a.y - b.y); }
function safeText(s) { return String(s).replace(/[^A-Za-z0-9 _\-.,!?:()#+\[\]']/g, "").slice(0, 120); }
/** @param {import("cs_script/point_script").Entity} e @param {{position?: any, angles?: any, velocity?: any}} values */
function move(e, values) { if (typeof e.Move === "function") e.Move(values); else e.Teleport(values); }

// ------------------------------------------------------------------ stage
function discoverStage() {
  const S = CONFIG.WORLD_SCALE;
  const L = findNamed(CONFIG.STAGE_LEFT), Rt = findNamed(CONFIG.STAGE_RIGHT);
  let origin, R, half;
  if (L && Rt) {
    const a = L.GetAbsOrigin(), b = Rt.GetAbsOrigin();
    origin = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, z: (a.z + b.z) / 2 };
    const rx = b.x - a.x, ry = b.y - a.y, len = Math.hypot(rx, ry);
    if (len < 200) { warnOnce("stage-short", `${CONFIG.STAGE_LEFT} and ${CONFIG.STAGE_RIGHT} are only ${Math.round(len)} units apart - make the stage at least ~600 wide`); if (len < 64) return null; }
    R = { x: rx / len, y: ry / len, z: 0 };
    half = len / 2;
  } else {
    const C = findNamed(CONFIG.STAGE_CENTER);
    if (!C) return null;
    origin = copyV(C.GetAbsOrigin());
    const yaw = C.GetAbsAngles().yaw * DEG;
    const D = { x: Math.cos(yaw), y: Math.sin(yaw) };
    R = { x: -D.y, y: D.x, z: 0 };
    half = CONFIG.STAGE_WIDTH / 2;
  }
  let D = { x: R.y, y: -R.x, z: 0 };
  const cam = findNamed(CONFIG.CAMERA_ENTITY);
  if (cam) {
    const c = cam.GetAbsOrigin();
    if ((c.x - origin.x) * D.x + (c.y - origin.y) * D.y < 0) {   // markers were swapped
      R = { x: -R.x, y: -R.y, z: 0 }; D = { x: -D.x, y: -D.y, z: 0 };
    }
  }
  return { origin, R, D, yaw: Math.atan2(R.y, R.x) / DEG, half, scale: S, halfFU: half / S };
}

function toWorld(x, y, depth, depthScale = CONFIG.DEPTH_SCALE) {
  const s = stage.scale, o = stage.origin, R = stage.R, D = stage.D;
  const dx = x * s, dz = y * s, dd = depth * s * depthScale;
  return { x: o.x + R.x * dx + D.x * dd, y: o.y + R.y * dx + D.y * dd, z: o.z + dz };
}
function parkPos() {
  const o = stage ? stage.origin : ZERO;
  return { x: o.x, y: o.y, z: o.z - CONFIG.PARK_DROP };
}

// ------------------------------------------------------------------ spawning
/** @param {string} tplName @returns {import("cs_script/point_script").Entity[]} */
function spawnFrom(tplName) {
  let tpl = live(templates[tplName]);
  if (!tpl) { tpl = findNamed(tplName); templates[tplName] = tpl; }
  if (!(tpl instanceof PointTemplate)) { warnOnce("tpl:" + tplName, `no point_template named ${tplName}`); return []; }
  return (tpl.ForceSpawn(parkPos(), { pitch: 0, yaw: 0, roll: 0 }) || []).filter((e) => live(e));
}
/** @param {import("cs_script/point_script").Entity} e */
function kill(e) { try { e.Remove(); } catch (err) { /* ignore */ } }

// ------------------------------------------------------------------ props for projectiles and effects
// A slot is one on-screen prop. Its model comes from a point_template (pb_tpl_ball, or
// pb_tpl_<key> for the effect props) and goes back to a per-model pool when the slot changes model.
/** @typedef {{ent: import("cs_script/point_script").BaseModelEntity | null, key: string, px: number, py: number, pz: number, ang: number, scale: number, color: number, parked: boolean, glow: boolean, rnd: number}} BallSlot */
/** @returns {BallSlot} */
function makeSlot() { return { ent: null, key: "", px: NaN, py: NaN, pz: NaN, ang: NaN, scale: NaN, color: -1, parked: true, glow: false, rnd: 0 }; }
const fxMissing = new Set();
/** @param {string} key @returns {import("cs_script/point_script").BaseModelEntity | undefined} */
function takeProp(key) {
  const list = key === "ball" ? pool.ball : (pool[key] || (pool[key] = []));
  while (list.length) { const e = list.pop(); if (live(e)) return e; }
  if (fxMissing.has(key)) return undefined;
  const tpl = key === "ball" ? CONFIG.TEMPLATES.ball : CONFIG.TEMPLATES.fx + key;
  if (key !== "ball" && !findNamed(tpl)) { fxMissing.add(key); return undefined; }
  /** @type {import("cs_script/point_script").BaseModelEntity | undefined} */
  let keep;
  for (const e of spawnFrom(tpl)) { if (!keep && e instanceof BaseModelEntity) keep = e; else kill(e); }
  if (keep) { try { keep.SetEntityName("pb_part"); } catch (err) { /* ignore */ } }
  else { warnOnce("tplprop:" + key, `${tpl} spawned no prop_dynamic`); if (key !== "ball") fxMissing.add(key); }
  return keep;
}
function takeBall() { return takeProp("ball"); }
/** Can this effect prop be shown? (its template is in the map) @param {string} key */
function hasProp(key) {
  if (!CONFIG.FX) return false;
  if (fxMissing.has(key)) return false;
  if ((pool[key] && pool[key].length) || findNamed(CONFIG.TEMPLATES.fx + key)) return true;
  fxMissing.add(key); return false;
}
/** @param {BallSlot} slot */
function parkSlot(slot) {
  const e = live(slot.ent);
  if (!e || slot.parked) return;
  e.Teleport({ position: parkPos(), velocity: ZERO });
  e.SetModelScale(0.01); slot.scale = 0.01;
  if (slot.glow) { try { e.Unglow(); } catch (err) { /* ignore */ } slot.glow = false; }
  slot.parked = true;
}
/** Points the slot at a model, swapping props through the pools. @param {BallSlot} slot @param {string} key */
function slotModel(slot, key) {
  if (slot.ent && slot.key === key && live(slot.ent)) return slot.ent;
  if (live(slot.ent)) {
    parkSlot(slot);
    const list = slot.key === "ball" ? pool.ball : (pool[slot.key] || (pool[slot.key] = []));
    list.push(/** @type {any} */ (slot.ent));
  }
  slot.ent = takeProp(key) || null; slot.key = key;
  slot.parked = true; slot.color = -1; slot.scale = NaN; slot.glow = false; slot.ang = NaN;
  return slot.ent;
}
/** @param {BallSlot} slot @param {{x: number, y: number, z: number}} pos @param {number} scale @param {{r: number, g: number, b: number}} c @param {boolean} glow @param {{pitch: number, yaw: number, roll: number} | null} [ang] */
function placeSlot(slot, pos, scale, c, glow, ang) {
  const e = /** @type {import("cs_script/point_script").BaseModelEntity} */ (slot.ent);
  const moved = Math.abs(pos.x - slot.px) + Math.abs(pos.y - slot.py) + Math.abs(pos.z - slot.pz);
  const ak = ang ? Math.round(ang.pitch * 4) * 1e6 + Math.round(ang.yaw * 4) * 1e3 + Math.round(ang.roll * 4) : 0;
  const turned = ang && ak !== slot.ang;
  if (slot.parked || !(moved < 90)) e.Teleport(ang ? { position: pos, angles: ang, velocity: ZERO } : { position: pos, velocity: ZERO });
  else if (moved > 0.03 || turned) move(e, ang ? { position: pos, angles: ang } : { position: pos });
  slot.px = pos.x; slot.py = pos.y; slot.pz = pos.z; slot.parked = false; slot.ang = ak;
  scale = Math.max(0.01, scale);
  if (!(Math.abs(scale - slot.scale) <= slot.scale * 0.004)) { e.SetModelScale(scale); slot.scale = scale; }
  const ck = (c.r << 16) | (c.g << 8) | c.b;
  if (ck !== slot.color) { e.SetColor({ r: c.r, g: c.g, b: c.b, a: 255 }); slot.color = ck; }
  if (glow && !slot.glow) { try { e.Glow(c); slot.glow = true; } catch (err) { /* ignore */ } }
}
/** @param {BallSlot} slot @param {number} x @param {number} y @param {number} r @param {number} depth @param {{r: number, g: number, b: number}} c @param {boolean} glow */
function applyBall(slot, x, y, r, depth, c, glow) {
  if (!slotModel(slot, "ball")) return;
  placeSlot(slot, toWorld(x, y, depth), (r * stage.scale) / MODEL_BALL_R, c, glow, null);
}
/** @param {{r: number, g: number, b: number}} c @param {number} k */
function dim(c, k) { return { r: Math.round(c.r * k), g: Math.round(c.g * k), b: Math.round(c.b * k) }; }

// ------------------------------------------------------------------ effects for the crowd
// Projectiles get their own model (a knot of wood, a brass cog, a juggling ball) spinning in the
// fight plane with a fading trail. Hits flash a star, big moments send a shockwave ring along the
// floor or across the air, and stock CS2 particles go off on specials, KOs and knockdowns.
const PROJ_MODEL = { timber: "proj_knot", brass: "proj_cog", motley: "proj_jball" };
const SPECIAL_PARTICLE = { timber: "embers", brass: "streak", pirouette: "zap", motley: "confetti" };
const POP_PARTICLE = { timber: "embers", brass: "arc", motley: "confetti" };
const TRAIL = 3;          // trail orbs behind each projectile
const TRAIL_GAP = 2;      // ticks between trail orbs
const RING_POOL = 8;
const PARTICLE_CAP = 14;
let trailSlots = [];      // [seat][i]
let projHist = [];        // [seat] -> recent {x, y}
/** @type {{slot: BallSlot, life: number, max: number, x: number, y: number, depth: number, r0: number, r1: number, color: {r: number, g: number, b: number}, flat: boolean}[]} */
let rings = [];
/** @type {{ents: any[], stopAt: number, killAt: number, stopped: boolean}[]} */
let particles = [];
const particleCD = new Map();
let stageMain = "", stageSub = "", stageSubUntil = 0, stageMainShown = "", stageSubShown = "";

function resetFx() {
  trailSlots = [0, 1, 2, 3].map(() => Array.from({ length: TRAIL }, makeSlot));
  projHist = [[], [], [], []];
  rings = Array.from({ length: RING_POOL }, () => ({ slot: makeSlot(), life: 0, max: 1, x: 0, y: 0, depth: 0, r0: 0, r1: 0, color: { r: 255, g: 255, b: 255 }, flat: true }));
  for (const p of particles) for (const e of p.ents) kill(e);
  particles = [];
  particleCD.clear();
  fxMissing.clear();
  stageMain = stageSub = stageMainShown = stageSubShown = ""; stageSubUntil = 0;
}

/** @param {number} x @param {number} y @param {number} r0 @param {number} r1 @param {{r: number, g: number, b: number}} color @param {number} ticks @param {boolean} flat */
function ring(x, y, r0, r1, color, ticks, flat) {
  if (!hasProp("fx_ring")) return;
  let R = rings.find((q) => q.life <= 0);
  if (!R) R = rings.reduce((a, b) => (a.life < b.life ? a : b));
  Object.assign(R, { life: ticks, max: ticks, x, y, depth: flat ? 0 : 10, r0, r1, color, flat });
  R.slot.parked = true;
}
/** @param {string} key @param {number} x @param {number} y @param {number} depth @param {number} seconds @param {number} [dir] @param {number} [cooldown] */
function particle(key, x, y, depth, seconds, dir = 1, cooldown = 0) {
  if (!CONFIG.FX || !CONFIG.FX_PARTICLES || fxMissing.has("fx_" + key)) return;
  const now = Instance.GetGameTime();
  if (cooldown && (particleCD.get(key) || 0) > now) return;
  if (particles.length >= PARTICLE_CAP) return;
  const name = CONFIG.TEMPLATES.fx + "fx_" + key;
  let tpl = live(templates[name]);
  if (!tpl) { tpl = findNamed(name); templates[name] = tpl; }
  if (!(tpl instanceof PointTemplate)) { fxMissing.add("fx_" + key); return; }
  particleCD.set(key, now + cooldown);
  const pos = toWorld(x, y, depth);
  const angles = { pitch: 0, yaw: stage.yaw + (dir < 0 ? 180 : 0), roll: 0 };
  const ents = (tpl.ForceSpawn(pos, angles) || []).filter((e) => live(e));
  for (const e of ents) {
    try { e.SetEntityName("pb_part"); e.Teleport({ position: pos, angles }); } catch (err) { /* ignore */ }
  }
  if (ents.length) particles.push({ ents, stopAt: now + seconds, killAt: now + seconds + 2.5, stopped: false });
}
function updateParticles() {
  if (!particles.length) return;
  const now = Instance.GetGameTime();
  particles = particles.filter((p) => {
    if (!p.stopped && now >= p.stopAt) {
      p.stopped = true;
      for (const e of p.ents) if (live(e)) { try { Instance.EntFireAtTarget({ target: e, input: "Stop" }); } catch (err) { /* ignore */ } }
    }
    if (now >= p.killAt) { for (const e of p.ents) kill(e); return false; }
    return true;
  });
}
/** @param {string} name @param {string} text */
function setStageText(name, text) {
  try { Instance.EntFireAtName({ name, input: "SetMessage", value: text || " " }); } catch (err) { /* ignore */ }
}
function updateStageText() {
  if (!CONFIG.FX) return;
  const A = game.hud.announce;
  const main = A.show && A.text ? safeText(A.text).toUpperCase() : "";
  if (main !== stageMainShown) { stageMainShown = main; setStageText(CONFIG.STAGE_TEXT, main); }
  const now = Instance.GetGameTime();
  const sub = now < stageSubUntil ? stageSub : "";
  if (sub !== stageSubShown) { stageSubShown = sub; setStageText(CONFIG.STAGE_SUB, sub); }
}
/** @param {string} text @param {number} seconds */
function stageCall(text, seconds) { stageSub = safeText(text).toUpperCase(); stageSubUntil = Instance.GetGameTime() + seconds; }

const WHITE = { r: 255, g: 255, b: 255 };
/** @param {any} e */
function onFx(e) {
  if (!CONFIG.FX || !stage) return;
  const f = typeof e.seat === "number" ? game.fighters[e.seat] : null;
  switch (e.fx) {
    case "special": {
      if (!f) break;
      const c = e.color || WHITE;
      if (e.combo) { ring(e.x, 0, 10, 46, c, 12, true); break; }
      ring(e.x, 0, 12, 90, c, 18, true);
      ring(e.x, 50, 8, 40, mix(c, WHITE, 0.5), 10, false);
      particle(SPECIAL_PARTICLE[e.ch] || "zap", e.x, 50, 6, e.ch === "timber" ? 0.9 : 0.6, f.facing);
      stageCall(game.displayName(e.seat) + "  -  " + e.name, 1.6);
      break;
    }
    case "hit":
      if (e.ko) {
        ring(e.dx, 0, 16, 150, WHITE, 26, true);
        ring(e.x, e.y, 10, 70, e.color || WHITE, 16, false);
        particle("firework", e.dx, 60, 8, 1.2, e.dir);
        particle("sparks", e.x, e.y, 10, 0.3, e.dir);
      } else if (e.heavy || e.special) {
        particle("sparks", e.x, e.y, 10, 0.3, e.dir, 0.08);
        if (e.special) ring(e.x, e.y, 6, 34, mix(e.color || WHITE, WHITE, 0.4), 9, false);
      }
      break;
    case "block":
      if (e.perfect) {
        ring(e.x, e.y, 6, 44, { r: 140, g: 230, b: 255 }, 11, false);
        particle("zap", e.x, e.y, 10, 0.4, -e.dir, 0.2);
        stageCall("PERFECT BLOCK  -  " + game.displayName(e.seat), 1.3);
      }
      break;
    case "dust":
      particle("dust", e.x, 2, 4, 0.5, 1, e.small ? 0.15 : 0);
      if (!e.small) ring(e.x, 0, 10, e.ko ? 80 : 52, { r: 150, g: 140, b: 130 }, 14, true);
      break;
    case "pop":
      if (POP_PARTICLE[e.kind]) particle(POP_PARTICLE[e.kind], e.x, e.y, 6, 0.35, 1, 0.1);
      ring(e.x, e.y, 6, 30, e.color || WHITE, 8, false);
      break;
    case "tag":
      ring(e.x, 0, 14, 110, e.color || WHITE, 20, true);
      particle("streak", e.x, 60, 6, 0.6, 1);
      stageCall("TAG IN  -  " + game.displayName(e.seat), 1.4);
      break;
    case "win": {
      const w = Math.max(80, game.halfW * 0.6);
      particle("firework", -w, 90, -20, 1.5, 1);
      particle("firework", w, 90, -20, 1.5, -1);
      particle("confetti", 0, 130, 0, 1.0, 1);
      break;
    }
  }
}

/** @param {number} seat */
function renderProjectile(seat) {
  const f = game.fighters[seat];
  const pr = f.projectile && game.projectiles.includes(f.projectile) ? f.projectile : null;
  const slot = projSlots[seat], trail = trailSlots[seat], hist = projHist[seat];
  if (!pr) {
    if (slot.ent) parkSlot(slot);
    for (const t of trail) if (t.ent) parkSlot(t);
    hist.length = 0;
    return;
  }
  const key = PROJ_MODEL[pr.kind];
  if (key && hasProp(key) && slotModel(slot, key)) {
    // spin in the fight plane: pitch turns the model about the axis pointing at the audience
    const spin = ((pr.spin * (pr.vx >= 0 ? 1 : -1)) % 360 + 360) % 360;
    placeSlot(slot, toWorld(pr.x, pr.y, 0), (pr.r * stage.scale) / MODEL_BALL_R, WHITE, false, { pitch: spin, yaw: stage.yaw, roll: 0 });
  } else applyBall(slot, pr.x, pr.y, pr.r, 0, pr.color, true);
  hist.unshift({ x: pr.x, y: pr.y });
  if (hist.length > TRAIL * TRAIL_GAP + 1) hist.length = TRAIL * TRAIL_GAP + 1;
  if (!hasProp("fx_orb")) return;
  for (let i = 0; i < TRAIL; i++) {
    const h = hist[(i + 1) * TRAIL_GAP];
    const t = trail[i];
    if (!h) { if (t.ent) parkSlot(t); continue; }
    if (!slotModel(t, "fx_orb")) continue;
    const k = 1 - (i + 1) / (TRAIL + 1);
    placeSlot(t, toWorld(h.x, h.y, -1), (pr.r * (0.35 + 0.55 * k) * stage.scale) / MODEL_BALL_R, dim(pr.color, 0.25 + 0.6 * k), false, null);
  }
}

function renderRings() {
  for (const R of rings) {
    if (R.life <= 0) { if (R.slot.ent && !R.slot.parked) parkSlot(R.slot); continue; }
    const k = 1 - R.life / R.max;            // 0 -> 1 over the ring's life
    const ease = 1 - (1 - k) * (1 - k);
    const r = R.r0 + (R.r1 - R.r0) * ease;
    if (!slotModel(R.slot, "fx_ring")) { R.life = 0; continue; }
    const ang = R.flat ? { pitch: 0, yaw: stage.yaw, roll: 0 } : { pitch: 0, yaw: stage.yaw, roll: 90 };
    placeSlot(R.slot, toWorld(R.x, R.flat ? 0.6 : R.y, R.depth), (r * stage.scale) / 8, dim(R.color, Math.max(0.05, 1 - k)), false, ang);
    R.life--;
  }
}

// ------------------------------------------------------------------ fighter bodies
// A body is the invisible animation rig (models/puppet_brawl/rig/pb_rig.vmdl, which holds
// every move as an animation) with a CS2 agent model bone-merged onto it. Each fighter has
// its own point_template (pb_tpl_<id>) holding both props; the agent is parented to the rig
// with "!bonemerge". Bodies are pooled per fighter, so changing fighter in the lobby swaps
// bodies instead of re-spawning.
/** @typedef {{rig: any, agent: any, id: string, name: string, clip: string, key: string, rate: number, x: number, y: number, z: number, yaw: number, scale: number, tint: number, glow: number, parked: boolean}} Body */
let bodySerial = 0;
/** @param {string} id @returns {Body | null} */
function spawnBody(id) {
  const ents = spawnFrom(CONFIG.TEMPLATES.body + id);
  if (!ents.length) return null;
  let rig = null, agent = null;
  for (const e of ents) {
    const em = /** @type {any} */ (e);
    const m = typeof em.GetModelName === "function" ? String(em.GetModelName()) : "";
    if (!rig && m.includes("pb_rig")) rig = e; else if (!agent && e instanceof BaseModelEntity && !m.includes("pb_rig")) agent = e; else kill(e);
  }
  if (!rig || !agent) {
    warnOnce("body:" + id, `${CONFIG.TEMPLATES.body + id} must hold the rig prop (pb_rig.vmdl) and one agent prop`);
    for (const e of [rig, agent]) if (e) kill(e);
    return null;
  }
  const name = "pb_rig_" + (++bodySerial);
  try { rig.SetEntityName(name); agent.SetEntityName("pb_agent"); } catch (err) { /* ignore */ }
  // the template parents the agent with !bonemerge; if that link didn't survive, make it now
  try { if (agent.GetParent() !== rig) Instance.EntFireAtTarget({ target: agent, input: "FollowEntity", value: name }); } catch (err) { /* ignore */ }
  return { rig, agent, id, name, clip: "", key: "", rate: NaN, x: NaN, y: NaN, z: NaN, yaw: NaN, scale: NaN, tint: -1, glow: -1, parked: true };
}
/** @param {string} id */
function takeBody(id) {
  const list = bodyPool[id] || (bodyPool[id] = []);
  while (list.length) { const b = list.pop(); if (b && live(b.rig) && live(b.agent)) return b; }
  return spawnBody(id);
}
/** @param {Body} b */
function parkBody(b) {
  if (b.parked || !live(b.rig)) return;
  b.rig.Teleport({ position: parkPos(), velocity: ZERO });
  b.parked = true; b.x = NaN;
}
/** @param {Body} b @param {string} input @param {string | number} value */
function fire(b, input, value) { try { Instance.EntFireAtTarget({ target: b.rig, input, value }); } catch (err) { /* ignore */ } }

const TINTS = [{ r: 255, g: 255, b: 255 }, { r: 255, g: 150, b: 150 }, { r: 150, g: 185, b: 255 }, { r: 160, g: 255, b: 165 }];
// Same fighter twice on stage: later seats get a colour wash so they can be told apart.
function tintFor(seat) {
  const f = game.fighters[seat];
  let n = 0;
  for (let i = 0; i < seat; i++) { const o = game.fighters[i]; if (o.onStage && game.seats[i].kind && o.ch.id === f.ch.id) n++; }
  return n ? TINTS[Math.min(TINTS.length - 1, seat === 0 ? 0 : n + (seat % 3))] : TINTS[0];
}

/** @param {number} seat */
function renderFighter(seat) {
  const f = game.fighters[seat];
  let b = seatBody[seat];
  const want = f.onStage && game.seats[seat].kind ? f.ch.id : null;
  if (b && b.id !== want) { parkBody(b); (bodyPool[b.id] || (bodyPool[b.id] = [])).push(b); b = seatBody[seat] = null; }
  if (!want) return;
  if (!b) { b = seatBody[seat] = takeBody(want); if (!b) return; }
  if (!live(b.rig) || !live(b.agent)) { seatBody[seat] = null; return; }
  // vanishing moves (Pratfall) hide the body for a moment
  if (f.pose[P_SC] < 0.3) { parkBody(b); return; }
  const thrown = f.state === "thrown" && f.throwPelvis;
  const x = thrown ? f.throwPelvis.x : f.x + f.shakeX;
  const y = thrown ? f.throwPelvis.y : f.y;
  const pos = toWorld(x, y, f.background ? CONFIG.QUEUE_DEPTH : f.depthBase * CONFIG.FIGHTER_DEPTH);
  const yaw = stage.yaw + (f.facing > 0 ? 0 : 180) + (CONFIG.BODY_YAW || 0);
  const moved = Math.abs(pos.x - b.x) + Math.abs(pos.y - b.y) + Math.abs(pos.z - b.z);
  if (b.parked || !(moved < 90) || b.yaw !== yaw) b.rig.Teleport({ position: pos, angles: { pitch: 0, yaw, roll: 0 }, velocity: ZERO });
  else if (moved > 0.02) move(b.rig, { position: pos, angles: { pitch: 0, yaw, roll: 0 } });
  b.x = pos.x; b.y = pos.y; b.z = pos.z; b.yaw = yaw; b.parked = false;
  const scale = (stage.scale / SKELETON_UNITS) * f.ch.scale;
  if (!(Math.abs(scale - b.scale) < 0.001)) { b.rig.SetModelScale(scale); b.scale = scale; }
  // animation: start the clip when it (or its restart key) changes, then steer the speed
  const a = f.animState();
  if (a.clip !== b.clip || a.key !== b.key) {
    fire(b, RIG_CLIPS[a.clip] && RIG_CLIPS[a.clip].loop ? "SetAnimationLooping" : "SetAnimationNotLooping", a.clip);
    b.clip = a.clip; b.key = a.key; b.rate = NaN;
  }
  let rate = a.rate;
  if (f.hitstop > 0 && f.active) rate = 0;
  else if (game.slowmo > 0) rate /= 3;
  rate = Math.round(rate * 50) / 50;
  if (rate !== b.rate) { fire(b, "SetPlaybackRate", rate); b.rate = rate; }
  const t = tintFor(seat), tk = (t.r << 16) | (t.g << 8) | t.b;
  if (tk !== b.tint) { try { b.agent.SetColor({ r: t.r, g: t.g, b: t.b, a: 255 }); } catch (err) { /* ignore */ } b.tint = tk; }
  // team outlines in 2v2 (optional)
  const g = CONFIG.TEAM_GLOW && game.mode === "teams" && game.inMatch() ? (f.team === 0 ? 0xff4040 : 0x4080ff) : 0;
  if (g !== b.glow) {
    try { if (g) b.agent.Glow({ r: g >> 16, g: (g >> 8) & 255, b: g & 255 }); else b.agent.Unglow(); } catch (err) { /* ignore */ }
    b.glow = g;
  }
}

function renderAll() {
  for (let seat = 0; seat < 4; seat++) {
    renderFighter(seat);
    renderProjectile(seat);
  }
  const star = hasProp("fx_burst");
  for (let i = 0; i < game.sparks.length; i++) {
    const s = game.sparks[i], slot = sparkSlots[i];
    if (s.life > 0) {
      const k = 1 - s.life / s.max;
      if (s.life === s.max) { slot.parked = true; slot.rnd = (slot.rnd + 137) % 360; }
      if (star && slotModel(slot, "fx_burst")) {
        // hit flash: a star that pops out, turns a little and fades
        const pos = toWorld(s.x, s.y, 14);
        placeSlot(slot, pos, (s.size * (0.5 + 1.1 * k) * stage.scale) / MODEL_BALL_R, dim(s.color, 1 - 0.75 * k), false,
          { pitch: slot.rnd + k * 40, yaw: stage.yaw, roll: 0 });
      } else applyBall(slot, s.x, s.y, s.size * (0.35 + 0.75 * k), 14, s.color, false);
    } else if (slot.ent) parkSlot(slot);
  }
  renderRings();
  updateParticles();
  updateStageText();
}

// Everything this script spawned is named pb_part, pb_agent or pb_rig_<n>.
function removeSpawned() {
  for (const n of ["pb_part", "pb_agent"]) for (const e of Instance.FindEntitiesByName(n)) kill(e);
  for (const e of Instance.FindEntitiesByClass("prop_dynamic")) {
    let n = "";
    try { n = e.GetEntityName(); } catch (err) { /* ignore */ }
    if (n.startsWith("pb_rig_")) kill(e);
  }
  pool = { ball: [] };
  for (const p of particles) for (const e of p.ents) kill(e);
  particles = [];
  for (const t of trailSlots) for (const q of t) q.ent = null;
  for (const R of rings) { R.slot.ent = null; R.life = 0; }
  bodyPool = {};
  seatBody = [null, null, null, null];
  for (const s of projSlots) { s.ent = null; }
  for (const s of sparkSlots) { s.ent = null; }
}

// ------------------------------------------------------------------ camera
/** @param {import("cs_script/point_script").CSPlayerPawn | undefined} pawn */
function cameraFor(pawn) {
  if (!pawn || typeof pawn.GetCustomCamera !== "function") return undefined;
  try { return live(pawn.GetCustomCamera()); } catch (err) { return undefined; }
}

function cameraTransform() {
  if (CONFIG.CAMERA_MODE === "fixed") {
    camEnt = live(camEnt) || findNamed(CONFIG.CAMERA_ENTITY);
    if (camEnt) return { position: copyV(camEnt.GetAbsOrigin()), angles: camEnt.GetAbsAngles() };
  }
  const cam = game.cam;
  const hfov = 2 * Math.atan(Math.tan(CONFIG.CAMERA_FOV * DEG / 2) * CONFIG.CAMERA_ASPECT / (4 / 3));
  const dist = Math.max(CONFIG.CAMERA_MIN_DIST, cam.half / Math.tan(hfov / 2));
  const look = toWorld(cam.cx, CONFIG.CAMERA_LOOK_HEIGHT, 0, 1);
  const pos = toWorld(cam.cx, CONFIG.CAMERA_HEIGHT, dist, 1);
  if (cam.shake > 0) {
    const a = cam.shake * stage.scale * 0.5;
    pos.x += (Math.random() - 0.5) * a; pos.y += (Math.random() - 0.5) * a; pos.z += (Math.random() - 0.5) * a;
  }
  const dx = look.x - pos.x, dy = look.y - pos.y, dz = look.z - pos.z;
  return { position: pos, angles: { pitch: -Math.atan2(dz, Math.hypot(dx, dy)) / DEG, yaw: Math.atan2(dy, dx) / DEG, roll: 0 } };
}

/** @param {number} slot @param {import("cs_script/point_script").CSPlayerPawn} pawn */
function takeCamera(slot, pawn) {
  if (CONFIG.CAMERA_MODE === "off") return;
  if (typeof pawn.GetCustomCamera !== "function") { warnOnce("cam", "this CS2 build has no GetCustomCamera - players keep their own view"); return; }
  const cam = cameraFor(pawn);
  if (!cam) return;
  camHeld.set(slot, { parent: cam.GetParent() });
  if (CONFIG.CAMERA_UNPARENT) cam.SetParent(undefined);
  const t = cameraTransform();
  cam.Teleport({ position: t.position, angles: t.angles });
  cam.SetMode(CustomCameraMode.CONTROLLED);
  try { pawn.SetEyeAngles({ pitch: t.angles.pitch, yaw: t.angles.yaw, roll: 0 }); } catch (err) { /* ignore */ }
}

function giveBackCamera(slot) {
  const held = camHeld.get(slot);
  if (!held) return;
  camHeld.delete(slot);
  const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
  const cam = live(pawn) ? cameraFor(pawn) : undefined;
  if (!cam) return;
  cam.SetMode(CustomCameraMode.DISABLED);
  if (CONFIG.CAMERA_UNPARENT && held.parent && live(held.parent)) cam.SetParent(held.parent);
}

function updateCameras() {
  if (!camHeld.size) return;
  const t = cameraTransform();
  for (const slot of camHeld.keys()) {
    const pawn = Instance.GetPlayerController(slot)?.GetPlayerPawn();
    const cam = live(pawn) ? cameraFor(pawn) : undefined;
    if (cam) move(cam, { position: t.position, angles: t.angles });
  }
}

// ------------------------------------------------------------------ HUD
// custom_hud_layout is recognised by its methods (see the import note in the header).
/** @param {any} e @returns {boolean} */
function isHudLayout(e) {
  return !!e && typeof e.SetDialogVariableString === "function" && typeof e.SetHasClass === "function" &&
    typeof e.SetDialogVariableStringForPlayer === "function" && typeof e.SetHasClassForPlayer === "function";
}
/** @returns {import("cs_script/point_script").CustomHudLayout | undefined} */
function hudEnt() {
  if (hudFailures >= 5) return undefined;
  if (!live(hud)) { const e = findNamed(CONFIG.HUD); hud = isHudLayout(e) ? /** @type {any} */ (e) : null; }
  return live(hud) || undefined;
}
// The HUD API is marked experimental. If its calls keep throwing, the fight carries on
// without a HUD instead of stalling joins or start-up.
/** @param {string} what @param {() => void} fn */
function hudGuard(what, fn) {
  if (hudFailures >= 5) return;
  try { fn(); }
  catch (err) {
    hudFailures++;
    warnOnce("hud:" + what, `HUD ${what} failed: ${err}`);
    if (hudFailures >= 5) warnOnce("hudoff", "the HUD keeps failing - carrying on without it");
  }
}
function hudVar(id, value) {
  const h = hudEnt(); if (!h) return;
  if (hudCache.get("v:" + id) === value) return;
  hudCache.set("v:" + id, value);
  h.SetDialogVariableString(id, "t", value);
}
function hudClass(id, cls, on) {
  const h = hudEnt(); if (!h) return;
  const key = "c:" + id + "." + cls;
  if (hudCache.get(key) === on) return;
  hudCache.set(key, on);
  h.SetHasClass(id, cls, on);
}
function hudWidth(id, w) {
  const h = hudEnt(); if (!h) return;
  const last = hudWidths.has(id) ? hudWidths.get(id) : 100;
  if (last === w) return;
  h.SetHasClass(id, "w" + last, false);
  h.SetHasClass(id, "w" + w, true);
  hudWidths.set(id, w);
}
function hudVarP(slot, id, value) {
  const h = hudEnt(); if (!h) return;
  const key = slot + "v:" + id;
  if (hudPlayerCache.get(key) === value) return;
  hudPlayerCache.set(key, value);
  h.SetDialogVariableStringForPlayer(slot, id, "t", value);
}
function hudClassP(slot, id, cls, on) {
  const h = hudEnt(); if (!h) return;
  const key = slot + "c:" + id + "." + cls;
  if (hudPlayerCache.get(key) === on) return;
  hudPlayerCache.set(key, on);
  h.SetHasClassForPlayer(slot, id, cls, on);
}
function hudForget(slot) {
  for (const k of [...hudPlayerCache.keys()]) if (k.startsWith(slot + "v:") || k.startsWith(slot + "c:")) hudPlayerCache.delete(k);
}
function hudShowFor(slot, on) {
  const h = hudEnt(); if (!h) return;
  if (on) hudClassP(slot, "pb_game", "Hidden", false);
  else { try { h.ResetForPlayer(slot); } catch (err) { /* ignore */ } hudForget(slot); }
}

// Every label shows "{s:t}" until its variable is set, so blank them all up front.
const HUD_LABELS = ["pb_joinhint_text", "pb_timer", "pb_queue", "pb_announce", "pb_lobby_mode", "pb_lobby_count", "pb_lobby_hint",
  "pb_me", "pb_moves", "pb_motions", "pb_status", "pb_footer",
  ...[1, 2, 3, 4].flatMap((n) => ["pb_c" + n + "_name", "pb_c" + n + "_fighter", "pb_c" + n + "_combo", "pb_c" + n + "_best", "pb_lobby_s" + n])];
function hudInitDefaults() {
  const h = hudEnt(); if (!h) return;
  for (const id of HUD_LABELS) { h.SetDialogVariableString(id, "t", ""); hudCache.set("v:" + id, ""); }
}

const ANN_STYLES = ["big", "fight", "ko", "win", "sub", "small"];
function updateHud() {
  if (!hudEnt()) return;
  const H = game.hud;
  hudClass("pb_game", "InLobby", H.inLobby);
  hudClass("pb_game", "InMatch", H.inMatch);
  for (const m of MODES) hudClass("pb_game", "Mode_" + m, game.mode === m);
  const cs = game.cardSeats();
  for (let i = 0; i < 4; i++) {
    const c = H.cards[i], id = "pb_c" + (i + 1);
    hudClass(id, "Show", c.show);
    if (!c.show) continue;
    hudVar(id + "_name", c.name);
    hudVar(id + "_fighter", c.fighter);
    hudVar(id + "_combo", c.combo);
    hudClass(id, "HasCombo", !!c.combo);
    hudClass(id, "Perfect", c.comboKind === "perfect");
    hudVar(id + "_best", c.best);
    hudClass(id, "HasBest", !!c.best);
    hudWidth(id + "_fill", c.hp);
    hudWidth(id + "_chip", c.hp);
    hudClass(id, "Low", c.hp <= 25);
    hudClass(id, "KO", c.ko);
    hudClass(id, "Bench", !!c.bench);
    for (let k = 0; k < 6; k++) hudClass(id, "Col" + k, c.color === k);
    for (let p = 1; p <= 3; p++) hudClass(id + "_pip" + p, "Won", c.wins >= p);
    hudClass(id, "Need3", c.need >= 3);
  }
  hudVar("pb_timer", H.timer);
  hudClass("pb_timer", "Low", H.timer !== "" && +H.timer <= 10);
  hudVar("pb_queue", H.queue);
  const A = H.announce;
  hudVar("pb_announce", A.text);
  for (const st of ANN_STYLES) hudClass("pb_announce", "St_" + st, A.style === st);
  hudClass("pb_announce", "Show", A.show && !!A.text);
  const L = H.lobby;
  hudVar("pb_lobby_mode", L.mode);
  for (let i = 0; i < 4; i++) {
    const s = game.seats[i], id = "pb_lobby_s" + (i + 1);
    hudVar(id, L.lines[i]);
    hudClass(id, "Taken", !!s.kind);
    hudClass(id, "Ready", !!s.kind && s.ready);
  }
  hudVar("pb_lobby_count", L.count);
  hudVar("pb_lobby_hint", L.hint);
  hudVar("pb_footer", H.footer);
  for (const [slot, p] of players) {
    if (p.watch) {
      hudVarP(slot, "pb_me", "WATCHING - press E to stop");
      hudVarP(slot, "pb_moves", ""); hudVarP(slot, "pb_motions", ""); hudVarP(slot, "pb_status", "");
      continue;
    }
    const info = H.seat[p.seat];
    hudVarP(slot, "pb_me", info.me);
    hudVarP(slot, "pb_moves", info.moves);
    hudVarP(slot, "pb_motions", info.motions);
    hudVarP(slot, "pb_status", info.status);
    hudClassP(slot, "pb_game", "Picking", !!info.status);
    for (let i = 0; i < 4; i++) hudClassP(slot, "pb_c" + (i + 1), "Me", cs[i] === p.seat);
    for (let i = 0; i < 4; i++) hudClassP(slot, "pb_lobby_s" + (i + 1), "Me", i === p.seat);
  }
}

function updateJoinHints() {
  const h = hudEnt(); if (!h) return;
  for (const ctrl of Instance.GetAllPlayerControllers()) {
    if (!ctrl || !ctrl.IsConnected() || ctrl.IsBot()) continue;
    const slot = ctrl.GetPlayerSlot();
    let text = "";
    if (!players.has(slot)) {
      const pawn = ctrl.GetPlayerPawn();
      if (live(pawn) && pawn.IsAlive()) {
        const o = pawn.GetAbsOrigin();
        for (let i = 0; i < 4 && !text; i++) {
          const pad = pads[i];
          if (!pad || dist2d(o, pad) >= CONFIG.PAD_RADIUS * 1.5 || Math.abs(o.z - pad.z) >= 80) continue;
          if (!game.seats[i].kind) text = "PRESS E TO PLAY  -  PAD " + (i + 1);
          else if (game.canTakeOver(i)) text = "PRESS E TO TAKE OVER FROM THE CPU  -  PAD " + (i + 1);
        }
        for (const w of watchSpots) if (!text && dist2d(o, w) < CONFIG.PAD_RADIUS * 1.5 && Math.abs(o.z - w.z) < 80) text = "PRESS E TO WATCH THE FIGHT";
      }
    }
    hudVarP(slot, "pb_joinhint_text", text);
    hudClassP(slot, "pb_joinhint", "Show", !!text);
  }
}

// ------------------------------------------------------------------ sounds / chat
function handleEvents() {
  for (const e of game.events) {
    if (e.t === "snd") {
      if (!soundOk.has(e.id) || playedThisTick.has(e.id)) continue;
      playedThisTick.add(e.id);
      Instance.EntFireAtName({ name: CONFIG.SOUND_PREFIX + e.id, input: "StartSound" });
    } else if (e.t === "fx") {
      onFx(e);
    } else if (e.t === "say" && CONFIG.ANNOUNCE_IN_CHAT) {
      Instance.ServerCommand("say " + safeText(e.text));
    }
  }
  game.events.length = 0;
}

// ------------------------------------------------------------------ players
/** @param {import("cs_script/point_script").CSWeaponBase} w */
function isKnife(w) { try { return w.GetData().GetType() === CSWeaponType.KNIFE; } catch (err) { return false; } }
/** @param {import("cs_script/point_script").CSPlayerPawn} pawn */
function holdKnife(pawn) {
  const a = pawn.GetActiveWeapon();
  if (a && isKnife(a)) return;
  const k = pawn.FindWeaponBySlot(CSGearSlot.KNIFE);
  if (k) pawn.SwitchToWeapon(k);
}
/** @param {import("cs_script/point_script").CSPlayerPawn} pawn @param {any} p */
function armForPlay(pawn, p) {
  if (CONFIG.WEAPONS === "knife") holdKnife(pawn);
  else if (CONFIG.WEAPONS === "strip") {
    p.weapons = [];
    for (const s of [CSGearSlot.RIFLE, CSGearSlot.PISTOL, CSGearSlot.KNIFE, CSGearSlot.GRENADES, CSGearSlot.C4]) {
      const w = pawn.FindWeaponBySlot(s);
      if (w) p.weapons.push(w.GetClassName());
    }
    pawn.DestroyWeapons();
  }
}
/** @param {import("cs_script/point_script").CSPlayerPawn} pawn @param {any} p */
function restoreWeapons(pawn, p) {
  if (CONFIG.WEAPONS !== "strip" || !p.weapons) return;
  for (const cls of p.weapons) {
    const name = /knife|bayonet/.test(cls) ? "weapon_knife" : cls;
    try { pawn.GiveNamedItem(name, false); } catch (err) { /* ignore */ }
  }
  p.weapons = null;
}
/** @param {import("cs_script/point_script").CSPlayerPawn} pawn @param {any} at */
function holdPlayer(pawn, at) {
  if (at) pawn.Teleport({ position: copyV(at), velocity: ZERO });
  if (CONFIG.FREEZE_PLAYERS) pawn.SetMoveType(CSMoveType.NONE);
}
/** @param {import("cs_script/point_script").CSPlayerPawn | undefined} pawn @param {any} p @param {boolean} teleport */
function releasePawn(pawn, p, teleport) {
  if (!live(pawn) || !pawn.IsAlive()) return;
  if (CONFIG.FREEZE_PLAYERS) pawn.SetMoveType(CSMoveType.WALK);   // unfreeze before any teleport
  restoreWeapons(pawn, p);
  if (teleport) {
    exitEnt = live(exitEnt) || findNamed(CONFIG.EXIT);
    if (exitEnt) pawn.Teleport({ position: copyV(exitEnt.GetAbsOrigin()), angles: { pitch: 0, yaw: exitEnt.GetAbsAngles().yaw, roll: 0 }, velocity: ZERO });
  }
}

/** @param {number} slot @param {import("cs_script/point_script").CSPlayerController} ctrl @param {import("cs_script/point_script").CSPlayerPawn} pawn @param {number} seat @param {any} at */
function seatPlayer(slot, ctrl, pawn, seat, at) {
  const name = ctrl.GetPlayerName();
  const ok = game.seats[seat].kind === "cpu" ? game.takeOver(seat, slot, name) : game.seatHuman(seat, slot, name);
  if (!ok) return false;
  const now = Instance.GetGameTime();
  // useArmed: the E press that joined must be let go before holding E counts as leaving
  const p = { seat, pawn, watch: false, pad: at ? copyV(at) : copyV(pawn.GetAbsOrigin()), useSince: -1, useArmed: !pawn.IsInputPressed(CSInputs.USE), held: 0, pressed: 0, since: now, weapons: null };
  players.set(slot, p);
  // a key held while joining must not count as a press
  for (const [ci, bit] of INPUT_MAP) if (pawn.IsInputPressed(ci)) p.held |= bit;
  game.fighters[seat].prevHeld = p.held;
  holdPlayer(pawn, p.pad);
  armForPlay(pawn, p);
  takeCamera(slot, pawn);
  hudGuard("show", () => hudShowFor(slot, true));
  log(`${name} took pad ${seat + 1}`);
  return true;
}

/** @param {number} slot @param {import("cs_script/point_script").CSPlayerController} ctrl @param {import("cs_script/point_script").CSPlayerPawn} pawn */
function watchPlayer(slot, ctrl, pawn) {
  const p = { seat: -1, pawn, watch: true, pad: copyV(pawn.GetAbsOrigin()), useSince: -1, useArmed: false, held: 0, pressed: 0, since: Instance.GetGameTime(), weapons: null };
  players.set(slot, p);
  holdPlayer(pawn, null);
  takeCamera(slot, pawn);
  hudGuard("show", () => hudShowFor(slot, true));
}

function leave(slot, reason, teleport = true) {
  const p = players.get(slot);
  if (!p) return;
  players.delete(slot);
  if (!p.watch && game) game.unseat(p.seat, reason);
  giveBackCamera(slot);
  hudGuard("hide", () => hudShowFor(slot, false));
  reentry.set(slot, Instance.GetGameTime() + CONFIG.REENTRY_COOLDOWN);
  releasePawn(p.pawn, p, teleport && !p.watch);
  dlog(`slot ${slot} left (${reason})`);
}

function leaveAll(reason) {
  for (const slot of [...players.keys()]) leave(slot, reason, false);
  for (const slot of [...camHeld.keys()]) giveBackCamera(slot);
}

// Pawn (any kind) -> its controller's slot; controller -> its slot. Duck-typed on purpose.
/** @param {import("cs_script/point_script").Entity | undefined} e @returns {number | undefined} */
function slotOfEntity(e) {
  if (!e) return undefined;
  try {
    const x = /** @type {any} */ (e);
    if (typeof x.GetPlayerController === "function") { const c = x.GetPlayerController(); return c ? c.GetPlayerSlot() : undefined; }
    if (typeof x.GetPlayerSlot === "function") return x.GetPlayerSlot();
  } catch (err) { /* ignore */ }
  return undefined;
}

function pollPlayers(now) {
  for (const [slot, p] of [...players]) {
    const ctrl = Instance.GetPlayerController(slot);
    const pawn = ctrl && ctrl.IsConnected() ? ctrl.GetPlayerPawn() : undefined;
    if (!live(pawn) || !pawn.IsAlive() || pawn !== p.pawn) { leave(slot, "gone", false); continue; }
    if (!CONFIG.FREEZE_PLAYERS && dist2d(pawn.GetAbsOrigin(), p.pad) > 24) pawn.Teleport({ position: copyV(p.pad), velocity: ZERO });
    if (p.watch) {
      if (now > p.since + 0.4 && pawn.WasInputJustPressed(CSInputs.USE)) leave(slot, "stopped watching", false);
      continue;
    }
    if (pawn.IsInputPressed(CSInputs.USE)) {
      if (!p.useArmed) { /* still holding the E that joined */ }
      else if (p.useSince < 0) p.useSince = now;
      else if (now - p.useSince >= CONFIG.HOLD_USE_TO_LEAVE) { leave(slot, "left"); continue; }
    } else { p.useSince = -1; p.useArmed = true; }
    let held = 0, pressed = 0;
    for (const [ci, bit] of INPUT_MAP) {
      if (pawn.IsInputPressed(ci)) held |= bit;
      if (pawn.WasInputJustPressed(ci)) pressed |= bit;
    }
    p.held = held; p.pressed |= pressed;
    if (CONFIG.WEAPONS === "knife" && (tickCount + slot) % 16 === 0) holdKnife(pawn);
  }
  for (const ctrl of Instance.GetAllPlayerControllers()) {
    if (!ctrl || !ctrl.IsConnected() || ctrl.IsBot()) continue;
    const slot = ctrl.GetPlayerSlot();
    if (players.has(slot)) continue;
    const pawn = ctrl.GetPlayerPawn();
    if (!live(pawn) || !pawn.IsAlive()) continue;
    if (!pawn.WasInputJustPressed(CSInputs.USE)) continue;
    if (now < (reentry.get(slot) ?? 0)) continue;
    const o = pawn.GetAbsOrigin();
    let done = false;
    for (let i = 0; i < 4 && !done; i++) {
      const pad = pads[i];
      if (!pad || (game.seats[i].kind && !game.canTakeOver(i))) continue;
      if (dist2d(o, pad) <= CONFIG.PAD_RADIUS && Math.abs(o.z - pad.z) < 80) done = seatPlayer(slot, ctrl, pawn, i, pad);
    }
    if (!done) for (const w of watchSpots) {
      if (dist2d(o, w) <= CONFIG.PAD_RADIUS && Math.abs(o.z - w.z) < 80) { watchPlayer(slot, ctrl, pawn); break; }
    }
  }
}

// ------------------------------------------------------------------ lifecycle
// Spectator spots: whatever pb_watch* matches, plus the usual numbered names in case this
// build's name lookup has no wildcard support.
function findWatchSpots() {
  const seen = new Set(), out = [];
  const add = (e) => { if (live(e) && !seen.has(e)) { seen.add(e); out.push(copyV(e.GetAbsOrigin())); } };
  try { for (const e of Instance.FindEntitiesByName(CONFIG.WATCH_PREFIX + "*")) add(e); } catch (err) { /* ignore */ }
  add(findNamed(CONFIG.WATCH_PREFIX));
  for (let i = 1; i <= 8; i++) { add(findNamed(CONFIG.WATCH_PREFIX + i)); add(findNamed(CONFIG.WATCH_PREFIX + "_" + i)); }
  return out;
}

/** run the arena server commands (bots out, rounds never end) */
function arenaCommands() {
  for (const c of CONFIG.ARENA_COMMANDS || []) { try { Instance.ServerCommand(c); } catch (err) { warnOnce("cmd", "ServerCommand failed: " + err); return; } }
}
function init() {
  arenaCommands();
  leaveAll("restart");
  removeSpawned();
  stage = discoverStage();
  if (!stage) {
    ready = false;
    warnOnce("stage", `no stage: add info_targets ${CONFIG.STAGE_LEFT} + ${CONFIG.STAGE_RIGHT} (or ${CONFIG.STAGE_CENTER})`);
    return;
  }
  game = new Game({
    seed: (Math.floor(Instance.GetGameTime() * 1000) % 100000) + 7,
    halfWidth: Math.max(140, stage.halfFU - 8),
    cfg: { mode: CONFIG.DEFAULT_MODE, roundTime: CONFIG.ROUND_TIME, roundsToWin: CONFIG.ROUNDS_TO_WIN, hpScale: CONFIG.HEALTH_SCALE, cpuLevel: CONFIG.CPU_LEVEL, backBlocks: CONFIG.BACK_BLOCKS, perfectBlock: CONFIG.PERFECT_BLOCK, perfectWindow: CONFIG.PERFECT_WINDOW,
      modes: CONFIG.MODES, tagTeam: CONFIG.TAG_TEAM, tagCooldown: CONFIG.TAG_COOLDOWN },
  });
  pads = [1, 2, 3, 4].map((i) => { const e = findNamed(CONFIG.PAD_PREFIX + i); return e ? copyV(e.GetAbsOrigin()) : null; });
  watchSpots = findWatchSpots();
  templates = {};
  exitEnt = findNamed(CONFIG.EXIT);
  camEnt = findNamed(CONFIG.CAMERA_ENTITY);
  projSlots = [0, 1, 2, 3].map(makeSlot);
  sparkSlots = game.sparks.map(makeSlot);
  resetFx();
  hud = null; hudFailures = 0;
  const hudFound = findNamed(CONFIG.HUD);
  if (isHudLayout(hudFound)) hud = /** @type {any} */ (hudFound);
  else if (hudFound) warnOnce("hudtype", `${CONFIG.HUD} isn't a custom_hud_layout`);
  hudCache.clear(); hudPlayerCache.clear(); hudWidths.clear();
  if (hud) { try { hud.Reset(); } catch (err) { /* ignore */ } hudGuard("setup", hudInitDefaults); }
  soundOk.clear();
  for (const id of SOUND_IDS) if (findNamed(CONFIG.SOUND_PREFIX + id)) soundOk.add(id);
  for (const n of [CONFIG.TEMPLATES.ball, ...CHARACTERS.map((c) => CONFIG.TEMPLATES.body + c.id)]) if (!findNamed(n)) warnOnce("tpl:" + n, `no point_template named ${n}`);
  if (!pads.some(Boolean)) warnOnce("pads", `no pads found (${CONFIG.PAD_PREFIX}1..4) - players can only join through Join buttons`);
  if (!hud) warnOnce("hud", `no custom_hud_layout named ${CONFIG.HUD} - fights run without a HUD`);
  ready = true;
  lastTime = Instance.GetGameTime();
  acc = 0;
  log(`v${PB_VERSION} ready: stage ${Math.round(stage.half * 2)} units, ${pads.filter(Boolean).length} pads, ${watchSpots.length} watch spots, HUD ${hud ? "on" : "off"}, ${soundOk.size} sounds, mode ${MODE_LABEL[game.mode]}`);
}

function tick() {
  const now = Instance.GetGameTime();
  tickCount++;
  playedThisTick = new Set();
  if (!ready) {
    if (now >= retryAt) { retryAt = now + 3; init(); }
    return;
  }
  let dt = now - lastTime;
  lastTime = now;
  if (!(dt >= 0) || dt > 0.25) dt = DT;
  acc += dt;
  pollPlayers(now);
  let steps = Math.min(4, Math.round(acc / DT));
  acc -= steps * DT;
  if (acc > DT * 4 || acc < -DT * 4) acc = 0;
  for (let s = 0; s < steps; s++) {
    for (const p of players.values()) {
      if (p.watch) continue;
      game.fighters[p.seat].setInput(p.held, p.pressed);
      p.pressed = 0;
    }
    game.step();
    handleEvents();
  }
  if (steps > 0) { renderAll(); updateCameras(); }
  if (tickCount % 2 === 0) hudGuard("update", updateHud);
  if (tickCount % CONFIG.JOIN_HINT_EVERY === 0) hudGuard("hints", updateJoinHints);
}

Instance.SetThink(() => {
  Instance.SetNextThink(Instance.GetGameTime());
  try { tick(); }
  catch (err) {
    errorCount++;
    if (errorCount <= 10) log("script error: " + (err && err.stack ? err.stack : err));
    if (errorCount === 10) log("(further errors hidden)");
  }
});

function start() { init(); Instance.SetNextThink(Instance.GetGameTime()); }
Instance.OnActivate(start);
hook("OnScriptReload", {
  before: () => { try { leaveAll("reload"); removeSpawned(); } catch (err) { /* ignore */ } return null; },
  after: () => start(),
});
hook("OnBeginRoundRestart", () => {
  try { leaveAll("round restart"); } catch (err) { /* ignore */ }
  ready = false;
  retryAt = Instance.GetGameTime() + 1;     // normally OnRoundStart re-arms this sooner
});
hook("OnRoundStart", () => {
  try { arenaCommands(); } catch (err) { /* ignore */ }
  try { leaveAll("round start"); } catch (err) { /* ignore */ }
  ready = false;
  retryAt = Instance.GetGameTime() + 0.5;   // map entities respawn at round start: re-find them shortly
});
/** @param {any} player @param {string} why */
function leaveIfSeated(player, why) { const s = slotOfEntity(player); if (s !== undefined && players.has(s)) leave(s, why, false); }
hook("OnPlayerDisconnect", (/** @type {{playerSlot: number}} */ { playerSlot }) => { if (players.has(playerSlot)) leave(playerSlot, "disconnected", false); camHeld.delete(playerSlot); });
hook("OnPlayerKill", (/** @type {any} */ { player }) => leaveIfSeated(player, "died"));
hook("OnPlayerReset", (/** @type {any} */ { player }) => leaveIfSeated(player, "respawned"));
hook("OnPlayerTeamChanged", (/** @type {any} */ { player }) => leaveIfSeated(player, "team change"));
hook("OnModifyPlayerDamage", (/** @type {any} */ event) => {
  if (!CONFIG.PROTECT_PLAYERS) return;
  const s = slotOfEntity(event.player);
  if (s !== undefined && players.has(s)) return { abort: true };
});

// ------------------------------------------------------------------ map buttons
/** @param {string} name @param {(data: any) => void} fn */
function onInput(name, fn) {
  hook("OnScriptInput", name, (/** @type {any} */ data) => {
    try {
      if (!ready) { buttonSay("not ready yet - try again in a second"); return; }
      fn(data);
    } catch (err) { log("input " + name + " failed: " + err); }
  });
}
// every host button says in chat what it did, so the whole room can see it worked
let lastSay = "", lastSayAt = -9;
/** @param {string} text */
function buttonSay(text) {
  const now = Instance.GetGameTime();
  if (text === lastSay && now - lastSayAt < 0.4) return;
  lastSay = text; lastSayAt = now;
  log(text);
  if (CONFIG.BUTTON_CHAT) { try { Instance.ServerCommand("say " + safeText("[Puppet Brawl] " + text)); } catch (err) { /* ignore */ } }
}
const seatWord = (seat) => "pad " + (seat + 1) + (game.mode === "teams" ? (seat < 2 ? " (RED)" : " (BLUE)") : "");
function seatedCount() { return game.seated().length + " of 4 seats filled"; }
/** @param {string} mode */
function modeButton(mode) {
  const before = game.pendingMode || game.mode;
  if (mode === "next") game.cycleMode(); else game.setMode(mode);
  const now = game.pendingMode || game.mode;
  if (now === before && mode !== "next") buttonSay("mode is already " + MODE_LABEL[now]);
  else buttonSay((game.inMatch() ? "next match will be " : "mode: ") + MODE_LABEL[now]);
}
onInput("ModeDuel", () => modeButton("duel"));
onInput("ModeTeams", () => modeButton("teams"));
onInput("ModeFFA", () => modeButton("ffa"));
onInput("ModeNext", () => modeButton("next"));
onInput("AddCPU", () => {
  const seat = game.addCpu();
  if (seat < 0) { buttonSay("no free seat - all 4 pads are taken"); return; }
  buttonSay("CPU added on " + seatWord(seat) + " as " + game.fighters[seat].ch.name + " - " + seatedCount() + (game.inMatch() ? " (joins the next match)" : ""));
});
onInput("RemoveCPU", () => {
  const seat = game.removeCpu();
  buttonSay(seat < 0 ? "there are no CPUs to remove" : "CPU on " + seatWord(seat) + " removed - " + seatedCount());
});
onInput("StopCPU", () => stopCpuGame());
onInput("CpuEasy", () => setCpuLevel(0));
onInput("CpuNormal", () => setCpuLevel(1));
onInput("CpuHard", () => setCpuLevel(2));
onInput("Start", () => {
  if (game.inMatch()) { buttonSay("a match is already running"); return; }
  if (game.forceStart()) { buttonSay("starting " + MODE_LABEL[game.mode] + " with " + game.seated().length + " fighters"); return; }
  buttonSay(game.seated().length < 2 ? "need at least 2 fighters - stand on a pad or press ADD CPU"
    : "tag team needs someone on each side: pads 1-2 (RED) and pads 3-4 (BLUE)");
});
// the game is reset first so emptying the seats can't hand out forfeit wins in chat
onInput("Reset", () => { game.reset(); game.cfg.needHuman = true; leaveAll("reset"); buttonSay("reset - everyone back to the lobby"); });
onInput("Join", ({ activator }) => {
  const slot = slotOfEntity(activator);
  if (slot === undefined || players.has(slot)) return;
  const ctrl = Instance.GetPlayerController(slot), pawn = ctrl?.GetPlayerPawn();
  if (!ctrl || !live(pawn) || !pawn.IsAlive()) return;
  let seat = game.freeSeat();
  if (seat < 0) seat = [0, 1, 2, 3].find((i) => game.canTakeOver(i)) ?? -1;
  if (seat >= 0) seatPlayer(slot, ctrl, pawn, seat, pads[seat]);
});
onInput("Leave", ({ activator }) => { const s = slotOfEntity(activator); if (s !== undefined) leave(s, "left"); });
onInput("Watch", ({ activator }) => {
  const slot = slotOfEntity(activator);
  if (slot === undefined) return;
  if (players.has(slot)) { if (players.get(slot).watch) leave(slot, "stopped watching", false); return; }
  const ctrl = Instance.GetPlayerController(slot), pawn = ctrl?.GetPlayerPawn();
  if (live(pawn) && pawn.IsAlive()) watchPlayer(slot, ctrl, pawn);
});
function setCpuLevel(level) {
  game.cfg.cpuLevel = level;
  for (const s of game.seats) if (s.brain) s.brain.L = AI_LEVELS[level];
  game.announce("CPU: " + ["EASY", "NORMAL", "HARD"][level], "small", 1.2);
  buttonSay("CPU level: " + ["EASY", "NORMAL", "HARD"][level]);
}

// ------------------------------------------------------------------ console (sv_cheats 1)
hook("RegisterCheatCommand", "pb_status", () => {
  if (!game) { log("not running"); return; }
  log(`phase ${game.phase}  mode ${game.mode}  round ${game.roundNum}  timer ${game.roundTimer.toFixed(1)}`);
  for (let i = 0; i < 4; i++) {
    const s = game.seats[i], f = game.fighters[i];
    log(`  P${i + 1}: ${s.kind || "-"} ${s.name}  ${f.ch.name}  hp ${f.hp}/${f.maxHp}  ${f.state}  x ${f.x.toFixed(0)}  active ${f.active}`);
  }
  log(`  players at the controls: ${[...players.keys()].join(", ") || "none"}  cameras held: ${camHeld.size}`);
});
hook("RegisterCheatCommand", "pb_cpu_match", () => {
  if (!ready) return;
  game.cfg.needHuman = false; game.forceCpuMatch = true;
  while (game.addCpu() >= 0) { /* fill every free seat */ }
  game.forceStart();
  log("CPU match started - the camera is yours if you join a watch spot (or use pb_join_host first)");
});
/** ends any CPU game: every CPU leaves, a CPU-only match stops */
function stopCpuGame() {
  const n = game.seated().filter((i) => game.seats[i].kind === "cpu").length;
  const hadMatch = game.stopCpus();
  game.announce("CPU GAME OVER", "small", 1.4);
  buttonSay(n ? n + " CPU" + (n > 1 ? "s" : "") + " removed" + (hadMatch ? " and the match stopped" : "") : "there were no CPUs to stop");
}
hook("RegisterCheatCommand", "pb_stop", () => { if (ready) stopCpuGame(); });
hook("RegisterCheatCommand", "pb_join_host", () => {
  if (!ready) return;
  const ctrl = Instance.GetPlayerController(0), pawn = ctrl?.GetPlayerPawn();
  if (!ctrl || !live(pawn)) { log("no player in slot 0"); return; }
  if (players.has(0)) { log("slot 0 is already at the controls"); return; }
  let seat = game.freeSeat();
  if (seat < 0) seat = [0, 1, 2, 3].find((i) => game.canTakeOver(i)) ?? -1;
  if (seat >= 0) seatPlayer(0, ctrl, pawn, seat, pads[seat]);
  else log("no free seat");
});
hook("RegisterCheatCommand", "pb_debug", () => { debugOn = !debugOn; log("debug " + (debugOn ? "on" : "off")); });
