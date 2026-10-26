// Posture: builds a full-body pose from a compact spec, starting from the agent's bind pose,
// and keyed postures (sampleSpecs: specs at key frames -> one spec per frame on smooth curves).
//   const W = posture(spec);   const specs = sampleSpecs([[0, specA], [20, specB]], 21);
// From cs2-fighter/tools/anim/posture.mjs (MIT), made project-neutral.
// Model space: the body faces +X, +Y is its left, +Z up. Angles in degrees.
//   pelvis: { p: [x, y, z], yaw, pitch, roll, spin }
//   chest:  { yaw, pitch, side }                    relative to the pelvis, spread up the spine
//   look:   [x, y, z]                               where the eyes go
//   feet:   { L|R: { p: [x, y], z, yaw, heel, roll, knee } }   knee = pole point (optional)
//   hands:  { L|R: { p: [x, y, z], elbow: [x, y, z], palm: [x, y, z], bend } }
//           palm = the direction the palm faces; the wrist stays straight unless bend (deg)
//   shape:  { L, R } hand shapes for hands.mjs
import { q, v3, DEG, monotoneSlopes, hermiteMap } from "./m3.mjs";
import { IDX, BIND, bindPose, setWorld, setWorldRot } from "./rig.mjs";
import { bendSpine, twistSpine, lookAt, placeFoot, footOnShin, BIND_ANKLE_Z } from "./pose.mjs";
import { ik2, ARM } from "./post.mjs";
import { shapeHand } from "./hands.mjs";

// hand-local palm normal and knuckle direction, from the bind hand
const HAND = {};
for (const s of ["L", "R"]) {
  const p = (n) => BIND[IDX[`${n}_${s}`]].p;
  const f = v3.norm(v3.sub(p("finger_middle_0"), p("hand")));
  const k = v3.norm(v3.sub(p("finger_pinky_0"), p("finger_index_0")));
  let n = v3.norm(v3.cross(f, k));
  if (v3.dot(n, v3.sub(p("finger_thumb_2"), p("finger_middle_0"))) < 0) n = v3.mul(n, -1);
  const hq = q.conj(BIND[IDX["hand_" + s]].q);
  HAND[s] = { palm: q.rotate(hq, n), fwd: q.rotate(hq, f) };
}
export const palmDir = (W, s) => q.rotate(W[IDX["hand_" + s]].q, HAND[s].palm);
export const knuckleDir = (W, s) => q.rotate(W[IDX["hand_" + s]].q, HAND[s].fwd);

// Hand to p with the elbow toward `elbow`; the hand keeps a straight wrist (follows the forearm)
// and is rolled about the forearm so the palm faces `palm`; `bend` tips the wrist (deg, + = toward
// the palm).
export function setHand(W, s, p, { elbow = null, palm = null, bend = 0, side = 0 } = {}) {
  const [ua, la, ha] = ARM[s].map((n) => IDX[n]);
  ik2(W, ...ARM[s], p, { pole: elbow, keepEnd: false });
  // straight wrist: the hand's rotation relative to the forearm back to its bind relation
  const bindRel = q.mul(q.conj(BIND[la].q), BIND[ha].q);
  setWorldRot(W, ha, q.mul(W[la].q, bindRel));
  const fax = v3.norm(v3.sub(W[ha].p, W[la].p));
  if (palm) {
    const cur = v3.perp(palmDir(W, s), fax), want = v3.perp(palm, fax);
    if (v3.len(cur) > 1e-4 && v3.len(want) > 1e-4) {
      const a = Math.atan2(v3.dot(v3.cross(v3.norm(cur), v3.norm(want)), fax), v3.dot(v3.norm(cur), v3.norm(want)));
      setWorldRot(W, ha, q.mul(q.axisAngle(fax, a), W[ha].q));
    }
  }
  if (bend || side) {
    const pd = palmDir(W, s), kd = knuckleDir(W, s);
    const bendAx = v3.norm(v3.cross(kd, pd));
    let r = W[ha].q;
    if (bend) r = q.mul(q.axisAngle(bendAx, bend * DEG), r);
    if (side) r = q.mul(q.axisAngle(pd, side * DEG), r);
    setWorldRot(W, ha, r);
  }
}

export function posture(P) {
  const W = bindPose();
  const pi = IDX.pelvis;
  const pel = P.pelvis || {};
  // pelvis place and turn (everything below and above follows)
  setWorld(W, pi, { q: W[pi].q, p: pel.p ? pel.p.slice() : W[pi].p });
  let rp = q.mul(q.axisAngle([0, 1, 0], (pel.pitch || 0) * DEG), q.axisAngle([1, 0, 0], (pel.roll || 0) * DEG));
  if (pel.spin) rp = q.mul(q.axisAngle([1, 0, 0], pel.spin * DEG), rp);   // about the fight line (lying, tumbling)
  rp = q.mul(q.axisAngle([0, 0, 1], (pel.yaw || 0) * DEG), rp);
  setWorldRot(W, pi, q.mul(rp, W[pi].q));
  // spine
  const ch = P.chest || {};
  if (ch.pitch) bendSpine(W, q.rotate(rp, [0, 1, 0]), ch.pitch * DEG, ch.pitchW || [0.15, 0.25, 0.3, 0.3]);
  if (ch.side) bendSpine(W, q.rotate(rp, [1, 0, 0]), ch.side * DEG);
  if (ch.yaw) twistSpine(W, ch.yaw * DEG, ch.yawW || [0.2, 0.25, 0.3, 0.25]);
  // legs
  for (const s of ["L", "R"]) {
    const f = P.feet && P.feet[s];
    if (!f) continue;
    const heel = f.heel || 0;
    const a = heel * DEG;
    const z = f.z ?? (a ? 1.29 + 5.4 * Math.sin(a) + 3.04 * Math.cos(a) : BIND_ANKLE_Z);
    placeFoot(W, s, [f.p[0], f.p[1], z], f.yaw || 0, { pitch: f.pitch ?? -heel, roll: f.roll || 0, pole: f.knee || null });
    // rel: the foot set on the shin instead of flat (degrees pointed, + = toes pointed)
    if (f.rel != null) footOnShin(W, s, f.rel, { hint: [Math.cos((f.yaw || 0) * DEG), Math.sin((f.yaw || 0) * DEG), 0], roll: f.roll || 0 });
  }
  // arms
  for (const s of ["L", "R"]) {
    const h = P.hands && P.hands[s];
    if (h) setHand(W, s, h.p, h);
  }
  if (P.look) lookAt(W, P.look, { roll: P.headRoll || 0 });
  if (P.shape) for (const s of ["L", "R"]) if (P.shape[s]) shapeHand(W, s, P.shape[s]);
  return W;
}

// ------------------------------------------------------------------ keyed postures
// keys: [[frame, spec], ...] with complete specs (every key gives the same fields); numbers are
// interpolated with monotone cubic curves, so a foot or hand passing through several keys follows
// a smooth arc. Extra per-key numbers: fistL / fistR (0 relaxed .. 1 fist).
function flat(o, pre = "", out = {}) {
  for (const [k, v] of Object.entries(o)) {
    const key = pre ? pre + "." + k : k;
    if (Array.isArray(v)) v.forEach((x, i) => { out[key + "." + i] = x; });
    else if (v && typeof v === "object") flat(v, key, out);
    else if (typeof v === "number") out[key] = v;
  }
  return out;
}
function unflat(fl) {
  const out = {};
  for (const [key, val] of Object.entries(fl)) {
    const ps = key.split(".");
    let o = out;
    for (let i = 0; i < ps.length - 1; i++) { if (!(ps[i] in o)) o[ps[i]] = /^\d+$/.test(ps[i + 1]) ? [] : {}; o = o[ps[i]]; }
    o[ps[ps.length - 1]] = val;
  }
  return out;
}
export function sampleKeys(keys, n) {
  const fl = keys.map(([f, s]) => [f, flat(s)]);
  const chans = new Set(); fl.forEach(([, x]) => Object.keys(x).forEach((c) => chans.add(c)));
  const frames = Array.from({ length: n }, () => ({}));
  for (const c of chans) {
    const pts = fl.filter(([, x]) => c in x).map(([f, x]) => [f, x[c]]);
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const m = xs.length > 1 ? monotoneSlopes(xs, ys) : [0];
    for (let f = 0; f < n; f++) frames[f][c] = xs.length === 1 ? ys[0] : hermiteMap(xs, ys, m, Math.max(xs[0], Math.min(xs[xs.length - 1], f)));
  }
  return frames.map(unflat);
}
export const cloneSpec = (s) => JSON.parse(JSON.stringify(s));

// A key with every channel present, so curves never hold a stale value between keys: missing
// knee / elbow poles are read off the pose the spec builds (the IK's own choice), feet without
// `rel` get a marker that sampleSpecs removes again.
const NO_REL = -999;
export function completeSpec(spec) {
  const o = cloneSpec(spec);
  o.pelvis = { p: o.pelvis.p, yaw: o.pelvis.yaw || 0, pitch: o.pelvis.pitch || 0, roll: o.pelvis.roll || 0, spin: o.pelvis.spin || 0 };
  o.chest = { yaw: 0, pitch: 0, side: 0, ...(o.chest || {}) };
  o.headRoll = o.headRoll || 0;
  const W = posture(spec);
  const pole = (a, b, c) => {
    const A = W[IDX[a]].p, B = W[IDX[b]].p, C = W[IDX[c]].p;
    let bulge = v3.sub(B, v3.mul(v3.add(A, C), 0.5));
    if (v3.len(bulge) < 0.3) bulge = [1, 0, 0];
    return v3.add(B, v3.mul(v3.norm(bulge), 25));
  };
  for (const s of ["L", "R"]) {
    const f = o.feet[s];
    o.feet[s] = { p: f.p, z: f.z ?? null, yaw: f.yaw || 0, heel: f.heel || 0, pitch: f.pitch ?? -(f.heel || 0), roll: f.roll || 0, rel: f.rel ?? NO_REL,
      knee: f.knee || pole("leg_upper_" + s, "leg_lower_" + s, "ankle_" + s) };
    if (o.feet[s].z === null) o.feet[s].z = W[IDX["ankle_" + s]].p[2];
    const h = o.hands[s];
    o.hands[s] = { p: h.p, elbow: h.elbow || pole("arm_upper_" + s, "arm_lower_" + s, "hand_" + s), palm: h.palm || null, bend: h.bend || 0, side: h.side || 0 };
  }
  return o;
}
export function sampleSpecs(keys, n) {
  const specs = sampleKeys(keys.map(([f, s]) => [f, completeSpec(s)]), n);
  for (const sp of specs) for (const s of ["L", "R"]) if (sp.feet[s].rel < NO_REL / 2) delete sp.feet[s].rel;
  return specs;
}
