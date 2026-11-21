// Round 4 finale, the clock runs out during it (docs/STATUS.md "Round 4 contract"). 4 humans + 4 bots, 20 s, zemap=map01, stats.
//   T escape -> T in the finale, CT still in their arena; live humans made equal on both sides; the clock ends ->
//   tie on live humans -> the side that escaped first (T) wins; ze_finale_wins for T humans 0 and 2
import { rm, killDoom, timeline, invariants, checker, god, arenaOf, finaleArena, forceEscape, statsOf } from './_lib.mjs';
const { probs, want } = checker();
const steps = timeline([
  [6, (api) => { const e = forceEscape(api, 2, 2); if (e) probs.add(e); }],
  [8, (api) => {
    const r = rm(api);
    want(!!finaleArena(api) && !r.zeResult, 'T in the finale, no result yet');
    // equal live humans: kill bots of the bigger side until both have as many
    const live = (side) => side === 2 ? [...finaleArena(api).players.values()].filter((p) => p.playerstate === 'live')
      : [...arenaOf(api, 3).players.values()].filter((p) => !p.zclass && p.playerstate === 'live');
    for (let k = 0; k < 8 && r.humansAlive(2) !== r.humansAlive(3); k++) {
      const big = r.humansAlive(2) > r.humansAlive(3) ? 2 : 3;
      const bot = live(big).find((p) => p.isBot);
      if (!bot) break;
      killDoom(api, bot.slot, null);
    }
    want(r.humansAlive(2) === r.humansAlive(3), `live humans equal: T ${r.humansAlive(2)} CT ${r.humansAlive(3)}`);
    r.timeUp();
    want(!!r.zeResult && r.zeResult.winner === 2 && r.zeResult.why === 'time', 'a tie at the clock goes to the side that escaped first: ' + JSON.stringify(r.zeResult));
  }],
]);
export default {
  setup(api) { for (const s of [0, 1, 2, 3]) api.manual.add(s); },
  tick(api) { god(api); steps(api); invariants(api, probs); },
  check(api) {
    const on = api.ctx.__stats().statsOn && !api.warmup;
    if (on) {
      const s = [0, 1, 2, 3].map((k) => statsOf(api, k));
      want(s[0].ze_finale_wins === 1 && s[2].ze_finale_wins === 1 && !s[1].ze_finale_wins && !s[3].ze_finale_wins, 'ze_finale_wins: ' + JSON.stringify(s.map((x) => x.ze_finale_wins)));
      want(api.mg.ok === true, 'mock mgstat check: ' + (api.mg.diffs || []).join('; '));
    }
    return [...probs];
  },
};
