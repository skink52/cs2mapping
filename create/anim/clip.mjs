// Clips: sequences of rig poses at 64 Hz, plus tools to cut them from mocap, retime, blend,
// plant feet and finish them for export.
import path from "node:path";
import { limitAnkles } from "./pose.mjs";
import { q, v3, clamp, smooth, smoother } from "./m3.mjs";
import { SK, IDX, N, fk, toLocals, mirrorPose, setWorldRot } from "./rig.mjs";
import { loadBVH } from "./bvh.mjs";
import { makeRetargeter } from "./retarget.mjs";
import { normalisePoses, gazeDir, chestDir } from "./gallery.mjs";
import { ik2, LEG, ARM, spreadTwist, armsOutOfBody, limitHips } from "./post.mjs";
import { shapeHand } from "./hands.mjs";

export const FPS = 64;
export const BVH_DIR = process.env.PB_BVH_DIR || "/tmp/claude-0/bvh";
const bvhCache = new Map();
function getTake(id) {
  if (!bvhCache.has(id)) {
    const b = loadBVH(path.join(BVH_DIR, id + ".bvh"));
    bvhCache.set(id, { b, rt: makeRetargeter(b), cache: new Map() });
  }
  return bvhCache.get(id);
}
// retargeted pose at source time t (seconds), interpolated between source frames
export function mocapPose(id, t) {
  const T = getTake(id);
  const sf = t / T.b.dt;
  const a = clamp(Math.floor(sf), 0, T.b.frames - 1), b = clamp(a + 1, 0, T.b.frames - 1), u = sf - a;
  const get = (f) => { if (!T.cache.has(f)) T.cache.set(f, T.rt(f)); return T.cache.get(f); };
  return lerpWorld(get(a), get(b), u);
}

// ------------------------------------------------------------------ pose blending
export function clonePose(W) { return W.map((t) => ({ q: t.q.slice(), p: t.p.slice() })); }
// world-space lerp of two poses whose skeletons agree (same bone lengths)
export function lerpWorld(A, B, t) { return A.map((x, i) => ({ q: q.slerp(x.q, B[i].q, t), p: v3.lerp(x.p, B[i].p, t) })); }
// local-space blend: rotations slerped per bone, pelvis position lerped; everything else
// rebuilt by FK so bone lengths stay exact
export function blendPose(A, B, t, weights = null) {
  const LA = toLocals(A), LB = toLocals(B);
  const L = LA.map((x, i) => {
    const w = weights ? (weights[i] ?? t) : t;
    return { q: q.slerp(x.q, LB[i].q, w), p: v3.lerp(x.p, LB[i].p, w) };
  });
  return fk(L);
}

// ------------------------------------------------------------------ clip
export class Clip {
  constructor(name, poses, { loop = false, fps = FPS } = {}) {
    this.name = name; this.poses = poses; this.loop = loop; this.fps = fps;
    this.root = null;          // per-frame forward displacement of the ground point (model units)
    this.fist = { L: 1, R: 1 };
    this.events = {};
  }
  get n() { return this.poses.length; }
  clone(name = this.name) { const c = new Clip(name, this.poses.map(clonePose), { loop: this.loop, fps: this.fps }); c.root = this.root && this.root.slice(); c.fist = { ...this.fist }; c.events = { ...this.events }; return c; }
  sample(t) {
    if (this.loop) t = ((t % this.n) + this.n) % this.n;
    else t = clamp(t, 0, this.n - 1);
    const a = Math.floor(t), b = this.loop ? (a + 1) % this.n : Math.min(this.n - 1, a + 1);
    return lerpWorld(this.poses[a], this.poses[b], t - a);
  }

  // cut [t0, t1] seconds of a take at 64 Hz, turned so the fighter faces +X at `alignAt`
  static fromMocap(name, take, t0, t1, { align = "gaze", alignAt = t0, yaw = 0, mirror = false, speed = 1 } = {}) {
    const n = Math.max(2, Math.round((t1 - t0) / speed * FPS) + 1);
    let poses = [];
    for (let k = 0; k < n; k++) poses.push(mocapPose(take, t0 + (k / FPS) * speed));
    if (mirror) poses = poses.map(mirrorPose);
    const ref = Math.round((alignAt - t0) / speed * FPS);
    poses = normalisePoses(poses, clamp(ref, 0, n - 1), align);
    if (yaw) poses = poses.map((W) => turn(W, yaw));
    return new Clip(name, poses);
  }

  // time warp: keys [[srcFrame, dstFrame], ...] (monotone), output length = last dst + 1
  warp(keys) {
    const src = keys.map((k) => k[0]), dst = keys.map((k) => k[1]);
    const m = monotoneSlopes(dst, src);
    const nOut = Math.round(dst[dst.length - 1]) + 1;
    const out = [];
    for (let f = 0; f < nOut; f++) out.push(this.sample(hermiteMap(dst, src, m, f)));
    this.poses = out;
    return this;
  }
  // uniform speed change
  speed(k) { const n = Math.max(2, Math.round((this.n - 1) / k) + 1); const out = []; for (let f = 0; f < n; f++) out.push(this.sample(f * k)); this.poses = out; return this; }
  slice(a, b) { this.poses = this.poses.slice(a, b); return this; }
  mirror() { this.poses = this.poses.map(mirrorPose); return this; }
  map(fn) { this.poses = this.poses.map((W, f) => fn(W, f, this) || W); return this; }

  // ground point = between the ankles, projected to the floor
  groundPoint(W) { const a = W[IDX.ankle_L].p, b = W[IDX.ankle_R].p; return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0]; }

  // Take horizontal travel out of the clip. axis "x": forward travel becomes root motion (the
  // game moves the fighter), sideways drift is removed. Returns per-frame forward displacement.
  extractRoot({ smoothFrames = 6, keepX = false } = {}) {
    const raw = this.poses.map((W) => { const p = W[IDX.pelvis].p; return [p[0], p[1]]; });
    const sm = raw.map((_, i) => {
      let sx = 0, sy = 0, c = 0;
      for (let k = -smoothFrames; k <= smoothFrames; k++) { const j = clamp(i + k, 0, raw.length - 1); sx += raw[j][0]; sy += raw[j][1]; c++; }
      return [sx / c, sy / c];
    });
    const x0 = sm[0][0], y0 = sm[0][1];
    this.root = sm.map((p) => p[0] - x0);
    this.poses = this.poses.map((W, i) => {
      const dx = keepX ? 0 : sm[i][0] - x0, dy = sm[i][1] - y0;
      return W.map((t) => ({ q: t.q, p: [t.p[0] - dx, t.p[1] - dy, t.p[2]] }));
    });
    if (keepX) this.root = null;
    return this.root;
  }
  // force root motion to a total distance (scaling the curve), adding it back if `apply`
  setRootTotal(total) { if (!this.root) return; const end = this.root[this.root.length - 1] || 1e-6; const k = total / end; this.root = this.root.map((x) => x * k); }

  // crossfade the first `n` frames from pose P (ease), and the last `n` into pose Q
  blendIn(P, n, { feet = true } = {}) {
    for (let f = 0; f < Math.min(n, this.n); f++) {
      const t = smoother((f + 1) / (n + 1));
      this.poses[f] = blendPose(P, this.poses[f], t);
    }
    return this;
  }
  blendOut(Q, n) {
    for (let k = 0; k < Math.min(n, this.n); k++) {
      const f = this.n - n + k;
      const t = smoother((k + 1) / n);
      this.poses[f] = blendPose(this.poses[f], Q, t);
    }
    return this;
  }
  // loop seam: crossfade the last n frames toward the first frames
  closeLoop(n) {
    const N0 = this.n;
    for (let k = 0; k < n; k++) {
      const f = N0 - n + k;
      const t = smooth((k + 1) / (n + 1));
      this.poses[f] = blendPose(this.poses[f], this.poses[k === n - 1 ? 0 : 0], t);
    }
    this.loop = true;
    return this;
  }

  // Feet: where a foot is low and slow it is planted; plants are held still and the leg is solved
  // to reach. floorZ is the ankle height of a flat foot.
  plantFeet({ heightTol = 2.2, speedTol = 18, minFrames = 3, floorZ = null, keep = null } = {}) {
    const fz = floorZ ?? SK_ANKLE_Z;
    for (const s of ["L", "R"]) {
      const ai = IDX["ankle_" + s];
      const P = this.poses.map((W) => W[ai].p);
      const low = P.map((p, f) => {
        const v = f > 0 ? v3.dist(p, P[f - 1]) * this.fps : 0;
        return p[2] < fz + heightTol && v < speedTol;
      });
      // runs of contact
      let f = 0;
      while (f < this.n) {
        if (!low[f]) { f++; continue; }
        let e = f; while (e + 1 < this.n && low[e + 1]) e++;
        if (e - f + 1 >= minFrames) {
          const anchor = v3.mul(P.slice(f, e + 1).reduce((a, p) => v3.add(a, p), [0, 0, 0]), 1 / (e - f + 1));
          anchor[2] = Math.max(fz, anchor[2]);
          for (let k = f; k <= e; k++) {
            // ease in/out of the plant over 2 frames
            const w = Math.min(1, (k - f + 1) / 2, (e - k + 1) / 2);
            const target = v3.lerp(this.poses[k][ai].p, anchor, w);
            ik2(this.poses[k], ...LEG[s], target, { keepEnd: true });
          }
        }
        f = e + 1;
      }
    }
    return this;
  }

  // final passes: twist bones, fingers
  finish() {
    this.poses = this.poses.map((W, f) => {
      const fist = typeof this.fist === "function" ? this.fist(f, this) : this.fist;
      for (const s of ["L", "R"]) shapeHand(W, s, handShape(fist[s]));
      armsOutOfBody(W);
      limitHips(W);
      spreadTwist(W);
      limitAnkles(W);
      return W;
    });
    return this;
  }
}

export const SK_ANKLE_Z = 4.33;
// fist amount (0 relaxed .. 1 fist) or a hands.mjs shape name -> shape
export function handShape(v) {
  if (typeof v === "string" || Array.isArray(v)) return v;
  const t = Math.max(0, Math.min(1, v ?? 1));
  return ["relaxed", "fist", t];
}

// rotate a pose about Z (degrees) around the origin
export function turn(W, deg) {
  const r = q.axisAngle([0, 0, 1], deg * Math.PI / 180);
  return W.map((t) => ({ q: q.mul(r, t.q), p: q.rotate(r, t.p) }));
}
export function shift(W, d) { return W.map((t) => ({ q: t.q, p: v3.add(t.p, d) })); }

// monotone cubic (Fritsch-Carlson) mapping from x[] to y[]
function monotoneSlopes(x, y) {
  const n = x.length, d = [], m = new Array(n).fill(0);
  for (let i = 0; i < n - 1; i++) d.push((y[i + 1] - y[i]) / Math.max(1e-9, x[i + 1] - x[i]));
  m[0] = d[0]; m[n - 1] = d[n - 2];
  for (let i = 1; i < n - 1; i++) m[i] = d[i - 1] * d[i] <= 0 ? 0 : (d[i - 1] + d[i]) / 2;
  for (let i = 0; i < n - 1; i++) {
    if (Math.abs(d[i]) < 1e-12) { m[i] = 0; m[i + 1] = 0; continue; }
    const a = m[i] / d[i], b = m[i + 1] / d[i], s = a * a + b * b;
    if (s > 9) { const t = 3 / Math.sqrt(s); m[i] = t * a * d[i]; m[i + 1] = t * b * d[i]; }
  }
  return m;
}
function hermiteMap(x, y, m, v) {
  const n = x.length;
  if (v <= x[0]) return y[0];
  if (v >= x[n - 1]) return y[n - 1];
  let i = 0; while (i < n - 2 && v > x[i + 1]) i++;
  const h = x[i + 1] - x[i], t = (v - x[i]) / h;
  const t2 = t * t, t3 = t2 * t;
  return (2 * t3 - 3 * t2 + 1) * y[i] + (t3 - 2 * t2 + t) * h * m[i] + (-2 * t3 + 3 * t2) * y[i + 1] + (t3 - t2) * h * m[i + 1];
}
export { hermiteMap, monotoneSlopes };
