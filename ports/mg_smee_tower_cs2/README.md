# mg_smee_tower_cs2

| | |
|---|---|
| Status | Published |
| Workshop | [mg_smee_tower_cs2](https://steamcommunity.com/sharedfiles/filedetails/?id=3816892618) |
| Original map | Mathijs (CS:GO port by WriteX) |
| Imported | 2026-10-09 |
| Map last changed | 2026-10-17 |
| How | manual (Valve importer + post_import_cleanup.py) |

The first mg map in this batch of ports. The source BSP was already named `mg_smee_tower_cs2.bsp`.

## History

- 2026-10-10: decal materials converted to `csgo_static_overlay` with `vmat_to_overlay.py` (mask keyed from the most common border colour, softened for blood decals).
- 2026-10-17: two-level radar split at z 2560: `"default"` (top of the tower, T spawn) with `mg_smee_tower_cs2_radar_psd`, and `"lower"` (ground, yard and tower stairs) with `mg_smee_tower_cs2_lower_radar_psd`. Loading text "Original map by Mathijs / CS:GO port by WriteX / Ported to CS2 by skink52". Both radar images were compiled the same morning.

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 15

## Open / to check

- Check in game that the radar switches between the two levels.
