// A kill counts once wherever it is shown (24 Nov 2026, skink52: 13 kills, all against AI, and the round end said 26). sum.kills
// already counts AI kills; sum.pveKills and sum.bossKills are subsets of it, kept for XP and stats, never added to it for display.
// usage: node test/kill_count.cjs     (needs build/core_test.cjs: create/build/build.mjs)
const { makeGame } = require('./lib.cjs');
let fails = 0, n = 0;
const ok = (c, name, info) => { n++; if (!c) { fails++; console.log('FAIL ' + name + (info !== undefined ? ': ' + info : '')); } };
const DT = 1 / 64;
const g = makeGame({ seed: 7, cfg: { round: { tb: 600, cq: 600, sk: 600, so: 600, kh: 600, ctf: 600, warmup: 1, podium: 3 } } });
g.setMode('tb', 0);
g.startRound(0);
g.addPlayer(0, { team: 2, human: true, name: 'ME', pilot: null });
const npcs = []; for (let i = 0; i < 3; i++) { const m = g.addNpc(3, 'normal', true); if (m) npcs.push(typeof m === 'object' ? m.slot : m); }
ok(npcs.length === 3, 'three AI mechs added', npcs.length);
let t = 0, end = null;
const step = (secs) => { for (let k = 0; k < secs * 64; k++) { g.tick(DT, t += DT); for (const e of g.events) if (e.t === 'round_end') end = e; g.events.length = 0; } };
step(4);   // warmup over, everyone spawned
ok(g.match.phase === 'running', 'round running', g.match.phase);
for (const s of npcs) { const m = g.mechs.get(s); if (m && !m.alive) step(1); g.killMech(s, 0); }
const me = g.mechs.get(0);
ok(me.sum.kills === 3, 'three kills counted', me.sum.kills);
ok(me.sum.pveKills === 3, 'all three are AI kills (pveKills, a subset)', me.sum.pveKills);
ok(g.pilotSummary(0).kills === 3, 'pilot summary (garage K/D/A, round end card): 3', g.pilotSummary(0).kills);
g.endRound(true);
step(0.1);
const mine = end && (end.podiumInfo || []).find((c) => c.slot === 0);
ok(!!mine, 'the player is on the podium');
ok(mine && mine.kills === 3, 'podium card kills: 3, not doubled', mine && mine.kills);
console.log((fails ? 'FAIL ' + fails + ' of ' : 'ok: ') + n + ' checks (kills counted once)');
process.exit(fails ? 1 : 0);
