# Reviewing held maps (for Claude)

Autoport holds a map back from the build when it finds anything missing, wrong or unknown. The other maps keep building. Your job: sort out each held map, then tell the pipeline, which builds it without anyone else doing anything.

## How to work

```bash
python C:\source1\cs2port\autoport\autoport.py review list
```

```bash
python C:\source1\cs2port\autoport\autoport.py review show <addon>
```

`show` gives every item and the files behind it. Today's log is `C:\source1\cs2port\logs\autoport\<date>.log`, and each run's step logs and map previews are in `C:\source1\cs2port\work\autoport_runs\<time>\`.

1. Read the repo's `CLAUDE.md` and `docs/porting/pipeline.md`.
2. For each held item, fix it or decide it doesn't matter. Hammer and CS2 must be closed, and back up a `.vmap` before editing it.
3. Tools run from `C:\source1\cs2port\tools` with root `C:\source1\cs2port\work`, where `content\<addon>` is a junction to the real addon. Never delete through it. Most tools write to `work\out\<addon>`; copy that back with `python C:\source1\cs2port\autoport\pclocal.py apply <addon>`.
4. Tell the pipeline. The note is required and goes in the log, so say what you did:

| Command | Use it when |
|---|---|
| `review ready <addon> --note "..."` | Sorted: clears the held items and builds the map |
| `review accept <addon> --note "..."` | Already built and fine as it is: clears them with no rebuild |
| `review redo <addon> <step> --note "..."` | A tool or an input changed: reruns from that step, then checks the map again |
| `review hold <addon> --note "..."` | Stops a map building until someone clears it |
| `review skip <addon> --note "..."` | Not worth porting: tell the user why |
| `review close <addon> --note "..."` | Finished and recorded: drops it off the list |

A command starts a worker if none is running. A build that fails or logs something new puts the map back in the held list, so check `review list` again later. The user decides anything that is a judgment call on the map's design, or that would change what the map plays like.

## What the holds mean

| Kind | Meaning | Usual start |
|---|---|---|
| `error` | A step failed or crashed, or the watchdog killed it | The named log, then `review redo` |
| `missing` | Models, textures, lost outputs or displacements | `WHY MISSING` in `maps\<addon>_cleanup_report.txt`, `maps\<addon>_dropped_io.txt` |
| `unknown` | No rule knows it: a vanished entity class, a new tool message, a new build error | Find out what it did. If it is harmless, add it to `profiles.py` so it never holds a map again |
| `io` | Map logic that probably doesn't work as it stands | The VMF's outputs against the vmap's |

## What past ports needed

- **Courses:** the finish score. `game_score` doesn't exist in CS2, so stage C makes it script `Score_n`. A course with none needs its finish found by hand.
- **Jail maps** (`ports/ba_jail_keimusho` is the fullest record): double doors whose trigger lost the output to the second leaf. `movedir` with two numbers dropping movers at compile. `logic_case` values needing `1.000000` because math_counter sends a float string. Triggers enabled with players inside, which CS2 doesn't re-check. `sm_cvar` outputs. Scripts re-hooking entities every round.
- **TTT:** `projects/cs2mapTTT/docs/MAP_REQUIREMENTS.md`. Map data kept in the repo means copying `work\ttt_project\maps\<addon>.json` to `projects/cs2mapTTT/maps/` and running `tools/build_data.py`.
- **Any map:** record what you find per the repo's rules: `ports/<addon>/README.md`, the gotchas and a `CHANGELOG.md` line.
