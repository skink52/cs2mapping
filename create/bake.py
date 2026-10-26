"""Object-space PBR baker: packs a mesh's charts into an atlas, rasterises every chart texel to its 3D point,
runs procedural material shaders there, bakes voxel ambient occlusion / edge / cavity masks, converts shader
height to a tangent-space (OpenGL, +Y up) normal map, and pads the gutters.
"""
import numpy as np
from scipy import ndimage

GUTTER = 3


def pack(charts, size, fill=0.82):
    """shelf-pack charts (w,h in units) into size x size; returns (density px/unit, rects[x,y,w,h])"""
    area = sum(c['w'] * c['h'] for c in charts)
    d = np.sqrt(fill * size * size / max(area, 1e-6))
    for _ in range(60):
        rects = [None] * len(charts)
        dims = [(max(2, int(np.ceil(c['w'] * d))), max(2, int(np.ceil(c['h'] * d)))) for c in charts]
        # rotate nothing; sort by height
        order = sorted(range(len(charts)), key=lambda i: -dims[i][1])
        x = y = 0; shelf = 0; ok = True
        for i in order:
            w, h = dims[i]
            W, Hh = w + 2 * GUTTER, h + 2 * GUTTER
            if W > size:
                ok = False; break
            if x + W > size:
                x = 0; y += shelf; shelf = 0
            if y + Hh > size:
                ok = False; break
            rects[i] = (x + GUTTER, y + GUTTER, w, h)
            x += W; shelf = max(shelf, Hh)
        if ok: return d, rects
        d *= 0.96
    raise RuntimeError('pack failed')


def atlas_uv(mesh, rects, size):
    """per-vertex atlas uv (u, v_img) with v_img measured from the top"""
    vchart = np.zeros(len(mesh.V), np.int64)
    vchart[mesh.F.ravel()] = np.repeat(mesh.FC, 3)
    R = np.array(rects, float)
    u = (R[vchart, 0] + mesh.T[:, 0] * R[vchart, 2]) / size
    v = (R[vchart, 1] + mesh.T[:, 1] * R[vchart, 3]) / size
    return np.stack([u, v], 1)


def rasterise(mesh, uv, size):
    """returns per-texel buffers: face index (-1 empty) and barycentrics"""
    face = np.full((size, size), -1, np.int64)
    bary = np.zeros((size, size, 3), np.float32)
    P = uv * size
    tri = P[mesh.F]                     # (m,3,2)
    for f in range(len(mesh.F)):
        t = tri[f]
        x0 = int(np.floor(t[:, 0].min() - 0.5)); x1 = int(np.ceil(t[:, 0].max() + 0.5))
        y0 = int(np.floor(t[:, 1].min() - 0.5)); y1 = int(np.ceil(t[:, 1].max() + 0.5))
        x0 = max(x0, 0); y0 = max(y0, 0); x1 = min(x1, size - 1); y1 = min(y1, size - 1)
        if x1 < x0 or y1 < y0: continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = t
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12: continue
        l0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den
        l1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / den
        l2 = 1 - l0 - l1
        # conservative: allow a little outside, but only claim texels nobody owns yet
        e = 0.6 / max(np.sqrt(abs(den)), 1e-6)
        inside = (l0 >= -e) & (l1 >= -e) & (l2 >= -e)
        strict = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
        yy = ys.astype(int); xx = xs.astype(int)
        cur = face[yy, xx]
        take = (inside & (cur < 0)) | strict
        if not take.any(): continue
        L = np.stack([l0, l1, l2], -1)
        L = np.clip(L, 0, None); L /= L.sum(-1, keepdims=True)
        face[yy[take], xx[take]] = f
        bary[yy[take], xx[take]] = L[take]
    return face, bary


def voxel_occupancy(mesh, res, pad=8, ground=None):
    lo, hi = mesh.bounds()
    lo = lo - pad * res; hi = hi + pad * res
    dims = np.ceil((hi - lo) / res).astype(int) + 1
    occ = np.zeros(dims, bool)
    A, B, C = mesh.V[mesh.F[:, 0]], mesh.V[mesh.F[:, 1]], mesh.V[mesh.F[:, 2]]
    area = np.linalg.norm(np.cross(B - A, C - A), axis=1) / 2
    n = np.clip(np.ceil(np.sqrt(area) / (res * 0.4)).astype(int), 1, 64)
    for k in np.unique(n):
        sel = n == k
        a, b, c = A[sel], B[sel], C[sel]
        g = np.linspace(0, 1, k + 1)
        uu, vv = np.meshgrid(g, g); m = (uu + vv) <= 1.0001
        uu = uu[m]; vv = vv[m]
        pts = a[:, None] + (b - a)[:, None] * uu[None, :, None] + (c - a)[:, None] * vv[None, :, None]
        idx = np.floor((pts.reshape(-1, 3) - lo) / res).astype(int)
        idx = np.clip(idx, 0, dims - 1)
        occ[idx[:, 0], idx[:, 1], idx[:, 2]] = True
    occ = ndimage.binary_fill_holes(occ)
    occ = occ.astype(np.float32)
    if ground is not None:
        gz = int(np.floor((ground - lo[2]) / res))
        if gz > 0: occ[:, :, :max(0, min(gz, dims[2]))] = 1.0
    return occ, lo, res


def sample(vol, lo, res, pts):
    c = ((pts - lo) / res).T
    return ndimage.map_coordinates(vol, c, order=1, mode='nearest')


def masks(mesh, P, N, res=1.0, ground=None, scales=(1.5, 3, 6, 12, 24)):
    occ, lo, res = voxel_occupancy(mesh, res, pad=int(max(scales) / res) + 4, ground=ground)
    ao = np.zeros(len(P), np.float32)
    wsum = 0
    for k, s in enumerate(scales):
        sig = s / res / 2.0
        b = ndimage.gaussian_filter(occ, sig, mode='constant')
        o = sample(b, lo, res, P + N * s)
        w = 1.0 / (1 + k * 0.35)
        ao += w * np.clip(o * 2.2, 0, 1); wsum += w
    ao = 1 - ao / wsum
    b1 = ndimage.gaussian_filter(occ, max(0.8, 0.8 / res), mode='constant')
    c = sample(b1, lo, res, P)
    edge = np.clip((0.5 - c) / 0.22, 0, 1)
    cav = np.clip((c - 0.5) / 0.22, 0, 1)
    return np.clip(ao, 0, 1), edge, cav


def height_to_normal(h, d, strength=1.0):
    """h in units (H,W); d px per unit. OpenGL convention (+green = +V = up the image)."""
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5 * d * strength
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5 * d * strength
    n = np.stack([-gx, gy, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n


def dilate(mask, *bufs):
    _, (iy, ix) = ndimage.distance_transform_edt(~mask, return_indices=True)
    return [b[iy, ix] for b in bufs]


class Ctx:
    """texel context handed to shaders (all arrays length k)"""
    def __init__(self, **kw):
        self.__dict__.update(kw)


def bake(mesh, shaders, size=1024, res=None, ground=None, fill=0.8, normal_strength=1.0, atlas_charts=None, verbose=True):
    charts = mesh.charts
    d, rects = pack(charts, size, fill)
    uv = atlas_uv(mesh, rects, size)
    face, bary = rasterise(mesh, uv, size)
    mask = face >= 0
    fi = face[mask]; b = bary[mask]
    Fv = mesh.F[fi]
    P = (mesh.V[Fv] * b[..., None]).sum(1)
    N = (mesh.N[Fv] * b[..., None]).sum(1); N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-9
    T = (mesh.T[Fv] * b[..., None]).sum(1)
    ch = mesh.FC[fi]; pt = mesh.FP[fi]
    A = (mesh.A[Fv] * b[..., None]).sum(1) if getattr(mesh, 'A', None) is not None else None   # extra vertex attributes
    W = np.array([[c['w'], c['h']] for c in charts])
    S = T * W[ch]
    # part-local coordinates
    L = np.zeros_like(P)
    for k, p in enumerate(mesh.parts):
        sel = pt == k
        if sel.any(): L[sel] = (P[sel] - p['o']) @ p['R']
    lo, hi = mesh.bounds()
    if res is None: res = max(0.5, float(np.max(hi - lo)) / 160.0)
    ao, edge, cav = masks(mesh, P, N, res=res, ground=ground)
    k = len(P)
    col = np.zeros((k, 3), np.float32); rough = np.full(k, 0.8, np.float32); metal = np.zeros(k, np.float32); hgt = np.zeros(k, np.float32)
    mats = np.array([charts[c]['mat'] for c in ch])
    for name in np.unique(mats):
        idx_all = np.nonzero(mats == name)[0]
        for c0 in range(0, len(idx_all), 600000):          # chunked: procedural shaders allocate many temporaries per texel
            sel = idx_all[c0:c0 + 600000]
            ctx = Ctx(P=P[sel], N=N[sel], S=S[sel], L=L[sel], part=pt[sel], chart=ch[sel], ao=ao[sel], edge=edge[sel], cav=cav[sel],
                      parts=mesh.parts, lo=lo, hi=hi, n=len(sel), d=d, chart_info=charts, A=A[sel] if A is not None else None)
            out = shaders[name](ctx)
            col[sel] = out['color']; rough[sel] = out.get('rough', 0.8); metal[sel] = out.get('metal', 0.0); hgt[sel] = out.get('height', 0.0)
    def img(vals, ch_):
        im = np.zeros((size, size, ch_) if ch_ > 1 else (size, size), np.float32)
        im[mask] = vals
        return im
    C = img(col, 3); Rr = img(rough, 1); M = img(metal, 1); Hh = img(hgt, 1); A = img(ao, 1)
    C, Rr, M, Hh, A = dilate(mask, C, Rr, M, Hh, A)
    # height gradients must not cross chart borders: blur slightly then derive normals
    Nm = height_to_normal(ndimage.gaussian_filter(Hh, 0.6), d, normal_strength)
    if verbose: print('  baked %d texels, density %.2f px/unit' % (k, d))
    return dict(color=C, rough=Rr, metal=M, normal=Nm, ao=A, uv=uv, density=d, mask=mask)
