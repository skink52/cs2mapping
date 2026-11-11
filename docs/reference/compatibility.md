# Compatibility and what "tested" means

CS2 and its Workshop Tools change with every update, and most of this repo was checked without the game. This page fixes the words
used for how far something has been checked, and records what the tools were last run with.

## Verification levels

Use exactly these words in docs, port READMEs, changelog lines and tool reports. Each level includes the ones above it only when that
is said; **a lower level never stands in for a higher one**. A simulated run or a clean compile is not evidence that something works in game.

| Level | Means | Typical evidence |
|---|---|---|
| **Untested** | Written, never run. | none |
| **Unit tested** | Run by an automated test on real inputs and real files (parsing, conversion, copying) in a temp folder. No game, no Valve tool. | `tools/tests`, `autoport/tests` (the parts that touch files), `create/anim/test_smoke.mjs` |
| **Simulated** | Run against a stand-in for the game: the mock script engine, a fake CS2 console, a pure-logic simulation. Catches exceptions and known pitfalls; says nothing about rendering, physics, networking or engine quirks. | `create/test/mock_point_script.mjs`, `autoport/tests/fakecs2.py`, the projects' `test/sim*` |
| **Compiled** | Valve's `resourcecompiler` built it without errors on a real install. The result has not been looked at. | a build log, `tools/rcompile.py` report |
| **Hammer verified** | Opened in Hammer and looked right there. | a person's report |
| **In-game verified** | Loaded in CS2 and the specific thing was seen to work, alone. | a person's report, or `autoport/ingame_check.py` output for what it checks (the map loads, console errors, script output) |
| **Playtested** | Played by people in the way it will be used (several players, full rounds). | a playtest report |

When a write-up says only "tested", "works" or "verified", it should be read as the lowest level its evidence supports, and corrected
when next touched. Automated reports say which level they reached: see [Machine-readable reports](#machine-readable-reports).

## What CI covers

The GitHub Actions workflow ([`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)) needs no CS2 and reaches these levels only:

| Job | Level | What it runs |
|---|---|---|
| Repo checks | none (consistency only) | `ci/check_repo.py`: every `.py` compiles, every `.js` parses, JSON parses, no build output or profile paths tracked, licence files and statements agree, the documented stage C / stage D lists match the code. `ci/check_links.py`: relative Markdown links and anchors |
| Unit tests (Windows) | Unit tested, and Simulated for the console tests | `tools/tests`, `autoport/tests` |
| Unit tests (Linux) | Unit tested, informational | `tools/tests`; a failure does not block, the tools are Windows tools |
| Map scripts | Simulated | every `ports/*/scripts/*.js` in the mock engine, the TTT script's suite, the mg_trenchwarfare type-check |

CI has no CS2 install, so the tests that read CS2's own entity definitions (FGD files) are skipped there: 10 of the 133 `tools` tests
and 1 of the 76 `autoport` tests. They run in full on a PC with CS2 (`python cs2mapping.py test`).

Nothing in CI is Compiled, Hammer verified, In-game verified or Playtested. Those levels come from the PC and from people, and are
recorded per map in `ports/<addon>/README.md` and per project in its status file.

## Last verified environment

One machine, one date. Add a row when the tools are run somewhere else or after a CS2 update; do not overwrite old rows.

| Date | Windows | Python | Node | TypeScript | Python packages | CS2 / Workshop Tools build | What was run | Level reached |
|---|---|---|---|---|---|---|---|---|
| 2026-11-11 | Windows 11 (10.0.26200) | 3.13.15 | 26.13.0 | 7.0.2 | numpy 2.1.3, scipy 1.18.1, Pillow 12.3.0, mutagen 1.48.1, lameenc 1.9.0 | not recorded | `tools/tests` (133 tests), `autoport/tests` (76 tests), `ci/check_repo.py`, `ci/check_links.py`, `ci/mock_ports.sh` (55 scripts), TTT `run_mock.sh`, mg_trenchwarfare `tsc` | Unit tested / Simulated |

Not yet recorded anywhere: the CS2 build number and Workshop Tools version each port or tool was last built against, and the versions of
BSPSource, VTFCmd and RadGen in use. Record the CS2 build (Steam: Properties, Updates, or `version` in the console) in the port's README
when a map is built.

## Known limits

- **Windows only for the pipeline.** Stage B and D run Valve's Windows tools; autoport and the batch files assume Windows paths.
  The Python tools that only read and write files also run on Linux (the cloud route), but that route is not covered by CI beyond the
  informational Linux job.
- **Node 22.15+** for anything that reads zstd-compressed CS2 files (`create/s2`, `create/anim`, `tools/vmatc.py`); CI uses Node 22.
- **Python**: the tools are run with 3.13. `tools/weapons/material.py` needs 3.12 or newer. No older version has been tested.
- **TypeScript 6 or newer** for the projects' `tsconfig.json` files (they set `ignoreDeprecations: "6.0"`).
- **In-game check**: `autoport/ingame_check.py`'s console connection has been used on the real game; its map loading, screenshots and
  movement were only run against the fake console (Simulated).

## Machine-readable reports

Tools that check things should be able to write JSON saying what was checked, what passed, failed and was skipped, and whether a
person still has to look. Today:

| Tool | Report |
|---|---|
| `ci/check_repo.py --json FILE` | `{ok, checks: [{name, status: pass / fail / skipped, checked, problems, note}]}` |
| `ci/check_links.py --json FILE` | `{files, links, broken, known}` |
| `tools/mapbackup.py verify` | `{checked, bad: [{map, stamp, problem}]}`, exit 1 when a copy is damaged |
| `autoport/pclocal.py apply` | `<root>\out\<addon>_apply_<stamp>.json`: each file written, its sha256 before and after, its backup |
| `tools/stage_c.py` | `<root>/out/<addon>_result.json`: files written, CS:GO files still needed |
| `tools/rcompile.py`, `tools/mapsanity.py` | JSON on stdout with `--json` (see [tools/README.md](../../tools/README.md)) |

A report from an automated check should carry `"level"` (one of the names above, lower case) and `"manual_check_required": true`
whenever its level is below In-game verified. The tools in the last two rows do not yet; that is listed in
[engineering-notes.md](engineering-notes.md#next-steps).
