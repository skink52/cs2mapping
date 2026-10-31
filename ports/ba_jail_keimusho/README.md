# ba_jail_keimusho

| | |
|---|---|
| Status | Ported (v3 import, skink52's Hammer work on top); fixes 2026-10-31 awaiting build + in-game test |
| Source BSP | `ba_jail_os_keimusho_v3` (imported); `ba_jail_os_keimusho_v3.bsp` and `_v2.bsp` are in `C:\source1\bspsrc-windows\bsp's` |
| Original map | Crycelia |
| Imported | 2026-10-07 |
| Map last changed | 2026-10-31 |
| How | Valve importer, Hammer by hand, then a one-off fix script ([`fix_20261031.py`](fix_20261031.py)) |

Loading text: `Map by Crycelia` / `CS2 Port by skink52 for Slime Servers`.

## v2 vs v3

Update (later on 31 Oct): with the v3 BSP on the PC the vmap matches v3 exactly apart from the outputs the importer dropped (the door pairs
below), so nothing in the vmap is a later addition; the v2 notes below are kept for history.

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
  player within 36 u is launched (900 u/s away, 750 up) with the detonate sound. Mines expire after 60 s / round start. Only while the game is on (start
  button → `bump_on` at 3 s, end button → `bump_off`) and inside the arena box, so spleef's decoys stay decoys. In the hand it's a decoy; in flight the
  decoy is hidden (alpha 0) and a pooled mine follows it, spinning. HUD: `custom_hud_layout bumphud` ([`panorama/`](panorama/)) shows "BUMP MINE READY -
  MOUSE1 THROW" + charges while the player holds the decoy in the arena. Model: CS:GO files written loose
  into `csgo\models\weapons` + `csgo\materials\models\weapons\v_models\bump_mine`, imported with `run_fixrefs.bat ba_jail_keimusho`
  (`maps/ba_jail_keimusho_fix_refs.txt`); sounds `sounds/bumpmine/` + `keimusho.bumpmine.land/detonate` events.
- **Radar** 2048 px (`radar.py` size 2048 + `radar_props.py`): textures from the map's embedded VTFs, 3201 props drawn from their CS:GO models
  (embedded + CS:GO pak01 chunks 033/053/065/068/072/073/088/092/101/105/109), roofs/ceilings/canopies left out ([`radar_20261031.py`](radar_20261031.py)).
  2 loading slides (generated title + radar art, Way 1 layout). Credits file.
- Scripts are separate files in `maps/scripts/` with their own point_script each (`samuraiscript`, `gravityscript`, `pushscale`, `pushscript`).
- Backup of the vmap before the edit: `maps/ba_jail_keimusho_vmap_backup_20261031.zip`.

## 2026-10-31, second pass (v3 BSP)

- Lights re-matched to the v3 `_light` values (132 of 132 matched; v2 had only matched 72); lightcover's 27 added lights set to the v3 median.
- **Climb balls** `ball1-7` (func_physbox, spawned by `climbtemp1-7`): `ballscript` ([`keimusho_balls.js`](scripts/keimusho_balls.js)) gives a ball the
  player's speed along the contact when a player walks into it (x1.15, min 60 u/s).
- **Triggers enabled with players inside** (CS2 doesn't re-check them): 30 trigger_hurt / trigger_teleport (roulette, fire game, parkour, spleef end
  teleport, skipping rope, bump mine kill plane, water race loser teleport) get `sweepscript Sweep_<name>` 0.1 s after each Enable and `Unsweep_<name>`
  with each Disable ([`keimusho_sweep.js`](scripts/keimusho_sweep.js)): teleports send everyone inside once; hurts damage everyone who was inside at the
  sweep (trigger damage per second, 0.5 s steps) until they leave the box.
- **Door sounds**: the importer dropped noise1/noise2 (22 `doors/wood_gate_open_01`, 4 `pushbardoor_open/close`): 30 point_soundevents started by the
  doors' own outputs, waves from CS:GO. **Button sounds**: 19 buttons with CS:GO `sounds 10` -> `use_sound keimusho.button10`.
- **point_spotlight** (15, importer exclusion list): beams rebuilt as additive func_brush cones (new `tools/spotbeam.py`).
- **Underwater lights**: 24 dim static lights in the three deep water volumes (water race and pools) where no light reached (`watervol.underwater_lights`).
- **Decal** `decals/hr_decals/plaster_stain_10` (stock CS:GO, not in the addon) ported as csgo_static_overlay.
- Script-moved props (`bumpmine_N`, `mask2`): `model_archetype ""`, moved with `Move` (a prop Teleported every tick isn't drawn); mask2 non-solid.
- `slepdoor6` opener added (missed in the first pass). `map_asset_references` += spotlight vmat, bump mine vmdl, bump HUD layout.
- Checked, nothing to do: `water1` (func_water_analog) has no mesh and nothing moves it, and a func_water already covers that pool; displacements (1,388
  in v3) are in the vmap; the 5 overlays have real sizes; ssbump normals were already converted; foliage alpha test / backfaces and the lantern self-illum
  are set; no `msmusic`/`mssound` entity exists in v3 either (the knife trigger's PlaySound target never existed).
- Validation script: [`validate_20261031.py`](validate_20261031.py) (every RunScriptInput has a script input, no missing targets, v3 output diff,
  dead classes, equips, renderamt, lights, probe coverage). All 7 scripts pass tsc + the mock engine.

## Open

- Not tested in game: all of the above. Build, then check the doors, gun room equips, skipping rope cases, samurai mask (speed/invisibility/mask
  position), water race, rock pushing, push pads, lighting bake, radar alignment (overview scale 5.53).
- Run `run_fixrefs.bat ba_jail_keimusho` before building (bump mine model), then check the mines in game: throw feel, launch strength, the decoy as
  the thrown item.
- Left as found (flagged): 2 placed `weapon_tagrenade` (not in CS2, they spawn nothing); `skippingpole` rotating sound `Concrete.ScrapeSmooth` relies on
  CS2 having that stock soundevent; `env_fire` (24, fire game) not yet seen working in CS2; `func_rotating`/`func_tanktrain` untouched.
- Stock CS2 materials the vmap uses that couldn't be checked without CS2's VPK: cs_italy/black, cs_italy/cr_miscwood2b, cs_italy/hpe_plaster_wall_red,
  wood/plywood02, de_train/train_metalceiling_02, de_mirage plaster_brick4, hr_dust_plaster_06, hr_massive/wood_planks_1, terracotta_pot_02 (model).
- Loading slides are generated art; replace with in-game screenshots when there are some.

## Files

- [`scripts/`](scripts/): the four map scripts. [`fix_20261031.py`](fix_20261031.py): the one-off edit. [`ba_jail_keimusho_fix_log_20261031.txt`](ba_jail_keimusho_fix_log_20261031.txt): its log.
