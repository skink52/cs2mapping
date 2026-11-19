# Hellmatch ZE: in-game test checklist (mg_hellescape)

Load: `map mg_hellescape` from the tools build, then `bot_add` a few times (or `bot_quota 16`).

## Map and content
- [ ] Lobby, booth and cache room load; console shows the script's "ready" line with 4 ZE levels (8 placements) and the HUD "on".
- [ ] Both copies of every level are there (T and CT arenas): MAP01, E1M1, E3M1, MAP06; doors and lifts move in both, independently.
- [ ] Phase 1 levels (E1M1, E3M1) show their own texture versions (switches, steps: the `_d1` materials) and MAP01/MAP06 theirs.
- [ ] Animated surfaces (water, slime, scrolling wall in the start corridor) animate in both copies.
- [ ] Loading screens cycle: the main one, the overview, then one per level (title, author, stage list, automap with the zones);
      radar shows every copy labelled (T) / (CT).
- [ ] Music: the theme at round start, then the level's own track and Hellmatch's four tracks in play (the MAP01, E1M1, E3M1
      and MAP06 renders are new and unheard: note any that sound wrong), a boss track (E1M8 / E2M8 / E3M8) in the boss stage.
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

## Classes and the boss (Phase 2)
- [ ] While dead / rising as a demon: R or right click = next class, F = previous; HUD "CLASS: IMP  [R] NEXT"; the pick sticks.
- [ ] Lunge (demon) and dash (deadflare) keep speed to the end and stop with a bump on walls; no seeing through walls as a deadflare.
- [ ] Boss stage: demons see "PRESS E TO BECOME THE BOSS" for 5 s; the first E near a demon spawn takes it; HUD health in percent;
      Mouse 1 melee, Mouse 2 / R the boss's missile; leaving / AFK / 10 s idle hands it back to the AI.
- [ ] A human killing a player boss gets the CS2 kill; humans killed by the boss player count as that player's kills.
- [ ] Bosses beatable: pain lord (MAP01), combat slug (E1M1), technospider (E3M1), assault tripod (MAP06, health capped).

## Demons (zombie view art)
- [ ] Serpentipede: claw frames (idle, wind-up, swipe, follow-through) and the fireball between the hands.
- [ ] Flesh worm: the jaws frame the screen when idle, close on a bite, red on a lunge.
- [ ] Deadflare: flames at the screen edges, a flare, the dash streak.
- [ ] Frames sit like the weapons do (no gap at the bottom while bobbing; scale matches the pistol).
