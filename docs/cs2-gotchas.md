# CS2 gotchas: what breaks when a CS:GO map is ported, and what fixed it

Collected from the ports in this repo. "Where" points at a port that has the fix (see `ports/<addon>/`). Pipeline fixes run
automatically in stage C (see [pipeline.md](pipeline.md)).

## Valve's importer

| Problem | Fix |
|---|---|
| The importer fails with "pak01.vpk / Failed to load file (invalid)" while `game\bin\win64\vpk.signatures` exists, and Steam restores the file after updates. | Rename it (`run_import.bat` does it every run). |
| `import_map_community.py` waits for Enter/Esc, so it can't run unattended. | `scripts/make_import_map_auto.py` makes a copy without the prompt. |
| The importer aborts the **whole** run on the first model or material it can't handle (`utlc.RunCommand` → `Error()` → `sys.exit(1)`). On a big map "it died" can mean anything from "barely started" to "only the compile didn't happen". | Run `post_import_cleanup.py` afterwards: it picks up where the importer stopped and reports what's still missing. |
| The importer fails when the CS:GO content path contains spaces. | Point it at a junction instead (`mklink /J C:\cscontent "<CS2>\csgo"`). |
| "Found no files matching specification". | The second argument (content root) is the folder that holds the VMF (`C:\source1`), not the CS:GO content folder. `-usebsp` needs the BSP in the legacy `csgo\maps`. |
| Raw BSPSource VMFs needed a Hammer open/save before the importer would take them. | `hammer_resave.py` reproduces exactly what that save changes (versioninfo, viewsettings, cordons, editor blocks, side `rotation`, %g planes, upper-case materials). |
| Entities on Valve's exclusion list (`source1import_map_entityexclusionlist.txt`) don't import: `func_illusionary`, `point_spotlight`, `func_dustmotes`, `func_precipitation`, `env_lightglow`, `color_correction`, `env_tonemap_controller`, `postprocess_controller`, `fog_volume`, `func_areaportal*`, `func_occluder`, `func_viscluster`, `func_lod`, `shadow_control`, `info_lighting`, `env_detail_controller`, `water_lod_control`, bot patrol routes, and anything matching `tele.` / `teleport_triggers`. | `func_illusionary` becomes a never-solid `func_brush` before import (it's often visible decoration: 94 on mg_fred_all). The cosmetic ones are listed in the cleanup log so you can decide whether to rebuild them. |
| Brushes textured `toolsskybox`, `toolshint`, `toolsskip`, `toolsareaportal` or `toolsoccluder` are skipped, so sky brushes vanish and rooms open to the void. | Stage C rebuilds each dropped sky brush as a moondome box using the map's sky. |
| Many outputs are dropped, especially ones aimed at `!activator`. | Stage C diffs every entity's outputs against the decompiled VMF and puts the missing ones back. |
| The importer writes the main map as a keyvalues2 text `.vmap` plus prefabs. | Stage C collapses the prefabs and saves the map back as binary. |
| `info_particle_system` entities don't come across with the map's particles, since CS:GO particle systems aren't in CS2. | Use stock CS2 particles. Mario Party's torches use `particles/burning_fx/env_fire_tiny.vpcf`. Check `game\csgo\pak01_dir.vpk` for names: there are many `particles/burning_fx/env_fire_*` and `env_embers_*`. |
| CS:GO materials with no source anywhere (custom textures not packed in the BSP). | Stage C rebuilds them from CS:GO's VPK if they're stock CS:GO, otherwise swaps in the closest stock CS2 material and flags it. Custom decals are left alone and flagged, because a random stock decal looks worse. |
| A prop using a player model (a `tm_balkan` prop on mg_simpsons_course) makes the importer convert that model's whole animation set (2,654 animations). | Slow, not broken. Let it run. |
| VTFCmd's `-output` flag flattens the folder tree (all PNGs land in one folder by bare name). | Leave out `-output` so each PNG is written next to its VTF. |

## Models (cs_mdl_import)

| Problem | Fix |
|---|---|
| Running `cs_mdl_import -r` with a bare `*.mdl` scans the entire stock model tree and can crash (access violation) on an unrelated stock model, losing the whole batch. | Give it an explicit `-l` file list (`legacy/mdltovmdl.py`). |
| One `.mdl`/`.dx90.vtx` checksum mismatch crashes the run and everything queued after it. | `legacy/newcheck.py` finds all the mismatched pairs first (studiohdr checksum at offset 8 vs the VTX header at offset 16). Exclude them, then fix them separately (Crowbar decompile/recompile). |
| cs_mdl_import converts geometry only. | Materials need their own pass (`post_import_cleanup.py` phases 2–3). |
| Unlit model materials (`UnlitGeneric` with `$basetexture`) can import as `TextureColor "[1 1 1]"`, so the model renders plain **white**. | Point `TextureColor` back at the texture. Mario Party's A/B flags were white because of this. |
| Custom CS:GO player models import as plain props with no CS2 skeleton or animgraph, so held weapons render huge. | Rebuild the model on the stock Phoenix agent skeleton (mg_mario_party's Octodad matched 73 bones; mg_50arenas' Power Ranger) and copy tm_phoenix's 14 ragdoll joints. |
| Props from other Source games that won't import. | Crowbar → Blender → ModelDoc, with alpha masks made from the textures. |

## Lighting and rendering

| Problem | Fix |
|---|---|
| CS:GO lights import as **Static** (baked only), so weapons and player models are black. | Switch enough lights to Stationary (`directlight 3`): one or more per sealed compartment, no spot inside more than 4 stationary lights. |
| Lights the map switches on and off. | They must be **Dynamic** (`directlight 2`): Static lights can't switch off (de_rats_1337's 32 switchable lights). |
| With no light probe volume, brush entities (doors, platforms, buttons), props, players and weapons don't get the baked light, so they look brighter or darker than the walls. | `env_combined_light_probe_volume` over each room (Mario Party, mg_draw_course). |
| Dark indoor maps whose light came from the sky through ceilings. | `daylight` pass: a stationary sun, ceilings set to cast no shadows, probe volumes, and higher `maxexposure` (mg_draw_course). |
| `$alphatest` / `$translucent` materials import **opaque**, so cut-out letters, fences, glass and decals turn into solid squares. | Add `F_ALPHA_TEST` or `F_TRANSLUCENT` with a `TextureTranslucency` mask made from the texture's alpha. |
| CS:GO water shaders don't exist (no waterfall shader at all). | Stock `materials/liquids/nuke_water.vmat` on a closed volume with the water material on top and nodraw elsewhere. Reflections come from a baked cubemap. |
| `env_sun` doesn't exist. | `light_environment` draws the sun. Remove `env_sun`. |
| CS:GO skies aren't in CS2. | Rebuild the six CS:GO faces into a 2:1 equirect panorama (`sky.py`). HDR skies are tone mapped. |
| A 3D skybox: CS2 ignores `sky_camera`, so the skybox geometry becomes part of the map. | Move it to a separate skybox map referenced by `skybox_reference` (mg_awp_submarine, mg_bombardment, mg_enjoy_multigames, mg_yolo_multigames, ba_jail_skylight, ba_jail_lightsout). If it doesn't render: untick **Editor only** on the skybox map's `sky_camera` (ba_jail_lightsout). |
| Overlays become meshes, and their alpha is lost. | `csgo_static_overlay` with a translucency mask from the original alpha. For decals with a solid background, key the mask from the most common border colour (mg_smee_tower_cs2, de_rats_1337). Overlays that come out too bright can be toned down with `g_fTextureColorBrightness` (0.3 on ba_jail_lightsout). |
| A moondome (sky-material shell) doesn't always hide the arena next door. | On mg_mario_party small parts of other arenas show from odd positions. Not solved yet. |

## Vis and compile

| Problem | Fix |
|---|---|
| Vis voxelises every vis-relevant face at 8 units. Big sky shells around every room dominated: Mario Party took 19.2M nodes and 103 s to voxelise, plus 62 s of outside detection. | Mark sky shells "Exclude from Vis" where the room is already sealed by its own walls (`skyvis.py`), and give each room its own hint box. Mario Party went to 3.6M nodes, 23 s voxelise, 27 s outside detection. |
| After that, a multi-room map's vis time is clustering, line-of-sight sampling and cluster merging: Mario Party still spent 27 min in vis, mostly merging 12,963 clusters down to the 4,096 cap (560 s) and LOS rays (444 s). | Fewer initial clusters is the lever: Lower (`hintType` 8) instead of Low on big rooms. Not yet tried on Mario Party. |
| Hint types (base.fgd) | 0 High (8), 1 Normal (8), 10 Reduced (16), 2 Medium (32), 3 Low (64), 8 Lower (64, fewer initial clusters), 9 Lowest (256, fewest clusters). |
| High or Medium hints over big arena boxes explode the cluster count: Mario Party's Medium arena hints gave 1,451,170 regions and 663 s of clustering. Lowest everywhere (256-unit regions) makes walls vanish a few steps back. | Low over each room or arena, one Lowest over the void, Medium only in small dense spots. For a very large total volume use Lower (mg_50arenas: 53 boxes, about 60 times a normal map's volume). |
| Open maps make vis slow: mg_circle_course's open centre took 18+ min (2,453,840 clusters). | Iterate without full vis and keep the sealed volume as small as the playable space. |
| A command-line build writes the `.vpk` only to its `-outroot`. Hammer copies it into `game\csgo_addons\<addon>\maps\` itself, so early command-line builds seemed to do nothing. | `build_maps.ps1` copies it and checks the size. |
| Starting the next compile before that `.vpk` is copied caused clashes. | Build one map at a time and copy the `.vpk` before the next one starts. |
| A command-line map build doesn't compile materials Hammer never loaded, and a missing material makes its meshes fail ("Failed loading resource materials/lasers/…vmat_c"). Radar PNGs need a `.vtex` next to them to be compiled at all. | Compile the addon's materials, models, radar, sounds and scripts first (`build_maps.ps1`). |
| A heavy environment prefab is too big to collapse in Hammer (ba_jail_lightsout: about 15 MB, 1,457 entities). | Open the prefab on its own, copy everything, then Paste Special into the main map. The pipeline now collapses prefabs directly in the `.vmap`. |
| Harmless build-log noise | `Failed loading resource "scripts/detail_prop_types.vdata_c"` shows on every build. "Parameter 'x' corresponds to an entity target name, but is sent to input 'RunScriptInput'… (FGD Error?)" just means a script input name matches an entity name. "No lightmap resolution volumes set" only lowers lightmap texel density. |

## Entities that changed or vanished

| CS:GO | What happens in CS2 | Replacement |
|---|---|---|
| `env_laser`, `env_beam` | Can't spawn (and env_beams were blamed for crashes on mg_n64_goldeneye). | Never-solid `func_brush` beam with a laser material between the end points. Parent it to the same mover if the hurt trigger moves (Mario Party's Platform Peril). |
| `func_brush` parented to a `func_rotating` | Won't Enable. | Leave it unparented and fire `SetParent` at runtime (ba_jail_seaside). |
| `game_ui` | Still in the FGD, but its outputs never fire. | cs_script reads the driver's keys and fires the thrusters (`bumper_cars.js`, `helicopter.js`, `vehicles.js`, mg_yolo_multigames' cube). |
| `trigger_gravity` | Doesn't work on players. | Script gravity per player (Mario Party `Gravity_<x>`, mg_yolo_multigames). |
| `player_speedmod` | Gone, and cs_script has no speed setter. | Script sets ground velocity from the keys. Scale by the held weapon's speed and compensate for friction (Mario Party `Speed_<x>`). On servers with CounterStrikeSharp a plugin can set `VelocityModifier` instead. |
| `trigger_push` (players) | Keeps **adding** velocity every tick you're inside, so CS:GO's "set speed" pushes become rocket launchers. | `trigger_multiple` + script that holds the velocity along the push direction at the push speed (clamped to 3500). |
| `trigger_push` (physics props) | Doesn't throw them. Mario Party's bullet bills dropped into the water. | Script flies the prop straight along the push direction (which turns with a rotating parent) until it hits a wall. |
| `phys_thruster` on a physbox | In Mario Party the chain chomp's 16 thrusters didn't move `Dog_box`. | Freeze the box's physics and move it from script. (The jail vehicles still use thrusters, driven by script.) |
| `phys_pushscale`, `cs_enable_player_physics_box` | Gone. Map checks that relied on them (yolo's physics barrel) fail. | Remove the check. The script knocks props when players knife, shoot or run into them (mg_swag_multigames, mg_yolo_multigames). |
| Ball-game physics props (yolo's volleyballs) | They spawn frozen, as in the original, and need waking. Low gravity has to come from somewhere else. | Script nudges them, and gives them low gravity by measuring CS2's gravity on the ball and cancelling 3/4 of it. |
| Thin triggers around a physbox | Players stop at the physbox surface, so a grab trigger that sticks out 2 units can't be reached. | Script proximity check (Mario Party's mushroom: within 36 units). |
| Triggers that should see grenades | CS2 triggers don't detect grenades. | Script tracks each grenade (yolo's grenade holes). |
| Triggers with no "touched by" flags | yolo's imported football goal triggers had none ticked, so the ball never set them off. | Tick the right flags (Physics Objects for the goals). |
| `trigger_teleport` aimed by renaming the player | It checks players only as they enter, and the rename lands after the player is already inside. | Script teleport (Mario Party's Block Fort). |
| `math_counter` → `logic_case` | The value arrives as a float ("5.000000"), so whole-number cases never match. | Script forwards `Math.round(value)` to the case (Mario Party `COUNTER_TO_CASE`). |
| Map entities across rounds | Re-created every round, so outputs a script hooked last round are gone. | Re-hook in `Instance.OnRoundStart` (ba_jail_skylight's keypad, Mario Party's counters). |
| `point_servercommand` | Most commands are blocked on community servers by default. | `Instance.ServerCommand` from the map script. Chat lines then show as "Console: …", and `say` can still be blocked by a server. |
| `game_score` | Gone. | `controller.AddScore(n)`. It adds to the scoreboard's score column, where CS:GO's game_score added frags. |
| `env_screenoverlay` | Gone. | `custom_hud_layout` + Panorama XML/CSS, shown and hidden from script. Screen-warp "EFFECT" overlays have no equivalent; keep the colour as a post-processing tint (mg_50arenas). |
| `trigger_teleport` `SetRemoteDestination` / `AddOutput "target ..."` | The input is gone. | Script keeps the current destination per teleporter and teleports on touch. |
| `!activator AddOutput "targetname x"` (filter_activator_name tricks) | Doesn't work ("AddOutput fired with bad string"). | `entity.SetEntityName("x")` from script. |
| `!activator Color` / `Alpha` / `rendermode` AddOutputs | Don't work. | `entity.SetColor({ r, g, b, a })`. |
| `AddOutput "origin x y z"` on players or env_entity_makers | Doesn't work. | Script `Teleport`. |
| `game_player_equip` | CS:GO never gave a second copy of a weapon you already owned. CS2 does, so walking in and out of weapon triggers stacks guns. CS2's FGD only has "Use Only" (1) and "Strip First" (2). Equips without "Use Only" also no longer run on every spawn. Legacy `weapon_x 1` keys don't work. | Items go in `weapon0..N` slots, and "Use" becomes `TriggerForActivatedPlayer`. Script `Equip_<name>` gives only what the player doesn't have (`FindWeapon` / `FindWeaponBySlot(KNIFE)`). The spawn strip is done in `OnPlayerReset`. |
| `filter_activator_team`, `filter_*` `negated` | Hammer's filter dropdowns and keyvalues are unreliable. | Turn Smart Edit off and add raw keyvalues (`filterteam` 2 = T, 3 = CT; `negated` 1), even though Hammer flags them as unknown. |
| Weapon targetnames | Lost when the weapon is picked up. `GiveNamedItem` doesn't fire `OnPlayerPickup` either. | Watch the named weapon on the ground and record who takes it (`buff_new.js`). |
| `func_door` sound keys (`noise1`, `noise2`, `closesound`, `startclosesound`) with `.vsnd` paths | Silent. | `point_soundevent` (source entity = the mover) + `StartSound` outputs (Mario Party thwomps). |
| `ambient_generic` | Converted to soundevents. Looping needs loop cue points in the `.wav`, and an `.mp3` without them plays once. | Soundevents in `soundevents_addon.vsndevts`, with `PlaySound` → `StartSound` (`StopSound` stays). "Play everywhere" uses the stereo base. |
| `point_soundevent` | Silent if `soundName` is a file path (`sounds/launch.vsnd`) or the `.wav` was never compiled. | Use the event name (`launch`), compile the wavs, then re-save the `.vsndevts`. Hammer can cache a failed load, so restart the tools (mg_awp_submarine). |
| `func_wall_toggle` | Gone. | `func_brush` (Solidity toggle), with `TurnOn`/`TurnOff` → `Enable`/`Disable`. |
| `func_breakable_surf` | Gone. | `func_breakable` (glass), or `func_shatterglass` with the stock `glass_plate_shatter` (mg_n64_goldeneye). |
| `prop_hallucination` | Doesn't spawn, so the props are invisible. | `prop_dynamic` if named, otherwise `prop_static` (de_rats_1337). |
| `func_conveyor` | Doesn't carry players. | Script moves the players on it (mg_swag_multigames). |
| `env_sprite`, `env_spritetrail` | Gone. | `info_particle_system`, one particle per sprite texture (mg_yolo_multigames, mg_swag_multigames). |
| `func_monitor`, `func_physbox_multiplayer`, `light_dynamic`, `color_correction` | Gone. | `func_brush`, `func_physbox`, `light_barn`, `post_processing_volume`. |
| `item_ammo_*` / `ammo_50ae` | No ammo items in CS2. | Script `RefillPistolAmmo`. |
| `sm_slay @all` etc. via `point_servercommand` | Needed SourceMod. | Script `SlayAll`. |
| `logic_script` VScripts (`.nut`) | No VScript in CS2. | Port to cs_script (`changemodel.js`, `mvp_health_increase.js`). Player-model VScripts become `Model_<name>` inputs that set a CS2 agent model (mg_50arenas). |

## Radar, loading screen and Workshop

| Problem | Fix |
|---|---|
| Radar overview file | `resource/overviews/<map>.txt` in `game\`: `material`, `pos_x`, `pos_y`, `scale`, `rotate`, `zoom`. The image is `panorama/images/overheadmaps/<map>_radar_psd.png` + `.vtex`. |
| Stacked maps (towers): one radar image can't show both levels. | `"verticalsections"` with `"default"` and `"lower"` sections (AltitudeMin/Max), each with its own image (`<map>_lower_radar_psd`). Done by hand for mg_smee_tower_cs2. |
| RadGen | The selection set has to be named exactly `radgen_path`. |
| Loading-screen text | A text file next to the map: `game\csgo_addons\<addon>\maps\<map>.txt`, first line `COMMUNITYMAPCREDITS:`. No rebuild needed. |
| Steam Workshop pages read through a page fetcher all say "This item has been removed…" / "incompatible with Counter-Strike 2". | That's hidden template text in every page's HTML. Never report an item as removed from it. A page that shows visitor and subscriber stats is live. |

## Hammer and workflow

- Hammer keeps the open map in memory. Close it before a script edits the `.vmap`, or the edit is lost on the next save.
- Don't delete the stock `materials\tools` folders, even to replace them with custom versions. Deleting them broke Hammer's clip tool.
- Opening a map in Hammer compiles its materials. The command-line build doesn't, so it compiles assets explicitly first.
- The `.vmap` keeps its own list of the assets it references. A stale list keeps Hammer reporting classes and scripts you've already removed
  (mg_50arenas). Rebuild it from the real entities.
- Moving outputs from a trigger onto a `logic_relay`: rename `OnStartTouch` to `OnTrigger`, or they never fire (yolo's scores).
- After fixing a sound, restart the tools. Hammer can keep a failed sound load cached.
