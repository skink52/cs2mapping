// Bots-only Hellmatch ZE rounds, played to a result in the playsim (no CS2).
//   node test/sim_ze.cjs [players=12] [rounds=2] [core module=test/out/hellescape_core.cjs] [seed]
// Env: ZECFG / ARENACFG (cfg overrides, e.g. '{"map":"e1m4"}'), HP, CAP, SCCAP=none (sidecar caps off), PRE=<module> (a debug hook
// required after the core module). Ends with a SIMJSON line (test/balance_ze.cjs sums those).
// Prints per round: the map, sides, stage progress per arena, swaps, kills by kind, the result and timing.
const path = require('path');
const N = +(process.argv[2] || 12), ROUNDS = +(process.argv[3] || 2);
const mod = path.resolve(process.argv[4] || path.join(__dirname, 'out/hellescape_core.cjs'));
const SEED = process.argv[5];
if (SEED !== undefined) {
  let s = +SEED >>> 0;
  const now0 = 1790000000000; Date.now = () => now0;   // P_Random is seeded from the clock
  Math.random = () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
const C = require(mod); if (process.env.PRE) require(process.env.PRE);
const cfg = JSON.parse(JSON.stringify(C.DEFAULT_CFG));
// HP=<n>: humans start with this much health (to reach the late stages on bots); CAP=<n>: zombie cap
if (process.env.HP) for (const L of C.LEVELS) if (L.ze) L.ze.humans = Object.assign({}, L.ze.humans, { health: +process.env.HP });
// ZECFG='{"aiBase":4,...}' / ARENACFG='{"zeKnockback":2}': overrides merged into cfg.ze / cfg.arena (balance runs)
if (process.env.ZECFG) Object.assign(cfg.ze, JSON.parse(process.env.ZECFG));
if (process.env.ARENACFG) Object.assign(cfg.arena, JSON.parse(process.env.ARENACFG));
// SCCAP=none: the sidecars' zombies.cap (a maximum since Round 3) is ignored: the cap formula alone
if (process.env.SCCAP === 'none') for (const L of C.LEVELS) if (L.ze && L.ze.zombies) { L.ze.zombies = Object.assign({}, L.ze.zombies); delete L.ze.zombies.cap; }
// (a sidecar's own zombies.cap wins over the config's, so CAP sets both)
if (process.env.CAP) { cfg.ze.cap = +process.env.CAP; for (const L of C.LEVELS) if (L.ze) L.ze.zombies = Object.assign({}, L.ze.zombies, { cap: +process.env.CAP }); }
// count the zombie classes' moves (ability use, hits) by wrapping their action functions
const moves = {};
// dash audit: every demon lunge / lost soul dash is followed to its end: how far it went, whether it ended against a
// wall (bump) or on a human, and that the body is never left inside a wall or outside the floor-ceiling gap
const dashes = [], dashLog = { LOSTSOUL: [], DEMON: [] };
let dashBad = 0;
if (C.WEAPON_ACTIONS) for (const k of ['A_ZClaw', 'A_ZFireball', 'A_ZBite', 'A_ZLunge', 'A_ZDash']) {
  const f = C.WEAPON_ACTIONS[k];
  if (f) C.WEAPON_ACTIONS[k] = function (p, psp) {
    moves[k] = (moves[k] || 0) + 1;
    if (k === 'A_ZLunge' || k === 'A_ZDash') dashes.push({ p, mo: p.mo, x: p.mo.x, y: p.mo.y, n: 0 });
    return f(p, psp);
  };
}
function dashAudit(a) {
  for (let i = dashes.length - 1; i >= 0; i--) {
    const d = dashes[i];
    if (d.p.arena !== a) continue;
    if (d.mo.removed || d.p.mo !== d.mo || d.mo.health <= 0) { dashes.splice(i, 1); continue; }
    d.n++;
    a.run(() => {
      const mo = d.mo, sec = a.level.sectorAt(mo.x, mo.y);
      const probe = { x: mo.x, y: mo.y, z: mo.z, radius: mo.radius, height: mo.height, flags: mo.flags, info: mo.info, type: mo.type, player: mo.player, sector: null };
      // overlapping a wall line, or sunk into the floor / poking through the ceiling (another body in the way is fine:
      // a charge ends against a human)
      C.TM.blockline = null;
      C.checkPositionProbe(probe, mo.x, mo.y);
      if (C.TM.blockline || mo.z < C.TM.floorz - 1 || mo.z + mo.height > C.TM.ceilingz + 1) {
        dashBad++;
        if (dashBad < 4) console.log(`DASH INSIDE WALL ${mo.player.zclass} at ${mo.x.toFixed(0)},${mo.y.toFixed(0)} z ${mo.z.toFixed(0)} sector ${sec.id} floor ${C.TM.floorz} ceil ${C.TM.ceilingz} line ${C.TM.blockline && C.TM.blockline.id}`);
      }
    });
    if (d.p.zdash <= 0 && d.n > 2) {
      dashLog[d.p.zclass] && dashLog[d.p.zclass].push({ dist: Math.hypot(d.mo.x - d.x, d.mo.y - d.y), hit: !!d.p.zhit, tics: d.n });
      dashes.splice(i, 1);
    }
  }
}
// Round 3: ammo drops made / picked up, the most AI alive at once, per round (summed into the SIMJSON line at the end)
let dropsMade = 0;
if (C.ZeArena) { const f = C.ZeArena.prototype.dropFor; C.ZeArena.prototype.dropFor = function (mo) { const it = f.call(this, mo); if (it) dropsMade++; return it; }; }
const summary = { rounds: 0, secs: 0, escapes: 0, arenas: 0, stage2: 0, stage3: 0, results: {}, surges: 0, surgeAI: 0, gives: 0, resupplies: 0, drops: 0, dropsTaken: 0, maxAI: 0, caps: [] };
const rm = new C.ZeRound(C.LEVELS, cfg);
for (let i = 0; i < N; i++) rm.addPerson(i, 'bot' + i, i % 2 ? 3 : 2, true);
let fails = 0, totalTics = 0, worst = 0;
const t0 = performance.now();
for (let r = 0; r < ROUNDS; r++) {
  if (!rm.startRound()) { console.log('round did not start', JSON.stringify(rm.events)); process.exit(1); }
  const kinds = {}, ev = {}, clsCount = {};
  const drops0 = dropsMade; let taken = 0;
  let tics = 0, swaps = 0, zspawns = 0, maxAlive = [0, 0], maxZp = [0, 0];
  const stageLog = [];
  while (rm.state === 'running' && tics < 35 * 900) {
    const s = performance.now();
    rm.tic(900 - tics / 35);
    const d = performance.now() - s; if (d > worst) worst = d;
    tics++;
    for (const a of rm.arenas) {
      if (dashes.length) dashAudit(a);
      for (const e of a.events) {
        if (e.type === 'kill') kinds[e.kind] = (kinds[e.kind] || 0) + 1;
        else if (e.type === 'zeSurge') { summary.surges++; summary.surgeAI += e.count; ev.zeSurge = (ev.zeSurge || 0) + 1; }
        else if (e.type === 'zeGive') { summary.gives++; ev.zeGive = (ev.zeGive || 0) + 1; }
        else if (e.type === 'zeResupply') { summary.resupplies++; ev.zeResupply = (ev.zeResupply || 0) + 1; }
        else if (e.type === 'zeStage') stageLog.push(`${a.mapId}@${Math.round(tics / 35)}s ${e.phase} ${e.name}${e.escape ? ' escaped ' + e.escaped : ''}`);
        else ev[e.type] = (ev[e.type] || 0) + 1;
      }
      a.events.length = 0;
      if ((tics & 31) === 0 && a.director && !a.finished) {   // (a finished arena's horde stands still)
        const al = a.director.alive(), zp = a.director.zombiePlayers();
        if (al > maxAlive[a.index]) maxAlive[a.index] = al;
        if (zp > maxZp[a.index]) maxZp[a.index] = zp;
        // over the cap on two samples in a row (~1.8 s): a burst of swaps is trimmed within the horde's next check
        if (al + zp > a.director.capN + 2) { if (a.simOver) { console.log(`CAP EXCEEDED ${a.mapId} AI ${al} + players ${zp} > ${a.director.capN}`); fails++; } a.simOver = true; } else a.simOver = false;
      }
    }
    for (const e of rm.events) { if (e.type === 'zeSwap') swaps++; else if (e.type === 'zeZombie') { zspawns++; clsCount[e.cls] = (clsCount[e.cls] || 0) + 1; } }
    rm.events.length = 0;
  }
  totalTics += tics;
  const res = rm.zeResult;
  for (const a of rm.arenas) for (const p of a.players.values()) taken += p.stats.pickups || 0;
  summary.rounds++; summary.secs += tics / 35; summary.drops += dropsMade - drops0; summary.dropsTaken += taken;
  if (res) { summary.results[res.why] = (summary.results[res.why] || 0) + 1; if (res.why === 'escape') summary.escapes++; }
  for (const a of rm.arenas) {
    summary.arenas++;
    if (a.ze.stages[1] && a.ze.stages[1].state !== 'pending') summary.stage2++;
    if (a.ze.stages[2] && a.ze.stages[2].state !== 'pending') summary.stage3++;
    summary.maxAI = Math.max(summary.maxAI, maxAlive[a.index]);
    if (!summary.caps.includes(a.director.capN)) summary.caps.push(a.director.capN);
  }
  const desc = rm.arenas.map((a) => `${a.mapId}(side ${a.zeSide}) stages ${a.ze.reached()}/${a.ze.stages.length} AI max ${maxAlive[a.index]} zombie players max ${maxZp[a.index]}`).join(' | ');
  console.log(`round ${r + 1}: ${rm.base && rm.base.id} ${N} bots, ${(tics / 35).toFixed(0)}s -> ${res ? res.text + ' (' + res.why + ', wiped at ' + JSON.stringify(rm.wipedAt) + ', tic ' + rm.time + ')' : 'NO RESULT'}`);
  console.log('  ' + desc);
  console.log(`  drops ${dropsMade - drops0} (pickups by humans ${taken}), caps ${rm.arenas.map((a) => a.director.capN).join('/')}`);
  console.log(`  swaps ${swaps}, zombie spawns ${zspawns} ${JSON.stringify(clsCount)}, kills ${JSON.stringify(kinds)}`);
  console.log(`  events ${JSON.stringify(ev)}`);
  console.log('  stages: ' + stageLog.join('; '));
  if (!res) fails++;
}
const ms = performance.now() - t0;
console.log('zombie player moves', JSON.stringify(moves));
for (const [k, l] of Object.entries(dashLog)) if (l.length) {
  const ds = l.map((x) => x.dist).sort((x, y) => x - y), med = ds[ds.length >> 1];
  console.log(`  ${k} charges ${l.length}: hit a human ${l.filter((x) => x.hit).length}, median ${med.toFixed(0)} units, short (<40% / wall) ${ds.filter((x) => x < (k === 'DEMON' ? 96 : 115)).length}`);
}
if (dashBad) { console.log(`DASH: ${dashBad} tics with a charging body inside a wall or outside its sector's gap`); fails++; }
console.log('SIMJSON ' + JSON.stringify(summary));
console.log(`sim_ze ${totalTics} tics in ${ms} ms -> ${(ms / totalTics).toFixed(3)} ms per tic (worst ${worst.toFixed(1)} ms) for ${N} bots; ${fails ? 'PROBLEMS ' + fails : 'OK'}`);
process.exit(fails ? 1 : 0);
