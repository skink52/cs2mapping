"""Small trench-life props: staved bucket, water barrel (standing / on its side), brazier, trench bench, tin pile, box periscope,
gas-alarm gong, entrenching tools (shovel, pick) leaning, spare-plank stack, hurricane lantern, loose sandbag pile, wire reel."""
import numpy as np
import geo
import shaders as S
from noise import fbm

IRON = lambda c: S.rust_steel(c, mud_top=2, edge_k=0.6)
TIN = lambda c: S.painted_steel(c, S._c(0.42, 0.40, 0.30), chip=0.45, mud_top=1, edge_k=0.7)
W = lambda c: S.wood(c, mud_top=3, wet=0.35)
ROPE = lambda c: S.canvas(c, base=S._c(0.55, 0.47, 0.33), mud_top=0)


def glass(c):
    n = c.n
    soot = np.clip(0.5 + 0.5 * fbm(c.P[:, 0] * 0.5, c.P[:, 1] * 0.5, c.P[:, 2] * 0.3, 3, seed=89), 0, 1)
    return dict(color=S.mix(S._c(0.42, 0.40, 0.33), S._c(0.10, 0.09, 0.08), soot * 0.8 + 0.2 * (c.P[:, 2] > 5.5)), rough=np.full(n, 0.15, np.float32), metal=np.zeros(n, np.float32), height=np.zeros(n, np.float32))


def coals(c):
    P = c.P
    g = fbm(P[:, 0] * 0.6, P[:, 1] * 0.6, P[:, 2] * 0.6, 3, seed=88)
    col = S.mix(S._c(0.05, 0.04, 0.04), S._c(0.55, 0.16, 0.04), np.clip(g * 1.4, 0, 1) ** 2)
    return dict(color=col, rough=np.full(c.n, 0.95, np.float32), metal=np.zeros(c.n, np.float32), height=0.3 * g)


def staved(r_of_z, z0, z1, n=14, gap=0.035, mat='wood', seed=0, lod=0, nz=8):
    """barrel/bucket wall of separate staves (seams visible)"""
    m = geo.Mesh()
    zs = np.linspace(z0, z1, nz + 1 if lod == 0 else 3)
    for k in range(n):
        a0 = 2 * np.pi * k / n + gap / 2; a1 = 2 * np.pi * (k + 1) / n - gap / 2
        th = np.linspace(a0, a1, 3 if lod == 0 else 2)
        TH, Z = np.meshgrid(th, zs, indexing='ij')
        R = r_of_z(Z) * (1 + 0.012 * np.sin(k * 2.3 + seed))
        P = np.stack([R * np.cos(TH), R * np.sin(TH), Z], -1)
        am = (a0 + a1) / 2
        fr = geo.frame(R=geo.rot('z', np.degrees(am)) @ geo.rot('y', -90), o=(0, 0, 0), seed=seed * 31 + k, tone=(k * 0.37) % 1)
        s = geo.surface(P, mat, fr)
        c = s.V[s.F].mean(1); c[:, 2] = 0
        if np.einsum('ij,ij->i', s.face_normals(), c).mean() < 0: s.F = s.F[:, ::-1]
        s.recompute_normals(angle=50); m.add(s)
        inner = geo.surface(P * np.array([0.93, 0.93, 1.0]), mat, dict(fr, R=fr['R'].copy(), o=fr['o'].copy()))
        ci = inner.V[inner.F].mean(1); ci[:, 2] = 0
        if np.einsum('ij,ij->i', inner.face_normals(), ci).mean() > 0: inner.F = inner.F[:, ::-1]
        inner.recompute_normals(angle=50); m.add(inner)
    return m


def hoop(r, z, w=0.9, t=0.25, mat='iron', seed=0, sides=24):
    return geo.lathe([(r, z - w / 2), (r + t, z - w / 2), (r + t, z + w / 2), (r, z + w / 2)], sides, mat, geo.frame(seed=seed))


def disk(r, z, mat, seed=0, sides=20, up=True):
    ring = [(np.cos(a) * r, np.sin(a) * r, z) for a in np.linspace(0, 2 * np.pi, sides, endpoint=False)]
    d = geo.disk(np.array([0, 0, z]), np.array(ring), np.array([0, 0, 1.0 if up else -1.0]), mat, geo.frame(seed=seed))
    return d


def bucket(lod=0, seed=0):
    rb, rt, H = 5.0, 6.2, 11.0
    rz = lambda z: rb + (rt - rb) * z / H
    m = staved(rz, 0, H, n=12, seed=seed, lod=lod)
    for z in (1.5, H - 1.6):
        m.add(hoop(rz(z) + 0.05, z, mat='iron', seed=seed + int(z)))
    m.add(disk(rb * 0.95, 0.6, 'wood', seed))
    m.add(disk(rb * 0.98, 6.0, 'water', seed + 3))            # muddy water inside
    th = np.linspace(0, np.pi, 12)
    pts = np.stack([np.cos(th) * (rt + 0.3), np.zeros(12), H + np.sin(th) * 5.5], 1)
    m.add(geo.tube(pts, 0.3, sides=6, mat='rope', part=geo.frame(seed=seed)))
    return m


def barrel(lod=0, seed=0):
    H, r0, r1 = 30.0, 9.0, 10.6
    rz = lambda z: r0 + (r1 - r0) * np.sin(np.pi * z / H)
    m = staved(rz, 0, H, n=16, seed=seed, lod=lod, nz=10)
    for z in (2.5, 8.0, H - 8.0, H - 2.5):
        m.add(hoop(rz(z) + 0.05, z, w=1.2, mat='iron', seed=seed + int(z)))
    m.add(disk(r0 * 0.93, H - 1.2, 'wood', seed + 1))          # head, slightly sunk
    m.add(disk(r0 * 0.93, 1.0, 'wood', seed + 2, up=False))
    # tin cup hanging on the rim
    cup = geo.lathe([(0.01, 0), (1.4, 0), (1.5, 2.6), (1.3, 2.6), (0.01, 0.3)], 12, 'tin', geo.frame(seed=seed))
    cup.transform(geo.rot('x', 90), (0, -r0 - 1.0, H - 3.0)); m.add(cup)
    return m


def brazier(lod=0, seed=0):
    m = geo.Mesh()
    body = geo.lathe([(6.5, 8), (7.2, 8), (7.6, 24), (6.9, 24), (6.2, 9)], 18, 'iron', geo.frame(seed=seed))
    m.add(body)
    for k in range(3):
        a = 2 * np.pi * k / 3
        m.add(geo.tube([(np.cos(a) * 6.8, np.sin(a) * 6.8, 9), (np.cos(a) * 9.5, np.sin(a) * 9.5, 0)], 0.5, sides=6, mat='iron', part=geo.frame(seed=seed + k)))
    m.add(disk(7.0, 21.5, 'coals', seed))
    # punched air holes in three rows
    for row, z in enumerate((12.5, 16.0, 19.5)):
        for k in range(10):
            a = 2 * np.pi * (k + 0.5 * row) / 10
            r = 6.4 + (7.4 - 6.4) * (z - 8) / 16 + 0.08
            h = geo.rbox(0.25, 1.3, 1.3, r=0.1, seg=1, mat='hole', part=geo.frame(seed=seed), center=(0, 0, 0))
            h.transform(geo.rot('z', np.degrees(a)), (np.cos(a) * r, np.sin(a) * r, z))
            m.add(h)
    rng = np.random.RandomState(seed)
    for k in range(9):
        a = rng.uniform(0, 2 * np.pi); r = rng.uniform(0, 4.5)
        c = geo.rbox(rng.uniform(1.5, 2.6), rng.uniform(1.2, 2.2), rng.uniform(1.0, 1.8), r=0.4, seg=1, mat='coals', part=geo.frame(seed=seed + k),
                     center=(np.cos(a) * r, np.sin(a) * r, 22.2))
        m.add(c)
    return m


def bench(lod=0, seed=0, L=56):
    m = geo.Mesh()
    m.add(geo.plank(L, 9.5, 1.6, mat='wood', seg=2, div=(4, 1, 1), warp=0.3, seed=seed, t=(0, 0, 16.2), tone=0.4))
    for x in (-L / 2 + 6, L / 2 - 6):
        for sy in (-1, 1):
            m.add(geo.plank(17.5, 3.0, 1.6, mat='wood', seg=1, div=(2, 1, 1), seed=seed + int(x) + sy,
                            R=geo.euler(0, -90 + sy * 12, 90), t=(x, sy * 2.2, 8.0), tone=0.6))
        m.add(geo.plank(9, 2.5, 1.2, mat='wood', seg=1, div=(1, 1, 1), seed=seed + 7 + int(x), R=geo.euler(90, 0, 0), t=(x, 0, 5.0), tone=0.3))
    return m


def tins(lod=0, seed=0):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    spots = [(0, 0), (4.4, 0.6), (-4.2, 1.0), (1.0, 4.2), (-1.5, -4.0), (5.5, -4.5)]
    for k, (x, y) in enumerate(spots):
        h = rng.uniform(4.0, 5.5); r = rng.uniform(1.9, 2.3)
        t = geo.lathe([(0.01, 0), (r, 0), (r + 0.1, 0.3), (r, 0.5), (r, h - 0.5), (r + 0.1, h - 0.3), (r, h), (0.01, h)], 14 if lod == 0 else 8,
                      'tin', geo.frame(seed=seed + k))
        if k == 5: t.transform(geo.rot('x', 90), (x, y, r))
        else: t.transform(t=(x, y, 0))
        m.add(t)
    t = geo.lathe([(0.01, 0), (2.1, 0), (2.1, 4.8), (0.01, 4.8)], 12, 'tin', geo.frame(seed=seed + 9))
    t.transform(t=(0.5, 0.3, 5.5)); m.add(t)
    return m


def periscope(lod=0, seed=0):
    """box periscope leaning on the parapet: long wooden box with two mirror windows"""
    m = geo.Mesh()
    L = 42.0
    m.add(geo.rbox(3.2, 4.0, L, r=0.3, seg=1, mat='wood', part=geo.frame(seed=seed, tone=0.6), center=(0, 0, L / 2), div=(1, 1, 4)))
    m.add(geo.rbox(0.4, 3.0, 3.6, r=0.1, seg=1, mat='glass', part=geo.frame(seed=seed), center=(-1.65, 0, L - 3.0)))
    m.add(geo.rbox(0.4, 3.0, 3.6, r=0.1, seg=1, mat='glass', part=geo.frame(seed=seed), center=(1.65, 0, 4.0)))
    for z in (8, L - 10):
        m.add(geo.rbox(3.5, 4.3, 0.6, r=0.1, seg=1, mat='tin', part=geo.frame(seed=seed + z), center=(0, 0, z)))
    m.transform(geo.rot('y', -16))
    return m


def gong(lod=0, seed=0):
    """gas alarm: an empty shell case hanging from a post, a striker on a cord"""
    m = geo.Mesh()
    m.add(geo.tube([(0, 0, 0), (0, 0, 64)], 1.8, sides=8, mat='bark', part=geo.frame(seed=seed)))
    m.add(geo.tube([(0, 0, 60), (11, 0, 60)], 1.0, sides=6, mat='wood', part=geo.frame(seed=seed + 1)))
    m.add(geo.tube([(9.5, 0, 60), (9.5, 0, 52)], 0.15, sides=4, mat='iron', part=geo.frame(seed=seed)))
    case = geo.lathe([(0.01, 0), (3.6, 0), (3.6, 0.6), (3.3, 0.8), (3.3, 13.5), (3.0, 14), (2.9, 14)], 18, 'brass', geo.frame(seed=seed))
    case.transform(geo.rot('x', 180), (9.5, 0, 52)); m.add(case)
    m.add(geo.tube([(1.5, 0, 45), (6, 2, 38)], 0.12, sides=4, mat='rope', part=geo.frame(seed=seed)))
    m.add(geo.rbox(1.0, 1.0, 9, r=0.2, seg=1, mat='iron', part=geo.frame(seed=seed + 2), center=(6.3, 2.2, 33)))
    return m


def shovel(lod=0, seed=0):
    m = geo.Mesh()
    m.add(geo.tube([(0, 0, 9), (0, 0, 44)], 0.75, sides=7, mat='wood', part=geo.frame(seed=seed)))
    m.add(geo.tube([(-2.3, 0, 44), (2.3, 0, 44)], 0.55, sides=6, mat='wood', part=geo.frame(seed=seed + 1)))
    blade = geo.prism([(-4.2, 0), (4.2, 0), (4.6, 9), (0, 11.5), (-4.6, 9)], -0.18, 0.18, 'iron', geo.frame(seed=seed))
    blade.transform(geo.rot('z', 90)); m.add(blade)
    return m


def pick(lod=0, seed=0):
    m = geo.Mesh()
    m.add(geo.tube([(0, 0, 0), (0, 0, 34)], [0.9, 1.1], sides=7, mat='wood', part=geo.frame(seed=seed)))
    m.add(geo.tube([(-12, 0, 32.5), (-6, 0, 34.5), (0, 0, 35), (6, 0, 34.5), (12, 0, 32.0)], [0.15, 0.8, 1.2, 0.8, 0.3], sides=6, mat='iron', part=geo.frame(seed=seed)))
    return m


def tools_lean(lod=0, seed=0):
    m = geo.Mesh()
    a = shovel(lod, seed); a.transform(geo.euler(0, 0, -14), (-5, 0, 0)); m.add(a)
    b = pick(lod, seed + 1); b.transform(geo.euler(80, 0, -12), (6, -1, 0)); m.add(b)
    return m


def planks_stack(lod=0, seed=0):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    z = 0.6
    for k in range(5):
        w = rng.uniform(6.5, 8.5)
        m.add(geo.plank(rng.uniform(52, 62), w, 1.2, mat='wood', seg=1, div=(3, 1, 1), warp=0.4, seed=seed + k,
                        R=geo.euler(rng.uniform(-6, 6), 0, 0), t=(rng.uniform(-2, 2), rng.uniform(-3, 3), z), tone=rng.rand()))
        z += 1.25
    for x in (-18, 18):
        m.add(geo.rbox(4, 12, 2.5, r=0.4, seg=1, mat='wood', part=geo.frame(seed=seed + 40 + x, tone=0.8), center=(x, 0, -0.6)))
    m.transform(t=(0, 0, 1.9))
    return m


def lantern(lod=0, seed=0):
    m = geo.Mesh()
    m.add(geo.lathe([(0.01, 0), (2.6, 0), (2.8, 1.0), (2.6, 1.8), (1.4, 2.2)], 14, 'tin', geo.frame(seed=seed)))
    m.add(geo.lathe([(1.4, 2.0), (2.0, 3.0), (2.2, 5.0), (1.9, 7.0), (1.3, 7.6)], 14, 'glass', geo.frame(seed=seed + 1)))
    m.add(geo.lathe([(1.4, 7.4), (2.2, 8.0), (1.5, 9.6), (0.6, 10.2), (0.01, 10.3)], 14, 'tin', geo.frame(seed=seed + 2)))
    for s in (-1, 1):
        m.add(geo.tube([(s * 2.8, 0, 1.0), (s * 3.2, 0, 5.0), (s * 1.6, 0, 9.0)], 0.18, sides=4, mat='tin', part=geo.frame(seed=seed)))
    th = np.linspace(0, np.pi, 10)
    m.add(geo.tube(np.stack([np.cos(th) * 2.6, np.zeros(10), 10.2 + np.sin(th) * 3.2], 1), 0.15, sides=4, mat='tin', part=geo.frame(seed=seed)))
    return m


def bag_pile(lod=0, seed=0):
    import p_sandbag
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    spots = [(0, 0, 0, 10), (-11, 4, 0, -14), (10, -3, 0, 22), (-3, 1, 5.2, 4), (6, 2, 5.0, -18)]
    for k, (x, y, z, yaw) in enumerate(spots):
        b = p_sandbag.bag(seed=seed + k, squash=0.25 + 0.1 * rng.rand(), lod=1 if lod else 0)
        b.transform(geo.euler(yaw, rng.uniform(-4, 4), rng.uniform(-6, 6)), (x, y, z)); m.add(b)
    return m


def wire_reel(lod=0, seed=0):
    m = geo.Mesh()
    for y in (-6, 6):
        d = geo.lathe([(0.01, -0.7), (11, -0.7), (11, 0.7), (0.01, 0.7)], 20, 'wood', geo.frame(seed=seed + y, tone=0.7))
        d.transform(geo.rot('x', 90), (0, y, 11)); m.add(d)
    core = geo.lathe([(6.5, -5.3), (6.5, 5.3)], 20, 'wire', geo.frame(seed=seed))
    core.transform(geo.rot('x', 90), (0, 0, 11)); m.add(core)
    m.add(geo.tube([(0, -7.5, 11), (0, 7.5, 11)], 1.0, sides=8, mat='wood', part=geo.frame(seed=seed + 3)))
    pts = [(0, 3, 4.6), (-8, 6, 1.0), (-18, 4, 0.5), (-26, 9, 0.6)]
    m.add(geo.tube(pts, 0.25, sides=4, mat='wire', part=geo.frame(seed=seed)))
    return m


def _hull(m, pad=0.0):
    lo, hi = m.bounds()
    return [np.array([[x, y, z] for x in (lo[0] - pad, hi[0] + pad) for y in (lo[1] - pad, hi[1] + pad) for z in (lo[2], hi[2])])]


def specs():
    sh = dict(hole=lambda c: dict(color=np.tile(S._c(0.03, 0.02, 0.02), (c.n, 1)), rough=np.full(c.n, 0.9, np.float32), metal=np.zeros(c.n, np.float32), height=np.zeros(c.n, np.float32)),
              wood=W, iron=IRON, tin=TIN, rope=ROPE, brass=S.brass, glass=glass, coals=coals, bark=S.bark, wire=S.wire, burlap=S.burlap,
              water=lambda c: dict(color=np.tile(S._c(0.16, 0.13, 0.09), (c.n, 1)), rough=np.full(c.n, 0.08, np.float32), metal=np.zeros(c.n, np.float32), height=np.zeros(c.n, np.float32)))
    out = {}
    table = [('tl_bucket', bucket, 512, 'wood'), ('tl_barrel', barrel, 1024, 'wood'), ('tl_brazier', brazier, 512, 'metal'),
             ('tl_bench', bench, 512, 'wood'), ('tl_tins', tins, 256, 'metal'), ('tl_periscope', periscope, 256, 'wood'),
             ('tl_gong', gong, 512, 'wood'), ('tl_tools', tools_lean, 512, 'wood'), ('tl_planks', planks_stack, 512, 'wood'),
             ('tl_lantern', lantern, 512, 'metal'), ('tl_bagpile', bag_pile, 512, 'dirt'), ('tl_wirereel', wire_reel, 512, 'wood')]
    for k, (name, fn, size, surf) in enumerate(table):
        m0 = fn(0, 11 + k); m1 = fn(1, 11 + k)
        solid = name not in ('tl_tins', 'tl_lantern', 'tl_tools', 'tl_gong')
        out[name] = dict(lods=[m0, m1], lod_thresholds=[0.0, 12.0], size=size, ground=0.0, metal=surf == 'metal', shaders=sh, surface=surf,
                         hulls=_hull(m0) if solid else [], res=0.25)
    return out
