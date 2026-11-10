"""Sounds for original maps: synthesised effects, WAV import (resampled, mono / stereo, loop markers), and their sound events.

  python sndkit.py make <addon content> <name> <preset> [--seconds 2] [--freq 440] [--seed 1] [--loop] [--gain 0.8]
  python sndkit.py import <addon content> <name> <file.wav> [--loop] [--mono]
  python sndkit.py event <addon content> <event.name> <sounds/x.vsnd> [--kind 3d|flat|music] [--range 2000] [--volume 0.8] [--tag mymap]
Presets: beep, alarm, hum, wind, rain, drone, click, whoosh, rumble, charge, zap. Files go to <content>/sounds/gen/<name>.wav (16-bit,
44.1 kHz; loops carry smpl/cue markers so CS2 loops them); events go into <content>/soundevents/soundevents_addon.vsndevts inside a tagged
block (sndevents.merge: re-running replaces only that block). Compile with tools/rcompile.py asset, or let Workshop Tools do it.

Ported from sound.py of cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT): sound_create presets, WAV import and sound_event
kinds; fresh code on skink52's chiptune.write_wav and sndevents writers.
"""
import argparse, os, sys, wave
import numpy as np
import chiptune, sndevents

SR = 44100
PRESETS = ('beep', 'alarm', 'hum', 'wind', 'rain', 'drone', 'click', 'whoosh', 'rumble', 'charge', 'zap')


def synth(preset, seconds=2.0, freq=440.0, seed=1, gain=0.8):
    """-> float32 mono samples in -1..1"""
    if preset not in PRESETS: raise ValueError('preset must be one of %s' % ', '.join(PRESETS))
    n = max(1, int(seconds * SR)); t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    tone = lambda f: np.sin(2 * np.pi * f * t)
    white = rng.standard_normal(n)
    def noise(cut):
        k = max(1, int(SR / cut / 2))
        return np.convolve(white, np.ones(k) / k, 'same') * np.sqrt(k)
    if preset == 'beep': x = tone(freq) * np.minimum(1, np.minimum(t, seconds - t) * 200)
    elif preset == 'alarm': x = np.sign(tone(freq)) * 0.5 * (tone(2) > 0) + tone(freq * 1.5) * 0.3 * (tone(2) <= 0)
    elif preset == 'hum': x = tone(freq / 8) + 0.35 * tone(freq / 4) + 0.12 * tone(3 * freq / 8)
    elif preset == 'wind': x = noise(500) * (0.65 + 0.3 * np.sin(2 * np.pi * 0.4 * t + rng.random() * 6))
    elif preset == 'rain': x = noise(5000) * 0.6 + 0.3 * noise(250) + (rng.random(n) > 0.9995) * rng.standard_normal(n) * 3
    elif preset == 'drone': x = tone(freq / 4) + 0.6 * tone(freq / 4 * 1.03) + 0.4 * noise(150)
    elif preset == 'click': x = white * np.exp(-t * 90) + 0.25 * tone(1800) * np.exp(-t * 60)
    elif preset == 'whoosh': x = noise(2500) * np.sin(np.pi * t / seconds) ** 2
    elif preset == 'rumble': x = noise(90) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.25 * t)) * np.exp(-t / max(0.3, seconds))
    elif preset == 'charge':
        f = freq / 2 + (freq * 3) * (t / seconds) ** 1.5
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.4 + 0.6 * t / seconds)
    else:   # zap
        f = freq * 6 * np.exp(-t * 18) + freq / 2
        x = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.exp(-t * 12) * 0.6 + white * np.exp(-t * 30) * 0.3
    x = x - x.mean()
    peak = np.max(np.abs(x)) or 1.0
    fade = np.minimum(1, np.minimum(t, seconds - t) / 0.005)
    return (x / peak * gain * fade).astype(np.float32)


def read_wav(path):
    """-> (float32 samples (n,) or (n, 2), rate); 8 / 16 / 24 / 32-bit PCM"""
    with wave.open(path, 'rb') as w:
        ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width == 1: a = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128) / 128
    elif width == 2: a = np.frombuffer(raw, '<i2').astype(np.float32) / 32768
    elif width == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
        a = ((b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16)) << 8 >> 8).astype(np.float32) / 8388608
    else: a = np.frombuffer(raw, '<i4').astype(np.float32) / 2147483648
    a = a.reshape(-1, ch)
    return (a[:, 0] if ch == 1 else a[:, :2]), rate


def resample(x, rate, to=SR):
    if rate == to: return x
    n = int(round(len(x) * to / rate))
    src = np.arange(len(x)) * (to / rate)
    dst = np.arange(n)
    if x.ndim == 1: return np.interp(dst, src, x).astype(np.float32)
    return np.stack([np.interp(dst, src, x[:, c]) for c in range(x.shape[1])], 1).astype(np.float32)


def write(content, name, x, loop=False, sub='gen'):
    """-> 'sounds/<sub>/<name>.vsnd' (the path events use); the WAV is written next to where the vsnd compiles"""
    rel = 'sounds/%s/%s.wav' % (sub, name)
    p = os.path.join(content, *rel.split('/')); os.makedirs(os.path.dirname(p), exist_ok=True)
    if x.ndim == 2:
        y = np.clip(x, -1, 1); data = (y * 32767).astype('<i2').tobytes()
        with wave.open(p, 'wb') as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(data)
    else:
        chiptune.write_wav(p, np.asarray(x, np.float64), loop=loop)
    return rel[:-4] + '.vsnd'


def event(content, name, vsnd, kind='3d', range_=2000, volume=0.8, tag='sndkit'):
    """add / replace the event in the addon's soundevents_addon.vsndevts (inside this tag's block, with any earlier events of the tag)"""
    if kind == '3d': text = sndevents.event_3d(name, vsnd, range_, volume)
    elif kind == 'flat': text = sndevents.event_music_flat(name, vsnd, volume)
    elif kind == 'music': text = sndevents.event_csgo_music(name, vsnd, volume)
    else: raise ValueError('kind must be 3d, flat or music')
    path = os.path.join(content, 'soundevents', 'soundevents_addon.vsndevts')
    old = open(path, encoding='utf-8').read() if os.path.exists(path) else sndevents.wrap([])
    begin, end = sndevents.markers(tag)
    events = {}
    if begin in old and end in old:
        block = old[old.index(begin) + len(begin):old.index(end)]
        for chunk in block.split('\n\t"')[1:]:
            ev = chunk.split('"', 1)[0]
            events[ev] = '\t"' + chunk.rstrip()
    events[name] = text.rstrip()
    new = sndevents.merge(old, '\n'.join(events[k] for k in sorted(events)), tag)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f: f.write(new)
    return {'event': name, 'file': path, 'events_in_block': sorted(events)}


def main(argv=None):
    ap = argparse.ArgumentParser(description='Sounds and sound events')
    ap.add_argument('cmd', choices=['make', 'import', 'event']); ap.add_argument('content'); ap.add_argument('name'); ap.add_argument('arg')
    ap.add_argument('--seconds', type=float, default=2.0); ap.add_argument('--freq', type=float, default=440.0); ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--gain', type=float, default=0.8); ap.add_argument('--loop', action='store_true'); ap.add_argument('--mono', action='store_true')
    ap.add_argument('--kind', default='3d'); ap.add_argument('--range', type=float, default=2000); ap.add_argument('--volume', type=float, default=0.8)
    ap.add_argument('--tag', default='sndkit')
    a = ap.parse_args(argv)
    if a.cmd == 'make': print(write(a.content, a.name, synth(a.arg, a.seconds, a.freq, a.seed, a.gain), a.loop))
    elif a.cmd == 'import':
        x, rate = read_wav(a.arg); x = resample(x, rate)
        if a.mono and x.ndim == 2: x = x.mean(1)
        print(write(a.content, a.name, x, a.loop))
    else: print(event(a.content, a.name, a.arg, a.kind, a.range, a.volume, a.tag))
    return 0


if __name__ == '__main__':
    sys.exit(main())
