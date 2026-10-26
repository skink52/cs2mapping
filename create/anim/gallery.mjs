// Renders strikes found by analyze.mjs as strips on the agent mesh (rows = strikes, columns =
// moments around the peak), turned so each strike goes toward +X like a fighter facing right.
//   node tools/anim/gallery.mjs <out.png> <kind:punch|kick|all> <take.bvh>... [--side L|R] [--max 12] [--view game]
import path from "node:path";
import { loadBVH } from "./bvh.mjs";
import { makeRetargeter } from "./retarget.mjs";
import { analyzeTake } from "./analyze.mjs";
import { renderFrames, writeSheet, AGENT_DIR } from "./preview.mjs";
import { loadAgent } from "./render.mjs";
import { v3, q } from "./m3.mjs";
import { IDX, BIND } from "./rig.mjs";

// the way the head faces (the agents face +X in their bind pose)
const HEAD_FWD_LOCAL = q.rotate(q.conj(BIND[IDX.head_0].q), [1, 0, 0]);
export function gazeDir(W) {
  const d = q.rotate(W[IDX.head_0].q, HEAD_FWD_LOCAL);
  return v3.norm([d[0], d[1], 0]);
}
export function chestDir(W) {
  const l = v3.sub(W[IDX.arm_upper_L].p, W[IDX.arm_upper_R].p);
  const lh = v3.sub(W[IDX.leg_upper_L].p, W[IDX.leg_upper_R].p);
  const left = v3.norm([l[0] + lh[0], l[1] + lh[1], 0]);
  return [left[1], -left[0], 0];
}
// turn + move a pose sequence so that at frame `ref` the body (by="chest") or the gaze
// (by="gaze") faces +X and the pelvis is over 0,0
export function normalisePoses(poses, ref, by = "chest") {
  const P = poses[ref];
  const fwd = by === "gaze" ? gazeDir(P) : chestDir(P);
  const yaw = Math.atan2(fwd[1], fwd[0]);
  const rot = q.axisAngle([0, 0, 1], -yaw);
  const c = q.rotate(rot, P[IDX.pelvis].p);
  return poses.map((W) => W.map((t) => { const p = q.rotate(rot, t.p); return { q: q.mul(rot, t.q), p: [p[0] - c[0], p[1] - c[1], p[2]] }; }));
}

if (process.argv[1] && process.argv[1].endsWith("gallery.mjs")) {
  const args = process.argv.slice(2);
  const opt = (k, d) => { const i = args.indexOf("--" + k); return i < 0 ? d : args[i + 1]; };
  const out = args[0], kind = args[1];
  const files = args.slice(2).filter((a, i, A) => a.endsWith(".bvh"));
  const side = opt("side", null), max = +opt("max", 12), view = opt("view", "game");
  const offsets = (opt("offsets", kind === "kick" ? "-0.45,-0.3,-0.18,-0.08,0,0.12,0.3" : "-0.3,-0.2,-0.12,-0.06,0,0.1,0.25")).split(",").map(Number);
  const agent = loadAgent(path.join(AGENT_DIR, "tm_professional_varf.json"));
  const rows = [];
  for (const f of files) {
    const r = analyzeTake(f);
    const b = loadBVH(f);
    const rt = makeRetargeter(b);
    const fps = 1 / b.dt;
    let evs = r.events.filter((e) => (kind === "all" || e.kind === kind) && (!side || e.side === side));
    if (opt("only")) { const keep = opt("only").split(",").map(Number); evs = evs.filter((e, i) => keep.includes(i)); }
    for (const e of evs) {
      const frames = offsets.map((o) => Math.max(0, Math.min(b.frames - 1, Math.round(e.f + o * fps))));
      const poses = normalisePoses(frames.map((fr) => rt(fr)), offsets.indexOf(0));
      rows.push({ label: `${r.file.replace(".bvh", "")} ${e.kind}${e.side} T${e.t} R${e.reach} H${e.height}`, poses });
      if (rows.length >= max) break;
    }
    if (rows.length >= max) break;
  }
  const W = 220, H = 220;
  const all = [];
  for (const row of rows) {
    const res = renderFrames({ actors: [{ agent, poses: row.poses }], view: { eye: [20, -190, 62], at: [20, 0, 38], fov: 36 }, size: [W, H], frames: row.poses.length, labelScale: 1, label: (k) => (k === 0 ? row.label : offsets[k] + "S") });
    all.push(...res.frames);
  }
  writeSheet({ W, H, frames: all }, out, { cols: offsets.length });
  console.log(`${rows.length} strikes -> ${out}`);
}
