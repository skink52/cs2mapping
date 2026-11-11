"""Radar / minimap for mg_monsoon, drawn from tools/layout.py alone (no vmap needed), fitted to the ground play space.
Same conventions as mg_trenchwarfare's make_radar.py (the cs2port radar that works in game): a 1024 px png + .vtex (max 1024,
no lod), and game resource/overviews/<map>.txt with pos_x / pos_y = world position of the image's top-left corner and
scale = world units per pixel.

usage: make_radar.py [<addon content out> [<addon game out>]]        defaults ../out/addon ../out/game
  writes <addon>/panorama/images/overheadmaps/mg_monsoon_radar_psd.png + .vtex
         <game>/resource/overviews/mg_monsoon.txt
         ../out/radar_region.json  {x0, y0, span, scale, size}       (render_board.py and the docs read it)
         ../out/radar_clean.png    the same picture without lettering
         ../out/radar_preview.png  the radar as shipped

The square is x, y in [-6400, 6400] (pos -6400 / 6400, scale 12.5): the play space is 12800 wide and 10240 tall, so the
valley fills the width and the bands above / below (the valley sides outside the play space) are dimmed. It is the same
square the artillery board uses (CONFIG.BOARD.EXT 6400), and the 16 x 16 grid (A-P across, 1-16 down) is the one the
script's gridRef() / !pos report.

Also the map renderer for render_board.py (the board picture and the loading slides): View, fields(), render_sat(), render_topo().
"""
import os, sys, json, math, hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layout as LY
from noise import fbm

MAP = 'mg_monsoon'
EXT = 6400.0                      # the radar / board square: x, y in [-EXT, EXT]
OUT_N = 1024
SCALE = 2 * EXT / OUT_N           # 12.5 world units per pixel
X0, Y0 = -EXT, EXT                # world position of the image's top-left corner
MASTER_N = 1536                   # cached terrain raster of the square
CACHE = os.path.join(HERE, '..', 'out', 'cache')
FONT_B = ['C:/Windows/Fonts/bahnschrift.ttf', 'C:/Windows/Fonts/arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf']
FONT_S = ['C:/Windows/Fonts/georgiab.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf', 'C:/Windows/Fonts/arialbd.ttf']
CT_COL = (104, 163, 229)          # CS2 team colours (CT blue, T sand)
T_COL = (234, 190, 84)


def font(size, serif=False, weight='Bold'):
    for p in (FONT_S if serif else FONT_B):
        if os.path.exists(p):
            f = ImageFont.truetype(p, int(size))
            try: f.set_variation_by_name(weight)
            except Exception: pass
            return f
    return ImageFont.load_default()


# ---------------------------------------------------------------- the cached terrain raster
_MASTER = {}


def master():
    """Z, jungle, grass, paint weight of the [-EXT, EXT] square (row 0 = north), cached by layout.py's content"""
    h = hashlib.md5(open(os.path.join(HERE, 'layout.py'), 'rb').read())
    dp = os.path.join(HERE, 'data', 'detail.png')                 # the eroded detail layer is part of the ground (docs/IMAGE_TERRAIN.md)
    if os.path.exists(dp): h.update(open(dp, 'rb').read())
    key = h.hexdigest()[:12]
    p = os.path.join(CACHE, 'terrain_%d_%s.npz' % (MASTER_N, key))
    if not os.path.exists(p) and os.environ.get('MV_RADAR_STALE') and os.path.isdir(CACHE):      # iterate on the look without waiting for a re-raster
        old = sorted(f for f in os.listdir(CACHE) if f.startswith('terrain_%d_' % MASTER_N))
        if old: p = os.path.join(CACHE, old[-1]); print('  (stale terrain cache %s)' % old[-1])
    if os.path.exists(p):
        if p not in _MASTER: d = np.load(p); _MASTER[p] = {k: d[k] for k in d.files}
        return _MASTER[p]
    os.makedirs(CACHE, exist_ok=True)
    N = MASTER_N
    xs = -EXT + (np.arange(N) + 0.5) * 2 * EXT / N; ys = EXT - (np.arange(N) + 0.5) * 2 * EXT / N
    Z = np.zeros((N, N), np.float32)
    for r in range(0, N, 128):
        X, Y = np.meshgrid(xs, ys[r:r + 128])
        Z[r:r + 128] = LY.height(X, Y)
        print('  terrain raster %d / %d' % (min(r + 128, N), N), flush=True)
    n = N // 2
    xs2 = -EXT + (np.arange(n) + 0.5) * 2 * EXT / n; ys2 = EXT - (np.arange(n) + 0.5) * 2 * EXT / n
    X, Y = np.meshgrid(xs2, ys2)
    J = LY.jungle(X, Y).astype(np.float32); G = LY.grass(X, Y).astype(np.float32)
    sl = LY.grid_slope(ndimage.zoom(Z, 0.5, order=1).T[:, ::-1], 2 * EXT / n).T[::-1][::-1]      # slope of the half-size grid
    gy, gx = np.gradient(ndimage.zoom(Z, 0.5, order=1), 2 * EXT / n)
    sl = np.degrees(np.arctan(np.hypot(gx, gy)))
    PW, TI = LY.paint_weight(X, Y, None, sl=sl)
    d = dict(Z=Z, J=J, G=G, PW=PW.astype(np.float32), SL=sl.astype(np.float32))
    for f in os.listdir(CACHE):
        if f.startswith('terrain_'): os.remove(os.path.join(CACHE, f))
    np.savez_compressed(p, **d)
    _MASTER[p] = d
    return d


class View:
    """a north-up window on the world: (x0, y0) = world position of the top-left corner, upp = world units per pixel"""

    def __init__(self, x0, y0, upp, W, H):
        self.x0, self.y0, self.upp, self.W, self.H = float(x0), float(y0), float(upp), int(W), int(H)

    def px(self, x, y):
        return ((x - self.x0) / self.upp, (self.y0 - y) / self.upp)

    def plen(self, u):
        return u / self.upp

    def grid(self):
        xs = self.x0 + (np.arange(self.W) + 0.5) * self.upp; ys = self.y0 - (np.arange(self.H) + 0.5) * self.upp
        return np.meshgrid(xs, ys)

    def sample(self, a, order=1):
        """a master array (any square size) sampled on this view's pixels"""
        n = a.shape[0]
        X, Y = self.grid()
        col = (X + EXT) / (2 * EXT) * n - 0.5; row = (EXT - Y) / (2 * EXT) * n - 0.5
        return ndimage.map_coordinates(a, [row, col], order=order, mode='nearest')


def fields(v):
    """everything the renderers need, on the view's pixel grid"""
    m = master()
    X, Y = v.grid()
    Z = v.sample(m['Z'], 3 if v.upp < 2 * EXT / MASTER_N else 1)
    J = np.clip(v.sample(m['J']), 0, 1); G = np.clip(v.sample(m['G']), 0, 1); PW = np.clip(v.sample(m['PW']), 0, 1); SL = v.sample(m['SL'])
    yr = Y - LY.river_y(X); a = np.abs(yr)
    wz = np.where(X < LY.FALL_X, LY.UPPER_WATER_Z, LY.WATER_Z)
    river = (a < LY.BANK_W) & (Z < wz + 1.5)
    marsh = (X > LY.MARSH_X0 - 200) & (Z < LY.WATER_Z + 1.5) & (a < 1300) & ~river
    od, _ = LY.seg_dist(X, Y, LY.OXBOW)
    oxbow = (od < LY.OXBOW_HW * 1.6) & (Z < LY.WATER_Z + 1.5)
    paddy = np.zeros(Z.shape, bool); dike = np.zeros(Z.shape, bool)
    for (x0, x1, yr0, yr1, cx, cy, up) in ((LY.PADDY_X0, LY.PADDY_X1, LY.PADDY_YR0, LY.PADDY_YR1, LY.PADDY_CELL_X, LY.PADDY_CELL_Y, -1),
                                         (LY.PADDY2_X0, LY.PADDY2_X1, LY.PADDY2_YR0, LY.PADDY2_YR1, LY.PADDY2_CELL_X, LY.PADDY2_CELL_Y, 1)):
        ph, inside, floor = LY.paddy_height(X, yr, x0, x1, yr0, yr1, cx, cy, up, 14.0 if up < 0 else 16.0)
        paddy |= inside & (ph < floor - 1.0); dike |= inside & (ph >= floor - 1.0)
    rd, hw = LY.road_dist(X, Y)
    kd = LY.karst_dist(X, Y)
    gy, gx = np.gradient(Z, v.upp)
    return dict(X=X, Y=Y, Z=Z, J=J, G=G, PW=PW, SL=SL, yr=yr, river=river, marsh=marsh, oxbow=oxbow, paddy=paddy, dike=dike,
                rd=rd, hw=hw, kd=kd, gx=gx, gy=-gy, water=river | marsh | oxbow)


def hillshade(F, az=315.0, alt=42.0, zf=1.6):
    """lambert shade 0..~1.3 with the light from compass azimuth az (315 = north-west, the map convention)"""
    a = math.radians(az); e = math.radians(alt)
    L = np.array([math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)])
    nx, ny = -F['gx'] * zf, -F['gy'] * zf
    n = np.sqrt(nx * nx + ny * ny + 1)
    return np.clip((nx * L[0] + ny * L[1] + L[2]) / n, 0, 1) / L[2]


def karst_outline(k, n=72):
    """fluted outline of a karst tower (world points) and its crown (the flat top)"""
    kx, ky, kr, kh, ks = k
    rng = np.random.RandomState(100 + ks)
    ph = rng.uniform(0, 6.28, 4)
    pts, top = [], []
    for i in range(n):
        t = 2 * math.pi * i / n
        r = kr * (0.90 + 0.07 * math.sin(3 * t + ph[0]) + 0.05 * math.sin(7 * t + ph[1]) + 0.03 * math.sin(13 * t + ph[2]))
        pts.append((kx + r * math.cos(t), ky + r * math.sin(t)))
        top.append((kx + r * 0.52 * math.cos(t), ky + r * 0.52 * math.sin(t)))
    return pts, top


def text_halo(d, xy, s, f, fill, halo=(0, 0, 0, 200), anchor='mm', w=2):
    d.text(xy, s, font=f, fill=fill, anchor=anchor, stroke_width=w, stroke_fill=halo)


def spaced(img, xy, s, f, fill, spacing=0.25, halo=(0, 0, 0, 170), rot=0, w=2):
    """letter-spaced text centred on xy (optionally rotated), composited on an RGBA image"""
    ws = [f.getlength(c) for c in s]; sp = f.size * spacing
    W = int(sum(ws) + sp * (len(s) - 1)) + 12; H = int(f.size * 1.6)
    t = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dt = ImageDraw.Draw(t)
    x = 6
    for c, cw in zip(s, ws):
        dt.text((x, H / 2), c, font=f, fill=fill, anchor='lm', stroke_width=w, stroke_fill=halo); x += cw + sp
    if rot: t = t.rotate(rot, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(t, (int(xy[0] - t.size[0] / 2), int(xy[1] - t.size[1] / 2)))


def village_huts():
    """stand-in hut footprints for the pictures (the real ones come from mv_places.py): (x, y, w, d, yaw)"""
    rng = np.random.RandomState(68); out = []
    c = LY.VILLAGE
    for k in range(9):
        a = 2 * math.pi * k / 9 + rng.uniform(-0.2, 0.2); r = rng.uniform(200, 480)
        out.append((c[0] + r * math.cos(a), c[1] + r * math.sin(a), rng.uniform(150, 210), rng.uniform(100, 130), rng.uniform(0, 180)))
    return out


def rect_pts(x, y, w, d, yaw):
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return [(x + c * a - s * b, y + s * a + c * b) for a, b in ((w / 2, d / 2), (-w / 2, d / 2), (-w / 2, -d / 2), (w / 2, -d / 2))]


# ================================================================ the "from the air" picture (radar)
def render_sat(v, ss=2, labels=True, grid=True, dim_outside=True, flag_badges=True, label_scale=1.0):
    """the valley as seen from above, painted for a minimap: returns an RGB image v.W x v.H"""
    V = View(v.x0, v.y0, v.upp / ss, v.W * ss, v.H * ss)
    F = fields(V)
    X, Y, Z, J, G, PW = F['X'], F['Y'], F['Z'], F['J'], F['G'], F['PW']
    n1 = fbm(X / 700.0, Y / 700.0, 0.4, 4, seed=21)[..., None]; n2 = fbm(X / 120.0, Y / 120.0, 1.7, 3, seed=22)[..., None]
    mud = np.array([0.43, 0.35, 0.25]); grassland = np.array([0.42, 0.49, 0.27]); egrass = np.array([0.60, 0.60, 0.33])
    rock = np.array([0.50, 0.49, 0.45]); floor = np.array([0.20, 0.27, 0.15])
    col = mud + (grassland - mud) * PW[..., None]
    col = col + (egrass - col) * (G[..., None] * 0.8)
    col = col + (floor - col) * (np.clip(J, 0, 1)[..., None] * 0.85)                       # the ground under the canopy
    rk = np.clip((F['SL'] - 30) / 18.0, 0, 1)[..., None] * (1 - J[..., None] * 0.7)
    col = col + (rock - col) * rk
    col = col * (0.92 + 0.10 * n1 + 0.07 * n2)
    # elephant grass stipple
    st = (fbm(X / 26.0, Y / 9.0, 3.1, 2, seed=23) > 0.25) & (G > 0.3)
    col[st] *= 0.9
    sh = hillshade(F, zf=2.2)
    img = col * (0.50 + 0.58 * sh[..., None])
    # contours: every 40 u faint, every 200 u stronger
    for step, k in ((40.0, 0.94), (200.0, 0.86)):
        gr_ = np.hypot(F['gx'], F['gy']) * V.upp + 1e-6
        c = np.abs((Z - 17.0) / step - np.round((Z - 17.0) / step)) * step / gr_
        img[(c < 0.55) & ~F['water'] & (F['kd'] > 40) & (gr_ > 0.02 * V.upp)] *= k
    # roads: the dirt band, lighter than the mud, with dark verges
    rd, hw = F['rd'], F['hw']
    road = np.clip((hw + V.upp - rd) / (V.upp * 1.5), 0, 1)[..., None] * (hw > 0)[..., None]
    wide = (hw > 50)[..., None]
    rc = np.where(wide, np.array([0.70, 0.60, 0.43]), np.array([0.60, 0.53, 0.38]))
    verge = np.clip(1 - np.abs(rd - hw - 12) / 14.0, 0, 1)[..., None] * 0.25
    img = img * (1 - verge)
    img = img + (rc * (0.9 + 0.1 * n2) - img) * road * np.where(wide, 0.95, 0.75)
    # water: muddy monsoon river, paddies as mirrors with dikes, the marsh pools
    deep = np.clip((np.where(X < LY.FALL_X, LY.UPPER_WATER_Z, LY.WATER_Z) - Z) / 30.0, 0, 1)[..., None]
    wcol = np.array([0.33, 0.44, 0.43]) * (1 - deep) + np.array([0.19, 0.31, 0.35]) * deep
    ripple = 1 + 0.07 * fbm(X / 160.0, (Y - LY.river_y(X)) / 30.0, 2.2, 3, seed=24)[..., None]
    wm = ndimage.gaussian_filter(F['water'].astype(np.float32), 0.8 * ss)[..., None]
    img = img * (1 - wm) + wcol * ripple * wm
    shore = (ndimage.binary_dilation(F['water'], iterations=ss) & ~F['water'])
    img[shore] = img[shore] * 0.55 + np.array([0.74, 0.69, 0.55]) * 0.45
    pm = F['paddy']
    img[pm] = np.array([0.36, 0.50, 0.45]) * (0.95 + 0.12 * n2[pm]) * 1.0
    rice = pm & (((X / 22.0).astype(int) + (F['yr'] / 22.0).astype(int)) % 2 == 0)
    img[rice] = img[rice] * 0.80 + np.array([0.45, 0.62, 0.25]) * 0.20
    img[F['dike']] = np.array([0.56, 0.50, 0.34]) * (0.9 + 0.1 * n2[F['dike']])
    # the fall: white water at the lip and in the pool
    fall = F['river'] & (np.abs(X - LY.FALL_X) < 70)
    img[fall] = (0.90, 0.93, 0.92)
    foam = F['river'] & (X > LY.FALL_X) & (X < LY.FALL_X + 320) & (fbm(X / 40.0, Y / 40.0, 1.3, 2, seed=25) > 0.05)
    img[foam] = img[foam] * 0.5 + 0.45
    canvas = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).convert('RGBA')
    M, Hh = V.W, V.H
    px, plen = V.px, V.plen

    # ---- built things under the canopy layer
    lay = Image.new('RGBA', (M, Hh), (0, 0, 0, 0)); dr = ImageDraw.Draw(lay)
    shadow = Image.new('L', (M, Hh), 0); dsh = ImageDraw.Draw(shadow)

    def poly(P, **kw): dr.polygon([px(*p) for p in P], **kw)

    def disc(x, y, r, **kw):
        c = px(x, y); rr = plen(r); dr.ellipse([c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr], **kw)

    def sh_poly(P, off=30.0, a=150): dsh.polygon([px(p[0] + off, p[1] - off) for p in P], fill=a)
    lw = max(1, int(round(ss)))
    # bridge: deck, truss shadows, the burnt truck
    bx, by = LY.BRIDGE_X, LY.BRIDGE_Y; hl = LY.BRIDGE_LEN / 2
    deck = [(bx - 62, by - hl), (bx + 62, by - hl), (bx + 62, by + hl), (bx - 62, by + hl)]
    sh_poly(deck, 46, 170)
    poly(deck, fill=(132, 126, 112, 255), outline=(40, 38, 34, 255), width=lw)
    for k in range(11):
        yy = by - hl + 2 * hl * k / 10
        dr.line([px(bx - 62, yy), px(bx + 62, yy)], fill=(64, 60, 54, 255), width=lw)
        if k < 10: dr.line([px(bx - 62, yy), px(bx + 62, yy + 2 * hl / 10)], fill=(84, 80, 72, 255), width=lw)
    poly(rect_pts(bx + 8, by + 40, 70, 150, 8), fill=(52, 46, 40, 255))
    poly(rect_pts(bx + 150, by - LY.BANK_W - 160, 150, 120, 0), fill=(150, 146, 136, 255), outline=(50, 48, 44, 255), width=lw)      # French bunker
    # village: thatch roofs with ridge lines
    for (hx, hy, w, d, yaw) in village_huts():
        P = rect_pts(hx, hy, w, d, yaw); sh_poly(P, 26, 150)
        poly(P, fill=(164, 138, 84, 255), outline=(70, 56, 34, 255), width=lw)
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        dr.line([px(hx - c * w / 2, hy - s * w / 2), px(hx + c * w / 2, hy + s * w / 2)], fill=(104, 84, 50, 255), width=lw)
    # temple: outer wall, galleries, the central tower
    tx, ty = LY.TEMPLE
    for sz, colr, wd in ((330, (128, 124, 112, 255), 3), (210, (150, 146, 132, 255), 2)):
        P = rect_pts(tx, ty, sz * 2, sz * 2, 0); dr.polygon([px(*p) for p in P], outline=colr, width=wd * lw)
    P = rect_pts(tx, ty, 150, 150, 45); sh_poly(P, 60, 190); poly(P, fill=(168, 162, 146, 255), outline=(60, 58, 52, 255), width=lw)
    P = rect_pts(tx, ty, 70, 70, 0); poly(P, fill=(196, 190, 172, 255))
    for a in range(4):
        gx_, gy_ = tx + 330 * math.cos(a * math.pi / 2), ty + 330 * math.sin(a * math.pi / 2)
        poly(rect_pts(gx_, gy_, 90, 90, 0), fill=(150, 146, 132, 255), outline=(60, 58, 52, 255), width=lw)
    # crash site: the C-123 hulk (fuselage, one wing, tail) and the skid scar
    cx, cy = LY.CRASH
    scar = [(cx - 700, cy + 160), (cx - 120, cy + 30)]
    dr.line([px(*scar[0]), px(*scar[1])], fill=(74, 60, 44, 200), width=int(plen(70)))
    for P, colr in ((rect_pts(cx + 40, cy, 620, 96, -12), (150, 152, 146, 255)), (rect_pts(cx + 90, cy + 190, 150, 380, -18), (140, 142, 136, 255)),
                    (rect_pts(cx - 250, cy + 56, 70, 250, -12), (132, 134, 128, 255)), (rect_pts(cx + 420, cy - 300, 330, 120, 40), (126, 128, 122, 255))):
        sh_poly(P, 30, 150); poly(P, fill=colr, outline=(40, 40, 38, 255), width=lw)
    # rubber plantation rows south of the crash site
    for r in range(7):
        for k in range(12):
            x_ = cx - 600 + k * 105; y_ = cy - 330 - r * 95
            if math.hypot(x_ - cx, y_ - cy) < LY.CRASH_R + 380: disc(x_, y_, 30, fill=(44, 82, 40, 255))
    # CT firebase
    fb = LY.firebase(); c = fb['centre']
    wire = [(c[0] + fb['wire_r'] * math.cos(t), c[1] + fb['wire_r'] * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 49)[:-1]]
    for r_, colr, wd in ((fb['wire_r'] + 18, (40, 38, 34, 255), 1), (fb['wire_r'], (196, 186, 150, 255), 2), (fb['wire_r'] - 20, (40, 38, 34, 255), 1)):
        P = [(c[0] + r_ * math.cos(t), c[1] + r_ * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 73)]
        dr.line([px(*p) for p in P], fill=colr, width=wd * lw)
    pr = fb.get('pit_r', 110.0)
    for g_ in fb['guns']:
        gx_, gy_ = g_[0], g_[1]
        disc(gx_, gy_, pr, fill=(186, 168, 128, 255), outline=(60, 52, 40, 255), width=lw); disc(gx_, gy_, pr - 26, fill=(96, 82, 62, 255))
        a = math.atan2(LY.T_BASE[1] - gy_, LY.T_BASE[0] - gx_)
        dr.line([px(gx_ - 30 * math.cos(a), gy_ - 30 * math.sin(a)), px(gx_ + 70 * math.cos(a), gy_ + 70 * math.sin(a))], fill=(34, 40, 30, 255), width=max(2, int(plen(14))))
    ps = 600.0 * fb.get('pad_scale', 0.5)
    for i_, q_ in enumerate(fb['pads']):
        qx, qy = q_[0], q_[1]
        P = rect_pts(qx, qy, ps, ps, fb.get('pad_angles', [0, 0, 0, 0])[i_ % 4]); poly(P, fill=(120, 116, 104, 255), outline=(60, 58, 52, 255), width=lw)
        f = font(plen(ps * 0.6)); dr.text(px(qx, qy), 'H', font=f, fill=(226, 220, 196, 255), anchor='mm')
    for i, b_ in enumerate(fb['bunkers']):
        bx_, by_ = b_[0], b_[1]
        P = rect_pts(bx_, by_, 120, 90, math.degrees(math.atan2(by_ - c[1], bx_ - c[0])) + 90); sh_poly(P, 18, 150)
        poly(P, fill=(150, 132, 96, 255), outline=(60, 50, 36, 255), width=lw)
    for P, colr in ((rect_pts(fb['fdc'][0], fb['fdc'][1], 170, 120, 0), (140, 124, 92, 255)), (rect_pts(fb['toc'][0], fb['toc'][1], 190, 130, 30), (116, 122, 96, 255)),
                    (rect_pts(fb['ammo'][0], fb['ammo'][1], 110, 90, 0), (130, 114, 84, 255))) + tuple((rect_pts(t[0], t[1], 200, 110, 0), (112, 118, 88, 255)) for t in fb['tents']):
        sh_poly(P, 20, 150); poly(P, fill=colr, outline=(50, 46, 36, 255), width=lw)
    for key in ('tower', 'quad50'):
        if key in fb: disc(fb[key][0], fb[key][1], 50, fill=(110, 96, 70, 255), outline=(40, 34, 26, 255), width=lw)
    if hasattr(LY, 'FARM'):
        for k_ in range(4):
            P = rect_pts(LY.FARM[0] + (k_ % 2) * 230 - 115, LY.FARM[1] + (k_ // 2) * 190 - 95, 170, 110, 20 + 50 * k_); sh_poly(P, 24, 150)
            poly(P, fill=(164, 138, 84, 255), outline=(70, 56, 34, 255), width=lw)
    # T camp: rocket pits, pads under netting, hooches
    cp = LY.camp(); c2 = cp['centre']
    for g_ in cp['rockets']:
        gx_, gy_ = g_[0], g_[1]
        disc(gx_, gy_, cp.get('pit_r', 74.0), fill=(112, 96, 68, 255), outline=(60, 50, 36, 255), width=lw)
        a = math.atan2(LY.CT_BASE[1] - gy_, LY.CT_BASE[0] - gx_)
        dr.line([px(gx_ - 40 * math.cos(a), gy_ - 40 * math.sin(a)), px(gx_ + 60 * math.cos(a), gy_ + 60 * math.sin(a))], fill=(40, 44, 34, 255), width=max(2, int(plen(10))))
    for q_ in cp['pads']:
        qx, qy = q_[0], q_[1]
        disc(qx, qy, 300, fill=(104, 92, 66, 255), outline=(66, 76, 46, 255), width=lw)
        for k in range(-7, 8):                                # camouflage netting hatch
            hw_ = math.sqrt(max(300.0 ** 2 - (k * 40.0) ** 2, 0.0))
            dr.line([px(qx - hw_, qy + k * 40), px(qx + hw_, qy + k * 40)], fill=(70, 90, 50, 200), width=lw)
            dr.line([px(qx + k * 40, qy - hw_), px(qx + k * 40, qy + hw_)], fill=(70, 90, 50, 200), width=lw)
    for h_ in cp['hooches']:
        hx, hy = h_[0], h_[1]
        P = rect_pts(hx, hy, 190, 120, h_[2] if len(h_) > 2 else (hx * 7 + hy) % 180); sh_poly(P, 22, 140); poly(P, fill=(150, 128, 80, 255), outline=(70, 56, 34, 255), width=lw)
    for a_ in cp['aa']:
        ax_, ay_ = a_[0], a_[1]
        disc(ax_, ay_, 70, fill=(120, 104, 74, 255), outline=(50, 44, 32, 255), width=lw)
    for t_ in LY.TUNNEL_PORTALS:
        tx_, ty_ = t_[0], t_[1]
        c_ = px(tx_, ty_); r = plen(46)
        dr.pieslice([c_[0] - r, c_[1] - r, c_[0] + r, c_[1] + r], 180, 360, fill=(24, 18, 12, 255), outline=(206, 186, 140, 255), width=lw)
    for g_ in LY.mounted_guns():
        mx, my = g_[2][0], g_[2][1]
        disc(mx, my, 44, fill=(186, 168, 128, 255), outline=(50, 44, 32, 255), width=lw)
    # craters
    for (qx, qy, r, dep) in LY.CRATERS:
        disc(qx, qy, r * 0.8, fill=(70, 56, 40, 120)); disc(qx + r * 0.1, qy - r * 0.1, r * 0.45, fill=(52, 42, 30, 140))

    # ---- canopy: one crown per tree, drawn over the ground with soft shadows
    crowns = Image.new('RGBA', (M, Hh), (0, 0, 0, 0)); dc = ImageDraw.Draw(crowns)
    rng = np.random.RandomState(1968)
    sp = 104.0
    gx0 = math.floor(V.x0 / sp) * sp; gy1 = math.ceil(V.y0 / sp) * sp
    nx = int(V.W * V.upp / sp) + 3; ny = int(V.H * V.upp / sp) + 3
    cxs = gx0 + (np.arange(nx)[None, :] + rng.uniform(0.1, 0.9, (ny, nx))) * sp
    cys = gy1 - (np.arange(ny)[:, None] + rng.uniform(0.1, 0.9, (ny, nx))) * sp
    m = master()
    jn = m['J'].shape[0]
    jc = ndimage.map_coordinates(m['J'], [(EXT - cys) / (2 * EXT) * jn - 0.5, (cxs + EXT) / (2 * EXT) * jn - 0.5], order=1, mode='nearest')
    keep = rng.uniform(0, 1, jc.shape) < np.clip(jc * 1.25, 0, 1) ** 0.8
    rad = rng.uniform(54, 96, jc.shape) * (0.8 + 0.35 * jc); tone = rng.uniform(0.82, 1.18, jc.shape)
    trees = sorted(zip(cxs[keep], cys[keep], rad[keep], tone[keep]), key=lambda t: -t[2])
    for (x, y, r, tn) in trees:
        p = px(x + r * 0.45, y - r * 0.45); rr = plen(r)
        dsh.ellipse([p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr], fill=150)
    for (x, y, r, tn) in trees:
        p = px(x, y); rr = plen(r)
        b = np.array([38, 74, 34]) * tn
        for k, f_ in enumerate((1.0, 0.70, 0.38)):
            cc = np.clip(b * (1 + 0.24 * k), 0, 255).astype(int); off = rr * 0.20 * k
            dc.ellipse([p[0] - rr * f_ - off, p[1] - rr * f_ - off, p[0] + rr * f_ - off, p[1] + rr * f_ - off], fill=(int(cc[0]), int(cc[1]), int(cc[2]), 255))
    # palms along the river
    for xw in np.arange(V.x0 + 60, V.x0 + V.W * V.upp, 170.0):
        for side in (-1, 1):
            if rng.rand() < 0.55 and abs(xw - LY.BRIDGE_X) > 300 and LY.FALL_X + 200 < xw < LY.MARSH_X0:
                yy = float(LY.river_y(xw)) + side * (LY.BANK_W + rng.uniform(20, 90)); p = px(xw + rng.uniform(-50, 50), yy); rr = plen(34)
                for k in range(6):
                    a = k * math.pi / 3 + xw
                    dc.line([p, (p[0] + rr * math.cos(a), p[1] + rr * math.sin(a))], fill=(64, 110, 48, 255), width=max(2, int(plen(12))))

    # ---- karst towers: long shadows, fluted cliff ring, lit crown
    kl = Image.new('RGBA', (M, Hh), (0, 0, 0, 0)); dk = ImageDraw.Draw(kl)
    for k in LY.KARST:
        pts, top = karst_outline(k)
        L = k[3] * 0.42                                        # shadow length: the towers are tall
        hull = [px(p[0] + L * t, p[1] - L * t) for t in (0, 0.5, 1.0) for p in (pts if t < 1 else top)]
        for t in np.linspace(0, 1, 12):
            f_ = 1 - 0.48 * t
            dsh.polygon([px(k[0] + (p[0] - k[0]) * f_ + L * t, k[1] + (p[1] - k[1]) * f_ - L * t) for p in pts], fill=205)
    for k in LY.KARST:
        pts, top = karst_outline(k)
        dk.polygon([px(*p) for p in pts], fill=(96, 98, 92, 255), outline=(30, 32, 30, 255), width=lw)
        n = len(pts)
        for i in range(n):                                     # cliff faces: lit north-west, dark south-east
            a = 2 * math.pi * i / n
            lit = 0.5 + 0.5 * math.cos(a - math.radians(135))
            g = int(70 + 110 * lit)
            dk.polygon([px(*pts[i]), px(*pts[(i + 1) % n]), px(*top[(i + 1) % n]), px(*top[i])], fill=(g, g, int(g * 0.94), 255))
            if i % 3 == 0: dk.line([px(*pts[i]), px(*top[i])], fill=(40, 42, 40, 150), width=lw)
        land = k[4] in LY.KARST_LANDABLE
        dk.polygon([px(*p) for p in top], fill=(86, 122, 66, 255) if land else (120, 128, 104, 255), outline=(34, 44, 30, 255), width=lw)
        rr = np.random.RandomState(300 + k[4])
        for _ in range(9):                                     # scrub on the crown
            a, r_ = rr.uniform(0, 6.28), rr.uniform(0, k[2] * 0.36); c_ = px(k[0] + r_ * math.cos(a), k[1] + r_ * math.sin(a)); q = plen(rr.uniform(22, 44))
            dk.ellipse([c_[0] - q, c_[1] - q, c_[0] + q, c_[1] + q], fill=(54, 96, 46, 255))

    shadow = shadow.filter(ImageFilter.GaussianBlur(plen(22)))
    g = np.asarray(canvas, np.float32)
    g[..., :3] *= (1 - 0.50 * (np.asarray(shadow, np.float32) / 255.0)[..., None])
    out = Image.fromarray(g.clip(0, 255).astype(np.uint8))
    out = Image.alpha_composite(out, lay)
    cr = np.asarray(crowns, np.float32)                       # the canopy takes the hill shading too, so the valley sides read
    cr[..., :3] *= (0.62 + 0.46 * np.clip(sh, 0, 1.3))[..., None]
    out = Image.alpha_composite(out, Image.fromarray(cr.clip(0, 255).astype(np.uint8)))
    # tower shadows fall over the canopy too
    ks = Image.new('L', (M, Hh), 0); dks = ImageDraw.Draw(ks)
    for k in LY.KARST:
        pts, top = karst_outline(k); L = k[3] * 0.42
        for t in np.linspace(0, 1, 12):
            f_ = 1 - 0.48 * t
            dks.polygon([px(k[0] + (p[0] - k[0]) * f_ + L * t, k[1] + (p[1] - k[1]) * f_ - L * t) for p in pts], fill=255)
    ks = ks.filter(ImageFilter.GaussianBlur(plen(16)))
    o = np.asarray(out, np.float32); o[..., :3] *= (1 - 0.42 * (np.asarray(ks, np.float32) / 255.0)[..., None])
    out = Image.alpha_composite(Image.fromarray(o.clip(0, 255).astype(np.uint8)), kl)

    # ---- the play space is bright, the valley sides beyond it dimmed
    if dim_outside:
        o = np.asarray(out, np.float32)[..., :3]
        e = np.maximum(np.abs(X) - LY.MAP_X, np.abs(Y) - LY.MAP_Y)
        pm_ = np.clip(-e / 160.0, 0, 1)[..., None]
        lum = o.mean(-1, keepdims=True)
        dim = (o * 0.55 + lum * 0.45) * 0.58
        o = o * pm_ + dim * (1 - pm_)
        out = Image.fromarray(o.clip(0, 255).astype(np.uint8)).convert('RGBA')
        dr = ImageDraw.Draw(out)
        P = [px(-LY.MAP_X, LY.MAP_Y), px(LY.MAP_X, LY.MAP_Y), px(LY.MAP_X, -LY.MAP_Y), px(-LY.MAP_X, -LY.MAP_Y)]
        for a_, b_ in zip(P, P[1:] + P[:1]):
            n = max(1, int(math.hypot(b_[0] - a_[0], b_[1] - a_[1]) / (14 * ss)))
            for k in range(0, n, 2):
                dr.line([(a_[0] + (b_[0] - a_[0]) * k / n, a_[1] + (b_[1] - a_[1]) * k / n), (a_[0] + (b_[0] - a_[0]) * (k + 1) / n, a_[1] + (b_[1] - a_[1]) * (k + 1) / n)],
                        fill=(226, 214, 176, 150), width=lw)
    clean = out.copy()
    ov = Image.new('RGBA', (M, Hh), (0, 0, 0, 0)); dr = ImageDraw.Draw(ov)
    ink = (236, 226, 192)
    # base tints: a soft team-coloured ring so each side's ground reads at a glance
    for cen, r_, colr in ((LY.CT_BASE, LY.CT_PLATEAU_R + 60, CT_COL), (LY.T_BASE, LY.T_PLATEAU_R + 60, T_COL)):
        c_ = px(*cen); rr = plen(r_)
        dr.ellipse([c_[0] - rr, c_[1] - rr, c_[0] + rr, c_[1] + rr], outline=colr + (230,), width=3 * lw)
    if flag_badges:
        for l, name, (fx, fy) in LY.FLAGS:
            c_ = px(fx, fy); rr = plen(LY.FLAG_R)
            for k in range(0, 36, 2):                         # dashed capture radius
                dr.arc([c_[0] - rr, c_[1] - rr, c_[0] + rr, c_[1] + rr], k * 10, k * 10 + 10, fill=(255, 255, 255, 210), width=2 * lw)
            q = 13 * ss * label_scale
            dr.ellipse([c_[0] - q, c_[1] - q, c_[0] + q, c_[1] + q], fill=(24, 26, 22, 235), outline=(255, 255, 255, 255), width=2 * lw)
            dr.text((c_[0], c_[1] + ss * 0.5), l.upper(), font=font(17 * ss * label_scale), fill=(255, 255, 255, 255), anchor='mm')
    out = Image.alpha_composite(out, ov)
    if labels:
        fs = lambda s_: font(s_ * ss * label_scale)
        for l, name, (fx, fy) in LY.FLAGS:
            dy = -LY.FLAG_R - 150 if l in ('a', 'e') else LY.FLAG_R + 150
            spaced(out, px(fx, fy + dy), name.upper(), fs(12), ink + (235,), 0.14, w=ss)
        spaced(out, px(LY.CT_BASE[0], LY.CT_BASE[1] - LY.CT_PLATEAU_R - 190), 'FIREBASE', fs(14), CT_COL + (255,), 0.22, w=ss)
        spaced(out, px(LY.T_BASE[0], LY.T_BASE[1] + LY.T_PLATEAU_R + 210), 'CAMP', fs(14), T_COL + (255,), 0.22, w=ss)
        xr = 3650.0; sl_ = math.degrees(math.atan(float(LY.river_dir(xr)[1] / LY.river_dir(xr)[0])))
        spaced(out, px(xr, float(LY.river_y(xr))), 'S O N G   M U A', font(10 * ss * label_scale, serif=True), (196, 226, 232, 215), 0.2, rot=sl_, w=ss)
        spaced(out, px(LY.FALL_X + 330, float(LY.river_y(LY.FALL_X)) + 420), 'FALLS', fs(10), ink + (200,), 0.2, w=ss)
        spaced(out, px(5650, float(LY.river_y(5650)) - 560), 'MARSH', fs(10), ink + (200,), 0.2, w=ss)
        for k in LY.KARST:
            if k[4] in LY.KARST_LANDABLE: spaced(out, px(k[0], k[1] - k[2] - 110), 'LZ %d' % (LY.gz(k[0], k[1]) + k[3]), fs(9), ink + (210,), 0.1, w=ss)
    if grid:
        dr = ImageDraw.Draw(out)
        fG = font(11 * ss * label_scale)
        for k in range(17):
            wx = -EXT + 2 * EXT * k / 16
            a_, b_ = px(wx, EXT), px(wx, -EXT); dr.line([a_, b_], fill=ink + (50,), width=1)
            a_, b_ = px(-EXT, wx), px(EXT, wx); dr.line([a_, b_], fill=ink + (50,), width=1)
        for k in range(16):
            wx = -EXT + 2 * EXT * (k + 0.5) / 16
            c_ = px(wx, EXT); dr.text((c_[0], max(c_[1], 0) + 9 * ss), chr(65 + k), font=fG, fill=ink + (190,), anchor='mm', stroke_width=ss, stroke_fill=(0, 0, 0, 150))
            c_ = px(-EXT, -wx); dr.text((max(c_[0], 0) + 9 * ss, c_[1]), str(k + 1), font=fG, fill=ink + (190,), anchor='mm', stroke_width=ss, stroke_fill=(0, 0, 0, 150))
    return finish(out, v, ss), finish(clean, v, ss)


def finish(img, v, ss, vignette=0.30):
    o = np.asarray(img.convert('RGB'), np.float32)
    h, w = o.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    r2 = ((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2
    o *= np.clip(1.05 - vignette * r2 * 0.6, 0.6, 1.05)[..., None]
    grain = ndimage.gaussian_filter(np.random.RandomState(9).rand(h // 2 + 1, w // 2 + 1), 0.8)
    grain = np.kron(grain, np.ones((2, 2)))[:h, :w] - 0.5
    o *= (1 + 0.10 * grain)[..., None]
    return Image.fromarray(o.clip(0, 255).astype(np.uint8)).resize((v.W, v.H), Image.LANCZOS)


# ================================================================ the printed map (artillery board, loading slides)
PAPER = np.array([0.905, 0.875, 0.770])


def render_topo(v, ss=2, grid=True, labels=True, flags=True, bases=True, label_scale=1.0, grid_labels=True, age=1.0):
    """a 1:25 000-style printed tactical map: paper, green vegetation tint, blue water, brown contours, red roads, black grid.
    Returns an RGB image v.W x v.H."""
    V = View(v.x0, v.y0, v.upp / ss, v.W * ss, v.H * ss)
    F = fields(V)
    X, Y, Z, J, G = F['X'], F['Y'], F['Z'], F['J'], F['G']
    M, Hh = V.W, V.H; px, plen = V.px, V.plen
    lw = max(1, int(round(ss * label_scale)))
    img = np.empty((Hh, M, 3)); img[:] = PAPER
    veg = np.array([0.69, 0.80, 0.58]); eg = np.array([0.86, 0.86, 0.62])
    js = ndimage.gaussian_filter(J, 1.5 * ss)
    img = img + (veg - img) * np.clip(js * 1.3, 0, 1)[..., None]
    img = img + (eg - img) * (np.clip(G * 1.2, 0, 1) * (1 - js))[..., None] * 0.8
    # jungle symbol stipple: small rings on a jittered grid, sparse
    sh = hillshade(F, zf=2.6)
    img *= (0.80 + 0.22 * np.clip(sh, 0, 1.25))[..., None]
    grad = np.hypot(F['gx'], F['gy']) * V.upp + 1e-6
    brown = np.array([0.62, 0.40, 0.22])
    dry = ~F['water'] & ~F['paddy'] & (F['kd'] > 0)
    for step, wd, a in ((50.0, 0.55, 0.50), (250.0, 1.05, 0.85)):
        zc = Z - 17.0                                          # off the round plateau heights (a flat at z 300 would fill solid)
        c = np.abs(zc / step - np.round(zc / step)) * step / grad
        m = np.clip((wd * ss - c) / 1.0, 0, 1) * dry * a * (grad > 0.02 * V.upp)
        img = img + (brown - img) * m[..., None]
    # water
    blue = np.array([0.62, 0.79, 0.88]); dblue = np.array([0.20, 0.40, 0.62])
    wm = ndimage.gaussian_filter(F['water'].astype(np.float32), 0.6 * ss)[..., None]
    img = img * (1 - wm) + blue * wm
    edge = ndimage.binary_dilation(F['water'], iterations=max(1, ss)) & ~ndimage.binary_erosion(F['water'], iterations=max(1, ss // 2))
    img[edge] = dblue
    mhatch = F['marsh'] & ((np.floor(Y / (36.0)) % 2) == 0)
    img[mhatch] = img[mhatch] * 0.6 + dblue * 0.4
    pd = F['paddy']
    img[pd] = np.array([0.74, 0.86, 0.84])
    ph = pd & ((np.floor((X + F['yr']) / 30.0) % 3) == 0)
    img[ph] = np.array([0.42, 0.62, 0.70])
    img[F['dike']] = np.array([0.50, 0.42, 0.30])
    fall = F['river'] & (np.abs(X - LY.FALL_X) < 40)
    img[fall] = dblue
    canvas = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).convert('RGBA')
    dr = ImageDraw.Draw(canvas)
    ink = (38, 34, 30, 255); red = (176, 52, 36, 255)
    # roads: red cased line; trails: dashed black
    for hw, pts in LY.ROADS:
        P = [px(*p) for p in pts]
        if hw > 50:
            dr.line(P, fill=ink, width=int(plen(hw * 2) + 4 * lw), joint='curve'); dr.line(P, fill=(214, 110, 70, 255), width=max(2, int(plen(hw * 2))), joint='curve')
        else:
            for a_, b_ in zip(pts[:-1], pts[1:]):
                L = math.hypot(b_[0] - a_[0], b_[1] - a_[1]); n = max(1, int(L / 90))
                for k in range(0, n, 2):
                    dr.line([px(a_[0] + (b_[0] - a_[0]) * k / n, a_[1] + (b_[1] - a_[1]) * k / n), px(a_[0] + (b_[0] - a_[0]) * (k + 1) / n, a_[1] + (b_[1] - a_[1]) * (k + 1) / n)],
                            fill=ink, width=2 * lw)
    # bridge
    bx, by = LY.BRIDGE_X, LY.BRIDGE_Y; hl = LY.BRIDGE_LEN / 2
    for s_ in (-1, 1):
        dr.line([px(bx + s_ * 95, by - hl - 60), px(bx + s_ * 70, by - hl), px(bx + s_ * 70, by + hl), px(bx + s_ * 95, by + hl + 60)], fill=ink, width=2 * lw)
    # karst: hachured rock with a spot height
    for k in LY.KARST:
        pts, top = karst_outline(k)
        dr.polygon([px(*p) for p in pts], fill=(196, 172, 140, 255), outline=ink, width=2 * lw)
        for i in range(0, len(pts), 2):
            dr.line([px(*pts[i]), px(*top[i])], fill=(104, 70, 44, 255), width=lw)
        dr.polygon([px(*p) for p in top], fill=(226, 208, 176, 255), outline=(104, 70, 44, 255), width=lw)
        if labels:
            dr.text(px(k[0], k[1]), '%d' % round((LY.gz(k[0], k[1]) + k[3]) / 10), font=font(9.5 * ss * label_scale), fill=ink, anchor='mm')
    # buildings as black squares
    for (hx, hy, w, d, yaw) in village_huts(): dr.polygon([px(*p) for p in rect_pts(hx, hy, max(w, 150), max(d, 120), yaw)], fill=ink)
    tx, ty = LY.TEMPLE
    dr.polygon([px(*p) for p in rect_pts(tx, ty, 520, 520, 0)], outline=ink, width=2 * lw); dr.polygon([px(*p) for p in rect_pts(tx, ty, 170, 170, 45)], fill=ink)
    cx, cy = LY.CRASH
    dr.polygon([px(*p) for p in rect_pts(cx + 40, cy, 620, 90, -12)], fill=ink); dr.polygon([px(*p) for p in rect_pts(cx + 90, cy + 60, 130, 560, -12)], fill=ink)
    if bases:
        fb = LY.firebase(); c = fb['centre']; cp = LY.camp(); c2 = cp['centre']
        blue_i = (30, 70, 150, 255)
        for r_, wd in ((fb['wire_r'], 2),):
            c_ = px(*c); rr = plen(r_)
            for k in range(0, 72, 2): dr.arc([c_[0] - rr, c_[1] - rr, c_[0] + rr, c_[1] + rr], k * 5, k * 5 + 6, fill=blue_i, width=3 * lw)
        for g_ in fb['guns']:
            c_ = px(g_[0], g_[1]); q = plen(fb.get('pit_r', 110.0) * 0.6) + 2 * lw
            dr.ellipse([c_[0] - q, c_[1] - q, c_[0] + q, c_[1] + q], outline=blue_i, width=2 * lw); dr.ellipse([c_[0] - 2 * lw, c_[1] - 2 * lw, c_[0] + 2 * lw, c_[1] + 2 * lw], fill=blue_i)
        for q_ in fb['pads']:
            dr.polygon([px(*p) for p in rect_pts(q_[0], q_[1], 300, 300, 0)], outline=blue_i, width=2 * lw)
        c_ = px(*c2); rr = plen(LY.T_PLATEAU_R)
        for k in range(0, 72, 2): dr.arc([c_[0] - rr, c_[1] - rr, c_[0] + rr, c_[1] + rr], k * 5, k * 5 + 6, fill=red, width=3 * lw)
        for g_ in cp['rockets']:
            c_ = px(g_[0], g_[1]); q = plen(70) + 2 * lw
            dr.polygon([(c_[0], c_[1] - q), (c_[0] + q, c_[1]), (c_[0], c_[1] + q), (c_[0] - q, c_[1])], outline=red, width=2 * lw)
        for q_ in cp['pads']:
            c_ = px(q_[0], q_[1]); q = plen(180); dr.ellipse([c_[0] - q, c_[1] - q, c_[0] + q, c_[1] + q], outline=red, width=2 * lw)
    out = canvas
    if grid:
        dr = ImageDraw.Draw(out)
        for k in range(17):
            wx = -EXT + 2 * EXT * k / 16
            gw = max(1, lw // 2)
            dr.line([px(wx, EXT), px(wx, -EXT)], fill=(30, 30, 30, 105), width=gw); dr.line([px(-EXT, wx), px(EXT, wx)], fill=(30, 30, 30, 105), width=gw)
        if grid_labels:
            fG = font(11 * ss * label_scale)
            for k in range(16):
                wx = -EXT + 2 * EXT * (k + 0.5) / 16
                c_ = px(wx, EXT); dr.text((c_[0], max(c_[1], 0) + 9 * ss * label_scale), chr(65 + k), font=fG, fill=ink, anchor='mm', stroke_width=2 * ss, stroke_fill=(232, 224, 198, 255))
                c_ = px(-EXT, -wx); dr.text((max(c_[0], 0) + 10 * ss * label_scale, c_[1]), str(k + 1), font=fG, fill=ink, anchor='mm', stroke_width=2 * ss, stroke_fill=(232, 224, 198, 255))
    if flags:
        dr = ImageDraw.Draw(out)
        for l, name, (fx, fy) in LY.FLAGS:
            c_ = px(fx, fy); rr = plen(LY.FLAG_R)
            dr.ellipse([c_[0] - rr, c_[1] - rr, c_[0] + rr, c_[1] + rr], outline=(20, 20, 20, 255), width=2 * lw)
            q = 11 * ss * label_scale
            dr.ellipse([c_[0] - q, c_[1] - q, c_[0] + q, c_[1] + q], fill=(246, 238, 210, 255), outline=(20, 20, 20, 255), width=2 * lw)
            dr.text((c_[0], c_[1] + ss * 0.5), l.upper(), font=font(15 * ss * label_scale), fill=(20, 20, 20, 255), anchor='mm')
    if labels:
        halo = (232, 224, 198, 235); fs = lambda s_: font(s_ * ss * label_scale)
        for l, name, (fx, fy) in LY.FLAGS:
            dy = -LY.FLAG_R - 170 if l in ('a', 'e') else LY.FLAG_R + 170
            spaced(out, px(fx, fy + dy), name.upper(), fs(11.5), ink, 0.12, halo=halo, w=2 * ss)
        if bases:
            spaced(out, px(LY.CT_BASE[0], LY.CT_BASE[1] - LY.CT_PLATEAU_R - 200), 'FSB', fs(13), (30, 70, 150, 255), 0.2, halo=halo, w=2 * ss)
            spaced(out, px(LY.T_BASE[0], LY.T_BASE[1] + LY.T_PLATEAU_R + 220), 'CAMP', fs(13), red, 0.2, halo=halo, w=2 * ss)
        xr = 3650.0; sl_ = math.degrees(math.atan(float(LY.river_dir(xr)[1] / LY.river_dir(xr)[0])))
        spaced(out, px(xr, float(LY.river_y(xr))), 'S O N G   M U A', font(10 * ss * label_scale, serif=True), (24, 60, 120, 255), 0.2, halo=(0, 0, 0, 0), rot=sl_, w=0)
    # paper: fibres, fold lines, foxing at the edges
    o = np.asarray(out.convert('RGB'), np.float32) / 255.0
    yy, xx = np.mgrid[0:Hh, 0:M]
    fib = fbm(xx / (90.0 * ss), yy / (14.0 * ss), 0.3, 3, seed=71) * 0.035 + fbm(xx / (9.0 * ss), yy / (9.0 * ss), 1.3, 2, seed=72) * 0.03
    o *= (1 + fib * age)[..., None]
    for fx_ in (M / 3.0, 2 * M / 3.0):
        o *= (1 - 0.10 * age * np.exp(-((xx - fx_) / (1.6 * ss)) ** 2))[..., None]
    o *= (1 - 0.10 * age * np.exp(-((yy - Hh / 2.0) / (1.6 * ss)) ** 2))[..., None]
    r2 = ((xx - M / 2) / (M / 2)) ** 2 + ((yy - Hh / 2) / (Hh / 2)) ** 2
    o *= (1 - 0.16 * age * np.clip(r2 - 0.55, 0, 1))[..., None]
    o[..., 2] *= 1 - 0.05 * age * np.clip(r2, 0, 1)
    return Image.fromarray((o.clip(0, 1) * 255).astype(np.uint8)).resize((v.W, v.H), Image.LANCZOS)


VTEX = '''<!-- dmx encoding keyvalues2_noids 1 format vtex 1 -->
"CDmeVtex"
{
    "m_inputTextureArray" "element_array"
    [
        "CDmeInputTexture"
        {
            "m_name" "string" "SheetTexture"
            "m_fileName" "string" "panorama/images/overheadmaps/%(map)s_radar_psd.png"
            "m_colorSpace" "string" "srgb"
            "m_typeString" "string" "2D"
            "m_imageProcessorArray" "element_array"
            [
            ]
        }
    ]
    "m_outputTypeString" "string" "2D"
    "m_outputFormat" "string" "BC7"
    "m_outputClearColor" "vector4" "0 0 0 0"
    "m_nOutputMinDimension" "int" "0"
    "m_nOutputMaxDimension" "int" "1024"
    "m_textureOutputChannelArray" "element_array"
    [
        "CDmeTextureOutputChannel"
        {
            "m_inputTextureArray" "string_array"
            [
                "SheetTexture"
            ]
            "m_srcChannels" "string" "rgba"
            "m_dstChannels" "string" "rgba"
            "m_mipAlgorithm" "CDmeImageProcessor"
            {
                "m_algorithm" "string" ""
                "m_stringArg" "string" ""
                "m_vFloat4Arg" "vector4" "0 0 0 0"
            }
            "m_outputColorSpace" "string" "srgb"
        }
    ]
    "m_vClamp" "vector3" "0 0 0"
    "m_bNoLod" "bool" "1"
}
'''


def main(argv):
    out = argv[0] if len(argv) > 0 else os.path.join(HERE, '..', 'out', 'addon')
    game = argv[1] if len(argv) > 1 else os.path.join(HERE, '..', 'out', 'game')
    v = View(X0, Y0, SCALE, OUT_N, OUT_N)
    final, clean = render_sat(v, ss=2)
    dst = os.path.join(out, 'panorama/images/overheadmaps'); os.makedirs(dst, exist_ok=True)
    final.save(os.path.join(dst, MAP + '_radar_psd.png'), optimize=True)
    open(os.path.join(dst, MAP + '_radar_psd.vtex'), 'w', newline='\n').write(VTEX % dict(map=MAP))
    od = os.path.join(HERE, '..', 'out')
    clean.save(os.path.join(od, 'radar_clean.png')); final.save(os.path.join(od, 'radar_preview.png'))

    def frac(x, y): return (x - X0) / (2 * EXT), (Y0 - y) / (2 * EXT)
    ctx, cty = frac(*LY.CT_BASE); tx, ty = frac(*LY.T_BASE)
    os.makedirs(os.path.join(game, 'resource/overviews'), exist_ok=True)
    open(os.path.join(game, 'resource/overviews/%s.txt' % MAP), 'w', newline='\n').write('''// Overview (radar) for %s (tools/make_radar.py)
"%s"
{
	"material"	"overviews/%s_radar"	// texture file
	"pos_x"		"%d"	// upper left world coordinate
	"pos_y"		"%d"
	"scale"		"%.2f"
	"rotate"	"0"
	"zoom"		"1.0"

	// loading screen icons and positions
	"CTSpawn_x"	"%.2f"
	"CTSpawn_y"	"%.2f"
	"TSpawn_x"	"%.2f"
	"TSpawn_y"	"%.2f"
}
''' % (MAP, MAP, MAP, X0, Y0, SCALE, ctx, cty, tx, ty))
    json.dump(dict(x0=X0, y0=Y0, span=2 * EXT, scale=SCALE, size=OUT_N, grid=16), open(os.path.join(od, 'radar_region.json'), 'w'))
    # self-check: the flags must land where the overview says they are
    for l, name, (fx, fy) in LY.FLAGS:
        u, w_ = (fx - X0) / SCALE, (Y0 - fy) / SCALE
        assert 0 <= u < OUT_N and 0 <= w_ < OUT_N, 'flag %s is off the radar' % l
    print('radar: %s (pos %d %d, scale %.2f, %d px) + overview -> %s' % (dst, X0, Y0, SCALE, OUT_N, game))


if __name__ == '__main__':
    main(sys.argv[1:])
