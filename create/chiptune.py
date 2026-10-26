"""chiptune.py: an old-sound-chip synthesiser for original game sounds and music (numpy only, 44.1 kHz).

The four voices of a classic chip: two pulse waves (duty 12.5 / 25 / 50 %, band-limited with polyBLEP so high notes
don't alias into hiss), a 16-step triangle and a noise channel (long = hiss, short = metallic buzz), with stepped
4-bit volume envelopes, pitch sweeps, a one-pole low-pass and a 22 kHz sample-and-hold "crunch".
A tiny tracker (render_part / bars_of) turns note lists into parts; mix() adds 5 ms fades at both ends so a
retriggered sound or loop never clicks. write_wav() can embed smpl + cue loop markers (Source 2 loops a sound on them).

usage (import it; nothing runs on import):
    import chiptune as C
    beep = C.blip(C.hz('A5'), 0.16, duty=0.5)                       # a short note
    n = C.n_of(1.0)
    boom = C.noise(C.exp_sweep(9000, 400, n), n) * C.decay(n, 0.35)  # noise sweep
    C.write_wav('beep.wav', C.crunch(C.norm(beep)))
    step = 60 / 140 / 4                                             # 16th notes at 140 bpm
    lead = C.render_part(32, step, 'p2', [('C5', 4), ('E5', 4), ('G5', 8), ('-', 16)], vol=0.5)
    bass = C.render_part(32, step, 'tri', [('C3', 8)] * 4)
    drum = C.render_part(32, step, 'drum', [('k', 4), ('h', 4), ('s', 4), ('h', 4)] * 2)
    C.write_wav('loop.wav', C.mix([lead, bass, drum]), loop=True)    # stereo, loop markers over the whole file
    chiptune.py <out_dir>      writes a few demo effects and a demo loop

Voices for render_part: 'p1' pulse 12.5 %, 'p2' pulse 25 %, 'p3' pulse 50 %, 'tri' triangle,
'drum' (k kick, s snare, h hat, o open hat). Notes are names like 'A4', 'C#5', 'Bb3'; '-' is a rest.

From space-racer-cs2/tools/sounds.py (MIT), made project-neutral; the loop-marker writer from
trenchwarfare-cs2/tools/sounds.py (MIT).
"""
import math, struct
import numpy as np

SR = 44100


# ---------------------------------------------------------------- the chip
def n_of(sec): return int(round(SR * sec))
def tt(n): return np.arange(n) / SR


def _blep(t, dt):
    """polyBLEP correction for a step at phase 0 (t = phase 0..1, dt = phase step per sample)"""
    out = np.zeros_like(t)
    m = t < dt
    x = t[m] / dt[m]; out[m] = x + x - x * x - 1
    m2 = t > 1 - dt
    x = (t[m2] - 1) / dt[m2]; out[m2] = x * x + x + x + 1
    return out


def pulse(freq, n, duty=0.5):
    """pulse wave (band-limited with polyBLEP so high notes don't alias into hiss); freq may be an array"""
    f = np.broadcast_to(np.asarray(freq, np.float64), (n,))
    dt = np.clip(f / SR, 1e-6, 0.5)
    ph = (np.cumsum(f) / SR) % 1.0
    x = np.where(ph < duty, 1.0, -1.0)
    x += _blep(ph, dt)
    x -= _blep((ph - duty) % 1.0, dt)
    return x - (2 * duty - 1)     # without the DC offset (the chip's output is AC-coupled)


def tri(freq, n):
    """the chip triangle: 16 steps per cycle"""
    f = np.broadcast_to(np.asarray(freq, np.float64), (n,))
    ph = np.cumsum(f) / SR % 1.0
    x = np.where(ph < 0.5, ph * 4 - 1, 3 - ph * 4)
    return np.round(x * 7.5) / 7.5


_lfsr_cache = {}
def lfsr(short):
    """the noise channel's shift register sequence (long = hiss, short = metallic buzz)"""
    if short in _lfsr_cache: return _lfsr_cache[short]
    reg = 1; out = []
    for _ in range(32767 if not short else 93):
        bit = (reg ^ (reg >> (6 if short else 1))) & 1
        reg = (reg >> 1) | (bit << 14)
        out.append(1.0 if reg & 1 else -1.0)
    _lfsr_cache[short] = np.array(out)
    return _lfsr_cache[short]


def noise(rate, n, short=False):
    """noise clocked at `rate` Hz (array ok): low rates rumble, high rates hiss"""
    seq = lfsr(short)
    r = np.broadcast_to(np.asarray(rate, np.float64), (n,))
    idx = (np.cumsum(r) / SR).astype(np.int64) % len(seq)
    return seq[idx]


def env(n, a=0.0, d=0.1, s=0.6, r=0.05):
    """ADSR in seconds, quantised to 16 volume steps like the chip"""
    out = np.zeros(n)
    ia, idd, ir = n_of(a), n_of(d), n_of(r)
    iss = max(0, n - ia - idd - ir)
    k = 0
    if ia: m = min(ia, n); out[:m] = np.linspace(0, 1, ia)[:m]; k += m
    m = min(idd, n - k); out[k:k + m] = np.linspace(1, s, idd)[:m]; k += m
    m = min(iss, n - k); out[k:k + m] = s; k += m
    m = n - k
    if m > 0: out[k:] = np.linspace(s, 0, max(ir, m))[:m]
    return np.round(out * 15) / 15


def decay(n, sec):
    """exponential fade with time constant `sec`, in 16 steps"""
    return np.round(np.exp(-tt(n) / max(sec, 1e-4)) * 15) / 15


def exp_sweep(f0, f1, n):
    """frequency sliding from f0 to f1 over n samples (exponential, as the ear hears pitch)"""
    return f0 * (f1 / f0) ** (np.arange(n) / max(1, n - 1))


def lowpass(x, cutoff):
    """one-pole low-pass"""
    a = 1 - math.exp(-2 * math.pi * cutoff / SR)
    try:
        from scipy.signal import lfilter         # fast path; same filter
        return lfilter([a], [1, a - 1], x)
    except ImportError:
        y = np.empty_like(x); acc = 0.0
        for i in range(len(x)):
            acc += a * (x[i] - acc); y[i] = acc
        return y


def crunch(x, music=False):
    """the chip's colour: effects get a 22 kHz sample-and-hold and 8-bit steps; music only loses its DC offset
    (whole tracks through 8 bits would hiss)"""
    x = x - x.mean()
    if music: return x
    y = x.copy()
    y[1::2] = y[0::2][:len(y[1::2])]
    return np.round(y * 127) / 127


def norm(x, gain=0.9):
    m = np.abs(x).max() or 1
    return x / m * gain


def cat(*xs): return np.concatenate(xs)


NOTE = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11, 'Bb': 10, 'Eb': 3, 'Ab': 8,
        'Db': 1, 'Gb': 6}
def hz(name):
    """'A4' -> 440"""
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((NOTE[pitch] + 12 * (octave + 1) - 69) / 12)


def oct_down(note): return note[:-1] + str(int(note[-1]) - 1)
def oct_up(note): return note[:-1] + str(int(note[-1]) + 1)


def blip(f, sec, duty=0.25, a=0.0, d=0.05, s=0.5, r=0.03):
    """one pulse note with an ADSR"""
    n = n_of(sec); return pulse(f, n, duty) * env(n, a, d, s, r)


# ---------------------------------------------------------------- the tracker
def render_part(steps, step_sec, voice, seq, vol=1.0, pan=0.0, vib=0.0, gate=0.85):
    """one voice: seq = [(note or '-' rest or drum letter, length in steps)]. Returns (left, right) arrays.
    pan -1 (left) .. 1 (right); vib = vibrato depth (0.01 = 1 %); gate = how much of each step a note holds."""
    total = n_of(steps * step_sec)
    L = np.zeros(total); R = np.zeros(total)
    pos = 0
    for tok, ln in seq:
        start = n_of(pos * step_sec); n = n_of(ln * step_sec * gate) if voice != 'drum' else n_of(min(ln, 2) * step_sec)
        pos += ln
        if tok == '-' or start >= total: continue
        n = min(n, total - start)
        if voice == 'drum':
            if tok == 'k': x = tri(exp_sweep(180, 45, n), n) * decay(n, 0.09) * 1.3
            elif tok == 's': x = noise(6000, n) * decay(n, 0.07) * 0.8 + tri(exp_sweep(260, 160, n), n) * decay(n, 0.04) * 0.5
            elif tok == 'h': x = noise(22000, n) * decay(n, 0.015) * 0.35
            elif tok == 'o': x = noise(20000, n) * decay(n, 0.08) * 0.3
            else: continue
        else:
            f = hz(tok)
            if vib: f = f * (1 + vib * np.sin(2 * math.pi * 6 * tt(n)) * np.clip(tt(n) / 0.15 - 0.5, 0, 1))
            if voice == 'tri': x = tri(f, n) * env(n, 0.0, 0.02, 1.0, 0.01)
            else:
                duty = {'p1': 0.125, 'p2': 0.25, 'p3': 0.5}[voice]
                x = pulse(f, n, duty) * env(n, 0.0, 0.08, 0.55, 0.03) * 0.5
        x = x * vol
        L[start:start + n] += x * (1 - max(0, pan)); R[start:start + n] += x * (1 + min(0, pan))
    return L, R


def bars_of(chords, pattern):
    """expand a per-bar chord list with a pattern function (chord -> list of (note, steps))"""
    out = []
    for c in chords: out += pattern(c)
    return out


def mix(parts, gain=0.85, cutoff=9000):
    """sum (left, right) parts into a stereo (n, 2) array, soften the top end, normalise, 5 ms fades at both ends"""
    n = max(len(p[0]) for p in parts)
    L = np.zeros(n); R = np.zeros(n)
    for a, b in parts: L[:len(a)] += a; R[:len(b)] += b
    m = max(np.abs(L).max(), np.abs(R).max()) or 1
    L = lowpass(crunch(L / m * gain, True), cutoff); R = lowpass(crunch(R / m * gain, True), cutoff)
    m = max(np.abs(L).max(), np.abs(R).max()) or 1
    L *= gain / m; R *= gain / m
    out = np.stack([L, R], 1)
    return fades(out)


def fades(x, sec=0.005):
    """fade in and out over `sec` so a retrigger never clicks (mono or stereo)"""
    x = np.array(x, np.float64, copy=True)
    f = min(n_of(sec), len(x) // 2)
    if f:
        ramp = np.linspace(0, 1, f)
        if x.ndim == 2: ramp = ramp[:, None]
        x[:f] *= ramp; x[-f:] *= ramp[::-1]
    return x


# ---------------------------------------------------------------- files
def write_wav(path, x, loop=False, loop_start=0, loop_end=None):
    """16-bit wav, mono (n,) or stereo (n, 2). loop=True adds smpl + cue chunks marking a loop (default: the whole
    file), which Source 2 uses to loop the sound."""
    x = np.asarray(x, np.float64)
    ch = 1 if x.ndim == 1 else x.shape[1]
    pcm = (np.clip(x, -1, 1) * 32000).astype('<i2').tobytes()
    n = x.shape[0]
    fmt = struct.pack('<HHIIHH', 1, ch, SR, SR * 2 * ch, 2 * ch, 16)
    chunks = b'fmt ' + struct.pack('<I', len(fmt)) + fmt
    if loop:
        end = n - 1 if loop_end is None else loop_end
        cue = struct.pack('<I', 1) + struct.pack('<II4sIII', 1, loop_start, b'data', 0, 0, loop_start)
        smpl = struct.pack('<9I', 0, 0, int(1e9 / SR), 60, 0, 0, 0, 1, 0) + struct.pack('<6I', 1, 0, loop_start, end, 0, 0)
        chunks += b'cue ' + struct.pack('<I', len(cue)) + cue + b'smpl' + struct.pack('<I', len(smpl)) + smpl
    chunks += b'data' + struct.pack('<I', len(pcm)) + pcm
    with open(path, 'wb') as f:
        f.write(b'RIFF' + struct.pack('<I', 4 + len(chunks)) + b'WAVE' + chunks)
    return n / SR


def demo(out_dir):
    """a few effects and an 8-bar loop, to hear what the chip does"""
    import os
    os.makedirs(out_dir, exist_ok=True)
    fx = {}
    fx['beep'] = blip(hz('A5'), 0.16, 0.5, 0, 0.04, 0.6, 0.05)
    fx['coin'] = cat(blip(hz('B5'), 0.07, 0.5), blip(hz('E6'), 0.3, 0.5, 0, 0.05, 0.6, 0.2))
    n = n_of(1.0)
    fx['boom'] = noise(exp_sweep(9000, 400, n), n) * decay(n, 0.35) * 1.2 + pulse(exp_sweep(220, 40, n), n, 0.5) * decay(n, 0.25) * 0.5
    n = n_of(0.5)
    fx['warp'] = pulse(exp_sweep(200, 3200, n) * (1 + 0.04 * np.sin(2 * math.pi * 30 * tt(n))), n, 0.125) * env(n, 0.01, 0.1, 0.8, 0.15)
    for k, x in fx.items(): write_wav(os.path.join(out_dir, k + '.wav'), fades(crunch(norm(x))))
    CH = {'Am': ['A4', 'C5', 'E5', 'A5'], 'F': ['F4', 'A4', 'C5', 'F5'], 'C': ['C5', 'E5', 'G5', 'C6'], 'G': ['G4', 'B4', 'D5', 'G5']}
    BASS = {'Am': 'A2', 'F': 'F2', 'C': 'C3', 'G': 'G2'}
    chords = ['Am', 'F', 'C', 'G'] * 2
    step = 60 / 150 / 4
    steps = 16 * len(chords)
    arp = bars_of(chords, lambda c: [(CH[c][k % 4], 1) for k in (0, 1, 2, 3, 2, 1, 0, 1, 2, 3, 2, 3, 1, 2, 3, 1)])
    bass = bars_of(chords, lambda c: [(BASS[c], 2), (oct_up(BASS[c]), 2)] * 4)
    drums = bars_of(chords, lambda c: [('k', 2), ('h', 2), ('s', 2), ('h', 1), ('k', 1), ('k', 2), ('h', 2), ('s', 2), ('o', 2)])
    lead = bars_of(chords, lambda c: [(CH[c][2], 6), (CH[c][1], 2), (CH[c][3], 8)])
    loop = mix([render_part(steps, step, 'p1', arp, 0.33, 0.35), render_part(steps, step, 'tri', bass, 0.9),
                render_part(steps, step, 'drum', drums, 0.6), render_part(steps, step, 'p2', lead, 0.45, -0.2, vib=0.012)])
    sec = write_wav(os.path.join(out_dir, 'loop.wav'), loop, loop=True)
    return sorted(fx) + ['loop'], sec


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2: sys.exit(__doc__)
    names, sec = demo(sys.argv[1])
    print('chiptune demo: %s (loop %.2f s) -> %s' % (', '.join(names), sec, sys.argv[1]))
