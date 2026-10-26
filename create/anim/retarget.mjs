// Mocap (BVH) -> CS2 agent skeleton. Defaults are for the CMU set (BVH conversion at
// github.com/Shriinivas/cmubvh); other sources pass their own joint map, leg joints and axes.
//   const rt = makeRetargeter(loadBVH("take.bvh"));  const W = rt(frame);   // one pose
//   const poses = retargetRange(bvh, f0, f1, { fps: 64 });                 // a resampled range
//
// Each target bone copies the world rotation of a source joint, corrected by the difference
// between the two rest poses (CMU's T-pose vs the agent's A-pose). Rest frames are built from a
// primary direction (along the bone) and a secondary one (forward or left), so twist carries over
// too. Bone lengths stay the agent's; the pelvis follows the source hips, scaled by leg length.
import { q, v3, m3 } from "./m3.mjs";
import { SK, IDX, BIND, fk, toLocals, bindLocals } from "./rig.mjs";
import { bvhFrame, bvhWorld, bvhRest } from "./bvh.mjs";

// From cs2-fighter/tools/anim/retarget.mjs (MIT), made project-neutral.

// CMU (Y up, Z forward, X = subject's left) -> agent model space (X forward, Y left, Z up),
// a row-major 3x3. Pass opts.axes for a source with other axes.
export const CMU_AXES = [0, 0, 1, 1, 0, 0, 0, 1, 0];

// target bone <- source joint, with the joints that give the rest frame directions:
// prim = [from, to] (source joints or end sites "J.end"), sec = "fwd" | "left" | [from, to]
export const CMU_MAP = [
  ["pelvis", "Hips", ["Hips", "Spine"], "left"],
  ["spine_0", "LowerBack", ["LowerBack", "Spine"], "left"],
  ["spine_1", "LowerBack", ["LowerBack", "Spine"], "left", { blend: ["Spine", 0.5] }],
  ["spine_2", "Spine", ["Spine", "Spine1"], "left"],
  ["spine_3", "Spine1", ["Spine1", "Neck1"], "left"],
  ["neck_0", "Neck", ["Neck", "Head"], "left"],
  ["head_0", "Head", ["Head", "Head.end"], "left"],
  ["clavicle_L", "LeftShoulder", ["LeftShoulder", "LeftArm"], "fwd"],
  ["arm_upper_L", "LeftArm", ["LeftArm", "LeftForeArm"], "fwd"],
  ["arm_lower_L", "LeftForeArm", ["LeftForeArm", "LeftHand"], "fwd"],
  ["hand_L", "LeftHand", ["LeftHand", "LeftHandIndex1"], "fwd"],
  ["clavicle_R", "RightShoulder", ["RightShoulder", "RightArm"], "fwd"],
  ["arm_upper_R", "RightArm", ["RightArm", "RightForeArm"], "fwd"],
  ["arm_lower_R", "RightForeArm", ["RightForeArm", "RightHand"], "fwd"],
  ["hand_R", "RightHand", ["RightHand", "RightHandIndex1"], "fwd"],
  ["leg_upper_L", "LeftUpLeg", ["LeftUpLeg", "LeftLeg"], "fwd"],
  ["leg_lower_L", "LeftLeg", ["LeftLeg", "LeftFoot"], "fwd"],
  ["ankle_L", "LeftFoot", ["LeftFoot", "LeftToeBase"], "up"],
  ["leg_upper_R", "RightUpLeg", ["RightUpLeg", "RightLeg"], "fwd"],
  ["leg_lower_R", "RightLeg", ["RightLeg", "RightFoot"], "fwd"],
  ["ankle_R", "RightFoot", ["RightFoot", "RightToeBase"], "up"],
];
// CMU joints that give the leg length (scale) and the hips (pelvis position)
export const CMU_LEGS = { hips: "Hips", upL: "LeftUpLeg", kneeL: "LeftLeg", footL: "LeftFoot", footR: "RightFoot" };
// the matching target directions (bone -> child joint) for the same frames
const TPRIM = {
  pelvis: ["pelvis", "spine_1"], spine_0: ["spine_0", "spine_1"], spine_1: ["spine_1", "spine_2"], spine_2: ["spine_2", "spine_3"],
  spine_3: ["spine_3", "neck_0"], neck_0: ["neck_0", "head_0"], head_0: null,
  clavicle_L: ["clavicle_L", "arm_upper_L"], arm_upper_L: ["arm_upper_L", "arm_lower_L"], arm_lower_L: ["arm_lower_L", "hand_L"], hand_L: ["hand_L", "finger_middle_0_L"],
  clavicle_R: ["clavicle_R", "arm_upper_R"], arm_upper_R: ["arm_upper_R", "arm_lower_R"], arm_lower_R: ["arm_lower_R", "hand_R"], hand_R: ["hand_R", "finger_middle_0_R"],
  leg_upper_L: ["leg_upper_L", "leg_lower_L"], leg_lower_L: ["leg_lower_L", "ankle_L"], ankle_L: ["ankle_L", "ball_L"],
  leg_upper_R: ["leg_upper_R", "leg_lower_R"], leg_lower_R: ["leg_lower_R", "ankle_R"], ankle_R: ["ankle_R", "ball_R"],
};
const SEC_T = { fwd: [1, 0, 0], left: [0, 1, 0], up: [0, 0, 1] };

function frameQ(prim, sec) {
  const a = v3.norm(prim);
  let s = v3.perp(sec, a);
  if (v3.len(s) < 1e-5) s = v3.perp(Math.abs(a[2]) < 0.9 ? [0, 0, 1] : [1, 0, 0], a);
  s = v3.norm(s);
  return q.fromBasis(a, s, v3.cross(a, s));
}

// opts: map (rows [targetBone, sourceJoint, [primFrom, primTo], "fwd"|"left"|"up", {blend}?]),
//       legs (see CMU_LEGS), axes (source -> model space), scale (source units -> model units;
//       default from leg length). The source's rest pose (all rotations zero) should be a T-pose.
export function makeRetargeter(bvh, opts = {}) {
  const MAP = opts.map || CMU_MAP, LG = opts.legs || CMU_LEGS;
  const C = opts.axes || CMU_AXES;
  const Cq = q.fromMat(C);
  const toT = (v) => m3.apply(C, v);
  const rotT = (r) => q.norm(q.mul(q.mul(Cq, r), q.conj(Cq)));
  const rest = bvhRest(bvh);
  const J = bvh.index;
  const posOf = (W, key) => {
    if (key.endsWith(".end")) { const j = J[key.slice(0, -4)]; return v3.add(W[j].p, q.rotate(W[j].q, bvh.joints[j].end)); }
    return W[J[key]].p;
  };
  const bindPos = (n) => BIND[IDX[n]].p;
  for (const [tb, sj] of MAP) {
    if (IDX[tb] === undefined) throw new Error(`retarget: target bone ${tb} not in the skeleton`);
    if (J[sj] === undefined) throw new Error(`retarget: source joint ${sj} not in the BVH`);
  }
  const entries = MAP.map(([tb, sj, prim, sec, extra]) => {
    const sp = toT(v3.sub(posOf(rest, prim[1]), posOf(rest, prim[0])));
    // bones without a child along them (the head) use their own X axis, which runs along the bone
    const tp = TPRIM[tb] ? v3.sub(bindPos(TPRIM[tb][1]), bindPos(TPRIM[tb][0])) : q.rotate(BIND[IDX[tb]].q, [1, 0, 0]);
    const secV = SEC_T[sec];
    const Fs = frameQ(sp, secV), Ft = frameQ(tp, secV);
    const restAligned = q.mul(q.mul(Fs, q.conj(Ft)), BIND[IDX[tb]].q);
    const srcRest = rotT(rest[J[sj]].q);
    const off = q.norm(q.mul(q.conj(srcRest), restAligned));
    let blend = null;
    if (extra && extra.blend) {
      const [bj, t] = extra.blend;
      const offB = q.norm(q.mul(q.conj(rotT(rest[J[bj]].q)), restAligned));
      blend = { j: J[bj], t, off: offB };
    }
    return { ti: IDX[tb], sj: J[sj], off, blend };
  });
  // leg-length scale and hips -> pelvis offset
  const legS = v3.dist(posOf(rest, LG.upL), posOf(rest, LG.kneeL)) + v3.dist(posOf(rest, LG.kneeL), posOf(rest, LG.footL));
  const legT = v3.dist(bindPos("leg_upper_L"), bindPos("leg_lower_L")) + v3.dist(bindPos("leg_lower_L"), bindPos("ankle_L"));
  const scale = opts.scale || legT / legS;
  // source hips height above its ankles at rest, versus the target's pelvis height above its ankles
  const restHipsT = toT(posOf(rest, LG.hips));
  const restAnkS = toT(v3.lerp(posOf(rest, LG.footL), posOf(rest, LG.footR), 0.5));
  const hipLocalT = v3.mul(v3.sub(restHipsT, restAnkS), scale);
  const pelvisBind = bindPos("pelvis");
  const ankBind = v3.lerp(bindPos("ankle_L"), bindPos("ankle_R"), 0.5);
  const hipToPelvis = v3.sub(v3.sub(pelvisBind, ankBind), hipLocalT);   // constant correction in rest

  return function retargetFrame(f) {
    const L = bvhFrame(bvh, f);
    const W = bvhWorld(bvh, L);
    const out = bindLocals();
    const world = new Array(SK.length).fill(null);
    for (const e of entries) {
      let r = q.mul(rotT(W[e.sj].q), e.off);
      if (e.blend) r = q.slerp(r, q.mul(rotT(W[e.blend.j].q), e.blend.off), e.blend.t);
      world[e.ti] = q.norm(r);
    }
    // world rotations -> locals (unmapped bones keep their bind local rotation under the parent)
    const Wt = new Array(SK.length);
    for (let i = 0; i < SK.length; i++) {
      const b = SK[i];
      if (b.pi < 0) { Wt[i] = { q: out[i].q, p: out[i].p }; continue; }
      const P = Wt[b.pi];
      const rot = world[i] || q.mul(P.q, b.local.q);
      let p = v3.add(P.p, q.rotate(P.q, b.local.p));
      if (b.name === "pelvis") {
        const hips = v3.mul(toT(W[J[LG.hips]].p), scale);
        // keep the hips -> pelvis correction rotating with the hips
        const hipR = q.mul(rotT(W[J[LG.hips]].q), q.conj(rotT(rest[J[LG.hips]].q)));
        p = v3.add(hips, q.rotate(hipR, hipToPelvis));
      }
      Wt[i] = { q: rot, p };
    }
    return Wt;
  };
}

// Whole take -> poses at 64 Hz (or `fps`), frames [f0, f1) of the source.
export function retargetRange(bvh, f0, f1, { fps = 64, ...opts } = {}) {
  const rt = makeRetargeter(bvh, opts);
  const srcFps = 1 / bvh.dt;
  const n = Math.max(1, Math.round((f1 - f0) / srcFps * fps));
  const poses = [];
  const cache = new Map();
  const get = (f) => { if (!cache.has(f)) cache.set(f, rt(f)); return cache.get(f); };
  for (let k = 0; k <= n; k++) {
    const sf = f0 + (k / fps) * srcFps;
    const a = Math.min(bvh.frames - 1, Math.floor(sf)), b = Math.min(bvh.frames - 1, a + 1), t = sf - a;
    const A = get(a), B = get(b);
    poses.push(A.map((x, i) => ({ q: q.slerp(x.q, B[i].q, t), p: v3.lerp(x.p, B[i].p, t) })));
  }
  return poses;
}
