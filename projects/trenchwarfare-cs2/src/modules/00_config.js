// mg_trenchwarfare.js - Western Front role manager (cs_script, no plugins)
// AI-generated (Claude) for skink52's mg_trenchwarfare addon.
//
// Roles: INFANTRY (fire trench, respawn, bolt rifle + pistol + knife, 3-kill streak -> Mondragon / Lewis gun, dressing stations heal),
//        MORTAR (5 crews x 2 per side: plot at the map table, fetch a bomb, load, fire; simulated shells with spread),
//        AIR (5 biplanes per side, arcade flight in third person; pilots posted on respawn or by !air, AIR_LIVES lives, then back to the ground).
// Bots are infantry; with few humans on a side the script runs some of them as pilots and mortar crews (85_ai). Everyone spawns in the briefing room and is sent to their post after a short delay.
//
// Map entities this script uses (all made by tools/make_map.py):
//   trench_<t|ct>_N (info_teleport_destination) infantry posts, facing the enemy
//   mortarpit_<t|ct>_K (info_target)            mortar tube position of crew K (1..5); place your mortar prefab there
//   mortarcrew_<t|ct>_K_a / _b (info_teleport_destination) crew seats: a = plotting table, b = ammunition box
//   heal_<t|ct>_N (info_target)                 dressing stations
//   plane_<t|ct>_N (info_teleport_destination)  biplane air-spawn points; tw_plane_<t|ct>_N (prop_dynamic) the aircraft
//   tw_hud (custom_hud_layout), tw_boom_fx_N / tw_dirt_fx_N / tw_boom_snd_N / tw_whistle_snd_N / tw_shake_N (effect pools),
//   tw_launch_snd_<tag>_K / tw_launch_fx_<tag>_K (per mortar pit); mortar_<tag>_K (prop_dynamic, fire animation; optional)
//   tw_whistle_attack (round-start whistle) and tw_plane_dive_1..N (dive sound pool): point_soundevents from tools/patch_sounds.py (optional)
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
    // dive sound (tw.plane_dive, 3 s): the nose PITCH degrees below the horizon at SPEED or more starts it on a free emitter of the pool
    // tw_plane_dive_1..EMITTERS (tools/patch_sounds.py), lent to the aircraft for LEN s; re-armed once the nose is back above REARM and
    // GAP s have passed. No free emitter (or a map without them): that dive is silent
    DIVE: { PITCH: 25, REARM: 10, SPEED: 900, GAP: 6, LEN: 3, EMITTERS: 4 },
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
          "mp_free_armor 0", "mp_solid_teammates 1", "mp_give_player_c4 0"],
  // ---- bots for low population (85_ai.js; docs/REVIEW_SCRIPT_1.md "Step 4"). CS2 bots are players: the script cannot steer their legs,
  // so infantry bots are PLACED (deploy targets, a leash) and the pilot / mortar roles are run by the script while the bot's pawn sits in
  // the seat. ON by default: the low-population requirement needs them, and the tw35 frame hitch came with the 44k-area nav that step 5
  // (woods seeds inside the fence) and tools/patch_nav.py (NONAV) cut down; false = bot_quota 0 + bot_kick (the tw35 behaviour).
  BOTS_ON: true,
  BOTS: {
    FILL_PER_SIDE: 8,          // bot_quota_mode fill, bot_quota 2 x this: bots fill the server to 16 players and leave as humans join (0 at 16+ humans)
    LEASH: 170, LEASH_Z: 160, LEASH_TIME: 3,   // a bot this close (dz) to a still-closed area's blocker for LEASH_TIME goes back to a post
    LEASH_AVOID: 400,          // the leash's post is at least this far from a closed blocker
    CHECK: 1.0,                // seconds between a bot's out-of-play checks
    NML_X: 1450, NML_Y: 2750, NML_ZMIN: -150,   // no man's land (tools/check_play.py T5): |x| < NML_X, |y| < NML_Y, above the galleries
    LOBBY_Z: -1500,            // a deployed bot below this is back in the briefing room
    FAR: 1500,                 // farther than this from every post (both sides), dressing station and opened area point: out of play
    OUT_TIME: 3,               // seconds out of play (no man's land, briefing room, far) before the bot goes back to a post
    COMBAT_GRACE: 6,           // the "far" check waits while the bot hurt or was hurt this recently
    FIRE_SHARE: 0.8,           // share of post deploys to the fire trench (the rest: the support trench)
    AREA_SHARE: 0.35,          // once an area is open, this share of bot deploys go to it (its sap head / ladder post or inside it)
    AREA_MAX: 4,               // at most this many bots of a side deployed into one opened area at a time
    // inside the opened areas (CT side; T mirrors x): tools/layout.py ground + 8 (woods clearing, the step-5 seeds) and the tunnel landing
    AREAS: {
      woodsopen: [{ x: 605, y: 3930, z: 10 }, { x: 1110, y: 3700, z: 10 }, { x: 1110, y: 4150, z: 6 }],
      // undergroundopen: [{ x: 2120, y: -3296, z: -252 }],  // off until the sap benches open with the unlock
      // (REVIEW_WORLD_2 W1: the user's benches seal the galleries unless deploy_tw runs with --user-h1 unlock|remove)
    },
  },
  AI: {
    MIN_HUMANS: 4,             // a side with fewer active humans than this gets script-run pilots and mortar crews (AFK humans do not count)
    PILOTS: 1, CREWS: 2,       // per side, bots permitting
    MAX_SHARE: 0.5,            // at most this share of a side's bots leave the infantry
    DIRECTOR_EVERY: 1.0,
    // pilot: patrols over the enemy line, gun and bomb runs on enemy infantry; slow to react and inaccurate on purpose
    CRUISE_ALT: 1000, MIN_ALT: 420, ARRIVE: 900, THINK: 0.25,
    STRAFE_RANGE: 3600, GUN_MAX: 2600, AIM_CONE: 12, REACT: 1.2, AIM_ERR: 0.03, ATTACK_TIME: 16, ATTACK_COOLDOWN: 8, BOMB_ERR: 300,
    // crew: one bot runs a tube alone at the table: plots a cluster of enemy infantry, "fetches and loads", fires
    CREW_THINK: 3, CREW_LOAD: 9, CREW_SIGMA: 160, CLUSTER_R: 420,
  },
  AFK: { PILOT: 60, CREW: 120 },   // seconds with no key, look or step: a pilot is brought down to the trench (infantry), a crew seat is freed
  ASSIST_MIN: 41,                  // the mortar loader's share of a hit is at least this much health damage when the victim can take it (assist)
  PERF_EVERY: 60,                  // seconds between "[tw] perf:" console lines (script time per tick, players, flights, shells, errors)
};
const T = 2, CT = 3;
const tagOf = (team) => (team === T ? "t" : "ct");
const enemyOf = (team) => (team === T ? CT : T);
const ROLE_NAME = { infantry: "INFANTRY", mortar: "TRENCH MORTAR CREW", air: "AIRCREW" };
