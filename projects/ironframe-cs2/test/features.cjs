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
const loH = '8,101,0,0,0,301,401,501,601';      // the heavy starter frame
// ---- overdrive: meter fills from damage, hold triggers charge then blast
{
  const g = setup([{ x: 0, lo: loH }, { x: 400, lo }, { x: 450, y: 100, team: 3, lo }]);      // a heavy frame: the blast (light / medium refit, below)
  const a = g.mechs.get(0), b = g.mechs.get(1), c = g.mechs.get(2);
  ok(a.cls.key === 'heavy' && g.odKind(a) === 'blast' && g.odKind(b) === 'refit', 'a heavy frame blasts, a medium frame refits');
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
  run(g, 1.3, () => { a.input.od = false; if (a.odPhase === 1) { a.en = 0; a.enStalled = 0; } });
  ok(a.odPhase === 0 && a.overdrive === 0, 'blast resets the meter');
  ok(g.events.some((e) => e.t === 'overdrive' && e.phase === 'blast' && e.kind === 'blast' && e.radius === 1200), 'blast event (heavy: 1200 u)');
  ok(ap0[0] - b.ap > 1800 && ap0[0] - b.ap <= 3200 * 1.01, 'near target loses ~3200 falloff damage (heavy)', ap0[0] - b.ap);
  ok(a.en >= a.enMax * 0.39, 'the heavy blast gives 40 % EN back', a.en / a.enMax);
  ok(b.staggered > 0 || b.stagger >= b.staggerMax, 'target staggered');
  ok(b.vel.x > 300 || b.pos.x > 400, 'target knocked back', b.vel.x + '/' + b.pos.x);
}
// ---- light / medium frames: the overdrive is a field refit (11 Nov 2026): AP, EN and ammo, no blast
{
  const g = setup([{ x: 0, lo: '4,101,0,208,0,301,401,501,601' }, { x: 400, team: 3, lo }]);
  const a = g.mechs.get(0), b = g.mechs.get(1), w = a.weapons[0], mend = a.weapons[2];
  a.ap = Math.round(a.apMax * 0.3); w.mag = 0; w.ammo = 0; mend.charges = 0; mend.chargeCd = 99; b.protect = 0;
  const bap = b.ap;
  a.overdrive = 1; a.input.od = true;
  run(g, 0.7); ok(a.odPhase === 1 && g.events.some((e) => e.t === 'overdrive' && e.phase === 'charge' && e.kind === 'refit'), 'medium frame: the charge says refit');
  run(g, 1.3, () => { a.input.od = false; if (a.odPhase === 1) { a.en = 0; a.ap = Math.round(a.apMax * 0.3); } });
  const ev = g.events.find((e) => e.t === 'overdrive' && e.phase === 'refit');
  ok(!!ev && ev.heal === Math.round(a.apMax * 0.45) && a.overdrive === 0 && a.odPhase === 0, 'refit event with the AP given, meter spent', JSON.stringify(ev));
  ok(near(a.ap, a.apMax * 0.75, 2), 'refit: +45 % AP (30 % -> 75 %)', a.ap / a.apMax);
  ok(a.en >= a.enMax * 0.95, 'refit: EN full', a.en / a.enMax);
  ok(w.mag === w.magSize && w.ammo === w.w.ammo - w.magSize && !w.reloading, 'refit: the empty rifle is full again', w.mag + '+' + w.ammo);
  ok(mend.charges === mend.w.charges, 'refit: ability charges are back', mend.charges);
  ok(b.ap === bap && !g.events.some((e) => e.t === 'explode' && e.kind === 'overdrive'), 'refit: no blast, the enemy next to it is unhurt');
  a.ap = a.apMax - 100; a.overdrive = 1; a.input.od = true; g.events.length = 0; run(g, 2.2, (k) => { if (k > 50) a.input.od = false; });
  const ev2 = g.events.find((e) => e.t === 'overdrive' && e.phase === 'refit'); ok(!!ev2 && ev2.heal <= 100 && a.ap === a.apMax, 'refit never goes over the AP bar', JSON.stringify(ev2));
}
// ---- supply: a kill gives ammo and armour back; a rested weapon rebuilds ammo
{
  const g = setup([{ x: 0, lo }, { x: 3000, team: 3, lo }]);
  const a = g.mechs.get(0), v = g.mechs.get(1), w = a.weapons[0];
  a.ap = Math.round(a.apMax * 0.5); w.ammo = 0; const mag0 = w.mag;
  v.ap = 1; v.protect = 0; L.IF_applyDamage(g, v, 0, 100, 0, null, 'x', null);
  const sv = g.events.find((e) => e.t === 'salvage');
  ok(!!sv && sv.slot === 0 && sv.heal === Math.round(a.apMax * 0.08), 'kill: salvage event with the AP given', JSON.stringify(sv));
  ok(w.ammo === Math.round(w.w.ammo * 0.25) && w.mag === mag0, 'kill: +25 % of a weapon\'s ammo into the reserve', w.ammo);
  ok(near(a.ap, a.apMax * 0.58, 2), 'kill: +8 % AP', a.ap / a.apMax);
  w.ammo = w.w.ammo - w.magSize; a.ap = a.apMax; g.events.length = 0;
  v.alive = true; v.ap = 1; L.IF_applyDamage(g, v, 0, 100, 0, null, 'x', null);
  ok(!g.events.some((e) => e.t === 'salvage') && w.ammo === w.w.ammo - w.magSize, 'kill at full ammo and AP: nothing to salvage, never over the cap');
  // rested weapon: nothing for 6 s, then empty to full in 120 s; firing stops it
  const g2 = setup([{ x: 0, lo }, { x: 3000, team: 3, lo }]);
  const a2 = g2.mechs.get(0), w2 = a2.weapons[0];
  w2.mag = 0; w2.ammo = 0; run(g2, 5.5);
  ok(w2.mag + w2.ammo === 0, 'a dry weapon stays dry for the first 6 s');
  run(g2, 12.5);
  const tot = w2.mag + w2.ammo; ok(tot >= 28 && tot <= 32, 'then it rebuilds: 12 s at 300 / 120 s = 30 rounds', tot);
  ok(w2.mag > 0 && !w2.reloading, 'and the first rounds are loaded by themselves (it can fire again)', w2.mag);
  a2.input.yaw = 90; a2.input.fire[0] = true; run(g2, 3); a2.input.fire[0] = false;
  const left = w2.mag + w2.ammo; ok(left < tot, 'firing spends it and stops the rebuild', left);
  run(g2, 5); ok(w2.mag + w2.ammo === left, 'no rebuild in the 6 s after the last shot', (w2.mag + w2.ammo) + ' vs ' + left);
  w2.mag = w2.magSize; w2.ammo = w2.w.ammo - w2.magSize; run(g2, 10); ok(w2.ammo === w2.w.ammo - w2.magSize, 'a full weapon stays at its cap');
  const g3 = setup([{ x: 0, lo }, { x: 3000, team: 3, lo }], { cfg: { feat: { supply: { fabTime: 0, killAmmo: 0, killAp: 0 } } } });
  const w3 = g3.mechs.get(0).weapons[0]; w3.mag = 0; w3.ammo = 0; run(g3, 20); ok(w3.mag + w3.ammo === 0, 'cfg.feat.supply can switch it off');
}
// ---- bots: a heavy blasts on 3+ enemies / staggered and low; a light or medium refits when hurt or dry
{
  const g = setup([{ x: 0, lo: loH }, { x: 300, team: 3, lo }, { x: 0, y: 300, team: 3, lo }, { x: -300, team: 3, lo }]);
  const a = g.mechs.get(0); a.human = false; a.overdrive = 1;
  run(g, 0.5); ok(a.odPhase === 1, 'heavy bot charges with 3 enemies inside the blast');
  const g2 = setup([{ x: 0, lo: loH }, { x: 300, team: 3, lo }]);
  const b = g2.mechs.get(0); b.human = false; b.overdrive = 1; run(g2, 0.5);
  ok(b.odPhase === 0, 'heavy bot waits with one enemy');
  b.staggered = 1; b.ap = b.apMax * 0.2; run(g2, 0.5);
  ok(b.odPhase === 1, 'heavy bot charges when staggered and low');
  const g3 = setup([{ x: 0, lo }, { x: 3000, team: 3, lo }]);
  const m = g3.mechs.get(0); m.human = false; m.overdrive = 1; run(g3, 0.5);
  ok(m.odPhase === 0, 'medium bot keeps a full overdrive while it is healthy and armed');
  m.ap = m.apMax * 0.4; run(g3, 0.5); ok(m.odPhase === 1, 'medium bot refits under half AP');
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
  // arty: armed 1.5 s after the reward, then fires at the lock target; every shell follows the target (11 Nov 2026)
  const lockIt = () => { a.lock.target = 1; };
  v.alive = true; v.ap = v.apMax; v.protect = 0; g.events.length = 0; run(g, 0.5, lockIt);
  ok(a.artyReady && g.shells.length === 0, 'artillery does not fire in the first 1.5 s (the reward text is still being read)');
  run(g, 1.2, lockIt);
  const fire = g.events.find((e) => e.t === 'streak' && e.kind === 'arty_fire');
  ok(!a.artyReady && !!fire && fire.target === 1 && g.shells.length + g.events.filter((e) => e.t === 'explode' && e.kind === 'artillery').length === 6, 'then six shells are on their way to the locked mech');
  v.pos.x = 5000; v.pos.y = 1500; v.vel.x = v.vel.y = 0;            // the target leaves: the shells still in the air go with it
  g.events.length = 0; run(g, 5, () => { v.pos.x = 5000; v.pos.y = 1500; v.vel.x = v.vel.y = 0; });
  const booms = g.events.filter((e) => e.t === 'explode' && e.kind === 'artillery'), marks = g.events.filter((e) => e.t === 'shell');
  const off = booms.map((e) => Math.round(Math.hypot(e.pos.x - 5000, e.pos.y - 1500)));
  ok(booms.length === 6 && marks.length === 5 && g.shells.length === 0, 'all six land; the first had picked its spot already (0.9 s before landing), five pick theirs now', booms.length + '/' + marks.length);
  ok(off[0] > 1500 && off.slice(1).every((d) => d <= 285), 'the committed shell lands where the target was, the other five within 280 u of where it went', off.join());
  ok(v.ap < v.apMax, 'and the target is hurt', v.ap);
  // a target closer than 700 u: no fire, and the pilot is told (once per 5 s)
  const gc = setup([{ x: 0, lo }, { x: 400, team: 3, lo }]); const ac = gc.mechs.get(0);
  ac.artyReady = true; run(gc, 6.5, () => { ac.lock.target = 1; });
  ok(ac.artyReady && gc.shells.length === 0 && gc.events.filter((e) => e.t === 'streak' && e.kind === 'arty_close').length === 2, 'too close: holds fire and says so', gc.events.filter((e) => e.t === 'streak').length);
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
