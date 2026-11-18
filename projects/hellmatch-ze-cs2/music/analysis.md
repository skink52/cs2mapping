# Hellmatch music: reference analysis and generated tracks

Numbers from `tools/music_analysis.py` (numpy/scipy STFT, ffmpeg loudnorm for loudness). Reference file:
`hellmatch_trailer_music.mp3` (49.4 s, 48 kHz stereo, 256 kb/s).

## Reference track

- **Tempo: 150 bpm** (4/4). The onset-strength autocorrelation puts almost equal weight on 152 bpm (0.40) and
  60 bpm (0.40, the 2-bar period); a comb tempogram over 1-4 beat lags peaks cleanly at 150 bpm, with 75 bpm
  (half-time) and 100 bpm (2/3) as the next candidates. Confidence is moderate (0.35 of the top-3 mass) because
  the kick mostly sits on the half-note while the guitars carry the 8ths, so a half-time 75 bpm reading is
  possible; 150 bpm with 8th-note drive is the musically sensible one.
- **Key: D minor** (Krumhansl correlation 0.66, runner-up D major 0.56; D minor also wins each section on its
  own). The bass-note histogram is dominated by A (33 %), C (30 %), F (18 %) and D (12 %): a pedal on the
  fifth and bVII/bIII movement, i.e. D Aeolian. The ending (41-48 s) tips towards D major.
- **Loudness: -12.3 LUFS integrated, true peak -1.4 dBTP, loudness range 3.5 LU**: a dense modern master with
  almost no dynamics; per-second RMS sits at -13 to -14 dBFS through the whole body of the track.
- **Spectral balance:** low (<200 Hz) 47 %, mid (200-2000 Hz) 35 %, high (>2 kHz) 18 % of the energy; spectral
  centroid 983 Hz; 85 % of the energy is below 2.3 kHz. Band energies relative to the total (dB): 20-60 Hz -7.7,
  60-120 -6.6, 120-250 -9.7, 250-500 -10.9, 500-1k -9.8, 1-2k -8.6, 2-4k -8.7, 4-8k -14.4, 8k+ -21.7. So: a big
  sub/kick region, a mild low-mid scoop, a strong 1-4 kHz presence region (guitar bite, snare) and a tame top octave.
- **Rhythmic density: 4.0 onsets/s** (199 onsets in 49 s): constant 8th/16th-note drive plus accents, nothing sparse.
- **Structure (49 s):** 0-8 s intro/build (filter sweep, drums from ~4 s), 8-29 s main riff section (RMS -13.5 dB),
  29-41 s louder hook section (-12.6 dB, lead over the riff), 41-44 s ending stabs, 44-49 s crash ring-out and fade.
  Novelty boundaries at 8.0, 29.5 and 41.0 s; one near-silent second at the very end.

In plain English: a tight, loud, modern heavy track at 150 bpm in D minor with constant 8th/16th drive, a huge low
end, a scooped low-mid, bright guitar presence and a short hook section. It is a produced metal/industrial mix,
nothing chiptune-like about it.

## What the generator does with that

`tools/compose.py` writes four tracks at 140-164 bpm (150 bpm +-10 %) in minor keys around D minor (D, A, G, E
minor), 190-210 s each, with intro, verse, pre-chorus, chorus (a returning 4-bar hook), breakdown, solo, final chorus
and a short outro; `tools/synth.py` renders them (synthesised guitars, bass, lead, pads and drums, no samples). Each
render is normalised to the project target (`loudnorm I=-16:TP=-1.5:LRA=11`, two-pass, linear) and encoded to
128 kb/s MP3. The generated files are therefore about 4 LU quieter than the reference file by design: the game
normalises every track to -16 LUFS and the reference would land there too.

- industrial: 16th-note synth-bass pulse, organ pad, four-on-the-floor kick with claps, sidechain pump, Phrygian riffs
- thrash: 164 bpm, harmonic minor, tremolo/gallop riffs, skank beat in the pre-chorus, china-cymbal half-time breakdown
- doom feel in the middle: 140 bpm, long half-time breakdown with slow open chords and tritone riff under the hook, choir pad
- heroic: string pad, lead motif in the intro, gallop drums with ride, hook doubled an octave up in the last chorus

## Generated tracks vs reference

| file | title | s | bpm | key (detected) | LUFS | TP dBTP | LRA | low/mid/high % | centroid Hz | onsets/s |
|---|---|---|---|---|---|---|---|---|---|---|
| reference | trailer music | 49 | 150 | D minor | -12.3 | -1.4 | 3.5 | 47/35/18 | 983 | 4.0 |
| gen01.mp3 | Ferrous Pulse (industrial) | 207 | 150 | D minor | -16.5 | -4.7 | 2.7 | 46/39/15 | 970 | 4.0 |
| gen02.mp3 | Chainsaw Vespers (thrash) | 196 | 164 | A minor | -16.4 | -5.6 | 2.3 | 34/47/20 | 1142 | 5.0 |
| gen03.mp3 | Low Orbit of Hell (doom) | 194 | 140 | G minor | -16.4 | -5.0 | 2.2 | 38/46/17 | 1024 | 4.4 |
| gen04.mp3 | Valkyrie Fragstorm (heroic) | 193 | 156 | G major | -16.4 | -5.2 | 3.0 | 39/42/19 | 1101 | 5.0 |

Band energies relative to each file's total (dB):

| file | 20-60 | 60-120 | 120-250 | 250-500 | 500-1k | 1-2k | 2-4k | 4-8k | 8k+ |
|---|---|---|---|---|---|---|---|---|---|
| reference | -7.7 | -6.6 | -9.7 | -10.9 | -9.8 | -8.6 | -8.7 | -14.4 | -21.7 |
| gen01.mp3 | -7.7 | -7.1 | -8.7 | -11.2 | -8.1 | -9.1 | -10.1 | -14.4 | -18.4 |
| gen02.mp3 | -11.1 | -8.5 | -7.8 | -9.6 | -8.3 | -7.9 | -8.4 | -13.5 | -21.9 |
| gen03.mp3 | -9.9 | -8.6 | -7.7 | -9.2 | -8.2 | -8.2 | -9.1 | -14.2 | -22.6 |
| gen04.mp3 | -9.5 | -8.2 | -8.2 | -10.9 | -9.1 | -7.3 | -8.3 | -14.1 | -22.5 |

Reading the comparison: tempo, key, onset density and section structure all sit in the reference's range (the key
detector reads gen04 as G major, the relative major of the E minor it is written in: its chorus progression leans on
bIII and bVII). The spectral balance is close: gen01 matches the
reference almost band for band; gen02-04 have 2-3 dB less sub (20-60 Hz) and 1-2 dB more 120-250 Hz, and all four
are within about 1.5 dB in the 1-4 kHz presence region. Loudness is within 0.6 LU of the -16 LUFS target and the
true peak is around -5 dBTP (well inside the -1 dBTP limit: loudnorm's own ceiling is -1.5 dBTP and the drop from
the ~-11 LUFS render leaves headroom). Loudness range is 2-3 LU, like the reference's 3.5; there are no quiet
stretches, the half-time breakdowns stay within about 1.3 dB RMS of the choruses, and the only soft second is the
final ring-out.

Caveats: the guitars are detuned saw stacks through a waveshaper and cabinet EQ, so they sound synthetic (closer to
industrial/synth-metal than to a mic'd amp), and the drums are analogue-style synthesised hits rather than acoustic
samples. Within those limits the tracks are in the same spirit as the reference: fast, dense, bass-heavy, with a
hook that comes back.
