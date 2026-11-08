# cs2-slop-porting recheck, 8 Nov 2026

> **AI-generated.** Written by Claude for skink52's pipeline. Earlier rechecks (29 Oct, 30 Oct, 2 Nov) are summarised in
> [external-tools.md](external-tools.md).

What was read: [Ninja-Chris/cs2-slop-porting](https://github.com/Ninja-Chris/cs2-slop-porting) at commit `8b94235` (8 Nov 2026):
`vmap_asset_slop_import.py` and `scripts/hurt_zone.js`, `player_velocity.js`, `push_mass.js`. Our last recheck was 3.5 / 2026-11-02a
(commit `949e104`). Nothing of theirs was copied into our tools; what we took is written fresh (the repo is MIT, Ninja-Chris and skink52).

## State of their script

- The committed file is two versions pasted together. Lines 1–18360 are the new 2026-11-08g; the rest is 2026-11-04b with its header cut
  off, so the file stops with a SyntaxError at line 18361 and **doesn't run as published** (lines 1–18360 alone parse).
- The author's own commit notes: "push and physbox changes are broken. don't use them" (`8b94235`), "script will break props. use
  original version" (`f4b5236`, push_mass.js v8), "vis has issues and laser / tesla untested" (`51342f0`).
- It bundles copies of our modules (dmx, kv2, vmapedit, lighting, visfit, probes, splitfaces). kv2 is identical; dmx, lighting and
  visfit are older than ours. Their splitfaces adds the Hammer crash fix below, their vmapedit two speed-ups.

## Taken (checked offline, in the pipeline since 8 Nov 2026)

| What | Evidence | Where |
|---|---|---|
| Open edges at "bowtie" corners (separate fans of faces meeting at one vertex) linked fan to fan. Linked back to their own fan, the mesh crashes Hammer on load (theirs: mg_divine, mg_hellz). | Valve's importer links all 4,453 such corners in 6 of our ports fan to fan, and none of our 81 vmaps has the other kind. Our `mesh_write` picked by index and turned most into the crash pattern when it re-wrote a mesh (ttt_island 73 of 75, mg_n64_goldeneye 1,096 of 1,116, mg_mario_party 135 of 161). After the fix: 505 re-written meshes in 4 maps all fan to fan, `mesh_check` clean, and the relink changes nothing in untouched importer meshes. Plausibly the cause of ba_jail_skylight's "post load fixup" crash (3 Nov). | `splitfaces.link_bowties`, called by `mesh_write` (used by `splitfaces` and `trigsplit`) |
| info_particle_system naming a CS:GO particle system (`effect_name dust_embers`) → CS2's particle of the same name. | The import logs say "Failed to find source 2 file for particle system …", the build logs "FixupResourceName: Illegal path, missing extension". 187 such entities in our ports (151 on mg_antique_course, 16 mg_jahoukarail_2015, 15 ttt_cg_skyscraper_2017); all 20 names are in csgo/pak01, one path each. No guessed stand-ins (theirs swaps fire → env_fire_small). | stage C / D `particles` (`tools/particles.py`) |
| Default door move sound: a func_door / func_door_rotating with an empty (or `0`) noise1 played `DoorSound.DefaultMove` / `RotDoorSound.DefaultMove` in CS:GO. | Source SDK 2013 `CBaseDoor::Precache`; CS:GO's `game_sounds_world.txt` defines both as `~doors/default_move.wav` (no loop points) at volume 0.2, the arrive defaults as `common/null.wav`. CS2 has neither name (182 of its 183 soundevent files read). All 19 doors on mg_insomnia_course and 19 of 55 on mg_n64_goldeneye relied on it (only 11 of our ports' VMFs are on the PC, so the full count is unknown; 300 doors in our vmaps have an empty noise1, the ones with their own sound included). | stage C `doors` (+ `soundscripts`), made rerun-safe: no doubled outputs, `port_door_N` never reused, doors named by an earlier run still match |
| `rendermode` as CS2's names. | CS2's `RenderMode_t` has three values: the 5 Nov 2026 server.dll / client.dll contain only `kRenderNormal`, `kRenderTransAlpha`, `kRenderNone` (in that order) and `source1import.exe` only Normal / None; the FGD still lists Source 1's ten. Our ports carry Source 1 numbers 1, 2, 4, 5, 10 (ttt_terrortrain's 6 train windows: 2 at renderamt 170; mg_kohztec_course's `climb_endbutton`, jb_sides_cs2's `vehicle_button5`: 10). How CS2 draws those numbers today is **not checked in game**. | stage C / D `rendermode` (`stage_c.render_modes`): 10 and 6 → None, other non-zero numbers / old names → TransAlpha |

Tests: scratch stage C roots (copies only) of mg_n64_goldeneye, mg_insomnia_course, mg_antique_course and ttt_terrortrain. Only the
intended keys changed, no entity was removed, no output doubled; `trigsplit` on mg_antique_course (12 triggers → 37 pieces) left no
own-fan link and no `mesh_check` problem. Not yet built or tried in game. The ported maps themselves were not changed: to apply the
new steps to one, `run_pass.py <addon> <root> rendermode,particles,soundscripts,doors`.

## Worth doing next (not implemented)

1. **math_counter → logic_case without a script** (`LOGIC_CASE_NUMERIC_FIX`): one logic_compare per case value (SetValueCompare,
   numeric), whose OnEqualTo sends the logic_case InValue with the case's own text. Our gotcha already says those cases never match in
   CS2; our fix is a per-map script (Mario Party `COUNTER_TO_CASE`). jb_renegade has 4 such links (`counter_case`, `counter_case_10`,
   `counter_case_axis`, `counter_case_10_axis`) and its README doesn't mention them. Unverified in game.
2. **Rotating doors opened only by outputs → One-way** (`ROTDOOR_ONE_WAY`): their finding (mg_hellz) is that CS2 swings such a door away
   from the activator handed down the I/O chain, where CS:GO had none and always opened it the positive way. 16 doors in our ports
   (ttt_minecraft 4, mg_awp_submarine 3, mg_jahoukarail_2015 3, ba_jail_lightsout 2, ba_jail_skylight 2, ba_jail_seaside 1, de_rats_1337 1).
   Check one from both sides in game before adding the flag.
3. **AddOutput keyvalue changes rebuilt with plain I/O** (`ADDOUTPUT_FIX`): trigger_teleport `target` (a destination of its own moved by
   point_teleports), `!activator targetname` checked by a filter (AddAttribute + filter_activator_attribute_int), func_conveyor / door
   `speed` (SetSpeed), func_rotating `maxspeed`, trigger_push `speed` (a copy per speed). Our answer so far is cs_script per map. Our ports:
   312 AddOutputs in 9 maps (mg_mario_party 199, already scripted; jb_mangaroons' rotators `speed 3` / `speed 250`; mg_50arenas' 43 add
   outputs, `OnStartTouch>knife>TriggerForActivatedPlayer…`, which their fix doesn't cover).
4. **One cs_mdl_import run per folder** (`MDL_BATCH`): `-nop4 -game csgo -r -i <root> -o <addon> -l <list> -v` for all of a folder's
   models, then one-at-a-time retries for what it didn't write. Saves the ~5 s start-up per model in stage B. Our gotchas: `-l` avoids
   the `-r *.mdl` crash, but one checksum mismatch kills the whole run (hence their fallback). Needs testing under our watchdog.
5. **Source 1 water → its own CS2 water material** (`WATER_CONVERT`): csgo_water_fancy per CS:GO water .vmt, fog colour from `$fogcolor`
   / `$bottommaterial`, fog strength 8 at `$fogend` 300 (1 left piratewars a grey mirror), render backfaces on. We use stock
   `anubis_water_canal` (or waterblend's decompiled stock water). A visual upgrade to tune in game.
6. **Broken stock CS2 assets** (`CS2_CHECK_ASSET_REFS`): stock vmat_c whose textures are in no CS2 VPK, and stock vmdl_c using missing or
   stub materials, ported from CS:GO. Extends `vmap_refs.py`'s stub list (error-shader vmats only).
7. **Fire damage by CS:GO's own model** (`hurt_zone.js` fire zones: damage from size / heat / damagescale, a growing box, no damage
   through walls; laser zones per CS:GO's BeamDamage). Our env_fire gets a 2/s trigger_hurt, twice CS:GO's measured 1/s (CS2's lowest).
8. **Geometry repairs**, each high effort: `FACE_RESTORE` (faces lost because the importer's compile treats clips, glass and water as
   solid: walls behind npc clips, floor strips under clips that leak light, pockets behind glass; rebuilt by vbsp's cutting rules; our
   `culled` only covers axis-aligned boxes under water), `ENTITY_COPY_FIX` (world copies lying exactly on brush entities with no origin
   key: func_conveyors that never push, func_breakable_surf windows doubled by panes that don't break; our `origindup` only finds
   copies at the origin), `CRACK_FIX` (hairline cracks lined up on the VMF planes, positions only, like `meshweld.py`), `SKEWED_AXIS_FIX`
   (a VMF texture axis off the face's plane: CS:GO projected along it, the importer re-aims it; `facescale` doesn't handle it).
9. **3D skybox shells and lighting**: `restore_skybox_shell` rebuilds the skybox tool boxes whose nodraw sides the importer drops;
   `sync_skybox_lighting` re-copies light_environment and env_sky into the skybox map every run. Compare with `skysplit.py`.
10. **vmapedit speed-ups**: iterative `walk`, and `next_node_id` remembering the highest id instead of scanning every element (22 ms per
    added entity on our 50k-element maps; small).
11. **player_weaponstrip** (not in CS2's FGD) → a blank game_player_equip, Use Only + Strip First, Strip → TriggerForActivatedPlayer.
    One in our ports (ba_jail_keimusho, already scripted).
12. **Equip semantics, skink52's call** (`EQUIP_SPAWN_STRIP`): in CS:GO an equip without Use Only replaced the spawn loadout (an empty one
    stripped the knife too); ours strips only when Strip First is set and gives the missing items on top.
13. **Old weapon names in equips** (weapon_mp5navy → mp5sd, scout → ssg08, m3 → nova, sg550 → scar20, sg552 → sg556, tmp → mp9 …).
    CS:GO itself didn't give these, so low value.

## Their claims, unverified here (check in game before relying on them)

- CS2's func_door ignores SetSpeed and AddOutput speed (`DOOR_SPEED_MOVELINEAR` rebuilds such doors as func_movelinear). CS2's FGD
  lists SetSpeed on doors. None in our ports.
- CS2 doors break from grenades whatever their health, and Valve's maps send SetUnbreakable from a logic_auto (`DOOR_UNBREAKABLE`).
  Valve's compiled entity lumps aren't readable with our KV3 reader (`vmatc.parse`), so not confirmed.
- toolsskybox doesn't stop players (`SKY_PLAYERCLIP` puts a player clip on every sky face); every toolsskybox face can become
  `materials/tools/toolsskybox_occluder.vmat` (`SKY_OCCLUDER`; the material exists in csgo/pak01).
- A func_water parented to a mover doesn't move (only its trigger_hurt rose: mg_hellz).
- func_physbox pieces longer than ~448 u have no collision, nor do open physbox meshes (the author says the physbox changes are broken).

## Not taken

- Ours already: trigger_push script (`push_tail.js`), 2D sky, prefab collapse, 3D skybox split, func_illusionary (stage A makes it a
  func_brush, so the importer never drops it), relight, radar, steam, fire, vis.
- The author says broken: push_mass.js v8, `PROP_MASS_RENAME`, every `PHYSBOX_*`.
- Not needed by our ports: `WEAPON_PROP_SWAP` (our 23 weapon-model props are imported CS:GO models, present in the addons);
  `GENERATED_COMPILE` (our generated particles compile with the map: the game folders have the `.vpcf_c`); `MESH_LINK_FIX` as a pass
  over every mesh (none of our vmaps needs it; the mesh_write fix covers what our tools write); lasers / teslas / spotlights as
  particles (author: untested; ours are func_brush beams and cones).
- Declined before (skink52, 2 Nov): heal trigger conversion (`HEAL_TRIGGERS_TO_SCRIPT`), `MIRRORED_TEXTURE_FIX`, `BRUSH_RENDER_FIX`,
  Source 1 sound falloff, keep_ lights, the missing-entity / seam reports. `PLAYER_VELOCITY_EXAMPLE` (a point_script in every map) for the
  same reason.
