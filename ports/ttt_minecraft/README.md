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
- 2026-10-29: vis compile inefficient (~200,900 regions): `visfit_lean` (50 Low + 40 Lower → 48 Lower). 2026-10-29: lighting rules: light_environment Static → Stationary; open-to-sky space gets stationary lights too (`lights`); renderamt fixed where rendermode was Normal. Backup `prefabs+backups\\ttt_minecraft_2026-10-29_prelights.vmap`.
- 2026-10-29 (in-game test): hut doors too narrow when open → `doorsolid` (15 doors were Non-solid to Player in CS:GO; now never-solid func_brush visuals parented to nodraw-hinge doors; Ttest_Frontdoors' second door renamed Ttest_Frontdoors_2 with copied outputs). Open areas pitch black → `skyshell` (11 moondome sky shells → toolsskybox), sun Stationary (earlier). Minecarts unpushable → `physpush` on the 22 func_physbox (minecarts mass ~144, blocks 0.4, gold block 8); two carts at -1348 44 sit on top of each other in the original too. Backup `prefabs+backups\\ttt_minecraft_2026-10-29_predoors.vmap`.

- 2026-10-30 (in-game test: lighting off, water solid, doorframes, traitor wiring, gold/diamond blocks): compared against the BSP.
  `lightbright`: all 88 lights had brightness 0 (= `_light` 265) from stage C; rebuilt from the VMF (50-200, quadratic). `matflags`: water_static was an
  opaque sheet → translucent 0.55 with back faces; cloud 0.9, portal 0.95, trap_lava 0.9 ($alpha); glowstone self-lit ($selfillum), as in CS:GO.
  `iofix`: the main logic_auto read global state `is_pc` (never set in CS2) so it never fired: gold block never teleported in, clouds never moved,
  Relay_Vclips never ran; cleared. `Trap_water`/`Trap_lava` outputs → exact names. `doorhinge`: hinge cubes moved 2 u into the frames (they stuck into the
  doorways). Traitor buttons: all 5 relays match the VMF outputs; only dead targets are `Trap_Nether_Light` / `Ttest_Light_Test`, missing in the original too.
  Diamond ores are placed by `ttt_map_settings` RoundStart (ttt.js `ttt_ms__start`), so they stay in the holding box until a round starts (3+ players).
  Backup `maps/ttt_minecraft.vmap.bak_lighting`.
- 2026-10-30: the End/win room and the gold/diamond holding box sat above the sky ceiling (z 1760-2816), visible from spawn through toolsskybox and
  shadowing the island. From skink52's Hammer save (he added a toolsskybox_occluder slab at 1552-1584 and disableShadows on the ceiling, kept):
  nether moved -4096 (z -5408..-4864), End + holding box moved -11008 (z -9248..-8192); island bottom -320, no overlaps. Teleports into both are
  inside the moved sets. io script nether push zones and cs2mapTTT map data (ttt_auto_3, Pigman_Furnace_Trigger) shifted too; Lowest vis hint spans
  z -9376..1632. Backup `maps/ttt_minecraft.vmap.bak_dims`.

- 2026-10-30: z-fighting ore patches: 33 static overlays (coal 11, gravel 9, iron 8, brick 3, stone 2) were csgo_complex → `<name>_overlay.vmat`
  csgo_static_overlay. Win_Tesla (point_tesla, gone in CS2) → info_particle_system `particles/port_tesla/tesla_ffffff.vpcf`. Lighthouse diamond-block
  trigger works (skink52 tested outside a round; cs2mapTTT now polls prop triggers in every phase, the win input stays round-only). Backup `bak_overlays`.

## Open / to check

- Traitor tester: needs the gold block carried (E, cs2mapTTT's carry) into Ttest_CraftTrigger, which unlocks the door buttons; the check itself is `ttt_traitor_check` → `ttt_logic_role`, handled by ttt.js since cs2mapTTT `cfbd4fa`. What ttt.js still needs for this map: cs2mapTTT `MAP_REQUIREMENTS.md`.

- point_clientcommand T2_Command (forces +duck in a tunnel) not converted.
- Stinger sounds music/stingers/industrial_suspense1/2 not found in the CS:GO content: those ambient_generics are silent.
- env_fog_controller dropped by the importer.
- Vis: if anything pops in or out of view where players stand, raise the nearest hint (Lower → Low → Medium).

## TTT game mode (cs2mapTTT, 29 Oct 2026)

- [cs2mapTTT](https://github.com/skink52/cs2mapTTT) `tools/ttt_convert.py` added `ttt_script` (maps/scripts/ttt.js), `ttt_hud`, the body template and an
  `info_map_parameters`, and converted the 42 ttt_* entities (5 traitor buttons, 5 testers, 8 role tests, 12 texts, 8 damage owners, a credit adjust,
  ttt_win, map settings) into logic_relays driven by ttt.js; the 6 weapon_ttt_* became CS2 weapons. Map data: cs2mapTTT `maps/ttt_minecraft.json`.
- Backup of the map before this: `maps/ttt_minecraft.vmap.bak_ttt` on the PC. Open: build and test (cs2mapTTT TESTING.md).

## Water (29 Oct 2026)

- `water` pass: water meshes → func_water, underwater post_processing_volume 80 u below the surface (master volume already there). Not yet built.
- 29 Oct 2026 (evening): cs2mapTTT covers MAP_REQUIREMENTS.md (status in cs2mapTTT `docs/MAP_REQUIREMENTS.md`): gold block / tester trigger through ttt.js with polling, crouch prompt for T2, sandbox texts removed from logic_auto, io script skips props held by a player (physpush owner check).
