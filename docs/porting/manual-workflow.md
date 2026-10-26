# The manual workflow (before the pipeline)

This is how the ports up to mid-October 2026 were done by hand. The pipeline automates every step, but this is still the way to port
a map without Claude, or to see what a pipeline stage is standing in for.

1. **Decompile** the CS:GO BSP with BSPSource, with "extract embedded files" on, into `C:\source1\maps`.
2. **Copy the decompiled assets** (materials, models) into the CS:GO content folder the importer reads (`<CS2>\csgo`, junctioned as
   `C:\cscontent`). Sounds and scripts go straight into the CS2 addon.
3. **Re-save the VMF in CS:GO Hammer.** The importer wanted a Hammer-saved VMF. `python3 tools/hammer_resave.py <in.vmf> <out.vmf>` now does the same edit
   without Hammer (prep.py runs it automatically).
4. **Create the addon** in the Workshop Tools launcher (addon name = map name, version suffixes stripped).
5. **Rename `game\bin\win64\vpk.signatures`** (e.g. to `vpk.signatures.aaa`), otherwise the importer fails.
6. **Run Valve's importer** from `game\csgo\import_scripts`:
   `python import_map_community.py "<CS2>\csgo" "C:\source1" "<CS2>\game\csgo" <addon> <map>` (add `-usebsp` to import from the BSP).
7. **Run `post_import_cleanup.py <addon>`** in the same folder. It finishes what the importer gave up on (models, textures, vmats) and writes
   `<addon>_cleanup_report.txt`.
8. **Collapse the prefabs into the main `.vmap`.** The importer writes the map as prefabs (environment, gameplay, lighting, cubemaps, audio,
   nav). Collapse them, or copy each one's contents and Paste Special into the main map. Paste Special also works when a prefab is too heavy to collapse.
9. **Fix what CS2 broke** (see [cs2-gotchas.md](../reference/cs2-gotchas.md)): stationary lights, lasers, sky, scripts for dead entities, materials.
10. **Radar** (RadGen, `C:\source2\RadGen.exe`) and **loading-screen text** (Hammer5Tools: "original map by &lt;author&gt; cs2 port by skink52").
11. **Build**, test, and upload to the Workshop (game mode Custom).

## Helpers from that period (`legacy/`)

- Models that wouldn't import: `mdltovmdl.py` (batch `cs_mdl_import` with an explicit file list) and `newcheck.py` (find `.mdl`/`.vtx`
  checksum mismatches that crash the batch).
- Textures: `findmissingtextures.py` / `findmissingmodels.py` gather what a `_refs.txt` needs. VTFEdit-Reloaded's VTFCmd converts the VTFs to PNG,
  and `makealpha.py` makes greyscale alpha masks for translucent materials.
- `scripts/modelsfromrefs.py`: import and compile just the models from a `_refs.txt`, without re-importing the map.
