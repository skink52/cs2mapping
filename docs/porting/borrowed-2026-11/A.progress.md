# Batch A progress (lighting and materials)

Tracker: [../borrowed-2026-11.md](../borrowed-2026-11.md). Source of the ideas: bcanusar/CS2-Porter (MIT), read through the GitHub API only.

| # | Status | Notes |
|---|---|---|
| A1 | done: unit tested; the glow vmat compiled | `tools/texlights.py` (new), step `texlights` (opt-in proposed) |
| A2 | done: unit tested (vrad constants checked against a real compiled light list) | `tools/lighting.py` `calibrate` = step `lightcal` (opt-in, report by default) |
| A3 | done: unit tested (no fully-bright map on the PC) | `tools/daylight.py` `fullbright` (opt-in pass) + report |
| A4 | done: unit tested; vposts compiled and decoded | new `tools/postfx.py` (steps `colorcorrect`, `underwaterfog`), gotcha row fixed |
| A5 | done: unit tested; checked on a real pakfile | `tools/assets.py` `compiler_copies`, `Source` (used by `assets`, `alpha`, texfix through c.src) |
| A6 | done: unit tested; run on a copy of a real importer geometry | `tools/texfix.py` `implied_widths`, `face_scales` extended |

## A1 texture lights

- New `tools/texlights.py`: `Bsp` (seek-per-lump reader, LZMA lumps), `texinfo_list`, `faces`, `world_lights` (HDR list when the
  map has HDR lightmaps), `lightmaps_lit`, `texture_lights` (emission e = pi x sum(surface-light intensity) / lit face area per
  material, compiler copies mapped back with `unpatched`), `self_illum`, `rect_lights`, `glow_vmat`, `plan`, `run` (stage step), CLI report.
- Self-illum written only on csgo_complex vmats that are in the addon (`F_SELF_ILLUM`, `g_flSelfIllumBrightness` = log2(max e),
  tint = e / max e, albedo factor 0, existing mask kept else `materials/default/default_mask.tga`). Stock CS2 materials (not in the
  addon) and other shaders get `light_rect` lights in front of the faces (axis-aligned faces only; <= 256).
- BSP is found at `<root>/source1/maps/<addon>.bsp`, `$CS2PORT_BSP`, or `--bsp`. Not staged by pclocal today (snippet below).
- Survey of the 57 BSPs on the PC: texture lights only in mg_jahoukarail_2015 (devneons/white_neon, 1263 surface lights, e = 13.7,
  brightness 3.77) and ba_jail_ds_arctic_summer_v1 (lights/hr_single_pane_illum_ambient e ~ 500 -> brightness 8.96;
  de_nuke/hr_nuke/officelight_emitter_001_blue e ~ 18).
- Dry run on a copy of mg_jahoukarail_2015 (work\borrowed_test\root): white_neon.vmat -> F_SELF_ILLUM 3.773, 0 rect lights. 5 s.
- Open: whether CS2's bake lights the room from F_SELF_ILLUM surfaces as strongly as e predicts (not in-game verified);
  hr_single_pane at 2^9 may bloom.

## A2 light brightness

- Compared CS2-Porter `lighting.py` with ours. Added to `tools/lighting.py` (opt-in): `BspTracer`, `vrad_falloff`, `s1_brightness`,
  `match_legacy`, `calibrate` (report, or apply), `fifty_percent_note`. relight / lightbright unchanged.
- Found: vrad's `_fifty_percent_distance` falloff is 2/65.25 x (1 + d/D + 63.25 (d/D)^2) (all 50 such lights in
  ttt_cg_skyscraper_2017_b1's compiled list have c = 0.03065; `vrad_falloff` reproduces c/l/q). Our `falloff_ratio` assumed vrad
  fell back to linear and normalised to 100 u: ~8x too bright at 128 u. Not changed by default (14 Nov rule); `fifty_percent_note`
  adds a TO CHECK line and lightcal fixes it.
- Kept ours: 1000 lumens = legacy 1 = a 265 _light (importer's conversion; CS2-Porter's 200 -> 1000 comes from the importer's nan
  fallback); barn cone factor; no HDR cap (LDR cap 2 taken).
- Report runs (read-only on the live vmaps): ttt_terrortrain 66 quadratic lights x1.00 (consistency check); mg_n64_goldeneye 499
  lights median x1.19, 89 linear-falloff lights 3-5x brighter when matched over the real room distances; mg_fred_all 176 matched.

### A2 follow-up: mg_antique_course "median x0.01" (23 Nov 2026)

- The integrator's stage D `lightcal` run on mg_antique_course reported "calibrated / current brightness median x0.01". **I found no
  units bug.** All 132 matched lights there are `_fifty_percent_distance` lights (D 28-60 u). The ratio is two real gaps multiplied
  together:
  1. The vmap was never relit (ported 24 Oct, before relight). Its values are the importer's, x7.08 of what relight gives.
  2. Calibrated / relight is x0.04: relight's linear fit is far too bright for short-D fifty-percent lights.
- I checked this against what CS:GO actually baked. The new `lighting.lightmap_check` reads the compiled HDR lightmap luxel on the
  floor under each light and compares it with every listed light's direct light (the compiled falloff, with lights behind a wall
  left out). On antique the median is 1.14 over 40 lights, so the compiled model lightcal uses matches the bake there.
  Units checked as well: HDR and LDR light lists agree; a quadratic light gives the same value as relight (terrortrain x1.00).
- Fix in `tools/lighting.py`: the report was misleading, not the numbers. `calibrate` now:
  - compares with what relight gives (from the VMF), not just the vmap's current value;
  - says when the current values are not relit (importer values);
  - counts the fifty-percent lights;
  - runs `lightmap_check`, and adds a TO CHECK line when that check is outside 0.5-2 over 10 or more samples.
- Rows are now `(name, class, current, calibrated, relight or None)`. Added helpers `relight_legacy`, `lightmap_check`, and the
  `check=` argument.
- Tests that would have caught it: `test_fifty_units_and_baseline` (fifty-percent light with an importer value: calibrated equals the
  compiled falloff's geometric mean; the report shows the relight comparison and "never relit") and `test_lightmap_check`. 39 batch A tests pass.
- Rerun (`work\borrowed_test\cal2.py`, read-only on the vmaps; VMF light entities from the BSP entity lump where no decompiled VMF exists):

  | Map | vs current | vs relight | lightmap check |
  |---|---|---|---|
  | mg_antique_course (HDR) | x0.01 | x0.04, all 132 fifty-percent | 1.14 |
  | ttt_cg_skyscraper_2017 (LDR) | x0.99 | x0.99; its 53 fifty-percent lights x0.10, the other 118 x1.00 | 5.34, so the compiled model does not explain its bake |
  | mg_n64_goldeneye (HDR) | x1.19 | x1.07 | 0.90 |
  | ttt_terrortrain (LDR) | x1.00 | x1.00 | 0.91 |
  | mg_fred_all (HDR) | x0.75 | x1.00 | 0.22 (11 samples; spots and unlisted lights dominate) |

  On skyscraper the floor under the fifty-percent lights bakes at ~0.8 where the light list predicts 0.13-0.47 (sky / bounce /
  something not in the list). So applying lightcal there would likely make those rooms too dark.
- Conclusion: lightcal stays opt-in. Apply it to fifty-percent lights only where `lightmap_check` is near 1 (antique yes, skyscraper
  no), and check in game first.

## A3 fully-bright maps

- `tools/daylight.py`: `is_fullbright` (BSP lightmap lumps absent or all black, `texlights.lightmaps_lit`), `unlit_vmat`,
  `fullbright(m, c, bsp=None, apply=True)`: addon csgo_complex world vmats -> csgo_unlitgeneric (see-through / self-lit / other
  shaders left lit and counted, stock materials listed in TO CHECK), a shadowless stationary light_environment straight down
  (angles 90 0 0) when the map has none, probe volumes when none. `run` refactored into `play_space`, `sun_props`,
  `probe_volumes` (same behaviour; smoke-run on a copy of mg_jahoukarail_2015, same log lines, 86 s, not saved).
- None of the 57 BSPs on the PC is fully bright (jb_sides_v1a_d_s2import.bsp reports it, but it is an import test with no lights).
  So: report in stage C (`apply=False`), the change only as the opt-in pass. Unit tested only.

## A4 colour correction and underwater

- Compile test in `zz_borrowed_test` (folder `lighting/postprocessing/borrowed_a4`, created next to the integrator's `rctest`),
  `.vpost_c` decoded with projects/cs21.6/tools/kv3bin.py (`m_colorCorrectionVolumeData`, 32^3 RGBA8):
  `CColorLookupColorCorrectionLayer` with `m_nDim = 32` + `m_lut` as a flat float list bakes the table exactly (<= 1/255);
  `m_lut` as a file path -> identity, `m_bHasColorCorrection` false; as `[r, g, b]` triples -> all black. Real tables (cc_dust,
  infected from CS:GO's VPK, iceskate_cc from mg_lego_multigames' pakfile): LUT layer max error 1/255; CS2-Porter's Curves +
  Saturation mean error 7 / 27 / 18 (max 31-206). So CS2-Porter's claim is true only for a file path; we write the table inline.
  mg_bombardment's hand-made vpost (10 Oct 2026, Post Processing editor) already has exactly this layer (`m_fileName` + `m_lut`).
- New `tools/postfx.py`: `read_lut`, `identity_lut`, `lut_layer` (default), `cc_layers` (mode 'curves'), `is_identity`, `vpost`,
  `add_layers`, `fog_colour`, `vmt_fog_keys` (raw VMT: assets.parse_vmt can't read "{r g b}"), `underwater_layers`,
  `underwater_vpost` (our filmic template + fog tint), steps `color_correction(m, c, vmfpath, mode='lut')` and `underwater(m, c)`.
  Global CC (falloff -1 or min == max, which CS:GO treats as global) goes in front of the master volume's own addon vpost, or onto
  a new master volume; a vpost that already has a lookup table is left; falloff ones get a box volume +-maxfalloff; named /
  start-disabled ones are written but left for the mapper (TO CHECK).
- Real run on a copy of mg_bombardment (VMF made from the BSP entity lump): its vpost already had the table -> left, nothing written.
- `docs/reference/cs2-gotchas.md` row "CS:GO Refract ... color_correction" rewritten with what the compile showed (level: compiled).
- The glow vmat (texlights) and an underwater vpost also compiled there; decoded: F_SELF_ILLUM 1 / brightness 3.773; underwater
  has tone mapping, bloom and colour correction.

## A5 materials from the compiler's copies

- `tools/assets.py`: `COPY_RE`, `compiler_copies(local)` (index of vbsp's full copies `materials/maps/<map>/x_<x>_<y>_<z>.vmt` /
  `x_wvt_patch.vmt` for originals the map didn't pack; "patch" copies skipped; wvt copy wins), `Source.has/read` fall back to them
  after the embedded files and CS:GO's VPK; `Source.copies_used`; `fix_materials` logs the ones used and lists _wvt_patch ones in
  TO CHECK (vbsp's wvt copy is the single-layer brush-face version of a blend). Fits the existing layout: the copies are already
  in `<root>/embedded/<addon>` (BSPSource unpacks the pakfile), so prep.py needs no change.
- Scan of 57 BSP pakfiles (watchdog, `work\borrowed_test\copies_scan.log`): full copies whose original is not packed in 21 maps, almost
  all stock CS:GO blends (already found in the VPK). Not stock either: custom/pebblesgrassblend (jb_mangaroons),
  agarden/agarden_grass_groundrock (ba_jail_os_keimusho_v2/_v3). Neither is used by the current ports' vmaps.
- Real check (`a5_real.py`): keimusho_v2's 105 pakfile vmts in a temp embedded folder -> 7 copies indexed;
  agarden_grass_groundrock now found (lightmappedgeneric, $basetexture agarden_massive_ground_rock_01_color), stock ones still from the VPK.

## A6 importer 8192-wide scales

- Measured on the importer's own geometry (the `*_environment_prefab.vmap` stage C leaves untouched): mg_pokemon_adventure 4,613 of
  5,373 faces and mg_nature_multigames 5,987 of 11,292 had the 8192 width; ttt_terrortrain 1 of 26,944.
- `facescale` already caught most: a face matched to one VMF side gets the VMF scale/shift (the importer's texcoords stay right).
  It missed faces with no single VMF mapping (overlapping brushes, no VMF side) unless the scale was below 0.01, and its fallback
  "texture size implied by the stored coordinates" could pick 8192 itself. Live vmaps after stage C still had 41 (pokemon) and 189
  (nature: rockwall01 121, woodm 8, ceilingtilea 7, anubis water 53) such faces.
- Added to `tools/texfix.py`: `IMPORT_PLACEHOLDER`, `implied_widths` (from CS2-Porter uvfix.py, adapted); in `face_scales`, a face
  without a VMF mapping whose stored coordinates imply 8192 x 8192 gets scale x r and shift / r with r = 8192 / the addon texture
  size (texcoords unchanged, so it looks the same and Hammer's Justify no longer moves it); 8192 is ignored when the texture size is
  implied from coordinates. New log line "... still had the importer's 8192-wide scale ...".
- Real run (`a6_real.py`, saved only to `work\borrowed_test`): pokemon's importer geometry with the VMF: 4,461 faces from the VMF
  as before + 154 cavewall faces by the new rule; rescan: 0 faces left at 8192. Without the VMF: 4,535 by the new rule, 78 left
  (water / cloud materials with no addon texture). Not Hammer verified: open a map after facescale and Justify a fixed face.

## Integration snippets (for the integrating session)

### stage_c.py

Imports: add `texlights, postfx, daylight` to the import line.

Step list: add none to the default list (all opt-in), but accept these names. After the relight / lightbright block and **before**
`if 'lights' in steps: lighting.run(m, c)` (lightcal sets ranges the stationary pass then trims):

```python
    if ('relight' in steps or 'lights' in steps or 'lightbright' in steps) and os.path.exists(vmfp): lighting.fifty_percent_note(c, vmfp)
    if 'lightcal' in steps or 'lightcal_apply' in steps:     # opt-in: brightness from the compiled CS:GO light list + BSP line traces
        bsp = texlights.find_bsp(c)
        if bsp: lighting.calibrate(m, c, bsp, apply='lightcal_apply' in steps, vmfpath=vmfp)
        else: c.todo.append('lightcal: no BSP staged at <root>/source1/maps/%s.bsp' % addon)
    if 'lights' in steps: daylight.fullbright(m, c, apply=False)    # report only: a BSP with no baked light
    if 'fullbright' in steps: daylight.fullbright(m, c)              # opt-in: unlit world materials, shadowless sun, probes
    if 'colorcorrect' in steps: postfx.color_correction(m, c, vmfp)  # opt-in until one map is seen in game
```

After the `assets` block and before `if 'matflags' in steps: texfix.material_flags(m, c)` (assets may have just rebuilt the vmat):

```python
    if 'texlights' in steps: texlights.run(m, c)     # opt-in: lights.rad texture lights -> F_SELF_ILLUM / light_rect (needs the BSP)
```

### stage_d.py

Imports: add `texlights, postfx`. After the `water` line (it needs watervol's underwater volumes):

```python
    if 'underwaterfog' in passes: postfx.underwater(m, c)            # after water: a vpost per CS:GO water fog colour
    if 'colorcorrect' in passes: postfx.color_correction(m, c, vmfp)
    if 'texlights' in passes: texlights.run(m, c)
    if 'lightcal' in passes or 'lightcal_apply' in passes:
        bsp = texlights.find_bsp(c)
        if bsp: lighting.calibrate(m, c, bsp, apply='lightcal_apply' in passes, vmfpath=vmfp)
        else: c.todo.append('lightcal: no BSP staged at <root>/source1/maps/%s.bsp' % addon)
    if 'fullbright' in passes: daylight.fullbright(m, c)
```

(`lightcal` before `lights` if both are given.) Add the five names to the docstring pass list and to the documented stage D list.

### Staging the BSP (autoport/pclocal.py root)

texlights, lightcal and fullbright need the BSP at `<root>/source1/maps/<addon>.bsp` (or `CS2PORT_BSP=`). `pclocal.root` copies the
VMF there already; copy the BSP the autoport state knows (`m.bsp`) with `safepath.copy_atomic` beside it. Without it the steps say so.

### docs/porting/pipeline.md (Follow-up passes)

- **Texture lights** (`texlights`, opt-in; needs the BSP staged): CS:GO `lights.rad` surfaces lit the map through surface lights the
  compiler put in the BSP (texinfo SURF_LIGHT + the light list); the importer keeps neither. Each material's emission is worked out
  from the BSP (pi x light / area); the addon's csgo_complex vmat gets `F_SELF_ILLUM` with that brightness (log2) and colour, and a
  material that can't glow (stock CS2, water, other shaders) gets `light_rect`s in front of its faces (<= 256). Unit tested and the
  vmat compiled; whether CS2's bake lights the room from the glow as strongly is not in-game verified (mg_jahoukarail_2015's
  devneons/white_neon: brightness 3.77). `python texlights.py <map.bsp>` reports. From CS2-Porter texlights.py (MIT).
- **Light calibration** (`lightcal` report / `lightcal_apply`, opt-in; needs the BSP): every light at the place of a compiled CS:GO light
  gets the brightness that gives the surfaces round it (64 line traces through the BSP tree) the light the compiled falloff gave.
  Same value as relight for quadratic lights; differs for linear / `_fifty_percent_distance` ones, which relight matches at 128 u with
  a falloff vrad doesn't use (fifty-percent lights come out ~8x too bright there; stage C says so in TO CHECK). From CS2-Porter lighting.py (MIT).
- **Fully-bright maps** (`fullbright`, opt-in; stage C `lights` only reports): a BSP with no lightmaps (or all black) was drawn fully bright;
  world vmats in the addon go `csgo_unlitgeneric`, a shadowless stationary sun straight down and probe volumes light players and
  weapons. Unit tested only. From CS2-Porter (MIT).
- **Colour correction** (`colorcorrect`, opt-in): each CS:GO `color_correction` (dropped by the importer) -> a `.vpost` with a
  `CColorLookupColorCorrectionLayer` holding its `.raw` table inline (compiled: the baked table matches within 1/255), global ones
  in front of the master volume's own vpost (or a new master volume), ones with a falloff in a box volume; named / start-disabled
  ones are written and left for the mapper. `postfx.py <file.raw>` prints the vpost. From CS2-Porter postfx.py (MIT), LUT route ours.
- **Underwater fog colour** (`underwaterfog`, stage D after `water`): each underwater post_processing_volume gets a copy of the
  filmic underwater vpost tinted to the `$fogcolor` of the CS:GO water material it sits under (one vpost per colour).
- `facescale` (stage C step): also faces with no single VMF mapping that still have the importer's 8192-wide scale (material
  missing at import) get scale and shift for the addon texture size, coordinates unchanged (pokemon: 154 faces the VMF route missed).
- `assets` (stage C step): materials the map didn't pack are also read from vbsp's full copies in the pakfile
  (`materials/maps/<map>/x_<x>_<y>_<z>.vmt`, `x_wvt_patch.vmt`) after CS:GO's VPK. From CS2-Porter bsp.py (MIT).

### tools/README.md rows

| `texlights.py` | `texlights` (opt-in) | lights.rad texture lights from the BSP (SURF_LIGHT faces + surface lights) -> F_SELF_ILLUM on the addon vmats, light_rect where a material can't glow; also the shared BSP reader (`Bsp`, `world_lights`, `lightmaps_lit`, `find_bsp`) | `python texlights.py <map.bsp>` (report) / `python texlights.py <addon> <root> [--bsp <map.bsp>]` (dry run) |
| `postfx.py` | `colorcorrect`, `underwaterfog` (opt-in) | CS:GO color_correction `.raw` -> .vpost lookup-table layer (or Curves + Saturation), master / box post_processing_volumes; underwater vpost per water fog colour | `python postfx.py <file.raw> [weight] [--curves]` |

and in the existing rows: `lighting.py` add "`lightcal` / `lightcal_apply` (opt-in): brightness from the compiled light list + BSP
line traces; `fifty_percent_note`"; `daylight.py` add "`fullbright` (opt-in): BSP with no baked light -> unlit world materials,
shadowless sun, probes"; `texfix.py` facescale "also the importer's 8192-wide scales"; `assets.py` "also vbsp's copies in the pakfile".

### CAPABILITIES.md line

- Lighting and look from the original map's compiled file: glowing light panels (lights.rad) glow and light the room, light brightness
  can be matched to how CS:GO lit each room, maps with no baked light stay fully bright, colour-correction filters and underwater
  tints come across (all opt-in, not yet checked in game).

### CHANGELOG.md line

- **Batch A of the CS2-Porter borrowings** (23 Nov 2026): `texlights.py` (lights.rad texture lights -> self-illum / light_rect),
  `lighting.calibrate` (`lightcal`: compiled falloff + BSP line traces; found that vrad's `_fifty_percent_distance` falloff is
  2/65.25 x (1 + d/D + 63.25 (d/D)^2), so relight's linear fit is ~8x too bright at 128 u), `daylight.fullbright`, `postfx.py`
  (color_correction -> inline lookup-table layer, compiled and decoded: exact within 1/255; underwater vpost per fog colour),
  `assets` reads vbsp's material copies, `facescale` fixes the importer's 8192-wide scales the VMF route missed. All opt-in or
  report-only except the last two; unit tested, vposts / vmat compiled, nothing in-game verified. cs2-gotchas colour-correction row corrected.

### docs/reference/external-tools.md credit

- **CS2-Porter** (bcanusar, MIT, https://github.com/bcanusar/CS2-Porter), read through the GitHub API, never cloned. Batch A adapted:
  texlights.py (texture lights: emission from the BSP's surface lights, self-illum, rect lights), lighting.py (compiled falloff,
  BSP-tree line traces, lumens matched over the surfaces round a light; fully-bright detection), postfx.py (Curves + Saturation
  approximation, underwater vpost), bsp.py `_recover_copy` (vbsp's material copies), uvfix.py (implied texture width). Each adapted
  function says so in its header.

## Log

- 23 Nov 2026: started; A1 and A2 code written, checked by hand on real BSPs (see above).
- 23 Nov 2026: A1-A3 tests (`tools/tests/test_borrowed_a1_a3.py`, 22), A4 (`test_borrowed_a4.py`, 10), A5-A6 (`test_borrowed_a5_a6.py`, 5).
  Scratch scripts and outputs in `C:\source1\cs2port\work\borrowed_test\` (survey.py, cal.py, copies_scan.py/.log, a5_real.py,
  a6_real.py/.log, w8192.py, lutcheck.py, lutreal.py, ccreal.py; root\ holds copies of mg_jahoukarail_2015 and mg_bombardment).
  Compile tests in addon `zz_borrowed_test`: `materials/borrowed_a1/`, `lighting/postprocessing/borrowed_a4/` (can be deleted).
- texlights' light_rect lumens use our relight scale (265 _light = 1000 lm), not CS2-Porter's 200.
- Open questions for skink52 (in game): does a ported F_SELF_ILLUM surface light the bake (jahoukarail white_neon)? Is light_rect's
  emitting axis +x like light_barn (texlights assumes so)? lightcal vs relight on a map with linear / fifty-percent lights
  (mg_n64_goldeneye, ttt_cg_skyscraper_2017)? colour correction on mg_lego_multigames / mg_swag_multigames / ba_jail_pripyat
  (mg_yolo_multigames' earlier hand-made CC volumes "showed nothing in CS2", reason unknown)?
- Not mine but seen: `python ci/check_repo.py` fails `control` on tools/repair.py:518 (a 0x1b character; another batch's file).
- Full `python -m unittest discover -s tools/tests`: 289 tests, 1 failure, `test_check_repo ... test_the_repo_passes`, which is the
  same repair.py:518 control character. All 37 batch A tests pass. Batch A finished; nothing copied to C:\source1\cs2port\tools
  (the integrating session does it), nothing committed.
