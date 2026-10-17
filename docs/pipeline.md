# cs2port: the CS:GO → CS2 map port pipeline

> **AI-generated code.** These tools were written by Claude (an AI agent) for skink52's CS:GO to CS2 map ports, not hand-written.

On the PC they live in `C:\source1\cs2port\tools` (this repo's `tools/` folder). Claude runs them in its cloud workspace and reads and writes
the PC through the linked-computer file tools. Hammer must stay closed while Claude edits a map. Paths below are the PC paths; see
[setup.md](setup.md) for how the repo maps onto them.

## Who does what

| Stage | What happens | Who |
|---|---|---|
| A. Prep | BSPSource decompile with embedded files unpacked (`bspsrc` extracted from your jlink image, run on Java 21). VMF renamed to the addon name. **Hammer re-save fix** (`hammer_resave.py`) adds versioninfo/viewsettings/cordons, editor blocks and side `rotation`, and rewrites planes and axes at %g precision with upper-case materials. The result matches a real Hammer save structurally. func_illusionary (on Valve's import exclusion list, so it would vanish) becomes a never-solid func_brush. Materials and models are packed into `C:\source1\cs2port\assets\<addon>.zip` (plus `.2`/`.3`/`.4.zip` for big maps, each under ~14 MB so they transfer to the PC), and `run_import.bat` unpacks them into `csgo\` (files that already exist are never overwritten). Claude doesn't need access to the `csgo` folder. The decompiled embedded files are not kept under `C:\source1\maps\<addon>\`; the BSP can always regenerate them. Sounds go to `<addon>\sounds\` with cleaned names (`maps\<addon>_sound_renames.json`). Other embedded files go to the addon. The addon is created from `addon_template`, the same way the Workshop Tools launcher does it. | Claude |
| B. Import | Double-click `C:\source1\cs2port\run_import.bat`. For each line in `queue.txt` (`addon [vmfname]`) it re-renames `vpk.signatures` if Steam restored it, unpacks `assets\<addon>*.zip` into `csgo\` with `tar -k` (log `logs\<addon>_assets_unpack.log`), runs `import_map_auto.py` (Valve's importer without the Enter prompt), then `post_import_cleanup.py`. Logs go to `logs\`. | **You** (Claude can't run programs on the PC) |
| C. Clean | `stage_c.py <addon> <root>` edits the .vmap directly. It collapses every prefab (lighting/nav/audio/cubemaps/environment/gameplay) into the map with world offsets kept; a 3D skybox prefab stays as a prefab. It then runs the fixes below and writes `maps\<addon>_cleanup_log.txt`. | Claude |
| D. Build | Close CS2/Hammer and double-click `C:\source1\cs2port\run_build.bat`. It compiles every map in `build_queue.txt` from the command line, one at a time, and moves each built .vpk into the game addon before starting the next (see below). Then test in game and report anything odd. | **You** |

## Before porting: duplicate check and names
- Claude checks every requested map against `C:\source1\cs2port\existing_ports.txt` (`ports.py check`, which ignores prefixes, `_cs2` and version suffixes) **and** searches the web (Steam Workshop, GameBanana) for a CS2 port that already exists. Any likely duplicate is reported before stage A starts, and that map is not ported unless you say so.
- Addon names are the BSP name with version/bloat stripped: `_v2`, `_v1_2`, `_b3`, `_rc1`, `_final`, `_fix`, `_beta`, `_csgo`, `_hdr`, `_ws`… (`mg_x_v2_final` → `mg_x`). A different name can be forced with `bspname=addonname`.
- Each map Claude starts is added to `existing_ports.txt` as `<addon> [in progress] [skink]` (`ports.py add`). A successful build changes it to `[in progress, built]`. `[briar]` lines are maintained by hand; `[ported]`, `[*original*]` and `[ext. port]` lines are never changed.

## Stage D: command-line build (`build_maps.ps1`)
- `run_build.bat` runs `build_maps.ps1` on `build_queue.txt` (one addon per line, optionally `addon mapname`). `build_maps.ps1 mg_a mg_b` builds just those maps.
- **Assets first.** The command-line map build does not compile materials or textures; Hammer normally compiles them when it loads a map. So anything Claude added outside Hammer (laser materials, alpha masks, radar) would be missing, and missing materials are fatal for those meshes. For each addon the script first runs `resourcecompiler -r -i <content addon>/<dir>/*.<ext>` for materials `*.vmat`, models `*.vmdl`, panorama `*.vtex` (radar), soundevents, sounds `*.wav`/`*.mp3` and `maps/scripts/*.js`, logging to `logs\<addon>_assets.log`. Only out-of-date files are recompiled. If any content .vmat still has no compiled `_c` in `game\`, that map is skipped and the materials are listed. A queue line `assets <addon>` compiles the assets only, with no map build.
- Then it runs `game\bin\win64\resourcecompiler.exe` with Hammer's full-build arguments: `-threads 5 -fshallow -maxtextureres 256 -quiet -unbufferedio -i <content vmap, forward slashes> -noassert -world -rebake_surfacegraph -bakelighting -lightmapMaxResolution 1024 -lightmapVRadQuality 1 -phys -vis -nav -sareverb -sareverb_threads 6 -sapaths -sareverb_threads 6 -sacustomdata -sacustomdata_threads 6 -breakpad -nop4 -outroot %LOCALAPPDATA%\Temp\valve\hammermapbuild\game`.
- **Outroot step** (what Hammer does after a build): the compiler writes `<outroot>\csgo_addons\<addon>\maps\<map>.vpk`. The script waits for the compiler to exit, then copies that vpk to `game\csgo_addons\<addon>\maps\`, checks the size matches, and deletes the temp copy. Only then does the next map start. A stale vpk left in the outroot is deleted before each compile so it can never be copied by mistake. If the game file is locked (CS2 open) it retries, then reports the map as failed with the vpk still in the outroot.
- Maps are built one at a time on purpose. Separate outroots per map would avoid the vpk clash, but the light bake uses the GPU and every build writes shared compiled assets into `game\`, so parallel builds are no faster and risk VRAM or file-lock failures.
- The script refuses to start while `cs2.exe` (CS2 or Hammer) is running, and waits for any other resourcecompiler to finish.
- Logs: `logs\<addon>_build.log`, plus one line per map in `logs\stage_d_done.txt` (OK / FAILED, minutes, exit code).
- Claude writes `build_queue.txt` at the end of stage C (or after follow-up passes) and tells you to run `run_build.bat`. When you say it's finished, Claude reads `logs\` and fixes any compile errors.

## Stage C fixes (automatic; the importer's main .vmap is keyvalues2 text and is saved back as binary)
- Puts back outputs the importer dropped (diffs every entity's outputs against the decompiled VMF).
- func_wall_toggle → func_brush (Solidity Toggle; StartDisabled from "Starts Invisible"). TurnOn/TurnOff → Enable/Disable.
- trigger_push → trigger_multiple plus `maps/scripts/<addon>_io.js` push zones that hold CS:GO "set speed" behaviour. Names, filters and Enable/Disable are kept.
- point_servercommand → script `Cmd_n`, with "Ported to CS2 by skink52" added after CS:GO port credits. game_score → script `Score_n`.
- game_player_equip → weapon0..weapon21 slots. func_breakable_surf → func_breakable (glass).
- prop_hallucination → prop_dynamic or prop_static. env_sun and unnamed point_viewcontrol are removed.
- ambient_generic custom sounds → soundevents in `soundevents_addon.vsndevts`. "Play everywhere" uses the stereo base; others use a 3D event with the original radius.
- Static overlays → `csgo_static_overlay` with a translucency mask taken from the original alpha.
- Missing materials are rebuilt from CS:GO's VPK (VMT from `pak01_dir`, VTF decoded from the archive chunk). Water materials → `liquids/nuke_water`. Materials missing everywhere are swapped for the closest stock CS2 material and flagged for checking. Custom decals with no CS:GO source are left as they are and flagged instead, as is anything whose closest stock match is not a decal; stickers are never used as substitutes.
- create a point_servercommand and point a logic_auto towards it, to set mp_freezetime 0 and mp_roundtime 600 OnMapSpawn. If a map only has 1 type of spawn (only info_player_counterterrorist or _terrorist) create a game_player_equip which will equip a knife, make it run OnMapSpawn. (Skipped when the map already has a game_player_equip that gives a knife on spawn, so players don't get a second one.)
- player_speedmod → script `Speed_n` (ground speed driven from the player's keys).
- Stock CS:GO sounds used by ambient_generics are pulled out of CS:GO's VPK into the addon with soundevents.
- env_sky: a sky that CS2 doesn't have is rebuilt from the six CS:GO faces into an equirect panorama (HDR skies tone mapped). Sky brushes the importer dropped come back as moondome boxes.
- **Sky shells out of vis** (`skyvis.py`). Moondome and tools/skybox meshes are huge surfaces, and the vis compile voxelises every vis face at 8 units, so they can be half the Voxelize time (mg_mario_party: 19.2M nodes, 103 s). For each shell, the rest of the world (minus sky shells and pass-through tool faces) is voxelised at 16 units over its box and flood-filled from outside. If the spawns / teleports inside can't be reached, the room is sealed by its own walls, so the shell gets **Exclude from Vis** (it still renders). Shells a room needs, or with no spawns / teleports inside, are left alone.
- visibility_hints: one Lowest over the whole map including the void, Low boxes over cells with geometry, Medium only in the densest cells.
- A report of excluded cosmetic entities (point_spotlight, func_dustmotes…) and 3D skyboxes, which need a separate skybox map in CS2.
- **Stationary lights.** CS:GO lights import as Static, which leaves weapons and players black. The world is voxelised and flood-filled into sealed compartments. Each compartment gets at least one light switched to `directlight 3` (Stationary; in the FGD 3 = Stationary and 2 = fully Dynamic), smallest rooms first. More lights are added only to cover the rest of a room. Ranges are trimmed so no spot is inside more than 4 stationary lights. A compartment open to sky is left to light_environment, if the map has one. A sealed room with spawns or teleport destinations but no light gets a new stationary light_omni2.
- **Daylight (indoor maps that are still dark).** `daylight` pass: adds a stationary light_environment using the map's env_sky and picks the sun angle that reaches the most floor. Every ceiling / roof mesh between the playable floors and the sky gets "Disable Shadows" so sun and sky light reach inside; walls still cast shadows. If the map has no light probe volumes it adds env_combined_light_probe_volumes over the playable space; without them players and weapons get no indirect light. It also raises post_processing_volume maxexposure to 2. Use it when stationary lights alone leave a map too dark.
- **env_laser / env_beam.** CS2 can't spawn them. Each becomes a never-solid func_brush between its end points: LaserTarget for lasers, LightningStart/End for beams, matched case-insensitively. It is drawn as crossed double-sided quads with a self-illuminated laser material in the beam's colour. A mutual laser pair is drawn once. A CS:GO beam with no name starts on. TurnOn/TurnOff/Toggle become Enable/Disable/Toggle. No damage is added; a damaging laser with no trigger_hurt along it is flagged.
- **Alpha.** Materials that were $alphatest/$translucent in CS:GO but imported opaque get F_ALPHA_TEST/F_TRANSLUCENT with a mask from the texture alpha.
- **Radar.** Rendered from the geometry. Only floors you can stand on are drawn (the space above them has lights, spawns or teleports, or is an enclosed non-sky room), shaded by height, with walls outlined. Output: `panorama/images/overheadmaps/<map>_radar_psd.png` + `.vtex`, plus game `resource/overviews/<map>.txt`.
- A missing-model report.
- Listed in the log's TO CHECK lines but not converted: trigger_gravity, player_speedmod, env_screenoverlay, point_clientcommand, game_ui, VScripts.

## Follow-up passes on a map you've already edited in Hammer
`stage_d.py <addon> <root> beams,lights,alpha,radar,daylight,skyvis` runs only those passes on the current vmap. It keeps your Hammer edits and appends to the cleanup log.
`stage_d.py <addon> <root> daylight` is the dark-indoor-map fix above.
Map-specific script gates (e.g. mg_fred_all's `EnableDamage`) go in `maps/scripts/<addon>_io.js`: `Instance.OnBeforePlayerDamage` returns `{ abort: true }` to cancel a hit, `Instance.OnRoundStart` resets per-round state, and a trigger fires `RunScriptInput <name>` on `<addon>_io_script`.

## Standard prompt (paste into a new Claude session in the "cs2 mapping" project)

> Port these CS:GO maps to CS2 with my cs2port pipeline: **<map names, or "the N smallest BSPs in C:\source1\bspsrc-windows\mg maps that don't have an addon yet">**.
> First check each map against `C:\source1\cs2port\existing_ports.txt` and the internet (Steam Workshop, GameBanana) for an existing CS2 port, and tell me about any you find before porting them. Strip version/bloat (`_v2`, `_final`…) from addon names, and add each map you start to existing_ports.txt as `<addon> [in progress] [skink]`.
> The tools and instructions are in the github.com/skink52/cs2portdocs repo (read its CLAUDE.md) and on my PC in `C:\source1\cs2port\tools`. Use them in your workspace and do stage A for every map. Add each one to `C:\source1\cs2port\queue.txt` and tell me when to run `run_import.bat`.
> When I say it's done, read `C:\source1\cs2port\logs`. For each map, do stage C on the vmap, the extra fixes you've been doing for me (moondomes for dropped sky brushes, vis hints, a radar for every map, loading-screen credit "original map by <author> cs2 port by skink52"), and anything map-specific the log flags.
> Back up the vmap to `csgo_addons\prefabs+backups\` first. Keep Hammer closed until you say you're done. Only send changed files.
> When the maps are ready, put them in `build_queue.txt` and tell me to run `run_build.bat` (stage D). When I say it's done, read the build logs and fix anything that failed.
> Record each port in the cs2portdocs repo (`ports/<addon>/` README, cleanup log and scripts, plus a CHANGELOG line) and push it.
