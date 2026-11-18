// run with the 'warmup' option: a ZE round plays in warmup, the swap happens, the zombie spawns without a CS2 respawn,
// and nothing reaches the CS2 scoreboard. Run: 4 humans + 2 bots, 20 s, options warmup.
import { pe, killDoom, timeline, checker } from './_lib.mjs';
import { god } from './_lib.mjs';
const { probs, want } = checker();
const steps = timeline([
  [7, (api) => killDoom(api, 1, null)],
  [10, (api) => want(pe(api, 1).zeRole === 'zombie', 'swap happens in warmup')],
  [14, (api) => want(pe(api, 1).player && pe(api, 1).player.mo && pe(api, 1).player.playerstate === 'live', 'zombie body up in warmup')],
]);
export default {
  setup(api) { for (const s of [0, 1, 2, 3]) api.manual.add(s); },
  tick: (api) => { god(api); steps(api); },
  check(api) { want(api.stats.scriptKills === 0, 'no scripted CS2 kills in warmup: ' + api.stats.scriptKills); return [...probs]; },
};
