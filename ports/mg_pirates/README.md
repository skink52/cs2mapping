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
- 2026-11-03: **z-fight fix undone where it was wrong** (skink52 spotted it): the 2 Nov polish had hidden 0 and moved 2 faces that only overlap a switched, moving, breakable or undrawn entity, or sit behind a see-through face. Restored from the pre-polish backup; zfight.py now leaves those alone. Needs a lighting build.
- 2026-11-10: CS:GO's water colour and murkiness, underwater fog in the water only (`fog_volume`), and the ropes rebuilt as cable_dynamic
  parented to the masts (see below). Needs a build.
- 2026-11-14: water cut into ≤384-u pieces (`watersplit`) and rebuilt, then **undone the same day**: the compiler's func_water "Failed to create physics hulls" warning, which the cut was meant to remove, turned out to be harmless (water with it works in game). vmap restored from `.bak_watersplit_20261114_*` and rebuilt entities-only; the cut version is kept as `.bak_prerevert_*`.

## Open / to check

- Cannons: check the shot speed and arc in game (2000 u/s, `MAX_SPEED` in `tools/physlaunch.py` / `speed` in the io script's LAUNCH table). Aiming and boats otherwise untested.
- Water edge: fade width is `g_flSkyBoxFadeRange` in `pirates_water.vmat` (0.1). The water textures are the stock compiled ones (`g_t… .vtex`): if the water looks flat, the vmat needs the `Texture…` inputs instead.
- 18 env_spritetrail (cosmetic trails) left out; a trail particle would replace them.
- If the 3D skybox doesn't render: untick Editor only on the skybox map's sky_camera.
- 6 trim faces with an absurd texture scale left as imported.
- Vis: if anything pops in or out of view where players stand, raise the nearest hint (Lower → Low → Medium).

## Water (29 Oct 2026)

- `water` pass: water meshes → func_water, underwater post_processing_volume 80 u below the surface (master volume already there). Not yet built.
- `pirates_water.vmat` failed to compile (textures pointed at `.vtex`); regenerated with `.vtex_c`.

## CS:GO's water look and underwater view, and the ropes (10 Nov 2026)

Applied to both real maps at skink52's request (first written as a separate test map, which was deleted unbuilt). Hammer was closed;
backups `maps\mg_pirates.vmap.bak_water_20261110_115913` and `maps\mg_pirates_3dskybox.vmap.bak_water_20261110_115913` (the main map as
skink52 last saved it in Hammer, 10 Nov 11:58). Not built yet. Background and the open questions:
[cs2-slop-porting-review.md](../../docs/reference/cs2-slop-porting-review.md#water-csgos-look-above-and-below-the-surface).

- **Ropes**: the 24 move_rope / keyframe_rope had come through as 8 `path_particle_rope` (flat-lit particle cables, rope material on
  the whole chain, t_mast2's chain missing its bottom node). Removed and rebuilt from the .vmf by `ropes` (16 cable_dynamic: rope_braid_1
  from the mast tops, cable.vmat below, as CS:GO's materials; sag from Slack, up to 26 u; 8 end caps at the mast tops), each **parented
  to its mast** (mast1 / mast2 / t_mast1 / t_mast2, func_breakables riding the `sinker` / `t_sinker` func_tracktrains) so they sink with
  the ship; the caps are prop_dynamic for that.

- CS:GO's water here is stock `liquids/inferno_water`: `$fogcolor {7 16 18}`, `$fogstart 5`, `$fogend 64` (a dark, murky teal).
- Surface: `materials/pirates/pirates_water_csgo.vmat` (and `_skybox`), our `pirates_water.vmat` (nuke_water + skybox fade) with
  cs2-slop-porting's WATER_CONVERT values: fog colour 7 16 18, fog strength 8 × 300 / 64 = 37.5, fog shadow and underwater darkening 0,
  decay colour white at 1, max depth 100 (6.25 in the skybox, built at 1/16), reflectance 0.02 with Fresnel 5, backfaces drawn,
  caustics and debris off.
- Underwater view: `env_gradient_fog` `underwater_fog` (colour 7 16 18, start 5, end 64, falloff exponent 1 for Source 1's
  linear fog, max opacity 1, no height fog, fade 0.2 s) and a `fog_volume` (`toolsfog`) over the func_water from 16 u under the bottom
  to the surface (z 0) naming it. The map had no fog before.
- `env_player_visibility` with player fog distance and density multipliers 1 (CS2's defaults 1.7 / 0.6 keep players clearer than walls in fog).
- Water parts by a one-off script (not in the repo); the underwater post_processing_volume and lights from the `water` pass are kept.

To check in game after the build, against CS:GO's mg_pirates from the same spots:
- Ropes: sag and caps look right, and they go down with the ship when it sinks (and vanish with a mast that breaks, as the mast's
  children).
- From the deck: is the sea a solid dark teal like CS:GO, not a grey mirror? Does it meet the 3D skybox sea without a seam?
- Swim with your head just above the surface, then dive: does the fog start only when your eyes go under (the volume tests the camera),
  or already while swimming (it tests the feet: lower the volume's top by about 64 u)?
- Is the rest of the map free of fog? If the whole map is teal, a fog_volume only picks between fogs and the map needs a clear default
  fog too.
- Looking up from under the water: is the surface visible, and are the ship and sky faded?
- Another player under water: fogged like the walls?
