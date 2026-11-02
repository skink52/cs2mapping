# Space Racer changelog

## v0.6.1: track edges and jungle music (29 Oct 2026)

- **Out of bounds** (all three games): the rails only hold a car on the road or just above it (`RULES.railHeight` 30).
  Higher in the air, past the edge, the car flies out of the map. It loses 55 shield (`outPenalty`) and comes back on
  the centreline where it left the road, or just past it if that was a gap, ramp or flight (`safeSpot`). Before
  this, invisible walls in mid-air caught cars that overshot a jump into a bend. Gap falls cost 35 (was 20). All falls
  now respawn where the car left, not at the last checkpoint. The HUD says `OUT OF BOUNDS` / `FELL OFF` and the hit.
- **Jumps land before the bend**: each ramp knows how far its landing deck runs straight (`f.maxD`). A fast car's
  throw is capped so a straight launch comes down by then. Slow cars still fall short of gaps as before.
- A little steering in the air (`RULES.airGrip` 2.5). Bots line up square and drift to the middle before a ramp.
- Sea creatures hitting a car in the air give a smaller shove (`creatureAirKnock` 0.3) and stop its climb.
- Coral Crown's kicker moved from mid-bend to the straight after it (0.13 -> 0.235).
- Sim (32 bots, 6 races per track): fly-outs at most 0.5 a race on any track (Skyway was 59 before the fixes).
- **Depth Racer music** is now atmospheric jungle / liquid drum & bass: 'Pressure' 172 bpm, 'Leviathan' 174 bpm,
  'Still Water' half-time lobby. Synthesised chopped breakbeats with ghost notes and rolls and 12-bit sampler grit,
  a phasing reese bass over a sine sub, choir / string pads, FM Rhodes chords and an airy delayed lead.

## v0.6.0: Depth Racer, and +200 km/h for all three games (29 Oct 2026)

- **Depth Racer** (`mg_depth_racer`, `SPR_THEME=depth`): a third game on the same code, on the sea floor.
  - Six tracks: Kelp Canyon, Coral Crown, The Wreck, Vent Field, Abyss Drop and Lantern Deep. Three have glides
    (Neon Racer's flight sections). The scenery is kelp, coral, ruins and rocks.
  - **Giant sea creatures** (`src/core/35_creatures.js`, `tools/creatures.py`): sea serpents, manta rays and whales
    cross the track over the jumps and glides on a fixed cycle. A hit shoves the car, makes it skid and takes shield;
    Aegis blocks it. Drivers get a warning before a crossing; bots hold back and let them pass.
  - Deep-sea pixel textures and skies, dark car hulls, a sea-floor loading screen, and dub / electro music
    ('Pressure', 'Leviathan', 'Still Water').
  - docs/depth/README_ADDON.md, TESTING.md and the Workshop description and thumbnail in workshop/depth/.
- **+200 km/h** (all three games):
  - Top speeds +556 u/s (Hornet 1620, Meteor 1646, Comet 1596, Bastion 1599). Acceleration x1.45, brakes x1.3.
  - Turning fades more slowly with speed (`RULES.turnFade` 1500 -> 2400).
  - Boost pads, the Pulse wave, the turbo start and Nova Burn kick harder. The Seeker Bolt reaches further.
    Flights climb and dive faster.
  - Jumps: ramps throw cars flatter (`RULES.rampThrow` 0.65) and gravity is 1150 -> 1500. Jump length goes with
    speed squared, so without this cars flew 2.5x as far and landed in the next bend.
  - Rail and bump damage start at higher speeds (`railSoft` 140 -> 220, `contactSoft` 250 -> 380), with less per
    unit over, so the faster racing doesn't wreck more cars.
  - Bots look further ahead for bends at speed.
  - Sim (32 bots, 12 rounds each game): laps about 30% quicker; wrecks Space 10 -> 19, Neon 17 -> 24, Depth 14 -> 37
    (mostly the Vent Field whale); falls about the same.
- Space Racer and Neon Racer: only the script changed (tracks, models, HUD and music are the same as in v0.5.0).

## Neon Racer pixel update (28 Oct 2026, evening)

- **Pixel style, neon colours**:
  - The Tripo3D cars, pylons and gates are gone.
  - The cars are Space Racer's voxel cars again, with near-black hulls and glowing team-colour trim and edge lines.
  - Every track texture and sky is drawn in chunky dithered pixels in a neon palette.
  - Flight gates are glowing pixel rings again.
- **Flight rings**: the stray strip across the corridor floor under each ring is gone. The rings were also being drawn as road pads.
- **Flight controls inverted**: like a plane, S pulls up and W noses down. The flight message, help panel, loading
  screen and Void Hop's billboard all say so.
- **Music with more punch**:
  - A heavier kick with an extra sub layer and click, and claps layered on snares.
  - Driven saw basses pumping hard under the kick, wide supersaw leads, and saw arpeggios in place of square ones.
  - A harder master: compression, drive and loudness normalised to about -11 LUFS.
- **Scenery out of the track**: buildings and spikes stay below the lowest part of the track near them. That counts
  every deck where the track passes over itself, and the flight corridors with their full radius. Tilted crystal
  spikes keep their tips clear. Before this, Skyline Dive's buildings stood in the flight corridor, and Overclock
  and Switchback Spire had some too (both games).
- **Turn signs are one-sided**: the face looks back at the cars coming, and from behind nothing is drawn. The back
  had shown a mirror image (both games).
- **Harder hits**: the Seeker Bolt does 6 -> 10 damage, the Shockwave 2 -> 6 and Nova fire 2 -> 4 every half second.
  The spin knockback is 480 -> 640 (shared game code: Space Racer gets it on its next build).
- **Faster vis compile**: Neon Racer's vis made 3.7 million clusters. The Low hints along every road are gone; nothing
  in a track box occludes, so they bought nothing. The whole map is now one Lowest hint, with Low only in the lobby
  rooms (both games; Space Racer on its next build).
- **Pylons tied to the track**: each trackside pylon has an arm under the road's edge and a stepped brace from its
  foot up to the road's underside, so it no longer floats beside the track (both games).
- **Start gantry**: its towers now stand clear of the track name. The letters had run into the pillars. This changes
  the generator for both games; Space Racer's tracks change too on their next build.

## Neon Racer v0.5.0 (28 Oct 2026, first build)

A second addon, `mg_neon_racer`, built from this repository (`SPR_THEME=neon`). It plays like Space Racer v0.5.0.
- **Six new tracks**: Grid Circuit, Pulse City, Void Hop, Data Stream, Skyline Dive and Overclock.
- **Flight sections** on Void Hop and Skyline Dive:
  - The road ends and you fly a corridor of gates. W climbs, S dives and A / D steer.
  - The corridor's edge bounces you like a rail. Gold rings boost you and blue rings charge you.
  - The corridor narrows onto the road at the end.
  - Bots fly through the rings, and the Seeker Bolt follows its target's height.
- **Neon look**: glowing-line roads, rails and towers, synthwave skies over an endless grid, Tripo3D pylons and
  flight gates.
- **Cars** made from skink52's Tripo3D models (about 9k triangles each). Their glowing strips show your side's colour.
  Replaced by pixel cars in the evening update.
- **Music**: four original electro pieces in place of chiptune.

Shared code changes (no effect on Space Racer's tracks):
- The track data can have flight sections and flight rings.
- A checkpoint that a long flight pushes onto the next one moves back before the flight instead.

## v0.5.0 (28 Oct 2026)

### Changed
- **Hornet: Seeker Bolt replaces Phase Dash.** E fires a bolt forward down the road. It locks on to the first car
  ahead and curves into it. The car hit is shoved sideways, skids, loses a quarter of its speed and 6 shield
  (credited to you). An Aegis shell stops it. Costs 20 charge, 6 s cooldown, range 2,500 units. Like the Shockwave,
  it unlocks 6 seconds after GO.

## v0.4.1 (18 Oct 2026)

### Changed
- **No team menu.** Players who join without a team are put on the side with fewer players after a second, so CS2's
  team menu never sits behind the race HUD. The M-key team menu is turned off (`AUTO_TEAM` in CONFIG turns this
  off); `!spec` still lets you watch.
- **No money.** Kills and rounds pay nothing, and nobody starts with money.

### Fixed
- The minimap dots didn't move: each dot was clipped by its own panel as soon as it moved down the map.
- The car picker could reopen over the results if you were tapping A / D as the race ended.

## v0.4.0 (18 Oct 2026)

### New
- **Track vote.** When a race ends, its top 3 vote on the next track from a box on the left of the screen.
  - Use W / S to pick, or type `!vote 1-4` or a track name.
  - 1st place's vote counts 3, 2nd's counts 2, 3rd's counts 1.
  - Votes can change until the next race is set up. Everyone in that race sees the box and the totals.
- **Votes work per arena.** With two or more arenas, each new arena races the track picked by the voters who end
  up in it. If two arenas want the same track, the one with more votes gets it and the other takes its next choice.
- **Colour shades.** `!shade` picks your car's colour; `!shade 1-6` or a name picks one directly. Your choice is
  remembered and your car changes straight away.
  - T: orange, red, crimson, coral, rose, maroon.
  - CT: blue, navy, cyan, teal, indigo, ice.
- **Winners' glow.** Last round's top 3 in each race drive the next race with a neon outline in their own colour.
- The loading screen and the `!help` panel list `!shade` and `!vote`.

### Fixed
- With two or more arenas, human players placed in the second (or third or fourth) arena were turned into
  spectators while it was being set up. Those arenas raced with bots only. Every arena now fills properly.

### Server settings (in the script's CONFIG)
- `VOTES`, `VOTE_WEIGHTS`, `VOTE_CHOICES` and `BOTS_VOTE` control the track vote.
- `WINNER_GLOW` and `GLOW_PLACES` control the glow. `GLOW_PLACES 1` limits it to winners only.

### Performance
- The map's script uses about a third of the server time it did, and makes about a third as many calls into CS2
  each tick. Nothing looks or plays differently.

| Server | Script time per tick, before → after | CS2 calls per tick, before → after |
|---|---|---|
| 64 players (20 humans + 44 bots) | 0.36 → 0.14 ms | 608 → 215 |
| 32 humans | 0.41 → 0.11 ms | 723 → 255 |
| 8 players | 0.055 → 0.026 ms | 63 → 25 |

These figures are from a test engine on a PC, not from a CS2 server.

### Fixed
- A car that fell off and reset at the very moment a race ended could vanish during the results.
- Some car sounds kept replaying after a race had ended.

### Server settings (in the script's CONFIG)
- `PERF_LOG` prints the script's time per tick in the console once a minute during races.
- `MINIMAP_DOT_HZ` sets how often the other cars' minimap dots move. The default of 8 is unchanged; 4 halves the
  biggest share of HUD traffic.
