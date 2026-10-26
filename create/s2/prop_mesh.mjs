// Extracts static prop meshes (.vmdl_c, LOD 0) for layout previews: positions, normals and
// triangle indices per draw call, plus the real bounds (model units, before any map scale), so
// stock props can be placed and stacked by their true size when dressing a set.
//   node prop_mesh.mjs <model.vmdl_c | path in VPK>... [--vpk <folder with pak01_dir.vpk>] [--json out.json]
//   e.g. node prop_mesh.mjs models/props/de_inferno/crate_fruit_break.vmdl_c --vpk "<CS2>/game/csgo"
// Prints draw calls, triangles, bounds (min .. max) and size; --json writes {model: {lo, hi, size, materials}}.
// From cs2-fighter/tools/s2/prop_mesh.mjs (MIT), made project-neutral.
import fs from "node:fs";
import path from "node:path";
import { readResourceKV } from "./resource.mjs";
import { readInput } from "./vpk.mjs";
import { MeshoptDecoder } from "./vendor/meshoptimizer/meshopt_decoder.mjs";

// VBIB: vertex and index buffer descriptors with self-relative offsets
function readVBIB(buf) {
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  const u32 = (o) => dv.getUint32(o, true);
  const vbOff = 0 + u32(0), vbCount = u32(4), ibOff = 8 + u32(8), ibCount = u32(12);
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

const half = (h) => { const s = h & 0x8000 ? -1 : 1, e = (h >> 10) & 31, m = h & 1023; return e === 0 ? s * m * 2 ** -24 : e === 31 ? s * Infinity : s * (1 + m / 1024) * 2 ** (e - 15); };

export async function extractProp(buf) {
  await MeshoptDecoder.ready;
  const L = readResourceKV(buf);
  const C = L.find((b) => b.type === "CTRL").kv;
  const out = { meshes: [], lo: [Infinity, Infinity, Infinity], hi: [-Infinity, -Infinity, -Infinity] };
  for (const em of C.embedded_meshes || []) {
    // only the first mesh (LOD 0)
    if ((em.mesh_index ?? em.m_nMeshIndex ?? 0) !== 0) continue;
    let md, vbib;
    if (em.vbib_block !== undefined) { md = L[em.data_block].kv; vbib = readVBIB(L[em.vbib_block].data); }
    else if (em.m_vertexBuffers) {
      // older layout: one MVTX / MIDX block per buffer, described in the CTRL block
      md = L[em.m_nDataBlock].kv;
      const nm = (f) => (typeof f.m_pSemanticName === "string" ? f.m_pSemanticName : Buffer.from(f.m_pSemanticName).toString("latin1")).replace(/\0+$/, "").toUpperCase();
      vbib = {
        vbs: em.m_vertexBuffers.map((vb) => {
          const fields = {};
          for (const f of vb.m_inputLayoutFields) fields[nm(f) + f.m_nSemanticIndex] = { off: f.m_nOffset, fmt: f.m_Format };
          return { count: vb.m_nElementCount, size: vb.m_nElementSizeInBytes, fields, raw: L[vb.m_nBlockIndex].data };
        }),
        ibs: em.m_indexBuffers.map((ib) => ({ count: ib.m_nElementCount, size: ib.m_nElementSizeInBytes, raw: L[ib.m_nBlockIndex].data })),
      };
    } else continue;
    const vbs = vbib.vbs.map((vb) => {
      let data = vb.raw;
      if (data.length !== vb.count * vb.size) { const d = new Uint8Array(vb.count * vb.size); MeshoptDecoder.decodeVertexBuffer(d, vb.count, vb.size, data); data = d; }
      return { ...vb, data: new Uint8Array(data) };
    });
    const ibs = vbib.ibs.map((ib) => {
      let data = ib.raw;
      if (data.length !== ib.count * ib.size) { const d = new Uint8Array(ib.count * ib.size); MeshoptDecoder.decodeIndexBuffer(d, ib.count, ib.size, data); data = d; }
      const dv = new DataView(data.buffer, data.byteOffset, data.byteLength);
      const idx = new Uint32Array(ib.count);
      for (let i = 0; i < ib.count; i++) idx[i] = ib.size === 2 ? dv.getUint16(i * 2, true) : dv.getUint32(i * 4, true);
      return idx;
    });
    for (const so of md.m_sceneObjects || []) {
      for (const dc of so.m_drawCalls || []) {
        const vb = vbs[dc.m_vertexBuffers[0].m_hBuffer], ib = ibs[dc.m_indexBuffer.m_hBuffer];
        const pf = vb.fields.POSITION0, nf = vb.fields.NORMAL0;
        if (!pf) continue;
        const dv = new DataView(vb.data.buffer, vb.data.byteOffset, vb.data.byteLength);
        const first = dc.m_nStartIndex || 0, n = dc.m_nIndexCount;
        const baseV = dc.m_nBaseVertex || 0;
        // compact the vertices this draw call uses
        const map = new Map(), P = [], N = [], I = [];
        for (let k = 0; k < n; k++) {
          const vi = ib[first + k] + baseV;
          let j = map.get(vi);
          if (j === undefined) {
            j = P.length / 3; map.set(vi, j);
            const o = vi * vb.size;
            const x = dv.getFloat32(o + pf.off, true), y = dv.getFloat32(o + pf.off + 4, true), z = dv.getFloat32(o + pf.off + 8, true);
            P.push(x, y, z);
            for (const [a, v] of [[0, x], [1, y], [2, z]]) { out.lo[a] = Math.min(out.lo[a], v); out.hi[a] = Math.max(out.hi[a], v); }
            let nx = 0, ny = 0, nz = 1;
            if (nf && nf.fmt === 2) { nx = dv.getFloat32(o + nf.off, true); ny = dv.getFloat32(o + nf.off + 4, true); nz = dv.getFloat32(o + nf.off + 8, true); }
            N.push(nx, ny, nz);
          }
          I.push(j);
        }
        out.meshes.push({ material: dc.m_material || "", P: Float32Array.from(P), N: Float32Array.from(N), I: Uint32Array.from(I), flatNormals: !(nf && nf.fmt === 2) });
      }
    }
  }
  return out;
}

// just the bounds: { lo, hi, size, materials }
export async function propBounds(buf) {
  const p = await extractProp(buf);
  return { lo: p.lo, hi: p.hi, size: p.hi.map((h, k) => h - p.lo[k]), materials: [...new Set(p.meshes.map((m) => String(m.material)))] };
}

if (process.argv[1] && path.basename(process.argv[1]) === "prop_mesh.mjs") {
  const args = process.argv.slice(2);
  const opt = (k) => { const i = args.indexOf("--" + k); return i < 0 ? null : args[i + 1]; };
  const files = args.filter((a, i) => !a.startsWith("--") && !["--vpk", "--json"].includes(args[i - 1]));
  if (!files.length) { console.log("usage: node prop_mesh.mjs <model.vmdl_c | path in VPK>... [--vpk dir] [--json out.json]"); process.exit(2); }
  const vpk = opt("vpk") || process.env.CS2_VPK_DIR;
  const all = {};
  const f1 = (v) => v.map((x) => x.toFixed(1)).join(",");
  for (const f of files) {
    const p = await extractProp(readInput(f, vpk));
    const tris = p.meshes.reduce((a, m) => a + m.I.length / 3, 0);
    const size = p.hi.map((h, k) => h - p.lo[k]);
    all[f] = { lo: p.lo, hi: p.hi, size, materials: [...new Set(p.meshes.map((m) => String(m.material)))] };
    console.log(f.split("/").pop(), "draws", p.meshes.length, "tris", tris, "bounds", f1(p.lo), "..", f1(p.hi), "size", f1(size), p.meshes.map((m) => String(m.material).split("/").pop()).join(" "));
  }
  if (opt("json")) fs.writeFileSync(opt("json"), JSON.stringify(all, null, 1));
}
