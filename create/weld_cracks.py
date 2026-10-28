"""Close the cracks in a converted soldier body DMX.
Seen on tw_de_a (Wehrmacht soldier with weights copied from a donor rig): its GLB has split vertices along every seam, the copied
weights differ slightly between the copies, so the T-pose -> A-pose re-pose pulled them apart (median 0.02 u, up to ~0.4 u): ~2,600 open
loops, see-through specks scattered over the model in game. Only boundary vertices (on an edge used by one triangle) are merged:
union-find over pairs closer than TOL that aren't in the same triangle, each group snapped to its mean position with averaged
(top-4, renormalised) weights. Interior vertices never move, so layered surfaces (collar over neck) aren't fused.
usage: python3 tools/weld_cracks.py <body dmx> <out dmx> [tol=0.45]"""
import sys
from collections import Counter
import numpy as np
from scipy.spatial import cKDTree
import dmx9


def tris(me):
    vd = me['currentState']; pi = np.array(vd['position$0Indices']); out = []
    for fs in me['faceSets']:
        cur = []
        for i in fs['faces']:
            if i < 0: out += [(pi[cur[0]], pi[cur[k]], pi[cur[k + 1]]) for k in range(1, len(cur) - 1)]; cur = []
            else: cur.append(i)
    return np.array(out)


def boundary(T):
    E = Counter()
    for t in T:
        for i, j in ((0, 1), (1, 2), (2, 0)): E[(min(t[i], t[j]), max(t[i], t[j]))] += 1
    return np.array([e for e, c in E.items() if c == 1])


def main(src, out, tol=0.45):
    tol = float(tol)
    dm = dmx9.DMX.load(src)
    for me in [e for e in dm.elements if e.type == 'DmeMesh']:
        vd = me['currentState']; jc = vd['jointCount']
        Praw = np.array(vd['position$0']); Traw = tris(me)
        # exact copies (UV / normal seams) are one vertex here
        _, first, canon = np.unique(np.round(Praw, 4), axis=0, return_index=True, return_inverse=True); canon = canon.ravel()
        P = Praw[first]; T = canon[Traw]
        Wr = np.array(vd['blendweights$0'], float).reshape(-1, jc); Ir = np.array(vd['blendindices$0']).reshape(-1, jc)
        W, I = Wr[first], Ir[first]
        b0 = boundary(T)
        bv = np.unique(b0.ravel())
        same = set()
        for t in T:
            for i, j in ((0, 1), (1, 2), (2, 0)): same.add((min(t[i], t[j]), max(t[i], t[j])))
        parent = np.arange(len(P))
        def find(x):
            while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
            return x
        lo = {v: P[v].copy() for v in bv}; hi = {v: P[v].copy() for v in bv}     # group bounding boxes (by root)
        pairs = np.array(sorted(cKDTree(P[bv]).query_pairs(tol), key=lambda q: np.linalg.norm(P[bv[q[0]]] - P[bv[q[1]]])))
        for a, b in pairs:                                     # closest first; a merge may not grow a group beyond tol across
            a, b = bv[a], bv[b]
            if (min(a, b), max(a, b)) in same: continue
            ra, rb = find(a), find(b)
            if ra == rb: continue
            l = np.minimum(lo[ra], lo[rb]); h = np.maximum(hi[ra], hi[rb])
            if np.linalg.norm(h - l) > tol: continue
            parent[rb] = ra; lo[ra], hi[ra] = l, h
        roots = np.array([find(x) for x in range(len(P))])
        groups = {}
        for v in bv: groups.setdefault(roots[v], []).append(v)
        nb = I.max() + 1
        P2 = P.copy(); W2, I2 = W.copy(), I.copy(); merged = 0; moved = []
        for g in groups.values():
            if len(g) < 2: continue
            merged += len(g)
            m = P[g].mean(0); moved += list(np.linalg.norm(P[g] - m, axis=1)); P2[g] = m
            dense = np.zeros(nb)
            for v in g: np.add.at(dense, I[v], W[v])
            top = np.argsort(-dense)[:jc]; w = dense[top]; w = w / w.sum()
            for v in g: I2[v] = top; W2[v] = w
        vd['position$0'] = [tuple(map(float, p)) for p in P2[canon]]
        vd['blendweights$0'] = [float(x) for x in W2[canon].ravel()]; vd['blendindices$0'] = [int(x) for x in I2[canon].ravel()]
        if me.get('bindState') is not None and 'position$0' in me['bindState'].attrs: me['bindState']['position$0'] = vd['position$0']
        # report: how many boundary edges remain once coincident positions are counted as one
        _, inv = np.unique(np.round(P2, 4), axis=0, return_inverse=True); inv = inv.ravel()
        Tw = inv[T]; Tw = Tw[(Tw[:, 0] != Tw[:, 1]) & (Tw[:, 1] != Tw[:, 2]) & (Tw[:, 0] != Tw[:, 2])]
        print('%s: %d boundary edges -> %d, %d vertices merged (moved mean %.3f, max %.3f u)'
              % (me.name, len(b0), len(boundary(Tw)), merged, np.mean(moved) if moved else 0, max(moved) if moved else 0))
    dm.save(out)


if __name__ == '__main__':
    main(*sys.argv[1:4])
