// both sides wiped on the same tick -> draw; the next round: T wiped first, CT 2 s later -> CT wins.
// Run: 4 humans + 0 bots, 40 s.
import { rm, pe, killDoom, timeline, checker } from './_lib.mjs';
import { god } from './_lib.mjs';
const { probs, want } = checker();
let r2 = null;
const steps = timeline([
  [7, (api) => { for (const s of [0, 1, 2, 3]) killDoom(api, s, null); api.log('all four humans killed on one tick'); }],
  [9.5, (api) => { const r = rm(api).zeResult; want(r && r.winner === 0 && r.why === 'wipe', 'same-tick wipe is a draw: ' + JSON.stringify(r)); }],
]);
const human = (api, s) => pe(api, s) && pe(api, s).zeRole === 'human' && pe(api, s).player && pe(api, s).player.mo;
export default {
  setup(api) { for (const s of [0, 1, 2, 3]) api.manual.add(s); },
  tick(api) {
    god(api); steps(api);
    const r = rm(api);
    if (r.roundNumber >= 2 && r.state === 'running' && !r2 && r.arenas.length === 2 && r.arenas.every((a) => a.countdown === 0)) r2 = { t: api.time, step: 0 };
    if (r2 && r2.step === 0 && api.time > r2.t + 1) { for (const s of [0, 2]) if (human(api, s)) killDoom(api, s, null); r2.step = 1; api.log('round 2: T humans killed'); }
    if (r2 && r2.step === 1 && api.time > r2.t + 3) { for (const s of [1, 3]) if (human(api, s)) killDoom(api, s, null); r2.step = 2; api.log('round 2: CT humans killed 2 s later'); }
    if (r2 && r2.step === 2 && api.time > r2.t + 6) { const z = r.zeResult; want(z && z.winner === 3, 'T wiped first -> CT wins: ' + JSON.stringify(z)); r2.step = 3; }
  },
  check(api) {
    want(api.winReasons['2'] >= 1, 'CS2 saw a DRAW round end: ' + JSON.stringify(api.winReasons));
    want(api.winReasons['8'] >= 1, 'CS2 saw a CT win: ' + JSON.stringify(api.winReasons));
    want(r2 && r2.step === 3, 'second round reached');
    return [...probs];
  },
};
