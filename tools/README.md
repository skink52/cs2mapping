# tools: index of the cs2port pipeline files

> **AI-generated code.** These tools were written by Claude (an AI agent) for skink52's CS:GO to CS2 map ports, not hand-written.

This is the list of every file in `tools/`, with what it does and how to run it. **How the stages fit together, what each fix does and the
order to run things in is in [docs/porting/pipeline.md](../docs/porting/pipeline.md)** (start with its "Quick start for an agent").
Where each file goes on the PC: [docs/porting/setup.md](../docs/porting/setup.md). On the PC this file is
`C:\source1\cs2port\tools\README.md`; the pipeline reference is `C:\source1\cs2port\cs2_port_pipeline.md`.

Everything runs in Claude's cloud workspace with Python 3 + numpy, scipy and Pillow. `<root>` is the working root that mirrors the PC
(layout in [setup.md](../docs/porting/setup.md#cloud-workspace)).

## Entry points (command line)

| File | What it does | Usage |
|---|---|---|
| `prep.py` | **Stage A.** BSPSource decompile, addon name cleaning, Hammer re-save fix, func_illusionary → func_brush, embedded files laid out at their PC paths, materials/models zipped into `assets\<addon>[.N].zip` (≤ 14 MB each), addon skeleton from `addon_template/`, and `manifest.json` (staged path → PC path pairs for `device_commit_files`) | `OUT=<dir> BSPSRC=<bspsrc.sh> python3 prep.py <bsp> [<bsp>...] [bspname=addonname ...] [--ports=existing_ports.txt]` (env `PORTS=` = `--ports=`; defaults `OUT=./prep_out`, `BSPSRC=tools/bspsrc.sh`) |
| `stage_c.py` | **Stage C.** Prefab merge + every post-import fix on the `.vmap` (step keys below). Writes `<root>/out/<addon>/`, `<root>/out/<addon>_game/` and `<root>/out/<addon>_result.json` | `python3 stage_c.py <addon> <root>` |
| `run_pass.py` | Any stage C step(s) on the current, already-cleaned vmap; appends to the cleanup log | `python3 run_pass.py <addon> <root> step[,step...]` (stage C step keys) |
| `run_c.py` | Stage C when CS2's `pak01_dir.vpk` isn't staged (stub VPK). Default steps leave out `alpha`, `assets` (need the VPK) and `doors`, `overlayfix`, `facescale`, `matflags`, `probes` (run those later with `run_pass.py`) | `python3 run_c.py <addon> <root> [step,...]` |
| `stage_d.py` | Follow-up passes on a map you've already edited in Hammer (keeps your edits) | `python3 stage_d.py <addon> <root> pass[,pass...]` (passes below) |
| `ports.py` | `existing_ports.txt` helpers: duplicate check (ignores prefixes, `_cs2`, version suffixes) and adding a line | `python3 ports.py check <existing_ports.txt> <name>...` · `python3 ports.py add <existing_ports.txt> <name> [status] [mapper]` (default `[in progress] [skink]`) |
| `hammer_resave.py` | What a CS:GO Hammer open/save changes in a BSPSource VMF (prep.py calls it) | `python3 hammer_resave.py <in.vmf> <out.vmf>` |
| `disprestore.py` | Rebuilds displacements the importer dropped ("Found a displacement missing a needed subkey.") from the BSP | `python3 disprestore.py <vmap in> <bsp> <vmap out> [x0,y0,z0,x1,y1,z1 ...]` (skip boxes) |
| `laserhurt.py` | A `trigger_hurt` along every CS:GO env_laser that did damage and has none (after stage C) | `python3 laserhurt.py <vmap in> <csgo vmf> <vmap out>` |
| `glowfix.py` | Parented env_particle_glows → following glow particles | `python3 glowfix.py <vmap in> <vmap out> <addon content root>` |
| `waterblend.py` | Main-map water fades into the 3D skybox water (decompiled stock water with MapUV + fade, sea bed cut back, skybox sea bed lowered, skybox probe volumes over the water) | `python3 waterblend.py <main.vmap> <skybox.vmap> <main out> <skybox out> <addon content root> <name> <cs2 pak01_dir.vpk> [fade]` |
| `gibfix.py` | Build log `Failed loading resource` → refs file of missing gib models / model materials for `run_fixrefs.bat`; generic CS:GO chunks for vmdls with a Metal/Wooden/Glass propdata base and no gibs | `python3 gibfix.py <build log> <out refs.txt> [addon .vmdl ...]` |
| `vmatc.py` | Compiled vmat_c (KV3 v5, LZ4/zstd) → editable vmat (g_ params, textures as `.vtex_c`) | `python3 vmatc.py <pak01_dir.vpk> <materials/...vmat> <out.vmat>` (the pak01_NNN.vpk next to the dir file) |
| `skysplit.py` | Old 3D skybox → its own `<map>_3dskybox.vmap` + `skybox_reference` in the main map (after stage C) | `python3 skysplit.py <map.vmap in> <main out> <skybox out> <map name> [x0,y0,z0,x1,y1,z1]` · `python3 skysplit.py --sky <in> <out>` (moondome shells → toolsskybox only) |
| `matnames.py` | Importer-sanitised material refs (spaces → underscores) back to the real file names; run before `alpha,assets` | `python3 matnames.py <addon> <root>` (needs `<root>/content_files_<addon>.json`) |
| `bsp2vmf_lite.py` | Minimal VMF from a CS:GO BSP (every brush side with material + uaxis/vaxis from the texinfo, infodecals, info_overlays) and the BSP's embedded files, for `texfix` passes when the decompiled VMF isn't available | `python3 -I bsp2vmf_lite.py <map.bsp> <root>/source1/maps/<addon>.vmf [<root>/embedded/<addon>]` |
| `vmap_preview.py` | Top-down + four corner renders of any vmap (binary or importer text) | `python3 vmap_preview.py <map.vmap> <out.png> [x0,y0,z0,x1,y1,z1]` |
| `setup_bspsrc.sh` | Extracts BSPSource from its jlink image and patches the class files to Java 21; writes `<dest>/bspsrc.sh` | `sh setup_bspsrc.sh <staged bspsrc-windows/lib/modules> <dest dir>` (use `<dest>` = `tools/` so prep.py finds it, or set `BSPSRC=`) |

### Stage C step keys (run order, from `stage_c.run()`)

`merge, io, wall, equip, launch, push, cmd, roundcfg, score, speed, gravity, dead, renderamt, steam, sounds, soundscripts, doors, overlays, overlayfix, facescale, sky, skyvis, vis, beams, lights, alpha, probes, radar, assets, matflags`,
plus `overlaydepth` (= `overlayfix` + projection depth 8) and `physpush` (opt-in) when named. `vis` runs `visfit.py`; `skyvis` (the older shell-only pass) runs only when `vis` isn't in the list.
`alpha` and `assets` need `<root>/vpk/cs2_pak01_dir.vpk` and are skipped silently without it. `daylight` is **not** a stage C step.

### stage_d.py passes

`beams, lights, lightbright, alpha, radar, daylight, skyvis, visfit, visfit_lower, visfit_lean, gravity, equipitems, overlayfix, overlaydepth, facescale, matflags, probes, probecover, steam, soundscripts, physpush, gameui, physlaunch, renderamt, ventlight, doorsolid, doorhinge, iofix, tesla, overlays, skyshell, water`.
Name differences from stage C: stage C's `vis` is stage D's `visfit`. `radar` here uses the default `pct=0.5`; for another value call
`radar.run(m, c, pct=0, tex=radar.textures_for(c))` from Python (there's no CLI flag). sky, sounds, doors, assets, equip and the other stage C
steps aren't stage D passes: use `run_pass.py`.

## Passes (library modules called by stage C / D)

| File | Step / pass | What it does |
|---|---|---|
| `gen_script.py` | (end of stage C) | Builds `maps/scripts/<addon>_io.js`: `Cmd_`, `Score_`, `Speed_`, `Gravity_`, `Item_`/`ItemAll_` inputs, spawn equips, physics pushing, plus `push_tail.js` for push zones (`PushIn_`/`PushOut_`) |
| `push_tail.js` | `push` | The trigger_push half of the generated io script (holds CS:GO "set speed" pushes, max 3500); appended by gen_script.py |
| `gravity.py` | `gravity` | trigger_gravity → trigger_multiple + script `Gravity_<scale>`; stage D patches the existing `_io.js` |
| `assets.py` | `alpha`, `assets` | Missing materials rebuilt from CS:GO's VPK (also stock CS2 stubs listed in `maps/<addon>_stub_materials.txt`), water → `liquids/nuke_water`, closest stock CS2 material otherwise; alpha-test/translucent masks |
| `soundscripts.py` | `soundscripts` | Source 1 soundscript names used by entities / door noises → same-named soundevents (map soundscripts, then CS:GO's manifest) |
| `steam.py` | `steam` | env_steam → info_particle_system + generated `particles/port_steam/*.vpcf` (heat wave = refracting sprite) |
| `gameui.py` | `gameui` (D) | game_ui → key poll in the io script (`GameUIOn_`/`GameUIOff_` inputs fire the original outputs); game_ui entities removed |
| `physlaunch.py` | `launch` (C, before `push`), `physlaunch` (D) | Physics-only trigger_push launchers (cannons: relay ForceSpawns a template ball, Enables the push for a moment) → `Launch_<pusher>` in the io script puts the ball at the muzzle and fires it (2000 u/s) |
| `watervol.py` | `water` (D) | Water meshes → func_water (touching ones grouped); underwater post_processing_volume from 16 u under the bottom to 80 u below the surface; master post_processing_volume if none |
| `postprocess_filmic_underwater.vpost` | template | Underwater post-processing (from ba_jail_seaside), copied to `lighting/postprocessing/` by the `water` pass |
| `doorsolid.py` | `doorsolid`, `doorhinge` (D) | Doors flagged Non-solid to Player: meshes → never-solid func_brush parented to the door, door keeps a nodraw hinge cube set 2 u into the frame (`doorhinge` moves the cube on maps already done) |
| `ventlight.py` | `ventlight` (D) | Stationary lights in crawl-space ducts behind func_breakable vent grates; covers get Disable Shadows |
| `tesla.py` | `tesla` (D) | point_tesla (not in CS2) → info_particle_system with a generated crackle particle (`particles/port_tesla/`), TurnOn/DoSpark/TurnOff → Start/Stop |
| `restore_ents.py` | `python3 tools/restore_ents.py <in.vmap> <map.vmf> <out.vmap> <name> [...]` | Puts back named entities the importer dropped, from the decompiled VMF, cloning a same-class CS2 entity as the template (ttt_cg_skyscraper_2017's 1-unit btn1/btn3) |
| `physpush.py` | `physpush` (opt-in) | Players push physics props (and func_physbox, mass from its size) by CS:GO `.phy` mass, from the io script (`patch_script` adds it to an existing `_io.js`) |
| `texfix.py` | `overlayfix`, `overlaydepth`, `facescale`, `matflags` | Static overlay geometry, brush-face texture scale/shift (match order in pipeline.md), `$additive`/`$nocull`/`$ssbump`/`$alpha`/`$selfillum`/water material fixes |
| `sky.py` | `sky` | Six CS:GO sky faces → 2:1 equirect panorama for `sky.vfx` / `csgo_moondome` |
| `visfit.py` | `vis` (C), `visfit`/`visfit_lower`/`visfit_lean` (D) | Vis hints fitted to the play space (Low / Lower / one Lowest) and sky shells out of vis |
| `skyvis.py` | `skyvis` | Older pass: sky shells that seal nothing get Exclude from Vis |
| `beams.py` | `beams` | env_laser / env_beam → never-solid func_brush beams (damage: `laserhurt.py`) |
| `lighting.py` | `lights`, `lightbright` (D) | Minimal set of Stationary lights per sealed compartment, max 4 overlapping; importer `brightness = nan` set to 0 (stage C) or rebuilt from the VMF `_light` values (`lightbright`) |
| `probecover.py` | `probes` (C, report) / `probecover` (D, fix) | Static func_breakable / func_brush meshes outside every light probe volume: listed in TO CHECK, or a volume added around each uncovered group |
| `daylight.py` | `daylight` (D only) | Stationary sun, ceilings without shadows, probe volumes, maxexposure 2 for dark indoor maps |
| `radar.py` | `radar` | Radar png + vtex + `resource/overviews/<map>.txt` from the standable floors, painted with their materials |
| `radartex.py` | (radar, vmap_preview) | Material name → tiled source texture or a colour guessed from the name |

## Libraries

| File | What it is |
|---|---|
| `vmapedit.py` | `.vmap` editing. `m = V.Map(path)`; `m.entities()`, `m.by_class('cls', ...)`, `m.P(e, key)` / `m.setp(e, key, val)` / `m.delp`, `m.name(e)`, `m.origin(e)`, `m.new_entity(cls, origin, props)`, `m.add_conn(e, output, target, input, param, delay)`, `m.all_conns()`, `m.remove_node(e)`, `m.prune()`, `m.dumps()` / `m.save(path)` |
| `dmx.py` | Binary DMX (encoding binary 9), the `.vmap` format: `dmx.load/loads/dumps`, `get/set_/delete` on elements. (Other DMX code: `create/dmx.py` is the lossless reader/writer for original maps, `tools/weapons/dmx.py` handles ModelDoc mesh DMX.) |
| `kv2.py` | Keyvalues2 text DMX (what Valve's importer writes for the main vmap) → `dmx.Doc` |
| `vmf.py` | Source 1 VMF parser/writer (`vmf.parse(text)`, `Node.get/set/ch`, `vmf.dump`) |
| `vpk.py` | VPK v1/v2 directory reader (stock file lists, CS:GO VMT/VTF extraction) |
| `vtf.py` | Top-mip VTF decoder → PIL image |

## Data files

| File | Used by |
|---|---|
| `box_template.vmap` | stage C sky pass: the moondome box mesh for dropped sky brushes (our own file) |
| `laser_template.vmap` | `beams.py`, `laserhurt.py`: the beam / hurt-box mesh (our own file) |
| `addon_template/` | **Not in the repo** (Valve's files). `prep.py` needs `tools/addon_template/content/` and `game/`: copy them from `<CS2>\content\csgo_addons\addon_template\` and `<CS2>\game\csgo_addons\addon_template\` (what the Workshop Tools launcher copies when it creates an addon) |
| `bspsrc.sh` | **Not in the repo.** Written by `setup_bspsrc.sh`; `prep.py` looks for `tools/bspsrc.sh` unless `BSPSRC=` is set |

## `weapons/`: the custom weapon builder (creation, not porting)

Method and config keys: [docs/creation/custom-weapons.md](../docs/creation/custom-weapons.md). Not needed on the PC for porting.

| File | What it does | Usage |
|---|---|---|
| `build_weapon.py` | FBX/GLB → CS2 weapon vmdl rigged to a stock weapon skeleton (DMX mesh, hull, magazine, stock anims, materials, optional scope); output under the config's `out` | `python3 build_weapon.py <config.json>` (env `WW1_STOCK` = folder of decompiled stock weapon vmdl/dmx) |
| `lee.json`, `gewehr.json`, `luger.json`, `colt.json` | Example configs (Lee-Enfield, Gewehr 98, Luger, Colt) | |
| `preview.py` | Left/right/top software renders of a built weapon body | `python3 preview.py <name or config.json> ...` (env `WEAPON_OUT`, default `/home/claude/out2`; `WEAPON_PREVIEW_DIR`, default `/tmp`) |
| `fbxparse.py`, `fbxmesh.py` | Binary FBX reader; static meshes in Source space | `python3 fbxparse.py <file.fbx>` dumps the node tree |
| `glbmesh.py` | GLB → parts in Source space, embedded textures exported | |
| `dmx.py`, `dmxmodel.py` | ModelDoc mesh DMX (model 22) read/write | |
| `hull.py` | Convex hulls for the physics shapes | |
| `material.py` | csgo_complex vmat + texture set | `make_material(out, sub, name, tex, size, flip_green)` |
| `scope2.py` | Period scope meshes (allied / axis) | |
| `scope.py` | Older scope builder, superseded by scope2.py (still imported, not called) | |
| `weather.py` | Weathered steel / brass textures | `python3 weather.py` (writes to /tmp) |
| `ww1_weapons.js` | cs_script loadout example (per-team weapons) | |
