# Hellmatch CS2 (formerly FreeDM Arena) — current status and handover (18 Oct 2026, 19:05 Adelaide)

Repo: https://github.com/skink52/hellmatch-cs2 (renamed from freedm-cs2 by Zach 17 Oct; source only). Build: `FREEDOOM_DIR=/path/to/freedoom sh tools/build_all.sh`
rebuilds the addon into out/addon (FREEDOOM_DIR not needed when the freedoom checkout is inside the repo).
Always rebuild the map from Zach's latest Hammer save: `FDM_CURRENT_VMAP=<his mg_hellmatch.vmap>` keeps his edits.
Renamed 17 Oct 09:05: public name Hellmatch, map mg_hellmatch (tools/names.py). Internal names stay: addon folder
mg_freedm, maps/scripts/freedm.js, panorama freedm.xml/css, fdm_* entities, models/materials/sounds under fdm/.

Zach's addon: `C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\content\csgo_addons\mg_freedm`
(PC linked to the chat). Changed files are written straight into it, only the files that changed. Zips only for bulk
model/material updates, and zips must NEVER contain maps/mg_hellmatch.vmap or maps/scripts/freedm.js (that overwrote a
newer script once). DELIVERY CHECK: the device write copies a delayed snapshot of /mnt/user-data/outputs, so a
write straight after `cp` can send the PREVIOUS version (happened 16 Oct: the 09:49 script landed hours late).
Copy, wait ~20 s, write, then stage the file back and compare sha1 before telling Zach it's there.
After a script/HUD change Zach must fully reload (`disconnect`, run the map again) so the script
and Panorama files recompile. Zach doesn't code: plain-language explanations, light code comments.

## Current version (16 Oct 09:50) — confirmed working in CS2 by Zach
- Map builds; script loads (`[freedm] v0.1.0 ready: 32 levels, 190 sprite models, HUD on, prop template on`).
- All 32 FreeDM levels render with correct textures, sky, animated water/slime/lava.
- Doom movement, doors, lifts, teleporters, pickups, all weapons, Doom HUD (status bar, face, numbers, weapon sprite,
  message line, top-right mode/score lines, centre messages).
- Modes: free-for-all, team deathmatch, team elimination, last man standing; up to 4 arenas, 16 per arena.
- Every Doom frag is a real CS2 kill (killfeed + scoreboard); CS2 bots play with the Doom bot AI (BOT_SKILL 0.35).
- CS2 round winner: the script fires FireWinCondition on `fdm_map_params` (info_map_parameters in the map) when the
  Doom round ends; T/CT round score ticks (confirmed 09:26). Side that won more arenas wins; FFA arena counts for
  the winner's side.
- Own body hidden (eye 15 units ahead).
- Chat commands (all confirmed): `!afk`, `!back`, `!spec`, `!doom`, `!hud`.
  - `!doom`: controls shown for 8 s on the typing player's own screen only (no chat broadcast).
  - `!hud`: per-player status bar size, cycles normal (85%, default) -> classic (100%) -> small (65%);
    `!hud normal|classic|small`. Status bar stays centred.
- Round messages in chat ("DOOM: <mode> - <maps>", "<map>: <result>", "DOOM round over - ..."), paced 1 s apart.
- TDM top-right line shows "TEAM DEATHMATCH - FIRST TO N" (was cut off before).
- Lobby status for players not in an arena: waiting for players n/2, starts in / after freeze time, Doom round time
  left, arena scores cycling every 3 s, AFK / join T or CT hints (Doom HUD text lines only, class Lobby on fdm_root).
- MIN_PLAYERS 2 (bots count); `!body` test command removed.
- Console diagnostics: `[freedm] chat command ...`, `[freedm] FireWinCondition <reason> (arenas won: T a, CT b)`,
  `[freedm] CS2 round ended: T win / CT win`, `[freedm] CS2 kill: killer (team, score) -> victim` for kills
  involving a human, and a warning when frags are skipped because of warmup.

## Update 16 Oct 15:10 (script + README_FREEDM.md written and verified by sha1)
- Scoreboard kills breaking when people join mid-game: found and fixed. When anyone between a scripted CS2 death
  and the CS2 respawn left the arena (CS2 kicking a bot to make room for a joining human, slot reuse, team change,
  disconnect), the 8 s respawn check failed and switched real kills off for the whole map. Now pending kills are
  dropped for leavers, kills by a leaver go to the world (a newcomer in the same slot never gets the credit), the
  check ignores anyone who left, and real kills only switch off after 3 genuine failures in a row.
- Team split bug (old): each arena's T share was computed from the Ts still unassigned, so with 32T/32CT the
  arenas came out 8v8, 6v10, 5v11, 13v3. Now worked out from the totals: even teams.
- One mode for every arena: picked so the smallest arena qualifies, and a team mode only when every arena gets
  both sides (else re-picked without team modes). mp_teammates_are_enemies is 1 whenever any arena has no teams.
- Arena sizes (15:50, Zach's rule): one arena up to 15, two from 16 (8+8 .. 16+15), four from 32 (8 each .. 16 each),
  always even (ARENA_MIN 8). Never 3 arenas.
- FINISH_GRACE 120: once the first arena finishes, the rest get 2 minutes (centre "120 SECONDS LEFT", top-right
  clock), then the leader wins.
- Weapon starts (15:50): rolled PER ARENA, LOADOUT_CHANCE 0.12 each; START_WEAPONS weights shotgun 3, ssg 3,
  chaingun 3, rocket 2, plasma 2, chainsaw 2, bfg 1, with extra ammo (rockets 25, cells 200, bullets 200, shells 30);
  given on every (re)spawn. Round chat line lists it per map; bottom line shows it during the countdown.
- Round-start hitch fixed (15:50): arenas are planned at round start and built one per Doom tic (core
  staggerArenas, events arenaBuilt -> onArenaBuilt parks that arena's players); HUD changes capped at HUD_BUDGET 600
  per server tick; new props capped at SPAWN_BUDGET 20 per tick. Mock: 64 players max ~20 ms (was 128 ms),
  10 players max 13 ms (was 22 ms). Players waiting for their arena have status 'planned'.
- Chat commands accept `/` as well as `!` (/doom, /hud, /afk, /back, /spec).
- AFK notice is no longer said in chat; the AFK player's own HUD shows "AFK - TYPE !BACK TO PLAY".
- Console: `[freedm] round N: <mode>[ + loadout], arenas <mode>:<players> ...`.
- Tests: test/mock_cs2.mjs `churn` option (joins with bot kicks and slot reuse, team swaps, leavers, CS2-style
  scoreboard incl. teamkill -1). 64 players, 700 s: kills stayed on, 0 teamkill penalties, modes consistent.
  test/sim.cjs shows rounds of ~2-6 minutes with 64 bots. Script cost ~4 ms per server tick at 64 players in Node,
  spikes up to ~50-90 ms at round start (arena build) — real CS2 cost unknown, watch "point_script thinking for".

## Update 16 Oct 17:15 (script, HUD xml/css, loading/radar/icon images, README; overview txt in the GAME folder)
- Late joiners: when no arena has room (all full, or one-life round) a human takes a CS2 bot's place
  (RoundManager.replaceBot; REPLACE_BOTS). Respawn rounds: a dead / lowest-frag bot of the joiner's team leaves and
  the human spawns fresh. One-life rounds: the human takes over a living bot's marine (health, weapons, spot).
  The bot spectates. CS2 respawning now stays ON in one-life rounds when REPLACE_BOTS is on, so a joiner gets a
  pawn (Doom deaths there only reach CS2 at round end, so nothing else changes). Console: "<name> took <bot>'s place".
- Spawns in walls fixed: 32 of 305 deathmatch starts sat exactly against a wall (our collision = stuck); every start
  is moved clear at level load (Arena.fitSpot), respawns step to the nearest clear spot, the unchecked team "jitter"
  at round start is gone, crowded starts fall back to other starts. Before: 14% of spawns stuck in a 64-bot test;
  after: 0 in ~6,500. fitSpot only accepts spots reachable in a straight line (walkableLine) inside the level
  outline - an earlier version could pick a point behind the outer wall (void) and a marine walked out of the map.
  Safety net: Arena.rescueOutside teleports anyone outside the level outline back to a spawn spot (every 32 tics).
- Bots stuck either side of a wall: not the camera (bots have none; EYE_FORWARD only affects spectators watching
  them). Cause: bots with nobody in sight walked straight at the nearest enemy when the route finder had no path
  or the enemy was round a corner in the same sector. Now bots only hunt enemies they can reach (route, or in
  sight), otherwise items / a random reachable start; blocked for ~1 s -> turn away 2 s and skip that enemy a few
  seconds; blocked by a player -> step away from them. Stuck 5 s+ without a target: 79 -> ~15 per 4 rounds.
  Route answers cached per level. Bot logic costs ~0.37 ms per tic for 64 bots (unchanged); zero without bots.
- Loading screen + radar + icon (tools/loading.py, part of build_all.sh): FreeDM title art + logo + controls in the
  Doom font (map_icons/screenshots/1080p/mg_freedm.png), a Doom-automap overview of all 32 levels as a flat PSD
  (overheadmaps/mg_freedm_radar.psd), a white map icon (map_icons/map_icon_mg_freedm.svg), and
  game/csgo_addons/mg_freedm/resource/overviews/mg_freedm.txt (pos_x -15856, pos_y 10458, scale 29.188).
  The HUD stylesheet references the images from hidden panels so CS2 compiles them with the HUD.
  20:44 test: icon shows on the loading screen and all three compiled, but the loading screen kept CS2's default
  art - it cycles NUMBERED screenshots (Valve maps have <map>_1.._4 plus the plain one). Added mg_freedm_1.png
  (controls) and mg_freedm_2.png (overview + modes), both preloaded too. Recheck.
  No in-game minimap is expected: sv_disable_radar 1 stays (CS2 pawns sit parked in the booth, so the radar would
  show everyone there, not their Doom positions).
  NOT YET VERIFIED IN CS2: check the "Failed loading resource ... overheadmaps / screenshots / map_icon" and
  "CMapOverview::SetMap" lines are gone and the loading screen shows the picture.
- Scoreboard: per-player option `!hud scores` hides the Doom HUD while the scoreboard (or end-of-match) is open;
  default keeps it (HIDE_HUD_ON_SCOREBOARD false). Panel fdm_opts (class hidescores) wraps fdm_root.
- Note for tools: the output folder adds C2PA "content credentials" metadata to PNG/SVG files; pixels/shapes unchanged,
  so compare those two by content, not sha1.

## Update 17 Oct 00:30 - seeing through walls when pressed against them
Cause: the eye sits 15 units ahead of the player centre (keeps the own marine model out of view) and the player's
collision radius is 16, so against a wall the camera is ~1 unit from it - closer than CS2's near clip plane, which
cuts the wall away. Scripts can't change the near plane or hide a prop per player. Fix in the level meshes
(tools/convert.py, WALL_BACKING 16): every one-sided wall gets a hidden copy up to 16 units behind it in the void
(1.5 short of whatever is behind, shrunk/dropped if it would cross another line - checked: 9,539 copies, none
crossing). Same unlit material, so through the clipped area you see wall. Simulated camera pressed against walls:
see-through ~99% -> <1% (assumed near plane 4 or 7). Render-only (no physics). Model names, props and level data
unchanged, so the map needs no edit; 233 level .smd files written to the addon (spot-checked 8 by content).
Zach must rebuild the map in Hammer (models recompile) before uploading. Not yet tested in CS2.

## Update 17 Oct 08:30 - music, no money, own title art, Workshop images
Written to the addon and verified (sha1; PNGs by pixels, MP3s by decoded audio - the outputs folder adds a metadata
block to PNG/MP3 headers): maps/mg_freedm.vmap (rebuilt from Zach's 16 Oct 08:01 Hammer save, kept as
ref/mg_freedm_hammer_saved_5.vmap; only change: 9 music point_soundevents), maps/scripts/freedm.js,
soundevents_addon.vsndevts, sounds/fdm/music/*.mp3 (9), the three loading screenshots, README_FREEDM.md,
TESTING_FREEDM.md, MUSIC_CREDITS.txt; GAME folder: MUSIC_CREDITS.txt, README_FREEDM.md.
- Music (Zach picked "classic, improved FM" from a 3-way test render): FreeDM's own level tracks rendered from MIDI
  with libADLMIDI (Nuked OPL3, DMXOPL3 bank by Sneakernets, MIT), loudness-matched to -16 LUFS, MP3 128k, 22 MB.
  tools/music.py (cache in build/music; tools/get_adlmidi.sh builds the renderer). Long pool for respawn rounds
  (FFA/TDM): DM05 Music for Freedoom 9, DM10 Paranoia, DM17 Panic, DM21 Friendly Fire, DM26 World of Pain (3-4 min).
  Short pool for one-life rounds (elim/LMS): DM02 Descent from Grace, DM14 The Heroic Battle, DM23 Shells,
  DM29 SevenFour (75-103 s). Sound events fdm_music.<id> are type csgo_music (everyone hears it, scaled by each
  player's snd_musicvolume), volume 0.7 (tools/extras.py MUSIC_VOLUME). Map: point_soundevent fdm_mus_<id> in the
  lobby (vmap_env.py, group fdm_env). Script src/cs2/55_music.js: shuffled playlist per round, next track 2 s after
  one ends (MUSIC_GAP), StopSound at round end / cleanup; console "[freedm] music: DM.. <title>". CONFIG.MUSIC.
  Players joining mid-track hear music from the next track. Not yet heard in CS2: the volume level, and whether a
  csgo_music event started from a lobby point_soundevent reaches everyone.
- Kill money off: CVARS_ALWAYS adds mp_playercashawards 0, mp_teamcashawards 0, mp_startmoney 0, mp_maxmoney 0.
- Freedoom endorsement check (Freedoom's BSD licence: keep the notice in docs; don't use the Freedoom name to
  endorse/promote): the loading screens used Freedoom's own FreeDM logo and title-screen art - replaced by our own
  title (tools/title.py; Russo One at first, replaced 09:05 by the in-game HUD font) over a level render (ref/art/render_*.png, made with
  preview/view.html, which now takes w/h/nearest/clear and marine skins). Footer on both screens: "UNOFFICIAL. USES
  FREEDOOM CONTENT UNDER ITS BSD LICENCE; NOT AFFILIATED WITH OR ENDORSED BY THE FREEDOOM PROJECT." README_FREEDM.md
  says the same. Licence + credits + music credits now copied into out/game (shipped in the Workshop upload).
  Still Zach's call: the name "FreeDM Arena" uses Freedoom's product name (FreeDM). Some FreeDM levels show
  Freedoom's FreeDM logo as a wall texture (their unmodified level art) - keep those out of promo screenshots.
  The chat labels "DOOM: ..." / "!doom" use id's trademark descriptively (README already disclaims id/Bethesda).
- Workshop images: tools/workshop_art.py -> dist/workshop_square.jpg (1080x1080 thumbnail) and dist/workshop_wide.jpg
  (1920x1080 gallery, with the unofficial line), both under 1 MB, sent to Zach.

## Update 17 Oct 09:05 - renamed Hellmatch CS2, lobby bhop removed, title in the in-game font
Written and verified (sha1; PNGs by pixels, SVG by shapes): content maps/mg_hellmatch.vmap (NEW map file),
maps/scripts/freedm.js, panorama/images/map_icons/screenshots/1080p/mg_hellmatch(.png,_1,_2), overheadmaps/
mg_hellmatch_radar.psd, map_icons/map_icon_mg_hellmatch.svg, styles/custom_game/freedm.css (preload names),
README_HELLMATCH.md, TESTING_HELLMATCH.md, MUSIC_CREDITS.txt; GAME folder resource/overviews/mg_hellmatch.txt,
README_HELLMATCH.md, MUSIC_CREDITS.txt.
- Name: Zach chose "Hellmatch CS2" (Workshop title). Map renamed mg_hellmatch so players/servers never see FreeDM.
  Chat: "HELLMATCH: <mode> - <maps>", "Round over - ..."; lobby lines "ROUND 4:32 LEFT", "ROUND STARTS IN n";
  console prefix [hellmatch]; help command !help (also !controls, !hm; old !doom / !fdm still work).
  Loading screens/overview: "32 DEATHMATCH LEVELS", "RETRO FM SOUNDTRACK", "!HELP", footer "USES CONTENT FROM THE
  FREEDOOM PROJECT (BSD LICENCE). NOT AFFILIATED WITH OR ENDORSED BY THE FREEDOOM PROJECT." Map icon: H in a crosshair.
- Title art: Zach asked for the in-game font - "HELLMATCH" is drawn in STCFN (the HUD message font) with a fire
  gradient, dark outline, shadow and orange glow (tools/title.py logo); Workshop taglines use the same font
  (title.hud_text). Russo One removed from the repo.
- Lobby bhop minigame removed (Zach: late joiners are handled by the script now). tools/strip_bhop.py (one-off) took
  ref/mg_freedm_hammer_saved_5.vmap -> ref/mg_hellmatch_base.vmap: removed 48 bhop entities (teleports, triggers,
  relays, sensors, hurt triggers), 57 meshes (platforms, clips, course walls, ladder, trigger leftovers, finish
  platform), the pinv/tree props out there, a small 32-unit jump-test block by the west wall, and the
  sv_bhop_time_window command from logic_auto. The stretched lobby room (to x=2200) is back to 1536x1536 with Zach's
  floor texture (lobby_ceil). Kept: his lobby torches (10 smrt props), logic_auto (mp_freezetime 0, mp_roundtime 600),
  light_environment, nav data, booth and cache rooms.
- Zach must delete the old files (Explorer search "mg_freedm" inside both mg_freedm addon folders, files only):
  content maps/mg_freedm.vmap (old map; keep a backup if wanted), the mg_freedm*.png / _radar.psd / map_icon svg,
  README_FREEDM.md, TESTING_FREEDM.md; game maps/mg_freedm.vpk (+ _cameras.txt, _retakes.txt), resource/overviews/
  mg_freedm.txt, the compiled mg_freedm* panorama images, README_FREEDM.md. Must happen before the Workshop upload,
  or the old map ships too. Then open maps/mg_hellmatch.vmap in Hammer and do a full build.
- Workshop: full description with the licence in docs/WORKSHOP_DESCRIPTION.txt (4.8k chars); images dist/workshop_*.jpg.
- GitHub repo renamed to hellmatch-cs2 by Zach (the session proxy refuses repository-settings writes, HTTP 403).
  Pushing to the new name needs the repo attached to the session (add_repo skink52/hellmatch-cs2, access push).
  Working copy with build caches: /home/claude/freedm-cs2 (remote now hellmatch-cs2).

## Update 17 Oct 09:45 - visibility compile took 30+ minutes
Zach's full build sat in the vis step: "Generated clusters for 1814535 regions in 1013 s, 18442235 clusters".
Cause: a Low visibility hint over every level box (36 hints, ~5.7e11 cubic units = ~2.2 million 64-unit cells).
Nothing inside the levels blocks sight (level props are not occluders), so the fine vis bought nothing. Now only
the whole-map Lowest hint + Low over the 3 lobby rooms (4 hints). maps/mg_hellmatch.vmap re-delivered (sha1 checked).
Same lesson as Space Racer: keep Low hints off big empty volumes.

## Update 17 Oct 10:15 - kill messages cut off, see-through walls on MAP28
Written to the addon and verified (sha1, 10 sampled): maps/scripts/freedm.js, panorama freedm.xml + freedm.css,
253 level .smd files (models/fdm/mXX), TESTING_HELLMATCH.md. The map file is unchanged (not re-sent). Zach must
rebuild in Hammer (the level models recompile) and fully reload.
- Kill messages (top-left message line) were cut at 40 characters ("...SKINK52'S CHAIN"). The message line is now two
  rows of 56 character slots (fdm_msg, fdm_msgb; tools/hud.py MsgLine2 sits 10 Doom px lower). The script splits at a
  space so each row fits the 320-px Doom screen (30_hud.js hudWrap), using the real STCFN glyph widths that
  tools/hud.py writes to build/hud_glyph_w.json and tools/build.mjs bakes in as HUD_GLYPH_W.
- Names on the game HUD are cut to 12 characters (core hudName, HUD_NAME_MAX): kill messages, "YOU TOOK x'S PLACE",
  LEADER, SPECTATING, "<name> WINS" in the centre and lobby lines. Characters the HUD font lacks are dropped (empty
  name -> PLAYER). Chat lines, console and CS2's own killfeed/scoreboard keep the full name. Worst case (two 12-char
  names of wide letters, longest obituary) fits in the two rows with nothing lost (mock check).
- See-through walls, MAP28: the 00:30 fix only covered one-sided (outer) walls. MAP28's walls are mostly two-sided:
  raised blocks, pillars and closed doors are sectors whose LOWER/UPPER faces form the wall, and those had no copy
  (m28: 0 of 101 lower, 0 of 10 upper). tools/convert.py (Level.backing) now also backs:
  - lower faces taller than a step (X_fmax - Y_fmin > STEP 24): copy inside the solid column under the higher floor,
    in the same mover bucket (lifts carry it);
  - upper faces of openings too low to walk under (X_cmin - Y_fmax < PASS 64: closed doors, low lintels): copy inside
    the solid column above the lower ceiling; none under sky ceilings (nothing would hide it there);
  - at slanted corners (octagonal pillars, angled walls) a copy is shortened at both ends (inset, UVs adjusted) before
    it is moved closer, so far fewer get dropped. Walls with no texture on that face get no copy (nothing to draw).
  Coverage, all 32 levels: one-sided 9,422/9,629, lower 2,702/2,917, upper 353/389; 12,477 copies (was 9,539).
  m28: one-sided 113/116, lower 97/101, upper 8/10. Left uncovered: faces with no room behind them (thin sectors) or
  whose copy would cross another line. props.json changed only in tri counts; levels.json and the vmap unchanged.
  NOT YET TESTED IN CS2.

## Update 17 Oct 10:50 - spectator lines, !help while spectating, one life per round
Zach: /help and /doom did nothing while spectating; wanted "type !back to play" on the spectator line and !help to
replace the "SPECTATING <name>" line. Written and verified (sha1): maps/scripts/freedm.js, panorama freedm.xml +
freedm.css, TESTING_HELLMATCH.md, README_HELLMATCH.md (content and game folders). Map and models unchanged.
- Cause: the help text only went on the bottom line when nothing else was there, so "SPECTATING <name>" always won;
  the controls went on pe.player's message line, and spectators have no player of their own on screen.
- New HUD row fdm_spec2_ (40 slots, .SpecLine.SpecLine2 at y 149, just above the bottom line fdm_spec at y 158).
  Spectators: top "SPECTATING <name>", bottom "TYPE !BACK TO PLAY" when !back would put them in right now
  (RoundManager.canJoin), else "YOU PLAY NEXT ROUND"; "AFK - TYPE !BACK TO PLAY" and "JOIN T OR CT TO PLAY" as before.
  !help (8 s, everyone): controls on the message line via info.msg (replaces the old messageTime trick), bottom line
  "CHAT: !SPEC  !AFK  !BACK  !HUD" over whatever was there; spectators also get "MOUSE1/2 SWITCH PLAYER  E NEXT ARENA"
  (the arena part only with 2+ arenas) on the top row. .MsgLine2 is now .MsgLine.MsgLine2 (wins on specificity).
- Bug fixed: !back from someone knocked out of a one-life round (or whose arena was over) set status 'none' while they
  were still in the arena, and lateJoin returned early: stuck on the lobby text until the round ended. !back now only
  acts when canJoin is true, and calls faceView after joining.
- One life per round (core): leaving a one-life arena for any reason (!spec, AFK, team change, knocked out then
  leaving) sets pe.outRound; botToReplace skips one-life arenas for them, so !spec then !back can no longer swap a
  dying marine for a bot's. Newcomers still take a bot's place. README says so.
- infoFor now takes a spectator's arena from pe.spec (the arena they watch), so after E / jump the top-right lines and
  the name match the arena on screen (it used their own arena before and showed just "SPECTATING").
- Mock: test/mock_cs2.mjs reads HUD text back (hudLine) and has a `spec` option (human0 !spec, /help, !back, !spec,
  !doom, !back; other spectators type !back and it must join exactly when canJoin says so). Runs: spec, spec+churn,
  spec+churn+elimonly - 0 problems, no one stuck. NOT YET TESTED IN CS2 (check the two rows don't overlap).

## Update 17 Oct 17:35 - "will it be too laggy on a server?": HUD cost halved, timing line in the console
Written and verified (sha1): maps/scripts/freedm.js only. No visible change.
- Profile (node --cpu-prof, mock 32 humans + 32 bots): hudPlayer 54% of script time (hudText 34%, hudSwap 20%,
  hudNumber 11%) - every tic re-checked ~270 text panels per player that had not changed. Doom sim 22%, prop
  updates 15%.
- Fix (30_hud.js): hudLines remembers what each text line / number last showed in full; unchanged ones are skipped
  (hudSame/hudDrawn). Only recorded when every change went out (HUD budget not exhausted, HUD entity not re-found
  halfway: hudGen). Cleared with hudCache (hudReset, hud() re-find). Mock option `hudcheck` still compares every
  skipped line panel by panel: 0 differences (default, churn, spec, spec+churn+elimonly, afk, round restarts).
  Mock option `nolinecache` = old behaviour, `perf` = per-tick stats.
- Script time per server tick (mock, Node, before -> after): 16 players avg 1.38 -> 0.79 ms (p99 4.3 -> 2.5);
  32 players 2.95 -> 1.60 (p99 8.7 -> 4.9); 64 players 6.2 -> 2.9 (p99 17.6 -> 8.2, ticks over 16 ms in 7 min
  551 -> 9, all at round start: arena build spikes 20-30 ms). Not measured: CS2's own cost of ~145 prop moves per
  tick at 64 players (~90 sounds/s, ~90 HUD class changes per tick) and networking them to every client.
- Console (60_main.js think): once a minute during a round "[hellmatch] script time: avg X ms, max Y ms per server
  tick (N players, A arenas)" (Date.now, 1 ms steps; skipped if Date is missing).
- Lag on a server, for the record: the camera is CONTROLLED_POSITION while alive, so mouse look stays client-side
  (instant); movement and shots are simulated on the server, so they arrive one round trip late (ping + up to one
  35 Hz Doom tic + interpolation). No lag compensation (shots use the server's current positions): lead targets by
  about your ping. A map script can't do client-side prediction.

## Update 17 Oct 18:20 - joiners left in the lobby with a knife, half-drawn HUD text
Zach's screenshot: skink52 joining T mid-round stood in the lobby with a CS2 knife, HUD showed "857" and "ING..."
(i.e. "ROUND 8:57 LEFT" / "JOINING..." with the unchanged characters missing); ! commands did nothing; he got in
only after waiting. Written and verified (sha1): maps/scripts/freedm.js, TESTING_HELLMATCH.md (item 15).
- Cause 1 (stuck): point_script.d.ts says OnPlayerReset also fires on a team change, and CS2 can send it BEFORE
  OnPlayerTeamChanged. Reset placed the joiner with the stale team (0) from the last scan; TeamChanged then saw
  status != none and did leaveArena + unpark (pawn back to WALK, knife) - and nothing re-joined them until another
  Reset. Fix (60_main.js): both events rescan first (current team); TeamChanged only removes someone whose place no
  longer fits (left T/CT, or a team arena on the other side), re-tries spectators who only watched for lack of a
  place, then placeLateJoiner; Reset uses placeLateJoiner; frame() runs placeLateJoiner every second for anyone
  status 'none' on T/CT, not AFK, with a live pawn (safety net); !back from the lobby (status none) now joins too.
- Cause 2 (missing letters): HUD class changes sent before the joiner's client was ready were lost, but the
  per-panel cache thought they were drawn, so only characters that later changed appeared. Fix: hudReset (engine
  ResetForPlayer + cache clear, full redraw) on OnPlayerActivate, OnPlayerTeamChanged and a lobby spawn (Reset with
  status none). Respawns in an arena don't reset (the HUD survives those, or the root class would have vanished).
- Mock: FDM_SCRIPT=<file> runs another build; `resetfirst` sends Reset before TeamChanged with the team already set
  (joins and swaps); `hudwipe` drops HUD messages to a joining client until it picks a team; churn runs now report
  people left standing in the lobby and screens not matching the script's HUD cache. Old build: stranded up to
  193 s, 1457 of 5300 screen checks wrong; new build: 0 and 0 (also with elimonly, spec, hudcheck).
- Music console line "[sndoperators] operator error: event fdm_music.dm21: CSosOperatorConvar" (sometimes, spams):
  our events match Valve's documented csgo_music example exactly (type, volume, volume_convar "snd_musicvolume",
  vsnd_files). 20:50 Zach's console dump: each line pair is followed by "Unable to acquire convar value:
  snd_musicvolume_rush / _casual / _armsrace / _deathmatch" in a loop while a track plays. CS2's built-in csgo_music
  stack looks up old per-mode CS:GO music volume convars that CS2 doesn't have. Harmless (music plays, follows
  snd_musicvolume); left as is. The only way to silence it is a non-music sound type, which would ignore the music
  volume slider (a shared point_soundevent can't be turned down per player).
  20:58 Zach: admins use the in-game console, so fix it. buyi.dev/2024/cs2-snd notes csgo_music follows snd_musicvolume
  by default and that a hand-written volume_convar "didn't work"; the failing names are volume_convar + _<mode>.
  Removed volume_convar from the music events (tools/extras.py); soundevents_addon.vsndevts re-sent. NOT YET TESTED:
  check the spam is gone and the music volume slider still turns the music down.

## Update 18 Oct 03:20 - monsters, Boss Battle, monsters in deathmatch, theme music (the 21:51 scheduled run)
Zach (21:21): make the trailer track the first song in game; generate similar fast-paced tracks; add a Boss Battle mode
(hordes of Freedoom monsters, then a boss); monster spawns as a chance roll in non-PvM rounds like the weapon starts.
Repo commits 11a49b7 + 8ef8ea2 (pushed to main). Script v0.2.0. NOT YET RUN IN CS2.
Delivered to the PC and verified (sha1 / pixels / decoded audio): maps/mg_hellmatch.vmap (rebuilt from his 09:45 save,
kept as ref/pc/mg_hellmatch_pc_2110.vmap, gitignored), maps/scripts/freedm.js, soundevents_addon.vsndevts, 5 music
MP3s, 43 HUD string images + freedm.css, 3 loading screens, README/TESTING/MUSIC_CREDITS (content + game), and the
bulk set of 1,245 new files (624 model files, 564 sprite materials, 57 monster wavs; ~250 MB) in 25 batches by a
helper agent (the session limit cut it at batch 8 at ~23:10; resumed 02:52 after the reset: 1,245/1,245 written,
0 rejected, 12 spot checks + 4 of mine matched; the outputs folder adds a metadata block to WAVs too, so compare
wavs by samples, not sha1). Zach must open the map in Hammer and do a full build (312 new models compile; the vmap has 502 cache
props, 94 sound events, 14 music events), then `disconnect` + run the map.

- Monsters (src/core/00_a_monsters.js + 35_enemy.js): the 17 Freedoom creatures (zombie, shotgun zombie, minigun
  zombie, serpentipede, flesh worm, stealth worm, deadflare, trilobite, pain bringer, pain lord, dark soldier, combat
  slug, technospider, summoner, flame bringer, assault tripod, large technospider) with Doom's own state tables and
  behaviour: tools/monsters_gen.py reads info.c/info.h/sounds.h of the Doom source (github id-Software/DOOM) and
  writes the tables as data (frames, tics, health, speed, radius, flags as strings resolved in 00_defs.js); the
  behaviour (A_Look/A_Chase/attacks, 8-direction movement, noise alerts, infighting, arch-vile resurrection,
  pain elemental skulls, revenant tracers, mancubus spreads, lost-soul charges) is our own port in 35_enemy.js.
  Monsters open normal/fast doors (specials 1, 32-34, 117) and use teleporters and the few walkover lines Doom lets
  them (39, 97, 4, 10, 88). Zombies drop their weapon. Big ones (tripod, large technospider) ignore splash damage.
  Only the last 24 monster corpses stay per arena (each is a prop). Lost souls capped at 20 per arena.
- Models: the sprite generator carves monsters from their 8 rotations like the players; sprites wider/taller than
  60 px are carved at 2 units per voxel, over 130 at 4 (a 1-unit large technospider was 50 MB per frame; now every
  model is 1-6 MB like the marine). Death/gib frames are stars. 502 models in all (was 190), 1,004 model files +
  564 star-material files; models/fdm/spr is 346 MB. Frames past Z (arch-vile heal [ \ ]) are keyed 0 1 2 in model
  names (Freedoom names the \ frame ^). The map rebuild (tools/vmap_env.py, group fdm_env) now adds cache props for
  models and point_soundevents for sounds that the user's map doesn't have yet (312 props, 57 sounds this time), on
  a 32x40 grid in the cache room.
- Boss Battle (MODES.boss, co-op): src/core/36_monsters.js MonsterDirector. Waves 1-4 are planned from a budget
  (4 + 2.5 x players) x (0.7 + 0.4 x wave) over a roster with costs/tiers (zombies and imps first, trilobites /
  pain bringers / dark soldiers from wave 3, combat slugs / technospiders / pain lords from wave 4, flame bringers
  on the boss wave's escort); the 5th wave is the boss: assault tripod (health 4000 x 0.4+0.12n), large technospider
  in arenas of 6+ when it fits, otherwise a pack of pain lords (1 + ceil(n/4), 1000 x (1 + m/2) hp), plus an escort.
  Monsters arrive through teleport fog at spots far from and out of sight of the players (DM starts + item spots,
  only in sectors reachable from the starts via the bots' nav graph), trickled in under an alive cap
  min(36, 8 + 2n, 6 + area/120000). Monsters that haven't moved for 25 s while nobody is within 400 units are
  teleported back near the players (pits, closed corners). 3 lives each (p.lives), out of lives = spectating.
  Win = boss dead (VICTORY); lose = everyone out of lives (OVERRUN) or 8 min (TIME UP). Boss arenas always start
  everyone with a weapon start. Players can't hurt each other (sameTeamNoFF with G.coop), no frags between players;
  the frag box counts monster kills (boss = 5). Result text "VICTORY - name N KILLS" / "OVERRUN AT WAVE n". CS2
  round credit: the side (T/CT) with more monster kills in a won arena. Player deaths by monsters are CS2 world
  kills (no -1); monster kills are not CS2 kills. HUD: top-right "WAVE 2 OF 5 - 6:40" / "14 MONSTERS  LIVES 3",
  centre "WAVE n OF 5", "WAVE CLEARED", "BOSS INCOMING", "BOSS DOWN!"; chat line when the boss appears.
  Mode weights now ffa 30 / tdm 30 / boss 15 / elim 15 / lms 10. CONFIG.MONSTERS {waves, lives, maxAlive, roamMax},
  BOSS_SECONDS 480. Bots: in co-op they hunt monsters; in deathmatch they shoot monsters within 700 units or that
  target them.
- Monsters in deathmatch: CONFIG.MONSTER_CHANCE 0.15 per arena (rolled in planArenas like the loadout). 2-8 monsters
  by level area (roam roster: zombies, imps, demons, lost souls, cacos, a few knights/revenants/mancubi/arachnotrons/
  barons), first ones placed before the countdown ends, replacements 15-25 s after a kill. Doom's rules: killing a
  monster is no frag, dying to one costs none (CS2: world kill). Chat line shows "(n, MONSTERS)".
- Music: music/tracks.json + files are extra tracks (tools/music.py extra_tracks: two-pass loudnorm to -16 LUFS,
  MP3 128k 44.1k stereo, cached in build/music by size+mtime). theme.mp3 = the trailer track (49 s), pool "opener":
  55_music.js plays it first in every round (CONFIG.MUSIC_OPENER "every" | "first" | "off"), then the round's pool.
  Generated tracks gen01-gen04 (tools/synth.py + tools/compose.py, written by a helper agent; see music/analysis.md)
  go in the long pool. MUSIC_CREDITS lists them.
- Tests: mock_cs2 options bossonly / noboss / monsters (MONSTER_CHANCE 1); sim.cjs MONSTERS=1 and mode arg "boss".
  Runs: bossonly 10h+6b 300 s (0 errors), noboss+monsters+churn (0 errors, kills on), bossonly+churn+hudcheck with
  4h+28b (4 boss arenas, round ended, 0 hud differences, think avg 2.2 ms, max 52 ms). sim 16 bots 8 mixed rounds OK;
  boss rounds with 8 bots end in 2.5-5 min (victory or time up at wave 3-5): the balance is tuned on bots only.
  tsc: 0 errors (the PC script had 3).
- Docs: README_HELLMATCH.md (modes table with Boss Battle, monsters section, music, settings, credits), TESTING items
  16-19 (theme music, Boss Battle checklist incl. how to force it via MODE_WEIGHTS, monsters in deathmatch, frame
  rate), WORKSHOP_DESCRIPTION.txt and WORKSHOP_CHANGELOG.md (18 Oct entry), loading screens list Boss Battle.
- Header line to expect: `[hellmatch] v0.2.0 ready: 32 levels, 502 sprite models, HUD on, prop template on`.
- Music helper's analysis (music/analysis.md): trailer is 150 bpm D minor, -12.3 LUFS; gen01 Ferrous Pulse
  (industrial, D minor 150), gen02 Chainsaw Vespers (thrash, A minor 164), gen03 Low Orbit of Hell (doom-metal
  middle, G minor 140), gen04 Valkyrie Fragstorm (heroic, E minor 156), all ~195-207 s, -16.4 LUFS. Guitars are
  synthesised (industrial/synth-metal feel, not a mic'd amp); Zach to judge by ear and drop any (remove from
  music/tracks.json). Previews music/preview_gen0N.mp3 (20 s from the second chorus).
- Open: CS2 cost of ~40 monsters + shots per arena (props, sounds) unknown; Boss Battle balance tuned on bots only;
  monster kills can't be CS2 kills; `MUSIC_OPENER` "every" by default (Zach's call; "first" = once per map load).


## Update 18 Oct 08:25 - monster audit (Zach 07:21: "check for the issues we've met before and anomalous AI; PvE rounds on large maps")
Commit 31867f4 (pushed). Delivered + sha1-verified: maps/scripts/freedm.js, README/TESTING (content), README (game). Map and
models unchanged, so no Hammer rebuild for this one (the 23:10 delivery still needs its full build). NOT YET RUN IN CS2.
Method: test/audit_monsters.cjs runs Boss Battle or DM+monsters on every level with bots and counts, once a second:
monsters outside the outline, inside a wall (blockline at own position), on a tall ledge, floating, stuck (no movement
for 10 s with a far target), idle (asleep with players alive), bots stuck 5 s+, spawn failures, relocations, slow tics,
HUD lines over their slots. Plus the mock (bossonly/noboss+monsters with churn, spec, hudcheck, resetfirst+hudwipe, afk),
tsc, and an independent code review (10 findings, all applied).
Found and fixed:
- Spawn spots inside a tall step: fitSpot/checkPositionProbe passed a spot whose radius overlapped a 128-high ledge;
  the monster then stood at ledge height inside the low room and could never move (MAP07 etc). Now a step > MAXSTEP
  within the radius rejects the spot (players' spawn spots use the same check; was rare for them).
- Co-op telefrag: sameTeamNoFF blocked 10000-damage telefrags in Boss Battle, so a bot taking a teleporter onto a
  teammate at the destination overlapped it; overlapping things can never separate (each blocks the other's moves) -
  3 bots stuck 45 s at one spot (MAP11). Telefrags now bypass team rules. Monsters don't teleport onto things.
- Monsters in walls after a teleporter: a 30-radius demon landing on MAP01's destination (16 units from a wall)
  overlapped it (Doom does this too). Monsters now step to the nearest clear spot after teleporting.
- Lost souls spawned through walls into the void by the summoner (Doom quirk): skull spawn needs a clear line and an
  inside point; any monster outside the outline is removed (rescueOutside, director.onLost keeps counters right).
- Wave stalls: monsters that lost sight of everyone went back to sleep; monsters jittered for minutes against geometry
  they can't path round; ledge snipers nobody can reach/aim at. Director.unstick (every 5 s, boss mode): asleep 5 s ->
  wake with the nearest player as target; no headway towards the nearest player (64 units) for 20 s and not fighting
  on the same floor -> back through a teleporter near the players, on their floor level (flyers exempt from the floor
  rule). Stuck monster-seconds over 32 maps 1913 -> ~100; rounds reach the boss everywhere.
- ML_BLOCKMONSTERS lines now block monsters (and the spot probe knows it). Monsters open all door kinds (keys don't
  exist; a monster behind a locked door would stall a wave).
- Boss Battle entry is once per round (leaving via !spec/AFK/team change and rejoining gave fresh lives and 0 frags).
- Boss Battle picks levels from the bigger half by area (16 levels: MAP24 32M .. MAP22 4.8M), the biggest quarter
  twice as often; CONFIG.BOSS_MAP_BLACKLIST. Verified over 400 rounds: 16 distinct, all >= 4.8M.
- Boss wave softened (health scale 0.35+0.1n, escort 2+n/3), bossDown fires on the kill (escort queue dropped), arenas'
  waves offset by a second so four arenas don't burst on one tick, aliveNow cached (HUD read it per player per tick),
  ADD_SCORE never docks a monster victim, csKill log with killer null fixed, raised boss corpses lose .boss, idle
  check keys on A_Look (STND/STND2 alternate).
Bot-only balance after fixes, 8 bots on the 16 large levels: ~13 victory / 1-2 overrun / 1-2 time-up per pass; 4 bots
lose more often (5 of 6 overrun) - small groups may need lives 4 or a smaller budget; judge after a human game.
Known/accepted: Doom's chase is greedy, so some jitter remains (relocation covers it); mock "blank spectator lines" at
t=25/45 are the second the !spec was typed (pre-existing, also in the previous script); monster kills still not CS2 kills.

## Update 19 Oct 17:xx - planned list done: theme rule, monster podium, animated/scrolling surfaces, joins re-checked
- Theme (55_music.js): MUSIC_OPENER "first+boss" (default): map's first round + first Boss Battle round (once if same).
- Podium (60_main.js monsterPodium, in endDoomRound): per coop arena, rank by p.frags (monster frags); top 3 with > 0;
  everyone else in the arena csKill'd credited by splitShares(losers, [50,30,20]) (Space Racer's rule); chat line.
- Animated surfaces (water etc.) never animated: convert.py's material groups remapped FROM the SMD material name;
  ModelDoc groups remap from the default group's material path (as the sprite colour skins do, which work). Fixed.
- Scrolling walls (special 48): csgo_unlitgeneric's g_vTexCoordScrollSpeed did nothing in CS2. Now each scrolling
  texture is its own anim prop (fdm_<lvl>_as_<tex>) with frames = the texture shifted scroll_step(w) = max(2, w/32)
  pixels (<= 32 frames), stepped by the script every `step` tics (level data an = [name, frames, tics]). Only on static
  buckets (scroll lines on lift/door sectors keep the old scroll material). MAP13 sp_face1, MAP20 skspine2, MAP32
  compblue + crackle2.
- Map: vmap_env on the PC's vmap (unchanged since 18 Oct 19:05 write): +4 prop_dynamic, nothing removed.
- Files: 320 new (190 vmat, 124 png, 6 model files) + 42 changed (35 anim vmdl, static bucket smd/vmdl on m13/m20/m32).
- Joins re-checked (mock churn/hudcheck/resetfirst/hudwipe/spec): 0 left in lobby, screens match, ballot shown.
- 17:30 Boss Battle harder (Zach): CONFIG.MONSTERS.difficulty 1.35 scales planWave budget, spawnGap (/d), boss health (m*d),
  escort count (*d). Mock (4h+12b, 8 seeds, bots only): d=1 6 win/6 overrun/4 time-up -> d=1.35 4/9/3. Think time
  unchanged (alive cap 36 kept). Mock option diff=X.

## Update 19 Oct 12:50 - !text (Doom-font text size), top-bar avatars (Zach 12:40)
Delivered 19 Oct 16:15 + verified: maps/scripts/freedm.js, panorama/styles/custom_game/freedm.css (+28 rules,
nothing else changed), README/TESTING (19d). The CSS needs a compile (map build). NOT YET RUN IN CS2.
- !text [normal|large|huge|small|tiny] per player (pe.textSize): class on fdm_screen; each line scales from its anchored
  edge, the second line of each pair is shifted by 9*(s-1) so pairs don't overlap; the message wrap width is 316/s.
- Avatars at the top of the CS2 HUD: a map can't style the native HUD; CONFIG.CLIENT_CVARS (default
  "cl_hud_playercount_showcount 1") is sent with ClientCommand once per arriving human. Unknown whether CS2 lets a
  server set it (cl_draw_only_deathnotices was refused). If it works it persists in the player's own config.

## Update 18 Oct 19:05 - Boss Battle: twin tripods, summoner swarm, boss music, monster score; flame bringer frames (Zach 18:33)
Delivered + sha1-verified (content): maps/scripts/freedm.js, maps/mg_hellmatch.vmap (+7 entities), soundevents_addon.vsndevts
(+4 music events), sounds/fdm/music/e1m8..e4m8.mp3, models + materials for vile_0..2 (15 files), MUSIC_CREDITS.txt,
README/TESTING (19c); (game) MUSIC_CREDITS.txt, README_HELLMATCH.md. MAP REBUILD NEEDED (new entities + sounds + models).
NOT YET RUN IN CS2. Note: files written through /mnt/user-data/outputs get a C2PA provenance chunk (mp3: ID3 GEOB,
png: caBX ancillary chunk, ~5.8 KB each); audio/image data unchanged, decoders ignore it (earlier music had it too).
- Bosses (36_monsters.js planBoss): cyber 4, twin 3 (6+ players, cyber fits; 2 x 1500*m health, smaller escort),
  spider 3 (6+, fits), swarm 3 (2 + ceil(n/5) summoners at 400*(1+m), escort 1 + n/4; flares capped at 20 by Doom's
  rule), lords 2 (4 if no cyber). The kind the last Boss Battle arena got has a quarter of its weight next time
  (lastBossKind). Bot audit, 8 bots, 16 large levels, forced kind: swarm 14/15 won; twin at 2600 health 3/10, at 2000
  5/14, at 1500 + smaller escort 9/15 (kept: the hard one); random mix 11/16 vs 13/16 this morning (noise-level).
  test/audit_monsters.cjs: AUDIT_BOSS=<kind>, boss name column, results by boss.
- Music: tools/music.py pool 'boss' = Freedoom Phase 1 boss levels E1M8 "On the Next Day", E2M8 "Treble Dissension",
  E3M8 "The Zenith", E4M8 "Vs. The Assault Quindecapod" (712 s together), same OPL3 render + loudnorm; titles() now
  reads Phase 1/2 too. Boss Battle rounds play the theme then the boss pool (startDoomRound), only when the map has
  boss tracks. music.json on the PC side = the deployed list + the 4 boss entries appended (existing entities keep
  their positions); fdm_mus_e1m8..e4m8 added by vmap_env (verified: only those 4 + fdm_cache_vile_0..2 added, nothing
  removed). The dm renders here differ in bytes from the PC's (encoder version), so only the new files were sent.
- Score: monsterKill event -> monsterScore: AddScore(MONSTER_SCORE 2 / MONSTER_SCORE_BOSS 10) in Boss Battle
  (MONSTER_SCORE_DEATHMATCH false), not in warmup; MONSTER_KILL_COMMAND (off) runs a server command per kill with
  {slot} {boss} {monster} for a plugin that wants the Kills column / ranks (no .NET here to build one).
- Flame bringer: sprite_models.json now 505 (VILE_0..2, its attack frames past Z) - those frames drew nothing before.
- Steam: docs/WORKSHOP_CHANGELOG.md has "Update - 18 Oct (evening)" covering everything since the 10:31 upload;
  docs/WORKSHOP_DESCRIPTION.txt updated (vote keys/commands, bosses, boss music credits, score, server load).
Checks: tsc; mock bossonly 64 players 15 min (boss music only in boss rounds, scores from monster kills, no errors);
churn 64 players (no monster score in deathmatch, ballot on every screen, screens match); vote/novote traces as before.

## Update 18 Oct 14:50 - next-mode vote at the end of every round (Zach 13:44), then more optimising
Delivered + sha1-verified: maps/scripts/freedm.js (b760c68e), README_HELLMATCH.md, TESTING_HELLMATCH.md (item 19b).
Script only: no Hammer/map rebuild (the ballot uses the HUD's existing text lines). NOT YET RUN IN CS2.
Vote (src/cs2/58_vote.js, CONFIG VOTE / VOTE_SECONDS 10 / VOTE_TOP_BONUS 2 / VOTE_KEYS):
- Opens when the Doom round ends (endDoomRound), for VOTE_SECONDS. Everyone sees it: players still parked on their
  arena get the lobby HUD (status bar off, text lines on) while a ballot exists, and lobby players get it too.
  Centre "VOTE NEXT MODE: n", bottom two lines "M1 FFA 3  M2 TDM 0  E ELIM 1" / "R LMS 0  F BOSS 2" (`>` = your pick),
  top right "YOUR VOTE COUNTS X3" / "YOUR VOTE: FFA (X3)". After it closes: centre "NEXT: <mode>", the tally below,
  chat "NEXT MODE: ... (votes ...)".
- Keys (non-movement, so walking about in the lobby never votes): M1 FFA, M2 TDM, E ELIM, R LMS, F BOSS. Chat !ffa
  !tdm !elim !lms !boss or !vote <mode>. Pressing another key moves your vote. Key presses in the first second are
  ignored (fire held through the round's end). Bots don't vote. Read with WasInputJustPressed every tick (pawn
  lookups 4x a second), only while the ballot is open.
- Weight: 1 + VOTE_TOP_BONUS x clamp(frags / top frags in your arena) -> top fragger 3, half the top score 2, none 1
  (people not in an arena 1). Snapshot at round end. Leavers' votes are removed.
- Ballot: modes with MODE_WEIGHTS > 0 that can be played with the people on T/CT now (smallest arena >= minPlayers,
  team modes only with both sides) and not played the last two rounds (no third in a row). Fewer than 2 options or no
  humans = no vote. No votes = random as before (pickMode, which already bans a third in a row).
- RoundManager.startRound(list): the vote's ranking, best first; the first that can be played when the round starts
  (enough players, both sides for team modes, not a third in a row) wins, else the old random pick. Tie = lot.
- The next Doom round waits for the ballot (voteBusy) if CS2's restart delay + freeze time is shorter than it.
Fixes found on the way:
- Lobby HUD after a round restart: with many players the 600 HUD changes per tick ran out and the rest waited for the
  next 0.25 s pass, always the same people last; with a busy ballot (totals changing every tick) the last 6-7 people
  never got drawn. Now a pass that runs out carries on next tick from where it stopped.
- Shots that escape a level (seen: a pain lord's ball on MAP10, Boss Battle) flew on forever and past the CS2 world
  edge (+-16384); a missile outside the level's outline is now removed, and the renderer never moves a prop past
  the edge (hides it instead).
Further optimising:
- Boss wave start was the worst tick in the game (50 ms at 64 players: planBoss checking where a cyberdemon /
  technospider fits ran ~800 probes x 24 spots, twice for the cyberdemon). Now: the same question isn't asked twice;
  a spot whose sector is lower than the monster is skipped outright (every searched point is in that sector, so it
  can't fit); the ring of search points per spot is worked out once per arena; fits is tested before the line
  trace. 50 -> 21 ms. Identical results (trace hashes).
- HUD text that hasn't changed is recognised before the upper-case conversion (half of hudText's time).
- Mock: trace hashing costs nothing when off; model-file checks cached. `novote` option = round flow without the vote.
Checks: with `novote` the trace hashes equal the 12:05 script in all 10 scenarios once the lobby-redraw fix is taken
out (it changes only when lobby lines are sent); sim.cjs / audit_monsters identical to before today (timings aside);
10 long mock runs with the vote: 0 errors, no mode three times running, ballot on every human's screen in every
check, hudcheck 0, screens-vs-script 0, no one left in the lobby. Vote fallbacks checked directly (all on T + voted
tdm -> next choice; ffa twice + voted ffa -> next choice; too few for tdm -> random).
Script time per tick (mock, seed=11, 12:05 script -> now): 16 players 0.37 -> 0.36 ms, 32 0.74 -> 0.74, 64 2.25 -> 2.13
(p99 6.7 -> 6.1, worst 17.6 -> 11.2). Steady state is now the Doom simulation itself (movement, line traces) and
drawing the things; little exact headroom left without changing how things look or play.

## Update 18 Oct 12:05 - script server time cut by about a third, engine calls halved (Zach 10:46: "further optimise the time the script spends thinking")
Delivered + sha1-verified: maps/scripts/freedm.js only (a4661dc4). No gameplay change, nothing else to rebuild. NOT YET RUN IN CS2.
Built from the deployed script's own generated data (levels, sprite models, HUD strings, glyphs, music list), so the
data parts are byte-identical to what was on the PC; only the code changed.
- Proof of no change: test/mock_cs2.mjs has two new options. `seed=N` fixes Math.random and the clock (the playsim's
  P_Random seeds from Date.now) so a run repeats exactly; `trace` hashes every call the script makes into CS2
  (positions/angles to 0.001, models, colours, skins, sounds, HUD classes, log lines) and counts engine calls per tick.
  Old and new script give the same hash in 10 scenarios (deathmatch 64 players, bossonly, elimonly, monsters, churn,
  spec, churn+hudcheck, afk+disc, churn+resetfirst, churn+hudwipe+noboss); test/sim.cjs and audit_monsters.cjs give
  identical results (only the timing columns differ); a fuzz test of 192k path traces / sight checks over all 32
  levels against the old code: 0 differences. hudcheck 0, tsc clean.
- Script time per server tick (mock, Node, seed=11, before -> after): 16 players avg 0.65 -> 0.44 ms (p99 2.2 -> 1.6);
  32 players 1.22 -> 0.87 (p99 3.2 -> 2.3); 64 players 3.73 -> 2.46 (p99 10.8 -> 7.2, worst tick 35 -> 15).
  Engine calls per tick at 64 players 1175 -> 560 (IsValid 513 -> 38, input reads 326 -> 218, GetGameTime 34 -> 3);
  these are native calls the Node numbers don't fully price, so the saving in CS2 should be larger than the timings.
What changed:
- Renderer (20_render.js): no IsValid() per prop per tick (a removed prop is caught by try/catch and checked once, the
  old behaviour after that); sprite -> model path cached per frame; stamp instead of a new Set per update; the sweep
  for vanished things only runs when something vanished.
- Cameras (40_players.js): no IsValid() on the camera per tick (same try/catch pattern).
- Input: weapon-switch edges still read every server tick; held buttons only on ticks where a Doom tic runs (a tic only
  ever saw the last sample, so the in-between reads changed nothing); view angles still every tick (view lock after a
  teleport and AFK turning depend on them). Pawn validity checked once per tick, not three times.
- HUD (30_hud.js, 60_main.js): the HUD entity is checked once per think instead of on every class change; the arena's
  lines (mode/clock, score, centre text) are worked out once per arena per tick instead of per viewer; message wrap,
  weapon and number class names cached; number lines remember the number, not a built string.
- Playsim: line openings return one shared object (every caller reads it at once); path traversal without per-call
  closures or temporary objects, and lines/things whose box can't meet the trace are skipped before the maths (they
  could only give intercepts past the trace's ends, which the walk never reaches; long traces only); collision block
  maths inlined; noise flood (monsters hearing shots) cached per source sector until a door/lift opens or shuts a line
  (movePlane counts shut lines before/after); bots sight-check enemy and item candidates nearest first and stop at the
  first one seen (same pick as before, ties in the old scan order) instead of a sight line to everyone in range.
- Object shapes: map objects, players and sectors declare all their late-added fields up front (undefined), so V8
  keeps one hidden class per kind and property reads stay fast (worth ~10% on its own). Every check on those fields is
  `=== undefined` / `!== undefined`, so nothing reads them differently.
- think() now always reschedules itself (finally), and a throw from the chat queue can't stop the think loop.
Noticed, not changed:
- The script on the PC (and so this one) knows 502 sprite models; a fresh build from today's Freedoom makes 505
  (VILE_0/1/2, the summoner's attack frames past Z), so those three frames draw nothing for a few tics. Fix = rebuild
  models + script together (models first).
- One mock run before the clock was fixed moved a thing to y=16389 (outside CS2's +-16384) in a Boss Battle arena:
  some projectile or knocked-back thing left its level far into the void. Not reproduced with fixed seeds; worth a
  clamp or removal if CS2 logs bad positions.

## Open issues
1. Confirm in CS2 that scoreboard kills keep counting when people join mid-round (fixed in the sim, 15:10 build).
   Frags during CS2 warmup are deliberately not sent (console warning says so).
3. Check the CS2 console at round start for "point_script ... thinking for" lines (spread out at 15:50).
2. Map base: ref/mg_hellmatch_base.vmap (his 16 Oct 08:01 save minus the bhop course). From now on his Hammer saves
   of maps/mg_hellmatch.vmap are the base (stage it, keep a copy in ref/, build with FDM_CURRENT_VMAP).
   Rebuild only from his latest Hammer save.

## Ideas / not done
- Per-player music on/off (csgo_music plays to everyone; players use snd_musicvolume).
- Intermission music between rounds (d_fdmint).
- (Done 19 Oct: theme rule, monster podium, animated/scrolling surfaces, joins re-checked.)
- Zach's C answers (18 Oct 19:25) are recorded in TESTING_HELLMATCH.md section C (→ lines). Dead bots turning green
  is accepted (signals a landed kill). Joining CS2's real spectator team is a bit buggy - accepted.

## Known CS2 limits found
- cl_draw_only_deathnotices can't be set from a script (CS2 refuses); only sv_disable_radar works server-side.
  The CS2 health box and chat box can't be hidden, moved or resized from a map.
- `say` from a script speaks as the listen-server host and hits the chat flood limit if lines go out together.
  Scripts can't send private chat and can't hide a player's own chat line.
- Panorama: moving a panel by changing horizontal-align through a class doesn't re-place it (transform/size changes
  do work); keyframe names must be quoted; the root HUD panel may not have an id; HUD text lines are fixed rows of character
  panels (32 per line; the message line 2 x 56; spectator top row 40). Line prefixes must not end in a digit
  (fdm_spec2 + "0" would clash with fdm_spec + "20"), hence fdm_inf1_, fdm_spec2_.
- Alpha-tested textures must be power-of-two; CS2 draws both faces of model polygons.
- Bots need a func_nav_markup WALKABLESEED volume in the lobby (present).

## Workshop
Uploaded as game type Custom, map mg_hellmatch. Description (updated 16 Oct) includes the full Freedoom BSD licence —
it has to, because the Workshop upload carries the compiled game folder, not the licence text files in the content
folder (the build now also copies the licence and credits into out/game). Source repo link:
https://github.com/skink52/hellmatch-cs2 (was freedm-cs2). Workshop title "Hellmatch CS2" (was "FreeDM Arena CS2"). Description: docs/WORKSHOP_DESCRIPTION.txt.
Preview images: dist/workshop_*.jpg (tools/workshop_art.py).
