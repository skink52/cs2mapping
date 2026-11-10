// 10 Nov 2026 playtest fixes (combat, movement, aim): player clips, the sky ceiling, shots on the reticle, the pilot's own IFF marker,
// the follow-camera ray. usage: node test/playtest_combat.cjs   (IF_ARENA_FILE=<arena.json> runs on another arena, as the other tests)
// The core parts run on build/core_test.cjs; the adapter helpers (cameraRay, the IFF placement) are cut out of src/cs2 and run in a sandbox.
const fs = require('fs'), path = require('path'), vm = require('vm');
const { C, ARENA, makeGame, ROOT } = require('./lib.cjs');
const DT = 1 / 64;
let fails = 0, passes = 0;
function ok(cond, name, info) { if (cond) passes++; else { fails++; console.log('FAIL ' + name + (info !== undefined ? ': ' + info : '')); } }
const r1 = (x) => Math.round(x * 10) / 10;

const FLAT = JSON.parse(JSON.stringify(ARENA));
const GROUND = 100;
FLAT.nav.height = FLAT.nav.height.map(() => GROUND); FLAT.nav.struct = FLAT.nav.struct.map(() => 0); FLAT.nav.walk = FLAT.nav.walk.map(() => 1);

// ---- a world: the flat heightfield for line / sphere traces (they don't see clips), optional clip boxes for the player hull trace
// (CS2 TracePlayer: a 32 x 32 x 72 box from the feet up; it also stands on the ground), an optional sky plane every trace hits
function makeWorld(opts) {
  opts = opts || {};
  const clips = opts.clips || [], sky = opts.sky;
  const w = { lines: 0, clipCalls: 0 };
  const plane = (a, b) => {   // the ground (z = GROUND) and the sky plane for a segment: first fraction
    let f = 1, nz = 0;
    if (a.z > GROUND && b.z <= GROUND) { const t = (a.z - GROUND) / (a.z - b.z); if (t < f) { f = t; nz = 1; } }
    if (sky !== undefined && a.z < sky && b.z >= sky) { const t = (sky - a.z) / (b.z - a.z); if (t < f) { f = t; nz = -1; } }
    return { f, nz };
  };
  w.traceLine = (a, b) => {
    w.lines++;
    const p = plane(a, b);
    return { hit: p.f < 1, frac: p.f, pos: { x: a.x + (b.x - a.x) * p.f, y: a.y + (b.y - a.y) * p.f, z: a.z + (b.z - a.z) * p.f }, normal: { x: 0, y: 0, z: p.nz || 1 }, mech: -1 };
  };
  w.traceSphere = (a, b, r) => w.traceLine(a, b);
  w.now = () => 0;
  if (opts.clipTrace !== false) w.traceClip = (a, b) => {
    w.clipCalls++;
    if (opts.noPawn) return null;
    let best = 1, n = null, solid = false;
    for (const c of clips) {
      // the box grown by the hull: x/y +-16, z from (bottom - 72) to top (the hull's feet are its origin)
      const lo = [c[0] - 16, c[1] - 16, c[2] - 72], hi = [c[3] + 16, c[4] + 16, c[5]];
      const A = [a.x, a.y, a.z], D = [b.x - a.x, b.y - a.y, b.z - a.z];
      let t0 = 0, t1 = 1, ax = -1, inside = true;
      let miss = false;
      for (let k = 0; k < 3; k++) {
        if (A[k] <= lo[k] || A[k] >= hi[k]) inside = false;
        if (Math.abs(D[k]) < 1e-9) { if (A[k] <= lo[k] || A[k] >= hi[k]) { miss = true; break; } continue; }
        let ta = (lo[k] - A[k]) / D[k], tb = (hi[k] - A[k]) / D[k], sgn = -1;
        if (ta > tb) { const s = ta; ta = tb; tb = s; sgn = 1; }
        if (ta > t0) { t0 = ta; ax = k * 2 + (sgn > 0 ? 1 : 0); }
        if (tb < t1) t1 = tb;
        if (t0 > t1) { miss = true; break; }
      }
      if (inside) { solid = true; continue; }
      if (miss || ax < 0 || t0 >= best) continue;
      best = t0; const k = ax >> 1; n = { x: 0, y: 0, z: 0 }; n[['x', 'y', 'z'][k]] = (ax & 1) ? 1 : -1;
    }
    const p = plane(a, b); if (p.f < best) { best = p.f; n = { x: 0, y: 0, z: p.nz }; }
    const pos = { x: a.x + (b.x - a.x) * best, y: a.y + (b.y - a.y) * best, z: a.z + (b.z - a.z) * best };
    return { hit: best < 1, solid, frac: best, pos, normal: n || { x: 0, y: 0, z: 1 } };
  };
  return w;
}

// a game with mechs placed by hand on the flat arena (as mechanics.cjs), with our own world
function setup(specs, opts) {
  opts = opts || {};
  const g = makeGame({ arena: FLAT, seed: 5, cfg: Object.assign({ round: { tb: 9999, cq: 9999, sk: 9999, so: 9999, warmup: 0, podium: 3 }, ai: { npcFill: false } }, opts.cfg || {}) });
  g.world = makeWorld(opts.world);
  g.setMode('tb', 2); g.startRound(0);
  specs.forEach((s, i) => {
    g.addPlayer(i, { team: s.team || (i % 2 ? 3 : 2), human: true, name: 'p' + i });
    if (s.lo) { const c = g.setLoadout(i, s.lo); if (c) throw new Error('loadout ' + s.lo + ' denied ' + c); }
    g.requestSpawn(i);
  });
  g.tick(DT, 0);
  specs.forEach((s, i) => {
    const m = g.mechs.get(i);
    m.pos.x = s.x || 0; m.pos.y = s.y || 0; m.pos.z = s.z !== undefined ? s.z : GROUND; m.vel.x = m.vel.y = m.vel.z = 0;
    m.dropT = 0; m.onGround = s.z === undefined; m.protect = 0; m.torsoYaw = m.legYaw = m.input.yaw = s.yaw || 0; m.histN = 0;
  });
  g.tick(DT, DT);
  g.events.length = 0;
  return g;
}
function run(g, secs, each) { for (let k = 0; k < Math.round(secs * 64); k++) { if (each) each(k); g.tick(DT, g.time + DT); } }
const MED = '4,101,0,0,0,301,401,501,601';

// ---------------------------------------------------------------------------------------------------------- 1. player clips
{
  // a thin clip wall (20 u, like skink52's fences on Dunes) across the path at x 600..620; line traces don't see it
  const wall = [600, -3000, 0, 620, 3000, 1200];
  const walk = (opts) => {
    const g = setup([{ lo: MED }], { world: Object.assign({ clips: [wall] }, opts || {}), cfg: opts && opts.cfg });
    const m = g.mechs.get(0);
    run(g, 3, () => { m.input.my = 1; m.input.boost = true; m.input.yaw = 0; });
    return { g, m };
  };
  {
    const { g, m } = walk();
    ok(m.pos.x < 600 - m.radius + 4 && m.pos.x > 600 - m.radius - 80, 'a boosting mech stops at a clip wall (body edge at the wall)', r1(m.pos.x) + ' (wall 600, radius ' + m.radius + ')');
    ok((g.stats.clipFound || 0) >= 1, 'the clip is discovered by the hull sweep (a line trace does not hit it)', g.stats.clipFound);
  }
  {
    const { m } = walk({ cfg: { clip: { on: false } } });
    ok(m.pos.x > 700, 'control: with the clip check off the mech passes through the wall (the playtest bug)', r1(m.pos.x));
  }
  {
    const { m } = walk({ noPawn: true });
    ok(m.pos.x > 700 && Number.isFinite(m.pos.x), 'no pawn to trace with: the check is skipped, nothing breaks', r1(m.pos.x));
  }
  {
    // a quick boost into the wall (the AC QB jet: 4 000+ u/s)
    const g = setup([{ lo: MED }], { world: { clips: [wall] } });
    const m = g.mechs.get(0);
    run(g, 0.5, () => { m.input.my = 1; m.input.yaw = 0; });
    run(g, 1, (k) => { m.input.my = 1; m.input.qb = k === 0; });
    ok(m.pos.x < 600 - m.radius + 4, 'a quick boost does not jump the clip wall', r1(m.pos.x));
  }
  {
    // sliding: walking diagonally into the wall keeps the motion along it
    const g = setup([{ lo: MED }], { world: { clips: [wall] } });
    const m = g.mechs.get(0);
    run(g, 3, () => { m.input.my = 1; m.input.yaw = 30; m.input.boost = true; });
    ok(m.pos.x < 600 - m.radius + 4 && m.pos.y > 1200, 'into the wall at 30 deg: blocked in x, slides along y', r1(m.pos.x) + ', ' + r1(m.pos.y));
  }
  {
    // a clip box to stand on (skink52 covered props with clip boxes): a mech dropping onto it lands on top
    const box = [1000, -300, 0, 1600, 300, 420];
    const g = setup([{ lo: MED, x: 1300, z: 1000 }], { world: { clips: [box] } });
    const m = g.mechs.get(0);
    run(g, 3);
    ok(Math.abs(m.pos.z - 420) < 6 && m.onGround, 'a mech lands on a clip box top and stays there', r1(m.pos.z) + ' ground ' + m.onGround);
    run(g, 2.5, () => { m.input.my = 1; m.input.yaw = 0; });
    ok(m.pos.x > 1600 + 60 && Math.abs(m.pos.z - GROUND) < 6, 'walking off the edge drops back to the ground', r1(m.pos.x) + ', ' + r1(m.pos.z));
  }
  {
    // budget: 16 mechs running loops on open ground (no clips): only discovery sweeps, one hull per mech every cfg.clip.discover ticks
    const specs = []; for (let i = 0; i < 16; i++) specs.push({ lo: MED, x: (i % 4) * 900 - 1400, y: Math.floor(i / 4) * 900 - 1400, team: 2 + (i & 1) });
    const g = setup(specs, { world: { clips: [] } });
    const w = g.world; w.clipCalls = 0;
    run(g, 4, (k) => { for (let i = 0; i < 16; i++) { const m = g.mechs.get(i); m.input.my = 1; m.input.yaw = (k * 2 + i * 20) % 360; m.input.boost = true; } });
    const per = w.clipCalls / (4 * 64);
    ok(per <= 16 / g.cfg.clip.discover + 0.5, 'open ground: about one hull trace per mech per ' + g.cfg.clip.discover + ' ticks', per.toFixed(2) + ' per tick for 16 mechs');
  }
}

// ---------------------------------------------------------------------------------------------------------- 2. the sky ceiling
{
  const SKY = 6143;   // Dunes: the toolsskybox shell's inner face (moondome 6144, toolsskybox 1 u inside)
  // the near-struct flag on every cell, so world traces run (on Dunes the sky is above the structure cells too)
  const skyGame = (lo, z) => { const g = setup([{ lo, z }], { world: { sky: SKY } }); g.skyZ = SKY; g.nav.near.fill(1); return g; };
  {
    // a bazooka rocket straight up: it used to burst on the sky (the trace near structures hit it)
    const g = skyGame('4,105,0,0,0,301,401,501,601', 4300);   // a mech hovering near the arena ceiling (a round lives 3 500 u)
    const m = g.mechs.get(0);
    const booms = [];
    run(g, 4, (k) => { m.input.pitch = -85; m.input.jump = true; m.input.fire[0] = k === 0; for (const e of g.events) if (e.t === 'explode' || e.t === 'hit') booms.push(e); g.events.length = 0; });
    const high = booms.filter((e) => e.pos && e.pos.z > 3000);
    ok(high.length === 0, 'a rocket fired at the sky vanishes there without a blast', high.map((e) => e.t + '@' + Math.round(e.pos.z)).join(','));
    ok((g.stats.skyVanish || 0) >= 1, 'the sky vanish is counted', g.stats.skyVanish);
  }
  {
    // VM-6 vertical missiles whose lock breaks at launch, flying at a point far up in the sky: they cruise under the cap
    const g = setup([{ lo: '4,0,0,201,0,301,401,501,601' }, { lo: MED, x: 4500, y: 0 }], { world: { sky: SKY } });
    g.skyZ = SKY; g.nav.near.fill(1);
    const m = g.mechs.get(0);
    let top = -1e9, launched = 0; const booms = [];
    run(g, 2.5, () => { m.input.yaw = 0; m.input.pitch = -1; });
    run(g, 7, (k) => {
      m.input.yaw = 0; m.input.pitch = -1; m.input.fire[2] = k < 3;
      for (const ms of g.missiles) if (ms.alive) { if (ms.target >= 0) { ms.target = -1; ms.aim.x = ms.pos.x + 3000; ms.aim.z = 20000; launched++; } top = Math.max(top, ms.pos.z); }
      for (const e of g.events) if (e.t === 'explode') booms.push(e); g.events.length = 0;
    });
    const cap = Math.min(SKY - g.cfg.weapon.skyPad, FLAT.bounds.max[2] + g.cfg.weapon.ceilPad);
    ok(launched > 0 && top <= cap + 1, 'lofted missiles aimed at the sky stay under the cruise cap ' + Math.round(cap) + ' (sky ' + SKY + ')', launched + ' launched, top ' + Math.round(top));
    ok(booms.every((e) => e.pos.z < SKY - 300), 'no missile bursts at the sky', booms.map((e) => Math.round(e.pos.z)).join(','));
  }
  {
    // a locked VM-6 at a far target still arrives (the cap doesn't stop the turn-over)
    const g = setup([{ lo: '4,0,0,201,0,301,401,501,601' }, { lo: MED, x: 4500, y: 0 }], { world: { sky: SKY } });
    g.skyZ = SKY; g.nav.near.fill(1);
    const m = g.mechs.get(0), v = g.mechs.get(1);
    let top = -1e9;
    run(g, 2.5, () => { m.input.yaw = 0; m.input.pitch = -1; });
    const ap0 = v.ap;
    run(g, 6, (k) => { m.input.yaw = 0; m.input.pitch = -1; m.input.fire[2] = k < 3; for (const ms of g.missiles) if (ms.alive) top = Math.max(top, ms.pos.z); });
    ok(v.ap < ap0, 'a locked missile salvo still hits a target 4 500 u away', ap0 + ' -> ' + v.ap);
    ok(top < SKY - 300, 'and stays under the sky on the way', Math.round(top));
  }
  {
    // the default without a measured sky: bounds.max z + skyDefault
    const g = setup([{ lo: MED }]);
    const want = FLAT.bounds.max[2] + g.cfg.weapon.skyDefault;
    // a rocket at the default sky: vanishes there (the bullet loop checks the sky height every tick)
    const m = g.mechs.get(0); g.nav.near.fill(1); g.world = makeWorld({ sky: want }); m.pos.z = want - 1500; m.onGround = false;
    g.mechs.get(0).weapons[0].setup(g.P.byId.get(105), 0, g.P.caps);
    const booms = [];
    run(g, 4, (k) => { m.input.pitch = -85; m.input.jump = true; m.input.fire[0] = k === 0; for (const e of g.events) if (e.t === 'explode') booms.push(e); g.events.length = 0; });
    ok(booms.length === 0 && (g.stats.skyVanish || 0) >= 1, 'no measured sky: bounds.max z + ' + g.cfg.weapon.skyDefault + ' is the sky; a rocket vanishes there', booms.length + ' booms, ' + g.stats.skyVanish);
  }
}

// ---------------------------------------------------------------------------------------------------------- 3. shots on the reticle
{
  // the follow camera as cameraRay places it (hip + cameraOffset turned by the eye angles): medium class, back 520, up 180
  const setCam = (m, yaw, pitch) => {
    const D = Math.PI / 180, cp = Math.cos(pitch * D);
    const f = { x: Math.cos(yaw * D) * cp, y: Math.sin(yaw * D) * cp, z: -Math.sin(pitch * D) };
    const r = { x: Math.sin(yaw * D), y: -Math.cos(yaw * D), z: 0 };
    const u = { x: r.y * f.z - r.z * f.y, y: r.z * f.x - r.x * f.z, z: r.x * f.y - r.y * f.x };
    const hip = { x: m.pos.x, y: m.pos.y, z: m.pos.z + m.height * 0.45 };
    m.input.camPos = { x: hip.x - f.x * 520 + u.x * 180, y: hip.y - f.y * 520 + u.y * 180, z: hip.z - f.z * 520 + u.z * 180 };
    m.input.camDir = f; m.input.yaw = yaw; m.input.pitch = pitch;
  };
  const lineDist = (p, o, d) => { const vx = p.x - o.x, vy = p.y - o.y, vz = p.z - o.z, t = vx * d.x + vy * d.y + vz * d.z; return Math.hypot(vx - d.x * t, vy - d.y * t, vz - d.z * t); };
  // reticle on the ground at several distances (camera pitched down so its ray meets z = GROUND there): the round's line must pass it
  for (const dist of [700, 1500, 3000, 5500]) {
    const g = setup([{ lo: MED }]);
    const m = g.mechs.get(0);
    // the pitch whose ray from the camera meets the ground `dist` u in front of the mech (iterate: the camera moves with the pitch)
    let pitch = 5;
    for (let it = 0; it < 30; it++) { setCam(m, 0, pitch); const c = m.input.camPos, f = m.input.camDir; const t = (c.z - GROUND) / -f.z; const x = c.x + f.x * t; pitch += (x - (m.pos.x + dist)) / dist * 4; }
    setCam(m, 0, pitch);
    const c = m.input.camPos, f = m.input.camDir, t = (c.z - GROUND) / -f.z, P = { x: c.x + f.x * t, y: c.y + f.y * t, z: GROUND };
    let ev = null;
    run(g, DT * 2, (k) => { setCam(m, 0, pitch); m.input.fire[0] = k === 0; for (const e of g.events) if (e.t === 'fire') ev = e; });
    const miss = ev ? lineDist(P, ev.pos, ev.dir) : 1e9;
    // the old aim: from the eye line (0.8 h) toward the camera ray's point 6 000 u out, with the old up vector (f x r: 2 x up too low)
    const eye = { x: m.pos.x, y: m.pos.y, z: m.pos.z + m.height * 0.8 };
    const oldCam = { x: c.x, y: c.y, z: c.z - 2 * 180 * Math.cos(pitch * Math.PI / 180) };
    const far = { x: oldCam.x + f.x * 6000, y: oldCam.y + f.y * 6000, z: oldCam.z + f.z * 6000 };
    const od = { x: far.x - eye.x, y: far.y - eye.y, z: far.z - eye.z }, ol = Math.hypot(od.x, od.y, od.z); od.x /= ol; od.y /= ol; od.z /= ol;
    const oldMiss = lineDist(P, eye, od);
    ok(ev && miss < 3, 'reticle on the ground ' + dist + ' u out: the round passes through it (was ' + Math.round(oldMiss) + ' u off)', ev ? r1(miss) : 'no fire event');
  }
  {
    // reticle on an enemy's upper body at 1 500 u: the reticle point is on its capsule (the camera ray stops at the first enemy)
    const g = setup([{ lo: MED }, { lo: MED, x: 1500, y: 0 }]);
    const m = g.mechs.get(0), v = g.mechs.get(1);
    const aimZ = v.pos.z + v.height * 0.8;
    let pitch = 0;
    for (let it = 0; it < 30; it++) { setCam(m, 0, pitch); const c = m.input.camPos, f = m.input.camDir; const z = c.z + f.z * ((v.pos.x - c.x) / f.x); pitch += (z - aimZ) / 1500 * 40; }
    m.lock.target = -1; m.lock.stage = 0;
    run(g, DT * 2, (k) => { setCam(m, 0, pitch); m.input.fire[0] = k === 0; });
    const R = m.retTick >= 0 ? m.reticle : null;
    // the hit point is the ray's closest approach to the capsule axis (as for every hitscan hit): on the ray, inside the body
    ok(R && Math.abs(R.x - v.pos.x) < v.radius && Math.abs(R.z - aimZ) < 30, 'the reticle ray stops in the enemy (not on the ground behind it)', R && (r1(R.x) + ', ' + r1(R.z)));
  }
}

// ---------------------------------------------------------------------------------------------------------- 4. adapter helpers
// cut a top-level function out of an adapter file and run it in a sandbox with the util helpers it needs
function adapterFns(file, names, extra) {
  const src = fs.readFileSync(path.join(ROOT, 'src', 'cs2', file), 'utf8'), util = fs.readFileSync(path.join(ROOT, 'src', 'cs2', '10_util.js'), 'utf8');
  const cut = (text, name) => {
    const i = text.indexOf('function ' + name + '('); if (i < 0) throw new Error(name + ' not found in ' + file);
    let depth = 0, j = text.indexOf('{', i);
    for (; j < text.length; j++) { if (text[j] === '{') depth++; else if (text[j] === '}') { depth--; if (!depth) break; } }
    return text.slice(i, j + 1);
  };
  const helpers = ['v3', 'vadd', 'vsub', 'vmul', 'vlen', 'vnorm', 'vfinite', 'fwdOf', 'rightOf'].map((n) => cut(util, n)).join('\n');
  const consts = (util.match(/^const (D2R|R2D)[^\n]*$/gm) || []).join('\n');
  const own = (src.match(/^const IFF_[A-Z_]+ = [^;]*;/gm) || []).join('\n');   // the file's own IFF constants
  const ctx = Object.assign({ Math, CONFIG: { CAM_CLIP: false } }, extra || {});
  vm.createContext(ctx);
  vm.runInContext((consts || 'const D2R = Math.PI / 180, R2D = 180 / Math.PI;') + '\n' + own + '\n' + helpers + '\n' + names.map((n) => cut(src, n)).join('\n')
    + '\n;this.__ = {' + names.join(',') + '};', ctx);
  return ctx.__;
}
{
  // cameraRay: the camera sits `up` ABOVE the followed point when level (the old f x r up vector put it 2 x up below)
  const fns = adapterFns('20_players.js', ['cameraRay'], { renderUpperPos: (m) => ({ x: m.pos.x, y: m.pos.y, z: m.pos.z + 130 }), renderUpperEnt: () => undefined, live: (e) => e });
  const pe = { slot: 0, eye: { yaw: 0, pitch: 0 }, camSent: { back: 520, up: 180, side: 0, hip: 130 }, camBack: 520, camUp: 180 };
  const m = { pos: { x: 0, y: 0, z: 100 } };
  const ray = fns.cameraRay(pe, m);
  ok(Math.abs(ray.pos.z - (100 + 130 + 180)) < 1 && Math.abs(ray.pos.x + 520) < 1, 'cameraRay: level camera 520 behind and 180 above the hip', JSON.stringify(ray.pos));
  pe.eye.pitch = 30;   // looking down 30 deg: the offset turns with the view, the camera rises
  const r2 = fns.cameraRay(pe, m), want = 230 + 520 * Math.sin(Math.PI / 6) + 180 * Math.cos(Math.PI / 6);
  ok(Math.abs(r2.pos.z - want) < 1, 'cameraRay: looking down 30 deg the camera rises over the mech', r1(r2.pos.z) + ' want ' + r1(want));
  pe.eye.pitch = 0; pe.camSent.side = 40;   // cameraOffset y is LEFT
  const r3 = fns.cameraRay(pe, m);
  ok(Math.abs(r3.pos.y - 40) < 1, 'cameraRay: a side kick of +40 moves the camera 40 u left (+y at yaw 0)', r1(r3.pos.y));
}
{
  // the pilot's own IFF marker never sits on their reticle; anybody else's stays where it was
  let fns = null;
  try { fns = adapterFns('40_fx.js', ['iffClearOfReticle']); } catch (e) { /* not there */ }
  ok(!!fns, 'iffClearOfReticle exists in 40_fx.js');
  if (fns) {
    const cam = { x: -520, y: 0, z: 410 }, dir = { x: 1, y: 0, z: 0 };
    const pos = { x: 0, y: 0, z: 458 };   // medium: feet 100 + 288 + 70; the reticle ray passes 48 u under it
    const out = fns.iffClearOfReticle(pos, cam, dir);
    const ang = (p) => { const vx = p.x - cam.x, vy = p.y - cam.y, vz = p.z - cam.z, l = Math.hypot(vx, vy, vz); return Math.acos(vx / l) * 180 / Math.PI; };
    ok(ang(out) >= 7.9 && out.z > pos.z && Math.abs(out.x) < 1, 'own marker over the reticle is lifted clear of it', r1(ang(pos)) + ' deg -> ' + r1(ang(out)) + ' deg, z ' + r1(out.z));
    const far = { x: 0, y: 0, z: 700 }, same = fns.iffClearOfReticle(far, cam, dir);
    ok(same.z === 700 && same.x === 0, 'a marker already clear of the reticle stays put', JSON.stringify(same));
    const below = { x: 0, y: 0, z: 380 }, ob = fns.iffClearOfReticle(below, cam, dir);
    ok(ob && ang(ob) >= 7.9 && ob.z > 410, 'a marker just under the reticle line goes over it (never down into the mech)', ob && r1(ob.z));
    const up = fns.iffClearOfReticle({ x: 0, y: 0, z: 458 }, cam, { x: 0.2, y: 0, z: 0.98 });   // looking straight up past it: no lift helps
    ok(up === null || ang(up) >= 0, 'a marker the lift cannot clear is hidden (null) or placed', JSON.stringify(up));
  }
}

console.log(`playtest_combat: ${passes} passed, ${fails} failed`);
process.exit(fails ? 1 : 0);
