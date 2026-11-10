// Frame round robin: 1v1 AI duels for every player frame pair at one tier, both sides, N seeds. usage: node test/frames.cjs [seeds=2] [tier=normal] [loadout-suffix]
const fs = require('fs'), path = require('path');
const { C, makeGame, ROOT } = require('./lib.cjs');
const SEEDS = +(process.argv[2] || 2), TIER = process.argv[3] || 'normal', SUF = process.argv[4] || '101,101,0,0,301,401,501,601';
const DT = 1 / 64;
const P = C.PARTS, byId = new Map(P.parts.map((p) => [p.id, p]));

// one fight: mechs [{lo, tier, team}], placed in two lines `gap` apart; ends at the first kill (duel) or after `secs`
function fight(specs, seed, opts) {
  opts = opts || {};
  const g = makeGame({ seed, cfg: { round: { tb: 9999, warmup: 0, podium: 2 }, ai: { npcFill: false }, tb: { killMin: 999, killMax: 999 } } });
  g.setMode('tb', 0); g.startRound(0);
  specs.forEach((s, i) => {
    g.addPlayer(i, { team: s.team, human: false, name: 'b' + i, pilot: s.pilot || null });
    const c = g.setLoadout(i, s.lo); if (c) throw new Error('deny ' + c + ' ' + s.lo);
    C.IF_Ai.attach(g, g.mechs.get(i), s.tier || 'normal');
  });
  g.tick(DT, DT);
  const gap = opts.gap || 2600, per = { 2: 0, 3: 0 };
  for (const [i, s] of specs.entries()) {
    const m = g.mechs.get(i), k = per[s.team]++;
    m.pos.x = (s.team === 2 ? -1 : 1) * gap / 2 + (k % 2) * 200; m.pos.y = (k - 3.5) * 350; m.pos.z = g.nav.height(m.pos.x, m.pos.y) + 5;
    m.dropT = 0; m.onGround = true; m.protect = 0; m.vel.x = m.vel.y = m.vel.z = 0;
  }
  const dmg = new Map(), first = { t: -1, killer: -1, victim: -1 }, kills = { 2: 0, 3: 0 };
  let t = 0;
  const secs = opts.secs || 60;
  for (let k = 0; k < secs * 64; k++) {
    g.tick(DT, t += DT);
    for (const e of g.events) {
      if (e.t === 'damage' && e.attacker >= 0 && e.attacker !== e.victim) dmg.set(e.attacker, (dmg.get(e.attacker) || 0) + e.amount);
      if (e.t === 'kill') { if (first.t < 0) { first.t = t; first.killer = e.killer; first.victim = e.victim; } const vm = g.mechs.get(e.victim); if (vm) kills[vm.team === 2 ? 3 : 2]++; }
    }
    g.events.length = 0;
    if (opts.duel && first.t >= 0) break;
  }
  const apFrac = { 2: 0, 3: 0 };
  for (const m of g.mechs.values()) if (m.alive) apFrac[m.team] += m.ap / m.apMax;
  return { g, t, first, kills, dmg, apFrac };
}
function duel(loA, loB, tierA, tierB, seed, pilots) {
  const r = fight([{ lo: loA, tier: tierA, team: 2, pilot: pilots && pilots[0] }, { lo: loB, tier: tierB, team: 3, pilot: pilots && pilots[1] }], seed, { duel: true, secs: 60 });
  let win = 0;   // +1 A, -1 B, 0 draw
  if (r.first.t >= 0) win = r.first.killer === 0 ? 1 : r.first.killer === 1 ? -1 : (r.first.victim === 0 ? -1 : 1);
  else win = r.apFrac[2] > r.apFrac[3] + 0.05 ? 1 : r.apFrac[3] > r.apFrac[2] + 0.05 ? -1 : 0;
  return { win, ttk: r.first.t >= 0 ? r.t : null, dpsA: (r.dmg.get(0) || 0) / r.t, dpsB: (r.dmg.get(1) || 0) / r.t };
}
const t0 = Date.now();
const frames = P.parts.filter((p) => p.kind === 'frame' && !p.pve);
const n = frames.length, W = frames.map(() => 0), G = frames.map(() => 0), M = frames.map(() => frames.map(() => 0));
for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
  let sc = 0, cnt = 0;
  for (let s = 1; s <= SEEDS; s++) for (const swap of [0, 1]) {
    const a = frames[swap ? j : i].id + ',' + SUF, b = frames[swap ? i : j].id + ',' + SUF;
    const r = duel(a, b, TIER, TIER, s * 17 + i * 3 + j);
    const w = swap ? -r.win : r.win;   // + = frame i won
    sc += w > 0 ? 1 : w < 0 ? 0 : 0.5; cnt++;
  }
  M[i][j] = sc / cnt; M[j][i] = 1 - sc / cnt;
  W[i] += sc; W[j] += cnt - sc; G[i] += cnt; G[j] += cnt;
}
console.log('frame (id) win% vs the other ' + (n - 1) + ', tier ' + TIER + ', ' + SEEDS + ' seeds x 2 sides');
const rows = frames.map((f, i) => ({ f, w: W[i] / G[i] })).sort((a, b) => b.w - a.w);
for (const r of rows) console.log(('  ' + r.f.key).padEnd(14) + String(r.f.id).padStart(3) + '  ' + (100 * r.w).toFixed(0) + ' %  ' + (r.w > 0.6 ? 'HIGH' : r.w < 0.4 ? 'LOW' : ''));
if (process.env.MATRIX) for (let i = 0; i < n; i++) console.log(frames[i].key.padEnd(10) + M[i].map((x, j) => i === j ? '  - ' : String(Math.round(100 * x)).padStart(3) + ' ').join(''));
console.log('time ' + ((Date.now() - t0) / 1000).toFixed(0) + ' s');
if (process.env.JSON) console.log('JSON ' + JSON.stringify(Object.fromEntries(frames.map((f, i) => [f.id, W[i] / G[i]]))));
