// Pose finishing passes and IK on rig poses (arrays of world {q, p}).
//  - twist bones: spread limb twist along the agent's TWIST bones (the bone-merged agent copies
//    them from our rig, so leaving them at bind makes skin wring at shoulders, wrists and neck)
//  - fists: curl the fingers (0 open .. 1 fist), per hand
//  - two-bone IK for arms and legs: hinge knees/elbows (ik2), free IK with CS2_FREE_IK=1
//  - armsOutOfBody (hands/elbows pushed out of head and torso), limitHips (airborne thigh flex)
// All work in place on a pose: e.g. ik2(W, ...LEG.L, [x, y, z]); spreadTwist(W).
// Numbers are for the CS2 agent at model scale 1 (KNEE_FLOOR, HEAD_R, TORSO_R, HIP_FLEX_MAX).
// From cs2-fighter/tools/anim/post.mjs (MIT), made project-neutral.
import { q, v3, clamp } from "./m3.mjs";
import { SK, IDX, BIND, setWorldRot, setWorld } from "./rig.mjs";

const local = (W, i) => q.mul(q.conj(W[SK[i].pi].q), W[i].q);
const bindLocalQ = (i) => SK[i].local.q;

// twist of bone i about its own X axis, relative to its parent (beyond its bind relation)
function twistAbout(W, i) {
  const rel = q.mul(q.conj(bindLocalQ(i)), local(W, i));   // rotation since bind, in bone-local space
  return q.twistAngle(q.norm(rel), [1, 0, 0]);
}
// world rotation of a twist bone that sits under `parent` with its bind local, turned about X
function placeTwist(W, ti, angle) {
  const pi = SK[ti].pi;
  const lq = q.mul(bindLocalQ(ti), q.axisAngle([1, 0, 0], angle));
  W[ti] = { q: q.norm(q.mul(W[pi].q, lq)), p: v3.add(W[pi].p, q.rotate(W[pi].q, SK[ti].local.p)) };
}

export function spreadTwist(W) {
  for (const s of ["L", "R"]) {
    // upper arm: its twist under the clavicle is carried 1/3 and 2/3 of the way by the TWIST bones
    const ua = IDX["arm_upper_" + s];
    const tw = twistAbout(W, ua);
    placeTwist(W, IDX[`arm_upper_${s}_TWIST`], -(2 / 3) * tw);
    placeTwist(W, IDX[`arm_upper_${s}_TWIST1`], -(1 / 3) * tw);
    // forearm: the hand's roll about the forearm is carried 1/3 and 2/3 down the forearm
    const hand = IDX["hand_" + s];
    const roll = twistAbout(W, hand);
    placeTwist(W, IDX[`arm_lower_${s}_TWIST`], (1 / 3) * roll);
    placeTwist(W, IDX[`arm_lower_${s}_TWIST1`], (2 / 3) * roll);
    // thigh
    const ul = IDX["leg_upper_" + s];
    const lt = twistAbout(W, ul);
    placeTwist(W, IDX[`leg_upper_${s}_TWIST`], -(2 / 3) * lt);
    placeTwist(W, IDX[`leg_upper_${s}_TWIST1`], -(1 / 3) * lt);
  }
  // neck: head_0_TWIST (under neck_0) takes half the head's turn relative to the neck
  const hi = IDX.head_0, nt = IDX.head_0_TWIST;
  const rel = q.mul(q.conj(bindLocalQ(hi)), local(W, hi));
  const half = q.slerp([0, 0, 0, 1], rel, 0.5);
  const pi = SK[nt].pi;
  W[nt] = { q: q.norm(q.mul(W[pi].q, q.mul(bindLocalQ(nt), half))), p: v3.add(W[pi].p, q.rotate(W[pi].q, SK[nt].local.p)) };
  return W;
}

// ------------------------------------------------------------------ fingers
const FINGERS = ["index", "middle", "ring", "pinky"];
const CURL = {};
for (const side of ["L", "R"]) {
  const p = (n) => BIND[IDX[n + "_" + side]].p;
  const f = v3.norm(v3.sub(p("finger_middle_1"), p("finger_middle_0")));
  const k = v3.norm(v3.sub(p("finger_pinky_0"), p("finger_index_0")));
  let n = v3.norm(v3.cross(f, k));
  if (v3.dot(n, v3.sub(p("finger_thumb_2"), p("finger_middle_0"))) < 0) n = v3.mul(n, -1);
  const tf = v3.norm(v3.sub(p("finger_thumb_2"), p("finger_thumb_1")));
  CURL[side] = { axis: v3.norm(v3.cross(f, n)), thumbAxis: v3.norm(v3.cross(tf, n)) };
}
// fist: 0 = open relaxed hand, 1 = tight fist. spread: open fingers apart (flat hand)
export function curlFingers(W, side, fist = 1, { thumb = null } = {}) {
  const ax = CURL[side];
  const chain = [];
  for (const f of FINGERS) [0, 1, 2].forEach((j) => chain.push([`finger_${f}_${j}_${side}`, [1.05, 1.45, 1.0][j] * fist + 0.12 * (1 - fist)]));
  const th = thumb === null ? fist : thumb;
  [1, 2].forEach((j) => chain.push([`finger_thumb_${j}_${side}`, [0.5, 0.7][j - 1] * th, true]));
  for (const [name, ang, isThumb] of chain) {
    const i = IDX[name];
    if (i === undefined) continue;
    const bindW = BIND[i].q;
    const la = q.rotate(q.conj(bindW), isThumb ? ax.thumbAxis : ax.axis);
    const lq = q.mul(bindLocalQ(i), q.axisAngle(la, ang));
    const pi = SK[i].pi;
    setWorld(W, i, { q: q.mul(W[pi].q, lq), p: v3.add(W[pi].p, q.rotate(W[pi].q, SK[i].local.p)) });
  }
  return W;
}

// ------------------------------------------------------------------ two-bone IK
// Moves the end of a chain (e.g. ankle) to `target`. The bend keeps its current plane unless a
// `pole` point is given. Descendants keep their local transforms; `keepEnd` keeps the end bone's
// world rotation (feet stay flat, fists keep their angle).
// ---------------------------------------------------------------- hinge IK
// Knees and elbows are hinges: the lower bone only turns about one axis of the upper bone. The
// axis comes from the bind pose (arms: the bind's slight elbow bend; legs: the hips' left-right
// axis), stored in the upper bone's own frame. The IK places the middle joint (toward the pole, or
// keeping the current bend direction), turns the upper bone so its hinge axis is square to the
// limb's plane, then bends the lower bone about that axis only, so the skin folds the way the
// joint does, never sideways or backwards.
export const HINGE_LOCAL = {};
export const KNEE_FLOOR = 3.2;   // knee joint height when kneeling on it
const BONE_AXIS = {};
function initHinge(upper, middle, end, worldAxis) {
  const A = IDX[upper], B = IDX[middle], C = IDX[end];
  const u = v3.norm(v3.sub(BIND[B].p, BIND[A].p)), l = v3.norm(v3.sub(BIND[C].p, BIND[B].p));
  let n = worldAxis ? v3.perp(worldAxis, u) : v3.cross(u, l);
  n = v3.norm(n);
  HINGE_LOCAL[upper] = q.rotate(q.conj(BIND[A].q), n);
  BONE_AXIS[upper] = q.rotate(q.conj(BIND[A].q), u);
  BONE_AXIS[middle] = q.rotate(q.conj(BIND[B].q), l);
}
for (const s of ["L", "R"]) {
  initHinge(`leg_upper_${s}`, `leg_lower_${s}`, `ankle_${s}`, [0, 1, 0]);
  initHinge(`arm_upper_${s}`, `arm_lower_${s}`, `hand_${s}`, null);
}
function basis(f, u) {
  const x = v3.norm(f), z = v3.norm(v3.cross(x, u)), y = v3.cross(z, x);
  return q.fromBasis(x, y, z);
}
export function ik2(W, upper, middle, end, target, opts = {}) {
  if (HINGE_LOCAL[upper] && !process.env.CS2_FREE_IK) return ik2Hinge(W, upper, middle, end, target, opts);
  return ik2Free(W, upper, middle, end, target, opts);
}
function ik2Hinge(W, upper, middle, end, target, { pole = null, keepEnd = true, soft = 0.995 } = {}) {
  const A = IDX[upper], B = IDX[middle], C = IDX[end];
  const endRot = W[C].q;
  const a = W[A].p;
  const l1 = v3.dist(W[A].p, W[B].p), l2 = v3.dist(W[B].p, W[C].p);
  const toT = v3.sub(target, a);
  const tl = v3.len(toT);
  const dist = clamp(tl, Math.abs(l1 - l2) + 1e-3, (l1 + l2) * soft);
  const axis = tl > 1e-6 ? v3.mul(toT, 1 / tl) : v3.norm(v3.sub(W[C].p, a));
  // which way the middle joint goes (perpendicular to the limb axis)
  let pv = pole ? v3.perp(v3.sub(pole, a), axis) : [0, 0, 0];
  if (v3.len(pv) < 1e-3) pv = v3.perp(v3.sub(W[B].p, a), axis);
  if (v3.len(pv) < 0.05 * l1) {
    // straight limb and no pole: the side the hinge already bends toward
    const H = q.rotate(W[A].q, HINGE_LOCAL[upper]);
    pv = v3.cross(axis, H);
  }
  pv = v3.norm(pv);
  const cosA = clamp((l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist), -1, 1);
  const sinA = Math.sqrt(1 - cosA * cosA);
  // a knee never goes through the floor: turn it about the limb axis (out to the side) until clear
  if (upper.startsWith("leg_") && sinA > 0.05) {
    const kz = (v) => a[2] + axis[2] * l1 * cosA + v[2] * l1 * sinA;
    if (kz(pv) < KNEE_FLOOR) {
      const side = v3.cross(axis, pv);
      let best = null;
      for (let d = 2; d <= 180 && !best; d += 2) {
        for (const sg of [1, -1]) {
          const t = sg * d * Math.PI / 180;
          const v = v3.add(v3.mul(pv, Math.cos(t)), v3.mul(side, Math.sin(t)));
          if (kz(v) >= KNEE_FLOOR) { best = v; break; }
        }
      }
      if (best) pv = v3.norm(best);
    }
  }
  const knee = v3.add(a, v3.add(v3.mul(axis, l1 * cosA), v3.mul(pv, l1 * sinA)));
  const tip = v3.add(a, v3.mul(axis, dist));
  const d1 = v3.norm(v3.sub(knee, a)), d2 = v3.norm(v3.sub(tip, knee));
  const n = v3.norm(v3.cross(pv, axis));
  // upper bone: bone axis along d1, hinge axis along n
  const Qu = q.mul(basis(d1, n), q.conj(basis(BONE_AXIS[upper], HINGE_LOCAL[upper])));
  setWorldRot(W, A, Qu);
  // lower bone: its bind relation to the upper bone, then bent about the hinge
  const rel0 = q.mul(q.conj(BIND[A].q), BIND[B].q);
  let Ql = q.mul(Qu, rel0);
  const now = q.rotate(Ql, BONE_AXIS[middle]);
  const ang = Math.atan2(v3.dot(v3.cross(now, d2), n), v3.dot(now, d2));
  Ql = q.mul(q.axisAngle(n, ang), Ql);
  setWorldRot(W, B, Ql);
  if (keepEnd) setWorldRot(W, C, endRot);
  return dist - tl;
}
function ik2Free(W, upper, middle, end, target, { pole = null, keepEnd = true, soft = 0.995 } = {}) {
  const A = IDX[upper], B = IDX[middle], C = IDX[end];
  const endRot = W[C].q;
  const a = W[A].p, b = W[B].p, c = W[C].p;
  const l1 = v3.dist(a, b), l2 = v3.dist(b, c);
  let toT = v3.sub(target, a);
  const dist = clamp(v3.len(toT), Math.abs(l1 - l2) + 1e-3, (l1 + l2) * soft);
  // bend plane normal
  let n = v3.cross(v3.sub(b, a), v3.sub(c, b));
  if (pole) {
    const axis = v3.norm(toT);
    const pv = v3.perp(v3.sub(pole, a), axis);
    if (v3.len(pv) > 1e-4) n = v3.cross(axis, v3.norm(pv));   // knee/elbow toward the pole
  }
  if (v3.len(n) < 1e-6) n = v3.cross(v3.sub(b, a), [0, 0, 1]);
  n = v3.norm(n);
  // 1) set the middle angle: angle between upper and lower so |c - a| = dist
  const cosB = clamp((l1 * l1 + l2 * l2 - dist * dist) / (2 * l1 * l2), -1, 1);
  const wantInterior = Math.acos(cosB);   // angle at the middle joint between the two bones
  const u1 = v3.norm(v3.sub(b, a)), u2 = v3.norm(v3.sub(c, b));
  const curInterior = Math.acos(clamp(v3.dot(v3.mul(u1, -1), u2), -1, 1));
  // rotate the lower bone about n (sign chosen so the interior angle grows toward the wanted one)
  const bendNow = v3.dot(v3.cross(u1, u2), n) >= 0 ? 1 : -1;
  const delta = (curInterior - wantInterior) * bendNow;
  if (Math.abs(delta) > 1e-6) setWorldRot(W, B, q.mul(q.axisAngle(n, delta), W[B].q));
  // 2) swing the upper bone so the end lands on the target direction
  const c2 = W[C].p;
  const sw = q.between(v3.sub(c2, a), v3.norm(toT));
  setWorldRot(W, A, q.mul(sw, W[A].q));
  // 3) pole: rotate the whole chain about a->target so the middle joint faces the pole
  if (pole) {
    const axis = v3.norm(toT);
    const mid = v3.perp(v3.sub(W[B].p, a), axis), pv = v3.perp(v3.sub(pole, a), axis);
    if (v3.len(mid) > 1e-4 && v3.len(pv) > 1e-4) {
      const ang = Math.atan2(v3.dot(v3.cross(v3.norm(mid), v3.norm(pv)), axis), v3.dot(v3.norm(mid), v3.norm(pv)));
      setWorldRot(W, A, q.mul(q.axisAngle(axis, ang), W[A].q));
    }
  }
  if (keepEnd) setWorldRot(W, C, endRot);
  return dist - v3.len(toT);   // 0 when reached; negative when stretched out of reach
}

export const LEG = { L: ["leg_upper_L", "leg_lower_L", "ankle_L"], R: ["leg_upper_R", "leg_lower_R", "ankle_R"] };
export const ARM = { L: ["arm_upper_L", "arm_lower_L", "hand_L"], R: ["arm_upper_R", "arm_lower_R", "hand_R"] };

// ---------------------------------------------------------------- arms out of the body
// Hands, elbows and forearms that end up inside the head or the torso are pushed back out to
// the surface (plus a margin) and the arm is re-solved with the elbow kept on its side; the hand
// keeps its set on the forearm.
export const HEAD_R = 7.2, TORSO_R = 7.0;
function closestOnSeg(p, a, b) {
  const ab = v3.sub(b, a), t = clamp(v3.dot(v3.sub(p, a), ab) / Math.max(1e-6, v3.dot(ab, ab)), 0, 1);
  return v3.add(a, v3.mul(ab, t));
}
function pushOut(p, W) {
  // head sphere and torso capsule; returns the corrected point or null when clear
  const hc = v3.add(W[IDX.head_0].p, q.rotate(W[IDX.head_0].q, [3.5, 0, 0]));
  let out = null, cur = p;
  for (let it = 0; it < 2; it++) {
    const dh = v3.sub(cur, hc), lh = v3.len(dh);
    if (lh < HEAD_R) { cur = v3.add(hc, v3.mul(lh > 1e-3 ? v3.norm(dh) : [0, -1, 0], HEAD_R)); out = cur; }
    const c = closestOnSeg(cur, W[IDX.spine_1].p, W[IDX.spine_3].p);
    const dt = v3.sub(cur, c), lt = v3.len(dt);
    if (lt < TORSO_R) { cur = v3.add(c, v3.mul(lt > 1e-3 ? v3.norm(dt) : [1, 0, 0], TORSO_R)); out = cur; }
  }
  return out;
}
export function armsOutOfBody(W) {
  for (const s of ["L", "R"]) {
    const [ua, la, ha] = ARM[s].map((n) => IDX[n]);
    for (let pass = 0; pass < 3; pass++) {
      const hand = W[ha].p, elbow = W[la].p;
      const mid = v3.mul(v3.add(hand, elbow), 0.5);
      const nh = pushOut(hand, W), ne = pushOut(elbow, W), nm = pushOut(mid, W);
      if (!nh && !ne && !nm) break;
      let target = nh || hand;
      if (nm && !nh) target = v3.add(hand, v3.sub(nm, mid));
      if (ne && !nh) target = v3.add(target, v3.mul(v3.sub(ne, elbow), 0.8));
      const pole = v3.add(ne || elbow, v3.mul(v3.sub(ne || elbow, W[ua].p), 0.5));
      const rel = q.mul(q.conj(W[la].q), W[ha].q);
      ik2(W, ...ARM[s], target, { pole, keepEnd: false });
      setWorldRot(W, ha, q.mul(W[la].q, rel));
    }
  }
  return W;
}

// ---------------------------------------------------------------- hips
// A leg in the air never swings up into the torso: thigh flexion against the hips is held to
// HIP_FLEX_MAX, the whole leg turned down about the hips' left-right axis (the foot keeps its set
// on the shin). Planted feet are left alone.
export const HIP_FLEX_MAX = 148;
export function limitHips(W) {
  const pq = W[IDX.pelvis].q, bq = q.conj(BIND[IDX.pelvis].q);
  const fwd = q.rotate(pq, q.rotate(bq, [1, 0, 0])), up = q.rotate(pq, q.rotate(bq, [0, 0, 1])), left = q.rotate(pq, q.rotate(bq, [0, 1, 0]));
  for (const s of ["L", "R"]) {
    if (W[IDX["ankle_" + s]].p[2] < 8) continue;
    const ti = IDX["leg_upper_" + s];
    const dir = v3.norm(v3.sub(W[IDX["leg_lower_" + s]].p, W[ti].p));
    const a = v3.dot(dir, fwd), b = -v3.dot(dir, up);
    if (Math.hypot(a, b) < 0.5) continue;
    const flex = Math.atan2(a, b) * 180 / Math.PI;
    if (flex <= HIP_FLEX_MAX) continue;
    setWorldRot(W, ti, q.mul(q.axisAngle(left, (flex - HIP_FLEX_MAX) * Math.PI / 180), W[ti].q));
  }
  return W;
}
