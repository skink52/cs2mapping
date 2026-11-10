"""IRONFRAME loading slides and Workshop icon: dark military terminal, cyan / blue / purple with magenta accents, angular frames.
slides(title) -> four 1920x1080 PIL images (title, controls, modes, tips); workshop_icon() -> 1024x1024; credits(map, title) -> the
<map>.txt text (COMMUNITYMAPCREDITS) and description(...). Mech pictures are rendered with tools/mech_render.py (textured, perspective,
low three-quarter camera) and cached in preview/loading/. Fonts: Bahnschrift, Agency FB, Segoe UI (all ship with Windows).
tools/loading.py calls this; python -I tools/loading_art.py <outdir> writes slide_1..4.png + workshop_icon.jpg for a look."""
import math, os, sys, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops, ImageOps
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
CACHE = os.path.join(PROJ, 'preview', 'loading')
W, H = 1920, 1080
CY = (70, 220, 255); BL = (70, 120, 255); PU = (150, 80, 255); MG = (255, 60, 190); OR = (255, 150, 70); WH = (235, 246, 255)
FD = 'C:/Windows/Fonts/'

_f = {}
def font(name, sz, var=None):
    k = (name, sz, var)
    if k not in _f:
        path = {'bahn': 'bahnschrift.ttf', 'agency': 'AGENCYB.TTF', 'agencyr': 'AGENCYR.TTF', 'segoe': 'segoeuib.ttf', 'segoer': 'segoeui.ttf', 'mono': 'consolab.ttf'}[name]
        f = ImageFont.truetype(FD + path, sz)
        if var:
            try: f.set_variation_by_name(var)
            except Exception: pass
        _f[k] = f
    return _f[k]


def tw(txt, f, track=0): return sum(f.getlength(c) + track for c in txt) - track


def text(d, xy, txt, f, fill, track=0, anchor='l'):
    """letter-spaced text; anchor l / m / r on x, y is the baseline top ('la')"""
    x, y = xy; w = tw(txt, f, track)
    if anchor == 'm': x -= w / 2
    elif anchor == 'r': x -= w
    for c in txt:
        d.text((x, y), c, font=f, fill=fill); x += f.getlength(c) + track
    return w


def lerp(a, b, t): return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def add(base, layer, gain=1.0):
    """additive composite of an RGBA layer (premultiplied by its alpha) onto an RGB image"""
    l = np.asarray(layer, np.float32); b = np.asarray(base, np.float32)
    out = b + l[..., :3] * (l[..., 3:4] / 255.0) * gain
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def glow(base, mask, color, radius, gain=1.0, offset=(0, 0)):
    """add a coloured blurred copy of an L mask"""
    m = mask.filter(ImageFilter.GaussianBlur(radius))
    if offset != (0, 0): m = ImageChops.offset(m, *offset)
    lay = Image.new('RGBA', base.size, color + (0,)); lay.putalpha(m)
    return add(base, lay, gain)


# ------------------------------------------------------------------ backdrop
def backdrop(seed=1, sun=(0.66, 0.0), horizon=0.60, cool=0.0, grid=True):
    rng = np.random.RandomState(seed)
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]; x = np.linspace(0, 1, W, dtype=np.float32)[None, :]
    hz = horizon
    stops = [(0.0, (6, 6, 26)), (0.28, (22, 14, 62)), (0.46, (62, 24, 104)), (hz - 0.07, (170, 44, 130)), (hz - 0.015, (255, 120, 90)), (hz, (255, 190, 120))]
    sky = np.zeros((H, W, 3), np.float32)
    ys = np.array([s[0] for s in stops]); cols = np.array([s[1] for s in stops], np.float32)
    yy = np.linspace(0, 1, H)
    for c in range(3): sky[:, :, c] = np.interp(yy, ys, cols[:, c])[:, None]
    if cool: sky = sky * (1 - cool) + sky[..., ::-1] * cool * 0.55 + np.array([0, 10, 30]) * cool
    # sun / glare at the horizon
    sx, sy = sun[0] * W, hz * H
    r = np.sqrt(((x * W - sx) / 1.0) ** 2 + ((y * H - sy) * 1.7) ** 2)
    sky += np.exp(-r / 150.0)[..., None] * np.array([255, 150, 90], np.float32) * 0.65 + np.exp(-r / 22.0)[..., None] * np.array([255, 235, 200], np.float32) * 0.9
    # stars
    for _ in range(260):
        px, py = rng.randint(0, W), int(rng.rand() ** 1.8 * hz * H * 0.8)
        b = rng.rand() * 160 + 50
        sky[py, px] += (b, b, b * 1.1)
    img = Image.fromarray(np.clip(sky, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img, 'RGBA')
    # dune ridges, far to near, fogged toward the horizon colour
    hy = hz * H
    for k, (amp, col, base) in enumerate(((26, (90, 40, 110), 0), (34, (62, 28, 94), 18), (46, (38, 20, 70), 40), (58, (22, 14, 48), 66))):
        pts = [(0, H)]
        ph = rng.rand(4) * 6.28
        for px in range(0, W + 20, 20):
            t = px / W
            yv = hy + base - amp * (0.5 + 0.28 * math.sin(t * 7 + ph[0] + k) + 0.18 * math.sin(t * 15 + ph[1]) + 0.1 * math.sin(t * 31 + ph[2]))
            pts.append((px, yv))
        pts.append((W, H)); d.polygon(pts, fill=col + (255,))
    # hangar apron (floor) with a perspective grid
    fy = hy + 100
    floor = Image.new('RGBA', (W, H), (0, 0, 0, 0)); fd = ImageDraw.Draw(floor)
    fd.polygon([(0, fy), (W, fy), (W, H), (0, H)], fill=(10, 10, 24, 255))
    gl = Image.new('RGBA', (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(gl)
    if grid:
        vx = W * 0.42
        for i in range(-30, 31):
            gd.line([(vx + i * 52, fy), (vx + i * 380, H)], fill=CY + (110,), width=2)
        k = 0
        z = 1.0
        yline = fy
        while yline < H:
            gd.line([(0, yline), (W, yline)], fill=CY + (int(40 + 70 * (yline - fy) / (H - fy)),), width=2)
            z *= 1.22; yline = fy + (z - 1) * 36
    img = Image.alpha_composite(img.convert('RGBA'), floor).convert('RGB')
    img = add(img, gl, 0.55)
    # rim light strip along the apron edge
    ed = Image.new('L', (W, H), 0); ImageDraw.Draw(ed).line([(0, fy), (W, fy)], fill=255, width=3)
    img = glow(img, ed, MG, 8, 1.4); img = glow(img, ed, CY, 2, 1.0)
    # floor mirror of the sky
    arr = np.asarray(img, np.float32)
    # haze at the horizon
    hz_mask = np.exp(-((np.arange(H) - fy + 20) / 70.0) ** 2)[:, None, None]
    arr += hz_mask * np.array([120, 40, 110], np.float32) * 0.5
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def gantries(img, seed=3):
    """dark angular hangar structure framing the top and sides, edge-lit"""
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    dark = (6, 8, 18, 255)
    d.polygon([(0, 0), (W, 0), (W, 70), (W - 150, 70), (W - 190, 100), (190, 100), (150, 70), (0, 70)], fill=dark)
    d.polygon([(0, 0), (230, 0), (170, 250), (110, 410), (60, 800), (0, 900)], fill=dark)
    d.polygon([(W, 0), (W - 230, 0), (W - 170, 250), (W - 110, 410), (W - 60, 800), (W, 900)], fill=dark)
    # truss lines
    for i in range(0, 12):
        x = 230 + i * 120
        d.polygon([(x, 70), (x + 10, 70), (x + 70, 100), (x + 60, 100)], fill=(14, 18, 36, 255))
    img = Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')
    edge = Image.new('L', (W, H), 0); ed = ImageDraw.Draw(edge)
    ed.line([(150, 70), (190, 100), (W - 190, 100), (W - 150, 70)], fill=255, width=3)
    ed.line([(230, 0), (170, 250), (110, 410), (60, 800)], fill=255, width=3)
    ed.line([(W - 230, 0), (W - 170, 250), (W - 110, 410), (W - 60, 800)], fill=255, width=3)
    img = glow(img, edge, CY, 10, 1.3); img = glow(img, edge, WH, 1.5, 0.6)
    # light-strip dashes on the beam
    st = Image.new('L', (W, H), 0); sd = ImageDraw.Draw(st)
    for x in range(330, W - 300, 60): sd.rectangle([x, 84, x + 30, 88], fill=255)
    img = glow(img, st, MG, 5, 1.2)
    return img


def beams(img, specs):
    """searchlight beams: (x0, x1, y_top, x_bot_left, x_bot_right, colour, strength)"""
    ov = Image.new('L', (W, H), 0)
    for (xa, xb, xc, xd, col, gain) in specs:
        m = Image.new('L', (W, H), 0); ImageDraw.Draw(m).polygon([(xa, 0), (xb, 0), (xd, H), (xc, H)], fill=255)
        m = m.filter(ImageFilter.GaussianBlur(26))
        fade = Image.linear_gradient('L').resize((W, H))
        m = ImageChops.multiply(m, ImageOps.invert(fade).point(lambda v: int(v * 0.5)))
        img = glow(img, m, col, 0.1, gain)
    return img


def embers(img, n=140, seed=5, colors=(CY, MG, OR)):
    rng = random.Random(seed)
    m = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(m)
    for _ in range(n):
        x, y = rng.uniform(0, W), rng.uniform(80, 1000); r = rng.choice((1, 1, 1, 2, 2, 3)); c = rng.choice(colors)
        d.ellipse([x - r, y - r, x + r, y + r], fill=c + (rng.randint(120, 255),))
    img = add(img, m.filter(ImageFilter.GaussianBlur(3)), 1.2)
    return add(img, m, 0.8)


def finish(img, vignette=0.55, scan=True, grain=0, seed=9):
    arr = np.asarray(img, np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    arr *= (1 - vignette * np.clip(r - 0.45, 0, 1) ** 1.6)[..., None]
    if scan: arr *= (1 - 0.06 * ((yy.astype(int) % 3) == 0))[..., None]
    arr += np.random.RandomState(seed).randn(H, W, 1).astype(np.float32) * grain
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


# ------------------------------------------------------------------ mechs
def mech_png(key, yaw, bh, elev=-9, lod=1, ss=1.5):
    """cached RGBA render of a frame, fitted so its projected bounds fill (1.25 bh x bh) with feet at the bottom; returns an image CWxCH and feet-y"""
    os.makedirs(CACHE, exist_ok=True)
    CW, CH = int(bh * 1.5), int(bh * 1.16)
    p = os.path.join(CACHE, 'mech_%s_%d_%d_%d.png' % (key, yaw, bh, -elev))
    if not os.path.exists(p):
        sys.path.insert(0, HERE)
        import mech_render as M
        m = M.load(key, lod=lod, upper_clip='idle', legs_clip='hover')
        S = ss
        img, al, zb = M.render(m, int(CW * S), int(CH * S), yaw=yaw, elev=elev, dist_mul=2.6, fov=34,
                               fit=(1.28 * bh * S, bh * S, CW * S / 2, (CH - 0.06 * bh) * S))
        im = M.to_rgba(img, al).resize((CW, CH), Image.LANCZOS)
        im.save(p)
    return Image.open(p).convert('RGBA'), int(CH - 0.06 * bh)


def place_mech(base, key, yaw, bh, ax, ay, fog=0.0, fogcol=(70, 30, 100), dim=1.0, elev=-9, rim=(CY, MG), reflect=True, tint=None):
    """composite a mech with its feet at (ax, ay): shadow, rim glow, fog, floor reflection"""
    im, feet = mech_png(key, yaw, bh, elev)
    CW, CH = im.size; ox, oy = int(ax - CW / 2), int(ay - feet)
    rgb = np.asarray(im.convert('RGB'), np.float32); a = im.getchannel('A')
    if tint is not None: rgb = rgb * np.array(tint, np.float32)
    rgb = rgb * dim
    if fog: rgb = rgb * (1 - fog) + np.array(fogcol, np.float32) * fog
    # graduated light: brighter top, dark toward the feet (reads as a lit hangar)
    g = np.linspace(1.12, 0.78, CH, dtype=np.float32)[:, None, None]; rgb = rgb * g
    lay = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert('RGBA'); lay.putalpha(a)
    base = base.convert('RGB')
    # rim glow behind (blurred alpha, two colours offset left / right)
    big = Image.new('L', base.size, 0); big.paste(a, (ox, oy))
    base = glow(base, big, rim[0], 12, 0.55 * (1 - fog * 0.6), offset=(-8, 0))
    base = glow(base, big, rim[1], 14, 0.45 * (1 - fog * 0.6), offset=(9, 3))
    # contact shadow
    sh = Image.new('L', base.size, 0); ImageDraw.Draw(sh).ellipse([ax - CW * 0.22, ay - 10, ax + CW * 0.22, ay + 22], fill=255)
    sh = sh.filter(ImageFilter.GaussianBlur(14))
    base = Image.composite(Image.new('RGB', base.size, (4, 4, 12)), base, sh.point(lambda v: int(v * 0.85)))
    if reflect:
        refl = lay.transpose(Image.FLIP_TOP_BOTTOM)
        ra = np.asarray(refl.getchannel('A'), np.float32)
        fade = np.clip(1 - np.arange(CH, dtype=np.float32) / (CH * 0.38), 0, 1)[:, None] ** 1.6 * 0.30
        refl.putalpha(Image.fromarray((ra * fade).astype(np.uint8))); refl = refl.filter(ImageFilter.GaussianBlur(2.5))
        # the flipped picture's feet are at its top: its transparent bottom margin sits above; place so feet touch
        base_rgba = base.convert('RGBA'); base_rgba.alpha_composite(refl, (ox, int(ay - (CH - feet))))
        base = base_rgba.convert('RGB')
    b = base.convert('RGBA'); b.alpha_composite(lay, (ox, oy))
    return b.convert('RGB')


# ------------------------------------------------------------------ UI pieces
def chamfer(x0, y0, x1, y1, c=18, c2=None):
    c2 = c if c2 is None else c2
    return [(x0 + c, y0), (x1, y0), (x1, y1 - c2), (x1 - c2, y1), (x0, y1), (x0, y0 + c)]


def panel(img, box, c=20, fill=(6, 10, 26, 205), edge=CY, glowc=None, label=None, lw=2):
    x0, y0, x1, y1 = box
    ov = Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    d.polygon(chamfer(x0, y0, x1, y1, c), fill=fill)
    img = Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')
    m = Image.new('L', img.size, 0); md = ImageDraw.Draw(m)
    pts = chamfer(x0, y0, x1, y1, c); md.line(pts + [pts[0]], fill=255, width=lw)
    img = glow(img, m, glowc or edge, 6, 0.9)
    ln = Image.new('RGBA', img.size, (0, 0, 0, 0)); ld = ImageDraw.Draw(ln)
    ld.line(pts + [pts[0]], fill=edge + (255,), width=lw)
    # corner ticks
    ld.line([(x0 + c + 12, y0 - 6), (x0 + c + 60, y0 - 6)], fill=MG + (255,), width=3)
    ld.line([(x1 - 60, y1 + 6), (x1 - 12 - c, y1 + 6)], fill=MG + (255,), width=3)
    img = Image.alpha_composite(img.convert('RGBA'), ln).convert('RGB')
    if label:
        d = ImageDraw.Draw(img); f = font('bahn', 20, 'Bold'); lw_ = int(tw(label, f, 4)) + 28
        d.polygon(chamfer(x0 + c + 6, y0 - 20, x0 + c + 6 + lw_, y0 + 8, 8, 8), fill=(10, 16, 40), outline=edge)
        text(d, (x0 + c + 20, y0 - 17), label, f, edge, 4)
    return img


def hazard(d, x0, y0, x1, y1, col=(255, 190, 60), step=18, alpha=200):
    for x in range(int(x0), int(x1), step * 2):
        d.polygon([(x, y1), (x + step, y1), (x + step + (y1 - y0), y0), (x + (y1 - y0), y0)], fill=col + (alpha,))


def header(img, tag, title, sub=None, page=None):
    """top-left title block and bottom strip, inside the safe area"""
    ov = Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    x = 252
    text(d, (x, 104), tag, font('bahn', 22, 'Bold'), CY + (255,), 6)
    d.polygon([(x - 28, 104), (x - 10, 104), (x - 2, 118), (x - 10, 132), (x - 28, 132), (x - 20, 118)], fill=MG + (255,))
    text(d, (x, 126), title, font('agency', 92), WH + (255,), 6)
    if sub: text(d, (x + 4, 226), sub, font('segoer', 26), (170, 190, 225, 255), 1)
    d.rectangle([x, 276, x + 1096, 278], fill=BL + (200,))
    d.polygon([(x, 274), (x + 120, 274), (x + 134, 280), (x, 280)], fill=CY + (255,))
    img = add(img, ov.filter(ImageFilter.GaussianBlur(8)), 0.6)
    ov2 = Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')
    d = ImageDraw.Draw(ov2)
    # bottom ticker
    y = 930
    text(d, (252, y), 'MG_IRONFRAME_DUNES   //   64 PILOTS', font('bahn', 20, 'SemiBold'), (120, 150, 200), 4)
    if page:
        for i in range(4):
            xx = 1348 - (3 - i) * 44
            d.polygon([(xx, y + 2), (xx + 30, y + 2), (xx + 38, y + 14), (xx + 8, y + 14)], fill=CY if i == page - 1 else (40, 50, 85))
    return ov2


# ------------------------------------------------------------------ logotype
def _letters(t=24):
    """angular IRONFRAME letters: each a list of (polygon, fill) in a 100-high box; later polygons with fill 0 cut holes"""
    c = 14
    L = {}
    L['I'] = (t, [([(0, 0), (t, 0), (t, 100), (0, 100)], 1)])
    def R_(w):
        return [([(0, 0), (w - 16, 0), (w, 16), (w, 48), (w - 16, 64), (0, 64)], 1),
                ([(t, 20), (w - t - 8, 20), (w - t, 28), (w - t, 36), (w - t - 8, 44), (t, 44)], 0),
                ([(0, 60), (t, 60), (t, 100), (0, 100)], 1),
                ([(w * 0.34, 62), (w * 0.34 + t + 6, 62), (w, 100), (w - t - 6, 100)], 1)]
    L['R'] = (70, R_(70))
    w = 78
    L['O'] = (w, [([(0, 18), (18, 0), (w - 18, 0), (w, 18), (w, 82), (w - 18, 100), (18, 100), (0, 82)], 1),
                  ([(t, t + 6), (t + 8, t - 2), (w - t - 8, t - 2), (w - t, t + 6), (w - t, 94 - t), (w - t - 8, 102 - t), (t + 8, 102 - t), (t, 94 - t)], 0)])
    w = 78
    L['N'] = (w, [([(0, 0), (t, 0), (t, 100), (0, 100)], 1), ([(w - t, 0), (w, 0), (w, 100), (w - t, 100)], 1),
                  ([(0, 0), (t + 8, 0), (w, 100), (w - t - 8, 100)], 1), ([(0, 0), (c, 0), (0, c)], 1)])
    w = 64
    L['F'] = (w, [([(0, 0), (w, 0), (w - 12, t * 0.85), (t, t * 0.85), (t, 100), (0, 100)], 1),
                  ([(t, 44), (w * 0.82, 44), (w * 0.82 - 10, 44 + t * 0.8), (t, 44 + t * 0.8)], 1)])
    L['R2'] = L['R']
    w = 84; c1 = w * 0.30
    L['A'] = (w, [([(0, 100), (c1, 0), (c1 + t + 6, 0), (t + 4, 100)], 1), ([(w, 100), (w - c1, 0), (w - c1 - t - 6, 0), (w - t - 4, 100)], 1),
                  ([(c1, 0), (w - c1, 0), (w - c1 - 8, t * 0.8), (c1 + 8, t * 0.8)], 1), ([(w * 0.22, 62), (w * 0.78, 62), (w * 0.78, 62 + t * 0.62), (w * 0.22, 62 + t * 0.62)], 1)])
    w = 98
    L['M'] = (w, [([(0, 0), (t, 0), (t, 100), (0, 100)], 1), ([(w - t, 0), (w, 0), (w, 100), (w - t, 100)], 1),
                  ([(0, 0), (t + 10, 0), (w / 2 + t * 0.5, 74), (w / 2 - t * 0.5, 74)], 1), ([(w - t - 10, 0), (w, 0), (w / 2 + t * 0.5, 74), (w / 2 - t * 0.5, 74)], 1)])
    w = 64
    L['E'] = (w, [([(0, 0), (w, 0), (w - 12, t * 0.85), (t, t * 0.85), (t, 100 - t * 0.85), (w - 12, 100 - t * 0.85), (w, 100), (0, 100)], 1),
                  ([(t, 46 - t * 0.4), (w * 0.86, 46 - t * 0.4), (w * 0.86 - 10, 46 + t * 0.4), (t, 46 + t * 0.4)], 1)])
    return L


def logotype(width=1060, ssf=2):
    """RGBA image of the IRONFRAME logotype (face, bevel, extrusion, stencil cuts) plus its L mask, height from the aspect"""
    L = _letters(); order = ['I', 'R', 'O', 'N', 'F', 'R2', 'A', 'M', 'E']
    gap = 13; total = sum(L[k][0] for k in order) + gap * (len(order) - 1)
    sx = width * ssf / (total + 22); sy = sx * 1.32 ; hgt = int(100 * sy)
    pad = int(60 * ssf)
    Wm, Hm = int(total * sx + 2 * pad + 40 * ssf), hgt + 2 * pad
    mask = Image.new('L', (Wm, Hm), 0); d = ImageDraw.Draw(mask)
    shear = 0.2
    x = pad
    for k in order:
        w, polys = L[k]
        lm = Image.new('L', (Wm, Hm), 0); ld = ImageDraw.Draw(lm)
        for pts, v in polys:
            ld.polygon([(x + px * sx + (100 - py) * sx * shear, pad + py * sy) for px, py in pts], fill=255 if v else 0)
        mask = ImageChops.lighter(mask, lm); x += (w + gap) * sx
    # stencil cuts: a diagonal slash and horizontal gap across the lower third
    cut = Image.new('L', (Wm, Hm), 0); cd = ImageDraw.Draw(cut)
    y1 = pad + hgt * 0.60
    cd.rectangle([0, y1, Wm, y1 + 4 * ssf], fill=255)
    mask = ImageChops.subtract(mask, cut)
    S = ssf
    # face: vertical gradient
    g = np.zeros((Hm, Wm, 3), np.float32); ty = np.clip((np.arange(Hm) - pad) / hgt, 0, 1)
    stops = [(0.0, (245, 252, 255)), (0.35, (110, 230, 255)), (0.62, (70, 130, 255)), (0.78, (130, 80, 255)), (1.0, (255, 70, 200))]
    for ch in range(3): g[:, :, ch] = np.interp(ty, [s[0] for s in stops], [s[1][ch] for s in stops])[:, None]
    face = Image.fromarray(g.astype(np.uint8)).convert('RGBA'); face.putalpha(mask)
    # extrusion: stack shifted darker copies
    out = Image.new('RGBA', (Wm, Hm), (0, 0, 0, 0))
    steps = 16
    for i in range(steps, 0, -1):
        ex = Image.new('RGBA', (Wm, Hm), lerp((40, 10, 90), (200, 30, 150), 1 - i / steps) + (255,)); m2 = ImageChops.offset(mask, int(i * 0.75 * S), int(i * 0.95 * S)); ex.putalpha(m2)
        out = Image.alpha_composite(out, ex)
    # bevel: bright inner edge top-left, dark inner edge bottom-right
    er = mask.filter(ImageFilter.MinFilter(int(5 * S) | 1))
    edge = ImageChops.subtract(mask, er)
    hi = ImageChops.multiply(edge, ImageChops.offset(ImageOps.invert(er.filter(ImageFilter.GaussianBlur(1))), 0, 0))
    lighten = Image.new('RGBA', (Wm, Hm), (255, 255, 255, 0)); lighten.putalpha(ImageChops.subtract(edge, ImageChops.offset(edge, int(2 * S), int(2 * S))))
    out = Image.alpha_composite(out, face); out = Image.alpha_composite(out, lighten)
    # scanline texture inside the face
    sc = Image.new('L', (Wm, Hm), 0); sd = ImageDraw.Draw(sc)
    for yy in range(0, Hm, int(6 * S)): sd.line([(0, yy), (Wm, yy)], fill=40, width=max(1, int(S)))
    dark = Image.new('RGBA', (Wm, Hm), (0, 10, 40, 0)); dark.putalpha(ImageChops.multiply(sc, mask)); out = Image.alpha_composite(out, dark)
    ext_mask = out.getchannel('A')
    return out.resize((Wm // S, Hm // S), Image.LANCZOS), ext_mask.resize((Wm // S, Hm // S), Image.LANCZOS), mask.resize((Wm // S, Hm // S), Image.LANCZOS)


def draw_logo(img, cx, top, width=1060):
    lg, am, fm = logotype(width)
    x0 = int(cx - lg.width / 2); y0 = int(top - 60)
    base = img.convert('RGB')
    full = Image.new('L', base.size, 0); full.paste(am, (x0, y0))
    face = Image.new('L', base.size, 0); face.paste(fm, (x0, y0))
    base = glow(base, full, MG, 40, 0.9, offset=(18, 20))
    base = glow(base, face, CY, 30, 1.0); base = glow(base, face, WH, 6, 0.6)
    b = base.convert('RGBA'); b.alpha_composite(lg, (x0, y0))
    return b.convert('RGB'), (x0, y0, lg.width, lg.height)


# ------------------------------------------------------------------ icons for the mode cards (vector, 96 px box centred at (cx, cy))
def icon(d, kind, cx, cy, col, s=1.0):
    w = 4
    def P(pts, **k): d.polygon([(cx + x * s, cy + y * s) for x, y in pts], **k)
    def Ln(pts, wd=w): d.line([(cx + x * s, cy + y * s) for x, y in pts], fill=col, width=wd, joint='curve')
    if kind == 'tdm':                  # two opposed chevrons
        Ln([(-44, -30), (-14, 0), (-44, 30)], 8); Ln([(44, -30), (14, 0), (44, 30)], 8); Ln([(-8, -34), (8, 34)], 5)
    elif kind == 'conq':               # three hex points
        for (x, y) in ((-34, 20), (34, 20), (0, -26)):
            hexp = [(x + 20 * math.cos(math.radians(60 * i + 30)), y + 20 * math.sin(math.radians(60 * i + 30))) for i in range(6)]
            d.polygon([(cx + a * s, cy + b * s) for a, b in hexp], outline=col, width=5)
        Ln([(-18, 14), (18, 14)], 3); Ln([(-8, -10), (-26, 8)], 3); Ln([(8, -10), (26, 8)], 3)
    elif kind == 'koth':               # hill with a crown ring
        Ln([(-48, 36), (-14, -14), (0, 6), (18, -22), (48, 36), (-48, 36)], 5)
        d.ellipse([cx - 30 * s, cy - 44 * s, cx + 30 * s, cy - 16 * s], outline=col, width=5)
    elif kind == 'ctf':                # flag
        Ln([(-24, 44), (-24, -44)], 6); P([(-22, -44), (38, -28), (-22, -8)], fill=col)
    elif kind == 'skirm':              # crosshair
        d.ellipse([cx - 34 * s, cy - 34 * s, cx + 34 * s, cy + 34 * s], outline=col, width=5)
        Ln([(-50, 0), (-16, 0)], 5); Ln([(16, 0), (50, 0)], 5); Ln([(0, -50), (0, -16)], 5); Ln([(0, 16), (0, 50)], 5)
    elif kind == 'sortie':             # drop arrow into a beacon
        Ln([(0, -46), (0, 20)], 6); Ln([(-20, 0), (0, 22), (20, 0)], 6)
        d.ellipse([cx - 44 * s, cy + 24 * s, cx + 44 * s, cy + 46 * s], outline=col, width=4)
    elif kind == 'lock':
        for sx_, sy_ in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            Ln([(sx_ * 44, sy_ * 20), (sx_ * 44, sy_ * 44), (sx_ * 20, sy_ * 44)], 6)
        d.ellipse([cx - 12 * s, cy - 12 * s, cx + 12 * s, cy + 12 * s], fill=col)
    elif kind == 'energy':
        P([(8, -48), (-26, 6), (-2, 6), (-10, 48), (28, -8), (4, -8)], fill=col)
    elif kind == 'dodge':
        Ln([(-46, 20), (6, 20)], 6); Ln([(-46, 0), (-6, 0)], 6); Ln([(-46, -20), (-18, -20)], 6)
        P([(10, -34), (46, 0), (10, 34), (22, 0)], fill=col)
    elif kind == 'contract':
        P([(-30, -44), (30, -44), (30, 44), (-30, 44)], outline=col, width=5)
        for yy in (-20, -4, 12): Ln([(-16, yy), (16, yy)], 4)
        Ln([(-16, 30), (-4, 30)], 4)


def draw_icon_glow(img, kind, cx, cy, col, s=1.0):
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay); icon(d, kind, cx, cy, col + (255,), s)
    img = add(img, lay.filter(ImageFilter.GaussianBlur(8)), 1.0)
    b = img.convert('RGBA'); b.alpha_composite(lay); return b.convert('RGB')


def keycap(img, x, y, label, w=None, h=64, col=CY, size=28):
    f = font('bahn', size, 'Bold')
    w = w or max(h, int(tw(label, f, 2) + 36))
    d = ImageDraw.Draw(img, 'RGBA')
    pts = chamfer(x, y, x + w, y + h, 12, 12)
    d.polygon(pts, fill=(16, 26, 58, 235)); d.line(pts + [pts[0]], fill=col + (255,), width=2)
    d.line([(x + 14, y + h - 7), (x + w - 14, y + h - 7)], fill=col + (140,), width=2)
    text(d, (x + w / 2, y + (h - size) / 2 - 7), label, f, WH, 2, 'm')
    return w


def wrap(txt, f, maxw):
    out, cur = [], ''
    for wd in txt.split():
        t = (cur + ' ' + wd).strip()
        if tw(t, f) <= maxw: cur = t
        else: out.append(cur); cur = wd
    out.append(cur); return out


# ------------------------------------------------------------------ the four slides
def slide_title(arena='DUNES'):
    img = backdrop(seed=1, sun=(0.70, 0), horizon=0.58)
    img = beams(img, [(250, 320, -80, 160, CY, 0.22), (1500, 1580, 1800, 2020, MG, 0.20), (1020, 1070, 1180, 1320, PU, 0.16)])
    img = gantries(img)
    ay = 880
    img = place_mech(img, 'ac4a_hari', -22, 470, 420, ay - 38, fog=0.30, dim=0.95)
    img = place_mech(img, 'gundam_barbatos', 32, 470, 1390, ay - 38, fog=0.30, dim=0.95)
    img = place_mech(img, 'ac4a_whiteglint', 22, 560, 640, ay + 6, fog=0.03)
    img = place_mech(img, 'tf_atlas', -24, 560, 1150, ay + 6, fog=0.03)
    img = embers(img, 160)
    img, (lx, ly, lw, lh) = draw_logo(img, 800, 112, 1040)
    ov = Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    y = ly + lh - 62
    d.polygon([(300, y), (1300, y), (1288, y + 6), (312, y + 6)], fill=MG + (255,))
    text(d, (800, y + 20), 'GIANT ROBOT ARENA COMBAT', font('bahn', 34, 'SemiBold'), WH + (255,), 14, 'm')
    img = add(img, ov.filter(ImageFilter.GaussianBlur(6)), 0.5)
    img = Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')
    # arena plate bottom-centre
    img = panel(img, (500, 892, 1100, 954), c=18, fill=(6, 8, 22, 225), edge=MG, glowc=MG)
    d = ImageDraw.Draw(img)
    text(d, (800, 897), 'ARENA  //  ' + arena.upper(), font('agency', 54), WH, 12, 'm')
    return finish(img)


def slide_controls():
    img = backdrop(seed=2, sun=(0.30, 0), horizon=0.60, cool=0.25)
    img = beams(img, [(1300, 1380, 1480, 1800, CY, 0.18), (300, 360, 100, 400, PU, 0.14)])
    img = gantries(img)
    img = place_mech(img, 'fear3_mule', 28, 800, 1500, 1010, fog=0.15, dim=0.95)
    img = embers(img, 90, seed=6)
    img = header(img, 'FLIGHT MANUAL  01', 'CONTROLS', 'Everything you need in the cockpit', 2)
    cap = 8
    cols = [(252, 'MOVEMENT', [(['W', 'A', 'S', 'D'], 'Move'), (['SHIFT'], 'Boost'), (['CTRL'], 'Quick-boost: dodge sideways'), (['SPACE'], 'Jump, hold to hover')]),
            (806, 'WEAPONS', [(['MOUSE 1'], 'Right arm weapon'), (['MOUSE 2'], 'Left arm weapon'), (['R', 'E'], 'Shoulder weapons'), (['F'], 'Next target: lock on')])]
    for x0, name, rows in cols:
        img = panel(img, (x0, 322, x0 + 542, 322 + 4 * 78 + 28), label=name, fill=(5, 8, 22, 215))
        for i, (keys, desc) in enumerate(rows):
            y = 346 + i * 78; x = x0 + 24
            for k in keys:
                x += keycap(img, x, y, k, w=50 if len(k) == 1 else None, h=58, size=24 if len(k) > 1 else 28) + 8
            d = ImageDraw.Draw(img); f = font('segoer', 24)
            tx = x0 + 262
            ls = wrap(desc, f, x0 + 526 - tx)
            for j, l in enumerate(ls[:2]):
                d.text((tx, y + 6 + j * 28 - (len(ls) - 1) * 14), l, font=f, fill=(210, 224, 245))
    img = panel(img, (252, 684, 1348, 780), label='WHEN DESTROYED', fill=(24, 6, 22, 220), edge=MG, glowc=MG)
    x = 280
    x += keycap(img, x, 704, 'CTRL', h=58, col=MG, size=24) + 10
    d = ImageDraw.Draw(img); d.text((x, 718), '/', font=font('segoe', 28), fill=MG); x += 24
    x += keycap(img, x, 704, 'F', h=58, col=MG) + 16
    d = ImageDraw.Draw(img); d.text((x, 719), 'Open the garage and change loadout before you respawn', font=font('segoer', 24), fill=(235, 215, 235))
    img = panel(img, (252, 812, 1348, 906), label='CHAT COMMANDS', fill=(5, 8, 22, 215))
    x = 280
    for cmd in ('!garage', '!loadout', '!contracts', '!help'):
        f = font('mono', 30); w = int(tw(cmd, f, 1)) + 40
        d = ImageDraw.Draw(img, 'RGBA'); pts = chamfer(x, 836, x + w, 888, 10, 10)
        d.polygon(pts, fill=(12, 22, 50, 235)); d.line(pts + [pts[0]], fill=CY + (255,), width=2)
        d.text((x + 20, 845), cmd, font=f, fill=WH); x += w + 24
    return finish(img)


def slide_modes():
    img = backdrop(seed=3, sun=(0.50, 0), horizon=0.62, cool=0.1)
    img = beams(img, [(1480, 1540, 1650, 1900, MG, 0.18), (250, 300, 20, 280, CY, 0.16)])
    img = gantries(img)
    img = place_mech(img, 'ac4a_hari', 20, 560, 1480, 1000, fog=0.30, dim=0.85)
    img = embers(img, 90, seed=7)
    img = header(img, 'BATTLE BRIEFING  02', 'GAME MODES', 'The server picks one each round; players vote on the next', 3)
    modes = [('tdm', 'TEAM DEATHMATCH', 'Two teams, one scoreboard. Every kill counts: first to the target wins.', CY),
             ('conq', 'CONQUEST', 'Hold points A, B and C. Held points bleed the enemy ticket count.', BL),
             ('koth', 'KING OF THE HILL', 'One zone. Stand in it to score and keep the other team out.', PU),
             ('ctf', 'CAPTURE THE FLAG', 'Steal their flag, carry it home, and defend your own.', MG),
             ('skirm', 'SKIRMISH', 'Free for all. No teams, first pilot to 25 kills wins.', OR),
             ('sortie', 'SORTIE', 'Co-op against waves of AI squads and bosses. Hold the beacon.', CY)]
    cw, ch, gx, gy = 350, 282, 23, 24
    for i, (k, name, line, col) in enumerate(modes):
        cx0 = 252 + (i % 3) * (cw + gx); cy0 = 316 + (i // 3) * (ch + gy)
        img = panel(img, (cx0, cy0, cx0 + cw, cy0 + ch), c=24, fill=(5, 8, 22, 222), edge=col, glowc=col)
        img = draw_icon_glow(img, k, cx0 + 70, cy0 + 70, col, 1.0)
        d = ImageDraw.Draw(img)
        text(d, (cx0 + cw - 24, cy0 + 22), '0%d' % (i + 1), font('agency', 54), col, 2, 'r')
        text(d, (cx0 + 24, cy0 + 132), name, font('bahn', 26, 'Bold'), WH, 3)
        d.line([(cx0 + 24, cy0 + 170), (cx0 + 120, cy0 + 170)], fill=col, width=3)
        f = font('segoer', 21)
        for j, l in enumerate(wrap(line, f, cw - 50)[:4]): d.text((cx0 + 24, cy0 + 184 + j * 26), l, font=f, fill=(200, 215, 240))
    return finish(img)


def slide_tips():
    img = backdrop(seed=4, sun=(0.80, 0), horizon=0.59)
    img = beams(img, [(400, 460, 200, 520, PU, 0.18), (1400, 1460, 1500, 1720, CY, 0.16)])
    img = gantries(img)
    img = place_mech(img, 'tf_atlas', -20, 600, 1450, 1000, fog=0.28, dim=0.9)
    img = embers(img, 90, seed=8)
    img = header(img, 'PILOT ADVICE  03', 'COMBAT TIPS', 'Small habits that win fights', 4)
    tips = [('lock', 'LOCK ON AND STAGGER', 'Press F to lock a target. Heavy hits fill its stagger meter; a staggered mech is slow, cannot boost and takes extra damage. Finish it then.', CY),
            ('energy', 'MANAGE YOUR ENERGY', 'Boost, quick-boost and hover all burn EN. Empty means no thrusters. Pace your bursts and land to recover.', BL),
            ('dodge', 'QUICK-BOOST THE MISSILES', 'Missiles cannot turn on a coin. Tap CTRL sideways just before impact and let them fly past.', MG),
            ('contract', 'UPGRADES AND CONTRACTS', 'Spend credits on part upgrades in the garage. Daily contracts pay extra XP and credits: type !contracts.', OR)]
    cw, ch, gx, gy = 541, 270, 14, 24
    for i, (k, name, body, col) in enumerate(tips):
        x0 = 252 + (i % 2) * (cw + gx); y0 = 316 + (i // 2) * (ch + gy)
        img = panel(img, (x0, y0, x0 + cw, y0 + ch), c=24, fill=(5, 8, 22, 222), edge=col, glowc=col)
        img = draw_icon_glow(img, k, x0 + 62, y0 + 62, col, 0.9)
        d = ImageDraw.Draw(img)
        text(d, (x0 + 122, y0 + 36), name, font('bahn', 24, 'Bold'), WH, 2)
        d.line([(x0 + 122, y0 + 74), (x0 + 210, y0 + 74)], fill=col, width=3)
        f = font('segoer', 26)
        for j, l in enumerate(wrap(body, f, cw - 52)[:6]): d.text((x0 + 26, y0 + 100 + j * 34), l, font=f, fill=(205, 218, 242))
    return finish(img)


def fit_png(img, limit=950000):
    """drop low colour bits until the optimised PNG is under `limit` bytes (the busy hero slide needs 2)"""
    import io
    a = np.asarray(img.convert('RGB'))
    for bits in range(0, 5):
        q = a if bits == 0 else (((a >> bits) << bits) + (1 << bits >> 1)).astype(np.uint8)
        b = io.BytesIO(); Image.fromarray(q).save(b, 'PNG', optimize=True)
        if len(b.getvalue()) <= limit: return Image.fromarray(q)
    return Image.fromarray(q)


def slides(title='IRONFRAME: Dunes'):
    arena = title.split(':')[-1].strip()
    return [fit_png(f) for f in (slide_title(arena), slide_controls(), slide_modes(), slide_tips())]


# ------------------------------------------------------------------ Workshop icon
def workshop_icon(size=1024):
    global W, H
    sw, sh = W, H; W, H = 1024, 1024
    try:
        img = backdrop(seed=11, sun=(0.5, 0), horizon=0.60)
        img = beams(img, [(100, 150, 0, 300, CY, 0.2), (880, 930, 800, 1100, MG, 0.2)])
        img = embers(img, 70, seed=12)
        img = place_mech(img, 'ac4a_whiteglint', 24, 700, 512, 840, fog=0.0, elev=-11)
        img, (lx, ly, lw, lh) = draw_logo(img, 512, 70, 920)
        d = ImageDraw.Draw(img)
        text(d, (512, 905), 'MECH ARENA COMBAT', font('bahn', 34, 'SemiBold'), WH, 12, 'm')
        out = finish(img, vignette=0.5)
    finally:
        W, H = sw, sh
    return out


# ------------------------------------------------------------------ text files
def credits_lines(title='IRONFRAME: Dunes'):
    return ['COMMUNITYMAPCREDITS:',
            title + '  -  64-player giant robot arena combat',
            'Map, script, HUD and sounds: skink52 with Claude (AI-generated, CC BY-NC 4.0)',
            'Mech frames and weapon props: Garry\'s Mod Workshop porters, credited on the Workshop page',
            'Armored Core, Titanfall, Gundam, F.E.A.R. 3 are the property of their owners',
            'Progression and garage: Slime Servers minigame module']


def description(title='IRONFRAME: Dunes'):
    return '''[h1]%s[/h1]
Giant robot arena combat for up to 64 pilots, in the style of Armored Core, Titanfall and Gundam. Boost, quick-boost and hover across huge terrain,
lock on, stagger your enemies and tear them apart.

[h2]How to play[/h2]
[list]
[*][b]Move:[/b] WASD. Shift boosts, Ctrl quick-boosts (a fast dodge), Space jumps and hovers.
[*][b]Fight:[/b] Mouse 1 and Mouse 2 fire the arm weapons, R and E the shoulder weapons, F locks the next target.
[*][b]Garage:[/b] Ctrl or F while dead, or type [i]!garage[/i]. Other chat commands: [i]!loadout[/i], [i]!contracts[/i], [i]!help[/i].
[/list]

[h2]Modes[/h2]
[list]
[*]Team Deathmatch, Conquest, King of the Hill, Capture the Flag, Skirmish (free for all) and Sortie (co-op against AI waves).
[/list]

[h2]Tips[/h2]
[list]
[*]Lock on and fill the stagger meter: a staggered mech cannot boost and takes extra damage.
[*]Boost, quick-boost and hover share one energy bar. Pace your bursts.
[*]Quick-boost sideways just before a missile lands.
[*]Upgrade parts in the garage and finish the daily contracts for extra XP and credits.
[/list]

[h2]Hosting[/h2]
[list]
[*]Game mode: Custom. Career, garage and contracts are saved by the Slime Servers minigame module; without it every part is unlocked and nothing is saved.
[/list]

Mech frames and weapon props are conversions of Garry's Mod Workshop models by their authors, credited in the addon; the original games' studios own the designs.
Map, script and art by skink52 with AI-assisted tools.
''' % title


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(PROJ, 'preview', 'loading')
    os.makedirs(out, exist_ok=True)
    only = sys.argv[2] if len(sys.argv) > 2 else 'all'
    fns = {'1': slide_title, '2': slide_controls, '3': slide_modes, '4': slide_tips}
    for k, f in fns.items():
        if only in ('all', k): f().save(os.path.join(out, 'slide_%s.png' % k)); print('slide', k, flush=True)
    if only in ('all', 'icon'): workshop_icon().save(os.path.join(out, 'workshop_icon.png')); print('icon')
