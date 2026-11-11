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
Since `out/hud.json` lists the additions, the plain mock run fails: `test/mock.mjs` throws on any addition id unless `hudnew=1`
(its HUDNEW flag ignores the baked `HUDDATA.ids`), the script's HUD gives up after 20 throws, and the objective / flight checks fail.
`node test/mock.mjs 32 300 hudnew=1` passes (12 Nov 2026). The mock needs HUDNEW set when the baked ids already hold every addition.

Outputs: `out/addon/panorama/{layout,styles}/custom_game/mg_monsoon.*`, `panorama/images/custom_game/mv/*.png` (304 pictures, most of them bar / tape / horizon frames),
`panorama/images/overheadmaps/mg_monsoon_radar_psd.png + .vtex`, `panorama/images/map_icons/...`, `sounds/mv/*.wav`,
`soundevents/soundevents_addon.vsndevts`, `maps/mg_monsoon_3dskybox.vmap`, `out/game/resource/overviews/mg_monsoon.txt` (game side),
and the reports `out/hud.json`, `out/hud_states.json`, `out/hud/*.png`, `out/sounds_report.json`, `out/radar_region.json`,
`out/board.json`, `out/sky.json`, `out/slides/*_cs2.png`.

## HUD

107 panel ids: the table in [SCRIPT.md](SCRIPT.md#hud-contract) plus its "HUD additions (pass 1)" table (`mv_feed_1..3`, `mv_gun_ammo`);
`mv_hud.py` reads both and fails on a missing id or a class with no css rule. Static art has no id. `out/hud.json` carries `board_steps`
160, `board_ext` 6400 (what the script reads), the step counts of every swap group and the id list `ids`: the script's `hudHas()`
switches the feed and the belt read-out on because the additions are in it.
Look: dark olive glass plates with a cream keyline and corner ticks (the same plates as the loading slides), Stratum2 for live
text, baked Bahnschrift stencil lettering for titles, green phosphor for instruments, amber for the player's own things,
sand = PAVN (T), blue = US (CT).

| Panel | Where (1080 high) | What |
|---|---|---|
| `mv_obj` | top centre, y 72, 560 wide (inside W/2 +-280, under CS2's team counter) | tickets + bars, five flag badges, the clock on its own tab under the bar (y 142-166, clear of the badges and the `here` caret). Each `mv_flag_x` is a transparent 560 x 224 panel holding its badge in the bar and a **capture ring** under the tab (y 176) that shows only with `here` (letter, 10-step arc in the capturing team's colour, flag name, CONTESTED tag) |
| `mv_feed_1..3` | right 24, y 198 / 226 / 254, 460 x 26 (under CS2's kill feed, which ends ~y 190) | event feed, newest on top: right-aligned 18 px Label on a dark band that fades out to the left, a 4 px tone tick at the right end; `feed_good` green, `feed_bad` red-orange, none = cream |
| `mv_brief` | centre, y 216, 640 x 372 | briefing card: role, 3 lines, deploy point strip, countdown line |
| `mv_info` | right 20, y 290, 360 x 330 | role / help card, under the feed; 360 wide so it clears the briefing card on 4:3 (1440: brief 400-1040, card 1060-1420) |
| `mv_banner` | centre, y 300 | title + subtitle between two amber rules |
| `mv_hold` / `mv_prompt` / `mv_toast` | centre, y 556 / 612 / 680 | hold-USE bar (21 steps; ends y 598, above the 4:3 chat box), `[E]` prompt, toast (SPLASH and the like) |
| `mv_status` | left, y 336, 360 x 136 (under CS2's radar, clear of the chat) | role (20 px, fits "INFANTRY  /  MACHINE GUNNER") + 3 lines. SCRIPT.md's hint says bottom left; that is CS2's chat box, so it sits under the radar as mg_trenchwarfare's did |
| `mv_gun` | right, y 880, 300 x 104 | gun name, belt read-out `mv_gun_ammo` ("BELT 87" / "RELOADING 3 s") under it, 10-segment heat bar; `hot` shows a red wash and an OVERHEAT tag beside the belt line (drawn under the text) |
| `mv_fly` | full screen container | heading tape top centre (y 190), info line y 758, dash bottom centre (716 x 200 at y 792: airframe bar, RTB lamp, rocket counter, airspeed, horizon, radar altimeter, vertical speed), crew list right (y 640). `seat_gunner` / `seat_rider` hide airspeed, vertical speed and the rocket counter; their wells then show a riveted NOT FITTED cover plate instead of an empty hole |
| `mv_board` | centre + 70 px, y 196, 900 x 772 | under the objective bar and its clock tab, and below CS2's kill feed at every width. 640 px map (4 px per reticle step), state lamps STANDBY / LAYING / LAID / DISABLED, gun, shell, range, grid, legend, controls, footer with next action, mission and stats |

How the moving parts work (picture swaps and rotations only, no class-driven sizes or margins). Since HUD pass 2 nothing relies on
`overflow: clip`, a child wider than its parent or `scale3d` except the board map's marker clip: every stepped read-out is one picture
per step, so the panel never leaves its box and `hud_check.py` draws exactly what Panorama should.
- **Bars** (tickets `tk_t_N` / `tk_ct_N`, hold `hold_N`, heat `heat_N`, airframe `hp_N`): one picture per step, the full bar cut to N / steps
  of its width (`frames()`); T's ticket bar is lit from the left, CT's from the right, so both drain towards the flags. Unset = full bar (empty for hold / heat).
- **Flag capture fill**: `flagcap_<t|ct>_N`, the badge filling from the bottom, picked by `.Flag.capt_x.capN`; owner ring by `own_x`.
- **Needles**: `.Rot.a0..a71` = `rotateZ(N x 5deg)`. Airspeed 0 at the top, 100 km/h at 300 degrees (CONFIG.HUDCFG.ASI_MAX_KMH); altimeter one
  turn per 100 m; the vertical-speed needle picture points to 9 o'clock at `a0`, so clockwise = climb and `a45..a71` = sinking.
- **Horizon**: `mv_ai_roll` (`rotateZ`) holds `mv_ai_pitch`, which swaps 21 round pictures `ai_0..ai_20` (horizon 6.8 px per step = 2 degrees,
  `pit10` level, `pit20` = nose up = horizon down; pitch ladder every 5 degrees, numbered at 10 / 20), and the bank pointer. The pictures are
  discs, transparent outside the window, so the roll never shows a corner; the bezel (fixed bank scale and aircraft symbol) sits on top.
- **Heading tape**: `mv_hdg` is the 300 x 36 window itself and swaps 72 window pictures `tape_0..tape_71` (heading N x 5 under the caret).
- **Board markers**: `.MCol.x0..x159` / `.MSq.y0..y159`, every marker a 64 px square with its art centred; `mv_cep` is a child of
  `mv_locky` and swaps one of nine ring pictures (radius (N + 1) x 3 px = 60 world units each). `sel` swaps the mission / flash picture.
- Blinks (`bleed`, `contest`, RTB, OVERHEAT) are one quoted `@keyframes "mvblink"`; the HUD reads the same without it.

States drawn by the gate (`out/hud_states.json` -> `out/hud/hud_<state>.png`, also at 2333 and 1440 wide): `lobby`, `infantry`,
`capture`, `contested`, `fly_pilot`, `fly_gunner`, `mounted_hot`, `board` (the feed and belt lines appear in `lobby`, `infantry`,
`fly_gunner`, `mounted_hot`). `hud_check.py` does not rotate, so needles and the horizon's roll stand still in its pictures;
`out/hud/fly_preview.png`, `fly_preview_2.png` (pilot) and `fly_preview_gunner.png` (drawn by `mv_hud.py`) are the instrument cluster
with the rotations applied. Pass 1's pictures are kept in `out/hud/before/` for comparison.

Checked at 1920 and 2333 (the gate, clean) and at 1440 (4:3, `--check-widths 1440,1920,2333`): at 4:3 only CS2's chat box *while someone
types* (x 0-576, y 600-1010) is left, under the prompt, the toast, the dash and the board: the centre column there is x 576-1010 (434 px),
narrower than those panels, so they stay where they are. Also looked at over a bright-sky / dark-jungle picture (plates and the feed band
keep every text readable).

Not in the HUD: a per-team board picture. `render_board.py` writes `board_t.png` / `board_ct.png` (enemy base at the top) but the layout
uses the north-up `board.png`, because the contract positions markers north-up for both teams. Using them needs a class on `mv_board`
and mirrored steps in the script.

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
2. The horizon's roll: a rotated panel whose picture is a disc (mg_trenchwarfare's dials rotate the same way); `padding-right` on the
   feed Labels (`hud_check.py` ignores padding, so in its pictures the text touches the tone tick).
3. `overflow: clip` on the board map (markers at the edge); `@keyframes "mvblink"`.
4. Banyans at 1/16 scale in the skybox (no vista LOD exists for them: watch the frame time looking at the valley sides).
5. Sound levels against stock weapons, and whether the flat stingers are too loud for players far from the action.
