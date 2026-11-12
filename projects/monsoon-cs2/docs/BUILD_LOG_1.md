# mg_monsoon build log 1: first deploy and asset compile (12 Nov 2026)

AI-generated (Claude) for skink52. Stage 1 of the first real CS2 build: deploy, then compile every addon asset **except the map**
(a polish pass was rewriting `out/addon/maps/mg_monsoon.vmap` at the same time). Level reached: assets **compiled** (resourcecompiler,
no errors, no warnings). Nothing here is Hammer verified or in-game verified; the map itself has not been compiled.

CS2 tools mode was closed throughout (the only `cs2.exe` running was the dedicated server from `C:\cs2server`). Every compile ran with
`C:\source1\cs2port` as the working folder. Logs of each run are kept in `out/logs/` (the build script overwrites
`C:\source1\cs2port\logs\mg_monsoon_assets.log` on every run).

## Commands and times

| # | What | Command | Time | Result |
|---|---|---|---|---|
| 1 | Deploy dry run | `python -I tools/deploy_monsoon.py` | seconds | 3114 files to create (1242 MB) + 3 written, 0 replaced; content and game addon folders do not exist yet |
| 2 | Deploy | `watchdog ... -- python -I -u tools/deploy_monsoon.py --apply` | about 1 min | 3114 created, 0 replaced; 3 written (sound events, `addoninfo.txt`, Steam description); `out/deploy/mg_monsoon_deploy_20261112_112209.json` |
| 3 | Asset dry run | `build_maps.ps1 -DryRun assets mg_monsoon` | seconds | up to 571 assets |
| 4 | Asset compile, run 1 | `watchdog --label "mg_monsoon assets" --expect 1800 ... -- powershell ... build_maps.ps1 assets mg_monsoon` | **9 min 19 s** (11:24:22-11:33:41); materials 431 s, models 97 s | wrapper "assets OK", but 5 models failed (below); log `out/logs/mg_monsoon_assets_run1.log` |
| 5 | Fixes, redeploys (5 + 3 + 8 files) | see "Fixed" | | |
| 6 | Asset compile, runs 2-4 | same line | 46 s, 31 s, 31 s | run 4: 0 errors, 0 warnings; `out/logs/mg_monsoon_assets_run4.log` |
| 7 | Forced HUD / script / icon | `resourcecompiler -f -i` on `mg_monsoon.xml`, `.css`, `maps/scripts/mg_monsoon.js`, `map_icon_mg_monsoon.svg` | about 20 s | each `OK: N compiled, 0 failed` (css pulls in 306 images); `out/logs/mg_monsoon_force_compile.log` |

The BUILD.md estimate for the first asset compile (20-40 min) was far too high: 9 min on this PC (332 materials, 193 models).

What is compiled in `game\csgo_addons\mg_monsoon` now: 335 `.vmat_c`, 193 `.vmdl_c`, `mg_monsoon.vxml_c`, `.vcss_c`, `.vjs_c`,
`soundevents_addon.vsndevts_c`, 41 sounds, 302 HUD pictures, 3 loading slides (`mg_monsoon_png`, `_1_png`, `_2_png`), the radar
(`overheadmaps/mg_monsoon_radar_psd.vtex_c`), the map icon (`.vsvg_c`). The four player models compiled with their `csgo_character`
materials with no message.

## Errors and warnings, before and after

| Class | Run 1 | Run 4 | Example | Cause | Status |
|---|---|---|---|---|---|
| Model fails: missing material | 5 models failed (60 `RESOURCE COMPILE ERROR` lines, each also a `content_consider_missing_materials_fatal` note) | 0 | `sandbag_wall_lod0 referencing missing material materials/models/mv/stock/hessian_c.vmat` | the sandbag props (`sandbag_wall`, `_b`, `_128`, `sandbag_low`, `_128`) use the stock hessian materials, which `stock.export_custom` writes, and nothing ever called it | **fixed** |
| `LODGroupList : Only a single LOD group specified, ignoring` | 3 warnings | 0 | `models/mv/ext/rs_bamboo_wall`, `rs_grass_set`, `rs_jungle_bush` | `lod_decimate.vmdl_rewrite` wrote a one-group list when no LOD was worth keeping | **fixed** |
| `FATAL ERROR: ...game\csgo\shaders_pc.vpk Failed to load file (invalid)!` | 1 (the `panorama\*.vtex` pass died before its summary; the radar was not compiled) | 0 | `overheadmaps/mg_monsoon_radar_psd.vtex` | not ours: the compiler failed to open Valve's shader pack once. The same file compiled on run 2 with no change | **gone on rerun**; if it comes back, check the install (Steam "verify") |
| Wrapper exit status | "assets OK" with 5 failed models | "assets OK" | | `build_maps.ps1` only treats uncompiled **materials** as fatal; a failed model is only in the log | documented: read the log, not the wrapper |
| HUD pictures not compiled | 2 | 2 | `board_t.png`, `board_ct.png` | written by `render_board.py`, referenced by nothing (docs/HUD.md) | harmless, by design |
| prop_dynamic on a `static_prop_model` model (would be DELETED at map compile, BUILD.md) | 5 models (checked against the vmap, not a compiler message) | 1 | `quad50_gun`, `rocket_122`, `rocket_rail`, `rocket_tripod`, `shell_105` | `build_prop` always wrote `static_prop_model` | 4 **fixed**; `shell_105` remains (below) |
| Texture size / alpha / power-of-two, bad vmdl keys, physics hulls, sound, script compile | 0 | 0 | | | none seen |

`Leaked KeyValues blocks: 605` after each pass is the compiler's own shutdown note, not about our files.

## Fixed (generators changed, assets rebuilt, redeployed, recompiled)

- `tools/stock.py`: new `ensure(outdir, vmats)` writes the missing stock copies (`export_custom(only=...)` / `export_bark`);
  `tools/build_prop.py` calls it for every prop that uses a stock material. Wrote `materials/models/mv/stock/hessian{,_b,_c}.vmat`
  + `default_cloth001_{color,normal}.png` (decoded from the game's `pbr_defaults` cloth). The sandbag vmdls did not change.
- `tools/vtexread.py`: with no `CS2_VPK_DIR` it now reads the install's `game\csgo\pak01_dir.vpk` (the old default was a
  cloud-workspace path, so the exporters could not run on the PC).
- `tools/lod_decimate.py`: no `LODGroupList` when only one mesh is kept. The three affected vmdls had the block removed in `out/addon`
  (the same text the fixed tool writes) rather than re-running the conversions.
- `tools/build_prop.py` + spec key `dynamic`: `model_archetype ""`, `primary_associated_entity "prop_dynamic"`. Set on
  `quad50_gun` (`p_guns.py`) and `rocket_122`, `rocket_rail`, `rocket_tripod` (`p_arty.py`), which the vmap places only as
  `prop_dynamic`; those four props were rebuilt (`build_all_props.py quad50_gun rocket_122 rocket_rail rocket_tripod`, 46 s).

## Remains

- **`shell_105` is used both ways**: 2 `prop_static` (dressing) and 13 `prop_dynamic` (`mv_shell_1` ..., the script's shells). One vmdl cannot
  have both archetypes. Fix for the owner of `mv_entities.py` / `mv_places.py`: a `shell_105_dyn` twin like
  `mv_models.ensure_dyn()` does for the crash hulk, and the prop_dynamic entities pointed at it. Until then, look for `DELETED` next to
  the shell entities in the map build log.
- Not yet known whether a `prop_dynamic` on a `static_prop_model` is really dropped by this compiler version; BUILD.md says so and the
  fix follows it. The map compile (step 11) will tell.
- `create/libsync.py check` lists `build_prop.py`, `stock.py`, `lod_decimate.py` and `vtexread.py` in this project as differing from
  their `create/` masters: pull the changes into `create/` (and push) before committing.
- The map (`maps/mg_monsoon.vmap`, `mg_monsoon_3dskybox.vmap`) was deployed as generated at 11:22; the polish pass will change it.
  Deploy again before the map compile.
