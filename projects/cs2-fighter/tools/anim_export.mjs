// Turns the shared core's 2D fighter poses into 3D animations on the CS2 agent skeleton.
//
// For each clip, every frame's 2D skeleton (side view: x forward, y up, in fighter units)
// is lifted into the agent's model space (+X forward, +Y left, +Z up). Hands and feet go
// exactly where the 2D hit boxes are (in the side view); the depth axis gets a boxer's
// stance twist, a guard that pulls the hands in, and feet at hip width. Elbows and knees
// are aimed through the 2D joint positions. The result is written as SMD animations plus a
// reference skeleton, and a ModelDoc .vmdl that lists them for the invisible "rig" model.
//
// Usage: node tools/anim_export.mjs <out_dir> [--preview preview.json]
import fs from "node:fs";
import path from "node:path";
import url from "node:url";
import * as C from "../dist/core_node.mjs";

const here = path.dirname(url.fileURLToPath(import.meta.url));
const outDir = process.argv[2] || path.join(here, "..", "dist", "addon");
const previewPath = process.argv.includes("--preview") ? process.argv[process.argv.indexOf("--preview") + 1] : null;
const { CHARACTERS, MOVES, Fighter, Game, P_LEN, P_HX, P_HY, P_ROT, P_SC, P_FLIP, P_AUTO, SKELETON_UNITS } = C;

// ------------------------------------------------------------------ small 3D maths
const V = {
  add: (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]],
  sub: (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]],
  mul: (a, s) => [a[0] * s, a[1] * s, a[2] * s],
  dot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2],
  cross: (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]],
  len: (a) => Math.hypot(a[0], a[1], a[2]),
  norm: (a) => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; },
  lerp: (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t],
};
// 3x3 matrices, row-major [r0c0, r0c1, r0c2, r1c0, ...]
const M = {
  I: () => [1, 0, 0, 0, 1, 0, 0, 0, 1],
  mul: (a, b) => {
    const o = new Array(9);
    for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) o[r * 3 + c] = a[r * 3] * b[c] + a[r * 3 + 1] * b[3 + c] + a[r * 3 + 2] * b[6 + c];
    return o;
  },
  T: (a) => [a[0], a[3], a[6], a[1], a[4], a[7], a[2], a[5], a[8]],
  apply: (m, v) => [m[0] * v[0] + m[1] * v[1] + m[2] * v[2], m[3] * v[0] + m[4] * v[1] + m[5] * v[2], m[6] * v[0] + m[7] * v[1] + m[8] * v[2]],
  fromQuat: ([x, y, z, w]) => [
    1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w),
    2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w),
    2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
  axisAngle: (ax, ang) => {
    const [x, y, z] = V.norm(ax), c = Math.cos(ang), s = Math.sin(ang), t = 1 - c;
    return [t * x * x + c, t * x * y - s * z, t * x * z + s * y, t * x * y + s * z, t * y * y + c, t * y * z - s * x, t * x * z - s * y, t * y * z + s * x, t * z * z + c];
  },
  // columns = basis vectors
  fromCols: (a, b, c) => [a[0], b[0], c[0], a[1], b[1], c[1], a[2], b[2], c[2]],
};
// orthonormal frame from an aim vector and a side hint (side made perpendicular to aim)
function frame(aim, side) {
  const a = V.norm(aim);
  let s = V.sub(side, V.mul(a, V.dot(side, a)));
  if (V.len(s) < 1e-6) s = Math.abs(a[2]) < 0.9 ? V.sub([0, 0, 1], V.mul(a, a[2])) : V.sub([1, 0, 0], V.mul(a, a[0]));
  s = V.norm(s);
  return M.fromCols(a, s, V.cross(a, s));
}
// rotation that carries bind frame (aimB, sideB) onto target frame (aimT, sideT)
const align = (aimB, sideB, aimT, sideT) => M.mul(frame(aimT, sideT), M.T(frame(aimB, sideB)));
// SMD euler: R = Rz(z) * Ry(y) * Rx(x)
function toEuler(m) {
  const sy = -m[6];
  let x, y, z;
  if (Math.abs(sy) < 0.99999) { y = Math.asin(sy); x = Math.atan2(m[7], m[8]); z = Math.atan2(m[3], m[0]); }
  else { y = sy > 0 ? Math.PI / 2 : -Math.PI / 2; x = Math.atan2(-m[5], m[4]); z = 0; }
  return [x, y, z];
}
const DEG = Math.PI / 180;

// ------------------------------------------------------------------ skeleton
const SK = JSON.parse(fs.readFileSync(path.join(here, "cs2_skeleton.json"), "utf8"));
const IDX = Object.fromEntries(SK.map((b, i) => [b.name, i]));
for (const b of SK) { b.pi = b.parent === null ? -1 : IDX[b.parent]; b.R = M.fromQuat(b.quat); b.p = b.pos.slice(); }
const BW = [];   // bind world [rot, pos]
for (const b of SK) {
  if (b.pi < 0) BW.push([b.R, b.p]);
  else { const [PR, PP] = BW[b.pi]; BW.push([M.mul(PR, b.R), V.add(PP, M.apply(PR, b.p))]); }
}
const bw = (n) => BW[IDX[n]];
const bindHipC = V.lerp(bw("leg_upper_L")[1], bw("leg_upper_R")[1], 0.5);
const bindTorsoAxis = V.norm(V.sub(bw("neck_0")[1], bindHipC));
const pelvisHipLocal = M.apply(M.T(bw("pelvis")[0]), V.sub(bindHipC, bw("pelvis")[1]));
const SPINE = ["spine_0", "spine_1", "spine_2", "spine_3"];
const FINGERS = ["index", "middle", "ring", "pinky"];
// knuckle axes from the bind hand: fingers curl toward the palm (the side the thumb is on)
const CURL = {};
for (const side of ["L", "R"]) {
  const p = (n) => bw(n + "_" + side)[1];
  const f = V.norm(V.sub(p("finger_middle_1"), p("finger_middle_0")));
  const k = V.norm(V.sub(p("finger_pinky_0"), p("finger_index_0")));
  let n = V.norm(V.cross(f, k));
  if (V.dot(n, V.sub(p("finger_thumb_2"), p("finger_middle_0"))) < 0) n = V.mul(n, -1);
  const tf = V.norm(V.sub(p("finger_thumb_2"), p("finger_thumb_1")));
  CURL[side] = { axis: V.norm(V.cross(f, n)), thumbAxis: V.norm(V.cross(tf, n)) };
}

// Pose: per-bone world rotation overrides; everything else follows its bind local transform.
function solveFK(rootPos, overrides) {
  const W = new Array(SK.length);
  for (let i = 0; i < SK.length; i++) {
    const b = SK[i];
    const o = overrides[i];
    if (b.pi < 0) { W[i] = [b.R, [0, 0, 0]]; continue; }
    const [PR, PP] = W[b.pi];
    const pos = b.name === "pelvis" ? rootPos : V.add(PP, M.apply(PR, b.p));
    let rot;
    if (o && o.world) rot = o.world;
    else if (o && o.local) rot = M.mul(PR, o.local);
    else rot = M.mul(PR, b.R);
    W[i] = [rot, pos];
  }
  return W;
}

// two-bone IK: start A, target C, lengths l1 l2, pole point P -> middle joint B (and clamped C)
function ik(A, C, l1, l2, P) {
  let d = V.sub(C, A), dist = V.len(d);
  const dir = V.norm(d);
  const maxD = (l1 + l2) * 0.9995, minD = Math.abs(l1 - l2) + 0.01;
  const dc = Math.min(maxD, Math.max(minD, dist));
  const Cc = V.add(A, V.mul(dir, dc));
  const a = (l1 * l1 - l2 * l2 + dc * dc) / (2 * dc);
  const h = Math.sqrt(Math.max(0, l1 * l1 - a * a));
  let pv = V.sub(P, A); pv = V.sub(pv, V.mul(dir, V.dot(pv, dir)));
  if (V.len(pv) < 1e-4) pv = [0, 0, -1];
  const bend = V.norm(pv);
  return { B: V.add(A, V.add(V.mul(dir, a), V.mul(bend, h))), C: Cc, bend, short: dist - dc };
}

// ------------------------------------------------------------------ 2D -> 3D retarget
const U = SKELETON_UNITS;   // model units per fighter unit (fighters export at scale 1)
const lenOf = (child) => V.len(SK[IDX[child]].p);
const ARM = { L1: lenOf("arm_lower_L"), L2: lenOf("hand_L") };
const LEG = { L1: lenOf("leg_lower_L"), L2: lenOf("ankle_L") };
const FOOT = lenOf("ball_L");
const bindBend = (a, b, c) => { const A = bw(a)[1], B = bw(b)[1], Cc = bw(c)[1]; const d = V.norm(V.sub(Cc, A)); let p = V.sub(B, A); p = V.sub(p, V.mul(d, V.dot(p, d))); return V.norm(p); };
const BIND = {
  armL: { A: "arm_upper_L", B: "arm_lower_L", C: "hand_L", bend: bindBend("arm_upper_L", "arm_lower_L", "hand_L") },
  armR: { A: "arm_upper_R", B: "arm_lower_R", C: "hand_R", bend: bindBend("arm_upper_R", "arm_lower_R", "hand_R") },
  legL: { A: "leg_upper_L", B: "leg_lower_L", C: "ankle_L", bend: bindBend("leg_upper_L", "leg_lower_L", "ankle_L") },
  legR: { A: "leg_upper_R", B: "leg_lower_R", C: "ankle_R", bend: bindBend("leg_upper_R", "leg_lower_R", "ankle_R") },
};

const ELBOW_OUT = 2.0;
const MAX_LIMB_TWIST = 75 * DEG;   // hips and shoulders turn about this far on their own axis
// the agent's foot slopes down from ankle to ball in its bind pose
const FOOT_PITCH = (() => { const v = V.sub(bw("ball_L")[1], bw("ankle_L")[1]); return M.axisAngle([0, 1, 0], Math.atan2(-v[2], Math.hypot(v[0], v[1]))); })();
const BIND_ANKLE_Z = bw("ankle_L")[1][2];

// joints: 2D points (fighter units) { P, N, H, S, fE, fW, fF, bE, bW, bF, fK, fA, fT, bK, bA, bT }
// opts: { rot: body tumble deg, spin: yaw deg, fist: 0..1 }
function retarget(J, opts = {}) {
  const rotBody = (opts.rot || 0) * DEG;
  // the 2D ankles sit nearly on the floor, but a CS2 ankle bone stands ~4 units up: lift the
  // body until the lower ankle is at that height (none in the air or when lying down)
  const lift = Math.max(0, BIND_ANKLE_Z - Math.min(J.fA.y, J.bA.y) * U) * Math.max(0, Math.cos(rotBody));
  const P3 = (j, lat = 0) => [J[j].x * U, lat, J[j].y * U + lift];
  const B = M.axisAngle([0, 1, 0], rotBody);
  const t = V.norm(V.sub(P3("N"), P3("P")));
  // total lean of the torso around the lateral axis, split into body tumble + torso lean
  const ang = (a, b) => Math.atan2(a[2] * b[0] - a[0] * b[2], a[0] * b[0] + a[2] * b[2]);
  const alpha = ang(bindTorsoAxis, t);
  const lean = alpha - rotBody;
  // guard lead: a boxer's stance turns the left (front) shoulder toward the opponent;
  // a long back-hand punch turns the right shoulder through instead
  const lead = (J.fW.x - J.bW.x);
  const twist0 = Math.max(-45, Math.min(45, 18 + 0.9 * lead)) * DEG;

  const build = (twist) => {
    const ov = [];
    const hipTwist = twist * 0.45;
    const spineRot = (w, tw) => M.mul(B, M.mul(M.axisAngle([0, 1, 0], lean * w), M.axisAngle(bindTorsoAxis, tw)));
    const pelvisR = spineRot(0.3, hipTwist);
    ov[IDX.pelvis] = { world: M.mul(pelvisR, bw("pelvis")[0]) };
    SPINE.forEach((n, k) => {
      const w = [0.45, 0.62, 0.8, 1.0][k];
      ov[IDX[n]] = { world: M.mul(spineRot(w, hipTwist + (twist - hipTwist) * (k + 1) / 4), bw(n)[0]) };
    });
    const hip = P3("P");
    const rootPos = V.sub(hip, M.apply(ov[IDX.pelvis].world, pelvisHipLocal));
    return { ov, rootPos };
  };
  // shoulders after the spine is posed; pick the twist that lets both hands reach their targets
  const reachCost = (twist) => {
    const { ov, rootPos } = build(twist);
    const W = solveFK(rootPos, ov);
    let cost = Math.abs(twist - twist0) * 0.5;
    for (const [side, w] of [["L", "fW"], ["R", "bW"]]) {
      const A = W[IDX["arm_upper_" + side]][1];
      const dx = J[w].x * U - A[0], dz = J[w].y * U + lift - A[2];
      cost += Math.max(0, Math.hypot(dx, dz) - (ARM.L1 + ARM.L2) * 0.995) * 4;
    }
    return cost;
  };
  let twist = twist0, best = reachCost(twist0);
  for (const d of [-10, 10, -20, 20, -30, 30, -45, 45]) {
    const tw = Math.max(-60, Math.min(60, twist0 / DEG + d)) * DEG;
    const c = reachCost(tw);
    if (c < best - 1e-6) { best = c; twist = tw; }
  }
  const { ov, rootPos } = build(twist);
  let W = solveFK(rootPos, ov);

  // neck and head follow the 2D head direction
  const hd = V.norm(V.sub(P3("H"), P3("N")));
  {
    const ni = IDX.neck_0, hi = IDX.head_0;
    const neckDir = V.norm(V.sub(W[hi][1], W[ni][1]));
    const q = alignVec(neckDir, hd);
    ov[ni] = { world: M.mul(halfRot(q), W[ni][0]) };
    W = solveFK(rootPos, ov);
    const headUp = M.apply(W[hi][0], [1, 0, 0]);
    ov[hi] = { world: M.mul(alignVec(headUp, hd), W[hi][0]) };
    W = solveFK(rootPos, ov);
  }

  // arms: hands to the 2D wrist positions, elbows through the 2D elbows
  const limb = (bind, Wpt, Ept, latTarget, latPole, lens) => {
    const ia = IDX[bind.A], ib = IDX[bind.B], ic = IDX[bind.C];
    const A = W[ia][1];
    const dxz = Math.hypot(J[Wpt].x * U - A[0], J[Wpt].y * U + lift - A[2]);
    const reach = (lens.L1 + lens.L2) * 0.995;
    let lat = latTarget;
    if (dxz < reach) { const maxDev = Math.sqrt(reach * reach - dxz * dxz); lat = A[1] + Math.max(-maxDev, Math.min(maxDev, lat - A[1])); }
    else lat = A[1];
    const Ct = [J[Wpt].x * U, lat, J[Wpt].y * U + lift];
    const pole = [J[Ept].x * U, latPole, J[Ept].y * U + lift];
    const s = ik(A, Ct, lens.L1, lens.L2, pole);
    const bB = bw(bind.B)[1], bC = bw(bind.C)[1], BA = bw(bind.A)[1];
    const u1 = V.norm(V.sub(s.B, A));
    // the bend plane through the elbow / knee only means something when the limb is bent:
    // a nearly straight limb takes the least-twisted orientation (carried with its parent),
    // otherwise its plane flips about and the limb wrings round (stretching the skin)
    const ip = SK[ia].pi;
    const carry = M.mul(W[ip][0], M.T(bw(SK[ip].name)[0]));        // parent's turn since bind
    const d0 = M.apply(carry, V.sub(bB, BA));
    const swing = M.mul(alignVec(d0, u1), M.mul(carry, bw(bind.A)[0]));
    const planed = M.mul(align(V.sub(bB, BA), bind.bend, V.sub(s.B, A), s.bend), bw(bind.A)[0]);
    const Tq = M.mul(planed, M.T(swing));
    let ref = V.cross(u1, Math.abs(u1[2]) < 0.9 ? [0, 0, 1] : [1, 0, 0]); ref = V.norm(ref);
    const tv = M.apply(Tq, ref);
    const theta = Math.atan2(V.dot(u1, V.cross(ref, tv)), V.dot(ref, tv));
    const bendAng = Math.acos(Math.max(-1, Math.min(1, V.dot(u1, V.norm(V.sub(s.C, s.B))))));
    const w = Math.max(0, Math.min(1, (bendAng / DEG - 8) / 27));
    // and never more than a joint can really turn on its own axis
    const tw = Math.max(-MAX_LIMB_TWIST, Math.min(MAX_LIMB_TWIST, theta * w * w * (3 - 2 * w)));
    const upper = M.mul(M.axisAngle(u1, tw), swing);
    ov[ia] = { world: upper };
    // lower bone: keep the bind elbow / knee relation under the upper bone, then aim it
    const rel = M.mul(upper, M.T(bw(bind.A)[0]));
    const lower0 = M.mul(rel, bw(bind.B)[0]);
    const ld0 = M.apply(rel, V.sub(bC, bB));
    ov[ib] = { world: M.mul(alignVec(ld0, V.sub(s.C, s.B)), lower0) };
    return s;
  };
  // a guard pulls the hands toward the centre line when they are up in front
  const armLen = (ARM.L1 + ARM.L2);
  const guardLat = (side, w) => {
    const sh = W[IDX["arm_upper_" + side]][1];
    const fwd = Math.max(0, Math.min(1, (J[w].x * U - sh[0]) / (armLen * 0.55)));
    const high = Math.max(0, Math.min(1, 1 - Math.abs(J[w].y * U + lift - (sh[2] - 4)) / (armLen * 0.9)));
    return sh[1] * (1 - 0.18 * fwd * high);
  };
  // elbows are pulled out wide of the body: CS2 agents wear bulky vests and gear
  limb(BIND.armL, "fW", "fE", guardLat("L", "fW"), W[IDX.arm_upper_L][1][1] * ELBOW_OUT, ARM);
  limb(BIND.armR, "bW", "bE", guardLat("R", "bW"), W[IDX.arm_upper_R][1][1] * ELBOW_OUT, ARM);
  W = solveFK(rootPos, ov);

  // legs: ankles at hip width plus a little, knees through the 2D knees
  const footLat = 4.9;
  limb(BIND.legL, "fA", "fK", footLat, footLat + 1.5, LEG);
  limb(BIND.legR, "bA", "bK", -footLat, -footLat - 1.5, LEG);
  W = solveFK(rootPos, ov);
  for (const [side, A2, T2, lat] of [["L", "fA", "fT", footLat], ["R", "bA", "bT", -footLat]]) {
    const ia = IDX["ankle_" + side];
    const ankle = W[ia][1];
    let dir = V.norm([J[T2].x - J[A2].x, 0, J[T2].y - J[A2].y]);
    dir = M.apply(FOOT_PITCH, dir);   // a flat 2D foot = the agent's foot as it stands in its bind pose
    dir = V.norm(V.add(dir, [0, side === "L" ? 0.18 : -0.18, 0]));   // toes turned out a little
    const bAim = V.sub(bw("ball_" + side)[1], bw("ankle_" + side)[1]);
    const delta = align(bAim, [0, 1, 0], dir, [0, 1, 0]);
    ov[ia] = { world: M.mul(delta, bw("ankle_" + side)[0]) };
  }
  // fists: each finger joint turns about its knuckle axis toward the palm
  const fist = opts.fist === undefined ? 1 : opts.fist;
  for (const side of ["L", "R"]) {
    const ax = CURL[side];
    for (const f of FINGERS) {
      [1.05, 1.45, 1.0].forEach((a, j) => {
        const n = `finger_${f}_${j}_${side}`;
        if (IDX[n] === undefined) return;
        const la = M.apply(M.T(bw(n)[0]), ax.axis);
        ov[IDX[n]] = { local: M.mul(SK[IDX[n]].R, M.axisAngle(la, a * fist)) };
      });
    }
    [0.5, 0.7].forEach((a, j) => {
      const n = `finger_thumb_${j + 1}_${side}`;
      if (IDX[n] === undefined) return;
      const la = M.apply(M.T(bw(n)[0]), ax.thumbAxis);
      ov[IDX[n]] = { local: M.mul(SK[IDX[n]].R, M.axisAngle(la, a * fist)) };
    });
  }
  W = solveFK(rootPos, ov);
  // twist bones: in game the agents' own rig spreads a limb's twist along it. Bone-merged
  // agents just copy our bones, so we do the same here, or the skin round hips and
  // shoulders wrings and stretches when a leg or arm turns on its own axis.
  for (const [limb, parent, bones] of TWIST_CHAINS) {
    const tw = twistOf(W, limb, parent);
    TWIST_STATS.max = Math.max(TWIST_STATS.max, Math.abs(tw) / DEG);
    if (TWIST_STATS.cur) { const k = limb; TWIST_STATS.cur[k] = Math.max(TWIST_STATS.cur[k] || 0, Math.abs(tw) / DEG); }
    for (const [bone, keep] of bones) {
      if (IDX[bone] === undefined) continue;
      ov[IDX[bone]] = { local: M.mul(SK[IDX[bone]].R, M.axisAngle([1, 0, 0], -(1 - keep) * tw)) };
    }
  }
  W = solveFK(rootPos, ov);
  // whole-body yaw (spin moves): rotate everything about the root
  if (opts.spin) {
    const Rz = M.axisAngle([0, 0, 1], opts.spin * DEG);
    W = W.map(([r, p], i) => i === 0 ? [r, p] : [M.mul(Rz, r), M.apply(Rz, p)]);
  }
  return W;
}
function alignVec(a, b) {
  const an = V.norm(a), bn = V.norm(b);
  const c = V.cross(an, bn), s = V.len(c), d = V.dot(an, bn);
  if (s < 1e-8) return M.I();
  return M.axisAngle(c, Math.atan2(s, d));
}
function halfRot(m) {
  // half of a rotation matrix's angle about the same axis
  const tr = m[0] + m[4] + m[8];
  const ang = Math.acos(Math.max(-1, Math.min(1, (tr - 1) / 2)));
  if (ang < 1e-6) return M.I();
  const ax = [m[7] - m[5], m[2] - m[6], m[3] - m[1]];
  return M.axisAngle(ax, ang / 2);
}
// [limb, its parent, [[twist bone, share of the limb's twist it keeps]]]
const TWIST_CHAINS = ["L", "R"].flatMap((sd) => [
  ["leg_upper_" + sd, "pelvis", [["leg_upper_" + sd + "_TWIST", 1 / 3], ["leg_upper_" + sd + "_TWIST1", 2 / 3]]],
  ["arm_upper_" + sd, "clavicle_" + sd, [["arm_upper_" + sd + "_TWIST", 1 / 3], ["arm_upper_" + sd + "_TWIST1", 2 / 3]]],
]);
const TWIST_STATS = { max: 0 };
// twist of a bone about its own (local X) axis, relative to its bind pose under its parent
function twistOf(W, bone, parent) {
  const L = M.mul(M.T(W[IDX[parent]][0]), W[IDX[bone]][0]);
  const B = SK[IDX[bone]].R;
  const sw = M.mul(alignVec(M.apply(B, [1, 0, 0]), M.apply(L, [1, 0, 0])), B);
  const T = M.mul(M.T(sw), L);
  return Math.atan2(T[7], T[8]);
}
function toLocals(W) {
  return SK.map((b, i) => {
    if (b.pi < 0) return [b.p, b.R];
    const [PR, PP] = W[b.pi];
    return [M.apply(M.T(PR), V.sub(W[i][1], PP)), M.mul(M.T(PR), W[i][0])];
  });
}

// ------------------------------------------------------------------ 2D poses from the core
const game = new Game({ halfWidth: 4000 });
const rigFighter = new Fighter(game, 0);
rigFighter.setCharacter(0);
// fighters export at scale 1 (geometry is the same for all, only scale differs)
function joints2D(ch, pose, mode = "normal") {
  const sk = C.makeSkeleton();
  const p = pose.slice();
  p[P_SC] = 1; p[P_FLIP] = 0;
  C.skeletonLocal(ch, p, sk, 0);
  let pelvisY = C.lerp(p[P_HY], -sk.minY, C.clamp(p[P_AUTO], 0, 1));
  const low = sk.minY + pelvisY;
  if (low < 0) pelvisY -= low;
  let ox = p[P_HX];
  if (mode === "thrown") { pelvisY = 0; ox = 0; }
  const J = {};
  for (const [k, v] of Object.entries(sk.pts)) J[k] = { x: ox + v.x, y: pelvisY + v.y };
  return { J, rot: p[P_ROT] };
}

const scale1 = (ch) => {
  const c = Object.assign({}, ch, { scale: 1, stats: Object.assign({}, ch.stats, { frame: 1 }) });
  c.dims = Object.assign({}, C.BASE_DIMS);
  c.legF = (c.dims.thigh + c.dims.shin) / 49; c.armF = (c.dims.uarm + c.dims.farm) / 31;
  c.poses = C.buildPoseSet(c);
  c.moves = C.buildMoveSet(c);
  return c;
};
const BASE = CHARACTERS.map(scale1);
const timber = BASE[0];

// clips: { name, fps, loop, frames: [{pose, spin, mode}] }
const clips = [];
function addClip(name, frames, { loop = false, fps = 64, fade = 0.06 } = {}) { clips.push({ name, frames, loop, fps, fade }); }

// moves, at base timing (the CS2 script plays them at 1/frame-multiplier speed)
// one clip per distinct clip name: shared normals once, styled normals per fighter,
// specials and combo finishers from their owner
const moveClips = new Map();
for (const ch of BASE) for (const id in ch.moves) { const mv = ch.moves[id]; if (!moveClips.has(mv.clip)) moveClips.set(mv.clip, ch); }
for (const [clipName, ch] of moveClips) {
  const mv = Object.values(ch.moves).find((m) => m.clip === clipName);
  const id = clipName;
  const frames = [];
  // a few held frames past the end, so the clip never runs out before the state changes
  for (let t = 0; t <= mv.total + 4; t++) {
    const pose = C.newPose();
    C.sampleKeys(mv.keys, t, pose, ch);
    let spin = 0;
    if (mv.flip) { const [a, b, per] = mv.flip; spin = t < a ? 0 : t > b ? 0 : 180 * (t - a) / per; if (t > b) spin = 0; }
    frames.push({ pose, spin });
  }
  addClip(id, frames, { fade: 0.05 });
}
// static and procedural states
const stat = (name, poseName, opts) => addClip(name, [{ pose: timber.poses[poseName] }, { pose: timber.poses[poseName] }], Object.assign({ loop: true, fade: 0.08 }, opts));
stat("crouch", "crouch"); stat("block", "block", { fade: 0.05 }); stat("cblock", "cblock", { fade: 0.05 });
stat("squat", "squat", { fade: 0.04 }); stat("air", "air", { fade: 0.12 }); stat("airrise", "airRise", { fade: 0.1 });
stat("land", "land", { fade: 0.04 }); stat("dashf", "dashF"); stat("dashb", "dashB");
stat("hithigh", "hitHigh", { fade: 0.03 }); stat("hitmid", "hitMid", { fade: 0.03 }); stat("hitcrouch", "hitCrouch", { fade: 0.03 });
stat("down", "down", { fade: 0.1 }); stat("downko", "downKO", { fade: 0.15 }); stat("defeat", "defeat", { fade: 0.25 });
const proc = (name, n, setup, opts) => {
  const f = new Fighter(game, 0); f.ch = timber; f.facing = 1;
  const frames = [];
  for (let i = 0; i < n; i++) { setup(f, i); const out = C.newPose(); f.targetPose(out); frames.push({ pose: out }); }
  addClip(name, frames, opts);
};
proc("idle", 96, (f, i) => { f.state = "idle"; f.idleT = i; }, { loop: true, fade: 0.1 });
proc("lobbyready", 52, (f, i) => { f.state = "lobby"; f.lobbyReady = true; f.idleT = Math.round(i * (2 * Math.PI / 0.12) / 52); }, { loop: true, fade: 0.15 });
proc("waiting", 79, (f, i) => { f.state = "waiting"; f.cheering = 0; f.idleT = i; }, { loop: true, fade: 0.2 });
proc("cheer", 21, (f, i) => { f.state = "waiting"; f.cheering = 10; f.idleT = i; }, { loop: true, fade: 0.1 });
// walk cycle: 32 frames = one full stride at 104 FU/s; the script scales playback by speed
for (const [name, dir] of [["walkf", 1], ["walkb", -1]]) {
  const f = new Fighter(game, 0); f.ch = timber; f.facing = 1; f.state = "walk"; f.walkPhase = 0; f.vx = 104 * dir;
  const frames = [];
  for (let i = 0; i < 32; i++) { const out = C.newPose(); f.targetPose(out); frames.push({ pose: out }); }
  addClip(name, frames, { loop: true, fade: 0.1 });
}
proc("launch", 21, (f, i) => { f.state = "launch"; f.sf = i; }, { fade: 0.04 });
proc("launchhold", 2, (f) => { f.state = "launch"; f.sf = 20; }, { loop: true, fade: 0.05 });
proc("getup", 19, (f, i) => { f.state = "getup"; f.sf = i; }, { fade: 0.06 });
for (const ch of BASE) {
  const f = new Fighter(game, 0); f.ch = ch; f.victoryPose = ch.victory;
  const frames = [];
  for (let i = 0; i < 42; i++) { f.state = "victory"; f.idleT = i; const out = C.newPose(); f.targetPose(out); frames.push({ pose: out }); }
  addClip("victory_" + ch.id, frames, { loop: true, fade: 0.3 });
}
// thrown victim: pelvis at the origin, rotation following the throw's victim keys
{
  const keys = timber.moves.throw.victim;
  const rel = timber.moves.throw.release;
  const frames = [];
  for (let t = 0; t <= rel; t++) {
    let a = keys[0], b = keys[keys.length - 1];
    for (let i = 1; i < keys.length; i++) if (t <= keys[i][0]) { a = keys[i - 1]; b = keys[i]; break; }
    const u = b[0] > a[0] ? C.smooth01((t - a[0]) / (b[0] - a[0])) : 1;
    const rot = C.lerp(a[3], b[3], u);
    const pose = C.resolvePose(Object.assign({}, C.POSES.thrown, { rot }), timber);
    frames.push({ pose, mode: "thrown" });
  }
  addClip("thrown", frames, { fade: 0.03 });
}

// ------------------------------------------------------------------ write
const fmt = (v) => (Math.abs(v) < 5e-7 ? 0 : v).toFixed(6);
function smdHeader() {
  let s = "version 1\nnodes\n";
  SK.forEach((b, i) => { s += `${i} "${b.name}" ${b.pi}\n`; });
  return s + "end\n";
}
// ModelDoc turns every SMD 90 degrees about Z on import (seen in the compiled props), so the
// root bone and the mesh are written turned -90 degrees to cancel it.
const IMPORT_FIX = [0, 1, 0, -1, 0, 0, 0, 0, 1];
function smdFrame(locals, time) {
  let s = `time ${time}\n`;
  locals.forEach(([p, r], i) => {
    if (SK[i].pi < 0) { p = M.apply(IMPORT_FIX, p); r = M.mul(IMPORT_FIX, r); }
    const e = toEuler(r); s += `${i} ${fmt(p[0])} ${fmt(p[1])} ${fmt(p[2])} ${fmt(e[0])} ${fmt(e[1])} ${fmt(e[2])}\n`;
  });
  return s;
}
const modelDir = path.join(outDir, "models", "puppet_brawl", "rig");
const animDir = path.join(modelDir, "anims");
fs.mkdirSync(animDir, { recursive: true });
// reference: bind pose plus one tiny dark triangle on every bone, hidden inside the agent's body.
// A bone with no geometry on it gets culled when the model compiles, and a mesh made only of
// tool materials is dropped, so each bone needs a real (if invisible) triangle.
{
  let s = smdHeader() + "skeleton\n" + smdFrame(SK.map((b) => [b.p, b.R]), 0) + "end\ntriangles\n";
  SK.forEach((b, bi) => {
    const pv = BW[bi][1];
    s += "pb_rig_dot\n";
    for (const d of [[0, 0, 0], [0.04, 0, 0], [0, 0.04, 0]]) {
      const q = M.apply(IMPORT_FIX, V.add(pv, d));
      s += `${bi} ${fmt(q[0])} ${fmt(q[1])} ${fmt(q[2])} 0 0 1 0 0 1 ${bi} 1\n`;
    }
  });
  s += "end\n";
  fs.writeFileSync(path.join(modelDir, "pb_rig_ref.smd"), s);
}
const preview = {};
let total = 0;
for (const clip of clips) {
  let s = smdHeader() + "skeleton\n";
  const pv = [];
  clip.frames.forEach((fr, t) => {
    const { J, rot } = joints2D(timber, fr.pose, fr.mode);
    const W = retarget(J, { rot, spin: fr.spin || 0 });
    s += smdFrame(toLocals(W), t);
    if (previewPath) pv.push({ J, W: W.map(([r, p]) => p) });
  });
  s += "end\n";
  if (process.env.TWIST_DEBUG) { console.log(clip.name.padEnd(18), Object.entries(TWIST_STATS.cur || {}).map(([k, v]) => k + ":" + v.toFixed(0)).join(" ")); }
  TWIST_STATS.cur = {};
  fs.writeFileSync(path.join(animDir, clip.name + ".smd"), s);
  total += s.length;
  if (previewPath) preview[clip.name] = pv;
}
// ModelDoc file
const animNode = (c) => `\t\t\t\t\t{
\t\t\t\t\t\t_class = "AnimFile"
\t\t\t\t\t\tname = "${c.name}"
\t\t\t\t\t\tis_default_idle_anim = ${c.name === "idle" ? "true" : "false"}
\t\t\t\t\t\tactivity_name = ""
\t\t\t\t\t\tactivity_weight = 1
\t\t\t\t\t\tweight_list_name = ""
\t\t\t\t\t\tfade_in_time = ${c.fade}
\t\t\t\t\t\tfade_out_time = ${c.fade}
\t\t\t\t\t\tlooping = ${c.loop ? "true" : "false"}
\t\t\t\t\t\tdelta = false
\t\t\t\t\t\tworldSpace = false
\t\t\t\t\t\thidden = false
\t\t\t\t\t\tanim_markup_ordered = false
\t\t\t\t\t\tdisable_compression = false
\t\t\t\t\t\tanimgraph_additive = false
\t\t\t\t\t\tdelete_from_compiled_model = false
\t\t\t\t\t\tsource_filename = "models/puppet_brawl/rig/anims/${c.name}.smd"
\t\t\t\t\t\timport_bone_scales = false
\t\t\t\t\t\tstart_frame = -1
\t\t\t\t\t\tend_frame = -1
\t\t\t\t\t\tframerate = ${c.fps.toFixed(1)}
\t\t\t\t\t\treverse = false
\t\t\t\t\t\tadditional_anim_files = [  ]
\t\t\t\t\t},`;
const vmdl = `<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:modeldoc41:version{12fc9d44-453a-4ae4-b4d9-7e2ac0bbd4e0} -->
{
\trootNode =
\t{
\t\t_class = "RootNode"
\t\tchildren =
\t\t[
\t\t\t{
\t\t\t\t_class = "MaterialGroupList"
\t\t\t\tchildren =
\t\t\t\t[
\t\t\t\t\t{
\t\t\t\t\t\t_class = "DefaultMaterialGroup"
\t\t\t\t\t\tremaps =
\t\t\t\t\t\t[
\t\t\t\t\t\t\t{
\t\t\t\t\t\t\t\tfrom = "pb_rig_dot.vmat"
\t\t\t\t\t\t\t\tto = "materials/puppet_brawl/props/pb_dark.vmat"
\t\t\t\t\t\t\t},
\t\t\t\t\t\t]
\t\t\t\t\t\tuse_global_default = false
\t\t\t\t\t\tglobal_default_material = ""
\t\t\t\t\t},
\t\t\t\t]
\t\t\t},
\t\t\t{
\t\t\t\t_class = "BoneMarkupList"
\t\t\t\tbone_cull_type = "None"
\t\t\t},
\t\t\t{
\t\t\t\t_class = "RenderMeshList"
\t\t\t\tchildren =
\t\t\t\t[
\t\t\t\t\t{
\t\t\t\t\t\t_class = "RenderMeshFile"
\t\t\t\t\t\tname = "pb_rig_ref"
\t\t\t\t\t\tfilename = "models/puppet_brawl/rig/pb_rig_ref.smd"
\t\t\t\t\t\timport_scale = 1.0
\t\t\t\t\t\timport_filter =
\t\t\t\t\t\t{
\t\t\t\t\t\t\texclude_by_default = false
\t\t\t\t\t\t\texception_list = [  ]
\t\t\t\t\t\t}
\t\t\t\t\t},
\t\t\t\t]
\t\t\t},
\t\t\t{
\t\t\t\t_class = "AnimationList"
\t\t\t\tchildren =
\t\t\t\t[
${clips.map(animNode).join("\n")}
\t\t\t\t]
\t\t\t\tdefault_root_bone_name = ""
\t\t\t},
\t\t]
\t\tmodel_archetype = ""
\t\tprimary_associated_entity = ""
\t\tanim_graph_name = ""
\t\tbase_model_name = ""
\t}
}
`;
fs.writeFileSync(path.join(modelDir, "pb_rig.vmdl"), vmdl);
// clip table for the CS2 script (frame counts at 64 fps)
const table = Object.fromEntries(clips.map((c) => [c.name, { frames: c.frames.length, loop: c.loop }]));
fs.writeFileSync(path.join(here, "..", "dist", "rig_clips.json"), JSON.stringify(table));
if (previewPath) fs.writeFileSync(previewPath, JSON.stringify({ bones: SK.map((b) => ({ name: b.name, pi: b.pi })), clips: preview }));
console.log(`${clips.length} clips, ${(total / 1e6).toFixed(1)} MB of SMD -> ${modelDir}  (largest limb twist ${TWIST_STATS.max.toFixed(0)} deg, spread over the twist bones)`);
