# cs2port: the CS:GO → CS2 map port pipeline

> **AI-generated code.** These tools were written by Claude (an AI agent) for skink52's CS:GO to CS2 map ports, not hand-written.

On the PC they live in `C:\source1\cs2port\tools` (this repo's `tools/` folder). Claude runs them in its cloud workspace and reads and writes
the PC through the linked-computer file tools. Hammer must stay closed while Claude edits a map. Paths below are the PC paths; see
[setup.md](setup.md) for how the repo maps onto them. Every tool with its usage line is in the tool index, [tools/README.md](../../tools/README.md).
On the PC this file is `C:\source1\cs2port\cs2_port_pipeline.md`.

## Quick start for an agent

1. Duplicate check: `python3 tools/ports.py check <existing_ports.txt> <name>...` plus a web search (Steam Workshop, GameBanana). Report hits before going on.
2. Stage A: `OUT=<dir> BSPSRC=<bspsrc.sh> python3 tools/prep.py <bsp>... [bspname=addon] [--ports=existing_ports.txt]`. Needs `tools/addon_template/`
   and BSPSource (see [setup.md](setup.md#cloud-workspace)). Output: `OUT/<addon>/pc/...`, `OUT/<addon>/manifest.json`, `OUT/<addon>/zips/`.
3. Send the files with `device_commit_files` using the manifest pairs, add the map to `existing_ports.txt` (`ports.py add`) and append `addon [vmfname]` to `queue.txt`.
4. The mapper runs `run_import.bat` (stage B).
5. Stage the working root (`<root>`, layout in [setup.md](setup.md#cloud-workspace)): the addon's content folder, the VMF, the VPKs.
6. If material paths had spaces → `matnames.py`.
7. Stage C: `python3 tools/stage_c.py <addon> <root>`; then, on its output: `disprestore.py` if the import log has "missing a needed subkey" (it needs a world mesh
   as a template, which the importer's vmap may not have until the prefab merge), `skysplit.py` if the map had a `sky_camera`, `stage_d.py … gameui` if it
   has game_ui, `laserhurt.py` if the log flags damaging lasers, `glowfix.py` if the map has parented glows. A NEED line lists CS:GO files stage C couldn't
   find: copy them from the extracted CS:GO content (`<CS2>\csgo`) into `<root>/embedded/<addon>/` and rerun (no archive chunks needed).
8. Back up the PC's `.vmap`, then copy back `<root>/out/<addon>/` (content) and `<root>/out/<addon>_game/` (game) — only changed files.
9. Write `build_queue.txt` and ask the mapper to run `run_build.bat` (stage D build); read `logs\` afterwards.
10. Record the port: `ports/<addon>/` README + cleanup log + scripts, a `CHANGELOG.md` line, `CAPABILITIES.md` if something new became possible.

## Who does what

| Stage | What happens | Who |
|---|---|---|
| A. Prep | BSPSource decompile with embedded files unpacked (`bspsrc` extracted from your jlink image, run on Java 21). VMF renamed to the addon name. **Hammer re-save fix** (`hammer_resave.py`) adds versioninfo/viewsettings/cordons, editor blocks and side `rotation`, and rewrites planes and axes at %g precision with upper-case materials. The result matches a real Hammer save structurally. func_illusionary (on Valve's import exclusion list, so it would vanish) becomes a never-solid func_brush. Materials and models are packed into `C:\source1\cs2port\assets\<addon>.zip` (plus `.2`/`.3`/`.4.zip` for big maps, each under ~14 MB: see the transfer limit in [ai-workflow.md](../reference/ai-workflow.md#transfer-limits-and-traps)), and `run_import.bat` unpacks them into `csgo\` (files that already exist are never overwritten). Claude doesn't need access to the `csgo` folder. The decompiled embedded files go to `C:\source1\maps\<addon>_embedded.zip` as a backup (one file instead of hundreds to transfer; stage C re-extracts them from the BSP into `<root>/embedded/<addon>`). Pakfile entries stored with an absolute path (`c:/…/csgo/maps/x.nav`) are cut back to the part after `csgo/`. Sounds go to `<addon>\sounds\` with cleaned names (`maps\<addon>_sound_renames.json`). Other embedded files go to the addon. The addon is created from `tools/addon_template/` (a copy of Valve's `addon_template`, see [setup.md](setup.md)), the same way the Workshop Tools launcher does it. | Claude |
| B. Import | Double-click `C:\source1\cs2port\run_import.bat`. For each line in `queue.txt` (`addon [vmfname]`) it re-renames `vpk.signatures` if Steam restored it, unpacks `assets\<addon>*.zip` into `csgo\` with `tar -k` (log `logs\<addon>_assets_unpack.log`), runs `import_map_auto.py` (Valve's importer without the Enter prompt), then `post_import_cleanup.py`, which first runs `vmap_refs.py` so the model/material list comes from the `.vmap` and its prefabs rather than the importer's `_refs.txt` (and lists stock CS2 stub materials in `<addon>_stub_materials.txt`). Each `cs_mdl_import` runs under a watchdog: models with a loose `.mdl` but no `.vvd`/`.vtx` are skipped, a run with no output for 120 s (or over 15 min) is killed and listed as stalled, other failures retry up to 3 times (output in `maps\<addon>_mdl_import.log`). The cleanup report ends with **WHY MISSING**: for each failed model or missing texture, the vmap/prefab that used it and same-named files in the CS:GO content or CS2's VPK. Logs go to `logs\`. | **You** (Claude can't run programs on the PC) |
| C. Clean | `stage_c.py <addon> <root>` edits the .vmap directly. It collapses every prefab (lighting/nav/audio/cubemaps/environment/gameplay) into the map with world offsets kept; a 3D skybox prefab stays as a prefab. It then runs the fixes below and writes `maps\<addon>_cleanup_log.txt`. | Claude |
| D. Build | Close CS2/Hammer and double-click `C:\source1\cs2port\run_build.bat`. It compiles every map in `build_queue.txt` from the command line, one at a time, and moves each built .vpk into the game addon before starting the next (see below). Then test in game and report anything odd. | **You** |

## Before porting: duplicate check and names
- Claude checks every requested map against `C:\source1\cs2port\existing_ports.txt` (`ports.py check <existing_ports.txt> <name>...`, which ignores prefixes, `_cs2` and version suffixes) **and** searches the web (Steam Workshop, GameBanana) for a CS2 port that already exists. Any likely duplicate is reported before stage A starts, and that map is not ported unless you say so.
- **Steam Workshop pages: ignore the "removed" banner** (this is the full explanation; the other docs point here). Every Workshop page's HTML contains hidden template text: "This item has been removed from the community because it violates Steam Community & Content Guidelines. It is only visible to you." and "This item is incompatible with Counter-Strike 2." A browser never shows it, but WebFetch's page reader picks it up on healthy items too (checked 17 Oct 2026 against an unrelated public collection). Never report an item as removed or incompatible from that text. An item that really is removed doesn't load at all for an anonymous visitor; a page that shows visitor/subscriber stats is live. (A Claude session wrongly reported the mg_smee_tower_cs2 item as removed this way, twice.)
- Addon names are the BSP name with version/bloat stripped: `_v2`, `_v1_2`, `_b3`, `_rc1`, `_final`, `_fix`, `_beta`, `_csgo`, `_hdr`, `_ws`… (`mg_x_v2_final` → `mg_x`). A different name can be forced with `bspname=addonname`.
- Each map Claude starts is added to `existing_ports.txt` as `<addon> [in progress] [skink]` (`ports.py add <existing_ports.txt> <addon>`). A successful build changes it to `[in progress, built]`. `[briar]` lines are maintained by hand; `[ported]`, `[*original*]` and `[ext. port]` lines are never changed.

## Stage C fixes (automatic; the importer's main .vmap is keyvalues2 text and is saved back as binary)

Step keys in run order (from `stage_c.run()`; `run_pass.py` takes these names): `merge, io, wall, equip, push, cmd, roundcfg, score, speed, gravity, dead,
steam, sounds, soundscripts, doors, overlays, overlayfix, facescale, sky, skyvis, vis, beams, lights, alpha, probes, radar, assets, matflags` (plus `overlaydepth`
and `physpush` when named).
`alpha` and `assets` need CS2's `pak01_dir.vpk` staged as `<root>/vpk/cs2_pak01_dir.vpk`. `skyvis` runs only when `vis` isn't in the list.

- **Prefabs** (`merge`): every prefab (lighting/nav/audio/cubemaps/environment/gameplay) collapsed into the map with world offsets kept; a 3D skybox prefab stays a prefab.
- **Dropped outputs** (`io`): puts back outputs the importer dropped (diffs every entity's outputs against the decompiled VMF), and reports the cosmetic
  entities the importer leaves out (point_spotlight, func_dustmotes, func_precipitation, env_lightglow, fog, colour correction). Then `io_fixups`:
  logic_auto "Global State to Read" `is_pc` is cleared (CS2 never sets it, so the logic_auto never fired), and output targets that match an entity
  only case-insensitively get the exact name (stage D `iofix` for maps already past stage C).
- **func_wall_toggle** (`wall`) → func_brush (Solidity Toggle; StartDisabled from "Starts Invisible"). TurnOn/TurnOff → Enable/Disable.
- **game_player_equip** (`equip`) → weapon0..weapon21 slots, and `Use` inputs on them → `TriggerForActivatedPlayer`. Equips without "Use Only" (CS:GO ran them
  on every spawn) are run by the io script one tick after `OnPlayerReset`: strip first if flagged, then give only the items the player doesn't already have.
- **trigger_push** (`push`) → trigger_multiple plus `maps/scripts/<addon>_io.js` push zones (`PushIn_n`/`PushOut_n`) that hold CS:GO "set speed" behaviour
  (clamped to 3500). Names, filters and Enable/Disable are kept.
- **point_servercommand** (`cmd`) → script `Cmd_n`, with "Ported to CS2 by skink52" added after CS:GO port credits.
- **Round setup** (`roundcfg`): a point_servercommand `port_servercommand` + logic_auto set `mp_freezetime 0` / `mp_roundtime 600` OnMapSpawn. Maps with
  only one team's spawns get `port_knife_equip` (skipped if a spawn equip already gives a knife).
- **game_score** (`score`) → script `Score_n`.
- **player_speedmod** (`speed`) → script `Speed_n` (ground speed driven from the player's keys).
- **trigger_gravity** (`gravity`; does nothing to players in CS2) → trigger_multiple whose OnStartTouch fires script `Gravity_<scale>`; names, filters and
  Enable/Disable are kept. While a player is airborne the script adds back `(1 - scale) * 800 * dt` of vertical velocity each tick. Leaving the trigger fires
  `Gravity_1` (OnEndTouch), so a zone is low-gravity only while you are inside it; a respawn also resets it. `gravity.py`; stage D runs it as `gravity` on an
  already-cleaned map and adds the section to the existing `<addon>_io.js`.
- **Dead entities** (`dead`): env_sun removed; point_viewcontrols that no output targets (and unnamed ones) removed; prop_hallucination → prop_dynamic (if
  targeted) or prop_static; func_breakable_surf → func_breakable (glass); func_physbox_multiplayer → func_physbox. Listed as TO CHECK, not converted: env_spritetrail, env_screenoverlay, point_clientcommand, game_ui (use the stage D `gameui` pass),
  logic_script, env_entity_igniter, func_precipitation, env_fog_controller, entities with a `vscripts` key, VScript inputs in I/O (RunScriptCode,
  RunScriptFile, CallScriptFunction), and a CS:GO 3D skybox (`sky_camera`), which needs a separate skybox map in CS2 (`skysplit.py`).
- **Sounds** (`sounds`): ambient_generic custom sounds → soundevents in `soundevents_addon.vsndevts` ("Play everywhere" uses the stereo base; others a 3D
  event with the original radius). Stock CS:GO sounds are pulled out of CS:GO's VPK into the addon. WAVs that aren't 16-bit PCM are re-encoded (ADPCM is
  flagged). Looping wavs with no cue marker get one (at the `smpl` loop start if there is one), since CS2 only loops wavs with markers.
- **Soundscript names** (`soundscripts`, `tools/soundscripts.py`): Source 1 soundscript names (`MetalGrate.ImpactHard`) in any entity keyvalue, or in a
  CS:GO door's noise1/noise2, are silent in CS2. Each becomes a soundevent with the same name (no entity changes), from the map's own
  `maps/<map>_level_sounds.txt` / `scripts/*sound*.txt` first, then CS:GO's `scripts/game_sounds_manifest.txt` files: every wave (rndwave → a list),
  volume, pitch, and a range from the soundlevel (75 dB = 1250 u; SNDLVL_NONE = everywhere). Waves come from the addon, stock CS2 or CS:GO (re-encoded
  to 16-bit PCM, smpl loops cued). Names starting `weapon`, `player`, `radio`, `ui.`, … are left alone (an addon event would replace the stock one
  map-wide) and listed in TO CHECK. Method from cs2-slop-porting.
- **Door sounds** (`doors`): the importer drops func_door / func_door_rotating / func_movelinear `noise1`/`noise2`. They are read from the VMF, made into
  soundevents (addon file, stock CS2 sound, or extracted from CS:GO's VPK), and each door gets a `point_soundevent` per sound (source entity = the door;
  unnamed doors become `port_door_N`) started from OnOpen/OnClose (noise1) and OnFullyOpen/OnFullyClosed (noise2).
- **env_steam** (`steam`, `tools/steam.py`): doesn't exist in CS2. Each becomes an `info_particle_system` playing `particles/port_steam/<values>.vpcf`, built
  from its keyvalues the way Source 1 drew it: lifetime JetLength/Speed, Speed along the entity's forward axis with ±SpreadSpeed sideways,
  StartSize→EndSize, ±rollspeed spin, fade in/out at renderamt alpha, rendercolor when Emissive (self-illuminated), light grey otherwise. Type 1 (heat
  wave) is a refracting sprite with a generated soft normal map. InitialState → `start_active`; TurnOn/TurnOff → Start/Stop (Toggle and the value inputs
  are flagged). env_steams the importer dropped are added back from the VMF. Untested in game: check direction and density on the first port that has one.
- **Physics prop pushing** (`physpush`, opt-in, `tools/physpush.py`): every prop_physics(_multiplayer/_override) gets a name and a mass (CS:GO `.phy` mass
  x massScale, 50 if no .phy) and the io script pushes them from player contact: speed into the face x 20/(20+mass), min 10 u/s, some spin off-centre;
  props already moving > 400 u/s are left alone and damage from a listed prop moving < 150 u/s is cancelled. Stage C lists maps with physics props in TO
  CHECK; run it when pushing feels wrong in game. Idea from cs2-slop-porting's `push_mass.js`.
- **Material flags** (`matflags`, `tools/texfix.py`): `$additive` → `csgo_unlitgeneric` `F_BLEND_MODE 4` (`LIT_ADDITIVE = True` keeps lightmapped ones lit with
  `F_TRANSLUCENT` + `F_ADDITIVE_BLEND`, but a black additive material then draws opaque black in Hammer), CS:GO water (`%compilewater` / `$abovewater`)
  → `F_TRANSLUCENT` at opacity 0.55 with back faces (csgo_complex can't refract; the importer left it a solid sheet), `$alpha` → `F_TRANSLUCENT` with
  that opacity, `$selfillum` → `F_SELF_ILLUM` (mask from the texture alpha), `$nocull` → `F_RENDER_BACKFACES` (+
  `F_DONT_FLIP_BACKFACE_NORMALS` on lit shaders), `$ssbump` bump maps rebuilt as real normal maps (`*_ssbn.png`).
- **Static overlays** (`overlays`) → `csgo_static_overlay` with a translucency mask taken from the original alpha.
- **Static overlay geometry** (`overlayfix`, `tools/texfix.py`): the importer's 2x2 placeholder quads are rebuilt from the VMF (texture size x `$decalscale`
  for infodecals, uv extent for info_overlays), laid on the brush face under the decal and the right way up. Hand-edited overlays are skipped. Overlays with
  a projection depth >= 32 are flagged; `overlaydepth` (stage C or D) sets all to 8.
- **Face texture scales** (`facescale`, `tools/texfix.py`): absurd brush-face scales/shifts are restored from the matching VMF side and the stored texture
  coordinates rewritten from the CS:GO texture size. No-op on faces that are already right. A face matches a VMF side when the normals agree
  (near-axis normals snapped) and every corner is within 0.6 u of the side's plane: imported corners can sit ~0.1 u off, which at map coordinates in
  the thousands moved a one-corner plane distance by 1.5-3 u and skipped the face. Matching order, first hit wins: same plane + material inside the
  brush (slivers thinner than 1 u by their corners only; a vmap material missing from the VMF uses the one VMF material with the same file name) →
  a moved copy of a same-size VMF brush (shift corrected, texture lock) → same plane outside the brush → corners up to 2.5 u off (rounded corners,
  centre inside the brush) → a flat face pushed up to 6 u off its side → a displacement's base face (coordinates from the face position projected onto
  the base plane) → absurd scales only: another material's side on the same plane. Unmatched slivers with an absurd scale take their material's usual
  scale. Texture size = the addon's converted colour texture (what Hammer draws), CS:GO VTF as fallback. Faces still absurd are listed with what the VMF
  says for their material.
- **Sky** (`sky`): an env_sky that CS2 doesn't have is rebuilt from the six CS:GO faces into an equirect panorama (HDR skies tone mapped). Sky brushes the
  importer dropped come back as `toolsskybox` boxes: the sun and sky light bake through toolsskybox but not through a moondome (ttt_minecraft's open
  areas under moondome shells baked pitch black), and a moondome would hide a 3D skybox. `MOONDOME_SHELLS = True` in stage_c.py brings back csgo_moondome
  boxes (the panorama is then built even when env_sky is a stock CS2 sky). Stage D `skyshell` switches existing moondome shells to toolsskybox. (CS2's new `toolsskyboxocclude` material may replace moondome shells: untested, see
  [cs2-gotchas](../reference/cs2-gotchas.md#sky-and-world).)
- **Vis: hints fitted to the play space and sky shells out of vis** (`vis` = `visfit.py`; `skyvis` = the older shell-only pass). Playable air is the empty
  space (16-unit voxels; 24 or 32 on very big maps) connected to a spawn or teleport destination, plus sealed rooms holding buttons, doors, triggers, trains
  or weapons. The **walkable band** is playable air up to 160 units above something to stand on. Hints sit on a 256-unit grid: **Low** over the walkable band,
  **Lower** (`hintType` 8, fewer initial clusters) over the rest of the playable air next to geometry (high ceilings, shafts), and one **Lowest** over the
  whole map, so the void, sealed-off rooms and open sky fall to Lowest. No Medium on ports (these Source 1 maps have no dense vis geometry; Medium is only
  for original multi-arena maps, see [conventions.md](conventions.md#multi-arena-maps-original-minigame-addons)). Low and Lower boxes never overlap, and
  they are merged down to about 100 boxes or fewer. `all_lower` (stage D `visfit_lower`) makes the Low boxes Lower too, for maps whose vis merge stalls.
  Moondome / tools/skybox shells get **Exclude from Vis** (they still render) unless they border playable air that is open once every sky shell is gone. That
  test uses only vis-relevant geometry: Valve's docs say `toolsnodraw` is ignored by vis and its inside/outside test, and clips, triggers and meshes already
  excluded from vis don't count. Big shells are expensive because vis voxelises every vis face at 8 units (mg_mario_party: 19.2M nodes and 103 s, then 3.6M
  nodes and 23 s with its 64 shells excluded).
- **env_laser / env_beam** (`beams`). CS2 can't spawn them. Each becomes a never-solid func_brush between its end points: LaserTarget for lasers,
  LightningStart/End for beams, matched case-insensitively. It is drawn as crossed double-sided quads with a self-illuminated laser material in the beam's
  colour. A mutual laser pair is drawn once. A CS:GO beam with no name starts on. TurnOn/TurnOff/Toggle become Enable/Disable/Toggle; StrikeOnce becomes
  Enable plus a Disable after the beam's `life`. Stage C adds no damage: a damaging laser with no trigger_hurt along it is flagged; then run `laserhurt.py`
  (below).
- **Probe coverage** (`probes`). Static `func_breakable` and `func_brush` meshes (not parented to a door, mover, train, rotator or physics object) are lit from light probes, not lightmaps: the **whole mesh** must sit inside an `env_combined_light_probe_volume`, or its lighting is wrong (skink52, 27 Oct 2026). Stage C `probes` lists any that aren't; `stage_d.py … probecover` adds a volume around each uncovered group.
- **Light brightness** (`lights`, with the VMF staged): every light's brightness is rebuilt from its CS:GO `_light` value (`lighting.fix_brightness`,
  same as stage D `lightbright`). Before 30 Oct 2026 stage C only set the importer's `nan` values to 0 (= legacy 1, a 265 `_light`), so every light
  in a map came out the same strength (ttt_minecraft's 50-200 lights all at 265).
- **Stationary lights** (`lights`). CS:GO lights import as Static, which leaves weapons and players black. The world is voxelised and flood-filled into
  sealed compartments. Each compartment gets at least one light switched to `directlight 3` (Stationary; in the FGD 3 = Stationary and 2 = fully Dynamic),
  smallest rooms first. More lights are added only to cover the rest of a room. Ranges are trimmed so no spot is inside more than 4 stationary lights. A
  compartment open to sky (or, on a map with no sky shell, the outdoor space players are in) gets at least one stationary light too, on top of
  light_environment (skink52's rule, 29 Oct 2026), topped up to 3; and light_environment itself goes from Static to Stationary (`directlight 3`), since
  the importer's Static sun lights nothing that moves (mg_jahoukarail_2015 looked unlit). A sealed room with spawns or teleport destinations but no light gets a new
  stationary light_omni2. (Maps still too dark afterwards: the stage D `daylight` pass, below.)
- **Alpha** (`alpha`). Materials that were $alphatest/$translucent in CS:GO but imported opaque get F_ALPHA_TEST/F_TRANSLUCENT with a mask from the texture alpha.
- **Radar** (`radar`). Rendered from the geometry. Only floors you can stand on are drawn (the space above them has lights, spawns or teleports, or is an
  enclosed non-sky room; tested at the centroid and halfway to each vertex, since one point missed faces with a prop on it and left wedge-shaped holes). Each
  floor is painted with its material: the source png/tga from the addon's content folder (or `<root>/embedded/<addon>/materials`) tiled every 128 units,
  world-aligned; stock CS2 materials, whose textures aren't readable from the workspace, get a colour guessed from the name (`radartex.py`: colour words
  first, then grass/dirt/sand/water/concrete/metal/wood/tile/brick…; dev_NN greys). Darker towards the bottom of the map, glass translucent, walls outlined.
  Water planes never set the extent. `pct` trims that percentile off each edge of the floor extent (default 0.5; 0 keeps everything — jb_sides_cs2 needed it).
  `pct` is a Python argument only: `radar.run(m, c, pct=0, tex=radar.textures_for(c))`; stage C and stage D's `radar` use 0.5. Output:
  `panorama/images/overheadmaps/<map>_radar_psd.png` + `.vtex`, plus game `resource/overviews/<map>.txt`.
  - Stacked maps (towers, one spawn directly above another): split into vertical sections like Nuke/Vertigo. `"verticalsections"` in the overview txt with
    `"default"` (image `<map>_radar_psd`) and `"lower"` (image `<map>_lower_radar_psd`), each with AltitudeMin/Max; all sections share pos_x/pos_y/scale.
    Done by hand for mg_smee_tower_cs2 (split at z 2560, 17 Oct 2026); `radar.py` itself still makes one image.
- **Missing materials and models** (`assets`). Missing materials are rebuilt from CS:GO's VPK (VMT from `pak01_dir`, VTF decoded from the archive chunk).
  Water materials → `liquids/nuke_water`. **Stock stubs:** stock CS2 materials Valve shipped unported (compiled against the error shader) count as
  missing and are rebuilt from CS:GO over the stock path; the list comes from `maps/<addon>_stub_materials.txt`, which `vmap_refs.py` writes on the PC
  in stage B (it reads each used stock `vmat_c`; best effort). Materials missing everywhere are swapped for the closest stock CS2 material and flagged for checking. Custom decals
  with no CS:GO source are left as they are and flagged instead, as is anything whose closest stock match is not a decal; stickers are never used as
  substitutes. Models referenced but not in the addon or CS2 are listed. (Player models are already skipped in stage B: `post_import_cleanup.py` skips
  `models/player/` and `maps/<addon>_skip_models.txt`, because they drag in the whole t/ct_animations set and hang cs_mdl_import; swap them for a stock CS2
  character, `characters/models/...`.)
- **Material flags** (`matflags`, after `assets`): CS:GO `$additive` → `F_TRANSLUCENT` + `F_ADDITIVE_BLEND` (lightmapped) or `csgo_unlitgeneric`
  `F_BLEND_MODE 4`; water → see-through `F_TRANSLUCENT`; `$alpha` → opacity; `$selfillum` → `F_SELF_ILLUM`; `$nocull` → `F_RENDER_BACKFACES`.
- **The io script** (end of the run): if any step needs it, `maps/scripts/<addon>_io.js` is generated (`gen_script.py` + `push_tail.js`) and a
  `point_script` `<addon>_io_script` is added. Then `maps/<addon>_cleanup_log.txt` is written, with TO CHECK lines for everything that needs a human look.

## Stage D: command-line build (`build_maps.ps1`)
- `run_build.bat` runs `build_maps.ps1` on `build_queue.txt` (one addon per line, optionally `addon mapname`). `build_maps.ps1 mg_a mg_b` builds just those maps. For assets only from the command line, pass the line as one quoted argument: `run_build.bat "assets mg_x"`.
- **Assets first.** The command-line map build does not compile materials or textures; Hammer normally compiles them when it loads a map. So anything Claude added outside Hammer (laser materials, alpha masks, radar) would be missing, and missing materials are fatal for those meshes. For each addon the script first runs `resourcecompiler -r -i <content addon>/<dir>/*.<ext>` for materials `*.vmat`, models `*.vmdl`, panorama `*.vtex` (radar) and `*.xml`/`*.css` (custom HUDs), soundevents, sounds `*.wav`/`*.mp3` and `maps/scripts/*.js`, logging to `logs\<addon>_assets.log`. Only out-of-date files are recompiled. If a content .vmat that a map vmap (or a model) uses still has no compiled `_c` in `game\`, that map is skipped and the materials are listed; uncompiled leftovers nothing uses are only listed as a note. A queue line `assets <addon>` compiles the assets only, with no map build.
- The pre-pass compiles `maps/scripts/*.js` and `panorama/*.vtex` only. Scripts in the older `scripts/` layout and Panorama `layout/custom_game/*.xml` /
  `styles/custom_game/*.css` (original addons) need `resourcecompiler -f -i <file>` by hand.
- Then it runs `game\bin\win64\resourcecompiler.exe` with Hammer's full-build arguments: `-threads 5 -fshallow -maxtextureres 256 -quiet -unbufferedio -i <content vmap, forward slashes> -noassert -world -rebake_surfacegraph -bakelighting -lightmapMaxResolution 1024 -lightmapVRadQuality 1 -phys -vis -nav -sareverb -sareverb_threads 6 -sapaths -sareverb_threads 6 -sacustomdata -sacustomdata_threads 6 -breakpad -nop4 -outroot %LOCALAPPDATA%\Temp\valve\hammermapbuild\game`.
- **Outroot step** (what Hammer does after a build): the compiler writes `<outroot>\csgo_addons\<addon>\maps\<map>.vpk`. The script waits for the compiler to exit, then copies that vpk to `game\csgo_addons\<addon>\maps\`, checks the size matches, and deletes the temp copy. Only then does the next map start. A stale vpk left in the outroot is deleted before each compile so it can never be copied by mistake. If the game file is locked (CS2 open) it retries, then reports the map as failed with the vpk still in the outroot.
- Maps are built one at a time on purpose. Separate outroots per map would avoid the vpk clash, but the light bake uses the GPU and every build writes shared compiled assets into `game\`, so parallel builds are no faster and risk VRAM or file-lock failures.
- The script refuses to start while `cs2.exe` (CS2 or Hammer) is running, and waits for any other resourcecompiler to finish.
- Logs: `logs\<addon>_build.log`, plus one line per map in `logs\stage_d_done.txt` (OK / FAILED, minutes, exit code).
- Claude writes `build_queue.txt` at the end of stage C (or after follow-up passes) and tells you to run `run_build.bat`. When you say it's finished, Claude reads `logs\` and fixes any compile errors.

## Loading-screen credit
CS2 reads the loading-screen text from `game\csgo_addons\<addon>\maps\<map>.txt` (the same file Hammer5Tools' Loading Editor writes): first line `COMMUNITYMAPCREDITS:`, then the text, e.g. `Original map by <author>` / `CS:GO port by <porter>` (when the map credits one) / `Ported to CS2 by skink52`. No map rebuild needed.

## Loading-screen background images
This is the canonical naming rule; [hud.md](../creation/hud.md#loading-screens) and the gotchas link here.

- **What CS2 loads:** the compiled `panorama/images/map_icons/screenshots/1080p/<map>_png.vtex_c`, then `<map>_1_png`, `<map>_2_png` … (up to `_9`), as a
  slideshow, 4 s each. Ship at least two: with one picture Space Racer and Hellmatch saw none of their art. Single-picture ports (ba_jail_skylight,
  jb_water_prison_cs2) should get a second one.
- **Way 1, what the ports use** (Hammer5Tools' Loading Editor layout): `content\csgo_addons\<addon>\panorama\images\map_icons\screenshots\{1080p,720p,360p}\<map>_png.png`
  + `<map>_png.vtex` (height 1080/720/360, same vtex as a radar but `linear` colour space, max dimension 2048), more images as `<map>_1_png`, `<map>_2_png`…
  Compile them with `run_build.bat "assets <addon>"` (the panorama pass is recursive).
- **Way 2, what the original addons use:** a plain `screenshots/1080p/<map>.png`, `<map>_1.png` … with no `.vtex`, referenced from a never-shown rule in the
  HUD stylesheet; the resource compiler turns `<map>.png` into the same `<map>_png.vtex_c` (Space Racer TESTING C6). Needs a `custom_hud_layout`.
- Not recorded per port: which ports' slides have been seen in game. Note it in `ports/<addon>/README.md` when the mapper confirms one.
- Pictures: Steam's image CDN is blocked from Claude's workspace, so Workshop images have to be saved on the PC first (the mapper drops them in a linked
  folder); the 637x358 thumbnails Steam shows on the item page are upscaled, the full-size originals look better. Safe area and crop: [hud.md](../creation/hud.md#loading-screens).

## Follow-up passes (after stage C, or on a map you've already edited in Hammer)

All of these keep your Hammer edits and append to the cleanup log. Exact usage lines: [tools/README.md](../../tools/README.md).

- `stage_d.py <addon> <root> pass[,pass...]`: passes `beams, lights, lightbright, alpha, radar, daylight, skyvis, visfit, visfit_lower, visfit_lean, gravity,
  equipitems, overlayfix, overlaydepth, facescale, matflags, probes, probecover, steam, soundscripts, physpush, gameui, physlaunch, renderamt, ventlight, doorsolid, doorhinge, doorparent, iofix, tesla, overlays, probefill, probedetail, skyshell, water` (`physpush`, `gameui` and `physlaunch` add their section to the existing `<addon>_io.js`). Stage C's `vis` step is called `visfit` here. sky, sounds, doors, assets, equip etc. aren't stage D passes: use `run_pass.py`.
  - `visfit` replaces the map's vis hints with ones fitted to the play space and takes unneeded sky shells out of vis. `visfit_lower` does the same with
    Lower instead of Low everywhere (for a map whose vis merge stalls).
  - **Daylight** (`daylight`, stage D only; for indoor maps that are still dark after stage C): adds a stationary light_environment using the map's env_sky
    and picks the sun angle that reaches the most floor. Every ceiling / roof mesh between the playable floors and the sky gets "Disable Shadows" so sun and
    sky light reach inside; walls still cast shadows. If the map has no light probe volumes it adds env_combined_light_probe_volumes over the playable space;
    without them players and weapons get no indirect light. It also raises post_processing_volume maxexposure to 2.
- `run_pass.py <addon> <root> step[,step]`: any stage C step (stage C key names) on the current vmap, e.g. `alpha,assets` once the CS2 VPK is available, or `sky`.
- `run_c.py <addon> <root> [steps]`: stage C when CS2's `pak01_dir.vpk` isn't staged. Its default list leaves out `alpha`, `assets`, `doors`, `overlayfix`,
  `facescale`, `matflags` and `probes`; run those with `run_pass.py` later.
- `laserhurt.py <vmap in> <csgo vmf> <vmap out>` (after stage C): a `trigger_hurt` box along every CS:GO env_laser that did damage and has no trigger_hurt
  yet — skink52's rule from 24 Oct 2026 is that damaging lasers are recreated even where the original relied on the laser itself. Same start state as the
  beam; Enable/Disable/Toggle sent to the beam are copied to `<laser>_hurt`.
- `glowfix.py <vmap in> <vmap out> <addon content root>` converts parented env_particle_glows to following glow particles (see cs2-gotchas). Run it on any
  map that has them; weapon-parented ones also need the glow follow section in `<addon>_io.js` (template: `ports/mg_metal_course_level_2/scripts`).
- `gameui` (stage D): game_ui → script. Activate/Deactivate outputs become `RunScriptInput GameUIOn_<name>` / `GameUIOff_<name>` on the io script; while a
  player holds it the script polls their keys every tick and fires the game_ui's own outputs (Pressed/Unpressed*, XAxis/YAxis/AttackAxis/Attack2Axis,
  PlayerOn/PlayerOff) with the original targets and delays. Freeze Player, +Use / Jump deactivate are kept; Hide Weapon and FieldOfView aren't (TO CHECK).
  The game_ui entities are removed. mg_pirates (22 cannons and boats, 29 Oct 2026).
- `renderamt` (stage D; stage C step after `dead`): renderamt 255 wherever rendermode is Normal. CS:GO ignored renderamt then; CS2 applies it, so
  props came out see-through (ttt_cg_skyscraper_2017's office chairs at 180).
- `water` (stage D): CS2 only treats water as water (swimming, splashes) inside a **func_water**. Water meshes (material name contains "water") in the
  world or a func_water_analog are grouped by contact and each group becomes one func_water. Groups deeper than 64 u get an underwater
  post_processing_volume (`lighting/postprocessing/postprocess_filmic_underwater.vpost`, copied from ba_jail_seaside; master 0, exposure 0–0.3, fade 0.1,
  spawnflags 4097, toolsnodraw) from 16 u under the bottom to **80 u below the surface** (the volume tests the player's feet). A master
  post_processing_volume (`filmic_default.vpost`, master 1) is added if the map has none.
- `doorsolid` (stage D): func_door / func_door_rotating flagged "Non-solid to Player" (spawnflags 4) are solid in CS2. The door's meshes move to a
  never-solid func_brush `<door>_vis` parented to the door, the door keeps a 2-unit nodraw cube on its hinge, so it looks and moves the same but
  blocks nothing, as in CS:GO (ttt_minecraft's hut doors: the open panel left 32 units, too narrow to pass). Double doors sharing a name are split
  (`<name>_2`, outputs copied).
- `ventlight` (stage D): crawl-space vents capped by func_breakable grates (thin, ≤160 u, not glass) bake pitch black in CS2. Each duct behind a cover
  (opening no wider than the cover, ≥48 u deep) gets a dim, unshadowed stationary light_omni2; the covers get Disable Shadows.
- `lightbright` also handles CS:GO lights with `_fifty_percent_distance` (and linear/constant attenuation): vrad falls back to linear falloff for them
  (I x 100 / d), and the importer gave them ~8x the brightness of a normal light and a 9,000-17,000 unit range. They are matched to CS:GO at 128 units
  with an inverse-square range of 1600 x sqrt(legacy) (ttt_cg_skyscraper_2017: lower floors much brighter than in CS:GO).
- **Missing gibs and model materials** (after a build): `tools/gibfix.py <build log> <out refs> [addon vmdl …]` turns every
  `Failed loading resource` in the build log into a refs file (gib models → `.mdl`, model materials → `.vmt`, a material whose texture never converted
  → its `.vmt`); a vmdl given on the command line whose propdata base is Metal/Wooden/Glass and that has no gibs gets CS:GO's generic chunks
  (models/gibs/metal_gib1-5, wood_gib01a-e, glass_shard01-06). Put the refs at `maps\<addon>_fix_refs.txt`; the mapper runs
  `run_fixrefs.bat <addon>` (cs_mdl_import + source1import via `modelsfromrefs.py`) and then the build. CS2 has no `models/gibs` at all, and some stock
  CS2 models point at gibs it never shipped (watermelon01a → props_junk/watermelon01_chunk*): importing the CS:GO ones at the same path fixes those too.
  The build log is also the check that imported models' textures exist (the cleanup report only covers the map's own refs).
- `physlaunch` (stage D; stage C step `launch`, before `push`): CS:GO cannons that fire a physics ball with a physics-only trigger_push (a relay
  ForceSpawns a point_template ball and Enables the push for a moment). CS2's trigger_push doesn't throw physics objects, and the `push` step used to
  turn these into player pushes. The Enable becomes `RunScriptInput Launch_<pusher>` 0.05 s later; the script takes the new ball near the cannon, puts it
  at the muzzle (the info_teleport_destination on the barrel) and gives it 2000 u/s along the barrel. mg_pirates (18 cannons, 29 Oct 2026). Physics-only
  pushes that don't fit the pattern stay trigger_push and are listed in TO CHECK.
- `waterblend.py <main.vmap> <skybox.vmap> <main out> <skybox out> <addon content root> <name> <cs2 pak01_dir.vpk> [fade]` (after `skysplit.py`, for maps
  with water in the 3D skybox; method from the cs2kz mapping guide, "Infinite water"): the main map renders over the 3D skybox, so its water must fade
  out at the edges. The water material (stock csgo_water_fancy, decompiled with `vmatc.py`) is copied to `materials/<name>/<name>_water.vmat` with
  `g_vMapUVMin/Max` = the water's XY extent and `g_flSkyBoxFadeRange` = fade (0.1), and to `<name>_water_skybox.vmat` (no fade) for the skybox. Main-map
  meshes under the water are cut back out of the fade band (they would hide the skybox water), the skybox sea bed goes down 1024 world units so the fog
  hides it like the main map's, and skybox probe volumes whose edges cross the water are grown over all of it.
- `skysplit.py <map.vmap in> <main out> <skybox out> <map name> [x0,y0,z0,x1,y1,z1]`: moves an old 3D skybox into `<map>_3dskybox.vmap` (everything inside
  the box, or the group of meshes around the sky_camera when no box is given), keeps light_environment / env_sky / env_fog_controller in both, sets
  `mapUsageType skybox`, adds the `skybox_reference` to the main map, and switches moondome shells in both maps to `toolsskybox` (a moondome hides the
  3D skybox). `skysplit.py --sky <in> <out>` does only that swap, for a map already split. Build it as its own queue line (`<addon> <map>_3dskybox`) before the main map.
  Check the result with `vmap_preview.py` and give a box when the auto box grabs playable space.
- `disprestore.py <vmap in> <bsp> <vmap out> [x0,y0,z0,x1,y1,z1 ...]` rebuilds displacements the importer dropped. The import log shows each one as "Found a
  displacement missing a needed subkey." (24 Oct 2026: mg_kohztec_course 61 (all, fixed), de_nuketown 152 (fixed, old 3D skybox skipped), mg_faohu_course 2).
  After every import, grep the log for that line. Run it on the stage C output, not the importer's vmap (it copies an existing world mesh as its template). It reads dispinfo/dispverts from the BSP and adds each as a closed mesh: the displaced surface with the
  CS:GO texture projection, toolsnodraw sides and a flat back. Materials with no CS2 copy get a stand-in from its `SUB` table; custom ones can be built from
  the BSP pakfile with `assets.write_vmat`. The optional boxes skip displacements centred in them (an old 3D skybox).
- `matnames.py <addon> <root>`: importer-sanitised material refs (spaces → underscores) back to the addon's real file names; run before the `assets` pass (see cs2-gotchas).
- `vmap_preview.py <vmap> <out.png> [box]`: top-down + four corner renders of any vmap (importer text or binary), to check a port or a generated map without Hammer.
- `node create/test/mock_point_script.mjs <addon>_io.js` and `sh create/test/tscheck.sh <addon>_io.js`: run / type-check a map script before the build
  (see [create/README.md](../../create/README.md)).
- **Unattended runs:** `run_import_then_build.bat` = stage B, then wait for `build_go.txt`, then stage D. Claude does stage C in between and writes the flag
  file; a scheduled check reads the logs afterwards.
- Map-specific script gates (e.g. mg_fred_all's `EnableDamage`) go in `maps/scripts/<addon>_io.js`: `Instance.OnModifyPlayerDamage` returns
  `{ abort: true }` to cancel a hit (mg_fred_all still uses the deprecated `OnBeforePlayerDamage`), `Instance.OnRoundStart` resets per-round state, and a
  trigger fires `RunScriptInput <name>` on `<addon>_io_script`.

## Standard prompt (paste into a new Claude session in the "cs2 mapping" project)

> Port these CS:GO maps to CS2 with my cs2port pipeline: **<map names, or "the N smallest BSPs in C:\source1\bspsrc-windows\mg maps that don't have an addon yet">**.
> First check each map against `C:\source1\cs2port\existing_ports.txt` and the internet (Steam Workshop, GameBanana) for an existing CS2 port, and tell me about any you find before porting them. Strip version/bloat (`_v2`, `_final`…) from addon names, and add each map you start to existing_ports.txt as `<addon> [in progress] [skink]`.
> The tools and instructions are in the github.com/skink52/cs2mapping repo (read its CLAUDE.md) and on my PC in `C:\source1\cs2port\tools`. Use them in your workspace and do stage A for every map. Add each one to `C:\source1\cs2port\queue.txt` and tell me when to run `run_import.bat`.
> When I say it's done, read `C:\source1\cs2port\logs`. For each map, do stage C on the vmap, the extra fixes you've been doing for me (moondomes for dropped sky brushes, vis hints, a radar for every map, loading-screen credit "original map by <author> cs2 port by skink52"), and anything map-specific the log flags.
> Back up the vmap to `csgo_addons\prefabs+backups\` first. Keep Hammer closed until you say you're done. Only send changed files.
> When the maps are ready, put them in `build_queue.txt` and tell me to run `run_build.bat` (stage D). When I say it's done, read the build logs and fix anything that failed.
> Record each port in the cs2mapping repo (`ports/<addon>/` README, cleanup log and scripts, plus a CHANGELOG line) and push it.
