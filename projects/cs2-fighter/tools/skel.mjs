import fs from "node:fs";
import { readKV3Blocks } from "./kv3.mjs";
import { execFileSync } from "node:child_process";
const D = "/mnt/user-data/uploads/csgo/pak01_dir.vpk";
const names = process.argv.slice(2);
const out = {};
for (const n of names) {
  const buf = execFileSync("python3", ["-c", `import vpk,sys;sys.stdout.buffer.write(vpk.extract('${D}','${n}'))`], { maxBuffer: 1 << 28 });
  const { kv } = readKV3Blocks(buf);
  const bones = kv.AGRP.m_decodeKey.m_boneArray.map((b) => ({ name: b.m_name, parent: b.m_parent, pos: b.m_pos, quat: b.m_quat }));
  const mats = (kv.DATA.m_materialGroups || []);
  // RERL external refs (materials etc.) as strings
  const s = buf.toString("latin1");
  const refs = [...new Set((s.match(/[a-z0-9_\/]+\.vmat/g) || []))];
  out[n] = { bones, refs, hull: kv.DATA.m_modelInfo.m_vHullMax, seq: kv.ASEQ && kv.ASEQ.m_localSequenceNameArray, attach: (kv.MDAT && kv.MDAT.m_attachments || []).map(a=>a.key||a.m_name) };
}
fs.writeFileSync(process.env.OUT || "/tmp/claude-0/skels.json", JSON.stringify(out));
for (const [n, v] of Object.entries(out)) console.log(n, v.bones.length, v.hull, v.refs.slice(0, 12).join(" "));
