# autoport: unattended CS:GO → CS2 ports on the PC

> **AI-generated code.** Written by Claude (an AI agent) for skink52's map ports, not hand-written.

Give it BSPs, come back to built addons and one cleanup list for agents. It runs entirely on the PC with no cloud workspace and no agent watching.
It calls the normal pipeline ([tools/](../tools/README.md), [docs/porting/pipeline.md](../docs/porting/pipeline.md), the PC batch files) without changing them.

## Run it

Close Hammer and CS2, then drop BSPs or a folder on `C:\source1\cs2port\autoport\run_autoport.bat`, or run:

```bash
python C:\source1\cs2port\autoport\autoport.py "C:\source1\bspsrc-windows\mg maps\ttt"
```

A monitor window opens with it. Results go to `C:\source1\cs2port\work\autoport_runs\<time>\`: `cleanup_list.md`, `cleanup_list.json`, step logs, `watchdog.jsonl` and a top-down preview of each map.

| Option | Meaning |
|---|---|
| `bspname=addon` | Choose an addon name instead of the cleaned BSP name |
| `--from STEP` | Redo STEP and everything after it. Without it, a restart skips finished steps |
| `--force` | Port maps already in `existing_ports.txt`; overwrite files that differ |
| `--no-build` | Stop before the build |
| `--wait-cs2 MIN` | How long to wait for CS2 / Hammer to close before skipping a build (default 30) |
| `--vis-budget MIN` | How long vis may take before the build restarts with lean hints (default 20) |

## What it does per map

| Step | What happens | Without a person |
|---|---|---|
| `prep` | Local duplicate check, then `prep.py` | Stops the map if it is in `existing_ports.txt`. The web check goes on the list |
| `deliver` | Copies the files to their PC paths, adds to `existing_ports.txt` | Refuses to overwrite differing files without `--force` |
| `import` | `run_import.bat` for this map only | `queue.txt` is swapped for the step and restored |
| `root` | Builds the stage C working root in `cs2port\work` | |
| `stage_c` | `stage_c.py`, rerun while it asks for CS:GO files | Copies them from `<CS2>\csgo`; always starts from the importer's vmap (`.vmap.imported`) |
| `fixups` | `disprestore` if displacements dropped, `laserhurt`, `glowfix`, `skysplit` | The skybox split is undone if it would move a player spawn |
| `passes` | `overlaydepth`, `probecover`, `gameui`, `origindup`, `water` when called for, then `visfit` | Falls back to `visfit_detail` when `visfit` finds under 0.1 billion cubic units of play space |
| `credit` | Writes the loading screen credit | The author goes on the list |
| `build` | `build_maps.ps1`, including the skybox map | Slow vis: restart with `visfit_lean`. Missing resources: `gibfix` + `run_fixrefs.bat`, then rebuild |
| `report` | Sorts everything left into the cleanup list | |

A failed step ends that map only; the run moves to the next one. Nothing is committed or pushed.

## Hang protection

[watchdog.py](watchdog.py) wraps every long step. It is a plain script, so it costs no tokens. A process tree counts as active while it uses CPU, writes data, starts a process or changes its log.

| Trigger | Limit | Result |
|---|---|---|
| No activity | 10 min for most steps, 15 for import, 30 for builds | Killed, exit 124, goes on the list as a blocker |
| Total time | 1–8 hours by step | Killed, exit 125, blocker |
| Vis phase in a build | `--vis-budget` | Killed, exit 127, rebuilt with `visfit_lean` |

It can also watch a batch file that is already running: `python watchdog.py --attach run_import.bat`. Only the stuck child is killed, so the batch file carries on.

[monitor.py](monitor.py) is the live window: steps per map, what is running, CPU, disk, idle time against the limit, newest log lines, watchdog kills. It only reads, so closing it doesn't affect the run. Open it by hand with `python C:\source1\cs2port\autoport\monitor.py`.

## The cleanup list

Three groups per map: **Blockers** (the map didn't finish or a tool failed), **Agent work** (fixable without the game) and **Playtest** (needs someone in the game).
An agent can be pointed straight at `cleanup_list.md`; it starts with its own instructions.

## Setup on a new PC

- Python 3 with numpy, scipy and Pillow.
- Copy this folder to `C:\source1\cs2port\autoport\`.
- `C:\source1\cs2port\tools\addon_template\content` and `\game`, copied from `<CS2>\content\csgo_addons\addon_template` and `<CS2>\game\csgo_addons\addon_template`.
- The rest of [docs/porting/setup.md](../docs/porting/setup.md#one-time-pc-setup). BSPSource runs from its own image in `C:\source1\bspsrc-windows` through [bspsrc.bat](bspsrc.bat), so it needs neither Java 21 nor `setup_bspsrc.sh`.
