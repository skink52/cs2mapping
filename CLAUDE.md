# Instructions for Claude sessions working on this repo

This repo is the shared memory for skink52's CS:GO → CS2 map ports: the cs2port pipeline, the PC runners, the per-map records and
what was learned along the way. Keep it current. If you change the pipeline, fix a port, or discover a CS2 behaviour, record it here
in the same session.

## Layout

- `tools/`: cs2port pipeline (runs in the cloud workspace). Entry points: `prep.py` (stage A), `stage_c.py` (stage C),
  `stage_d.py` (follow-up passes). The library modules are `vmapedit.py`/`dmx.py`/`kv2.py` (vmap read/write), `vmf.py`, `vpk.py` and `vtf.py`.
  The passes live in `lighting.py`, `beams.py`, `daylight.py`, `skyvis.py`, `radar.py`, `sky.py`, `assets.py` and `gen_script.py`.
- `scripts/`: things that run on the Windows PC (`run_import.bat`, `run_build.bat`, `build_maps.ps1`,
  `post_import_cleanup.py`, `modelsfromrefs.py`, `make_import_map_auto.py`).
- `docs/pipeline.md`: the pipeline reference. It is deployed to the PC as `C:\source1\cs2port\tools\README.md` and
  `C:\source1\cs2port\cs2_port_pipeline.md`, and mirrored in the claude.ai project as `claude/cs2_port_pipeline.md`.
- `docs/setup.md`: which repo file goes where on the PC.
- `ports/<addon>/`: `README.md` (status, history, open issues), the cleanup log/report, and the map's own `scripts/*.js`.
- `CHANGELOG.md`: dated history, newest first.
- `data/existing_ports.txt`: snapshot only. The live file is `C:\source1\cs2port\existing_ports.txt` on the PC.

## Rules

- **The PC copy is what runs.** After changing anything in `tools/` or `scripts/`, copy the changed files to their PC paths
  (see `docs/setup.md`) and say which ones you copied. Then check the sizes on the PC, because a stale copy has been delivered once before.
- **No map content in git.** That means BSPs, VMFs, `.vmap`/`.vpk` files, and materials, models or sounds from the original maps. It also
  means no Valve scripts (`import_map_community.py`, `utils/`). `.gitignore` blocks the usual extensions. The two small template
  `.vmap` files in `tools/` are our own and are allowed.
- **No personal details.** Use the handle skink52, never a real name, email, or `C:\Users\...` path.
- Keep the "AI-generated code" disclaimer in `README.md`.
- When a port gets fixes: update `ports/<addon>/README.md` (what changed and why, what's still open), copy the new cleanup log and
  changed scripts into `ports/<addon>/`, and add a `CHANGELOG.md` line.
- When a CS2 behaviour is discovered (something that worked in CS:GO and doesn't in CS2, plus the workaround), add it to
  `docs/cs2-gotchas.md`.
- Commit messages say what changed and which map or pass it was for.
- Hammer must be closed while editing a map on the PC. Back up the `.vmap` before editing it, and send only changed files.
