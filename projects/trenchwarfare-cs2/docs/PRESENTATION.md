# mg_trenchwarfare presentation: HUD, sounds, radar, plotting board, loading screen, skybox

AI-generated (Claude) for skink52. Remaster step 8 (12 Nov 2026). Status: **simulated** (layout check, mock engine, numeric sound
check, radar alignment check). Nothing here has been compiled or seen in CS2 yet. Details: [HUD.md](HUD.md) (HUD contract and layout),
[SOUNDS.md](SOUNDS.md). Not deployed: the files are staged in `out/addon` / `out/game`, the list is `out/step8/deploy_files.txt`.

## Regenerate (from `tools/`, in this order)

```
python -u make_radar.py --vmap ../out/mg_trenchwarfare_models.vmap --addon ../out/addon --game ../out/game   # ~1.5 min (watchdog); final chained map later
python render_sight.py ../out/addon        # plotting-board maps target_t/ct.png (6 s; reads out/radar_clean.png)
python render_slides.py ../out/addon       # 3 loading slides + map icon (5 s; reads out/radar_clean.png and target_ct.png)
python tw_hud.py ../out/addon              # HUD art + xml + css + out/hud.json + the hud_check gate (9 s)
python sounds.py ../out/addon "C:/source1/links/content_addons/mg_trenchwarfare/soundevents/soundevents_addon.vsndevts"   # 12 s
cd .. && python tools/check_radar.py       # alignment (5 s)
```
Then the script gate in [SCRIPT.md](SCRIPT.md) (the mock reads the staged xml / css). Shared tools are libsync copies of `create/`
(`hud_check.py`, `panorama.py`, `loading.py`, `sndevents.py`, `merge_snd.py`; added 12 Nov 2026 with `libsync add` + `push trenchwarfare-cs2`).

## What exists and how it is made

| Piece | Tool | Output | Check |
|---|---|---|---|
| HUD layout | `tw_hud.py` (+ `tw_cockpit.py` dials) | xml, css (547 rules, 32 KB), 26 pictures in `panorama/images/custom_game/tw/` | contract table in HUD.md vs layout / css / `src/modules`; `hud_check.py`: 6 states at 1920 and 2333, pictures also at 1440: **0 problems** |
| Plotting-board maps | `render_sight.py` | `target_t.png`, `target_ct.png` (1024 px, shown 640) | `out/step8/sight_check.png`: all 10 pits drawn through `worldToSight` sit on the printed pit rings (looked at) |
| Radar | `make_radar.py` | `mg_trenchwarfare_radar_psd.png` + `.vtex` (1024 px, BC7), game `resource/overviews/mg_trenchwarfare.txt` | `check_radar.py`: **clean** |
| Loading screen | `render_slides.py` via `loading.py` | `map_icons/screenshots/1080p/mg_trenchwarfare.png`, `_1`, `_2`; `map_icon_mg_trenchwarfare.svg` | `out/step8/slides/*_cs2.png` (CS2's column, 4:3 / 21:9 cuts drawn; content inside the safe area, looked at); `--css-check` (the HUD css preloads all three and the icon) |
| Sounds | `sounds.py` | 31 wavs + the events block (whistle_attack, plane_dive, rain_tin wired by `patch_sounds.py` + 60_air/75_front) | numeric listen-check: **clean** (SOUNDS.md) |

**HUD look.** Dark olive canvas plates with a brass keyline, corner brackets and rivets for the live cards (status, orders card,
headline banner); feathered dark bands for the prompt and toast; the briefing room's orders as a printed FIELD MESSAGE form with an
ORDERS stamp; the mortar sight as a wooden plotting board with a printed trench map (own works blue, the enemy's red, as British trench
maps printed them) and a ledger card (fire order read-outs, a marker key, the controls); the cockpit as five 128 px brass-bezelled
dials in a walnut dash with a leather roll, the rounds counter and bomb lamps on a side plate. Live text in fonts CS2 ships
(Stratum2, Noto Serif, Noto Mono); fixed titles and help baked into the pictures. Every plate picture is drawn at its shown size.
The old green "digital" sight (anachronistic) is gone; `render_top.py` no longer writes it.

**Script (HUD only, 12 Nov 2026).** `40_hud.js` `headline()`: an area unlock is now a banner headline ("THE WAY TO THE WOOD IS OPEN" /
"Ladder at the north end of the fire trench") instead of a 7 s toast another toast could overwrite; the streak reward is a MARKSMAN
headline; the briefing room now shows toasts (role-command answers were never shown there) and headlines; the status card hides while
the plotting board is up (the ledger carries the same lines; on 4:3 the board covered it); two toasts shortened to one line. No new
HUD id; no gameplay change. Kill feed: CS2's own (the script draws none). Bot / AI roles: the script shows none beyond the hand-over
toast ("A bot pilot handed his aircraft over to you"), so the HUD adds none.

**Radar.** Same region and conventions as before (pos -4300 / 4700, scale 8.40 per pixel of a 1024 picture = `CONFIG.RADAR` =
`out/radar_region.json`), rebuilt from `out/mg_trenchwarfare_models.vmap` (step 6 map) with Windows fonts and larger grid letters and
road names. `check_radar.py`: (1) the four copies of the constants agree; (2) the script's own `radarSquare()` (run in node from the
built script) names the printed square for all 56 named points (40 posts, 10 pits, 6 dressing stations); (3) on the unlabelled 4096 px
master, CS2's dot for each point lands on its drawn feature: posts on a trench floor, pits on the tube, stations on the red cross,
largest gap **0 u**. Validated on a known-bad case: an overview shifted 120 u fails 42 checks. Picture: `out/step8/radar_alignment.png`.
Re-run `make_radar.py --vmap <final chained map>` after steps 5-7 are chained (props: wire, wrecks, trees), then `check_radar.py`.

**Skybox: assessed, not regenerated.** The 3D skybox (`maps/mg_trenchwarfare_3dskybox.vmap`, the user's file, read only) was filled by
`make_skybox.py` from `layout.ground_low` at the map edge; nothing in step 8 changes that edge. Regenerate it only if step 7's terrain
patch moves the ground at the map edge (then: `make_skybox.py <copy of the skybox vmap> out/<new> --layout layout --plain`, check_mesh,
and the user decides). The 2D sky is the stock `env_sky`; a custom overcast cubemap would need a sky material and a cube vtex: not
cheap, not done.

## Files (staged; `out/step8/deploy_files.txt` is the copy list)

Content: `panorama/layout|styles/custom_game/mg_trenchwarfare.xml|css`, `panorama/images/custom_game/tw/*.png` (26),
`panorama/images/overheadmaps/mg_trenchwarfare_radar_psd.png|vtex`, the 3 slides and the icon, `sounds/tw/*.wav` (28),
`soundevents/soundevents_addon.vsndevts`, `maps/scripts/mg_trenchwarfare.js`. Game: `resource/overviews/mg_trenchwarfare.txt`.
Reports: `out/hud.json`, `out/target_map.json`, `out/sounds_report.json`, `out/step8/` (hud pictures and states, sight_check, slides,
radar_alignment.png / .json, pending_sounds).

## Only CS2 can confirm

1. Force-compile the xml, css and js (`resourcecompiler -f -i`) and look for "compiled": a broken layout is ignored silently.
2. The fonts: `"Noto Serif"` and `"Noto Mono"` by family name (CS2's fonts.conf registers notoserif / notomono; the gate drew them with
   those very files); Labels with long text wrap inside their fixed boxes (the gate draws one clipped line: the orders card foot and
   `tw_t_state` are the two that may wrap).
3. The dials turn (`rotateZ` classes; `hud_check.py` does not rotate) and the read-out windows on the compass and altimeter stay legible.
4. The radar dot against `!pos` in a few places (the convention itself is the cs2port one), and the loading slides and icon showing
   (preloaded by the HUD css).
5. Sound levels against stock weapons, loop seams in the engine, the soundscape's density (SOUNDS.md).
