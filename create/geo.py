"""Triangle meshes with per-chart local UVs (for atlas baking) and part frames (for procedural shading).

Coordinates are Source units, Z up. A chart is a [0,1]^2 UV patch of known world size (w, h units); the baker
packs charts into one atlas per model. A part is a local frame (R, o) handed to shaders (wood grain, panel axes).
"""
import numpy as np

class Mesh:
    def __init__(self):
        self.V = np.zeros((0, 3)); self.N = np.zeros((0, 3)); self.T = np.zeros((0, 2))
        self.F = np.zeros((0, 3), np.int64); self.FC = np.zeros(0, np.int64); self.FP = np.zeros(0, np.int64)
        self.charts = []   # dict(w, h, mat)
        self.parts = []    # dict(R, o, **params)

    def copy(self):
        m = Mesh()
        m.V, m.N, m.T, m.F, m.FC, m.FP = self.V.copy(), self.N.copy(), self.T.copy(), self.F.copy(), self.FC.copy(), self.FP.copy()
        m.charts = [dict(c) for c in self.charts]
        m.parts = [dict(p, R=p['R'].copy(), o=p['o'].copy()) for p in self.parts]
        return m

    def add(self, o):
        if o is None or len(o.F) == 0: return self
        nv, nc, npart = len(self.V), len(self.charts), len(self.parts)
        self.V = np.vstack([self.V, o.V]); self.N = np.vstack([self.N, o.N]); self.T = np.vstack([self.T, o.T])
        self.F = np.vstack([self.F, o.F + nv]); self.FC = np.concatenate([self.FC, o.FC + nc]); self.FP = np.concatenate([self.FP, o.FP + npart])
        self.charts += [dict(c) for c in o.charts]
        self.parts += [dict(p, R=p['R'].copy(), o=p['o'].copy()) for p in o.parts]
        return self

    def transform(self, R=None, t=(0, 0, 0), s=1.0):
        R = np.eye(3) if R is None else np.asarray(R, float)
        t = np.asarray(t, float)
        self.V = (self.V * s) @ R.T + t
        self.N = self.N @ R.T
        if np.linalg.det(R) < 0: self.F = self.F[:, ::-1]
        for c in self.charts: c['w'] *= s; c['h'] *= s
        for p in self.parts:
            p['R'] = R @ p['R']; p['o'] = (p['o'] * s) @ R.T + t
        return self

    def bounds(self):
        return self.V.min(0), self.V.max(0)

    def tri_count(self): return len(self.F)

    def face_normals(self):
        a, b, c = self.V[self.F[:, 0]], self.V[self.F[:, 1]], self.V[self.F[:, 2]]
        n = np.cross(b - a, c - a)
        return n

    def recompute_normals(self, angle=55.0, weld=True):
        fn = self.face_normals()
        n0 = np.zeros_like(self.V)
        for k in range(3): np.add.at(n0, self.F[:, k], fn)
        l = np.linalg.norm(n0, axis=1, keepdims=True); l[l == 0] = 1; n0 /= l
        if not weld:
            self.N = n0; return self
        q = np.round(self.V * 64).astype(np.int64)
        key = np.stack([q[:, 0], q[:, 1], q[:, 2], self._vpart()], 1)
        _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
        inv = inv.ravel()
        out = n0.copy()
        multi = np.where(cnt[inv] > 1)[0]
        if len(multi):
            order = multi[np.argsort(inv[multi], kind='stable')]
            g = inv[order]
            splits = np.flatnonzero(np.diff(g)) + 1
            cos = np.cos(np.radians(angle))
            for grp in np.split(order, splits):
                ns = n0[grp]
                d = ns @ ns.T
                acc = (d > cos).astype(float) @ ns
                l = np.linalg.norm(acc, axis=1, keepdims=True); l[l == 0] = 1
                out[grp] = acc / l
        self.N = out
        return self

    def _vpart(self):
        vp = np.zeros(len(self.V), np.int64)
        vp[self.F.ravel()] = np.repeat(self.FP, 3)
        return vp

    def deform(self, fn):
        """fn(V) -> new V; normals recomputed"""
        self.V = fn(self.V.copy())
        return self.recompute_normals()


def frame(R=None, o=(0, 0, 0), **kw):
    return dict(R=np.eye(3) if R is None else np.asarray(R, float), o=np.asarray(o, float), **kw)


def surface(P, mat, part=None, closed_u=False, closed_v=False, w=None, h=None, N=None, flip=False):
    """P: (nu+1, nv+1, 3) grid of points. Faces wind so the normal is du x dv (flip reverses)."""
    P = np.asarray(P, float)
    nu, nv = P.shape[0] - 1, P.shape[1] - 1
    m = Mesh()
    uu, vv = np.meshgrid(np.linspace(0, 1, nu + 1), np.linspace(0, 1, nv + 1), indexing='ij')
    m.V = P.reshape(-1, 3)
    m.T = np.stack([uu.ravel(), vv.ravel()], 1)
    idx = np.arange((nu + 1) * (nv + 1)).reshape(nu + 1, nv + 1)
    a = idx[:-1, :-1].ravel(); b = idx[1:, :-1].ravel(); c = idx[1:, 1:].ravel(); d = idx[:-1, 1:].ravel()
    F = np.concatenate([np.stack([a, b, c], 1), np.stack([a, c, d], 1)])
    # drop degenerate triangles (poles)
    A, B, C = m.V[F[:, 0]], m.V[F[:, 1]], m.V[F[:, 2]]
    keep = np.linalg.norm(np.cross(B - A, C - A), axis=1) > 1e-9
    F = F[keep]
    if flip: F = F[:, ::-1]
    m.F = F
    if w is None: w = np.linalg.norm(np.diff(P, axis=0), axis=2).sum(0).mean()
    if h is None: h = np.linalg.norm(np.diff(P, axis=1), axis=2).sum(1).mean()
    m.charts = [dict(w=max(float(w), 1e-3), h=max(float(h), 1e-3), mat=mat)]
    m.FC = np.zeros(len(F), np.int64)
    m.parts = [part or frame()]
    m.FP = np.zeros(len(F), np.int64)
    if N is not None:
        m.N = np.asarray(N, float).reshape(-1, 3)
    else:
        m.recompute_normals(angle=80)
        if closed_u or closed_v:
            pass
    return m


def rbox(sx, sy, sz, r=0.5, seg=2, mat='mat', part=None, div=(1, 1, 1), center=(0, 0, 0), jitter=None):
    """Axis-aligned box with rounded edges (radius r). div: interior subdivisions along x,y,z."""
    hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
    r = min(r, hx * 0.99, hy * 0.99, hz * 0.99)
    inner = np.array([hx - r, hy - r, hz - r])
    def axis_ts(h, n_in):
        # param positions on the cube face axis in physical units, dense near the edges
        ts = [-h]
        for k in range(1, seg + 1):
            ts.append(-h + r * (k / seg))   # within the rounded band
        ts = ts[:-1] + list(np.linspace(-(h - r), (h - r), n_in + 1))
        ts += [h - r + r * (k / seg) for k in range(1, seg + 1)]
        return np.array(ts)
    ex, ey, ez = axis_ts(hx, div[0]), axis_ts(hy, div[1]), axis_ts(hz, div[2])
    m = Mesh()
    part = part or frame(o=center)
    faces = [  # (normal axis, sign, u axis, v axis)
        (2, 1, 0, 1), (2, -1, 1, 0), (0, 1, 1, 2), (0, -1, 2, 1), (1, 1, 2, 0), (1, -1, 0, 2)]
    E = [ex, ey, ez]; H = [hx, hy, hz]
    for ax, sg, ua, va in faces:
        tu, tv = E[ua], E[va]
        U, Vv = np.meshgrid(tu, tv, indexing='ij')
        Pc = np.zeros(U.shape + (3,))
        Pc[..., ua] = U; Pc[..., va] = Vv; Pc[..., ax] = sg * H[ax]
        # round: points beyond the inner box are pulled onto spheres/cylinders of radius r
        cl = np.clip(Pc, -inner, inner)
        d = Pc - cl
        l = np.linalg.norm(d, axis=-1, keepdims=True)
        nrm = np.where(l > 1e-9, d / np.maximum(l, 1e-9), 0)
        P = cl + nrm * r
        N = nrm
        # orientation: make du x dv point outwards
        du = P[1, 0] - P[0, 0] if P.shape[0] > 1 else None
        s = surface(P, mat, part, w=2 * H[ua], h=2 * H[va], N=N.reshape(-1, 3))
        fn = s.face_normals()
        cen = s.V[s.F].mean(1)
        if (np.einsum('ij,ij->i', fn, cen - 0) < 0).sum() > len(fn) / 2:
            s.F = s.F[:, ::-1]
        m.add(s)
    # merge parts into one
    m.parts = [part]; m.FP[:] = 0
    m.V = m.V + np.asarray(center, float)
    m.parts[0]['o'] = np.asarray(center, float) if part is None else m.parts[0]['o']
    return m


def path_frames(pts):
    """parallel-transport frames along a polyline: tangents T, normals Nn, binormals B"""
    pts = np.asarray(pts, float)
    T = np.gradient(pts, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    up = np.array([0, 0, 1.0]) if abs(T[0, 2]) < 0.9 else np.array([1.0, 0, 0])
    n = np.cross(T[0], up); n /= np.linalg.norm(n)
    Ns = [n]
    for i in range(1, len(pts)):
        v = np.cross(T[i - 1], T[i]); s = np.linalg.norm(v)
        if s > 1e-8:
            v /= s; ang = np.arctan2(s, np.dot(T[i - 1], T[i]))
            n = n * np.cos(ang) + np.cross(v, n) * np.sin(ang) + v * np.dot(v, n) * (1 - np.cos(ang))
        n = n - T[i] * np.dot(n, T[i]); n /= np.linalg.norm(n)
        Ns.append(n)
    Ns = np.array(Ns)
    B = np.cross(T, Ns)
    return T, Ns, B


def tube(pts, radii, sides=8, mat='mat', part=None, caps=True, rnoise=None, phase=0.0):
    """generalised cylinder along pts with per-point radii. rnoise(theta, s) -> radius multiplier"""
    pts = np.asarray(pts, float); radii = np.broadcast_to(np.asarray(radii, float), (len(pts),))
    Tn, Nn, Bn = path_frames(pts)
    th = np.linspace(0, 2 * np.pi, sides + 1) + phase
    seglen = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    P = np.zeros((sides + 1, len(pts), 3)); NN = np.zeros_like(P)
    for j in range(len(pts)):
        rr = radii[j] * (rnoise(th, seglen[j]) if rnoise else 1.0)
        dirs = np.cos(th)[:, None] * Nn[j] + np.sin(th)[:, None] * Bn[j]
        P[:, j] = pts[j] + dirs * np.broadcast_to(rr, th.shape)[:, None]
        NN[:, j] = dirs
    P[-1] = P[0]
    circ = 2 * np.pi * float(np.mean(radii))
    m = surface(P, mat, part or frame(o=pts[0], axis=Tn.mean(0)), w=circ, h=seglen[-1] + 1e-3)
    fn = m.face_normals(); cen = m.V[m.F].mean(1)
    ctr = np.repeat(pts, 1, axis=0)
    if np.einsum('ij,ij->i', fn, NN.reshape(-1, 3)[m.F[:, 0]]).mean() < 0: m.F = m.F[:, ::-1]
    m.recompute_normals(angle=70)
    if caps:
        for j, sgn in ((0, -1), (len(pts) - 1, 1)):
            if radii[j] < 1e-3: continue
            ring = P[:-1, j]
            c = pts[j]
            cap = disk(c, ring, Tn[j] * sgn, mat, m.parts[0])
            m.add(cap)
            m.FP[-len(cap.F):] = 0
        m.parts = m.parts[:1]
    return m


def disk(center, ring, normal, mat, part=None):
    """fan cap from a ring of points"""
    ring = np.asarray(ring, float); n = len(ring)
    m = Mesh()
    m.V = np.vstack([center, ring])
    rad = np.linalg.norm(ring - center, axis=1).max() + 1e-6
    # planar uv
    nrm = np.asarray(normal, float); nrm /= np.linalg.norm(nrm)
    a = ring[0] - center; a -= nrm * np.dot(a, nrm); a /= np.linalg.norm(a) + 1e-9
    b = np.cross(nrm, a)
    loc = m.V - center
    m.T = np.stack([0.5 + loc @ a / (2 * rad), 0.5 + loc @ b / (2 * rad)], 1)
    F = np.array([[0, 1 + k, 1 + (k + 1) % n] for k in range(n)])
    fn = np.cross(m.V[F[:, 1]] - m.V[F[:, 0]], m.V[F[:, 2]] - m.V[F[:, 0]])
    if (fn @ nrm).mean() < 0: F = F[:, ::-1]
    m.F = F; m.N = np.tile(nrm, (len(m.V), 1))
    m.charts = [dict(w=2 * rad, h=2 * rad, mat=mat)]; m.FC = np.zeros(n, np.int64)
    m.parts = [part or frame(o=center)]; m.FP = np.zeros(n, np.int64)
    return m


def lathe(profile, sides=16, mat='mat', part=None, axis_frame=None):
    """profile: list of (r, z) from bottom to top; revolved around +Z"""
    pr = np.asarray(profile, float)
    th = np.linspace(0, 2 * np.pi, sides + 1)
    P = np.zeros((sides + 1, len(pr), 3))
    P[..., 0] = np.cos(th)[:, None] * pr[None, :, 0]
    P[..., 1] = np.sin(th)[:, None] * pr[None, :, 0]
    P[..., 2] = pr[None, :, 1]
    plen = np.linalg.norm(np.diff(pr, axis=0), axis=1).sum()
    m = surface(P, mat, part or frame(), w=2 * np.pi * pr[:, 0].max() + 1e-3, h=plen + 1e-3)
    fn = m.face_normals(); cen = m.V[m.F].mean(1)
    radial = cen.copy(); radial[:, 2] = 0
    if np.einsum('ij,ij->i', fn, radial).mean() < 0: m.F = m.F[:, ::-1]
    m.recompute_normals(angle=60)
    return m


def rot(axis, deg):
    a = np.radians(deg); c, s = np.cos(a), np.sin(a)
    if axis == 'x': return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == 'y': return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def euler(yaw=0, pitch=0, roll=0):
    return rot('z', yaw) @ rot('y', pitch) @ rot('x', roll)


def look_frame(direction, up=(0, 0, 1)):
    """rotation whose +x points along direction"""
    x = np.asarray(direction, float); x /= np.linalg.norm(x)
    up = np.asarray(up, float)
    if abs(np.dot(x, up)) > 0.95: up = np.array([0, 1.0, 0]) if abs(x[1]) < 0.9 else np.array([1.0, 0, 0])
    y = np.cross(up, x); y /= np.linalg.norm(y); z = np.cross(x, y)
    return np.stack([x, y, z], 1)


def plank(length, width, thick, mat='wood', r=0.35, seg=2, div=(6, 1, 1), warp=0.0, seed=0, R=None, t=(0, 0, 0), **pkw):
    """a board along local +x, width along y, thickness z; part frame carries grain axis = x"""
    seed = int(abs(seed)) % (2 ** 31)
    rng = np.random.RandomState(seed)
    part = frame(grain=0, seed=seed, **pkw)
    m = rbox(length, width, thick, r=r, seg=seg, mat=mat, part=part, div=div)
    if warp:
        cup = rng.uniform(-1, 1) * warp; bow = rng.uniform(-1, 1) * warp; twist = rng.uniform(-1, 1) * warp * 0.02
        x = m.V[:, 0] / max(length / 2, 1e-6)
        m.V[:, 2] += bow * (1 - x ** 2) + cup * (m.V[:, 1] / max(width / 2, 1e-6)) ** 2
        ang = twist * m.V[:, 0]
        y, z = m.V[:, 1].copy(), m.V[:, 2].copy()
        m.V[:, 1] = y * np.cos(ang) - z * np.sin(ang); m.V[:, 2] = y * np.sin(ang) + z * np.cos(ang)
        m.recompute_normals()
    if R is not None or any(t):
        m.transform(R, t)
    return m


def ear_clip(poly):
    """triangulate a simple 2D polygon (CCW); returns index triples"""
    pts = [tuple(p) for p in poly]
    idx = list(range(len(pts)))
    def area(a, b, c):
        return (pts[b][0] - pts[a][0]) * (pts[c][1] - pts[a][1]) - (pts[c][0] - pts[a][0]) * (pts[b][1] - pts[a][1])
    def inside(p, a, b, c):
        d1 = (p[0] - pts[b][0]) * (pts[a][1] - pts[b][1]) - (pts[a][0] - pts[b][0]) * (p[1] - pts[b][1])
        d2 = (p[0] - pts[c][0]) * (pts[b][1] - pts[c][1]) - (pts[b][0] - pts[c][0]) * (p[1] - pts[c][1])
        d3 = (p[0] - pts[a][0]) * (pts[c][1] - pts[a][1]) - (pts[c][0] - pts[a][0]) * (p[1] - pts[a][1])
        neg = (d1 < 0) or (d2 < 0) or (d3 < 0); pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
        return not (neg and pos)
    tris = []
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        n = len(idx)
        for i in range(n):
            a, b, c = idx[(i - 1) % n], idx[i], idx[(i + 1) % n]
            if area(a, b, c) <= 1e-9: continue
            if any(inside(pts[j], a, b, c) for j in idx if j not in (a, b, c)): continue
            tris.append((a, b, c)); idx.pop(i); break
        else:
            break
    if len(idx) == 3: tris.append(tuple(idx))
    return tris


def poly_area(poly):
    p = np.asarray(poly, float)
    return 0.5 * np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1])


def prism(poly, y0, y1, mat, part=None, rim_mat=None, rim_charts=True):
    """extrude a polygon given in the x-z plane between y0 and y1 (caps + rim)"""
    poly = np.asarray(poly, float)
    if poly_area(poly) < 0: poly = poly[::-1]
    n = len(poly)
    part = part or frame()
    m = Mesh()
    tris = ear_clip(poly)
    lo = poly.min(0); hi = poly.max(0); ext = np.maximum(hi - lo, 1e-3)
    for y, sgn in ((y1, 1), (y0, -1)):
        c = Mesh()
        c.V = np.stack([poly[:, 0], np.full(n, y), poly[:, 1]], 1)
        c.T = np.stack([(poly[:, 0] - lo[0]) / ext[0], (poly[:, 1] - lo[1]) / ext[1]], 1)
        if sgn < 0: c.T[:, 0] = 1 - c.T[:, 0]
        F = np.array(tris)
        # polygon CCW in (x,z); normal of (x,y,z) tri with y const: cross gives -y for CCW in x-z
        fn = np.cross(c.V[F[:, 1]] - c.V[F[:, 0]], c.V[F[:, 2]] - c.V[F[:, 0]])
        if (fn[:, 1] * sgn).mean() < 0: F = F[:, ::-1]
        c.F = F; c.N = np.tile([0, sgn, 0], (n, 1)).astype(float)
        c.charts = [dict(w=ext[0], h=ext[1], mat=mat)]; c.FC = np.zeros(len(F), np.int64)
        c.parts = [part]; c.FP = np.zeros(len(F), np.int64)
        m.add(c)
    # rim
    loop = np.vstack([poly, poly[:1]])
    P = np.zeros((n + 1, 2, 3))
    P[:, 0] = np.stack([loop[:, 0], np.full(n + 1, y0), loop[:, 1]], 1)
    P[:, 1] = np.stack([loop[:, 0], np.full(n + 1, y1), loop[:, 1]], 1)
    r = surface(P, rim_mat or mat, part)
    cen = np.array([poly[:, 0].mean(), (y0 + y1) / 2, poly[:, 1].mean()])
    fc = r.V[r.F].mean(1) - cen; fc[:, 1] = 0
    if np.einsum('ij,ij->i', r.face_normals(), fc).mean() < 0: r.F = r.F[:, ::-1]
    r.recompute_normals(angle=40)
    m.add(r)
    m.parts = [part]; m.FP[:] = 0
    return m


def offset_poly(poly, d):
    """offset a CCW polygon outward by d (miter)"""
    p = np.asarray(poly, float)
    if poly_area(p) < 0: p = p[::-1]
    n = len(p); out = []
    for i in range(n):
        a, b, c = p[i - 1], p[i], p[(i + 1) % n]
        e1 = b - a; e2 = c - b
        n1 = np.array([e1[1], -e1[0]]); n1 /= np.linalg.norm(n1)
        n2 = np.array([e2[1], -e2[0]]); n2 /= np.linalg.norm(n2)
        bis = n1 + n2; bis /= np.linalg.norm(bis)
        out.append(b + bis * d / max(np.dot(bis, n1), 0.3))
    return np.array(out)


def resample_loop(poly, step):
    p = np.vstack([poly, poly[:1]])
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    n = max(8, int(s[-1] / step))
    t = np.linspace(0, s[-1], n + 1)[:-1]
    return np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], 1), s[-1]


def decal(img_id, origin, u_axis, v_axis, size, lift=0.06, seg=1):
    """flat quad carrying decal image img_id over origin + [0,size0] u + [0,size1] v, lifted along u x v; baked into the prop's alpha-tested
    'decal' atlas (see build_prop: spec['decal_imgs'])"""
    o = np.asarray(origin, float); ua = np.asarray(u_axis, float); va = np.asarray(v_axis, float)
    n = np.cross(ua, va); n /= np.linalg.norm(n)
    s = np.linspace(0, 1, seg + 1)
    P = o + n * lift + s[:, None, None] * ua * size[0] + s[None, :, None] * va * size[1]
    m = surface(P, 'decal', frame())
    m.charts[0]['decal'] = img_id; m.charts[0]['atlas'] = 'decal'
    m.charts[0]['w'] = float(size[0]); m.charts[0]['h'] = float(size[1])
    m.parts[0]['decal_o'] = o + n * lift; m.parts[0]['decal_u'] = ua; m.parts[0]['decal_v'] = va; m.parts[0]['decal_s'] = np.asarray(size, float)
    return m
