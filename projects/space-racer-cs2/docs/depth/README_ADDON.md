# Depth Racer for CS2: setup and how it plays

Depth Racer is Space Racer's game on the sea floor. It is a 32-car anti-grav racer run by the cs_script
`maps/scripts/depth_racer.js`, with no server plugins and up to 64 players in two arenas. It has six new tracks, three
of them with **glides** (Neon Racer's flight sections, through the water), and **giant sea creatures** that cross the
track over the glides and jumps. The art is Space Racer's pixel style in deep-sea colours, and the music is dark dub /
electro. Rules, controls, chat commands, rounds and kill credit are the same as Space Racer's (see Space Racer's
README_ADDON.md). The map name is `mg_depth_racer`.

## 1. Install and build

1. Unpack the build into `content\csgo_addons\mg_depth_racer\` (`unpack_mg_depth_racer.bat` does it).
2. Open `maps/mg_depth_racer.vmap` in Hammer and build it. Everything is unlit, so there is no light bake.
3. Copy `resource/overviews/mg_depth_racer.txt` into `game\csgo_addons\mg_depth_racer\resource\overviews\` (the radar).

The entity names are Space Racer's, with the script name `depth_racer`. The `point_script` points at
`maps/scripts/depth_racer.vjs`, and the HUD layout is `panorama/layout/custom_game/depth_racer.vxml`.

## 2. What is different

- **Tracks**:

  | Track | What it has | Creatures |
  |---|---|---|
  | Kelp Canyon | A winding canyon through a kelp forest, a chasm jump and a tube | A sea serpent through the chasm |
  | Coral Crown | A stadium round a coral ring; the back straight glides off a reef shelf | A manta ray over the glide |
  | The Wreck | A figure-8 round a sunken liner, through the hull and over it, a jump off the bow | A sea serpent past the bow |
  | Vent Field | A rolling hexagon over hot vents, two jumps on the long straights | A whale over the second jump |
  | Abyss Drop | A spiral up a seamount, then a long glide down into the trench | A whale and a sea serpent in the glide |
  | Lantern Deep | A dark loop with a rail-less ledge and a short glide over a sinkhole | A manta ray over the sinkhole |

- **Sea creatures**:
  - Each one crosses the track at one spot on a fixed cycle, one way and then back. Every client sees the same thing.
  - A sea creature hit shoves the car the way it is swimming, makes it skid and takes shield (whale 24, serpent 22,
    manta 16). In the air it is a smaller shove and the car stops climbing. An Aegis shell blocks it. A car can't be
    hit again for 1 s.
  - Coming up to a crossing while a creature is on it, the bottom line warns you (`SERPENT AHEAD` etc.).
  - Bots hold back and let it pass, except on the run-up to a jump.
- **Glides**: Neon Racer's flight sections. S pulls up, W noses down, A / D steer. Gold rings boost and blue rings charge.
- **Cars**: the voxel cars with dark hulls and glowing team trim.
- **Music**: atmospheric jungle / liquid drum & bass: 'Pressure' (172 bpm) and 'Leviathan' (174 bpm) race loops,
  'Still Water' (half-time 172) in the lobby, and a results sting. Chopped breaks, reese bass, choir pads, Rhodes.

## 3. Speed and track edges (all three games, v0.6.0 / v0.6.1)

Top speeds are 200 km/h higher than in v0.5.0 (+556 units/s). Acceleration, brakes and turning were raised to match.
Ramps throw cars at a flatter angle and gravity is stronger, so jumps land about where they did. Rail and bump damage
start at higher speeds so the faster racing doesn't wreck more cars.

Track edges (v0.6.1): a car in the air higher than the rails (30 units) is no longer held in by them. If it crosses the
edge it is **out of bounds**. It sails off, loses 55 shield and comes back on the centreline where it left the road,
or just past it if that was a gap, ramp or glide. Falling into a gap or off a rail-less edge costs 35 (20 before). A
fast car's jump flattens so that a straight launch lands before the road bends. Leaving the lip at an angle, or being
shoved in the air, can still put you out. Bots line up straight for jumps. Sim: at most 0.5 fly-outs a race per track
with 32 bots.

Source: github.com/skink52/space-racer-cs2. `SPR_THEME=depth sh tools/build_all.sh` builds this addon.
