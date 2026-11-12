# mg_trenchwarfare (CS2): WW1 trench battle

> **AI-generated code.** Everything here (map generator and patches, procedural props and textures, HUD, sounds and the cs_script) was
> written by an AI agent (Claude) for skink52's mg_trenchwarfare addon: AI-written code directed by skink52.

A Counter-Strike 2 addon set on the Western Front in WW1. Two trench lines face each other across no man's land: German infantry (T)
on one side, British (CT) on the other. Behind each line are mortar pits, and each side has an aerodrome on its flank. The wood to the
north and the mine galleries under the south end are blown open during the round. Up to 64 players. Script bots fill a quiet server.
Everything runs in the map's own `point_script`; the server needs no plugins.

**Status (12 Nov 2026): remaster, simulated, not yet tested in CS2.** The remaster brings the addon up to the mg_monsoon standard
([docs/REMASTER_PLAN.md](docs/REMASTER_PLAN.md), steps 1-10). Each part has reached this level:
- **Script, bots, HUD, sounds:** simulated (mock engine, type check, `api.py --strict`, layout and sound checks).
- **Map patches:** simulated (guarded delta patches on a copy of skink52's map, `check_world` / `check_play`).
- **Delivery:** a deploy **dry run** against the real addon folders. Nothing of the remaster has been deployed, compiled,
  Hammer verified or played.
- **Earlier builds:** the tw34 build (29 Oct) was compiled and played by skink52. The open in-game questions are the checklist in
  [docs/TESTING.md](docs/TESTING.md).
- **Workshop:** not publishable yet. Three weapon models have licence problems ([docs/WORKSHOP_COMPLIANCE.md](docs/WORKSHOP_COMPLIANCE.md)).
- **Resume from:** [NOTES.md](NOTES.md) "Resume here".

## Roles

| Role | Chat | What you do |
|---|---|---|
| Infantry | `!infantry` / `!rifle` | Hold the fire trench. T: Gewehr 98 + Luger; CT: Lee-Enfield + Colt M1911. 3 kills without dying earns the Mondragón (T) or the Lewis gun (CT); SHIFT+E / `!swap` switches back. Dressing stations heal. |
| Mortar crew | `!mortar` / `!artillery` | 5 crews of two per side. The plotter uses the map table (E, WASD to move the marker, MOUSE1 lock, SPACE fire). The loader fetches a bomb from the ammo box (E) and loads it. Shells fall with spread and flight time. The loader's share of a hit counts as an assist. |
| Pilot | `!air` / `!pilot` | 5 aircraft per side (CT SPAD VII biplane, T Fokker Dr.I triplane). Mouse steers, W/S throttle, A/D roll, MOUSE1 guns, MOUSE2 bombs (2, re-armed after 18 s). Chase camera, brass cockpit dials. 2 lives per posting, then back to the ground. |

## How to play

- Everyone spawns in the briefing room, gets an orders sheet and is sent to their post: 4 s on the first spawn, 1.5 s after each
  respawn. Respawn is on; rounds last 60 minutes.
- Roles are drawn for you; a chat command sets your preference. In the briefing room the change is immediate; in the field it applies
  at your next deploy.
- **The wood** opens after 15 enemy kills or 4 minutes. **The mine galleries** open after 30 kills or 8 minutes. Each opening comes
  with a blast and a headline.
- Chat commands (type them exactly, with `!`):

| Command | Does |
|---|---|
| `!infantry` `!rifle` · `!mortar` `!artillery` · `!air` `!pilot` | role preference |
| `!random` | let the script pick your role |
| `!roles` | role card: your side's crews and aircraft |
| `!swap` (or SHIFT+E) | streak weapon / rifle |
| `!pos` | your position and radar square (quote it in reports) |
| `!uniform` | period uniform on / off (applied in the briefing room) |

Server operators: rain is off by default. `ent_fire tw_rain FireUser1` starts it and `FireUser2` stops it. The console prints
`[tw] perf: ...` once a minute with the script's time per tick.

## Bots

`CONFIG.BOTS_ON` is true by default: `bot_quota_mode fill`, `bot_quota 16`. Bots fill the server to 16 players and leave as people join.
- Infantry bots are placed at fire-trench and support-trench posts, and later in the opened areas. A leash brings back bots that
  wander into no man's land, the briefing room, or far from any post.
- A side with fewer than 4 active humans also gets 1 AI pilot and 2 AI mortar crews. A human who asks for that role takes the
  aircraft or seat at his next deploy.
- Bots on depend on the patched map's nav. NONAV markup and the woods seed fix cut the estimate from 44,160 to about 1,470 areas.
  On the old compile, set `BOTS_ON: false`.
- Details: [docs/SCRIPT.md](docs/SCRIPT.md), [docs/REVIEW_SCRIPT_1.md](docs/REVIEW_SCRIPT_1.md#step-4-bots-12-nov-2026-remaster-step-4).

## Build and test

Needs Python 3 with numpy, scipy and Pillow, and Node 18+. Run from this folder unless marked. Anything over about 2 minutes runs
under `C:\source1\cs2port\autoport\watchdog.py` ([docs/BUILD.md](docs/BUILD.md)).

| Step | Command |
|---|---|
| restage `out/` from the map + addon | `python tools/restage_out.py` (8 s) |
| script build (never edit `src/mg_trenchwarfare.js`) | `node ../../create/build_script.mjs src/build.json` |
| script gate | repo root: `python create/test/api.py --strict --check projects/trenchwarfare-cs2/src/mg_trenchwarfare.js`, `sh create/test/tscheck.sh projects/trenchwarfare-cs2/src/mg_trenchwarfare.js` |
| mock | `node test/mock.mjs 32 300`, `node test/mock.mjs 16 300 fill=1 humans=4`, `node test/mock.mjs 32 150 scenario=all` |
| perf, balance | `node test/mock.mjs 64 300 humans=6 perf=1,8`; `node ../../create/sim_balance.mjs test/balance.json 50 32` (watchdog) |
| names | `python tools/check_contract.py [--vmap <map> --stage out/addon]` |
| world checks | `python tools/check_world.py <map> --stage out/addon`, `python tools/check_play.py <map> --stage out/addon` |
| HUD, sounds, radar | `python tools/tw_hud.py out/addon`, `python tools/sounds.py out/addon <template vsndevts>`, `python tools/check_radar.py` ([docs/PRESENTATION.md](docs/PRESENTATION.md)) |
| chain + gate + deploy dry run | `python -u tools/deploy_tw.py --chain` (about 10 min, watchdog); `python -u tools/deploy_tw.py` (merge + gate + dry run) |
| deploy | `python -u tools/deploy_tw.py --apply` (Hammer and `cs2 -tools` closed; copies changed files only, backs up first) |
| compile | `build_maps.ps1 assets mg_trenchwarfare`, forced xml / css / js, `build_maps.ps1 final mg_trenchwarfare` ([docs/BUILD.md](docs/BUILD.md)) |

The map is never regenerated. Every change is a guarded delta patch on skink52's own vmap: `tools/patch_*.py` + `tools/patch_guard.py
--strict`, chained by `deploy_tw.py`. The original generator (`tools/make_map.py`, `render_top.py`, `build_all_props.py`) built tw1-tw35.
Do not rerun it on the user's map. Layout constants live in `tools/layout.py`.

## Documents

| Doc | What |
|---|---|
| [NOTES.md](NOTES.md) | session log, "Resume here" |
| [docs/REMASTER_PLAN.md](docs/REMASTER_PLAN.md), [docs/REMASTER_PROMPT.md](docs/REMASTER_PROMPT.md) | the remaster: steps, decisions, rules |
| [docs/CONTRACT.md](docs/CONTRACT.md) | every name the map, script, HUD and tests share |
| [docs/SCRIPT.md](docs/SCRIPT.md) | script modules, CONFIG guide, tests and gate |
| [docs/HUD.md](docs/HUD.md), [docs/SOUNDS.md](docs/SOUNDS.md), [docs/PRESENTATION.md](docs/PRESENTATION.md) | HUD contract and layout, sounds, radar / board / loading slides |
| [docs/ASSETS.md](docs/ASSETS.md), [docs/WORKSHOP_COMPLIANCE.md](docs/WORKSHOP_COMPLIANCE.md) | every model, its source and licence; what blocks a Workshop upload |
| [docs/BUILD.md](docs/BUILD.md), [docs/BUILD_LOG_1.md](docs/BUILD_LOG_1.md) | chain, deploy, compile; the first remaster build's log |
| [docs/REVIEW_WORLD_1.md](docs/REVIEW_WORLD_1.md), [docs/REVIEW_SCRIPT_1.md](docs/REVIEW_SCRIPT_1.md) | review pass 1: world findings and patches, script bugs and bots (pass 2: `docs/REVIEW_*_2.md`) |
| [docs/TESTING.md](docs/TESTING.md) | the in-game checklist: everything only CS2 can confirm |
| [docs/WORKSHOP.md](docs/WORKSHOP.md) | Workshop page text, tags, credits, pre-upload checklist |
| [docs/weapons_handover.md](docs/weapons_handover.md), [docs/tripo_prompts.md](docs/tripo_prompts.md), [docs/research/](docs/research/) | weapon builder notes, soldier model prompts, remaster research |

## Licence

Free for non-commercial use: copy, change, share and run it, including on game servers (donation/VIP servers are fine). Not to be sold, paywalled or built into a paid product or service. Code: [PolyForm Noncommercial 1.0.0](LICENSE). Art, models, sounds and maps: [CC BY-NC 4.0](LICENSE-CC-BY-NC-4.0.txt). See [LICENSE](LICENSE) for third-party parts that keep their own terms (the CC BY models and the weapon models listed in the addon's `CREDITS.txt`).

## Shared files

`test/point_script.d.ts` and these toolkit copies in `tools/` are master copies from [cs2mapping](https://github.com/skink52/cs2mapping)
(`create/libsync.json`): `bake.py`, `build_all_props.py`, `build_prop.py`, `check_mesh.py`, `clean_stale.py`, `dmx.py`, `dmx9.py`,
`dump_entities.py`, `ext_smd.py`, `fx_models.py`, `geo.py`, `glb2cs2_multi.py`, `hud_check.py`, `loading.py`, `lod_decimate.py`,
`make_skybox.py`, `merge_snd.py`, `modelio.py`, `noise.py`, `p_sandbag.py`, `panorama.py`, `placer.py`, `render.py`, `shaders.py`,
`sndevents.py`, `stock.py`, `vmaplib.py`, `vmesh.py`, `vpkdir.py`, `vtexread.py`, `weld_cracks.py`. Change them there and run
`python create/libsync.py push`; if a fix lands here first, `libsync.py pull` it into cs2mapping. `libsync.py check` shows drift.

`sync_repo.sh` (working folder → this checkout) never deletes, copies only newer changed files, and never touches README.md, NOTES.md,
the licences or the shared files above: edit those in the checkout.
