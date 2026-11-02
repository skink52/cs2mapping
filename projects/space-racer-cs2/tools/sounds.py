"""Chiptune sounds and music for Space Racer (all original, synthesised here) and their sound events.

usage: sounds.py <addon_out_dir> <soundevents_template.vsndevts>
Writes sounds/spr/*.wav, soundevents/soundevents_addon.vsndevts (the template with our events added) and
_gen/music.json (loop lengths for the script).

Every sound is made from the four voices of an old sound chip: two pulse waves (duty 12.5 / 25 / 50 %), a triangle
and a noise channel, with stepped (4-bit) volume envelopes and a 22 kHz sample-and-hold for the crunch.
The music is four original pieces written below as note lists: a lobby loop, two race loops (they take turns)
and a results jingle.
"""
import os, sys, math, wave, json
import numpy as np

OUT = sys.argv[1]
TEMPLATE = sys.argv[2] if len(sys.argv) > 2 else None
SR = 44100
rng = np.random.RandomState(5)

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
    if ia: out[k:k + ia] = np.linspace(0, 1, ia); k += ia
    m = min(idd, n - k); out[k:k + m] = np.linspace(1, s, idd)[:m]; k += m
    m = min(iss, n - k); out[k:k + m] = s; k += m
    m = n - k
    if m > 0: out[k:] = np.linspace(s, 0, max(ir, m))[:m]
    return np.round(out * 15) / 15

def decay(n, sec):
    return np.round(np.exp(-tt(n) / max(sec, 1e-4)) * 15) / 15

def exp_sweep(f0, f1, n):
    return f0 * (f1 / f0) ** (np.arange(n) / max(1, n - 1))

def lowpass(x, cutoff):
    """one-pole low-pass (vectorised via lfilter-free recursion in chunks)"""
    a = 1 - math.exp(-2 * math.pi * cutoff / SR)
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc += a * (x[i] - acc); y[i] = acc
    return y

def crunch(x, music=False):
    """the chip's colour: effects get a 22 kHz sample-and-hold and 8-bit steps; music only a soft top end
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

NOTE = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11, 'Bb': 10, 'Eb': 3, 'Ab': 8}
def hz(name):
    """'A4' -> 440"""
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((NOTE[pitch] + 12 * (octave + 1) - 69) / 12)

def blip(f, sec, duty=0.25, a=0.0, d=0.05, s=0.5, r=0.03):
    n = n_of(sec); return pulse(f, n, duty) * env(n, a, d, s, r)

# ---------------------------------------------------------------- sound effects
SOUNDS = {}
def S(name, x, gain=0.9): SOUNDS[name] = crunch(norm(x, gain))

S('beep', blip(hz('A5'), 0.16, 0.5, 0, 0.04, 0.6, 0.05))
S('go', cat(*[blip(hz(n), 0.05, 0.25, 0, 0.02, 0.8, 0.0) for n in ('C6', 'E6', 'G6')], blip(hz('C7'), 0.5, 0.5, 0, 0.1, 0.6, 0.3)))
n = n_of(1.0)
S('wreck', noise(exp_sweep(9000, 400, n), n) * decay(n, 0.35) * 1.2 + pulse(exp_sweep(220, 40, n), n, 0.5) * decay(n, 0.25) * 0.5)
fan = cat(*[blip(hz(f), 0.09, 0.5, 0, 0.03, 0.7, 0.01) for f in ('C5', 'E5', 'G5', 'C6', 'E6', 'G6')], blip(hz('C7'), 0.55, 0.25, 0, 0.1, 0.6, 0.3))
bass = tri(hz('C3'), len(fan)) * 0.6
S('finish', fan + bass)
n = n_of(0.5); S('warp', pulse(exp_sweep(200, 3200, n) * (1 + 0.04 * np.sin(2 * math.pi * 30 * tt(n))), n, 0.125) * env(n, 0.01, 0.1, 0.8, 0.15))
S('lap', cat(blip(hz('E6'), 0.08, 0.5), blip(hz('B6'), 0.22, 0.5, 0, 0.05, 0.6, 0.12)))
n = n_of(1.3)
S('pulse', tri(exp_sweep(160, 40, n), n) * env(n, 0.05, 0.4, 0.6, 0.6) + 0.5 * noise(exp_sweep(800, 6000, n), n) * env(n, 0.4, 0.2, 0.5, 0.6))
S('pulsed', cat(*[blip(hz(f), 0.045, 0.125, 0, 0.02, 0.7, 0.0) for f in ('G6', 'B6', 'D7', 'G7', 'B7')]))
n = n_of(0.12); S('hit', noise(2500, n) * decay(n, 0.04) + 0.6 * pulse(exp_sweep(180, 60, n), n, 0.5) * decay(n, 0.05))
n = n_of(0.22); S('rail', noise(14000, n, short=True) * decay(n, 0.06) * 0.7 + pulse(hz('E6'), n, 0.125) * decay(n, 0.08))
n = n_of(0.4); S('scrape', noise(20000 + 4000 * np.sin(2 * math.pi * 17 * tt(n)), n, short=True) * env(n, 0.02, 0.1, 0.6, 0.15))
n = n_of(0.35); S('pad', pulse(exp_sweep(400, 1600, n), n, 0.125) * env(n, 0, 0.1, 0.7, 0.12) + 0.4 * noise(exp_sweep(3000, 12000, n), n) * decay(n, 0.15))
n = n_of(0.75); S('fall', pulse(exp_sweep(1400, 90, n), n, 0.5) * env(n, 0, 0.1, 0.8, 0.25))
n = n_of(0.3); S('spin', pulse(1200 + 700 * np.sin(2 * math.pi * 40 * tt(n)), n, 0.25) * env(n, 0, 0.05, 0.7, 0.1))
S('reset', cat(*[blip(hz(f), 0.06, 0.5, 0, 0.02, 0.7, 0.01) for f in ('A5', 'E6', 'A6')]))
n = n_of(0.8)
S('boost', noise(exp_sweep(1500, 9000, n), n) * env(n, 0.02, 0.2, 0.8, 0.3) * 0.9 + 0.5 * pulse(exp_sweep(110, 330, n), n, 0.25) * env(n, 0.0, 0.2, 0.7, 0.3))
n = n_of(0.7)
arp_f = np.array([hz('A5'), hz('C#6'), hz('E6')])[(tt(n) * 30).astype(int) % 3]
S('charge', pulse(arp_f, n, 0.125) * env(n, 0.02, 0.1, 0.7, 0.25) + 0.5 * tri(hz('A3'), n) * env(n, 0.05, 0.1, 0.8, 0.25))
# engine grains (0.5 s, soft ends so the 0.38 s retriggers blend): idle, cruise, flat out, boosting
def hum(f0, bright):
    n = n_of(0.5); t_ = tt(n)
    duty = 0.25 + 0.2 * np.sin(2 * math.pi * 7 * t_)
    x = pulse(f0 * (1 + 0.01 * np.sin(2 * math.pi * 23 * t_)), n, 0.5) * 0.5 + tri(f0 * 0.5, n) * 0.6
    x += bright * 0.35 * pulse(f0 * 2, n, 0.125) + 0.15 * noise(f0 * 40, n)
    e = np.minimum(1, np.minimum(t_ / 0.08, (0.5 - t_) / 0.2))
    return x * np.clip(e, 0, 1)
for k, (f0, br) in enumerate(((65, 0.0), (98, 0.3), (140, 0.6), (185, 1.0))):
    S('hum%d' % k, hum(f0, br), 0.8)
n = n_of(0.3); S('jump', pulse(exp_sweep(300, 1200, n), n, 0.25) * env(n, 0, 0.1, 0.7, 0.1))
if os.environ.get('SPR_THEME') == 'depth':
    # Depth Racer: a sea creature's call as it sets off across the track - a long, low moan sliding down, with a
    # throaty growl in it and a hiss of water
    n = n_of(2.4); t_ = tt(n)
    f0 = 92 * np.exp(-t_ / 3.0) * (1 + 0.04 * np.sin(2 * np.pi * 5.5 * t_))
    moan = tri(f0, n) + 0.6 * pulse(f0 * 0.5, n, 0.3) * (0.5 + 0.5 * np.sin(2 * np.pi * 9 * t_))
    S('creature', lowpass(moan * env(n, 0.25, 0.4, 0.8, 0.9), 900) + 0.15 * noise(exp_sweep(2000, 400, n), n) * env(n, 0.3, 0.5, 0.5, 0.8), 0.95)
n = n_of(0.28); S('land', noise(exp_sweep(3000, 300, n), n) * decay(n, 0.08) + 0.7 * tri(exp_sweep(150, 50, n), n) * decay(n, 0.1))
# new: the countdown's last beep, a "new best lap" chime, a position-gained blip
S('beep2', blip(hz('A6'), 0.2, 0.5, 0, 0.04, 0.6, 0.08))
S('best', cat(*[blip(hz(f), 0.07, 0.25, 0, 0.02, 0.7, 0.01) for f in ('E6', 'G#6', 'B6')], blip(hz('E7'), 0.3, 0.25, 0, 0.05, 0.6, 0.2)))
# the cars' E abilities: Seeker Bolt launch ('dash': a zip up), Shockwave (a deep thump and rumble), Nova Burn (a rising roar),
# Aegis (a shimmering chord)
n = n_of(0.22); S('dash', pulse(exp_sweep(500, 4200, n), n, 0.125) * env(n, 0, 0.05, 0.8, 0.08) + 0.5 * noise(exp_sweep(4000, 16000, n), n) * decay(n, 0.12))
n = n_of(0.8); S('quake', tri(exp_sweep(150, 28, n), n) * env(n, 0, 0.3, 0.7, 0.4) * 1.3 + noise(exp_sweep(3000, 200, n), n) * decay(n, 0.3))
n = n_of(1.0)
nova_f = np.array([hz('C5'), hz('G5'), hz('C6'), hz('E6')])[np.minimum(3, (tt(n) * 6).astype(int))]
S('nova', noise(exp_sweep(800, 14000, n), n) * env(n, 0.05, 0.3, 0.8, 0.35) + 0.6 * pulse(nova_f, n, 0.25) * env(n, 0, 0.2, 0.6, 0.3))
n = n_of(0.7)
aeg_f = np.array([hz('C6'), hz('E6'), hz('G6'), hz('C7')])[(tt(n) * 40).astype(int) % 4]
S('aegis', tri(aeg_f, n) * env(n, 0.02, 0.2, 0.7, 0.3) + 0.4 * pulse(aeg_f * 0.5, n, 0.5) * env(n, 0.02, 0.2, 0.5, 0.3))

# ---------------------------------------------------------------- music
# A tiny tracker: each part is a list of (note or '-' rest, length in steps). Voices: 'p1' pulse 12.5 %, 'p2' pulse
# 25 %, 'p3' pulse 50 %, 'tri' triangle, 'drum' (k kick, s snare, h hat, o open hat).
def render_part(steps, step_sec, voice, seq, vol=1.0, pan=0.0, vib=0.0, gate=0.85):
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

CH = {   # chord tones (root, third, fifth, octave) for the arpeggios; bass root
    'Am': ['A4', 'C5', 'E5', 'A5'], 'F': ['F4', 'A4', 'C5', 'F5'], 'C': ['C5', 'E5', 'G5', 'C6'], 'G': ['G4', 'B4', 'D5', 'G5'],
    'E': ['E4', 'G#4', 'B4', 'E5'], 'Dm': ['D4', 'F4', 'A4', 'D5'], 'Bb': ['A#3', 'D4', 'F4', 'A#4'], 'Em': ['E4', 'G4', 'B4', 'E5'],
}
BASS = {'Am': 'A2', 'F': 'F2', 'C': 'C3', 'G': 'G2', 'E': 'E2', 'Dm': 'D3', 'Bb': 'A#2', 'Em': 'E2'}
def oct_down(note): return note[:-1] + str(int(note[-1]) - 1)
def oct_up(note): return note[:-1] + str(int(note[-1]) + 1)

def song_race():
    """'Neon Overdrive' - 156 bpm, A minor; 16 bars: 8 of groove, 8 with the lead"""
    bpm = 156; step = 60 / bpm / 4
    chords = ['Am', 'F', 'C', 'G', 'Am', 'F', 'G', 'E'] * 2
    steps = 16 * len(chords)
    arp = bars_of(chords, lambda c: [(CH[c][k % 4], 1) for k in (0, 1, 2, 3, 2, 1, 0, 1, 2, 3, 2, 3, 1, 2, 3, 1)])
    bass = bars_of(chords, lambda c: [(BASS[c], 2), (oct_up(BASS[c]), 2)] * 4)
    drums = bars_of(chords, lambda c: [('k', 2), ('h', 2), ('s', 2), ('h', 1), ('k', 1), ('k', 2), ('h', 2), ('s', 2), ('o', 2)])
    lead = [('-', 16 * 8)] + [
        ('E5', 2), ('A5', 2), ('C6', 2), ('E6', 4), ('D6', 2), ('C6', 2), ('B5', 2),
        ('A5', 4), ('C6', 2), ('A5', 2), ('F5', 4), ('G5', 2), ('A5', 2),
        ('G5', 2), ('E5', 2), ('G5', 2), ('C6', 4), ('B5', 2), ('C6', 2), ('D6', 2),
        ('D6', 6), ('B5', 2), ('G5', 4), ('A5', 2), ('B5', 2),
        ('C6', 2), ('B5', 2), ('A5', 2), ('E6', 6), ('D6', 2), ('C6', 2),
        ('A5', 2), ('C6', 2), ('F6', 4), ('E6', 2), ('D6', 2), ('C6', 4),
        ('B5', 2), ('D6', 2), ('G6', 4), ('F6', 2), ('E6', 2), ('D6', 4),
        ('G#5', 4), ('B5', 4), ('E6', 6), ('-', 2)]
    # counter line in the first half: long notes on the 50 % pulse
    counter = bars_of(chords[:8], lambda c: [(CH[c][2], 6), (CH[c][1], 2), (CH[c][3], 8)]) + [('-', 16 * 8)]
    parts = [render_part(steps, step, 'p1', arp, 0.33, 0.35), render_part(steps, step, 'tri', bass, 0.9),
             render_part(steps, step, 'drum', drums, 0.6), render_part(steps, step, 'p2', lead, 0.55, -0.2, vib=0.012),
             render_part(steps, step, 'p3', counter, 0.28, -0.35, vib=0.008)]
    return parts, steps * step

def song_race2():
    """'Starlight Circuit' - 168 bpm, E minor; a bouncing octave bass, a call-and-answer lead and a fast arp"""
    bpm = 168; step = 60 / bpm / 4
    chords = ['Em', 'C', 'D', 'B', 'Em', 'C', 'Am', 'B'] * 2
    CH2 = dict(CH); CH2['D'] = ['D4', 'F#4', 'A4', 'D5']; CH2['B'] = ['B3', 'D#4', 'F#4', 'B4']
    BASS2 = dict(BASS); BASS2['D'] = 'D3'; BASS2['B'] = 'B2'
    steps = 16 * len(chords)
    arp = bars_of(chords, lambda c: [(oct_up(CH2[c][k]), 1) for k in (0, 2, 1, 3, 0, 2, 1, 3, 3, 2, 1, 0, 1, 2, 3, 2)])
    bass = bars_of(chords, lambda c: [(BASS2[c], 1), ('-', 1), (oct_up(BASS2[c]), 1), ('-', 1)] * 4)
    drums = bars_of(chords, lambda c: [('k', 2), ('h', 1), ('h', 1), ('s', 2), ('h', 2), ('k', 1), ('k', 1), ('h', 2), ('s', 2), ('h', 1), ('s', 1)])
    call = [('E5', 2), ('G5', 2), ('B5', 4), ('A5', 2), ('G5', 2), ('F#5', 4)]
    lead = [('-', 16 * 4)] + \
        call + [('E5', 4), ('G5', 2), ('C6', 6), ('B5', 4)] + \
        [('A5', 2), ('B5', 2), ('D6', 4), ('C6', 2), ('B5', 2), ('A5', 4)] + [('F#5', 4), ('A5', 2), ('B5', 6), ('-', 4)] + \
        call + [('E5', 4), ('G5', 2), ('C6', 6), ('E6', 4)] + \
        [('D6', 2), ('C6', 2), ('B5', 4), ('A5', 2), ('C6', 2), ('E6', 4)] + [('D#6', 4), ('B5', 4), ('F#6', 6), ('-', 2)] + \
        [('G6', 6), ('F#6', 2), ('E6', 4), ('B5', 4)] + [('E6', 4), ('D6', 4), ('C6', 8)] + [('-', 16)] * 2
    lead_steps = sum(n for _, n in lead)
    if lead_steps < steps: lead.append(('-', steps - lead_steps))
    parts = [render_part(steps, step, 'p1', arp, 0.26, 0.35), render_part(steps, step, 'tri', bass, 0.95),
             render_part(steps, step, 'drum', drums, 0.6), render_part(steps, step, 'p2', lead, 0.5, -0.25, vib=0.014)]
    return parts, steps * step

def song_lobby():
    """'Parking Orbit' - 100 bpm, D minor; dreamy arpeggios over a slow triangle bass, soft hats"""
    bpm = 100; step = 60 / bpm / 4
    chords = ['Dm', 'Bb', 'F', 'C', 'Dm', 'Bb', 'C', 'Am']
    steps = 16 * len(chords)
    arp = bars_of(chords, lambda c: [(CH[c][k], 1) for k in (0, 2, 1, 3, 2, 0, 3, 1, 0, 2, 1, 3, 2, 3, 1, 2)])
    arp2 = bars_of(chords, lambda c: [('-', 3)] + [(oct_up(CH[c][k]), 2) for k in (2, 1, 3, 2, 1, 3)] + [('-', 1)])
    bass = bars_of(chords, lambda c: [(oct_down(BASS[c]) if BASS[c][-1] == '3' else BASS[c], 6), (BASS[c], 2), (BASS[c], 4), (CH[c][2][:-1] + '2', 4)])
    hats = bars_of(chords, lambda c: [('h', 2), ('-', 2)] * 4)
    melody = [('A5', 6), ('F5', 2), ('D5', 8), ('F5', 6), ('D6', 2), ('A#5', 8), ('A5', 6), ('C6', 2), ('F5', 8), ('E5', 4), ('G5', 4), ('C6', 8),
              ('D6', 6), ('C6', 2), ('A5', 8), ('A#5', 4), ('A5', 4), ('F5', 8), ('G5', 4), ('E5', 4), ('C6', 8), ('A5', 12), ('-', 4)]
    parts = [render_part(steps, step, 'p1', arp, 0.3, 0.4), render_part(steps, step, 'p1', arp2, 0.16, -0.4),
             render_part(steps, step, 'tri', bass, 0.8), render_part(steps, step, 'drum', hats, 0.5),
             render_part(steps, step, 'p3', melody, 0.32, -0.1, vib=0.015)]
    return parts, steps * step

def song_results():
    """a 4-second fanfare for the results screen"""
    bpm = 140; step = 60 / bpm / 4
    lead = [('G5', 1), ('C6', 1), ('E6', 1), ('G6', 1), ('E6', 2), ('G6', 2), ('A6', 4), ('F6', 2), ('A6', 2), ('C7', 8), ('-', 8)]
    harm = [('E5', 4), ('C5', 4), ('F5', 4), ('A5', 4), ('E5', 8), ('-', 8)]
    bass = [('C3', 4), ('C3', 4), ('F2', 4), ('F2', 4), ('C3', 8), ('-', 8)]
    drums = [('s', 1), ('s', 1), ('s', 1), ('s', 1), ('k', 4), ('k', 4), ('s', 4), ('k', 8), ('-', 8)]
    steps = 32
    parts = [render_part(steps, step, 'p2', lead, 0.55, vib=0.01), render_part(steps, step, 'p1', harm, 0.3, 0.3),
             render_part(steps, step, 'tri', bass, 0.9), render_part(steps, step, 'drum', drums, 0.7)]
    return parts, steps * step

MUSIC = {}
def mix(parts, sec, gain=0.85):
    n = max(len(p[0]) for p in parts)
    L = np.zeros(n); R = np.zeros(n)
    for a, b in parts: L[:len(a)] += a; R[:len(b)] += b
    m = max(np.abs(L).max(), np.abs(R).max()) or 1
    L = lowpass(crunch(L / m * gain, True), 9000); R = lowpass(crunch(R / m * gain, True), 9000)
    m = max(np.abs(L).max(), np.abs(R).max()) or 1
    L *= gain / m; R *= gain / m
    # 5 ms fades at both ends so a retrigger never clicks
    f = n_of(0.005)
    for ch in (L, R): ch[:f] *= np.linspace(0, 1, f); ch[-f:] *= np.linspace(1, 0, f)
    return np.stack([L, R], 1)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from theme import NEON
if NEON:
    import electro                 # Neon Racer: electro / synthwave pieces instead of chiptune (Depth Racer: deep, dubby)
    MUSIC = electro.depth_music() if os.environ.get('SPR_THEME') == 'depth' else electro.neon_music()
else:
    for name, fn in (('mus_race', song_race), ('mus_race2', song_race2), ('mus_lobby', song_lobby), ('mus_results', song_results)):
        parts, sec = fn()
        MUSIC[name] = (mix(parts, sec), sec)

# ---------------------------------------------------------------- files
RANGE = {'creature': 7000, 'dash': 1500, 'quake': 2500, 'nova': 2500, 'aegis': 1800, 'beep': 6000, 'beep2': 6000, 'go': 7000, 'wreck': 3500, 'finish': 2500, 'warp': 2500, 'lap': 1200, 'best': 1200, 'pulse': 3500, 'pulsed': 1200,
         'hit': 1200, 'rail': 1200, 'scrape': 900, 'pad': 1500, 'fall': 1800, 'spin': 1500, 'reset': 1200, 'boost': 1800, 'charge': 1200,
         'hum0': 900, 'hum1': 1000, 'hum2': 1100, 'hum3': 1200, 'jump': 1500, 'land': 1500}
VOL = {'quake': 0.8, 'nova': 0.7, 'dash': 0.6, 'aegis': 0.6, 'scrape': 0.45, 'hit': 0.6, 'rail': 0.6, 'charge': 0.5, 'boost': 0.6, 'pulsed': 0.55, 'hum0': 0.3, 'hum1': 0.33, 'hum2': 0.36, 'hum3': 0.4,
       'beep': 0.7, 'beep2': 0.75, 'go': 0.75}
MUSIC_VOL = {'mus_race': 0.32, 'mus_race2': 0.32, 'mus_lobby': 0.3, 'mus_results': 0.38}

d = os.path.join(OUT, 'sounds/spr'); os.makedirs(d, exist_ok=True)
def write_wav(path, x, channels):
    with wave.open(path, 'wb') as w:
        w.setnchannels(channels); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32000).astype(np.int16).tobytes())
for name, x in SOUNDS.items(): write_wav(os.path.join(d, name + '.wav'), x, 1)
for name, (x, sec) in MUSIC.items(): write_wav(os.path.join(d, name + '.wav'), x, 2)

def curve(points):
    out = ['\t\t[']
    for dist, v in points:
        out += ['\t\t\t[', '\t\t\t\t%.1f, %.2f, 0.0, 0.0,' % (dist, v), '\t\t\t\t2.0, 3.0,', '\t\t\t],']
    return out + ['\t\t]']

ev = ['\t// ---- Space Racer sound events (generated by tools/sounds.py) ----']
for name in SOUNDS:
    r = RANGE[name]
    ev += ['\t"spr.%s" =' % name, '\t{', '\t\ttype = "csgo_mega"', '\t\tvolume = %.2f' % VOL.get(name, 0.8), '\t\tpitch = 1.0',
           '\t\tvsnd_files_track_01 = "sounds/spr/%s.vsnd"' % name, '\t\tdistance_volume_mapping_curve ='] + \
          curve([(0, 1), (r * 0.2, 1), (r, 0)]) + ['\t}']
# music: heard everywhere at the same volume, not placed in the world (stereo, no distance fall-off, no occlusion)
for name in MUSIC:
    ev += ['\t"spr.%s" =' % name, '\t{', '\t\ttype = "csgo_mega"', '\t\tvolume = %.2f' % MUSIC_VOL[name], '\t\tpitch = 1.0',
           '\t\tvsnd_files_track_01 = "sounds/spr/%s.vsnd"' % name, '\t\tocclusion_intensity = 0.0', '\t\tdistance_effect_mix = 0.0',
           '\t\trestrict_source_reverb = true', '\t\tuse_distance_unfiltered_stereo_mapping_curve = true',
           '\t\tdistance_volume_mapping_curve ='] + curve([(0, 1), (100000, 1)]) + \
          ['\t\tdistance_unfiltered_stereo_mapping_curve ='] + curve([(0, 1), (100000, 1)]) + ['\t}']
ev.append('\t// ---- end Space Racer ----')
body = '\n'.join(ev) + '\n'
os.makedirs(os.path.join(OUT, 'soundevents'), exist_ok=True)
if TEMPLATE and os.path.exists(TEMPLATE):
    tpl = open(TEMPLATE, encoding='utf-8').read()
    if '"spr.' in tpl:
        # already has ours (an addon file that was built before): replace the block
        a = tpl.index('\t// ---- Space Racer'); b = tpl.index('\t// ---- end Space Racer ----\n') + len('\t// ---- end Space Racer ----\n')
        tpl = tpl[:a] + tpl[b:]
    first = tpl.index('\n{') + 2
    text = tpl[:first] + body + tpl[first:]
else:
    text = ('<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:generic:version{7412167c-06e9-4698-aff2-e63eb59037e7} -->\n{\n' + body + '}\n')
open(os.path.join(OUT, 'soundevents/soundevents_addon.vsndevts'), 'w', newline='\n', encoding='utf-8').write(text)
os.makedirs(os.path.join(OUT, '_gen'), exist_ok=True)
json.dump({k: round(sec, 4) for k, (x, sec) in MUSIC.items()}, open(os.path.join(OUT, '_gen/music.json'), 'w'))
print('sounds: %d effects, %d music pieces (%s), events written' % (len(SOUNDS), len(MUSIC), ', '.join('%s %.1fs' % (k, s) for k, (x, s) in MUSIC.items())))
