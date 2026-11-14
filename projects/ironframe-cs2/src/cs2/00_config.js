// ===================================================================================================================
// IRONFRAME CS2 adapter, part 0: CONFIG. Every tunable of the CS2 side in one place (the game rules live in the core and
// in PARTS; CONFIG.core overrides the core's defaults). A server may change these before compiling the script.
// ===================================================================================================================
const CONFIG = {
  TAG: 'ironframe',
  // ---- entity names (tools/vmap.py writes them; docs/INTERFACES.md section 7)
  SCRIPT: 'ifr_script', HUD: 'ifr_hud', PROP_TEMPLATE: 'ifr_tpl_prop', BOOTH: 'ifr_booth', MAP_PARAMS: 'ifr_map_params',
  MAIL_PREFIX: 'ifr_mail_', SOUND_PREFIX: 'ifr_snd_', PFX_PREFIX: 'ifr_pfx_', DROP_PREFIX: 'ifr_drop_', POINT_PREFIX: 'ifr_point_',
  // ---- cvars: APPLY_CVARS false lets a server keep its own settings (then set them in the server cfg); CVARS_ALWAYS are
  //      re-sent at every round start too (the minigame server re-runs its mode cfg 0.25 s after the map starts)
  APPLY_CVARS: true,
  CVARS_ALWAYS: [
    'mp_ignore_round_win_conditions 1', 'mp_respawn_on_death_t 1', 'mp_respawn_on_death_ct 1', 'mp_respawn_immunitytime 0',
    'mp_teammates_are_enemies 1',     /* 11 Nov 2026: at 0 a kill of a pawn on the pilot's own CS2 team was a team kill (no kill, -1): Skirmish, and every stand-in kill */ 'sv_gravity 0', 'sv_maxvelocity 6000', 'sv_disable_radar 1', 'mp_free_armor 0',
    'mp_buytime 0', 'mp_startmoney 0', 'mp_playercashawards 0', 'mp_teamcashawards 0', 'mp_death_drop_gun 0',
    'mp_solid_teammates 0', 'sv_disable_teamselect_menu 1', 'mp_autoteambalance 0', 'mp_limitteams 0',
    'mp_warmuptime 0', 'mp_warmup_pausetimer 0', 'mp_team_intro_time 0', 'mp_halftime 0', 'mp_match_can_clinch 0', 'mp_freezetime 0', 'mp_round_restart_delay 7', 'sv_disable_immunity_alpha 1',
    // the respawn wave (common.cfg: 10 s) kept killed pawns dead past the respawn watchdog, which then switched real kills off (no kill credit)
    'mp_respawnwavetime_t 0', 'mp_respawnwavetime_ct 0',
    // mp_timelimit 0 with mp_maxrounds 0 ENDS THE MATCH after round 1 (cs2-gotchas): CS2 then never starts round 2, its win panel
    // ("ROUND WON" / "ROUND LOST") stays over the HUD for good and only the script's RESTART_WAIT fallback keeps rounds going
    // (10 Nov 2026 playtest). A round limit nobody reaches keeps CS2's own round restart working.
    'mp_maxrounds 999',
  ],
  CVARS_ONCE: ['mp_roundtime 11', 'mp_maxrounds 999', 'mp_timelimit 0', 'mp_match_end_restart 0'],
  // ---- rounds: the core runs them; CS2's clock is kept ROUND_SLACK seconds longer; if CS2 doesn't end the round within
  //      ROUND_END_WAIT seconds of ours (warmup, a plugin), the next one starts anyway
  //      RESTART_WAIT: CS2 ended the round but no new round came this many seconds later (match end, a plugin): the script starts it
  ROUND_SECONDS: 600, ROUND_SLACK: 15, ROUND_END_WAIT: 20, RESTART_WAIT: 15, PODIUM_SECONDS: 12, INTRO_SECONDS: 6,
  // ---- camera per class (behind and above the mech's hip point; the boost camera pulls back BOOST_BACK more)
  // 10 Nov 2026 playtest ("hard to shoot up / down"): up raised 160 / 180 / 210 -> 215 / 250 / 290 so the mech's head sits ~10 deg under
  // the reticle instead of 2 deg; CAM_UP_ORBIT: degrees of up-look the camera still orbits, beyond it only the view turns (90_main.js)
  CAMERA: { light: { back: 460, up: 215 }, medium: { back: 520, up: 250 }, heavy: { back: 600, up: 290 }, boss: { back: 900, up: 560 } },
  CAM_UP_ORBIT: 28,   // 10 at first: aiming a little uphill already sank the mech behind the bottom HUD (10 Nov recording); at 28 the camera is still ~100 u over the feet
  CAM_BOOST_BACK: 120, CAM_ASSAULT_BACK: 80, CAM_SPEED_LAG: 0.25, CAM_RATE_TICKS: 2, CAM_MIN_STEP: 4, CAM_CLIP: true, CAM_CLIP_RETURN: 2.5,
  DEATH_CAM_SECONDS: 3, DEATH_CAM_RADIUS: 700, DEATH_CAM_UP: 320, SPEC_BACK: 700, SPEC_UP: 260,
  // ---- pawn ride (Dogfight): the invisible pawn is dragged after the mech by velocity, snapped beyond RIDE_SNAP
  RIDE_GAIN: 8, RIDE_MAX: 600, RIDE_SNAP: 400, RIDE_MAX_SPEED: 5800, RIDE_PAWN_UP: 36,
  // ---- rendering budgets
  SPAWN_BUDGET: 24, MAX_POOL: 900, FAR_DIST: 9000, HUD_BUDGET: 900, TELEPORT_DIST: 400,
  FX: { boom: 24, spark: 16, gboom: 8, beam: 16, tracer: 48, missile: 128, ring: 24, anchors: 16, soundsPerTick: 24, fxDist: 12000, sndDist: 7000 },
  // ---- frame auras (47_auras.js): tier 2 = every part + flares (humans' own mechs + the nearest fullCap within fullDist of a human),
  //      tier 1 = one idle part (next reducedCap within reducedDist), else none; props from the shared pool, at most maxProps
  //      and never within `reserve` of MAX_POOL; ghosts = afterimage / drain-beam one-offs alive at once
  AURA: { on: true, fullDist: 4000, reducedDist: 9000, fullCap: 40, reducedCap: 32, maxProps: 160, reserve: 60, claimsPerTick: 6, every: 16, poll: 4, ghosts: 12, hyst: 400 },
  // ---- hangar: the side each ifr_bay_N's preview camera sits on (yaw: 90 = +Y, -90 = -Y); bays not listed pick the clearest side
  BAY_CAMERA_YAW: { 1: 90, 2: 90, 3: 90, 4: 90, 5: 90, 6: 90, 7: -90, 8: -90, 9: -90, 10: -90, 11: -90, 12: -90 },
  // ---- AI fill as real CS2 bots when the map has a nav mesh (else the script's own AI mechs)
  CS2_BOTS: true,    // was off 13-14 Nov 2026: CS2 1.41.9.7 + MultiAddonManager 1.7.3 crashed the server a tick after a bot joined;
                     // MultiAddonManager 1.7.4 fixes it (14 Nov). If bots crash it again after a CS2 update, set false (STATUS).
  // ---- kill credit: CS2 score for a kill of the script's own AI mechs (they have no pawn, so no real kill); a killed human's pawn is
  //      revived by the script REVIVE_AFTER s after the kill (hidden in the booth) so the death orbit and the garage have a camera
  //      STANDIN_KILLS: a CS2 bot's pawn takes the kill for a destroyed AI mech (20_players.js npcKill), so it is a real CS2 kill
  NPC_KILL_SCORE: 2, REVIVE_AFTER: 1.5, STANDIN_KILLS: true, STANDIN_BACK: 0.5,
  // ---- input and chat
  CHAT_COMMANDS: true, SAY_GAP: 1.1, AFK_WARN: 60, AFK_SPEC: 90,
  // ---- server plugin channel (docs/SERVER_CONTRACT.md); SERVER_STATS and server mode are switched on by the plugin's inputs
  SERVER_STATS: false, PROTOCOL: 1, HELLO_EVERY: 60, SERVER_WAIT: 10, SRV_STATS_PER_TICK: 24,
  // ---- core overrides (IF_DEFAULT_CFG keys); empty = the core's own numbers (data/parts.json#move and DESIGN.md)
  core: {},
  // ---- diagnostics
  PERF_LOG: true, DEBUG: false,
};
