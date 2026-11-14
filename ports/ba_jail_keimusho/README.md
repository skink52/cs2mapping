# ba_jail_keimusho

| | |
|---|---|
| Status | Ported (v3 import, skink52's Hammer work on top); fixes 2026-10-31 awaiting build + in-game test |
| Source BSP | `ba_jail_os_keimusho_v3` (imported); `ba_jail_os_keimusho_v3.bsp` and `_v2.bsp` are in `C:\source1\bspsrc-windows\bsp's` |
| Original map | Crycelia |
| Imported | 2026-10-07 |
| Map last changed | 2026-11-07 |
| How | Valve importer, Hammer by hand, then a one-off fix script ([`fix_20261031.py`](fix_20261031.py)) |

Loading text: `Map by Crycelia` / `CS2 Port by skink52 for Slime Servers`.

**Shareable bump mine kit** ([`bumpmine_kit/`](bumpmine_kit/), 2026-11-08): this map's bump mines packaged for any CS2 map, with agent
setup instructions, a Hammer prefab and a `.vmap` installer. `python bumpmine_kit/make_kit.py` builds `cs2_bumpmine_kit.zip`, copying the
Valve model, materials and sounds in from the content addon at build time (they stay out of git). The kit has no HUD charge count.

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
- **Cell doors `celldoor2`** (2026-11-02): 6 func_movelinears shared the name and 6 celldoor props were parented to it, and CS2 logged "unrecognized parent". The compile dropped the movelinears. Cause: `movedir "0 90"` (2 numbers); set to `0 90 0`, confirmed working. Not Solid was also cleared on the way (the clip face is now solid, matching the prop); also renamed `celldoor2_1..6`, each prop parented to its door, the two func_button outputs (Open/Close) split into one per door.
- **trigger_push** (4, speeds 350/700) → trigger_multiple + `keimusho_push.js` push zones. 2026-11-01: rewritten to CS:GO base velocity (players run/strafe on top of the push, momentum kept on exit, the 700 up-pushes over the slide-game boxes are near-zero gravity instead of a launch); the old set-speed version made the slide game's box jumps impossible. 2026-11-02: horizontal slide pushes lowered 350 → 150 (skink52); func_conveyors tried instead didn't push, triggers restored.
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
  (embedded + CS:GO pak01 chunks 033/053/065/068/072/073/088/092/101/105/109), roofs/ceilings/canopies left out ([`radar_20261031.py`](radar_20261031.py)). 2026-11-02: water (7 func_water volumes) added as see-through blue.
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

## 2026-10-31, third pass

- **env_fire** (24: fire game fire1-20, roulette deathfire1-4) doesn't burn in CS2 (skink52, seen on ttt_minecraft) -> info_particle_system with a generated
  flame particle `particles/port_fire/fire_96.vpcf` (new `tools/firefx.py`); 90 StartFire/Extinguish/Disable -> Start/Stop, 24 Enable outputs dropped.
- **Vis** (the map had no hints): `visfit_detail` (new): 12 Medium over the busiest enclosed cells, 193 Low over enclosed walkable space, 176 Lower over
  open-sky play areas and air above the walkable band, one Lowest over everything else (1,702 open cells with nothing standing in them stay Lowest).
- Stock materials confirmed present by skink52 (the map reports no missing textures).

## 2026-11-01

- `maps/ba_jail_keimusho_fix_refs.txt` rewritten in the `importfilelist` format. The imported `models/weapons/w_eq_bumpmine_dropped.vmdl` didn't compile
  (bodygroup choices with no name): choices named `studio`, and `glow` = `on` (default, mines glow) / `off`. Original kept as `.vmdl.bak`.
- Bump mines stopped appearing after the first round: the script kept the round-1 `bumpmine_N` entities (map entities are re-created each
  round). The pool is now re-found whenever an entry is invalid, and reset on round start.
- Still not working (reported): the thrower now comes from the projectile (`GetThrower`; with one decoy the weapon has no owner by the time
  OnGrenadeThrow fires), a landing fallback (decoy at rest or 3 s without a bounce event), and a `bump_debug` toggle (RunScriptInput or cheat
  command) that prints every give/throw/landing; `bump_on` cheat command for testing.
- In game: "no bumpmine_1..8 props found": the pool props parked under the map (z -1064, outside the playable world) weren't there at runtime.
  Moved (with their point_soundevents) into the bump arena at -2144 -4544 -73, renderamt 0; the script shows a mine with alpha 255 and
  hides it again when parked.
- Real cause (build log): the compile DELETES a prop_dynamic whose model has prop_data. Removed the prop_data block from
  `w_eq_bumpmine_dropped.vmdl`. (The move into the arena stays; it does no harm.)
- Fire game lit everything at once: `firerelay` sent `firetimer` a `RefireTime` with an empty value 1 s after start (in the original v3 too),
  read as 0 in CS2. Output removed: 2 random fires (one from fire1-10, one from fire11-20) every 8 s; each fire's button (`fireNbrush`, at the
  fire, +use) puts it out.

## 2026-11-02 (skink52's own fixes in Hammer)

- **Slide box jumps:** with both pushes scripted, the up push sped players forward too, so the jumps couldn't be made in time. The two up pushes are now
  real CS2 `trigger_push` (speed 40, pushdir 270 0 0, spawnflags 4097, smaller boxes over the jumps); the script keeps `PushIn_1` and `PushIn_3` (forward, 150).
  Cause found afterwards: the script's ground-friction undo over-compensated on the low-friction slide. Fixed in `tools/push_tail.js` and stage C for future ports;
  this map's own `keimusho_push.js` still has the old code but no longer has up pushes.
- **Vis:** a Medium hint over the slide entrance / upstairs platform jump (x -2488..-500, y 776..2516, z 504..776) replaces a Lower box at z 896.
  Props there popped out of view across the long open stretch. `visfit.py` now does the same in thin stretches.
- **Rope:** the CS:GO `move_rope` pair rope3/rope4 (cable/rope2, -384 -1813 301 → 450) is now two `grapplinghook_rope_end_01` props tinted 240 179 94 at z 279 and 447
  (the top one flipped), next to the imported invisible ladder.
- Lighting: 2 light_omni2 and 7 env_combined_light_probe_volumes around -660 464 adjusted or added; 2 func_conveyors removed.

## 2026-11-05

- **Bump mine HUD stuck on screen round to round.** Cause: the script only sends HUD changes, and the round-start reset cleared its "last sent" cache,
  so the hide that followed looked like no change and was never sent; whoever held the decoy at round end kept the card. Now: the card shows once per
  player per round for at most 5 s (ends sooner if they stop holding the decoy, leave the arena or die), and every slot is hidden explicitly on round
  start (again 0.5 s and 2 s later, once the new round's HUD entity exists), round end, bump_off, death, spawn, connect and disconnect. Checked with
  tsc, the mock engine and a targeted round/death/timeout simulation; not yet seen in game.
- **Vis: every hint Medium** (skink52 still saw props popping in and out). The 381 visibility_hints (14 Medium, 192 Low, 174 Lower, the Lowest over the
  whole map) all set to Medium, so the whole map is Medium; compile time traded for robustness. Backup: `maps/ba_jail_keimusho_vmap_backup_20261105.zip`.
- Built with `build_maps.ps1 final ba_jail_keimusho` (new mode: full build, 2048 lightmaps, VRAD quality 2): OK in 70.6 min, vpk 152 MB.
  Vis: 586,031 regions, 31,697 clusters merged to 16,384 (the cap); boundary ray pass 25 min, large-cluster pass 14 min.

## 2026-11-07

- **Fire game hurt after it was stopped / with no fire.** The stop button `fireoff` disabled (and unswept) only `firehurt1-10`; `firehurt11-20`
  stayed enabled while their particles were stopped, so the right half (x -1972..-1405) kept doing 4 dps with nothing visible until round end.
  A fire picked just before Stop also enabled its hurt 2 s later (the `firecase1/2` outputs are delayed 2 s). `fireoff` now sends, at 0 s and
  again at 2.5 s, Disable + `Unsweep_firehurtN` + `fireN` Stop + `fireNbrush` Lock for all 20 (old duplicate fire outputs removed)
  ([`fix_20261107_firegame.py`](fix_20261107_firegame.py)). Backup: `maps/ba_jail_keimusho_vmap_backup_20261107.zip`. Not yet tested in game.
- Each `firehurtN` covers its whole half of the room (as in CS:GO), not just the spot around `fireN`: while any fire in a half is burning,
  everyone in that half takes 4 dps (stacking per fire). **Intended, keep it:** it's a team game, and each half (fire1-10 / fire11-20,
  `firecase1` / `firecase2`) is its own game container; only `firebrush`, which locks players in, spans both (skink52).
- Built (final, 10 threads, CS2 open alongside): OK in 49.3 min, 1,125 compiled, 0 failed; vpk 159,391,550 bytes copied into `game\`.
- Bump mine HUD: text and charge count centred as one group in a card that fits its contents ([`panorama/keimusho_bump.css`](panorama/keimusho_bump.css)).

## 2026-11-08: built without vis

- **Player bodies invisible around the cell block** (skink52, spectating and in third person): the body vanished while the held weapon stayed,
  only at some view angles (the same setpos switched with the camera angle), mostly with the camera at grass level in the courtyard between the
  cell rows, or high above it. It happened with Medium hints everywhere and again with a High (8-unit) hint over the cell block
  (x -1944..-280, y -1558..302, z -22..394). `vis_enable 0` brings the bodies back; `vis_debug_lock 1` showed the world itself isn't culled,
  and the `vis_debug_*` commands print nothing. Nothing solid lies between body and camera (the courtyard is open air up past z 340), and in vis
  terms the whole map is open to the void (88% of its vis geometry is nodraw), so the bad cull couldn't be pinned to one surface.
- Fix: keimusho is built **without `-vis`** (`$NoVis` in `scripts/build_maps.ps1`). FPS with `vis_enable 0` checked fine across the map by
  skink52. Cost: no PVS, so the server sends every player everywhere (wallhacks see more). Vis was also most of the build time:
  final build without vis (2048 lightmaps, quality 2, 10 threads) 15 min against 49 min with it; vpk 153,628,119 bytes, no
  `world_visibility.vvis_c` inside (checked). **Confirmed in game by skink52:** bodies stay visible around the cells.
- Entity-only / lighting builds start from the current .vpk, so they keep whatever vis it has: do one full or final build first.
- **Fire game hurt with all fires out** (skink52, seen on the fire11-20 side). A case pick starts `fireN` at 0.1 s but enables `firehurtN`
  and unlocks `fireNbrush` at 2.0 s (Sweep at 2.1 s). When a burning fire was picked again and put out inside that window, the late
  Enable/Unlock/Sweep landed after the button's Disable: that half took 4 dps with no fire, and an invisible button stayed usable. Not a designed
  penalty, but the slower side has more fires burning, so more re-picks, so it hit this more often.
  Fix ([`fix_20261108_firebuttons.py`](fix_20261108_firebuttons.py)): a `logic_branch` `fire_litN` per fire. A pick sets it with the Start
  (0.1 s) and Tests it at 2.0 s instead of enabling directly; OnTrue enables the hurt, unlocks the button, sweeps and (re)starts the fire;
  OnFalse stops all four. The button clears it and Tests again at 0.15 s; `fireoff` clears all 20 at 0 and 2.5 s. `fire2brush`/`fire3brush`
  now lock themselves. (A first try, the button repeating its stop 2.15 s later, failed the mock below: up to 2 s of fire-less damage,
  and a fire re-picked just after being put out lost its flames but kept its hurt.)
  **Mock-tested** with [`mock_firegame_io.py`](mock_firegame_io.py), which runs the map's own outputs from the .vmap through entity models
  with simulated fast/slow teams and fireoff, plus scripted re-pick races, and with same-tick outputs in random order (`--shuffle`).
  Pre-fix map: 3,653 s of fire-less damage in 20 games, longest 183 s. Fixed: none, apart from one 0.05 s blip when a press lands in the very tick of
  the 2 s test (settled by the 0.15 s Test). Backup: `maps/ba_jail_keimusho_vmap_backup_20261108.zip`. Needs an entity build; not tested in game.

## 2026-11-14: water physics

`watersplit`: 5 func_water meshes over 384 u cut into 104 closed pieces. CS2 gives a func_water mesh over ~500 u no physics hull, so that
water could not be swum in. Entities-only rebuild (0.7 min): no hull failure on the cut water. **Two pools still have no hull** (meshes 8018 and
8022): their tops are displacements (subdivision meshes), which the cut leaves whole. Backup `ba_jail_keimusho.vmap.bak_watersplit_20261114_*`.
Compiled, not checked in game.

Later the same day (flat displaced tops): the two pools (8018, 1,568 x 1,681 x 90 u, `hr_aztec_water_shallow`; 8022, 346 x 998 x 16 u,
`anubis_water_canal`) have an all-zero displacement, and CS2 gives a subdivided func_water mesh no hull at any size, so `split_volumes` dropped
their subdivision and cut them into 25 and 3 closed pieces. Entities-only rebuild (about 1 min): **0 func_water hull failures**. Backup
`ba_jail_keimusho.vmap.bak_waterflat_20261114_161926`. Compiled, not checked in game.
Two hull failures remain, both older than this (in the 7 Nov builds) and not water: node 8117, a 1-u-thick `toolstrigger` sheet in the
trigger_teleport over the water-race pool (entity 8095), and node 8247, the 1-u-thick trigger_hurt `parkourthurt` (9595). A trigger with no hull
may never fire: check both in game.

## Open

- Not tested in game: all of the above. Build, then check the doors, gun room equips, skipping rope cases, samurai mask (speed/invisibility/mask
  position), water race, rock pushing, push pads, lighting bake, radar alignment (overview scale 5.53), fire particles (look/size), vis compile time and pop-in.
- Run `run_fixrefs.bat ba_jail_keimusho` before building (bump mine model), then check the mines in game: throw feel, launch strength, the decoy as
  the thrown item.
- Left as found (flagged): 2 placed `weapon_tagrenade` (not in CS2, they spawn nothing); `skippingpole` rotating sound `Concrete.ScrapeSmooth` relies on
  CS2 having that stock soundevent; `func_rotating`/`func_tanktrain` untouched.
- Loading slides are generated art; replace with in-game screenshots when there are some.

## Files

- [`scripts/`](scripts/): the four map scripts. [`fix_20261031.py`](fix_20261031.py): the one-off edit. [`ba_jail_keimusho_fix_log_20261031.txt`](ba_jail_keimusho_fix_log_20261031.txt): its log.
