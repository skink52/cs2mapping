# CS2 gotchas: what breaks when a CS:GO map is ported, and what fixed it

Collected from the ports in this repo. "Where" points at a port that has the fix (see `ports/<addon>/`). Pipeline fixes run
automatically in stage C (see [pipeline.md](../porting/pipeline.md)).

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
| The importer sanitises asset paths with spaces (`materials/schooufi texture/x.vmt` is referenced as `schooufi_texture/x.vmat`, `crash bandicoot/` → `crash_bandicoot/`), but `post_import_cleanup.py` converts the textures under their real names, so the vmap points at files that don't exist and the assets pass substitutes random stock materials. | `tools/matnames.py <addon> <root>` remaps the refs to the addon's real file names (needs `content_files_<addon>.json`). Run it before `alpha,assets`. mg_antique_course / mg_crash_bandicoot_course, 24 Oct 2026. |
| Static overlays (CS:GO infodecal / info_overlay) import as a 2x2 placeholder quad: tiny, flat on the default axis, often not on the surface. Some get a projection depth of 64, which shows as a 2x2x64 box and the overlay is invisible. | Stage C `overlayfix` (`tools/texfix.py`) rebuilds every untouched placeholder from the VMF: size = CS:GO texture x `$decalscale` (infodecal) or the info_overlay's own uv0..uv3 extent and StartU/EndU, laid on the brush face under the decal, origin 4 units off it, local +Z into the surface (Z = +normal makes it invisible), u mirrored and v flipped so the image reads correctly. Overlays edited by hand are left alone. `overlaydepth` also sets every overlay's projection depth to 8. Method from github.com/Ninja-Chris/cs2-slop-porting, 26 Oct 2026. |
| Brush face texture scale comes out absurd (e.g. 0.25/256) when the importer can't read the CS:GO texture, it reduces shifts to 0..16 and rounds axes, and Hammer draws the stored per-vertex texture coordinates, not the scale/shift numbers. | Stage C `facescale` (`tools/texfix.py`) matches each face to the VMF side on the same plane + material (overlapping brushes disambiguated by containment, axes, then shift mod 16), restores scale/axes/shift when the match is unambiguous or the scale is <0.01 / >8, and rewrites the texture coordinates with u = (P.axisU / scaleU + shiftU) / CS:GO texture width. Deliberate scales (0.125, 2, 4…) are kept. Same source, 26 Oct 2026. |
| CS:GO `$additive` and `$nocull` are dropped. | Stage C `matflags`: lightmapped materials get `F_TRANSLUCENT 1` + `F_ADDITIVE_BLEND 1` (additive only appears once translucent is on; alpha test is removed, the lit shaders can't do both); other shaders move to `csgo_unlitgeneric` with `F_BLEND_MODE 4`. `$nocull` → `F_RENDER_BACKFACES 1`. |
| An addon shows up in the Workshop Tools launcher as an example map that can't be edited. | `game\csgo_addons\<addon>\` still has the template's `readonly_tools_asset_info.bin` / `addoninfo.txt`. Delete both (working addons have neither). `prep.py` no longer copies them (24 Oct 2026). |

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
| mg_egypt_course's vis stalled in the final cluster merge: 35,254 clusters after the list merge (other maps got to 13-39k), then 2,308 s to merge only to 32,768 (135 s per pass, against about 1 s on mg_draw_course), with 4,094 as the target. The build was stopped after 51 min. Its long open halls have almost nothing that blocks vis (2,172 triangles), so most clusters see each other. | Fewer clusters to start from: hints fitted to the play space with Lower (`hintType` 8) instead of Low everywhere (`stage_d.py ... visfit_lower`). Build it last in a queue so a stall doesn't hold up the other maps. |
| Region counts don't follow hint volume: mg_draw_course's 6 Low boxes covered about 7,000 regions' worth of volume, but it got 258,371 regions. They follow vis surface area much more closely (roughly 300 to 1,400 regions per million square units across six maps). | Shrinking hint boxes helps most where it moves space players never stand in out of Low, but surface detail still costs. Keep detail that doesn't need to block sight Excluded from Vis. |
| `toolsnodraw` doesn't block vis and is ignored by the inside/outside test (Valve's Source 2 visibility docs). Clips, triggers and meshes marked Exclude from Vis don't count either. Imported func_detail comes in already Excluded from Vis (993 of egypt's 1,187 world meshes). | When checking whether a room is sealed for vis, use only vis-relevant geometry. Several ports (e.g. mg_galaxy_course) are enclosed only by nodraw, so in vis terms they're open. |
| Overlapping visibility_hints: the highest-resolution one governs (Valve docs). Low (3) and Lower (8) are both 64-unit grids, so which one wins where they overlap is unclear. | Keep Low and Lower boxes from overlapping. One Lowest over everything underneath is fine. |
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
| `trigger_gravity` | Doesn't work on players. | Script gravity per player: the pipeline's `gravity` pass (`tools/gravity.py`, `Gravity_<scale>`; same method as Mario Party and mg_yolo_multigames). |
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
| `func_door` sound keys (`noise1`, `noise2`, `closesound`, `startclosesound`) with `.vsnd` paths | Silent. The importer also drops `noise1`/`noise2` entirely (mg_n64_goldeneye). | `point_soundevent` (source entity = the mover) + `StartSound` outputs (Mario Party thwomps). |
| `ambient_generic` | Converted to soundevents. Looping needs loop cue points in the `.wav`, and an `.mp3` without them plays once. | Soundevents in `soundevents_addon.vsndevts`, with `PlaySound` → `StartSound` (`StopSound` stays). "Play everywhere" uses the stereo base. |
| `point_soundevent` | Silent if `soundName` is a file path (`sounds/launch.vsnd`) or the `.wav` was never compiled. | Use the event name (`launch`), compile the wavs, then re-save the `.vsndevts`. Hammer can cache a failed load, so restart the tools (mg_awp_submarine). |
| `func_wall_toggle` | Gone. | `func_brush` (Solidity toggle), with `TurnOn`/`TurnOff` → `Enable`/`Disable`. |
| `func_breakable_surf` | Gone. | `func_breakable` (glass), or `func_shatterglass` with the stock `glass_plate_shatter` (mg_n64_goldeneye). |
| `prop_hallucination` | Doesn't spawn, so the props are invisible. | `prop_dynamic` if named, otherwise `prop_static` (de_rats_1337). |
| `func_conveyor` | Doesn't carry players. | Script moves the players on it (mg_swag_multigames). |
| `env_sprite`, `env_spritetrail` | Gone. | `info_particle_system`, one particle per sprite texture (mg_yolo_multigames, mg_swag_multigames). |
| `env_particle_glow` (imported from CS:GO glow sprites) draws where it spawned: moving it from script or re-parenting it doesn't move the visible glow, a glow parented to a weapon stays put when a player picks the weapon up, and its `colortint` is ignored. Scripts can see and move the entity (found 48/48 on mg_metal_course_level_2); only the drawing is stuck. Restarting it after a move just redraws it once at the new spot. | `tools/glowfix.py`: every parented glow → `info_particle_system` with a generated per-colour `particles/glowfix/glow_<rrggbb>.vpcf` (additive sprite, continuous emitter, position lock, so it follows its entity) and names `glow_<parent>_<k>`. Weapon-parented glows also need a script follow (unparent, move each tick: weapon → carrier's chest → thrown projectile, kill on detonate). Apply wherever a map has parented env_particle_glows. mg_metal_course_level_2 (24 Oct 2026, awaiting in-game confirmation). |
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

## Learned building original addons

These came from the original cs_script minigames (Hellmatch, Space Racer, mg_trenchwarfare, Puppet Brawl, mg_deku_tree, the bomb-arena game).
"Unverified" means the project notes say it had not been confirmed in CS2 yet. The detailed write-ups are in the creation docs
([../creation/](../creation/)).

### Rendering, materials, models

| Problem | Fix |
|---|---|
| A custom camera close to a wall clips through it (CS2's near clip plane; eye 15 u forward, collision radius 16). Scripts can't change the near plane. | A hidden render-only copy of each wall up to 16 u behind it, same material; tall step faces and low lintels too. See-through dropped from ~99% to <1% (Hellmatch). |
| `csgo_unlitgeneric` `g_vTexCoordScrollSpeed` does nothing in CS2. | Animated prop whose frames are the texture shifted `max(2, w/32)` px (max 32 frames), stepped by the script. `F_TEXTURE_ANIMATION` (Valve's TV-static material) is the other route (unverified). |
| ModelDoc material-group skins never switched when groups were remapped from the SMD material name. | Remap groups from the default group's material path. |
| Alpha-tested textures must be power-of-two. | Pad or resize. |
| Backface culling: Hellmatch found CS2 drew both faces of its model polygons, while `$nocull` ports need `F_RENDER_BACKFACES 1`. | Depends on the shader. Check the material's flags instead of assuming. |
| Stock vmats with `F_VERTEX_ANIMATION` (wind, e.g. `maple_tree_bark_1`) look wrong on static props; legacy `vertexlitgeneric` stock materials (palletwood, kasbah planks, cloth01) have flat normals. | Export a non-animated `csgo_complex` copy of the texture, or pick a `csgo_complex` stock material. |
| Self-lit model parts (tracers, sight pips). | `csgo_vertexlitgeneric` + `F_SELF_ILLUM`. |
| Terrain blending. | Valve blend materials (e.g. `hr_ancient_blend_groundmud03-groundgrass_01_wet`), `VertexPaintBlendParams.x` = layer B weight, `VertexPaintTintColor`. Copy the mesh stream layout from `content/csgo/maps/editor/zoo/ancient_zoo.vmap`. |
| LOD pops at ~300 u with `lod_thresholds` 12–60, and generated LOD1 meshes that shift parts. | Thresholds ×16 (192–480); ship LOD0 only where LOD1 deviates > ~2 u; keep geometry identical across LODs. |
| A prop with no physics hull is walk-through; a full-mesh hull on a weapon crashed on drop. | One convex hull per prop (or a few), never the render mesh. |
| A ModelDoc model that only the script references (rig, effects) doesn't compile from the map build. | Open and save it in ModelDoc once, or compile it with `resourcecompiler -i <vmdl>`. |
| `SetModel` on players to a CS2 agent drew the local body/head in first person (mg_trenchwarfare, removed). Calling `SetColor`/alpha on a pawn every reset is the suspected cause of giant first-person weapons. | Hide pawns with `SetModelScale(0.02)` only and restore only what you changed. Converted custom player models need the agent rebuild ([../creation/models.md](../creation/models.md#player-models)). |
| Props the script moves. | `prop_dynamic` with `model_archetype ""`. Move them with `Move` every tick; a prop that is `Teleport`ed every tick is not drawn. |
| `SetModel` to a model the map never loaded does nothing. | Place a hidden "cache" `prop_dynamic` of every model the script uses. |

### Lighting and bake

| Problem | Fix |
|---|---|
| Lightmap bake stalled in charting ("26669 unique meshes") with every prop forced to `bakelighting 1` × LODs. | Light-probe foliage, wire and props under ~40 u (`bakelighting 0`); cover outer areas with probe volumes. |
| "No lightmap resolution volumes set". | Closed `toolslightmapres.vmat` meshes over the player space (64 grid, floor to +128) plus one box per room. |
| CS2 has 4 shadow slots per area. | In lamp-heavy spaces make most lights unshadowed with capped range, 1–2 shadowed. |

### Sky, vis, world

| Problem | Fix |
|---|---|
| The 3D skybox draws behind everything. | Nothing players or vehicles can get near may live in it. The skybox map needs `mapUsageType skybox`, its own `light_environment` + `env_sky` and a `sky_camera` (scale 16); the main map gets a `skybox_reference`. |
| Sky shells around arenas / dropped sky brushes (moondomes). | **New in the late-October 2026 CS2 update:** a `toolsskyboxocclude` tool material that does the job of the moondome shells (a surface that shows the sky and closes off the void). Reported by skink52; not yet tested in our maps or wired into the pipeline, which still writes `csgo_moondome` shells. Check the exact material path in Hammer's tools materials before scripting it. |
| A `toolsskybox` shell always shows the single `env_sky`. | Several skies in one map: one moondome box per area with its own sky material and no toolsskybox shell (whether `csgo_moondome` accepts an equirect `TextureCubeMap` is unverified). |
| `prop_static` models (visoccluder off) never block vis; fine hints over prop-only levels cost huge compile time (36 Low hints → 1.8M regions, 1013 s). | Low hints only along the play band, Lowest elsewhere. |
| World limit ±16384. Scripted things flown past it misbehave. | Clamp positions or hide the entity. |
| Bots don't move in a script-built lobby. | `func_nav_markup` WALKABLESEED volume. |
| `cs_minimap_boundary` makes CS2 draw its own top-down minimap instead of the radar image. | Remove them; the overview txt is enough. |
| Two players teleported to the same spot can never move again; spawns flush against a wall stick the player. | Step to the nearest clear spot after teleporting; fit spawns clear of walls. |

### Sound

| Problem | Fix |
|---|---|
| `csgo_music` soundevents with `volume_convar "snd_musicvolume"` spam "CSosOperatorConvar … Unable to acquire convar value: snd_musicvolume_rush…" on servers. | `volume_convar = "snd_menumusic_volume"` (verified: no spam, follows the Main Menu Music slider, silent if it's at 0). Alternative: `csgo_mega` with a flat distance curve (follows effects volume). Music is per server, not per player. |
| Looping wavs don't loop. | Write both a `smpl` loop and a `cue` chunk. |
| Rapid repeated sounds cut each other off. | Several `point_soundevent`s per source, round-robin. |

### Players, rounds and plugins

| Problem | Fix |
|---|---|
| `OnPlayerReset` also fires on a team change, sometimes **before** `OnPlayerTeamChanged`, with stale team data. | Re-read the controller's team in both handlers. |
| A slot can change hands with no disconnect event (a bot kicked for a joining human). | Check once a second who holds each slot; drop queued state when it changes. |
| HUD class changes sent before a joining client is ready are lost. | `hud.ResetForPlayer(slot)` and redraw on `OnPlayerActivate`, `OnPlayerTeamChanged` and spawn. |
| Scripted kills don't happen or count as teamkills. | `mp_respawn_immunitytime 0`, `mp_teammates_are_enemies 1`, skip kills in warmup (details in [cs_script-notes.md](cs_script-notes.md#kills-rounds-and-score)). |
| CounterStrikeSharp plugins that break script-run games: position-based AFK managers, no-respawn, spawn protection/godmode, TK punishment, plugins forcing `mp_teammates_are_enemies 0`, round-start cvar resetters (re-apply ~1 s after round start), loadout/knife givers, anti-stuck/noblock/third-person, chat-command clashes (`!rtv`), mid-round team balancers, per-tick entity scanners, `mp_restartgame` (clears spawned entities). | Whitelist the map or re-apply settings after them. |
| Client cvars from script (`Instance.ClientCommand`) are unreliable (`cl_draw_only_deathnotices` was refused once and took effect another time, hiding the custom HUD too). | Don't depend on them. |
| A script or Panorama change doesn't show after recompiling. | `disconnect`, then load the map again. |

### Loading screens and Workshop

| Problem | Fix |
|---|---|
| Space Racer / Hellmatch: with a single loading picture CS2 kept its default art. | Ship at least two (`<map>`, `<map>_1` … `_9`); they play as a slideshow, 4 s each, starting on a random one. Ports done with the Hammer5Tools `<map>_png` layout should be checked against this. |
| Loading pictures not compiled. | Reference them from a never-shown rule in the HUD stylesheet (they show from the second load), or compile with `run_build.bat "assets <addon>"`. |
| Content hidden behind CS2's loading UI. | 1920×1080 slide; CS2 draws a 300 px column 20 px from the right and crops 4:3/ultrawide. Keep content in x 252–1348, y 104–948. |
| The overview txt in the content folder isn't used. | `resource/overviews/<map>.txt` goes in the **game** folder. |
| Renamed map ships its old files too. | Delete the old `maps/<old>.vpk`, `_cameras.txt`, `_retakes.txt`, overview txt and compiled panorama images from content and game before uploading. |
| Workshop upload carries the compiled game folder, not content. | Licence and credit files must be in the game folder and/or the description. |

### More from the port and addon chats

| Problem | Fix |
|---|---|
| ModelDoc turns SMD imports 90° about Z and reads V from the bottom (Space Racer tracks and cars came out 90° off). | Write SMD positions pre-rotated −90° (`(y, −x, z)`) with V flipped, or compensate with a yaw offset in script. Verified. |
| ModelDoc drops bones that have no geometry (and meshes made only of tool materials): an invisible animation rig compiled with zero bones, leaving bone-merged agents in T-pose. | A tiny triangle per bone hidden inside the body (dark material) and `BoneMarkupList { bone_cull_type = "None" }`. Verified. |
| A custom player model imported from CS:GO is a plain prop: held weapons render huge, no ragdoll. | Rebuild it on the CS2 agent setup ([../creation/models.md](../creation/models.md#player-models)). |
| `CSWeaponBase.SetModel()` / `pawn.SetModel()` to a model that isn't loaded fails silently ("RESOURCE_TYPE_MODEL … requested is not loaded"). | Precache with a hidden `prop_dynamic` in the map. |
| The viewmodel can't be reached from cs_script (no `*viewmodel*` class at runtime). | Change view models through `weapons.vdata` ([../creation/custom-weapons.md](../creation/custom-weapons.md)). |
| Decompiling stock `scripts/weapons.vdata_c` throws "Unknown KVType … 26" in release Source 2 Viewer. | Use the Source 2 Viewer dev build (s2v.app), "Decompile & Export". A server's own vdata addon takes priority over a map's. |
| CS2 draws the local player's own body attached to the view even with a custom camera. | Make the parked pawn invisible (`SetModelScale`), keep geometry clear of the camera. |
| A text Label truncated at ~32 characters (Hellmatch kill messages). | Split long messages into rows wrapped at spaces; cap names at ~12 characters. |
| `say` sent from inside an `OnPlayerChat` callback is dropped. | Queue it and send from the think loop, ≥1 s apart. |
| Team-select menu shows behind a custom HUD. | Auto-assign unteamed players ~1 s after connect (`JoinTeam`), plus `mp_force_assign_teams 1`, `sv_disable_teamselect_menu 1`. |
| `RunScriptInput` carries only the input name, no value. | Encode numbers in the name (`Gravity_0.3`, `Speed_1.5`) and parse in script. |
| CS2 doesn't re-check players already inside a trigger when it's Enabled (and a `trigger_teleport` checks only on entry). | Script "Sweep_<name>" 0.1 s after the Enable teleports whoever is inside. Verified on Mario Party. |
| Imported triggers with no "touched by" flags ticked never fire. | Tick Clients / Physics Objects as needed (ball goals need Physics Objects). |
| Thin triggers around a physbox are unreachable (players stop at the physbox surface). | Script proximity check (36 units). |
| `prop_physics_override` won't move when pushed. | `damagetoenablemotion` / `forcetoenablemotion` set to any value (even "0") spawn it motion-disabled; clear them. `massScale` is a multiplier. |
| `phys_pushscale` is a disallowed Workshop convar (even through `Console.SetConvar`); `cs_enable_player_physics_box` is gone. | Simulate pushes: `OnBulletImpact` → velocity along impact − shooter eye; `OnKnifeAttack` → `TraceSphere` 72 u ahead → launch; proximity push for running into props. Verified on yolo. |
| No per-prop gravity for low-gravity balls. | Measure the engine's gravity on the ball in free flight ((vz − last set vz)/dt) and cancel (1 − scale) of it. Verified ("low grav is working"). |
| `amb.looping.stereo.base` fades in from silence over 1 s, so one-shots based on it lose their start. | `use_time_volume_mapping_curve = false`. |
| A `.mp3` without loop markers plays once. | Loops as WAV with `smpl` + `cue` chunks; mono for 3D sounds. Verified. |
| `effect_textureOverride` on a shared stock particle (glow01) changes every glow01 in the map. | A dedicated vpcf per texture. Hand-written vpcf that "isn't precached correctly": open and re-save it in the Particle Editor. |
| CS:GO "Refract" screen overlays and `color_correction` have no CS2 equivalent. | Keep the colour as a `post_processing_volume` with a 32³ RGB `.raw` LUT (`CColorLookupColorCorrectionLayer`). |
| Build logs look garbled. | They're UTF-16LE (`iconv -f UTF-16LE -t UTF-8`). Harmless noise: `scripts/detail_prop_types.vdata_c` missing, "Parameter corresponds to an entity target name… RunScriptInput", "No lightmap resolution volumes set". |
| `vrad3` `VK_ERROR_OUT_OF_DEVICE_MEMORY` on an Intel Arc B580. | Driver/ReBAR or CPU lighting, and lightmap resolution volumes to cut charts (untested). |
| Hammer while CS2 is running. | Second instance: `cs2.exe -addon <name> -tools -steam -retail -insecure -noassetbrowser -vulkan` (≈2× RAM/VRAM; don't build while both have the addon mounted; untested). |
| Blender FBX → ModelDoc materials. | Per-material custom string property `FBX_vmatPath` (live value, forward slashes, `materials/` prefix, no extension), Custom Properties ticked on export. |
| A door prop's pivot is in the wrong place and ModelDoc has no import translation. | Move the mesh in the source file, or an invisible `func_door_rotating` pivot with the prop parented. |
| WAVs that aren't plain 16-bit PCM (8/24/32-bit, float, ADPCM). | Re-encode to 16-bit PCM (stage C `sounds` does PCM/float; ADPCM is flagged). From cs2-slop-porting. |
| Some stock CS2 materials ship as stubs (error shader, no textures), so a CS:GO material of the same name looks broken. | Re-port the CS:GO material into the addon (cs2-slop-porting checks for this; our pipeline doesn't yet). |
| Entities that play Source 1 soundscript names (`MetalGrate.ImpactHard`) are silent. | Write a same-named soundevent from the CS:GO soundscript (cs2-slop-porting does this). |
| `env_steam` doesn't exist in CS2. | An `info_particle_system` with a particle built from its speed/spread/size/colour keyvalues (heat-wave type as a refracting sprite), as cs2-slop-porting generates. |
| The choose-team camera position. | It uses an `info_player_terrorist`'s position/angles. |
