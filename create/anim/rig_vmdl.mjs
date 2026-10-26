// Writes an invisible animation rig for CS2: a ModelDoc .vmdl that holds every clip as an
// animation, its reference SMD (one tiny hidden triangle per bone, so ModelDoc keeps every bone),
// one SMD per clip plus a mirrored "<clip>_m" twin, and a dark material for the hidden triangles.
// In game an agent (or any model with the same bone names) is bone-merged onto the rig and the
// script plays clips on the rig (see README.md, "Driving the rig in game").
//
//   import { writeRig } from "./rig_vmdl.mjs";
//   writeRig({ addonDir: "out/addon", modelDir: "models/mygame/rig", name: "mygame_rig",
//              clips: [{ name: "idle", poses, loop: true }, { name: "jab", poses }], idle: "idle" });
//
//   CLI (from SMDs you already have):
//   node rig_vmdl.mjs <addon content dir> <models/.../rig> <name> <clip.smd>... [--loop a,b] [--idle clip] [--no-mirror] [--fps 64]
//
// From cs2-fighter/tools/anim/build.mjs (MIT), made project-neutral.
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { SK, BIND, smdNodes, smdFrame, toLocals, mirrorPose, IMPORT_FIX_Q } from "./rig.mjs";
import { q, v3 } from "./m3.mjs";

const fmt = (v) => (Math.abs(v) < 5e-6 ? "0" : v.toFixed(5));

// skeletal animation SMD text for a list of world poses
export function smdAnimText(poses) {
  const parts = [smdNodes(), "skeleton\n"];
  poses.forEach((W, t) => parts.push(smdFrame(toLocals(W), t)));
  parts.push("end\n");
  return parts.join("");
}

// Reference mesh: bind pose plus one 0.04-unit triangle at every bone, weighted 1.0 to it.
// A bone with no geometry is culled when the model compiles, and a mesh made only of tool
// materials is dropped, so each bone gets a real (if invisible) triangle.
export function refSMDText(matName) {
  let s = smdNodes() + "skeleton\n" + smdFrame(SK.map((b) => b.local), 0) + "end\ntriangles\n";
  SK.forEach((b, bi) => {
    const pv = BIND[bi].p;
    s += matName + "\n";
    for (const d of [[0, 0, 0], [0.04, 0, 0], [0, 0.04, 0]]) {
      const p = q.rotate(IMPORT_FIX_Q, v3.add(pv, d));
      s += `${bi} ${fmt(p[0])} ${fmt(p[1])} ${fmt(p[2])} 0 0 1 0 0 1 ${bi} 1\n`;
    }
  });
  return s + "end\n";
}

// a solid-colour PNG (no dependencies)
export function solidPNG(w, h, [r, g, b]) {
  const crcT = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
  const crc = (buf) => { let c = 0xffffffff; for (const x of buf) c = crcT[(c ^ x) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  const chunk = (type, data) => {
    const td = Buffer.concat([Buffer.from(type, "latin1"), data]);
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const c = Buffer.alloc(4); c.writeUInt32BE(crc(td));
    return Buffer.concat([len, td, c]);
  };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) raw.set([r, g, b], y * (w * 3 + 1) + 1 + x * 3);
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", ihdr), chunk("IDAT", zlib.deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]);
}

const animNode = (e, modelDir) => `\t\t\t\t\t{
\t\t\t\t\t\t_class = "AnimFile"
\t\t\t\t\t\tname = "${e.name}"
\t\t\t\t\t\tis_default_idle_anim = ${e.idle ? "true" : "false"}
\t\t\t\t\t\tactivity_name = ""
\t\t\t\t\t\tactivity_weight = 1
\t\t\t\t\t\tweight_list_name = ""
\t\t\t\t\t\tfade_in_time = ${e.fade}
\t\t\t\t\t\tfade_out_time = ${e.fade}
\t\t\t\t\t\tlooping = ${e.loop ? "true" : "false"}
\t\t\t\t\t\tdelta = false
\t\t\t\t\t\tworldSpace = false
\t\t\t\t\t\thidden = false
\t\t\t\t\t\tanim_markup_ordered = false
\t\t\t\t\t\tdisable_compression = false
\t\t\t\t\t\tanimgraph_additive = false
\t\t\t\t\t\tdelete_from_compiled_model = false
\t\t\t\t\t\tsource_filename = "${modelDir}/anims/${e.src || e.name}.smd"
\t\t\t\t\t\timport_bone_scales = false
\t\t\t\t\t\tstart_frame = -1
\t\t\t\t\t\tend_frame = -1
\t\t\t\t\t\tframerate = ${e.fps.toFixed(1)}
\t\t\t\t\t\treverse = false
\t\t\t\t\t\tadditional_anim_files = [  ]
\t\t\t\t\t},`;

export function vmdlText({ modelDir, name, entries, dotMat, material }) {
  return `<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:modeldoc41:version{12fc9d44-453a-4ae4-b4d9-7e2ac0bbd4e0} -->
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
\t\t\t\t\t\t\t\tfrom = "${dotMat}.vmat"
\t\t\t\t\t\t\t\tto = "${material}"
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
\t\t\t\t\t\tname = "${name}_ref"
\t\t\t\t\t\tfilename = "${modelDir}/${name}_ref.smd"
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
${entries.map((e) => animNode(e, modelDir)).join("\n")}
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
}

// addonDir: the addon's content folder (holds models/, materials/).
// modelDir: where the rig goes, relative to it ("models/mygame/rig"); paths in the vmdl use it.
// clips: [{ name, poses, loop, fade }]  (or { name, smd: text } to copy an SMD as is)
//   fade = blend time in seconds (fade_in = fade_out); default 0.12 for loops, 0.05 otherwise.
// idle: a clip that also goes in as "idle" with is_default_idle_anim = true (prop_dynamic's
//   StartingAnim / IdleAnim can then say "idle"). If a clip is itself called "idle", it is the default.
// material: vmat the hidden triangles use; by default a dark vmat + PNG are written next to the rig.
// mirror: also write "<clip>_m" (left/right swapped) for every clip. fps: animation frame rate.
export function writeRig({ addonDir, modelDir, name, clips, idle = null, material = null, mirror = true, fps = 64, clean = true }) {
  modelDir = modelDir.replace(/\\/g, "/").replace(/\/$/, "");
  const outModel = path.join(addonDir, modelDir);
  const animDir = path.join(outModel, "anims");
  if (clean) fs.rmSync(animDir, { recursive: true, force: true });
  fs.mkdirSync(animDir, { recursive: true });
  const dotMat = name + "_dot";
  if (!material) {
    const matRel = "materials/" + modelDir.replace(/^models\//, "") + "/" + dotMat;
    const matDir = path.join(addonDir, path.dirname(matRel));
    fs.mkdirSync(matDir, { recursive: true });
    fs.writeFileSync(path.join(addonDir, matRel + "_color.png"), solidPNG(16, 16, [20, 18, 22]));
    fs.writeFileSync(path.join(addonDir, matRel + ".vmat"), `// hidden bone triangles of ${name}\nLayer0\n{\n\tshader "csgo_vertexlitgeneric.vfx"\n\tTextureColor "${matRel}_color.png"\n\tTextureNormal "materials/default/default_normal.tga"\n\tTextureRoughness "materials/default/default_rough.tga"\n}\n`);
    material = matRel + ".vmat";
  }
  fs.writeFileSync(path.join(outModel, name + "_ref.smd"), refSMDText(dotMat));
  const entries = [];
  let bytes = 0;
  const names = new Set(clips.map((c) => c.name));
  for (const c of clips) {
    if (!/^[A-Za-z0-9_]+$/.test(c.name)) throw new Error(`clip name "${c.name}": use letters, digits and _ only`);
    const fade = c.fade ?? (c.loop ? 0.12 : 0.05);
    const text = c.smd || smdAnimText(c.poses);
    fs.writeFileSync(path.join(animDir, c.name + ".smd"), text); bytes += text.length;
    entries.push({ name: c.name, loop: !!c.loop, fade, idle: c.name === "idle" && !idle, fps });
    if (mirror) {
      if (!c.poses) throw new Error(`clip ${c.name}: mirroring needs poses (read the SMD with smd.mjs)`);
      const m = smdAnimText(c.poses.map(mirrorPose));
      fs.writeFileSync(path.join(animDir, c.name + "_m.smd"), m); bytes += m.length;
      entries.push({ name: c.name + "_m", loop: !!c.loop, fade, idle: false, fps });
    }
  }
  if (idle) {
    const c = clips.find((x) => x.name === idle);
    if (!c) throw new Error(`idle clip ${idle} not in clips`);
    if (names.has("idle") && idle !== "idle") throw new Error(`a clip is already called "idle"`);
    if (idle === "idle") entries.find((e) => e.name === "idle").idle = true;
    else entries.push({ name: "idle", src: idle, loop: true, fade: c.fade ?? 0.12, idle: true, fps });
  }
  const vmdl = vmdlText({ modelDir, name, entries, dotMat, material });
  const vmdlPath = path.join(outModel, name + ".vmdl");
  fs.writeFileSync(vmdlPath, vmdl);
  return { vmdl: vmdlPath, clips: entries.length, bytes, material };
}

if (process.argv[1] && path.basename(process.argv[1]) === "rig_vmdl.mjs") {
  const args = process.argv.slice(2);
  const opt = (k) => { const i = args.indexOf("--" + k); return i < 0 ? null : args[i + 1]; };
  const flags = new Set(["--loop", "--idle", "--fps", "--material"]);
  const pos = args.filter((a, i) => !a.startsWith("--") && !flags.has(args[i - 1]));
  if (pos.length < 4) { console.log("usage: node rig_vmdl.mjs <addon content dir> <models/.../rig> <name> <clip.smd>... [--loop a,b] [--idle clip] [--no-mirror] [--fps 64] [--material x.vmat]"); process.exit(2); }
  const [addonDir, modelDir, name, ...smds] = pos;
  const loops = new Set((opt("loop") || "").split(",").filter(Boolean));
  const { readSMD } = await import("./smd.mjs");
  const tmp = smds.map((f) => ({ name: path.basename(f, ".smd"), poses: readSMD(f), loop: loops.has(path.basename(f, ".smd")) }));
  const r = writeRig({ addonDir, modelDir, name, clips: tmp, idle: opt("idle"), material: opt("material"), mirror: !args.includes("--no-mirror"), fps: +(opt("fps") || 64), clean: false });
  console.log(`${r.vmdl}: ${r.clips} animations, ${(r.bytes / 1e6).toFixed(2)} MB SMD`);
}
