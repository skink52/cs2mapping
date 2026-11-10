// Real bounds of many compiled models in one run, for tools/visualcheck.py and tools/propatlas.py: a model that can't be read is
// reported and skipped instead of ending the run (prop_mesh.mjs stops at the first one).
//   node bounds_batch.mjs <list.json> <out.json>
// list.json: [{"path": "<.vmdl_c file or path in the VPK>", "vpk": "<folder with pak01_dir.vpk> | null"}]
// out.json:  {"<path>": {"lo": [x,y,z], "hi": [x,y,z], "size": [...], "materials": [...]} | {"error": "..."}}
// Node 22.15+ (zstd). Reads with prop_mesh.mjs's propBounds (embedded meshes, LOD 0); models whose blocks the KV3 reader doesn't know get
// an error entry (visualcheck.py then tries the model's source SMD).
import fs from "node:fs";
import { propBounds } from "./prop_mesh.mjs";
import { readInput } from "./vpk.mjs";

const [listFile, outFile] = process.argv.slice(2);
if (!listFile || !outFile) { console.log("usage: node bounds_batch.mjs <list.json> <out.json>"); process.exit(2); }
const list = JSON.parse(fs.readFileSync(listFile, "utf8"));
const out = {};
let ok = 0;
for (const { path, vpk } of list) {
  try {
    const b = await propBounds(readInput(path, vpk || undefined));
    if (!b.lo.every(Number.isFinite)) throw new Error("no vertices");
    out[path] = b; ok++;
  } catch (err) {
    out[path] = { error: String(err && err.message || err).slice(0, 200) };
  }
}
fs.writeFileSync(outFile, JSON.stringify(out));
console.log(`bounds: ${ok} of ${list.length} models read`);
