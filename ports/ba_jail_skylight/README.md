# ba_jail_skylight

| | |
|---|---|
| Status | Ported, with added scripted features (jailbreak map) |
| Imported | 2026-08-30 |
| Map last changed | 2026-11-03 (switched lights, disco floor, trim mesh bottom row to -704) |
| How | manual (Valve importer + post_import_cleanup.py) |

8 bumper cars (1-4 blue, 5-8 red: physbox `carN` + four thrusters each, driven remote-control style, crouch/jump to get out), a remote-piloted helicopter (six thrusters, +use in and out, optional camera anchor), weapon buffs (ssg08 = invisible, mp5sd = about 2x speed, gated so loadout copies don't count), and a keypad door. The servers run CounterStrikeSharp with a loadout picker and a Last Request system, which the buff gating had to work around. Separate 3D skybox map.

## History

- 2026-11-09: **ranged music resumes when you come back** (disco1-3, barbie, inthenavy): CS2 stopped a non-looping sound for good once the listener was out of range. `voice_culling_threshold = -1.0` keeps it playing silently (`tools/rangedmusic.py`). vsndevts compiled, backup `soundevents_addon.vsndevts.bak_20261109`; not yet heard in game or uploaded.
- 2026-10-25: radar re-rendered with textured floors (`radar.py` + `radartex.py`).
- 2026-10-24: Radar, 1 loading-screen image, credits (JJJohan, custom models IVORK). Assets compile with `run_build.bat "assets ba_jail_skylight"`.
- 2026-09-28 (file date): the keypad was rebuilt as a cs_script code door. Map entities are re-created every round, so the script re-hooks the buttons on every round start.
- 2026-11-03: **switched lights** (`mapcheck.py`): 30 lights the map switches are no longer baked: Stationary (Dynamic only if it rides a parent or was already Dynamic; shadows off where more than 4 shadowed stationary lights would overlap), bounce light off, so their light no longer stays on the walls when they are off. Needs a lighting build.
- 2026-11-03: one TurnOn / TurnOff output to a CS2 light renamed Enable / Disable (`mapcheck.py`).
- 2026-11-03: **trim mesh floating above the floor** (skink52 spotted it: the gap shows only where the 468-face trim mesh sits on the 4139-face floor): the trim's bottom row of 428 vertices sat at z -703.0..-703.5 over a floor top at -703.875, and moving the whole mesh down opened the join at its top. Fixed by stretching only the bottom row to z = -704 (the floor skirt's bottom, on the prefab grid); the top row and every other mesh untouched, no face flattened. Backup `ba_jail_skylight.vmap.bak_trimfix_20261103_135500`. Needs a build and an in-game look.
- 2026-11-03: **hairline gaps between the wall, floor and trim meshes: tried and reverted.** skink52 saw small gaps along the edges of the collapsed meshes (most visible on the 468- and 4139-face meshes) against the environment prefab. Measured: the floor tops sit at -703.875 with a 0.125 skirt of sliver faces, the 4382-face wall mesh 0.035 low, the 468-face trim mesh between -703.5 and -703.0 where everything meets at -704; geometry identical since the 26 Oct backup. `meshweld.py` (new) moved 8,604 vertices back onto the prefab's vertices / the grid and welded near-touching vertices of different meshes (real near-miss pairs 3,414 -> 229); a first version that also rebuilt the half-edge arrays crashed Hammer on load. The position-only map opened but skink52 reported it did not fix what he sees, so the map was restored from `ba_jail_skylight.vmap.bak_weld_20261103_130600` (byte-identical to his 12:49 save). Open: what the visible gaps actually are (vertex drift was measured, but closing it changed nothing visible).
- 2026-11-03: **disco floor** (`mapcheck.py`, skink52): its 24 coloured switched lights have shadows off, so the changing colours look right; switched lights get no baked bounce. Needs a lighting build.
- 2026-11-14: water cut into ≤384-u pieces (`watersplit`) and rebuilt, then **undone the same day**: the compiler's func_water "Failed to create physics hulls" warning, which the cut was meant to remove, turned out to be harmless (water with it works in game). vmap restored from `.bak_watersplit_20261114_*` and rebuilt entities-only; the cut version is kept as `.bak_prerevert_*`.

## Import report

(`post_import_cleanup.py` report in this folder)

- Models - failed to compile: 6
- Textures - fully missing, no source found anywhere: 33

## Scripts

- [`scripts/buff_new.js`](scripts/buff_new.js) - invisibility / speed buffs tracked from the named map weapons
- [`scripts/bumper_cars.js`](scripts/bumper_cars.js) - game_ui replacement for the 8 cars
- [`scripts/helicopter.js`](scripts/helicopter.js) - game_ui replacement for the helicopter (6 thrusters, camera follow)
- [`scripts/keypad.js`](scripts/keypad.js) - keypad code door

## Open / to check

- `dodgeballbutton` OnPressed → Unlock should target `0button` (it targets `zerobutton`).
