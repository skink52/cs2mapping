// Bot races on the pure game: durations, lap times, wrecks, falls, car balance, team points, kill plans.
// usage: node test/sim.cjs [players=32] [rounds=6] [opts: trace,track=<id>,skill=0.5,laps=N,v,seed=N,even,json,tune=<file>]
const C = require('../build/core_test.cjs');
const N = +(process.argv[2] || 32), ROUNDS = +(process.argv[3] || 6), OPTS = process.argv[4] || '';
if (OPTS.includes('nocr')) for (const t of C.TRACKS) delete t.creatures;     // nocr: the sea creatures stay home
const opt = (k, d) => { const m = OPTS.match(new RegExp(k + '=([^,]+)')); return m ? m[1] : d; };
C.seedRandom(+opt('seed', 7));
// tune=<file.json>: try other numbers without rebuilding - { "RULES": { ... }, "CARS": { "hornet": { ... } } }
const tune = opt('tune', null);
if (tune) {
  const t = JSON.parse(require('fs').readFileSync(tune, 'utf8'));
  Object.assign(C.RULES, t.RULES || {});
  for (const [k, v] of Object.entries(t.CARS || {})) Object.assign(C.CARS[k], v);
}
const cfg = { botSkill: +opt('skill', 0.5), staggerArenas: false, laps: +opt('laps', 0) };
const only = opt('track', null);
const rm = new C.RoundManager(only ? C.TRACKS.filter((t) => t.id === only) : C.TRACKS, cfg);
if (only) rm.cfg.trackBlacklist = [];
for (let i = 0; i < N; i++) rm.addPerson(i, 'bot' + i, i % 2 ? 3 : 2, true);
// even: the same number of each car (the bots' own picks are random), turned round every round
const even = OPTS.includes('even');
const classStats = {}; for (const k of C.CAR_KEYS) classStats[k] = { races: 0, posSum: 0, wins: 0, podiums: 0, wrecks: 0, top8: 0, kos: 0, spinHits: 0, abil: 0, abilHits: 0, bigAir: 0 };
let launches = 0, stalls = 0;
let totalWrecks = 0, totalFalls = 0, totalKO = 0, worst = 0;
const t0 = Date.now();
let ticks = 0;
const creatureHits = {}, creatureByTrack = {};
for (let r = 0; r < ROUNDS; r++) {
  if (even) for (let i = 0; i < N; i++) rm.person(i).carChoice = C.CAR_KEYS[(i + (r >> 1)) % C.CAR_KEYS.length];
  if (!rm.startRound()) { console.log('not enough players'); break; }
  const falls = {}, wrecks = {}, kos = {}, laps = {};
  let steps = 0;
  const trace = OPTS.includes('trace') ? rm.arenas[0].order[0] : null;
  while (rm.state === 'running' && steps < 400 * 64) {
    const s = performance.now();
    rm.tic(); steps++; ticks++;
    const d = performance.now() - s; if (d > worst) worst = d;
    for (const a of rm.arenas) for (const e of a.events) {
      if (e.type === 'wreck') { wrecks[a.index] = (wrecks[a.index] || 0) + 1; if (e.attacker) { kos[a.index] = (kos[a.index] || 0) + 1; classStats[e.attacker.cls].kos++; } }
      if (e.type === 'spinHit' && e.attacker) classStats[e.attacker.cls].spinHits++;
      if (e.type === 'creatureHit') { creatureHits[e.car.isBot ? 'bot' : 'human'] = (creatureHits[e.car.isBot ? 'bot' : 'human'] || 0) + 1; creatureByTrack[e.cr.kind] = (creatureByTrack[e.cr.kind] || 0) + 1; }
      if (e.type === 'ability') { classStats[e.car.cls].abil++; classStats[e.car.cls].abilHits += e.hits || 0; }
      if (e.type === 'boltHit' && !e.blocked) classStats[e.bolt.owner.cls].abilHits++;
      if (e.type === 'launch') launches++;
      if (e.type === 'stall') stalls++;
      if (e.type === 'lap') { (laps[a.index] ||= []).push(e.last); }
    }
    for (const a of rm.arenas) for (const c of a.order) { if (c.fx & 128) falls[a.index] = (falls[a.index] || 0) + 1; if (c.fx & 4096) classStats[c.cls].bigAir++; }
    for (const a of rm.arenas) a.events.length = 0;
    rm.events.length = 0;
    if (trace && steps % 64 === 0 && steps < 64 * 60) {
      const T = rm.arenas[0].track;
      console.log(`t=${(steps / 64).toFixed(0)}s ${trace.cls} spd ${trace.speed.toFixed(0)} vl ${trace.vl.toFixed(0)} d ${trace.d.toFixed(0)}/${T.hw[trace.seg]} s ${trace.s.toFixed(0)} lap ${trace.lapsDone} cp ${trace.nextCp} shield ${trace.shield.toFixed(0)} charge ${trace.charge.toFixed(0)} boost ${trace.boosting ? 1 : 0} pad ${trace.padTimer > 0 ? 1 : 0} drift ${trace.drifting ? 1 : 0} state ${trace.state} pos ${trace.pos}`);
    }
  }
  const pts = rm.teamPoints();
  for (const a of rm.arenas) {
    const res = a.result;
    const lp = laps[a.index] || [];
    const fin = res.ranking.filter((c) => c.state === 'gone' || c.state === 'finished').length;
    const kp = rm.killPlan(a);
    const credit = {};
    for (const k of kp) credit[k.killer ? k.killer.name : 'world'] = (credit[k.killer ? k.killer.name : 'world'] || 0) + 1;
    console.log(`round ${r + 1} arena ${a.index} ${a.track.id.padEnd(9)} ${a.order.length} cars ${a.laps} laps: ${res.reason.padEnd(6)} ${(a.raceTic / 64).toFixed(0)}s, finished ${fin}, wrecks ${wrecks[a.index] || 0} (KO ${kos[a.index] || 0}), falls ${falls[a.index] || 0}, lap avg ${(lp.reduce((x, y) => x + y, 0) / Math.max(1, lp.length)).toFixed(1)}s best ${Math.min(...lp, 999).toFixed(1)}s | winner ${res.winner ? res.winner.name + '/' + res.winner.cls : '-'} | kills ${JSON.stringify(credit)} (${kp.length})`);
    if (OPTS.includes('v')) console.log('   ' + res.ranking.map((c, i) => `${i + 1}.${c.name}(${c.cls[0]}${c.state[0]})`).join(' '));
    res.ranking.forEach((c, i) => { const cs = classStats[c.cls]; cs.races++; cs.posSum += i + 1; if (i === 0) cs.wins++; if (i < 3) cs.podiums++; if (i < 8) cs.top8++; if (c.state === 'wrecked') cs.wrecks++; });
    totalWrecks += wrecks[a.index] || 0; totalFalls += falls[a.index] || 0; totalKO += kos[a.index] || 0;
  }
  console.log(`   team points T ${pts[2]} CT ${pts[3]} -> ${pts.winner === 2 ? 'T' : pts.winner === 3 ? 'CT' : 'draw'} ${JSON.stringify(pts.detail)}`);
  rm.endRoundCleanup(); rm.state = 'idle';
}
// car balance: per 100 races of that car (a race = one car in one arena), so classes picked more or less often compare
const races = Object.values(classStats).reduce((n, s) => n + s.races, 0) / 4;
console.log('car balance (per 100 starts):');
for (const [k, s] of Object.entries(classStats)) {
  const per = (v) => (100 * v / Math.max(1, s.races)).toFixed(1).padStart(5);
  console.log(`  ${k.padEnd(8)} starts ${String(s.races).padStart(5)}  avg place ${(s.posSum / Math.max(1, s.races)).toFixed(2).padStart(5)}  wins ${per(s.wins)}  podiums ${per(s.podiums)}  top 8 ${per(s.top8)}  wrecked ${per(s.wrecks)}  wreck kills ${per(s.kos)}  spin hits ${per(s.spinHits)}  E uses ${per(s.abil)} (hits ${per(s.abilHits)})  big air ${per(s.bigAir)}`);
}
if (OPTS.includes('json')) console.log('JSON ' + JSON.stringify(classStats));
console.log(`turbo starts ${launches}, stalls ${stalls}`);
if (Object.keys(creatureByTrack).length) console.log('sea creature hits', JSON.stringify(creatureByTrack));
console.log(`wrecks ${totalWrecks} (KO ${totalKO}), falls ${totalFalls}; ${ticks} tics in ${Date.now() - t0} ms (${((Date.now() - t0) / ticks).toFixed(3)} ms/tic, worst ${worst.toFixed(1)} ms)`);
