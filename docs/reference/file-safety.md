# File safety: what the tools change, and how to get it back

The tools here edit maps and assets in place inside the CS2 install. This page says which tools write where, what each one keeps
before it overwrites, how to preview a change, and how to undo one. Audit of 11 Nov 2026; file and line references are to that state.

## Rules the tools follow

1. **Close Hammer** before a tool edits a map: Hammer keeps the map in memory and saves over the edit.
2. **A file is backed up before it is overwritten**, and the backup is checked (size and sha256) before the new file goes in.
   New files are written to a temp name and renamed into place, so a crash never leaves a half-written file under the real name.
3. **Names are not paths.** An addon, map, script or pack name must be one folder name: no `..`, no slashes, no drive. The tools that
   delete or overwrite by name refuse anything else (`tools/safepath.py` `addon_name`).
4. **Never delete through a junction.** The working root holds `content\<addon>` as a junction to the real addon, which may be on
   another drive. Remove a junction with `rmdir <link>` only. `prep.py` refuses to clear a work folder that is a link.
5. **Containment is checked on the path as written**, not after resolving links: a path that climbs out with `..` is outside.
   Rejecting every path that resolves to another drive would break the junction layout, so the tools do not do that.
6. **The root may be a junction; nothing below it may.** The folder a tool is pointed at can be a junction (the working root's
   `content\<addon>`). A link *below* that folder was not named by anyone, and writing through it lands in a place the tool was never
   pointed at (a `materials` folder linked to another addon). `safepath` refuses to write, restore or delete through one, and checks
   again just before each write in case the link appeared after the plan was made.
7. **The working root's junction is verified, not assumed.** `pclocal.py root` makes `content\<addon>` and reads it back; when a plain
   folder, a broken link or a junction to another place is already there it stops and says what to remove. It never replaces it.

## Backups

| Kept by | What | Where | Checked | Undo |
|---|---|---|---|---|
| `tools/mapbackup.py` | A `.vmap`, compressed, with its sha256; optional snapshots of the addon's other source files, stored once per content | `--store`, else `CS2MAP_BACKUPS`, else `<cs2port>\map_backups` | read back and unpacked after every save, and again before a restore; `mapbackup.py verify` checks the whole store | `mapbackup.py restore <map> <stamp or latest>` (the map it replaces is saved first, kind `before-restore`) |
| `autoport/pclocal.py deliver --force` | every existing file it replaces when copying stage A's output to the PC paths | `<root>\deliver_backups\<stamp>\` | size and sha256 before the overwrite; each copy against its source after | `pclocal.py rollback <root>\out\deliver_<stamp>.json` |
| `tools/matnames.py` | the map, through `mapbackup`, before it renames a material in it (kind `before-matnames`) | the `mapbackup` store | by `mapbackup` | `mapbackup.py restore` |
| `tools/vmdlfix.py`, `tools/gibfix.py` | each `.vmdl` they change | `<file>.bak_<stamp>` beside it | sha256 before the replace | copy it back by hand |
| `autoport/pclocal.py apply` | every file it overwrites when copying stage C's output into the addon | a `.vmap` as `<map>.vmap.bak_<stamp>` next to it; other files under `<root>\apply_backups\<addon>\<stamp>\` | size and sha256 before the overwrite | `pclocal.py rollback <addon>` |
| `autoport/autoport.py` (stage C step) | the importer's untouched map as `<map>.vmap.imported`; and, before a rerun puts that copy back over a map that has changed since, the changed map | next to the map; the changed map goes to the `mapbackup` store, kind `before-rerun` | by `mapbackup` | `mapbackup.py restore` |
| `autoport/polish.py` | the map before a polish pass | `<map>.vmap.bak_polish_<stamp>` next to it | no | copy it back by hand |
| `create/mapops.py` | the map, through `mapbackup`, when it edits a map in place | the `mapbackup` store | by `mapbackup` | `mapbackup.py restore` |
| `scripts/reorg_pc.ps1` | nothing is overwritten; every move is logged | `reorg_log.csv` and a generated `reorg_undo.ps1` | n/a | run the undo script |

`mapbackup` trims old copies by tier (newest 3, then hourly, daily, weekly) and keeps pinned copies for ever: `mapbackup.py pin <map> <stamp>`
before anything risky. The `.bak_*` files next to maps are never trimmed by a tool; delete old ones by hand.

## Change records

`pclocal.py apply` (and `deliver`, as `deliver_<stamp>.json`) writes `<root>\out\<addon>_apply_<stamp>.json` after every file it copies, so even an interrupted run leaves a
usable record: for each file the operation (`create` or `modify`), its sha256 before and after, and where its backup is.
`rollback` reads that record. It puts overwritten files back and removes created ones **only while a file still has the bytes the run
wrote**; a file edited since (in Hammer, by a later pass) is left alone and listed, because undoing it would lose that edit.

Other records: `prep.py` `manifest.json` (staged file to PC path), `stage_c.py` `<addon>_result.json` (files written), autoport's dated
log, `polish_<time>.md`, the `mapbackup` store's own JSON.

## Preview before changing (dry run)

| Tool | How | Shows |
|---|---|---|
| `autoport/pclocal.py apply <addon> --dry-run` | changes nothing, writes nothing | files that would be created and overwritten, folders touched, bytes to write and to back up |
| `autoport/pclocal.py deliver <manifest> --dry-run` | changes nothing, writes nothing | files that would be created and overwritten, and whether the real run would stop for `--force` |
| `autoport/pclocal.py rollback <addon> --dry-run` | | what would be restored, removed and left alone |
| `create/blenderkit.py --dry-run` | writes nothing (`--no-blender` writes the script and vmdl without starting Blender) | the script and vmdl text, the files it would write and overwrite |
| `create/hats/pack.py --prune --dry-run` | | the hat folders it would delete and the zip it would write |
| `autoport/autoport.py --dry-run` | writes nothing, not even log lines | the plan for each map, then stops |
| `tools/mapbackup.py trim --dry-run` | | the copies it would delete |
| `tools/rcompile.py map --dry-run` | | the compiler command line |
| `tools/release.py` | dry by default; `--apply` copies | what would be published, missing and stale files |
| `scripts/reorg_pc.ps1` | previews by default, then asks | every move, skip and duplicate |
| `create/clean_stale.py --dry-run`, `create/playermodels/cleanup.py --dry-run`, `create/hats/suggest.py --dry-run` | | what would be removed or added |
| MCP tools `build_map`, `model_build`, `map_edit` | `dry_run` argument | the result without saving |

## What still writes without a backup or a preview

Known gaps, most important first, after the two 11 Nov 2026 passes. Each needs a real import or build to test.

| Tool | What it does | Why it matters |
|---|---|---|
| `scripts/build_maps.ps1` | copies built files over `game\csgo_addons\<addon>\` (size checked, not hashed); no dry run | compiled output only, rebuilt by building again. It now refuses addon or map names that are paths. |
| `scripts/run_import.bat`, `run_fixrefs.bat` | rename `game\bin\win64\vpk.signatures`, copy scripts into `game\csgo\import_scripts`, unpack assets into `csgo\` with `tar -k` (keeps existing files) | writes inside the CS2 install; Steam restores `vpk.signatures` on update |
| `tools/vmapedit.py` `Map.save` | atomic now (temp file, then replace; unchanged bytes are not rewritten), but takes no backup | a caller that saves over a map someone edits must back it up first; `stage_c`, `stage_d` and `run_pass` write to `<root>/out`, not in place |
| `autoport/polish.py`, `autoport/profiles.py` | write non-map files (scripts, HUD css) into the addon with no backup | small text files, regenerated by rerunning |
| `create/hats/pack.py --prune`, `create/playermodels/cleanup.py`, `create/clean_stale.py`, `create/loading.py`, `create/mech_anim.py` | delete generated folders or files under the addon or the work folder | targets come from a catalog or config; the first three have `--dry-run`; none keeps a copy (the files are regenerated by rerunning the converter) |
| MCP server (`tools/mcp_server.py`, `autoport/mcp_live.py`) | the writers overwrite generated files with no backup (`map_edit` in place does back up) | the hints now say which tools can replace or delete (`destructiveHint`), which only add, and which only read; `script_write` refuses names that are paths. Stopping a job (`job_cancel`, `job_status cancel=true`) or the game (`game_stop`) is marked destructive: a compile killed half way leaves partial output |

## Using the safe copy in a new tool

`tools/safepath.py` is the shared piece (standard library only):

```python
import safepath
addon = safepath.addon_name(addon)                      # ValueError unless it is one plain folder name
plan = safepath.plan_copy(out_dir, addon_dir)           # reads only: create / modify / same per file
plan = safepath.plan_pairs(pairs, [allowed_root, ...])  # or explicit (source, destination) pairs, each inside an allowed folder
man = safepath.apply_plan(plan, backup_dir, manifest_json, dry_run=args.dry_run)
...
safepath.rollback(manifest_json)                        # or dry_run=True to see what it would do
safepath.write_atomic(path, data, backup='sibling')     # one file: temp file then replace; same bytes = untouched
```

Tests: `tools/tests/test_safepath.py` (names, containment, junctions, interrupted runs, damaged backups), `tools/tests/test_links.py` (links below a root, a link swapped in after planning, rollback through a link),
`autoport/tests/test_pclocal.py`, `tools/tests/test_mapbackup.py`, `tools/tests/test_dryrun.py` (the file tree before and after each dry run). They use real files in temp folders, including a real NTFS junction
on Windows; none touches a CS2 install.
