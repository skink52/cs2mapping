// Joint checker: walks every frame of every clip and reports poses a body can't make or that
// skin badly: knees and elbows bending the wrong way, thighs twisted or swung into the torso,
// ankles past their range, hands, elbows and knees inside the torso or head.
//   node validate.mjs <clip.smd | folder of SMDs>... [--min 0.5]     (worst first)
//   in code: checkPose(W) -> [{j, msg, sev}], checkClip({poses}) -> [{msg, frames, sev}]
// Run it after every animation change; a severity under ~1 is usually fine on screen.
// From cs2-fighter/tools/anim/validate.mjs (MIT), made project-neutral.
import fs from "node:fs";
import path from "node:path";
import { q, v3, clamp, DEG } from "./m3.mjs";
import { IDX, BIND } from "./rig.mjs";
import { footAngles } from "./pose.mjs";
import { HINGE_LOCAL } from "./post.mjs";
import { readSMD } from "./smd.mjs";

const P = (W, n) => W[IDX[n]].p;
const local = (W, a, v) => q.rotate(q.conj(W[IDX[a]].q), v);

// natural bend directions (bone-local) of knees and elbows: the hinge axes post.mjs's IK uses
const HINGE = {};
for (const s of ["L", "R"]) { HINGE["knee" + s] = HINGE_LOCAL["leg_upper_" + s]; HINGE["elbow" + s] = HINGE_LOCAL["arm_upper_" + s]; }
// a hinge: bend angle and how well the bend plane matches the natural one (1 = exactly, -1 = reversed)
function hinge(W, upper, lower, end, H) {
  const a = v3.norm(local(W, upper, v3.sub(P(W, lower), P(W, upper))));
  const b = v3.norm(local(W, upper, v3.sub(P(W, end), P(W, lower))));
  const bend = Math.acos(clamp(v3.dot(a, b), -1, 1)) / DEG;
  const n = v3.cross(a, b);
  return { bend, align: v3.len(n) > 1e-4 ? v3.dot(v3.norm(n), H) : 1 };
}
// the thigh in the pelvis frame against bind: swing (flexion forward +, abduction out +) and twist
const BIND_REL = {};
for (const s of ["L", "R"]) BIND_REL[s] = q.mul(q.conj(BIND[IDX.pelvis].q), BIND[IDX["leg_upper_" + s]].q);
function hip(W, s) {
  const pq = W[IDX.pelvis].q, tq = W[IDX["leg_upper_" + s]].q;
  // body axes from the pelvis: forward, left, up (bind pelvis -> model axes)
  const fwd = q.rotate(pq, q.rotate(q.conj(BIND[IDX.pelvis].q), [1, 0, 0]));
  const left = q.rotate(pq, q.rotate(q.conj(BIND[IDX.pelvis].q), [0, 1, 0]));
  const up = q.rotate(pq, q.rotate(q.conj(BIND[IDX.pelvis].q), [0, 0, 1]));
  const dir = v3.norm(v3.sub(P(W, "leg_lower_" + s), P(W, "leg_upper_" + s)));
  const flex = Math.atan2(v3.dot(dir, fwd), -v3.dot(dir, up)) / DEG;
  const sag = Math.hypot(v3.dot(dir, fwd), v3.dot(dir, up)) > 0.5;   // flexion only means something off the side
  const out = (s === "L" ? 1 : -1) * Math.asin(clamp(v3.dot(dir, left), -1, 1)) / DEG;
  // twist: where the knee points against where it would point for this thigh direction with the
  // hips square (forward for a hanging thigh, up for a thigh raised level, forward when it swings out)
  const n = q.rotate(tq, HINGE_LOCAL["leg_upper_" + s]);
  const kneeFront = v3.norm(v3.cross(dir, n));
  let nat = v3.cross(dir, left);
  if (v3.len(nat) < 0.35) nat = v3.perp(fwd, dir);
  nat = v3.norm(v3.perp(nat, dir));
  let twist = Math.atan2(v3.dot(v3.cross(nat, kneeFront), dir), v3.dot(nat, kneeFront)) / DEG;
  if (s === "R") twist = -twist;
  return { flex, out, twist, sag };
}
// distance from a point to a segment
function segDist(p, a, b) {
  const ab = v3.sub(b, a), t = clamp(v3.dot(v3.sub(p, a), ab) / Math.max(1e-6, v3.dot(ab, ab)), 0, 1);
  return v3.len(v3.sub(p, v3.add(a, v3.mul(ab, t))));
}
const LIM = { kneeAlign: 0.35, elbowAlign: 0.2, bendMin: 18, flexMax: 125, flexMin: -45, outMax: 80, inMax: 35, twist: 50, torsoR: 6.0, headR: 6.5 };

export function checkPose(W) {
  const out = [];
  for (const s of ["L", "R"]) {
    const k = hinge(W, "leg_upper_" + s, "leg_lower_" + s, "ankle_" + s, HINGE["knee" + s]);
    if (k.bend > LIM.bendMin && k.align < LIM.kneeAlign) out.push({ j: "knee" + s, v: k.align, msg: `knee ${s} bends the wrong way (${k.bend.toFixed(0)}deg, align ${k.align.toFixed(2)})`, sev: (1 - k.align) * k.bend / 30 });
    const e = hinge(W, "arm_upper_" + s, "arm_lower_" + s, "hand_" + s, HINGE["elbow" + s]);
    if (e.bend > LIM.bendMin && e.align < LIM.elbowAlign) out.push({ j: "elbow" + s, msg: `elbow ${s} bends the wrong way (${e.bend.toFixed(0)}deg, align ${e.align.toFixed(2)})`, sev: (1 - e.align) * e.bend / 40 });
    const h = hip(W, s);
    if (h.sag && h.flex > LIM.flexMax) out.push({ j: "hip" + s, msg: `thigh ${s} swung into the torso (flex ${h.flex.toFixed(0)})`, sev: (h.flex - LIM.flexMax) / 15 });
    if (h.sag && h.flex < LIM.flexMin) out.push({ j: "hip" + s, msg: `thigh ${s} too far back (flex ${h.flex.toFixed(0)})`, sev: (LIM.flexMin - h.flex) / 15 });
    if (h.out > LIM.outMax) out.push({ j: "hip" + s, msg: `thigh ${s} too far out (${h.out.toFixed(0)})`, sev: (h.out - LIM.outMax) / 15 });
    if (h.out < -LIM.inMax) out.push({ j: "hip" + s, msg: `thigh ${s} crosses the body (${h.out.toFixed(0)})`, sev: (-LIM.inMax - h.out) / 15 });
    if (Math.abs(h.twist) > LIM.twist) out.push({ j: "hip" + s, msg: `thigh ${s} twisted (${h.twist.toFixed(0)})`, sev: (Math.abs(h.twist) - LIM.twist) / 25 });
    const a = footAngles(W, s);
    const air = Math.min(P(W, "ankle_" + s)[2], P(W, "ball_" + s)[2] + 2) >= 6;
    if (air && (a.plantar > 62 || a.plantar < -27 || Math.abs(a.yaw) > 27 || Math.abs(a.roll) > 27))
      out.push({ j: "ankle" + s, msg: `ankle ${s} out of range (p ${a.plantar.toFixed(0)} y ${a.yaw.toFixed(0)} r ${a.roll.toFixed(0)})`, sev: 1 });
  }
  // inside the body: torso capsule pelvis -> neck, head sphere
  const t0 = P(W, "spine_1"), t1 = P(W, "spine_3");
  const hc = v3.add(P(W, "head_0"), q.rotate(W[IDX.head_0].q, [3.5, 0, 0]));
  for (const s of ["L", "R"]) {
    for (const [n, r] of [["hand_", 1.5], ["arm_lower_", 2], ["leg_lower_", 2.5]]) {
      const p = P(W, n + s);
      const d = segDist(p, t0, t1) - r;
      if (d < LIM.torsoR - 2) out.push({ j: n + s, msg: `${n}${s} inside the torso (${d.toFixed(1)})`, sev: (LIM.torsoR - d) / 3 });
      if (n !== "leg_lower_") {
        const dh = v3.len(v3.sub(p, hc)) - r;
        if (dh < LIM.headR - 2) out.push({ j: n + s, msg: `${n}${s} inside the head (${dh.toFixed(1)})`, sev: (LIM.headR - dh) / 3 });
      }
    }
    // mid forearm
    const mid = v3.mul(v3.add(P(W, "arm_lower_" + s), P(W, "hand_" + s)), 0.5);
    if (segDist(mid, t0, t1) < LIM.torsoR - 2.5) out.push({ j: "forearm" + s, msg: `forearm ${s} through the torso`, sev: 1 });
    if (v3.len(v3.sub(mid, hc)) < LIM.headR - 2.5) out.push({ j: "forearm" + s, msg: `forearm ${s} through the head`, sev: 1 });
  }
  return out;
}

export function checkClip(c) {
  const issues = {};
  c.poses.forEach((W, f) => {
    for (const it of checkPose(W)) {
      const k = it.j + "|" + it.msg.split(" (")[0];
      const e = issues[k] || (issues[k] = { frames: [], sev: 0, msg: it.msg });
      e.frames.push(f); e.sev = Math.max(e.sev, it.sev);
      if (it.sev >= e.sev) e.msg = it.msg;
    }
  });
  return Object.values(issues);
}

const main = process.argv[1] && path.basename(process.argv[1]) === "validate.mjs";
if (main) {
  const args = process.argv.slice(2);
  const mi = args.indexOf("--min");
  const min = mi < 0 ? 0 : +args[mi + 1];
  const inputs = args.filter((a, i) => !a.startsWith("--") && args[i - 1] !== "--min");
  if (!inputs.length) { console.log("usage: node validate.mjs <clip.smd | folder>... [--min severity]"); process.exit(2); }
  const files = [];
  for (const a of inputs) {
    if (fs.statSync(a).isDirectory()) for (const f of fs.readdirSync(a).sort()) { if (f.endsWith(".smd") && !f.endsWith("_ref.smd")) files.push(path.join(a, f)); }
    else files.push(a);
  }
  const rows = [];
  for (const f of files) for (const it of checkClip({ poses: readSMD(f) })) if (it.sev >= min) rows.push({ clip: path.basename(f, ".smd"), ...it });
  rows.sort((a, b) => b.sev - a.sev);
  const w = Math.max(8, ...rows.map((r) => r.clip.length));
  for (const r of rows) {
    const fr = r.frames.length > 8 ? `${r.frames[0]}..${r.frames[r.frames.length - 1]} (${r.frames.length})` : r.frames.join(",");
    console.log(`${r.sev.toFixed(1).padStart(5)}  ${r.clip.padEnd(w)} ${r.msg}  @ ${fr}`);
  }
  console.log(`${files.length} clips, ${rows.length} issues`);
}
