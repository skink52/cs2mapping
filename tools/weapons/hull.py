import numpy as np
from itertools import combinations
def support_points(V, n=80, seed=1):
    rng = np.random.default_rng(seed)
    D = rng.normal(size=(n, 3)); D = np.vstack([D, np.eye(3), -np.eye(3)]); D /= np.linalg.norm(D, axis=1, keepdims=True)
    return V[np.unique(np.argmax(V @ D.T, axis=0))]
def _hull2d(pts):
    pts = sorted(map(tuple, pts))
    def half(seq):
        h = []
        for p in seq:
            while len(h) >= 2 and (h[-1][0]-h[-2][0])*(p[1]-h[-2][1]) - (h[-1][1]-h[-2][1])*(p[0]-h[-2][0]) <= 0: h.pop()
            h.append(p)
        return h
    lo = half(pts); hi = half(pts[::-1]); return lo[:-1] + hi[:-1]
def convex_hull(P, eps=1e-3):
    """hull of a small point set -> (verts, list of polygon index lists, outward CCW)"""
    P = np.unique(np.round(P, 4), axis=0); n = len(P); c = P.mean(0)
    planes = {}
    for i, j, k in combinations(range(n), 3):
        a, b, d = P[i], P[j], P[k]; nrm = np.cross(b - a, d - a); ln = np.linalg.norm(nrm)
        if ln < 1e-9: continue
        nrm /= ln; s = (P - a) @ nrm
        if s.max() <= eps: pass
        elif s.min() >= -eps: nrm = -nrm; s = -s
        else: continue
        if np.dot(nrm, a - c) < 0: continue
        key = tuple(np.round(nrm, 2)) + (round(float(nrm @ a), 1),)
        planes.setdefault(key, set()).update(np.where(np.abs(s) <= eps)[0].tolist())
    polys = []
    for key, idxs in planes.items():
        idxs = sorted(idxs); nrm = np.array(key[:3]); nrm /= np.linalg.norm(nrm)
        u = np.cross(nrm, [1, 0, 0]); u = np.cross(nrm, [0, 1, 0]) if np.linalg.norm(u) < 0.1 else u; u /= np.linalg.norm(u); v = np.cross(nrm, u)
        pts2 = [(float(P[i] @ u), float(P[i] @ v), i) for i in idxs]
        ring = _hull2d([(x, y) for x, y, _ in pts2]); lookup = {(x, y): i for x, y, i in pts2}
        poly = [lookup[p] for p in ring]
        if len(poly) >= 3:
            a, b, d = P[poly[0]], P[poly[1]], P[poly[2]]
            if np.dot(np.cross(b - a, d - a), nrm) < 0: poly = poly[::-1]
            polys.append(poly)
    used = sorted({i for p in polys for i in p}); remap = {v: q for q, v in enumerate(used)}
    return P[used], [[remap[i] for i in p] for p in polys]
