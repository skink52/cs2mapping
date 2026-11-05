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
- **Neon's own E moves** (the cars are Space Racer's; their E ability is different in each game, v0.7.0):
  - HORNET **Light Trail** (20 charge, 10 s): for 2 s you run 6% faster and lay a hard wall of light behind you. A car
    that cuts across it bounces off like a rail (a graze just deflects; square on costs speed and up to 20 shield).
    Your side passes through.
  - METEOR **EMP** (40, 14 s): every enemy within 360 units loses 35 charge, its boost stops and for 0.8 s it can't
    boost, steer well or use E.
  - COMET **Overclock** (30, 14 s): 3 s of free, stronger boost (1.6x); pads and rings kick 1.5x.
  - BASTION **Firewall** (30, 15 s): a wall across a lane and a bit of the road behind you for 2 s. An enemy driving
    through loses a quarter of its speed and 7 shield and skids; it burns out after three. Your side drives through.
  - **Boost trails**: every car boosting on Mouse 1 leaves a short light trail. Cut across one at an angle and you
    skid and lose 1 shield; follow it straight (drafting) and nothing happens.
  - The attacks (Light Trail, EMP, Firewall) unlock 6 seconds after GO, like spin attacks.
- **Cars**:
  - The four cars are Space Racer's voxel cars with near-black hulls.
  - Their glowing trim and edge lines show your side's colour: T orange to red shades, CT blue to cyan shades, gold
    for winners, cyan before a team is picked.
- **Music**: four original electro pieces: two race loops at 124 and 128 bpm, a 96 bpm lobby loop and a results sting.

Source: github.com/skink52/cs2mapping/tree/main/projects/space-racer-cs2. `SPR_THEME=neon sh tools/build_all.sh` builds this addon.

## Server stats (v0.7.0)

The map needs no plugin. With one that understands `mgstat` (SlimeMG), the script reports each human's finishes, podiums, wins,
wrecks dealt during the race and best race and lap times per track. It is off in the build (`CONFIG.SERVER_STATS`); the plugin
switches it on at load (`RunScriptInput mgstat_on` on `spr_script`). Without a plugin the switch stays off and nothing is sent.
