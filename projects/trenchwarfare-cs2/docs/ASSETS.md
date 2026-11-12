# mg_trenchwarfare: models, sources and the Workshop search (remaster step 6)

Every model the map ships, where it came from, its licence and rip risk, and what was looked at to choose it. Catalog of Workshop packs:
`tools/tw_gmod_catalog.json` (id, author, licence note, rip, rip_risk, quality, status, converted items); tool: `create/gmod_assets.py`
(project-neutral fork of monsoon's); swap table: `tools/tw_models.py` (`SWAPS`, `WEAPONS`); map patch: `tools/patch_models.py`;
machine-readable result: `out/gmod_models.json`. Written 12 Nov 2026.

**How far this was checked:** converted and looked at in a software render of the written SMDs / DMXs and vmats
(`out/step6/turntables/*.png`, fixed sun, same scale and camera for both sides of a pair). The swapped map passed `patch_guard --strict`,
`check_world` and `check_play` with results identical to the step 5 map (below). Nothing was compiled, seen in Hammer or in game.

**Licence position.** Almost every WW1 pack on the GMod Workshop is a port from Battlefield 1, Verdun / Tannenberg / Isonzo, Day of
Infamy, Men of War, World of Tanks or War Thunder: rip risk high, never shipped. The few originals (ROCK MAN, Performance_Anna,
n00buss) are far below our props in detail. One pack beat our prop and is not a game rip: the Canon de 75 (a credited Sketchfab
original), swapped in for `gun_75mm`. Its exact Creative Commons variant still has to be read off the Sketchfab page before a Workshop
upload ([WORKSHOP_COMPLIANCE.md](WORKSHOP_COMPLIANCE.md)).

## Pipeline

```
python -I ../../create/gmod_assets.py tools/tw_gmod_catalog.json search  "fokker,sopwith camel,..." [--pages 2]   Workshop text search -> <work>/search.json
python -I ../../create/gmod_assets.py tools/tw_gmod_catalog.json details [--only id,id]   descriptions (author statements about sources)
python -I ../../create/gmod_assets.py tools/tw_gmod_catalog.json fetch   --only id,id     SteamCMD anonymous -> <work>/<id>/x/
python -I ../../create/gmod_assets.py tools/tw_gmod_catalog.json list    <id> --stats
python -I ../../create/gmod_assets.py tools/tw_gmod_catalog.json convert [--only name] [--force]   -> out/addon/models/tw/ext/<name>/
python tools/tw_models.py compare [slot]       out/step6/turntables/<slot>.png: current vs candidates, 3 views each
python tools/tw_models.py weapons              out/step6/turntables/weapon_<key>.png: ours, stock CS2 weapon, scale overlay, candidates
python tools/tw_models.py view <vmdl>          one model from 4 sides
python tools/patch_models.py                   out/mg_trenchwarfare_models.vmap + guard + out/step6/deploy_files.txt
```

- Work folder (downloads, extracts, previews, per-model reports): `C:\source1\gmod_assets\trenchwarfare` (catalog `config.work`; env
  `GMOD_WORK` overrides). Outside the repo; ~1.7 GB after this step. Converted models go to the staging tree `out/addon`, never the addon.
- Discovery, as monsoon did it: Workshop browse pages with `searchtext` (41 search words: aircraft, tanks, guns, mortars, trench props,
  soldiers, rifles), titles filtered for WW1 words (339 hits), then the descriptions of 87 relevant items read through
  GetPublishedFileDetails for the author's own statements ("I did not make the models", "from Battlefield 1", "all rights reserved to
  Blackmill") before anything was downloaded. Only packs that were not plainly game rips, plus WW1 Source / Iron Europe (free mods) for
  quality reference, were downloaded (12 packs).
- Downloads are untrusted: everything that parses them runs with `-I`; nothing in them is run; lua is never extracted.

## Conventions of every converted model

40 units per metre, `+X` front / muzzle, `+Z` up, origin on the ground (z 0) unless stated; static props `static_prop_model`, anything
a script moves needs the `_dyn` twin with `model_archetype ""` (a static model on a `prop_dynamic` can be deleted by the compile).

**Player models / uniforms (user's finding, 12 Nov 2026):** the giant first-person weapons came from players being set to a model that
was not loaded (a CS2 model picked in Hammer without its game assets). Any player model or uniform the script sets must be compiled into
this addon (staged, on the deploy list, precached by a `tw_uniform_N` prop) and never point at a model the game will not load. Step 6
changes no uniform name; `tw_de_a_body.dmx` is staged and `tw_de_a.vmdl` must be recompiled with it.

## The swap table (`tools/tw_models.py SWAPS`)

| Slot (map model) | Instances | Chosen | Fallback | Archetype | Decision | Turntable |
|---|---|---|---|---|---|---|
| `ext/gun_75mm` | 1 (id 3047, tw_gen) | **`ext/gm_canon75`** (Canon de 75 mle 1897) | `ext/gun_75mm` | static, lightmapped | **swapped**: split trail, breech and cradle detail, weathered paint and wooden wheels vs our flat green gun with white wheels; same 240 u length, origin and facing (converted yaw 270, origin moved +32.5 x), no entity fix-up | `gun_75mm.png`, `gm_canon75_view.png` |
| `ext/plane_spad7` (+ `_dyn`) | 2 static + 5 dynamic | ours | ours | static + dyn twin | keep; LODs added | `plane_spad7.png` |
| `ext/plane_dr1` (+ `_dyn`) | 2 static + 5 dynamic | ours | ours | static + dyn twin | keep; LODs added (no non-rip Dr.I exists) | |
| `ext/tank_renault_ft` | 1 | ours | `wreck_tank` | static | keep (candidate a little better, licence unverified) | `tank_renault_ft.png` |
| `ext/tank_a7v` | 1 | ours | `wreck_tank` | static | keep; LODs added (every Workshop A7V is BF1) | |
| `wreck_tank` | 2 | ours | ours | static | keep (WW1 Source Mark I stands on its end, mod asset) | `wreck_tank.png` |
| `ext/howitzer_bl8` | 1 | ours | `wreck_fieldgun` | static | keep; LODs added | |
| `ext/mortar_58mm` | 5 (mortar_ct_K) | ours | ours | dynamic (step 5 twin) | keep | `mortar_58mm.png` |
| `minenwerfer` | 5 (mortar_t_K) | ours | ours | dynamic (step 5 twin) | keep | `minenwerfer.png` |
| `ammo_box_mortar`, `sandbag_wall_a`, `sandbag_wall_128`, `duckboard`, `wire_fence_a`, `crate_german`, `shelter` | many | ours | ours | static | keep: every candidate lower poly / older texture | `<slot>.png` |

User-owned instances of a swapped slot (tw_user / ungrouped): none (`out/step6/user_owned.txt`). CONTRACT: no script-set model changed
name (planes, `_dyn` twins, mortars, uniforms all keep their paths).

## Props improved without a swap

| Model | Was | Now | How |
|---|---|---|---|
| `ext/tank_a7v` | 27.3k tris, one LOD | + LOD3 7.4k at 120, LOD4 2.9k at 240 | `create/lod_decimate.py --lightmapped-from` (lightmapped: best two LODs only, tw34 chart budget) |
| `ext/howitzer_bl8` | 15.6k, one LOD | + LOD3 5.5k, LOD4 2.4k | same |
| `ext/gun_75mm` | 18.7k, one LOD | + LOD2 3.7k, LOD4 0.5k | same (now the fallback) |
| `ext/gm_canon75` | mdl2cs2's 4 LODs | LOD0 24.6k + LOD2 6.8k + LOD4 1.2k | re-run lightmap-aware on the swapped map |
| `ext/plane_dr1` | 38.8k, one LOD | static: + LOD3 8.4k, LOD4 3.1k; `_dyn` (flying, not lightmapped): all four, 29.0k / 16.1k / 8.4k / 3.1k at 20/60/120/240 | same; `_dyn.vmdl` rewritten with the full set |
| `ext/plane_spad7` | 21.7k, one LOD | static: + LOD2 5.7k, LOD4 1.3k; `_dyn`: 12.5k / 5.7k / 2.8k / 1.3k | same |
| `players/tw_de_a` body | 167 open edges in 47 loops | 154; 4 holes capped (5 triangles) | `tools/fill_holes.py`: caps small simple boundary loops reusing existing corner data (weights unchanged). The other 43 loops run along non-manifold edges left by the tw31 weld (2,285 of them): no well-defined cap; the real fix is at the source (weld the Tripo GLB before the donor weight transfer in `soldiers.py`), which needs the GLB and a rebuild of the uniform |

Not rebuilt (weakest that remain): `wreck_tank` (procedural hull reads flat at close range: no sponson guns, plain panels; 2 wrecks in no
man's land), `ext/petrol_can` (28.9k triangles for a can, 13 instances: LODs exist from 20 u), `ext/tank_renault_ft` LOD0 54.8k.
Single-LOD props (`toolkit.json single_lod`: shattered trees, stumps, tunnel set, hangar ...) are single on purpose (lightmap charts).

## Turntable review notes (12 Nov 2026, `out/step6/turntables/`)

- `plane_spad7.png`: ours plain doped linen, clean silhouette, 21.7k. Camel (3469424955): olive dope, better engine / cockpit detail,
  but source unknown and the author forbids modified re-uploads. SPAD XIII (1315182127): striking camouflage texture, 8.7k, simple
  struts, "I did not make the models". Both rejected on rip / licence.
- `tank_renault_ft.png`: ours blue-grey, crisp geometry, 54.8k; Kalamari's FT (Sketchfab originals by Ceramic soda / Jesper Landin)
  olive with dirt, markings and stowage, 29.9k: slightly better look, licence not stated; ours is verified CC BY. Kept; first option
  if the Sketchfab licence turns out CC BY.
- `gun_75mm.png`: see the swap row. Pivot and facing checked in all three views after conversion.
- `mortar_58mm.png`: ours (French 58 mm No.2, 7.6k) best; Iron Europe 58 mm the same design at 2.6k with flat tint; the 2-inch
  British mortar is two crude parts (0.9k + 2.3k).
- `minenwerfer.png`: ours (procedural lMW n.A.) carries the period details (recoil cylinders, sight, base plate); Iron Europe's is a
  different turntable-base mount, lower poly.
- `sandbag_wall_a.png`, `sandbag_wall_128.png`: WW1 Source wall 920 tris with a single brown texture; ROCK MAN nest 2.3k flat;
  n00buss bag 484. Ours (3.7k, stock hessian) kept.
- `wire_fence_a.png`: ours (19.7k: posts, barbed strands, sag) far ahead of 224-260-tri candidates (ROCK MAN's is a chain-link cross).
- `duckboard.png`, `crate_german.png`, `ammo_box_mortar.png`: candidates 300-1.1k tris, older textures: ours kept.
- `shelter.png` vs Performance_Anna's trench section (`gm_pa_okop1`): modern dug-in position, no slot (our trenches are terrain).
- `wreck_tank.png`: WW1 Source Mark I is lying on its end (needs a pitch the converter has no option for) and is a mod asset; ours kept.

## Weapons (vdata classes; builder `tools/weapons/`, nothing rebuilt)

Render: `weapon_<key>.png` (ours, the stock CS2 weapon it replaces, the side-view overlay ours blue / stock red, Workshop candidates).
First-person scale is the stock weapon's (the model hangs off the same `weapon_offset` bone), so the overlay is the scale check.

| Class | Ours | Source / licence | Length vs stock | Look | Verdict |
|---|---|---|---|---|---|
| `weapon_awp` (T rifle) | `gewehr98` 7.9k | **BF1 rip** (FBX object "BF1 All weapons.002") | 56.3 vs AWP 53.7 u | good | **replaced in step 11** (staged, not deployed): "Free Mauser Gewehr 98" by lawlordp, CC BY 4.0, 13.1k tris, 56.0 u; see [Weapon replacements](#weapon-replacements-step-11) |
| `weapon_g3sg1` (T streak) | `mondragon_m1908` 19.3k, procedural scope / wood materials | Blockbench GLB, Spanish node names, no metadata; most likely "Mondragón M1908" by DilanMendozaHer on Sketchfab (CC BY, 24.7k faces): **to verify** | 48.0 vs G3SG1 42.8 u (+12 %, real rifle is longer; no giant model) | blocky source, large wood-grain stripes | keep; only Workshop alternative is BF1 (853036866, rip). Confirm the author and add the credit |
| `weapon_scar20` (CT streak) | `lewis_mk1` 10.6k | "Lewis Mk1" by MaX3Dd, Sketchfab, **CC BY 4.0** (GLB metadata) | 51.2 vs SCAR-20 42.5 u (drum forward; grip and butt at stock positions) | good: drum, cooling shroud, bipod, wood | keep; WW1 Source Lewis (281700167) 4.0k, mod asset, worse. **Credit missing from CREDITS.txt** |
| `weapon_glock` | `luger_p08` 23.6k | FSkala, Sketchfab, **CC BY-ND 4.0**: no adaptations may be shared; ours is rigged / reassembled | 9.0 vs Glock 7.9 u | good | **replaced in step 11** (staged, not deployed): "Luger - Game ready asset" by Burdock, CC BY 4.0, 37.3k tris, 9.3 u; see [Weapon replacements](#weapon-replacements-step-11) |
| `weapon_hkp2000` | `colt_m1911` | Ole Gunnar Isager, Sketchfab, CC BY 4.0 | | | keep; credit missing from CREDITS.txt |
| `weapon_ssg08` | `lee_enfield` | CGTrader ("cgtrader_optimized_lee_enfield_mk1.FBX"), royalty-free licence assumed, author not recorded | | | record the CGTrader page / author |

**Gewehr 98 replacement plan (step 6, superseded).** Every GMod Gewehr is Verdun / BF1 (2667468843, 1124304947, 786984611, 1128980556)
or a low-poly mod asset (WW1 Source 2.9k, Iron Europe 2.1k). The plan named janovich3D's "Gewehr 98 (ww1)" first; step 11 found that
its page says the author did not model it (below), and built lawlordp's instead, downloaded through Objaverse without an account.

## Weapon replacements (step 11)

12 Nov 2026. The two models that blocked a Workshop upload are rebuilt from CC BY 4.0 sources with `tools/weapons/` (configs
`gewehr.json`, `luger.json`), at the same model and material paths, so `weapons.vdata`, the script and the vdata classes are unchanged.
Staged in `out/step11/addon/` with `out/step11/deploy_files.txt`. Provenance (Sketchfab API record, Objaverse metadata, the GLB's own
`asset.extras` author / licence / source, sha256): `out/step11/sources.json`. Renders: `out/step11/renders/`.

**Licence rule** ([docs/creation/workshop.md](../../../docs/creation/workshop.md#licence)): the addon is free and non-commercial
(PolyForm NC for code, CC BY-NC 4.0 for our art), with an extra permission for donation / VIP servers; third-party parts keep their own
licence and are credited. Accepted: CC0, CC BY, CC BY-SA (allow adapted copies in any use; BY-SA parts would stay BY-SA). CC BY-NC
would be compatible with the free release but not clearly with the donation / VIP-server permission, so only as a last resort (not
needed). Rejected: any ND (we re-scale, re-rig and regroup, which is an adaptation), "Standard" / editorial / no licence.

**Route.** Objaverse 1.0 (Hugging Face `allenai/objaverse`, CC-licensed Sketchfab uploads with per-object licence and author): all 160
metadata shards streamed and searched (names and tags: gewehr, mauser, gew 98, k98, luger, p08, parabellum, pistole, c96,
reichsrevolver; 294 hits), plus the public Sketchfab search API to read each candidate's current page (licence, description, the
author's other uploads). GLBs downloaded from Objaverse into `C:\source1\gmod_assets\trenchwarfare\weapons\objaverse\<name>\`, read
only with `python -I`. Objaverse had clean candidates for both, so the later routes (Poly Pizza, OpenGameArt, Smithsonian, Workshop
originals) and a procedural build were not needed.

| Candidate (Objaverse shard) | Author | Licence | Size | Rip check | Verdict |
|---|---|---|---|---|---|
| "Free Mauser Gewehr 98" (000-127) | lawlordp (Milantique, now Foolish Me Studios) | CC BY 4.0 | 12.0k tris, 1k PBR | no description; tags fps / free; the author's other uploads are original characters and props (Candy Cove NPCs, Galreth, Dracarybell ...), no game names | **chosen** |
| "Gewehr 98 (ww1)" (000-023) | janovich3D | CC BY 4.0 | 6.9k | page says "I did not do the modelling for this item. I've updated the UV's and Textured it": mesh author unknown | rejected (licence chain broken) |
| "Gewehr98" (000-060) | IMPULSE_SLY | CC BY 4.0 | 2.3k | original low poly | rejected: flat palette colours |
| "Mauser2" / "LE GEWEHR" / "mauser" (000-007 / 146 / 067) | ClementParisotCaso / bfif / halflife1and2 | CC BY | 5-8k | untextured Kar98 / flat colours / a C96 | rejected (quality, wrong gun) |
| "Gewehr 98" (Sketchfab only) | vburnashev | CC BY | 4.1k | student project | not in Objaverse; Sketchfab download needs an account |
| "Kar 98" (Sketchfab only) | buh-late | CC BY | 16.1k | Gew 98 per its text | not in Objaverse (2022) |
| "Luger - Game ready asset" (000-083) | Burdock | CC BY 4.0 | 37.3k tris, 1k PBR + AO | "Modelled in blender and textured with Substance Painter"; the author's only upload; no game names | **chosen**: truest P08 shape, blued steel, walnut grips |
| "luger handgun" (000-059) | DorianDabrav | CC BY 4.0 | 8.0k | school assignment (Howest DAE game asset course) | runner-up (in-the-white finish, scene parts rotated) |
| "Luger" (000-017) | emelyarules | CC BY 4.0 | 5.9k | prolific original author | runner-up |
| "Luger" (000-133) | 3DDomino | CC BY 4.0 | 75.5k | no description | heavy, not needed |
| "Red Baron's P08" (000-009) | seaneisenhardt | CC BY 4.0 | 16.8k | own modelling, but "recreate the Luger pistol shown in the game Battlefield 1 as close as possible" | rejected (copies a BF1 design) |
| "Luger p08" (000-070) | kemicalfx | CC BY 4.0 | 115.7k | the file is an untextured C96 | rejected |
| I_Live, zdani98, WolvenBolt, Freddan755, TheAlchatrazGuy, TylerEdlen, cet321boom Lugers | | CC BY | 3.7-88k | | rejected: lower detail, untextured, silencer or flat colours |
| FSkala "Luger P08" (current), leondp, virtualcurationlab P.08 scan | | CC BY-ND / BY-NC-ND | | | excluded (ND) |

Period alternative: not needed. The Luger is the German infantry pistol (`INF_PISTOL` T = `weapon_glock` in `src/modules/00_config.js`);
the P08 was the standard German sidearm from 1908, and clean CC BY P08s exist. CC BY Mauser C96s (twilightfox, maxencerouillet,
ArnaudLescure) and a Reichsrevolver M1879 (emelyarules) are in Objaverse if a second sidearm is ever wanted.

**What the build changed** (allowed adaptations under CC BY, listed in CREDITS): Gewehr: scale 0.128, the bolt (modelled open, handle
straight up) turned 90 degrees to the closed position about its own axis (new builder rule `rotx`), the orange wood re-graded to walnut
and the steel darkened (`grade`), the period Axis scope added, bolt and trigger bound to the AWP's `bolt_action` / `trigger`. Internal
magazine as before (invisible stub mag). Luger: scale 0.00177, toggle, receiver and barrel on the Glock's `slide` (the toggle
translates like a slide, as before), trigger on `trigger`, and a steel magazine block inside the grip on `magazine` (the source has no
separate magazine), as the Colt does. Both keep their vmat names (`gewehr98.vmat`, `luger_p08_body.vmat`), so a deploy overwrites the
old files.

**Scale check** (`python -I tools/weapons/compare.py built ...`, `out/step11/renders/weapon_gewehr98.png`, `weapon_luger_p08.png`:
current / new / stock, side, 3/4, shoulder and an approximate first-person camera, plus side overlays on the stock):

| Model | Length | Bounds (weapon_offset) | Current | Stock |
|---|---|---|---|---|
| gewehr98 (new) | 56.0 u | x -16.9..39.1, z -7.6..2.5 | 56.3 u, x -16.0..40.3, z -8.1..2.5 | AWP 53.7 u |
| luger_p08 (new) | 9.3 u | x -4.0..5.3, z -4.1..1.1 | 9.0 u, x -4.4..4.6, z -4.5..1.1 | Glock 7.9 u (real P08 / G17 = 1.19, so ~9.4 u) |

Both sit where the in-game-verified models sat (grip at the stock hand bone, bore on the stock bolt / slide axis), so no giant
first-person weapon: the model hangs off the stock `weapon_offset` bone and is the same size as the one it replaces.

**Test compile (12 Nov 2026, level: compiled):** in a scratch addon `tw_weapontest` (content + game `csgo_addons\tw_weapontest`,
the staged files plus a copy of the addon's shared `scope/` materials; mg_trenchwarfare untouched), `resourcecompiler -f -i` per vmdl
under the watchdog: `gewehr98.vmdl` 1 compiled, 0 failed (6 s); `luger_p08.vmdl` 1 compiled, 0 failed; `gewehr98_mag.vmdl` +
`luger_p08_mag.vmdl` 2 compiled, 0 failed. No warning or error line in the logs (`out/step11/compile_*_watch.log`). The magazine
vmdls are named only in an animation event (`AE_CL_EJECT_MAG`), so compiling the weapon does not compile them: compile all four.
The compiled colour textures (`*_color_png_*.vtex_c`) were decoded back and rendered on the bodies
(`out/step11/renders/compiled_textures*.png`). Not yet seen in Hammer or in game: after the deploy, check in game that the Gewehr's
bolt and the Luger's toggle move with the shoot / reload animations and that both sit in the hands like the old models (TESTING.md).

## Every Workshop candidate looked at

Status: converted = items made and turntabled; candidate = description read, not downloaded (rip stated or no slot). Full notes per
pack in `tools/tw_gmod_catalog.json`.

| Id | Title | Author | Status | Quality notes | Rip risk |
|---|---|---|---|---|---|
| 3576805717 | WW1 French Canon de 75mm 1897 | soap | **converted, swapped in** (`gm_canon75`) | 24.6k, best gun on the Workshop | low (Sketchfab original, CC family per Objaverse; variant to verify) |
| 3295824204 | [LVS] Renault FT Series | Kalamari | converted (`gm_ft_female`), not used | 29.9k, good | medium (Sketchfab, licence unstated) |
| 3469424955 | [LVS] WW1 Great Britain Aviation Pack | Ryuunosuke | converted (`gm_camel`), rejected | 19.3k Camel, good | high (unknown source; no-modification clause) |
| 1315182127 | [WAC] SPAD XIII | Gredwitch | converted (`gm_spad13`), rejected | 8.7k | high ("did not make the models") |
| 3596038513 | 2-inch medium mortar | soap | converted (2 parts), rejected | crude | medium |
| 457050430 | Iron Europe WW1 Weapons/Props | The Devils Own | converted (minenwerfer, 58 mm, crate, Gewehr), rejected | 1-3k, flat | medium (M&B mod assets) |
| 284023910 | World War 1 Maps + Prop Pack | Annoying Rooster | converted (sandbags, duckboard, wire, Mark I), rejected | 0.2-4k | medium (WW1 Source mod) |
| 281700167 | World War 1 Weapon Models | Annoying Rooster | converted (Gewehr, Lewis), rejected | 2.9k / 4.0k | medium (WW1 Source mod) |
| 3071058065 | Fortification Collection | ROCK MAN | converted (nest, wire, crate), rejected | very low poly | low (free to use) |
| 2911215049 | collection of trench props | Performance_Anna | converted (`gm_pa_okop1`), no slot | modern sections | low (use with a link) |
| 3741611873 | Ragdolled Sandbags by n00buss | The Big Green J | converted, rejected | 484 tris | low |
| 1768321089, 841647275, 810303880, 1304631248 | Fokker Dr.I (LFS / WAC / BF1 props) | various | candidate | | high (BF1) |
| 560223889, 824084964, 3488405138, 1859377828, 1521539590, 785583698, 800275474 | WW1 tanks (Neurotanks, A7V, Mark V, FT) | various | candidate | | high (Neurotec / BF1) |
| 340350362, 797368041, 3460390873, 3613863071, 2775182645, 3239979308 | Renault FT, WW1 vehicles | Professor Heavy, Wild Wrecker, others | candidate | | high (World of Tanks, War Thunder, Amnesia, Men of War) |
| 3387015015, 1179000266, 1293671534, 2854472403, 2593186995, 3584557713, 3603055762 | WW1 artillery (FK 96, leFH 16, BL 8-in, 60-pdr, 18-pdr) | soap, others | candidate | | high (BF1) / medium (WW1 Source, unstated) |
| 928843244, 2307768785, 2856544886, 1449744686, 2014440526 | barbed wire, sandbags | various | candidate | | high (BF1, DoD:S, CoD) / unknown |
| 724953514, 1988055799, 2869518478, 2393238893, 2091881996, 3837621655 | Verdun / Isonzo / BF1 / Squad prop packs | The Devils Own, Conte, Hugh Tamlin, others | candidate | large, detailed | high |
| 1920174934, 3133710310, 2904086559, 3700734132, 1728324376, 894750030 | fortifications, Stahlhelm, French props, radios, trench models | various | candidate | | medium / unknown |
| 885000645, 975367154, 3382283626, 3397455324, 3403793837, 3443350078 | trench maps | various | candidate (maps, not props) | | n/a |

### Soldier player models (not converted: `create/playermodels` owns that route; our uniforms are the Tripo soldiers)

| Id | Title | Author | Rip risk |
|---|---|---|---|
| 194172212 | WW1 NPCs and playermodels | Professor Heavy | high (Men of War) |
| 704464467 | WWI NPCs and playermodels | Captain Meow | medium (Iron Europe / Red Wars mods) |
| 2880130730, 2941124700, 2243022388, 3303057102, 2738103609 | Verdun soldier packs | RisuDraws, Crustys41, Jogurcik101, KrystekSK1, Ingomar | high (Verdun) |
| 3716661506, 1966634203, 3449723119 | BF1 soldier packs | Bob, Fordring, Scientist Walter | high (BF1) |
| 3629373321, 3580817580 | Western Front playermodels / ragdolls | Mr. Blue, JiffyJelly | high (kitbash of rips) |
| 707102497 | Ww1 ragdolls (necrovision) | Sandslash | high (NecroVisioN) |
| 2933988697 | The Great War SNPCs | s3an | unknown (no description) |

## Checks on the swapped map (`out/mg_trenchwarfare_models.vmap`)

- `patch_guard --strict`: PASS, 1 declared target (id 3047 `kv:model`), nothing else changed (`out/step6/guard_models.json`).
- `check_world` (`out/step6/check_world_*.log`): identical to the step 5 map except `gun_75mm` stale -> `gm_canon75` staged; still 11
  overlapping pairs (none new), the only FAIL is the pre-existing duplicate `info_map_parameters` (M2, user's, opt-in in step 5).
- `check_play` (`out/step6/check_play_*.log`): byte-identical output before / after (its failures are pre-existing step 5 findings).
- Deploy list: `out/step6/deploy_files.txt` (map + 30 files: the gun, the LOD rewrites, the tw_de_a body). Needs step 5 deployed
  first, then a model compile; nothing is compiled.
