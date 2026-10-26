# Sound and music

## Files and events

- Source sounds go in `content\csgo_addons\<addon>\sounds\...` as `.wav` (16-bit PCM) or `.mp3`; they compile to `.vsnd`. Events reference `sounds/<path>.vsnd`.
- Events live in `soundevents\soundevents_addon.vsndevts` (KV3). Keep the addon template's file and **merge** your events into it
  (`create/merge_snd.py <template.vsndevts> <ours.vsndevts>`); generators replace only their own marked block on re-runs.
- A 3D event with a range (what the port pipeline writes for `ambient_generic`):

```
	"mymap.door_open" =
	{
		base = "amb.base"                 // "amb.looping.stereo.base" for 'play everywhere' loops
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

- Space Racer used `type = "csgo_mega"` events with explicit curves. **Music heard everywhere** (stereo, no fall-off, no occlusion): add
  `occlusion_intensity = 0.0`, `distance_effect_mix = 0.0`, `restrict_source_reverb = true`, a flat volume curve to 100000 and
  `use_distance_unfiltered_stereo_mapping_curve = true` with a flat `distance_unfiltered_stereo_mapping_curve`.
- `csgo_music` type events play to everyone with no fall-off. Set `volume_convar = "snd_menumusic_volume"` (verified): `snd_musicvolume` spams
  "Unable to acquire convar value" errors on servers. Music then follows the **Main Menu Music** slider and is silent if that's at 0. Music is per server, not per player.
- `amb.looping.stereo.base` fades in over 1 s; set `use_time_volume_mapping_curve = false` for sounds whose punch is at the start.
- A `point_soundevent`'s `soundName` must be the event name, not a `sounds/….vsnd` path (silent otherwise). Hammer caches failed sound loads: restart the tools.
- **Loops:** the wav needs loop markers. Write both a `smpl` loop and a `cue` point (the port pipeline adds a cue to looping wavs that lack one).
  The script restarts music loops itself when it knows their length.

## Playing sounds

- Map I/O: `point_soundevent` (`StartSound`/`StopSound`) or `ambient_generic` replacements. Movers: one `point_soundevent` per door sound, fired from the door's outputs.
- Script: a pool of `point_soundevent`s; point one at an entity with `SetSourceEntity`, then `StartSound`. Several per source played round-robin for rapid fire.
- Stock CS2 events can be reused by name (mg_trenchwarfare's plane guns use `m249_01..03` with pitch 0.96–1.04).

## Making sounds without samples

Every original addon synthesises its audio in Python (numpy/scipy, 44.1 kHz), so there's nothing to license:
- **Hellmatch** `tools/synth.py` + `compose.py`: distorted guitar (detuned saw stack → waveshaper → cabinet EQ, palm mutes), bass, leads with delay, pads/choir/organ, drums
  from sine sweeps and noise; deterministic tracks from seeds. `music_analysis.py` describes a reference track (tempo, key, loudness, spectrum, density)
  to steer the generated music. Trailer music used Karplus-Strong guitar.
- **Space Racer** `tools/sounds.py`: chiptune — two pulse waves (12.5/25/50% duty), a 16-step triangle, shift-register noise, 4-bit envelopes, 22 kHz sample-and-hold;
  music written as note lists.
- **mg_trenchwarfare** `tools/sounds.py`: mortar launch/whistle/impact synthesised and merged into the addon's events.
- **mg_deku_tree**: ambience and two music tracks through Hellmatch's synth.
- MIDI music can be rendered with libADLMIDI (Nuked OPL3 + DMXOPL3 bank) to MP3 (Hellmatch's FreeDM level music).
