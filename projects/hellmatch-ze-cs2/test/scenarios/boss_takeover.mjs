// player boss takeover (3.1): when a boss stage starts, zombie players of that arena see "PRESS E TO BECOME THE BOSS";
// E away from a spawn is an opt-in and the opted-in player with the most human kills gets the boss when the 5 s run
// out; E near a spawn takes it at once. The boss body keeps the boss's health and has its attacks on ATTACK / ATTACK2;
// the Doom AI takes it back when its player sits idle (10 s) or leaves; a human killing the player boss ends the stage
// and gets the CS2 kill and the boss score; a human killed by the boss player is that player's CS2 kill.
// Run: 4 humans + 4 bots, 52 s.
import { rm, pe, killDoom, liveZombie, timeline, invariants, checker } from './_lib.mjs';
const { probs, want } = checker();
const IN = { USE: 128, ATTACK2: 512 };
const press = (api, slot, b) => { const c = api.ctrl(slot); if (c && c.pawn && c.pawn.valid !== false) c.pawn.buttons |= b; else probs.add(`slot ${slot}: no pawn to press with at ${api.time.toFixed(2)}`); };
const arenaT = (api) => rm(api).arenas.find((a) => a.zeSide === 2);
const bossStage = (a) => a.ze.stages.find((s) => s.d.boss);
const liveBossMonsters = (a) => [...a.mobjs].filter((m) => m.info.kind === 'monster' && m.boss && m.health > 0);
const busy = new Set([0, 1, 2, 3]);   // slots whose players keep turning (not idle, not AFK); 3 stops to test the idle hand-back
let sawBall = false, bossType = '', cls = null, bossHp0 = 0, k3 = 0, k2 = 0, s2 = 0, victim = null, bodyHp = 0;
function tpNear(api, a, p, tx, ty) {
  for (const [dx, dy] of [[150, 0], [-150, 0], [0, 150], [0, -150], [110, 110], [-110, -110], [110, -110], [-110, 110], [220, 0], [0, 220], [-220, 0], [0, -220]]) {
    let ok = false;
    a.run(() => { ok = api.ctx.teleportMove(p.mo, tx + dx, ty + dy); });
    if (ok) { p.mo.z = p.mo.floorz; p.mo.momx = p.mo.momy = p.mo.momz = 0; return true; }
  }
  return false;
}
const newOffer = (a) => { a.ze.offer = { until: a.leveltime + 5 * 35, opted: new Map() }; };
const steps = timeline([
  [6, (api) => { killDoom(api, 1, null); killDoom(api, 3, null); api.log('CT humans 1 and 3 killed: zombies in the T arena'); }],
  [12, (api) => {
    want(liveZombie(api, 1) && liveZombie(api, 3), 'slots 1 and 3 are live zombies by 12 s');
    want(pe(api, 1).arena === arenaT(api) && pe(api, 3).arena === arenaT(api), 'both in the T arena');
    killDoom(api, 0, 3); api.log('zombie 3 kills T human 0 (a human kill for the boss draw)');
  }],
  [12.2, (api) => want(pe(api, 3).zeHumanKills === 1 && !pe(api, 1).zeHumanKills, `human kills: slot 3 ${pe(api, 3).zeHumanKills}, slot 1 ${pe(api, 1).zeHumanKills}`)],
  [13, (api) => {
    const a = arenaT(api), ze = a.ze;
    ze.nearSpawn = () => false;   // test the opt-in path: nobody counts as near a spawn
    a.run(() => { for (const s of ze.stages) if (!s.d.boss && s.i < bossStage(a).i) ze.finishStage(s); });
    const st = bossStage(a).d.start;
    if (st && st.line_crossed !== undefined) ze.crossed.add(st.line_crossed);
    api.log('T arena forced to the boss stage');
  }],
  [13.3, (api) => {
    const a = arenaT(api), ze = a.ze;
    want(bossStage(a).state === 'active', 'boss stage active');
    want(!!ze.boss && ze.boss.info.kind === 'monster' && !!ze.offer, `AI boss up and offered: ${ze.boss && ze.boss.info.key} offer ${!!ze.offer}`);
    bossHp0 = ze.boss ? ze.boss.health : 0;
    bossType = ze.boss ? ze.boss.info.key : '';
    cls = api.ctx.__ZCLASS && api.ctx.__ZCLASS['B_' + bossType];
    want(!!cls, 'a player class for the ' + bossType);
    want(api.hudLine(1, 'fdm_msg', 56) === 'PRESS E TO BECOME THE BOSS', `slot 1 HUD: "${api.hudLine(1, 'fdm_msg', 56)}"`);
  }],
  [13.5, (api) => press(api, 1, IN.USE)],
  [13.8, (api) => press(api, 3, IN.USE)],
  [14.1, (api) => {
    const o = arenaT(api).ze.offer;
    want(!!o && o.opted.size === 2, `both opted in: ${o && o.opted.size}`);
    want(api.hudLine(1, 'fdm_msg', 56) === 'BOSS REQUESTED - MOST HUMAN KILLS WINS', `slot 1 HUD after E: "${api.hudLine(1, 'fdm_msg', 56)}"`);
    want(!pe(api, 1).player.zclass.startsWith('B_'), 'nobody is the boss before the offer runs out');
  }],
  [19, (api) => {
    const a = arenaT(api), ze = a.ze, p3 = pe(api, 3).player;
    want(p3.zclass === 'B_' + bossType && ze.bossPlayer === p3 && ze.boss === p3.mo && p3.mo.boss, `slot 3 (most human kills) drives the boss: ${p3.zclass}`);
    want(p3.mo.health > 0 && p3.mo.health <= bossHp0 && p3.mo.health >= bossHp0 - 400, `boss body keeps the boss's health: ${p3.mo.health} of ${bossHp0}`);
    want(liveBossMonsters(a).length === 0, 'the AI boss monster is gone');
    want(api.hudLine(3, 'fdm_spec', 32) === `${cls.name}  ${cls.ability} READY`, `boss HUD bottom: "${api.hudLine(3, 'fdm_spec', 32)}"`);
    want(api.hudLine(3, 'fdm_msg', 56).startsWith('YOU ARE THE BOSS'), `boss HUD message: "${api.hudLine(3, 'fdm_msg', 56)}"`);
    want(api.hudLine(1, 'fdm_ctr', 24) === 'THE BOSS IS A PLAYER!', `centre: "${api.hudLine(1, 'fdm_ctr', 24)}"`);
    want(!pe(api, 1).player.zclass.startsWith('B_'), 'slot 1 stays a zombie');
  }],
  [19.5, (api) => press(api, 3, IN.ATTACK2)],
  [20.3, (api) => {
    const a = arenaT(api), p3 = pe(api, 3).player;
    if (cls.cd > 30) want(p3.zcd > 0, 'the missile is on cooldown after MOUSE2');
    want(sawBall, `a ${cls.missile} from the player boss`);
  }],
  [20.5, (api) => {
    const a = arenaT(api);
    victim = [...a.players.values()].find((p) => !p.zclass && p.isBot && p.playerstate === 'live');
    want(!!victim, 'a live T human bot to kill');
    if (!victim) return;
    k3 = api.ctrl(3).kills;
    killDoom(api, victim.slot, 3); api.log(`boss player 3 kills T human bot ${victim.slot}`);
  }],
  [22.5, (api) => { if (victim) want(api.ctrl(3).kills === k3 + 1, `a kill by the boss player is that player's CS2 kill: ${k3} -> ${api.ctrl(3).kills}`); }],
  [23, (api) => { busy.delete(3); bodyHp = pe(api, 3).player.mo ? pe(api, 3).player.mo.health : 0; api.log('slot 3 goes idle'); }],
  [34.6, (api) => {
    const a = arenaT(api), ze = a.ze, b = liveBossMonsters(a);
    want(ze.bossPlayer === null, 'idle 10 s: the boss player is released');
    want(b.length === 1 && ze.boss === b[0] && b[0].info.key === bossType, `the AI drives the boss again: ${b.length}`);
    if (b[0]) want(b[0].health > 0 && b[0].health <= bodyHp && !!b[0].target, `AI boss has the body's health (${b[0].health} <= ${bodyHp}) and hunts`);
    want(bossStage(a).state === 'active', 'the boss stage goes on');
    want(api.hudLine(3, 'fdm_msg', 56) === 'THE AI TOOK THE BOSS BACK', `slot 3 told: "${api.hudLine(3, 'fdm_msg', 56)}"`);
    busy.add(3);
  }],
  [37, (api) => {
    want(liveZombie(api, 3) && !pe(api, 3).player.zclass.startsWith('B_'), `slot 3 rose as its own class: ${pe(api, 3).player.zclass}`);
    const a = arenaT(api);
    delete a.ze.nearSpawn;   // back to the real rule
    newOffer(a);
    want(tpNear(api, a, pe(api, 1).player, a.ze.boss.x, a.ze.boss.y), 'slot 1 placed next to the boss');
  }],
  [37.3, (api) => press(api, 1, IN.USE)],
  [37.5, (api) => {
    const a = arenaT(api), p1 = pe(api, 1).player;
    want(a.ze.bossPlayer === p1 && p1.zclass === 'B_' + bossType, `E next to the boss takes it at once: ${p1.zclass}`);
  }],
  [38, (api) => { api.disconnect(api.ctrl(1)); api.log('boss player 1 disconnects'); }],
  [38.3, (api) => {
    const a = arenaT(api), b = liveBossMonsters(a);
    want(a.ze.bossPlayer === null && b.length === 1 && a.ze.boss === b[0], `left: the AI has the boss again (${b.length})`);
    want(bossStage(a).state === 'active', 'the stage did not end on the leave');
  }],
  [39, (api) => {
    const a = arenaT(api);
    newOffer(a);
    want(tpNear(api, a, pe(api, 3).player, a.ze.boss.x, a.ze.boss.y), 'slot 3 placed next to the boss');
  }],
  [39.3, (api) => press(api, 3, IN.USE)],
  [39.5, (api) => {
    const a = arenaT(api), p3 = pe(api, 3).player;
    want(a.ze.bossPlayer === p3, 'slot 3 drives the boss again');
    k2 = api.ctrl(2).kills; s2 = api.ctrl(2).score;
    killDoom(api, 3, 2); api.log('T human 2 kills the player boss');
  }],
  [39.8, (api) => {
    const a = arenaT(api);
    want(bossStage(a).state === 'done', `boss stage done when the player boss dies: ${bossStage(a).state}`);
    want(a.ze.bossPlayer === null, 'no boss player after the kill');
  }],
  [42, (api) => {
    want(api.ctrl(2).kills === k2 + 1, `human gets the CS2 kill of the player boss: ${k2} -> ${api.ctrl(2).kills}`);
    want(api.ctrl(2).score >= s2 + 10, `and the boss score: ${s2} -> ${api.ctrl(2).score}`);
  }],
  [49, (api) => want(liveZombie(api, 3) && !pe(api, 3).player.zclass.startsWith('B_'), `slot 3 back as a zombie class: ${pe(api, 3).player.zclass}`)],
]);
let lastTurn = 0;
export default {
  setup(api) { for (const s of [0, 1, 2, 3]) api.manual.add(s); },
  tick(api) {
    // nobody dies unless the scenario kills them (a side wiped would end the round)
    for (const a of rm(api).arenas) for (const p of a.players.values()) if (!p.zclass) p.powers[0] = 1 << 20;
    for (const s of [0, 1, 2, 3]) { const x = pe(api, s); if (x && x.player) x.player.powers[0] = 1 << 20; }
    if (api.time - lastTurn >= 0.5) { lastTurn = api.time; for (const s of busy) { const c = api.ctrl(s); if (c && c.pawn) c.pawn.eye.yaw = (c.pawn.eye.yaw + 3) % 360; } }
    if (api.time > 19.4 && api.time < 20.3 && !sawBall) {
      const p3 = pe(api, 3).player, a = arenaT(api);
      sawBall = !!p3 && !!p3.mo && !!cls && [...a.mobjs].some((m) => m.info.key === cls.missile && m.target === p3.mo && m.zkind === 'zBOSSfire');
    }
    steps(api); invariants(api, probs);
  },
  check: () => [...probs],
};
