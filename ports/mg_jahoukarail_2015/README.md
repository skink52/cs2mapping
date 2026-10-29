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
- 2026-10-29: looked unlit: the importer's Static light_environment → Stationary, a stationary light added to the open-air play space (`lights` with the open-sky rule). de_train/barrel broke into nothing: generic CS:GO metal chunks added to its vmdl (`gibfix.py`); `maps/mg_jahoukarail_2015_fix_refs.txt` lists the missing gib models (wood_crate001a chunks, watermelon01 chunks for the stock watermelon, metal_gib1-5) and model materials (ventilationduct02, concretebags, fruit_objects01) for `run_fixrefs.bat`. Backups `prefabs+backups\\mg_jahoukarail_2015_2026-10-29_prelights.vmap`, `…_barrel_2026-10-29.vmdl`.

## Open / to check
- Run `run_fixrefs.bat mg_jahoukarail_2015` before the next build; check the barrel / crate / watermelon breaks in game.

- 19 point_spotlight and 4 func_dustmotes dropped by the importer (cosmetic).
- Substituted material: environment_maps/pipeset_metal → models/props_pipes/pipeset_metal.
- Overlay materials not converted: bills02a, blood7, blood8.
- env_steam particles: check direction, size, density.
- 48 physics props: physpush is optional if pushing feels wrong.
- Vis: if anything pops in or out of view where players stand, raise the nearest hint (Lower → Low → Medium).
