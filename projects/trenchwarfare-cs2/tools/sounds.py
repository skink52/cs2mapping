"""mg_trenchwarfare sounds: everything synthesised (numpy / scipy, 44.1 kHz, no samples) + the tw.* sound events, merged into
the addon's soundevents_addon.vsndevts (block "mg_trenchwarfare", re-runnable; nothing else in the file is touched).
Method from projects/monsoon-cs2/tools/sounds.py (loops from noise that is periodic over the file, whole cycles, smpl + cue
markers, no crossfade; a numeric listen-check that reads every wav back from disk).

usage: sounds.py <addon content out> <template soundevents_addon.vsndevts> [--no-check] [--pending DIR]
  writes  <addon>/sounds/tw/*.wav                        16-bit PCM 44.1 kHz; loops carry smpl + cue markers
          <addon>/soundevents/soundevents_addon.vsndevts  the template (the live addon file, read only) with our block replaced
          ../out/sounds_report.json                       the listen-check (peak, RMS, DC, loop seam, spectrum, length)
          --pending DIR (default ../out/step8/pending_sounds): sounds made and checked but NOT shipped, because nothing plays
                         them yet (they need a script or map hook first; none since 12 Nov 2026: the last three were wired by
                         tools/patch_sounds.py and the script, docs/SOUNDS.md)
  exits 1 if a check fails (clipping, DC offset, a loop seam that would click, a spectrum that is not what the sound should be,
  an event naming a missing file, a shipped file no event uses, a contract event missing).

Events (docs/CONTRACT.md "Sound events"; docs/SOUNDS.md for the design):
  tw.mortar_launch   3D 4500    Stokes / Minenwerfer: cartridge cough, tube ring, the bomb leaving (2 variants)
  tw.mortar_whistle  3D 3500    2.0 s falling whistle, loudest at the end (the script starts it 2.0 s before the impact)
  tw.mortar_impact   3D 9000    HE burst: crack, boom, clods coming down, rolling tail (3 variants)
  tw.plane_engine    3D 7000    loop: 9-cylinder rotary at 1200 rpm (90 Hz firing, 40 Hz two-blade prop)
  tw.plane_gun       3D 7000    twin synchronised MGs, two rounds per event (the script plays one every 2nd round, 3 variants)
  tw.ambient_blast   3D 9000    = the impact files (kept for older map wiring)
  tw.whistle_attack  flat       the company officer's whistle, over the top: tw_whistle_attack (script, LOBBY_RESPAWN after round start)
  tw.plane_dive      3D 5000    a biplane diving: engine winding up, rigging howling: tw_plane_dive_1..4 (script pool, 60_air)
  tw.amb.rain_tin    3D 600     loop: rain on the shelters' elephant iron: tw_rain_tin_<tg>_1..3 (map: relay tw_rain OnUser1 / OnUser2)
  tw.amb.front       soundscape parent (env_soundscape in the map) -> tw.amb.wind (stereo loop), tw.amb.barrage (stereo loop:
                     drumfire beyond the horizon), tw.amb.guns, tw.amb.shells, tw.amb.mg, tw.amb.whistles, tw.amb.planes (ours,
                     random around the player) + tw.amb.crows, tw.amb.rifles, tw.amb.whiz (stock files)
"""
import os, sys, json, struct, re
import numpy as np
from scipy import signal
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sndevents as E

SR = 44100
TAG = 'mg_trenchwarfare'
SUB = 'sounds/tw'


# ---------------------------------------------------------------- dsp helpers (monsoon's, generic)
def bp(x, lo, hi, order=2):
    return signal.sosfilt(signal.butter(order, [lo, hi], 'bandpass', fs=SR, output='sos'), x)


def lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, 'lowpass', fs=SR, output='sos'), x)


def hp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, 'highpass', fs=SR, output='sos'), x)


def _unit(x):
    return x / (np.std(x) + 1e-12)


def bn(rng, n, lo, hi, order=2):
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
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / tau)
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def shaped_noise(n, rng, shape):
    """noise exactly periodic over n samples with magnitude spectrum shape(f): the building block of every seamless loop"""
    spec = np.fft.rfft(rng.normal(0, 1, n))
    f = np.fft.rfftfreq(n, 1.0 / SR)
    x = np.fft.irfft(spec * shape(f), n)
    return x / (np.std(x) + 1e-12)


def band(lo, hi, soft=0.25):
    def s(f):
        f = np.maximum(f, 1e-3)
        a = 1.0 / (1.0 + (lo / f) ** (2 / soft * 0.5 + 2)); b = 1.0 / (1.0 + (f / hi) ** (2 / soft * 0.5 + 2))
        return a * b
    return s


def reverb(x, sec, rng, tau, wet, lo=60.0, hi=1800.0, pre=0.03, echoes=()):
    """x + wet * (x convolved with a decaying band-limited noise tail) + discrete echoes [(delay s, gain, lowpass Hz)]"""
    n = int(SR * sec); t = np.arange(n) / SR
    ir = bn(rng, n, lo, hi) * np.exp(-t / tau) * (t >= pre)
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-12
    out = np.concatenate([x, np.zeros(n)])
    w = signal.fftconvolve(x, ir)
    w = np.concatenate([w, np.zeros(len(out) - len(w))])[:len(out)]
    out = out + wet * w * (np.max(np.abs(x)) / (np.max(np.abs(w)) + 1e-12))
    for delay, gain, f in echoes:
        d = int(delay * SR); e = lp(x, f) * gain; m = min(len(e), len(out) - d)
        if m > 0: out[d:d + m] += e[:m]
    return out


def circ_reverb(x, rng, tau, wet, lo=40.0, hi=600.0, sec=3.0):
    """reverb for a LOOP: circular convolution, so the tail of the end runs into the start and the file stays periodic"""
    n = len(x); m = min(int(SR * sec), n)
    t = np.arange(m) / SR
    ir = np.zeros(n); ir[:m] = bn(rng, m, lo, hi) * np.exp(-t / tau)
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-12
    w = np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(ir), n)
    return x + wet * w * (np.std(x) / (np.std(w) + 1e-12))


def circ_lp(x, f):
    """zero-phase low-pass in the frequency domain (periodic: keeps a loop seamless)"""
    n = len(x); F = np.fft.rfftfreq(n, 1.0 / SR)
    return np.fft.irfft(np.fft.rfft(x) / np.sqrt(1 + (F / f) ** 4), n)


def place_wrap(buf, x, at):
    """add x into buf at sample `at`, wrapping round the end (loops)"""
    n = len(buf); i = int(at) % n
    k = min(len(x), n - i); buf[i:i + k] += x[:k]
    if len(x) > k: place_wrap(buf, x[k:], 0)


def clip(x, drive=1.0):
    return np.tanh(x * drive) / np.tanh(drive)


def fade_out(x, sec):
    n = min(len(x), int(SR * sec)); x = x.copy(); x[-n:] *= np.linspace(1, 0, n) ** 2
    return x


def fade_in(x, sec):
    n = min(len(x), int(SR * sec)); x = x.copy(); x[:n] *= np.linspace(0, 1, n)
    return x


def norm(x, peak=0.92):
    return x / (np.max(np.abs(x)) + 1e-12) * peak


def place(buf, x, at):
    i = int(at * SR); m = min(len(x), len(buf) - i)
    if m > 0: buf[i:i + m] += x[:m]


def distant(x, rng, sec=1.6, tau=0.6, wet=0.7, lo=40, hi=1500, cut=None, echoes=()):
    """the far side of the line: high end gone, a long outdoor tail"""
    if cut: x = lp(x, cut, 3)
    return fade_out(reverb(x, sec, rng, tau, wet, lo, hi, pre=0.06, echoes=echoes), min(1.0, sec * 0.6))


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


SOUNDS = {}      # name -> (array, loop, expectations, shipped)


def add(name, x, loop=False, ship=True, **expect):
    x = np.asarray(x, float)
    if not loop:                                  # one-shots: 3 ms in, 12 ms out, so a retrigger never clicks
        x = x.copy(); a = int(SR * 0.003); b = int(SR * 0.012)
        ra = np.linspace(0, 1, a); rb = np.linspace(1, 0, b)
        if x.ndim == 1: x[:a] *= ra; x[-b:] *= rb
        else: x[:a] *= ra[:, None]; x[-b:] *= rb[:, None]
    x = x - np.mean(x, axis=0)
    SOUNDS[name] = (norm(x), loop, expect, ship)


# ================================================================ mortars
def make_launch(rng, v):
    """Stokes 3-inch / Minenwerfer: the bomb slides down the tube, the cartridge fires: a hollow cough, the tube ringing,
    the bomb tearing away overhead, a short field tail (about 2.2 s)"""
    n = int(SR * 1.0); t = np.arange(n) / SR
    crack = hn(rng, n, 1200) * env(n, 0.0004, 0.006)
    cough = bn(rng, n, 160, 1400) * env(n, 0.001, 0.045 + 0.01 * v)
    boom = sweep(n, 140 - 15 * v, 46, 0.035) * env(n, 0.002, 0.16)
    ring = sum(a * np.sin(2 * np.pi * f * t + i) * env(n, 0.002, d) for i, (f, a, d) in
               enumerate(((236 + 18 * v, 0.6, 0.22), (566, 0.35, 0.15), (1012 - 40 * v, 0.2, 0.09), (1731, 0.08, 0.05))))
    leave = np.zeros(int(SR * 0.9))
    nl = len(leave); tl = np.arange(nl) / SR                          # the bomb leaving: a rising, fading rip of air
    fc = 500 + 1600 * (1 - np.exp(-tl / 0.18))
    nz = rng.normal(0, 1, nl); out_ = np.zeros(nl); blk = 1024; hop = 256; w = np.hanning(blk)
    for i in range(0, nl - blk, hop):
        seg = np.fft.rfft(nz[i:i + blk] * w); ff = np.fft.rfftfreq(blk, 1.0 / SR)
        out_[i:i + blk] += np.fft.irfft(seg * band(fc[i] * 0.6, fc[i] * 1.8)(ff), blk) * w
    leave = _unit(out_) * env(nl, 0.02, 0.22)
    x = clip(crack * 0.8 + cough * 1.4 + boom * 1.2 + ring * 0.55, 1.8)
    place(x, leave * 0.32, 0.02)
    return fade_out(reverb(x, 1.3, rng, 0.36, 0.38, 70, 2000, pre=0.03, echoes=((0.29 + 0.03 * v, 0.14, 700),)), 0.5)


def make_whistle(rng, v):
    """2.0 s: a falling, swelling whistle with air rush; loudest at the very end (the bomb arrives). Variant 1 tumbles
    (a slow wobble, like a Minenwerfer bomb turning over)."""
    n = int(SR * 2.0); t = np.arange(n) / SR; u = t / t[-1]
    f0, f1 = (1650, 690) if v == 0 else (1350, 560)
    wob = 14 * np.sin(2 * np.pi * 6.5 * t) if v == 0 else 38 * np.sin(2 * np.pi * (2.6 + 1.2 * u) * t)
    f = f0 - (f0 - f1) * u ** 1.35 + wob
    ph = 2 * np.pi * np.cumsum(f) / SR
    amp = 0.10 + 0.90 * u ** 2.3
    if v == 1: amp *= 0.85 + 0.15 * np.sin(2 * np.pi * (2.6 + 1.2 * u) * t) ** 2
    tone = np.sin(ph) * 0.8 + np.sin(2.005 * ph) * 0.14 + np.sin(3.01 * ph) * 0.05
    air = np.zeros(n); blk = 2048; hop = 512; w = np.hanning(blk); nz = rng.normal(0, 1, n)
    for i in range(0, n - blk, hop):
        fc = f[i + blk // 2]
        seg = np.fft.rfft(nz[i:i + blk] * w); ff = np.fft.rfftfreq(blk, 1.0 / SR)
        air[i:i + blk] += np.fft.irfft(seg * band(fc * 0.6, fc * 2.2)(ff), blk) * w
    air /= np.std(air) + 1e-12
    x = (tone + air * 0.30) * amp
    x[-int(SR * 0.02):] *= np.linspace(1, 0, int(SR * 0.02))
    return x


def make_impact(rng, v):
    """HE burst in wet ground: crack, boom, the ground thump, clods and mud coming down, rolling tail (about 4.4 s)"""
    n = int(SR * 1.9); t = np.arange(n) / SR
    crack = rng.normal(0, 1, n) * env(n, 0.0003, 0.010 + 0.002 * v)
    blast = bn(rng, n, 80, 1500) * env(n, 0.001, 0.13)
    boom = sweep(n, 110 - 8 * v, 34, 0.06) * env(n, 0.002, 0.34 + 0.04 * v)
    sub = np.sin(2 * np.pi * (41 - 2 * v) * t) * env(n, 0.005, 0.42)
    deb = np.zeros(n)
    for _ in range(90 + 20 * v):
        at = 0.18 + rng.gamma(2.2, 0.26)
        if at > 1.75: continue
        m = int(SR * rng.uniform(0.012, 0.05))
        clod = bp(rng.normal(0, 1, m + 64), rng.uniform(180, 700), rng.uniform(1200, 4200))[:m] * env(m, 0.0006, m / SR / 4)
        place(deb, clod * rng.uniform(0.2, 1.0) * np.exp(-at / 0.7), at)
    splat = hn(rng, n, 1500) * env(n, 0.25, 0.42) * 0.35               # mud and water coming down
    punch = bn(rng, n, 300, 3200) * env(n, 0.0006, 0.09)
    x = clip(crack * 1.3 + punch * 1.6 + blast * 1.9 + boom * 0.85 + sub * 0.4 + deb * 0.9 + splat * 0.30, 2.4)
    x = reverb(x, 2.6, rng, 0.75, 0.50, 50, 1900, pre=0.05, echoes=((0.37 + 0.06 * v, 0.20, 450), (0.9, 0.12, 280), (1.5, 0.07, 190)))
    return fade_out(x, 1.0)


# ================================================================ aircraft
def make_engine(rng):
    """2.0 s loop: a 9-cylinder rotary (Clerget / Le Rhone / Oberursel) at 1200 rpm: 90 firings a second, every ninth a touch
    different (a cylinder is never quite like the others), the two-blade prop beating at 40 Hz, valve clatter, wind in the
    rigging. Every component is periodic over the 2 s (whole cycles; firings placed with wrap-around)."""
    L = 2.0; n = int(SR * L); t = np.arange(n) / SR
    fire = np.zeros(n)
    per = SR / 90.0
    cyl = 1.0 + 0.22 * rng.uniform(-1, 1, 9)                           # per-cylinder strength
    tone = 150 + 50 * rng.uniform(0, 1, 9)
    m = int(SR * 0.012); tt = np.arange(m) / SR
    for k in range(180):                                               # 90 Hz x 2 s: whole cycles
        c = k % 9
        burst = (np.exp(-tt / 0.0032) * np.sin(2 * np.pi * tone[c] * tt) + 0.5 * bn(rng, m, 300, 2400) * np.exp(-tt / 0.0016))
        place_wrap(fire, burst * cyl[c], int(round(k * per)))
    body = circ_lp(fire, 1400) * 1.5
    prop = (0.55 + 0.45 * np.cos(2 * np.pi * 40 * t)) * shaped_noise(n, rng, band(60, 420))
    clat = shaped_noise(n, rng, band(2200, 6000)) * (0.5 + 0.5 * np.cos(2 * np.pi * 90 * t + 1.0)) ** 4
    wind = shaped_noise(n, rng, band(200, 2600)) * (0.85 + 0.15 * np.cos(2 * np.pi * 1.5 * t))
    hum = sum(np.sin(2 * np.pi * f * t + i) / (i + 1) for i, f in enumerate((20.0, 40.0, 80.0)))   # crank and prop fundamentals
    x = body * 1.0 + prop * 0.55 + clat * 0.10 + wind * 0.20 + hum * 0.18
    x = x - np.mean(x)                                                 # the decaying firing bursts carry DC
    return clip(x / np.max(np.abs(x)), 1.3)


def make_gun(rng, v):
    """twin synchronised MGs (Vickers / Spandau): two rounds 90 ms apart, the guns 14-22 ms out of step with each other,
    a dry mechanical clack, little reverb (it is fired in the air). About 0.7 s."""
    n = int(SR * 0.3)
    def shot(seed_shift):
        crack = hn(rng, n, 1300) * env(n, 0.0003, 0.006)
        body = bn(rng, n, 180, 1500) * env(n, 0.0008, 0.030 + 0.004 * v)
        thump = sweep(n, 190 - 12 * v + seed_shift, 60, 0.02) * env(n, 0.001, 0.05)
        t = np.arange(n) / SR
        mech = sum(np.sin(2 * np.pi * f * t + i) * env(n, 0.001, d) for i, (f, d) in
                   enumerate(((1320 + 70 * v, 0.022), (2610, 0.015), (3980 - 110 * v, 0.010))))
        return clip(crack * 1.0 + body * 1.25 + thump * 0.9 + mech * 0.16, 1.9)
    x = np.zeros(int(SR * 0.42))
    off = (0.014, 0.018, 0.022)[v]
    for k, at in enumerate((0.004, 0.094)):
        place(x, shot(k * 6) * 1.0, at)
        place(x, shot(k * 6 + 9) * 0.82, at + off)
    return fade_out(reverb(x, 0.35, rng, 0.08, 0.18, 150, 3000, pre=0.015), 0.12)


def make_plane_far(rng, eng, v):
    """an aircraft passing a few hundred metres off: the engine loop pitched by the doppler shift, fading in and out
    (about 9 s)"""
    L = 9.0 + v; n = int(SR * L); t = np.arange(n) / SR
    tc = L * (0.48 + 0.06 * v)
    speed = 52.0; dmin = 380.0 + 140 * v                              # m/s, closest distance (m)
    r = np.hypot(speed * (t - tc), dmin)
    vr = speed ** 2 * (t - tc) / r                                     # range rate
    ratio = 343.0 / (343.0 + vr)                                      # received / emitted frequency
    ratio *= 0.94 + 0.04 * v                                          # a different engine note
    pos = np.cumsum(ratio)
    src = np.tile(eng, int(np.ceil(pos[-1] / len(eng))) + 2)
    y = hp(np.interp(pos, np.arange(len(src)), src), 25)
    amp = (dmin / r) ** 1.4
    y = lp(y, 1600, 2) * amp
    y = y + lp(y, 300, 2) * (1 - dmin / r) * 0.5                       # far: the low drone carries further
    return fade_out(fade_in(reverb(y, 1.2, rng, 0.5, 0.35, 40, 1200), 0.8), 1.5)


# ================================================================ ambience
def make_wind(rng):
    """16 s stereo loop: wind across open, wrecked ground: a broad bed, slow gusts, the barbed wire singing faintly.
    Every gust and every swell is a whole number of cycles over the loop."""
    L = 16.0; n = int(SR * L); t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for c in range(2):
        bed = shaped_noise(n, rng, band(70, 900))
        hiss = shaped_noise(n, rng, band(900, 5000))
        g = 0.62 + 0.20 * np.sin(2 * np.pi * (2 + c) / L * t + rng.uniform(0, 6)) + 0.12 * np.sin(2 * np.pi * (5 - c) / L * t + rng.uniform(0, 6)) \
            + 0.06 * np.sin(2 * np.pi * 11 / L * t + rng.uniform(0, 6))
        wire = sum(shaped_noise(n, rng, band(f * 0.985, f * 1.015, soft=0.05)) * a for f, a in ((612 + 40 * c, 1.0), (933, 0.6), (1404, 0.35)))
        wire *= np.clip(g - 0.7, 0, 1) * 4                               # the wire only sings in the gusts
        out[:, c] = bed * g * 0.55 + hiss * g ** 2 * 0.16 + wire * 0.05
    return out


def make_barrage(rng):
    """20 s stereo loop: drumfire beyond the horizon: a continuous low rumble, many dull thuds rolling into each other,
    the odd heavier one, all low-passed by distance. Thuds wrap round the loop end; the tail is a circular reverb."""
    L = 20.0; n = int(SR * L); t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for c in range(2):
        thuds = np.zeros(n)
        k = 0
        at = rng.uniform(0, 0.3)
        while at < L:
            m = int(SR * 0.9); th = sweep(m, 64 + rng.uniform(-8, 10), 30, 0.07) * env(m, 0.012, 0.24) + \
                ln(rng, m, 220) * env(m, 0.010, 0.12) * 0.5
            g = rng.uniform(0.25, 0.8) * (1.6 if rng.rand() < 0.08 else 1.0)
            place_wrap(thuds, th * g, at * SR)
            at += rng.exponential(0.32); k += 1
        thuds = circ_lp(thuds, 260)
        rumble = shaped_noise(n, rng, band(22, 140)) * (0.8 + 0.2 * np.sin(2 * np.pi * (3 + c) / L * t + c))
        x = thuds * 1.0 + rumble * 0.35
        out[:, c] = circ_reverb(x, rng, 1.1, 0.8, 25, 300)
    return out


def make_far_guns(rng, v):
    """heavy guns a few kilometres back: 1-4 dull reports with long echoes along the valley (about 4 s)"""
    x = np.zeros(int(SR * 3.4))
    shots = [1, 2, 3, 4][v % 4]
    at = 0.1
    for k in range(shots):
        m = int(SR * 0.9)
        th = sweep(m, 74, 32, 0.07) * env(m, 0.010, 0.26) + ln(rng, m, 300) * env(m, 0.012, 0.16) * 0.55
        place(x, th * rng.uniform(0.7, 1.0), at)
        at += rng.uniform(0.35, 0.9)
    return fade_out(reverb(lp(x, 520), 2.4, rng, 0.85, 0.75, 30, 450, pre=0.08, echoes=((0.7, 0.3, 260), (1.5, 0.18, 180))), 1.2)


def make_far_shell(rng, v):
    """a shell bursting a few hundred metres down the line: a crump, dirt, a long tail; variant 2 is heard coming in"""
    x = make_impact(rng, v % 3)
    x = lp(x, 900 + 300 * v, 3)
    if v == 2:
        w = make_whistle(rng, 0)[int(SR * 0.6):]
        w = lp(w, 2500) * 0.18
        x = np.concatenate([w, x])
    return fade_out(reverb(x, 1.8, rng, 0.7, 0.55, 40, 900, pre=0.06), 1.0)


def make_mg_far(rng, v):
    """a Maxim / Vickers a few hundred metres off: bursts at 8 rounds a second, each round a dull knock, distance
    taking the crack away (2.5-4 s)"""
    plan = [[(0.05, 18)], [(0.05, 7), (1.25, 9)], [(0.05, 4), (0.75, 5), (1.6, 12)]][v]
    L = max(a + k / 8.0 for a, k in plan) + 0.4
    x = np.zeros(int(SR * L))
    rate = 8.0 + 0.6 * v
    for at, k in plan:
        for i in range(k):
            m = int(SR * 0.12)
            sh = bn(rng, m, 300, 2200) * env(m, 0.0006, 0.012) * 0.9 + sweep(m, 160, 70, 0.015) * env(m, 0.001, 0.03)
            place(x, sh * rng.uniform(0.75, 1.0), at + i / rate + rng.uniform(-0.004, 0.004))
    return distant(x, rng, sec=1.4, tau=0.45, wet=0.65, lo=60, hi=1800, cut=1700, echoes=((0.42, 0.18, 900),))


def whistle_blast(rng, dur, f0=3050.0, pea=27.0, shape='long'):
    """an officer's pea whistle (Acme Thunderer): a bright carrier warbled by the pea"""
    n = int(SR * dur); t = np.arange(n) / SR
    fm = 1 + 0.035 * np.sin(2 * np.pi * pea * t) + 0.006 * np.sin(2 * np.pi * 5.2 * t)
    ph = 2 * np.pi * np.cumsum(f0 * fm) / SR
    am = 0.72 + 0.28 * np.sin(2 * np.pi * pea * t + 0.6)
    a = np.minimum(t / 0.03, 1.0) * np.minimum((dur - t) / 0.06, 1.0).clip(0)
    if shape == 'rise': a *= 0.6 + 0.4 * np.minimum(t / (dur * 0.4), 1)
    breath = bn(rng, n, 2500, 7000) * 0.10
    return (np.sin(ph) + 0.18 * np.sin(2 * ph) + breath) * am * a


def make_whistles(rng, v):
    """whistles blowing somewhere along the line (another company going over): one long blast, three short ones, or two
    whistles answering each other further away (about 3 s)"""
    x = np.zeros(int(SR * 3.0))
    if v == 0:
        place(x, whistle_blast(rng, 1.3, 3020, 27, 'rise'), 0.1)
    elif v == 1:
        for k in range(3): place(x, whistle_blast(rng, 0.26, 3110, 31), 0.1 + k * 0.42)
    else:
        place(x, whistle_blast(rng, 0.9, 2950, 25), 0.1)
        place(x, whistle_blast(rng, 1.0, 3240, 29) * 0.5, 0.75)
    x = hp(x, 600)
    return distant(x, rng, sec=1.6, tau=0.55, wet=0.75, lo=500, hi=4500, cut=5200, echoes=((0.55, 0.22, 2500),))


# ---------------------------------------------------------------- wired 12 Nov 2026 (were pending): patch_sounds.py + 60_air / 90_main
def make_dive(rng, eng):
    """3 s: an aircraft diving: the engine winding up, the rigging wires howling, wind rush building"""
    L = 3.0; n = int(SR * L); t = np.arange(n) / SR; u = t / L
    ratio = 1.0 + 0.35 * u ** 1.6
    pos = np.cumsum(ratio); src = np.tile(eng, int(np.ceil(pos[-1] / len(eng))) + 2)
    e = np.interp(pos, np.arange(len(src)), src)
    howl = sum(np.sin(2 * np.pi * np.cumsum(f * (1 + 0.6 * u)) / SR + i) * a for i, (f, a) in enumerate(((520, 1.0), (780, 0.6), (1170, 0.3))))
    howl *= (0.4 + 0.6 * u) * (1 + 0.1 * ln(rng, n, 8))
    rush = bn(rng, n, 400, 4000) * (0.2 + 0.8 * u ** 1.5)
    swell = 0.2 + 0.8 * u ** 2.2                                      # the dive builds to the pull-out
    return fade_out(fade_in((e * 0.8 + howl * 0.25 + rush * 0.5) * swell, 0.15), 0.08)


def make_rain_tin(rng):
    """12 s stereo loop: rain on corrugated iron (the shelters' elephant iron): many small pings, a ringing sheet, a bed of
    rain; drops placed with wrap-around"""
    L = 12.0; n = int(SR * L)
    out = np.zeros((n, 2))
    for c in range(2):
        drops = np.zeros(n)
        for _ in range(int(L * 160)):
            m = int(SR * 0.03); f = rng.uniform(2200, 6500)
            tt = np.arange(m) / SR
            d = np.sin(2 * np.pi * f * tt) * np.exp(-tt / rng.uniform(0.003, 0.012)) + bn(rng, m, 1500, 8000) * np.exp(-tt / 0.002) * 0.6
            place_wrap(drops, d * rng.uniform(0.1, 1.0) ** 2, rng.uniform(0, n))
        sheet = circ_reverb(drops, rng, 0.25, 0.6, 300, 3000, sec=1.0)
        bed = shaped_noise(n, rng, band(1200, 9000))
        out[:, c] = sheet * 0.8 + bed * 0.25
    return out


def make_whistle_attack(rng):
    """1.8 s: the company officer's whistle close by: over the top (a round-start stinger)"""
    x = np.zeros(int(SR * 1.8))
    place(x, whistle_blast(rng, 0.16, 3080, 30), 0.02)
    place(x, whistle_blast(rng, 1.25, 3060, 28, 'rise'), 0.3)
    return fade_out(reverb(hp(x, 500), 0.8, rng, 0.25, 0.25, 800, 6000), 0.3)


# ================================================================ build all
def build():
    R = np.random.RandomState
    for v in range(2): add('mortar_launch_%d' % (v + 1), make_launch(R(10 + v), v), centroid=(150, 1600), low=(0.25, 20, 500), dur=(1.9, 2.6))
    for v in range(2): add('mortar_whistle_%d' % (v + 1), make_whistle(R(14 + v), v), centroid=(600, 2200), dur=(1.98, 2.02), late=True)
    for v in range(3): add('mortar_impact_%d' % (v + 1), make_impact(R(20 + v), v), low=(0.4, 20, 200), mid=(0.06, 400, 8000), dur=(4.0, 5.0), tail=0.012)
    eng = make_engine(R(30))
    add('plane_engine', eng, loop=True, centroid=(150, 1500), low=(0.35, 20, 500))
    for v in range(3): add('plane_gun_%d' % (v + 1), make_gun(R(40 + v), v), centroid=(250, 3500), mid=(0.15, 500, 8000), dur=(0.6, 0.9))
    add('amb_wind', make_wind(R(50)), loop=True, centroid=(150, 1500))
    add('amb_barrage', make_barrage(R(51)), loop=True, low=(0.85, 15, 250), centroid=(20, 200))
    for v in range(4): add('amb_guns_%d' % (v + 1), make_far_guns(R(60 + v), v), low=(0.85, 15, 300), centroid=(20, 260))
    for v in range(3): add('amb_shell_%d' % (v + 1), make_far_shell(R(70 + v), v), low=(0.5, 15, 300), centroid=(30, 700))
    for v in range(3): add('amb_mg_%d' % (v + 1), make_mg_far(R(80 + v), v), centroid=(150, 1500))
    for v in range(3): add('amb_whistle_%d' % (v + 1), make_whistles(R(90 + v), v), centroid=(1500, 4500), high=(0.45, 2000, 8000))
    for v in range(2): add('amb_plane_%d' % (v + 1), make_plane_far(R(95 + v), eng, v), centroid=(60, 1200))
    # wired 12 Nov 2026 (tools/patch_sounds.py emitters; the script's dive pool and round-start whistle); ship=False keeps a sound
    # out of the addon (written to --pending) until something plays it
    add('plane_dive', make_dive(R(100), eng), centroid=(200, 2500), late=True)
    add('rain_tin', make_rain_tin(R(101)), loop=True, centroid=(2000, 7000), high=(0.5, 2000, 12000))
    add('whistle_attack', make_whistle_attack(R(102)), centroid=(1800, 4500), high=(0.5, 2000, 8000))


# ================================================================ numeric listen-check (monsoon's)
def analyse(name, x, loop, expect):
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
            seam = abs(y[0] - y[-1])
            worst = max(worst, seam / (float(np.percentile(d, 99.9)) + 1e-9))
            dd = np.abs(np.diff(y, 2)); k = abs((y[1] - y[0]) - (y[0] - y[-1]))
            worst2 = max(worst2, k / (float(np.percentile(dd, 99.9)) + 1e-9))
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
    if expect.get('late'):
        q = np.sqrt(np.mean(mono[-n // 4:] ** 2)) / (np.sqrt(np.mean(mono[:n // 4] ** 2)) + 1e-9)
        row['late_ratio'] = round(float(q), 1)
        if q < 3: prob.append('does not swell toward the end (%.1f x)' % q)
    if 'tail' in expect:
        i = int(2.0 * SR); lvl = float(np.sqrt(np.mean(mono[i:i + SR // 4] ** 2))) if n > i + SR // 4 else 0.0
        row['rms_at_2s'] = round(lvl, 4)
        if lvl < expect['tail']: prob.append('tail too short (rms %.4f at 2 s)' % lvl)
    return row, prob


# ================================================================ events
def files(stem, n=None):
    return ['%s/%s.vsnd' % (SUB, stem)] if n is None else ['%s/%s_%d.vsnd' % (SUB, stem, i + 1) for i in range(n)]


def ev3d(name, fl, volume, pts, pitch=None, extra=()):
    lines = ['type = "csgo_mega"', 'volume = %.2f' % volume, 'pitch = 1.00', 'use_time_volume_mapping_curve = false']
    if len(fl) == 1: lines.append('vsnd_files_track_01 = "%s"' % fl[0])
    else: lines += ['vsnd_files_track_01 =', '['] + ['\t"%s",' % f for f in fl] + [']']
    if pitch: lines += ['pitch_random_min = %.2f' % pitch[0], 'pitch_random_max = %.2f' % pitch[1]]
    lines += list(extra) + ['distance_volume_mapping_curve ='] + E.curve(pts)
    return E._event(name, lines)


def ev_loop(name, fl, volume):
    return E._event(name, ['base = "amb.looping.stereo.base"', 'volume = %.2f' % volume, 'vsnd_files_track_01 = "%s"' % fl[0]])


def ev_rand(name, fl, volume, rmin, rmax, imin, imax, pitch=(0.96, 1.04)):
    return E._event(name, ['base = "amb.intermittent.randomAroundPlayer.base"', 'volume = %.2f' % volume,
                           'randomize_position_min_radius = %.1f' % rmin, 'randomize_position_max_radius = %.1f' % rmax,
                           'retrigger_interval_min = %.1f' % imin, 'retrigger_interval_max = %.1f' % imax,
                           'pitch_random_min = %.2f' % pitch[0], 'pitch_random_max = %.2f' % pitch[1],
                           'vsnd_files_track_01 =', '['] + ['\t"%s",' % f for f in fl] + [']'])


def far(r, full=0.1, mid=0.35, midv=0.5):
    return [(0, 1), (r * full, 1), (r * mid, midv), (r * 0.7, midv * 0.36), (r, 0)]


AMB_KIDS = ['tw.amb.wind', 'tw.amb.barrage', 'tw.amb.guns', 'tw.amb.shells', 'tw.amb.mg', 'tw.amb.whistles', 'tw.amb.planes',
            'tw.amb.crows', 'tw.amb.rifles', 'tw.amb.whiz']
CONTRACT = ['tw.mortar_launch', 'tw.mortar_whistle', 'tw.mortar_impact', 'tw.plane_engine', 'tw.plane_gun', 'tw.amb.front',
            'tw.whistle_attack', 'tw.plane_dive', 'tw.amb.rain_tin']
FLAT = [(0, 1), (20000, 1)]     # heard everywhere at full level (csgo_mega with a flat distance curve: cs2-gotchas "play everywhere")


def events():
    ev = []
    ev.append(ev3d('tw.mortar_launch', files('mortar_launch', 2), 1.0, [(0, 1), (700, 1), (2200, 0.45), (4500, 0)], pitch=(0.95, 1.05)))
    ev.append(ev3d('tw.mortar_whistle', files('mortar_whistle', 2), 0.9, [(0, 1), (700, 1), (2000, 0.45), (3500, 0)], pitch=(0.96, 1.05)))
    ev.append(ev3d('tw.mortar_impact', files('mortar_impact', 3), 1.0, [(0, 1), (1200, 1), (3800, 0.55), (7000, 0.22), (9000, 0)], pitch=(0.94, 1.05)))
    ev.append(ev3d('tw.plane_engine', files('plane_engine'), 1.0, [(0, 1), (800, 1), (3000, 0.45), (5000, 0.18), (7000, 0)]))
    ev.append(ev3d('tw.plane_gun', files('plane_gun', 3), 0.95, far(7000), pitch=(0.96, 1.04)))
    # wired 12 Nov 2026: the round-start whistle (flat, one emitter), the dive (3D, the script's pool of 4 emitters on the aircraft),
    # rain on the shelters' tin (3D loop inside each of the 6 dressing-station shelters, started / stopped with the rain relay)
    ev.append(ev3d('tw.whistle_attack', files('whistle_attack'), 0.60, FLAT,
                   extra=('use_distance_unfiltered_stereo_mapping_curve = true', 'distance_unfiltered_stereo_mapping_curve =') + tuple(E.curve(FLAT))))
    ev.append(ev3d('tw.plane_dive', files('plane_dive'), 0.90, [(0, 1), (800, 1), (2500, 0.45), (5000, 0)]))
    ev.append(ev3d('tw.amb.rain_tin', files('rain_tin'), 0.55, [(0, 1), (150, 1), (400, 0.35), (600, 0)], extra=('mixgroup = "Amb_Common"',)))
    ev.append(ev3d('tw.ambient_blast', files('mortar_impact', 3), 0.85, [(0, 1), (1200, 1), (3800, 0.5), (7000, 0.2), (9000, 0)], pitch=(0.92, 1.04)))
    ev.append(E._event('tw.amb.front', ['base = "amb.soundscapeParent.base"', 'enable_child_events = true', 'soundevent_01 =', '['] +
                       ['\t"%s",' % k for k in AMB_KIDS] + [']']))
    ev.append(ev_loop('tw.amb.wind', files('amb_wind'), 0.40))
    ev.append(ev_loop('tw.amb.barrage', files('amb_barrage'), 0.50))
    ev.append(ev_rand('tw.amb.guns', files('amb_guns', 4), 0.80, 3500, 7000, 5.0, 16.0, (0.92, 1.05)))
    ev.append(ev_rand('tw.amb.shells', files('amb_shell', 3), 0.70, 2500, 6000, 7.0, 22.0, (0.93, 1.05)))
    ev.append(ev_rand('tw.amb.mg', files('amb_mg', 3), 0.45, 2000, 5000, 6.0, 18.0, (0.95, 1.05)))
    ev.append(ev_rand('tw.amb.whistles', files('amb_whistle', 3), 0.32, 2500, 5500, 40.0, 110.0, (0.97, 1.03)))
    ev.append(ev_rand('tw.amb.planes', files('amb_plane', 2), 0.45, 2500, 6000, 35.0, 90.0, (0.95, 1.05)))
    # stock files, as before (the game's pak01; not checked offline)
    ev.append(ev_rand('tw.amb.crows', ['sounds/ambient/common/animal/crows_%02d.vsnd' % i for i in range(1, 11)], 0.5, 800, 2000, 14.0, 40.0))
    ev.append(ev_rand('tw.amb.rifles', ['sounds/weapons/ssg08/ssg08_distant.vsnd', 'sounds/weapons/awp/awp_distant.vsnd',
                                        'sounds/weapons/g3sg1/g3sg1_distant_01.vsnd', 'sounds/weapons/scar20/scar20_distant_02.vsnd'], 0.55, 1200, 4200, 0.5, 3.5))
    ev.append(ev_rand('tw.amb.whiz', ['sounds/weapons/fx/nearmiss/bulletby_subsonic_0%d.vsnd' % i for i in range(1, 6)], 0.35, 60, 300, 9.0, 30.0))
    return ev


LEGACY = re.compile(r'(\{)[ \t]*// ---- mg_trenchwarfare \(generated by tools/sounds\.py\) ----\n.*?\t// ---- end mg_trenchwarfare ----\n', re.S)


def check_events(text, shipped):
    prob = []
    for f in re.findall(r'"(%s/[^"]+)\.vsnd"' % SUB, text):
        if f.split('/')[-1] not in shipped: prob.append('event names a missing sound: %s' % f)
    names = set(E.event_names(E.body_of(text, TAG)))
    prob += ['contract event missing: %s' % w for w in CONTRACT if w not in names]
    prob += ['soundscape child not defined: %s' % k for k in AMB_KIDS if k not in names]
    used = set(re.findall(r'%s/([^"]+)\.vsnd' % SUB, text))
    prob += ['sound shipped but used by no event: %s' % s for s in shipped if s not in used]
    for o, c in ('{}', '[]'):
        if text.count(o) != text.count(c): prob.append('unbalanced %s%s' % (o, c))
    if len(re.findall(r'// ---- %s sound events' % TAG, text)) != 1 or 'generated by tools/sounds.py' in text:
        prob.append('the file does not hold exactly one %s block' % TAG)
    return prob, sorted(names)


def write_and_check(path, name, x, loop, expect):
    open(path, 'wb').write(wav_bytes(x, loop))
    raw = open(path, 'rb').read()
    i = 12; seen = []
    while raw[i:i + 4] != b'data':
        seen.append(raw[i:i + 4]); i += 8 + struct.unpack('<I', raw[i + 4:i + 8])[0]
    y = np.frombuffer(raw[i + 8:i + 8 + struct.unpack('<I', raw[i + 4:i + 8])[0]], '<i2').astype(float) / 32767.0
    if x.ndim == 2: y = y.reshape(-1, 2)
    assert len(y) == len(x), name
    if loop: assert b'smpl' in seen and b'cue ' in seen, name + ': loop markers missing'
    return analyse(name, y, loop, expect)


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    if len(args) < 2: sys.exit(__doc__)
    out, template = args[0], args[1]
    pend = os.path.join(HERE, '..', 'out', 'step8', 'pending_sounds')
    if '--pending' in argv: pend = argv[argv.index('--pending') + 1]; args = [a for a in args if a != pend]
    d = os.path.join(out, 'sounds', 'tw'); os.makedirs(d, exist_ok=True); os.makedirs(pend, exist_ok=True)
    build()
    shipped = [k for k, v in SOUNDS.items() if v[3]]
    for f in os.listdir(d):                              # no stale wavs from an older build in OUR staging folder
        if f.endswith('.wav') and f[:-4] not in shipped: os.remove(os.path.join(d, f))
    report, bad = {}, []
    for name, (x, loop, expect, ship) in SOUNDS.items():
        row, prob = write_and_check(os.path.join(d if ship else pend, name + '.wav'), name, x, loop, expect)
        row['shipped'] = ship
        report[name] = row
        bad += ['%s: %s' % (name, p) for p in prob]
    sev = os.path.join(out, 'soundevents'); os.makedirs(sev, exist_ok=True)
    dst = os.path.join(sev, 'soundevents_addon.vsndevts')
    base = open(template, encoding='utf-8').read()
    base = LEGACY.sub(r'\1\n', base)                     # the tw1-tw35 block had its own markers (on the root brace line)
    text = E.merge(base, E.wrap(events()), TAG)
    open(dst, 'w', newline='\n', encoding='utf-8').write(text)
    eprob, names = check_events(text, shipped)
    bad += eprob
    rp = os.path.join(HERE, '..', 'out', 'sounds_report.json')
    json.dump(dict(sounds=report, events=names, problems=bad), open(rp, 'w'), indent=1)
    print('%-17s %5s %2s %7s %7s %5s %8s  %-26s %s' % ('sound', 'sec', 'ch', 'peak dB', 'rms dB', 'crest', 'centroid', 'sub/low/mid/high/air', 'loop seam (step, kink, level dB)'))
    for name, r in report.items():
        b = r['bands']
        seam = '   seam %.2f %.2f %+.2f' % (r['seam_step_vs_p999'], r['seam_kink_vs_p999'], r['seam_level_db']) if r['loop'] else ''
        print('%-17s %5.2f %2d %7.2f %7.2f %5.1f %8d  %.2f/%.2f/%.2f/%.2f/%.2f%s%s' % (name, r['seconds'], r['channels'], r['peak_dbfs'], r['rms_dbfs'],
              r['crest_db'], r['centroid_hz'], b['sub_120'], b['low_500'], b['mid_2k'], b['high_8k'], b['air'], seam, '' if r['shipped'] else '   (pending)'))
    print('sounds: %d wavs shipped + %d pending, %d events (%s) -> %s' % (len(shipped), len(SOUNDS) - len(shipped), len(names), TAG, dst))
    if bad and '--no-check' not in argv:
        print('\n'.join('SOUND: ' + b for b in bad)); sys.exit(1)
    print('sound checks: clean' if not bad else 'sound checks: %d problems (ignored)' % len(bad))


if __name__ == '__main__':
    main(sys.argv[1:])
