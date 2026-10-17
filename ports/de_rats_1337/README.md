# de_rats_1337

| | |
|---|---|
| Status | Published |
| Workshop | [de_rats_1337](https://steamcommunity.com/sharedfiles/filedetails/?id=3820105155) |
| Imported | 2026-10-14 |
| Map last changed | 2026-10-15 |
| How | first cleanup with the scripted fixes that became stage C |

Part of the first three-map batch with de_rats_1337, mg_lego_course and mg_super_tower, where the loading-screen credit rule started.

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
