// Small 3D maths for the animation tools: vectors [x,y,z], quaternions [x,y,z,w],
// 3x3 row-major matrices, rigid transforms, easing and monotone cubic curves.
// Model space is CS2's: +X forward, +Y left, +Z up. No dependencies.
// From cs2-fighter/tools/anim/m3.mjs (MIT), made project-neutral.
export const DEG = Math.PI / 180;

export const v3 = {
  add: (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]],
  sub: (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]],
  mul: (a, s) => [a[0] * s, a[1] * s, a[2] * s],
  madd: (a, b, s) => [a[0] + b[0] * s, a[1] + b[1] * s, a[2] + b[2] * s],
  dot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2],
  cross: (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]],
  len: (a) => Math.hypot(a[0], a[1], a[2]),
  dist: (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]),
  norm: (a) => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; },
  lerp: (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t],
  neg: (a) => [-a[0], -a[1], -a[2]],
  // component of a perpendicular to unit vector n
  perp: (a, n) => { const d = a[0] * n[0] + a[1] * n[1] + a[2] * n[2]; return [a[0] - n[0] * d, a[1] - n[1] * d, a[2] - n[2] * d]; },
};

export const q = {
  I: () => [0, 0, 0, 1],
  mul: (a, b) => [
    a[3] * b[0] + a[0] * b[3] + a[1] * b[2] - a[2] * b[1],
    a[3] * b[1] - a[0] * b[2] + a[1] * b[3] + a[2] * b[0],
    a[3] * b[2] + a[0] * b[1] - a[1] * b[0] + a[2] * b[3],
    a[3] * b[3] - a[0] * b[0] - a[1] * b[1] - a[2] * b[2],
  ],
  conj: (a) => [-a[0], -a[1], -a[2], a[3]],
  norm: (a) => { const l = Math.hypot(a[0], a[1], a[2], a[3]) || 1; return [a[0] / l, a[1] / l, a[2] / l, a[3] / l]; },
  axisAngle: (ax, ang) => { const n = v3.norm(ax), s = Math.sin(ang / 2); return [n[0] * s, n[1] * s, n[2] * s, Math.cos(ang / 2)]; },
  rotate: (a, v) => {
    // v' = a v a*
    const [x, y, z, w] = a;
    const ix = w * v[0] + y * v[2] - z * v[1], iy = w * v[1] + z * v[0] - x * v[2];
    const iz = w * v[2] + x * v[1] - y * v[0], iw = -x * v[0] - y * v[1] - z * v[2];
    return [ix * w + iw * -x + iy * -z - iz * -y, iy * w + iw * -y + iz * -x - ix * -z, iz * w + iw * -z + ix * -y - iy * -x];
  },
  dot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3],
  slerp: (a, b, t) => {
    let d = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3];
    let bb = b;
    if (d < 0) { d = -d; bb = [-b[0], -b[1], -b[2], -b[3]]; }
    if (d > 0.9995) return q.norm([a[0] + (bb[0] - a[0]) * t, a[1] + (bb[1] - a[1]) * t, a[2] + (bb[2] - a[2]) * t, a[3] + (bb[3] - a[3]) * t]);
    const th = Math.acos(Math.min(1, d)), s = Math.sin(th);
    const wa = Math.sin((1 - t) * th) / s, wb = Math.sin(t * th) / s;
    return [a[0] * wa + bb[0] * wb, a[1] * wa + bb[1] * wb, a[2] * wa + bb[2] * wb, a[3] * wa + bb[3] * wb];
  },
  // shortest rotation taking unit-ish vector a onto b
  between: (a, b) => {
    const an = v3.norm(a), bn = v3.norm(b);
    const d = v3.dot(an, bn);
    if (d > 0.999999) return [0, 0, 0, 1];
    if (d < -0.999999) {
      let ax = v3.cross([1, 0, 0], an);
      if (v3.len(ax) < 1e-6) ax = v3.cross([0, 1, 0], an);
      return q.axisAngle(ax, Math.PI);
    }
    const c = v3.cross(an, bn);
    return q.norm([c[0], c[1], c[2], 1 + d]);
  },
  angle: (a) => 2 * Math.acos(Math.min(1, Math.abs(a[3]))),
  // rotation from an orthonormal basis given as columns (x axis, y axis, z axis)
  fromBasis: (x, y, z) => q.fromMat(m3.fromCols(x, y, z)),
  fromMat: (m) => {
    const tr = m[0] + m[4] + m[8];
    let x, y, z, w;
    if (tr > 0) { const s = Math.sqrt(tr + 1) * 2; w = 0.25 * s; x = (m[7] - m[5]) / s; y = (m[2] - m[6]) / s; z = (m[3] - m[1]) / s; }
    else if (m[0] > m[4] && m[0] > m[8]) { const s = Math.sqrt(1 + m[0] - m[4] - m[8]) * 2; w = (m[7] - m[5]) / s; x = 0.25 * s; y = (m[1] + m[3]) / s; z = (m[2] + m[6]) / s; }
    else if (m[4] > m[8]) { const s = Math.sqrt(1 + m[4] - m[0] - m[8]) * 2; w = (m[2] - m[6]) / s; x = (m[1] + m[3]) / s; y = 0.25 * s; z = (m[5] + m[7]) / s; }
    else { const s = Math.sqrt(1 + m[8] - m[0] - m[4]) * 2; w = (m[3] - m[1]) / s; x = (m[2] + m[6]) / s; y = (m[5] + m[7]) / s; z = 0.25 * s; }
    return q.norm([x, y, z, w]);
  },
  toMat: ([x, y, z, w]) => [
    1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w),
    2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w),
    2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
  // twist of rotation a about unit axis n (swing-twist decomposition): returns [swing, twist]
  swingTwist: (a, n) => {
    const p = v3.dot([a[0], a[1], a[2]], n);
    let tw = q.norm([n[0] * p, n[1] * p, n[2] * p, a[3]]);
    if (!Number.isFinite(tw[0])) tw = [0, 0, 0, 1];
    const sw = q.mul(a, q.conj(tw));
    return [sw, tw];
  },
  twistAngle: (a, n) => {
    const p = v3.dot([a[0], a[1], a[2]], n);
    return 2 * Math.atan2(p, a[3]);
  },
  // euler for SMD: R = Rz(z) Ry(y) Rx(x)
  toEulerSMD: (a) => {
    const m = q.toMat(a);
    const sy = -m[6];
    let x, y, z;
    if (Math.abs(sy) < 0.99999) { y = Math.asin(sy); x = Math.atan2(m[7], m[8]); z = Math.atan2(m[3], m[0]); }
    else { y = sy > 0 ? Math.PI / 2 : -Math.PI / 2; x = Math.atan2(-m[5], m[4]); z = 0; }
    return [x, y, z];
  },
  fromEulerZYX: (rz, ry, rx) => q.mul(q.axisAngle([0, 0, 1], rz), q.mul(q.axisAngle([0, 1, 0], ry), q.axisAngle([1, 0, 0], rx))),
  // keep b in the same hemisphere as a (for smooth interpolation / filtering)
  near: (a, b) => (a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3] < 0 ? [-b[0], -b[1], -b[2], -b[3]] : b),
};

export const m3 = {
  I: () => [1, 0, 0, 0, 1, 0, 0, 0, 1],
  mul: (a, b) => {
    const o = new Array(9);
    for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) o[r * 3 + c] = a[r * 3] * b[c] + a[r * 3 + 1] * b[3 + c] + a[r * 3 + 2] * b[6 + c];
    return o;
  },
  T: (a) => [a[0], a[3], a[6], a[1], a[4], a[7], a[2], a[5], a[8]],
  apply: (m, v) => [m[0] * v[0] + m[1] * v[1] + m[2] * v[2], m[3] * v[0] + m[4] * v[1] + m[5] * v[2], m[6] * v[0] + m[7] * v[1] + m[8] * v[2]],
  fromCols: (a, b, c) => [a[0], b[0], c[0], a[1], b[1], c[1], a[2], b[2], c[2]],
  col: (m, i) => [m[i], m[3 + i], m[6 + i]],
};

// rigid transform {q, p}: world = parent * local
export const xf = {
  mul: (a, b) => ({ q: q.norm(q.mul(a.q, b.q)), p: v3.add(a.p, q.rotate(a.q, b.p)) }),
  inv: (a) => { const iq = q.conj(a.q); return { q: iq, p: v3.neg(q.rotate(iq, a.p)) }; },
  apply: (a, v) => v3.add(a.p, q.rotate(a.q, v)),
  lerp: (a, b, t) => ({ q: q.slerp(a.q, b.q, t), p: v3.lerp(a.p, b.p, t) }),
};

export const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
export const lerp = (a, b, t) => a + (b - a) * t;
export const smooth = (t) => { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); };
export const smoother = (t) => { t = clamp(t, 0, 1); return t * t * t * (t * (t * 6 - 15) + 10); };

// monotone cubic (Fritsch-Carlson) curve through points (x[i], y[i]): slopes, then evaluation.
// Used for retiming (key pairs) and keyed postures: no overshoot between keys.
export function monotoneSlopes(x, y) {
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
export function hermiteMap(x, y, m, v) {
  const n = x.length;
  if (v <= x[0]) return y[0];
  if (v >= x[n - 1]) return y[n - 1];
  let i = 0; while (i < n - 2 && v > x[i + 1]) i++;
  const h = x[i + 1] - x[i], t = (v - x[i]) / h;
  const t2 = t * t, t3 = t2 * t;
  return (2 * t3 - 3 * t2 + 1) * y[i] + (t3 - 2 * t2 + t) * h * m[i] + (-2 * t3 + 3 * t2) * y[i + 1] + (t3 - t2) * h * m[i + 1];
}
