// Moves from motion capture: a cut of a CMU take is turned to strike along +X, placed so its
// support foot stands where the fighter's stance has it, retimed so its contact lands on the
// move's active frame, and blended out of the start stance and back into the end stance with a
// displacement that fades to nothing at contact (so the strike itself is the real motion).
import { q, v3, clamp, smoother } from "./m3.mjs";
import { SK, IDX, N, fk, toLocals, mirrorPose } from "./rig.mjs";
import { mocapPose, clonePose, hermiteMap, monotoneSlopes } from "./clip.mjs";
import { ik2, LEG, ARM } from "./post.mjs";
import { lookAt, bendSpine } from "./pose.mjs";
import { BIND } from "./rig.mjs";
const BIND_PELVIS_Q = BIND[IDX.pelvis].q;

// world tip of a limb (matches bake.mjs): fists at the knuckles, feet between ankle and toe
export function tipOf(W, tip) {
  const p = (n) => W[IDX[n]].p;
  if (tip === "fF" || tip === "bF") { const s = tip === "fF" ? "L" : "R"; return v3.lerp(p("hand_" + s), p("finger_middle_0_" + s), 0.8); }
  if (tip === "fT" || tip === "bT") {
    const s = tip === "fT" ? "L" : "R";
    const a = p("ankle_" + s), b = p("ball_" + s);
    return v3.lerp(a, v3.add(b, v3.mul(v3.norm(v3.sub(b, a)), 2.2)), 0.75);
  }
  if (tip === "fK") return p("leg_lower_L");
  if (tip === "bK") return p("leg_lower_R");
  return p("head_0");
}
const LIMB_ROOT = { fF: "arm_upper_L", bF: "arm_upper_R", fT: "leg_upper_L", bT: "leg_upper_R" };

function transformPose(W, rot, d) {
  return W.map((t) => ({ q: q.mul(rot, t.q), p: v3.add(q.rotate(rot, t.p), d) }));
}

// bone groups for blend gains
const GROUP = SK.map((b) => {
  const n = b.name;
  if (/arm|hand|finger|clavicle|scapula/.test(n)) return n.endsWith("_L") || /_L_/.test(n) ? "armL" : "armR";
  if (/leg|ankle|ball|toe/.test(n)) return n.endsWith("_L") || /_L_/.test(n) ? "legL" : "legR";
  if (/spine|neck|head/.test(n)) return "torso";
  return "root";
});

// Cut a take: frames are in the take's own frame numbers (120 Hz for CMU).
//  spec: { take, mirror, keys: [[gameFrame, takeFrame], ...] (monotone), tip, support: "L"|"R",
//          aimFrame (take frame used to aim and place), yaw (extra turn, deg) }
export function cutTake(spec, n) {
  const keys = spec.keys;
  const gx = keys.map((k) => k[0]), tx = keys.map((k) => k[1]);
  const m = monotoneSlopes(gx, tx);
  const poses = [];
  for (let f = 0; f < n; f++) {
    const tf = hermiteMap(gx, tx, m, f);
    let W = mocapPose(spec.take, tf / 120);
    if (spec.mirror) W = mirrorPose(W);
    poses.push(W);
  }
  return poses;
}

// Aim and place a cut: the strike (limb root -> tip, level) points along +X at the aim frame and
// the support ankle sits at `supportAt` (x, y).
export function aimCut(poses, { tip, aimIndex, support, supportAt, yaw = 0, by = "tip" }) {
  const A = poses[aimIndex];
  let from = A[IDX[LIMB_ROOT[tip] || "pelvis"]].p, to = tipOf(A, tip);
  if (by === "travel") { from = poses[0][IDX.pelvis].p; to = poses[poses.length - 1][IDX.pelvis].p; }
  const d = [to[0] - from[0], to[1] - from[1]];
  const a = -Math.atan2(d[1], d[0]) + yaw * Math.PI / 180;
  const rot = q.axisAngle([0, 0, 1], a);
  const sa = q.rotate(rot, A[IDX["ankle_" + support]].p);
  const off = [supportAt[0] - sa[0], supportAt[1] - sa[1], 0];
  return poses.map((W) => transformPose(W, rot, off));
}

// Displacement blend: frame f gets the start offset (stance - cut[0]) with weight wIn(f) and the
// end offset (endStance - cut[n-1]) with weight wOut(f). Gains per bone group scale how much of
// the offset is kept beyond the plain fade (keep: 0..1 holds that share of the stance through the
// whole move, e.g. a boxer's guard during a kick).
export function displace(poses, startPose, endPose, { inEnd, outStart, keep = {} } = {}) {
  const n = poses.length;
  const L = poses.map(toLocals);
  const S0 = toLocals(startPose), S1 = toLocals(endPose);
  // offsets as the short way round (a quaternion and its negative are the same turn, but
  // slerping from identity toward one with w < 0 swings the bone through more than 180deg)
  const short = (r) => (r[3] < 0 ? r.map((x) => -x) : r);
  const d0 = S0.map((s, i) => ({ q: short(q.norm(q.mul(s.q, q.conj(L[0][i].q)))), p: v3.sub(s.p, L[0][i].p) }));
  const d1 = S1.map((s, i) => ({ q: short(q.norm(q.mul(s.q, q.conj(L[n - 1][i].q)))), p: v3.sub(s.p, L[n - 1][i].p) }));
  const ID = [0, 0, 0, 1];
  return L.map((Lf, f) => {
    const a = f >= inEnd ? 0 : 1 - smoother(f / inEnd);
    const b = f <= outStart ? 0 : smoother((f - outStart) / Math.max(1, n - 1 - outStart));
    return fk(Lf.map((t, i) => {
      const k = keep[GROUP[i]] || 0;
      const wa = k + (1 - k) * a, wb = b;
      // the kept share of the start offset hands over to the end offset as it comes in
      const wa2 = wa * (1 - wb);
      let r = q.mul(q.slerp(ID, d0[i].q, wa2), t.q);
      r = q.mul(q.slerp(ID, d1[i].q, wb), r);
      return { q: q.norm(r), p: v3.add(t.p, v3.add(v3.mul(d0[i].p, wa2), v3.mul(d1[i].p, wb))) };
    }));
  });
}

// keep a foot planted at a point (ankle position; rotation kept from the pose or given)
export function lockFoot(W, s, at, rot = null, w = 1) {
  const ai = IDX["ankle_" + s];
  const target = v3.lerp(W[ai].p, at, w);
  const r = rot ? q.slerp(W[ai].q, rot, w) : W[ai].q;
  ik2(W, ...LEG[s], target, { keepEnd: false });
  W[ai] = { q: r, p: W[ai].p };
  // re-place the ankle's children (ball/toe) with the new ankle rotation
  const kids = SK.map((b, i) => i).filter((i) => SK[i].pi === ai);
  const walk = (j) => { for (const c of SK.map((b, i) => i).filter((i) => SK[i].pi === j)) { W[c] = { q: q.mul(W[j].q, SK[c].local.q), p: v3.add(W[j].p, q.rotate(W[j].q, SK[c].local.p)) }; walk(c); } };
  walk(ai);
  return W;
}

// Move a strike's tip toward a target over a window of frames: the limb is re-solved with IK
// (leg: hip-knee-ankle, arm: shoulder-elbow-hand) by the weighted miss. target: {x, z} (either).
const CHAIN = { fF: ["arm_upper_L", "arm_lower_L", "hand_L"], bF: ["arm_upper_R", "arm_lower_R", "hand_R"], fT: ["leg_upper_L", "leg_lower_L", "ankle_L"], bT: ["leg_upper_R", "leg_lower_R", "ankle_R"] };
export function steerTip(P, tip, { from, to, ease = 3, x = null, z = null, y = null }) {
  const ch = CHAIN[tip];
  if (!ch) return;
  for (let f = Math.max(0, from - ease); f <= Math.min(P.length - 1, to + ease); f++) {
    const w = f < from ? 1 - (from - f) / (ease + 1) : f > to ? 1 - (f - to) / (ease + 1) : 1;
    const W = P[f];
    const t = tipOf(W, tip);
    const d = [x === null ? 0 : (x - t[0]) * w, y === null ? 0 : (y - t[1]) * w, z === null ? 0 : (z - t[2]) * w];
    const end = W[IDX[ch[2]]];
    // the foot / fist keeps its set on the shin / forearm (a straight wrist, an ankle that follows)
    const rel = q.mul(q.conj(W[IDX[ch[1]]].q), end.q);
    ik2(W, ...ch, v3.add(end.p, d), { keepEnd: false });
    W[IDX[ch[2]]] = { q: q.norm(q.mul(W[IDX[ch[1]]].q, rel)), p: W[IDX[ch[2]]].p };
    refreshKids(W, IDX[ch[2]]);
  }
}
const KIDS = SK.map((_, i) => SK.map((b, j) => j).filter((j) => SK[j].pi === i));
export function refreshKids(W, i) {
  for (const c of KIDS[i]) { W[c] = { q: q.mul(W[i].q, SK[c].local.q), p: v3.add(W[i].p, q.rotate(W[i].q, SK[c].local.p)) }; refreshKids(W, c); }
}
// keep both feet above the floor (ankle z >= floor), lifting the whole body if needed is not
// done: the low foot's leg is re-solved instead
export function floorFeet(W, floorZ = 4.0) {
  for (const s of ["L", "R"]) {
    const ai = IDX["ankle_" + s];
    if (W[ai].p[2] < floorZ) { const r = W[ai].q.slice(); ik2(W, ...LEG[s], [W[ai].p[0], W[ai].p[1], floorZ], { keepEnd: false }); W[ai] = { q: r, p: W[ai].p }; refreshKids(W, ai); }
  }
  return W;
}

// Build a move clip from a mocap spec.
//  spec: { take, mirror, keys: [[baseFrame, takeFrame]...], aim: takeFrame, tip, support,
//          place: "support" | "pelvis", pelvisDx, yaw, lock (support foot planted at its stance spot),
//          keep: {armL, armR, ...}, steer: [{from, to, x, z}] (base frames), inEnd, outStart }
export function mocapPoses(spec, { start, end, k = 1, n }) {
  const keys = spec.keys.map(([g, t]) => [g * k, t]);
  let P = cutTake({ ...spec, keys }, n);
  // aim index: the game frame mapped to the aim take frame
  const ak = spec.keys.find((x) => x[1] === spec.aim);
  const aimIndex = Math.min(n - 1, Math.round(ak[0] * k));
  const sup = spec.support;
  if (spec.place === "pelvis") {
    P = aimCut(P, { tip: spec.tip, aimIndex, support: sup, supportAt: [0, 0], yaw: spec.yaw || 0, by: spec.aimBy });
    // travelling moves (the game carries the fighter): hold the pelvis over one spot
    if (spec.strip) { const x0 = P[0][IDX.pelvis].p[0]; P = P.map((W) => { const dx = W[IDX.pelvis].p[0] - x0; return W.map((t) => ({ q: t.q, p: [t.p[0] - dx * spec.strip, t.p[1], t.p[2]] })); }); }
    const pz = P[aimIndex][IDX.pelvis].p, sp = start[IDX.pelvis].p;
    const d = [sp[0] + (spec.pelvisDx || 0) - pz[0], sp[1] + (spec.pelvisDy || 0) - pz[1], 0];
    P = P.map((W) => W.map((t) => ({ q: t.q, p: [t.p[0] + d[0], t.p[1] + d[1], t.p[2]] })));
  } else {
    const sa = start[IDX["ankle_" + sup]].p;
    P = aimCut(P, { tip: spec.tip, aimIndex, support: sup, supportAt: [sa[0] + (spec.supportDx || 0), sa[1]], yaw: spec.yaw || 0 });
  }
  const inEnd = Math.round((spec.inEnd ?? ak[0]) * k);
  const outStart = Math.round((spec.outStart ?? ak[0] + 4) * k);
  P = displace(P, start, end, { inEnd, outStart, keep: spec.keep || {} });
  // turn: the whole body pivots on the support foot (more hip turn into a roundhouse)
  if (spec.turn) {
    const T = spec.turn;
    const a0 = Math.round(T.from * k), a1 = Math.round(T.to * k), e = Math.round((T.ease ?? 4) * k);
    P = P.map((W, f) => {
      const w = f < a0 - e || f > a1 + e ? 0 : f < a0 ? smoother((f - (a0 - e)) / Math.max(1, e)) : f > a1 ? 1 - smoother((f - a1) / Math.max(1, e)) : 1;
      if (w <= 0) return W;
      const c = W[IDX["ankle_" + sup]].p;
      const r = q.axisAngle([0, 0, 1], T.deg * w * Math.PI / 180);
      return W.map((t) => ({ q: q.mul(r, t.q), p: v3.add(c, q.rotate(r, v3.sub(t.p, c))) }));
    });
  }
  // lean: the upper body tips back (deg > 0) over a window, e.g. to counter a big push kick
  if (spec.lean) {
    const T = spec.lean;
    const a0 = Math.round(T.from * k), a1 = Math.round(T.to * k), e = Math.max(1, Math.round((T.ease ?? 4) * k));
    P = P.map((W, f) => {
      const w = f < a0 - e || f > a1 + e ? 0 : f < a0 ? smoother((f - (a0 - e)) / e) : f > a1 ? 1 - smoother((f - a1) / e) : 1;
      if (w <= 0) return W;
      const left = q.rotate(W[IDX.pelvis].q, q.rotate(q.conj(BIND_PELVIS_Q), [0, 1, 0]));
      bendSpine(W, left, -T.deg * w * Math.PI / 180);
      return W;
    });
  }
  if (spec.lock) {
    const sa = start[IDX["ankle_" + sup]];
    P = P.map((W) => lockFoot(W, sup, sa.p, null, 1));
  }
  for (const st of spec.steer || []) steerTip(P, spec.tip, { ...st, from: Math.round(st.from * k), to: Math.round(st.to * k) });
  P = P.map((W) => floorFeet(W));
  // eyes on the opponent through the move (the capture looks wherever the performer did)
  if (spec.look !== false) {
    const tgt = spec.look || [90, 0, 52];
    P = P.map((W, f) => {
      const w = Math.min(1, Math.min(f, n - 1 - f) / Math.max(1, 3 * k));
      if (w <= 0) return W;
      const before = W.map((t) => ({ q: t.q.slice(), p: t.p.slice() }));
      lookAt(W, tgt, { neckShare: 0.45 });
      if (w >= 1) return W;
      for (const n2 of ["neck_0", "head_0"]) { const i = IDX[n2]; W[i] = { q: q.slerp(before[i].q, W[i].q, w), p: W[i].p }; }
      refreshKids(W, IDX.head_0);
      return W;
    });
  }
  return { poses: P, aimIndex };
}
