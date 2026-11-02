"""Re-textures the converted aircraft (plane_spad7 / plane_dr1) as one weathered PBR atlas.

The Sketchfab sources are clean toy-like colours on ~50 materials, yawed ~30 degrees off the model axis. This:
  1. rotates the model so the nose points at +x (Source convention) and centres it over the origin,
  2. splits every material into planar charts and packs them into one unique atlas,
  3. bakes, per texel: the original colour (sampled through the original uv), CS2 HD detail (cloth weave, wood grain,
     metal grain sampled triplanar from the game textures) and object-space wear: castor-oil spray and exhaust soot
     streaming back from the engine, mud flung up by the wheels onto the undersides, sun-faded upper surfaces,
     chipped leading edges, grime in creases, doped repair patches over bullet holes, worn bare metal on edges,
  4. writes one SMD material (+ colour/normal/roughness/metalness/ao), compound physics hulls, both vmdls.
usage: weather_ext.py [plane_spad7] [plane_dr1]"""
import os, sys, re, json, math
import numpy as np
from PIL import Image
import geo, bake, modelio, render
import ext_smd as E
from noise import fbm, smoothstep, hash01
import vtexread as V

OUT = E.ADDON
PREV = os.path.join(os.path.dirname(__file__), '..', 'preview')

# per aircraft: material roles (others are classified from their colour), fuselage + wheel materials for the axis, engine x
CFG = {
    'plane_spad7': dict(
        fuselage='m40', wheels='m27', engine='inline',
        wood=['m17', 'm18', 'm19', 'm20', 'm21', 'm24', 'm25', 'm39'], rubber=['m27'], leather=['m14'], glass=['m15'],
        pilot=['m44', 'm43', 'm42', 'm50', 'm51', 'm9', 'm45', 'm46', 'm47', 'm48', 'm49'],
        recolour={'m51': (0.24, 0.17, 0.11), 'm43': (0.33, 0.25, 0.17), 'm42': (0.30, 0.22, 0.15)},
        wings=['m52', 'm16'], tail=['m33', 'm31', 'm34', 'm32', 'm28', 'm41'],
        metal=['m0'], drop=['m39'], prop=dict(blades=2, src='m39', colour=(0.30, 0.17, 0.08))),
    'plane_dr1': dict(
        fuselage='m0', wheels='m36', engine='rotary',
        wood=['m15', 'm29'], rubber=['m36'], leather=['m17', 'm22'], glass=[],
        pilot=['m21', 'm20', 'm27', 'm24', 'm23', 'm26', 'm25', 'm37'],
        recolour={'m20': (0.30, 0.24, 0.17)},
        wings=['m18', 'm34', 'm3', 'm35', 'm4', 'm32', 'm33'], tail=['m19', 'm5', 'm6'],
        metal=['m9', 'm16'], drop=[], prop=None),
}


# ---------------------------------------------------------------- HD detail textures from the game files
_DET = {}


def detail(key, vtex, size=512):
    if key not in _DET:
        im = V.decode_vtex(V.vpk_read(vtex + '.vtex_c'), 0).convert('RGB').resize((size, size), Image.LANCZOS)
        a = np.asarray(im, np.float32) / 255.0
        lum = a.mean(-1)
        _DET[key] = dict(rgb=a, lum=lum / max(lum.mean(), 1e-3))
    return _DET[key]


def tri_sample(img, P, N, S, axis_bias=None):
    """triplanar sample of a (H,W) or (H,W,C) tiling image at model points P (k,3), S units per tile"""
    H, W = img.shape[:2]
    w = np.abs(N) ** 4; w /= w.sum(1, keepdims=True) + 1e-9
    out = 0
    for ax, (a, b) in enumerate(((1, 2), (0, 2), (0, 1))):
        u = P[:, a] / S; v = P[:, b] / S
        px = (np.floor(u * W).astype(int)) % W; py = (np.floor(v * H).astype(int)) % H
        s = img[py, px]
        out = out + (s * w[:, ax] if s.ndim == 1 else s * w[:, ax, None])
    return out


def sample_img(img, uv):
    """bilinear sample of img (H,W,3) at uv (k,2) in SMD convention (v up), wrapping"""
    H, W = img.shape[:2]
    x = uv[:, 0] * W - 0.5; y = (1 - uv[:, 1]) * H - 0.5
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int); fx = (x - x0)[:, None]; fy = (y - y0)[:, None]
    def g(yy, xx): return img[yy % H, xx % W]
    return (g(y0, x0) * (1 - fx) * (1 - fy) + g(y0, x0 + 1) * fx * (1 - fy) + g(y0 + 1, x0) * (1 - fx) * fy + g(y0 + 1, x0 + 1) * fx * fy)


# ---------------------------------------------------------------- geometry: orientation, charts
def orient(mats, cfg, name):
    """angle (deg) that turns the model nose to +x, plus the xy offset that centres it"""
    def hpts(m):
        P = mats['%s_%s' % (name, m)]['P'].reshape(-1, 3); return np.stack([-P[:, 1], P[:, 0], P[:, 2]], 1)
    F = hpts(cfg['fuselage']); c = F[:, :2].mean(0)
    _, _, vt = np.linalg.svd(F[:, :2] - c, full_matrices=False); ax = vt[0]
    wc = hpts(cfg['wheels'])[:, :2].mean(0)
    if (wc - c) @ ax < 0: ax = -ax                     # the wheels sit forward of the fuselage centroid
    return -math.degrees(math.atan2(ax[1], ax[0]))


def build_mesh(mats, name, yaw, cfg):
    """geo.Mesh in hammer coords, nose +x; one chart per planar patch; A = original uv; chart src = material"""
    R = geo.rot('z', yaw)
    allP = np.vstack([np.stack([-g['P'][..., 1], g['P'][..., 0], g['P'][..., 2]], -1).reshape(-1, 3) for g in mats.values()]) @ R.T
    lo, hi = allP.min(0), allP.max(0)
    off = np.array([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])
    m = geo.Mesh()
    Vs, Ns, As, Fs, FCs, charts = [], [], [], [], [], []
    nv = 0
    dropped = {}
    for mname, g in mats.items():
        short = mname[len(name) + 1:]
        P = np.stack([-g['P'][..., 1], g['P'][..., 0], g['P'][..., 2]], -1) @ R.T + off       # (n,3,3)
        if short in cfg.get('drop', []):
            dropped[short] = P.reshape(-1, 3); continue
        N = np.stack([-g['N'][..., 1], g['N'][..., 0], g['N'][..., 2]], -1) @ R.T
        fn = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); ar = np.linalg.norm(fn, axis=1)
        fn = fn / np.maximum(ar, 1e-12)[:, None]
        # adjacency through shared (welded) edges
        key = np.round(P.reshape(-1, 3) / 0.02).astype(np.int64)
        _, vid = np.unique(key, axis=0, return_inverse=True); vid = vid.reshape(-1, 3)
        edges = {}
        for t in range(len(vid)):
            for a, b in ((0, 1), (1, 2), (2, 0)):
                e = (min(vid[t, a], vid[t, b]), max(vid[t, a], vid[t, b]))
                edges.setdefault(e, []).append(t)
        nb = [[] for _ in range(len(vid))]
        for ts in edges.values():
            if len(ts) == 2: nb[ts[0]].append(ts[1]); nb[ts[1]].append(ts[0])
        chart_of = -np.ones(len(vid), int)
        order = np.argsort(-ar)
        for seed in order:
            if chart_of[seed] >= 0: continue
            cid = len(charts); chart_of[seed] = cid
            n0 = fn[seed].copy(); acc = fn[seed] * ar[seed]; stack = [seed]; members = [seed]
            ext_lo = P[seed].min(0); ext_hi = P[seed].max(0)
            while stack:
                t = stack.pop()
                for u in nb[t]:
                    if chart_of[u] >= 0 or fn[u] @ n0 < 0.82: continue
                    nlo = np.minimum(ext_lo, P[u].min(0)); nhi = np.maximum(ext_hi, P[u].max(0))
                    if (nhi - nlo).max() > 260: continue
                    chart_of[u] = cid; members.append(u); stack.append(u); ext_lo, ext_hi = nlo, nhi
                    acc = acc + fn[u] * ar[u]; n0 = acc / (np.linalg.norm(acc) + 1e-12)
            mem = np.array(members)
            # planar projection on the chart's mean normal, tangent along +x where possible (wood grain / airflow)
            t1 = np.array([1.0, 0, 0]) - n0 * n0[0]
            if np.linalg.norm(t1) < 0.3: t1 = np.array([0, 1.0, 0]) - n0 * n0[1]
            t1 /= np.linalg.norm(t1); t2 = np.cross(n0, t1)
            Q = P[mem].reshape(-1, 3)
            u = Q @ t1; v = Q @ t2
            # minimum-area bounding rectangle (search the hull edge directions)
            uv2 = np.stack([u, v], 1)
            if len(uv2) >= 6:
                try:
                    from scipy.spatial import ConvexHull
                    hv = uv2[ConvexHull(uv2).vertices]
                    ev = np.diff(np.vstack([hv, hv[:1]]), axis=0); angs = np.arctan2(ev[:, 1], ev[:, 0])
                    best = None
                    for a_ in angs:
                        ca, sa = np.cos(a_), np.sin(a_)
                        ru = hv @ [ca, sa]; rv = hv @ [-sa, ca]
                        ar_ = (ru.max() - ru.min()) * (rv.max() - rv.min())
                        if best is None or ar_ < best[0]: best = (ar_, ca, sa)
                    _, ca, sa = best
                    u, v = uv2 @ [ca, sa], uv2 @ [-sa, ca]
                except Exception:
                    pass
            u0, v0 = u.min(), v.min(); w = max(u.max() - u0, 0.05); h = max(v.max() - v0, 0.05)
            T = np.stack([(u - u0) / w, (v - v0) / h], 1)
            if h > w: T = T[:, ::-1].copy(); w, h = h, w
            Vs.append(Q); Ns.append(N[mem].reshape(-1, 3)); As.append(g['UV'][mem].reshape(-1, 2)); T_ = T
            Fs.append(np.arange(len(Q)).reshape(-1, 3) + nv); FCs.append(np.full(len(mem), cid))
            charts.append(dict(w=float(w), h=float(h), mat=role(short, cfg, mname, name), src=mname))
            m.T = T_ if not hasattr(m, '_Tl') else m.T
            m._Tl = getattr(m, '_Tl', []) + [T_]
            nv += len(Q)
    m.V = np.vstack(Vs); m.N = np.vstack(Ns); m.N /= np.linalg.norm(m.N, axis=1, keepdims=True) + 1e-9
    m.T = np.vstack(m._Tl); del m._Tl
    m.A = np.vstack(As); m.F = np.vstack(Fs); m.FC = np.concatenate(FCs); m.charts = charts
    m.parts = [geo.frame()]; m.FP = np.zeros(len(m.F), np.int64)
    if cfg.get('prop') and cfg['prop']['src'] in dropped:
        add_prop(m, dropped[cfg['prop']['src']], cfg['prop'], name)
    return m, off, R


def add_prop(m, disc, pc, name):
    """replaces the source's propeller-blur disc with real laminated blades + hub (prop axis = x)"""
    c = disc.mean(0); Rr = (disc[:, 2].max() - disc[:, 2].min()) / 2 * 0.98
    c[1] = (disc[:, 1].max() + disc[:, 1].min()) / 2; c[2] = (disc[:, 2].max() + disc[:, 2].min()) / 2
    nr, ns = 14, 12
    rr = np.linspace(4.0, Rr, nr + 1)
    s_ = rr / Rr
    chord = 4.2 + 7.5 * np.sin(np.clip(s_, 0, 1) * np.pi * 0.62) ** 1.2 * (1 - 0.55 * np.clip((s_ - 0.8) / 0.2, 0, 1) ** 2)
    thick = 2.8 * (1 - s_) + 0.55
    twist = np.radians(38 - 26 * s_)
    t = np.linspace(0, 2 * np.pi, ns + 1)
    for b in range(pc['blades']):
        ang = 2 * np.pi * b / pc['blades'] + 0.35
        er = np.array([0, np.cos(ang), np.sin(ang)]); et = np.cross([1.0, 0, 0], er)
        P = np.zeros((nr + 1, ns + 1, 3))
        for i in range(nr + 1):
            cx = chord[i] / 2 * np.cos(t); cz = thick[i] / 2 * np.sin(t) * (1 + 0.35 * np.cos(t))      # flat-backed airfoil
            a_, b_ = cx * np.cos(twist[i]) - cz * np.sin(twist[i]), cx * np.sin(twist[i]) + cz * np.cos(twist[i])
            P[i] = c + er * rr[i] + np.outer(a_, et) + np.outer(b_, [1.0, 0, 0])
        bl = geo.surface(P, 'wood', geo.frame(), closed_v=True)
        bl.charts[0]['w'] = float(chord.max() * 2.2); bl.charts[0]['h'] = float(Rr)
        bl.charts[0]['src'] = '%s_prop' % name
        fn = bl.face_normals(); cen = bl.V[bl.F].mean(1)
        axp = c + er * ((cen - c) @ er)[:, None]
        if ((cen - axp) * fn).sum(1).mean() < 0: bl.F = bl.F[:, ::-1].copy()
        bl.recompute_normals()
        nA = len(m.V); m.add(bl); m.A = np.vstack([m.A, np.zeros((len(m.V) - nA, 2))])
    hub = geo.lathe([(0.01, -5), (5.5, -5), (6.0, -3), (6.0, 3), (4.5, 5), (0.01, 6)], 16, 'metal', geo.frame())
    hub.transform(geo.rot('y', 90), c)
    hub.charts[0]['src'] = '%s_hub' % name
    nA = len(m.V); m.add(hub); m.A = np.vstack([m.A, np.zeros((len(m.V) - nA, 2))])


_ROLE = {}


def role(short, cfg, mname, name):
    for r in ('wood', 'rubber', 'leather', 'glass', 'pilot', 'metal'):
        if short in cfg[r]: return r
    tp = E.vmat_tex(name, mname)
    im = np.asarray(Image.open(os.path.join(SRC, tp)).convert('RGB'), np.float32) / 255
    c = im.reshape(-1, 3).mean(0)
    if im.shape[0] > 8 or (c.max() - c.min()) > 0.12 or c.mean() > 0.9: return 'fabric'
    return 'metal'


# ---------------------------------------------------------------- shading
def make_shaders(name, cfg, mesh):
    rng = np.random.RandomState(7 if name.endswith('spad7') else 11)
    lo, hi = mesh.bounds()
    nose = hi[0]; L = hi[0] - lo[0]
    srcimg = {}
    def src_col(ctx):
        out = np.zeros((ctx.n, 3), np.float32)
        srcs = np.array([ctx.chart_info[c]['src'] for c in ctx.chart])
        for s in np.unique(srcs):
            sel = srcs == s
            short = s[len(name) + 1:]
            if short in cfg['recolour']:
                out[sel] = cfg['recolour'][short]; continue
            if short == 'prop': out[sel] = cfg['prop']['colour']; continue
            if short == 'hub': out[sel] = (0.35, 0.35, 0.34); continue
            if s not in srcimg:
                srcimg[s] = np.asarray(Image.open(os.path.join(SRC, E.vmat_tex(name, s))).convert('RGB'), np.float32) / 255.0
            out[sel] = sample_img(srcimg[s], ctx.A[sel])
        return out

    cloth = detail('cloth', 'materials/pbr_defaults/default_cloth001_color_psd_e8be67f8')
    mtl = detail('metal', 'materials/de_mirage/metal/metal_basic_1_color_tga_c231a254')
    try:
        k = [x for x in V.index() if 'hrts2_wood_floor_boards_02_color' in x and x.endswith('.vtex_c')][0][:-7]
        wood = detail('wood', k)
    except Exception:
        wood = mtl
    grime = detail('grime', 'materials/de_overpass/buildings/roof_metal_painted_1_a_color_tga_edd9ab08')

    # repair patches over bullet holes: centres on upper/side fabric of wings and fuselage
    patches = [(np.array([rng.uniform(lo[0] + 20, hi[0] - 40), rng.uniform(lo[1] + 15, hi[1] - 15), 0.0]), rng.uniform(3.5, 7.0), rng.uniform(0, np.pi)) for _ in range(14)]
    holes = [(np.array([rng.uniform(lo[0] + 20, hi[0] - 30), rng.uniform(lo[1] + 10, hi[1] - 10)]), rng.uniform(0.35, 0.6)) for _ in range(26)]

    wsel = np.isin(np.array([c['src'] for c in mesh.charts])[mesh.FC], ['%s_%s' % (name, cfg['wheels'])])
    WV = mesh.V[mesh.F[wsel].ravel()]
    WX, WY = float(WV[:, 0].mean()), float(np.abs(WV[:, 1]).max())

    def wear(ctx, col, rough, metal, hgt, kind):
        P, N = ctx.P, ctx.N
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        up = N[:, 2]; under = np.clip(-up, 0, 1)
        dn = nose - x                                     # distance aft of the nose
        n1 = fbm(P[:, 0] * 0.05, P[:, 1] * 0.05, P[:, 2] * 0.05, 4, seed=3)
        n2 = fbm(P[:, 0] * 0.4, P[:, 1] * 0.4, P[:, 2] * 0.4, 3, seed=4)
        # grime in creases and occluded areas
        g = np.clip(0.55 * ctx.cav + 0.6 * (1 - ctx.ao) + 0.15 * n1, 0, 1)
        col = col * (1 - 0.30 * g[:, None]) + np.array([0.20, 0.16, 0.11]) * 0.30 * g[:, None]
        # sun-faded, slightly chalky upper surfaces
        if kind in ('fabric', 'wood', 'leather'):
            f = np.clip(up, 0, 1) * (0.10 + 0.06 * n1)
            lum = col.mean(1, keepdims=True)
            col = col * (1 - f[:, None]) + (lum * 0.55 + 0.45 * col + 0.06) * f[:, None]
        # castor oil (rotary) / oil weeps (inline) streaming aft, mostly below the centreline and on the sides
        streak = np.clip(fbm(P[:, 0] * 0.012, P[:, 1] * 0.55, P[:, 2] * 0.55, 3, seed=5) * 1.6 + 0.35, 0, 1)
        reach = 150 if cfg['engine'] == 'rotary' else 95
        oil = np.exp(-np.clip(dn - 10, 0, None) / reach) * (0.35 + 0.65 * np.clip(0.6 - up, 0, 1)) * streak
        oil *= (np.abs(y) < 55) | (kind == 'metal')
        oil = np.clip(oil * (1.25 if cfg['engine'] == 'rotary' else 0.85), 0, 0.92)
        col = col * (1 - 0.75 * oil[:, None]) + np.array([0.16, 0.11, 0.05]) * 0.75 * oil[:, None]
        rough = rough * (1 - 0.55 * oil)
        # exhaust soot behind the stacks
        soot = np.exp(-np.clip(dn - 18, 0, None) / 60) * np.clip(0.75 - up, 0, 1) * np.clip(0.5 + 0.8 * n2, 0, 1)
        soot *= (np.abs(y) < 40)
        col = col * (1 - 0.6 * soot[:, None]) + 0.05 * 0.6 * soot[:, None]
        rough = np.clip(rough + 0.25 * soot, 0, 1)
        # mud flung from the wheels: undersides, lower fuselage, tailplane underside, heavy near the ground
        low = np.clip(1 - z / 60.0, 0, 1)
        sp = fbm(P[:, 0] * 0.9, P[:, 1] * 0.9, P[:, 2] * 0.9, 3, seed=6)
        # wheel spray cone: aft of the axle, inside the wheel track, on downward / low surfaces
        aft = np.clip((WX - x) / 160.0, 0, 1) * (x < WX + 12)
        cone = np.exp(-(np.abs(y) / (WY + 30)) ** 2) * (1 - 0.6 * aft)
        mud = np.clip((0.7 * under + 0.5 * low) * cone * (0.6 + 0.4 * n1) + 0.5 * low * low * (0.5 + 0.5 * n1), 0, 1)
        mud = np.clip((mud - 0.28) * 2.0 + (sp - 0.3) * 1.2 * (mud > 0.18), 0, 1) * ((sp > 0.0) | (mud > 0.7))
        dust = 0.10 * under * (0.6 + 0.4 * n1)
        col = col * (1 - dust[:, None]) + np.array([0.42, 0.36, 0.28]) * dust[:, None]
        mcol = np.array([0.29, 0.23, 0.16]) * (0.85 + 0.25 * n2[:, None])
        col = col * (1 - mud[:, None] * 0.85) + mcol * mud[:, None] * 0.85
        rough = rough * (1 - mud) + 0.95 * mud; metal = metal * (1 - mud)
        hgt = hgt + 0.12 * mud * np.clip(0.5 + sp, 0, 1)
        return col, rough, metal, hgt

    def fabric(ctx):
        col = src_col(ctx)
        lum = col.mean(1, keepdims=True)
        col = (col * 0.86 + lum * 0.14) * 0.93                 # aged dope: a little duller and darker than the factory colours
        w = tri_sample(cloth['lum'], ctx.P, ctx.N, 7.0)
        col = col * (0.93 + 0.07 * w[:, None])
        hgt = 0.015 * (w - 1)
        rough = np.full(ctx.n, 0.62, np.float32) + 0.08 * (w - 1)       # doped linen: satin, not matte
        metal = np.zeros(ctx.n, np.float32)
        # leading-edge abrasion and chipped dope: lighter, rougher raw linen showing through
        lead = np.clip(ctx.N[:, 0], 0, 1)                    # forward-facing: leading edges, nose
        ed = np.clip(ctx.edge * 1.4 - 0.25, 0, 1) * (0.3 + 0.7 * lead) * np.clip(0.5 + fbm(ctx.P[:, 0] * 0.25, ctx.P[:, 1] * 0.25, ctx.P[:, 2] * 0.25, 3, seed=8), 0, 1)
        col = col * (1 - 0.30 * ed[:, None]) + np.array([0.58, 0.54, 0.44]) * 0.30 * ed[:, None]
        rough = rough + 0.25 * ed
        # repair patches (newer, cleaner dope with a taped border) and unpatched bullet holes
        for c, r, a in patches:
            d = ctx.P[:, :2] - c[:2]
            ca, sa = math.cos(a), math.sin(a)
            du = np.abs(d[:, 0] * ca + d[:, 1] * sa); dv = np.abs(-d[:, 0] * sa + d[:, 1] * ca)
            inside = (du < r) & (dv < r * 0.8) & (np.abs(ctx.N[:, 2]) > 0.6)
            border = inside & ((du > r - 0.5) | (dv > r * 0.8 - 0.5))
            col[inside] = col[inside] * 1.06 + 0.015
            col[border] *= 0.82
            hgt[inside] += 0.03; rough[inside] -= 0.06
        for c, r in holes:
            d = np.hypot(ctx.P[:, 0] - c[0], ctx.P[:, 1] - c[1])
            hole = (d < r) & (np.abs(ctx.N[:, 2]) > 0.6)
            ring = (d < r * 2.4) & ~hole & (np.abs(ctx.N[:, 2]) > 0.6)
            col[hole] = 0.03; hgt[hole] -= 0.08
            col[ring] = col[ring] * 0.78 + np.array([0.12, 0.09, 0.06]) * 0.22
        return dict(zip(('color', 'rough', 'metal', 'height'), wear(ctx, col, rough, metal, hgt, 'fabric')))

    def metal_(ctx):
        col = src_col(ctx)
        gl = tri_sample(mtl['lum'], ctx.P, ctx.N, 18.0)
        gr = tri_sample(grime['lum'], ctx.P, ctx.N, 40.0)
        lum = col.mean(1)
        # gunmetal / steel fittings: darkened, blued, worn bright on edges
        base = np.clip(col * 0.55, 0, 1) * (0.9 + 0.1 * gl[:, None]) * (0.85 + 0.15 * gr[:, None])
        ed = np.clip(ctx.edge * 1.8 - 0.3, 0, 1)
        base = base * (1 - ed[:, None]) + np.array([0.55, 0.55, 0.54]) * ed[:, None]
        rough = np.clip(0.48 - 0.15 * ed + 0.1 * (gr - 1), 0.2, 1)
        metal = np.full(ctx.n, 0.85, np.float32)
        hgt = 0.01 * (gl - 1)
        return dict(zip(('color', 'rough', 'metal', 'height'), wear(ctx, base, rough, metal, hgt, 'metal')))

    def wood_(ctx):
        col = src_col(ctx)
        gw = tri_sample(wood['lum'], ctx.P, ctx.N, 60.0)
        col = col * (0.78 + 0.22 * gw[:, None]) * np.array([1.0, 0.93, 0.82])     # varnished ash/walnut
        rough = np.full(ctx.n, 0.38, np.float32) + 0.1 * (1 - gw)
        hgt = 0.02 * (gw - 1)
        return dict(zip(('color', 'rough', 'metal', 'height'), wear(ctx, col, rough, np.zeros(ctx.n, np.float32), hgt, 'wood')))

    def rubber(ctx):
        col = np.minimum(src_col(ctx), 0.09) * (0.8 + 0.2 * tri_sample(cloth['lum'], ctx.P, ctx.N, 5.0)[:, None])
        out = wear(ctx, col, np.full(ctx.n, 0.86, np.float32), np.zeros(ctx.n, np.float32), np.zeros(ctx.n, np.float32), 'rubber')
        return dict(zip(('color', 'rough', 'metal', 'height'), out))

    def leather(ctx):
        col = src_col(ctx)
        w = tri_sample(cloth['lum'], ctx.P, ctx.N, 3.0)
        if col.mean() > 0.6: col = np.tile([0.30, 0.20, 0.12], (ctx.n, 1)).astype(np.float32)     # white placeholder -> brown leather
        col = col * (0.9 + 0.1 * w[:, None])
        rough = np.full(ctx.n, 0.58, np.float32) - 0.1 * ctx.edge
        return dict(zip(('color', 'rough', 'metal', 'height'), wear(ctx, col, rough, np.zeros(ctx.n, np.float32), 0.02 * (w - 1), 'leather')))

    def glass(ctx):
        col = src_col(ctx) * 0.5
        return dict(color=col, rough=np.full(ctx.n, 0.15, np.float32), metal=np.zeros(ctx.n, np.float32))

    def pilot(ctx):
        col = src_col(ctx)
        w = tri_sample(cloth['lum'], ctx.P, ctx.N, 4.0)
        col = col * (0.92 + 0.08 * w[:, None])
        return dict(color=col, rough=np.full(ctx.n, 0.7, np.float32), metal=np.zeros(ctx.n, np.float32), height=0.01 * (w - 1))

    return dict(fabric=fabric, metal=metal_, wood=wood_, rubber=rubber, leather=leather, glass=glass, pilot=pilot)


# ---------------------------------------------------------------- physics: compound hulls (fuselage, each wing, tail)
def hulls(mesh, cfg, name):
    out = []
    srcs = np.array([c['src'] for c in mesh.charts])
    def pts(sel_mats):
        fs = np.isin(srcs[mesh.FC], ['%s_%s' % (name, m) for m in sel_mats])
        return mesh.V[mesh.F[fs].ravel()] if fs.any() else None
    for m in cfg['wings']:
        p = pts([m])
        if p is not None and len(p) > 8:
            lo, hi = p.min(0), p.max(0)
            out.append(modelio.box_pts(lo[0], lo[1], lo[2] - 0.5, hi[0], hi[1], hi[2] + 0.5))
    p = pts([cfg['fuselage']])
    lo, hi = p.min(0), p.max(0)
    out.append(modelio.box_pts(lo[0], -12 if hi[1] - lo[1] > 24 else lo[1], lo[2], hi[0], 12 if hi[1] - lo[1] > 24 else hi[1], hi[2]))
    p = pts(cfg['tail'])
    if p is not None:
        lo, hi = p.min(0), p.max(0); out.append(modelio.box_pts(lo[0], lo[1], lo[2], hi[0], hi[1], hi[2]))
    return out


def write_vmdls(name, smd_rel, matname, vmat, hull_files):
    """one remap to the skin material and exactly one PhysicsHullFile per hull file (rebuilt from the first block every run)"""
    for fn in (name, name + '_dyn'):
        p = os.path.join(OUT, 'models/tw/ext/%s/%s.vmdl' % (name, fn))
        if not os.path.exists(p): continue
        t = open(p).read()
        t = re.sub(r'remaps =\s*\[.*?\n\t\t\t\t\t\t\]', 'remaps =\n\t\t\t\t\t\t[\n\t\t\t\t\t\t\t{\n\t\t\t\t\t\t\t\tfrom = "%s.vmat"\n\t\t\t\t\t\t\t\tto = "%s"\n\t\t\t\t\t\t\t},\n\t\t\t\t\t\t]' % (matname, vmat), t, flags=re.S)
        blocks = re.findall(r'\t\t\t\t\t\{\n\t\t\t\t\t\t_class = "PhysicsHullFile".*?\n\t\t\t\t\t\},\n', t, flags=re.S)
        if blocks:
            tpl = re.sub(r'name = "[^"]*"', 'name = "@N@"', blocks[0], count=1)
            tpl = re.sub(r'filename = "[^"]*"', 'filename = "@F@"', tpl, count=1)
            new = ''.join(tpl.replace('@N@', '%s_hull%d' % (name, k)).replace('@F@', h) for k, h in enumerate(hull_files))
            i0 = t.index(blocks[0]); i1 = t.rindex(blocks[-1]) + len(blocks[-1])
            t = t[:i0] + new + t[i1:]
        open(p, 'w', newline='\n').write(t)


SRC = os.path.join(os.path.dirname(__file__), '..', 'out', 'ext_src')


def backup(name):
    """keep the converter's output (smd + per-material vmats/textures) as the source for re-runs"""
    import shutil
    for sub in ('models/tw/ext/%s' % name, 'materials/models/tw/ext/%s' % name):
        dst = os.path.join(SRC, sub)
        if not os.path.exists(dst): shutil.copytree(os.path.join(OUT, sub), dst)


def run(name, size=4096):
    cfg = CFG[name]
    backup(name)
    E.ADDON = SRC
    mats, head = E.load(name)
    yaw = orient(mats, cfg, name)
    mesh, off, R = build_mesh(mats, name, yaw, cfg)
    print('%s: yaw %+.1f deg, %d tris, %d charts' % (name, yaw, len(mesh.F), len(mesh.charts)))
    sh = make_shaders(name, cfg, mesh)
    bk = bake.bake(mesh, sh, size=size, res=1.25, fill=0.86, normal_strength=1.0)
    rel = 'materials/models/tw/ext/%s' % name
    tname = '%s_skin' % name
    tex = modelio.write_textures(OUT, rel, tname, bk, metal=True)
    vm = '%s/%s.vmat' % (rel, tname)
    modelio.write_vmat(OUT, vm, tex, comment='%s: original colours + CS2 HD detail + object-space wear (procedural, AI-generated)' % name, backfaces=True)
    # SMD (render) with the atlas uv
    mdir = os.path.join(OUT, 'models/tw/ext', name)
    modelio.write_smd(os.path.join(mdir, name + '.smd'), mesh, bk['uv'], tname)
    hs = hulls(mesh, cfg, name)
    hfiles = []
    for k, pts in enumerate(hs):
        hp = 'models/tw/ext/%s/%s_hull%d.smd' % (name, name, k)
        modelio.write_hull_smd(os.path.join(OUT, hp), [pts]); hfiles.append(hp)
    old = os.path.join(mdir, name + '_hull.smd')
    if os.path.exists(old): os.remove(old)
    write_vmdls(name, None, tname, vm, hfiles)
    # drop the old per-material vmats/textures
    keep = set(os.path.basename(v) for v in tex.values()) | {tname + '.vmat'}
    for f in os.listdir(os.path.join(OUT, rel)):
        if f not in keep: os.remove(os.path.join(OUT, rel, f))
    # preview
    lo, hi = mesh.bounds(); c = (lo + hi) / 2
    pv = [(mesh, bk['uv'], bk)]
    ims = [Image.fromarray(render.render(pv, c + e, c, W=800, H=520)) for e in ([260, -300, 170], [-330, 210, 120], [60, -40, -420], [-40, 260, 380])]
    W = Image.new('RGB', (1600, 1040))
    for i, im in enumerate(ims): W.paste(im, ((i % 2) * 800, (i // 2) * 520))
    os.makedirs(PREV, exist_ok=True); W.save(os.path.join(PREV, name + '_weathered.png'))
    json.dump(dict(yaw=yaw, off=off.tolist(), bounds=[lo.tolist(), hi.tolist()]), open(os.path.join(mdir, 'weather.json'), 'w'))
    return mesh


if __name__ == '__main__':
    for n in (sys.argv[1:] or list(CFG)):
        run(n)
