// mg_trenchwarfare.js - Western Front role manager (cs_script, no plugins)
// AI-generated (Claude) for skink52's mg_trenchwarfare addon.
//
// Roles: INFANTRY (fire trench, respawn, bolt rifle + pistol + knife, 3-kill streak -> Mondragon / Lewis gun, dressing stations heal),
//        MORTAR (5 crews x 2 per side: plot at the map table, fetch a bomb, load, fire; simulated shells with spread),
//        AIR (5 biplanes per side, arcade flight in third person; pilots posted on respawn or by !air, AIR_LIVES lives, then back to the ground).
// Bots are always infantry. Everyone spawns in the briefing room and is sent to their post after a short delay.
//
// Map entities this script uses (all made by tools/make_map.py):
//   trench_<t|ct>_N (info_teleport_destination) infantry posts, facing the enemy
//   mortarpit_<t|ct>_K (info_target)            mortar tube position of crew K (1..5); place your mortar prefab there
//   mortarcrew_<t|ct>_K_a / _b (info_teleport_destination) crew seats: a = plotting table, b = ammunition box
//   heal_<t|ct>_N (info_target)                 dressing stations
//   plane_<t|ct>_N (info_teleport_destination)  biplane air-spawn points; tw_plane_<t|ct>_N (prop_dynamic) the aircraft
//   tw_hud (custom_hud_layout), tw_boom_fx_N / tw_dirt_fx_N / tw_boom_snd_N / tw_whistle_snd_N / tw_shake_N (effect pools),
//   tw_launch_snd_<tag>_K / tw_launch_fx_<tag>_K (per mortar pit); mortar_<tag>_K (prop_dynamic, fire animation; optional)
// The full list, with counts and who makes each name: docs/CONTRACT.md. Module map, build and tests: docs/SCRIPT.md.


// ------------------------------------------------------------------ settings
const CONFIG = {
  HUD: "tw_hud",
  RADAR: { x0: -4300, y0: 4700, span: 8601.6 },   // tools/make_radar.py region (overview pos_x/pos_y, 1024 px x scale 8.40)
  LOBBY_FIRST: 4.0,          // seconds in the briefing room on first spawn
  LOBBY_RESPAWN: 1.5,        // ... and after every respawn
  MORTAR_CHANCE: 0.4,        // chance a new player is put on a mortar crew (if a seat is free)
  ROTATE_CHANCE: 0.12,       // on respawn, chance to be moved to the other ground role ("a taste of everything")
  CREWS: 5,
  // WW1 weapons come from the addon's weapons.vdata (models, magazines): T Gewehr 98 = weapon_awp, Luger = weapon_glock;
  // CT Lee-Enfield = weapon_ssg08, Colt M1911 = weapon_hkp2000. Streak upgrade: T Mondragon = weapon_g3sg1, CT Lewis gun = weapon_scar20.
  INF_RIFLE: { 2: "weapon_awp", 3: "weapon_ssg08" },
  INF_PISTOL: { 2: "weapon_glock", 3: "weapon_hkp2000" },
  STREAK_UPGRADE: 3,                   // kills without dying -> upgrade
  UPGRADE: { 2: "weapon_g3sg1", 3: "weapon_scar20" },
  RIFLE_NAME: { 2: "Gewehr 98", 3: "Lee-Enfield" }, UPGRADE_NAME: { 2: "Mondragon self-loader", 3: "Lewis gun" },
  INF_ARMOR: 50,
  HEAL_RADIUS: 120, HEAL_HP_PER_S: 12, HEAL_ARMOR_PER_S: 25,
  STATION_RADIUS: 72,
  TARGET_EXT: 4600,                    // targeting map covers x, y in [-EXT, EXT] (render_top.py EXT); includes the wood
  TARGET_STEPS: 192,
  SIGHT_SPEED: 60, SIGHT_FINE: 14,     // steps per second
  SHELL_RADIUS: 330, SHELL_DAMAGE: 170, TRENCH_COVER: 0.35,
  SPREAD_BASE: 70, SPREAD_PER_UNIT: 0.035,
  FLIGHT_BASE: 2.2, FLIGHT_PER_UNIT: 1 / 1500,
  RELOAD_COOLDOWN: 2.0,
  MORTAR_FIRE_ANIM: "fire",
  FRIENDLY_SPLASH: false,
  POOL: 12,
  AMBIENT_MIN: 4, AMBIENT_MAX: 13, AMBIENT_CLEAR: 550,   // cosmetic no man's land bursts (seconds between, min distance to any player)
  AIR_ENABLED: true, AIR_SLOTS: 5, AIR_LIVES: 2,
  AIR_CHANCE: 0.12,          // on respawn, chance a ground player is posted to the aerodrome (if a plane is free; + merit, + first flight)
  // arcade flight (mouse aim: the plane turns toward where the pilot looks; W/S throttle, A/D roll, LMB guns, RMB bomb)
  AIR: {
    SPAWN_ALT: 1100, V_STALL: 420, V_MIN: 520, V_CRUISE: 1150, V_MAX: 1650, ACCEL: 0.6, DIVE_GAIN: 520,
    TURN_SLOW: 0.45, ROLL_SIGN: 1, PITCH_SIGN: -1, MODEL_YAW: 0,              // models' noses point at +x (Source pitch: positive = nose down)
    // tw33 flight feel ported from the Dogfight addon (steerAim / turnRate / flightStick / boundsWeight / anglesNear / cameraRay),
    // retuned for biplanes: the nose slerps toward the aim (proportional, capped by a speed-dependent turn rate), the bank comes
    // from the yaw rate, A/D add a free roll (no auto level) that never fights the mouse.
    STEER: { RATE: 62, REF_SPEED: 1150, MIN_SPEED: 300, MIN_RATE: 40, MAX_RATE: 75, GAIN: 4, PITCH_LIMIT: 75,
             BANK_GAIN: 0.8, BANK_MAX: 65, BANK_RATE: 150 },
    ROLL: { RATE: 120, IN: 0.15, OUT: 0.10 },
    BOUNDS: { AHEAD: 1.5, HARD: 600, HARD_Z: 400, FAR: 1500, HOME_Z: 2000 },     // soft walls = BOX_X / BOX_Y / ALT_MAX
    NOSE: 90, PULLUP_EVERY: 8, PULLUP_SECONDS: 1.5,
    GUN_GIMBAL: 3,                               // guns converge on the crosshair within this many degrees of the nose
    CAM_BACK_FAST: 440, CAM_TAU: 0.35, CAM_MIN_STEP: 4, CAM_EVERY: 2 / 64, CAM_SNAP: 6, CAM_RETURN: 0.3,   // camera eases back with speed
    GUN_AMMO: 500, GUN_RELOAD: 6, SMOKE_HP: 45,
    COCKPIT: { back: -40, up: 84 }, VIEW_DEFAULT: "chase",                     // "cockpit" also supported (camera at the pilot's head)
    BOX_X: 6500, BOX_Y: 5500, ALT_MAX: 5000, ALT_MIN: 120,
    GUN_INTERVAL: 0.09, GUN_DAMAGE: 16, GUN_RANGE: 5200, GUN_SPREAD: 0.014, GUN_FROM: 150,
    BOMBS: 2, BOMB_REARM: 18, BOMB_RADIUS: 420, BOMB_DAMAGE: 240, GRAVITY: 800,
    BSIGHT_RAISE: 260,                           // bomb-sight ring held this far above the landing point on the line to the camera (one-sided, faces the camera)
    HIT_SCALE: 0.4, HIT_MIN: 12,                 // rifle bullets on a plane: weapon damage x scale (at least HIT_MIN) to the pilot
    CRASH_CREDIT: 10,                            // seconds a hit keeps kill credit for a crash
    CAM_FOLLOW: { x: 0, y: 0, z: 70 }, CAM_OFFSET: { x: -380, y: 0, z: 70 },
    PILOT: { back: -46, up: 30 },                // (hidden) pilot pawn relative to the plane origin: in the cockpit
    TRACER_EVERY: 3, TRACER_SPEED: 9000, SIGHT_DIST: 1600, GUN_SOUND_EVERY: 2,   // effects: every Nth round a tracer / gun sound; gun-sight pip distance
  },
  // soldier player models (tools/soldiers.py; each precached by a hidden prop_dynamic tw_uniform_N under the lobby). Applied a moment
  // after every spawn, picked by player slot. UNIFORMS_ON false = stock agents; players can opt out with !uniform.
  UNIFORMS_ON: true, UNIFORM_DELAY: 0.25,
  UNIFORMS: {
    2: ["models/tw/players/tw_de_a/tw_de_a.vmdl", "models/tw/players/tw_de_b/tw_de_b.vmdl"],   // German
    3: ["models/tw/players/tw_gb_a/tw_gb_a.vmdl", "models/tw/players/tw_gb_b/tw_gb_b.vmdl"],   // British
  },
  // blocked areas opened during the round: every map entity with this targetname is blown open (removed + explosion) at whichever
  // comes first, enemy kills by anyone since the round started or seconds since the round started. Map entities return every round.
  UNLOCKS: [
    { name: "woodsopen", kills: 15, time: 240, msg: "THE WAY TO THE WOOD IS OPEN - ladder at the north end of the fire trench" },
    { name: "undergroundopen", kills: 30, time: 480, msg: "THE MINE GALLERIES ARE OPEN - saps at the south end of the support trench" },
  ],
  CVARS: ["mp_respawn_on_death_t 1", "mp_respawn_on_death_ct 1", "mp_respawn_immunitytime 0", "mp_freezetime 0",
          "mp_roundtime 60", "mp_buy_anywhere 0", "mp_buytime 0", "mp_death_drop_gun 0", "mp_weapons_allow_map_placed 1",
          "mp_free_armor 0", "mp_solid_teammates 1", "bot_quota_mode normal", "mp_give_player_c4 0"],
  // bots (infantry only; the map's nav seeds cover the lobby, trenches, woods clearings and tunnels): a bot that hangs around a
  // still-closed area's blocker (woodsopen / undergroundopen) for LEASH_TIME is sent back to a fire-trench post
  BOTS: { LEASH: 170, LEASH_Z: 160, LEASH_TIME: 3, LEASH_AVOID: 400 },   // LEASH_AVOID: the leash's post is at least this far from a closed blocker
  // off by default (their pathing over the 44k-area nav gave a frame hitch every ~0.5 s on a listen server); true = keep the server's bot_quota
  BOTS_ON: false,
  AFK: { PILOT: 60, CREW: 120 },   // seconds with no key, look or step: a pilot is brought down to the trench (infantry), a crew seat is freed
  ASSIST_MIN: 41,                  // the mortar loader's share of a hit is at least this much health damage when the victim can take it (assist)
  PERF_EVERY: 60,                  // seconds between "[tw] perf:" console lines (script time per tick, players, flights, shells, errors)
};
const T = 2, CT = 3;
const tagOf = (team) => (team === T ? "t" : "ct");
const enemyOf = (team) => (team === T ? CT : T);
const ROLE_NAME = { infantry: "INFANTRY", mortar: "TRENCH MORTAR CREW", air: "AIRCREW" };
