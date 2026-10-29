# Outside tools and references

Everything used alongside this repo that isn't ours, what it was used for, and the traps found. Our own tools are listed in
[../../tools/README.md](../../tools/README.md) (porting) and [../../create/README.md](../../create/README.md) (creation).

## Valve (ships with CS2 Workshop Tools)

| Tool | Used for | Notes |
|---|---|---|
| `import_map_community.py` (`game\csgo\import_scripts`) | CS:GO VMF/BSP → CS2 addon | Needs a CS:GO legacy install as the first argument, `vpk.signatures` renamed, no spaces in paths, waits for Enter (patched by `scripts/make_import_map_auto.py`). See [cs2-gotchas.md](cs2-gotchas.md#valves-importer). |
| `cs_mdl_import.exe` | CS:GO `.mdl` → `.vmdl` | Use an explicit file list (`-l`); mdl/vtx checksum mismatches crash the batch; player models drag in whole animation sets (skipped by `post_import_cleanup.py`). |
| `resourcecompiler.exe` (`game\bin\win64`) | Command-line map and asset builds | Hammer's full-build arguments and the outroot copy are in [../porting/pipeline.md](../porting/pipeline.md#stage-d-command-line-build-build_mapsps1); `-f -i <file>` compiles one asset. Logs are UTF-16LE. |
| Hammer 5, ModelDoc, Particle Editor | Editing, model compile, particle re-save | Close Hammer before a script edits the map. ModelDoc rotates SMDs 90° and drops boneless bones ([../creation/models.md](../creation/models.md#modeldoc-traps-verified)). |
| `point_script.d.ts` | cs_script API types | Copy in `create/test/`; used by `tscheck.sh` and the mock engine. |

## Community tools

| Tool | Used for | Notes |
|---|---|---|
| [BSPSource](https://github.com/ata4/bspsrc) | Decompiling CS:GO BSPs with embedded files | Run as a jlink image on Java 21 (`tools/setup_bspsrc.sh`). |
| [Source 2 Viewer](https://valveresourceformat.github.io/) (VRF, incl. CLI) | Decompiling stock models (agents, weapons), dumping compiled blocks (`-b PHYS`, `-b DATA`) | The **dev build** (s2v.app) is needed for `weapons.vdata_c` ("Unknown KVType 26" otherwise). Use Decompile & Export. |
| Hammer5Tools | Loading-screen text and images | Its Loading Editor layout is what `pipeline.md` writes by hand. |
| RadGen (`C:\source2\RadGen.exe`) | Radars in the manual ports | The selection set must be named `radgen_path`. Replaced by `tools/radar.py`. |
| VTFEdit Reloaded / VTFCmd | VTF → PNG in the manual ports | `-output` flattens folders; leave it out. Replaced by `tools/vtf.py`. |
| [cs2-slop-porting](https://github.com/Ninja-Chris/cs2-slop-porting) (`vmap_asset_slop_import.py`, `push_mass.js`) | Reference for porting features | Everything useful in it is now in our pipeline, rewritten (no licence on that repo, so nothing copied): static-overlay rebuild and face-scale repair (`tools/texfix.py`), lit additive and non-PCM wav re-encode, stock **stub** material re-port (`vmap_refs.py` + `assets`), **soundscript** names → same-named soundevents (`soundscripts`), **env_steam** particles (`steam`), `cs_mdl_import` watchdog with retries and sidecar check, and the WHY MISSING report (`post_import_cleanup.py`), and mass-based prop pushing (`physpush`, from `push_mass.js`). Its generated sprite particles can override stock particles of the same path, so we never write particles under stock paths (ours go in `particles/port_steam/`). Rechecked 29 Oct 2026: no new commits since 26 Oct. Ninja Chris's newer merged script (`vmap_convert_merged.py`, 2026-10-28j, shared privately, not in the repo) added more face matching, unlit-by-default additive, `$ssbump` conversion and CS2 sound-stub avoidance: reimplemented here 29 Oct. Not taken: `MATCH_MOVED_LEVELS` (whole floors moved together, off by default there), stale displacement texture tables, tangent regeneration. |
| CounterStrikeSharp | Server plugins on the minigame server | Plugins that break script-run games are listed in [cs2-gotchas.md](cs2-gotchas.md#scripts-players-rounds-and-plugins). `VelocityModifier` is the plugin route for player speed. |
| [nvmxre/cs2-hud-panel](https://github.com/nvmxre/cs2-hud-panel) | Reference while debugging Panorama layouts | Its GOTCHAS doc covers root sizing and re-layout. |
| Blender | FBX export to ModelDoc | Per-material `FBX_vmatPath` property ([../creation/models.md](../creation/models.md)). |

## Assets and media

| Source | Used for | Notes |
|---|---|---|
| [CMU Motion Capture](http://mocap.cs.cmu.edu/) (BVH via github.com/Shriinivas/cmubvh) | Puppet Brawl kicks and punches | Free to use. 120 Hz takes. Takes and retargeting method in [../creation/models.md](../creation/models.md#animated-rigs-puppet-brawl). The BVH cache lives in the session's temp folder, so a new session has to fetch the takes again. |
| Sketchfab (CC-BY models) | GLB props, aircraft | Credit author + licence in the vmdl comment and `CREDITS.md`. Avoid game rips. |
| Freedoom | Hellmatch levels, sprites, sounds | BSD; licence text in the Workshop description; don't use the name to endorse. |
| libADLMIDI (Nuked OPL3, DMXOPL3 bank) | Rendering MIDI music | MIT bank. Hellmatch: `adlmidiplay` bank 72 (DMXOPL3) with 2 emulated OPL3 chips so notes don't drop; then two-pass `loudnorm I=-16:TP=-1.5:LRA=11` in ffmpeg. |
| Playwright + headless Chromium (software GL) | Rendering previews of models and Panorama HUDs without the game | `chromium.launch(args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])`; the page sets `document.title = "done"` when drawn (Hellmatch `preview/`). Panorama-to-HTML translation doesn't model Panorama's alignment rules. |
| ffmpeg, gifsicle | Trailers, GIFs, audio analysis | |
| TypeScript (`npm i -g typescript`) | Type-checking cs_script | |
