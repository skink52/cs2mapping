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
| 4 | Short front design: what moves, what is cut, what every chain stage assumes; regenerate vs transform decision | `docs/SHORT_FRONT_DESIGN.md` | every map stage and script constant that depends on y listed with its new value | |
| 5 | Short front build | layout, patch stages, script config, radar, mortar board | `check_world`, `check_play`, contract, mock, sim_balance green; renders looked at | |
| 6 | Deploy + asset compile + map compile under the watchdog (~55 min) | `tools/deploy_tw.py` | 0 errors, 0 DELETED, nav count recorded | |
| 7 | TESTING items, README, NOTES, CHANGELOG | docs | committed | |

Steps 1-3 do not depend on the map shape and can be deployed on their own if step 5 runs long.
