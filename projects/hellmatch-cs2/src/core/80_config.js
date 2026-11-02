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
  arena: { altdeath: true, itemRespawnTics: 30 * TICRATE, spawnProtectTics: 2 * TICRATE, freelookAim: true, viewBob: true, botSkill: 0.35, teamSuicidePenalty: true,
    maxMonsterCorpses: 24, maxLostSouls: 20 },
};
