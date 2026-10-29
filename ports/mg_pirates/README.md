# mg_pirates

| | |
|---|---|
| Status | Stage C done, waiting for the build |
| Original | Archanor (credit texture: "Created by Archanor, Inspired by Solid Snake") |
| Imported | 2026-10-29 |
| How | cs2port pipeline (stage A–C + follow-up passes) |

Pirate ship battle: cannons and boats steered with the movement keys (game_ui).

## History

- 2026-10-29: stage A (BSP from `mg maps`), stage B import, stage C.
- 2026-10-29: 256 displacements restored (disprestore on the stage C output).
- 2026-10-29: 3D skybox moved to `mg_pirates_3dskybox.vmap` (212 top-level nodes, box -2720,-2720,-4470 .. 2720,2720,-3550) with `skysplit.py`; `skybox_reference` in the main map.
- 2026-10-29: Missing CS:GO assets copied from the extracted CS:GO content (game_sounds scripts, VTFs, wavs, milrock001); stage D visfit, lights, radar, probes.
- 2026-10-29: game_ui → script (`gameui` pass, first use): 22 game_ui (cannon and boat controllers), 104 outputs fired from the key poll, Freeze Player kept.
- 2026-10-29: 18 func_physbox_multiplayer → func_physbox.
- 2026-10-29: loading credit `maps/mg_pirates.txt` ("Original map by …" / "Ported to CS2 by skink52"); build queue `mg_pirates mg_pirates_3dskybox` then `mg_pirates`.

## Open / to check

- game_ui emulation untested in game: cannons aiming/firing, boats steering, release on +use/jump.
- 18 env_spritetrail (cosmetic trails) left out; a trail particle would replace them.
- If the 3D skybox doesn't render: untick Editor only on the skybox map's sky_camera.
- 6 trim faces with an absurd texture scale left as imported.
- Vis: if anything pops in or out of view where players stand, raise the nearest hint (Lower → Low → Medium).
