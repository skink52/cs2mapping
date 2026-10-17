# mg_n64_goldeneye

| | |
|---|---|
| Status | Published |
| Workshop | [mg_n64_goldeneye_cs2](https://steamcommunity.com/sharedfiles/filedetails/?id=3818260481) |
| Imported | 2026-10-12 |
| Map last changed | 2026-10-12 |
| How | manual (Valve importer + post_import_cleanup.py) |

Kept as a reference port after publishing.

## History

- 2026-10-12, round 1: soundevents built the same way as Mario Party's. The I/O was diffed against the BSP, and all 41 `Use` → `TriggerForActivatedPlayer` conversions checked. The `elite` equip gave an SSG 08 and now gives Dual Berettas; `item_assaultsuit` restored; leftover CS:GO `weapon_x 1` keys removed. The 14 dropped env_beams restored (lobby lightning, 900 damage, 20 s after a door is chosen), 20 medals restored from the BSP's textures, overlays → `csgo_static_overlay` with masks.
- 2026-10-12, round 2 (from 03:35): all env_beams and their outputs removed on request ("they can cause crashes"). The 24 signs that were left on a grey placeholder were rebuilt as properly sized quads (32×16, 24×24 round, 16×16 vents). 16 func_breakable_surf windows → func_shatterglass with the stock `glass_plate_shatter`.

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 26

## Open / to check

- One unused `point_viewcontrol` is still in the map.
