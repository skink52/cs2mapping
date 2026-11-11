# mg_monsoon CS2 test: what to check

Each line says what to do and what to expect. **Only report what fails** (what you saw, where, the console lines if any):
anything you don't mention counts as passed. Version under test: **mv-0.1 (11 Nov 2026)**.

This is the first time any of it meets CS2. Until now: map, models, HUD and sounds checked offline; the script **simulated**
on a mock engine. Every item below is an assumption until you tick it. The order is the order to test in: a failure early
(build, script start) makes the later sections meaningless, so stop and report.

Useful: `!pos` in chat prints your position and grid square: quote it for anything about a place. Console filter: every script
line starts `[mv]`. After copying new files: `disconnect`, then `map mg_monsoon` again.

## A. Build log (before launching)

`C:\source1\cs2port\logs\mg_monsoon_assets.log` and `mg_monsoon_build.log`. Send the lines, not a summary.

- [ ] Assets: no `FAILED - these materials did not compile`. If there is one, send the list under it.
- [ ] The three hand compiles (`mg_monsoon.xml`, `.css`, `.js` with `resourcecompiler -f -i`) each print a compiled line and no error.
- [ ] Map: `OK in N min - mg_monsoon.vpk moved to ...`. Send N.
- [ ] Search the map log for `DELETED`. Expect none. Send every line that has it (the prop or entity name matters).
- [ ] Search for `Error loading resource`, `missing material`, `ERROR`. Send the lines that name a `.vmdl` or `.vmat`.
- [ ] Send the numbers from `Charting N unique meshes` and `Packing N UV charts`, and say whether the bake stayed at 2048.
- [ ] No `OUT OF MEMORY` / `FATAL ERROR`. If there is, send the 20 lines before it.
- [ ] Send the nav mesh area count if the log prints one.
- [ ] Does the log mention `mg_monsoon_3dskybox`? (Is the skybox map built with the main map?)

## B. Hammer

- [ ] `maps/mg_monsoon.vmap` opens without an error dialog. Expect a river valley about 12800 x 10240 units, a hill base in the
      south-east, a jungle camp in the north-west, a lobby room below the map.
- [ ] `mv_script` (point_script) and `mv_hud` (custom_hud_layout): the file fields are not red.
- [ ] No ERROR models, no pink materials in the 3D view. Fly over both bases and the five flags.
- [ ] Double-sided sheets, each from both sides (black speckle or one side missing = fail): the flags on the flag poles,
      camouflage nets over the Mi-8 stands, parachute silk at the crash site, the big tents, vine curtains, the supply crate tarps.
- [ ] Terrain under the six firebase bunkers: holes were cut for their floors. No gap you can see through from outside.
- [ ] The three tunnel mouths (camp, toward the paddies, toward the village): ramp meets ground, no see-through crack, about a 6-unit step.
- [ ] The Apaches on the firebase pads: standing on the pad, not sunk or floating, not wider than the pad by much. Send a screenshot.
- [ ] The Mi-8s under the nets: rotor and tail rotor props sit on the hubs.

## C. First run, alone (`map mg_monsoon`, then `!bots 0` in chat)

- [ ] Console: `[mv] mg_monsoon script mv-0.1 (11 Nov 2026) - flags 5, bots on (quota 10)`.
- [ ] Console: `[mv] round 1 start (...)` then `[mv] points: spawns 16/16, helicopters 3/3, guns 4/3, mounts 8, uniforms cached N`.
      Send the line if any number differs.
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
- [ ] After a minute: `[mv] script time X ms/tick avg, Y max over N ticks, 1 players, errors 0`. Send the line.
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
- [ ] Rotors: Apache blades start turning (animation); Mi-8 rotor and tail rotor props spin and stay on their hubs.
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
      script-time line. (The sibling map lost FPS with a huge nav mesh.)
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
      the valley sides (banyans at skybox scale have no cheap far model).
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
- [ ] `[mv] script time` line at the highest player count you reach. Under about 5 ms is comfortable.

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
13. **Does the invisible ladder volume on the guard tower and temple tower work?** Section D.
14. **Do multi-hull converted models and SMD material names ending in `.vmat` compile?** Build log (only matters for the converted models).
15. **Is the lightmap chart count within 2048?** Build log.

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
