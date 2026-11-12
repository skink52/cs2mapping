// Dumps compiled stock models (LOD 0) for the skybox review tools (sky_budget.py, sky_review.py): per draw call the material,
// positions, first UV set and triangle indices, so the Python side can count triangles and render the skyline offline.
//   node sky_meshes.mjs <out dir> <models/...vmdl> [...]          (VPK folder: env CS2_VPK_DIR, else the default CS2 install)
// Writes <out dir>/<model path with / -> __>.json: {"model", "draws": [{"material", "P": [...], "UV": [...], "I": [...]}], "lods": n}
// Formats read: positions R32G32B32_FLOAT (6); UVs R32G32_FLOAT (16), R16G16_FLOAT (34), _UNORM (35) or _SNORM (37). Node 22.15+.
// Reuses create/s2 (resource.mjs, vpk.mjs, meshoptimizer decoder); prop_mesh.mjs has no UVs, so the draw-call walk is repeated here.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const s2 = path.resolve(here, "..", "..", "..", "create", "s2");
const { readResourceKV } = await import(pathToFileURL(path.join(s2, "resource.mjs")).href);
const { readInput } = await import(pathToFileURL(path.join(s2, "vpk.mjs")).href);
const { MeshoptDecoder } = await import(pathToFileURL(path.join(s2, "vendor", "meshoptimizer", "meshopt_decoder.mjs")).href);

const [outDir, ...models] = process.argv.slice(2);
if (!outDir || !models.length) { console.log("usage: node sky_meshes.mjs <out dir> <models/...vmdl> [...]"); process.exit(2); }
const vpk = process.env.CS2_VPK_DIR || "C:/Program Files (x86)/Steam/steamapps/common/Counter-Strike Global Offensive/game/csgo";
fs.mkdirSync(outDir, { recursive: true });
await MeshoptDecoder.ready;

// VBIB block (newer layout): vertex and index buffer descriptors with self-relative offsets (as create/s2/prop_mesh.mjs)
function readVBIB(buf) {
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  const u32 = (o) => dv.getUint32(o, true);
  const vbOff = u32(0), vbCount = u32(4), ibOff = 8 + u32(8), ibCount = u32(12);
  const vbs = [], ibs = [];
  for (let i = 0; i < vbCount; i++) {
    const o = vbOff + i * 24;
    const count = u32(o), size = u32(o + 4) & 0x3ffffff;
    const attrOff = o + 8 + u32(o + 8), attrCount = u32(o + 12);
    const dataOff = o + 16 + u32(o + 16), total = u32(o + 20);
    const fields = {};
    for (let a = 0; a < attrCount; a++) {
      const ao = attrOff + a * 56;
      let name = "";
      for (let k = 0; k < 32; k++) { const ch = buf[ao + k]; if (!ch) break; name += String.fromCharCode(ch); }
      fields[name.toUpperCase() + u32(ao + 32)] = { fmt: u32(ao + 36), off: u32(ao + 40) };
    }
    vbs.push({ count, size, fields, raw: buf.subarray(dataOff, dataOff + total) });
  }
  for (let i = 0; i < ibCount; i++) {
    const o = ibOff + i * 24;
    const count = u32(o), size = u32(o + 4) & 0x3ffffff;
    const dataOff = o + 16 + u32(o + 16), total = u32(o + 20);
    ibs.push({ count, size, raw: buf.subarray(dataOff, dataOff + total) });
  }
  return { vbs, ibs };
}

function half(h) {
  const s = h & 0x8000 ? -1 : 1, e = (h >> 10) & 0x1f, f = h & 0x3ff;
  if (e === 0) return s * Math.pow(2, -14) * (f / 1024);
  if (e === 31) return f ? NaN : s * Infinity;
  return s * Math.pow(2, e - 15) * (1 + f / 1024);
}

for (const model of models) {
  const rel = model.replace(/\.vmdl(_c)?$/, "") + ".vmdl_c";
  try {
    const L = readResourceKV(readInput(rel, vpk));
    const C = L.find((b) => b.type === "CTRL").kv;
    const out = { model: model.replace(/_c$/, ""), draws: [], lods: (C.embedded_meshes || []).length };
    for (const em of C.embedded_meshes || []) {
      if ((em.mesh_index ?? em.m_nMeshIndex ?? 0) !== 0) continue;
      let md, rawV, rawI;
      if (em.vbib_block !== undefined) { md = L[em.data_block].kv; ({ vbs: rawV, ibs: rawI } = readVBIB(L[em.vbib_block].data)); }
      else if (em.m_vertexBuffers) {
        md = L[em.m_nDataBlock].kv;
        const nm = (f) => (typeof f.m_pSemanticName === "string" ? f.m_pSemanticName : Buffer.from(f.m_pSemanticName).toString("latin1")).replace(/\0+$/, "").toUpperCase();
        rawV = em.m_vertexBuffers.map((vb) => {
          const fields = {};
          for (const f of vb.m_inputLayoutFields) fields[nm(f) + f.m_nSemanticIndex] = { off: f.m_nOffset, fmt: f.m_Format };
          return { count: vb.m_nElementCount, size: vb.m_nElementSizeInBytes, fields, raw: L[vb.m_nBlockIndex].data };
        });
        rawI = em.m_indexBuffers.map((ib) => ({ count: ib.m_nElementCount, size: ib.m_nElementSizeInBytes, raw: L[ib.m_nBlockIndex].data }));
      } else throw new Error("unknown mesh layout");
      const vbs = rawV.map((vb) => {
        let data = vb.raw;
        const n = vb.count, sz = vb.size;
        if (data.length !== n * sz) { const d = new Uint8Array(n * sz); MeshoptDecoder.decodeVertexBuffer(d, n, sz, data); data = d; }
        return { n, sz, fields: vb.fields, data: new Uint8Array(data) };
      });
      const ibs = rawI.map((ib) => {
        let data = ib.raw;
        const n = ib.count, sz = ib.size;
        if (data.length !== n * sz) { const d = new Uint8Array(n * sz); MeshoptDecoder.decodeIndexBuffer(d, n, sz, data); data = d; }
        const dv = new DataView(data.buffer, data.byteOffset, data.byteLength);
        const idx = new Uint32Array(n);
        for (let i = 0; i < n; i++) idx[i] = sz === 2 ? dv.getUint16(i * 2, true) : dv.getUint32(i * 4, true);
        return idx;
      });
      for (const so of md.m_sceneObjects || []) {
        for (const dc of so.m_drawCalls || []) {
          const vb = vbs[dc.m_vertexBuffers[0].m_hBuffer], ib = ibs[dc.m_indexBuffer.m_hBuffer];
          const pf = vb.fields.POSITION0, tf = vb.fields.TEXCOORD0;
          if (!pf || pf.fmt !== 6) throw new Error("position format " + (pf && pf.fmt));
          const dv = new DataView(vb.data.buffer, vb.data.byteOffset, vb.data.byteLength);
          const first = dc.m_nStartIndex || 0, n = dc.m_nIndexCount, base = dc.m_nBaseVertex || 0;
          const map = new Map(), P = [], UV = [], I = [];
          for (let k = 0; k < n; k++) {
            const vi = ib[first + k] + base;
            let j = map.get(vi);
            if (j === undefined) {
              j = P.length / 3; map.set(vi, j);
              const o = vi * vb.sz;
              P.push(dv.getFloat32(o + pf.off, true), dv.getFloat32(o + pf.off + 4, true), dv.getFloat32(o + pf.off + 8, true));
              if (tf && tf.fmt === 16) UV.push(dv.getFloat32(o + tf.off, true), dv.getFloat32(o + tf.off + 4, true));
              else if (tf && tf.fmt === 34) UV.push(half(dv.getUint16(o + tf.off, true)), half(dv.getUint16(o + tf.off + 2, true)));
              else if (tf && tf.fmt === 35) UV.push(dv.getUint16(o + tf.off, true) / 65535, dv.getUint16(o + tf.off + 2, true) / 65535);
              else if (tf && tf.fmt === 37) UV.push(Math.max(-1, dv.getInt16(o + tf.off, true) / 32767), Math.max(-1, dv.getInt16(o + tf.off + 2, true) / 32767));
              else UV.push(0, 0);
            }
            I.push(j);
          }
          out.draws.push({ material: String(dc.m_material || ""), uvfmt: tf ? tf.fmt : null, P: P.map((x) => +x.toFixed(3)), UV: UV.map((x) => +x.toFixed(5)), I });
        }
      }
    }
    const tris = out.draws.reduce((a, d) => a + d.I.length / 3, 0);
    fs.writeFileSync(path.join(outDir, out.model.replace(/\//g, "__") + ".json"), JSON.stringify(out));
    console.log(out.model, "draws", out.draws.length, "tris", tris, "lods", out.lods, "uv", out.draws.map((d) => d.uvfmt).join(","));
  } catch (err) {
    console.log(model, "ERROR", String(err && err.message || err).slice(0, 200));
  }
}
