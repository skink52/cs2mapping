"""German leichter Minenwerfer 7.58 cm n.A. (1916) in firing position: round baseplate, cradle cheeks, rifled tube with
recoil cylinders, elevation arc, hand wheels and carrying handles. Tube points +x, pivot over the origin."""
import numpy as np
import geo
import shaders as S

FIELDGREY = S._c(0.40, 0.42, 0.37)
SCALE = 1.4     # lMW n.A.: ~1 m baseplate, muzzle ~1.4 m up at 50 degrees


def _dir(el):
    a = np.radians(el)
    return np.array([np.cos(a), 0, np.sin(a)]), np.array([-np.sin(a), 0, np.cos(a)])


def minenwerfer(lod=0, seed=0, el=50.0):
    m = geo.Mesh()
    sd = 20 if lod == 0 else 9
    P = lambda **kw: geo.frame(seed=seed + len(m.charts), **kw)
    # baseplate: dished round plate with a raised rim and radial ribs
    m.add(geo.lathe([(0.01, 0), (21, 0), (22, 0.8), (22, 2.6), (20.5, 3.0), (15, 3.4), (13.5, 4.6), (0.01, 4.6)], sd * 2, 'gun', P()))
    if lod == 0:
        for k in range(8):
            a = np.radians(22.5 + k * 45)
            m.add(_rib(a, P()))
    # turntable and cradle cheeks
    m.add(geo.lathe([(0.01, 4.6), (12.5, 4.6), (12.5, 6.4), (11.5, 7.0), (0.01, 7.0)], sd * 2, 'gunsteel', P()))
    cheek = [(-9, 0), (9, 0), (7, 9), (3.5, 15.5), (-3.5, 15.5), (-8, 7)]
    for y in (-7.5, 6.0):
        c = geo.prism(cheek, y, y + 1.5, 'gun', P())
        c.transform(t=(0, 0, 7.0)); m.add(c)
    piv = np.array([0, 0, 21.0])
    m.add(geo.tube([piv + (0, -9.5, 0), piv + (0, 9.5, 0)], 1.6, sides=sd, mat='gunsteel', part=P()))
    d, up = _dir(el)
    # rifled tube: breech block, barrel, muzzle swell
    tube_pts = [piv - d * 13, piv - d * 9, piv - d * 8.6, piv + d * 22, piv + d * 23, piv + d * 25.5]
    m.add(geo.tube(tube_pts, [4.6, 4.6, 3.9, 3.7, 4.3, 4.3], sides=sd, mat='gunsteel', part=P()))
    bore = geo.tube([piv + d * 25.6, piv + d * 18], [2.9, 2.9], sides=sd, mat='hole', part=P(), caps=True)
    bore.F = bore.F[:, ::-1]; bore.recompute_normals(); m.add(bore)
    # recoil / recuperator cylinders above the barrel
    for off in (-2.4, 2.4):
        a = piv + up * 5.4 + np.array([0, off, 0])
        m.add(geo.tube([a - d * 9, a + d * 13], 1.5, sides=max(6, sd // 2), mat='gun', part=P()))
        m.add(geo.tube([a + d * 13, a + d * 14], 1.1, sides=max(6, sd // 2), mat='gunsteel', part=P()))
    # cradle band round the tube
    m.add(geo.tube([piv - d * 3, piv + d * 4], 5.1, sides=sd, mat='gun', part=P()))
    # elevation arc with teeth on the left cheek
    arc = []
    for t in np.linspace(np.radians(195), np.radians(265), 18):
        arc.append((np.cos(t) * 12.0, np.sin(t) * 12.0))
    for t in np.linspace(np.radians(265), np.radians(195), 18):
        arc.append((np.cos(t) * 8.5, np.sin(t) * 8.5))
    sec = geo.prism(arc, -9.6, -8.4, 'gunsteel', P())
    sec.transform(t=piv); m.add(sec)
    m.add(geo.tube([piv + (0, -9.0, 0), piv + (np.cos(np.radians(230)) * 9, -9.0, np.sin(np.radians(230)) * 9)], 1.0, sides=6, mat='gunsteel', part=P()))
    if lod == 0:
        for t in np.linspace(np.radians(198), np.radians(262), 14):
            p = piv + np.array([np.cos(t) * 12.4, -9.0, np.sin(t) * 12.4])
            m.add(geo.rbox(0.9, 1.0, 0.9, r=0.1, seg=1, mat='gunsteel', part=P(), center=tuple(p)))
    # hand wheels: elevation (left) and traverse (rear)
    for (c, ax) in (((-11.0, -12.6, 13.0), 'y'), ((-15.5, 0.0, 9.5), 'x')):
        c = np.array(c)
        ring = []
        for t in np.linspace(0, 2 * np.pi, 17):
            if ax == 'y': ring.append(c + np.array([np.cos(t) * 4.2, 0, np.sin(t) * 4.2]))
            else: ring.append(c + np.array([0, np.cos(t) * 4.2, np.sin(t) * 4.2]))
        m.add(geo.tube(ring, 0.45, sides=6, mat='gunsteel', part=P(), caps=False))
        for k in range(3):
            q = ring[k * 5 + 1]
            m.add(geo.tube([c, q], 0.3, sides=5, mat='gunsteel', part=P()))
        hub = c + (np.array([0, 1.8, 0]) if ax == 'y' else np.array([1.8, 0, 0]))
        m.add(geo.tube([c, hub], 0.8, sides=7, mat='gunsteel', part=P()))
        m.add(geo.tube([ring[3], ring[3] + (np.array([0, -2.2, 0]) if ax == 'y' else np.array([-2.2, 0, 0]))], 0.45, sides=6, mat='wood', part=P()))
    m.add(geo.tube([(-11.0, -9.0, 13.0), (-11.0, -11.0, 13.0)], 0.6, sides=6, mat='gunsteel', part=P()))
    m.add(geo.tube([(-11.5, 0, 9.5), (-6.5, 0, 9.5)], 0.6, sides=6, mat='gunsteel', part=P()))
    # carrying handles (four) on the baseplate rim and tow ring
    for k in range(4):
        a = np.radians(45 + k * 90)
        r0, r1 = 21.0, 25.5
        pts = [(np.cos(a - 0.12) * r0, np.sin(a - 0.12) * r0, 2.2), (np.cos(a - 0.1) * r1, np.sin(a - 0.1) * r1, 2.6),
               (np.cos(a + 0.1) * r1, np.sin(a + 0.1) * r1, 2.6), (np.cos(a + 0.12) * r0, np.sin(a + 0.12) * r0, 2.2)]
        m.add(geo.tube(pts, 0.55, sides=6, mat='gunsteel', part=P()))
    # sight bracket and dial on the right cheek
    m.add(geo.rbox(2.2, 1.6, 8.6, r=0.3, seg=1, mat='gunsteel', part=P(), center=(-2.0, 8.7, 20.4)))
    m.add(geo.tube([(-2.0, 9.5, 24.5), (-2.0, 9.5, 27.5)], 1.1, sides=8, mat='brass', part=P()))
    m.add(geo.tube([(-3.8, 9.5, 27.0), (0.5, 9.5, 27.0)], 0.7, sides=7, mat='gunsteel', part=P()))
    m.transform(s=SCALE)
    return m


def _rib(a, part):
    c, s = np.cos(a), np.sin(a)
    r = geo.prism([(-4.5, 0), (4.5, 0), (3.5, 1.6), (-3.5, 1.6)], -0.6, 0.6, 'gun', part)
    r.transform(geo.rot('z', np.degrees(a)) @ np.eye(3), (c * 17.0, s * 17.0, 3.0))
    return r


def specs():
    sh = dict(gun=lambda c: S.painted_steel(c, FIELDGREY, chip=0.14, rivets=True, mud_top=5),
              gunsteel=lambda c: S.painted_steel(c, FIELDGREY * 0.7, chip=0.22, mud_top=4, edge_k=0.6),
              brass=S.brass, wood=lambda c: S.wood(c, mud_top=0, wet=0.2),
              hole=lambda c: dict(color=np.tile(S._c(0.02, 0.02, 0.02), (c.n, 1)), rough=np.full(c.n, 0.9), metal=np.zeros(c.n), height=np.zeros(c.n)))
    m0 = minenwerfer(0, 3); m1 = minenwerfer(1, 3)
    lo, hi = m0.bounds()
    hull = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (0, 7 * SCALE)] +
                    [[x * SCALE, y * SCALE, z * SCALE] for x in (-14, 22) for y in (-10, 10) for z in (7, 30)] + [[hi[0], y, hi[2]] for y in (-5, 5)])
    return {'minenwerfer': dict(lods=[m0, m1], lod_thresholds=[0.0, 30.0], size=1024, ground=0.0, metal=True, shaders=sh,
                                surface='metal', hulls=[hull], res=0.5)}
