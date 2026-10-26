// Smoke test for the animation pipeline, needing no CS2 files: builds a synthetic skeleton with
// the CS2 agent's bone names (made-up proportions, not Valve's data) and a synthetic CMU-style
// BVH, then runs retarget, mocap cut/blend, posture + IK, hand shapes, finishing passes, mirror,
// the joint validator, SMD write/read round trip and the rig vmdl writer.
//   node test_smoke.mjs [out dir]      (default /tmp/cs2_anim_smoke; exits 1 on a failure)
// Written for this repo (MIT), alongside the pipeline from cs2-fighter.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const OUT = process.argv[2] || path.join(os.tmpdir(), "cs2_anim_smoke");
fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(OUT, { recursive: true });
let fails = 0;
const check = (ok, what) => { console.log(`${ok ? "ok  " : "FAIL"} ${what}`); if (!ok) fails++; };

// ------------------------------------------------------------------ synthetic skeleton
// World bind positions (model space: +X forward, +Y left, +Z up), left side; the right mirrors it.
const { v3, q } = await import("./m3.mjs");
function buildSkeleton() {
  const P = {}, PAR = {}, AIM = {};
  const add = (name, parent, p, aim = null) => { P[name] = p; PAR[name] = parent; AIM[name] = aim; };
  add("root_motion", null, [0, 0, 0], [1, 0, 0]);
  add("pelvis", "root_motion", [-2.8, 0, 42.8], "spine_1");
  add("spine_0", "pelvis", [-2.7, 0, 43.8], "spine_1");
  add("spine_1", "spine_0", [-2.3, 0, 47.8], "spine_2");
  add("spine_2", "spine_1", [-2.3, 0, 52.5], "spine_3");
  add("spine_3", "spine_2", [-3.4, 0, 58.8], "neck_0");
  add("neck_0", "spine_3", [-3.1, 0, 65.3], "head_0");
  add("head_0", "neck_0", [-1.4, 0, 70.8], [0, 0, 1]);
  add("head_0_TWIST", "neck_0", [-3.1, 0, 65.3], "head_0");
  for (const [s, k] of [["L", 1], ["R", -1]]) {
    const m = (p) => [p[0], p[1] * k, p[2]];
    add(`clavicle_${s}`, "spine_3", m([-0.2, 1.3, 62.9]), `arm_upper_${s}`);
    add(`scapula_${s}`, `clavicle_${s}`, m([-3.3, 6.7, 63.8]), m([-0.3, -0.2, -0.9]));
    add(`arm_upper_${s}`, `clavicle_${s}`, m([-3.3, 7.2, 61.7]), `arm_lower_${s}`);
    add(`arm_lower_${s}`, `arm_upper_${s}`, m([-4.5, 14.7, 52.7]), `hand_${s}`);
    add(`hand_${s}`, `arm_lower_${s}`, m([-1.2, 21.0, 44.1]), `finger_middle_0_${s}`);
    const au = P[`arm_upper_${s}`], al = P[`arm_lower_${s}`], h = P[`hand_${s}`];
    add(`arm_upper_${s}_TWIST`, `arm_upper_${s}`, v3.lerp(au, al, 0.33), `arm_lower_${s}`);
    add(`arm_upper_${s}_TWIST1`, `arm_upper_${s}`, v3.lerp(au, al, 0.66), `arm_lower_${s}`);
    add(`arm_lower_${s}_TWIST`, `arm_lower_${s}`, v3.lerp(al, h, 0.33), `hand_${s}`);
    add(`arm_lower_${s}_TWIST1`, `arm_lower_${s}`, v3.lerp(al, h, 0.66), `hand_${s}`);
    // hand: fingers run along f, knuckles spread along `across`, thumb on the palm side
    const f = v3.norm(m([0.25, 0.25, -0.93])), across = v3.norm(m([-0.75, -0.2, -0.2]));
    const palm = v3.norm(v3.cross(f, across));
    ["index", "middle", "ring", "pinky"].forEach((fn, i) => {
      const knuckle = v3.add(v3.add(h, v3.mul(f, 3.2)), v3.mul(across, (i - 1.2) * 0.75));
      add(`finger_${fn}_meta_${s}`, `hand_${s}`, v3.add(h, v3.mul(across, (i - 1.2) * 0.4)), `finger_${fn}_0_${s}`);
      add(`finger_${fn}_0_${s}`, `finger_${fn}_meta_${s}`, knuckle, `finger_${fn}_1_${s}`);
      add(`finger_${fn}_1_${s}`, `finger_${fn}_0_${s}`, v3.add(knuckle, v3.mul(f, 1.8)), `finger_${fn}_2_${s}`);
      add(`finger_${fn}_2_${s}`, `finger_${fn}_1_${s}`, v3.add(knuckle, v3.mul(f, 3.1)), f);
    });
    const t0 = v3.add(v3.add(h, v3.mul(f, 0.9)), v3.add(v3.mul(across, -0.9), v3.mul(palm, 0.6)));
    const td = v3.norm(v3.add(v3.mul(f, 0.8), v3.add(v3.mul(across, -0.3), v3.mul(palm, 0.5))));
    add(`finger_thumb_0_${s}`, `hand_${s}`, t0, `finger_thumb_1_${s}`);
    add(`finger_thumb_1_${s}`, `finger_thumb_0_${s}`, v3.add(t0, v3.mul(td, 1.8)), `finger_thumb_2_${s}`);
    add(`finger_thumb_2_${s}`, `finger_thumb_1_${s}`, v3.add(t0, v3.mul(td, 3.2)), td);
    add(`leg_upper_${s}`, "pelvis", m([-1.9, 3.7, 39.0]), `leg_lower_${s}`);
    add(`leg_lower_${s}`, `leg_upper_${s}`, m([-1.7, 4.4, 21.2]), `ankle_${s}`);
    add(`ankle_${s}`, `leg_lower_${s}`, m([-3.5, 4.5, 4.3]), `ball_${s}`);
    add(`ball_${s}`, `ankle_${s}`, m([1.9, 5.8, 1.3]), [1, 0, 0]);
    const lu = P[`leg_upper_${s}`], ll = P[`leg_lower_${s}`];
    add(`leg_upper_${s}_TWIST`, `leg_upper_${s}`, v3.lerp(lu, ll, 0.33), `leg_lower_${s}`);
    add(`leg_upper_${s}_TWIST1`, `leg_upper_${s}`, v3.lerp(lu, ll, 0.66), `leg_lower_${s}`);
  }
  // world rotation: X along the bone (toward its aim), Y toward the body's left where possible
  const Wq = {};
  const out = [];
  for (const name of Object.keys(P)) {
    const a = AIM[name];
    const dir = v3.norm(typeof a === "string" ? v3.sub(P[a], P[name]) : a);
    let y = v3.perp([0, 1, 0], dir);
    if (v3.len(y) < 0.2) y = v3.perp([1, 0, 0], dir);
    y = v3.norm(y);
    Wq[name] = q.fromBasis(dir, y, v3.cross(dir, y));
    const par = PAR[name];
    const lq = par ? q.mul(q.conj(Wq[par]), Wq[name]) : Wq[name];
    const lp = par ? q.rotate(q.conj(Wq[par]), v3.sub(P[name], P[par])) : P[name];
    out.push({ name, parent: par, pos: lp, quat: q.norm(lq) });
  }
  return out;
}
const skel = buildSkeleton();
const skFile = path.join(OUT, "synthetic_skeleton.json");
fs.writeFileSync(skFile, JSON.stringify(skel));
check(skel.length === 77, `synthetic skeleton has ${skel.length} bones (CS2 agent: 77)`);
process.env.CS2_SKELETON = skFile;

// ------------------------------------------------------------------ synthetic BVH (CMU layout)
function bvhText(frames = 72) {
  const J = (name, off, kids, end = null) => ({ name, off, kids, end });
  const leg = (s, x) => J(`${s}HipJoint`, [0, 0, 0], [J(`${s}UpLeg`, [x * 1.6, -1.6, 0.6], [J(`${s}Leg`, [0, -7, 0], [J(`${s}Foot`, [0, -7, 0], [J(`${s}ToeBase`, [0, -0.8, 2.2], [], [0, 0, 1])])])])]);
  const arm = (s, x) => J(`${s}Shoulder`, [0, 0, 0], [J(`${s}Arm`, [x * 1.8, 0.4, 0], [J(`${s}ForeArm`, [x * 5, 0, 0], [J(`${s}Hand`, [x * 4.5, 0, 0], [
    J(`${s}FingerBase`, [x * 0.6, 0, 0], [J(`${s}HandIndex1`, [x * 0.6, 0, 0], [], [x * 0.5, 0, 0])]),
    J(`${s === "Left" ? "L" : "R"}Thumb`, [x * 0.4, 0, 0.4], [], [x * 0.3, 0, 0.3]),
  ])])])]);
  const root = J("Hips", [0, 0, 0], [leg("Left", 1), leg("Right", -1),
    J("LowerBack", [0, 0, 0], [J("Spine", [0, 2, 0], [J("Spine1", [0, 2, 0], [J("Neck", [0, 0, 0], [J("Neck1", [0, 1.7, 0], [J("Head", [0, 1.7, 0], [], [0, 1.5, 0])])]), arm("Left", 1), arm("Right", -1)])])])]);
  const order = [];
  let s = "HIERARCHY\n";
  const walk = (j, d, isRoot) => {
    const ind = "  ".repeat(d);
    s += `${ind}${isRoot ? "ROOT" : "JOINT"} ${j.name}\n${ind}{\n${ind}  OFFSET ${j.off.join(" ")}\n`;
    s += `${ind}  CHANNELS ${isRoot ? "6 Xposition Yposition Zposition Zrotation Yrotation Xrotation" : "3 Zrotation Yrotation Xrotation"}\n`;
    order.push(j.name);
    for (const k of j.kids) walk(k, d + 1, false);
    if (j.end) s += `${ind}  End Site\n${ind}  {\n${ind}    OFFSET ${j.end.join(" ")}\n${ind}  }\n`;
    s += `${ind}}\n`;
  };
  walk(root, 0, true);
  s += `MOTION\nFrames: ${frames}\nFrame Time: ${1 / 120}\n`;
  for (let f = 0; f < frames; f++) {
    const t = Math.sin(Math.PI * f / (frames - 1));   // 0 -> 1 -> 0
    const rot = {
      LeftArm: [-60 + 50 * t, -70 * t, 0],    // Z, Y, X degrees: arm down from T-pose, then forward
      RightArm: [60, 0, 0],
      LeftForeArm: [0, -60 * (1 - t), 0],     // elbow bent, straightening at the peak
      LeftUpLeg: [0, 0, -70 * t], LeftLeg: [0, 0, 100 * t],   // left knee lifts
      Spine1: [0, 10 * t, 0],
    };
    const row = [];
    for (const n of order) {
      if (n === "Hips") row.push(0.3 * t, 17.5 - 0.4 * t, 1.5 * t, 0, 0, 0);   // ankles ~1.9 above the floor
      else row.push(...(rot[n] || [0, 0, 0]));
    }
    s += row.map((x) => x.toFixed(4)).join(" ") + "\n";
  }
  return s;
}
const bvhFile = path.join(OUT, "synthetic_take.bvh");
fs.writeFileSync(bvhFile, bvhText());

// ------------------------------------------------------------------ the pipeline
const { SK, IDX, BIND, N, bindPose, mirrorPose } = await import("./rig.mjs");
const { loadBVH } = await import("./bvh.mjs");
const { makeRetargeter, retargetRange } = await import("./retarget.mjs");
const { Clip, clonePose } = await import("./clip.mjs");
const { mocapPoses } = await import("./mocap_move.mjs");
const { posture, sampleSpecs } = await import("./posture.mjs");
const { ik2, LEG, armsOutOfBody } = await import("./post.mjs");
const { setWorldRot } = await import("./rig.mjs");
const { limitAnkles } = await import("./pose.mjs");
const { checkPose, checkClip } = await import("./validate.mjs");
const { readSMD } = await import("./smd.mjs");
const { writeRig, smdAnimText } = await import("./rig_vmdl.mjs");

const finite = (poses) => poses.every((W) => W.every((t) => [...t.q, ...t.p].every(Number.isFinite)));
// bone lengths stay the skeleton's (the pelvis moves freely under the root, so it is skipped)
const bonesRigid = (W, tol = 1e-3) => SK.every((b, i) => b.pi < 0 || SK[b.pi].pi < 0 || Math.abs(v3.dist(W[i].p, W[b.pi].p) - v3.len(b.local.p)) < tol);
const maxDiff = (A, B) => Math.max(...A.flatMap((W, f) => W.map((t, i) => v3.dist(t.p, B[f][i].p))));

// 1. BVH + retarget
const bvh = loadBVH(bvhFile);
check(bvh.frames === 72 && Math.abs(1 / bvh.dt - 120) < 1e-6, `BVH read: ${bvh.joints.length} joints, ${bvh.frames} frames at ${Math.round(1 / bvh.dt)} Hz`);
const rt = makeRetargeter(bvh);
const W0 = rt(0), Wp = rt(36);
check(finite([W0, Wp]) && bonesRigid(Wp), "retargeted poses are finite and keep bone lengths");
const ankZ = (W) => Math.min(W[IDX.ankle_L].p[2], W[IDX.ankle_R].p[2]);
check(Math.abs(ankZ(W0) - BIND[IDX.ankle_L].p[2]) < 1.5, `rest frame stands on the floor (ankle z ${ankZ(W0).toFixed(2)})`);
check(Wp[IDX.ankle_L].p[2] > W0[IDX.ankle_L].p[2] + 3, "left knee lift in the take lifts the left foot");
const range = retargetRange(bvh, 0, 72, { fps: 64 });
check(range.length === 39, `resampled 72 frames @120 Hz -> ${range.length} frames @64 Hz`);

// 2. a posed stance (posture + hinge IK + hand shapes)
const stanceSpec = {
  pelvis: { p: [-2, 0, 38], yaw: -10 },
  chest: { pitch: 6 },
  look: [100, 0, 60],
  feet: { L: { p: [6, 7], yaw: 10 }, R: { p: [-8, -6], yaw: -20 } },
  hands: { L: { p: [12, 6, 56] }, R: { p: [8, -4, 54] } },
  shape: { L: "fist", R: "fist" },
};
const stance = posture(stanceSpec); console.log("A", stance[IDX.ankle_R].p);
check(finite([stance]) && bonesRigid(stance), "posture() builds a valid stance");
const miss = v3.dist(stance[IDX.hand_L].p, [12, 6, 56]);
check(miss < 0.5, `hand IK reaches its target (miss ${miss.toFixed(3)})`);
const knee = stance[IDX.leg_lower_L].p, hip = stance[IDX.leg_upper_L].p, ank = stance[IDX.ankle_L].p;
check(v3.dot(v3.sub(knee, v3.lerp(hip, ank, 0.5)), [1, 0, 0]) > 0, "hinge IK bends the knee forward");

// 3. keyed postures -> a clip
console.log("B", stance[IDX.ankle_R].p); const keyB = JSON.parse(JSON.stringify(stanceSpec));
keyB.hands.L.p = [26, 4, 58]; keyB.pelvis.p = [0, 0, 37.5];
const specs = sampleSpecs([[0, stanceSpec], [8, keyB], [16, stanceSpec]], 17);
const jab = new Clip("jab", specs.map(posture));
jab.finish();
check(jab.n === 17 && finite(jab.poses) && bonesRigid(jab.poses[8]), "keyed clip sampled and finished (hands, twist bones, limits)");
check(jab.poses[8][IDX.hand_L].p[0] > jab.poses[0][IDX.hand_L].p[0] + 8, "the jab reaches forward at its key");

console.log("C", stance[IDX.ankle_R].p);
// 4. mocap move: cut, aim, place on support foot, retime with key pairs, blend into the stance
const { poses: kick } = mocapPoses({
  take: bvhFile, keys: [[0, 0], [10, 36], [24, 71]], aim: 36, tip: "foot_L", support: "R", lock: true, look: [100, 0, 60],
}, { start: stance, end: stance, n: 25 });
check(kick.length === 25 && finite(kick), "mocapPoses: 25 frames, finite");
check(maxDiff([kick[0]], [stance]) < 0.6, `move starts in the stance (max ${maxDiff([kick[0]], [stance]).toFixed(3)})`);
check(maxDiff([kick[24]], [stance]) < 0.6, `move ends in the stance (max ${maxDiff([kick[24]], [stance]).toFixed(3)})`);
check(kick[10][IDX.ankle_L].p[2] > stance[IDX.ankle_L].p[2] + 3, "the knee lift lands on the keyed frame");
console.log(stance[IDX.ankle_R].p, kick[0][IDX.ankle_R].p, kick[0][IDX.ball_R].p, stance[IDX.ball_R].p); const drifts = kick.map((W) => v3.dist(W[IDX.ankle_R].p, stance[IDX.ankle_R].p)); const supDrift = Math.max(...drifts); console.log(drifts.map((d) => d.toFixed(2)).join(" "));
check(supDrift < 0.5, `support foot stays planted (drift ${supDrift.toFixed(3)})`);
const kickClip = new Clip("knee", kick); kickClip.fist = { L: 1, R: 1 }; kickClip.finish();

// 5. a looping mocap clip from the take (Clip.fromMocap via a .bvh path)
const sway = Clip.fromMocap("sway", bvhFile, 0, 0.59).closeLoop(4).finish();
check(sway.loop && finite(sway.poses), `Clip.fromMocap: ${sway.n} frames, looped`);

// 6. mirror
const mm = stance.map((t) => t);
const back = mirrorPose(mirrorPose(mm));
check(maxDiff([back], [stance]) < 1e-4, "mirroring twice gives the pose back");
const mir = mirrorPose(stance);
check(Math.abs(mir[IDX.hand_R].p[1] + stance[IDX.hand_L].p[1]) < 1e-4, "mirror swaps left and right across XZ");

// 7. validator
const bad = clonePose(bindPose());
// shin swung forward past the thigh: a knee bending the wrong way
setWorldRot(bad, IDX.leg_lower_L, q.mul(q.axisAngle([0, 1, 0], -1.0), bad[IDX.leg_lower_L].q));
const issues = checkPose(bad).map((i) => i.msg);
check(issues.some((m) => /knee L bends the wrong way/.test(m)), `validator flags a backward knee (${issues.length} issues)`);
const sev = (c) => Math.max(0, ...checkClip(c).map((i) => i.sev));
console.log(`     validator worst severity: jab ${sev(jab).toFixed(2)}, knee ${sev(kickClip).toFixed(2)}, sway ${sev(sway).toFixed(2)}`);

// 8. SMD round trip and the rig vmdl
const smdFile = path.join(OUT, "jab.smd");
fs.writeFileSync(smdFile, smdAnimText(jab.poses));
const back2 = readSMD(smdFile);
check(back2.length === jab.n && maxDiff(back2, jab.poses) < 0.01, `SMD write/read round trip (max ${maxDiff(back2, jab.poses).toFixed(4)})`);
const addon = path.join(OUT, "addon");
const r = writeRig({ addonDir: addon, modelDir: "models/smoketest/rig", name: "smoke_rig",
  clips: [{ name: "stand", poses: [stance, stance], loop: true }, jab, kickClip, sway], idle: "stand" });
const vm = fs.readFileSync(r.vmdl, "utf8");
const animCount = (vm.match(/_class = "AnimFile"/g) || []).length;
check(animCount === 9, `rig vmdl lists ${animCount} animations (4 clips + 4 mirrored + idle)`);
check(/bone_cull_type = "None"/.test(vm) && /anim_graph_name = ""/.test(vm) && /is_default_idle_anim = true/.test(vm), "vmdl keeps every bone, has no anim graph, has a default idle");
check(fs.existsSync(path.join(addon, "models/smoketest/rig/anims/jab_m.smd")), "mirrored clip SMD written");
const ref = fs.readFileSync(path.join(addon, "models/smoketest/rig/smoke_rig_ref.smd"), "utf8");
check((ref.match(/^smoke_rig_dot$/gm) || []).length === N, `reference SMD has one triangle per bone (${N})`);
check(fs.existsSync(path.join(addon, "materials/smoketest/rig/smoke_rig_dot.vmat")), "dark material for the hidden triangles written");

// 9. the CLI validator over the written clips
const { spawnSync } = await import("node:child_process");
const v = spawnSync(process.execPath, [path.join(path.dirname(new URL(import.meta.url).pathname), "validate.mjs"), path.join(addon, "models/smoketest/rig/anims")], { env: process.env, encoding: "utf8" });
check(v.status === 0 && /8 clips/.test(v.stdout), `validate.mjs CLI ran over the rig's clips (${(v.stdout.trim().split("\n").pop() || v.stderr).trim()})`);

console.log(`\n${fails ? fails + " FAILED" : "all passed"}; output in ${OUT}`);
process.exit(fails ? 1 : 0);
