# Batch B progress (map fixes and effects)

Tracker: [../borrowed-2026-11.md](../borrowed-2026-11.md). Source of the ideas: CS2-Porter (MIT, copyright bcanusar), read through the GitHub API only.
Verification words from [compatibility.md](../../reference/compatibility.md). Nothing here is in-game verified.
Test copies: `C:\source1\cs2port\work\borrowed_test\` (never the addons).

| # | Status | Files |
|---|---|---|
| B1 | done (unit tested; real maps: run on copies, values cross-checked; not compiled) | new `tools/blendpaint.py`, `tools/disprestore.py`, `tools/tests/test_borrowed_b1.py` |
| B2 | done: report by default, opt-in fix (unit tested; run on a copy of mg_arcs_multigames) | `tools/repair.py` (`thin_triggers`), `tools/tests/test_borrowed_b2.py` |
| B3 | done: report by default, opt-in lift (unit tested; run on a copy of ttt_island17) | `tools/repair.py` (`spawn_lift`), `tools/tests/test_borrowed_b2.py` |
| B4 | done (unit tested; run on a copy of mg_antique_course with restore_io after it) | `tools/repair.py` (`numeric_names`, `imported_form`), `tools/tests/test_borrowed_b4.py` |
| B5 | done (unit tested; run on copies of mg_antique_course and mg_pirates; vpcf parsed, not compiled) | new `tools/smokestack.py`, `tools/tests/test_borrowed_b5.py` |
| B6 | done: adopted as opt-in `--bsp` / `--room`, default unchanged (unit tested; compared on 4 real maps) | `tools/skysplit.py`, `tools/tests/test_borrowed_b6.py` |
| B7 | done (unit tested; script simulated: api.py --strict --check, tscheck, mock engine) | new `tools/momentum.py`, `tools/tests/test_borrowed_b7.py` |
| B8 | done: evaluated, not adopted (reasons below) | this file only |

## B1 Blend displacements

**Finding (changes the premise).** Valve's importer does *not* drop the alphas on displacements it imports: on ba_jail_keimusho it wrote
`VertexPaintBlendParams:0` into `subdivisionData` of 439 subdivision meshes (and a bound, all-zero copy in `faceVertexData`). The alphas are
lost where the displacement never came through and `disprestore.py` rebuilt it from the BSP as a plain mesh: mg_pirates (4 blend meshes),
ttt_island17 (33), mg_crash_bandicoot_course (83) had no paint at all. disprestore read the BSP alpha and threw it away.
Second gap, not ours to fix here: the `assets` pass rebuilds a WorldVertexTransition material CS2 lacks as **single-layer** `csgo_complex`
(mg_pirates `nature/blendmilground004_2`, ttt_island17 `nature/blendrockdirt008a` / `blendsandgrass008a`, all four crash blends), so even
painted they show one texture. The importer itself writes these as `csgo_lightmappedgeneric` with `F_LAYERS 1`, `TextureLayer1Color`,
`TextureLayer2Color`, `TextureBlendModulation` (keimusho `brick_g1_blend.vmat`). See "Proposed for assets.py" below.

What was done:
- `tools/disprestore.py`: restored displacements now carry the BSP alphas as `VertexPaintBlendParams:0` (face-vertex stream, alpha/255 in all
  four channels, as the importer writes it); a paint stream copied from the template mesh is resized (it kept the template's length before).
- new `tools/blendpaint.py <vmap in> <vmf> <vmap out> [--content <addon root>] [--force] [--compare]` (and `run(m, vmfpath, content, force,
  compare, log)`): for maps already restored. Plain meshes: face corners matched by position to the VMF's displaced grid (both corner orders,
  the mesh picks). Subdivision meshes: only when their paint is missing or all zero (CS2-Porter's patch layout and inverse bilinear).
  Existing paint is kept unless `--force` (skink52's Hammer paint is never overwritten). `--content` lists blend materials whose vmat has one layer.
  Header credits CS2-Porter blend.py (MIT, copyright bcanusar).

How checked:
- Unit tested: `tools/tests/test_borrowed_b1.py` (6 tests: VMF grid, inverse bilinear, paint of a box top from a synthetic VMF, kept on rerun,
  save/reload, layer detection).
- Real data, on copies in `C:\source1\cs2port\work\borrowed_test\`:
  - ba_jail_keimusho `--compare` (the importer's paint as reference): of 178 subdivision meshes it could match, 109 identical to the
    importer's values with the CS2-Porter corner order (51 with the other order), 55 differ by interpolation (meshes not split on the grid),
    14 have faces skink52 moved since (no VMF match). 89.9% of 61,084 values within 0.02.
  - disprestore (patched) on keimusho with `ba_jail_os_keimusho_v2.bsp`: 924 restored meshes painted (= the VMF's 924 displacements with
    alpha); blendpaint's VMF values vs disprestore's BSP values on those meshes: 435,314 of 437,744 within 0.02 (99.4%).
  - blendpaint on the live ports' copies: mg_pirates 4 meshes / 64 faces, ttt_island17 33 / 528, mg_crash_bandicoot_course 83 / 4,858
    (1 already painted, kept). All their blend vmats reported single-layer.
- Not compiled, not opened in Hammer, not in game.

skink52 must verify: open one painted map copy (e.g. ttt_island17 after the assets fix below) in Hammer, Paint Blend tool: the paint should
follow the CS:GO blend (grass/rock edges where they were). In game: the second texture shows on the terrain.

Open questions: whether Hammer re-derives subdivision paint from the face-vertex stream on edit (the importer leaves that one zero; blendpaint
copies the importer's form).

### Proposed for assets.py (owner: Batch A / integrating session)
When `fix_materials` rebuilds a CS:GO `WorldVertexTransition` vmt, write two layers like the importer instead of one `csgo_complex` layer:
```
Layer0
{
    shader "csgo_lightmappedgeneric.vfx"
    F_LAYERS 1
    TextureLayer1Color "materials/<basetexture>.png"
    TextureLayer2Color "materials/<basetexture2>.png"
    TextureBlendModulation "materials/<blendmodulatetexture>.png"   // only when the vmt has $blendmodulatetexture
    F_FANCY_BLENDING 1                                             // same condition
    g_vLayer1Tint "[1.000000 1.000000 1.000000]"
    g_vLayer2Tint "[1.000000 1.000000 1.000000]"
}
```
($basetexture2 has to be converted too; normals as TextureLayer1Normal / TextureLayer2Normal from $bumpmap / $bumpmap2.)
Then `python tools/blendpaint.py <vmap> <vmf> <out> --content <addon>` should report no single-layer blends.

## B2 Thin boost / gravity triggers

CS2-Porter (vmf.py) raises the top face of boost / gravity trigger_multiples at most 4 u high to 6 u, on its claim that CS2 misses touches on
them. Not seen in any of our ports. Following the 14 Nov rule, this ships as a report plus an opt-in fix:
- `repair.thin_triggers(m, c, fix=False)`: triggers that change velocity or gravity (trigger_push / trigger_gravity, or trigger_multiple /
  trigger_once with `AddOutput basevelocity|gravity`, or our converted `RunScriptInput PushIn_/Launch_/Gravity_`) whose height is at most 4 u.
  Report -> one TO CHECK line. `fix=True` moves the vertices at the top up so the trigger is 6 u high (bottom kept, rotated/scaled meshes skipped).
  The io script's push zones check the player with 24 u slack above the trigger box, so +2 u stays inside what they accept.
- Real data: mg_arcs_multigames copy: 33 of 52 boost triggers are 1-4 u high (4 u floor pushes, the 1 u `puschcircle_push` ring). Fix raised
  all 33 to 6 u; a rerun reports none. Other copies (keimusho, pirates, island, crash, pokemon, minecraft x2, terrortrain): none thin.
  (keimusho's 14 Nov thickening was of teleports/hurts for a compile warning, not boosts.)
- Checked: unit tested (`test_borrowed_b2.py` ThinTriggers: report-only by default, fix raises top only, non-boost trigger ignored).
- skink52 must verify (only if a boost seems not to fire): on mg_arcs_multigames (not yet tested in game), stand on a 4 u push pad and on the
  `puschcircle_push` ring; if they fail, run `stage_d.py <addon> <root> thintrigfix` and try again.

## B3 Spawns in the floor

mapsanity stays read-only (its docstring promises it never writes). The fix is in repair.py:
- `repair.spawn_lift(m, c, fix=False)` (CS2-Porter `_lift_spawns`, adapted to mapsanity's mesh floors): a spawn whose origin is on the floor or
  up to 8 u in it (highest floor under five footprint columns, ±15.5 u) goes to 2 u above that floor when nothing solid is within 72 u above
  (mapsanity's headroom test). Spawns 0.05-2 u above the floor (mapsanity spawn_low; imported spawns at 0.6-0.8 play) are not touched.
  Report -> TO CHECK; `fix=True` moves them and lists any left for lack of room.
- Real data: ttt_island17 copy: 23 spawns in the floor (mapsanity's centre-only test: 10 spawn_in_floor), 22 lifted, 1 left (no headroom);
  mapsanity afterwards: no spawn_in_floor. mg_pirates: 1 info_player_start 1.3 u in the floor. keimusho, crash, arcs, pokemon, minecraft x2,
  terrortrain: none.
- Checked: unit tested (`test_borrowed_b2.py` SpawnLift: sunk spawn lifted to 2 u, 0.7 u spawn left, spawn under a 40 u shelf left and listed).
- skink52 must verify: ttt_island17 (not yet tested in game): do all players get a spawn ("all teams are full" in console means CS2 refused
  spawns). Only then run `spawnliftfix` on it.

## B4 Names that look like numbers

**The importer does change them.** In mg_antique_course's untouched importer prefabs (`maps/prefabs/mg_antique_course/*.vmap`) the VMF's
path_tracks / train `001`, `002`, `003` came out as `1`, `2`, `3` and the ambient_generics `000` as `0`, in targetname, target and parentname
alike (consistent, so the train path still chains), while the train's output `OnStart -> 000 PlaySound` was dropped and stage C's `io` could
not put it back (no entity `000`). Float-typed keys get `%f` (`wait 0.500000`, `RefireTime`) in every importer prefab checked (nature, arcs,
color, pokemon, minecraft, terrortrain), which matches CS2-Porter's `1.01 -> 1.010000` for names. No other local VMF has numeric names
(16 checked).
- `repair.numeric_names(m, c, vmfp)` (step `numnames`): for name-like keys (targetname, target, parentname, filtername, ..., or any key whose
  VMF value is some entity's name) and output targets, maps the importer's text back to the VMF text. A converted text with more than one
  possible original ("07" and "7") is left and listed in TO CHECK.
- Real data: mg_antique_course copy: 9 values put back (targetname 5, target 3, parentname 1). Then `stage_c.restore_io` restores 60 outputs
  instead of 59: the extra one is `func_tracktrain 001 OnStart -> 000 PlaySound`.
- Checked: unit tested (`test_borrowed_b4.py`: forms, restore of names / target / output target, ambiguous "07"/"7" left and listed, rerun no-op).
- skink52 must verify: mg_antique_course in Hammer: the train path_tracks are `001`-`003` and the train's OnStart plays `000`; in game the
  train sound plays when the train starts (it was silent).

## B5 Smoke and other effects

Compared CS2-Porter's effect list (vmf.py `EFFECT_CLASSES`: env_steam, func_dustmotes, point_spotlight, beam_spotlight, env_spritetrail,
func_dustcloud, env_embers, func_smokevolume, env_smoketrail, env_fire, env_spark, env_smokestack, point_tesla) with ours: steam.py,
firefx.py (fire, spark), tesla.py, spotbeam.py (point_spotlight), glowfix.py, beams.py, particles.py (stock names) already cover theirs.
Missing here, and how often our VMFs have them (16 VMFs in `C:\source1\maps`):
func_dustmotes 115 (mg_antique_course 106), point_spotlight (covered), env_spritetrail 28 (mg_pirates 18, color 6, arcs 4),
beam_spotlight 64 (mg_crash_bandicoot_course, kept by the importer, nothing converts it), env_smokestack 9 (antique);
func_dustcloud, env_embers, func_smokevolume, env_smoketrail: none locally.

- new `tools/smokestack.py` (step / pass `smoke`, `smokestack.run(m, c, vmfpath)`): env_smokestack, env_smoketrail, env_spritetrail (point:
  converted in place), func_dustmotes, func_dustcloud, env_embers, func_smokevolume (brush: converted in place when the importer kept them,
  else added from the VMF at the box centre) -> info_particle_system with a generated vpcf66 particle `particles/port_smoke/<kind>_<hash>.vpcf`
  (the box size is baked into the particle, so dust boxes of different sizes get their own file) and a generated soft puff
  `materials/port_smoke/puff.png/.vtex`. Formulas from CS2-Porter's `_smokestack_params`, `_dustcloud_params`, `_embers_params`,
  `_smokevolume_params`, `_smoketrail_params` and its templates (credited in the header). TurnOn/TurnOff/Enable/Disable -> Start/Stop,
  other inputs (Toggle, Rate, JetLength...) listed. Smokestacks get angles 0 0 0 (rise along world z, wind in world yaw).
- Not done (outside my files): `beam_spotlight` (64 on crash) is a rotating spotlight beam; it belongs in `tools/spotbeam.py` (proposed below).
  Custom `.pcf` systems (CS2-Porter particles.py runs Valve's importer on a stub game folder with the map's .pcf files): ours lists them in TO
  CHECK; worth a separate item.
- Real data: mg_antique_course copy: 9 env_smokestack + 106 func_dustmotes -> 115 info_particle_system, 67 particle files; rerun adds nothing.
  mg_pirates copy: 18 env_spritetrail -> 1 shared trail particle, parents kept (`4c_ball_trail` -> `4c_ball`). All 68 vpcf files parse with
  `tools/kv3text.py`.
- Checked: unit tested (`test_borrowed_b5.py`: in-place + VMF conversion, start states, parent kept, input remap, files only under port_smoke,
  vpcf parse, rerun no-op, names carry values). Not compiled (would need a write into an addon), not seen in game.
- skink52 must verify: mg_antique_course in game: the yellow smokestacks rise and fade, the dust motes are visible but faint (Source drew small
  motes as hard dots; they are drawn 2x bigger here), mg_pirates: the cannon balls leave a short glowing trail. Open one vpcf in the particle
  editor and save it once to see it keeps its initializers.

### Proposed for spotbeam.py (owner: integrating session)
`beam_spotlight` (CS:GO only; keys spotlightlength, spotlightwidth, rendercolor, HDRColorScale, maxspeed, spawnflags 1 = start on,
2 = no dynamic light, 4 = start rotation on, 8 = reverse, 16/32/64 = X/Y axis...) is kept by the importer and draws nothing. The same cone
as point_spotlight along the entity's forward axis, plus (rotation flags) a func_rotating parent at maxspeed, would cover it.

## B6 3D skybox room from BSP areas

CS2-Porter sky3d.py takes the skybox room from the compiled map: the empty BSP leaves of the sky_camera's area (vbsp floods each sealed region
into its own area; area portals split them) plus the areas its portals reach; brushes touching the room go to the skybox map, brushes also
touching other areas are copied. Ours (`skysplit.py`) grows a box from the meshes around the sky_camera (bounds within 16 u).
- Added to `tools/skysplit.py`: `--bsp <map.bsp>` (split by the BSP room: nodes touching only room leaves move, nodes touching the room and
  another area stay and are copied into the skybox map; refuses when a spawn / teleport destination stands in the room or the room is the
  whole map), and `--room <vmap> <bsp>` (read-only comparison of the two methods). Default behaviour unchanged. Header credits CS2-Porter.
- Compared on real data (read-only): mg_antique_course port (9 nodes both ways), mg_bob2 port (79 = 79), ba_jail_skylight importer
  prefabs (13 = 13), mg_bombardment importer prefabs (2 = 2); no node differed and nothing was shared. de_nuketown: its port no longer has the
  skybox geometry (0 both ways). awp_submarine / enjoy_multigames: no sky_camera in the importer prefabs to test with.
  So on our data the BSP room fixes no case the auto box gets wrong; it is kept as the option to use when the auto box grabs playable space
  (pipeline.md already says "give a box" for that) and for its spawn-in-room refusal.
- Limits: BSPs with LZMA-compressed lumps are refused with a message; node bounds, not brush planes, decide touching (a big mesh near the
  room can come out "shared").
- Checked: unit tested (`test_borrowed_b6.py`, BSP reading stubbed: room / shared / elsewhere, split output, spawn refusal, non-BSP refused);
  real maps read-only as above. Not compiled.
- skink52 must verify: nothing unless `--bsp` is used on a map; then open both maps in Hammer and check shared walls weren't doubled visibly.

## B7 Momentum Mod triggers

- new `tools/momentum.py` (step / pass `momentum`; `run(m, c)` fills `c.momentum`, `patch_script(js, data)` adds or replaces the script
  section, the shared think loop included when missing). Our model, as gravity.py: each trigger becomes trigger_multiple firing
  `RunScriptInput Mom*_<n>` on `c.script` with the player as activator:
  - trigger_momentum_teleport: stop + resetang -> plain trigger_teleport (what CS2's does); otherwise MomTele_<n> (Teleport position; angles
    only with resetang; velocity zeroed only with stop).
  - trigger_momentum_speedthreshold: MomSpeedIn_<n> / MomSpeedOut_<n>; OnThreshold outputs -> OnUser1; the script fires FireUser1 on the
    trigger (`caller`) when horizontal / vertical speed passes the limit, on entry and every Interval while inside (OnThink).
  - trigger_momentum_slide: MomSlideIn / MomSlideOut; friction loss given back on the ground, slope pull (TraceLine down 16 u).
  - trigger_momentum_push: MomPush_<n> on start and/or end touch (spawnflags 1<<21 / 1<<22); modes 0 set, 1 add, 2 set if slower, 3 add if
    slower, 4 base velocity (added once), 5 variable push (added every tick over varpushduration, bias curve, as CS2-Porter's script).
  Semantics from CS2-Porter momentum.py (credited); its compiled script is not used.
- Calls looked up with `create/test/api.py` (OnScriptInput, Teleport new form, Entity.FireInput, Entities.FindByName, TraceLine,
  Console.GetConvarNumber, GetGroundEntity, GetAbsVelocity/Origin/Angles, GetPlayerController/Slot, SetThink/SetNextThink, OnPlayerReset).
- Checked: unit tested (`test_borrowed_b7.py`: conversions, kept teleport, OnThreshold -> OnUser1, push vector/modes/flags, script patch
  on a gen_script.build output and on an empty script, rerun replaces). Simulated: a generated test script (gravity + every Momentum kind)
  passes `python create/test/api.py --strict --check` (0 problems), `sh create/test/tscheck.sh` (OK) and
  `node create/test/mock_point_script.mjs <js> ents.json players=8 seconds=60` (OK: no errors). No Momentum map on this PC: no real-data run.
- Open: whether mode 5 (variable push) adds the push every tick (CS2-Porter's reading) or spreads one push over the duration; check against a
  Momentum map before relying on it.
- skink52 must verify: on the first Momentum Mod map ported, each trigger kind in game (teleport keeps speed, speed gates open, slides keep
  speed and pull down slopes, push pads).

## B8 Evaluation: s1stub.py and mdl.py

**s1stub.py** (CS2-Porter): a temporary Source 1 game folder holding only the map's VMTs and zero-filled DXT1 VTFs of the right size, so the
importer can work out brush texture scales without touching a game folder. Ours: `run_import.bat` unpacks `assets\<addon>*.zip` into the
CS:GO install's `csgo\` with `tar -k` (never overwrites) and runs Valve's importer against the real game folder; post_import_cleanup then
converts the real textures from there.
- What it would fix: nothing we log. The texture-scale failure it targets (importer can't read a texture -> 8192-wide scale) happens when the
  VMT/VTF is missing at import time; s1stub needs the same VMT and VTF size from somewhere, so a material that is missing everywhere stays
  missing. Our `facescale` step repairs those faces afterwards, and A6 (Batch A) checks it catches the 8192 case. A5 (Batch A) recovers
  compiler copies from the BSP, which is the real source of the missing ones.
- What it would cost: post_import_cleanup reads the real textures from the game folder for conversion, so the stub can't replace that folder;
  we'd run two Source 1 roots.
- Only real gain: no files left in the CS:GO install. Not a failure in any log (REVIEW.md, 45 cleanup reports). Not adopted; worth
  revisiting only if the install's `csgo\` ever causes a clash (two maps shipping different files under one path: `tar -k` keeps the first).

**mdl.py** (CS2-Porter): pure-Python MDL v44-49 + VVD + VTX + PHY reader that decompiles to QC + SMD (for a VMDL template). Ours:
cs_mdl_import per model under a watchdog, `weaponmodels` for `w_*` weapons, `vmdlfix.py`, `gibfix.py`, and Crowbar/Blender/ModelDoc by hand.
- Logged model failures, all 45 `*_cleanup_report.txt` under the content addons ("MODELS - FAILED TO COMPILE"): 11 reports list 1-7 each,
  47 models. 34 are CS:GO `w_*` weapon world models (handled by stage D `weaponmodels`). The rest: `characters/hostage_01`,
  `chicken/chicken` (x2), `player/tm_pirate_variantb/c`, `player/tm_professional_var3`, custom player models (`chickenleet`,
  `mapeadores/.../green`), and five props (`tomobobo/.../newbiclighter`, `props_doors/doormain01_static`, `props_c17/door01_left`,
  `props_wasteland/woodwall030b_window01a_bars` (probably the empty bodygroup names `vmdlfix.py` now fixes: ttt_island17's window bars), `3d/penis/penis`).
  The 10 `*_mdl_import.log` files show no stall and no crash; only "skipping absent PHY file" notes (harmless).
- A geometry-only decompile would not give working player / character models (skeleton and animations are the point), and those stock
  ones exist in CS2 (`chicken`, `hostage`, the `tm_` agents): a remap like `weaponmodels` is the cheaper fix. For the remaining props the
  cause is not in our logs (cs_mdl_import wrote no .vmdl, or resourcecompiler refused it); a decompile would help only if cs_mdl_import
  itself is the failing step.
- Not adopted. Proposed instead (outside this batch): (1) extend `weaponmodels` into a stock-model remap for `chicken/chicken.mdl`,
  `characters/hostage_01.mdl` and the `player/tm_*` agents to their CS2 `.vmdl`; (2) have post_import_cleanup keep cs_mdl_import's last
  error line per failed model in the report, so the next review can tell decompile-worthy failures from compile ones. If (2) shows
  cs_mdl_import failing on static props, mdl.py (MIT) is the candidate for that fallback.

## Integration snippets (for the integrating session)

### B1
- `run_pass.py` / `stage_d.py` pass `blendpaint` (after disprestore, on any map with painted displacements):
  ```python
  import blendpaint
  if 'blendpaint' in passes and os.path.exists(vmfp):
      st, single = blendpaint.run(m, vmfp, c.content, log=c.log)
      if single: c.todo.append('blendpaint: blend materials with a single-layer vmat (paint shows only on a two-layer material): ' + ', '.join(single))
  ```
  Not needed in stage C's default list: the importer already paints what it imports; disprestore now paints what it restores.
- pipeline.md, after the `disprestore.py` paragraph: "Restored displacements keep their blend paint (the BSP's vertex alphas as
  VertexPaintBlendParams). `blendpaint.py <vmap in> <vmf> <vmap out> [--content <addon root>]` paints maps restored before 23 Nov 2026 (plain
  meshes matched to the VMF's displaced grid; subdivision meshes only where the importer left no paint; existing paint kept unless --force) and
  lists blend materials whose vmat has a single layer, where paint can't show. From CS2-Porter blend.py (MIT)."
- tools/README.md row: `blendpaint.py` | displacement alphas from the VMF -> VertexPaintBlendParams on restored / unpainted displacement meshes |
  `python blendpaint.py <vmap in> <vmf> <vmap out> [--content <addon root>] [--force] [--compare]`
- CAPABILITIES line: "Blend terrain (two textures painted across a displacement) keeps its painting when a displacement has to be rebuilt."
- CHANGELOG: "2026-11-23 [tools] disprestore keeps displacement blend paint; new blendpaint.py paints maps restored earlier (idea from CS2-Porter, MIT)."
- gotcha row (cs2-gotchas, near "Terrain blending"): "Displacements rebuilt by disprestore lost their blend paint, and the assets pass rebuilds
  missing WorldVertexTransition materials single-layer, so blend terrain showed one texture (mg_pirates, ttt_island17, mg_crash_bandicoot_course).
  | The importer keeps the paint on displacements it imports (subdivisionData stream). disprestore now writes the BSP alphas; blendpaint.py
  paints older maps; the vmat must have two layers (F_LAYERS 1)."
- external-tools credit: CS2-Porter (MIT, copyright bcanusar): blend.py displacement grid / subdivision paint layout -> blendpaint.py.

### B2 / B3
- `stage_c.py`, in the step list after `trigsplit` (report only, cheap):
  ```python
  if 'thintrig' in steps: repair.thin_triggers(m, c)            # report only; stage D thintrigfix raises them
  if 'spawnlift' in steps: repair.spawn_lift(m, c)              # report only; stage D spawnliftfix moves them
  ```
  and add `'thintrig'` (after `'trigsplit'`) and `'spawnlift'` (after `'thintrig'`) to the default `steps` list and the docstring.
- `stage_d.py` passes (opt-in fixes; also add them to the PASSES list / usage line):
  ```python
  if 'thintrigfix' in passes: repair.thin_triggers(m, c, fix=True)
  if 'spawnliftfix' in passes: repair.spawn_lift(m, c, fix=True)
  ```
  `run_pass.py`: the same two lines (it already imports repair).
- pipeline.md, under "Trigger repairs": "`thintrig` lists boost and gravity triggers at most 4 u high (CS2-Porter reports CS2 can miss touches
  on them; not seen in our ports). Stage D `thintrigfix` raises their top face to 6 u: only for a map where a boost was seen not to fire
  (14 Nov 2026 rule). `spawnlift` lists spawns on or up to 8 u in the floor (CS2 may refuse them: "all teams are full"); stage D
  `spawnliftfix` puts each 2 u above the floor when a player fits. Ideas from CS2-Porter vmf.py (MIT)."
  Also add `thintrig, spawnlift` to the step-key list and `thintrigfix, spawnliftfix` to the stage D pass list (ci/check_repo.py compares them).
- tools/README.md: extend the repair.py row with "thintrig/thintrigfix, spawnlift/spawnliftfix".
- CAPABILITIES: "Reports boost pads that are paper-thin and spawns sunk into the floor; can fix both on request."
- CHANGELOG: "2026-11-23 [tools] repair.py: thin boost/gravity triggers and spawns in the floor reported in stage C, opt-in stage D fixes
  thintrigfix / spawnliftfix (ideas from CS2-Porter, MIT)."

### B4
- `stage_c.py`, right after `merge` and before the `nullparams`/`io` lines (restore_io must see the exact names):
  ```python
  if ('numnames' in steps or 'io' in steps) and os.path.exists(vmfp): repair.numeric_names(m, c, vmfp)   # "000" -> "0" undone before io
  ```
  (`vmfp` is defined after merge; move the `vmfp = ...` line above it if needed.) Add `numnames` to the step-key list (it runs with `io`, like
  nullparams). `stage_d.py` / `run_pass.py`: `if 'numnames' in passes and os.path.exists(vmfp): repair.numeric_names(m, c, vmfp)`; for a ported
  map run `numnames,io` (or `numnames,droppedio`) so dropped outputs to those names come back.
- pipeline.md, under "Dropped outputs": "Before the diff, names the importer read as numbers (`000` -> `0`, `1.01` -> `1.010000`; target,
  parentname and output targets too) get the VMF text back (`numnames`, `tools/repair.py`; mg_antique_course's train path and its
  `000` sound). A converted name that could come from two VMF names is listed, not guessed. From CS2-Porter (MIT)."
- gotcha row: "Entity names that look like numbers (`000`, `001`, `1.01`) | The importer stores them as numbers (`0`, `1`, `1.010000`), in
  targetname/target/parentname, so outputs naming the original text reach nothing and are dropped (mg_antique_course `000 PlaySound`).
  | Stage C `numnames` puts the VMF text back before restoring outputs."
- CHANGELOG: "2026-11-23 [tools] repair.py numnames: entity names the importer read as numbers get their VMF text back (mg_antique_course;
  idea from CS2-Porter, MIT)."

### B5
- `stage_c.py`: `import smokestack`; after the `steam` line: `if 'smoke' in steps: smokestack.run(m, c, vmfp)`; add `'smoke'` after `'steam'` in
  the default list and the docstring. In `dead_entities` (line ~470), drop the env_spritetrail TO CHECK line when `'smoke' in steps`
  (smokestack converts them). `stage_d.py` / `run_pass.py`: `if 'smoke' in passes: smokestack.run(m, c, vmfp)`.
- pipeline.md, after the env_steam paragraph: "**Smoke, dust and trails** (`smoke`, `tools/smokestack.py`): env_smokestack, env_smoketrail,
  env_spritetrail, func_dustmotes / func_dustcloud, env_embers and func_smokevolume draw nothing in CS2 (the importer drops func_dustmotes).
  Each becomes an info_particle_system playing a generated `particles/port_smoke/<kind>_<hash>.vpcf` built from its keyvalues (rate, speed,
  spread, sizes, colour, lifetime; dust in its brush box) with a generated soft puff; brush ones come back from the VMF. TurnOn/TurnOff ->
  Start/Stop. Formulas from CS2-Porter (MIT). Not yet seen in game (mg_antique_course, mg_pirates)."
- tools/README.md row: `smokestack.py` | smoke / dust / ember / trail entities -> generated vpcf66 particles | stage C step / stage D pass `smoke`.
- CAPABILITIES: "Smoke stacks, floating dust, embers and sprite trails come back as particles."
- CHANGELOG: "2026-11-23 [tools] smokestack.py: env_smokestack, func_dustmotes, env_spritetrail and other smoke effects -> generated particles
  (formulas from CS2-Porter, MIT)."
- gotcha row: "env_smokestack, env_spritetrail, func_dustmotes, env_embers, func_smokevolume draw nothing in CS2 (func_dustmotes is not even
  imported). | Stage C `smoke` makes generated particles from their keyvalues."
- external-tools credit: CS2-Porter vmf.py effect parameter formulas and assets/*.vpcf templates -> smokestack.py.

### B6
- pipeline.md, `skysplit.py` paragraph, add: "`--bsp <map.bsp>` takes the room from the compiled CS:GO map instead (the sky_camera's BSP area
  and the areas its area portals reach; walls shared with the play space are copied into both maps; refused when a spawn is in the room);
  `--room <vmap> <bsp>` shows what each method would move. Same result as the auto box on the four maps compared (23 Nov 2026). From
  CS2-Porter sky3d.py (MIT)."
- tools/README.md: usage line `skysplit.py <in> <main out> <sky out> <name> [box] [--bsp <map.bsp>]`, `skysplit.py --room <vmap> <bsp>`.
- CHANGELOG: "2026-11-23 [tools] skysplit.py --bsp / --room: 3D skybox room from the BSP's areas (idea from CS2-Porter, MIT)."

### B7
- `stage_c.py`: `import momentum`; after the `gravity` line: `if 'momentum' in steps: momentum.run(m, c)`; add `'momentum'` after `'gravity'` in
  the default list. Script: in the block that writes `<addon>_io.js`, include `getattr(c, 'momentum', None)` in the "anything to write"
  condition, and after `js = gen_script.build(...)`:
  ```python
  if getattr(c, 'momentum', None): js = jsapi.ensure_imports(momentum.patch_script(js, c.momentum))
  ```
  (gen_script itself unchanged; the follow-up-pass branch `passes and only_phys` needs the same: patch the existing file.)
  `stage_d.py` pass `momentum`: run, then `momentum.patch_script(open(existing_js).read(), c.momentum)` like the gravity pass.
- pipeline.md, after trigger_gravity: "**Momentum Mod triggers** (`momentum`, `tools/momentum.py`, for bhop / surf maps made for Momentum Mod):
  trigger_momentum_teleport (kept as trigger_teleport when it stops the player and sets the view, else script MomTele_<n> keeping speed or
  angles), _speedthreshold (OnThreshold -> OnUser1, fired by the script when the speed passes the limit), _slide (no ground friction, slopes
  pull) and _push (velocity set / added once on start or end touch, or a variable push) -> trigger_multiple + io script. Semantics from
  CS2-Porter (MIT). Simulated only."
- tools/README.md row: `momentum.py` | Momentum Mod triggers -> trigger_multiple + io-script section | step / pass `momentum`.
- CAPABILITIES: "Bhop and surf maps made for Momentum Mod keep their special triggers (teleports that keep speed, speed gates, slides, push pads)."
- CHANGELOG: "2026-11-23 [tools] momentum.py: Momentum Mod triggers -> script-driven triggers (semantics from CS2-Porter, MIT; simulated)."

### B8
- No code. Tracker status line: "B8 skipped: evaluated; neither removes a failure we log (s1stub: texture scale already repaired by
  facescale and depends on the same missing files; mdl.py: 34 of 47 logged model failures are w_ weapons already remapped, the rest mostly
  rigged characters). See B.progress.md for the two smaller proposals."

## Batch checks (23 Nov 2026, end of batch)
- `python -m unittest discover -s tools/tests`: 289 tests OK (the 6 new files add 21).
- `python ci/check_repo.py`: all PASS (a raw ESC character in repair.py was caught by the `control` check and replaced by `\x1b`).
- `python ci/check_links.py --anchors --baseline ci/known_broken_links.txt`: 0 broken.
- Not done here (integrating session): copying the changed tools to `C:\source1\cs2port\tools` (blendpaint.py, smokestack.py, momentum.py,
  repair.py, skysplit.py, disprestore.py), step registration, docs rows. Nothing committed. Test copies stay in
  `C:\source1\cs2port\work\borrowed_test\` (map copies, outputs; safe to delete).
