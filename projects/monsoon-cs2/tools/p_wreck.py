"""The crash site (flag E) and battlefield wrecks: a C-123 Provider's fuselage section you can walk through, its broken wing and
one engine, a sunken river patrol boat, a burnt 2.5-ton truck, a burnt M113, an air-drop cargo pallet, a draped parachute canopy.

Origins on the ground (pbr_wreck: on the river bed, it lists and is meant to sit half under water). Long axis along x, nose / bow /
front to +x. The fuselage is open at both ends and has a cargo door on the +y side; its floor is 12 u above the ground (one step).
"""
import numpy as np
import geo
import mv_geo as MG
import mv_shaders as M
import shaders as S
from noise import fbm, smoothstep


def _thin(pts, n=160, seed=0):
    """subsample a point cloud for a convex hull piece"""
    pts = np.asarray(pts, float)
    if len(pts) <= n: return pts
    idx = np.random.RandomState(seed).choice(len(pts), n, replace=False)
    ext = [pts[:, k].argmin() for k in range(3)] + [pts[:, k].argmax() for k in range(3)]
    return pts[np.unique(np.concatenate([idx, ext]))]


def _settle(m, R=None, sink=0.0, extra=()):
    """rotate a wreck into its resting pose and drop it so its lowest point is `sink` below the ground; returns the shift used"""
    if R is not None: m.transform(R)
    dz = -m.V[:, 2].min() - sink
    m.transform(None, (0, 0, dz))
    return dz


def airfoil(chord, thick, n=16, z0=0.0):
    """closed (y, z) loop: leading edge at +y, blunt nose, thin trailing edge"""
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    y = chord / 2 * np.cos(t)
    z = thick / 2 * np.sin(t) * (0.55 + 0.45 * np.cos(t)) * 1.25
    return np.stack([y, z + z0], 1)


# ---------------------------------------------------------------- C-123
def c123_fuselage(lod=0, seed=131, L=700.0):
    hw = 76.0; zlo, zhi, zf = -14.0, 134.0, 12.0
    rng = np.random.RandomState(seed)
    xs = [-350, -300, -262, -232, -195, -158, -110, -60, -10, 40, 90, 140, 190, 240, 290, 330, 350]
    def sec(x, inset=0.0):
        up = 22.0 * (max(0.0, (-150 - x) / 200.0)) ** 1.5              # the rear fuselage sweeps up
        return MG.rrect_section(hw - inset, zlo + up + inset * 0.7, zhi - inset, 3.2, n=24, flat_bottom=0.45)
    outer = MG.loft([(x, sec(x)) for x in xs], 'camo', geo.frame(seed=seed, burnt=1.0, burnt_x=340.0, burnt_w=230.0, panel_u=40.0, panel_v=40.0), n=24, cap_front=False, cap_back=False, seam_split=4)
    inner = MG.loft([(x, sec(x, 3.0)) for x in xs], 'interior', geo.frame(seed=seed + 1, burnt=1.0, burnt_x=340.0, burnt_w=200.0), n=24, cap_front=False, cap_back=False, seam_split=4)
    inner.F = inner.F[:, ::-1]
    holes = lambda c: ((c[:, 1] > hw * 0.55) & (c[:, 0] > -232) & (c[:, 0] < -158) & (c[:, 2] > zf + 6) & (c[:, 2] < 104)) | \
                      ((c[:, 2] > 112) & (c[:, 0] > 262) & (c[:, 1] < 24)) | ((c[:, 0] > 310) & (c[:, 1] < -40) & (c[:, 2] > 60))
    m = geo.Mesh()
    for sk in (outer, inner):
        MG.remove_faces(sk, holes)
        V = sk.V                                                      # ragged torn ends, light crumpling everywhere
        n1 = np.abs(fbm(V[:, 1] * 0.07, V[:, 2] * 0.07, 3.0, 3, seed=seed))
        V[:, 0] -= np.where(V[:, 0] > 349, n1 * 46, 0.0); V[:, 0] += np.where(V[:, 0] < -349, n1 * 34, 0.0)
        cr = fbm(V[:, 0] * 0.012, V[:, 1] * 0.02, V[:, 2] * 0.02, 3, seed=seed + 2)
        V[:, 1] += cr * 3.0 * np.sign(V[:, 1]); V[:, 2] += cr * 3.5 * (V[:, 2] > 60)
        sk.V = V; sk.recompute_normals(angle=48); m.add(sk)
    ip = geo.frame(seed=seed + 3, panel_u=44.0, panel_v=44.0)
    m.add(MG.box(-340, -64, zf - 4, 340, 64, zf, 'floor', ip, r=0.4))
    for x in np.arange(-325, 341, 47.5):                               # frames
        lp = sec(x, 5.0); lp = lp[lp[:, 1] > zf - 2]
        order = np.argsort(np.arctan2(lp[:, 1] - 60, lp[:, 0]))
        lp = lp[order]
        m.add(geo.tube(np.stack([np.full(len(lp), x), lp[:, 0], lp[:, 1]], 1), 2.2, sides=4, mat='interior', part=ip, caps=False))
    for (y, z) in ((-71, 44), (-70, 84), (71, 44), (70, 84), (-40, 128), (40, 128)):          # stringers
        m.add(MG.cyl((-338, y * 0.985, z), (338, y * 0.985, z), 1.3, 'interior', ip, sides=4))
    for k, (x0, x1) in enumerate(((-120, 20), (60, 230))):                                   # troop seats along the -y wall, one run collapsed
        dz = 0 if k == 0 else -14
        m.add(MG.plate((x0, -70, 30 + dz), (x1 - x0, 0, 0), (0, 15, -2 + dz * 0.6), 'seat', geo.frame(seed=seed + 5 + k), thick=0.8))
        m.add(MG.cyl((x0, -55, 29 + dz * 1.6), (x1, -55, 29 + dz * 1.6), 0.9, 'interior', ip, sides=5))
        for x in np.linspace(x0, x1, 5): m.add(MG.cyl((x, -55, 29 + dz * 1.6), (x, -58, zf), 0.8, 'interior', ip, sides=4))
        m.add(MG.plate((x0, -71, 52), (x1 - x0, 0, 0), (0, 1.5, 26), 'seat', geo.frame(seed=seed + 8 + k), thick=0.6))
    for k in range(5):                                                 # cables and torn lining hanging from the roof
        x = rng.uniform(-300, 320); y = rng.uniform(-40, 40)
        m.add(MG.limb((x, y, 128), (x + rng.uniform(-14, 14), y + rng.uniform(-10, 10), 128 - rng.uniform(26, 62)), 0.7, 0.5, 'cable', seed + 20 + k, sides=4, n=4, wob=2.5))
    for k, (x, y) in enumerate(((-250, -20), (120, 30), (250, -34))):  # loose ammo boxes on the floor
        m.add(MG.box(-9, -5, 0, 9, 5, 9, 'od', geo.frame(seed=seed + 30 + k), r=0.5).transform(geo.rot('z', 30 * k + 15), (x, y, zf)))
    # centre wing stub on top (high wing), torn off outboard, with spar ends
    wg = MG.loft([(-128, airfoil(128, 20)), (-60, airfoil(134, 23)), (60, airfoil(134, 23)), (128, airfoil(128, 20))], 'camo', geo.frame(seed=seed + 40, burnt=0.6, burnt_x=200.0, burnt_w=160.0, panel_u=36.0, panel_v=36.0), n=16, seam_split=2)
    wg.transform(geo.rot('z', -90), (86, 0, 141)); m.add(wg)
    for s in (-1, 1):
        for xo in (66, 112): m.add(MG.box(xo - 2, s * 126, 134, xo + 2, s * 150, 148, 'alu', ip, r=0.3))
    STAR = MG.star_img(256); USAF = MG.text_img(['U.S. AIR FORCE'], 512, 64, color=(0.08, 0.08, 0.10), fonts=MG.SANS)
    m.add(geo.decal('star', (-96, -hw - 0.3, 34), (1, 0, 0), (0, 0, 1), (60, 60), lift=1.6))
    m.add(geo.decal('usaf', (30, -hw - 0.3, 96), (1, 0, 0), (0, 0, 1), (150, 17), lift=1.9))
    B = MG.pts_box
    H = [B(-340, -66, zlo, 340, 66, zf), B(-350, -78, zf, 350, -66, 112), B(-350, 66, zf, -234, 78, 112), B(-156, 66, zf, 350, 78, 112),
         B(-350, -78, 112, 262, 78, 136), B(-234, 66, 104, -156, 78, 112), B(20, -130, 130, 152, 130, 154)]
    return m, H, dict(star=STAR, usaf=USAF)


def c123_wing(lod=0, seed=132, L=600.0):
    """outer wing panel lying on the ground, torn at the root (-x) with spars and a rib showing, tip bent up, a flap hanging"""
    xs = np.linspace(-L / 2, L / 2, 9)
    secs = []
    for x in xs:
        t = (x + L / 2) / L
        secs.append((x, airfoil(156 - 74 * t, 25 - 14 * t, n=16, z0=0.0)))
    w = MG.loft(secs, 'camo', geo.frame(seed=seed, burnt=1.0, burnt_x=-L / 2, burnt_w=170.0, panel_u=38.0, panel_v=38.0), n=16, cap_front=True, cap_back=False, seam_split=2)
    V = w.V
    V[:, 0] += np.where(V[:, 0] < -L / 2 + 1, np.abs(fbm(V[:, 1] * 0.06, V[:, 2] * 0.3, 1.0, 3, seed=seed)) * 40, 0.0)
    V[:, 2] += np.clip((V[:, 0] - 190) / 110, 0, 1) ** 2 * 26 + 3.0 * fbm(V[:, 0] * 0.02, V[:, 1] * 0.03, 0.0, 3, seed=seed + 1)
    w.V = V; w.recompute_normals(angle=48)
    m = geo.Mesh(); m.add(w)
    ip = geo.frame(seed=seed + 2)
    rib = geo.prism([(y, z) for y, z in airfoil(150, 23, n=16) * 0.96], -L / 2 + 22, -L / 2 + 23.5, 'interior', ip)       # prism: poly (x, z) extruded along y
    rib.V = rib.V[:, [1, 0, 2]]; rib.F = rib.F[:, ::-1]               # (a, y, z) -> (y, a, z): the plate now stands across the wing
    rib.recompute_normals(angle=40); m.add(rib)
    for yo in (30, -22):
        m.add(MG.box(-L / 2 - 26, yo - 2.5, -8, -L / 2 + 30, yo + 2.5, 8, 'alu', ip, r=0.4))
    fl = MG.plate((-200, -80, 2), (150, 0, 0), (0, -30, -9), 'camo', geo.frame(seed=seed + 4, burnt=0.4, burnt_x=-300.0, burnt_w=200.0), thick=2.0); m.add(fl)
    m.add(MG.cyl((282, 28, 12), (282, 52, 11), 1.0, 'alu', ip, sides=5))
    STAR = MG.star_img(256)
    R = geo.euler(0, -2.5, 5.0)
    dec = geo.decal('star', (70, -34, 9.2), (1, 0, 0), (0, 1, 0), (72, 72), lift=2.4)
    m.add(dec)
    dz = _settle(m, R, sink=3.0)
    return m, [_thin(m.V[m.V[:, 0] < 0], seed=1), _thin(m.V[m.V[:, 0] >= 0], seed=2)], dict(star=STAR)


def c123_engine(lod=0, seed=133):
    """R-2800 radial torn from its nacelle: two rows of finned cylinders, exhaust ring, half the cowling, a three-blade propeller
    with one blade bent back; lying nose-down in the dirt"""
    m = geo.Mesh()
    ep = geo.frame(seed=seed)
    m.add(MG.lathe_x([(0, -6), (15, -6), (18, 4), (18, 34), (13, 44), (8.5, 58), (0, 58)], 'alu', sides=14, part=ep))
    fin = [(4.6, 0)]
    for k in range(6): fin += [(6.9, 1.2 + k * 3.0), (6.9, 2.2 + k * 3.0), (4.9, 2.8 + k * 3.0), (4.9, 3.8 + k * 3.0)]
    fin += [(6.2, 20.5), (6.2, 25), (3.0, 27), (0, 27)]
    for row, x in enumerate((8.0, 27.0)):
        for k in range(9):
            a = np.radians(k * 40 + row * 20)
            c = geo.lathe(fin, sides=8, mat='cyl', part=ep)
            c.transform(geo.rot('x', np.degrees(a) - 90) , (x, 16.5 * np.cos(a), 16.5 * np.sin(a))); m.add(c)
            m.add(MG.cyl((x + 5, 20 * np.cos(a + 0.2), 20 * np.sin(a + 0.2)), (-2, 31 * np.cos(a + 0.1), 31 * np.sin(a + 0.1)), 1.5, 'rust', ep, sides=5))
    ring = [(-4, 33 * np.cos(q), 33 * np.sin(q)) for q in np.linspace(0, 2 * np.pi, 19)]
    m.add(geo.tube(ring, 3.2, sides=6, mat='rust', part=ep, caps=False))
    # cowling: what is left of it (about 220 degrees)
    th = np.radians(np.linspace(25, 245, 14)); xs = np.array([-8, 14, 40, 58, 66.0]); rr = np.array([45, 46.5, 46, 43, 37.0])
    P = np.zeros((len(xs), len(th), 3))
    P[..., 0] = xs[:, None]; P[..., 1] = rr[:, None] * np.cos(th)[None, :]; P[..., 2] = rr[:, None] * np.sin(th)[None, :]
    P[..., 0] += 5 * fbm(P[..., 1] * 0.08, P[..., 2] * 0.08, 0.5, 2, seed=seed)
    m.add(MG.sheet(P, 'camo', geo.frame(seed=seed + 1, burnt=1.0, burnt_x=0.0, burnt_w=400.0)))
    # propeller
    m.add(MG.lathe_x([(0, 56), (8, 56), (10.5, 64), (9, 76), (4, 88), (0, 91)], 'alu', sides=12, part=ep))
    for k in range(3):
        b = geo.rbox(2.6, 17, 92, r=1.2, seg=1, mat='blade', part=geo.frame(seed=seed + 5 + k), div=(1, 1, 6), center=(0, 0, 54))
        z = b.V[:, 2]; t = np.clip((z - 8) / 92, 0, 1)
        b.V[:, 1] *= (1.0 - 0.45 * t) * (0.55 + 0.9 * np.sin(np.pi * np.clip(t * 0.9 + 0.1, 0, 1)) * 0.5)
        ang = np.radians(34 - 26 * t); y0, x0 = b.V[:, 1].copy(), b.V[:, 0].copy()
        b.V[:, 0] = x0 * np.cos(ang) + y0 * np.sin(ang); b.V[:, 1] = -x0 * np.sin(ang) + y0 * np.cos(ang)
        if k == 0: b.V[:, 0] -= (np.clip(t - 0.35, 0, 1) / 0.65) ** 2 * 40          # bent back on impact
        if k == 2: b.V[:, 0] += (np.clip(t - 0.6, 0, 1) / 0.4) ** 2 * 16
        b.recompute_normals(angle=50)
        b.transform(geo.rot('x', k * 120 + 15), (70, 0, 0)); m.add(b)
    # firewall and torn bearer tubes at the back
    m.add(MG.lathe_x([(0, -14), (31, -14), (31, -12), (0, -12)], 'rust', sides=14, part=ep))
    for k in range(6):
        a = k * np.pi / 3 + 0.3
        m.add(MG.cyl((-12, 26 * np.cos(a), 26 * np.sin(a)), (-40 - 6 * (k % 2), 10 * np.cos(a + 0.6), 10 * np.sin(a + 0.6)), 1.6, 'rust', ep, sides=5))
    core = len(m.V)
    _settle(m, geo.euler(25, 38, 12), sink=9.0)
    return m, [_thin(m.V[m.V[:, 2] < 70], seed=3)]


# ---------------------------------------------------------------- river patrol boat
def pbr_wreck(lod=0, seed=134):
    """PBR Mk II hulk, 400 u: fibreglass hull listing to port and down by the stern, foredeck gun tub with bent twin .50s, open
    cockpit well, collapsed canopy frame, engine covers aft"""
    m = geo.Mesh()
    xs = np.linspace(-200, 200, 13)
    def dims(x):
        t = x / 200.0
        w = 66 * (1 - 0.93 * max(0.0, t) ** 2.4) * (1 - 0.05 * max(0.0, -t))
        return max(w, 3.0), 14 * max(0.0, t) ** 3, 46 + 12 * max(0.0, t) ** 2
    secs = [(x, MG.rrect_section(dims(x)[0], dims(x)[1], dims(x)[2], 2.5, n=16, flat_bottom=0.35)) for x in xs]
    hp = geo.frame(seed=seed, panel_u=0.0)
    hull = MG.loft(secs, 'boat', hp, n=16, seam_split=2)
    MG.remove_faces(hull, lambda c: (c[:, 2] > 44) & (np.abs(c[:, 1]) < 60) & (c[:, 0] < 150))
    m.add(hull)
    # deck from gunwale to gunwale, with the cockpit well cut out
    P = np.zeros((len(xs), 5, 3))
    for i, x in enumerate(xs):
        w, zb, zt = dims(x)
        P[i, :, 0] = x; P[i, :, 1] = np.linspace(-(w - 3), w - 3, 5); P[i, :, 2] = zt - 2.5 + 2.0 * (1 - (np.linspace(-1, 1, 5)) ** 2)
    deck = geo.surface(P, 'deck', geo.frame(seed=seed + 1))
    if deck.face_normals()[:, 2].mean() < 0: deck.F = deck.F[:, ::-1]
    deck.recompute_normals(angle=50)
    MG.remove_faces(deck, lambda c: (c[:, 0] > -40) & (c[:, 0] < 62) & (np.abs(c[:, 1]) < 40))
    m.add(deck)
    well = MG.box(-34, -46, 16, 66, 46, 47, 'deck', geo.frame(seed=seed + 2), r=0.3)
    MG.remove_faces(well, lambda c: c[:, 2] > 46.5); well.F = well.F[:, ::-1]; well.recompute_normals(angle=40); m.add(well)
    gp = geo.frame(seed=seed + 3)
    for s in (-1, 1):                                                  # rub rails
        pts = [(x, s * (dims(x)[0] + 0.5), dims(x)[2] - 3) for x in xs]
        m.add(geo.tube(pts, 2.0, sides=6, mat='rubber', part=gp))
    # forward gun tub and the twin fifties
    tub = geo.lathe([(21, 0), (22.5, 18), (21, 18), (19.5, 1), (19.5, 0)], sides=14, mat='boat', part=hp); tub.transform(None, (118, 0, 52)); m.add(tub)
    m.add(MG.cyl((118, 0, 50), (118, 0, 74), 3.0, 'gunsteel', gp, sides=8))
    for s in (-1, 1):
        m.add(MG.box(106, s * 5 - 2.5, 72, 128, s * 5 + 2.5, 79, 'gunsteel', gp, r=0.6))
        m.add(geo.tube([(128, s * 5, 76), (150, s * 5, 82), (168, s * 6 + 3, 80 - s * 6)], [1.6, 1.3, 1.1], sides=6, mat='gunsteel', part=gp))
    m.add(MG.plate((112, -17, 70), (0, 34, 0), (-5, 0, 22), 'boat', hp, thick=1.2))             # gun shield
    # cockpit: coaming, console, wheel, the canopy frame folded over to port
    m.add(MG.box(54, -30, 47, 62, 30, 66, 'boat', hp, r=1.0)); m.add(MG.box(50, -12, 50, 55, 12, 62, 'gunsteel', gp, r=0.6))
    wheel = [(46, -10 + 6.5 * np.cos(q), 63 + 6.5 * np.sin(q)) for q in np.linspace(0, 2 * np.pi, 13)]
    m.add(geo.tube(wheel, 0.7, sides=4, mat='gunsteel', part=gp, caps=False))
    for x in (-30, 12, 56):
        m.add(geo.tube([(x, -44, 47), (x - 4, -52, 82), (x - 2, -20, 96), (x + 6, 26, 78), (x + 4, 44, 49)], 1.3, sides=5, mat='gunsteel', part=gp))
    m.add(MG.cyl((-32, -40, 94), (60, -34, 92), 1.2, 'gunsteel', gp, sides=5))
    # aft: engine covers, after gun pedestal, pump outlets, a cleat, the ensign staff
    for s in (-1, 1): m.add(MG.box(-150, s * 34, 46, -74, s * 6, 60, 'boat', hp, r=2.0))
    m.add(MG.cyl((-176, 0, 46), (-176, 0, 78), 3.2, 'gunsteel', gp, sides=8)); m.add(MG.box(-186, -3, 76, -160, 3, 82, 'gunsteel', gp, r=0.6))
    m.add(geo.tube([(-160, 0, 79), (-140, 2, 70), (-128, 6, 56)], [1.5, 1.3, 1.1], sides=6, mat='gunsteel', part=gp))
    for s in (-1, 1): m.add(MG.cyl((-204, s * 22, 14), (-196, s * 22, 15), 7.0, 'gunsteel', gp, sides=10))
    m.add(MG.cyl((-190, 30, 46), (-196, 34, 96), 0.9, 'gunsteel', gp, sides=4))
    dz = _settle(m, geo.euler(0, 5.0, 17.0), sink=7.0)
    hullpts = _thin(m.V[: len(hull.V)] if False else m.V[m.V[:, 2] < 62], n=200, seed=4)
    return m, [hullpts]


# ---------------------------------------------------------------- vehicles
def wheel(r, w, mat_t, mat_r, seed, sides=14, tyre=True):
    """wheel on its side axis (y): a tyre (or bare rim), dished hub"""
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    if tyre:
        prof = [(r * 0.55, -w / 2), (r * 0.9, -w / 2), (r, -w * 0.3), (r, w * 0.3), (r * 0.9, w / 2), (r * 0.55, w / 2)]
        t = geo.lathe(prof, sides=sides, mat=mat_t, part=p); t.transform(geo.rot('x', -90)); m.add(t)
    rr = r * 0.56
    rim = geo.lathe([(0, -w * 0.15), (rr * 0.5, -w * 0.15), (rr, -w * 0.42), (rr * 1.04, -w * 0.5), (rr * 1.04, w * 0.5), (rr, w * 0.42), (rr * 0.5, w * 0.2), (0, w * 0.2)], sides=sides, mat=mat_r, part=p)
    rim.transform(geo.rot('x', -90)); m.add(rim)
    return m


def truck_wreck(lod=0, seed=135):
    """burnt-out M35: bare frame, bed with stake sides and canvas bows, gutted cab, front tyres burnt off so it kneels on its rims"""
    m = geo.Mesh()
    rng = np.random.RandomState(seed)
    p = geo.frame(seed=seed, panel_u=30.0, panel_v=30.0)
    for s in (-1, 1): m.add(MG.box(-130, s * 16 - 2.5, 30, 126, s * 16 + 2.5, 38, 'burnt', p, r=0.5))
    for x in (-110, -46, 10, 70, 118): m.add(MG.box(x - 2, -16, 31, x + 2, 16, 37, 'burnt', p, r=0.4))
    for x in (-72, -24):
        m.add(MG.cyl((x, -44, 20), (x, 44, 20), 3.2, 'rust', p, sides=8)); m.add(MG.lathe_x([(0, -9), (8, -9), (9, 0), (8, 9), (0, 9)], 'rust', sides=10, part=p).transform(None, (x, 0, 20)))
        for s in (-1, 1): m.add(wheel(20, 20, 'ash', 'rust', seed + int(x) + s).transform(None, (x, s * 38, 20)))
    m.add(MG.cyl((92, -42, 12), (92, 42, 12), 3.0, 'rust', p, sides=8))
    for s in (-1, 1): m.add(wheel(21, 15, 'ash', 'rust', seed + 9 + s, tyre=False).transform(None, (92, s * 38, 12)))
    # bed
    m.add(MG.box(-132, -46, 38, 6, 46, 42, 'burnt', p, r=0.5))
    for s in (-1, 1):
        m.add(MG.box(-132, s * 46 - 1, 42, 6, s * 46 + 1, 56, 'burnt', p, r=0.4))
        for x in np.linspace(-126, 0, 6): m.add(MG.box(x - 1.5, s * 46 - 1.5, 42, x + 1.5, s * 46 + 1.5, 74, 'burnt', p, r=0.3))
        for z in (62, 71): m.add(MG.box(-130, s * 46 - 0.8, z - 2.5, 4, s * 46 + 0.8, z + 2.5, 'charwood', geo.frame(seed=seed + 20 + s + z), r=0.3))
    m.add(MG.box(4, -46, 42, 6.5, 46, 74, 'burnt', p, r=0.4))
    m.add(MG.plate((-132, -45, 40), (0, 90, 0), (-9, 0, -30), 'burnt', p, thick=1.6))                      # tailgate hanging down
    for k, x in enumerate((-120, -84, -46, -8)):                       # canvas bows, two of them buckled
        sq = 1.0 if k % 2 == 0 else 0.72
        pts = [(x + (0 if sq == 1 else 10 * np.sin(q * 2)), 45 * np.cos(q), 74 + 40 * sq * np.sin(q)) for q in np.linspace(0, np.pi, 9)]
        m.add(geo.tube(pts, 1.2, sides=5, mat='burnt', part=p))
    # cab
    m.add(MG.box(8, -45, 38, 62, 45, 50, 'burnt', p, r=0.6))
    for s in (-1, 1):
        m.add(MG.box(8, s * 45 - 1, 50, 14, s * 45 + 1, 104, 'burnt', p, r=0.4))                          # B pillar
        m.add(MG.plate((16, s * 45, 44), (38, s * 22, 0), (0, 0, 34), 'burnt', geo.frame(seed=seed + 30 + s, panel_u=20.0, panel_v=20.0), thick=1.4))   # doors swung open
        m.add(MG.cyl((61, s * 43, 70), (56, s * 43, 106), 1.6, 'burnt', p, sides=6))                      # windscreen posts
    m.add(MG.box(8, -45, 50, 10, 45, 80, 'burnt', p, r=0.4)); m.add(MG.box(60, -45, 50, 62.5, 45, 70, 'burnt', p, r=0.4))
    m.add(MG.cyl((56, -43, 106), (56, 43, 106), 1.6, 'burnt', p, sides=6)); m.add(MG.cyl((58.5, 0, 70), (56, 0, 106), 1.2, 'burnt', p, sides=5))
    for s in (-1, 1): m.add(MG.cyl((10, s * 44, 104), (56, s * 43, 106), 1.2, 'burnt', p, sides=5))
    for s in (-1, 1):                                                  # seat frames (springs), steering wheel
        m.add(MG.box(16, s * 22 - 16, 50, 40, s * 22 + 16, 56, 'rust', p, r=1.0)); m.add(MG.box(13, s * 22 - 16, 56, 17, s * 22 + 16, 78, 'rust', p, r=1.0))
    sw = [(46 + 2.5 * np.sin(q), 22 + 8.5 * np.cos(q), 82 + 8 * np.sin(q)) for q in np.linspace(0, 2 * np.pi, 13)]
    m.add(geo.tube(sw, 0.8, sides=4, mat='rust', part=p, caps=False)); m.add(MG.cyl((46, 22, 82), (60, 22, 62), 1.0, 'rust', p, sides=5))
    # hood, wings, radiator, bumper, lamps
    hood = geo.rbox(60, 60, 30, r=7, seg=2, mat='burnt', part=geo.frame(seed=seed + 40, panel_u=30.0, panel_v=0.0), center=(92, 0, 61)); m.add(hood)
    m.add(MG.plate((64, -30, 77), (52, 0, 16), (0, 30, 9), 'burnt', geo.frame(seed=seed + 41), thick=1.2))   # one hood half thrown open
    for s in (-1, 1):
        m.add(MG.plate((70, s * 30, 52), (44, 0, -3), (0, s * 17, -2), 'burnt', p, thick=1.4)); m.add(MG.plate((114, s * 30, 49), (8, 0, -14), (0, s * 17, -1), 'burnt', p, thick=1.4))
        m.add(geo.lathe([(0, 0), (4.5, 0), (5, 3), (4, 5), (0, 5)], sides=10, mat='rust', part=p).transform(geo.rot('y', 90), (122, s * 22, 56)))
    m.add(MG.box(121, -26, 44, 124, 26, 74, 'rust', p, r=0.6)); m.add(MG.box(124, -47, 30, 131, 47, 40, 'burnt', p, r=1.0))
    m.add(MG.cyl((20, -40, 28), (56, -40, 28), 9.0, 'burnt', p, sides=10))                                # fuel tank
    m.recompute_normals(angle=50)
    R = geo.rot('y', 3.2)
    dz = _settle(m, R, sink=1.0)
    B = MG.pts_box
    H = [MG.xform_pts(B(-132, -47, 0, 6, 47, 74), R, (0, 0, dz)), MG.xform_pts(B(6, -46, 0, 131, 46, 78), R, (0, 0, dz))]
    return m, H


def m113_hulk(lod=0, seed=136):
    """burnt M113: sloped glacis, ramp dropped, cargo hatch open, the left track thrown and lying beside it, an RPG hole in the side"""
    import p_guns
    m = geo.Mesh()
    p = geo.frame(seed=seed, panel_u=48.0, panel_v=0.0)
    up = [(-96, 40), (-96, 73), (58, 73), (96, 50), (96, 40)]
    lowp = [(-96, 15), (-96, 40), (96, 40), (96, 34), (78, 14), (-84, 14)]
    upper = geo.prism(up, -53, 53, 'burnt', p); MG.remove_faces(upper, lambda c: c[:, 0] < -95.5)
    lower = geo.prism(lowp, -38, 38, 'burnt', p); MG.remove_faces(lower, lambda c: c[:, 0] < -95.5)
    m.add(upper); m.add(lower)
    # prism caps are single triangles fans: the roof opening is cut as a dark recessed well instead
    inner = MG.box(-95, -36, 17, 44, 36, 71, 'gutted', geo.frame(seed=seed + 1), r=0.3)
    MG.remove_faces(inner, lambda c: c[:, 0] < -94.5); inner.F = inner.F[:, ::-1]; inner.recompute_normals(angle=40); m.add(inner)
    m.add(MG.box(-82, -28, 72.6, -24, 28, 73.5, 'void', geo.frame(seed=seed + 2), r=0.1))                     # the open cargo hatch: a black opening on the roof
    for (xa, ya, xb, yb) in ((-84, -30, -22, -28), (-84, 28, -22, 30), (-84, -30, -82, 30), (-24, -30, -22, 30)): m.add(MG.box(xa, ya, 73, xb, yb, 75.5, 'burnt', p, r=0.3))
    m.add(MG.plate((-22, -28, 74), (30, 0, 22), (0, 56, 0), 'burnt', p, thick=1.6))                         # cargo hatch cover standing open
    m.add(MG.plate((-96, 44, 16), (-52, 0, -13), (0, -88, 0), 'burnt', geo.frame(seed=seed + 3, panel_u=30.0, panel_v=30.0), thick=3.0))   # ramp down
    for s in (-1, 1): m.add(MG.box(-97, s * 46 - 3, 14, -93, s * 46 + 3, 73, 'burnt', p, r=0.5))            # rear door frame
    m.add(MG.box(-97, -46, 68, -93, 46, 73, 'burnt', p, r=0.5))
    # running gear: right side (-y) still tracked, left (+y) thrown
    tr = [(-72, 0), (72, 0), (90, 13), (95, 25), (88, 37), (-88, 35), (-95, 24), (-89, 9)]
    m.add(geo.prism(tr, -53, -40, 'track', geo.frame(seed=seed + 4)))
    for x in (-66, -33, 0, 33, 66):
        m.add(MG.cyl((x, -54.5, 12), (x, -52.6, 12), 11, 'ash', p, sides=12)); m.add(MG.cyl((x, -55.5, 12), (x, -54.4, 12), 4, 'rust', p, sides=8))
        m.add(wheel(11.5, 9, 'ash', 'rust', seed + 10 + x, sides=12).transform(None, (x, 46, 11.5)))
    for x, z in ((84, 26), (-84, 24)): m.add(wheel(9, 8, 'rust', 'rust', seed + 20 + x, sides=10).transform(None, (x, 46, z)))
    xs = np.linspace(-150, 60, 22)
    P = np.zeros((len(xs), 2, 3)); P[:, 0, 0] = xs; P[:, 1, 0] = xs
    wig = 9 * np.sin(xs * 0.03) + 78
    P[:, 0, 1] = wig; P[:, 1, 1] = wig + 13; P[:, :, 2] = (1.5 + 2.5 * np.abs(np.sin(xs * 0.11)))[:, None]
    m.add(MG.sheet(P, 'track', geo.frame(seed=seed + 5)))
    # glacis: trim vane, lamps, driver's hatch; cupola with the fifty hanging down
    m.add(MG.plate((62, -44, 72.5), (33, 0, -19.5), (0, 88, 0), 'burnt', geo.frame(seed=seed + 6, panel_u=0.0), thick=1.4))
    for s in (-1, 1): m.add(geo.lathe([(0, 0), (4, 0), (4.5, 3), (0, 3.5)], sides=8, mat='rust', part=p).transform(geo.rot('y', 90), (96.5, s * 40, 45)))
    m.add(geo.lathe([(0, 0), (9, 0), (9, 1.6), (0, 1.6)], sides=12, mat='burnt', part=p).transform(geo.rot('y', -62), (40, 30, 74)))
    m.add(geo.lathe([(11, 0), (14, 0), (14, 9), (11, 9)], sides=14, mat='burnt', part=p).transform(None, (12, -14, 73)))
    m.add(geo.lathe([(0, 0), (11, 0), (11, 1.8), (0, 1.8)], sides=14, mat='burnt', part=p).transform(geo.rot('y', 72), (-1, -14, 76)))
    g = p_guns.m2_gun(lod=1, seed=seed + 7)
    for c in g.charts: c['mat'] = 'burnt' if c['mat'] not in ('gunsteel',) else c['mat']
    g.transform(geo.euler(-28, 24, 0), (16, -14, 86)); m.add(g)
    m.add(MG.cyl((12, -14, 73), (14, -14, 86), 2.2, 'rust', p, sides=6))
    hole = [(10 + 6.5 * np.cos(q) * (1 + 0.25 * np.sin(q * 5)), -53.5, 52 + 6.5 * np.sin(q) * (1 + 0.25 * np.cos(q * 4))) for q in np.linspace(0, 2 * np.pi, 14, endpoint=False)]
    m.add(geo.disk((10, -53.5, 52), hole, (0, -1, 0), 'void', geo.frame(seed=seed + 8)))
    m.recompute_normals(angle=50)
    R = geo.rot('y', 1.5)          # both sides rest on their road wheels: no roll, a slight nose-down settle
    dz = _settle(m, R, sink=1.5)
    B = MG.pts_box
    upts = np.array([[x, y, z] for x, z in up for y in (-53, 53)], float)
    H = [MG.xform_pts(upts, R, (0, 0, dz)), MG.xform_pts(B(-96, -53, 0, 96, 53, 40), R, (0, 0, dz)),
         MG.xform_pts(np.array([[-96, -44, 2], [-96, 44, 2], [-96, -44, 17], [-96, 44, 17], [-148, -44, 0], [-148, 44, 0], [-148, -44, 5], [-148, 44, 5]], float), R, (0, 0, dz))]
    return m, H


# ---------------------------------------------------------------- pallet, parachute
def cargo_pallet(lod=0, seed=137):
    """air-dropped A-22 load: plywood skid on crushed honeycomb, ammo crates and ration cartons, webbing straps, a cargo net"""
    import p_jungle, p_base
    m = geo.Mesh()
    rng = np.random.RandomState(seed)
    p = geo.frame(seed=seed)
    m.add(geo.rbox(104, 84, 6, r=1.5, seg=1, mat='cardboard', part=p, center=(0, 0, 3)))
    m.add(geo.plank(108, 88, 2.4, mat='wood', seed=seed + 1, r=0.4, div=(2, 2, 1), t=(0, 0, 7.2)))
    tops = [(-54, -44, 54, 44, 8.4)]
    for i, (x, y, a) in enumerate(((-26, -24, 2), (-26, 6, -3), (-26, -9, 4))):
        z = 8.4 if i < 2 else 30.6
        m.add(p_jungle.crate(48, 28, 22, seed=seed + 5 + i).transform(geo.rot('z', a), (x, y, z)))
        tops.append((x - 24, y - 14, x + 24, y + 14, z + 22))
    m.add(p_jungle.crate(48, 28, 22, seed=seed + 9).transform(geo.rot('z', 91), (-28, 32, 8.4))); tops.append((-42, 20, -14, 44, 30.4))
    for ix in range(2):
        for iy in range(3):
            for iz in range(3 - (ix + iy) % 2):
                c = geo.rbox(25, 17, 12.4, r=0.7, seg=1, mat='cardboard', part=geo.frame(seed=seed + 20 + ix * 9 + iy * 3 + iz))
                x = 14 + ix * 26 + rng.uniform(-0.8, 0.8); y = -27 + iy * 18 + rng.uniform(-0.8, 0.8)
                c.transform(geo.rot('z', rng.uniform(-3, 3)), (x, y, 8.4 + 6.2 + iz * 12.5)); m.add(c)
                tops.append((x - 12.5, y - 8.5, x + 12.5, y + 8.5, 8.4 + (iz + 1) * 12.5))
    for k, (x, y, a) in enumerate(((16, 34, 20), (32, 35, -10))):
        m.add(p_base.jerry_can(lod, seed + 40 + k).transform(geo.rot('z', a), (x, y, 8.4))); tops.append((x - 7, y - 4, x + 7, y + 4, 27.5))
    net = MG.drape(-56, 56, -46, 46, tops, 'net', geo.frame(seed=seed + 50, img=0, tone=0.5), n=24, blur=1.1, lift=1.3, wrinkle=0.8, seed=seed, double=False, floor=8.4)
    for c in net.charts: c['atlas'] = 'cut'
    m.add(net)
    for x in (-30, 26):                                                # webbing straps over the load
        m.add(MG.box(x - 2.2, -45, 8.4, x + 2.2, -44, 52, 'webbing', p, r=0.2)); m.add(MG.box(x - 2.2, 44, 8.4, x + 2.2, 45, 46, 'webbing', p, r=0.2))
    m.add(geo.tube([(-4, -6, 55), (4, 2, 60), (10, -4, 56), (2, -10, 55), (-4, -6, 55)], 1.4, sides=6, mat='webbing', part=p))    # riser bundle on top
    ST = MG.text_img(['CTG 7.62MM', 'LINKED  LOT 4'], 256, 64, color=(0.08, 0.08, 0.07), fonts=MG.STENCIL, size=20)
    R2 = geo.rot('z', 2)
    m.add(geo.decal('st', R2 @ np.array([-16.0, -14.7, 4.0]) + np.array([-26, -24, 8.4]), R2 @ np.array([1.0, 0, 0]), (0, 0, 1), (32, 9), lift=0.12))
    return m, [MG.pts_box(-54, -44, 0, 54, 44, 8.4), MG.pts_box(-52, -40, 8.4, 44, 46, 46)], dict(st=ST)


def parachute_silk(lod=0, seed=138, R0=158.0):
    """a cargo canopy collapsed over the undergrowth: 24 gores in two colours draped over three lumps, shroud lines trailing to a
    riser bundle. No collision."""
    rng = np.random.RandomState(seed)
    nr, ns = 12, 72
    rr = np.linspace(0, 1, nr + 1); th = np.linspace(0, 2 * np.pi, ns + 1)
    T, Rg = np.meshgrid(th, rr, indexing='xy')                        # shape (nr+1, ns+1)
    hem = R0 * (0.82 + 0.20 * fbm(np.cos(th) * 1.3, np.sin(th) * 1.3, 0.3, 3, seed=seed)) * (1 + 0.035 * np.cos(24 * th))
    X = Rg * hem[None, :] * np.cos(T); Y = Rg * hem[None, :] * np.sin(T)
    Z = np.zeros_like(X)
    for cx, cy, h, sg in ((14, -8, 50, 40), (-58, 34, 28, 32), (62, 52, 20, 26), (-20, -70, 14, 30)):
        Z = np.maximum(Z, h * np.exp(-((X - cx) ** 2 + (Y - cy) ** 2) / (2 * sg * sg)))
    fold = (3.2 * np.abs(np.sin(12 * T)) + 2.2 * fbm(X * 0.05, Y * 0.05, 1.0, 3, seed=seed + 1)) * Rg
    Z = Z + fold + 1.0
    m = MG.sheet(np.stack([X, Y, Z], -1).transpose(1, 0, 2), 'silk', geo.frame(o=(0, 0, 0), seed=seed, gores=24.0))
    lp = geo.frame(seed=seed + 2)
    bundle = np.array([236.0, -52.0, 3.0])
    for k in range(0, ns, 6):
        a = th[k]
        if np.cos(a - np.arctan2(bundle[1], bundle[0])) < -0.1: continue
        h0 = np.array([hem[k] * np.cos(a), hem[k] * np.sin(a), 1.6])
        mid = (h0 + bundle) / 2 + np.array([rng.uniform(-14, 14), rng.uniform(-14, 14), 0.0]); mid[2] = 0.9
        m.add(geo.tube([h0, mid, bundle], 0.4, sides=3, mat='line', part=lp, caps=False))
    m.add(geo.rbox(22, 14, 8, r=3.0, seg=2, mat='webbing', part=lp, center=(244, -54, 4)))
    m.add(geo.tube([(232, -50, 4), (226, -40, 2), (236, -34, 1.5)], 1.2, sides=5, mat='webbing', part=lp))
    return m, []


# ---------------------------------------------------------------- specs
def _boat(ctx):
    """dark green fibreglass, chalky above the water line, slimed and stained below it"""
    out = S.painted_steel(ctx, S._c(0.17, 0.22, 0.15), chip=0.12, mud_top=0.0)
    P = ctx.P
    n = fbm(P[:, 0] * 0.04, P[:, 1] * 0.04, P[:, 2] * 0.04, 4, seed=461)
    under = smoothstep(46, 26, P[:, 2] + 9 * n)
    slime = S.mix(S._c(0.16, 0.20, 0.08), S._c(0.30, 0.27, 0.17), np.clip(n * 0.5 + 0.5, 0, 1))
    col = S.mix(out['color'], slime, under * 0.85)
    line = smoothstep(4, 0, np.abs(P[:, 2] + 9 * n - 44))
    col = S.mix(col, S._c(0.55, 0.52, 0.42), line * 0.5)
    out['color'] = np.clip(col, 0, 1); out['metal'] = out['metal'] * 0.0; out['rough'] = np.clip(out['rough'] - 0.25 * under, 0.2, 1)
    return out


def _sh():
    import p_jungle
    dark = lambda c: dict(color=np.full((c.n, 3), 0.035, np.float32), rough=np.full(c.n, 0.95, np.float32))
    return {'camo': M.sea_camo, 'interior': lambda c: M.sea_camo_int(c) if hasattr(M, 'sea_camo_int') else M.interior(c), 'floor': lambda c: S.rust_steel(c, paint=S._c(0.40, 0.42, 0.38), chip=0.4, rivets=True, mud_top=2.0),
            'alu': M.aluminium, 'seat': lambda c: S.canvas(c, base=S._c(0.55, 0.16, 0.12), mud_top=2.0, stains=0.8), 'cable': M.rubber, 'od': M.od_paint,
            'cyl': lambda c: S.rust_steel(c, paint=S._c(0.20, 0.20, 0.20), chip=0.5, mud_top=6.0), 'rust': M.rust, 'blade': lambda c: S.rust_steel(c, paint=S._c(0.07, 0.07, 0.07), chip=0.22, mud_top=10.0),
            'boat': _boat, 'deck': lambda c: S.rust_steel(c, paint=S._c(0.33, 0.35, 0.33), chip=0.3, mud_top=0.0), 'rubber': M.rubber, 'gunsteel': M.gun_steel,
            'burnt': M.burnt_steel, 'ash': M.ash, 'charwood': lambda c: S.wood(c, weather=1.0, mud_top=0.0) | {'color': np.clip(S.wood(c, weather=1.0, mud_top=0.0)['color'] * 0.28, 0, 1)},
            'gutted': lambda c: dict(color=np.clip(M.burnt_steel(c)['color'] * 0.35, 0, 1), rough=np.full(c.n, 0.95, np.float32)), 'track': S.track, 'void': dark,
            'cardboard': M.cardboard, 'wood': M.wood, 'rope': M.rope, 'webbing': M.webbing, 'net': lambda c: M.grass_card(c, p_jungle.cargo_net_img()),
            'silk': M.silk, 'line': lambda c: dict(color=np.full((c.n, 3), 0.72, np.float32), rough=np.full(c.n, 0.7, np.float32))}


def _spec(fn, size=2048, surface='metal', metal=True, cut=None, **kw):
    r = fn(lod=0, **kw)
    spec = dict(lods=[r[0]], single_lod=True, size=size, decal_size=512, ground=0.0, surface=surface, metal=metal, shaders=_sh(), stock={},
                decal_imgs=r[2] if len(r) > 2 else {}, hulls=r[1], normal_strength=0.9)
    if cut: spec['atlases'] = {'main': dict(size=size), 'cut': dict(size=cut, alpha=lambda b: b['metal'], metal=False, fill=0.9, backfaces=True)}
    return spec


def specs():
    return {
        'c123_fuselage': lambda: _spec(c123_fuselage, 2048),
        'c123_wing': lambda: _spec(c123_wing, 2048),
        'c123_engine': lambda: _spec(c123_engine, 1024),
        'pbr_wreck': lambda: _spec(pbr_wreck, 2048),
        'truck_wreck': lambda: _spec(truck_wreck, 2048),
        'm113_hulk': lambda: _spec(m113_hulk, 2048),
        'cargo_pallet': lambda: _spec(cargo_pallet, 1024, surface='wood', metal=False, cut=512),
        'parachute_silk': lambda: _spec(parachute_silk, 1024, surface='default', metal=False),
    }
