"""mg_monsoon sounds: everything synthesised (numpy / scipy, 44.1 kHz, no samples) + the mv.* sound events, merged into
the addon's soundevents_addon.vsndevts (block "mg_monsoon", re-runnable; nothing else in the file is touched).

usage: sounds.py <addon content out> <template soundevents_addon.vsndevts> [--no-check]
  writes  <addon>/sounds/mv/*.wav                        16-bit PCM; loops carry smpl + cue markers
          <addon>/soundevents/soundevents_addon.vsndevts  (merged into the file already there, else into the template)
          ../out/sounds_report.json                       the numeric listen-check (peak, RMS, loop seam, spectrum)
  exits 1 if a check fails (clipping, a loop seam that would click, a spectrum that is not what the sound should be).

Events (docs/CONTRACT.md "Sound events"):
  mv.heli_rotor      loop, 3D 9000   blade slap (11 Hz blade pass) + rotor wash + tail rotor
  mv.heli_turbine    loop, 3D 3500   turbine whine + gearbox + exhaust hiss (close-in layer)
  mv.heli_gun        3D 8000         chain gun / door gun shot, 3 variants, pitch 0.96-1.04
  mv.rocket_launch   3D 7000         air rocket leaving the pod (2 variants)
  mv.rocket_fly      3D 4500         4 s motor roar for a flying rocket (one-shot, fades out; start it on the rocket prop)
  mv.howitzer_fire   3D 14000        105 mm: crack, boom, breech ring, valley echo tail (2 variants)
  mv.rocket_fire     3D 14000        122 mm rail launch: ignition crack + tearing roar (2 variants)
  mv.shell_whistle   3D 4200         2.0 s falling whistle, loudest at the end = the impact moment
  mv.shell_impact    3D 11000        HE burst: crack, boom, debris, tail (3 variants)
  mv.mount_gun       3D 7500         heavy MG shot (.50 / 12.7), 3 variants, pitch 0.95-1.05
  mv.capture / mv.flag_lost / mv.radio_blip   heard everywhere at the same volume (flat csgo_mega, no fall-off)
  mv.amb.valley      soundscape parent -> mv.amb.cicadas (stereo loop), mv.amb.river (stereo loop), mv.amb.birds, mv.amb.gecko,
                     mv.amb.frogs, mv.amb.thunder, mv.amb.guns (intermittent, random around the player)
"""
import os, sys, json, struct
import numpy as np
from scipy import signal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sndevents as E

SR = 44100
TAG = 'mg_monsoon'
HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- dsp helpers
def T(sec):
    return np.arange(int(round(SR * sec))) / SR


def bp(x, lo, hi, order=2):
    return signal.sosfilt(signal.butter(order, [lo, hi], 'bandpass', fs=SR, output='sos'), x)


def lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, 'lowpass', fs=SR, output='sos'), x)


def hp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, 'highpass', fs=SR, output='sos'), x)


def _unit(x):
    return x / (np.std(x) + 1e-12)


def bn(rng, n, lo, hi, order=2):
    """band-passed noise with unit rms (so layer gains mean what they say)"""
    return _unit(bp(rng.normal(0, 1, n), lo, hi, order))


def hn(rng, n, f, order=2):
    return _unit(hp(rng.normal(0, 1, n), f, order))


def ln(rng, n, f, order=2):
    return _unit(lp(rng.normal(0, 1, n), f, order))


def env(n, att, dec, hold=0.0):
    """attack (linear, s) then exponential decay (time constant s) after an optional hold"""
    t = np.arange(n) / SR
    return np.minimum(t / max(att, 1e-6), 1.0) * np.exp(-np.maximum(t - att - hold, 0) / dec)


def sweep(n, f0, f1, tau):
    """sine whose frequency falls from f0 to f1 with time constant tau"""
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / tau)
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def shaped_noise(n, rng, shape):
    """noise that is exactly periodic over n samples with the magnitude spectrum shape(f) (f in Hz): the building block of
    every seamless loop here (no crossfade needed, the last sample runs into the first)"""
    spec = np.fft.rfft(rng.normal(0, 1, n))
    f = np.fft.rfftfreq(n, 1.0 / SR)
    x = np.fft.irfft(spec * shape(f), n)
    return x / (np.std(x) + 1e-12)


def band(lo, hi, soft=0.25):
    """smooth band-pass magnitude for shaped_noise (log-domain raised edges)"""
    def s(f):
        f = np.maximum(f, 1e-3)
        a = 1.0 / (1.0 + (lo / f) ** (2 / soft * 0.5 + 2)); b = 1.0 / (1.0 + (f / hi) ** (2 / soft * 0.5 + 2))
        return a * b
    return s


def tail_ir(sec, rng, tau, lo=60.0, hi=1800.0, pre=0.0, echoes=()):
    """synthetic outdoor tail: decaying band-limited noise + discrete echoes [(delay s, gain, lowpass Hz)]"""
    n = int(SR * sec); t = np.arange(n) / SR
    ir = bn(rng, n, lo, hi) * np.exp(-t / tau) * (t >= pre)
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-12
    return ir, echoes


def reverb(x, sec, rng, tau, wet, lo=60.0, hi=1800.0, pre=0.03, echoes=()):
    """x + wet * (x convolved with the tail); output is len(x) + sec long"""
    ir, _ = tail_ir(sec, rng, tau, lo, hi, pre)
    out = np.concatenate([x, np.zeros(len(ir))])
    w = signal.fftconvolve(x, ir)
    w = np.concatenate([w, np.zeros(len(out) - len(w))])
    out = out + wet * w * (np.max(np.abs(x)) / (np.max(np.abs(w)) + 1e-12))
    for delay, gain, f in echoes:
        d = int(delay * SR)
        e = lp(x, f) * gain
        m = min(len(e), len(out) - d)
        if m > 0: out[d:d + m] += e[:m]
    return out


def clip(x, drive=1.0):
    return np.tanh(x * drive) / np.tanh(drive)


def fade_out(x, sec):
    n = min(len(x), int(SR * sec))
    x = x.copy(); x[-n:] *= np.linspace(1, 0, n) ** 2
    return x


def fade_in(x, sec):
    n = min(len(x), int(SR * sec))
    x = x.copy(); x[:n] *= np.linspace(0, 1, n)
    return x


def norm(x, peak=0.92):
    return x / (np.max(np.abs(x)) + 1e-12) * peak


def place(buf, x, at):
    i = int(at * SR); m = min(len(x), len(buf) - i)
    if m > 0: buf[i:i + m] += x[:m]


# ---------------------------------------------------------------- wav output
def wav_bytes(x, loop=False):
    """x: (n,) mono or (n, 2) stereo float -1..1. loop=True adds cue + smpl markers over the whole file."""
    x = np.asarray(x, float)
    ch = 1 if x.ndim == 1 else x.shape[1]
    pcm = np.clip(np.round(x * 32767.0), -32768, 32767).astype('<i2').tobytes(); n = len(x)
    fmt = struct.pack('<HHIIHH', 1, ch, SR, SR * 2 * ch, 2 * ch, 16)
    chunks = b'fmt ' + struct.pack('<I', len(fmt)) + fmt
    if loop:
        cue = struct.pack('<I', 1) + struct.pack('<II4sIII', 1, 0, b'data', 0, 0, 0)
        smpl = struct.pack('<9I', 0, 0, int(1e9 / SR), 60, 0, 0, 0, 1, 0) + struct.pack('<6I', 1, 0, 0, n - 1, 0, 0)
        chunks += b'cue ' + struct.pack('<I', len(cue)) + cue + b'smpl' + struct.pack('<I', len(smpl)) + smpl
    chunks += b'data' + struct.pack('<I', len(pcm)) + pcm
    return b'RIFF' + struct.pack('<I', 4 + len(chunks)) + b'WAVE' + chunks


SOUNDS = {}      # name -> (array, loop, expectations)


def add(name, x, loop=False, **expect):
    x = np.asarray(x, float)
    if not loop:                                  # one-shots: 3 ms in, 12 ms out, so a retrigger never clicks
        x = x.copy(); a = int(SR * 0.003); b = int(SR * 0.012)
        ra = np.linspace(0, 1, a); rb = np.linspace(1, 0, b)
        if x.ndim == 1: x[:a] *= ra; x[-b:] *= rb
        else: x[:a] *= ra[:, None]; x[-b:] *= rb[:, None]
    x = x - np.mean(x, axis=0)
    SOUNDS[name] = (norm(x), loop, expect)


# ================================================================ helicopter
def make_rotor(rng):
    """2.0 s loop. Blade pass 11 Hz (22 slaps in the loop, whole cycles), every other slap a touch stronger (5.5 Hz rotor
    asymmetry), tail rotor buzz at 110 Hz, wash noise breathing with the blades."""
    L = 2.0; n = int(SR * L); t = np.arange(n) / SR
    bpf = 11.0
    ph = (t * bpf) % 1.0                                             # 0..1 inside each blade pass
    alt = 1.0 + 0.16 * np.cos(2 * np.pi * 5.5 * t)                   # alternate blades
    # the slap: a steep pressure pulse; built from harmonics of the blade pass so it is periodic by construction
    slap = np.zeros(n)
    for k in range(1, 70):                                           # the 11 Hz fundamental itself is below hearing: the
        fk = k * bpf                                                 # energy sits in harmonics 5-40 (55-450 Hz), in phase = a pulse
        a = (fk / 85.0) ** 1.3 / (1.0 + (fk / 85.0) ** 2.6) * np.exp(-(fk / 620.0) ** 2)
        slap += a * np.cos(2 * np.pi * fk * t - 0.0035 * k * k + 0.25 * np.sin(k * 1.7))
    slap *= alt
    pulse = np.exp(-ph / 0.16) * np.minimum(ph / 0.012, 1.0)         # envelope of each pass
    crack = shaped_noise(n, rng, band(160, 1500)) * pulse ** 1.6 * alt       # the "whop" body
    hiss = shaped_noise(n, rng, band(900, 5200)) * (0.25 + 0.75 * pulse)     # blade tip hiss
    wash = shaped_noise(n, rng, band(40, 320)) * (0.6 + 0.4 * np.cos(2 * np.pi * bpf * t + 1.0))
    tail = np.zeros(n)
    for k in range(1, 9):
        tail += np.sin(2 * np.pi * 110.0 * k * t + k) / k ** 1.1
    tail *= 0.5 + 0.5 * np.cos(2 * np.pi * 5.5 * t)
    whine = np.sin(2 * np.pi * 2310.0 * t) * 0.5 + np.sin(2 * np.pi * 3465.0 * t) * 0.3
    slap /= np.std(slap); tail /= np.std(tail)
    x = slap * 1.0 + crack * 1.5 + hiss * 0.10 + wash * 0.30 + tail * 0.10 + whine * 0.012
    return clip(x / np.max(np.abs(x)), 1.6)


def make_turbine(rng):
    """2.0 s loop: compressor whine (whole cycles, slow periodic vibrato), gearbox tones, exhaust roar and hiss"""
    L = 2.0; n = int(SR * L); t = np.arange(n) / SR
    vib = 0.9 * np.sin(2 * np.pi * 1.5 * t) + 0.4 * np.sin(2 * np.pi * 4.0 * t)
    x = np.zeros(n)
    for f, a in ((3150.0, 1.0), (4725.0, 0.5), (6300.0, 0.42), (9450.0, 0.16), (2100.0, 0.25)):
        x += a * np.sin(2 * np.pi * f * t + vib * (f / 3150.0))
    gear = sum(a * np.sin(2 * np.pi * f * t + i) for i, (f, a) in enumerate(((440.0, 0.5), (880.0, 0.3), (1320.0, 0.18), (660.0, 0.2))))
    roar = shaped_noise(n, rng, band(90, 700)) * (0.85 + 0.15 * np.sin(2 * np.pi * 11.0 * t))
    hiss = shaped_noise(n, rng, band(2500, 11000))
    return x * 0.30 + gear * 0.22 + roar * 0.55 + hiss * 0.34


def make_heli_gun(rng, v):
    """one 30 mm / door gun shot: 0.55 s"""
    n = int(SR * 0.42)
    crack = hn(rng, n, 900) * env(n, 0.0004, 0.010)
    body = bn(rng, n, 180, 1400) * env(n, 0.0008, 0.035 + 0.006 * v)
    thump = sweep(n, 210 - 14 * v, 62, 0.022) * env(n, 0.001, 0.07)
    t = np.arange(n) / SR
    mech = sum(np.sin(2 * np.pi * f * t + i) * env(n, 0.001, d) for i, (f, d) in enumerate(((1460 + 90 * v, 0.03), (2380, 0.02), (3710 - 120 * v, 0.014))))
    x = clip(crack * 1.0 + body * 1.2 + thump * 0.9 + mech * 0.12, 1.8)
    return reverb(x, 0.5, rng, 0.13, 0.30, 150, 3000, pre=0.02)


def make_mount_gun(rng, v):
    """heavy MG (.50 cal / DShK): a harder, lower shot than the door gun with a longer field tail"""
    n = int(SR * 0.5)
    crack = hn(rng, n, 1400) * env(n, 0.0003, 0.007)
    body = bn(rng, n, 120, 1100) * env(n, 0.0008, 0.05 + 0.008 * v)
    thump = sweep(n, 170 - 10 * v, 48, 0.03) * env(n, 0.001, 0.10)
    t = np.arange(n) / SR
    mech = sum(np.sin(2 * np.pi * f * t) * env(n, 0.002, d) for f, d in ((930 + 60 * v, 0.05), (1740, 0.03), (2890, 0.02)))
    x = clip(crack * 0.9 + body * 1.3 + thump * 1.15 + mech * 0.10, 2.2)
    return reverb(x, 0.9, rng, 0.24, 0.42, 90, 2200, pre=0.03, echoes=((0.19 + 0.02 * v, 0.10, 900),))


def whoosh(n, rng, f_start, f_end, q_lo=0.55, q_hi=1.9, tau=0.35):
    """noise through a band whose centre glides: done in blocks with overlap so the glide is smooth"""
    x = rng.normal(0, 1, n); out = np.zeros(n)
    blk = 2048; hop = 512; w = np.hanning(blk)
    for i in range(0, n - blk, hop):
        tt = i / SR
        fc = f_end + (f_start - f_end) * np.exp(-tt / tau)
        seg = np.fft.rfft(x[i:i + blk] * w)
        f = np.fft.rfftfreq(blk, 1.0 / SR)
        seg *= band(fc * q_lo, fc * q_hi)(f)
        out[i:i + blk] += np.fft.irfft(seg, blk) * w
    return out / (np.std(out) + 1e-12)


def make_rocket_launch(rng, v):
    """air rocket leaving the pod: bang of the igniter, a rasping whoosh pulling away (1.3 s)"""
    n = int(SR * 1.3); t = np.arange(n) / SR
    bang = bn(rng, n, 200, 3000) * env(n, 0.0006, 0.022)
    thump = sweep(n, 150, 55, 0.03) * env(n, 0.001, 0.06)
    w = whoosh(n, rng, 2600 + 300 * v, 520, tau=0.30) * env(n, 0.012, 0.36, hold=0.05)
    rasp = 1.0 + 0.35 * np.sign(np.sin(2 * np.pi * (140 + 20 * v) * t)) * np.exp(-t / 0.5)
    lowr = bn(rng, n, 70, 300) * env(n, 0.02, 0.30)
    x = clip(bang * 1.0 + thump * 0.8 + w * rasp * 0.75 + lowr * 0.5, 1.5)
    return fade_out(reverb(x, 0.6, rng, 0.2, 0.22, 200, 4000), 0.25)


def make_rocket_fly(rng):
    """4 s motor roar with flutter, fading over the last 1.2 s"""
    n = int(SR * 4.0); t = np.arange(n) / SR
    roar = bn(rng, n, 140, 2400)
    flut = 1.0 + 0.28 * np.sin(2 * np.pi * 37 * t + 3 * np.sin(2 * np.pi * 2.3 * t)) + 0.18 * ln(rng, n, 14)
    hiss = hn(rng, n, 3000) * 0.10
    tone = np.sin(2 * np.pi * np.cumsum(310 - 40 * t / 4.0) / SR) * 0.12
    x = clip((roar * flut + hiss + tone) * 0.5, 1.4)
    return fade_out(fade_in(x, 0.03), 1.2)


# ================================================================ artillery
def make_howitzer(rng, v):
    """105 mm: the crack, the chest thump, the breech ring, then the report rolling round the valley (about 4.5 s)"""
    n = int(SR * 1.3); t = np.arange(n) / SR
    crack = rng.normal(0, 1, n) * env(n, 0.0003, 0.012)
    blast = bn(rng, n, 70, 900) * env(n, 0.001, 0.11)
    boom = sweep(n, 170 - 10 * v, 44, 0.08) * env(n, 0.002, 0.40)
    sub = np.sin(2 * np.pi * (47 - 3 * v) * t + 0.4) * env(n, 0.006, 0.50)
    ring = sum(np.sin(2 * np.pi * f * t + i) * env(n, 0.002, d) for i, (f, d) in enumerate(((312 + 9 * v, 0.24), (741, 0.16), (1183, 0.11), (1978, 0.06))))
    dust = bn(rng, n, 300, 2400) * env(n, 0.05, 0.25) * 0.5
    punch = bn(rng, n, 350, 2800) * env(n, 0.0006, 0.07)
    x = clip(crack * 1.3 + punch * 1.5 + blast * 1.9 + boom * 0.9 + sub * 0.45 + ring * 0.16 + dust * 0.25, 2.6)
    x = reverb(x, 3.4, rng, 0.95, 0.55, 45, 1700, pre=0.05,
               echoes=((0.42 + 0.05 * v, 0.24, 500), (0.95, 0.15, 320), (1.62 - 0.1 * v, 0.10, 220), (2.4, 0.06, 160)))
    return fade_out(x, 1.2)


def make_rocket_fire(rng, v):
    """122 mm rail launch: ignition crack, a tearing roar that climbs away, back-blast rumble (about 3.6 s)"""
    n = int(SR * 2.4); t = np.arange(n) / SR
    crack = rng.normal(0, 1, n) * env(n, 0.0004, 0.016)
    bang = sweep(n, 130, 44, 0.05) * env(n, 0.002, 0.20)
    w = whoosh(n, rng, 3400 - 250 * v, 340, q_lo=0.4, q_hi=2.4, tau=0.55) * env(n, 0.02, 0.62, hold=0.12)
    tear = 1.0 + 0.45 * np.sign(np.sin(2 * np.pi * np.cumsum(96 + 70 * np.exp(-t / 0.4)) / SR)) * np.exp(-t / 0.9)
    rumble = bn(rng, n, 45, 260) * env(n, 0.03, 0.7)
    x = clip(crack * 0.9 + bang * 1.3 + w * tear * 1.0 + rumble * 0.9, 2.0)
    x = reverb(x, 2.4, rng, 0.8, 0.40, 50, 1400, pre=0.05, echoes=((0.5, 0.16, 500), (1.1 + 0.1 * v, 0.10, 300)))
    return fade_out(x, 1.0)


def make_whistle(rng):
    """2.0 s: a falling, swelling whistle with air rush; its loudest point is the end (the shell arrives)"""
    n = int(SR * 2.0); t = np.arange(n) / SR; u = t / t[-1]
    f = 1750 - 1020 * u ** 1.35 + 14 * np.sin(2 * np.pi * 6.5 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    amp = 0.10 + 0.90 * u ** 2.3
    tone = np.sin(ph) * 0.8 + np.sin(2.005 * ph) * 0.14 + np.sin(3.01 * ph) * 0.05
    air = np.zeros(n)
    blk = 2048; hop = 512; w = np.hanning(blk); nz = rng.normal(0, 1, n)
    for i in range(0, n - blk, hop):                      # air rush: noise that follows the whistle's pitch
        fc = f[i + blk // 2]
        seg = np.fft.rfft(nz[i:i + blk] * w); ff = np.fft.rfftfreq(blk, 1.0 / SR)
        air[i:i + blk] += np.fft.irfft(seg * band(fc * 0.6, fc * 2.2)(ff), blk) * w
    air /= np.std(air) + 1e-12
    x = (tone + air * 0.30) * amp
    x[-int(SR * 0.02):] *= np.linspace(1, 0, int(SR * 0.02))
    return x


def make_impact(rng, v):
    """HE burst: crack, boom, the ground thump, debris and dirt coming down, valley tail (about 4.2 s)"""
    n = int(SR * 1.9); t = np.arange(n) / SR
    crack = rng.normal(0, 1, n) * env(n, 0.0003, 0.010 + 0.002 * v)
    blast = bn(rng, n, 80, 1500) * env(n, 0.001, 0.13)
    boom = sweep(n, 110 - 8 * v, 34, 0.06) * env(n, 0.002, 0.34 + 0.04 * v)
    sub = np.sin(2 * np.pi * (41 - 2 * v) * t) * env(n, 0.005, 0.42)
    # debris: sparse clods and stones landing between 0.25 and 1.6 s
    deb = np.zeros(n)
    for _ in range(90 + 20 * v):
        at = 0.18 + rng.gamma(2.2, 0.26)
        if at > 1.75: continue
        m = int(SR * rng.uniform(0.012, 0.05))
        clod = bp(rng.normal(0, 1, m + 64), rng.uniform(250, 900), rng.uniform(1500, 5200))[:m] * env(m, 0.0006, m / SR / 4)
        place(deb, clod * rng.uniform(0.2, 1.0) * np.exp(-at / 0.7), at)
    rain = hn(rng, n, 1800) * env(n, 0.25, 0.42) * 0.35
    punch = bn(rng, n, 300, 3200) * env(n, 0.0006, 0.09)
    x = clip(crack * 1.3 + punch * 1.6 + blast * 1.9 + boom * 0.85 + sub * 0.4 + deb * 0.9 + rain * 0.30, 2.4)
    x = reverb(x, 2.6, rng, 0.75, 0.50, 50, 1900, pre=0.05, echoes=((0.37 + 0.06 * v, 0.20, 450), (0.9, 0.12, 280), (1.5, 0.07, 190)))
    return fade_out(x, 1.0)


# ================================================================ stingers (2D)
def brass(freq, dur, rng, bright=1.0, vib=5.2):
    """a small horn section: detuned saws through a filter that opens with the attack"""
    n = int(SR * dur); t = np.arange(n) / SR
    x = np.zeros(n)
    for det in (-0.006, 0.0, 0.005):
        f = freq * (1 + det) * (1 + 0.004 * np.sin(2 * np.pi * vib * t + rng.uniform(0, 6)) * np.minimum(t / 0.3, 1))
        ph = np.cumsum(f) / SR
        for k in range(1, 15):
            if k * freq > 9000: break
            x += np.sin(2 * np.pi * k * ph) / k * (1.0 if k % 2 else 0.8)
    a = np.minimum(t / 0.035, 1.0) * np.minimum((dur - t) / 0.09, 1.0).clip(0) * (0.82 + 0.18 * np.exp(-t / 0.25))
    dark = lp(x, 900 * bright); open_ = lp(x, 3600 * bright)
    mix = np.minimum(t / 0.08, 1.0)
    return (dark * (1 - 0.7 * mix) + open_ * 0.7 * mix) * a


def drum(rng, f0=92.0, dec=0.32):
    n = int(SR * 0.9)
    return sweep(n, f0 * 1.9, f0, 0.02) * env(n, 0.002, dec) + bn(rng, n, 90, 700) * env(n, 0.001, 0.05) * 0.5


def snare_roll(rng, dur, rate=26.0):
    n = int(SR * dur); out = np.zeros(n + SR)
    k = 0; at = 0.0
    while at < dur:
        m = int(SR * 0.07)
        hit = (hp(rng.normal(0, 1, m), 1500) * 0.7 + np.sin(2 * np.pi * 190 * np.arange(m) / SR) * 0.5) * env(m, 0.001, 0.016)
        place(out, hit * (0.35 + 0.65 * at / dur) * (1.0 if k % 2 == 0 else 0.75), at)
        at += 1.0 / rate; k += 1
    return out[:n]


def make_capture(rng):
    """flag taken: a short snare pickup, then a rising three-note horn call landing on an open fifth with a drum (1.9 s)"""
    out = np.zeros(int(SR * 1.5))
    place(out, snare_roll(rng, 0.26) * 0.35, 0.0)
    D4, A4, D5, FS5 = 293.66, 440.0, 587.33, 739.99
    place(out, brass(D4, 0.17, rng) * 0.8, 0.24)
    place(out, brass(A4, 0.17, rng) * 0.85, 0.41)
    for f, g in ((D5, 1.0), (A4, 0.6), (FS5, 0.45), (D4 / 2, 0.5)):
        place(out, brass(f, 0.78, rng, bright=1.15) * g, 0.58)
    place(out, drum(rng) * 1.5, 0.58)
    place(out, drum(rng, 120, 0.2) * 0.8, 0.24)
    x = reverb(out, 0.9, rng, 0.35, 0.22, 200, 5000, pre=0.02)
    return fade_out(x, 0.5)


def make_flag_lost(rng):
    """flag lost: two falling low horn notes over a dull drum, minor (1.9 s)"""
    out = np.zeros(int(SR * 1.5))
    D4, BF3, G3, D3 = 293.66, 233.08, 196.0, 146.83
    place(out, drum(rng, 70, 0.45) * 1.6, 0.0)
    for f, g in ((D4, 0.9), (BF3, 0.5)):
        place(out, brass(f, 0.36, rng, bright=0.7) * g, 0.02)
    for f, g in ((G3, 1.0), (BF3, 0.55), (D3 / 2, 0.6), (D3, 0.5)):
        place(out, brass(f, 0.95, rng, bright=0.6, vib=4.2) * g, 0.42)
    place(out, drum(rng, 62, 0.5) * 1.3, 0.42)
    x = reverb(out, 1.0, rng, 0.45, 0.28, 120, 3000, pre=0.02)
    return fade_out(x, 0.6)


def make_radio(rng):
    """radio key-up: squelch burst, a short tone, the tail of static (0.36 s)"""
    n = int(SR * 0.36); t = np.arange(n) / SR
    sq = bn(rng, n, 450, 3200) * (env(n, 0.002, 0.03) + 0.9 * np.exp(-((t - 0.27) / 0.035) ** 2))
    beep = np.sin(2 * np.pi * 1320 * t) * ((t > 0.06) & (t < 0.17)) * np.minimum((t - 0.06) / 0.004, 1).clip(0) * np.minimum((0.17 - t) / 0.006, 1).clip(0)
    click = np.zeros(n); click[int(0.002 * SR)] = 1.0; click = bp(click, 800, 4000) * 30
    x = bp(clip(sq * 0.6 + beep * 0.75 + click * 0.3, 1.5), 350, 3600)        # the whole thing through a "speaker"
    return x


# ================================================================ ambience
def make_cicadas(rng):
    """12 s stereo loop: evening cicada chorus (several insects, each a rasping carrier, swelling at its own pace),
    a bed of leaf hiss and high crickets. Everything periodic over the loop."""
    L = 12.0; n = int(SR * L); t = np.arange(n) / SR
    out = np.zeros((n, 2))
    voices = [(4300, 900, 92, 1, 0.9), (5600, 1100, 134, 2, 0.7), (3600, 700, 61, 1, 0.55), (6900, 1300, 171, 3, 0.5),
              (4900, 800, 108, 2, 0.6), (8200, 1500, 212, 4, 0.3)]
    for i, (fc, bw, rasp, swells, g) in enumerate(voices):
        car = shaped_noise(n, rng, band(fc - bw / 2, fc + bw / 2, soft=0.1))
        am = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * rasp * t + i)) * 0.85                       # the rasp (whole cycles: rasp * 12 is an integer)
        swell = (0.5 + 0.5 * np.sin(2 * np.pi * swells / L * t + rng.uniform(0, 6))) ** 2 * 0.85 + 0.15
        v = car * am * swell * g
        pan = 0.5 + 0.38 * np.cos(i * 2.4)
        out[:, 0] += v * np.sqrt(1 - pan); out[:, 1] += v * np.sqrt(pan)
    for c in range(2):
        hiss = shaped_noise(n, rng, band(1800, 9000)) * (0.8 + 0.2 * np.sin(2 * np.pi * (c + 1) / L * t + c))
        crick = shaped_noise(n, rng, band(7400, 7900, soft=0.05)) * (np.sin(2 * np.pi * (4.0 + c * 0.5) * t) > 0.55) * (0.5 + 0.5 * np.sin(2 * np.pi * 33 * t) > 0.5)
        lowwind = shaped_noise(n, rng, band(80, 500)) * (0.7 + 0.3 * np.sin(2 * np.pi * (2 - c) / L * t + 1.3 * c))
        out[:, c] += hiss * 0.10 + crick * 0.22 + lowwind * 0.16
    return out


def make_river(rng):
    """10 s stereo loop: broad water rush with slow surges and a bubbling upper layer"""
    L = 10.0; n = int(SR * L); t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for c in range(2):
        rush = shaped_noise(n, rng, band(220, 2600))
        deep = shaped_noise(n, rng, band(60, 320))
        gurg = shaped_noise(n, rng, band(900, 3800)) * (0.55 + 0.45 * shaped_noise(n, rng, band(1.5, 9.0)).clip(-2, 2) / 2)
        surge = 0.82 + 0.18 * np.sin(2 * np.pi * (1 + c) / L * t + 2.0 * c)
        out[:, c] = (rush * 0.6 + deep * 0.35 + gurg * 0.4) * surge
    return out


def chirp(dur, f0, f1, rng, harm=0.25, vib=0.0, vibf=28.0, curve=1.0):
    n = int(SR * dur); t = np.arange(n) / SR; u = (t / dur) ** curve
    f = f0 + (f1 - f0) * u + vib * np.sin(2 * np.pi * vibf * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    a = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.6
    return (np.sin(ph) + harm * np.sin(2 * ph) + harm * 0.4 * np.sin(3 * ph)) * a


def distant(x, rng, sec=1.2, tau=0.35, wet=0.5, lo=300, hi=6000):
    return fade_out(reverb(x, sec, rng, tau, wet, lo, hi, pre=0.03), 0.4)


def make_birds(rng):
    """six jungle calls (each its own file): koel, barbet, bulbul phrase, parakeet screech, coucal boom, a far whooping call"""
    calls = []
    # koel: rising two-note "ko-EL", repeated and climbing
    x = np.zeros(int(SR * 4.2))
    for k in range(5):
        base = 780 * (1 + 0.035 * k)
        place(x, chirp(0.16, base, base * 1.03, rng, 0.2) * 0.6, 0.1 + k * 0.78)
        place(x, chirp(0.36, base * 1.05, base * 1.52, rng, 0.2, curve=0.6) * (0.7 + 0.07 * k), 0.30 + k * 0.78)
    calls.append(distant(x, rng))
    # barbet: steady hollow "tonk tonk tonk"
    x = np.zeros(int(SR * 3.4))
    for k in range(11):
        note = chirp(0.085, 1130, 1010, rng, 0.08) * env(int(SR * 0.085), 0.004, 0.03)
        place(x, note, 0.1 + k * 0.29)
    calls.append(distant(x, rng, wet=0.6))
    # bulbul: quick bright phrase
    x = np.zeros(int(SR * 2.0))
    seq = [(2600, 3300, .07), (3300, 2500, .09), (2900, 3900, .06), (3900, 3000, .11), (2400, 2700, .07), (3200, 4200, .10), (4200, 2800, .14)]
    at = 0.1
    for rep in range(2):
        for f0, f1, d in seq:
            place(x, chirp(d, f0, f1, rng, 0.12) * rng.uniform(0.6, 1.0), at); at += d + rng.uniform(0.02, 0.06)
        at += 0.35
    calls.append(distant(x, rng, tau=0.25, wet=0.4, lo=800, hi=9000))
    # parakeets: harsh screeches passing over
    x = np.zeros(int(SR * 2.6))
    for k in range(7):
        d = rng.uniform(0.09, 0.2)
        s = chirp(d, rng.uniform(2700, 3300), rng.uniform(2300, 2900), rng, 0.6, vib=420, vibf=rng.uniform(70, 110))
        place(x, s * rng.uniform(0.5, 1.0), 0.1 + k * 0.3 + rng.uniform(0, 0.12))
    calls.append(distant(x, rng, tau=0.3, wet=0.45, lo=900, hi=8000))
    # coucal: deep hollow booming series that falls and slows
    x = np.zeros(int(SR * 5.0))
    at = 0.1
    for k in range(13):
        f = 430 - 9 * k
        place(x, chirp(0.15, f * 1.08, f * 0.92, rng, 0.1) * (0.6 + 0.4 * np.sin(np.pi * k / 12)), at)
        at += 0.23 + 0.012 * k
    calls.append(distant(x, rng, sec=1.6, tau=0.5, wet=0.7, lo=150, hi=3000))
    # a far whooping call (gibbon-like great call): slow rising whoops that speed up
    x = np.zeros(int(SR * 6.0))
    at = 0.1; gap = 0.8
    for k in range(10):
        d = max(0.22, 0.55 - 0.035 * k)
        place(x, chirp(d, 620 + 22 * k, 1150 + 60 * k, rng, 0.3, curve=1.6) * (0.5 + 0.05 * k), at)
        at += gap; gap = max(0.3, gap * 0.86)
    calls.append(distant(x, rng, sec=1.8, tau=0.6, wet=0.8, lo=300, hi=4000))
    return calls


def make_gecko(rng):
    """tokay gecko: a rattling wind-up then "to-KAY" five times, slowing and sinking"""
    x = np.zeros(int(SR * 6.2))
    t0 = 0.1
    for k in range(9):                                                 # the wind-up cackle
        m = int(SR * 0.045)
        place(x, bp(rng.normal(0, 1, m + 64), 900, 2600)[:m] * env(m, 0.002, 0.012) * (0.3 + 0.05 * k), t0 + k * 0.075)
    at = 1.0
    for k in range(5):
        fa = 1250 - 60 * k
        n1 = int(SR * 0.11); tt = np.arange(n1) / SR
        to = np.sin(2 * np.pi * np.cumsum(np.full(n1, fa)) / SR) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 95 * tt))) * env(n1, 0.004, 0.05)
        n2 = int(SR * 0.30); tt = np.arange(n2) / SR
        f = fa * 0.78 - 190 * (tt / 0.30)
        kay = (np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.4 * np.sin(4 * np.pi * np.cumsum(f) / SR)) * (0.55 + 0.45 * np.sign(np.sin(2 * np.pi * 70 * tt))) * env(n2, 0.006, 0.14)
        g = 1.0 - 0.1 * k
        place(x, bp(to, 500, 4000) * 0.6 * g, at); place(x, bp(kay, 400, 3500) * g, at + 0.2)
        at += 0.82 + 0.07 * k
    return distant(x, rng, sec=1.0, tau=0.25, wet=0.35, lo=300, hi=5000)


def make_frogs(rng):
    """three files: a paddy chorus (many small frogs answering each other), slow deep croaks, a rain-frog trill"""
    out = []
    x = np.zeros(int(SR * 7.0))
    for v in range(7):                                                # chorus
        f = rng.uniform(1900, 3100); rate = rng.uniform(2.6, 4.2); ph0 = rng.uniform(0, 1); g = rng.uniform(0.3, 1.0)
        k = 0
        while True:
            at = 0.1 + (k + ph0) / rate + rng.uniform(-0.02, 0.02)
            if at > 6.4: break
            if 0.25 < (at / 7.0 * (1 + v * 0.13)) % 1.0:              # each frog rests part of the time
                place(x, chirp(0.06, f * 0.9, f * 1.12, rng, 0.15) * g, at)
            k += 1
    out.append(distant(x, rng, tau=0.3, wet=0.45, lo=600, hi=7000))
    x = np.zeros(int(SR * 5.0))
    at = 0.15
    for k in range(6):                                                # bullfrog-like croaks: pulsed low tone
        d = rng.uniform(0.32, 0.5); n = int(SR * d); t = np.arange(n) / SR
        f = rng.uniform(190, 240)
        cro = sum(np.sin(2 * np.pi * f * h * t) / h for h in (1, 2, 3, 4, 5)) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 34 * t))) * np.sin(np.pi * t / d) ** 0.5
        place(x, bp(cro, 120, 1600) * rng.uniform(0.6, 1.0), at); at += d + rng.uniform(0.25, 0.6)
    out.append(distant(x, rng, sec=1.3, tau=0.4, wet=0.5, lo=100, hi=2500))
    x = np.zeros(int(SR * 4.6))
    for k in range(3):                                                # trills
        d = rng.uniform(0.8, 1.2); n = int(SR * d); t = np.arange(n) / SR
        tr = np.sin(2 * np.pi * (2450 + 60 * k) * t) * (np.sin(2 * np.pi * 22 * t) > 0) * np.sin(np.pi * t / d) ** 0.4
        place(x, tr * (0.7 + 0.15 * k), 0.1 + k * 1.5)
    out.append(distant(x, rng, tau=0.3, wet=0.5, lo=800, hi=6000))
    return out


def make_thunder(rng, v):
    """distant monsoon thunder: a low rolling rumble with a few swells (6-8 s)"""
    L = 6.0 + v; n = int(SR * L); t = np.arange(n) / SR
    e = np.zeros(n)
    for _ in range(4 + v):
        c = rng.uniform(0.3, L * 0.6); w = rng.uniform(0.25, 0.9)
        e += rng.uniform(0.4, 1.0) * np.exp(-0.5 * ((t - c) / w) ** 2) * (t > c - 2 * w)
    e = e * np.exp(-t / (L * 0.55)) + 0.25 * np.exp(-t / (L * 0.4))
    rum = ln(rng, n, 110 + 20 * v, 3) + bn(rng, n, 100, 420) * 0.30 * np.exp(-t / 1.5)
    wob = 1 + 0.35 * ln(rng, n, 5)
    x = rum * e * wob
    return fade_out(fade_in(reverb(x, 2.0, rng, 0.8, 0.5, 30, 300), 0.25), 1.8)


def make_far_guns(rng, v):
    """artillery a few valleys away: 1-4 dull thumps with their echoes"""
    x = np.zeros(int(SR * 3.2))
    shots = [1, 2, 3, 4][v % 4]
    at = 0.1
    for k in range(shots):
        n = int(SR * 0.9)
        th = sweep(n, 70, 34, 0.06) * env(n, 0.012, 0.22) + ln(rng, n, 260) * env(n, 0.015, 0.16) * 0.5
        place(x, th * rng.uniform(0.7, 1.0), at)
        at += rng.uniform(0.28, 0.75)
    return fade_out(reverb(lp(x, 480), 2.2, rng, 0.8, 0.7, 30, 420, pre=0.08, echoes=((0.6, 0.3, 260), (1.3, 0.18, 180))), 1.2)


# ================================================================ build all
def build():
    R = np.random.RandomState
    add('heli_rotor', make_rotor(R(11)), loop=True, low=(0.55, 40, 500), centroid=(90, 900))
    add('heli_turbine', make_turbine(R(12)), loop=True, centroid=(1500, 6500), high=(0.25, 2000, 12000))
    for v in range(3): add('heli_gun_%d' % (v + 1), make_heli_gun(R(20 + v), v), centroid=(200, 3500), mid=(0.15, 500, 8000), dur=(0.5, 1.1))
    for v in range(3): add('mount_gun_%d' % (v + 1), make_mount_gun(R(30 + v), v), low=(0.25, 20, 300), mid=(0.10, 500, 8000), dur=(0.9, 1.6))
    for v in range(2): add('rocket_launch_%d' % (v + 1), make_rocket_launch(R(40 + v), v), centroid=(500, 3500), dur=(1.4, 2.2))
    add('rocket_fly', make_rocket_fly(R(45)), centroid=(500, 4000), dur=(3.9, 4.1))
    for v in range(2): add('howitzer_fire_%d' % (v + 1), make_howitzer(R(50 + v), v), low=(0.5, 20, 200), mid=(0.04, 400, 8000), dur=(4.0, 5.2), tail=0.02)
    for v in range(2): add('rocket_fire_%d' % (v + 1), make_rocket_fire(R(55 + v), v), centroid=(200, 2500), dur=(4.0, 5.2))
    add('shell_whistle', make_whistle(R(60)), centroid=(700, 2200), dur=(1.98, 2.02), late=True)
    for v in range(3): add('shell_impact_%d' % (v + 1), make_impact(R(65 + v), v), low=(0.4, 20, 200), mid=(0.06, 400, 8000), dur=(4.0, 5.0), tail=0.012)
    add('capture', make_capture(R(70)), centroid=(350, 2600), dur=(1.8, 2.6))
    add('flag_lost', make_flag_lost(R(71)), centroid=(120, 1200), dur=(1.8, 2.7))
    add('radio_blip', make_radio(R(72)), centroid=(800, 2600), dur=(0.3, 0.4))
    add('amb_cicadas', make_cicadas(R(80)), loop=True, centroid=(3000, 8000), high=(0.6, 2500, 12000))
    add('amb_river', make_river(R(81)), loop=True, centroid=(350, 2400))
    for i, c in enumerate(make_birds(R(82))): add('amb_bird_%d' % (i + 1), c, centroid=(300, 5000))
    add('amb_gecko', make_gecko(R(83)), centroid=(500, 2800))
    for i, c in enumerate(make_frogs(R(84))): add('amb_frog_%d' % (i + 1), c, centroid=(200, 4200))
    for v in range(3): add('amb_thunder_%d' % (v + 1), make_thunder(R(86 + v), v), low=(0.85, 15, 250), centroid=(20, 220))
    for v in range(4): add('amb_guns_%d' % (v + 1), make_far_guns(R(90 + v), v), low=(0.85, 15, 300), centroid=(20, 260))


# ================================================================ numeric listen-check
def analyse(name, x, loop, expect):
    """peak / RMS / crest, spectrum (centroid, band shares), loop seam, start / end levels. Returns (row, problems)."""
    mono = x if x.ndim == 1 else x.mean(axis=1)
    n = len(mono); prob = []
    peak = float(np.max(np.abs(x))); rms = float(np.sqrt(np.mean(mono ** 2)))
    spec = np.abs(np.fft.rfft(mono * np.hanning(n))) ** 2; f = np.fft.rfftfreq(n, 1.0 / SR)
    tot = spec.sum() + 1e-20
    cen = float((spec * f).sum() / tot)
    share = lambda lo, hi: float(spec[(f >= lo) & (f < hi)].sum() / tot)
    row = dict(seconds=round(n / SR, 3), channels=1 if x.ndim == 1 else 2, peak_dbfs=round(20 * np.log10(peak + 1e-12), 2),
               rms_dbfs=round(20 * np.log10(rms + 1e-12), 2), crest_db=round(20 * np.log10(peak / (rms + 1e-12)), 1), centroid_hz=round(cen),
               bands=dict(sub_120=round(share(0, 120), 3), low_500=round(share(120, 500), 3), mid_2k=round(share(500, 2000), 3),
                          high_8k=round(share(2000, 8000), 3), air=round(share(8000, 22050), 3)),
               dc=round(float(abs(np.mean(mono))), 5), loop=loop)
    if peak > 0.99: prob.append('clips (peak %.3f)' % peak)
    if peak < 0.5: prob.append('too quiet (peak %.3f)' % peak)
    if abs(np.mean(mono)) > 0.01: prob.append('dc offset %.4f' % np.mean(mono))
    if rms < 10 ** (-40 / 20): prob.append('rms %.1f dBFS: nearly silent' % row['rms_dbfs'])
    if loop:
        ch = x[:, None] if x.ndim == 1 else x
        worst = 0.0; worst2 = 0.0
        for c in range(ch.shape[1]):
            y = ch[:, c]; d = np.abs(np.diff(y))
            seam = abs(y[0] - y[-1])                                   # the step the engine plays when it wraps
            p999 = float(np.percentile(d, 99.9)) + 1e-9
            worst = max(worst, seam / p999)
            # second difference across the seam against the file's own (a slope kink also clicks)
            dd = np.abs(np.diff(y, 2)); k = abs((y[1] - y[0]) - (y[0] - y[-1]))
            worst2 = max(worst2, k / (float(np.percentile(dd, 99.9)) + 1e-9))
        # level before / after the seam (a loop that was faded would dip here)
        a = np.sqrt(np.mean(mono[:SR // 4] ** 2)); b = np.sqrt(np.mean(mono[-SR // 4:] ** 2))
        row.update(seam_step_vs_p999=round(worst, 3), seam_kink_vs_p999=round(worst2, 3), seam_level_db=round(20 * np.log10((a + 1e-9) / (b + 1e-9)), 2))
        if worst > 1.0: prob.append('loop seam step %.2f x the 99.9th percentile sample step: it would click' % worst)
        if worst2 > 1.5: prob.append('loop seam slope kink %.2f x' % worst2)
        if min(a, b) < 0.25 * rms: prob.append('level dips at the loop seam')
    else:
        head = float(np.max(np.abs(mono[:8]))); tail = float(np.max(np.abs(mono[-64:])))
        row.update(start_abs=round(head, 4), end_abs=round(tail, 4))
        if head > 0.05: prob.append('starts with a step (%.3f)' % head)
        if tail > 0.02: prob.append('ends with a step (%.3f)' % tail)
    if 'centroid' in expect and not (expect['centroid'][0] <= cen <= expect['centroid'][1]):
        prob.append('spectral centroid %.0f Hz outside %s' % (cen, expect['centroid']))
    for key in ('low', 'high', 'mid'):
        if key in expect:
            frac, lo, hi = expect[key]
            if share(lo, hi) < frac: prob.append('only %.2f of the energy in %d-%d Hz (want >= %.2f)' % (share(lo, hi), lo, hi, frac))
    if 'dur' in expect and not (expect['dur'][0] <= n / SR <= expect['dur'][1]):
        prob.append('length %.2f s outside %s' % (n / SR, expect['dur']))
    if expect.get('late'):                                              # energy must sit at the end (the whistle)
        q = np.sqrt(np.mean(mono[-n // 4:] ** 2)) / (np.sqrt(np.mean(mono[:n // 4] ** 2)) + 1e-9)
        row['late_ratio'] = round(float(q), 1)
        if q < 3: prob.append('does not swell toward the end (%.1f x)' % q)
    if 'tail' in expect:                                                # a long tail: still audible 2 s in
        i = int(2.0 * SR); lvl = float(np.sqrt(np.mean(mono[i:i + SR // 4] ** 2))) if n > i + SR // 4 else 0.0
        row['rms_at_2s'] = round(lvl, 4)
        if lvl < expect['tail']: prob.append('tail too short (rms %.4f at 2 s)' % lvl)
    return row, prob


# ================================================================ events
def files(stem, n=None):
    return ['sounds/mv/%s.vsnd' % stem] if n is None else ['sounds/mv/%s_%d.vsnd' % (stem, i + 1) for i in range(n)]


def ev3d(name, fl, volume, pts, pitch=None, extra=()):
    """csgo_mega with an explicit distance curve [(distance, volume)]"""
    lines = ['type = "csgo_mega"', 'volume = %.2f' % volume, 'pitch = 1.00', 'use_time_volume_mapping_curve = false']
    if len(fl) == 1: lines.append('vsnd_files_track_01 = "%s"' % fl[0])
    else: lines += ['vsnd_files_track_01 =', '['] + ['\t"%s",' % f for f in fl] + [']']
    if pitch: lines += ['pitch_random_min = %.2f' % pitch[0], 'pitch_random_max = %.2f' % pitch[1]]
    lines += list(extra) + ['distance_volume_mapping_curve ='] + E.curve(pts)
    return E._event(name, lines)


def ev2d(name, fl, volume):
    """heard everywhere at the same volume (stingers): flat curves, no occlusion (sound.md, the flat csgo_mega form)"""
    return E._event(name, ['type = "csgo_mega"', 'volume = %.2f' % volume, 'pitch = 1.00', 'use_time_volume_mapping_curve = false',
                           'vsnd_files_track_01 = "%s"' % fl[0], 'occlusion_intensity = 0.0', 'distance_effect_mix = 0.0',
                           'restrict_source_reverb = true', 'use_distance_unfiltered_stereo_mapping_curve = true',
                           'distance_volume_mapping_curve ='] + E.curve([(0, 1), (100000, 1)]) +
                    ['distance_unfiltered_stereo_mapping_curve ='] + E.curve([(0, 1), (100000, 1)]))


def ev_loop(name, fl, volume):
    return E._event(name, ['base = "amb.looping.stereo.base"', 'volume = %.2f' % volume, 'vsnd_files_track_01 = "%s"' % fl[0]])


def ev_rand(name, fl, volume, rmin, rmax, imin, imax, pitch=(0.96, 1.04)):
    return E._event(name, ['base = "amb.intermittent.randomAroundPlayer.base"', 'volume = %.2f' % volume,
                           'randomize_position_min_radius = %.1f' % rmin, 'randomize_position_max_radius = %.1f' % rmax,
                           'retrigger_interval_min = %.1f' % imin, 'retrigger_interval_max = %.1f' % imax,
                           'pitch_random_min = %.2f' % pitch[0], 'pitch_random_max = %.2f' % pitch[1],
                           'vsnd_files_track_01 =', '['] + ['\t"%s",' % f for f in fl] + [']'])


def far(r, full=0.1, mid=0.35, midv=0.5):
    """a gun's fall-off: full volume near, half at about a third of the range, a long quiet reach to r"""
    return [(0, 1), (r * full, 1), (r * mid, midv), (r * 0.7, midv * 0.36), (r, 0)]


def events():
    ev = []
    ev.append(ev3d('mv.heli_rotor', files('heli_rotor'), 1.0, far(9000, 0.12, 0.4, 0.45)))
    ev.append(ev3d('mv.heli_turbine', files('heli_turbine'), 0.55, [(0, 1), (500, 1), (1600, 0.35), (3500, 0)]))
    ev.append(ev3d('mv.heli_gun', files('heli_gun', 3), 1.0, far(8000), pitch=(0.96, 1.04)))
    ev.append(ev3d('mv.rocket_launch', files('rocket_launch', 2), 1.0, far(7000), pitch=(0.95, 1.05)))
    ev.append(ev3d('mv.rocket_fly', files('rocket_fly'), 0.85, [(0, 1), (600, 1), (2000, 0.4), (4500, 0)]))
    ev.append(ev3d('mv.howitzer_fire', files('howitzer_fire', 2), 1.0, [(0, 1), (1400, 1), (4500, 0.55), (9000, 0.26), (14000, 0)], pitch=(0.97, 1.03)))
    ev.append(ev3d('mv.rocket_fire', files('rocket_fire', 2), 1.0, [(0, 1), (1400, 1), (4500, 0.5), (9000, 0.22), (14000, 0)], pitch=(0.96, 1.04)))
    ev.append(ev3d('mv.shell_whistle', files('shell_whistle'), 0.9, [(0, 1), (700, 1), (2000, 0.45), (4200, 0)], pitch=(0.95, 1.06)))
    ev.append(ev3d('mv.shell_impact', files('shell_impact', 3), 1.0, [(0, 1), (1200, 1), (3800, 0.55), (7500, 0.22), (11000, 0)], pitch=(0.94, 1.05)))
    ev.append(ev3d('mv.mount_gun', files('mount_gun', 3), 1.0, far(7500), pitch=(0.95, 1.05)))
    ev.append(ev2d('mv.capture', files('capture'), 0.60))
    ev.append(ev2d('mv.flag_lost', files('flag_lost'), 0.60))
    ev.append(ev2d('mv.radio_blip', files('radio_blip'), 0.45))
    kids = ['mv.amb.cicadas', 'mv.amb.river', 'mv.amb.birds', 'mv.amb.gecko', 'mv.amb.frogs', 'mv.amb.thunder', 'mv.amb.guns']
    ev.append(E._event('mv.amb.valley', ['base = "amb.soundscapeParent.base"', 'enable_child_events = true', 'soundevent_01 =', '['] +
                       ['\t"%s",' % k for k in kids] + [']']))
    ev.append(ev_loop('mv.amb.cicadas', files('amb_cicadas'), 0.42))
    ev.append(ev_loop('mv.amb.river', files('amb_river'), 0.16))
    ev.append(ev_rand('mv.amb.birds', files('amb_bird', 6), 0.55, 700, 2200, 5.0, 16.0, (0.94, 1.07)))
    ev.append(ev_rand('mv.amb.gecko', files('amb_gecko'), 0.50, 500, 1400, 45.0, 110.0, (0.95, 1.05)))
    ev.append(ev_rand('mv.amb.frogs', files('amb_frog', 3), 0.45, 500, 1600, 9.0, 26.0, (0.94, 1.06)))
    ev.append(ev_rand('mv.amb.thunder', files('amb_thunder', 3), 0.80, 3500, 7000, 28.0, 75.0, (0.92, 1.05)))
    ev.append(ev_rand('mv.amb.guns', files('amb_guns', 4), 0.70, 3000, 6500, 12.0, 40.0, (0.93, 1.05)))
    return ev


def check_events(text):
    """every vsnd an event names is one we wrote; every CONTRACT event is there; braces balance"""
    import re
    prob = []
    for f in re.findall(r'"(sounds/mv/[^"]+)\.vsnd"', text):
        if f.split('/')[-1] not in SOUNDS: prob.append('event names a missing sound: %s' % f)
    names = set(E.event_names(E.body_of(text, TAG)))
    want = ['mv.heli_rotor', 'mv.heli_turbine', 'mv.heli_gun', 'mv.rocket_launch', 'mv.rocket_fly', 'mv.howitzer_fire', 'mv.rocket_fire',
            'mv.shell_whistle', 'mv.shell_impact', 'mv.mount_gun', 'mv.capture', 'mv.flag_lost', 'mv.radio_blip', 'mv.amb.valley']
    prob += ['contract event missing: %s' % w for w in want if w not in names]
    used = set(re.findall(r'sounds/mv/([^"]+)\.vsnd', text))
    prob += ['sound written but used by no event: %s' % s for s in SOUNDS if s not in used]
    for o, c in ('{}', '[]'):
        if text.count(o) != text.count(c): prob.append('unbalanced %s%s' % (o, c))
    return prob, sorted(names)


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    if len(args) < 2: sys.exit(__doc__)
    out, template = args[0], args[1]
    d = os.path.join(out, 'sounds', 'mv'); os.makedirs(d, exist_ok=True)
    build()
    report, bad = {}, []
    for f in os.listdir(d):                              # no stale wavs from an older build
        if f.endswith('.wav') and f[:-4] not in SOUNDS: os.remove(os.path.join(d, f))
    for name, (x, loop, expect) in SOUNDS.items():
        open(os.path.join(d, name + '.wav'), 'wb').write(wav_bytes(x, loop))
        # check what was written, not what was meant: read the 16-bit data back
        raw = open(os.path.join(d, name + '.wav'), 'rb').read()
        i = 12; seen = []
        while raw[i:i + 4] != b'data':                    # walk the RIFF chunks ("data" also appears inside the cue chunk)
            seen.append(raw[i:i + 4]); i += 8 + struct.unpack('<I', raw[i + 4:i + 8])[0]
        y = np.frombuffer(raw[i + 8:i + 8 + struct.unpack('<I', raw[i + 4:i + 8])[0]], '<i2').astype(float) / 32767.0
        if x.ndim == 2: y = y.reshape(-1, 2)
        assert len(y) == len(x), name
        if loop: assert b'smpl' in seen and b'cue ' in seen, name + ': loop markers missing'
        row, prob = analyse(name, y, loop, expect)
        report[name] = row
        bad += ['%s: %s' % (name, p) for p in prob]
    sev = os.path.join(out, 'soundevents'); os.makedirs(sev, exist_ok=True)
    dst = os.path.join(sev, 'soundevents_addon.vsndevts')
    base = open(dst if os.path.exists(dst) else template, encoding='utf-8').read()
    text = E.merge(base, E.wrap(events()), TAG)
    open(dst, 'w', newline='\n', encoding='utf-8').write(text)
    eprob, names = check_events(text)
    bad += eprob
    rp = os.path.join(HERE, '..', 'out', 'sounds_report.json')
    json.dump(dict(sounds=report, events=names, problems=bad), open(rp, 'w'), indent=1)
    print('%-18s %6s %2s %7s %7s %6s %8s  %s' % ('sound', 'sec', 'ch', 'peak dB', 'rms dB', 'crest', 'centroid', 'sub/low/mid/high/air   loop seam (step, kink, level dB)'))
    for name, r in report.items():
        b = r['bands']
        seam = '   seam %.2f %.2f %+.2f' % (r['seam_step_vs_p999'], r['seam_kink_vs_p999'], r['seam_level_db']) if r['loop'] else ''
        print('%-18s %6.2f %2d %7.2f %7.2f %6.1f %8d  %.2f/%.2f/%.2f/%.2f/%.2f%s' % (name, r['seconds'], r['channels'], r['peak_dbfs'], r['rms_dbfs'],
              r['crest_db'], r['centroid_hz'], b['sub_120'], b['low_500'], b['mid_2k'], b['high_8k'], b['air'], seam))
    print('sounds: %d wavs, %d events (%s) -> %s' % (len(SOUNDS), len(names), TAG, dst))
    if bad and '--no-check' not in argv:
        print('\n'.join('SOUND: ' + b for b in bad)); sys.exit(1)
    print('sound checks: clean' if not bad else 'sound checks: %d problems (ignored)' % len(bad))


if __name__ == '__main__':
    main(sys.argv[1:])
