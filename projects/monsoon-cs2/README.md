# mg_monsoon (CS2) - generator source

> **AI-generated code.** Everything here (map generator, procedural props and textures, HUD and the cs_script) is being written by an AI
> agent (Claude) for skink52's mg_monsoon addon, the second map of the series that started with mg_trenchwarfare.

Status (12 Nov 2026): the map, its 3D skybox and the assets are **compiled**; the script (mv-0.5) is **simulated** on the mock
engine. Nothing has been opened in Hammer or loaded in CS2, so nothing is in-game verified. Resume from [NOTES.md](NOTES.md)
("Resume here"); the design is [docs/DESIGN.md](docs/DESIGN.md); build and first launch: [docs/BUILD.md](docs/BUILD.md).

**Not ready for the public Steam Workshop.** The current build places models converted from Garry's Mod Workshop packs (mostly
commercial-game rips) and four GMod player models: fine for skink52's private server, not for a public upload. What to drop or swap,
and what `MV_NO_EXT=1` does and does not remove: [docs/WORKSHOP_COMPLIANCE.md](docs/WORKSHOP_COMPLIANCE.md).

Release docs (the first four ship in both addon folders through `tools/deploy_monsoon.py`): [docs/README_MONSOON.md](docs/README_MONSOON.md)
(setup and how it plays), [docs/TESTING_MONSOON.md](docs/TESTING_MONSOON.md) (the in-game checklist), [docs/CREDITS.md](docs/CREDITS.md),
[LICENSE](LICENSE) + [LICENSE-CC-BY-NC-4.0.txt](LICENSE-CC-BY-NC-4.0.txt); the Workshop text
[docs/WORKSHOP_DESCRIPTION.txt](docs/WORKSHOP_DESCRIPTION.txt) (copied to `mg_monsoon STEAM DESCRIPTION.txt` in the content addon);
[docs/SERVER_ISSUES.md](docs/SERVER_ISSUES.md).

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

Free for non-commercial use: copy, change, share and run it, including on game servers (donation/VIP servers are fine). Not to be sold, paywalled or built into a paid product or service. Code: [PolyForm Noncommercial 1.0.0](LICENSE). Art, models, sounds and maps: [CC BY-NC 4.0](LICENSE-CC-BY-NC-4.0.txt). See [LICENSE](LICENSE) for third-party parts that keep their own terms: the CC-BY Apache model flown by the US side must be credited as [docs/CREDITS.md](docs/CREDITS.md) says, and the converted Garry's Mod Workshop models and player models are not licensed to anyone by this repo.

## Shared files

`test/point_script.d.ts`, `test/mock_point_script.mjs` and the toolkit copies in `tools/` (`bake.py`, `build_prop.py`, `build_all_props.py`, `check_mesh.py`, `clean_stale.py`, `dmx.py`, `dmx9.py`, `dump_entities.py`, `ext_smd.py`, `fx_models.py`, `geo.py`, `glb2cs2_multi.py`, `lod_decimate.py`, `make_skybox.py`, `merge_snd.py`, `modelio.py`, `noise.py`, `p_sandbag.py`, `panorama.py`, `hud_check.py`, `loading.py`, `patch_vmap.py`, `placer.py`, `render.py`, `shaders.py`, `sndevents.py`, `split_parts.py`, `stock.py`, `vmaplib.py`, `vmapgen.py`, `vmesh.py`, `vpkdir.py`, `vtexread.py`, `weld_cracks.py`) are master copies from [cs2mapping](https://github.com/skink52/cs2mapping) (`create/libsync.json`). Change them there and run `python create/libsync.py push`.
