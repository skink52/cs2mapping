// ===================================================================================
// Hellmatch ZE (zombie escape) for CS2 - CS2 side. Settings you may want to change are in CONFIG.
// ===================================================================================

const CONFIG = {
  // ---- zombie escape (core defaults in DEFAULT_CFG.ze; a map's sidecar can set cap, respawn_seconds, time_limit, classes)
  ZE: {
    MAP: null,                   // e.g. "e1m1" to always play that ZE level (null = rotate through the ZE levels)
    // live zombies per arena, AI and zombie players together (AI yields to players): CAP_BASE + CAP_PER_PLAYER x the players
    // placed in that arena at round start, within CAP_MIN..CAP_MAX; a map's sidecar zombies.cap is a maximum on top
    CAP_BASE: 24, CAP_PER_PLAYER: 4, CAP_MIN: 32, CAP_MAX: 96,
    KILL_DELAY_TICS: 35,         // Doom tics (35 a second) from a human's death to their swap into the other arena
    DRAW_WINDOW_TICS: 35,        // both sides wiped within this many tics of each other: a draw
    ZOMBIE_RESPAWN: 4,           // seconds before a dead zombie comes back (behind the humans), unless the sidecar says otherwise
    TIME_LIMIT: 600,             // seconds, unless the sidecar's time_limit says otherwise; then most live humans, then furthest stage
    AI_BASE: 8, AI_PER_HUMAN: 5, // AI zombies wanted in an arena: AI_BASE + AI_PER_HUMAN x live humans (under the cap)
    // a surge ("HERE THEY COME"): SURGE_BASE + SURGE_PER_HUMAN x live humans at once, in packs from behind and the flanks;
    // at every hold, boss and escape start (AUTO_SURGE) and wherever a map's sidecar asks for one
    SURGE_BASE: 6, SURGE_PER_HUMAN: 3, AUTO_SURGE: true,
    FAR_AI: 2000,                // Doom units: AI with no live human this close thinks every 4th tic (cheaper big hordes)
    // ammo and upgrades: an AI zombie's death drops ammo DROP_CHANCE of the time (the kind the arena's humans use, clips and
    // shells mostly), gone after DROP_SECONDS; a completed hold gives HOLD_RESUPPLY (share of max ammo for each ammo type a
    // human can use, health / armour up to 100) unless the map's sidecar has its own; maps without "give" actions hand out
    // UPGRADE_LADDER ("done:N": the Nth stage done, "boss": a boss stage starts; ids pistol shotgun ssg chaingun rocket
    // plasma bfg chainsaw); a human's bullets refill 1 a second while below AMMO_FLOOR (never fists only)
    DROP_CHANCE: 0.35, DROP_SECONDS: 30,
    HOLD_RESUPPLY: { ammo: 0.5, health: 25, armor: 0 },
    UPGRADE_LADDER: [{ on: "done:1", give: ["chaingun", "ssg"] }, { on: "done:2", give: ["rocket"] }, { on: "boss", give: ["plasma"] }],
    AMMO_FLOOR: 50,
    AI_DAMAGE: 0.5,              // the AI horde's hits on humans, against Doom's (1 = Doom's own); a bigger horde hits lighter
    ZOMBIE_DAMAGE: 1,            // zombie players' claw / bite / lunge / dash (the classes' own numbers x this)
    ZOMBIE_HP: 1,                // zombie players' health (x this, on top of the scaling by the humans they hunt)
    KNOCKBACK: 1.6,              // shots push zombie players this much harder than Doom's mass rule alone
    BOSS_TAKEOVER: true,         // a zombie player may take over a stage boss (E within 5 s of it appearing)
    CLASSES: ["IMP", "DEMON", "LOSTSOUL"],   // zombie classes in rotation when the sidecar doesn't list its own
    DRAW_DIST: 3000,             // Doom units: things farther than this from everyone looking at an arena are not drawn (props freed)
    HOLD_SCORE: 1, ESCAPE_SCORE: 3,          // CS2 score for each live human when a hold completes / for an escape
  },
  MIN_PLAYERS: 2,                // fewer than this on T/CT (bots count): no Doom round, players stay in the lobby
  ROUND_SECONDS: 660,            // the script sets the CS2 round timer to this at round start (above the ZE time limit)
  ITEMS_RESPAWN: true,           // Doom "deathmatch 2.0": items respawn, weapons are picked up
  FREELOOK_AIM: true,            // aim up/down with the mouse when autoaim finds nothing
  // red screen when hurt (Doom's palette shift, toned down after the 20 Nov playtest): MAX_STEP = strongest red class used
  // (1-8, about 11% opacity each; Doom goes to 8), SCALE = tint per point of damage taken (Doom 1), FADE = tint lost per
  // tic (Doom 1: a big hit stayed red for 3 s). Pickup gold, berserk and invulnerability tints are Doom's own.
  DAMAGE_TINT: { MAX_STEP: 3, SCALE: 0.6, FADE: 1.25 },

  // ---- monster kills on the CS2 scoreboard (Score column; the Kills column and rank plugins need a server plugin)
  MONSTER_SCORE: 1,              // points per AI zombie killed (a CS2 kill is worth 2); 0 = off
  MONSTER_SCORE_BOSS: 10,        // points for killing a stage boss

  // ---- stats for a server plugin: "echo mgstat <slot> <stat> [n]" server commands (pve_kills, boss_kills, lms_wins), through
  // echo because a dedicated server drops Workshop map commands that aren't on Valve's allow list.
  // Off by default: a server without the plugin would print each one in its console.
  // A plugin can also switch it on for the current map: point_script fdm_script, input RunScriptInput "mgstat_on"
  SERVER_STATS: false,
  SERVER_STATS_EVERY: 1,         // seconds: monster kills are added up per player and sent at most this often

  // ---- kill credit
  REAL_KILLS: true,              // every Doom frag is also a real CS2 kill (killfeed, scoreboard, rank plugins)
  KILL_DELAY: 1.0,               // seconds between the Doom death and the CS2 kill
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
  // what the template's logic_auto did in Hellmatch: no freeze time, a CS2 round clock longer than the ZE round
  // (applied at activation and every round start)
  CVARS_ROUND: ["mp_freezetime 0", "mp_roundtime 12"],
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
  MUSIC: true,                   // level music during rounds (the "long" pool; the "boss" pool during a boss stage when the map has it)
  MUSIC_GAP: 2,                  // seconds of quiet between tracks
  MUSIC_OPENER: "first",         // the Hellmatch theme (trailer track) at round start: "first" round of the map only, "every" round, "off"
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
const VERSION = "0.1.0-ze";
