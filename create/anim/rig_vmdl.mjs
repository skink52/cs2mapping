// Builds the rig model and its animations from the clip library:
//   models/puppet_brawl/rig/pb_rig.vmdl, pb_rig_ref.smd, anims/<clip>.smd and <clip>_m.smd (mirrored,
//   used when the fighter faces left so the same side always faces the camera)
//   dist/anim_data.json: the 2D joint tracks the game core uses for hit and hurt boxes
// Usage: node tools/anim/build.mjs [addon_dir]   (needs dist/core_node.mjs from tools/build.mjs)
import fs from "node:fs";
import path from "node:path";
import url from "node:url";
import { SK, BIND, smdNodes, smdFrame, toLocals, mirrorPose, IMPORT_FIX_Q } from "./rig.mjs";
import { q, v3 } from "./m3.mjs";
import { bakeClip, JOINTS } from "./bake.mjs";
import { buildLibrary } from "./library.mjs";

const here = path.dirname(url.fileURLToPath(import.meta.url));
const root = path.join(here, "..", "..");
const outDir = process.argv[2] || path.join(root, "dist", "addon");
const C = await import(path.join(root, "dist", "core_node.mjs"));

const core = {
  CHARACTERS: C.CHARACTERS,
  MOVES: C.MOVES,
  walk: (id, dir) => { const ch = C.CHARACTERS.find((c) => c.id === id); return dir > 0 ? ch.stats.walkF : ch.stats.walkB; },
};
const t0 = Date.now();
const { clips, sets } = buildLibrary(core);

const modelDir = path.join(outDir, "models", "puppet_brawl", "rig");
const animDir = path.join(modelDir, "anims");
fs.rmSync(animDir, { recursive: true, force: true });
fs.mkdirSync(animDir, { recursive: true });

// reference: bind pose plus one tiny dark triangle on every bone, hidden inside the agent's body.
// A bone with no geometry on it gets culled when the model compiles, and a mesh made only of
// tool materials is dropped, so each bone needs a real (if invisible) triangle.
{
  let s = smdNodes() + "skeleton\n" + smdFrame(SK.map((b) => b.local), 0) + "end\ntriangles\n";
  const fmt = (v) => (Math.abs(v) < 5e-6 ? "0" : v.toFixed(5));
  SK.forEach((b, bi) => {
    const pv = BIND[bi].p;
    s += "pb_rig_dot\n";
    for (const d of [[0, 0, 0], [0.04, 0, 0], [0, 0.04, 0]]) {
      const p = q.rotate(IMPORT_FIX_Q, v3.add(pv, d));
      s += `${bi} ${fmt(p[0])} ${fmt(p[1])} ${fmt(p[2])} 0 0 1 0 0 1 ${bi} 1\n`;
    }
  });
  fs.writeFileSync(path.join(modelDir, "pb_rig_ref.smd"), s + "end\n");
}

function writeSMD(file, poses) {
  const parts = [smdNodes(), "skeleton\n"];
  poses.forEach((W, t) => parts.push(smdFrame(toLocals(W), t)));
  parts.push("end\n");
  const s = parts.join("");
  fs.writeFileSync(file, s);
  return s.length;
}

let bytes = 0;
const data = { fps: 64, joints: JOINTS, clips: {}, sets };
const entries = [];
for (const c of clips) {
  bytes += writeSMD(path.join(animDir, c.name + ".smd"), c.poses);
  bytes += writeSMD(path.join(animDir, c.name + "_m.smd"), c.poses.map(mirrorPose));
  data.clips[c.name] = bakeClip(c);
  const fade = c.fade ?? (c.key && /^(hit|block|cblock|launch|land|squat)/.test(c.key) ? 0.03 : c.loop ? 0.12 : 0.05);
  entries.push({ name: c.name, loop: c.loop, fade, idle: false });
  entries.push({ name: c.name + "_m", loop: c.loop, fade, idle: false });
  // the map's rig templates start on "idle" (StartingAnim / IdleAnim): give it a clip of that name
  if (c.key === "idle" && c.name.startsWith("timber")) entries.push({ name: "idle", src: c.name, loop: true, fade, idle: true });
}

const animNode = (c) => `\t\t\t\t\t{
\t\t\t\t\t\t_class = "AnimFile"
\t\t\t\t\t\tname = "${c.name}"
\t\t\t\t\t\tis_default_idle_anim = ${c.idle ? "true" : "false"}
\t\t\t\t\t\tactivity_name = ""
\t\t\t\t\t\tactivity_weight = 1
\t\t\t\t\t\tweight_list_name = ""
\t\t\t\t\t\tfade_in_time = ${c.fade}
\t\t\t\t\t\tfade_out_time = ${c.fade}
\t\t\t\t\t\tlooping = ${c.loop ? "true" : "false"}
\t\t\t\t\t\tdelta = false
\t\t\t\t\t\tworldSpace = false
\t\t\t\t\t\thidden = false
\t\t\t\t\t\tanim_markup_ordered = false
\t\t\t\t\t\tdisable_compression = false
\t\t\t\t\t\tanimgraph_additive = false
\t\t\t\t\t\tdelete_from_compiled_model = false
\t\t\t\t\t\tsource_filename = "models/puppet_brawl/rig/anims/${c.src || c.name}.smd"
\t\t\t\t\t\timport_bone_scales = false
\t\t\t\t\t\tstart_frame = -1
\t\t\t\t\t\tend_frame = -1
\t\t\t\t\t\tframerate = 64.0
\t\t\t\t\t\treverse = false
\t\t\t\t\t\tadditional_anim_files = [  ]
\t\t\t\t\t},`;
const vmdl = `<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:modeldoc41:version{12fc9d44-453a-4ae4-b4d9-7e2ac0bbd4e0} -->
{
\trootNode =
\t{
\t\t_class = "RootNode"
\t\tchildren =
\t\t[
\t\t\t{
\t\t\t\t_class = "MaterialGroupList"
\t\t\t\tchildren =
\t\t\t\t[
\t\t\t\t\t{
\t\t\t\t\t\t_class = "DefaultMaterialGroup"
\t\t\t\t\t\tremaps =
\t\t\t\t\t\t[
\t\t\t\t\t\t\t{
\t\t\t\t\t\t\t\tfrom = "pb_rig_dot.vmat"
\t\t\t\t\t\t\t\tto = "materials/puppet_brawl/props/pb_dark.vmat"
\t\t\t\t\t\t\t},
\t\t\t\t\t\t]
\t\t\t\t\t\tuse_global_default = false
\t\t\t\t\t\tglobal_default_material = ""
\t\t\t\t\t},
\t\t\t\t]
\t\t\t},
\t\t\t{
\t\t\t\t_class = "BoneMarkupList"
\t\t\t\tbone_cull_type = "None"
\t\t\t},
\t\t\t{
\t\t\t\t_class = "RenderMeshList"
\t\t\t\tchildren =
\t\t\t\t[
\t\t\t\t\t{
\t\t\t\t\t\t_class = "RenderMeshFile"
\t\t\t\t\t\tname = "pb_rig_ref"
\t\t\t\t\t\tfilename = "models/puppet_brawl/rig/pb_rig_ref.smd"
\t\t\t\t\t\timport_scale = 1.0
\t\t\t\t\t\timport_filter =
\t\t\t\t\t\t{
\t\t\t\t\t\t\texclude_by_default = false
\t\t\t\t\t\t\texception_list = [  ]
\t\t\t\t\t\t}
\t\t\t\t\t},
\t\t\t\t]
\t\t\t},
\t\t\t{
\t\t\t\t_class = "AnimationList"
\t\t\t\tchildren =
\t\t\t\t[
${entries.map(animNode).join("\n")}
\t\t\t\t]
\t\t\t\tdefault_root_bone_name = ""
\t\t\t},
\t\t]
\t\tmodel_archetype = ""
\t\tprimary_associated_entity = ""
\t\tanim_graph_name = ""
\t\tbase_model_name = ""
\t}
}
`;
fs.writeFileSync(path.join(modelDir, "pb_rig.vmdl"), vmdl);
fs.mkdirSync(path.join(root, "dist"), { recursive: true });
fs.writeFileSync(path.join(root, "dist", "anim_data.json"), JSON.stringify(data));
const fresh = clips.filter((c) => c.fresh).length;
console.log(`${clips.length} clips (${fresh} new, ${clips.length - fresh} from the old exporter) x2 mirrored, ${(bytes / 1e6).toFixed(1)} MB SMD, anim_data ${(JSON.stringify(data).length / 1e6).toFixed(2)} MB, ${((Date.now() - t0) / 1000).toFixed(1)} s`);
