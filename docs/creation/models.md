# Models

Every route used so far to get a model into CS2, from downloaded files to fully generated ones. Tools are in [`create/`](../../create)
unless a project repo is named. Model files: ModelDoc `.vmdl` (KV3 text) referencing SMD/DMX/OBJ meshes; compile in ModelDoc, by loading the map
in Hammer, or with `resourcecompiler -i <file.vmdl>` (`run_build.bat "assets <addon>"`). A model only the script uses must be compiled explicitly.

## Static props from downloaded models (GLB/glTF)

`python3 create/glb2cs2_multi.py model.glb <addon content> <name> --length <units>` (or `--scale`), `--yaw`, `--maxtex 2048`, `--surface metal|wood|…`,
`--keep/--drop` node filters, `--credit "<author, licence>"`.

- Output: `models/<prefix>/<name>/<name>.smd` + hull SMD + `.vmdl` (`static_prop_model`, `RenderMeshFile`, `PhysicsHullFile`, a `DefaultMaterialGroup`
  remap per material) and `materials/models/<prefix>/<name>/*.vmat` (`csgo_complex`) + colour/normal/rough/metal/AO PNGs.
- Conventions: glTF metres → inches ×39.3701; Y-up → Z-up `(x, y, z) → (x, −z, y)`; UV v flipped; node transforms baked (winding flipped for mirrored nodes);
  glTF normal maps are OpenGL (Y+), which Source 2 uses as-is. Metallic-roughness texture: G = roughness, B = metalness. Constant roughness → a 4×4 grey PNG.
  `doubleSided` → `F_RENDER_BACKFACES 1`.
- First used for a CC-BY spike barricade in mg_kohztec_course; mg_trenchwarfare converted its Sketchfab aircraft and props this way (`ext_smd.py` re-textures
  them later, e.g. one weathered PBR atlas per aircraft). Moving parts (propellers) were split out of the SMD into their own `prop_dynamic` models with the
  origin on the hub so the script can spin them.
- Record the source and licence in the vmdl comment and the addon's `CREDITS.md`.

## Procedural props with baked textures

mg_trenchwarfare's props (sandbags, revetments, duckboards, wire, shattered trees, a Minenwerfer, wrecked tank, hangar…) are all generated:

1. **Geometry** (`geo.py`): triangle meshes built from parts (rounded boxes, tubes, lathes) with per-chart UVs of known world size, and a local frame per part
   handed to the shaders (wood grain direction, panel axes).
2. **Shaders** (`shaders.py` + `noise.py`): procedural PBR materials evaluated per texel in object space — colour, roughness, metalness, height — wood, rust, burlap,
   mud, painted metal, canvas, with fBm/ridged/cellular noise.
3. **Bake** (`bake.py`): packs charts into one atlas per model, rasterises every texel to its 3D point, runs the shaders, bakes voxel AO, edge and cavity masks,
   converts height to a tangent-space normal map (OpenGL, +Y up), pads gutters.
4. **Write** (`modelio.py` via `build_prop.py`): LOD meshes sharing the chart layout, `csgo_complex` vmat + PNGs, vmdl with LODs and convex hulls, a turntable preview
   (`render.py`) to check before CS2.
5. **Stock materials where they're better** (`stock.py`): charts mapped to real Valve materials (wet floorboards, rusty metal, mud, maple bark exported as a non-animated
   copy) skip the bake and get real-scale tiling UVs per face corner (plank strips, box or cylindrical projection).

Lessons: LOD thresholds ×16 (pops at ~300 u otherwise) and LOD0 only where LOD1 deviates > ~2 u; probe-light (`bakelighting 0`) small props and foliage;
one convex hull per prop. Example: `build_prop.build('sandbags', p_sandbag.spec(0))`.

## Low-poly creatures with painted atlases

mg_deku_tree's creatures (snapper, spitter, weaver, grub, a boss) are procedural low-poly models with a painted swatch atlas (its `tools/creatures.py`,
`tools/swatches.py`); poses are separate models swapped by the script (no animgraph). Bomb-arena characters are 2D chibi sprites on props.

## Voxel models from sprites

- Hellmatch (`tools/sprites.py`): Freedoom sprites → CS2 models. `rot8`: a voxel figure carved from the 8 sprite rotations (players, rockets); `lathe`: solid of
  revolution (lamps, barrels); `slab`: extrusion (boxes, weapons); `star`: three crossed alpha-tested planes (effects, corpses). One shared palette material
  with 16 player-colour skins + a fuzz skin; sector light via `SetColor`.
- Space Racer (`tools/cars.py`): true 3D voxel cars (~115 units) in normal and boosting variants with T/CT colour skins, explosion frames, effects; renders for the HUD picker.
- Animated textures (water, lava): frames as separate models stepped by the script, because `g_vTexCoordScrollSpeed` doesn't scroll in CS2.

## Player models

### Rebuilding a CS:GO player model as a CS2 agent

CS:GO custom player models (Octodad in mg_mario_party, the green Power Ranger in mg_50arenas) import as plain props: no CS2 animgraph, so weapons are
drawn huge and ragdolls fail. They were rebuilt as real CS2 player models:

PLAYER_MODEL_METHOD

### Script-driven characters

- Hide the pawn with `SetModelScale(0.02)`, not `SetColor`/alpha every reset (suspected cause of giant first-person weapons). `SetModel` on a live pawn to a stock
  agent drew the local body in first person in mg_trenchwarfare and was removed.
- Every model the script swaps to must be precached by a hidden `prop_dynamic` in the map.

## Animated rigs (Puppet Brawl)

One invisible rig model plays every animation, and the four stock agents are **bone-merged** on top (`point_template` with the rig `prop_dynamic` and an agent
`prop_dynamic` parented to it with attachment `!bonemerge`), so one animation set drives all fighters. The fighting game runs in 2D in the script; the rig shows it.

- **Skeleton:** the CS2 agent skeleton read from a stock agent `vmdl_c` (bones, parents, bind pose; `cs2-fighter/tools/skel.mjs` + `kv3.mjs`).
- **Clips** (`tools/anim/`): written as SMD animations + a reference SMD and listed in the rig's ModelDoc vmdl. 196 clips, each with a mirrored twin (392 files).
  - 2D game poses lifted to 3D (hands and feet exactly where the 2D hit boxes are; depth gets a stance twist and guard).
  - Hand shapes (fist with thumb wrap, relaxed, open, chop, claw) and straight wrists by default (`hands.mjs`, `posture.mjs`).
  - **Motion capture:** CMU mocap BVHs (free use) cut, aimed along +X, placed on the support foot, retimed to game frames, blended in/out of each fighter's
    stance per bone group, support foot locked, feet put on the floor (`mocap_move.mjs`, `retarget.mjs`, `bvh.mjs`).
  - **Hinge IK** for knees/elbows (can't bend backwards; knee floor limit), airborne ankles held to a natural range, arms pushed out of head/torso.
  - Hit and hurt boxes baked from the same animation, so gameplay matches what's drawn.
- **Checks without CS2:** `validate.mjs` (joint ranges, limbs inside the body), offline renders on the real agent meshes (`review.mjs`), review sheets sent to the mapper.
- Delivery: hundreds of SMDs go as a zip the mapper extracts into `rig/anims/`, then `pb_rig.vmdl` is recompiled.

## Weapons

Rigging new weapon models onto stock weapon skeletons and swapping them in through `weapons.vdata`: [custom-weapons.md](custom-weapons.md).

## Checking stock CS2 assets offline

`create/vpkdir.py` + `create/vtexread.py` index CS2's `pak01_dir.vpk`, pull files out of the chunks, list a `vmat_c`'s textures and decode `vtex_c` to PNG — used to
preview Valve materials before choosing them and to export stock textures as non-animated copies. Source 2 Viewer (CLI: Decompile & Export) turns stock
`vmdl_c` models into editable vmdl + DMX, the starting point for weapons and player models.
