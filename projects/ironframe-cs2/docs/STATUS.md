# IRONFRAME status and handover

## To do (skink52, 9 Nov 2026 evening)
- [ ] White dots above heads = the IFF markers, but the team tint isn't showing: make coloured marker models.
- [x] Nav mesh so CS2 bots can join (11 Nov: both maps have booth seeds and a 4-area nav file; unseen in game); the script now fills with real bots when it can (kills credited like Hellmatch).
- [ ] Animation review sheet / video (animated GIF per clip).
- [ ] Vis near the train tunnels: find a better hint layout or build without vis.
- [ ] Hangar grime overlays (oil stains, concrete wall stains).
- [ ] Compile and run sims on the local server (map from the game folder, bots, plugin flows, mailbox rename).
- [ ] Post-processing (bloom, grading, vignette) fitting the sky.
- [ ] After the map build: `python -I tools/patch_cache.py <map> out/patched.vmap out/addon` for the supply crate model (back up first).
- [ ] Frame identities: every frame its own stat profile + one signature passive/ability (awaiting skink52's yes).
- [ ] Visible damage states (scorch/blacken skins, smoke, fire) and death gibs (after the animation agent).
- [x] Tripo humanoid models for Krasnaya / Lisa / Supplice: DROPPED by skink52 (10 Nov, ~19:15): "if the built in weapons are stripped thats good enough". The three keep their AC models, weapons stripped. Prompts stay in docs/TRIPO_PROMPTS.md if wanted later.
- [ ] Further polish passes.

## Resume here
**12 Nov 2026, night (skink52's Sprawl notes, "half rate for above 40 is yes", "update server"). build 31: 19 suites PASS, mock PASS, Sprawl rebuilt and compiled (vpk 13 Nov 00:56, 5194 resources, 0 failed, cache check clean), Dunes script deployed, both copied to the test server's files; test server down (CSS, below). Unseen in game.**
- **Sprawl ramps split** (skink52: "inelegant - and removed playable area ... a single lane on and off ramp, and have normal traffic
  flow between"): tools/arenas/sprawl.py `highway`. The decks are 900 wide (the avenue's width; barriers 40 thick at +-430) and each
  end parts into an off lane and an on lane (|t| 150-450, 300 wide, outer concrete barrier, inner steel guard rail on posts), with
  the street running on between them (300 u) and **under them where they are high**: columns at the outer edge under pitched cap
  beams while the underside is above 400 u (`UNDER_CLEAR`, heavy frames are 336), then an embankment block laid parallel to the lane
  (no steps: they left saw-tooth gaps). A gore barrier closes the deck's middle where the lanes part (detail pass: chevron boards, a
  crash cushion of drums, cones, an amber board over each lane mouth). Nav: the lanes are walkable steps, the street between is ground.
  The deck dressing (studs, lamps, gantries, edge lines) follows the new barrier line `PAR`.
- **Signs that floated** (skink52): the neon blade signs hung 120 u off the block edge whatever stood there (over a low block's car
  park, in front of a set-back tower) on a bracket to nothing. `sign_mount` hangs each on a real tower face within 420 u of the street,
  bottom above the canopy, top under the roof; the blade stands out from the wall (20-160 u) on two arms, and its light is in front
  of it (it was inside). 22 signs (topped up from their own random stream; the outer blocks' fronts carry some).
  **Mirrored text**: Hammer's default face axes read backwards on faces looking -x or +y, so half the shop signs on the canopies
  were mirrored all along (seen on a wall board in the preview). sprawl_ops `READ_U` / `read_uv` gives every sign face the axis that
  reads left to right; a blade is two halves back to back, each reading right on its side.
- **Containers removed** (skink52: "very large", then "Containers can all be removed, we don't need them"): the 30 in the avenues
  are gone (they were the stock 40-ft container at scale 2.4: 690 x 288 x 326 u, four times a car).
- **The void past the ring road** (skink52: "an elegant, AAA quality, on theme container"): `outer_ring`. The sky shell is
  +-7424 (was +-5376, where the terrain stops). Past the ring road the grid goes on: a row of outer blocks (centres +-6000) with a
  street-wall slab, a row of towers facing the arena and a taller one set back behind them (the city layer builds them like any
  tower, never as ruins; the detail pass dresses their faces and billboards, no roof clutter). Every street that leaves the ring is
  closed just past the kerb by a **concrete barricade** (precast T-wall sections set a little out of line, one sometimes missing,
  floodlight masts with a light), and behind everything
  stands the **quarantine wall**: 1900 u, cast-in courses, buttresses, a lit lip and lamps on top, a lit board (QUARANTINE ZONE /
  NO ENTRY / FLOOD BARRIER 7) on it at the end of each street. Outside PLAY: no nav, nothing playable. The fog (end 7000) softens it.
  Cycles previews of the four views (`ramp`, `stub`, `ring`, `outer` in sprawl_preview_bl.py SHOTS) were judged and fixed
  (embankment steps, the blank wall, mirrored text).
- **Load shedding (half-rate simulation)**: core cfg.load `{aiHalfAbove: 24, simHalfAbove: 40}`, counted over the whole server (the
  arena wrapper passes the live total of all copies). Above 24 each script-AI mech thinks every other tick; above 40 its movement and
  lock-on also run every other tick with twice the time step, in two groups by slot. Humans, weapons, bullets, missiles and mech
  collisions always run every tick; the adapter draws a skipped AI mech a tick ahead along its velocity, so it does not judder.
  CS2 bots count as AI. test/load.cjs (11 checks: levels, groups, distance travelled within 30 % of full rate, a 60 s round stays
  finite and fights); 19 suites PASS. **Not measured in CS2** (the test server is down, below): expected ~4 ms off the 64-mech
  tick (AI, movement and lock-on are ~8 ms of it). It does nothing for human mechs: a full human server still needs the 64-HUD and
  per-human numbers.
- **Test server updated** to CS2 1.41.9.7 (SteamCMD validate, gameinfo re-patched) and now **crashes a second after every map load**
  (after "Created physics"): CounterStrikeSharp 1.0.379 predates the update; **v1.0.380 (12 Nov) is "fix: Game Update 1.41.9.7"**.
  Needs skink52's OK to download (49 MB with runtime) and a check of the guard's CSS command shield after it.
- Dunes deploy: six Tripo materials were stale (their AO pictures re-copied with the same image, new date); compiled.

**12 Nov 2026, 04:30: build 30 (18 suites PASS, mock PASS, both addons deployed, plugin harness 3/3, test server on Dunes).**
- **CS2's own HUD**: skink52's recording of `slime_ifr_test hidehud` (every single bit, 2 s each): only bit 4 does anything and it hides
  everything, the chat box included. No supported way removes the score bar, the health number or the bottom icon one by one (the
  pilot's pawn already has no weapons). So: hidden while the pilot is in a live mech, back when dead / garage / intro / watching
  (`ifr_srv <slot> hud 1|0`, SERVER_CONTRACT 12; plugin `HideHudInMech`); plain chat lines go to the message line of pilots whose HUD
  is hidden. **Not seen in game**: the hide and return, the chat relay, whether chat can be typed blind.
- **Sortie**: no capture strip under the beacon chip any more ("BEACON CONTESTED" stayed up and repeated the chip). The A and C
  skink52 asked about are the map's Conquest letter masts (map props), the HUD shows only the B chip.
- **World sounds on the dedicated server: still silent, cause unknown.** skink52 heard none of `!snd 1-4`. server.dll and client.dll
  both name `soundevents/soundevents_addon.vsndevts`; the file and the 99 `sounds/ifr` files are on the server; no sound error in the
  server console. **Next: skink52's CLIENT console after `!snd 1`** (asked). It works on a listen server from Hammer, so a Workshop
  mount may simply work: the loose-file test server is the odd one.
- Waiting on skink52: half-rate simulation for more than ~40 mechs (yes / no).

**11 Nov 2026, night: build 29 (18 suites PASS, mock PASS, both addons deployed, plugin harness 3/3, test server on Dunes 22:19). Waiting on skink52 for three answers.**
- **World sounds are still silent on the dedicated server** (only the single-client tones: hit, kill). The plugin's precache did not
  fix it; the server console has no sound error. Chat `!snd 1` .. `!snd 4` (src/cs2/40_fx.js sndTest) plays one explosion four ways
  (1 normal: source = the mech, StartSound; 2 source + StartSoundOnSingleClient; 3 the sound entity moved onto the mech, StartSound;
  4 moved + single client). **Ask which numbers are heard**, then move every world sound to a way that works.
- **"BEACON CONTESTED" with no enemy near**: the Sortie ring had no height and counted any team 0 mech. Now only wave enemies (npc)
  within 1200 u of the beacon's height. Not reproduced: the likely cause, not a confirmed one.
- **Hard landing plants the mech** (fall faster than `land_fall_speed`): no walking and the slide is braked for the landing lag; a
  quick boost breaks out (it was blocked during the lag before). mechanics 169 PASS. Not played.
- **CS2's own HUD**: the script API cannot hide it. Plugin console `slime_ifr_test hidehud <bits>` sets m_iHideHUD on every pilot
  live (4 all, 8 health, 64 status, 128 chat, 4096 radar: Source 1 names, which ones CS2 honours is unknown). **Try them with
  skink52 on the server**, then set `IronFrame.HideHud` / `HideHudBits`.
- **Script time by stage, 64 mechs** (avg ms a tick): move 4.2, render 3.2-3.4, AI 2.5-2.7, lock 0.9-1.0, separate 0.8, players in
  0.7, weapons + bullets + missiles 1.3. **39 mechs: 9.4-12 ms.** In-game benchmark: the script engine is about 5 x slower than Node
  (3 M arithmetic 278 ms against 58), a line trace 21 us, sphere 16, hull 17, a Teleport 3. Nothing cut yet: traces are already
  staggered and small tweaks buy 10-20 %. The real fix for more than ~40 mechs is half-rate simulation (alternate halves at 32 Hz):
  **built 12 Nov (core cfg.load), see above.** A real 64-player round has no AI (fill is 16 mechs under 22 humans); 64 HUDs are unmeasured.

**11 Nov 2026, evening: second round of skink52's play (Dunes, from Hammer, local listen server). Build 25 + the timing test: 18 suites PASS, mock PASS, both addons deployed (Sprawl without the timing test), plugin harness 3/3, test server on Dunes.**
- **No deprecated script calls left.** The 7 `Instance.*` calls (Msg, ServerCommand, FindEntityByName, FindEntitiesByName,
  EntFireAtTarget, EntFireAtName, IsWarmupPeriod) are `Console.Log`, `Console.ServerCommand`, `Entities.FindByName`, `ent.FireInput`,
  `Entities.FireInput`, `GameRules.IsWarmupPeriod` (src/cs2/10_util.js wrappers, 20_players, 50_hud, 70_server, 90_main; build.json and
  out/sprawl/build.json import the three objects). `python create/test/api.py --strict --check` on both scripts: 0 invalid, 0
  deprecated; the project's line in create/test/api_allow.txt is gone, so CI fails if one comes back. **In-game verified** (skink52's
  console log after the script reloaded with the new calls, and the test server's console): `Console.Log` prints the `[ironframe]`
  lines where `Instance.Msg` did, the HUD entity and all 94 prop entities were found (`Entities.FindByName`), `echo ifr_srv` ran.
  Plugin: the one obsolete CounterStrikeSharp call (TTT body push, `VirtualFunctions.CBaseEntity_TakeDamageOldFunc`) is the
  `OnEntityTakeDamagePre` listener; compiled, TTT round harness test passes, the push itself not seen in game.
- **"Heavy overdrive dropped me to 1-2 fps for 30 s" was my deploy, not the overdrive.** A deploy chain reached the Dunes addon
  while skink52 was playing it in tools mode. The console shows `Reloading Resource [1/114]: materials/...` for about 900 files and
  `On-demand recompile of asset maps/scripts/ironframe.vjs (file CRC changed)`: tools mode reloads every addon file whose date
  changes, and the script restarted mid-round. tools/deploy.sh copied with `cp -r` (new dates on everything), which also made all
  289 compiled files look stale; tools/cache_check.py then re-dated every compiled file. Fixed: **tools/copy_changed.py** (writes
  only files whose bytes differ), cache_check re-dates only outputs older than their content, and **tools/game_open.py**: a deploy
  is HELD (exit 3) while a `cs2.exe -tools` is open on the addon; `IF_DEPLOY_OPEN=1` overrides. build/chain.sh stops there
  ("BUILT AND TESTED, NOT DEPLOYED"). The blast's four outer fireballs are the small effect now (only 8 big ones exist in the pool).
  **The heavy overdrive's own cost on the client is still not measured**: ask for a second try with no deploy running.
- **Static HUD text is about 20 % wider at 1280 x 600** (Hammer's game window), not the 5-10 % assumed at noon: the death card's
  `CTRL OR F: GARAGE (CHANGE WEAPONS AND FRAM` (screenshot). Rows get 25 % + 8 px to lay out in; the label boxes do not clip, a card
  does, so tools/hud.py now FAILS the build when a text in a card-wide box (300 px or more) would pass the box's edge at 20 % wider
  (`hud TIGHT`). Shortened: the death card line (`CTRL OR F: CHANGE WEAPONS OR FRAME`) and two intro lines. The mode clock said
  `WARMU` (console: "HUD text cut in clock"): it says `PREP`. Centred static text sits up to 10 % right of centre at that window.
- **Script time: too slow for a full server (measured).** skink52's game (1 human, 14-16 mechs): avg 3.5-4.0 ms per server tick,
  a 10-12 ms tick about once a second (CS2 warns at 10 ms). A tick has 15.6 ms for everything. **With 64 mechs on the local test
  server** (the new timing test, Team Deathmatch, 47 CS2 bots + 17 script AI, no human, 255 props, five 20 s windows): **avg 11.4-13.6
  ms, max 48-65 ms, 1275-1280 of 1280 ticks at 8 ms or more**, 117-157 traces a tick; the server console fills with `Long frame: 114 ms
  elapsed, 6 ticks` (it cannot hold 64 ticks a second). Where it goes, avg ms a tick: **core simulation 7.7-9.1**, render (moving the
  props) 2.3-2.9, reading the players 0.5-0.6, events 0.2-0.3, loops 0.2-0.3, everything else under 0.2 each; the HUD is nothing here
  because no human was in (not measured with 64 HUDs). The Node mock's 4.1 ms for 64 players was no guide: CS2's script engine is
  several times slower than Node and every trace is an engine call. **Next: time the parts of the core tick (AI, movement and its
  traces, weapons, missiles, lock-on) and cut it to about 5 ms**, before any public test with more than ~25 mechs.
  The test: script inputs `ifr_perf_64` / `ifr_perf_32` / `ifr_perf_off` (src/cs2/90_main.js), fired by the plugin's console command
  `slime_ifr_test input <name>` (guard-locked on a server: the harness unlocks it); `python build/perf_run.py start|read|tail|off`.
- Still open from that log: booster particles follow a hidden rig under the map for a moment (`ifr_pfx_boost_NNN ... outside of cell
  bounds`, console noise only); `soundevents_addon.vsndevts` recompiles on every load in tools mode (a template sound event points at
  the missing `sounds/vent_01.wav`); two `ifr_vfog` volumetric fog controllers (one per arena copy), neither set to master.

**11 Nov 2026, noon: skink52 played Dunes on the local test server (joined through Hammer). Then four changes from that session, build 23: 18 suites PASS, mock PASS, both addons deployed, plugin harness 3/3, test server restarted on Dunes 12:55.**
- **SEEN IN GAME, good:** AI mech kills count on the scoreboard (the stand-ins; console: "AI mech kills are credited as real CS2 kills
  through CS2 bot stand-ins"), the killfeed hides them (plugin `KillfeedHumansOnly`), CS2 bots join on Dunes (4 of them), destructible
  props bind ("94 of 94 entries have their ifr_car entity").
- **!help cards were clipped in game** (screenshot: every row one to three letters short, the key column running into the text). Cause:
  a static label is a row of glyph panels sized for 1080 high; CS2 scales the HUD to the window and rounds each panel to whole pixels,
  so at a smaller window every letter is a fraction wider, a 30-letter row several letters wider, and what does not fit the row is not
  drawn. Fix: both cards are ONE baked picture each (tools/hud.py `bake_card`, `card_ctrl.png` / `card_help.png`, drawn at twice the
  size): nothing to re-flow. Every other static row (`slbl`) is 14 % + 6 px wider than its letters. Not seen in game yet.
  **This also means all static HUD text is slightly wide at small windows**: right-aligned and centred static labels sit a few px off.
- **World sounds silent on the server** (skink52: "sounds for being hit play in game, but other sounds dont (shooting etc)"). Tones
  (`StartSoundOnSingleClient`) played; everything started on an entity did not. Likely cause: the addon's sound events file is loaded
  by CS2 only for a mounted addon; the test server has the files loose under game\csgo (tools/server_copy.py), so the server never
  knew the events. Fix in the plugin: IronFrame `Precache` adds `soundevents/soundevents_addon.vsndevts` to the server's resource
  manifest on `mg_ironframe_*` maps (slime-mg-gm docs/ironframe.md "Sounds on a server"). **Not heard yet.** If still silent: the next
  suspect is the sound's source entity (the null-model anchor props) not being sent to clients.
- **`/help` and `/garage` did nothing for the map** (skink52: "/help works to bring up the server help, but it doesn't bring up the
  ironframe help"). CounterStrikeSharp keeps a `/` chat line to itself, so the script never saw it. Now the plugin passes its own
  commands on: `RunScriptInput ifr_cmd_<name>` on `ifr_script` with the pawn as activator (help, garage, back, od, cam, hints, bots, mode;
  SERVER_CONTRACT.md section 11). `/garage` and `!garage` open the map's hangar garage on a mech map (the plugin's chat garage is the
  fallback without the script); a `!` line reaches the map twice (chat and input), the second is dropped (same word within 0.8 s).
  Mock: help by chat and by input both checked. Not tried in game yet.
- **Starter parts' upgrades cost credits** (skink52 saw FREE next to priced upgrades in the garage; every part has the same track, so a
  starter got for nothing what a bought part pays 4.5 x its price for). `caps.upgrade_floor_cost` 2000 in parts.json (the cheapest paid
  part): a free part's steps are 600, 1200, 1800, 2400, 3000. Core `IF_upgradeCost` and plugin `Catalog.UpgradeCost` use the same floor,
  so the garage shows what the server charges; the operator's `UpgradeFloorCost` is 0 = the catalogue's. Levels already taken stay.
  Stand-alone (no plugin) upgrades are still free. Tests: garage_upgrades (600 CR on the starter frame), plugin harness (`upg 101`
  denied with 250 credits).
- **Ammo, healing, overdrive, artillery** (skink52: "the most annoying part of gameplay is running out of ammo - there's nothing you
  can do about it, and there's also no way to heal"; "no artillery fire seemed to reach my lock"). docs/FEATURES.md has the numbers.
  Overdrive is a FIELD REFIT on light and medium frames (+45 % AP, EN and all ammo full) and a bigger blast on heavies (3 200 within
  1 200 u, +40 % EN); every kill salvages 25 % ammo and 8 % AP; a weapon rested 6 s rebuilds its reserve (full in 120 s), so nobody is
  left dry. Artillery used to fire the instant it was earned at whatever was locked, at the spot the target had already left: it now
  arms after 1.5 s, each shell aims 0.9 s before landing at where the target will be, with a falling streak, and says so when the
  target is too close. Unit tested (features: 62 checks); test/balance.cjs re-run: a 32 v 32 AI Team Deathmatch round lasts 431 s (424 s before) and pays a median 487 credits (475), so bots refitting and salvaging barely move it. Nothing of it played yet.

**11 Nov 2026, 11:52: Dunes on the local test server (C:\cs2server, port 27015).** `python -I tools/server_copy.py copy mg_ironframe_dunes`
copies the map .vpk and the addon's compiled files under the server's game\csgo (5 390 files, 1.36 GB; manifest
logs/server_copy_mg_ironframe_dunes.txt; `remove` takes exactly those off again). Re-run `copy` after every deploy, or the server keeps
the old script and HUD. Seen in the server console after `changelevel`: the script in server mode, **three CS2 bots joined** (so the nav
mesh does bring bots on Dunes), no script errors. Expected noise: world_visibility.vvis_c missing (no-vis build), lightmap textures
(a dedicated server draws nothing).

**11 Nov 2026, afternoon (skink52: "The !help menu has a lot of text get cut off. Still no kill credits in game for killing bots"): all 18 suites pass; mock: 3 AI mech kills = 3 real kills, bots alive after, no team kill penalty; script + HUD compiled in both addons 11:04 / 11:07 (no map rebuild needed). Note: a Sprawl deploy with SPRAWL_NO_MAP=1 does not compile the script and HUD: run sh tools/compile_ui.sh mg_ironframe_sprawl after it. Unseen in game.**
- **!help**: it was the controls card plus four long sentences paged through the message line (Labels, 3.5 s a page while the next
  waited; the Label font's in-game width has never been seen, and a row wrapped to the last pixel is cut at both ends if CS2 draws
  wider). Now !help shows two static cards for 25 s (a second !help puts them away): the controls, and beside them HOW TO FIGHT
  (4 lines) and CHAT COMMANDS (7) as neon glyph pictures: no Label, no wrapping, no paging (tools/hud.py `HELP_TIPS` / `HELP_CMDS`,
  panel `ifr_help`; 80_chat.js; holding Tab shows both for 12 s). The build fails if the cards reach under y 600 (CS2's chat box).
  The controls card's overdrive row said SPACE + R + E: now HOLD R + E. Every other message on the line now wraps at 88 % of the
  box (50_hud.js `IFR_HUD_LINE_FIT`), as insurance against the same cut. **If text is still cut anywhere, a screenshot says
  whether it is width (ends of a row missing) or time.**
- **Kill credit for AI mechs**: two causes found.
  1. `mp_teammates_are_enemies 0` (00_config.js): a scripted kill of a pawn on the pilot's own CS2 team is a team kill (no kill,
     -1). Skirmish is free-for-all on two CS2 teams, so half its kills were that. Now 1 (docs/reference/cs_script-notes.md said so).
  2. The enemies of a Sortie, and the fill wherever CS2 bots did not join, are the script's own AI mechs: no pawn, so CS2 had
     nothing to count (only `AddScore`). Now a CS2 bot's pawn stands in (20_players.js `npcKill`): it takes the kill from the pilot
     (kills column, killfeed line with that bot's name) and is revived 0.5 s later, back on its mech or in the booth. Picked: a bot
     whose mech is down, else one on the other CS2 team, else the one used longest ago. A Sortie keeps at least two CS2 bots for
     this. Cost: those bots' deaths column counts the stand-in deaths, and the killfeed names the bot, not `AI-7`.
  - No CS2 bot in the game: score only, as before, and the console says so once. **`!bots` in chat shows it**: "CS2 bots N of Q.
    AI kills: R real, S score only". If N is 0 the bots are not joining (the console then also says "no CS2 bots joined").
  - Not possible without a pawn: a killfeed line with the AI mech's own name.
  - **Killfeed on a server** (skink52, 11 Nov: "We can have server side obfuscate bot kills, and only show human->human kills"):
    the SlimeMG IronFrame module now sends only pilot-against-pilot `player_death` lines to clients (`KillfeedHumansOnly`, default
    true; slime-mg-gm docs/ironframe.md "Killfeed"). Stand-in kills and deaths to AI mechs still count (kills column, contracts,
    stats) but show no line. Stand-alone (no plugin) the feed still names the stand-in bot. Not seen with a client yet.

**11 Nov 2026, midday (skink52's notes after looking at Sprawl): all 18 suites pass, both maps rebuilt 10:26 (Dunes) / 10:39 (Sprawl), no deleted entities, no failed resources, cache checks clean; Sprawl has 44 destructible cars an arena, Dunes 47. Unseen in game.**
- **Sprawl ramps** (skink52: "where the ramps to the top level meet the ground make no sense - they ramp down halfway into the roads
  below"): the decks ran to +-3600 and the ramps came down at +-5035, i.e. across the outer ring road (4350-5250) at half height.
  Now (sprawl.py `HW_END` 2860, `HW_FOOT` 4335, `HW_PIERS`): the decks end just past the 2400 crossing and each ramp lands at
  the kerb of the ring road, beside the outer block. The ramp's top runs from the deck's top edge to the ground (it sat 57 u
  under the deck: a lip), a stepped concrete fill stands under it (the nav solids always treated it as solid: an unseen wall),
  the barriers end in low blocks. Piers at -1800 / -600 / 600 / 1800 under both decks (the N-S one had none between +-2400).
  The detail pass reads the deck length from the plan (`hw_end`, `hw_foot`, `hw_piers`). Nav grid regenerated.
- **Vehicles in the water** (skink52: "they'd be destroyed if they were there irl"): the eleven in the flooded square are wrecks
  now: stripped / burnt bodies, rust tints, lying at an angle, deeper in the silt (sprawl_detail.py, the flood loop).
- **Destructible props** (skink52: "could we implement some interactive props? like cars that if take enough damage have
  explosions etc and burn"): core `src/core/88_props.js`, adapter `src/cs2/48_props.js`, test `test/props.cjs` (22 checks).
  - A prop has hit points (600; buses, trailers, trucks 1 600). Hitscan shots and beams, bullets in flight (they pass through:
    a car is not cover), every explosion and a mech walking over it hurt it. At 0: it explodes a tick later (radius 330, 900
    damage, credited to whoever destroyed it, weapon key `car`), so a row of cars goes up as a chain; it burns 14 s (a smoke
    column, sparks); the body turns dark and slumps. Walked over: crushed flat into the ground, no explosion. All whole again
    at each round start.
  - Map side: `prop_dynamic_override` named `ifr_car` (the same name in every arena copy; matched to `arena.cars` by position).
    Sprawl: one in three of the one-piece street cars, at most 64 an arena (sprawl_detail.py `LIVE_EVERY`, `car()`), written
    into the Sprawl arena.json. Dunes: every second van / saloon / trailer / truck and every second barrel group and propane
    cluster of the detail patch (`LIVE` in tools/patch_dunes_detail.py; 47 an arena, list in data/cars_dunes.json, merged
    into arena.json by common.py `write_arena_json`).
  - **Look in game**: the console line "destructible props: N of M entries have their ifr_car entity" (N = M expected); that
    `Color` darkens these models (else the wreck look needs a second model); the smoke column; that 171 (Sprawl) / 94 (Dunes)
    dynamic props cost no frame rate. Not done: a fire particle (smoke and sparks only), debris, a scorch decal.
- Tests: `sh build/run_tests.sh` (now with props) all pass.

**11 Nov 2026, late morning (skink52's notes on the morning batch): all below is tested (17 suites, 64-player mock), deployed, and both maps are rebuilt (Dunes vpk 09:13, Sprawl vpk 09:25; cache_check clean, no failed resources in either build log). Unseen in game.**
- **Overdrive keys** (skink52: "Space R + E for overdrive is hard to use - difficult to position when forced to hold space (which is
  jump)"): now **R + E pressed together and held** (both shoulder buttons, within 8 ticks of each other; 45_features.js `featInput`,
  `OD_CHORD`). A lock held on R with a shield raised on E later is not an overdrive; while the meter is full a lone fresh shoulder
  press waits 0.12 s so the chord's first key does not fire. Space + R + E and `!od` still work. Every prompt changed (HUD
  `READY: HOLD R+E TOGETHER`, hints, controls card, chat help).
- **Crew shoulders** (skink52: "shoulders seem rolled forwards on pilot", then "they just look too narrow"): the arms-down poses
  drop the arms less, open the chest, and a new `shift` in tools/hangar_crew.py moves each arm joint 1.5 u out and 0.6 u up, so
  the shoulder line stays as wide as in the A pose (preview/crew/crew_sheet3.jpg). All six props re-exported.
- **Nav mesh for real CS2 bots: it exists.** Both maps have the `func_nav_markup` seeds at the pawn booth (generator
  common.py `booth`, Dunes tools/patch_nav_vis.py) and every full build makes the nav file: "Nav mesh loaded with 4 nav areas"
  in both build logs. That is all a bot needs: bot pawns stand in the booth (`bot_stop 1`), the script flies their mechs. An
  arena-wide nav flood was tried on 9 Nov (ARENA_NAV in patch_nav_vis.py) and the build ran over 3 hours: not wanted. The to-do
  line at the top of this file was stale. **To see in game**: bots join within 20 s of a round start (else the console says
  "no CS2 bots joined" and the script's own AI fills).
- **M4, Dunes detail** (skink52: "start these"): `tools/patch_dunes_detail.py`, additive, vis group `ifr_dunes_detail`
  (delete the group in Hammer to remove it all; a re-run replaces it). Per arena copy 423 stock props at 0.6 human scale,
  solid 0, not lightmapped: container yards with stacks, trailers, generators, flood-light masts and fences (8 camps: by the
  refinery, by the wreck, on the rims of plateaus A and C, inside both drop rims), supply columns of wrecked trucks and cars
  with tyres / barrels / barriers on tracks inside both rims and where the canyon floor is free, power-line poles, flood-light
  rings round the three plateaus, relay towers near the rims, 148 scatter spots (half-buried wrecks, tyre piles, lone
  containers). It keeps clear of every prop skink52 placed (radius by that prop's scale: the rock fields, the canyon-floor
  rocks), of structure cells, steep ground, objective centres and drop pads. Placement map: preview/dunes_detail_map.jpg
  (yellow containers, green vehicles, pink masts, white small things, blue = skink52's props). Backup of the map before it:
  backups/mg_ironframe_dunes.*.pre_detail.vmap. ~1.4 M LOD0 triangles a copy: **check the frame rate on Dunes**, and that
  nothing floats or sinks (ground heights are the generator's: hand-sculpted terrain would differ).
- Still open: audio mix, bigger muzzle flashes, the waist seam check, a real-server run of the S2 / S3 payloads.

**11 Nov 2026, ~08:30 (morning batch; skink52: "pick up the remaining tasks now"): both maps rebuilt with everything below (Dunes vpk 08:10, Sprawl vpk 08:35; cache_check clean on both; script + HUD current on both). All unseen in game.**
- **A, the mech as one machine** (30_render.js `rigWeight`): a standing turn is steps now (weight shift + a planted foot with its
  stomp every ~40 deg while the legs are dragged round), a crouch into a boost, a push off the ground at take-off, a roll into
  a quick boost (`rigDash`, 40_fx.js `qb`). All on the existing landing spring, so they decay by themselves. Not done of A: the
  waist seam check at 60 deg twist per frame (tools/review_frames.py) and a collar ring in mdl2cs2 if a seam shows: look in game first.
- **C, jump-in, second half** (60_garage.js `garageRows`): part lists show what a pilot can use first (equipped / owned, then
  buyable by price, then "need credits", then rank-locked by rank; frames keep their class order); the cheapest buyable part of
  each kind is tagged `NEXT BUY`, an owned starter part `GOOD START`. The training wave was not built: the contextual first-time
  hints (45_features.js HINTS: start, lock, stall, heat, stagger, overdrive, crate, mode goal ...) already cover that ground.
- **F, post-processing**: Sprawl has its own bloom (`postprocess/ifr_sprawl.vpost`, made at deploy by tools/arenas/post.py from the
  template's file: threshold 2.84 -> 2.1, strength 2.0 -> 2.3, widest blur slightly violet) so signs, screens, beams and thrusters
  glow. Blind tuning: if it washes out, raise the threshold in post.py `LOOKS`. Dunes keeps the template look. Nav mesh for real
  CS2 bots: not started.
- **M5, hangar crew** (skink52: "pilot models in the hangar ... gmod pilot and worker models"): `tools/hangar_crew.py` runs three
  converted GMod player models (Urban Assault Eclipse pilot and HMC worker, workshop 3772745299; mechanic, 734781319) through the
  player-model converter, poses them (looking up at the machine, at ease, marshalling with both arms up, kneeling at a foot,
  reading a slate) and writes six STATIC props `models/ifr/crew/*.vmdl` at 0.6 human scale with the models' own materials
  (create/playermodels/gmod2cs2.py got the `GMOD_STATIC_DUMP` hook for it). `tools/patch_crew.py` puts three of them round every
  garage bay (ring 215 u, on the camera's side, varied per bay): 36 props in vis group `ifr_crew_patch`, additive on Dunes' live
  map (backup backups/mg_ironframe_dunes.20261111_080313.pre_crew.vmap); Sprawl gets them with the imported hangar. Previews:
  preview/crew/crew_sheet.jpg, crew_sheet2.jpg. Third-party models: never in git (out/ and preview/ are ignored).
  **Look in game**: nobody stands inside bay furniture or the turning mech (else change `RING` / `SPOTS` in patch_crew.py and
  re-run it: the group is replaced), and the props are lit (probe-lit, `bakelighting 0`).
- **Small items**: the arch legs in Sprawl's square are in the nav solids (sprawl.py `plaza`); the plugin answers deny codes 9 / 10
  with its built-in texts when an older SlimeMG.json has only eight (Garage.cs `DenyBuiltin`); `tests/run.py --only ironframe` 3/3.
- **S4** needs nothing new: the server's own `!stats` and `!top` already read the mech counters the map sends (docs/stats.md).
- **B** left: bigger muzzle flashes (needs eyes on the game). **E, audio mix**: not touched; volumes cannot be judged offline.
- Tests: `sh build/run_tests.sh` all pass, 64-player mock clean.
- **Still open on the list**: M4 (Dunes detail, additive only), nav mesh, E, the waist seam check, hud_check's 6 "under CS2 chat"
  notes at 1920, a real-server run of the S2 / S3 payloads.

**11 Nov 2026, ~04:55 (04:01 continuation): list item 8 C, first half (quick starts) done, tested (all suites + 64-player mock), deployed
to both addons 04:51. Unseen in game.**
- A pilot's first garage of the session opens on the SORTIE tab with the cursor on the launch row (Space flies at once); under it
  three quick starts from `parts.json` starter loadouts: `Quick: Assault` (White Glint), `Quick: Scout` (Krasnaya), `Quick: Brawler`
  (Ogre). The one under the cursor stands in the bay; Space saves it to the active slot and launches. Own key legend on that tab.
  A ranked pilot of the server (rank > 1) and every later garage open on the list as before. 60_garage.js `GARAGE_QUICK`, `garageRows`,
  `garagePick`, `garagePreviewIds`, `garageOpen`; test/garage_upgrades.cjs last section (419 checks).
- Left of C: the RECOMMENDED tag and sort in the part lists, the first-sortie training wave with prompts.
- Next: 7 A (the mech as one machine), the rest of C, then E, F, S4, M4, M5.

**11 Nov 2026, ~05:00 (04:01 continuation): list item 8 D (teammate marks) done, tested, deployed to both addons. Unseen in game.**
- Each pilot's HUD puts a green triangle (`ally.png`, tools/hud_images.py `ally_mark`) over the head of up to 8 living teammates that
  are on screen and within 9 000 u, nearest first, dimmed past 4 500 u (`stFar`); a mark keeps its mech so marks do not swap.
  Rule (90_main.js): nobody in Skirmish, every pilot and AI ally in Sortie, the own team elsewhere, same arena copy only. Driver
  50_hud.js `ifrHudAllies` (every second tick per pilot), layout tools/hud.py `FR_N` (ids `ifr_fr<k>` + `x` / `y` on the lock
  bracket's grid). 504 panel ids of 800. Preview: build/hud/hud_lock.png (two marks in the `lock` state).
- Tests: `sh build/run_tests.sh` all pass (hud_driver has the marks' cases; hud_ids walks the 24 new ids).
- Also: tools/arenas/deploy_sprawl.sh leaves an identical vmap alone (no more false "vpk built before the vmap" from cache_check).
- In game, check: the triangle sits over the head (uses the same projection as the lock bracket, so if the bracket is right this
  is); 8 marks with 0.1 s eased steps do not jitter when the pilot turns fast.
- Next: 7 A (the mech as one machine: waist seam at 60 deg twist, foot slide, boost crouch / landing bend), then 8 C (starter presets,
  training wave), E (audio mix), F (nav mesh, post-processing), S4, M4, M5 (hangar pilots / crew).

**11 Nov 2026, ~04:35 (04:01 continuation): list item 4 (M3, "3D skyboxes") done as far scenery painted into the sky panoramas; both maps
rebuilt (Sprawl vpk 04:20, Dunes vpk 04:29, cache_check clean on both). Unseen in game.**
- Why not a real 3D skybox (skink52, ~01:40: "investigate capacity for custom moondomes to accomplish sharing 3d skyboxes between
  locations"): the arena copies are thousands of units apart and a 3D skybox is drawn from player position / 16, so it sits wrong
  from every copy but one. Every copy already stands in its own moondome shell (csgo_moondome, `g_flCubeParallax 0` = at infinity)
  with a toolsskybox shell inside for the sky light, so the far world goes INTO the panorama: same from every copy, no second map.
- `tools/sky_vista.py` (new), called by `tools/sky.py make()`: drawn at 8192 x 4096 in a strip around the horizon, saved `IF_SKY_W`
  wide (default 8192; the old skies were 4096). Sprawl: three depth layers of towers (lit windows in floor runs, tiers, masts,
  crown lines, neon edges, LED panels, aviation lights), six supertalls with spires that fade into the overcast, elevated-road light
  strings, the city's glow on the mist, a haze band and an opaque ground under the horizon. Dunes: three ranges of mesas with
  flat-capped buttes (cliff + scree), dusk rim light, strata and gullies, two refineries (stacks, tanks, platforms with lights,
  three flares each, smoke plumes) at yaw 205 and 318, lone derricks, a dust band.
- Preview without the game: `python -I tools/sky_vista.py <sprawl|dunes> preview/sky` (strip quarters + pinhole views a player
  would see). Judged there: two passes each (Sprawl: windows were a dot matrix and far towers lighter than their sky; Dunes: ranges
  were 1-2 deg high and the refinery invisible).
- Limits, by design: no parallax, no animation (blinking lights, flames = props / particles in the arena if wanted). The compiled
  sky textures are block-compressed (6-9 MB): **look in game whether the window dots survive the compression** and whether the
  8192 panorama shows sharper than the old one; if a sky shows as an error material, `IF_SKY_W=4096` and rebuild.
- Panorama yaw 0 = +x is still unverified (docstring of tools/sky.py): the refineries' compass directions may be rotated.
- List item 7 B ("hits that read") checked against the code: damage skins by AP band, damage smoke, death gibs and wreck, hit
  marker, incoming-fire arrows all exist (src/cs2/46_damage.js, 90_main.js). Left of B: an in-game look, bigger muzzle flashes.
- Next: 7 A (the mech as one machine), then 8 (D teammate markers first: skink52's friend-or-foe remark).

**11 Nov ~01:25 (superseded by the 04:35 block): list item 4 (M3, 3D skyboxes) design notes.** Reminders set for 04:01 and 09:02 continue here.
- Tool: `create/make_skybox.py` (terrain ring at 1/16, `--plain`, `--layout`), worked example projects/trenchwarfare-cs2/tools/make_map.py
  line ~1018 (`skybox_reference` at the origin, targetMapName `maps/<map>_3dskybox.vmap`, fixupNames 1, worldGroupID skyboxWorldGroup0)
  and its tools/make_skybox.py; guide.md line 147.
- **The problem to design around**: the arena copies are offset from each other (tools/arenas/copies.py: read the real offsets first),
  but there is ONE skybox, drawn from player position / 16. A pilot in a copy 8 000 u away sees the ring from 8 000 u off: near
  skybox content would sit wrong (15 deg at 30 000 u). Domes per copy cannot work (they would overlap at 1/16).
- **Design**: far layers only, 60 000-100 000 world units out (3 750-6 250 skybox units, inside the +-16 384 limit), so the offset
  shifts them under 8 deg; bases sunk in a thick haze / glow band so no horizon line gives the offset away; centre the skybox on the
  MEAN of the copies' offsets to halve the error. Sprawl: layered lit supertall silhouettes (emissive window cards, aviation lights,
  a few far elevated roads as light strings, cloud-base glow). Dunes: far mesas and a ridge, refinery flares / derricks as small
  emissive points, dust haze in the map's fog colour; Dunes main map only gets the `skybox_reference` by ADDITIVE patch with a backup.
  Check each copy's sky shell material shows the 3D skybox (toolsskybox does). Make an offline preview from each copy's centre before
  building; judge it critically. Then rebuild Sprawl (~13 min), Dunes map build (~35 min, `build_maps.ps1 mg_ironframe_dunes`).
- Added to the list (noticed 11 Nov): (a) `cache_check --vpk` date warning on Sprawl after a script-only deploy: make deploy_sprawl.sh
  skip copying an identical vmap; (b) diff the Sprawl nav grid before / after the detail pass; (c) two DenyTexts for codes 9 and 10 in
  the default SlimeMG.json; (d) `hud_check`'s 13 problems under CS2's chat box.

**Git, 11 Nov ~01:10**: both repos are on branch `ironframe-test`, pushed (cs2mapping e7f914c, slime-mg-gm e98a989; test commits, skink52 allowed them). STAY on that branch: the project is not on `main`, so `git checkout main` removes its tracked files from disk. preview/ and backups/ are git-ignored. Not merged, no PR.

**11 Nov 2026, ~01:00 (main session): list item 5 (M2, Sprawl detail from references) done by an agent; Sprawl has the 00:15 script + HUD
(compiled 00:54). Both addons are now on the same script.**
- Full write-up: `out/handover_sprawl_detail.md`; gap table per area in docs/SPRAWL_NOTES.md "Detail pass"; references (20 images +
  sources.txt) in `C:\source1\ironframe_work\refs\sprawl\` (never in git). Map vpk 00:51, 61.6 MB (was 38), 8 min compile.
- Added: broadcast arch with LED screens and mast over the dais, plaza rim steps, bollards, duckboards, festoon cables, advert pylons,
  promenades, tram + stop, bus shelters; avenues with road markings, puddles, 168 cars, guard rails, lamps, poles and wires, shopfront
  tiles with awnings / signs / AC units; lane paint, gantries and lamp masts on the elevated roads, a car park under them; AC units,
  fire escapes, roof tanks, billboards, two tower cranes. A storey is now 76.8 u and human things 0.6 of CS2 size (mech = 3-4 storeys).
- New tools in tools/arenas: `sprawl_detail.py`, `sprawl_detail_mats.py`, `sprawl_kit.json`, `sprawl_preview.py` / `_bl.py` (offline
  Cycles preview, before / after pictures in preview/arenas/sprawl_detail_*), `sprawl_prop_meshes.mjs`, `sprawl_cost.py`.
- Learned: lightmapping the detail made 687 428 charts and the bake stopped: detail meshes and props are probe-lit (`bakelighting`
  off). Stock `car004b`, `van001a`, `van_glass`, `concretebags` have models in pak01 but no materials: not used.
- Cost, whole map: prop_static 503 -> 2 633, prop LOD0 triangles 92 k -> 2.9 M, world mesh triangles 85 k -> 563 k, lights 216 -> 1 065
  (baked only), run-time entities 1 759 -> 1 786.
- **Check first in game**: (1) are the detail meshes really non-solid (`mapbuilder.nonsolid`): if not, kiosks / rails / the tram block
  mechs and bullets; (2) probe-lit detail next to the lightmapped street; (3) fade pop-in at 3 000-5 200 u; (4) frame rate with a full
  arena; also paint / puddle z-fighting, shelter and crane orientation, the steam particle; the game will be darker than the previews.
  The nav grid was not diffed against the old arena.json (SOLIDS / STRUCT untouched, so it should be equal).
- `cache_check --vpk` now reports "vpk built before the vmap was written": the 00:53 script deploy re-copied the same vmap; the vpk
  is current. A map rebuild (`sh tools/arenas/rebuild_sprawl.sh`, ~13 min) clears the message.
- Next on the list: 4 (M3, 3D skyboxes for both maps), then 7 (A + B) and 8.

**11 Nov 2026, ~00:15 (main session): list item 6 (S2 + S3) done by an agent, merged, tested, deployed to Dunes 00:10.**
- Full write-up: `out/handover_server.md`; contract in docs/SERVER_CONTRACT.md sections 3-4 and 8-10, server side in slime-mg-gm
  `docs/ironframe.md`. Six named loadout slots with an accent colour, callsign / title / badge (12 titles, 8 badges from career
  counters), camera preset, hints off, favourite frame; garage PILOT tab; chat `!callsign !name !title !badge !cam !hints !contracts
  !top !loadout 1-6`. Leaderboard plate (top five + own place), daily-contract strip on the HUD, operator rules from SlimeMG.json
  `IronFrame.Rules`, `IronFrame.HideHud` (pawn `m_iHideHUD`, off by default, bits unverified). New shared data `data/career.json`.
  DB migration 3 applies itself. HUD 480 panel ids of 800.
- Tests (`sh build/run_tests.sh`, all 17 suites pass, new test/career.cjs 144 checks); plugin `tests/run.py --only ironframe` 3/3
  (agent's run; it rebuilt the plugin on the LOCAL test server C:\cs2server only).
- **Not seen on a real server**: multi-page payloads through the mailboxes (`q1`, `o1`, `r1`, `t1`), `ifr_server` reading mailbox 00,
  HideHud bits, the accent tint on weapon materials, where the two new plates sit next to CS2's panels. `hud_check` still lists 13
  problems in the vitals / reticle area under CS2's chat (old, leftover 1's area).
- An existing SlimeMG.json has eight `DenyTexts`: codes 9 and 10 read "refused (9)" until two texts are added.
- (Superseded 00:54: Sprawl has it.) Sprawl had NOT had this script / HUD yet (the Sprawl detail agent owns its pipeline until it reports; then
  `SPRAWL_SCRIPT=1 sh tools/arenas/rebuild_sprawl.sh` or a full rebuild).

**10 Nov 2026, ~23:20 (main session, after the usage reset): list items 1, 2, 3 done; Dunes deployed 23:12-23:16, Sprawl fully rebuilt (see the log lines in logs/sprawl_rebuild_watch.log); NOT played.**
- **Leftover 1, the bottom HUD off the mech**: vitals and weapon boxes now leave `MECH_GAP` 290 px clear on the screen centre (tools/hud.py;
  the cluster starts ~100 px under CS2's chat box at 16:9, only while the chat is open). The kill line and the message line moved out of
  the mech's place too: a 500 px column of four rows right of the mech, over the weapon boxes (`LINE_W`, `MSG_SHIFT`). 462 panel ids.
- **Leftover 2, CS2's own HUD**: a map script cannot hide the health number, the rank emblem or the top scoreboard (`sv_disable_radar 1`
  is already set; client cvars from a script are unreliable, cs2-gotchas). The way is the server plugin: set the pawn's `m_iHideHUD` bits
  for pilots in mech mode (IronFrame module; unverified which bits CS2's Panorama HUD honours). Queued as part of S3 below.
- **Leftover 3, balance** (docs/BALANCE.md regenerated, `node test/balance.cjs 2 2`): with missiles that hit and the weaker jets the
  table had moved a lot (VM-6 44 -> 80 %, flamethrower 84 %, HM-4 Pod 75 %, AC-Drum 92 -> 3 %: a braced cannon stands still under
  missiles, energy shotgun 24 %, grenade launcher 28 %). Two passes: VM-6 470 -> 310 per missile, HM-4 Pod 350 -> 300, flamethrower
  140 -> 100 and burn 400 -> 260 /s, AC-Drum brace 0.2 -> 0.06 s, energy shotgun 100 -> 125 per pellet, grenade launcher 1 200 -> 1 450.
  Result: arm families 39-67 %, shoulders 34-64 %, no flags. Frames (`node test/frames.cjs 4 normal`, before the trims): 44-57 %, RX-78
  39 % LOW (not retuned). The plugin's catalog copy refreshed; `tests/run.py --only ironframe` 3/3.
- **S1, more stats to the server**: core `pilotStats(slot)` (per-round counters in `m.sum`, kills / damage per weapon key in `m.wsum`),
  adapter `srvRoundStats` -> queued `echo mgstat` lines, 24 a tick (docs/SERVER_CONTRACT.md 2b; slime-mg-gm docs/stats.md row; no plugin
  change: mgstat stores any name). ~20-35 lines per pilot per round. Tests: test/playtest3.cjs section 6, `node test/server_stats.cjs`
  (35 713 checks on names and values); the mock engine prints `mgstat stats sent (...)` when a run sends any. Not seen end to end on the
  live server (the mock run here did not reach server mode).
- **M1, Sprawl's road barriers** (tools/arenas/sprawl.py `highway(cross=)`): the two elevated roads meet at the same deck height at
  (-2400, 2400); each road's barriers used to run straight across the other. They now stop at the junction's corners with a corner post,
  have a coping, end posts on both roads, pillar heads under the deck, and the ramps carry barriers (checked against the box helper's
  orientation). Sprawl fully rebuilt for it.
- Tests on the merged tree (23:10): mechanics 169, playtest_combat 29, playtest3 54, server_stats, features 35, traits 83, auras 395,
  objectives 45, garage_upgrades 413, hud_strings, hud_driver 17, hud_garage_turn 7, hud_ids, weapon_mounts 23, beam_ladder, sim 64 x 60,
  parts_check, tscheck both scripts, mock_flows both (332 / 333 ids).
- Next on the list: 4 (3D skyboxes), 5 (Sprawl detail from references), 6 (S2 + S3), then 7 and 8. Best started in a fresh session:
  this one's history is very long, and a fresh one reads this file and costs far less per step.

**10 Nov 2026, ~21:00 (main session): fifth playtest (the 20:28 build on Dunes, a screenshot + an 84 s recording) fixed; deploy state at the
end of this block.** skink52: "text becomes a little hard to read", "'destroyed slot 64' was staying on screen too", "all mechs now have the
red above their heads, it doesnt seem to show who is an enemy and who is friendly". Good news in the recording: the Label HUD works (bars,
weapon boxes, plate, streak, overdrive, lock ring all live; no panel-id errors seen on screen).
- **Text**: the Labels' glow was a 6 px shadow in the text's own colour, which smeared the letters: now a tight dark contour
  (`text-shadow: 0px 0px 3px 3.0 #000000f0`, tools/hud.py `glow`), Text / Dim colours a step lighter. Still Noto Serif Bold; if small text
  (20 px) is still weak in game, the next step is Stratum2 for the XS / S sizes (not measured: tools/hud_label_metrics.json is Noto's).
- **"DESTROYED SLOT 64" stuck**: `.KillPop.stPop` / `.Badge.stPop` carried `opacity: 1` and the pop class stays on after `stOn` goes: the kill
  line and the +XP badge never left. The pop rules no longer set opacity. "SLOT 64": `nameOf()` had no name for a script AI mech: now the
  mech's own name ("AI-3").
- **Markers**: in Sortie every AI was red, the allies too: the wave (team 0) is red, pilots and AI allies cyan (30_render.js `iffColor`).
  Team modes stay T orange / CT cyan; props have no per-viewer colour, so "friend or foe" there is the team colour (the pilot plate
  shows the pilot's own).
- **Camera**: `CAM_UP_ORBIT` 10 -> 28: in the recording, aiming a little uphill already stopped the orbit and the mech sank behind the
  bottom HUD.
- Stills from a recording without ffmpeg: headless Blender (`blender -b --python <script>`: a movie strip in the sequencer, render
  stills); the script used is not kept in the repo.

## Leftover work and AAA plan (written ~21:00 on 10 Nov 2026 for the 23:04 continuation; do them in this order, one at a time)
**The complete task list, in order** (skink52, ~21:00: "make sure your complete task list is ready to go, and you're aiming AAA quality";
details of each item are in the paragraphs below; finish one, test, deploy, note it here, then the next; skink52 may reorder):
 0. DONE 20:50: the Dunes build ended clean (build_maps.ps1: OK in 4.5 min; cache_check --vpk: no gaps, 264 models). Dunes now draws beams, objective markers and the bubble.
 1. DONE 23:20 (console read still open: needs Workshop Tools running). Leftovers 1-4: the bottom HUD off the pilot's mech; CS2's own HUD hidden; balance re-run; console read.
 2. DONE 23:20. S1: more stats to the server (map side, batched).
 3. DONE 23:20 (unseen in game). M1: Sprawl's elevated-road barriers at the joins.
 4. DONE 04:35 11 Nov (painted into the moondome panoramas; unseen in game). M3: 3D skyboxes for Sprawl and Dunes.
 5. DONE 01:00 11 Nov (unseen in game). M2: Sprawl detail pass from reference images, the central square first.
 6. DONE 00:15 11 Nov (unseen on a real server). S2 + S3: customisation that follows the pilot; server -> map information and match rules.
 7. A + B: the mech as one machine; hits and deaths that read.
 8. M5 hangar pilots and crew; C, D, E, F, S4, M4: jump-in presets and training wave; teammate markers; audio mix; nav mesh and post-processing; server-drawn extras;
    Dunes detail.
Quality bar for every item (memory "detail-and-quality-bar"): AAA. Look at your own renders / previews critically before calling an item
done; a thing that only passes its test but looks cheap is not done. Research first (repo docs, the creation guide) before building.

Leftovers (small, do first):
1. **The bottom HUD covers the pilot's own mech** (recording: vitals at 33-49 % and weapon boxes at 51-73 % of the width, the mech between
   and under them). Open a gap in the middle (tools/hud.py `vitals` / `wboxes` / `.VitPos`): vitals left of the mech, weapons right, about
   320 px clear at 1080 high, without going under CS2's chat box (x < 576 at 16:9) more than the vitals already do at 4:3. hud_check at
   1440 / 1920 / 2333 and at the recording's 2.16:1.
2. **CS2's own HUD shows through** (recording: the pawn's health number bottom centre-left, the rank emblem bottom centre, the top
   scoreboard with avatars): find what a map / script can switch off (search docs/reference/cs2-gotchas.md and the other projects' cfgs
   first: Hellmatch and Space Racer hide parts of it) and do it in 00_config.js CVARS.
3. **Balance not re-run** since the lofted missiles started hitting (they were 0 % under 5 000 u) and Mule / Lisa / 002-B were resized:
   `node test/balance.cjs`, `node test/frames.cjs 8 normal`; retune VM-6 / VM-12 / Swarm damage if they now dominate (docs/BALANCE.md).
4. `47_auras.js` and boosters were re-parented blind: if Workshop Tools is running, read the console for `WARNING: weapon mount drift`,
   `HUD text cut`, `maximum number of panel ids`, `cell bounds`.
5. Dunes map: skink52 allowed the map builds (~20:45). The live vmap was the objectives-patched one (identical to out/patched_objectives.vmap); out/patched_assets.vmap (all 264 models cached) was copied over it at 20:45 (backup backups/mg_ironframe_dunes.20261110_204544.pre_assets_cache.vmap) and the full no-vis build started under the watchdog (logs/build_dunes5_wd.log, ~35 min). Check it ended: the vpk newer than 20:45 and `python -I tools/cache_check.py <live vmap> --addon mg_ironframe_dunes --vpk --quiet` clean; if not, re-run `build_maps.ps1 mg_ironframe_dunes`.

Server-map interface (skink52, ~20:45: "we really want to lean in to server-map interface - the more stats and customisations etc that can
be built into server the better"; do this right after the leftovers, before the polish list):
- Read first (short): slime-mg-gm `docs/ironframe.md` (ops, payload, objective lines, DB, settings), `docs/stats.md` + `docs/map-dependencies.md`
  section 2 (the `mgstat` channel), `docs/map-integration.md` (what the server does per map type), this project's `docs/SERVER_CONTRACT.md`.
  What exists today. Map -> server: `echo mgstat <slot> <stat> [n]` (adds n to the player's stat in the mode; `best_*` keeps the maximum;
  `time <track> <ms>` keeps the lowest; `wins_*` / `*_wins` also counts the round as won), `echo ifr_srv <op ...>` (hello / want / buy / upg /
  save, rate-limited 10 per 10 s), `echo ifr_obj <copy> mode|pt|flag|end` (objective state for the plugin's beams). Server -> map:
  `RunScriptInput` `ifr_server` / `ifr_pilot` / `ifr_deny` with the payload in the `ifr_mail_NN` mailboxes (origin-encoded pages), and
  `mgstat_on`. Mech stats sent now: mech_xp, mech_credits, mech_assists, mech_captures, mech_damage, mech_pve_kills, mech_boss_kills,
  mech_wins, mech_rounds, best_streak.
- S1 **More stats, cheaply** (map side only + stat names in the plugin's lists): per round, batched at the round end so the echo volume
  stays low: per-weapon kills and damage (`mech_w_<key>_kills`, `_dmg`), per-frame rounds / kills / wins (`mech_f_<key>_*`), per-mode wins
  (`mech_<mode>_wins`), quick boosts, missiles fired / hit / dodged, staggers dealt, overdrives, crates, flag captures and returns, zone
  seconds, `best_damage_round`, `best_life_s`, accuracy as hits and shots counters. The core already keeps most of them per weapon
  (`wp.shots / hits / dmg`) and per mech (`m.sum`).
- S2 **Customisation that follows the pilot** (new `ifr_srv` ops + payload fields + DB columns; keep `data/contract_vectors.json` and
  `tests/run.py --only ironframe` in step): more loadout slots with names, paint and accent colours per loadout, a callsign / title and
  a badge earned from stats (shown on the kill line, the podium and the pilot plate), HUD and camera preferences (camera distance,
  hints off, reticle), a favourite frame for the hangar.
- S3 **Server -> map information**: a leaderboard payload (top pilots, the pilot's own rank among them) for the podium and the garage,
  daily-contract progress on the HUD, the lobby's average rank for the AI fill (it is rank-based already), server-set match rules through
  the `ifr_server` payload (mode rotation, round length, AI skill bounds, mutators, XP rate events) so an operator tunes it in SlimeMG.json.
- **S2 + S3 DONE 11 Nov 2026 ~00:10 (the server-map agent; not deployed, not committed: `out/handover_server.md` has the deploy steps).**
  Contract: docs/SERVER_CONTRACT.md sections 3-4 (ops, payload kinds, what a pilot costs) and the new 8-10; data `data/career.json`.
  Map: six loadout slots with names and accent colours, callsign / title / badge on the kill line, podium and a pilot strip, camera and hints
  preferences, favourite frame, daily contract on the HUD, the top pilots beside the podium and in the garage's new PILOT tab, operator rules
  (rotation, round length, AI skill bounds, XP rate) in the core; stand-alone keeps a session profile. HUD 480 ids of 800. Plugin
  (slime-mg-gm `IronFrame/Career.cs` + Store / IronFrame / Contract / Garage, Config.cs settings): the ops, the profile / owned / rules /
  leaderboard payloads, migration 3, career counters, `HideHud` (pawn `m_iHideHUD`, UNVERIFIED, off by default: leftover 2's plugin half).
  Tests: `node test/career.cjs` (new, 144), hud_strings / hud_ids / garage_upgrades / hud_garage_turn extended, mock flows; plugin
  `tests/run.py --only ironframe` 3/3 (101 vectors). Unverified until a real `ifr_pilot` round: every multi-page payload in game.
- S4 **Server-drawn extras** that do not cost HUD panel ids (centre HTML round summary, chat summaries, `!top`, `!stats <pilot>`): only on
  the mg server, so never the only place something essential is shown; stand-alone keeps working with local pilots.
- Every step: the contract change written in docs/SERVER_CONTRACT.md and slime-mg-gm docs/ironframe.md, plugin built with setup.py, its
  tests run, nothing deployed to the live server and nothing committed or pushed without skink52.

Maps (skink52, ~21:00: "the roads in sprawl that are elevated, the side barriers of the roads cross over in an odd fashion at the joins.
it's also an OK map but it lacks any real detail beyond the colours of lights in the buildings. far more small scale props etc can be
applied to it. You should find some ref images to use with the map generation tools you have to improve areas such as the central square
etc. Also, 3d skyboxes for both maps in line with their themes would be good."):
- M1 **Highway barriers** (tools/arenas/sprawl.py `highway()`, the parapets; tools/arenas/sprawl_ops.py): the E-W slab (y 2400) and the N-S
  slab (x -2400) cross, and each slab's side barriers run straight through the other road and through the ramp joins. Cut the barriers at
  the crossing and at the ramp heads, mitre or cap the ends, add proper junction corners, expansion joints and pillar heads; check with
  `tools/visualcheck.py` and a preview render before the rebuild.
- M2 **Detail pass from references.** (1) Collect references first: elevated expressways over a dense city (Tokyo Shuto, Osaka,
  Chongqing), neon megacity plazas and crossings at night in rain, flooded squares, Armored Core 6 / Titanfall city arenas for mech-scale
  staging. Save them under `C:\source1\ironframe_work\refs\sprawl\` with a `sources.txt` of URLs (never in git: no third-party images in
  the repo), and write down per area what the references have that the map lacks. The creation guide section 9 (docs/creation/guide.md,
  "reference judging") is the method. (2) The central square (point B, the flooded plaza with the dais) first: a readable centrepiece
  (monument or broadcast tower base), terraces and steps at mech and at human scale, tram / bus stops, kiosks, screens and billboards,
  planters, bollards, puddles and reflections, steam vents, cables overhead. (3) Then the avenues: human-scale props everywhere so the
  mechs read as 15 m machines (cars, buses, trucks, street lights, traffic signals, signs, vending machines, AC units, fire escapes,
  rooftop tanks and antennas, cranes, scaffolding, shutters, road markings and decals, litter, barriers), ground-floor shop fronts with
  depth, alley clutter. Tools: `create/gen_world.py` (scatter, fences, streets), `create/gen_kits.py` + `create/kits`, `create/placer.py`
  (footprints so nothing interpenetrates), `create/build_prop.py` / `build_all_props.py` / `blenderkit.py` (new props), `matkit`,
  `fxkit` (weather, lightning), mapops batches as sprawl_ops.py does. Budget: 64 players and a no-vis map, so instance the props, give
  them LODs and fade distances, keep collision off the small ones (mechs walk over anything under the step height anyway) and measure
  the frame time before and after. Every new model name goes through `tools/cache_check.py` only if the SCRIPT sets it; map props do not.
- M3 **3D skyboxes** (create/make_skybox.py, guide.md "3D skybox", mg_trenchwarfare as the worked example: a separate
  `<map>_3dskybox.vmap` at 1/16 with its own sky and `sky_camera`, and a `skybox_reference` in the main map). Sprawl: a ring of far
  megacity (lit tower silhouettes in layers, a few supertalls with aviation lights, far elevated roads, haze / rain, glow on the cloud
  base). Dunes: a dune sea out to mesas and a far ridge, derricks or a refinery with flares on the horizon, dust haze matching the map's
  fog. First check how a 3D skybox behaves with the stacked arena copies (Sprawl 3, Dunes 2: each copy has its own sky shell; the
  skybox draws behind everything, so it is one sky for all copies) and that each copy's shell uses a material that shows it.
- M5 **Hangar life** (skink52, ~23:00: "pilot models in the hangar - nothing super detailed but can use gmod pilot and worker models to add more life to the hangars"): pilots and ground crew standing at the bays (a pilot by each occupied bay, workers at consoles, on gantries, with carts and tool racks), from GMod pilot / worker models through the player-model pipeline (docs/creation/gmod-playermodels.md, create/playermodels; static posed props or a looping idle, human scale 72 u so the mechs read as machines). Sprawl's hangar is imported from Dunes (tools/arenas/import_region.py), so dress the Dunes hangar additively (a patch with a backup) and re-import. Credits and permissions as for the frames (docs/CREDITS.md).
- M4 **Dunes detail** the same way, but Dunes is hand-edited in Hammer: only additive patches through the patch tools
  (tools/patch_cache.py style, a fresh backup each time), never a regenerated map over skink52's work.

Toward AAA (largest visible gain first; each is its own item with tests and a deploy):
A. **The mech as one machine.** The waist join and the 75 deg leg limit are in; next: (1) torso twist shown in the model (the upper body
   yaws at the waist: check every frame's seam at 60 deg twist with tools/review_frames.py and close open seams with a waist collar ring
   in mdl2cs2); (2) feet that do not slide (stride / rate from models.json is there: verify at walk, strafe, back-pedal with the new leg
   modes; add turn-in-place steps when the legs are dragged by the 75 deg limit); (3) landing / quick-boost body language (lean is there;
   add a boost-start crouch and a landing knee bend through the existing hip curve).
B. **Hits that read.** Damage states (scorch skins exist: wire smoke and sparks by AP band), a proper death (the gib models exist:
   explosion, wreck that stays 8 s), bigger muzzle flashes and impact sparks at the new thin beams and tracers, a hit-direction flash on
   the vitals. STATUS to-do "Visible damage states".
C. **Jump-in clarity** (the HUD agent's ranked list in the ~18:20 block): three starter presets on the first garage screen, a
   RECOMMENDED tag and sort, a first-sortie training wave with spoken-style prompts.
D. **Friend or foe at a glance** in team modes: a HUD marker for teammates only (a few moving Labels within the 461-id budget, projected
   like the lock bracket), since prop markers cannot differ per viewer.
E. **Audio**: a mix pass (boost loop, footfalls by class, lock tones, low-AP alarm), nothing new to compile if only soundevent volumes move.
F. **Maps**: nav mesh so real CS2 bots can join (STATUS to-do), post-processing (bloom, grading) per arena, Sprawl street dressing.
Rules for the continuation (skink52, ~23:25: the PC is free overnight): CPU / GPU-heavy jobs that cost no tokens (map builds, model compiles, bakes, renders, balance sims, Blender) may run several at once in the background, each under the watchdog; keep TOKEN use low (no parallel agents; small, finished steps); every item ends with tests, a deploy to both
addons and a line here.

**10 Nov 2026, ~20:30 (main session): fourth playtest (the 18:44 build, played on Dunes ~19:50) fixed and deployed to BOTH addons; NOT played yet.**
skink52: "bast's back is invisible - check if this is a recurring issue", "none of my bars have anything in them, and weapons section is
empty", "the red marker that was showing when an enemy was in range is gone", "the diamonds above player heads are ALL white", "legs being
disconnected and rotating through 360 still looks weird", "gameplay is still far from AAA".
- **HUD dead = CS2's cap of 1024 panel ids per custom_hud_layout** (console: `The maximum number of panel ids has been reached, no more can be
  referenced.`; server.dll next to that string: `cmp dword ptr [rbp+0], 0x400`, a member of the layout object). The script referenced
  1 900-2 650 ids (every text character was a panel with an id), so whatever was referenced after the first 1024 never updated; the
  pre-evening HUD was over too (2 253), which very likely was behind "equipped weapons blank" and "messages cut off" in the earlier
  playtests. Rebuilt by the HUD agent (block below): dynamic text is one Label + dialog variable per slot, 461 ids in the layout, 454 the
  most a session can name, build and tests fail over 800 / 950. The mock engine counts them (`HUD panel ids referenced: N`, `panelids=950`).
  Read live console output with `python C:\source1\cs2mapping\autoport\vconsole.py tail --backlog` (Workshop Tools running): that is how this was found.
- **Bastion's back**: Tripo's auto-rig skinned the whole back / spine block to the pelvis, so it sat in the LEGS model: the upper model had
  an open back and the block turned with the legs. `create/mdl2cs2.py --torso-to-upper` (frames.json `torso_to_upper`: Bastion only): legs-group
  vertices not on a leg bone and above the pelvis / thigh joints go to the upper model (3 566 vertices). Recurring? No: `python -I
  tools/hole_check.py` (new; share of each side view whose nearest surface faces away) reads 5-12 % on all 24 frames, Bastion read 29-30 %
  and now 5-6 %; no other frame carries torso-height shells in its legs model.
- **Legs and torso**: (1) each prop turned about its own origin at the feet, so lean, aim pitch and flinch swung the upper body 20-40 u off
  the legs at hip height: the upper prop is now placed so its waist joint sits on the legs' (30_render.js `angRot`, `waistZ`; models.json
  `waist_z` = the pelvis bone, written by tools/frames.py, back-filled by build/waist_patch.py; `hip_z`, the lowest point of the upper
  model, was 40-90 u under the real waist on most frames); the lean is converted into the upper body's own frame. (2) the legs faced the
  travel direction whatever the torso did: now forward within 60 deg, back-pedal past 120, side-step (30 deg toward the travel side)
  between, hard limit 75 deg (`leg_fwd`, `leg_strafe`, `leg_twist`; test/playtest3.cjs section 5).
- **White diamonds**: the coloured models existed, but self-illum brightness 40 clips every channel (inferred from the values, not seen):
  iff_t / ct / red at 1.6 with saturated colours, objective marker materials at a twelfth of their old brightness (tools/fx.py,
  tools/objective_fx.py; the vmats patched in place).
- **Boost flames 15 000 u under the map** (console: `ifr_pfx_boost_013 ... outside of cell bounds @(... -16891)`): loop particles and aura
  props were parented at `prop.lastPos` (null since the pool clears it): both now use the engine transform (`propXform` / `propParentLocal`).
- **Deployed 20:24-20:28**: `sh tools/deploy_dunes.sh` and `SPRAWL_SCRIPT=1 SPRAWL_SKIP_BUILD=1 SPRAWL_NO_MAP=1 sh tools/arenas/rebuild_sprawl.sh`
  + `sh tools/compile_ui.sh mg_ironframe_sprawl`; cache_check clean on both, script + HUD compiled (1 541 resources, 0 failed), no map
  rebuild needed (no new model names). The live Dunes vmap is STILL unpatched (out/patched_assets.vmap, block of ~19:00 below): beams,
  objective markers and the bubble do not draw there until it is applied; Sprawl has everything.
- **Tests on the merged tree (20:20)**: mechanics 169, playtest_combat 29, playtest3 46, features 35, traits 83, auras 395, objectives 45,
  garage_upgrades 413, hud_strings, hud_driver 17, hud_garage_turn 7, hud_ids (454 of 461), weapon_mounts 23, beam_ladder, sim 64 x 90 all
  modes, parts_check, hole_check 0 over 16 %, weapon_fit 0 failures, tscheck both scripts, mock_flows both (332 / 333 ids), 64-player
  mock 120 s `OK: no errors` (344 ids, 1.6 ms/tick).
- **Look at first in game**: how the Labels render (font "Noto Serif" bold capitals, glow, vertical place in the boxes: previews only); the
  console free of the panel-id line; the waist join (the roll / pitch sign convention of entity angles is Source's AngleVectors, assumed);
  the camera now sways a little with the lean (it follows the upper prop); marker colours; boost flames at the boosters.
- **Dropped**: Tripo replacements for Krasnaya / Lisa / Supplice (skink52, ~19:15: the stripped AC models are good enough).

**10 Nov 2026, ~20:20: the HUD rebuilt under CS2's panel-id cap (HUD agent; offline-verified, script built for tests, NOT deployed, NOT seen in CS2).**
skink52, 19:50 on the 18:44 build: "none of my bars have anything in them, weapons section is empty", "the red marker ... is gone"; console:
`The maximum number of panel ids has been reached, no more can be referenced.` Details and the budget table: docs/HUD.md "The panel-id cap".
- **Cause:** a `custom_hud_layout` remembers at most 1024 panel ids the script has named and never frees them. The neon type was one glyph panel
  WITH AN ID per character: 5 846 ids in the layout, 2 644 named in a mock session. Whatever was shown first (the garage) used the table up.
- **Fix:** every dynamic text is one `<Label id text="{s:v}">` set with `SetDialogVariableStringForPlayer` (1 id, 1 engine call per changed
  text). Static captions keep the neon glyph pictures (no ids). Ids in the layout, before -> now: garage 3 437 -> 200, common 652 -> 117, fight
  540 -> 91, slates 941 -> 35, cards 275 -> 17, root 1 -> 1; **total 5 846 -> 461**. Named in a session: both mock flows 2 644 -> 332 / 333,
  64 players 120 s -> 344, the exhaustive walk -> 454 (everything but the 7 click-only Buttons). One layout entity is enough: the HUD is NOT
  split over several entities (no map change, nothing for 90_main.js to rebind); that lever stays in reserve.
- **So it cannot come back:** `tools/hud.py` registers every id per screen, prints `panel ids the script can reference: 461 of budget 800`,
  asserts the xml holds no unregistered id, and fails the build over 800; `test/hud_ids.cjs` (new) walks every screen and counts what the
  engine is handed (fails over the budget, hard over 950, and when an id is never referenced); `panelids=950` in `tools/mock_flows.sh` and
  `tools/build_all.sh`; the driver counts too (`HUD on: 461 panel ids`, a console warning past 950).
- **What changed on screen:** dynamic text is Noto Serif Bold capitals (a font CS2 ships; within 2 % of the glyph widths at the same cap height)
  with a glow in the text colour, instead of baked Cinzel glyphs; captions are still the Cinzel glyph art. Player names keep non-ASCII letters.
  Boxes widened a little: weapon boxes 244 px (vitals cluster 916 px, shifted 68 px right), buff badges 296, pilot / streak plates 356, loadout
  card 496. Wording: garage rows show the upgrade level on the small right line (`MK III` / `R ARM  +3`), equipped rows put it first when it
  fits; tab LOADOUT -> SLOTS; `CT SCORES`; `DROP 12 S`; podium `KILLS 9 | ASSISTS 3`. Everything of the evening block below still works
  (message queue and ranks, weapon state rows, lock states and the bracket on the target, plate, streak meter, overdrive block, cards, hints,
  garage facing + turn buttons, frames by class). HUD cost fell: full fight refresh 394 -> 135 writes, garage first draw 1 026 -> 140.
- **Tests** (script built ~20:15 from the tree as it was): `node test/hud_ids.cjs` ok (454 of 461); `hud_driver` 17/17; `hud_strings` ok (224
  slots, 22 313 states and messages, 77 call sites, measured with the Label font's real advance widths x 1.03); `hud_garage_turn` 7/7;
  garage_upgrades 413; features 35; traits 83; auras 395; mechanics 169; objectives 45; playtest_combat 29; `sh tools/mock_flows.sh` both
  "OK: no errors" with panelids=950 (its text helper now reads Labels: `api.hudVar`); 64-player mock 120 s with panelids=950 "OK: no errors",
  1.73 ms / tick; tscheck OK; hud_check 11 states at 1440 / 1920 / 2333 with `--label-font`: clean at 1920 and 2333, at 1440 the vitals
  cluster and reticle box under CS2's chat while typing (as before).
- **Files:** tools/hud.py, tools/hud_font.py (+ tools/hud_label_metrics.json, generated), src/cs2/50_hud.js, 60_garage.js, 45_features.js (two
  hints shortened), test/hud_ids.cjs (new), test/hud_driver.cjs, test/mock_flows.mjs (text helper), tools/mock_flows.sh, tools/build_all.sh,
  docs/HUD.md. Shared (repo root, uncommitted): create/hud_check.py (`--label-font`, Labels drawn with a glow), create/test/mock_point_script.mjs
  (`api.hudVar`, `api.hudIds`, dialog variables stored), create/test/README.md, create/panorama.py (warning on the pixel-text helpers),
  docs/reference/cs2-gotchas.md, docs/creation/hud.md, docs/reference/cs_script-notes.md, CHANGELOG.md. `create/libsync.py check` already
  showed monsoon-cs2's copies of hud_check / panorama / the mock differing before this; nothing pushed.
- **Deploy (main session), script and panorama together** (the script bakes hud.json; an old script on this layout throws on the missing glyph
  cells, a new script on the old layout shows no text): 1. only if hud.py / parts.json changed since 20:15: `python -I tools/hud.py out/addon
  ironframe mg_ironframe_dunes`. 2. `node ../../create/build/build.mjs build.json` and `node ../../create/build/build.mjs out/sprawl/build.json`.
  3. Dunes: `sh tools/deploy_dunes.sh` (it deploys and compiles script + HUD), or `IF_ARENA=dunes sh tools/deploy.sh` then
  `sh tools/compile_ui.sh mg_ironframe_dunes`; Sprawl: `SPRAWL_SCRIPT=1 SPRAWL_SKIP_BUILD=1 SPRAWL_NO_MAP=1 sh tools/arenas/rebuild_sprawl.sh`
  (or deploy_sprawl.sh) then `sh tools/compile_ui.sh mg_ironframe_sprawl`. The layout xml is a third of its size (112 KB), the css ~15 % smaller; no
  new picture, model, particle, sound or map entity. Check the compile log for `ironframe.xml` / `.css` "compiled" (a css that fails to
  compile leaves the old HUD in place silently).
- **Unverified in CS2, most important first:** (1) that the Labels render at all the way the previews assume: `"Noto Serif"` resolving (CS2's
  fonts.conf loads notoserif*; if not, the fallback Stratum2 is narrower, so nothing is cut but the look is sans), bold, upper-case, the glow
  (`text-shadow: 0px 0px 6px 2.0 #rrggbbc0`), `white-space: nowrap`; (2) the vertical place of the capitals in their boxes (a few px either
  way if Panorama's line box differs from ascent + descent); (3) that 461 ids really is under whatever the table counts (it should say nothing
  in the console now: look for "maximum number of panel ids"); (4) that the table is per layout entity and whether a round restart frees it
  (not relied on); (5) per-player dialog variables surviving `ResetForPlayer` the way the driver assumes (it resends every text after a
  reset); (6) everything listed as unverified in the evening block below.

**10 Nov 2026, ~19:00 (main session): third playtest (Sprawl) fixed and deployed to BOTH addons; Sprawl map rebuilt; NOT played yet.**
skink52's list: shoulder weapons floating, rockets hitting the roof / no idea how to target, messages cut off, tiny bumps stop the mech,
ERROR models at the feet, invisible models, jets too strong, baked-in weapons on the frames, M1 + M2 showdowns always lost, garage facing +
rotate buttons, nothing easy to jump into, wide lasers, no frags / overdrive / streak explanation, camera hard to shoot up / down, Tripo
models for Krasnaya / Lisa / Supplice. Four agents (blocks below: assets, frames, hud, tripo) + the main session (core, camera).
- **Deployed 18:44-18:58:** Dunes = script + HUD + every model / particle compiled (`sh tools/deploy_dunes.sh`, cache_check clean against
  `out/patched_assets.vmap`); the LIVE DUNES VMAP IS UNTOUCHED and still lacks the cache props for the 65 objective markers, the 33 beam
  rungs and the bubble (apply the patch below before playing Dunes, or beams / markers will not draw). Sprawl = full rebuild (one command,
  below): 264 models and 25 particle pools precached, 0 gaps, vpk 18:56, script + HUD 18:57.
- **Main-session changes** (details and numbers: docs/AC_FEEL.md "Fourth pass"; tests `node test/playtest3.cjs` 39):
  jets (climb cap 650 u/s, 3.8 s a tank, slow air regen, 4.9 s ground refill); step height 80-101 u with the body sphere above it and an
  eased step (`m.stepOff`); lofted missiles turn over low and hit (they went to the ceiling and hit nothing under ~5 000 u), no loft under a
  roof, no phantom heightfield ramps for rounds / missiles / sight lines near structures, a launcher always fires (unguided without a
  lock); AI fill skill (starts easy stand-alone, follows the humans' results, bots re-tier at respawn), starter loadout 1 = two rifles, the
  four Tripo frames in the bot loadouts; camera up 215 / 250 / 290 and no orbit past 10 deg of up-look; beam width from the core
  (`beam.w`: cannon 1.5, charged 1.4). slime-mg-gm: the plugin's catalog copy refreshed, `tests/run.py --only ironframe` 3/3 (starter L1
  expectation updated); not deployed to the live server, not committed.
- **Commands.** Sprawl, everything: `SPRAWL_SCRIPT=1 python C:\source1\cs2port\autoport\watchdog.py --label "sprawl rebuild" --expect 660
  --heartbeat 60 --stall 600 --max 2400 --log logs/sprawl_rebuild_watch.log -- sh tools/arenas/rebuild_sprawl.sh` (~11 min; needs
  `node ../../create/build/build.mjs out/sprawl/build.json` first; CS2 must not have the map loaded). Dunes, everything but the map:
  `sh tools/deploy_dunes.sh` (~5 min, after `node ../../create/build/build.mjs build.json`). Script + HUD only: `sh tools/compile_ui.sh <addon>`.
- **Dunes map patch (skink52, Hammer closed; only while the live vmap is still the 12:38 51 125 997-byte one, else re-run
  `sh tools/patch_objectives.sh <fresh backup>` then `python -I tools/patch_cache.py out/patched_objectives.vmap out/patched_assets.vmap out/addon`):**
  `Copy-Item "C:\source1\cs2mapping\projects\ironframe-cs2\out\patched_assets.vmap" "C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\content\csgo_addons\mg_ironframe_dunes\maps\mg_ironframe_dunes.vmap"`
  then the full no-vis build. (`out/patched_assets.vmap` replaces `out/patched_objectives.vmap` as the file to apply.)
- **Tests on the merged tree (18:40):** mechanics 169, playtest_combat 29, playtest3 39, features 35, traits 83, auras 395, objectives 45,
  garage_upgrades 413, hud_strings, hud_driver 16, hud_garage_turn 7, weapon_mounts 23, beam_ladder 16 550, sim 64 x 120 all modes,
  parts_check, tscheck (both scripts), mock_flows both runs, 64-player mock 120 s "OK: no errors" (2.3 ms/tick avg; it was 1.6: the HUD
  writes roughly doubled).
- **Open / to decide.** (1) Tripo: DROPPED by skink52 at ~19:15 (stripped AC models are good enough; do not generate or top up). Was: nothing generated, the CLI's API wallet has 0 credits: `tripo.cmd topup` then
  `python -I C:\source1\ironframe_work\scripts\tripo_gen.py krasnaya|lisa|supplice`, or the studio with the prompts in docs/TRIPO_PROMPTS.md
  "Humanoid replacements" (block below). (2) A whole mech or weapon invisible is only explained by the pool-budget bug the frames agent
  fixed (`rigFill`): if it still happens, note the frame and the moment. (3) Aretha's own weapons can be stripped with one `strip` line.
  (4) Onboarding: 11 ranked suggestions in the hud block (top: starter presets on the first garage screen, a RECOMMENDED tag, a
  training wave). (5) Balance sims not re-run for the stronger lofted missiles or the resized Mule / Lisa / 002-B bodies
  (`node test/balance.cjs`, `node test/frames.cjs 8 normal`). (6) `47_auras.js auraClaim` still parents with `parent.lastPos`.
- **Look at first in game:** the camera when looking up / down (maths only); the lock bracket sitting on the target (assumes CS2's
  default FOV: `CONFIG.HUD_FOCAL`); garage rotate buttons' clicks; shoulder units seated; beams thin with a glow; no ERROR models on
  Sprawl; a console line `WARNING: weapon mount drift` or `HUD text cut in` if either still happens.

**10 Nov 2026, ~18:10 ("assets" agent): ERROR / invisible models on Sprawl, beam rework (offline-verified; models compiled in both addons; script NOT deployed; NOT played).**
**State at hand-over (18:04): the Sprawl rebuild was still running** (started 17:58:33 under the watchdog with `SPRAWL_NO_UI=1`, at the copies /
hangar step of build_sprawl.sh after waiting 4 min on the frames agent's models.json.lock; no cache patch, deploy, asset check or map compile
yet). Its result is NOT known: read the last line of `logs/sprawl_rebuild_watch.out` (`exit 0` = rebuilt and clean, `exit 1` = a step or
cache_check failed, `exit 3` = staged, CS2 held the vpk) and `logs/sprawl_rebuild_watch.log`; if there is no `exit` line the job died with
my run: re-run the one command below. Until it has ended with exit 0 the live Sprawl content vmap is still the 16:44 one and the vpk the
16:53 one (both without the aura / objective / beam cache props). Also NOT done: the non-forced compile in the Dunes addon
(`cache_check.py out/patched_assets.vmap --addon mg_ironframe_dunes --sync --compile`; held back because the frames agent was compiling
frames there), so on Dunes only the 33 new beam / bubble models are known fresh and the full Dunes check has not been run.

skink52: "there are model error orange things at the feet of some models", "some models are invisible" (Sprawl), "the lasers from the charge
weapons have a large width too - can be reworked to look nicer".

- **Cause of the ERROR models (evidence: the real vmaps, not `_gen/entities.json`).** `tools/arenas/build_sprawl.sh` copied only models.json,
  sounds.json and fx_particles.json into `out/sprawl/addon/_gen`, not auras.json or objectives.json, and never ran patch_cache. So the Sprawl map
  that was played (content vmap of 16:44, vpk of 16:53) loaded 110 models: every frame, weapon and fx model, but **none of the 65 aura models, none of
  the 65 objective markers and none of the 76 aura particle pool entities** (`ifr_pfx_aura_*`). The Sprawl script is built with
  `AURAS = out/addon/_gen/auras.json`, so 47_auras.js SetModels those 65 unloaded models onto props parented to each mech's legs / upper prop, whose
  origin is the mech's feet: an ERROR model at the feet of every mech that wears an aura and is near a human (tier 2: the 40 nearest within 4 000 u).
  Dunes' live map has all 65 aura models, which is why it only showed on Sprawl. The vpk agrees: it names `tf_ogre_upper` and `fx/beam/beam` but
  no aura or `obj_` model. 90_main.js's `Instance.Precache` list has frames / weapons / fx only, so it did not cover them either.
- **"Some models are invisible": what the same gap explains, and what I could not pin down.** Explained: the aura parts themselves (wings, fields,
  ribbons: CS2 either draws ERROR or nothing for an unloaded model, cs2-gotchas says nothing, the playtest says ERROR; both were seen), the aura
  flare particles (no pool entities), and every objective marker (45_features.js found no `ifr_cache_obj_*` prop and drew its stock fallbacks: the
  landing ring for zone rings, IFF diamonds for letters and flags, and **the laser bar scaled x18 pointing up as the zone column**, a second source of
  "wide lasers"). Also found: the pulse-shield bubble was never drawn as a bubble on any map (30_render.js asks for `FX_MODELS.bubble`, tools/fx.py
  only made `shield`, so the lock ring was drawn instead). Not explained offline: a whole mech (frame or weapon) being invisible. Every frame /
  weapon / fx model is in Sprawl's map and compiled with all its materials and textures (cache_check walks the compiled files' reference lists:
  1 807 resources, 0 missing in either addon), the pool is far from its 900 cap, and the gib-hidden upper body is dropped before the 6 s respawn.
  If mechs are still invisible after this rebuild, I need which frame and when (at spawn, after a death, far away).
- **Stale `*_c` (the `cp -rn` copy from Dunes).** The frames, weapons and fx models in the Sprawl game addon were NOT the stale copies any more: CS2's
  tools had recompiled them at the 16:04 and 16:54-16:57 map loads (which is the minutes of console silence in SPRAWL_NOTES finding 12). The compiler
  takes a `*_c` copied from another addon for out of date: all 130 aura / objective models copied from Dunes were recompiled by the first non-forced
  compile in the Sprawl addon (186 compiled, 103 skipped, 0 failed, 191 s), the 46 frame and 32 weapon models were skipped as up to date.
  So copying compiled files between addons buys nothing; `cp -rn` on top would have kept an old copy for good on a server (no tools, no recompile).
- **Fix, tooling (all in `tools/`):**
  - `cache_check.py <vmap>` (new): lists every model and particle the script can use (models.json frames / weapons / fx, auras.json states,
    objectives.json, the null model, any `models/...vmdl` literal in src/, the particle pools of fx_particles.json + auras.json by the names 40_fx.js
    looks up) and reports PRECACHE (no prop in the vmap), CACHE NAME (objective prop not named `ifr_cache_<key>`), POOL (pool entity or prop template
    missing), COMPILED (a `*_c` or anything under it missing from the game addon; stock paths are looked up in CS2's pak01_dir.vpk), STALE (content
    differs from out/addon, or `*_c` older than its content), VPK (`--vpk`: map built before the vmap). Exit 1 on any gap. `--sync` copies only
    changed models / materials / particles into the addon content, `--compile` runs resourcecompiler without -f over all of it in the addon
    (recompiles what is out of date, skips the rest, then dates the outputs), `--map-only` for a vmap that is not deployed.
  - `patch_cache.py`: takes its model list from cache_check (one definition), adds every missing pool entity, uses a 64 u grid (585 spots; the
    generator's 96 u grid holds 232 and the script now has 264 models), optional `--gen`.
  - `arenas/build_sprawl.sh`: copies auras.json + objectives.json too, waits out a models.json.lock, uses the shared null model (vmap.py had
    written a second `models/ifr/null.vmdl` for Sprawl that overwrote the shared one at each deploy), then patch_cache and
    `cache_check --map-only`: a gap stops the build.
  - `arenas/deploy_sprawl.sh`: models / materials / particles through `cache_check --sync-only` (only changed files; `cp -r` re-dated ~3 900 files
    per deploy); `SPRAWL_NO_UI=1` leaves panorama / sounds alone. No `*_c` is copied from Dunes any more.
  - `arenas/rebuild_sprawl.sh` (new): **the one command** (below).
- **Beams.** Cause as the main session found, plus the length: `SetModelScale(l / 180)` on a 100 u tube drew a bar `l / 180` times as wide
  (84 u at 2 600 u, 200 u at 6 000 u) that stopped at 56 % of the way to the hit. Now `tools/fx.py` builds a ladder: `models.json#fx`
  `beam_c_<L>` (cyan) / `beam_r_<L>` (red), 16 lengths 64 .. 11 585 u in x1.41 steps (`--beams-only` builds just these + the bubble, 13 s).
  Each is a self-lit near-white core (r 2.6, csgo_vertexlitgeneric F_SELF_ILLUM, the tracer recipe) inside six additive shells (r 3.9-13,
  csgo_unlitgeneric F_BLEND_MODE 4, the aura recipe): swells out of the muzzle, thins slowly, a point at the hit. 30_render.js `beamPick` takes the
  rung nearest length / width on a log scale and scales it to the exact length, so the width stays within x0.84-1.19 of the wanted one at any
  range (core ~5 u, glow ~26 u wide) and the beam ends on the hit. Width tiers come from the same ladder by picking a shorter or longer rung:
  `o.w` 1..1.5 for a charged shot (capped), x0.7 for the last 0.045 s so it thins out instead of popping. Colour follows the core's `red` flag as
  before (laser rifle, laser cannon, drones red; rail, sniper cyan). The old `beam` / `beam_red` stay for the objective column fallback and for a
  build without the ladder. Also new: `fx.bubble` (the translucent shield sphere at r 150), so the pulse-shield bubble draws as a bubble.
  fx.py now writes models.json under `models.json.lock`.
- **For the main session (not my files):**
  1. Charge width needs one field from the core, `src/core/40_combat.js`: `function IF_beam(game, from, to, red, slot, w)` + `best.w = w || 1;`,
     and at line ~526 `IF_beam(game, mz, to, w.en_shot > 0 || !!w.cannon, m.slot, w.cannon ? 1.5 : mult > 1 ? 1.4 : 1);` (80_game.js beam objects:
     add `w: 1`). Until then every beam is drawn at width 1. The requested colours ("laser cyan, rail / charge red") are the opposite of the core's
     `red` (= energy weapons); swap it there if wanted, the models are named by colour.
  2. `src/cs2/90_main.js` init: the `Instance.Precache` list should also take the aura states (`AURAS.frames[*].parts[*].states[*]`) and the
     objective models, and the returned handle should be kept in a module variable (it is dropped today). A second line of defence only.
  3. Suggested guard in 30_render.js `propModel` (pool section, not mine): build a Set of `GetModelName()` over `Instance.FindEntitiesByClass(
     'prop_dynamic')` at init and skip + `warnOnce` a SetModel to anything outside it. An unloaded model then draws nothing and names itself in
     the log instead of standing in the map as ERROR.
  4. Dunes: the live vmap (12:38, 51 125 997 bytes) is untouched. `out/patched_assets.vmap` = `out/patched_objectives.vmap` + cache props for all
     264 models (the beam ladder, bubble; map side clean). It replaces patched_objectives.vmap as the file to copy over the live map (Hammer
     closed, only if the live map is still the 12:38 one), then the full no-vis build:
     `Copy-Item "C:\source1\cs2mapping\projects\ironframe-cs2\out\patched_assets.vmap" "C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\content\csgo_addons\mg_ironframe_dunes\maps\mg_ironframe_dunes.vmap"`
     Re-make it after any model list change: `python -I tools/patch_cache.py out/patched_objectives.vmap out/patched_assets.vmap out/addon` then
     `python -I tools/cache_check.py out/patched_assets.vmap --addon mg_ironframe_dunes --sync --compile --quiet` (exit 0 = clean).
  5. Until Dunes is rebuilt from the patched map, the new script draws NO beams' ladder models there unless they are loaded: the live Dunes map
     lacks the 32 rungs and the bubble (and the 65 objective markers, as before). Build and deploy the script together with the maps.
- **The one command (cache patch + check + Sprawl rebuild), from projects/ironframe-cs2, ~10 min, in the background:**
  `python C:\source1\cs2port\autoport\watchdog.py --label "sprawl rebuild" --expect 600 --heartbeat 60 --stall 600 --max 2400 --log logs/sprawl_rebuild_watch.log -- sh tools/arenas/rebuild_sprawl.sh`
  (exit 0 clean; 1 a step failed or cache_check found gaps, before the map compile; 3 all staged but CS2 holds the .vpk: the script prints the
  map compile line to run once the map is unloaded. `SPRAWL_SCRIPT=1` also copies the Sprawl script, `SPRAWL_NO_UI=1` skips panorama / sounds,
  `SPRAWL_SKIP_BUILD=1` keeps the generated vmap.)
- **Tests:** `node test/beam_ladder.cjs` 16 550 checks (the shipped beamPick cut out of 30_render.js: exact length and width within x1.203 for
  every length 20-13 800 u and every width tier, both colours, model files present); mock run of a laser-loadout build (12 players, 150 s,
  `models=out/addon` strict): 1 047 beam draws over 27 rungs, scales 0.59-1.19, the old bar never set, "OK: no errors"; plain build mock (3 and
  16 players) OK; tscheck: no errors in the beam code (6 errors at the time in the HUD text code, another agent's work in progress).
  `python -I tools/cache_check.py <vmap>` on the live maps before the fix: Sprawl PRECACHE 130 (65 aura + 65 objective) + POOL 19; Dunes PRECACHE
  65 (objective, the pending patch). Previews: `preview/fx/beam_before_after.png`, `preview/fx/beam_profile.png` (`python -I tools/review_beams.py`).
- **Unverified in CS2:** that the ERROR models are gone (the cause is certain, the engine's reaction to an unloaded model is inferred); the beam's
  look (the additive glow's brightness against the day sky on Dunes, the self-lit core's bloom, whether a 5 u core reads at 6 000 u; the software
  preview shows shape, width and length only); the thin tail (a model swap two ticks before the beam goes); the bubble sphere's look and its size
  with the camera inside (r 350 around a 520 u camera boom: outside); the objective markers and aura flares on Sprawl, now that they load.

**10 Nov 2026, ~18:35: shoulder units seated, frames stripped of their own weapons, robust weapon parenting ("frames" agent; offline-verified;
frames compiled and copied into both addons; script built for tests, NOT deployed; NOT played).**
skink52 (evening playtest, mg_ironframe_sprawl): "Shoulder weapons now occasionally float significantly above the character" and "can we also
remove the weapons that are a part of mech models?".

- **Cause of the floating: the fit itself (tools/weapon_fit.py), not the engine and not stale models.** The 16:40 fit dropped each shoulder unit
  onto the MAXIMUM of a top-down height map of EVERY pose under its whole footprint, so one aerial, V-fin, sabre hilt, back unit or raised arm
  anywhere under a 100-160 u pod held the unit up while the test (penetration <= 4 u) still passed. "Occasionally" = it depends on frame x unit.
  Measured with the new seat metric (how far a unit hovers over a 100 u^2 patch of the idle frame under it), old mounts on the meshes of then:
  **533 of 672 shoulder pairs (79 %) hovered over 5 u, 142 over 20 u, median 8.3 u, worst 93 u on a player frame (Loki dualmsl; Unicorn median
  22, Ogre 24, White Glint 16; Aretha 240). Now: 0 of 672 over 5 u, worst +3.1 u, median -6.0 u (resting / sunk in); overlap with the idle
  frame <= 7.5 u, with any other pose <= 11.2 u.** On the 14 frames whose mesh did not change the mounts came down by a median 10.7 u (220 of
  420 by more than 10 u, up to 150 u). Per frame: the table at the end. It was visible in the 16:10 review sheets (Unicorn / Stryder units
  over the head); nobody looked at the shoulder rows, and the test only measured penetration.
  - Ruled out, stale Sprawl models (hypothesis c): the weapon / frame sources in out/addon and in both content addons were byte-identical, and
    both game addons' weapon vmdl_c (Dunes 15:00-15:40, Sprawl 16:56) were compiled after the re-pivoted SMDs (14:54-15:39), same sizes.
  - Runtime (hypothesis b): no fault found by reading (Teleport and Move both set the server origin at once; the offset was computed from the
    position the script had just asked for). Made robust anyway, see below; `rigMountCheck` now PROVES it in game (a console line if the
    engine ever has a weapon off its mount).
- **New shoulder fit** (weapon_fit.py `fit_shoulder`, `rest_z`, `Fields.seat`): the unit comes down from above until it overlaps the IDLE frame
  by 5 u (thin aerials / fins read under that and are passed through), centred near the shoulder joint, each unit on its own side of the centre
  plane, never below the joint; the spot is the cheapest by seat gap (a unit caught on a spike pays) + rise above the shoulder top + distance
  from the joint + overlap in the moving poses beyond 10 u. Wide units overhang narrow shoulders outward. Test (`python -I tools/weapon_fit.py`,
  ~3-6 min): a shoulder unit fails when its seat gap is over 5 u (floating), its idle overlap over 7.5 u (merged), or its overlap in any other
  pose over 15 u; arm weapons as before (4 u, hand on the weapon). **Result: 24 frames x 32 weapons, 0 failures** (fit 203 s, test 169 s).
  `--fit --only` now also rewrites docs/WEAPON_FIT.md from the report; `--lock` takes out/addon/_gen/models.json.lock for the write; the write
  is atomic. models.json#mounts `v` 2 (same layout: [right x, y, z, left x, y, z] per frame and weapon).
- **Frames stripped of their own weapons** (`data/frames.json frames.<key>.strip` -> `create/mdl2cs2.py --bodygroup part=<empty>` /
  new `--drop-parts` / `--drop-bones` / `--drop-boxes`; `tools/frames.py` passes them and deletes material files nothing references any more).
  Every frame in frames.json was looked at (body parts, bones, previews):
  | frame | removed | kept on purpose |
  |---|---|---|
  | ac4a_whiteglint | both hand rifles, both back missile units (4 body groups) | the wing boosters (core mesh) |
  | ac4a_hari (Krasnaya) | both hand rifles | stabilisers |
  | ac4a_oldking (Lisa) | both hand weapons, both back units | stabilisers |
  | ac4_berlioz (Supplice) | both hand weapons, the right back cannon, both shoulder units | stabilisers |
  | ac4_002b (PvE) | the two shoulder shields (body part `shields`) | the rifle arm and the blade arm: they ARE the forearms (no hands under them) |
  | ac4_normal (PvE) | the two back missile racks (bones l_bwep / r_bwep) | the gun arms: they are the arms |
  | fear3_mule | the roof gatling with belt and ammo box (bone gun), the two side mortars | the empty turret brackets |
  | gundam_rx78, gundam_unicorn | the two beam sabres on the backpack (body group saber = empty) | forearm sabre hatches (flush, in the main mesh) |
  | tripo_scout | the gun barrel on the left forearm (its own piece of the one-skin mesh, `--drop-boxes`) | forearm housing + feed hose, the blade under it and the sensor / missile head: fused with the body |
  | ac4_aretha (boss) | nothing, as briefed | gatling + plasma cannon are body groups WITH an empty choice (`gatling=1`, `plasma_cannon=1`): a clean body with a right hand and a claw arm is left (previewed; the cannon is what makes it 700 u tall, so the body would be rescaled) and the 10 `unfit` left-hand pairs would probably go. One `strip` entry in frames.json if skink52 wants it. |
  | noblesse, tf_atlas / stryder / ogre, tf2_legion / ronin, gundam_barbatos, me3_atlas, me2_loki, ac3_moa, tripo_kestrel / warden / bastion | nothing to remove | no weapon parts (Barbatos' are off by default; ME3 Atlas' gun arm and MOA's gun arms are the arms; Kestrel's back fin is fused) |
  No holes: every removal is a whole body group / bone / mesh piece (previews `preview/frames/<key>.png`). Hands stay (AC fists, Gundam hands).
  **Side effects to know (models.json frames[k] of the 10 changed):** the frame is scaled to its class height WITHOUT the removed parts
  (body x1.24 Mule, x1.18 Lisa, x1.13 002-B, x1.08 Supplice, x1.04 Normal, x1.03 RX-78; others x1.00); the feet origin is no longer dragged
  off by the hanging rifles (waist pivot White Glint x -60 -> -10, Krasnaya -45 -> +9, Lisa -70 -> -46, Supplice -51 -> +11 u: these four
  stood 50-60 u off their game position); `hip_z` is the real waist now (White Glint 50 -> 149, Krasnaya 48 -> 107, Lisa 36 -> 145,
  Supplice 51 -> 130): `renderHipZ` = max(hip_z, 45 % of the height), so the camera / reticle origin rises 37 u on Lisa, 25 u on the Mule,
  20 u on White Glint, 14 u on 002-B, 7 u on the Normal, 3 u on the RX-78 (unchanged on Krasnaya, Supplice, Unicorn, Scout); hit spheres, hardpoints, boosters, strides and hip curves were regenerated. Balance sims not re-run.
  Backups of the 10 frames as they were: `C:\source1\ironframe_work\strip_backup\<key>\{models,materials}` (remove the `strip` entry and
  reconvert, or copy back, to undo).
- **Script (src/cs2/30_render.js; built + tested, NOT deployed):**
  - `propParentLocal(p, parent, local)`: the child is Teleported to parent transform x mount using the transform the ENGINE reports
    (GetAbsOrigin / GetAbsAngles, full pitch / yaw / roll), then SetParent: right wherever the parent is at that moment (parked, mid-drop,
    pitched, a pooled prop placed by a Move). `propParent(p, parent, worldPos, ang)` (the garage preview's call, unchanged signature) converts to it.
  - `releaseProp`: a prop that rode a parent forgets its stale lastPos (its next placement is a Teleport); `renderDropMech` does the same for
    the body halves (a re-used body no longer slides in from its last place with its weapons).
  - `rigFill`: a rig the pool could not complete at claim time (SPAWN_BUDGET 24 props a tick; a mech takes up to 6) is completed on later
    ticks. Before, a prop the pool could not give was never asked for again: a mech without its upper body or a weapon for its whole life
    (round starts with many mechs).
  - `rigMountCheck`: once per rig, after it moved 48 u, each weapon's engine position is compared with its mount; over 8 u off =
    `WARNING: weapon mount drift: frame .. slot .. model .. was N u off its mount (parented again)` once per frame / slot, and it is parented
    again. It turns itself off where children do not report a followed origin (the mock). **Look for that line after the next playtest.**
  - `IFR_ARMED_SWAY = false`: a mech holding a hand weapon keeps the idle upper clip while it walks (the `*_sway` arm swing took the palms
    13-66 u off the rigid weapon props; now 5-22 u, idle + fire recoil only: WEAPON_FIT.md hands column). Unarmed mechs still swing. No
    upper clip moves the torso, so the halves stay joined. Set it to true to get the swing back. This is the cheap answer to the open
    "hands leave the grips while walking" item; the amplitudes themselves (create/mech_anim.py `sway(gt, Aw, Ae, ..)`, lines ~622-626: walk
    14 / 9 deg, run 19 / 13) were NOT changed: that needs every animated frame reconverted and recompiled (~1 h).
- **Tests:** `python -I tools/weapon_fit.py` 0 failures (24 x 32); `node test/weapon_mounts.cjs` (new, 23 checks: parenting against a fake
  engine that models SetParent, a parked / pitched parent, the garage call, the drift check, rigFill over several ticks); tscheck OK;
  64-player mock 120 s OK (avg 2.4 ms/tick, no warnings); `sh tools/mock_flows.sh` both runs OK; mechanics 169, features 35, traits 83,
  auras 395, playtest_combat 29, playtest3 39, hud_driver 16 groups, frames.cjs all pass.
- **Sheets:** `preview/weapons/<frame>.png` (labels now carry the shoulder seat gap), new `preview/weapons/shoulders_<frame>.png` (EVERY
  shoulder unit on the frame, front + side) and `shoulders_contact.png`, `contact.png`; `preview/frames/<key>.png` of the 10 stripped frames;
  `preview/review/` + docs/FRAME_REVIEW.md regenerated (tools/review_frames.py); docs/WEAPON_FIT.md, MODELS.md, CREDITS.md regenerated.
  `tools/review_mounts.py --mounts <models.json> --report <fit.json> --out <dir>` renders another mounts set (before / after).
- **Compiled and copied:** the 10 changed frames (20 vmdl + materials) were compiled in mg_ironframe_dunes by frames.py (all OK) and copied
  to mg_ironframe_sprawl: sources into both content addons, compiled files into both game addons (checked: 0 files differ, every vmdl_c
  newer than its source). Weapon props did not change (not recompiled). Model names are unchanged: no map rebuild for this.
- **Files changed:** create/mdl2cs2.py (`--drop-parts`, `--drop-bones`, `--drop-boxes`, `--list-pieces`), create/README.md,
  docs/reference/cs_script-notes.md (parenting note), tools/frames.py (strip, prune), tools/weapon_fit.py, tools/review_mounts.py,
  data/frames.json (10 `strip` entries, 002-B unfit text), src/cs2/30_render.js, test/weapon_mounts.cjs (new), docs/TESTING.md (weapons line),
  generated docs and sheets. Not changed: tools/weapon_props.py, tools/compile_frames.py, create/mech_anim.py.
- **For the main session:** (1) build + deploy the script: 30_render.js AND models.json changed (frames[k] of 10 frames, mounts of all 24);
  (2) add `node test/weapon_mounts.cjs` to the suite list; (3) the camera / reticle origin moved up on Lisa (+37 u), the Mule (+25), White Glint (+20) and 002-B (+14) with
  the corrected hip_z: check `renderHipZ` users if that matters; balance sims were not re-run for the bigger Mule / Lisa / 002-B bodies;
  (4) src/cs2/47_auras.js `auraClaim` parents with `parent.lastPos` (the script's idea of the parent's place, the pattern replaced here):
  `propParentLocal(p, parent, [0, 0, 0])` would make it as robust; (5) tools/build_all.sh's weapon-mount comment still says "shoulder units
  clear"; (6) decide on Aretha (see the table).
- **Unverified in CS2:** everything visual (the seats in idle / walk / boost / air on real models, the stripped frames' look and their bigger
  bodies against cover and doorways, the steady arms while walking); that GetAbsOrigin / GetAbsAngles of a prop report what Teleport / Move
  just set (if not, propParentLocal is still self-consistent: it parents against what the engine reports); the mount check's reading of a
  parented child's GetAbsOrigin. The aim pitch still turns the upper body about the feet (up to ~125 u at the shoulders against the legs at
  steep aim): the weapons ride with it, the waist parts; not changed here.
- Still open: Tripo frames carry fused gear the piece filter cannot separate (Scout's forearm blade + head pod, Kestrel's back fin);
  arm weapons still sit 4-40 u off the palm where the hip armour is in the way (AC frames median ~18 u: unchanged by the strip, the hands hang
  beside the skirt); shoulder props are one size for every class (125 u orbit-drone racks overhang light frames).

| frame | before: seat gap max / median (u), units hovering > 5 u | now: seat gap max / median | idle overlap max | any-pose overlap max |
|---|---|---|---|---|
| ac3_moa | 30 / 13, 28 of 28 | +1.2 / -10.0 | 7.5 | 7.5 |
| me3_atlas | 23 / 6, 19 of 28 | +2.2 / -5.3 | 5.0 | 9.7 |
| fear3_mule | 166 / 7, 17 of 28 | -1.9 / -5.7 | 5.0 | 5.0 |
| me2_loki | 93 / 18, 28 of 28 | +1.3 / -2.0 | 5.0 | 7.5 |
| ac4a_noblesse | 68 / 4, 14 of 28 | +1.3 / -4.9 | 4.6 | 7.5 |
| ac4a_whiteglint | 43 / 16, 28 of 28 | +1.3 / -5.6 | 5.0 | 11.2 |
| ac4a_hari | 21 / 9, 23 of 28 | +1.3 / -8.1 | 5.0 | 7.5 |
| tf_atlas | 43 / 13, 27 of 28 | +1.3 / -11.2 | 5.0 | 8.7 |
| tf_stryder | 18 / 8, 22 of 28 | -5.0 / -10.0 | 5.0 | 8.8 |
| tf_ogre | 51 / 24, 25 of 28 | +1.2 / -13.0 | 5.0 | 7.5 |
| gundam_rx78 | 43 / 13, 24 of 28 | +1.3 / -4.1 | 5.0 | 7.5 |
| gundam_barbatos | 36 / 13, 26 of 28 | -2.4 / -7.4 | 5.0 | 9.7 |
| gundam_unicorn | 73 / 22, 28 of 28 | -3.1 / -5.6 | 5.0 | 7.5 |
| ac4a_oldking | 28 / 6, 21 of 28 | +1.2 / -5.9 | 6.2 | 7.5 |
| ac4_berlioz | 18 / 8, 25 of 28 | -1.4 / -8.9 | 6.2 | 8.7 |
| ac4_002b | 38 / 6, 15 of 28 | -1.5 / -4.0 | 5.0 | 7.5 |
| ac4_aretha | 240 / 14, 28 of 28 | -2.3 / -8.6 | 5.0 | 11.2 |
| ac4_normal | 13 / 1, 6 of 28 | +3.1 / -4.4 | 5.0 | 5.0 |
| tf2_legion | 23 / 4, 14 of 28 | -1.5 / -6.5 | 5.0 | 7.5 |
| tf2_ronin | 60 / 13, 27 of 28 | +1.2 / -8.5 | 5.0 | 8.8 |
| tripo_scout | 46 / 8, 20 of 28 | +1.2 / -4.7 | 5.0 | 7.5 |
| tripo_warden | 28 / 13, 28 of 28 | -2.0 / -13.2 | 7.5 | 7.5 |
| tripo_bastion | 23 / 6, 21 of 28 | +1.3 / -4.2 | 5.0 | 9.7 |
| tripo_kestrel | 30 / 6, 19 of 28 | +1.2 / -5.7 | 5.0 | 7.5 |

"Before" = the 16:03 models.json mounts measured on the meshes of then (the stripped frames from their backups); a negative seat gap means the
patch is in contact or a fin / overhang of the frame stands above it (the overlap columns say how deep the unit really sits in the frame).

**10 Nov 2026, ~18:20: evening playtest, everything the player reads (HUD agent; offline-verified, script built for tests, NOT deployed, NOT played).**
skink52: "many in game messages get cut off"; "i don't know how to target [rockets] ... no indication in game of what to do"; "no real indication of
current frags, or what overdrive / killstreaks do, or how to use any of them"; "not much is easy to understand or jump straight into"; "garage ...
face the mech towards player ... 2 buttons below their feet". Details and the API: docs/HUD.md "Evening playtest, 10 Nov 2026".

- **Messages (A).** Three causes. (1) Time: every `reply()` replaced the line at once, so a prompt vanished when a bot took a crate or a trait
  procced. Now each message stays >= 1.6 s, later ones queue, and messages are ranked: ambient (other pilots' news, trait procs: only on a free
  line), normal, important (gold; cuts in, the interrupted one returns). `reply()` ranks by the core event being handled (`replyCtx`), so no
  caller changed. (2) Space: the line is 3 rows of 18 px capitals, 640 px (was 2 x 14 px, 600 px); it wraps by pixels and cells, breaks an
  over-long word, and pages what is left: it cannot drop text. (3) Real cuts the wider test found: weapon boxes `100%  1200` (gatling),
  `CHARGE 100%` (lasers), `120 / 600` (flamethrower) in a 112 px box; the garage's one-row answer line (`Welcome back: pick a loadout and
  SORTIE`: now two rows); `ALL UNLOCKED` in the stand-alone credits cell (offline was never tested: `UNLOCKED`); generator `CAPACITY .. REGEN ..
  OUTPUT ..`; `SHOULDER / PROJECTILE  RANK 5  3 500 CR`; the sniper cannon's `IMP`; podium `TOTAL +XP +CR` at six figures; player names over
  ~12 wide letters in the lock box, kill pop, death slate, podium and spectator bar (now shortened with `..`). A cut in game logs
  `HUD text cut in <slot>` once per slot.
- **Rockets (B)**, for the core's final rules (no enemy in the cone: unguided at the reticle; held on a building lock: waits, launches guided;
  released early: unguided). The lock bracket sits ON the target (projected from the pilot's camera, 20 px grid, eased): ACQUIRING (thin amber) ->
  SOFT LOCK -> LOCKED (red, flashing), with name, lock progress bar, range, AP; the lock tones are the core's. Each weapon box has a state row:
  `NO LOCK: UNGUIDED` / `HOLD: LOCK 60 %` / `KEEP HOLDING 60 %` (wp.mslWait) / `LOCKED: FIRE` / `OUT OF RANGE` / `READY IN 5 S` / `NO AMMO`;
  multi-lock `HOLD TO LOCK` / `NO TARGET IN RING` / `KEEP HOLDING: 2` / `3 LOCKED: RELEASE` plus a diamond on each locked mech; also reload
  time, heat, charge, shield. One-time hints: launcher pressed with nothing in the ring, holding on a building lock, multi-lock, soft / hard lock.
- **Frags / streak / overdrive (C).** Pilot plate under the radar (YOUR TEAM vs ENEMY, kills / deaths / assists); the mode box lights and
  underlines your team's score. Streak meter: 8 pips, marks at 3 / 5 / 8, the next reward and what it gives. Overdrive block: gauge, %, and a
  line (`DEAL OR TAKE DAMAGE TO FILL` / `READY: HOLD SPACE + R + E`, pulsing gold / `CHARGING: BLAST IN 0.8 S`: the old code compared `odPhase`
  with `'charge'` while the core sets 1, so the charge state never showed). Buff badges name the effect and the time left. Every reward says what
  it is, what it does and how to use it (gold line): streak 3 / 5 / 8, all five crate kinds, overdrive ready.
- **Jump-in help (D).** Controls card (first 2 spawns, first 3 death screens, `!help` / `!keys`, after holding Tab); loadout card at every spawn
  (M1 / M2 / R / E, icon, name, role; the frame, its trait and the key for it); hints once per pilot and session (start, the mode's goal, EN stall,
  stagger, locks, death -> garage, first capture zone, crate, overheat, shield); intro and death slates reworded; `AI EASY / NORMAL / HARD` at
  the end of the objective line when it fits. Calmer: ambient news no longer interrupts, the streak badge went (the meter replaces it), cards
  time out, the kill pop joined the message column.
- **Garage (E).** The mech faces the camera on opening and when the frame changes; no idle spin; E / R held turn it in any column (A / D in the
  tabs); Buttons `<  E`, `FRONT`, `R  >` under the feet (45 degrees a click, eased; continuous while the mouse button is reported
  down); the camera pitch keeps the feet at y ~672 for any frame height / bay depth; weapons still mount through `weaponMountPos`. FRAMES are
  listed by class with the four Tripo frames first in each (they were rows 16-19).
- **Tests** (all on the script built at 18:16 from the tree as it was then, other agents' edits of that moment included): `node test/hud_strings.cjs` ok (224 slots; 22 313 drawn states and
  messages; 77 message call sites found by scanning src/, each as a worst-case upper bound with 24-letter names; 92 line messages each on one
  page; 200 garage answers; 1 398 real buy / upgrade questions, server and stand-alone; a 400-message fuzz of the line); `node
  test/hud_driver.cjs` 16/16 (5 new: queue / ranks / pages, hints and cards, lock states and projection, overdrive / streak / plate);
  `node test/hud_garage_turn.cjs` 7/7 (new); garage_upgrades 413; features 35; traits 83; auras 395; mechanics 169; playtest_combat 29;
  objectives 45; `sh tools/mock_flows.sh` both runs "OK: no errors" (a mid-way run flagged "props Teleported 3+ ticks in a row" for the garage
  preview's weapon props while the scripted pilot scrolled the list a row a tick: the preview now rebuilds at most every 0.12 s, flag gone);
  22-player mock with the HUD, 90 s: "OK: no errors", no class outside the css, 0.56 ms / tick; tscheck OK; hud_check 11 states at 1440 /
  1920 / 2333: clean at 1920 and 2333, at 1440 only the vitals cluster and the reticle box under CS2's chat box while someone types (as before).
- **Previews:** `preview/hud/hud_*.png` (fight, fight_cq / ctf / kh, lock, death, spec, intro, podium, garage, garage_turn at 1920 / 1440 / 2333); the previous
  set in `preview/hud/before_evening_playtest/`. Source backups: `backups/hud_evening/`.
- **Files changed:** tools/hud.py, tools/hud_images.py, src/cs2/50_hud.js, 60_garage.js, 45_features.js, 80_chat.js, test/hud_strings.cjs
  (rewritten), test/hud_driver.cjs, test/hud_garage_turn.cjs (new), docs/HUD.md. No core file, no 90_main.js, no 20_players.js touched.
  Generated: out/addon/_gen/hud.json, out/addon/panorama/{layout,styles,images}/custom_game/ (3 new pictures: ifr/lockbox_acq.png, ml.png,
  ml_done.png), build/hud_states.json, out/addon/maps/scripts/ironframe.js (test build).
- **Deploy (main session).** 1. `python -I tools/hud.py out/addon ironframe mg_ironframe_dunes` (only if tools/hud.py or parts.json changed
  since 18:13; ~40 s). 2. Build both scripts AFTER hud.json: `node ../../create/build/build.mjs build.json` and `node
  ../../create/build/build.mjs out/sprawl/build.json` (the script bakes hud.json: an old script on the new layout throws on unknown panels, a
  new script on the old layout shows no new elements). 3. Copy `out/addon/panorama/` (layout xml, styles css, images/custom_game/ifr/ with the
  3 new pngs) to the addon's content folder and compile the panorama (xml + css + the new images), then the script: `sh tools/deploy.sh` /
  `SPRAWL_SCRIPT=1 sh tools/arenas/deploy_sprawl.sh` do the copying. No map change, no new model, no new particle, no new sound.
- **Unverified in CS2** (first things to look at): the bracket's place on the target (assumes the custom camera uses CS2's default FOV, 90
  degrees across 4:3 = 720 px per unit of tangent at 1080 high: `CONFIG.HUD_FOCAL` overrides; if the bracket drifts off targets toward the
  screen edge, that number is wrong) and the feet-above-buttons camera pitch (same number); `transition` on the translate classes; the three new
  Buttons' hit-testing (a first click logs `HUD click ifr_grl`); whether a held mouse button is reported during input capture (else: 45
  degrees per click only) and whether SHOW_SCORES reads in a mech (else: no Tab trigger for the controls card); the gold `stHi` tint and the
  overdrive pulse animation; glyph-row heights in the taller weapon boxes; the lit team-score plates.
- **Fields read from other owners' code** (defensively; none needed that does not exist): `m.lock {target, stage, t}`, `m.lockSoft / lockHard`,
  `wp.cd / reloadT / salvo / mslWait / mlock[{slot, p, done}] / mlDone / mlHold`, `w.lock / multilock / range`, `m.input.camPos / camDir`,
  `m.fkills`, `m.sum {kills, deaths, assists, pveKills, bossKills}`, `m.odPhase / odT / overdrive`, `m.aceT / radarT / boostDmgT / shieldT /
  artyReady`, `m.enStalled`, `m.frame {name, trait, trait_name}`, `IF_FEAT.streak`, `IF_Ai.fillSkill(g)`, `m.fill`. Wanted, not blocking:
  (a) 90_main.js `case 'capture'` uses `(ARENA.points)[ev.point]` for "took point X" (the chips and strip already show it; the line is now
  ambient); (b) an event when a launcher fires unguided (`fire` with `guided: false`) would let the HUD pop "UNGUIDED" on the box instead of
  inferring it.
- **For the "assets" agent:** nothing. No new model, particle or sound (the lock marks and brackets are HUD pictures).

### Easier to jump into: further suggestions for skink52, ranked (cost = my estimate; none of these is built)
| # | Suggestion | Why | Rough cost |
|---|---|---|---|
| 1 | **Three starter presets on the first garage screen** (ASSAULT: rifle + rifle + missiles + decoy; BRAWLER: shotgun + blade + grenade cannon + repair; SNIPER: rail + rifle + dual missiles + pulse shield), each a big card with one line; the full armory one key behind them. | The armory opens on 66 rows and 9 tabs; a new pilot needs a choice of three, not a catalogue. | 0.5 day (garage tab + 3 loadout strings; hud.py card row) |
| 2 | **A "RECOMMENDED" tag and a default sort** in the armory: owned and recommended first, locked last; one recommended item per slot for the frame's class. | Removes the reading; pairs with #1. | 2-3 h (parts.json flag + sort) |
| 3 | **First-sortie training wave**: the first life of a session drops the pilot 15 s early against 3 passive AI mechs at 1 500 u with step prompts (boost here, lock, fire R, quick boost). Skippable with F. | Teaches by doing; the hints added today only tell. | 1-1.5 days (core: passive AI flag, script: step machine; no map change) |
| 4 | **Fewer systems on by default** for the first rounds of a server: supply crates and streak artillery off until round 2 (`cfg.feat`), traits explained one at a time. | "Heaps of stuff going on": crates, streaks, traits, overdrive, objectives all start at once. | 1-2 h (config + a round counter) |
| 5 | **Lead indicator / hit confirmation numbers**: a small pip where rounds will land on a moving locked target, and damage numbers on the bracket. | Makes "am I hitting?" obvious; AC has both. | 0.5 day (reuses the projected bracket grid: one more panel pair) |
| 6 | **Objective arrow**: a chevron at the screen edge toward the nearest point / flag / hill with its distance. | The world markers exist but are far away on Sprawl; new pilots wander. | 3-4 h (the threat-chevron ring already does 8 directions) |
| 7 | **Kill / death recap on the death slate**: what killed you, from how far, your damage to them, "try: quick boost sideways against missiles". | Turns deaths into lessons; one tip per weapon family. | 0.5 day (core already tracks dmgBy; texts per family) |
| 8 | **A training arena** (`!train`: a quiet arena copy with static and strafing dummies, infinite ammo, no score). | The honest place to learn locks, missiles, overdrive without being shot. | 1.5-2 days (uses an arena copy; needs a mode flag in the core and bot script) |
| 9 | **Key rebinding note / `!keys alt`**: an alternative layout with overdrive on a single key (e.g. hold F + Space) and shoulders on Q / E via binds in a cfg. | Space + R + E is a three-finger chord; R and E mean reload / use to every CS player. | 2-3 h for a cfg + docs; a real rebind UI is not possible in a map script |
| 10 | **Voice-style callouts** (short synthesised barks: "lock", "missile", "overdrive ready", "stagger"). | Players in a fight do not read; AC talks to them. | 0.5-1 day (tools/sounds.py synth + 8 events; the assets agent's area) |
| 11 | **Simplify the fight HUD further behind a setting** (`!hud min`): hide the buff column, mode sub-line and stagger bar until they matter. | Some will find even this too busy. | 3-4 h (root classes in hud.py, one chat command) |

**10 Nov 2026, ~17:50 (agent "tripo"): Krasnaya / Lisa / Supplice as humanoid Tripo models: BLOCKED before the first generation; nothing generated, converted, compiled or changed in parts.json / frames.json.**

- Blocker: the Tripo CLI is signed in (`tripo.cmd doctor` ok, region ov) but its API wallet has **0 credits** (`tripo.cmd balance` ->
  `{"balance":0,"frozen":0}`; Tripo keeps studio credits and API credits apart, as docs/reference/external-tools.md already says).
  The one real attempt (Krasnaya, 17:36, under the watchdog) was refused by the CLI's balance pre-check: `Insufficient credits`,
  api_code 2010, exit 4. Nothing was submitted (`tripo.cmd history` / `usage` empty). **Credits spent: 0. Task ids: none.**
  No Chrome extension was connected, so the studio could not be reached from this session either (and it was not the route asked for).
- Needs skink52, one of:
  1. generate the three in the studio as he did the first four (~55 studio credits each; settings and full prompts in
     docs/TRIPO_PROMPTS.md "Humanoid replacements"), saving `C:\source1\ironframe_work\tripo\tripo_krasnaya.glb`, `tripo_lisa.glb`,
     `tripo_supplice.glb` (rigged GLB, auto-rig biped); or
  2. `tripo.cmd topup` (API credits), then `python -I C:\source1\ironframe_work\scripts\tripo_gen.py krasnaya` (then `lisa`,
     `supplice`; `--try 2` for a retry) under the watchdog, ~8 min each: H3.1, PBR, detailed texture, face limit 12000 / 12000 / 15000,
     rig-check + Mixamo-spec rig, rigged GLB copied to the same three paths; task ids and credits in
     `C:\source1\ironframe_work\tripo\cli\<name>_tryN\result.json`. List price 30 credits per generation plus the rig step (not estimated
     by the CLI). All three plans pass `--dry-run`.
  Also worth a yes / no from him: his words were "could just be our tripo models", which may have meant re-using the four existing
  Tripo frames rather than three new generations.
- Written: docs/TRIPO_PROMPTS.md (three prompts: Krasnaya the duelist, Lisa the jumper, Supplice the interceptor; common "empty hands,
  clean back" line; shared style line unchanged; the blocker; an empty task / credit table), `C:\source1\ironframe_work\scripts\`
  `tripo_prompts.json`, `tripo_gen.py` (one generation), `with_lock.py` (runs a command holding `models.json.lock`).
  Not touched: data/parts.json, data/frames.json, models.json, state.json, CREDITS.md, MODELS.md, FRAME_REVIEW.md, either addon.

**The four older Tripo frames (tripo_scout / Sandviper, tripo_kestrel, tripo_warden, tripo_bastion): compiled, cached and selectable; no bot ever uses them.**
- Compiled: `_legs.vmdl_c` + `_upper.vmdl_c` and their materials are in both game addons (mg_ironframe_dunes 10 Nov 03:39-03:41,
  mg_ironframe_sprawl 16:56). Dunes' content `.vmdl` files are from 16:44 (the frames agent's run), newer than its compiled ones.
- Cached: both content vmaps hold cache props for all eight vmdls, and both built map vpks (Dunes 13:18, Sprawl 16:53) reference them.
- In the script: the deployed `ironframe.vjs_c` of both addons (Dunes 12:52, the build skink52 played) lists ids 21-24 as player
  frames with the `tripo_*` model paths.
- Selectable: garage FRAMES tab; offline every part is owned, so no rank or credit gate. They are rows 16-19 of 19 in an 8-row
  list, so two scrolls down.
- Why he has not seen them: `ai_loadouts` in parts.json uses frames 1, 2, 4, 5, 6, 7, 8, 9, 12 only, so no AI mech wears a Tripo
  model, and the starter loadouts are 4, 1, 8. Fix (main session, parts.json): add loadouts with frames 21-24 to
  `ai_loadouts.normal / hard`, or move them up the list.
- Not verified: how they look in game (nobody has reported seeing one in CS2).

**To finish once the three GLBs exist** (resume this agent, or run in this order; LOCK = `python -I C:\source1\ironframe_work\scripts\with_lock.py out/addon/_gen/models.json.lock --`; long steps under the watchdog):
1. Look at each GLB first (`python -I ../../create/glbrig.py <glb>`: Mixamo bones, one skin, triangle count; hands empty, back clean).
2. data/frames.json: add `tripo_krasnaya` (light), `tripo_lisa` (light), `tripo_supplice` (medium), copied from `tripo_kestrel` /
   `tripo_warden` (`source: tripo`, `glb` path, `retint: 0.4`, `legs: "(?i)thigh|calf|foot|toe|pelvis"`, `decimate` 12000 / 15000 only if
   over); mark `ac4a_hari`, `ac4a_oldking`, `ac4_berlioz` with a `retired` note (files stay on disk).
3. `LOCK python -I tools/frames.py --all --merge --only tripo_krasnaya,tripo_lisa,tripo_supplice` (~4 min; converts through
   glbrig + mdl2cs2 with clips and hard-surface materials, compiles in mg_ironframe_dunes, writes models.json / MODELS.md / CREDITS.md).
   frames.py maps models to parts through parts.json `model`, so switch the three `model` lines (step 7) before or straight after.
4. `python -I tools/stretch_check.py tripo_krasnaya,tripo_lisa,tripo_supplice`; `python -I tools/review_frames.py --only ...`;
   `python -I tools/review_anim.py --only ...` (~7 min); look at preview/review/<key>.png and the GIFs (feet on the floor, knees /
   ankles, tint mask); regenerate (one retry each in the budget) or fix before going on.
5. `python -I tools/compile_frames.py --only tripo_krasnaya,tripo_lisa,tripo_supplice` if step 3 ran with `--no-compile` or materials changed.
6. `LOCK python -I tools/weapon_fit.py --fit --only tripo_krasnaya,tripo_lisa,tripo_supplice`, then the test without `--fit`
   (0 failures); `python -I tools/review_mounts.py --only ...`; `python -I tools/auras.py --only krasnaya,lisa,supplice` (ribbons,
   wings, plumes refit to the new meshes; same aura model paths).
7. data/parts.json, three lines only (Edit, re-read first): id 1 `"model": "ac4a_hari"` -> `"tripo_krasnaya"`, id 3 `"ac4a_oldking"` ->
   `"tripo_lisa"`, id 6 `"ac4_berlioz"` -> `"tripo_supplice"`. The `desc` texts still name the AC machines (03-AALIYAH, Old King,
   Berlioz): main session's wording. Lisa's `legs: "reverse"` is a stat profile only and can stay with humanoid legs.
8. Copy `models/ifr/frames/tripo_{krasnaya,lisa,supplice}` and `materials/ifr/frames/<same>` (content sources and compiled `_c`
   files) into content_addons and game_addons of mg_ironframe_dunes and mg_ironframe_sprawl; the rebuilt aura models likewise.
9. Tests: `node test/frames.cjs`, `node test/traits.cjs`, `node test/auras.cjs`, `python -I tools/parts_check.py`. Docs: CREDITS.md,
   MODELS.md, FRAME_REVIEW.md, the table in TRIPO_PROMPTS.md.

**Model paths the maps will have to precache once they exist** (none exist yet; patch_cache picks them up from models.json):
`models/ifr/frames/tripo_krasnaya/tripo_krasnaya_legs.vmdl`, `.../tripo_krasnaya_upper.vmdl`,
`models/ifr/frames/tripo_lisa/tripo_lisa_legs.vmdl`, `.../tripo_lisa_upper.vmdl`,
`models/ifr/frames/tripo_supplice/tripo_supplice_legs.vmdl`, `.../tripo_supplice_upper.vmdl`.
The aura models keep their paths (`models/ifr/aura/krasnaya|lisa|supplice/...`).

Tests: not run (no data, code or model changed by this agent).

**10 Nov 2026, ~17:00 (main session): all four playtest-fix agents merged, script + panorama + weapon / objective models deployed.** Blocks below
are the agents' own. Main-session changes: 22 humans per arena copy (`IFR_SPLIT_AT`, `ai.floor`; DESIGN.md §2/§8); the RESTART_WAIT
fallback first sends `mp_restartgame 1` (clears CS2's win panel), and only RESTART_WAIT later starts the round itself; the garage
preview mounts weapons with `weaponMountPos` (models.json#mounts); `tools/arenas/objectives.py map_points` takes copy 0 from
`ifr_arena_1` (test/objectives_copies.py). All suites, the 64-player mock and both mock flows pass (64p mock avg 4.1 ms/tick).
Next: copy `out/patched_objectives.vmap` over the content vmap (Hammer closed; live vmap still the 12:38 51 125 997-byte one),
then the full no-vis build (`$NoVis` has mg_ironframe_dunes), then playtest (docs/TESTING.md).

**10 Nov 2026, ~16:40: weapons in the hands, shoulder units clear of the body (offline-verified; weapon vmdls compiled; script NOT built or
deployed; NOT played).** skink52: "line each weapon up better with each model's hands ... shoulder-mounted weapons ... merge into the bodies".
- Cause: the props' origin was their bounds centre, placed on `hardpoints` that are bounds guesses on 10 frames (AC hands 50-70 u off the
  real wrists). Now `tools/weapon_props.py` GRIPS re-pivots every prop to its grip (arm) / bottom-centre mount base (shoulder); all 32 vmdls
  recompiled (`--repivot` also recompiles stale ones). `tools/weapon_fit.py --fit` places each weapon per frame from the posed mesh: the grip
  at the palm (hand-bone vertices, or the source rig's hand centroid carried by arm_lo on the AC rigs), nudged out / down / forward only where
  the body is in the way. Shoulder units are dropped onto a height map of every pose next to the shoulder joint, each on its own side of the
  centre plane. The result goes to `models.json#mounts`, which 30_render.js `weaponMountPos()` reads (falling back to hardpoints).
- Test: `python -I tools/weapon_fit.py` (~4 min) measures every frame x weapon in idle / walk / run / aim (fire clips, upper +-10 deg
  pitch and +-30 deg yaw against the legs) by voxel depth (2.5 u). It fails over 4 u or when the hand is off the weapon; result 0 failures.
  build_all.sh runs `--fit` after the weapon props. Table: docs/WEAPON_FIT.md. Sheets: `preview/weapons/<frame>.png`, `contact.png`
  (`tools/review_mounts.py`). Worst penetration before -> after: 12-54 u -> <= 3.8 u on every frame.
- Can't fit (data/frames.json `mount.unfit`, PvE frames): Aretha's left hand is inside its laser-cannon arm, so 10 arm weapons sit 72-124 u
  off it; 002-B's shield sits ~83 u off the hands. Normal, Mule and MOA have no arms: their arm weapons use the hard-points, clear of the body.
- Open: the weapons are rigid on the upper body, but the walk / run sway clips move the palms 13-66 u (Bastion 66, Legion 49, Ogre 46), so
  hands leave the grips while walking (idle, hover and boost hold). Fixes: calmer arm sway in mech_anim, or bone attachments
  (`SetParentAttachment`, unverified). The AC frames still carry their own hand guns and back units in the mesh, so held weapons sit beside
  them (strip them in frames.py). The garage preview (60_garage.js ~351) still uses hardpoints: it needs `weaponMountPos(frameKey, weaponKey,
  i, hp[keys[i]])`. The aim pitch rotates the upper body about the feet, which the check models as the game does today.

**10 Nov 2026, ~15:50: objective modes in the world (CTF / Conquest / KOTH) (mock-tested; script built, NOT deployed; map patch in out/, NOT built; NOT played).**
skink52: "not much indication of what mode is playing; CTF / domination don't work well; zones and capture progress need to be obvious".
- Mode bugs fixed: KOTH scored for the owner while nobody (or only the enemy) stood on the hill (now: owner present and not contested;
  `points[].scoring`); KOTH capture events named the wrong point ("took point A" on B: `capture.point` is the arena index now, plus `id`);
  **every `!vote` was wiped** by the core reset at CS2's round restart before pickMode read it (80_game.js reset keeps votes), so no vote ever
  chose CTF / KOTH; Conquest bled both sides for every held point (16-bot rounds ended in 2.5 min; now majority rule, `match.bleed`);
  CTF flags defaulted to the first drop point (11 200 u apart in the corners; now map stands, else the drop centroid a quarter in);
  a carrier shot down high up returned the flag at once (void check compared ground with the carrier's height); bots barely stood on
  objectives (9-13 %; `objPull` from 85_objectives.js in 50_ai.js: now 27-38 %); objective rings were the generic lock ring, upright, a
  quarter of the zone size, in the 24-ring effects pool (now drawn by the adapter). Additive state for the HUD: `points[].nT/nCT/scoring/idx`,
  `match.hillLeft/hillNext/bleed`, `flags[].returnMax/carrierTeam`, `hill` soon event.
- World markers (`src/cs2/45_features.js` objTick, models `tools/objective_fx.py` -> models/ifr/fx/obj, 65 compiled): owner-colour ground ring
  scaled to the radius, progress arc (20 steps) in the capturer's colour, a 3000 u light column whose visible height is the progress, white
  flash while contested, the zone letter turning 1300 u up; KOTH's next hill shows its letter and blinks 15 s before the move; CTF flags
  (team colour, on the stand / dropped spinning / over the carrier) with a column (blinking over a carrier) and the home ring. <= 4 props per
  zone, 3 per flag; falls back to the stock fx models when the map lacks the cache props.
- Plugin beams (slime-mg-gm `IronFrame/ZoneDraw.cs`, `Objectives.cs`; built with setup.py, not committed): the map's markers give the
  positions, `echo ifr_obj <copy> mode|pt|flag|end` the live state (SERVER_CONTRACT.md section 7); `RunScriptInput ifr_objdraw` turns the
  script's rings / arcs / columns off. Marker convention for every map (Sprawl too): docs/ARENAS.md "Objective markers"
  (`ifr_point_<ID>`, optional `ifr_point_<ID>_edge` = radius, `ifr_flag_t/ct`); 15_arenas.js reads them (map set replaces the baked one).
- Map: `sh tools/patch_objectives.sh <backup.vmap>` (patch_cache with the marker models, then `tools/arenas/objectives.py`: per zone a lit
  ring inlay + kerb, dais, letter mast with a four-sided lit sign and lamp, `ifr_point_<ID>_edge`; per team a flag pad with lit inlays, pylons,
  team lamps, `ifr_flag_t` (-4200, 0) / `ifr_flag_ct` (4200, 0); both arena copies). Output `out/patched_objectives.vmap` from backup
  `backups/mg_ironframe_dunes.20261110_145102.pre_objectives.vmap` (= the live map of 12:38). To apply (Hammer closed; only if the live
  map is still 51 125 997 bytes from 12:38, else re-run the patch on a fresh backup):
  `Copy-Item "C:\source1\cs2mapping\projects\ironframe-cs2\out\patched_objectives.vmap" "C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\content\csgo_addons\mg_ironframe_dunes\maps\mg_ironframe_dunes.vmap"`
  then the full no-vis build. Previews: `preview/objectives/` (top_down, zone_B_ground, zone_B_contested, zone_A_held, flag_T_stand,
  from_T_base, sheet; `python -I tools/objectives_preview.py`).
- Tests: `node test/objectives.cjs` 45/45 (KOTH scoring / rotation, capture index, votes over reset, Conquest presence and bleed, CTF take /
  capture / drop / return / void, AI pull, a 16-bot soak per mode on the test arena and Dunes with the runtime nav survey);
  `sh tools/mock_objectives.sh` ok (cq / kh / ctf voted in, props drawn, ifr_obj lines); features 35, traits 83, auras 395, mechanics 169,
  sim 64 x 300 all ok; mock_flows passes its checks (its "props Teleported" PROBLEM is pre-existing: same 8 with the markers switched off).
- Unverified in CS2: the marker models' look and scale (self-lit brightness, the sunk column hidden by the terrain), the dressing's fit
  on the real terrain (heights from dunes.py, not the Hammer-edited mesh), the stand pad edge for walking mechs, the plugin's beams and the
  ifr_objdraw hand-over, Dunes KOTH still favours CT in bot soaks (T 0.17 vs CT 0.41 on the hill).

**10 Nov 2026, ~15:45: second playtest, HUD / garage / round flow (mock-tested; built, NOT deployed, NOT played).** HUD agent; layout details in docs/HUD.md.
- "ROUND WON / ROUND LOST" stuck over the HUD: CS2's own win panel (`WinPanel_RoundWon` in csgo_english), not ours. Cause: `mp_timelimit 0` with
  `mp_maxrounds 0` ends the MATCH after round 1 (cs2-gotchas), so CS2 never starts round 2 and the panel stays while the script's RESTART_WAIT fallback
  runs its own rounds. Fix: `00_config.js` sends `mp_maxrounds 999` (CVARS_ALWAYS and CVARS_ONCE). Still open for the 90_main.js owner: the RESTART_WAIT
  fallback should send `mp_restartgame 1` (a real CS2 restart clears a game-over state a server cfg could still cause) instead of starting a round on top of it.
- Garage at 4:3 (the likely cause of "equipped weapons blank", "tracks don't respond" and "!garage text cut off": at 1440 wide the right-pinned ITEM
  INFORMATION covered EQUIPPED WEAPONS, the 880 px centre block lay over the tracks, the message line ran under the chat). New aspect-safe layout,
  checked at 1440 / 1920 / 2333: left = top bar, ARMORY (8 rows), EQUIPPED WEAPONS (M1 / M2 / R / E, icon, name +level, DMG, rate or cooldown, mag/ammo
  or EN); centre (400 px) = bay caption, two-row confirm bar, legend, FRAME stats; right (430 px, from y 196) = UPGRADE TRACKS, ITEM INFORMATION.
  The garage draws each section in its own try/catch (equipped first), keeps the mouse capture on (re-enabled after ResetForPlayer / when dropped) and
  logs `HUD click <id>` once per button: check the console if a click still does nothing.
- Stand-alone upgrades (the duplicate agent's 60_garage.js / 80_game.js work, kept): offline the tracks are free and local (`pe.localPilot`, core
  `keptPilots` survive round restarts, a local pilot has rank 0); one click asks, CONFIRM upgrades. Server mode: "No pilot record from the server yet"
  instead of "Need N CR" while the mailbox has not delivered.
- Mode display: mode tag top centre (TDM / CONQUEST / KOTH / CTF / FFA / SORTIE, own colour), objective line under the scores (tickets, kills to win,
  hill move timer, captures to win), objective chips (Conquest A B C, KOTH hill, CTF flags: holder colour, progress bar, T HOLDS / CT 64 % / CONTESTED /
  TAKEN 60 % / DROPPED 12), a capture strip while something changes hands (the zone you stand in first; CTF: FLAG IN HAND 60 % HOME / ENEMY HAS YOUR
  FLAG). Intro slate: the full mode name over a bar in the mode colour + the objective. Reads 85_objectives.js / captureStep fields defensively
  (nT / nCT, scoring, hillLeft, returnMax, carrierTeam); core adds `match.khTarget / ctfCaptures`; `!vote dom|domination` = Conquest.
- Reticle: FCS cone ring 300-400 px -> 128 px thin broken ring (scaled 0.7-1.1); spawn shield ring 420 -> 200 px. Message line: two rows, shifted
  right of the chat; `!garage` in a mech: "In a mech: !spec first, or wait for your next death"; `!help` pages queue (only the last line used to show).
  Spectator bar moved under the reticle (y 716). Podium moved to y 196 (under the kill-feed band at 4:3).
- Weapons: every arm / shoulder part has a `desc` in parts.json (role + feel); the garage shows it on two info rows, extra figures on the third.
- Tests: `node test/garage_upgrades.cjs` (new, 413 checks: offline click -> CONFIRM -> SORTIE -> the mech's AP / damage / EN / drain / lock carry the
  level and match the garage figures, a round restart keeps them; server mode `ifr_srv upg` -> mailbox answer -> save -> sortie; every upgradable part
  at every level); `node test/hud_strings.cjs` (all modes / chips / strips / intros / help pages fit); `node test/hud_driver.cjs` 11/11;
  `sh tools/mock_flows.sh` both runs OK with a new step (offline upgrade by keys -> fight HUD AP / 11 672); mechanics 169/169, features 35, traits 83,
  auras 395, sim 64 x 120 all modes ended; hud_check (1440 / 1920 / 2333, --glyph-space --allow-outside Txt): clean except the old fight layout under the open chat at 1440 (vitals, kill pop, reticle box: not changed); tscheck OK.
- Previews: `preview/hud/reticle_before_after.png`, `mode_objectives.png`, `intro_mode.png`, `garage_equipped.png`, full screens `hud_*.png`
  (incl. `hud_fight_cq / ctf / kh`, `hud_garage_1440.png`); the previous ones in `preview/hud/before_playtest_fixes/`.
- Unverified in CS2: that skink52 plays at a non-16:9 aspect (the garage now fits either way); that the win panel clears with mp_maxrounds 999;
  track clicks (watch for `HUD click ifr_ur0`); Button hit-testing inside the translated centre column (confirm / cancel); the fight HUD at 4:3 with
  the chat open (vitals and kill pop sit under it, as before).

**10 Nov 2026, ~15:20: second playtest, combat / movement / aim (mock-tested; built, NOT deployed, NOT played).** Tests: `node test/playtest_combat.cjs` (29).
- Clip brushes block mechs: `20_mech.js IF_clipStep` sweeps a player hull (`world.traceClip` = `Instance.TracePlayer`, 90_main.js; any live pawn for
  AI mechs, rider pawns ignored) at 88 / 208 u over the feet, a body radius ahead; a hit is a plane the mech is pushed off (stops and slides), clip
  tops can be stood on. Clips are learned per cell (discovery sweep every 8 ticks); budget `cfg.clip` (64 hull traces a tick: mock worst case
  117 -> 64). Dunes has 68 `toolsclip` meshes (20 u fences, 300-700 u boxes) in both arena copies.
- Sky: the vmap's sky shell is z 6 143 (copy 2: -2 521), the script's arena ceiling 5 000. The adapter measures the sky at load (`[ironframe] arena N:
  sky ...`); rounds and missiles cruise under `IF_capZ` (min(sky - 300, ceiling + 200) = 5 200) and vanish at the sky (also the sky walls past the
  arena box) without a blast. Lofted missiles overshot their loft height by up to ~3 000 u (turn radius) and the old code burst them at 7 000 u.
- Shots on the reticle: the cause was `cameraRay`'s up vector (f x r points DOWN), which put the aim ray 2 x 180 u under the real camera, plus a
  fixed 6 000 u convergence from the eye line: rounds landed 115 / 153 / 230 / 358 u low at 700 / 1 500 / 3 000 / 5 500 u. Now the camera ray (the
  upper prop's real origin + hip, the side kick, the wall pull-in traced) is traced to the point under the reticle (`40_combat.js IF_reticle`,
  enemies only, 12 000 u) and every round flies from its muzzle to it; a reticle point < 200 u in front of the muzzle fires along the camera ray.
  Remaining by design: FCS assist bends rounds to a locked target's centre; spread.
- Own IFF diamond: lifted 8 deg clear of the pilot's reticle (`40_fx.js iffPlace`); not drawn at all with no other human in the arena copy.
- A duplicate agent from another session wrote the first clip / sky / reticle / IFF version (stopped mid-way); I kept its clip discovery, sky,
  reticle and camera up-vector fix and replaced its IFF hide (it hid a human's marker from everyone most of the time) and its clip wall stop.
- Unverified in CS2: TracePlayer with a parked pawn for AI mechs, its hull / normals on clip meshes, clipCameraOffset matching a line trace,
  the measured sky line, marker lift readability. Other agents' edits seen in my files and kept: 50_ai.js `objPull`, 00_config.js `mp_maxrounds 999`.

**10 Nov 2026, ~13:00: playtest fixes (mock-tested; script + panorama compiled and deployed to mg_ironframe_dunes; NOT played yet).**
- AI aim model (`50_ai.js` header, DESIGN.md "AI"): reaction delay on switch / reacquire, lagging turn, low-passed target velocity, QB surprise,
  range / settle / lateral-speed error, the bot's FCS steers to its perceived point (the gimbal used to make bots hit 99 %). Hard 93 / 85 / 64 / 28 %
  (standing 2 000 u / strafing 1 500 / strafing 3 500 / after a QB), normal 73 / 69 / 38 / 23 %. Frame ap mods retuned + Atlas regen 2 -> 0.8 %/s
  (BALANCE.md): frames normal 44-55 %, hard 43-55 %. mechanics.cjs +6 aim tests (169).
- Stuck screens: a dead pawn shows CS2's observer view, not our camera: `revivePawn` (Pawn.Reset, hidden, booth) on `!garage`, `!spec` and 1.5 s after
  a scripted kill. The respawn watchdog no longer switches real kills off (common.cfg's `mp_respawnwavetime 10` tripped it: no kill credit for the
  map); the script sends `mp_respawnwavetime_t/ct 0` and slime-mg-gm `mech.cfg` sets them. CS2 ended the round but no new one in `RESTART_WAIT` 15 s:
  the script starts it (was: podium forever). Every round shows its intro slate (the podium no longer lingers).
- Kill credit: inflictor = the killer's pawn (was the upper-body prop); kills of the script's own AI mechs (no pawn) give `NPC_KILL_SCORE` 2 score.
  The map still has no nav mesh, so the fill is script AI, not CS2 bots: those kills can't be real kills (kills column) until it has one.
- Podium: the core ranks AI fill too (`podiumInfo`, names / team / kills incl. PvE); the cards were empty with one human and AI fill.
- Garage: arms / shoulders fill R and L in turn (every pick used to replace R). Prop contact adds at most 200 u/s upward (sloped prop faces launched mechs).
- HUD: radar top left (where CS2's radar sits); icons, badges and part cards anti-aliased neon (no pixel art), 10 new family icons.
  Before / after: `preview/hud/before_neon_icons/`, `preview/hud/hud_fight.png`, `hud_garage.png`, `images_sheet.png`.
- Tests: `sh tools/mock_flows.sh [entities.json]` (mock engine `scenario=test/mock_flows.mjs`: !spec / !garage / !back orders, garage with a dead pawn,
  two-arm picks, round end in the garage, podium cards, round 2 with and without CS2 restarting). Give the Hammer map's dump for the bay check
  (`python create/dump_entities.py <vmap> <json>`).
- Unverified in CS2: Pawn.Reset reviving a killed pawn for the custom camera; the real cause of the round-won freeze was not reproduced
  (candidates: a CS2 match end with mp_timelimit 30 from mech.cfg, or no OnRoundStart); the fallback covers both. Server mode garage saves still
  depend on the mailbox answer (unconfirmed in game). Pre-existing mock flag: "props Teleported 3+ ticks in a row" (also in the previous build).

**10 Nov 2026, 03:50: everything below is compiled and deployed to mg_ironframe_dunes; NOT yet played in game.** Next: skink52 playtests.
- Deployed: script (Cinzel Bold neon HUD, hip_curve/sway wired in 30_render.js rigHip, traits for 19 frames, auras, AC feel + economy
  passes), panorama, all 47 frame vmdls (hard-surface materials, floor fix for every leg family in create/mech_anim.py FAMILIES floor=True:
  review shows no foot below the floor), 19 auras + particles. Map: patch_cache added the aura models, 76 aura particle entities and 256
  origin-fallback mailboxes `ifr_mail_NN_0..3` (backup backups/*.pre_aura_mail.vmap); entity-only rebuild (build_maps.ps1 entities).
- Mailbox: the server sim read `ifr_mail_00` back unrenamed after AddOutput targetname, so the plugin default `MailboxMode` is now "origin"
  (slime-mg-gm Config.cs + docs). Unconfirmed until a real human round sends ifr_pilot: check the garage loads the saved pilot.
- Server copy: the local dedicated server needs the vpk plus scripts / models / particles / soundevents copied into game\csgo (the map agent's
  sims removed its copies afterwards).
- Tests: test/lib.cjs reads IF_ARENA_FILE now (IF_ARENA is the arena name tools/names.sh exports; sourcing it broke every test).
- Open: in-game checks listed per section below (aura flipbooks, F_TINT_MASK team paint, AO strength, QB 0.18 s jet, camera pull-back,
  tunnel vis hints, White Glint flare strength); knee/ankle stretch on 6 smooth-skinned rigs; Ogre 61 % / Unicorn 40 % on hard AI.

**10 Nov 2026, ~03:00: the four Tripo frames are player frames (offline-verified, NOT compiled / tested in game).**
- Traits (src/core/87_traits.js, adapter 46_traits.js, docs/FEATURES.md tables): Sandviper **Spotter** (a lock held 1.5 s marks the target 6 s:
  bounty dot on the marker team's radar via 45_features.js featPinged, +10 % damage taken), Kestrel **Slipstream** (-35 % damage for 0.5 s from
  each quick boost), Warden **Aegis pulse** (hold F 0.5 s: 10 % max-AP barrier for 6 s on itself and allies within 900 u; 18 s cooldown, 300 EN),
  Bastion **Siege mode** (hold F 0.5 s on the ground: rooted 4 s, +20 % damage, a quick boost ends it; 16 s cooldown, 300 EN). Bots use the two
  active ones through featPre. 20_mech.js: `featSpeed` 0 now roots (was read as unset). parts.json 21-24: `pve` / `todo` gone, mods + trait text;
  traits.cjs 83/83 (19 player frames). Balance: docs/BALANCE.md tuning notes (normal 41-59 %, hard 43-61 %, no frame pushed out).
- Auras: four new styles in tools/auras.py (radar_scope lime, slipstream sky blue, aegis_pulse teal, siege_anchors ultraviolet; new textures
  radar / pulse / stake), parts.json#auras blocks, auras.cjs 395 checks. Built with `--no-compile`.
- Floor dip: create/mech_anim.py has a `mixamo` family (matched on the original bone name glbrig.py now keeps in `src`, passed through
  mdl2cs2) with a floor clearance on the hover / boost / air / QB clips (the measured foot mesh; flattens the tiptoe to 35 % first, then lifts
  the ankle). Hover min z Bastion -40 -> +1 u, Warden -13 -> +1, Kestrel -8 -> +1, Sandviper -4 -> +1; hip curves, models.json entries and
  stretch_check identical; the other 20 frames untouched (13 of them still dip 3-50 u in hover: enabling `floor` for their family is a
  one-line change in FAMILIES, then a reconvert and recompile).
- To compile (skink52): `python -I tools/compile_frames.py --only tripo_scout,tripo_kestrel,tripo_warden,tripo_bastion`; the aura models,
  materials and particles of sandviper / kestrel / warden / bastion (`python -I tools/auras.py --only sandviper,kestrel,warden,bastion`
  without `--no-compile`); then `tools/patch_cache.py` on the map (cache props for the new aura models, `ifr_pfx_aura_<frame>_00..03` pools).

**10 Nov 2026: Armored Core feel pass (offline-verified, NOT tested in game).** Targets, sources and every old -> new number: `docs/AC_FEEL.md`.
- Changelog: ground boost free (regen x0.5 while skating), air boost 300 -> 180 EN/s, assault boost flies level (gravity x0.2); QB is a 0.18 s jet
  (distance 283 -> 772 u medium), QB 450 -> 600 EN, reload 0.38 / 0.45 / 0.55 s by class and up to x1.6 above 70 % of the load limit (boost -10 % there);
  two-step chain QB (one extra inside the reload, 60 deg off line, x1.25 EN; not Ronin; bots do not use it); QB breaks a stagger in its last 0.25 s.
  EN: regen x1.6 (GN-Standard 560 -> 900), pause 0.6 -> 0.9 s, +20 % of the tank after a redline. Stagger meter held 2 s then 450/s (was 1.2 s / 300/s);
  per-weapon direct-hit multiplier `w.dha` (1.2-2.0) replaces the flat x1.5; `damage` events carry `crit`, which shows the heavy hit marker.
  Class AP 7 800 / 9 000 / 11 000 -> 9 500 / 10 800 / 12 900, boost +15 % (1 720 / 1 500 / 1 260); FCS soft lock -0.05..0.1 s; shotgun impact 70 -> 60,
  laser EN/shot 180 -> 230; frame ap mods Stryder 1.19, Lisa 1.26, Atlas 0.89, Cerberus Atlas 0.89. Camera: speed dolly (+120 u at boost speed,
  +80 u assault, eased 0.25 s) instead of the fixed +90 u, as the boost FOV kick (no FOV API); QB kick back 70 -> 40.
- Results: frames normal 44-58 %, hard 39-59 % (Unicorn LOW at hard); families: autocannon (shoulder table, old), blade 20 % and flamer 8 % flagged as before;
  mechanics 159/159 (15 new AC checks), maxed vs stock duels 72 -> 84 % (longer fights; caps hold). Next AC gap: damage fall-off past ideal range.
- Second pass (same day): anti-stomp caps AP +15 -> +5 %, DPS +10 -> +3 %, mobility 8 -> 3 %, ladders flattened (frame AP 1 %/level, weapon damage 0.6,
  generator 1, booster 0.6, FCS -1): maxed vs stock 84 -> 67 % (fair side-alternating duel, 56 % noise floor). AC6 ideal-range fall-off (`falloff` in
  parts.json; garage shows `Range: ideal / max`); homing blade lunge to the 900 u lock range (lunge 0.2 s); hard AI two-step against missiles (tier `chain`);
  flamer / blade / pile bunker buffed, laser / shotgun / rifle / rail trimmed, VM-6 470 + turn 120. Families 34-70 % with no flags; frames normal 40-59 %,
  hard 40-61 %; mechanics 163/163. Details: docs/AC_FEEL.md "Second pass", BALANCE.md tuning notes.
- Third pass: upgrade steps cost floor(price x 30 %) x (level + 1) (`caps.upgrade_cost_pct`, core + plugin `Catalog.UpgradeCost`; slime-mg
  tests/run.py ironframe expectations updated, 3/3 pass); garage tiers MK I-V, a MK V frame wears its aura in the accent colour; AC-Drum and flak are
  braced shoulder cannons (0.2 / 0.3 s, quads exempt); anti-stomp duel paired (control 50 %). Earn table in BALANCE.md "Progression".

**10 Nov 2026, ~01:00-02:30: hard-surface materials for every frame + four Tripo frames (offline-verified, NOT compiled/tested in game yet unless noted below).**
- Materials: `create/hardsurface_mat.py` (shared) derives per-pixel roughness / metalness / AO / team-tint mask, chipped-paint edge wear on the mesh's
  convex feature edges, crevice grime, white-paint knee, and a normal map from the albedo when the source has none; source phong-exponent and
  env-mask gloss used when present. `create/mdl2cs2.py` runs it by default (`--plain-mat` / env `MDL2CS2_PLAIN_MAT=1` off; it adds ~5-300 s per frame).
  `tools/upgrade_materials.py` rewrites converted frames in place from the plain originals in `<work>/mat_orig/<key>/` (`--restore` undoes) and
  re-derives the `_scorched` / `_wrecked` vmats and colour maps. `tools/compile_frames.py [--only k,..]` copies + compiles every frame vmdl (materials with them). Before/after sheets: `preview/materials/<key>.png`, `contact_sheet.png`
  (`tools/review_materials.py`, a deferred PBR software renderer). Findings: docs/creation/models.md "Hard-surface materials".
- Tripo frames (`data/frames.json` source `tripo`, status review; `create/glbrig.py` loads the rigged GLB inside mdl2cs2, Mixamo bones renamed to
  ValveBiped so mech_anim's valve family drives the clips): `tripo_scout` (light, Sandviper, 10.0k tris), `tripo_kestrel` (light, Kestrel, 10.1k),
  `tripo_warden` (medium, Warden, 10.5k), `tripo_bastion` (heavy, Bastion, 32.6k -> 21.0k quadric). parts.json ids 21-24 (player frames
  with traits since ~03:00, see above). Review sheets `preview/review/tripo_*.png`, GIFs `preview/review/anim/tripo_*`.
- mdl2cs2 fix: hardpoints of bones with < 3 owned vertices used the raw (unscaled, unrotated) bone position; now the placed one.
- Follow-ups (mech_anim): the Tripo rigs' hover floor dip is fixed (mixamo family, see above).
- frames.py: `--merge` (with `--only`: models.json keeps every other frame's entry). Two frames.py runs at once overwrite each other's state.json
  results (each saves the whole `frames` section it loaded): run them one at a time.

**9 Nov 2026, ~20:00: arena copies, new weapons, readability, contracts (offline-verified, NOT yet tested in game).**
- Arena copies (`src/cs2/15_arenas.js`): `ifr_arena_2..4` info_targets; the offset is measured from duplicated marker pairs
  (skink52's Dunes copy: 0 0 -8664 from 27 pairs). <= 32 humans share copy 1; above, humans are dealt evenly (T and CT separately)
  at round start; late joiners go to the emptiest active copy. Each copy runs its own core game (AI slots 64 + 64 k); the CS2 round
  ends when every active copy has finished. Mock: 36/40/48 humans -> 18/18, 20/20, 24/24 over three rounds, OK.
- 10 new parts (113-118, 211-214): pile bunker, sniper cannon, burst rifle, flamethrower, energy shotgun, heavy blade, mine layer,
  orbit drones, multi-lock missiles, cluster artillery. mechanics 144/144; balance in BALANCE.md (flamethrower weak vs AI kiting).
- Readability: team IFF markers over mechs, hit/heavy/kill reticle markers, killer camera on death, drone/mine/burn visuals.
- Plugin: daily contracts (3 per pilot per UTC day, `!contracts`), catalog copy refreshed; `tests/run.py --only ironframe` 3/3.
- Rank-up line lists newly unlocked parts.

## Earlier (same day)
**9 Nov 2026, evening: first human review fixed (not yet retested in game).** skink52's report: stuck behind the team intro /
"first half" banner, WASD rotated, legs orbiting the body, mechs passing through solid geometry, no HUD, no animation, clunky.
Done: input axes fixed (core wants mx right+, my forward+); `mp_team_intro_time 0`, `mp_halftime 0`, no warmup (script and
slime-mg-gm `mech.cfg`, resets in `common.cfg`); the first round starts by itself 1.5 s after load; unassigned humans are put on a
team; a once-a-second watchdog respawns stuck humans and restores camera/move type; the script surveys the real map collision at
load (`IF_Nav.probeStart/probeStep`, 2 traces per 256 u cell) and reads `ifr_drop_*` / `ifr_point_*` from the map, so Hammer edits
collide and AI paths follow them; legs and upper rotate about the frame's waist pivot; 18 of 20 frames are skinned with procedural
clips (legs hover/move/boost/air/land/qb_l/qb_r, upper idle/fire_r/fire_l/fire_s/stagger) driven by state and events; garage rebuilt
from the mock-up (armory list, upgrade tracks with now/next, frame stats, equipped weapons, item info, confirm bar, mouse) with a live
3D preview on a hangar bay; model review gallery `preview/review/` + `docs/FRAME_REVIEW.md` (`status` per frame in data/frames.json).
Map needs: a lit hangar room ~5600 u across with an `info_target` named `ifr_hangar` at its floor centre (8x8 bays, 700 u).
Modes now: Team Deathmatch (tb), Conquest, King of the Hill (kh: one hill, moves every 120 s, first to 150),
Capture the Flag (ctf: flags at the first team drop or map `info_target`s `ifr_flag_t` / `ifr_flag_ct`, 3 captures; carrier boost drain x1.5),
Skirmish (FFA), Sortie (co-op AI waves). All soak clean at 64 mechs; CTF captures happen at low population, at 64 carriers die
fast over 12000 u (place the flags closer in Hammer). Feel: snappier walk (accel 3600, friction 8, leg turn 600), camera kicks on
quick-boost / landing / heavy fire / big hits, missile trails + rocket loops, damage-direction arrows, XP ticker, teams balanced
by rank at round start (server mode, 6+ humans). Sprawl and Orbital sketches: `out/sketch/` + `preview/arenas/`.
HUD not showing: unexplained; check the console line `[ironframe] v... ready: ... HUD on/MISSING` first.

## Earlier
**9 Nov 2026, 14:30: everything is written and verified offline; the Dunes map compile and the last asset pass were in flight.**
What exists (all `written`, `verified offline` where a check is named, nothing `tested in game`):
- Docs: DESIGN.md, INTERFACES.md, SERVER_CONTRACT.md (incl. §5b plugin-side decisions), TESTING.md (hand checklist), HUD.md, AUDIO_FX.md, BALANCE.md, ARENAS.md, CREDITS.md.
- Core (`src/core`): movement, every weapon family, AP/stagger, lock-on, modes tb/cq/sk/so, AI (3 tiers, squads, fill), progression/garage, nav.
  `node test/mechanics.cjs` 66/66 incl. the contract vectors; `node test/sim.cjs 64 120 all` clean (0.3 ms/tick p50); `test/balance.cjs` → BALANCE.md
  (rifle/gatling impact and damage retuned; blade still weak for bots); `python -I tools/parts_check.py` ok.
- Adapter (`src/cs2`): pawn ride + FOLLOW camera, prop rendering (legs/upper/parented weapons), particles + sounds pools, HUD feed, garage (key-driven),
  server channel (echo ifr_srv / mgstat, mailbox name + origin fallback), chat, rounds. Flow: join → intro → auto-sortie with the active loadout;
  Ctrl/F while dead (or `!garage`) opens the garage.
- Script build: `node ../../create/build/build.mjs build.json` → `out/addon/maps/scripts/ironframe.js` (395 KB); `tscheck` OK; mock engine
  (`create/test/mock_point_script.mjs`, Dunes entities, 64 players, held+churn, 120 s) `OK: no errors`, 0.85 ms/tick avg, 2 round cycles clean
  (with `CONFIG.core.round` shortened to 70 s for the run). Kill credit reaches the mock scoreboard.
- HUD: 274 panels, hud_check clean at 1920/2333, driver harness `node test/hud_driver.cjs` passes, previews in `preview/hud/`.
- Audio/FX: 79 sound events (90 synthesised WAVs), 52 particle sources, all compiled by resourcecompiler; `_gen/sounds.json`, `_gen/fx_particles.json`.
- Models: `create/mdl2cs2.py` (GMod MDL → CS2 prop, bone-group split, hit spheres, hardpoints) and `tools/frames.py`; 17+ frames converted
  (previews in `preview/frames/`; Titan Atlas, Cerberus Atlas, White Glint, Hari, Noblesse, Mule look right; ValveBiped Gundams needed the
  arms-down pose pass), weapon props and fx models (`tools/weapon_props.py`, `tools/fx.py`) → `_gen/models.json`.
- Map: `tools/vmap.py` + `tools/arenas/{dunes,sprawl,orbital}.py`, sky, loading slides; Dunes generated (`_gen/arena.json`, `entities.json`,
  previews in `preview/arenas/`); compile with `C:\source1\cs2port\build_maps.ps1 mg_ironframe_dunes` after `sh tools/deploy.sh`.
- Server: slime-mg-gm `plugins/SlimeMG/IronFrame/` (mode `mech`, group `mg_slime_mech` pending a Workshop id), builds clean,
  `python tests/run.py --only ironframe` 3/3. Not committed.

## Next steps (in order)
1. Finish the Dunes compile; load it on the local server in mode `mech`, run TESTING.md §1–§4; the first things to verify: the mailbox rename
   (`AddOutput targetname` with a ~400-char name) and `RunScriptInput` with a pawn activator; if the rename fails set `IronFrame.MailboxMode "origin"`.
2. Fix what the first in-game run shows (camera offsets per class, pawn ride feel, model scale/hardpoints, sound ranges).
3. Sprawl and Orbital maps (modules exist, not generated/compiled); the remaining frames (tf_ogre, gundam_rx78 if missing) and gait clips.
4. Workshop: descriptions (`<addon> STEAM DESCRIPTION.txt`), icons, and the porters' permissions before any public upload.
5. Commit cs2mapping (`[ironframe]`) and slime-mg-gm; push only with skink52's OK.

## Open questions for skink52
- Permission from the GMod porters (Moon., Tech, blaze98, Kali, ...) before a public Workshop upload; private server use meanwhile.
- The DESIGN.md §3 class AP numbers are superseded by parts.json (light 9500, medium 10800, heavy 12900 after the AC feel pass).
