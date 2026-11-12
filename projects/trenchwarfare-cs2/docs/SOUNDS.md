# mg_trenchwarfare sounds

AI-generated (Claude) for skink52. Remaster step 8 (12 Nov 2026). Status: **simulated** (a numeric listen-check of the files; nothing
compiled or heard in CS2 yet). Overview of the presentation work: [PRESENTATION.md](PRESENTATION.md).

## Build

```
python tools/sounds.py out/addon "C:/source1/links/content_addons/mg_trenchwarfare/soundevents/soundevents_addon.vsndevts"   # 12 s
```
Everything is synthesised (numpy / scipy, 44.1 kHz 16-bit, no samples), with monsoon's method (`projects/monsoon-cs2/tools/sounds.py`):
loops are built from noise that is periodic over the file and whole numbers of cycles (events placed with wrap-around, reverb by
circular convolution), so they need no crossfade; loops carry `smpl` + `cue` markers. The template (the live addon file) is only read;
the result goes to `out/addon/soundevents/soundevents_addon.vsndevts`: our events in the block `// ---- mg_trenchwarfare sound events
(generated) ----` (written by `tools/sndevents.py`, libsync copy of `create/sndevents.py`), replacing the tw1-tw35 block that had its own
markers. Nothing else in the file changes (the template's `ambient_example.*` and `amb.*` base events stay).

## The check (`out/sounds_report.json`; exit 1 on any failure)

Every wav is read back from disk: peak (all -0.72 dBFS: no clipping), RMS, crest, DC (< 0.01), spectral centroid and band shares
against what the sound should be (the impacts must keep 40 % of their energy under 200 Hz and still be audible 2 s in, the whistles
must swell to the end, the barrage bed must sit under 250 Hz, the field whistles in 2-8 kHz...), a start / end step for one-shots (no
click on retrigger), and for loops the wrap step and slope kink against the file's own 99.9th-percentile sample step plus the level on
both sides of the seam. 12 Nov 2026: **clean**, 31 files.

| Loop | Length | Seam step / kink (x the file's p99.9 step; < 1 / < 1.5 passes) | Level across the seam |
|---|---|---|---|
| `plane_engine` | 2.0 s mono | 0.20 / 0.01 | +0.41 dB |
| `amb_wind` | 16 s stereo | 0.35 / 0.21 | +0.05 dB |
| `amb_barrage` | 20 s stereo | 0.24 / 0.20 | +0.84 dB |
| `rain_tin` (pending) | 12 s stereo | 0.15 / 0.17 | 0.00 dB |

## Events (all wired: the map or the script already plays them)

| Event | Played by | Files (`sounds/tw/`) | What |
|---|---|---|---|
| `tw.mortar_launch` | `tw_launch_snd_<tg>_K` (script, on firing) | `mortar_launch_1..2` | cartridge cough, tube ring, the bomb tearing away; 3D to 4500 u |
| `tw.mortar_whistle` | `tw_whistle_snd_1..12` (script, 2.0 s before the impact, 300 u over it) | `mortar_whistle_1..2` | 2.0 s falling whistle, loudest at the end; variant 2 tumbles |
| `tw.mortar_impact` | `tw_boom_snd_1..12` (impacts, cosmetic no man's land bursts, unlock blasts) | `mortar_impact_1..3` | HE in wet ground: crack, boom, clods and mud, rolling tail; 3D to 9000 u |
| `tw.plane_engine` | `tw_plane_eng_<tg>_N` (StartSound / StopSound, follows the aircraft) | `plane_engine` (loop) | 9-cylinder rotary at 1200 rpm: 90 Hz firing, 40 Hz prop beat, valve clatter, wind in the rigging |
| `tw.plane_gun` | `tw_plane_gun / gun2 / gun3_<tg>_N` (every 2nd round, rotating) | `plane_gun_1..3` | twin synchronised MGs: two rounds 90 ms apart, the guns 14-22 ms out of step |
| `tw.ambient_blast` | nothing in the current map (kept for older wiring) | the impact files | |
| `tw.amb.front` | the map's `env_soundscape` | soundscape parent | children below |
| `tw.amb.wind` | soundscape | `amb_wind` (stereo loop) | broad wind, slow gusts, barbed wire singing in the gusts |
| `tw.amb.barrage` | soundscape (**new child**) | `amb_barrage` (stereo loop) | drumfire beyond the horizon: low rumble, thuds rolling into each other |
| `tw.amb.guns` | soundscape | `amb_guns_1..4` | heavy guns a few km back, 1-4 reports with valley echoes (was stock thunder) |
| `tw.amb.shells` | soundscape | `amb_shell_1..3` | shells bursting down the line, one heard coming in (was stock HE) |
| `tw.amb.mg` | soundscape | `amb_mg_1..3` | a Maxim / Vickers far off, 8 rounds a second (was stock m249 / negev) |
| `tw.amb.whistles` | soundscape (**new child**) | `amb_whistle_1..3` | officers' pea whistles somewhere along the line (another company going over), rare |
| `tw.amb.planes` | soundscape (**new child**) | `amb_plane_1..2` | an aircraft passing a few hundred metres off (doppler from the engine loop) |
| `tw.amb.crows`, `tw.amb.rifles`, `tw.amb.whiz` | soundscape | stock (game pak01) | unchanged |

New children only needed the soundscape parent the map already plays, so they need no map or script change.

## Waiting for wiring (made and checked, NOT shipped: `out/step8/pending_sounds/`)

| Sound | Needs | Suggested event |
|---|---|---|
| `whistle_attack.wav` (1.8 s, the company whistle close by) | a round-start hook: the script (90_main round start) firing `StartSound` at a new flat `point_soundevent` `tw_whistle_attack`, or a `logic_eventlistener` in the map | `tw.whistle_attack`, flat csgo_mega (heard everywhere), volume ~0.6 |
| `plane_dive.wav` (3 s: engine winding up, rigging wires howling) | the script (60_air) starting it on a `tw_plane_dive_<tg>_N` point_soundevent when the nose goes down past ~25 deg at speed, with a re-trigger guard | `tw.plane_dive`, 3D 5000 |
| `rain_tin.wav` (12 s stereo loop: rain on elephant iron) | weather in the map (step 7's fxkit rain, if it lands) and an `amb.looping.atXYZ` point_soundevent inside each shelter | `tw.amb.rain_tin`, at XYZ, ~600 u |

## Only CS2 can confirm

- Levels against stock weapons (all files peak at -0.72 dBFS; event volumes 0.32-1.0) and whether the soundscape is too busy.
- That the 2 s loops loop seamlessly in the engine (markers are written as monsoon's, which compiled; neither has been heard in game).
- `pitch_random_*` on the gun and impacts, and that `tw.plane_engine` stops cleanly on StopSound.
