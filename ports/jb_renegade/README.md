# jb_renegade

| | |
|---|---|
| Status | Imported and worked on (jailbreak map, Aug-Sep 2026) |
| Source BSP | `jb_renegade_v5_d` |
| Imported | 2026-08-30 |
| Map last changed | 2026-08-30 |
| How | manual (Valve importer) |

## Scripts

- [`scripts/secret.js`](scripts/secret.js) - GiveHugeHealth: 1000 HP for whoever finds the secret

## History

- 2026-11-03: **switched lights** (`mapcheck.py`): 8 lights the map switches are no longer baked: Stationary (Dynamic only if it rides a parent or was already Dynamic; shadows off where more than 4 shadowed stationary lights would overlap), bounce light off, so their light no longer stays on the walls when they are off. Needs a lighting build.
- 2026-11-14: water cut into ≤384-u pieces (`watersplit`) and rebuilt, then **undone the same day**: the compiler's func_water "Failed to create physics hulls" warning, which the cut was meant to remove, turned out to be harmless (water with it works in game). vmap restored from `.bak_watersplit_20261114_*` and rebuilt entities-only; the cut version is kept as `.bak_prerevert_*`.
