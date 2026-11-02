"""Barbed wire: screw pickets, entanglement fences, concertina coils, cheval de frise."""
import numpy as np
import geo
from noise import fbm
import shaders as S


def picket(x, y, h=54, seed=0, lod=0, lean=(0, 0)):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    n = 8 if lod == 0 else 2
    zs = np.linspace(-4, h, n + 1)
    bend = rng.uniform(-1.5, 1.5)
    pts = np.stack([x + lean[0] * zs / 60 + bend * (zs / h) ** 2, y + lean[1] * zs / 60, zs], 1)
    m.add(geo.tube(pts, 0.55, sides=6 if lod == 0 else 4, mat='iron', part=geo.frame(seed=seed)))
    if lod == 0:
        for zh in (14, 30, 46, h - 1):
            th = np.linspace(0, 2 * np.pi, 13)
            c = np.array([x + lean[0] * zh / 60 + bend * (zh / h) ** 2, y + lean[1] * zh / 60 + 1.6, zh])
            ring = c + np.stack([np.cos(th) * 0.2, np.sin(th) * 1.4 - 0.2, np.sin(th) * 1.2 * 0.0 + np.cos(th) * 1.0], 1)
            m.add(geo.tube(ring, 0.3, sides=4, mat='iron', part=geo.frame(seed=seed + 1), caps=False))
    return m


def strand(a, b, sag=2.0, seed=0, lod=0, barbs=True, wob=0.8):
    rng = np.random.RandomState(seed)
    a = np.asarray(a, float); b = np.asarray(b, float)
    L = np.linalg.norm(b - a)
    n = max(4, int(L / (2.0 if lod == 0 else 8.0)))
    t = np.linspace(0, 1, n + 1)
    pts = a[None] + (b - a)[None] * t[:, None]
    pts[:, 2] -= sag * 4 * t * (1 - t)
    w = fbm(t * 3 + seed, seed, 0.3, 2, seed=seed % 50)[:, None] * wob
    side = np.cross(b - a, [0, 0, 1.0]); side /= np.linalg.norm(side) + 1e-9
    pts += side[None] * w * np.sin(t * np.pi)[:, None] + np.array([0, 0, 1.0]) * 0.4 * w * np.sin(t * np.pi)[:, None]
    m = geo.Mesh()
    if lod == 0:
        # two twisted wires
        T, N, B = geo.path_frames(pts)
        s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
        fine = np.linspace(0, s[-1], max(8, int(s[-1] / 0.85)) + 1)
        P = np.stack([np.interp(fine, s, pts[:, k]) for k in range(3)], 1)
        T, N, B = geo.path_frames(P)
        for ph in (0, np.pi):
            ang = fine * 2 * np.pi / 1.6 + ph
            q = P + (np.cos(ang)[:, None] * N + np.sin(ang)[:, None] * B) * 0.11
            m.add(geo.tube(q, 0.085, sides=3, mat='wire', part=geo.frame(seed=seed), caps=False))
        if barbs:
            k = 2.0
            while k < s[-1] - 1:
                i = np.searchsorted(fine, k); c = P[min(i, len(P) - 1)]; tt = T[min(i, len(P) - 1)]
                r1 = np.cross(tt, [0, 0, 1.0]); r1 /= np.linalg.norm(r1) + 1e-9; r2 = np.cross(tt, r1)
                rot = rng.uniform(0, np.pi)
                for d in ((np.cos(rot) * r1 + np.sin(rot) * r2), (-np.sin(rot) * r1 + np.cos(rot) * r2)):
                    m.add(geo.tube([c - d * 0.75 + tt * 0.15, c + d * 0.75 - tt * 0.15], [0.06, 0.03], sides=3, mat='wire', part=geo.frame(seed=seed), caps=False))
                k += 5.5 + rng.uniform(-0.5, 0.5)
    else:
        m.add(geo.tube(pts, 0.2, sides=3, mat='wire', part=geo.frame(seed=seed), caps=False))
    return m


def fence(lod=0, seed=0, length=128):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    xs = [-length / 4 + rng.uniform(-6, 6), length / 4 + rng.uniform(-6, 6)]
    heights = [52 + rng.uniform(-3, 3), 52 + rng.uniform(-3, 3)]
    for k, (x, h) in enumerate(zip(xs, heights)):
        m.add(picket(x, 0, h, seed=seed * 10 + k, lod=lod, lean=(rng.uniform(-4, 4), rng.uniform(-6, 6))))
    # horizontal strands through the pickets, ends fixed so neighbours line up
    for j, z in enumerate((8, 20, 32, 44)):
        pts = [(-length / 2, 0, z), (xs[0], 1.4, z + rng.uniform(-1, 1)), (xs[1], 1.4, z + rng.uniform(-1, 1)), (length / 2, 0, z)]
        for a, b in zip(pts[:-1], pts[1:]):
            m.add(strand(a, b, sag=rng.uniform(1.0, 3.0), seed=seed * 100 + j * 7 + int(a[0]), lod=lod))
    # diagonals and an apron toward the enemy (+y)
    for k in range(2):
        x = xs[k]
        m.add(strand((x, 1.4, heights[k] - 2), (x - 30, 38, 1), sag=1.5, seed=seed * 300 + k, lod=lod))
        m.add(strand((x, 1.4, heights[k] - 2), (x + 30, 38, 1), sag=1.5, seed=seed * 300 + k + 5, lod=lod))
        m.add(strand((x, 1.4, 30), (x + rng.uniform(-40, 40), -34, 1), sag=1.0, seed=seed * 300 + k + 9, lod=lod))
    m.add(strand((-length / 2, 0, 44), (length / 2, 0, 8), sag=2, seed=seed * 400 + 1, lod=lod))
    m.add(strand((-length / 2, 0, 8), (length / 2, 0, 44), sag=2, seed=seed * 400 + 2, lod=lod))
    return m


def coil(lod=0, seed=0, length=128, R=17):
    rng = np.random.RandomState(seed)
    loops = int(length / 6.5)
    n = loops * (28 if lod == 0 else 8)
    t = np.linspace(0, 1, n + 1)
    ang = t * loops * 2 * np.pi
    x = -length / 2 + t * length + 2.0 * np.sin(ang)
    rr = R * (1 + 0.08 * fbm(t * 9 + seed, 0, 0, 2, seed=3)) * (1 + 0.1 * np.sin(ang * 0.5 + seed))
    y = rr * np.cos(ang); z = R + rr * np.sin(ang) * 0.92 - 1
    pts = np.stack([x, y, z], 1)
    m = geo.Mesh()
    segs = np.array_split(np.arange(len(pts)), max(1, loops // 3))
    for k, idx in enumerate(segs):
        idx = np.arange(max(idx[0] - 1, 0), idx[-1] + 1)
        p = pts[idx]
        if lod == 0:
            m.add(geo.tube(p, 0.13, sides=3, mat='wire', part=geo.frame(seed=seed + k), caps=False))
        else:
            m.add(geo.tube(p[::1], 0.22, sides=3, mat='wire', part=geo.frame(seed=seed + k), caps=False))
    if lod == 0:
        T, N, B = geo.path_frames(pts)
        for i in range(3, len(pts), 9):
            c = pts[i]; tt = T[i]
            r1 = np.cross(tt, [0, 0, 1.0]); r1 /= np.linalg.norm(r1) + 1e-9
            m.add(geo.tube([c - r1 * 0.7, c + r1 * 0.7], [0.06, 0.03], sides=3, mat='wire', part=geo.frame(seed=seed), caps=False))
    # pickets holding the coil
    for k, xx in enumerate((-length / 3, length / 3)):
        m.add(picket(xx + rng.uniform(-4, 4), -R - 2, 2 * R + 6, seed=seed + 50 + k, lod=lod))
    return m


def cheval(lod=0, seed=0):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    beam = np.array([[-48, 0, 22], [48, 0, 22]], float)
    m.add(geo.tube(np.linspace(beam[0], beam[1], 8), 3.2, sides=10 if lod == 0 else 6, mat='bark', part=geo.frame(seed=seed, stripped=0.8)))
    for k, x in enumerate(np.linspace(-40, 40, 5)):
        for s in (-1, 1):
            a = np.radians(45 * s + rng.uniform(-6, 6))
            d = np.array([0, np.cos(a), np.sin(a)])
            p0 = np.array([x, 0, 22]) - d * 32; p1 = np.array([x, 0, 22]) + d * 32
            pts = np.linspace(p0, p1, 6)
            rad = np.array([0.4, 1.7, 1.9, 1.9, 1.7, 0.4])
            m.add(geo.tube(pts, rad, sides=7 if lod == 0 else 4, mat='bark', part=geo.frame(seed=seed * 9 + k * 2 + s, stripped=0.9)))
    # wire wrapped between the stake tips
    tips = []
    for x in np.linspace(-40, 40, 5):
        for s in (-1, 1):
            a = np.radians(45 * s)
            tips.append((x, np.cos(a) * 29, 22 + np.sin(a) * 29))
            tips.append((x, -np.cos(a) * 29, 22 - np.sin(a) * 29))
    order = sorted(tips, key=lambda p: (np.arctan2(p[2] - 22, p[1]), p[0]))
    for i in range(0, len(tips) - 1):
        a, b = tips[i], tips[(i + 4) % len(tips)]
        m.add(strand(a, b, sag=1.0, seed=seed * 50 + i, lod=lod, wob=1.5))
    return m


def specs():
    iron = lambda c: S.rust_steel(c, mud_top=8)
    sh = {'wire': S.wire, 'iron': iron, 'bark': S.bark}
    out = {}
    out['wire_fence_a'] = dict(lods=[fence(0, 1), fence(1, 1)], size=512, ground=0.0, metal=True, shaders=sh, surface='metal', hulls=[], res=1.0)
    out['wire_fence_b'] = dict(lods=[fence(0, 2), fence(1, 2)], size=512, ground=0.0, metal=True, shaders=sh, surface='metal', hulls=[], res=1.0)
    out['wire_coil'] = dict(lods=[coil(0, 3), coil(1, 3)], size=512, ground=0.0, metal=True, shaders=sh, surface='metal', hulls=[], res=1.0)
    out['cheval'] = dict(lods=[cheval(0, 4), cheval(1, 4)], size=1024, ground=0.0, metal=True, shaders=sh, surface='wood',
                         hulls=[np.array([[x, y, z] for x in (-48, 48) for y in (-24, 24) for z in (0, 46)])])
    return out
