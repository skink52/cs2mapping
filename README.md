# cs2mapping

Everything skink52 and Claude have worked out about **making Counter-Strike 2 maps with an AI agent**, in one place:
**porting** CS:GO maps to CS2 (mainly `mg_` minigames, plus jailbreak and a few `de_` maps) and **creating** original CS2 addons
(script-driven minigames, generated maps, models, HUDs, weapons, sound). Formerly `cs2portdocs`.

> **AI-generated code.** The scripts and most of the write-ups in this repo were produced by Claude, an AI agent, working with skink52.
> They aren't hand-written code, so please don't read them as a showcase of anyone's own programming. They're shared because the knowledge in them is useful.

**New here? Read [CAPABILITIES.md](CAPABILITIES.md)** — a plain-language list of everything this toolkit can do, no coding knowledge needed.

## Porting CS:GO maps to CS2

| | |
|---|---|
| [docs/porting/pipeline.md](docs/porting/pipeline.md) | The cs2port pipeline: stages A–D, who does what, every automatic fix |
| [docs/porting/conventions.md](docs/porting/conventions.md) | House rules: naming, credits, lights, lasers, radar, vis, multi-arena maps |
| [docs/porting/setup.md](docs/porting/setup.md) | Which repo file goes where on the PC |
| [docs/porting/manual-workflow.md](docs/porting/manual-workflow.md) | The by-hand method the pipeline replaced |
| [`tools/`](tools/README.md) | The pipeline (Python, runs on the PC through autoport or Claude Code, or in Claude's cloud workspace): decompile prep, Hammer-save fix, `.vmap` editing, post-import fixes, radar, sky, vis, lights, overlays, texture scales, map previews. [tools/README.md](tools/README.md) is the index of every tool with its usage line |
| [`scripts/`](scripts/README.md) | PC-side runners: import, command-line build, post-import cleanup, model import, unattended import→build |
| [`autoport/`](autoport/README.md) | **The normal way to port.** Paste map names; it runs every stage on the PC with each map type's extra steps (TTT, course, jailbreak), checks each map (entities, z-fighting, gibs, build logs), builds the good ones and holds the rest for Claude, who marks them ready to build. Hang watchdog, live monitor window, dated log |
| [`ports/`](ports) | One folder per ported map: status, Workshop link, fixes, open issues, cleanup log, the map's cs_script files |
| [`data/`](data/README.md) | `existing_ports.txt` (which maps have CS2 ports, by whom) and the queue files |
| [`legacy/`](legacy/README.md) | Helpers from the early manual ports |

## Creating original CS2 addons

| | |
|---|---|
| [docs/creation/guide.md](docs/creation/guide.md) | How the original minigames are built: project shape, writing the map, world layout, the script, assets, testing, delivery |
| [docs/creation/models.md](docs/creation/models.md) | Props from GLB files, procedural props with baked textures, stock materials, voxel models, CS:GO player models rebuilt as CS2 agents, animated rigs |
| [docs/creation/hud.md](docs/creation/hud.md) | Panorama HUDs (`custom_hud_layout`), screen overlays, loading screens, map icons, radar |
| [docs/creation/custom-weapons.md](docs/creation/custom-weapons.md) | New weapons without plugins: `weapons.vdata` override, rigging models onto stock weapon skeletons, scopes |
| [docs/creation/sound.md](docs/creation/sound.md) | Sound events, music, loops, synthesised audio |
| [docs/creation/workshop.md](docs/creation/workshop.md) | Publishing, Workshop limits, keeping content safe to publish |
| [`create/`](create/README.md) | The creation toolkit (index in [create/README.md](create/README.md)): lossless vmap read/write and map generation, mesh writer/checker, GLB→prop, procedural props, stock textures, voxel models, HUD/loading-screen/sky/sound generators and checkers. Subfolders: [`create/test/`](create/test) (cs_script type-check and mock engine), [`create/build/`](create/build) (script build template), [`create/anim/`](create/anim) (mocap retarget, IK, joint validator, rig vmdl writer), [`create/s2/`](create/s2) (compiled-resource readers), [`create/playermodels/`](create/playermodels/README.md) (GMod player models → CS2), [`create/hats/`](create/hats/README.md) (GMod hats → CS2 hats that bone-merge onto any player) |
| [`tools/weapons/`](tools/README.md#weapons-the-custom-weapon-builder-creation-not-porting) | The weapon builder (FBX/GLB → rigged CS2 weapon) |

## Reference (both)

| | |
|---|---|
| [docs/reference/cs2-gotchas.md](docs/reference/cs2-gotchas.md) | What breaks in CS2 and the fix: importer, models, lighting, vis, entities, sound, players, Workshop |
| [docs/reference/cs_script-notes.md](docs/reference/cs_script-notes.md) | cs_script patterns: wiring, input, movement, weapons, kills/rounds, cameras, prop pools, HUD API, performance, testing |
| [docs/reference/external-tools.md](docs/reference/external-tools.md) | Outside tools and references (Valve, BSPSource, Source 2 Viewer, Hammer5Tools, cs2-slop-porting, mocap, …) and their traps |
| [docs/reference/ai-workflow.md](docs/reference/ai-workflow.md) | Working with Claude: who does what, house rules, transfer limits, unattended runs, verifying without the game |
| [docs/reference/compatibility.md](docs/reference/compatibility.md) | What "tested" means here (unit tested, simulated, compiled, in-game verified, playtested), what CI covers, the versions last run with |
| [docs/reference/file-safety.md](docs/reference/file-safety.md) | What each tool overwrites or deletes, its backups, dry runs, and how to roll back |
| [docs/reference/engineering-notes.md](docs/reference/engineering-notes.md) | Path settings and environment variables, dependencies, and the proposals for one settings file, one command and releases |
| [`cs2mapping.py`](cs2mapping.py) | `python cs2mapping.py doctor`: is this PC set up (Python, packages, paths, Valve's tools, PC copy against the clone)? `check` and `test` run what CI runs |
| [`requirements/`](requirements) / [`ci/`](ci/README.md) | pip lists per area (porting, creation, models) with the versions last run with; the repo checks CI runs |
| [CHANGELOG.md](CHANGELOG.md) | Dated history, newest first |

## What is *not* here

No map content: no BSPs, decompiled VMFs, `.vmap` files, or textures, models and sounds taken from the original maps. Those belong to the original mappers
(each port credits them in its loading screen: "original map by &lt;author&gt; cs2 port by skink52"). Valve's own import scripts aren't copied either;
[`scripts/make_import_map_auto.py`](scripts/make_import_map_auto.py) patches your local copy instead.

## Licence

Free for non-commercial use: copy, change, share and run anything here, including the tools, docs and cs_script files, and on game servers (donation/VIP servers are fine). Not to be sold, paywalled or built into a paid product or service. Code and docs: [PolyForm Noncommercial 1.0.0](LICENSE); art, sounds and maps: [CC BY-NC 4.0](LICENSE-CC-BY-NC-4.0.txt). Versions before 30 Oct 2026 were MIT.
It covers this repo's own work only (Hellmatch's Freedoom-derived content stays under Freedoom's licence; `create/s2/vendor/meshoptimizer` is MIT and `create/fonts`' Cinzel is under the SIL Open Font License, each with its licence file alongside). Valve's tools and files (the import scripts `scripts/` runs alongside, `create/test/point_script.d.ts`), and the original maps,
assets and sounds credited in each port, belong to their owners.

## Projects

Each original addon lives in [`projects/`](projects), with its full history (merged here in Nov 2026; the old repos are archived and point here).

| Project | Folder |
|---|---|
| Hellmatch CS2: Doom-style deathmatch from Freedoom's levels, 4 arenas × 16 players, entirely in cs_script (Freedoom content under [its own licence](projects/hellmatch-cs2/FREEDOOM_LICENSE.txt)) | [projects/hellmatch-cs2](projects/hellmatch-cs2) |
| Space Racer (plus Neon and Depth themes): 32-car anti-grav racer with generated tracks | [projects/space-racer-cs2](projects/space-racer-cs2) |
| mg_trenchwarfare: WW1 trenches with procedural props, mortars, biplanes and custom rifles | [projects/trenchwarfare-cs2](projects/trenchwarfare-cs2) |
| [projects/monsoon-cs2](projects/monsoon-cs2/) | mg_monsoon: second battle map of the mg_trenchwarfare series (Vietnam valley, helicopters, howitzer and rocket batteries, Conquest). In progress, paused; resume from its NOTES.md. |
| Puppet Brawl: 2.5D fighting game with mocap-based animation | [projects/cs2-fighter](projects/cs2-fighter) |
| TTT for CS2: drop-in Trouble in Terrorist Town cs_script for any map | [projects/cs2mapTTT](projects/cs2mapTTT) |
| CS 1.6 in CS2 (mg_cs16): 1.6 maps and rules in one CS2 map | [projects/cs21.6](projects/cs21.6) |
| IRONFRAME (mg_ironframe_dunes / _sprawl / _orbital): 64-player Armored Core style mech combat, saved progression on the minigame server (SlimeMG IronFrame module), AI fill and co-op sorties | [projects/ironframe-cs2](projects/ironframe-cs2) |
| Nanite Temple (mg_nanite_temple): 64-player roguelike, squads through randomised temple vaults into one showdown arena, CS2 gunplay and buy menu kept | [projects/cs2-roguelike](projects/cs2-roguelike) |
| The ported maps | [ports/](ports/README.md) |
