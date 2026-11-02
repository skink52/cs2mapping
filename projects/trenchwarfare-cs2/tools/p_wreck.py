"""Destroyed equipment for no man's land: a wrecked rhomboid heavy tank and a wrecked field gun (+ loose wheel)."""
import numpy as np
import geo
from noise import fbm, perlin
import shaders as S

BROWN = S._c(0.38, 0.36, 0.29)
FIELDGREY = S._c(0.40, 0.42, 0.37)


def chaikin(p, it=2):
    p = np.asarray(p, float)
    for _ in range(it):
        q = []
        for i in range(len(p)):
            a, b = p[i], p[(i + 1) % len(p)]
            q += [a * 0.75 + b * 0.25, a * 0.25 + b * 0.75]
        p = np.array(q)
    return p


def box(x0, y0, z0, x1, y1, z1, mat, part=None):
    return geo.prism([(x0, z0), (x1, z0), (x1, z1), (x0, z1)], y0, y1, mat, part)


TANK_PROFILE = chaikin([(-152, 42), (-142, 10), (-112, 0), (92, 0), (132, 12), (160, 44), (166, 72), (150, 97), (108, 101), (-122, 99), (-150, 80)], 2)


def track_band(poly, y0, y1, step=4.3, seed=0, cut=None, part=None):
    loop, per = geo.resample_loop(geo.offset_poly(poly, 3.0), step)
    n = len(loop)
    idx = np.arange(n + 1) % n
    if cut is not None:
        # open the loop between parameter fractions cut=(a,b): keep the rest
        a, b = int(cut[0] * n), int(cut[1] * n)
        idx = np.concatenate([np.arange(b, n), np.arange(0, a + 1)])
    L = loop[idx]
    P = np.zeros((len(L), 2, 3))
    P[:, 0] = np.stack([L[:, 0], np.full(len(L), y0), L[:, 1]], 1)
    P[:, 1] = np.stack([L[:, 0], np.full(len(L), y1), L[:, 1]], 1)
    m = geo.surface(P, 'track', part or geo.frame(seed=seed, tw=abs(y1 - y0)))
    cen = np.array([poly[:, 0].mean(), (y0 + y1) / 2, poly[:, 1].mean()])
    fc = m.V[m.F].mean(1) - cen; fc[:, 1] = 0
    if np.einsum('ij,ij->i', m.face_normals(), fc).mean() < 0: m.F = m.F[:, ::-1]
    m.recompute_normals(angle=35)
    # inner side of the band (seen from below/inside)
    inner = geo.surface(P - np.array([0, 0, 0]), 'track', part or geo.frame(seed=seed, tw=abs(y1 - y0)))
    inner.V = inner.V.copy()
    # shrink inward by 1.6 units along -normal
    inner.V -= np.vstack([m.N]) * 1.6
    inner.F = m.F[:, ::-1].copy(); inner.recompute_normals(angle=35)
    m.add(inner)
    return m, L


def grousers(L, y0, y1, every=2, part=None):
    m = geo.Mesh()
    c = L.mean(0)
    for i in range(0, len(L) - 1, every):
        p = L[i]; q = L[i + 1]
        t = q - p; t /= np.linalg.norm(t) + 1e-9
        nrm = np.array([t[1], -t[0]])
        if np.dot(nrm, p - c) < 0: nrm = -nrm
        a = p + nrm * 0.2; b = p + nrm * 1.9
        quad = [a - t * 1.1, a + t * 1.1, b + t * 0.9, b - t * 0.9]
        g = geo.prism(quad, y0 + 0.5, y1 - 0.5, 'track', part)
        m.add(g)
    return m


def shell_hole(c, r=6.0, y_face=76.0, out=1, seed=0):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    k = 9
    for i in range(k):
        a0 = 2 * np.pi * i / k; a1 = 2 * np.pi * (i + 1) / k; am = (a0 + a1) / 2
        rr = r * rng.uniform(0.8, 1.2)
        p0 = np.array([c[0] + np.cos(a0) * r, y_face + out * 0.3, c[1] + np.sin(a0) * r])
        p1 = np.array([c[0] + np.cos(a1) * r, y_face + out * 0.3, c[1] + np.sin(a1) * r])
        tip = np.array([c[0] + np.cos(am) * r * 0.25, y_face - out * rng.uniform(2, 5), c[1] + np.sin(am) * r * 0.25])
        P = np.array([[p0, tip], [p1, tip]])
        P = np.stack([np.linspace(p0, p1, 3), np.linspace(p0, p1, 3) * 0 + tip], 1)
        s = geo.surface(P, 'tank', geo.frame(seed=seed + i))
        if (s.face_normals()[:, 1] * out).mean() < 0: s.F = s.F[:, ::-1]
        s.recompute_normals()
        m.add(s)
    th = np.linspace(0, 2 * np.pi, 13)[:-1]
    ring = np.stack([c[0] + np.cos(th) * r * 0.5, np.full(12, y_face - out * 4.5), c[1] + np.sin(th) * r * 0.5], 1)
    m.add(geo.disk(np.array([c[0], y_face - out * 4.5, c[1]]), ring, [0, out, 0], 'hole'))
    return m


def tank(lod=0, seed=0):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    prof = TANK_PROFILE
    plate = geo.frame(seed=seed, panel_u=46.0, panel_v=33.0)
    for side in (1, -1):
        y0, y1 = (50, 76) if side > 0 else (-76, -50)
        m.add(geo.prism(prof, y0, y1, 'tank', plate))
        cut = (0.06, 0.16) if side < 0 else None
        band, L = track_band(prof, y0 - 1.5 if side > 0 else y0 - 1.5, y1 + 1.5, seed=seed + side, cut=cut)
        m.add(band)
        if lod == 0: m.add(grousers(L, y0 - 1.5, y1 + 1.5, every=2))
        if cut is not None:
            # thrown track lying in the mud in front
            xs = np.linspace(110, 230, 26)
            ys = y0 - 8 + 10 * np.sin(xs * 0.03) + np.linspace(0, -18, 26)
            zs = 0.6 + 0.8 * np.abs(np.sin(xs * 0.2))
            P = np.zeros((26, 2, 3))
            d = np.array([0, 1.0, 0])
            for i in range(26):
                P[i, 0] = [xs[i], ys[i], zs[i]]; P[i, 1] = [xs[i] - 2, ys[i] + 29, zs[i] + 0.4]
            t = geo.surface(P, 'track', geo.frame(seed=seed + 7, tw=29.0))
            if t.face_normals()[:, 2].mean() < 0: t.F = t.F[:, ::-1]
            t.recompute_normals(); m.add(t)
            if lod == 0:
                for i in range(1, 25, 2):
                    a = P[i, 0]; b = P[i, 1]
                    g = box(-1, 0, 0, 1, 1, 1.6, 'track')
                    g.V[:, 1] = g.V[:, 1] * 0
                    m.add(geo.prism([(a[0] - 1, a[2] + 0.3), (a[0] + 1, a[2] + 0.3), (a[0] + 0.8, a[2] + 1.9), (a[0] - 0.8, a[2] + 1.9)], a[1] + 0.5, b[1] - 0.5, 'track'))
    # central hull
    m.add(geo.rbox(232, 100, 90, r=2.0, seg=1, mat='tank', part=geo.frame(seed=seed + 1, o=(0, 0, 0), panel_u=46.0, panel_v=30.0), center=(-6, 0, 52), div=(4, 2, 2)))
    # roof plates and cab
    m.add(geo.rbox(50, 70, 22, r=1.5, seg=1, mat='tank', part=geo.frame(seed=seed + 2, panel_u=25.0), center=(94, 0, 106)))
    for yy in (-22, -8, 8, 22):
        m.add(box(118.5, yy - 3, 105, 120.5, yy + 3, 107, 'slit'))
    # sponsons
    sp = [(-26, 22), (44, 22), (56, 44), (46, 82), (-26, 82), (-34, 52)]
    for side in (1, -1):
        y0, y1 = (76, 98) if side > 0 else (-98, -76)
        m.add(geo.prism(sp, y0, y1, 'tank', geo.frame(seed=seed + 3 + side, panel_u=24.0, panel_v=20.0)))
        # 6-pdr barrel poking out of the sponson front
        base = np.array([40.0, side * 90.0, 56.0])
        d = np.array([0.82, side * 0.3, 0.02 * side]); d /= np.linalg.norm(d)
        if side < 0: d = np.array([0.5, -0.5, -0.25]); d /= np.linalg.norm(d)   # knocked askew
        mant = geo.lathe([(0.01, -6), (5, -5), (7.5, -1), (7.5, 2), (5, 5), (0.01, 6)], 14 if lod == 0 else 8, 'tank', geo.frame(seed=seed + 9))
        mant.transform(geo.look_frame(d) @ geo.rot('y', 90), base)
        m.add(mant)
        bpts = [base + d * t for t in np.linspace(0, 52, 6)]
        m.add(geo.tube(bpts, [2.6, 2.5, 2.4, 2.3, 2.3, 2.6], sides=12 if lod == 0 else 6, mat='gunsteel', part=geo.frame(seed=seed + 11)))
    # exhaust along the roof, silencer at the back
    ex = [(70, 26, 102), (40, 26, 103), (-60, 26, 103), (-112, 26, 100)]
    m.add(geo.tube(ex, 3.0, sides=10 if lod == 0 else 6, mat='rust', part=geo.frame(seed=seed + 12)))
    m.add(geo.tube([(-112, 26, 100), (-126, 26, 100)], 6.5, sides=12 if lod == 0 else 6, mat='rust', part=geo.frame(seed=seed + 13)))
    # unditching rails and beam
    for yy in (-40, 40):
        m.add(geo.rbox(250, 4, 4, r=0.6, seg=1, mat='tank', part=geo.frame(seed=seed + 14), center=(-4, yy, 99)))
    beam = geo.tube([(-96, -78, 107), (-97, 0, 108), (-95, 78, 107)], 7.5, sides=12 if lod == 0 else 7, mat='bark', part=geo.frame(seed=seed + 15, stripped=0.7))
    m.add(beam)
    # shell penetrations on the left plate
    for k, c in enumerate([(-40, 62), (20, 30)]):
        m.add(shell_hole(c, r=7 + k, y_face=76.0, out=1, seed=seed + 20 + k))
    hulls = [np.array([[x, y, z] for x in (-150, 150) for y in (-77, 77) for z in (0, 98)]),
             np.array([[x, y, z] for x in (70, 120) for y in (-35, 35) for z in (95, 117)]),
             np.array([[x, y, z] for x in (-30, 55) for y in (76, 98) for z in (22, 82)]),
             np.array([[x, y, z] for x in (-30, 55) for y in (-98, -76) for z in (22, 82)])]
    return m, hulls


def wheel(r=26.0, seed=0, lod=0, broken=0):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    n = 48 if lod == 0 else 16
    th = np.linspace(0, 2 * np.pi, n + 1)
    # iron tyre (band) and wooden felloe
    for rad, w, mat, th_ in ((r, 3.2, 'gunsteel', 1.0), (r - 1.0, 3.0, 'wood', 3.2)):
        P = np.zeros((n + 1, 2, 3))
        P[:, 0] = np.stack([np.cos(th) * rad, np.full(n + 1, -w / 2), np.sin(th) * rad], 1)
        P[:, 1] = np.stack([np.cos(th) * rad, np.full(n + 1, w / 2), np.sin(th) * rad], 1)
        o = geo.surface(P, mat, geo.frame(seed=seed))
        if (np.einsum('ij,ij->i', o.face_normals(), o.V[o.F].mean(1) * [1, 0, 1])).mean() < 0: o.F = o.F[:, ::-1]
        o.recompute_normals(angle=60); m.add(o)
        i_ = geo.surface(P * [(rad - th_) / rad, 1, (rad - th_) / rad], mat, geo.frame(seed=seed))
        i_.F = o.F[:, ::-1].copy(); i_.recompute_normals(angle=60); m.add(i_)
        for yy in (-w / 2, w / 2):
            Q = np.zeros((n + 1, 2, 3))
            Q[:, 0] = np.stack([np.cos(th) * rad, np.full(n + 1, yy), np.sin(th) * rad], 1)
            Q[:, 1] = np.stack([np.cos(th) * (rad - th_), np.full(n + 1, yy), np.sin(th) * (rad - th_)], 1)
            s = geo.surface(Q, mat, geo.frame(seed=seed))
            if (s.face_normals()[:, 1] * np.sign(yy)).mean() < 0: s.F = s.F[:, ::-1]
            s.recompute_normals(angle=30); m.add(s)
    # spokes
    missing = set(rng.choice(12, broken, replace=False)) if broken else set()
    for k in range(12):
        a = 2 * np.pi * k / 12
        d = np.array([np.cos(a), 0, np.sin(a)])
        if k in missing:
            L = rng.uniform(4, 9)
            m.add(geo.tube([d * 5, d * (5 + L)], [1.3, 1.1], sides=6, mat='wood', part=geo.frame(seed=seed + k)))
            continue
        m.add(geo.tube([d * 5 + [0, 0.8, 0], d * (r - 3.5)], [1.4, 1.0], sides=7 if lod == 0 else 4, mat='wood', part=geo.frame(seed=seed + k)))
    hub = geo.lathe([(0.01, -6), (4.5, -6), (5.5, -3), (5.5, 3), (3.5, 5), (2.5, 7), (0.01, 7)], 14 if lod == 0 else 8, 'gunsteel', geo.frame(seed=seed + 40))
    hub.transform(geo.rot('x', -90)); m.add(hub)
    return m


def field_gun(lod=0, seed=0):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    R = 26.0
    for side in (1, -1):
        w = wheel(R, seed=seed + side, lod=lod, broken=3 if side < 0 else 0)
        if side < 0: w.transform(np.eye(3) * [1, -1, 1] if False else geo.rot('z', 180))
        w.transform(None, (0, side * 31, R)); m.add(w)
    m.add(geo.tube([(0, -33, R), (0, 33, R)], 2.2, sides=10 if lod == 0 else 6, mat='gunsteel', part=geo.frame(seed=seed + 2)))
    # carriage cheeks and trail
    trail = [(-4, 22), (14, 30), (14, 40), (-10, 40), (-120, 6), (-124, 1), (-112, 1)]
    for yy in (-6, 6):
        m.add(geo.prism(trail, yy - 1.2, yy + 1.2, 'gun', geo.frame(seed=seed + 3, panel_u=30.0)))
    m.add(box(-122, -9, 0, -116, 9, 11, 'gun'))           # spade
    m.add(geo.tube([(-112, -12, 8), (-112, 12, 8)], 0.9, sides=6, mat='gunsteel', part=geo.frame(seed=seed + 4)))
    # cradle, recoil cylinder, barrel (elevated slightly)
    el = geo.rot('y', -6)
    piv = np.array([2.0, 0, 42.0])
    parts = geo.Mesh()
    parts.add(geo.rbox(70, 10, 9, r=1.2, seg=1, mat='gun', part=geo.frame(seed=seed + 5), center=(12, 0, -4)))
    parts.add(geo.tube([(-24, 0, -5), (46, 0, -5)], 3.4, sides=12 if lod == 0 else 6, mat='gun', part=geo.frame(seed=seed + 6)))
    prof = [(0.01, -26), (5.0, -26), (5.2, -14), (4.2, -10), (3.6, 20), (3.1, 60), (3.0, 72), (3.6, 74), (3.6, 78), (2.2, 78), (2.2, 70)]
    bar = geo.lathe(prof, 16 if lod == 0 else 8, 'gunsteel', geo.frame(seed=seed + 7))
    bar.transform(geo.rot('y', 90)); parts.add(bar)
    parts.add(geo.rbox(14, 12, 12, r=1.0, seg=1, mat='gunsteel', part=geo.frame(seed=seed + 8), center=(-28, 0, 0)))
    parts.transform(el, piv); m.add(parts)
    # shield: main plate with barrel slot, folding top plate, apron
    sh = [(-30, 0), (30, 0), (30, 36), (6, 36), (6, 22), (-6, 22), (-6, 36), (-30, 36)]
    s = geo.prism([(x, z) for x, z in sh], -0.6, 0.6, 'gun', geo.frame(seed=seed + 9, panel_u=20.0))
    s.transform(geo.rot('z', 90) @ geo.rot('y', 0), (0, 0, 0))
    s.transform(geo.rot('y', 10), (16, 0, 30)); m.add(s)
    top = box(-0.6, -30, 0, 0.6, 30, 12, 'gun', geo.frame(seed=seed + 10)); top.transform(geo.rot('y', 25), (22.5, 0, 66)); m.add(top)
    apron = box(-0.6, -26, 0, 0.6, 26, 12, 'gun', geo.frame(seed=seed + 11)); apron.transform(geo.rot('y', -8), (17, 0, 14)); m.add(apron)
    # sight bracket and hand wheels
    m.add(geo.tube([(4, -9, 44), (4, -9, 54)], 0.8, sides=6, mat='gunsteel', part=geo.frame(seed=seed + 12)))
    for yy in (-11, 11):
        th = np.linspace(0, 2 * np.pi, 17)
        ring = np.stack([-6 + np.cos(th) * 4, np.full(17, yy), 34 + np.sin(th) * 4], 1)
        m.add(geo.tube(ring, 0.5, sides=5, mat='gunsteel', part=geo.frame(seed=seed + 13), caps=False))
    hulls = [np.array([[x, y, z] for x in (-12, 22) for y in (-36, 36) for z in (0, 70)]),
             np.array([[x, y, z] for x in (-124, -10) for y in (-9, 9) for z in (0, 30)]),
             np.array([[x, y, z] for x in (-30, 80) for y in (-5, 5) for z in (34, 50)])]
    return m, hulls


def specs():
    sh = dict(tank=lambda c: S.painted_steel(c, BROWN, chip=0.28, rivets=True, mud_top=34, burnt=0.4),
              track=S.track, slit=lambda c: S.rust_steel(c, mud_top=0),
              gunsteel=lambda c: S.painted_steel(c, S._c(0.30, 0.31, 0.29), chip=0.3, mud_top=6),
              rust=lambda c: S.rust_steel(c, mud_top=0, burnt=0.6), bark=S.bark,
              hole=lambda c: dict(color=np.tile(S._c(0.03, 0.025, 0.02), (c.n, 1)), rough=np.full(c.n, 0.9), metal=np.zeros(c.n), height=np.zeros(c.n)))
    gsh = dict(gun=lambda c: S.painted_steel(c, FIELDGREY, chip=0.32, rivets=True, mud_top=14),
               gunsteel=lambda c: S.painted_steel(c, FIELDGREY * 0.85, chip=0.3, mud_top=10),
               wood=lambda c: S.wood(c, mud_top=12, wet=0.4))
    out = {}
    m0, h = tank(0, 1); m1, _ = tank(1, 1)
    out['wreck_tank'] = dict(lods=[m0, m1], lod_thresholds=[0.0, 40.0], size=2048, ground=0.0, metal=True, shaders=sh, surface='metal', hulls=h, res=2.0)
    m0, h = field_gun(0, 2); m1, _ = field_gun(1, 2)
    out['wreck_fieldgun'] = dict(lods=[m0, m1], lod_thresholds=[0.0, 30.0], size=2048, ground=0.0, metal=True, shaders=gsh, surface='metal', hulls=h, res=1.0)
    w0 = wheel(26, 7, 0, broken=5); w0.transform(geo.rot('x', 90), (0, 0, 3.2))
    w1 = wheel(26, 7, 1, broken=5); w1.transform(geo.rot('x', 90), (0, 0, 3.2))
    out['wreck_wheel'] = dict(lods=[w0, w1], size=1024, ground=0.0, metal=True, shaders=gsh, surface='wood',
                              hulls=[np.array([[x, y, z] for x in (-27, 27) for y in (-27, 27) for z in (0, 7)])], res=0.75)
    return out
