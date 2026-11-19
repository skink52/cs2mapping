// ===================================================================================
// Part 0b (Hellmatch ZE): states for player-controlled monsters ("zombie classes") and key items.
// Merged into STATE_DEFS / LOOP_DEFS by 00_defs.js. Body states carry no AI action (the player drives them);
// first-person states use the view sprites the pipeline draws (docs/STATUS.md Contract: ZIMP, ZIMF, ZDMN, ZSKL).
// ===================================================================================

const ZE_STATE_DEFS = {
  // ---- imp (serpentipede) body: TROO frames
  ZB_IMP: ['TROO', 'A', -1, null, 'NULL'],
  ZB_IMP_RUN1: ['TROO', 'A', 4, null, 'ZB_IMP_RUN2'],
  ZB_IMP_RUN2: ['TROO', 'B', 4, null, 'ZB_IMP_RUN3'],
  ZB_IMP_RUN3: ['TROO', 'C', 4, null, 'ZB_IMP_RUN4'],
  ZB_IMP_RUN4: ['TROO', 'D', 4, null, 'ZB_IMP_RUN1'],
  ZB_IMP_ATK1: ['TROO', 'E', 4, null, 'ZB_IMP_ATK2'],
  ZB_IMP_ATK2: ['TROO', 'F', 4, null, 'ZB_IMP_ATK3'],
  ZB_IMP_ATK3: ['TROO', 'G', 6, null, 'ZB_IMP'],
  ZB_IMP_PAIN: ['TROO', 'H', 3, null, 'ZB_IMP_PAIN2'],
  ZB_IMP_PAIN2: ['TROO', 'H', 3, 'A_Pain', 'ZB_IMP'],
  // ---- demon (flesh worm) body: SARG frames
  ZB_DEMON: ['SARG', 'A', -1, null, 'NULL'],
  ZB_DEMON_RUN1: ['SARG', 'A', 3, null, 'ZB_DEMON_RUN2'],
  ZB_DEMON_RUN2: ['SARG', 'B', 3, null, 'ZB_DEMON_RUN3'],
  ZB_DEMON_RUN3: ['SARG', 'C', 3, null, 'ZB_DEMON_RUN4'],
  ZB_DEMON_RUN4: ['SARG', 'D', 3, null, 'ZB_DEMON_RUN1'],
  ZB_DEMON_ATK1: ['SARG', 'E', 4, null, 'ZB_DEMON_ATK2'],
  ZB_DEMON_ATK2: ['SARG', 'F', 4, null, 'ZB_DEMON_ATK3'],
  ZB_DEMON_ATK3: ['SARG', 'G', 6, null, 'ZB_DEMON'],
  ZB_DEMON_PAIN: ['SARG', 'H', 3, null, 'ZB_DEMON_PAIN2'],
  ZB_DEMON_PAIN2: ['SARG', 'H', 3, 'A_Pain', 'ZB_DEMON'],
  // ---- lost soul (deadflare) body: SKUL frames, always burning
  ZB_SKUL: ['SKUL', 'A', 6, null, 'ZB_SKUL2', 1],
  ZB_SKUL2: ['SKUL', 'B', 6, null, 'ZB_SKUL', 1],
  ZB_SKUL_RUN1: ['SKUL', 'A', 4, null, 'ZB_SKUL_RUN2', 1],
  ZB_SKUL_RUN2: ['SKUL', 'B', 4, null, 'ZB_SKUL_RUN1', 1],
  ZB_SKUL_ATK1: ['SKUL', 'C', 6, null, 'ZB_SKUL_ATK2', 1],
  ZB_SKUL_ATK2: ['SKUL', 'D', 10, null, 'ZB_SKUL', 1],
  ZB_SKUL_PAIN: ['SKUL', 'E', 3, null, 'ZB_SKUL_PAIN2', 1],
  ZB_SKUL_PAIN2: ['SKUL', 'E', 3, 'A_Pain', 'ZB_SKUL', 1],

  // ---- first-person view (psprite) states. A_ZReady reads the buttons, like A_WeaponReady.
  // imp: ZIMP A idle, B wind-up, C swipe, D follow-through; ZIMF A cupped hands, B fireball, C release
  ZIMP_UP: ['ZIMP', 'A', 1, 'A_ZRaise', 'ZIMP_UP'],
  ZIMP_READY: ['ZIMP', 'A', 1, 'A_ZReady', 'ZIMP_READY'],
  ZIMP_CLAW1: ['ZIMP', 'B', 3, 'A_ZWindup', 'ZIMP_CLAW2'],
  ZIMP_CLAW2: ['ZIMP', 'C', 4, 'A_ZClaw', 'ZIMP_CLAW3'],
  ZIMP_CLAW3: ['ZIMP', 'D', 5, null, 'ZIMP_CLAW4'],
  ZIMP_CLAW4: ['ZIMP', 'A', 2, 'A_ZReFire', 'ZIMP_READY'],
  ZIMF_1: ['ZIMF', 'A', 6, 'A_ZFireStart', 'ZIMF_2'],
  ZIMF_2: ['ZIMF', 'B', 4, 'A_ZFireball', 'ZIMF_3', 1],
  ZIMF_3: ['ZIMF', 'C', 6, null, 'ZIMP_READY'],
  // demon: ZDMN A idle jaws, B open, C bite, D lunge/charge
  ZDMN_UP: ['ZDMN', 'A', 1, 'A_ZRaise', 'ZDMN_UP'],
  ZDMN_READY: ['ZDMN', 'A', 1, 'A_ZReady', 'ZDMN_READY'],
  ZDMN_BITE1: ['ZDMN', 'B', 6, 'A_ZWindup', 'ZDMN_BITE2'],
  ZDMN_BITE2: ['ZDMN', 'C', 5, 'A_ZBite', 'ZDMN_BITE3'],
  ZDMN_BITE3: ['ZDMN', 'A', 9, 'A_ZReFire', 'ZDMN_READY'],
  ZDMN_LUNGE1: ['ZDMN', 'B', 3, 'A_ZWindup', 'ZDMN_LUNGE2'],
  ZDMN_LUNGE2: ['ZDMN', 'D', 14, 'A_ZLunge', 'ZDMN_LUNGE3'],
  ZDMN_LUNGE3: ['ZDMN', 'A', 6, null, 'ZDMN_READY'],
  // lost soul: ZSKL A idle, B flare, C dash
  ZSKL_UP: ['ZSKL', 'A', 1, 'A_ZRaise', 'ZSKL_UP'],
  ZSKL_READY: ['ZSKL', 'A', 1, 'A_ZReady', 'ZSKL_READY'],
  ZSKL_DASH1: ['ZSKL', 'B', 5, 'A_ZWindup', 'ZSKL_DASH2', 1],
  ZSKL_DASH2: ['ZSKL', 'C', 12, 'A_ZDash', 'ZSKL_DASH3', 1],
  ZSKL_DASH3: ['ZSKL', 'A', 6, null, 'ZSKL_READY'],
};

// key items (only placed when a ZE map's sidecar keeps keys: humans.keys "keep")
const ZE_LOOP_DEFS = {
  BKEY: ['BKEY', 'AB', 10, 1], RKEY: ['RKEY', 'AB', 10, 1], YKEY: ['YKEY', 'AB', 10, 1],
  BSKU: ['BSKU', 'AB', 10, 1], RSKU: ['RSKU', 'AB', 10, 1], YSKU: ['YSKU', 'AB', 10, 1],
};

// ---- player-driven stage bosses (3.1): a zombie player can take a boss over. Its body runs on states copied from the
// monster's own (sprites, frames, timing) with every AI action taken out: ZB_<type> stand, _RUN1.. the see loop,
// _ATK1.. a short attack pose, _PAIN1.. the pain frames (A_Pain kept). The first-person view reuses the imp's art:
// ZIMP claw frames for the melee, ZIMF fireball frames for the missile (no new art in the Contract).
const ZE_BOSS_TYPES = ['BARON', 'KNIGHT', 'REVENANT', 'MANCUBUS', 'ARACHNOTRON', 'CYBERDEMON'];
const ZE_BOSS_RUNS = {};          // type -> number of run states (the body's run range is ZB_<type>_RUN1..N)
for (const T of ZE_BOSS_TYPES) {
  const def = MONSTER_DEFS[T], S = MONSTER_STATE_DEFS, P = 'ZB_' + T;
  const sp = S[def.spawnstate];
  ZE_STATE_DEFS[P] = [sp[0], sp[1], -1, null, 'NULL'];
  // the see chain up to where it loops (an arachnotron's first "sight" state is left out of the loop)
  const run = [];
  for (let n = def.seestate; n && S[n] && !run.includes(n) && run.length < 16; n = S[n][4]) run.push(n);
  run.splice(0, Math.max(0, run.indexOf(S[run[run.length - 1]][4])));   // only the loop itself
  const loopTo = 0;
  run.forEach((n, i) => { const s = S[n]; ZE_STATE_DEFS[P + '_RUN' + (i + 1)] = [s[0], s[1], Math.max(1, s[2]), null, P + '_RUN' + (i + 1 < run.length ? i + 2 : loopTo + 1), s[5]]; });
  ZE_BOSS_RUNS[T] = run.length;
  const chain = (start, tag, keepPain) => {
    const names = [];
    for (let n = start; n && S[n] && !run.includes(n) && !names.includes(n) && names.length < 3; n = S[n][4]) names.push(n);
    names.forEach((n, i) => {
      const s = S[n];
      ZE_STATE_DEFS[P + tag + (i + 1)] = [s[0], s[1], Math.max(2, Math.min(8, s[2])), keepPain && s[3] === 'A_Pain' ? 'A_Pain' : null, i + 1 < names.length ? P + tag + (i + 2) : P, s[5]];
    });
  };
  chain(def.missilestate || def.meleestate, '_ATK', false);
  chain(def.painstate, '_PAIN', true);
}
Object.assign(ZE_STATE_DEFS, {
  // boss view: A idle, melee B wind-up C swipe D follow-through (heavier than the imp's); missile ZIMF A-C
  ZBV_UP: ['ZIMP', 'A', 1, 'A_ZRaise', 'ZBV_UP'],
  ZBV_READY: ['ZIMP', 'A', 1, 'A_ZReady', 'ZBV_READY'],
  ZBV_MELEE1: ['ZIMP', 'B', 5, 'A_ZWindup', 'ZBV_MELEE2'],
  ZBV_MELEE2: ['ZIMP', 'C', 5, 'A_ZBossMelee', 'ZBV_MELEE3'],
  ZBV_MELEE3: ['ZIMP', 'D', 8, null, 'ZBV_MELEE4'],
  ZBV_MELEE4: ['ZIMP', 'A', 4, 'A_ZReFire', 'ZBV_READY'],
  ZBV_FIRE1: ['ZIMF', 'A', 7, 'A_ZFireStart', 'ZBV_FIRE2'],
  ZBV_FIRE2: ['ZIMF', 'B', 4, 'A_ZBossMissile', 'ZBV_FIRE3', 1],
  ZBV_FIRE3: ['ZIMF', 'C', 7, null, 'ZBV_READY'],
});
