"""oplmidi.py: renders a Freedoom MIDI track with an approximate OPL2 FM synth driven by Freedoom's own GENMIDI
instrument patches (lumps/genmidi/config.py + instruments/*.sbi), the way DMX played Doom music. Pure numpy; for PCs
without libADLMIDI / ffmpeg (music.py prefers adlmidiplay + ffmpeg when they are there).

usage: oplmidi.py <in.mid> <out.mp3|out.wav> [--seconds N]

Model per voice: 2-operator FM (or additive) with the OPL multiplier table, the four OPL2 waveforms, total level,
attack/decay/sustain/release rates (OPL timing), sustaining/percussive envelopes, modulator feedback (two-pass
approximation), tremolo and vibrato bits. Double-voice instruments play both voices; percussion uses the GENMIDI
fixed notes. Loudness is matched to about -16 LUFS (RMS-based) with a soft limiter, then MP3 (lameenc) or WAV.
"""
import math, os, struct, sys, wave
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets

SR = 88200          # internal rate (2x, so FM sidebands alias less); output is OUT_SR
OUT_SR = 44100
MULT = [0.5, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 12, 12, 15, 15]
TWO_PI = 2 * math.pi


def load_genmidi():
    d = os.path.join(assets.FD, 'lumps', 'genmidi')
    cwd = os.getcwd(); sys.path.insert(0, d)
    try:
        os.chdir(d)
        g = {}
        exec(compile(open('config.py', encoding='utf-8').read(), 'config.py', 'exec'), g)
    finally:
        os.chdir(cwd); sys.path.remove(d)
    return g['INSTRUMENTS'], g['PERCUSSION']


# ------------------------------------------------------------------ MIDI
def read_midi(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'MThd'
    fmt, ntr, div = struct.unpack('>HHH', d[8:14])
    pos = 14; events = []
    for tr in range(ntr):
        assert d[pos:pos + 4] == b'MTrk'
        ln, = struct.unpack('>I', d[pos + 4:pos + 8]); p = pos + 8; end = p + ln; pos = end
        tick = 0; status = 0
        while p < end:
            v = 0
            while True:
                b = d[p]; p += 1; v = (v << 7) | (b & 0x7f)
                if not b & 0x80: break
            tick += v
            b = d[p]
            if b & 0x80: status = b; p += 1
            if status == 0xFF:
                typ = d[p]; p += 1; l = 0
                while True:
                    c = d[p]; p += 1; l = (l << 7) | (c & 0x7f)
                    if not c & 0x80: break
                if typ == 0x51: events.append((tick, 'tempo', int.from_bytes(d[p:p + 3], 'big')))
                p += l
            elif status in (0xF0, 0xF7):
                l = 0
                while True:
                    c = d[p]; p += 1; l = (l << 7) | (c & 0x7f)
                    if not c & 0x80: break
                p += l
            else:
                hi, ch = status & 0xF0, status & 0x0F
                n = 1 if hi in (0xC0, 0xD0) else 2
                a = d[p:p + n]; p += n
                events.append((tick, hi, ch) + tuple(a))
    events.sort(key=lambda e: (e[0], 0 if e[1] == 'tempo' else 1))
    # ticks -> seconds
    out = []; tempo = 500000; last_tick = 0; t = 0.0
    for e in events:
        t += (e[0] - last_tick) * tempo / 1e6 / div; last_tick = e[0]
        if e[1] == 'tempo': tempo = e[2]; continue
        out.append((t,) + e[1:])
    return out


def notes_of(events):
    """[(start, dur, ch, note, vel, program, chvol, pan, bend)]"""
    prog = [0] * 16; vol = [100] * 16; pan = [64] * 16; bend = [0.0] * 16; expr = [127] * 16
    on = {}; out = []
    for e in events:
        t, hi, ch = e[0], e[1], e[2]
        if hi == 0x90 and e[4] > 0:
            on.setdefault((ch, e[3]), []).append((t, e[4], prog[ch], vol[ch] * expr[ch] / 127, pan[ch], bend[ch]))
        elif hi == 0x80 or (hi == 0x90 and e[4] == 0):
            st = on.get((ch, e[3]))
            if st:
                s = st.pop(0); out.append((s[0], max(0.02, t - s[0]), ch, e[3], s[1], s[2], s[3], s[4], s[5]))
        elif hi == 0xC0: prog[ch] = e[3]
        elif hi == 0xB0:
            if e[3] == 7: vol[ch] = e[4]
            elif e[3] == 10: pan[ch] = e[4]
            elif e[3] == 11: expr[ch] = e[4]
        elif hi == 0xE0:
            bend[ch] = (((e[4] << 7) | e[3]) - 8192) / 8192 * 2
    return out


# ------------------------------------------------------------------ OPL voice
def wavefn(w, ph):
    s = np.sin(ph)
    if w == 1: return np.maximum(s, 0)
    if w == 2: return np.abs(s)
    if w == 3: return np.where((ph % TWO_PI) % math.pi < math.pi / 2, np.abs(s), 0)
    return s


def env(op, n_on, n_tot):
    """amplitude envelope (linear gain) for one operator"""
    ar, dr = op['ad'] >> 4, op['ad'] & 15
    sl, rr = op['sr'] >> 4, op['sr'] & 15
    sustain = bool(op['avek'] & 0x20)
    att_s = 0.0 if ar == 15 else (1e9 if ar == 0 else 2.826 / 2 ** (ar - 1))
    rate = lambda r: 0.0 if r == 0 else 96.0 / (39.28 / 2 ** (r - 1))   # dB per second
    sl_db = 93.0 if sl == 15 else sl * 3.0
    t = np.arange(n_tot) / SR
    db = np.zeros(n_tot)
    # attack: approx exponential rise
    if att_s > 0:
        a = np.clip(t / att_s, 0, 1)
        db = np.where(t < att_s, 96 * (1 - a) ** 3, 0)
    ta = t - att_s
    dec = rate(dr)
    after = ta > 0
    d_db = np.minimum(ta * dec, sl_db) if dec > 0 else np.zeros_like(ta)
    db = np.where(after, d_db, db)
    if not sustain:
        # percussive: once at SL keep falling at the release rate
        t_sl = att_s + (sl_db / dec if dec > 0 else 1e9)
        extra = np.clip(t - t_sl, 0, None) * rate(rr)
        db = np.where(t > t_sl, sl_db + extra, db)
    # note off
    t_off = n_on / SR
    db_off = db[min(n_on, n_tot - 1)]
    rel = rate(rr) if rr else 96.0 / 8
    db = np.where(t >= t_off, np.maximum(db, db_off + (t - t_off) * rel), db)
    return 10 ** (-np.clip(db, 0, 96) / 20)


def ops(v):
    m = dict(avek=v['m_am_vibrato_eg'], kv=v['m_ksl_volume'], ad=v['m_attack_decay'], sr=v['m_sustain_release'], w=v['m_waveform'] & 3)
    c = dict(avek=v['c_am_vibrato_eg'], kv=v['c_ksl_volume'], ad=v['c_attack_decay'], sr=v['c_sustain_release'], w=v['c_waveform'] & 3)
    return m, c, (v['feedback_fm'] >> 1) & 7, v['feedback_fm'] & 1


def render_voice(v, freq, dur, vel_gain):
    m, c, fb, additive = ops(v)
    rr = max(1, min(m['sr'] & 15, c['sr'] & 15))
    tail = min(2.5, 96.0 / (96.0 / (39.28 / 2 ** (rr - 1)))) if rr else 1.0
    n_on = int(dur * SR); n = n_on + int(tail * SR)
    if n <= 0: return None
    t = np.arange(n) / SR
    def phase(op, vib):
        f = freq * MULT[op['avek'] & 15]
        ph = TWO_PI * f * t
        if vib: ph = ph + (f * 0.004 / 6.1) * TWO_PI * np.sin(TWO_PI * 6.1 * t)
        return ph
    def level(op):
        ksl = [0, 3.0, 1.5, 6.0][op['kv'] >> 6] * max(0.0, math.log2(max(freq, 1) / 32.7) - 1)
        g = 10 ** (-((op['kv'] & 63) * 0.75 + ksl) / 20) * env(op, n_on, n)
        if op['avek'] & 0x80: g = g * (1 - 0.06 * (0.5 + 0.5 * np.sin(TWO_PI * 3.7 * t)))
        return g
    pm = phase(m, m['avek'] & 0x40); gm = level(m)
    beta = 0 if fb == 0 else 4 * math.pi / 2 ** (7 - fb)
    mo = wavefn(m['w'], pm)
    if beta:
        mo = wavefn(m['w'], pm + beta * mo)
        mo = wavefn(m['w'], pm + beta * mo)
    mo = mo * gm
    pc = phase(c, c['avek'] & 0x40); gc = level(c) * vel_gain
    if additive:
        out = mo * vel_gain + wavefn(c['w'], pc) * gc
    else:
        out = wavefn(c['w'], pc + 8 * math.pi * mo) * gc
    return out.astype(np.float32)


def render(mid, seconds=None):
    INS, PERC = load_genmidi()
    ev = read_midi(mid)
    ns = notes_of(ev)
    total = max(s + d for s, d, *_ in ns) + 3.0
    if seconds: total = min(total, seconds)
    L = np.zeros(int(total * SR) + SR * 3, np.float32); R = np.zeros_like(L)
    for (st, dur, ch, note, vel, prog, cvol, pan, bend) in ns:
        if st >= total: continue
        if ch == 9:
            k = note - 35
            if not 0 <= k < len(PERC): continue
            ins = PERC[k]; base = ins.fixed_note if ins.fixed_note is not None else note
        else:
            ins = INS[prog]; base = note + bend
        g = ((vel / 127.0) * (cvol / 127.0)) ** 1.3
        for vi, (voice, off) in enumerate(((ins.voice1, ins.offset1), (ins.voice2, ins.offset2))):
            if voice is None: continue
            f = 440.0 * 2 ** ((base + off - 69) / 12.0)
            y = render_voice(voice, f, dur, g * (0.7 if ins.voice2 is not None else 1.0))
            if y is None: continue
            i0 = int(st * SR); y = y[:len(L) - i0]
            p = (pan - 64) / 64.0 * 0.5
            L[i0:i0 + len(y)] += y * (1 - max(0, p)); R[i0:i0 + len(y)] += y * (1 + min(0, p))
    st = np.stack([L, R], 1).astype(np.float64)
    from scipy import signal
    st = signal.resample_poly(st, 1, SR // OUT_SR, axis=0)          # band-limited back to 44.1 kHz
    st = signal.sosfilt(signal.butter(2, 25, 'highpass', fs=OUT_SR, output='sos'), st, axis=0)    # DC (half/abs sine waves)
    st = signal.sosfilt(signal.butter(1, 11000, 'lowpass', fs=OUT_SR, output='sos'), st, axis=0)  # the sound card's output stage
    nz = np.nonzero(np.abs(st).max(1) > 1e-4)[0]
    st = st[:nz[-1] + OUT_SR // 2] if len(nz) else st
    # loudness: RMS of the loud half to about -16 LUFS-ish (-18 dBFS RMS), soft limit at -1.5 dBFS
    blk = st[:len(st) // 4096 * 4096].reshape(-1, 4096, 2)
    rms = np.sqrt((blk ** 2).mean((1, 2)))
    ref = np.sqrt((np.sort(rms)[len(rms) // 2:] ** 2).mean()) + 1e-9
    st = st * (10 ** (-18 / 20) / ref)
    lim = 10 ** (-1.5 / 20)
    st = np.tanh(st / lim) * lim
    return st


def save(st, path):
    pcm = (np.clip(st, -1, 1) * 32767).astype(np.int16)
    if path.endswith('.wav'):
        with wave.open(path, 'wb') as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(OUT_SR); w.writeframes(pcm.tobytes())
    else:
        import lameenc
        e = lameenc.Encoder(); e.set_bit_rate(128); e.set_in_sample_rate(OUT_SR); e.set_channels(2); e.set_quality(2)
        open(path, 'wb').write(e.encode(pcm.tobytes()) + e.flush())
    return len(st) / OUT_SR


if __name__ == '__main__':
    secs = float(sys.argv[sys.argv.index('--seconds') + 1]) if '--seconds' in sys.argv else None
    st = render(sys.argv[1], secs)
    print('%s: %.1f s' % (sys.argv[2], save(st, sys.argv[2])))
