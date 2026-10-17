# mg_50arenas

| | |
|---|---|
| Status | Ported 13 Oct 2026, not published: a CS2 port by someone else exists |
| Imported | 2026-10-13 |
| Map last changed | 2026-10-13 |
| How | manual, with a generated map script (`convert_a50.py`) |

50 small arenas in sky bubbles (the spawn teleporters send both teams to one of them), with Simon-says weapons, super powers, gravity and HP modes, and random player skins. existing_ports.txt lists mg_50arenas as an `[ext. port]` ([3571758583](https://steamcommunity.com/sharedfiles/filedetails/?id=3571758583)), so this port wasn't published.

## History

- 2026-10-13 (05:51 to the evening): sky `sky56` + moondome; 13 music soundevents; the 33 SetModel VScripts → script `Model_<name>` using CS2 agents, and the Green Power Ranger rebuilt on the CS2 skeleton (only the first player to touch the round-start trigger gets it, as in the original); 55 "EFFECT" screen overlays → colour-tint post-processing (the T2/T3 warp has no CS2 equivalent); 100 func_wall_toggle → func_brush; `sm_cvar X` → `X`. The moondome was rebuilt as 53 boxes, one per bubble, with vis hints per arena.
- 2026-10-13: a stale copy of the map's asset reference list inside the vmap still named the old VScripts, ambient_generics and screen overlays, so Hammer kept reporting them. It was rebuilt from the real entities.
- 2026-10-13: Lowest-only hints made walls vanish a few steps back (16:28), and Low gave about 1.6 million regions, because the 53 boxes add up to about 60 times a normal map's volume. The arena hints went to Lower (`hintType` 8). VIS3 still ran 30+ min.

## Import report

(`post_import_cleanup.py` report in this folder)

- Models - failed to import: 29
- Models - failed to compile: 4

## Scripts

- [`scripts/a50_io.js`](scripts/a50_io.js) - every replacement listed in its header: names, alpha/colour/scale, speed, strip, HP, teleporter destinations, agent models, intro overlay, screen tints, the spawn strip and round-end outputs

## Open / to check

- The build with Lower hints is untested, and shrinking the oversized bubble boxes was the next step for vis.
- func_dustmotes weren't recreated.
