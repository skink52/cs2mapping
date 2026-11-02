"""Small props: ammunition, crates, helmets, medical, signs, plotting table, mortar ammo box, Bessonneau hangar."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import geo
from noise import fbm
import shaders as S

FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf'
FONT_SERIF = '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'


def text_img(lines, w=512, h=128, color=(0.92, 0.90, 0.85), font=FONT, rough=True, size=None):
    im = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(im)
    n = len(lines)
    fs = size or int(h / (n + 0.4) * 0.8)
    f = ImageFont.truetype(font, fs)
    for i, t in enumerate(lines):
        bb = d.textbbox((0, 0), t, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        sc = min(1.0, (w * 0.92) / max(tw, 1))
        if sc < 1:
            f2 = ImageFont.truetype(font, int(fs * sc)); bb = d.textbbox((0, 0), t, font=f2); tw, th = bb[2] - bb[0], bb[3] - bb[1]
        else:
            f2 = f
        y = (i + 0.5) * h / n - th / 2 - bb[1]
        d.text(((w - tw) / 2 - bb[0], y), t, fill=255, font=f2)
    a = np.asarray(im, np.float32) / 255.0
    if rough:
        # hand-painted: brush streaks and drips
        yy, xx = np.mgrid[0:h, 0:w]
        n1 = fbm(xx * 0.05, yy * 0.05, 1.0, 3, seed=5)
        a = a * np.clip(0.75 + 0.5 * n1, 0, 1)
        a = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8)), np.float32) / 255
    rgba = np.zeros((h, w, 4), np.float32); rgba[..., :3] = color; rgba[..., 3] = a
    return rgba


def cross_img(w=256):
    a = np.zeros((w, w), np.float32)
    c = w // 2; t = w // 8; L = w * 3 // 8
    a[c - t:c + t, c - L:c + L] = 1; a[c - L:c + L, c - t:c + t] = 1
    bg = np.zeros((w, w, 4), np.float32)
    circle = ((np.mgrid[0:w, 0:w] - c) ** 2).sum(0) < (w * 0.47) ** 2
    bg[circle] = (0.85, 0.83, 0.78, 1.0)
    bg[a > 0] = (0.62, 0.08, 0.06, 1.0)
    return bg


def crate(L=30, W=16, H=12, seed=0, mat='wood', lod=0, lid=True):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    # plank sides
    top_charts = []
    sg = 2 if lod == 0 else 1
    for z0 in np.arange(0, H - 0.1, H / 2):
        for yy in (-W / 2 + 0.5, W / 2 - 0.5):
            m.add(geo.plank(L, H / 2 - 0.2, 1.0, mat=mat, seg=sg, div=(3, 1, 1), seed=seed + int(z0 * 3 + yy), R=geo.euler(0, 0, 90),
                            t=(0, yy, z0 + H / 4), tone=rng.rand()))
        for xx in (-L / 2 + 0.5, L / 2 - 0.5):
            m.add(geo.plank(W - 2, H / 2 - 0.2, 1.0, mat=mat, seg=sg, div=(2, 1, 1), seed=seed + int(z0 * 5 + xx), R=geo.euler(90, 0, 90),
                            t=(xx, 0, z0 + H / 4), tone=rng.rand()))
    nb = int(W / 5.5)
    for k in range(nb):
        w = W / nb
        if lid:
            top_charts.append(len(m.charts))
            m.add(geo.plank(L + 0.6, w - 0.3, 1.0, mat=mat, seg=sg, div=(3, 1, 1), seed=seed + 70 + k, t=(0, -W / 2 + w * (k + 0.5), H + 0.1), tone=rng.rand()))
        m.add(geo.plank(L, w - 0.3, 1.0, mat=mat, seg=1, div=(2, 1, 1), seed=seed + 90 + k, t=(0, -W / 2 + w * (k + 0.5), 0.5), tone=rng.rand()))
    # corner battens
    for xx in (-L / 2 + 2, L / 2 - 2):
        for yy in (-W / 2 - 0.4, W / 2 + 0.4):
            m.add(geo.rbox(2.2, 0.8, H, r=0.25, seg=1, mat=mat, part=geo.frame(seed=seed + int(xx + yy)), center=(xx, yy, H / 2)))
    # rope handles on the ends
    if lod == 0:
        for xx in (-L / 2 - 0.9, L / 2 + 0.9):
            th = np.linspace(0, np.pi, 9)
            pts = np.stack([np.full(9, xx) + np.sign(xx) * np.sin(th) * 1.4, np.cos(th) * 4, H * 0.6 - np.sin(th) * 1.5], 1)
            m.add(geo.tube(pts, 0.45, sides=6, mat='rope', part=geo.frame(seed=seed), caps=True))
    return m, top_charts


def shell(seed=0, lod=0, case=True, scale=1.0):
    """18-pdr style round lying along +x: brass case + steel projectile"""
    m = geo.Mesh()
    sides = 14 if lod == 0 else 7
    if case:
        cp = [(0.01, 0), (1.85, 0), (1.85, 0.4), (1.65, 0.5), (1.65, 9.5), (1.55, 11.0), (1.45, 11.2)]
        c = geo.lathe(cp, sides, 'brass', geo.frame(seed=seed)); m.add(c)
    pp = [(1.48, 11.0), (1.5, 13.5), (1.6, 14.0), (1.6, 14.6), (1.5, 15.0), (1.45, 16.5), (1.25, 19.0), (0.8, 21.0), (0.35, 22.0), (0.01, 22.2)]
    p = geo.lathe(pp, sides, 'proj', geo.frame(seed=seed + 1)); m.add(p)
    m.transform(geo.rot('y', 90), (0, 0, 0), s=scale)
    return m


def shell_pile(seed=0, lod=0):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    k = 0
    for row in range(3):
        n = 5 - row
        for i in range(n):
            s = shell(seed + k, lod)
            s.transform(geo.euler(rng.uniform(-6, 6), 0, rng.uniform(0, 360)), (rng.uniform(-1, 1) - 11, -n * 1.8 + i * 3.6 + row * 0.0, 1.8 + row * 3.0))
            m.add(s); k += 1
    for i in range(4):
        s = shell(seed + 50 + i, lod, case=(i % 2 == 0))
        s.transform(geo.euler(rng.uniform(0, 360), rng.uniform(-8, 8), rng.uniform(0, 360)), (rng.uniform(-30, 25), rng.uniform(-22, 22), 1.6))
        m.add(s)
    return m


def casings(seed=0, lod=0):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    cp = [(0.01, 0), (1.85, 0), (1.85, 0.4), (1.65, 0.5), (1.65, 9.5), (1.55, 11.0), (1.45, 11.2), (1.3, 11.2), (1.3, 1.0), (0.01, 1.0)]
    for i in range(14):
        c = geo.lathe(cp, 12 if lod == 0 else 6, 'brass', geo.frame(seed=seed + i))
        if rng.rand() < 0.3:
            c.transform(geo.euler(rng.uniform(0, 360), 0, 0), (rng.uniform(-24, 24), rng.uniform(-24, 24), 0))
        else:
            c.transform(geo.euler(rng.uniform(0, 360), 90 + rng.uniform(-5, 5), 0), (rng.uniform(-30, 30), rng.uniform(-30, 30), 1.75))
        m.add(c)
    return m


def helmet(kind='brodie', seed=0, lod=0):
    n = 24 if lod == 0 else 10
    if kind == 'brodie':
        prof = [(0.01, 4.9), (2.4, 4.7), (4.2, 3.9), (5.4, 2.4), (6.0, 0.9), (6.2, 0.4), (7.8, 0.05), (8.3, 0.0), (8.3, -0.25), (7.8, -0.15), (6.05, 0.25), (5.85, 0.8), (5.25, 2.2), (4.1, 3.6), (2.3, 4.4), (0.01, 4.6)]
    else:
        prof = [(0.01, 6.4), (2.5, 6.2), (4.5, 5.2), (5.6, 3.6), (5.9, 2.0), (6.0, 0.8), (6.6, -0.6), (7.3, -1.6), (7.2, -1.9), (6.4, -0.9), (5.7, 0.7), (5.6, 2.0), (5.3, 3.4), (4.3, 4.9), (2.4, 5.9), (0.01, 6.1)]
    m = geo.lathe(prof, n, 'helmet', geo.frame(seed=seed))
    if kind != 'brodie':
        V = m.V
        ang = np.arctan2(V[:, 1], V[:, 0])
        # stahlhelm: deeper skirt at the sides and back, shorter visor at the front
        back = np.clip(-np.cos(ang), 0, 1)
        V[:, 2] -= np.where(V[:, 2] < 1.2, 1.4 * back + 0.6 * np.abs(np.sin(ang)), 0)
        V[:, 0] *= 1.08
        m.V = V; m.recompute_normals()
        for s in (-1, 1):
            m.add(geo.lathe([(0.01, -0.3), (0.55, -0.3), (0.55, 0.3), (0.01, 0.3)], 8, 'helmet', geo.frame(seed=seed + 5)).transform(geo.rot('x', 90 * s), (0, s * 5.8, 3.2)))
    else:
        m.V[:, 0] *= 1.12; m.recompute_normals()
    return m


def stretcher(seed=0, lod=0):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    for yy in (-11, 11):
        m.add(geo.tube([(-46, yy, 5), (46, yy, 5)], 1.0, sides=8 if lod == 0 else 5, mat='wood', part=geo.frame(seed=seed + yy)))
    xs = np.linspace(-34, 34, 18); ys = np.linspace(-11, 11, 7)
    X, Y = np.meshgrid(xs, ys, indexing='ij')
    Z = 5.2 - 1.6 * np.cos(Y / 11 * np.pi / 2) * np.sin((X + 34) / 68 * np.pi) - 0.3 * fbm(X * 0.1, Y * 0.1, 1, 2, seed=3)
    P = np.stack([X, Y, Z], -1)
    c = geo.surface(P, 'canvas', geo.frame(seed=seed))
    if c.face_normals()[:, 2].mean() < 0: c.F = c.F[:, ::-1]
    c.recompute_normals(); m.add(c)
    under = geo.surface(P - [0, 0, 0.15], 'canvas', geo.frame(seed=seed)); under.F = c.F[:, ::-1].copy(); under.recompute_normals(); m.add(under)
    for xx in (-26, 26):
        for yy in (-11, 11):
            m.add(geo.tube([(xx, yy, 5), (xx, yy, 0.3)], 0.8, sides=6, mat='gunsteel', part=geo.frame(seed=seed)))
    return m


def sign(lines, seed=0, lod=0, w=40, h=12, post_h=60, color=(0.9, 0.88, 0.82), lean=4):
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    board_chart = len(m.charts)
    m.add(geo.plank(w, h, 1.2, mat='board', seg=2, div=(4, 1, 1), warp=0.08, seed=seed, R=geo.euler(0, 0, 90), t=(0, -0.2, post_h - h / 2 - 2), tone=0.7))
    zc = post_h - h / 2 - 2
    m.add(geo.decal(0, (-w * 0.47, -0.8, zc - h * 0.44), (1, 0, 0), (0, 0, 1), (w * 0.94, h * 0.88), lift=0.14))
    # the plank's front face (normal -y) chart: rbox face order: +z,-z,+x,-x,+y,-y -> after rotation x90 the -y face was +z
    m.add(geo.tube([(0, 1.6, -6), (0.5, 1.6, post_h + 2)], 1.6, sides=8, mat='wood', part=geo.frame(seed=seed + 1)))
    for k in range(2):
        m.add(geo.tube([(-2.2, 0.6, post_h - h + 2 + k * 6), (2.2, 0.6, post_h - h + 2 + k * 6)], 0.25, sides=4, mat='gunsteel', part=geo.frame(seed=seed)))
    m.transform(geo.euler(0, rng.uniform(-lean, lean), rng.uniform(-lean, lean)))
    return m, board_chart


def table_station(seed=0, lod=0):
    """mortar plotting table: trestle table with a map board and a field telephone"""
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    top0 = len(m.charts)
    for k in range(5):
        m.add(geo.plank(48, 6.2, 1.2, mat='wood', seg=2, div=(4, 1, 1), warp=0.2, seed=seed + k, t=(0, -12.4 + k * 6.2, 33.4), tone=rng.rand()))
    for xx in (-19, 19):
        for s in (-1, 1):
            m.add(geo.tube([(xx, s * 10, 33), (xx + s * 0.0, s * 13, 0)], 1.1, sides=7, mat='wood', part=geo.frame(seed=seed + int(xx) + s)))
        m.add(geo.tube([(xx, -12, 12), (xx, 12, 12)], 0.9, sides=6, mat='wood', part=geo.frame(seed=seed + 9)))
    # map board
    mapc = len(m.charts)
    m.add(geo.rbox(34, 24, 0.6, r=0.2, seg=1, mat='map', part=geo.frame(seed=seed + 20), center=(-3, 0, 34.4)))
    # field telephone (wooden box, crank, handset)
    m.add(geo.rbox(8, 6, 6, r=0.5, seg=1, mat='wood', part=geo.frame(seed=seed + 30, tone=0.2), center=(17, 6, 37)))
    m.add(geo.tube([(21.1, 6, 38), (22.5, 6, 38), (22.5, 6, 36)], 0.35, sides=5, mat='gunsteel', part=geo.frame(seed=seed)))
    m.add(geo.tube([(14, 3, 40.4), (20, 3, 40.4)], [0.8, 0.8], sides=7, mat='gunsteel', part=geo.frame(seed=seed)))
    # compass / dividers / pencil on the map
    m.add(geo.tube([(-10, 4, 34.9), (2, -3, 34.9)], 0.3, sides=5, mat='wood', part=geo.frame(seed=seed + 40)))
    return m, mapc


def ammo_box(seed=0, lod=0):
    """open crate of trench-mortar bombs (loader station)"""
    m, tops = crate(34, 22, 14, seed=seed, lod=lod, lid=False)
    for i in range(3):
        for j in range(2):
            b = geo.lathe([(0.01, 0), (2.8, 0), (3.0, 1), (3.0, 11), (2.6, 13), (1.2, 13.4), (1.2, 15.5), (0.01, 15.5)], 14 if lod == 0 else 7, 'bomb', geo.frame(seed=seed + i * 3 + j))
            b.transform(geo.rot('y', 90), (-8, -6.5 + i * 6.5, 4 + j * 6.2))
            m.add(b)
    # lid leaning against the crate
    lid = geo.Mesh()
    for k in range(4):
        lid.add(geo.plank(34, 5.2, 1.0, mat='wood', seg=1, div=(3, 1, 1), seed=seed + 300 + k, t=(0, -7.8 + k * 5.3, 0), tone=0.6))
    lid.transform(geo.euler(0, 0, 70), (0, -15, 9)); m.add(lid)
    return m


def hangar(lod=0, seed=0):
    """Bessonneau-style canvas aircraft hangar: wooden lattice trusses, canvas skin, open front at -x"""
    rng = np.random.RandomState(seed)
    m = geo.Mesh()
    L, Wd, Hw, Hr = 760.0, 640.0, 150.0, 300.0
    nb = 7
    xs = np.linspace(-L / 2, L / 2, nb)
    def roof_z(y): return Hw + (Hr - Hw) * (1 - (np.abs(y) / (Wd / 2)) ** 1.0)
    for x in xs:
        # posts and rafters (timber)
        for s in (-1, 1):
            m.add(geo.rbox(6, 6, Hw, r=0.8, seg=1, mat='wood', part=geo.frame(seed=seed + int(x) + s), center=(x, s * Wd / 2, Hw / 2)))
            pts = np.array([[x, s * Wd / 2, Hw + 3], [x, 0, Hr + 3]])
            m.add(geo.tube(pts, 3.0, sides=6, mat='wood', part=geo.frame(seed=seed + int(x) * 3 + s)))
            # lattice diagonals
            for k in range(5):
                y0 = s * Wd / 2 * (1 - k / 5); y1 = s * Wd / 2 * (1 - (k + 1) / 5)
                m.add(geo.tube([[x, y0, roof_z(y0) - 2], [x, y1, roof_z(y1) - 20]], 1.2, sides=4, mat='wood', part=geo.frame(seed=seed + k)))
        m.add(geo.tube([[x, -Wd / 2, Hw - 10], [x, Wd / 2, Hw - 10]], 2.0, sides=6, mat='wood', part=geo.frame(seed=seed + 77)))
    # canvas: roof (two slopes), side walls, back wall; drape between trusses
    ny = 16 if lod == 0 else 6; nx = (nb - 1) * (6 if lod == 0 else 2)
    for s in (-1, 1):
        X, Y = np.meshgrid(np.linspace(-L / 2 - 8, L / 2 + 8, nx + 1), np.linspace(0, s * (Wd / 2 + 12), ny + 1), indexing='ij')
        sag = 6 * np.abs(np.sin((X + L / 2) / (L / (nb - 1)) * np.pi))
        Z = roof_z(np.clip(Y, -Wd / 2, Wd / 2)) + 6 - sag - np.where(np.abs(Y) > Wd / 2, (np.abs(Y) - Wd / 2) * 1.2, 0)
        P = np.stack([X, Y, Z], -1)
        r = geo.surface(P, 'canvas', geo.frame(seed=seed + 100 + s))
        if r.face_normals()[:, 2].mean() < 0: r.F = r.F[:, ::-1]
        r.recompute_normals(); m.add(r)
        ri = geo.surface(P - [0, 0, 0.6], 'canvas_in', geo.frame(seed=seed + 100 + s)); ri.F = r.F[:, ::-1].copy(); ri.recompute_normals(); m.add(ri)
        # side wall
        X, Z = np.meshgrid(np.linspace(-L / 2 - 8, L / 2 + 8, nx + 1), np.linspace(0, Hw + 6, 6 if lod == 0 else 2), indexing='ij')
        Y = s * (Wd / 2 + 8) + s * 4 * np.abs(np.sin((X + L / 2) / (L / (nb - 1)) * np.pi)) * (Z / Hw)
        P = np.stack([X, Y, Z], -1)
        w = geo.surface(P, 'canvas', geo.frame(seed=seed + 200 + s))
        if (w.face_normals()[:, 1] * s).mean() < 0: w.F = w.F[:, ::-1]
        w.recompute_normals(); m.add(w)
        wi = geo.surface(P - [0, s * 0.6, 0], 'canvas_in', geo.frame(seed=seed + 200 + s)); wi.F = w.F[:, ::-1].copy(); wi.recompute_normals(); m.add(wi)
    # back wall (+x) gable
    Y, Z = np.meshgrid(np.linspace(-Wd / 2 - 8, Wd / 2 + 8, ny * 2 + 1), np.linspace(0, 1, 8 if lod == 0 else 3), indexing='ij')
    Z = Z * (roof_z(np.clip(Y, -Wd / 2, Wd / 2)) + 4)
    X = np.full_like(Y, L / 2 + 8) + 3 * np.sin(Y * 0.02) * (Z / Hr)
    P = np.stack([X, Y, Z], -1)
    b = geo.surface(P, 'canvas', geo.frame(seed=seed + 300))
    if b.face_normals()[:, 0].mean() < 0: b.F = b.F[:, ::-1]
    b.recompute_normals(); m.add(b)
    bi = geo.surface(P - [0.6, 0, 0], 'canvas_in', geo.frame(seed=seed + 300)); bi.F = b.F[:, ::-1].copy(); bi.recompute_normals(); m.add(bi)
    # front curtains rolled up at the top of the opening
    m.add(geo.tube([[-L / 2 - 10, -Wd / 2, Hw + 2], [-L / 2 - 10, 0, Hr - 6], [-L / 2 - 10, Wd / 2, Hw + 2]], 7, sides=10, mat='canvas', part=geo.frame(seed=seed + 400)))
    for c in m.charts:
        c['atlas'] = 'canvas' if c['mat'].startswith('canvas') else 'main'
    hulls = []
    for s in (-1, 1):
        hulls.append(np.array([[x, y, z] for x in (-L / 2, L / 2) for y in (s * Wd / 2, s * (Wd / 2 + 10)) for z in (0, Hw)]))
        hulls.append(np.array([[x, y, z] for x in (-L / 2, L / 2) for y in (0, s * (Wd / 2 + 10)) for z in (Hr + 6, Hw - 2)] +
                              [[x, s * (Wd / 2 + 10), Hw - 8] for x in (-L / 2, L / 2)]))
    hulls.append(np.array([[x, y, z] for x in (L / 2, L / 2 + 10) for y in (-Wd / 2, Wd / 2) for z in (0, Hw)]))
    return m, hulls


def specs():
    W = lambda c: S.wood(c, mud_top=3, wet=0.3)
    rope = lambda c: S.canvas(c, base=S._c(0.55, 0.47, 0.33), mud_top=0)
    out = {}
    sh = {'wood': W, 'rope': rope}
    for name, (L, Wd, H, txt) in {'crate_shells': (30, 16, 12, ['18 PDR', 'H.E. 4']), 'crate_long': (44, 18, 14, ['S.A.A.', '1000 RDS']),
                                  'crate_german': (36, 20, 14, ['7,7 cm', 'F.K. Gr.'])}.items():
        m0, tops = crate(L, Wd, H, seed=hash(name) % 997)
        m1, _ = crate(L, Wd, H, seed=hash(name) % 997, lod=1)
        img = text_img(txt, 512, 192, color=(0.08, 0.07, 0.06), font=FONT)
        for mm in (m0, m1):
            mm.add(geo.decal(0, (-L * 0.4, -Wd * 0.4, H + 0.6), (1, 0, 0), (0, 1, 0), (L * 0.8, Wd * 0.8), lift=0.16))
        out[name] = dict(lods=[m0, m1], size=512, ground=0.0, shaders={'wood': W, 'rope': rope}, surface='wood', decal_imgs=[img],
                         stock={'wood': 'boards', 'rope': 'rope'},
                         hulls=[np.array([[x, y, z] for x in (-L / 2, L / 2) for y in (-Wd / 2, Wd / 2) for z in (0, H + 0.6)])], res=0.5)
    bst = {'brass': 'brass', 'proj': 'paint_khaki'}
    bsh = {'brass': S.brass, 'proj': lambda c: S.painted_steel(c, S._c(0.32, 0.34, 0.28), chip=0.3, mud_top=2, edge_k=0.2)}
    out['shell_pile'] = dict(lods=[shell_pile(1), shell_pile(1, 1)], size=1024, ground=0.0, metal=True, shaders=bsh, stock=bst, surface='metal',
                             hulls=[np.array([[x, y, z] for x in (-12, 12) for y in (-9, 9) for z in (0, 9)])], res=0.4)
    out['casings'] = dict(lods=[casings(2), casings(2, 1)], size=512, ground=0.0, metal=True, shaders=bsh, stock=bst, surface='metal', hulls=[], res=0.4)
    hsh = {'helmet': lambda c: S.painted_steel(c, S._c(0.30, 0.31, 0.22), chip=0.3, mud_top=2, edge_k=0.15)}
    out['helmet_brodie'] = dict(lods=[helmet('brodie', 1)], size=256, ground=0.0, metal=True, shaders=hsh, stock={'helmet': 'paint_khaki'}, surface='metal', hulls=[], res=0.25)
    hsh2 = {'helmet': lambda c: S.painted_steel(c, S._c(0.36, 0.38, 0.33), chip=0.3, mud_top=2, edge_k=0.15)}
    out['helmet_stahl'] = dict(lods=[helmet('stahl', 2)], size=256, ground=0.0, metal=True, shaders=hsh2, stock={'helmet': 'paint_feld'}, surface='metal', hulls=[], res=0.25)
    ssh = {'wood': W, 'canvas': lambda c: S.canvas(c, mud_top=2), 'gunsteel': lambda c: S.rust_steel(c, mud_top=1)}
    out['stretcher'] = dict(lods=[stretcher(3)], size=512, ground=0.0, metal=True, shaders=ssh, stock={'wood': 'boards', 'canvas': 'canvas', 'gunsteel': 'rust_fine'}, surface='cloth',
                            hulls=[np.array([[x, y, z] for x in (-46, 46) for y in (-12, 12) for z in (0, 6)])], res=0.5)
    # red-cross crate
    m0, tops = crate(30, 20, 18, seed=41); m1, _ = crate(30, 20, 18, seed=41, lod=1)
    rc = cross_img()
    for mm in (m0, m1):
        mm.add(geo.decal(0, (-9, -9, 18.6), (1, 0, 0), (0, 1, 0), (18, 18), lift=0.16))
        mm.add(geo.decal(0, (-7, -10.0, 2), (1, 0, 0), (0, 0, 1), (14, 14), lift=0.14))
    medic = lambda c: S.decal_proj(S.decal_proj(c, rc, W, (-9, -9, 18), (1, 0, 0), (0, 1, 0), (18, 18), facing=(0, 0, 1)), rc, None, (-7, -10.5, 2), (1, 0, 0), (0, 0, 1), (14, 14), facing=(0, -1, 0)) if False else S.decal_proj(c, rc, lambda cc: S.decal_proj(cc, rc, W, (-7, -10.5, 2), (1, 0, 0), (0, 0, 1), (14, 14), facing=(0, -1, 0)), (-9, -9, 18), (1, 0, 0), (0, 1, 0), (18, 18), facing=(0, 0, 1))
    out['crate_medical'] = dict(lods=[m0, m1], size=512, ground=0.0, shaders={'wood': W, 'rope': rope}, decal_imgs=[rc], stock={'wood': 'boards', 'rope': 'rope'},
                                surface='wood', hulls=[np.array([[x, y, z] for x in (-15, 15) for y in (-10, 10) for z in (0, 18.6)])], res=0.5)
    signs = {'sign_dressing_gb': ['DRESSING', 'STATION'], 'sign_dressing_de': ['VERBAND-', 'PLATZ'], 'sign_mortars_gb': ['TRENCH', 'MORTARS'],
             'sign_mortars_de': ['MINEN-', 'WERFER'], 'sign_firetrench_gb': ['FIRE', 'TRENCH'], 'sign_firetrench_de': ['FEUER-', 'GRABEN'],
             'sign_piccadilly': ['PICCADILLY', 'CIRCUS'], 'sign_unter_den_linden': ['UNTER DEN', 'LINDEN'], 'sign_danger': ['DANGER', 'SNIPERS'],
             'sign_achtung': ['ACHTUNG!', 'FEIND SIEHT'], 'sign_airfield_gb': ['R.F.C.', 'AERODROME'], 'sign_airfield_de': ['FLIEGER-', 'ABTEILUNG'],
             'sign_wood_gb': ['TO THE', 'WOOD'], 'sign_wood_de': ['ZUM', 'WALD'],
             'sign_sap_gb': ['SAP 7', 'NO NAKED LIGHTS'], 'sign_sap_de': ['STOLLEN 7', 'RUHE!']}
    for k, (name, lines) in enumerate(signs.items()):
        m0, ch = sign(lines, seed=60 + k)
        img = text_img(lines, 512, 160, color=(0.88, 0.86, 0.80) if not name.endswith('_de') and name not in ('sign_unter_den_linden', 'sign_achtung') else (0.10, 0.09, 0.08))
        base = W if not (name.endswith('_de') or name in ('sign_unter_den_linden', 'sign_achtung')) else (lambda c: S.painted_steel(c, S._c(0.78, 0.76, 0.70), chip=0.28, mud_top=4, edge_k=0.3))
        # board front face: rbox faces are +z,-z,+x,-x,+y,-y; rotated about x by 90 -> local -y face points to -y... use both big faces
        enamel = name.endswith('_de') or name in ('sign_unter_den_linden', 'sign_achtung')
        out[name] = dict(lods=[m0], size=512, ground=0.0, metal=True, shaders={'wood': W, 'board': base, 'gunsteel': lambda c: S.rust_steel(c, mud_top=0)},
                         decal_imgs=[img], stock={'wood': 'boards', 'board': 'paint_white' if enamel else 'boards', 'gunsteel': 'rust_fine'}, surface='wood', hulls=[], res=0.5)
    m0, mapc = table_station(5)
    mapimg = np.asarray(Image.open(__import__('os').path.join(__import__('os').path.dirname(__file__), 'trench_map_small.png')).convert('RGBA'), np.float32) / 255 \
        if __import__('os').path.exists(__import__('os').path.join(__import__('os').path.dirname(__file__), 'trench_map_small.png')) else text_img(['MAP'], 256, 256)
    out['plotting_table'] = dict(lods=[m0], size=1024, ground=0.0, metal=True, stock={'wood': 'boards', 'gunsteel': 'paint_dark'},
                                 shaders={'wood': W, 'gunsteel': lambda c: S.painted_steel(c, S._c(0.12, 0.12, 0.11), chip=0.2, mud_top=0),
                                          'map': lambda c: S.decal_proj(c, mapimg, lambda cc: S.canvas(cc, base=S._c(0.80, 0.76, 0.64), mud_top=0, stains=0.3), (-20, -12, 34), (1, 0, 0), (0, 1, 0), (34, 24), facing=(0, 0, 1), weather=False)},
                                 surface='wood', hulls=[np.array([[x, y, z] for x in (-24, 24) for y in (-15, 15) for z in (0, 35)])], res=0.5)
    out['ammo_box_mortar'] = dict(lods=[ammo_box(7), ammo_box(7, 1)], size=1024, ground=0.0, metal=True, stock={'wood': 'boards', 'rope': 'rope', 'bomb': 'paint_feld'},
                                  shaders={'wood': W, 'rope': rope, 'bomb': lambda c: S.painted_steel(c, S._c(0.35, 0.36, 0.30), chip=0.25, mud_top=0, edge_k=0.2)},
                                  surface='wood', hulls=[np.array([[x, y, z] for x in (-17, 17) for y in (-11, 11) for z in (0, 14)])], res=0.5)
    m0, hh = hangar(0, 8); m1, _ = hangar(1, 8)
    out['hangar'] = dict(lods=[m0, m1], lod_thresholds=[0.0, 60.0], ground=0.0, stock={'wood': 'boards', 'canvas': 'canvas', 'canvas_in': 'canvas_dark'},
                         atlases={'main': dict(size=2048), 'canvas': dict(size=2048, backfaces=False)},
                         shaders={'wood': lambda c: S.wood(c, mud_top=20, wet=0.3), 'canvas': lambda c: S.canvas(c, base=S._c(0.62, 0.58, 0.47), mud_top=24),
                                  'canvas_in': lambda c: S.canvas(c, base=S._c(0.50, 0.46, 0.37), mud_top=10)},
                         surface='cloth', hulls=hh, res=6.0)
    return out
