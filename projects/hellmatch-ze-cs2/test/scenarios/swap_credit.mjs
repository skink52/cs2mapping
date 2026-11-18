// human death -> zombie in the other arena (CS2 team unchanged); cross-team kill credit both ways; no teamkill penalty;
// monsters never target zombie players; zombies never pick things up. Run: 4 humans + 4 bots, 40 s.
import { pe, killDoom, liveZombie, timeline, invariants, checker } from './_lib.mjs';
import { god } from './_lib.mjs';
const { probs, want } = checker();
let k1 = 0, k2 = 0, d0 = 0;
const steps = timeline([
  [7, (api) => { want(pe(api, 1).zeRole === 'human', 'slot 1 starts human'); killDoom(api, 1, null); api.log('CT human slot 1 killed by the world'); }],
  [9.5, (api) => {
    const x = pe(api, 1);
    want(x.zeRole === 'zombie' && x.arena && x.arena.zeSide === 2, `slot 1 should be a zombie in the T arena: role ${x.zeRole} arena side ${x.arena && x.arena.zeSide}`);
    want(api.ctrl(1).team === 3, 'slot 1 must stay on CT');
  }],
  [13, (api) => {
    want(liveZombie(api, 1), 'slot 1 zombie body is up by 13 s');
    if (!liveZombie(api, 1)) return;
    k1 = api.ctrl(1).kills; d0 = api.ctrl(0).deaths;
    killDoom(api, 0, 1); api.log('zombie slot 1 kills T human slot 0');
  }],
  [15.5, (api) => {
    want(api.ctrl(1).kills === k1 + 1, `zombie (CT) gets the CS2 kill of a T human: kills ${k1} -> ${api.ctrl(1).kills}`);
    want(api.ctrl(0).deaths === d0 + 1, 'T human death counted');
    want(pe(api, 0).zeRole === 'zombie' && pe(api, 0).arena.zeSide === 3, 'slot 0 is now a zombie in the CT arena');
  }],
  [20, (api) => {
    want(liveZombie(api, 1), 'zombie slot 1 alive at 20 s');
    k2 = api.ctrl(2).kills;
    killDoom(api, 1, 2); api.log('T human slot 2 kills zombie slot 1');
  }],
  [22.5, (api) => want(api.ctrl(2).kills === k2 + 1, `T human gets the CS2 kill of the CT zombie: ${k2} -> ${api.ctrl(2).kills}`)],
  [32, (api) => want(liveZombie(api, 1), 'zombie slot 1 came back by 32 s')],
]);
export default {
  setup(api) { for (const s of [0, 1, 2, 3]) api.manual.add(s); },
  tick(api) { god(api); steps(api); invariants(api, probs); },
  check(api) { if (api.stats.teamkills) probs.add('teamkill penalties: ' + api.stats.teamkills); return [...probs]; },
};
