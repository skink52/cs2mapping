// Finds strikes in a CMU take: punches and kicks with their timing, limb, height and shape.
//   node tools/anim/analyze.mjs <take.bvh> [more...]
import path from "node:path";
import { loadBVH, bvhFrame, bvhWorld } from "./bvh.mjs";
import { v3, q } from "./m3.mjs";

export function analyzeTake(file) {
  const b = loadBVH(file);
  const J = b.index;
  const n = b.frames, fps = 1 / b.dt;
  const step = Math.max(1, Math.round(fps / 60));   // analyse at ~60 Hz
  const S = [];
  for (let f = 0; f < n; f += step) {
    const W = bvhWorld(b, bvhFrame(b, f));
    const P = (k) => W[J[k]].p;
    const chestL = v3.sub(P("LeftArm"), P("RightArm"));
    const up = v3.norm(v3.sub(P("Neck1"), P("Hips")));
    const left = v3.norm(v3.perp(chestL, up));
    const fwd = v3.cross(left, up);
    const hipsL = v3.sub(P("LeftUpLeg"), P("RightUpLeg"));
    S.push({ f, W, P: Object.fromEntries(["Hips", "Head", "LeftArm", "RightArm", "LeftHand", "RightHand", "LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase", "LeftUpLeg", "RightUpLeg", "Spine1"].map((k) => [k, P(k)])), fwd, up, left, hipsL });
  }
  const armLen = v3.dist(S[0].P.LeftArm, S[0].P.LeftHand) || 1;
  const legLen = v3.dist(S[0].P.LeftUpLeg, S[0].P.LeftFoot) || 1;
  const floor = Math.min(...S.map((s) => Math.min(s.P.LeftToeBase[1], s.P.RightToeBase[1])));
  const events = [];
  const limbs = [
    ["LeftHand", "LeftArm", "punch", "L", armLen], ["RightHand", "RightArm", "punch", "R", armLen],
    ["LeftFoot", "LeftUpLeg", "kick", "L", legLen], ["RightFoot", "RightUpLeg", "kick", "R", legLen],
  ];
  for (const [end, root, kind, side, len] of limbs) {
    const ext = S.map((s) => {
      const d = v3.sub(s.P[end], s.P[root]);
      // reach along the body's forward axis, normalised
      return { all: v3.len(d) / len, fwd: v3.dot(d, s.fwd) / len, up: v3.dot(d, s.up) / len, side: v3.dot(d, s.left) / len };
    });
    for (let i = 2; i < S.length - 2; i++) {
      const e = ext[i];
      const isPeak = e.fwd >= ext[i - 1].fwd && e.fwd >= ext[i + 1].fwd && e.fwd >= ext[i - 2].fwd && e.fwd >= ext[i + 2].fwd;
      if (!isPeak) continue;
      if (kind === "punch" && e.fwd < 0.8) continue;
      if (kind === "kick" && (e.fwd < 0.55 || (S[i].P[end][1] - floor) / legLen < 0.25)) continue;
      // how fast it got there: frames since the limb was 35% shorter (forward reach)
      let j = i; while (j > 0 && ext[j].fwd > e.fwd - 0.35 * (kind === "punch" ? 1 : 0.8)) j--;
      const rise = (i - j) * step / fps;
      let k = i; while (k < S.length - 1 && ext[k].fwd > e.fwd - 0.35) k++;
      const fall = (k - i) * step / fps;
      if (rise > 0.6) continue;
      const height = (S[i].P[end][1] - floor) / (legLen * 2);
      events.push({ t: +(S[i].f / fps).toFixed(2), f: S[i].f, kind, side, reach: +e.fwd.toFixed(2), up: +e.up.toFixed(2), lat: +e.side.toFixed(2), height: +height.toFixed(2), rise: +rise.toFixed(2), fall: +fall.toFixed(2) });
    }
  }
  events.sort((a, c) => a.f - c.f);
  // merge duplicates within 0.15 s of the same limb
  const out = [];
  for (const e of events) {
    const prev = out.findLast((x) => x.kind === e.kind && x.side === e.side);
    if (prev && e.t - prev.t < 0.15) { if (e.reach > prev.reach) Object.assign(prev, e); continue; }
    out.push(e);
  }
  return { file: path.basename(file), frames: n, fps: Math.round(fps), secs: +(n / fps).toFixed(1), events: out };
}

if (process.argv[1] && process.argv[1].endsWith("analyze.mjs")) {
  for (const f of process.argv.slice(2)) {
    const r = analyzeTake(f);
    const counts = {};
    for (const e of r.events) counts[e.kind + e.side] = (counts[e.kind + e.side] || 0) + 1;
    console.log(`${r.file} ${r.secs}s ${JSON.stringify(counts)}`);
    if (process.env.VERBOSE) for (const e of r.events) console.log("   ", e.t.toFixed(2).padStart(6), e.kind, e.side, "reach", e.reach, "up", e.up, "lat", e.lat, "h", e.height, "rise", e.rise, "fall", e.fall, "f", e.f);
  }
}
