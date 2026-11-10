"""Hard-surface PBR maps (painted military metal) for converted models: from a colour map (+ normal map, + any source gloss / spec /
self-illum masks, + optionally the mesh) derive per-pixel roughness, metalness, ambient occlusion, a team-paint tint mask, edge wear
and crevice grime, and a normal map from the albedo when the source has none. Writes csgo_complex vmats.

Used by create/mdl2cs2.py (default on; --plain-mat to opt out) and projects/ironframe-cs2/tools/upgrade_materials.py (rewrites
already converted frames in place). Findings behind the numbers: docs/creation/models.md "Hard-surface materials".

  mb = MeshBake(P, F, UV, N=None)               the whole model once (model units, UV image convention: v from the top):
                                                voxel AO, convex/concave feature edges (dihedral angles), KD-tree of edge samples
  tex = mb.texels(face_ids, size)               one material's faces rasterised: per-texel 3D position, normal, edge, crease, ao
  maps = derive(col, nrm=None, gloss=None, illum=None, texels=None, opts={})   -> dict of uint8 arrays (color, normal?, rough,
                                                metal, ao, tint) + 'notes'
  lines = vmat_lines(...)                       the texture block of a csgo_complex vmat
Everything is deterministic (seeded by the material name).
"""
import math, os, re, zlib
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
import sys
if HERE not in sys.path: sys.path.insert(0, HERE)
import noise                                                    # noqa: E402

DEFAULTS = dict(
    rough_paint=0.50,        # painted armour (CS2 roughness, 0 mirror .. 1 chalk)
    gloss_span=0.30,         # source gloss mask (0..1, stretched to its own contrast) spreads roughness this much around rough_paint
    rough_metal=0.30,        # worn / bare steel
    wear=1.0,                # edge-wear amount (0 off)
    grime=1.0,               # crevice grime amount
    band=1.6,                # edge-wear band half-width in model units (a 288 u mech: ~4 cm)
    chip_scale=2.2,          # object-space chip noise cell (model units)
    steel=(176, 176, 170),   # bare steel albedo (sRGB) where paint is chipped
    retint=0.0,              # 0..1 pull toward the roster palette (gunmetal / off-white / hazard yellow): Tripo colour maps
    albedo_max=0.78,         # linear albedo ceiling (soft knee): white paint ~ sRGB 230, not 255
    min_size=512, max_size=2048,
)

PALETTE = dict(gunmetal=(0.20, 0.215, 0.23), offwhite=(0.80, 0.79, 0.75), hazard=(0.88, 0.66, 0.12))


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)


def srgb2lin(c): c = np.asarray(c, np.float32); return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def lin2srgb(c): c = np.clip(c, 0, 1); return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def fbm2(h, w, seed, cell, octaves=4, gain=0.55):
    """2D value fBm (image space), cell = feature size in pixels; 0..1"""
    rng = np.random.default_rng(seed); out = np.zeros((h, w), np.float32); amp, tot = 1.0, 0.0
    for _ in range(octaves):
        ch, cw = max(2, int(h / cell) + 2), max(2, int(w / cell) + 2)
        im = Image.fromarray(rng.random((ch, cw)).astype(np.float32), 'F').resize((w, h), Image.BICUBIC)
        out += amp * np.asarray(im); tot += amp; amp *= gain; cell = max(1.5, cell / 2)
    out /= tot
    lo, hi = np.percentile(out, 1), np.percentile(out, 99)
    return np.clip((out - lo) / max(1e-6, hi - lo), 0, 1)


def fbm3(P, cell, seed, octaves=4, gain=0.55):
    """object-space fBm at points P (k,3), feature size `cell` model units; 0..1 (continuous across UV charts)"""
    if len(P) == 0: return np.zeros(0, np.float32)
    q = np.asarray(P, np.float32) / cell
    v = noise.fbm(q[:, 0], q[:, 1], q[:, 2], octaves=octaves, gain=gain, seed=seed)
    return np.clip(v * 0.75 + 0.5, 0, 1)


def noise_img(tx, cell, seed, octaves, gain, step, zs=1.0):
    """object-space fBm over a texel bake: evaluated on every `step`-th texel (covered ones only at step 1), upsampled to the map"""
    pos = tx['pos']; H, W = pos.shape[:2]
    if step > 1:
        p = pos[::step, ::step].reshape(-1, 3).copy(); p[:, 2] *= zs
        v = fbm3(p, cell, seed, octaves, gain).reshape(pos[::step, ::step].shape[:2])
        return np.asarray(Image.fromarray(v.astype(np.float32), 'F').resize((W, H), Image.BILINEAR))
    cov = tx['cov']; p = pos[cov].copy(); p[:, 2] *= zs
    out = np.full((H, W), 0.5, np.float32); out[cov] = fbm3(p, cell, seed, octaves, gain)
    return out


# ---------------------------------------------------------------- mesh bake
class _M:
    def __init__(s, V, F): s.V, s.F = V, F
    def bounds(s): return s.V.min(0), s.V.max(0)


def _rasterise(UVpx, F, size_w, size_h, acc=None):
    """per-texel face index (-1 empty) and barycentrics; UVpx in pixels (x right, y down). acc: a list that receives every
    (texel index, face, barycentrics) a face covers (overlapping / re-used UVs: the caller averages over all of them)"""
    face = np.full((size_h, size_w), -1, np.int64); bary = np.zeros((size_h, size_w, 3), np.float32)
    tri = UVpx[F]
    for f in range(len(F)):
        t = tri[f]
        x0 = max(int(np.floor(t[:, 0].min() - 0.5)), 0); x1 = min(int(np.ceil(t[:, 0].max() + 0.5)), size_w - 1)
        y0 = max(int(np.floor(t[:, 1].min() - 0.5)), 0); y1 = min(int(np.ceil(t[:, 1].max() + 0.5)), size_h - 1)
        if x1 < x0 or y1 < y0: continue
        (ax, ay), (bx, by), (cx, cy) = t
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12: continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den
        l1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / den
        l2 = 1 - l0 - l1
        e = 0.7 / max(math.sqrt(abs(den)), 1e-6)
        inside = (l0 >= -e) & (l1 >= -e) & (l2 >= -e)
        strict = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
        yy = ys.astype(int); xx = xs.astype(int)
        take = (inside & (face[yy, xx] < 0)) | strict
        if not take.any(): continue
        L = np.clip(np.stack([l0, l1, l2], -1), 0, None); L /= L.sum(-1, keepdims=True)
        face[yy[take], xx[take]] = f; bary[yy[take], xx[take]] = L[take]
        if acc is not None and strict.any():
            acc.append((yy[strict] * size_w + xx[strict], np.full(int(strict.sum()), f, np.int32), L[strict].astype(np.float32)))
    return face, bary


class MeshBake:
    """the whole model (every material) once: AO volume, feature edges. P (n,3) model units, F (m,3), UV (n,2) image convention."""

    def __init__(s, P, F, UV, N=None, edge_deg=(18.0, 55.0), ao_res=None, log=None):
        s.P = np.asarray(P, np.float64); s.F = np.asarray(F, np.int64); s.UV = np.asarray(UV, np.float64)
        lo, hi = s.P.min(0), s.P.max(0); s.size = float((hi - lo).max())
        s.log = log or (lambda *a: None)
        e1 = s.P[s.F[:, 1]] - s.P[s.F[:, 0]]; e2 = s.P[s.F[:, 2]] - s.P[s.F[:, 0]]
        fn = np.cross(e1, e2); s.area = np.linalg.norm(fn, axis=1) / 2
        s.FN = fn / np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
        s.N = np.asarray(N, np.float64) if N is not None else None
        # AO: voxel occupancy blurred at several scales, sampled off the surface (create/bake.py); resolution from the model size
        res = ao_res or max(0.75, s.size / 160.0)
        import bake
        sc = tuple(x * s.size / 288.0 for x in (3, 6, 12, 24, 40))
        s.occ, s.olo, s.ores = bake.voxel_occupancy(_M(s.P, s.F), res, pad=int(max(sc) / res) + 4)
        s.blur = [(sv, ndimage.gaussian_filter(s.occ, sv / res / 2.0, mode='constant')) for sv in sc]
        s._edges(edge_deg)

    def _edges(s, deg):
        """feature edges by dihedral angle on the position-welded mesh: convex (armour edges) and concave (creases); KD-trees of samples"""
        from scipy.spatial import cKDTree
        q = np.round(s.P / max(1e-3, s.size * 2e-5)).astype(np.int64)
        _, wid = np.unique(q, axis=0, return_inverse=True); wid = wid.ravel()
        WF = wid[s.F]
        ed = np.concatenate([WF[:, [0, 1]], WF[:, [1, 2]], WF[:, [2, 0]]]); fidx = np.tile(np.arange(len(WF)), 3)
        opp = np.concatenate([s.F[:, 2], s.F[:, 0], s.F[:, 1]])
        key = np.sort(ed, 1); kk = key[:, 0] * (wid.max() + 1) + key[:, 1]
        order = np.argsort(kk, kind='stable'); kk = kk[order]
        same = np.nonzero(kk[1:] == kk[:-1])[0]                     # consecutive pairs sharing an edge (manifold pairs)
        a, b = order[same], order[same + 1]
        fa, fb = fidx[a], fidx[b]
        ok = (fa != fb) & (s.area[fa] > 0) & (s.area[fb] > 0)
        a, b, fa, fb = a[ok], b[ok], fa[ok], fb[ok]
        cosang = np.clip((s.FN[fa] * s.FN[fb]).sum(1), -1, 1); ang = np.degrees(np.arccos(cosang))
        # convex when the other face's far corner lies behind this face's plane
        pe = s.P[s.F[fa, 0]]
        side = ((s.P[opp[b]] - pe) * s.FN[fa]).sum(1)
        convex = side < 0
        strength = smooth(deg[0], deg[1], ang) * (ang < 150)          # > 150 deg: back-to-back sheets, not an edge
        # sample points along each edge (every ~0.4 band) with the two face normals
        e_idx = np.stack([np.concatenate([s.F[:, 0], s.F[:, 1], s.F[:, 2]])[a], np.concatenate([s.F[:, 1], s.F[:, 2], s.F[:, 0]])[a]], 1)
        out = {}
        for name, m in (('convex', convex & (strength > 0.05)), ('concave', ~convex & (strength > 0.05))):
            if not m.any(): out[name] = None; continue
            p0, p1 = s.P[e_idx[m, 0]], s.P[e_idx[m, 1]]; L = np.linalg.norm(p1 - p0, axis=1)
            step = max(0.25, s.size / 1200.0)
            n = np.clip(np.ceil(L / step).astype(int), 1, 400)
            rep = np.repeat(np.arange(len(L)), n + 1)
            t = np.concatenate([np.linspace(0, 1, k + 1) for k in n])
            pts = p0[rep] + (p1 - p0)[rep] * t[:, None]
            out[name] = (cKDTree(pts), strength[m][rep].astype(np.float32), s.FN[fa[m]][rep].astype(np.float32), s.FN[fb[m]][rep].astype(np.float32))
            s.log('  %s edges: %d (%d samples)' % (name, int(m.sum()), len(pts)))
        s.edges = out

    def ao_at(s, P, N):
        import bake
        ao = np.zeros(len(P), np.float32); ws = 0.0
        for k, (sv, b) in enumerate(s.blur):
            o = bake.sample(b, s.olo, s.ores, P + N * sv)
            w = 1.0 / (1 + k * 0.35); ao += w * np.clip(o * 2.2, 0, 1); ws += w
        return np.clip(1 - ao / ws, 0, 1)

    def edge_at(s, name, P, N, band):
        e = s.edges.get(name)
        if e is None or not len(P): return np.zeros(len(P), np.float32)
        tree, st, n1, n2 = e
        d, i = tree.query(P, k=1, distance_upper_bound=band * 3.0)
        hit = np.isfinite(d)
        out = np.zeros(len(P), np.float32)
        if hit.any():
            ii = i[hit]; nn = N[hit]
            gate = np.maximum((nn * n1[ii]).sum(1), (nn * n2[ii]).sum(1))     # only the faces that meet at that edge, not a plate behind it
            out[hit] = st[ii] * np.exp(-(d[hit] / band) ** 2) * smooth(0.35, 0.75, gate)
        return out

    def texels(s, face_ids, w, h=None, band=1.6, tiling_ok=False):
        """rasterise the given faces (indices into F) into a w x h texture -> dict(cov, pos, nrm, edge, crease, ao, tiling)
        or None when the UVs tile/repeat (a tiled detail texture has no single place on the mesh)"""
        h = h or w
        F = s.F[face_ids]
        uv = s.UV[F].reshape(-1, 2)
        if not len(uv): return None
        sh = np.floor(np.median(uv, 0) + 1e-6)                        # converters leave whole-tile offsets (v in 1..2): undo them
        uv = uv - sh
        out_frac = float(((uv < -0.02) | (uv > 1.02)).any(1).mean())
        if out_frac > 0.04 and not tiling_ok: return None
        UVpx = np.stack([np.clip(s.UV[:, 0] - sh[0], 0, 1) * w, np.clip(s.UV[:, 1] - sh[1], 0, 1) * h], 1)
        uva = np.abs(np.cross(np.c_[(UVpx[F[:, 1]] - UVpx[F[:, 0]]), np.zeros(len(F))], np.c_[(UVpx[F[:, 2]] - UVpx[F[:, 0]]), np.zeros(len(F))])[:, 2]).sum() / 2
        acc = []
        face, bary = _rasterise(UVpx, F, w, h, acc)
        cov = face >= 0
        if cov.sum() < 16: return None
        reuse = uva / max(1, cov.sum())                 # 1: every texel used once; 2: mirrored halves; more: a texture re-used on many parts
        fi = face[cov]; bb = bary[cov]
        Fc = F[fi]
        pos = (s.P[Fc] * bb[..., None]).sum(1)
        bandv = band * s.size / 288.0
        def masks(fi, bb):
            Fc = F[fi]; p = (s.P[Fc] * bb[..., None]).sum(1); fnv = s.FN[face_ids][fi]
            if s.N is not None:
                nv = (s.N[Fc] * bb[..., None]).sum(1); nv /= np.maximum(np.linalg.norm(nv, axis=1, keepdims=True), 1e-9)
            else: nv = fnv
            return (nv, np.maximum(s.edge_at('convex', p, fnv, bandv), 0), s.edge_at('concave', p, fnv, bandv * 1.6),
                    s.edge_at('convex', p, fnv, bandv * 3.0), s.ao_at(p, nv))
        if reuse > 1.25 and acc:
            # every place on the mesh that uses a texel counts: average the masks (what all the copies agree on survives)
            ti = np.concatenate([a[0] for a in acc]); af = np.concatenate([a[1] for a in acc]); ab = np.concatenate([a[2] for a in acc])
            if len(ti) > 12_000_000:
                k = np.random.default_rng(0).choice(len(ti), 12_000_000, replace=False); ti, af, ab = ti[k], af[k], ab[k]
            nv_, e_, c_, es_, ao_ = masks(af, ab)
            cnt = np.bincount(ti, minlength=w * h).astype(np.float32); ok = cnt[cov.ravel()] > 0
            av = lambda v: (np.bincount(ti, v, minlength=w * h) / np.maximum(cnt, 1))[cov.ravel()]
            nv0, e0, c0, es0, ao0 = masks(fi, bb)
            edge = np.where(ok, av(e_), e0); crease = np.where(ok, av(c_), c0); edge_soft = np.where(ok, av(es_), es0); ao = np.where(ok, av(ao_), ao0)
            nv = nv0
        else:
            nv, edge, crease, edge_soft, ao = masks(fi, bb)
        img = lambda v, fill: _scatter(cov, v, fill)
        import bake as _b
        res = dict(cov=cov, pos=img(pos.astype(np.float32), 0), nrm=img(nv.astype(np.float32), 0), edge=img(edge, 0), crease=img(crease, 0),
                   edge_soft=img(edge_soft, 0), ao=img(ao, 1), scale=s.size / 288.0, reuse=float(reuse))
        # pad the gutters (bilinear / mip sampling must not pull in empty texels)
        keys = ['pos', 'nrm', 'edge', 'crease', 'edge_soft', 'ao']
        dil = _b.dilate(cov, *[res[k] for k in keys])
        for k, v in zip(keys, dil): res[k] = v
        return res


def _scatter(cov, v, fill):
    shp = cov.shape + (v.shape[1:] if v.ndim > 1 else ())
    out = np.full(shp, fill, np.float32); out[cov] = v; return out


# ---------------------------------------------------------------- image-space helpers
def normal_to_grad(n8):
    """OpenGL normal map (uint8 or 0..1 floats) -> slopes (dh/dx right, dh/dy down) in texel units"""
    n = n8.astype(np.float32) / (255.0 if n8.dtype == np.uint8 else 1.0) * 2 - 1
    nz = np.maximum(n[..., 2], 0.2)
    return -n[..., 0] / nz, n[..., 1] / nz          # +green = normal leans toward the image top = height rises down the image


def height_from_grad(gx, gy):
    """Frankot-Chellappa: least-squares height from slopes (periodic), zero mean"""
    h, w = gx.shape
    wx = np.fft.fftfreq(w) * 2 * np.pi; wy = np.fft.fftfreq(h) * 2 * np.pi
    WX, WY = np.meshgrid(wx, wy)
    den = WX ** 2 + WY ** 2; den[0, 0] = 1
    Z = (-1j * WX * np.fft.fft2(gx) - 1j * WY * np.fft.fft2(gy)) / den; Z[0, 0] = 0
    return np.real(np.fft.ifft2(Z)).astype(np.float32)


def grad_to_normal(gx, gy):
    n = np.stack([-gx, gy, np.ones_like(gx)], -1); n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return np.clip((n * 0.5 + 0.5) * 255 + 0.5, 0, 255).astype(np.uint8)


def norm01(x, pct=99.0):
    s = np.percentile(np.abs(x), pct)
    return x / max(s, 1e-6)


def retint(lin, amount, warm_keep=True):
    """pull a linear-RGB colour map toward the roster palette: darks -> gunmetal, lights -> off-white, saturated warm hues ->
    hazard yellow (accents), everything else desaturated; `amount` 0..1 (keep it ~0.3-0.5: the source detail must survive)"""
    if amount <= 0: return lin
    L = lin @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    mx, mn = lin.max(-1), lin.min(-1); sat = (mx - mn) / np.maximum(mx, 1e-4)
    r, g, b = lin[..., 0], lin[..., 1], lin[..., 2]
    warm = (r > b * 1.6) & (g > b * 1.2) & (sat > 0.45) & (mx > 0.2)                 # yellow / orange accents
    t = smooth(0.08, 0.45, L)[..., None]
    base = np.array(PALETTE['gunmetal'], np.float32) * (1 - t) + np.array(PALETTE['offwhite'], np.float32) * t
    tgt = base * (0.55 + 0.9 * np.clip(L / np.maximum(base.mean(-1), 1e-3), 0, 1.6))[..., None] * 0.62
    tgt = np.where(warm[..., None], np.array(PALETTE['hazard'], np.float32) * (0.5 + 0.7 * np.clip(L / 0.45, 0, 1.4))[..., None], tgt)
    a = np.where(warm, amount * 0.8, amount)[..., None]
    return np.clip(lin * (1 - a) + tgt * a, 0, 1)


# ---------------------------------------------------------------- the maps
def derive(col, nrm=None, gloss=None, illum=None, texels=None, seed='mat', opts=None):
    """col (H,W,3) uint8 sRGB; nrm (H,W,3) uint8 OpenGL normal map or None (derived from the albedo); gloss (H,W) 0..1 source shininess
    (phong exponent map / env-map mask) or None; illum (H,W) 0..1 self-illum mask or None; texels: MeshBake.texels() at the output size.
    -> dict(color, normal (only when derived), rough, metal, ao, tint: uint8 arrays at the output size, notes)"""
    o = dict(DEFAULTS); o.update(opts or {})
    sd = zlib.crc32(str(seed).encode()) & 0xffff
    H0, W0 = col.shape[:2]
    if texels is not None: H, W = texels['cov'].shape
    else:
        s = min(o['max_size'], max(o['min_size'], max(H0, W0))) / max(H0, W0); W, H = max(4, int(round(W0 * s))), max(4, int(round(H0 * s)))
    rs = lambda a, mode=Image.BICUBIC: np.asarray(Image.fromarray(a).resize((W, H), mode)) if a.shape[:2] != (H, W) else a
    rsf = lambda a: np.asarray(Image.fromarray(a.astype(np.float32), 'F').resize((W, H), Image.BILINEAR)) if a.shape[:2] != (H, W) else a.astype(np.float32)
    c8 = rs(col[..., :3])
    lin = srgb2lin(c8.astype(np.float32) / 255.0)
    notes = []
    glow = None
    if o.get('auto_glow') and illum is None:
        # colour-only sources (Tripo) paint their sensor lights as bright saturated cyan/blue: make those self-lit, keep their colour
        s8 = c8.astype(np.float32) / 255.0; v = s8.max(-1); sv = (v - s8.min(-1)) / np.maximum(v, 1e-4)
        r_, g_, b_ = s8[..., 0], s8[..., 1], s8[..., 2]
        glow = smooth(0.55, 0.75, v) * smooth(0.45, 0.65, sv) * ((b_ > r_ * 1.4) & (g_ > r_ * 1.2)).astype(np.float32)
        glow = ndimage.grey_opening(glow, size=2)                      # no single stray texels
        if glow.max() > 0.5 and glow.mean() < 0.05: illum = glow; notes.append('auto glow %.1f%%' % (100 * float((glow > 0.5).mean())))
        else: glow = None
    orig = lin.copy()
    kn = o['albedo_max']                                            # soft knee: pure white paint (255) blows out under CS2's sun and hides all detail
    lin = np.where(lin > kn * 0.75, kn * 0.75 + (lin - kn * 0.75) / (1 + (lin - kn * 0.75) / (kn * 0.25)), lin)
    if o['retint'] > 0: lin = retint(lin, o['retint']); notes.append('retint %.2f' % o['retint'])
    if glow is not None: lin = lin * (1 - glow[..., None]) + orig * glow[..., None]
    L = lin @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    mx, mn = lin.max(-1), lin.min(-1); sat = (mx - mn) / np.maximum(mx, 1e-4)
    px = max(W, H) / 1024.0                                         # pixel scale relative to a 1k map
    tx = texels
    cov = tx['cov'] if tx is not None else np.ones((H, W), bool)
    # --- normal: source, else from the albedo (fine high-pass of luminance: panel lines, rivets, scratches)
    derived_n = None
    if nrm is not None:
        n8 = rs(nrm[..., :3])
    else:
        Ls = np.sqrt(np.clip(L, 0, 1))
        hp = ndimage.gaussian_filter(Ls, 0.7 * px) - ndimage.gaussian_filter(Ls, 5.0 * px)
        gx = ndimage.sobel(hp, 1) / 8.0; gy = ndimage.sobel(hp, 0) / 8.0      # dh/dx, dh/drow
        k = 1.0 / max(1e-4, np.percentile(np.hypot(gx, gy), 99))       # the strongest albedo edges -> a ~45 degree slope
        derived_n = grad_to_normal(gx * k, gy * k); n8 = derived_n; notes.append('normal from albedo')
    gx, gy = normal_to_grad(n8)
    # --- image-space curvature (panel lines, grooves, bevels painted into the normal map)
    curv = -(np.gradient(gx, axis=1) + np.gradient(gy, axis=0))           # -laplacian(height): + convex, - concave
    curv = ndimage.gaussian_filter(curv, 0.8 * px)
    curv = norm01(curv, 99.5)
    h = height_from_grad(gx, gy)
    cav_img = np.clip(norm01(ndimage.gaussian_filter(h, 6 * px) - h, 99.0), 0, 1)      # recessed relative to the surroundings
    edge_img = smooth(0.25, 0.8, curv)
    groove = smooth(0.2, 0.7, -curv)
    # --- object-space (mesh) masks when we have them, else image space
    if tx is not None:
        sc = tx['scale']
        n_mottle = noise_img(tx, 40 * sc, sd + 1, 4, 0.55, 4)
        n_grunge = noise_img(tx, 9 * sc, sd + 2, 4, 0.55, 2)
        n_chip = noise_img(tx, o['chip_scale'] * sc, sd + 3, 3, 0.6, 1)
        n_fine = noise_img(tx, 0.7 * sc, sd + 4, 2, 0.55, 1)
        n_streak = noise_img(tx, 2.5 * sc, sd + 5, 3, 0.55, 2, zs=0.12)       # vertical streaks: stretched along z
        up = tx['nrm'][..., 2]
        edge = np.clip(np.maximum(tx['edge'] * 1.0, edge_img * 0.75), 0, 1)
        edge_soft = np.clip(np.maximum(tx['edge_soft'], edge_img * 0.5), 0, 1)
        cav = np.clip(np.maximum(tx['crease'] * 0.9, np.maximum(cav_img * 0.8, groove * 0.6)), 0, 1)
        ao_m = tx['ao']
    else:
        n_mottle = fbm2(H, W, sd + 1, 220 * px); n_grunge = fbm2(H, W, sd + 2, 48 * px)
        n_chip = fbm2(H, W, sd + 3, 9 * px, 3, 0.6); n_fine = fbm2(H, W, sd + 4, 3 * px, 2)
        n_streak = fbm2(H, W, sd + 5, 14 * px, 3); up = np.zeros((H, W), np.float32)
        edge = np.clip(edge_img, 0, 1); edge_soft = ndimage.gaussian_filter(edge, 1.5 * px); cav = np.clip(np.maximum(cav_img * 0.8, groove * 0.6), 0, 1)
        ao_m = np.ones((H, W), np.float32)
    il = np.clip(rsf(illum), 0, 1) if illum is not None else np.zeros((H, W), np.float32)
    gl = np.clip(rsf(gloss), 0, 1) if gloss is not None else None
    # --- paint vs bare metal: dark-to-mid desaturated areas the source marks shiny (or, without a mask, darker greys: joints, pistons)
    greyish = smooth(0.22, 0.08, sat)
    if gl is not None:
        bare = greyish * smooth(0.55, 0.85, gl) * smooth(0.03, 0.08, L) * smooth(0.45, 0.25, L)
    else:
        bare = greyish * smooth(0.02, 0.05, L) * smooth(0.18, 0.08, L) * 0.6
    bare *= (1 - il)
    # --- edge wear: chipped paint on convex edges, broken up by chip noise; a darker primer rim around each chip
    w_amt = o['wear']
    wv = edge * (0.15 + 1.0 * n_chip)
    wear = smooth(0.62, 0.88, wv) * w_amt * (1 - il) * (1 - bare)
    primer = np.clip(smooth(0.45, 0.62, wv) * w_amt * (1 - il) - wear, 0, 1)
    # --- grime: crevices, AO and downward streaks under edges; subtle
    g_amt = o['grime']
    grime = np.clip(cav * (0.45 + 0.8 * n_grunge) * 0.75 + (1 - ao_m) * 0.3 * n_grunge + smooth(0.62, 0.85, n_streak) * 0.18 * (1 - np.abs(up)), 0, 1) * g_amt
    grime *= (1 - il)
    # --- albedo
    out = lin * (0.94 + 0.12 * n_mottle[..., None]) * (0.97 + 0.06 * n_fine[..., None])
    gcol = np.array([0.045, 0.038, 0.030], np.float32)
    out = out * (1 - 0.55 * grime[..., None]) + gcol * 0.55 * grime[..., None] * 0.6
    ao_tot = np.clip(ao_m * (1 - 0.55 * cav), 0.15, 1)
    out *= (0.68 + 0.32 * ao_tot)[..., None]                       # a little AO in the albedo: CS2 only applies the AO map to indirect light
    steel = srgb2lin(np.array(o['steel'], np.float32) / 255.0) * (0.85 + 0.3 * n_fine[..., None]) * (0.45 + 0.55 * smooth(0.02, 0.35, L))[..., None]   # dark gunmetal parts wear to darker steel
    bare_col = np.maximum(out, srgb2lin(0.33) * (0.8 + 0.4 * n_grunge[..., None]))   # bare metal must not be near-black (metal albedo = reflectance)
    out = out * (1 - bare[..., None] * 0.7) + bare_col * bare[..., None] * 0.7
    out = out * (1 + 0.22 * edge_soft * (1 - grime))[..., None]      # handled / sun-faded paint along edges reads lighter
    out = out * (1 - primer[..., None] * 0.45)
    out = out * (1 - wear[..., None]) + steel * wear[..., None]
    out = np.where(il[..., None] > 0.02, lin * (1 - il[..., None]) + lin * il[..., None], out) if illum is not None else out
    # --- roughness
    if gl is not None:
        r0 = o['rough_paint'] + (0.5 - gl) * o['gloss_span']; notes.append('gloss from source mask')
    else:
        r0 = np.full((H, W), o['rough_paint'], np.float32) + 0.06 * (0.5 - L)
    rough = r0 + 0.11 * (n_grunge - 0.5) + 0.05 * (n_fine - 0.5) + 0.16 * cav + 0.16 * grime + 0.05 * smooth(0.5, 0.9, n_streak)
    rough -= 0.07 * edge_soft
    rough = rough * (1 - bare * 0.6) + (o['rough_metal'] + 0.08 * n_grunge) * bare * 0.6
    rough = rough * (1 - wear) + (o['rough_metal'] + 0.10 * (n_chip - 0.5)) * wear
    rough = np.where(il > 0.3, 0.45, rough)
    rough = np.clip(rough, 0.16, 0.95)
    metal = np.clip(np.maximum(bare * 0.75, wear * 0.95), 0, 1)
    tint = np.clip(1 - np.maximum(np.maximum(wear, bare * 0.8), il), 0, 1)
    res = dict(color=(lin2srgb(out) * 255 + 0.5).astype(np.uint8), rough=(rough * 255 + 0.5).astype(np.uint8),
               metal=(metal * 255 + 0.5).astype(np.uint8), ao=(np.clip(ao_tot, 0, 1) * 255 + 0.5).astype(np.uint8),
               tint=(tint * 255 + 0.5).astype(np.uint8), notes=notes,
               stats=dict(wear=float(wear[cov].mean()), metal=float(metal[cov].mean()), rough=float(rough[cov].mean()), bare=float(bare[cov].mean()),
                          mesh=tx is not None))
    if derived_n is not None: res['normal'] = derived_n
    if glow is not None: res['illum'] = (np.clip(il, 0, 1) * 255 + 0.5).astype(np.uint8)
    return res


# ---------------------------------------------------------------- vmat
STRIP = re.compile(r'^\s*(TextureRoughness|g_flMetalness|F_METALNESS_TEXTURE|TextureMetalness|TextureAmbientOcclusion|g_flAmbientOcclusion\w*|'
                   r'F_TINT_MASK|TextureTintMask|F_SPECULAR)\b')


def rewrite_vmat(txt, files):
    """txt: an existing csgo_complex vmat; files: {color, normal?, rough, metal, ao, tint} addon-relative paths -> new text.
    Keeps the comment, shader, tint, alpha test / translucency / backfaces and self-illum lines; replaces the PBR inputs."""
    lines = txt.rstrip().split('\n')
    keep = [l for l in lines if not STRIP.match(l)]
    out = []
    for l in keep:
        if re.match(r'^\s*TextureColor\b', l): l = '\tTextureColor "%s"' % files['color']
        elif re.match(r'^\s*TextureNormal\b', l) and files.get('normal'): l = '\tTextureNormal "%s"' % files['normal']
        out.append(l)
    close = max(i for i, l in enumerate(out) if l.strip() == '}')
    sh = next((i for i, l in enumerate(out) if l.strip().startswith('shader')), 1)
    out[sh + 1:sh + 1] = ['\tF_SPECULAR 1', '\tF_METALNESS_TEXTURE 1', '\tF_TINT_MASK 1']
    close += 3
    add = ['\tTextureRoughness "%s"' % files['rough'], '\tTextureMetalness "%s"' % files['metal'],
           '\tg_flAmbientOcclusionDirectDiffuse "0.000"', '\tg_flAmbientOcclusionDirectSpecular "0.000"',
           '\tTextureAmbientOcclusion "%s"' % files['ao'], '\tTextureTintMask "%s"' % files['tint']]
    if not any(re.match(r'^\s*g_flModelTintAmount', l) for l in out): add.append('\tg_flModelTintAmount "1.000"')
    if files.get('illum') and not any('F_SELF_ILLUM' in l for l in out):      # auto-glow (sensor lights painted into a colour-only map)
        add += ['\tF_SELF_ILLUM 1', '\tTextureSelfIllumMask "%s"' % files['illum'], '\tg_flSelfIllumScale "1.000"',
                '\tg_flSelfIllumBrightness "3.000"', '\tg_flSelfIllumAlbedoFactor "1.000"']
    out[close:close] = add
    return '\n'.join(out) + '\n'


def is_upgraded(txt):
    return 'TextureTintMask' in txt and 'TextureAmbientOcclusion' in txt


# ---------------------------------------------------------------- shared drivers (mdl2cs2.py and the project upgrade tools)
def gloss_from_vmt(prm, tex_of, shape):
    """0..1 shininess from a Source 1 material's masks, at `shape` (None if it has none). prm: VMT params (lower-case keys);
    tex_of(key) -> RGBA uint8 array or None. Phong exponent map, normal-map alpha / base alpha / separate env-map mask: their mean,
    stretched to the mask's own contrast (absolute levels differ wildly between packs)."""
    g = lambda k: str(prm.get(k, '')).strip('"').strip()
    rs = lambda a: np.asarray(Image.fromarray(np.ascontiguousarray(a)).resize((shape[1], shape[0]), Image.BILINEAR), np.float32) / 255.0
    parts, how = [], []
    ex = tex_of('$phongexponenttexture') if g('$phong') == '1' else None
    if ex is not None: parts.append(rs(ex[..., 0])); how.append('exponent')
    if g('$normalmapalphaenvmapmask') == '1':
        n = tex_of('$bumpmap') if prm.get('$bumpmap') else tex_of('$normalmap')
        if n is not None and n.ndim == 3 and n.shape[-1] == 4 and n[..., 3].min() < 250: parts.append(rs(n[..., 3])); how.append('normal alpha')
    em = tex_of('$envmapmask') if prm.get('$envmapmask') else None
    if em is not None: parts.append(rs(em[..., :3].mean(2).astype(np.uint8))); how.append('env mask')
    if g('$basealphaenvmapmask') == '1':
        b = tex_of('$basetexture')
        if b is not None and b.ndim == 3 and b.shape[-1] == 4: parts.append(rs(255 - b[..., 3])); how.append('base alpha')
    if not parts: return None, 'no masks'
    gl = np.mean(parts, 0)
    lo, hi = np.percentile(gl, 2), np.percentile(gl, 98)
    if hi - lo > 0.08: gl = np.clip((gl - lo) / (hi - lo), 0, 1)
    else: gl = np.full(gl.shape, 0.5, np.float32)
    return gl.astype(np.float32), '+'.join(how)


def upgrade_set(out_root, items, mesh=None, opts=None, cap=2048, log=None):
    """items: [dict(vmat=addon-relative vmat path, col=RGB uint8, nrm=RGB uint8 OpenGL or None, gloss=HxW 0..1 or None,
    illum=HxW 0..1 or None, faces=face indices into mesh F or None)]; mesh: (P, F, UV image-convention, N or None) of the whole model.
    Writes <stem>_color/_rough/_metal/_ao/_tint(/_nrmd).png beside each vmat and rewrites the vmat (translucent ones are left alone).
    -> {stem: report}"""
    log = log or (lambda *a: None)
    mb = None
    if mesh is not None and len(mesh[1]):
        try: mb = MeshBake(mesh[0], mesh[1], mesh[2], mesh[3], log=log)
        except Exception as e: log('  mesh bake skipped: %s' % e)
    rep = {}
    for it in items:
        rel = it['vmat']; vp = os.path.join(out_root, rel.replace('/', os.sep)); d = os.path.dirname(vp)
        stem = os.path.basename(rel)[:-5]; rd = rel.rsplit('/', 1)[0]
        txt = open(vp, encoding='utf-8').read()
        if 'F_TRANSLUCENT 1' in txt: rep[stem] = 'translucent: unchanged'; continue
        col = it['col']; H0, W0 = col.shape[:2]
        s = min(cap, max(512, max(H0, W0))) / max(H0, W0); W, H = int(round(W0 * s)), int(round(H0 * s))
        tex = None
        if mb is not None and it.get('faces') is not None and len(it['faces']):
            try: tex = mb.texels(np.asarray(it['faces']), W, H)
            except Exception as e: log('  %s: texel bake failed (%s), image-space masks' % (stem, e))
        mp = derive(col, it.get('nrm'), it.get('gloss'), it.get('illum'), tex, seed=it.get('seed', rel), opts=opts)
        files = {}
        for key, suf, mode in (('color', 'color', 'RGB'), ('rough', 'rough', 'L'), ('metal', 'metal', 'L'), ('ao', 'ao', 'L'), ('tint', 'tint', 'L'),
                               ('normal', 'nrmd', 'RGB'), ('illum', 'illum', 'L')):
            if key not in mp: continue
            fn = '%s_%s.png' % (stem, suf); Image.fromarray(mp[key]).convert(mode).save(os.path.join(d, fn), optimize=True)
            files[key] = '%s/%s' % (rd, fn)
        open(vp, 'w', newline='\n').write(rewrite_vmat(txt, files))
        for old in os.listdir(d):                                   # flat roughness swatches the vmat no longer uses
            if re.match(re.escape(stem) + r'_rough\d+\.png$', old): os.remove(os.path.join(d, old))
        st = mp['stats']
        rep[stem] = dict(size=[W, H], gloss=it.get('gloss_how', 'none'), mesh=st['mesh'], wear=round(st['wear'], 3), metal=round(st['metal'], 3),
                         rough=round(st['rough'], 3), notes=mp['notes'])
        log('  %-32s %4dx%-4d gloss=%-22s mesh=%-5s wear %.3f metal %.3f rough %.2f %s' % (stem[:32], W, H, it.get('gloss_how', 'none')[:22], st['mesh'],
                                                                                         st['wear'], st['metal'], st['rough'], ','.join(mp['notes'])))
    return rep
