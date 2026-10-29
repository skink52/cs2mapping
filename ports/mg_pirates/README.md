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
- 2026-10-29: moondome shells in the 3D skybox map → `toolsskybox` (`skysplit.py --sky`; a moondome hides the 3D skybox, and pirates' moondome used a sky panorama that was never built, so it was an error material). The main map's sky shells had already been changed in Hammer. Backup: `prefabs+backups\mg_pirates_3dskybox_2026-10-29_moondome.vmap`.
- 2026-10-29: cannons didn't fire (in-game test): each shot was a template ball teleported to the muzzle and thrown by a physics-only trigger_push for 0.15 s, which stage C had turned into a player push (and CS2's trigger_push doesn't throw physics objects anyway). New `physlaunch` pass: the 18 `*_fire` relays now send `Launch_<pusher>`, the script puts the new ball at the muzzle and gives it 2000 u/s along the barrel. Backup: `prefabs+backups\\mg_pirates_2026-10-29_precannon.vmap`.
- 2026-10-29: 3D skybox water didn't blend into the map water. `waterblend.py`: both waters are copies of nuke_water (decompiled with `vmatc.py`); the main one fades out over its last 10% to each edge (`materials/pirates/pirates_water.vmat`), the sea bed under the fade band was cut back, the skybox sea bed lowered 1024 world units and the skybox probe volume (its edges crossed the water) grown over the whole water. Backup: `prefabs+backups\\mg_pirates_3dskybox_2026-10-29_prewater.vmap`.
- 2026-10-29: lighting rules: light_environment Static → Stationary; open-to-sky space gets stationary lights too (`lights`); renderamt fixed where rendermode was Normal. Backup `prefabs+backups\\mg_pirates_2026-10-29_prelights.vmap`.

## Open / to check

- Cannons: check the shot speed and arc in game (2000 u/s, `MAX_SPEED` in `tools/physlaunch.py` / `speed` in the io script's LAUNCH table). Aiming and boats otherwise untested.
- Water edge: fade width is `g_flSkyBoxFadeRange` in `pirates_water.vmat` (0.1). The water textures are the stock compiled ones (`g_t… .vtex`): if the water looks flat, the vmat needs the `Texture…` inputs instead.
- 18 env_spritetrail (cosmetic trails) left out; a trail particle would replace them.
- If the 3D skybox doesn't render: untick Editor only on the skybox map's sky_camera.
- 6 trim faces with an absurd texture scale left as imported.
- Vis: if anything pops in or out of view where players stand, raise the nearest hint (Lower → Low → Medium).
