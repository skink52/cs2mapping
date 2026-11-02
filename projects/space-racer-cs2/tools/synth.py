"""synth.py: a small offline synthesiser for original game music (numpy + scipy, 44.1 kHz, no samples).

Instruments: distorted rhythm guitar (detuned saw stack -> tube-ish waveshaper at 2x oversampling -> cabinet EQ, with
palm mutes), bass (saw + sub sine, low-pass, drive), lead (detuned saws, vibrato, drive, ping-pong delay), pad / choir /
organ, a drum kit built from sine sweeps, noise and inharmonic square stacks, and a noise riser. Mixing: per-track gain
and pan, sidechain pump from the kick, a synthesised-impulse convolution reverb, a block-based bus compressor and a
soft-clip limiter. An arranger (song structure, riffs) goes on top; this file only makes sound.

Events are (start_seconds, duration_seconds, pitch, velocity, flags): pitch is a MIDI note or a list of MIDI notes,
velocity 0..1, flags a dict ('mute' for palm mutes, 'slide' for a pitch slide-in). Drums take (start, name, velocity).

usage:
    import synth as S
    n = S.sec(8)
    gtr = S.Guitar(seed=1).render([(0, 0.5, [40, 47], 1.0, {'mute': True}), ...], n)
    kit = S.Drums().render([(0, 'kick', 1.0), (0.5, 'snare', 0.9)], n)          # {group: buffer}
    m = S.Mixer(n); m.pump = S.pump_curve([0, 1, 2], n)
    m.add(gtr, -3, -0.3); m.add(kit['kick'], 0); S.write_wav('out.wav', m.master())
    synth.py <out.wav>          renders an 8-second demo of every instrument

Then normalise for CS2 music (two-pass ffmpeg loudnorm I=-16:TP=-1.5:LRA=11, MP3 128k or a 16-bit WAV).

From hellmatch-cs2/tools/synth.py (MIT), made project-neutral.
"""
import math
import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 44100


def sec(t):
    return int(round(t * SR))


def midi_hz(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def db(x):
    return 10.0 ** (x / 20.0)


# ----------------------------------------------------------------------------------------------- oscillators
def _blep(t, dt):
    """polyBLEP correction for a discontinuity at phase 0 (t in [0,1), dt = phase step per sample)."""
    y = np.zeros_like(t)
    m = t < dt
    if m.any():
        x = t[m] / dt[m]
        y[m] = x + x - x * x - 1.0
    m = t > 1.0 - dt
    if m.any():
        x = (t[m] - 1.0) / dt[m]
        y[m] = x * x + x + x + 1.0
    return y


def phase(freq, n, phase0=0.0):
    f = np.asarray(freq, dtype=np.float64)
    dt = np.full(n, f / SR) if f.ndim == 0 else f[:n] / SR
    return (phase0 + np.cumsum(dt)) % 1.0, dt


def saw(freq, n, phase0=0.0):
    t, dt = phase(freq, n, phase0)
    return 2.0 * t - 1.0 - _blep(t, dt)


def pulse(freq, n, width=0.5, phase0=0.0):
    t, dt = phase(freq, n, phase0)
    t2 = (t + width) % 1.0
    return (2.0 * t - 1.0 - _blep(t, dt)) - (2.0 * t2 - 1.0 - _blep(t2, dt))


def sine(freq, n, phase0=0.0):
    t, _ = phase(freq, n, phase0)
    return np.sin(2 * np.pi * t)


def noise(n, rng):
    return rng.uniform(-1.0, 1.0, n)


# ----------------------------------------------------------------------------------------------- envelopes / filters
def env_exp(n, tau, hold=0.0):
    t = np.arange(n) / SR
    return np.exp(-np.maximum(t - hold, 0) / tau)


def env_adsr(dur, a=0.005, d=0.05, s=1.0, r=0.05, n=None):
    """Linear attack, exponential decay to sustain, held for dur, then exponential release; length dur + r (+tail)."""
    n = n or sec(dur + r) + sec(0.02)
    t = np.arange(n) / SR
    env = np.ones(n)
    if a > 0:
        env = np.minimum(env, t / a)
    if d > 0 and s < 1.0:
        env *= s + (1 - s) * np.exp(-np.maximum(t - a, 0) / d)
    rel = np.exp(-np.maximum(t - dur, 0) / max(r, 1e-4))
    return env * rel


_sos_cache = {}


def sos(kind, fc, order=2, q=None):
    key = (kind, round(fc, 2), order, q)
    if key not in _sos_cache:
        fc = min(fc, SR * 0.49)
        if kind in ('lp', 'hp'):
            _sos_cache[key] = signal.butter(order, fc, btype='low' if kind == 'lp' else 'high', fs=SR, output='sos')
        elif kind == 'bp':
            lo, hi = fc, q    # q holds the upper edge for band passes
            _sos_cache[key] = signal.butter(order, [lo, min(hi, SR * 0.49)], btype='band', fs=SR, output='sos')
        elif kind == 'peak':
            # RBJ peaking EQ, order is the gain in dB, q the quality
            A = 10 ** (order / 40.0); w = 2 * np.pi * fc / SR; al = np.sin(w) / (2 * (q or 1.0))
            b = [1 + al * A, -2 * np.cos(w), 1 - al * A]; a = [1 + al / A, -2 * np.cos(w), 1 - al / A]
            _sos_cache[key] = np.array([[b[0] / a[0], b[1] / a[0], b[2] / a[0], 1.0, a[1] / a[0], a[2] / a[0]]])
        elif kind == 'res':
            # 2-pole resonant low-pass (RBJ), q = resonance
            w = 2 * np.pi * fc / SR; al = np.sin(w) / (2 * (q or 0.707)); c = np.cos(w)
            b = [(1 - c) / 2, 1 - c, (1 - c) / 2]; a = [1 + al, -2 * c, 1 - al]
            _sos_cache[key] = np.array([[b[0] / a[0], b[1] / a[0], b[2] / a[0], 1.0, a[1] / a[0], a[2] / a[0]]])
    return _sos_cache[key]


def lp(x, fc, order=2): return signal.sosfilt(sos('lp', fc, order), x)
def hp(x, fc, order=2): return signal.sosfilt(sos('hp', fc, order), x)
def bp(x, lo, hi, order=2): return signal.sosfilt(sos('bp', lo, order, hi), x)
def peak(x, fc, gain_db, q=1.0): return signal.sosfilt(sos('peak', fc, gain_db, q), x)
def reslp(x, fc, q=2.0): return signal.sosfilt(sos('res', fc, 2, q), x)


def sweep_lp(x, fc_from, fc_to, blocks=48, q=1.5):
    """Resonant low-pass whose cutoff glides exponentially from fc_from to fc_to over the signal (blockwise)."""
    out = np.empty_like(x)
    edges = np.linspace(0, len(x), blocks + 1).astype(int)
    zi = None
    for i in range(blocks):
        fc = fc_from * (fc_to / fc_from) ** ((i + 0.5) / blocks)
        s = sos('res', fc, 2, q)
        if zi is None:
            zi = signal.sosfilt_zi(s) * x[0]
        out[edges[i]:edges[i + 1]], zi = signal.sosfilt(s, x[edges[i]:edges[i + 1]], zi=zi)
    return out


def shaper(x, drive, bias=0.0):
    """tanh waveshaper with a little asymmetry (even harmonics) and the DC removed again."""
    y = np.tanh(drive * x + bias) - math.tanh(bias)
    return y / math.tanh(drive) if drive < 1 else y


def oversampled(fn, x, factor=2):
    up = signal.resample_poly(x, factor, 1)
    return signal.resample_poly(fn(up), 1, factor)[:len(x)]


def norm_active(y, target=0.25, thresh_db=-40.0):
    """Scale y so the RMS of its non-silent 50 ms blocks is `target` (so a part that only plays in some sections
    is not boosted for the silence around it)."""
    blk = sec(0.05)
    m = len(y) // blk
    if m == 0:
        return y
    r = np.sqrt(np.mean(y[:m * blk].reshape(m, blk) ** 2, axis=1))
    act = r[r > db(thresh_db)]
    ref = np.sqrt(np.mean(act ** 2)) if len(act) else (np.sqrt(np.mean(y ** 2)) + 1e-9)
    return y / (ref + 1e-9) * target


def add(buf, x, at):
    """Mix x into buf starting at sample `at`, clipped to the buffer."""
    if at >= len(buf):
        return
    if at < 0:
        x = x[-at:]; at = 0
    m = min(len(x), len(buf) - at)
    if m > 0:
        buf[at:at + m] += x[:m]


# ----------------------------------------------------------------------------------------------- instruments
class Guitar:
    """Distorted rhythm guitar. Notes are summed clean (so power chords intermodulate in the amp) and the amp runs
    over the whole track. 'mute' flag = palm mute (short, dark). tone: 0 = scooped/dark, 1 = bright/present."""

    def __init__(self, seed=0, drive=9.0, detune=5.0, tone=0.5, cab_hz=6500, pick=0.5):
        self.rng = np.random.default_rng(seed)
        self.drive, self.detune, self.tone, self.cab_hz, self.pick = drive, detune, tone, cab_hz, pick

    def note(self, pitches, dur, vel, mute=False, slide=False):
        pitches = pitches if isinstance(pitches, (list, tuple)) else [pitches]
        n = sec(dur) + sec(0.06)
        x = np.zeros(n)
        for p in pitches:
            f = midi_hz(p)
            if slide:   # slide in from two semitones below over 70 ms
                f = midi_hz(p) * 2.0 ** ((np.minimum(np.arange(n) / SR / 0.07, 1.0) - 1.0) * 2 / 12)
            for sgn in (-1, 1):
                d = 2.0 ** (sgn * self.detune * (0.6 + 0.8 * self.rng.random()) / 1200)
                x += saw(f * d, n, self.rng.random())
        x /= 2 * len(pitches)
        if mute:
            env = env_exp(n, 0.075 + 0.02 * self.rng.random()) * np.exp(-np.maximum(np.arange(n) / SR - dur, 0) / 0.01)
            x = lp(x, 1600, 1) * env
        else:
            env = env_adsr(dur, a=0.003, d=0.6, s=0.65, r=0.025, n=n)
            x = x * env
        pk = sec(0.004)
        x[:pk] += self.pick * vel * hp(noise(pk, self.rng), 2000) * np.linspace(1, 0, pk)
        return x * vel

    def amp(self, x):
        x = hp(x, 120, 2)
        x = x + 0.8 * hp(x, 900, 1)                         # overdrive-pedal style mid push before the amp
        g = self.drive
        x = oversampled(lambda u: shaper(u, g, 0.15), x, 2)
        x = hp(x, 30, 1)
        # cabinet + tone stack
        x = lp(x, self.cab_hz, 2)
        x = peak(x, 400, -5.0 * (1 - self.tone) - 1.0, 1.2)     # mid scoop
        x = peak(x, 1500, 3.0, 1.0)                             # bite
        x = peak(x, 3200, 4.0 + 3.0 * self.tone, 1.0)           # presence
        x = peak(x, 110, 1.0, 1.0)                              # cabinet thump
        x = hp(x, 90, 2)
        return x

    def render(self, events, n):
        buf = np.zeros(n)
        for t0, dur, p, vel, fl in events:
            add(buf, self.note(p, dur, vel, fl.get('mute', False), fl.get('slide', False)), sec(t0))
        return norm_active(self.amp(buf))


class Bass:
    def __init__(self, seed=1, drive=2.5, sub=0.6, fc=550, electronic=False):
        self.rng = np.random.default_rng(seed)
        self.drive, self.sub, self.fc, self.electronic = drive, sub, fc, electronic

    def note(self, p, dur, vel, mute=False):
        p = p[0] if isinstance(p, (list, tuple)) else p
        n = sec(dur) + sec(0.05)
        f = midi_hz(p)
        if self.electronic:
            x = pulse(f, n, 0.3) * 0.6 + saw(f, n) * 0.4
            env = env_adsr(dur, a=0.002, d=0.08, s=0.5, r=0.02, n=n)
            x = sweep_lp(x, 2600, 300, 24, 3.0) * env
        else:
            x = saw(f, n) + 0.5 * saw(f * 1.004, n, 0.3)
            env = env_adsr(dur, a=0.003, d=0.4, s=0.7, r=0.03, n=n)
            x = sweep_lp(x, 1400, self.fc, 16, 1.2) * env
        x += self.sub * sine(f, n) * env
        return x * vel

    def render(self, events, n):
        buf = np.zeros(n)
        for t0, dur, p, vel, fl in events:
            add(buf, self.note(p, dur, vel), sec(t0))
        y = oversampled(lambda u: shaper(u, self.drive, 0.1), buf / 2.0, 2)
        y = lp(y, 2500, 2)
        y = hp(y, 35, 2)
        return norm_active(y)


class Lead:
    """Detuned saws with vibrato, light drive and a ping-pong delay (delay time in seconds, usually a dotted 8th)."""

    def __init__(self, seed=2, voices=3, detune=9.0, vib_hz=5.5, vib_depth=0.35, drive=2.2, delay=0.3, fb=0.4, dmix=0.35,
                 square=0.0):
        self.rng = np.random.default_rng(seed)
        self.voices, self.detune, self.vib_hz, self.vib_depth = voices, detune, vib_hz, vib_depth
        self.drive, self.delay, self.fb, self.dmix, self.square = drive, delay, fb, dmix, square

    def note(self, p, dur, vel, slide=False):
        p = p[0] if isinstance(p, (list, tuple)) else p
        n = sec(dur) + sec(0.12)
        t = np.arange(n) / SR
        vib = np.minimum(t / 0.18, 1.0) ** 2 * self.vib_depth * np.sin(2 * np.pi * self.vib_hz * t + self.rng.random() * 6)
        bend = -3.0 * np.maximum(1 - t / 0.09, 0) if slide else 0.0
        f = midi_hz(p) * 2.0 ** ((vib + bend) / 12.0)
        x = np.zeros(n)
        for i in range(self.voices):
            d = 2.0 ** (self.detune * (i - (self.voices - 1) / 2) / (max(self.voices - 1, 1) / 2) / 1200)
            x += saw(f * d, n, self.rng.random()) * (1 - self.square) + pulse(f * d, n, 0.45, self.rng.random()) * self.square
        env = env_adsr(dur, a=0.008, d=0.3, s=0.8, r=0.08, n=n)
        return x / self.voices * env * vel

    def render(self, events, n):
        buf = np.zeros(n)
        for t0, dur, p, vel, fl in events:
            add(buf, self.note(p, dur, vel, fl.get('slide', False)), sec(t0))
        y = hp(buf, 180, 2)
        y = oversampled(lambda u: shaper(u, self.drive, 0.05), y, 2)
        y = lp(y, 6500, 2)
        y = peak(y, 1800, 3.0, 1.0)
        return pingpong(norm_active(y), self.delay, self.fb, self.dmix)


class Pad:
    """mode 'choir' (formant-filtered detuned saws), 'strings' (bright saws) or 'organ' (drawbar sines)."""

    def __init__(self, seed=3, mode='choir', voices=6, detune=14.0):
        self.rng = np.random.default_rng(seed)
        self.mode, self.voices, self.detune = mode, voices, detune

    def note(self, pitches, dur, vel):
        pitches = pitches if isinstance(pitches, (list, tuple)) else [pitches]
        n = sec(dur) + sec(0.9)
        x = np.zeros(n)
        for p in pitches:
            f = midi_hz(p)
            if self.mode == 'organ':
                for h, g in ((1, 1.0), (2, 0.7), (3, 0.5), (4, 0.4), (6, 0.2), (8, 0.15)):
                    x += g * sine(f * h, n, self.rng.random())
            else:
                t = np.arange(n) / SR
                for i in range(self.voices):
                    d = 2.0 ** (self.detune * (i - (self.voices - 1) / 2) / (self.voices - 1) / 1200)
                    lfo = 1 + 0.0015 * np.sin(2 * np.pi * (0.1 + 0.07 * i) * t + i)
                    x += saw(f * d * lfo, n, self.rng.random())
        x /= max(len(pitches), 1) * (3 if self.mode == 'organ' else self.voices)
        a = 0.02 if self.mode == 'organ' else 0.35
        env = env_adsr(dur, a=a, d=0.1, s=1.0, r=0.6, n=n)
        return x * env * vel

    def render(self, events, n):
        buf = np.zeros(n)
        for t0, dur, p, vel, fl in events:
            add(buf, self.note(p, dur, vel), sec(t0))
        if self.mode == 'choir':
            y = 0.6 * bp(buf, 500, 900, 2) + 0.5 * bp(buf, 1100, 1600, 2) + 0.4 * lp(buf, 700, 2) + 0.15 * bp(buf, 2400, 3200, 2)
        elif self.mode == 'strings':
            y = lp(buf, 3200, 2)
        else:
            y = lp(buf, 5000, 1)
        y = hp(y, 120, 2)
        return chorus(norm_active(y), self.rng)


class Drums:
    """Synthesised kit: kick, snare, clap, hat, ohat, crash, china, ride, tom_h, tom_m, tom_l, riser."""

    def __init__(self, seed=4, style='rock'):
        self.rng = np.random.default_rng(seed)
        self.style = style
        self.cache = {}

    def metallic(self, n, base, tau):
        ratios = (1.0, 1.342, 1.2312, 1.6532, 1.9025, 2.5177, 3.11, 4.07)
        x = sum(pulse(base * r, n, 0.5, self.rng.random()) for r in ratios) / len(ratios)
        return x * env_exp(n, tau)

    def make(self, name):
        rng = self.rng
        if name == 'kick':
            n = sec(0.5); t = np.arange(n) / SR
            f = 46 + 130 * np.exp(-t / 0.028) + 40 * np.exp(-t / 0.004)
            x = sine(f, n) * env_exp(n, 0.14, 0.01)
            x = np.tanh(1.8 * x) * 0.9
            x[:sec(0.006)] += 0.8 * hp(noise(sec(0.006), rng), 2000) * np.linspace(1, 0, sec(0.006))
            x += 0.25 * bp(noise(n, rng), 1500, 5000, 2) * env_exp(n, 0.012)
            if self.style == 'electronic':
                x += 0.35 * sine(f * 0.5 + 10, n) * env_exp(n, 0.2)
                x = np.tanh(1.5 * x)
            return lp(x, 9000, 2)
        if name == 'snare':
            n = sec(0.35); t = np.arange(n) / SR
            body = sine(190 - 40 * np.exp(-t / 0.01), n) * env_exp(n, 0.055) + 0.6 * sine(335, n) * env_exp(n, 0.035)
            nz = noise(n, rng)
            wires = bp(nz, 1500, 7500, 2) * env_exp(n, 0.11) + 0.5 * hp(nz, 400, 2) * env_exp(n, 0.16)
            x = 0.9 * body + 0.9 * wires
            if self.style == 'electronic':
                x = 0.7 * body + 1.1 * hp(nz, 800, 2) * env_exp(n, 0.2) * (t < 0.22)   # gated
            x = np.tanh(1.6 * x)
            x[:sec(0.002)] += 0.4 * np.linspace(1, 0, sec(0.002))
            return x
        if name == 'clap':
            n = sec(0.3); x = np.zeros(n)
            for k in range(3):
                add(x, bp(noise(sec(0.03), rng), 900, 4500, 2) * env_exp(sec(0.03), 0.008), sec(0.011 * k))
            x += bp(noise(n, rng), 800, 5000, 2) * env_exp(n, 0.07, 0.03) * 0.8
            return x
        if name in ('hat', 'ohat'):
            tau = 0.025 if name == 'hat' else 0.22
            n = sec(0.1 if name == 'hat' else 0.7)
            x = 0.6 * hp(noise(n, rng), 7000, 2) * env_exp(n, tau) + 0.5 * hp(self.metallic(n, 420, tau * 1.3), 6000, 2)
            return x
        if name == 'crash':
            n = sec(2.6)
            x = 0.7 * bp(noise(n, rng), 2500, 13000, 2) * (0.5 * env_exp(n, 0.9) + 0.5 * env_exp(n, 0.12))
            x += 0.5 * hp(self.metallic(n, 310, 1.0), 2500, 2)
            return x * 0.8
        if name == 'china':
            n = sec(1.5)
            x = 0.8 * bp(noise(n, rng), 1500, 9000, 2) * env_exp(n, 0.4) + 0.6 * hp(self.metallic(n, 230, 0.5), 1500, 2)
            return np.tanh(1.3 * x)
        if name == 'ride':
            n = sec(0.9); t = np.arange(n) / SR
            x = 0.35 * hp(noise(n, rng), 5000, 2) * env_exp(n, 0.3) + 0.4 * hp(self.metallic(n, 520, 0.5), 3000, 2)
            x += 0.3 * np.sin(2 * np.pi * 2900 * t) * env_exp(n, 0.08)
            return x
        if name.startswith('tom'):
            f0 = {'tom_h': 210, 'tom_m': 150, 'tom_l': 100}[name]
            n = sec(0.45); t = np.arange(n) / SR
            x = sine(f0 * (0.75 + 0.45 * np.exp(-t / 0.05)), n) * env_exp(n, 0.16)
            x += 0.25 * bp(noise(n, rng), 800, 4000, 2) * env_exp(n, 0.02)
            return np.tanh(1.5 * x)
        if name == 'riser':
            n = sec(3.2)
            x = sweep_lp(noise(n, rng), 250, 9000, 64, 2.5) * np.linspace(0.05, 1.0, n) ** 2
            return hp(x, 120, 2) * 0.6
        raise KeyError(name)

    def hit(self, name):
        if name not in self.cache:
            self.cache[name] = self.make(name)
        return self.cache[name]

    GROUPS = {'kick': 'kick', 'snare': 'snare', 'clap': 'snare', 'hat': 'hat', 'ohat': 'hat', 'crash': 'cym', 'china': 'cym',
              'ride': 'cym', 'tom_h': 'tom', 'tom_m': 'tom', 'tom_l': 'tom', 'riser': 'cym'}

    def render(self, events, n):
        """events: (t, name, vel). Returns {group: mono buffer} so the mixer can treat kick, snare, hats etc. apart."""
        bufs = {g: np.zeros(n) for g in set(self.GROUPS.values())}
        for t0, name, vel in events:
            h = self.hit(name)
            if name == 'riser':
                add(bufs['cym'], h * vel, sec(t0))
                continue
            # tiny velocity-dependent brightness: scale, and for very soft hits, dull it a little
            x = h * (0.3 + 0.7 * vel) ** 1.3
            add(bufs[self.GROUPS[name]], x, sec(t0))
        for g in bufs:
            if np.any(bufs[g]):
                bufs[g] = bufs[g] / (np.max(np.abs(bufs[g])) + 1e-9) * 0.9
        return bufs


# ----------------------------------------------------------------------------------------------- effects
def pingpong(x, delay, fb=0.4, mix=0.35, taps=8):
    """Mono in, stereo out: alternating left/right echoes (vectorised, no feedback loop needed)."""
    n = len(x)
    out = np.zeros((n, 2)); out[:, 0] = x; out[:, 1] = x
    d = sec(delay)
    wet = lp(x, 3500, 1)
    for k in range(1, taps + 1):
        g = mix * fb ** (k - 1)
        if g < 0.005:
            break
        ch = (k - 1) % 2
        add(out[:, ch], wet * g, k * d)
    return out


def chorus(x, rng, depth=0.004, rate=0.35):
    """Two modulated fractional-delay copies, one per channel: mono in, stereo out."""
    n = len(x); t = np.arange(n)
    out = np.zeros((n, 2))
    for ch, (ph, r) in enumerate(((0.0, rate), (0.5, rate * 1.17))):
        delay = SR * (0.012 + depth * np.sin(2 * np.pi * r * t / SR + 2 * np.pi * ph))
        out[:, ch] = 0.6 * x + 0.6 * np.interp(t - delay, t, x)
    return out


def reverb_ir(seed=7, length=1.6, predelay=0.02):
    """Stereo impulse: decaying noise with faster decay in the highs, a few early reflections, predelay."""
    rng = np.random.default_rng(seed)
    n = sec(length); t = np.arange(n) / SR
    ir = np.zeros((n, 2))
    for ch in range(2):
        nz = noise(n, rng)
        x = lp(nz, 700, 1) * np.exp(-t / 0.55) + bp(nz, 700, 4000, 1) * np.exp(-t / 0.35) + hp(nz, 4000, 1) * np.exp(-t / 0.15)
        x[:sec(0.01)] *= np.linspace(0, 1, sec(0.01))
        for k in range(6):                                     # early reflections
            at = sec(0.008 + 0.009 * k + 0.004 * rng.random())
            x[at] += 0.5 * (0.8 ** k) * (1 if rng.random() < 0.5 else -1)
        ir[:, ch] = x
    ir /= np.sqrt(np.sum(ir ** 2)) / 2
    pre = np.zeros((sec(predelay), 2))
    return np.vstack([pre, ir])


def reverb(x, ir):
    """x stereo (n,2), ir stereo: convolve each channel (fft)."""
    n = len(x)
    out = np.zeros((n, 2))
    for ch in range(2):
        out[:, ch] = signal.fftconvolve(x[:, ch], ir[:, ch])[:n]
    return out


def pump_curve(kick_times, n, depth=0.35, release=0.16):
    """Sidechain gain: dips to 1-depth on every kick and recovers exponentially."""
    g = np.ones(n)
    tail = sec(release * 5)
    shape = 1 - depth * np.exp(-np.arange(tail) / SR / release)
    for t0 in kick_times:
        at = sec(t0)
        m = min(tail, n - at)
        if m > 0:
            g[at:at + m] = np.minimum(g[at:at + m], shape[:m])
    return g


def compress(x, thr_db=-16.0, ratio=3.0, attack=0.004, release=0.12, block=64, makeup_db=0.0):
    """Feed-forward bus compressor; the detector runs at block rate (cheap) and the gain is interpolated."""
    n = len(x)
    nb = (n + block - 1) // block
    pad = np.zeros((nb * block, x.shape[1]) if x.ndim == 2 else nb * block)
    pad[:n] = x
    pk = np.max(np.abs(pad).reshape(nb, block, -1), axis=(1, 2))
    att = math.exp(-block / SR / attack); rel = math.exp(-block / SR / release)
    env = np.zeros(nb); e = 0.0
    for i in range(nb):
        p = pk[i]
        e = p + (e - p) * (att if p > e else rel)
        env[i] = e
    env_db = 20 * np.log10(env + 1e-9)
    gain_db = np.where(env_db > thr_db, (thr_db - env_db) * (1 - 1 / ratio), 0.0) + makeup_db
    g = np.interp(np.arange(n), np.arange(nb) * block + block / 2, db(gain_db))
    return x * (g[:, None] if x.ndim == 2 else g)


def softclip(x, knee=0.6):
    """Linear below `knee`, smooth tanh bend above it, never exceeds 1.0."""
    a = np.abs(x)
    over = a > knee
    y = x.copy()
    y[over] = np.sign(x[over]) * (knee + (1 - knee) * np.tanh((a[over] - knee) / (1 - knee)))
    return y


def pan(x, p):
    """mono -> stereo with constant-power pan, p in -1..1."""
    th = (p + 1) * np.pi / 4
    if x.ndim == 2:
        return x * np.array([np.cos(th) * 1.414, np.sin(th) * 1.414])[None, :] * 0.707
    return np.stack([x * np.cos(th), x * np.sin(th)], axis=1)


class Mixer:
    """Collects tracks: add(buffer, gain_db, pan, send_db, pump) then master() -> stereo float array."""

    def __init__(self, n, ir=None):
        self.n = n
        self.dry = np.zeros((n, 2))
        self.send = np.zeros((n, 2))
        self.ir = ir if ir is not None else reverb_ir()
        self.pump = None

    def add(self, x, gain_db=0.0, p=0.0, send_db=-100.0, pump=0.0, hpf=None):
        if x.ndim == 1 and hpf:
            x = hp(x, hpf, 2)
        y = pan(x[:self.n], p) * db(gain_db)
        if pump and self.pump is not None:
            y = y * (1 - pump + pump * self.pump)[:, None]
        self.dry += y
        if send_db > -60:
            self.send += y * db(send_db)

    def master(self, comp_thr=-14.0, ratio=3.0, drive_db=3.0, peak_dbfs=-1.0, eq=((180, -2.0, 1.0), (3000, 2.5, 0.8))):
        x = self.dry + reverb(self.send, self.ir)
        for fc, g, q in eq:                                   # master tone: tame low mids, add presence
            x = np.stack([peak(x[:, c], fc, g, q) for c in range(2)], axis=1)
        x = compress(x, comp_thr, ratio, 0.006, 0.15)
        x = softclip(x * db(drive_db))
        x = x / (np.max(np.abs(x)) + 1e-9) * db(peak_dbfs)
        return x


def write_wav(path, x):
    wavfile.write(path, SR, np.clip(x, -1, 1).astype(np.float32))



def demo(path, bpm=140):
    """8 seconds: power-chord riff, bass, lead line, pad, drums, mixed and written to path"""
    beat = 60.0 / bpm
    n = sec(8.5)
    riff = [(k * beat / 2, beat / 2 * 0.9, [40, 47] if k % 4 else [40, 47, 52], 0.9, {'mute': k % 4 != 0}) for k in range(30)]
    bass = [(k * beat, beat * 0.9, 28, 0.9, {}) for k in range(15)]
    lead = [(4 * beat + k * beat, beat * 0.9, p, 0.8, {}) for k, p in enumerate([64, 67, 69, 71, 72, 71, 69, 67])]
    pad = [(0, 8 * beat, [52, 55, 59], 0.6, {}), (8 * beat, 7 * beat, [50, 53, 57], 0.6, {})]
    drums, kicks = [], []
    for k in range(16):
        t = k * beat
        drums.append((t, 'kick' if k % 2 == 0 else 'snare', 1.0)); drums.append((t + beat / 2, 'hat', 0.6))
        if k % 2 == 0: kicks.append(t)
    drums.append((0, 'crash', 0.8))
    kit = Drums().render(drums, n)
    m = Mixer(n)
    m.pump = pump_curve(kicks, n, 0.25, 0.14)
    m.add(Guitar(seed=1).render(riff, n), -4, -0.35, -18, 0.3)
    m.add(Guitar(seed=2).render(riff, n), -4, 0.35, -18, 0.3)
    m.add(Bass().render(bass, n), -3, 0.0, -100, 0.4)
    m.add(Lead().render(lead, n), -6, 0.1, -12)
    m.add(Pad().render(pad, n), -12, 0.0, -8, 0.3)
    for g, x in kit.items(): m.add(x, {'kick': -1, 'snare': -3}.get(g, -8), 0.0, -16 if g != 'kick' else -100)
    out = m.master()
    write_wav(path, out)
    return out


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2: sys.exit(__doc__)
    x = demo(sys.argv[1])
    print('synth demo: %.1f s stereo -> %s' % (len(x) / SR, sys.argv[1]))
