# Models

Every route used so far to get a model into CS2, from downloaded files to fully generated ones. Tools are in [`create/`](../../create)
unless a project repo is named. Model files: ModelDoc `.vmdl` (KV3 text, header `format:modeldoc41`) referencing SMD/DMX/OBJ meshes; compile in ModelDoc, by loading the map
in Hammer, or with `resourcecompiler -i <file.vmdl>` (`run_build.bat "assets <addon>"`). A model only the script uses must be compiled explicitly
(the asset pre-pass's `models|*.vmdl` pass catches it on the command-line build).

## ModelDoc traps (verified)

- ModelDoc turns **SMD imports 90° about Z** and reads V from the bottom: write positions as `(y, −x, z)` with V flipped (or compensate in script).
  Animation SMDs: pre-rotate the root bone instead ([cs2-gotchas](../reference/cs2-gotchas.md#models-modeldoc-and-weapons)).
- It **drops bones with no geometry**: an invisible rig needs a tiny hidden triangle per bone and `BoneMarkupList { bone_cull_type = "None" }`.
- Material groups (skins) must remap from the default group's full material path, not the SMD material name.
- Minimal static prop: `RootNode` → `MaterialGroupList/DefaultMaterialGroup` remaps (`from = "<smd material>.vmat"`, `to = "materials/….vmat"`),
  `RenderMeshList/RenderMeshFile`, `PhysicsShapeList/PhysicsHullFile` on the same mesh, `model_archetype`, `document_sub_type = "ModelDocSubType_None"`.
  Props a script moves: `model_archetype ""`. `create/s2.py` writes SMD + vmdl + vmat + PNG.
- Blender FBX: a per-material string property `FBX_vmatPath` maps materials. Door pivots: move the mesh in the source or use a `func_door_rotating` pivot.

## Skins and animated textures

- **Skin index:** a script picks a material group with `Instance.EntFireAtTarget({ target: prop, input: "Skin", value: n })`; `n` is the order in the vmdl's
  `MaterialGroupList`: `DefaultMaterialGroup` = 0, then each `MaterialGroup` in order. Space Racer: neutral, t, ct, gold, then 12 shades; Hellmatch: 16 player
  colours + a fuzz skin. One model with skins beats one model per colour (the cache room and `SetModel` stay small).
- **Animated textures (Hellmatch, water/lava/slime and scrolling walls):** **one prop, one `MaterialGroup` per frame** (named `anim<N>`, each remapping the
  default group's full material paths to that frame's vmat), stepped by the script with the `Skin` input (Doom flats every 8 tics). Scrolling walls: each
  scrolling texture becomes its own anim prop whose frames are the texture shifted `max(2, w/32)` px (≤ 32 frames), because `g_vTexCoordScrollSpeed`
  doesn't scroll in CS2. The first version remapped from the SMD material name and never animated; the 19 Oct fix (remap from the default group's path)
  is **not yet confirmed in game**.
- The material-side alternative, `F_TEXTURE_ANIMATION` strips (Space Racer flames; `voxel.flame_frames`): keys in
  [cs2-gotchas](../reference/cs2-gotchas.md#lighting-materials-and-rendering); untested in CS2.

## Static props from downloaded models (GLB/glTF)

`python3 create/glb2cs2_multi.py model.glb <addon content> <name> --length <units>` (or `--scale`), `--yaw`, `--maxtex 2048`, `--surface metal|wood|…`,
`--keep/--drop` node filters, `--credit "<author, licence>"`.

- Output: `models/<prefix>/<name>/<name>.smd` + hull SMD + `.vmdl` (`static_prop_model`, `RenderMeshFile`, `PhysicsHullFile`, a `DefaultMaterialGroup`
  remap per material) and `materials/models/<prefix>/<name>/*.vmat` (`csgo_complex`) + colour/normal/rough/metal/AO PNGs.
- Conventions: glTF metres → inches ×39.3701; Y-up → Z-up `(x, y, z) → (x, −z, y)`; UV v flipped; node transforms baked (winding flipped for mirrored nodes);
  glTF normal maps are OpenGL (Y+), which Source 2 uses as-is. Metallic-roughness texture: G = roughness, B = metalness. Constant roughness → a 4×4 grey PNG.
  `doubleSided` → `F_RENDER_BACKFACES 1`.
- **Re-texturing converted models** (mg_trenchwarfare's aircraft, `weather_ext.py` in its repo, method only): re-orient yawed Sketchfab models (nose to +X,
  centred), pack ~50 materials into one 4096 atlas of planar charts, bake the original colour plus triplanar stock-texture detail and object-space wear
  (oil, soot, mud, faded paint, worn edges), and write compound convex hulls (wings, fuselage, tail). `create/ext_smd.py` reads/writes the converted SMDs.
- **Moving parts** (propellers, wheels): `python3 create/split_parts.py <model.smd> --name prop --axis x --min 120` moves every connected piece beyond the
  threshold into `<model>_prop.smd/.vmdl` with the origin on the hub, writes the hub offset to JSON, and keeps the unsplit SMD so re-runs are idempotent.
  The script places the part at body origin + hub rotated by the body's angles and spins it.
- Record the source and licence in the vmdl comment and the addon's `CREDITS.md`.

## Procedural props with baked textures

mg_trenchwarfare's props (sandbags, revetments, duckboards, wire, shattered trees, a Minenwerfer, wrecked tank, hangar…) are all generated:

1. **Geometry** (`geo.py`): triangle meshes built from parts (rounded boxes, tubes, lathes) with per-chart UVs of known world size, and a local frame per part
   handed to the shaders (wood grain direction, panel axes). Decals: `geo.decal(img_id, origin, u, v, size)` + `spec['decal_imgs']` → an alpha-tested
   `<prop>_decal` atlas.
2. **Shaders** (`shaders.py` + `noise.py`): procedural PBR materials evaluated per texel in object space — colour, roughness, metalness, height — wood, rust, burlap,
   mud, painted metal, canvas, with fBm/ridged/cellular noise.
3. **Bake** (`bake.py`): packs charts into one atlas per model, rasterises every texel to its 3D point, runs the shaders, bakes voxel AO, edge and cavity masks,
   converts height to a tangent-space normal map (OpenGL, +Y up), pads gutters.
4. **Write** (`modelio.py` via `build_prop.py`): LOD meshes sharing the chart layout, `csgo_complex` vmat + PNGs, vmdl with LODs and convex hulls, a turntable preview
   (`render.py`) to check before CS2.
5. **Stock materials where they're better** (`stock.py`): charts mapped to real Valve materials skip the bake and get real-scale tiling UVs per face corner
   (plank strips, box or cylindrical projection). mg_trenchwarfare's exported copies: hessian ← `pbr_defaults` cloth001 tinted; paint ← `metalhull003a`
   (rust kept, roughness derived); brass/steel ← de_mirage `metal_basic_1`; rope ← `rope_braid_1`; boards ← train boards 02. `ASSIGN` lists per-part variants.
6. **Batch and tidy:** `create/build_all_props.py <modules>` builds every prop and writes `props.json` (model, tris, bounds) for the placer;
   `create/clean_stale.py` deletes material files no vmdl uses any more, before zipping a delivery.

Example: `build_prop.build('sandbags', p_sandbag.spec(0))`.

**LODs** (mg_trenchwarfare): thresholds ×16 (`modelio.LOD_SCALE`; at ×1 and ×4 the swaps were visible at ~300 u). Measure each prop's LOD0-vs-LOD1 deviation
as the **p95 of the nearest-surface distance** between the two meshes: shattered trees 20–48 u, tunnel set 10, hangar 9, stumps 7–8, log 6,
shelter/wire coil/wrecked tank ~2, revetments 1.2–1.7, sandbags 0.7, crates 0.1. Props at **≥ ~2 u** shipped LOD0 only (`CS2_SINGLE_LOD` /
`modelio.SINGLE_LOD`, empty by default). Keep geometry rules identical across LODs (a LOD-dependent plank gap made revetments jump). Better long-term: derive LOD1 by
decimating LOD0. Probe-light (`bakelighting 0`) small props and foliage; one convex hull per prop.

**Self-lit effect models** (tracers, sight pips, ground markers): `python3 create/fx_models.py <addon> [--prefix fx]`; `fx_models.emissive(...)` writes a
`csgo_vertexlitgeneric` vmat with `F_SELF_ILLUM 1`, a `TextureSelfIllumMask`, `g_flSelfIllumBrightness` 12–40 and `g_vSelfIllumTint`; quads are double-sided.

## Voxel and sprite models

- **Voxel models** ([`create/voxel.py`](../../create/voxel.py), from Space Racer's `cars.py`): paint a `Grid` (box, ellipsoid, taper, cylinders), greedy-mesh it
  into quads (a few hundred triangles per vehicle), one palette texture with 4 shades per colour (lighting baked in, unlit material), skins as material groups,
  a shaded render at any angle for HUD pictures, and `null_model()` (one 0.01-unit triangle) for pooled props.
- **Hellmatch** (`tools/sprites.py` in its repo): Freedoom sprites → CS2 models. `rot8`: a voxel figure carved from the 8 sprite rotations; `lathe`; `slab`
  (extrusion); `star`: three crossed alpha-tested planes with `F_RENDER_BACKFACES 1`. Sprites over 60 px are carved at 2 u per voxel, over 130 px at 4 u
  (one large model went from 50 MB per frame to 1–6 MB).
- **Unlit retro materials** (`csgo_unlitgeneric`): `F_BLEND_MODE` 0 / 2 alpha test / 1 translucent, `g_vColorTint` per baked light level,
  `g_flModelTintAmount "1.000"` so script `SetColor` tints the prop (Hellmatch's sector light). Alpha-tested textures must be power-of-two: Hellmatch pads
  sprites (UVs scaled `w·4 / pot(w·4)`) and stretches tiling textures.
- **Flat sprite models (top-down games):** the bomb-arena game draws everything as flat textured quads seen from straight above (camera pitch 89.9°):
  617 small models, a static floor+blocks model per generated map swapped onto one prop, the script choosing the model per frame. 1,357 model files went to the
  PC as one zip. Bodygroups switched with `SetBodyGroup` would cut the model count.
- **Low-poly creatures** (mg_deku_tree `tools/creatures.py`, `tools/swatches.py`): procedural low-poly models with a painted swatch atlas; poses are separate
  models swapped by the script (no animgraph).

## Player models

### LODs that don't pop (and don't cost FPS)

ModelDoc `switch_threshold` scales inversely with screen size (bigger = further). Default-scale values (20, 40, 80…) with a LOD1 that
isn't a copy of LOD0 pop visibly at ~300 u; pushing the thresholds out 16x hid the pops but made every prop draw LOD0 map-wide
(mg_trenchwarfare: ~17M triangles looking across no man's land). Fix: decimate each LOD from LOD0 itself (`create/lod_decimate.py`),
with the cell size held to about a pixel at the switch distance, then keep the default-scale thresholds (20/60/120/240). Downloaded
models with no LODs at all (28k-tri petrol cans, 55k-tri tanks) are usually the worst offenders per instance. Barbed wire and other
geometry thinner than a cell keeps a generated low LOD instead.

LODs cost lightmap space. The baker charts every LOD x material of every `bakelighting 1` instance ("Charting N unique meshes"), and
each disconnected piece is a chart that needs atlas room and edge-seam memory. Per-face corners in a decimated LOD (every triangle its
own vertices) make every triangle a chart: mg_trenchwarfare went to 5.6M charts and vrad3 ran out of memory welding seams. So LOD
vertices must be shared (one normal + UV per cluster and LOD0 chart), and lightmapped props should carry two decimated LODs at most
(`lod_decimate.py --lightmapped-from <vmap>`); probe-lit props can keep all four. If the bake needs an ever larger
`lightmapMaxResolution` to pack, count the charts: instances x LODs x materials x pieces.

Seam cracks on a converted body: if the source mesh is split at every seam and the copies get different skin weights (e.g. weights
transferred per vertex from a donor), re-posing pulls them apart and the model shows see-through specks. Weld the source first; to
repair a finished DMX, `create/weld_cracks.py` merges the cracked boundary vertices.

### Rebuilding a CS:GO player model as a CS2 agent

CS:GO custom player models (Octodad in mg_mario_party, the green Power Ranger in mg_50arenas) import as plain props: no CS2 animgraph, so weapons are
drawn huge and ragdolls fail. They were rebuilt as real CS2 player models:

1. **Get the real agent.** The `characters/models/…` agents in `pak01_dir.vpk` are placeholders with one "dummy" bone. The real ones are
   `agents/models/<agent>/<agent>.vmdl_c` on the new animation system: shared skeleton `animation/skeletons/characters/worldmodel.vnmskel_c`
   (+ `viewmodel.vnmskel_c`) and `.vnmgraph_c` graphs. Find the chunk through the VPK directory (`create/vpkdir.py`) and slice it out of `pak01_NNN.vpk`
   (tm_phoenix was in `pak01_366`/`502`; numbers change with updates).
2. **Decompile it** with Source 2 Viewer CLI: `Source2Viewer-CLI -i tm_phoenix.vmdl_c -d -o dec/tm_phoenix.vmdl` → ModelDoc vmdl +
   `tm_phoenix_thirdperson_body.dmx`, `tm_phoenix_firstperson_default_gloves_arms2.dmx`, `tm_phoenix_firstperson_sleeves3.dmx`, `tm_phoenix_tools_preview.dmx`.
3. **Use the agent vmdl as the template** (skeleton, animgraph, hitboxes, physics shapes, attachments, first-person arms) and edit it:
   remove the `thirdperson_default_gloves` render mesh and its bodygroup choice, remove every `AnimConstraintDotToMorph` and the `eye_test` animation
   (no face morphs on the new mesh), repoint the four DMX paths to your model folder, check no `tm_phoenix` string is left and braces balance.
4. **Rebuild the ragdoll.** The decompiled vmdl has physics bodies but **no joints**, so the first build didn't ragdoll. Dump the compiled physics
   (`Source2Viewer-CLI -i tm_phoenix.vmdl_c -b PHYS`) and rebuild the 14 joints from `m_joints` (type 4 conical, 3 revolute for knees; `m_Frame1` position +
   quaternion → `anchor_origin`/`anchor_angles`; swing/twist limits rad → deg; bone names from `m_boneNames`) as a `PhysicsJointList` after the
   `PhysicsShapeList`:
   ```
   { _class = "PhysicsJointList" children = [
     { _class = "PhysicsJointConical" parent_body = "<bone>" child_body = "<bone>"
       anchor_origin = [ x, y, z ] anchor_angles = [ p, y, r ] collision_enabled = false motion_resistance = "none"
       enable_swing_limit = true swing_limit = 45.0 swing_offset_angle = [ 0.0, 0.0, 0.0 ]
       enable_twist_limit = true min_twist_angle = -30.0 max_twist_angle = 30.0 }, … ] },
   ```
   Knees were written as conical joints with swing 0 and the hinge range as twist. Octodad's ragdoll was confirmed working in game.
5. **Rebind the mesh onto the CS2 skeleton.** Start from the agent's third-person body DMX: keep its joints, hierarchy and bind pose, delete its meshes and
   graft the old mesh in.
   - Models with ValveBiped-like names (Octodad: 73 bones matched by name, within ~0.5 u after alignment): rotate the mesh +90° about Z (CS:GO player models face
     −Y, CS2 agents face +X), shift by the median per-bone offset, remap weights by bone name; unmatched bones go to the nearest matching ancestor;
     explicit map for twist bones (`bip01_l*armtwist → arm_upper_l_twist`, `*thightwist → leg_upper_l_twist`, `*calftwist → leg_lower_l`).
   - Models with different proportions (the Power Ranger, T-pose): re-pose every bone onto the CS2 A-pose (rotate without twist onto the CS2 bone direction,
     stretch to its length, put it on the CS2 joint), carry the vertices by their skin weights, then remap weights. Map: `bip01_pelvis→pelvis`,
     `spine..spine3→spine_0..spine_3`, `neck→neck_0`, `head→head_0`, `<s>_clavicle→clavicle_<s>`, `upperarm→arm_upper_<s>`, `forearm→arm_lower_<s>`,
     `hand→hand_<s>`, `thigh→leg_upper_<s>`, `calf→leg_lower_<s>`, fingers 0–4 → thumb/index/middle/ring/pinky, `weapon_bone→hand_r`.
   - Check the fit with a front/side plot of the vertices over the CS2 bones.
6. **First-person arms:** the agent's arms and sleeves DMX are copied as they are (you see the agent's gloves in first person).
   Custom sleeves with a stock agent's default gloves (mg_trenchwarfare: T = tm_phoenix glove_fullfinger, CT = ctm_sas glove_hardknuckle_black):
   `create/s2/fp_gloves.mjs <agent vmdl_c> <out.json> --vpk <game/csgo>` pulls the glove draw call of `firstperson_default_gloves_arms` straight from
   the VPK (no decompile needed; UVs come out in DMX orientation, verified against the S2V decompile of tm_phoenix), a writer puts it on the template
   skeleton (bone names → jointList, UV-derived tangents), and the sleeve cuff is eased out over the glove (glove profile around the forearm bone
   + 0.3 u, smoothed, faded above the glove; weld seam vertices first or the sleeve cracks) until no glove edge crosses a sleeve triangle.
   Shrinking the glove instead leaves jagged cuffs wherever the sleeve hem is cut at a slant. Tools: trenchwarfare-cs2 `tools/agent_gloves.py`, `tools/fit_gloves.py`.
7. **Materials:** the CS:GO VertexLitGeneric base texture decoded to PNG with a simple vmat.
8. **In game:** `pawn.SetModel(path)` from the map script (a `Model_<name>` / `ChangeModel` input), with a hidden `prop_dynamic` of the model in the map so it's loaded.
   Agent models often don't render in Hammer's viewport; that's normal.

The Power Ranger reused the finished Octodad vmdl with only the paths swapped (its ragdoll wasn't checked in game). The fallback when a rebuild isn't worth it:
keep the stock model and only tint/mark the player, or map CS:GO player models to the nearest CS2 agent (mg_50arenas has a 33-model table, e.g.
`ctm_gign → ctm_gendarmerie/ctm_gendarmerie_varianta`).

### Script-driven characters

- Hiding the parked pawn (two methods, both used): see [cs_script-notes, parking](../reference/cs_script-notes.md#players-parking-cameras-and-input).
  `SetModel` on a live pawn to a stock agent drew the local body in first person in mg_trenchwarfare and was removed.
- Every model the script swaps to must be precached by a hidden `prop_dynamic` in the map's cache room.

## Animated rigs (Puppet Brawl)

One invisible rig model plays every animation, and stock agents are **bone-merged** on top (a `point_template` holding the rig `prop_dynamic` and an agent
`prop_dynamic` parented to it with attachment `!bonemerge`), so one animation set drives every look. The full pipeline, entity keys, script inputs and file list:
[`create/anim/README.md`](../../create/anim/README.md) (Node 22+; compiled-file readers in [`create/s2/`](../../create/s2)).

- **Skeleton:** the CS2 agent skeleton, 77 bones, read from a stock agent `vmdl_c` (`create/s2/`; not committed, it's Valve's data). Root `root_motion` →
  `pelvis` → `spine_0..3` → `neck_0` → `head_0`; `clavicle_L/R`, `arm_upper/lower_L/R`, `hand_L/R`, fingers `finger_{thumb_0..2, index/middle/ring/pinky_meta, _0.._2}_L/R`,
  `scapula_L/R`, `leg_upper/lower_L/R`, `ankle_L/R`, `ball_L/R`, plus `*_TWIST*` bones. Model space +X forward, +Y left, +Z up; agents face +X in bind.
  Puppet Brawl's agents: `tm_professional_varf`, `ctm_swat_varianth`, `ctm_fbi_variantb`, `tm_leet_variantf` (under `agents/models/`).
- **Rig vmdl** (`create/anim/rig_vmdl.mjs` `writeRig`): reference SMD with one 0.04-unit triangle per bone (material `<name>_dot` remapped to a dark vmat),
  `BoneMarkupList { bone_cull_type = "None" }`, `anim_graph_name = ""`, and an `AnimationList` of `AnimFile` entries: `name`, `looping`,
  `fade_in_time = fade_out_time` (Puppet Brawl: 0.03 s for hit/block/launch/land clips, 0.12 s loops, 0.05 s otherwise), `framerate = 64.0`,
  `source_filename = "models/…/anims/<clip>.smd"`, `delta/worldSpace/hidden = false`, `start_frame = end_frame = -1`. An extra `name = "idle"` entry with
  `is_default_idle_anim = true` matches the template props' `StartingAnim`/`IdleAnim` `idle`.
- **Mirrored clips:** every clip has a `<clip>_m` twin (left/right bones swapped, reflected with a per-bone bind correction), played when the body faces the
  other way so the same side always faces the camera (Puppet Brawl: 196 clips → 392 SMDs).
- **Making clips:** 2D game poses lifted to 3D; full-body postures from compact specs; hand shapes (fist with thumb wrap, relaxed, open, chop, claw);
  CMU mocap (BVH, 120 Hz) retargeted by rest-matched world rotations, cut, aimed along +X, placed on the support foot, retimed with `[gameFrame, takeFrame]`
  keys, blended in/out of the stance, support foot locked, feet floored. Mocap discovery: `analyze.mjs` lists strikes in a take → `gallery.mjs` strips →
  pick a moment → key it. Takes used: [external-tools.md](../reference/external-tools.md).
- **Joint limits that worked** (`post.mjs`, `pose.mjs`): hinge IK for knees/elbows (legs hinge about the hips' left-right axis, arms about the bind elbow
  bend; knee floor 3.2), head keep-out r 7.2 and torso r 7.0 for arms, airborne thigh flex ≤ 148°, ankles toes-up 25° / pointed 60° / turn 25° / roll 25°.
- **Twist bones:** the bone-merged agent copies `arm_upper_*_TWIST*`, `arm_lower_*_TWIST*`, `leg_upper_*_TWIST*`, `head_0_TWIST` from the rig; left at bind,
  the skin wrings at shoulders, wrists and neck, so limb twist is spread along them (`spreadTwist`).
- **What you see is what hits:** 16 joints projected to the fight plane at 64 Hz (= the sim rate), 2 characters per value, embedded in the script as data;
  the game's hit and hurt boxes sample them (Puppet Brawl `bake.mjs`, project-specific).
- **Keep old reach when art is redone:** record the previous system's hit tips, hurt capsules and timing per move (`old_ref.mjs` → `old_frames.json`) and key the
  new clips to the same reach, so balance doesn't shift. Mid-rebuild, clips not yet redone are read back from the previous SMDs so the game stays complete.
- **In game:** `SetAnimationLooping` / `SetAnimationNotLooping` (value = clip name) **only when the clip changes**, `SetPlaybackRate` rounded to 0.02 and sent
  only on change (0 during hitstop, ⅓ during KO slow-mo). Bone-merge from the template is verified; blending via `fade_in_time`, the visible freeze at rate 0
  and the `FollowEntity` fallback are not ([cs_script-notes](../reference/cs_script-notes.md#spawning-and-moving-things)).
- Delivery: hundreds of SMDs go as a zip extracted into `rig/anims/` (or copied directly and sha1-checked), then the rig vmdl is recompiled.

### Checks without CS2

- `node create/anim/validate.mjs <anims dir>`: joint checker (wrong-way knees/elbows, twisted thighs, ankles out of range, limbs inside the body), worst
  first. Run it after every animation change as a gate; accept by-design flags explicitly in the notes (deep crouch, dancer kicks).
- **Review-sheet loop:** contact sheets of each clip on the real agent meshes from the game camera (`create/anim/preview.mjs`; Puppet Brawl's `review.mjs`
  adds hit circles and the old reach). The sheets go to the mapper; the annotated notes become the next task list.

### Troubleshooting a rig addon (from Puppet Brawl's README)

| Symptom | Likely cause |
|---|---|
| Console prints an old version, bodies don't animate | Old compiled script: `resourcecompiler -f -i` the `.js`, layout `.xml` and `.css`, reload the map |
| Bodies invisible | Rig vmdl not compiled |
| Agent frozen in T-pose | Bone-merge failed (rig compiled without bones, or parent/attachment wrong) |
| Pink checkerboard | Model or material not compiled |
| No HUD | `custom_hud_layout` not pointing at the `.vxml` |
| Silent sounds | Events missing from `soundevents_addon.vsndevts`, or a `point_soundevent` missing |

## Weapons

Rigging new weapon models onto stock weapon skeletons and swapping them in through `weapons.vdata`: [custom-weapons.md](custom-weapons.md).

## Checking stock CS2 assets offline

- `create/vpkdir.py` + `create/vtexread.py` index CS2's `pak01_dir.vpk`, pull files out of the chunks, list a `vmat_c`'s textures and decode `vtex_c` to PNG — used to
  preview Valve materials before choosing them and to export stock textures as non-animated copies. The `pak01_NNN.vpk` chunks (~100 MB each) are staged from
  the PC on demand.
- `create/s2/` (Node 22+, binary KV3 with LZ4/zstd): `prop_mesh.mjs <model.vmdl_c>` prints a stock prop's real bounds and materials (for placement),
  `agent_mesh.mjs` extracts an agent's skinned mesh for previews.
- Source 2 Viewer (CLI: Decompile & Export) turns stock `vmdl_c` models into editable vmdl + DMX, the starting point for weapons and player models.
