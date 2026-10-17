# data

Snapshots of the pipeline's bookkeeping files from the PC (`C:\source1\cs2port\`). The PC copies are the live ones. Update these when they change.

- `existing_ports.txt`: every known CS2 port of the maps in the queue, and who made it. Tags: `[in progress]`, `[in progress, built]`,
  `[ported]` (published, Workshop link), `[*original*]` (not a port), `[ext. port]` (someone else's CS2 port, so don't port it), `[skink]` / `[briar]` (porter).
- `queue.txt`: the last stage B import queue (`addon [vmfname]` per line).
- `build_queue.txt`: the stage D build queue (`addon [mapname]`, or `assets addon` for an assets-only compile).
- `logs/stage_b_done.txt`, `logs/stage_d_done.txt`: one line per import / build run (OK or FAILED, build minutes).
