# Setup: the PC side and the cloud side

The pipeline has two halves. The heavy lifting (decompiling, editing `.vmap` files, generating scripts, radars, materials) runs in Claude's
cloud workspace with Python. Anything that has to run Valve's tools (the map importer, `resourcecompiler`) runs on the Windows PC
from a double-clicked batch file. Files move between the two through the linked-computer file tools, so Claude can read and write the PC's
folders but can't start programs there.

## Where the repo goes on the PC

| Repo | PC |
|---|---|
| `tools/*` | `C:\source1\cs2port\tools\` |
| `docs/porting/pipeline.md` | `C:\source1\cs2port\tools\README.md` **and** `C:\source1\cs2port\cs2_port_pipeline.md` |
| `scripts/run_import.bat`, `run_build.bat`, `build_maps.ps1` | `C:\source1\cs2port\` |
| `scripts/make_import_map_auto.py` | `C:\source1\cs2port\` - run once (below); it writes `C:\source1\cs2port\import_map_auto.py` |
| `scripts/post_import_cleanup.py`, `scripts/vmap_refs.py`, `scripts/modelsfromrefs.py` | `<CS2>\game\csgo\import_scripts\` (next to Valve's `import_map_community.py`, they import its `utils`) |
| `data/existing_ports.txt` | `C:\source1\cs2port\existing_ports.txt` (the PC copy is the live one) |
| `ports/<addon>/scripts/*.js` | `<CS2>\content\csgo_addons\<addon>\maps\scripts\` (pipeline ports) or `...\<addon>\scripts\` (older jail ports) |

`<CS2>` is `C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive`.

## PC folders

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
        import_map_auto.py     made by scripts/make_import_map_auto.py
        queue.txt              stage B queue: "addon [vmfname]" per line
        build_queue.txt        stage D queue: "addon [mapname]" or "assets addon" per line
        existing_ports.txt     every known CS2 port and its status
        assets\                <addon>.zip (+ .2/.3/.4.zip) - materials/models from the BSP, unpacked into <CS2>\csgo by stage B
        logs\                  <addon>_import / _cleanup / _assets / _build logs, stage_b_done.txt, stage_d_done.txt
        tools\                 this repo's tools/
    pak01_dir.vpk              CS:GO's VPK directory (staged into the workspace for the missing-material pass)
<CS2>\
    csgo\                      CS:GO content the importer reads (gameinfo.txt, materials\, models\...). C:\cscontent is a junction to it
    content\csgo_addons\<addon>\   addon sources (vmap, materials, scripts...)
    game\csgo_addons\<addon>\      compiled addon (what the game loads)
    game\csgo\import_scripts\      Valve's importer + post_import_cleanup.py + modelsfromrefs.py
    game\bin\win64\                resourcecompiler.exe, cs_mdl_import.exe (and vpk.signatures, see below)
```

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
7. **Radar tool (optional):** RadGen at `C:\source2\RadGen.exe`. The pipeline renders its own radars, but RadGen was used for the jail maps.
8. **Loading-screen text:** set with Hammer5Tools.

## Cloud workspace

- Python 3 with `numpy`, `scipy` and `Pillow`.
- Java 21 for BSPSource. [`tools/setup_bspsrc.sh`](../../tools/setup_bspsrc.sh) extracts BSPSource from the jlink image in
  `C:\source1\bspsrc-windows\lib\modules` (staged into the workspace) and patches the class files from Java 24 down to 21.
- A working root that mirrors the PC (this is what `stage_c.py <addon> <root>` expects):

```
<root>/content/<addon>/...            staged copy of content\csgo_addons\<addon>
<root>/source1/maps/<addon>.vmf       the decompiled VMF (for dropped outputs, sky brushes...)
<root>/vpk/cs2_pak01_dir.vpk          CS2's game\csgo\pak01_dir.vpk (stock materials/particles list)
<root>/vpk/csgo_pak01_dir.vpk         CS:GO's pak01_dir.vpk
<root>/vpk/csgo_pak01_NNN.vpk         only the CS:GO archive chunks stage C asks for ("NEED CS:GO archives: ...")
<root>/content_files_<addon>.json     optional listing of the addon folder on the PC (so the tools know what exists without staging it)
```

Stage C writes changed files to `<root>/out/<addon>/` (content files), `<root>/out/<addon>_game/` (game-side files such as
`resource/overviews/<map>.txt`) and `<root>/out/<addon>_result.json`. Only those files are copied back to the PC.

## Rules while Claude is editing

- Close Hammer while a map is being edited. Hammer keeps the map in memory and will overwrite the edit when it saves.
- Close CS2 before building, because the build can't replace a `.vpk` that's loaded. `build_maps.ps1` waits for you.
- Before editing a `.vmap`, Claude backs it up (to `content\csgo_addons\prefabs+backups\`, or as `<map>.vmap.bak_<date>` next to it).
- Only changed files are sent back to the PC.
