# legacy: helpers from the early (manual) ports

> **AI-generated code** (written by Claude for skink52's ports).

These came before the pipeline, from the August–September 2026 jail ports. Each one solved a specific blocker and is kept because it still works.
Check the CONFIG lines at the top of each file before using it, because several of them name a specific addon.

| File | What it does |
|---|---|
| `mdltovmdl.py` | Batch `.mdl` → `.vmdl` with `cs_mdl_import`, using an explicit `-l` file list. Running `-r` with a bare `*.mdl` makes cs_mdl_import scan the whole stock model tree, and it crashed (access violation) on an unrelated stock model and lost the batch |
| `newcheck.py` | Checks every `.mdl`'s checksum against its `.dx90.vtx`. One mismatch (trashdumpster02a) crashed cs_mdl_import and took every file after it in the same `-l` run with it. This finds all the bad pairs up front |
| `makealpha.py` | Writes `<name>_mask.png` (greyscale alpha) for every PNG in the folder, for Translucent / Alpha Test materials |
| `findmissingmodels.py` | Reads a `_refs.txt` and copies each listed `.mdl` from the CS:GO folder, with its `.vvd`/`.phy`/`.vtx` companions, `$includemodel` models, materials and textures, into `csgo\<addon>\` ready to import |
| `findmissingtextures.py` | Compares a `_refs.txt` against the textures already in the addon and copies the missing `.vtf` files from `C:\source1\materials` into the VTF staging folder |
