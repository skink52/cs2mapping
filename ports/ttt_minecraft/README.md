# ttt_minecraft

| | |
|---|---|
| Status | Stage C done, waiting for the build |
| Original | finniespin (credit texture) |
| Imported | 2026-10-29 |
| How | cs2port pipeline (stage A–C + follow-up passes) |

Minecraft-style TTT map. TTT gameplay scripting is done separately ([cs2mapTTT](https://github.com/skink52/cs2mapTTT)); this is the map port only.

## History

- 2026-10-29: stage A (BSP from `mg maps`), stage B import, stage C.
- 2026-10-29: Pakfile entries with absolute paths fixed in prep.py; minecraft sky rebuilt; 10 alpha masks (glass, doors, ladder, tracks, flowers, signs).
- 2026-10-29: Stage D overlaydepth (35), probecover (95 volumes).
- 2026-10-29: loading credit `maps/ttt_minecraft.txt` ("Original map by …" / "Ported to CS2 by skink52"); build queue `ttt_minecraft`.

## Open / to check

- point_clientcommand T2_Command (forces +duck in a tunnel) not converted.
- Stinger sounds music/stingers/industrial_suspense1/2 not found in the CS:GO content: those ambient_generics are silent.
- env_fog_controller dropped by the importer.
- Vis: if anything pops in or out of view where players stand, raise the nearest hint (Lower → Low → Medium).

## TTT game mode (cs2mapTTT, 29 Oct 2026)

- [cs2mapTTT](https://github.com/skink52/cs2mapTTT) `tools/ttt_convert.py` added `ttt_script` (maps/scripts/ttt.js), `ttt_hud`, the body template and an
  `info_map_parameters`, and converted the 42 ttt_* entities (5 traitor buttons, 5 testers, 8 role tests, 12 texts, 8 damage owners, a credit adjust,
  ttt_win, map settings) into logic_relays driven by ttt.js; the 6 weapon_ttt_* became CS2 weapons. Map data: cs2mapTTT `maps/ttt_minecraft.json`.
- Backup of the map before this: `maps/ttt_minecraft.vmap.bak_ttt` on the PC. Open: build and test (cs2mapTTT TESTING.md).
