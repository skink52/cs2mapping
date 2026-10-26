# scripts: what runs on the Windows PC

> **AI-generated code** (written by Claude for skink52's ports).

| File | Goes to | What it does |
|---|---|---|
| `run_import.bat` | `C:\source1\cs2port\` | **Stage B.** For each line of `queue.txt` it renames `vpk.signatures` if Steam restored it, unpacks `assets\<addon>*.zip` into `<CS2>\csgo` without overwriting, runs `import_map_auto.py`, then `post_import_cleanup.py`, and logs to `logs\` |
| `run_build.bat` + `build_maps.ps1` | `C:\source1\cs2port\` | **Stage D.** Command-line build of every map in `build_queue.txt`, one at a time: addon assets first, then `resourcecompiler` with Hammer's full-build arguments, then the outroot copy. Marks `existing_ports.txt` `[in progress, built]` |
| `run_build_one_example.bat` | `C:\source1\cs2port\` | Builds one addon without touching the queue (`run_build.bat <addon>`). Copy it and change the name |
| `run_import_then_build.bat` | `C:\source1\cs2port\` | Unattended: `run_import.bat`, then waits for Claude to write `build_go.txt` after stage C, then `run_build.bat`. Logs to `logs\unattended.log` |
| `make_import_map_auto.py` | `C:\source1\cs2port\` | Run once. Copies Valve's `import_map_community.py` to `import_map_auto.py` without the Enter/Esc prompt, so the import can run unattended |
| `vmap_refs.py` | `<CS2>\game\csgo\import_scripts\` | Scans `<addon>.vmap` **and every prefab it references** for the materials and models actually used, drops stock CS2 ones, and writes `maps\<addon>_vmap_refs.txt` in the importer's refs format. `post_import_cleanup.py` calls it automatically; run it alone (`python vmap_refs.py <addon>`, `--all` for the unfiltered list) to audit a map. Needs `dmx.py` and `kv2.py` from `C:\source1\cs2port\tools\` (kv2 for the importer's keyvalues2 text vmaps) |
| `post_import_cleanup.py` | `<CS2>\game\csgo\import_scripts\` | Run after the importer, even if it died part-way (it aborts the whole run on the first bad model). Driven off the `.vmap` via `vmap_refs.py` (the importer's `_refs.txt` only with `--refs`, or when the vmap doesn't exist). Re-imports and compiles models that are missing or out of date, finds textures (addon → VTF staging → raw CS:GO content) and converts them with VTFCmd, writes vmats for loose textures, and reports what's still missing in `<addon>_cleanup_report.txt` |
| `modelsfromrefs.py` | `<CS2>\game\csgo\import_scripts\` | Imports and compiles only the models in a `_refs.txt` (plus their materials) without touching the map. Edit the CONFIG block first |

Stage A (decompile, assets) and stage C (all the map fixes) run in Claude's workspace. See [../docs/porting/pipeline.md](../docs/porting/pipeline.md) for the workflow,
[../tools/README.md](../tools/README.md) for the workspace tools and [../docs/porting/setup.md](../docs/porting/setup.md) for where each file goes.
