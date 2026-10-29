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
