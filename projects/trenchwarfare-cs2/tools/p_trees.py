"""Shell-blasted trees: shattered trunks with splintered crowns, branch stubs and root flare; stumps; fallen trunk."""
import numpy as np
import geo
from noise import fbm, perlin
import shaders as S


def trunk_path(H, seed, lean=8.0, n=None):
    rng = np.random.RandomState(seed)
    n = n or max(8, int(H / 12))
    z = np.linspace(-10, H, n + 1)
    lx = rng.uniform(-1, 1) * lean; ly = rng.uniform(-1, 1) * lean
    x = lx * np.clip(z / H, 0, None) ** 1.6 + 3 * perlin(z * 0.01 + seed, 0.3, 0.1)
    y = ly * np.clip(z / H, 0, None) ** 1.6 + 3 * perlin(z * 0.01 + seed, 5.3, 0.7)
    return np.stack([x, y, z], 1)


def splinter_shard(base, direction, length, width, seed, lod=0):
    d = np.asarray(direction, float); d /= np.linalg.norm(d)
    pts = np.array([base + d * length * t for t in np.linspace(0, 1, 4 if lod == 0 else 2)])
    rad = width * np.linspace(1, 0.08, len(pts))
    return geo.tube(pts, rad, sides=4, mat='splinter', part=geo.frame(seed=seed), caps=False,
                    rnoise=lambda th, s: 1 + 0.4 * np.cos(th * 2))


def shattered_tree(H=360, R=12.0, seed=0, lod=0, branches=4, roots=5, crown=True, stripped=0.3):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    pts = trunk_path(H, seed, n=max(6, int(H / (12 if lod == 0 else 40))))
    z = pts[:, 2]
    rad = R * (1 - 0.35 * np.clip(z / max(H, 1), 0, 1)) * (1 + 0.55 * np.exp(-np.clip(z, 0, None) / 14.0))
    sides = 14 if lod == 0 else 7
    jag = rng.uniform(0, 2 * np.pi)
    part = geo.frame(seed=seed, stripped=stripped)
    def rn(th, s):
        # fluted trunk, buttresses near the ground
        base = 1 + 0.06 * np.sin(th * 5 + seed) + 0.04 * np.sin(th * 11 + seed * 2)
        flare = np.exp(-max(s - 10, 0) / 18.0)
        return base + flare * 0.25 * np.maximum(np.sin(th * roots + seed), 0) ** 2
    tr = geo.tube(pts, rad, sides=sides, mat='bark', part=part, caps=False, rnoise=rn)
    # jagged top rim: lift the top rings by an angle-dependent tear
    top_z = pts[-1, 2]
    zr = tr.V[:, 2]
    near_top = np.clip((zr - (top_z - 24)) / 24.0, 0, 1)
    ang = np.arctan2(tr.V[:, 1] - pts[-1, 1], tr.V[:, 0] - pts[-1, 0])
    tear = np.abs(perlin(np.cos(ang + jag) * 1.7 + seed, np.sin(ang + jag) * 1.7, 0.5)) * 34 * (1 if crown else 0.3)
    tr.V[:, 2] += near_top ** 2 * (tear - 10)
    tr.recompute_normals(angle=70)
    m.add(tr)
    # broken core: a splintered cone inside the top
    c = pts[-1].copy()
    nth = sides
    th = np.linspace(0, 2 * np.pi, nth + 1)
    rho = np.linspace(0, 1, 5 if lod == 0 else 2)
    TH, RH = np.meshgrid(th, rho, indexing='ij')
    rtop = rad[-1] * 0.94
    spikes = np.abs(perlin(np.cos(TH + jag) * 2.3 + seed * 1.1, np.sin(TH + jag) * 2.3, RH * 1.5)) * 40
    Z = top_z - 8 + (1 - RH) * 6 + spikes * np.sin(RH * np.pi) * 0.9 + 10 * RH
    P = np.stack([c[0] + np.cos(TH) * rtop * (1 - RH * 0.97), c[1] + np.sin(TH) * rtop * (1 - RH * 0.97), Z], -1)
    core = geo.surface(P, 'splinter', geo.frame(seed=seed + 1))
    cen = core.V[core.F].mean(1)
    if (core.face_normals()[:, 2]).mean() < 0: core.F = core.F[:, ::-1]
    core.recompute_normals(angle=75)
    m.add(core)
    if crown and lod == 0:
        for k in range(rng.randint(3, 7) if H > 100 else rng.randint(2, 4)):
            a = rng.uniform(0, 2 * np.pi)
            base = c + np.array([np.cos(a), np.sin(a), 0]) * rtop * rng.uniform(0.3, 0.9) + np.array([0, 0, rng.uniform(-8, 4)])
            d = np.array([np.cos(a) * rng.uniform(0.05, 0.5), np.sin(a) * rng.uniform(0.05, 0.5), 1])
            m.add(splinter_shard(base, d, rng.uniform(8, 40) * (1 if H > 100 else 0.45), rng.uniform(1.2, 3.0), seed * 31 + k))
    # broken branches
    for k in range(branches):
        zb = rng.uniform(0.35, 0.92) * H
        i = np.searchsorted(z, zb); i = min(i, len(pts) - 1)
        a = rng.uniform(0, 2 * np.pi)
        rb = rng.uniform(1.8, 4.2) * (R / 12)
        L = rng.uniform(18, 70)
        d = np.array([np.cos(a), np.sin(a), rng.uniform(0.2, 0.9)]); d /= np.linalg.norm(d)
        p0 = pts[i] + np.array([np.cos(a), np.sin(a), 0]) * rad[i] * 0.6
        bp = np.array([p0 + d * L * t + np.array([0, 0, -L * 0.1 * t * t]) for t in np.linspace(0, 1, 5 if lod == 0 else 2)])
        m.add(geo.tube(bp, rb * np.linspace(1, 0.55, len(bp)), sides=7 if lod == 0 else 4, mat='bark', part=geo.frame(seed=seed * 7 + k, stripped=stripped),
                       caps=False))
        if lod == 0:
            tip = bp[-1]
            for j in range(3):
                dd = d + rng.normal(0, 0.25, 3)
                m.add(splinter_shard(tip - d * 1.5, dd, rng.uniform(4, 12), rb * 0.45, seed * 91 + k * 5 + j))
    # roots spreading into the ground
    for k in range(roots):
        a = 2 * np.pi * k / roots + rng.uniform(-0.3, 0.3) + seed
        L = rng.uniform(14, 26) * (R / 12)
        rp = np.array([[np.cos(a) * (R * 0.55 + L * t), np.sin(a) * (R * 0.55 + L * t), 12 - 26 * t ** 0.8]
                       for t in np.linspace(0, 1, 5 if lod == 0 else 2)])
        m.add(geo.tube(rp, R * 0.5 * np.linspace(1, 0.3, len(rp)), sides=7 if lod == 0 else 4, mat='bark', part=geo.frame(seed=seed * 13 + k), caps=False))
    hull = [np.vstack([pts[0] + np.array([np.cos(t) * R * 1.1, np.sin(t) * R * 1.1, 10]) for t in np.linspace(0, 2 * np.pi, 9)]
                      + [pts[-1] + np.array([np.cos(t) * rad[-1], np.sin(t) * rad[-1], 0]) for t in np.linspace(0, 2 * np.pi, 9)])]
    return m, hull


def fallen_log(L=260, R=10, seed=0, lod=0):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    n = int(L / (14 if lod == 0 else 50))
    x = np.linspace(-L / 2, L / 2, n + 1)
    pts = np.stack([x, 4 * np.sin(x * 0.01 + seed), R * 0.75 + 2 * np.sin(x * 0.02)], 1)
    rad = R * (1 - 0.3 * (x + L / 2) / L)
    tr = geo.tube(pts, rad, sides=12 if lod == 0 else 6, mat='bark', part=geo.frame(seed=seed, stripped=0.5), caps=False,
                  rnoise=lambda th, s: 1 + 0.05 * np.sin(th * 5) + 0.04 * np.sin(th * 9 + s * 0.05))
    m.add(tr)
    # splintered break at +x, root plate at -x
    for end, sgn in ((pts[-1], 1), (pts[0], -1)):
        if sgn > 0:
            for k in range(6 if lod == 0 else 0):
                a = rng.uniform(0, 2 * np.pi)
                b = end + np.array([0, np.cos(a), np.sin(a)]) * rad[-1] * rng.uniform(0.2, 0.8)
                m.add(splinter_shard(b, [1, rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3)], rng.uniform(8, 26), rng.uniform(1.0, 2.2), seed * 7 + k))
            th = np.linspace(0, 2 * np.pi, 13)
            ring = end + np.stack([np.zeros_like(th), np.cos(th), np.sin(th)], 1)[:-1] * rad[-1]
            m.add(geo.disk(end + np.array([4, 0, 0]), ring, [1, 0, 0], 'splinter'))
        else:
            for k in range(7):
                a = 2 * np.pi * k / 7
                rp = np.array([end + np.array([-t * 8, np.cos(a) * (R * 0.6 + 16 * t), np.sin(a) * (R * 0.6 + 16 * t)]) for t in np.linspace(0, 1, 4)])
                rp[:, 2] = np.maximum(rp[:, 2], -6)
                m.add(geo.tube(rp, R * 0.45 * np.linspace(1, 0.35, 4), sides=6 if lod == 0 else 4, mat='bark', part=geo.frame(seed=seed + 40 + k), caps=False))
            # root ball of earth
            th = np.linspace(0, 2 * np.pi, 17)
            ph = np.linspace(-np.pi / 2, np.pi / 2, 9)
            TH, PH = np.meshgrid(th, ph, indexing='ij')
            rr = R * 2.3 * (1 + 0.25 * perlin(np.cos(TH) * 2 + seed, np.sin(TH) * 2, PH))
            P = np.stack([end[0] - 6 + rr * np.sin(PH) * 0.35, end[1] + rr * np.cos(PH) * np.cos(TH), np.maximum(end[2] + rr * np.cos(PH) * np.sin(TH), -6)], -1)
            ball = geo.surface(P, 'earth', geo.frame(seed=seed + 99))
            c = ball.V[ball.F].mean(1) - (end + np.array([-6, 0, 0]))
            if np.einsum('ij,ij->i', ball.face_normals(), c).mean() < 0: ball.F = ball.F[:, ::-1]
            ball.recompute_normals()
            m.add(ball)
    hull = [np.array([[xx, yy, zz] for xx in (-L / 2, L / 2) for yy in (-R, R) for zz in (0, R * 1.6)])]
    return m, hull


def specs():
    sh = {'bark': S.bark, 'splinter': S.splinter, 'earth': S.earth}
    out = {}
    defs = [('tree_shattered_a', dict(H=380, R=13, seed=21, branches=5)), ('tree_shattered_b', dict(H=270, R=11, seed=22, branches=3, stripped=0.6)),
            ('tree_shattered_c', dict(H=170, R=14, seed=23, branches=2, roots=6)), ('tree_shattered_d', dict(H=460, R=12, seed=24, branches=6, stripped=0.15)),
            ('stump_a', dict(H=46, R=13, seed=25, branches=0, roots=6)), ('stump_b', dict(H=26, R=10, seed=26, branches=0, roots=5, stripped=0.5))]
    for name, kw in defs:
        m0, hull = shattered_tree(lod=0, **kw); m1, _ = shattered_tree(lod=1, **kw)
        out[name] = dict(lods=[m0, m1], lod_thresholds=[0.0, 30.0], size=2048 if kw['H'] > 300 else 1024, ground=0.0, shaders=sh, surface='wood', hulls=hull, res=1.5)
    m0, hull = fallen_log(seed=27); m1, _ = fallen_log(seed=27, lod=1)
    out['log_fallen'] = dict(lods=[m0, m1], lod_thresholds=[0.0, 30.0], size=1024, ground=0.0, shaders=sh, surface='wood', hulls=hull, res=1.5)
    return out
