// a zombie that changes CS2 team rejoins as a zombie for its new side; a human that changes team counts as lost for the
// old side and comes back as a zombie (rejoin rule). Run: 4 humans + 2 bots, 20 s.
import { rm, pe, killDoom, timeline, checker } from './_lib.mjs';
import { god } from './_lib.mjs';
const { probs, want } = checker();
let t0 = 0;
const steps = timeline([
  [7, (api) => killDoom(api, 1, null)],
  [10, (api) => { want(pe(api, 1).zeRole === 'zombie' && pe(api, 1).arena.zeSide === 2, 'slot 1 zombie in T arena'); api.teamChange(api.ctrl(1), 2); api.log('zombie slot 1 switches to T'); }],
  [13, (api) => { const x = pe(api, 1); want(x.zeRole === 'zombie' && x.arena && x.arena.zeSide === 3, 'now a zombie for T, hunting in the CT arena: ' + x.zeRole + ' ' + (x.arena && x.arena.zeSide)); }],
  [14, (api) => { t0 = rm(api).humansAlive(2); api.teamChange(api.ctrl(2), 3); api.log('T human slot 2 switches to CT'); }],
  [17, (api) => {
    const x = pe(api, 2);
    want(rm(api).humansAlive(2) === t0 - 1, `T lost a human: ${t0} -> ${rm(api).humansAlive(2)}`);
    want(x.zeRole === 'zombie' && x.arena && x.arena.zeSide === 2, 'slot 2 rejoins as a CT zombie in the T arena: ' + x.zeRole + ' ' + (x.arena && x.arena.zeSide));
  }],
]);
export default { setup(api) { for (const s of [0, 1, 2, 3]) api.manual.add(s); }, tick: (api) => { god(api); steps(api); }, check: () => [...probs] };
