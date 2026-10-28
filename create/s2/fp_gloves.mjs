// An agent's first-person default gloves (the glove draw call of its firstperson_default_gloves_arms mesh) as JSON:
// {material, P, N, UV, J (bone names), W, I}. UVs are already in ModelDoc DMX orientation (checked on tm_phoenix against the
// Source 2 Viewer decompile: positions, UVs, normals and weights identical). Feed it to a DMX writer on the agent skeleton
// (mg_trenchwarfare tools/agent_gloves.py). Keep the JSON out of git (Valve data).
//   node fp_gloves.mjs agents/models/ctm_sas/ctm_sas.vmdl_c sas_glove.json --vpk "<CS2>/game/csgo"
import fs from "node:fs";
import { extractAgent } from "./agent_mesh.mjs";
import { readInput } from "./vpk.mjs";

const args = process.argv.slice(2);
const vi = args.indexOf("--vpk"); const vpk = vi >= 0 ? args.splice(vi, 2)[1] : process.env.CS2_VPK_DIR;
const [f, out] = args;
if (!out) { console.log("usage: node fp_gloves.mjs <agent vmdl_c | path in the VPK> <out.json> [--vpk <folder with pak01_dir.vpk>]"); process.exit(2); }
const a = await extractAgent(readInput(f, vpk), { meshGroupMask: 0xffff });
const ms = a.meshes.filter((m) => m.mesh === "firstperson_default_gloves_arms" && /glove/.test(m.material));
if (!ms.length) { console.error("no first-person glove draw call in " + f); process.exit(1); }
const m = ms[0], names = a.skeleton.map((b) => b.name);
fs.writeFileSync(out, JSON.stringify({ material: m.material, P: Array.from(m.P), N: Array.from(m.N), UV: Array.from(m.UV),
  J: Array.from(m.J).map((j) => names[j]), W: Array.from(m.W), I: Array.from(m.I) }));
console.log(f, m.P.length / 3, "verts", m.I.length / 3, "tris", m.material);
