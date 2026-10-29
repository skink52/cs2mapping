# mg_jahoukarail_2015

| | |
|---|---|
| Status | Stage C done, waiting for the build |
| Original | Ganesh (BSP hint message) |
| Imported | 2026-10-29 |
| How | cs2port pipeline (stage A–C + follow-up passes) |

Minigame course on a train.

## History

- 2026-10-29: stage A (BSP from `mg maps`), stage B import, stage C.
- 2026-10-29: 38 displacements restored; missing assets (tarp_ext_01, mudfloor001a_cheap) rebuilt from the CS:GO content.
- 2026-10-29: Jungle sky rebuilt from the six faces; 9 env_lasers → beams (laserhurt: none did damage); env_steam → particles.
- 2026-10-29: Stage D visfit, lights, radar, overlaydepth (138 overlays), probecover (17 volumes).
- 2026-10-29: loading credit `maps/mg_jahoukarail_2015.txt` ("Original map by …" / "Ported to CS2 by skink52"); build queue `mg_jahoukarail_2015`.

## Open / to check

- 19 point_spotlight and 4 func_dustmotes dropped by the importer (cosmetic).
- Substituted material: environment_maps/pipeset_metal → models/props_pipes/pipeset_metal.
- Overlay materials not converted: bills02a, blood7, blood8.
- env_steam particles: check direction, size, density.
- 48 physics props: physpush is optional if pushing feels wrong.
- Vis: if anything pops in or out of view where players stand, raise the nearest hint (Lower → Low → Medium).
