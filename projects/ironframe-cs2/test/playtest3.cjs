// 10 Nov 2026 evening playtest (Sprawl) fixes in the core: bumps and the step height, step smoothing, the jets, rockets (no-lock fire, a
// roof over the launcher, phantom heightfield ramps beside towers and under decks), the AI fill skill. usage: node test/playtest3.cjs
const { C, ARENA, makeGame } = require('./lib.cjs');
const DT = 1 / 64;
let fails = 0, passes = 0;
function ok(cond, name, info) { if (cond) passes++; else { fails++; console.log('FAIL ' + name + (info !== undefined ? ': ' + info : '')); } }
const r1 = (x) => Math.round(x * 10) / 10;
const GROUND = 100;
const MED = '4,101,0,0,0,301,401,501,601';

// ---- a world of boxes on a flat floor: line and sphere traces (the sphere as a point against the boxes grown by r), every nav cell
// "near a structure" so the core asks the world (as in Sprawl's city). boxes: [x0, y0, z0, x1, y1, z1]
function boxWorld(boxes) {
  const w = { lines: 0, spheres: 0, now: () => 0 };
  function sweep(a, b, r) {
    let best = 1, n = null, solid = false;
    const all = boxes.concat([[-1e6, -1e6, -1e6, 1e6, 1e6, GROUND]]);
    for (const c of all) {
      const lo = [c[0] - r, c[1] - r, c[2] - r], hi = [c[3] + r, c[4] + r, c[5] + r];
      const A = [a.x, a.y, a.z], D = [b.x - a.x, b.y - a.y, b.z - a.z];
      let t0 = 0, t1 = 1, ax = -1, inside = true, miss = false;
      for (let k = 0; k < 3; k++) {
        if (A[k] <= lo[k] || A[k] >= hi[k]) inside = false;
        if (Math.abs(D[k]) < 1e-9) { if (A[k] <= lo[k] || A[k] >= hi[k]) { miss = true; break; } continue; }
        let ta = (lo[k] - A[k]) / D[k], tb = (hi[k] - A[k]) / D[k], sgn = -1;
        if (ta > tb) { const s = ta; ta = tb; tb = s; sgn = 1; }
        if (ta > t0) { t0 = ta; ax = k * 2 + (sgn > 0 ? 1 : 0); }
        if (tb < t1) t1 = tb;
        if (t0 > t1) { miss = true; break; }
      }
      if (inside) { solid = true; best = 0; n = { x: 0, y: 0, z: 1 }; continue; }
      if (miss || ax < 0 || t0 >= best) continue;
      best = t0; const k = ax >> 1; n = { x: 0, y: 0, z: 0 }; n[['x', 'y', 'z'][k]] = (ax & 1) ? 1 : -1;
    }
    return { hit: best < 1, solid, frac: best, pos: { x: a.x + (b.x - a.x) * best, y: a.y + (b.y - a.y) * best, z: a.z + (b.z - a.z) * best }, normal: n || { x: 0, y: 0, z: 1 }, mech: -1 };
  }
  w.traceLine = (a, b) => { w.lines++; return sweep(a, b, 0); };
  w.traceSphere = (a, b, r) => { w.spheres++; return sweep(a, b, r); };
  return w;
}
function arena(struct) {
  const A = JSON.parse(JSON.stringify(ARENA));
  A.nav.height = A.nav.height.map(() => GROUND); A.nav.walk = A.nav.walk.map(() => 1); A.nav.struct = A.nav.struct.map(() => (struct ? 1 : 0));
  return A;
}
function setup(specs, opts) {
  opts = opts || {};
  const A = opts.arena || arena(true);
  const g = makeGame({ arena: A, seed: opts.seed || 5, cfg: Object.assign({ round: { tb: 9999, cq: 9999, sk: 9999, so: 9999, warmup: 0, podium: 3 }, ai: { npcFill: false }, clip: { on: false } }, opts.cfg || {}) });
  if (opts.boxes) g.world = boxWorld(opts.boxes);
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
    m.dropT = 0; m.onGround = true; m.protect = 0; m.torsoYaw = m.legYaw = m.input.yaw = s.yaw || 0; m.histN = 0; m.en = m.enMax;
  });
  g.tick(DT, DT);
  g.events.length = 0;
  return g;
}
function run(g, secs, each) { for (let k = 0; k < Math.round(secs * 64); k++) { if (each) each(k); g.tick(DT, g.time + DT); } }
function aim(m, t) {
  const ox = m.pos.x, oy = m.pos.y, oz = m.pos.z + m.height * 0.8;
  m.input.yaw = Math.atan2(t.pos.y - oy, t.pos.x - ox) * 180 / Math.PI;
  m.input.pitch = -Math.atan2(t.pos.z + t.height * 0.55 - oz, Math.hypot(t.pos.x - ox, t.pos.y - oy)) * 180 / Math.PI;
}

// ---------------------------------------------------------------------------------------------------------- 1. bumps and steps
{
  // a 40 u kerb across the path (x 600..700), a 16 u slab edge (x 1200..3000): the walking mech must cross both without losing speed
  const g = setup([{ lo: MED }], { boxes: [[600, -3000, GROUND, 700, 3000, GROUND + 40], [1200, -3000, GROUND, 3000, 3000, GROUND + 16]] });
  const m = g.mechs.get(0);
  let minSpeed = 1e9, maxZ = 0, maxVisJump = 0, lastVis = m.pos.z, offSeen = 0, t650 = -1;
  run(g, 4, (k) => {
    m.input.my = 1; m.input.yaw = 0;
    if (k > 64) minSpeed = Math.min(minSpeed, m.speed);
    maxZ = Math.max(maxZ, m.pos.z);
    const vis = m.pos.z + m.stepOff; maxVisJump = Math.max(maxVisJump, Math.abs(vis - lastVis)); lastVis = vis;
    offSeen = Math.max(offSeen, Math.abs(m.stepOff));
    if (t650 < 0 && m.pos.x > 650) t650 = k;
  });
  ok(m.pos.x > 1500, 'a walking mech crosses a 40 u kerb and a 16 u slab edge (it used to stop dead at anything over 4 u)', r1(m.pos.x));
  ok(minSpeed > m.walkSpeed * 0.9, 'and keeps its walking speed over them', r1(minSpeed) + ' of ' + m.walkSpeed);
  ok(Math.abs(maxZ - (GROUND + 40)) < 1 && Math.abs(m.pos.z - (GROUND + 16)) < 1, 'it follows the ground: up on the kerb, down, up on the slab', r1(maxZ) + ' / ' + r1(m.pos.z));
  ok(offSeen > 20, 'the step is eased: stepOff holds the drawn mech back', r1(offSeen));
  ok(maxVisJump < 20, 'the drawn height never jumps more than a slope would in a tick', r1(maxVisJump));
  ok(m.stepOff === 0, 'the offset is gone once the mech walks on the flat', m.stepOff);
}
{
  // boosting over the kerb as well (1 500 u/s)
  const g = setup([{ lo: MED }], { boxes: [[600, -3000, GROUND, 700, 3000, GROUND + 60]] });
  const m = g.mechs.get(0);
  run(g, 2, () => { m.input.my = 1; m.input.boost = true; m.input.yaw = 0; });
  ok(m.pos.x > 2000, 'a boosting mech crosses a 60 u kerb', r1(m.pos.x));
}
{
  // over the step height it is a wall: medium 288 u -> step max(80, 0.3 x 288) = 86.4
  const g = setup([{ lo: MED }], { boxes: [[600, -3000, GROUND, 700, 3000, GROUND + 130]] });
  const m = g.mechs.get(0);
  run(g, 3, () => { m.input.my = 1; m.input.yaw = 0; });
  ok(m.pos.x < 600 && m.pos.z === GROUND, 'a 130 u ledge stops a medium mech (step height 86 u)', r1(m.pos.x) + ' z ' + r1(m.pos.z));
  const g2 = setup([{ lo: '8,103,0,0,0,301,401,501,601' }], { boxes: [[600, -3000, GROUND, 700, 3000, GROUND + 95]] });
  const h = g2.mechs.get(0);
  run(g2, 4, () => { h.input.my = 1; h.input.yaw = 0; });
  ok(h.pos.x > 800, 'a heavy (336 u, step 100 u) walks over a 95 u ledge', r1(h.pos.x));
}
{
  // a wall is still a wall, and a mech standing against it can walk away (a sweep that starts touching must not pin it)
  const g = setup([{ lo: MED }], { boxes: [[600, -3000, GROUND, 700, 3000, GROUND + 1200]] });
  const m = g.mechs.get(0);
  run(g, 3, () => { m.input.my = 1; m.input.boost = true; m.input.yaw = 0; });
  ok(m.pos.x < 600 - m.radius + 6, 'a tall wall stops a boosting mech at its body radius', r1(m.pos.x));
  const x0 = m.pos.x;
  run(g, 1.5, () => { m.input.my = -1; m.input.boost = false; m.input.yaw = 0; });
  ok(m.pos.x < x0 - 300, 'and it walks away from the wall again', r1(x0 - m.pos.x));
}

// ---------------------------------------------------------------------------------------------------------- 2. jets
{
  const g = setup([{ lo: MED }], { arena: arena(false) });
  const m = g.mechs.get(0), MV = g.move;
  let top = 0, maxVz = 0, tEmpty = -1, k0 = 0;
  run(g, 8, (k) => {
    m.input.jump = tEmpty < 0;
    top = Math.max(top, m.pos.z - GROUND); maxVz = Math.max(maxVz, m.vel.z);
    if (tEmpty < 0 && (m.enStalled > 0 || m.en <= 0)) tEmpty = k / 64;
  });
  ok(tEmpty > 3 && tEmpty < 4.6, 'a full standard tank holds the jets 3-4.6 s (it was 6.8 s)', tEmpty);
  ok(maxVz <= MV.hover_climb + 1 && maxVz > 400, 'the climb speed is capped at hover_climb (it accelerated to 2 500 u/s)', r1(maxVz));
  ok(top > 1500 && top < 2800, 'one tank lifts a medium 1 500-2 800 u, not to the 5 000 u ceiling', r1(top));
  // recharge: from the redline on the ground
  const g2 = setup([{ lo: MED }], { arena: arena(false) });
  const m2 = g2.mechs.get(0);
  m2.en = 0; m2.enStalled = m2.stallTime; m2.enPause = 0;
  let tFull = -1;
  run(g2, 12, (k) => { if (tFull < 0 && m2.en >= m2.enMax - 1) tFull = k / 64; });
  ok(tFull > 4.5 && tFull < 7, 'empty -> full on the ground takes 4.5-7 s with the stall (it was ~4.6 s incl. the stall at x1.3 regen)', tFull);
  // airborne regen is slow: gliding gives little back
  const g3 = setup([{ lo: MED }], { arena: arena(false) });
  const m3 = g3.mechs.get(0);
  m3.pos.z = GROUND + 3000; m3.onGround = false; m3.en = 100; m3.enPause = 0;
  run(g3, 1.5);
  ok(!m3.onGround && m3.en < 100 + m3.enRegen * 1.5 * 0.5, 'in the air the tank refills at air_regen_mult (' + MV.air_regen_mult + ')', r1(m3.en));
}

// ---------------------------------------------------------------------------------------------------------- 3. rockets
const VM6 = '4,101,0,201,0,301,401,501,601';    // shoulder: six hard-lock lofted missiles
const live = (g) => g.missiles.filter((x) => x.alive);
{
  // nothing in the FCS cone: the press fires the salvo unguided along the aim line, without the loft
  const g = setup([{ lo: VM6 }, { x: 0, y: 6000, lo: MED }], { arena: arena(false) });
  const a = g.mechs.get(0);
  run(g, 0.3, () => { a.input.yaw = 0; a.input.pitch = 0; a.input.fire[2] = true; });
  const L = live(g);
  ok(L.length >= 1, 'a hard-lock launcher fires on the press with no target in the cone (the button did nothing before)', L.length);
  ok(L.every((x) => x.target === -1 && !x.lofting && x.dir.x > 0.9), 'unguided: no target, no loft, along the aim line', L.map((x) => r1(x.dir.x)).join(','));
}
{
  // held on a target: nothing until the hard lock, then a guided, lofted salvo
  const g = setup([{ lo: VM6 }, { x: 2500, lo: MED }], { arena: arena(false) });
  const a = g.mechs.get(0), v = g.mechs.get(1);
  v.ap = v.apMax = 1e6;
  let firstAt = -1, stageAt = 0;
  run(g, 3, (k) => { aim(a, v); a.input.fire[2] = true; if (firstAt < 0 && live(g).length) { firstAt = k / 64; stageAt = a.lock.stage; } });
  ok(firstAt > a.lockSoft + a.lockHard - 0.1, 'holding the button on a target waits for the hard lock', r1(firstAt) + ' s, lock ' + r1(a.lockSoft + a.lockHard));
  ok(stageAt === 2 && g.events.some((e) => e.t === 'threat' && e.kind === 'launch' && e.slot === 1), 'and launches guided when it completes', stageAt);
}
{
  // a tap while the lock is building: fires unguided on release
  const g = setup([{ lo: VM6 }, { x: 2500, lo: MED }], { arena: arena(false) });
  const a = g.mechs.get(0), v = g.mechs.get(1);
  run(g, 0.25, () => { aim(a, v); a.input.fire[2] = false; });   // the FCS picks the target up
  run(g, 0.15, () => { aim(a, v); a.input.fire[2] = true; });
  ok(live(g).length === 0, 'pressed while the lock builds: held, nothing yet', live(g).length);
  run(g, 0.1, () => { aim(a, v); a.input.fire[2] = false; });
  const L = live(g);
  ok(L.length >= 1 && L.every((x) => x.target === -1), 'released before the lock: the salvo goes unguided at the reticle', L.length);
}
{
  // a roof over the launcher (a deck 400 u over the mech's feet): the guided salvo leaves straight, nothing bursts on the deck
  const deck = [-3000, -3000, GROUND + 400, 6000, 3000, GROUND + 460];
  const g = setup([{ lo: VM6 }, { x: 2500, lo: MED }], { boxes: [deck] });
  const a = g.mechs.get(0), v = g.mechs.get(1);
  v.ap = v.apMax = 1e6;
  let early = 0, launched = 0, lofted = 0;
  run(g, 2.6, () => {
    aim(a, v); a.input.fire[2] = true;
    for (const x of live(g)) { launched = 1; if (x.lofting) lofted++; }
    for (const e of g.events) if (e.t === 'explode' && e.kind === 'missile' && e.pos.z > GROUND + 330) early++;
    g.events.length = 0;
  });
  ok(launched === 1 && lofted === 0, 'under a low deck the vertical pack launches straight (no loft)', launched + ' / ' + lofted);
  ok(early === 0, 'no missile bursts on the deck above the launcher (the playtest\'s "rockets hit the roof")', early);
  // with room (a roof 1 200 u up) the apex is lowered under it
  const g2 = setup([{ lo: VM6 }, { x: 2500, lo: MED }], { boxes: [[-3000, -3000, GROUND + 1200, 6000, 3000, GROUND + 1260]] });
  const a2 = g2.mechs.get(0), v2 = g2.mechs.get(1);
  v2.ap = v2.apMax = 1e6;
  let maxZ = 0, hitRoof = 0;
  run(g2, 3.5, () => { aim(a2, v2); a2.input.fire[2] = true; for (const x of live(g2)) maxZ = Math.max(maxZ, x.pos.z); for (const e of g2.events) if (e.t === 'explode' && e.kind === 'missile' && e.pos.z > GROUND + 1100) hitRoof++; g2.events.length = 0; });
  ok(a2.weapons[2].loftTop < GROUND + 1200 - 100 && maxZ > GROUND + 500, 'under a higher roof the loft apex sits below it', r1(a2.weapons[2].loftTop) + ' top ' + r1(maxZ));
  ok(hitRoof === 0, 'and the salvo turns over without touching it', hitRoof);
}
{
  // the phantom ramp: a tower cell (roof 2 900) beside a street. The heightfield blends the roof down over the next cell; a real world
  // only has the tower box. A missile, a reticle ray and a lob flying 60 u beside the wall, below the roof, must pass.
  const A = arena(false), nav = A.nav, cell = nav.cell || 256;
  const ci = Math.floor((0 - nav.x0) / cell), cj = Math.floor((0 - nav.y0) / cell);
  nav.height[cj * nav.w + ci] = 2900; nav.struct[cj * nav.w + ci] = 1;
  const x0 = nav.x0 + ci * cell, y0 = nav.y0 + cj * cell, tower = [x0, y0, GROUND, x0 + cell, y0 + cell, 2900];
  const yPass = y0 - 60;   // 60 u outside the tower's wall
  const g = setup([{ lo: VM6, x: x0 - 1500, y: yPass }, { x: x0 + 2200, y: yPass, lo: MED }], { arena: A, boxes: [tower] });
  const a = g.mechs.get(0), v = g.mechs.get(1);
  const N = g.nav;
  ok(N.height(x0 + cell / 2, yPass) > GROUND + 300, 'control: the bilinear heightfield has a ramp beside the tower', r1(N.height(x0 + cell / 2, yPass)));
  const p = { x: a.pos.x, y: yPass, z: GROUND + 200 }, q = { x: v.pos.x, y: yPass, z: GROUND + 200 };
  ok(C.IF_Game.lib.IF_rayWorld(g, p, q) >= 0.999, 'a sight line along the street beside the tower is clear (lock, reticle, bullets)', C.IF_Game.lib.IF_rayWorld(g, p, q));
  const into = { x: x0 + cell / 2, y: y0 + cell / 2, z: GROUND + 200 };
  ok(C.IF_Game.lib.IF_rayWorld(g, p, into) < 0.999, 'a line into the tower itself is still blocked (the world trace)', C.IF_Game.lib.IF_rayWorld(g, p, into));
  v.ap = v.apMax = 1e6;
  let hits = 0, air = 0;
  run(g, 4.5, () => {
    aim(a, v); a.input.fire[2] = true;
    for (const e of g.events) { if (e.t === 'damage' && e.victim === 1) hits++; if (e.t === 'explode' && e.kind === 'missile' && e.pos.z > GROUND + 150 && Math.abs(e.pos.x - v.pos.x) > 500) air++; }
    g.events.length = 0;
  });
  ok(hits >= 4, 'guided missiles fired down the street past the tower reach the target', hits);
  ok(air === 0, 'none bursts in mid-air on the phantom ramp', air);
}

// ---------------------------------------------------------------------------------------------------------- 4. the fill skill
{
  const g = setup([{ lo: MED }], { arena: arena(false) });
  ok(C.IF_Ai.fillSkill(g) === 0 && C.IF_Ai.fillTier(g) === 'easy', 'a stand-alone pilot (no rank) starts against the easy fill (it was normal)', C.IF_Ai.fillSkill(g));
  const h = g.mechs.get(0), bot = g.addNpc(3, 'easy', true);
  for (let i = 0; i < 10; i++) C.IF_Ai.onKill(g, h, bot);
  ok(Math.abs(C.IF_Ai.fillSkill(g) - 0.6) < 1e-6, 'ten kills of fill bots raise the skill to 0.6 (mostly normal bots)', C.IF_Ai.fillSkill(g));
  for (let i = 0; i < 2; i++) C.IF_Ai.onKill(g, bot, h);
  ok(Math.abs(C.IF_Ai.fillSkill(g) - 0.24) < 1e-6, 'two deaths to them take three times as much back', C.IF_Ai.fillSkill(g));
  for (let i = 0; i < 40; i++) C.IF_Ai.onKill(g, bot, h);
  ok(C.IF_Ai.fillSkill(g) === 0, 'never under easy', C.IF_Ai.fillSkill(g));
  g.fillAdj = 1.4; let hard = 0; for (let i = 0; i < 200; i++) if (C.IF_Ai.fillTier(g) === 'hard') hard++;
  ok(hard > 50 && hard < 110, 'between tiers the bots are a mix (skill 1.4: ~40 % hard)', hard + ' of 200');
  g.fillAdj = 1; bot.alive = false; C.IF_Ai.retier(g, bot);
  ok(bot.ai.tierKey === 'normal' && !!bot.pendingLoadout, 'a fill bot takes the new tier and a loadout from its list at the next respawn', bot.ai.tierKey);
  const ranked = setup([{ lo: MED }], { arena: arena(false) }); ranked.mechs.get(0).rank = 25;
  ok(C.IF_Ai.fillSkill(ranked) === 2, 'a rank-25 lobby still starts on hard', C.IF_Ai.fillSkill(ranked));
  ok(C.PARTS.starter.loadouts[0].split(',').slice(1, 3).join() === '101,101', 'the first starter loadout carries two rifles (M2 was a 1 500 u shotgun: half the pilot\'s fire did nothing at range)', C.PARTS.starter.loadouts[0]);
}

// ---------------------------------------------------------------------------------------------------------- 5. legs under the torso
{
  const L = C.IF_Game.lib;
  const twist = (m) => { let d = (m.legYaw - m.torsoYaw) % 360; if (d > 180) d -= 360; if (d < -180) d += 360; return d; };
  const walk = (mx, my, secs, spin) => {
    const g = setup([{ lo: MED }], { arena: arena(false) }); const m = g.mechs.get(0);
    let worst = 0;
    run(g, secs || 1.5, (k) => { m.input.mx = mx; m.input.my = my; m.input.yaw = spin ? (k * spin / 64) % 360 : 0; worst = Math.max(worst, Math.abs(twist(m))); });
    return { m, worst };
  };
  ok(Math.abs(twist(walk(0, 1).m)) < 2, 'walking forward: the legs face the travel direction', r1(twist(walk(0, 1).m)));
  { const t = twist(walk(1, 1).m); ok(Math.abs(t + 45) < 3, 'forward-right (45 deg): the legs still face the travel direction', r1(t)); }
  { const t = twist(walk(1, 0).m); ok(Math.abs(t + 30) < 3, 'side-stepping right: the legs keep 30 deg toward the travel side (they turned the full 90)', r1(t)); }
  { const t = twist(walk(0, -1).m); ok(Math.abs(t) < 3, 'walking backwards: the legs face the torso way and back-pedal (they turned 180)', r1(t)); }
  { const t = twist(walk(-1, -1).m); ok(Math.abs(t + 45) < 3, 'backwards-left: the legs face the other way of the travel line (45 deg off the torso)', r1(t)); }
  { const w = walk(0, 1, 4, 400); ok(w.worst <= 75.01, 'a torso spinning at 400 deg/s never twists the legs past leg_twist (75 deg)', r1(w.worst)); }
  { const w = walk(1, 0, 4, -300); ok(w.worst <= 75.01, 'the same while side-stepping the other way round', r1(w.worst)); }
}

// ---------------------------------------------------------------------------------------------------------- 6. round statistics for the server
{
  const g = setup([{ lo: '4,101,101,201,209,301,401,501,601' }, { x: 900, lo: MED }], { arena: arena(false) });
  const a = g.mechs.get(0), v = g.mechs.get(1);
  v.ap = v.apMax = 4000;
  let qbs = 0;
  run(g, 9, (k) => { aim(a, v); a.input.fire[0] = true; a.input.fire[1] = true; a.input.fire[2] = true; a.input.qb = k === 30 || k === 200; if (a.input.qb) qbs++; a.input.mx = a.input.qb ? 1 : 0; });
  const t = g.pilotStats(0), tv = g.pilotStats(1);
  ok(!!t && t.shots > 20 && t.hits > 5 && t.hits <= t.shots * 12, 'pilotStats: shots and hits of the round', t && (t.shots + ' / ' + t.hits));
  ok(t.qb === 2, 'quick boosts counted', t.qb);
  ok(t.weapons.rifle && t.weapons.rifle.damage > 500, 'damage per weapon part key', JSON.stringify(t.weapons));
  ok(t.kills >= 1 && Object.values(t.weapons).reduce((n, w) => n + w.kills, 0) === t.kills, 'every kill is on a weapon', t.kills + ' ' + JSON.stringify(t.weapons));
  ok(t.frame === a.frame.key && t.mode === 'tb', 'the frame flown and the mode', t.frame + ' ' + t.mode);
  ok(tv.dmgTaken > 3000 && tv.lifeBest >= 1, 'the victim: damage taken and its longest life', tv.dmgTaken + ' ' + tv.lifeBest);
  ok(Math.abs(Object.values(t.weapons).reduce((n, w) => n + w.damage, 0) - t.damage) <= 4, 'weapon damage adds up to the round damage', t.damage);
  g.startRound(g.time);
  const z = g.pilotStats(0);
  ok(z.shots === 0 && z.qb === 0 && Object.keys(z.weapons).length === 0, 'a new round starts from zero');
}

console.log('playtest3: ' + passes + ' passed, ' + fails + ' failed');
process.exit(fails ? 1 : 0);
