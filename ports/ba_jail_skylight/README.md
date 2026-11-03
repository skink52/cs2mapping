# ba_jail_skylight

| | |
|---|---|
| Status | Ported, with added scripted features (jailbreak map) |
| Imported | 2026-08-30 |
| Map last changed | 2026-11-03 (mesh weld, switched lights) |
| How | manual (Valve importer + post_import_cleanup.py) |

8 bumper cars (1-4 blue, 5-8 red: physbox `carN` + four thrusters each, driven remote-control style, crouch/jump to get out), a remote-piloted helicopter (six thrusters, +use in and out, optional camera anchor), weapon buffs (ssg08 = invisible, mp5sd = about 2x speed, gated so loadout copies don't count), and a keypad door. The servers run CounterStrikeSharp with a loadout picker and a Last Request system, which the buff gating had to work around. Separate 3D skybox map.

## History

- 2026-10-25: radar re-rendered with textured floors (`radar.py` + `radartex.py`).
- 2026-10-24: Radar, 1 loading-screen image, credits (JJJohan, custom models IVORK). Assets compile with `run_build.bat "assets ba_jail_skylight"`.
- 2026-09-28 (file date): the keypad was rebuilt as a cs_script code door. Map entities are re-created every round, so the script re-hooks the buttons on every round start.
- 2026-11-03: **switched lights** (`mapcheck.py`): 30 lights the map switches are no longer baked: Stationary (Dynamic only if it rides a parent or was already Dynamic; shadows off where more than 4 shadowed stationary lights would overlap), bounce light off, so their light no longer stays on the walls when they are off. Needs a lighting build.
- 2026-11-03: one TurnOn / TurnOff output to a CS2 light renamed Enable / Disable (`mapcheck.py`).
- 2026-11-03: **hairline gaps between the wall, floor and trim meshes** (`meshweld.py`, skink52 noticed them against the environment prefab): the collapsed meshes had drifted off the grid in Hammer (floor tops at -703.875 with a 0.125 skirt of sliver faces, walls 0.035 low, the 468-face trim mesh anywhere from -703.5 to -703.0 where everything meets at -704); 8,604 vertices of 166 meshes put back onto the prefab's vertices / the grid or welded to the neighbouring mesh, positions only (963 moves that would have flattened a sliver face were undone). Real near-miss vertex pairs across meshes: 3,414 -> 229 (the environment prefab itself: 325). A first version that also rebuilt the meshes' edge structure and dropped the slivers crashed Hammer on load (post load fixup) and was rolled back. Geometry had been identical since the 26 Oct backup, so the Nov 3 lighting builds only made the gaps easier to see. Backup `ba_jail_skylight.vmap.bak_weld_20261103_130600`; log `ba_jail_skylight_weld_log.txt`. Needs a build and an in-game look.
- 2026-11-03: **disco floor** (`mapcheck.py`, skink52): its 24 coloured switched lights have shadows off, so the changing colours look right; switched lights get no baked bounce. Needs a lighting build.

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
