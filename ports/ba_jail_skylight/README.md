# ba_jail_skylight

| | |
|---|---|
| Status | Ported, with added scripted features (jailbreak map) |
| Imported | 2026-08-30 |
| Map last changed | 2026-09-28 |
| How | manual (Valve importer + post_import_cleanup.py) |

8 bumper cars (1-4 blue, 5-8 red: physbox `carN` + four thrusters each, driven remote-control style, crouch/jump to get out), a remote-piloted helicopter (six thrusters, +use in and out, optional camera anchor), weapon buffs (ssg08 = invisible, mp5sd = about 2x speed, gated so loadout copies don't count), and a keypad door. The servers run CounterStrikeSharp with a loadout picker and a Last Request system, which the buff gating had to work around. Separate 3D skybox map.

## History

- 2026-09-28 (file date): the keypad was rebuilt as a cs_script code door. Map entities are re-created every round, so the script re-hooks the buttons on every round start.

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
