# mg_monsoon game script

`src/NN_*.js` joined by `tools/build_script.mjs` into `out/addon/maps/scripts/mg_monsoon.js`. Names come from
[CONTRACT.md](CONTRACT.md), rules from [DESIGN.md](DESIGN.md) sections 3 and 6. AI-generated (Claude) for skink52.

Status: **simulated** (mock engine, `tsc`, `api.py --strict`). Nothing here has run in CS2. See "Simulated vs not yet tested".

## HUD contract

The script only talks to the HUD through `hText` / `hClass` / `hSwap` (per-player cache, only changes are sent) on the
`custom_hud_layout` named `mv_hud`. Every panel id and class it uses is in the tables below; `test/mock.mjs` parses these
tables and fails on any id or class that is not listed (and on any listed HUD file id/class that is missing once
`panorama/layout/custom_game/mg_monsoon.xml` and its css exist).

Kinds:
- `text`: a Label whose text is the dialog variable `v` (`text="{s:v}"`); the script calls
  `SetDialogVariableStringForPlayer(slot, id, "v", string)`.
- `class`: the script switches the listed classes on and off independently (`SetHasClassForPlayer`).
- `swap`: exactly one class of the group is on at a time (or none before the first use). `p0..p20` means the 21 classes
  `p0`, `p1`, ... `p20`.

Markers on the artillery board are two nested panels: `<id>` takes class `on` (visible) and one of `x0..x159`
(horizontal position, left to right), its child `<id>y` takes one of `y0..y159` (vertical position, top to bottom).
The board picture is a square, north-up map of x, y in [-6400, 6400] (`CONFIG.BOARD.EXT`, `CONFIG.BOARD.STEPS` = 160):
step `x` = floor((worldX + 6400) / 12800 * 160), step `y` = floor((6400 - worldY) / 12800 * 160).
If `out/hud.json` has `board_steps` / `board_ext` the script uses those instead (nothing else is read from HUDDATA
except an optional `apache` object, see CONFIG guide).

Needles and cards use `a0..a71` = rotation in 5 degree steps clockwise (`aN` = N x 5 degrees).

<!-- HUD-CONTRACT-BEGIN (machine-read by test/mock.mjs: | id | kind | classes | meaning |) -->
| id | kind | classes | meaning |
|---|---|---|---|
| mv_brief | class | show | briefing card (lobby, before deploying) |
| mv_brief_role | text | | role name |
| mv_brief_l1 | text | | briefing line 1 |
| mv_brief_l2 | text | | briefing line 2 |
| mv_brief_l3 | text | | briefing line 3 |
| mv_brief_spawn | text | | chosen deploy point ("DEPLOY: BASE  [R] next") |
| mv_brief_count | text | | countdown + chat hints |
| mv_info | class | show | role / help card (chat commands) |
| mv_info_title | text | | card title |
| mv_info_l1 | text | | card line 1 |
| mv_info_l2 | text | | card line 2 |
| mv_info_l3 | text | | card line 3 |
| mv_info_l4 | text | | card line 4 |
| mv_info_l5 | text | | card line 5 |
| mv_info_foot | text | | card footer |
| mv_banner | class | show | big banner after deploying / round end |
| mv_banner_title | text | | banner title |
| mv_banner_sub | text | | banner subtitle |
| mv_toast | class | show | short message, lower centre |
| mv_toast_text | text | | toast text |
| mv_prompt | class | show | "[E] ..." interaction prompt |
| mv_prompt_text | text | | prompt text |
| mv_status | class | show | role status box (hidden while flying / on the board) |
| mv_st_role | text | | role + kit name |
| mv_st_l1 | text | | status line 1 |
| mv_st_l2 | text | | status line 2 |
| mv_st_l3 | text | | status line 3 |
| mv_hold | class | show | hold-USE progress (fire mission, gun repair) |
| mv_hold_text | text | | what is being held ("CALLING FIRE MISSION") |
| mv_hold_bar | swap | p0..p20 | progress fill, p20 = complete |
| mv_obj | class | show | objective bar, top centre (always on after the first deploy) |
| mv_flag_a | swap | own_n, own_t, own_ct | flag A owner colour (neutral / T / CT) |
| mv_flag_a | swap | cap0..cap10 | flag A capture progress fill, cap10 = about to flip |
| mv_flag_a | swap | capt_t, capt_ct | which team's colour the progress fill has |
| mv_flag_a | class | contest, here | contest = both teams inside (blink); here = this player is inside its radius |
| mv_flag_b | swap | own_n, own_t, own_ct | flag B, as flag A |
| mv_flag_b | swap | cap0..cap10 | |
| mv_flag_b | swap | capt_t, capt_ct | |
| mv_flag_b | class | contest, here | |
| mv_flag_c | swap | own_n, own_t, own_ct | flag C, as flag A |
| mv_flag_c | swap | cap0..cap10 | |
| mv_flag_c | swap | capt_t, capt_ct | |
| mv_flag_c | class | contest, here | |
| mv_flag_d | swap | own_n, own_t, own_ct | flag D, as flag A |
| mv_flag_d | swap | cap0..cap10 | |
| mv_flag_d | swap | capt_t, capt_ct | |
| mv_flag_d | class | contest, here | |
| mv_flag_e | swap | own_n, own_t, own_ct | flag E, as flag A |
| mv_flag_e | swap | cap0..cap10 | |
| mv_flag_e | swap | capt_t, capt_ct | |
| mv_flag_e | class | contest, here | |
| mv_tk_t | text | | T tickets (number) |
| mv_tk_t | class | bleed | T is bleeding tickets (enemy holds 3+ flags) |
| mv_tk_ct | text | | CT tickets (number) |
| mv_tk_ct | class | bleed | CT is bleeding tickets |
| mv_tkbar_t | swap | w0..w20 | T ticket bar width, w20 = full |
| mv_tkbar_ct | swap | w0..w20 | CT ticket bar width |
| mv_clock | text | | conquest clock "mm:ss" |
| mv_fly | class | show | helicopter instruments (anyone aboard) |
| mv_fly | swap | seat_pilot, seat_gunner, seat_rider | which seat this player has (pilot = all instruments; gunner/rider = reduced) |
| mv_ai_roll | swap | a0..a71 | artificial horizon roll (rotation of the horizon card; a0 = level) |
| mv_ai_pitch | swap | pit0..pit20 | artificial horizon pitch, 2 degrees per step, pit10 = level, pit20 = 20 degrees nose up |
| mv_n_asi | swap | a0..a71 | airspeed needle (a0 = 0, full scale 300 degrees = 100 km/h... see CONFIG.HUD.ASI_MAX_KMH) |
| mv_n_alt | swap | a0..a71 | radar altimeter needle (one turn = 100 m) |
| mv_n_vsi | swap | a0..a71 | vertical speed needle (a0 = level, +-135 degrees = +-10 m/s; a45..a71 = descending) |
| mv_hdg | swap | h0..h71 | heading tape position, hN = heading N x 5 degrees (0 = north) |
| mv_hdg_txt | text | | heading "045" |
| mv_alt_txt | text | | radar altitude in metres |
| mv_spd_txt | text | | airspeed km/h |
| mv_heli_hp | swap | hp0..hp20 | airframe health bar, hp20 = 100 |
| mv_rtb | class | on | low-health "RTB" lamp |
| mv_rkt_txt | text | | rockets left ("RKT 28" / "RE-ARM" / "") |
| mv_seat_1 | text | | seat list line 1 ("PILOT  name") |
| mv_seat_1 | class | me | this line is the player's own seat |
| mv_seat_2 | text | | seat list line 2 |
| mv_seat_2 | class | me | |
| mv_seat_3 | text | | seat list line 3 |
| mv_seat_3 | class | me | |
| mv_seat_4 | text | | seat list line 4 |
| mv_seat_4 | class | me | |
| mv_seat_5 | text | | seat list line 5 |
| mv_seat_5 | class | me | |
| mv_seat_6 | text | | seat list line 6 |
| mv_seat_6 | class | me | |
| mv_fly_info | text | | one line under the instruments (warnings, pad repair / re-arm state) |
| mv_gun | class | show, hot | gun heat box (door gun, chin gun, mounted gun); hot = overheated, locked out |
| mv_gun_name | text | | gun name ("M2 .50 CAL") |
| mv_gun_heat | swap | ht0..ht10 | heat bar, ht10 = overheated |
| mv_board | class | show | artillery plotting board (full-screen map + read-outs) |
| mv_board | swap | lay_idle, lay_laying, lay_laid, lay_disabled | state lamp of the player's gun |
| mv_ret | class | on | marker: the reticle the player moves |
| mv_ret | swap | x0..x159 | |
| mv_rety | swap | y0..y159 | |
| mv_lock | class | on | marker: locked target of the player's gun |
| mv_lock | swap | x0..x159 | |
| mv_locky | swap | y0..y159 | |
| mv_cep | class | on | predicted 50 % circle; make it a child of mv_locky, centred on the lock |
| mv_cep | swap | cep0..cep8 | circle radius: cepN = (N + 1) x 60 world units (scale to board pixels: board px / 12800 per unit) |
| mv_gpos | class | on | marker: the player's own gun |
| mv_gpos | swap | x0..x159 | |
| mv_gposy | swap | y0..y159 | |
| mv_imp0 | class | on | marker: last impact of the player's gun |
| mv_imp0 | swap | x0..x159 | |
| mv_imp0y | swap | y0..y159 | |
| mv_imp1 | class | on | marker: impact before that |
| mv_imp1 | swap | x0..x159 | |
| mv_imp1y | swap | y0..y159 | |
| mv_imp2 | class | on | marker: oldest impact shown |
| mv_imp2 | swap | x0..x159 | |
| mv_imp2y | swap | y0..y159 | |
| mv_msn0 | class | on, sel | marker: fire mission 1 of the team (sel = the one RELOAD selected) |
| mv_msn0 | swap | x0..x159 | |
| mv_msn0y | swap | y0..y159 | |
| mv_msn1 | class | on, sel | marker: fire mission 2 |
| mv_msn1 | swap | x0..x159 | |
| mv_msn1y | swap | y0..y159 | |
| mv_msn2 | class | on, sel | marker: fire mission 3 |
| mv_msn2 | swap | x0..x159 | |
| mv_msn2y | swap | y0..y159 | |
| mv_msn3 | class | on, sel | marker: fire mission 4 |
| mv_msn3 | swap | x0..x159 | |
| mv_msn3y | swap | y0..y159 | |
| mv_msn4 | class | on, sel | marker: fire mission 5 |
| mv_msn4 | swap | x0..x159 | |
| mv_msn4y | swap | y0..y159 | |
| mv_fl0 | class | on, sel | marker: counter-battery flash 1 (an enemy gun fired here) |
| mv_fl0 | swap | x0..x159 | |
| mv_fl0y | swap | y0..y159 | |
| mv_fl1 | class | on, sel | marker: flash 2 |
| mv_fl1 | swap | x0..x159 | |
| mv_fl1y | swap | y0..y159 | |
| mv_fl2 | class | on, sel | marker: flash 3 |
| mv_fl2 | swap | x0..x159 | |
| mv_fl2y | swap | y0..y159 | |
| mv_fl3 | class | on, sel | marker: flash 4 |
| mv_fl3 | swap | x0..x159 | |
| mv_fl3y | swap | y0..y159 | |
| mv_b_range | text | | "RANGE 1240 m" (gun to reticle) |
| mv_b_grid | text | | "GRID F7  LOCKED" |
| mv_b_gun | text | | "GUN 2  LAID" / "LAYING 1.2s" / "DISABLED 31s" |
| mv_b_shell | text | | "LOADED: HE" / "LOADED: 3 ROCKETS" / "EMPTY" |
| mv_b_state | text | | what to do next ("READY - MOUSE1 / SPACE TO FIRE") |
| mv_b_msn | text | | selected mission ("MISSION 2/3  p14  F7  32s") |
| mv_b_stats | text | | "ROUNDS 12  HITS 3  MISSIONS 2" |
<!-- HUD-CONTRACT-END -->

Total: 103 panel ids (CS2 limit 1024 per layout).

Layout hints (not checked by the mock): `mv_obj` top centre under CS2's round timer; `mv_fly` bottom centre; `mv_gun`
bottom right; `mv_status` bottom left above CS2's health; `mv_board` centred, about 70 % of the screen height, read-outs
in a column on its right; `mv_hold` centre, under the crosshair; `mv_brief` / `mv_info` / `mv_banner` as mg_trenchwarfare's.

## Structure

Build: `node tools/build_script.mjs` joins `src/NN_*.js` in name order under one import line and bakes in
`const LAYOUT = <out/layout.json>` and `const HUDDATA = <out/hud.json, or {}>`. Source files must not import anything.

| File | Holds |
|---|---|
| `00_config.js` | `VERSION`, the one `CONFIG` object |
| `10_util.js` | vectors, angle bases (`angleBasis`, `anglesFromBasis`, `anglesNear`), entity cache (`ent`, `need`, `fire`), HUD cache (`hText`, `hClass`, `hSwap`), effect pools, tracers, smoke screens, `hitscan`, `groundZ` / `approxGround` |
| `20_players.js` | player state `P(slot)`, roles (`chooseRole`, `requestRole`), kits and the AT rocket trigger, uniforms, deploy points, `deploy` |
| `30_heli.js` | helicopters: pose to entities, seats and cameras, boarding / leaving / fast-rope, shared gun code (heat, tracers), rockets, damage, crash, wreck, respawn, the flight model `tickHeli` |
| `40_arty.js` | guns (laying, loading, firing, recoil, disable / repair), shells, `blast` (damage + assist split), fire missions, the plotting board, crew stations |
| `50_mounted.js` | emplaced guns |
| `60_conquest.js` | flags, tickets, bleed, round end and its fallbacks |
| `70_hud.js` | role cards, objective bar, instruments, board, status box |
| `80_ambient.js` | occasional far-off cosmetic burst |
| `85_ai.js` | bot director, AI pilot / gunner / battery crew, infantry bot deploy choice and leash (DESIGN lists bots under `90_main`; split out for size) |
| `90_main.js` | roster, think loop (try/catch per player and per helicopter, `SetNextThink` first), events, chat, damage guard, per-minute script-time log, `globalThis.__mvDebug` |

One think per tick: load points (first tick of a round) -> roster -> AI director and AI pilots' stick inputs -> every player
(keys, seats, stations, HUD) -> helicopters -> guns, shells, rockets, tracers, missions, flags (4 Hz), tickets, ambience.

Things worth knowing:
- All helicopter offsets are in the nose frame (x forward, y left, z up, origin on the ground under the mast). The model's
  own nose direction (`NOSE_YAW`, Apache -90) is applied only when entity angles are written.
- The height of a helicopter's origin over its pad and the Hip's rotor / tail hub positions are measured from the map
  entities at round start, so the map decides them; CONFIG values are the fallback.
- Hits on helicopters by script weapons are sphere tests (`HELI.HIT_RADIUS`), not engine collision; player bullets arrive
  through `OnBulletImpact` and need the prop to have collision.
- **A script cannot read entity keyvalues**, so the `message` of `mv_mountinfo_N` never reaches it directly. The build copies
  those keys from `out/entities.json` into `LAYOUT.mountinfo` when the dump has a `message` field (today's
  `tools/dump_entities.py` does not write one), a `mounts` list in layout.json also works, and otherwise a mount's team
  is its base within `MOUNT.BASE_RADIUS` (else anyone) and its kind m2 (CT) / dshk.
- Optional entities, used when present and not in CONTRACT: `mv_flag_snd_<a..e>` (point_soundevent, `StartSound` on capture).
  `mv.capture`, `mv.flag_lost`, `mv.radio_blip`, `mv.heli_turbine`, `mv.rocket_fly` have no entity in CONTRACT and are not played.
- Chat: `!infantry !artillery !air` (role now if open, else next respawn), `!rifle !mg !at`, `!roles`, `!spawn <a-e|base>`,
  `!pos`, `!uniform`, `!bots <n>`, and `!swap` = next free seat in a helicopter, or the next kit at an arms rack.
  `/` works as well as `!`.

## CONFIG guide

| Section | What to tune |
|---|---|
| `LOBBY_*`, `ROLES` | briefing time; chance of being drawn into the battery / an air slot |
| `KITS`, `PISTOL`, `AT`, `BULLET_VS_HELI` | weapon classes per team, kit limits (`share`, `per`), the AT rocket, rifle damage to helicopters |
| `UNIFORMS*` | models per team; only applied when an `mv_cache_N` prop holds that model |
| `CONQUEST` | tickets, bleed, capture time, round length, round-end fallbacks |
| `HELI` | flight feel (collective, pedals, cyclic `ACCEL`, tilt), landing limits, collision, crash, pad service, boarding and rope limits, camera, rockets |
| `HELI_MODELS`, `HELI_KINDS`, `WRECK_YAW` | per model: nose yaw, rotor size, seat / exit / pod / gun offsets, gun cone and damage; which model sits on which pad. These are **defaults**: `LAYOUT.models` (written into `out/layout.json` by `tools/mv_models.py` from the models the map was built with; the Apache block comes from `out/apache.json`) overwrites nose yaw, rotor radius, hub / tail hub, seats, exits, pods and the gun's muzzle / camera / cone in `heliModel()`, the pad list in `heliKind()` and the hulk's yaw in `wreckYaw()`. To change a seat or a hub, edit `mv_models.py`, re-run `make_map.py` (or `python -c "import layout; layout.export('../out/layout.json')"` in `tools/`) and rebuild the script. Damage, rate of fire and heat stay in CONFIG. Without a `models` block the old `LAYOUT.apache` / `HUDDATA.apache` route still works |
| gun pivots | `40_arty.js` measures each tube's trunnion from the `mv_tube_*` prop's place on its carriage (fallback `LAYOUT.models.howitzer / rocket .trunnion`); `50_mounted.js` takes the pintle from the `mv_mount_N` origin and the muzzle distance from `LAYOUT.models.<kind>.muzzle` (fallback `MOUNT.MUZZLE`) |
| `ARTY`, `BOARD` | shells, spread, flight time, laying speed, counter-battery, missions, board size |
| `MOUNT` | emplaced gun kinds, cone, heat |
| `POOL` | pool sizes: must match the map |
| `BOTS_ON`, `BOT_QUOTA*`, `AI` | bots on/off and quota (`bot_quota_mode fill`), `MIN_HUMANS_FOR_ROLES`, how many AI pilots / gunners / crews, their reaction times and spread, leash times |
| `CVARS` | server settings sent on activate |

Departures from DESIGN, on purpose: cyclic `ACCEL` 0.7 (design 0.45); rockets re-arm progressively over `REARM_TIME`;
a flag flips straight to the capturing team; nobody aboard a helicopter takes pawn damage (the airframe does); the pilot
can only leave when landed; no pilot ATTACK2 gun (the Apache has a gunner seat); the Hip slick has one door gunner (CONTRACT).

## Tests

```
node tools/build_script.mjs
node test/mock.mjs 32 600      # 22 humans in every role + 10 infantry bots
node test/mock.mjs 4 600       # 4 humans, "!bots 14": AI pilot / gunner / crew must act and yield seats
tsc -p test/tsconfig.json
python create/test/api.py --strict --check projects/monsoon-cs2/out/addon/maps/scripts/mg_monsoon.js   (from cs2mapping)
sh create/test/tscheck.sh projects/monsoon-cs2/out/addon/maps/scripts/mg_monsoon.js
```
Mock switches: `MOCK_NORESTART=1` (CS2 never starts a new round: exercises the FireWinCondition and self-restart path),
`MOCK_TICKETS`, `MOCK_ROUND`, `MOCK_LOG=1`, `DEBUGFLY=<slot>`. The mock uses `out/entities.json` and the real HUD xml/css
when they exist; today it synthesises the entities from layout.json and checks the HUD against the contract above.
The mock runs with 150 tickets and 8 s captures so rounds end inside the run.

## Simulated vs NOT YET TESTED IN CS2

Simulated (mock engine, 11 Nov 2026): role and spawn flow, kits, captures, tickets, round end and both restart paths,
human and AI flight (take-off, patrol, rocket runs, pad landings, repair), boarding, fast-rope, door / chin / emplaced
guns, the battery loop for both sides, fire missions, counter-battery, the bot leash, seat hand-over from AI to humans,
slot reuse, HUD ids. `tsc` and `api.py --strict` clean. Not exercised by the mock drivers: Beehive, the marksman kit,
gun repair by a human, more than one fire mission or two flashes on the board at once.

Not yet tested in CS2 (every item is an assumption):
- `GameRules.TerminateRound` with `mp_ignore_round_win_conditions`, and whether `AddTeamScore` shows on the scoreboard.
- `SetAnimation` on the Apache prop_dynamic; `Skin` on the flag poles; particle `Start` / `Stop` re-triggering.
- Moving a parked pawn (`MOVETYPE_NONE`, scale 0.02) every tick under a `FOLLOW_POSITION` / `CONTROLLED_POSITION` camera
  on a helicopter; restoring the camera parent; what CS2 bots do while parked in a seat.
- `OnGunFire` for `weapon_taser` and re-giving the Zeus.
- Bullets reaching `OnBulletImpact` with the helicopter as `hitEntity` (needs collision on a `model_archetype ""` prop).
- The loader's speed cap by velocity teleport; the rope's fall-speed cap; `pawn.Reset()` in the self-restart path.
- The assist rule behind the loader / observer damage share (inherited from mg_trenchwarfare, unverified there too).
- Flight feel, and AI altitude over the real terrain: layout.json has no height samples, so `approxGround` guesses from the
  bases and the karst list, backed by a look-ahead trace; a `LAYOUT.terrain = { x0, y0, cell, nx, ny, z[] }` grid is used if exported.
- Script time on a server: the mock measured about 0.1 ms/tick at 32 players, its own traces included.
