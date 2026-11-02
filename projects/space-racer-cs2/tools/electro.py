"""Neon Racer music: four original electro / synthwave pieces made with synth.py (saw stacks, side-chained bass,
arpeggios, pads, an electronic kit). Same names and use as Space Racer's chiptune pieces: mus_lobby, mus_race,
mus_race2 (they take turns) and mus_results. Loops are seamless: the reverb / delay tail is wrapped onto the start."""
import numpy as np
import synth as S

NOTE = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}
def m(name):
    """'A2' -> MIDI"""
    return 12 * (int(name[-1]) + 1) + NOTE[name[:-1]]
def chord(root, kind='min', octave=4):
    r = m(root + str(octave))
    return [r, r + (3 if kind == 'min' else 4), r + 7]

def loop(parts_fn, bars, bpm, tail=2.5):
    beat = 60.0 / bpm
    sec = bars * 4 * beat
    n = S.sec(sec); nt = n + S.sec(tail)
    out = parts_fn(beat, bars, nt)
    out[:S.sec(tail)] += out[n:]
    out = out[:n]
    rms = np.sqrt(np.mean(out ** 2)) + 1e-9                    # loud and dense: bring the body up, round off the peaks
    out = S.softclip(out * (S.db(-12.0) / rms), 0.65)
    out = out / (np.max(np.abs(out)) + 1e-9) * S.db(-1.5)
    f = S.sec(0.004)
    out[:f] *= np.linspace(0, 1, f)[:, None]; out[-f:] *= np.linspace(1, 0, f)[:, None]
    return out, sec

def punch_kick(times, n):
    """an extra kick layer for weight: a long sub thump (60 -> 42 Hz) and a short click, on every kick"""
    k = S.sec(0.42); t = np.arange(k) / S.SR
    f = 42 + 70 * np.exp(-t / 0.035)
    sub = S.sine(f, k) * np.exp(-t / 0.22) * np.minimum(t / 0.002, 1)
    click = S.hp(S.noise(k, np.random.default_rng(3)), 2500) * np.exp(-t / 0.004) * 0.5
    one = np.tanh(2.2 * (sub + click)) * 0.9
    buf = np.zeros(n)
    for t0 in times: S.add(buf, one, S.sec(t0))
    return buf

def four_floor(beat, bars, clap=True, ohat=True, fill_every=8, hats16=False):
    ev, kicks = [], []
    for b in range(bars):
        for q in range(4):
            t = (b * 4 + q) * beat
            ev.append((t, 'kick', 1.0)); kicks.append(t)
            if clap and q in (1, 3): ev.append((t, 'clap', 0.9)); ev.append((t, 'snare', 0.85))
            if ohat: ev.append((t + beat / 2, 'ohat', 0.5))
            if hats16:
                for s_ in (1, 3): ev.append((t + s_ * beat / 4, 'hat', 0.3))
        if fill_every and b % fill_every == fill_every - 1:
            ev.append(((b * 4 + 2) * beat, 'riser', 0.6))
        if b % 8 == 0: ev.append((b * 4 * beat, 'crash', 0.6))
    return ev, kicks

PUNCH = ((70, 1.0, 0.9), (300, -3.0, 1.0), (2500, 3.0, 0.9), (7000, 2.0, 0.8))     # master tone: weight in the lows, less box, some bite

def mix_drums(mx, kit, kicks, n, hat_db=-9):
    mx.add(punch_kick(kicks, n), -8, 0.0)
    for g, x in kit.items(): mx.add(x, {'kick': -4, 'snare': -2, 'hat': hat_db + 2, 'cym': -9}.get(g, -8), 0.0, -20 if g not in ('kick',) else -100)

def race1(beat, bars, n):
    """'Grid Runner' - 124 bpm, A minor: a driven rolling 16th saw bass pumping under a four-on-the-floor kick,
    a filtered saw arpeggio, a wide supersaw lead in the second half"""
    prog = [('A', 'min'), ('F', 'maj'), ('C', 'maj'), ('G', 'maj')]
    bass, arp, pad, lead = [], [], [], []
    for b in range(bars):
        root, kind = prog[b % 4]
        ch = chord(root, kind, 4)
        pad.append((b * 4 * beat, 4 * beat, [c - 12 for c in ch], 0.7, {}))
        r1 = m(root + '1') if root in ('A', 'G') else m(root + '2') - 12
        for s_ in range(16):
            t = (b * 4 + s_ / 4) * beat
            if s_ % 4 != 0: bass.append((t, beat / 4 * 0.85, r1 + (12 if s_ % 4 == 2 else 0), 1.0 if s_ % 4 == 2 else 0.8, {}))
            arp.append((t, beat / 4 * 0.6, ch[s_ % 3] + 12 * (s_ // 8), 0.55, {}))
    mel = [('E5', 2), ('A5', 1), ('C6', 1), ('B5', 2), ('G5', 2), ('A5', 3), ('E5', 1), ('C5', 2), ('D5', 2),
           ('E5', 2), ('G5', 1), ('A5', 1), ('B5', 2), ('D6', 2), ('C6', 3), ('B5', 1), ('A5', 4)]
    t = (bars // 2) * 4 * beat
    for k in range(2):
        tt = t + k * 16 * beat
        for note, d in mel:
            if tt >= bars * 4 * beat: break
            lead.append((tt, d * beat * 0.95, m(note), 0.9, {'slide': d >= 3}))
            tt += d * beat
    drums, kicks = four_floor(beat, bars, hats16=True)
    kit = S.Drums(seed=11, style='electronic').render(drums, n)
    mx = S.Mixer(n); mx.pump = S.pump_curve(kicks, n, 0.7, 0.14)
    mx.add(S.Bass(seed=3, electronic=False, drive=4.0, sub=0.6, fc=1400).render(bass, n), -8, 0.0, -100, 0.9)
    mx.add(S.lp(S.Lead(seed=4, voices=3, detune=8, drive=1.6, delay=beat * 0.75, dmix=0.2, square=0.0, vib_depth=0.0).render(arp, n)[:, 0], 4000, 2), -9, -0.25, -18, 0.7)
    mx.add(S.Pad(seed=5, mode='strings', voices=6, detune=16).render(pad, n), -13, 0.0, -10, 0.8)
    if lead: mx.add(S.Lead(seed=6, voices=7, detune=18, drive=2.4, vib_depth=0.12, delay=beat * 0.75, dmix=0.25).render(lead, n), -3, 0.1, -12, 0.35)
    mix_drums(mx, kit, kicks, n)
    return mx.master(comp_thr=-18, ratio=4.0, drive_db=8.0, eq=PUNCH)

def race2(beat, bars, n):
    """'Neon Highway' - 128 bpm, F# minor: an octave-bouncing driven bass, stabbed saw chords, a call-and-answer lead"""
    prog = [('F#', 'min'), ('D', 'maj'), ('A', 'maj'), ('E', 'maj')]
    bass, gate, lead = [], [], []
    for b in range(bars):
        root, kind = prog[b % 4]
        ch = chord(root, kind, 4)
        r1 = m(root + '1') if root in ('F#', 'E') else m(root + '2') - 12
        for e in range(8):
            t = (b * 4 + e / 2) * beat
            bass.append((t, beat / 2 * 0.75, r1 + (12 if e % 2 else 0), 1.0 if e % 2 else 0.85, {}))
            if e in (1, 3, 6): gate.append((t, beat / 2 * 0.35, ch, 0.9, {}))
    call = [('C#5', 1), ('E5', 1), ('F#5', 2), ('-', 4)]
    answer = [('A5', 1), ('G#5', 1), ('E5', 1), ('C#5', 1), ('E5', 4)]
    for b in range(4, bars, 2):
        tt = b * 4 * beat
        for note, d in (call if (b // 2) % 2 == 0 else answer):
            if note != '-': lead.append((tt, d * beat * 0.9, m(note), 0.9, {}))
            tt += d * beat
    drums, kicks = four_floor(beat, bars, ohat=True)
    kit = S.Drums(seed=12, style='electronic').render(drums, n)
    mx = S.Mixer(n); mx.pump = S.pump_curve(kicks, n, 0.7, 0.13)
    mx.add(S.Bass(seed=7, electronic=False, drive=4.5, sub=0.6, fc=1300).render(bass, n), -8, 0.0, -100, 0.9)
    mx.add(S.Lead(seed=8, voices=5, detune=14, drive=2.0, delay=beat * 0.5, dmix=0.2, vib_depth=0.0).render(gate, n), -6, 0.0, -14, 0.8)
    mx.add(S.Lead(seed=9, voices=7, detune=16, drive=2.4, vib_depth=0.1, delay=beat * 0.75, dmix=0.3).render(lead, n), -3, 0.15, -12, 0.35)
    mix_drums(mx, kit, kicks, n, -10)
    return mx.master(comp_thr=-18, ratio=4.0, drive_db=8.0, eq=PUNCH)

def lobby(beat, bars, n):
    """'After Hours' - 100 bpm, D minor: a heavy half-time groove, a dark pad and a slow saw arpeggio"""
    prog = [('D', 'min'), ('A#', 'maj'), ('F', 'maj'), ('C', 'maj')]
    bass, arp, pad = [], [], []
    for b in range(bars):
        root, kind = prog[b % 4]
        ch = chord(root, kind, 4)
        pad.append((b * 4 * beat, 4 * beat, [c - 12 for c in ch], 0.8, {}))
        r1 = m(root + '2') - 12
        for e in range(8):
            bass.append(((b * 4 + e / 2) * beat, beat / 2 * 0.8, r1 + (12 if e in (3, 7) else 0), 0.95 if e % 2 == 0 else 0.7, {}))
        for s_ in range(8):
            arp.append(((b * 4 + s_ / 2) * beat, beat / 2 * 0.5, ch[(0, 1, 2, 1)[s_ % 4]] + 12, 0.5, {}))
    ev, kicks = [], []
    for b in range(bars):
        for q in range(4):
            t = (b * 4 + q) * beat
            if q == 0 or (q == 2 and b % 2): ev.append((t, 'kick', 1.0)); kicks.append(t)
            if q == 2: ev.append((t, 'snare', 0.9)); ev.append((t, 'clap', 0.7))
            ev.append((t + beat / 2, 'hat', 0.35))
    kit = S.Drums(seed=13, style='electronic').render(ev, n)
    mx = S.Mixer(n); mx.pump = S.pump_curve(kicks, n, 0.5, 0.25)
    mx.add(S.Bass(seed=14, electronic=False, drive=3.0, sub=0.6, fc=1000).render(bass, n), -8, 0.0, -100, 0.7)
    mx.add(S.Pad(seed=15, mode='strings', voices=7, detune=20).render(pad, n), -8, 0.0, -6, 0.5)
    mx.add(S.lp(S.Lead(seed=16, voices=3, detune=7, drive=1.3, delay=beat * 0.75, dmix=0.4, fb=0.5, square=0.0, vib_depth=0.0).render(arp, n)[:, 0], 3500, 2), -8, -0.2, -10, 0.4)
    mix_drums(mx, kit, kicks, n, -12)
    return mx.master(comp_thr=-18, ratio=3.5, drive_db=7.0, eq=PUNCH)

def results(beat, bars, n):
    """a short electro sting: a rising saw arpeggio into a held supersaw chord over a sub hit"""
    notes = [m(x) for x in ('A4', 'C5', 'E5', 'A5', 'C6', 'E6')]
    arp = [(k * beat / 4, beat / 4 * 0.9, p, 0.8, {}) for k, p in enumerate(notes * 2)]
    hold = [(3 * beat, 4 * beat, [m('A4'), m('C#5'), m('E5'), m('A5')], 0.9, {})]
    bass = [(3 * beat, 4 * beat, m('A1'), 1.0, {})]
    drums = [(0, 'riser', 0.7), (3 * beat, 'kick', 1.0), (3 * beat, 'crash', 0.9), (3 * beat, 'clap', 0.9)]
    kit = S.Drums(seed=17, style='electronic').render(drums, n)
    mx = S.Mixer(n)
    mx.add(S.Lead(seed=18, voices=5, detune=12, delay=beat * 0.5, dmix=0.3).render(arp, n), -6, 0.0, -10)
    mx.add(S.Lead(seed=19, voices=7, detune=18, drive=2.0, delay=beat * 0.75, dmix=0.3).render([(3 * beat, 4 * beat, p, 0.8, {}) for p in hold[0][2]], n), -6, 0.0, -8)
    mx.add(S.Bass(seed=20, drive=3.0, sub=1.0).render(bass, n), -3)
    mx.add(punch_kick([3 * beat], n), -1)
    for g, x in kit.items(): mx.add(x, -4, 0.0, -12)
    return mx.master(drive_db=4.0, eq=PUNCH)

def neon_music():
    out = {}
    for name, fn, bars, bpm in (('mus_race', race1, 16, 124), ('mus_race2', race2, 16, 128), ('mus_lobby', lobby, 8, 100)):
        out[name] = loop(fn, bars, bpm)
    x, _ = loop(results, 2, 120, tail=0.01)
    out['mus_results'] = (x, 4 * 60 / 120 * 2)
    return out

# ---------------------------------------------------------------- Depth Racer: atmospheric jungle / liquid drum & bass
def sonar(times, n, note=m('E6')):
    """a sonar ping: a pure tone with a long watery echo"""
    k = S.sec(1.4); t = np.arange(k) / S.SR
    one = S.sine(S.midi_hz(note) * (1 - 0.02 * t), k) * np.exp(-t / 0.35) * np.minimum(t / 0.003, 1)
    buf = np.zeros(n)
    for t0 in times:
        S.add(buf, one, S.sec(t0))
        S.add(buf, one * 0.35, S.sec(t0 + 0.37)); S.add(buf, one * 0.15, S.sec(t0 + 0.74))
    return buf

# ---- atmospheric jungle / liquid drum & bass (170-174 bpm): chopped breaks, reese bass under a long sub, lush pads,
# electric piano chords and an airy lead, everything washed in reverb

def fm_ep(events, n, seed=40, bright=1.0):
    """an FM electric piano (Rhodes-like): a sine carrier, a ratio-1 modulator for the bark and a high tine, slow tremolo"""
    rng = np.random.default_rng(seed)
    buf = np.zeros(n)
    for t0, dur, pitches, vel, fl in events:
        pitches = pitches if isinstance(pitches, (list, tuple)) else [pitches]
        k = S.sec(dur + 1.2); t = np.arange(k) / S.SR
        for p in pitches:
            f = S.midi_hz(p) * (1 + 0.0007 * rng.standard_normal())
            idx = bright * (1.6 * np.exp(-t / 0.25) + 0.3)
            x = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * t))
            x += 0.18 * bright * np.sin(2 * np.pi * f * 14 * t) * np.exp(-t / 0.03)
            env = np.minimum(t / 0.002, 1) * np.exp(-t / 1.4) * np.exp(-np.maximum(t - dur, 0) / 0.18)
            S.add(buf, x * env * vel / len(pitches) ** 0.5, S.sec(t0))
    tt = np.arange(n) / S.SR
    return S.chorus(S.norm_active(S.hp(buf, 140, 2) * (1 + 0.18 * np.sin(2 * np.pi * 4.2 * tt))), rng, 0.003, 0.5)

def reese(events, n, drive=2.5, lo=180, hi=1100, lfo=0.25, detune=0.011, sub=0.9, seed=41):
    """the jungle reese: two detuned saws phasing against each other through a low-pass that swells with a slow LFO,
    distorted, with a clean sine sub under it"""
    buf, subb = np.zeros(n), np.zeros(n)
    for t0, dur, p, vel, fl in events:
        k = S.sec(dur + 0.02); f = S.midi_hz(p)
        env = S.env_adsr(dur, a=0.004, d=0.2, s=0.9, r=0.02, n=k)
        x = S.saw(f * (1 - detune), k, 0.1) + S.saw(f * (1 + detune), k, 0.6) + 0.5 * S.saw(f * 2.003, k, 0.3)
        S.add(buf, x * env * vel, S.sec(t0))
        S.add(subb, S.sine(f, k) * env * vel, S.sec(t0))
    tt = np.arange(n) / S.SR
    mix_ = 0.5 - 0.5 * np.cos(2 * np.pi * lfo * tt)
    y = S.lp(buf, lo, 2) * (1 - mix_) + S.lp(buf, hi, 2) * mix_
    y = S.oversampled(lambda u: S.shaper(u, drive, 0.15), y / 2.5, 2)
    y = S.hp(S.lp(y, 3000, 2), 90, 2)
    return S.norm_active(y), S.norm_active(S.lp(subb, 120, 2)) * sub

def crunch_break(x, keep=0.6):
    """sampler grit for the breaks: 26 kHz sample-and-hold, 12-bit steps and a little drive, blended with the clean"""
    k = 44100 // 26000 + 1
    y = np.repeat(x[::k], k)[:len(x)]
    y = np.round(y * 2048) / 2048
    y = np.tanh(1.8 * y)
    return keep * y + (1 - keep) * x

AMEN = [   # 16 steps a bar: (kick, snare) velocities, 'g' = ghost snare
    ('K...S..gK.KgS..g', '.h.h.h.h.h.h.h.h'),
    ('K.K.S..g.gK.S..g', '.h.h.h.h.h.h.h.h'),
    ('K...S..gK.KgS..g', '.h.h.h.h.h.h.hhh'),
    ('K.K.S..g.gK.S.gS', '.h.h.h.h.h.h.h.h'),
]
CHOPS = [  # the 4th bar of a phrase gets one of these: rolls, rushes and stutters
    ('K...S..gK.KgSSSS', '.h.h.h.h.h.h....'),
    ('K.K.S.gSg.KgS.SS', '.h.h.h.h.h.h.h..'),
    ('K..KS.S.K.S.SgSS', '.h.h.h.h........'),
]

def jungle_break(beat, bars, rng, half=False, ride=True, drop=(), crash_every=8):
    """breakbeat events for `bars` bars (amen-flavoured: two-step kick, backbeat snare with ghosts, 16th hats, a chop
    every 4th bar). half: the lobby's half-time version. drop: bars with no drums. Returns (events, kick times)."""
    ev, kicks = [], []
    st = beat / 4
    for b in range(bars):
        if b in drop: continue
        pat, hats = (CHOPS[rng.integers(len(CHOPS))] if b % 4 == 3 else AMEN[b % 4])
        if half: pat, hats = ('K.......S......g' if b % 2 == 0 else 'K.....K.S...g..g'), '..h...h...h...h.'
        for s_ in range(16):
            t = (b * 16 + s_) * st + rng.normal(0, 0.002)
            t = max(t, 0.0)
            c = pat[s_]
            if c == 'K': ev.append((t, 'kick', 0.95 if s_ in (0, 2) else 0.85)); kicks.append(t)
            elif c == 'S': ev.append((t, 'snare', 1.0 if s_ in (4, 12) else 0.75 + 0.2 * rng.random()))
            elif c == 'g': ev.append((t, 'snare', 0.28 + 0.12 * rng.random()))
            if hats[s_] == 'h': ev.append((t, 'hat', 0.45 + 0.25 * (s_ % 4 == 2) + 0.1 * rng.random()))
            elif s_ % 2 == 0 and not half: ev.append((t, 'hat', 0.18 + 0.08 * rng.random()))
            if ride and s_ % 4 == 2: ev.append((t, 'ride', 0.35))
        if b % crash_every == 0: ev.append((b * 4 * beat, 'crash', 0.55))
        if b % 8 == 7 and (b + 1) not in drop: ev.append(((b * 4 + 0.8) * beat, 'riser', 0.35))
    return ev, kicks

def mix_breaks(mx, beat, bars, n, rng, seed, gain=-3.0, half=False, ride=True, drop=(), hp_bars=()):
    ev, kicks = jungle_break(beat, bars, rng, half, ride, drop)
    kit = S.Drums(seed=seed, style='rock').render(ev, n)
    bus = kit['kick'] * 0.9 + kit['snare'] * 1.0 + kit['hat'] * 0.32 + kit['cym'] * 0.22 + kit.get('tom', 0) * 0.5
    bus = crunch_break(S.peak(S.peak(bus, 220, 3.0, 1.2), 4500, 3.0, 0.8))
    for b in hp_bars:                                        # filtered intro / breakdown bars: the break thins out
        a, z = S.sec(b * 4 * beat), S.sec((b + 1) * 4 * beat)
        bus[a:z] = S.hp(bus[a:z], 700, 2) * 0.8
    bus = S.norm_active(bus)
    mx.add(bus, gain, 0.0, -14)
    mx.add(punch_kick(kicks, n), gain - 9, 0.0)              # a sub under each kick, so the break hits on a system
    return kicks

def liquid(beat, bars, n, key, prog, seed, lead_mel=None, drive=2.5, hi=1100, lfo=0.25, ep_rhythm=(0, 1.5, 2.5),
           drop=(), hp_bars=(), half=False, gains=None):
    """one atmospheric jungle piece: prog = per-bar (root, chord intervals); the bass follows the roots"""
    rng = np.random.default_rng(seed)
    g = dict(brk=-3.0, reese=-9.0, sub=-5.0, pad=-10.0, ep=-9.0, lead=-8.0, ping=-12.0)
    g.update(gains or {})
    pad, ep, bass, lead, pings = [], [], [], [], []
    for b in range(bars):
        root, ivs = prog[b % len(prog)]
        r = m(root + '3')
        notes = [r + i for i in ivs]
        pad.append((b * 4 * beat, 4 * beat, notes + [r + 12 + ivs[1]], 0.8, {}))
        for q in ep_rhythm: ep.append(((b * 4 + q) * beat, beat * 0.9, [x + 12 for x in notes[1:]], 0.7 if q else 0.85, {}))
        rb = m(root + '1') if NOTE[root] <= NOTE['F#'] else m(root + '0') + 12
        if half: bass.append((b * 4 * beat, 3.8 * beat, rb, 1.0, {}))
        else:
            bass += [(b * 4 * beat, 1.4 * beat, rb, 1.0, {}), ((b * 4 + 1.5) * beat, 0.9 * beat, rb, 0.8, {}),
                     ((b * 4 + 2.5) * beat, 1.4 * beat, rb + (12 if b % 2 else 7), 0.9, {})]
        if b % 2 == 1: pings.append((b * 4 + 3.5) * beat)
    if lead_mel:
        start, mel = lead_mel
        tt = start * 4 * beat
        while tt < bars * 4 * beat:
            for note, d in mel:
                if tt >= bars * 4 * beat: break
                if note != '-': lead.append((tt, d * beat * 0.92, m(note), 0.8, {'slide': d >= 2}))
                tt += d * beat
    mx = S.Mixer(n, S.reverb_ir(seed=seed, length=3.6, predelay=0.03))
    kicks = mix_breaks(mx, beat, bars, n, rng, seed + 1, g['brk'], half, True, drop, hp_bars)
    mx.pump = S.pump_curve(kicks, n, 0.45, 0.12)
    rz, sb = reese(bass, n, drive=drive, hi=hi, lfo=lfo, seed=seed + 2)
    mx.add(rz, g['reese'], 0.0, -100, 0.5)
    mx.add(sb, g['sub'], 0.0, -100, 0.6)
    mx.add(S.Pad(seed=seed + 3, mode='choir', voices=7, detune=20).render(pad, n), g['pad'], 0.0, -2, 0.35)
    mx.add(S.Pad(seed=seed + 4, mode='strings', voices=6, detune=16).render([(t, d, [p + 12 for p in ps], v, f) for t, d, ps, v, f in pad], n), g['pad'] - 6, 0.0, -2, 0.35)
    mx.add(fm_ep(ep, n, seed + 5), g['ep'], 0.15, -5, 0.3)
    if lead: mx.add(S.Lead(seed=seed + 6, voices=3, detune=6, drive=1.2, vib_depth=0.2, delay=beat * 0.75, fb=0.55, dmix=0.45).render(lead, n), g['lead'], -0.1, -4, 0.2)
    mx.add(sonar(pings, n, m(key + '6')), g['ping'], 0.35, -3)
    return mx.master(comp_thr=-16, ratio=3.5, drive_db=6.0, eq=((60, 2.0, 0.9), (300, -3.0, 1.0), (3500, 2.0, 0.8), (9000, 1.5, 0.7)))

MIN9, MAJ7, MIN7, ADD9, SUS = (0, 3, 7, 10, 14), (0, 4, 7, 11, 14), (0, 3, 7, 10), (0, 4, 7, 14), (0, 5, 7, 10)

def depth1(beat, bars, n):
    """'Pressure' - 172 bpm, F minor: rolling amen chops, a phasing reese under a deep sub, choir pads and Rhodes
    chords, an airy lead in the second half"""
    prog = [('F', MIN9), ('C#', MAJ7), ('A#', MIN9), ('C', SUS)] * 2 + [('F', MIN9), ('C#', MAJ7), ('D#', ADD9), ('C', SUS)] * 2
    mel = [('C6', 2), ('G#5', 1), ('A#5', 3), ('-', 2), ('C6', 1), ('D#6', 1), ('C6', 2), ('A#5', 2), ('G#5', 4), ('-', 4),
           ('F5', 2), ('G#5', 2), ('A#5', 2), ('C6', 2), ('C#6', 3), ('C6', 1), ('A#5', 4), ('-', 4)]
    return liquid(beat, bars, n, 'F', prog, 50, (16, mel), drive=2.6, hi=1200, lfo=0.23, hp_bars=(0, 1), drop=(15,))

def depth2(beat, bars, n):
    """'Leviathan' - 174 bpm, A minor: darker and heavier - a growling reese that opens wide, chopped-up breaks,
    a cold pad and a call-and-answer lead"""
    prog = [('A', MIN9), ('F', MAJ7), ('D', MIN9), ('E', SUS)] * 2 + [('A', MIN9), ('C', MAJ7), ('G', ADD9), ('E', SUS)] * 2
    mel = [('E5', 1), ('A5', 1), ('C6', 2), ('B5', 2), ('-', 2), ('E6', 1), ('D6', 1), ('C6', 2), ('A5', 4), ('-', 2),
           ('G5', 1), ('A5', 1), ('C6', 3), ('D6', 1), ('E6', 4), ('-', 4)]
    return liquid(beat, bars, n, 'A', prog, 60, (8, mel), drive=4.0, hi=1700, lfo=0.43, ep_rhythm=(0, 0.75, 2.5, 3.25),
                  drop=(23,), gains=dict(reese=-7.5, ep=-11.0))

def depth_lobby(beat, bars, n):
    """'Still Water' - 172 bpm in half time, D minor: a slow rolling break with a ride, a long sub, wide pads and Rhodes"""
    prog = [('D', MIN9), ('A#', MAJ7), ('G', MIN9), ('A', SUS)]
    return liquid(beat, bars, n, 'D', prog, 70, None, drive=1.8, hi=700, lfo=0.12, ep_rhythm=(0, 1.5, 3.0), half=True,
                  gains=dict(brk=-5.0, pad=-7.0, ep=-7.0))

def depth_music():
    out = {}
    for name, fn, bars, bpm in (('mus_race', depth1, 32, 172), ('mus_race2', depth2, 32, 174), ('mus_lobby', depth_lobby, 16, 172)):
        out[name] = loop(fn, bars, bpm, tail=3.0)
    x, _ = loop(results, 2, 120, tail=0.01)
    out['mus_results'] = (x, 4 * 60 / 120 * 2)
    return out
