// Extracts the skeleton (bone names, parents, parent-relative bind pose) of a compiled CS2 model,
// e.g. a stock agent, as the JSON ../anim/rig.mjs works on. Also prints the hull, sequences,
// attachments and material references, which help when setting up a rig.
//   node skeleton.mjs <model.vmdl_c | path in VPK> <out.json> [--vpk <folder with pak01_dir.vpk>] [--from agrp|model]
//   e.g. node skeleton.mjs agents/models/tm_professional/tm_professional_varf.vmdl_c ../anim/cs2_skeleton.json --vpk "<CS2>/game/csgo"
// --from agrp (default when the model has one): the animation group's bone list (the 77-bone agent
// animation skeleton the anim tools expect); --from model: the model's own skeleton (DATA block).
// The output is data from Valve's model: keep it out of git (cs2_skeleton.json is git-ignored here).
// From cs2-fighter/tools/skel.mjs (MIT), rewritten to take arguments and read the VPK in JS.
import fs from "node:fs";
import path from "node:path";
import { readKV3Blocks } from "./kv3.mjs";
import { readInput } from "./vpk.mjs";

const arr = (v) => (v ? Array.from(v, Number) : null);

export function extractSkeleton(buf, { from = null } = {}) {
  const { kv } = readKV3Blocks(buf);
  const agrp = kv.AGRP && kv.AGRP.m_decodeKey && kv.AGRP.m_decodeKey.m_boneArray;
  const useAgrp = from ? from === "agrp" : !!agrp;
  let bones;
  if (useAgrp) {
    if (!agrp) throw new Error("no AGRP bone list in this model (try --from model)");
    bones = agrp.map((b) => ({ name: b.m_name, parent: b.m_parent, pos: arr(b.m_pos), quat: arr(b.m_quat) }));
  } else {
    const sk = kv.DATA && kv.DATA.m_modelSkeleton;
    if (!sk) throw new Error("no model skeleton in the DATA block");
    bones = sk.m_boneName.map((name, i) => ({ name, parent: sk.m_nParent[i], pos: arr(sk.m_bonePosParent[i]), quat: arr(sk.m_boneRotParent[i]) }));
  }
  // parents by name, as rig.mjs and the shipped examples use
  const out = bones.map((b) => ({ name: b.name, parent: b.parent >= 0 ? bones[b.parent].name : null, pos: b.pos, quat: b.quat }));
  const D = kv.DATA || {};
  const info = {
    hull: D.m_modelInfo ? [arr(D.m_modelInfo.m_vHullMin), arr(D.m_modelInfo.m_vHullMax)] : null,
    sequences: (kv.ASEQ && kv.ASEQ.m_localSequenceNameArray) || [],
    attachments: ((kv.MDAT && kv.MDAT.m_attachments) || []).map((a) => a.key || a.m_name),
    materials: [...new Set(buf.toString("latin1").match(/[a-z0-9_/]+\.vmat/g) || [])],
  };
  return { bones: out, info };
}

if (process.argv[1] && path.basename(process.argv[1]) === "skeleton.mjs") {
  const args = process.argv.slice(2);
  const opt = (k) => { const i = args.indexOf("--" + k); return i < 0 ? null : args[i + 1]; };
  const pos = args.filter((a, i) => !a.startsWith("--") && !["--vpk", "--from"].includes(args[i - 1]));
  if (!pos[0]) { console.log("usage: node skeleton.mjs <model.vmdl_c | path in VPK> [out.json] [--vpk dir] [--from agrp|model]"); process.exit(2); }
  const { bones, info } = extractSkeleton(readInput(pos[0], opt("vpk") || process.env.CS2_VPK_DIR), { from: opt("from") });
  console.log(`${bones.length} bones, root ${bones[0].name}; hull ${JSON.stringify(info.hull)}`);
  console.log(`attachments: ${info.attachments.join(" ") || "-"}`);
  console.log(`sequences: ${info.sequences.slice(0, 20).join(" ") || "-"}${info.sequences.length > 20 ? " ..." : ""}`);
  console.log(`materials: ${info.materials.slice(0, 12).join(" ")}`);
  if (pos[1]) { fs.mkdirSync(path.dirname(path.resolve(pos[1])), { recursive: true }); fs.writeFileSync(pos[1], JSON.stringify(bones)); console.log("wrote", pos[1]); }
}
