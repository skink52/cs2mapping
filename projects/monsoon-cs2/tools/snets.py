"""Surface nets: a quad mesh of the zero set of a sampled field (mg_monsoon playtest 1: the tunnels and their mouths).

phi is sampled on grid corners (x0 + i h, y0 + j h, z0 + k h); phi > 0 is air. One vertex per cell the surface crosses (the mean of
the crossing points on its 12 edges), one quad per grid edge with a sign change (the four cells round it), wound so its normal
points into the air. Properties a Hammer half-edge mesh needs:
- every mesh edge is shared by at most two quads once no grid face is ambiguous (a face whose corners alternate + - + - gives a
  mesh edge four quads): fix_ambiguous() flips the weakest corner of each such face first;
- cells can be excluded (include mask): a quad is kept only when all four of its cells are included, so the mesh can stop on a
  plane (an open boundary) exactly where its cells stop;
- force: per-cell vertex positions that override the mean (e.g. a heightfield's own vertices on a boundary it must meet).
Where two separate sheets pass through one cell the shared vertex is a pinch; vmesh.polymesh_open splits those.
"""
import numpy as np


def fix_ambiguous(phi, max_iter=200):
    """every grid face whose corners alternate in sign (+ - + -): its weakest earth corner (phi < 0, smallest |phi|) becomes air.
    Corners only ever go from earth to air, so this cannot cycle; the void grows by a hair where a sheet of earth was thinner than a
    cell. Returns (phi, corners flipped)."""
    phi = np.array(phi, float)
    phi[phi == 0.0] = -1e-4
    fixed = 0
    for _ in range(max_iter):
        n_this = 0
        for ax in range(3):
            S = phi > 0
            a1, a2 = [a for a in range(3) if a != ax]
            def sl(o1, o2):
                idx = [slice(None)] * 3
                idx[a1] = slice(o1, phi.shape[a1] - 1 + o1); idx[a2] = slice(o2, phi.shape[a2] - 1 + o2)
                return tuple(idx)
            c = [sl(0, 0), sl(1, 0), sl(1, 1), sl(0, 1)]
            s0, s1, s2, s3 = (S[q] for q in c)
            amb = (s0 == s2) & (s1 == s3) & (s0 != s1)
            if not amb.any(): continue
            n_this += int(amb.sum())
            vals = np.stack([phi[q] for q in c], 0)
            mag = np.where(vals < 0, np.abs(vals), np.inf)
            pick = mag.argmin(0)
            for q_i, q in enumerate(c):
                sel = amb & (pick == q_i)
                if not sel.any(): continue
                sub = phi[q]                                  # a view into phi
                sub[sel] = 1e-3
        fixed += n_this
        if not n_this: break
    else:
        raise RuntimeError('surface nets: ambiguous grid faces left after %d rounds' % max_iter)
    return phi, fixed


def surface_nets(phi, x0, y0, z0, h, include=None, force=None):
    """-> (verts (n,3), quads (m,4) int, cell (n,3) int of each vertex). force: (mask over cells, positions (n,3) for those cells)"""
    nx, ny, nz = phi.shape
    S = phi > 0
    ncell = (nx - 1) * (ny - 1) * (nz - 1)
    acc = np.zeros((ncell, 3)); cnt = np.zeros(ncell)
    cid = lambda i, j, k: (i * (ny - 1) + j) * (nz - 1) + k
    for ax in range(3):
        lo = [slice(None)] * 3; hi = [slice(None)] * 3
        lo[ax] = slice(0, -1); hi[ax] = slice(1, None)
        pa, pb = phi[tuple(lo)], phi[tuple(hi)]
        e = (pa > 0) != (pb > 0)
        I, J, K = np.nonzero(e)
        t = pa[I, J, K] / (pa[I, J, K] - pb[I, J, K])
        P = np.stack([x0 + I * h, y0 + J * h, z0 + K * h], 1).astype(float)
        P[:, ax] += t * h
        # the four cells sharing this edge
        o1, o2 = [a for a in range(3) if a != ax]
        for d1 in (-1, 0):
            for d2 in (-1, 0):
                C = np.stack([I, J, K], 1).copy()
                C[:, o1] += d1; C[:, o2] += d2
                ok = (C[:, o1] >= 0) & (C[:, o1] < phi.shape[o1] - 1) & (C[:, o2] >= 0) & (C[:, o2] < phi.shape[o2] - 1) & (C[:, ax] < phi.shape[ax] - 1)
                ids = cid(C[ok, 0], C[ok, 1], C[ok, 2])
                np.add.at(acc, ids, P[ok]); np.add.at(cnt, ids, 1)
    has = cnt > 0
    if include is not None: has &= np.asarray(include, bool).ravel()
    vid = -np.ones(ncell, np.int64); vid[has] = np.arange(int(has.sum()))
    V = acc[has] / cnt[has, None]
    if force is not None:
        fm = np.asarray(force[0], bool).ravel() & has
        fp = np.asarray(force[1], float)
        full = np.zeros((ncell, 3)); full[np.asarray(force[0], bool).ravel()] = fp
        V[vid[fm]] = full[fm]
    quads = []
    for ax in range(3):
        lo = [slice(None)] * 3; hi = [slice(None)] * 3
        lo[ax] = slice(0, -1); hi[ax] = slice(1, None)
        sa, sb = S[tuple(lo)], S[tuple(hi)]
        e = sa != sb
        I, J, K = np.nonzero(e)
        o1, o2 = [a for a in range(3) if a != ax]
        Cn = np.stack([I, J, K], 1)
        ok = (Cn[:, o1] >= 1) & (Cn[:, o1] <= phi.shape[o1] - 2) & (Cn[:, o2] >= 1) & (Cn[:, o2] <= phi.shape[o2] - 2)
        Cn = Cn[ok]; air_hi = sb[I[ok], J[ok], K[ok]]
        corners = []
        for (d1, d2) in ((-1, -1), (0, -1), (0, 0), (-1, 0)):     # (o1, o2) steps: + along o1, then + along o2: normal = o1 x o2
            C = Cn.copy(); C[:, o1] += d1; C[:, o2] += d2
            corners.append(vid[cid(C[:, 0], C[:, 1], C[:, 2])])
        Q = np.stack(corners, 1)
        # o1 x o2 is +ax for (x: y,z), (y: x,z) gives -y, (z: x,y) +z: put every quad's normal along +ax first
        if ax == 1: Q = Q[:, ::-1]
        Q = np.where(air_hi[:, None], Q, Q[:, ::-1])               # the normal points to the air side
        Q = Q[(Q >= 0).all(1)]
        quads.append(Q)
    Q = np.concatenate(quads) if quads else np.zeros((0, 4), np.int64)
    ci = np.nonzero(has)[0]
    cell = np.stack([ci // ((ny - 1) * (nz - 1)), (ci // (nz - 1)) % (ny - 1), ci % (nz - 1)], 1)
    return V, Q, cell


def edge_use(quads):
    """how many quads use each undirected edge: a manifold mesh has only 1 (boundary) or 2"""
    E = np.concatenate([np.stack([quads[:, k], quads[:, (k + 1) % 4]], 1) for k in range(4)])
    E = np.sort(E, 1)
    _, c = np.unique(E, axis=0, return_counts=True)
    return c
