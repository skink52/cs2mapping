// Renders strikes found by analyze.mjs as strips on an agent mesh (rows = strikes, columns =
// moments around the peak), turned so each strike goes toward +X. Use it to pick mocap moments.
//   node gallery.mjs <out.png> <punch|kick|all> <take.bvh>... --agent <agent.json|name>
//        [--side L|R] [--max 12] [--only 0,3] [--offsets -0.3,-0.1,0,0.2]
// From cs2-fighter/tools/anim/gallery.mjs (MIT), made project-neutral.
import { loadBVH } from "./bvh.mjs";
import { makeRetargeter } from "./retarget.mjs";
import { analyzeTake } from "./analyze.mjs";
import { renderFrames, writeSheet, agentFile } from "./preview.mjs";
import { loadAgent } from "./render.mjs";
import { normalisePoses } from "./clip.mjs";
export { normalisePoses, gazeDir, chestDir } from "./clip.mjs";

if (process.argv[1] && process.argv[1].endsWith("gallery.mjs")) {
  const args = process.argv.slice(2);
  const opt = (k, d) => { const i = args.indexOf("--" + k); return i < 0 ? d : args[i + 1]; };
  const out = args[0], kind = args[1];
  const files = args.slice(2).filter((a, i, A) => a.endsWith(".bvh"));
  const side = opt("side", null), max = +opt("max", 12);
  const offsets = (opt("offsets", kind === "kick" ? "-0.45,-0.3,-0.18,-0.08,0,0.12,0.3" : "-0.3,-0.2,-0.12,-0.06,0,0.1,0.25")).split(",").map(Number);
  if (!out || !kind || !opt("agent")) { console.log("usage: node gallery.mjs <out.png> <punch|kick|all> <take.bvh>... --agent <agent.json|name>"); process.exit(2); }
  const agent = loadAgent(agentFile(opt("agent")));
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
