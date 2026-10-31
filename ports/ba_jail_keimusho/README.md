# ba_jail_keimusho

| | |
|---|---|
| Status | Ported (v3 import, skink52's Hammer work on top); fixes 2026-10-31 awaiting build + in-game test |
| Source BSP | `ba_jail_os_keimusho_v3` (imported); comparison copy on the PC is `ba_jail_os_keimusho_v2.bsp` |
| Original map | Crycelia |
| Imported | 2026-10-07 |
| Map last changed | 2026-10-31 |
| How | Valve importer, Hammer by hand, then a one-off fix script ([`fix_20261031.py`](fix_20261031.py)) |

Loading text: `Map by Crycelia` / `CS2 Port by skink52 for Slime Servers`.

## v2 vs v3

Only a v2 BSP is on the PC; the vmap is v3. Everything in the vmap with no v2 equivalent is treated as planned and kept: death roulette
(`roulbutton`/`roulcase`), spleef (`spleefon`/`spleefoff`, decoy spawners), rock dodgeball (`rockbuttonon`/`off`, `rocktemp6-9`), the ssg08 gun-room
trigger (v2 had sg556), the new cell / sleeping-room doors. The v3 BSP also moved whole sections (gun room, fire game, skipping rope), so only 72 of
117 v2 lights match by position.

## 2026-10-31 fixes

- **Doors:** 9 doors had no opener: each double door's trigger/button had lost the output to the second leaf (outsidebigdoor1, outsideoutsidedoorleft,
  aboveoutsidedoorright, belowoutsidedoorleft, grdoorleft (trigger + `GunRoomctdoorfilter`), slepdoor2, slepdoor3, slepdoor12; slepdoor5's trigger
  fired slepdoor5 twice → second one slepdoor6). Added next to the partner's output.
- **game_player_equip** (12): legacy `weapon_x` keys → `weapon0`; 22 `Use`/`use` → `TriggerForActivatedPlayer` (the `!activator` param cleared).
- **skippingcase:** case values `1` → `1.000000` (math_counter sends a float string). Unverified; the tested fix is script forwarding.
- `func_tanktrain skippingtrain` left as is (exists in CS2).
- **trigger_push** (4, speeds 350/700) → trigger_multiple + `keimusho_push.js` push zones (CS:GO set-speed behaviour, stage C method).
- **Samurai mask** (trigger_once by the floor knife `knife`): the dead outputs (player_speedmod `value` x3, `AddOutput gravity 0.5`, `Alpha ###`,
  `rendermode 1`, `health 200`) → `samuraiscript` `samurai_on` ([`keimusho_samurai.js`](scripts/keimusho_samurai.js)): 3x ground speed (weapon speed x
  friction compensation, Mario Party method), half gravity, alpha 0, 200 HP, a knife if the floor pickup failed, `mask2` unparented and kept on the
  player's head. Resets on death / respawn / round start. `player_speedmod` removed; strip, shake, mask template and knife toggle unchanged.
- **Water race:** `AddOutput gravity -1 / 1` → `gravityscript` `Gravity_-1` / `Gravity_1` ([`keimusho_gravity.js`](scripts/keimusho_gravity.js)).
- **Rock dodgeball:** `rockbuttonon` → `pushscale` `push_on` (0.5 s), `rockbuttonoff` → `push_off` ([`keimusho_pushscale.js`](scripts/keimusho_pushscale.js),
  ba_jail_seaside's pushscale.js for `rock6-9`). The `sm_cvar phys_pushscale` outputs are left in place.
- **Lighting:** brightness rebuilt from the v2 `_light` values (72 matched; the 60 moved/new lights copy the nearest; omni range = sqrt(legacy x 3.3856e6)).
  Every light was the importer's legacy 1 / range 1598, 2-3.5x brighter than CS:GO. light_environment Stationary. `lights` saw one open compartment
  (3 lights), so the new `tools/lightcover.py` did it: 34 lights → Stationary, 19 new unshadowed stationary omnis in unlit play pockets (spleef pit,
  rock arena, roulette rooms, ...), 8 stationary fills over the open-to-sky play areas. Probe volume added around `firebrush` (Priority 1).
- **Bump mines** ([`keimusho_bumpmine.js`](scripts/keimusho_bumpmine.js), `bumpscript`; `weapon_bumpmine` isn't in CS2): the 5 `bumpminebutton`s also fire
  `bump_give`; `awp spawner` now strips and gives `weapon_decoy`. A player with charges (3) throws decoys; on its first bounce the decoy is removed and one of
  8 pooled `bumpmine_N` prop_dynamics (CS:GO `w_eq_bumpmine_dropped`, non-solid, parked under the map) is put there with a land sound; after 0.3 s the first
  player within 36 u is launched (900 u/s away, 750 up) with the detonate sound. Mines expire after 60 s / round start. Model: CS:GO files written loose
  into `csgo\models\weapons` + `csgo\materials\models\weapons\v_models\bump_mine`, imported with `run_fixrefs.bat ba_jail_keimusho`
  (`maps/ba_jail_keimusho_fix_refs.txt`); sounds `sounds/bumpmine/` + `keimusho.bumpmine.land/detonate` events.
- **Radar** 2048 px (`radar.py` size 2048 + `radar_props.py`): textures from the map's embedded VTFs, 3201 props drawn from their CS:GO models
  (embedded + CS:GO pak01 chunks 033/053/065/068/072/073/088/092/101/105/109), roofs/ceilings/canopies left out ([`radar_20261031.py`](radar_20261031.py)).
  2 loading slides (generated title + radar art, Way 1 layout). Credits file.
- Scripts are separate files in `maps/scripts/` with their own point_script each (`samuraiscript`, `gravityscript`, `pushscale`, `pushscript`).
- Backup of the vmap before the edit: `maps/ba_jail_keimusho_vmap_backup_20261031.zip`.

## Open

- Not tested in game: all of the above. Build, then check the doors, gun room equips, skipping rope cases, samurai mask (speed/invisibility/mask
  position), water race, rock pushing, push pads, lighting bake, radar alignment (overview scale 5.53).
- Run `run_fixrefs.bat ba_jail_keimusho` before building (bump mine model), then check the mines in game: throw feel, launch strength, the decoy as
  the thrown item.
- Left as found (flagged): `water1` is a `func_water_analog` (not swimmable), `func_physbox` balls ball1-7 can't be pushed by players,
  `mssound` target doesn't exist (v2 too).
- Loading slides are generated art; replace with in-game screenshots when there are some.

## Files

- [`scripts/`](scripts/): the four map scripts. [`fix_20261031.py`](fix_20261031.py): the one-off edit. [`ba_jail_keimusho_fix_log_20261031.txt`](ba_jail_keimusho_fix_log_20261031.txt): its log.
