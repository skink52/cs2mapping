// BVH reader (any BVH; written for the CMU mocap set) with forward kinematics.
//   const b = loadBVH("take.bvh"); const W = bvhWorld(b, bvhFrame(b, 0));
// From cs2-fighter/tools/anim/bvh.mjs (MIT), made project-neutral.
import fs from "node:fs";
import { q, v3, DEG } from "./m3.mjs";

export function readBVH(text) {
  const tok = text.split(/\s+/).filter(Boolean);
  let i = 0;
  const joints = [];
  const stack = [];
  let pendingEnd = false;
  while (i < tok.length) {
    const t = tok[i++];
    if (t === "ROOT" || t === "JOINT") {
      const name = tok[i++];
      joints.push({ name, parent: stack.length ? stack[stack.length - 1] : -1, offset: [0, 0, 0], channels: [], end: null });
      stack.push(joints.length - 1);
    } else if (t === "End") { i++; pendingEnd = true; stack.push(-2); }
    else if (t === "OFFSET") {
      const o = [+tok[i], +tok[i + 1], +tok[i + 2]]; i += 3;
      const top = stack[stack.length - 1];
      if (top === -2) { const p = stack[stack.length - 2]; joints[p].end = o; }
      else joints[top].offset = o;
    } else if (t === "CHANNELS") {
      const n = +tok[i++];
      joints[stack[stack.length - 1]].channels = tok.slice(i, i + n); i += n;
    } else if (t === "}") { stack.pop(); if (pendingEnd) pendingEnd = false; }
    else if (t === "MOTION") break;
  }
  // MOTION
  while (tok[i] !== "Frames:") i++;
  const frames = +tok[i + 1]; i += 2;
  while (tok[i] !== "Time:") i++;
  const dt = +tok[i + 1]; i += 2;
  const nch = joints.reduce((s, j) => s + j.channels.length, 0);
  const data = new Float32Array(frames * nch);
  for (let k = 0; k < frames * nch; k++) data[k] = +tok[i + k];
  return { joints, frames, dt, nch, data, index: Object.fromEntries(joints.map((j, k) => [j.name, k])) };
}
export const loadBVH = (file) => readBVH(fs.readFileSync(file, "utf8"));

// local rotations + root position for frame f; rotation order as listed (intrinsic)
export function bvhFrame(b, f) {
  const out = [];
  let c = f * b.nch;
  for (const j of b.joints) {
    let r = [0, 0, 0, 1];
    let p = j.offset.slice();
    for (const ch of j.channels) {
      const v = b.data[c++];
      if (ch === "Xposition") p[0] = v; else if (ch === "Yposition") p[1] = v; else if (ch === "Zposition") p[2] = v;
      else if (ch === "Xrotation") r = q.mul(r, q.axisAngle([1, 0, 0], v * DEG));
      else if (ch === "Yrotation") r = q.mul(r, q.axisAngle([0, 1, 0], v * DEG));
      else if (ch === "Zrotation") r = q.mul(r, q.axisAngle([0, 0, 1], v * DEG));
    }
    out.push({ q: r, p });
  }
  return out;
}
// world transforms (rotation, joint position) per joint
export function bvhWorld(b, locals) {
  const W = [];
  b.joints.forEach((j, k) => {
    const L = locals[k];
    if (j.parent < 0) W.push({ q: q.norm(L.q), p: L.p.slice() });
    else { const P = W[j.parent]; W.push({ q: q.norm(q.mul(P.q, L.q)), p: v3.add(P.p, q.rotate(P.q, L.p)) }); }
  });
  return W;
}
export const bvhRest = (b) => bvhWorld(b, b.joints.map((j) => ({ q: [0, 0, 0, 1], p: j.offset.slice() })));
