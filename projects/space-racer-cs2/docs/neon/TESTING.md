# Neon Racer: what to test (v0.5.0, pixel update)

Build `maps/mg_neon_racer.vmap` in Hammer first. Then load the map with `bot_quota 8`.

## N1. Look
- All six tracks show their glowing-line road, rails and pylons, their skyline sky and the grid floor far below.
  Pick tracks with `!vote` or play a few rounds.
- The cars are the voxel cars with near-black hulls and glowing edges. The edges are orange on T, blue on CT, cyan
  before a team is picked and gold for last round's winners. Say if the cars are hard to see on the road.
- The car picker (R) and the loading screen show the new cars.

## N2. Flight sections (Void Hop, about 40 % of the lap; Skyline Dive, about 66 % of the lap)
- When the road ends, the bottom line says `FLIGHT: W DOWN  S UP  HIT THE RINGS`.
- S climbs and W dives (like a plane). With no key pressed you sink slowly. A / D steer.
- Flying into the edge of the gate rings bounces you back and hurts like a rail. You can't fall out.
- Gold rings give a boost and blue rings charge you.
- At the end of a flight the corridor narrows and you land on the road with no big drop.
- Bots fly through the rings too, and their lap times are close to yours.
- The camera follows your height in flight. Say if diving puts the camera inside the track or a gate.

## N3. Music
- The lobby, both race loops and the results sting play, and the loops have no click where they repeat.
- Say if the music is too loud or too quiet next to the effects.
