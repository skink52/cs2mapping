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
both sides of the seam. 12 Nov 2026: **clean**, 31 files (all shipped since the wiring below; re-run the same day, the 28 older wavs
came out byte-identical).

| Loop | Length | Seam step / kink (x the file's p99.9 step; < 1 / < 1.5 passes) | Level across the seam |
|---|---|---|---|
| `plane_engine` | 2.0 s mono | 0.20 / 0.01 | +0.41 dB |
| `amb_wind` | 16 s stereo | 0.35 / 0.21 | +0.05 dB |
| `amb_barrage` | 20 s stereo | 0.24 / 0.20 | +0.84 dB |
| `rain_tin` | 12 s stereo | 0.15 / 0.17 | 0.00 dB |

## Events (all wired: the map or the script already plays them)

| Event | Played by | Files (`sounds/tw/`) | What |
|---|---|---|---|
| `tw.mortar_launch` | `tw_launch_snd_<tg>_K` (script, on firing) | `mortar_launch_1..2` | cartridge cough, tube ring, the bomb tearing away; 3D to 4500 u |
| `tw.mortar_whistle` | `tw_whistle_snd_1..12` (script, 2.0 s before the impact, 300 u over it) | `mortar_whistle_1..2` | 2.0 s falling whistle, loudest at the end; variant 2 tumbles |
| `tw.mortar_impact` | `tw_boom_snd_1..12` (impacts, cosmetic no man's land bursts, unlock blasts) | `mortar_impact_1..3` | HE in wet ground: crack, boom, clods and mud, rolling tail; 3D to 9000 u |
| `tw.plane_engine` | `tw_plane_eng_<tg>_N` (StartSound / StopSound, follows the aircraft) | `plane_engine` (loop) | 9-cylinder rotary at 1200 rpm: 90 Hz firing, 40 Hz prop beat, valve clatter, wind in the rigging |
| `tw.plane_gun` | `tw_plane_gun / gun2 / gun3_<tg>_N` (every 2nd round, rotating) | `plane_gun_1..3` | twin synchronised MGs: two rounds 90 ms apart, the guns 14-22 ms out of step |
| `tw.whistle_attack` | `tw_whistle_attack` (script, `CONFIG.LOBBY_RESPAWN` after each round start: as the briefing room empties) | `whistle_attack` | the company officer's whistle close by, over the top; flat (heard everywhere: csgo_mega, flat distance curve, unfiltered stereo), volume 0.6 |
| `tw.plane_dive` | `tw_plane_dive_1..4` (script pool, 60_air: lent to a diving aircraft) | `plane_dive` | 3 s: engine winding up, rigging wires howling, wind rush; 3D to 5000 u, volume 0.9 |
| `tw.amb.rain_tin` | `tw_rain_tin_<tg>_1..3` (map: the rain relay `tw_rain` OnUser1 / OnUser2) | `rain_tin` (stereo loop) | rain on the shelters' elephant iron; 3D to 600 u, volume 0.55, mixgroup Amb_Common |
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

## The three wired on 12 Nov 2026 (were pending)

Made in step 8 and held back (`out/step8/pending_sounds/`, the same bytes, kept for reference) until something played them. Now:
`tools/sounds.py` ships them (`ship=False` is gone for the three) and writes their events; `tools/patch_sounds.py` adds the emitters to
the map; the script starts two of them. Nothing is deployed: the wavs and the events file are staged in `out/addon` and listed in
`out/step8/deploy_files.txt`; the emitters are in `out/mg_trenchwarfare_sounds.vmap` (chain world_1 -> models -> terrain -> **sounds**
-> nav: run `patch_nav.py --in out/mg_trenchwarfare_sounds.vmap` next). On the deployed map the script finds no emitter and fires
nothing (the mock checks that with `sounds=0`).

| Sound | Wiring | Why this way |
|---|---|---|
| `whistle_attack` (2.6 s with its room tail) | one flat `point_soundevent` `tw_whistle_attack` beside `tw_ambience` in the briefing room; `75_front.js` `tickWhistle` starts it `CONFIG.LOBBY_RESPAWN` (1.5 s) after `OnRoundStart`, the moment everyone moves up from the briefing room | one entity; the script already owns the round clock. A `logic_eventlistener` in the map would need the event name and still one emitter. A tick check, not a delayed input from `OnRoundStart`, so it lands after the map's entities are re-created |
| `plane_dive` (3 s) | a pool `tw_plane_dive_1..4` (`CONFIG.AIR.DIVE.EMITTERS`); `60_air.js` `diveSound`: nose 25 deg below the horizon (`DIVE.PITCH`) at 900 u/s or more (`DIVE.SPEED`) takes a free emitter, `SetSourceEntity` to the aircraft then `StartSound` (0.05 s later, as the engine's emitter), busy for `DIVE.LEN` 3 s; re-armed once the nose is above -10 deg (`DIVE.REARM`) and 6 s (`DIVE.GAP`) have passed; `diveStop` on `endFlight` stops a dive still sounding (else it would follow the aircraft to its park) | cs_script has no call that plays a sound (`api.py sound`: none; `Entities.Spawn` is experimental and an event no map entity names may not be precached), so emitters must be in the map. 4 shared instead of 10 per-aircraft: a busy emitter is never taken over; all 4 busy = that dive is silent (`stats.divesSilent`; the mock's 32-player runs: 2 of 105, 64 players: 0 of 70) |
| `rain_tin` (12 s stereo loop) | `tw_rain_tin_<tg>_1..3` 88 u over each of the 6 dressing-station shelters (`models/tw/shelter`, the elephant iron, all inside the rain tiles); the rain relay `tw_rain` gets `OnUser1` -> `StartSound` and `OnUser2` -> `StopSound` for each | map-only: the rain is a map switch (`ent_fire tw_rain FireUser1 / FireUser2`, step 7), so the tin rings exactly while it rains and the script needs nothing. A round restart re-creates both off |

Checks (simulated): `patch_guard --strict` PASS (11 added, the relay's `conns`, the prefix entity counts); `check_contract.py --vmap
out/mg_trenchwarfare_sounds.vmap --stage out/addon` 86 / 86 (the emitters, their events staged, the relay wiring); the mock's coverage
row "sounds: attack whistle / plane dives" (fails on 0; the counts at the emitters must equal the script's own).

## Only CS2 can confirm

- That the flat `tw.whistle_attack` (a csgo_mega with a flat distance curve on a point_soundevent) is heard at full level everywhere,
  and that `tw.amb.rain_tin`, a stereo file on a 3D event, is placed at its emitter (if CS2 plays it unspatialised, the 600 u
  distance curve still limits it to the shelter). Whether a player who joins while it rains hears the loop (it starts on the relay).

- Levels against stock weapons (all files peak at -0.72 dBFS; event volumes 0.32-1.0) and whether the soundscape is too busy.
- That the 2 s loops loop seamlessly in the engine (markers are written as monsoon's, which compiled; neither has been heard in game).
- `pitch_random_*` on the gun and impacts, and that `tw.plane_engine` stops cleanly on StopSound.
