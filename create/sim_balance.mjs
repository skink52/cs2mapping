// sim_balance.mjs: balance in simulation. Runs a project's mock engine many times (seeded, in parallel), one round window per run
// with the real CONFIG, and reports round length, team win rate and kills by source against the targets in a small JSON config.
// Neutral fork of projects/monsoon-cs2/test/sim_balance.mjs.
//
// usage: node create/sim_balance.mjs <balance.json> [seeds=40] [players=32] [key=value ...]
//   key=value pairs are passed through to the mock (e.g. seconds=600, ttk=20, cfg.X=...), label=<text> goes in the header,
//   md=1 prints the table as markdown, jobs=<n> parallel runs (default CPUs - 2, 2..10),
//   seed0=<n> first seed (default seedBase; seeds are seed0 + 7 i): a second seed set to check a tuning on
// balance.json (paths relative to the JSON file's folder):
//   { "name": "mg_example",
//     "mock": "mock.mjs",                    // run as: node <mock> <players> <seconds> mode=balance json=1 seed=<n> [args] [pass-through]
//     "cwd": "..",                           // working folder for the mock
//     "seconds": 900, "seedBase": 101, "args": [],
//     "teams": { "2": "T", "3": "CT" },
//     "sources": ["rifle", "mortar"],        // kill sources reported (others are summed as "other")
//     "model": ["rifle"],                    // sources that come from the mock's stand-in fight, not the script (marked "(model)")
//     "noTarget": ["crash"],                 // sources reported but not held to the share band (accidents, not weapons)
//     "targets": { "win": [0.45, 0.55], "share": [0.03, 0.40], "roundSecs": [600, 1200] },   // any may be left out
//     "notes": ["printed under the table"] }
// The mock's last stdout line must be JSON with: seed, secs, winner (team number, 0 = draw), kills {t, ct} (or by team number),
// killsBy {source: n}, errors; optional roundSecs (when the game ends rounds itself), perf {avg, max}, and any numeric or list fields
// named in "extras": [{ "key": "flightLife", "label": "...", "stat": "median" | "mean" | "sum" }], and killsTeamBy {team: {source: n}}.
// Exit 1 when a run crashed or reported errors. One standard error of a win rate over 40 seeds is ~8 points: decide on 40-60.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const argv = process.argv.slice(2);
if (!argv[0] || /^(-h|--help)$/.test(argv[0])) { console.log('usage: node create/sim_balance.mjs <balance.json> [seeds=40] [players=32] [key=value ...]'); process.exit(2); }
const cfgPath = path.resolve(argv[0]), base = path.dirname(cfgPath), C = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
const rest = argv.slice(1), pos = rest.filter((a) => !a.includes('=')), opt = Object.fromEntries(rest.filter((a) => a.includes('=')).map((a) => { const i = a.indexOf('='); return [a.slice(0, i), a.slice(i + 1)]; }));
const SEEDS = +(pos[0] || 40), N = +(pos[1] || 32), SECS = +(opt.seconds || C.seconds || 600);
const pass = Object.entries(opt).filter(([k]) => !['seconds', 'label', 'md', 'jobs', 'seed0'].includes(k)).map(([k, v]) => k + '=' + v);
const mock = path.resolve(base, C.mock), cwd = path.resolve(base, C.cwd || '.');
const SRC = C.sources || [], MODEL = new Set(C.model || []), TG = C.teams || { 2: 'T', 3: 'CT' }, TGT = C.targets || {};

function run(seed) {
  return new Promise((resolve) => {
    const args = [mock, String(N), String(SECS), 'mode=balance', 'json=1', 'seed=' + seed, ...(C.args || []), ...pass];
    const ch = spawn(process.execPath, args, { cwd, stdio: ['ignore', 'pipe', 'pipe'] });
    let out = '', err = '';
    ch.stdout.on('data', (d) => { out += d; }); ch.stderr.on('data', (d) => { err += d; });
    ch.on('close', () => { try { resolve(JSON.parse(out.trim().split('\n').pop())); } catch (e) { resolve({ seed, crash: (err || out).slice(-400) }); } });
  });
}
async function pool(jobs, width) { const res = new Array(jobs.length); let i = 0; await Promise.all(Array.from({ length: width }, async () => { while (i < jobs.length) { const k = i++; res[k] = await jobs[k](); if ((k + 1) % 10 === 0) console.error('sim_balance: ' + (k + 1) + ' / ' + jobs.length + ' runs started and done in order'); } })); return res; }
const q = (a, f) => { if (!a.length) return NaN; const s = a.slice().sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor(s.length * f))]; };
const mean = (a) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : NaN);
const mm = (s) => (Number.isFinite(s) ? Math.floor(s / 60) + ':' + ('0' + Math.round(s % 60)).slice(-2) : '-');
const pc = (x) => (Number.isFinite(x) ? (x * 100).toFixed(0) + ' %' : '-');
const killsOf = (r, team) => (r.kills ? (r.kills[team] ?? r.kills[TG[team] && TG[team].toLowerCase()] ?? 0) : 0);

const t0 = Date.now();
const width = +(opt.jobs || Math.max(2, Math.min(10, os.cpus().length - 2)));
const res = await pool(Array.from({ length: SEEDS }, (_, i) => () => run(+(opt.seed0 || C.seedBase || 101) + i * 7)), width);
const bad = res.filter((r) => r.crash || r.errors), ok = res.filter((r) => !r.crash);
const teams = Object.keys(TG).map(Number), wins = Object.fromEntries([...teams, 0].map((t) => [t, 0]));
for (const r of ok) wins[r.winner] = (wins[r.winner] || 0) + 1;
const decided = teams.reduce((a, t) => a + wins[t], 0), first = teams[0];
const winRate = decided ? wins[first] / decided : NaN;
const kills = {}; let total = 0, other = 0;
for (const r of ok) for (const [k, v] of Object.entries(r.killsBy || {})) { if (SRC.includes(k)) { kills[k] = (kills[k] || 0) + v; total += v; } else other += v; }
const share = Object.fromEntries(SRC.map((k) => [k, (kills[k] || 0) / Math.max(1, total)]));
const rs = ok.map((r) => r.roundSecs ?? r.secs);
const margin = ok.map((r) => Math.abs(killsOf(r, teams[0]) - killsOf(r, teams[1])));
const rows = {
  runs: ok.length + ' (' + bad.length + ' crashed or with errors)',
  'round length min / p25 / median / p75 / max': [q(rs, 0), q(rs, 0.25), q(rs, 0.5), q(rs, 0.75), q(rs, 1)].map(mm).join(' / ') + (ok.some((r) => r.roundSecs !== undefined) ? '' : '  (the window simulated: the game does not end rounds itself)'),
  [TG[teams[0]] + ' wins : ' + TG[teams[1]] + ' wins : draws']: wins[teams[0]] + ' : ' + wins[teams[1]] + ' : ' + wins[0],
  [TG[first] + ' win rate (decided)']: pc(winRate) + (decided ? '  (+-' + (100 * Math.sqrt(winRate * (1 - winRate) / decided)).toFixed(0) + ' one SE)' : ''),
  ['kills per round ' + TG[teams[0]] + ' / ' + TG[teams[1]] + ' (mean), margin median']: mean(ok.map((r) => killsOf(r, teams[0]))).toFixed(0) + ' / ' + mean(ok.map((r) => killsOf(r, teams[1]))).toFixed(0) + ', ' + q(margin, 0.5),
  'kills by source': SRC.map((k) => k + ' ' + pc(share[k]) + (MODEL.has(k) ? ' (model)' : '')).join(', '),
  'other deaths (not in the list)': pc(other / Math.max(1, total + other)),
};
if (ok.some((r) => r.killsTeamBy)) for (const t of teams) {          // optional: the mock's kills by source for each side
  const by = {}; for (const r of ok) for (const [k, n] of Object.entries((r.killsTeamBy || {})[t] || {})) by[k] = (by[k] || 0) + n;
  rows['kills per run by ' + TG[t] + ', by source (mean)'] = SRC.map((k) => k + ' ' + ((by[k] || 0) / ok.length).toFixed(1)).join(', ');
}
for (const e of C.extras || []) {
  const vals = ok.flatMap((r) => (Array.isArray(r[e.key]) ? r[e.key] : r[e.key] !== undefined ? [r[e.key]] : []));
  const v = e.stat === 'median' ? q(vals, 0.5) + ' (p25 ' + q(vals, 0.25) + ', p75 ' + q(vals, 0.75) + ')' : e.stat === 'sum' ? vals.reduce((a, b) => a + b, 0) : mean(vals).toFixed(1);
  rows[e.label || e.key] = v;
}
if (ok.some((r) => r.perf)) rows['script ms/tick avg, worst max (mock, runs in parallel)'] = mean(ok.map((r) => r.perf.avg)).toFixed(3) + ', ' + Math.max(...ok.map((r) => r.perf.max)).toFixed(1);
rows['wall time'] = ((Date.now() - t0) / 1000).toFixed(0) + ' s, ' + width + ' at once';

const verdicts = [];
const v = (name, good, got) => verdicts.push((good ? 'ok   ' : 'MISS ') + name + ' (' + got + ')');
const pct = (a) => a.map((x) => Math.round(x * 100)).join('-');
if (TGT.win) v(TG[first] + ' win rate ' + pct(TGT.win) + ' %', winRate >= TGT.win[0] && winRate <= TGT.win[1], pc(winRate));
if (TGT.roundSecs) v('round length median ' + TGT.roundSecs.map(mm).join('-'), q(rs, 0.5) >= TGT.roundSecs[0] && q(rs, 0.5) <= TGT.roundSecs[1], mm(q(rs, 0.5)));
if (TGT.share) for (const k of SRC.filter((x) => !(C.noTarget || []).includes(x))) v('kills by ' + k + ' in ' + pct(TGT.share) + ' %' + (MODEL.has(k) ? ' (model)' : ''), share[k] >= TGT.share[0] && share[k] <= TGT.share[1], pc(share[k]));
for (const b of bad.slice(0, 3)) verdicts.push('ERR  seed ' + b.seed + ': ' + (b.crash || (b.fails || []).join('; ')));

console.log((C.name || 'balance') + ': ' + SEEDS + ' seeds, ' + N + ' players, ' + SECS + ' s per run' + (opt.label ? ' [' + opt.label + ']' : '') + (pass.length ? '  pass-through: ' + pass.join(' ') : ''));
if (opt.md) { console.log('| | |\n|---|---|'); for (const [k, val] of Object.entries(rows)) console.log('| ' + k + ' | ' + val + ' |'); }
else for (const [k, val] of Object.entries(rows)) console.log('  ' + k.padEnd(58) + val);
for (const s of verdicts) console.log(s);
for (const n of C.notes || []) console.log('note: ' + n);
process.exit(verdicts.some((s) => s.startsWith('ERR')) ? 1 : 0);
