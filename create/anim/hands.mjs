// Hand shapes: a real fist (fingers rolled into the palm, thumb wrapped over the front of the
// index and middle fingers), a relaxed hand, an open hand and a flat chop. Curls are applied
// about each hand's knuckle line, so they follow the hand wherever the arm puts it.
//   shapeHand(W, "R", "fist");  shapeHand(W, "L", ["relaxed", "fist", 0.5]);   // or a shape object
// Uses the CS2 agent finger bone names (finger_<index|middle|ring|pinky>_<meta|0|1|2>_<L|R>, thumb_0..2).
// From cs2-fighter/tools/anim/hands.mjs (MIT), made project-neutral.
import { q, v3 } from "./m3.mjs";
import { SK, IDX, BIND, setWorld } from "./rig.mjs";

const FINGERS = ["index", "middle", "ring", "pinky"];
// per side: knuckle axis (curl toward the palm is a positive turn about it) and palm normal
const AX = {};
for (const s of ["L", "R"]) {
  const p = (n) => BIND[IDX[`${n}_${s}`]].p;
  const f = v3.norm(v3.sub(p("finger_middle_1"), p("finger_middle_0")));
  const k = v3.norm(v3.sub(p("finger_pinky_0"), p("finger_index_0")));
  let n = v3.norm(v3.cross(f, k));
  if (v3.dot(n, v3.sub(p("finger_thumb_2"), p("finger_middle_0"))) < 0) n = v3.mul(n, -1);
  AX[s] = { curl: v3.norm(v3.cross(f, n)), palm: n, along: f, across: k };
}

export const SHAPES = {
  //        mcp   pip   dip   meta(index..pinky)        spread thumb: [cmc swing to palm, cmc roll, mcp, ip]
  fist:    { j: [1.55, 1.90, 1.15], meta: [0, 0.05, 0.12, 0.2], spread: 0, thumb: [0.95, 0.55, 0.55, 0.45], wrap: 1 },
  tight:   { j: [1.62, 1.95, 1.20], meta: [0, 0.06, 0.14, 0.24], spread: 0, thumb: [1.05, 0.6, 0.6, 0.5], wrap: 1 },
  relaxed: { j: [0.40, 0.65, 0.35], meta: [0, 0.03, 0.06, 0.1], spread: 0.03, thumb: [0.35, 0.2, 0.2, 0.2] },
  open:    { j: [0.12, 0.18, 0.10], meta: [0, 0, 0.03, 0.05], spread: 0.12, thumb: [0.1, 0.1, 0.1, 0.1] },
  chop:    { j: [0.05, 0.06, 0.04], meta: [0, 0, 0, 0], spread: 0, thumb: [0.55, 0.3, 0.2, 0.1] },
  claw:    { j: [0.7, 1.2, 0.9], meta: [0, 0.04, 0.08, 0.12], spread: 0.1, thumb: [0.5, 0.3, 0.4, 0.3] },
};
const lerpShape = (a, b, t) => ({
  j: a.j.map((x, i) => x + (b.j[i] - x) * t), meta: a.meta.map((x, i) => x + (b.meta[i] - x) * t),
  spread: a.spread + (b.spread - a.spread) * t, thumb: a.thumb.map((x, i) => x + (b.thumb[i] - x) * t),
  wrap: (a.wrap || 0) + ((b.wrap || 0) - (a.wrap || 0)) * t,
});
// shape: a name, a shape object, or [nameA, nameB, t]
export function resolveShape(shape) {
  if (typeof shape === "string") return SHAPES[shape];
  if (Array.isArray(shape)) return lerpShape(resolveShape(shape[0]), resolveShape(shape[1]), shape[2]);
  return shape;
}

function setLocalRot(W, i, extraWorldAxisAngles) {
  // local = bindLocal * R(axes expressed in the bone's bind frame)
  const b = SK[i];
  let lq = b.local.q;
  for (const [axis, ang] of extraWorldAxisAngles) lq = q.mul(lq, q.axisAngle(q.rotate(q.conj(BIND[i].q), axis), ang));
  const P = W[b.pi];
  setWorld(W, i, { q: q.mul(P.q, lq), p: v3.add(P.p, q.rotate(P.q, b.local.p)) });
}

export function shapeHand(W, s, shape) {
  const S = resolveShape(shape);
  const A = AX[s];
  FINGERS.forEach((f, fi) => {
    const sp = (fi - 1.5) * S.spread;   // index and pinky fan out
    const meta = IDX[`finger_${f}_meta_${s}`];
    if (meta !== undefined) setLocalRot(W, meta, [[A.curl, S.meta[fi]]]);
    for (let j = 0; j < 3; j++) {
      const i = IDX[`finger_${f}_${j}_${s}`];
      if (i === undefined) continue;
      const rots = [[A.curl, S.j[j] * (1 + (fi - 1) * 0.04)]];
      if (j === 0 && sp) rots.unshift([A.palm, sp * (s === "L" ? 1 : -1)]);
      setLocalRot(W, i, rots);
    }
  });
  // thumb: a fitted wrap for fists (see fitThumb), else swing/roll/flex from the shape
  const t0 = IDX[`finger_thumb_0_${s}`], t1 = IDX[`finger_thumb_1_${s}`], t2 = IDX[`finger_thumb_2_${s}`];
  let th = S.thumb;
  if (S.wrap) { const fit = fitThumb(s); th = th.map((x, i) => x + (fit[i] - x) * S.wrap); }
  applyThumb(W, s, th);
  return W;
}
function applyThumb(W, s, [sw, roll, mcp, ip]) {
  const A = AX[s];
  const t0 = IDX[`finger_thumb_0_${s}`], t1 = IDX[`finger_thumb_1_${s}`], t2 = IDX[`finger_thumb_2_${s}`];
  const thumbAlong = v3.norm(v3.sub(BIND[t2].p, BIND[t1].p));
  const thumbCurl = v3.norm(v3.cross(thumbAlong, A.palm));
  const sg = s === "L" ? 1 : -1;
  setLocalRot(W, t0, [[A.along, sw * sg], [A.palm, roll * sg]]);
  setLocalRot(W, t1, [[thumbCurl, mcp]]);
  setLocalRot(W, t2, [[thumbCurl, ip]]);
}
// Thumb angles that lay the thumb pad across the middle phalanges of the curled index and
// middle fingers, found once per side by search on the bind hand.
const THUMB_FIT = {};
function fitThumb(s) {
  if (THUMB_FIT[s]) return THUMB_FIT[s];
  const W = SK.map((b, i) => ({ q: BIND[i].q.slice(), p: BIND[i].p.slice() }));
  const base = { ...SHAPES.tight, wrap: 0 };
  shapeHand(W, s, base);
  const P = (n) => W[IDX[`${n}_${s}`]].p;
  const hand = P("hand");
  const mids = [P("finger_index_1"), P("finger_index_2"), P("finger_middle_1"), P("finger_middle_2")];
  // the thumb lies across the front of the curled index and middle fingers: its last joint by
  // the side of the index's middle phalanx, its tip over the middle finger's middle phalanx
  const across = v3.norm(v3.sub(P("finger_pinky_0"), P("finger_index_0")));
  const front = v3.norm(v3.sub(v3.lerp(P("finger_index_1"), P("finger_middle_1"), 0.5), v3.lerp(hand, P("finger_middle_0"), 0.5)));
  const goalJoint = v3.add(v3.lerp(P("finger_index_1"), P("finger_index_2"), 0.5), v3.add(v3.mul(across, -1.0), v3.mul(front, 0.5)));
  const goalTip = v3.add(v3.lerp(P("finger_middle_1"), P("finger_middle_2"), 0.5), v3.mul(front, 0.9));
  const t2i = IDX[`finger_thumb_2_${s}`];
  const len2 = v3.dist(BIND[t2i].p, BIND[IDX[`finger_thumb_1_${s}`]].p) * 0.85;
  let best = null;
  for (let sw = -1.6; sw <= 1.6001; sw += 0.1) for (let roll = -1.6; roll <= 1.6001; roll += 0.1)
    for (let mcp = -0.3; mcp <= 1.2001; mcp += 0.15) for (let ip = 0; ip <= 1.2001; ip += 0.15) {
      applyThumb(W, s, [sw, roll, mcp, ip]);
      const t2 = W[t2i];
      const tip = v3.add(t2.p, q.rotate(t2.q, [len2, 0, 0]));
      let cost = v3.dist(t2.p, goalJoint) + v3.dist(tip, goalTip) + 0.03 * (Math.abs(sw) + Math.abs(roll));
      for (const f of mids) { const d = Math.min(v3.dist(f, t2.p), v3.dist(f, tip)); if (d < 0.9) cost += (0.9 - d) * 3; }
      if (!best || cost < best.cost) best = { cost, a: [sw, roll, mcp, ip] };
    }
  THUMB_FIT[s] = best.a;
  return best.a;
}

