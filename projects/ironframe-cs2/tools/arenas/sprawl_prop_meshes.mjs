// LOD 0 meshes of stock CS2 models for tools/arenas/sprawl_preview_bl.py (see sprawl_preview.py).
//   node tools/arenas/sprawl_prop_meshes.mjs <models.txt> <out.json> [CS2 game/csgo folder]
// models.txt: one "models/....vmdl" per line. out.json: {model: [{material, P: [x,y,z,...], I: [i,...]}]}
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const s2 = path.resolve(here, "..", "..", "..", "..", "create", "s2");
const { extractProp } = await import(pathToFileURL(path.join(s2, "prop_mesh.mjs")).href);
const { readInput } = await import(pathToFileURL(path.join(s2, "vpk.mjs")).href);

const [list, out, vpk = "C:/Program Files (x86)/Steam/steamapps/common/Counter-Strike Global Offensive/game/csgo"] = process.argv.slice(2);
if (!list || !out) { console.log("usage: node sprawl_prop_meshes.mjs <models.txt> <out.json> [game/csgo]"); process.exit(2); }
const all = {};
for (const m of fs.readFileSync(list, "utf8").split(/\r?\n/).filter(Boolean)) {
  try {
    const r = await extractProp(readInput(m + "_c", vpk));
    all[m] = r.meshes.map((x) => ({ material: x.material, P: Array.from(x.P, (v) => Math.round(v * 100) / 100), I: Array.from(x.I) }));
  } catch (e) { console.log("skip " + m + ": " + e.message); }
}
fs.writeFileSync(out, JSON.stringify(all));
console.log(Object.keys(all).length + " models -> " + out);
