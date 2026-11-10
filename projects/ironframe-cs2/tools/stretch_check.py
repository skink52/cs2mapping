"""Stretch metric: for every clip sample, edges whose posed length differs a lot from the bind length (mesh stretched between bones).
usage: python -I tools/stretch_check.py [key,..] [--lod 0] [--ratio 1.5] [--min 6]
An edge counts when posed/bind > ratio (bind length > min units) ; prints per frame/group the worst count, the bone pairs involved and the clip."""
import json, os, sys, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import review_frames as RF, review_anim as RA

GROUP = None

def check(key, entry, lod, ratio, minlen, clipsel=None):
    parts, clips = RA.load_parts(key, entry, lod)
    res = {}
    for g, m in parts.items():
        V0 = RF.posed(m, None); n = len(V0) // 3
        T = V0.reshape(n, 3, 3)
        e = [(0, 1), (1, 2), (2, 0)]
        A = np.concatenate([np.arange(n) * 3 + a for a, b in e]); B = np.concatenate([np.arange(n) * 3 + b for a, b in e])
        L0 = np.linalg.norm(V0[A] - V0[B], axis=1)
        ok = L0 > minlen
        dom = m['BI'][np.arange(len(V0)), m['BW'].argmax(1)]
        names = [x[0] for x in m['nodes']]
        for (gg, c), frs in clips.items():
            if gg != g or (clipsel and c not in clipsel) or (GROUP and g != GROUP): continue
            ks = sorted(frs)[::max(1, len(frs) // 12)]
            worst = (0, None)
            for k in ks:
                P = RF.posed(m, frs[k]); L = np.linalg.norm(P[A] - P[B], axis=1)
                r = np.where(ok, L / np.maximum(L0, 1e-6), 1.0)
                cnt = int((r > ratio).sum())
                if cnt >= worst[0]: worst = (cnt, k, r, )
            cnt, k, r = worst
            idx = np.where(r > ratio)[0]
            pairs = collections.Counter(tuple(sorted((names[dom[A[i]]], names[dom[B[i]]]))) for i in idx)
            res[(g, c)] = (cnt, float(r.max()), pairs.most_common(3), n * 3)
    return res

if __name__ == '__main__':
    a = sys.argv[1:]; opt = lambda n, d: a[a.index(n) + 1] if n in a else d
    GROUP = opt('--group', None) or None
    keys = [x for x in a if not x.startswith('--') and x not in (opt('--lod', ''), opt('--ratio', ''), opt('--min', ''), opt('--clips', ''), opt('--group', ''))]
    fr = json.load(open(os.path.join(RF.OUT, '_gen', 'models.json'), encoding='utf-8'))['frames']
    keys = keys[0].split(',') if keys else list(fr)
    clipsel = opt('--clips', '').split(',') if '--clips' in a else None
    for k in keys:
        r = check(k, fr[k], int(opt('--lod', 0)), float(opt('--ratio', 1.5)), float(opt('--min', 6)), clipsel)
        tot = sum(v[0] for v in r.values())
        print('%-16s stretched edges (worst frame per clip): %d' % (k, tot))
        for (g, c), (cnt, mx, pairs, ne) in sorted(r.items(), key=lambda kv: -kv[1][0])[:6]:
            if cnt: print('    %-6s %-12s %5d edges (max x%.1f) %s' % (g, c, cnt, mx, pairs))
