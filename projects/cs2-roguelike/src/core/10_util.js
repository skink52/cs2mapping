// ===================================================================================
// Seeded RNG (mulberry32) and small vector helpers. One Rng per round so a run replays from its seed.
// ===================================================================================
class Rng {
  constructor(seed) { this.s = (seed >>> 0) || 1; }
  next() {
    let t = (this.s += 0x6D2B79F5) >>> 0;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  int(n) { return Math.floor(this.next() * n); }
  pick(a) { return a[this.int(a.length)]; }
  shuffle(a) { for (let i = a.length - 1; i > 0; i--) { const j = this.int(i + 1); const t = a[i]; a[i] = a[j]; a[j] = t; } return a; }
}

const V = {
  add: (a, b) => ({ x: a.x + b.x, y: a.y + b.y, z: a.z + b.z }),
  sub: (a, b) => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z }),
  mul: (a, s) => ({ x: a.x * s, y: a.y * s, z: a.z * s }),
  dot: (a, b) => a.x * b.x + a.y * b.y + a.z * b.z,
  len: (a) => Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z),
  dist: (a, b) => Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2),
  dist2d: (a, b) => Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2),
  norm: (a) => { const l = Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z) || 1; return { x: a.x / l, y: a.y / l, z: a.z / l }; },
  fromAngles: (ang) => {   // Source angles: pitch down-positive, yaw about z
    const p = ang.pitch * Math.PI / 180, y = ang.yaw * Math.PI / 180;
    return { x: Math.cos(p) * Math.cos(y), y: Math.cos(p) * Math.sin(y), z: -Math.sin(p) };
  },
  yawTo: (from, to) => Math.atan2(to.y - from.y, to.x - from.x) * 180 / Math.PI,
  inBox: (p, b, pad = 0) => p.x >= b[0] - pad && p.x <= b[3] + pad && p.y >= b[1] - pad && p.y <= b[4] + pad && p.z >= b[2] - pad && p.z <= b[5] + pad,
  // distance from point p to segment a-b
  segDist: (p, a, b) => {
    const ab = V.sub(b, a), ap = V.sub(p, a); const l2 = V.dot(ab, ab) || 1;
    const t = Math.max(0, Math.min(1, V.dot(ap, ab) / l2));
    return V.dist(p, V.add(a, V.mul(ab, t)));
  },
};

const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const fmtTime = (s) => { s = Math.max(0, Math.ceil(s)); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
