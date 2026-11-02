// puppet_brawl.js  -  PUPPET BRAWL, a 2-4 player 2.5D street fighter for CS2 maps (cs_script)
//
// Players stand on a control pad and press E. Their view switches to a side-on fight
// camera and a custom HUD, and they control a CS2 agent on a stage built in the map. Anyone
// else in the map can simply watch the fight happen on the stage.
//
// Each fighter is an invisible animation rig (models/puppet_brawl/rig/pb_rig.vmdl, holding
// every move as an animation) with a CS2 agent model bone-merged onto it. The hit boxes are
// the same skeleton the animations were made from, so what you see is what hits.
//
// Hammer setup (the mg_cs2_fighter map has all of this already):
//   point_script        pb_script        cs_script = scripts/puppet_brawl.vjs
//   info_target         pb_stage_left    left end of the fight line (as the camera sees it)
//   info_target         pb_stage_right   right end of the fight line
//   info_target         pb_pad_1 .. 4    where players stand to play (press E on one)
//   point_template      pb_tpl_timber / pb_tpl_brass / pb_tpl_pirouette / pb_tpl_motley
//                       each = prop_dynamic rig (pb_rig.vmdl) + prop_dynamic agent model with
//                       parent = the rig and Parent Attachment = !bonemerge (both Not Solid)
//   point_template      pb_tpl_ball      prop_dynamic models/puppet_brawl/pb_ball.vmdl (projectiles, sparks)
//   custom_hud_layout   pb_hud           layout = panorama/layout/custom_game/puppet_brawl.vxml
// Optional: pb_camera (fixed camera), pb_exit, pb_watch / pb_watch_1..8 (spectator spots),
//           point_soundevents pb_snd_hit / heavy / block / whiff / kd / special / ko / bell / tick / select / win
//
// CONTROLS  A/D move (hold away to guard)  W or SPACE jump  S or CTRL crouch
//           MOUSE1 punch  MOUSE2 kick  SHIFT block  R special (toward+R, down+R)  F throw
//           hold E to leave
// LOBBY     A/D pick a fighter, MOUSE1 ready, MOUSE2 un-ready. The first player in is
//           the host: R changes mode, F adds / clears CPU fighters.
//
// MODES     duel  - 1v1, winner stays on, everyone else queues at the back of the stage
//           teams - 2v2: pads 1-2 are RED, pads 3-4 are BLUE (uneven teams get extra health)
//           ffa   - up to 4 on stage at once, last fighter standing
//
// BUTTONS   func_button OnPressed -> pb_script -> RunScriptInput -> one of:
//           ModeDuel ModeTeams ModeFFA ModeNext  AddCPU RemoveCPU StopCPU  CpuEasy CpuNormal CpuHard
//           Start Reset  Join Leave Watch (these three use the activator)
//
// Console (sv_cheats 1): pb_status, pb_cpu_match, pb_stop (ends any CPU game), pb_join_host, pb_debug
//
// The fighters' moves, the game and the stage art are original; the bodies are CS2 agents.

// Only names that Valve's own example scripts import are imported here. A name the
// runtime module doesn't export would stop the whole script loading, so the HUD layout
// and player controller are recognised by their methods instead.
import {
  Instance, CSInputs, CSMoveType, CSGearSlot, CSWeaponType, CustomCameraMode,
  PointTemplate, BaseModelEntity,
} from "cs_script/point_script";

// ----- config ------------------------------------------------------------------------
const CONFIG = {
  // entity names (lookups also try a capitalised first letter)
  STAGE_LEFT: "pb_stage_left",
  STAGE_RIGHT: "pb_stage_right",
  STAGE_CENTER: "pb_stage",          // alternative to left/right: centre point, facing the audience
  STAGE_WIDTH: 900,                  // only used with pb_stage
  PAD_PREFIX: "pb_pad_",             // pb_pad_1 .. pb_pad_4
  WATCH_PREFIX: "pb_watch",          // spectator spots: pb_watch, pb_watch1..8 or pb_watch_1..8 (or any pb_watch*)
  EXIT: "pb_exit",                   // optional: where players are put when they leave
  CAMERA_ENTITY: "pb_camera",        // optional fixed camera position + angles
  HUD: "pb_hud",                     // custom_hud_layout
  TEMPLATES: { body: "pb_tpl_", ball: "pb_tpl_ball", fx: "pb_tpl_" },   // body: pb_tpl_<fighter id>; fx: pb_tpl_proj_knot, pb_tpl_fx_ring, ...
  // effects for the crowd: projectile models with trails, hit flashes, shockwave rings, stock CS2
  // particles on big moments, and a world-text announcer over the stage. false = plain glowing balls.
  FX: true,
  FX_PARTICLES: true,
  STAGE_TEXT: "pb_stage_text",       // point_worldtext: big line (ROUND 1, K.O., ...)
  STAGE_SUB: "pb_stage_sub",         // point_worldtext: small line (special move names, combos)
  SOUND_PREFIX: "pb_snd_",           // point_soundevent names: pb_snd_hit, pb_snd_ko, ...

  // world units per fighter unit. 0.72 shows the agents at their normal CS2 size (~72 tall)
  WORLD_SCALE: 0.72,
  DEPTH_SCALE: 1.0,
  FIGHTER_DEPTH: 4.0,                // spreads fighters in FFA across the stage depth
  QUEUE_DEPTH: -110,                 // fighter units: where the duel queue waits (behind the fight line)
  TEAM_GLOW: true,                   // 2v2: red / blue outlines on the fighters
  PARK_DROP: 1200,                   // unused parts wait this far below the stage floor

  // fight camera: "auto" follows the action, "fixed" uses pb_camera, "off" keeps first person
  CAMERA_MODE: "auto",
  CAMERA_FOV: 90,                    // CS2 horizontal FOV at 4:3
  CAMERA_ASPECT: 16 / 9,
  CAMERA_HEIGHT: 78,                 // fighter units above the floor
  CAMERA_LOOK_HEIGHT: 56,            // fighter units: the height the camera aims at
  CAMERA_MIN_DIST: 170,              // fighter units
  CAMERA_UNPARENT: true,             // the custom camera starts parented to the pawn

  // the players at the controls
  PAD_RADIUS: 52,                    // world units: how close to a pad you must be to join
  FREEZE_PLAYERS: true,              // MOVETYPE_NONE while playing
  WEAPONS: "strip",                  // "strip" remove & give back on leaving | "knife" hold the knife | "keep"
  PROTECT_PLAYERS: true,             // players at the controls can't be hurt
  HOLD_USE_TO_LEAVE: 0.6,            // seconds of holding E to leave
  REENTRY_COOLDOWN: 1.0,
  JOIN_HINT_EVERY: 8,                // ticks between "press E" hint checks

  // game rules
  DEFAULT_MODE: "duel",              // "duel" | "teams" | "ffa"
  ROUND_TIME: { duel: 60, teams: 99, ffa: 80 },
  MODES: ["duel", "teams"],          // what the MODE button cycles: "duel" 1v1 winner stays, "teams" tag team, "ffa" free-for-all
  TAG_TEAM: true,                    // teams: one fighter per side, partners tag in (SHIFT+R). false = all four fight at once
  TAG_COOLDOWN: 3,                   // seconds between tags
  ROUNDS_TO_WIN: 2,
  HEALTH_SCALE: 1.0,
  BACK_BLOCKS: true,                 // holding away from the opponent guards in place (false = SHIFT only, away walks back)
  PERFECT_BLOCK: true,               // guard just before a hit: no chip, quick recovery, +2 health
  PERFECT_WINDOW: 7,                 // frames (64 per second) the guard press may come before the hit
  CPU_LEVEL: 1,                      // 0 easy, 1 normal, 2 hard
  ANNOUNCE_IN_CHAT: true,            // match results in chat
  BUTTON_CHAT: true,                 // the map's host buttons say in chat what they did

  // server settings for a fighting map, run when the script starts and at every round start:
  // no bots, no round endings, respawning, no starting pistols. Set to [] to leave the server alone.
  ARENA_COMMANDS: [
    "bot_quota 0", "bot_kick",
    "mp_ignore_round_win_conditions 1", "mp_roundtime 60", "mp_roundtime_defuse 60", "mp_roundtime_hostage 60",
    "mp_freezetime 0", "mp_respawn_on_death_t 1", "mp_respawn_on_death_ct 1",
    "mp_t_default_secondary \"\"", "mp_ct_default_secondary \"\"", "mp_give_player_c4 0", "mp_buytime 0", "mp_death_drop_gun 0",
  ],
  BODY_YAW: 0,                       // degrees added to every fighter's facing (fix for a model that faces sideways)

  DEBUG: false,
};
// --------------------------------------------------------------------------------------
