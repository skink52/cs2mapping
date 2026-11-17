# Round 2: ambience, fidelity, fixes (started 18 Nov 2026)

AI-generated (Claude) for skink52. Follows the short front ([SHORT_FRONT_PLAN.md](SHORT_FRONT_PLAN.md), deployed + compiled 18 Nov
02:27, not yet played by Claude). The user's list, 18 Nov 2026 (their own playtest of the short-front build):

1. Improve ambience: sounds, fog etc.
2. Terrain textures: the grid squares where terrain has been manipulated are really obvious; make them natural.
3. Mine galleries: some parts make you crouch (clip squishing?); some supports cross into the path: delete those.
4. Improve visual fidelity overall.
5. Mortar sandbags: lower them a bit to allow sniping; they hover and don't look stacked like real ones.
6. Some trench models aren't solid; some are in weird places.
7. Forest models pop in and out (LOD changes visible).
8. Flight instruments: no wooden panel background, just the dials.
9. All in-game text reads as AI-written: make hints / cards AAA in language and tone.
10. Fog: there still isn't any. And optimise performance.

**Resuming after a usage reset or in a new chat:** read this table, the newest line of `out/short_front/round2_progress.md`, `git log
-5` in `C:\source1\cs2mapping`, then carry on with the first row not marked done. The map is regenerated, not hand-patched:
`python -u tools/deploy_tw.py --chain` (user save -> move_user_objects -> make_map_stage -> patch stages `--find` -> fog), then
the gate; `sh tools/short_front_stages.sh <stage>` runs stages by hand into `out/short_front/step5/chain/`. Check CS2 / Hammer are
not open on the addon before `--apply` (deploy_tw also checks). Long commands under the watchdog (see the user's CLAUDE.md).
The user authorised pushing this branch (18 Nov) and deploying when the gate passes.

| # | Item | Where | Done when | Status |
|---|---|---|---|---|
| A | Fog that shows (why is there none? env_cubemap_fog / volumetric settings in CS2, light_environment fog keys, post-process) | `tools/patch_fog_2.py`, `make_map.py` env block | a reason found (CS2 keys / known requirements) and values that render; TESTING L5 | done 18 Nov (code; not deployed): CS2 excludes volumetric fog -> env_gradient_fog tw_mist + cubemap height band to the ground |
| B | Ambience: soundscape richer and closer (distant artillery, MG, wind, mud, birds at the woods), soundscape per area (trench / NML / woods / galleries) | `tools/sounds.py`, soundscape in `make_map.py` | events + emitters, sounds checked | done 18 Nov (code): far artillery from recordings, closer shells / MG, woods + gallery soundscapes, crater smoke back |
| C | Galleries: find crouch-only stretches (roof vs player 72 u) and supports (tunnel_set) inside the walkway; delete those supports, raise the roof where needed | `make_map.py` tunnel section, check | check_play gallery headroom probe 0 low spots; 0 sets in the path | done 18 Nov (code): sets skipped where the cap < 77 u, in junctions, or with a post in another passage |
| D | Mortar pits: sandbag courses lower (one course less or lower z), bags bedded on each other (no hover), staggered like a real stack | `make_map.py` pits, `patch_world_3` W9 | clipping check: 0 floating bags; sightline crews still covered at crouch | done 18 Nov (code): wall + cap (~32 u), bedded on the lowest ground; W9 off |
| E | Trench props: non-solid ones (solid 0 / no hull) and odd places | `make_map.py` dressing, check_world overlaps | listed and fixed | done 18 Nov (code): hulls for 16 signs, gong, tool rack (add_hulls.py); petrol cans out of the hangar walls |
| F | Forest LOD pop: fade / LOD distances on tree models (`fademindist` / `fademaxdist`, LOD switch), fewer vista swaps near play | `make_map.py` woodland | no visible LOD swap inside ~3000 u of play | done 18 Nov (code): lodlevel 0 within ~900 u of play, 1 to ~1,400 u |
| G | Terrain grid: re-gridded / patched tiles show square seams (paint blend, normals, 16 vs 32 u grids) | `patch_terrain.py`, `make_map.py` terrain_paint | smooth blend across tiles; render checks | done 18 Nov (code): patched faces got FLAT normals (the squares): now smooth per-vertex normals from the final heights; forest paint ramp on the battle-zone edge |
| H | Flight HUD: dials only, no wooden dash plate | `tools/tw_hud.py`, `tw_cockpit.py` | hud_check green, picture looked at | done 18 Nov (hud_check green) |
| I | Text tone: every player-facing string (HUD cards, toasts, banners, chat, briefing) rewritten AAA-style: short, direct, in-world | `src/modules/*.js`, `tw_hud.py` baked text | all strings listed in a table before/after; mock green | done 18 Nov: 47 strings rewritten (roles RIFLEMAN / MORTAR CREW / PILOT, [KEY] prompts, no chatty dashes); mocks + 10 scenarios green |
| J | Visual fidelity pass + performance (draw distance, shadows, prop counts, particles, light count) | map, HUD | a perf budget written and met offline (counts) | done 18 Nov (code): no dynamic shadows from clutter / foliage / far trees, clutter fades past 3,200 u; fidelity via A, F, G |
| K | Chain, gate, deploy, compile | `deploy_tw.py` | gate PASS, compiled | done 18 Nov 05:18: gate PASS, deployed (backup deploy_20261118_050223), map 503 compiled / 0 failed, 0 DELETED, nav 3,798 |

**18 Nov 05:18: round 2 deployed and compiled. Level: compiled, not loaded in CS2.** Not done / notes: decorative ladders, wire and small
clutter stay non-solid on purpose; the gong and tool rack stay non-solid (a single convex hull blocked the bay spawns); check_play's
sightlines now show mortar crews visible over the lower breastwork (what the user asked for). In-game checks: docs/TESTING.md L5 (fog),
Q2-Q4 (sounds, soundscapes), V1-V6, and group W below.
