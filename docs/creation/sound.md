# Sound and music

Engine-side sound problems (loops, convar spam, silent `point_soundevent`s, fade-ins): [cs2-gotchas, Sound](../reference/cs2-gotchas.md#sound).
This page is how the original addons make, write and play their sounds.

## Files and events

- Source sounds go in `content\csgo_addons\<addon>\sounds\...` as 16-bit PCM `.wav` or `.mp3`; they compile to `.vsnd`. Events reference `sounds/<path>.vsnd`.
  Hellmatch converts 8-bit/stereo source WAVs to 16-bit mono 44.1 kHz (linear resample) before compiling; 3D sounds mono.
- Events live in `soundevents\soundevents_addon.vsndevts` (KV3 text). Keep the addon's own file and **merge** yours into it:
  `python3 create/merge_snd.py <template or live .vsndevts> <ours.vsndevts> --tag NAME [-o OUT]` writes your events between
  `// ---- NAME sound events (generated) ----` and `// ---- end NAME ----`, and on a re-run replaces only that block. It fails if one of your event names
  already exists outside the block. [`create/sndevents.py`](../../create/sndevents.py) writes the events (`event_3d`, `event_base`, `event_base_3d`,
  `event_music_flat`, `event_csgo_music`, `wrap`, `merge`). Use the `<X>_SOUNDEVENTS` switch to merge into the live file ([guide](guide.md#1-project-shape)).

### Event bodies that worked

**3D SFX** (`csgo_mega`, a distance curve). Points are `[distance, volume, 0, 0, 2.0, 3.0]`:

```
	"mymap.door_open" =
	{
		type = "csgo_mega"                // or base = "amb.base" (what the port pipeline writes for ambient_generic)
		volume = 1.00
		use_time_volume_mapping_curve = false
		vsnd_files_track_01 = "sounds/mymap/door_open.vsnd"
		distance_volume_mapping_curve =
		[
			[ 0.0, 1.0, 0.0, 0.0, 2.0, 3.0, ],
			[ 1250.0, 0.0, 0.0, 0.0, 2.0, 3.0, ],     // full volume at 0, silent at the radius
		]
	}
```

- Hellmatch: one base event `fdm.base` (`csgo_mega`, full volume 0–200 u, silent at 1400 u); each sound only sets `base = "fdm.base"` + `vsnd_files_track_01`.
- Space Racer / `sndevents.event_3d`: curve `(0, 1)`, `(0.2·r, 1)`, `(r, 0)`. mg_trenchwarfare: `(0, 1)`, `(0.15·r, 1)`, `(r, 0)`, ranges 3000–9000 for guns and shells.
- **Random variants:** `vsnd_files_track_01` as a list `[ "a.vsnd", "b.vsnd", ]`, plus `pitch_random_min/max` (mg_trenchwarfare's plane gun: stock
  `m249_01..03`, pitch 0.96–1.04). Stock CS2 sounds can be referenced directly.

**Music** (plays to everyone, no fall-off). Hellmatch's final form, `sndevents.event_csgo_music`:

```
	"mygame_music.track1" =
	{
		type = "csgo_music"
		volume = 0.7
		volume_convar = "snd_menumusic_volume"
		vsnd_files = "sounds/mygame/music/track1.vsnd"     // vsnd_files, not vsnd_files_track_01
	}
```

It follows the **Main Menu Music** slider (silent if that's at 0) and doesn't spam the console (why: [gotchas](../reference/cs2-gotchas.md#sound)). Music is per server,
not per player. The other modes Hellmatch kept as fallbacks: plain `csgo_music` (spams on some builds), and `csgo_mega` heard everywhere
(`sndevents.event_music_flat`: `occlusion_intensity = 0.0`, `distance_effect_mix = 0.0`, `restrict_source_reverb = true`, a flat volume curve to 100000 and
`use_distance_unfiltered_stereo_mapping_curve = true` with a flat `distance_unfiltered_stereo_mapping_curve`), which follows the effects volume instead.
Space Racer used the flat `csgo_mega` form.

### Soundscapes

mg_trenchwarfare's front-line ambience, all stock sounds, on an `env_soundscape` (`soundscape Nothing`, `enablesoundevent 1`, `soundevent tw.amb.front`) plus a
`point_soundevent` with `startOnSpawn 1`:
- Parent: `base = "amb.soundscapeParent.base"`, `enable_child_events = true`, `soundevent_01 = [ "tw.amb.wind", "tw.amb.guns", … ]`.
- Loop child: `base = "amb.looping.stereo.base"` (`sounds/ambient/anubis/wind_low_amb.vsnd`).
- Intermittent children: `base = "amb.intermittent.randomAroundPlayer.base"` with `randomize_position_min_radius` / `max_radius` and
  `retrigger_interval_min` / `max` (e.g. distant thunder as guns 2500–5000 u every 3–11 s; `crows_01..10` 800–2000 u every 14–40 s; `*_distant` rifle and MG
  sounds; `weapons/fx/nearmiss/bulletby_subsonic_01..05` at 60–300 u every 9–30 s).

## Playing sounds

- Map side: one `point_soundevent` per event (keys in [guide.md](guide.md#entity-recipes-the-generators-write): `stopOnNew 1` for music, `0` for SFX). `soundName` is the
  event name. Movers: one `point_soundevent` per door sound, fired from the door's outputs.
- Script: point a `point_soundevent` at a source entity with `SetSourceEntity` (value = an entity **name**, so name pooled props with `SetEntityName`), then
  `StartSound`. Several per source played round-robin for rapid fire (mg_trenchwarfare: 3 per plane gun).
- **Sounds at arbitrary points:** an anchor ring of pooled invisible null-model props (Hellmatch 24, Space Racer 16) teleported to the spot, then used as the
  source; cap sounds per tick (Hellmatch `MAX_SOUNDS_PER_TICK` 24).
- **Music sequencer** (Hellmatch `55_music.js`): one `point_soundevent` per track, track lengths baked into the script, a shuffled playlist per pool, the next
  track `MUSIC_GAP` 2 s after one ends, never the same track twice in a row, `StopSound` at round end, an opener track only on the first round. Players joining
  mid-track hear music from the next track. Loops restart from lengths in `_gen/music.json` (Space Racer), so the wav doesn't need loop markers for music.
- **Loops** that must loop in the engine need `smpl` + `cue` markers: `chiptune.write_wav(path, x, loop=True)` writes both.

## Making sounds without samples

Every original addon synthesises its audio (numpy/scipy, 44.1 kHz), so there's nothing to license and no YouTube claims on trailers.

- **Chiptune** ([`create/chiptune.py`](../../create/chiptune.py), from Space Racer): two pulse waves (12.5/25/50% duty) band-limited with **polyBLEP** so high
  notes don't alias into hiss, a 16-step triangle, shift-register noise (long/short), 4-bit stepped envelopes, pitch sweeps, a 22 kHz sample-and-hold
  "crunch"; a tiny tracker (`render_part`, `bars_of`) for note-list music; `mix()` adds **5 ms fades** at both ends so retriggers never click.
- **Rock/metal music** ([`create/synth.py`](../../create/synth.py), from Hellmatch): distorted guitar (detuned saw stack → 2× oversampled waveshaper → cab EQ,
  palm mutes), bass, lead with ping-pong delay, pad/choir/organ, a synthesised drum kit, risers; sidechain, convolution reverb from a synthesised impulse,
  bus compressor, soft-clip limiter. Events `(start_s, dur_s, pitch | [pitches], vel, flags)`. Hellmatch's arranger (`compose.py`, in its repo) builds songs
  from seeds; trailer music used Karplus-Strong guitar.
- **Reference matching** ([`create/music_analysis.py`](../../create/music_analysis.py) `<file> [--json]`): tempo, key, LUFS/true peak/LRA, band balance, spectral
  centroid, onset density, section boundaries of a reference track, to steer generated music and check the result.
- **Loudness standard:** every music track two-pass ffmpeg `loudnorm=I=-16:TP=-1.5:LRA=11`, then MP3 128 kb/s 44.1 kHz stereo.
- **MIDI music** (Hellmatch's FreeDM level music): libADLMIDI `adlmidiplay` with Nuked OPL3, bank 72 (DMXOPL3), 2 emulated chips so no notes drop, then
  the loudness pass. Credit the MIDI authors and the bank.
- **mg_trenchwarfare** (`tools/sounds.py` in its repo): synthesises the mortar launch thump, the falling whistle and a 9-cylinder rotary `plane_engine` loop;
  the mortar **impact** uses stock `hegrenade_detonate_02/03` + `c4_explode1`, and the launch layers a stock `c4_thump_01`.
- **Puppet Brawl**: 18 events, all stock CS2 sounds, layered per impact tier.
- **mg_deku_tree**: ambience and two music tracks through Hellmatch's synth.
