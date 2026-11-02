// CPU vs CPU balance sweep: every pairing, both sides, every CPU level.
// Usage: node test/balance.mjs [seconds per run] [seeds] > out.json
import { Game, CHARACTERS, SIM_HZ } from "../dist/core_node.mjs";
const SECS = +process.argv[2] || 600, SEEDS = +process.argv[3] || 3;
const N = CHARACTERS.length;
const res = [];
function run(a, b, level, seed) {
  const g = new Game({ seed, halfWidth: 360, cfg: { mode: "duel", needHuman: false, cpuLevel: level } });
  g.forceCpuMatch = true;
  g.addCpu(0); g.addCpu(1);
  g.fighters[0].setCharacter(a); g.fighters[1].setCharacter(b);
  g.forceStart();
  const st = { a, b, level, seed, rounds: 0, winA: 0, winB: 0, draws: 0, ko: 0, time: 0, dmgA: 0, dmgB: 0, framesFight: 0, perfA: 0, perfB: 0, moveHitsA: {}, moveHitsB: {}, bestA: 0, bestB: 0, matches: 0 };
  let lastPhase = g.phase, hp0 = [0, 0];
  const lastAtt = [null, null];
  for (let fr = 0; fr < SECS * SIM_HZ; fr++) {
    const before = [g.fighters[0].hp, g.fighters[1].hp];
    const mv = [g.fighters[0].move && g.fighters[0].move.id, g.fighters[1].move && g.fighters[1].move.id];
    g.step();
    if (g.phase === "fight") st.framesFight++;
    for (let s = 0; s < 2; s++) {
      const d = before[s] - g.fighters[s].hp;
      if (d > 0) { const att = 1 - s; const key = mv[att] || (g.fighters[att].move && g.fighters[att].move.id) || "proj/other"; const tab = att === 0 ? st.moveHitsA : st.moveHitsB; tab[key] = (tab[key] || 0) + d; if (att === 0) st.dmgA += d; else st.dmgB += d; }
    }
    for (const e of g.events) if (e.t === "perfect") { if (e.seat === 0) st.perfA++; else st.perfB++; }
    g.events.length = 0;
    if (g.phase !== lastPhase) {
      if (g.phase === "roundEnd") {
        st.rounds++;
        const [f0, f1] = g.fighters;
        const w = g.roundWinner;
        if (w === f0.team) st.winA++; else if (w === f1.team) st.winB++; else st.draws++;
        if (f0.ko || f1.ko) st.ko++; else st.time++;
      }
      if (g.phase === "matchEnd") st.matches++;
      lastPhase = g.phase;
    }
  }
  st.bestA = g.bestCombo[0]; st.bestB = g.bestCombo[1];
  return st;
}
const LV = process.env.LEVEL !== undefined ? [+process.env.LEVEL] : [0, 1, 2];
for (const level of LV)
  for (let a = 0; a < N; a++) for (let b = 0; b < N; b++)
    for (let s = 1; s <= SEEDS; s++) res.push(run(a, b, level, s * 104729 + a * 31 + b * 7 + level));
console.log(JSON.stringify({ names: CHARACTERS.map((c) => c.name), res }));
