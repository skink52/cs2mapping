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
  ZDMN_BITE1: ['ZDMN', 'B', 4, 'A_ZWindup', 'ZDMN_BITE2'],
  ZDMN_BITE2: ['ZDMN', 'C', 4, 'A_ZBite', 'ZDMN_BITE3'],
  ZDMN_BITE3: ['ZDMN', 'A', 6, 'A_ZReFire', 'ZDMN_READY'],
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
