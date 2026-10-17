# cs2portdocs

Tools, notes and history for porting **CS:GO maps to Counter-Strike 2** (mainly `mg_` minigame maps, plus jailbreak and a few `de_` maps), by **skink52**.

> **AI-generated code.** The scripts and most of the write-ups in this repo were produced by Claude, an AI agent, working with skink52 on these ports. They aren't hand-written code, so please don't read them as a showcase of anyone's own programming. They're shared because the porting knowledge in them is useful.

## What's here

| Folder | What it is |
|---|---|
| [`docs/`](docs) | How the port pipeline works, PC setup, house rules for ports, a list of CS2 gotchas (what broke going from CS:GO to CS2 and the fix), cs_script notes, and a dated changelog |
| [`tools/`](tools) | The **cs2port** pipeline (Python): decompile prep, Hammer-save fix, `.vmap` editing without Hammer, post-import fixes (lights, lasers, sky, vis, radar, scripts...) |
| [`scripts/`](scripts) | The PC-side batch / PowerShell runners (import, command-line build), the post-import cleanup and model import helpers, and a patcher that makes Valve's map importer run unattended |
| [`ports/`](ports) | One folder per ported map: status, workshop link, what was fixed, open issues, the cleanup log and the map's own cs_script files |
| [`legacy/`](legacy) | Small helper scripts from the early manual ports (alpha masks, model batch import, VTX checksum check, missing model/texture finders) |
| [`data/`](data) | `existing_ports.txt` (which maps have CS2 ports, by whom) and the pipeline queue files |

## Start here

- **Porting a map:** [docs/pipeline.md](docs/pipeline.md) (stages A–D and who does what) and [docs/conventions.md](docs/conventions.md) (naming, credits, lights, lasers, radar, vis).
- **Setting up a PC:** [docs/setup.md](docs/setup.md).
- **Something broke after porting:** [docs/cs2-gotchas.md](docs/cs2-gotchas.md).
- **Writing map logic in cs_script:** [docs/cs_script-notes.md](docs/cs_script-notes.md).
- **What happened when:** [CHANGELOG.md](CHANGELOG.md) and [ports/README.md](ports/README.md).

## What is *not* here

No map content: no BSPs, decompiled VMFs, `.vmap` files, or textures, models and sounds taken from the original maps. Those belong to the original mappers (each port credits them in its loading screen: "original map by &lt;author&gt; cs2 port by skink52"). Valve's own import scripts aren't copied either. [`scripts/make_import_map_auto.py`](scripts/make_import_map_auto.py) patches your local copy instead.

## Related

- [Hellmatch CS2](https://github.com/skink52/freedm-cs2) (repo first named freedm-cs2): a Freedoom deathmatch made entirely in cs_script.
- [space-racer-cs2](https://github.com/skink52/space-racer-cs2): a 2.5D anti-grav racer in cs_script.
