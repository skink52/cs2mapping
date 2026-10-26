// Animation preview: renders clips on the real agent meshes to contact sheets or MP4.
//   node tools/anim/preview.mjs --smd <clip.smd> [--agent tm_professional_varf] [--view game|side|front|top]
//        [--sheet out.png --cols 6 --every 3] [--mp4 out.mp4] [--size 480x360] [--mirror]
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { Renderer, loadAgent } from "./render.mjs";
import { readSMD } from "./smd.mjs";
import { mirrorPose } from "./rig.mjs";
import { q, v3 } from "./m3.mjs";

export const AGENT_DIR = process.env.PB_AGENT_DIR || "/tmp/claude-0/agentmesh";
export const AGENTS = { timber: "tm_professional_varf", brass: "ctm_swat_varianth", pirouette: "ctm_fbi_variantb", motley: "tm_leet_variantf" };
export const VIEWS = {
  // the fight camera: audience side (-Y), a little above head height, fighter facing +X
  game: { eye: [0, -150, 58], at: [0, 0, 40], fov: 50 },
  side: { eye: [0, -260, 42], at: [0, 0, 40], fov: 30 },
  front: { eye: [260, 0, 50], at: [0, 0, 40], fov: 30 },
  back: { eye: [-260, -30, 50], at: [0, 0, 40], fov: 30 },
  three: { eye: [150, -190, 90], at: [0, 0, 40], fov: 32 },
  top: { eye: [0, -1, 330], at: [0, 0, 0], fov: 40 },
};

export function renderFrames({ actors, view = "game", size = [480, 360], label = null, frames, extra = null, labelScale = 2 }) {
  const [W, H] = size;
  const V = typeof view === "string" ? VIEWS[view] : view;
  const out = [];
  for (let f = 0; f < frames; f++) {
    const R = new Renderer(W, H);
    R.clear();
    R.camera(V.eye, V.at, V.fov);
    R.floor(0, 160, 16);
    for (const a of actors) {
      const pose = a.poses[Math.min(a.poses.length - 1, f)];
      R.drawAgent(a.agent, pose, { q: q.axisAngle([0, 0, 1], (a.yaw || 0) * Math.PI / 180), p: a.pos || [0, 0, 0], s: a.scale || 1 }, { tint: a.tint });
    }
    if (extra) extra(R, f);
    if (label) R.text(6, 6, typeof label === "function" ? label(f) : `${label} ${f}`, [240, 230, 200], labelScale);
    out.push(R.rgb);
  }
  return { W, H, frames: out };
}

function ffmpeg(args, input) {
  const r = spawnSync("ffmpeg", ["-v", "error", "-y", ...args], { input, maxBuffer: 1 << 30 });
  if (r.status !== 0) throw new Error("ffmpeg failed: " + r.stderr);
}
export function writeSheet(res, file, { cols = 6, pick = null } = {}) {
  const idx = pick || res.frames.map((_, i) => i);
  const rows = Math.ceil(idx.length / cols);
  const { W, H } = res;
  const buf = new Uint8Array(W * H * 3 * cols * rows);
  idx.forEach((fi, k) => {
    const cx = (k % cols) * W, cy = Math.floor(k / cols) * H;
    const src = res.frames[fi];
    for (let y = 0; y < H; y++) buf.set(src.subarray(y * W * 3, (y + 1) * W * 3), ((cy + y) * W * cols + cx) * 3);
  });
  ffmpeg(["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", `${W * cols}x${H * rows}`, "-i", "-", file], Buffer.from(buf.buffer));
}
export function writeMP4(res, file, fps = 32) {
  const { W, H } = res;
  const all = Buffer.concat(res.frames.map((f) => Buffer.from(f.buffer, f.byteOffset, f.byteLength)));
  ffmpeg(["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", `${W}x${H}`, "-r", String(fps), "-i", "-", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "20", file], all);
}

if (process.argv[1] && path.basename(process.argv[1]) === "preview.mjs") {
  const arg = (k, d) => { const i = process.argv.indexOf("--" + k); return i < 0 ? d : process.argv[i + 1]; };
  const flag = (k) => process.argv.includes("--" + k);
  const smd = arg("smd");
  let poses = readSMD(smd);
  if (flag("mirror")) poses = poses.map(mirrorPose);
  const agentName = AGENTS[arg("agent", "timber")] || arg("agent", "timber");
  const agent = loadAgent(path.join(AGENT_DIR, agentName + ".json"));
  const size = arg("size", "480x360").split("x").map(Number);
  const every = +arg("every", 1);
  const sel = poses.filter((_, i) => i % every === 0);
  const res = renderFrames({ actors: [{ agent, poses: sel }], view: arg("view", "game"), size, frames: sel.length, label: (f) => `${path.basename(smd, ".smd")} ${f * every}` });
  if (arg("sheet")) writeSheet(res, arg("sheet"), { cols: +arg("cols", 6) });
  if (arg("mp4")) writeMP4(res, arg("mp4"), Math.round(64 / every));
  console.log(`rendered ${sel.length} frames`);
}
