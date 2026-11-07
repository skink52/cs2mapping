"""What an imported model is made of, to choose drop/fold settings: materials (triangles, centre height) and the skinned chains of
bones the converter doesn't map (chain root = first unmapped bone under a mapped one or the root; vertices, centre, size).

    python -I partlist.py <work>/fbx/<slug>/<slug>.npz [...]
"""
import sys, collections
import numpy as np


def main():
    for f in sys.argv[1:]:
        z = np.load(f); n = [str(x) for x in z['names']]; p = z['parents']; V = z['V']; W = z['W']; B = z['B']
        T = z['tris']; tm = z['tri_mat']
        print('==', f.replace('\\', '/').split('/')[-1][:-4])
        for k, m in enumerate(z['materials']):
            vs = np.unique(T[tm == k])
            if len(vs): print('   material %-28s %6d tris  z %5.1f..%5.1f' % (m, (tm == k).sum(), V[vs, 2].min(), V[vs, 2].max()))
        mapped = [x.startswith('ValveBiped.') for x in n]
        def chain_root(i):
            r = i
            while p[r] >= 0 and not mapped[p[r]]: r = p[r]
            return r
        groups = collections.defaultdict(list)
        for v in range(len(V)):
            j = B[v, int(np.argmax(W[v]))]
            if not mapped[j]: groups[chain_root(j)].append(v)
        for r, vs in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:12]:
            P = V[vs]; par = n[p[r]].replace('ValveBiped.Bip01_', '') if p[r] >= 0 else '-'
            print('   chain %-26s under %-12s %6d verts  centre %s  size %s' % (n[r], par, len(vs), P.mean(0).round(1), (P.max(0) - P.min(0)).round(1)))


if __name__ == '__main__':
    main()
