// Extracts a CS2 agent model (.vmdl_c) into a compact preview mesh: the model skeleton (bind
// pose), and the third-person default meshes with positions, normals, UVs and skin weights.
// Usage: node tools/s2/agent_mesh.mjs <model.vmdl_c> <out.json>
import fs from "node:fs";
import { readResourceKV } from "./resource.mjs";
import { MeshoptDecoder } from "../vendor/meshoptimizer/meshopt_decoder.mjs";

export async function extractAgent(buf, { meshGroupMask = null } = {}) {
  await MeshoptDecoder.ready;
  const L = readResourceKV(buf);
  const D = L.find((b) => b.type === "DATA").kv;
  const C = L.find((b) => b.type === "CTRL").kv;
  if (meshGroupMask === null) meshGroupMask = D.m_nDefaultMeshGroupMask;
  const sk = D.m_modelSkeleton;
  const skeleton = sk.m_boneName.map((name, i) => ({
    name, parent: sk.m_nParent[i],
    pos: Array.from(sk.m_bonePosParent[i]), quat: Array.from(sk.m_boneRotParent[i]),
  }));
  const remap = D.m_remappingTable, starts = D.m_remappingTableStarts;
  const out = { skeleton, meshes: [] };
  C.embedded_meshes.forEach((em, mi) => {
    const mask = D.m_refMeshGroupMasks[em.m_nMeshIndex];
    if (!(mask & meshGroupMask)) return;
    const md = L[em.m_nDataBlock].kv;
    const remapStart = starts[em.m_nMeshIndex];
    const vbs = em.m_vertexBuffers.map((vb) => {
      const raw = L[vb.m_nBlockIndex].data;
      const n = vb.m_nElementCount, sz = vb.m_nElementSizeInBytes;
      let data;
      if (raw.length === n * sz) data = new Uint8Array(raw);
      else { data = new Uint8Array(n * sz); MeshoptDecoder.decodeVertexBuffer(data, n, sz, raw); }
      const fields = {};
      for (const f of vb.m_inputLayoutFields) {
        const nm = (typeof f.m_pSemanticName === "string" ? f.m_pSemanticName : Buffer.from(f.m_pSemanticName).toString("latin1")).replace(/\0+$/, "").toUpperCase();
        fields[nm + f.m_nSemanticIndex] = { off: f.m_nOffset, fmt: f.m_Format };
      }
      return { n, sz, data, fields };
    });
    const ibs = em.m_indexBuffers.map((ib) => {
      const raw = L[ib.m_nBlockIndex].data;
      const n = ib.m_nElementCount, sz = ib.m_nElementSizeInBytes;
      let data;
      if (raw.length === n * sz) data = new Uint8Array(raw);
      else { data = new Uint8Array(n * sz); MeshoptDecoder.decodeIndexBuffer(data, n, sz, raw); }
      const dv = new DataView(data.buffer);
      const idx = new Uint32Array(n);
      for (let i = 0; i < n; i++) idx[i] = sz === 2 ? dv.getUint16(i * 2, true) : dv.getUint32(i * 4, true);
      return idx;
    });
    for (const so of md.m_sceneObjects) {
      for (const dc of so.m_drawCalls) {
        const vb = vbs[dc.m_vertexBuffers[0].m_hBuffer];
        const ib = ibs[dc.m_indexBuffer.m_hBuffer];
        const dv = new DataView(vb.data.buffer);
        const nv = vb.n;
        const P = new Float32Array(nv * 3), N = new Float32Array(nv * 3), UV = new Float32Array(nv * 2);
        const J = new Uint16Array(nv * 4), W = new Float32Array(nv * 4);
        const F = vb.fields;
        for (let i = 0; i < nv; i++) {
          const o = i * vb.sz;
          const po = F.POSITION0.off;
          P[i * 3] = dv.getFloat32(o + po, true); P[i * 3 + 1] = dv.getFloat32(o + po + 4, true); P[i * 3 + 2] = dv.getFloat32(o + po + 8, true);
          if (F.TEXCOORD0) {
            const to = o + F.TEXCOORD0.off;
            if (F.TEXCOORD0.fmt === 37) { UV[i * 2] = dv.getInt16(to, true) / 32767; UV[i * 2 + 1] = dv.getInt16(to + 2, true) / 32767; }
            else if (F.TEXCOORD0.fmt === 34) { UV[i * 2] = half(dv.getUint16(to, true)); UV[i * 2 + 1] = half(dv.getUint16(to + 2, true)); }
            else if (F.TEXCOORD0.fmt === 16) { UV[i * 2] = dv.getFloat32(to, true); UV[i * 2 + 1] = dv.getFloat32(to + 4, true); }
          }
          if (F.NORMAL0) {
            const no = o + F.NORMAL0.off;
            let n3;
            if (F.NORMAL0.fmt === 42) n3 = normal2(dv.getUint32(no, true));
            else if (F.NORMAL0.fmt === 28) n3 = normal1(vb.data[no], vb.data[no + 1]);
            else n3 = [dv.getFloat32(no, true), dv.getFloat32(no + 4, true), dv.getFloat32(no + 8, true)];
            N[i * 3] = n3[0]; N[i * 3 + 1] = n3[1]; N[i * 3 + 2] = n3[2];
          }
          const bi = F.BLENDINDICES0, bw = F.BLENDWEIGHT0;
          let ws = [1, 0, 0, 0];
          if (bw) { ws = [0, 1, 2, 3].map((k) => vb.data[o + bw.off + k] / 255); }
          for (let k = 0; k < 4; k++) {
            const local = bi ? vb.data[o + bi.off + k] : 0;
            J[i * 4 + k] = remap[remapStart + local];
            W[i * 4 + k] = ws[k];
          }
          const s = W[i * 4] + W[i * 4 + 1] + W[i * 4 + 2] + W[i * 4 + 3];
          if (s > 0) for (let k = 0; k < 4; k++) W[i * 4 + k] /= s;
        }
        const tri = ib.slice(dc.m_nStartIndex, dc.m_nStartIndex + dc.m_nIndexCount).map((x) => x + dc.m_nBaseVertex);
        out.meshes.push({ mesh: em.m_Name, material: dc.m_material, P, N, UV, J, W, I: tri });
      }
    }
  });
  return out;
}

function half(h) {
  const s = h >> 15, e = (h >> 10) & 31, m = h & 1023;
  return (s ? -1 : 1) * (e ? Math.pow(2, e - 15) * (1 + m / 1024) : Math.pow(2, -14) * (m / 1024));
}
function normal1(x, y) {
  x -= 128; y -= 128;
  const zSignBit = x < 0 ? 1 : 0, tSignBit = y < 0 ? 1 : 0;
  const zSign = -(2 * zSignBit - 1), tSign = -(2 * tSignBit - 1);
  x = x * zSign - zSignBit; y = y * tSign - tSignBit;
  x -= 64; y -= 64;
  const xSignBit = x < 0 ? 1 : 0, ySignBit = y < 0 ? 1 : 0;
  const xSign = -(2 * xSignBit - 1), ySign = -(2 * ySignBit - 1);
  x = (x * xSign - xSignBit) / 63; y = (y * ySign - ySignBit) / 63;
  let z = 1 - x - y;
  const l = 1 / Math.hypot(x, y, z);
  return [x * l * xSign, y * l * ySign, z * l * zSign];
}
function normal2(p) {
  const X = ((p >>> 12) & 0x3ff) / 1023 * 2 - 1, Y = ((p >>> 22) & 0x3ff) / 1023 * 2 - 1;
  let z = 1 - Math.abs(X) - Math.abs(Y);
  let x = X, y = Y;
  const neg = Math.max(0, Math.min(1, -z));
  x += x >= 0 ? -neg : neg; y += y >= 0 ? -neg : neg;
  const l = Math.hypot(x, y, z) || 1;
  return [x / l, y / l, z / l];
}

// JSON-friendly: typed arrays as base64
export function packAgent(a) {
  const b64 = (t) => Buffer.from(t.buffer, t.byteOffset, t.byteLength).toString("base64");
  return {
    skeleton: a.skeleton,
    meshes: a.meshes.map((m) => ({ mesh: m.mesh, material: m.material, nv: m.P.length / 3, nt: m.I.length / 3,
      P: b64(m.P), N: b64(m.N), UV: b64(m.UV), J: b64(m.J), W: b64(m.W), I: b64(new Uint32Array(m.I)) })),
  };
}
export function unpackAgent(o) {
  const f = (s, T) => { const b = Buffer.from(s, "base64"); return new T(b.buffer, b.byteOffset, b.byteLength / T.BYTES_PER_ELEMENT); };
  return {
    skeleton: o.skeleton,
    meshes: o.meshes.map((m) => ({ mesh: m.mesh, material: m.material, P: f(m.P, Float32Array), N: f(m.N, Float32Array), UV: f(m.UV, Float32Array),
      J: f(m.J, Uint16Array), W: f(m.W, Float32Array), I: f(m.I, Uint32Array) })),
  };
}

if (process.argv[1] && process.argv[1].endsWith("agent_mesh.mjs") && process.argv[2]) {
  const a = await extractAgent(fs.readFileSync(process.argv[2]));
  console.log(a.skeleton.length, "bones;", a.meshes.map((m) => `${m.mesh}:${m.material.split("/").pop()} v${m.P.length / 3} t${m.I.length / 3}`).join(", "));
  if (process.argv[3]) fs.writeFileSync(process.argv[3], JSON.stringify(packAgent(a)));
}
