// Load shedding on full servers (core cfg.load, src/core/80_game.js tick). usage: node test/load.cjs
// 48 mechs (2 humans, 46 AI): above simHalfAbove each AI mech is simulated every other tick (two groups by slot) with twice the
// time step; humans every tick. It must not change how far AI mechs get, and nothing breaks over a long run.
const { C, ARENA, makeGame } = require('./lib.cjs');
const DT = 1 / 64;
let fails = 0, passes = 0;
function ok(cond, name, info) { if (cond) passes++; else { fails++; console.log('FAIL ' + name + (info !== undefined ? ': ' + info : '')); } }

function setup(n, load) {
  const cfg = { round: { tb: 9999, cq: 9999, sk: 9999, so: 9999, warmup: 0, podium: 3 }, ai: { npcFill: false } };
  if (load) cfg.load = load;
  const g = makeGame({ arena: ARENA, seed: 9, cfg });
  g.setMode('tb', 2); g.startRound(0);
  for (let i = 0; i < n; i++) { g.addPlayer(i, { team: i % 2 ? 3 : 2, human: i < 2, name: 'p' + i, pilot: null }); g.requestSpawn(i); }
  return g;
}
const run = (g, n, each) => { for (let k = 0; k < n; k++) { g.tick(DT, g.time + DT); if (each) each(g); } };
const alive = (g) => [...g.mechs.values()].filter((m) => m.alive);
function travel(g, secs) {
  const last = new Map(), dist = new Map();
  run(g, Math.round(secs * 64), (gg) => {
    for (const m of alive(gg)) {
      if (m.human || m.dropT > 0) continue;
      const p = last.get(m.slot);
      if (p) dist.set(m.slot, (dist.get(m.slot) || 0) + Math.hypot(m.pos.x - p.x, m.pos.y - p.y));
      last.set(m.slot, { x: m.pos.x, y: m.pos.y });
    }
  });
  let s = 0; for (const v of dist.values()) s += v;
  return s / Math.max(1, dist.size);
}

{ // 1. the levels and the groups
  const g = setup(48);
  run(g, 64 * 4);
  const L = alive(g);
  ok(L.length > 40, 'most of the 48 are alive after the drop', L.length);
  ok(g.loadLevel === 2, 'above 40 live mechs: level 2 (AI simulated every other tick)', g.loadLevel);
  const before = new Map(L.map((m) => [m.slot, m.simOff]));
  run(g, 1);
  let flipped = 0, humansOff = 0, ai = 0;
  for (const m of alive(g)) {
    if (m.human) { if (m.simOff) humansOff++; continue; }
    ai++; if (before.has(m.slot) && before.get(m.slot) !== m.simOff) flipped++;
  }
  ok(humansOff === 0, 'humans are never skipped', humansOff);
  ok(flipped >= ai - 2, 'each AI mech alternates between simulated and skipped', flipped + ' of ' + ai);
  const off = alive(g).filter((m) => m.simOff).length;
  ok(off > ai * 0.3 && off < ai * 0.7, 'about half the AI mechs are skipped in a tick', off + ' of ' + ai);
}
{ // 2. a small game: no shedding
  const g = setup(16);
  run(g, 64 * 4);
  ok(g.loadLevel === 0, '16 mechs: level 0', g.loadLevel);
  ok(alive(g).every((m) => !m.simOff), '16 mechs: nobody skipped');
}
{ // 3. it moves them as far: the same 48-mech round with and without shedding
  const off = setup(48, { aiHalfAbove: 1e9, simHalfAbove: 1e9 }); run(off, 64 * 4);
  const on = setup(48); run(on, 64 * 4);
  const a = travel(off, 10), b = travel(on, 10);
  ok(a > 200, 'AI mechs move in 10 s', a.toFixed(0));
  ok(Math.abs(b - a) / a < 0.3, 'AI mechs get about as far at half rate (within 30 %)', 'full ' + a.toFixed(0) + ', half ' + b.toFixed(0));
}
{ // 4. a long run at level 2 stays finite and keeps fighting
  const g = setup(48); g.events.length = 0;
  let kills = 0;
  run(g, 64 * 60, (gg) => { for (const e of gg.events) if (e.t === 'kill') kills++; gg.events.length = 0; });
  ok(alive(g).every((m) => Number.isFinite(m.pos.x + m.pos.y + m.pos.z + m.vel.x + m.vel.y + m.vel.z)), 'positions and velocities stay finite');
  ok(kills > 0, 'the AI still fights at half rate (kills in 60 s)', kills);
}
console.log((fails ? 'FAILED ' : 'ok ') + passes + ' passed, ' + fails + ' failed');
process.exit(fails ? 1 : 0);
