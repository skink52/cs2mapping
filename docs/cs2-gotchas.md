# CS2 gotchas: what breaks when a CS:GO map is ported, and what fixed it

Collected from the ports in this repo. "Where" points at a port that has the fix (see `ports/<addon>/`). Pipeline fixes run
automatically in stage C (see [pipeline.md](pipeline.md)).

## Valve's importer

| Problem | Fix |
|---|---|
| The importer fails while `game\bin\win64\vpk.signatures` exists, and Steam restores the file after updates. | Rename it (`run_import.bat` does it every run). |
| `import_map_community.py` waits for Enter/Esc, so it can't run unattended. | `scripts/make_import_map_auto.py` makes a copy without the prompt. |
| The importer aborts the **whole** run on the first model or material it can't handle. On a big map "it died" can mean anything from "barely started" to "only the compile didn't happen". | Run `post_import_cleanup.py` afterwards: it picks up where the importer stopped and reports what's still missing. |
| Raw BSPSource VMFs needed a Hammer open/save before the importer would take them. | `hammer_resave.py` reproduces exactly what that save changes (versioninfo, viewsettings, cordons, editor blocks, side `rotation`, %g planes, upper-case materials). |
| Entities on Valve's exclusion list (`source1import_map_entityexclusionlist.txt`) don't import: `func_illusionary`, `point_spotlight`, `func_dustmotes`, `func_precipitation`, `env_lightglow`, `color_correction`, `env_tonemap_controller`, `postprocess_controller`, `fog_volume`, `func_areaportal*`, `func_occluder`, `func_viscluster`, `func_lod`, `shadow_control`, `info_lighting`, `env_detail_controller`, `water_lod_control`, bot patrol routes, and anything matching `tele.` / `teleport_triggers`. | `func_illusionary` becomes a never-solid `func_brush` before import (it's often visible decoration). The cosmetic ones are listed in the cleanup log so you can decide whether to rebuild them. |
| Brushes textured `toolsskybox`, `toolshint`, `toolsskip`, `toolsareaportal` or `toolsoccluder` are skipped, so sky brushes vanish and rooms open to the void. | Stage C rebuilds each dropped sky brush as a moondome box using the map's sky. |
| `info_particle_system` entities don't come across with the map's particles, since CS:GO particle systems aren't in CS2. | Use stock CS2 particles. Mario Party's torches use `particles/burning_fx/env_fire_tiny.vpcf`. Check `game\csgo\pak01_dir.vpk` for names: there are many `particles/burning_fx/env_fire_*` and `env_embers_*`. |
| CS:GO materials with no source anywhere (custom textures not packed in the BSP). | Stage C rebuilds them from CS:GO's VPK if they're stock CS:GO, otherwise swaps in the closest stock CS2 material and flags it. Custom decals are left alone and flagged, because a random stock decal looks worse. |

## Models (cs_mdl_import)

| Problem | Fix |
|---|---|
| Running `cs_mdl_import -r` with a bare `*.mdl` scans the entire stock model tree and can crash (access violation) on an unrelated stock model, losing the whole batch. | Give it an explicit `-l` file list (`legacy/mdltovmdl.py`). |
| One `.mdl`/`.dx90.vtx` checksum mismatch crashes the run and everything queued after it. | `legacy/newcheck.py` finds all the mismatched pairs first. Exclude them, then fix them separately (Crowbar decompile/recompile). |
| Unlit model materials (`UnlitGeneric` with `$basetexture`) can import as `TextureColor "[1 1 1]"`, so the model renders plain **white**. | Point `TextureColor` back at the texture. Mario Party's A/B flags were white because of this. |

## Lighting and rendering

| Problem | Fix |
|---|---|
| CS:GO lights import as **Static** (baked only), so weapons and player models are black. | Switch enough lights to Stationary (`directlight 3`): one or more per sealed compartment, no spot inside more than 4 stationary lights. |
| With no light probe volume, brush entities (doors, platforms, buttons), props, players and weapons don't get the baked light, so they look brighter or darker than the walls. | `env_combined_light_probe_volume` over each room (Mario Party, mg_draw_course). |
| Dark indoor maps whose light came from the sky through ceilings. | `daylight` pass: a stationary sun, ceilings set to cast no shadows, probe volumes, and higher `maxexposure` (mg_draw_course). |
| `$alphatest` / `$translucent` materials import **opaque**, so cut-out letters, fences, glass and decals turn into solid squares. | Add `F_ALPHA_TEST` or `F_TRANSLUCENT` with a `TextureTranslucency` mask made from the texture's alpha. |
| CS:GO water shaders don't exist (no waterfall shader at all). | Stock `materials/liquids/nuke_water.vmat` on a closed volume with the water material on top and nodraw elsewhere. |
| `env_sun` doesn't exist. | `light_environment` draws the sun. Remove `env_sun`. |
| CS:GO skies aren't in CS2. | Rebuild the six CS:GO faces into a 2:1 equirect panorama (`sky.py`). HDR skies are tone mapped. |
| A 3D skybox: CS2 ignores `sky_camera`, so the skybox geometry becomes part of the map. | Move it to a separate skybox map referenced by `skybox_reference` (mg_awp_submarine, mg_bombardment, mg_enjoy_multigames, mg_yolo_multigames, ba_jail_skylight, ba_jail_lightsout). If it doesn't render: untick **Editor only** on the skybox map's `sky_camera` (ba_jail_lightsout). |
| Overlays become meshes, and their alpha is lost. | `csgo_static_overlay` with a translucency mask from the original alpha. |

## Vis and compile

| Problem | Fix |
|---|---|
| Vis voxelises every vis-relevant face at 8 units. Big sky shells around every room dominated: Mario Party took 19.2M nodes and 103 s to voxelise, plus 62 s of outside detection. | Mark sky shells "Exclude from Vis" where the room is already sealed by its own walls (`skyvis.py`), and use visibility hints: Lowest over the whole map, Low per room or arena. |
| Hint types (base.fgd) | 0 High (8), 1 Normal (8), 10 Reduced (16), 2 Medium (32), 3 Low (64), 8 Lower (64, fewer initial clusters), 9 Lowest (256, fewest clusters). |
| A command-line map build doesn't compile materials Hammer never loaded, and a missing material makes its meshes fail. | Compile the addon's materials, models, radar, sounds and scripts first (`build_maps.ps1`). |
| The compiler writes the `.vpk` to a temp outroot. Starting the next compile before that `.vpk` is copied caused clashes. | Build one map at a time and copy the `.vpk` into `game\csgo_addons\<addon>\maps\` before the next one starts. |
| A heavy environment prefab is too big to collapse in Hammer (ba_jail_lightsout). | Open the prefab on its own, copy everything, then Paste Special into the main map. The pipeline now collapses prefabs directly in the `.vmap`. |

## Entities that changed or vanished

| CS:GO | What happens in CS2 | Replacement |
|---|---|---|
| `env_laser`, `env_beam` | Can't spawn. | Never-solid `func_brush` beam with a laser material between the end points. Parent it to the same mover if the hurt trigger moves (Mario Party's Platform Peril). |
| `game_ui` | Still in the FGD, but its outputs never fire. | cs_script reads the driver's keys and fires the thrusters (`bumper_cars.js`, `helicopter.js`, `vehicles.js`, mg_yolo_multigames' cube). |
| `trigger_gravity` | Doesn't work on players. | Script gravity per player (Mario Party `Gravity_<x>`, mg_yolo_multigames). |
| `player_speedmod` | Gone. | Script sets ground velocity from the keys. Scale by the held weapon's speed and compensate for friction (Mario Party `Speed_<x>`). |
| `trigger_push` (players) | Keeps **adding** velocity every tick you're inside, so CS:GO's "set speed" pushes become rocket launchers. | `trigger_multiple` + script that holds the velocity along the push direction at the push speed (clamped to 3500). |
| `trigger_push` (physics props) | Doesn't throw them. Mario Party's bullet bills dropped into the water. | Script flies the prop straight along the push direction (which turns with a rotating parent) until it hits a wall. |
| `phys_thruster` on a physbox | In Mario Party the chain chomp's 16 thrusters didn't move `Dog_box`. | Freeze the box's physics and move it from script. (The jail vehicles still use thrusters, driven by script.) |
| `point_servercommand` | Most commands are blocked on servers. | `Instance.ServerCommand` from the map script. `say` can still be blocked by a server. |
| `game_score` | Gone. | `controller.AddScore(n)`. |
| `env_screenoverlay` | Gone. | `custom_hud_layout` + Panorama XML/CSS, shown and hidden from script. |
| `trigger_teleport` `SetRemoteDestination` / `AddOutput "target ..."` | The input is gone. | Script keeps the current destination per teleporter and teleports on touch. |
| `!activator AddOutput "targetname x"` (filter_activator_name tricks) | Doesn't work. | `entity.SetEntityName("x")` from script. |
| `!activator Color` / `Alpha` / `rendermode` AddOutputs | Don't work. | `entity.SetColor({ r, g, b, a })`. |
| `AddOutput "origin x y z"` on players or env_entity_makers | Doesn't work. | Script `Teleport`. |
| `game_player_equip` | CS:GO never gave a second copy of a weapon you already owned. CS2 does, so walking in and out of weapon triggers stacks guns. CS2's FGD only has "Use Only" (1) and "Strip First" (2). Equips without "Use Only" also no longer run on every spawn. | Script `Equip_<name>` gives only what the player doesn't have (`FindWeapon` / `FindWeaponBySlot(KNIFE)`). The spawn strip is done in `OnPlayerReset`. |
| `filter_activator_team` | The "Filter Team" dropdown in Hammer doesn't work. | Add the raw keyvalue `filterteam` (2 = T, 3 = CT), even though Hammer flags it as unknown. |
| Weapon targetnames | Lost when the weapon is picked up. | Watch the named weapon on the ground and record who takes it (`buff_new.js`). |
| `func_door` sound keys (`noise1`, `noise2`, `closesound`, `startclosesound`) with `.vsnd` paths | Silent. | `point_soundevent` (source entity = the mover) + `StartSound` outputs (Mario Party thwomps). |
| `ambient_generic` | Converted to soundevents. Looping needs loop cue points in the `.wav`, and an `.mp3` without them plays once. | Soundevents in `soundevents_addon.vsndevts`. "Play everywhere" uses the stereo base. |
| `func_wall_toggle` | Gone. | `func_brush` (Solidity toggle), with `TurnOn`/`TurnOff` → `Enable`/`Disable`. |
| `func_breakable_surf` | Gone. | `func_breakable` (glass). |
| `prop_hallucination` | Gone. | `prop_dynamic` / `prop_static`. |
| `func_conveyor` | Doesn't carry players. | Script moves the players on it (mg_swag_multigames). |
| `phys_pushscale`, `cs_enable_player_physics_box` | Gone. | Script knocks balls when players knife, shoot or run into them (mg_swag_multigames, mg_yolo_multigames). |
| `item_ammo_*` / `ammo_50ae` | No ammo items in CS2. | Script `RefillPistolAmmo`. |
| `sm_slay @all` etc. via `point_servercommand` | Needed SourceMod. | Script `SlayAll`. |
| `logic_script` VScripts (`.nut`) | No VScript in CS2. | Port to cs_script (`changemodel.js`, `mvp_health_increase.js`). |

## Hammer and workflow

- Hammer keeps the open map in memory. Close it before a script edits the `.vmap`, or the edit is lost on the next save.
- Don't delete the stock `materials\tools` folders, even to replace them with custom versions. Deleting them broke Hammer's clip tool.
- Opening a map in Hammer compiles its materials. The command-line build doesn't, so it compiles assets explicitly first.
