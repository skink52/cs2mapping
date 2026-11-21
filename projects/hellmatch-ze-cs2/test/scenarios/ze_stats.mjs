// server stats (Round 3, docs/SERVER_STATS_NOTE.md): each ZE stat fires for the right human player and never for a bot.
// Run three ways (test/run_scenarios.sh): with the option 'stats' every stat below must arrive; with 'stats,warmup' and with
// stats off nothing may be sent at all. 4 humans + 4 bots, 50 s.
//   slot 1 (CT) dies -> zombie in the T arena; kills T human 0 (ze_infections); T human 2 kills zombie 1 (ze_zombie_kills);
//   the T arena's hold completes (ze_holds for 2); its boss stage starts, zombie 1 takes the boss (ze_boss_takeovers),
//   kills a T bot human as the boss (ze_infections + ze_boss_player_kills); human 2 kills the player boss (ze_zombie_kills,
//   pve_kills, boss_kills); the escape stage, human 2 in its zone when it completes (ze_escapes), the T side wins
//   (ze_survivor_wins for 2, none for CT human 3); best_ze_stage for 2 = the escape stage's number.
// Without the finale level record (Round 4 finale: test/scenarios/finale_*.mjs), so the escape wins at once.
// The mock's own mgstat check (every stat the playsim says a human earned arrived, names / format, no bots) must say OK too.
import { rm, pe, killDoom, liveZombie, timeline, invariants, checker, god, noFinale } from './_lib.mjs';
const { probs, want } = checker();
const IN = { USE: 128 };
const arenaT = (api) => rm(api).arenas.find((a) => a.zeSide === 2);
const bossStage = (a) => a.ze.stages.find((s) => s.d.boss);
const escStage = (a) => a.ze.stages.find((s) => s.d.escape);
let hadBoss = false, escN = 0, botVictim = null;
function tpInto(api, a, p, x, y) {
  for (const [dx, dy] of [[0, 0], [40, 0], [-40, 0], [0, 40], [0, -40], [64, 64], [-64, -64], [96, 0], [0, 96]]) {
    let ok = false;
    a.run(() => { ok = api.ctx.teleportMove(p.mo, x + dx, y + dy); });
    if (ok) { p.mo.z = p.mo.floorz; p.mo.momx = p.mo.momy = p.mo.momz = 0; return true; }
  }
  return false;
}
// the stats a slot got: sent (mg.bySlot) plus what still waits in the script's one-second batch
function got(api, slot) {
  const o = Object.assign({}, api.mg.bySlot.get(String(slot)) || {});
  const p = api.ctx.__stats().statPending.get(slot) || {};
  for (const [k, n] of Object.entries(p)) o[k] = k.startsWith('best_') ? Math.max(o[k] || 0, n) : (o[k] || 0) + n;
  return o;
}
const steps = timeline([
  [6, (api) => { killDoom(api, 1, null); api.log('CT human 1 killed by the world: a zombie in the T arena'); }],
  [12, (api) => {
    want(liveZombie(api, 1) && pe(api, 1).arena === arenaT(api), 'slot 1 is a live zombie in the T arena by 12 s');
    killDoom(api, 0, 1); api.log('zombie 1 kills T human 0');
  }],
  [16, (api) => { if (liveZombie(api, 1)) { killDoom(api, 1, 2); api.log('T human 2 kills zombie 1'); } else probs.add('zombie 1 not up at 16 s'); }],
  [19, (api) => {
    const a = arenaT(api), ze = a.ze, s = ze.active();
    want(!!s && s.total > 0 && !s.d.escape, 'the T arena is in a hold at 19 s: ' + (s && s.name));
    if (s) a.run(() => ze.finishStage(s));
    api.log('T arena hold completed by the scenario');
    // then straight on to the boss stage (the scripted zombie is the one to take it)
    const b = bossStage(a);
    if (!b) return;
    hadBoss = true;
    ze.nearSpawn = () => true;
    a.run(() => { for (const x of ze.stages) if (x.i < b.i && x.state !== 'done') { if (x.state === 'pending') ze.startStage(x); ze.finishStage(x); } });
    const st = b.d.start;
    if (st && st.line_crossed !== undefined) ze.crossed.add(st.line_crossed);
    if (st && st.use_line !== undefined) ze.used.add(st.use_line);
  }],
  [21, (api) => {
    if (!hadBoss) return;
    const a = arenaT(api);
    want(bossStage(a).state === 'active' && !!a.ze.offer, `boss stage active and offered: ${bossStage(a).state} ${!!a.ze.offer}`);
    const c = api.ctrl(1);
    if (c && c.pawn) c.pawn.buttons |= IN.USE;
  }],
  [22, (api) => {
    if (!hadBoss) return;
    const p1 = pe(api, 1).player;
    want(!!p1 && !!p1.zclass && p1.zclass.startsWith('B_'), 'zombie 1 drives the boss: ' + (p1 && p1.zclass));
    // the boss kills a T bot human
    const a = arenaT(api);
    const bot = [...a.players.values()].find((p) => p.isBot && !p.zclass && p.playerstate === 'live' && p.mo);
    if (bot && p1 && p1.zclass && p1.zclass.startsWith('B_')) { botVictim = bot.slot; killDoom(api, bot.slot, 1); api.log('the boss player kills T bot ' + bot.name); }
    else probs.add('no T bot human to kill as the boss');
  }],
  [24, (api) => {
    if (!hadBoss) return;
    const p1 = pe(api, 1).player;
    if (p1 && p1.mo && p1.mo.boss) { killDoom(api, 1, 2); api.log('T human 2 kills the player boss'); } else probs.add('no player boss to kill at 24 s');
  }],
  [26, (api) => {
    const a = arenaT(api), ze = a.ze, e = escStage(a);
    if (!e) { probs.add('no escape stage in ' + a.mapId); return; }
    escN = e.i + 1;
    a.run(() => { for (const x of ze.stages) if (x.i < e.i && x.state !== 'done') { if (x.state === 'pending') ze.startStage(x); ze.finishStage(x); } if (e.state === 'pending') ze.startStage(e); });
    const c = ze.zoneCentre(e.d.zone), p2 = pe(api, 2).player;
    want(!!c && !!p2 && p2.playerstate === 'live' && tpInto(api, a, p2, c.x, c.y), 'human 2 into the escape zone');
    a.run(() => ze.finishStage(e));
    api.log(`T arena escape stage ${escN} completed with human 2 in the zone`);
  }],
  [27, (api) => want(!!rm(api).zeResult && rm(api).zeResult.why === 'escape' && rm(api).zeResult.winner === 2, 'the round ended with the T escape: ' + JSON.stringify(rm(api).zeResult))],
]);
export default {
  setup(api) { noFinale(api); for (const s of [0, 1, 2, 3]) api.manual.add(s); },   // the escape ends the round (finale: finale_*.mjs)
  tick(api) {
    god(api);
    // the T bot humans are the boss's victim at 22 s: the horde mustn't get them first (Round 4: packs no longer jam)
    if (api.time < 22.5) { const a = arenaT(api); if (a) for (const p of a.players.values()) if (p.isBot && !p.zclass && p.playerstate === 'live') p.powers[0] = 1 << 20; }
    else if (api.time < 22.6) { const a = arenaT(api); if (a) for (const p of a.players.values()) if (p.isBot && !p.zclass) p.powers[0] = 0; }
    steps(api); invariants(api, probs);
  },
  check(api) {
    const on = api.ctx.__stats().statsOn && !api.warmup;
    if (!on) {
      want(api.mg.sent === 0, `stats off or warmup: nothing may be sent, got ${api.mg.sent} commands ${JSON.stringify(api.mg.byStat)}`);
      return [...probs];
    }
    const g = (s) => got(api, s);
    const s0 = g(0), s1 = g(1), s2 = g(2), s3 = g(3);
    api.log('stats by slot: ' + JSON.stringify({ 0: s0, 1: s1, 2: s2, 3: s3 }));
    want(api.mg.bots === 0, 'a stat was sent for a bot or an empty slot: ' + api.mg.bots);
    want(api.mg.bad.length === 0, 'a command outside the contract: ' + api.mg.bad[0]);
    want((s1.ze_infections || 0) === (hadBoss ? 2 : 1), `slot 1 ze_infections ${s1.ze_infections} (want ${hadBoss ? 2 : 1})`);
    want((s2.ze_zombie_kills || 0) === (hadBoss ? 2 : 1), `slot 2 ze_zombie_kills ${s2.ze_zombie_kills} (want ${hadBoss ? 2 : 1})`);
    want((s2.ze_holds || 0) >= 1, 'slot 2 ze_holds ' + s2.ze_holds);
    want(!s0.ze_holds, 'slot 0 (a zombie by then) got ze_holds ' + s0.ze_holds);
    want(s2.ze_escapes === 1, 'slot 2 ze_escapes ' + s2.ze_escapes);
    want(s2.ze_survivor_wins === 1, 'slot 2 ze_survivor_wins ' + s2.ze_survivor_wins);
    want(!s3.ze_survivor_wins && !s3.ze_escapes, 'CT human 3 got a win or an escape: ' + JSON.stringify(s3));
    want(!s1.ze_survivor_wins && !s0.ze_survivor_wins, 'a zombie got ze_survivor_wins');
    want(s2.best_ze_stage === escN, `slot 2 best_ze_stage ${s2.best_ze_stage} (want ${escN})`);
    want(s0.best_ze_stage === 1 && s1.best_ze_stage === 1, `slots 0/1 best_ze_stage ${s0.best_ze_stage}/${s1.best_ze_stage} (want 1: they died in stage 1)`);
    if (hadBoss) {
      want(s1.ze_boss_takeovers === 1, 'slot 1 ze_boss_takeovers ' + s1.ze_boss_takeovers);
      want(s1.ze_boss_player_kills === 1, 'slot 1 ze_boss_player_kills ' + s1.ze_boss_player_kills);
      want((s2.boss_kills || 0) === 1 && (s2.pve_kills || 0) >= 1, `slot 2 boss_kills ${s2.boss_kills} pve_kills ${s2.pve_kills}`);
    }
    // the mock's own contract check (every stat the playsim says a human earned arrived) must agree
    want(api.mg.ok === true, 'mock mgstat check: ' + (api.mg.diffs || []).join('; '));
    return [...probs];
  },
};
