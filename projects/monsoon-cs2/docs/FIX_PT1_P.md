# Playtest 1, batch P (prop quality): findings 16-18

Progress file, updated after every item so a usage reset loses little. Tracker: [PLAYTEST_1.md](PLAYTEST_1.md).
Measurements: `tools/tex_budget.py` (area-weighted median texel density per prop and material, texture memory), results in
`out/review/props_pt1/tex_budget_{before,after}.json`; turntables before / after in `out/review/props_pt1/{before,after}/`, side by side
in `out/review/props_pt1/sheets/`. Units: 40 u = 1 m, so 512 px/m = 12.8 px/u.

| # | Item | Status | Notes |
|---|---|---|---|
| P0 | Measure before | done | 103 props of p_heli, p_arty, p_guns, p_base, p_village, p_wreck, p_bridge, p_temple: median 80 px/m (huts 30-39, temple tower 18, gate 28, school 26) |
| P1 | Cause 1: `geo.surface` spaced UVs by grid index | done | an rbox face (seg=1) got 1/3 of each chart axis (1/9 of its texels), its 0.3 u edge bands the rest, baked as smeared streaks. Arc-length UVs in `create/geo.py`. Same 2048 atlas, hooch_a: median 34 -> 103 px/m |
| P2 | Cause 2: fixed atlas size per prop | done | `create/build_prop.atlas_size`: opaque atlases sized from chart area for toolkit.json `texel_density` (12.8 px/u, 256..2048, slack 1.65: the smallest power of two reaching 1/1.65 of the target). `tools/atlas_fit.py` shrank 18 atlases of the first rebuild (rounded up) without re-baking; `ao_scale` 0.5 (AO is low-frequency) |
| P3 | Cause 3: one atlas cannot cover 100-1000 m2 at 512 px/m | done | tiling materials through `create/stock.py`: CS2's own (`v_*`: de_ancient thatch, thatch edge, reed panels, wall stone moss/grey, plaster; hr_bamboo_01; de_anubis hay pile; de_dust basket), exported CS2 copies (de_train boards box-mapped, cloth -> hessian / olive-drab canvas, hr_conc_d darkened), project tiles `tools/mv_tiles.py` (bamboo culm 1280 px/m; jointless Khmer sandstone lichen/moss/dark and laterite, 640 px/m). `stock.GENERATORS` hook, `cyl` mode per connected piece, hemi-octahedral decode of CS2 normals (export and preview) |
| P3b | Routing | done | p_village `VSTOCK`, p_base `BSTOCK` (8 large base props; earth stays baked: de_ancient mud read grey), p_bridge `PSTOCK`, p_temple `route()` + `TSTOCK` (coursed masonry -> jointed CS2 wall stone; single blocks mono>=0.5 -> jointless sandstone tiles; carved panels, lion, naga and coursed laterite stay baked) |
| P4 | Thatch as thatch | done | `p_village.thatch_roof`: 4 stepped courses per slope, CS2 thatch-edge alpha fringes under each course, double eave, verges, round ridge bundle; footprint within ~3 u of the old roof |
| 17 | Hay | done | `haystack` -> Vietnamese rice-straw stack (thatch courses + fringes, top-knot, de_anubis hay strands at the foot; old footprint +3 u); `rice_basket` (the "cute" woven pots) -> de_dust basket weave in 6 segments, rolled rim, heaped paddy (cell shader); ox cart load on straw |
| 18 | Temple statues | done | Valve has no Khmer lion/naga; Workshop searched (ASSETS.md): nothing Khmer. Procedural last resort, much better: `tools/sculpt.py` (SDF smooth unions, surface nets, Taubin, planar unwrap, crumb removal); `p_temple.singha_sdf` (seated singha, bulging eyes, grin with teeth and fangs, snail-curl mane, beaded collar; left ear and tail tip broken, jaw chip, broken toes, chest crack, erosion) and `naga_sdf` (scaled rail, seven-headed hood with flame aureole, one head broken off). Same model paths and hulls; LODs by lod_decimate (76.9k / 12.4k / 3.3k / 1.2k tris) |
| P5 | Rebuild | done | 103 props rebuilt into out/addon under the watchdog (4 runs: main 64 min, then 11 + 13 + 4 + 3 props after stock-key and look fixes); lod_decimate on the 12 step-1c props + sculpts; W's p_jungle / p_sandbag_mv not rebuilt (W owns them; they get the shared fixes on their next build) |
| V | Verify | done | `tools/prop_lint.py` (check_mesh.py reads vmaps only): 103 props, 0 bad (zero-area faces now dropped by build_prop; lod_decimate clamps atlas UVs). Every before/after sheet looked at |
| M | Texture memory | done | props the map places (74 of the 103): atlases 338 -> 504 MiB, plus 49 MiB of shared tile/stock textures (was 2); all 103: 519 -> 730 MiB. Valve materials referenced in place are not counted (game files). Median density of placed props 79 -> 495 px/m |
| D | Deploy | done | 769 files (734 replaced, 35 new, 715 MB) out/addon -> content addon, backups + sha256 (0 mismatches): `out/deploy/pt1_P_20261113_021323.json`. cs2.exe not running. No vmap deployed or compiled |
| C | Compile | done (compiled) | 204 jobs (101 material folders, 103 model folders), 592 compiled, 0 failed, no error or warning lines, 16 min; per folder, `resourcecompiler -r -i <folder>/*.vmat|*.vmdl -nop4` from C:\source1\cs2port, waiting for any other resourcecompiler before each call; log `out/review/props_pt1/compile_rc.log` |

## Numbers (tex_budget, median px/m before -> after)

hooch_a 34 -> 715, hooch_c 30 -> 724, camp_hut 39 -> 706, haystack 67 -> 817, rice_basket 85 -> 742, school 26 -> 165 (plaster 320,
tin roof baked), khmer_tower 18 -> 303 (tiles 273-640), khmer_gate 28 -> 282, stone_stairs 40 -> 305, guardian_statue 118 -> 556,
naga_balustrade 143 -> 433, bunker_large 66 -> 786, guard_tower 97 -> 963, gp_tent 31 -> 857, ammo_crate 138 -> 618,
bridge_pier 48 -> 514. Still under 300 px/m (large single-atlas props, mostly vehicles and wrecks seen from range, several not placed):
c123 pieces, heli_hip(_gun), wrecks, m113_hulk, truck_wreck, pbr_wreck, psp_pad, conex, water_trailer, sampans, quad50_mount, school.

## Map changes needed

None: every model path, hull and origin is unchanged. Bounds moved by a few units (roofs +2..6 u, haystack +3 u radius / +4 u
height, statue smaller); a map regenerate reads them from props.json.

## Left / next

- A second pass for the vehicle and wreck props (CS2 painted-metal and rust tiles for their hull plates).
- W's props (p_jungle foliage cards, supply crate, flag poles; p_sandbag_mv) get the UV and density fixes on their next rebuild.
