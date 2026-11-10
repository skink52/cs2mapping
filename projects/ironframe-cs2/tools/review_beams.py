"""Before / after sheet for the hitscan beams (laser rifle, laser cannon, rail, sniper, drones): preview/fx/beam_before_after.png and
preview/fx/beam_profile.png. A software render of what 30_render.js draws, seen from behind the shooter's right shoulder, at three ranges, on a night (Sprawl) and a day (Dunes) backdrop.
  before  one 100 u tube (r 2.5 cyan / 3.0 red) scaled uniformly by range / 180: the width grows with the range and the beam
          stops at 56 % of the way (100 u x range / 180)
  after   the ladder from tools/fx.py: beamPick's rung and scale (the same arithmetic as the script, tools/review_beams.py pick()),
          a self-lit core + four additive shells; "charged" = the thick tier (w 1.4)
The additive shells are composited the way the engine blends them (colour added where the depth test passes, no depth write) and
a mild bloom is put over both columns alike. It shows shape, width and length, not the engine's exact tone mapping.
usage: python -I tools/review_beams.py
"""
import math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fx as FX                                              # noqa: E402

OUTD = os.path.join(PROJ, 'preview', 'fx')
SS = 2


def pick(l, w=1.0, lengths=FX.BEAM_LENGTHS):
    """the script's beamPick: the rung nearest l / w on a log scale -> (length, scale); the drawn width is the scale"""
    want = max(1.0, l) / max(0.5, min(1.5, w))
    best = min(lengths, key=lambda L: abs(math.log(L / want)))
    return best, max(0.5, min(1.8, l / best))


def box_tris(c, s, col):
    cx, cy, cz = c; hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
    v = np.array([[cx + dx * hx, cy + dy * hy, cz + dz * hz] for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)])
    q = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    out = []
    for a, b, c_, d in q:
        n = np.cross(v[b] - v[a], v[c_] - v[a]); n = n / np.linalg.norm(n)
        sh = 0.55 + 0.45 * max(0.0, float(n @ np.array([-0.3, -0.4, 0.86])))
        out += [(v[[a, b, c_]], tuple(x * sh for x in col), 0), (v[[a, c_, d]], tuple(x * sh for x in col), 0)]
    return out


def mech(at, yaw_deg, col):
    """the placeholder box mech (288 u), feet at `at`"""
    parts = [((0, -32, 82.5), (44, 40, 165)), ((0, 32, 82.5), (44, 40, 165)), ((4, 0, 210), (90, 120, 120)), ((14, 0, 275), (40, 44, 26)),
             ((-10, -72, 215), (30, 24, 90)), ((-10, 72, 215), (30, 24, 90))]
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg)); R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])
    out = []
    for ctr, size in parts:
        for P, colr, kind in box_tris(ctr, size, col): out.append((P @ R.T + np.array(at), colr, kind))
    return out


def place(tris, frm, to, scale):
    """model-space [(P, colour, kind)] with +x forward -> world: scaled, x along frm->to"""
    d = np.array(to, float) - np.array(frm, float); d /= np.linalg.norm(d)
    up = np.array([0, 0, 1.0]); r = np.cross(up, d); r /= np.linalg.norm(r); u = np.cross(d, r)
    M = np.stack([d, r, u], 1)
    return [((P * scale) @ M.T + np.array(frm, float), col, kind) for P, col, kind in tris]


def old_beam(red):
    import geo
    m = geo.tube([(0, 0, 0), (100, 0, 0)], [3.0 if red else 2.5] * 2, sides=8, mat='m')
    col = (1.0, 0.27, 0.24) if red else (0.35, 0.88, 1.0)
    return [(m.V[f], tuple(c * 2.2 for c in col), 0) for f in m.F]


def new_beam(L, c):
    colr = FX.BEAM_COLORS[c]; core = tuple(x / 255 * 2.4 for x in colr['core']); out = []
    for P, UV, mat in FX.beam_tris(float(L)):
        if mat == 'core': out.append((P, core, 0))
        else:
            b = FX.BEAM_SHELLS[min(len(FX.BEAM_SHELLS) - 1, int(UV[0][0] * FX.BEAM_COLS))][1]
            out.append((P, tuple(x / 255 * b * 1.6 for x in colr['glow']), 1))
    return out


def render(tris, eye, target, W, H, fov, bg_top, bg_bot, ground):
    """z-buffered flat triangles (kind 0) + additive ones (kind 1: both faces add, depth-tested, no depth write) -> float image"""
    w, h = W * SS, H * SS
    f = np.array(target, float) - np.array(eye, float); f /= np.linalg.norm(f)
    r = np.cross(f, [0, 0, 1.0]); r /= np.linalg.norm(r); u = np.cross(r, f)
    fl = (w / 2) / math.tan(math.radians(fov) / 2)
    img = np.zeros((h, w, 3)); zb = np.full((h, w), 1e12)
    # backdrop: sky gradient above the horizon, ground below
    ys = np.arange(h)[:, None]; hz = h / 2 + fl * (f[2] / max(1e-6, math.hypot(f[0], f[1])))
    t = np.clip(ys / max(1.0, hz), 0, 1)
    img[:] = np.where((ys < hz)[..., None], np.array(bg_top)[None, None] * (1 - t[..., None]) + np.array(bg_bot)[None, None] * t[..., None],
                      np.array(ground)[None, None] * (0.75 + 0.25 * np.clip((ys - hz) / max(1.0, h - hz), 0, 1))[..., None])
    add = np.zeros_like(img)

    def proj(P):
        d = P - np.array(eye, float); z = d @ f
        return np.stack([w / 2 + fl * (d @ r) / np.maximum(z, 1e-3), h / 2 - fl * (d @ u) / np.maximum(z, 1e-3), z], 1)

    def raster(P, col, kind):
        S = proj(P)
        if (S[:, 2] < 4.0).any(): return
        x0, x1 = int(max(0, math.floor(S[:, 0].min()))), int(min(w - 1, math.ceil(S[:, 0].max())))
        y0, y1 = int(max(0, math.floor(S[:, 1].min()))), int(min(h - 1, math.ceil(S[:, 1].max())))
        if x0 > x1 or y0 > y1: return
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = S
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-9: return
        l0 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / den; l1 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / den; l2 = 1 - l0 - l1
        inside = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
        if not inside.any(): return
        z = l0 * az + l1 * bz + l2 * cz
        zs = zb[y0:y1 + 1, x0:x1 + 1]
        if kind == 0:
            m = inside & (z < zs); zs[m] = z[m]; img[y0:y1 + 1, x0:x1 + 1][m] = col
        else:
            m = inside & (z < zs); add[y0:y1 + 1, x0:x1 + 1][m] += col

    for P, col, kind in tris:
        if kind == 0: raster(P, col, 0)
    for P, col, kind in tris:
        if kind == 1: raster(P, col, 1)
    img += add
    # mild bloom of what is over 1.0 (the engine's bloom on self-lit surfaces), the same for every panel
    hot = np.clip(img - 0.9, 0, 4)
    hi = Image.fromarray((np.clip(hot / 4, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.2 * SS))
    img = img + np.asarray(hi, float) / 255 * 4 * 0.55
    out = Image.fromarray((np.clip(img, 0, 1) ** (1 / 1.0) * 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
    return out


def font(sz):
    for f in ('C:/Windows/Fonts/segoeui.ttf', 'C:/Windows/Fonts/arial.ttf'):
        if os.path.exists(f): return ImageFont.truetype(f, sz)
    return ImageFont.load_default()


THEMES = {'night (Sprawl)': dict(top=(0.02, 0.03, 0.07), bot=(0.07, 0.09, 0.16), ground=(0.05, 0.055, 0.07), mech=(0.20, 0.22, 0.27)),
          'day (Dunes)': dict(top=(0.36, 0.55, 0.82), bot=(0.80, 0.83, 0.85), ground=(0.70, 0.60, 0.42), mech=(0.42, 0.42, 0.44))}


def panel(theme, rng, mode, red, W=460, H=260):
    th = THEMES[theme]
    muzzle = np.array([80.0, -53.0, 150.0]); tgt = np.array([float(rng), 0.0, 150.0])
    tris = mech((0, 0, 0), 0, th['mech']) + mech((rng + 40, 0, 0), 180, th['mech'])
    l = float(np.linalg.norm(tgt - muzzle))
    if mode == 'before':
        s = max(0.2, min(60, l / 180)); tris += place(old_beam(red), muzzle, tgt, s); note = 'scale %.1f: %.0f u wide, ends at %.0f u of %.0f' % (s, 2 * (3.0 if red else 2.5) * s, 100 * s, l)
    else:
        L, s = pick(l, 1.4 if mode == 'charged' else 1.0)
        tris += place(new_beam(L, 'r' if red else 'c'), muzzle, tgt, s); note = 'rung %d x %.2f: core %.1f u, glow %.0f u wide, full length' % (L, s, 2 * FX.BEAM_CORE_R * s, 2 * FX.BEAM_GLOW_R * s)
    eye = (-430.0, -560.0, 330.0); look = (min(rng, 2600) * 0.42, 0.0, 150.0)       # over the right shoulder, off to the side: shooter, beam and target in view
    return render(tris, eye, look, W, H, 74, th['top'], th['bot'], th['ground']), note


def sheet():
    os.makedirs(OUTD, exist_ok=True)
    W, H, pad, lab = 460, 260, 8, 22
    cols = [('before', 'BEFORE'), ('after', 'AFTER'), ('charged', 'AFTER, full charge (w 1.4)')]
    rows = [(th, rng, red) for th in THEMES for rng, red in ((700, True), (2600, True), (6000, False))]
    im = Image.new('RGB', (pad + len(cols) * (W + pad), 60 + len(rows) * (H + lab + pad)), (16, 18, 22)); d = ImageDraw.Draw(im)
    d.text((pad, 8), 'IRONFRAME hitscan beams: before / after (tools/review_beams.py)  from behind the right shoulder, target mech at the range shown', fill=(235, 235, 235), font=font(18))
    for ci, (mode, title) in enumerate(cols): d.text((pad + ci * (W + pad), 36), title, fill=(255, 210, 120), font=font(15))
    for ri, (th, rng, red) in enumerate(rows):
        for ci, (mode, title) in enumerate(cols):
            p, note = panel(th, rng, mode, red)
            x, y = pad + ci * (W + pad), 60 + ri * (H + lab + pad)
            im.paste(p, (x, y))
            d.text((x + 2, y + H + 2), '%s, %d u, %s: %s' % (th, rng, 'red' if red else 'cyan', note), fill=(200, 200, 205), font=font(12))
        print('row %d / %d' % (ri + 1, len(rows)), flush=True)
    out = os.path.join(OUTD, 'beam_before_after.png'); im.save(out); print('wrote', out)


def profile():
    """side-on close-up, the same world scale in every strip: the width against the range, and the two ends of the new beam"""
    os.makedirs(OUTD, exist_ok=True)
    W, H = 1380, 120
    im = Image.new('RGB', (W + 16, 40 + 9 * (H + 26)), (16, 18, 22)); d = ImageDraw.Draw(im)
    d.text((8, 8), 'Beam width against range, side-on, 1 px = 0.5 u (a 288 u mech would be 576 px tall). Mid-beam unless said.', fill=(235, 235, 235), font=font(16))
    y = 40
    def strip(tris, label, cx):
        nonlocal y
        eye = (cx, -4000.0, 0.0); p = render(tris, eye, (cx, 0, 0), W, H, 2 * math.degrees(math.atan((W / 4) / 4000.0)), (0.03, 0.035, 0.06), (0.03, 0.035, 0.06), (0.03, 0.035, 0.06))
        im.paste(p, (8, y)); d.text((10, y + H + 3), label, fill=(200, 200, 205), font=font(13)); y += H + 26
    for rng in (700, 2600, 6000):
        s = max(0.2, min(60, rng / 180))
        strip(place(old_beam(True), (0, 0, 0), (1, 0, 0), s), 'before, %d u shot: tube %.0f u wide (and only %.0f u long)' % (rng, 6 * s, 100 * s), min(50 * s, 50 * s))
    for rng in (700, 2600, 6000):
        L, s = pick(rng)
        strip(place(new_beam(L, 'r'), (0, 0, 0), (1, 0, 0), s), 'after, %d u shot: rung %d x %.2f, core %.1f u, glow %.0f u' % (rng, L, s, 2 * FX.BEAM_CORE_R * s, 2 * FX.BEAM_GLOW_R * s), rng / 2)
    L, s = pick(2600, 1.4)
    strip(place(new_beam(L, 'r'), (0, 0, 0), (1, 0, 0), s), 'after, 2600 u, full charge: rung %d x %.2f, core %.1f u, glow %.0f u' % (L, s, 2 * FX.BEAM_CORE_R * s, 2 * FX.BEAM_GLOW_R * s), 1300)
    L, s = pick(2600)
    strip(place(new_beam(L, 'c'), (0, 0, 0), (1, 0, 0), s), 'after, cyan, the muzzle end (first 690 u): swells out of the barrel', 330)
    strip(place(new_beam(L, 'c'), (0, 0, 0), (1, 0, 0), s), 'after, cyan, the far end (last 690 u): tapers to a point at the hit', 2600 - 330)
    out = os.path.join(OUTD, 'beam_profile.png'); im.save(out); print('wrote', out)


if __name__ == '__main__':
    profile(); sheet()
