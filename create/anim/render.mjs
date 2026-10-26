// A small software renderer for animation previews: skinned CS2 agent meshes (extracted by
// ../s2/agent_mesh.mjs), a floor, debug lines and points, 5x7 text labels. Outputs RGB frames
// that preview.mjs turns into PNG contact sheets / MP4 with ffmpeg.
//   const R = new Renderer(480, 360); R.clear(); R.camera(eye, at, fov); R.drawAgent(loadAgent(json), pose, { q: [0,0,0,1], p: [0,0,0] });
// From cs2-fighter/tools/anim/render.mjs (MIT), made project-neutral.
import fs from "node:fs";
import { v3, q, xf } from "./m3.mjs";
import { unpackAgent } from "../s2/agent_mesh.mjs";
import { IDX as RIG_IDX } from "./rig.mjs";

// ------------------------------------------------------------------ agents
const AGENT_CACHE = new Map();
export function loadAgent(file) {
  if (AGENT_CACHE.has(file)) return AGENT_CACHE.get(file);
  const a = unpackAgent(JSON.parse(fs.readFileSync(file, "utf8")));
  const sk = a.skeleton;
  sk.forEach((b) => { b.local = { q: q.norm(b.quat), p: b.pos }; });
  const bind = [];
  sk.forEach((b, i) => bind.push(b.parent < 0 ? b.local : xf.mul(bind[b.parent], b.local)));
  a.bind = bind;
  a.invBind = bind.map((t) => xf.inv(t));
  a.rigIndex = sk.map((b) => (RIG_IDX[b.name] === undefined ? -1 : RIG_IDX[b.name]));
  // merge draw calls that share vertices into per-material lists
  a.parts = a.meshes.map((m) => ({ ...m, color: materialColor(m.material) }));
  AGENT_CACHE.set(file, a);
  return a;
}
// rough base colours by material name, so the preview reads like the agent
function materialColor(name) {
  const n = name.toLowerCase();
  if (/head|face/.test(n)) return [0.62, 0.47, 0.38];
  if (/bare_arm|skin/.test(n)) return [0.6, 0.45, 0.36];
  if (/glove/.test(n)) return [0.12, 0.12, 0.13];
  if (/visor|glasses/.test(n)) return [0.08, 0.1, 0.12];
  if (/mask|helmet/.test(n)) return [0.18, 0.19, 0.2];
  if (/lower|pant|leg/.test(n)) return [0.25, 0.26, 0.27];
  if (/hat|radio/.test(n)) return [0.15, 0.15, 0.16];
  return [0.33, 0.34, 0.33];
}

// world transforms for every agent bone from a rig pose (bone-merge: same-named bones copy the
// rig; the rest keep their bind offset from their parent)
export function agentBones(agent, rigPose, actor) {
  const sk = agent.skeleton;
  const W = new Array(sk.length);
  for (let i = 0; i < sk.length; i++) {
    const ri = agent.rigIndex[i];
    if (ri >= 0 && rigPose) W[i] = rigPose[ri];
    else W[i] = sk[i].parent < 0 ? sk[i].local : xf.mul(W[sk[i].parent], sk[i].local);
  }
  return W.map((w) => xf.mul(actor, w));
}

// ------------------------------------------------------------------ renderer
export class Renderer {
  constructor(w, h) {
    this.w = w; this.h = h;
    this.rgb = new Uint8Array(w * h * 3);
    this.z = new Float32Array(w * h);
    this.light = v3.norm([-0.35, -0.55, 0.75]);
    this.fill = v3.norm([0.6, 0.4, 0.3]);
  }
  clear(top = [24, 22, 30], bottom = [58, 50, 54]) {
    const { w, h } = this;
    for (let y = 0; y < h; y++) {
      const t = y / (h - 1);
      const c = [0, 1, 2].map((k) => Math.round(top[k] + (bottom[k] - top[k]) * t));
      for (let x = 0; x < w; x++) { const o = (y * w + x) * 3; this.rgb[o] = c[0]; this.rgb[o + 1] = c[1]; this.rgb[o + 2] = c[2]; }
    }
    this.z.fill(Infinity);
  }
  camera(eye, target, fovDeg = 40, up = [0, 0, 1]) {
    const f = v3.norm(v3.sub(target, eye));
    const r = v3.norm(v3.cross(f, up));
    const u = v3.cross(r, f);
    this.cam = { eye, f, r, u, k: (this.h / 2) / Math.tan((fovDeg * Math.PI / 180) / 2) };
  }
  project(p) {
    const c = this.cam, d = v3.sub(p, c.eye);
    const z = v3.dot(d, c.f);
    if (z < 1) return null;
    return [this.w / 2 + v3.dot(d, c.r) * c.k / z, this.h / 2 - v3.dot(d, c.u) * c.k / z, z];
  }
  // triangles: positions Float32 (x,y,z...), normals Float32, indices, colour [r,g,b] 0..1
  drawTris(P, Nrm, I, color, opts = {}) {
    const { w, h } = this;
    const nv = P.length / 3;
    const sx = new Float32Array(nv), sy = new Float32Array(nv), sz = new Float32Array(nv), lit = new Float32Array(nv);
    const c = this.cam;
    for (let i = 0; i < nv; i++) {
      const dx = P[i * 3] - c.eye[0], dy = P[i * 3 + 1] - c.eye[1], dz = P[i * 3 + 2] - c.eye[2];
      const z = dx * c.f[0] + dy * c.f[1] + dz * c.f[2];
      sz[i] = z;
      if (z < 1) { sx[i] = NaN; continue; }
      sx[i] = w / 2 + (dx * c.r[0] + dy * c.r[1] + dz * c.r[2]) * c.k / z;
      sy[i] = h / 2 - (dx * c.u[0] + dy * c.u[1] + dz * c.u[2]) * c.k / z;
      const nx = Nrm[i * 3], ny = Nrm[i * 3 + 1], nz = Nrm[i * 3 + 2];
      const key = Math.max(0, nx * this.light[0] + ny * this.light[1] + nz * this.light[2]);
      const fill = Math.max(0, nx * this.fill[0] + ny * this.fill[1] + nz * this.fill[2]);
      // rim from the camera direction
      const vdot = -(nx * c.f[0] + ny * c.f[1] + nz * c.f[2]);
      const rim = Math.pow(Math.max(0, 1 - Math.abs(vdot)), 3);
      lit[i] = 0.28 + 0.95 * key + 0.3 * fill + 0.55 * rim;
    }
    const tint = opts.tint || [1, 1, 1];
    const col = [color[0] * tint[0] * 255, color[1] * tint[1] * 255, color[2] * tint[2] * 255];
    const rgb = this.rgb, zb = this.z;
    for (let t = 0; t < I.length; t += 3) {
      const a = I[t], b = I[t + 1], cc = I[t + 2];
      const ax = sx[a], bx = sx[b], cx = sx[cc];
      if (Number.isNaN(ax) || Number.isNaN(bx) || Number.isNaN(cx)) continue;
      const ay = sy[a], by = sy[b], cy = sy[cc];
      const area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax);
      if (Math.abs(area) < 1e-9) continue;   // CS2 draws both faces of model polygons
      let x0 = Math.max(0, Math.floor(Math.min(ax, bx, cx))), x1 = Math.min(w - 1, Math.ceil(Math.max(ax, bx, cx)));
      let y0 = Math.max(0, Math.floor(Math.min(ay, by, cy))), y1 = Math.min(h - 1, Math.ceil(Math.max(ay, by, cy)));
      if (x0 > x1 || y0 > y1) continue;
      const ia = 1 / area;
      const za = 1 / sz[a], zbv = 1 / sz[b], zc = 1 / sz[cc];
      const la = lit[a], lb = lit[b], lc = lit[cc];
      for (let y = y0; y <= y1; y++) {
        const py = y + 0.5;
        for (let x = x0; x <= x1; x++) {
          const px = x + 0.5;
          let w0 = ((bx - px) * (cy - py) - (by - py) * (cx - px)) * ia;
          let w1 = ((cx - px) * (ay - py) - (cy - py) * (ax - px)) * ia;
          let w2 = 1 - w0 - w1;
          if (w0 < 0 || w1 < 0 || w2 < 0) continue;
          const iz = w0 * za + w1 * zbv + w2 * zc;
          const depth = 1 / iz;
          const o = y * w + x;
          if (depth >= zb[o]) continue;
          zb[o] = depth;
          const l = w0 * la + w1 * lb + w2 * lc;
          const oo = o * 3;
          rgb[oo] = Math.min(255, col[0] * l); rgb[oo + 1] = Math.min(255, col[1] * l); rgb[oo + 2] = Math.min(255, col[2] * l);
        }
      }
    }
  }
  // skinned agent: pose = rig world pose (model space), actor = {q, p} placement (with scale)
  drawAgent(agent, pose, actor, opts = {}) {
    const scale = actor.s || 1;
    const bones = agentBones(agent, pose, { q: actor.q, p: [0, 0, 0] });
    const skin = bones.map((wb, i) => xf.mul(wb, agent.invBind[i]));
    const mats = skin.map((t) => { const m = q.toMat(t.q); return [m, t.p]; });
    for (const part of agent.parts) {
      const nv = part.P.length / 3;
      const P = new Float32Array(nv * 3), Nn = new Float32Array(nv * 3);
      for (let i = 0; i < nv; i++) {
        const vx = part.P[i * 3], vy = part.P[i * 3 + 1], vz = part.P[i * 3 + 2];
        const nx = part.N[i * 3], ny = part.N[i * 3 + 1], nz = part.N[i * 3 + 2];
        let ox = 0, oy = 0, oz = 0, mx = 0, my = 0, mz = 0;
        for (let k = 0; k < 4; k++) {
          const wgt = part.W[i * 4 + k];
          if (wgt <= 0) continue;
          const [m, p] = mats[part.J[i * 4 + k]];
          ox += wgt * (m[0] * vx + m[1] * vy + m[2] * vz + p[0]);
          oy += wgt * (m[3] * vx + m[4] * vy + m[5] * vz + p[1]);
          oz += wgt * (m[6] * vx + m[7] * vy + m[8] * vz + p[2]);
          mx += wgt * (m[0] * nx + m[1] * ny + m[2] * nz);
          my += wgt * (m[3] * nx + m[4] * ny + m[5] * nz);
          mz += wgt * (m[6] * nx + m[7] * ny + m[8] * nz);
        }
        P[i * 3] = actor.p[0] + ox * scale; P[i * 3 + 1] = actor.p[1] + oy * scale; P[i * 3 + 2] = actor.p[2] + oz * scale;
        const l = Math.hypot(mx, my, mz) || 1;
        Nn[i * 3] = mx / l; Nn[i * 3 + 1] = my / l; Nn[i * 3 + 2] = mz / l;
      }
      this.drawTris(P, Nn, part.I, part.color, opts);
    }
    return bones;
  }
  line(a, b, color = [255, 220, 60], width = 1) {
    const pa = this.project(a), pb = this.project(b);
    if (!pa || !pb) return;
    const n = Math.ceil(Math.max(Math.abs(pb[0] - pa[0]), Math.abs(pb[1] - pa[1]))) + 1;
    for (let i = 0; i <= n; i++) {
      const t = i / n;
      const x = pa[0] + (pb[0] - pa[0]) * t, y = pa[1] + (pb[1] - pa[1]) * t;
      this.dot2(x, y, width, color);
    }
  }
  dot2(x, y, r, color) {
    const { w, h } = this;
    for (let yy = Math.floor(y - r + 0.5); yy <= Math.floor(y + r - 0.5); yy++) for (let xx = Math.floor(x - r + 0.5); xx <= Math.floor(x + r - 0.5); xx++) {
      if (xx < 0 || yy < 0 || xx >= w || yy >= h) continue;
      const o = (yy * w + xx) * 3; this.rgb[o] = color[0]; this.rgb[o + 1] = color[1]; this.rgb[o + 2] = color[2];
    }
  }
  point(p, r, color) { const s = this.project(p); if (s) this.dot2(s[0], s[1], r, color); }
  circle3(center, radius, axisA, axisB, color, segs = 32) {
    let prev = null;
    for (let i = 0; i <= segs; i++) {
      const a = (i / segs) * Math.PI * 2;
      const p = v3.add(center, v3.add(v3.mul(axisA, Math.cos(a) * radius), v3.mul(axisB, Math.sin(a) * radius)));
      if (prev) this.line(prev, p, color);
      prev = p;
    }
  }
  floor(z = 0, extent = 200, step = 16, color = [70, 64, 70]) {
    for (let x = -extent; x <= extent; x += step) this.line([x, -extent, z], [x, extent, z], color);
    for (let y = -extent; y <= extent; y += step) this.line([-extent, y, z], [extent, y, z], color);
  }
  // simple 5x7 bitmap text for labels
  text(x, y, str, color = [235, 230, 220], scale = 2) {
    let cx = x;
    for (const ch of String(str).toUpperCase()) {
      const g = FONT[ch] || FONT["?"];
      for (let r = 0; r < 7; r++) for (let c = 0; c < 5; c++) if (g[r] & (16 >> c)) {
        for (let yy = 0; yy < scale; yy++) for (let xx = 0; xx < scale; xx++) {
          const px = cx + c * scale + xx, py = y + r * scale + yy;
          if (px < 0 || py < 0 || px >= this.w || py >= this.h) continue;
          const o = (py * this.w + px) * 3; this.rgb[o] = color[0]; this.rgb[o + 1] = color[1]; this.rgb[o + 2] = color[2];
        }
      }
      cx += 6 * scale;
    }
  }
}

const FONT = (() => {
  const d = {
    A: [14, 17, 17, 31, 17, 17, 17], B: [30, 17, 17, 30, 17, 17, 30], C: [14, 17, 16, 16, 16, 17, 14], D: [30, 17, 17, 17, 17, 17, 30],
    E: [31, 16, 16, 30, 16, 16, 31], F: [31, 16, 16, 30, 16, 16, 16], G: [14, 17, 16, 23, 17, 17, 15], H: [17, 17, 17, 31, 17, 17, 17],
    I: [14, 4, 4, 4, 4, 4, 14], J: [7, 2, 2, 2, 2, 18, 12], K: [17, 18, 20, 24, 20, 18, 17], L: [16, 16, 16, 16, 16, 16, 31],
    M: [17, 27, 21, 21, 17, 17, 17], N: [17, 17, 25, 21, 19, 17, 17], O: [14, 17, 17, 17, 17, 17, 14], P: [30, 17, 17, 30, 16, 16, 16],
    Q: [14, 17, 17, 17, 21, 18, 13], R: [30, 17, 17, 30, 20, 18, 17], S: [15, 16, 16, 14, 1, 1, 30], T: [31, 4, 4, 4, 4, 4, 4],
    U: [17, 17, 17, 17, 17, 17, 14], V: [17, 17, 17, 17, 17, 10, 4], W: [17, 17, 17, 21, 21, 21, 10], X: [17, 17, 10, 4, 10, 17, 17],
    Y: [17, 17, 10, 4, 4, 4, 4], Z: [31, 1, 2, 4, 8, 16, 31], 0: [14, 17, 19, 21, 25, 17, 14], 1: [4, 12, 4, 4, 4, 4, 14],
    2: [14, 17, 1, 2, 4, 8, 31], 3: [31, 2, 4, 2, 1, 17, 14], 4: [2, 6, 10, 18, 31, 2, 2], 5: [31, 16, 30, 1, 1, 17, 14],
    6: [6, 8, 16, 30, 17, 17, 14], 7: [31, 1, 2, 4, 8, 8, 8], 8: [14, 17, 17, 14, 17, 17, 14], 9: [14, 17, 17, 15, 1, 2, 12],
    " ": [0, 0, 0, 0, 0, 0, 0], "-": [0, 0, 0, 31, 0, 0, 0], ".": [0, 0, 0, 0, 0, 12, 12], ":": [0, 12, 12, 0, 12, 12, 0],
    "/": [1, 1, 2, 4, 8, 16, 16], "_": [0, 0, 0, 0, 0, 0, 31], "?": [14, 17, 1, 2, 4, 0, 4], "+": [0, 4, 4, 31, 4, 4, 0],
    "(": [2, 4, 8, 8, 8, 4, 2], ")": [8, 4, 2, 2, 2, 4, 8], "#": [10, 10, 31, 10, 31, 10, 10], "=": [0, 0, 31, 0, 31, 0, 0],
  };
  return d;
})();
