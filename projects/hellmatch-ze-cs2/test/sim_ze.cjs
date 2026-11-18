// Bots-only Hellmatch ZE rounds, played to a result in the playsim (no CS2).
//   node test/sim_ze.cjs [players=12] [rounds=2] [core module=test/out/ze_core.cjs] [seed]
// Prints per round: the map, sides, stage progress per arena, swaps, kills by kind, the result and timing.
const path = require('path');
const N = +(process.argv[2] || 12), ROUNDS = +(process.argv[3] || 2);
const mod = path.resolve(process.argv[4] || path.join(__dirname, 'out/ze_core.cjs'));
const SEED = process.argv[5];
if (SEED !== undefined) {
  let s = +SEED >>> 0;
  const now0 = 1790000000000; Date.now = () => now0;   // P_Random is seeded from the clock
  Math.random = () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
const C = require(mod);
const cfg = JSON.parse(JSON.stringify(C.DEFAULT_CFG));
// HP=<n>: humans start with this much health (to reach the late stages on bots); CAP=<n>: zombie cap
if (process.env.HP) for (const L of C.LEVELS) if (L.ze) L.ze.humans = Object.assign({}, L.ze.humans, { health: +process.env.HP });
if (process.env.CAP) cfg.ze.cap = +process.env.CAP;
// count the zombie classes' moves (ability use, hits) by wrapping their action functions
const moves = {};
if (C.WEAPON_ACTIONS) for (const k of ['A_ZClaw', 'A_ZFireball', 'A_ZBite', 'A_ZLunge', 'A_ZDash']) {
  const f = C.WEAPON_ACTIONS[k];
  if (f) C.WEAPON_ACTIONS[k] = function (p, psp) { moves[k] = (moves[k] || 0) + 1; return f(p, psp); };
}
const rm = new C.ZeRound(C.LEVELS, cfg);
for (let i = 0; i < N; i++) rm.addPerson(i, 'bot' + i, i % 2 ? 3 : 2, true);
let fails = 0, totalTics = 0, worst = 0;
const t0 = performance.now();
for (let r = 0; r < ROUNDS; r++) {
  if (!rm.startRound()) { console.log('round did not start', JSON.stringify(rm.events)); process.exit(1); }
  const kinds = {}, ev = {};
  let tics = 0, swaps = 0, zspawns = 0, maxAlive = [0, 0], maxZp = [0, 0];
  const stageLog = [];
  while (rm.state === 'running' && tics < 35 * 900) {
    const s = performance.now();
    rm.tic(900 - tics / 35);
    const d = performance.now() - s; if (d > worst) worst = d;
    tics++;
    for (const a of rm.arenas) {
      for (const e of a.events) {
        if (e.type === 'kill') kinds[e.kind] = (kinds[e.kind] || 0) + 1;
        else if (e.type === 'zeStage') stageLog.push(`${a.mapId}@${Math.round(tics / 35)}s ${e.phase} ${e.name}${e.escape ? ' escaped ' + e.escaped : ''}`);
        else ev[e.type] = (ev[e.type] || 0) + 1;
      }
      a.events.length = 0;
      if ((tics & 31) === 0 && a.director) {
        const al = a.director.alive(), zp = a.director.zombiePlayers();
        if (al > maxAlive[a.index]) maxAlive[a.index] = al;
        if (zp > maxZp[a.index]) maxZp[a.index] = zp;
        if (al + zp > a.director.capN + 2) { console.log(`CAP EXCEEDED ${a.mapId} AI ${al} + players ${zp} > ${a.director.capN}`); fails++; }
      }
    }
    for (const e of rm.events) { if (e.type === 'zeSwap') swaps++; else if (e.type === 'zeZombie') zspawns++; }
    rm.events.length = 0;
  }
  totalTics += tics;
  const res = rm.zeResult;
  const desc = rm.arenas.map((a) => `${a.mapId}(side ${a.zeSide}) stages ${a.ze.reached()}/${a.ze.stages.length} AI max ${maxAlive[a.index]} zombie players max ${maxZp[a.index]}`).join(' | ');
  console.log(`round ${r + 1}: ${rm.base && rm.base.id} ${N} bots, ${(tics / 35).toFixed(0)}s -> ${res ? res.text + ' (' + res.why + ', wiped at ' + JSON.stringify(rm.wipedAt) + ', tic ' + rm.time + ')' : 'NO RESULT'}`);
  console.log('  ' + desc);
  console.log(`  swaps ${swaps}, zombie spawns ${zspawns}, kills ${JSON.stringify(kinds)}`);
  console.log(`  events ${JSON.stringify(ev)}`);
  console.log('  stages: ' + stageLog.join('; '));
  if (!res) fails++;
}
const ms = performance.now() - t0;
console.log('zombie player moves', JSON.stringify(moves));
console.log(`sim_ze ${totalTics} tics in ${ms} ms -> ${(ms / totalTics).toFixed(3)} ms per tic (worst ${worst.toFixed(1)} ms) for ${N} bots; ${fails ? 'PROBLEMS ' + fails : 'OK'}`);
process.exit(fails ? 1 : 0);
