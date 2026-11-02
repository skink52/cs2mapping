// =====================================================================================
//  PUPPET BRAWL core - part 1: constants, maths, roster, skeleton + pose system
//  Engine-agnostic. The CS2 script and the browser preview both run this same code.
// =====================================================================================

const PB_VERSION = "1.0.0";
const SIM_HZ = 64;
const DT = 1 / SIM_HZ;

// Game-level input bits. Each front end maps its own keys onto these.
const IN = {
  LEFT: 1 << 0, RIGHT: 1 << 1, UP: 1 << 2, DOWN: 1 << 3,
  PUNCH: 1 << 4, KICK: 1 << 5, BLOCK: 1 << 6, SPECIAL: 1 << 7,
  THROW: 1 << 8, USE: 1 << 9,
};

const DEG = Math.PI / 180;
function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
function lerp(a, b, t) { return a + (b - a) * t; }
function smooth01(t) { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); }
function wrap180(a) { a %= 360; if (a > 180) a -= 360; if (a < -180) a += 360; return a; }
// Skeleton angles are measured from straight DOWN, positive toward the way the
// fighter faces: 0 = down, 90 = forward, 180 = up, -90 = backward.
function dX(a) { return Math.sin(a * DEG); }
function dY(a) { return -Math.cos(a * DEG); }
function angleOf(dx, dy) { return Math.atan2(dx, -dy) / DEG; }
function finite(n) { return typeof n === "number" && Number.isFinite(n); }

function distPointSeg(px, py, ax, ay, bx, by) {
  const vx = bx - ax, vy = by - ay;
  const len2 = vx * vx + vy * vy;
  let t = len2 > 1e-9 ? ((px - ax) * vx + (py - ay) * vy) / len2 : 0;
  t = clamp(t, 0, 1);
  const cx = ax + vx * t - px, cy = ay + vy * t - py;
  return Math.sqrt(cx * cx + cy * cy);
}

function makeRng(seed) {
  let s = (seed >>> 0) || 1;
  const rng = () => {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  rng.range = (a, b) => a + (b - a) * rng();
  rng.int = (a, b) => Math.floor(a + (b - a + 1) * rng());
  rng.chance = (p) => rng() < p;
  rng.pick = (arr) => arr[Math.floor(rng() * arr.length) % arr.length];
  return rng;
}

// ------------------------------------------------------------------ colours ----------
const PLAYER_COLORS = [
  { r: 232, g: 62, b: 58 },    // P1 red
  { r: 40, g: 132, b: 232 },   // P2 blue
  { r: 64, g: 178, b: 84 },    // P3 green
  { r: 246, g: 196, b: 40 },   // P4 yellow
];
const PLAYER_COLOR_NAMES = ["RED", "BLUE", "GREEN", "YELLOW"];
// Teams mode recolours the four seats into two families.
const TEAM_COLORS = [
  [{ r: 232, g: 62, b: 58 }, { r: 255, g: 132, b: 52 }],   // left team: red / orange
  [{ r: 40, g: 132, b: 232 }, { r: 40, g: 196, b: 214 }],  // right team: blue / teal
];
const TEAM_NAMES = ["RED TEAM", "BLUE TEAM"];
function shade(c, k) {
  return { r: clamp(Math.round(c.r * k), 0, 255), g: clamp(Math.round(c.g * k), 0, 255), b: clamp(Math.round(c.b * k), 0, 255) };
}
function mix(c1, c2, t) {
  return { r: Math.round(lerp(c1.r, c2.r, t)), g: Math.round(lerp(c1.g, c2.g, t)), b: Math.round(lerp(c1.b, c2.b, t)) };
}

// ------------------------------------------------------------------ the roster -------
// Body sizes are in "fighter units" (FU). A standard puppet stands ~92 FU tall; the
// CS2 script multiplies everything by its WORLD_SCALE.
// specials: [neutral R / motion, toward+R / motion, down+R / motion]
// Body sizes match the CS2 agent skeleton (all agents share it): 1 FU = SKELETON_UNITS world
// units at scale 1, so the hit boxes sit on the visible model. `scale` grows or shrinks the
// whole fighter (model and hit boxes together). `agent` is the CS2 model each fighter wears.
const SKELETON_UNITS = 0.72;
const BASE_DIMS = { thigh: 24.9, shin: 23.5, foot: 9.4, torso: 36.4, neck: 4.3, headR: 6.4, uarm: 16.4, farm: 15.4, fistR: 4.9 };
const CHARACTERS = [
  {
    id: "timber", name: "TIMBER",
    tag: "Street boxer. Balanced, with a heavy right hand.",
    agent: "agents/models/tm_professional/tm_professional_varf.vmdl",
    accent: { r: 255, g: 176, b: 64 },
    scale: 1.0,
    limb: "limb",
    stats: { hp: 100, walkF: 175, walkB: 140, dashV: 430, jumpVy: 650, jumpVx: 205, dmg: 1.0, pushW: 14, frame: 1.0 },
    extras: [],
    specials: ["knotShot", "haymaker", "risingSplinter"],
    combos: { p: "splitter", k: "timberFall", mix: "rootSweep" },
    style: { windup: 1.0, follow: 1.0 },
    victory: "victoryBoxer",
  },
  {
    id: "brass", name: "BRASS",
    tag: "Riot heavy. Slow, armoured, hits like a truck.",
    agent: "agents/models/ctm_swat/ctm_swat_varianth.vmdl",
    accent: { r: 70, g: 210, b: 255 },
    scale: 1.07,
    limb: "block",
    stats: { hp: 106, walkF: 135, walkB: 112, dashV: 360, jumpVy: 600, jumpVx: 170, dmg: 1.1, pushW: 16, frame: 1.12 },
    extras: [{ ox: 0, oy: 1.25, r: 2.4 }],
    specials: ["cogToss", "steamRam", "pistonStomp"],
    combos: { p: "rivetHammer", k: "boilerKick", mix: "gearGrind" },
    style: { windup: 1.5, follow: 1.25 },
    victory: "victorySalute",
  },
  {
    id: "pirouette", name: "PIROUETTE",
    tag: "Field agent with a dancer's kicks. Fast and light.",
    agent: "agents/models/ctm_fbi/ctm_fbi_variantb.vmdl",
    accent: { r: 255, g: 92, b: 205 },
    scale: 1.0,
    limb: "limb",
    stats: { hp: 104, walkF: 205, walkB: 168, dashV: 490, jumpVy: 700, jumpVx: 232, dmg: 1.08, pushW: 13, frame: 0.94 },
    extras: [{ ox: -0.85, oy: 0.55, r: 3.3 }],
    specials: ["spinKick", "glide", "fouette"],
    combos: { p: "pasDeDeux", k: "arabesque", mix: "plieSweep" },
    style: { windup: 0.7, follow: 1.4 },
    victory: "victoryBallet",
  },
  {
    id: "motley", name: "MOTLEY",
    tag: "Masked trickster. Teleports and juggles.",
    agent: "agents/models/tm_leet/tm_leet_variantf.vmdl",
    accent: { r: 150, g: 255, b: 120 },
    scale: 0.95,
    limb: "limb",
    stats: { hp: 94, walkF: 185, walkB: 152, dashV: 455, jumpVy: 665, jumpVx: 216, dmg: 0.95, pushW: 13, frame: 1.0 },
    extras: [{ ox: -0.95, oy: 1.0, r: 2.7 }, { ox: 0.8, oy: 1.1, r: 2.7 }],
    specials: ["juggleBall", "cartwheel", "pratfall"],
    combos: { p: "slapstick", k: "bananaSweep", mix: "jesterDrop" },
    style: { windup: 1.35, follow: 1.6 },
    victory: "victoryBow",
  },
];
// Standard proportions the poses are authored against.
const STD_LEG = 49, STD_ARM = 31;
const FIST_OFFSET = 0.85;   // fist centre past the wrist, in fist radii (a CS2 hand is long)
for (const ch of CHARACTERS) {
  ch.dims = {};
  for (const k in BASE_DIMS) ch.dims[k] = BASE_DIMS[k] * ch.scale;
  const d = ch.dims;
  ch.legF = (d.thigh + d.shin) / STD_LEG;
  ch.armF = (d.uarm + d.farm) / STD_ARM;
  ch.height = (d.thigh + d.shin) * 0.9 + d.torso + d.neck + d.headR * 2;
}

// ------------------------------------------------------------------ models -----------
// Part models are authored along +X from the pivot, MODEL_LEN long (the "ball" is a
// sphere of radius MODEL_BALL_R). Thickness ratios match the generated meshes.
const MODEL_LEN = 16;
const MODEL_BALL_R = 8;
const LIMB_RADIUS_K = 2.6 / 16;     // limb capsule radius per unit length
const BLOCK_HALF_K = 4.1 / 16;      // average half-thickness of the tapered block

// Part indices inside a puppet.
const PART = {
  TORSO: 0, HEAD: 1,
  B_UARM: 2, B_FARM: 3, B_FIST: 4,
  F_UARM: 5, F_FARM: 6, F_FIST: 7,
  B_THIGH: 8, B_SHIN: 9, B_FOOT: 10,
  F_THIGH: 11, F_SHIN: 12, F_FOOT: 13,
  EXTRA0: 14, EXTRA1: 15,
};
const PART_COUNT = 16;

// ------------------------------------------------------------------ pose arrays ------
// A resolved pose is a flat array so it can be blended cheaply.
const P_HX = 0, P_HY = 1, P_TL = 2, P_HD = 3, P_ROT = 4, P_SC = 5,
  P_FA0 = 6, P_FA1 = 7, P_BA0 = 8, P_BA1 = 9, P_FL0 = 10, P_FL1 = 11, P_BL0 = 12, P_BL1 = 13,
  P_FF = 14, P_BF = 15, P_FLIP = 16, P_AUTO = 17, P_LEN = 18;
const ANGLE_IDX = [P_FA0, P_BA0, P_FL0, P_BL0, P_FF, P_BF];

function newPose() { const p = new Array(P_LEN).fill(0); p[P_SC] = 1; p[P_FF] = 90; p[P_BF] = 90; return p; }
function copyPose(src, dst) { dst = dst || new Array(P_LEN); for (let i = 0; i < P_LEN; i++) dst[i] = src[i]; return dst; }
function lerpPose(a, b, t, out) {
  out = out || new Array(P_LEN);
  for (let i = 0; i < P_LEN; i++) out[i] = a[i] + (b[i] - a[i]) * t;
  for (const i of ANGLE_IDX) out[i] = a[i] + wrap180(b[i] - a[i]) * t;
  return out;
}

// Two-bone IK. Returns absolute angles of both bones (degrees, skeleton convention).
// bend = +1 puts the middle joint on the forward side (knees), -1 below/behind (elbows).
function ik2(px, py, tx, ty, l1, l2, bend) {
  let dx = tx - px, dy = ty - py;
  let d = Math.sqrt(dx * dx + dy * dy);
  if (d < 1e-6) { dx = 0; dy = -1; d = 1e-6; }
  const maxD = l1 + l2 - 0.02, minD = Math.abs(l1 - l2) + 0.5;
  const dc = clamp(d, minD, maxD);
  const phi = angleOf(dx, dy);
  const cosA = clamp((l1 * l1 + dc * dc - l2 * l2) / (2 * l1 * dc), -1, 1);
  const alpha = Math.acos(cosA) / DEG;
  const a1 = phi + bend * alpha;
  const kx = px + l1 * dX(a1), ky = py + l1 * dY(a1);
  const ex = px + (dx / d) * dc, ey = py + (dy / d) * dc;
  return [a1, angleOf(ex - kx, ey - ky)];
}

// Pose spec -> resolved array for one character.
// Spec keys (all optional):
//   hy  pelvis height (FU, scaled by leg length). Leave out for "auto": lowest point on the floor
//   hx  pelvis forward offset, tl torso lean (+ forward), hd head tilt (+ chin down)
//   rot whole-body rotation (+ = tumble forward), sc render scale (vanish effects), flip mirror
//   fa/ba front/back arm:  [shoulderAngle, elbowBend]  or  {x, y} wrist target from the shoulder
//   fl/bl front/back leg:  [hipAngle, kneeBend]        or  {x, y, r:'g'|'h'} ankle target
//                          ('g' = from the fighter's ground point, 'h' = from the hip)
//   ff/bf foot angle (absolute, 90 = flat pointing forward) or {rel:n} relative to the shin
function resolvePose(spec, ch) {
  const d = ch.dims, legF = ch.legF, armF = ch.armF;
  const p = newPose();
  p[P_HX] = (spec.hx || 0) * legF;
  p[P_TL] = spec.tl || 0;
  p[P_HD] = spec.hd || 0;
  p[P_ROT] = spec.rot || 0;
  p[P_SC] = spec.sc === undefined ? 1 : spec.sc;
  p[P_FLIP] = spec.flip ? 1 : 0;
  const auto = spec.hy === undefined || spec.hy === null;
  p[P_AUTO] = auto ? 1 : 0;
  const hy = auto ? 0 : spec.hy * legF;
  p[P_HY] = hy;
  const hx = p[P_HX];
  const td = 180 - p[P_TL];
  const sx = hx + d.torso * 0.86 * dX(td), sy = hy + d.torso * 0.86 * dY(td);
  const arm = (s, out0, out1) => {
    if (!s) return;
    if (Array.isArray(s)) { p[out0] = s[0]; p[out1] = s[1]; return; }
    const tx = sx + s.x * armF, ty = sy + s.y * armF;
    const [a1, a2] = ik2(sx, sy, tx, ty, d.uarm, d.farm, -1);
    p[out0] = a1; p[out1] = wrap180(a2 - a1);
  };
  const leg = (s, out0, out1) => {
    if (!s) return;
    if (Array.isArray(s)) { p[out0] = s[0]; p[out1] = s[1]; return; }
    let tx, ty;
    if (s.r === "h") { tx = hx + s.x * legF; ty = hy + s.y * legF; }
    else { tx = s.x * legF; ty = s.y * legF; }
    const [a1, a2] = ik2(hx, hy, tx, ty, d.thigh, d.shin, +1);
    p[out0] = a1; p[out1] = wrap180(a1 - a2);
  };
  arm(spec.fa || [20, 60], P_FA0, P_FA1);
  arm(spec.ba || [10, 60], P_BA0, P_BA1);
  leg(spec.fl || [10, 10], P_FL0, P_FL1);
  leg(spec.bl || [-10, 10], P_BL0, P_BL1);
  const foot = (s, hip, knee) => {
    if (s === undefined) return 90;
    if (typeof s === "number") return s;
    return hip - knee + (s.rel || 0);
  };
  p[P_FF] = foot(spec.ff, p[P_FL0], p[P_FL1]);
  p[P_BF] = foot(spec.bf, p[P_BL0], p[P_BL1]);
  if (auto) {
    const tmp = makeSkeleton();
    skeletonLocal(ch, p, tmp, 0);
    p[P_HY] = -tmp.minY;
  }
  return p;
}

// ------------------------------------------------------------------ forward kinematics
const JOINTS = ["P", "N", "H", "S", "fE", "fW", "fF", "bE", "bW", "bF", "fK", "fA", "fT", "bK", "bA", "bT", "X0", "X1"];
function makeSkeleton() {
  const s = { minY: 0, pts: {} };
  for (const j of JOINTS) s.pts[j] = { x: 0, y: 0 };
  return s;
}

// Fills skeleton points relative to the pelvis (rotation and scale applied, facing right).
// pelvisY is added to y. Returns the skeleton; minY = lowest surface point (with radii).
function skeletonLocal(ch, p, sk, pelvisY) {
  const d = ch.dims, P = sk.pts;
  const td = 180 - p[P_TL];
  const set = (j, x, y) => { P[j].x = x; P[j].y = y; };
  set("P", 0, 0);
  set("N", d.torso * dX(td), d.torso * dY(td));
  set("S", d.torso * 0.86 * dX(td), d.torso * 0.86 * dY(td));
  const hdir = td - p[P_HD];
  set("H", P.N.x + (d.neck + d.headR) * dX(hdir), P.N.y + (d.neck + d.headR) * dY(hdir));
  const arm = (pre, a, e) => {
    const E = P[pre + "E"], W = P[pre + "W"], F = P[pre + "F"];
    E.x = P.S.x + d.uarm * dX(a); E.y = P.S.y + d.uarm * dY(a);
    W.x = E.x + d.farm * dX(a + e); W.y = E.y + d.farm * dY(a + e);
    F.x = W.x + d.fistR * FIST_OFFSET * dX(a + e); F.y = W.y + d.fistR * FIST_OFFSET * dY(a + e);
  };
  arm("f", p[P_FA0], p[P_FA1]);
  arm("b", p[P_BA0], p[P_BA1]);
  const leg = (pre, h, k, footA) => {
    const K = P[pre + "K"], A = P[pre + "A"], T = P[pre + "T"];
    K.x = d.thigh * dX(h); K.y = d.thigh * dY(h);
    A.x = K.x + d.shin * dX(h - k); A.y = K.y + d.shin * dY(h - k);
    T.x = A.x + d.foot * dX(footA); T.y = A.y + d.foot * dY(footA);
  };
  leg("f", p[P_FL0], p[P_FL1], p[P_FF]);
  leg("b", p[P_BL0], p[P_BL1], p[P_BF]);
  // extras ride on the head
  const ex = ch.extras || [];
  for (let i = 0; i < 2; i++) {
    const X = P["X" + i];
    if (!ex[i]) { X.x = P.H.x; X.y = P.H.y; continue; }
    const up = hdir, fw = hdir - 90;
    X.x = P.H.x + (ex[i].ox * dX(fw) + ex[i].oy * dX(up)) * d.headR;
    X.y = P.H.y + (ex[i].ox * dY(fw) + ex[i].oy * dY(up)) * d.headR;
  }
  // whole-body rotation about the pelvis (+ = forward tumble = clockwise) and scale
  const rot = p[P_ROT], sc = p[P_SC];
  if (rot !== 0 || sc !== 1) {
    const c = Math.cos(rot * DEG), s = Math.sin(rot * DEG);
    for (const j of JOINTS) {
      const q = P[j]; const x = q.x, y = q.y;
      q.x = (x * c + y * s) * sc; q.y = (-x * s + y * c) * sc;
    }
  }
  const fr = d.fistR * sc, hr = d.headR * sc, footR = BLOCK_HALF_K * d.foot * sc + 0.2;
  let minY = Math.min(P.fA.y, P.bA.y, P.fT.y, P.bT.y) - footR;
  minY = Math.min(minY, P.H.y - hr, P.fF.y - fr, P.bF.y - fr, P.fK.y - 3 * sc, P.bK.y - 3 * sc, P.P.y - 6 * sc, P.N.y - 6 * sc, P.fE.y - 2, P.bE.y - 2);
  for (const j of JOINTS) P[j].y += pelvisY;
  sk.minY = minY + pelvisY;
  return sk;
}

function limbRadius(ch, len) {
  return (ch.limb === "block" ? BLOCK_HALF_K : LIMB_RADIUS_K) * len;
}
