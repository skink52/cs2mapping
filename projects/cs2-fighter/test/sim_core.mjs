// Headless soak test of the core: CPU-only matches in every mode, checking for
// exceptions, NaNs, stuck states and that rounds and matches actually finish.
import { Game, CHARACTERS, SIM_HZ } from "../dist/core_node.mjs";

function finiteParts(g) {
  for (const f of g.fighters) {
    if (!f.onStage) continue;
    for (const p of f.parts) {
      if (p.hidden) continue;
      for (const k of ["x", "y", "ang", "len", "r", "depth"]) {
        if (!Number.isFinite(p[k])) throw new Error(`NaN part ${k} seat ${f.seat} state ${f.state} move ${f.move && f.move.id}`);
      }
    }
    for (const k of ["x", "y", "vx", "vy", "hp"]) if (!Number.isFinite(f[k])) throw new Error(`NaN fighter ${k} seat ${f.seat}`);
  }
}

function run(mode, cpus, seconds, seed) {
  const g = new Game({ seed, halfWidth: 360, cfg: { mode, needHuman: false, cpuLevel: 2 } });
  g.forceCpuMatch = true;
  for (let i = 0; i < cpus; i++) g.addCpu();
  const stats = { matches: 0, rounds: 0, kos: 0, hits: 0, blocks: 0, specials: 0, throws: 0, phases: {}, states: {}, moves: {} };
  let lastPhase = "", stuck = 0, lastHp = "";
  const frames = seconds * SIM_HZ;
  for (let fr = 0; fr < frames; fr++) {
    g.step();
    finiteParts(g);
    for (const e of g.events) {
      if (e.t === "snd") {
        if (e.id === "hit" || e.id === "heavy") stats.hits++;
        if (e.id === "block") stats.blocks++;
        if (e.id === "special") stats.specials++;
        if (e.id === "ko") stats.kos++;
      }
    }
    g.events.length = 0;
    if (g.phase !== lastPhase) {
      stats.phases[g.phase] = (stats.phases[g.phase] || 0) + 1;
      if (g.phase === "matchEnd") stats.matches++;
      if (g.phase === "roundEnd") stats.rounds++;
      lastPhase = g.phase;
    }
    for (const f of g.fighters) if (f.active) {
      stats.states[f.state] = (stats.states[f.state] || 0) + 1;
      if (f.move && f.mf === 1) { stats.moves[f.move.id] = (stats.moves[f.move.id] || 0) + 1; if (f.move.id === "throw") stats.throws++; }
    }
    // stuck detection: in fight, hp unchanged for 40s
    const hpKey = g.fighters.map((f) => f.hp).join(",");
    if (g.phase === "fight") { if (hpKey === lastHp) stuck++; else stuck = 0; }
    lastHp = hpKey;
    if (stuck > SIM_HZ * 40) throw new Error(`stuck in fight: ${g.fighters.map((f) => f.state + "@" + f.x.toFixed(0)).join(" ")}`);
  }
  return stats;
}

let fail = false;
for (const [mode, n] of [["duel", 2], ["duel", 4], ["teams", 4], ["teams", 3], ["ffa", 4], ["ffa", 3]]) {
  for (const seed of [1, 2, 3]) {
    try {
      const st = run(mode, n, 240, seed * 7919);
      console.log(`${mode} x${n} seed${seed}: matches ${st.matches} rounds ${st.rounds} KOs ${st.kos} hits ${st.hits} blocks ${st.blocks} specials ${st.specials} throws ${st.throws}`);
      if (seed === 1 && mode === "duel" && n === 2) console.log("  moves:", JSON.stringify(st.moves), "\n  states:", JSON.stringify(st.states));
      if (st.matches < 1) { console.log("  !! no match finished"); fail = true; }
    } catch (e) {
      fail = true;
      console.log(`${mode} x${n} seed${seed}: ERROR ${e.stack}`);
    }
  }
}
process.exit(fail ? 1 : 0);
