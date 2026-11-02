import fs from "node:fs";
import { readKV3Blocks } from "./kv3.mjs";
const [,, file, block, depth] = process.argv;
const { kv, res } = readKV3Blocks(fs.readFileSync(file));
const strip = (k, v) => (v && v.data !== undefined && v.blob !== undefined ? { blob: v.blob } : (Array.isArray(v) && v.length > 64 && typeof v[0] === "number" ? `[${v.length} numbers]` : v));
const out = block ? kv[block] : kv;
console.log(JSON.stringify(out, strip, 1));
