"""music_analysis.py: describe a music file by numbers: tempo, key, loudness, spectral balance, rhythmic density and structure.

usage: music_analysis.py <audio file> [--json]
Only numpy, scipy and ffmpeg/ffprobe are needed. Use it to describe a reference track you want generated music to
resemble, then check the generated tracks against it (tempo, key, LUFS / true peak / LRA via ffmpeg loudnorm, low /
mid / high balance, spectral centroid, onset density, section boundaries).

From hellmatch-cs2/tools/music_analysis.py (MIT), made project-neutral.
"""
import json, os, subprocess, sys, tempfile
import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 22050          # analysis rate: enough for key/tempo/balance, keeps the STFTs small
N_FFT, HOP = 2048, 512

KRUMHANSL_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KRUMHANSL_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def load(path):
    """Decode anything ffmpeg reads to a mono float array at SR, plus the full-rate stereo float array."""
    with tempfile.TemporaryDirectory() as td:
        mono = os.path.join(td, 'm.wav')
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', path, '-ac', '1', '-ar', str(SR),
                        '-c:a', 'pcm_f32le', mono], check=True)
        _, y = wavfile.read(mono)
    return y.astype(np.float32)


def loudness(path):
    """ffmpeg's EBU R128 measurement (same filter the build uses for normalisation)."""
    err = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-af',
                          'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    m = json.loads(err[err.rindex('{'):err.rindex('}') + 1])
    return {'lufs': float(m['input_i']), 'true_peak_dbtp': float(m['input_tp']), 'lra': float(m['input_lra'])}


def stft_mag(y):
    f, t, Z = signal.stft(y, fs=SR, nperseg=N_FFT, noverlap=N_FFT - HOP, window='hann', padded=False, boundary=None)
    return f, t, np.abs(Z)


def onset_envelope(mag):
    """Spectral flux on a log-compressed, roughly log-spaced band set (a poor man's mel onset strength)."""
    nb = 64
    edges = np.geomspace(40, SR / 2, nb + 1)
    f = np.linspace(0, SR / 2, mag.shape[0])
    bands = np.zeros((nb, mag.shape[1]), dtype=np.float32)
    for i in range(nb):
        sel = (f >= edges[i]) & (f < edges[i + 1])
        if sel.any():
            bands[i] = mag[sel].mean(axis=0)
    logb = np.log1p(1000 * bands)
    flux = np.maximum(0, np.diff(logb, axis=1)).sum(axis=0)
    flux = np.concatenate([[0], flux])
    # remove slow trend so autocorrelation sees the beat, not the song's envelope
    flux = flux - signal.medfilt(flux, 2 * int(SR / HOP) + 1)
    return np.maximum(flux, 0)


def tempo(onset):
    fps = SR / HOP
    x = onset - onset.mean()
    ac = signal.correlate(x, x, mode='full')[len(x) - 1:]
    ac /= ac[0] + 1e-9
    lags = np.arange(len(ac))
    bpm = 60 * fps / np.maximum(lags, 1)
    sel = (bpm >= 50) & (bpm <= 250)
    cand = ac.copy(); cand[~sel] = -1
    peaks, props = signal.find_peaks(cand, distance=3, prominence=0.01)
    if len(peaks) == 0:
        return {'bpm': None, 'candidates': []}
    order = np.argsort(-cand[peaks])[:8]
    out = []
    for p in peaks[order]:
        out.append({'bpm': round(float(bpm[p]), 1), 'strength': round(float(cand[p]), 3)})
    # a fast heavy track lives in 120-220; pick the strongest candidate there, else the strongest overall
    best = max(out, key=lambda c: c['strength'] * (1.0 if 110 <= c['bpm'] <= 230 else 0.6))
    related = []
    for c in out:
        r = c['bpm'] / best['bpm']
        for name, ratio in (('half', 0.5), ('double', 2.0), ('2/3', 2 / 3), ('3/2', 1.5)):
            if abs(r - ratio) < 0.04:
                related.append({'relation': name, **c})
    conf = best['strength'] / (sum(c['strength'] for c in out[:3]) + 1e-9)
    return {'bpm': best['bpm'], 'confidence': round(float(conf), 2), 'candidates': out[:5], 'related': related}


def key(mag, f):
    """Chroma from the STFT (log-weighted magnitude, 60 Hz-5 kHz) correlated with Krumhansl key profiles."""
    sel = (f >= 60) & (f <= 5000)
    midi = 69 + 12 * np.log2(f[sel] / 440.0)
    pc = np.round(midi).astype(int) % 12
    w = np.log1p(100 * mag[sel]).sum(axis=1)
    chroma = np.zeros(12)
    for i in range(12):
        chroma[i] = w[pc == i].sum()
    chroma /= chroma.sum() + 1e-9
    scores = []
    for tonic in range(12):
        for mode, prof in (('major', KRUMHANSL_MAJOR), ('minor', KRUMHANSL_MINOR)):
            r = np.corrcoef(np.roll(prof, tonic), chroma)[0, 1]
            scores.append((float(r), '%s %s' % (NOTES[tonic], mode)))
    scores.sort(reverse=True)
    return {'key': scores[0][1], 'r': round(scores[0][0], 3), 'runner_up': scores[1][1], 'runner_r': round(scores[1][0], 3),
            'chroma': {NOTES[i]: round(float(chroma[i]), 3) for i in range(12)}}


def balance(mag, f):
    p = (mag ** 2).mean(axis=1)
    tot = p.sum() + 1e-12
    low = p[f < 200].sum() / tot
    mid = p[(f >= 200) & (f < 2000)].sum() / tot
    high = p[f >= 2000].sum() / tot
    cent = float((f * p).sum() / tot)
    # rolloff: frequency below which 85 % of the energy sits
    cum = np.cumsum(p) / tot
    roll = float(f[np.searchsorted(cum, 0.85)])
    return {'low_pct': round(100 * low, 1), 'mid_pct': round(100 * mid, 1), 'high_pct': round(100 * high, 1),
            'centroid_hz': round(cent), 'rolloff85_hz': round(roll)}


def density(onset):
    fps = SR / HOP
    thr = onset.mean() + 0.8 * onset.std()
    peaks, _ = signal.find_peaks(onset, height=thr, distance=int(0.05 * fps))
    return {'onsets_per_sec': round(len(peaks) / (len(onset) / fps), 2), 'onsets': int(len(peaks))}


def structure(y, mag, f, t):
    """Energy over time (1 s RMS, dBFS) and section boundaries from a checkerboard novelty on band features."""
    sec = int(SR)
    n = len(y) // sec
    rms = [float(20 * np.log10(np.sqrt(np.mean(y[i * sec:(i + 1) * sec] ** 2)) + 1e-9)) for i in range(n)]
    silent = [i for i, r in enumerate(rms) if r < -45]
    # features: log energy in 24 log-spaced bands per 0.5 s
    edges = np.geomspace(40, SR / 2, 25)
    fr = int(0.5 * SR / HOP)
    nf = mag.shape[1] // fr
    feats = np.zeros((nf, 24))
    for j in range(nf):
        seg = mag[:, j * fr:(j + 1) * fr].mean(axis=1)
        for i in range(24):
            s = (f >= edges[i]) & (f < edges[i + 1])
            feats[j, i] = np.log1p(1000 * seg[s].mean()) if s.any() else 0
    feats -= feats.mean(axis=0)
    feats /= np.linalg.norm(feats, axis=1, keepdims=True) + 1e-9
    ssm = feats @ feats.T
    L = 16                                        # kernel half-size: 8 s
    k = np.outer(np.r_[-np.ones(L), np.ones(L)], np.r_[-np.ones(L), np.ones(L)])
    k *= signal.windows.gaussian(2 * L, L / 2)[:, None] * signal.windows.gaussian(2 * L, L / 2)[None, :]
    nov = np.zeros(nf)
    for i in range(L, nf - L):
        nov[i] = (ssm[i - L:i + L, i - L:i + L] * k).sum()
    nov = np.maximum(nov, 0)
    peaks, _ = signal.find_peaks(nov, distance=int(6 / 0.5), prominence=nov.max() * 0.15 if nov.max() > 0 else 1)
    bounds = [round(p * 0.5, 1) for p in peaks]
    return {'seconds': round(len(y) / SR, 1), 'rms_db_per_sec': [round(r, 1) for r in rms], 'silent_seconds': silent,
            'boundaries_s': bounds, 'rms_db_mean': round(float(np.mean(rms)), 1), 'rms_db_min': round(float(np.min(rms)), 1),
            'rms_db_max': round(float(np.max(rms)), 1)}


def analyse(path):
    y = load(path)
    f, t, mag = stft_mag(y)
    on = onset_envelope(mag)
    return {'file': os.path.basename(path), 'loudness': loudness(path), 'tempo': tempo(on), 'key': key(mag, f),
            'balance': balance(mag, f), 'density': density(on), 'structure': structure(y, mag, f, t)}


def summary(a):
    s, tp, k = a['structure'], a['tempo'], a['key']
    lines = ['%s: %.1f s' % (a['file'], s['seconds']),
             '  tempo %s bpm (confidence %s; candidates %s)' % (tp['bpm'], tp.get('confidence'),
                                                                ', '.join('%s@%s' % (c['bpm'], c['strength']) for c in tp['candidates'])),
             '  key %s (r=%s; runner-up %s r=%s)' % (k['key'], k['r'], k['runner_up'], k['runner_r']),
             '  loudness %.1f LUFS, true peak %.1f dBTP, LRA %.1f LU' % (a['loudness']['lufs'], a['loudness']['true_peak_dbtp'], a['loudness']['lra']),
             '  balance low/mid/high %s/%s/%s %%, centroid %s Hz, 85%% rolloff %s Hz' % (
                 a['balance']['low_pct'], a['balance']['mid_pct'], a['balance']['high_pct'], a['balance']['centroid_hz'], a['balance']['rolloff85_hz']),
             '  onsets %.2f /s; RMS mean %.1f dB (min %.1f, max %.1f); silent seconds %s; section boundaries at %s s' % (
                 a['density']['onsets_per_sec'], s['rms_db_mean'], s['rms_db_min'], s['rms_db_max'], s['silent_seconds'] or 'none', s['boundaries_s'])]
    return '\n'.join(lines)


def plain(o):
    """numpy scalars -> python scalars so the result serialises."""
    if isinstance(o, dict): return {k: plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [plain(v) for v in o]
    if isinstance(o, np.generic): return o.item()
    return o


if __name__ == '__main__':
    args = [x for x in sys.argv[1:] if not x.startswith('--')]
    for p in args:
        a = plain(analyse(p))
        print(json.dumps(a, indent=1) if '--json' in sys.argv else summary(a))
