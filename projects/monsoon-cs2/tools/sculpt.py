"""Signed-distance sculpting for organic props (mg_monsoon playtest 1, finding 18: the guardian lion was a pile of ellipsoids).

Build a shape as an SDF over a grid (smooth unions of ellipsoids, round cones, rounded boxes; subtractions for mouths, toes,
breaks), erode it with noise, mesh it with surface nets (a dual method: one vertex per surface cell, quads across sign changes),
smooth it lightly (Taubin), take the normals from the SDF gradient, and unwrap it into planar charts per dominant axis so the
atlas baker (bake.py) can paint it like any other prop. Pure numpy/scipy. AI-generated (Claude) for skink52.
"""
import numpy as np
from scipy import ndimage
import geo


# ---------------------------------------------------------------- SDF primitives (P: (n,3))
def sph(P, c, r):
    return np.linalg.norm(P - np.asarray(c, float), axis=1) - r


def ell(P, c, r, R=None):
    """ellipsoid of semi-axes r at c, optionally rotated by R (columns = local axes in world); approximate distance (iq's bound)"""
    q = P - np.asarray(c, float)
    if R is not None: q = q @ np.asarray(R, float)
    r = np.asarray(r, float)
    k0 = np.linalg.norm(q / r, axis=1); k1 = np.linalg.norm(q / (r * r), axis=1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)


def cone(P, a, b, ra, rb):
    """round cone / capsule from a (radius ra) to b (radius rb)"""
    a = np.asarray(a, float); b = np.asarray(b, float)
    pa = P - a; ba = b - a
    h = np.clip(pa @ ba / max(ba @ ba, 1e-9), 0, 1)
    return np.linalg.norm(pa - h[:, None] * ba, axis=1) - (ra + (rb - ra) * h)


def chain(P, pts, radii, k=1.5):
    """smooth union of round cones through pts"""
    d = None
    for i in range(len(pts) - 1):
        e = cone(P, pts[i], pts[i + 1], radii[i], radii[i + 1])
        d = e if d is None else smin(d, e, k)
    return d


def rbox(P, c, half, r=0.0, R=None):
    q = P - np.asarray(c, float)
    if R is not None: q = q @ np.asarray(R, float)
    q = np.abs(q) - (np.asarray(half, float) - r)
    return np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(q.max(1), 0) - r


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b + (a - b) * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def cut(d, e, k=0.6):
    """subtract shape e from d, with a small fillet"""
    return smax(d, -e, k)


# ---------------------------------------------------------------- meshing
def surface_nets(F, lo, h):
    """F: (nx,ny,nz) SDF samples at lo + i*h. Returns V (k,3), quads as triangles (m,3) wound so normals point to +F (outside)."""
    nx, ny, nz = F.shape
    inside = F < 0
    # cells with a sign change among their 8 corners
    c = [inside[i:nx - 1 + i, j:ny - 1 + j, k:nz - 1 + k] for i in (0, 1) for j in (0, 1) for k in (0, 1)]
    anyin = np.logical_or.reduce(c); allin = np.logical_and.reduce(c)
    act = anyin & ~allin
    idx = -np.ones(act.shape, np.int64)
    ci = np.argwhere(act)
    idx[act] = np.arange(len(ci))
    # vertex = mean of the edge crossings of the cell
    acc = np.zeros((len(ci), 3)); cnt = np.zeros(len(ci))
    corners = np.array([(i, j, k) for i in (0, 1) for j in (0, 1) for k in (0, 1)])
    edges = [(a, b) for a in range(8) for b in range(a + 1, 8) if np.abs(corners[a] - corners[b]).sum() == 1]
    for a, b in edges:
        pa = ci + corners[a]; pb = ci + corners[b]
        fa = F[pa[:, 0], pa[:, 1], pa[:, 2]]; fb = F[pb[:, 0], pb[:, 1], pb[:, 2]]
        s = (fa < 0) != (fb < 0)
        t = np.where(s, fa / np.where(s, fa - fb, 1.0), 0.0)
        p = pa + (pb - pa) * t[:, None]
        acc[s] += p[s]; cnt[s] += 1
    V = acc / np.maximum(cnt, 1)[:, None] * h + np.asarray(lo, float)
    tris = []
    # one quad per grid edge with a sign change, joining the 4 cells around it
    for ax in range(3):
        o1, o2 = [a for a in range(3) if a != ax]
        sl0 = [slice(0, n) for n in F.shape]; sl1 = list(sl0)
        sl0[ax] = slice(0, F.shape[ax] - 1); sl1[ax] = slice(1, F.shape[ax])
        s = inside[tuple(sl0)] != inside[tuple(sl1)]
        pts = np.argwhere(s)
        # the edge needs the 4 cells (o1-1|o1, o2-1|o2) to exist
        ok = (pts[:, o1] > 0) & (pts[:, o2] > 0) & (pts[:, o1] < F.shape[o1] - 1) & (pts[:, o2] < F.shape[o2] - 1)
        pts = pts[ok]
        flip = inside[tuple(pts.T)]
        def cell(d1, d2):
            q = pts.copy(); q[:, o1] -= d1; q[:, o2] -= d2
            return idx[q[:, 0], q[:, 1], q[:, 2]]
        a, b, c_, d = cell(1, 1), cell(0, 1), cell(0, 0), cell(1, 0)
        good = (a >= 0) & (b >= 0) & (c_ >= 0) & (d >= 0)
        a, b, c_, d, flip = a[good], b[good], c_[good], d[good], flip[good]
        t1 = np.stack([a, b, c_], 1); t2 = np.stack([a, c_, d], 1)
        # orientation: decided below from the SDF gradient
        tris += [t1, t2]
    T = np.concatenate(tris)
    return V, T


def taubin(V, T, it=2, lam=0.5, mu=-0.53):
    n = len(V)
    from scipy.sparse import coo_matrix
    e = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]); e = np.concatenate([e, e[:, ::-1]])
    A = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)).tocsr(); A.data[:] = 1
    deg = np.asarray(A.sum(1)).ravel(); deg[deg == 0] = 1
    for _ in range(it):
        for f in (lam, mu):
            V = V + f * ((A @ V) / deg[:, None] - V)
    return V


def grad_normals(F, lo, h, V):
    g = np.gradient(F, h)
    c = ((V - lo) / h).T
    N = np.stack([ndimage.map_coordinates(gi, c, order=1, mode='nearest') for gi in g], 1)
    return N / (np.linalg.norm(N, axis=1, keepdims=True) + 1e-9)


def mesh_sdf(fn, lo, hi, h, smooth=2, mat='stone', part=None, min_chart_faces=6):
    """sample fn (P -> distance) on a grid of spacing h over [lo, hi], mesh it and unwrap it -> geo.Mesh with planar charts"""
    lo = np.asarray(lo, float); hi = np.asarray(hi, float)
    n = np.ceil((hi - lo) / h).astype(int) + 1
    g = np.stack(np.meshgrid(*[lo[i] + np.arange(n[i]) * h for i in range(3)], indexing='ij'), -1).reshape(-1, 3)
    F = np.concatenate([fn(g[i:i + 400000]) for i in range(0, len(g), 400000)]).reshape(n)
    V, T = surface_nets(F, lo, h)
    # drop floating crumbs (a break can leave a sliver detached): keep pieces with at least 1 % of the faces
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    nvv = len(V); e = np.concatenate([T[:, [0, 1]], T[:, [1, 2]]])
    _, lab = connected_components(coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(nvv, nvv)), directed=False)
    fl = lab[T[:, 0]]; cnt = np.bincount(fl)
    T = T[cnt[fl] >= max(50, 0.01 * len(T))]
    # drop unused vertices
    used = np.unique(T); remap = -np.ones(len(V), np.int64); remap[used] = np.arange(len(used)); V = V[used]; T = remap[T]
    if smooth: V = taubin(V, T, smooth)
    N = grad_normals(F, lo, h, V)
    fn_ = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    flip = np.einsum('ij,ij->i', fn_, N[T].mean(1)) < 0
    T[flip] = T[flip][:, ::-1]
    return unwrap(V, N, T, mat, part, min_chart_faces)


def unwrap(V, N, T, mat, part, min_chart_faces=6):
    """planar charts: each face goes to the axis (+-x, +-y, +-z) its normal is closest to (labels smoothed over neighbours so
    charts are not confetti), each connected group of same-label faces becomes one chart projected on that axis' plane"""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    fnm = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    fnm /= np.linalg.norm(fnm, axis=1, keepdims=True) + 1e-12
    dirs = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1.0]])
    score = fnm @ dirs.T
    nf = len(T)
    # face adjacency through shared edges
    e = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]); fi = np.tile(np.arange(nf), 3)
    e.sort(1); key = e[:, 0] * (len(V) + 1) + e[:, 1]
    o = np.argsort(key); ks = key[o]; same = np.nonzero(ks[1:] == ks[:-1])[0]
    a, b = fi[o][same], fi[o][same + 1]
    adj = coo_matrix((np.ones(len(a) * 2), (np.concatenate([a, b]), np.concatenate([b, a]))), shape=(nf, nf)).tocsr()
    for _ in range(3):                   # smooth the axis scores so small islands join their neighbours
        score = 0.5 * score + 0.5 * (adj @ score) / np.maximum(np.asarray(adj.sum(1)), 1)
    lab = score.argmax(1)
    keep = lab[a] == lab[b]
    g = coo_matrix((np.ones(keep.sum()), (a[keep], b[keep])), shape=(nf, nf))
    ncomp, comp = connected_components(g, directed=False)
    m = geo.Mesh()
    Vs, Ns, Ts, Fs, FCs = [], [], [], [], []
    charts = []
    nv = 0
    axes_uv = {0: (1, 2), 1: (2, 1), 2: (2, 0), 3: (0, 2), 4: (0, 1), 5: (1, 0)}
    for cidx in range(ncomp):
        fsel = np.nonzero(comp == cidx)[0]
        L = np.bincount(lab[fsel], minlength=6).argmax()
        vs = np.unique(T[fsel]); rm = np.full(len(V), -1, np.int64); rm[vs] = np.arange(len(vs))
        P = V[vs]; ua, va = axes_uv[L]
        u = P[:, ua]; v = -P[:, va] if va == 2 else P[:, va]       # z runs down the image (v from the top)
        w = max(u.max() - u.min(), 0.5); hh = max(v.max() - v.min(), 0.5)
        Ts.append(np.stack([(u - u.min()) / w, (v - v.min()) / hh], 1))
        Vs.append(P); Ns.append(N[vs])
        Fs.append(rm[T[fsel]] + nv)
        FCs.append(np.full(len(fsel), len(charts)))
        charts.append(dict(w=float(w), h=float(hh), mat=mat))
        nv += len(vs)
    m.V = np.concatenate(Vs); m.N = np.concatenate(Ns); m.T = np.concatenate(Ts)
    m.F = np.concatenate(Fs).astype(np.int64); m.FC = np.concatenate(FCs).astype(np.int64)
    # keep each chart's winding consistent with its (possibly mirrored) uv: the baker does not care, the SMD does not either
    m.charts = charts
    m.parts = [part or geo.frame(mono=1.0)]; m.FP = np.zeros(len(m.F), np.int64)
    return m


def noise3(P, freq, octaves, seed):
    from noise import fbm
    return fbm(P[:, 0] * freq, P[:, 1] * freq, P[:, 2] * freq, octaves, seed=seed)
