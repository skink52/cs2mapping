# IRONFRAME: audio and particle effects

Everything here is made by two generators and nothing is sampled from outside the household:

- `python -I tools/sounds.py out/addon [--soundevents <live vsndevts>] [--no-music] [--only a,b]` synthesises every sound
  (numpy/scipy + `create/chiptune.py` + `create/synth.py`), writes `sounds/ifr/*.wav`, the sound events
  (`soundevents/soundevents_addon.vsndevts`, merged with `create/sndevents.py` under the tag `IRONFRAME`; `--soundevents`
  merges into and rewrites the live addon file), the baked table `_gen/sounds.json` (`SOUNDS` in `build.json`), and the
  preview sheet `preview/audio/` (contact sheet, spectrograms, a loudness table).
- `python -I tools/particles.py out/addon` writes the text particle sources `particles/ifr/ifr_*.vpcf` (adapted from the
  Dogfight particles in `C:\source2\projects\dogfight`) and the pool/effect table `_gen/fx_particles.json`.

Both run in about two minutes (the music is most of it) and are deterministic (seeded).

## 1. Conventions the adapter and the map generator share (`_gen/sounds.json`)

```
{ "events": { "<key>": { "event": "ifr.<key>", "entity": "ifr_snd_<key>", "range": <silent u>, "full": <full-volume u>,
                         "loop": bool, "ui": bool, "stop_on_new": bool, "seconds": s, "variants": n, "files": [...],
                         "volume": v, "mixgroup": "...", "category": "...", "per_slot": 64?, "ring": N?, "note": "..." } },
  "music": { "music_garage": {...}, "music_battle": {...} }, "pilot_tones": [...], "loops_to_stop": [...] }
```

- **One-shot positional events** (`loop` false, `ui` false): one `point_soundevent` named `ifr_snd_<key>` with `stopOnNew 0`
  (`stop_on_new` false). The adapter `SetSourceEntity`s it onto a pooled anchor prop (or the mech's upper-body prop) and
  `StartSound`s; several may overlap.
- **`per_slot: 64`** (`boost_loop`, `hover_loop`): the map places `ifr_snd_<key>_00..63`, one per mech slot; the adapter
  sources `_NN` on that slot's upper-body prop, `StartSound` when the boost begins and `StopSound` when it ends (`stop_on_new` true).
  `hover_loop` is marked optional: drop it if the entity budget is tight.
- **`ring: N`** (`gatling_loop` 16, `msl_loop` 24, `repair_loop` 8): `ifr_snd_<key>_00..N-1`, handed out round-robin and
  `StopSound`ed when the source dies.
- **`ui: true`**: not placed in the world (`ifr.ui.base`: `use_world_position false`, mixgroup UI, no distance effect). Play with
  `StartSoundOnSingleClient` for pilot-only tones; `ui_round_start` / `ui_podium` may be sent to everyone the same way.
- Start and Stop of the same event must not land in the same tick (entity I/O is queued; Dogfight `FX_EM` rule).
- Music: `csgo_music` events with `volume_convar snd_menumusic_volume` (follows the Main Menu Music slider, per server), each a
  `point_soundevent` `ifr_snd_music_<x>` with `stopOnNew 1`; the WAVs loop on their smpl/cue markers and `seconds` is baked so
  the script can restart a loop if a player joined mid-track.

Every file is 44.1 kHz 16-bit PCM, mono (music stereo), peak -1 dBFS; loops have smpl + cue chunks written by
`chiptune.write_wav(loop=True)`. Event `volume` is the category's base volume trimmed by the file's RMS toward the category
target (within -8..+4 dB, UI -5..+2 dB) so a category sounds even in game; the per-file numbers are in `preview/audio/README.md`.

### 3D ranges (full volume to `full`, silent at `range`, `csgo_mega`, pitch jitter +-4 % unless a loop)

| category | full / silent u | base vol | mixgroup | RMS target | used for |
|---|---|---|---|---|---|
| weapon_light | 600 / 3500 | 0.85 | Weapons | -15 | rifle, smg, gatling |
| weapon_medium | 900 / 4500 | 0.90 | Weapons | -14 | shotgun, laser, grenade, blade, plasma, handmsl, autocannon, flak |
| weapon_heavy | 1200 / 6000 | 1.00 | Weapons | -13 | bazooka, rail, vm6, vm12, dualmsl, lasercannon, grenadecannon |
| booster | 1200 / 4000 | 0.55 | World | -20 | boost / hover / missile loops, boost_on, qb |
| explosion | 2000 / 9000 | 1.00 | Explosions | -12 | boom_small, boom_large, mech_death, flak_burst |
| impact | 400 / 2500 | 0.80 | World | -16 | hit_metal, hit_ground, blade_clash, grenade_bounce, stagger_clang |
| foley | 300 / 1800 | 0.70 | World | -18 | landings, footsteps |
| ability | 500 / 3000 | 0.80 | World | -16 | shield, pulseshield, repair, decoy |
| world | 2000 / 9000 | 1.00 | World | -13 | drop_entry, capture, wave_start, boss_roar, bounty |
| ui | flat | 0.60 | UI | -16 | the pilot tones and the round/garage sounds |

## 2. Every sound (key = `ifr.<key>` = `ifr_snd_<key>`)

Weapon keys are the `parts.json` part keys, so the adapter can play `PARTS[w].key` directly. Variants are random
(`vsnd_files_track_01` list). Source: synthesised in `tools/sounds.py` unless noted.

### Boosters and movement

| key | entity | s | loop | what it is |
|---|---|---|---|---|
| boost_loop | ifr_snd_boost_loop_00..63 | 2.95 | yes | neutral medium thruster bed: band-passed roar + 96 Hz drone + whine, crossfaded seamless. Stop when the boost ends |
| boost_loop_light / boost_loop_heavy | single | 2.95 | yes | optional class beds (light: hiss + 1.2 kHz whine; heavy: 44 Hz sub + rumble); not placed per slot |
| boost_on_light / _medium / _heavy | single | 0.7 | | ignition punch: thump 180/140/110 -> 60/45/32 Hz, swept noise, spark hiss |
| qb | single | 0.62 | | quick boost: rising then falling band-swept whoosh + 260 -> 1100 Hz tone |
| hover_loop | ifr_snd_hover_loop_00..63 | 2.3 | yes | hover bed: 260-1500 Hz noise with 14 Hz flutter + 58 Hz hum (optional) |
| land_light / land_heavy | single | 0.9 / 1.25 | | landing thud + plate clank + servo; heavy has a 95 -> 30 Hz sub |
| step_light / step_medium / step_heavy | single | 0.45 | | stomp (sub + crunch + servo whine) for gait clips later |

### Weapons

| key | s | var | what it is |
|---|---|---|---|
| rifle | 0.68 | 3 | AR-22 crack: click, 5 kHz burst, 400 -> 95 Hz body, action cycle at 70 ms |
| smg | 0.46 | 3 | SMG-Hornet snap, brighter and shorter |
| gatling | 0.09 | 1 | one GT-9 round (for single ticks); hold uses the ring |
| gatling_loop (ring 16) | 0.40 | loop | exactly 10 rounds at 25/s + 175 Hz barrel motor; Stop on release, then gatling_down |
| gatling_down | 1.4 | 1 | barrel whine 175 -> 30 Hz + slowing clicks |
| shotgun | 1.2 | 1 | SG-Scatter: 3 kHz burst, 260 -> 48 Hz body, 120 -> 38 Hz sub, pump at 0.38/0.47 s |
| laser | 0.45 | 1 | LR-Lumen zap: FM sweep 2.6 kHz -> 260 Hz + hiss |
| laser_charge | 1.2 | 1 | rising 220 -> 1800 Hz tone with accelerating tremolo + noise (the 1.2 s charge) |
| bazooka | 1.7 | 1 | BZ-Hammer: 90 -> 28 Hz thump, 1.4 kHz burst, rocket whoosh, room |
| grenade | 0.7 | 1 | GL-Lob thunk: 700 Hz noise + hollow-pipe resonance |
| grenade_bounce | 0.3 | 1 | metallic clink (impact category) |
| blade | 0.55 | 1 | PB-Moonlight swing: band-swept whoosh + 110 Hz electric hum |
| blade_clash | 1.1 | 1 | blade hit: inharmonic plate ring + FM zap (impact category) |
| plasma | 0.5 | 1 | PR-Ion pulse: FM 190 -> 120 Hz blob + sizzle + 40 Hz wobble |
| rail | 1.8 | 1 | RG-Lance crack: 3.2 kHz -> 180 Hz sweep, 110 -> 36 Hz thump, long room tail |
| rail_charge | 0.5 | 1 | wind-up 400 -> 2600 Hz + rising noise (the 0.5 s wind-up) |
| handmsl | 1.03 | 1 | HM-4: four launch pops 0.11 s apart with whooshes |
| msl_loop (ring 24) | 1.55 | loop | rocket motor: 350-3000 Hz noise with 31 Hz flutter + 95 Hz |
| shield / shield_down | 0.5 | 1 | arm shield raised (180 -> 420 Hz harmonic hum) / lowered |
| vm6 / vm12 | 1.2 / 1.64 | 1 | 6 / 12 launch pops at 0.1 / 0.085 s |
| dualmsl | 1.0 | 1 | two heavy launches 0.3 s apart |
| lasercannon | 1.9 | 1 | LC-Solar beam: crack, 220/440 Hz sustained hum 0.6 s, sizzle, sub |
| lasercannon_charge | 1.25 | 1 | 55 -> 440 Hz saw drone + harmonics + noise, cut at the end (fires) |
| grenadecannon | 2.5 | 1 | GC-Thunder: 110 -> 32 Hz boom with rumble and room |
| autocannon | 0.9 | 3 | AC-Drum thud: 2.6 kHz burst, 300 -> 70 Hz body, 140 -> 50 Hz sub |
| flak | 0.95 | 1 | FK-Burst fire thud |
| flak_burst | 1.6 | 1 | air-burst at the detonation point (explosion category) |
| pulseshield / pulseshield_down | 0.95 | 1 | PS-Aegis: rising A-C#-E-A chord with shimmer / falling |
| repair | 0.7 | 1 | RK-Mend activated: C-E-G chime |
| repair_loop (ring 8) | 1.8 | loop | chime arpeggio over a C hum while healing (6 s, Stop at the end) |
| decoy | 0.6 | 1 | DC-Chaff: three pops 0.15 s apart over a fizz (the Dogfight `df_flare_release` recipe, re-synthesised) |

### Impacts, deaths, arena events

| key | s | var | what it is |
|---|---|---|---|
| hit_metal | 0.32 | 3 | round on armour: inharmonic ring + click |
| hit_ground | 0.45 | 2 | round on terrain: dull thud + grit |
| boom_small | 1.8 | 1 | small splash (plasma, grenade, flak, missiles) |
| boom_large | 2.9 | 1 | large splash (bazooka, grenade cannon) |
| mech_death | 3.6 | 1 | mech destroyed: 70 -> 22 Hz boom, secondary pops at 0.35-1.3 s, debris rings, hiss |
| stagger_clang | 1.4 | 1 | the staggered mech's bell-like clang (world sound; the pilot also gets ui_stagger) |
| drop_entry | 2.6 | 1 | drop-pod atmospheric entry roar + rising whistle |
| capture_tick | 0.18 | 1 | capture progress tick at the point |
| capture_done | 2.4 | 1 | capture complete: G-C-E-G chord |
| wave_start | 2.0 | 1 | PvE wave klaxon (two detuned saw blasts) over a hit |
| boss_roar | 3.7 | 1 | boss roar: 42 Hz formant-filtered saw growl + breath + sub, range 9000 |
| bounty | 1.7 | 1 | bounty shimmer (C-E-G-C) over a hit |

### Pilot-only tones (`ui: true`, StartSoundOnSingleClient) and round / garage sounds

| key | s | what it is | when |
|---|---|---|---|
| ui_lock1 | 0.07 | one 880 Hz beep | soft lock acquired |
| ui_lock2 | 0.22 | two 1046 Hz beeps | hard lock stage 2 |
| ui_lock3 | 0.27 | three fast 1318 Hz beeps | hard lock (stage 3) |
| ui_locked_warn | 0.5 | 1200/900 Hz warble | someone has you locked; repeat every 0.5-1 s |
| ui_launch_warn | 0.4 | 1.5 kHz chopped at 10 Hz | missile launched at you; repeat every 0.5 s |
| ui_msl_close | 0.3 | 2 kHz chopped at 20 Hz | missile within 0.5 s; repeat every 0.3 s |
| ui_hit | 0.07 | 2.2 kHz tick | hit marker |
| ui_kill | 0.41 | 880-1320-1760 Hz rise | kill confirmed |
| ui_stagger | 0.5 | low chopped buzz | you are staggered |
| ui_low_ap | 0.48 | two 440 Hz beeps | AP under 25 %; repeat every 2 s |
| ui_en_empty | 0.4 | falling 600 -> 180 Hz buzz | EN stalled |
| ui_en_ok | 0.28 | rising 420 -> 840 Hz chirp | EN recovered |
| ui_ready | 0.16 | click + 1 kHz blip | weapon ready / reloaded |
| ui_spawn | 0.9 | rising power-up sweep | mech powered up |
| ui_capture | 0.07 | 1480 Hz tick | capture progress (pilot side) |
| ui_round_start | 3.9 | riser into an E power-chord hit | intro slate (send to everyone) |
| ui_podium | 6.2 | brass-like fanfare in G | podium slate (send to everyone) |
| ui_garage_move | 0.04 | 660 Hz tick | garage cursor |
| ui_garage_ok | 0.2 | 880 -> 1320 Hz | garage confirm |
| ui_garage_deny | 0.22 | 300 -> 200 Hz buzz | garage deny / cannot afford |

(The design's "14 pilot tones" became 15 gameplay tones plus 5 round/garage sounds, at the adapter author's list.)

### Music (`csgo_music`, follows the Main Menu Music slider)

| key | event / entity | length | volume | what it is |
|---|---|---|---|---|
| music_garage | ifr.music_garage / ifr_snd_music_garage | 120.0 s loop | 0.55 | "Hangar Lights": 96 bpm E minor, string pad over Em-C-G-D / Am-Em-C-B, slow electronic bass, square-wave arps and a sparse lead, soft kick + hats |
| music_battle | ifr.music_battle / ifr_snd_music_battle | 180.0 s loop | 0.60 | "Ironframe Overdrive": 160 bpm E minor, palm-muted power-chord riffs (synth.py Guitar x2), bass, full kit, lead hooks in the choruses, a half-time bridge with a lead line, a tom build; 15 x 8-bar sections that wrap into the intro |

Both are rendered 3 s longer than the loop and the overhang folded onto the start, so the loop point has no gap or click.

## 3. Particles (`particles/ifr/`, `_gen/fx_particles.json`)

Format: the vpcf54 text layout of the Dogfight particles (CParticleSystemDefinition, behaviour version 5, editor field names),
which compile with `resourcecompiler -f -i`. Textures are stock CS2 (`particle_flare_001`, `fire_burning_character`,
`particle_smokegrenade`, `effects/yellowflare`, `effects/spark`, `particle_debris_burst_001`), so only the `.vpcf` files ship.
Axes: boosters and muzzles emit along the particle entity's local **+X** (Dogfight convention; point the entity out of the
nozzle / barrel), the missile flame along -X (behind a prop facing +X), hover / pillars / drop entry along +-Z.
Overdraw (cs2-gotchas): every emitter is small and short-lived; per mech a boost is 12 core + up to 44 flame + 24 sparks + 8
haze sprites, so 64 boosting mechs stay under 6k sprites; missile smoke is 60/s with a 1.4-2 s life (128 trails < 15k).

### Pools (`info_particle_system` `ifr_pfx_<kind>_NN`)

| pool | count | effect | use |
|---|---|---|---|
| boost | 128 | ifr_boost_medium | two per mech, parented at claim time, Start/Stop with the boost. An `info_particle_system`'s effect is fixed, so one pool is one class; `variants` lists ifr_boost_light / ifr_boost_heavy if the generator splits the pool by class |
| muzzle | 64 | ifr_muzzle_rifle | one per mech, pulsed (Start) per shot; `muzzle_heavy` is available for a second pool |
| boom | 24 | ifr_boom_small | teleport then Start, ~1 s |
| spark | 16 | ifr_impact_metal | teleport then Start, 0.6 s |
| gboom | 8 | ifr_boom_large | big splashes; mech deaths may use ifr_mech_death on some of these or a 7th pool |
| trail | 128 | ifr_missile_trail | parented to the pooled missile prop, Start at launch, Stop at impact (smoke lingers 2 s) |

### Effects (`effects` key -> file; children listed under `files`)

| key | file | adapted from | what |
|---|---|---|---|
| boost_light / boost_medium / boost_heavy | ifr_boost_<class> | df_thrust_boost + df_thrust_boost_flame + df_hit_sparks | blue-white glow core (radius 26-62), an animated flame tongue tinted blue fading to deep blue, spark spit, faint exhaust haze (children ifr_boost_<class>_flame, ifr_boost_sparks, ifr_boost_heat). A true heat-shimmer needs a refracting normal-map texture under materials/, which is another agent's folder: deferred |
| qb_burst | ifr_qb_burst (+ ifr_qb_ring) | df_flare_burst, df_flare_balls | 18 radial blue-white sprites + an expanding ring, 0.3 s |
| hover | ifr_hover (+ ifr_hover_dust) | df_thrust_idle, df_smoke_light | downward glow wash + dust |
| muzzle_rifle | ifr_muzzle_rifle (+ ifr_muzzle_core) | df_flare_burst | 4 hot sprites thrown forward + a core flash, 80 ms |
| muzzle_heavy | ifr_muzzle_heavy (+ core, ifr_muzzle_smoke) | df_thrust_boost_flame, df_jet_boom_smoke | fire tongue + core + smoke puff |
| tracer | ifr_tracer | poc/df_cannon_tracer_fwd | RenderTrails streak along +X at 11000 u/s, 0.42 s (4600 u), one per Start |
| impact_metal | ifr_impact_metal (+ ifr_impact_flash) | df_hit_sparks | 22 sparks with gravity + flash |
| impact_ground | ifr_impact_ground (+ ifr_impact_grit) | df_jet_boom_smoke | dust puff + grit |
| boom_small | ifr_boom_small (+ _smoke, ifr_boom_sparks, stock flash02b) | df_jet_boom | 7 fire sprites radius 110-180 |
| boom_large | ifr_boom_large (+ _smoke, sparks, stock flash / distort / debris / light) | df_jet_boom | 12 fire sprites radius 300-480 |
| mech_death | ifr_mech_death (+ _smoke, _column 3.5 s, _debris 30 chunks, sparks, the stock explosion_c4 children Dogfight used) | df_jet_boom, df_smoke_heavy | the big one |
| missile_trail | ifr_missile_trail (+ ifr_missile_flame, ifr_missile_smoke) | df_missile_motor / _flame / _smoke | flame along -X + white smoke |
| laser_beam_impact | ifr_laser_beam_impact (+ ifr_beam_sparks) | df_flare_burst, df_hit_sparks | red-white flare burst + molten sparks at a beam end |
| stagger_sparks | ifr_stagger_sparks | df_hit_sparks | blue-white electrical sparks for 2 s, position-locked to the mech |
| shield_bubble | ifr_shield_bubble (+ ifr_shield_core) | df_thrust_boost glow | 350 u shell of blue motes + one faint sphere, 6.5 s |
| repair | ifr_repair | glow | green motes rising, Start 6 s then Stop |
| decoy | ifr_decoy (+ _balls, _sparks, _smoke) | df_flare_burst set | the Dogfight flare burst, 0.5 s |
| capture_t / capture_ct / capture_neutral | ifr_capture_<team> (+ _base) | glow | orange / blue / white motes rising 2000+ u + a glowing base disc |
| drop_entry | ifr_drop_entry (+ _glow, _smoke) | df_thrust_boost_flame | white-orange plasma sheath streaming up off a falling pod |

Stock CS2 particles worth using directly (also in `fx_particles.json` `stock`): `particles/explosions_fx/explosion_c4_500.vpcf`,
`explosion_basic.vpcf`, `explosion_hegrenade_brief.vpcf`, `particles/weapons/cs_weapon_fx/weapon_muzzle_flash_assaultrifle.vpcf`
(+ `_fallback`), `particles/impact_fx/impact_metal.vpcf` (`_cheap`), `impact_dirt.vpcf`, `impact_concrete.vpcf`,
`particles/burning_fx/env_fire_medium_smoke.vpcf` (wreck smoke), `particles/ambient_fx/env_sparks_directional.vpcf`,
`particles/weapons/cs_weapon_fx/weapon_tracers_50cal.vpcf`.

### Frame aura flares (`particles/ifr/aura/`, `_gen/auras.json#pools`)

`tools/auras.py` writes one burst per aura frame from the `tools/particles.py` blocks: `aura_<frame>.vpcf` (18-26 additive sparks or
soft motes in the aura's colours, 0.3-0.7 s, style-specific gravity: Cerberus' rise, Stryder's and Mule's fall, White Glint's drift)
with a child `aura_<frame>_flash.vpcf` (one 70 u flash). Pools: `ifr_pfx_aura_<frame>_00..03` (4 each, 60 entities), added to the
mapper's map by `tools/patch_cache.py` (and by the arena generator, `tools/arenas/common.py`); `47_auras.js` registers the pool names
in `PFX_POOLS`, so `fxInit` finds them and `pfxBurst` plays them (Teleport + Start, Stop after 0.9 s). Without the entities the flares
are mesh-only. No aura sound layer: the existing quick-boost / trait tones already mark those moments.

### Frame aura materials (`materials/ifr/aura/`)

`csgo_unlitgeneric`, `F_BLEND_MODE 4` (additive, confirmed see-through in CS2) or `1` with a `TextureTranslucency` mask (Barbatos'
smoky tendrils, Ogre's cracks, Noblesse's gold rings), `F_RENDER_BACKFACES 1`, `F_TEXTURE_ANIMATION 1` with a 16-cell strip
(`g_vAnimationGrid "[16 1]"`, 0.03-0.2 s per cell; the model UVs span one cell 0..1, the case cs2-gotchas says animates), `g_vColorTint`
1.25 (1.6 for flare states; above 1 is unconfirmed, CS2 may clamp it), `g_flModelTintAmount 1` so the script's `SetColor` sets the
brightness. Textures are painted in `tools/auras.py` (numpy): energy flow, blade rims, lightning, orbiting motes, feathers, ring
segments, plasma plume with shock diamonds, hex lattice + scan, panel seams, molten cracks, rune band, star sigil, glitch scanlines,
beacon sweep, hazard dust ring, rising light. Colours are baked in (one material set per frame).

## 4. Compile check

Scratch addon `C:\source1\links\content_addons\mg_ironframe_dunes` (created from Valve's addon template like
`cs2-roguelike/tools/deploy.sh`): the 90 WAVs, the merged vsndevts and the 52 `.vpcf` were copied in and each compiled with
`resourcecompiler.exe -f -i <file>` (`logs/compile_fx.sh`, logs in `logs/rc/`). 9 Nov 2026: **52/52 .vpcf OK, the vsndevts
OK, and `boost_loop.wav` (loop markers), `music_battle.wav` (stereo loop) and `rifle_01.wav` compile to .vsnd** (3 s each, no
warnings). Re-run the loop after regenerating. Nothing has been heard or seen in game yet.

## 5. What the adapter author must know

- Weapon fire: play `PARTS[w].key` (`rifle gatling shotgun laser bazooka grenade blade plasma rail handmsl shield smg vm6
  dualmsl lasercannon grenadecannon autocannon flak pulseshield repair decoy vm12`); charges: `laser_charge`, `rail_charge`,
  `lasercannon_charge`; extras `gatling_down`, `grenade_bounce`, `blade_clash`, `shield_down`, `pulseshield_down`, `flak_burst`.
- Loops to `StopSound` (`loops_to_stop`): `boost_loop` (per slot), `hover_loop` (per slot, optional), `gatling_loop` (ring 16),
  `msl_loop` (ring 24), `repair_loop` (ring 8), plus `boost_loop_light` / `boost_loop_heavy` if used; and the two music events.
- Pilot tones (`pilot_tones`): `ui_lock1 ui_lock2 ui_lock3 ui_locked_warn ui_launch_warn ui_msl_close ui_hit ui_kill ui_stagger
  ui_low_ap ui_en_empty ui_en_ok ui_ready ui_spawn ui_capture`; everyone: `ui_round_start ui_podium`; garage: `ui_garage_move
  ui_garage_ok ui_garage_deny`.
- Positional one-shots use one entity each with `stopOnNew 0`; per-slot / ring entities use `stopOnNew 1`.
- Particle pools are single-effect; the per-effect files are in `fx_particles.json` `effects` for extra pools or
  `info_particle_system`s the map generator places (capture pillars at the points, drop entry on the drop props).

## Weight and realism pass (9 Nov 2026)

Playtest: "no punch, cartoony". Weapons, impacts, explosions, footsteps, landings and boost ignitions are now **layered events**:
one or more stock CS2 `.vsnd` tracks (`vsnd_files_track_01..NN`, played together, each track a random pick from its list) plus a
last track of our synthesised WAV (sub-bass 25-100 Hz, distant tail, metal ring, debris). The event `pitch` pulls the stock tracks
down (0.55-0.8 for guns/explosions); the synth WAV is pre-warped by the same factor (`prewarp`) so it plays as designed. Layer
choices are in `_gen/sounds.json` (`events.<key>.stock`) and the `note` of each row in `preview/audio/README.md`.

| family | stock layers (pitch) | synth layer |
|---|---|---|
| rifle / autocannon / smg / gatling round | awp_01/02, negev, m249, mac10 (0.66-0.8) | 90-105 Hz -> 40 Hz thump, tail, ring |
| shotgun / flak / grenade | nova-1, xm1014-1 (0.6-0.7) | 82 Hz sub, heavy pump clack |
| bazooka / missiles / grenadecannon | c4_thump_01 (+ xm1014) (0.55-1.1) | launch boom, whoosh, ignition crackle |
| rail | awp_distant, awp_01 (0.6) | electric crack, ring, boom (laser, plasma, lasercannon: synth only) |
| boom_small / boom_large / flak_burst / mech_death | hegrenade_detonate, c4_explode1, c4_exp_deb (0.7-0.9) | 22-98 Hz sub, long tail, debris, collapse groan, secondary pops |
| blade_clash / stagger_clang / hit_metal | physics/metal box, barrel, bullet impacts (0.55-0.8) | clang rings + sub |
| step_* / land_* / hit_ground | physics/metal + concrete impacts, boulder (0.55-0.85) | sub thud, servo whine, dirt |
| boost_on_*, qb | c4_thump_01 (0.7-1.15) | turbine spool + kick, hard air blast |

Synth only (loops cannot reference one-shot stock files): boost_loop*, hover_loop, gatling_loop (now a 0.8 s / 20-round loop), msl_loop,
gatling_down, laser/charges, blade. UI tones are sine + harmonics (no pulse waves).
Mix: weapons/explosions full to 900-1800 u, silent at 6000-10000 u; impacts, landings, footsteps vol 0.45-0.8, full to 250 u, silent 1600-1800 u.
Synth WAV peaks -1 dBFS (loops/synth-only) or lower under a stock layer; 0 clipped samples. Stock paths are stored as `sounds/<path>.vsnd`.
Ability/world sounds (shields, repair, decoy, drop_entry, boss_roar, capture, bounty, music) are unchanged.
