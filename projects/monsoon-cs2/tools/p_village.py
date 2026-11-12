"""Village and camp dressing: thatched hooches (3 sizes, one with a loft), the open-sided camp hut (T FDC), a small school, a
roadside shrine, a well, bamboo fences, rice baskets, water jars, a drying rack, haystacks, a pig pen, an ox cart, sampans, a fish
trap, a market stall, a propaganda board, punji stakes, a cook fire, a camouflage net. Origins on the ground, fronts to +x.
"""
import numpy as np
import geo
import mv_geo as MG
import mv_shaders as M
import shaders as S
import mv_tiles  # noqa: F401  (registers the generated tiling materials, e.g. mv_bamboo)
from noise import fbm


def bamboo_pole(p0, p1, r, seed, sides=8):
    return geo.tube([p0, ((np.asarray(p0) + np.asarray(p1)) / 2).tolist(), p1], r, sides=sides, mat='bamboo', part=geo.frame(seed=seed, tone=np.random.RandomState(int(abs(seed)) % (2 ** 31)).uniform(0.2, 0.9)))


FRINGE_S = 96.0      # units along the eave per tile of the CS2 thatch-edge texture (2048 x 512): a card is FRINGE_S / 4 deep


def fringe_card(p0, p1, down, depth, seed, nseg=None, face=None):
    """alpha-tested thatch-edge card hanging from the line p0-p1 along `down` (unit-ish), `depth` deep; uv laid for stock key
    v_thatch_edge (u along the edge at FRINGE_S units per tile, v 0 at the attached edge -> 1 at the straw tips); the tips sag"""
    p0 = np.asarray(p0, float); p1 = np.asarray(p1, float); dn = np.asarray(down, float); dn = dn / np.linalg.norm(dn)
    Lx = float(np.linalg.norm(p1 - p0))
    n = nseg or max(2, int(Lx / 24))
    t = np.linspace(0, 1, n + 1)
    P = np.zeros((n + 1, 3, 3))
    rng = np.random.RandomState(int(abs(seed)) % (2 ** 31))
    wob = fbm(t * Lx * 0.05, seed * 0.37, 0.0, 2, seed=int(abs(seed)) % 997)
    for j, f in enumerate((0.0, 0.5, 1.0)):
        P[:, j] = p0[None] + (p1 - p0)[None] * t[:, None] + dn[None] * depth * f * (1 + 0.12 * wob[:, None])
    m = geo.surface(P, 'thatch_fringe', geo.frame(seed=seed))
    if face is not None and (m.face_normals().sum(0) @ np.asarray(face, float)) < 0:   # front face toward the viewer side
        m.F = m.F[:, ::-1]; m.N = -m.N
    ou = rng.rand()
    m.T = np.stack([np.repeat(t * Lx / FRINGE_S + ou, 3), np.tile([0.0, 0.5, 0.995], n + 1)], 1)
    return m


def thatch_roof(L, W, ridge_z, eave_z, part, overhang=18, hip=False, lod=0, courses=4):
    """gabled thatch roof built the way it is laid: `courses` overlapping bundles of straw per slope, each tilted a little steeper
    than the roof so its butt end stands proud of the course below (a stepped silhouette), with a fringe of straw (alpha cards,
    CS2's de_ancient thatch edge) under every course line and the eaves, and a round ridge bundle. Surfaces use CS2's tiling thatch
    (stock key v_thatch, 1140 px/m) instead of the baked atlas (playtest 1, finding 16: 'flat brown plane')."""
    m = geo.Mesh()
    sd = part['seed']
    span = W / 2 + overhang
    rise = ridge_z - eave_z
    slope_len = float(np.hypot(span, rise))
    for s in (-1, 1):
        y0 = s * span
        down = np.array([0.0, s * span, -rise]) / slope_len            # down the slope, toward the eave
        u_ax = np.array([1.0, 0, 0])
        nrm = np.cross(u_ax, -down); nrm = nrm if nrm[2] > 0 else -nrm   # outward, up
        # courses from the ridge down: course c spans [c, c+1] / courses of the slope plus an overlap under the course above
        cl = (slope_len - 8.0) / courses                           # 8 u short: the proud butts and the fringe keep the old footprint
        for c in range(courses):
            top_d = max(0.0, c * cl - 10.0); bot_d = (c + 1) * cl
            lift = 3.0 + 2.5 * (c / max(courses - 1, 1))              # butt end stands proud of the course below
            top = np.array([0.0, 0.0, ridge_z]) + down * top_d + nrm * (0.5 * c)
            bot = np.array([0.0, 0.0, ridge_z]) + down * bot_d + nrm * (0.5 * c + lift)
            v = bot - top
            sub = 4 if c == courses - 1 else 3
            u = np.array([L + 2 * overhang, 0, 0])
            org = top - u / 2
            fr = geo.frame(R=np.stack([v / np.linalg.norm(v), u_ax, np.cross(v, u_ax) / np.linalg.norm(np.cross(v, u_ax))], 1), seed=sd + 17 * c + s)
            th = 5.0 + 1.5 * c
            slab = MG.plate(org, u, v, 'thatch', fr, thick=th)
            if np.dot(np.cross(u, v), nrm) < 0:      # plate extrudes along u x v: keep it on the outside
                slab = MG.plate(org + u, -u, v, 'thatch', fr, thick=th)
            sag = fbm(slab.V[:, 0] * 0.03, slab.V[:, 1] * 0.03 + c, 0.0, 3, seed=sd + 3 + c)
            slab.V[:, 2] += 1.6 * sag * (0.3 + 0.7 * c / max(courses - 1, 1))
            slab.recompute_normals()
            m.add(slab)
            # straw butts under the course line: two staggered cards hanging steeply from the course's lower edge
            e0 = bot - u / 2 + nrm * (th - 0.5); e1 = bot + u / 2 + nrm * (th - 0.5)
            # course lines: the straw lies along the slope over the butt of the course below; eave: cut ends hang steeper
            hang = (down * 0.25 + np.array([0, 0, -0.95])) if c == courses - 1 else (down * 0.95 - nrm * 0.12)
            depth = FRINGE_S / 4 * (0.8 if c == courses - 1 else 0.7)
            m.add(fringe_card(e0, e1, hang, depth, sd * 31 + c * 7 + s, face=nrm))
            if c == courses - 1:                                         # the eave gets a second, deeper layer for volume
                m.add(fringe_card(e0 - nrm * 3.0, e1 - nrm * 3.0, hang, depth * 1.1, sd * 37 + s, face=nrm))
        # rake (gable) edges: a short fringe down each verge
        for sx in (-1, 1):
            xg = sx * (L / 2 + overhang - 1)
            r0 = np.array([xg, 0.0, ridge_z + 4]); r1 = np.array([xg, y0, eave_z])
            m.add(fringe_card(r0, r1, (sx * 0.25, 0, -1.0), FRINGE_S / 4 * 0.5, sd * 41 + sx + 3 * s, nseg=6, face=(sx, 0, 0)))
    # ridge cap: a round bundle along the ridge, straw wrapped over it, with a fringe each side
    m.add(geo.tube([(-L / 2 - overhang, 0, ridge_z + 6), (0, 0, ridge_z + 8), (L / 2 + overhang, 0, ridge_z + 6)], 9.0, sides=12,
                   mat='thatch_ridge', part=geo.frame(R=geo.rot('z', 90), seed=sd + 9)))
    for s in (-1, 1):
        m.add(fringe_card((-L / 2 - overhang, s * 6, ridge_z + 9), (L / 2 + overhang, s * 6, ridge_z + 9),
                          (0, s * 0.8, -0.6), FRINGE_S / 4 * 0.7, sd * 43 + s, face=(0, s * 0.6, 0.8)))
    return m


def wattle_wall(x0, x1, y, z0, z1, part, seed, door=None, window=None):
    """woven bamboo matting wall between x0..x1 at y, from z0..z1; door/window: (x centre, width[, sill, height]) openings"""
    m = geo.Mesh()
    pan = MG.plate((x0, y, z0), (x1 - x0, 0, 0), (0, 0, z1 - z0), 'wattle', part, thick=1.6)
    cen_pred = []
    if door: cen_pred.append(lambda c, d=door: (np.abs(c[:, 0] - d[0]) < d[1] / 2) & (c[:, 2] < z0 + 70))
    if window: cen_pred.append(lambda c, w=window: (np.abs(c[:, 0] - w[0]) < w[1] / 2) & (c[:, 2] > w[2]) & (c[:, 2] < w[2] + w[3]))
    # the plate is a box; openings are made by splitting into strips: simpler = build strips
    m = geo.Mesh()
    strips = [(x0, x1)]
    cuts = []
    if door: cuts.append((door[0] - door[1] / 2, door[0] + door[1] / 2, z0, z0 + 70))
    if window: cuts.append((window[0] - window[1] / 2, window[0] + window[1] / 2, window[2], window[2] + window[3]))
    xs = sorted({x0, x1} | {c[0] for c in cuts} | {c[1] for c in cuts})
    for a, b in zip(xs[:-1], xs[1:]):
        cut = next((c for c in cuts if c[0] <= a and c[1] >= b), None)
        if cut is None:
            m.add(MG.plate((a, y, z0), (b - a, 0, 0), (0, 0, z1 - z0), 'wattle', part, thick=1.6))
        else:
            if cut[2] > z0: m.add(MG.plate((a, y, z0), (b - a, 0, 0), (0, 0, cut[2] - z0), 'wattle', part, thick=1.6))
            if cut[3] < z1: m.add(MG.plate((a, y, cut[3]), (b - a, 0, 0), (0, 0, z1 - cut[3]), 'wattle', part, thick=1.6))
    return m


def hooch(lod=0, seed=91, L=220, W=160, wall_h=84, loft=False, open_front=False):
    """thatched hut on a low bamboo frame: wattle walls, a door on +x, a window each side, raised floor of split bamboo"""
    rng = np.random.RandomState(seed)
    p = geo.frame(seed=seed, tone=0.5)
    m = geo.Mesh()
    floor_z = 10.0
    # floor platform and short stilts
    m.add(MG.box(-L / 2, -W / 2, floor_z - 4, L / 2, W / 2, floor_z, 'bamboo_floor', p))
    for xx in np.linspace(-L / 2 + 8, L / 2 - 8, 4):
        for yy in np.linspace(-W / 2 + 8, W / 2 - 8, 3):
            m.add(MG.cyl((xx, yy, -4), (xx, yy, floor_z - 4), 3.0, 'wood_dark', p, sides=6))
    # posts and beams
    posts = [(sx * (L / 2 - 4), sy * (W / 2 - 4)) for sx in (-1, 1) for sy in (-1, 1)] + [(0, sy * (W / 2 - 4)) for sy in (-1, 1)]
    for k, (xx, yy) in enumerate(posts):
        m.add(bamboo_pole((xx, yy, floor_z), (xx, yy, wall_h + floor_z + 2), 3.4, seed + k))
    for sy in (-1, 1):
        m.add(bamboo_pole((-L / 2 - 10, sy * (W / 2 - 4), wall_h + floor_z), (L / 2 + 10, sy * (W / 2 - 4), wall_h + floor_z), 3.0, seed + 20 + sy))
    ridge_z = wall_h + floor_z + W * 0.42
    m.add(bamboo_pole((-L / 2 - 14, 0, ridge_z - 4), (L / 2 + 14, 0, ridge_z - 4), 3.2, seed + 30))
    for sx in (-1, 1):   # king posts under the ridge
        m.add(bamboo_pole((sx * (L / 2 - 4), 0, wall_h + floor_z), (sx * (L / 2 - 4), 0, ridge_z - 6), 3.0, seed + 40 + sx))
    # walls
    if not open_front:
        m.add(wattle_wall(-L / 2 + 2, L / 2 - 2, -W / 2 + 2, floor_z, wall_h + floor_z, p, seed, window=(-L / 4, 40, floor_z + 40, 30)))
        m.add(wattle_wall(-L / 2 + 2, L / 2 - 2, W / 2 - 2, floor_z, wall_h + floor_z, p, seed, window=(L / 4, 40, floor_z + 40, 30)))
        back = wattle_wall(-W / 2 + 2, W / 2 - 2, 0, floor_z, wall_h + floor_z, p, seed); back.transform(geo.rot('z', 90), (-L / 2 + 2, 0, 0)); m.add(back)
        front = wattle_wall(-W / 2 + 2, W / 2 - 2, 0, floor_z, wall_h + floor_z, p, seed, door=(0, 44)); front.transform(geo.rot('z', 90), (L / 2 - 2, 0, 0)); m.add(front)
        # gable infill (wattle triangles)
        for sx in (-1, 1):
            tri = geo.prism([(-W / 2 + 2, wall_h + floor_z), (W / 2 - 2, wall_h + floor_z), (0, ridge_z - 2)], -0.8, 0.8, 'wattle', p)
            tri.transform(geo.rot('z', 90), (sx * (L / 2 - 3), 0, 0)); m.add(tri)
    # roof
    m.add(thatch_roof(L, W, ridge_z, wall_h + floor_z - 6, dict(seed=seed), overhang=22, lod=lod))
    # inside: sleeping mat, a low table, a lamp; the loft (second floor on the back half) if asked
    ip = geo.frame(seed=seed + 50)
    m.add(MG.box(-L / 2 + 20, -W / 2 + 14, floor_z, -L / 2 + 90, -W / 2 + 60, floor_z + 2.5, 'mat', ip))
    m.add(MG.box(-20, 10, floor_z, 30, 50, floor_z + 20, 'wood_dark', ip))
    for (xx, yy) in ((-18, 12), (28, 12), (-18, 48), (28, 48)):
        m.add(MG.cyl((xx, yy, floor_z), (xx, yy, floor_z + 20), 1.2, 'wood_dark', ip, sides=5))
    if loft:
        m.add(MG.box(-L / 2 + 4, -W / 2 + 4, floor_z + wall_h - 2, -10, W / 2 - 4, floor_z + wall_h + 2, 'bamboo_floor', ip))
        for z in np.arange(floor_z + 14, floor_z + wall_h, 14):   # ladder
            m.add(MG.cyl((-6, -14, z), (-6, 14, z), 1.2, 'bamboo', ip, sides=5))
        for s in (-1, 1): m.add(MG.cyl((-2, s * 14, floor_z), (-10, s * 14, floor_z + wall_h), 1.6, 'bamboo', ip, sides=6))
    m.recompute_normals(angle=50)
    return m


def camp_hut(lod=0, seed=92):
    """open-sided thatched shelter (the T FDC / briefing hut): six posts, thatch roof, a low bamboo wall on three sides, earth floor"""
    p = geo.frame(seed=seed, tone=0.4)
    m = geo.Mesh()
    L, W, H = 260, 180, 92
    for xx in (-L / 2 + 6, 0, L / 2 - 6):
        for sy in (-1, 1):
            m.add(bamboo_pole((xx, sy * (W / 2 - 6), 0), (xx, sy * (W / 2 - 6), H), 3.8, seed + int(xx) + sy))
    for sy in (-1, 1): m.add(bamboo_pole((-L / 2 - 12, sy * (W / 2 - 6), H - 2), (L / 2 + 12, sy * (W / 2 - 6), H - 2), 3.2, seed + 20 + sy))
    ridge_z = H + W * 0.38
    m.add(bamboo_pole((-L / 2 - 16, 0, ridge_z - 4), (L / 2 + 16, 0, ridge_z - 4), 3.2, seed + 30))
    for sx in (-1, 1): m.add(bamboo_pole((sx * (L / 2 - 6), 0, H - 4), (sx * (L / 2 - 6), 0, ridge_z - 6), 3.0, seed + 40 + sx))
    m.add(thatch_roof(L, W, ridge_z, H - 8, dict(seed=seed), overhang=26, lod=lod))
    for sy in (-1, 1):   # half-height wattle on the long sides and the back
        m.add(wattle_wall(-L / 2 + 8, L / 2 - 8, sy * (W / 2 - 6), 0, 44, p, seed + sy))
    back = wattle_wall(-W / 2 + 8, W / 2 - 8, 0, 0, 44, p, seed + 5); back.transform(geo.rot('z', 90), (-L / 2 + 6, 0, 0)); m.add(back)
    # a bench along the back, a hanging lamp
    m.add(MG.box(-L / 2 + 14, -60, 0, -L / 2 + 34, 60, 18, 'wood_dark', p))
    m.add(MG.cyl((20, 0, ridge_z - 8), (20, 0, ridge_z - 40), 0.5, 'rope', p, sides=4))
    m.add(MG.lathe_x([(0, 0), (5, 0), (6, 6), (4, 12), (2, 16), (0, 16)], 'gunsteel', sides=10, part=p).transform(geo.rot('y', -90), (20, 0, ridge_z - 56)))
    m.recompute_normals(angle=50)
    return m


def school(lod=0, seed=93):
    """small plastered-brick village school with a tin roof, a bell on a post, shuttered windows; door on +x; bomb-damaged corner"""
    p = geo.frame(seed=seed, tone=0.5)
    m = geo.Mesh()
    L, W, H = 300, 200, 110
    walls = MG.box(-L / 2, -W / 2, 0, L / 2, W / 2, H, 'plaster', p, r=1.0)
    # openings: door (+x) and four windows cut by removing faces and adding reveals
    MG.remove_faces(walls, lambda c: ((c[:, 0] > L / 2 - 1) & (np.abs(c[:, 1]) < 26) & (c[:, 2] < 84)) |
                    ((np.abs(c[:, 1]) > W / 2 - 1) & (np.abs(np.abs(c[:, 0]) - 80) < 24) & (c[:, 2] > 44) & (c[:, 2] < 90)))
    m.add(walls)
    # interior box (dark) so openings don't show the void
    m.add(MG.box(-L / 2 + 6, -W / 2 + 6, 0, L / 2 - 6, W / 2 - 6, H - 6, 'interior_dark', p, r=0.5))
    for sy in (-1, 1):
        for sx in (-1, 1):
            xx = sx * 80
            m.add(MG.box(xx - 26, sy * (W / 2 - 3), 42, xx + 26, sy * (W / 2 + 2), 46, 'plaster', p))              # sills
            m.add(MG.plate((xx - 24, sy * (W / 2 + 2.2), 46), (22, 0, 0), (0, 0, 42), 'shutter', p, thick=1.2))    # shutters (one closed, one open)
            m.add(MG.plate((xx + 2, sy * (W / 2 + 2.2), 46), (22, 0, 0) if sx < 0 else (0, sy * 22, 0), (0, 0, 42), 'shutter', p, thick=1.2))
    m.add(MG.plate((L / 2 + 1, -26, 0), (0, 52, 0), (0, 0, 84), 'interior_dark', p, thick=0.3))
    m.add(MG.plate((L / 2 + 1.6, 24, 0), (0, 0, 0) if False else (26, 20, 0), (0, 0, 82), 'shutter', p, thick=1.4))   # door swung open
    # tin roof: corrugated sheets with overhang, on purlins; a chunk missing at the -x -y corner (bomb damage)
    ridge_z = H + 46
    for s in (-1, 1):
        u = np.array([L + 50, 0, 0]); v = np.array([0, -s * (W / 2 + 25), ridge_z - H + 4])
        sheet = MG.plate((-L / 2 - 25, s * (W / 2 + 25), H - 4), u, v, 'tin', p, thick=1.2)
        if s < 0: MG.remove_faces(sheet, lambda c: (c[:, 0] < -L / 2 + 60) & (c[:, 1] < -W / 2 + 40))
        m.add(sheet)
        for xx in np.arange(-L / 2 - 20, L / 2 + 20, 48):
            m.add(MG.cyl((xx, s * (W / 2 + 20), H - 6), (xx, s * 3, ridge_z - 4), 2.2, 'wood_dark', p, sides=5))      # rafters under the sheets
    m.add(MG.cyl((-L / 2 - 26, 0, ridge_z + 4), (L / 2 + 26, 0, ridge_z + 4), 4.0, 'tin', p, sides=6))
    # rubble at the damaged corner, bell post, chalkboard inside, a few desks
    rp = geo.frame(seed=seed + 7)
    for k in range(14):
        rng = np.random.RandomState(seed + k)
        b = geo.rbox(rng.uniform(8, 20), rng.uniform(6, 14), rng.uniform(4, 10), r=1.0, mat='plaster', part=rp, center=(-L / 2 - 20 + rng.uniform(-10, 60), -W / 2 - 20 + rng.uniform(-10, 60), rng.uniform(2, 10)))
        b.transform(geo.euler(rng.uniform(0, 360), rng.uniform(-20, 20), rng.uniform(-20, 20)), (0, 0, 0)); m.add(b)
    m.add(MG.cyl((L / 2 + 60, -70, 0), (L / 2 + 60, -70, 120), 3.0, 'wood_dark', p, sides=8))
    m.add(MG.cyl((L / 2 + 60, -70, 120), (L / 2 + 60, -56, 118), 2.0, 'wood_dark', p, sides=6))
    m.add(MG.lathe_x([(0, 0), (6, 0), (8, 8), (6, 14), (2, 16), (0, 16)], 'brass', sides=12, part=p).transform(geo.rot('y', -90) @ geo.rot('y', 180) @ geo.rot('y', 180), (L / 2 + 60, -56, 100)))
    for k in range(3):
        m.add(MG.box(-60 + k * 60, -40, 0, -30 + k * 60, 0, 28, 'wood', rp))
        m.add(MG.box(-60 + k * 60, -40, 28, -30 + k * 60, 0, 31, 'wood', rp))
    m.add(MG.plate((-L / 2 + 7, -50, 40), (0, 100, 0), (0, 0, 60), 'blackboard', rp, thick=1.0))
    BOARD = MG.text_img(['TRUONG TIEU HOC', 'BINH AN'], 512, 128, color=(0.1, 0.1, 0.1), fonts=MG.SANS)
    m.add(geo.decal('board', (L / 2 - 80, -W / 2 - 1.3, 92), (1, 0, 0), (0, 0, 1), (64, 16)))
    m.recompute_normals(angle=50)
    return m, dict(board=BOARD)


def shrine(lod=0, seed=94):
    """roadside spirit house: a small pagoda-roofed box on a pedestal, incense pot, offerings"""
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    m.add(MG.box(-16, -16, 0, 16, 16, 44, 'plaster', p, r=1.0))
    m.add(MG.box(-24, -20, 44, 24, 20, 48, 'plaster', p, r=0.6))
    m.add(MG.box(-18, -14, 48, 18, 14, 84, 'paint_red', p, r=0.8))
    MG.remove_faces(m, lambda c: (c[:, 0] > 17.5) & (np.abs(c[:, 1]) < 10) & (c[:, 2] > 52) & (c[:, 2] < 80))
    m.add(MG.box(-17, -13, 49, 17, 13, 83, 'interior_dark', p))
    # tiled roof with upturned corners
    roof = geo.prism([(-30, 84), (30, 84), (0, 104)], -24, 24, 'tile', p)
    m.add(roof)
    for sx in (-1, 1):
        for sy in (-1, 1):
            m.add(MG.cyl((sx * 28, sy * 22, 85), (sx * 34, sy * 28, 96), 1.6, 'tile', p, sides=6))
    m.add(MG.lathe_x([(0, 0), (5, 0), (6, 3), (6, 10), (4, 11), (0, 11)], 'brass', sides=10, part=p).transform(geo.rot('y', -90), (6, 0, 48)))
    for k in range(5): m.add(MG.cyl((6 + k * 0.6, -1.5 + k * 0.7, 59), (7 + k * 0.4, -1 + k * 0.6, 74), 0.25, 'wood_dark', p, sides=4))
    m.recompute_normals(angle=50)
    return m


def well(lod=0, seed=95):
    """stone well ring with a timber frame, roller and bucket on a rope"""
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    m.add(geo.lathe([(0, 0), (38, 0), (38, 36), (30, 36), (30, 2), (0, 2)], sides=20, mat='stone', part=p))
    m.add(geo.disk((0, 0, 1.5), [(29 * np.cos(a), 29 * np.sin(a), 1.5) for a in np.linspace(0, 2 * np.pi, 20, endpoint=False)], (0, 0, 1), 'water_dark', p))
    for s in (-1, 1): m.add(MG.cyl((0, s * 36, 0), (0, s * 36, 96), 3.2, 'wood_dark', p, sides=8))
    m.add(MG.cyl((0, -40, 92), (0, 40, 92), 2.2, 'wood_dark', p, sides=8))
    m.add(MG.cyl((0, -10, 92), (0, 10, 92), 4.5, 'wood', p, sides=10))
    m.add(MG.cyl((0, 12, 92), (0, 22, 86), 1.4, 'gunsteel', p, sides=6))
    m.add(MG.cyl((0, 0, 92), (0, 0, 50), 0.5, 'rope', p, sides=4))
    m.add(geo.lathe([(0, 0), (6, 0), (7, 12), (0, 12)], sides=12, mat='wood', part=p).transform(None, (0, 0, 38)))
    m.recompute_normals(angle=50)
    return m


def bamboo_fence(lod=0, seed=96, length=128):
    """woven / tied bamboo fence section along x, 60 tall"""
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    rng = np.random.RandomState(seed)
    for xx in np.arange(-length / 2, length / 2 + 1, 32):
        m.add(bamboo_pole((xx, 0, -4), (xx + rng.uniform(-2, 2), 0, 62 + rng.uniform(-4, 4)), 2.2, seed + int(xx)))
    for z in (18, 48):
        m.add(bamboo_pole((-length / 2 - 2, 2.4, z), (length / 2 + 2, 2.4, z + rng.uniform(-1, 1)), 1.6, seed + 100 + int(z)))
    for xx in np.arange(-length / 2 + 4, length / 2, 6.5):
        m.add(bamboo_pole((xx + rng.uniform(-0.6, 0.6), 4.2, 0), (xx + rng.uniform(-1, 1), 4.2, 44 + rng.uniform(-6, 8)), 1.0, seed + 200 + int(xx * 10), sides=5))
    m.recompute_normals(angle=50)
    return m


# CS2's de_dust grain basket texture (1024 px atlas, materials/models/props/de_dust/hr_dust/dust_grain_basket): the side weave
# strip (rim band at the top) and the woven spiral of the base, in image uv (v from the top)
BASKET_SIDE = (588 / 1024, 1016 / 1024, 244 / 1024, 1018 / 1024)     # u0, u1, v_rim, v_bottom (inside the strip's border)
BASKET_BASE = (770 / 1024, 112 / 1024, 180 / 1024)                  # centre u, v, radius


def woven_lathe(profile, segs=6, per=4, mat='basket', part=None, seed=0):
    """a lathe in `segs` separate segments, each mapping the full width of the basket side strip once (the weave repeats round
    the basket at about its own scale instead of one stretched copy); v follows the profile, rim at the top of the strip"""
    pr = np.asarray(profile, float)
    plen = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pr, axis=0), axis=1))]); plen /= plen[-1]
    u0, u1, vr, vb = BASKET_SIDE
    m = geo.Mesh()
    ph = np.random.RandomState(seed).uniform(0, 2 * np.pi)
    for k in range(segs):
        th = ph + np.linspace(k, k + 1, per + 1) * 2 * np.pi / segs
        P = np.zeros((per + 1, len(pr), 3))
        P[..., 0] = np.cos(th)[:, None] * pr[None, :, 0]; P[..., 1] = np.sin(th)[:, None] * pr[None, :, 0]; P[..., 2] = pr[None, :, 1]
        s = geo.surface(P, mat, part or geo.frame(seed=seed))
        fn = s.face_normals(); cen = s.V[s.F].mean(1); radial = cen.copy(); radial[:, 2] = 0
        if np.einsum('ij,ij->i', fn, radial).mean() < 0: s.F = s.F[:, ::-1]
        uu, vv = np.meshgrid(np.linspace(u0, u1, per + 1), vb + (vr - vb) * plen, indexing='ij')
        s.T = np.stack([uu.ravel(), vv.ravel()], 1)
        m.add(s)
    return m


def rice_basket(lod=0, seed=97):
    """round woven rice basket (thung) with a rolled rim, heaped with paddy: CS2's photo-sourced basket weave (de_dust grain
    basket texture) instead of the procedural wicker (playtest 1, finding 17)"""
    p = geo.frame(seed=seed)
    rng = np.random.RandomState(seed)
    prof = [(13, 0.5), (16, 3), (18.5, 10), (20, 20), (20.3, 27), (21.2, 29.5), (20.6, 31.2), (19.2, 31)]
    m = woven_lathe(prof, segs=6, per=4, part=p, seed=seed)
    m.recompute_normals(angle=60)
    # woven base (the spiral of the texture)
    cu, cv, cr = BASKET_BASE
    ring = [(13 * np.cos(a), 13 * np.sin(a), 0.5) for a in np.linspace(0, 2 * np.pi, 16, endpoint=False)]
    base = geo.disk((0, 0, 0.0), ring, (0, 0, -1), 'basket', p)
    base.T = np.stack([cu + base.V[:, 0] / 13 * cr, cv + base.V[:, 1] / 13 * cr], 1)
    m.add(base)
    # paddy heaped a little above the rim, uneven
    h = 2.0 + rng.uniform(0, 3)
    dome = geo.lathe([(19.4, 29.5), (17, 30.5 + h * 0.5), (11, 31 + h * 0.85), (4, 31 + h), (0, 31 + h)], sides=18, mat='rice', part=geo.frame(seed=seed + 1))
    dome.V[:, 2] += 0.6 * fbm(dome.V[:, 0] * 0.3, dome.V[:, 1] * 0.3, 0.0, 2, seed=seed)
    dome.recompute_normals(angle=70)
    m.add(dome)
    return m


def water_jar(lod=0, seed=98):
    p = geo.frame(seed=seed)
    m = geo.lathe([(0, 0), (12, 0), (20, 10), (23, 26), (19, 40), (14, 46), (15, 50), (0, 50)], sides=16, mat='clay', part=p)
    m.add(geo.disk((0, 0, 47), [(13 * np.cos(a), 13 * np.sin(a), 47) for a in np.linspace(0, 2 * np.pi, 14, endpoint=False)], (0, 0, 1), 'water_dark', p))
    return m


def drying_rack(lod=0, seed=99):
    """bamboo rack with fish / clothes drying"""
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    for xx in (-50, 50):
        m.add(bamboo_pole((xx, -2, 0), (xx, -2, 70), 2.0, seed + xx))
        m.add(bamboo_pole((xx, -22, 0), (xx, 4, 70), 1.4, seed + 7 + xx, sides=6))
    m.add(bamboo_pole((-56, -2, 68), (56, -2, 68), 1.6, seed + 20))
    rng = np.random.RandomState(seed)
    for k in range(6):
        xx = -40 + k * 16
        m.add(MG.plate((xx, -1, 40 + rng.uniform(-4, 4)), (10, 0, 0), (0, 0, 26), 'cloth', p, thick=0.4))
    m.recompute_normals(angle=50)
    return m


def straw_card(c, w, h, yaw, tilt, seed, z0=0.0):
    """one loose-straw card (CS2's de_anubis hay pile strands, alpha-tested): w wide, h tall, standing at c, leaning `tilt` deg
    outward from vertical toward yaw"""
    rng = np.random.RandomState(int(abs(seed)) % (2 ** 31))
    P = np.zeros((3, 3, 3))
    a = np.radians(yaw); out = np.array([np.cos(a), np.sin(a), 0.0]); side = np.array([-np.sin(a), np.cos(a), 0.0])
    up = np.array([0, 0, 1.0]) * np.cos(np.radians(tilt)) + out * np.sin(np.radians(tilt))
    for i, s in enumerate((-0.5, 0.0, 0.5)):
        for j, t in enumerate((0.0, 0.5, 1.0)):
            P[i, j] = np.asarray(c, float) + side * s * w + up * t * h + out * (0.15 * h * t * t) + np.array([0, 0, z0])
    m = geo.surface(P, 'straw', geo.frame(seed=seed))
    if m.face_normals().sum(0) @ out < 0: m.F = m.F[:, ::-1]; m.N = -m.N
    u0 = rng.uniform(0, 0.5); v0 = rng.uniform(0, 0.3)
    uu, vv = np.meshgrid([u0, u0 + 0.25, u0 + 0.5], [v0 + 0.7, v0 + 0.35, v0], indexing='ij')
    m.T = np.stack([uu.ravel(), vv.ravel()], 1)
    return m


def haystack(lod=0, seed=100):
    """Vietnamese rice-straw stack (cay rom): straw built up round a bamboo pole into a shaggy dome, laid in courses with the
    straw running down so the rain sheds, a straw top-knot round the pole, loose straw at the foot. Surfaces: CS2's thatch
    (straw running down the profile) and thatch-edge fringes per course, de_anubis hay-pile strands at the foot (playtest 1,
    finding 17: the old one was a smooth noise-shaded lathe). Same footprint as before (r 48-52, about 100 tall)."""
    p = geo.frame(seed=seed)
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    prof = [(0, 0), (43, 0), (47, 10), (48, 26), (46, 42), (41, 58), (33, 72), (22, 84), (11, 92), (4, 96), (0, 97)]
    body = geo.lathe(prof, sides=22, mat='straw_body', part=p)
    lump = fbm(body.V[:, 0] * 0.05, body.V[:, 1] * 0.05, body.V[:, 2] * 0.05, 3, seed=seed)
    lean = np.clip(body.V[:, 2] / 97.0, 0, 1) ** 2 * rng.uniform(2, 5)          # a slight lean, the top settles to one side
    body.V += body.N * (lump * 3.0)[:, None]
    body.V[:, 0] += lean
    body.recompute_normals(angle=70)
    m.add(body)

    def rz(z):            # radius of the profile at height z
        zs = [q[1] for q in prof]; rs = [q[0] for q in prof]
        return float(np.interp(z, zs[1:], rs[1:]))
    # a straw fringe under each course line, hanging down over the course below
    for k, z in enumerate((30.0, 50.0, 68.0, 82.0)):
        r = rz(z) + 1.0; n = 9
        a0 = rng.uniform(0, 2 * np.pi)
        for i in range(n):
            a1, a2 = a0 + i * 2 * np.pi / n, a0 + (i + 1.08) * 2 * np.pi / n
            q1 = (r * np.cos(a1), r * np.sin(a1), z); q2 = (r * np.cos(a2), r * np.sin(a2), z)
            mid = 0.5 * (a1 + a2)
            dn = (0.15 * np.cos(mid), 0.15 * np.sin(mid), -1.0)
            m.add(fringe_card(q1, q2, dn, FRINGE_S / 4 * (0.75 - 0.08 * k), seed * 13 + k * 31 + i, nseg=2, face=(np.cos(mid), np.sin(mid), 0)))
    # pole and top-knot
    m.add(bamboo_pole((0, 0, -4), (rng.uniform(-1, 1), rng.uniform(-1, 1), 104), 2.0, seed + 5))
    knot = geo.lathe([(0, 90), (9, 90), (8, 94), (5, 98), (2.5, 100.5), (0, 101)], sides=12, mat='straw_body', part=geo.frame(seed=seed + 6))
    m.add(knot)
    for i in range(6):
        a1, a2 = i * np.pi / 3, (i + 1.1) * np.pi / 3
        m.add(fringe_card((8 * np.cos(a1), 8 * np.sin(a1), 97), (8 * np.cos(a2), 8 * np.sin(a2), 97), (0.5 * np.cos(a1 + 0.5), 0.5 * np.sin(a1 + 0.5), -1), 12.0, seed * 17 + i, nseg=1, face=(np.cos(a1 + 0.5), np.sin(a1 + 0.5), 0)))
    # loose straw at the foot
    for i in range(14):
        a = rng.uniform(0, 360)
        c = (37 * np.cos(np.radians(a)), 37 * np.sin(np.radians(a)), 0.0)
        m.add(straw_card(c, rng.uniform(16, 24), rng.uniform(9, 12), a, rng.uniform(25, 45), seed * 19 + i))
    m.recompute_normals(angle=60)
    return m


def pig_pen(lod=0, seed=101):
    """low split-bamboo pen with a thatch lean-to and a trough"""
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    for k, (x0, y0, x1, y1) in enumerate(((-70, -50, 70, -50), (70, -50, 70, 50), (70, 50, -70, 50), (-70, 50, -70, -50))):
        f = bamboo_fence(lod, seed + k, length=float(np.hypot(x1 - x0, y1 - y0)))
        f.V[:, 2] *= 0.6
        ang = np.degrees(np.arctan2(y1 - y0, x1 - x0))
        f.transform(geo.rot('z', ang), ((x0 + x1) / 2, (y0 + y1) / 2, 0)); m.add(f)
    for xx in (-60, -10):
        m.add(bamboo_pole((xx, -40, 0), (xx, -40, 60), 2.4, seed + 30 + xx))
        m.add(bamboo_pole((xx, 40, 0), (xx, 40, 40), 2.4, seed + 40 + xx))
    m.add(MG.plate((-66, -46, 58), (60, 0, 0), (0, 92, -18), 'thatch', geo.frame(R=geo.rot('z', 90), seed=seed + 50), thick=6.0))
    m.add(MG.box(20, -10, 0, 60, 10, 12, 'wood_dark', p))
    m.add(MG.box(22, -8, 10, 58, 8, 12.5, 'mud', p))
    m.recompute_normals(angle=50)
    return m


def ox_cart(lod=0, seed=102):
    """two-wheeled wooden cart with a load of straw, shafts to +x"""
    p = geo.frame(seed=seed, tone=0.6)
    m = geo.Mesh()
    m.add(MG.box(-60, -30, 36, 50, 30, 40, 'wood', p))
    for s in (-1, 1):
        m.add(MG.box(-60, s * 28, 40, 50, s * 31, 62, 'wood', p))
        m.add(MG.cyl((50, s * 18, 38), (130, s * 14, 46), 2.2, 'wood', p, sides=8))
        # spoked wheel
        m.add(geo.tube([(0, s * 34, 36), (0, s * 38, 36)], 36, sides=18, mat='wood_dark', part=p))
        for k in range(10):
            a = k * np.pi / 5
            m.add(MG.cyl((0, s * 36, 36), (33 * np.cos(a), s * 36, 36 + 33 * np.sin(a)), 1.2, 'wood', p, sides=5))
        m.add(MG.cyl((0, s * 33, 36), (0, s * 40, 36), 5.0, 'wood_dark', p, sides=10))
    m.add(MG.cyl((0, -34, 36), (0, 34, 36), 2.6, 'wood_dark', p, sides=8))
    hay = geo.rbox(100, 50, 30, r=10, seg=2, mat='straw_body', part=p, div=(3, 2, 1), center=(-5, 0, 76))
    hay.V += hay.N * fbm(hay.V[:, 0] * 0.1, hay.V[:, 1] * 0.1, hay.V[:, 2] * 0.1, 2, seed=seed)[:, None] * 3
    hay.recompute_normals(angle=60); m.add(hay)
    m.recompute_normals(angle=50)
    return m


def sampan(lod=0, seed=103, roof=True):
    """flat-bottomed wooden sampan, 240 long, with a woven arched shelter amidships; bow +x; sits in water: waterline at z 8"""
    p = geo.frame(seed=seed, tone=0.7)
    m = geo.Mesh()
    xs = np.linspace(-120, 120, 9)
    secs = []
    for x in xs:
        t = x / 120
        w = 30 * (1 - 0.55 * t ** 4) * (1 - 0.25 * max(0, -t) ** 2)
        zb = 2 + 10 * t ** 4; zt = 26 + 8 * t ** 2
        loop = MG.rrect_section(w, zb, zt, 2.6, n=12, flat_bottom=0.7)
        secs.append((x, loop))
    hull = MG.loft(secs, 'wood', p, n=12)
    MG.remove_faces(hull, lambda c: (c[:, 2] > 22) & (np.abs(c[:, 0]) < 112))   # open top
    m.add(hull)
    m.add(MG.box(-84, -17, 6, 84, 17, 8, 'wood_dark', p))                         # bottom boards (inside the hull, not past it)
    for xx in (-70, -20, 30, 76): m.add(MG.box(xx, -25, 8, xx + 3, 25, 20, 'wood', p))   # ribs
    if roof:
        th = np.linspace(0, np.pi, 10)
        P = np.zeros((2, len(th), 3))
        for i, x in enumerate((-60, 40)):
            P[i, :, 0] = x; P[i, :, 1] = 30 * np.cos(th); P[i, :, 2] = 22 + 34 * np.sin(th)
        m.add(geo.surface(P, 'wicker', p))
    m.add(MG.cyl((-124, 0, 24), (-150, 0, 56), 1.6, 'wood', p, sides=6))            # steering oar
    m.add(MG.plate((-150, -3, 56), (-30, 0, 0), (0, 6, 0), 'wood', p, thick=1.0))
    m.recompute_normals(angle=50)
    return m


def fish_trap(lod=0, seed=104):
    p = geo.frame(seed=seed)
    m = geo.lathe([(0, 0), (8, 0), (12, 20), (6, 40), (3, 48), (0, 48)], sides=12, mat='wicker', part=p)
    m.transform(geo.rot('y', 70), (0, 0, 8))
    return m


def market_stall(lod=0, seed=105):
    """bamboo table under a tarp awning with baskets of produce"""
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    for (xx, yy, h) in ((-50, -40, 100), (-50, 40, 100), (50, -40, 80), (50, 40, 80)):
        m.add(bamboo_pole((xx, yy, 0), (xx, yy, h), 2.6, seed + xx + yy))
    m.add(MG.plate((-56, -46, 100), (112, 0, -20), (0, 92, 0), 'tarp_blue', p, thick=0.8))
    m.add(MG.box(-44, -36, 36, 44, 36, 40, 'bamboo_floor', p))
    for s in (-1, 1): m.add(bamboo_pole((-44, s * 30, 0), (44, s * 30, 0), 1.8, seed + 10 + s).transform(None, (0, 0, 20)))
    rng = np.random.RandomState(seed)
    for k in range(4):
        b = rice_basket(lod, seed + 20 + k); b.transform(None, (-30 + k * 20, rng.uniform(-14, 14), 40)); b.V[:, 2] = 40 + (b.V[:, 2] - 40) * 0.6; m.add(b)
    m.recompute_normals(angle=50)
    return m


def propaganda_board(lod=0, seed=106):
    p = geo.frame(seed=seed, tone=0.5)
    m = geo.Mesh()
    for s in (-1, 1): m.add(bamboo_pole((0, s * 60, 0), (0, s * 60, 110), 3.0, seed + s))
    m.add(MG.box(-1.5, -64, 56, 1.5, 64, 106, 'paint_red', p, r=0.4))
    img = MG.text_img(['QUYET TAM DANH THANG', 'GIAC MY XAM LUOC'], 1024, 400, color=(0.95, 0.9, 0.3), fonts=MG.SANS)
    m.add(geo.decal('txt', (1.7, -62, 58), (0, 1, 0), (0, 0, 1), (124, 46)))
    m.recompute_normals(angle=50)
    return m, dict(txt=img)


def punji_stakes(lod=0, seed=107):
    """a patch of sharpened bamboo stakes in a shallow pit"""
    p = geo.frame(seed=seed)
    m = geo.Mesh(); rng = np.random.RandomState(seed)
    for k in range(14):
        x, y = rng.uniform(-30, 30), rng.uniform(-30, 30)
        m.add(MG.cyl((x, y, -8), (x + rng.uniform(-4, 4), y + rng.uniform(-4, 4), rng.uniform(16, 26)), 1.1, 'bamboo', p, sides=5, r1=0.1))
    m.add(geo.disk((0, 0, -7.5), [(40 * np.cos(a), 40 * np.sin(a), -7.5) for a in np.linspace(0, 2 * np.pi, 16, endpoint=False)], (0, 0, 1), 'mud', p))
    m.recompute_normals(angle=50)
    return m


def cook_fire(lod=0, seed=108):
    """stones in a ring, charred logs, a pot on an iron tripod (the fire particle sits on top in the map)"""
    p = geo.frame(seed=seed)
    m = geo.Mesh(); rng = np.random.RandomState(seed)
    for k in range(9):
        a = k * 2 * np.pi / 9
        s = geo.rbox(rng.uniform(8, 12), rng.uniform(7, 10), rng.uniform(5, 8), r=2.5, seg=1, mat='stone', part=p, center=(22 * np.cos(a), 22 * np.sin(a), 3))
        s.transform(geo.euler(rng.uniform(0, 360), 0, 0)); m.add(s)
    for k in range(3):
        a = k * 2.1
        m.add(geo.tube([(14 * np.cos(a), 14 * np.sin(a), 3), (-10 * np.cos(a), -10 * np.sin(a), 6)], 3.0, sides=7, mat='charred', part=p))
    for k in range(3):
        a = k * 2 * np.pi / 3
        m.add(MG.cyl((26 * np.cos(a), 26 * np.sin(a), 0), (0, 0, 54), 0.9, 'gunsteel', p, sides=5))
    m.add(geo.lathe([(0, 0), (9, 0), (11, 8), (10, 14), (8, 15), (0, 15)], sides=12, mat='gunsteel', part=p).transform(None, (0, 0, 32)))
    m.recompute_normals(angle=50)
    return m


def camo_net(lod=0, seed=109, W=560, D=420, H=150):
    """camouflage net on poles over a parking spot: an alpha-tested lattice sheet (cut-out atlas) with garnish strips"""
    p = geo.frame(seed=seed)
    m = geo.Mesh()
    xs = np.linspace(-W / 2, W / 2, 6); ys = np.linspace(-D / 2, D / 2, 5)
    X, Y = np.meshgrid(xs, ys, indexing='ij')
    Z = H - 18 * ((X / (W / 2)) ** 2 + (Y / (D / 2)) ** 2) + 6 * fbm(X * 0.02, Y * 0.02, 0.0, 2, seed=seed)
    P = np.stack([X, Y, Z], -1)
    net = geo.surface(P, 'net', p); net.charts[0]['atlas'] = 'cut'
    net2 = geo.surface(P, 'net', p, flip=True); net2.charts[0]['atlas'] = 'cut'
    m.add(net); m.add(net2)
    for (xx, yy) in ((-W / 2, -D / 2), (W / 2, -D / 2), (-W / 2, D / 2), (W / 2, D / 2), (0, -D / 2), (0, D / 2)):
        m.add(MG.cyl((xx, yy, 0), (xx, yy, H - 2), 2.4, 'wood_dark', p, sides=6))
        m.add(MG.cyl((xx, yy, H - 4), (xx * 1.15, yy * 1.15, 0), 0.5, 'rope', p, sides=4))
    m.recompute_normals(angle=50)
    return m


def net_img(w=512):
    """camouflage net texture with alpha: diamond mesh plus leafy garnish"""
    from PIL import Image, ImageDraw
    im = Image.new('RGBA', (w, w), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    rng = np.random.RandomState(3)
    step = 24
    for x in range(0, w, step):
        d.line([(x, 0), (w, w - x)], fill=(60, 55, 40, 255), width=2); d.line([(0, x), (w - x, w)], fill=(60, 55, 40, 255), width=2)
        d.line([(x, w), (w, x)], fill=(60, 55, 40, 255), width=2); d.line([(0, w - x), (w - x, 0)], fill=(60, 55, 40, 255), width=2)
    for _ in range(900):
        x, y = rng.randint(0, w), rng.randint(0, w); r = rng.randint(6, 16)
        col = [(70, 90, 40), (96, 84, 46), (52, 72, 34), (110, 100, 60)][rng.randint(0, 4)]
        d.ellipse([x - r, y - r // 2, x + r, y + r // 2], fill=col + (255,))
    return np.asarray(im, np.float32) / 255.0


NET_IMG = None


def _sh():
    global NET_IMG
    if NET_IMG is None: NET_IMG = net_img()
    return {'bamboo': M.bamboo, 'bamboo_floor': lambda c: M.bamboo(c), 'wood': M.wood, 'wood_dark': M.wood_dark, 'thatch': M.thatch,
            'wattle': lambda c: _wattle(c), 'mat': lambda c: S.canvas(c, base=S._c(0.60, 0.52, 0.30), mud_top=0.0, stains=0.3),
            'plaster': lambda c: M.concrete(c, tone=S._c(0.78, 0.72, 0.58), damage=0.6), 'interior_dark': lambda c: dict(color=np.full((c.n, 3), 0.06, np.float32), rough=np.full(c.n, 0.9, np.float32)),
            'shutter': lambda c: S.painted_steel(c, S._c(0.22, 0.42, 0.45), chip=0.35), 'tin': lambda c: _tin(c), 'blackboard': lambda c: dict(color=np.full((c.n, 3), 0.1, np.float32), rough=np.full(c.n, 0.7, np.float32)),
            'paint_red': lambda c: S.painted_steel(c, S._c(0.62, 0.12, 0.10), chip=0.3), 'tile': lambda c: M.concrete(c, tone=S._c(0.45, 0.28, 0.22), damage=0.2),
            'brass': M.brass, 'stone': lambda c: M.concrete(c, tone=S._c(0.50, 0.50, 0.46), damage=0.5), 'water_dark': lambda c: dict(color=np.full((c.n, 3), 0.08, np.float32), rough=np.full(c.n, 0.1, np.float32)),
            'gunsteel': M.gun_steel, 'rope': M.rope, 'wicker': lambda c: _wicker(c), 'rice': lambda c: _rice(c),
            'clay': lambda c: M.concrete(c, tone=S._c(0.48, 0.30, 0.22), damage=0.2), 'cloth': lambda c: S.canvas(c, base=S._c(0.55, 0.45, 0.55), mud_top=0.0, stains=0.3),
            'hay': lambda c: _hay(c), 'mud': M.earth, 'tarp_blue': lambda c: M.tarp(c, base=S._c(0.18, 0.30, 0.52)), 'charred': lambda c: S.rust_steel(c, burnt=1.0),
            'net': lambda c: M.grass_card(c, NET_IMG)}


def _wattle(ctx):
    """split-bamboo matting: flat strips 3.4 u wide woven over uprights every 10 u, each row shifted (soft relief, no checkerboard)"""
    from noise import hash01, smoothstep
    S_ = ctx.S
    u, v = S_[:, 0], S_[:, 1]
    row = np.floor(v / 3.4); fv = v / 3.4 - row
    over = np.cos(u / 10.0 * np.pi + row * np.pi)
    gap = smoothstep(0.14, 0.0, np.minimum(fv, 1 - fv))
    tone = hash01(row.astype(np.int64), 5)
    col = S.mix(S._c(0.53, 0.45, 0.27), S._c(0.42, 0.35, 0.20), tone) * (0.86 + 0.14 * over)[:, None]
    col = col * (1 - 0.45 * gap)[:, None]
    n = fbm(ctx.P[:, 0] * 0.1, ctx.P[:, 1] * 0.1, ctx.P[:, 2] * 0.1, 3, seed=301) * 0.5 + 0.5
    col = col * (0.82 + 0.28 * n[:, None])
    h = 0.22 * over - 0.45 * gap
    col, rough, h, _ = S.mud_layer(ctx, col, np.full(ctx.n, 0.9, np.float32), h, top=16.0, amount=0.8, splash=0.6)
    return dict(color=np.clip(S.ao_tint(col, ctx, 0.6), 0, 1), rough=rough, height=h)


def _tin(ctx):
    out = S.rust_steel(ctx, paint=S._c(0.55, 0.56, 0.54), chip=0.5, mud_top=0.0)
    corr = np.sin(ctx.S[:, 1] * 1.4) * 0.5
    out['height'] = out['height'] + corr * 0.6
    return out


def _wicker(ctx):
    """basket weave: thin weavers (1.3 u) over stakes every 3.6 u"""
    from noise import hash01, smoothstep
    S_ = ctx.S
    u, v = S_[:, 0], S_[:, 1]
    row = np.floor(v / 1.3); fv = v / 1.3 - row
    over = np.cos(u / 3.6 * np.pi + row * np.pi)
    gap = smoothstep(0.2, 0.0, np.minimum(fv, 1 - fv))
    col = S.mix(S._c(0.60, 0.49, 0.28), S._c(0.50, 0.40, 0.22), hash01(row.astype(np.int64), 6)) * (0.84 + 0.16 * over)[:, None] * (1 - 0.4 * gap)[:, None]
    return dict(color=np.clip(S.ao_tint(col, ctx, 0.6), 0, 1), rough=np.full(ctx.n, 0.88, np.float32), height=0.2 * over - 0.3 * gap)


def _rice(ctx):
    """unhusked paddy heaped in a basket: grains about 0.3 u (8 mm), golden to grey-brown per grain, husk sheen"""
    from noise import cells, hash01
    P = ctx.P * 3.4
    f1, f2, cid = cells(P[:, 0], P[:, 1], P[:, 2], seed=7)
    t = hash01(cid, 3)
    col = S.mix(S._c(0.78, 0.64, 0.36), S._c(0.62, 0.50, 0.30), t) * (0.75 + 0.25 * np.clip(f2 - f1, 0, 1) * 2)[:, None]
    n = fbm(ctx.P[:, 0] * 0.15, ctx.P[:, 1] * 0.15, ctx.P[:, 2] * 0.15, 2, seed=9)
    col = col * (0.9 + 0.1 * n)[:, None]
    h = 0.12 * np.clip(f2 - f1, 0, 0.5)
    return dict(color=np.clip(S.ao_tint(col, ctx, 0.7), 0, 1), rough=np.clip(0.62 + 0.2 * f1, 0, 1).astype(np.float32), height=h)


def _hay(ctx):
    P = ctx.P
    n = fbm(P[:, 0] * 0.4, P[:, 1] * 0.4, P[:, 2] * 0.4, 3, seed=311)
    col = S.mix(S._c(0.70, 0.60, 0.30), S._c(0.50, 0.40, 0.18), np.clip(n * 0.5 + 0.5, 0, 1))
    return dict(color=np.clip(S.ao_tint(col, ctx, 0.7), 0, 1), rough=np.full(ctx.n, 0.95, np.float32), height=0.3 * n)


# chart material -> CS2 tiling material (stock.py keys) for the large surfaces (playtest 1, finding 16): roofs, wall panels,
# floors and plaster at CS2's own texel density; poles, posts and small pieces stay on the baked atlas
VSTOCK = {'thatch': 'v_thatch', 'thatch_ridge': 'v_thatch_cyl', 'thatch_fringe': 'v_thatch_edge', 'wattle': 'v_reed',
          'bamboo_floor': 'v_bamboo', 'plaster': 'v_plaster', 'straw': 'v_hay', 'straw_body': 'v_thatch', 'basket': 'v_basket', 'bamboo': 'mv_bamboo'}


def _two(fn, size=1024, hulls=None, ground=0.0, thr=30.0, surface='wood', cut=False, stock=None, **kw):
    a = fn(lod=0, **kw); b = fn(lod=1, **kw)
    imgs = {}
    if isinstance(a, tuple): a, imgs = a; b = b[0]
    lo, hi = a.bounds()
    spec = dict(lods=[a, b], lod_thresholds=[0.0, thr], size=size, decal_size=512, ground=ground, surface=surface, metal=False, shaders=_sh(),
                decal_imgs=imgs, stock=VSTOCK if stock is None else stock, hulls=hulls if hulls is not None else [MG.pts_box(lo[0], lo[1], lo[2], hi[0], hi[1], hi[2])])
    if cut: spec['atlases'] = {'main': dict(size=size), 'cut': dict(size=512, alpha=lambda b: b['metal'], metal=False, fill=0.9, backfaces=True)}
    return spec


def specs():
    return {
        'hooch_a': lambda: _two(hooch, 2048, hulls=[MG.pts_box(-110, -80, -4, 110, 80, 96), MG.pts_box(-132, -102, 88, 132, 102, 170)], L=220, W=160),
        'hooch_b': lambda: _two(hooch, 2048, hulls=[MG.pts_box(-90, -70, -4, 90, 70, 96), MG.pts_box(-112, -92, 88, 112, 92, 160)], L=180, W=140, seed=111),
        'hooch_c': lambda: _two(hooch, 2048, hulls=[MG.pts_box(-130, -90, -4, 130, 90, 104), MG.pts_box(-152, -112, 96, 152, 112, 190)], L=260, W=180, loft=True, seed=112),
        'camp_hut': lambda: _two(camp_hut, 2048, hulls=[MG.pts_box(-136, -92, 0, 136, 92, 10), MG.pts_box(-156, -116, 84, 156, 116, 170), MG.pts_box(-136, -92, 0, -126, 92, 44), MG.pts_box(-136, -92, 0, 136, -82, 44), MG.pts_box(-136, 82, 0, 136, 92, 44)]),
        'school': lambda: _two(school, 2048, hulls=[MG.pts_box(-150, -100, 0, 150, -94, 110), MG.pts_box(-150, 94, 0, 150, 100, 110), MG.pts_box(-150, -100, 0, -144, 100, 110), MG.pts_box(144, -100, 0, 150, -26, 110), MG.pts_box(144, 26, 0, 150, 100, 110), MG.pts_box(-175, -125, 104, 175, 125, 160), MG.pts_box(206, -74, 0, 214, -66, 120)], surface='concrete'),
        'shrine': lambda: _two(shrine, 1024, hulls=[MG.pts_box(-24, -20, 0, 24, 20, 104)], surface='concrete'),
        'well': lambda: _two(well, 1024, hulls=[MG.pts_box(-38, -38, 0, 38, 38, 36), MG.pts_box(-4, -40, 0, 4, 40, 96)], surface='concrete'),
        'bamboo_fence': lambda: _two(bamboo_fence, 1024, hulls=[MG.pts_box(-66, -2, 0, 66, 6, 60)]),
        'bamboo_fence_64': lambda: _two(bamboo_fence, 512, hulls=[MG.pts_box(-34, -2, 0, 34, 6, 60)], length=64, seed=97),
        'rice_basket': lambda: _two(rice_basket, 256),
        'water_jar': lambda: _two(water_jar, 256, surface='concrete'),
        'drying_rack': lambda: _two(drying_rack, 512, hulls=[MG.pts_box(-52, -4, 0, -48, 0, 70), MG.pts_box(48, -4, 0, 52, 0, 70)]),
        'haystack': lambda: _two(haystack, 512),
        'pig_pen': lambda: _two(pig_pen, 1024, hulls=[MG.pts_box(-72, -52, 0, 72, -48, 36), MG.pts_box(-72, 48, 0, 72, 52, 36), MG.pts_box(68, -52, 0, 72, 52, 36), MG.pts_box(-72, -52, 0, -68, 52, 36)]),
        'ox_cart': lambda: _two(ox_cart, 1024, hulls=[MG.pts_box(-60, -40, 0, 50, 40, 62), MG.pts_box(-60, -30, 40, 50, 30, 92)]),
        'sampan': lambda: _two(sampan, 1024, hulls=[MG.pts_box(-120, -30, 0, 120, 30, 30), MG.pts_box(-60, -30, 22, 40, 30, 56)]),
        'sampan_open': lambda: _two(sampan, 1024, hulls=[MG.pts_box(-120, -30, 0, 120, 30, 30)], roof=False, seed=104),
        'fish_trap': lambda: _two(fish_trap, 256),
        'market_stall': lambda: _two(market_stall, 1024, hulls=[MG.pts_box(-44, -36, 0, 44, 36, 40), MG.pts_box(-52, -42, 0, -48, -38, 100), MG.pts_box(-52, 38, 0, -48, 42, 100), MG.pts_box(48, -42, 0, 52, -38, 80), MG.pts_box(48, 38, 0, 52, 42, 80)]),
        'propaganda_board': lambda: _two(propaganda_board, 1024, hulls=[MG.pts_box(-3, -64, 0, 3, 64, 110)]),
        'punji_stakes': lambda: _two(punji_stakes, 512, hulls=[]),
        'cook_fire': lambda: _two(cook_fire, 512, hulls=[MG.pts_box(-30, -30, 0, 30, 30, 10)]),
        'camo_net': lambda: _two(camo_net, 1024, hulls=[MG.pts_box(-282, -212, 0, -278, -208, 150), MG.pts_box(278, -212, 0, 282, -208, 150), MG.pts_box(-282, 208, 0, -278, 212, 150), MG.pts_box(278, 208, 0, 282, 212, 150)], cut=True),
    }
