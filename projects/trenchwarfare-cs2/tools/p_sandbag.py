"""Sandbag parapet segments: burlap bags laid as headers with a stretcher course on top."""
import numpy as np
import geo
from noise import fbm, hash01
import shaders as S


def bag(L=20.0, W=10.0, H=5.6, seed=0, squash=0.0, lod=0):
    rng = np.random.RandomState(seed)
    seg, div = ((1, (3, 1, 1)) if lod == 0 else (1, (1, 1, 1)))
    part = geo.frame(seed=seed, tone=rng.uniform(0, 1), mud_top=7.0)
    m = geo.rbox(L, W, H, r=min(2.4, H * 0.45), seg=seg, mat='burlap', part=part, div=div)
    V = m.V
    x = V[:, 0] / (L / 2); y = V[:, 1] / (W / 2); z = V[:, 2] / (H / 2)
    # pillow: thicker in the middle, thinner at the ends; heavier bags spread
    V[:, 2] *= (1 - 0.32 * x ** 4) * (1 - 0.15 * y ** 4) * (1 - squash * 0.35)
    V[:, 1] *= 1 + squash * 0.18 * (1 - z ** 2)
    V[:, 0] *= 1 + squash * 0.06
    # tied end: gather the +x end into a neck with ears
    tie = np.clip((x - 0.72) / 0.28, 0, 1)
    V[:, 1] *= 1 - 0.35 * tie ** 2
    V[:, 2] *= 1 - 0.62 * tie ** 2
    V[:, 0] += 1.2 * tie ** 3
    # flat bottom (resting), lumps
    V[:, 2] = np.where(z < -0.4, V[:, 2] * 0.85 - 0.2, V[:, 2])
    n = fbm(V[:, 0] * 0.18 + seed, V[:, 1] * 0.18, V[:, 2] * 0.18, 3, seed=seed % 97)
    nrm0 = V / (np.linalg.norm(V, axis=1, keepdims=True) + 1e-6)
    V += nrm0 * n[:, None] * 1.0
    m.V = V
    m.V[:, 2] += H / 2 * (1 - squash * 0.35)
    m.recompute_normals(angle=70)
    return m


def wall(length=64, courses=3, lod=0, seed=1, top=True, tilt=0.0):
    """headers (long axis along +y, into the bank) along x; y=0 is the trench-side face"""
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    hulls = []
    z = 0.0
    Hb = 5.4
    for c in range(courses):
        n = int(np.ceil(length / 10.0))
        off = (c % 2) * 5.0
        squash = 0.25 * (courses - c) / courses
        for i in range(n + 1):
            x = -length / 2 + off + i * 10.0 + rng.uniform(-0.6, 0.6)
            if x < -length / 2 - 2 or x > length / 2 + 2: continue
            b = bag(20 + rng.uniform(-1, 1.5), 10 + rng.uniform(-0.5, 0.8), Hb, seed=seed * 1000 + c * 50 + i, squash=squash, lod=lod)
            ang = rng.uniform(-6, 6); pitch = rng.uniform(-3, 3) - tilt
            b.transform(geo.euler(90 + ang + (180 if rng.rand() < 0.5 else 0), pitch, rng.uniform(-2, 2)),
                        (x, 10.0 - c * 1.2 + rng.uniform(-0.8, 0.8), z))
            m.add(b)
        z += Hb * (1 - squash * 0.35) - 0.6
    if top:
        for i in range(int(length // 20) + 1):
            x = -length / 2 + 10 + i * 20 + rng.uniform(-1, 1)
            if x > length / 2 + 4: continue
            b = bag(20 + rng.uniform(-1, 1), 10.5, Hb, seed=seed * 1000 + 900 + i, squash=0.05, lod=lod)
            b.transform(geo.euler(rng.uniform(-5, 5) + (180 if rng.rand() < 0.5 else 0), rng.uniform(-3, 3) - tilt, 0), (x, 6.0 - courses * 1.2, z))
            m.add(b)
        z += Hb - 0.8
    return m, z


def spec(variant=0, courses=3, length=64):
    m0, h = wall(length=length, courses=courses, lod=0, seed=11 + variant)
    m1, _ = wall(length=length, courses=courses, lod=1, seed=11 + variant)
    lo, hi = m0.bounds()
    return dict(lods=[m0, m1], lod_thresholds=[0.0, 25.0], size=1024 if length <= 64 else 2048, ground=0.0, surface='sand',
                shaders={'burlap': S.burlap},
                hulls=[np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (0.0, hi[1]) for z in (0.0, hi[2] - 1.5)])])
