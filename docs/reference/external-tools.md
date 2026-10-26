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
| [cs2-slop-porting](https://github.com/Ninja-Chris/cs2-slop-porting) (`vmap_asset_slop_import.py`, `push_mass.js`) | Reference for texture porting | Its static-overlay rebuild and face-scale repair are reimplemented in `tools/texfix.py`. It also does things our pipeline doesn't (no licence on that repo, so not copied): checks assets against the CS2 VPK and re-ports CS2 materials that ship as **stubs** (error shader, no textures); converts Source 1 **soundscript** names used by entities into same-named soundevents; builds **env_steam** particles from the entity keyvalues (heat-wave type as a refracting sprite); retries `cs_mdl_import` with hang detection; explains each missing asset (who referenced it, same-name files elsewhere). Its generated sprite particles can override stock particles of the same path, so they're off by default. `push_mass.js` makes players push physics props by prop mass from cs_script (props named `push_<mass>_<name>`). |
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
