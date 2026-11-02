// ===================================================================================
// Nanite Temple: every tunable in one place. The core (src/core) has no engine calls and runs in Node for sims.
// ===================================================================================
const VERSION = '0.1.0';
const CONFIG = {
  APPLY_CVARS: true,          // servers that keep their own config set this false (chat: it is a const in the script)
  TAG: 'nanite',
  MIN_PLAYERS: 1,             // humans + bots needed to start a run; one player runs the vaults alone and the showdown ends on the clock
  DEV_COMMANDS: true,         // chat !skip clears the room you stand in (testing); turn off for the workshop release
  WAVE_GRACE: 3.0, WAVE_TRICKLE: 0.6,   // seconds after a squad lands before the first guardian wakes, and between wakings
  SPAWN_MIN_DIST: 560,        // guardians never rise closer than this to the entry plate
  TELEPORT_IMMUNITY: 2.5,     // seconds of guardian immunity after a teleport (not against players)
  SQUAD_MAX: 8, SQUAD_MIN: 1, SQUADS_MAX: 8,
  FLOORS: 3,                  // rooms per squad before the breach
  FLOOR_TIME: 150,            // seconds per room before the squad is pushed on (clears early when the room is cleared)
  LOBBY_WAIT: 12,             // seconds after round start before squads are sent out (freeze time + a breath)
  STAGING_TIME: 35,           // buy time in the staging room once every squad is through (or the clock runs out)
  SHOWDOWN_TIME: 240,         // the arena; barriers close every RING_EVERY seconds
  RING_EVERY: 45, RING_DAMAGE: 8,
  ROUND_PAD: 20,              // CS2 round clock runs this much longer than the game's own clock
  // enemies per room: base + per squad member, scaled by floor
  WAVE_BASE: 4, WAVE_PER_PLAYER: 1.5, WAVE_FLOOR_SCALE: [1.0, 1.35, 1.8],
  NANITES_PER_KILL: 150, NANITES_ROOM_CLEAR: 400, NANITES_START: 800, NANITES_PVP_KILL: 300,
  CLASS_DEFAULT: 'ninja',
  // classes: numbers the abilities use (the adapter turns them into teleports, velocity and damage hooks)
  NINJA_DASH: 256, NINJA_DASH_CD: 6, NINJA_STRIKE: 60,
  MONK_DOME_R: 128, MONK_DOME_T: 6, MONK_DOME_CD: 18, MONK_DOME_CUT: 0.7, MONK_ARMOR_GAIN: 0.25,
  CHRONO_T: 5, CHRONO_CD: 20, CHRONO_SPEED: 1.4, CHRONO_SAVE_HP: 50,
  PVP_DAMAGE_SCALE: 1.0,
  HUD_BUDGET: 600,
};
