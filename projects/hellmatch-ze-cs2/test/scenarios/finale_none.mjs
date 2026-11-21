// Round 4: no finale level record (a build without one) -> an escape wins at once, as before. 4 humans + 4 bots, 15 s, zemap=map01.
import { rm, timeline, invariants, checker, god, finaleArena, forceEscape, hudCentre, noFinale } from './_lib.mjs';
const { probs, want } = checker();
const steps = timeline([
  [6, (api) => { const e = forceEscape(api, 2, 2); if (e) probs.add(e); }],
  [7, (api) => {
    const r = rm(api);
    want(!!r.zeResult && r.zeResult.winner === 2 && r.zeResult.why === 'escape', 'the T escape ended the round: ' + JSON.stringify(r.zeResult));
    want(!finaleArena(api) && !r.finale, 'no finale arena');
    want(hudCentre(api, 1) === 'T HUMANS ESCAPED!', 'centre line: ' + hudCentre(api, 1));
  }],
]);
export default {
  setup(api) { noFinale(api); for (const s of [0, 1, 2, 3]) api.manual.add(s); },
  tick(api) { god(api); steps(api); invariants(api, probs); },
  check(api) { want((api.winReasons[9] || 0) >= 1, 'the CS2 round ended as a T win: ' + JSON.stringify(api.winReasons)); return [...probs]; },
};
