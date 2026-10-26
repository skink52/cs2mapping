// Pose editing helpers: place the pelvis, bend and twist the spine, aim the head, plant feet,
// put hands somewhere with the elbows where they should be. All work on world poses in place.
import { q, v3, clamp, DEG } from "./m3.mjs";
import { SK, IDX, BIND, setWorldRot, setWorld } from "./rig.mjs";
import { ik2, LEG, ARM } from "./post.mjs";

export const SPINE = ["spine_0", "spine_1", "spine_2", "spine_3"];
const HEAD_FWD = q.rotate(q.conj(BIND[IDX.head_0].q), [1, 0, 0]);   // head-local forward (face)
const HEAD_UP = q.rotate(q.conj(BIND[IDX.head_0].q), [0, 0, 1]);
const FOOT_FWD = { L: null, R: null };   // ankle-local forward (heel -> toe, flat) and up
const FOOT_UP = { L: null, R: null };
for (const s of ["L", "R"]) {
  const a = BIND[IDX["ankle_" + s]], b = BIND[IDX["ball_" + s]];
  const toe = v3.sub(b.p, a.p);
  FOOT_FWD[s] = q.rotate(q.conj(a.q), v3.norm([toe[0], toe[1], 0]));
  FOOT_UP[s] = q.rotate(q.conj(a.q), [0, 0, 1]);
}
export const BIND_ANKLE_Z = BIND[IDX.ankle_L].p[2];

// move the whole body (pelvis and below) by d, keeping feet unless keepFeet=false
export function movePelvis(W, d, { keepFeet = true } = {}) {
  const feet = keepFeet ? ["L", "R"].map((s) => ({ s, p: W[IDX["ankle_" + s]].p.slice(), q: W[IDX["ankle_" + s]].q.slice() })) : [];
  const pi = IDX.pelvis;
  setWorld(W, pi, { q: W[pi].q, p: v3.add(W[pi].p, d) });
  for (const f of feet) { ik2(W, ...LEG[f.s], f.p); setWorldRot(W, IDX["ankle_" + f.s], f.q); }
}
// rotate the pelvis (and everything above/below) about an axis through the pelvis, feet kept
export function rotatePelvis(W, axis, ang, { keepFeet = true, keepChest = false } = {}) {
  const feet = keepFeet ? ["L", "R"].map((s) => ({ s, p: W[IDX["ankle_" + s]].p.slice(), q: W[IDX["ankle_" + s]].q.slice() })) : [];
  const chest = keepChest ? W[IDX.spine_0].q.slice() : null;
  const pi = IDX.pelvis;
  setWorldRot(W, pi, q.mul(q.axisAngle(axis, ang), W[pi].q));
  if (chest) setWorldRot(W, IDX.spine_0, chest);
  for (const f of feet) { ik2(W, ...LEG[f.s], f.p); setWorldRot(W, IDX["ankle_" + f.s], f.q); }
}
// spread a rotation over the spine bones (weights sum to 1), e.g. lean forward / twist
export function bendSpine(W, axis, ang, weights = [0.2, 0.25, 0.3, 0.25]) {
  SPINE.forEach((n, k) => { const i = IDX[n]; setWorldRot(W, i, q.mul(q.axisAngle(axis, ang * weights[k]), W[i].q)); });
}
// twist about the spine's own axis (pelvis -> neck)
export function twistSpine(W, ang, weights) {
  const axis = v3.norm(v3.sub(W[IDX.neck_0].p, W[IDX.spine_0].p));
  bendSpine(W, axis, ang, weights);
}
// aim the face at a point, splitting the turn between neck and head
export function lookAt(W, target, { neckShare = 0.4, roll = 0 } = {}) {
  for (const [bone, share] of [["neck_0", neckShare], ["head_0", 1]]) {
    const i = IDX[bone], h = IDX.head_0;
    const face = q.rotate(W[h].q, HEAD_FWD);
    const want = v3.norm(v3.sub(target, W[h].p));
    const full = q.between(face, want);
    const part = q.slerp([0, 0, 0, 1], full, share);
    setWorldRot(W, i, q.mul(part, W[i].q));
  }
  // keep the head upright-ish: remove roll around the face axis
  const h = IDX.head_0;
  const face = q.rotate(W[h].q, HEAD_FWD), up = q.rotate(W[h].q, HEAD_UP);
  const wantUp = v3.norm(v3.perp([0, 0, 1], face));
  const ang = Math.atan2(v3.dot(v3.cross(up, wantUp), face), v3.dot(up, wantUp)) + roll * DEG;
  setWorldRot(W, h, q.mul(q.axisAngle(face, ang * 0.85), W[h].q));
}
// plant a foot: ankle at p (z = ankle height), toe pointing along yaw (deg, 0 = +X), flat
// (pitch/roll in degrees tilt it: pitch>0 = toe up, roll for the outside edge)
export function placeFoot(W, s, p, yawDeg, { pitch = 0, roll = 0, pole = null } = {}) {
  const ai = IDX["ankle_" + s];
  ik2(W, ...LEG[s], p, { pole: pole || kneePole(W, s, yawDeg), keepEnd: false });
  const fwd = [Math.cos(yawDeg * DEG), Math.sin(yawDeg * DEG), 0];
  let rot = footRot(s, fwd);
  if (pitch) rot = q.mul(q.axisAngle(v3.cross([0, 0, 1], fwd), -pitch * DEG), rot);
  if (roll) rot = q.mul(q.axisAngle(fwd, roll * DEG), rot);
  setWorldRot(W, ai, rot);
}
// world rotation of an ankle whose foot points along fwd (horizontal) and stands flat
export function footRot(s, fwd) {
  const f = v3.norm(fwd), u = [0, 0, 1];
  // ankle-local basis (FOOT_FWD, FOOT_UP) -> world (f, u)
  const A = basisQ(FOOT_FWD[s], FOOT_UP[s]), B = basisQ(f, u);
  return q.norm(q.mul(B, q.conj(A)));
}
function basisQ(f, u) {
  const x = v3.norm(f), y = v3.norm(v3.cross(u, x)), z = v3.cross(x, y);
  return q.fromBasis(x, y, z);
}
// knees point roughly over the toes
function kneePole(W, s, yawDeg) {
  const hip = W[IDX["leg_upper_" + s]].p;
  return v3.add(hip, [Math.cos(yawDeg * DEG) * 40, Math.sin(yawDeg * DEG) * 40, -18]);
}
// hand to a point with the elbow pulled toward `elbow` (a point), wrist aimed by `aim` (dir)
export function placeHand(W, s, p, { elbow = null, aim = null, upHint = null } = {}) {
  ik2(W, ...ARM[s], p, { pole: elbow, keepEnd: false });
  if (aim) {
    const hi = IDX["hand_" + s];
    const cur = q.rotate(W[hi].q, [1, 0, 0]);
    setWorldRot(W, hi, q.mul(q.between(cur, aim), W[hi].q));
    if (upHint) {
      // roll the hand about its axis so its local -Z (back of the hand) faces upHint
      const ax = v3.norm(aim);
      const back = q.rotate(W[hi].q, [0, 0, s === "L" ? -1 : 1]);
      const pb = v3.perp(back, ax), pu = v3.perp(upHint, ax);
      if (v3.len(pb) > 1e-4 && v3.len(pu) > 1e-4) {
        const ang = Math.atan2(v3.dot(v3.cross(v3.norm(pb), v3.norm(pu)), ax), v3.dot(v3.norm(pb), v3.norm(pu)));
        setWorldRot(W, hi, q.mul(q.axisAngle(ax, ang), W[hi].q));
      }
    }
  }
}
export const P = (W, n) => W[IDX[n]].p;

// ------------------------------------------------------------------ ankles that follow the shin
// The knee's hinge axis and the foot's "neutral" direction (square to the shin, toward where the
// knee points). hint = a direction to use when the leg is straight.
function shinFrame(W, s, hint) {
  const hip = W[IDX["leg_upper_" + s]].p, knee = W[IDX["leg_lower_" + s]].p, ank = W[IDX["ankle_" + s]].p;
  const down = v3.norm(v3.sub(ank, knee));
  const bulge = v3.sub(knee, v3.mul(v3.add(hip, ank), 0.5));
  let fwd = v3.perp(bulge, down);
  const h = hint ? v3.perp(hint, down) : null;
  if (v3.len(fwd) < 0.8 && h && v3.len(h) > 1e-3) fwd = v3.add(v3.mul(v3.norm(fwd.every((x) => x === 0) ? h : fwd), v3.len(fwd) / 0.8), v3.mul(v3.norm(h), 1 - v3.len(fwd) / 0.8));
  if (v3.len(fwd) < 1e-4) fwd = h && v3.len(h) > 1e-4 ? h : v3.perp([1, 0, 0], down);
  fwd = v3.norm(fwd);
  return { down, fwd, axis: v3.norm(v3.cross(fwd, down)) };
}
// foot set on the shin: plantar = degrees of pointing the toes (+) or pulling them up (-),
// roll = degrees about the foot's long axis.
export function footOnShin(W, s, plantar = 0, { hint = null, roll = 0 } = {}) {
  const F = shinFrame(W, s, hint);
  const a = plantar * DEG;
  const fwd = v3.add(v3.mul(F.fwd, Math.cos(a)), v3.mul(F.down, Math.sin(a)));
  let up = v3.add(v3.mul(F.down, -Math.cos(a)), v3.mul(F.fwd, Math.sin(a)));
  if (roll) up = q.rotate(q.axisAngle(fwd, roll * DEG), up);
  const A = basisQ(FOOT_FWD[s], FOOT_UP[s]), B = basisQ(fwd, up);
  setWorldRot(W, IDX["ankle_" + s], q.norm(q.mul(B, q.conj(A))));
}
// how the foot sits on the shin now: plantar (deg, + toes pointed), roll (deg), yaw (deg, the toe
// turned off the knee's direction)
export function footAngles(W, s) {
  const F = shinFrame(W, s, null);
  const r = W[IDX["ankle_" + s]].q;
  const fwd = q.rotate(r, FOOT_FWD[s]), up = q.rotate(r, FOOT_UP[s]);
  const plantar = Math.atan2(v3.dot(fwd, F.down), v3.dot(fwd, F.fwd)) / DEG;
  const yaw = Math.asin(clamp(v3.dot(fwd, F.axis), -1, 1)) / DEG;
  const sideUp = v3.dot(up, F.axis);
  return { plantar, yaw, roll: Math.asin(clamp(sideUp, -1, 1)) / DEG, F };
}
// keep every ankle inside a natural range (toes pulled up 25, pointed 60, turned 25, rolled 25)
export const ANKLE_LIMIT = { up: 25, down: 60, yaw: 25, roll: 25 };
export function limitAnkles(W, lim = ANKLE_LIMIT) {
  for (const s of ["L", "R"]) {
    // a foot standing on the floor stays flat; only feet in the air are held to the range
    if (Math.min(W[IDX["ankle_" + s]].p[2], W[IDX["ball_" + s]].p[2] + 2) < 6) continue;
    const a = footAngles(W, s);
    const p = clamp(a.plantar, -lim.up, lim.down), y = clamp(a.yaw, -lim.yaw, lim.yaw), r = clamp(a.roll, -lim.roll, lim.roll);
    if (Math.abs(p - a.plantar) < 0.5 && Math.abs(y - a.yaw) < 0.5 && Math.abs(r - a.roll) < 0.5) continue;
    const F = a.F;
    const pa = p * DEG, ya = y * DEG;
    let fwd = v3.add(v3.mul(F.fwd, Math.cos(pa)), v3.mul(F.down, Math.sin(pa)));
    fwd = v3.norm(v3.add(v3.mul(fwd, Math.cos(ya)), v3.mul(F.axis, Math.sin(ya))));
    let up = v3.norm(v3.perp(v3.add(v3.mul(F.down, -Math.cos(pa)), v3.mul(F.fwd, Math.sin(pa))), fwd));
    up = q.rotate(q.axisAngle(fwd, -r * DEG * Math.sign(v3.dot(v3.cross(fwd, up), F.axis) || 1)), up);
    const A = basisQ(FOOT_FWD[s], FOOT_UP[s]), B = basisQ(fwd, up);
    setWorldRot(W, IDX["ankle_" + s], q.norm(q.mul(B, q.conj(A))));
  }
  return W;
}
