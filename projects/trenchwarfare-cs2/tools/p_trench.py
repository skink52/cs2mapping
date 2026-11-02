"""Trench furniture: revetments, fire-steps, duckboards, ladders, elephant shelters."""
import numpy as np
import geo
from noise import fbm
import shaders as S
W_REV = lambda c: S.wood(c, mud_top=22, wet=0.6)
W_STEP = lambda c: S.wood(c, mud_top=10, wet=0.5)
W_DUCK = lambda c: S.wood(c, mud_top=4.5, wet=0.7, mud=1.0)


def earth_back(x0, x1, z0, z1, y=2.5, nx=16, nz=24, seed=0, amp=1.2):
    xs = np.linspace(x0, x1, nx + 1); zs = np.linspace(z0, z1, nz + 1)
    X, Z = np.meshgrid(xs, zs, indexing='ij')
    Y = y + amp * fbm(X * 0.08 + seed, Z * 0.08, seed * 0.3, 3, seed=5) + 0.5 * fbm(X * 0.3, Z * 0.3, 1, 2, seed=6)
    P = np.stack([X, Y, Z], -1)
    m = geo.surface(P, 'earth', geo.frame(seed=seed))
    # face the trench (-y)
    if (m.face_normals()[:, 1]).mean() > 0: m.F = m.F[:, ::-1]
    m.recompute_normals()
    return m


def post(x, y, z0, z1, r=2.2, seed=0, lean=(0, 0), sides=9, lod=0):
    rng = np.random.RandomState(seed)
    n = 6 if lod == 0 else 2
    zs = np.linspace(z0, z1, n + 1)
    pts = np.stack([x + lean[0] * (zs - z0) / 100, y + lean[1] * (zs - z0) / 100, zs], 1)
    rad = r * (1 + 0.06 * np.sin(zs * 0.07 + seed))
    m = geo.tube(pts, rad, sides=sides if lod == 0 else 5, mat='bark', part=geo.frame(seed=seed, stripped=0.7), caps=True,
                 rnoise=lambda th, s: 1 + 0.05 * np.sin(th * 3 + seed) + 0.03 * np.sin(th * 7 + s * 0.1))
    return m


def revetment_planks(lod=0, seed=0, damaged=False, length=64):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    hl = length / 2.0
    m.add(earth_back(-hl - 2, hl + 2, -2, 100, y=3.2, seed=seed, nx=(6 if lod == 0 else 2) * int(length / 32), nz=12 if lod == 0 else 4))
    z = 0.3
    k = 0
    while z < 95:
        w = rng.uniform(7, 9.5)
        if damaged and rng.rand() < 0.18:
            # broken plank: shorter piece hanging at an angle, leaves a gap
            L = rng.uniform(25, 40); x = rng.uniform(-hl + 2 + L / 2, hl - 2 - L / 2)
            p = geo.plank(L, w, 1.2, mat='wood', r=0.4, seg=1, div=(2 if lod == 0 else 1, 1, 1), warp=0.6, seed=seed * 100 + k,
                          R=geo.euler(rng.uniform(-8, 8), 0, 90 + rng.uniform(-3, 3)) @ np.eye(3), t=(x, 1.6, z + w / 2), tone=rng.rand())
        else:
            L = length + 4 + rng.uniform(0, 2)
            p = geo.plank(L, w, 1.2, mat='wood', r=0.4, seg=1, div=(int(length / 16) if lod == 0 else 2, 1, 1), warp=0.5, seed=seed * 100 + k,
                          R=geo.euler(rng.uniform(-0.5, 0.5), 0, 90 + rng.uniform(-2, 2)), t=(rng.uniform(-1, 1), 1.4 + rng.uniform(-0.3, 0.3), z + w / 2), tone=rng.rand())
        m.add(p)
        z += w + rng.uniform(0.0, 0.9)                     # same in every LOD, or the planks jump when the LOD swaps
        k += 1
    pxs = (-21, 23) if length <= 64 else (-44, 0, 46)
    for j, x in enumerate(pxs):
        m.add(post(x + rng.uniform(-3, 3), -1.6, -2, 101 + rng.uniform(-3, 4), r=2.4, seed=seed * 10 + j, lean=(rng.uniform(-2, 2), rng.uniform(-3, 0)), lod=lod))
    return m


def corrugated_sheet(w, h, p=2.6, a=0.55, nseg=None, mat='galv', part=None, lod=0, dent=0.0, seed=0):
    nx = int(w / p * (6 if lod == 0 else 2)); nz = 6 if lod == 0 else 2
    xs = np.linspace(-w / 2, w / 2, nx + 1); zs = np.linspace(0, h, nz + 1)
    X, Z = np.meshgrid(xs, zs, indexing='ij')
    Y = a * np.sin(X * 2 * np.pi / p)
    if dent:
        Y += dent * fbm(X * 0.05 + seed, Z * 0.05, seed, 3, seed=8) * 4
    P = np.stack([X, Y, Z], -1)
    f = geo.surface(P, mat, part or geo.frame(seed=seed))
    if f.face_normals()[:, 1].mean() > 0: f.F = f.F[:, ::-1]
    f.recompute_normals(angle=89)
    b = geo.surface(P + np.array([0, 0.12, 0]), mat, part or geo.frame(seed=seed))
    if b.face_normals()[:, 1].mean() < 0: b.F = b.F[:, ::-1]
    b.recompute_normals(angle=89)
    f.add(b)
    return f


def revetment_iron(lod=0, seed=0, length=64):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    hl = length / 2.0
    m.add(earth_back(-hl - 2, hl + 2, -2, 100, y=3.4, seed=seed + 5, nx=(6 if lod == 0 else 2) * int(length / 32), nz=12 if lod == 0 else 4))
    x = -hl - 1
    k = 0
    while x < hl + 1:
        sw = 27
        sh = geo.corrugated_sheet if False else corrugated_sheet(sw, 74 + rng.uniform(-2, 3), lod=lod, dent=0.3, seed=seed * 10 + k)
        sh.transform(geo.euler(rng.uniform(-2, 2), 0, rng.uniform(-1.5, 1.5)), (x + sw / 2, 1.2 + (k % 2) * 0.35, rng.uniform(-1, 1)))
        m.add(sh); x += sw - 3; k += 1
    # upper planks above the iron
    z = 74
    while z < 95:
        w = rng.uniform(7.5, 9)
        m.add(geo.plank(length + 4, w, 1.2, mat='wood', seg=1, div=(int(length / 16) if lod == 0 else 2, 1, 1), warp=0.5, seed=seed * 70 + int(z),
                        R=geo.euler(0, 0, 90), t=(0, 1.6, z + w / 2), tone=rng.rand()))
        z += w + 0.5
    pxs = (-22, 22) if length <= 64 else (-44, 0, 44)
    for j, x in enumerate(pxs):
        m.add(post(x + rng.uniform(-2, 2), -1.5, -2, 100 + rng.uniform(-2, 3), r=2.3, seed=seed * 13 + j, lean=(rng.uniform(-2, 2), rng.uniform(-3, 0)), lod=lod))
    return m


def firestep(lod=0, seed=0):
    """two-tier step against the front wall: top tread y in [-16,0] at z=40, lower tread y in [-30,-16] at z=20; length x in [-32,32]"""
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    sg = 2 if lod == 0 else 1
    def tread(z, y0, y1, k0):
        y = y0 + 0.2; kk = k0
        while y < y1 - 1:
            w = min(rng.uniform(7, 8.5), y1 - y)
            m.add(geo.plank(65, w, 1.5, mat='wood', seg=sg, div=(8 if lod == 0 else 2, 1, 1), warp=0.4, seed=seed * 50 + kk,
                            t=(rng.uniform(-0.5, 0.5), y + w / 2, z - 0.75), tone=rng.rand()))
            y += w + 0.4; kk += 1
    tread(40, -16, 0, 0)
    tread(20, -30, -16, 10)
    # risers
    for z0, z1, y in ((20, 40, -16.6), (0, 20, -30.6)):
        z = z0
        while z < z1 - 0.5:
            w = min(rng.uniform(6.5, 8), z1 - 1.5 - z)
            if w < 2: break
            m.add(geo.plank(64, w, 1.2, mat='wood', seg=sg, div=(8 if lod == 0 else 2, 1, 1), warp=0.3, seed=seed * 90 + int(z),
                            R=geo.euler(0, 0, 90), t=(0, y, z + w / 2), tone=rng.rand()))
            z += w + 0.3
    # stakes holding the risers
    for x in (-28, 0, 28):
        m.add(post(x + rng.uniform(-2, 2), -32.6, -1, 21, r=1.5, seed=seed + int(x) + 40, lod=lod, sides=7))
        m.add(post(x + rng.uniform(-2, 2), -18.4, 18, 41, r=1.5, seed=seed + int(x) + 80, lod=lod, sides=7))
    return m


def duckboard(lod=0, seed=0, length=64):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    sg = 2 if lod == 0 else 1
    for y in (-7.5, 7.5):
        m.add(geo.plank(length, 3.5, 3.0, mat='wood', seg=sg, div=(6 if lod == 0 else 2, 1, 1), warp=0.3, seed=seed * 7 + int(y + 20),
                        R=geo.euler(rng.uniform(-0.6, 0.6), 0, 0), t=(0, y, 1.5), tone=rng.rand()))
    x = -length / 2 + 2
    k = 0
    while x < length / 2 - 1:
        w = rng.uniform(3.2, 3.8)
        broken = rng.rand() < 0.06
        if not broken:
            m.add(geo.plank(24 + rng.uniform(-1, 1), w, 1.0, mat='wood', seg=sg, div=(2, 1, 1), warp=0.35, seed=seed * 300 + k,
                            R=geo.euler(90 + rng.uniform(-2, 2), rng.uniform(-1, 1), 0), t=(x + w / 2, rng.uniform(-0.6, 0.6), 3.5 + rng.uniform(0, 0.25)), tone=rng.rand()))
        x += w + rng.uniform(1.2, 1.9); k += 1
    return m


def ladder(lod=0, seed=0, length=110):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    sg = 2 if lod == 0 else 1
    for y in (-8, 8):
        m.add(geo.plank(length, 3.2, 2.2, mat='wood', seg=sg, div=(8 if lod == 0 else 2, 1, 1), warp=0.4, seed=seed + int(y) + 30,
                        R=geo.euler(0, -90, 0), t=(0, y, length / 2), tone=rng.rand()))
    z = 10
    while z < length - 4:
        m.add(geo.tube([[0, -9.5, z], [0, 9.5, z + rng.uniform(-0.5, 0.5)]], 0.9, sides=7 if lod == 0 else 4, mat='wood', part=geo.frame(seed=seed + int(z)), caps=True))
        z += 12
    return m


def tunnel_set(lod=0, seed=0, width=80.0, height=92.0):
    """mine-gallery timber set: two round props under a squared cap, a sill, and a few lagging boards over the cap (gallery runs along x)"""
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    sides = 9 if lod == 0 else 5
    for s in (-1, 1):
        y = s * (width / 2 - 4.5)
        m.add(geo.tube([(rng.uniform(-0.6, 0.6), y, -2), (rng.uniform(-0.6, 0.6), y + s * rng.uniform(-0.8, 0.4), height - 7)], [4.2, 3.9], sides=sides,
                       mat='bark', part=geo.frame(seed=seed + s)))
    m.add(geo.plank(width + 4, 7.5, 7.0, mat='wood', seg=1, div=(4, 1, 1), warp=0.6, seed=seed + 7, R=geo.euler(90, 0, 0), t=(0, 0, height - 3.5), tone=rng.rand()))
    m.add(geo.plank(width - 2, 5.0, 3.0, mat='wood', seg=1, div=(3, 1, 1), warp=0.3, seed=seed + 8, R=geo.euler(90, 0, 0), t=(0, 0, 0.5), tone=rng.rand()))
    if lod == 0:
        for k in range(3):
            m.add(geo.plank(22, 9.0, 1.4, mat='wood', seg=1, div=(2, 1, 1), warp=0.3, seed=seed + 20 + k,
                            t=(rng.uniform(-3, 3), -width / 3 + k * width / 3, height + 0.8), tone=rng.rand()))
    return m


def shelter(lod=0, seed=0):
    """elephant-iron shelter: corrugated half-arch, length along x (96), opening at -x, earth/sandbags over"""
    import p_sandbag
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    R0 = 46.0; L = 96.0
    nth = 24 if lod == 0 else 8
    th = np.linspace(0, np.pi, nth + 1)
    for k in range(3):
        x0 = -L / 2 + k * 31
        xs = np.linspace(x0, x0 + 34, (14 if lod == 0 else 4) + 1)
        TH, X = np.meshgrid(th, xs, indexing='ij')
        rr = R0 + 0.55 * np.sin(TH * R0 / 2.6 * 2) * 0 + 0.55 * np.sin(X * 2 * np.pi / 2.6) * 0
        # corrugations run around the arch (ridges along the arc)
        corr = 0.55 * np.sin(TH * R0 * 2 * np.pi / 2.6 / 1.0)
        P = np.stack([X, (R0 + corr) * np.cos(TH), (R0 + corr) * np.sin(TH) * 0.92], -1)
        inner = geo.surface(P, 'galv', geo.frame(seed=seed * 7 + k))
        if (inner.face_normals() * np.stack([np.zeros(len(inner.F)), -inner.V[inner.F].mean(1)[:, 1], -inner.V[inner.F].mean(1)[:, 2]], 1)).sum(1).mean() < 0:
            inner.F = inner.F[:, ::-1]
        inner.recompute_normals(angle=89)
        m.add(inner)
        outer = inner.copy()
        outer.V = outer.V.copy(); outer.V[:, 1:] *= 1 + 0.5 / R0
        outer.F = outer.F[:, ::-1].copy(); outer.recompute_normals(angle=89)
        m.add(outer)
    # earth mound over the arch, closed at the mouth and the back
    nx, na = (20, 30) if lod == 0 else (6, 10)
    x_front, x_back = -L / 2, L / 2 + 10
    xs = np.linspace(x_front, x_back, nx + 1); a = np.linspace(-0.25, np.pi + 0.25, na + 1)
    A, X = np.meshgrid(a, xs, indexing='ij')
    def mound_pt(X, A):
        Rm = R0 + 14 + 6 * fbm(X * 0.05, A * 2, 3, 3, seed=9)
        return np.stack([X, Rm * np.cos(A) * 1.25, np.maximum(Rm * np.sin(A) * 0.9, -3)], -1)
    P = mound_pt(X, A)
    mound = geo.surface(P, 'earth', geo.frame(seed=seed))
    c = mound.V[mound.F].mean(1)
    if (mound.face_normals()[:, 2] * np.sign(c[:, 2] + 1e-3)).mean() < 0: mound.F = mound.F[:, ::-1]
    mound.recompute_normals()
    m.add(mound)
    # mouth: earth face between the arch edge and the mound, facing -x
    th = np.linspace(-0.25, np.pi + 0.25, na + 1)
    outer_e = mound_pt(np.full(th.shape, x_front), th)
    thc = np.clip(th, 0, np.pi)
    inner_e = np.stack([np.full(th.shape, x_front + 0.3), (R0 + 0.6) * np.cos(thc), np.maximum((R0 + 0.6) * np.sin(thc) * 0.92, -3)], -1)
    inner_e[:, 2] = np.where((th < 0) | (th > np.pi), -3, inner_e[:, 2])
    cap = geo.surface(np.stack([inner_e, outer_e], 1), 'earth', geo.frame(seed=seed + 5))
    if cap.face_normals()[:, 0].mean() > 0: cap.F = cap.F[:, ::-1]
    cap.recompute_normals(angle=89); m.add(cap)
    # back: close the mound end facing +x
    outer_b = mound_pt(np.full(th.shape, x_back), th)
    cen = np.tile([x_back, 0, -3], (len(th), 1)).astype(float)
    capb = geo.surface(np.stack([cen, outer_b], 1), 'earth', geo.frame(seed=seed + 6))
    if capb.face_normals()[:, 0].mean() < 0: capb.F = capb.F[:, ::-1]
    capb.recompute_normals(angle=89); m.add(capb)
    # back wall of planks
    z = 0
    while z < 42:
        w = rng.uniform(7, 8.5)
        half = np.sqrt(max(R0 ** 2 - (z / 0.92) ** 2, 1))
        m.add(geo.plank(2 * half + 4, w, 1.3, mat='wood', seg=2 if lod == 0 else 1, div=(6 if lod == 0 else 1, 1, 1), seed=seed + int(z),
                        R=geo.euler(90, 0, 90), t=(L / 2 + 2, 0, z + w / 2), tone=rng.rand()))
        z += w + 0.3
    # sandbag header over the mouth, bedded into the mound
    w, h = p_sandbag.wall(length=64, courses=2, lod=1 if lod else 0, seed=seed + 40, top=False)
    w.transform(geo.euler(90, 0, 0), (-L / 2 + 23, 0, R0 * 0.92 + 9))
    m.add(w)
    return m


def specs():
    out = {}
    for v in range(2):
        out['revet_planks_%s' % 'ab'[v]] = dict(lods=[revetment_planks(0, 3 + v), revetment_planks(1, 3 + v)], size=1024, ground=0.0,
                                               shaders={'wood': W_REV, 'bark': S.bark, 'earth': S.earth}, surface='wood',
                                               hulls=[np.array([[x, y, z] for x in (-32, 32) for y in (0, 6) for z in (0, 96)])])
    out['revet_planks_broken'] = dict(lods=[revetment_planks(0, 7, True), revetment_planks(1, 7, True)], size=1024, ground=0.0,
                                      shaders={'wood': W_REV, 'bark': S.bark, 'earth': S.earth}, surface='wood',
                                      hulls=[np.array([[x, y, z] for x in (-32, 32) for y in (0, 6) for z in (0, 96)])])
    out['revet_iron'] = dict(lods=[revetment_iron(0, 2), revetment_iron(1, 2)], size=1024, ground=0.0, metal=True,
                             shaders={'wood': W_REV, 'bark': S.bark, 'earth': S.earth, 'galv': S.galvanised}, surface='metal',
                             hulls=[np.array([[x, y, z] for x in (-32, 32) for y in (0, 6) for z in (0, 96)])])
    for nm, fn, sd in (('revet_planks_a_128', lambda l: revetment_planks(l, 13, length=128), 0), ('revet_planks_b_128', lambda l: revetment_planks(l, 14, length=128), 0),
                       ('revet_iron_128', lambda l: revetment_iron(l, 12, length=128), 0), ('revet_planks_broken_128', lambda l: revetment_planks(l, 17, True, length=128), 0)):
        out[nm] = dict(lods=[fn(0), fn(1)], size=1024, ground=0.0, metal='iron' in nm,
                       shaders={'wood': W_REV, 'bark': S.bark, 'earth': S.earth, 'galv': S.galvanised}, surface='wood',
                       hulls=[np.array([[x, y, z] for x in (-64, 64) for y in (0, 6) for z in (0, 96)])])
    out['duckboard_128'] = dict(lods=[duckboard(0, 5, 128), duckboard(1, 5, 128)], size=1024, ground=0.0, shaders={'wood': W_DUCK}, surface='wood',
                                hulls=[np.array([[x, y, z] for x in (-64, 64) for y in (-11, 11) for z in (0, 4.2)])])
    out['firestep'] = dict(lods=[firestep(0, 1), firestep(1, 1)], size=1024, ground=0.0,
                           shaders={'wood': W_STEP, 'bark': S.bark}, surface='wood',
                           hulls=[np.array([[x, y, z] for x in (-32, 32) for y in (-16, 0) for z in (0, 40)]),
                                  np.array([[x, y, z] for x in (-32, 32) for y in (-30, -16) for z in (0, 20)])])
    out['duckboard'] = dict(lods=[duckboard(0, 1), duckboard(1, 1)], size=512, ground=0.0, shaders={'wood': W_DUCK}, surface='wood',
                            hulls=[np.array([[x, y, z] for x in (-32, 32) for y in (-11, 11) for z in (0, 4.2)])])
    out['ladder'] = dict(lods=[ladder(0, 2)], size=512, ground=0.0, shaders={'wood': S.wood}, surface='wood', hulls=[])
    out['tunnel_set'] = dict(lods=[tunnel_set(0, 3), tunnel_set(1, 3)], size=512, ground=0.0, shaders={'wood': S.wood, 'bark': S.bark}, surface='wood',
                             stock={'wood': ['boards', 'boards_dark'], 'bark': 'bark'},
                             hulls=[np.array([[x, y, z] for x in (-4, 4) for y in (s * 31, s * 40) for z in (0, 88)]) for s in (-1, 1)])
    out['shelter'] = dict(lods=[shelter(0, 4), shelter(1, 4)], size=2048, ground=0.0, metal=True,
                          shaders={'wood': S.wood, 'earth': S.earth, 'galv': S.galvanised, 'burlap': S.burlap}, surface='dirt',
                          hulls=[np.array([[x, 58 * np.cos(a) * 1.25, max(58 * np.sin(a) * 0.9, -3)] for x in (-48, 58)
                                           for a in np.linspace(-0.25, np.pi + 0.25, 13)])])      # the earth mound (the arch is too low to stand in)
    return out
