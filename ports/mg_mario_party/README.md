# mg_mario_party

| | |
|---|---|
| Status | Published, fixes on 17 Oct 2026 not yet republished |
| Workshop | [mg_mario_party](https://steamcommunity.com/sharedfiles/filedetails/?id=3818267169) |
| Imported | 2026-10-11 |
| Map last changed | 2026-10-17 |
| How | manual (Valve importer + post_import_cleanup.py), hand fixes and scripts; follow-up fixes with the pipeline tools on 17 Oct |

Mario-themed multigame lobby with 20+ minigames (Mario Says, Hexagon Heat, Platform Peril, Obstacle, Speed SMGs, Thwomp Falls, Sniper Thwomps, Block Fort, Chain Chomp, Knife Arena, MVP, pirate/floating islands, gun games...). Almost every CS:GO I/O trick in it needed a cs_script replacement.

## History

- 2026-10-11: soundevents built from the map's 46 sounds. Every ambient_generic became a point_soundevent, with `PlaySound` → `StartSound` (`StopSound` stays).
- 2026-10-11/13: ported with the manual flow. `mario_io.js` replaced the `!activator AddOutput targetname` filters, player alpha/colour, player_speedmod, trigger_gravity, retargetable teleporters (`AddOutput target`), game_round_end, the Block Fort random spawn sorter, the Chain Chomp's 16 phys_thrusters (the script glides Dog_box), the spawn-box mushroom power-up and the spawn strip. `overlays.js` + Panorama replaced 25 env_screenoverlays. `teleports.js` replaced SetRemoteDestination for the MVP game. `changemodel.js` and `mvp_health_increase.js` are ports of the map's VScripts.
- 2026-10-12: filter audit (warnings about missing filter targets are names the script gives players, such as `predator` and `marine`). A new `part1_spawn` destination for the five part1 teleports, which pointed at one that never existed. Dead Mario Kart teleports removed. Moondome with `sky_pipeplaza`.
- 2026-10-12: math_counter → logic_case now goes through the script (`COUNTER_TO_CASE`), because CS2 passes the counter value as a float ("5.000000") and the whole-number cases never fired. The hooks are re-made every round, since map entities respawn.
- 2026-10-12: the mushroom grab is done by script within 36 units: CS2 stops players at the physbox surface, so the trigger that stuck out 2 units couldn't be reached. Octodad rebuilt on the Phoenix agent (73 bones; the old model had no CS2 skeleton or animgraph, so held weapons were huge). The between-rounds strip moved into the script. Aztec grass/rock blend material. First vis hints (High around the moondome areas).
- 2026-10-13 (`fix_games.py`): chain chomp (frozen physics, the script glides `Dog_box`: chase 280, wander 220); pirate climb `bolder_timer` 0.5 → 1.0 s; Block Fort hands out one of 16 random spawns per team from script (the teleporter only checks players as they enter); Octodad got tm_phoenix's 14 ragdoll joints. Medium arena hints gave 1,451,170 regions and 663 s of clustering, so the arena hints became Low with one Lowest over the void.
- 2026-10-17 (reported in game, compared with the CS:GO v3_5 version): flag cloth was white (the import dropped the neon textures from `a_flag/green.vmat` and `mario/red.vmat`); A/B button fronts were black (letter textures now alpha-tested); entity lighting didn't match the world (no light probe volumes: one `env_combined_light_probe_volume` per moondome room, 32 total); no fire on torches (40 `info_particle_system` with `particles/burning_fx/env_fire_tiny.vpcf`); lava added under Mario Says, Hexagon Heat and both pits of Obstacle's last level (new `mario_cs2/lava_glow.vmat`); water in the 5 pits of Obstacle's sand level; Platform Peril's moving laser hurt trigger got a visible magenta beam (`laser_door1_beam`, parented to `laser_door1`); wall-jump arrow decal translucent; Speed SMGs ran about 8% slow (friction, and CS:GO's speedmod scaled the held weapon's speed); weapon triggers handed out duplicate guns (CS2 `game_player_equip` gives duplicates); 13 thwomps silent (sound only in func_door keys); bullet bills fell out of the cannons (CS2 trigger_push doesn't throw the prop).
- 2026-10-17: vis compile took 103 s to voxelise (19.2M nodes) plus 62 s outside detection. The 64 sky shells (moondome + tools/skybox per room) were set to Exclude from Vis, since every room is sealed by its own nodraw hull, and the 32 Low vis hints (all copies of the map-wide box) were made one per room.
- 2026-10-17, rebuilt from the command line (29.3 min, OK): voxelize 23 s / 3,641,409 nodes (was 103 s / 19,173,961), outside detection 27 s (was 62 s). The vis stage as a whole still took 27 min: 117 s of clustering, 416 s merging cluster lists, 444 s of line-of-sight rays and 560 s merging 12,963 clusters down to 4,096.

## Import report

(`post_import_cleanup.py` report in this folder)

- Textures - fully missing, no source found anywhere: 5

## Scripts

- [`scripts/changemodel.js`](scripts/changemodel.js) - port of changemodel.nut (Octodad player model, tint/glow fallback)
- [`scripts/mario_io.js`](scripts/mario_io.js) - all the I/O replacements, plus `Equip_<name>` (no duplicate weapons), `BulletFire_<push trigger>` (bullet bill cannons) and weapon-speed `Speed_<x>`
- [`scripts/mvp_health_increase.js`](scripts/mvp_health_increase.js) - port of mvp_health_increase.nut (predator 600 HP)
- [`scripts/overlays.js`](scripts/overlays.js) - env_screenoverlay replacement (custom_hud_layout `mario_overlay_layout`, panels in `panorama/`)
- [`scripts/teleports.js`](scripts/teleports.js) - trigger_teleport SetRemoteDestination replacement (MVP game)

## Open / to check

- 2026-10-27 (mock engine): `mario_io.js` `moveBullets()` moves the bullet bills with `Teleport` every tick; CS2 stops drawing props moved that way (the mushrooms were switched to `Move` for this). Switch to `Move` if the bullets are invisible in game.

- This port was made from an older version than CS:GO v3_5, so some geometry differs (Hexagon Heat, for example). The lava and sand water match v3_5's look rather than its exact brushwork. The original BSP is no longer in `C:\source1`.
- Flag colours are red/green (the original materials). v3_5 has black flags, so check which is wanted.
- Torch fire positions were estimated from the nearby lights.
- Bullet speed is `BULLET_SPEED = 1500` in `mario_io.js`.
- Moondome doesn't fully block the other arenas: small parts of them show from odd positions (reported 13 Oct).
- The motes game prints "t's win" but doesn't end the round (reported 12 Oct).
- Vis still takes 27 min. Switching the 32 room hints from Low to Lower (`hintType` 8) should start with fewer clusters.
- Test in game: thwomp sounds, bullet bills, Speed SMGs, lava and water, entity lighting.
