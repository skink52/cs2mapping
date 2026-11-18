// a zombie player leaving is just removed; the last CT human leaving wipes CT -> T wins at once (no stall).
// Run: 4 humans + 0 bots, 20 s.
import { rm, pe, killDoom, timeline, checker } from './_lib.mjs';
import { god } from './_lib.mjs';
const { probs, want } = checker();
const steps = timeline([
  [7, (api) => { killDoom(api, 3, null); api.log('CT human slot 3 killed (becomes a zombie in the T arena)'); }],
  [12, (api) => { want(pe(api, 3).zeRole === 'zombie', 'slot 3 is a zombie'); api.disconnect(api.ctrl(3)); api.log('zombie slot 3 leaves'); }],
  [13, (api) => { want(!pe(api, 3), 'slot 3 removed'); want(!rm(api).zeResult, 'no result yet'); api.disconnect(api.ctrl(1)); api.log('last CT human (slot 1) leaves'); }],
  [15, (api) => { const r = rm(api).zeResult; want(r && r.winner === 2 && r.why === 'wipe', 'T wins when the last CT human leaves: ' + JSON.stringify(r)); }],
]);
export default {
  setup(api) { for (const s of [0, 1, 2, 3]) api.manual.add(s); },
  tick: (api) => { god(api); steps(api); },
  check(api) { want(api.winReasons['9'] >= 1, 'CS2 saw a T win: ' + JSON.stringify(api.winReasons)); return [...probs]; },
};
