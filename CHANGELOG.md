# Changelog

Newest first, in local time. Entries before this repo existed were rebuilt from file dates on the PC, the cleanup logs and the records
of earlier Claude sessions. Dates taken only from file timestamps say "(file date)". Per-map detail is in [ports/](ports/README.md).

## 2026-10-29: water pass, pirates water material, fix_refs format

- `gibfix.py` writes the refs file as `importfilelist { "file" … }`: modelsfromrefs rejected the bare list ("Expecting importfilelist"), so run_fixrefs imported nothing.

- New stage D `water` (`tools/watervol.py` + `postprocess_filmic_underwater.vpost`): water meshes → func_water, underwater post_processing_volume
  80 u below the surface, master volume if missing. Applied to ttt_minecraft (6 func_water) and mg_pirates (1).
- `vmatc.py` writes textures as `.vtex_c`: `pirates_water.vmat` failed to compile ("An output texture can only point to a .vtex_c file").

## 2026-10-29: ttt_minecraft doors, sky shells, minecarts

- New stage D `doorsolid` (`tools/doorsolid.py`): doors flagged Non-solid to Player stay non-solid in CS2. New `skyshell` pass; stage C rebuilds
  dropped sky brushes as toolsskybox by default (moondome shells baked black). `physpush` covers func_physbox. Applied to ttt_minecraft.

## 2026-10-29: lighting rules, vents, gibs (skyscraper, jahoukarail, pirates, minecraft)

- `lighting.py`: light_environment Static → Stationary; open-to-sky compartments (and outdoor space on maps with no sky shell) get stationary lights
  too (skink52's rule); `lightbright` handles `_fifty_percent_distance` lights (linear falloff). Applied to all four maps of the batch.
- New `ventlight` pass (`tools/ventlight.py`), stage C/D `renderamt`, `tools/gibfix.py` + `scripts/run_fixrefs.bat` (modelsfromrefs.py takes
  `<addon> <refs>` and imports material entries) for gibs and model materials missing after a build.
- ttt_minecraft: `visfit_lean`.

## 2026-10-29: mg_pirates cannons and skybox water

- New `tools/physlaunch.py` (stage C `launch` before `push`, stage D `physlaunch`): physics-only trigger_push cannons → script launch. Stage C's `push`
  no longer turns physics-only pushes into player pushes. mg_pirates: 18 cannons.
- New `tools/vmatc.py` (compiled vmat_c → vmat; KV3 v5 with LZ4/zstd) and `tools/waterblend.py` (main-map water fades into the 3D skybox water, from the
  cs2kz mapping guide). mg_pirates water blended.
- ttt_cg_skyscraper_2017: `visfit_lean` for a slow vis compile (no Low hints; 10 Lower over the walkable band).

## 2026-10-29: mg_pirates, mg_jahoukarail_2015, ttt_cg_skyscraper_2017, ttt_minecraft stage C

- Imported (stage B) and cleaned (stage C + follow-up passes); details and open items in each `ports/<addon>/README.md`. Build queue in `data/build_queue.txt`.
- New `tools/skysplit.py`: an old 3D skybox → its own `<map>_3dskybox.vmap` + `skybox_reference` (mg_pirates, ttt_cg_skyscraper_2017).
- New `tools/gameui.py` / stage D `gameui` pass: game_ui → key poll in the io script firing the original outputs (mg_pirates, 22 cannon/boat controllers).
- Stage C `dead`: func_physbox_multiplayer → func_physbox; env_spritetrail flagged. NEED lists the CS:GO file paths too, so they can be copied from the
  extracted CS:GO content into `<root>/embedded/<addon>/` instead of staging archive chunks.
- disprestore runs on the stage C output (it needs an existing world mesh as its template).
- Moondomes hide a 3D skybox: `skysplit.py` (and `--sky`) switch sky shells to `toolsskybox`; stage C builds the moondome panorama for stock CS2 skies (mg_pirates' moondome was an error material). Applied to the mg_pirates and
  ttt_cg_skyscraper_2017 skybox maps.

## 2026-10-29: mg_yolo_multigames fixes (Ninja-Chris comparison)

- Translucent cut-out materials given `TextureTranslucency` masks (banners, random button, spawn signs), wireframe material moved to `F_BLEND_MODE 1`, wallhack
  Toggle chains → Enable/Disable, env_sprite particles resized (texture width × 0.25, non-square textures padded), scouts drugged effect → HUD overlay,
  secret camera teleport disabled; stage D lightbright/visfit/probecover/lights on the hand-ported vmap; creeper parts carried by script.
  Details in `ports/mg_yolo_multigames/README.md`.
- `tools/assets.py` `alpha`: also fixes vmats that already have `F_TRANSLUCENT` / `F_ALPHA_TEST` but no `TextureTranslucency` (they draw opaque).

## 2026-10-29

- **tools/restore_ents.py** (new): restores importer-dropped entities from the VMF; ttt_cg_skyscraper_2017 btn1/btn3 put back after a BSP/VMF/vmap comparison. Gotcha row for dropped tiny brush entities.
- **physpush.py**: physics push skips props owned by a player (cs2mapTTT carry sets the owner) and adds the CSPlayerPawn import; ttt_minecraft's io script patched. cs2mapTTT covers ttt_minecraft's MAP_REQUIREMENTS (gold block tester, crouch prompt, sandbox texts); skyscraper's invisibility button is missing from the CS2 vmap.
- **Stage A for mg_jahoukarail_2015, mg_pirates, ttt_cg_skyscraper_2017, ttt_minecraft** (the top level of `mg maps`; no CS2 ports found in existing_ports.txt or on the web). Queued for `run_import.bat`; added to existing_ports.txt `[in progress] [skink]`. The ttt_ maps are plain ports; TTT gameplay comes from github.com/skink52/cs2mapTTT. `prep.py`: pakfile entries with absolute paths (ttt_minecraft's `c:/…/csgo/maps/*.nav`) are cut back to the part after `csgo/` (they made invalid PC paths), nav/graph files are no longer staged anywhere, and the decompiled embedded files travel as `C:\source1\maps\<addon>_embedded.zip` (4 files instead of 841 for this batch). Loading-screen text carries no AI note (conventions.md). Deployed: `tools/prep.py`, `cs2_port_pipeline.md`.
- **mg_n64_goldeneye**: facescale + matflags re-run with the new texfix (775 faces re-scaled, 803 re-mapped, glass04 → unlit additive); see `ports/mg_n64_goldeneye/`. `texfix.facescale` now only rewrites texture coordinates on faces that have a VMF side (it had been rewriting generated geometry such as the laser beams). `bsp2vmf_lite.py` writes a minimal dispinfo for displacement sides. Deployed to the PC (sizes checked): `tools/` texfix, soundscripts, stage_c, bsp2vmf_lite, README; `cs2_port_pipeline.md`.
- **create/lod_decimate.py** (mg_trenchwarfare tw34): shared LOD vertices and `--lightmapped-from` (two LODs for lightmapped props). The tw31 LODs had a lightmap chart per triangle (5.6M charts, vrad3 out of memory). Gotcha row and docs/creation/models.md.
- **`texfix` from Ninja Chris's `vmap_convert_merged.py` 2026-10-28j** (rewritten, not copied): `facescale` now also matches renamed materials (one VMF material with the same file name), moved copies of same-size brushes (texture lock shift correction), rounded corners (2.5 u), faces pushed off their side (6 u), displacement faces (base-face mapping, coordinates from the projected position), slivers by their corners, and for absurd scales another material on the same plane; same-plane matches outside the brush rank below moved copies; texture size from the addon's converted texture first; absurd leftovers reported with the VMF's scales; materials with no known size listed. `matflags`: `$additive` → unlit `F_BLEND_MODE 4` by default (lit additive drew black glass04 opaque black in Hammer; reruns convert earlier lit ones), `F_DONT_FLIP_BACKFACE_NORMALS` with `$nocull` on lit shaders, `$ssbump` → real normal maps. `soundscripts`: CS:GO wave before the stock CS2 file (some are stubs). Their results: unmatched faces jacs 299 → 0, goldeneye 299 → 296, tomgreens 15,630 → 11,734. Tested on synthetic vmaps (each match path, rerun idempotent). **Fixed syntax errors** in `stage_c.py` (line 835) and `soundscripts.py` (line 177) from the earlier 29 Oct commit: an apostrophe inside a single-quoted string stopped stage C from loading.
- **Features from github.com/Ninja-Chris/cs2-slop-porting, rewritten** (that repo has no licence; it had no new commits on 29 Oct): stage C `steam` (env_steam → info_particle_system + generated `particles/port_steam/*.vpcf`, heat wave as a refracting sprite; `tools/steam.py`), `soundscripts` (Source 1 soundscript names used by entities and CS:GO door noises → same-named soundevents; `tools/soundscripts.py`; `doors` now uses them), opt-in `physpush` (players push physics props by CS:GO `.phy` mass from the io script; `tools/physpush.py`, also a stage D pass that patches an existing `_io.js`). Stage B: `vmap_refs.py` finds stock CS2 materials that are error-shader stubs and lists them in `<addon>_stub_materials.txt` (stage C `assets` rebuilds them from CS:GO); `post_import_cleanup.py` runs `cs_mdl_import` under a watchdog (sidecar check, stall kill after 120 s idle / 15 min, 3 retries, `maps\<addon>_mdl_import.log`) and ends the cleanup report with WHY MISSING (where each missing asset is used, same-named files elsewhere). Tested on a synthetic addon and with a fake importer only; the generated io script passes tscheck and the mock engine. `run_c.py` defaults gained `steam,soundscripts`.
- `data/unported_mg.md`: the 18 mg_ maps in Briar's Dropbox `csgo/maps` folder with no CS2 port found (Workshop + gordon rechecked).
- **stage C `sky`**: dropped sky brushes come back as toolsskybox (not moondome) on maps with a 3D skybox; ttt_cg_skyscraper_2017's 6 slabs retextured by hand. Gotcha added.
- **ttt_minecraft, ttt_cg_skyscraper_2017**: cs2mapTTT added (ttt_convert.py; minecraft's 42 ttt_* entities converted to relays driven by ttt.js). ports/ records + cs2-gotchas row for ttt_* entities.
- **CS2's HUD can be hidden from a map**: pawn input `SetHUDVisibility` (found in the Dogfight addon's df_combat.js); cs_script-notes, hud.md, CAPABILITIES updated; cs2mapTTT uses it.
- **cs2mapTTT**: in-round kill credit fully hidden (score deltas held to round end); HUD panel over the killfeed zone as a test (docs/creation/hud.md, cs_script-notes).
- **cs_script-notes**: velocity-spring carrying (from workshop jb_watermelon_v2's medibeam), API seen there but missing from our d.ts (`OnGameEvent`, `AddAttribute`, `SetAmmoAmount`), server-side ragdoll bodies, CSSharp killfeed suppression. cs2mapTTT now carries props/bodies.
- **cs2mapTTT** (new, [skink52/cs2mapTTT](https://github.com/skink52/cs2mapTTT)): drop-in Trouble in Terrorist Town cs_script for any map (point_script + optional custom_hud_layout via `create/patch_vmap.py`). cs_script-notes: hidden-killer world kills, killfeed limits, per-phase respawn, winner fallback without info_map_parameters, silent slot handover.

## 2026-10-28

- **docs/reference/cs_script-notes.md**: vehicle flight feel (slerp mouse aim, turn law, continuous angles, no opposite-vector blends, converging guns, robust think), from Dogfight → mg_trenchwarfare tw33.
- **create/lod_decimate.py**, **create/weld_cracks.py** (from mg_trenchwarfare tw31): faithful decimated LODs with default-scale switch thresholds (FPS fix: ~17M → ~4M prop triangles across no man's land), and seam-crack repair for converted player bodies. Notes in docs/creation/models.md.
- **create/s2/fp_gloves.mjs**: first-person default gloves straight out of an agent's vmdl_c (verified on tm_phoenix against the S2V decompile). mg_trenchwarfare uses it for stock T (tm_phoenix) and CT (ctm_sas) gloves inside its generated sleeves, with the sleeve cuff eased out so nothing clips (docs/creation/models.md).
- **create/glbmesh.py**: GLB loader and dependency-free decimator (Tripo3D models from ~950k to ~9k triangles, keeping UVs) with a textured preview renderer, from space-racer-cs2's Neon Racer (mg_neon_racer, built from the space-racer-cs2 repo with `SPR_THEME=neon`).
- **mg_mario_party**: `lightbright` applied (349 lights rebuilt from the CS:GO `_light` values; 195 had brightness 0). Light entities read from the v3_1 BSP entity lump, as no VMF was available.
- **`texfix.facescale` plane match** (fix shared by another mapper using this repo, reproduced on mg_n64_goldeneye): stack007/wall triangles with a corner ~0.1 u off the plane tilted the normal ~0.001, shifting the one-corner plane distance 1.5-3 u past the 0.5 u limit, so the face kept the importer's reduced shift (e.g. 15x/10y instead of u 389 / -465, v 128). Now: Newell normal snapped to the axis when within 0.999, plane measured at the face centre, and a side matches when every corner is within 0.6 u. Their goldeneye run: 49,539 → 49,866 faces matched, unmatched 2,572 → 2,253. Re-run idempotence only checked without real CS:GO textures (337 coordinate rewrites from guessed sizes); expected clean on the PC.

## 2026-10-27

- **Crash: `item_*` in a game_player_equip weapon slot** crashes CS2 on map load (mg_n64_goldeneye, item_assaultsuit). Stage C `equip_items` (and `stage_d.py equipitems`) takes items out of the slots and gives them from the io script (`Item_<equip>` / `ItemAll_<equip>`). **Light brightness:** the importer writes `brightness = nan` for CS:GO lights dimmer than ~265 (most of them); stage C now sets those to 0 like a Hammer save, and `stage_d.py lightbright` rebuilds them from the VMF (`I = _light 4th value or 255, x (max rgb/255)^2.2, legacy = I/265`). `visfit_lean` (from an earlier session, uncommitted until now) deployed with them.
- mg_n64_goldeneye: 9 opaque-imported translucent/alpha-test materials fixed. `assets.fix_alpha` / `fix_materials` take the alpha from the CS:GO VTF when the addon png has none (fix_materials used to drop it when the png already existed). `build_maps.ps1` scans only the built vmap + prefabs it references.
- mg_n64_goldeneye build fix: `+` in a material file name never compiles ("fused delimiter"), so `+0sign_compmon4_hr` was renamed in the map; stage C now flags such names. `build_maps.ps1` only fails a map for uncompiled materials that a vmap (or model) uses; unused leftovers are listed as a note.
- **mg_n64_goldeneye**: new passes run on the cleaned map (facescale 6,352 faces, glass04 additive, 19 probe volumes for 24 static breakables/brushes); see `ports/mg_n64_goldeneye/`. New `tools/bsp2vmf_lite.py` (VMF for texfix straight from the BSP). Fix in `texfix.material_flags`: $additive is judged by the CS:GO shader (LightMappedGeneric stays lit with F_TRANSLUCENT + F_ADDITIVE_BLEND; VertexLit/Unlit go to csgo_unlitgeneric), not by the imported vmat's shader (every imported vmat is csgo_complex, so lightmapped glass had been sent to unlit).
- **Deployed to the PC** (sizes and bytes checked): `tools/` README (index), beams, hammer_resave, prep, probecover, run_c, stage_c, stage_d, texfix, vmap_preview, vmf; `run_import_then_build.bat` (the `< nul` fix had never reached the PC); `cs2_port_pipeline.md`; live `existing_ports.txt` updated from skink52's status list. Not deployed: the docstring-only changes to `vmap_refs.py` / `modelsfromrefs.py` (their folder, `game\csgo\import_scripts`, isn't linked).
- **Port status from skink52's list**: published mg_draw_course, mg_fred_all, mg_egypt_course, mg_galaxy_course, mg_faohu_course, mg_minecraft_adventure, mg_metal_course_level_2, mg_crash_bandicoot_course, mg_insomnia_course, mg_simpsons_course and de_nuketown (Workshop links in `ports/`); mg_super_tower, mg_swag_multigames and mg_bob2 built, mg_kohztec_course and mg_antique_course in progress. `data/existing_ports.txt` snapshot merged (duplicates such as the old `trains_detach [in progress]` removed; originals, briar's and ninja chris's maps added).
- **Probe coverage rule** (skink52): static func_breakable / func_brush meshes must sit entirely inside an env_combined_light_probe_volume or their lighting is wrong. New `tools/probecover.py`: stage C step `probes` reports uncovered ones, stage D pass `probecover` adds volumes.
- **Review of every skink52 repo** (hellmatch-cs2, space-racer-cs2, trenchwarfare-cs2, cs2-fighter anim-v3) against this one, plus a structure audit. New in `create/`: `vmapgen.py` (sky shells, hints, probe/lightmap volumes, nav seed, model cache, terrain, `finish()` + `EditKeeper`), `patch_vmap.py`, `make_skybox.py`, `placer.py`, `build_all_props.py`, `clean_stale.py`, `split_parts.py`, `fx_models.py`, `hud_check.py` (Panorama stand-in + CS2 HUD zones; flags Space Racer's bottom line/logo under chat at 4:3), `panorama.py`, `loading.py`, `pixfont.py`, `retro.py`, `skies.py`, `chiptune.py`, `synth.py`, `music_analysis.py`, `sndevents.py` (+ `merge_snd.py --tag`, now project-neutral and re-runnable), `build/` script assembler, `voxel.py`, `smd_view.py`, `anim/` (mocap retarget, hinge IK, joint validator, rig vmdl writer; IK now lands within 0.002 u) and `s2/` (compiled-resource readers). Mock engine: traces, call counts, timing, churn/slot-reuse/warmup/HUD checks, round flow; all 38 port scripts pass; flagged Teleport-every-tick in mg_mario_party's bullet bills. Docs: tool index in `tools/README.md` (pipeline.md now deploys as `cs2_port_pipeline.md` only), contradictions resolved, gotchas deduplicated, creation guide rewritten (regeneration warning, entity keyvalues, testing), animation input names corrected (`SetAnimationLooping/NotLooping`), project-doc templates in `docs/creation/templates/`.
- Stage C `sounds`: WAVs that aren't 16-bit PCM (8/24/32-bit, float) are re-encoded to 16-bit PCM; ADPCM is flagged. New `docs/reference/external-tools.md` (Valve, community tools, assets and their traps). Gotchas for the cs2-slop-porting features we lack (stub stock materials, soundscript names, env_steam) and the bomb-arena DMX/entity-cloning and flat-sprite model notes (commit 8446fd4).
- Docs restructure from the self-audit: `tools/README.md` is now the tool index (every file in `tools/` and `tools/weapons/` with its usage line) instead of a second copy of pipeline.md, and deploys as `C:\source1\cs2port\tools\README.md`; pipeline.md deploys only as `cs2_port_pipeline.md`. pipeline.md gained a quick start for agents, stage C step keys in run order, prep.py usage and the `addon_template` requirement. Contradictions resolved (laser damage rule, Medium hints, player_speedmod, daylight as a stage D pass, `OnModifyPlayerDamage`, embedded files, generated script inputs, pawn hiding methods, Hellmatch label truncation). cs2-gotchas deduplicated into topical sections; cs_script notes, AI workflow and external tools extended from the Hellmatch, Space Racer, mg_trenchwarfare and Puppet Brawl repos. `tools/weapons/preview.py` paths now come from arguments/env vars.

## 2026-10-26

- Noted the new `toolsskyboxocclude` tool material (CS2 update, late Oct 2026), which does what our moondome shells do. Untested; the pipeline still writes moondomes.
- **Repo becomes `cs2mapping`: porting + creation.** Docs split into `docs/porting/`, `docs/creation/`, `docs/reference/`; new `CAPABILITIES.md` (plain-language list for non-coders), creation guide, models, HUD, sound, Workshop and AI-workflow docs. New `create/` toolkit gathered from hellmatch-cs2, space-racer-cs2, trenchwarfare-cs2 and cs2-fighter (lossless DMX, vmaplib/vmesh, mesh checker, GLB→prop, procedural prop baker, stock materials, VPK/vtex reader, sound-event merge) made project-neutral, plus a generic cs_script mock engine and tsc wrapper (all port scripts pass). `tools/vmap_preview.py` renders any vmap. Gotchas and cs_script notes extended with the original addons' findings; `OnBeforePlayerDamage` noted as deprecated (use `OnModifyPlayerDamage`).
- Repo licensed MIT (`LICENSE`, README section): anyone may copy and reuse it.
- **Texture porting from github.com/Ninja-Chris/cs2-slop-porting**, reimplemented as `tools/texfix.py` and three new stage C steps (also `stage_d.py` / `run_pass.py` passes): `overlayfix` rebuilds the importer's 2x2 placeholder static overlays from the VMF (size, surface, orientation, UVs; `overlaydepth` also sets projection depth 8), `facescale` restores broken brush-face texture scale/shift and rewrites texture coordinates from the CS:GO texture size, `matflags` carries over `$additive` / `$nocull`. Tested on synthetic vmaps only; check the first real port's overlays and textures in Hammer. Gotchas recorded.
- **mg_n64_goldeneye** re-ported with the pipeline (overwrote the published manual vmap, backups in `prefabs+backups`). New generic stage C behaviour from it: equip `Use` → `TriggerForActivatedPlayer`; non-"Use Only" equips run from the io script on every spawn; `doors` pass (func_door noise1/noise2 → point_soundevents); env_beam `StrikeOnce` → Enable + Disable after the beam life; looping wavs without markers get a cue point; point_viewcontrols nothing targets are removed. Ragdoll player model → stock tm_jumpsuit.
- `post_import_cleanup.py` skips `models/player/` (player models pull in the whole t/ct_animations set: cs_mdl_import ran 20+ min on mg_n64_goldeneye's ragdoll and the result is unusable) plus anything listed in `maps/<addon>_skip_models.txt`. `vmap_refs.py` now reads keyvalues2 vmaps (a fresh import is text, so it had been falling back to the importer's refs.txt). The PC copy of post_import_cleanup.py was the August version without vmap_refs; both are now deployed.
- `run_import.bat`: a map now counts as FAILED in `stage_b_done.txt` when the import log says "Aborting" (the importer always exits 1 at its prefab_refs step, so the exit code is no use). Before, an older vmap left in the addon made a failed import look OK (mg_n64_goldeneye re-port, vpk.signatures was back).

## 2026-10-25

- Custom WW1 weapons pipeline (vdata override + cs_script loadout + FBX/GLB→DMX weapon rigging builder): `docs/creation/custom-weapons.md`, `tools/weapons/`.
- **Textured radars.** `radar.py` now paints each floor with its material instead of grey: the addon's own source textures tiled world-aligned (`tools/radartex.py`), a name-guessed colour for stock CS2 materials, glass translucent, height as brightness. Wired into stage C and `stage_d.py radar` (`radar.textures_for(c)`). Two bugs fixed on the way: the standable-floor test used only the face centroid, so a face with a prop on that spot was dropped and left a wedge-shaped hole (jb_mangaroons); `lighting.mesh_polys` stopped at 64 vertices per face. Water planes no longer set the radar extent (ba_jail_seaside's sea). Re-rendered the six jail radars (seaside first for a Workshop update).
- Loading screens added for mg_crash_bandicoot_course (2) and mg_insomnia_course (3) from skink52's screenshots.

## 2026-10-24 (evening)

- **Jailbreak maps: radars, loading screens, credits** (ba_jail_lightsout, ba_jail_seaside, ba_jail_skylight, jb_mangaroons, jb_sides_cs2, jb_water_prison_cs2). Radar rendered with `radar.py` for all six (jb_sides_cs2's RadGen radar was broken and is replaced; its old `_radar.tga/_radar_tga.vtex` files are still in the content folder). Loading-screen backgrounds from the Workshop preview images (Hammer5Tools layout, documented in pipeline.md); jb_mangaroons uses the full 1920x1080 `Mangaroons.png`, the rest are 637x358 Steam thumbnails upscaled. `COMMUNITYMAPCREDITS:` credits written for skylight (JJJohan, models IVORK), mangaroons (gReeN), sides (JJ and ab), water_prison (TomGreen, CS:GO port JJ); seaside's existing file was missing the header line and was rewritten. jb_renegade skipped (compiled for someone else). `radar.py` gained a `pct` argument (percentile trimmed off the floor extent; 0 keeps every floor - jb_sides_cs2's long west corridor was clipped at the default 0.5).

## 2026-10-24

- `prep.py` no longer copies `addoninfo.txt` / `readonly_tools_asset_info.bin` from addon_template into the game addon: they made the launcher list the three new addons as read-only example maps (delete them by hand on existing addons).
- **Three new ports from Briar's CS:GO minigames folder**: mg_insomnia_course (Charon), mg_crash_bandicoot_course, mg_antique_course (ScHoOuFi), stages A–C done the same day, builds queued. Per-map notes in `ports/`.
- **Unattended runs**: `scripts/run_import_then_build.bat` runs stage B, then polls for `C:\source1\cs2port\build_go.txt` (Claude writes it after stage C) and runs stage D. Nested batch files are called with `< nul` so their `pause` doesn't block. Claude follows up with scheduled checks.
- **Pipeline rule change (skink52, 24 Oct)**: lasers that did damage in CS:GO get a `trigger_hurt` even where the original had none. New `tools/laserhurt.py` (run after stage C; reads the CS:GO VMF for damage/targets, adds an 8-unit trigger_hurt box per laser, same start state, Enable/Disable/Toggle I/O copied).
- **Importer-sanitised material names**: the importer rewrites `materials/schooufi texture/x.vmat` to `schooufi_texture/x.vmat` (spaces → underscores) while post_import_cleanup writes the real names, so the assets pass thought 25 materials were missing and swapped them for random stock ones. New `tools/matnames.py <addon> <root>` points the vmap back at the real files; run it before the assets pass. Gotcha recorded.
- `tools/run_pass.py <addon> <root> passes` runs stage C passes (e.g. `alpha,assets`, `sky`) on an already-cleaned map and appends to the cleanup log; `tools/run_c.py` runs stage C with a stubbed CS2 VPK when `game\csgo\pak01_dir.vpk` isn't reachable (sky/sounds still work, assets/alpha skipped).
- Stock CS:GO textures for the assets pass can come from the extracted CS:GO content in `<CS2>\csgo\materials` (copy them into `<root>/embedded/<addon>/materials`) when the CS:GO VPK chunks aren't on the PC.
- Workshop sweep for the remaining Briar minigames (83 maps): 22 with no CS2 port, 30 with an existing one, all recorded as `[ext. port]` lines in existing_ports.txt. A Steam account ("gordon") is bulk-porting the same folder (24 mg ports, 19–21 Oct 2026).

### earlier the same day

- mg_metal_course_level_2: HE grenade glows (env_particle_glow, parented to he2–he13) now follow the carrier and the thrown grenade: per-colour following glow particles + script follow. New `tools/glowfix.py` for parented env_particle_glows on future ports; gotcha recorded.
- de_nuketown: 122 dropped displacements rebuilt (30 more in the old 3D skybox skipped); 8 custom materials built from the BSP pakfile. `disprestore.py`: flat fan-triangulated back (smaller vmaps, needed to stay under the 30 MB transfer limit) and skip boxes.
- mg_kohztec_course: all 61 displacements were missing after import; rebuilt from the BSP with new `tools/disprestore.py` (closed meshes, CS:GO texture projection; blendgrassgravel001a/road01_cheap get stand-ins). Import logs show the same drop ("Found a displacement missing a needed subkey.") on de_nuketown (152, restored) and mg_faohu_course (2, not yet restored).

## 2026-10-20

- `scripts/vmap_refs.py` scans the .vmap + prefabs for used materials/models (stock CS2 filtered); `post_import_cleanup.py` now runs off that list by default (`--refs` for the old importer refs.txt behaviour).

## 2026-10-19

- **Pipeline: `gravity` pass** (`tools/gravity.py`, in stage C by default and `stage_d.py ... gravity` for ports already cleaned). trigger_gravity → trigger_multiple
  firing script `Gravity_<scale>` on touch; the script adds back `(1 - scale) * 800 * dt` of vertical velocity while airborne (the Mario Party / yolo method); OnEndTouch fires `Gravity_1` so leaving the zone restores normal gravity.
  Stage D patches the section into the map's existing `<addon>_io.js`. trigger_gravity is no longer a TO CHECK line.
- **mg_galaxy_course**: its 6 trigger_gravity (0.2, 0.3, 0.5, 1) scripted with the new pass. Untested in game.
- **mg_simpsons_course**: its 2 trigger_gravity (0.5, 1) scripted with the same pass. Untested in game.

## 2026-10-18

- **Pipeline: `visfit` pass** (`tools/visfit.py`; it is now the stage C `vis` step, and stage D runs it as `visfit` or `visfit_lower`). Hints are fitted to the play
  space: Low over the walkable band (playable air up to 160 units above a floor), Lower over the rest of the playable air near geometry,
  one Lowest over everything. They sit on a 256-unit grid with no Low/Lower overlap and no Medium. Sky shells are excluded from vis unless they close playable air. The sealing test
  ignores toolsnodraw, clips, triggers and meshes already excluded from vis, which Valve's docs say vis doesn't use.
- **Vis pass on the 8 queued maps** (mg_egypt_course, mg_faohu_course, mg_galaxy_course, mg_kohztec_course, mg_minecraft_adventure, de_nuketown,
  mg_metal_course_level_2, mg_simpsons_course). Low hint volume went down by 50-70% on the courses: e.g. metal 19.4 → 5.8, faohu 20.3 → 7.8 and
  kohztec 71.8 → 39.1 billion cubic units. Nuketown stays about the same (21 → 25; its whole outdoor ground is walkable). 21 of the 174 sky shells
  are out of vis, including the 5 around nuketown's old 3D skybox. All Medium hints are gone. Backups are in `csgo_addons\prefabs+backups\pre_vis_2026-10-18`.
  Build queue reordered with mg_egypt_course last.
- **mg_egypt_course: vis stall.** The first build stalled in the final vis cluster merge: 35,254 clusters, then 2,308 s to reach 32,768, and it was
  stopped after 51 min. Its play-space hints are all Lower now.
- **mg_bob2 built** (08:14, 30.2 min, OK). Not in `stage_d_done.txt` because the run was stopped during egypt, before the summary is written;
  existing_ports.txt was already marked built.

## 2026-10-17

- **mg_mario_party rebuilt** with the vis changes below (command-line build, 29.3 min, OK). Voxelize went from 103 s / 19,173,961 nodes
  to 23 s / 3,641,409 nodes, and outside detection from 62 s to 27 s. The whole visibility stage still took 1,631 s (27 min). Most of
  that is now clustering (1,282,040 initial clusters from 291,915 regions, 117 s, then 416 s merging the cluster lists), line-of-sight
  sampling (444 s) and merging 12,963 clusters down to the 4,096 cap (560 s).
- **Repo created** (this repo): pipeline tools, PC runners, a per-map record of every port, the CS2 gotchas list, cs_script notes, and this changelog.
  The pipeline's references to a real name became the handle. `scripts/make_import_map_auto.py` replaces shipping a copy of Valve's importer.
  The history of the earlier sessions was then merged in: this changelog, the gotchas, the house rules and the port records.
- **Pipeline: `skyvis` pass** (`tools/skyvis.py`, stage C and `stage_d.py ... skyvis`). Moondome and tools/skybox shells around rooms that
  are already sealed by their own walls get "Exclude from Vis". Each shell is checked with a 16-unit voxel flood fill from outside the
  room, and shells a room needs to stay sealed are left alone. Tested on Mario Party (all 64 shells excluded) and on a copy with Platform
  Peril's hull removed (its 2 shells correctly kept).
- **mg_mario_party: vis.** The first rebuild took 103 s to voxelise (19,173,961 nodes) plus 62 s of outside detection. The 64 sky shells
  were about half of all vis surface, so they're now excluded from vis. The 32 Low vis hints were all copies of the whole-map box, and each
  now covers one room. (A first copy of this change didn't reach the PC: the rebuild after it showed the identical node count, and the file was re-sent and verified.)
- **mg_mario_party: gameplay and visual fixes** reported from in-game testing against the CS:GO v3_5 version. See
  [ports/mg_mario_party](ports/mg_mario_party/README.md): flags, A/B buttons, light probe volumes, torch fire, lava and water floors, the Platform
  Peril laser, the arrow decal, Speed SMGs speed, weapon-trigger duplicates, thwomp sounds and bullet bill cannons.
- **mg_smee_tower_cs2: two-level radar and loading text** (10:11). The radar is split at z 2560 into vertical sections: `"default"` for the
  top of the tower (T spawn, image `mg_smee_tower_cs2_radar_psd`) and `"lower"` for the ground, yard and tower stairs
  (`mg_smee_tower_cs2_lower_radar_psd`). Loading text: "Original map by Mathijs / CS:GO port by WriteX / Ported to CS2 by skink52".
  The two radar images need an assets compile: `run_build.bat "assets mg_smee_tower_cs2"`.
- **Workshop false alarm** (10:43). A session reported the mg_smee_tower_cs2 Workshop item as removed for breaking the content guidelines.
  It wasn't: every Workshop page's HTML carries hidden "removed" and "incompatible with Counter-Strike 2" template text, and the page reader
  picks it up. It was the second time this happened. The pipeline doc now says never to report that text. The same session added the
  loading-screen credit section and the stacked-map radar note to the doc. Those three additions were missing from the first import
  of `docs/pipeline.md` (now `docs/porting/pipeline.md`) and were restored later the same day.
- mg_bombardment's `.vmap` also changed this morning (file date). What changed isn't recorded.

## 2026-10-16: the cs2port pipeline

- **Pipeline built** in one session (about 10:40 to 16:47; tool file dates 10:53–18:34), starting from the manual flow in
  [docs/porting/manual-workflow.md](docs/porting/manual-workflow.md).
  - Stage A: BSPSource extracted from its jlink image, with class files patched to run on Java 21 (`setup_bspsrc.sh`). `hammer_resave.py`
    was built by diffing a BSPSource `.vmx` against a Hammer save. `prep.py` creates the addon from `addon_template`.
  - Stage B: `run_import.bat`, running `import_map_auto.py` (Valve's importer without its Enter prompt), then `post_import_cleanup.py`.
  - Stage C: `stage_c.py` on the vmap library (`dmx.py` for binary DMX encoding 9, `kv2.py`, `vmapedit.py`), with `gen_script.py`, `vpk.py`, `vtf.py` and `assets.py`.
  - 12:15, the first stage C runs (mg_color_dev and mg_ski_mountain). **Valve's importer throws away every func_illusionary** (94 on
    mg_fred_all, 2 on mg_draw_course), so stage A now turns them into never-solid func_brush, and both maps were re-imported.
  - 12:34, stage C on mg_fred_all and mg_draw_course.
  - 13:07–13:42, after the first look in game: stationary lights (weapons were black), env_laser/env_beam replacements, alpha flags and a
    radar for every map (`lighting.py`, `beams.py`, `radar.py`, `stage_d.py`). mg_ski_mountain was deleted because a CS2 port already
    existed, and the duplicate check moved to the front of the pipeline.
  - 13:42, stage D: `build_maps.ps1`, `run_build.bat`, `build_queue.txt`, and `ports.py` for `existing_ports.txt`.
  - 14:34, the first command-line builds failed on `materials/lasers/laser_*.vmat_c`, because a command-line map build doesn't compile
    materials (Hammer does that when it loads a map). `build_maps.ps1` got the assets-first step and `assets <addon>` queue lines.
    mg_color_dev then built, and was published as 3820639006.
  - 16:35, the `daylight` pass for mg_draw_course ("really dark"), and mg_fred_all's enemy-damage gate (`EnableDamage` when the Fin room's trigger fires).
- **Batch 2** (a parallel session, 14:17–18:35): stages A–C for mg_bob2, mg_egypt_course, mg_faohu_course, mg_galaxy_course,
  mg_kohztec_course and mg_minecraft_adventure.
  - The duplicate check held back three maps: kolkazadrot's CS2 ports of mg_simpsons_course (mg_simpsons_course_v2, Workshop
    3070447697) and mg_metal_course_level_2 (mg_metal_course_2_v2, 3070464801), and the CS2 Nuketown maps, which turned out to be remakes of
    the Call of Duty map rather than ports. All three went ahead on request (15:55). Kolkazadrot also ported mg_draw_course.
  - Assets now travel as `assets\<addon>.zip` (+ `.2`/`.3`/`.4.zip`, each under about 14 MB), unpacked by `run_import.bat` with `tar -k`.
  - Stage C gained the round setup (`mp_freezetime 0`, `mp_roundtime 600`, and a knife on one-team maps unless the map already gives one).
  - Custom decals with no CS:GO source are now left alone and flagged (mg_bob2's had been swapped for a sticker). Overlays rebuilt later in
    the same run now convert too (mg_metal_course_level_2's panda spray).
  - mg_simpsons_course's import was slow because a tm_balkan prop made the importer convert the whole T animation set (2,654 animations).
  - All nine were queued in `build_queue.txt`. Their build results aren't recorded yet.
- Builds (`logs/stage_d_done.txt`): mg_color_dev assets, mg_draw_course (49 min) and mg_fred_all (24.7 min) at 15:52. Both maps were
  rebuilt after the daylight and damage-gate changes, finishing at 18:13 (56.6 and 26.9 min).

## 2026-10-15

- **de_rats_1337 / mg_lego_course / mg_super_tower follow-ups** (feedback at 09:10): a rats lighter model referenced `no_material.vmat` and
  was repointed at its black material. lego's interior lighting is weak (left for a manual pass). super_tower's sky lacks detail (a 3D skybox later).
- Radar `.vtex` files added next to the PNGs, so a command-line compile picks up the radars. `compile_ports_oct15.ps1` did a forced asset
  compile, the builds, then a copy to `game\` with a size check. mg_freedm and mg_bomb_arena went to the front of its build order.
- 15:51, mg_lego_course's script explained: `Cmd_0..Cmd_14` (15 chat lines plus `sv_airaccelerate 150`) replace two point_servercommands, and
  `Score_500` replaces game_score on the five finish lasers (21 outputs). The chat lines show as "Console: …". CS2's `AddScore` adds to the
  scoreboard's score column, where CS:GO's game_score added frags.

## 2026-10-14

- **de_rats_1337, mg_lego_course, mg_super_tower** cleaned as one batch (19:14 to 23:22). These scripted fixes became stage C. Backups are in
  `csgo_addons\prefabs+backups\preclean_2026-10-14`.
  - trigger_push → trigger_multiple + `<map>_io.js` push zones that hold the push speed (capped at 3500): super_tower's 16 corridors at 3650,
    rats' fan vortex (9 pushes at 300) and a 16000 vent launcher.
  - Static overlays → `csgo_static_overlay` with masks. Eight rats decals had grey backgrounds, which were keyed out.
  - Vis hints: one Lowest over the map, Low over the play areas, one Medium in the densest spot.
  - Radars: rats from its original CS:GO radar image, lego and tower rendered from the geometry.
  - Loading-screen text in `maps\<map>.txt` (`COMMUNITYMAPCREDITS:`), crediting SkyDusH (whose credits also name Deamon), The_Prodigy and
    iSuperleggera. The credit rule "original map by &lt;author&gt; cs2 port by skink52" starts here.
  - rats: 94 prop_hallucination lamps and ladders were invisible (the entity doesn't spawn in CS2), so the 32 named ones became
    prop_dynamic and the other 62 prop_static. Its 32 switchable lights became Dynamic, since Static lights can't switch off. Sky and 5
    materials rebuilt, boathouse water → stock CS2 water. At 23:22 three sounds were pulled from CS:GO's VPK (`rats.boulder_scrape_rough`,
    `rats.inferno_loop`, `rats.steam01`).
  - lego: 21 dropped sky ceilings → moondomes, equips → `weapon0` slots, game_score / env_sun / point_viewcontrol removed, and a "Ported to CS2
    by skink52" chat line. At 22:19 its 11 env_lasers became func_brush beams `laser_beam_1..11` (laser_red, copied from mg_circle_course's
    lasers). The existing 700-damage trigger_hurts still do the killing.
  - super_tower: sky shell → moondome, 8 func_breakable_surf windows → func_breakable glass, the dropped no-fall-damage output restored, 6
    materials swapped for stock ones.
- Published soon after: de_rats_1337 (3820105155) and mg_lego_course (3820524232).

## 2026-10-09 – 13: the first mg ports (manual flow)

- **mg_smee_tower_cs2** (imported 10-09, published 3816892618), **mg_bombardment** (10-10, 3816918916), **mg_balistic_course** (10-10, 3816960127),
  **mg_enjoy_multigames** (10-10, 3817075436), **mg_awp_submarine** (10-11, 3817816213), **mg_circle_course** (10-11, 3817732135).
  3D skyboxes moved to separate skybox maps for awp_submarine, bombardment and enjoy_multigames.
- **mg_mario_party** (10-11, 3818267169): `mario_io.js` plus overlay, teleport, model and health scripts.
- **mg_n64_goldeneye** (10-12, 3818260481): kept as a reference port.
- **mg_yolo_multigames** (10-12, 3819030057) and **mg_swag_multigames** (10-13): big generated scripts (`yolo_io.js`, `swag_io.js`) replacing about 20 dead mechanisms each.
- **mg_50arenas** (10-13): ported, then not published, because a CS2 port by someone else exists (`[ext. port]` in existing_ports.txt).
- Also published in this period: **mg_kirbys_brawl** (3819068027) and **awp_multigames** (3819078634).

### 2026-10-13

- **mg_yolo_multigames** (`convert_yolo.py`, from 00:12, with "make sure lasers, sprites and beams are reformatted"):
  - Restored the dropped `!activator` outputs.
  - game_player_equip → `weapon0..N` slots, and "use" → `TriggerForActivatedPlayer`.
  - Spawn teleporters' `AddOutput "target X"` → script `SetDest_` / `Teleport_`, and `AddOutput "origin x y z"` → `MakerOrigin_`.
  - env_sprite → one particle per texture; ambient_generic → point_soundevent.
  - The two game_ui (a remote-control cube and a secret) → script.
  - player_speedmod → `Speed_<x>`, trigger_gravity → `Gravity_<x>`, player_weaponstrip → `Strip`, `sm_slay @all` → `SlayAll`, and
    `head_ammo` (ammo_50ae; CS2 has no ammo items) → `RefillPistolAmmo`.
  - env_screenoverlay → custom_hud_layout.
  - Class swaps: func_monitor → func_brush, func_physbox_multiplayer → func_physbox, light_dynamic → light_barn, color_correction → post_processing_volume.
  - Dropped toolsskybox faces → moondome + toolsskybox meshes, and militiawater → dev_water2.
- **mg_swag_multigames** (`convert_swag.py`, from about 01:00):
  - The same treatment as yolo, plus 17 env_screenoverlays and 5 env_spritetrail → info_particle_system.
  - 9 func_illusionary → non-solid func_brush, and water → dev_water2 inside a func_water.
  - The star models rebuilt from the pakfile.
  - At 01:18, func_wall_toggle → func_brush (toggled solidity, start state from "starts invisible") in both swag and yolo.
- **mg_mario_party** (`fix_games.py`, before 06:35):
  - The chain chomp's 16 phys_thrusters didn't move `Dog_box`. The script steered it at first; in the end its physics is frozen and the
    script glides the box (chase 280, wander 220).
  - Pirate climb `bolder_timer` refire 0.5 → 1.0 s.
  - Block Fort: the teleporter only checks players as they enter, and the rename landed after they were already inside, so the script
    now hands out one of 16 random spawns per team.
  - The Octodad model got tm_phoenix's 14 ragdoll joints.
- **mg_50arenas** (`convert_a50.py`, 05:51 to the evening). See [ports/mg_50arenas](ports/mg_50arenas/README.md):
  - Sky `sky56` + moondome; 13 music soundevents.
  - 33 SetModel VScripts → `Model_<name>` using CS2 agents, and the Green Power Ranger rebuilt on the CS2 skeleton.
  - 55 "EFFECT" screen overlays → colour-tint post-processing; 100 func_wall_toggle → func_brush.
  - The moondome rebuilt as 53 boxes, one per arena bubble.
  - A stale asset reference list inside the vmap was found and rebuilt.
- **Vis hint tuning** (mario, yolo, swag, 50arenas):
  - Medium arena hints on mario still gave 1,451,170 regions (662.85 s, 7,124,693 clusters).
  - Lowest-only hints (256-unit regions) made walls vanish a few steps back (50arenas, 16:28).
  - Settled on Low per arena and one Lowest over the void.
  - 50arenas (53 boxes, about 60 times a normal map's volume) went to Lower (`hintType` 8), but VIS3 still ran 30+ min there.
  - Mario's moondome also showed bits of other arenas from odd positions.
- **yolo / swag gameplay fixes** (afternoon to 20:26):
  - Removed the map check (a physics barrel that can't arrive in CS2 was deleting four game buttons), and the `phys_pushscale` /
    `cs_enable_player_physics_box` commands. The script now pushes props for knife hits, shots and players running into them.
  - Football goal triggers set to Physics Objects.
  - Grenade holes are tracked by script, since CS2 triggers don't detect grenades.
  - Shot blocks fly toward the shooter.
  - Volleyball: frozen balls get a nudge, the ball passes `fb_playerclip`, and low gravity cancels 3/4 of the measured gravity.
  - 20:26 "score doesn't work": the outputs moved onto 24 logic_relays still said `OnStartTouch`, and were renamed to `OnTrigger`.
  - swag: the intro overlay is limited to two rounds.
- **Build scripts:** `compile_maps.ps1` builds mario, yolo, swag and 50arenas one after another (lightmap 1024, phys/vis/nav, Steam Audio
  bakes) and copies each map's outroot back into `game\csgo_addons\<addon>` with a vpk size check. The copy exists because an `-outroot`
  build only writes to the outroot; Hammer copies the vpk into the game addon itself.

### 2026-10-12

- **mg_mario_party** (00:32 to 23:43):
  - Filter audit (the "missing filter target" warnings are names the script gives players, such as `predator` and `marine`).
  - A new `part1_spawn` (the five part1 teleports pointed at a destination that never existed), and the dead Mario Kart teleports removed.
  - At 11:27, a moondome using `sky_pipeplaza`.
  - **math_counter → logic_case passes a float** ("5.000000"), so whole-number cases never fired. The script now forwards the rounded value
    (`COUNTER_TO_CASE`) and re-hooks the counters every round.
  - 22:13: the motes game prints "t's win" but doesn't end the round (still open).
  - 22:52–23:31: the mushroom grab. CS2 stops players at the physbox surface, so the thin grab trigger couldn't be reached; the script grabs within 36 units.
  - The Octodad player model was rebuilt on the Phoenix agent (73 bones). The old model had no CS2 skeleton or animgraph, so held weapons were huge.
  - The between-rounds strip moved into the script (CS2 doesn't apply non-"Use Only" equips on spawn).
  - An Aztec grass/rock blend material.
  - 23:43: the first visibility hints (High around the moondome areas).
- **mg_n64_goldeneye**, round 1:
  - Soundevents, and all 41 `Use` → `TriggerForActivatedPlayer` conversions checked.
  - The `elite` equip fixed (it gave an SSG 08), `item_assaultsuit` restored, leftover `weapon_x 1` keys removed.
  - The 14 dropped env_beams restored, 20 medals restored, and overlays → `csgo_static_overlay`.
- **mg_n64_goldeneye**, round 2 (from 03:35):
  - All env_beams removed on request ("they can cause crashes").
  - 24 signs rebuilt as properly sized quads.
  - 16 func_breakable_surf windows → func_shatterglass (`glass_plate_shatter`).
- `cs2_build_goldeneye_mario.ps1`: the first command-line build script. It compiles out-of-date assets first, checks the vpk contents and copies it with a hash check.

### 2026-10-11

- **mg_circle_course:** VIS ran 18+ min (307,557 regions, 2,453,840 clusters). The big open centre gives vis little to cull. Iterate without full vis and keep the sealed volume small.
- **mg_awp_submarine** (21:28): the `launch` soundevent was silent.
  - Most of the wavs had never compiled to `.vsnd_c`.
  - Two point_soundevents had a file path (`sounds/launch.vsnd`) where the event name (`launch`) belongs.
  - The `disco1` / `disco2` wavs were missing.
- **mg_mario_party** (late): soundevents built from the map's 46 sounds. Every ambient_generic → point_soundevent, with `PlaySound` → `StartSound` (`StopSound` stays).

### 2026-10-10

- mg_smee_tower_cs2 / mg_balistic_course: `vmat_to_overlay.py` converts decal materials from `csgo_complex` to `csgo_static_overlay` in place,
  with a mask keyed from the most common border colour.
- Neon laser textures (red, green, cyan, magenta: colour, translucency and self-illum PNGs + vmats) made in mg_balistic_course's
  `materials\lasers`, and reused by later ports.

### 2026-10-09

- mg_ka_trains_detach (briar's port): a trigger_gravity replacement script (`gravity_minigames.js`: low 0.4 and high 1.4 by logic_case),
  still being debugged with `[gravity]` logging and chat test commands.

## 2026-10-01 – 07

- **ba_jail_lightsout** imported 10-01.
  - The environment prefab (about 15 MB, 1,457 entities) was too heavy to collapse in Hammer, so its contents were pasted in with Paste Special.
  - The 3D skybox didn't render until "Editor only" was unticked on its `sky_camera`.
  - The importer needed the content root to be `C:\source1`, where the VMF is, not the CS:GO content folder ("Found no files matching
    specification"). `-usebsp` needs the BSP in the legacy `csgo\maps`.
  - Glow and blood decals got alpha masks, and its static overlays were toned down with `g_fTextureColorBrightness` 0.3.
  - Its compile log: 123 light_omni2 asked for shadow slots and 102 failed; the vis boundary pass took about 1,018 s.
- **ba_jail_keimusho** import started 10-07.

## 2026-09 (jailbreak features)

- **jb_water_prison_cs2** imported 09-20: `vehicles.js` (drivable car replacing game_ui; file date 09-20) and `water_immunity.js` (09-29).
  CS2's AddOutput can't rename entities ("AddOutput fired with bad string"), so the immunity script calls `SetEntityName`. `waterfilter` needed
  `negated 1`, added as a raw keyvalue with Smart Edit off.
- **ba_jail_seaside**: `dodgeball.js` (09-19), `bumper_cars.js` / `buff_new.js` copies (09-24). func_brush beams parented to a func_rotating
  wouldn't Enable, so they stay unparented and get `SetParent` at runtime. The radar was made with RadGen (its selection set has to be named
  `radgen_path`). The BreakFloor respawn uses a counter (to 104) and a point_template.
- **ba_jail_skylight**: `bumper_cars.js` (09-25), `helicopter.js` (09-25), `keypad.js` (09-28), `buff_new.js` (10-01). The keypad script
  re-hooks its buttons every round start, because map entities are re-created each round. The buff script was rewritten to track who picks up
  the named map weapon, after it turned out CS2 doesn't keep a weapon's targetname through a pickup.
- **jb_sides_cs2** radar made with RadGen (09-30).
- A jailbreak speed knife: player_speedmod doesn't work in CS2, cs_script has no speed setter, and `GiveNamedItem` doesn't fire
  `OnPlayerPickup`, so it became a CounterStrikeSharp plugin setting `VelocityModifier`.

## 2026-08 (first CS2 ports: jailbreak maps)

- **jb_mangaroons** (08-22), **ba_jail_seaside** (08-24), **jb_yeetnam** (08-28), **jb_renegade** and **ba_jail_skylight** (08-30) imported with Valve's importer.
- Import helpers written as problems came up: `findmissingtextures.py` (08-24), `findmissingmodels.py`, `mdltovmdl.py`, `newcheck.py` (08-26),
  `makealpha.py` (08-27), `modelsfromrefs.py` and **`post_import_cleanup.py`** (08-28).
  - Valve's importer kills the whole run on its first bad asset (`utlc.RunCommand` → `Error()` → `sys.exit(1)`), so post_import_cleanup
    became the standard second step.
  - It grew from `modelsfromrefs.py` into four phases: models, texture cascade, vmat sweep, report. It skips models that already have a
    `.vmdl` but always retries their compile, decides what's out of date by comparing against the compiled `_c` files, and leaves `materials/tools/` alone.
- Import failures found on these maps:
  - "pak01.vpk / Failed to load file (invalid)": rename `vpk.signatures`.
  - A CS:GO content path with spaces: use a junction (`C:\cscontent` → `csgo`).
  - VTFCmd's `-output` flattens the folder tree, so the PNGs are written next to the VTFs instead.
- ba_jail_seaside models:
  - `cs_mdl_import -r` with `*.mdl` scanned about 12,164 stock models and crashed (253 of 255 failed).
  - An explicit `-l` file list got 152 through, then crashed on one mdl/vtx checksum mismatch, which is what `newcheck.py` finds.
  - cs_mdl_import converts geometry only; materials are a separate pass.
- Props from other Source games (undated): Crowbar → Blender → ModelDoc, with generated alpha masks.
