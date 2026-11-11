# mg_monsoon presentation: HUD, sounds, radar, board, skybox, loading screen

AI-generated (Claude) for skink52. Status: **simulated** (layout check, mock engine, numeric sound check, mesh check).
Nothing here has been compiled or seen in CS2 yet; the things that most need an in-game look are listed at the end.

## Regenerate

From `tools/` (order matters: the HUD preloads the slides and uses the board picture):

```
python sounds.py ../out/addon "C:/source1/links/content_addons/addon_template/soundevents/soundevents_addon.vsndevts"   # 8 s
python make_radar.py ../out/addon ../out/game      # ~2.5 min after layout.py changes (terrain raster, cached in out/cache), else 1 min
python render_board.py ../out/addon                # board picture, 3 loading slides, map icon (~2 min)
python make_sky.py                                 # out/sky_template.vmap -> out/addon/maps/mg_monsoon_3dskybox.vmap, check_mesh (1 min)
python mv_hud.py ../out/addon                      # art + xml + css + out/hud.json + the hud_check gate (1 min; --no-art: 5 s)
```

`MV_RADAR_STALE=1` reuses the last terrain raster while iterating on looks (never for a final run).
`mv_hud.py` exits 1 if the layout breaks the HUD contract, names a picture that does not exist, or fails `hud_check.py`.
The gate by hand: `python hud_check.py --addon ../out/addon --name mg_monsoon --states ../out/hud_states.json --out ../out/hud/hud`.
Then `node tools/build_script.mjs && node test/mock.mjs 32 300` (the mock reads the xml / css and `out/hud.json`).

Outputs: `out/addon/panorama/{layout,styles}/custom_game/mg_monsoon.*`, `panorama/images/custom_game/mv/*.png` (100 pictures),
`panorama/images/overheadmaps/mg_monsoon_radar_psd.png + .vtex`, `panorama/images/map_icons/...`, `sounds/mv/*.wav`,
`soundevents/soundevents_addon.vsndevts`, `maps/mg_monsoon_3dskybox.vmap`, `out/game/resource/overviews/mg_monsoon.txt` (game side),
and the reports `out/hud.json`, `out/hud_states.json`, `out/hud/*.png`, `out/sounds_report.json`, `out/radar_region.json`,
`out/board.json`, `out/sky.json`, `out/slides/*_cs2.png`.

## HUD

103 panel ids, exactly the table in [SCRIPT.md](SCRIPT.md#hud-contract) (ids, classes, swap groups, step counts); static art has no
id. `out/hud.json` carries `board_steps` 160, `board_ext` 6400 (what the script reads), the step counts of every swap group and the id list.
Look: dark olive glass plates with a cream keyline and corner ticks (the same plates as the loading slides), Stratum2 for live
text, baked Bahnschrift stencil lettering for titles, green phosphor for instruments, amber for the player's own things,
sand = PAVN (T), blue = US (CT).

| Panel | Where (1080 high) | What |
|---|---|---|
| `mv_obj` | top centre, y 72, 560 wide (inside W/2 +-280, under CS2's team counter) | tickets + bars, five flag badges, clock. Each `mv_flag_x` is a transparent 560 x 204 panel holding its badge in the bar and a **capture ring** under the bar that shows only with `here` (letter, 10-step arc in the capturing team's colour, flag name, CONTESTED tag) |
| `mv_brief` | centre, y 216, 640 x 372 | briefing card: role, 3 lines, deploy point strip, countdown line |
| `mv_info` | right, y 236, 380 x 330 | role / help card |
| `mv_banner` | centre, y 300 | title + subtitle between two amber rules |
| `mv_hold` / `mv_prompt` / `mv_toast` | centre, y 562 / 612 / 680 | hold-USE bar (21 steps), `[E]` prompt, toast (SPLASH and the like) |
| `mv_status` | left, y 336 (under CS2's radar, clear of the chat) | role + 3 lines. SCRIPT.md's hint says bottom left; that is CS2's chat box, so it sits under the radar as mg_trenchwarfare's did |
| `mv_gun` | right, y 888 | gun name, 10-segment heat bar, OVERHEAT overlay with `hot` |
| `mv_fly` | full screen container | heading tape top centre (y 190), info line y 758, dash bottom centre (716 x 200 at y 792: airframe bar, RTB lamp, rocket counter, airspeed, horizon, radar altimeter, vertical speed), crew list right (y 600). `seat_gunner` / `seat_rider` hide airspeed, vertical speed and the rocket counter |
| `mv_board` | centre + 70 px, y 120, 900 x 772 | 640 px map (4 px per reticle step), state lamps STANDBY / LAYING / LAID / DISABLED, gun, shell, range, grid, legend, controls, footer with next action, mission and stats |

How the moving parts work (all class-driven transforms or picture swaps, no class-driven sizes or margins):
- **Bars** (tickets, hold, heat, airframe): a fixed clipping track with a full-length fill picture inside, slid by `translatex`.
- **Flag capture fill**: the same, vertically, inside the badge; owner and capturing team swap pictures.
- **Needles**: `.Rot.a0..a71` = `rotateZ(N x 5deg)`. Airspeed 0 at the top, 100 km/h at 300 degrees (CONFIG.HUDCFG.ASI_MAX_KMH); altimeter one
  turn per 100 m; the vertical-speed needle picture points to 9 o'clock at `a0`, so clockwise = climb and `a45..a71` = sinking.
- **Horizon**: square clipping window > `mv_ai_roll` (rotates, no clip) > `mv_ai_pitch` (`translatey`, 6.8 px per step = 2 degrees,
  `pit10` level, `pit20` = nose up = horizon down) > the card at a fixed `scale3d(2.6)`. The bezel picture carries the dash's own
  pixels outside its ring, so the square window's corners never show.
- **Heading tape**: a 1164 px tape in a 300 px flow-right clipping window, `h0..h71` = `translatex(-N x 12px)`; heading 0 under the caret at `h0`.
- **Board markers**: `.MCol.x0..x159` / `.MSq.y0..y159`, every marker a 64 px square with its art centred; `mv_cep` is a child of
  `mv_locky` and swaps one of nine ring pictures (radius (N + 1) x 3 px = 60 world units each). `sel` swaps the mission / flash picture.
- Blinks (`bleed`, `contest`, RTB, OVERHEAT) are one quoted `@keyframes "mvblink"`; the HUD reads the same without it.

States drawn by the gate (`out/hud_states.json` -> `out/hud/hud_<state>.png`, also at 2333 and 1440 wide): `lobby`, `infantry`,
`capture`, `contested`, `fly_pilot`, `fly_gunner`, `mounted_hot`, `board`. `hud_check.py` does not model clipping, rotation or
scale: in its pictures bar fills and the tape hang out of their windows and needles do not turn. `out/hud/fly_preview*.png`
(drawn by `mv_hud.py`) is the instrument cluster as Panorama should show it.

Not in the HUD because the contract has no id for it: a gunner ammo count (heat only), and a per-team board picture.
`render_board.py` writes `board_t.png` / `board_ct.png` (enemy base at the top) but the layout uses the north-up `board.png`,
because the contract positions markers north-up for both teams. Using them needs a class on `mv_board` and mirrored steps in the script.

## Sounds (`tools/sounds.py`)

41 wavs, all synthesised (numpy / scipy, 44.1 kHz 16-bit), 21 events in the `mg_monsoon` block of `soundevents_addon.vsndevts`.

| Event | Kind | Files |
|---|---|---|
| `mv.heli_rotor` | 3D loop, 9000 | 2 s, 22 blade slaps (11 Hz), whole cycles, smpl + cue |
| `mv.heli_turbine` | 3D loop, 3500 | 2 s whine + gearbox + exhaust |
| `mv.heli_gun`, `mv.mount_gun` | 3D, 8000 / 7500, random pitch | 3 variants each |
| `mv.rocket_launch`, `mv.rocket_fly` | 3D, 7000 / 4500 | 2 variants; fly is a 4 s one-shot that fades (not a loop) |
| `mv.howitzer_fire`, `mv.rocket_fire` | 3D, **14000** | 2 variants each, 4.7 s with valley echoes |
| `mv.shell_whistle` | 3D, 4200 | 2.0 s, loudest at the end: start it 2 s before the impact |
| `mv.shell_impact` | 3D, 11000 | 3 variants, 4.5 s |
| `mv.capture`, `mv.flag_lost`, `mv.radio_blip` | flat `csgo_mega` (same volume everywhere, everyone hears it) | horn call / falling horns / radio key-up |
| `mv.amb.valley` | soundscape parent | children `mv.amb.cicadas` + `mv.amb.river` (stereo loops), `mv.amb.birds` (6), `mv.amb.gecko`, `mv.amb.frogs` (3), `mv.amb.thunder` (3), `mv.amb.guns` (4), random around the player |

The numeric listen-check (`out/sounds_report.json`, exit 1 on a failure) reads every wav back from disk: peak (-0.72 dBFS for all),
RMS, crest, DC, spectral centroid and band shares against what the sound should be (the howitzer must keep half its energy
under 200 Hz and still be audible 2 s in, the whistle must swell, cicadas must sit above 3 kHz...), a start / end step for
one-shots, and for loops the wrap step and slope kink against the file's own 99.9th percentile sample step (all four loops < 1).
The loops are built from noise that is periodic over the file and whole numbers of cycles, so there is no crossfade.

## Radar, board, slides, skybox

- **Radar**: 1024 px, the square x, y in [-6400, 6400] (`pos_x -6400`, `pos_y 6400`, `scale 12.50`), the valley sides outside the
  play space dimmed. Drawn from `layout.py` only: hill shade, river / paddies / marsh, roads, a crown per tree from the jungle
  mask, karst towers with long shadows, bases, bridge, flags A-E with capture radius, and the 16 x 16 grid `!pos` reports.
  Village huts are stand-ins (the real footprints live in `mv_places.py`).
- **Board**: the same square as a printed 1:25 000 map, `out/board.json` = `{ext 6400, steps 160, px 640}`.
- **Slides**: `mg_monsoon.png` (title + roles), `_1` (five flags), `_2` (fire mission), content inside CS2's safe area
  (`out/slides/*_cs2.png` show CS2's column and the 4:3 / 21:9 cuts). Icon: a helicopter, `map_icon_mg_monsoon.svg`.
- **Skybox**: `make_skybox.build` in plain mode on a copy of the mg_trenchwarfare skybox map (its `tw_sky` ring dropped, its
  sky_camera kept, its light_environment / env_sky set to the main map's sun and sky). 64 terrain sheets from the terrain
  edge (7168 x 6144) out to 30720, all-green Ancient blend, 2212 trees (Aztec banyans near, small banyans and Dust skybox palms
  further, none on the far ridge), 33 karst towers on the horizon. `check_mesh.py`: 97 meshes, 0 bad.

## To look at in CS2 first

1. Compile the layout and css with `resourcecompiler` and check for "compiled" (a failed layout is ignored silently).
2. The horizon (rotation + `scale3d` + nested no-clip panels inside a clipping window) and the heading tape (a flow-right child
   wider than its parent): the two constructions with no earlier in-game example in this repo.
3. `overflow: clip` on the bar tracks and the board map; `@keyframes "mvblink"`.
4. Banyans at 1/16 scale in the skybox (no vista LOD exists for them: watch the frame time looking at the valley sides).
5. Sound levels against stock weapons, and whether the flat stingers are too loud for players far from the action.
