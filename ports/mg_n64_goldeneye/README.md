# mg_n64_goldeneye

| | |
|---|---|
| Status | Re-ported with the cs2port pipeline 26 Oct 2026, queued for build |
| Original | mg_n64_goldeneye_hdr by [TsM]RoB (HDR recompile by GFLClan) |
| Workshop | [mg_n64_goldeneye_cs2](https://steamcommunity.com/sharedfiles/filedetails/?id=3818260481) (published from the 12 Oct manual port) |
| Imported | 2026-10-26 (first import 2026-10-12) |
| Map last changed | 2026-10-26 |
| How | cs2port pipeline (stages A–D); the published manual port's vmap was overwritten |

## History

- 2026-10-27 (later still): 9 materials that were `$translucent`/`$alphatest` in CS:GO had come through opaque (library008/012, glass01, offwndwb, redhandrailclassic, metalfence007a, metalrail003a, prodventb, nuke_metalvent): rebuilt with a translucency mask taken from the CS:GO texture alpha (`alpha` pass), offwndwb also two-sided (`matflags`). The alpha pass had skipped them because their vmats were only on the PC; it now takes the alpha straight from the CS:GO VTF when the png has none. The tsm_textures pngs were deleted by accident and restored on the PC. build_maps.ps1 now reads only the map being built and the prefabs it references, so the old import prefabs no longer count the `+0sign` leftover as used.
- 2026-10-27 (later): first build stopped on two materials. `+0sign_compmon4_hr` (a CS:GO animated-texture frame name) can never compile because resourcecompiler treats `+` as a fused delimiter: copied to `sign_compmon4_hr.vmat/.png` and the 2 meshes + `map_asset_references` repointed. `sky_cs15_daylight03_hdrrt.vmat` is a 12 Oct leftover with no texture that nothing uses; `build_maps.ps1` now only fails a map for uncompiled materials a vmap or model uses. Backup: `prefabs+backups\mg_n64_goldeneye_before_plusfix_2026-10-27.vmap`.
- 2026-10-27: new cleanup passes on the cleaned map (`stage_d.py … facescale,matflags,probecover`), VMF rebuilt from the BSP with `tools/bsp2vmf_lite.py`
  (the decompiled VMF folder wasn't linked). Backup: `maps\mg_n64_goldeneye_before_texfix_2026-10-27.vmap.bak`.
  - Face texture mapping: 6,352 faces given back their CS:GO scale/shift, 6,267 with texture coordinates rewritten; ~6,500 texture coordinates moved by a
    visible amount (the importer had reduced shifts mod 16 texels and mangled scales). 1,340 faces where overlapping brushes disagree and 1,066 with no
    matching side were left as imported.
  - `glass04` ($additive LightMappedGeneric): F_TRANSLUCENT + F_ADDITIVE_BLEND (was opaque black).
  - 19 light probe volumes added around 24 static func_breakable / func_brush meshes no existing volume fully covered.
  - Overlays: all 70 are real-sized (no importer placeholders), so `overlayfix` had nothing to do; their projection depth (64/128) was left alone.
- 2026-10-26: full re-port from `mg_n64_goldeneye_hdr.bsp`, overwriting the published vmap. Backups: `prefabs+backups\mg_n64_goldeneye_published_2026-10-26.vmap` (+ `_published_2026-10-26\` prefabs and soundevents) and `mg_n64_goldeneye_imported_2026-10-26.vmap`. Map-specific fixes done along the way, and added to the pipeline so later ports get them:
  - 45 `Use` inputs on game_player_equips → `TriggerForActivatedPlayer` (weapon arenas' teleports, HE wall buttons).
  - The unnamed "Strip First" knife equip ran on every spawn in CS:GO: the io script now strips each spawning player and gives a knife (one tick after `OnPlayerReset`), so arena guns no longer stack on the default pistol.
  - Door sounds: the importer drops `noise1`/`noise2`; 40 point_soundevents (default_locked, door_metal_large open/close, rock2, rock_impact_hard1) started from the doors' outputs; 28 unnamed doors got `port_door_N` names.
  - Lobby lightning (14 env_beam, `StrikeOnce` 20 s after a door is picked): func_brush beams, `StrikeOnce` → Enable, Disable after the beam's 2 s life. The existing `beam2` trigger_hurt (100 dmg) still does the damage. (The 12 Oct port removed the beams because env_beam crashed; func_brushes don't.)
  - `force_field_loop1.wav` (teleport hum, looping) given a cue point so CS2 loops it.
  - The custom inmate ragdoll (`models/player/rgmodels/rginmate`) → stock `characters/models/tm_jumpsuit/tm_jumpsuit_varianta.vmdl`; player models are skipped by post_import_cleanup now (cs_mdl_import hung 20+ min on its animations).
  - 2 dropped displacements rebuilt (`disprestore.py`, goldeneye/egyptian/sand); 31 dropped sky brushes → moondomes; sky_cs15_daylight04_hdr rebuilt from the CS:GO faces.
  - Both point_viewcontrols removed (nothing targets them; the old port's open item).
  - Loading text: "Original map by [TsM]RoB / HDR recompile by GFLClan / Ported to CS2 by skink52".
- 2026-10-12, round 1 (manual): soundevents built the same way as Mario Party's. The I/O was diffed against the BSP, and all 41 `Use` → `TriggerForActivatedPlayer` conversions checked. The `elite` equip gave an SSG 08 and now gives Dual Berettas; `item_assaultsuit` restored; leftover CS:GO `weapon_x 1` keys removed. The 14 dropped env_beams restored, 20 medals restored from the BSP's textures, overlays → `csgo_static_overlay` with masks.
- 2026-10-12, round 2 (manual): all env_beams and their outputs removed ("they can cause crashes"). The 24 signs left on a grey placeholder were rebuilt as properly sized quads. 16 func_breakable_surf windows → func_shatterglass.

## What the cleanup did

See [mg_n64_goldeneye_cleanup_log.txt](mg_n64_goldeneye_cleanup_log.txt): 6 prefabs collapsed, 4 dropped outputs restored, 13 equips → weapon slots, point_servercommand → script `Cmd_n` (credits message, `sv_infinite_ammo 2`, `sv_autobunnyhopping 0`, nade hint), 27 ambient_generics → 8 soundevents (3 stock CS:GO sounds extracted), visfit 48 Low / 26 Lower / 1 Lowest, 11 of 567 lights Stationary, radar, 6 missing materials rebuilt from CS:GO, 2 overlays → csgo_static_overlay.

## Open / to check

- 2026-10-27 passes, check in Hammer/game: texture alignment on walls/floors (revert = restore the `.vmap.bak`), the new probe volumes, glass04.
  Faces still with an absurd scale and no VMF match: nuke_metalvent 8, dev_measuregeneric20 12, offwndwb 1, blackmetal 8, door_metal_hr 10, rail_rust 1,
  glass01 13, glass04 1, metalrail003a 10, metalwall014a 32. concretefloor016a / dev_measureice01 scales fixed but coordinates not rewritten (no texture size).
- 14 point_spotlight beams and the env_fog_controller are dropped by the importer (cosmetic).
- Chat messages go through cs_script `ServerCommand("say ...")`.
- Vis: if anything pops where players stand, change the nearest Lower hint to Low.

## Scripts

- [`scripts/mg_n64_goldeneye_io.js`](scripts/mg_n64_goldeneye_io.js) (point_servercommand commands, spawn strip + knife)
