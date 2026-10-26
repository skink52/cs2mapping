// Reads skeletal SMD animations (as written by rig.mjs) back into rig poses: undoes the root
// import turn; bones missing from the file keep their bind transform.
//   import { readSMD } from "./smd.mjs"; const poses = readSMD("anims/walk.smd");
// From cs2-fighter/tools/anim/smd.mjs (MIT), made project-neutral.
import fs from "node:fs";
import { q } from "./m3.mjs";
import { SK, IDX, fk, IMPORT_FIX_Q } from "./rig.mjs";

export function readSMD(file) {
  const lines = fs.readFileSync(file, "utf8").split(/\r?\n/);
  const nodes = [];
  let i = 0;
  while (i < lines.length && lines[i].trim() !== "nodes") i++;
  for (i++; i < lines.length && lines[i].trim() !== "end"; i++) {
    const m = lines[i].match(/^\s*(\d+)\s+"([^"]+)"\s+(-?\d+)/);
    if (m) nodes[+m[1]] = m[2];
  }
  while (i < lines.length && lines[i].trim() !== "skeleton") i++;
  const frames = [];
  let cur = null;
  const unfix = q.conj(IMPORT_FIX_Q);
  for (i++; i < lines.length && lines[i].trim() !== "end"; i++) {
    const s = lines[i].trim();
    if (s.startsWith("time")) { cur = new Array(SK.length).fill(null); frames.push(cur); continue; }
    const v = s.split(/\s+/).map(Number);
    const bi = IDX[nodes[v[0]]];
    if (bi === undefined || !cur) continue;
    let p = [v[1], v[2], v[3]];
    let r = q.fromEulerZYX(v[6], v[5], v[4]);
    if (SK[bi].pi < 0) { p = q.rotate(unfix, p); r = q.mul(unfix, r); }
    cur[bi] = { q: r, p };
  }
  // missing bones keep their bind local transform
  return frames.map((f) => fk(f.map((t, bi) => t || SK[bi].local)));
}
