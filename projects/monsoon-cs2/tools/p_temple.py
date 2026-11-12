"""Khmer temple ruin (flag D): a gateway with carved lintels and pediments, a ruined sanctuary tower with a chamber you can enter,
a naga balustrade, a guardian lion, a rubble pile, a broad stair, a fallen lintel. Mossy weathered sandstone (mv_shaders.khmer_stone)
with laterite enclosure walls. Origins on the ground; the gate's and the tower's doorways face +x (passage along x).
Carving is a relief baked by the shader on parts tagged carve=1 (thin proud panels and pediment faces), not geometry.
"""
import numpy as np
import geo
import mv_geo as MG
import mv_shaders as M
import shaders as S
from noise import fbm


def blk(x0, y0, z0, x1, y1, z1, seed=0, mat='stone', carve=0.0, mono=0.0, r=1.0):
    return MG.box(x0, y0, z0, x1, y1, z1, mat, geo.frame(seed=seed, carve=carve, mono=mono), r=r)


def panel(x0, z0, x1, z1, y, seed=0, thick=1.4, face=-1):
    """thin carved panel standing proud of a wall face at y, facing -y (face -1) or +y"""
    y0, y1 = (y - thick, y) if face < 0 else (y, y + thick)
    return MG.box(x0, y0, z0, x1, y1, z1, 'stone', geo.frame(seed=seed, carve=1.0, mono=1.0), r=0.5)


def colonette(h, r=6.5, seed=0):
    """octagonal door colonette with ring mouldings"""
    prof = [(0, 0), (r * 1.25, 0), (r * 1.25, 5), (r, 7)]
    for k in range(1, 5):
        z = h * k / 5.0
        prof += [(r, z - 3), (r * 1.18, z - 1.5), (r * 1.18, z + 1.5), (r, z + 3)] if k < 5 else []
    prof = [p for p in prof if p[1] < h - 8] + [(r, h - 8), (r * 1.3, h - 5), (r * 1.3, h), (0, h)]
    return geo.lathe(prof, sides=8, mat='stone', part=geo.frame(seed=seed, mono=1.0))


def pediment_poly(hw, h):
    """flame-shaped fronton outline in (x, z): upturned naga ends, concave shoulders, pointed apex"""
    r = [(hw, 0), (hw + 7, 4), (hw + 9, 13), (hw + 2, 13), (hw * 0.80, h * 0.24), (hw * 0.62, h * 0.50), (hw * 0.40, h * 0.72), (hw * 0.18, h * 0.90), (0, h)]
    return r + [(-x, z) for x, z in r[-2::-1]]


def pediment(hw, h, thick, seed=0):
    return geo.prism(pediment_poly(hw, h), -thick, 0.0, 'stone', geo.frame(seed=seed, carve=1.0, mono=1.0))


def portal(w=72.0, h=118.0, seed=0, lintel_h=30.0, ped_h=72.0, door=True):
    """door dressing in front of a wall face at y = 0 (facing -y), opening centred on x = 0: two colonettes, a carved lintel, a
    pediment above it; door False adds a carved false-door leaf instead of an opening"""
    m = geo.Mesh()
    for s in (-1, 1):
        m.add(colonette(h, seed=seed + s).transform(None, (s * (w / 2 + 9), -8, 0)))
        m.add(blk(s * (w / 2 + 18), -10, 0, s * (w / 2 + 30), 0, h, seed + 3 + s, r=0.8))             # pilaster behind the colonette
    m.add(blk(-(w / 2 + 34), -15, h, w / 2 + 34, 0, h + lintel_h, seed + 6, mono=1.0, r=1.2))           # lintel block
    m.add(panel(-(w / 2 + 31), h + 2.5, w / 2 + 31, h + lintel_h - 2.5, -15, seed + 7))
    m.add(pediment(w / 2 + 30, ped_h, 9.0, seed + 8).transform(None, (0, -3, h + lintel_h)))
    if not door:
        m.add(blk(-w / 2, -3, 0, w / 2, 0, h, seed + 9, mono=1.0, r=0.6))
        for s in (-1, 1): m.add(panel(s * w / 4 - w / 4 + 3, 6, s * w / 4 + w / 4 - 3, h - 6, -3, seed + 10 + s))
        m.add(blk(-2, -6, 0, 2, -3, h, seed + 12, mono=1.0, r=0.8))                                       # the leaves' meeting stile
    return m


def lotus(r=40.0, h=46.0, seed=0, sides=12):
    prof = [(0, 0), (r, 0), (r * 1.08, h * 0.10), (r * 0.80, h * 0.22), (r * 0.86, h * 0.34), (r * 0.60, h * 0.52), (r * 0.64, h * 0.62), (r * 0.36, h * 0.82), (r * 0.16, h * 0.94), (0, h)]
    return geo.lathe(prof, sides=sides, mat='stone', part=geo.frame(seed=seed, mono=1.0))


def rubble(n, cx, cy, rad, seed, zmax=0.0, size=(10, 30)):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    for k in range(n):
        a = rng.uniform(0, 2 * np.pi); r = rad * np.sqrt(rng.rand())
        sx, sy, sz = rng.uniform(*size), rng.uniform(size[0], size[1] * 0.8), rng.uniform(size[0] * 0.7, size[1] * 0.55)
        b = geo.rbox(sx, sy, sz, r=1.4, seg=1, mat='stone', part=geo.frame(seed=seed + k, mono=1.0, carve=1.0 if k % 4 == 0 else 0.0))
        b.transform(geo.euler(rng.uniform(0, 360), rng.uniform(-14, 14), rng.uniform(-14, 14)), (cx + r * np.cos(a), cy + r * np.sin(a), zmax * max(0, 1 - r / rad) + sz / 2 - rng.uniform(1.5, 4)))
        m.add(b)
    return m


# ---------------------------------------------------------------- gate
def khmer_gate(lod=0, seed=141):
    """gopura: two piers, a 72 x 130 passage, lintel and pediment on both faces, a stepped superstructure with a row of finials,
    stubs of the laterite enclosure wall on both sides. Built spanning x, then turned so the passage runs along x."""
    m = geo.Mesh(); H = []
    B = MG.pts_box
    m.add(blk(-132, -40, 0, 132, 40, 8, seed)); H.append(B(-132, -40, 0, 132, 40, 8))                     # plinth (one 8 u step)
    for s in (-1, 1):
        x0, x1 = (36, 112) if s > 0 else (-112, -36)
        m.add(blk(x0, -30, 8, x1, 30, 138, seed + 1 + s))
        m.add(blk(x0 - 3, -33, 8, x1 + 3, 33, 22, seed + 3 + s)); m.add(blk(x0 - 3, -33, 126, x1 + 3, 33, 138, seed + 5 + s))   # base and capital mouldings
        for f in (-1, 1): m.add(panel(x0 + 24 if s > 0 else x0 + 8, 30, x1 - 8 if s > 0 else x1 - 24, 118, f * 30, seed + 7 + s + f, face=f))
        H.append(B(x0 - 3, -33, 8, x1 + 3, 33, 138))
    m.add(blk(-118, -33, 138, 118, 33, 160, seed + 10)); m.add(blk(-126, -37, 160, 126, 37, 172, seed + 11))
    m.add(blk(-98, -28, 172, 98, 28, 212, seed + 12)); m.add(blk(-106, -32, 212, 106, 32, 222, seed + 13))
    m.add(blk(-62, -22, 222, 62, 22, 246, seed + 14)); m.add(blk(-68, -25, 246, 68, 25, 252, seed + 15))
    H += [B(-126, -37, 138, 126, 37, 172), B(-106, -32, 172, 106, 32, 222), B(-68, -25, 222, 68, 25, 252)]
    for k, x in enumerate((-52, -26, 0, 26)):                                                              # ridge finials (one fallen)
        m.add(lotus(8.5, 24, seed + 20 + k, sides=8).transform(None, (x, 0, 252)))
    for f in (-1, 1):
        pt = portal(72, 130, seed + 30 + f, lintel_h=30, ped_h=74)
        pt.transform(geo.rot('z', 0 if f < 0 else 180), (0, f * 30, 8)); m.add(pt)
    for f in (-1, 1): m.add(panel(-80, 178, 80, 206, f * 28, seed + 40 + f, face=f))
    # laterite wall stubs, stepped down where they have collapsed
    for s, steps in ((1, ((112, 152, 98), (152, 176, 72), (176, 196, 40))), (-1, ((-150, -112, 98), (-168, -150, 58)))):
        for k, (xa, xb, hh) in enumerate(steps):
            m.add(blk(xa, -15, 0, xb, 15, hh, seed + 50 + k + s, mat='laterite'))
            H.append(B(xa, -15, 0, xb, 15, hh))
        xa, xb, hh = steps[0]
        m.add(blk(xa, -18, hh, xb, 18, hh + 7, seed + 56 + s, r=1.5))
    m.add(rubble(7, -176, 10, 30, seed + 60, zmax=10, size=(9, 24)))
    m.add(rubble(4, 60, 62, 22, seed + 70, size=(8, 20)))
    R = geo.rot('z', 90)
    m.transform(R)
    return m, [MG.xform_pts(h, R) for h in H]


# ---------------------------------------------------------------- tower
def khmer_tower(lod=0, seed=142):
    """prasat: plinth, a square cella (inner 140 x 140 x 150, door 64 x 110 on +x, false doors on the other faces), cornice, four
    diminishing redented tiers with antefix pediments and a lotus crown at ~416 u; strangler-fig roots down one corner"""
    m = geo.Mesh(); H = []
    B = MG.pts_box
    m.add(blk(-124, -124, 0, 124, 124, 10, seed)); m.add(blk(-114, -114, 10, 114, 114, 20, seed + 1))
    H += [B(-124, -124, 0, 124, 124, 10), B(-114, -114, 10, 114, 114, 20)]
    z0, z1 = 20.0, 170.0
    wp = geo.frame(seed=seed + 2)
    for a, b, op in (((85, -100), (85, 100), [(68, 132, z0, z0 + 110)]), ((-85, 100), (-85, -100), []), ((-70, 85), (70, 85), []), ((70, -85), (-70, -85), [])):
        w, hs = MG.slab_wall(a, b, z0, z1, 30.0, 'stone', wp, openings=op, r=1.0)
        m.add(w); H += hs
    for sx in (-1, 1):
        for sy in (-1, 1):
            m.add(blk(sx * 78, sy * 78, z0, sx * 107, sy * 107, z1, seed + 4 + sx + 2 * sy))
            m.add(blk(sx * 76, sy * 76, z0, sx * 110, sy * 110, z0 + 16, seed + 9 + sx + 2 * sy))
            H.append(B(min(sx * 76, sx * 110), min(sy * 76, sy * 110), z0, max(sx * 76, sx * 110), max(sy * 76, sy * 110), z1))
    for k, ang in enumerate((90, 180, 270, 0)):       # portals: +x (the real door), +y, -x, -y
        pt = portal(64, 110, seed + 20 + k * 20, lintel_h=26, ped_h=58, door=(k == 0))
        pt.transform(geo.rot('z', ang), (np.round(np.cos(np.radians(ang - 90))) * -100 if False else 0, 0, 0))
        d = np.array([np.cos(np.radians(ang - 90)), np.sin(np.radians(ang - 90)), 0.0])      # outward normal of that face
        pt.transform(None, d * 100 + np.array([0, 0, z0])); m.add(pt)
    m.add(blk(-108, -108, z1, 108, 108, z1 + 8, seed + 12)); m.add(blk(-116, -116, z1 + 8, 116, 116, z1 + 16, seed + 13))
    H.append(B(-116, -116, z1, 116, 116, z1 + 16))
    m.add(blk(-70, -70, z1 - 6, 70, 70, z1, seed + 14, mono=1.0))                                          # ceiling slab seen from inside
    z = z1 + 16
    rng = np.random.RandomState(seed)
    for k, (half, hk) in enumerate(((92, 58), (74, 50), (59, 42), (47, 36))):
        tp = geo.frame(seed=seed + 30 + k)
        cut = half * 0.11
        body = MG.vloft([(z, MG.rect_loop(half, half, cut, 2)), (z + hk * 0.74, MG.rect_loop(half * 0.97, half * 0.97, cut, 2))], 'stone', tp, cap_top=False)
        m.add(body)
        m.add(MG.vloft([(z + hk * 0.74, MG.rect_loop(half + 5, half + 5, cut, 2)), (z + hk, MG.rect_loop(half + 7, half + 7, cut, 2))], 'stone', geo.frame(seed=seed + 40 + k), cap_top=True, cap_bottom=True))
        H.append(B(-half - 7, -half - 7, z, half + 7, half + 7, z + hk))
        for q, ang in enumerate((0, 90, 180, 270)):
            if k == 3 and q == 1: continue            # one antefix has fallen from the top tier
            pd = pediment(half * 0.42, hk * 0.92, 6.0, seed + 50 + k * 4 + q)
            pd.transform(geo.rot('z', ang), (0, 0, 0))
            d = np.array([np.cos(np.radians(ang - 90)), np.sin(np.radians(ang - 90)), 0.0])
            pd.transform(None, d * (half + 1.5) + np.array([0, 0, z + 1])); m.add(pd)
        for sx in (-1, 1):
            for sy in (-1, 1):
                if k >= 2 and sx > 0 and sy > 0: continue
                m.add(lotus(half * 0.10 + 2, hk * 0.5, seed + 70 + k, sides=6).transform(None, (sx * (half + 1), sy * (half + 1), z + hk)))
        z += hk
    cr = lotus(40, 46, seed + 80, sides=14); cr.transform(geo.euler(0, 3, -2), (1.5, -1, z - 1)); m.add(cr)
    H.append(B(-30, -30, z, 30, 30, z + 44))
    # inside: pedestal and linga
    m.add(blk(-20, -20, z0, 20, 20, z0 + 16, seed + 90, carve=0.0)); m.add(blk(-15, -15, z0 + 16, 15, 15, z0 + 22, seed + 91, mono=1.0))
    m.add(geo.lathe([(0, 0), (8, 0), (8, 16), (6.5, 22), (3, 25), (0, 25.5)], sides=10, mat='stone', part=geo.frame(seed=seed + 92, mono=1.0)).transform(None, (0, 0, z0 + 22)))
    H.append(B(-20, -20, z0, 20, 20, z0 + 30))
    # strangler fig roots down the -x +y corner, from the first tier to the ground
    for k in range(5):
        yk = 104.0 - k * 10 + rng.uniform(-2, 2)
        xw = -109.5 if yk >= 77 else -102.5                    # on the corner pier or on the wall face
        pts = np.array([[-80 + rng.uniform(-6, 6), yk - 12, z1 + 18 + rng.uniform(0, 22)], [-104, yk - 4, z1 + 19.5], [-119.5, yk, z1 + 15], [-118, yk + 1, z1 + 2],
                        [xw - 1.5, yk + 2, z1 - 14], [xw, yk + rng.uniform(-5, 5), 96], [xw - 1, yk + rng.uniform(-6, 6), 34], [xw - 20 - rng.uniform(0, 14), yk + rng.uniform(-10, 10), -4]])
        m.add(geo.tube(pts, [2.0, 2.4, 2.8, 3.0, 3.3, 3.8, 4.6, 5.4], sides=6, mat='root', part=geo.frame(seed=seed + 100 + k)))
    m.add(rubble(6, 150, -120, 34, seed + 110, zmax=8, size=(10, 26)))
    m.add(rubble(4, -150, -60, 26, seed + 120, size=(9, 22)))
    return m, H


# ---------------------------------------------------------------- smaller pieces
def ellipsoid(c, r, mat='stone', part=None, sides=14, rings=9, R=None):
    """smooth ellipsoid of semi-axes r = (rx, ry, rz) at c (a scaled lathed sphere), optionally turned by R"""
    prof = [(np.sin(t), -np.cos(t)) for t in np.linspace(0.0, np.pi, rings + 1)]
    prof[0] = (0.0, -1.0); prof[-1] = (0.0, 1.0)
    m = geo.lathe(prof, sides=sides, mat=mat, part=part or geo.frame(mono=1.0))
    m.V = m.V * np.asarray(r, float)
    if R is not None: m.V = m.V @ np.asarray(R, float).T
    m.V = m.V + np.asarray(c, float)
    m.charts[0]['w'] = 2 * np.pi * max(r); m.charts[0]['h'] = np.pi * max(r)
    m.recompute_normals(angle=80)
    return m


def etube(pts, rx, ry, sides=12, mat='stone', part=None, caps=True, twist=0.0):
    """tube with an elliptical section (rx along the path normal, ry along the binormal), both per point"""
    pts = np.asarray(pts, float); n = len(pts)
    rx = np.broadcast_to(np.asarray(rx, float), (n,)); ry = np.broadcast_to(np.asarray(ry, float), (n,))
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]); s = s / max(s[-1], 1e-6)
    def rn(th, sl):
        k = np.interp(sl / max(1e-6, np.linalg.norm(np.diff(pts, axis=0), axis=1).sum()), s, np.arange(n))
        i = int(np.clip(round(k), 0, n - 1))
        a, b = rx[i], ry[i]; r0 = max(a, b)
        return 1.0 / np.sqrt((np.cos(th + twist) / a) ** 2 + (np.sin(th + twist) / b) ** 2) / r0
    return geo.tube(pts, np.maximum(rx, ry), sides=sides, mat=mat, part=part, caps=caps, rnoise=rn)


def weather(m, amp, freq, seed, angle=70.0):
    """push vertices along their normals by fbm noise: worn, eroded stone"""
    m.recompute_normals(angle=angle)
    n = fbm(m.V[:, 0] * freq, m.V[:, 1] * freq, m.V[:, 2] * freq, 3, seed=seed)
    m.V = m.V + m.N * n[:, None] * amp
    m.recompute_normals(angle=angle)
    return m


def naga_head(base, up, out, size, seed, sp):
    """one cobra head of the hood: a neck rising from the hood face, a swelling skull, a blunt snout, a brow ridge"""
    base = np.asarray(base, float); up = np.asarray(up, float); out = np.asarray(out, float)
    up = up / np.linalg.norm(up); out = out / np.linalg.norm(out)
    pts = [base, base + up * size * 0.9 + out * size * 0.15, base + up * size * 1.7 + out * size * 0.55, base + up * size * 2.05 + out * size * 1.15,
           base + up * size * 2.1 + out * size * 1.75]
    rx = np.array([0.42, 0.40, 0.55, 0.62, 0.30]) * size; ry = np.array([0.42, 0.38, 0.48, 0.50, 0.24]) * size
    h = etube(pts, rx, ry, sides=12, mat='stone', part=sp)
    h.add(ellipsoid(base + up * size * 2.12 + out * size * 0.9, (size * 0.30, size * 0.62, size * 0.16), part=sp, sides=10, rings=5))    # brow ridge
    return h


def naga_balustrade(lod=0, seed=143):
    """128 u of naga rail along x: a smooth serpent body (scaled, banded belly) on three moulded posts, rearing at +x into a
    seven-headed hood (a scalloped fan with sculpted cobra heads, the middle one larger)"""
    m = geo.Mesh()
    for k, x in enumerate((-52, -6, 38)):
        m.add(blk(x - 9.5, -8.5, 0, x + 9.5, 8.5, 5, seed + k, r=1.4))
        m.add(geo.lathe([(0, 0), (7.6, 0), (7.6, 2), (6.4, 4), (6.0, 17), (7.2, 19), (8.0, 23), (7.0, 25.5), (0, 25.5)], sides=4, mat='stone',
                        part=geo.frame(seed=seed + 3 + k, mono=1.0)).transform(geo.rot('z', 45), (x, 0, 5)))
    sp = geo.frame(R=np.eye(3), seed=seed + 6, mono=1.0)
    # the body: undulating along x, the tail end tapering at -x, rising into the neck at +x
    xs = np.linspace(-66, 44, 23)
    pts = [(x, 1.6 * np.sin(x * 0.07), 33 + 0.9 * np.sin(x * 0.11 + 1.0)) for x in xs] + [(50, 0, 36), (54, 0, 44), (55.5, 0, 52), (56, 0, 58)]
    nb = len(pts); t = np.linspace(0, 1, nb)
    r = 9.0 - 2.4 * np.clip(1 - (t * nb) / 4.0, 0, 1)
    def scales(th, sl):
        return (1.0 + 0.035 * np.cos(sl * 0.62) * (np.cos(th) > -0.5)) * (1.0 - 0.10 * np.clip(-np.cos(th) - 0.55, 0, 1))
    body = geo.tube(np.array(pts), r, sides=14, mat='stone', part=sp, rnoise=scales, phase=np.pi / 2)
    m.add(weather(body, 0.6, 0.13, seed))
    # the hood: a backing disc and seven overlapping petals (flattened ellipsoids) fanned in the y-z plane at x 60, each carrying a
    # cobra head on a short neck that leans out (+x) and up; the middle head is the largest
    hp = geo.frame(seed=seed + 8, carve=1.0, mono=1.0)
    m.add(ellipsoid((59.0, 0, 63), (3.6, 24, 21), part=hp, sides=18, rings=9))
    lobes = 7; a0, a1 = np.radians(-10), np.radians(190)
    for k in range(lobes):
        am = a0 + (a1 - a0) * (k + 0.5) / lobes; big = k == lobes // 2
        ca, sa = np.cos(am), np.sin(am)
        Rr = np.array([[1, 0, 0], [0, ca, -sa], [0, sa, ca]])          # local y = radial direction in the y-z plane
        m.add(ellipsoid((59.5, 21.0 * ca, 63 + 21.0 * sa), (3.4, 12.5, 8.0), part=hp, R=Rr, sides=14, rings=7))
        sz = 1.35 if big else 1.0
        n0 = np.array([61.5, 15.0 * ca, 63 + 15.0 * sa]); n1 = np.array([66.0, 24.0 * ca * sz, 63 + 24.0 * sa * sz])
        hd = geo.Mesh()
        hd.add(geo.tube([n0, (n0 + n1) / 2 + np.array([1.0, 0, 0]), n1], [3.0 * sz, 2.8 * sz, 3.2 * sz], sides=10, mat='stone', part=sp))
        dirn = n1 - n0; dirn /= np.linalg.norm(dirn)
        fwd = np.array([1.0, 0.0, 0.0]); side = np.cross(dirn, fwd); side /= np.linalg.norm(side)
        Rh = np.stack([fwd * 0.6 + dirn * 0.4, side, np.cross(fwd * 0.6 + dirn * 0.4, side)], 1)
        Rh[:, 0] /= np.linalg.norm(Rh[:, 0]); Rh[:, 2] /= np.linalg.norm(Rh[:, 2])
        hd.add(ellipsoid(n1 + np.array([1.5, 0, 0]) * sz, (6.2 * sz, 4.4 * sz, 3.4 * sz), part=sp, R=Rh, sides=12, rings=6))      # the head, snout forward
        for sy in (-1, 1): hd.add(ellipsoid(n1 + (np.array([3.2, 0, 0]) + side * sy * 2.6 + Rh[:, 2] * 2.0) * sz, (1.3 * sz,) * 3, part=sp, sides=6, rings=4))
        m.add(weather(hd, 0.3, 0.35, seed + 30 + k))
    m.add(ellipsoid((60.0, 0, 50), (8, 10, 13), part=sp))              # the neck swelling into the hood
    return m, [MG.pts_box(-66, -10, 0, 52, 10, 43), MG.pts_box(52, -34, 30, 74, 34, 99)]


def naga_balustrade_old(lod=0, seed=143):
    """128 u of naga rail along x: the body on three squat posts, rearing into a seven-lobed hood at +x"""
    m = geo.Mesh()
    for k, x in enumerate((-52, -6, 38)):
        m.add(blk(x - 9, -8, 0, x + 9, 8, 6, seed + k, mono=1.0)); m.add(blk(x - 7, -6.5, 6, x + 7, 6.5, 25, seed + 3 + k, mono=1.0))
    bp = geo.frame(R=np.eye(3), seed=seed + 6, mono=1.0)
    pts = [(-64, 0, 33), (-20, 0, 33), (30, 0, 33), (46, 0, 35), (55, 0, 44), (58, 0, 58)]
    m.add(geo.tube(pts, [8.5, 9, 9, 9, 8.5, 8], sides=8, mat='stone', part=bp, phase=np.pi / 8))
    for x in np.arange(-58, 44, 12.0):          # scale bands
        m.add(geo.tube([(x, 0, 33), (x + 2.2, 0, 33)], 9.9, sides=8, mat='stone', part=bp, phase=np.pi / 8))
    # hood: a fan of seven lobes in the y-z plane
    c = np.array([0.0, 64.0]); poly = [(-9, 40), (9, 40)]
    for k in range(7):
        a0 = np.radians(-12 + k * 204 / 7.0); a1 = np.radians(-12 + (k + 1) * 204 / 7.0); am = (a0 + a1) / 2
        poly += [(c[0] + 24 * np.cos(a0), c[1] + 24 * np.sin(a0)), (c[0] + 31 * np.cos(am - 0.1), c[1] + 31 * np.sin(am - 0.1)), (c[0] + 33 * np.cos(am + 0.06), c[1] + 33 * np.sin(am + 0.06))]
    poly.append((c[0] + 24 * np.cos(np.radians(192)), c[1] + 24 * np.sin(np.radians(192))))
    hood = geo.prism(poly, -4, 4, 'stone', geo.frame(seed=seed + 8, carve=1.0, mono=1.0))
    hood.transform(geo.rot('z', 90), (60, 0, 0)); m.add(hood)
    for k in range(7):                           # the heads: one large in the middle, three smaller each side
        am = np.radians(-12 + (k + 0.5) * 204 / 7.0); big = k == 3
        y, z = 25 * np.cos(am), 64 + 25 * np.sin(am)
        hd = geo.rbox(11 if big else 7, 9 if big else 6, 12 if big else 8, r=3.2 if big else 2.4, seg=2, mat='stone', part=geo.frame(seed=seed + 10 + k, mono=1.0))
        hd.transform(geo.euler(0, 0, np.degrees(am) - 90), (66.5 if big else 65, y, z)); m.add(hd)
    m.add(geo.rbox(9, 13, 20, r=3.5, seg=2, mat='stone', part=geo.frame(seed=seed + 20, mono=1.0)).transform(None, (65.5, 0, 66)))   # central neck
    m.recompute_normals(angle=52)
    return m, [MG.pts_box(-64, -9, 0, 52, 9, 42), MG.pts_box(52, -32, 30, 72, 32, 98)]


def guardian_statue(lod=0, seed=144):
    """Khmer singha: a lion sitting upright on its haunches on a moulded pedestal, chest thrust out, forelegs straight, the head
    turned a little, a mane of tight stone curls, the jaw open, the tail curled up its flank; sculpted from lofted ellipses and
    ellipsoids and eroded by noise. Faces +x, 100 u tall."""
    m = geo.Mesh()
    # pedestal: a plinth, a recessed die with a lotus moulding top and bottom, carved panels on the long sides
    m.add(blk(-25, -31, 0, 27, 31, 6, seed, r=1.6))
    m.add(blk(-23, -29, 6, 25, 29, 10, seed + 1, mono=1.0, r=2.0))
    m.add(blk(-20, -26, 10, 22, 26, 19, seed + 2, mono=1.0, r=1.2))
    m.add(blk(-22.5, -28.5, 19, 24.5, 28.5, 24, seed + 3, mono=1.0, r=1.8))
    for f in (-1, 1): m.add(panel(-16, 11.5, 18, 18, f * 26, seed + 4 + f, face=f))
    sp = geo.frame(seed=seed + 5, mono=1.0)
    s = geo.Mesh()
    # haunches and thighs: big rounded masses either side, the hind feet tucked forward
    for sy in (-1, 1):
        s.add(ellipsoid((-7, sy * 12.5, 37), (19, 12, 15), 'lion', sp, R=geo.rot('y', -18)))
        s.add(ellipsoid((8, sy * 19, 27.5), (11, 5.5, 4.2), 'lion', sp))                                         # hind paw
    # torso: a loft up the spine from the rump to the base of the neck, chest pushed forward
    spine = [(-12, 0, 36), (-6, 0, 47), (1, 0, 58), (6, 0, 68), (9, 0, 77)]
    for (c_, r_, tl) in (((-5, 0, 47), (11.5, 12.5, 13), -25), ((2, 0, 57), (10.5, 11.5, 12), -30)):
        s.add(ellipsoid(c_, r_, 'lion', sp, R=geo.rot('y', tl)))                                                 # belly and ribs up the spine
    s.add(ellipsoid((-10, 0, 37), (13, 14, 11), 'lion', sp))                                                      # rump
    s.add(ellipsoid((9, 0, 62), (9.5, 12, 14), 'lion', sp, R=geo.rot('y', -12)))                                 # chest
    s.add(ellipsoid((9, 0, 76), (9, 10, 9), 'lion', sp))                                                          # base of the neck                                                       # chest
    # forelegs: straight columns with an elbow and a wrist, big paws with toes
    for sy in (-1, 1):
        s.add(geo.tube([(9, sy * 10, 66), (14, sy * 10.5, 52), (17, sy * 10.5, 38), (18, sy * 10.5, 28)], (np.array([6.6, 5.6, 4.6, 4.8]) + np.array([6.0, 5.2, 4.4, 4.6])) / 2.0, sides=10,
                    mat='lion', part=sp))
        s.add(ellipsoid((22, sy * 10.5, 27), (8, 6, 3.6), 'lion', sp))
        s.add(ellipsoid((9, sy * 10.5, 62), (8.5, 7.0, 11), 'lion', sp, R=geo.rot('y', -10)))                        # shoulder over the leg top
        for k in (-1, 0, 1): s.add(ellipsoid((29, sy * 10.5 + k * 3.4, 26.8), (2.4, 1.9, 2.0), 'lion', sp, sides=8, rings=5))
    # head, turned 8 degrees to its right: skull, brow, muzzle, open jaw, cheeks, ears, eyes
    hs = geo.Mesh(); hc = np.array([14.0, 0.0, 87.0])
    hs.add(ellipsoid((0, 0, 0), (12.5, 13, 12), 'lion', sp))
    hs.add(geo.tube([(8, 0, 4.5), (13, 0, 3), (17.5, 0, 1)], (np.array([6.2, 5.6, 4.6]) + np.array([8.5, 8, 6.8])) / 2.0, sides=12, mat='lion', part=sp))                 # muzzle
    hs.add(ellipsoid((17.5, 0, 2.6), (3.2, 4.4, 2.8), 'lion', sp))                                                                     # nose
    hs.add(geo.tube([(7, 0, -5), (12, 0, -7.5), (16, 0, -9.5)], (np.array([3.6, 3.2, 2.6]) + np.array([7.5, 7, 6])) / 2.0, sides=10, mat='lion', part=sp))              # lower jaw, open
    hs.add(ellipsoid((14.5, 0, -3.5), (3.5, 5.5, 2.5), 'lion', sp, sides=10, rings=5))                                                  # the tongue in the open mouth
    for sy in (-1, 1):
        hs.add(ellipsoid((9, sy * 8, 0.5), (6, 4.5, 5.5), 'lion', sp))                                                                  # cheeks
        hs.add(ellipsoid((9.5, sy * 4.6, 8.4), (4.0, 3.6, 2.2), 'lion', sp, R=geo.rot('x', sy * 15)))                                   # brow ridges
        hs.add(ellipsoid((11.6, sy * 4.6, 6.2), (2.3, 2.3, 2.1), 'lion', sp, sides=8, rings=5))                                        # bulging eyes
        hs.add(ellipsoid((-1, sy * 10.5, 11), (3.4, 2.0, 4.8), 'lion', sp, R=geo.rot('x', sy * 30)))                                   # ears
    # mane: three rows of tight curls round the face and down the neck
    for row, (rr, nc, zz) in enumerate(((14.5, 13, 0.0), (16.0, 15, -6.0), (14.0, 13, -13.0))):
        for k in range(nc):
            a = np.radians(-150 + 300 * (k + 0.5 * (row % 2)) / nc)
            p = np.array([-2.0 - row * 2.5 + 5.0 * np.cos(a) ** 2, rr * np.cos(a), zz + rr * 0.85 * np.sin(a) * (1.0 if row == 0 else 0.5)])
            if row == 0 and p[2] < -6: continue
            hs.add(ellipsoid(p, (3.6, 3.4, 3.4), 'lion', sp, sides=8, rings=5))
    hs.transform(geo.rot('z', 8) @ geo.rot('y', -6), hc)
    s.add(hs)
    # tail: from the rump round the right flank, curling up the side
    s.add(geo.tube([(-24, 6, 28), (-26, 14, 34), (-20, 22, 38), (-10, 24, 44), (-4, 22, 52), (-6, 18, 59), (-11, 17, 60)], [3.3, 3.1, 3.0, 2.8, 2.7, 3.2, 4.2],
                   sides=8, mat='lion', part=sp))
    weather(s, 0.9, 0.16, seed)
    m.add(s)
    return m, [MG.pts_box(-25, -31, 0, 27, 31, 24), MG.pts_box(-28, -19, 24, 32, 19, 102)]


def guardian_statue_old(lod=0, seed=144):
    """weathered seated lion on a carved pedestal, facing +x, 100 u tall"""
    m = geo.Mesh()
    m.add(blk(-24, -31, 0, 26, 31, 8, seed)); m.add(blk(-20, -27, 8, 22, 27, 20, seed + 1, mono=1.0)); m.add(blk(-22, -29, 20, 24, 29, 24, seed + 2, mono=1.0))
    for f in (-1, 1): m.add(panel(-17, 10, 19, 18.5, f * 27, seed + 3 + f, face=f))
    sp = geo.frame(seed=seed + 5, mono=1.0)
    s = geo.Mesh()
    def rb(sx, sy, sz, r, c, R=None):
        b = geo.rbox(sx, sy, sz, r=r, seg=3, mat='lion', part=sp); b.transform(R, c); s.add(b)
    rb(36, 34, 28, 12, (-8, 0, 38))                                   # haunches
    rb(26, 29, 46, 11, (6, 0, 56), geo.rot('y', -10))                 # chest
    rb(25, 25, 25, 10, (12, 0, 86))                                   # head
    s.add(geo.lathe([(0, 0), (15, 0), (18, 4), (18.5, 9), (15, 14), (0, 14)], sides=12, mat='lion', part=sp).transform(geo.rot('y', -14), (7, 0, 66)))   # mane
    rb(12, 15, 10, 4, (26, 0, 84)); rb(10, 13, 5, 2.2, (25, 0, 76), geo.rot('y', 14))           # muzzle, open jaw
    for sy in (-1, 1):
        rb(7, 4, 6, 2.0, (5, sy * 10.5, 96.5))                                                 # ears, laid back
        rb(24, 11, 20, 6, (-4, sy * 17, 34))                                                   # thighs
        s.add(geo.tube([(13, sy * 9.5, 62), (16, sy * 9.5, 44), (17, sy * 9.5, 27)], [6.2, 5.6, 5.4], sides=8, mat='lion', part=sp))   # forelegs
        rb(14, 10, 7, 3, (20, sy * 9.5, 27)); rb(13, 9, 6, 2.8, (9, sy * 18, 27))               # paws
        rb(4.5, 4.5, 4.5, 2.2, (22.5, sy * 6.5, 91))                                           # eyes (bulging, worn)
    s.add(geo.tube([(-25, 0, 27), (-27, 0, 40), (-23, 0, 50), (-15, 0, 54), (-9.5, 0, 60), (-9, 1, 71), (-8.5, 3, 79)], [3.2, 3.2, 3.0, 2.9, 2.8, 2.8, 3.6], sides=7, mat='lion', part=sp))   # tail lying up the back
    s.recompute_normals(angle=70)
    n = fbm(s.V[:, 0] * 0.11, s.V[:, 1] * 0.11, s.V[:, 2] * 0.11, 3, seed=seed)
    s.V = s.V + s.N * n[:, None] * 1.3
    s.recompute_normals(angle=70)
    m.add(s)
    return m, [MG.pts_box(-24, -31, 0, 26, 31, 24), MG.pts_box(-28, -19, 24, 32, 19, 102)]


def fallen_blocks(lod=0, seed=145):
    """rubble pile of sandstone blocks, a few carved, with two column drums"""
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    m.add(rubble(13, 0, 0, 62, seed, size=(18, 46)))
    for k in range(5):
        sx, sy, sz = rng.uniform(22, 44), rng.uniform(18, 30), rng.uniform(14, 22)
        b = geo.rbox(sx, sy, sz, r=1.6, seg=1, mat='stone', part=geo.frame(seed=seed + 40 + k, mono=1.0, carve=1.0 if k % 2 else 0.0))
        b.transform(geo.euler(rng.uniform(0, 360), rng.uniform(-24, 24), rng.uniform(-24, 24)), (rng.uniform(-24, 24), rng.uniform(-20, 20), 20 + sz / 2 + rng.uniform(-3, 6))); m.add(b)
    for k, (x, y, a) in enumerate(((52, -40, 30), (-58, 34, 100))):
        d = colonette(40, r=9, seed=seed + 60 + k)
        d.transform(geo.rot('z', a) @ geo.rot('y', 84), (x, y, 9.5)); m.add(d)
    return m, [MG.pts_box(-66, -58, 0, 66, 58, 15), MG.pts_box(-34, -28, 15, 34, 28, 38)]


def stone_stairs(lod=0, seed=146, n=10, rise=8.0, tread=14.0, W=160.0):
    """broad temple stair: ten worn steps rising 80 u toward +x, stepped cheek walls with newel blocks, a landing at the top.
    Origin at the foot, centre of the first riser."""
    rng = np.random.RandomState(seed)
    m = geo.Mesh(); H = []
    B = MG.pts_box
    for i in range(n):
        x0 = i * tread + rng.uniform(-0.8, 0.8)
        st = blk(x0, -W / 2 + rng.uniform(-1.5, 1.5), 0, (i + 1) * tread + 1.5, W / 2 + rng.uniform(-1.5, 1.5), (i + 1) * rise - rng.uniform(0, 0.7), seed + i, r=1.6)
        m.add(st)
    top = n * rise; run = n * tread
    m.add(blk(run, -W / 2 - 18, 0, run + 30, W / 2 + 18, top, seed + 20))
    H += [MG.wedge_pts(-tread / 2, run - tread / 2, -W / 2, W / 2, 0, top), B(run - tread / 2, -W / 2 - 18, 0, run + 30, W / 2 + 18, top)]
    for s in (-1, 1):
        y0, y1 = (W / 2, W / 2 + 18) if s > 0 else (-W / 2 - 18, -W / 2)
        for k, (xa, xb, hh) in enumerate(((-4, 46, 34), (46, 94, 62), (94, run, 90))):
            m.add(blk(xa, y0, 0, xb, y1, hh, seed + 30 + k + s)); m.add(blk(xa - 1.5, y0 - 1.5, hh, xb + 1.5, y1 + 1.5, hh + 5, seed + 40 + k + s, mono=1.0))
            H.append(B(xa, y0, 0, xb, y1, hh + 5))
            m.add(panel(xa + 5, 8 + k * 26, xb - 5, hh - 5, y1 if s > 0 else y0, seed + 50 + k + s, face=s))
        m.add(blk(-22, y0 - 2, 0, -4, y1 + 2, 44, seed + 60 + s)); m.add(lotus(9, 20, seed + 62 + s, sides=8).transform(None, (-13, (y0 + y1) / 2, 44)))
        H.append(B(-22, y0 - 2, 0, -4, y1 + 2, 46))
    return m, H


def lintel_fallen(lod=0, seed=147):
    """a carved lintel broken in two, lying half sunk, with chips"""
    rng = np.random.RandomState(seed)
    m = geo.Mesh(); H = []
    for k, (L, c, e) in enumerate(((94, (-40, 0, 12), (6, -5, 8)), (62, (50, 9, 10), (-15, 8, -22)))):
        R = geo.euler(*e)
        b = geo.rbox(L, 30, 34, r=1.6, seg=1, mat='stone', part=geo.frame(seed=seed + k, mono=1.0)); b.transform(R, c); m.add(b)
        p = MG.box(-L / 2 + 3, -16.4, -14, L / 2 - 3, -15, 14, 'stone', geo.frame(seed=seed + 4 + k, carve=1.0, mono=1.0), r=0.5); p.transform(R, c); m.add(p)
        H.append(MG.xform_pts(MG.pts_box(-L / 2, -15, -17, L / 2, 15, 17), R, c))
    for k in range(7):
        s = geo.rbox(rng.uniform(5, 12), rng.uniform(4, 9), rng.uniform(3, 7), r=1.0, seg=1, mat='stone', part=geo.frame(seed=seed + 10 + k, mono=1.0))
        s.transform(geo.euler(rng.uniform(0, 360), rng.uniform(-20, 20), rng.uniform(-20, 20)), (rng.uniform(-10, 30), rng.uniform(-34, 34), rng.uniform(1, 3))); m.add(s)
    return m, H


def khmer_pillar(lod=0, seed=148, broken=False):
    """square gallery pillar (Angkor style): a moulded base, a 20-u shaft with carved panels (apsaras) on all four faces, a stepped
    capital and an abacus; broken = the shaft snapped at mid height with a jagged top, the capital lying at its foot"""
    rng = np.random.RandomState(seed)
    m = geo.Mesh(); H = []
    B = MG.pts_box
    m.add(blk(-15, -15, 0, 15, 15, 7, seed, r=1.4)); m.add(blk(-13, -13, 7, 13, 13, 13, seed + 1, mono=1.0, r=1.6))
    top = 64.0 + rng.uniform(-6, 10) if broken else 132.0
    sh = MG.box(-10, -10, 13, 10, 10, top, 'stone', geo.frame(seed=seed + 2, mono=1.0), r=1.0, div=(2, 2, 8))
    if broken:      # jagged break: splintered chunks still standing on the stump
        for k in range(3):
            ch = geo.rbox(rng.uniform(7, 12), rng.uniform(7, 12), rng.uniform(5, 11), r=0.8, seg=1, mat='stone', part=geo.frame(seed=seed + 30 + k, mono=1.0))
            ch.transform(geo.euler(rng.uniform(0, 90), rng.uniform(-18, 18), rng.uniform(-18, 18)), (rng.uniform(-4, 4), rng.uniform(-4, 4), top + rng.uniform(-1, 3))); m.add(ch)
    m.add(sh)
    for ang in (0, 90, 180, 270):
        p = panel(-7, 22, 7, min(top - 8, 112), -10.0, seed + 4 + ang // 90, thick=1.2)
        p.transform(geo.rot('z', ang)); m.add(p)
    H.append(B(-15, -15, 0, 15, 15, top))
    if not broken:
        m.add(blk(-13, -13, 132, 13, 13, 138, seed + 10, mono=1.0, r=1.6)); m.add(blk(-16, -16, 138, 16, 16, 146, seed + 11, mono=1.0, r=1.8))
        H.append(B(-16, -16, 132, 16, 16, 146))
    else:
        cap = geo.Mesh(); cap.add(blk(-13, -13, 0, 13, 13, 6, seed + 10, mono=1.0, r=1.6)); cap.add(blk(-16, -16, 6, 16, 16, 14, seed + 11, mono=1.0, r=1.8))
        cap.transform(geo.euler(rng.uniform(0, 90), 84, 0), (34, 6, 16)); m.add(cap)
        H.append(B(18, -12, 0, 50, 24, 33))
        m.add(rubble(5, 22, -18, 18, seed + 20, size=(6, 16)))
    return m, H


def enclosure_wall(lod=0, seed=150, ruin=False):
    """192 u of the laterite enclosure wall along x: a moulded footing, laterite courses, a sandstone coping with a rounded crest;
    ruin = collapsed in steps toward +x, the fallen blocks spilled on both sides"""
    rng = np.random.RandomState(seed)
    m = geo.Mesh(); H = []
    B = MG.pts_box
    m.add(blk(-96, -19, 0, 96, 19, 10, seed, mat='laterite', r=1.6)); H.append(B(-96, -19, 0, 96, 19, 10))
    steps = ((-96, -20, 104), (-20, 34, 78), (34, 70, 52), (70, 96, 26)) if ruin else ((-96, 96, 104),)
    for k, (xa, xb, hh) in enumerate(steps):
        m.add(blk(xa, -15, 10, xb, 15, hh, seed + 1 + k, mat='laterite', r=1.2))
        H.append(B(xa, -15, 10, xb, 15, hh))
        if k == 0:
            m.add(blk(xa, -18, hh, xb, 18, hh + 6, seed + 10, r=1.8, mono=1.0))
            m.add(geo.tube([(xa + 1, 0, hh + 6), (xb - 1, 0, hh + 6)], 13.0, sides=10, mat='stone', part=geo.frame(seed=seed + 11, mono=1.0)).transform(None, (0, 0, 0)))
            H.append(B(xa, -18, hh, xb, 18, hh + 19))
        else:        # broken top: blocks half out of their course
            for q in range(int((xb - xa) / 18)):
                bx = xa + 9 + q * 18 + rng.uniform(-2, 2)
                b = geo.rbox(rng.uniform(14, 18), rng.uniform(22, 28), rng.uniform(8, 12), r=1.2, seg=1, mat='laterite', part=geo.frame(seed=seed + 20 + k * 10 + q, mono=1.0))
                b.transform(geo.euler(rng.uniform(-8, 8), rng.uniform(-6, 6), rng.uniform(-8, 8)), (bx, rng.uniform(-3, 3), hh + 4)); m.add(b)
    if ruin:
        m.add(rubble(9, 70, 34, 34, seed + 40, size=(10, 24))); m.add(rubble(7, 60, -36, 28, seed + 50, size=(10, 22)))
        H += [B(40, 18, 0, 104, 64, 20), B(36, -62, 0, 92, -18, 18)]
    return m, H


def root_wall(lod=0, seed=152):
    """a length of temple wall split by a strangler fig: the blocks pushed apart and tilted round a root mass that pours over the top
    and down both faces into the ground, 170 long"""
    rng = np.random.RandomState(seed)
    m = geo.Mesh(); H = []
    B = MG.pts_box
    for k, (xa, xb, tilt) in enumerate(((-86, -26, -5.0), (-22, 14, 0.0), (26, 86, 6.0))):
        if k == 1:      # the middle is split open: two leaning blocks with the root between
            for sx, ang in ((-1, -9.0), (1, 11.0)):
                b = geo.rbox(16, 30, 58, r=1.4, seg=1, mat='stone', part=geo.frame(seed=seed + 5 + sx, mono=1.0))
                b.transform(geo.euler(0, ang, rng.uniform(-4, 4)), (sx * 12, rng.uniform(-3, 3), 30)); m.add(b)
            H.append(B(-22, -16, 0, 22, 16, 58))
            continue
        for c_ in range(4):      # dry-laid courses, each a little displaced
            for q in range(int((xb - xa) / 30)):
                bx = xa + 15 + q * 30 + rng.uniform(-2, 2) + c_ * 2.0 * np.sign(tilt)
                b = geo.rbox(rng.uniform(27, 31), 30, 17, r=1.3, seg=1, mat='stone', part=geo.frame(seed=seed + 10 + k * 40 + c_ * 8 + q, mono=1.0, carve=1.0 if (q + c_) % 5 == 0 else 0.0))
                b.transform(geo.euler(rng.uniform(-3, 3), tilt * c_ / 3.0 + rng.uniform(-2, 2), rng.uniform(-3, 3)), (bx + tilt * c_ * 0.8, rng.uniform(-1.5, 1.5), 8.5 + c_ * 17.5))
                m.add(b)
        H.append(B(xa - 4, -16, 0, xb + 4, 16, 72))
    # roots: a mass over the top of the split, cables down both faces, flaring into buttresses at the ground
    rp = geo.frame(seed=seed + 90)
    for f in (-1, 1):
        for k in range(5):
            x0 = rng.uniform(-30, 30); x1 = x0 + rng.uniform(-60, 60)
            pts = np.array([[x0 * 0.3, 0, 84 + rng.uniform(-4, 6)], [x0, f * 10, 80], [x0 + (x1 - x0) * 0.3, f * 19, 64], [x0 + (x1 - x0) * 0.6, f * 18, 34],
                            [x1, f * (22 + rng.uniform(0, 10)), 8], [x1 + rng.uniform(-14, 14), f * (40 + rng.uniform(0, 26)), -4]])
            r0 = rng.uniform(3.0, 6.0)
            m.add(geo.tube(pts, [r0 * 1.5, r0 * 1.2, r0, r0 * 0.95, r0 * 1.3, r0 * 0.12], sides=8, mat='root', part=rp))
    m.add(weather(geo.tube([(0, 0, 54), (2, 0, 72), (-2, 0, 88), (3, 1, 98), (10, 3, 104), (16, 5, 103)], [11, 13, 12, 9, 5, 0.6], sides=10, mat='root', part=rp), 1.2, 0.12, seed))
    for k in range(4):       # thin aerial roots hanging from above
        x0 = rng.uniform(-40, 40); y0 = rng.uniform(-6, 6)
        m.add(geo.tube([(x0, y0, 102), (x0 + rng.uniform(-6, 6), y0 + rng.uniform(-14, 14), 60), (x0 + rng.uniform(-10, 10), y0 + rng.uniform(-20, 20), 0)], [1.6, 1.3, 0.3], sides=5, mat='root', part=rp))
    m.add(rubble(6, 20, 40, 30, seed + 120, size=(9, 22)))
    H.append(B(-14, -14, 54, 14, 14, 104))
    return m, H


def paving_slabs(lod=0, seed=154, size=192.0):
    """a square of worn paving: slabs of uneven size and height, a few tilted or missing, the joints left for moss; laid on a terrace
    top (walk-over, 1-4 u thick)"""
    rng = np.random.RandomState(seed)
    m = geo.Mesh(); h = size / 2
    y = -h
    while y < h - 1:
        dy = min(rng.uniform(28, 42), h - y)
        x = -h + rng.uniform(0, 20) * (1 if rng.rand() < 0.5 else 0)
        if x > -h + 1: x = -h
        while x < h - 1:
            dx = min(rng.uniform(30, 58), h - x)
            if rng.rand() > 0.07:
                th = rng.uniform(1.4, 3.6)
                b = geo.rbox(dx - 1.6, dy - 1.6, th, r=0.7, seg=1, mat='stone', part=geo.frame(seed=seed + int(x * 7 + y * 13) % 997, mono=1.0, carve=1.0 if rng.rand() < 0.06 else 0.0))
                b.transform(geo.euler(rng.uniform(-2, 2), rng.uniform(-2.5, 2.5) if rng.rand() < 0.2 else 0.0, rng.uniform(-2.5, 2.5) if rng.rand() < 0.2 else 0.0),
                            (x + dx / 2, y + dy / 2, th / 2 - 0.8))
                m.add(b)
            x += dx
        y += dy
    return m, []


# ---------------------------------------------------------------- specs
def _sh():
    return {'stone': M.khmer_stone, 'laterite': M.laterite, 'lion': lambda c: M.khmer_stone(c, tone=S._c(0.43, 0.41, 0.35), moss=1.0),
            'root': M.jungle_bark}


def _spec(fn, size=2048, **kw):
    a, hulls = fn(lod=0, **kw)
    return dict(lods=[a], single_lod=True, size=size, ground=0.0, surface='concrete', metal=False, shaders=_sh(), stock={}, hulls=hulls)


def specs():
    return {
        'khmer_gate': lambda: _spec(khmer_gate, 2048),
        'khmer_tower': lambda: _spec(khmer_tower, 2048),
        'naga_balustrade': lambda: _spec(naga_balustrade, 1024),
        'guardian_statue': lambda: _spec(guardian_statue, 1024),
        'fallen_blocks': lambda: _spec(fallen_blocks, 1024),
        'stone_stairs': lambda: _spec(stone_stairs, 2048),
        'lintel_fallen': lambda: _spec(lintel_fallen, 1024),
        'khmer_pillar': lambda: _spec(khmer_pillar, 1024),
        'khmer_pillar_broken': lambda: _spec(khmer_pillar, 1024, broken=True, seed=149),
        'enclosure_wall': lambda: _spec(enclosure_wall, 1024),
        'enclosure_wall_ruin': lambda: _spec(enclosure_wall, 1024, ruin=True, seed=151),
        'root_wall': lambda: _spec(root_wall, 2048),
        'paving_slabs': lambda: _spec(paving_slabs, 1024),
    }
