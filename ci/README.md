# ci/: repository checks

What GitHub Actions runs ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)), runnable by hand from the repo root. None of it
needs CS2. These files are not part of the pipeline and are not copied to the PC.

| File | What it does |
|---|---|
| `check_repo.py [check ...] [--json FILE]` | Eight checks, all by default: `python` (every tracked `.py` compiles), `node` (`node --check` on every `.js` / `.mjs` / `.cjs`; skipped without Node), `json`, `hygiene` (no build output, nothing over 20 MB), `private` (no user-profile paths), `control` (no control characters in text: usually a Windows path whose backslash was lost), `licence` (both licence files in the root and each project, no README calling the repo's code MIT), `docs` (the stage C and stage D lists in `pipeline.md` and `tools/README.md` match the code). Exit 1 when a check fails. |
| `check_links.py [--anchors] [--baseline FILE] [--json FILE] [path ...]` | Relative links in tracked Markdown: the target must be tracked, with the right letter case; `--anchors` checks `#heading` fragments too. |
| `known_broken_links.txt` | Links CI accepts for now, one `file: link` per line. Remove a line when its link is fixed; the checker says when one no longer applies. |
| `mock_ports.sh [players=8] [seconds=30]` | Every `ports/*/scripts/*.js` through the stand-in engine. A simulated run: it finds script errors, it does not show anything works in CS2. |

Before pushing: `python ci/check_repo.py && python ci/check_links.py --anchors --baseline ci/known_broken_links.txt`, then the unit
tests (`python -m unittest discover -s tools/tests`, `python -m unittest discover -s autoport/tests`).
What each CI job does and does not prove: [docs/reference/compatibility.md](../docs/reference/compatibility.md#what-ci-covers).
