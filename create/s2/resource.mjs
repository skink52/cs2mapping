// Source 2 compiled resource reader: block list (by index and by type) + binary KV3 per block.
//   const blocks = readResourceKV(buf);  blocks.find((b) => b.type === "DATA").kv
// Based on the layout documented by ValveResourceFormat (MIT). Node 22+ for zstd-compressed files.
// From cs2-fighter/tools/s2/resource.mjs (MIT), made project-neutral.
import { readKV3 } from "./kv3.mjs";

export function readResourceBlocks(buf) {
  const blockOffset = buf.readUInt32LE(8) + 8;
  const blockCount = buf.readUInt32LE(12);
  const list = [];
  for (let i = 0; i < blockCount; i++) {
    const p = blockOffset + i * 12;
    const type = buf.toString("latin1", p, p + 4);
    const off = p + 4 + buf.readUInt32LE(p + 4);
    const size = buf.readUInt32LE(p + 8);
    list.push({ type, data: buf.subarray(off, off + size) });
  }
  return list;
}

const KV_TYPES = new Set(["DATA", "CTRL", "MDAT", "ANIM", "ASEQ", "AGRP", "PHYS", "MRPH", "RED2", "LaCo", "INSG", "STAT"]);
export function readResourceKV(buf) {
  const list = readResourceBlocks(buf);
  for (const b of list) {
    if (!KV_TYPES.has(b.type)) continue;
    try { b.kv = readKV3(b.data); } catch (err) { b.err = String(err); }
  }
  return list;
}
