# de_rats_1337

| | |
|---|---|
| Status | Published |
| Workshop | [de_rats_1337](https://steamcommunity.com/sharedfiles/filedetails/?id=3820105155) |
| Original map | SkyDusH (credits also name Deamon) |
| Imported | 2026-10-14 |
| Map last changed | 2026-10-15 |
| How | first cleanup with the scripted fixes that became stage C |

Part of the first three-map batch with de_rats_1337, mg_lego_course and mg_super_tower, where the loading-screen credit rule started.

## History

- 2026-10-14: 9 fan-vortex pushes (300) and a 16000 vent launcher → script push zones; 8 decals with grey backgrounds keyed into static overlays; 94 prop_hallucination lamps and ladders (invisible in CS2) → 32 prop_dynamic (the named ones) + 62 prop_static; the 32 switchable lights → Dynamic (Static lights can't switch off); sky and 5 materials rebuilt; boathouse water → stock CS2 water; radar from the original CS:GO radar image; vis hints (Lowest over the map, Low over the play areas, one Medium); loading text.
- 2026-10-14 23:22: three sounds pulled from CS:GO's VPK wavs as `rats.boulder_scrape_rough`, `rats.inferno_loop` and `rats.steam01`.
- 2026-10-15: a lighter model's `no_material.vmat` repointed at its black material.

## What the cleanup did

(from the cleanup log in this folder)

- env_sky embassy: rebuilt materials/skybox/embassy.vmat from the six CS:GO faces
- 12 trigger_push (fan vortex "TP" x9 at 300, vent launcher at 16000) -> trigger_multiple + script push zones holding CS:GO speed; "TP" name kept so the fan button still enables/disables them
- visibility hints: {'lowest': 1, 'low': 15, 'medium': 1} (lowest box over whole map incl. void, low over gameplay, medium only in the densest cells)
- radar: original CS:GO radar converted (panorama/images/overheadmaps/de_rats_1337_radar_psd.png + game resource/overviews/de_rats_1337.txt)

## Import report

(`post_import_cleanup.py` report in this folder)

- Models - failed to compile: 1
- Textures - fully missing, no source found anywhere: 6

## Scripts

- [`scripts/de_rats_1337_io.js`](scripts/de_rats_1337_io.js) - trigger_push replacement (fan vortex, vent launcher)

## Open / to check

- The three imported sounds haven't been tested in game.
