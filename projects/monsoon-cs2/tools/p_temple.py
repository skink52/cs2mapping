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
def naga_balustrade(lod=0, seed=143):
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
    }
