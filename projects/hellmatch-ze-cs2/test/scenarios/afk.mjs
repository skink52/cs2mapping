// run with the 'afk' option: human0 never moves -> marked AFK after 30 s, out of the arena, counted as a lost T human.
// Run: 4 humans + 2 bots, 45 s, options afk.
import { rm, pe, timeline, checker } from './_lib.mjs';
import { god } from './_lib.mjs';
const { probs, want } = checker();
let before = 0;
const steps = timeline([
  [8, (api) => { before = rm(api).humansAlive(2); }],
  [40, (api) => {
    const x = pe(api, 0);
    want(x.afk && !x.arena, 'human0 marked AFK and out of the arena: afk ' + x.afk + ' status ' + x.status);
    want(rm(api).humansAlive(2) <= before - 1, `T humans down by one: ${before} -> ${rm(api).humansAlive(2)}`);
  }],
]);
// every human is invulnerable: a side wiped before 30 s would end the round and restart the AFK clock (seed-dependent)
const allGod = (api) => { for (const a of rm(api).arenas) for (const p of a.players.values()) if (!p.zclass) p.powers[0] = 1 << 20; };
export default { setup(api) { api.manual.add(0); }, tick: (api) => { god(api); allGod(api); steps(api); }, check: () => [...probs] };
