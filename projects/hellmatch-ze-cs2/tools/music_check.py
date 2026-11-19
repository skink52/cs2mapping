"""Numeric fault check for a rendered music track (Phase 2/4 row 2.4: an OPL render with obvious faults leaves the playlist).

usage: music_check.py <track id | file.wav> [...]      renders a Freedoom track id with tools/oplmidi.py, or reads a 16-bit WAV
       import music_check; music_check.check(st, sr)    st: float array (n, 2) in -1..1 -> dict with 'ok' and 'faults'

Faults (any one drops the track):
  - clipping: more than 0.5 % of the samples at or above 98 % of the peak ceiling (the render's soft limiter at -1.5 dBFS,
    or full scale): the limiter is flattening the track, i.e. it distorts
  - DC: a channel's mean above 0.02 (2 % of full scale)
  - silence: overall RMS below -40 dBFS, more than 20 % of the 100 ms blocks below -60 dBFS, or a silent run longer than
    6 s anywhere but the last 3 s (a stuck or empty channel, a broken MIDI)
  - too short: under 20 s (a level playlist entry that ends before the first hold does)
Numbers go to build/music/<id>.check.json beside the cached MP3, so a cached track keeps its verdict.
"""
import json, math, os, sys, wave
import numpy as np

CEIL = 10 ** (-1.5 / 20)     # tools/oplmidi.py's soft limiter


def db(x): return 20 * math.log10(max(float(x), 1e-12))


def check(st, sr):
    st = np.asarray(st, np.float64)
    if st.ndim == 1: st = st[:, None]
    n = len(st); secs = n / float(sr)
    peak = float(np.abs(st).max()) if n else 0.0
    ceil = CEIL if peak <= CEIL + 1e-3 else 1.0
    clip = float((np.abs(st) >= 0.98 * ceil).mean()) if n else 0.0
    dc = [float(st[:, c].mean()) for c in range(st.shape[1])] if n else [0.0]
    rms = float(np.sqrt((st ** 2).mean())) if n else 0.0
    blk = max(1, sr // 10)
    nb = n // blk
    brms = np.sqrt((st[:nb * blk].reshape(nb, blk, -1) ** 2).mean((1, 2))) if nb else np.zeros(0)
    quiet = brms < 10 ** (-60 / 20)
    tail = int(3 * 10)
    run = best = 0
    for q in quiet[:max(0, nb - tail)]:
        run = run + 1 if q else 0; best = max(best, run)
    out = {'seconds': round(secs, 1), 'peak_dbfs': round(db(peak), 2), 'clip_fraction': round(clip, 5),
           'dc': [round(x, 5) for x in dc], 'rms_dbfs': round(db(rms), 2),
           'silent_fraction': round(float(quiet.mean()) if nb else 1.0, 4), 'longest_silence_s': round(best / 10.0, 1)}
    f = []
    if clip > 0.005: f.append('clipping: %.2f %% of samples at the ceiling' % (clip * 100))
    if max(abs(x) for x in dc) > 0.02: f.append('DC offset %s' % out['dc'])
    if out['rms_dbfs'] < -40: f.append('near silent: RMS %.1f dBFS' % out['rms_dbfs'])
    if out['silent_fraction'] > 0.2: f.append('%.0f %% silent' % (out['silent_fraction'] * 100))
    if out['longest_silence_s'] > 6: f.append('silent for %.1f s' % out['longest_silence_s'])
    if secs < 20: f.append('only %.1f s long' % secs)
    out['faults'] = f; out['ok'] = not f
    return out


def read_wav(path):
    with wave.open(path, 'rb') as w:
        ch, sw, sr = w.getnchannels(), w.getsampwidth(), w.getframerate()
        if sw != 2: raise SystemExit('music_check: %s: only 16-bit WAV' % path)
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64) / 32768.0
    return a.reshape(-1, ch), sr


if __name__ == '__main__':
    if len(sys.argv) < 2: raise SystemExit(__doc__)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    bad = 0
    for a in sys.argv[1:]:
        if a.lower().endswith('.wav'):
            st, sr = read_wav(a)
        else:
            import assets, oplmidi
            st, sr = oplmidi.render(os.path.join(assets.FD, 'musics/d_%s.mid' % a.lower())), oplmidi.OUT_SR
        r = check(st, sr)
        bad += not r['ok']
        print('%s: %s %s' % (a, 'ok' if r['ok'] else 'FAULT ' + '; '.join(r['faults']), json.dumps({k: v for k, v in r.items() if k not in ('faults', 'ok')})))
    sys.exit(1 if bad else 0)
