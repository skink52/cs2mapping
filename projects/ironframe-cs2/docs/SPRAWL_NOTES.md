# mg_ironframe_sprawl: build notes and the cs2-map-mcp toolset test

Sprawl is the second IRONFRAME arena and the test of the cs2-map-mcp toolset (repo `docs/creation/guide.md` section 9) on a real map.
Layout and gameplay contract: `docs/ARENAS.md` (Sprawl). This file is the running log: what was built with which tool, every bug or gap.

## Pipeline (`sh tools/arenas/build_sprawl.sh`, output `out/sprawl/addon/`, never `out/addon` which is Dunes')

1. `tools/vmap.py` with `IF_ARENA=sprawl` (the existing generator): ground, plaza, highways, booth, cache room, probes, sky, gameplay
   markers, `arena.json`. With `IF_SPRAWL_CITY=ops` (default) `tools/arenas/sprawl.py` writes no towers, only `_gen/sprawl_plan.json`.
2. `tools/arenas/sprawl_ops.py`: the city layer as one `create/mapops.py` batch (vis group `ifr_city`, ~1 140 ops, ~16 s) plus `matkit`
   materials (`materials/ifr/sprawl/`): lit window walls (4 palettes, 2048 px = 16 floors of 128 u), storefront bands, 12 katakana / kanji
   blade signs and 10 shop signs (emissive neon), aviation and lamp heads. Towers: mesh_edit shafts with per-face materials, storefront
   band + canopy, pilasters, ledges every 512 u, setbacks, roof slab / parapet / plant / antennas; ~38 % of the tall towers are ruins
   (stepped broken top cut in staggered 3 x 3 cells, hollow upper floors with hanging slabs, bent steel, rubble). Streets: kerbed avenues
   (`street`) and junctions, lamp poles. Rain: `fxkit.weather_tiles` (7 x 7 tiles of 2000 u). Lightning: `fxkit.lightning` alpha 55 / 28 s.
3. `tools/arenas/copies.py --stack 8664`: 3 arena copies stacked in z like Dunes (0, -8664, +8664; each keeps its own sky shell), up to
   22 players each (skink52, 10 Nov 2026; the arena is 4 x 4 blocks, ~10 700 u, sized for 22). Singletons (sun, sky, fog, post) are not
   copied; `ifr_arena_1..3` info_targets; drop / point names duplicated per copy. (`--spacing` lays copies on a 2 x 2 grid instead.)

4. The hangar (`tools/arenas/import_region.py`), then `tools/patch_cache.py` (a cache prop for every model the script can SetModel to
   that the generator's cache room lacks: the objective markers, anything newer than the generator's lists; the particle pools) and
   `tools/cache_check.py --map-only`: a model or particle pool the script can use that the map does not load stops the build.

**The whole rebuild is one command** (vmap, deploy, asset compile in the Sprawl addon, check, map compile, ~10 min; under the watchdog):
`python C:\source1\cs2port\autoport\watchdog.py --label "sprawl rebuild" --expect 600 --heartbeat 60 --stall 600 --max 2400 --log logs/sprawl_rebuild_watch.log -- sh tools/arenas/rebuild_sprawl.sh`
(switches and exit codes in the script's header; exit 3 = everything staged but CS2 holds the .vpk). `tools/arenas/deploy_sprawl.sh` copies
only changed models / materials / particles (`cache_check.py --sync-only`); their `*_c` are compiled in the Sprawl addon itself
(`cache_check.py <vmap> --compile`, resourcecompiler without -f), never copied from Dunes.

Pre-build checks (repo `tools/`): `fgdcheck.py`, `mapsanity.py`, `visualcheck.py`; build with `rcompile.py`; after the build
`autoport/ingame_check.py` with CS2 Workshop Tools open.

## Toolset findings (10 Nov 2026)

| # | Tool | Finding | Fix |
|---|---|---|---|
| 1 | mapops | Primitive ops take one material for every face: no lit facade with a concrete roof. | `materials: {top, bottom, side}` on any shape (by face normal); test `test_toolset_sprawl.py`. |
| 2 | mapops / meshedit | A cut that removes the whole shape failed with "faces wind inward (negative volume)". | Clear error "the cuts removed the whole shape"; test. |
| 3 | meshedit (not a bug) | Cutting a slab with a regular 3 x 3 grid of boxes at different heights can leave two diagonal cells touching along one edge: non-manifold, rightly refused by `P.check`. The error message doesn't say why. | Sprawl staggers the cell rows; test `test_staggered_cells_stay_manifold`. |
| 4 | fxkit | `lightning` flash fixed at alpha 180: a full-screen white flash every ~12 s, unusable in a shooter. | `alpha=` parameter; test. |
| 5 | fxkit | `precipitation` writes `func_precipitation`, which CS2's own FGD marks `@exclude` (fgdcheck: excluded_class). | Result carries a warning, docstring says prefer `weather_tiles`; Sprawl uses tiles. Unverified in game either way. |
| 6 | gen_world | Street / kerb / sidewalk defaults are `materials/dev/reflectivity_*` (dev textures). | Sprawl passes real materials; defaults left (noted). |
| 7 | gen_buildings | Player scale only (128-u floors, a CSG cut per window): a 2 800-u tower would be ~700 cuts and hollow interiors nobody enters. | Not used for mech-scale towers; Sprawl builds facades from emissive window textures on mesh_edit shafts. |
| 8 | fgdcheck | Looks the addon up by the folder name above `maps/` in CS2's `content/csgo_addons`, so a map built outside the addon folder reports every addon asset missing. | Run it on the deployed map (or `--addon`); a `--content <dir>` option would help. |
| 9 | fgdcheck | Reports `env_volumetric_fog_controller` as excluded_class, but the class works in CS2 (cs2-gotchas: trench warfare fog). | False positive to keep in mind. |
| 11 | rcompile | A map build runs with `-fshallow`, so the addon's new matkit materials were not compiled: 60 "referencing missing material" warnings, the bake without them, and no hint. | New hint (compile with `rcompile.py asset <content>/materials/<dir>/*.vmat`, then rebuild); test in `test_rcompile.py`. Sprawl: materials compiled (160 files), map rebuilt. |
| 12 | autoport/ingame_check + cs2live | First run on the real game: `ping` and `status` work, but `ingame_check` (stock baseline and Sprawl) failed both times with "console closed during the load". Loading a map by hand (`map_workshop`) left the console silent for minutes while CS2 loaded (11 GB, responding); the check treats that as a crash. | Gap: the load path needs to wait / reconnect through a long load instead of failing. Not fixed yet. |
| 10 | vmap_preview (old tool) | Flat grey render; the new toolset's material / model previews were not ported (need Source 2 Viewer), so the look can only be judged after a compile. | Gap. |

## Status (10 Nov 2026, ~15:30)

- Map: 4 x 4-block arena x 3 stacked copies, 3 583 meshes (check_mesh 0 bad), mapsanity clean, visualcheck 18 warnings left
  (6 containers per copy touching a highway ramp or kerb: cosmetic). Deployed with `tools/arenas/deploy_sprawl.sh` (map + shared assets;
  no Sprawl script yet: the main session is changing src/ for the playtest fixes; build it with `node ../../create/build/build.mjs
  out/sprawl/build.json` once they land, then `SPRAWL_SCRIPT=1 sh tools/arenas/deploy_sprawl.sh`).
- Compile: `rcompile.py asset .../materials/ifr/sprawl/*.vmat .../materials/ifr/sky/*sprawl*.vmat` (160 compiled), then
  `rcompile.py map ... --preset full --novis --threads 11` (no vis like Dunes / keimusho): 6 min, 0 failed, 25.8 MB vpk (15:33).
  The shared frame / weapon / fx models and their materials are copied compiled from the Dunes game addon (`cp -rn`); the next full
  IRONFRAME build should compile them into both addons.
- Without the script players stay in the booth (z -12000): for a look, `noclip` and `setpos 0 0 600` (copy 2: z -8064, copy 3: z 9264).
- To check in game: window walls / signs glow, storefront bands, ruins read as ruins, rain tile cost (`r_drawparticles 0` to compare),
  lightning flash strength, the three copies each lit (sun through each copy's own toolsskybox shell).
- 15:52: objective dressing (tools/arenas/objectives.py --arena sprawl, before copies.py: zone rings / letter masts / dais at A, B, C,
  flag stands ifr_flag_t (-3600, 0) / ifr_flag_ct (3600, 0)); rebuilt: 69 compiled, 0 failed, no missing materials, 26.2 MB vpk.
  Next: in-game check in Workshop Tools (`python ../../autoport/ingame_check.py mg_ironframe_sprawl`), after a stock baseline.
- 16:45: garage hangar: skink52's 12-bay hangar copied from Dunes' saved map (`tools/arenas/import_region.py`, vis group `ifr_hangar`,
  825 nodes incl. `ifr_bay_1..12`; a re-run refreshes it; part of build_sprawl.sh). No missing assets. Sprawl script built from
  `out/sprawl/build.json` (Sprawl's arena.json): tscheck OK, mock 22 players / 120 s with HUD "OK: no errors"; deployed and compiled
  (`ironframe.vjs_c`, HUD layout). Map rebuilt with the hangar.
- 17:05: loaded in CS2 Workshop Tools (map_workshop): skink52 checked it in game: "looks ok". The automated in-game check could not run (finding 12).

## Detail pass (11 Nov 2026, STATUS item M2)

skink52: "it's an OK map but it lacks any real detail beyond the colours of lights in the buildings. far more small scale props etc
can be applied to it. You should find some ref images ... to improve areas such as the central square".

**References.** 20 images in `C:\source1\ironframe_work\refs\sprawl\` with `sources.txt` (18 Wikimedia Commons, 2 Steam store
screenshots; never in git). What they show and the map did not have, per area:

| Area | In the references (file) | The map before | Added (tools/arenas/sprawl_detail.py) |
|---|---|---|---|
| Central square | A flooded square stays furnished: cafe tables with their legs in the water, duckboard walkways on trestles, paving bands showing through a film of water (`square_venice_san_marco_acqua_alta_01/02`). A monument is a tall object on a narrow base with lights in its soffit and a tram passing beside it (`square_berlin_alexanderplatz_weltzeituhr_01`). Station plazas have waist-high bollards every 1.5-2 m, planters, map boards, stacked vertical signs (`square_tokyo_shimbashi_sl_plaza_01`). LED walls wash dark wet stone in broad colour (`neon_times_square_rainy_night_01`) | A water sheet, a bare dais, eight bare pillars, four coloured lamps | Three rim steps into the water with a pale nosing and inlay bands; lit bollards on the top step; four duckboard walkways from the landings to the dais; cafe tables in the shallows; two steps round the dais and a lit edge; a broadcast arch over the dais (four legs, a ring at z 1195, four double-sided LED screens at z 860-1120, a ticker round the ring, a mast to z 2250; sized round the objective's letter mast with an aviation light); festoon cables from the ring to the eight pillars, which became advert pylons; promenades with lamps, benches, planters and trees, kiosks, vending machines, phone booths, market corners; a tram track with catenary, a tram and its stop on the east side, bus shelters on the other three; LED walls with tickers on the towers facing the square; cars and a bus caught in the flood |
| Avenues | Signage in layers: rooftop billboards on frames, full-height blade signs, a fascia band over every shop; guard rail between pavement and road, zebra bars, signal masts on the corners (`neon_shinjuku_yasukuni_dori_night_01`); sodium lamps about three storeys tall every ~30 m, yellow box junctions, a median (`neon_hongkong_nathan_road_typhoon_rain_01`); advert pylons, planters, shutters, a wrecked compact car at mech scale (`mech_titanfall_2_street_01`); vending machines light only their own patch (`clutter_japan_vending_machines_night_01`) | Bare asphalt between kerbs, a lamp pole per crossing, mech-scale containers, bare concrete block slabs 200 u high along every pavement | Lane paint (centre lines, dashes, edge lines, stop lines, zebras, arrows, hatched boxes, bus bays, manholes), puddles, parked and abandoned cars / vans / taxis / buses, road blocks with cones; guard rails, sodium lamps every 400 u with banners, utility poles with wires along and across the street, signal masts and bollards at every corner; vending clusters, benches, kiosks, planters, mail boxes, phone booths, cabinets, A-boards, news boxes, hydrants, bins, dumpsters, bags, pallets, bus stops; the block slabs are now street walls (shops with fascia signs, two storeys over them) with pilasters, awnings, blade lightboxes, AC units, down pipes, a cornice and a roof rail |
| Elevated roads | On deck: dashed lanes and a solid edge line, 1-m barriers, truss gantries with green signs and an amber LED panel, lamp masts every 30-40 m (`expressway_shanghai_yanan_01/02`), chevrons at the gore (`expressway_osaka_hanshin_gate_tower_01`). Underneath: banded pier collars, ID plates, drain pipes down the piers, cool flood lamps under the deck against warm street light, parked cars between the piers (`expressway_tokyo_nihonbashi_02`, `expressway_tokyo_hakozaki_jct_01`) | Plain slabs with barriers | Lane paint, junction stop lines / arrows / a hatched box, expansion joints, amber reflector studs on the parapets, lamp masts, two sign gantries per road, stranded traffic, cones and warning boards at the ramp heads; pier collars, chevron boards, number plates, drain pipes, soffit lamps, a median island round each pier, a car park under the east-west deck |
| Facades and roofs | An AC unit under nearly every window, drain stacks, cables (`clutter_hongkong_facade_ac_units_01`, `clutter_hongkong_back_alley_01`); exhaust ducts, lightbox signs, awnings (`clutter_tokyo_shinjuku_alley_01`); helipads, condenser clusters, a billboard on a frame, a tower crane (`expressway_osaka_hanshin_gate_tower_01`); red warning lights and lattice masts (`mech_armored_core_6_city_01`) | Window texture, a plant box, an antenna on the tallest | AC units under the windows of the lower storeys, down pipes, fire escapes, tall lightbox banners; roof tanks, condenser rows, vents, aerials, helipad paint, billboards on steel frames with floodlights, two tower cranes at ruins; plant, skylights and tanks on the block slabs |

Not found on the web: Chongqing, an Osaka under-deck street shot, a dedicated rooftop tank shot (the Osaka aerial stands in).

**Scale.** The facade tile was 128 u per storey (CS2 player scale: a mech was 2.5 storeys). Now `sprawl_ops.FACADE_UV = 1.2`: a
storey is 76.8 u, and human things are 0.6 of CS2's size (`sprawl_detail.S`: a car 140 x 42 u), so a 240-336 u mech is 3-4 storeys.

**How.** `tools/arenas/sprawl_detail.py` (vis group `ifr_detail`, run by build_sprawl.sh after sprawl_ops.py and before
objectives.py / copies.py) + `sprawl_detail_mats.py` (87 matkit materials `materials/ifr/sprawl/d_*`) + `sprawl_kit.json` (bounds and
LOD0 triangles of the stock models, measured from pak01). Stock props go through `create/placer.py` footprints (towers, containers,
piers, ramps and flag stands registered first), so nothing interpenetrates. Meshes are merged per kind and 1024-u cell.
- **No collision added in the play space**: every stock prop is `prop_static` with `solid 0`; every detail mesh uses a `d_*` material
  with `Attributes { "mapbuilder.nonsolid" "1" }`. Solid additions: the rim steps (within 16 u of the old slope), the dais steps and
  the arch (legs in the water at (+-700, +-700), everything else above z 860). SOLIDS / STRUCT and arena.json's nav grid are unchanged.
- The block slabs' sides and the towers' street bands use `d_shop_0..3` (a 256-u tile: shops, fascia signs, two storeys): set in
  `sprawl.py street_wall()` and `sprawl_ops.tower_ops` (with a v shift so the pavement row sits at each tower's base).
- Light: baked-only `light_omni2` (sodium at the lamps, cool white under the decks and at vending machines, the screens' colours in
  front of them); no stationary or dynamic light was added.
- Counts and cost: `out/handover_sprawl_detail.md` and `out/sprawl/addon/_gen/sprawl_detail_stats.json` (written by every build).

**Preview without CS2** (`tools/arenas/sprawl_preview.py` has the three commands): the map's faces with their stored texcoords and
our PNG textures, the stock props' LOD 0 from pak01, Cycles on the GPU, ~30 s a picture. It judges composition, scale and density;
it is not the engine (emissive surfaces light the scene there, stock materials are flat colours, no fog or rain).
Before / after: `preview/arenas/sprawl_detail_*.png`.

**Toolset findings.**

| # | Tool | Finding | Fix / state |
|---|---|---|---|
| 13 | mapops | The `entity` / `kit` / `scatter` ops cannot scale a prop (`scales` stays 1) and write one CMapMesh per shape. | The detail pass calls primitives / meshedit directly, sets `scales` on the node and merges shapes per cell (`Out.flush`). Worth porting into mapops. |
| 14 | prop_static | CS2's FGD has no fade distance keys (`fademindist` ...): only `lodlevel`. | Distance cost = the models' own LODs; many-of-a-kind props use the `_low` variants. |
| 15 | matkit | No way to mark a material non-solid. | `sprawl_detail_mats._write` inserts `Attributes { "mapbuilder.nonsolid" "1" }` (the block matkit's water uses). Unverified in game. |
| 16 | sprawl_ops | The storefront band's texture was not anchored to the tower base (world-aligned v): towers on a 200-u slab showed the tile's middle at the pavement. | `uv.shift = [0, z0 * 4]`. |
| 17 | visualcheck | Useful again: found fire-escape landings coplanar with the floor ledges, overlapping puddles, paint under paint. | Fixed in the generator. |
