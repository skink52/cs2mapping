# Setup: the PC, and the cloud route

**The supported route is everything on the Windows PC** (since 2 Nov 2026): Claude Code runs from the workspace folder and runs the Python
tools, Valve's importer and `resourcecompiler` itself, normally through [autoport](../../autoport/README.md). Most of this page is that setup:
where each repo file goes, the folder layout, the junctions, and [what has to be installed](#requirements).

**The cloud route is the older alternative and still works:** the Python tools run in Claude's cloud workspace, files move through the
linked-computer file tools, and the mapper double-clicks the batch files for the steps that need Valve's tools, because on that route Claude
can read and write the PC's folders but can't start programs there. What differs is in [Cloud workspace](#cloud-workspace);
[pipeline.md](pipeline.md) says "on the PC" / "in the cloud" wherever a step differs.

## Where the repo goes on the PC

| Repo | PC |
|---|---|
| `tools/*` except `tools/weapons/` (a creation tool, not needed for porting) | `C:\source1\cs2port\tools\` (this includes `tools/README.md`, the tool index) |
| `docs/porting/pipeline.md` | `C:\source1\cs2port\cs2_port_pipeline.md` (and the claude.ai project doc `claude/cs2_port_pipeline.md`) |
| `scripts/run_import.bat`, `run_build.bat`, `build_maps.ps1`, `run_import_then_build.bat`, `run_build_one_example.bat`, `run_fixrefs.bat`, `modelsfromrefs.py` | `C:\source1\cs2port\` (`run_fixrefs.bat` copies `modelsfromrefs.py` next to Valve's importer each time it runs) |
| `scripts/make_import_map_auto.py` | `C:\source1\cs2port\` - run once (below); it writes `C:\source1\cs2port\import_map_auto.py` |
| `scripts/post_import_cleanup.py`, `scripts/vmap_refs.py` | `<CS2>\game\csgo\import_scripts\` (next to Valve's `import_map_community.py`, they import its `utils`) |
| `autoport/*` | `C:\source1\cs2port\autoport\` ([autoport/README.md](../../autoport/README.md#setup-on-a-new-pc)) |
| `data/existing_ports.txt` | `C:\source1\cs2port\existing_ports.txt` (the PC copy is the live one) |
| Not in the repo: `tools/addon_template/` | Needed next to `prep.py` on both routes: `C:\source1\cs2port\tools\addon_template\` on the PC (autoport's launch check looks for it), and the cloud copy of `tools/`. `prep.py` builds each new addon from `tools/addon_template/content/` and `game/`. Copy them from Valve's template in the CS2 install, `<CS2>\content\csgo_addons\addon_template\` and `<CS2>\game\csgo_addons\addon_template\` (the folders the Workshop Tools launcher copies when it creates an addon). prep.py skips the template vmap, `addoninfo.txt` and `readonly_tools_asset_info.bin` |
| Not in the repo: `tools/bspsrc.sh` | Cloud route only (on the PC, `autoport/bspsrc.bat` runs BSPSource from its own image): written by `sh tools/setup_bspsrc.sh <staged lib/modules> tools` (or put it elsewhere and set `BSPSRC=`) |
| `ports/<addon>/scripts/*.js` | `<CS2>\content\csgo_addons\<addon>\maps\scripts\` (pipeline ports) or `...\<addon>\scripts\` (older jail ports) |

`<CS2>` is `C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive`.

**These paths are skink52's PC, not a requirement.** Every `C:\...` and `E:\...` path on this page (and `<CS2>` above) is how one
PC is laid out. Another PC can use different drives and folder names: the batch files and scripts in `scripts/` and `autoport/`
name these paths near the top, so change them there to match your own layout. What has to hold is the relationship between the
folders (which repo file sits next to which Valve tool), not the drive letters.

## PC folders

Laid out by `scripts/reorg_pc.ps1` (30 Oct 2026; `C:\source2\reorg_undo.ps1` reverses it). Put new things where they belong here.

```
C:\source1\
    bspsrc-windows\            BSPSource (jlink image, bin\bspsrc.bat) and the input BSPs:
        mg maps\               CS:GO BSPs waiting to be ported (mg maps\multigames\ for the big multigames)
        bsp's\                 older inputs (jail maps, single ports)
    maps\                      decompiled VMFs: <addon>.vmf (Hammer-save fixed), <addon>.vmx (raw BSPSource output)
    cs2port\
        run_import.bat         stage B
        run_build.bat          stage D (runs build_maps.ps1)
        build_maps.ps1
        run_import_then_build.bat   unattended stage B → wait for build_go.txt → stage D
        run_build_one_example.bat   template for building one addon
        import_map_auto.py     made by scripts/make_import_map_auto.py
        queue.txt              stage B queue: "addon [vmfname]" per line
        build_queue.txt        stage D queue: "addon [mapname]" or "assets addon" per line
        existing_ports.txt     every known CS2 port and its status
        assets\                <addon>.zip (+ .2/.3/.4.zip) - materials/models from the BSP, unpacked into <CS2>\csgo by stage B
        logs\                  <addon>_import / _cleanup / _assets / _build logs, stage_b_done.txt, stage_d_done.txt
        tools\                 this repo's tools/ (vmap_refs.py loads dmx.py and kv2.py from here); README.md = the tool index
        cs2_port_pipeline.md   docs/porting/pipeline.md
    pak01_dir.vpk              CS:GO's VPK directory (staged into the workspace for the missing-material pass)
    gameinfo.txt, expressions\   CS:GO files from the original importer setup (left in place)
    sound\                     junction to <CS2>\csgo\sound (10 Nov 2026: was a byte-identical copy; rmdir only, never delete through it)
    tools\                     mappacker\, crowbar\, source2converter\, disk_report\
    archive\                   old manual import kit, screenshots, Blender/Crowbar leftovers, old vpks (unused by any pipeline)
C:\source2\                   original addons (creation)
    apps\                      RadGen.exe, Source2Viewer.exe, Hammer5Tools.lnk
    projects\<project>\        source assets per project: trenchwarfare\ (GLBs, weapon FBXs, stock\, tools\ = the weapon builder,
                               design notes.txt), dogfight\ (install_dogfight.bat), hellmatch\freedoom-0.13.0\, apache\, space-racer\,
                               reference\kz_infinite_water_template\
    workshop\<addon>\          Workshop icons, galleries, descriptions, videos (hellmatch\, space-racer\, ttt\, slime-servers\);
                               ports\ = port icons, unsorted\ = images not yet matched to an addon
    notes\                     server details, old notes and snippets
    archive\                   unused: Neon Racer's Tripo GLBs, dogfight.rar, jb_clouds.vpk, loose texture work
<CS2>\
    csgo\                      CS:GO content the importer reads (gameinfo.txt, materials\, models\...). C:\cscontent is a junction to it
    content\csgo_addons\<addon>\   addon sources (vmap, materials, scripts...)
    game\csgo_addons\<addon>\      compiled addon (what the game loads)
    game\csgo\import_scripts\      Valve's importer + post_import_cleanup.py, vmap_refs.py, modelsfromrefs.py
    game\bin\win64\                resourcecompiler.exe, cs_mdl_import.exe (and vpk.signatures, see below)
```

### Offloaded to E: (10 Nov 2026, C: was full)

**Specific to skink52's PC; nothing here is needed on another PC.** It records where folders went when one machine ran out of space,
so sessions on that machine know which paths are junctions. A PC with room on one drive keeps everything at the paths above.

These folders now live in `E:\offload\` (a slow 5400-rpm HDD) with a **junction left at the old path**, so every script and doc path
still works. Never delete through a junction: remove the link with `rmdir <old path>` (not `rd /s`, `Remove-Item -Recurse` or an
Explorer delete), then move the folder back to undo. The disk survey behind these moves is a local record kept on that PC, not in this repo.

| Old path (junction) | Now on E: |
|---|---|
| `C:\source1\playermodels\extract` (earlier) | `E:\offload\playermodels_extract` |
| `C:\source1\playermodels\basegame`, `preview` | `E:\offload\playermodels_basegame`, `playermodels_preview` |
| `C:\source1\hats\extract` | `E:\offload\hats_extract` |
| `C:\source1\gmod_ports` | `E:\offload\gmod_ports` |
| `C:\source1\bspsrc-windows\mg maps\ported`, `bsp's` | `E:\offload\bspsrc_mg_maps_ported`, `bspsrc_bsps` |
| `<CS2>\content\csgo_addons\prefabs+backups` | `E:\offload\prefabs+backups` (new .vmap backups land on E:) |
| `C:\source2\archive` | `E:\offload\source2_archive` |
| `C:\VTF\VTFInput` | `E:\offload\VTFInput` |
| `C:\cs2server` (slime-mg test server) | `E:\offload\cs2server` (slower server starts and test runs) |
| `%USERPROFILE%\Videos` | `E:\offload\Videos` |

Plain moves (no junction): `E:\offload\ironframe_backups\` (IRONFRAME .vmap backups of 9 Nov) and `E:\offload\source1_sound_extra\`
(skink52's Pokemon music zip). Deleted the same day: the SteamCMD GMod downloads of catalog items that are already extracted
(`fetch.py` downloads again; move `appworkshop_4000.acf` aside first), the SteamCMD CS2 Workshop downloads, crash dumps older than a
week, and 393 content-addon backups older than 8 Nov (the list is a local record on that PC, not in this repo; the newest
map backup in each addon was kept).

## Claude Code on the PC (one folder)

Claude Code runs from `C:\source1`. Everything it needs outside that folder is reached through NTFS junctions in `C:\source1\links\`,
made by [`scripts/make_links.bat`](../../scripts/make_links.bat) (safe to re-run; it skips links that exist). Editing through a link edits the real folder.
Removing a link (`rmdir` on the link only) is safe; deleting files inside a link deletes the real files.

| Link | Real path |
|---|---|
| `links\VTF` | `C:\VTF` |
| `links\source2` | `C:\source2` (original addons: `apps\`, `projects\`, `workshop\`, `notes\`, `archive\`) |
| `links\cs2_root` | `<CS2>` |
| `links\content_addons` | `<CS2>\content\csgo_addons` |
| `links\game_addons` | `<CS2>\game\csgo_addons` |
| `links\csgo` | `<CS2>\csgo` (same target as `C:\cscontent`) |
| `links\bin_win64` | `<CS2>\game\bin\win64` (resourcecompiler, vpk.signatures) |
| `links\import_scripts` | `<CS2>\game\csgo\import_scripts` |

- Porting work stays in `C:\source1` (`cs2port\`, `maps\`, `bspsrc-windows\`, `tools\`, `archive\`).
- Never search recursively over `links\cs2_root` or `links\csgo` (huge); target a subfolder.
- `links\` is excluded from git locally (`.git\info\exclude`) and never committed.
- Docs may use link paths or real paths; scripts keep the real paths (or `C:\cscontent`) so they still work outside Claude Code.

## Requirements

Required on the PC for porting:

| What | Why |
|---|---|
| Windows with CS2 and its **Workshop Tools** | Hammer, `resourcecompiler`, Valve's import scripts |
| **Python 3** (`py` launcher and `python`; last run with 3.13) | every tool here |
| `numpy`, `scipy`, `Pillow` | stage A, stage C and the checks: `pip install -r requirements/porting.txt -c requirements/constraints.txt` |
| **BSPSource** (its Windows image, with its own Java) | decompiling; `autoport/bspsrc.bat` runs it, no separate Java needed |
| **CS:GO content** extracted into `<CS2>\csgo` | what the importer reads (step 5 below) |
| `tools/addon_template/` copied from the CS2 install | `prep.py` builds each new addon from it (table above) |

Optional (each tool says so, or does without, when its extra is missing):

| What | Used by |
|---|---|
| `mutagen`, `lameenc`, `lz4` ([requirements/porting-optional.txt](../../requirements/porting-optional.txt)) | music length and MP3 encoding (`rangedmusic.py`, `coursemusic.py`); faster texture decode (`vtexc.py`) |
| **Node** 18+ (22.15+ for `create/anim` and `create/s2`) | compiled-material reading in `vmatc.py`, the script tests |
| `VTFCmd.exe`, RadGen, Hammer5Tools | steps 6 to 8 below |
| Java 21 | the cloud route only ([Cloud workspace](#cloud-workspace)) |

The creation toolkit and model tools have their own lists: [requirements/](../../requirements). Versions the tools were last run with,
and what "tested" means for each part: [docs/reference/compatibility.md](../reference/compatibility.md).

### Paths without editing files

These environment variables replace the built-in paths in the Python tools; set them instead of editing a script.

| Variable | Replaces | Read by |
|---|---|---|
| `CS2_ROOT` | the CS2 install folder (`<CS2>`) | `tools/` (stage A, stage C, checks, compiler wrapper, radar) and `autoport/` |
| `CS2PORT` | `C:\source1\cs2port` (tools, logs, working root) | `autoport/` |
| `CS2MAP_SOURCE1` | `C:\source1` (decompiled maps, BSPSource, CS:GO's `pak01_dir.vpk`) | `autoport/`, `tools/prep.py` |
| `CS2MAPPING` | the clone of this repo | `autoport/` |
| `CS2MAP_BACKUPS` | the map backup store | `tools/mapbackup.py` |
| `BSPSRC` | the BSPSource launcher | `tools/prep.py` |

Still fixed in the file (edit the lines near the top): the batch files and `build_maps.ps1` in `scripts/` (`CS2`, `PORT`), and
`scripts/post_import_cleanup.py` (which also takes `--steam-root`). A full list of what reads which path, and the plan for one shared
configuration file, is in [docs/reference/engineering-notes.md](../reference/engineering-notes.md#paths-and-configuration).

### Troubleshooting

Start with `python cs2mapping.py doctor` in the clone: it lists what is missing, each path and where its value came from, and whether the
PC copy of the tools matches the clone.

| Symptom | Cause and fix |
|---|---|
| The importer fails straight away | `game\bin\win64\vpk.signatures` is back after a Steam update. `run_import.bat` renames it each run; run the import through it. |
| `prep.py` stops with "addon_template" | `tools\addon_template\content` and `\game` are not next to `prep.py`. Copy them from the CS2 install (table above). |
| autoport's launch check warns that tools differ from the repo | The PC copy under `cs2port\` is older or newer than the clone. Copy the changed files across and compare sizes. |
| A tool cannot find CS2 | The install is not in the default Steam folder: set `CS2_ROOT` (above). |
| A built `.vpk` is not replaced | The map is loaded in CS2. Unload it, or close CS2, and build again. |
| An edit made by a tool vanished | Hammer had the map open and saved over it. Close Hammer first; the tool's backup is listed in [file-safety.md](../reference/file-safety.md). |

## One-time PC setup

1. **Workshop Tools** installed for CS2 (Hammer, `resourcecompiler`, the import scripts).
2. **Python** on the PC (the `py` launcher and `python`) for the import scripts.
3. **Valve's importer, unattended:** put `scripts/make_import_map_auto.py` in `C:\source1\cs2port\` and run
   `py C:\source1\cs2port\make_import_map_auto.py`. It copies `game\csgo\import_scripts\import_map_community.py` to
   `C:\source1\cs2port\import_map_auto.py` without the "Enter to Continue, Esc to Quit" prompt, and `run_import.bat` copies that next to
   Valve's script before every import. Run it again if a CS2 update changes Valve's script.
4. **`vpk.signatures`.** The importer fails while `game\bin\win64\vpk.signatures` exists. `run_import.bat` renames it to
   `vpk.signatures.aaa` every time, because Steam puts it back after updates.
5. **CS:GO content** extracted into `<CS2>\csgo` (materials, models, gameinfo.txt), with `C:\cscontent` as a junction to it
   (`mklink /J C:\cscontent "<CS2>\csgo"`). A `.lnk` shortcut won't work because Python doesn't follow those.
6. Only for the older `post_import_cleanup.py` texture cascade: VTFEdit-Reloaded's `VTFCmd.exe` at `C:\VTF\VTFEdit\VTFCmd.exe`, with staging
   folders `C:\VTF\VTFInput` and `C:\VTF\VTFOutput`. The current pipeline rebuilds missing materials in stage C instead, so this is optional.
7. **Radar tool (optional):** RadGen at `C:\source2\apps\RadGen.exe`. The pipeline renders its own radars, but RadGen was used for the jail maps.
8. **Loading-screen text:** set with Hammer5Tools.

## Cloud workspace

- Python 3 with `numpy`, `scipy` and `Pillow`.
- Java 21 for BSPSource. [`tools/setup_bspsrc.sh`](../../tools/setup_bspsrc.sh) extracts BSPSource from the jlink image in
  `C:\source1\bspsrc-windows\lib\modules` (staged into the workspace) and patches the class files from Java 24 down to 21. It writes
  `<dest>/bspsrc.sh`; `prep.py` uses `tools/bspsrc.sh` unless `BSPSRC=` points elsewhere.
- `tools/addon_template/` (content/ and game/), copied from the CS2 install's `addon_template` folders (table above). prep.py fails without it.
- A working root that mirrors the PC (this is what `stage_c.py <addon> <root>` expects):

```
<root>/content/<addon>/...            staged copy of content\csgo_addons\<addon>
<root>/source1/maps/<addon>.vmf       the decompiled VMF (for dropped outputs, sky brushes...)
<root>/vpk/cs2_pak01_dir.vpk          CS2's game\csgo\pak01_dir.vpk (stock materials/particles list)
<root>/vpk/csgo_pak01_dir.vpk         CS:GO's pak01_dir.vpk
<root>/vpk/csgo_pak01_NNN.vpk         only the CS:GO archive chunks stage C asks for ("NEED CS:GO archives: ..."), or instead the listed
                                      files from the extracted CS:GO content copied into <root>/embedded/<addon>/
<root>/content_files_<addon>.json     optional listing of the addon folder on the PC (so the tools know what exists without staging it)
```

Stage C writes changed files to `<root>/out/<addon>/` (content files), `<root>/out/<addon>_game/` (game-side files such as
`resource/overviews/<map>.txt`) and `<root>/out/<addon>_result.json`. Only those files are copied back to the PC.

## Rules while Claude is editing

- Close Hammer while a map is being edited. Hammer keeps the map in memory and will overwrite the edit when it saves.
- CS2 must stay in the state it was in when the build started (skink52, 11 Nov 2026): open before the build and open until it ends, or closed throughout. Never start it part-way through a build, and never quit it part-way through. CS2 can stay open during a build if it was started **before** the build and stays open until the build ends (quitting it mid-build kills the
  compiler). Don't have the map being built loaded: a loaded `.vpk` can't be replaced
  ([pipeline.md](pipeline.md#stage-d-command-line-build-build_mapsps1)).
- Before editing a `.vmap`, Claude backs it up (to `content\csgo_addons\prefabs+backups\`, or as `<map>.vmap.bak_<date>` next to it).
- Only changed files are sent back to the PC.
