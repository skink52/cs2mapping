"""IRONFRAME sounds: every sound effect, pilot tone and music loop, synthesised here (no samples), their CS2 sound
events, and the baked table the script and the map generator read.

usage: python -I tools/sounds.py <addon out dir> [--soundevents <live soundevents_addon.vsndevts>] [--no-music] [--only a,b]
Writes
  <out>/sounds/ifr/*.wav                     44.1 kHz 16-bit PCM, mono for 3D sounds, stereo music; loops carry smpl + cue markers
  <out>/soundevents/soundevents_addon.vsndevts   our events merged (tag IRONFRAME) into --soundevents, else into Valve's template
  <out>/_gen/sounds.json                     {"events": {key: {event, entity, range, loop, ui, stop_on_new, per_slot?, ring?, ...}}, "music": {...}}
  preview/audio/contact_sheet.png, spec_*.png, README.md   waveforms, spectrograms, a table of seconds / peak / RMS

Conventions (agreed with the adapter, docs/AUDIO_FX.md): event "ifr.<key>", entity "ifr_snd_<key>"; a one-shot positional
event is one entity with stop_on_new false (the adapter SetSourceEntity's it onto a pooled anchor prop and StartSounds);
"per_slot": 64 loops get ifr_snd_<key>_00..63 (one per mech slot); "ring": N loops get ifr_snd_<key>_00..N-1;
"ui": true tones are not placed in the world (StartSoundOnSingleClient). Music follows the Main Menu Music slider
(csgo_music + volume_convar, see docs/creation/sound.md).

Synthesis: numpy/scipy here plus create/chiptune.py (pulse tones, loop-marker writer) and create/synth.py (music
instruments, mixer, reverb). Every sound is peak-normalised to -1 dBFS; the event volume is then trimmed per category
from the measured RMS so a category sounds even in game (the table is in preview/audio/README.md).
"""
import os, sys, json, math, argparse
import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
CREATE = os.path.normpath(os.path.join(PROJ, '..', '..', 'create'))
sys.path.insert(0, CREATE)
import chiptune as C          # noqa: E402
import sndevents as E         # noqa: E402
import synth as S             # noqa: E402

SR = 44100
PEAK_DB = -1.0
TEMPLATE = r'C:\source1\cs2port\tools\addon_template\content\soundevents\soundevents_addon.vsndevts'
rng = np.random.default_rng(1952)


# ================================================================ DSP toolbox
def N(s): return int(round(s * SR))
def T(n): return np.arange(n) / SR
def dbv(x): return 10 ** (x / 20)
def wn(n, seed=None): return (np.random.default_rng(seed) if seed is not None else rng).uniform(-1, 1, n)
def pink(n, seed=None):
    """1/f noise: filtered white (3 one-pole stages)"""
    x = wn(n, seed); b, a = signal.butter(1, 400, 'low', fs=SR); y = signal.lfilter(b, a, x)
    return y / (np.abs(y).max() + 1e-9) + 0.3 * x


def lp(x, fc, o=2): return S.lp(x, min(fc, SR * 0.45), o)
def hp(x, fc, o=2): return S.hp(x, max(fc, 10), o)
def bp(x, lo, hi, o=2): return S.bp(x, max(lo, 10), min(hi, SR * 0.45), o)


def xs(f0, f1, n):
    """exponential frequency sweep f0 -> f1"""
    return f0 * (f1 / f0) ** (np.linspace(0, 1, n))


def sine(f, n, ph=0.0):
    f = np.broadcast_to(np.asarray(f, np.float64), (n,))
    return np.sin(2 * np.pi * (np.cumsum(f) / SR + ph))


def saw(f, n): return S.saw(np.broadcast_to(np.asarray(f, np.float64), (n,)), n, rng.random())
def sq(f, n, w=0.5): return S.pulse(np.broadcast_to(np.asarray(f, np.float64), (n,)), n, w, rng.random())


def fm(fc, fm_, idx, n):
    """FM: carrier fc, modulator fm_, index idx (any may be arrays)"""
    fm_ = np.broadcast_to(np.asarray(fm_, np.float64), (n,))
    m = np.sin(2 * np.pi * np.cumsum(fm_) / SR)
    fc = np.broadcast_to(np.asarray(fc, np.float64), (n,))
    return np.sin(2 * np.pi * np.cumsum(fc) / SR + idx * m)


def ad(n, a, d, hold=0.0):
    """linear attack a s, hold, then exponential decay with time constant d"""
    t = T(n); e = np.minimum(t / max(a, 1e-5), 1.0)
    return e * np.exp(-np.maximum(t - a - hold, 0) / max(d, 1e-4))


def lin(points, n):
    """piecewise linear envelope from [(t_sec, value), ...]"""
    t = T(n); xs_, ys = zip(*points)
    return np.interp(t, xs_, ys)


def drive(x, k=2.0): return np.tanh(k * x) / math.tanh(k) if k < 1 else np.tanh(k * x)


def metal(n, freqs, decays, amps=None, seed=0):
    """inharmonic ringing partials: a struck plate / bell"""
    r = np.random.default_rng(seed); x = np.zeros(n); t = T(n)
    amps = amps or [1.0] * len(freqs)
    for f, d, a in zip(freqs, decays, amps):
        x += a * np.sin(2 * np.pi * f * (1 + 0.002 * r.standard_normal()) * t + r.random() * 6.28) * np.exp(-t / d)
    return x / (np.abs(x).max() + 1e-9)


def sweep_bp(x, lo0, lo1, hi0, hi1, blocks=32):
    """band-pass whose edges glide (exponentially) over the signal, blockwise"""
    out = np.empty_like(x); edges = np.linspace(0, len(x), blocks + 1).astype(int); zi = None
    for i in range(blocks):
        k = (i + 0.5) / blocks
        lo = lo0 * (lo1 / lo0) ** k; hi = hi0 * (hi1 / hi0) ** k
        sos = signal.butter(2, [max(lo, 20), min(hi, SR * 0.45)], 'band', fs=SR, output='sos')
        if zi is None: zi = signal.sosfilt_zi(sos) * x[0]
        out[edges[i]:edges[i + 1]], zi = signal.sosfilt(sos, x[edges[i]:edges[i + 1]], zi=zi)
    return out


def rev(x, sec=0.5, wet=0.25, bright=0.5, seed=3):
    """small mono reverb: decaying noise impulse, darker tail"""
    r = np.random.default_rng(seed); n = N(sec); t = T(n)
    ir = lp(r.uniform(-1, 1, n), 1200 + 6000 * bright, 1) * np.exp(-t / (sec / 3.5))
    ir[:N(0.004)] = 0; ir /= (np.sqrt(np.sum(ir ** 2)) + 1e-9)
    y = signal.fftconvolve(x, ir)
    out = np.zeros(len(x) + n); out[:len(x)] = x * (1 - wet); out[:len(y)] += y[:len(out)] * wet * 2.5
    return out


def mixn(*parts):
    """sum arrays of different lengths (zero-padded)"""
    n = max(len(p) for p in parts); out = np.zeros(n)
    for p in parts: out[:len(p)] += p
    return out


def pad(x, sec): return np.concatenate([x, np.zeros(N(sec))])


def fade(x, a=0.002, r=0.01):
    x = x.copy(); fa, fr = min(N(a), len(x) // 2), min(N(r), len(x) // 2)
    if fa: x[:fa] *= np.linspace(0, 1, fa)
    if fr: x[-fr:] *= np.linspace(1, 0, fr)
    return x


def loopify(x, cross=0.12):
    """seamless loop: the tail crossfades into the head; the output is shorter by `cross` seconds"""
    c = N(cross); n = len(x); out = x[:n - c].copy(); r = np.linspace(0, 1, c)
    out[:c] = x[n - c:] * (1 - r) + x[:c] * r
    return out


def finalize(x):
    """DC off, high-pass 25 Hz, peak to PEAK_DB"""
    x = np.asarray(x, np.float64); x = x - x.mean(); x = hp(x, 25, 1)
    return x / (np.abs(x).max() + 1e-9) * dbv(PEAK_DB)


def shots(hit, times, gains=None):
    """place copies of `hit` at the given times (seconds)"""
    n = N(max(times)) + len(hit) + 1; out = np.zeros(n)
    for i, t0 in enumerate(times):
        g = gains[i] if gains else 1.0; a = N(t0); out[a:a + len(hit)] += hit * g
    return out


def blip(f, sec, duty=0.5, a=0.002, d=0.03, s=0.6, r=0.03, vib=0.0):
    """a clean UI pulse tone (polyBLEP pulse, smooth envelope); f may sweep (array)"""
    n = N(sec); t = T(n)
    f = np.broadcast_to(np.asarray(f, np.float64), (n,))
    if vib: f = f * (1 + vib * np.sin(2 * np.pi * 6 * t))
    d = max(d, 1e-6)
    env = np.minimum(t / a, 1) * np.where(t < a + d, 1 - (1 - s) * np.clip((t - a) / d, 0, 1), s) * np.minimum((sec - t) / r, 1)
    return (sine(f, n) + 0.22 * sine(2 * f, n) + 0.08 * sine(3 * f, n)) * 0.8 * np.clip(env, 0, 1)


# ================================================================ categories and the registry
# category: full-volume radius, silent radius, base volume, mixgroup, target RMS dBFS (per-sound trim toward it)
CATS = {
    'weapon_light':  (900, 6000, 1.00, 'Weapons', -13.0),
    'weapon_medium': (1200, 7500, 1.00, 'Weapons', -12.0),
    'weapon_heavy':  (1500, 9500, 1.00, 'Weapons', -11.0),
    'booster':       (1200, 4500, 0.60, 'World', -18.0),
    'explosion':     (1800, 10000, 1.00, 'Explosions', -11.0),
    'impact':        (250, 1600, 0.60, 'World', -16.0),
    'foley':         (250, 1800, 0.55, 'World', -18.0),
    'ability':       (500, 3000, 0.80, 'World', -16.0),
    'world':         (2000, 9000, 1.00, 'World', -13.0),
    'ui':            (0, 0, 0.60, 'UI', -16.0),
}
SFX = {}      # key -> dict(cat, variants=[arrays], loop, per_slot, ring, pitch, note, src)


def sfx(key, cat, *variants, loop=False, per_slot=None, ring=None, pitch=0.04, note='', src='synthesised here', stock=None, vol=None):
    vs = [finalize(v) for v in variants]
    if stock:                      # layered event: the synth track is pre-warped by the event pitch and sits `level` dB under full scale
        vs = [prewarp(v, stock['pitch']) * dbv(stock['level']) for v in vs]; src = 'stock CS2 tracks + synthesised track'
    SFX[key] = dict(cat=cat, variants=vs, loop=loop, per_slot=per_slot, ring=ring,
                    pitch=pitch, note=note, src=src, stock=stock, vol=vol)


# ================================================================ boosters and movement
def thruster_loop(kind):
    """a stationary 3 s bed: filtered noise + a drone, then crossfaded into a seamless loop"""
    n = N(3.2); t = T(n)
    if kind == 'light':
        hiss = bp(wn(n, 11), 1800, 7000) * (0.8 + 0.2 * np.sin(2 * np.pi * 9 * t))
        whine = sine(1180 * (1 + 0.004 * np.sin(2 * np.pi * 3.1 * t)), n) * 0.35 + sine(2360, n) * 0.12 + sine(1770, n) * 0.08
        body = lp(saw(140, n), 900) * 0.25
        x = hiss * 0.55 + whine * 0.5 + body
    elif kind == 'heavy':
        rumble = lp(wn(n, 13), 420) * (0.75 + 0.25 * np.sin(2 * np.pi * 6.5 * t) * np.sin(2 * np.pi * 1.3 * t))
        sub = sine(44 * (1 + 0.01 * np.sin(2 * np.pi * 0.7 * t)), n) * 0.5 + sine(88, n) * 0.2
        drone = lp(saw(66, n), 500) * 0.35
        hiss = bp(wn(n, 14), 900, 3000) * 0.18
        x = rumble * 0.9 + sub + drone + hiss
    else:
        roar = bp(wn(n, 12), 350, 2800) * (0.85 + 0.15 * np.sin(2 * np.pi * 7.3 * t))
        drone = lp(saw(96 * (1 + 0.006 * np.sin(2 * np.pi * 2.3 * t)), n), 1400) * 0.35 + sine(96, n) * 0.25
        whine = sine(780, n) * 0.12 * (0.7 + 0.3 * np.sin(2 * np.pi * 5 * t))
        x = roar * 0.75 + drone + whine
    return loopify(drive(x * 0.8, 1.5), 0.25)


def boost_on(kind):
    n = N(0.7); t = T(n)
    f0, f1, tone = {'light': (180, 60, 7000), 'medium': (140, 45, 5000), 'heavy': (110, 32, 3000)}[kind]
    thump = sine(xs(f0, f1, n), n) * ad(n, 0.003, 0.09)
    burst = sweep_bp(wn(n, 21), 300, 120, tone, 900) * ad(n, 0.004, 0.18)
    ign = bp(wn(n, 22), 2000, 9000) * ad(n, 0.001, 0.025)
    return mixn(thump * 0.9, burst * 0.9, ign * 0.5)


def quick_boost():
    n = N(0.62); t = T(n)
    whoosh = sweep_bp(wn(n, 31), 300, 1400, 1200, 6000) * lin([(0, 0), (0.06, 1), (0.25, 0.7), (0.62, 0)], n)
    tail = sweep_bp(wn(n, 32), 1400, 250, 5000, 900) * lin([(0, 0), (0.2, 0), (0.3, 0.8), (0.62, 0)], n)
    tone = sine(xs(260, 1100, n), n) * lin([(0, 0), (0.05, 0.5), (0.3, 0.2), (0.62, 0)], n)
    return mixn(whoosh, tail, tone * 0.6)


def hover_loop():
    n = N(2.6); t = T(n)
    x = bp(wn(n, 41), 260, 1500) * (0.8 + 0.2 * np.sin(2 * np.pi * 14 * t)) * 0.7 + sine(58, n) * 0.4 + lp(saw(116, n), 700) * 0.2
    return loopify(x, 0.3)


def landing(kind):
    n = N(0.9 if kind == 'heavy' else 0.55)
    f0, f1 = (95, 30) if kind == 'heavy' else (160, 55)
    thud = sine(xs(f0, f1, n), n) * ad(n, 0.002, 0.14 if kind == 'heavy' else 0.08)
    crunch = lp(wn(n, 51), 1800 if kind == 'heavy' else 3500) * ad(n, 0.001, 0.05)
    clank = metal(n, [1850, 2470, 3320], [0.12, 0.09, 0.06], seed=5) * ad(n, 0.0, 0.1) * (0.35 if kind == 'heavy' else 0.5)
    servo = sine(xs(900, 400, n), n) * ad(n, 0.05, 0.1, 0.08) * 0.1
    return rev(mixn(drive(thud * 1.4, 1.8), crunch * 0.8, clank, servo), 0.35, 0.18)


def footstep(kind):
    n = N(0.45); f0, f1, tone, w = {'light': (130, 60, 4000, 0.4), 'medium': (100, 45, 2600, 0.6), 'heavy': (80, 32, 1800, 0.9)}[kind]
    thud = sine(xs(f0, f1, n), n) * ad(n, 0.002, 0.07 * (1 + w))
    crunch = lp(wn(n, 61), tone) * ad(n, 0.001, 0.03)
    servo = sine(xs(1300, 700, n), n) * lin([(0, 0), (0.03, 0.12), (0.18, 0.08), (0.3, 0)], n) * (1.2 - w)
    plate = metal(n, [1500, 2200], [0.07, 0.05], seed=6) * ad(n, 0, 0.05) * 0.3
    return mixn(drive(thud * 1.3, 1.6), crunch * 0.6, servo, plate)


# ================================================================ weapons
def crack(n, seed, tone=5000, body=(420, 90), bdec=0.07, ndec=0.035, punch=1.0):
    """generic gunshot: transient click, noise burst, a pitched body sweep, soft drive"""
    click = hp(wn(n, seed), 3000) * ad(n, 0.0005, 0.004)
    burst = lp(wn(n, seed + 1), tone) * ad(n, 0.001, ndec)
    bod = sine(xs(body[0], body[1], n), n) * ad(n, 0.001, bdec)
    return drive(mixn(click * 0.7, burst, bod * punch), 2.2)


def rifle(v):
    n = N(0.38); x = crack(n, 100 + v * 3, tone=5200 + 400 * v, body=(400 + 30 * v, 95), bdec=0.06, ndec=0.03)
    mech = bp(wn(n, 110 + v), 2500, 6000) * lin([(0, 0), (0.06, 0), (0.07, 0.25), (0.11, 0)], n)   # the action cycling
    return rev(mixn(x, mech), 0.3, 0.14)


def smg(v):
    n = N(0.26); x = crack(n, 130 + v * 3, tone=6500, body=(520, 140), bdec=0.035, ndec=0.02, punch=0.7)
    return rev(x, 0.2, 0.1, 0.7)


def gatling_loop():
    """10 rounds at 25/s = 0.40 s, exactly one loop, plus the barrel motor"""
    hit = crack(N(0.09), 150, tone=6000, body=(500, 150), bdec=0.03, ndec=0.018, punch=0.6)
    x = shots(hit, [i / 25 for i in range(10)], [0.9 + 0.1 * ((i * 7) % 3) / 2 for i in range(10)])[:N(0.4)]
    n = len(x); t = T(n)
    motor = lp(saw(175, n), 2200) * 0.22 + sine(350, n) * 0.08
    return x + motor * (0.9 + 0.1 * np.sin(2 * np.pi * 25 * t))


def gatling_down():
    n = N(1.4); t = T(n)
    whine = lp(saw(xs(175, 30, n), n), 2200) * lin([(0, 0.35), (1.0, 0.25), (1.4, 0)], n)
    clicks = shots(hp(wn(N(0.01), 161), 2500) * ad(N(0.01), 0.0005, 0.003), [0.05, 0.14, 0.26, 0.42, 0.63, 0.9, 1.2])
    return mixn(whine, clicks[:n] * 0.5)


def shotgun():
    n = N(0.75); x = crack(n, 170, tone=3200, body=(260, 48), bdec=0.11, ndec=0.07, punch=1.3)
    sub = sine(xs(120, 38, n), n) * ad(n, 0.002, 0.12) * 0.7
    pump = shots(bp(wn(N(0.03), 171), 1200, 4000) * ad(N(0.03), 0.001, 0.008), [0.38, 0.47])[:n] * 0.6
    return rev(mixn(x, sub, pump), 0.45, 0.2)


def laser_zap():
    n = N(0.45); t = T(n)
    core = fm(xs(2600, 260, n), xs(900, 120, n), 3.0, n) * ad(n, 0.001, 0.09)
    hiss = hp(wn(n, 181), 4000) * ad(n, 0.001, 0.05) * 0.6
    tail = sine(xs(420, 110, n), n) * ad(n, 0.01, 0.12, 0.05) * 0.4
    return mixn(core, hiss, tail)


def charge(sec, f0, f1, seed, noise_hi=6000, trem=False, bright=True):
    n = N(sec); t = T(n); k = np.linspace(0, 1, n)
    tone = sine(xs(f0, f1, n), n) * (0.3 + 0.7 * k) + sine(xs(f0 * 2, f1 * 2, n), n) * 0.3 * k
    nz = sweep_bp(wn(n, seed), 300, 1200, 1500, noise_hi) * k ** 2 * 0.7
    if trem: tone = tone * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * (4 + 26 * k ** 2) * t)))
    x = (tone + nz) * np.minimum(t / 0.05, 1) * np.minimum((sec - t) / 0.03, 1)
    return x


def bazooka():
    n = N(1.1); thump = sine(xs(90, 28, n), n) * ad(n, 0.003, 0.2)
    burst = lp(wn(n, 191), 1400) * ad(n, 0.002, 0.12)
    whoosh = sweep_bp(wn(n, 192), 400, 1800, 1600, 7000) * lin([(0, 0), (0.05, 0.8), (0.4, 0.3), (1.1, 0)], n)
    return rev(mixn(drive(thump * 1.6, 2.0), burst, whoosh * 0.7), 0.6, 0.22, 0.4)


def grenade_thunk():
    n = N(0.4); x = lp(wn(n, 201), 700) * ad(n, 0.002, 0.06)
    pipe = bp(sine(xs(240, 160, n), n) * ad(n, 0.001, 0.1), 200, 500) * 1.5
    return rev(mixn(drive(x, 1.5), pipe), 0.3, 0.15)


def grenade_bounce():
    n = N(0.3); x = metal(n, [2100, 3300, 4800, 6200], [0.08, 0.06, 0.04, 0.03], seed=7) * ad(n, 0.0, 0.1)
    return mixn(x, hp(wn(n, 211), 3000) * ad(n, 0.0005, 0.006) * 0.6)


def blade_swing():
    n = N(0.55); t = T(n)
    whoosh = sweep_bp(wn(n, 221), 250, 2500, 900, 9000) * lin([(0, 0), (0.12, 0.3), (0.22, 1), (0.35, 0.3), (0.55, 0)], n)
    hum = lp(sq(xs(110, 130, n), n, 0.3), 2500) * (0.6 + 0.4 * np.sin(2 * np.pi * 55 * t)) * lin([(0, 0), (0.05, 0.5), (0.4, 0.5), (0.55, 0)], n)
    return mixn(whoosh, hum * 0.5)


def blade_clash():
    n = N(0.7); x = metal(n, [1870, 2340, 3110, 4720, 6100], [0.25, 0.2, 0.15, 0.1, 0.07], [1, 0.8, 0.6, 0.4, 0.3], seed=8)
    burst = hp(wn(n, 231), 2500) * ad(n, 0.0005, 0.02)
    zap = fm(xs(1800, 300, n), 180, 4, n) * ad(n, 0.001, 0.08) * 0.6
    return rev(mixn(x * 0.9, burst, zap), 0.4, 0.2)


def plasma():
    n = N(0.5); t = T(n)
    x = fm(xs(190, 120, n), xs(95, 60, n), 2.5, n) * ad(n, 0.004, 0.12)
    sizzle = bp(wn(n, 241), 1500, 7000) * ad(n, 0.002, 0.08) * 0.5
    wob = sine(xs(600, 200, n), n) * (0.5 + 0.5 * np.sin(2 * np.pi * 40 * t)) * ad(n, 0.002, 0.1) * 0.4
    return mixn(drive(x * 1.3, 1.8), sizzle, wob)


def rail_crack():
    n = N(0.9); click = hp(wn(n, 251), 2000) * ad(n, 0.0003, 0.012)
    sweep = sine(xs(3200, 180, n), n) * ad(n, 0.0005, 0.05)
    thump = sine(xs(110, 36, n), n) * ad(n, 0.002, 0.16) * 0.9
    sizzle = bp(wn(n, 252), 2000, 9000) * ad(n, 0.002, 0.2) * 0.4
    return rev(drive(mixn(click, sweep, thump, sizzle), 2.0), 0.9, 0.3, 0.5)


def missile_launch(count=1, spacing=0.0, heavy=False):
    hit_n = N(0.7); t = T(hit_n)
    pop = lp(wn(hit_n, 261), 1200 if heavy else 2200) * ad(hit_n, 0.001, 0.04 if heavy else 0.025)
    whoosh = sweep_bp(wn(hit_n, 262), 500, 2500, 1500, 8000) * lin([(0, 0), (0.03, 1), (0.25, 0.5), (0.7, 0)], hit_n)
    thump = sine(xs(150 if heavy else 220, 50, hit_n), hit_n) * ad(hit_n, 0.002, 0.08) * (1.0 if heavy else 0.5)
    one = mixn(pop, whoosh * 0.8, thump)
    return shots(one, [i * spacing for i in range(count)], [1.0 - 0.03 * i for i in range(count)]) if count > 1 else one


def rocket_loop():
    n = N(1.8); t = T(n)
    x = bp(wn(n, 271), 350, 3000) * (0.8 + 0.2 * np.sin(2 * np.pi * 31 * t)) + sine(95, n) * 0.25
    return loopify(x, 0.25)


def lasercannon_charge():
    n = N(1.25); t = T(n); k = np.linspace(0, 1, n)
    drone = lp(saw(xs(55, 440, n), n), 3000) * (0.3 + 0.7 * k)
    harm = sine(xs(220, 1760, n), n) * k ** 2 * 0.5
    nz = sweep_bp(wn(n, 281), 200, 2000, 1000, 9000) * k ** 1.5 * 0.6
    return (drone + harm + nz) * np.minimum(t / 0.05, 1) * np.minimum((1.25 - t) / 0.02, 1)


def lasercannon_beam():
    n = N(1.2); t = T(n)
    crack = hp(wn(n, 291), 1500) * ad(n, 0.0005, 0.03)
    beam = (sine(220, n) + 0.5 * sine(440, n) + 0.3 * sq(110, n, 0.3)) * lin([(0, 0), (0.02, 1), (0.55, 0.9), (0.75, 0)], n)
    sizzle = bp(wn(n, 292), 2500, 10000) * lin([(0, 0), (0.02, 0.8), (0.6, 0.5), (1.2, 0)], n) * 0.5
    sub = sine(xs(80, 40, n), n) * ad(n, 0.002, 0.3) * 0.6
    return rev(drive(mixn(crack, beam * 0.8, sizzle, sub), 1.6), 0.7, 0.25)


def big_boom(sec, f0, f1, tone, seed, rumble=0.6, bright=0.4):
    n = N(sec); t = T(n)
    sub = sine(xs(f0, f1, n), n) * ad(n, 0.003, sec * 0.25)
    burst = lp(wn(n, seed), tone) * ad(n, 0.002, sec * 0.12)
    crackle = bp(wn(n, seed + 1), 1200, 6000) * ad(n, 0.001, sec * 0.05) * 0.6
    rumble_ = lp(wn(n, seed + 2), 160) * lin([(0, 0), (sec * 0.1, 1), (sec, 0)], n) * rumble
    return rev(drive(mixn(sub * 1.3, burst, crackle, rumble_), 1.9), min(sec, 1.2), 0.28, bright)


def autocannon(v):
    n = N(0.5); x = crack(n, 300 + v * 3, tone=2600 + 200 * v, body=(300, 70), bdec=0.09, ndec=0.045, punch=1.2)
    return rev(mixn(x, sine(xs(140, 50, n), n) * ad(n, 0.002, 0.08) * 0.5), 0.4, 0.18)


def flak_fire():
    n = N(0.55); x = crack(n, 320, tone=2200, body=(240, 60), bdec=0.1, ndec=0.05, punch=1.2)
    return rev(x, 0.4, 0.2)


def flak_burst():
    n = N(0.8); x = big_boom(0.8, 200, 60, 2600, 330, rumble=0.2, bright=0.7)
    whistle = sine(xs(2800, 1400, n), n) * ad(n, 0.001, 0.08) * 0.25
    return mixn(x, pad(whistle, 0.0))


def shield_hum(up=True):
    n = N(0.5); t = T(n); f = xs(180, 420, n) if up else xs(420, 160, n)
    x = (sine(f, n) + 0.5 * sine(f * 2, n) + 0.3 * sine(f * 3.01, n)) * (0.7 + 0.3 * np.sin(2 * np.pi * 30 * t))
    nz = bp(wn(n, 341), 800, 4000) * 0.3
    env = lin([(0, 0), (0.04, 1), (0.35, 0.8), (0.5, 0)], n) if up else lin([(0, 0), (0.02, 1), (0.5, 0)], n)
    return (x + nz) * env


def bubble(up=True):
    n = N(0.95); t = T(n)
    notes = [220, 277, 330, 440] if up else [440, 330, 277, 220]
    x = np.zeros(n)
    for i, f in enumerate(notes):
        a = N(0.12 * i); e = np.zeros(n); e[a:] = ad(n - a, 0.02, 0.35)
        x += (sine(f * (1 + 0.003 * np.sin(2 * np.pi * 5 * t)), n) + 0.4 * sine(f * 2, n)) * e * (0.9 - 0.1 * i)
    shimmer = bp(wn(n, 351), 3000, 9000) * lin([(0, 0), (0.3, 0.4), (0.95, 0)], n) * 0.4
    return mixn(x * 0.5, shimmer)


def repair_chime():
    n = N(0.7); x = np.zeros(n)
    for i, f in enumerate([523.25, 659.25, 783.99]):
        a = N(0.09 * i); e = np.zeros(n); e[a:] = ad(n - a, 0.004, 0.22); x += (sine(f, n) + 0.3 * sine(f * 2, n)) * e * 0.4
    return x + lp(wn(n, 361), 600) * ad(n, 0.005, 0.05) * 0.2


def repair_loop():
    n = N(2.0); t = T(n); x = np.zeros(n)
    for i, f in enumerate([523.25, 659.25, 783.99, 1046.5]):
        a = N(0.5 * i); e = np.zeros(n); e[a:] = ad(n - a, 0.004, 0.25); x += sine(f, n) * e * 0.3
    hum = (sine(130.8, n) + 0.5 * sine(261.6, n)) * (0.8 + 0.2 * np.sin(2 * np.pi * 4 * t)) * 0.25
    return loopify(x + hum + bp(wn(n, 371), 2000, 6000) * 0.06, 0.2)


def decoy_pop():
    n = N(0.6)
    pop = lp(wn(N(0.08), 381), 3000) * ad(N(0.08), 0.0005, 0.015)
    x = shots(pop, [0.0, 0.15, 0.3], [1.0, 0.9, 0.8])
    fizz = bp(wn(n, 382), 2000, 9000) * lin([(0, 0), (0.05, 0.6), (0.6, 0)], n) * 0.5
    return mixn(x, fizz)


# ================================================================ impacts
def hit_metal(v):
    n = N(0.32); fr = [1600 + 150 * v, 2450 + 200 * v, 3700 + 100 * v, 5200]
    x = metal(n, fr, [0.09, 0.07, 0.05, 0.03], [1, 0.7, 0.5, 0.3], seed=20 + v) * ad(n, 0.0, 0.12)
    return mixn(x, hp(wn(n, 400 + v), 2500) * ad(n, 0.0005, 0.008) * 0.7, lp(wn(n, 410 + v), 900) * ad(n, 0.001, 0.02) * 0.5)


def hit_ground(v):
    n = N(0.45); x = lp(wn(n, 420 + v), 1100 + 200 * v) * ad(n, 0.002, 0.06)
    thud = sine(xs(170, 60, n), n) * ad(n, 0.002, 0.07) * 0.6
    grit = bp(wn(n, 430 + v), 2000, 7000) * ad(n, 0.004, 0.12) * 0.3
    return mixn(drive(x, 1.4), thud, grit)


def mech_death():
    n = N(3.4); boom = big_boom(2.4, 70, 22, 2400, 500, rumble=0.9, bright=0.35)
    pops = shots(lp(wn(N(0.3), 510), 2000) * ad(N(0.3), 0.001, 0.05), [0.35, 0.62, 0.95, 1.3], [0.6, 0.5, 0.55, 0.4])
    debris = shots(metal(N(0.5), [1400, 2200, 3100], [0.15, 0.1, 0.08], seed=9) * ad(N(0.5), 0, 0.2), [0.5, 0.8, 1.1, 1.5, 1.9], [0.4, 0.3, 0.35, 0.25, 0.2])
    hiss = bp(wn(n, 511), 500, 3000) * lin([(0, 0), (0.4, 0.3), (3.4, 0)], n) * 0.3
    return mixn(boom, pops, debris, hiss)


def stagger_clang():
    n = N(0.9); bell = metal(n, [620, 1240, 1660, 2480, 3300], [0.5, 0.35, 0.25, 0.15, 0.1], [1, 0.7, 0.6, 0.4, 0.3], seed=10) * ad(n, 0, 0.5)
    crunch = lp(wn(n, 520), 2500) * ad(n, 0.001, 0.05)
    sub = sine(xs(90, 40, n), n) * ad(n, 0.002, 0.12) * 0.6
    return rev(mixn(drive(bell, 1.5), crunch * 0.8, sub), 0.5, 0.2)


def drop_entry():
    n = N(2.6); t = T(n)
    roar = sweep_bp(wn(n, 530), 150, 600, 900, 4000) * lin([(0, 0), (0.6, 0.7), (2.0, 1), (2.6, 0)], n)
    sub = sine(xs(30, 70, n), n) * lin([(0, 0), (1.0, 0.6), (2.6, 0)], n)
    whistle = sine(xs(600, 2400, n), n) * lin([(0, 0), (0.8, 0.1), (2.3, 0.3), (2.6, 0)], n)
    return mixn(roar, sub, whistle)


def boss_roar():
    n = N(2.6); t = T(n)
    f = xs(42, 36, n) * (1 + 0.02 * np.sin(2 * np.pi * 7 * t))
    growl = lp(saw(f, n), 900) + 0.6 * lp(sq(f * 1.5, n, 0.3), 700)
    formant = bp(growl, 280, 420) * 2 + bp(growl, 650, 900) * 1.2 + growl * 0.4
    env = lin([(0, 0), (0.15, 1), (1.6, 0.9), (2.6, 0)], n)
    breath = bp(wn(n, 540), 400, 3000) * env * 0.35
    sub = sine(xs(55, 38, n), n) * env * 0.6
    return rev(drive(mixn(formant * env, breath, sub), 2.5), 1.1, 0.3, 0.35)


def capture_tick():
    n = N(0.18); return (sine(1480, n) + 0.3 * sine(2960, n)) * ad(n, 0.002, 0.05) + hp(wn(n, 550), 4000) * ad(n, 0.0005, 0.004) * 0.3


def capture_done():
    n = N(1.6); x = np.zeros(n)
    for i, f in enumerate([392, 523.25, 659.25, 783.99]):
        a = N(0.1 * i); e = np.zeros(n); e[a:] = ad(n - a, 0.01, 0.5); x += (sine(f, n) + 0.3 * sine(f * 2, n) + 0.2 * saw(f, n)) * e * 0.4
    return rev(x + lp(wn(n, 560), 500) * ad(n, 0.004, 0.06) * 0.3, 0.8, 0.3, 0.6)


def wave_start():
    n = N(2.0); t = T(n)
    horn = (saw(xs(150, 150, n), n) + saw(151.5, n) + 0.5 * saw(225, n)) / 2.5
    horn = lp(horn, 1800) * lin([(0, 0), (0.03, 1), (0.7, 1), (0.8, 0), (0.9, 0), (0.93, 1), (1.6, 1), (2.0, 0)], n)
    hit = big_boom(1.0, 120, 40, 1600, 570, rumble=0.4)
    return mixn(horn * 0.8, hit[:n] * 0.7)


def bounty():
    n = N(1.1); x = np.zeros(n)
    for i, f in enumerate([1046.5, 1318.5, 1568, 2093]):
        a = N(0.06 * i); e = np.zeros(n); e[a:] = ad(n - a, 0.002, 0.3); x += sine(f, n) * e * 0.3
    hit = sine(xs(140, 50, n), n) * ad(n, 0.003, 0.15) * 0.8 + lp(wn(n, 580), 1200) * ad(n, 0.001, 0.05) * 0.5
    return rev(mixn(x, drive(hit, 1.5)), 0.6, 0.25)


# ================================================================ pilot-only tones (UI, not in the world)
def ui_tone(seq, gap=0.0):
    """seq: list of (freq, seconds, duty); played back to back with `gap` between"""
    parts = []
    for f, s, d in seq:
        parts.append(blip(f, s, d)); parts.append(np.zeros(N(gap)))
    return np.concatenate(parts)


def define_ui():
    sfx('ui_lock1', 'ui', ui_tone([(880, 0.07, 0.5)]), note='soft lock acquired: one short beep')
    sfx('ui_lock2', 'ui', ui_tone([(1046, 0.06, 0.5), (1046, 0.06, 0.5)], 0.05), note='hard lock stage 2: two beeps')
    sfx('ui_lock3', 'ui', ui_tone([(1318, 0.05, 0.5)] * 3, 0.04) + 0.0, note='hard lock stage 3: three fast beeps (locked)')
    n = N(0.5); t = T(n)
    warn = blip(np.where((t * 8).astype(int) % 2 == 0, 1200.0, 900.0), 0.5, 0.5, 0.002, 0.0, 1.0, 0.01)
    sfx('ui_locked_warn', 'ui', warn, note='someone has locked you: 0.5 s two-tone warble, repeat while locked')
    n = N(0.4); t = T(n); gate = (np.sin(2 * np.pi * 10 * t) > 0)
    sfx('ui_launch_warn', 'ui', blip(1500, 0.4, 0.25, 0.002, 0, 1, 0.005) * gate, note='missile launched at you: 10 Hz chopped 1.5 kHz, repeat every 0.5 s')
    n = N(0.3); t = T(n); gate = (np.sin(2 * np.pi * 20 * t) > 0)
    sfx('ui_msl_close', 'ui', blip(2000, 0.3, 0.25, 0.002, 0, 1, 0.005) * gate, note='missile within 0.5 s: faster, higher chop')
    n = N(0.07)
    sfx('ui_hit', 'ui', (sine(2200, n) + 0.4 * sine(3300, n)) * ad(n, 0.001, 0.02) + hp(wn(n, 600), 5000) * ad(n, 0.0005, 0.003) * 0.5, note='hit marker tick')
    kill = ui_tone([(880, 0.08, 0.25), (1320, 0.08, 0.25), (1760, 0.22, 0.25)], 0.01)
    sfx('ui_kill', 'ui', kill, note='kill confirmed: rising three-note')
    n = N(0.5); t = T(n)
    sfx('ui_stagger', 'ui', drive(lp(sq(xs(140, 70, n), n, 0.3), 1500), 3) * ad(n, 0.002, 0.2) * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 18 * t))), note='you are staggered: low chopped buzz')
    sfx('ui_low_ap', 'ui', ui_tone([(440, 0.14, 0.5), (440, 0.14, 0.5)], 0.1), note='AP under 25 %: two low beeps, repeat every 2 s')
    n = N(0.4)
    sfx('ui_en_empty', 'ui', drive(blip(xs(600, 180, n), 0.4, 0.3, 0.002, 0.0, 1.0, 0.03), 1.5), note='EN stalled: falling buzz')
    sfx('ui_en_ok', 'ui', blip(xs(420, 840, N(0.28)), 0.28, 0.5, 0.002, 0.0, 1.0, 0.04), note='EN recovered: rising chirp')
    n = N(0.16)
    sfx('ui_ready', 'ui', hp(wn(n, 610), 3000) * ad(n, 0.0005, 0.005) * 0.6 + sine(1000, n) * lin([(0, 0), (0.03, 0), (0.035, 0.8), (0.16, 0)], n), note='weapon ready / reloaded: click + blip')
    n = N(0.9); t = T(n)
    sfx('ui_spawn', 'ui', (sine(xs(200, 800, n), n) + 0.5 * sine(xs(400, 1600, n), n)) * lin([(0, 0), (0.1, 0.6), (0.6, 1), (0.9, 0)], n) + bp(wn(n, 620), 2000, 8000) * lin([(0, 0), (0.6, 0.3), (0.9, 0)], n), note='mech powered up: rising sweep')
    sfx('ui_capture', 'ui', ui_tone([(1480, 0.07, 0.5)]), note='capture progress tick (pilot side)')
    # round / garage (also flat, heard by everyone the adapter sends them to)
    n = N(3.0); t = T(n)
    riser = sweep_bp(wn(n, 630), 200, 3000, 800, 9000) * lin([(0, 0), (1.3, 0.8), (1.4, 0)], n)
    hitn = N(1.6); chord = sum(lp(saw(f, hitn), 2500) for f in [82.4, 123.5, 164.8, 246.9]) / 4 * ad(hitn, 0.005, 0.5)
    drum = (sine(xs(120, 40, hitn), hitn) * ad(hitn, 0.002, 0.25) + lp(wn(hitn, 631), 1500) * ad(hitn, 0.001, 0.08)) * 0.9
    sting = mixn(riser, np.concatenate([np.zeros(N(1.4)), rev(drive(chord + drum, 1.8), 0.9, 0.3)]))
    sfx('ui_round_start', 'ui', sting, note='round intro sting: riser into a power-chord hit')
    sfx('ui_podium', 'ui', podium_fanfare(), note='podium fanfare (5 s)')
    sfx('ui_garage_move', 'ui', ui_tone([(660, 0.04, 0.25)]), note='garage cursor moved')
    sfx('ui_garage_ok', 'ui', ui_tone([(880, 0.06, 0.25), (1320, 0.12, 0.25)], 0.01), note='garage confirm')
    sfx('ui_garage_deny', 'ui', drive(blip(xs(300, 200, N(0.22)), 0.22, 0.5, 0.002, 0.0, 1.0, 0.03), 1.3), note='garage deny / cannot afford')


def podium_fanfare():
    """5 s brass-like fanfare: detuned saws through a low-pass, a drum roll in, a cymbal-ish wash"""
    bpm = 132; b = 60 / bpm; n = N(5.0)
    notes = [(0, 0.5, [67, 71, 74]), (0.5, 0.5, [67, 71, 74]), (1.0, 1.0, [72, 76, 79]), (2.0, 0.5, [69, 72, 76]), (2.5, 0.5, [71, 74, 79]),
             (3.0, 2.0, [72, 76, 79, 84])]
    x = np.zeros(n)
    for t0, dur, ch in notes:
        m = N(dur * b + 0.3); e = S.env_adsr(dur * b, 0.01, 0.1, 0.8, 0.25, n=m)
        tone = sum(lp(S.saw(S.midi_hz(p) * d, m, rng.random()), 3000) for p in ch for d in (0.997, 1.003)) / (2 * len(ch))
        S.add(x, tone * e, N(t0 * b))
    roll = shots(lp(wn(N(0.06), 640), 3000) * ad(N(0.06), 0.001, 0.02), [i * 0.07 for i in range(8)], [0.3 + 0.1 * i for i in range(8)])
    hit = (sine(xs(130, 45, N(1)), N(1)) * ad(N(1), 0.002, 0.2) + lp(wn(N(1), 641), 1200) * ad(N(1), 0.001, 0.08)) * 0.9
    wash = bp(wn(n, 642), 3000, 11000) * lin([(0, 0), (3.0, 0), (3.02, 0.5), (5.0, 0)], n) * 0.4
    return rev(mixn(x * 0.8, roll, np.concatenate([np.zeros(N(3.0)), hit]), wash), 1.2, 0.3, 0.6)


# ================================================================ music (synth.py instruments)
def chord_notes(root, kind):
    iv = {'m': (0, 3, 7), 'M': (0, 4, 7), 'm7': (0, 3, 7, 10), 'sus': (0, 5, 7), 'M7': (0, 4, 7, 11)}[kind]
    return [root + i for i in iv]


def wrap_loop(x, n_loop):
    """x longer than n_loop (instrument tails): fold the overhang onto the start, cut to n_loop"""
    x = np.asarray(x); tail = min(len(x) - n_loop, n_loop)
    if tail > 0: x[:tail] += x[n_loop:n_loop + tail]
    x = x[:n_loop]
    return x / (np.abs(x).max() + 1e-9) * dbv(PEAK_DB)          # the fold can add a little: back to -1 dBFS


def music_garage():
    """'Hangar Lights', 96 bpm E minor, 48 bars = 120 s: strings pad, slow electronic bass, sparse lead, soft beat"""
    bpm = 96; beat = 60 / bpm; bar = 4 * beat; bars = 48; n_loop = N(bars * bar); n = n_loop + N(3.0)
    prog_a = [(52, 'm'), (48, 'M'), (55, 'M'), (50, 'M')]            # Em C G D
    prog_b = [(57, 'm'), (52, 'm'), (48, 'M'), (47, 'M')]            # Am Em C B
    chords = []
    for sec_i in range(6):
        prog = prog_b if sec_i in (2, 3) else prog_a
        for root, kind in prog: chords.append((root, kind))         # 24 chords x 2 bars
    pad_ev = []; bass_ev = []; lead_ev = []; arp_ev = []; drums = []; kicks = []
    for ci, (root, kind) in enumerate(chords):
        t0 = ci * 2 * bar
        pad_ev.append((t0, 2 * bar, chord_notes(root, kind) + [root + 12], 0.7, {}))
        broot = root - 24 if root >= 52 else root - 12
        if ci < 4:
            bass_ev.append((t0, 2 * bar * 0.95, broot, 0.8, {}))
        else:
            for k in range(8): bass_ev.append((t0 + k * beat, beat * 0.5, broot if k % 4 != 3 else broot + 7, 0.75 if k % 2 == 0 else 0.55, {}))
        if 8 <= ci < 24:
            tones = chord_notes(root + 12, kind)
            for k in range(16):
                arp_ev.append((t0 + k * beat / 2, beat / 2 * 0.8, tones[[0, 2, 1, 2][k % 4]] + (12 if k >= 8 else 0), 0.45, {}))
        if ci >= 4:
            for k in range(2):
                tb = t0 + k * bar
                drums.append((tb, 'kick', 0.9)); kicks.append(tb); drums.append((tb + 2 * beat, 'kick', 0.7)); kicks.append(tb + 2 * beat)
                if ci >= 8: drums.append((tb + 2 * beat, 'clap', 0.5))
                for h in range(8): drums.append((tb + h * beat / 2, 'hat', 0.35 if h % 2 else 0.5))
    melody = [(0, 2, 76), (2, 1, 74), (3, 3, 71), (8, 2, 72), (10, 1, 74), (11, 3, 76), (16, 1.5, 79), (17.5, 1.5, 78), (19, 3, 74), (24, 2, 71), (26, 2, 72), (28, 4, 74)]
    for off in (16 * bar, 32 * bar + 16 * bar - 16 * bar):
        for tb, dur, p in melody:
            if off == 16 * bar or tb < 28:
                lead_ev.append((off + tb * beat, dur * beat * 0.9, p, 0.7, {}))
    kit = S.Drums(seed=5, style='electronic').render(drums, n)
    m = S.Mixer(n, S.reverb_ir(seed=11, length=2.4, predelay=0.03)); m.pump = S.pump_curve(kicks, n, 0.2, 0.18)
    m.add(S.Pad(seed=3, mode='strings', voices=5, detune=10).render(pad_ev, n), -13, 0.0, -9, 0.3)
    m.add(S.Bass(seed=1, electronic=True, drive=1.8, sub=0.7).render(bass_ev, n), -7, 0.0, -100, 0.5)
    m.add(S.Lead(seed=2, voices=2, detune=6, vib_depth=0.2, drive=1.2, delay=beat * 0.75, fb=0.45, dmix=0.4, square=0.6).render(lead_ev, n), -11, 0.1, -10)
    m.add(S.Lead(seed=8, voices=1, detune=0, vib_depth=0.0, drive=1.0, delay=beat * 0.75, fb=0.35, dmix=0.3, square=1.0).render(arp_ev, n), -17, -0.3, -12)
    for g, x in kit.items(): m.add(x, {'kick': -5, 'snare': -10, 'hat': -16}.get(g, -14), 0.0, -18 if g != 'kick' else -100)
    out = m.master(comp_thr=-16, ratio=2.5, drive_db=1.5, peak_dbfs=PEAK_DB, eq=((200, -1.5, 1.0), (3000, 1.0, 0.8)))
    return wrap_loop(out, n_loop), bars * bar


def music_battle():
    """'Ironframe Overdrive', 160 bpm E minor, 120 bars = 180 s: palm-muted power-chord riffs, driving kit, lead hooks, a bridge"""
    bpm = 160; beat = 60 / bpm; bar = 4 * beat; bars = 120; n_loop = N(bars * bar); n = n_loop + N(3.0)
    E, G, A, B, C, D = 40, 43, 45, 47, 48, 50
    def pc(p): return [p, p + 7]
    # riffs: per bar, list of (eighth index, eighths, pitches, mute)
    riff_a = [(0, 1, pc(E), 1), (1, 1, pc(E), 1), (2, 1, pc(E), 1), (3, 1, pc(G), 0), (4, 1, pc(E), 1), (5, 1, pc(E), 1), (6, 2, pc(A), 0)]
    riff_a2 = [(0, 1, pc(E), 1), (1, 1, pc(E), 1), (2, 1, pc(E), 1), (3, 1, pc(G), 0), (4, 1, pc(E), 1), (5, 1, pc(E), 1), (6, 1, pc(D), 0), (7, 1, pc(C), 0)]
    riff_b = [(0, 2, pc(D), 0), (2, 1, pc(D), 1), (3, 1, pc(C), 0), (4, 2, pc(C), 0), (6, 1, pc(C), 1), (7, 1, pc(B), 0)]
    riff_b2 = [(0, 2, pc(G), 0), (2, 1, pc(G), 1), (3, 1, pc(A), 0), (4, 2, pc(A), 0), (6, 1, pc(B), 1), (7, 1, pc(B), 1)]
    chorus = [[(0, 4, pc(C), 0), (4, 4, pc(G), 0)], [(0, 4, pc(D), 0), (4, 2, pc(E), 0), (6, 2, pc(E), 1)],
              [(0, 4, pc(C), 0), (4, 4, pc(G), 0)], [(0, 4, pc(D), 0), (4, 4, pc(B), 0)]]
    intro = [(k, 1, pc(E), 1) for k in range(8)]
    build = [(0, 1, pc(E), 1), (1, 1, pc(E), 1), (2, 1, pc(E), 1), (3, 1, pc(E), 1), (4, 1, pc(G), 1), (5, 1, pc(G), 1), (6, 1, pc(A), 1), (7, 1, pc(A), 1)]
    sections = ['intro', 'va', 'va', 'ch', 'vb', 'vb', 'ch', 'bridge', 'build', 'ch', 'ch', 'va', 'va', 'ch', 'outro']
    gtr = []; bass = []; lead = []; pad_ev = []; drums = []; kicks = []
    hook = [(0, 1, 76), (1, 1, 79), (2, 2, 83), (4, 1, 81), (5, 1, 79), (6, 2, 76), (8, 1, 74), (9, 1, 76), (10, 2, 79), (12, 4, 78),
            (16, 1, 76), (17, 1, 79), (18, 2, 83), (20, 1, 84), (21, 1, 83), (22, 2, 81), (24, 2, 79), (26, 2, 78), (28, 4, 74)]
    solo = [(0, 3, 71), (3, 1, 74), (4, 2, 76), (6, 2, 74), (8, 4, 71), (12, 2, 69), (14, 2, 67), (16, 3, 74), (19, 1, 76), (20, 2, 79), (22, 2, 78), (24, 6, 76), (30, 2, 74)]
    for si, sec_name in enumerate(sections):
        t_s = si * 8 * bar
        for bi in range(8):
            tb = t_s + bi * bar
            if sec_name == 'intro': r = intro
            elif sec_name == 'va': r = riff_a if bi % 2 == 0 else riff_a2
            elif sec_name == 'vb': r = riff_b if bi % 2 == 0 else riff_b2
            elif sec_name == 'ch': r = chorus[bi % 4]
            elif sec_name == 'build': r = build
            elif sec_name == 'outro': r = riff_a if bi < 7 else [(0, 2, pc(E), 0), (2, 2, pc(G), 0), (4, 2, pc(A), 0), (6, 2, pc(B), 0)]
            else: r = []
            for e8, dur8, pcs, mute in r:
                t0 = tb + e8 * beat / 2; dur = dur8 * beat / 2
                gtr.append((t0, dur * (0.55 if mute else 0.95), pcs, 0.95 if not mute else 0.8, {'mute': bool(mute)}))
                bass.append((t0, dur * 0.9, pcs[0] - 12, 0.9, {}))
            if sec_name == 'bridge':
                root = [E, C, G, D][bi // 2]
                pad_ev.append((tb, bar * (2 if bi % 2 == 0 else 0.999), chord_notes(root + 12, 'M' if root in (C, G, D) else 'm') + [root + 24], 0.7, {})) if bi % 2 == 0 else None
                bass.append((tb, bar * 0.9, root - 12, 0.8, {}))
            # drums
            if sec_name in ('intro',):
                drums.append((tb, 'kick', 0.9)); kicks.append(tb); drums.append((tb + 2 * beat, 'kick', 0.9)); kicks.append(tb + 2 * beat)
                for h in range(8): drums.append((tb + h * beat / 2, 'hat', 0.5))
                if bi >= 6: drums += [(tb + k * beat / 2, 'snare', 0.4 + 0.07 * k) for k in range(8)]
                if bi == 5: drums.append((tb, 'riser', 0.8))
            elif sec_name == 'bridge':
                drums.append((tb, 'kick', 0.8)); kicks.append(tb); drums.append((tb + 2 * beat, 'snare', 0.7))
                for h in range(4): drums.append((tb + h * beat, 'ride', 0.5))
            elif sec_name == 'build':
                for k in range(4): drums.append((tb + k * beat, 'kick', 0.9)); kicks.append(tb + k * beat)
                drums += [(tb + k * beat / 2, 'tom_l' if k % 2 else 'tom_m', 0.6) for k in range(8)] if bi >= 4 else [(tb + 2 * beat, 'snare', 0.8)]
                if bi == 4: drums.append((tb, 'riser', 1.0))
            else:
                for k in range(4):
                    drums.append((tb + k * beat, 'kick', 0.95)); kicks.append(tb + k * beat)
                    if k % 2 == 1: drums.append((tb + k * beat, 'snare', 0.9))
                drums += [(tb + h * beat / 2, 'hat' if sec_name != 'ch' else 'ohat', 0.55 if h % 2 else 0.7) for h in range(8)]
                if sec_name == 'ch' and bi % 4 == 0: drums.append((tb, 'crash', 0.8))
                if bi == 7: drums += [(tb + 3 * beat + k * beat / 4, 'snare', 0.6 + 0.1 * k) for k in range(4)]
        if sec_name == 'ch' or (sec_name == 'bridge'):
            line = hook if sec_name == 'ch' else solo
            for tb, dur, p in line:
                if sec_name == 'ch' and si in (3,): continue           # the first chorus is guitar only
                lead.append((t_s + tb * beat, dur * beat * 0.9, p, 0.85, {}))
    kit = S.Drums(seed=4).render(drums, n)
    m = S.Mixer(n, S.reverb_ir(seed=7, length=1.4)); m.pump = S.pump_curve(kicks, n, 0.22, 0.12)
    m.add(S.Guitar(seed=1, drive=9, tone=0.55).render(gtr, n), -4.5, -0.4, -20, 0.25)
    m.add(S.Guitar(seed=2, drive=9, tone=0.45).render(gtr, n), -4.5, 0.4, -20, 0.25)
    m.add(S.Bass(seed=1, drive=2.5).render(bass, n), -4, 0.0, -100, 0.45)
    m.add(S.Lead(seed=2, voices=3, detune=9, delay=beat * 1.5, fb=0.35, dmix=0.3).render(lead, n), -7, 0.08, -12)
    m.add(S.Pad(seed=3, mode='strings').render(pad_ev, n), -13, 0.0, -8, 0.3)
    for g, x in kit.items(): m.add(x, {'kick': -1.5, 'snare': -3, 'hat': -9, 'cym': -8, 'tom': -5}.get(g, -8), 0.0, -16 if g != 'kick' else -100)
    out = m.master(comp_thr=-14, ratio=3.0, drive_db=3.0, peak_dbfs=PEAK_DB)
    return wrap_loop(out, n_loop), bars * bar


# ================================================================ the catalogue
# ================================================================ heavy rebuild: stock CS2 layers + synthesised sub/tails
# Each weapon/impact/explosion event = stock CS2 .vsnd tracks (played together, pitched down by the event's `pitch`) + one
# synthesised track (sub-bass thump, distant tail, metal ring, debris).  The synth WAV is pre-warped by the same pitch so that,
# played at the event pitch, it ends up exactly as designed here (sub 25-100 Hz etc.).
def prewarp(x, p):
    if abs(p - 1) < 1e-3: return x
    from fractions import Fraction
    f = Fraction(p).limit_denominator(50)
    return signal.resample_poly(x, f.numerator, f.denominator)


def slow(n, seed, fc):
    """slow random modulation in -1..1"""
    x = lp(wn(n, seed), fc, 1); return x / (np.abs(x).max() + 1e-9)


def sub_hit(sec, f0, f1, dec, k=1.5, h2=0.3, a=0.002):
    n = N(sec); f = xs(f0, f1, n)
    return drive((sine(f, n) + h2 * sine(2 * f, n)) * ad(n, a, dec) * 1.4, k)


def nzb(sec, seed, lo=None, hi=None, dec=0.05, a=0.0005):
    n = N(sec); x = wn(n, seed)
    if lo and hi: x = bp(x, lo, hi)
    elif hi: x = lp(x, hi)
    elif lo: x = hp(x, lo)
    return x * ad(n, a, dec)


def dist_tail(sec, seed, hi0=1100, hi1=140, lo=28, delay=0.03):
    n = N(sec); x = sweep_bp(wn(n, seed), lo, lo * 1.01, hi0, hi1, blocks=24)
    return x * lin([(0, 0), (delay, 0), (delay + 0.06, 1), (sec * 0.4, 0.5), (sec, 0)], n)


def ring(sec, seed, base=1.0, lvl=1.0):
    n = N(sec); fr = [170, 288, 455, 760, 1210, 1980, 3100]
    dec = [sec * k for k in (.55, .45, .35, .25, .18, .12, .08)]
    x = metal(n, [f * base for f in fr], dec, [1, .8, .7, .5, .4, .3, .2], seed) * lvl
    x[:N(0.0008)] *= np.linspace(0, 1, N(0.0008)); return x


def clatter(sec, seed, dens=50, lo=700, hi=6000, power=1.8):
    n = N(sec); r = np.random.default_rng(seed); base = bp(wn(n, seed + 1), lo, hi); out = np.zeros(n)
    for t0 in np.sort(r.random(int(dens * sec)) ** power * sec):
        a = N(t0); l = min(N(0.004 + 0.012 * r.random()), n - a)
        if l < 8: continue
        out[a:a + l] += base[a:a + l] * np.exp(-np.arange(l) / (SR * 0.004)) * (0.3 + 0.7 * r.random())
    return out * np.exp(-T(n) / (sec * 0.6))


def servo(sec, f0, f1, lvl=1.0, pk=0.35):
    n = N(sec); f = xs(f0, f1, n)
    x = sine(f, n) + 0.4 * sine(f * 2.01, n) + 0.25 * fm(f * 3, f * 0.5, 1.5, n)
    return x * lin([(0, 0), (sec * pk, 1), (sec, 0)], n) * lvl


def whoosh(sec, seed, lo0, lo1, hi0, hi1, pk=0.3):
    n = N(sec)
    return sweep_bp(wn(n, seed), lo0, lo1, hi0, hi1) * lin([(0, 0), (sec * pk, 1), (sec, 0)], n)


def at(x, t0, total=None):
    """x delayed by t0 s, padded/cut to `total` s"""
    out = np.concatenate([np.zeros(N(t0)), x])
    return out if total is None else np.pad(out, (0, max(0, N(total) - len(out))))[:N(total)]


def wrap_add(out, x, start):
    """add x into the ring buffer `out` at `start`, wrapping (seamless loops)"""
    n = len(out)
    for i in range(0, len(x), n):
        seg = x[i:i + n]; s = (start + i) % n
        k = min(len(seg), n - s); out[s:s + k] += seg[:k]
        if k < len(seg): out[:len(seg) - k] += seg[k:]


def H(key, cat, variants, tracks, p, level=-4.0, vol=None, **kw):
    """a layered event: stock `tracks` (list of lists of .vsnd paths) at pitch p + the synth variants"""
    sfx(key, cat, *variants, stock=dict(tracks=tracks, pitch=p, level=level), vol=vol, **kw)


W = 'weapons/'
M249 = [W + 'm249/m249_0%d' % i for i in (1, 2, 3)]
NEG = [W + 'negev/negev_01', W + 'negev/negev_02', W + 'negev/negev_clean_01', W + 'negev/negev_clean_02']
HE = [W + 'hegrenade/hegrenade_detonate_02', W + 'hegrenade/hegrenade_detonate_03']
BOX = ['physics/metal/metal_box_impact_hard%d' % i for i in (1, 2, 3)]
BARREL = ['physics/metal/metal_barrel_impact_hard%d' % i for i in (1, 2, 3)]
CONC = ['physics/concrete/concrete_impact_hard%d' % i for i in (1, 2, 3)]
BULLETM = ['physics/metal/bullet_metal_solid_0%d' % i for i in range(1, 7)]


# ---- loops: turbine-shaped boosters (tone frequencies are whole cycles per loop, so the cross-fade only blends noise)
def turbine_loop(kind):
    n = N(3.2); t = T(n); L = (n - N(0.25)) / SR; q = lambda f: max(1, round(f * L)) / L
    wf, rf, bands = {'light': (1900, 66, ((300, 1200, .5), (1200, 4500, .6), (4500, 11000, .25))),
                     'medium': (1100, 52, ((180, 900, .7), (900, 3500, .5), (3500, 9000, .18))),
                     'heavy': (640, 38, ((100, 600, .85), (600, 2500, .45), (2500, 7000, .12)))}[kind]
    flut = 1 + 0.16 * slow(n, 70 + len(kind), 14)
    roar = sum(bp(wn(n, 71 + i + len(kind)), lo, hi) * g for i, (lo, hi, g) in enumerate(bands)) * flut * (0.9 + 0.1 * np.sin(2 * np.pi * q(7) * t))
    whine = (sine(q(wf) * (1 + 0.012 * np.sin(2 * np.pi * q(0.7) * t)), n) * .22 + sine(q(wf * 2.01), n) * .1 + sine(q(wf * 3.02), n) * .05) * (0.8 + 0.2 * np.sin(2 * np.pi * q(1.3) * t))
    rumble = (sine(q(rf), n) * .7 + sine(q(rf * 2), n) * .3 + lp(wn(n, 79), 110) * 1.1) * (0.75 + 0.25 * np.sin(2 * np.pi * q(5.5) * t))
    burble = lp(wn(n, 78), 260) * 0.7 * (0.5 + 0.5 * np.sin(2 * np.pi * q(11) * t))
    return loopify(drive((roar * .55 + whine + rumble * .9 + burble) * 0.7, 1.4), 0.25)


def hover_h():
    n = N(2.6); t = T(n); L = (n - N(0.3)) / SR; q = lambda f: round(f * L) / L
    x = (bp(wn(n, 41), 160, 1300) * (0.85 + 0.15 * np.sin(2 * np.pi * q(14) * t)) * 0.6 + sine(q(46), n) * .5 + sine(q(92), n) * .22
         + lp(wn(n, 42), 100) * .8 + sine(q(610), n) * .03)
    return loopify(drive(x * .8, 1.3), 0.3)


def boost_on_h(kind):
    f0, f1, spool, sec = {'light': (120, 52, 1500, 1.0), 'medium': (95, 40, 1000, 1.25), 'heavy': (75, 30, 640, 1.5)}[kind]
    n = N(sec)
    kick = sub_hit(.55, f0, f1, .13)
    roar = whoosh(sec, 21, 180, 120, 5000, 1100, .12) * 0.9 + lp(wn(n, 24), 240) * lin([(0, 0), (.08, 1), (sec * .6, .6), (sec, 0)], n) * .8
    whine = sine(xs(spool * .3, spool, n), n) * lin([(0, 0), (sec * .5, .35), (sec * .8, .2), (sec, 0)], n) * .35
    ign = nzb(.12, 22, 1800, 9000, .035, .0003) * 1.2
    return mixn(kick * 1.3, roar, whine, ign, clatter(.4, 25, 120, 1200, 6000) * .35)


def quick_boost_h():
    n = N(0.85)
    blast = sweep_bp(wn(n, 31), 500, 180, 9000, 2200) * lin([(0, 0), (.004, 1), (.12, .85), (.85, 0)], n) * 1.1
    air = sweep_bp(wn(n, 32), 150, 120, 2400, 700) * lin([(0, 0), (.01, .8), (.4, .7), (.85, 0)], n) * .9
    crk = nzb(.012, 33, 3500, dec=.004, a=.0002)
    return mixn(blast, air, sub_hit(.45, 130, 48, .09) * 1.1, crk * .8, at(whoosh(.6, 34, 600, 1500, 3000, 7000, .3) * .4, .08))


def landing_h(kind):
    hv = kind == 'heavy'
    thud = sub_hit(.9 if hv else .6, 88 if hv else 135, 26 if hv else 40, .2 if hv else .12)
    crunch = nzb(.35, 51, hi=2200 if hv else 4000, dec=.08 if hv else .05)
    return rev(mixn(thud * 1.3, crunch, clatter(.7, 52, 90, 300, 4500) * .6, ring(.5, 53, .55 if hv else .8, .35), at(servo(.5, 520, 240, .1), .02)), .5, .2, .3)


def footstep_h(kind, v):
    f0, f1, dec, rb, tone = {'light': (140, 58, .08, 1.0, 3500), 'medium': (110, 44, .11, .8, 2600), 'heavy': (88, 30, .16, .6, 1800)}[kind]
    thud = sub_hit(.4, f0 * (1 + .04 * v), f1, dec)
    dirt = nzb(.2, 61 + v, hi=tone, dec=.04) * 0.9
    clank = ring(.3, 62 + v, rb * (1 + .06 * v), .3)
    sv = servo(.4, {'light': 1500, 'medium': 1000, 'heavy': 700}[kind] * (1 + .05 * v), 380, .1, .25)
    return mixn(thud * 1.2, dirt, clank, at(sv, .02, .55), clatter(.3, 63 + v, 70, 400, 5000) * .35)


# ---- weapons
def rifle_h(v):
    return rev(mixn(sub_hit(.5, 105, 42, .10) * 1.1, dist_tail(1.2, 700 + v, 900, 120) * .6, ring(.5, 710 + v, 1 + .05 * v, .12),
                    nzb(.012, 720 + v, 3000, dec=.003) * .5, clatter(.25, 730 + v, 40, 1500, 7000) * .18), .8, .2, .3)


def smg_h(v):
    return mixn(sub_hit(.2, 125, 58, .05), nzb(.02, 740 + v, 2000, dec=.005) * .5, clatter(.15, 745 + v, 60, 1200, 6000) * .3, dist_tail(.5, 748 + v, 700, 150) * .3)


def autocannon_h(v):
    return rev(mixn(sub_hit(.45, 92, 38, .10) * 1.1, dist_tail(.9, 750 + v, 800, 130) * .5, ring(.4, 755 + v, .9 + .05 * v, .18),
                    nzb(.015, 758 + v, 2500, dec=.004) * .5, clatter(.2, 759 + v, 40, 900, 5000) * .2), .6, .18, .25)


def gatling_round_h():
    return mixn(sub_hit(.07, 130, 70, .03) * .9, nzb(.04, 150, hi=4500, dec=.012) * .8, nzb(.006, 151, 3000, dec=.002) * .5, ring(.05, 152, 3.2, .3))


def gatling_loop_h():
    rate = 25; rounds = 20; n = N(rounds / rate); out = np.zeros(n); r = np.random.default_rng(160); hit = gatling_round_h(); t = T(n)
    for i in range(rounds):
        wrap_add(out, hit * (0.8 + 0.2 * r.random()), N(i / rate + 0.0006 * r.standard_normal()) % n)
    motor = (sine(75, n) * .22 + sine(150, n) * .17 + sine(300, n) * .09 + sine(25, n) * .12) * (0.85 + 0.15 * np.cos(2 * np.pi * 25 * t))
    gear = lp(wn(n, 161), 1200) * .08 * (0.7 + 0.3 * np.cos(2 * np.pi * 25 * t))
    return drive(out * .85 + motor + gear, 1.25)


def gatling_down_h():
    n = N(1.8)
    whine = (lp(saw(xs(150, 28, n), n), 1800) * .4 + sine(xs(75, 14, n), n) * .5) * lin([(0, .7), (1.2, .35), (1.8, 0)], n)
    clicks = shots(mixn(nzb(.012, 162, 2000, dec=.003), ring(.03, 163, 2.5, .3)), [0.05, .13, .24, .38, .56, .8, 1.1, 1.5])[:n]
    return mixn(whine, clicks * .6, at(sub_hit(.4, 70, 34, .1) * .5, 0))


def shotgun_h():
    pump = shots(mixn(nzb(.03, 171, 900, 4500, .01, .0005), ring(.12, 172, 2.0, .6)), [.42, .54])
    return rev(mixn(sub_hit(.6, 82, 32, .15) * 1.15, dist_tail(1.1, 170, 800, 110) * .6, ring(.45, 173, .9, .12), nzb(.02, 174, 2500, dec=.006) * .5, pump * .6), .8, .2, .25)


def zap_h():
    crk = sine(xs(5200, 380, N(.04)), N(.04)) * ad(N(.04), .0003, .012) * 1.1 + nzb(.04, 301, 4000, dec=.004, a=.0002) * 1.1
    buzz = sq(xs(900, 260, N(.2)), N(.2), .3) * ad(N(.2), .001, .05) * .25
    return rev(mixn(crk, buzz, clatter(.4, 302, 150, 3000, 11000) * .45, sub_hit(.45, 95, 36, .1) * .9, ring(.6, 303, 1.4, .25), dist_tail(.8, 304, 700, 120) * .35), .8, .22, .6)


def plasma_h():
    n = N(.5)
    return rev(mixn(sub_hit(.5, 100, 34, .13), fm(xs(900, 120, n), xs(300, 60, n), 3, n) * ad(n, .001, .09) * .6, nzb(.4, 311, 600, 5000, .08) * .6,
                    ring(.6, 312, 1.1, .3), dist_tail(.9, 313, 800, 110) * .4), .7, .2, .5)


def charge_h(sec, f0, f1, seed, noise_hi=6000):
    n = N(sec); t = T(n); f = xs(f0, f1, n)
    tone = (lp(saw(f, n), 3500) * .5 + sine(f, n) * .5 + sine(f * 2, n) * .2) * lin([(0, .15), (sec, 1)], n)
    swell = sweep_bp(wn(n, seed), 200, 900, 1500, noise_hi) * lin([(0, 0), (sec, .8)], n)
    pulse = sine(xs(45, 90, n), n) * (0.5 + 0.5 * np.sin(2 * np.pi * np.cumsum(xs(6, 22, n)) / SR)) * lin([(0, .1), (sec, 1)], n)
    return mixn(tone * .6, swell * .5, pulse * .8) * np.minimum((sec - t) / .02, 1)


def bazooka_h():
    return rev(mixn(sub_hit(.8, 85, 32, .18) * 1.1, at(whoosh(1.2, 321, 300, 160, 4500, 1200, .2) * .75, .03), dist_tail(1.5, 322, 800, 110) * .55,
                    nzb(.015, 323, 2000, dec=.004) * .4, clatter(.5, 324, 80, 700, 5000) * .3, ring(.6, 325, .8, .12)), 1.0, .22, .25)


def grenade_h():
    return rev(mixn(sub_hit(.4, 115, 46, .1) * 1.1, nzb(.03, 330, 1500, 7000, .01) * .6, at(whoosh(.4, 331, 500, 900, 3000, 6000, .4) * .4, .03),
                    ring(.3, 332, 1.1, .15), dist_tail(.6, 333, 700, 130) * .35), .5, .18, .3)


def grenadecannon_h():
    return rev(mixn(sub_hit(1.0, 72, 26, .25) * 1.2, dist_tail(2.0, 340, 900, 90) * .7, at(whoosh(.9, 341, 250, 130, 3500, 900, .15) * .5, .02),
                    ring(.8, 342, .7, .15), clatter(.8, 343, 70, 500, 5000) * .3, nzb(.02, 344, 2000, dec=.006) * .5), 1.2, .25, .25)


def missile_h(count, spacing, heavy=False):
    sec = count * spacing + 1.4; n = N(sec); out = np.zeros(n); r = np.random.default_rng(350 + count)
    for i in range(count):
        a = N(i * spacing)
        pop = sub_hit(.3, 150 if not heavy else 110, 56, .06) * .9 + nzb(.3, 351 + i, 1200, 7000, .012) * .6
        hiss = whoosh(1.1, 360 + i, 500, 260, 3500 if not heavy else 2600, 1500, .12) * (.7 if not heavy else .95)
        seg = mixn(pop, hiss, clatter(.3, 370 + i, 220, 1500, 8000) * .45) * (0.85 + .15 * r.random())
        k = min(len(seg), n - a); out[a:a + k] += seg[:k]
    return rev(mixn(out, at(dist_tail(1.0, 380, 600, 120) * .25, 0.02, sec)), .8, .15, .35)


def rocket_loop_h():
    n = N(1.5); L = (n - N(.2)) / SR; q = lambda f: round(f * L) / L
    roar = bp(wn(n, 390), 220, 3200) * (.8 + .2 * slow(n, 391, 30))
    low = sine(q(74), n) * .4 + sine(q(148), n) * .15 + lp(wn(n, 393), 140) * .8
    return loopify(drive((roar * .55 + clatter(1.5, 392, 160, 1500, 7500, 1.0) * .35 + low) * .8, 1.3), .2)


def blade_h():
    n = N(1.1)
    hyd = at(nzb(.5, 401, 3000, 9000, .15, .02) * .35, .55, 1.1)
    return rev(mixn(at(whoosh(.8, 400, 200, 700, 1200, 5500, .45), .02, 1.1), hyd, at(servo(1.0, 160, 340, .22, .45), 0, 1.1), sub_hit(.4, 70, 38, .1) * .5), .6, .15, .3)[:n + N(.3)]


def clang_h(sec, seed, base, sub=True):
    return rev(mixn(ring(sec, seed, base, 1.0), ring(sec * .7, seed + 1, base * .53, .8), nzb(.015, seed + 2, 1500, dec=.004) * .6,
                    sub_hit(.4, 85, 38, .1) * (.9 if sub else 0), clatter(sec * .5, seed + 3, 50, 800, 6000) * .3), .9, .22, .3)


def boom_h(sec, f0, f1, seed, deb=1.0, tail_sec=None):
    ts = tail_sec or sec * 1.8
    return rev(mixn(sub_hit(sec, f0, f1, sec * .28) * 1.2, dist_tail(ts, seed, 1000, 90) * .7, clatter(sec * 1.2, seed + 1, 55 * deb, 120, 4500, 1.4) * .7,
                    nzb(.02, seed + 2, 1500, dec=.006) * .4, ring(sec * .8, seed + 3, .6, .12)), min(2.4, sec * 1.4), .22, .25)


def death_h():
    boom = sub_hit(1.8, 62, 22, .55) * 1.2
    rings = [at(ring(1.1, 430 + i, b, .45 * g), tt) for i, (tt, b, g) in enumerate([(.25, .55, 1), (.8, .8, .8), (1.5, .45, .7), (2.3, 1.1, .5)])]
    pops = [at(sub_hit(.45, 90, 38, .1) * .8 + nzb(.45, 440 + i, 800, 5000, .03) * .7, tt) for i, tt in enumerate([.9, 1.45, 2.1, 2.9])]
    return rev(mixn(boom, dist_tail(3.8, 420, 900, 80) * .7, at(servo(2.4, 420, 55, .35, .25), .1), clatter(3.2, 421, 80, 150, 3200, 1.1) * .75,
                    *rings, *pops, nzb(.02, 449, 1500, dec=.006)), 1.6, .22, .2)


def rail_h():
    return rev(mixn(sine(xs(7000, 300, N(.05)), N(.05)) * ad(N(.05), .0002, .015) * 1.1, nzb(.02, 510, 4000, dec=.005, a=.0002) * 1.2,
                    sub_hit(.7, 90, 30, .18) * 1.1, ring(1.2, 511, 1.5, .35), ring(1.0, 512, .8, .3), dist_tail(1.5, 513, 900, 100) * .5, clatter(.4, 514, 120, 3000, 11000) * .35), 1.0, .22, .6)


def lasercannon_h():
    n = N(1.8); t = T(n)
    beam = (lp(saw(55 * (1 + .01 * np.sin(2 * np.pi * 7 * t)), n), 1200) * .5 + lp(saw(110.5, n), 2500) * .35 + sine(55, n) * .6) * lin([(0, 0), (.04, 1), (1.4, .8), (1.8, 0)], n)
    crk = sine(xs(6000, 250, N(.06)), N(.06)) * ad(N(.06), .0003, .02) + nzb(.06, 520, 3500, dec=.006, a=.0002)
    hiss = hp(wn(n, 521), 3000) * lin([(0, 0), (.05, .5), (1.4, .35), (1.8, 0)], n) * .25
    return rev(mixn(beam, crk * 1.1, hiss, sub_hit(.8, 80, 28, .2), ring(1.0, 522, 1.3, .3), clatter(1.4, 523, 80, 2500, 10000) * .35), 1.1, .22, .6)


def define_heavy():
    for k in ('light', 'medium', 'heavy'):
        sfx('boost_loop' + ('' if k == 'medium' else '_' + k), 'booster', turbine_loop(k), loop=True, per_slot=64 if k == 'medium' else None, pitch=0.0,
            note=('neutral ' if k == 'medium' else '%s-class ' % k) + 'turbine bed: filtered roar + spooling whine + sub rumble; Stop it when the boost ends')
        H('boost_on_' + k, 'booster', [boost_on_h(k)], [[W + 'c4/c4_thump_01']], {'light': 1.0, 'medium': .85, 'heavy': .7}[k], -4,
          note='boost ignition (%s): stock c4 thump + synth turbine spool-up and kick' % k)
    H('qb', 'booster', [quick_boost_h()], [[W + 'c4/c4_thump_01']], 1.15, -5, note='quick boost: hard air blast + boom + crack')
    sfx('hover_loop', 'booster', hover_h(), loop=True, per_slot=64, pitch=0.0, note='hover bed: low rumble + soft turbine (optional per-slot ring)')
    H('land_light', 'foley', [landing_h('light')], [CONC, BOX], .75, -4, vol=.7, note='landing: stock concrete + metal impacts down to 0.75 + sub thud')
    H('land_heavy', 'foley', [landing_h('heavy')], [['physics/concrete/boulder_impact_hard4', 'physics/concrete/rock_impact_hard3'], ['physics/metal/metal_box_break1', 'physics/metal/metal_box_break2']],
      .55, -4, vol=.8, note='heavy landing: boulder + crumpling metal + deep sub')
    st = {'light': ([BOX, CONC], .85, .45), 'medium': ([BARREL, CONC], .7, .55),
          'heavy': ([['physics/concrete/boulder_impact_hard4', 'physics/concrete/rock_impact_hard1', 'physics/concrete/rock_impact_hard2'], BARREL], .55, .65)}
    for k, (tr, p, vol) in st.items():
        H('step_' + k, 'foley', [footstep_h(k, v) for v in range(3)], tr, p, -5, vol=vol, note='footstep (%s): stock metal + ground stomp, servo whine, sub thud; 3 synth variants' % k)
    H('rifle', 'weapon_light', [rifle_h(v) for v in range(3)], [[W + 'awp/awp_01', W + 'awp/awp_02', W + 'negev/negev_01']], .72, -4, note='AR-22: heavy cannon crack (AWP/negev down to 0.72) + sub + tail')
    H('smg', 'weapon_light', [smg_h(v) for v in range(3)], [M249 + [W + 'mac10/mac10_01']], .8, -5, note='SMG-Hornet: m249/mac10 down to 0.8 + sub + clack')
    H('gatling', 'weapon_light', [gatling_round_h()], [[W + 'negev/negev_clean_01', W + 'negev/negev_clean_02']], .72, -4, note='one gatling round (negev down to 0.72 + thump)')
    sfx('gatling_loop', 'weapon_light', gatling_loop_h(), loop=True, ring=16, pitch=0.0, note='20 rounds at 25/s + barrel motor, loops (synth only: stock shots cannot loop); Stop on release then gatling_down')
    sfx('gatling_down', 'weapon_light', gatling_down_h(), note='barrel spin-down')
    H('shotgun', 'weapon_medium', [shotgun_h()], [[W + 'nova/nova-1', W + 'xm1014/xm1014-1']], .62, -4, note='SG-Scatter: nova/xm1014 down to 0.62 + sub + heavy pump')
    sfx('laser', 'weapon_medium', zap_h(), note='LR-Lumen: sharp electric crack + sub boom + metal ring + crackle (synth)')
    sfx('laser_charge', 'weapon_medium', charge_h(1.2, 120, 1600, 700), note='laser charge rise (1.2 s)')
    H('bazooka', 'weapon_heavy', [bazooka_h()], [[W + 'c4/c4_thump_01']], .8, -4, note='BZ-Hammer: stock c4 thump + synth launch boom, whoosh, tail')
    H('grenade', 'weapon_medium', [grenade_h()], [[W + 'nova/nova-1']], .6, -5, note='GL-Lob thunk')
    H('grenade_bounce', 'impact', [mixn(ring(.35, 335, 1.0, .5), sub_hit(.2, 110, 55, .05) * .8)], [['physics/metal/metal_grenade_impact_hard%d' % i for i in (1, 2, 3)]], .7, -6, vol=.5,
      note='grenade bounce (metal impacts down to 0.7)')
    sfx('blade', 'weapon_medium', blade_h(), note='PB-Moonlight: heavy air swing + hydraulic hiss (synth)')
    H('blade_clash', 'impact', [clang_h(1.1, 410, 1.0)], [BOX + BARREL], .55, -4, vol=.75, note='blade/pile hit: huge metal clang (stock metal impacts down to 0.55) + ring + sub')
    sfx('plasma', 'weapon_medium', plasma_h(), note='PR-Ion: heavy plasma burst (synth)')
    H('rail', 'weapon_heavy', [rail_h()], [[W + 'awp/awp_distant', W + 'awp/awp_01']], .6, -5, note='RG-Lance: electric crack + ring (synth) + distant AWP boom')
    sfx('rail_charge', 'weapon_heavy', charge_h(.5, 200, 2600, 710, 9000), note='rail wind-up (0.5 s)')
    H('handmsl', 'weapon_medium', [missile_h(4, .11)], [[W + 'c4/c4_thump_01']], 1.1, -6, note='HM-4: four launches 0.11 s apart')
    sfx('msl_loop', 'booster', rocket_loop_h(), loop=True, ring=24, pitch=0.05, note='rocket motor loop following a missile (ring of 24)')
    H('vm6', 'weapon_heavy', [missile_h(6, .1)], [[W + 'c4/c4_thump_01']], 1.0, -6, note='VM-6 salvo')
    H('vm12', 'weapon_heavy', [missile_h(12, .085)], [[W + 'c4/c4_thump_01']], .95, -6, note='VM-12 salvo')
    H('dualmsl', 'weapon_heavy', [missile_h(2, .3, True)], [[W + 'c4/c4_thump_01']], .8, -5, note='DM-2: two heavy launches')
    sfx('lasercannon', 'weapon_heavy', lasercannon_h(), note='LC-Solar: electric crack + sustained beam roar + sub (synth)')
    sfx('lasercannon_charge', 'weapon_heavy', charge_h(1.25, 90, 1500, 720), note='LC-Solar charge (1.25 s)')
    H('grenadecannon', 'weapon_heavy', [grenadecannon_h()], [[W + 'c4/c4_thump_01'], [W + 'xm1014/xm1014-1', W + 'nova/nova-1']], .55, -4, note='GC-Thunder: layered thump + shotgun boom down to 0.55 + sub')
    H('autocannon', 'weapon_medium', [autocannon_h(v) for v in range(3)], [M249 + NEG], .66, -4, note='AC-Drum: m249/negev down to 0.66 + sub + ring, 3 synth variants')
    H('flak', 'weapon_medium', [shotgun_h()[:N(.9)]], [[W + 'nova/nova-1', W + 'xm1014/xm1014-1']], .7, -5, note='FK-Burst fire')
    H('flak_burst', 'explosion', [boom_h(.6, 110, 44, 450, .8)], [HE], .9, -5, note='flak air-burst: hegrenade down to 0.9 + frag debris')
    H('hit_metal', 'impact', [rev(mixn(ring(.3, 460 + v, 1 + .12 * v, .9), sub_hit(.14, 170, 80, .04) * .7, clatter(.2, 465 + v, 60, 900, 6500) * .4), .3, .15, .5) for v in range(3)],
      [BULLETM + ['physics/metal/metal_sheet_impact_bullet1', 'physics/metal/metal_solid_impact_bullet1']], .8, -5, vol=.6, note='round on armour: stock metal bullet impacts down to 0.8 + clank')
    H('hit_ground', 'impact', [mixn(sub_hit(.2, 105, 50, .06), nzb(.2, 470 + v, hi=900, dec=.05) * .8) for v in range(2)],
      [['physics/concrete/concrete_impact_bullet%d' % i for i in range(1, 8)]], .75, -5, vol=.55, note='round on terrain: stock concrete impacts + dirt thud')
    H('boom_small', 'explosion', [boom_h(.9, 98, 36, 480, .8)], [HE], .8, -4, note='small splash: hegrenade down to 0.8 + sub + debris')
    H('boom_large', 'explosion', [boom_h(1.5, 72, 24, 490, 1.0, 3.0)], [[W + 'c4/c4_explode1'], [W + 'c4/c4_exp_deb1', W + 'c4/c4_exp_deb2']], .75, -4, note='large splash: c4 explode + debris down to 0.75 + deep sub + long tail')
    H('mech_death', 'explosion', [death_h()], [[W + 'c4/c4_explode1'], [W + 'c4/c4_exp_deb1', W + 'c4/c4_exp_deb2'], HE], .7, -4, note='mech destroyed: layered explosions + metal collapse groan, clatter, secondary pops (4 s)')
    H('stagger_clang', 'impact', [clang_h(1.3, 500, .75)], [BOX + BARREL], .6, -4, vol=.8, note='stagger: massive structural clang')


def define_all():
    # boosters and movement
    sfx('boost_loop', 'booster', thruster_loop('medium'), loop=True, per_slot=64, pitch=0.0,
        note='neutral thruster bed following each mech (class flavour comes from boost_on_*); Stop it when the boost ends')
    sfx('boost_loop_light', 'booster', thruster_loop('light'), loop=True, pitch=0.0, note='optional light-class bed (not placed per slot)')
    sfx('boost_loop_heavy', 'booster', thruster_loop('heavy'), loop=True, pitch=0.0, note='optional heavy-class bed')
    for k in ('light', 'medium', 'heavy'): sfx('boost_on_' + k, 'booster', boost_on(k), note='boost ignition punch, %s class' % k)
    sfx('qb', 'booster', quick_boost(), note='quick boost whoosh')
    sfx('hover_loop', 'booster', hover_loop(), loop=True, per_slot=64, pitch=0.0, note='hover bed (optional per-slot ring; drop if entity budget is tight)')
    sfx('land_light', 'foley', landing('light'), note='landing thud, light/medium')
    sfx('land_heavy', 'foley', landing('heavy'), note='landing thud, heavy/boss')
    for k in ('light', 'medium', 'heavy'): sfx('step_' + k, 'foley', footstep(k), note='footstep stomp for gait clips (%s)' % k)
    # weapons (parts.json keys)
    sfx('rifle', 'weapon_light', *[rifle(v) for v in range(3)], note='AR-22 crack, 3 variants')
    sfx('smg', 'weapon_light', *[smg(v) for v in range(3)], note='SMG-Hornet snap, 3 variants')
    sfx('gatling', 'weapon_light', gatling_loop()[:N(0.09)] * 1.0, note='one gatling round (use gatling_loop ring while the trigger is held)')
    sfx('gatling_loop', 'weapon_light', gatling_loop(), loop=True, ring=16, pitch=0.0, note='10 rounds at 25/s + barrel motor, loops; Stop on release then play gatling_down')
    sfx('gatling_down', 'weapon_light', gatling_down(), note='barrel spin-down')
    sfx('shotgun', 'weapon_medium', shotgun(), note='SG-Scatter boom + pump')
    sfx('laser', 'weapon_medium', laser_zap(), note='LR-Lumen zap')
    sfx('laser_charge', 'weapon_medium', charge(1.2, 220, 1800, 700, trem=True), note='laser charge rise (1.2 s, matches charge time)')
    sfx('bazooka', 'weapon_heavy', bazooka(), note='BZ-Hammer thump + rocket whoosh')
    sfx('grenade', 'weapon_medium', grenade_thunk(), note='GL-Lob thunk')
    sfx('grenade_bounce', 'impact', grenade_bounce(), note='grenade bouncing (play at the bounce point)')
    sfx('blade', 'weapon_medium', blade_swing(), note='PB-Moonlight swing + hum')
    sfx('blade_clash', 'impact', blade_clash(), note='blade hit on a mech')
    sfx('plasma', 'weapon_medium', plasma(), note='PR-Ion pulse')
    sfx('rail', 'weapon_heavy', rail_crack(), note='RG-Lance crack (range 6000)')
    sfx('rail_charge', 'weapon_heavy', charge(0.5, 400, 2600, 710, noise_hi=9000), note='rail wind-up (0.5 s)')
    sfx('handmsl', 'weapon_medium', missile_launch(4, 0.11), note='HM-4 pod: four launches 0.11 s apart')
    sfx('msl_loop', 'booster', rocket_loop(), loop=True, ring=24, pitch=0.05, note='rocket motor loop following a missile (ring of 24)')
    sfx('shield', 'ability', shield_hum(True), note='arm shield raised')
    sfx('shield_down', 'ability', shield_hum(False), note='arm shield lowered')
    sfx('vm6', 'weapon_heavy', missile_launch(6, 0.1), note='VM-6 salvo')
    sfx('vm12', 'weapon_heavy', missile_launch(12, 0.085), note='VM-12 salvo')
    sfx('dualmsl', 'weapon_heavy', missile_launch(2, 0.3, heavy=True), note='DM-2: two heavy launches')
    sfx('lasercannon', 'weapon_heavy', lasercannon_beam(), note='LC-Solar beam')
    sfx('lasercannon_charge', 'weapon_heavy', lasercannon_charge(), note='LC-Solar charge (1.25 s)')
    sfx('grenadecannon', 'weapon_heavy', big_boom(1.3, 110, 32, 1500, 720, rumble=0.5), note='GC-Thunder fire')
    sfx('autocannon', 'weapon_medium', *[autocannon(v) for v in range(3)], note='AC-Drum thud, 3 variants')
    sfx('flak', 'weapon_medium', flak_fire(), note='FK-Burst fire')
    sfx('flak_burst', 'explosion', flak_burst(), note='flak air-burst (at the detonation point)')
    sfx('pulseshield', 'ability', bubble(True), note='PS-Aegis bubble up')
    sfx('pulseshield_down', 'ability', bubble(False), note='bubble collapse')
    sfx('repair', 'ability', repair_chime(), note='RK-Mend activated')
    sfx('repair_loop', 'ability', repair_loop(), loop=True, ring=8, pitch=0.0, note='repair in progress (6 s, Stop at end)')
    sfx('decoy', 'ability', decoy_pop(), note='DC-Chaff pops (adapted from the Dogfight flare-release recipe)', src='synthesised here, after Dogfight df_flare_release')
    # impacts and events
    sfx('hit_metal', 'impact', *[hit_metal(v) for v in range(3)], note='round on armour, 3 variants')
    sfx('hit_ground', 'impact', *[hit_ground(v) for v in range(2)], note='round on terrain, 2 variants')
    sfx('boom_small', 'explosion', big_boom(0.9, 160, 45, 2800, 800, rumble=0.3, bright=0.6), note='small splash (plasma, grenade, flak, missile)')
    sfx('boom_large', 'explosion', big_boom(1.7, 90, 28, 1800, 810, rumble=0.7, bright=0.4), note='large splash (bazooka, grenade cannon)')
    sfx('mech_death', 'explosion', mech_death(), note='mech destroyed: boom, secondary pops, debris')
    sfx('stagger_clang', 'impact', stagger_clang(), note='a mech staggered (world sound at the mech)')
    sfx('drop_entry', 'world', drop_entry(), note='drop-pod atmospheric entry (2.6 s)')
    sfx('capture_tick', 'world', capture_tick(), note='capture point progress tick (at the point)')
    sfx('capture_done', 'world', capture_done(), note='capture complete chord')
    sfx('wave_start', 'world', wave_start(), note='PvE wave start klaxon')
    sfx('boss_roar', 'world', boss_roar(), note='boss roar (synth formant growl, range 9000)')
    sfx('bounty', 'world', bounty(), note='bounty placed / claimed')
    define_ui()
    define_heavy()


# ================================================================ events and tables
MUSIC_VOL = {'music_garage': 0.55, 'music_battle': 0.6}


def vsnd_list(files, ind='\t\t'):
    out = [ind + 'vsnd_files_track_01 =', ind + '[']
    out += [ind + '\t"%s",' % f for f in files]
    return out + [ind + ']']


def rms_db(x): return 20 * math.log10(math.sqrt(float(np.mean(x ** 2))) + 1e-9)


def event_text(key, d, files, vol):
    full, silent, _, mix, _ = CATS[d['cat']]
    if d['cat'] == 'ui':
        lines = ['base = "ifr.ui.base"', 'volume = %.2f' % vol]
        if len(files) == 1: lines.append('vsnd_files_track_01 = "%s"' % files[0])
        else: lines += vsnd_list(files)
        return E._event('ifr.' + key, lines)
    st = d.get('stock')
    lines = ['type = "csgo_mega"', 'volume = %.2f' % vol, 'pitch = %.2f' % (st['pitch'] if st else 1.0), 'mixgroup = "%s"' % mix, 'reverb_wet = 0.3',
             'occlusion_intensity = 0.0', 'distance_effect_mix = 1.0', 'use_distance_volume_mapping_curve = true']
    if d['pitch']: lines += ['pitch_random_min = %.2f' % -d['pitch'], 'pitch_random_max = %.2f' % d['pitch']]
    tracks = ([['sounds/%s.vsnd' % f for f in tr] for tr in st['tracks']] if st else []) + [files]
    for i, tr in enumerate(tracks, 1):
        nm = 'vsnd_files_track_%02d' % i
        if len(tr) == 1: lines.append('%s = "%s"' % (nm, tr[0]))
        else: lines += vsnd_list(tr).__class__([l.replace('vsnd_files_track_01', nm) for l in vsnd_list(tr)])
    lines.append('distance_volume_mapping_curve =')
    return E._event('ifr.' + key, lines + E.curve([(0, 1), (full, 1), (silent, 0)]))


UI_BASE = E._event('ifr.ui.base', ['type = "csgo_mega"', 'volume = 0.6', 'pitch = 1.0', 'mixgroup = "UI"', 'use_world_position = false',
                                    'position_relative_to_player = false', 'distance_effect_mix = 0.0', 'occlusion_intensity = 0.0'])


# ================================================================ preview sheet (PIL + numpy; no matplotlib)
def contact_sheet(path, items, cols=6, w=300, h=90):
    from PIL import Image, ImageDraw
    rows = (len(items) + cols - 1) // cols
    img = Image.new('RGB', (cols * w, rows * h), (18, 18, 22)); dr = ImageDraw.Draw(img)
    for i, (name, x) in enumerate(items):
        cx, cy = (i % cols) * w, (i // cols) * h
        x = x if x.ndim == 1 else x.mean(1)
        step = max(1, len(x) // (w - 8)); seg = x[:step * ((w - 8))].reshape(-1, step) if len(x) >= step * (w - 8) else None
        if seg is None: seg = np.pad(x, (0, step * (w - 8) - len(x))).reshape(-1, step)
        mn, mx = seg.min(1), seg.max(1); mid = cy + h // 2 + 6; amp = (h // 2 - 14)
        dr.rectangle([cx, cy, cx + w - 1, cy + h - 1], outline=(40, 40, 48))
        for k in range(len(mn)):
            dr.line([(cx + 4 + k, mid - mx[k] * amp), (cx + 4 + k, mid - mn[k] * amp)], fill=(90, 200, 255))
        dr.text((cx + 4, cy + 2), '%s  %.2fs  pk %.1f  rms %.1f dB' % (name, len(x) / SR, 20 * math.log10(np.abs(x).max() + 1e-9), rms_db(x)), fill=(230, 230, 230))
    img.save(path)


def spectrogram(path, x, title=''):
    from PIL import Image, ImageDraw
    x = x if x.ndim == 1 else x.mean(1)
    nfft, hop = 1024, max(256, len(x) // 1400)
    frames = max(1, (len(x) - nfft) // hop)
    win = np.hanning(nfft)
    spec = np.empty((nfft // 2, frames))
    for i in range(frames):
        seg = x[i * hop:i * hop + nfft] * win; spec[:, i] = np.abs(np.fft.rfft(seg))[:nfft // 2]
    spec /= win.sum() / 2                                     # a full-scale sine reads 0 dBFS
    db = 20 * np.log10(spec + 1e-6); db = np.clip((db + 80) / 80, 0, 1)
    # log frequency rows (20 Hz .. 20 kHz), 256 tall
    rows = 256; f = np.fft.rfftfreq(nfft, 1 / SR)[:nfft // 2]
    fr = np.geomspace(30, 20000, rows); idx = np.clip(np.searchsorted(f, fr), 0, nfft // 2 - 1)
    img_a = db[idx[::-1], :]
    rgb = np.stack([np.clip(img_a * 2.2 - 0.6, 0, 1), np.clip(img_a * 1.6 - 0.3, 0, 1), np.clip(img_a * 1.2, 0, 1)], 2)
    im = Image.fromarray((rgb * 255).astype(np.uint8)).resize((min(1400, max(400, frames)), rows))
    dr = ImageDraw.Draw(im); dr.text((4, 4), '%s  (log 30 Hz - 20 kHz, 80 dB)' % title, fill=(255, 255, 255))
    im.save(path)


# ================================================================ main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('out'); ap.add_argument('--soundevents'); ap.add_argument('--no-music', action='store_true')
    ap.add_argument('--only', help='comma list of keys to (re)write (dev)')
    a = ap.parse_args()
    out = a.out; snd_dir = os.path.join(out, 'sounds', 'ifr'); os.makedirs(snd_dir, exist_ok=True)
    os.makedirs(os.path.join(out, 'soundevents'), exist_ok=True); os.makedirs(os.path.join(out, '_gen'), exist_ok=True)
    prev = os.path.join(PROJ, 'preview', 'audio'); os.makedirs(prev, exist_ok=True)
    define_all()
    only = set(a.only.split(',')) if a.only else None
    table = {}; events = [UI_BASE]; rows = []; sheet = []; clipped = 0
    for key, d in SFX.items():
        if only and key not in only: continue
        files = []; secs = 0
        for i, x in enumerate(d['variants']):
            name = key if len(d['variants']) == 1 else '%s_%02d' % (key, i + 1)
            path = os.path.join(snd_dir, name + '.wav')
            clipped += int(np.sum(np.abs(x) >= 0.999))
            secs = C.write_wav(path, x if d['loop'] else fade(x, 0.001, 0.004), loop=d['loop'])
            files.append('sounds/ifr/%s.vsnd' % name)
            rows.append((name, d['cat'], secs, 20 * math.log10(np.abs(x).max()), rms_db(x), 'loop' if d['loop'] else '', d['note']))
            sheet.append((name, x))
        full, silent, base_vol, mix, target = CATS[d['cat']]
        lo_hi = (-5, 2) if d['cat'] == 'ui' else (-8, 4)
        trim = dbv(np.clip(target - rms_db(d['variants'][0]), *lo_hi))        # toward the category's RMS, within -8..+4 dB (UI -5..+2)
        vol = float(np.clip(base_vol * trim, 0.15, 1.0))
        if d.get('stock') or d.get('vol'): vol = float(d['vol'] if d.get('vol') else base_vol)
        events.append(event_text(key, d, files, vol))
        ent = {'event': 'ifr.' + key, 'entity': 'ifr_snd_' + key, 'range': silent, 'full': full, 'loop': d['loop'], 'ui': d['cat'] == 'ui',
               'stop_on_new': bool(d['loop']), 'seconds': round(secs / (d['stock']['pitch'] if d.get('stock') else 1.0), 3), 'variants': len(files), 'files': files, 'volume': round(vol, 2),
               'mixgroup': mix, 'category': d['cat'], 'note': d['note']}
        if d.get('stock'): ent['stock'] = {'tracks': d['stock']['tracks'], 'pitch': d['stock']['pitch']}
        if d['per_slot']: ent['per_slot'] = d['per_slot']
        if d['ring']: ent['ring'] = d['ring']
        table[key] = ent
    music = {}
    if not a.no_music:
        for key, fn in (('music_garage', music_garage), ('music_battle', music_battle)):
            if only and key not in only: continue
            x, secs = fn(); path = os.path.join(snd_dir, key + '.wav')
            C.write_wav(path, x, loop=True)
            clipped += int(np.sum(np.abs(x) >= 0.999))
            events.append(E.event_csgo_music('ifr.' + key, 'sounds/ifr/%s.vsnd' % key, MUSIC_VOL[key]))
            music[key] = {'event': 'ifr.' + key, 'entity': 'ifr_snd_' + key, 'seconds': round(secs, 3), 'loop': True, 'stop_on_new': True,
                          'file': 'sounds/ifr/%s.vsnd' % key, 'volume': MUSIC_VOL[key], 'convar': 'snd_menumusic_volume'}
            rows.append((key, 'music', secs, 20 * math.log10(np.abs(x).max()), rms_db(x.mean(1)), 'loop', 'stereo'))
            sheet.append((key, x))
            spectrogram(os.path.join(prev, 'spec_%s.png' % key), x[:N(20)], key + ' (first 20 s)')
    # sound events
    ours = E.wrap(events)
    live = a.soundevents
    tpl = ''
    if live and os.path.exists(live): tpl = open(live, encoding='utf-8').read()
    elif os.path.exists(TEMPLATE): tpl = open(TEMPLATE, encoding='utf-8').read()
    text = E.merge(tpl, ours, 'IRONFRAME')
    open(os.path.join(out, 'soundevents', 'soundevents_addon.vsndevts'), 'w', encoding='utf-8', newline='\n').write(text)
    if live:
        os.makedirs(os.path.dirname(live) or '.', exist_ok=True)
        open(live, 'w', encoding='utf-8', newline='\n').write(text)
    # baked table
    if only and os.path.exists(os.path.join(out, '_gen', 'sounds.json')):        # dev: keep the other keys
        old = json.load(open(os.path.join(out, '_gen', 'sounds.json'), encoding='utf-8'))
        old['events'].update(table); old['music'].update(music); table, music = old['events'], old['music']
    pilot = [k for k in table if k.startswith('ui_')]
    doc = {'version': 1, 'prefix': 'ifr', 'tag': 'IRONFRAME',
           'conventions': {'event': 'ifr.<key>', 'entity': 'ifr_snd_<key>', 'per_slot': 'ifr_snd_<key>_00..NN-1, one per mech slot (adapter SetSourceEntity on the upper-body prop)',
                           'ring': 'ifr_snd_<key>_00..N-1, round-robin', 'ui': 'not placed in the world: StartSoundOnSingleClient', 'stop_on_new': 'point_soundevent stopOnNew key'},
           'events': table, 'music': music, 'pilot_tones': pilot,
           'loops_to_stop': [k for k, v in table.items() if v['loop']]}
    json.dump(doc, open(os.path.join(out, '_gen', 'sounds.json'), 'w', encoding='utf-8'), indent=1)
    # previews
    if sheet:
        contact_sheet(os.path.join(prev, 'contact_sheet.png'), sheet)
        for k in ('rifle_01', 'bazooka', 'boom_large', 'step_heavy_01', 'qb', 'gatling_loop', 'boost_loop', 'mech_death', 'lasercannon', 'ui_locked_warn'):
            for name, x in sheet:
                if name == k: spectrogram(os.path.join(prev, 'spec_%s.png' % k), x, k)
        with open(os.path.join(prev, 'README.md'), 'w', encoding='utf-8', newline='\n') as f:
            f.write('# IRONFRAME audio preview\n\nGenerated by `python -I tools/sounds.py out/addon`. Every file is 44.1 kHz 16-bit PCM, mono unless noted, '
                    'peak-normalised to %.0f dBFS; loops carry smpl + cue markers. Clipped samples (|x| >= 0.999) across every file: %d.\n\n'
                    '`contact_sheet.png` shows every waveform; `spec_*.png` are log-frequency spectrograms (a clipped file shows as flat broadband '
                    'bars across the whole band at the loud frames; none here).\n\n| file | category | seconds | peak dBFS | RMS dBFS | loop | note |\n|---|---|---|---|---|---|---|\n' % (PEAK_DB, clipped))
            for name, cat, secs, pk, r, lp_, note in rows:
                f.write('| %s | %s | %.2f | %.1f | %.1f | %s | %s |\n' % (name, cat, secs, pk, r, lp_, note))
            cats = {}
            for name, cat, secs, pk, r, lp_, note in rows: cats.setdefault(cat, []).append(r)
            f.write('\n## Loudness per category (RMS dBFS of the files; the event volume trims each sound toward the category target)\n\n| category | files | mean RMS | min | max | target |\n|---|---|---|---|---|---|\n')
            for cat, rs in cats.items():
                f.write('| %s | %d | %.1f | %.1f | %.1f | %s |\n' % (cat, len(rs), sum(rs) / len(rs), min(rs), max(rs), CATS[cat][4] if cat in CATS else '-'))
    n_files = sum(len(v['files']) for v in table.values()) + len(music)
    print('sounds: %d events (%d files), %d music loops, %d pilot tones, %d loops; clipped samples %d; events -> %s' %
          (len(table), n_files, len(music), len(pilot), len(doc['loops_to_stop']), clipped, os.path.join(out, 'soundevents', 'soundevents_addon.vsndevts')))


if __name__ == '__main__':
    main()
