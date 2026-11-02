// Source 2 compiled-resource reader (blocks + binary KV3 v1..v5) for exploring game assets.
// Based on the layout documented by ValveResourceFormat (MIT). Node 22+ (built-in zstd).
import zlib from "node:zlib";

export function readResource(buf) {
  const fileSize = buf.readUInt32LE(0);
  const headerVersion = buf.readUInt16LE(4);
  const blockOffset = buf.readUInt32LE(8) + 8;
  const blockCount = buf.readUInt32LE(12);
  const blocks = {};
  for (let i = 0; i < blockCount; i++) {
    const p = blockOffset + i * 12;
    const type = buf.toString("latin1", p, p + 4);
    const off = p + 4 + buf.readUInt32LE(p + 4);
    const size = buf.readUInt32LE(p + 8);
    blocks[type] = buf.subarray(off, off + size);
  }
  return { fileSize, headerVersion, blocks };
}

// tiny LZ4 block decoder
function lz4(src, outSize) {
  const out = Buffer.alloc(outSize);
  let i = 0, o = 0;
  while (i < src.length) {
    const tok = src[i++];
    let lit = tok >> 4;
    if (lit === 15) { let b; do { b = src[i++]; lit += b; } while (b === 255); }
    src.copy(out, o, i, i + lit); i += lit; o += lit;
    if (i >= src.length) break;
    const off = src[i] | (src[i + 1] << 8); i += 2;
    let ml = tok & 15;
    if (ml === 15) { let b; do { b = src[i++]; ml += b; } while (b === 255); }
    ml += 4;
    for (let k = 0; k < ml; k++) out[o + k] = out[o - off + k];
    o += ml;
  }
  return out;
}

class Lane {
  constructor(b) { this.b = b || Buffer.alloc(0); this.p = 0; }
  u8() { return this.b[this.p++]; }
  i8() { return this.b.readInt8(this.p++); }
  i16() { const v = this.b.readInt16LE(this.p); this.p += 2; return v; }
  u16() { const v = this.b.readUInt16LE(this.p); this.p += 2; return v; }
  i32() { const v = this.b.readInt32LE(this.p); this.p += 4; return v; }
  u32() { const v = this.b.readUInt32LE(this.p); this.p += 4; return v; }
  f32() { const v = this.b.readFloatLE(this.p); this.p += 4; return v; }
  i64() { const v = this.b.readBigInt64LE(this.p); this.p += 8; return Number(v); }
  u64() { const v = this.b.readBigUInt64LE(this.p); this.p += 8; return v <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(v) : v.toString(); }
  f64() { const v = this.b.readDoubleLE(this.p); this.p += 8; return v; }
}

const align = (o, a) => (o + a - 1) & ~(a - 1);

export function readKV3(b) {
  const r = new Lane(b);
  const magic = r.u32();
  if (magic === 0x03564B56) throw new Error("legacy VKV3 not supported");
  const version = magic & 0xff;
  if ((magic & 0xffffff00) !== 0x4b563300) throw new Error("not KV3 " + magic.toString(16));
  r.p += 16; // format guid
  const comp = r.u32();
  let dictId = 0, frame = 0, c1, c4, c8, cTypes = 0, cObjects = 0, cArrays = 0, uncompTotal, compTotal = 0, cBlocks = 0, blobBytes = 0;
  if (version === 1) { c1 = r.i32(); c4 = r.i32(); c8 = r.i32(); uncompTotal = r.i32(); compTotal = b.length - r.p; }
  else {
    dictId = r.u16(); frame = r.u16(); c1 = r.i32(); c4 = r.i32(); c8 = r.i32(); cTypes = r.i32();
    cObjects = r.u16(); cArrays = r.u16(); uncompTotal = r.i32(); compTotal = r.i32(); cBlocks = r.i32(); blobBytes = r.i32();
  }
  let c2 = 0, blockSizesBytes = 0;
  if (version >= 4) { c2 = r.i32(); blockSizesBytes = r.i32(); }
  let u1 = uncompTotal, s1 = compTotal, u2 = 0, s2 = 0, b2c1 = 0, b2c2 = 0, b2c4 = 0, b2c8 = 0, b2objs = 0;
  if (version >= 5) {
    u1 = r.i32(); s1 = r.i32(); u2 = r.i32(); s2 = r.i32();
    b2c1 = r.i32(); b2c2 = r.i32(); b2c4 = r.i32(); b2c8 = r.i32();
    r.i32(); b2objs = r.i32(); r.i32(); r.i32();
  }
  const dec = (size, outSize) => {
    const src = b.subarray(r.p, r.p + size); r.p += size;
    if (comp === 0) return Buffer.from(src);
    if (comp === 1) return lz4(src, outSize);
    if (comp === 2) return zlib.zstdDecompressSync(src);
    throw new Error("comp " + comp);
  };
  let buf1;
  if (comp === 0) { buf1 = Buffer.from(b.subarray(r.p, r.p + u1)); r.p += u1; }
  else buf1 = dec(s1, u1);
  const lanes = (B, off, n1, n2, n4, n8, v5) => {
    const L = {};
    L.b1 = new Lane(B.subarray(off, off + n1)); off += n1;
    if (n2) off = align(off, 2);
    L.b2 = new Lane(B.subarray(off, off + n2 * 2)); off += n2 * 2;
    if (n4) off = align(off, 4);
    L.b4 = new Lane(B.subarray(off, off + n4 * 4)); off += n4 * 4;
    if (n8) off = align(off, 8); else if (!v5) off = align(off, 8);
    L.b8 = new Lane(B.subarray(off, off + n8 * 8)); off += n8 * 8;
    L.end = off;
    return L;
  };
  const ctx = { version, strings: [] };
  const L1 = lanes(buf1, 0, c1, c2, c4, c8, version >= 5);
  const nStrings = L1.b4.i32();
  let blobSizesLane = null;
  if (version >= 5) {
    for (let i = 0; i < nStrings; i++) { const e = L1.b1.b.indexOf(0, L1.b1.p); ctx.strings.push(L1.b1.b.toString("utf8", L1.b1.p, e)); L1.b1.p = e + 1; }
    ctx.aux = L1;
    let buf2;
    if (comp === 0) { buf2 = Buffer.from(b.subarray(r.p, r.p + u2)); r.p += u2; } else buf2 = dec(s2, u2);
    ctx.objLens = new Lane(buf2.subarray(0, b2objs * 4));
    const L2 = lanes(buf2, b2objs * 4, b2c1, b2c2, b2c4, b2c8, true);
    ctx.buf = L2;
    ctx.types = new Lane(buf2.subarray(L2.end, L2.end + cTypes));
    blobSizesLane = new Lane(buf2.subarray(L2.end + cTypes));
  } else {
    ctx.buf = L1; ctx.aux = L1;
    let off = L1.end;
    const strStart = off;
    for (let i = 0; i < nStrings; i++) { const e = buf1.indexOf(0, off); ctx.strings.push(buf1.toString("utf8", off, e)); off = e + 1; }
    const tlen = version === 1 ? uncompTotal - off - 4 : cTypes - off + strStart;
    ctx.types = new Lane(buf1.subarray(off, off + tlen));
    blobSizesLane = new Lane(buf1.subarray(off + tlen));
  }
  if (cBlocks > 0) {
    ctx.blobLens = [];
    for (let i = 0; i < cBlocks; i++) ctx.blobLens.push(blobSizesLane.i32());
    // blob data follows; we only need to skip it for our purposes (zstd / raw only)
    if (comp === 0) { ctx.blobs = b.subarray(r.p, r.p + blobBytes); }
    else if (comp === 2 && version >= 5) { ctx.blobs = zlib.zstdDecompressSync(b.subarray(r.p, r.p + (compTotal - s1 - s2))); }
    else if (comp === 2) { ctx.blobs = zlib.zstdDecompressSync(b.subarray(r.p - s1, r.p)).subarray(u1); }
    else ctx.blobs = null;
    ctx.blobP = 0;
  }
  const readType = () => {
    let t = ctx.types.u8(), flag = 0;
    if (version >= 3) { if (t & 0x80) flag = ctx.types.u8(); if (t & 0x40) ctx.types.u8(); t &= 0x3f; }
    else { if (t & 0x80) flag = ctx.types.u8(); t &= 0x7f; }
    return [t, flag];
  };
  const str = (i) => (i >= 0 && i < ctx.strings.length ? ctx.strings[i] : "");
  const value = (t, lane) => {
    const B = ctx.buf;
    switch (t) {
      case 1: return null;
      case 13: return true; case 14: return false;
      case 15: return 0; case 16: return 1; case 17: return 0; case 18: return 1;
      case 2: return lane.b1.u8() !== 0;
      case 22: return lane.b1.i8(); case 23: return lane.b1.u8();
      case 20: return lane.b2.i16(); case 21: return lane.b2.u16();
      case 11: return lane.b4.i32(); case 12: return lane.b4.u32(); case 19: return lane.b4.f32();
      case 3: return lane.b8.i64(); case 4: return lane.b8.u64(); case 5: return lane.b8.f64();
      case 6: return str(B.b4.i32());
      case 7: {
        if (version < 2) { const n = B.b4.i32(); const o = B.b1.b.subarray(B.b1.p, B.b1.p + n); B.b1.p += n; return { blob: n }; }
        const n = ctx.blobLens.shift(); ctx.blobP += n; return { blob: n, data: ctx.blobs ? ctx.blobs.subarray(ctx.blobP - n, ctx.blobP) : null };
      }
      case 8: { const n = B.b4.i32(); const a = []; for (let i = 0; i < n; i++) { const [tt] = readType(); a.push(value(tt, ctx.buf)); } return a; }
      case 10: case 24: case 25: {
        const n = t === 10 ? B.b4.i32() : B.b1.u8();
        const [st] = readType();
        const ln = t === 25 ? ctx.aux : ctx.buf;
        const a = []; for (let i = 0; i < n; i++) a.push(value(st, ln)); return a;
      }
      case 9: {
        const n = version >= 5 ? ctx.objLens.i32() : B.b4.i32();
        const o = {};
        for (let i = 0; i < n; i++) { const [tt] = readType(); const k = str(B.b4.i32()); o[k] = value(tt, ctx.buf); }
        return o;
      }
      default: throw new Error("kv3 type " + t);
    }
  };
  const [rt] = readType();
  return value(rt, ctx.buf);
}

export function readKV3Blocks(file) {
  const res = readResource(file);
  const out = {};
  for (const [k, v] of Object.entries(res.blocks)) {
    const m = v.length >= 4 ? v.readUInt32LE(0) : 0;
    if ((m & 0xffffff00) === 0x4b563300) { try { out[k] = readKV3(v); } catch (e) { out[k] = { error: String(e) }; } }
    else if (k === "RERL" || k === "RED2" || k === "REDI") out[k] = { raw: v.length };
  }
  return { res, kv: out };
}
