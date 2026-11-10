// ===================================================================================================================
// IRONFRAME core, part 1: scalar and vector helpers. Vectors are plain {x, y, z}; the hot loops (bullets, separation)
// work on typed arrays and scalars and never allocate. Source conventions: x forward, y left, z up; yaw in degrees
// grows anticlockwise seen from above; pitch + is down.
// ===================================================================================================================

const IF_D2R = Math.PI / 180, IF_R2D = 180 / Math.PI;

function IF_clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
function IF_lerp(a, b, t) { return a + (b - a) * t; }
function IF_fin(v, d) { return Number.isFinite(v) ? v : d; }
function IF_sign(v) { return v < 0 ? -1 : v > 0 ? 1 : 0; }
function IF_approach(v, target, step) { return v < target ? Math.min(target, v + step) : Math.max(target, v - step); }
function IF_normAngle(a) { a = a % 360; if (a > 180) a -= 360; else if (a < -180) a += 360; return a; }
function IF_angleDiff(from, to) { return IF_normAngle(to - from); }
// turn an angle toward another by at most `rate` degrees
function IF_turnAngle(a, to, rate) { const d = IF_angleDiff(a, to); return IF_normAngle(a + IF_clamp(d, -rate, rate)); }

function IF_v3(x, y, z) { return { x: x || 0, y: y || 0, z: z || 0 }; }
function IF_vset(o, x, y, z) { o.x = x; o.y = y; o.z = z; return o; }
function IF_vcopy(o, a) { o.x = a.x; o.y = a.y; o.z = a.z; return o; }
function IF_vlen(a) { return Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z); }
function IF_vlen2(a) { return a.x * a.x + a.y * a.y + a.z * a.z; }
function IF_vdist(a, b) { const dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z; return Math.sqrt(dx * dx + dy * dy + dz * dz); }
function IF_vdist2(a, b) { const dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z; return dx * dx + dy * dy + dz * dz; }
function IF_vdistXY(a, b) { const dx = a.x - b.x, dy = a.y - b.y; return Math.sqrt(dx * dx + dy * dy); }
function IF_vdot(a, b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
// o = a normalised (fallback forward when zero)
function IF_vnorm(o, a) {
  const l = Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z);
  if (l > 1e-9) { o.x = a.x / l; o.y = a.y / l; o.z = a.z / l; } else { o.x = 1; o.y = 0; o.z = 0; }
  return o;
}
// forward vector of yaw / pitch (degrees, Source pitch + down) into o
function IF_fwd(o, yaw, pitch) {
  const cp = Math.cos(pitch * IF_D2R);
  o.x = Math.cos(yaw * IF_D2R) * cp; o.y = Math.sin(yaw * IF_D2R) * cp; o.z = -Math.sin(pitch * IF_D2R);
  return o;
}
function IF_yawOf(x, y) { return Math.atan2(y, x) * IF_R2D; }
function IF_pitchOf(dx, dy, dz) { const h = Math.sqrt(dx * dx + dy * dy); return -Math.atan2(dz, h) * IF_R2D; }
// angle in degrees between two directions (not necessarily unit)
function IF_angleBetween(ax, ay, az, bx, by, bz) {
  const la = Math.sqrt(ax * ax + ay * ay + az * az), lb = Math.sqrt(bx * bx + by * by + bz * bz);
  if (la < 1e-9 || lb < 1e-9) return 0;
  return Math.acos(IF_clamp((ax * bx + ay * by + az * bz) / (la * lb), -1, 1)) * IF_R2D;
}

// squared distance from point p to segment a..b, and the parameter t (0..1) of the nearest point; scalar in, result in IF_SEG
const IF_SEG = { d2: 0, t: 0 };
function IF_segPointDist2(ax, ay, az, bx, by, bz, px, py, pz) {
  const dx = bx - ax, dy = by - ay, dz = bz - az;
  const l2 = dx * dx + dy * dy + dz * dz;
  let t = 0;
  if (l2 > 1e-9) t = IF_clamp(((px - ax) * dx + (py - ay) * dy + (pz - az) * dz) / l2, 0, 1);
  const qx = ax + dx * t - px, qy = ay + dy * t - py, qz = az + dz * t - pz;
  IF_SEG.d2 = qx * qx + qy * qy + qz * qz; IF_SEG.t = t;
  return IF_SEG;
}
// squared distance between segment a..b (a bullet's step) and a vertical segment (a mech capsule axis from z0 to z1 at x,y),
// approximated: nearest point on a..b to the capsule centre, then clamped to the axis. Good to a few units for our sizes.
function IF_segCapsuleDist2(ax, ay, az, bx, by, bz, cx, cy, z0, z1) {
  const cz = 0.5 * (z0 + z1);
  const s = IF_segPointDist2(ax, ay, az, bx, by, bz, cx, cy, cz);
  const t = s.t;
  const qx = ax + (bx - ax) * t, qy = ay + (by - ay) * t, qz = az + (bz - az) * t;
  const zz = IF_clamp(qz, z0, z1);
  const dx = qx - cx, dy = qy - cy, dz = qz - zz;
  IF_SEG.d2 = dx * dx + dy * dy + dz * dz; IF_SEG.t = t;
  return IF_SEG;
}

// Gaussian-ish noise from a uniform rng (sum of 3 uniforms, mean 0, spread about 0.5)
function IF_noise(rng) { return (rng() + rng() + rng()) - 1.5; }
// a random unit-ish spread of `deg` degrees applied to direction d (in place): perturb then normalise
function IF_spread(d, deg, rng) {
  if (deg <= 0) return d;
  const r = Math.tan(deg * IF_D2R) * Math.sqrt(rng());
  const a = rng() * Math.PI * 2;
  // basis perpendicular to d
  let ux, uy, uz;
  if (Math.abs(d.z) < 0.9) { ux = -d.y; uy = d.x; uz = 0; } else { ux = 0; uy = -d.z; uz = d.y; }
  const ul = Math.sqrt(ux * ux + uy * uy + uz * uz) || 1; ux /= ul; uy /= ul; uz /= ul;
  const vx = d.y * uz - d.z * uy, vy = d.z * ux - d.x * uz, vz = d.x * uy - d.y * ux;
  const ca = Math.cos(a) * r, sa = Math.sin(a) * r;
  d.x += ux * ca + vx * sa; d.y += uy * ca + vy * sa; d.z += uz * ca + vz * sa;
  return IF_vnorm(d, d);
}
// rotate direction d toward direction t by at most maxDeg (both unit; result in d)
function IF_steerToward(d, tx, ty, tz, maxDeg) {
  const ang = IF_angleBetween(d.x, d.y, d.z, tx, ty, tz);
  if (ang <= 1e-6) return d;
  const f = Math.min(1, maxDeg / ang);
  d.x += (tx - d.x) * f; d.y += (ty - d.y) * f; d.z += (tz - d.z) * f;
  return IF_vnorm(d, d);
}
// ballistic launch pitch (radians above horizontal) to reach a target at horizontal distance x and height dy with speed v
// under gravity g, low arc (or the 45 degree max-range shot when out of reach); returns NaN-free numbers always
function IF_ballisticPitch(v, g, x, dy, high) {
  const v2 = v * v, disc = v2 * v2 - g * (g * x * x + 2 * dy * v2);
  if (x < 1) return high ? Math.PI * 0.49 : 0;
  if (disc < 0) return Math.PI / 4;
  const root = Math.sqrt(disc);
  return Math.atan2(high ? v2 + root : v2 - root, g * x);
}
