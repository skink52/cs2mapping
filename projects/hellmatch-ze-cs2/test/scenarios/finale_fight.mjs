// Round 4 finale, both sides escape (docs/STATUS.md "Round 4 contract"). 4 humans + 4 bots, 30 s, zemap=map01; run
// with 'stats', 'stats,warmup' and without stats (test/run_scenarios.sh).
//   T escape (human 2 in the zone), then the CT escape (human 3) -> both sides' live humans in the finale; centre
//   "FINAL FIGHT!" (or the whole sentence as one image) and the message line "CTS TRACKED DOWN THE REMAINING TS - ..."
//   T vs CT damage on, same side off
//   CT human 1 kills T human 0 -> a real CS2 kill for slot 1 (outside warmup); slot 0 watches, no zombie, can't !back
//   the rest of the T in the finale die -> CT win the final fight (CS2 round: CT)
//   stats: ze_finale_wins for CT humans 1 and 3 only; nothing in warmup
import { rm, pe, killDoom, timeline, invariants, checker, god, arenaOf, finaleArena, forceEscape, hudCentre, hudMsg, statsOf } from './_lib.mjs';
const { probs, want } = checker();
const LONG = 'CTS TRACKED DOWN THE REMAINING TS - FIGHT TO BE THE FINAL SURVIVORS';
let kills1 = 0;
const steps = timeline([
  [6, (api) => { const e = forceEscape(api, 2, 2); if (e) probs.add('T: ' + e); else api.log('T escaped'); }],
  [8, (api) => { const e = forceEscape(api, 3, 3); if (e) probs.add('CT: ' + e); else api.log('CT escaped'); }],
  [9, (api) => {
    const F = finaleArena(api), r = rm(api);
    want(!!F && r.finale && r.finale.fight, 'the finale fight is on');
    if (!F) return;
    want(!r.zeResult, 'no result yet: ' + JSON.stringify(r.zeResult));
    want([0, 1, 2, 3].every((s) => pe(api, s).arena === F), 'all four humans are in the finale');
    for (const s of [0, 1]) {
      const c = hudCentre(api, s), m = hudMsg(api, s);
      want(c === LONG || (c === 'FINAL FIGHT!' && m === LONG), `slot ${s} sees the fight message: centre "${c}" msg "${m}"`);
    }
    // damage: T vs CT on, same side off (god mode and spawn protection lifted for the test)
    const t0 = pe(api, 0).player, t2 = pe(api, 2).player, c1 = pe(api, 1).player;
    t0.powers[0] = 0; t0.protectUntil = 0;
    const h = t0.health;
    F.run(() => api.ctx.damageMobj(t0.mo, t2.mo, t2.mo, 7));
    want(t0.health === h, `same side hurt: ${h} -> ${t0.health}`);
    F.run(() => api.ctx.damageMobj(t0.mo, c1.mo, c1.mo, 7));
    want(t0.health < h, `CT can't hurt T: ${h} -> ${t0.health}`);
    t0.health = t0.mo.health = 100;
    kills1 = api.ctrl(1).kills;
  }],
  [10, (api) => { killDoom(api, 0, 1); api.log('CT human 1 kills T human 0 in the finale'); }],
  [12.5, (api) => {
    const x = pe(api, 0);
    want(x.status === 'spectating' && !x.player && x.zeRole !== 'zombie', `slot 0 watches after a finale death: ${x.status} ${x.zeRole}`);
    want(!rm(api).canJoin(x), 'slot 0 may not !back in this round');
    if (!api.warmup) want(api.ctrl(1).kills === kills1 + 1, `slot 1's CS2 kills ${kills1} -> ${api.ctrl(1).kills}`);
    const F = finaleArena(api);
    const ts = [...F.players.values()].filter((p) => p.person.zeSide === 2 && p.playerstate === 'live');
    for (const p of ts) killDoom(api, p.slot, p.isBot ? 1 : 3);
    api.log(`the other ${ts.length} T in the finale killed`);
  }],
  [14, (api) => {
    const r = rm(api);
    want(!!r.zeResult && r.zeResult.winner === 3 && r.zeResult.why === 'finale', 'CT win the final fight: ' + JSON.stringify(r.zeResult));
  }],
]);
export default {
  setup(api) { for (const s of [0, 1, 2, 3]) api.manual.add(s); },
  tick(api) { god(api); steps(api); invariants(api, probs); },
  check(api) {
    want((api.winReasons[8] || 0) >= 1, 'the CS2 round ended as a CT win: ' + JSON.stringify(api.winReasons));
    const on = api.ctx.__stats().statsOn && !api.warmup;
    if (!on) { want(api.mg.sent === 0, `stats off or warmup: nothing may be sent, got ${api.mg.sent}`); return [...probs]; }
    const s = [0, 1, 2, 3].map((k) => statsOf(api, k));
    api.log('stats by slot: ' + JSON.stringify(s));
    want(s[1].ze_finale_wins === 1 && s[3].ze_finale_wins === 1, `CT humans 1 and 3 ze_finale_wins ${s[1].ze_finale_wins} ${s[3].ze_finale_wins}`);
    want(!s[0].ze_finale_wins && !s[2].ze_finale_wins, 'a T human got ze_finale_wins');
    want(api.mg.bots === 0, 'a stat for a bot: ' + api.mg.bots);
    want(api.mg.ok === true, 'mock mgstat check: ' + (api.mg.diffs || []).join('; '));
    return [...probs];
  },
};
