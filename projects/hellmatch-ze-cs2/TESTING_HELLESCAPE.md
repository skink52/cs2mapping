# Hellmatch ZE: in-game test checklist (mg_hellescape)

Load: `map mg_hellescape` from the tools build, then `bot_add` a few times (or `bot_quota 16`).

## Map and content
- [ ] Lobby, booth and cache room load; console shows the script's "ready" line with 6 ZE levels (12 placements) and the HUD "on".
- [ ] Both copies of every level are there (T and CT arenas): MAP01, E1M1, E3M1, MAP06, E1M4, MAP03; doors and lifts move in both, independently.
- [ ] Phase 1 levels (E1M1, E3M1, E1M4) show their own texture versions (switches, steps: the `_d1` materials) and MAP01/MAP06/MAP03 theirs.
- [ ] Animated surfaces (water, slime, scrolling wall in the start corridor) animate in both copies.
- [ ] Loading screens cycle: the main one, the overview, then one per level (title, author, stage list, automap with the zones);
      radar shows every copy labelled (T) / (CT).
- [ ] Music: the theme at round start, then the level's own track and Hellmatch's four tracks in play (the MAP01, E1M1, E3M1,
      MAP06, E1M4 and MAP03 renders are new and unheard: note any that sound wrong), a boss track (E1M8 / E2M8 / E3M8) in the boss stage.
- [ ] Console: once a minute "script time: avg X ms" (simulated: ~1.2 ms at 64 players); any "point_script ... thinking for" line.

## Round rules
- [ ] T players play the T copy, CT players the CT copy; the HUD shows the stage, hold seconds, humans alive per side, the clock.
- [ ] Die to a monster as a human: about a second later a CS2 death (world), then you are a demon in the OTHER team's copy, with
      "YOU ARE A ZOMBIE - HUNT THE ... HUMANS"; your CS2 team does not change.
- [ ] As a demon kill an enemy human: the killfeed credits you (a normal enemy kill); they become a demon in your old copy.
- [ ] Kill a demon player as a human: normal enemy kill; they come back as a demon after ~4 s behind the humans.
- [ ] Monsters ignore demon players; demons can't hurt the monsters; demons can't pick items up; shots push demons back.
- [ ] Wipe one side: the other side wins the CS2 round (round score ticks). Escape: that side wins at once.
- [ ] Join mid-round: human during the first stage hold, demon after it. Last human leaving the server: that side loses.

## Stages (ze/map01.json)
- [ ] 1 HOLD THE FLOODGATE: the east door (sector 56) stays shut and can't be opened until the 52 s hold is done; then it opens.
- [ ] 2 HOLD THE PUMP STATION: 59 s in the south-east corner by the pedestal; the stairs down are blocked until it is done.
- [ ] 3 DEFEAT THE TURBINE GUARDIAN: crossing the stairs spawns the pain lord in the turbine hall; its health grows with the humans alive.
- [ ] Killing it opens the turbine door (sector 161, slowly).
- [ ] 4 ESCAPE: 30 s in the exit alcove; demons pour in from the flooded cave; the side that finishes first wins.
- [ ] The north lift door and the back channel (south room to the flooded side) stay blocked all round.

## Stages (ze/e1m1.json, Outer Prison)
- [ ] The north door of the atrium (to the middle hall) and the two side cells stay shut all round.
- [ ] 1 HOLD THE SOUTH GATE: 52 s in the atrium's south-east part; the south door (sector 100) opens when it is done and the lift to the flooded hall (sector 103) goes down and stays down.
- [ ] 2 HOLD THE FLOODED HALL: 59 s in the water hall with the cages; then the cave door (sector 54) opens slowly.
- [ ] 3 SLAY THE CAVE SLUG: walking out of the cave mouth spawns the combat slug in the cave; you can't drop into the pit yet.
- [ ] Killing it opens the pit rim and the blue door north of the middle hall: drop in, run north through the blue wing.
- [ ] 4 ESCAPE: the blue doors and the exit chamber door open; 30 s in the octagon chamber (the exit switch does nothing).

## Stages (ze/e3m1.json, Land of the Lost)
- [ ] 1 HOLD THE STAIRS: 45 s on the stairs out of the blood pit; the stairs' top is shut until then, then the barrier (sector 9) sinks.
- [ ] The water shortcut from the pit to the west caves stays shut all round (also after crossing the west corridor's trigger).
- [ ] 2 HOLD THE TEMPLE PLAZA: 59 s on the plaza north of the temple; then the west caves open.
- [ ] 3 KILL THE CAVE SPIDER: entering the blood room spawns the technospider in the big cave below.
- [ ] 4 ESCAPE: killing it opens the exit gate (sector 100); 30 s in the exit room.

## Stages (ze/map06.json, Janus Terminal)
- [ ] The west doors of the hub stay shut all round; the blue gate north of the hub stays shut until the escape.
- [ ] 1 HOLD THE EAST GATE: 52 s by the east door of the hub; then the east door and the yellow door open.
- [ ] 2 HOLD THE PILLAR HALL: 59 s in the four-pillar hall; then the way to the stairs opens.
- [ ] 3 DESTROY THE TRIPOD: the top of the stairs spawns the assault tripod in the yard (check it is beatable with the
      humans' weapons and its health scaling; it may need a lower scale).
- [ ] 4 ESCAPE: the blue gate opens; run back through the hub and the north corridor; 30 s in the terminal exit room.

## Stages (ze/e1m4.json, Supply Depot; long level, about 9-12 min)
- [ ] The north-west door of the ring corridor, the yellow door west of the sludge rooms, the door north of the east room
      (up to the outdoor yard) and the east corridor past the walkway junction stay shut all round.
- [ ] 1 HOLD THE ENTRY HALL: the back door of the start room (sector 273) bursts open at round start; 50 s on the hall's
      sunken centre; then the east yellow door (sector 28) opens.
- [ ] 2 HOLD THE PILLAR HALL: down the east stairs, 60 s around the octagon pillar; the sludge pit (west side) is shut till then.
- [ ] 3 SLAY THE SLUDGE WARDEN: stepping onto the bridge or into the sludge spawns a pain bringer in the pit (the nukage hurts
      humans, not it). Killing it opens the north yellow door (sector 175).
- [ ] 4 HOLD THE NUKAGE WALKWAY: 60 s at the junction of the walkway and the east corridor; demons rush from the east corridor.
- [ ] 5 SLAY THE NUKAGE PAIN LORD: a pain lord spawns on the north walkway, between the humans and the blue door.
- [ ] 6 ESCAPE: the blue door (sector 188) and the exit door (sector 126) open; up the stairs, through the north hall, 30 s in the
      exit chamber. Falling into the nukage teleports you back onto the walkway (the level's own pads).

## Stages (ze/map03.json, Crude Processing Center; long level, about 10-13 min)
- [ ] 1 HOLD THE GALLERY: 50 s in the gallery south of the start room; then the blue door (sector 247) south of the east wing opens.
- [ ] 2 HOLD THE PUMP ROOM: 55 s in the room past the blue door; then the east gate (sector 46) opens.
- [ ] 3 KILL THE SLUDGE SOLDIER: entering the eight-pillar hall spawns a dark soldier (revenant). Killing it opens the south gate
      (sector 49) and starts the lift (sector 61) cycling so you can get back up out of the hall: check humans and bots ride it.
- [ ] 4 HOLD THE CROSSROADS: back through the hub, down the south stairs and through two doors; 60 s on the centre of the
      cross-shaped hall; demons rush down the north arm. Then the red door (sector 233) opens.
- [ ] 5 DESTROY THE REFINERY TRIPOD: through the column hall, ride the lift down to the core (one way); landing spawns the
      assault tripod in the core room.
- [ ] 6 ESCAPE: the north exit hall opens and the exit lift (sector 306) comes down; 30 s on it / in the room around it.

## Round 3: ammo and upgrades from the stage files
- [ ] Every finished hold gives the "resupply" (ammo share, health, some armour after the second hold); boss kills too.
- [ ] Upgrades (HUD "UPGRADE: ..."): MAP01 ssg + chaingun / rocket / plasma at the boss; E1M1 chaingun + chainsaw / rocket /
      plasma; E3M1 chaingun / rocket / plasma; MAP06 ssg + chaingun / rocket + plasma / BFG at the tripod; E1M4 chaingun +
      chainsaw / rocket (Phase 1 E1 has no plasma); MAP03 ssg + chaingun / rocket / chainsaw / plasma.
- [ ] "HERE THEY COME" surges: when the first gate of each level opens (a rush from behind), and at the walkway (E1M4) and
      crossroads (MAP03) holds from the flank.

## Classes and the boss (Phase 2)
- [ ] While dead / rising as a demon: R or right click = next class, F = previous; HUD "CLASS: IMP  [R] NEXT"; the pick sticks.
- [ ] Lunge (demon) and dash (deadflare) keep speed to the end and stop with a bump on walls; no seeing through walls as a deadflare.
- [ ] Boss stage: demons see "PRESS E TO BECOME THE BOSS" for 5 s; the first E near a demon spawn takes it; HUD health in percent;
      Mouse 1 melee, Mouse 2 / R the boss's missile; leaving / AFK / 10 s idle hands it back to the AI.
- [ ] A human killing a player boss gets the CS2 kill; humans killed by the boss player count as that player's kills.
- [ ] Bosses beatable: pain lord (MAP01), combat slug (E1M1), technospider (E3M1), assault tripod (MAP06, health capped);
      E1M4 pain bringer + pain lord, MAP03 dark soldier + assault tripod.

## Demons (zombie view art)
- [ ] Serpentipede: claw frames (idle, wind-up, swipe, follow-through) and the fireball between the hands.
- [ ] Flesh worm: the jaws frame the screen when idle, close on a bite, red on a lunge.
- [ ] Deadflare: flames at the screen edges, a flare, the dash streak.
- [ ] Frames sit like the weapons do (no gap at the bottom while bobbing; scale matches the pistol).
