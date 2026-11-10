# IRONFRAME (mg_ironframe_*): 64-player mech combat for CS2

> **AI-generated code.** Written by Claude, directed by skink52. Licence: PolyForm Noncommercial 1.0.0 for the code (`LICENSE`),
> CC BY-NC 4.0 for our own art, sounds and maps (`LICENSE-CC-BY-NC-4.0.txt`). Third-party models are credited in `docs/CREDITS.md`
> and are **not** covered by our licence.

Armored Core style third-person mech battles: boost, quick-boost, hover, four hard-points, lock-on and stagger, 64 players in
huge terrain arenas, modular garages with saved progression on the Slime Servers minigame server (SlimeMG `IronFrame` module),
and AI mechs that fill the lobby and run co-op sorties when few people are on.

- Design: [docs/DESIGN.md](docs/DESIGN.md). Seams between the parts: [docs/INTERFACES.md](docs/INTERFACES.md).
- Server contract (map <-> SlimeMG): [docs/SERVER_CONTRACT.md](docs/SERVER_CONTRACT.md).
- Status and handover: [docs/STATUS.md](docs/STATUS.md). Hand tests: [docs/TESTING.md](docs/TESTING.md).
- Parts catalog: [data/parts.json](data/parts.json); model sources: [data/frames.json](data/frames.json).

## Build
```
sh tools/build_all.sh        # IF_ARENA=dunes|sprawl|orbital  IF_CURRENT_VMAP=<the map as last saved in Hammer>
sh tools/deploy.sh           # copies out/addon and out/game into CS2's addon folders (Hammer closed)
```
Then build the map (`C:\source1\cs2port\build_maps.ps1 mg_ironframe_dunes` or Hammer) and load it. The console prints
`[ironframe] v0.1.0 ready: ...` with `MISSING` for anything the script could not find.

Status: **designed and being written; NOT YET TESTED IN CS2.**
