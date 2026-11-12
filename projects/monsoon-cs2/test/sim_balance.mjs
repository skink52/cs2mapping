// Feel and balance in simulation: many seeded matches of the real script on the stand-in engine (test/mock.mjs mode=balance), one
// full round each with the real CONFIG, and a report against the design targets.
//   node test/sim_balance.mjs [seeds=40] [players=32] [key=value ...]
//     set=bots|mixed|both   32 bots (the script's AI flies, guns and crews) / 22 humans driven by the test + 10 bots / both (default)
//     cfg.<path>=<json>     CONFIG override passed to every match, e.g. cfg.HELI.ACCEL=0.45 cfg.CONQUEST.NEUTRAL_FIRST=true
//     ttk=<s> engage=<u> helihits=<n>   the infantry stand-in's rates (see mock.mjs FIGHT)
//     label=<text>          printed in the header        md=1   print the table as markdown
//     fwd=<0-1>             share of the mixed set's human deploys made at the front flag (default 0 = always the base, as before; 0.6 = a forward-deploying crowd)
//     seed0=<n>             first seed (default 101; seeds are seed0 + 7 i): a second seed set to check a tuning on
//     script=<file>         run that built script (e.g. out/review3/before_review3.js) instead of building src/
// What is real and what is assumed: helicopters, their guns and rockets, artillery, emplaced guns, AT rockets, flags, tickets and the
// AI roles are the script's own code. The infantry fight is a rate model (CS2's bots and players cannot be run here), and in "mixed"
// the humans are the test's drivers. Numbers that depend mostly on the model are marked (model).
import { spawn } from 'node:child_process';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2), pos = argv.filter((a) => !a.includes('=')), opt = Object.fromEntries(argv.filter((a) => a.includes('=')).map((a) => { const i = a.indexOf('='); return [a.slice(0, i), a.slice(i + 1)]; }));
const SEEDS = +(pos[0] || 40), N = +(pos[1] || 32);
const pass = Object.entries(opt).filter(([k]) => k.startsWith('cfg.') || k.startsWith('move.') || k.startsWith('spawnflip.') || ['ttk', 'engage', 'helihits', 'script', 'fwd'].includes(k)).map(([k, v]) => k + '=' + v);
const sets = (opt.set || 'both') === 'both' ? ['bots', 'mixed'] : [opt.set];
const SRC = ['rifle', 'mg', 'at', 'heligun', 'helirocket', 'arty', 'mount'];

function run(set, seed) {
  return new Promise((resolve) => {
    const args = [path.join(here, 'mock.mjs'), String(N), '1500', 'mode=balance', 'json=1', 'seed=' + seed, 'humans=' + (set === 'bots' ? 0 : Math.round(N * 22 / 32)), 'tag=_bal_' + set + seed, ...pass];
    const ch = spawn(process.execPath, args, { stdio: ['ignore', 'pipe', 'pipe'] });
    let out = '', err = '';
    ch.stdout.on('data', (d) => { out += d; }); ch.stderr.on('data', (d) => { err += d; });
    ch.on('close', () => { try { resolve(JSON.parse(out.trim().split('\n').pop())); } catch (e) { resolve({ seed, crash: (err || out).slice(0, 400) }); } });
  });
}
async function pool(jobs, width) { const res = new Array(jobs.length); let i = 0; await Promise.all(Array.from({ length: width }, async () => { while (i < jobs.length) { const k = i++; res[k] = await jobs[k](); } })); return res; }
const q = (a, f) => { if (!a.length) return NaN; const s = a.slice().sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor(s.length * f))]; };
const mean = (a) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : NaN);
const mm = (s) => (Number.isFinite(s) ? Math.floor(s / 60) + ':' + ('0' + Math.round(s % 60)).slice(-2) : '-');
const pc = (x) => (Number.isFinite(x) ? (x * 100).toFixed(0) + ' %' : '-');

const rows = [];
const verdicts = [];
for (const set of sets) {
  const res = await pool(Array.from({ length: SEEDS }, (_, i) => () => run(set, +(opt.seed0 || 101) + i * 7)), Math.max(2, Math.min(10, os.cpus().length - 2)));
  const bad = res.filter((r) => r.crash || r.errors);
  const ok = res.filter((r) => !r.crash);
  const secs = ok.map((r) => r.secs), wins = { 2: 0, 3: 0, 0: 0 };
  for (const r of ok) wins[r.winner]++;
  const kills = {}; let total = 0, other = 0;
  for (const r of ok) for (const [k, v] of Object.entries(r.killsBy)) { if (SRC.includes(k)) { kills[k] = (kills[k] || 0) + v; total += v; } else other += v; }
  const lives = ok.flatMap((r) => r.heliLives);
  const flagCh = {}; for (const r of ok) for (const [k, v] of Object.entries(r.flagChanges)) (flagCh[k] = flagCh[k] || []).push(v);
  const margin = ok.map((r) => Math.abs(r.tickets.t - r.tickets.ct));
  const sum = (f) => ok.reduce((a, r) => a + f(r), 0);
  const decided = wins[2] + wins[3], tRate = decided ? wins[2] / decided : NaN;
  const inBand = secs.filter((s) => s >= 720 && s <= 1200).length / Math.max(1, secs.length);
  const share = Object.fromEntries(SRC.map((k) => [k, (kills[k] || 0) / Math.max(1, total)]));
  const dead = Object.entries(flagCh).filter(([, a]) => mean(a) < 2 || a.filter((v) => v < 1).length / a.length > 0.1).map(([k]) => k);
  const ai = (k) => mean(ok.map((r) => (r.ai[k].t + r.ai[k].ct) / 2));
  const R = {
    set, matches: ok.length, crashed: bad.length,
    'round length min / p25 / median / p75 / max': [q(secs, 0), q(secs, 0.25), q(secs, 0.5), q(secs, 0.75), q(secs, 1)].map(mm).join(' / '),
    'rounds inside 12-20 min': pc(inBand), 'rounds ended by the clock': pc(secs.filter((s) => s >= 1199).length / Math.max(1, secs.length)),
    'T wins : CT wins : draws': wins[2] + ' : ' + wins[3] + ' : ' + wins[0], 'T win rate (decided)': pc(tRate),
    'ticket margin median': q(margin, 0.5),
    'flag changes per round a / b / c / d / e (mean)': ['a', 'b', 'c', 'd', 'e'].map((k) => mean(flagCh[k] || []).toFixed(1)).join(' / '),
    'dead flags (mean under 2 changes, or never taken in 10 % of rounds)': dead.join(' ') || 'none',
    'flag held by T / CT, share of the round a b c d e': ['a', 'b', 'c', 'd', 'e'].map((k) => pc(mean(ok.map((r) => (r.own && r.own[k] ? r.own[k].t : NaN)))) + '/' + pc(mean(ok.map((r) => (r.own && r.own[k] ? r.own[k].ct : NaN))))).join(' '),
    'tickets lost per round T / CT: deaths, bleed': (sum((r) => r.deathsOn ? r.deathsOn.t : 0) / ok.length).toFixed(0) + ' / ' + (sum((r) => r.deathsOn ? r.deathsOn.ct : 0) / ok.length).toFixed(0) + ', ' +
      (sum((r) => r.bleedOn ? r.bleedOn.t : 0) / ok.length).toFixed(0) + ' / ' + (sum((r) => r.bleedOn ? r.bleedOn.ct : 0) / ok.length).toFixed(0),
    'captures per round by T / CT a b c d e (mean)': ['a', 'b', 'c', 'd', 'e'].map((k) => mean(ok.map((r) => (r.capsBy && r.capsBy[k] ? r.capsBy[k].t : NaN))).toFixed(1) + '/' + mean(ok.map((r) => (r.capsBy && r.capsBy[k] ? r.capsBy[k].ct : NaN))).toFixed(1)).join(' '),
    'rounds in which both sides took it a b c d e': ['a', 'b', 'c', 'd', 'e'].map((k) => pc(ok.filter((r) => r.capsBy && r.capsBy[k] && r.capsBy[k].t > 0 && r.capsBy[k].ct > 0).length / Math.max(1, ok.length))).join(' '),
    'rounds in which it was fought over (both took it, or both inside 10 s+) a b c d e': ['a', 'b', 'c', 'd', 'e'].map((k) => pc(ok.filter((r) => (r.capsBy && r.capsBy[k] && r.capsBy[k].t > 0 && r.capsBy[k].ct > 0) || (r.contest && r.contest[k] >= 10)).length / Math.max(1, ok.length))).join(' '),
    'contested seconds per round a b c d e (mean)': ['a', 'b', 'c', 'd', 'e'].map((k) => mean(ok.map((r) => (r.contest ? r.contest[k] || 0 : NaN))).toFixed(0)).join(' / '),
    'kills by source (model: rifle, mg)': SRC.map((k) => k + ' ' + pc(share[k])).join(', '), 'other deaths (falls, crashes by own error)': pc(other / Math.max(1, total + other)),
    'deaths per round, T side by source': SRC.concat(['crash', 'other']).map((k) => k + ' ' + (sum((r) => ((r.killsOn || {})[2] || {})[k] || 0) / ok.length).toFixed(0)).join(', '),
    'deaths per round, CT side by source': SRC.concat(['crash', 'other']).map((k) => k + ' ' + (sum((r) => ((r.killsOn || {})[3] || {})[k] || 0) / ok.length).toFixed(0)).join(', '),
    'deaths per player-minute (model)': (sum((r) => r.deaths) / Math.max(1, sum((r) => r.secs * r.players / 60))).toFixed(2),
    'helicopter airframe life p25 / median / p75 (s), lost per round': [q(lives, 0.25), q(lives, 0.5), q(lives, 0.75)].join(' / ') + ', ' + (sum((r) => r.heliLost) / ok.length).toFixed(1),
    'helicopters lost T : CT': sum((r) => r.heliLostTeam.t) + ' : ' + sum((r) => r.heliLostTeam.ct),
    'helicopters lost to': Object.entries(ok.reduce((a, r) => { for (const [k, v] of Object.entries(r.heliLostBy)) a[k] = (a[k] || 0) + v; return a; }, {})).sort((a, b) => b[1] - a[1]).map(([k, v]) => k + ' ' + v).join(', '),
    'artillery: rounds fired / round, men hit per round fired': (sum((r) => r.fired) / ok.length).toFixed(0) + ', ' + (sum((r) => r.shellHits) / Math.max(1, sum((r) => r.shells))).toFixed(2),
    'artillery: fire missions / round, men hit per mission round': (sum((r) => r.missions) / ok.length).toFixed(1) + ', ' + (sum((r) => r.missionShells) ? (sum((r) => r.missionHits) / sum((r) => r.missionShells)).toFixed(2) : '-'),
    'guns knocked out per round': (sum((r) => r.gunsDisabled) / ok.length).toFixed(1),
    'AI role uptime pilot flying / gunner seated / crew at gun': set === 'bots' ? [ai('pilot'), ai('gunner'), ai('crew')].map(pc).join(' / ') : 'n/a (enough humans)',
    'AI pilot time by state, both sides (share of side-seconds)': set === 'bots' ? (() => { const t = {}; for (const r of ok) for (const [k, v] of Object.entries(r.pilotWhy || {})) t[k] = (t[k] || 0) + v; const n = Object.values(t).reduce((a, b) => a + b, 0) || 1; return Object.entries(t).sort((a, b) => b[1] - a[1]).map(([k, v]) => k + ' ' + pc(v / n)).join(', '); })() : 'n/a',
    'script ms/tick avg, worst max': mean(ok.map((r) => r.perf.avg)).toFixed(3) + ', ' + Math.max(...ok.map((r) => r.perf.max)).toFixed(1),
  };
  rows.push(R);
  const v = (name, good, got) => verdicts.push((good ? 'ok   ' : 'MISS ') + set + ': ' + name + ' (' + got + ')');
  v('round length median in 12-20 min', q(secs, 0.5) >= 720 && q(secs, 0.5) <= 1200, mm(q(secs, 0.5)));
  v('T win rate 45-55 %', tRate >= 0.45 && tRate <= 0.55, pc(tRate));
  v('no dead flag', !dead.length, dead.join(' ') || 'none');
  for (const k of SRC) if (!(set === 'bots' && k === 'at' && !share[k])) v('kills by ' + k + ' in 3-40 %', share[k] >= 0.03 && share[k] <= 0.4, pc(share[k]));
  v('helicopter life median 60-180 s', q(lives, 0.5) >= 60 && q(lives, 0.5) <= 180, q(lives, 0.5) + ' s');
  if (set === 'bots') v('AI roles up at least half the time', ai('pilot') >= 0.5 && ai('gunner') >= 0.5 && ai('crew') >= 0.5, [ai('pilot'), ai('gunner'), ai('crew')].map(pc).join(' / '));
  for (const b of bad.slice(0, 3)) verdicts.push('ERR  ' + set + ' seed ' + b.seed + ': ' + (b.crash || (b.fails || []).join('; ')));
}
console.log('mg_monsoon balance: ' + SEEDS + ' seeds x ' + sets.join(' + ') + ', ' + N + ' players' + (opt.label ? ' [' + opt.label + ']' : '') + (pass.length ? '  overrides: ' + pass.join(' ') : ''));
const keys = Object.keys(rows[0]).filter((k) => k !== 'set');
if (opt.md) { console.log('| | ' + rows.map((r) => r.set).join(' | ') + ' |\n|---|' + rows.map(() => '---').join('|') + '|'); for (const k of keys) console.log('| ' + k + ' | ' + rows.map((r) => r[k]).join(' | ') + ' |'); }
else for (const k of keys) console.log('  ' + k.padEnd(62) + rows.map((r) => String(r[k]).padEnd(46)).join(''));
for (const s of verdicts) console.log(s);
process.exit(verdicts.some((s) => s.startsWith('ERR')) ? 1 : 0);
