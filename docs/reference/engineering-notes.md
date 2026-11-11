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

**Counted again on 11 Nov 2026** (code files, tests and documents left out): the CS2 install path is written in 23 files (6 in `tools/`,
4 in `autoport/`, 8 in `scripts/`, 5 in `create/`); 11 of them read `CS2_ROOT` first, and the 12 that do not are the `scripts/` batch files
and the five `create/` scripts. The cs2port root is written in 17 files, 5 of which read `CS2PORT`. Eleven `create/` scripts know about
`toolkit.json`. The MCP servers (`tools/mcp_server.py`, `autoport/mcp_live.py`) take their paths from the modules they wrap, so they follow
whatever those modules resolve and need no keys of their own.

Keys the file should end up with, and what each replaces:

| Key | Meaning | Today |
|---|---|---|
| `cs2_root` | the CS2 install | `CS2_ROOT`, 23 literals |
| `source2_content`, `source2_game` | `<cs2_root>\content\csgo_addons`, `<cs2_root>\game\csgo_addons`; a key only so a test or a second install can point elsewhere | joined by hand in each tool |
| `source1` | the Source 1 workspace (decompiled maps, the CS:GO `pak01_dir.vpk`) | `CS2MAP_SOURCE1` |
| `workspace` | the cs2port root (tools copy, logs, `work\`) | `CS2PORT` |
| `bspsource` | BSPSource launcher | `BSPSRC` |
| `backups` | map backup store | `CS2MAP_BACKUPS`, `--store` |
| `tools.blender`, `tools.steamcmd`, `tools.vtfcmd`, `tools.node` | optional external programs | `STEAMCMD`, PATH lookups, literals |

The project layer of the precedence (argument, environment, **project file**, detected default) is a `cs2mapping.json` found by walking up
from the folder a tool is run in, the way `create/toolkit.json` is found today; `create/toolkit.json` keeps working and is read as that
project's file. A project file may set only the creation keys and `workspace`; it may not move `cs2_root` (one install per PC, and a
project folder is not the place a wrong value should hide).

Safest order to build it in, each step shippable and reversible on its own:

1. `tools/cs2paths.py`: `resolve()` returns every key with its value and its source (`argument`, `env:NAME`, `file:<path>`, `default`).
   It reads the environment names of today, so with no file present every value is what it is now. Unit tests only; nothing calls it yet.
2. `cs2mapping doctor` prints from it. Any difference from what doctor prints today is a bug in step 1, found before a tool depends on it.
3. `autoport/common.py` takes `CS2`, `PORT`, `S1`, `REPO` from it (the names stay; the 87 autoport tests already patch them).
4. The `tools/` constants, one tool per commit.
5. `create/modelio.CONF` becomes a view of it; the six scripts that parse `toolkit.json` themselves go through `CONF`.
6. Last, the batch files and `build_maps.ps1`, through `cs2paths.py --bat` / `--ps1`, each tried with its dry run before a real one.

What would make it unsafe: changing a default while moving it, resolving at import time in a module the tests patch, or letting a
project file redirect a destructive tool. Steps 1 and 2 avoid all three and are the part worth doing next.

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

`project-report` was added on 11 Nov 2026 (`python cs2mapping.py project-report <project> [--vmap FILE] [--json]`): it calls
`create/context.py`, `create/test/api.py` and `tools/mapdigest.py` as libraries and joins what they return. It holds no logic of its own
beyond the cross-check of `RunScriptInput` names against the scripts' `OnScriptInput` names, and each tool is still run alone.

### Proposed: a project manager (not built)

The aim: one place that knows, for every project and port, its addon, maps, scripts, last build, last validation, open warnings, backups,
API state and how far it was verified. The pieces exist; what is missing is a record that outlives a session.

**Reuse, do not rewrite.** `create/context.py` (where a project stands, git, scripts, tests), `create/test/api.py` (API state),
`tools/mapdigest.py` (map facts), `tools/mapsanity.py` / `fgdcheck.py` / `mapcheck.py` (validation, already JSON with a `level`),
`tools/mapbackup.py` (backup history: its store is already a list of stamped, hashed copies), `autoport`'s per-map state and held-map
list (build and port history), the apply / deliver manifests (what changed on disk), `ports/<addon>/README.md` (the human record), and
`cs2mapping.py doctor` (the environment).

**Data.** One small file per project, `project.json` beside its README (in git: it is a record, like the README), written only by the
manager and only by appending or replacing whole sections:

```json
{ "schema": 1, "name": "mg_example", "kind": "port", "addon": "mg_example",
  "maps": [{ "vmap": "maps/mg_example.vmap", "vmf": "mg_example.vmf", "sha256": "...", "entities": 1220 }],
  "scripts": [{ "file": "scripts/mg_example_io.js", "sha256": "...", "api": { "invalid": 0, "deprecated": 0, "allowed": 0 } }],
  "runs": [{ "when": "2026-11-11T14:02", "what": "build", "ok": true, "level": "compiled", "cs2_build": "...", "log": "...", "warnings": 3 }],
  "verified": { "level": "compiled", "when": "2026-11-11", "by": "skink52", "note": "" },
  "open": [{ "id": 1, "text": "loading screen image missing", "since": "2026-11-09" }] }
```

`runs` is append-only and capped (the last 50); `verified.level` is one of the seven words in [compatibility.md](compatibility.md) and only a
person sets `in-game verified` or `playtested` (`cs2mapping project verify <name> --level ...`): no tool may raise it. Dependencies
(models, materials, sounds a map uses) are not stored: `mapdigest.py` and `scripts/vmap_refs.py` recompute them from the map in seconds,
and a stored copy would go stale. Machine paths never go in the file; they come from the settings file above.

**Commands** (all under the existing front door; every one except `record` and `verify` reads only):

| Command | Does |
|---|---|
| `cs2mapping project list` | every project and port: kind, verified level, last run, open items, uncommitted files |
| `cs2mapping project show <name>` | today's `project-report`, plus the stored runs and open items |
| `cs2mapping project record <name> --from <result.json>` | append a run from a tool's JSON result (`mapsanity`, `rcompile`, autoport's state) |
| `cs2mapping project verify <name> --level <word> [--note ...]` | a person records how far it was checked |
| `cs2mapping project backups <name>` | `mapbackup.py`'s store for that addon |

**MCP.** Two read-only tools on the existing `tools/mcp_server.py` (`project_list`, `project_show`), marked read-only like the current
inspection tools; `project_record` as a third, not destructive but writing, so it follows the `script_write` rules (name guard, repo
folder only). No new server.

**Configuration.** Needs the settings file's `workspace` and `source2_content` to find the addon behind a project; without them `show`
reports the repo side only, as `project-report` does now.

**Risks.** (1) A second source of truth beside the READMEs: keep `project.json` to facts a tool measured and leave prose in the README.
(2) Stale records presented as current: every stored fact carries the file hash it was measured on, and `show` marks a fact stale when the
hash no longer matches. (3) Automated writes into `projects/` folders another session is editing: `record` refuses when the folder has
uncommitted changes it did not make. (4) Verification inflation: only the `verify` command, run by a person, sets the two highest levels.
(5) Growth into a framework: no database, no daemon, no plugin system; if `project.json` and five subcommands are not enough, the answer
is a better README, not more machinery.

Order: `project list` and `show` from what exists (no stored file at all), then `record` fed by autoport, then `verify`.

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
