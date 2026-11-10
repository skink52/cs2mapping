// Scripted-input unit tests of the core rules (DESIGN.md sections 4-7). usage: node test/mechanics.cjs
// A flat test arena (no structures, so no traces), two or three mechs placed by hand, inputs set each tick.
const fs = require('fs'), path = require('path');
const { C, ARENA, makeGame, ROOT } = require('./lib.cjs');
const L = C.IF_Game.lib;
const DT = 1 / 64;
let fails = 0, passes = 0;
function ok(cond, name, info) { if (cond) passes++; else { fails++; console.log('FAIL ' + name + (info !== undefined ? ': ' + info : '')); } }
const near = (a, b, tol) => Math.abs(a - b) <= tol;

const FLAT = JSON.parse(JSON.stringify(ARENA));
FLAT.nav.height = FLAT.nav.height.map(() => 100); FLAT.nav.struct = FLAT.nav.struct.map(() => 0); FLAT.nav.walk = FLAT.nav.walk.map(() => 1);

// a game with mechs at given positions, already landed and unprotected
function setup(specs, opts) {
  opts = opts || {};
  const g = makeGame({ arena: FLAT, seed: opts.seed || 3, cfg: Object.assign({ round: { tb: 9999, cq: 9999, sk: 9999, so: 9999, warmup: 0, podium: 3 }, ai: { npcFill: false } }, opts.cfg || {}) });
  g.setMode(opts.mode || 'tb', 2); g.startRound(0);
  specs.forEach((s, i) => {
    g.addPlayer(i, { team: s.team || (i % 2 ? 3 : 2), human: true, name: 'p' + i, pilot: s.pilot || null });
    if (s.lo) { const c = g.setLoadout(i, s.lo); if (c) throw new Error('loadout ' + s.lo + ' denied ' + c); }
    g.requestSpawn(i);
  });
  g.tick(DT, 0);
  specs.forEach((s, i) => {
    const m = g.mechs.get(i);
    m.pos.x = s.x || 0; m.pos.y = s.y || 0; m.pos.z = 100; m.vel.x = m.vel.y = m.vel.z = 0;
    m.dropT = 0; m.onGround = true; m.protect = 0; m.torsoYaw = m.legYaw = m.input.yaw = s.yaw || 0; m.histN = 0;
  });
  g.tick(DT, DT);   // rebuild the live list and the grid at the new places
  g.events.length = 0;
  return g;
}
function aim(g, m, t) {
  const ox = m.pos.x, oy = m.pos.y, oz = m.pos.z + m.height * 0.8;
  const tx = t.pos.x + t.vel.x * 0, ty = t.pos.y, tz = t.pos.z + t.height * 0.55;
  m.input.yaw = Math.atan2(ty - oy, tx - ox) * 180 / Math.PI;
  m.input.pitch = -Math.atan2(tz - oz, Math.hypot(tx - ox, ty - oy)) * 180 / Math.PI;
}
function run(g, secs, each) { for (let k = 0; k < Math.round(secs * 64); k++) { if (each) each(k); g.tick(DT, g.time + DT); } }
function dmgEvents(g, victim) { return g.events.filter((e) => e.t === 'damage' && e.victim === victim); }

// ---------------------------------------------------------------------------------------------------------- movement
{
  const g = setup([{ lo: '4,101,0,0,0,301,401,501,601' }]);
  const m = g.mechs.get(0);
  run(g, 1);
  const en0 = m.en, cost = m.qbCost;
  m.input.mx = 1; m.input.qb = true; run(g, DT); m.input.qb = false;
  ok(near(en0 - m.en, cost, 1), 'QB costs ' + cost + ' EN', en0 - m.en);
  ok(Math.hypot(m.vel.x, m.vel.y) > m.qbSpeed * 0.8, 'QB impulse ~ class QB speed', Math.hypot(m.vel.x, m.vel.y));
  const qbs = () => g.events.filter((e) => e.t === 'qb').length;
  g.events.length = 0;
  run(g, 0.2, (k) => { m.input.qb = k % 2 === 0; });
  ok(qbs() === 0, 'QB cooldown blocks a second dodge inside 0.45 s', qbs());
  m.input.qb = false; run(g, 0.3); m.input.qb = true; run(g, DT); m.input.qb = false;
  ok(qbs() === 1, 'QB again after the cooldown', qbs());
  // EN stall: boost until empty
  m.input.mx = 0; m.input.my = 1; m.input.boost = true; m.input.jump = true;
  let emptyAt = -1;
  run(g, 12, () => { if (emptyAt < 0 && m.en <= 0) emptyAt = g.time; });
  ok(emptyAt > 0 && m.enStalled > 0 || g.events.some((e) => e.t === 'en_empty'), 'boost + hover empties the tank and stalls');
  m.input.boost = false; m.input.jump = false; m.input.my = 0;
  // wait to land and empty again to measure the stall cleanly
  run(g, 4);
  m.en = 0; m.spendEn(1); const stall = m.enStalled;
  run(g, stall - 0.1);
  ok(m.en === 0, 'no regen during the stall', m.en);
  run(g, 0.5);
  ok(m.en > 0, 'regen after the stall (' + stall + ' s)', m.en);
}
{ // landing lag
  const g = setup([{ lo: '8,101,0,0,0,301,401,501,601' }]);
  const m = g.mechs.get(0);
  m.pos.z = 2000; m.onGround = false; m.vel.z = -1600;
  let lag = 0, hard = false;
  run(g, 2, () => { if (m.landLag > lag) lag = m.landLag; });
  hard = g.events.some((e) => e.t === 'land' && e.hard);
  ok(hard && near(lag, m.landLagTime, 0.03), 'hard landing lag ' + m.landLagTime + ' s (heavy)', lag);
}
// ---------------------------------------------------------------------------------------------------------- stagger
{
  const g = setup([{ lo: '4,101,0,0,0,301,401,501,601' }, { x: 1000, lo: '4,101,0,0,0,301,401,501,601' }]);
  const a = g.mechs.get(0), v = g.mechs.get(1);
  L.IF_applyDamage(g, v, 0, 100, v.staggerMax - 1, null, 'test', a.pos);
  ok(v.staggered === 0, 'below the cap: no stagger');
  L.IF_applyDamage(g, v, 0, 100, 10, null, 'test', a.pos);
  ok(v.staggered > 1.9 && g.events.some((e) => e.t === 'stagger'), 'stagger at the cap for 2 s', v.staggered);
  const ap = v.ap; L.IF_applyDamage(g, v, 0, 100, 0, null, 'test', a.pos);
  ok(near(ap - v.ap, 150, 0.01), 'staggered mechs take x1.5', ap - v.ap);
  run(g, 2.1);
  ok(v.staggered === 0 && v.stagger === 0, 'stagger ends and the meter resets');
}
// ---------------------------------------------------------------------------------------------------------- AC feel (docs/AC_FEEL.md)
{
  const MV = C.PARTS.move, lo = '4,101,0,0,0,301,401,501,601';
  // skating on the ground is free (AC4 / AC6); regen runs at boost_regen_mult meanwhile
  let g = setup([{ lo }]); let m = g.mechs.get(0);
  run(g, 1); m.en = m.enMax * 0.5; m.enPause = 0;
  const e0 = m.en; m.input.my = 1; m.input.boost = true; run(g, 1);
  const want = m.enRegen * MV.ground_regen_mult * MV.boost_regen_mult;
  ok(m.boosting && m.onGround && near(m.en - e0, want, want * 0.05), 'ground boost costs no EN, regen x' + MV.boost_regen_mult, (m.en - e0).toFixed(0) + ' vs ' + want.toFixed(0));
  ok(m.speed > m.boostSpeed * 0.9, 'ground boost reaches boost speed', m.speed.toFixed(0));
  // quick boost jet: holds QB speed for qb_jet s in a straight line
  g = setup([{ lo }]); m = g.mechs.get(0); run(g, 1);
  const x0 = m.pos.x, y0 = m.pos.y;
  m.input.mx = 1; m.input.qb = true; run(g, DT); m.input.qb = false;
  run(g, MV.qb_jet - 2 * DT);
  ok(m.speed >= m.qbSpeed * 0.98, 'QB jet holds the dash speed for ' + MV.qb_jet + ' s', m.speed.toFixed(0));
  m.input.mx = 0; run(g, 0.6);
  const qd = Math.hypot(m.pos.x - x0, m.pos.y - y0);
  ok(qd > m.qbSpeed * MV.qb_jet + 150 && qd < 1100, 'QB distance about 2-3 body heights', qd.toFixed(0) + ' u, height ' + m.height);
  // two-step: one extra QB inside the reload, at least qb_chain_angle off the first line, x qb_chain_cost EN
  g = setup([{ lo }]); m = g.mechs.get(0); run(g, 1);
  const qbs = () => g.events.filter((e) => e.t === 'qb');
  m.input.mx = 1; m.input.qb = true; run(g, DT); m.input.qb = false; run(g, MV.qb_chain + DT);
  g.events.length = 0;
  const en1 = m.en; m.input.mx = 0; m.input.my = 1; m.input.qb = true; run(g, DT); m.input.qb = false;
  ok(qbs().length === 1 && qbs()[0].chain === true, 'two-step chain QB at a right angle inside the reload', qbs().length);
  ok(near(en1 - m.en, m.qbCost * MV.qb_chain_cost, 2), 'chain QB costs x' + MV.qb_chain_cost, (en1 - m.en).toFixed(0));
  run(g, MV.qb_chain + DT); g.events.length = 0;
  m.input.my = 0; m.input.mx = -1; m.input.qb = true; run(g, DT); m.input.qb = false;
  ok(qbs().length === 0, 'only one chain per reload');
  run(g, m.qbCdTime); g.events.length = 0; m.input.qb = true; run(g, DT); m.input.qb = false;
  ok(qbs().length === 1 && !qbs()[0].chain, 'a plain QB after the reload');
  // redline: the generator hands back stall_refill of the tank when the stall ends
  g = setup([{ lo }]); m = g.mechs.get(0); run(g, 1);
  m.en = 0; m.spendEn(1); run(g, m.stallTime + 2 * DT);
  ok(m.en >= m.enMax * MV.stall_refill && m.en < m.enMax * MV.stall_refill + m.enRegen * 0.1, 'post-stall EN supply ' + MV.stall_refill, m.en.toFixed(0));
  // stagger: per-weapon direct-hit multiplier, crit flag; QB breaks out in the last stagger_qb_out s
  g = setup([{ lo }, { x: 1000, lo }]);
  const a = g.mechs.get(0), v = g.mechs.get(1);
  L.IF_applyDamage(g, v, 0, 1, v.staggerMax + 10, null, 'test', a.pos); g.events.length = 0;
  let ap = v.ap; L.IF_applyDamage(g, v, 0, 100, 0, null, 'rifle', a.pos);
  const dha = C.PARTS.parts.find((p) => p.key === 'rifle').w.dha;
  ok(near(ap - v.ap, 100 * dha, 0.01) && g.events.some((e) => e.t === 'damage' && e.crit), 'direct hit: rifle x' + dha + ' on a staggered mech, crit flag', ap - v.ap);
  ap = v.ap; L.IF_applyDamage(g, v, 0, 100, 0, null, 'plasma', a.pos);
  ok(ap - v.ap < 100 * dha - 1, 'energy weapons crit lower than kinetic', ap - v.ap);
  v.input.mx = 1; v.input.qb = true; run(g, DT); v.input.qb = false;
  ok(v.staggered > 0.5, 'no QB early in a stagger', v.staggered);
  v.staggered = MV.stagger_qb_out - 0.05; run(g, DT); g.events.length = 0;
  v.input.qb = true; run(g, DT); v.input.qb = false;
  ok(v.staggered === 0 && g.events.some((e) => e.t === 'qb' && e.slot === 1), 'QB breaks the stagger in its last ' + MV.stagger_qb_out + ' s');
  // weight: above weight_ideal of the load boost speed drops and the QB reload grows
  const lg = setup([{ lo: '4,101,0,0,0,301,401,501,601' }, { x: 1000, lo: '4,105,106,210,0,303,401,501,601' }]);
  const li = lg.mechs.get(0), hv = lg.mechs.get(1);
  ok(li.weightF === 0 && hv.weightF > 0.5, 'heavy kit above the ideal weight', hv.weight + ' / ' + hv.load);
  ok(hv.boostSpeed < li.boostSpeed && hv.qbCdTime > li.qbCdTime, 'heavy kit: slower boost, longer QB reload', hv.boostSpeed.toFixed(0) + ' ' + hv.qbCdTime.toFixed(2));
}
{ // AC6 ideal range: full damage inside falloff.ideal x range, falling to falloff.min at the range
  const F = C.PARTS.falloff, rw = C.PARTS.parts.find((p) => p.key === 'rifle').w, near0 = rw.range * F.rifle.ideal * 0.5, far0 = rw.range * 0.97;
  const shot = (dist) => {
    const g = setup([{ lo: '4,101,0,0,0,301,401,501,601' }, { x: dist, lo: '9,0,0,0,0,301,401,501,601' }]);
    const a = g.mechs.get(0), v = g.mechs.get(1); v.staggerMax = 1e9; v.ap = v.apMax = 1e6;
    run(g, 1.5, () => aim(g, a, v)); g.events.length = 0;
    run(g, 1.5, () => { aim(g, a, v); a.input.fire[0] = true; });
    const ev = dmgEvents(g, 1); return ev.length ? Math.max(...ev.map((e) => e.amount)) : 0;
  };
  const dn = shot(near0), df = shot(far0);
  ok(near(dn, rw.damage, 1), 'rifle full damage inside its ideal range', dn);
  ok(df < rw.damage * (F.rifle.min + 0.12) && df >= rw.damage * F.rifle.min - 1, 'rifle damage falls to ' + F.rifle.min + ' near max range', df);
}
{ // the blade lunge homes on a locked target anywhere inside the melee lock range
  const g = setup([{ lo: '4,107,0,0,0,301,401,501,601' }, { x: 850, lo: '9,0,0,0,0,301,401,501,601' }]);
  const a = g.mechs.get(0), v = g.mechs.get(1); v.staggerMax = 1e9; v.ap = v.apMax = 1e6;
  run(g, 1.5, () => aim(g, a, v)); g.events.length = 0;
  a.input.fire[0] = true; run(g, DT); a.input.fire[0] = false;
  v.input.mx = 1; run(g, 0.4, () => aim(g, a, v));   // the target side-steps during the lunge
  ok(dmgEvents(g, 1).length === 1, 'blade lunge reaches and tracks a locked target at 850 u');
}
{ // hard AI: with a missile salvo closing in it dodges, then chains a second QB across the first (two-step)
  let chained = false;
  for (let tr = 0; tr < 8 && !chained; tr++) {
    const g = setup([{ lo: '8,0,0,202,0,301,401,501,601' }, { x: 4000, lo: '4,101,0,0,0,301,401,501,601' }], { seed: 11 + tr });
    const a = g.mechs.get(0), b = g.mechs.get(1);
    b.human = false; C.IF_Ai.attach(g, b, 'hard'); b.staggerMax = 1e9;
    run(g, 2.5, () => aim(g, a, b)); g.events.length = 0;
    run(g, 4, (k) => { aim(g, a, b); a.input.fire[2] = k < 2; if (g.events.some((e) => e.t === 'qb' && e.slot === 1 && e.chain)) chained = true; });
  }
  ok(chained, 'hard AI uses the two-step chain against a missile salvo');
}
// ---------------------------------------------------------------------------------------------------------- AI aim model (50_ai.js header)
// a bot (two rifles) shoots a huge-AP human target for `secs`; the target strafes (`strafe`), quick boosts every 1.2 s (`qb`) or stands;
// returns shots, hits, and the hits / shots inside the 0.6 s after each target QB
function aimRun(tier, dist, mode, seed, secs) {
  const g = setup([{ lo: '4,101,101,0,0,301,401,501,601' }, { x: dist, yaw: 180, lo: '4,0,0,0,0,301,401,501,601' }], { seed });
  const b = g.mechs.get(0), t = g.mechs.get(1);
  b.human = false; C.IF_Ai.attach(g, b, tier);
  t.ap = t.apMax = 1e9; t.staggerMax = 1e9;
  let shots = 0, hits = 0, qS = 0, qH = 0, lastQb = -99, dir = 1, firstShot = -1;
  const t0 = g.time;
  run(g, secs, (k) => {
    const I = t.input; I.yaw = 180; I.pitch = 0; I.any = true; I.qb = false; I.mx = 0; I.my = 0;
    if (mode !== 'still') { if (k % 96 === 0) dir = -dir; I.mx = dir; }
    if (mode === 'qb' && k % 77 === 40) { I.qb = true; lastQb = g.time; dir = -dir; I.mx = dir; }
    const dx = t.pos.x - b.pos.x; if (Math.abs(dx) < dist * 0.85) I.my = -1; else if (Math.abs(dx) > dist * 1.15) I.my = 1;
    if (Math.abs(t.pos.y) > 1500) I.mx = t.pos.y > 0 ? 1 : -1;
    for (const e of g.events) {
      if (e.t === 'fire' && e.slot === 0) { shots++; if (firstShot < 0) firstShot = g.time - t0; if (g.time - lastQb < 0.4) qS++; }
      if (e.t === 'damage' && e.attacker === 0 && e.victim === 1) { hits++; if (g.time - lastQb > 0.2 && g.time - lastQb < 0.62) qH++; }
    }
    g.events.length = 0;
  });
  return { shots, hits, acc: hits / Math.max(1, shots), qAcc: qH / Math.max(1, qS), firstShot };
}
{
  const sum = (tier, dist, mode) => { let S = 0, H = 0, qS = 0, qH = 0; for (const seed of [7, 14, 21]) { const r = aimRun(tier, dist, mode, seed, 20); S += r.shots; H += r.hits; qS += r.qAcc * 1000; qH++; } return { acc: H / Math.max(1, S), q: qS / 1000 / qH }; };
  const hardNear = sum('hard', 1500, 'strafe'), hardFar = sum('hard', 3500, 'strafe'), hardQb = sum('hard', 2000, 'qb'), hardStill = sum('hard', 2000, 'still');
  const normStill = sum('normal', 2000, 'still'), normNear = sum('normal', 1500, 'strafe');
  const pc = (x) => Math.round(100 * x) + ' %';
  ok(hardStill.acc > 0.8 && hardStill.acc < 0.99, 'hard AI hits a standing mech at 2000 u most of the time, not always', pc(hardStill.acc));
  ok(hardFar.acc < hardNear.acc * 0.85, 'AI aim: long range (3500 u) misses more than close (1500 u)', pc(hardFar.acc) + ' vs ' + pc(hardNear.acc));
  ok(hardQb.q < hardStill.acc * 0.6, 'AI aim: a quick boost makes a hard bot miss for a moment', 'QB window ' + pc(hardQb.q) + ' vs standing ' + pc(hardStill.acc));
  ok(normStill.acc < hardStill.acc - 0.1 && normNear.acc < hardNear.acc - 0.08, 'normal AI aims clearly worse than hard', pc(normStill.acc) + ' / ' + pc(normNear.acc) + ' vs ' + pc(hardStill.acc) + ' / ' + pc(hardNear.acc));
  // reaction: no shot before the tier's reaction time after the target is acquired
  const T = C.IF_DEFAULT_CFG.ai.tiers;
  for (const tier of ['normal', 'hard']) { const r = aimRun(tier, 1500, 'still', 3, 3); ok(r.firstShot >= T[tier].react, tier + ' AI reacts before its first shot (' + T[tier].react + ' s)', r.firstShot.toFixed(2)); }
}
// ---------------------------------------------------------------------------------------------------------- every weapon family
{
  const P = C.PARTS.parts.filter((p) => p.w && p.w.damage && p.kind !== 'frame');
  for (const p of P) {
    if (p.w.ability === 'mines') continue;      // proximity mines have their own test below
    const arm = p.kind === 'arm';
    const lo = arm ? `8,${p.id},0,0,0,303,403,504,601` : `8,0,0,${p.id},0,303,403,504,601`;
    const hp = arm ? 0 : 2, w = p.w;
    const dist = w.type === 'melee' ? 500 : w.loft ? 3500 : Math.min(1200, (w.range || 3000) * 0.4);
    const g = setup([{ lo }, { x: dist, lo: '9,0,0,0,0,301,401,501,601' }], { seed: 5 });
    const a = g.mechs.get(0), v = g.mechs.get(1);
    v.staggerMax = 1e9; v.ap = v.apMax = 1e6;
    a.en = a.enMax;
    // lock first (missiles need it; soft lock helps guns too)
    run(g, 2.0, () => aim(g, a, v));
    g.events.length = 0;
    const hold = w.charge && !w.cannon ? 2 : (w.windup || w.charge || w.brace ? 2.5 : 1.5);
    let k = 0;
    run(g, hold + 3 + (w.multilock ? 3 : 0), () => { aim(g, a, v); a.input.fire[hp] = k++ < (w.charge && !w.cannon ? 5 : hold * 64); });
    const ev = dmgEvents(g, 1).filter((e) => e.attacker === 0 && !(w.burn_dps && e.impact === 0));   // burn lumps are tested below
    const expect = Math.round(w.damage);
    const all = ev.length > 0 && ev.every((e) => Math.abs(e.amount - expect) <= 1);
    ok(all, `${p.key} (${w.type}${w.splash ? ', splash' : ''}) hits a stationary target for ${expect}`, ev.slice(0, 6).map((e) => e.amount).join(',') || 'no hits');
  }
  // laser full charge x2.4
  const g = setup([{ lo: '8,104,0,0,0,303,403,504,601' }, { x: 1500, lo: '9,0,0,0,0,301,401,501,601' }]);
  const a = g.mechs.get(0), v = g.mechs.get(1); v.staggerMax = 1e9;
  run(g, 1.5, () => aim(g, a, v)); g.events.length = 0;
  let k = 0; run(g, 2, () => { aim(g, a, v); a.input.fire[0] = k++ < 64 * 1.3; });
  const ev = dmgEvents(g, 1);
  const lw = C.PARTS.parts.find((p) => p.key === 'laser').w, full = lw.damage * lw.charge_mult;   // inside the ideal range: no fall-off
  ok(ev.length === 1 && Math.abs(ev[0].amount - full) <= 1, 'laser rifle full charge ' + full, ev.map((e) => e.amount).join(','));
}
// ---------------------------------------------------------------------------------------------------------- splash fall-off
{
  const g = setup([{ lo: '9,0,0,0,0,301,401,501,601' }, { x: 3000, lo: '9,0,0,0,0,301,401,501,601' }]);
  const a = g.mechs.get(0), v = g.mechs.get(1); v.staggerMax = 1e9;
  const R = 400, at = (d) => { const ap = v.ap; L.IF_explode(g, { x: v.pos.x - v.radius - d, y: v.pos.y, z: v.pos.z + 150 }, R, 1000, 0, 0, 'test', 'test'); const r = ap - v.ap; v.ap = v.apMax; return r; };
  ok(near(at(0), 1000, 1), 'splash full at the surface');
  ok(near(at(0.4 * R), 1000, 2), 'splash full to 40 % of the radius');
  ok(near(at(0.7 * R), 625, 3), 'splash 62.5 % at 70 %', at(0.7 * R));
  ok(near(at(0.999 * R), 250, 3), 'splash 25 % at the edge');
  ok(at(1.1 * R) === 0, 'no splash beyond the radius');
  const ap = a.ap; L.IF_explode(g, { x: a.pos.x, y: a.pos.y, z: a.pos.z + 150 }, R, 1000, 0, 0, 'test', 'test');
  ok(near(ap - a.ap, 500, 2), 'self splash 50 %', ap - a.ap);
}
// ---------------------------------------------------------------------------------------------------------- shield arc
{
  const g = setup([{ lo: '9,0,0,0,0,301,401,501,601' }, { x: 1000, yaw: 180, lo: '9,0,111,0,0,301,401,501,601' }]);
  const a = g.mechs.get(0), v = g.mechs.get(1); v.staggerMax = 1e9;
  v.input.fire[1] = true; v.input.yaw = 180; run(g, 0.1);
  ok(v.weapons[1].raised, 'shield raised while held');
  let ap = v.ap; L.IF_applyDamage(g, v, 0, 1000, 0, null, 'test', a.pos);
  ok(near(ap - v.ap, 400, 1), 'shield blocks 60 % from the front', ap - v.ap);
  ap = v.ap; L.IF_applyDamage(g, v, 0, 1000, 0, null, 'test', { x: 2000, y: 0, z: 100 });
  ok(near(ap - v.ap, 1000, 1), 'no block from behind', ap - v.ap);
  ap = v.ap; L.IF_applyDamage(g, v, 0, 1000, 0, null, 'test', { x: 1000 + 200, y: 1000, z: 100 });
  ok(near(ap - v.ap, 1000, 1), 'no block outside the 70 degree arc (101 deg off)', ap - v.ap);
}
// ---------------------------------------------------------------------------------------------------------- lock stages and decoy
{
  const g = setup([{ lo: '8,0,0,201,0,301,401,501,601' }, { x: 2500, lo: '8,0,0,0,209,301,401,501,601' }]);
  const a = g.mechs.get(0), v = g.mechs.get(1);
  const stages = [];
  run(g, 2, () => { aim(g, a, v); for (const e of g.events) if (e.t === 'lock' && e.slot === 0) stages.push([e.stage, +g.time.toFixed(3)]); g.events.length = 0; });
  ok(stages.length === 2 && stages[0][0] === 1 && stages[1][0] === 2, 'soft then hard lock', JSON.stringify(stages));
  if (stages.length === 2) ok(near(stages[1][1] - stages[0][1], a.lockHard, 0.1) && stages[0][1] <= a.lockSoft + 0.15, 'lock times soft ' + a.lockSoft + ' hard ' + a.lockHard, JSON.stringify(stages));
  a.input.fire[2] = true; run(g, 0.1, () => aim(g, a, v)); a.input.fire[2] = false;
  const inFlight = g.missiles.filter((m) => m.alive && m.target === 1).length;
  ok(inFlight >= 1, 'hard lock launches missiles', inFlight);
  v.input.fire[3] = true; run(g, DT); v.input.fire[3] = false;
  ok(a.lock.target === -1 && g.missiles.every((m) => !m.alive || m.target !== 1), 'decoy breaks the lock and every missile');
  run(g, 1, () => aim(g, a, v));
  ok(a.lock.target === -1, 'no relock during decoy immunity');
  run(g, 3, () => aim(g, a, v));
  ok(a.lock.target === 1, 'relock after immunity');
}
// ---------------------------------------------------------------------------------------------------------- homing: hit, and the late perpendicular quick boost
for (const dodge of [false, true]) {
  const g = setup([{ lo: '8,0,0,202,0,301,401,501,601' }, { x: 4000, lo: '4,0,0,0,0,301,401,501,601' }]);
  const a = g.mechs.get(0), v = g.mechs.get(1); v.staggerMax = 1e9; v.ap = v.apMax = 1e6;
  run(g, 2, () => aim(g, a, v));
  a.input.fire[2] = true; run(g, DT, () => aim(g, a, v)); a.input.fire[2] = false;
  g.events.length = 0;
  let dodged = false;
  run(g, 3, () => {
    if (!dodge || dodged) return;
    for (const ms of g.missiles) if (ms.alive && ms.target === 1) {
      const d = Math.hypot(ms.pos.x - v.pos.x, ms.pos.y - v.pos.y, ms.pos.z - v.pos.z - 150);
      if (d / ms.speed < 0.45) { v.input.mx = 1; v.input.qb = true; dodged = true; return; }
    }
  });
  v.input.qb = false;
  const hits = dmgEvents(g, 1).filter((e) => e.weapon === 'dualmsl').length;
  if (!dodge) ok(hits === 2, 'dual missiles hit a stationary target', hits);
  else ok(dodged && hits === 0, 'a perpendicular quick boost in the last 0.5 s dodges', 'dodged ' + dodged + ' hits ' + hits);
}
// ---------------------------------------------------------------------------------------------------------- spawn protection
{
  const g = setup([{ lo: '8,101,0,0,0,301,401,501,601' }, { x: 1000, lo: '9,101,0,0,0,301,401,501,601' }]);
  const a = g.mechs.get(0), v = g.mechs.get(1);
  v.protect = 3;
  let ap = v.ap; L.IF_applyDamage(g, v, 0, 500, 0, null, 'test', a.pos);
  ok(v.ap === ap, 'spawn protection blocks damage');
  aim(g, v, a); v.input.fire[0] = true; run(g, 0.1); v.input.fire[0] = false;
  ok(v.protect === 0, 'firing ends spawn protection');
  ap = v.ap; L.IF_applyDamage(g, v, 0, 500, 0, null, 'test', a.pos);
  ok(ap - v.ap === 500, 'damage after protection');
  // protection during the drop too
  const g2 = setup([{ lo: '8,101,0,0,0,301,401,501,601' }]);
  g2.mechs.get(0).dropT = 0.5; ap = g2.mechs.get(0).ap;
  L.IF_applyDamage(g2, g2.mechs.get(0), -1, 500, 0, null, 'test', null);
  ok(g2.mechs.get(0).ap === ap, 'no damage while dropping in');
}
// ---------------------------------------------------------------------------------------------------------- assists
{
  const g = setup([{ team: 2 }, { team: 2, x: 200 }, { team: 2, x: 400 }, { team: 3, x: 3000 }].map((s) => Object.assign({ lo: '8,101,0,0,0,301,401,501,601' }, s)));
  const v = g.mechs.get(3); v.staggerMax = 1e9;
  L.IF_applyDamage(g, v, 1, v.apMax * 0.2, 0, null, 'rifle', g.mechs.get(1).pos);
  L.IF_applyDamage(g, v, 2, v.apMax * 0.1, 0, null, 'rifle', g.mechs.get(2).pos);
  L.IF_applyDamage(g, v, 0, v.apMax, 0, null, 'rifle', g.mechs.get(0).pos);
  const k = g.events.find((e) => e.t === 'kill');
  ok(k && k.killer === 0 && k.assist.length === 1 && k.assist[0] === 1 && k.weapon === 'rifle', 'kill credit with one assist (>= 15 %, not 10 %)', JSON.stringify(k));
  ok(g.pilotSummary(0).kills === 1 && g.pilotSummary(1).assists === 1 && g.pilotSummary(2).assists === 0 && g.match.scores[2] === 1, 'summary and team score');
  const d = g.events.find((e) => e.t === 'death');
  ok(d && d.slot === 3 && d.killer === 0 && !v.alive && v.deathT === g.now, 'death event and deathT');
  // the 8 s window
  const g2 = setup([{ team: 2 }, { team: 2, x: 200 }, { team: 3, x: 3000 }].map((s) => Object.assign({ lo: '8,101,0,0,0,301,401,501,601' }, s)));
  const v2 = g2.mechs.get(2); v2.staggerMax = 1e9;
  L.IF_applyDamage(g2, v2, 1, v2.apMax * 0.3, 0, null, 'rifle', null);
  run(g2, 8.5);
  L.IF_applyDamage(g2, v2, 0, v2.apMax, 0, null, 'rifle', null);
  const k2 = g2.events.find((e) => e.t === 'kill');
  ok(k2 && k2.assist.length === 0, 'no assist after 8 s', JSON.stringify(k2 && k2.assist));
}
// ---------------------------------------------------------------------------------------------------------- conquest capture
{
  const g = setup([{ team: 2, lo: '4,101,0,0,0,301,401,501,601' }], { mode: 'cq' });
  const m = g.mechs.get(0), p = g.match.points[0];
  m.pos.x = p.pos.x; m.pos.y = p.pos.y;
  let at = -1; const t0 = g.time;
  run(g, 10, () => { m.pos.x = p.pos.x; m.pos.y = p.pos.y; if (at < 0 && p.owner === 2) at = g.time - t0; });
  ok(at > 7.8 && at < 8.4, 'Conquest: one mech captures a neutral point in 8 s', at.toFixed(2));
  ok(g.events.some((e) => e.t === 'capture' && e.point === 0 && e.team === 2 && e.slot === 0) && m.sum.captures === 1, 'capture event and credit');
  const tk = g.match.tickets[3]; run(g, 2);
  ok(near(tk - g.match.tickets[3], 2, 0.1), 'a held point bleeds 1 ticket/s', tk - g.match.tickets[3]);
}
// ---------------------------------------------------------------------------------------------------------- contract vectors
{
  const V = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'contract_vectors.json'), 'utf8'));
  let bad = 0;
  for (const c of V.validate) {
    const pil = V.pilots[c.pilot];
    const pilot = { rank: pil.rank, owned: new Set(pil.owned) };
    const r = C.IF_Progress.validateRef(c.loadout, pilot, C.PARTS);
    const r2 = C.IF_Progress.validate(c.loadout, { rank: pil.rank, owned: pil.owned }, C.PARTS);
    if (r.deny !== c.deny || r.ref !== c.ref || r2 !== c.deny) { bad++; console.log(`   validate "${c.name}": got ${r.deny}/${r.ref} want ${c.deny}/${c.ref}`); }
  }
  ok(bad === 0, `validate() matches ${V.validate.length} contract vectors`, bad + ' wrong');
  let xb = 0;
  for (const c of V.xp) if (C.IF_Progress.xpFor(c.rank, C.PARTS) !== c.xp) xb++;
  for (const c of V.rank_for) if (C.IF_Progress.rankFor(c.xp, C.PARTS) !== c.rank) xb++;
  ok(xb === 0, `xpFor / rankFor match ${V.xp.length + V.rank_for.length} vectors`, xb);
  const r = C.IF_Progress.roundXp({ kills: 3, bountyKills2: 1, assists: 2, captures: 1, survive: 100.6, won: true }, { parts: C.PARTS, rank: 3, medianRank: 10 });
  ok(r.xp === Math.round((100 + 40 * 4 + 30 + 60 + 300 + 100) * 1.5) && r.credits === Math.round(r.xp / 2), 'roundXp: bounty x2, catch-up x1.5, credits 50 %', JSON.stringify(r));
}
// ---------------------------------------------------------------------------------------------------------- balance helper, mode pick
{
  const b = L.IF_balanceTeams([1, 2, 3, 4, 5, 6, 7, 8].map((r, i) => ({ slot: i, rating: r * 100 })));
  ok(b[2].length === 4 && b[3].length === 4 && b.diff <= 0.05, 'rating balance within 5 %', b.diff.toFixed(3));
  const g = setup([{ lo: '4,101,0,0,0,301,401,501,601' }]);
  ok(g.pickMode(3) === 'so' && ['tb', 'cq'].includes(g.pickMode(10)) && g.pickMode(40) !== 'sk', 'mode by humans');
  g.vote(0, 'sk'); ok(g.pickMode(10) === 'sk' && g.pickMode(30) !== 'sk', 'skirmish by vote at 16 or fewer');
}
// ---------------------------------------------------------------------------------------------------------- arsenal expansion (113-118, 211-214)
{
  const key = (k) => C.PARTS.parts.find((p) => p.key === k);
  const mk = (arm, sh, dist, extra) => {
    const lo = `8,${arm || 0},0,${sh || 0},0,303,403,504,601`;
    const specs = [{ lo }, { x: dist, lo: '9,0,0,0,0,301,401,501,601' }].concat(extra || []);
    const g = setup(specs, { seed: 7 });
    const a = g.mechs.get(0), v = g.mechs.get(1);
    for (let i = 1; i < specs.length; i++) { const t = g.mechs.get(i); t.staggerMax = 1e9; t.ap = t.apMax = 1e6; }
    a.en = a.enMax;
    return { g, a, v };
  };
  const fires = (g) => g.events.filter((e) => e.t === 'fire');
  // every new part names an existing sound and its fire events carry the part key
  const snd = path.join(ROOT, 'out', 'addon', '_gen', 'sounds.json');
  if (fs.existsSync(snd)) {
    const ev = JSON.parse(fs.readFileSync(snd, 'utf8')).events;
    for (const p of C.PARTS.parts.filter((q) => (q.id >= 113 && q.id <= 118) || (q.id >= 211 && q.id <= 214))) ok(ev[p.w.sound] !== undefined, p.key + ' w.sound names an existing sound', p.w.sound);
  }

  // ---- pile bunker: short lunge, huge hit, instant stagger, long cooldown
  {
    const w = key('pilebunker').w;
    const { g, a, v } = mk(113, 0, 330);
    run(g, 1, () => aim(g, a, v)); g.events.length = 0;
    const en0 = a.en;
    a.input.fire[0] = true; run(g, DT * 2); a.input.fire[0] = false;
    run(g, 0.6, () => aim(g, a, v));
    const ev = dmgEvents(g, 1).filter((e) => e.attacker === 0);
    ok(ev.length === 1 && ev[0].amount === w.damage, 'pile bunker hits once for ' + w.damage, ev.map((e) => e.amount).join(','));
    ok(v.staggered > 0 || g.events.some((e) => e.t === 'stagger' && e.slot === 1), 'pile bunker staggers at once (stagger meter was 1e9)');
    ok(fires(g).length === 1 && fires(g)[0].weapon === 'pilebunker', 'pile bunker fire event carries the part key');
    ok(a.en < en0 - w.en_shot + 200, 'pile bunker costs EN', en0 - a.en);
    g.events.length = 0; a.input.fire[0] = true; run(g, DT * 2); a.input.fire[0] = false; run(g, 2, () => aim(g, a, v));
    ok(dmgEvents(g, 1).length === 0, 'pile bunker cooldown blocks a second thrust inside 2 s');
    // real stagger meter: one hit staggers a heavy frame outright
    const h = mk(113, 0, 330);
    h.v.staggerMax = 1900; h.v.stagger = 0; h.v.ap = h.v.apMax = 1e6;
    run(h.g, 1, () => aim(h.g, h.a, h.v)); h.a.input.fire[0] = true; run(h.g, DT * 2); h.a.input.fire[0] = false; run(h.g, 0.5, () => aim(h.g, h.a, h.v));
    ok(h.v.staggered > 0, 'pile bunker staggers a real mech (not just by impact)');
  }

  // ---- sniper cannon: charge, long range, no firing while boosting
  {
    const w = key('sniper').w;
    const { g, a, v } = mk(114, 0, 9000);
    run(g, 2, () => aim(g, a, v)); g.events.length = 0;
    let k = 0; run(g, 0.8, () => { aim(g, a, v); a.input.fire[0] = true; });
    ok(dmgEvents(g, 1).length === 0, 'sniper: no damage inside the 1 s charge');
    run(g, 0.5, () => { aim(g, a, v); a.input.fire[0] = false; });
    const ev = dmgEvents(g, 1).filter((e) => e.attacker === 0);
    ok(ev.length === 1 && ev[0].amount === w.damage, 'sniper hits at 9000 u for ' + w.damage, ev.map((e) => e.amount).join(','));
    ok(g.events.some((e) => e.t === 'beam') && fires(g).length === 1 && fires(g)[0].weapon === 'sniper', 'sniper emits one beam and a fire event with the part key');
    // boosting blocks the shot
    const b = mk(114, 0, 5000);
    run(b.g, 2, () => aim(b.g, b.a, b.v)); b.g.events.length = 0;
    const mag0 = b.a.weapons[0].mag;
    run(b.g, 2, () => { aim(b.g, b.a, b.v); b.a.input.fire[0] = true; b.a.input.boost = true; b.a.input.mx = 0; b.a.input.my = 1; });
    ok(b.a.boosting && dmgEvents(b.g, 1).length === 0 && fires(b.g).length === 0, 'sniper cannot fire while boosting', fires(b.g).length);
    b.a.input.fire[0] = false; b.a.input.boost = false; b.a.input.my = 0; run(b.g, 1);
    ok(b.a.weapons[0].mag === mag0 || b.a.weapons[0].reloading, 'sniper round is refunded when the charge is spoiled', b.a.weapons[0].mag + ' vs ' + mag0);
  }

  // ---- burst rifle: three rounds per pull
  {
    const w = key('burstrifle').w;
    const { g, a, v } = mk(115, 0, 1500);
    run(g, 2, () => aim(g, a, v)); g.events.length = 0;
    a.input.fire[0] = true; run(g, DT); a.input.fire[0] = false;
    run(g, 0.6, () => aim(g, a, v));
    const ev = dmgEvents(g, 1).filter((e) => e.attacker === 0);
    ok(fires(g).length === 3 && fires(g).every((e) => e.weapon === 'burstrifle'), 'burst rifle: one pull = 3 fire events', fires(g).length);
    ok(ev.length === 3 && ev.every((e) => e.amount === w.damage), 'burst rifle: 3 hits of ' + w.damage, ev.map((e) => e.amount).join(','));
    ok(a.weapons[0].mag === w.mag - 3, 'burst rifle uses 3 rounds of the magazine', a.weapons[0].mag);
    g.events.length = 0; a.input.fire[0] = true; run(g, 1.0, () => aim(g, a, v)); a.input.fire[0] = false;
    ok(fires(g).length >= 6 && fires(g).length <= 9 && fires(g).length % 3 === 0 || fires(g).length === 7, 'burst rifle held: about 2 bursts a second (rate 2.2) -> 6-7 rounds in 1 s', fires(g).length);
  }

  // ---- flamethrower: cone, burn timer, low impact
  {
    const w = key('flamer').w;
    const { g, a, v } = mk(116, 0, 500);
    run(g, 1, () => aim(g, a, v)); g.events.length = 0;
    a.input.fire[0] = true; run(g, 1.0, () => aim(g, a, v)); a.input.fire[0] = false;
    ok(v.burnT > 0 && v.burnBy === 0, 'flamethrower sets the target burning', v.burnT);
    ok(g.events.some((e) => e.t === 'burn' && e.slot === 1 && e.on), 'burn start event');
    const dmg = dmgEvents(g, 1).filter((e) => e.attacker === 0);
    const burns = dmg.filter((e) => e.impact === 0 && e.weapon === 'flamer');
    ok(burns.length >= 2 && dmg.filter((e) => e.impact > 0).every((e) => e.amount === w.damage && e.impact === w.impact), 'flamethrower: direct hits for ' + w.damage + ' with impact ' + w.impact + ' plus burn lumps', burns.length);
    ok(w.impact <= 10 && !g.events.some((e) => e.t === 'stagger'), 'flamethrower impact is low (no stagger)');
    g.events.length = 0; const ap = v.ap; run(g, 1.0);
    ok(ap - v.ap > w.burn_dps * 0.5 && ap - v.ap < w.burn_dps * 1.2, 'burn keeps ticking after the flame stops (~' + w.burn_dps + ' AP/s)', ap - v.ap);
    run(g, 3);
    ok(v.burnT === 0 && g.events.some((e) => e.t === 'burn' && !e.on), 'burn ends after its timer');
    // outside the cone / beyond the range: nothing
    const o = mk(116, 0, 500);
    o.v.pos.y = 300; run(o.g, 0.2); o.g.events.length = 0;
    o.a.input.yaw = 0; o.a.input.pitch = 0; o.a.input.fire[0] = true; run(o.g, 0.5); o.a.input.fire[0] = false;
    ok(dmgEvents(o.g, 1).length === 0 && o.v.burnT === 0, 'flamethrower misses a target outside its cone');
    const far = mk(116, 0, w.range + 400);
    run(far.g, 0.3, () => aim(far.g, far.a, far.v)); far.a.input.fire[0] = true; run(far.g, 0.5, () => aim(far.g, far.a, far.v));
    ok(dmgEvents(far.g, 1).length === 0, 'flamethrower is short range (' + w.range + ' u)');
    // death clears the burn
    v.ap = 1; v.burnT = 2; run(g, 0.5);
    ok(!v.alive && v.burnT === 0, 'a burn kills and is cleared on death');
  }

  // ---- orbit drones
  {
    const w = key('orbitdrones').w;
    const { g, a, v } = mk(101, 212, 1500);
    a.weapons[2].cd = 0;
    run(g, 2, () => aim(g, a, v)); g.events.length = 0;
    const lines0 = g._testWorld ? g._testWorld.lines : 0;
    a.input.fire[2] = true; run(g, DT * 2); a.input.fire[2] = false;
    const dr = () => g.effects.filter((e) => e.alive && e.kind === 'drone');
    ok(dr().length === 2 && dr().every((e) => e.slot === 0), 'orbit drones: two drone effects owned by the user', dr().length);
    ok(g.events.some((e) => e.t === 'ability' && e.weapon === 'orbitdrones'), 'ability event carries the part key');
    const d0 = dr().map((e) => ({ x: e.pos.x, y: e.pos.y }));
    run(g, 0.4, () => aim(g, a, v));
    const orbit = dr().every((e) => Math.abs(Math.hypot(e.pos.x - a.pos.x, e.pos.y - a.pos.y) - w.orbit) < 5) && dr().some((e, i) => Math.hypot(e.pos.x - d0[i].x, e.pos.y - d0[i].y) > 20);
    ok(orbit, 'drones circle the user at the orbit radius');
    g.events.length = 0; a.weapons[2].cd = 99;
    run(g, 4, () => aim(g, a, v));
    const hits = dmgEvents(g, 1).filter((e) => e.weapon === 'orbitdrones');
    ok(hits.length >= 6 && hits.length <= 2 * w.rate * 4 + 2 && hits.every((e) => e.amount === w.damage), 'drones shoot the soft-locked target at a low rate (' + w.rate + '/s each)', hits.length);
    const lines = g._testWorld ? g._testWorld.lines - lines0 : 0;
    ok(lines <= hits.length * 2 + 10, 'one LOS check per drone shot (flat arena: no world traces)', lines);
    a.weapons[2].cd = 0; run(g, 6.5);
    ok(dr().length === 0 && a.droneN === 0, 'drones expire after ' + w.duration + ' s');
    // killing the user removes them
    a.weapons[2].cd = 0; a.input.fire[2] = true; run(g, DT * 2); a.input.fire[2] = false;
    ok(dr().length === 2, 'drones deploy again after expiry');
    L.IF_applyDamage(g, a, 1, 1e9, 0, null, 'test', null); run(g, DT * 2);
    ok(dr().length === 0, 'drones vanish when the owner dies');
  }

  // ---- multi-lock missiles
  {
    const w = key('multimsl').w;
    const targets = [{ x: 3000, y: -200, lo: '9,0,0,0,0,301,401,501,601' }, { x: 3000, y: 200, lo: '9,0,0,0,0,301,401,501,601' }, { x: 3200, y: 0, lo: '9,0,0,0,0,301,401,501,601' }];
    for (const t of targets) t.team = 3;
    const { g, a, v } = mk(101, 213, 3000, targets);
    for (let i = 1; i < 4; i++) g.mechs.get(i).team = 3;
    g.mechs.get(1).pos.y = 0; g.mechs.get(1).pos.x = 3000;
    run(g, 0.2); g.events.length = 0;
    const wp = a.weapons[2];
    let max = 0;
    a.input.fire[2] = true;
    run(g, 0.5, () => aim(g, a, v)); max = wp.mlock.length;
    ok(wp.mlock.length >= 3 && wp.mlDone === 0, 'multi-lock: targets in the cone start locking, none done after 0.5 s', wp.mlock.length + '/' + wp.mlDone);
    run(g, 0.6, () => aim(g, a, v));
    ok(wp.mlDone >= 3, 'each target finishes after the hard-lock time (' + a.lockHard.toFixed(2) + ' s)', wp.mlDone);
    const ammo0 = wp.ammo;
    a.input.fire[2] = false; run(g, 1.2, () => aim(g, a, v));
    const live = g.missiles.filter((m) => m.alive), tg = new Set(g.missiles.map((m) => m.target).concat(live.map((m) => m.target)));
    const fired = ammo0 - wp.ammo;
    ok(fired === w.count, 'release fires the whole salvo (' + w.count + ')', fired);
    const hitSlots = new Set(g.events.filter((e) => e.t === 'threat' && e.kind === 'launch').map((e) => e.slot));
    ok(hitSlots.size >= 3, 'the salvo is split across the locked targets (launch warnings on ' + hitSlots.size + ')', [...hitSlots].join(','));
    // up to 4 locks, no more
    const five = mk(101, 213, 3000, [1, 2, 3, 4].map((i) => ({ x: 3000 + i * 40, y: i * 60 - 120, team: 3, lo: '9,0,0,0,0,301,401,501,601' })));
    for (let i = 1; i < 6; i++) five.g.mechs.get(i).team = 3;
    five.a.input.fire[2] = true; run(five.g, 1.5, () => aim(five.g, five.a, five.v));
    ok(five.a.weapons[2].mlock.length <= w.multilock, 'at most ' + w.multilock + ' locks', five.a.weapons[2].mlock.length);
    // a target leaving the cone is dropped
    const out = mk(101, 213, 3000);
    out.a.input.fire[2] = true; run(out.g, 0.4, () => aim(out.g, out.a, out.v));
    out.v.pos.y = 2500; run(out.g, 1.0);
    ok(out.a.weapons[2].mlock.length === 0 && out.a.weapons[2].mlDone === 0, 'a target outside the cone loses its lock');
    out.a.input.fire[2] = false; run(out.g, 0.2);
    { const L = out.g.missiles.filter((m) => m.alive); ok(L.length >= 1 && L.every((m) => m.target === -1 && !m.lofting), 'releasing with nothing locked fires the salvo unguided (10 Nov 2026: a pilot button always does something)', L.length); }
  }

  // ---- mine layer
  {
    const w = key('minelayer').w;
    const { g, a, v } = mk(101, 211, 2500);
    const wp = a.weapons[2], mines = () => g.effects.filter((e) => e.alive && e.kind === 'mine');
    g.events.length = 0;
    for (let i = 0; i < 6; i++) { a.pos.x = -i * 500; wp.cd = 0; a.input.fire[2] = true; run(g, DT * 2); a.input.fire[2] = false; run(g, DT * 2); }
    ok(mines().length === w.max && a.mineN === w.max, 'mine layer: at most ' + w.max + ' live mines', mines().length);
    ok(mines().every((e) => e.slot === 0 && e.radius === w.trigger), 'mines are effects of kind mine with the trigger radius');
    // an ally never sets them off; an enemy walking in does
    g.events.length = 0;
    const m0 = mines()[0];
    v.pos.x = m0.pos.x + 900; run(g, 1.5);
    ok(dmgEvents(g, 1).length === 0 && mines().length === w.max, 'mines wait while no enemy is near');
    a.pos.x = m0.pos.x + 20; run(g, 1.5);
    ok(mines().length === w.max, 'the owner does not trigger its own mines');
    v.pos.x = m0.pos.x + 150; v.pos.y = m0.pos.y; run(g, 0.5);
    const ev = dmgEvents(g, 1).filter((e) => e.weapon === 'minelayer');
    ok(ev.length === 1 && ev[0].amount > w.damage * 0.4 && ev[0].amount <= w.damage, 'an enemy inside ' + w.trigger + ' u takes the blast', ev.map((e) => e.amount).join(','));
    ok(mines().length === w.max - 1 && g.events.some((e) => e.t === 'explode' && e.kind === 'mine'), 'the mine explodes (explode event kind mine) and is removed');
    // life
    v.pos.x = 99999; v.pos.y = 99999; run(g, w.life + 1);
    ok(mines().length === 0 && a.mineN === 0, 'mines expire after ' + w.life + ' s');
  }

  // ---- cluster artillery
  {
    const w = key('clusterart').w;
    const { g, a, v } = mk(101, 214, 2600);
    run(g, 1.5, () => aim(g, a, v)); g.events.length = 0;
    a.input.fire[2] = true; run(g, DT * 2, () => aim(g, a, v)); a.input.fire[2] = false;
    let maxLob = 0, split = false;
    run(g, 6, () => { aim(g, a, v); const n = g.projectiles.filter((p) => p.alive && p.kind === 'lob').length; if (n > maxLob) maxLob = n; });
    split = g.events.some((e) => e.t === 'explode' && e.kind === 'cluster_split');
    ok(split && maxLob === w.pellets, 'cluster shell splits into ' + w.pellets + ' bomblets at the apex', maxLob + ' ' + split);
    const boom = g.events.filter((e) => e.t === 'explode' && e.kind === 'clusterart');
    ok(boom.length === w.pellets, 'each bomblet explodes once (explode events)', boom.length);
    ok(fires(g).length === 1 && fires(g)[0].weapon === 'clusterart', 'one fire event with the part key', fires(g).length);
    const hits = dmgEvents(g, 1).filter((e) => e.attacker === 0);
    ok(hits.length >= 1 && hits.every((e) => e.amount <= w.damage), 'bomblets damage the target within the bomblet damage', hits.map((e) => e.amount).join(','));
    ok(g.bullets.count === 0, 'no bullets left behind');
  }

  // ---- energy shotgun: EN fed
  {
    const w = key('eshotgun').w;
    const { g, a, v } = mk(117, 0, 700);
    ok(a.weapons[0].ammoLeft === -1, 'energy shotgun has no ammo');
    run(g, 1, () => aim(g, a, v)); g.events.length = 0; a.en = a.enMax;
    const en0 = a.en;
    a.input.fire[0] = true; run(g, DT * 2, () => aim(g, a, v)); a.input.fire[0] = false;
    ok(near(en0 - a.en, w.en_shot, 40), 'energy shotgun costs ' + w.en_shot + ' EN a shot', en0 - a.en);
    a.en = w.en_shot - 20; g.events.length = 0; a.weapons[0].cd = 0;
    a.input.fire[0] = true; run(g, 0.5, () => aim(g, a, v)); a.input.fire[0] = false;
    ok(fires(g).length === 0, 'energy shotgun will not fire without the EN');
  }

  // ---- heavy laser blade: slower and wider than the Moonlight
  {
    const w = key('heavyblade').w, bw = key('blade').w;
    ok(w.lunge_time > 0.25 && w.hit_radius > bw.hit_radius && w.rate < bw.rate, 'heavy blade is slower with a wider arc than PB-Moonlight');
    const far = mk(118, 0, 1400);
    run(far.g, 1, () => aim(far.g, far.a, far.v)); const x0 = far.a.pos.x;
    far.a.input.fire[0] = true; run(far.g, DT); far.a.input.fire[0] = false;
    ok(far.a.lungeT > w.lunge_time - 0.05, 'heavy blade lunge lasts ' + w.lunge_time + ' s', far.a.lungeT);
    run(far.g, 0.6, () => aim(far.g, far.a, far.v));
    ok(near(far.a.lungeSpeed, w.lunge / w.lunge_time, 60), 'heavy blade lunge speed = lunge / lunge_time', far.a.lungeSpeed);
    const { g, a, v } = mk(118, 0, 600);
    run(g, 1, () => aim(g, a, v)); g.events.length = 0;
    a.input.fire[0] = true; run(g, DT * 2); a.input.fire[0] = false;
    run(g, 0.8, () => aim(g, a, v));
    const ev = dmgEvents(g, 1).filter((e) => e.attacker === 0);
    ok(ev.length === 1 && ev[0].amount === w.damage, 'heavy blade hits once for ' + w.damage, ev.map((e) => e.amount).join(','));
    ok(fires(g)[0] && fires(g)[0].weapon === 'heavyblade', 'fire event carries the part key');
  }
}

console.log(`mechanics: ${passes} passed, ${fails} failed`);
process.exit(fails ? 1 : 0);
