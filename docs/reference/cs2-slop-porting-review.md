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

## Water: CS:GO's look above and below the surface

skink52, 10 Nov 2026: replicating CS:GO's water fog and underwater view is high value if it can be done. Read 10 Nov 2026 from the
script (2026-11-08g, `WATER_*` settings and `_cs2_water_vmat_text`) and CS2's own FGDs. Nothing here is built or checked in game yet.

**What CS:GO did** (Source 1 `Water` shader, keys from the map's .vmt): looking down, what is under the surface fades to `$fogcolor`
over `$fogstart`..`$fogend` units of water and is tinted by `$refracttint`; with the eye under the surface the whole view gets that
fog (linear, same colour and distances) and `$underwateroverlay` warps the screen; the surface is seen from below.

**What we do now**: `water` (stage D, `watervol.py`) puts the meshes in func_water with stock `anubis_water_canal` (or `waterblend`'s
decompiled stock water for 3D-skybox seas), dim lights under the surface, and an underwater post_processing_volume
(`postprocess_filmic_underwater.vpost`, from ba_jail_seaside). That vpost is only a tonemap and bloom: no colour, no fog. So neither
the per-map colour nor the underwater view is carried over.

**What their script does** (`WATER_CONVERT`, on by default, author-tuned on piratewars and tomgreens, not checked by us):
- One csgo_water_fancy material per CS:GO water material, at the same path: `g_vWaterFogColor` = `$fogcolor`,
  `g_flWaterFogStrength` = 8 × 300 / `$fogend` (8 is their "variant B" for CS:GO's solid teal sea; 1 left piratewars a grey mirror),
  `g_vWaterDecayColor` = `$refracttint` at strength 1, `g_flWaterFogShadowStrength` 0 and `g_flUnderwaterDarkening` 0 (Source 1's fog
  was a flat colour, not lit), reflectance 0.02 with Fresnel exponent 5 (Source 1's mix), no caustics, foam or debris.
- `F_RENDER_BACKFACES 1`: the surface is drawn from below, and things above it fade, as in CS:GO. Off, it is invisible from under the
  water and everything above stays sharp.
- CS2's wave textures (`materials/dev/water_substance_soft_normal` / `_height`, compiled only) decoded to TGAs in the addon
  (`materials/water/cs2_waves_*.tga`), since a material can only take content files; without them the water has only player ripples.
- `g_vMapUVMin/Max` set to ±16384 on water with no skybox blend. Their reading of the shader: csgo_water_fancy discards water pixels
  outside Map UV Min/Max, and the default box is about -10272 -10199 .. 10241 10241, so water beyond it isn't drawn. Worth checking on
  our big maps that use stock water (stock materials carry their own Map UV values).
- The generated materials are recompiled every run: Hammer kept an older compile of a rewritten water vmat (tomgreens).
- **Underwater view: not achieved.** Earlier versions put in a map-wide `env_gradient_fog` "underwater_fog" and an underwater screen
  overlay; both were removed (the fog was map-wide, not limited to the water).

**A lead they didn't use**: CS2's `csgo.fgd` keeps `fog_volume`, a brush entity with `FogName` ("The name of the fog entity associated
with this volume"); Valve's comment there says only its PostProcessName and ColorCorrectionName had to be dropped. That is the piece
that limits an `env_gradient_fog` to the water. Per water: an env_gradient_fog with `fogcolor` = `$fogcolor`, `fogstart` / `fogend`
from the .vmt, `fogfalloffexponent` 1 (Source 1's fog was linear), `fogmaxopacity` 1, `heightfog` 0, a short `fadetime`; and a
fog_volume over the func_water up to the surface naming it. To find out in game:
- does fog_volume test the camera or the player's origin? (Our post_processing_volume tests the feet, hence its top 80 u under the surface.)
- which fog applies outside every fog_volume, especially in maps that already have their own env_gradient_fog (`global( gradient_fog )`)?
- does it fog the water surface itself seen from below, and does it stack with the material's own fog when looking down from above?
- players: CS2 draws players through fog at 1.7× the distance and 0.6× the density (`env_player_visibility` defaults, for competitive
  play), so players under water would stay clearer than the walls unless the map sets 1 / 1, which is map-wide.

Test plan: one map with deep water and a CS:GO original to compare (mg_pirates, ttt_minecraft or ba_jail_seaside). Material per CS:GO
water first (surface look from above and below), then the fog_volume, screenshots from the same spots in CS:GO and CS2.

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
5. **Source 1 water → its own CS2 water material, and CS:GO's underwater view**: see [Water](#water-csgos-look-above-and-below-the-surface)
   below (skink52: high value if it works, 10 Nov 2026).
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

## Smaller ideas worth knowing (10 Nov 2026 pass over their 322 settings; not compared with ours in detail)

Most settings match something we already do (null parameters, dropped `!self` outputs, the water-surface probe volume, sound distance
curves, sparks, steam, lasers, radar). These looked new or different:
- **Models with bare material names** (`VMDL_REMAP_BARE_MATERIALS`): a mesh naming `fern01.vmat` with no folder, because cs_mdl_import
  didn't apply the .mdl's `$cdmaterials`, gets a material remap to where the material was found, so the model compiles. We have nothing on
  this; check stage B's failed models for it.
- **Tool materials outside `materials/tools/`** (`TOOL_MATERIAL_PATH_FIX`): e.g. `materials/toolslightmapres.vmat`, which neither CS2 nor
  the addon has, pointed at `materials/tools/<same name>`.
- **Named or parented func_illusionary dropped by the importer** (`ILLUSIONARY_IO_FIX`, mg_hellz `mg7_illu`): rebuilt from the VMF as a
  never-solid func_brush with its name, render settings and faces.
- **Brush entity shadows** (`BRUSH_SYNC_MESH_SHADOWS`, `BRUSH_DISABLE_RECEIVING_SHADOWS`): the importer leaves the meshes at Cast Shadows
  Enabled on entities set to No Shadows (Hammer writes both); and a shadow over part of a brush entity darkens all of it unless Disable
  Receiving Shadows is set.
- **Mirrored texture patches bake darker** (`MIRRORED_TEXTURE_ANY`, mg_tomgreens): faces whose texture is turned 180° in the VMF baked
  visibly darker in CS2 (the normal map turned with it); they rotate the patch back.
- **Equip target names** (`EQUIP_FIX_INPUTS`): outputs firing Use at a game_player_equip → TriggerForActivatedPlayer, with the target
  respelled to the equip's exact case (their note: CS:GO matched names ignoring case). If CS2 matches entity names case-sensitively, that
  is a gotcha well beyond equips: worth one test.

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
