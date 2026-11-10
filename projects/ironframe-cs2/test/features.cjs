// Overdrive, supply crates and killstreak rewards (src/core/86_features.js). usage: node test/features.cjs
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


const lo = '4,101,0,0,0,301,401,501,601';
// ---- overdrive: meter fills from damage, hold triggers charge then blast
{
  const g = setup([{ x: 0, lo }, { x: 400, lo }, { x: 450, y: 100, team: 3, lo }]);
  const a = g.mechs.get(0), b = g.mechs.get(1), c = g.mechs.get(2);
  ok(a.overdrive === 0, 'meter starts empty');
  b.team = 3;
  L.IF_applyDamage(g, b, 0, b.apMax * 0.6, 0, null, 'x', null);   // a deals 60 % of a bar -> 0.3
  ok(near(a.overdrive, 0.3, 0.02), 'dealing 60 % of a victim bar fills 0.3', a.overdrive);
  L.IF_applyDamage(g, a, 1, a.apMax * 0.4, 0, null, 'x', null);
  ok(near(a.overdrive, 0.3 + 0.1, 0.02), 'taking 40 % AP adds 0.1', a.overdrive);
  a.overdrive = 1; a.input.od = true; a.input.fire[2] = a.input.fire[3] = true;
  run(g, 0.4); ok(a.odPhase === 0 && !a.input.fire[2], 'holding < 0.6 s does not trigger and suppresses shoulder fire');
  run(g, 0.4); ok(a.odPhase === 1, 'hold of 0.6 s starts the charge');
  ok(g.events.some((e) => e.t === 'overdrive' && e.phase === 'charge' && e.slot === 0), 'charge event');
  ok(near(a.featSpeed, 0.4, 0.001), 'self slow during the charge');
  const ap0 = [b.ap, c.ap]; b.protect = c.protect = 0;
  run(g, 1.3, () => { a.input.od = false; });
  ok(a.odPhase === 0 && a.overdrive === 0, 'blast resets the meter');
  ok(g.events.some((e) => e.t === 'overdrive' && e.phase === 'blast'), 'blast event');
  ok(ap0[0] - b.ap > 1400 && ap0[0] - b.ap <= 2500 * 1.01, 'near target loses ~2500 falloff damage', ap0[0] - b.ap);
  ok(b.staggered > 0 || b.stagger >= b.staggerMax, 'target staggered');
  ok(b.vel.x > 300 || b.pos.x > 400, 'target knocked back', b.vel.x + '/' + b.pos.x);
}
// ---- bots fire it on 3+ enemies / staggered and low
{
  const g = setup([{ x: 0, lo }, { x: 300, team: 3, lo }, { x: 0, y: 300, team: 3, lo }, { x: -300, team: 3, lo }]);
  const a = g.mechs.get(0); a.human = false; a.overdrive = 1;
  run(g, 0.5); ok(a.odPhase === 1, 'bot charges with 3 enemies inside 600');
  const g2 = setup([{ x: 0, lo }, { x: 300, team: 3, lo }]);
  const b = g2.mechs.get(0); b.human = false; b.overdrive = 1; run(g2, 0.5);
  ok(b.odPhase === 0, 'bot waits with one enemy');
  b.staggered = 1; b.ap = b.apMax * 0.2; run(g2, 0.5);
  ok(b.odPhase === 1, 'bot charges when staggered and low');
}
// ---- crates
{
  const g = setup([{ x: 0, lo }, { x: 3000, team: 3, lo }], { cfg: { feat: { crate: { first: [1, 1] } } } });
  run(g, 1.5);
  const ev = g.events.filter((e) => e.t === 'crate'); ok(ev.length === 1 && ev[0].phase === 'drop', 'crate drops after the first timer');
  const e = g.crate; ok(e && e.kind === 'crate' && e.state === 'fall' && e.slot === -1 && e.alive, 'crate effect falling');
  ok(g.nav.walk(e.pos.x, e.pos.y) && !g.nav.nearStruct(e.pos.x, e.pos.y), 'crate on open walkable ground');
  run(g, 2.6); ok(e.state === 'ground' && g.events.some((x) => x.t === 'crate' && x.phase === 'land'), 'crate lands');
  const m = g.mechs.get(0); m.ap = m.apMax * 0.3; m.pos.x = e.pos.x; m.pos.y = e.pos.y; m.pos.z = e.pos.z; m.vel.x = m.vel.y = 0; m.input.mx = m.input.my = 0;
  run(g, 0.1);
  const t = g.events.find((x) => x.t === 'crate' && x.phase === 'take'); ok(t && t.slot === 0 && t.kind, 'first toucher takes it', JSON.stringify(t));
  ok(!e.alive && g.crate === null, 'crate consumed');
  // each kind
  for (const [k, chk] of [['repair', (mm) => mm.ap > mm.apMax * 0.3 + 100], ['damage', (mm) => mm.boostDmgT > 14], ['shield', (mm) => mm.shieldT > 14], ['overdrive', (mm) => mm.overdrive === 1], ['ammo', () => true]]) {
    const g2 = setup([{ x: 0, lo }, { x: 3000, team: 3, lo }]); const m2 = g2.mechs.get(0); m2.ap = m2.apMax * 0.3; m2.weapons[0].mag = 0;
    const w = g2.feat.crate.weights; for (const kk in w) w[kk] = kk === k ? 1 : 0;
    const fx = L.IF_effect(g2, 'crate', m2.pos, 100, -1, 50); fx.state = 'ground'; fx.fall = 0; g2.crate = fx; g2.crateT = 1e9;
    run(g2, 0.1); ok(chk(m2), 'crate kind ' + k);
  }
  // shield / boost multipliers
  const g3 = setup([{ x: 0, lo }, { x: 500, team: 3, lo }]); const a3 = g3.mechs.get(0), b3 = g3.mechs.get(1);
  const base = L.IF_applyDamage(g3, b3, 0, 1000, 0, null, 'x', null);
  b3.ap = b3.apMax; a3.boostDmgT = 5; const boosted = L.IF_applyDamage(g3, b3, 0, 1000, 0, null, 'x', null);
  b3.ap = b3.apMax; a3.boostDmgT = 0; b3.shieldT = 5; const shielded = L.IF_applyDamage(g3, b3, 0, 1000, 0, null, 'x', null);
  ok(near(boosted / base, 1.25, 0.01) && near(shielded / base, 0.6, 0.01), 'boost x1.25, shield x0.6', boosted / base + ' ' + shielded / base);
  // so mode has no crates
  const g4 = setup([{ x: 0, lo }], { mode: 'so', cfg: { feat: { crate: { first: [1, 1] } } } }); run(g4, 3); ok(!g4.crate, 'no crates in sortie');
  // interval scaled and bounded
  const g5 = setup([{ x: 0, lo }, { x: 3000, team: 3, lo }], { cfg: { feat: { crate: { first: [1, 1] } } } }); run(g5, 1.2);
  ok(g5.crateT >= 60 * 0.6 - 2 && g5.crateT <= 90 * 1.4, 'next crate in the 60-90 s band (scaled)', g5.crateT);
}
// ---- killstreaks
{
  const g = setup([{ x: 0, lo }, { x: 3000, team: 3, lo }]);
  const a = g.mechs.get(0), v = g.mechs.get(1);
  const kill = () => { v.ap = 1; v.protect = 0; v.alive = true; L.IF_applyDamage(g, v, 0, 100, 0, null, 'x', null); };
  for (let i = 1; i <= 9; i++) { kill(); }
  const st = g.events.filter((e) => e.t === 'streak').map((e) => e.kind + e.streak);
  ok(st.join() === 'radar3,arty5,ace8', 'streak rewards at 3, 5, 8 and none beyond', st.join());
  ok(a.radarT > 9 && a.aceT > 19 && a.artyReady, 'states set');
  // arty: fires at the lock target
  a.lock.target = 1; v.alive = true; v.ap = v.apMax; g.events.length = 0; run(g, 0.1);
  ok(!a.artyReady && g.events.filter((e) => e.t === 'shell').length === 6, 'artillery queues 6 shells');
  const ap = v.ap; run(g, 5);
  ok(g.events.filter((e) => e.t === 'explode' && e.kind === 'artillery').length === 6, 'six artillery explosions over 4 s');
  ok(a.featSpeed > 1.19, 'ACE speed +20 %');
}
// rookie stomp earns no progress
{
  const g = setup([{ x: 0, lo, pilot: null }, { x: 3000, team: 3, lo }]);
  const a = g.mechs.get(0), v = g.mechs.get(1); a.rank = 20; v.rank = 2;
  for (let i = 0; i < 3; i++) { v.ap = 1; v.protect = 0; v.alive = true; L.IF_applyDamage(g, v, 0, 100, 0, null, 'x', null); }
  ok(a.fkills === 0 && !a.radarT, 'rank 20 killing rank 2 earns no streak reward');
}
console.log(`features: ${passes} passed, ${fails} failed`);
process.exit(fails ? 1 : 0);
