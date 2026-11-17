# Short front revision (started 17 Nov 2026)

AI-generated (Claude) for skink52. The user's request, 17 Nov 2026:

> the actual trench is too long, and there are too many mortar stations. can we shrink it to about a third the size, keeping the
> underground, and forest, the size they are. we also need to create a solution to stop players on the ground seeing the reticle of
> the planes - an adaptive hud like ironframe would be ideal instead. The plane sounds are also very cartoony, and the mortar sound
> doesn't carry much weight to it. [...] reinstate a gentle fog, that's atmospheric but still allows for the infantry to see from one
> side of the trench to the other.

**Resuming after a usage stop or a new chat:** read the step table below and the newest `out/short_front/progress.md` line, check
`git log -5` on this folder, then carry on with the first step not marked done. Never redo a done step; every step leaves its files
in git or in `out/short_front/<step>/` before it is marked done.

## Starting point (checked 17 Nov)

- Deployed map `content\csgo_addons\mg_trenchwarfare\maps\mg_trenchwarfare.vmap` = chain final **843a5675** (the 14 Nov deploy;
  not saved in Hammer since). Last compile 7: clean, level **compiled, not loaded in CS2**.
- Trench (`tools/layout.py`): `NBAY = 15` bays of `P = 384` u = 5,760 u along y (-2,880..2,880), fire trench x +-1,641, support
  x +-2,150; 3 communication trenches, 3 shelters, **5 mortar pits a side** (`MORTAR_X` 3,200, y -1,600..1,600).
- Underground (`layout.tunnels()`): galleries at y -3,200..-3,536 off the south end of the support trench (sap at y -2,816).
- Forest skirmish: north of the last traverse (ladder at y 2,904), clearing y 3,450-4,415.
- Plane sights: world props `tw_gunsight_<tg>` / `tw_bombsight_<tg>` (self-illuminated models, `60_air.js` teleports them):
  **everyone on the ground sees them**.
- Sounds: all synthesised (`tools/sounds.py`, `docs/SOUNDS.md`). Stock CS:GO VPK holds real prop-plane recordings
  (`sound/ambient/overhead/plane1-3`, `bank_airplane_01-03`, `dust2|nuke/airplane_0N`) and heavy thunder / explosion material.
- Fog: only `env_cubemap_fog` (250-7,500, max 0.85, exp 1.25). No `env_volumetric_fog_controller`: the user's 29 Oct save already
  had none. Fire trench to fire trench is 3,282 u.

## Decisions taken without asking (change them if the user says otherwise)

- Keep the **centre third**: 5 bays (y -960..960). Forest and underground keep their size and shape and move in along y to meet
  the new trench ends (forest -1,920, galleries +1,920).
- **2 mortar pits a side** (was 5), one per flank of the shorter line.
- Aerodromes, hangars, runways, briefing room unchanged.
- Plane sights: a per-player HUD layer (only the pilot's screen), projected from the chase camera like IRONFRAME's lock bracket.
- Sounds: real recordings (stock game files, so no licence question) layered over the existing synthesised low end.
- Fog: gentle, both layers; the far fire trench must stay clearly readable (target: under 25 % fog at 3,300 u at head height).

## Step table

| # | Step | Files | Done when | Status |
|---|---|---|---|---|
| 0 | Plan, resume notes, memory pointer | this file, `NOTES.md`, memory | committed | done 17 Nov |
| 1 | Pilot-only HUD sights: gun pip at the guns' convergence point and bomb ring at the predicted impact, projected onto the pilot's screen, edge arrows when off screen; world sight props parked for good (removed from the map in step 5) | `src/modules/40_hud.js`, `60_air.js`, HUD xml/css (`tools/tw_hud.py`), `docs/HUD.md` | api check, tscheck, contract, `tw_hud.py`, `hud_check.py`, mock green (simulated) | done 17 Nov (simulated) |
| 2 | Sounds with weight: plane engine loop, guns and dive from real recordings; mortar launch / whistle / impact with a real low end and a long tail | `tools/sounds.py`, `docs/SOUNDS.md`, staged wavs | loop check green; spectra meet SOUNDS.md targets; listened-to pictures (waveform + spectrogram) | done 17 Nov (simulated; staged `out/short_front/step2/addon`, not deployed) |
| 3 | Gentle fog: `env_volumetric_fog_controller` back + cubemap fog retuned | new guarded stage `tools/patch_fog_2.py` | fog at 3,300 u under 25 % (computed); guard shows only the fog entities | done 17 Nov (simulated: guard PASS, far trench 29 % -> 12 %; chain stage 8_fog, not deployed) |
| 4 | Short front design: what moves, what is cut, what every chain stage assumes; regenerate vs transform decision | `docs/SHORT_FRONT_DESIGN.md` | every map stage and script constant that depends on y listed with its new value | done 17 Nov (docs/SHORT_FRONT_DESIGN.md) |
| 5 | Short front build | layout, patch stages, script config, radar, mortar board | `check_world`, `check_play`, contract, mock, sim_balance green; renders looked at | **in progress** (see "Step 5 progress" below) |
| 6 | Deploy + asset compile + map compile under the watchdog (~55 min) | `tools/deploy_tw.py` | 0 errors, 0 DELETED, nav count recorded | |
| 7 | TESTING items, README, NOTES, CHANGELOG | docs | committed | |

Steps 1-3 do not depend on the map shape and can be deployed on their own if step 5 runs long.

## Step 5 progress (update as pieces land)

**Mid-change warning:** since 18 Nov `tools/layout.py` describes the SHORT front (5 bays). Until step 5 is done the chain stages,
script config, checkers and radar still assume the 15-bay map, so do NOT run `deploy_tw.py --chain` or redeploy the map from this
state; the deployed addon map (843a5675) is untouched.

- [x] 1. `layout.py` parameters (NBAY 5, COMM_Y, SHELTER_Y, MORTAR_Y, RY, spawns, tunnels +1920, craters; helpers `fy()`,
      `FRONT_DY`, `WOOD_DY`, `TUN_DY`).
- [x] 2. `make_map.py` literals moved (battle zone, paint, tile_res, galleries, scatter counts `nk()` and bounds, wrecks `sy()`,
      woods, probes, vis hints, lightmap shell); Windows font fallback; numpy point-in-polygon replaces matplotlib.
      First full run: `out/short_front/step4/gen_short1.vmap` (log `make_map_short1.log`).
- [x] 3. `tools/move_user_objects.py` (user objects by zone): `python tools/move_user_objects.py out/short_front/step4/user_base.vmap
      out/short_front/step5/user_moved.vmap` (user_base = the 29 Oct save, CRC32 2e3f90d0, from `backups
emaster_20261112\`):
      91 moved, 11 dropped (6 niche revetments of the gone y-2304 station, 5 props at an old outer pit). Then
      `python -u tools/make_map.py out/short_front/step5/user_moved.vmap out/short_front/step5/gen_short2.vmap out/short_front/step5/addon_gen`
      (~2.5 min, run under the watchdog). Quick look: `out/short_front/step4/top_short1.png` (shape right: 5 bays, 2 pits, 2 stations a side,
      galleries off the support trench's south end).
- [~] 4. Chain stages re-targeted: world_1 / world_3 `--find` (rules, not ids; single-object 15-bay fixes dropped), sounds from the
      layout, terrain / seams / nav literals moved, terrain finder knows 16-u sheets, battle zone on a tile edge. `deploy_tw.py --chain`
      now runs 0a_moved -> 0b_gen -> 1..8. By hand: `sh tools/short_front_stages.sh [gen|w1|terrain|seams|w3|sounds|nav|fog]` (writes
      out/short_front/step5/chain/; resume from the stage that failed). Status of the first full run: see the newest progress line.
- [~] 5. Script config / ai / front, RADAR, mock seat test done; checkers follow the layout (CREWS 2, TARGET_EXT 3600, NML_Y 830, AREAS moved, AI patrol +-1000,
      ambient bursts +-1280). Checkers (`check_world` counts, `check_play` literals) and restaging `out/entities.json` NOT done.
- [~] 6. Radar reframed (`make_radar.py` scale 7.00); re-run it + `render_sight.py` on the final map (deploy_tw does the radar).
- [ ] 7. Renders looked at; gate green.

**18 Nov ~00:40, first full run** (`sh tools/short_front_stages.sh gen`, ~11 min): every stage ran and every guard PASSED
(world_1 14 targets, world_3 80 incl. 64 pool rims + 16 pit sandbags on 4 pits, sounds 10 (9 emitters), nav 444 (222 NONAV boxes,
**estimate ~3,050 nav areas**, budget 5,000), fog 0 (already in make_map)). The uniform precache props were missing:
`make_map_stage.py` now runs `patch_uniforms.py` after make_map (tested; the chain must be re-run from `gen` to include it).
`check_world` on that map: **clean**. `check_play` (`python tools/check_play.py out/short_front/step5/chain/9_test_uniforms.vmap
--stage out/addon --json out/short_front/step5/chain/check_play.json --map out/short_front/step5/chain/check_play_map.png`, 45 s)
**FAILS**, to fix next (diagnosis so far):
- T8 / walkability: `trench_*_8` at the support trench's north end (x +-2150, y 704) has 18 u headroom: the support trench now ends
  at y 672 (dog-legs from y -864 every 768) -> move that spawn inside (y ~600) in `layout.infantry_spawns`; `trench_t_3`,
  `trench_ct_4` 53-56 u "off the floor" (fire-step duckboards?); `trench_ct_6` split from the CT trench world.
- T4: 3 of 4 dressing-station mouths not in the walkable trench. The support trench's x alternates 2150 / 2198 per 768 segment;
  the old stations sat on 2150 segments. y 576 is on the short 2150 piece between the jog at 544 and the end at 672 -> pick station
  ys on 2150 segments or place niche + shelter at the support trench's x at that y (layout `segments()` niche uses XS).
- T9 CT sap: no standing or crouched passage at the CT sap mouth (T side crouch ok). The user's tl_bench bridges were moved +1920
  with the galleries; check they still sit on the new mouth (`move_user_objects` report, `patch_seams` SAP_CAP).
- 1b routes: no route trench -> woods for either side, ct -> chamber missing: check the woods exit (ladder at x +-1716, y ~984: the
  user's ladders were moved -1920; the generated exit is at y 996) and the woods blockers / clip walls; then the CT sap (above).
- T7: plane_t_5, plane_ct_2, plane_ct_3 air lanes blocked by tall poplars by the aerodromes (the old T7 per-tree fix was a 15-bay
  instance fix, dropped): make it a rule (scale or skip poplars under the lanes) in make_map or patch_world_3 `--find`.
- T2: one CT fire step "blind" at (1575, 576); clipping (woods half: head 4/6, crouch 2/1 of need 4); water: 25 z-fight cells near
  (40..88, 1000..1064); nav: see check_play.json "8"/"9".
- 3 floating props, 2 dressing-inside-solid, 17 overlapping prop pairs (check_world warnings; mostly hangar + petrol can, as before).


**18 Nov ~01:40, check_play after the fixes** (stations off the support trench's real x, user meshes kept via tw_user, user objects
follow the ground, 50-u dressing walkway, no trees under the take-off run, water z-fight rule): routes all OK (woods 1,825 / 1,834,
chamber 2,736 / 2,727, mirror-even), walkability, T4, T7, T8, T9 (both saps crouch, as decided 12 Nov) pass; left only the gate
baseline's accepted categories (clipping: 3 props 6-9 u floating + a wire fence through a log; water; one CT fire step).
check_world clean. Then `python -u tools/deploy_tw.py --chain` (dry run, gate) and, once CS2 / Hammer are closed on the addon,
`--apply`, asset compile, forced HUD / script compiles, map compile (docs/BUILD.md). The user said (18 Nov): "deploy when the checks pass".
Step-16 deploy list (`out/step16/deploy_files.txt`, out/ is not in git): panorama/images/custom_game/tw/m_pip.png, m_ring.png, m_edge.png,
m_edge_bomb.png, target_t.png, target_ct.png (from out/addon; re-run `python tools/render_sight.py` after the chain's radar).
