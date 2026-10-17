# scripts: what runs on the Windows PC

> **AI-generated code** (written by Claude for skink52's ports).

| File | Goes to | What it does |
|---|---|---|
| `run_import.bat` | `C:\source1\cs2port\` | **Stage B.** For each line of `queue.txt` it renames `vpk.signatures` if Steam restored it, unpacks `assets\<addon>*.zip` into `<CS2>\csgo` without overwriting, runs `import_map_auto.py`, then `post_import_cleanup.py`, and logs to `logs\` |
| `run_build.bat` + `build_maps.ps1` | `C:\source1\cs2port\` | **Stage D.** Command-line build of every map in `build_queue.txt`, one at a time: addon assets first, then `resourcecompiler` with Hammer's full-build arguments, then the outroot copy. Marks `existing_ports.txt` `[in progress, built]` |
| `run_build_one_example.bat` | `C:\source1\cs2port\` | Builds one addon without touching the queue (`run_build.bat <addon>`). Copy it and change the name |
| `make_import_map_auto.py` | `C:\source1\cs2port\` | Run once. Copies Valve's `import_map_community.py` to `import_map_auto.py` without the Enter/Esc prompt, so the import can run unattended |
| `post_import_cleanup.py` | `<CS2>\game\csgo\import_scripts\` | Run after the importer, even if it died part-way (it aborts the whole run on the first bad model). Re-imports and compiles models that are missing or out of date, finds textures (addon → VTF staging → raw CS:GO content) and converts them with VTFCmd, writes vmats for loose textures, and reports what's still missing in `<addon>_cleanup_report.txt` |
| `modelsfromrefs.py` | `<CS2>\game\csgo\import_scripts\` | Imports and compiles only the models in a `_refs.txt` (plus their materials) without touching the map. Edit the CONFIG block first |

Stage A (decompile, assets) and stage C (all the map fixes) run in Claude's workspace. See [../docs/pipeline.md](../docs/pipeline.md).
