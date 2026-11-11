# Instructions for Claude sessions working on this repo

This repo (`cs2mapping`, formerly `cs2portdocs`) is the shared memory for skink52's CS2 mapping: CS:GO → CS2 ports (the cs2port pipeline,
the PC runners, the per-map records) and original CS2 addons (the creation toolkit and guides), plus what was learned along the way. Keep it current. If you change the pipeline, fix a port, or discover a CS2 behaviour, record it here
in the same session.

## Start here: which project?

The user names a project ("work out of cs2mapping, we're on TTT maps"). Find it below, run `python create/context.py <project>` for a
snapshot of where it stands (resume notes, uncommitted work, scripts, tests, and which section of which document to open), then read
the project's own instructions file and work in that folder. The snapshot is a map of where to look, not a substitute for the section it points at.
One clone of this repo covers everything; there are no other repos to clone or push.
On the PC, Claude Code runs from `C:\source1` and reaches CS2, `C:\source2` and the addon folders through `C:\source1\links\` junctions
([docs/porting/setup.md](docs/porting/setup.md#claude-code-on-the-pc-one-folder)). Never search recursively over `links\cs2_root` or `links\csgo`.

| User says | Folder | Read first |
|---|---|---|
| TTT, TTT script, ttt_ maps | `projects/cs2mapTTT/` (the script) + `ports/ttt_*/` (map ports) | `projects/cs2mapTTT/CLAUDE.md` |
| Hellmatch, FreeDM, Freedoom DM | `projects/hellmatch-cs2/` | `projects/hellmatch-cs2/docs/STATUS.md` |
| Space Racer, Neon Racer, Depth Racer, racing | `projects/space-racer-cs2/` (themes via `SPR_THEME`) | `projects/space-racer-cs2/README.md`, `docs/DESIGN.md` |
| Puppet Brawl, fighter, fighting game | `projects/cs2-fighter/` | `projects/cs2-fighter/README.md` |
| Trench warfare, WW1, mg_trenchwarfare, custom rifles | `projects/trenchwarfare-cs2/` | `projects/trenchwarfare-cs2/NOTES.md` |
| Monsoon, mg_monsoon, valley map, helicopters + firebase, the second battle map | `projects/monsoon-cs2/` | `projects/monsoon-cs2/NOTES.md` (Resume here), `docs/DESIGN.md` |
| CS 1.6, mg_cs16 | `projects/cs21.6/` | `projects/cs21.6/README.md` |
| Roguelike, Nanite Temple, mg_nanite_temple, vaults/squads/showdown | `projects/cs2-roguelike/` | `projects/cs2-roguelike/docs/DESIGN.md`, `README.md` |
| IRONFRAME, mech game, Armored Core style, mg_ironframe_* | `projects/ironframe-cs2/` | `projects/ironframe-cs2/docs/STATUS.md`, `docs/DESIGN.md` |
| Porting, a CS:GO map name, mg_/jb_/ba_ ports | `ports/<map>/`, `tools/`, `scripts/` | `docs/porting/pipeline.md` |
| Unattended ports, autoport, a port cleanup list | `autoport/` | `autoport/README.md`; `autoport/REVIEW.md` when reviewing held maps |
| A new original addon | new `projects/<name>/` | `docs/creation/guide.md` |
| GMod player models, converting player models, playermodel batch | `create/playermodels/` (work folder `C:\source1\playermodels\`) | `docs/creation/gmod-playermodels.md`, `create/playermodels/README.md` |
| GMod hats, hats/accessories for the shop, hat batch | `create/hats/` (work folder `C:\source1\hats\`) | `docs/creation/gmod-hats.md`, `create/hats/README.md` |

Bomb Arena (BomberClone-style) has no folder yet; create `projects/<name>/` when its source is first committed.
New projects get their own folder under `projects/`, a README (with the AI disclaimer), the licence files, and a row in this table and in `README.md`.

## Layout

- `tools/`: cs2port pipeline (runs on the PC from `C:\source1\cs2port	ools`, through autoport or Claude Code; the cloud workspace is the older route). Entry points: `prep.py` (stage A), `stage_c.py` (stage C), `stage_d.py` / `run_pass.py`
  (follow-up passes). **Every file, its job and its usage line are in the tool index, `tools/README.md`**: keep it in step when a tool or a usage line changes.
  `tools/weapons/` is the custom weapon builder (creation, not porting).
- `scripts/`: things that run on the Windows PC (`run_import.bat`, `run_build.bat`, `build_maps.ps1`, `run_import_then_build.bat`,
  `run_build_one_example.bat`, `post_import_cleanup.py`, `vmap_refs.py`, `modelsfromrefs.py`, `make_import_map_auto.py`); see `scripts/README.md`.
- `create/`: the creation toolkit for original addons; its index is `create/README.md`. `create/context.py` (project snapshot) and
  `create/test/api.py` (typings lookup and call check) are the two to run before working on a project's scripts.
- `ci/` and `.github/workflows/ci.yml`: the repo checks and what CI runs (`ci/README.md`). `requirements/`: pip lists per area. Neither is copied to the PC.
  Before committing: `python ci/check_repo.py` and `python ci/check_links.py --anchors --baseline ci/known_broken_links.txt`.
- How far something was checked is said in the words of `docs/reference/compatibility.md` (unit tested, simulated, compiled, Hammer verified,
  in-game verified, playtested). Tools that overwrite or delete in an addon follow `docs/reference/file-safety.md` and use `tools/safepath.py`.
- `docs/porting/`, `docs/creation/`, `docs/reference/` (gotchas, cs_script notes, AI workflow, external tools). `CAPABILITIES.md` is the plain-language list for non-coders:
  keep it in step when a capability is added.
- `docs/porting/pipeline.md`: the pipeline reference (workflow, every stage C step). It is deployed to the PC as `C:\source1\cs2port\cs2_port_pipeline.md`
  and mirrored in the claude.ai project as `claude/cs2_port_pipeline.md`. The tool index `tools/README.md` deploys with `tools/` as
  `C:\source1\cs2port\tools\README.md`; it links to pipeline.md rather than copying it.
- `docs/porting/setup.md`: which repo file goes where on the PC.
- `projects/<name>/`: one folder per original addon (imported Nov 2026 from its own repo with full history; the old repos are archived and point here).
  Each keeps its own layout, docs and tests; run its commands from inside its folder.
  `archive/cs2-fighter-anim-v3` and `archive/cs2-fighter-polish` are the fighter's unmerged side branches (original paths, not under `projects/`).
- `ports/<addon>/`: `README.md` (status, history, open issues), the cleanup log/report, and the map's own `scripts/*.js`.
- `CHANGELOG.md`: dated history, newest first.
- `data/existing_ports.txt`: snapshot only. The live file is `C:\source1\cs2port\existing_ports.txt` on the PC.

## Rules

- **Look the cs_script API up; never write it from memory.** Before writing or changing a script call, run
  `python create/test/api.py <word>` (or `--members CSPlayerPawn`): it prints the declaration from Valve's `create/test/point_script.d.ts`.
  The API moved in Oct-Nov 2026 and will move again. A script is not finished until `python create/test/api.py --check <script.js>` reports
  nothing unknown and `sh create/test/tscheck.sh <script.js>` passes; then the mock engine. All of that is "simulated", never "works in game".
- **Read a map through its digest, not its file.** `python tools/mapdigest.py <map.vmap> --summary`, then `--graph`, `--class`, `--name`,
  `--near` or `--touches` for the part in question: entities, names, positions and I/O wiring without the mesh data. It only reads.
  Edit with `tools/vmapedit.py` (or the stage passes), after a backup (`docs/reference/file-safety.md`).
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
- **Shared files are mastered here.** `create/libsync.json` lists the files copied into the game repos and the neutral tools forked from them.
  Edit a shared file here (or `pull` a fix made in a game repo), then `python3 create/libsync.py push` and commit every repo it touched.
  `copies` paths are inside `projects/<name>/`. Before committing, run `python3 create/libsync.py check`; port the generic part of any
  `ORIGIN CHANGED` fork into `create/` and `ack` it. New shared tools go in the manifest (`add`).
- Commit messages start with the area in brackets, e.g. `[ttt]`, `[hellmatch]`, `[port mg_pirates]`, `[create]`, and say what changed.
- Project discoveries that apply beyond the project go in the root docs (gotchas, cs_script notes, creation guides) as well as the project's notes.
- New projects get the standard non-commercial licence files ([docs/creation/workshop.md](docs/creation/workshop.md#licence)).
- Hammer must be closed while editing a map on the PC. Back up the `.vmap` before editing it, and send only changed files.
