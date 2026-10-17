# tools: the cs2port pipeline

> **AI-generated code** (written by Claude for skink52's ports).

The full reference is [../docs/pipeline.md](../docs/pipeline.md). On the PC that same file is deployed as `C:\source1\cs2port\tools\README.md`.

| File | Stage | What it does |
|---|---|---|
| `prep.py` | A | BSPSource decompile, rename to the addon name, Hammer-save fix, asset zips, addon skeleton, sound name cleanup |
| `hammer_resave.py` | A | Makes a BSPSource VMF match what a CS:GO Hammer save produces (the manual flow needed that Hammer re-save before importing) |
| `ports.py` | A | `existing_ports.txt` duplicate check and addon-name cleaning (`mg_x_v2_final` → `mg_x`) |
| `setup_bspsrc.sh` | A | Unpacks BSPSource from its jlink image and back-patches it to run on Java 21 |
| `stage_c.py` | C | Prefab collapse + every post-import fix (see the pipeline doc), writes the cleanup log |
| `stage_d.py` | C/D | Re-runs single passes (`beams,lights,alpha,radar,daylight,skyvis`) on a map already edited in Hammer |
| `vmapedit.py`, `dmx.py`, `kv2.py` | lib | Read/write Hammer 5 `.vmap` (binary DMX 9 and keyvalues2 text) without Hammer |
| `vmf.py`, `vpk.py`, `vtf.py` | lib | VMF parser, VPK directory reader, VTF decoder |
| `lighting.py` | C | Static → Stationary lights per sealed compartment (max 4 overlapping) |
| `daylight.py` | C | Dark indoor maps: stationary sun, ceilings stop casting shadows, light probe volumes, exposure |
| `beams.py` + `laser_template.vmap` | C | env_laser / env_beam → never-solid func_brush beams with laser materials |
| `sky.py`, `box_template.vmap` | C | CS:GO six-face sky → equirect panorama; moondome boxes for dropped sky brushes |
| `skyvis.py` | C | Sky shells that a sealed room doesn't need → "Exclude from Vis" |
| `radar.py` | C | Minimap rendered from the floors, plus `resource/overviews/<map>.txt` |
| `assets.py` | C | Missing materials rebuilt from CS:GO's VPK (or swapped for stock CS2), alpha/translucency fixes, missing-model report |
| `gen_script.py` + `push_tail.js` | C | Generates `maps/scripts/<addon>_io.js` (trigger_push, point_servercommand, game_score, player_speedmod replacements) |
