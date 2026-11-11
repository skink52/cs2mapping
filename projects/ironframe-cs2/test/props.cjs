// Destructible street props (src/core/88_props.js). usage: node test/props.cjs
// A flat arena with five cars by hand: shots, blasts, a chain, a mech walking over one, the reset at the next round.
const { C, ARENA, makeGame } = require('./lib.cjs');
const L = C.IF_Game.lib, F = L.IF_PROPS_CFG;
const DT = 1 / 64;
let fails = 0, passes = 0;
function ok(cond, name, info) { if (cond) passes++; else { fails++; console.log('FAIL ' + name + (info !== undefined ? ': ' + info : '')); } }

const FLAT = JSON.parse(JSON.stringify(ARENA));
FLAT.nav.height = FLAT.nav.height.map(() => 100); FLAT.nav.struct = FLAT.nav.struct.map(() => 0); FLAT.nav.walk = FLAT.nav.walk.map(() => 1);
// [x, y, z, radius, big]: two close together (a chain), one far, one for the walk, one bus
FLAT.cars = [[600, 0, 100, 50, 0], [800, 0, 100, 50, 0], [3000, 3000, 100, 50, 0], [0, 900, 100, 50, 0], [-2000, 0, 100, 90, 1]];

function setup(specs) {
  const g = makeGame({ arena: FLAT, seed: 5, cfg: { round: { tb: 9999, cq: 9999, sk: 9999, so: 9999, warmup: 0, podium: 3 }, ai: { npcFill: false } } });
  g.setMode('tb', 2); g.startRound(0);
  specs.forEach((s, i) => { g.addPlayer(i, { team: i % 2 ? 3 : 2, human: true, name: 'p' + i, pilot: null }); g.requestSpawn(i); });
  g.tick(DT, 0);
  specs.forEach((s, i) => { const m = g.mechs.get(i); m.pos.x = s.x; m.pos.y = s.y; m.pos.z = 100; m.vel.x = m.vel.y = m.vel.z = 0; m.dropT = 0; m.onGround = true; m.protect = 0; m.histN = 0; });
  g.tick(DT, DT); g.events.length = 0;
  return g;
}
const run = (g, n) => { for (let k = 0; k < n; k++) g.tick(DT, g.time + DT); };
const evs = (g, t) => g.events.filter((e) => e.t === t);

{ // 1. the list, the reset, a map without cars
  const g = setup([{ x: -5000, y: -5000 }, { x: 5000, y: 5000 }]);
  const P = g.dprops;
  ok(P && P.list.length === 5 && P.alive === 5, 'five props alive at the round start');
  ok(P.list[4].hp === F.hpBig && P.list[0].hp === F.hp, 'a bus has more hit points');
  const bare = JSON.parse(JSON.stringify(FLAT)); delete bare.cars;
  const g0 = makeGame({ arena: bare, seed: 1, cfg: { ai: { npcFill: false } } }); g0.setMode('tb', 2); g0.startRound(0); g0.tick(DT, 0);
  ok(g0.dprops && g0.dprops.list.length === 0, 'a map without arena.cars: no props, no error');
}
{ // 2. shots: a segment through a car hurts it once, a miss does not; enough damage destroys it and it explodes a tick later
  const g = setup([{ x: -5000, y: -5000 }, { x: 5000, y: 5000 }]);
  const P = g.dprops, far = P.list[2];
  L.IF_propsSegment(g, 2000, 3000, 120, 4000, 3000, 120, 250, 0);
  ok(far.hp === F.hp - 250, 'a shot through the car takes its damage off', far.hp);
  L.IF_propsSegment(g, 2000, 3400, 120, 4000, 3400, 120, 250, 0);
  ok(far.hp === F.hp - 250, 'a shot 400 u beside it does nothing');
  L.IF_propsSegment(g, 3000, 3000, 3000, 3000, 3000, 110, 9999, 0);
  ok(!far.alive && evs(g, 'prop').length === 1 && evs(g, 'prop')[0].how === 'boom' && evs(g, 'prop')[0].slot === 0, 'destroyed: a prop event, how boom, the shooter named');
  ok(evs(g, 'explode').length === 0, 'no explosion in the same tick');
  run(g, 1);
  const ex = evs(g, 'explode');
  ok(ex.length === 1 && ex[0].kind === 'car' && Math.abs(ex[0].pos.x - 3000) < 1, 'the explosion comes on the next tick', JSON.stringify(ex[0] || null));
  ok(P.alive === 4 && far.burnT > 0, 'it burns');
  run(g, Math.ceil(F.burn * 64) + 2);
  ok(far.burnT === 0 && evs(g, 'prop_out').length === 1, 'the fire goes out after cfg.burn seconds');
}
{ // 3. a blast takes both cars of the pair; a blast out of reach takes none; the chain: one car's explosion sets off its neighbour
  const g = setup([{ x: -5000, y: -5000 }, { x: 5000, y: 5000 }]);
  const P = g.dprops, a = P.list[0], b = P.list[1];
  L.IF_explode(g, { x: 600, y: 2000, z: 100 }, 400, 5000, 0, 0, 'test', 'test', null);
  ok(a.alive && b.alive && a.hp === F.hp, 'a blast 2 000 u away: untouched');
  L.IF_propsBlast(g, { x: 560, y: 0, z: 100 }, 100, F.hp * 3, 0);
  ok(!a.alive && b.alive, 'a small blast on the first car destroys only it');
  run(g, 1);
  ok(!b.alive, 'the chain: its explosion a tick later destroys the neighbour 200 u away', b.hp);
  ok(evs(g, 'prop').filter((e) => e.how === 'boom').length === 2 && evs(g, 'prop')[1].slot === 0, 'the second wreck is credited to the one who started it');
  run(g, 1); ok(evs(g, 'explode').filter((e) => e.kind === 'car').length === 2, 'each wreck exploded once, one tick apart');
}
{ // 4. a mech on the car's explosion takes damage, credited to the one who shot the car
  const g = setup([{ x: -5000, y: -5000 }, { x: 3060, y: 3000 }]);
  const v = g.mechs.get(1), ap0 = v.ap;
  L.IF_propsSegment(g, 3000, 3000, 3000, 3000, 3000, 110, 9999, 0);
  run(g, 2);
  ok(v.ap < ap0, 'the mech beside the car is hurt by its explosion', ap0 - v.ap);
  const dm = evs(g, 'damage').find((e) => e.victim === 1);
  ok(dm && dm.attacker === 0, 'the damage is the shooter\'s', JSON.stringify(dm || null));
}
{ // 5. walking over a car crushes it (no explosion); standing on it does not
  const g = setup([{ x: 0, y: 900 }, { x: 5000, y: 5000 }]);
  const P = g.dprops, c = P.list[3], m = g.mechs.get(0);
  run(g, 3);
  ok(c.alive, 'a mech standing still on a car leaves it');
  m.vel.x = 400; m.onGround = true; run(g, 1);
  ok(!c.alive && evs(g, 'prop').some((e) => e.how === 'crush' && e.slot === 0), 'a walking mech crushes it');
  run(g, 3);
  ok(evs(g, 'explode').filter((e) => e.kind === 'car').length === 0 && c.burnT === 0, 'crushed: no explosion, no fire');
}
{ // 6. the next round: everything whole again
  const g = setup([{ x: -5000, y: -5000 }, { x: 5000, y: 5000 }]);
  L.IF_propsBlast(g, { x: 700, y: 0, z: 100 }, 400, 99999, 0);
  ok(g.dprops.alive === 3, 'two destroyed');
  g.events.length = 0; g.startRound(g.time);
  ok(g.dprops.alive === 5 && g.dprops.list.every((p) => p.alive && p.hp > 0) && evs(g, 'props_reset').length === 1, 'a new round restores all five (props_reset)');
}
console.log((fails ? 'FAIL: ' + fails + ' of ' : 'props: ') + (passes + fails) + (fails ? ' checks' : ' passed, 0 failed'));
process.exit(fails ? 1 : 0);
