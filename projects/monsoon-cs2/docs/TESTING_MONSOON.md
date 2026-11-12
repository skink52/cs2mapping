# mg_monsoon CS2 test: what to check

Each line says what to do and what to expect. **Only report what fails** (what you saw, where, the console lines if any):
anything you don't mention counts as passed. Version under test (playtest 2): **mv-0.7 (13 Nov 2026, playtest 1 batch G: era
weapons, requisition, armory)**, map build stage 5 (the playtest 1 fixes; nav areas in docs/BUILD_LOG_1.md "Stage 5") and the 3D
skybox after its triangle cut (1.93 M triangles, was 16.2 M). Start with "Playtest 2 checklist" below.

This is the first time any of it meets CS2. Until now: the map, the 3D skybox and the assets are **compiled** (no errors), the
script is **simulated** on a mock engine, the rest was checked offline. **NOT YET TESTED IN CS2**: every item below is an
assumption until you tick it. The order is the order to test in: a failure early (build, script start) makes the later sections
meaningless, so stop and report.

Which build: a **private-server build** has the converted Garry's Mod Workshop models (T Mi-8s, howitzers, M2 / DShK, vehicles,
Rising Storm foliage) and four GMod player models as team uniforms. A **public build** (`MV_NO_EXT=1`, no uniforms;
`docs/WORKSHOP_COMPLIANCE.md` in the source repository) has our procedural Mi-8, M102, mounts and wrecks instead, and players wear
CS2 agents. Say which one you tested; sections E, F, G and L differ between them.

Useful: `!pos` in chat prints your position and grid square: quote it for anything about a place. Console filter: every script
line starts `[mv]`. After copying new files: `disconnect`, then `map mg_monsoon` again.

## Playtest 2 checklist (the playtest 1 fixes, 13 Nov 2026)

The build after playtest 1: script **mv-0.7 (13 Nov 2026, playtest 1 batch G: era weapons, requisition, armory)**, map build stage 5
(docs/BUILD_LOG_1.md "Stage 5"). Every line below is **compiled** or **simulated** only; each is something only CS2 can confirm. The
records behind them: docs/FIX_PT1_S.md, FIX_PT1_W.md, FIX_PT1_G.md, FIX_PT1_P.md (finding numbers from docs/PLAYTEST_1.md in brackets).
Do this section first, then go on with the rest of the file as before. Report only what fails, with `!pos` for anything about a place.

Script start:
- [ ] Console on load names `mv-0.7 (13 Nov 2026, playtest 1 batch G: ...)`. An older version means a stale `.vjs_c`.
- [ ] The HUD stays up for everyone, including a player who joins while the round runs and the host. The per-minute `[mv] perf` line
      shows `HUD failures 0` or a small number, and flag owners / progress (finding 1).

Flags and capture (findings 1, 6):
- [ ] At map start every flag hangs white at the foot of its pole. Stand at a pole alone: the on-foot prompt reads
      "CAPTURING B BRIDGE 45 %" (rising), the owner's cloth runs down over the first half and yours runs up over the second, changing
      colour only at the foot. The capture takes about 15 s alone. A chat line announces it with the flag count. With an enemy in the
      circle the prompt says "CONTESTED"; standing on your own flag, "HOLDING".
- [ ] The cloth slides between poses (0.3 s fades) and reads as a flag being raised, not jumping; at the foot it is clear of the
      cairn and sandbags.
- [ ] `!help` (also `!commands`, `!cmds`, `!?`) shows the command card on the HUD and 5 lines in chat; `!controls` / `!keys` lists the
      keys for your seat, gun or battery; an unknown `!word` answers "Unknown command ... !help lists them".

Helicopters (findings 2, 4, 5):
- [ ] Apache rotors turn on take-off and spool up / down (the script fires `SetAnimationLooping spin` and `SetPlaybackRate`).
- [ ] The Mi-8 (both kinds) is solid from every distance and angle, no see-through hull panels at range; its shading looks right.
- [ ] Weapons: Apache pilot MOUSE1 rockets, and MOUSE2 the chin gun while the gunner seat is empty; Mi-8 slick pilot MOUSE1 nose
      machine gun; dirt puffs where rounds land; tracers every 2nd round; the gun / heat box on screen for a pilot gun; a toast that
      says why a trigger does nothing (on the ground, rockets empty, gunner has the chin gun). The seat card on boarding.
- [ ] Pilot guns feel usable (gimbal, rate of fire) and are not overpowered in a human match.

Sound (finding 7):
- [ ] The emplaced guns (bridge M2 and others) play CS2's own M249 report, one per round, loud enough at the bridge and not tinny.

World (findings 8-15):
- [ ] Tunnels: each entrance is a rounded cut with a lip and spoil heaps, a steep walkable shaft with log treads, no blocky pit; the
      ground patch meets the terrain with no seam or lighting step; galleries are smooth ovoids with timber frames that touch wall,
      floor and roof; no floating arches. Bots get through the shafts.
- [ ] Spawns: no T spawn (or any teleport point) stuck in the battery berms, the temple terraces, the temple DShK seat or the tunnels.
- [ ] Lighting: no hard horizontal line across the grass, reeds and rice near the river, and no pale band on the lower trunks of the
      palms and slim trees.
- [ ] Temple vines lie on the stone (tower cornice, gate, wall copings, east architrave): no vines hanging from poles in the air;
      the leaf cards' alpha looks right.
- [ ] Sandbags: the full-height walls at the bridge's south bank, the gun pits and the quad .50 ring look like filled bags laid in
      bond (GMod bag texture on each bag), follow the ground with no floating courses or gaps, work as cover, and their LODs hold
      up at distance.
- [ ] Water: you wade in the shallows and fords and swim in the deep channel (about 120 u); splashes; the river surface looks right
      from above and below; the underwater tint and exposure under the surface; no hard edge where the river crosses a light probe
      volume. The paddies are shallow water you walk through. Swim the whole river (upper reach above the fall too), the marsh and
      the oxbow: no stretch where you drop through to the bed as if there were no water (the volumes are now built from many
      pieces; a gap between pieces would show as a dry spot). No visible seams on the surface between the pieces.
- [ ] FPS looking along the river from the bridge and from the marsh edge (`cl_showfps 1`), compared with looking away from it: the
      water surface is now 482 separate pieces.
- [ ] Bots cross at the three fords and do not get stuck at the deep channel; they still reach flag B under the bridge. FPS with
      bots: the nav is 13,739 areas now (12,597 in playtest 1); send the `[mv] perf` line and FPS with 14+ bots.

Weapons and requisition (finding 19, batch G):
- [ ] Each side spawns with its era kit (US M16A1 / M60 / M79 / M14 / M1911, NVA AK / RPD / RPG-7 / SKS / TT-33 by class); the
      M1911, M14 and M21 models look right in first and third person with the stock animations (hands, op-rod handle, magazine on the
      reload). CS2's own kill feed still names the stock weapons (SCAR-20 for the M14): expected.
- [ ] REQ points: the REQ row on the HUD rises with kills, assists and captures. At a kit station, F (inspect) opens the armory card,
      even on a quick tap; `!armory` too. The frag pouch (one HE + one smoke), shotgun, carbine and sniper unlocks work; at most 1 in
      8 players has a sniper rifle at once.
- [ ] The M79's lob feels right; bots buy and use the frag pouch, scoped rifles and shotgun.
- [ ] A player who leaves and rejoins keeps his REQ (by name).

Props (findings 16-18, batch P):
- [ ] Prop textures are sharp up close: huts, the temple tower and gate, bunkers, tents, crates (was blurry and smeared). The
      thatch roofs read as layered thatch with fringes.
- [ ] Hay: rice-straw stacks, woven rice baskets and the ox-cart load look like straw, not plastic.
- [ ] Temple: the seated singha lions and the seven-headed naga balustrades look like weathered Khmer stone; their LODs at distance.
- [ ] FPS and VRAM: texture memory of the placed props rose from 338 to about 550 MiB. Watch FPS at 64 players and report VRAM if you
      can see it.

## Check these first (new since mv-0.1, none of it seen in CS2)

Script (review pass 2 and round 3; only CS2 can settle these):
- [ ] Console on load: `[mv] mg_monsoon script mv-0.7 (13 Nov 2026, playtest 1 batch G: era weapons, requisition, armory) - flags 5,
      bots on (quota 10)`. An older version string means a stale `.vjs_c`: recompile the `.js`.
- [ ] `[mv] points: ... uniforms cached 4` in a private build (0 in a public build). Private build: T players wear the NVA / Viet Cong
      soldiers, CT the woodland / US soldiers; first-person arms look normal; `!uniform` switches you back to the CS2 agent. Report
      two-handed weapons clipping into the chest (the conversions' torsos are bulkier than a CS2 agent's).
- [ ] Once a minute: `[mv] perf: X ms/tick avg, Y ms max, N ticks, H HUD calls/tick, P players (h human), F flying, ...,
      errors 0`. (The old `[mv] script time ...` wording is gone.) Send the line at the highest player count you reach.
- [ ] **Leaving players (`IsConnected`).** With bots on and an AI pilot flying, kick that bot (`bot_kick <name>`) or lower the quota.
      Expect another bot to take the AI pilot role within a few seconds, and nobody "owning" the empty helicopter for the rest
      of the round. Also: a bot that dies and respawns keeps its AI role (its helicopter / gun is not handed round every death).
      A human who disconnects from a gun or helicopter: the seat is free again for others.
- [ ] **Joining mid-round (`OnPlayerActivate`).** Join a running round (second client, or `retry`). Expect the briefing card and the
      whole HUD on screen once loaded, no empty boxes. After a round ends and restarts: no empty banner, toast or info panel left.
- [ ] **Bot takeover (`OnBotControl`), take and release.** Spectate a bot that is flying, gunning or crewing a battery and take
      it over, if CS2 offers it on this server. Expect: the bot's body full size and free to move, you play it as infantry where it
      stands, its helicopter / gun / board seat free. When that body dies (or the round ends), you are back to your own player
      and the bot rejoins normally. Report a shrunk or frozen body, a view stuck in the helicopter, or the takeover not offered.
- [ ] **Bots follow the flag plan.** Bot-only match (`!bots 24`, you spectating): bots of both teams spread over several flags
      rather than all running to one; CT bots go for B and C as well as D / E; every flag changes hands at least once in a round.
      Send the five flag owners at 5 and at 10 minutes. (The plan's own counters, `__mvDebug.stats.botGoals`, exist only on the
      mock engine; nothing prints them in CS2, so this check is by watching.)
- [ ] **Hot rotor on the pad.** An AI helicopter back on its pad for repair keeps its rotor turning and its engine sound running,
      then lifts off about 4 s after the repair with part of its rockets.
- [ ] **Pilotless helicopter over the river.** Bail out (or let a bot pilot be kicked) over the river: the empty helicopter
      should hold height and creep toward its pad, not drop into the water.
- [ ] **Helicopter fetched home.** Get killed in the air, redeploy on your pad: the empty helicopter that landed in the field
      comes back to your pad after about 3 s.
- [ ] **Helicopter handed over in the field.** Say `!air` while an AI pilot holds every helicopter, then walk out into the
      field. You are told the helicopter is yours and waiting on its pad; you are **not** teleported to it.
- [ ] **`!bots` vote.** With two or more humans, one `!bots 0` only starts a vote (`votes !bots 0: 1/2 ...`); bots stay until a
      majority agrees within 30 s.

Map (world passes 2 and 3, compiled, never looked at):
- [ ] Bots on the nav: bots walk the bases, flags, roads and the two routes (the west ford from the T camp to the paddies; CT's
      route down the north-west flank and across the river to the temple). Bots standing still in the jungle, the marsh, on karst
      tops or behind the waterfall should be re-deployed after about 20 s. Report a bot stuck longer, with `!pos`.
- [ ] Temple ghat: the landing and the two flights of steps from the river up to the temple's south stair are walkable both ways.
- [ ] Temple court: four balustrades, four lions, the supply crate in the south-east corner by the DShK.
- [ ] Village: the market lane with three stalls, two climbable drying platforms, no hut roof you can stand on. The one known
      small pocket at about (-1064, 1976): you can jump out.
- [ ] Firebase gate: the culvert bunker and the M113 outside the wire: you cannot climb onto the M113 and get stuck.
- [ ] FPS at 64 players: on a server with 64 (or the most you can get; bots alone stop at 24), `cl_showfps 1` looking across the
      valley from the firebase. Send the number and the `[mv] perf` line. VRAM if you can see it: the elephant grass is 109 MB of
      the map's 206 MB of aggregate vertex data.
- [ ] 3D skybox in game: the skyline from the CT firebase, the bridge, and a helicopter at the map edge. Is the front row of trees
      thick enough, do the far tree cards read as jungle (not flat billboards), is every karst tower base visible, no dark hedge
      line floating in the air? FPS looking at the valley sides compared with looking at the ground.

## A. Build log (before launching)

`C:\source1\cs2port\logs\mg_monsoon_assets.log` and `mg_monsoon_build.log`. Send the lines, not a summary.

- [ ] Assets: no `FAILED - these materials did not compile`. If there is one, send the list under it.
- [ ] The three hand compiles (`mg_monsoon.xml`, `.css`, `.js` with `resourcecompiler -f -i`) each print a compiled line and no error.
- [ ] Map: `OK in N min - mg_monsoon.vpk moved to ...`. Send N.
- [ ] Search the map log for `DELETED`. Expect none. Send every line that has it (the prop or entity name matters).
- [ ] Search for `Error loading resource`, `missing material`, `ERROR`. Send the lines that name a `.vmdl` or `.vmat`.
- [ ] Send the numbers from `Charting N unique meshes` and `Packing N UV charts`, and say whether the bake stayed at 2048.
- [ ] No `OUT OF MEMORY` / `FATAL ERROR`. If there is, send the 20 lines before it.
- [ ] Nav mesh area count (`Nav mesh (v36/1) loaded with N nav areas`): expect about 15,033. Send N.
- [ ] The 3D skybox is built by its own line, `build_maps.ps1 final "mg_monsoon mg_monsoon_3dskybox"`: its log ends
      `OK in N min - mg_monsoon_3dskybox.vpk moved`, about 56 MB.

## B. Hammer

- [ ] `maps/mg_monsoon.vmap` opens without an error dialog. Expect a river valley about 12800 x 10240 units, a hill base in the
      south-east, a jungle camp in the north-west, a lobby room below the map.
- [ ] `mv_script` (point_script) and `mv_hud` (custom_hud_layout): the file fields are not red.
- [ ] No ERROR models, no pink materials in the 3D view. Fly over both bases and the five flags.
- [ ] Double-sided sheets, each from both sides (black speckle or one side missing = fail): the flags on the flag poles,
      parachute silk at the crash site, the big tents, vine curtains, the supply crate tarps.
- [ ] Terrain under the six firebase bunkers: holes were cut for their floors. No gap you can see through from outside.
- [ ] The three tunnel mouths (camp, toward the paddies, toward the village): ramp meets ground, no see-through crack, about a 6-unit step.
- [ ] The Apaches on the firebase pads: standing on the pad, not sunk or floating, not wider than the pad by much. Send a screenshot.
- [ ] The Mi-8s on the T pads (no nets over them now): rotor and tail rotor props sit on the hubs; wheels on the ground; on pad 2
      the tail boom overhangs lower ground (known).
- [ ] Private build: the M101 tubes sit on their trunnions, the M2 / DShK guns on their pintles behind the sandbag horseshoes, the
      M35 sits on its axles (it has no wheels, by design), the PBR floats at the marsh.

## C. First run, alone (`map mg_monsoon`, then `!bots 0` in chat)

- [ ] Console: `[mv] mg_monsoon script mv-0.5 (12 Nov 2026, review pass 3: bot balance) - flags 5, bots on (quota 10)`.
- [ ] Console: `[mv] points: spawns 16/16, helicopters 3/3, guns 4/3, mounts 8, uniforms cached N` (N 4 private, 0 public)
      and `[mv] round 1 start (...)`. Send the line if any number differs.
- [ ] No `[mv] missing entity <name>` lines. Send every one.
- [ ] No `[mv] error in ...` lines, ever, in any section. Send every one with what you were doing.
- [ ] You spawn in the briefing room with a card: role, three lines, `DEPLOY: BASE  [R] next`, a countdown from 10.
- [ ] R during the countdown changes the deploy line (only "BASE" until your team holds a flag).
- [ ] At zero you are at your base, a banner shows and fades, weapons in hand: rifle + pistol for the rifleman kit.
- [ ] HUD in place and nothing overlapping CS2's own HUD: objective bar top centre under the round timer (five flag badges, two
      ticket numbers and bars, a clock); status box on the left under the radar; nothing of ours over the chat (bottom left) or
      the kill feed (top right).
- [ ] The radar shows the valley and your arrow is where you are (stand on the bridge: the arrow is on the bridge).
- [ ] Loading screen showed the map's own slides (three) and the map icon.
- [ ] After a minute: `[mv] perf: X ms/tick avg, Y ms max, ... 1 players (1 human), ... errors 0`. Send the line.
- [ ] `!roles` shows the role card on the right; `!pos` prints a position and a grid square in chat.

## D. Infantry

- [ ] Arms rack at your base: prompt `[E] Kit: RIFLEMAN  ->  MACHINE GUNNER`. E changes kit and weapons. `!rifle`, `!mg`, `!at` do the same.
- [ ] Anti-tank kit: you hold a Zeus. Fire it at ground 30 m away. Expect a rocket prop flying, an explosion, the toast
      `M72 LAW away - reloading 25 s` (or RPG-7), and a new Zeus after 25 s. Report if the Zeus fires as a normal Zeus with no rocket,
      or never comes back.
- [ ] Fire mission: look at open ground more than 400 units away, hold E. Expect a bar `CALLING FIRE MISSION` filling in about 1.2 s
      and a ring marker on the ground there. Report if E opens something else or the bar never starts.
- [ ] Flag capture: walk to flag B (on the bridge deck). Expect the B badge to grow a ring under the bar with a 10-step arc,
      the flag pole's flag to change to your team's colour when it completes (about 15 s alone), a horn sound, and the badge colour to change.
- [ ] Killed and respawned: `!spawn b` then die. Expect the next deploy at B (briefing card says so), 5 s countdown.
- [ ] Guard tower at the firebase: can you climb the ladder and stand on the platform? (Known suspect: 50 units of headroom.)
- [ ] Temple tower and its stairs: climbable, no invisible wall on the stairs.
- [ ] Tunnels: walk all three portals to the chamber. Lit by lamps, no black void, no getting stuck, no falling through.
- [ ] River: wade across at the bridge ford, at A and at the marsh. You never need to swim. Anywhere you get stuck: `!pos`.
- [ ] Karst towers: try to walk up one from the ground. Expect an invisible wall. Report if you can climb one.
- [ ] Map edge: walk into the jungle at the edge. Expect an invisible wall before the terrain ends, never a fall out of the world.

## E. Helicopters (`!air`, wait for the next deploy, or respawn)

Do the CT Apache first, then switch team and do the T Mi-8.

- [ ] You deploy at a pad and sit in the helicopter; the view is a chase camera behind and above it; your own player model is not visible.
- [ ] Rotors: Apache blades start turning (animation); Mi-8 rotor and tail rotor props spin and stay on their hubs, on the pad
      as well as in flight.
- [ ] Mi-8 seats (they were measured from the model, never seen with a player): the pilot in the left cockpit seat, the door
      gunner at the open left door, riders on the cabin floor; nobody sticking out of the fuselage. Gunship (pad 3): rockets
      leave from the six pods on the outriggers.
- [ ] SPACE lifts off. Releasing everything holds a steady hover (no drift up or down after 2 s).
- [ ] Mouse turns the nose; W tilts the nose **down** and moves forward; A / D roll **toward** the side you move to.
      Report a tilt that goes the wrong way (which key, which way).
- [ ] The Apache's nose points where you fly (not sideways or backwards). Same for the Mi-8.
- [ ] Camera: smooth at speed, no jitter, never inside the helicopter or under the ground. Report jitter with rough speed.
- [ ] Instruments bottom centre: horizon card rolls and pitches with the helicopter and stays inside its round window;
      airspeed, altimeter and vertical-speed needles move the right way (climb = vertical-speed needle clockwise from 9 o'clock);
      heading tape at the top slides and reads 000 flying north (toward the village from the bridge). Screenshot in a banked turn.
- [ ] Fly into a tree and a karst tower slowly: expect damage on the airframe bar and a bounce, not flying through. Fly through the
      bridge truss: report what happens.
- [ ] Land on flat ground level and slow: it settles on its skids / wheels with no damage, E gets you out next to the helicopter (not inside it, not under the map).
- [ ] Land hard or tilted: crash damage. At 0 health: spin, fall, explosion, you die, a wreck and smoke stay about 40 s, a new
      helicopter is on the pad 45 s later.
- [ ] Back on your own pad for 8 s: airframe bar full; the info line under the instruments says so.
- [ ] Gunship (CT any Apache, T pad 3): MOUSE1 fires rocket pairs from the pods (not from the middle of the fuselage), the counter
      `RKT 28` counts down, rockets explode on the ground. Re-arm on the pad.
- [ ] Fly out of the map on purpose: the nose is turned back; far outside destroys the helicopter. No way out of the world.
- [ ] Second player (or ask a friend): E at the landed helicopter boards (prompt `[E] Board the AH-64 (gunner)`); the gunner's
      camera looks along the gun, MOUSE1 fires tracers, the heat bar bottom right fills and locks with OVERHEAT. `!swap` moves to
      a rider seat. E at low hover = fast-rope: placed below the helicopter, lands unhurt. E from high up = fall damage.
- [ ] Riders on the Apache's stub wings: do they look attached while it flies, or do they lag / jitter? Screenshot from outside.
- [ ] Shoot an enemy helicopter with a rifle from the ground: its health drops (the pilot sees the bar fall). If rifle fire
      does nothing while the mounted guns work, say so: that is the bullet-impact question in section N.
- [ ] Shoot a teammate's helicopter and stand under a friendly one landing: nobody inside takes damage; console may print
      `[mv] blocked N damage to aboard ...` (expected).
- [ ] Helicopter rotor sound follows the helicopter and is audible from about a third of the map away; it stops when the engine stops.

## F. Artillery (`!artillery`)

- [ ] You deploy at the battery. CT: three howitzers in sandbag pits around the FDC bunker. T: four rocket launchers in berms.
- [ ] Ammo rack: prompt `[E] Take HE   [MOUSE2] next type` (CT). E picks up a shell (you walk slower); MOUSE2 cycles HE / WP SMOKE / BEEHIVE.
- [ ] Breech: `[E] Load HE`. T side: load two, three, four rockets; a rocket prop appears on the rail.
- [ ] Plotting table: `[E] Plotting board` opens a full-screen north-up map with a reticle; your pawn stays put; WASD moves the
      reticle (SHIFT fine); the read-outs on the right change (RANGE, GRID).
- [ ] MOUSE1 locks: lamp goes LAYING then LAID, the gun barrel **visibly turns and elevates** toward the target (look from
      outside with a second player or after leaving the board). Report a gun that points the wrong way or a barrel detached from the carriage.
- [ ] SPACE fires: recoil, muzzle effect, a loud shot heard across the map, a whistle about 2 s before the impact, an explosion at
      the target, an impact marker on the board. Fire at flag B from the base and watch from there with a second player if possible.
- [ ] Accuracy: ten rounds at one spot. Expect impacts scattered within roughly 100-200 units at mid range, none kilometres off.
- [ ] WP smoke: a smoke screen about 400 units wide for 25 s. Does it actually block the view?
- [ ] Beehive (CT): lock a target inside 900 units of the gun, fire: direct cone, kills at the wire.
- [ ] T salvo: four rockets leave about 0.8 s apart and land spread wider than the howitzer.
- [ ] Fire mission from section D appears on the board as a mark; R selects it; the line `MISSION 1/1 ...` shows the caller.
- [ ] Counter-battery: have the other team fire; about 3 s later a flash mark shows on your board for 12 s.
- [ ] Hit an enemy gun (shell within 260 units): it smokes, its crew is thrown off the board, board says DISABLED with a countdown;
      a teammate holding E on it for 6 s (bar `REPAIRING`) brings it back.
- [ ] Killing with a shell: the kill feed names the gunner; send what the feed and scoreboard show for the loader and for the
      player who called the mission.
- [ ] Leaving the board (E) gives the normal view and movement back.

## G. Mounted guns

All eight: three M2s on the firebase wall, the quad-50 ring, two DShKs at the camp, the M2 at the bridge's south bunker, the DShK
in the temple courtyard.

- [ ] Prompt `[E] Man the M2 .50 CAL` standing behind it. E: camera behind the gun, your body hidden, the gun model turns with the mouse.
- [ ] MOUSE1 fires with tracers and sound; hits kill; about 6 s of fire shows OVERHEAT; 4 s later it fires again.
- [ ] E leaves and puts you behind the gun, standing, not stuck in sandbags.
- [ ] An enemy cannot man a base gun; either team can man the bridge and temple guns.
- [ ] Each gun's cone covers something useful (not a sandbag wall in the face). Name any gun that is blocked.

## H. Conquest and round end

- [ ] Tickets: a death takes 1 from that team. Holding 3 flags makes the enemy's number blink and fall by 1 every 3 s.
- [ ] Two teams inside one flag: the badge blinks CONTESTED and the progress freezes.
- [ ] Round end by tickets (hold 5 flags, or wait): banner with the winner; console `[mv] round over: ...`. Then **one** of:
      a normal CS2 round end and new round (best); or after 20 s `[mv] no new round 20 s after TerminateRound: firing
      FireWinCondition at mv_params`; or after 40 s `[mv] still no new round: the script restarts its own`. Send which lines appeared.
- [ ] Does the team score on the scoreboard go up for the winner?
- [ ] New round: helicopters back on pads, guns reset, flags neutral, tickets 400, everyone through the briefing room.
- [ ] The 20-minute clock on the objective bar counts down and ends the round at 00:00.

## I. Bots (`!bots 14`, you alone on one team)

- [ ] Bots join both teams, deploy from the briefing room and walk toward flags. They do not stand in the lobby or spawn in the ground.
- [ ] Do bots walk on the roads and valley floor only? Report bots climbing steep slopes, stuck in the river, in the paddies, or
      at a tunnel mouth (`!pos` near them).
- [ ] With you as the only human on your team: within a minute a bot-flown helicopter takes off from each base, patrols, comes
      back to the pad when damaged. Watch one full circuit. Report crashes into terrain, karst or trees (where).
- [ ] The bot pilot's body: invisible / parked in the helicopter, not running around on the pad or shooting from the seat.
- [ ] Bot gunners fire at enemies from helicopters and mounted guns; bot battery crew fires at your marks and at groups of enemies.
- [ ] `!air`: you get a helicopter although the bot had one (the bot gives it up at your next deploy).
- [ ] FPS with 14 and with 24 bots (`cl_showfps 1`), looking across the valley from the firebase. Send both numbers and the
      `[mv] perf` line. (The sibling map lost FPS with 44k nav areas; this one has 15,033.)
- [ ] Bots capture flags and tickets drain: a round can end with only bots playing.

## J. HUD details (the constructions with no earlier in-game example)

- [ ] Horizon: the card stays clipped to its round window while rolling; no square corners showing.
- [ ] Heading tape: clipped to its window (no tape hanging outside left or right).
- [ ] Bars (tickets, hold, heat, airframe): the fill stays inside the track at every value.
- [ ] Blinking items (bleeding tickets, CONTESTED, RTB lamp, OVERHEAT) blink; if they are static but visible that is acceptable, say so.
- [ ] Board markers land where they should: lock the reticle on the bridge and check the impact marker is on the bridge on the board.
- [ ] At 2560 x 1080 or 1440 wide if you can: nothing off-screen.
- [ ] Text is readable over bright sky and dark jungle.

## K. Sound

- [ ] Ambience in the valley: cicadas, birds, river, far thunder and guns. Not silent, not deafening against footsteps.
- [ ] Levels against stock weapons: howitzer and rocket fire loud across the map but not painful next to the gun; impacts audible from the other base.
- [ ] The capture / flag-lost horns play for everyone at the same volume: too loud far from the action?
- [ ] No looping sound that clicks once per loop (rotor, turbine, cicadas, river).
- [ ] No sound stuck on after a helicopter is destroyed or a round ends.

## L. World

- [ ] Rain over the five flags and the two bases: visible, and FPS under it compared with outside it.
- [ ] Lightning: a faint flash now and then. Is it also visible in the tunnels and the briefing room? (Expected, tell us if it is distracting.)
- [ ] Fog: thick on the valley floor, clear on the hills; you can still see a helicopter across the valley.
- [ ] 3D skybox: jungle hills and far karst towers continue past the terrain edge with no gap or seam. Frame time looking at
      the valley sides (the skybox's banyans have no cheap far model; past the front row they are 8-triangle tree cards now).
- [ ] Waterfall at the west end: water sheets, foam, sound; cannot walk through the rock.
- [ ] Props floating or sunk on slopes: note the worst ones with `!pos`.
- [ ] Foliage cards with a straight bottom edge showing on steep ground: where it is bad.
- [ ] Grass and reeds do not block bullets or movement; trees do.
- [ ] Bunkers are solid blocks by design in this version (you cannot enter them): anything that looks enterable but is not, name it.

## M. Multiplayer (when two or more people can join)

- [ ] Another player's helicopter moves smoothly for you (no stutter) and its riders stay attached.
- [ ] Kill credit in the kill feed for: rifle, mounted gun, helicopter rocket, door gun, shell, anti-tank rocket, helicopter crash
      (the last attacker within 10 s gets it).
- [ ] 64 spawns: nobody spawns inside another player in the briefing room.
- [ ] `[mv] perf` line at the highest player count you reach. Under about 5 ms is comfortable.

## N. Engine questions only a real run can answer

Answered items stay here (the -> lines), so a problem that comes back can be checked against them.

1. **Does `GameRules.TerminateRound` end the round with `mp_ignore_round_win_conditions 1`, and does `AddTeamScore` show on the scoreboard?** Section H.
2. **Does `SetAnimation` (`idle` / `spin_slow` / `spin`) drive the Apache as a `prop_dynamic`?** Section E, rotors.
3. **Does `Skin` on the flag pole switch neutral / T / CT?** Section D, capture.
4. **Do particle systems re-trigger on `Start` after `Stop`?** Second explosion at the same pool slot, helicopter dust, damage smoke.
5. **Is a parked pawn (`MOVETYPE_NONE`, scale 0.02) moved every tick stable under the follow camera, and does the camera come back when leaving?** Section E.
6. **What do CS2 bots do while parked in a seat?** Section I.
7. **Does `OnGunFire` fire for `weapon_taser`, and can the Zeus be re-given?** Section D.
8. **Do bullets reach `OnBulletImpact` with the helicopter as the hit entity?** Section E, rifle fire.
9. **Do the loader's slow walk, the rope's capped fall and `pawn.Reset()` (script-restarted round) behave?** Sections F, E, H.
10. **Is the damage share shown as an assist for the loader and the observer?** Section F.
11. **AI flight over real terrain**: altitude holds over hills and karst, no ground strikes. Section I.
12. **Do `func_nav_markup` NONAV boxes (key `navProperty_NavGen NONAV`) cut the nav mesh?** Build log area count, section I.
    -> COMPILED 12 Nov 2026 (not in-game): 243 boxes took the compile from 33,661 to 15,033 nav areas, so the markup acts at
    nav generation. How bots move on it is still section I.
13. **Does the invisible ladder volume on the guard tower and temple tower work?** Section D.
14. **Do multi-hull converted models and SMD material names ending in `.vmat` compile?** Build log (only matters for the converted models).
    -> COMPILED 12 Nov 2026: asset run 4 had 0 errors and 0 warnings. Whether the hulls collide as meant is section L.
15. **Is the lightmap chart count within 2048?** Build log. -> COMPILED 12 Nov 2026: the bake stayed at 2048 x 2048 with no OOM.
16. **Does `Instance.OnBotControl` fire on take and on release, and do `GetControlledBotPawn` / `GetOriginalPlayerController`
    answer as assumed?** "Check these first".
17. **Does a departed controller report `IsConnected()` false, and a dead bot between lives `true`?** "Check these first".
18. **Does `OnPlayerActivate` fire after the client's HUD is ready, and does `ResetForPlayer` clear dialog variables?** "Check
    these first" (mid-round join, round restart).
19. **Does the helicopter's ground trace see the river as water** (it tests "the trace ends below `water_z`")? "Check these first",
    pilotless helicopter over the river.

## Known unknowns (only CS2 can answer)

- Flight feel: every number in `CONFIG.HELI` is a first guess tuned on a mock with no rendering.
- Seat, gun-muzzle and rocket-pod positions on the Apache are measured from its geometry by heuristics; the Mi-8's come from the generator.
- Interpolation of script-moved props and of players carried by them, as other clients see it.
- Translucency sorting of rain, smoke, camouflage nets and foliage cards against each other and the water.
- Sound position relative to the chase camera rather than the parked pawn.
- Panorama features used here for the first time in this repo: rotation plus `scale3d` inside a clipping window, a flow-right child
  wider than its parent, `overflow: clip` on bar tracks, quoted `@keyframes`.
- Server cost of the script and of the nav mesh with bots: the 0.1 ms per tick figure is from the mock.
- Not driven even on the mock: Beehive, the marksman kit, a human repairing a gun, several fire missions or flashes on the board at once.
- Bot-only balance: the mock's T win rate is 49 % over 80 rounds, but the plan acts only through deploy points and real CS2 bots
  do not walk to flags the way the mock's stand-ins do. Flags C and D are the weak ones in the mock (taken by both sides in 55-65 %
  of bot rounds).
- Route balance: the C-E routes are 1.11 to 1 against CT (the CT deploy point sits behind gun pit 1); whether players feel it.
- The full list of script calls not yet seen in CS2: `docs/SCRIPT.md` "Not yet tested in CS2" and `docs/REVIEW_SCRIPT_2.md`
  sections 6 and "Round 3" 4, in the source repository.
