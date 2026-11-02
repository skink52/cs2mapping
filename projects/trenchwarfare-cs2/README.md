# mg_trenchwarfare (CS2) - generator source

> **AI-generated code.** Everything here (map generator, procedural props and textures, HUD and the cs_script) was written by an AI
> agent (Claude) for skink52's mg_trenchwarfare addon.

Needs Python 3 with numpy, scipy, Pillow; Node 18+ for the tests.

| Step | Command |
|---|---|
| props (procedural, baked PBR) | `python3 tools/build_all_props.py [names]` -> `out/addon/models/tw`, `materials/models/tw`, previews in `preview/` |
| downloaded glb models | `python3 tools/glb2cs2_multi.py <file.glb> out/addon <name> --length <units>` -> `models/tw/ext/<name>` |
| map | `python3 tools/make_map.py <current .vmap> out/addon/maps/mg_trenchwarfare.vmap out/addon` (terrain is in the map itself, ~47 MB vmap; everything generated is in vis group `tw_gen`, so re-running on a map edited in Hammer only replaces that group) |
| targeting screens, radar, paper map | `python3 tools/render_top.py out/addon out/game` |
| HUD | `python3 tools/tw_hud.py out/addon` |
| sounds | `python3 tools/sounds.py out/addon <template soundevents_addon.vsndevts>` |
| script | `src/mg_trenchwarfare.js` -> `out/addon/maps/scripts/` |
| entity dump for tests | `python3 tools/dump_entities.py out/addon/maps/mg_trenchwarfare.vmap out/entities.json` |
| tests | `node test/mock.mjs 32 120` (mock cs_script run), `cd test && tsc -p tsconfig.json` (types) |

Layout constants (trench lines, mortar pits, hangars...) live in `tools/layout.py` and are shared by the map, the renders and the script data.

## Licence

Free for non-commercial use: copy, change, share and run it, including on game servers (donation/VIP servers are fine). Not to be sold, paywalled or built into a paid product or service. Code: [PolyForm Noncommercial 1.0.0](LICENSE). Art, models, sounds and maps: [CC BY-NC 4.0](LICENSE-CC-BY-NC-4.0.txt). See [LICENSE](LICENSE) for third-party parts that keep their own terms.

## Shared files

`test/point_script.d.ts`, `tools/bake.py`, `tools/check_mesh.py`, `tools/dmx.py`, `tools/dmx9.py`, `tools/geo.py`, `tools/lod_decimate.py`, `tools/noise.py`, `tools/p_sandbag.py`, `tools/render.py`, `tools/shaders.py`, `tools/vmaplib.py`, `tools/vmesh.py`, `tools/vpkdir.py`, `tools/weld_cracks.py` are master copies from [cs2mapping](https://github.com/skink52/cs2mapping) (`create/libsync.json`). Change them there and run `python3 create/libsync.py push`, or if a fix lands here first, `libsync.py pull` it into cs2mapping. `libsync.py check` shows drift.

`sync_repo.sh` (working folder → this checkout) never deletes, copies only newer changed files, and never touches README.md, NOTES.md, the licences or the shared files above: edit those in the checkout.
