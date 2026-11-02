# Space Racer for CS2 — design

A 32-car anti-gravity racing minigame that runs entirely inside one Counter-Strike 2 map as a cs_script
(JavaScript), with no server plugins. Up to 64 players in two 32-car arenas. 2.5D: huge neon tracks seen from a
chase camera, cars drawn as voxel models, in the style of the FreeDM and bomb-arena addons.

The look is **retro**: everything is drawn in one original 32-colour palette with chunky, dithered pixels
(`tools/retro.py`) - the roads, the pixel-art skies, the cities and asteroids, the HUD (an original 8x8 pixel font,
`tools/pixfont.py`), the loading screen - and every sound and the music is chiptune, synthesised from the four voices
of an old sound chip (`tools/sounds.py`).

Everything here is original: the name, cars, tracks, art, sounds and rules are ours. Nothing is taken from
F-Zero or any other racing game (see `WORKSHOP_COMPLIANCE.md`). The genre conventions we do use (anti-grav
racers, boost pads, drafting, laps) are not anyone's property.

## The pitch

Thirty-two cars line up on a glowing track hanging in space over a pixel city or an asteroid belt. Two or three
long laps. Every car has a **shield** (its health)
and a **charge** meter (its boost). Boost pads on the racing line give free speed; **charge platforms** sit on
slower side lanes and refill your charge and shield, so the race is a constant choice between the fast line and
the refill detour. Cars bump, ram and spin-attack each other; a car whose shield hits zero is **wrecked** and out.
Once a lap the **Pulse** sweeps the track from the back of the pack and tops up everyone it overtakes, so the
field never strings out and a bad start is never the end.

When the chequered flag drops the CS2 scoreboard settles up: the winner is credited with half the losers as
kills, second place with 30%, third with 20% — and the CS2 round goes to the side (T or CT) with more cars in the
top 8.

## Cars

Every player picks one of four cars; the choice is remembered between rounds and can be changed any time you are
not racing. The car picker comes up by itself only until you have chosen (A / D in the picker, or `!car 1-4`) or
raced once - in the lobby and as small cards on the grid - so it never covers the results. After that `!car` (or
`/car`, `!pick`) brings it back for 6 seconds (every A / D press keeps it up), and `!car 1-4` or a car's name picks
straight away; A / D only change the car while the picker is on screen. The cars differ in feel and in one
signature perk. Nobody gets more total "stat"; they trade speed for armour and so on.

| | HORNET | METEOR | COMET | BASTION |
|---|---|---|---|---|
| Style | light, agile | heavy, rams | boost specialist | tank, team player |
| Top speed (u/s; x0.36 = km/h) | 1620 | 1646 | 1596 | 1599 |
| Acceleration | 928 | 776 | 761 | 798 |
| Turning | sharpest | widest | medium | medium |
| Shield | 108 | 110 | 110 | 115 |
| Mass (bumps, spin shoves) | 1.0 | 1.6 | 1.0 | 1.3 |
| Charge capacity | 100 | 100 | 130 | 100 |
| Boost strength | +32% | +28% | +38% | +33% |
| Spin attack cost | 18 | 30 | 30 | 30 |
| Perk | **Drift charge**: drifting (hold Space) fills charge twice as fast; cheap spin attack | **Ram**: contact deals 1.8x damage to the other car and the Meteor takes 1/1.8; 1.6x mass, so it shoves | **Afterburn**: boost pads last 38% longer; charge platforms fill it 30% faster | **Slipstream**: drafting behind any car fills charge at double rate and repairs the shield; teammates drafting *it* get the convoy bonus |

The numbers are tuned in `test/sim.cjs` (`node test/sim.cjs 64 100 even,seed=71`: bot races with the same number
of each car) towards one shape: the light, fast cars win a little more often, the heavy ones wreck more rivals and
finish in the top 8 more steadily. 18 Oct, 1,200 races of 32 (400 each at bot skill 0.25, 0.5 and 0.85; the
table is the average of the three; 3,600 races in all went into the tuning):

| per 100 starts | HORNET | METEOR | COMET | BASTION |
|---|---|---|---|---|
| wins | 3.3 | 2.8 | 3.8 | 2.6 |
| podiums | 9.3 | 9.1 | 9.2 | 10.0 |
| top 8 | 22 | 25 | 21 | 32 |
| average place (of 32) | 18.0 | 15.3 | 18.3 | 14.4 |
| wrecked | 18 | 0.5 | 18 | 0.3 |
| rivals wrecked (KO) | 4.8 | 13.4 | 6.3 | 10.7 |

(An even share would be 3.1 wins and 9.4 podiums per 100 starts.) About 3 wrecks a race, nearly all of them
knock-outs. The light cars are boom or bust (more wins, wrecked in about 1 race in 5); the heavy ones are steady
(the Bastion makes the podium and the top 8 most often) and do the wrecking. Run-to-run noise at this size is
about +-0.3 wins per 100, and top speed is very sensitive (a few units/s moves a car's wins by 1 per 100). Tune in `CARS`
in `src/core/00_defs.js`.

Speeds are CS2 units per second (a player sprinting is 250). A full-speed car crosses a 640-unit-wide track in
under a second.

## E abilities

Every car has one ability on E (it costs charge and has a cooldown; the HUD shows it under the charge bar: gold and
pulsing when ready, red when there isn't enough charge). Bots use them too.

| | Ability | Cost / cooldown | What it does |
|---|---|---|---|
| HORNET | **Seeker Bolt** | 20 / 6 s | Fires a bolt forward along the road at the Hornet's speed + 900 u/s, out to 2,500 units. It locks on to the first car ahead (by road distance, either team) and curves towards its line at 280 u/s. The car it hits is shoved sideways, skids for 0.6 s, loses 25% of its speed and 10 shield (credited to the Hornet). An Aegis shell stops it. Locked for the first seconds of a race like the Shockwave. (Replaced Phase Dash, a sideways dodge, on 28 Oct 2026.) |
| METEOR | **Shockwave** | 40 / 12 s | Slams the road: every car within 320 units is shoved sideways away from the Meteor (300 x its mass / theirs, more the closer), skids for 0.3 s and loses a little shield; the Meteor loses 8% of its speed. A ring of light shows the blast; everyone caught gets a hard camera shake. |
| COMET | **Nova Burn** | at least 40 / 12 s | Spends all its charge at once: a 220 u/s kick, then an overdrive (1.5x top speed, double acceleration) for 0.7 s + 0.012 s per point of charge, and a trail of blue fire for the first 0.8 s. Anyone else driving through the fire loses grip and 2 shield every half second (credited to the Comet). |
| BASTION | **Aegis** | 30 / 12 s | A 2.5-second hexagon shell: no damage and no shoves, and cars bounce off it as if it weighed four times as much. Teammates within 500 units get +20 shield. |

Balance with the abilities in: see the table under the cars (18 Oct). Bots use their abilities too
(about 2.9 Seeker Bolts with 2.5 hits, 2.6 Shockwaves, 1.4 Nova Burns and 1.9 Aegis shells per race; bots fire a bolt only at a foe roughly in line).

## Track mechanics

- **Track**: a closed loop with walls (rails) on both sides. The rail bounces you back, costs speed and a little
  shield (scraping is cheap, a head-on hit is not). Some tracks have **gap** sections with no rail: run off and you
  fall into space, reappear at the last checkpoint 2.5 seconds later with 20 less shield and no speed.
- **Boost pads**: bright chevron strips on the racing line. Driving over one gives 1.2 s of boost (1.65 s in a Comet)
  and an instant speed kick. They cost nothing.
- **Charge platforms**: wide glowing panels, usually on the outside of a corner or on a side lane that is a bit
  longer than the racing line. While you are on one, charge refills quickly and shield slowly. The detour is the
  decision: refill now, or stay on the line and hope for the Pulse.
- **Boost** (hold Mouse 1): spends charge for about 30-45% more top speed and extra acceleration. Charge drains in
  roughly 3 seconds from full. No charge, no boost.
- **Drift** (hold Space): the car slides; sharper turning, more speed loss, and the drift fills charge a little
  (a lot in a Hornet) - but only through a slide held one way for 0.35 s, and not while boosting (before 17 Oct a
  Hornet could hold drift, flick left-right and boost for ever).
- **Slipstream**: directly behind another car (within ~300 units, in a 20 degree cone) you get less drag and a
  trickle of charge. Teammates (same CS2 side) in each other's slipstream get the trickle doubled (**convoy**).
- **Spin attack** (Mouse 2): costs 30 charge (18 in a Hornet), 3 second cooldown. The car spins for half a second,
  and any car within its reach - touching, or a little further, as the tail swings round - takes 20 shield and is
  shoved sideways, away from the attacker: its speed changes by 480 x attacker mass / its own mass, it loses 12%
  of its speed and it skids for 0.55 s (a quarter of its grip, half its steering), so the shove carries it across
  the road, often into the rail. A Meteor shoves a Hornet about 220 units, a Hornet shoves a Meteor about 100
  (`node test/spin_test.cjs` prints them all). Before 17 Oct a spin only hit a car it was closing on, and grip
  killed the shove within a few frames (about 35 units). The attacker is not immune to the rail.
- **Contact**: cars are solid. Bumps exchange momentum by mass and cost both cars shield in proportion to the
  closing speed (0 to about 20 per hit). Being hit never stops you outright, it pushes you.
- **Wreck**: shield 0 means a wreck — explosion, car gone, placed behind everyone still racing. If another player
  dealt the last blow within the last 2 seconds, that player gets the CS2 kill immediately (killfeed and all).
- **The Pulse**: once per lap a ring of light sets off from the back of the field and travels the track at 1.5x
  top speed. Every car it overtakes gets +40 charge. It is a catch-up mechanic you can see coming.
- **Jumps everywhere** (17 Oct): besides Skyway's two big downhill jumps there are gap jumps on Solar Oval (the top
  straight before the chicane), Hairpin Harbour (two straights), Crosswire (after the start), Switchback Spire (two)
  and Helix (the bottom straight), each a 6-sample ramp 110 high and a 670-720-unit gap - about 800 u/s clears it,
  so full speed always makes it and a car slowed by a bump, a spin or a Shockwave drops in (falling costs 20 shield
  now) - and two kickers on Skyway's straights (a ramp with the road carrying on: air time, no gap). A spin or a
  Shockwave mid-air pushes a car sideways for the whole flight, off the edge of a gap. **Big air**: landing cleanly
  after 0.7 s or more in the air pays 15 charge.
- **Jump ramps**: a full-width striped ramp, then open space. Off the lip the car flies with the ramp's slope
  (gravity 1150, a little steering, no thrust); land on the road beyond, or fall into the gap. Skyway's ramps rise
  110 units and the landings are 240 lower than the lips - about 700 u/s is needed to clear the 720-unit gap. A hard
  landing (falling faster than 1050 u/s) costs a little shield.
- **Banked bends**: every bend leans into the turn by its curvature (up to 14-26 degrees, steepest on Skyway). A
  banked bend grips harder and turns tighter (`RULES.bankGrip`, `bankTurn`), so the fast line hugs the high side.
  The car and the camera lean with the road.
- **Tubes**: some sections run through octagonal tubes with neon strips that stream past; the camera drops and
  closes in inside them. Ringworld's lower pass runs through a tube under the bridge.
- **Turbo start** (a secret: nothing in the game or on the Workshop page tells players): press W on the third beep,
  or any time after it, and hold it to GO for a launch (an instant kick and a pad-strength boost for a second). The
  beeps come 3, 2 and 1 seconds before GO (the third one higher); the window opens 1.25 s before GO, so a press on
  the beat counts even with ping and reaction time. Holding W since before the second beep stalls the engine for
  half a second ("TOO EARLY - ENGINE STALLED"). Bots get it sometimes, more often the better they are.
  `node test/turbo_test.cjs` checks the timing. (Before 17 Oct the window was the last 0.45 s, so a press on the
  third beep did nothing.)
- **Lap records**: the best lap on each track since the map loaded is shown in the lobby ("RECORD 0:24.31 NAME")
  and announced in chat at the end of the race that set it.
- **Slick zones**: on some tracks, a strip where grip drops to 30% (purple and pink wavy bands).
- **Shield repair**: once nothing has hit you for 4 seconds the shield repairs slowly (2.2/s), so a race is lost
  to sustained aggression, not to attrition. Bumps below a closing speed of 250 are free.
- **Clean start**: for the first 6 seconds after the lights nothing can be damaged, nobody can spin and the Meteor
  can't Shockwave or the Hornet Seeker Bolt (their ability bar counts down "ATTACKS IN 6"; then everyone gets "ATTACKS ON"), so the start is a
  drag race, not a brawl in a 32-car pack. Nova Burn and Aegis work from GO (they can't hurt anyone
  while nothing takes damage, and locking them too cost the Comet its launch: wins 3.8 -> 3.0 per 100). Meteor bots
  then Shockwave over the next few seconds, not all at once. A car hit by a spin can't
  be spun again for 1.5 s, so a pack can't chain-spin someone to a wreck. Measured (scratchpad start.cjs, 24 races):
  bots alone, no wreck in the first 16 s (first wreck typically at ~50 s); with a quarter of the field mashing
  Mouse 2 and E from the lights, no wreck in the first 12 s and the first one at ~18 s (before: ~11 s, 9 wrecks a
  race; now 7). Balance with it (720 races): wins/100 H 3.1 M 3.2 C 3.4 B 2.8, podiums 9.3 / 8.9 / 9.0 / 10.4,
  KOs H 3.6 M 12.5 C 5.7 B 7.3, about 2.4 wrecks a race (fewer chain wrecks), light cars wrecked ~15%.
- **Laps**: per track (2 or 3; a race is about 75-120 seconds for bots, longer for people). Eight checkpoints per lap stop corner
  cutting; driving the wrong way shows a warning and does not count, and a missed checkpoint shows
  "MISSED CHECKPOINT" until you go back for it.
- **Finish**: crossing the line on the last lap. Your car warps out (flash) so it does not block the others.
  The race ends when everyone is in, or 30 seconds after the winner; the rest are ranked by distance.

## Round flow (one CS2 round = one race)

1. **Lobby / freeze time.** Players spawn in the lobby room. Their CS2 bodies are parked in a sealed booth for the
   whole round and only used for input; everyone looks through a script camera. The HUD shows "race starts in N",
   your car, and the car picker (by itself until you have picked or raced once; `!car` after that).
2. **Grid.** When freeze time ends, everyone on T or CT who is not AFK is assigned to an arena and put on its grid
   in a random order, 4 abreast. 10-second countdown; cars can be swapped until 3 seconds before the start (the
   small cards show by themselves on your first grid, or after `!car`; the line under the track name says your
   grid slot and the time to the lights).
3. **Race.** Rounds are **locked**: nobody joins a race in progress. Someone connecting mid-round watches
   (Mouse 1 / Mouse 2 change the car you follow, E changes arena) and is in the next round; `!car` brings up the
   cards to pick a car for it.
4. **Results.** Each arena shows its top 8 and your own placing for 6 seconds, with nothing over it: a car picker
   still open when the race ends closes (`!car` brings it back). The CS2 kills are applied in a
   cascade (one every few ticks, so the killfeed rolls). When every arena is done the script ends the CS2 round
   with the team result below. A race that somehow runs past 5 minutes is cut off and ranked by distance.

### Arenas

- Up to 32 cars per arena, up to 2 arenas: 1-32 players race together; 33-64 are split evenly into two arenas
  (33 → 17 + 16). The split keeps the same share of Ts and CTs in each arena.
- Each arena races on a different track, picked at random from the eight in the map, never the same track two
  rounds running. The next round's tracks are picked in advance so the lobby can show them.
- Bots on the server race too (CS2 bots are driven by the script's own driving AI), so a test server with
  `bot_quota` fills the grid.

### Who wins the CS2 round (T vs CT)

Per arena: with 8 or more cars, count how many of the top 8 are T and how many are CT. With fewer than 8 cars, the
winner's side gets 1 point. Add the arenas up; the higher side wins the round. On a tie, the side with the better
single finishing position wins (switchable; otherwise a draw).

### Kill credit (rank plugins)

Racing has no kills, so the script makes them at the end so the CS2 scoreboard and rank plugins see the result:

- The top 3 of each arena survive. Everyone else is a loser and takes one CS2 death.
- The deaths are credited as kills: 50% to the winner, 30% to second, 20% to third (largest remainder rounding).
  32 cars → 29 losers → 15 / 9 / 5.
- A car wrecked by another player's attack during the race is a real kill for that player at that moment, and is
  left out of the end-of-race shares. (Config `KO_CREDIT_TO_ATTACKER`; off = all deaths go to the podium.)
- Everything uses the FreeDM method: `pawn.TakeDamage` with the attacker, so the killfeed, scoreboard and rank
  plugins all count it. `mp_teammates_are_enemies 1` keeps same-side kills from counting as teamkills.

### AFK

No input for 20 s while driving: warning on your own HUD. 30 s: your car withdraws (it counts as a loser), you
watch the rest, and you sit out the next round until you press a key or type `!back`. Waiting after you finish or
wreck, or watching as a late joiner, is not idling. Idle through 2 minutes of lobby: the same as AFK.

### Joins, leaves and slots (robustness)

- Every CS2 slot is checked once a second; a slot that now holds a different player (bot kicked for a joining
  human, a quick leave and rejoin) is treated as a new person: no inherited car, kill credit, HUD state or options.
- Every queued CS2 kill remembers who the victim and killer were; if either slot changed hands, the kill is dropped
  or goes to the world. A killer who left gives a world kill.
- Knock-out kills mid-race need CS2 to respawn the pawn. If CS2 doesn't (two failures), knock-outs are credited
  to the attacker in the end-of-race cascade instead.
- If CS2 doesn't end the round after a race (warmup, or a plugin), the next race starts on its own after 20 s.
- HUDs refresh at 32 Hz (half the players each tick); cameras every tick.

## Controls

| Key | Action |
|---|---|
| W / S | accelerate / brake and reverse |
| A / D | steer (and move through the cars while the car picker is up) |
| E | the car's ability (and confirm your car on the picker) |
| R | bring the car picker back (when not driving) |
| Mouse 1 | boost (spends charge) |
| Mouse 2 | spin attack |
| Space | drift (fills charge through a slide held one way, not while boosting) |
| Mouse (look) | nothing — the camera follows the car |
| Mouse 1 / Mouse 2 / E (spectating) | next car / previous car / next arena |

Chat (`!` or `/`): `!car` (the car picker, 6 seconds), `!car 1-4` or a name (pick straight away), `!cam` (high /
far / near view), `!tilt` (camera lean on/off), `!crt` (scanlines on/off), `!music`, `!spec`, `!afk`, `!back`,
`!help` or `!race` (controls on your own HUD).

## HUD

Panorama custom HUD, per player, all game text in the pixel font: a big position ("3RD/32", green on the podium,
gold when leading; it pops each time you gain a place), the lap ("FINAL LAP" blinks red), the live team score
("T 5 - 3 CT": top-8 places per side across all arenas, the thing that decides the CS2 round) and the bend-ahead
arrows top-centre, a pixelated track map top-left with a dot for every car in the race (T orange, CT blue, the
leader gold, yours blinking white) and under it the race clock with the running lap time and your best lap, the
top-8 standings down the right edge (a side-coloured tab per row, you highlighted), segmented pixel bars for shield
and charge bottom-right (shield blinks red when low; charge turns gold when boosting and pink on a charge platform)
over the speed, centre messages (countdown, GO!, FINAL LAP, WRONG WAY blinking, WRECKED, FINISHED 3RD, LAP RECORD!;
each new one pops in), a bottom line for short news and the answers to chat commands, the car picker (four framed
cards, each with a pixel picture of the car in your side's colour, its perk and five stat bars; the chosen one gold
and pulsing) in the lobby, and a row of four small cards bottom-right on the grid (so the flyover's view of the
field stays clear; both only until you have picked a car or raced once, then after `!car`), the SPACE RACER logo and three status lines in the lobby, a pulsing RESULTS banner over a
results board at the end (top 8 with the winner's time and everyone else's gap, your own line swapped in if you
placed lower), flickering pixel speed lines round the screen edges while boosting, and CRT scanlines plus a vignette
over everything (`!crt` turns them off for you). `preview/hud_race.png`, `hud_grid.png`, `hud_lobby.png` show it.

CS2's own HUD stays on (a script can't hide it) and is drawn over ours, so ours keeps out of the places it uses
(`preview/hud_cs2.png` marks them): chat bottom-left (the chat box is x 18-571, y 609-1000 at 1080 high, its
newest lines at the bottom), the kill feed top-right (from y 75 down, a line about 36 px), the team counter
top-centre (to about y 65) and the money / health row along the bottom edge. That is why the left column is the
map and the clock, shield / charge sit over the speed on the right, the lobby's cards end around y 790 (the last
half-dozen chat lines show under them) and the bottom line is 38 characters at most (at 16:9 even the longest
stays right of the chat). On 4:3 the chat is 40% of the screen's width, so long bottom lines and the cards' left
edge can reach it there; chat is still drawn on top.

How the pixel text works: each text row is a line of small image panels, one per character. The script sets each
panel's glyph class (`g65` = A) and the row's colour class, and only for characters that changed; whole rows are
cached, so an unchanged HUD costs nothing. Player names in the standings stay as ordinary Labels. The minimap dots
move with transforms; the other cars' dots step two map pixels at a time and a quarter of them refresh per HUD
update, which halves their class traffic.

Layout rules (from the first CS2 test, 17 Oct, where the HUD was thrown around: top panels at the bottom of the
screen, centre text stacked, the bars squashed, no car cards):
- The cause: the script's state class on the root ("Pick") had the same name as the picker panel's class, so the
  whole HUD root took the picker's rule (a narrow flow-down box aligned to the bottom). State classes on `spr_root`
  now all start with `st` (stOn, stLobby, stPick, stHelp, stRes, stSpec, stBoost), `tools/hud.py` refuses to build
  if a switched class has a rule of its own, and the mock test checks it too.
- The layout is also static now, so nothing depends on Panorama laying things out again at runtime: one fixed
  1080-high Screen panel (Panorama scales every screen to 1080 high), every panel a fixed size pinned from the top
  and from the left edge, the centre or the right edge (no vertical centring, no negative margins, no fit-children
  boxes), and panels are shown and hidden with opacity instead of collapsing.
- `preview/hud_render.py` is a small stand-in for Panorama: it lays the HUD out from the generated xml/css, draws it
  with the real pictures at 1920, 2333 (ultrawide) and 1440 (4:3) wide, and fails the build if any panel breaks
  those rules or (at 16:9 and wider, in every state) sits where CS2 draws its chat, kill feed, team counter or
  money / health row. A text line too long for its row is a `WARNING` in the console (and fails the mock test).

## Tracks (eight, all original)

| Track | Lap | Laps | Scenery | Character |
|---|---|---|---|---|
| Solar Oval | 30.9k | 3 | pixel city at sunset | a huge speedway; the east bend climbs onto an elevated back straight with a chicane that ends in a tube, the west bend dives home |
| Hairpin Harbour | 37.4k | 2 | teal city | four long straights joined by banked hairpins, climbing a terrace each time, then down through the harbour tube |
| Crosswire | 36.7k | 3 | neon city | a giant figure-8: the first pass dives low through the middle; the second climbs into a full banked spiral loop round the crossing (the first pass threads through it, twice underneath), comes out over the top of itself and dives round the east lobe to the grid |
| Null Gap | 28.1k | 3 | asteroid belt | two long narrow rail-less sections over the void that roll up and down like a coaster |
| Switchback Spire | 39.2k | 2 | crystal spikes | four switchbacks up to 1200 units, a long banked sweep, then a dive through a tube |
| Ringworld | 29.5k | 3 | giant rings, asteroids | a figure-8; one pass is a bridge 920 up, the other runs under it through a tube |
| Skyway | 33.0k | 3 | cloud sea | a stadium high in the sky with steep banking and a long downhill jump on each straight |
| Helix | 38.8k | 3 | asteroid belt | a 1.5-turn spiral climbing 1300 units, off the side and a banked dive home through a tube |

(Lap lengths in units; `preview/tracks.png` shows all eight with their pads, platforms, gaps, tubes and
checkpoints; `preview/chase_all.png` the racer's view on each.)

Every track has a start gantry with its name in voxel letters, checkpoint gates with their sector number in voxel
digits, slogan billboards beside the straights, beacons and turn signs, a synth-grid floor far below (Skyway has
clouds instead), and its own pixel-art sky: gradient bands, a dithered nebula, pixel stars, a big planet (ringed,
banded, cratered, or a striped retro sun) and a skyline or mountain silhouette on the horizon.

World layout: each track sits in its own 13,800-unit box. The eight boxes are two layers of 2 x 2 (layer 0 at
z -5000: oval, hairpin, crosswire, null gap; layer 1 at z +3600: spire, ringworld, skyway, helix), all inside the
CS2 world limits. Each box is a moondome shell showing that track's own pixel sky (no toolsskybox shell: it would
show the map's single env_sky instead). Vis hints: Lowest over the whole map, Low only in the lobby rooms. Nothing inside a box occludes (the track and
scenery are props with visoccluder off), so fine vis there buys nothing. Until 28 Oct a band of Low hints ran along
each road; Neon Racer's vis then made 3.7 million clusters (`SPR_ROAD_HINTS=1` brings the band back). Only
one box is ever in view, so the scenery (25-35k triangles per track) costs little.

## Loading screen

CS2's loading screen shows `panorama/images/map_icons/screenshots/1080p/<map>.png`, `<map>_1.png` ... `<map>_9.png`
as a slideshow (4 seconds each, starting on a random one) - and shows nothing at all when a map has only one
picture, which is why the first version's loading screen never appeared. `tools/loading.py` draws four slides.
Every slide has the same frame: the logo and a CONTROLS panel (the keys for driving and watching, and the chat
commands) in the same place, so it can be read while the slides change. Below it is a panel that changes: the four
cars and their perks, the eight tracks, how to win (kill shares, the T / CT result, drafting) and what is on
the track (pads, ramps, slick bands, the Pulse), each over a different track's sky.

CS2 draws its own column over the right of the screen (map name, icon, mode, the loading bar; 300 px wide, 20 px
from the edge, the slide blurred behind it) and scales each slide to cover the screen. So everything that matters
sits in x 252-1348, y 104-948: clear of the column at 16:9 and 16:10, and not cut off at 4:3 (which loses 240 px
on each side) or by an ultrawide's crop of the top and bottom. `preview/loading_cs2.png` sketches the column and
those edges over the first slide; `preview/loading_all.png` shows all four. The slides get compiled because the
HUD's stylesheet points at them (never-shown `SprPre` rules), like the radar and the map icon.

## Architecture (same shape as FreeDM)

```
src/core/   the race game, plain JS, no engine calls: track maths, car physics, rules, bots, round manager
src/cs2/    the CS2 side: pawn parking + chase camera, input, prop pool rendering, HUD, sounds, CS2 kills,
            round control (FireWinCondition), chat commands, cvars
tools/      generators: trackdefs.py (the eight designs + colour themes), tracks.py (track data, road / tube /
            scenery models, minimaps), retro.py (palette, dithering), pixfont.py (the pixel font, logos),
            skies.py (pixel-art sky panoramas), cars.py (voxel car models, pixel effects), hud.py (Panorama
            layout/css + glyph pictures), loading.py, sounds.py (chiptune sounds + music + soundevents),
            vmap.py (writes the whole map into the Hammer template), build.mjs (assembles the script), build_all.sh
test/       sim.cjs (bot races on the pure game), mock_cs2.mjs (the real script on a stand-in cs_script API),
            tsconfig.json + point_script.d.ts (type check against Valve's API)
preview/    PNG renders of tracks, cars and the HUD for checking without CS2 (hud_render.py: the HUD layout check)
```

- Script cost (18 Oct pass): a full 64-player server costs about 0.14 ms of script time and ~215 CS2 calls per tick on
  the stand-in engine. What keeps it there: the HUD remembers what each part was drawn from and skips parts whose
  inputs haven't changed (the class cache is only consulted when something did); per-arena and per-car values the
  HUD needs (clock, field size, turn arrow) are worked out once per tick; pawns, cameras, props and the HUD entity
  are checked with IsValid every 8th / 16th tick instead of every tick (CS2's events drop stale entries, and a failed
  call drops the entry too); cars that haven't moved aren't moved; idle players' keys are read with one masked call
  once the script has seen that masks mean "any"; every field a car or arena will ever have is set in its
  constructor (V8 slows down when objects change shape); the pair loops (slipstreams, bumps) scan flat arrays.
  The race itself is bit-for-bit the same as before (test: a hash of every car's state every tic).
  test/mock_cs2.mjs runs the script like CS2 does (as a module, not in a vm context, which made timings ~2.5x too
  slow) and has `held`, `seed=`, `trace=` (compare two builds by what ends up on screen), `calls` and `maskall`.
- Track votes (RoundManager.closeRace / vote / assignTracks): a finished race's top places (VOTE_WEIGHTS 3 / 2 / 1)
  get a ballot of VOTE_CHOICES tracks (unraced this round first; ballots use their own seeded random so the race's
  random sequence is untouched); at the next startRound each new group counts its own members' votes, arenas with
  the strongest pick choose first, clashes fall to the next choice, no votes = the upcoming rotation. A person's
  vote only counts while the same person holds the slot. The race's top glowPlaces get car.glow next round
  (Glow() on the prop in their shade's colour); pe.shade / car.shade pick one of SHADES (tools/cars.py: six palette
  skins per side after neutral / t / ct / gold, so the old skin numbers never move).
- The sim runs at 64 Hz, one step per CS2 server tick (64 cars cost about 0.04 ms per tick in Node), so props are moved with `Move` every tick and the client
  interpolates; no sub-tick interpolation needed. `Teleport` only for a prop's first placement and real jumps
  (respawns): CS2 stops drawing a prop that is teleported every tick (the first test's invisible grid).
- Cars are pooled `prop_dynamic` entities spawned from one `point_template` (model = car class + state:
  normal / boosting / wreck frames; skin = T or CT colour).
- Camera: `CustomPlayerCamera` in CONTROLLED mode. Presets per player (`!cam`): high (default, 290 back / 165 up /
  15 deg down), far (420 / 260 / 22), near (230 / 100 / 9); pulls back further at speed, yaw eases towards the car's
  heading turned 35% into the bend ahead (so the upcoming track stays in view), a few degrees of roll in corners.
  The mouse does nothing during a race.
- Readability at a distance: tall beacon pylons with glowing caps every ~480 units on alternating sides, and a
  chevron sign on the outside of every real corner, facing the approaching cars. No fog, nothing fades out.
- On the grid the camera first does a flyover: a low swoop along the track towards the waiting field, cutting to
  the chase camera 4 seconds before the lights. At the results it circles the start gantry.
- The camera leans with banked bends (60% of the road's angle) plus a few degrees into each turn (`!tilt` turns
  the lean off for you), shakes a little on hits, rail strikes, landings and wrecks (`CAM_SHAKE`), and drops lower
  inside tubes. Cars sit level with a banked road and lean into their turns (up to 16 degrees, from how fast they
  are turning). Roll angles follow Source's convention, + = right side down; `PROP_ROLL_SIGN` / `CAM_ROLL_SIGN`
  flip either one if CS2 ever shows it the other way.
- The Pulse is drawn as a low pixel laser fence across the road with a strip of forward chevrons under it, tilted
  with the road's slope and bank (the first version, a 160-tall see-through sheet, washed out the screen as it
  passed the chase camera).
- Cars are true 3D voxel models (about 115 units long), so every viewing angle is drawn correctly - the chase camera
  shows them from behind like a classic racer, and each car's tail has its own silhouette and lights.
  `preview/car_angles.png` shows all four from eight directions.
- Every CS2 pawn stays parked (frozen, invisible, weaponless) in the booth; all damage to pawns is aborted except
  the script's own kills.
- Tracks are `prop_static` models (road, rails, pads, platforms, scenery), unlit materials, so compiles are quick
  and the look is the same on every setting.
- Sounds: `point_soundevent` per sound, pointed at the car prop (or an anchor) and started, as in FreeDM. All
  chiptune: pulse waves, a 16-step triangle, shift-register noise, 4-bit envelopes, a 22 kHz sample-and-hold.
- Music: four original pieces written as note lists in `tools/sounds.py` - "Parking Orbit" (lobby loop, 100 bpm,
  D minor), "Neon Overdrive" (race loop, 156 bpm, A minor), "Starlight Circuit" (race loop, 168 bpm, E minor; the
  two race loops take turns) and a results fanfare. They play for everyone at once,
  not placed in the world (stereo, no distance fall-off); the script restarts each loop as it ends. `MUSIC: false`
  in CONFIG turns it off; the volume is `MUSIC_VOL` in `tools/sounds.py`.

## Settings (CONFIG in the script)

Laps, arena sizes, finish window, race time cap, the four car stat tables, kill shares and podium size,
`KO_CREDIT_TO_ATTACKER`, the Pulse (on/off, speed, charge), AFK times, bot skill, cvars the map applies.

## Bots

Each bot keeps a home lane (from its grid column, five lanes across the track), changes lane only to pass a slower
car into a lane that is clear ahead and just behind, brakes when it is closing on the car in front, gives room to a car
alongside, and brakes for any bend it cannot make at its current speed (turn rate needed vs. its car's turn rate).
In `test/sim.cjs` this cut car-to-car contact by about 30% and wrecks from ~110 to ~60 per 16 races of 32 cars.
