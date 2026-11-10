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
| RadGen (`C:\source2\apps\RadGen.exe`) | Radars in the manual ports | The selection set must be named `radgen_path`. Replaced by `tools/radar.py`. |
| VTFEdit Reloaded / VTFCmd | VTF → PNG in the manual ports | `-output` flattens folders; leave it out. Replaced by `tools/vtf.py`. |
| [cs2-slop-porting](https://github.com/Ninja-Chris/cs2-slop-porting) (`vmap_asset_slop_import.py`, `push_mass.js`) | Reference for porting features | Everything useful in it is now in our pipeline, rewritten (rewritten for our vmap model; the repo had no licence until 29 Oct 2026, now MIT, copyright Ninja-Chris and skink52): static-overlay rebuild and face-scale repair (`tools/texfix.py`), lit additive and non-PCM wav re-encode, stock **stub** material re-port (`vmap_refs.py` + `assets`), **soundscript** names → same-named soundevents (`soundscripts`), **env_steam** particles (`steam`), `cs_mdl_import` watchdog with retries and sidecar check, and the WHY MISSING report (`post_import_cleanup.py`), and mass-based prop pushing (`physpush`, from `push_mass.js`). Its generated sprite particles can override stock particles of the same path, so we never write particles under stock paths (ours go in `particles/port_steam/`). Rechecked 30 Oct 2026 (2.0 / 2026-10-29h and `rebuild_lighting.py`, which bundles our older lighting, visfit and probe passes): taken: delete-and-rebuild of every light from the VMF (`lighting.relight`, now the default in stage C `lights`) and the same colour / HDR / switched-light / style / sun-spread fixes in place (`lightbright`), median brightness for added lights, underwater lights (`watervol`), heat-wave refract -0.007 (`steam`), overlays on brush entities as parented quads (`ovlquads`), dropped-IO report (`droppedio`). Not taken: its bundled copies of our passes (older versions), large-face report. Ninja Chris's newer merged script (`vmap_convert_merged.py`, 2026-10-28j, shared privately, not in the repo) added more face matching, unlit-by-default additive, `$ssbump` conversion and CS2 sound-stub avoidance: reimplemented here 29 Oct. Not taken: `MATCH_MOVED_LEVELS` (whole floors moved together, off by default there), stale displacement texture tables, tangent regeneration. Rechecked 2 Nov 2026 (3.5 / 2026-11-02a): taken: large-face split (`splitfaces`), water probe volume (`waterprobe`), push_mass.js v7 rules (`physpush`), stock env_fire particle + burn trigger_hurt + fire.cpp I/O and env_spark particles (`fire`), vpcf66 particle format (`tools/vpcf66.py`), `(null)` params, trigger material and tool path fixes, faces culled under water, display brushes, origin duplicates (report; delete on request). Not taken (skink52): heal trigger conversion (negative-damage trigger_hurts work in CS2), Source 1 sound falloff, func_breakable render flags, turned textures, keep_ lights, missing-entity / seam reports, parallel model compile, its water pass changes. hurt_zone.js / player_velocity.js are referenced but not in the repo (added 2 Nov). Rechecked 8 Nov 2026 (2026-11-08g; the committed file is two versions pasted together and doesn't parse): taken: fan-to-fan bowtie links in `splitfaces.mesh_write` (Hammer load crash), CS:GO particle names → CS2 particles (`particles`), CS:GO's default door move sound (`doors`), CS2 render mode names (`rendermode`). Everything else, ranked, with what we found in our ports: [cs2-slop-porting-review.md](cs2-slop-porting-review.md). |
| CounterStrikeSharp | Server plugins on the minigame server | Plugins that break script-run games are listed in [cs2-gotchas.md](cs2-gotchas.md#scripts-players-rounds-and-plugins). `VelocityModifier` is the plugin route for player speed. |
| [nvmxre/cs2-ui-kit](https://github.com/nvmxre/cs2-ui-kit) (was cs2-hud-panel) | Reference while debugging Panorama layouts | Its GOTCHAS doc covers root sizing and re-layout. |
| SteamCMD (`C:\steamcmd`) | Downloading GMod workshop items: `steamcmd +login anonymous +workshop_download_item 4000 <id> +quit` | Anonymous works for app 4000. Lands in `steamapps\workshop\contentĀ0\<id>\` as a `.gma` (or a legacy LZMA `.bin`); `create/playermodels/gma.py` extracts both. |
| Blender | FBX export to ModelDoc | Per-material `FBX_vmatPath` property ([../creation/models.md](../creation/models.md)). |
| [Tripo CLI](https://github.com/vast-enterprise/Tripo-API-CLI) (`npm i -g tripo-cli`, 0.10.0) | Text or image → 3D model from the terminal (Tripo V3 API) | Installed on the PC 3 Nov 2026, signed in on the international site (`--region ov`); the key is in `~/.tripo/config.json`. **Use it only when skink52 asks for Tripo by name**: every generation spends account credits. On the PC's PowerShell (scripts disabled) run it as `tripo.cmd`, and install or update with `npm.cmd`; installs from a sandboxed Claude shell don't reach the real npm folder. `tripo doctor` checks the key and API. Earlier Tripo3D models came from the website: decimate them with `create/glbmesh.py`; prompts used for Trench Warfare are in [../../projects/trenchwarfare-cs2/docs/tripo_prompts.md](../../projects/trenchwarfare-cs2/docs/tripo_prompts.md). **Studio instead of the CLI (3 Nov 2026):** the CLI account showed 0 API credits while the studio had 1905, so the roguelike's guardians were made at studio.tripo3d.ai (text mode, HD, H3.1, PBR on, Triangle topology, polycount box set per model: 8000 boss, 4000 turret, 1500 drone; 55 credits each). Exports are GLB with no emissive channel (glow baked into the albedo) and front facing -Y after `glb2cs2_multi.py`'s axis swap, so convert with `--yaw 90` and build a self-illum mask from the glow hue (`projects/cs2-roguelike/tools/import_glb.py --glow cyan`). Any prompt that mentions glyphs or runes comes back with gibberish script painted on: say "no runes, no glyphs, no letters, no text" or it needs a second generation. |

## Other CS2 mapping projects (survey, 10 Nov 2026)

Not used yet; read through the GitHub API (stars, last push, licence, README) by a Claude subagent. The Valve developer wiki blocked the
fetch, so none of its pages were checked.

| Project | What it does | Worth learning or borrowing |
|---|---|---|
| [Rmgs123/cs2-map-mcp](https://github.com/Rmgs123/cs2-map-mcp) (MIT, v1.3.0 Nov 2026; **ported 10 Nov 2026**, see [../creation/guide.md](../creation/guide.md#9-the-cs2-map-mcp-toolset-10-nov-2026-not-the-default-yet)) | MCP server for AI-built CS2 maps: its own lossless DMX v9 codec in Python, FGD-checked entities, resourcecompiler wrapper, launches and plays the map | The closest peer. Its **VConsole2 link (TCP 29000)** sends commands to the running game and reads its console, play-tests with real input, takes screenshots and reads crash dumps: the way to check built maps unattended (and around map echo output missing from console.log). |
| [ValveResourceFormat/Datamodel.NET](https://github.com/ValveResourceFormat/Datamodel.NET) (MIT) | C# DMX library, every binary / kv2 version including binary 9 | An independent check that our vmap writer's output loads; `Tests.VMAP/ValveMap.cs` is a typed vmap schema. |
| [TeamSpen210/srctools](https://github.com/TeamSpen210/srctools) | Python Source 1 formats (VMF, BSP, FGD, DMX up to binary v5) | Its DMX doesn't do v9 (so our own codec is justified); its VMF / FGD / BSP parsers could replace one-off code. |
| [kristiker/keyvalues3](https://github.com/kristiker/keyvalues3) (MIT, PyPI) | Python KV3 text and binary | Its tests: one fixture file per encoding with reader / writer round trips. `vmatc.py` has its own KV3 reader. |
| [craftablescience/sourcepp](https://github.com/craftablescience/sourcepp) / [VPKEdit](https://github.com/craftablescience/VPKEdit) (MIT) | C++ format libraries with Python wrappers (vpkpp, vtfpp, bsppp, kvpp) | Maintained VPK / VTF / BSP readers in place of, or as a check on, `vpk.py`, `vtf.py`, `bsp2vmf_lite.py`. |
| [SteamTracking/GameTracking-CS2](https://github.com/SteamTracking/GameTracking-CS2) | CS2's files on every update: FGDs, `point_script.d.ts`, Valve's cs_script demos | Diff the FGD and the d.ts per update to catch Valve's changes before they break a port or the cs_script notes. |
| [Source2ZE/cs_script](https://github.com/Source2ZE/cs_script) + [cs_script_boilerplate](https://github.com/Source2ZE/cs_script_boilerplate) (MIT) | `@s2ze/types`, math, scheduler packages; rollup template | An MIT types package instead of copying Valve's d.ts; a tested scheduler. |
| [Angel-foxxo/CS2-Workshop-Manager](https://github.com/Angel-foxxo/CS2-Workshop-Manager) (MIT) | Workshop packer / publisher, GUI and CLI | Scripted upload (`upload --id`) and `rules unused` to keep unreferenced files out. We have no scripted publish. |
| [Angel-foxxo/Source2MapCompiler](https://github.com/Angel-foxxo/Source2MapCompiler) (MIT) | resourcecompiler front end: presets per map, map lists, per-stage progress | Its stage-progress parsing, for watchdog heartbeats on map builds. |
| [Source2Wiki](https://github.com/Source2Wiki/Source2Wiki) (source2.wiki; CC BY-SA content) | Community Source 2 wiki: entities, cs_script API, the S2ZE porting guide | Cross-check our gotchas against its Source 1 entity replacement table and quirks pages. |
| [Source2ZE/Port-Vmaps](https://github.com/Source2ZE/Port-Vmaps) (MIT) | Source vmaps of the zombie-escape ports | Real ported vmaps usable as test fixtures. |
| [EasterLee/easter_prefabs](https://github.com/EasterLee/easter_prefabs) (MIT) | Rain, snow and tesla particles, boss HP bar, **underwater overlay** | The underwater overlay, for the water work ([cs2-slop-porting-review.md](cs2-slop-porting-review.md#water-csgos-look-above-and-below-the-surface)). |
| [Angel-foxxo/cs_script-UI](https://github.com/Angel-foxxo/cs_script-UI) (MPL-2.0) | In-world particle UI with a font-atlas baker | The particle text technique. |
| [kristiker/source1import](https://github.com/kristiker/source1import) (MIT, last push Feb 2025) | Source 1 materials, particles, models → Source 2 | Its particle conversion (the S2ZE guide recommends it). |
| [LaplaceTor/cs2-map-importer](https://github.com/LaplaceTor/cs2-map-importer) (GPL-3.0) | GUI around Valve's importer with BSPSource, VPKEdit, VTFEdit | Little: no fixing after the import. |

**How this repo compares.** No other project repairs the vmap after Valve's importer (the others wrap the importer or are manual guides),
nor runs ports unattended with classified leftovers; our in-game-checked gotchas and cs_script mock engine go further than the rest.
Weaker: no unit tests or CI (the parsers above ship round-trip fixture tests), home-grown readers where maintained libraries exist
(VPK, VTF, KV3; the `dmx.py` copies in `tools/` and `create/` are deliberate libsync copies), no pyproject (tools run from fixed PC
paths), in-game checks by hand, little discoverability (no topics or releases; GitHub can't read the licence), and the non-commercial
licence keeps MIT / CC BY-SA projects from taking anything back.

**Ranked improvements** (none started):
1. Round-trip tests for the vmap core (load + save gives identical bytes) and a before / after fixture per stage C step; Datamodel.NET
   as an independent load check; CI.
2. In-game checks over VConsole2, as cs2-map-mcp does: autoport loads the built map, collects missing-resource and script errors,
   takes screenshots.
3. A scheduled diff of GameTracking-CS2's FGD and `point_script.d.ts` to flag stale tables and notes.
4. A scripted Workshop publish step (CS2-Workshop-Manager CLI).
5. Maintained format libraries where they fit, a pyproject, repo topics and a release.

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
