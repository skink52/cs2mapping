# cs2-slop-porting rechecks (8 and 25 Nov 2026)

> **AI-generated.** Written by Claude for skink52's pipeline. Earlier rechecks (29 Oct, 30 Oct, 2 Nov) are summarised in
> [external-tools.md](external-tools.md).

What was read: [Ninja-Chris/cs2-slop-porting](https://github.com/Ninja-Chris/cs2-slop-porting) at commit `8b94235` (8 Nov 2026):
`vmap_asset_slop_import.py` and `scripts/hurt_zone.js`, `player_velocity.js`, `push_mass.js`. Our last recheck was 3.5 / 2026-11-02a
(commit `949e104`). Nothing of theirs was copied into our tools; what we took is written fresh (the repo is MIT, Ninja-Chris and skink52).

## Recheck 25 Nov 2026 (2026-11-24h)

Read: commits `de5420b`..`ba2cbb1` (24 Nov 2026). The script now parses (30,016 lines, 439 settings, 117 new since 8 Nov, `DOOR_SPEED_MOVELINEAR`
gone) and ships 11 new cs_script files (player_equip, teleport_cycle, softbarrier, speedmod, screen_overlay, round_end, game_score,
maker_spawn, trigger_push, debug_watch, pickup_probe). The author's commit note: "diff merge yourself". Most new work was tuned on
mg_mario_party, mg_divine, mg_hellz and ba_jail_os_gulag_d. Each new setting was sized by a census of our 90 port vmaps (counts below).

**Omni-script: not recommended.** Their file is one 30k-line script holding every step; ours is the same work as small passes
(`stage_c` / `stage_d` / `run_c`, autoport on top), each testable and rerunnable on a map someone has edited in Hammer. Taking their
ideas into those passes (as below) gives one pipeline without importing a second, overlapping one. `stage_c` with its default list
already is the "one command".

### Taken (stage C default `compat`, stage D passes; `tools/csgocompat.py`, `tools/lighting.py`)

| What | Our ports | Evidence |
|---|---|---|
| Light styles written as CS2 style names | 1 (ttt_terrortrain) + every future relight | CS2's `scripts/light_styles.vdata_c` (read 25 Nov 2026): 11 named dimmer curves, exactly Source 1 presets 1-11 (`flicker_1` = style 1's `mmnmmommommnonmmonqnmmo`). We wrote the pattern string, which CS2 doesn't take. |
| Lights switched by outputs no longer client-only; TurnOn / TurnOff → Enable / Disable, SetPattern → SetStyle | 278 named client-only lights in 8 ports; switched: ba_jail_lightsout 147, ba_jail_skylight 30 | CS2 FGD: light_omni2 has Enable / Disable / Toggle / SetStyle, no TurnOn. A Create Client-Only Entity light has no server entity, so inputs never reach it (theirs: gulag's disco lights). Our `relight` set client-only on every light. |
| trigger_teleport `UseLandmarkAngles` / `CheckDestIfClearForPlayer` → `use_landmark_angles` / `check_if_dest_clear_for_player` | 175 set to 1 under the old name, 11 ports (mg_swag_multigames 55) | CS2 FGD has only the new names; the importer keeps the old ones. |
| StopSound in front of a Volume 0 (never raised again) / a Kill of a looping ambient_generic | mg_arcs_multigames 38, 4 more ports 22 | Theirs from CS:GO's binary + game (Mario Party lobby music). |
| prop_dynamic DefaultAnim → IdleAnim, looping | 72 in 4 ports (mg_antique_course 60) | CS2 FGD prop_dynamic has no DefaultAnim key. |
| func_clip_vphysics toolstrigger faces → toolsnodraw | 69 entities in 13 ports | Theirs in game (Mario Party lanes); not checked by us. |
| All-playerclip func_brush / func_wall / unbreakable func_breakable → func_clip_interaction_layer (InteractsAs playerclip, InteractsWith player) | mg_swag_multigames 28, mg_yolo_multigames 4, ba_jail_skylight 1 | Theirs in game (Mario Party cannon); FGD has the class and both keys. Entities sent Toggle / Break etc. are left and listed. |

Tested: scratch copies of ba_jail_lightsout, mg_swag_multigames, mg_arcs_multigames, mg_antique_course, ba_jail_skylight,
mg_yolo_multigames: changes as counted, entity count kept, a second run changes nothing. Not built, not checked in game. The ported
maps themselves were not changed: `stage_d.py <addon> <root> compat` applies it to one.

### Taken, batch 2 (same day)

| What | Where | Our ports | Tested on scratch copies |
|---|---|---|---|
| AddOutput keyvalues CS2 rejects on named targets → SetHealth / Alpha / Color (SetColor on lights), rendermode dropped; added outputs `OnX t:i:p:d:n` → `OnX>t>i>p>d>n` | `compat` / `addoutfix` | mg_arcs_multigames 60 rendercolor, mg_color_multigames 24 added outputs; 35 !activator ones listed for the io script | mg_arcs, mg_color: as counted, rerun 0 |
| Wake beside Enable / Toggle of a physics-object trigger over a sleeping physbox / prop | `compat` / `physwake` | 116 sleeping physboxes, 300 sleeping props, 174 physics triggers in 19 ports | none matched in the 8 maps tried |
| Shared parent name → the entity CS:GO picked (first in the VMF), renamed `<name>__parent`, outputs copied | `compat` / `sharedparent` | 35 children in 9 ports | mg_insomnia_course officedoor4 (6 children), mg_jahoukarail_2015 Grenade6 (4) |
| func_physbox SetMass to CS:GO's mass (volume, visible sides 0.5 u in approximated as volume − 0.5 × visible area, × CS:GO surfaceprop density read from its surfaceproperties, × massScale, max 50000) | opt-in `physboxmass` | 311 physboxes in 24 ports; template and shared-name ones left | ba_jail_lightsout Dball_1 2281 kg (concrete), mg_jahoukarail_2015 Break3 20.8 kg (metal, hollow) |
| TextureScroll on `$basetexturetransform` → csgo_unlitgeneric + DynamicParams `g_vTexCoordOffset` | `matscroll` (texfix) | ttt_terrortrain 5 (3D skybox ground), mg_pokemon_adventure 2 | written to memory only, rerun 0 |
| BSPSource 4-decimal scales → 1/256 multiple (`DECOMPILE_SCALE_FIX`) | `facescale` | every decompiled VMF | unit values (0.0313 → 0.03125, 0.4688 → 0.46875, 0.3 kept) |
| Floating spawns 16-48 u → 2 u over the floor (not over a prop) | stage C report, D `spawndropfix` | mg_arcs_multigames 65 at 32 u, mg_nature 48, ba_jail_keimusho 23 | report only |
| debug_watch.js (in-game console tools) | `tools/debug_watch.js`, opt-in `debugwatch` | — | api check and tscheck clean |

Left out of batch 2 on purpose: ConveyorScroll (needs a material copy per conveyor speed), ANIMATED_UNLIT (our importer route already writes F_TEXTURE_ANIMATION;
`animprops` handles tiled faces), VMDL_BODYGROUP_NAMES (`vmdlfix.py` already does it).

### Needs a check in game before taking

- **trigger_teleport the "CS:GO way"** (`CSGO_TELEPORTS` + teleport_cycle.js: keep the toucher's angles and velocity, cycle through
  same-named destinations). This contradicts Source SDK 2013's `CTriggerTeleport::Touch` (no landmark: destination angles and zero
  velocity unless spawnflag 32 Preserve angles), and would touch 1,462 landmark-less teleports in 39 of our ports. Same-named
  destinations: only 26 teleports in 3 ports (mg_bob2 13, jb_renegade 9, mg_minecraft_multigames 4). Test in CS:GO first.
- **phys_thruster force** (`PHYS_THRUSTER_FORCE`: × mass / 1000 with flag 16): 237 thrusters in 8 ports (mapgames 128, ba_jail_skylight 48).
  From their binary reading; needs the attached object's CS:GO mass. Our gotcha already says thrusters didn't move Mario Party's Dog_box.
- **logic_case fed numbers** (`LOGIC_CASE_FLOAT_TEXT`): they say CS2 sends "1.0", our gotcha guessed "1.000000". 7 math → case links in 3 ports.
- **trigger_buoyancy** over func_water (`WATER_BUOYANCY`): not in CS2's FGD.

### Not yet taken (bigger; candidates for later batches)

(Batch 2 took `ADDOUTPUT_KEY_INPUTS`, `ADDOUTPUT_OUTPUTS_GATED` (as a rewrite to the `>` form), `PHYS_TRIGGER_WAKE`, `PHYSBOX_SET_MASS`,
`SHARED_PARENT_FIX` / `AMBIGUOUS_PARENT_FIX`, `TEXTURE_SCROLL`, `DECOMPILE_SCALE_FIX`, `SPAWN_DROP_MAX`, `DEBUG_WATCH_SCRIPT`; the rest are still open.)
Models: `MDL_VTX_ONE_STRIP_GROUP` (cs_mdl_import joins a second strip group's triangles to the first's vertices: hostage faces),
`MDL_INCLUDE_TRIM` (import only the sequences the map plays from $includemodel), `MDL_CRASH_OTHER_SOURCE`, `MDL_REMEMBER_FAILURES`,
`VMDL_BODYGROUP_NAMES`, `RAGDOLL_*`, `MODEL_DEFAULT_POSE*`, `MODEL_SPHERE_HULLS`, `EYE_IRIS_BAKE`, `PROPDATA_MISSING_MODELS`.
Materials: `TEXTURE_SCROLL` / `ANIMATED_UNLIT` / `CONVEYOR_SCROLL` (only csgo_unlitgeneric animated in their tests), `ANIM_ONLY_BY_PROXY`,
`SELFILLUM_MASKS`, `REFRACT_FACES`, `MISSING_BLACK_FIX`, `RENDER_TARGET_BLACK`, `MATERIAL_BRACE_FIX`, `AREAPORTAL_FADE_BRUSH`.
Geometry (VMF-based): `DECOMPILE_SCALE_FIX` (BSPSource's 4-decimal scales), `BROKEN_SCALE_BY_PLANE`, `HIDDEN_FACE_FIX`, `GLASS_BACK_FIX`,
`GLASS_FLUSH_FIX`, `DISP_REBUILD`, `STATIC_OVERLAY_FIT_DEPTH` / `SURFACE_GAP`. Entities: `ENV_SUN_IN_SKY`, `CONVERT_SOUNDSCAPES` (35 in 15),
`WORLDTEXT_FIX` (75 in 9, mostly our originals), `SOFT_BARRIERS`, `SCREEN_OVERLAYS` (1), `MONSTER_GENERIC_FIX`, `MAKER_TEMPLATE_AT_ENTITY`,
`SHARED_PARENT_FIX` / `AMBIGUOUS_PARENT_FIX`, `PHYS_TRIGGER_WAKE`, `PHYSBOX_SET_MASS` (CS2 gave a physbox 10.6 kg for CS:GO's 445),
`ADDOUTPUT_KEY_INPUTS` / `ADDOUTPUT_OUTPUTS_GATED` (ao_targetname 209 in 8, ao_health 37, output-adding 44), `SPAWN_FLOOR_FIX` drop of
floating spawns (our `spawnlift` only lifts), `ROPE_CLIENTSIDE`. Tools: `debug_watch.js` (in-game entity / I/O console) is worth a copy
in `create/` as a debugging aid, not added to every map.
Covered already by our io script: equips, game_round_end, game_score, player_speedmod, trigger_gravity, trigger_push, dustmotes, ropes.

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
