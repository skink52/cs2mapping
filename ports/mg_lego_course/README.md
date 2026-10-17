# mg_lego_course

| | |
|---|---|
| Status | Published |
| Workshop | [mg_lego_course](https://steamcommunity.com/sharedfiles/filedetails/?id=3820524232) |
| Original map | The_Prodigy (CS:GO port by Hallucinogenic Troll) |
| Imported | 2026-10-14 |
| Map last changed | 2026-10-16 |
| How | first cleanup with the scripted fixes that became stage C |

## What the cleanup did

(from the cleanup log in this folder)

- restored 21 sky brushes (dropped by the importer) as moondome meshes using materials/skybox/sky_dust_moondome.vmat
- env_sky sky_dust: rebuilt materials/skybox/sky_dust.vmat from the six CS:GO faces packed in the BSP; boharox/lego/dawall_middle.vmat created (texture was imported, material wasn't)
- removed point_servercommand 'prodigy3' (chat messages + sv_airaccelerate now sent by the script)
- removed point_servercommand 'tyi' (chat messages + sv_airaccelerate now sent by the script)
- 15 point_servercommand Command outputs (say messages, sv_airaccelerate 150) -> script Cmd_n; added "Ported to CS2 by skink52" after each CS:GO port credit
- removed game_score 'score1' (game_score does not exist in CS2; ApplyScore -> script Score_500)
- 11 env_laser replaced by func_brush beams (laser_beam_1..11, never solid, materials/lasers/laser_red.vmat copied from mg_circle_course, crossed double-sided quads 8u wide); the existing 2u trigger_hurt under each laser (700 dmg) does the killing, unchanged
- visibility hints: {'lowest': 1, 'low': 39} (lowest box over whole map incl. void, low over gameplay, medium only in the densest cells)
- radar: rendered from geometry

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 2

## Scripts

- [`scripts/mg_lego_course_io.js`](scripts/mg_lego_course_io.js) - point_servercommand (map credits, sv_airaccelerate 150) and game_score replacements

## Open / to check

- chat messages use "say" from cs_script ServerCommand - if your server blocks it the messages just won't show
