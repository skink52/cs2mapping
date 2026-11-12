// mg_monsoon - Conquest in a monsoon valley: infantry kits, helicopters you fly and ride, a howitzer battery against a rocket
// battery, five flags, tickets. cs_script only, no plugins. Rules: docs/DESIGN.md 3; names: docs/CONTRACT.md; HUD ids: docs/SCRIPT.md.
// Every tunable is in CONFIG. Units: Hammer units (40 u = 1 m), seconds, degrees.

const VERSION = "mv-0.5 (12 Nov 2026, review pass 3: bot balance)";

const CONFIG = {
  HUD: "mv_hud", PARAMS: "mv_params",
  LOBBY_FIRST: 10, LOBBY_RESPAWN: 5,     // seconds in the briefing room (first spawn / round start, later respawns)
  STATION_RADIUS: 80,                    // E range of kit racks, ammo racks, board seats
  PARK_XY: { x: 0, y: 0 },               // pooled props are parked at LAYOUT.map.park_z under this point
  SPAWN_PROTECT: 3,                      // seconds after deploying in which enemy damage is refused (ends early when the player fires)
  BASE_RADIUS: 1700,                     // "at the base" for an immediate role change (elsewhere a role request waits for the next deploy)
  AFK: { TIME: 120, MOVE: 48, EVERY: 1.0 },   // a human with no key, no look and no step for TIME s frees their seat and stops counting
  FEED: { LINES: 3, TIME: 6, UNDER_ATTACK: 20, TICKETS_LOW: [100, 50, 20] },   // event feed (HUD additions, pass 1); toasts stand in without it

  // ---- roles
  ROLES: {
    ARTY_CHANCE: 0.18,                   // chance a human with no preference is drawn into a battery seat (if one is free)
    AIR_CHANCE: 0.08, AIR_MERIT: 0.03, AIR_MERIT_MAX: 5, AIR_FIRST: 0.06,   // air slot draw on respawn: base + merit + never flown
    ROTATE_CHANCE: 0.04,                 // on respawn, chance a no-preference artillery player goes back to the infantry
    ARTY_CREW: 2,                        // seats per gun
  },

  // ---- infantry kits (DESIGN 3.1). Weapon classes are stock CS2; custom models come from weapons.vdata, never from the script.
  PISTOL: { 2: "weapon_glock", 3: "weapon_hkp2000" },
  KITS: {
    rifle:    { label: "RIFLEMAN",       weapon: { 2: "weapon_ak47", 3: "weapon_m4a1" },   name: { 2: "AK-47", 3: "M16A1" } },
    mg:       { label: "MACHINE GUNNER", weapon: { 2: "weapon_negev", 3: "weapon_m249" },  name: { 2: "RPD", 3: "M60" }, share: 0.25 },
    at:       { label: "ANTI-TANK",      weapon: { 2: "weapon_taser", 3: "weapon_taser" }, name: { 2: "RPG-7", 3: "M72 LAW" }, share: 0.25 },
    marksman: { label: "MARKSMAN",       weapon: { 2: "weapon_scar20", 3: "weapon_g3sg1" }, name: { 2: "SVD", 3: "M21" }, per: 8, flagOnly: true },
  },
  KIT_ORDER: ["rifle", "mg", "at", "marksman"],
  INF_ARMOR: 50, INF_HELMET: true,
  AT: { SPEED: 2200, GRAVITY: 60, BLAST: 180, DAMAGE: 120, HELI: 45, RELOAD: 25, LIFE: 5, GUN_DISABLE: 150, PROX: 44 },
  // rifle rounds on a helicopter, by weapon class (OnBulletImpact); anything else = DEFAULT
  BULLET_VS_HELI: { DEFAULT: 1.2, weapon_m249: 3, weapon_negev: 3, weapon_g3sg1: 2, weapon_scar20: 2 },

  // ---- uniforms: applied only when a cache prop mv_cache_1..16 holds that model (so a missing model is never set).
  // The four converted GMod player models (create/playermodels), copied into the addon at their own paths.
  UNIFORMS_ON: true, UNIFORM_DELAY: 0.25, CACHE_PROPS: 16,
  UNIFORMS: {
    2: ["models/player/gmod/nva_soldier/nva_soldier.vmdl", "models/player/gmod/vietcong_soldier/vietcong_soldier.vmdl"],
    3: ["models/player/gmod/soldier2_woodland/soldier2_woodland.vmdl", "models/player/gmod/us/us.vmdl"],
  },

  // ---- conquest (DESIGN 3.4)
  CONQUEST: {
    TICKETS: 500, DEATH_COST: 1, BLEED_FLAGS: 3, BLEED_SECONDS: 6, NEUTRAL_FIRST: false,   // holding BLEED_FLAGS+ bleeds 1 ticket / BLEED_SECONDS per flag over 2
    ROUND_SECONDS: 1200, CAPTURE_SECONDS: 15, CAPTURE_MAX: 3, DECAY: 0.05, CAP_HEIGHT: 260,
    TICK: 0.25,                           // seconds between flag presence checks
    END_DELAY: 6, RESTART_FALLBACK: 20, SELF_RESET: 40,   // TerminateRound delay; FireWinCondition fallback; the script restarts its own round
  },

  // ---- helicopters (DESIGN 3.2). Model numbers are in HELI_MODELS; offsets are in the NOSE frame: x forward, y left, z up,
  // origin on the ground under the mast.
  HELI: {
    COUNT: 3, HEALTH: 100, SMOKE_HP: 35, RESPAWN: 45, WRECK_TIME: 40, SPAWN_GUARD: 3, ABANDON: 45, FETCH: 3, LOSS_TICKETS: 0,   // FETCH: own pilot waits on the pad
    VS_MAX: 380, VS_EASE: 0.4, VS_SETTLE: 1.5,              // collective
    YAW_RATE: 70, YAW_GAIN: 3.5,                            // pedals: nose follows the eye yaw
    V_FWD: 900, V_BACK: 350, V_SIDE: 380, ACCEL: 0.7,       // cyclic: speed eases to the target at ACCEL / s
    TILT_PITCH: 18, TILT_ROLL: 14, TILT_ACC: 0.65, TILT_RATE: 40, PITCH_SIGN: 1, ROLL_SIGN: 1,   // Source pitch + = nose down
    GE_ALT: 120, GE_VS: 120,                                // ground effect
    LAND_TILT: 8, LAND_SPEED: 140, CRASH_BASE: 15, CRASH_DIV: 12, CRASH_KILL: 60,
    HIT_BASE: 5, HIT_DIV: 12, ROTOR_DAMAGE: 12, ROTOR_COOLDOWN: 0.5, ROTOR_MIN_ALT: 40, BODY_UP: 70, BODY_AHEAD: 140,
    SPINDOWN: 2.5, SPIN_RATE: 300, GRAVITY: 600, CRASH_CREDIT: 10, CRASH_BLAST: 300, CRASH_BLAST_DAMAGE: 80,
    PAD_RADIUS: 260, REPAIR_TIME: 8, REARM_TIME: 40,        // on the own pad: full health after REPAIR_TIME, all rockets after REARM_TIME
    BOARD_RADIUS: 300, BOARD_ALT: 90, ROPE_ALT: 450, ROPE_SPEED: 300, ROPE_DROP: 60, ROPE_FALL: 260, ROPE_SAFE: 3,
    BOUNDS: { HARD: 600, AHEAD: 1.5, HOME_SPEED: 500 },     // soft box = LAYOUT.map.air; HARD beyond it destroys
    CAM: { BACK: 420, UP: 110, BACK_FAST: 560, TAU: 0.5, MIN_STEP: 6, EVERY: 2 / 64, RETURN: 0.3 },
    ROCKET: { SPEED: 2600, GRAVITY: 120, BLAST: 300, DAMAGE: 150, HELI: 90, PAIR_INTERVAL: 0.6, LIFE: 6,
              GIMBAL_YAW: 8, GIMBAL_UP: 6, GIMBAL_DOWN: 35, GUN_DISABLE: 260 },
    HIT_RADIUS: 150, HIT_UP: 80,                            // sphere used for hitscan / projectile hits on a helicopter
    TRACER_EVERY: 3, TRACER_SPEED: 9000, SOUND_EVERY: 2,
    ROTOR_RPM: 1100,                                        // degrees per second of the Hip rotor props at full speed
    SPOOL: 3.0,                                             // seconds for the rotor to spin up / down
    AUTOLAND_VS: -200,                                      // a helicopter left without a pilot in the air settles at this rate
    DUST_ALT: 220,
  },
  // The numbers below are DEFAULTS. The map generator exports the models it was built with as LAYOUT.models (tools/mv_models.py:
  // nose yaw, rotor radius, hub, seats, exits, pods, gun muzzle / camera per helicopter) and heliModel() overwrites these with them,
  // so a model swap is a change in mv_models.py only. Defaults here = the converted Mi-8 (measured from its SMDs, 12 Nov 2026).
  HELI_MODELS: {
    // CC-BY Apache (tools/apache_setup.py -> out/apache.json -> LAYOUT.models.apache)
    apache: {
      label: "AH-64", HEALTH: 100, NOSE_YAW: -90, ROTOR_R: 303, ROTOR_Z: 156, ANIMATED: true, ANIM_INPUT: "SetAnimation",
      ANIMS: { off: "idle", slow: "spin_slow", full: "spin" },
      SEATS: [{ kind: "pilot", off: [58.6, 0, 68.5] }, { kind: "gunner", off: [109.3, 0, 50.9] },
              { kind: "rider", off: [-4.6, 79.3, 80.2] }, { kind: "rider", off: [-4.6, -79.3, 80.2] }],
      EXIT: [[40, 150, 0], [40, -150, 0], [-60, 170, 0], [-60, -170, 0]],
      ROCKETS: 12, REARM_TIME: 50, PODS: [[27.1, 63.6, 59.6], [27.1, -63.6, 59.6], [27, 95, 60], [27, -95, 60]],
      GUN: { name: "M230 30 MM", muzzle: [153, 0, 27.2], cam: [118, 0, 74], yaw: 0, cone: 110, up: 15, down: 60,
             interval: 0.1, damage: 24, heli: 2.5, range: 5200, spread: 0.012, overheat: 6, cool: 4, belt: 120, reload: 5 },
    },
    // Mi-8 slick: pilot left seat, PK in the open left door, four riders on the cabin floor (floor z 30, cockpit floor z 40)
    hip: {
      label: "Mi-8", HEALTH: 170, NOSE_YAW: 0, ROTOR_R: 418, ROTOR_Z: 149.5, ANIMATED: false, HUB: [0, 0, 149.46], TAIL: [-513.2, 22.21, 157.27],
      SEATS: [{ kind: "pilot", off: [176, 22, 56] }, { kind: "gunner", off: [119, 30, 46] },
              { kind: "rider", off: [62, 22, 46] }, { kind: "rider", off: [62, -22, 46] }, { kind: "rider", off: [4, 22, 46] }, { kind: "rider", off: [4, -22, 46] }],
      EXIT: [[119, 140, 0], [60, 140, 0], [180, 140, 0], [0, 140, 0], [-110, 140, 0], [-170, 140, 0]],
      ROCKETS: 0, PODS: [],
      GUN: { name: "PK DOOR GUN", muzzle: [119.5, 74, 61.5], cam: [119, 44, 78], yaw: 90, cone: 60, up: 25, down: 60,
             interval: 0.09, damage: 32, heli: 2, range: 4800, spread: 0.014, overheat: 8, cool: 4, belt: 200, reload: 4 },
    },
    // Mi-8 gunship: six UB-16 pods on outriggers (fired in left / right pairs), the same door gun, two riders
    hip_gun: {
      label: "Mi-8TV", HEALTH: 160, NOSE_YAW: 0, ROTOR_R: 418, ROTOR_Z: 149.5, ANIMATED: false, HUB: [0, 0, 149.46], TAIL: [-513.2, 22.21, 157.27],
      SEATS: [{ kind: "pilot", off: [176, 22, 56] }, { kind: "gunner", off: [119, 30, 46] },
              { kind: "rider", off: [62, 22, 46] }, { kind: "rider", off: [62, -22, 46] }],
      EXIT: [[119, 175, 0], [180, 175, 0], [60, 175, 0], [0, 175, 0]],
      ROCKETS: 40, REARM_TIME: 30, PODS: [[57, 104, 35], [57, -104, 35], [57, 124, 35], [57, -124, 35], [57, 83, 35], [57, -83, 35]],
      GUN: { name: "PK DOOR GUN", muzzle: [119.5, 74, 61.5], cam: [119, 44, 78], yaw: 90, cone: 60, up: 25, down: 60,
             interval: 0.09, damage: 32, heli: 2, range: 4800, spread: 0.014, overheat: 8, cool: 4, belt: 200, reload: 4 },
    },
  },
  WRECK_YAW: 0,                           // added to the nose yaw when the crash hulk is put down (LAYOUT.models.wreck.yaw overrides)
  HELI_KINDS: { 2: ["hip", "hip", "hip_gun"], 3: ["apache", "apache", "apache"] },

  // ---- artillery (DESIGN 3.3)
  ARTY: {
    GUNS: { 2: 4, 3: 3 }, MAX_LOAD: { 2: 4, 3: 1 }, SHELLS: { 2: ["rocket"], 3: ["he", "smoke", "beehive"] },
    SHELL_NAME: { he: "HE", smoke: "WP SMOKE", beehive: "BEEHIVE", rocket: "HE ROCKET" },
    SIGMA: { 2: [70, 0.035], 3: [30, 0.02] },             // spread sigma = a + b x range
    FLIGHT_BASE: 2.4, FLIGHT_PER_UNIT: 1 / 1700, WHISTLE: 2.0, FALL_TIME: 1.2, FALL_HEIGHT: 2600,
    HE_RADIUS: 360, HE_DAMAGE: 190, COVER: 0.5, HELI_RADIUS: 260, HELI_DAMAGE: 70, FRIENDLY_SPLASH: false,
    SMOKE_TIME: 25, SMOKE_RADIUS: 200,
    BEEHIVE: { RANGE: 900, CONE: 25, DAMAGE: 60, HELI: 30 },
    SALVO_INTERVAL: 0.8, COOLDOWN: 1.5,
    LAY_MIN: 0.5, LAY_MAX: 3, LAY_RATE: 40,              // seconds = angle change / LAY_RATE, clamped
    ELEV_MIN: 12, ELEV_MAX: 62, RANGE_MAX: 13000, RECOIL: 26, RECOIL_TIME: 0.7,
    BREECH_RADIUS: 110, CARRY_SPEED: 0.75, RUN_SPEED: 250, SOLO_RELOAD: 4.0,   // a lone crew waits SOLO_RELOAD after firing (half rate)
    DISABLE_RADIUS: 260, DISABLE_TIME: 40, REPAIR_HOLD: 6, DISABLE_PUFF: 4, REPAIR_GRACE: 15,   // GRACE: a gun just back in action can't be silenced again
    FLASH_DELAY: 3, FLASH_TIME: 12, FLASH_MAX: 4,
    MISSION: { HOLD: 1.2, MIN_DIST: 400, MAX_DIST: 9000, TIME: 45, PER_TEAM: 5, ASSIST_RADIUS: 320, ASSIST_TIME: 15, LOCK_RADIUS: 200 },
    SHARE_MIN: 55, SHARE_FRAC: 0.4,                       // loader / observer non-lethal share (assist), as mg_trenchwarfare
    IMPACTS_SHOWN: 3,
  },
  BOARD: { EXT: 6400, STEPS: 160, SPEED: 44, FINE: 10, CEP_STEP: 60, CEP_MAX: 8 },   // reticle steps per second

  // ---- emplaced guns (mv_mount_N). kind:team comes from LAYOUT.mountinfo (build copies the mv_mountinfo_N message keys;
  // a script cannot read keyvalues) or, without it, from where the gun stands (see mountInfo()).
  MOUNT: {
    USE_RADIUS: 70, CONE: 30, CONE_ANY: 180, UP: 35, DOWN: 20, RANGE: 5200, BASE_RADIUS: 1500, CAM: { back: 64, up: 22 },
    MUZZLE: 40,                          // pintle to muzzle; LAYOUT.models[kind].muzzle (the model the map uses) overrides it per kind
    KINDS: {
      m2:     { name: "M2 .50 CAL", interval: 0.11, damage: 40, heli: 4, spread: 0.010, overheat: 6, cool: 4, belt: 100, reload: 4 },
      dshk:   { name: "DShK 12.7",  interval: 0.10, damage: 40, heli: 6, spread: 0.011, overheat: 6, cool: 4, belt: 100, reload: 4 },
      quad50: { name: "QUAD .50",   interval: 0.045, damage: 25, heli: 3, spread: 0.018, overheat: 6, cool: 4, belt: 240, reload: 6 },
    },
    MAX: 16,
  },

  // ---- effect pools (CONTRACT)
  POOL: { BOOM: 16, TRACER: 24, ROCKET: 16, MARKER: 10, SMOKE: 6, SHELL: 12 },
  TRACER_LEN: 5200,

  // ---- bots and AI (low population). CS2 bots are players: the script cannot steer their legs, so infantry bots are placed
  // (deploy point, leash) and the vehicle / battery roles are simulated by the script while the bot's pawn sits in the seat.
  BOTS_ON: true, BOT_QUOTA: 10, BOT_QUOTA_MAX: 24, BOT_QUOTA_MODE: "fill", BOTS_CHAT: true, BOT_KITS: true,
  BOTS_VOTE: 30,                         // !bots <n>: more than half of the humans must ask for the same n within this many s (one human alone: at once)
  AI: {
    MIN_HUMANS_FOR_ROLES: 4,             // a team with fewer humans than this gets AI pilots / gunners / crews
    PILOTS: 1, GUNNERS: 2, CREWS: 1,     // how many of each per team (bots permitting)
    MAX_ROLE_SHARE: 0.5,                 // at most this share of a team's bots leave the infantry
    DIRECTOR_EVERY: 1.0,
    LEASH_IDLE: 20, LEASH_MOVE: 60, LEASH_CHECK: 1.0, BAND_MARGIN: 80, BAND_Z_UNDER: 260, COMBAT_GRACE: 10,
    // pilot
    CRUISE: 520, CRUISE_SPEED: 0.6, ARRIVE: 700, LOOKAHEAD: 2.5, REACT: 1.5,
    STRAFE_RANGE: 2600, STRAFE_FIRE_MAX: 2000, STRAFE_FIRE_MIN: 650, STRAFE_PAIRS: 3, STRAFE_COOLDOWN: 14, STRAFE_ALT: 420,
    ROCKET_SPREAD: 0.035, AIM_YAW: 7, RTB_HP: 50, PAD_HOLD: 4, WAIT_BOARD: 6,
    REARM_GO: 0.6,                       // an AI pilot on its pad lifts off once repaired with this share of its rockets back (review 3: it waited for all)
    MOUNT_AVOID: 0.2,                    // weight of a patrol flag inside the arc of an enemy-manned emplaced gun (review 3)
    // gunner
    GUN_RANGE: 3200, GUN_RETARGET: 0.5, GUN_REACT: 0.9, GUN_SPREAD: 0.025, GUN_BURST: 1.2, GUN_PAUSE: 1.1,
    // battery
    AT_RANGE: 2000, AT_FIRST: 8, AT_SPREAD: 0.08, AT_EVERY: 1.0, AT_BOTS: 2,     // the bot AT man: rockets at flying helicopters in range, this inaccurate
    // team plan for the infantry bots' deploy points (85_ai teamPlan, review 3): weight per flag = what it is worth x exp(-distance
    // from the side's nearest deploy point / REACH); a deploying bot is sent where the plan is shortest (weight share x bots - bots sent)
    PLAN: { EVERY: 1.0, DEFEND: 3, GARRISON: 0, NEUTRAL: 1.5, ATTACK: 1.0, REACH: 3000, PUSH: 3, BLEED_PUSH: 4, FLOOR: 0.05, HUB: 0, HUB_EXP: 3, PACE: 2, PACE_MIN: 0.5, PACE_MAX: 2, SAFE: 1150, SAFE_FRIEND: 0, SAFE_BLED: 1150, SAFE_CROWD: 400 },
    CREW_LOAD: 11, CREW_THINK: 2.0, CREW_EXTRA_SIGMA: 30, CLUSTER_MIN: 2, CLUSTER_RADIUS: 320, CLUSTER_FLAG: 900, MARK_AGE: 6,
  },

  // ---- ambience: cosmetic bursts far from every player
  AMBIENT: { ON: true, MIN: 14, MAX: 40, CLEAR: 1500 },

  HUDCFG: { ASI_MAX_KMH: 100, OBJ_EVERY: 0.25, STATUS_EVERY: 16 },   // STATUS_EVERY: ticks between status-box rebuilds
  PERF_LOG: 60,                          // seconds between script-time lines in the console

  CVARS: ["mp_respawn_on_death_t 1", "mp_respawn_on_death_ct 1", "mp_respawn_immunitytime 0", "mp_respawnwavetime_t 0", "mp_respawnwavetime_ct 0",
          "mp_freezetime 0", "mp_roundtime 21", "mp_ignore_round_win_conditions 1", "mp_buy_anywhere 0", "mp_buytime 0",
          "mp_death_drop_gun 0", "mp_weapons_allow_map_placed 1", "mp_free_armor 0", "mp_solid_teammates 1", "mp_give_player_c4 0",
          "mp_playercashawards 0", "mp_teamcashawards 0", "mp_startmoney 0", "mp_maxmoney 0", "mp_afterroundmoney 0", "mp_autoteambalance 1"],
};
