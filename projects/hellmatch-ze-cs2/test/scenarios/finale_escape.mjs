// Round 4 finale, one side escapes (docs/STATUS.md "Round 4 contract"). 4 humans + 4 bots, 30 s, zemap=map01; run with
// 'stats', 'stats,warmup' and without stats (test/run_scenarios.sh).
//   T human 0 carries a chaingun, 77 health, 123 bullets; the T arena's escape completes with human 2 in the zone ->
//   every live T human (bots too) is in the finale arena with what they carried, the T arena is over, the round goes
//   on; everyone's centre line says the T escaped (the image of the whole sentence, or "T'S ESCAPED!" with the
//   sentence on the message line); the finale level has no monsters
//   every live CT human is killed -> no zombies (the T arena is over: they watch) -> T win (CS2 round: T)
//   stats: ze_finale_wins for T humans 0 and 2 only (no bots, none for CT), ze_survivor_wins for them, nothing in warmup
import { rm, pe, killDoom, timeline, invariants, checker, god, arenaOf, finaleArena, forceEscape, hudCentre, hudMsg, statsOf } from './_lib.mjs';
const { probs, want } = checker();
const LONG = "T'S ESCAPED - BUT WILL THE CTS BE HOT ON THEIR TRAIL?";
let movedT = 0;
const steps = timeline([
  [6, (api) => {
    const live = [...arenaOf(api, 2).players.values()].filter((p) => !p.zclass && p.playerstate === 'live' && !p.spectating);
    movedT = live.length;
    const e = forceEscape(api, 2, 2, () => {
      const p = pe(api, 0).player;
      p.weaponowned[3] = true; p.health = 77; p.mo.health = 77; p.ammo[0] = 123;   // 3 = WP_CHAINGUN, 0 = AM_CLIP
    });
    if (e) probs.add(e); else api.log(`T escaped with human 2 in the zone (${movedT} live T humans)`);
  }],
  [7, (api) => {
    const F = finaleArena(api), r = rm(api);
    want(!!F && !!r.finale, 'a finale arena was built');
    if (!F) return;
    want(!!F.level.data.finale, 'the finale arena plays the finale record: ' + F.mapId);
    want(!r.zeResult, 'the round goes on after the first escape: ' + JSON.stringify(r.zeResult));
    want(arenaOf(api, 2).finished, 'the T arena is over');
    const inF = [...F.players.values()].filter((p) => p.playerstate === 'live');
    want(inF.length === movedT && inF.every((p) => p.person.zeSide === 2 && pe(api, p.slot).arena === F), `every live T human moved (${inF.length} of ${movedT})`);
    const p0 = pe(api, 0).player;
    want(!!p0 && p0.arena === F && p0.weaponowned[3] && p0.health === 77 && p0.ammo[0] === 123, `human 0 kept weapons/health/ammo: ${p0 && [p0.weaponowned[3], p0.health, p0.ammo[0]]}`);
    want([...F.mobjs].every((m) => m.info.kind !== 'monster'), 'no monsters in the finale');
    want(inF.every((p) => F.inside(p.mo.x, p.mo.y)), 'everyone in the finale is inside its level');
    for (const s of [1, 0]) {
      const c = hudCentre(api, s), m = hudMsg(api, s);
      want(c === LONG || (c === "T'S ESCAPED!" && m === LONG), `slot ${s} sees the escape message: centre "${c}" msg "${m}"`);
    }
  }],
  [8, (api) => {
    const a = arenaOf(api, 3);
    const live = [...a.players.values()].filter((p) => !p.zclass && p.playerstate === 'live');
    for (const p of live) killDoom(api, p.slot, null);
    api.log(`all ${live.length} live CT humans killed`);
  }],
  [11, (api) => {
    const r = rm(api);
    want(!!r.zeResult && r.zeResult.winner === 2, 'T win once the CT are wiped: ' + JSON.stringify(r.zeResult));
    for (const s of [1, 3]) { const x = pe(api, s); want(x.zeRole !== 'zombie' || !x.player, `CT ${s} did not rise as a zombie in the finished T arena`); }
  }],
]);
export default {
  setup(api) { for (const s of [0, 1, 2, 3]) api.manual.add(s); },
  tick(api) { god(api); steps(api); invariants(api, probs); },
  check(api) {
    want((api.winReasons[9] || 0) >= 1, 'the CS2 round ended as a T win: ' + JSON.stringify(api.winReasons));
    const on = api.ctx.__stats().statsOn && !api.warmup;
    if (!on) { want(api.mg.sent === 0, `stats off or warmup: nothing may be sent, got ${api.mg.sent}`); return [...probs]; }
    const s = [0, 1, 2, 3].map((k) => statsOf(api, k));
    api.log('stats by slot: ' + JSON.stringify(s));
    want(s[0].ze_finale_wins === 1 && s[2].ze_finale_wins === 1, `T humans 0 and 2 ze_finale_wins ${s[0].ze_finale_wins} ${s[2].ze_finale_wins}`);
    want(!s[1].ze_finale_wins && !s[3].ze_finale_wins, 'a CT human got ze_finale_wins');
    want(s[0].ze_survivor_wins === 1 && s[2].ze_survivor_wins === 1, `T humans 0 and 2 ze_survivor_wins ${s[0].ze_survivor_wins} ${s[2].ze_survivor_wins}`);
    want(s[2].ze_escapes === 1, 'human 2 ze_escapes ' + s[2].ze_escapes);
    want(api.mg.bots === 0, 'a stat for a bot: ' + api.mg.bots);
    want(api.mg.ok === true, 'mock mgstat check: ' + (api.mg.diffs || []).join('; '));
    return [...probs];
  },
};
