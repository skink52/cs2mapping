# mg_lego_course

| | |
|---|---|
| Status | Published |
| Workshop | [mg_lego_course](https://steamcommunity.com/sharedfiles/filedetails/?id=3820524232) |
| Original map | The_Prodigy (CS:GO port by Hallucinogenic Troll) |
| Imported | 2026-10-14 |
| Map last changed | 2026-10-16 |
| How | first cleanup with the scripted fixes that became stage C |

## History

- 2026-10-14: 21 dropped sky ceilings → moondomes; equips → `weapon0` slots; game_score, env_sun and point_viewcontrol removed; a "Ported to CS2 by skink52" chat line; `dawall_middle` material fixed; radar from the geometry. At 22:19 its 11 env_lasers became func_brush beams `laser_beam_1..11` (crossed quads, 8 units wide, never solid, parents kept). The existing 2-unit, 700-damage trigger_hurts do the killing.
- 2026-10-15: `Cmd_0..Cmd_14` (15 chat lines plus `sv_airaccelerate 150`) replace two point_servercommands, and `Score_500` replaces game_score on the five finish lasers (21 outputs). The winners' box: a door, a one-time trigger that plays saxobeat (`lego.saxobeat`) and shows the credits, then five lasers worth 500 points to the first player to touch each. CS2's `AddScore` adds to the score column, where CS:GO's game_score added frags.

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

- Interior lighting is weak (left for a manual pass).
- chat messages use "say" from cs_script ServerCommand - if your server blocks it the messages just won't show
