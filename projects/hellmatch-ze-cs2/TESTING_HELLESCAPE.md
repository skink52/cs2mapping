# Hellmatch ZE: in-game test checklist (mg_hellescape)

Load: `map mg_hellescape` from the tools build, then `bot_add` a few times (or `bot_quota 16`).

## Map and content
- [ ] Lobby, booth and cache room load; console shows the script's "ready" line with 2 levels and the HUD "on".
- [ ] Both copies of MAP01 are there (T and CT arenas); doors and the lift move in both, independently.
- [ ] Animated surfaces (water, slime, scrolling wall in the start corridor) animate in both copies.
- [ ] Loading screen says HELLMATCH ZE and credits the level; radar shows both copies labelled (T) / (CT).
- [ ] Music: the theme at round start, then MAP01's track and Hellmatch's four tracks in play (MAP01's render is new and
      unheard: drop it if it sounds wrong), the boss track in the boss stage.
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
- [ ] 1 HOLD THE FLOODGATE: the east door (sector 56) stays shut and can't be opened until the 40 s hold is done; then it opens.
- [ ] 2 HOLD THE PUMP STATION: 45 s in the south-east corner by the pedestal; the stairs down are blocked until it is done.
- [ ] 3 DEFEAT THE TURBINE GUARDIAN: crossing the stairs spawns the pain lord in the turbine hall; its health grows with the humans alive.
- [ ] Killing it opens the turbine door (sector 161, slowly).
- [ ] 4 ESCAPE: 20 s in the exit alcove; demons pour in from the flooded cave; the side that finishes first wins.
- [ ] The north lift door and the back channel (south room to the flooded side) stay blocked all round.

## Demons (zombie view art)
- [ ] Serpentipede: claw frames (idle, wind-up, swipe, follow-through) and the fireball between the hands.
- [ ] Flesh worm: the jaws frame the screen when idle, close on a bite, red on a lunge.
- [ ] Deadflare: flames at the screen edges, a flare, the dash streak.
- [ ] Frames sit like the weapons do (no gap at the bottom while bobbing; scale matches the pistol).
