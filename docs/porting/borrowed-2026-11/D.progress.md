# Batch D progress (follow-ons from Batch B)

Items from B.progress.md: D1 two-layer WorldVertexTransition vmats (assets.py), D2 beam_spotlight (spotbeam.py),
D3 model failures: cs_mdl_import error line in the report + stock-model remap (chicken, hostage, tm_/ctm_ agents).

| Item | Status | Files |
|---|---|---|
| D1 | done (unit tested, compiled one vmat; not in Hammer / game) | `tools/assets.py`, `tools/tests/test_borrowed_d1.py` |
| D2 | done (unit tested, run on the crash copy; not compiled, not in game) | `tools/spotbeam.py`, `tools/tests/test_borrowed_d2.py` |
| D3 | done (unit tested; stockmodels run report-only on live prefabs; cleanup change not run on the PC) | `scripts/post_import_cleanup.py`, new `tools/stockmodels.py`, `tools/tests/test_borrowed_d3.py` |

Checks at the end: `python -m unittest discover -s tools/tests`: 311 tests OK. `python ci/check_repo.py`: all PASS.
Nothing copied to `C:\source1\cs2port\tools` / `scripts` (the integrating session deploys). Nothing written into a live addon except
the scratch addon `zz_borrowed_test` (no `cs2.exe -tools` was running; only the dedicated server).

## D1 Two-layer WorldVertexTransition materials

**What Valve's importer writes** (read from `ba_jail_keimusho/materials/brick/hr_brick/inferno/brick_g1_blend.vmat`,
`flagstone_d_blend.vmat`, `mg_nature_multigames/materials/nature/blendmilground004_2.vmat`): `csgo_lightmappedgeneric.vfx`,
`TextureLayer1Color` / `TextureLayer2Color`, `TextureLayerNNormal` **only when** the vmt has that `$bumpmap`/`$bumpmap2`,
`TextureLayerNRoughness materials/default/default_rough_s1import.tga`, `TextureLayerNAmbientOcclusion materials/default/default_ao.tga`,
`TextureBlendModulation` + `F_FANCY_BLENDING 1` when `$blendmodulatetexture` (else `F_FANCY_BLENDING 0`, no modulation key),
`F_LAYERS 1`, `g_vLayer1Tint` / `g_vLayer2Tint` white, `F_TEXTURETRANSFORMS 0`, `SystemAttributes { PhysicsSurfaceProperties(2) }`.
Normals: `<bumpmap>_normal.tga` with the **same pixels as the VTF** (checked: keimusho flagstone_d_normals, pixel values equal within 1)
plus a sidecar `<bumpmap>_normal.txt` `"settings" { "legacy_source1_inverted_normal" "1" }` (the compiler flips green). The importer passes
`$ssbump` maps through as normals (wrong, cs2-gotchas); ours rebuilds them with `texfix.ssbump_to_normal` into `<bumpmap>_ssbn.tga` (+ the same sidecar).
Not copied: `$detail` (importer writes `TextureLayer1Detail` + `F_DETAILTEXTURE`), `$basetexturetransform`.

What was done in `tools/assets.py`:
- `fix_materials`: a missing material whose CS:GO vmt is `WorldVertexTransition` with `$basetexture2` -> `write_blend` (two-layer vmat
  in the importer's form, every texture converted: `$basetexture`, `$basetexture2`, `$bumpmap`, `$bumpmap2`, `$blendmodulatetexture`).
  Waits for a VPK chunk like the one-layer path. Log line "built N missing blend (WorldVertexTransition) materials as two-layer ...".
  First-layer texture missing -> falls back to the old one-layer path. Only missing materials are rebuilt, so a rerun on an existing port
  changes nothing.
- new `upgrade_blends(m, c, csgo_vpk, archives)` (opt-in): rewrites one-layer vmats **our** earlier runs wrote (header `// Rebuilt from CS:GO`,
  no `F_LAYERS`) whose vmt is WVT with `$basetexture2`. Importer-written and hand-made vmats are never touched; rerun is a no-op.
- new CLI: `python tools/assets.py upgrade-blends <map.vmap> <addon content dir> <out dir> [--root <stage root>] [--csgo <CS:GO csgo folder>]`:
  writes the vmats + textures under `<out dir>` for review; refuses an `<out>` inside the addon.
- helpers `convert_texture`, `blend_vmat`, `write_blend`. `fix_alpha` / `texfix._opacity_and_glow` skip non-`csgo_complex` vmats, so the
  blends aren't touched by them; `matflags` ssbump fix matches only `TextureNormal`, not `TextureLayerNNormal` (no double conversion).

How checked:
- Unit tested: `tools/tests/test_borrowed_d1.py` (5 tests: importer form incl. normal sidecar and surfaceprops, blendpaint.vmat_layers = 2,
  no modulation -> F_FANCY_BLENDING 0, ssbump -> `_ssbn.tga`, waits for a VPK chunk, upgrade only touches our one-layer rebuilds, rerun no-op,
  CLI refuses out-in-addon).
- Real data (copies in `C:\source1\cs2port\work\borrowed_test\`; output `d1_out\<addon>`, merged vmat view `d1_merged\<addon>`):
  `assets.py upgrade-blends` on mg_pirates (2: blendmilground004_2, blendsandweed005a), mg_crash_bandicoot_course (6:
  blendgraveldirt001a, blend_dirt_concrete_07_aztec, blend_dirt_roots_01, blend_grass_concrete_01, blendswampmud_aztec, rockwall007),
  ttt_island17_pezversion (2: blendgrassgravel001a, blendsandgrass008a; `--root` for its embedded files).
  `blendpaint.py <vmap> <vmf> <out> --content <dir>`, live vmats vs. upgraded: mg_pirates 1 single-layer -> 0; crash 4 -> 0;
  ttt_island17 3 -> 2: the two left are **not blends in CS:GO either** (`grass/hr_grass/grass_b` is LightmappedGeneric in CS:GO's VPK;
  the map's packed `nature/blendrockdirt008a.vmt` is a LightmappedGeneric "coast bumpmap upgrade"), so blendpaint's report is right there.
- Compiled: `materials/nature/blendsandweed005a.vmat` (two layers, both normals with the sidecar) + its textures in `zz_borrowed_test`
  with `python tools/rcompile.py asset ... --force`: ok, 7 compiled, 0 failed.
- Not opened in Hammer, not in game; whether the compiler honoured the normal sidecar was not inspected (the vtex_c exists).

skink52 must verify: in Hammer, open a map copy after `upgrade-blends` output is copied in (e.g. ttt_island17 with blendsandgrass008a):
material shows two layers in the Paint Blend tool; in game the painted terrain shows grass/sand transitions, normals light the right way
(not inverted bumps).

Open questions: `$detail` on blends not carried (importer does); the `_wvt_patch` TO CHECK text in `fix_materials` still says "shows one layer".

### Snippets for files I may not edit

`tools/stage_d.py` (opt-in pass `blendupgrade`, run before `blendpaint` so its single-layer report sees the new vmats):
```python
    if 'blendupgrade' in passes and c.src:
        assets.upgrade_blends(m, c, c.src.vpk, c.src.arcs, src=c.src)
    if 'blendpaint' in passes and os.path.exists(vmfp):
        st, single = blendpaint.run(m, vmfp, c.content, log=c.log)
        single = [x for x in single if 'materials/%s.vmat' % x not in c.files]   # rewritten in this run (blendupgrade)
        ...
```
and `blendupgrade` in the stage_d usage line / pass list (ci/check_repo "docs" counts stage D passes against pipeline.md).

`docs/porting/pipeline.md`, assets section, after the WVT/compiler-copies sentence:
> A missing **blend** material (CS:GO `WorldVertexTransition` with `$basetexture2`) is rebuilt as the importer writes one: two-layer
> `csgo_lightmappedgeneric` (`F_LAYERS 1`, `TextureLayer1/2Color`, normals from `$bumpmap`/`$bumpmap2` with the importer's
> `legacy_source1_inverted_normal` sidecar, `$ssbump` rebuilt, `TextureBlendModulation` + `F_FANCY_BLENDING` with `$blendmodulatetexture`),
> so blendpaint's vertex paint shows. Ports made before 24 Nov 2026 got one-layer blends: stage D `blendupgrade` (opt-in) rewrites those
> (only vmats with our "Rebuilt from CS:GO" header), or `python assets.py upgrade-blends <vmap> <content> <out>` to review first.

`tools/README.md` row for assets.py usage: add `python assets.py upgrade-blends <map.vmap> <addon content> <out dir> [--root R] [--csgo DIR]`.
`CHANGELOG.md`: `24 Nov 2026: assets rebuilds missing blend materials as two layers like Valve's importer; stage D blendupgrade for older ports.`
`CAPABILITIES.md`: "Blend terrain (two textures painted together) is rebuilt with both textures, so painted grass/rock edges show."
`docs/reference/cs2-gotchas.md` (optional): "Importer normal maps keep Source 1's green channel and add a `<name>.txt` with
`legacy_source1_inverted_normal 1`; a hand-made vmat pointing at a Source 1 normal needs the same sidecar."

## D2 beam_spotlight

How spotbeam is called today: **nowhere in the pipeline** (no stage C step or stage D pass calls `spotbeam.run`; it was run by hand for
ba_jail_keimusho). So "the existing route" was given a CLI and a VMF reader, and stage wiring is a snippet below.

What was done in `tools/spotbeam.py`:
- `run(m, c, spots)` takes `point_spotlight` and `beam_spotlight` dicts (key case no longer matters). beam_spotlight: same cone along its
  forward axis, width `spotlightwidth`, strength renderamt x `HDRColorScale`; the importer's kept `beam_spotlight` at that origin is removed.
- Rotation (spawnflags 4, or Start/Stop/Reverse/Toggle sent to it): `func_rotating <name>_rot` at the lamp with the spotlight's angles,
  `maxspeed`, flags 4 -> 1 start on, 8 -> 2 reverse, 16 -> 4 X axis, 32 -> 8 Y axis, +64 never solid, a 2-unit toolsinvisible mesh.
  The beam func_brush stays unparented and gets `SetParent <name>_rot` from `port_logic_auto` OnMapSpawn / OnMultiNewRound (the
  doorsolid method: a func_brush parented in the map never shows). Start/Stop/Reverse/Toggle retargeted to `<name>_rot`; LightOn/LightOff ->
  Enable/Disable. Unnamed rotating ones get `port_bspot_<n>`. Axis mapping follows Source 1, where beam_spotlight and func_rotating use the
  same angle-velocity axes (default yaw, X = roll, Y = pitch).
- Rerun adds nothing (a func_brush already at the beam's midpoint is skipped).
- `from_vmf(path)`, `kept(m)` (importer's entities, no VMF), CLI `python tools/spotbeam.py <map.vmap> <map.vmf | -> <out.vmap> [--files <dir>]`.
- Not rebuilt: the dynamic light a beam_spotlight casts without spawnflags 2 (TO CHECK line with the count).

How checked:
- Unit tested: `tools/tests/test_borrowed_d2.py` (5 tests: VMF read, conversion with straight-up / default-length beams, func_rotating
  flags / maxspeed, SetParent wiring, Stop retarget, LightOff -> Disable, rerun no-op, no-VMF path, flag map).
- Real data: mg_crash_bandicoot_course copy (`borrowed_test\mg_crash_bandicoot_course.vmap` + `.vmf` -> `...bspot.vmap`, materials in
  `borrowed_test\d2_files`): 64 beam_spotlight -> 64 func_brush beams (func_brush 7 -> 71, beam_spotlight 64 -> 0, entity count unchanged),
  one material `spot_5ef143_83` (green 94 241 67). None rotate (all spawnflags 1, angles -87: straight up). 2 min 10 s (world voxelising).
- Not compiled, not in game. The rotating path is unit tested only (no local map has a rotating beam_spotlight).

skink52 must verify: crash in game: the green beams stand up from the 64 lamps and fade; a map with a rotating beam_spotlight, when one
turns up: it sweeps about the lamp at the CS:GO speed.

### Snippets
`tools/stage_c.py` (new step `spotbeam`, after `beams`; needs the VMF):
```python
    if 'spotbeam' in steps and os.path.exists(vmfp):
        import spotbeam
        spotbeam.run(m, c, spotbeam.from_vmf(vmfp))
```
`tools/stage_d.py` (pass `spotbeam`): same lines with `passes`; with no VMF `spotbeam.run(m, c, spotbeam.kept(m))`.
Also remove `point_spotlight` from `stage_c.DROPPED` / `droppedio.IMPORTER_DROPS` reporting once the step runs (it is rebuilt).
`docs/porting/pipeline.md` beams section:
> **point_spotlight / beam_spotlight** (`spotbeam`). The importer drops point_spotlight and keeps beam_spotlight, which draws nothing in CS2.
> Both become never-solid additive func_brush cones along the lamp's forward axis, cut at the first wall. A rotating beam_spotlight gets a
> func_rotating `<name>_rot` (its maxspeed and axis flags) that the beam is SetParent to at spawn; Start/Stop/Reverse go to it. The dynamic
> light beam_spotlight cast is not rebuilt (TO CHECK).
`tools/README.md` spotbeam row usage: `python spotbeam.py <map.vmap> <map.vmf | -> <out.vmap> [--files <dir>]`.
`CHANGELOG.md`: `24 Nov 2026: spotbeam converts beam_spotlight too (crash: 64 beams), rotating ones via func_rotating.`
`CAPABILITIES.md`: "Spotlight beams, including CS:GO's rotating beam_spotlight, are rebuilt as glowing cones."

## D3 Model failures

### (a) cs_mdl_import's own error line in the report
Where failures are logged: `scripts/post_import_cleanup.py` phase 1 (`import_model` -> FAILED TO IMPORT with a reason; `resourcecompiler` ->
FAILED TO COMPILE with no reason), report in phase 4 (`autoport.py` counts them, "See WHY MISSING"). `tools/gibfix.py` reads the *build* log
("Failed loading resource"), not import failures, so it was left unchanged. (`scripts/modelsfromrefs.py` has the same compile loop; not in
my files: same change would apply there.)

What was done (post_import_cleanup.py):
- `error_line(text)`: the last error-like line (error/fail/cannot/unable/exception/assert/crash/invalid/not found/missing/[killed);
  "Failed to create CModelDocPhysicsHullFile Node" and "skipping absent PHY" (on every successful import too) only when nothing else matches;
  else the last line; cut at 220 chars.
- `import_model`: remembers the log size before each attempt and adds ` - cs_mdl_import said: "<line>"` (from that attempt's part of
  `<addon>_mdl_import.log`, header and command line skipped) to the stalled / no-.vmdl reason.
- model compile: `run_command_capture` (prints the output as before) and `mdl  (resourcecompiler said: "<line>")` in FAILED TO COMPILE.
  The `"  ("` separator is kept, so `explain_missing`, autoport's counts and the B8-style scans still split the name off.
- WHY MISSING now also covers FAILED TO COMPILE models (used-by + same name elsewhere).

How checked: unit tested (`test_borrowed_d3.py` ErrorLine: picks the real error over the hull-node noise, noise-only, empty, length cap;
module imported with Valve's `utils` stubbed). Not run on the PC (needs a real import). skink52 / next autoport run: the next cleanup
report with a failed model should show the importer's line after the name.

### (b) Stock-model remap: new `tools/stockmodels.py`
What actually failed (45 cleanup reports under content_addons, scanned 24 Nov): FAILED TO COMPILE `chicken/chicken` (ba_jail_skylight,
mg_kohztec_course), `characters/hostage_01` (ba_jail_seaside), `player/tm_pirate_variantb/c`, `tm_professional_var3`, custom
`chickenleet`, `mapeadores/.../green` (mg_50arenas, jb_yeetnam); FAILED TO IMPORT 27 `models/player/(c)tm_*` on mg_50arenas (older run;
post_import_cleanup now skips `models/player/` outright) and custom `player/slow/zombie_package/slow_1` (mg_antique_course).
Where they are used: chicken only in kohztec's / skylight's asset list and environment prefab (no prop uses it in the vmap: they are
`chicken` entities, which CS2 spawns with its own model; and `models/chicken/chicken.vmdl` **is** CS2's stock path, so it resolves anyway);
hostage_01 on a prop in ba_jail_seaside's gameplay prefab; the 32 agent props in mg_50arenas' gameplay prefab.

CS2 stock (from `borrowed_test\root\vpk\cs2_pak01_dir.vpk`): `models/chicken/chicken.vmdl` (+ chick, polish, silkie...),
`models/hostage/hostage.vmdl`, `characters/models/<family>/<agent>.vmdl` for ctm_fbi (base + a-h), ctm_sas (base, f, g), ctm_st6 (e, g, i-n),
ctm_swat (e-k), tm_phoenix (base, a-d, f-i), tm_leet (a-k), tm_balkan (f-l), tm_professional (varf-varj), ctm_diver, ctm_gendarmerie, tm_jumpsuit,
tm_jungle_raider, heavies. No gsg9, gign, idf, separatist, anarchist, pirate.

`stockmodels.run(m, c)` (needs `c.cs2v`): chicken -> same path; `models/characters/hostage_0N*` -> `models/hostage/hostage.vmdl`;
`models/player/[custom_player/legacy/](c)tm_*` -> same agent, else family base, else first variant, else team default (tm_phoenix / ctm_sas).
Custom player models untouched. Hammer's `map_asset_references` updated like weaponmodels. Log lists each repoint (with "family" / "variant" /
"team" when not the same agent); TO CHECK lists substitutes and that agents stand in CS2's default pose. CLI:
`python tools/stockmodels.py <map.vmap> <cs2_pak01_dir.vpk> [<out.vmap>]` (report only without out).

How checked: unit tested (`test_borrowed_d3.py` StockModels: remap table incl. the real failure names, run on a synthetic map, no VPK).
Real data, report only (no write) on the live vmaps / prefabs: mg_50arenas gameplay prefab 32 props repointed (fbi same; gign/gsg9/idf ->
ctm_sas team default; st6 a/d -> st6_variante; ...), ba_jail_seaside gameplay prefab hostage_01 -> models/hostage/hostage.vmdl,
skylight / kohztec nothing (no chicken props). Not compiled, not in game.

skink52 must verify: mg_50arenas (after the pass on a copy) in game: the agent statues show CS2 agents of the right side, size and pose OK
(CS2 agents have no CS:GO idle sequences); ba_jail_seaside: the hostage prop shows.

Open question: substitute choice for agents CS2 dropped (team default vs. something closer in look); skink52's call.

### Snippets
`tools/stage_d.py` next to `weaponmodels`:
```python
    if 'stockmodels' in passes:
        import stockmodels
        stockmodels.run(m, c)
```
Note: the agent props in mg_50arenas / seaside sit in **prefabs**; stage C's `merge` brings them into the map first (otherwise run the CLI
on the prefab vmap copy). Usage line: `stockmodels (CS:GO chicken / hostage / agent props -> CS2 stock models)`.
`docs/porting/pipeline.md` (weaponmodels paragraph): add "`stockmodels` does the same for CS:GO's chicken, hostage and tm_/ctm_ agent
props (agents CS2 dropped get the team default, TO CHECK)". `tools/README.md`: row for `stockmodels.py`. CHANGELOG / CAPABILITIES:
"Statues of CS:GO agents, hostages and chickens use CS2's own models." For (a): pipeline.md cleanup-report section: "each failed model
now carries the importer's / compiler's own error line; WHY MISSING covers compile failures too."
