"""Deterministic composer for the generated Hellmatch background music: writes music/gen01..gen04.mp3 (plus 20 s
previews and music/tracks.json). Everything is original and generated from seeds; nothing is sampled.

usage: compose.py [ids...] [--wav-only] [--short]
music/tracks.json keeps any entries that are not generated tracks (the trailer theme) and gets ours replaced.
Each track is a fast heavy-game-music piece in the reference's tempo range (~150 bpm +-10 %) and a minor key, with a
real song structure (intro, verse, pre-chorus, chorus with a returning hook, breakdown, solo, final chorus, outro),
rendered with tools/synth.py, loudness-normalised with ffmpeg loudnorm (two-pass, same target as tools/music.py) and
encoded as 128 kb/s MP3. --short renders only the first 32 bars (for tuning), --wav-only skips the MP3 step.
"""
import json, os, subprocess, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'music')
SCRATCH = os.environ.get('COMPOSE_SCRATCH', os.path.join(ROOT, 'build/music_gen'))
TARGET = 'I=-16:TP=-1.5:LRA=11'

SCALES = {'minor': [0, 2, 3, 5, 7, 8, 10], 'harmonic': [0, 2, 3, 5, 7, 8, 11], 'phrygian': [0, 1, 3, 5, 7, 8, 10],
          'dorian': [0, 2, 3, 5, 7, 9, 10], 'pent': [0, 3, 5, 7, 10], 'blues': [0, 3, 5, 6, 7, 10]}

# drum patterns: 16th-note slots per bar; hats get accents on the quarter notes
PATTERNS = {
    'drive': {'kick': [0, 6, 8, 14], 'snare': [4, 12], 'hat': range(0, 16, 2)},
    'drive2': {'kick': [0, 3, 6, 8, 11, 14], 'snare': [4, 12], 'hat': range(0, 16, 2)},
    'gallop': {'kick': [0, 2, 3, 4, 6, 7, 8, 10, 11, 12, 14, 15], 'snare': [4, 12], 'hat': range(0, 16, 2)},
    'double': {'kick': range(16), 'snare': [4, 12], 'hat': range(0, 16, 2)},
    'thrash': {'kick': range(0, 16, 2), 'snare': [4, 12], 'hat': range(0, 16, 2)},
    'skank': {'kick': [0, 4, 8, 12], 'snare': [2, 6, 10, 14], 'hat': range(0, 16, 2)},
    'half': {'kick': [0, 10], 'snare': [8], 'hat': range(0, 16, 4)},
    'halfdbl': {'kick': range(16), 'snare': [8], 'china': [0, 4, 8, 12]},
    'four': {'kick': [0, 4, 8, 12], 'clap': [4, 12], 'hat': range(0, 16, 2), 'ohat': [2, 6, 10, 14]},
    'four16': {'kick': [0, 4, 8, 12], 'clap': [4, 12], 'snare': [4, 12], 'hat': range(16), 'ohat': [6, 14]},
    'ride': {'kick': [0, 6, 8, 14], 'snare': [4, 12], 'ride': range(0, 16, 2)},
    'ridegallop': {'kick': [0, 2, 3, 4, 6, 7, 8, 10, 11, 12, 14, 15], 'snare': [4, 12], 'ride': range(0, 16, 2)},
    'intro': {'kick': [0, 8], 'hat': range(0, 16, 4)},
    'pulse': {'kick': [0, 4, 8, 12], 'hat': range(0, 16, 2), 'ohat': [2, 6, 10, 14]},
    'quarter': {'kick': [0, 8], 'hat': [0, 4, 8, 12], 'snare': [8]},
}

TRACKS = [
    dict(id='gen01', title='Ferrous Pulse', seed=1101, bpm=150, root=38, key='D minor', scale='phrygian', style='industrial',
         pool=[0, 0, 1, 3, 5, 6, 10, -2], prog=[0, 0, 3, 5], prog2=[0, 1, 0, 6], mix=dict(pad=-11, lead=-6),
         sections=[('intro', 8), ('verse', 16), ('pre', 8), ('chorus', 16), ('verse', 8), ('pre', 8), ('chorus', 16),
                   ('breakdown', 12), ('solo', 16), ('chorus', 16), ('outro', 4)]),
    dict(id='gen02', title='Chainsaw Vespers', seed=2202, bpm=164, root=45, key='A minor', scale='harmonic', style='thrash',
         pool=[0, 1, 6, 7, 5, 3, 10, -2, -5], prog=[0, 8, 6, 7], prog2=[0, 1, 0, 3], mix=dict(pad=-14, lead=-5.5),
         sections=[('intro', 8), ('verse', 16), ('pre', 8), ('chorus', 16), ('verse', 16), ('pre', 8), ('chorus', 16),
                   ('breakdown', 8), ('solo', 16), ('chorus', 16), ('outro', 4)]),
    dict(id='gen03', title='Low Orbit of Hell', seed=3303, bpm=140, root=43, key='G minor', scale='minor', style='doom',
         pool=[0, 6, 5, 3, 1, 8, 10], prog=[0, 5, 3, 1], prog2=[0, 6, 5, 0], mix=dict(pad=-11, lead=-5.5),
         sections=[('intro', 8), ('verse', 16), ('pre', 8), ('chorus', 16), ('verse', 8), ('chorus', 8),
                   ('breakdown', 16), ('solo', 12), ('chorus', 16), ('outro', 4)]),
    dict(id='gen04', title='Valkyrie Fragstorm', seed=4404, bpm=156, root=40, key='E minor', scale='minor', style='heroic',
         pool=[0, 3, 5, 7, 10, 8, 12, -2], prog=[0, 8, 3, 10], prog2=[0, 5, 8, 10], mix=dict(pad=-10, lead=-5),
         sections=[('intro', 8), ('verse', 16), ('pre', 8), ('chorus', 16), ('verse', 8), ('pre', 8), ('chorus', 16),
                   ('breakdown', 8), ('solo', 16), ('chorus', 16), ('outro', 4)]),
]


class Song:
    def __init__(self, spec, short=False):
        self.spec = spec
        self.rng = np.random.default_rng(spec['seed'])
        self.bpm = spec['bpm']; self.beat = 60.0 / self.bpm; self.bar = 4 * self.beat; self.s16 = self.beat / 4
        self.root = spec['root']; self.low = spec['root'] - 4 if spec['root'] > 42 else spec['root']
        self.scale = SCALES[spec['scale']]
        self.style = spec['style']
        self.pool = spec['pool']
        self.lead_base = self.root + (24 if self.root < 42 else 12)
        self.gL, self.gR, self.bass, self.lead, self.pad, self.drums = [], [], [], [], [], []
        self.sections = []
        secs = spec['sections']
        if short:
            secs = [('intro', 4), ('verse', 8), ('pre', 4), ('chorus', 8), ('breakdown', 4), ('solo', 4), ('outro', 4)]
        self.plan = secs
        self.riff_a = self.make_riff(self.verse_rhythm(), self.pool, accents=4, chord_prob=0.45)
        self.riff_a2 = self.turnaround(self.riff_a)
        self.riff_b = self.make_riff('stab8' if self.style != 'thrash' else 'tremolo', self.pool, accents=3, chord_prob=0.8)
        self.riff_c = self.make_riff('chorus', self.pool, accents=2, chord_prob=1.0)
        self.hook = self.make_phrase(4, self.scale, 0 if self.style != 'heroic' else 2, 0, density=0.5)
        self.hook_b = self.make_phrase(4, self.scale, 3, 2, density=0.7)
        self.intro_motif = self.make_phrase(4, self.scale, 0, 4, density=0.2)

    # ------------------------------------------------------------------ helpers
    def t(self, bar, slot=0):
        return bar * self.bar + slot * self.s16

    def chord_quality(self, off):
        """Triad intervals for a chord on scale/pool offset `off` (minor if the minor third is in the scale)."""
        third = 3 if (off + 3) % 12 in self.scale else 4
        fifth = 6 if (off + 7) % 12 not in self.scale and (off + 6) % 12 in self.scale else 7
        return [0, third, fifth]

    def verse_rhythm(self):
        return {'industrial': '16th', 'thrash': 'gallop', 'doom': '8th', 'heroic': 'gallop'}[self.style]

    # ------------------------------------------------------------------ riffs (2 bars = 32 sixteenth slots)
    def make_riff(self, rhythm, pool, accents=4, chord_prob=0.5):
        rng = self.rng
        slots = [None] * 32

        def put(i, kind, pitch, ln):
            if i >= 32:
                return
            ln = min(ln, 32 - i)
            slots[i] = dict(kind=kind, p=pitch, len=ln)
            for j in range(i + 1, i + ln):
                slots[j] = None

        if rhythm == 'gallop':
            for b in range(8):
                put(b * 4, 'mute', 0, 2); put(b * 4 + 2, 'mute', 0, 1); put(b * 4 + 3, 'mute', 0, 1)
        elif rhythm == '16th':
            for i in range(32):
                put(i, 'mute', 0, 1)
        elif rhythm == '8th':
            for i in range(0, 32, 2):
                put(i, 'mute', 0, 2)
        elif rhythm == 'stab8':
            for i in range(0, 32, 4):
                put(i, 'mute', 0, 2); put(i + 2, 'chord', 0, 2)
        elif rhythm == 'tremolo':
            seq = [0] + [int(pool[rng.integers(len(pool))]) for _ in range(5)]
            segs = [8, 8, 4, 4, 4, 4]
            i = 0
            for p, n in zip(seq, segs):
                for k in range(n):
                    put(i + k, 'note', p, 1)
                i += n
        elif rhythm == 'chorus':
            for bar in (0, 16):
                put(bar, 'chord', 0, 3)
                for i in range(bar + 3, bar + 16):
                    put(i, 'mute', 0, 1)
                for i in rng.choice([6, 10, 12, 14], size=2, replace=False):
                    put(bar + int(i), 'chord', 0, 2)
            return slots
        cand = [0, 6, 10, 12, 16, 22, 26, 28]
        pos = sorted(int(x) for x in rng.choice(cand, size=min(accents, len(cand)), replace=False))
        for k, i in enumerate(pos):
            p = 0 if (i == 0 and rng.random() < 0.6) else int(pool[rng.integers(len(pool))])
            kind = 'chord' if rng.random() < chord_prob else 'note'
            ln = int(rng.choice([2, 2, 3, 4]))
            if rhythm == 'tremolo':
                kind, ln = 'chord', 2
            put(i, kind, p, ln)
        return slots

    def turnaround(self, riff):
        """Variant of a 2-bar riff whose last two beats walk chromatically/tritonally back to the root."""
        r = [None if s is None else dict(s) for s in riff]
        walks = [[8, 7, 6, 5], [3, 5, 6, 5], [10, 8, 7, 6], [1, 0, 6, 5], [5, 6, 8, 10], [0, 0, 6, 6]]
        walk = walks[int(self.rng.integers(len(walks)))]
        kind = 'chord' if self.rng.random() < 0.5 else 'note'
        for i in range(24, 32):
            r[i] = None
        for k, p in enumerate(walk):
            r[24 + 2 * k] = dict(kind=kind, p=p, len=2)
        return r

    def play_riff(self, riff, bar0, bars, prog=None, vel=1.0, guitars=('L', 'R'), bass=True, alt=None, alt_every=4):
        """Write a riff for `bars` bars from bar0; `alt` (a riff) replaces bars alt_every-2..alt_every-1 of each loop."""
        for b in range(bars):
            cur = riff
            if alt is not None and (b % alt_every) >= alt_every - 2:
                cur = alt
            off = prog[b % len(prog)] if prog else 0
            base = b % 2
            for i in range(16):
                s = cur[base * 16 + i]
                if s is None:
                    continue
                self.note_event(b + bar0, i, s, off, vel, guitars, bass)

    def gtr_pitch(self, p, off):
        q = self.root + p + off
        while q < self.low:
            q += 12
        while q > self.low + 15:
            q -= 12
        return q

    def note_event(self, bar, slot, s, off, vel, guitars, bass):
        t0 = self.t(bar, slot)
        ln = s['len']
        accent = 1.0 if slot % 4 == 0 else (0.85 if slot % 2 == 0 else 0.75)
        q = self.gtr_pitch(s['p'], off)
        if s['kind'] == 'mute':
            ev = (t0, ln * self.s16 * 0.9, q, vel * accent * 0.95, {'mute': True})
        elif s['kind'] == 'note':
            ev = (t0, ln * self.s16 * 0.95, q, vel * accent, {})
        else:
            ev = (t0, ln * self.s16 * 0.97, [q, q + 7, q + 12], vel * min(1.0, accent + 0.1), {})
        if 'L' in guitars:
            self.gL.append(ev)
        if 'R' in guitars:
            self.gR.append(ev)
        if bass and self.style != 'industrial':
            if s['kind'] == 'mute' and ln == 1 and slot % 2 == 1:
                return
            bl = max(ln, 2) if s['kind'] == 'mute' else ln
            self.bass.append((t0, bl * self.s16 * 0.9, q - 12, vel * accent, {}))

    def bass_pulse(self, bar0, bars, prog=None, vel=1.0, rate=1):
        """Industrial 16th-note synth-bass pulse on the chord root."""
        for b in range(bars):
            off = prog[b % len(prog)] if prog else 0
            q = self.gtr_pitch(0, off) - 12
            for i in range(0, 16, rate):
                acc = 1.0 if i % 4 == 0 else 0.8
                self.bass.append((self.t(bar0 + b, i), self.s16 * rate * 0.8, q, vel * acc, {}))

    def chord_hits(self, bar0, bars, prog, slots=(0,), sustain=16, vel=1.0, bass=True):
        """Open power chords (and bass) on the given slots of each bar, ringing for `sustain` slots."""
        for b in range(bars):
            off = prog[b % len(prog)] if prog else 0
            q = self.gtr_pitch(0, off)
            for sl in slots:
                ev = (self.t(bar0 + b, sl), sustain * self.s16 * 0.95, [q, q + 7, q + 12], vel, {})
                self.gL.append(ev); self.gR.append(ev)
                if bass:
                    self.bass.append((self.t(bar0 + b, sl), sustain * self.s16 * 0.95, q - 12, vel, {}))

    # ------------------------------------------------------------------ melodies
    def make_phrase(self, bars, scale, start_deg, end_deg, density=0.5):
        """Lead phrase as (slot, len_slots, pitch_offset) over `bars` bars, shaped A A': the second half repeats the
        first with a new ending that resolves to end_deg. Mostly stepwise with the odd leap, long notes land on chord
        tones, the contour goes up then back down, and the range stays within about 1.5 octaves."""
        rng = self.rng
        ns = len(scale)
        degs = [d + 12 * o for o in range(3) for d in scale]
        lo, hi = start_deg + ns - 3, min(start_deg + ns + 7, len(degs) - 1)
        sparse = [[4, 4, 4, 4], [8, 4, 4], [4, 2, 2, 8], [6, 2, 8], [2, 2, 4, 8], [4, 4, 8]]
        mid = [[2, 2, 2, 2, 4, 4], [4, 2, 2, 4, 4], [2, 2, 4, 2, 2, 4], [3, 3, 2, 4, 4], [6, 2, 4, 4], [2, 2, 2, 2, 8], [4, 2, 2, 2, 2, 4]]
        dense = [[1, 1, 2, 1, 1, 2, 4, 4], [2, 1, 1, 2, 2, 4, 4], [2, 2, 2, 2, 2, 2, 2, 2], [1, 1, 2, 2, 2, 4, 4], [2, 2, 2, 2, 4, 2, 2]]

        def rhythm_bar():
            r = rng.random()
            tl = dense if r < density * 0.6 else (mid if r < 0.5 + density * 0.4 else sparse)
            return list(tl[int(rng.integers(len(tl)))])

        def walk(tl, cur, target, final=None):
            out = []
            for j, ln in enumerate(tl):
                r = rng.random()
                step = 1 if r < 0.55 else (2 if r < 0.8 else int(rng.choice([3, 4])))
                direction = 1 if cur < target else -1
                if rng.random() < 0.25:
                    direction = -direction
                cur = int(np.clip(cur + direction * step, lo, hi))
                if ln >= 4 and (cur % ns) not in (0, 2, 4):
                    cur = int(np.clip(cur + int(rng.choice([-1, 1])), lo, hi))
                if final is not None and j == len(tl) - 1:
                    cur = final
                out.append(cur)
            return out

        half = max(bars // 2, 1)
        rhythms = [rhythm_bar() for _ in range(half)]
        cur = start_deg + ns
        a_pitches = []
        for b in range(half):
            target = start_deg + ns + (5 if b < (half + 1) // 2 else 1)
            pit = walk(rhythms[b], cur, target, final=(start_deg + ns + int(rng.choice([1, 2, 4]))) if b == half - 1 else None)
            a_pitches.append(pit); cur = pit[-1]
        # A': same rhythm, same pitches except the last bar, which resolves
        b_pitches = [list(x) for x in a_pitches]
        last_rhythm = rhythms[-1] if rng.random() < 0.6 else rhythm_bar()
        b_pitches[-1] = walk(last_rhythm, a_pitches[-2][-1] if half > 1 else start_deg + ns, start_deg + ns - 1, final=end_deg + ns)
        rh_b = rhythms[:-1] + [last_rhythm]
        out = []
        slot = 0
        for rhythms_x, pitches_x in ((rhythms, a_pitches), (rh_b, b_pitches)):
            for tl, pit in zip(rhythms_x, pitches_x):
                for ln, cur in zip(tl, pit):
                    out.append((slot, ln, degs[cur]))
                    slot += ln
        return out

    def play_phrase(self, phrase, bar0, vel=0.9, octave=0, legato=0.92):
        for slot, ln, p in phrase:
            self.lead.append((self.t(bar0) + slot * self.s16, ln * self.s16 * legato, self.lead_base + p + 12 * octave, vel,
                              {'slide': ln >= 6}))

    def solo(self, bar0, bars):
        """16th-note runs, pedal licks, trills and long bends over the key's blues/harmonic scales."""
        rng = self.rng
        scale = SCALES['blues'] if rng.random() < 0.5 else self.scale
        degs = [d + 12 * o for o in range(3) for d in scale] + [36]
        b = 0
        while b < bars - 2:
            kind = rng.choice(['run', 'pedal', 'trill', 'bend', 'seq'])
            if kind == 'run':
                start = int(rng.integers(0, len(scale)))
                up = rng.random() < 0.6
                for i in range(32):
                    idx = int(np.clip(start + (i if up else 24 - i) * 0.75, 0, len(degs) - 1))
                    self.lead.append((self.t(bar0 + b, i), self.s16 * 0.9, self.lead_base + degs[idx], 0.85 + 0.1 * (i % 4 == 0), {}))
            elif kind == 'seq':                                   # groups of four: up 3, back 1
                start = int(rng.integers(0, len(scale)))
                for i in range(32):
                    g, j = divmod(i, 4)
                    idx = int(np.clip(start + g + [0, 1, 2, 1][j], 0, len(degs) - 1))
                    self.lead.append((self.t(bar0 + b, i), self.s16 * 0.9, self.lead_base + degs[idx], 0.9, {}))
            elif kind == 'pedal':
                top = len(scale) * 2
                for i in range(32):
                    idx = top if i % 2 == 0 else int(np.clip(top - 1 - (i // 2) % 8, 0, len(degs) - 1))
                    self.lead.append((self.t(bar0 + b, i), self.s16 * 0.9, self.lead_base + degs[idx], 0.9, {}))
            elif kind == 'trill':
                base = int(rng.integers(len(scale), 2 * len(scale)))
                for i in range(24):
                    idx = base + (i % 2)
                    self.lead.append((self.t(bar0 + b, i), self.s16 * 0.9, self.lead_base + degs[idx], 0.85, {}))
                self.lead.append((self.t(bar0 + b, 24), 8 * self.s16, self.lead_base + degs[base + 2], 1.0, {'slide': True}))
            else:                                                 # bend: long notes with slides
                for i, sl in enumerate((0, 6, 16, 24)):
                    idx = int(rng.integers(len(scale), 2 * len(scale) + 3))
                    self.lead.append((self.t(bar0 + b, sl), (6 if i < 3 else 8) * self.s16 * 0.95, self.lead_base + degs[idx], 1.0, {'slide': True}))
            b += 2
        # ending: a long high root with a slide, then the fifth
        self.lead.append((self.t(bar0 + b, 0), 6 * self.beat, self.lead_base + 24, 1.0, {'slide': True}))
        self.lead.append((self.t(bar0 + b + 1, 8), 1.5 * self.beat + (bars - b - 2) * self.bar, self.lead_base + 19, 0.9, {'slide': True}))

    def pad_chords(self, bar0, bars, prog, vel=0.8, octave=2, per=1):
        for b in range(0, bars, per):
            off = prog[(b // per) % len(prog)] if prog else 0
            q = self.root + 12 * octave + off
            tri = [q + i for i in self.chord_quality(off)]
            self.pad.append((self.t(bar0 + b), per * self.bar * 0.98, tri, vel, {}))

    # ------------------------------------------------------------------ drums
    def drum_bars(self, bar0, bars, pattern, fills=True, crash_first=True, crash_every=8, hat_vel=0.7, cym='crash'):
        rng = self.rng
        pat = PATTERNS[pattern]
        for b in range(bars):
            last = (b == bars - 1)
            small = fills and (b + 1) % 4 == 0 and not (b + 1) % 8 == 0
            big = fills and ((b + 1) % 8 == 0 or (last and bars >= 4))
            fill_from = 12 if small else (8 if big else 16)
            for name, slots in pat.items():
                for sl in slots:
                    if sl >= fill_from and name in ('snare', 'clap', 'kick', 'hat', 'ohat', 'ride') and name != 'kick':
                        continue
                    if name in ('hat', 'ride'):
                        v = hat_vel if sl % 4 == 0 else hat_vel * 0.65
                        if pattern in ('four16',) and sl % 2 == 1:
                            v *= 0.6
                    elif name == 'ohat':
                        v = 0.6
                    elif name == 'china':
                        v = 0.9
                    else:
                        v = 1.0 if name != 'kick' else 0.95
                        if name == 'kick' and sl % 2 == 1:
                            v = 0.8
                    self.drums.append((self.t(bar0 + b, sl), name, v))
            if (crash_first and b == 0) or (crash_every and b % crash_every == 0 and b > 0):
                self.drums.append((self.t(bar0 + b, 0), cym, 1.0))
            if small:
                choice = rng.integers(3)
                if choice == 0:
                    for sl in (12, 13, 14, 15):
                        self.drums.append((self.t(bar0 + b, sl), 'snare', 0.8 + 0.2 * (sl == 12)))
                elif choice == 1:
                    for sl, nm in ((12, 'snare'), (13, 'snare'), (14, 'tom_h'), (15, 'tom_m')):
                        self.drums.append((self.t(bar0 + b, sl), nm, 0.9))
                else:
                    for sl, nm in ((12, 'snare'), (14, 'tom_m'), (15, 'tom_l')):
                        self.drums.append((self.t(bar0 + b, sl), nm, 0.95))
                    self.drums.append((self.t(bar0 + b, 12), 'kick', 1.0))
            elif big:
                choice = rng.integers(3)
                if choice == 0:
                    seq = ['snare', 'snare', 'tom_h', 'tom_h', 'tom_m', 'tom_m', 'tom_l', 'tom_l']
                elif choice == 1:
                    seq = ['snare', 'tom_h', 'snare', 'tom_m', 'snare', 'tom_l', 'tom_l', 'tom_l']
                else:
                    seq = ['snare', 'snare', 'snare', 'tom_h', 'tom_m', 'tom_l', 'snare', 'snare']
                for k, nm in enumerate(seq):
                    self.drums.append((self.t(bar0 + b, 8 + k), nm, 0.85 + 0.15 * (k % 2 == 0)))
                for sl in (8, 10, 12, 14):
                    self.drums.append((self.t(bar0 + b, sl), 'kick', 0.9))

    def snare_build(self, bar0, bars):
        """Rising snare roll: 8ths, then 16ths, with a riser; ends with a crash on the next section."""
        for b in range(bars):
            step = 2 if b < bars - 1 else 1
            for sl in range(0, 16, step):
                self.drums.append((self.t(bar0 + b, sl), 'snare', 0.5 + 0.5 * (b * 16 + sl) / (bars * 16)))
                self.drums.append((self.t(bar0 + b, sl), 'kick', 0.9))
        self.drums.append((self.t(bar0 + bars) - 3.2, 'riser', 0.8))

    # ------------------------------------------------------------------ sections
    def compose(self):
        bar = 0
        chorus_no = 0
        for name, bars in self.plan:
            self.sections.append((name, self.t(bar), self.t(bar + bars)))
            getattr(self, 'sec_' + name)(bar, bars, chorus_no if name == 'chorus' else 0)
            if name == 'chorus':
                chorus_no += 1
            bar += bars
        self.length = self.t(bar) + 2.5

    def sec_intro(self, bar, bars, _):
        half = bars // 2
        st = self.style
        if st == 'industrial':
            self.bass_pulse(bar, bars, vel=0.9)
            self.drum_bars(bar, half, 'pulse', fills=False, crash_first=False, crash_every=0)
            self.drum_bars(bar + half, half, 'four', fills=True, crash_first=True, crash_every=0)
            self.play_riff(self.riff_a, bar + half, half, bass=False, vel=0.9)
            self.pad_chords(bar, bars, [0], vel=0.6, octave=1)
        elif st == 'thrash':
            self.play_riff(self.riff_a, bar, half, guitars=('L',), bass=False)
            self.play_riff(self.riff_a, bar + half, half, alt=self.riff_a2)
            self.drum_bars(bar + half, half, 'thrash', fills=True, crash_first=True, crash_every=0)
            for b in range(half):                                    # hat count-in
                for sl in (0, 4, 8, 12):
                    self.drums.append((self.t(bar + b, sl), 'hat', 0.6))
        elif st == 'doom':
            self.pad_chords(bar, bars, self.spec['prog2'], vel=0.8, per=2)
            self.chord_hits(bar, half, self.spec['prog2'][:1] * 2, slots=(0,), sustain=16, vel=0.9)
            self.chord_hits(bar + 2, 2, self.spec['prog2'][1:2], slots=(0, 8), sustain=8, vel=0.9)
            self.drum_bars(bar, half, 'quarter', fills=False, crash_first=True, crash_every=0, cym='china')
            self.play_riff(self.riff_a, bar + half, half, alt=self.riff_a2)
            self.drum_bars(bar + half, half, 'drive', fills=True, crash_first=True, crash_every=0)
        else:  # heroic: motif over strings, then the band enters
            self.pad_chords(bar, bars, self.spec['prog'], vel=0.9)
            self.play_phrase(self.intro_motif, bar, vel=0.9)
            self.play_phrase(self.intro_motif, bar + 4, vel=1.0, octave=0)
            self.chord_hits(bar, half, self.spec['prog'], slots=(0,), sustain=16, vel=0.85, bass=True)
            self.play_riff(self.riff_c, bar + half, half, prog=self.spec['prog'])
            self.drum_bars(bar + half, half, 'gallop', fills=True, crash_first=True, crash_every=0)
        self.drums.append((self.t(bar + bars) - 3.2, 'riser', 0.6))

    def sec_verse(self, bar, bars, _):
        st = self.style
        self.play_riff(self.riff_a, bar, bars, alt=self.riff_a2)
        if st == 'industrial':
            self.bass_pulse(bar, bars)
            self.drum_bars(bar, bars // 2, 'four', hat_vel=0.6)
            self.drum_bars(bar + bars // 2, bars - bars // 2, 'four16', hat_vel=0.6, crash_first=False)
            self.pad_chords(bar, bars, [0], vel=0.5, octave=1)
        elif st == 'thrash':
            self.drum_bars(bar, bars, 'thrash', hat_vel=0.75)
        elif st == 'doom':
            self.drum_bars(bar, bars, 'drive2', hat_vel=0.7)
        else:
            self.drum_bars(bar, bars, 'gallop' if bars > 8 else 'drive2', hat_vel=0.7)
        if bars >= 16:      # a lead answer-lick in the second half of long verses
            self.play_phrase(self.intro_motif, bar + 12, vel=0.8)

    def sec_pre(self, bar, bars, _):
        prog = self.spec['prog2']
        self.play_riff(self.riff_b, bar, bars - 2, prog=prog)
        self.chord_hits(bar + bars - 2, 2, [prog[-1], prog[-1] + 1], slots=(0, 4, 8, 12), sustain=3, vel=1.0)
        if self.style == 'industrial':
            self.bass_pulse(bar, bars, prog=prog)
            self.drum_bars(bar, bars - 2, 'four16', hat_vel=0.65, crash_every=0)
        elif self.style == 'thrash':
            self.drum_bars(bar, bars - 2, 'skank', hat_vel=0.75, crash_every=0)
        else:
            self.drum_bars(bar, bars - 2, 'double', hat_vel=0.7, crash_every=0)
        self.snare_build(bar + bars - 2, 2)
        self.pad_chords(bar, bars, prog, vel=0.6)

    def sec_chorus(self, bar, bars, chorus_no):
        prog = self.spec['prog']
        self.play_riff(self.riff_c, bar, bars, prog=prog, vel=1.0)
        if self.style == 'industrial':
            self.bass_pulse(bar, bars, prog=prog)
            self.drum_bars(bar, bars, 'four16', hat_vel=0.7, crash_every=4)
        elif self.style == 'thrash':
            self.drum_bars(bar, bars, 'ride' if chorus_no < 2 else 'ridegallop', hat_vel=0.75, crash_every=4)
        elif self.style == 'doom':
            self.drum_bars(bar, bars, 'ride', hat_vel=0.7, crash_every=4)
        else:
            self.drum_bars(bar, bars, 'ridegallop', hat_vel=0.7, crash_every=4)
        for b in range(0, bars, 4):
            ph = self.hook_b if (b // 4) % 4 == 2 else self.hook
            self.play_phrase(ph, bar + b, vel=1.0)
            if chorus_no >= 2 and (b // 4) % 2 == 1:                 # final chorus: octave doubling
                self.play_phrase(ph, bar + b, vel=0.6, octave=1)
        self.pad_chords(bar, bars, prog, vel=0.8)

    def sec_breakdown(self, bar, bars, _):
        prog = self.spec['prog2']
        half = bars // 2
        self.drums.append((self.t(bar), 'crash', 1.0))
        if self.style == 'doom':
            # half-time doom: slow open chords, tritone riff in 8ths, china on the quarters
            self.chord_hits(bar, half, prog, slots=(0, 6), sustain=6, vel=1.0)
            doom = self.make_riff('8th', [0, 6, 5, 6, 1, 0], accents=4, chord_prob=0.9)
            self.play_riff(doom, bar + half, bars - half, prog=[0, 0, 6, 5], vel=1.0)
            self.drum_bars(bar, half, 'half', hat_vel=0.8, cym='china', crash_every=4)
            self.drum_bars(bar + half, bars - half, 'halfdbl', cym='china', crash_every=4)
            self.pad_chords(bar, bars, prog, vel=1.0, per=1)
            self.play_phrase(self.hook, bar + half, vel=0.8, legato=1.0)
        elif self.style == 'industrial':
            self.bass_pulse(bar, bars, prog=prog, rate=2)
            self.chord_hits(bar, bars, prog, slots=(0, 10), sustain=4, vel=0.95, bass=False)
            self.drum_bars(bar, bars, 'half', hat_vel=0.6, crash_every=4)
            self.pad_chords(bar, bars, prog, vel=0.9, octave=1)
        elif self.style == 'thrash':
            self.chord_hits(bar, half, prog, slots=(0, 6, 12), sustain=4, vel=1.0)
            self.play_riff(self.riff_a, bar + half, bars - half, prog=[0, 0, 1, 1], vel=1.0)
            self.drum_bars(bar, half, 'half', hat_vel=0.8, cym='china', crash_every=4)
            self.drum_bars(bar + half, bars - half, 'halfdbl', cym='china', crash_every=4)
            self.pad_chords(bar, bars, prog, vel=0.8)
        else:
            self.chord_hits(bar, bars, prog, slots=(0, 8), sustain=8, vel=0.95)
            self.drum_bars(bar, bars, 'half', hat_vel=0.7, crash_every=4)
            self.pad_chords(bar, bars, prog, vel=1.0)
            self.play_phrase(self.hook, bar, vel=0.9, legato=1.0)
            self.play_phrase(self.hook_b, bar + 4, vel=0.9, legato=1.0)
        self.drums.append((self.t(bar + bars) - 3.2, 'riser', 0.7))

    def sec_solo(self, bar, bars, _):
        prog = self.spec['prog2'] if self.style != 'heroic' else self.spec['prog']
        self.play_riff(self.riff_a, bar, bars, prog=prog, alt=self.riff_a2, vel=0.95)
        if self.style == 'industrial':
            self.bass_pulse(bar, bars, prog=prog)
            self.drum_bars(bar, bars, 'four16', hat_vel=0.65)
        elif self.style == 'thrash':
            self.drum_bars(bar, bars, 'thrash', hat_vel=0.75)
        else:
            self.drum_bars(bar, bars, 'drive2', hat_vel=0.7)
        self.solo(bar, bars)
        self.pad_chords(bar, bars, prog, vel=0.5)

    def sec_outro(self, bar, bars, _):
        q = self.gtr_pitch(0, 0)
        for b, sl, ln in ((0, 0, 8), (0, 10, 6), (1, 0, 4), (1, 4, 4), (1, 8, 4), (1, 12, 4)):
            ev = (self.t(bar + b, sl), ln * self.s16 * 0.95, [q, q + 7, q + 12], 1.0, {})
            self.gL.append(ev); self.gR.append(ev)
            self.bass.append((self.t(bar + b, sl), ln * self.s16 * 0.95, q - 12, 1.0, {}))
            self.drums.append((self.t(bar + b, sl), 'kick', 1.0))
            self.drums.append((self.t(bar + b, sl), 'crash' if sl == 0 else 'snare', 1.0))
        for k, sl in enumerate((0, 2, 4, 6, 8, 10, 12, 14)):      # last bar before the final hit: tom roll
            nm = ['snare', 'tom_h', 'tom_m', 'tom_l'][k % 4]
            self.drums.append((self.t(bar + 2, sl), nm, 0.9))
            self.drums.append((self.t(bar + 2, sl), 'kick', 0.9))
        final = (self.t(bar + 3), 2.2, [q, q + 7, q + 12], 1.0, {})
        self.gL.append(final); self.gR.append(final)
        self.bass.append((self.t(bar + 3), 2.2, q - 12, 1.0, {}))
        self.drums.append((self.t(bar + 3), 'kick', 1.0)); self.drums.append((self.t(bar + 3), 'crash', 1.0))
        self.drums.append((self.t(bar + 3), 'china', 0.8))
        self.pad.append((self.t(bar + 3), 2.0, [q + 24, q + 24 + self.chord_quality(0)[1], q + 31], 0.9, {}))

    # ------------------------------------------------------------------ render
    def render(self):
        n = S.sec(self.length)
        st = self.style
        seed = self.spec['seed']
        gpar = {'industrial': dict(drive=8.0, tone=0.35, cab_hz=5500), 'thrash': dict(drive=10.0, tone=0.6, cab_hz=6500),
                'doom': dict(drive=9.0, tone=0.3, cab_hz=5200), 'heroic': dict(drive=8.5, tone=0.7, cab_hz=7000)}[st]
        gl = S.Guitar(seed=seed + 1, **gpar).render(self.gL, n)
        gr = S.Guitar(seed=seed + 2, **gpar).render(self.gR, n)
        bs = S.Bass(seed=seed + 3, electronic=(st == 'industrial'), drive=3.0 if st != 'heroic' else 2.0).render(self.bass, n)
        ld = S.Lead(seed=seed + 4, delay=self.beat * 0.75, square=0.5 if st == 'industrial' else 0.0,
                    detune=12.0 if st == 'heroic' else 9.0).render(self.lead, n) if self.lead else None
        pmode = {'industrial': 'organ', 'thrash': 'choir', 'doom': 'choir', 'heroic': 'strings'}[st]
        pd = S.Pad(seed=seed + 5, mode=pmode).render(self.pad, n) if self.pad else None
        dk = S.Drums(seed=seed + 6, style='electronic' if st == 'industrial' else 'rock').render(self.drums, n)
        mix = self.spec.get('mix', {})
        m = S.Mixer(n, S.reverb_ir(seed + 7, length=1.4 if st != 'doom' else 2.2))
        kicks = [t for t, nm, v in self.drums if nm == 'kick']
        m.pump = S.pump_curve(kicks, n, 0.35 if st == 'industrial' else 0.2, 0.14)
        m.add(gl, mix.get('gtr', -4.0), -0.7, send_db=-22)
        m.add(gr, mix.get('gtr', -4.0), 0.7, send_db=-22)
        m.add(bs, mix.get('bass', -6.0), 0.0, pump=0.6 if st == 'industrial' else 0.3)
        if ld is not None:
            m.add(ld, mix.get('lead', -7.0), 0.0, send_db=-10)
        if pd is not None:
            m.add(pd, mix.get('pad', -12.0), 0.0, send_db=-6, pump=0.7)
        m.add(dk['kick'], mix.get('kick', -2.0), 0.0)
        m.add(dk['snare'], mix.get('snare', -3.0), 0.0, send_db=-13)
        m.add(dk['hat'], mix.get('hat', -8.0), 0.3)
        m.add(dk['cym'], mix.get('cym', -5.0), -0.25, send_db=-12)
        m.add(dk['tom'], mix.get('tom', -5.0), 0.0, send_db=-12)
        return m.master(comp_thr=-13.0, ratio=3.0, drive_db=6.5, peak_dbfs=-1.0)


def loudnorm_mp3(wav, mp3):
    err = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', wav, '-af', 'loudnorm=%s:print_format=json' % TARGET,
                          '-f', 'null', '-'], capture_output=True, text=True).stderr
    m = json.loads(err[err.rindex('{'):err.rindex('}') + 1])
    af = ('loudnorm=%s:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true'
          % (TARGET, m['input_i'], m['input_tp'], m['input_lra'], m['input_thresh'], m['target_offset']))
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', wav, '-af', af, '-ar', '44100',
                    '-c:a', 'libmp3lame', '-b:a', '128k', mp3], check=True)
    return m


def seconds(path):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path]))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    short = '--short' in sys.argv
    os.makedirs(OUT, exist_ok=True); os.makedirs(SCRATCH, exist_ok=True)
    tracks = []
    for spec in TRACKS:
        if args and spec['id'] not in args:
            continue
        t0 = time.time()
        song = Song(spec, short=short)
        song.compose()
        audio = song.render()
        wav = os.path.join(SCRATCH, spec['id'] + '.wav')
        S.write_wav(wav, audio)
        print('%s: %s, %s %d bpm, %.1f s, composed+rendered in %.1f s' % (spec['id'], spec['title'], spec['key'], spec['bpm'],
                                                                           song.length, time.time() - t0))
        print('  sections: ' + ', '.join('%s %.0f-%.0f' % s for s in song.sections))
        json.dump({'sections': song.sections}, open(os.path.join(SCRATCH, spec['id'] + '.sections.json'), 'w'))
        if '--wav-only' in sys.argv:
            continue
        mp3 = os.path.join(OUT, spec['id'] + '.mp3')
        m = loudnorm_mp3(wav, mp3)
        print('  loudnorm: measured %s LUFS, TP %s, LRA %s -> %s' % (m['input_i'], m['input_tp'], m['input_lra'], os.path.relpath(mp3, ROOT)))
        # 20 s preview from the second chorus (first if there is only one)
        ch = [s for s in song.sections if s[0] == 'chorus']
        start = ch[min(1, len(ch) - 1)][1] if ch else 0.0
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-ss', '%.3f' % start, '-t', '20', '-i', mp3,
                        '-af', 'afade=t=in:d=0.05,afade=t=out:st=19:d=1', '-c:a', 'libmp3lame', '-b:a', '128k',
                        os.path.join(OUT, 'preview_%s.mp3' % spec['id'])], check=True)
        tracks.append({'id': spec['id'], 'file': spec['id'] + '.mp3', 'pool': 'long', 'title': spec['title'],
                       'by': 'Generated for Hellmatch with tools/compose.py (original, CC0)', 'seconds': round(seconds(mp3), 1)})
    if tracks and not short:
        # merge into music/tracks.json: keep entries that are not ours (e.g. the trailer theme), replace ours
        tj = os.path.join(OUT, 'tracks.json')
        old = json.load(open(tj)) if os.path.exists(tj) else []
        mine = {t['id']: t for t in tracks}
        merged = [mine.pop(t['id'], t) for t in old] + list(mine.values())
        json.dump(merged, open(tj, 'w'), indent=1)
        print('wrote music/tracks.json (%d entries)' % len(merged))


if __name__ == '__main__':
    main()
