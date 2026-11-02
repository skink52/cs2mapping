# Neon Racer for CS2: setup and how it plays

Neon Racer is Space Racer's game in a new look. It is a 32-car anti-grav racer run by the cs_script
`maps/scripts/neon_racer.js`, with no server plugins and up to 64 players in two arenas. It has six new tracks, two of
them with **flight sections**, Space Racer's pixel-art style in neon colours and electro / synthwave music. Rules,
controls, chat commands, rounds and kill credit are the same as Space Racer's (see Space Racer's README_ADDON.md). The
map name is `mg_neon_racer`.

## 1. Install and build

1. Unpack the build into `content\csgo_addons\mg_neon_racer\` (`unpack_mg_neon_racer.bat` does it).
2. Open `maps/mg_neon_racer.vmap` in Hammer and build it. Everything is unlit, so there is no light bake.
3. Copy `resource/overviews/mg_neon_racer.txt` into `game\csgo_addons\mg_neon_racer\resource\overviews\` (the radar).

The entity names are Space Racer's, with the script name `neon_racer`. The `point_script` points at
`maps/scripts/neon_racer.vjs`, and the HUD layout is `panorama/layout/custom_game/neon_racer.vxml`.

## 2. What is different from Space Racer

- **Tracks**:

  | Track | What it has |
  |---|---|
  | Grid Circuit | Flat out, with a chicane and a tube |
  | Pulse City | Two hairpins round a notch, and a jump |
  | Void Hop | A flight across the void, and a rail-less stretch |
  | Data Stream | A rolling three-lobed loop, with a tube |
  | Skyline Dive | A spiral climb, then a long diving flight through a canyon of gates |
  | Overclock | A figure-8 with a bridge and a tube |

- **Flight sections**:
  - The road ends and the car flies down a corridor of gates.
  - Like a plane: S pulls up (climbs), W noses down (dives) and A / D steer. Thrust is always on, and boost, spin and E still work.
  - The corridor's edge bounces you like a rail. The corridor narrows at the end so you come down onto the road.
  - Gold rings are boost pads. Blue rings charge you.
  - The Hornet's Seeker Bolt climbs and dives after its target.
- **Cars**:
  - The four cars are Space Racer's voxel cars with near-black hulls.
  - Their glowing trim and edge lines show your side's colour: T orange to red shades, CT blue to cyan shades, gold
    for winners, cyan before a team is picked.
- **Music**: four original electro pieces: two race loops at 124 and 128 bpm, a 96 bpm lobby loop and a results sting.

Source: github.com/skink52/space-racer-cs2. `SPR_THEME=neon sh tools/build_all.sh` builds this addon.
