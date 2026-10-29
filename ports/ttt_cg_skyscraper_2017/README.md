# ttt_cg_skyscraper_2017

| | |
|---|---|
| Status | Stage C done, waiting for the build |
| Original | CGMentos ("//Map by CGMentosPK") |
| Imported | 2026-10-29 |
| How | cs2port pipeline (stage A–C + follow-up passes) |

TTT map on a skyscraper. TTT gameplay scripting is done separately ([cs2mapTTT](https://github.com/skink52/cs2mapTTT)); this is the map port only.

## History

- 2026-10-29: stage A (BSP from `mg maps`), stage B import, stage C.
- 2026-10-29: 6 displacements restored; 3D skybox moved to `ttt_cg_skyscraper_2017_3dskybox.vmap` (42 nodes, box -3720,1750,500 .. 3780,9190,2240).
- 2026-10-29: 39 func_breakable_surf → func_breakable; clearsky rebuilt; assets; stage D visfit, lights, radar, overlaydepth (33), probes.
- 2026-10-29: loading credit `maps/ttt_cg_skyscraper_2017.txt` ("Original map by …" / "Ported to CS2 by skink52"); build queue `ttt_cg_skyscraper_2017 ttt_cg_skyscraper_2017_3dskybox` then `ttt_cg_skyscraper_2017`.
- 2026-10-29: moondome shells in the 3D skybox map → `toolsskybox` (`skysplit.py --sky`; a moondome hides the 3D skybox). The main map's shells had already been changed to toolsskybox in Hammer. Backup: `prefabs+backups\ttt_cg_skyscraper_2017_3dskybox_2026-10-29_moondome.vmap`.
- 2026-10-29: vis compile too slow (map is ~15,700 units tall). `visfit_lean`: 18 Low + 14 Lower hints (8.9 + 14.6 billion cubic units) → 10 Lower (10.7 billion) over the walkable band only, everything else Lowest. Backup: `prefabs+backups\\ttt_cg_skyscraper_2017_2026-10-29_previs.vmap`.
- 2026-10-29: lower floors too bright: 51 CS:GO `_fifty_percent_distance` lights (linear falloff in CS:GO) had ~8x brightness and 9,000-17,000 unit ranges from the importer; `lightbright` now matches them at 128 units (range ~1,600). Vents pitch black: `ventlight` put 8 dim stationary lights in the ducts behind the 9 nuke_metalvent grates (grates Disable Shadows). Office chairs see-through (renderamt 180, rendermode Normal): renderamt 255 on 6 entities. Sun Static → Stationary. `maps/ttt_cg_skyscraper_2017_fix_refs.txt` lists the missing gibs (oildrum chunks, cafeteria_table001a chunks, furniture gibs) for `run_fixrefs.bat`. Backup `prefabs+backups\\ttt_cg_skyscraper_2017_2026-10-29_prelights.vmap`.

## Open / to check
- Run `run_fixrefs.bat ttt_cg_skyscraper_2017` before the next build. `hr_concrete_polished_002`'s detail texture is missing from CS2 itself (a stock material; not fixable here).

- 2 VMF entities with outputs not matched 1:1 in the vmap (their outputs unchecked).
- env_fog_controller dropped by the importer.
- Overlay materials not converted: decalpapers02, decalstain006a, decalstain009a (vmats not in the addon).
- If the 3D skybox doesn't render: untick Editor only on the skybox map's sky_camera.
- 132 physics props: physpush is optional.
- Vis: if anything pops in or out of view where players stand, raise the nearest hint (Lower → Low → Medium).

## TTT game mode (cs2mapTTT, 29 Oct 2026)

- [cs2mapTTT](https://github.com/skink52/cs2mapTTT) `tools/ttt_convert.py` added `ttt_script` (maps/scripts/ttt.js), `ttt_hud` and the body template
  (the map has no ttt_* entities; its own info_map_parameters is used). Backup: `maps/ttt_cg_skyscraper_2017.vmap.bak_ttt` on the PC.
- Its 132 physics props can be carried (hold E). Open: build and test (cs2mapTTT TESTING.md).
- 29 Oct 2026: the 6 rebuilt sky slabs (clearsky_moondome) retextured to toolsskybox so the 3D skybox (city) shows through; stage C fixed for future 3D-skybox maps.
