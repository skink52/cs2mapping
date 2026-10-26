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
| [`tools/`](tools) | The pipeline (Python, runs in Claude's workspace): decompile prep, Hammer-save fix, `.vmap` editing, post-import fixes, radar, sky, vis, lights, overlays, texture scales, map previews |
| [`scripts/`](scripts) | PC-side runners: import, command-line build, post-import cleanup, model import, unattended import→build |
| [`ports/`](ports) | One folder per ported map: status, Workshop link, fixes, open issues, cleanup log, the map's cs_script files |
| [`data/`](data) | `existing_ports.txt` (which maps have CS2 ports, by whom) and the queue files |
| [`legacy/`](legacy) | Helpers from the early manual ports |

## Creating original CS2 addons

| | |
|---|---|
| [docs/creation/guide.md](docs/creation/guide.md) | How the original minigames are built: project shape, writing the map, world layout, the script, assets, testing, delivery |
| [docs/creation/models.md](docs/creation/models.md) | Props from GLB files, procedural props with baked textures, stock materials, voxel models, CS:GO player models rebuilt as CS2 agents, animated rigs |
| [docs/creation/hud.md](docs/creation/hud.md) | Panorama HUDs (`custom_hud_layout`), screen overlays, loading screens, map icons, radar |
| [docs/creation/custom-weapons.md](docs/creation/custom-weapons.md) | New weapons without plugins: `weapons.vdata` override, rigging models onto stock weapon skeletons, scopes |
| [docs/creation/sound.md](docs/creation/sound.md) | Sound events, music, loops, synthesised audio |
| [docs/creation/workshop.md](docs/creation/workshop.md) | Publishing, Workshop limits, keeping content safe to publish |
| [`create/`](create) | The creation toolkit: lossless vmap read/write, mesh writer/checker, GLB→prop, procedural prop baker, stock texture reader, cs_script type-check and mock engine |
| [`tools/weapons/`](tools/weapons) | The weapon builder (FBX/GLB → rigged CS2 weapon) |

## Reference (both)

| | |
|---|---|
| [docs/reference/cs2-gotchas.md](docs/reference/cs2-gotchas.md) | What breaks in CS2 and the fix: importer, models, lighting, vis, entities, sound, players, Workshop |
| [docs/reference/cs_script-notes.md](docs/reference/cs_script-notes.md) | cs_script patterns: wiring, input, movement, weapons, kills/rounds, cameras, prop pools, HUD API, performance, testing |
| [docs/reference/external-tools.md](docs/reference/external-tools.md) | Outside tools and references (Valve, BSPSource, Source 2 Viewer, Hammer5Tools, cs2-slop-porting, mocap, …) and their traps |
| [docs/reference/ai-workflow.md](docs/reference/ai-workflow.md) | Working with Claude: who does what, house rules, transfer limits, unattended runs, verifying without the game |
| [CHANGELOG.md](CHANGELOG.md) | Dated history, newest first |

## What is *not* here

No map content: no BSPs, decompiled VMFs, `.vmap` files, or textures, models and sounds taken from the original maps. Those belong to the original mappers
(each port credits them in its loading screen: "original map by &lt;author&gt; cs2 port by skink52"). Valve's own import scripts aren't copied either;
[`scripts/make_import_map_auto.py`](scripts/make_import_map_auto.py) patches your local copy instead.

## Licence

MIT ([LICENSE](LICENSE)): copy, change and reuse anything here, including the tools, docs and cs_script files, as long as the licence notice goes with it.
It covers this repo's own work only. Valve's tools and files (the import scripts `scripts/` runs alongside, `create/test/point_script.d.ts`), and the original maps,
assets and sounds credited in each port, belong to their owners.

## Projects built with this

- [Hellmatch CS2](https://github.com/skink52/hellmatch-cs2): Doom-style deathmatch from Freedoom's levels, 4 arenas × 16 players, entirely in cs_script.
- [Space Racer](https://github.com/skink52/space-racer-cs2): 32-car anti-grav racer with eight generated tracks.
- [mg_trenchwarfare](https://github.com/skink52/trenchwarfare-cs2): WW1 trenches with procedural props, mortars, biplanes and custom rifles.
- [Puppet Brawl](https://github.com/skink52/cs2-fighter): 2.5D fighting game with mocap-based animation.
- The ported maps in [`ports/`](ports/README.md).
