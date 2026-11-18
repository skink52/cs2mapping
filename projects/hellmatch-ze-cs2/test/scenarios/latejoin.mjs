// late joiners: a human during the first stage; a zombie once it is done; anyone rejoining the same round is a zombie.
// Run: 4 humans + 2 bots, 25 s.
import { rm, pe, timeline, checker } from './_lib.mjs';
import { god } from './_lib.mjs';
const { probs, want } = checker();
let a = null, b = null, c = null;
const steps = timeline([
  [7, (api) => { a = api.connect('late_t', 2, false); api.log('late_t joins T during stage 1'); }],
  [9, (api) => { const x = pe(api, a.slot); want(x && x.zeRole === 'human' && x.arena && x.arena.zeSide === 2 && x.player.playerstate === 'live', 'late_t is a live human in the T arena: ' + (x && x.zeRole)); }],
  [10, (api) => { api.disconnect(api.ctrl(0)); api.log('human0 (T) leaves'); }],
  [11, (api) => { b = api.connect('human0', 2, false); api.log('human0 rejoins'); }],
  [13, (api) => { const x = pe(api, b.slot); want(x && x.zeRole === 'zombie' && x.arena && x.arena.zeSide === 3, 'a rejoin comes back as a zombie in the CT arena: ' + (x && x.zeRole) + ' ' + (x && x.arena && x.arena.zeSide)); }],
  [14, (api) => {
    const ct = rm(api).arenas.find((x) => x.zeSide === 3);
    ct.run(() => { if (ct.ze.stages[0] && ct.ze.stages[0].state === 'active') ct.ze.finishStage(ct.ze.stages[0]); });
    c = api.connect('late_ct', 3, false); api.log('stage 1 of the CT arena done; late_ct joins CT');
  }],
  [16, (api) => { const x = pe(api, c.slot); want(x && x.zeRole === 'zombie' && x.arena && x.arena.zeSide === 2, 'after stage 1 a CT joiner is a zombie in the T arena: ' + (x && x.zeRole)); }],
  [22, (api) => { const x = pe(api, c.slot); want(x && x.player && x.player.playerstate === 'live' && x.player.mo, 'late_ct zombie body is up'); }],
]);
export default { setup(api) { for (const s of [0, 1, 2, 3]) api.manual.add(s); }, tick: (api) => { god(api); steps(api); }, check: () => [...probs] };
