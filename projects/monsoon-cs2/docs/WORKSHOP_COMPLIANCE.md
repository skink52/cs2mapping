# mg_monsoon: Workshop / IP compliance

Not legal advice; a practical checklist for a Steam Workshop upload
([docs/creation/workshop.md](../../../docs/creation/workshop.md#keeping-it-safe-to-publish-ip)). Rewritten 12 Nov 2026 (release-readiness
review) from the repo's own records: [ASSETS.md](ASSETS.md), `tools/gmod_assets.json` and `out/gmod_models.json` (the conversion
records), `create/playermodels/catalog.json` and [gmod-playermodels.md](../../../docs/creation/gmod-playermodels.md#rights),
`tools/mv_models.py`, `tools/stock.py`, `tools/apache_setup.py`, `tools/sounds.py`, and the model paths in the generated
`mg_monsoon.vmap` / `mg_monsoon_3dskybox.vmap` of 12 Nov 2026 (read-only scan). Nothing was downloaded for this review, and nothing
here is in-game verified.

## Verdict

**The current build must not go on the public Steam Workshop.** Since the integration pass of 12 Nov 2026 the map **places 35
converted Garry's Mod Workshop models** (the T Mi-8s, the CT howitzers, every M2 / DShK, the vehicles, the Rising Storm foliage, the
sandbag nests, both crash hulks) and the script **caches and applies four GMod player models** as uniforms. Most of those are rips of
commercial games; none comes with a licence. The earlier version of this page ("the map places none of them") is out of date.

The fix exists in the generator but is not complete: `MV_NO_EXT=1` swaps the converted props for our procedural ones (or drops them),
and **does not touch the player models**. A clean public build needs the extra steps in "Steps for a public Workshop build".
For skink52's private or friends server the current build is what the repo's records already accept ([ASSETS.md](ASSETS.md),
"Licence position"), with the limits under "Private or friends server".

## Rip risk per asset

Ratings: **do not ship** = not on the public Steam Workshop (commercial rip, or no licence and no permission); **attribution needed** =
allowed with the credit text in CREDITS.md and the description; **ok** = ours, or Valve's CS2 content inside a CS2 addon.
"Placed" = referenced by the generated main map of 12 Nov 2026 (35 converted models, 4 player models); "files only" = in
`out/addon` and copied by the deploy unless `--skip-ext`, but not referenced. Author names are the Steam profile names recorded on
11 Nov 2026; the number is the Workshop item id (`https://steamcommunity.com/sharedfiles/filedetails/?id=<id>`).

### Do not ship (public Workshop)

| Asset (addon path) | In this build | Source (Workshop pack, author, id) | Original source of the art, as recorded | Licence / terms | Rating |
|---|---|---|---|---|---|
| Mi-8 `models/mv/ext/hip/hip_upper`, `hip_rotor`, `hip_tail`; `hip_slick` | placed: all three T helicopters (body + rotor + tail rotor) | [LFS] Vietnam Helicopter Pack #2, Gredwitch, 2165664559 | commercial game assets; the author states the models, sounds and textures are not his | none | **do not ship** |
| UH-1 `huey_upper`, `huey_rotor`, `huey_tail` | files only | same pack | same | none | **do not ship** |
| Mi-24 `hind_upper`, `hind_rotor`, `hind_tail` | files only | [LFS] Vietnam Helicopter Pack, Gredwitch, 2125035846 | commercial game assets, same statement | none | **do not ship** |
| `m101` + `m101_gun` (CT howitzers), `m2_tripod` + `m2_gun` (M2 mounts), `dshk_tripod` + `dshk_gun` (DShK mounts) | placed: the CT battery and every M2 / DShK | Gredwitch's Emplacement Pack, Gredwitch, 1391460275 | rips from several commercial games ("mixed") | none | **do not ship** |
| `m60_gun`, `mortar_m1` | files only | same pack | same | none | **do not ship** |
| `bm21`, `ural`, `zpu4` | placed: T camp vehicles, T truck | COD4 Vehicle props, Kally, 127682564 | Call of Duty 4 | none | **do not ship** |
| `rocket_grad` | files only | same pack | Call of Duty 4 | none | **do not ship** |
| `pbr`, `t54`, `m151`, `gaz69`, `comm_station`, `nva_ammo_case` | placed: PBR on the marsh, T-54, jeeps, CT TOC radio, T ammo point | Bad Company 2 models: Vietnam pack, Moon., 740797619 | Battlefield: Bad Company 2 Vietnam | none | **do not ship** |
| `nva_ammo_case_open`, `w_ak47`, `w_rpg7`, `w_m14`, `w_m79`, `w_m60` | files only | same pack | same | none | **do not ship** |
| `m114_howitzer`, `m40_rr`, `pbr_mcv`, `lssc_boat` | files only | Military Conflict: Vietnam - Boat and Emplacement Props, GenericName, 3677941897 | Military Conflict: Vietnam | none | **do not ship** |
| `m35` | placed: CT truck hulk | [simfphys] Vietnam Vehicles Pack, Zackrovich, 1671748726 | Call of Duty: Black Ops, Battlefield: Bad Company 2 Vietnam | none | **do not ship** |
| `m113` | placed: bridge, roads, firebase gate | [LVS] M113 pack, Ryuunosuke, 3366544842 | not stated; recorded as "likely RIP" | none | **do not ship** |
| 12 `rs_*` foliage (`rs_elephant_grass`, `rs_grass_set`, `rs_bamboo_bundle`, `rs_bamboo_wall`, `rs_jungle_tree`, `rs_mangrove`, `rs_jungle_palm`, `rs_coconut_palm`, `rs_nypa_palm`, `rs_taro`, `rs_ferns`, `rs_jungle_bush`) | placed: bamboo groves, slim trees, palms, mangroves, ferns and bushes along the ravines, village thickets | Rising Storm Jungle Props, Hugh Tamlin (Piggo), 1978220591 | Rising Storm / Red Orchestra 2 | none | **do not ship** |
| `rs_hedge` | files only | same pack | same | none | **do not ship** |
| `sandbag_cover` | placed: the horseshoe in front of every converted M2 / DShK | Firebrand - Fortifications, Hugh Tamlin (Piggo), 1920174934 | the Firebrand mod (a credited port, not the uploader's own work) | none stated | **do not ship** |
| `sandbag_fort` | files only | same pack | same | none stated | **do not ship** |
| `skyraider` | files only | Vietnam War USAF Planes, huan.bb, 1923196118 | not stated; recorded as "likely RIP" | none | **do not ship** |
| `heli_wreck` / `heli_wreck_dyn` | placed: both crash hulks (prop_dynamic, cached by the script) | Helicopter Wreck Model, Quarantine, 887209835 | **unknown** (not stated) | none stated | **do not ship** without the author's written permission (asking is realistic) |
| `tent_gp` | files only | Tent Army V2, Neiremberg, 933819302 | **unknown** | none stated | **do not ship** without permission (unused: our `gp_tent` is placed) |
| `wood_tower` | files only | Wooden Defense V2 / Wooden Tower, Neiremberg, 944539940 | **unknown** | none stated | **do not ship** without permission (unused: our `guard_tower` is placed) |
| Player model `models/player/gmod/nva_soldier`, `vietcong_soldier` (+ `materials/models/player/gmod/...`) | placed: cached by `mv_cache_*`, worn by T players (`CONFIG.UNIFORMS`) | Vietnam Player Models, Blue_Skies, 129903045 | **unknown** (not recorded; the source MDLs sit under `models/player/kuma/`) | none recorded | **do not ship** |
| Player model `soldier2_woodland` | placed: CT uniform | Early 2000s U.S. Military [P.M. Version], Giga Sigma Goon, 754145149 | **unknown** | none recorded | **do not ship** |
| Player model `us` | placed: CT uniform | U.S. Army Military {Playermodels & NPC's, [CZ] Colonel Clanny, 669868438 | **unknown** (source MDL `models/player/military_navy/male_08.mdl`) | none recorded | **do not ship** |

The player models' rule is the toolkit's own: converted GMod player models are "for private/local testing", and a published map needs
the author's permission and nothing ripped from a commercial game ([gmod-playermodels.md](../../../docs/creation/gmod-playermodels.md#rights)).
The commercial-source packs cannot be cleared by asking the GMod uploader: the rights are the game publishers'.

### Attribution needed

| Asset | In this build | Source | Licence | Rating |
|---|---|---|---|---|
| AH-64E Apache "Guardian" (`models/vehicles/apache`, `materials/models/vehicles/apache`) | placed: all three CT helicopters | Sketchfab, Jeyhun1985 (credit text in `tools/apache_setup.py` and `C:\source2\projects\apache\cs2_apache\CREDITS.txt`) | CC-BY-4.0 ("Author must be credited. Commercial use is allowed.") | **attribution needed**: the credit text verbatim in CREDITS.md (done) and in the Workshop description (done), and the changes stated (CREDITS.md: converted, LODs, hulls, rotor animations, scaled). Whether the Sketchfab model is itself original was not checked; the repo relies on its published licence |

### Ok

| Asset | How it is used | Source | Rating |
|---|---|---|---|
| Valve stock models, main map | referenced, not copied: Aztec banyans and foliage (`models/props/de_aztec/hr_aztec/...`, 36 models), Anubis palms and `water_wall02`, `cs_italy` ferns / taro / leaf plants, `foliage/weeds` grasses | CS2 (`pak01`) | **ok** |
| Valve stock models, 3D skybox | referenced: Aztec banyans and the Aztec skybox tree cards (`aztec_skybox_tree_card_*`), `foliage/trees/poplar` and `maple`, two `de_dust/hr_dust` models, skybox palms | CS2 | **ok** |
| Valve materials, particles, sounds | referenced: Ancient ground blends, water, tool materials, the sky material; 8 stock particle systems (explosions, dirt, fire, smoke, rain, waterfall, helicopter dust); the CS2 weapons the kits hand out and their sounds; agents and bots; the Stratum2 HUD font; `addon_template`'s post-processing and base sound events (copied by the deploy, as for every addon) | CS2 | **ok** |
| Valve textures **copied** into the addon | `materials/models/mv/stock/default_cloth001_color.png` and `_normal.png` (exported from `pak01` by `stock.export_custom` for the hessian / canvas vmats); `models/player/gmod/shared/firstperson_arms.dmx`, `firstperson_sleeves.dmx`, `tools_preview.dmx` (the CS2 agent parts the player-model route decompiles, [models.md](../../../docs/creation/models.md#rebuilding-a-csgo-player-model-as-a-cs2-agent)) | CS2 | **ok** (Valve's CS2 content inside a CS2 addon; credited as Valve). The DMX leave with the player models |
| Procedural props (117+), terrain, karst, water, 3D skybox terrain ring, HUD (100 pictures), radar, board, loading slides, icon, fx models | generated by this project's tools; slides and icon are drawn from the board map, not from screenshots | ours | **ok** (CC BY-NC 4.0) |
| 41 sounds and the `mv.*` sound events | synthesised (`tools/sounds.py`: numpy / scipy, no samples) | ours | **ok** |
| Script, generator, tools | AI-written, directed by skink52; `tools/stock.py` and other shared tools derive from skink52's own earlier MIT code | ours | **ok** (PolyForm Noncommercial 1.0.0) |

Also downloaded and looked at but **not** converted (nothing of theirs is in the addon): 1735519742, 3477505306, 942347951,
422672588, 309931181, 1432385076, 939768444. `out/gmod/` holds extracts of the converted packs for re-conversion; `out/` never ships.

## What `MV_NO_EXT=1` does, and what it does not

`MV_NO_EXT=1` (environment variable at generation time) makes `mv_models.have()` report every `models/mv/ext/...` model as absent, so
`pick()` and `static()` return the procedural variant or nothing. It is read when `make_map.py` and the script build run; the deploy
and the files on disk are unaffected.

**Swapped for our procedural props** (`tools/mv_models.py` `HELIS`, `GUNS`, `STATIC`):

| Converted (now) | Procedural (with `MV_NO_EXT=1`) |
|---|---|
| `hip_slick`, `hip_upper`, `hip_rotor`, `hip_tail` (T Mi-8 x3) | `heli_hip`, `heli_hip_gun`, `rotor_hip`, `tailrotor_hip` (seats, exits, pods and hubs switch to the `proc` numbers, exported to `layout.json` for the script) |
| `m101` + `m101_gun` | `howitzer_m102` + `howitzer_m102_gun` |
| `m2_tripod` + `m2_gun`; `dshk_tripod` + `dshk_gun` | `m3_tripod` + `m2_gun`; `dshk_mount` + `dshk_gun` |
| `heli_wreck_dyn` (both hulks, also in the script's cache list) | `wreck_hip` (T), `wreck_huey` (CT) |
| `m35`, `ural` | `truck_wreck` |
| `m113` | `m113_hulk` (the firebase-gate M113 is skipped: it is placed only when the converted model is there) |
| `pbr` (afloat) | `pbr_wreck` (on the river bed) |
| `comm_station` | `radio_prc25` |
| `nva_ammo_case` | `ammo_crate` |
| `rs_elephant_grass`, `rs_bamboo_bundle`, `rs_mangrove` | `elephant_grass_a`, `bamboo_clump`, `root_tangle` |

**Dropped, no replacement** (`static()` returns None and `W.sprop` / `W.park` skip it): `m151` and `gaz69` jeeps, `bm21`, `zpu4`,
`t54`; the whole Rising Storm foliage layer (`rs_grass_set`, `rs_bamboo_wall`, `rs_jungle_tree`, three palms, `rs_taro`, `rs_ferns`,
`rs_jungle_bush`, `rs_hedge`: the extra-density pass in `mv_places.py` keeps only converted models). `sandbag_cover` at the nests is
replaced by a one-course arc of our `sandbag_low` (`W.mount`). The stock Aztec / Anubis / Italy foliage stays.

**Still shipped, or still risky, with `MV_NO_EXT=1`:**
1. **The four GMod player models.** They are not under `models/mv/ext`, so neither `MV_NO_EXT` nor `deploy_monsoon.py --skip-ext`
   touches them: `out/cache_models.json` still lists them, `mv_entities.py` still writes them into `mv_cache_*`, `CONFIG.UNIFORMS`
   still names them, and the deploy still copies `models/player/gmod` and `materials/models/player/gmod` (44 MB of materials).
2. **The converted files themselves.** `MV_NO_EXT` changes what the map places, not what is in `out/addon`. Without `--skip-ext` the
   deploy copies all 59 converted models (about 544 MB of sources). The deploy never deletes, so an addon that already has them keeps
   them, and their compiled `_c` files in `game\csgo_addons\mg_monsoon` (what uploads) stay until removed by hand.
3. **Credits and description** still have to match what ships (below).
4. **Gameplay numbers.** Every `check_play` figure (cover, route balance, pockets, nav estimate), the Mi-8 seat offsets and the
   balance runs were measured on the converted set. A procedural build has thinner jungle, lower cover at the nests, no parked
   vehicles at the camp, a longer procedural Mi-8 (871 u against 741) and a wreck on the river bed instead of an afloat PBR: it needs
   its own `check_play.py` / `check_world.py` pass and its own in-game check.

## Recommendation

**Public Steam Workshop: release only the procedural build.** Drop or swap, in this order:
1. Every converted model (all 59; 35 are placed): generate with `MV_NO_EXT=1` and deploy with `--skip-ext`.
2. The four GMod player models: `out/cache_models.json` set to `[]` and `CONFIG.UNIFORMS_ON false` (or the `UNIFORMS` lists emptied),
   and the `models/player/gmod` / `materials/models/player/gmod` trees taken out of `out/addon` and both addon folders. Players then
   wear CS2 agents, which the description already allows for. If team uniforms matter for the public release, they need original
   models (or models whose author grants redistribution and whose art is not from a commercial game).
3. Keep the Apache, with its credit in CREDITS.md and the description.
4. Optional, before or after release: ask Quarantine (`heli_wreck`) for written permission; it is the only placed model with no
   recorded commercial source. Neiremberg's tent and tower are unused. The commercial-game packs cannot be cleared that way.

**Private or friends server: the current build is acceptable by the repo's own rule** ([ASSETS.md](ASSETS.md) "Licence position":
"acceptable for the private server"), with CREDITS.md naming every pack and player model, as it now does. Limits to keep in mind:
- CS2 players get custom maps through the Workshop (`host_workshop_map`). A Friends-only or Unlisted Workshop item is still hosted
  by Steam and still covered by the same rights; it only lowers exposure. Handing the files to friends directly avoids Steam
  hosting but is still redistribution of other people's work.
- No screenshots, trailers or gallery images of the converted models or uniforms on any public page.
- Do not charge for access to the map, and do not mix the two builds under one Workshop item.

## Steps for a public Workshop build

1. Generate with `MV_NO_EXT=1` (map, then the script build so `layout.json` `models` carries the procedural seats), with
   `out/cache_models.json` = `[]` and `UNIFORMS_ON false` in `src/00_config.js`.
2. Run `check_world.py`, `check_play.py` and `check_mesh.py` on that vmap; `node test/mock.mjs 32 300`.
3. Dry run: `python -I tools/deploy_monsoon.py --skip-ext` must print "the map references 0 of the models".
4. Remove `models\mv\ext`, `materials\models\mv\ext`, `models\player\gmod` and `materials\models\player\gmod` from **both** the content
   and the game addon folders by hand (the deploy never deletes; back up first, `docs/reference/file-safety.md`), and from
   `out/addon` so a later deploy does not bring the player models back.
5. Deploy with `--skip-ext --apply`, rebuild assets and the map.
6. Before uploading, check `game\csgo_addons\mg_monsoon` has nothing under `models\mv\ext`, `materials\models\mv\ext`,
   `models\player\gmod` or `materials\models\player\gmod`.
7. Ship CREDITS.md with the "Garry's Mod Workshop" sections removed **only** when the files are really gone; keep the Apache and
   Valve sections. The Steam description (`mg_monsoon STEAM DESCRIPTION.txt`) is already written for this build.
8. Work through TESTING_MONSOON.md on this build: the procedural Mi-8, howitzer and mounts have different seats and pivots.

## What to avoid on the Workshop page

- Other games' names, logos, characters, music or screenshots in the title, description, tags or images. No "Battlefield",
  "Rising Storm", "Military Conflict", "Call of Duty" or "Conquest mode from ..." comparisons. "Inspired by classic large-scale
  combined-arms shooters" is fine.
- Preview images and video: this addon only, and only from the procedural build (no converted model or GMod uniform in any frame).
- Description credit line: the Apache CC-BY text, "All other art, sound and code original or Counter-Strike 2 stock",
  "Not affiliated with or endorsed by Valve", and a link to the source repository.
- Keep `CREDITS.md` and both licence files in the published addon (the deploy copies them to both addon roots).

## What is in the addon (public build)

- **Name:** "mg_monsoon" / "Monsoon". A weather word; not a trademark we know of in games of this kind. No other game's name is used.
- **Setting:** a 1968 Southeast Asian river valley. Historical armies and equipment by their real designations (M102, M2, DShK,
  Mi-8, AH-64, M16, AK-47, PAVN). Designations and history belong to nobody; no unit, person or film is depicted. The AH-64 is
  out of period for 1968: a deliberate reuse of a licensed model, said in the description.
- **Rules:** Conquest with flags and tickets, roles, fire missions: genre conventions. The mechanics and numbers are our own.
- **Art:** terrain, world, procedural props, HUD, radar, board, slides, icon, 3D skybox ring generated by this project's tools.
- **Sounds:** 41 files, all synthesised. No samples, no melody from any game, film or song. Weapons use CS2's own sounds.
- **Third party:** the CC-BY Apache (credited); Valve's CS2 stock, mostly referenced, two textures copied.
- **Weapons:** stock CS2 weapons under period names. No custom weapon models ship.
- **Code:** written for this project (AI-written, directed by skink52). PolyForm Noncommercial 1.0.0; assets CC BY-NC 4.0.

## Residual risk

- **Current build (converted models and GMod uniforms in it): high.** Recognisable assets from current commercial franchises.
- **Public build as above: low.** Original generated content, one CC-BY model with its credit, CS2 stock. Remaining points: the
  Apache credit must stay; historical equipment names are descriptive use; the procedural props were modelled from general
  reference knowledge of the real objects, not from any game's meshes or textures; two Valve textures are copied, not referenced.
- Not checked: whether the Apache's Sketchfab author had the rights to what he published; the original source of the four player
  models (not recorded anywhere in the repo).
