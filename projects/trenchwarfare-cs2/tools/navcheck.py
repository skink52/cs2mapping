"""coverage + connectivity of a compiled nav against the bot destinations. Reads only.
usage: python tools/navcheck.py <map.nav> [keep.json]
destinations: every post / dressing station (check_play nav_protect) and nav seed (proto_keep.json, from the map the patch read)
plus CONFIG.BOTS.AREAS points (both sides): woodsopen, and undergroundopen (landing, northern gallery, chamber edge). Adjacency: areas sharing a corner (welded vertices);
ladder and jump links are not read, so the woods (ladder) and the galleries (sap ramp) may show as their own pieces."""
import sys, os, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import navread
from scipy import sparse
from scipy.sparse.csgraph import connected_components
ver, V, polys = navread.read(sys.argv[1])
keep = json.load(open(sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'proto_keep.json')))['keep']
pts = [('keep', *p) for p in keep]
for (x, y, z) in [(605, 3930, 10), (1110, 3700, 10), (1110, 4150, 6)]: pts += [('woods pt', x, y, z), ('woods pt', -x, y, z)]
pts += [('landing', 2120, -3296, -252), ('landing', -2120, -3296, -252)]
for (x, y, z) in [(1100, -3272, -247), (130, -3272, -258)]: pts += [('gallery pt', x, y, z), ('gallery pt', -x, y, z)]   # BOTS.AREAS.undergroundopen
rows, cols = [], []
for i, idx in enumerate(polys):
    for c in idx: rows.append(i); cols.append(c)
M = sparse.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(polys), len(V)))
adj = (M @ M.T).tocsr()
# T-junctions: a corner of one area lying on an edge of another (within 1.5 u in xy, 20 u in z) joins them too
from collections import defaultdict
G = 32.0
cells = defaultdict(list)
owner = defaultdict(list)
for i, idx in enumerate(polys):
    for c in idx: owner[c].append(i)
for c in range(len(V)): cells[(int(V[c, 0] // G), int(V[c, 1] // G))].append(c)
er, ec = [], []
for i, idx in enumerate(polys):
    P = V[list(idx)]
    for k in range(len(idx)):
        a, b = P[k], P[(k + 1) % len(idx)]
        lo = np.minimum(a, b) - 2; hi = np.maximum(a, b) + 2
        ab = b[:2] - a[:2]; L2 = float(ab @ ab) or 1e-9
        for gx in range(int(lo[0] // G), int(hi[0] // G) + 1):
            for gy in range(int(lo[1] // G), int(hi[1] // G) + 1):
                for c in cells.get((gx, gy), ()):
                    q = V[c]
                    t = float((q[:2] - a[:2]) @ ab) / L2
                    if t < -0.01 or t > 1.01: continue
                    pr = a + (b - a) * min(1, max(0, t))
                    if np.hypot(*(q[:2] - pr[:2])) < 1.5 and abs(q[2] - pr[2]) < 20:
                        for j in owner[c]:
                            if j != i: er.append(i); ec.append(j)
adj = (adj + sparse.csr_matrix((np.ones(len(er)), (er, ec)), shape=adj.shape)).tocsr()
ncomp, lab = connected_components(adj, directed=False)
sizes = np.bincount(lab)
def contains(P, x, y):
    n = len(P); inside = False
    for k in range(n):
        x1, y1 = P[k][:2]; x2, y2 = P[(k + 1) % n][:2]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1: inside = not inside
    return inside
cent = np.array([V[list(p)].mean(0) for p in polys])
res = []; miss = 0
for (kind, x, y, z) in pts:
    best = None
    near = np.nonzero((np.abs(cent[:, 0] - x) < 400) & (np.abs(cent[:, 1] - y) < 400))[0]
    for i in near:
        P = V[list(polys[i])]
        if contains(P, x, y) and abs(P[:, 2].mean() - z) < 64: best = (0.0, i); break
    if best is None and len(near):
        d = np.hypot(cent[near, 0] - x, cent[near, 1] - y) + np.abs(cent[near, 2] - z) * 2
        k = int(np.argmin(d)); best = (float(d[k]), near[k])
    if best is None or best[0] > 64: miss += 1
    res.append((kind, round(x), round(y), round(z), None if best is None else round(best[0]), None if best is None else int(lab[best[1]])))
comps = {}
for r in res: comps.setdefault(r[5], []).append(r)
print('areas %d, pieces %d (largest %s)' % (len(polys), ncomp, sorted(sizes)[-6:]))
for c, rs in sorted(comps.items(), key=lambda t: -len(t[1])):
    print('piece %s (%s areas): %d points: %s' % (c, sizes[c] if c is not None else '-', len(rs), ', '.join('%s(%d,%d,%d)%s' % (r[0], r[1], r[2], r[3], '' if not r[4] else ' d%d' % r[4]) for r in rs[:6]) + (' ...' if len(rs) > 6 else '')))
for r in res:
    if r[0] != 'keep': print('  %-10s (%d, %d, %d): piece %s, %s' % (r[0], r[1], r[2], r[3], r[5], 'inside an area' if r[4] == 0 else 'nearest area %s u' % r[4]))
print('points with no nav area within 64 u: %d of %d' % (miss, len(pts)))
for r in res:
    if r[4] is None or r[4] > 64: print('  MISSING', r)
