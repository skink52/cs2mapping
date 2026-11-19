// Balance table for Hellmatch ZE (Round 3): test/sim_ze.cjs, one bots-only round per map x seed x size, run in parallel,
// summed per map and size from each run's SIMJSON line.
//   node test/balance_ze.cjs [core=test/out/hellescape_core.cjs] [maps=map01,e1m1,...] [seeds=8] [sizes=16,32] [jobs=4]
// Environment passes through to sim_ze (ZECFG, SCCAP=none, HP...). Prints one progress line per finished run and a table:
// stage 2+ = arenas whose second stage started (of all arenas), stage 3+, escapes (of rounds), mean round length, the
// largest AI horde alive at once, surges / AI they brought, drops made / picked up, results by kind.
const { spawn } = require('child_process');
const path = require('path');
const arg = (k, d) => { const a = process.argv.find((x) => x.startsWith(k + '=')); return a ? a.slice(k.length + 1) : d; };
const core = path.resolve(arg('core', path.join(__dirname, 'out/hellescape_core.cjs')));
const C = require(core);
const allMaps = [...new Set(C.LEVELS.filter((L) => L.ze && L.side).map((L) => L.base || L.id.slice(0, -1)))];
const maps = arg('maps', allMaps.join(',')).split(',').filter(Boolean);
const seeds = +arg('seeds', 8), sizes = arg('sizes', '16,32').split(',').map(Number), jobs = +arg('jobs', 4);
const runs = [];
for (const m of maps) for (const n of sizes) for (let s = 1; s <= seeds; s++) runs.push({ m, n, s });
const out = new Map();
let next = 0, done = 0, failed = 0;
const t0 = Date.now();
function start() {
  if (next >= runs.length) return;
  const r = runs[next++];
  const zecfg = Object.assign(process.env.ZECFG ? JSON.parse(process.env.ZECFG) : {}, { map: r.m });
  const ch = spawn(process.execPath, [path.join(__dirname, 'sim_ze.cjs'), String(r.n), '1', core, String(r.s)], { env: Object.assign({}, process.env, { ZECFG: JSON.stringify(zecfg) }) });
  let buf = '';
  ch.stdout.on('data', (d) => { buf += d; });
  ch.stderr.on('data', (d) => { buf += d; });
  ch.on('close', (code) => {
    done++;
    const line = buf.split('\n').find((l) => l.startsWith('SIMJSON '));
    if (!line || code) { failed++; console.log(`FAILED ${r.m} ${r.n} seed ${r.s} (exit ${code})\n` + buf.split('\n').filter((l) => /PROBLEM|EXCEEDED|DASH|Error|at /.test(l)).slice(0, 6).join('\n')); }
    if (line) {
      const j = JSON.parse(line.slice(8));
      const k = r.m + ' ' + (r.n / 2) + 'v' + (r.n / 2);
      const t = out.get(k) || { rounds: 0, secs: 0, escapes: 0, arenas: 0, stage2: 0, stage3: 0, results: {}, surges: 0, surgeAI: 0, gives: 0, resupplies: 0, drops: 0, dropsTaken: 0, maxAI: 0, caps: [] };
      for (const f of ['rounds', 'secs', 'escapes', 'arenas', 'stage2', 'stage3', 'surges', 'surgeAI', 'gives', 'resupplies', 'drops', 'dropsTaken']) t[f] += j[f];
      t.maxAI = Math.max(t.maxAI, j.maxAI);
      for (const c of j.caps) if (!t.caps.includes(c)) t.caps.push(c);
      for (const [w, n] of Object.entries(j.results)) t.results[w] = (t.results[w] || 0) + n;
      out.set(k, t);
      console.log(`[${done}/${runs.length} ${((Date.now() - t0) / 1000).toFixed(0)}s] ${k} seed ${r.s}: ${(j.secs).toFixed(0)}s stage2 ${j.stage2}/${j.arenas} esc ${j.escapes} maxAI ${j.maxAI}`);
    }
    if (done === runs.length) report(); else start();
  });
}
function report() {
  console.log('\nmap size     | stage 2+ | stage 3+ | escapes | mean round | max AI (cap) | surges (AI) | drops (taken) | results');
  for (const [k, t] of out) {
    console.log(`${k.padEnd(12)} | ${(t.stage2 + '/' + t.arenas).padEnd(8)} | ${(t.stage3 + '/' + t.arenas).padEnd(8)} | ${(t.escapes + '/' + t.rounds).padEnd(7)} | ${(t.secs / t.rounds).toFixed(0).padStart(5)} s    | ${(t.maxAI + ' (' + t.caps.join('/') + ')').padEnd(12)} | ${(t.surges + ' (' + t.surgeAI + ')').padEnd(11)} | ${(t.drops + ' (' + t.dropsTaken + ')').padEnd(13)} | ${JSON.stringify(t.results)}`);
  }
  console.log(`balance_ze: ${runs.length} runs, ${failed} failed, ${((Date.now() - t0) / 1000).toFixed(0)} s`);
  process.exitCode = failed ? 1 : 0;
}
for (let i = 0; i < jobs; i++) start();
