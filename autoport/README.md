# autoport: unattended CS:GO → CS2 ports on the PC

> **AI-generated code.** Written by Claude (an AI agent) for skink52's map ports, not hand-written.

Name the maps and come back to built addons. Maps with problems wait for Claude while the good ones build, and each one builds by itself once Claude marks it ready.
It runs entirely on the PC and calls the normal pipeline ([tools/](../tools/README.md), [docs/porting/pipeline.md](../docs/porting/pipeline.md), the PC batch files) without changing them.

## Run it

Close Hammer and CS2, then double-click `C:\source1\cs2port\autoport\run_autoport.bat`. Paste or type the maps, on one line or several, and press Enter on an empty line. You get a plan to confirm, and everything after that runs by itself.

Or give the maps directly, which skips the questions:

```bash
python C:\source1\cs2port\autoport\autoport.py ttt_island17 mg_antique_course --force
```

A map can be a name (the version suffix is optional), a path, a folder, a wildcard (`mg_*`), `@list.txt`, or `bspname=addon` to choose the addon name. Names are looked for in `bspsrc-windows\mg maps` and `bsp's`, including their subfolders.

| Option | Meaning |
|---|---|
| `--dry-run` | Show the plan and stop |
| `--from STEP` | Redo STEP and everything after it. Without it, finished steps are skipped |
| `--force` | Port maps already in `existing_ports.txt`; overwrite files that differ |
| `--no-build` | Stop before building. `autoport.py serve` builds them later |
| `--no-wait` | Build the good maps, then exit rather than wait for reviews |
| `--allow-missing` | Let maps with missing assets build. Errors, unknowns and I/O problems still hold them |
| `--vis-budget MIN` | How long vis may take before the build restarts with lean hints (default 20) |
| `--no-online` | Skip the Steam Workshop and GameBanana search |

Running it while a worker is active adds the maps to that worker's queue.

## What happens

1. **Launch:** finds each BSP and works out its type, then searches for existing ports (`existing_ports.txt`, Steam Workshop, GameBanana) and checks the PC is ready. Problems show here, before any work starts.
2. **Prepare, one map at a time:** `prep deliver import root stage_c fixups passes profile credit audit`.
3. **Sort:** a map with anything holding it back waits. The screen recommends getting Claude to look, with the prompt on your clipboard.
4. **Build:** good maps build now, one at a time. The worker stays open for the held ones and builds each as it is marked ready.

A failed step stops that map only. Nothing is committed or pushed.

## Map types

Set by the addon's prefix in [profiles.py](profiles.py). Every type also gets the normal pipeline.

| Type | Matches | Extra |
|---|---|---|
| TTT | `ttt_` | The full cs2mapTTT install: `ttt_convert`, map data baked into `ttt.js`, script and HUD copied in. It works on a copy in `cs2port\work\ttt_project`, so the repo doesn't change. Other people's ports don't count as duplicates, because they need dedicated servers and ours play from the map's script |
| Minigame course | `mg_*course*` | Checks the finish score survived (`game_score` → script `Score_n`); a course with no finish score is held. Respawning on until 5 s before the spawn AFK killer (`respawnwindow.py`) |
| Jailbreak | `jb_`, `ba_` | `iofix`, `visfit_detail`, and an I/O audit (`AddOutput`, `RunScript`, `sm_`, `logic_case`, `math_counter`, templates). Anything it finds holds the map |
| Minigame | other `mg_` | None |
| Standard | `de_`, `cs_`, `aim_`, `surf_` and similar | None |
| Unknown | anything else | None, and held so someone can say what it needs |

## Checks on every map

| When | Check | Fixes by itself |
|---|---|---|
| After import | `vmdlfix.py`: bodygroup choices cs_mdl_import left unnamed | Names them, so the models compile |
| Fixups | `propexplode.py`: props that used their model's explosion | Copies the CS:GO model's explosive_damage / radius onto them |
| Fixups | `respawnable.py` when the map has prop_physics_respawnable | prop_physics + point_template + env_entity_maker, respawning with no script |
| End of passes | `mapcheck.py`: Hammer's Check for Problems against CS2's `.fgd` files | Removes dangling outputs and classes CS2 doesn't need; converts trigger_waterydeath and func_wall; TurnOn/TurnOff → Enable/Disable on CS2 lights; lights the map switches → Stationary (Dynamic if parented), no bounce |
| End of passes | `zfight.py`: coplanar overlapping faces | Hides fully covered faces; moves the smaller of two partly overlapping materials 0.25 units forward |
| End of passes | `lightwall.py`: lights a few units off a wall | Moves them 24 units out |
| End of passes | `uvflip.py`: upside-down torch textures | Flips them |
| Audit | Entity classes that vanished with no known conversion, tool messages no rule knows | - |
| Before the build | Gibs for every addon model | Generic CS:GO chunks for Metal / Wooden / Glass props with none; imports missing gib models |
| After the build | Compile errors, unknown log lines, `unrecognized parent`, missing physics hulls; TTT script and HUD compiled | - |
| Last | Steam Workshop description | Writes `<addon> STEAM DESCRIPTION.txt` in the content addon folder (from `templates/`), with a Music list from `sounds/port_music/credits.txt` when `coursemusic.py` added songs; never overwrites a hand-edited one |

Water materials become `anubis/anubis_water_canal`.

## What gets noted

Everything found about a map goes to **`C:\source1\cs2port\logs\autoport\<date>.log`** and to **`logs\autoport\cleanup_list.md`**, the current list for every map not yet closed.

| Kind | Examples | Holds the build? |
|---|---|---|
| `error` | Failed step, crash, watchdog kill, bad BSP | Yes |
| `missing` | Failed models, textures with no source, lost outputs, compile errors, dropped displacements | Yes (`--allow-missing` lets them through) |
| `unknown` | Entity classes that vanished with no known conversion, tool messages or build errors no rule knows, an unknown map type | Yes |
| `io` | Lost finish score, jail audit findings, VScript, unconverted `game_ui` | Yes |
| `minor` | Decals not converted, silent door sounds | No |
| `review` | Author credit, loading screen images, recording the port | No |
| `playtest` | Pop-in, light brightness, physics props | No |

A build can also send a map back to held, if its logs show something new.

## Claude's feedback line

Full instructions for Claude are in [REVIEW.md](REVIEW.md). To start a session, paste the prompt autoport put on your clipboard.

```bash
python C:\source1\cs2port\autoport\autoport.py review list
```

```bash
python C:\source1\cs2port\autoport\autoport.py review ready ttt_x --note "restored the missing model"
```

For a change that doesn't need the full build, add a mode to a rebuild. Both mode builds start from the map's current `.vpk`, and use skink52's Hammer arguments:

```bash
python C:\source1\cs2port\autoport\autoport.py review redo ttt_x build --mode entities --note "explosions copied onto props"
```

| `--mode` | When | What it builds | Island17 took |
|---|---|---|---|
| `entities` | Only entities changed | `-entities` with lighting, no world, vis or nav | under 1 min (full: 10–15) |
| `lighting` | Textures or materials changed, no brush moved | `-world` with lighting, no vis or nav | - |
| `full` | Anything moved, the first build | Everything (the default) | - |

`build_maps.ps1` takes the same as queue prefixes (`entities <addon>`, `lighting <addon>`), and does a full build if there is no earlier `.vpk`.

`ready`, `accept`, `redo`, `hold`, `skip` and `close` all need a note, which goes in the log. If no worker is running, the command starts one in its own console, minimised and never activated, so it can't pull you out of a fullscreen game. Closing a window never strands a map.

Only the worker writes map state. Commands go through `work\autoport_state\inbox`, so a review can't collide with a running step.

## Hang protection and the live view

[watchdog.py](watchdog.py) wraps every long step. A process tree counts as active while it uses CPU, writes data, starts a process or changes its log.

| Trigger | Limit | Result |
|---|---|---|
| No activity | 10 min for most steps, 15 for import, 30 for builds | Killed, exit 124, noted as an error |
| Total time | 1–8 hours by step | Killed, exit 125, noted as an error |
| Vis phase in a build | `--vis-budget` | Killed, exit 127, rebuilt with `visfit_lean` |

[monitor.py](monitor.py) is the live window: each map's status and steps, what is running, CPU, disk, idle time against the limit, newest log lines and kills. It only reads, so closing it doesn't affect the run. `run_autoport.bat` opens it, or run `python C:\source1\cs2port\autoport\monitor.py`.

If CS2 or Hammer is open, autoport waits for it to close before editing or building a map, rather than failing.

## Polishing maps ported before autoport

`polish.py` brings an already-ported map up to today's rules without rerunning Stage C, so hand edits stay. It works on the content vmap,
backed up first, and builds nothing:

```bash
python C:\source1\cs2port\autoport\polish.py mg_antique_course mg_lego_course
```

It runs round setup (only the commands a map lacks), fires, respawning props, the entity check, z-fighting, model explosions, lights off walls,
upside-down torches and the bodygroup fix. Round setup also sets any other `sv_airaccelerate` the map's script sends to 2000 (content and
`ports/<addon>/scripts` copies), and on a prefab-split import whose main vmap has no entities it edits `prefabs/<map>/<map>_gameplay.vmap`.
`--only roundcfg` does just the round setup; `--all-ports` takes every `ports/<addon>`. The report,
`logs\autoport\polish_<time>.md`, lists what each map got and what is left for a person.

## Setup on a new PC

- Python 3 with numpy, scipy and Pillow.
- Copy this folder to `C:\source1\cs2port\autoport\`. The launch check warns if it, or `cs2port\tools`, differs from the repo.
- `C:\source1\cs2port\tools\addon_template\content` and `\game`, copied from `<CS2>\content\csgo_addons\addon_template` and `<CS2>\game\csgo_addons\addon_template`.
- A clone of this repo at `C:\source1\cs2mapping` for TTT maps (or set `CS2MAPPING`).
- The rest of [docs/porting/setup.md](../docs/porting/setup.md#one-time-pc-setup). BSPSource runs from its own image in `C:\source1\bspsrc-windows` through [bspsrc.bat](bspsrc.bat), so it needs neither Java 21 nor `setup_bspsrc.sh`.

## Files

| File | Job |
|---|---|
| `autoport.py` | The steps, the worker and the command line |
| `launch.py` | Map list, finding BSPs, duplicate search, PC checks, confirmation |
| `profiles.py` | Map types, their extra steps, how tool messages are sorted |
| `review.py` | The `review` commands |
| `common.py` | Paths, the dated log, map state |
| `watchdog.py`, `monitor.py` | Hang protection and the live window |
| `pclocal.py`, `bspsrc.bat`, `run_autoport.bat` | Copying files to the PC, BSPSource's command line, the double-click launcher |
| `REVIEW.md` | Instructions for Claude when reviewing a held map |
