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
| `run_c.py` | Stage C when CS2's `pak01_dir.vpk` isn't staged (stub VPK). Default steps leave out `alpha`, `assets` (need the VPK) and `doors`, `overlayfix`, `facescale`, `matflags` (run those later with `run_pass.py`) | `python3 run_c.py <addon> <root> [step,...]` |
| `stage_d.py` | Follow-up passes on a map you've already edited in Hammer (keeps your edits) | `python3 stage_d.py <addon> <root> pass[,pass...]` (passes below) |
| `ports.py` | `existing_ports.txt` helpers: duplicate check (ignores prefixes, `_cs2`, version suffixes) and adding a line | `python3 ports.py check <existing_ports.txt> <name>...` · `python3 ports.py add <existing_ports.txt> <name> [status] [mapper]` (default `[in progress] [skink]`) |
| `hammer_resave.py` | What a CS:GO Hammer open/save changes in a BSPSource VMF (prep.py calls it) | `python3 hammer_resave.py <in.vmf> <out.vmf>` |
| `disprestore.py` | Rebuilds displacements the importer dropped ("Found a displacement missing a needed subkey.") from the BSP | `python3 disprestore.py <vmap in> <bsp> <vmap out> [x0,y0,z0,x1,y1,z1 ...]` (skip boxes) |
| `laserhurt.py` | A `trigger_hurt` along every CS:GO env_laser that did damage and has none (after stage C) | `python3 laserhurt.py <vmap in> <csgo vmf> <vmap out>` |
| `glowfix.py` | Parented env_particle_glows → following glow particles | `python3 glowfix.py <vmap in> <vmap out> <addon content root>` |
| `matnames.py` | Importer-sanitised material refs (spaces → underscores) back to the real file names; run before `alpha,assets` | `python3 matnames.py <addon> <root>` (needs `<root>/content_files_<addon>.json`) |
| `vmap_preview.py` | Top-down + four corner renders of any vmap (binary or importer text) | `python3 vmap_preview.py <map.vmap> <out.png> [x0,y0,z0,x1,y1,z1]` |
| `setup_bspsrc.sh` | Extracts BSPSource from its jlink image and patches the class files to Java 21; writes `<dest>/bspsrc.sh` | `sh setup_bspsrc.sh <staged bspsrc-windows/lib/modules> <dest dir>` (use `<dest>` = `tools/` so prep.py finds it, or set `BSPSRC=`) |

### Stage C step keys (run order, from `stage_c.run()`)

`merge, io, wall, equip, push, cmd, roundcfg, score, speed, gravity, dead, sounds, doors, overlays, overlayfix, facescale, sky, skyvis, vis, beams, lights, alpha, radar, assets, matflags`,
plus `overlaydepth` (= `overlayfix` + projection depth 8) when named. `vis` runs `visfit.py`; `skyvis` (the older shell-only pass) runs only when `vis` isn't in the list.
`alpha` and `assets` need `<root>/vpk/cs2_pak01_dir.vpk` and are skipped silently without it. `daylight` is **not** a stage C step.

### stage_d.py passes

`beams, lights, alpha, radar, daylight, skyvis, visfit, visfit_lower, gravity, overlayfix, overlaydepth, facescale, matflags`.
Name differences from stage C: stage C's `vis` is stage D's `visfit`. `radar` here uses the default `pct=0.5`; for another value call
`radar.run(m, c, pct=0, tex=radar.textures_for(c))` from Python (there's no CLI flag). sky, sounds, doors, assets, equip and the other stage C
steps aren't stage D passes: use `run_pass.py`.

## Passes (library modules called by stage C / D)

| File | Step / pass | What it does |
|---|---|---|
| `gen_script.py` | (end of stage C) | Builds `maps/scripts/<addon>_io.js`: `Cmd_`, `Score_`, `Speed_`, `Gravity_` inputs, spawn equips, plus `push_tail.js` for push zones (`PushIn_`/`PushOut_`) |
| `push_tail.js` | `push` | The trigger_push half of the generated io script (holds CS:GO "set speed" pushes, max 3500); appended by gen_script.py |
| `gravity.py` | `gravity` | trigger_gravity → trigger_multiple + script `Gravity_<scale>`; stage D patches the existing `_io.js` |
| `assets.py` | `alpha`, `assets` | Missing materials rebuilt from CS:GO's VPK, water → `liquids/nuke_water`, closest stock CS2 material otherwise; alpha-test/translucent masks |
| `texfix.py` | `overlayfix`, `overlaydepth`, `facescale`, `matflags` | Static overlay geometry, brush-face texture scale/shift, `$additive`/`$nocull` material flags |
| `sky.py` | `sky` | Six CS:GO sky faces → 2:1 equirect panorama for `sky.vfx` / `csgo_moondome` |
| `visfit.py` | `vis` (C), `visfit`/`visfit_lower` (D) | Vis hints fitted to the play space (Low / Lower / one Lowest) and sky shells out of vis |
| `skyvis.py` | `skyvis` | Older pass: sky shells that seal nothing get Exclude from Vis |
| `beams.py` | `beams` | env_laser / env_beam → never-solid func_brush beams (damage: `laserhurt.py`) |
| `lighting.py` | `lights` | Minimal set of Stationary lights per sealed compartment, max 4 overlapping |
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
