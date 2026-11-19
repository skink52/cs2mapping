// zombie class choice: while a zombie player is dead / rising, R and right click cycle the next body's class forward and
// F (look at weapon) back; the HUD bottom line reads "CLASS: <name>  [R] NEXT"; the pick is kept for every later body
// (no rotation); the same keys on a live zombie are its ability and change nothing. Run: 4 humans + 4 bots, 40 s.
import { pe, killDoom, liveZombie, timeline, invariants, checker } from './_lib.mjs';
import { god } from './_lib.mjs';
const { probs, want } = checker();
const IN = { ATTACK2: 512, RELOAD: 1024, LOOK_AT_WEAPON: 4096 };
const press = (api, slot, b) => { const c = api.ctrl(slot); if (c && c.pawn && c.pawn.valid !== false) c.pawn.buttons |= b; else probs.add(`slot ${slot}: no pawn to press with at ${api.time.toFixed(2)}`); };
const NAMES = { IMP: 'IMP', DEMON: 'DEMON', LOSTSOUL: 'LOST SOUL' };
let list = null, c0 = null, want1 = null;
const steps = timeline([
  [6, (api) => { killDoom(api, 1, null); api.log('CT human slot 1 killed by the world'); }],
  [12, (api) => {
    want(liveZombie(api, 1), 'slot 1 is a live zombie by 12 s');
    const x = pe(api, 1);
    list = api.dbg().rm.classList(x.arena);
    c0 = x.player && x.player.zclass;
    want(x.zeClassPick === c0, `first body is the person's pick: pick ${x.zeClassPick} body ${c0}`);
    api.log(`slot 1 rose as ${c0} (classes ${list.join(',')})`);
  }],
  [13, (api) => { killDoom(api, 1, null); api.log('zombie slot 1 killed'); }],
  [13.5, (api) => press(api, 1, IN.RELOAD)],
  [13.6, (api) => {
    const i = list.indexOf(c0), n1 = list[(i + 1) % list.length];
    const line = api.hudLine(1, 'fdm_spec', 32);
    want(line === `CLASS: ${NAMES[n1]}  [R] NEXT`, `HUD after R: "${line}" (want "CLASS: ${NAMES[n1]}  [R] NEXT")`);
  }],
  [13.65, (api) => press(api, 1, IN.ATTACK2)],
  [13.8, (api) => press(api, 1, IN.LOOK_AT_WEAPON)],
  [13.95, (api) => {
    const i = list.indexOf(c0);
    want1 = list[(i + 1) % list.length];
    want(pe(api, 1).zeClassPick === want1, `R, right click, F: pick ${pe(api, 1).zeClassPick}, want ${want1}`);
  }],
  [22, (api) => {
    want(liveZombie(api, 1), 'slot 1 rose again by 22 s');
    const z = pe(api, 1).player;
    want(z && z.zclass === want1 && z.mo && z.mo.info.key === 'ZPLAYER_' + want1, `second body is the pick: ${z && z.zclass} / ${z && z.mo && z.mo.info.key}`);
    const line = api.hudLine(1, 'fdm_spec', 32);
    want(line.startsWith(NAMES[want1] + '  '), `live HUD shows the class and its ability: "${line}"`);
  }],
  [23, (api) => press(api, 1, IN.RELOAD)],
  [23.3, (api) => want(pe(api, 1).zeClassPick === want1 && pe(api, 1).player.zclass === want1, 'R on a live zombie is the ability, not a class change')],
  [25, (api) => { killDoom(api, 1, null); api.log('zombie slot 1 killed again (no keys this time)'); }],
  [34, (api) => {
    want(liveZombie(api, 1), 'slot 1 rose a third time by 34 s');
    want(pe(api, 1).player.zclass === want1, `default = last pick, no rotation: ${pe(api, 1).player.zclass} want ${want1}`);
  }],
]);
export default {
  setup(api) { for (const s of [0, 1, 2, 3]) api.manual.add(s); },
  tick(api) { god(api); steps(api); invariants(api, probs); },
  check(api) {
    // every zombie player (bots included) is one of the arena's classes
    for (const a of api.dbg().rm.arenas) for (const p of a.players.values()) if (p.zclass && !list.includes(p.zclass)) probs.add(`${p.name} has class ${p.zclass}`);
    return [...probs];
  },
};
