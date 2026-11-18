"""Zombie first-person view frames (the zombie's "weapon" psprites) in the Doom palette, built from the creatures' own
Freedoom art: the serpentipede's (TROO) striped hide and the flesh worm's (SARG) and deadflare's (SKUL, BAL1) flesh
and fire are sampled as textures, shaded and quantised to PLAYPAL.

usage: zviews.py <out_dir> [--sheet preview/zviews_sheet.png]
writes <out_dir>/<SPR><F>0.png (RGBA, 1 pixel = 1 Doom pixel) and <out_dir>/offsets.json {name: [left, top]}, offsets in
the weapon-sprite convention hud.py uses (screen x = 1 - left, screen y = 16 - top on the 320x200 screen, the view
bottom at y 184 like PISG/PUNG; frames run on to y 200 so the bob never shows an edge).

Frames (STATUS.md contract): ZIMP A-D imp claw (A idle, B wind-up, C swipe, D follow-through); ZIMF A-C imp fireball
(A cupped hands, B bright fireball, C release); ZDMN A-D flesh-worm jaws (A idle, B open, C bite, D lunge);
ZSKL A-C deadflare (A idle, B flare, C dash).
"""
import json, math, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets

SS = 4                       # supersampling
VW, VH = 320, 200
W, H = VW * SS, VH * SS
FRAMES = {'ZIMP': 'ABCD', 'ZIMF': 'ABC', 'ZDMN': 'ABCD', 'ZSKL': 'ABC'}
LIGHT = np.array([-0.45, -0.6, 0.66]); LIGHT = LIGHT / np.linalg.norm(LIGHT)
RNG = np.random.default_rng(1993)

# palette without the transparent magenta
PALF = assets.PAL.astype(np.float32)
PAL_OK = np.array([i for i in range(256) if tuple(assets.PAL[i]) != (255, 0, 255)])


def spr(name):
    return assets.sprite(name)[0].astype(np.float32) / 255.0


def lin(c):
    return np.array(c, np.float32) / 255.0


# ------------------------------------------------------------------ textures from the creatures' own sprites
def strip(name, x0, x1, y0, y1):
    a = spr(name)[y0:y1, x0:x1]
    rgb = a[..., :3].copy()
    m = a[..., 3] > 0.5
    fill = rgb[m].mean(0)
    rgb[~m] = fill
    return rgb


TEX_IMP = strip('TROOA1', 18, 31, 22, 56)        # the serpentipede's gold-banded torso
TEX_WORM = strip('SARGA1', 8, 30, 30, 56)        # flesh worm body
TEX_WORM_MOUTH = strip('SARGF1', 18, 42, 6, 26)  # its red star mouth
TEX_SOUL = strip('SKULA1', 4, 26, 4, 22)         # deadflare flesh


def tex_sample(tex, u, v):
    """u in [-1, 1] across, v any (wraps along)"""
    th, tw = tex.shape[:2]
    x = np.clip(((u + 1) * 0.5 * (tw - 1)).round().astype(int), 0, tw - 1)
    y = (np.floor(v).astype(int)) % th
    return tex[y, x]


# ------------------------------------------------------------------ canvas
class Canvas:
    def __init__(self):
        self.rgb = np.zeros((H, W, 3), np.float32)
        self.a = np.zeros((H, W), np.float32)
        self.yy, self.xx = np.mgrid[0:H, 0:W].astype(np.float32)

    def put(self, mask, col, x0=0, y0=0):
        """mask HxW (or a window at x0,y0) in [0,1]; col same shape + 3"""
        h, w = mask.shape
        r = self.rgb[y0:y0 + h, x0:x0 + w]; a = self.a[y0:y0 + h, x0:x0 + w]
        m = mask[..., None]
        r[:] = r * (1 - m) + col * m
        a[:] = np.maximum(a, mask)

    def add(self, col, x0=0, y0=0):
        """additive light (glow) over what is drawn and as its own alpha"""
        h, w = col.shape[:2]
        self.rgb[y0:y0 + h, x0:x0 + w] += col
        self.a[y0:y0 + h, x0:x0 + w] = np.maximum(self.a[y0:y0 + h, x0:x0 + w], np.clip(col.max(-1) * 1.6, 0, 1))


def shade(n, base, amb=0.32, spec=0.35, power=18, warm=None):
    d = np.clip((n * LIGHT).sum(-1), 0, 1)
    h = LIGHT + np.array([0, 0, 1.0]); h = h / np.linalg.norm(h)
    s = np.clip((n * h).sum(-1), 0, 1) ** power * spec
    out = base * (amb + (1 - amb) * d)[..., None] + s[..., None] * np.array([1.0, 0.95, 0.85])
    if warm is not None:
        out = out + warm
    return out


def bez(p, t):
    p = np.asarray(p, np.float32); t = np.asarray(t, np.float32)[:, None]
    n = len(p) - 1
    out = 0
    for i, q in enumerate(p):
        out = out + math.comb(n, i) * (1 - t) ** (n - i) * t ** i * q
    return out


def tube(cv, ctrl, r0, r1, tex, bands=0.0, rim=0.12, warm_at=None, warm_col=None, step=0.6, taper=1.0, tint=1.0, vscale=1.1):
    """a shaded, textured tube swept along a bezier (screen coords x SS); r0 at the start, r1 at the end"""
    ctrl = [(x * SS, y * SS) for x, y in ctrl]
    pts = bez(ctrl, np.linspace(0, 1, 400))
    seg = np.r_[0, np.cumsum(np.hypot(*np.diff(pts, axis=0).T))]
    L = seg[-1]
    n = max(2, int(L / step))
    ts = np.interp(np.linspace(0, L, n), seg, np.linspace(0, 1, len(pts)))
    P = bez(ctrl, ts)
    D = np.gradient(P, axis=0); D /= np.linalg.norm(D, axis=1, keepdims=True) + 1e-9
    for i in range(n):
        t = ts[i]
        r = (r0 + (r1 - r0) * t ** taper) * SS
        if r < 0.6: continue
        cx, cy = P[i]; dx, dy = D[i]
        x0, x1 = int(max(0, cx - r - 2)), int(min(W, cx + r + 3)); y0, y1 = int(max(0, cy - r - 2)), int(min(H, cy + r + 3))
        if x0 >= x1 or y0 >= y1: continue
        X = cv.xx[y0:y1, x0:x1] - cx; Y = cv.yy[y0:y1, x0:x1] - cy
        d = np.hypot(X, Y)
        m = np.clip(r - d + 0.5, 0, 1)
        if not m.any(): continue
        s = np.clip((X * -dy + Y * dx) / r, -1, 1)       # across the tube
        along = np.clip((X * dx + Y * dy) / r, -1, 1)
        nz = np.sqrt(np.clip(1 - s * s, 0, 1))
        nx = -dy * s; ny = dx * s
        nrm = np.stack([nx + dx * along * 0.25, ny + dy * along * 0.25, nz], -1)
        nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
        v = seg_len = t * L / SS
        col = tex_sample(tex, s, np.full_like(s, v * vscale)) * tint
        if bands:
            col = col * (0.75 + 0.35 * (0.5 + 0.5 * np.cos(v * bands)))
        warm = None
        if warm_at is not None:
            wx, wy = warm_at[0] * SS, warm_at[1] * SS
            dist = np.hypot(cv.xx[y0:y1, x0:x1] - wx, cv.yy[y0:y1, x0:x1] - wy) / SS
            face = np.clip(-(nx * (cv.xx[y0:y1, x0:x1] - wx) + ny * (cv.yy[y0:y1, x0:x1] - wy)) / (dist * SS + 1e-6), 0, 1)
            warm = (np.clip(1 - dist / 70.0, 0, 1) ** 1.5 * (0.35 + 0.65 * face))[..., None] * warm_col
        c = shade(nrm, col, warm=warm)
        edge = np.clip((np.abs(s) - (1 - rim)) / rim, 0, 1)
        c = c * (1 - 0.75 * edge[..., None])
        cv.put(m, c, x0, y0)


def claw(cv, base, ang, length, width, curl, warm_at=None, warm_col=None):
    """a curved talon from base (screen px) pointing at ang (radians), curling by curl"""
    bx, by = base
    ex = bx + math.cos(ang) * length; ey = by + math.sin(ang) * length
    mx = bx + math.cos(ang) * length * 0.55 + math.cos(ang + math.pi / 2) * curl
    my = by + math.sin(ang) * length * 0.55 + math.sin(ang + math.pi / 2) * curl
    # horn: dark at the root, pale towards the point (texture rows run along the talon)
    ramp = np.linspace(0, 1, 24)[:, None, None]
    tex = np.ascontiguousarray((np.array([0.16, 0.11, 0.07]) * (1 - ramp) + np.array([0.88, 0.82, 0.66]) * ramp)
                               .repeat(3, 1).astype(np.float32))
    tube(cv, [(bx, by), (mx, my), (ex, ey)], width, 0.4, tex, rim=0.25, warm_at=warm_at, warm_col=warm_col, taper=1.2,
         vscale=23.0 / max(1.0, length))


def imp_arm(cv, ctrl, r0=30, r1=15, warm_at=None, warm_col=None, talons=None):
    """a serpentipede tentacle-arm (banded hide) ending in a clawed hand"""
    tube(cv, ctrl, r0, r1, TEX_IMP, bands=0.32, warm_at=warm_at, warm_col=warm_col, taper=0.8, vscale=0.7)
    hx, hy = ctrl[-1]
    # knuckle pad: a darker bulb
    tube(cv, [(ctrl[-2][0] * 0.15 + hx * 0.85, ctrl[-2][1] * 0.15 + hy * 0.85), (hx, hy)], r1 * 1.25, r1 * 1.05,
         TEX_IMP * 0.8, rim=0.18, warm_at=warm_at, warm_col=warm_col)
    for (ang, ln, cu) in talons or []:
        bx = hx + math.cos(ang) * r1 * 0.7; by = hy + math.sin(ang) * r1 * 0.7
        claw(cv, (bx, by), ang, ln, 5.5, cu, warm_at, warm_col)


def glow(cv, cx, cy, radius, col, power=2.0):
    x0, x1 = int(max(0, (cx - radius) * SS)), int(min(W, (cx + radius) * SS)); y0, y1 = int(max(0, (cy - radius) * SS)), int(min(H, (cy + radius) * SS))
    d = np.hypot(cv.xx[y0:y1, x0:x1] - cx * SS, cv.yy[y0:y1, x0:x1] - cy * SS) / (radius * SS)
    g = np.clip(1 - d, 0, 1) ** power
    cv.add(g[..., None] * np.array(col, np.float32), x0, y0)


def blit_sprite(cv, name, cx, cy, scale, bright=1.0):
    a = spr(name)
    h, w = a.shape[:2]
    im = Image.fromarray((a * 255).astype(np.uint8)).resize((int(w * scale * SS), int(h * scale * SS)), Image.BICUBIC)
    b = np.asarray(im).astype(np.float32) / 255
    x0 = int(cx * SS - b.shape[1] / 2); y0 = int(cy * SS - b.shape[0] / 2)
    xs, ys = max(0, -x0), max(0, -y0)
    b = b[ys:, xs:]; x0 += xs; y0 += ys
    b = b[:H - y0, :W - x0]
    cv.put(np.clip(b[..., 3], 0, 1), np.clip(b[..., :3] * bright, 0, 1.4), x0, y0)


# ------------------------------------------------------------------ noise (fire)
def value_noise(shape, cell, seed):
    rng = np.random.default_rng(seed)
    gh, gw = shape[0] // cell + 3, shape[1] // cell + 3
    g = rng.random((gh, gw)).astype(np.float32)
    y, x = np.mgrid[0:shape[0], 0:shape[1]].astype(np.float32) / cell
    xi, yi = x.astype(int), y.astype(int); xf, yf = x - xi, y - yi
    xf = xf * xf * (3 - 2 * xf); yf = yf * yf * (3 - 2 * yf)
    a = g[yi, xi]; b = g[yi, xi + 1]; c = g[yi + 1, xi]; d = g[yi + 1, xi + 1]
    return a + (b - a) * xf + (c - a) * yf + (a - b - c + d) * xf * yf


def fbm(shape, cell, seed, oct=4):
    out = 0; amp = 1; tot = 0
    for o in range(oct):
        out = out + value_noise(shape, max(2, cell >> o), seed + o) * amp; tot += amp; amp *= 0.5
    return out / tot


FIRE = [(0.0, (0, 0, 0)), (0.18, (0.35, 0.02, 0.0)), (0.38, (0.75, 0.12, 0.0)), (0.58, (1.0, 0.45, 0.02)),
        (0.78, (1.0, 0.78, 0.15)), (1.0, (1.0, 1.0, 0.75))]


def fire_ramp(v):
    xs = [p for p, _ in FIRE]; out = np.zeros(v.shape + (3,), np.float32)
    for k in range(3):
        out[..., k] = np.interp(v, xs, [c[k] for _, c in FIRE])
    return out


# ------------------------------------------------------------------ the frames
def zimp(f):
    cv = Canvas()
    talons_r = lambda base: [(base - 0.75, 30, -9), (base - 0.22, 38, -11), (base + 0.3, 34, -10), (base + 0.95, 22, -6)]
    if f == 'A':     # idle: arm low on the right, claws relaxed
        imp_arm(cv, [(310, 225), (296, 178), (262, 156), (232, 142)], talons=talons_r(-2.25))
    elif f == 'B':   # wind-up: drawn back high and to the right
        imp_arm(cv, [(345, 230), (330, 150), (310, 96), (284, 66)], r1=16, talons=talons_r(-2.55))
    elif f == 'C':   # swipe: across the screen, three claw slashes behind it
        xs = cv.xx / SS; ys = cv.yy / SS
        for k in range(3):
            d = np.abs(ys - (52 + k * 15 + (xs - 60) * 0.42))
            w = 2.6 * np.clip(np.sin(np.clip((xs - 40) / 230, 0, 1) * math.pi), 0, 1)
            span = (xs > 40) & (xs < 270)
            cv.put(np.clip(w * 2.2 - d, 0, 1) * 0.35 * span, np.broadcast_to(lin((160, 20, 10)), (H, W, 3)))
            cv.put(np.clip(w - d + 0.5, 0, 1) * 0.9 * span, np.broadcast_to(lin((235, 225, 190)) * (1 - 0.15 * k), (H, W, 3)))
        imp_arm(cv, [(320, 225), (262, 160), (196, 120), (150, 100)], r0=31, r1=16, talons=talons_r(-2.95))
    elif f == 'D':   # follow-through: low on the left
        imp_arm(cv, [(310, 228), (240, 200), (150, 178), (88, 166)], r0=31, r1=15, talons=talons_r(3.05))
    return cv


def zimf(f):
    cv = Canvas()
    fx, fy = 160, 118
    warm = np.array([1.0, 0.55, 0.12]) * {'A': 0.35, 'B': 0.9, 'C': 0.55}[f]
    if f == 'C': fx, fy = 160, 96
    spread = {'A': 0, 'B': 4, 'C': 18}[f]
    tal_l = [(-0.95, 24, 8), (-0.35, 29, 9), (0.25, 24, 8)]
    tal_r = [(math.pi + 0.95, 24, -8), (math.pi + 0.35, 29, -9), (math.pi - 0.25, 24, -8)]
    # fire behind the hands first (it shows between them)
    if f == 'A':
        glow(cv, fx, fy, 22, (0.9, 0.4, 0.05), 2.2)
        blit_sprite(cv, 'BAL1A0', fx, fy, 1.4, 1.0)
    elif f == 'B':
        glow(cv, fx, fy, 70, (0.75, 0.35, 0.05), 2.0)
        blit_sprite(cv, 'BAL1B0', fx, fy, 3.2, 1.25)
        glow(cv, fx, fy, 18, (1.0, 0.95, 0.6), 1.4)
    else:
        glow(cv, fx, fy, 40, (0.8, 0.35, 0.05), 2.0)
        blit_sprite(cv, 'BAL1A0', fx, fy, 2.0, 1.15)
    imp_arm(cv, [(20, 230), (58, 180), (100 - spread, 152), (122 - spread, 132 + spread * 0.4)], r0=30, r1=15,
            warm_at=(fx, fy), warm_col=warm, talons=tal_l)
    imp_arm(cv, [(300, 230), (262, 180), (220 + spread, 152), (198 + spread, 132 + spread * 0.4)], r0=30, r1=15,
            warm_at=(fx, fy), warm_col=warm, talons=tal_r)
    return cv


def zdmn(f):
    """the flesh worm's star mouth framing the screen: six spiked petals with serrated edges"""
    cv = Canvas()
    tip = {'A': 128, 'B': 152, 'C': 30, 'D': 78}[f]
    rot = {'A': 0.0, 'B': 0.04, 'C': -0.02, 'D': 0.09}[f]
    cx, cy = 160 * SS, 96 * SS
    X = (cv.xx - cx) / SS; Y = (cv.yy - cy) / SS * 1.25
    r = np.hypot(X, Y); th = np.arctan2(Y, X)
    R = 260.0
    best = np.full((H, W), -1.0, np.float32); S_ = np.zeros((H, W), np.float32); T_ = np.zeros((H, W), np.float32)
    for k in range(6):
        phi = rot + k * math.pi / 3 + math.pi / 6
        dth = (th - phi + math.pi) % (2 * math.pi) - math.pi
        frac = np.clip((r - tip) / (R - tip), 0, 1)
        half = (math.pi / 6) * 1.18 * frac ** 0.55
        s = dth / np.maximum(half, 1e-3)
        inside = (r > tip) & (np.abs(s) < 1)
        upd = inside & (np.abs(s) < np.abs(np.where(best >= 0, S_, 9)))
        best = np.where(upd, k, best); S_ = np.where(upd, s, S_); T_ = np.where(upd, frac, T_)
    m = best >= 0
    # throat behind the petals: dark red going black at the edges
    # throat behind the petals: only at the screen edges while open, all round when it bites
    reach = {'A': 175, 'B': 200, 'C': 40, 'D': 105}[f]
    throat = np.clip((r - reach) / 60, 0, 1)
    gum = np.clip((r - reach) / 120, 0, 1)
    cv.put(throat * (1 - m), lin((130, 14, 12)) * (1 - gum)[..., None] + lin((28, 0, 2)) * gum[..., None])
    s = S_; t = T_
    nz = np.sqrt(np.clip(1 - s * s, 0, 1)) * 0.9 + 0.1
    ang = np.arctan2(Y, X)
    # the petal's across-direction is tangential
    tx, ty = -np.sin(ang), np.cos(ang)
    nrm = np.stack([tx * s, ty * s, nz], -1); nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    flesh = tex_sample(TEX_WORM, s, t * 40)
    mouth = tex_sample(TEX_WORM_MOUTH, s, t * 30)
    base = flesh * (0.35 + 0.65 * t[..., None]) + mouth * (1 - t[..., None]) * 0.9
    col = shade(nrm, base * 1.15, amb=0.3, spec=0.45, power=14)
    # veins
    vein = (np.abs(np.sin(s * 5.0 + t * 23)) < 0.08) & (t > 0.25)
    col = np.where(vein[..., None], col * 0.6 + lin((90, 0, 10)) * 0.4, col)
    # serrated teeth along both edges near the tip
    dist_r = r - tip
    saw = 1 - 2 * np.abs(((dist_r / 9.0) % 1) - 0.5)
    tooth = m & (np.abs(s) > 0.62 + 0.3 * (1 - saw)) & (dist_r < 95)
    ivory = shade(nrm, np.broadcast_to(lin((228, 212, 170)), nrm.shape), amb=0.45, spec=0.6, power=20)
    col = np.where(tooth[..., None], ivory * (1 - 0.3 * (np.abs(s) > 0.97))[..., None], col)
    # dark rim
    col = col * (1 - 0.7 * np.clip((np.abs(s) - 0.93) / 0.07, 0, 1) * ~tooth)[..., None]
    if f == 'D':
        col = col * np.array([1.15, 0.8, 0.8])
    cv.put(m.astype(np.float32), col)
    if f == 'C':   # a bite: spit/blood flecks in the closing gap
        for _ in range(26):
            a = RNG.random() * 2 * math.pi; rr = 20 + RNG.random() * 40
            glow(cv, 160 + math.cos(a) * rr, 96 + math.sin(a) * rr * 0.8, 3 + RNG.random() * 3, (0.55, 0.0, 0.02), 1.0)
    return cv


def zskl(f):
    """the deadflare: its flesh brow at the bottom, wreathed in its own fire"""
    cv = Canvas()
    X = cv.xx / SS; Y = cv.yy / SS
    heat = {'A': 0.55, 'B': 1.0, 'C': 0.85}[f]
    if f == 'C':
        # dash: flames stream back along the screen edges
        cxs, cys = 160, 100
        dx, dy = X - cxs, (Y - cys) * 1.4
        rr = np.hypot(dx, dy); an = np.arctan2(dy, dx)
        n = fbm((H, W), 48, 7)
        streak = value_noise((H, W), 6, 11)
        polar = np.sin(an * 23 + n * 6) * 0.5 + 0.5
        f_ = np.clip((rr - 95) / 120, 0, 1) * (0.55 + 0.45 * polar) * (0.6 + 0.6 * n)
        f_ = np.clip(f_ * 1.5, 0, 1)
    else:
        # tongues: noise stretched upwards, so the flames rise in licks rather than a flat band
        n = np.asarray(Image.fromarray(fbm((H // 4, W), 40, 3 if f == 'A' else 5)).resize((W, H), Image.BILINEAR))
        cols = np.asarray(Image.fromarray(value_noise((2, W + 64), 26, 9)[:, :W]).resize((W, H), Image.BILINEAR))
        top = 178 - (40 if f == 'A' else 110) * heat - 40 * cols
        edge = np.minimum(X, VW - X)
        side = np.clip(1 - edge / (22 + 50 * heat * (0.6 + 0.8 * n)), 0, 1) * np.clip((Y - 20) / 140, 0, 1)
        bottom = np.clip((Y - top) / np.maximum(200 - top, 1), 0, 1)
        f_ = np.clip(np.maximum(bottom, side) * (0.55 + 0.9 * n) - 0.2, 0, 1)
        f_ = np.clip(f_ * 1.6, 0, 1)
    col = fire_ramp(f_ * heat ** 0.3)
    cv.put(np.clip(f_ * 2.5, 0, 1), col)
    # the brow: the top of the deadflare's flesh orb
    bcx, bcy, brx, bry = 160, 268 if f != 'C' else 276, 150, 105
    d = ((X - bcx) / brx) ** 2 + ((Y - bcy) / bry) ** 2
    m = np.clip((1 - d) * 60, 0, 1)
    nx = (X - bcx) / brx; ny = (Y - bcy) / bry
    nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0, 1))
    nrm = np.stack([nx, ny, nz + 0.2], -1); nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    th_, tw_ = TEX_SOUL.shape[:2]
    big = np.asarray(Image.fromarray((TEX_SOUL * 255).astype(np.uint8)).resize((tw_ * 8, th_ * 8), Image.BICUBIC)).astype(np.float32) / 255
    u = ((np.clip(nx, -1, 1) * 0.5 + 0.5) * (big.shape[1] - 1)).astype(int)
    v = (np.clip(ny + 1, 0, 1) * (big.shape[0] - 1) * 0.9).astype(int)
    base = big[v, u]
    rim_fire = np.clip(1 - nz * 2.2, 0, 1)[..., None] * np.array([1.0, 0.45, 0.05]) * heat
    col = shade(nrm, base * 1.1, amb=0.3, spec=0.4, power=16, warm=rim_fire)
    # the burning core glows through the flesh at the centre
    core = np.clip(1 - np.hypot((X - 160) / 34, (Y - (183 if f != 'C' else 190)) / 16), 0, 1) ** 1.5
    col = col + core[..., None] * np.array([1.0, 0.6, 0.1]) * (0.6 + 0.6 * heat)
    cv.put(m, col)
    if f == 'B':
        for _ in range(40):   # sparks
            glow(cv, 20 + RNG.random() * 280, 40 + RNG.random() * 120, 1.5 + RNG.random() * 1.5, (1.0, 0.85, 0.4), 1.0)
    return cv


# ------------------------------------------------------------------ to the Doom palette
def finish(cv):
    rgb = cv.rgb.reshape(VH, SS, VW, SS, 3).mean((1, 3))
    a = cv.a.reshape(VH, SS, VW, SS).mean((1, 3))
    op = a >= 0.5
    # crisp 1-pixel dark outline where the shape meets the screen (Doom sprites read best with one)
    nb = np.zeros_like(op)
    nb[1:] |= ~op[:-1]; nb[:-1] |= ~op[1:]; nb[:, 1:] |= ~op[:, :-1]; nb[:, :-1] |= ~op[:, 1:]
    outline = op & nb
    rgb = np.where(outline[..., None], rgb * 0.55, rgb)
    rgb = np.clip(rgb, 0, 1) * 255
    # nearest palette colour, weighted for perceived brightness
    wts = np.array([0.30, 0.59, 0.11], np.float32) * 3
    pal = PALF[PAL_OK]
    flat = rgb[op]
    best = np.zeros(len(flat), int)
    for i in range(0, len(flat), 20000):
        c = flat[i:i + 20000]
        d = (((c[:, None, :] - pal[None]) ** 2) * wts).sum(-1)
        best[i:i + 20000] = PAL_OK[d.argmin(1)]
    out = np.zeros((VH, VW, 4), np.uint8)
    out[op, :3] = assets.PAL[best]
    out[op, 3] = 255
    return out


def crop(img):
    ys, xs = np.nonzero(img[..., 3])
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    return img[y0:y1, x0:x1], (int(1 - x0), int(16 - y0))


BUILD = {'ZIMP': zimp, 'ZIMF': zimf, 'ZDMN': zdmn, 'ZSKL': zskl}


def main():
    out = sys.argv[1]
    sheet = sys.argv[sys.argv.index('--sheet') + 1] if '--sheet' in sys.argv else None
    os.makedirs(out, exist_ok=True)
    offs = {}; full = {}
    for sp, frames in FRAMES.items():
        for f in frames:
            img = finish(BUILD[sp](f))
            full[sp + f] = img
            c, o = crop(img)
            name = sp + f + '0'
            Image.fromarray(c).save(os.path.join(out, name.lower() + '.png'))
            offs[name] = list(o)
            print(name, c.shape[1], 'x', c.shape[0], 'offsets', o, 'colours', len(np.unique(c[c[..., 3] > 0][:, :3], axis=0)))
    json.dump(offs, open(os.path.join(out, 'offsets.json'), 'w'), indent=1)
    if sheet:
        contact(full, sheet)


def contact(full, path):
    """every frame over a Doom-ish view (a wall texture and a floor), 2x, with the status bar line at 168"""
    wall = assets.texture('BRONZE1')
    if wall is None:
        wall = np.full((128, 64, 4), 90, np.uint8)
    bg = np.zeros((VH, VW, 3), np.uint8)
    for y in range(0, 100):
        for x in range(0, VW, wall.shape[1]):
            bg[y, x:x + wall.shape[1]] = wall[y % wall.shape[0], :min(wall.shape[1], VW - x), :3]
    bg[:100] = (bg[:100] * 0.7).astype(np.uint8)
    bg[100:] = np.array([60, 52, 44], np.uint8)
    cells = []
    for name, img in full.items():
        c = bg.copy()
        m = img[..., 3] > 0
        c[m] = img[m, :3]
        c[168:] = (c[168:] * 0.35).astype(np.uint8)
        cells.append((name, Image.fromarray(c).resize((VW * 2, VH * 2), Image.NEAREST)))
    cols = 4; rows = (len(cells) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * (VW * 2 + 8), rows * (VH * 2 + 8)), (20, 20, 24))
    from PIL import ImageDraw
    dr = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(cells):
        x = (i % cols) * (VW * 2 + 8); y = (i // cols) * (VH * 2 + 8)
        sheet.paste(im, (x, y)); dr.text((x + 6, y + 4), name, fill=(255, 255, 0))
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    sheet.save(path)
    print('sheet', path, sheet.size)


if __name__ == '__main__':
    main()
