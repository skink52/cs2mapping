# Engineering notes: configuration, dependencies, command line, releases

Where the repo stands after the 11 Nov 2026 review, what was decided, and what is proposed but **not built**. Nothing in the
"Proposed" sections exists yet; each is the least disruptive option found, written down so it can be agreed before anyone builds it.

## Paths and configuration

### Today

Each area finds its folders its own way. Defaults are skink52's PC layout ([setup.md](../porting/setup.md#pc-folders)); the
environment variables below override them without editing a file.

| Setting | Default | Override | Read by |
|---|---|---|---|
| CS2 install | `C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive` | `CS2_ROOT` | `tools/`: `fgdcat`, `rcompile`, `radar`, `mapcheck`, `prep`, `stage_c`; `autoport/`: `common`, `pclocal`, `cs2live`, `crashdump` |
| cs2port root (tools, logs, work) | `C:\source1\cs2port` | `CS2PORT` | `autoport/common.py` |
| Source 1 workspace | `C:\source1` | `CS2MAP_SOURCE1` | `autoport/common.py`, `pclocal.py`, `tools/prep.py` |
| This repo's clone | `C:\source1\cs2mapping` | `CS2MAPPING` | `autoport/common.py` |
| BSPSource launcher | `tools/bspsrc.sh`, or `autoport/bspsrc.bat` on the PC | `BSPSRC` | `tools/prep.py` |
| Map backups | `<cs2port>\map_backups` | `CS2MAP_BACKUPS`, `--store` | `tools/mapbackup.py` |
| Caches | `%LOCALAPPDATA%\cs2mapping\...` | `CS2MAP_CACHE`, `CS2MAP_ATLAS` | `tools/visualcheck.py`, `propatlas.py` |
| Build threads | all | `BUILD_THREADS` | `scripts/build_maps.ps1` |
| Creation output | `create/../out/addon` | `CS2_ADDON_OUT`, `CS2_MODEL_PREFIX`, `CS2_PREVIEW_DIR`, `CS2_VPK_DIR`, `CS2_SINGLE_LOD`; optional `create/toolkit.json` | `create/` |
| Player models, hats | `C:\source1\playermodels`, `C:\source1\hats`, `C:\steamcmd` | `PM_WORK`, `PM_OUT`, `PM_BASEGAME`, `PM_TEMPLATE`, `STEAMCMD`, `HATS_WORK`, `HATS_OUT`; the catalog's `paths` block | `create/playermodels`, `create/hats` |

Still fixed in the file: `CS2` and `PORT` at the top of every `.bat` and of `build_maps.ps1` in `scripts/`; `STEAM_CSGO_ROOT` in
`scripts/post_import_cleanup.py` (also `--steam-root`); `autoport/polish.py` and `ingame_check.py` (cs2port root); the hard-coded
addon in `scripts/modelsfromrefs.py`'s CONFIG block; `create/playermodels/mdl2cs2.py` `BASEGAME`.

Known unevenness: `create/build_prop.py` reads `toolkit.json` before the environment while `create/vmapgen.py` reads the
environment only, and six `create/` scripts parse `toolkit.json` themselves instead of going through `modelio.CONF`.

### Proposed: one optional settings file

Precedence, the same everywhere: **command-line argument, then environment variable, then settings file, then a detected default.**

- File: `cs2mapping.json` (JSON, no new dependency), looked for at `%CS2MAPPING_CONFIG%`, then next to the cs2port root, then in the
  repo clone. A checked-in `cs2mapping.example.json` documents every key; the real file is git-ignored.
- Keys mirror the table above (`cs2_root`, `cs2port`, `source1`, `repo`, `bspsource`, `backups`, `create_out`, ...), plus a
  `workspaces` map so more than one mapping workspace can be named.
- Detection for `cs2_root` only: Steam's `libraryfolders.vdf` (read from the registry's Steam path) for app 730. Nothing else is guessed.
- One small module, `tools/cs2paths.py`, returns the resolved paths and a list of what is missing; `autoport/common.py` and the
  `tools/` constants import from it. The existing names (`CS2`, `PORT`, `S1`, ...) stay, so no caller changes.
- The batch files read the same values from `cs2paths.py --bat` (prints `set "CS2=..."` lines) instead of their own `set` lines.
- `cs2mapping doctor` (below) prints each path, where its value came from, and what is missing.

Why it was not built in this pass: the batch files and `build_maps.ps1` are what the mapper double-clicks, and they cannot be tested
without running real imports and builds, which this pass was not to do. The environment overrides above were the part that could be
added and tested safely.

## Dependencies

Files in [`requirements/`](../../requirements): `porting.txt`, `porting-optional.txt`, `creation.txt`, `models.txt`,
`models-optional.txt`, `dev.txt`, and `constraints.txt` (the exact versions last run with). Install one group with the constraints:

```
pip install -r requirements/porting.txt -c requirements/constraints.txt
```

What the audit found:

- Three packages carry almost everything: numpy (about 270 files), Pillow (about 170), scipy (about 50). `autoport/` needs none.
- Used by one or two tools each, and optional: `mutagen`, `lameenc`, `lz4` (porting); `fast_simplification`, `playwright` (models,
  previews); `matplotlib` (one mg_trenchwarfare script). Blender's `bpy` is needed only by the two scripts that run inside Blender.
- Node: no third-party packages except `playwright` in two cs2-fighter preview scripts. No lockfile is needed. TypeScript is a global
  install for type-checks (`npm i -g typescript`; 7.0.2 was used).
- `projects/hellmatch-cs2/preview/package.json` was an empty `npm init` stub (no dependencies, a failing `test` script, an "ISC" licence
  line that was never true); removed 11 Nov 2026. The repo now has no `package.json`.
- Nothing was upgraded. No lower version bounds are stated because none were tested.

## Development workflow

Decisions, with reasons:

- **Shared helpers only where they remove a real risk.** `tools/safepath.py` exists because five tools needed the same three checks
  around deletes and overwrites. Logging, argument parsing and progress output were left per tool: autoport already has its dated
  log and watchdog heartbeats, and merging the tools' argument styles would change command lines people and docs rely on.
- **Exit codes** already in use, to keep: `0` done, `1` a check found problems, `2` could not run (bad arguments, missing input).
  autoport's watchdog adds `124` hung and `125` over the time limit. New tools should use the same.
- **Tests** are `unittest`, run with `python -m unittest discover -s <area>/tests`. No test framework dependency.

### `cs2mapping.py` (started 11 Nov 2026)

`python cs2mapping.py doctor [--json]`, `check` and `test` exist at the repo root: `doctor` reports Python, Node, the packages of each
requirements group, every path and whether it came from an environment variable or the default, Valve's tools and content, and whether
the PC copy of `tools/` and `autoport/` matches the clone. It reads only. The rest of the table below is still a proposal.

### Proposed: the rest of one `cs2mapping` command

Worth doing as a thin front door, not as a rewrite: a single `cs2mapping.py` at the repo root that only dispatches to the existing
scripts, so every current command line keeps working.

| Command | Calls | Notes |
|---|---|---|
| `cs2mapping doctor` | new, small | Python and Node versions, packages per requirements group, each path and where it came from, Workshop Tools present, PC copy of `tools/` against the repo. JSON with `--json`. The one genuinely new command, and the most useful for a new PC. |
| `cs2mapping config` | new, small | print the resolved settings; `--init` writes the example file |
| `cs2mapping backup` / `restore` / `verify` | `tools/mapbackup.py save / restore / verify` | |
| `cs2mapping port <maps>` | `autoport/autoport.py` | `--dry-run` passes through |
| `cs2mapping apply` / `rollback <addon>` | `autoport/pclocal.py` | |
| `cs2mapping validate <addon>` | `tools/mapsanity.py`, `fgdcheck.py`, `mapcheck.py` | one combined JSON report with a `level` field ([compatibility.md](compatibility.md#verification-levels)) |
| `cs2mapping compile <addon>` | `tools/rcompile.py` / `scripts/build_maps.ps1` | |
| `cs2mapping check` | `ci/check_repo.py`, `ci/check_links.py` | what CI runs |

Order to build it in: `doctor` and `check` first (no risk, immediate use), then the pass-through commands. `create` is left out: the
creation toolkit is dozens of unrelated generators and gains nothing from one verb.

### Proposed: releases

There are no tags or releases today; `main` is the only published state and the changelog is by date.

- Keep the dated changelog. Add **date-based tags** for known-good states, `vYYYY.MM.DD` (for example `v2026.11.11`), rather than
  semantic versions: the repo is a toolkit and a knowledge base with no API whose compatibility a version number could promise.
- A tag is cut only when CI is green and the pipeline has ported and built at least one map on the PC since the last tag. The release
  notes are that period's changelog entries plus a copy of the "Last verified environment" row and the CS2 build used.
- `main` between tags is the development state. The README says which tag is the last known-good one.
- A release note template is in [`.github/release_template.md`](../../.github/release_template.md). Nothing publishes automatically.

## Next steps

Highest value first.

1. ~~Run CI once on GitHub~~ Done 11 Nov 2026: green on all four jobs after two fixes.
2. **Record the CS2 build** in each port README when a map is built, and in the compatibility table.
3. **The settings file** (above), starting with the Python side; `doctor` already reports where each path comes from.
4. ~~Backups for `matnames`, `vmdlfix`, `gibfix`; atomic `vmapedit.Map.save`~~ Done 11 Nov 2026. Left: `polish.py` and `profiles.py`
   ([file-safety.md](file-safety.md#what-still-writes-without-a-backup-or-a-preview)).
5. ~~`level` and `manual_check_required` fields~~ Done 11 Nov 2026.
6. ~~Correct the MCP tools' `destructiveHint`~~ Done 11 Nov 2026.
7. ~~Dry run for `build_maps.ps1`~~ Done 11 Nov 2026 (`-DryRun`), with `run_import.bat --dry-run`. Left: `run_fixrefs.bat`.
8. Decide whether the 27 MB of tracked music and reference `.vmap` files under `projects/` that `.gitignore` now excludes should stay.
