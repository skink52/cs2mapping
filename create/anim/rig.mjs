// The skeleton every tool works on (the CS2 agent skeleton, shared by every agent), forward
// kinematics, mirroring and the SMD animation writer.
// A pose is an array of world transforms {q, p}, one per bone, in model space
// (+X forward, +Y left, +Z up, units = CS2 units at model scale 1).
//
// The skeleton is read once, when this module is first imported, from CS2_SKELETON (a JSON file)
// or else cs2_skeleton.json next to this file. Make it with ../s2/skeleton.mjs from a stock agent;
// it isn't shipped (it is data from Valve's model). Format: [{name, parent (name or index or null),
// pos [x,y,z], quat [x,y,z,w]}], parent-relative, parents before children.
//
// From cs2-fighter/tools/anim/rig.mjs (MIT), made project-neutral.
import fs from "node:fs";
import path from "node:path";
import url from "node:url";
import { v3, q, xf } from "./m3.mjs";

const here = path.dirname(url.fileURLToPath(import.meta.url));
export const SKELETON_FILE = process.env.CS2_SKELETON || path.join(here, "cs2_skeleton.json");
if (!fs.existsSync(SKELETON_FILE)) {
  throw new Error(`No skeleton at ${SKELETON_FILE}. Extract one from a stock agent first:\n` +
    `  node ${path.join(here, "..", "s2", "skeleton.mjs")} --vpk <folder with pak01_dir.vpk> agents/models/tm_professional/tm_professional_varf.vmdl_c ${path.join(here, "cs2_skeleton.json")}\n` +
    `or set CS2_SKELETON to a skeleton JSON.`);
}
export const SK = JSON.parse(fs.readFileSync(SKELETON_FILE, "utf8"));
export const IDX = Object.fromEntries(SK.map((b, i) => [b.name, i]));
for (const b of SK) {
  b.pi = b.parent === null || b.parent === undefined || b.parent === -1 ? -1 : typeof b.parent === "number" ? b.parent : IDX[b.parent];
  if (b.pi === undefined) throw new Error(`skeleton: parent ${b.parent} of ${b.name} not found`);
  b.local = { q: q.norm(b.quat), p: b.pos.slice() };
}
export const BIND = [];
for (const b of SK) BIND.push(b.pi < 0 ? b.local : xf.mul(BIND[b.pi], b.local));
export const bindOf = (n) => BIND[IDX[n]];
export const N = SK.length;
export const children = SK.map(() => []);
SK.forEach((b, i) => { if (b.pi >= 0) children[b.pi].push(i); });

// pose from local transforms
export function fk(locals) {
  const W = new Array(N);
  for (let i = 0; i < N; i++) W[i] = SK[i].pi < 0 ? locals[i] : xf.mul(W[SK[i].pi], locals[i]);
  return W;
}
export function toLocals(W) {
  return W.map((w, i) => (SK[i].pi < 0 ? w : xf.mul(xf.inv(W[SK[i].pi]), w)));
}
export const bindLocals = () => SK.map((b) => ({ q: b.local.q.slice(), p: b.local.p.slice() }));
export const bindPose = () => fk(bindLocals());

// Recompute world transforms below bone i after its world rotation changed, keeping every
// descendant's local transform (used by IK / pose edits).
export function setWorldRot(W, i, rot) {
  const L = toLocalsSub(W, i);
  W[i] = { q: q.norm(rot), p: W[i].p };
  refreshSub(W, i, L);
}
export function setWorld(W, i, t) {
  const L = toLocalsSub(W, i);
  W[i] = { q: q.norm(t.q), p: t.p.slice() };
  refreshSub(W, i, L);
}
function toLocalsSub(W, i) {
  const L = new Map();
  const walk = (j) => { for (const c of children[j]) { L.set(c, xf.mul(xf.inv(W[j]), W[c])); walk(c); } };
  walk(i);
  return L;
}
function refreshSub(W, i, L) {
  const walk = (j) => { for (const c of children[j]) { W[c] = xf.mul(W[j], L.get(c)); walk(c); } };
  walk(i);
}

// mirror a pose across the model's XZ plane (left <-> right): y -> -y, bones swap sides
const MIRROR_NAME = (n) => n.replace(/_L(?=$|_)/, "_@").replace(/_R(?=$|_)/, "_L").replace(/_@/, "_R");
export const MIRROR = SK.map((b) => IDX[MIRROR_NAME(b.name)] ?? IDX[b.name]);
// The rig's bones have their own axes; mirroring world rotations needs, per bone pair, the bind
// relation: W'_i = M W_mirror(i) M * C_i, where C_i maps the mirrored bind frame to bone i's bind.
const MREF = (t) => ({ q: [-t.q[0], t.q[1], -t.q[2], t.q[3]], p: [t.p[0], -t.p[1], t.p[2]] });   // reflect across XZ
const MCORR = SK.map((b, i) => {
  const j = MIRROR[i];
  const mb = MREF(BIND[j]);
  return q.norm(q.mul(q.conj(mb.q), BIND[i].q));
});
export function mirrorPose(W) {
  return W.map((_, i) => {
    const j = MIRROR[i];
    const r = MREF(W[j]);
    return { q: q.norm(q.mul(r.q, MCORR[i])), p: r.p };
  });
}

// ------------------------------------------------------------------ SMD output
// ModelDoc turns every SMD 90 degrees about Z on import (seen in the compiled props), so the root
// bone and the reference mesh are written turned -90 degrees to cancel it.
const FIX = q.axisAngle([0, 0, 1], -Math.PI / 2);
const fmt = (v) => (Math.abs(v) < 5e-6 ? "0" : v.toFixed(5));
export function smdNodes() {
  let s = "version 1\nnodes\n";
  SK.forEach((b, i) => { s += `${i} "${b.name}" ${b.pi}\n`; });
  return s + "end\n";
}
export function smdFrame(locals, time) {
  let s = `time ${time}\n`;
  locals.forEach((t, i) => {
    let p = t.p, r = t.q;
    if (SK[i].pi < 0) { p = q.rotate(FIX, p); r = q.mul(FIX, r); }
    const e = q.toEulerSMD(r);
    s += `${i} ${fmt(p[0])} ${fmt(p[1])} ${fmt(p[2])} ${fmt(e[0])} ${fmt(e[1])} ${fmt(e[2])}\n`;
  });
  return s;
}
export function smdAnim(poses) {
  let s = smdNodes() + "skeleton\n";
  poses.forEach((W, t) => { s += smdFrame(toLocals(W), t); });
  return s + "end\n";
}
export const IMPORT_FIX_Q = FIX;
