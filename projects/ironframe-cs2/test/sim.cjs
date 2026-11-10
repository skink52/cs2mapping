// AI vs AI soak on the pure core. usage: node test/sim.cjs [mechs=64] [seconds=300] [mode=tb|cq|sk|so|all] [seed=N]
// Fails (exit 1) on exceptions, NaN, out-of-bounds, a mech stuck > 10 s, an unfinished round, pool leaks or the trace budget.
// The round length is set to the run length, so every round must end by score or time inside it.
const { makeGame } = require('./lib.cjs');
const N = +(process.argv[2] || 64), SECS = +(process.argv[3] || 300), MODE = process.argv[4] || 'all';
const SEED = +(String(process.argv[5] || '').replace('seed=', '') || 7);
const modes = MODE === 'all' ? ['tb', 'cq', 'sk', 'so', 'kh', 'ctf'] : [MODE];
let failed = false;
const fail = (msg) => { failed = true; console.log('FAIL ' + msg); };
const DT = 1 / 64;
const summary = [];
for (const mode of modes) {
  const g = makeGame({ seed: SEED, cfg: { round: { tb: SECS - 5, cq: SECS - 5, sk: SECS - 5, so: SECS - 5, kh: SECS - 5, ctf: SECS - 5, warmup: 2, podium: 3 } } });
  g.setMode(mode, 0);
  // pawn bots (CS2 bots, human:false) fill the lobby; Sortie: 4 of them plus the core's ally fill and enemy waves
  const pawnBots = mode === 'so' ? 4 : mode === 'sk' ? Math.min(N, 16) : N;
  g.startRound(0);
  for (let s = 0; s < pawnBots; s++) g.addPlayer(s, { team: s % 2 ? 3 : 2, human: false, name: 'bot' + s, pilot: null });
  const times = [], stuck = new Map(), B = g.bullets, A = g.arena.bounds;
  let t = 0, ended = false, maxBullets = 0, maxMsl = 0, kills = 0, nanAt = null, oob = 0, worstStuck = 0, worstSlot = -1, peakMechs = 0;
  const events = {};
  const tr0 = g.stats.traces, mt0 = g.stats.mechTicks;
  for (let k = 0; k < SECS * 64 && !ended; k++) {
    const s0 = performance.now();
    try { g.tick(DT, t); } catch (err) { fail(mode + ' exception at ' + t.toFixed(2) + 's: ' + (err.stack || err)); break; }
    times.push(performance.now() - s0);
    t += DT;
    for (const e of g.events) { events[e.t] = (events[e.t] || 0) + 1; if (e.t === 'kill') kills++; if (e.t === 'round_end') ended = true; }
    g.events.length = 0;
    maxBullets = Math.max(maxBullets, B.count);
    let ms = 0; for (const m of g.missiles) if (m.alive) ms++; maxMsl = Math.max(maxMsl, ms);
    peakMechs = Math.max(peakMechs, g.alive.length);
    if ((k & 15) === 0) for (const m of g.mechs.values()) {
      if (!m.alive) { stuck.delete(m.slot); continue; }
      for (const v of [m.pos.x, m.pos.y, m.pos.z, m.vel.x, m.vel.y, m.vel.z, m.ap, m.en, m.stagger, m.torsoYaw]) if (!Number.isFinite(v)) nanAt = nanAt || (mode + ' slot ' + m.slot + ' at ' + t.toFixed(2));
      if (m.pos.x < A.min[0] - 1 || m.pos.x > A.max[0] + 1 || m.pos.y < A.min[1] - 1 || m.pos.y > A.max[1] + 1 || m.pos.z > A.max[2] + 1) oob++;
      const st = stuck.get(m.slot) || { x: m.pos.x, y: m.pos.y, t };
      if (Math.hypot(m.pos.x - st.x, m.pos.y - st.y) > 100 || m.wishLen < 0.3 || m.braced) { st.x = m.pos.x; st.y = m.pos.y; st.t = t; }
      if (t - st.t > worstStuck) { worstStuck = t - st.t; worstSlot = m.slot; }
      stuck.set(m.slot, st);
    }
  }
  const sorted = times.slice().sort((a, b) => a - b), q = (p) => sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))] || 0;
  const tpm = (g.stats.traces - tr0) / Math.max(1, g.stats.mechTicks - mt0);
  const M = g.match;
  const score = mode === 'ctf' ? 'captures T ' + M.scores[2] + ' CT ' + M.scores[3] + ', flags ' + [2, 3].map((t) => M.flags[t].state).join('/') : mode === 'kh' ? 'hill T ' + M.scores[2] + ' CT ' + M.scores[3] + ' at ' + (M.points[0] ? M.points[0].id : '-') : mode === 'cq' ? 'tickets T ' + Math.round(M.tickets[2]) + ' CT ' + Math.round(M.tickets[3]) + ', points ' + M.points.map((p) => p.id + ':' + p.owner).join(' ')
    : mode === 'so' ? 'wave ' + M.wave + '/' + M.waves + ', beacon loss ' + M.beaconLoss.toFixed(1) + ' s' : 'score T ' + M.scores[2] + ' CT ' + M.scores[3] + ' / ' + M.killTarget;
  console.log(`${mode}: peak ${peakMechs} live mechs, ${t.toFixed(0)} s, ${ended ? 'ended' : 'NOT ENDED'}, winner ${M.winner} | ${score} | kills ${kills}, spawns ${g.stats.spawns}, missiles ${g.stats.missiles} (dodged ${g.stats.missileDodges}), unstuck ${g.stats.aiUnstuck}`);
  console.log(`   ms/tick p50 ${q(0.5).toFixed(3)} p99 ${q(0.99).toFixed(3)} max ${q(1).toFixed(2)} | traces/mech/tick ${tpm.toFixed(3)} | peak bullets ${maxBullets} (dropped ${B.dropped}), missiles ${maxMsl} | worst stuck ${worstStuck.toFixed(1)} s (slot ${worstSlot})`);
  console.log(`   events ${JSON.stringify(events)}`);
  if (!ended) fail(mode + ': the round did not finish');
  if (nanAt) fail('NaN: ' + nanAt);
  if (oob) fail(mode + ': out of bounds samples ' + oob);
  if (worstStuck > 10) fail(mode + ': a mech was stuck ' + worstStuck.toFixed(1) + ' s');
  if (tpm > g.cfg.stats.traceBudget) fail(mode + ': trace budget ' + tpm.toFixed(2) + ' > ' + g.cfg.stats.traceBudget);
  if (kills === 0) fail(mode + ': no kills at all');
  // pools drain after the podium (no new fire; everything in flight lands or expires)
  for (let k = 0; k < 64 * 10; k++) { g.tick(DT, t); t += DT; g.events.length = 0; }
  const leftM = g.missiles.filter((m) => m.alive).length, leftBeam = g.beams.filter((b) => b.alive).length;
  if (B.count !== 0 || leftM || leftBeam || B.count + B.nfree !== B.n) fail(mode + `: pool leak (bullets ${B.count}, free ${B.nfree}/${B.n}, missiles ${leftM}, beams ${leftBeam})`);
  summary.push(`${mode} p50 ${q(0.5).toFixed(3)} p99 ${q(0.99).toFixed(3)} ms, ${tpm.toFixed(2)} traces/mech/tick`);
}
console.log('summary: ' + summary.join(' | '));
console.log(failed ? 'sim: FAILED' : 'sim: ok');
process.exit(failed ? 1 : 0);
