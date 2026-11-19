// ===================================================================================
// Part 8: default settings (the CS2 script copies these and applies its own overrides)
// ===================================================================================
const DEFAULT_CFG = {
  arenaMax: 16, arenaMin: 8, maxArenas: 4, minPlayersToStart: 2,
  modeWeights: { ffa: 30, tdm: 30, boss: 15, elim: 15, lms: 10 },
  monsterChance: 0.15,            // chance, per arena, that a deathmatch round has monsters loose in the level
  monsters: { waves: 5, lives: 3, maxAlive: 36, roamMax: 8 },
  bossMapBlacklist: [],           // levels never used for Boss Battle (it already picks from the bigger half)
  bossTimeLimitTics: 480 * TICRATE,
  ffaFrags: 20, tdmFrags: 32,
  areaPerPlayer: 420000, mapRepeatGap: 8, mapBlacklist: [],
  friendlyFire: false,
  countdownTics: 3 * TICRATE, arenaEndHoldTics: 4 * TICRATE,
  minRespawnTics: TICRATE, autoRespawnTics: 3 * TICRATE, elimSpectateTics: 3 * TICRATE,
  afkWarnTics: 20 * TICRATE, afkKickTics: 30 * TICRATE,
  elimTimeLimitTics: 240 * TICRATE,
  finishGraceTics: 120 * TICRATE,
  loadoutChance: 0.12, loadouts: { shotgun: 3, ssg: 3, chaingun: 3, rocket: 2, plasma: 2, chainsaw: 2, bfg: 1 },
  staggerArenas: false,
  // Hellmatch ZE (75_ze.js). Horde (Round 3): cap per arena = clamp(capBase + capPerPlayer x players placed there at round
  // start, capMin, capMax) live zombies (AI + players), a sidecar's zombies.cap is a maximum (cap: a fixed number instead of
  // the formula); AI wanted = aiBase + aiPerHuman x live humans (under the cap less the zombie players); a surge (sidecar
  // action, and at every hold / boss / escape start) brings surgeBase + surgePerHuman x live humans at once, in packs;
  // AI with no live human within farDist thinks every farEvery-th tic
  ze: { cap: null, capBase: 24, capPerPlayer: 4, capMin: 32, capMax: 96, killDelayTics: TICRATE, drawWindowTics: TICRATE,
    zombieRespawnTics: 4 * TICRATE, zombieFirstTics: 2 * TICRATE,
    timeLimitTics: 600 * TICRATE, aiBase: 8, aiPerHuman: 5, fillGapTics: Math.round(1.2 * TICRATE), lateHumanTics: 120 * TICRATE,
    packMin: 3, packMax: 6, packGapTics: Math.round(2.5 * TICRATE), sleepShare: 0.3,   // sleepShare: the level's own monsters asleep at once, of the cap
    surgeBase: 6, surgePerHuman: 3, surgeDelayTics: 3 * TICRATE, autoSurge: true,
    farDist: 2000, farEvery: 4,
    // ammo and upgrades (Round 3): AI deaths drop ammo (dropChance, the type weighted by what the arena's live humans carry,
    // gone after dropTics, at most dropMax lying about); a completed hold without its own resupply action gives
    // holdResupply; a sidecar with no give action gets upgradeLadder ("done:N" = the Nth stage done, "boss" = a boss
    // stage starts); a human's bullets refill 1 each ammoFloorTics while below ammoFloor
    dropChance: 0.35, dropTics: 30 * TICRATE, dropMax: 40,
    holdResupply: { ammo: 0.5, health: 25, armor: 0 },
    upgradeLadder: [{ on: 'done:1', give: ['chaingun', 'ssg'] }, { on: 'done:2', give: ['rocket'] }, { on: 'boss', give: ['plasma'] }],
    ammoFloor: 50, ammoFloorTics: TICRATE,
    classes: ['IMP', 'DEMON', 'LOSTSOUL'], holdScore: 1, escapeScore: 3, map: null,
    // balance (test/sim_ze.cjs runs, 19 Nov 2026; Round 3: aiDamage 0.6 -> 0.5 for the bigger horde): the AI hits humans for aiDamage of Doom; a level's monsters are scaled by the
    // side's humans (mapScaleBase + mapScalePerHuman x humans, 0.3..1); a zombie player's health by its arena's live humans
    // (zHpBase + zHpPerHuman x humans, zHpMin..zHpMax); zDamage / zHp scale zombie players' hits and health on top
    zDamage: 1, zHp: 1, aiDamage: 0.5, mapScaleBase: 0.1, mapScalePerHuman: 0.11,
    zHpBase: 0.4, zHpPerHuman: 0.075, zHpMin: 0.55, zHpMax: 1.2,
    // a zombie player may drive a stage boss; idle this long -> AI again
    bossTakeover: true, bossAfkTics: 10 * TICRATE,
    // zombie players' respawn x (1 + catchup x (zombie players / live humans - 1)), at most x max
    zRespawnCatchup: 0.5, zRespawnMax: 3 },
  arena: { zeKnockback: 1.6, altdeath: true, itemRespawnTics: 30 * TICRATE, spawnProtectTics: 2 * TICRATE, freelookAim: true, viewBob: true, botSkill: 0.35, teamSuicidePenalty: true,
    maxMonsterCorpses: 24, maxLostSouls: 20 },
};
