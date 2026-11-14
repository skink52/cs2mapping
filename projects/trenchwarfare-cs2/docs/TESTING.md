# mg_trenchwarfare CS2 test: what to check

AI-generated (Claude) for skink52. This is the in-game checklist for the remaster: every item here can only be settled by CS2 (the
compiler, Hammer or the running game). Each item says **how** to test, what to **expect**, and **where to record** the result.
Until an item is ticked, it is **NOT YET TESTED IN CS2**. Everything before this point is **simulated** or checked offline
([SCRIPT.md](SCRIPT.md), [REVIEW_WORLD_1.md](REVIEW_WORLD_1.md), [PRESENTATION.md](PRESENTATION.md)).

**Version under test:** the remaster, 12 Nov 2026. The map is the chain's final vmap; write down the CRC32 that
`python -u tools/deploy_tw.py` prints (`a109a678` for the 12 Nov chain, which ran before the sound emitters existed: re-run `--chain`).
Deploy, compile and force-compile the HUD first ([BUILD.md](BUILD.md)). After copying new files: `disconnect`, then `map mg_trenchwarfare`.

**Reporting.** Only report what fails: what you saw, where (`!pos` line), and the console lines. Anything you don't mention counts as passed.
Every script console line starts `[tw]`.

**Where to record:**
- **R**: the [Results](#results) table at the end of this file. One row per item that failed or needs a note.
- **BL**: [BUILD_LOG_1.md](BUILD_LOG_1.md), in the section named.
- **RS4**: [REVIEW_SCRIPT_1.md](REVIEW_SCRIPT_1.md#open-questions-only-cs2-can-answer), "Step 4: bots".

Test in this order: a failure early (compile, script start) makes the later sections meaningless, so stop there and report.

## A. Compile log (before launching)

Logs: `C:\source1\cs2port\logs\mg_trenchwarfare_assets.log` and `mg_trenchwarfare_build.log`. Save copies in `out/step9/logs/`. Send lines, not a summary.

- [ ] A1. Assets: grep `RESOURCE COMPILE ERROR` and `compiled, N failed`. Expect 0 failed, whatever the wrapper says. Record: BL "Errors and warnings".
- [ ] A2. Grep `referencing missing material` and `FAILED - these materials did not compile`. Expect none. Record: BL "Errors and warnings".
- [ ] A3. Forced `resourcecompiler -f -i` on the xml, css, js and svg. Expect each `compiled`, `0 failed`. Record: BL "Commands and times" row 5.
- [ ] A4. Map: `OK in N min - mg_trenchwarfare.vpk moved`. Record N and the vpk size: BL "Map compile figures".
- [ ] A5. Grep `DELETED`. Expect none naming `mortar_*`, `undergroundopen`, `woodsopen`, `tw_crater_smoke_*` or `tw_rain*`. Record: BL "Map compile figures".
- [ ] A6. `Charting N unique meshes` and `Packing N UV charts`. Expect lightmap still 2048, no `OUT OF MEMORY`. Record: BL "Map compile figures" (tw34: 24,754 / 1.37 M).
- [ ] A7. The nav generation line. Expect **under 5,000 areas** (estimate about 1,470; tw34 had 44,160). Record: BL "Map compile figures" and RS4.
- [ ] A8. Grep `Unconnected ladder`. Expect it for the two woods ladders at most (M4, known). Record: BL "Errors and warnings" (nav row).

## B. Hammer

- [ ] B1. Open `maps/mg_trenchwarfare.vmap`. Expect no error dialog and two trench systems with no man's land, aerodromes on both flanks and the briefing room below. Record: R.
- [ ] B2. `tw_script` (point_script) and `tw_hud` (custom_hud_layout) file fields are not red. Record: R.
- [ ] B3. Fly over the mortar pits, the 75 gun at (-2660, 900) and the woods ladders. Expect no ERROR models and no pink materials. Record: R (send the model / material name).
- [ ] B4. The 10 mortars are `prop_dynamic` named `mortar_t_1..5` / `mortar_ct_1..5`; the 4 blockers use `revet_planks_broken*_dyn`. Record: R.

## C. Spawn and rounds (listen server, alone, then with bots)

- [ ] C1. `map mg_trenchwarfare`. Console: `[tw] points: trench 20/20, heal 3/3, plane spawns 5/5, aircraft 5/5`. Send the line if a number differs. Record: R.
- [ ] C2. No `[tw] error in ...` line, ever, in any section. Send each with what you were doing. Record: R.
- [ ] C3. You spawn in the briefing room with the orders sheet (role, three lines, countdown from 4). Then you are at your post with the role banner. Record: R.
- [ ] C4. The cvars applied: `mp_roundtime` 60, `mp_freezetime` 0, respawn on death, no buy menu. Record: R.
- [ ] C5. `mp_restartgame 1` twice, once while flying and once at the map table. Expect normal scale, walking, camera back, no frozen pawn. Record: R.
- [ ] C6. After a minute: `[tw] perf: X ms/tick avg, Y ms max, ... longest gap between thinks Z ms, errors 0`. Send the line. Record: R.

## D. Infantry

- [ ] D1. Kit: T gets Gewehr 98 + Luger, CT Lee-Enfield + Colt; magazines from vdata. Record: R.
- [ ] D1b. New models (13 Nov): Gewehr 98 (lawlordp), Luger P08 (Burdock), Lee-Enfield Mk III (Moony_State). In first person each sits in the hands like the old one (no giant weapon); the Gewehr and Lee bolts and the Luger toggle move on fire and reload; magazines drop. Record: R.
- [ ] D2. Get 3 kills without dying (bots). Expect a MARKSMAN headline and the Mondragón (T) or Lewis (CT). SHIFT+E and `!swap` toggle back, ammo kept. Record: R.
- [ ] D3. Stand at a dressing station (support trench by a shelter) while hurt. Expect health and armour to refill. Record: R.
- [ ] D4. Walk the fire steps. Expect you can see over the parapet everywhere, CT x 1575, y -576..-320 included (M6: report if you can't). Record: R.
- [ ] D5. `!mortar` in the field. Expect a toast saying you move at your next deploy, and no teleport now. In the briefing room it applies at once. Record: R.

## E. Mortar crews (`!mortar`, one human per seat or one human + a bot)

- [ ] E1. Plotter: E at the table brings up the wooden plotting board (your trench map, enemy line at the top). WASD moves the marker, MOUSE1 locks. The knife is out: MOUSE1 does not fire a pistol. Record: R.
- [ ] E2. Loader: E at the ammo box ("Take a mortar bomb"), E at the tube ("Load the bomb"), then SPACE / "[E] FIRE". Expect a launch sound and smoke. Record: R.
- [ ] E3. **Fire animation:** the tube recoils on each shot, then returns to idle. Expect it on all 5 tubes per side. Record: R (which tubes don't).
- [ ] E4. Nothing at the tube pushes or traps the crew; walk seat a to seat b in `pit_t_2` (`!pos` there; L1 stock shells). Record: R.
- [ ] E4b. **Pit sandbags (new 14 Nov):** in each side's pits, a fourth sandbag course on the front arc. Expect no floating or sunk bags and no bag in the tube, table or stores; the tube still fires over it; standing at a seat, the enemy trench line is hidden behind it (except at `pit_ct_2` SW and `pit_t_4` SE, two known dips). Record: R (pit + `!pos`).
- [ ] E5. Impact: a falling whistle about 2 s before, a blast and dirt at the marked point with spread growing with range. Record: R.

## F. Assist credit

- [ ] F1. Two humans crew one tube. A shell kills an **armoured** enemy (bot with armour). Expect the kill to the firer and an **assist** to the loader in the kill feed and scoreboard (REVIEW_SCRIPT_1 bug 7). Record: R.
- [ ] F2. A shell from a firer who switched team before it landed. Expect no team-kill credit. Record: R.

## G. Crew-death bug (the old "crew dies when firing")

- [ ] G1. Fire 20+ shells from each side's pits with bots around. Watch the console for `[tw] blocked <n> damage to mortar pit (...)` and `[tw] crew death: slot ... attacker ..., inflictor ..., weapon ..., own tube fired <s> ago`. Record: R, paste every line.
- [ ] G2. If a crewman dies at the moment his own tube fires, the `crew death` line names the attacker and inflictor. Send it: it is the only evidence of the cause (REVIEW_SCRIPT_1 #19). Record: R.

## H. Pilots (`!air`, then die or wait for the next deploy; do CT then T)

- [ ] H1. You start at an air spawn in the aircraft, chase camera behind, your own model hidden, cockpit dials bottom centre. Record: R.
- [ ] H2. Mouse steers, W/S throttle, A/D roll, MOUSE1 guns with tracers, MOUSE2 bomb (2, re-armed after 18 s); the bomb-sight ring shows where it lands. Record: R.
- [ ] H3. **Boundary turn:** fly straight out at each map edge (x about 6500, y about 5500). Expect one smooth turn home to one side, with no flip-flopping and no destruction. Do it again with the nose high. Record: R (`!pos` where it misbehaved).
- [ ] H4. **Dive sound:** dive nose down 25 deg or more at full speed. Expect a 3 s howl that follows the aircraft, again after you level out and wait 6 s. Record: R.
- [ ] H5. Crash into the ground: kill and explosion, credit to whoever last hit you within 10 s. Two lives, then infantry. Record: R.
- [ ] H6. Sit still 60 s in the air (AFK). Expect the aircraft to go home and you to deploy as infantry. Record: R.

## I. Bots and low population

- [ ] I1. Alone on the server: bots fill to 16 (8 a side) and leave as players join. Record: R.
- [ ] I2. With under 4 humans per side, 1 bot pilot flies and 2 bot crews fire for each side within about 30 s. Record: RS4 ("how good the AI pilots and crews feel").
- [ ] I3. Infantry bots fight from the fire steps, stay out of no man's land and the briefing room, and come back if they wander. Record: RS4.
- [ ] I4. **Yielding:** `!air`, die, deploy. Expect a bot's aircraft handed to you (toast "A bot pilot handed his aircraft over to you"). The same with `!mortar` and a bot's seat. Record: R.
- [ ] I5. A frozen bot at a mortar table and a bot pilot: no stuck bot left after `mp_restartgame 1`. Record: RS4.
- [ ] I6. **FPS hitch:** `cl_showfps 1` with 16 bots for 5 minutes. Expect no dip every 0.5 s (tw35: 200 to 71); the perf line's longest gap stays under about 50 ms. Record: R and RS4.
- [ ] I7. Nav area count from the compile (A7). Record: BL and RS4.

## J. Unlock blockers (wood and mine galleries)

- [ ] J1. At round start the planks stand at the woods ladder (north end of the fire trench, `!pos` near y 2790) and in both sap mouths (south end of the support trench, y -2808). You cannot pass. Record: R.
- [ ] J2. After 15 kills or 4 minutes: a blast, the headline "THE WAY TO THE WOOD IS OPEN", the planks gone, and the ladder climbable on both sides. Record: R.
- [ ] J3. After 30 kills or 8 minutes: "THE MINE GALLERIES ARE OPEN", the sap planks gone. Record: R.
- [ ] J4. `mp_restartgame 1` after both opened. Expect every blocker back and closed. Record: R.

## K. Sap tunnels

- [ ] K1. After J3, walk into each sap. Expect you need to **crouch** at the mouth (the upper benches set 57-62 u head room); the new floor ramp, lintel and ground cap over each mouth show no gap or light leak. Record: R.
- [ ] K2. Without the `--user-h1` opt-in, the bench barricade behind the planks still blocks the way (H1, known). Report if you can crouch-jump through and how. Record: R.
- [ ] K3. With `--user-h1 unlock`, the benches stand until J3 and go with the planks; walk through to the chamber on both sides. Record: R.
- [ ] K4. Galleries are lit, with no black void, no getting stuck and no falling through, the tunnel set in gallery water included (L4). Record: R.

## L. Terrain

- [ ] L1. Walk no man's land and both rears. Expect fresh shell holes, churned mud and puddles, with no seams, spikes or holes at tile edges. Record: R.
- [ ] L1b. Seams (13 Nov): walk the support/comm trenches and the mortar side, and look along the revetment tops from inside the trench and from no man's land. Expect no slot behind the siding top, no see-through cracks, no light leaks. Known: small steps at the six dressing-station niches (user revetments) and one backwards revetment at (-1892, 144). Record: R.
- [ ] L2. **Mud stretch:** look at the steep crater walls (48 faces). Expect the texture is not visibly smeared. Record: R (`!pos` of the worst).
- [ ] L3. **Ruts:** the tank tracks behind the 4 wrecks and the twin lorry ruts along both airfield edges (y about +-1100). Expect them to read at player scale. Record: R.
- [ ] L4. Parked aircraft and props sit on the ground, not floating or sunk. The lightmap over the re-gridded tiles has no blotches. Record: R.

## M. Rain

- [ ] M1. Console `ent_fire tw_rain FireUser1`. Expect rain over both trench systems. Note the FPS before and after. Record: R (both FPS numbers).
- [ ] M2. Stand by a dressing-station shelter: rain on tin heard only near it. `ent_fire tw_rain FireUser2` stops rain and sound. Record: R.
- [ ] M3. A player who joins while it rains hears the tin loop. Record: R.

## N. Smoke columns

- [ ] N1. Six smoke columns rise from shell holes in no man's land (`tw_crater_smoke_1..6`). Expect them to read as smouldering and cost little FPS. Record: R.

## O. HUD (at 1920 x 1080, 2560 x 1080 or 21:9, and 1440 x 1080 or 4:3)

- [ ] O1. Briefing orders sheet, role banner, status card (under the radar), toast, `!roles` card (right), prompt at the ammo box. None overlaps CS2's chat, kill feed or team counter. Record: R (state + resolution).
- [ ] O2. Plotting board: map, markers on the board, ledger card readable; the status card hidden while it is up. Record: R.
- [ ] O3. Cockpit: five dials whose needles turn, altimeter and compass read-outs legible, rounds counter, bomb lamps. Record: R.
- [ ] O4. Fonts: serif and mono text renders (not a fallback font); long lines wrap inside their boxes. Record: R.

## P. Radar

- [ ] P1. At five places (a fire-trench post, a mortar pit, a dressing station, the woods ladder, the sap mouth) type `!pos`. Expect the dot in the grid square the line names. Record: R (the line + where the dot was).

## Q. Sounds and loops

- [ ] Q1. Officer's whistle about 1.5 s after round start, heard at full level everywhere. Record: R.
- [ ] Q2. Mortar launch, falling whistle and impact: levels against stock rifles; 3D position right. Record: R.
- [ ] Q3. Aircraft engine loop: no click at the seam (2 s loop). It stops cleanly when the flight ends. Guns sound every second round. Record: R.
- [ ] Q4. Soundscape: wind, distant drumfire, guns, MG, whistles, passing aircraft. Expect seamless loops, not too busy. Record: R.

## R. Loading screen

- [ ] R1. Loading `mg_trenchwarfare` shows the three map slides and the map icon (not stock). Record: R.

## S. Giant first-person weapons (with every uniform)

- [ ] S1. With uniforms on (default), check each of the four: T `tw_de_a`, `tw_de_b`, CT `tw_gb_a`, `tw_gb_b` (picked by player slot; spectate bots in first person to see the ones you are not wearing). Expect normal-size weapons. Record: R (which uniform fails).
- [ ] S2. `!uniform` off and on again in the briefing room, then as a pilot and back. Expect no giant weapon and no model change mid-field. Record: R.

## T. Model swaps

- [ ] T1. The Canon de 75 replaces the old 75 mm gun at (-2660, 900): it stands on its wheels and trail, faces as before, is solid and lit right, and has no LOD pop at range. Record: R.
- [ ] T2. LOD switches on the A7V, howitzer, SPAD and Dr.I (static and flying): no visible jump. Record: R.

## U. Workshop upload (after [WORKSHOP.md](WORKSHOP.md)'s pre-upload checklist)

- [ ] U1. Upload from the game addon. Expect the item to install on a clean client and the map to load with `host_workshop_map <id>` on a dedicated server. Record: R and [WORKSHOP.md](WORKSHOP.md).
- [ ] U2. On the dedicated server: the `[tw] perf:` line with 10+ humans. Record: R.

## Results

One row per failed or noted item. Answered rows stay, so a problem that comes back can be checked against them.

| Item | Date | Map CRC32 | Result | Console lines / `!pos` / note |
|---|---|---|---|---|
| | | | | |
