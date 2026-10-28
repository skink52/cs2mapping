# create/: toolkit for original CS2 addons

> **AI-generated code.** Written by Claude for skink52's CS2 addons; collected here from
> [trenchwarfare-cs2](https://github.com/skink52/trenchwarfare-cs2), [hellmatch-cs2](https://github.com/skink52/hellmatch-cs2),
> [space-racer-cs2](https://github.com/skink52/space-racer-cs2), [cs2-fighter](https://github.com/skink52/cs2-fighter/tree/anim-v3) and made project-neutral.
> MIT, like the rest of the repo. Every file's header says where it came from. Tested offline only unless the guide says it ran in CS2.

Python 3 with numpy, scipy and Pillow (ffmpeg for audio analysis and MP4 previews); Node 18+ for the tests, **Node 22.15+** for `anim/` and `s2/`
(zstd-compressed CS2 files). Run the tools from this folder (they import each other).
Environment variables instead of hard-coded project paths:
`CS2_ADDON_OUT` (generated content tree, default `../out/addon`), `CS2_MODEL_PREFIX` (folder under `models/` and `materials/models/`, default `props`/`ext`),
`CS2_PREVIEW_DIR` (turntable renders), `CS2_VPK_DIR` (folder with CS2's `pak01_dir.vpk` + the chunks you need), `CS2_SINGLE_LOD` (props that ship LOD0 only),
`CS2_SKELETON` / `CS2_BVH_DIR` / `CS2_AGENT_DIR` (animation), `CS2_SCRIPT_NAME` (script build). Run Python tools with `python3 -I` when they read downloaded files.

The guide that explains how these fit together: [docs/creation/guide.md](../docs/creation/guide.md).

## Maps (.vmap)

| File | What it does |
|---|---|
| `dmx.py` | Lossless binary DMX (encoding binary 9) reader/writer: `DMX.load(path)` → elements; `save` reproduces the bytes. |
| `vmaplib.py` | Writes Hammer map nodes into a vmap: entities (`ent`), meshes, groups, vis groups. |
| `vmesh.py` | `CMapMesh` writer that supports open meshes (boundary half-edges with face −1, as Valve's maps use). |
| `check_mesh.py <vmap>...` | Validates every half-edge mesh (opposite/next chains, face loops, vertex and face-vertex counts). Run before handing a generated map over. |
| `dump_entities.py <vmap> <out.json>` | Named point entities + spawns, for the mock engine. |
| `vmapgen.py` | Map-writing recipes for generators: `open_map()`; skies (`sky_files()` csgo_moondome vmat + equirect PNG per area, `sky_vmat()` env_sky `sky.vfx` with `F_TEXTURE_FORMAT2`, `env_sky()`); `room()`, `shell()`, `moondome(box, mat, toolsskybox=False)` (toolsskybox shell only on single-sky maps); `hint(box, 'Low')` (hintType by name), `path_hints()` (Low hints along a path, `merge=True` asserts no overlap), `assert_no_overlap()`; `cache_room()` (one hidden prop_dynamic per model, only those the map lacks), `sound_events()` (point_soundevent per event), `template_pool()` (point_template + null-model source prop), `nav_seed()` (func_nav_markup WALKABLESEED + toolsnavattribute mesh), `probe_volume()`, `map_params()`, `skybox_reference()`, `clone()`; `lmres_grid()`/`lmres_terrain()`/`lmres_box()` (toolslightmapres shells); `Terrain` (512-unit tiles, per-tile cell size, crack-free seams, `surf_z()` for spawn heights), `fix_pinches()`; `finish(d, out, group=..., entities_json=...)` (replaces only its own vis group, drops Hammer's sample entities and default box on the first run, rewrites `map_asset_references` + `map_subasset_reference_*` from the real entities, writes entities.json for the mock); `EditKeeper` (keeps the user's Hammer edits to generated objects: previous generated map vs latest save, 0.75 u / 1°, `user_edits.json`). |
| `patch_vmap.py <user.vmap> <out.vmap> [addon] [patch.json]` | Delta patch onto the user's latest map: drop classes / names, set keys on named entities, add entities. Re-runnable (skips entities already there) and recounts the asset references. Edit its `PATCH` block or pass a JSON. |
| `make_skybox.py <sky.vmap> <out.vmap> --half X Y [--edge-z Z] [--ring R] [--trees a.vmdl,b.vmdl]` | 3D skybox content at 1/16: a terrain ring from the main map's edge out to hills and a far ridge (vertex-painted blend material), stock trees on it. Sets `mapUsageType skybox`, adds a `sky_camera` (scale 16) if missing, re-runs replace only its vis group. The main map gets `vmapgen.skybox_reference()`. |
| `placer.py [<map.vmap> [props.json] [overlaps.json]]` | Prop footprints (oriented boxes + z range on a grid): `Placer().footprint()/hits()/add()` keep set dressing from interpenetrating; `audit()`/`write_audit()` list overlapping pairs. Bounds from props.json, converted SMDs, a `STOCK` table (example values, estimated) or tree-name rules. On its own it audits a vmap's props. |

Example generator: `d = vmapgen.open_map(src, out); K = vmapgen.EditKeeper(d, prev, 'gen'); …; vmapgen.finish(d, dst, group='gen', keeper=K, entities_json='out/entities.json')`.

> **Regenerating deletes things.** `finish()` replaces every node in its vis group, and with `drop_classes=` it also removes classes the generator owns
> (the user's own lights, probes and spawns included, whatever group they're in). Pass the previous generated map to `EditKeeper` so Hammer edits survive,
> and use `patch_vmap.py` for late changes. Details: [guide.md](../docs/creation/guide.md).

The porting side's `tools/vmapedit.py` (also reads the importer's keyvalues2 maps) and `tools/vmap_preview.py` (top-down + corner renders) work on any map too.

## Models and materials

| File | What it does |
|---|---|
| `glb2cs2_multi.py model.glb <addon content> <name> [--length L \| --scale S] [--yaw d] [--maxtex 2048] [--surface metal]` | glTF binary → static prop: SMD render mesh + convex hull SMD, a `csgo_complex` vmat per material, PNG textures, vmdl. Handles multi-material Sketchfab models; `--keep/--drop` filter nodes, `--credit` records the licence. |
| `glbmesh.py` (import: `load`, `weld`, `decimate_to`, `render`) | Load a single-texture GLB (e.g. Tripo3D, ~950k triangles), decimate it to a target triangle count with numpy only (seam-aware vertex clustering with a quadric position per cell; UV charts kept apart so no texture smearing or seam cracks) and render textured previews. No pip packages needed (the cloud workspace can't reach PyPI). Used by space-racer-cs2's Neon Racer cars (9k triangles), pylons and gates. |
| `ext_smd.py` | Reads/writes converted props (SMD + vmats) for re-texturing and previews. |
| `s2.py` | Minimal SMD + ModelDoc vmdl and vmat + PNG writers. |
| `modelio.py` | Writes baked meshes as Source 2 content: render/physics SMDs, `csgo_complex` vmat + PNGs, vmdl with LODs (`LOD_SCALE`; `SINGLE_LOD` props ship LOD0 only, empty by default: `CS2_SINGLE_LOD=a,b`, `single_lod`, or spec `'single_lod': True`). |
| `build_prop.py` | Bakes and writes one procedural prop: LOD meshes with a shared chart layout, atlas textures (colour/normal/rough/AO), vmat, vmdl, hulls, a turntable preview. |
| `geo.py`, `noise.py`, `shaders.py`, `bake.py`, `render.py` | Triangle meshes with per-chart UVs; 3D noise (fBm, ridged, cellular); procedural PBR materials (wood, rust, burlap, mud, paint…); the object-space baker (AO, edge/cavity masks, height → normal); a software renderer for previews. |
| `stock.py` | Maps chart materials to stock CS2 materials with real-scale tiling UVs (plank strips, box, cylinder), and can export a game texture as a non-animated `csgo_complex` copy. The tables are examples from mg_trenchwarfare: edit `STOCK`/`ASSIGN`. |
| `p_sandbag.py` | Example prop definition (`spec()` → `build_prop.build(name, spec)`). |
| `build_all_props.py <p_mod1,p_mod2 \| list.json> [names] [--no-preview]` | Builds every prop from spec modules (`specs()` → `{name: spec}`, or one `spec()`), records model, triangle counts and bounds in `props.json` next to `$CS2_ADDON_OUT`. |
| `clean_stale.py [props.json] [--dry-run]` | Deletes files under `materials/models/<prefix>/<prop>/` that the prop's vmdl no longer uses. Run before zipping a delivery. |
| `split_parts.py <model.smd> --name prop --axis x --min 120 [--hubs hubs.json]` | Splits a part (propeller, wheel, turret) into its own `prop_dynamic` model with its origin on the hub. The part is every welded piece entirely past the threshold. Re-runnable (keeps the unsplit SMD); writes the hub offset for the script. |
| `fx_models.py <addon> [--prefix fx] [--only tracer,marker,sight,bomb]` | Self-lit effect models (tracer streak, ground ring marker, ring-and-cross sight, finned bomb) with a `csgo_vertexlitgeneric` + `F_SELF_ILLUM` material writer `emissive()`. Double-sided quads, forward = +x. |
| `voxel.py <addon_out> [preview.png]` | Voxel models: `Grid` (box, ellipsoid, taper, cylinders, flame), greedy mesher with palette UVs, palette textures (4 face shades per colour) as unlit materials, skins as material groups (`Skin` input index = group order), `render_voxels` pictures, `star_tris` crossed quads, `null_model`, an `F_TEXTURE_ANIMATION` strip material. The CLI builds a demo ship. |
| `smd_view.py <addon_out> <out.png> --model m.vmdl[@x,y,z,yaw] --eye=x,y,z --at=x,y,z [--sky png] [--skin NAME]` | Software render of generated SMD + vmdl + unlit vmat textures: textured z-buffer, `_trans` alpha test, near clipping, equirect sky, CS2's FOV (90° at 4:3 = 106° at 16:9). Use `--eye=` with "=" for negative values. |
| `vpkdir.py`, `vtexread.py` | Index a CS2 VPK directory, pull files out of the chunks, list a `vmat_c`'s textures, decode `vtex_c` mip 0 to PNG (LZ4/uncompressed; DXT1/5, BC4/5/7, RGBA8888). |

Example: `CS2_ADDON_OUT=out/addon python3 -c "import build_prop, p_sandbag; build_prop.build('sandbags', p_sandbag.spec(0))"`.

## HUD and loading screens

| File | What it does |
|---|---|
| `panorama.py` | Helpers for generating a custom HUD (`custom_hud_layout`): css rule builder, `P()` panels (`hittest="false"`), `place()` pinned boxes, `show_when()`, pixel-font glyph rows (`glyph_font`/`gtext`/`stext`, one image panel per character), Hellmatch-style `char_line`, `preload()` (makes CS2 compile the loading slides, radar and icon), `hide_with_scoreboard()`, and `write()` which asserts no duplicate ids and no lone rule on a switched class. `python3 panorama.py <addon_out>` writes the worked example. |
| `hud_check.py <layout.xml> \| --addon <out> --name <layout> [--states s.json] [--out prefix] [--bg png]` | Stand-in for Panorama: lays the HUD out at 1920/2333 wide (1080 high), draws it with the real pictures and flags fit-children/unsized panels, `margin-bottom`, non-top `vertical-align`, negative margins outside flow rows, children outside their parent, unsupported panel types, duplicate ids, an id on the top panel, and anything under CS2's own kill feed / team counter / money-health row / chat. States JSON: `{state: {panelId: {add, remove, text, glyphs}}, "_chat_top": 800}`. Exits 1 on any problem (use it as a build gate). |
| `loading.py slides <addon_out> <map> img1 img2 [...] [--css-check]` | Loading-screen slides `<map>.png`, `<map>_1.png`… (cover-scaled to 1920×1080, at least 2, stale ones deleted; `--css-check` fails if the HUD css doesn't preload each). Also `overlay` (CS2's column, loading bar, 4:3 and 21:9 edges sketched on a slide), `radar <addon_out> <map> <img> minx miny maxx maxy [--game dir]` (flat PSD + `resource/overviews/<map>.txt`), `overview`, `icon` (white 64×64 SVG), `workshop <in> <out.jpg> [WxH]` (shaded, saved under 1 MB). |

## 2D art

| File | What it does |
|---|---|
| `pixfont.py` | Original 8×8 arcade pixel font: `render` (outline/shadow), `draw` onto a numpy canvas, `logo` (gradient + drop shadow), `text_voxels` for voxel signs. Credit "Space Racer for CS2 by skink52" if you ship the glyphs. |
| `retro.py` | 32-colour palette with named colours, Bayer `quantize`/`quantize_rgba`, `up` (nearest ×k), `shade`, `nearest`, `scanlines`, value `noise`, `pixel_sphere` planets. |
| `skies.py <out.png> [theme] [seed]` | Pixel-art equirect skies (2048×1024): gradient, dithered nebula, stars, planet/sun, city or mountain horizon. Theme dict `sky=(top, mid, horizon)`, `glow`, `planet=(colour, kind)`, `scenery`; `EXAMPLE_THEMES` has six. |

## Sound

| File | What it does |
|---|---|
| `chiptune.py <out_dir>` | Sound-chip synth (importable): polyBLEP pulse, 16-step triangle, LFSR noise, 4-bit envelopes, sweeps, low-pass, crunch, a note tracker (`render_part`/`bars_of`), `mix` with 5 ms fades, and `write_wav(..., loop=True)` with smpl + cue loop markers. The CLI writes demo effects and a loop. |
| `synth.py <out.wav>` | Offline band synth (numpy + scipy): distorted guitar, bass, lead with ping-pong delay, pad/choir/organ, synthesised drum kit, sidechain pump, convolution reverb, bus compressor, limiter. The CLI renders an 8 s demo. |
| `music_analysis.py <audio> [--json]` | Describes a track: tempo, key, LUFS / true peak / LRA (ffmpeg loudnorm), band balance, centroid, onset density, section boundaries. Needs ffmpeg. |
| `sndevents.py` | Sound-event writers: `event_3d` (csgo_mega, full to 20 % of range, silent at range), `event_base`/`event_base_3d`, `event_music_flat` (flat 0–100000 curves), `event_csgo_music` (`volume_convar = "snd_menumusic_volume"`, `vsnd_files`), `wrap`, and `merge(template, events, tag)`, which replaces only the `// ---- <tag> …` / `// ---- end <tag> ----` block. |
| `merge_snd.py <template.vsndevts> <ours.vsndevts> --tag NAME [-o OUT]` | Merges generated events into the addon's `soundevents_addon.vsndevts`, keeping everything else. Re-runnable (replaces its own block); fails on a name clash outside the block. |

## Animation

Animated bodies: your own clips for CS2's agent skeleton (from CMU mocap or keyed poses), checked and shipped as an invisible rig model
that a script plays clips on, with a stock agent bone-merged on top. From [cs2-fighter](https://github.com/skink52/cs2-fighter/tree/anim-v3) (Puppet Brawl).
The whole pipeline, the rig's vmdl format and the exact Hammer/script setup: [anim/README.md](anim/README.md).

| File | What it does |
|---|---|
| `anim/rig.mjs`, `anim/m3.mjs` | The skeleton (`CS2_SKELETON` or `anim/cs2_skeleton.json`, made with `s2/skeleton.mjs`), FK, mirroring, SMD writer; maths. |
| `anim/bvh.mjs`, `anim/retarget.mjs` | BVH reader; mocap → agent skeleton (CMU joint names by default, other sources via a joint map). |
| `anim/clip.mjs`, `anim/mocap_move.mjs` | Clips: cut from mocap, aim, stand on the support foot, retime with key pairs (120 Hz take frames), blend into a stance, foot lock, floor clamp, loop, finish. |
| `anim/post.mjs`, `anim/pose.mjs`, `anim/posture.mjs`, `anim/hands.mjs` | Hinge IK for knees/elbows, twist bones, arms out of the body, hip and ankle limits; pose helpers; a pose from a short spec + keyed postures; hand shapes. |
| `anim/validate.mjs <smd or folder>` | Joint checker: knees/elbows the wrong way, twisted thighs, ankles out of range, limbs inside the body. Run after every animation change. |
| `anim/rig_vmdl.mjs` | Writes the rig: ModelDoc vmdl (`AnimationList`, `bone_cull_type = "None"`, default `idle`), one hidden triangle per bone, every clip + a mirrored `_m` twin, dark vmat. |
| `anim/preview.mjs`, `anim/render.mjs`, `anim/analyze.mjs`, `anim/gallery.mjs` | Contact sheets / MP4 of clips on a real agent mesh (ffmpeg); find and view strikes in CMU takes. |
| `anim/test_smoke.mjs` | Self-contained test on a synthetic skeleton + BVH (no CS2 files). |

## Compiled CS2 files (s2/)

Readers for CS2's compiled resources (`*_c`), straight from the game's VPKs (`--vpk <CS2>/game/csgo` or `CS2_VPK_DIR`). Their output is Valve data: keep it out of git.

| File | What it does |
|---|---|
| `s2/vpk.mjs <vpk folder> [regex]` | Lists / reads files in `pak01_dir.vpk` + chunks (JS twin of `vpkdir.py`). |
| `s2/kv3.mjs <file_c> [BLOCK]`, `s2/resource.mjs` | Resource blocks + binary KV3 (v1–v5, LZ4/zstd); prints a file's blocks as JSON. |
| `s2/skeleton.mjs <model.vmdl_c> <out.json>` | Bones, parents and bind pose of a model (the agent skeleton for `anim/`), plus hull, attachments, sequences, materials. |
| `s2/agent_mesh.mjs <agent.vmdl_c> <out.json>` | Agent skeleton + skinned third-person meshes for the animation previews. |
| `lod_decimate.py <addon> <out> <model dir under models/> ... [--keep-lod1 a,b]` | Faithful LOD1-4 for SMD static props decimated from LOD0 (quadric vertex clustering per material, corner normals kept, UVs re-projected per face so tiled textures hold); largest cell within ~1 px at each switch (thresholds 20/60/120/240); rewrites the vmdl's RenderMeshList + LODGroupList. Thin wire: keep its own LOD1. |
| `weld_cracks.py <body dmx> <out> [tol]` | Closes seam cracks in a skinned DMX body (split vertices that drifted apart): merges boundary vertices only, closest first, groups capped at tol, weights averaged. Needs dmx9.py (mg_trenchwarfare tools). |
| `s2/fp_gloves.mjs <agent.vmdl_c> <out.json> [--vpk <game/csgo>]` | An agent's first-person default gloves (glove draw call of `firstperson_default_gloves_arms`) with weights by bone name, UVs in DMX orientation, for putting stock gloves under custom sleeves. |
| `s2/prop_mesh.mjs <model.vmdl_c>... [--json out]` | Real bounds (and meshes) of stock props, for placing and stacking them by their true size. |

`s2/vendor/meshoptimizer/` is meshoptimizer's decoder (MIT, Arseny Kapoulkine; licence alongside).


## Scripts (cs_script)

| File | What it does |
|---|---|
| `build/build.mjs <config.json> [--name NAME]` | Assembles a cs_script game: sorted `coreDir` files + `const NAME = <json>` data + sorted `adapterDir` files under one `cs_script/point_script` import → `out/addon/maps/scripts/<name>.js`, plus `build/core_test.cjs` (core + data, `module.exports`) for Node tests. Config: `name`, `coreDir`, `adapterDir`, `data` (`{CONST: path}` or `{path, default}`), `imports`, `exports`, `out`. `CS2_ADDON_OUT` / `CS2_SCRIPT_NAME` override. |
| `build/build_all.example.sh` | Reference build order to copy: test module → models → HUD → **HUD check gate** → sounds + merge → sky / slides (css-checked) / radar / icon → map + mesh check + entity dump → script → tscheck → mock run → ship docs. |
| `test/point_script.d.ts` | Valve's cs_script API declarations (from the CS2 Workshop Tools; Valve's file, not covered by this repo's licence). |
| `test/tscheck.sh <script.js>...` | Type-checks scripts against it (`npm i -g typescript`). |
| `test/mock_point_script.mjs <script.js> [entities.json] [key=value …]` | Runs the real script on a stand-in engine: joins, inputs, damage, kills, respawns, chat, disconnects, round flow; options for traces, engine-call counts, timing percentiles, churn/slot-reuse/warmup scenarios and HUD checks. Exits 1 on any exception or call outside the API. Works on port `_io.js` scripts too. All options: [test/README.md](test/README.md). |

Node sims of the pure game (balance, soak) live in each project; the method is in [guide.md](../docs/creation/guide.md#6-testing-before-cs2).

## Elsewhere in this repo

- Project-doc templates (README, TESTING, HANDOVER, CREDITS, Workshop compliance…): [docs/creation/templates/](../docs/creation/templates).
- Custom weapons (vdata override + FBX/GLB rigging onto stock weapon skeletons): [`tools/weapons/`](../tools/weapons) and [docs/creation/custom-weapons.md](../docs/creation/custom-weapons.md).
- Radar renders, sky panoramas from six faces, moondomes, vis hint fitting, stationary-light placement: the porting passes in [`tools/`](../tools) work on original maps too.
