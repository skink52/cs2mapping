// ---------------------------------------------------------------- settings (server owners can change these)
const CONFIG = {
  // maps run at once by player count (T + CT): [from this many players, maps]. Never more maps than the smaller team.
  MAPS_BY_PLAYERS: [[0, 1], [25, 2], [45, 3]],
  MAP_ORDER: ['dust2', 'train', 'nuke'],
  ROUNDS_PER_MAP: 10,          // the map set moves on after this many rounds (0 = never); !dust2 etc. requests pick the next
  ROUND_TIME: 180,             // seconds
  FREEZE_TIME: 6,              // 1.6 mp_freezetime
  BUY_TIME: 90,                // seconds after the freeze time ends (1.6 mp_buytime 1.5)
  C4_TIMER: 45,                // 1.6 mp_c4timer
  START_MONEY: 800,
  MAX_MONEY: 16000,
  RESTART_DELAY: 5,            // seconds between the round result and the next round (1.6: 5)
  FINISH_GRACE: 90,            // once one map is decided the others get at most this long (0 = no limit); planted bombs play out
  SET_ROUND_TIME: true,        // set CS2's round clock from the script (otherwise mp_roundtime)
  DRAW_REASONS: [10, 2],       // FireWinCondition values tried for a draw (see TESTING.md)
  EXACT_END_REASONS: false,    // send bombed / defused / saved to CS2 instead of plain T / CT wins (see TESTING.md)

  // 1.6 rules (switch any off to keep CS2's)
  DAMAGE_16: true,             // 1.6 weapon damage, armour, knife, HE grenade and C4 blast
  FALL_DAMAGE_16: true,        // 1.6 fall damage (starts at lower heights than CS2's)
  CS2_REAPPLIES_HITGROUP: false, // set true if headshots turn out 4x too strong in the first test (see TESTING.md)
  ROUND_MONEY: true,           // 1.6 round rewards and losing-streak bonus
  KILL_MONEY: true,            // +$300 per kill, -$3300 per teammate
  GIVE_C4: true,               // one bomb per map for a random terrorist
  BOT_BUY: true,               // CS2 bots buy 1.6 gear when they spawn (they can't use the menu)
  SWAP_P2000_FOR_USP: true,    // CTs who spawn with a P2000 get the USP (1.6's CT pistol)
  NO_SPAWN_ARMOR: true,        // nobody spawns with armour (1.6)
  SPARE_AMMO_ON_BUY: false,    // 1.6: a bought gun has one magazine; buy ammo separately
  AMMO_FILL: true,             // one click on "primary / secondary ammo" buys packs until full (1.6 needed one key press per pack)
  JUMP_16: true,               // 1.6 jump height (sv_jump_impulse 268); crouch-jumps reach what they reached in 1.6

  // menus and HUD
  CLASS_MENU: true,            // the 1.6 class (player model) menu when joining a team
  CLASS_MENU_SECONDS: 25,      // auto-select after this long
  SET_MODELS: true,
  MODELS_16: true,             // the 1.6 player models (false: CS2 agents stand in for the 1.6 classes)
  PACKS_16: true,              // 1.6 models show the bomb pack on the C4 carrier and the defuse kit on CTs who have one
  MENU_MOUSE: true,            // menus use CS2's cursor mode (click a row); false: W / S to move, E to pick, R to go back
  BUY_KEY_INSPECT: true,       // F (inspect) opens the buy menu in a buy zone
  BUY_KEY_CS2: true,           // CS2's buy key opens it too (if CS2 shows its buy menu at all)
  HUD_MODE: 'raised',          // raised: the 1.6 HUD sits just above CS2's own boxes; classic: 1.6 positions; off
  HUD_BUDGET: 700,             // HUD changes sent per server tick
  HELP_LINE: 'Counter-Strike 1.6   -   F in a buy zone: buy menu   -   !help',

  // sounds and chat
  SOUNDS: true,
  SOUND_SHARE: 96,             // players this close to someone hearing a radio line share that copy
  MAX_SOUNDS_PER_TICK: 24,
  FIRE_IN_THE_HOLE: true,
  CHAT: true,                  // map results in chat when several maps run
  SAY_GAP: 1.0,                // seconds between chat lines

  APPLY_CVARS: true,
  CVARS: [
    'mp_ignore_round_win_conditions 1',     // the script ends rounds (several maps at once)
    'mp_halftime 0',                        // 1.6 had no half time
    'mp_give_player_c4 0',                  // one bomb per map, given by the script
    'mp_playercashawards 0', 'mp_teamcashawards 0',   // 1.6 money is paid by the script
    'mp_free_armor 0', 'mp_buy_anywhere 0', 'mp_death_drop_gun 1', 'mp_death_drop_defuser 1',
    'mp_solid_teammates 1', 'mp_display_kill_assists 0', 'mp_weapons_glow_on_ground 0', 'mp_randomspawn 0',
    'mp_anyone_can_pickup_c4 0', 'mp_plant_c4_anywhere 0', 'mp_defuser_allocation 0',
    'ammo_grenade_limit_flashbang 2', 'ammo_grenade_limit_default 1', 'ammo_grenade_limit_total 4',
    'sv_accelerate 5', 'sv_friction 4', 'sv_stopspeed 75', 'sv_airaccelerate 10',
  ],
  // names of the map's entities
  SCRIPT: 'cs16_script',
  HUD: 'cs16_hud',
  MAP_PARAMS: 'cs16_map_params',
  SOUND_PREFIX: 'cs16_snd_',
  TIMING: true,                // script time per tick in the console once a minute
  DEBUG: false,
  DEBUG_DAMAGE: false,         // every hit's CS2 and 1.6 damage in the console
};

const VERSION = '0.1.0';
// the 1.6 player models, rebuilt on CS2's player skeleton (tools/models.py)
const CLASS_MODELS_16 = {
  terror: 'models/player/cs16/terror/terror.vmdl', leet: 'models/player/cs16/leet/leet.vmdl',
  arctic: 'models/player/cs16/arctic/arctic.vmdl', guerilla: 'models/player/cs16/guerilla/guerilla.vmdl',
  urban: 'models/player/cs16/urban/urban.vmdl', gsg9: 'models/player/cs16/gsg9/gsg9.vmdl',
  sas: 'models/player/cs16/sas/sas.vmdl', gign: 'models/player/cs16/gign/gign.vmdl',
};
// CS2 agents for the same classes (MODELS_16: false, or if the 1.6 models are missing)
const CLASS_MODELS_CS2 = {
  terror: 'characters/models/tm_phoenix/tm_phoenix.vmdl',
  leet: 'characters/models/tm_leet/tm_leet_varianta.vmdl',
  arctic: 'characters/models/tm_balkan/tm_balkan_variantf.vmdl',
  guerilla: 'characters/models/tm_jungle_raider/tm_jungle_raider_varianta.vmdl',
  urban: 'characters/models/ctm_st6/ctm_st6_variante.vmdl',
  gsg9: 'characters/models/ctm_swat/ctm_swat_variante.vmdl',
  sas: 'characters/models/ctm_sas/ctm_sas.vmdl',
  gign: 'characters/models/ctm_gendarmerie/ctm_gendarmerie_varianta.vmdl',
};
const CLASS_MODELS = CONFIG.MODELS_16 ? CLASS_MODELS_16 : CLASS_MODELS_CS2;
