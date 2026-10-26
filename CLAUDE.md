# Instructions for Claude sessions working on this repo

This repo (`cs2mapping`, formerly `cs2portdocs`) is the shared memory for skink52's CS2 mapping: CS:GO → CS2 ports (the cs2port pipeline,
the PC runners, the per-map records) and original CS2 addons (the creation toolkit and guides), plus what was learned along the way. Keep it current. If you change the pipeline, fix a port, or discover a CS2 behaviour, record it here
in the same session.

## Layout

- `tools/`: cs2port pipeline (runs in the cloud workspace). Entry points: `prep.py` (stage A), `stage_c.py` (stage C), `stage_d.py` / `run_pass.py`
  (follow-up passes). **Every file, its job and its usage line are in the tool index, `tools/README.md`**: keep it in step when a tool or a usage line changes.
  `tools/weapons/` is the custom weapon builder (creation, not porting).
- `scripts/`: things that run on the Windows PC (`run_import.bat`, `run_build.bat`, `build_maps.ps1`, `run_import_then_build.bat`,
  `run_build_one_example.bat`, `post_import_cleanup.py`, `vmap_refs.py`, `modelsfromrefs.py`, `make_import_map_auto.py`); see `scripts/README.md`.
- `create/`: the creation toolkit for original addons; its index is `create/README.md`.
- `docs/porting/`, `docs/creation/`, `docs/reference/` (gotchas, cs_script notes, AI workflow, external tools). `CAPABILITIES.md` is the plain-language list for non-coders:
  keep it in step when a capability is added.
- `docs/porting/pipeline.md`: the pipeline reference (workflow, every stage C step). It is deployed to the PC as `C:\source1\cs2port\cs2_port_pipeline.md`
  and mirrored in the claude.ai project as `claude/cs2_port_pipeline.md`. The tool index `tools/README.md` deploys with `tools/` as
  `C:\source1\cs2port\tools\README.md`; it links to pipeline.md rather than copying it.
- `docs/porting/setup.md`: which repo file goes where on the PC.
- `ports/<addon>/`: `README.md` (status, history, open issues), the cleanup log/report, and the map's own `scripts/*.js`.
- `CHANGELOG.md`: dated history, newest first.
- `data/existing_ports.txt`: snapshot only. The live file is `C:\source1\cs2port\existing_ports.txt` on the PC.

## Rules

- **The PC copy is what runs.** After changing anything in `tools/` or `scripts/`, copy the changed files to their PC paths
  (see `docs/porting/setup.md`) and say which ones you copied. Then check the sizes on the PC, because a stale copy has been delivered once before.
- **No map content in git.** That means BSPs, VMFs, `.vmap`/`.vpk` files, and materials, models or sounds from the original maps. It also
  means no Valve scripts (`import_map_community.py`, `utils/`). `.gitignore` blocks the usual extensions. The two small template
  `.vmap` files in `tools/` (`box_template.vmap`, `laser_template.vmap`) are our own and are allowed. `tools/addon_template/` is Valve's and stays out of git.
- **No personal details.** Use the handle skink52, never a real name, email, or `C:\Users\...` path.
- Keep the "AI-generated code" disclaimer in `README.md`.
- When a port gets fixes: update `ports/<addon>/README.md` (what changed and why, what's still open), copy the new cleanup log and
  changed scripts into `ports/<addon>/`, and add a `CHANGELOG.md` line.
- When a CS2 behaviour is discovered (something that worked in CS:GO and doesn't in CS2, plus the workaround), add it to
  `docs/reference/cs2-gotchas.md`. cs_script API findings go in `docs/reference/cs_script-notes.md`.
- When an original addon project learns something reusable (a model method, HUD trick, engine limit), add it to the creation docs and, if it's a tool,
  a project-neutral copy in `create/`.
- Commit messages say what changed and which map or pass it was for.
- Hammer must be closed while editing a map on the PC. Back up the `.vmap` before editing it, and send only changed files.
