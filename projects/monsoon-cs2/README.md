# mg_monsoon (CS2) - generator source

> **AI-generated code.** Everything here (map generator, procedural props and textures, HUD and the cs_script) is being written by an AI
> agent (Claude) for skink52's mg_monsoon addon, the second map of the series that started with mg_trenchwarfare.

Status: **in progress, paused** (9 Nov 2026). Resume from [NOTES.md](NOTES.md) ("Resume here"); the design is [docs/DESIGN.md](docs/DESIGN.md).
Nothing has been compiled or tested in CS2 yet.

Needs Python 3 with numpy, scipy, Pillow; Node 18+ for the tests. Run tools from `tools/` (`cd tools`).

| Step | Command |
|---|---|
| layout preview | `python preview_layout.py ../out/layout_preview.png [cell]` |
| props (procedural, baked PBR) | `MV_OUT=<abs path to out/addon> python build_all_props.py [names]` -> `out/addon/models/mv`, `materials/models/mv`, turntables in `preview/` |
| map | `python make_map.py <template or current .vmap> ../out/addon/maps/mg_monsoon.vmap ../out/addon [<previous generated .vmap>]` (everything generated is in vis group `mv_gen`) |
| mesh check | `python check_mesh.py ../out/addon/maps/mg_monsoon.vmap` |
| flat preview of the vmap | `python ../../../tools/vmap_preview.py ../out/addon/maps/mg_monsoon.vmap ../out/vmap_preview.png` |

Layout constants (river, bases, flags, karst, roads, paddies) live in `tools/layout.py` and are shared by the map, the renders and the script data.
`tools/toolkit.json` holds the project settings for the shared tools (prefix `mv`, prop modules, fx stems, skybox).

## Licence

Free for non-commercial use: copy, change, share and run it, including on game servers (donation/VIP servers are fine). Not to be sold, paywalled or built into a paid product or service. Code: [PolyForm Noncommercial 1.0.0](LICENSE). Art, models, sounds and maps: [CC BY-NC 4.0](LICENSE-CC-BY-NC-4.0.txt). See [LICENSE](LICENSE) for third-party parts that keep their own terms (the CC-BY Apache model planned for the US helicopters must be credited as its CREDITS.txt says).

## Shared files

`test/point_script.d.ts`, `test/mock_point_script.mjs` and the toolkit copies in `tools/` (`bake.py`, `build_prop.py`, `build_all_props.py`, `check_mesh.py`, `clean_stale.py`, `dmx.py`, `dmx9.py`, `dump_entities.py`, `ext_smd.py`, `fx_models.py`, `geo.py`, `glb2cs2_multi.py`, `lod_decimate.py`, `make_skybox.py`, `merge_snd.py`, `modelio.py`, `noise.py`, `p_sandbag.py`, `panorama.py`, `hud_check.py`, `loading.py`, `patch_vmap.py`, `placer.py`, `render.py`, `shaders.py`, `sndevents.py`, `split_parts.py`, `stock.py`, `vmaplib.py`, `vmapgen.py`, `vmesh.py`, `vpkdir.py`, `vtexread.py`, `weld_cracks.py`) are master copies from [cs2mapping](https://github.com/skink52/cs2mapping) (`create/libsync.json`). Change them there and run `python create/libsync.py push`.
