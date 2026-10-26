# create/: toolkit for original CS2 addons

> **AI-generated code.** Written by Claude for skink52's CS2 addons; collected here from
> [trenchwarfare-cs2](https://github.com/skink52/trenchwarfare-cs2), [hellmatch-cs2](https://github.com/skink52/hellmatch-cs2),
> [space-racer-cs2](https://github.com/skink52/space-racer-cs2) and made project-neutral. MIT, like the rest of the repo.

Python 3 with numpy, scipy and Pillow; Node 18+ for the tests. Run the tools from this folder (they import each other).
Environment variables instead of hard-coded project paths:
`CS2_ADDON_OUT` (generated content tree, default `../out/addon`), `CS2_MODEL_PREFIX` (folder under `models/` and `materials/models/`, default `props`/`ext`),
`CS2_PREVIEW_DIR` (turntable renders), `CS2_VPK_DIR` (folder with CS2's `pak01_dir.vpk` + the chunks you need).

The guide that explains how these fit together: [docs/creation/guide.md](../docs/creation/guide.md).

## Maps (.vmap)

| File | What it does |
|---|---|
| `dmx.py` | Lossless binary DMX (encoding binary 9) reader/writer: `DMX.load(path)` → elements; `save` reproduces the bytes. |
| `vmaplib.py` | Writes Hammer map nodes into a vmap: entities (`ent`), meshes, groups, vis groups. |
| `vmesh.py` | `CMapMesh` writer that supports open meshes (boundary half-edges with face −1, as Valve's maps use). |
| `check_mesh.py <vmap>...` | Validates every half-edge mesh (opposite/next chains, face loops, vertex and face-vertex counts). Run before handing a generated map over. |
| `dump_entities.py <vmap> <out.json>` | Named point entities + spawns, for the mock engine. |

The porting side's `tools/vmapedit.py` (also reads the importer's keyvalues2 maps) and `tools/vmap_preview.py` (top-down + corner renders) work on any map too.

## Models and materials

| File | What it does |
|---|---|
| `glb2cs2_multi.py model.glb <addon content> <name> [--length L \| --scale S] [--yaw d] [--maxtex 2048] [--surface metal]` | glTF binary → static prop: SMD render mesh + convex hull SMD, a `csgo_complex` vmat per material, PNG textures, vmdl. Handles multi-material Sketchfab models; `--keep/--drop` filter nodes, `--credit` records the licence. |
| `ext_smd.py` | Reads/writes converted props (SMD + vmats) for re-texturing and previews. |
| `s2.py` | Minimal SMD + ModelDoc vmdl and vmat + PNG writers. |
| `modelio.py` | Writes baked meshes as Source 2 content: render/physics SMDs, `csgo_complex` vmat + PNGs, vmdl with LODs (`LOD_SCALE`, `SINGLE_LOD`). |
| `build_prop.py` | Bakes and writes one procedural prop: LOD meshes with a shared chart layout, atlas textures (colour/normal/rough/AO), vmat, vmdl, hulls, a turntable preview. |
| `geo.py`, `noise.py`, `shaders.py`, `bake.py`, `render.py` | Triangle meshes with per-chart UVs; 3D noise (fBm, ridged, cellular); procedural PBR materials (wood, rust, burlap, mud, paint…); the object-space baker (AO, edge/cavity masks, height → normal); a software renderer for previews. |
| `stock.py` | Maps chart materials to stock CS2 materials with real-scale tiling UVs (plank strips, box, cylinder), and can export a game texture as a non-animated `csgo_complex` copy. The tables are examples from mg_trenchwarfare: edit `STOCK`/`ASSIGN`. |
| `p_sandbag.py` | Example prop definition (`spec()` → `build_prop.build(name, spec)`). |
| `vpkdir.py`, `vtexread.py` | Index a CS2 VPK directory, pull files out of the chunks, list a `vmat_c`'s textures, decode `vtex_c` mip 0 to PNG (LZ4/uncompressed; DXT1/5, BC4/5/7, RGBA8888). |

Example: `CS2_ADDON_OUT=out/addon python3 -c "import build_prop, p_sandbag; build_prop.build('sandbags', p_sandbag.spec(0))"`.

## Sound

| File | What it does |
|---|---|
| `merge_snd.py <template.vsndevts> <ours.vsndevts>` | Merges generated sound events into the addon's `soundevents_addon.vsndevts`, keeping what's there. |

## Scripts (cs_script)

| File | What it does |
|---|---|
| `test/point_script.d.ts` | Valve's cs_script API declarations (from the CS2 Workshop Tools; Valve's file, not covered by this repo's licence). |
| `test/tscheck.sh <script.js>...` | Type-checks scripts against it (`npm i -g typescript`). |
| `test/mock_point_script.mjs <script.js> [entities.json] [players=N] [seconds=S] [inputs=a,b] [chat=!x] [seed=N]` | Runs the real script on a stand-in engine with players joining, inputs, damage, kills, respawns, chat and a disconnect. Exits 1 on any exception or call outside the API. Works on port `_io.js` scripts as well. |

Bigger projects (Hellmatch, Space Racer) have their own richer mock engines and Node sims in their repos; see [guide.md](../docs/creation/guide.md#6-testing-before-cs2).

## Elsewhere in this repo

- Custom weapons (vdata override + FBX/GLB rigging onto stock weapon skeletons): [`tools/weapons/`](../tools/weapons) and [docs/creation/custom-weapons.md](../docs/creation/custom-weapons.md).
- Radar renders, sky panoramas from six faces, moondomes, vis hint fitting, stationary-light placement: the porting passes in [`tools/`](../tools) work on original maps too.
