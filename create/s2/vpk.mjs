// Reads files out of CS2's VPKs (pak01_dir.vpk + pak01_NNN.vpk chunks). Same format and logic as
// ../vpkdir.py + ../vtexread.py's vpk_read, in JS so the s2 tools need no Python.
//   const v = openVPK("<CS2>/game/csgo");  v.read("agents/models/ctm_swat/ctm_swat_varianth.vmdl_c");
//   v.list(/^models\/props\/.*\.vmdl_c$/)
//   node vpk.mjs <folder with pak01_dir.vpk> [regex]     lists matching paths
// readInput(arg, vpkDir): a file on disk if it exists, else that path from the VPK.
// From cs2-fighter/tools/vpk.py (MIT) and this repo's create/vpkdir.py, made project-neutral.
import fs from "node:fs";
import path from "node:path";

export function openVPK(dir) {
  const dirFile = dir.endsWith(".vpk") ? dir : path.join(dir, "pak01_dir.vpk");
  const base = dirFile.replace(/_dir\.vpk$/, "");
  const d = fs.readFileSync(dirFile);
  const ver = d.readUInt32LE(4), tree = d.readUInt32LE(8);
  const hdr = ver === 2 ? 28 : 12;
  let p = hdr;
  const cstr = () => { const e = d.indexOf(0, p); const s = d.toString("utf8", p, e); p = e + 1; return s; };
  const idx = new Map();
  for (;;) {
    const ext = cstr(); if (!ext) break;
    for (;;) {
      const folder = cstr(); if (!folder) break;
      for (;;) {
        const name = cstr(); if (!name) break;
        const pre = d.readUInt16LE(p + 4), arc = d.readUInt16LE(p + 6), off = d.readUInt32LE(p + 8), len = d.readUInt32LE(p + 12);
        p += 18;
        const preload = d.subarray(p, p + pre); p += pre;
        const full = (folder.trim() ? folder + "/" : "") + name + "." + ext;
        idx.set(full, { arc, off, len, preload });
      }
    }
  }
  const read = (file) => {
    const e = idx.get(file.replace(/\\/g, "/").toLowerCase()) || idx.get(file.replace(/\\/g, "/"));
    if (!e) throw new Error(`not in the VPK: ${file}`);
    if (e.len === 0) return Buffer.from(e.preload);
    let chunk, start;
    if (e.arc === 0x7fff) { chunk = dirFile; start = hdr + tree + e.off; }
    else { chunk = `${base}_${String(e.arc).padStart(3, "0")}.vpk`; start = e.off; }
    if (!fs.existsSync(chunk)) throw new Error(`${file} is in ${path.basename(chunk)}, which isn't in ${path.dirname(chunk)}`);
    const fd = fs.openSync(chunk, "r");
    const buf = Buffer.alloc(e.len);
    fs.readSync(fd, buf, 0, e.len, start);
    fs.closeSync(fd);
    return Buffer.concat([e.preload, buf]);
  };
  return { files: idx, read, list: (re) => [...idx.keys()].filter((k) => re.test(k)).sort() };
}

const opened = new Map();
export function readInput(arg, vpkDir) {
  if (fs.existsSync(arg)) return fs.readFileSync(arg);
  if (!vpkDir) throw new Error(`${arg} not found (pass --vpk <folder with pak01_dir.vpk> or set CS2_VPK_DIR to read it from the game)`);
  if (!opened.has(vpkDir)) opened.set(vpkDir, openVPK(vpkDir));
  return opened.get(vpkDir).read(arg);
}

if (process.argv[1] && path.basename(process.argv[1]) === "vpk.mjs") {
  const [dir, re] = process.argv.slice(2);
  if (!dir) { console.log("usage: node vpk.mjs <folder with pak01_dir.vpk> [regex]"); process.exit(2); }
  const v = openVPK(dir);
  const out = re ? v.list(new RegExp(re)) : [...v.files.keys()];
  console.log(out.join("\n"));
  console.error(`${out.length} of ${v.files.size} files`);
}
