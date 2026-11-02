// ===================================================================================
// FreeDM for CS2 - CS2 side. Settings you may want to change are in CONFIG.
// ===================================================================================

const CONFIG = {
  // ---- game rules
  MODE_WEIGHTS: { ffa: 30, tdm: 30, boss: 15, elim: 15, lms: 10 },   // boss = Boss Battle (co-op: waves of monsters, then a boss)
  FFA_FRAGS: 20,                 // first to this many (scaled down for small arenas)
  TDM_FRAGS: 32,                 // team total (scaled down for small arenas)
  ARENA_MAX: 16, ARENA_MIN: 8, MAX_ARENAS: 4,   // one arena until there are 2 x ARENA_MIN players, then 2, then 4, spread evenly
  MIN_PLAYERS: 2,                // fewer than this on T/CT (bots count): no Doom round, players stay in the lobby
  ROUND_SECONDS: 600,            // the script sets the CS2 round timer to this at round start
  ELIM_SECONDS: 240,             // elimination / last man standing arenas end after this (most alive wins)
  REPLACE_BOTS: true,            // someone joining mid-round takes a bot's place when there is no free room
  FINISH_GRACE: 120,             // once the first arena finishes, the others have this many seconds left (0 = off)
  LOADOUT_CHANCE: 0.12,          // chance, per arena, of a "weapon start": everyone there (re)spawns with one of START_WEAPONS
  START_WEAPONS: { shotgun: 3, ssg: 3, chaingun: 3, rocket: 2, plasma: 2, chainsaw: 2, bfg: 1 },   // weapon: how likely
  MONSTER_CHANCE: 0.15,          // chance, per arena, that a deathmatch round has monsters loose in the level (no frags for them)
  MONSTERS: { waves: 5, lives: 3, maxAlive: 36, roamMax: 8, difficulty: 1.35 },   // Boss Battle: waves before the boss (the 5th is the boss), lives each; alive cap per arena;
                                 // difficulty scales wave size, spawn pace, boss health and escort (1 = the 18 Oct balance)
  BOSS_SECONDS: 480,             // Boss Battle arenas end after this (the monsters win)
  ITEMS_RESPAWN: true,           // Doom "deathmatch 2.0": items respawn, weapons are picked up
  FRIENDLY_FIRE: false,
  FREELOOK_AIM: true,            // aim up/down with the mouse when autoaim finds nothing
  MAP_BLACKLIST: [],             // e.g. ["m24"] to never pick MAP24
  BOSS_MAP_BLACKLIST: [],        // levels never used for Boss Battle (it picks from the larger half of the levels anyway)

  // ---- next-mode vote (at the end of every round; no third round of one mode in a row)
  VOTE: true,
  VOTE_SECONDS: 10,              // how long the ballot is open (the next round waits for it if CS2's own break is shorter)
  VOTE_TOP_BONUS: 2,             // a vote counts 1 + this x (your frags / the top frags in your arena): top fragger = 3
  VOTE_KEYS: { ffa: "ATTACK", tdm: "ATTACK2", elim: "USE", lms: "RELOAD", boss: "LOOK_AT_WEAPON" },   // M1 M2 E R F

  // ---- monster kills on the CS2 scoreboard (Score column; the Kills column and rank plugins need a server plugin)
  MONSTER_SCORE: 2,              // points per monster kill (a CS2 kill is worth 2); 0 = off
  MONSTER_SCORE_BOSS: 10,        // points for killing a boss
  MONSTER_SCORE_DEATHMATCH: false, // also for the monsters loose in deathmatch rounds (off: they aren't the game there)
  MONSTER_PODIUM: true,          // Boss Battle: at round end the arena's top 3 monster killers get real CS2 kills, the others dying credited to them
  MONSTER_PODIUM_SHARES: [50, 30, 20],   // how the others are shared out: 1st, 2nd, 3rd (like Space Racer's podium)
  MONSTER_KILL_COMMAND: "",      // e.g. "hm_monster_kill {slot} {boss} {monster}": a server command per monster kill, for a plugin

  // ---- kill credit
  REAL_KILLS: true,              // every Doom frag is also a real CS2 kill (killfeed, scoreboard, rank plugins)
  KILL_DELAY: 1.0,               // seconds between the Doom death and the CS2 kill in respawn modes
  ADD_SCORE: false,              // add frags with AddScore instead (only used when REAL_KILLS is false)

  // ---- AFK
  AFK_WARN: 20, AFK_KICK: 30,    // seconds without input

  // ---- bots
  CS2_BOTS_PLAY: true,           // CS2 bots in the server are driven by the Doom bot AI
  BOT_SKILL: 0.35,              // 0 = hopeless, 1 = deadly; each bot varies a little around this

  // ---- server settings the map applies (set APPLY_CVARS false to leave the server's own config alone)
  APPLY_CVARS: true,
  CVARS_ALWAYS: [
    "mp_respawn_immunitytime 0",
    "mp_death_drop_gun 0",
    "mp_buy_anywhere 0",
    "mp_buytime 0",
    "mp_playercashawards 0",       // no money for kills (nothing can be bought anyway)
    "mp_teamcashawards 0",
    "mp_startmoney 0",
    "mp_maxmoney 0",
    "sv_disable_radar 1",         // the CS2 radar can't be hidden per client from a script; this is the server-side switch
  ],
  RESPAWN_CVARS_ON: ["mp_respawn_on_death_t 1", "mp_respawn_on_death_ct 1"],
  RESPAWN_CVARS_OFF: ["mp_respawn_on_death_t 0", "mp_respawn_on_death_ct 0"],
  EYE_FORWARD: 15,               // Doom units the camera sits ahead of the player centre (keeps the eye outside the marine model)
  OWN_BODY: "move",            // own Doom marine: "move" (smoothed), "snap" (teleport each tick), "off" (invisible to everyone)
  HIDE_OWN_BODY: true,           // make the parked CS2 pawn invisible (its body otherwise shows under the Doom view)
  CLIENT_CVARS: ["cl_hud_playercount_showcount 1"],   // sent to each player on arrival: player count instead of the avatars at the top (if CS2 lets a server set it)
  HIDE_CS_HUD: false,            // cl_draw_only_deathnotices can't be set from a server script (CS2 refuses it); kept for servers that allow it

  // ---- input
  // CS2 gives scripts no number keys, so: R = next weapon, F (inspect) = previous, right click = next
  NEXT_WEAPON: ["RELOAD", "ATTACK2"],
  PREV_WEAPON: ["LOOK_AT_WEAPON"],
  USE_KEYS: ["USE", "JUMP"],
  WALK_KEY: "WALK",              // hold to walk (Doom's default is to run)
  CHAT_COMMANDS: true,
  HELP_SECONDS: 8,               // how long !help shows the controls on that player's screen
  SAY_GAP: 1.0,                  // seconds between chat lines the script sends (CS2 drops chat sent too fast)

  // ---- rendering
  TICK_INTERP: true,
  MAX_EFFECT_PROPS: 120,         // per arena: puffs, blood, explosions...
  MAX_SOUNDS_PER_TICK: 24,
  MUSIC: true,                   // level music during rounds: long tracks in respawn rounds, short ones in one-life rounds
  MUSIC_GAP: 2,                  // seconds of quiet between tracks
  MUSIC_OPENER: "first+boss",    // the Hellmatch theme (trailer track) at round start: "first+boss" = the map's first round and its first Boss Battle round, "every" round, "first" round only, "off"
  SPAWN_BUDGET: 20,             // new props created per server tick at most (round start creates hundreds)
  HIDE_HUD_ON_SCOREBOARD: false,  // default for everyone; each player can switch it with !hud scores
  HUD_BUDGET: 600,               // HUD changes sent per server tick at most (the first draw for many players is spread out)

  // ---- entity names in the map
  HUD: "fdm_hud",
  PROP_TEMPLATE: "fdm_tpl_prop",
  BOOTH: "fdm_booth",
  SOUND_PREFIX: "fdm_snd_",
  MUSIC_PREFIX: "fdm_mus_",
  MAP_PARAMS: "fdm_map_params",  // info_map_parameters: its FireWinCondition input ends the CS2 round with a winner
  ROUND_SLACK: 15,               // CS2 round clock runs this much longer than the Doom clock, so the script ends the round

  DEBUG: false,
};

const ZSCALE = 1.2;
const VERSION = "0.2.0";
