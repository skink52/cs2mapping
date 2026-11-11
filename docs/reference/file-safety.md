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
5. **Containment is checked on the path as written**, not after resolving links: a path that goes through a junction is where the
   tool was told to work; a path that climbs out with `..` is not. Rejecting every path that resolves to another drive would break
   the junction layout, so the tools do not do that.

## Backups

| Kept by | What | Where | Checked | Undo |
|---|---|---|---|---|
| `tools/mapbackup.py` | A `.vmap`, compressed, with its sha256; optional snapshots of the addon's other source files, stored once per content | `--store`, else `CS2MAP_BACKUPS`, else `<cs2port>\map_backups` | read back and unpacked after every save, and again before a restore; `mapbackup.py verify` checks the whole store | `mapbackup.py restore <map> <stamp or latest>` (the map it replaces is saved first, kind `before-restore`) |
| `autoport/pclocal.py apply` | every file it overwrites when copying stage C's output into the addon | a `.vmap` as `<map>.vmap.bak_<stamp>` next to it; other files under `<root>\apply_backups\<addon>\<stamp>\` | size and sha256 before the overwrite | `pclocal.py rollback <addon>` |
| `autoport/autoport.py` (stage C step) | the importer's untouched map as `<map>.vmap.imported`; and, before a rerun puts that copy back over a map that has changed since, the changed map | next to the map; the changed map goes to the `mapbackup` store, kind `before-rerun` | by `mapbackup` | `mapbackup.py restore` |
| `autoport/polish.py` | the map before a polish pass | `<map>.vmap.bak_polish_<stamp>` next to it | no | copy it back by hand |
| `create/mapops.py` | the map, through `mapbackup`, when it edits a map in place | the `mapbackup` store | by `mapbackup` | `mapbackup.py restore` |
| `scripts/reorg_pc.ps1` | nothing is overwritten; every move is logged | `reorg_log.csv` and a generated `reorg_undo.ps1` | n/a | run the undo script |

`mapbackup` trims old copies by tier (newest 3, then hourly, daily, weekly) and keeps pinned copies for ever: `mapbackup.py pin <map> <stamp>`
before anything risky. The `.bak_*` files next to maps are never trimmed by a tool; delete old ones by hand.

## Change records

`pclocal.py apply` writes `<root>\out\<addon>_apply_<stamp>.json` after every file it copies, so even an interrupted run leaves a
usable record: for each file the operation (`create` or `modify`), its sha256 before and after, and where its backup is.
`rollback` reads that record. It puts overwritten files back and removes created ones **only while a file still has the bytes the run
wrote**; a file edited since (in Hammer, by a later pass) is left alone and listed, because undoing it would lose that edit.

Other records: `prep.py` `manifest.json` (staged file to PC path), `stage_c.py` `<addon>_result.json` (files written), autoport's dated
log, `polish_<time>.md`, the `mapbackup` store's own JSON.

## Preview before changing (dry run)

| Tool | How | Shows |
|---|---|---|
| `autoport/pclocal.py apply <addon> --dry-run` | changes nothing, writes nothing | files that would be created and overwritten, folders touched, bytes to write and to back up |
| `autoport/pclocal.py rollback <addon> --dry-run` | | what would be restored, removed and left alone |
| `autoport/autoport.py --dry-run` | | the plan for each map, then stops |
| `tools/mapbackup.py trim --dry-run` | | the copies it would delete |
| `tools/rcompile.py map --dry-run` | | the compiler command line |
| `tools/release.py` | dry by default; `--apply` copies | what would be published, missing and stale files |
| `scripts/reorg_pc.ps1` | previews by default, then asks | every move, skip and duplicate |
| `create/clean_stale.py --dry-run`, `create/playermodels/cleanup.py --dry-run`, `create/hats/suggest.py --dry-run` | | what would be removed or added |
| MCP tools `build_map`, `model_build`, `map_edit` | `dry_run` argument | the result without saving |

## What still writes without a backup or a preview

Known gaps, most important first. None was changed in the 11 Nov 2026 pass because each needs a decision about where its backups
should go or a test against real addons.

| Tool | What it does | Why it matters |
|---|---|---|
| `scripts/build_maps.ps1` | copies built files over `game\csgo_addons\<addon>\` (size checked, not hashed); no dry run | compiled output only, rebuilt by building again. It now refuses addon or map names that are paths. |
| `scripts/run_import.bat`, `run_fixrefs.bat` | rename `game\bin\win64\vpk.signatures`, copy scripts into `game\csgo\import_scripts`, unpack assets into `csgo\` with `tar -k` (keeps existing files) | writes inside the CS2 install; Steam restores `vpk.signatures` on update |
| `tools/matnames.py`, `vmdlfix.py`, `gibfix.py` | rewrite a `.vmap` or `.vmdl` in the addon in place | no backup of their own: run `mapbackup.py save` first, or use them through autoport, whose stage C output goes through `pclocal apply` |
| `tools/vmapedit.py` `Map.save` | plain write to the path given, no temp file | a crash mid-write can truncate the map; every caller that saves in place should back up first |
| `autoport/polish.py`, `autoport/profiles.py` | write non-map files (scripts, HUD css) into the addon with no backup | small text files, regenerated by rerunning |
| `create/hats/pack.py --prune`, `create/playermodels/cleanup.py`, `create/clean_stale.py`, `create/loading.py`, `create/mech_anim.py` | delete generated folders or files under the addon or the work folder | targets come from a catalog or config; `cleanup.py` and `clean_stale.py` have `--dry-run`, `pack.py --prune` does not |
| `create/blenderkit.py --dry-run` | still writes its script and the `.vmdl` | "dry run" there only skips Blender |
| `create/mapops.py` | `mechanics` ops call the builder before the `dry_run` check | a dry run may still write generated files (not confirmed) |
| MCP server (`tools/mcp_server.py`) | every tool is advertised with `destructiveHint: false`, including the ones that write | a client cannot tell readers from writers. `script_write` now refuses names that are paths. |

## Using the safe copy in a new tool

`tools/safepath.py` is the shared piece (standard library only):

```python
import safepath
addon = safepath.addon_name(addon)                      # ValueError unless it is one plain folder name
plan = safepath.plan_copy(out_dir, addon_dir)           # reads only: create / modify / same per file
man = safepath.apply_plan(plan, backup_dir, manifest_json, dry_run=args.dry_run)
...
safepath.rollback(manifest_json)                        # or dry_run=True to see what it would do
```

Tests: `tools/tests/test_safepath.py` (names, containment, junctions, interrupted runs, damaged backups),
`autoport/tests/test_pclocal.py`, `tools/tests/test_mapbackup.py`. They use real files in temp folders, including a real NTFS junction
on Windows; none touches a CS2 install.
