"""Zombie first-person view frames (the zombie's "weapon" psprites), drawn the way Doom's own weapon sprites are:
on the 320x200 screen grid, one palette index per pixel (Freedoom PLAYPAL), hard edges, banded light ramps, dark
1-pixel rims. Nothing is rendered at high resolution and nothing is anti-aliased; hud.py scales the result 6x nearest
like PISG/SHTG/PUNG, so every pixel here is a pixel on screen.

The creatures' own sprites are the source of every colour and of the shapes:
- serpentipede (TROO): its tentacle browns (palette 69-79, 238/239, 1/2) for the arm and finger-tentacles, the gold of
  its body stripes and feet (160-167) for the stripes on the forearm and the talons. One clawed hand on the right, like
  the fist in PUNG; two hands framing the fireball. The fireball is BAL1's own frames (A/B native, B also Scale2x'd for
  the "held up close" frame), full bright.
- flesh worm (SARG): its pink flesh ramp (17-47) and the six-petal star mouth from SARGE/SARGF, seen from inside: the
  petals (with a dark central groove and bone teeth on the edges) close in from the screen edges, the throat (36-47 to
  black) behind them.
- deadflare (SKUL): the wrinkled orb flesh (52-79) as the lower rim of the view, its red hooked legs (20-47) curling up
  from the bottom corners, and its flare: yellow crackle bolts like SKULC/SKULD and flame tongues in the fire yellows
  and oranges (224-231, 161, 213-235).

Lighting: one light from the upper left in front (like the Freedoom weapons), quantised to the material's ramp; a
fixed per-pixel grain and a soft mottle (seeded, so every run is identical) break the bands the way the hand-painted
sprites do. Every part gets its own darkest-ramp rim where it meets the background or a part behind it.

usage: zviews.py <out_dir> [--sheet preview/zviews_sheet.png] [--ingame preview/zviews_ingame.png]
writes <out_dir>/<SPR><F>0.png (RGBA, 1 pixel = 1 Doom pixel) and <out_dir>/offsets.json {name: [left, top]}, offsets in
the weapon-sprite convention hud.py uses (screen x = 1 - left, screen y = 16 - top on the 320x200 screen; frames run on
to y 200 so the bob never shows an edge; nothing touches the left/right edge of the 4:3 view, which would show as a
hard cut on a 16:9 screen). The sheet shows every frame at 4x over a Freedoom wall (STARTAN3/FLOOR4_8) with PISGA,
SHTGA and PUNGB placed the same way for comparison, the blue line marking the idle limit; a 2x copy is written next
to it as zviews_zoom.png. --ingame writes four 1920x1080 mock screens (ZIMPA, ZIMFB, ZDMNA, ZSKLA) with the status
bar at hud.py's 85% scale, which covers y 171-200 of the view the way Doom's covers the weapons' lower edge.

Frames (STATUS.md contract): ZIMP A-D imp claw (A idle, B wind-up, C swipe, D follow-through); ZIMF A-C imp fireball
(A cupped hands, B bright fireball, C release); ZDMN A-D flesh-worm jaws (A idle, B open, C bite, D lunge);
ZSKL A-C deadflare (A idle, B flare, C dash). Idle frames start no higher than y 122 (SHTGA starts at 123), so above
the status bar they show about as much as the shotgun does.
"""
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets

VW, VH = 320, 200
FRAMES = {'ZIMP': 'ABCD', 'ZIMF': 'ABC', 'ZDMN': 'ABCD', 'ZSKL': 'ABC'}
IDLE_TOP = 122                      # idle frames stay below this line, like SHTGA (top at 123)
PAL = assets.PAL
LIGHT = np.array([-0.58, -0.68, 0.42]); LIGHT = LIGHT / np.linalg.norm(LIGHT)   # x right, y down, z to the viewer

# ---------------------------------------------------------------- ramps (palette indices, light -> dark)
R_TENT = [68, 70, 72, 73, 74, 75, 76, 77, 78, 79, 238, 239, 1, 2]       # TROO tentacles
R_GOLD = [160, 161, 162, 163, 164, 165, 166, 167, 239, 2]                 # TROO body stripes / feet
R_HORN = [225, 160, 161, 162, 163, 164, 165, 166, 167, 238, 2]            # talons: pale point, gold, dark root
R_FLESH = list(range(18, 48)) + [2]                                       # SARG flesh
R_THROAT = [38, 40, 42, 44, 45, 46, 47, 2, 0]                             # SARG mouth inside
R_BONE = [225, 50, 128, 130, 132, 134, 137, 140, 143, 2]                   # teeth
R_SKIN = list(range(52, 76)) + [77, 79, 239]                              # SKUL orb
R_LEG = [20, 22, 24, 26, 28, 30, 32, 35, 38, 41, 44, 47, 2]               # SKUL legs
R_FIRE = [225, 226, 227, 229, 231, 161, 162, 213, 214, 215, 216, 218, 220, 222, 232, 234, 235, 167]
R_GLOW = [225, 227, 231, 161, 213, 215, 218, 222, 232]                    # lit cracks


# ---------------------------------------------------------------- deterministic noise
def _hash(x, y, seed):
    h = (x.astype(np.int64) * 374761393 + y.astype(np.int64) * 668265263 + seed * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


YY, XX = np.mgrid[0:VH, 0:VW]
PX, PY = XX + 0.5, YY + 0.5


def grain(seed):
    return _hash(XX, YY, seed)


def vnoise(cell, seed):
    """smooth value noise over the screen, cell in pixels, [0, 1]"""
    gx, gy = XX / cell, YY / cell
    x0, y0 = np.floor(gx).astype(int), np.floor(gy).astype(int)
    fx, fy = gx - x0, gy - y0
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _hash(x0, y0, seed), _hash(x0 + 1, y0, seed)
    c, d = _hash(x0, y0 + 1, seed), _hash(x0 + 1, y0 + 1, seed)
    return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy


# ---------------------------------------------------------------- frame + painting
# the view panel is 4:3 inside a 16:9 screen, so anything reaching the left/right edge of the 320 frame would show a
# hard vertical cut beside the world. Full-view frames therefore stay inside this oval (the screen top and bottom are
# real screen edges and may be cut); the claws and hands simply keep off the sides.
OVAL = np.hypot((PX - 160) / 157.0, (PY - 100) / 175.0)


class Frame:
    def __init__(self, oval=False):
        self.idx = np.full((VH, VW), -1, np.int16)
        self.clip = OVAL < 1 if oval else np.ones((VH, VW), bool)


def border(mask):
    """pixels of mask with a 4-neighbour outside it (the screen edge counts as inside, so cut-offs get no rim)"""
    p = np.pad(mask, 1, mode='edge')
    inner = p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    return mask & ~inner


def paint(fr, mask, v, ramp, seed=0, gr=0.05, mottle=0.07, cell=4.0, rim=1, rim_v=None):
    """quantise light v (0 dark .. 1 light) to ramp with grain + mottle; rim: darkest-ramp outline pixels"""
    mask = mask & fr.clip
    if not mask.any():
        return
    v = v + (grain(seed) - 0.5) * 2 * gr + (vnoise(cell, seed + 7) - 0.5) * 2 * mottle
    n = len(ramp)
    k = np.clip(np.round((1 - v) * (n - 1)), 0, n - 1).astype(int)
    col = np.asarray(ramp)[k]
    if rim:
        e = border(mask)
        if rim == 'bg':
            p = np.pad(fr.idx < 0, 1, constant_values=False)
            e &= p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
        col = np.where(e, ramp[-1] if rim_v is None else np.asarray(ramp)[np.clip(np.round((1 - rim_v) * (n - 1)), 0, n - 1).astype(int)], col)
    fr.idx[mask] = col[mask]


def light(nx, ny, nz, amb=0.16, diff=0.84, spec=0.18, power=10):
    d = np.clip(nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2], 0, 1)
    h = LIGHT + np.array([0, 0, 1.0]); h = h / np.linalg.norm(h)
    s = np.clip(nx * h[0] + ny * h[1] + nz * h[2], 0, 1) ** power
    return amb + diff * d + spec * s


# ---------------------------------------------------------------- swept tubes (arms, fingers, talons, petals, legs)
def bez(ctrl, t):
    ctrl = np.asarray(ctrl, float); t = np.asarray(t, float)[:, None]
    n = len(ctrl) - 1
    return sum(math.comb(n, i) * (1 - t) ** (n - i) * t ** i * ctrl[i] for i in range(n + 1))


class Tube:
    """a tube swept along a bezier; per pixel: inside mask, s (-1..1 across), t (0..1 along), the unit direction"""

    def __init__(self, ctrl, r0, r1, taper=1.0, n=96, rfun=None):
        P = bez(ctrl, np.linspace(0, 1, n + 1))
        self.P = P
        self.length = float(np.hypot(*np.diff(P, axis=0).T).sum())
        rf = rfun or (lambda t: r0 + (r1 - r0) * t ** taper)
        rmax = max(r0, r1) + 2
        x0, x1 = int(max(0, P[:, 0].min() - rmax)), int(min(VW, P[:, 0].max() + rmax + 1))
        y0, y1 = int(max(0, P[:, 1].min() - rmax)), int(min(VH, P[:, 1].max() + rmax + 1))
        self.mask = np.zeros((VH, VW), bool)
        self.s = np.zeros((VH, VW)); self.t = np.zeros((VH, VW))
        self.dx = np.zeros((VH, VW)); self.dy = np.zeros((VH, VW))
        if x0 >= x1 or y0 >= y1:
            return
        px, py = PX[y0:y1, x0:x1], PY[y0:y1, x0:x1]
        best = np.full(px.shape, 1e9); bs = np.zeros(px.shape); bt = np.zeros(px.shape)
        bdx = np.zeros(px.shape); bdy = np.zeros(px.shape); bin_ = np.zeros(px.shape, bool)
        for i in range(n):
            ax, ay = P[i]; bx, by = P[i + 1]
            abx, aby = bx - ax, by - ay
            L2 = abx * abx + aby * aby
            if L2 < 1e-9:
                continue
            apx, apy = px - ax, py - ay
            h = np.clip((apx * abx + apy * aby) / L2, 0, 1)
            qx, qy = apx - h * abx, apy - h * aby
            d = np.hypot(qx, qy)
            tt = (i + h) / n
            r = np.maximum(rf(tt), 1e-3)
            score = d - r
            upd = score < best
            Ln = math.sqrt(L2)
            cross = (abx * apy - aby * apx) / Ln
            best = np.where(upd, score, best)
            bs = np.where(upd, np.clip(cross / r, -1, 1), bs)
            bt = np.where(upd, tt, bt)
            bdx = np.where(upd, abx / Ln, bdx); bdy = np.where(upd, aby / Ln, bdy)
            bin_ = np.where(upd, d < r, bin_)
        self.mask[y0:y1, x0:x1] = bin_
        self.s[y0:y1, x0:x1] = bs; self.t[y0:y1, x0:x1] = bt
        self.dx[y0:y1, x0:x1] = bdx; self.dy[y0:y1, x0:x1] = bdy

    def normal(self):
        s = self.s
        nz = np.sqrt(np.clip(1 - s * s, 0, 1))
        nx, ny = -self.dy * s, self.dx * s
        return nx, ny, nz

    def end(self, back=0.0):
        """point and unit direction at the end of the curve (back: fraction of the curve before the end)"""
        i = int(round((1 - back) * (len(self.P) - 1)))
        i = max(1, i)
        d = self.P[i] - self.P[i - 1]
        return self.P[i], d / (np.linalg.norm(d) + 1e-9)


def shade_tube(tb, amb=0.16, ridge=0.0, warm=None):
    nx, ny, nz = tb.normal()
    v = light(nx, ny, nz, amb=amb)
    if ridge:
        # the lighter streak along the TROO tentacles, on whichever side faces the light
        pl = np.clip((-tb.dy * LIGHT[0] + tb.dx * LIGHT[1]) * 3, -1, 1)
        v = v + ridge * np.exp(-((tb.s - 0.42 * pl) / 0.16) ** 2)
    if warm is not None:
        wx, wy, wpow = warm
        lx, ly = wx - PX, wy - PY
        dist = np.hypot(lx, ly) + 1e-6
        lz = 0.35 * dist
        ln = np.sqrt(lx * lx + ly * ly + lz * lz)
        wd = np.clip((nx * lx + ny * ly + nz * lz) / ln, 0, 1) * np.clip(1 - dist / 70.0, 0, 1)
        v = v + wpow * wd
    return np.clip(v, 0, 1.3) ** 1.35        # Doom sprites keep their forms in strong light/dark contrast


# ---------------------------------------------------------------- serpentipede arm
def finger(fr, base, ang, length, curl, r, warm=None, seed=0, talon=12):
    """a finger-tentacle curling sideways (curl px), ending in a hooked gold talon"""
    ca, sa = math.cos(ang), math.sin(ang)
    px_, py_ = -sa, ca
    bx, by = base
    ctrl = [(bx, by), (bx + ca * length * 0.5 + px_ * curl * 0.2, by + sa * length * 0.5 + py_ * curl * 0.2),
            (bx + ca * length * 0.9 + px_ * curl * 0.7, by + sa * length * 0.9 + py_ * curl * 0.7),
            (bx + ca * length + px_ * curl * 1.4, by + sa * length + py_ * curl * 1.4)]
    tb = Tube(ctrl, r, r * 0.55, n=48, rfun=lambda t: (r + (r * 0.55 - r) * t) * (1 + 0.12 * np.sin(t * math.pi * 3) ** 2))
    v = shade_tube(tb, ridge=0.26, warm=warm)
    paint(fr, tb.mask, v, R_TENT, seed=seed, mottle=0.05)
    (ex, ey), (dx, dy) = tb.end()
    pxx, pyy = -dy, dx
    k = 1 if curl >= 0 else -1
    tctrl = [(ex - dx * 2, ey - dy * 2), (ex + dx * talon * 0.55, ey + dy * talon * 0.55),
             (ex + dx * talon * 0.85 + pxx * k * talon * 0.5, ey + dy * talon * 0.85 + pyy * k * talon * 0.5)]
    tt = Tube(tctrl, r * 0.72, 0.3, taper=0.75, n=36)
    v = shade_tube(tt, amb=0.22, warm=warm) * 0.85 + tt.t * 0.32
    paint(fr, tt.mask, v, R_HORN, seed=seed + 1, gr=0.03, mottle=0.0)


def imp_arm(fr, ctrl, r0, r1, fingers, warm=None, seed=10, stripes=False, palm=1.45):
    """a serpentipede tentacle-arm from off screen (muscle swell on the forearm, gold slashes like its body),
    a knotted palm and finger-tentacles. fingers: (angle from the arm, length, curl, radius, talon)"""
    rf = lambda t: (r0 + (r1 - r0) * t ** 0.9) * (1 + 0.16 * np.sin(np.clip(t, 0, 1) * math.pi * 1.6) ** 2)
    tb = Tube(ctrl, r0, r1, n=120, rfun=rf)
    v = shade_tube(tb, ridge=0.22, warm=warm)
    l = tb.t * tb.length
    # sinews running along the arm and darker blotches, so it reads as hide, not a hose
    v = v + 0.07 * np.cos(tb.s * 7.0 + np.sin(l * 0.07) * 1.5) * (np.abs(tb.s) < 0.8)
    v = v - 0.16 * np.clip(vnoise(9, seed + 9) - 0.55, 0, 1) * 3
    paint(fr, tb.mask, v, R_TENT, seed=seed)
    if stripes:
        # the body's gold chevrons: pairs of diagonal bars either side of the dark spine, near the root
        ph = (l / 12.0 + np.abs(tb.s) * 0.85) % 1.0
        st = tb.mask & (ph < 0.3) & (np.abs(tb.s) > 0.14) & (np.abs(tb.s) < 0.9) & (tb.t > 0.04) & (tb.t < 0.5)
        st &= ~border(tb.mask)
        paint(fr, st, v * 1.05 + 0.08, R_GOLD, seed=seed + 2, rim=1, mottle=0.04)
    (hx, hy), (dx, dy) = tb.end()
    rp = r1 * palm
    knot = Tube([(hx - dx * rp * 0.8, hy - dy * rp * 0.8), (hx + dx * rp * 0.25, hy + dy * rp * 0.25)], rp * 0.95, rp, n=16)
    v = shade_tube(knot, ridge=0.1, warm=warm) - 0.04
    paint(fr, knot.mask, v, R_TENT, seed=seed + 3, rim='bg')
    base_ang = math.atan2(dy, dx)
    for i, (da, ln, cu, rr, tal) in enumerate(fingers):
        a = base_ang + da
        bx = hx + math.cos(a) * rp * 0.5; by = hy + math.sin(a) * rp * 0.5
        finger(fr, (bx, by), a, ln, cu, rr, warm=warm, seed=seed + 10 + i * 3, talon=tal)


# ---------------------------------------------------------------- sprites from the WAD (fireball)
_IDX = {tuple(c): i for i, c in reversed(list(enumerate(PAL.tolist())))}


def sprite_idx(name):
    a, _ = assets.sprite(name)
    out = np.full(a.shape[:2], -1, np.int16)
    m = a[..., 3] > 0
    out[m] = [_IDX[tuple(c)] for c in a[m][:, :3].tolist()]
    return out


def scale2x(a):
    """Scale2x/EPX on palette indices: doubles a pixel sprite and keeps its hard edges and its colours"""
    h, w = a.shape
    p = np.pad(a, 1, constant_values=-1)
    B, D, F, H_ = p[0:h, 1:w + 1], p[1:h + 1, 0:w], p[1:h + 1, 2:w + 2], p[2:h + 2, 1:w + 1]
    E = a
    e0 = np.where((D == B) & (B != F) & (D != H_), D, E)
    e1 = np.where((B == F) & (B != D) & (F != H_), F, E)
    e2 = np.where((D == H_) & (D != B) & (H_ != F), D, E)
    e3 = np.where((H_ == F) & (D != H_) & (B != F), F, E)
    out = np.empty((h * 2, w * 2), a.dtype)
    out[0::2, 0::2], out[0::2, 1::2], out[1::2, 0::2], out[1::2, 1::2] = e0, e1, e2, e3
    return out


def blit(fr, spr, cx, cy):
    h, w = spr.shape
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    for y in range(h):
        yy = y0 + y
        if not 0 <= yy < VH: continue
        for x in range(w):
            xx = x0 + x
            if 0 <= xx < VW and spr[y, x] >= 0:
                fr.idx[yy, xx] = spr[y, x]


# ---------------------------------------------------------------- fire, crackle
def bolt(fr, x, y, ang, length, rng, branches=2, depth=0):
    """a jagged crackle bolt like SKULC/SKULD: white-yellow core, yellow/orange fringe"""
    pts = [(x, y)]
    a = ang
    for _ in range(int(length / 3)):
        a = ang + rng.uniform(-0.75, 0.75)
        x += math.cos(a) * 3; y += math.sin(a) * 3
        pts.append((x, y))
    core = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for k in range(n + 1):
            core.append((int(round(x0 + (x1 - x0) * k / n)), int(round(y0 + (y1 - y0) * k / n))))
    fringe = [227, 228, 231, 161, 213]
    for (cx, cy) in core:
        for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if rng.random() < 0.45 and 0 <= cx + ox < VW and 0 <= cy + oy < VH and OVAL[cy + oy, cx + ox] < 0.97:
                fr.idx[cy + oy, cx + ox] = fringe[rng.integers(len(fringe))]
    for (cx, cy) in core:
        if 0 <= cx < VW and 0 <= cy < VH and OVAL[cy, cx] < 0.97:
            fr.idx[cy, cx] = 225 if depth == 0 else 227
    if depth < 2:
        for _ in range(branches):
            if len(pts) > 3:
                bx, by = pts[rng.integers(1, len(pts) - 1)]
                bolt(fr, bx, by, ang + rng.choice([-1, 1]) * rng.uniform(0.6, 1.2), length * 0.4, rng, 1, depth + 1)


# ---------------------------------------------------------------- serpentipede: claw
FINGERS_R = [  # (angle from the arm, length, curl, radius, talon) for the right hand
    (-1.05, 26, -6, 7.5, 15), (-0.42, 36, -9, 8.5, 17), (0.18, 35, -9, 8.5, 17), (0.8, 25, -6, 7.2, 14)]


def swoosh(fr, ctrl, r, seed):
    """a claw streak: a thin pale tapering arc, brightest at the head"""
    tb = Tube(ctrl, 0.4, r, taper=1.6, n=60)
    v = 0.25 + 0.75 * tb.t + 0.15 * (1 - np.abs(tb.s))
    paint(fr, tb.mask, v, [225, 4, 128, 130, 133, 136], seed=seed, gr=0.08, mottle=0, rim=0)


def zimp(f):
    fr = Frame()
    if f == 'A':     # idle: the claw half-raised on the right, over the status bar like the pistol hand
        imp_arm(fr, [(282, 246), (276, 210), (260, 186), (244, 172)], 30, 15, FINGERS_R)
    elif f == 'B':   # wind-up: drawn back and up to the right, talons cocked high
        imp_arm(fr, [(270, 250), (288, 206), (290, 166), (278, 138)], 28, 15,
                [(a - 0.2, l, c - 3, r, t) for a, l, c, r, t in FINGERS_R])
    elif f == 'C':   # swipe: across the screen to the upper left, three claw streaks behind the talons
        for k in range(3):
            swoosh(fr, [(296, 66 + k * 13), (250, 50 + k * 13), (186, 56 + k * 14)], 2.2, 70 + k)
        imp_arm(fr, [(282, 252), (262, 180), (216, 130), (170, 108)], 32, 15,
                [(a, l + 4, c, r, t + 2) for a, l, c, r, t in FINGERS_R])
    elif f == 'D':   # follow-through: low on the left, recovering
        imp_arm(fr, [(250, 252), (196, 212), (140, 186), (100, 170)], 30, 15,
                [(a + 0.25, l, c + 2, r, t) for a, l, c, r, t in FINGERS_R])
    return fr


# ---------------------------------------------------------------- serpentipede: fireball
def zimf(f):
    fr = Frame()
    ball = {'A': (160, 146), 'B': (160, 136), 'C': (160, 78)}[f]
    warm = (ball[0], ball[1], {'A': 0.35, 'B': 0.6, 'C': 0.2}[f])
    if f == 'A':     # cupped low round a small flame
        wl, wr = (124, 168), (196, 168)
        cup = [(-0.8, 20, 6, 6.2, 11), (-0.2, 24, 7, 6.6, 12), (0.4, 21, 7, 6.2, 11)]
    elif f == 'B':   # raised, spread round the full fireball
        wl, wr = (116, 160), (204, 160)
        cup = [(-0.9, 21, 6, 6.2, 12), (-0.3, 25, 7, 6.6, 13), (0.3, 22, 7, 6.2, 12)]
    else:            # release: flung apart, talons splayed
        wl, wr = (98, 178), (222, 178)
        cup = [(-1.05, 22, -4, 6.2, 12), (-0.45, 26, -5, 6.6, 13), (0.15, 23, -5, 6.2, 12)]
    if f == 'B':     # the ball sits behind the fingers
        blit(fr, scale2x(sprite_idx('BAL1B0')), *ball)
    imp_arm(fr, [(wl[0] - 56, 250), (wl[0] - 40, 214), (wl[0] - 16, wl[1] + 12), wl], 28, 14,
            [(-a, l, -c, r, t) for a, l, c, r, t in cup], warm=warm, seed=40)
    imp_arm(fr, [(wr[0] + 56, 250), (wr[0] + 40, 214), (wr[0] + 16, wr[1] + 12), wr], 28, 14, cup, warm=warm, seed=60)
    if f == 'A':
        blit(fr, sprite_idx('BAL1A0'), *ball)
    elif f == 'B':
        rng = np.random.default_rng(5)
        for _ in range(16):      # sparks thrown off the ball
            a = rng.uniform(0, 2 * math.pi); r = rng.uniform(17, 27)
            x, y = int(ball[0] + math.cos(a) * r), int(ball[1] + math.sin(a) * r * 0.9)
            if 0 <= x < VW and 0 <= y < VH and fr.idx[y, x] < 0:
                fr.idx[y, x] = [225, 227, 161, 213][rng.integers(4)]
    else:
        blit(fr, sprite_idx('BAL1B0'), *ball)
        rng = np.random.default_rng(6)
        for i in range(12):      # a short trail back down to the hands
            y = ball[1] + 10 + i * 4.5; x = ball[0] + rng.uniform(-2.5, 2.5)
            if rng.random() < 0.9 - i * 0.05:
                fr.idx[int(y), int(x)] = [225, 227, 161, 213, 215][min(4, i // 2)]
    return fr


# ---------------------------------------------------------------- flesh worm: the star mouth from inside
def petal(fr, base, tip, width, bend, seed, teeth=3):
    """one fleshy lobe of the star mouth: round-sided, a dark groove down the middle, ring folds like the worm's
    body across it, darker towards the throat; a few big bone teeth on each edge near the point"""
    bx, by = base; tx, ty = tip
    dx, dy = tx - bx, ty - by
    L = math.hypot(dx, dy); ux, uy = dx / L, dy / L
    mid = (bx + dx * 0.55 - uy * bend, by + dy * 0.55 + ux * bend)
    curve = [base, mid, tip]
    rf = lambda t: 1.0 + (width - 1.0) * np.clip(1 - t, 0, 1) ** 0.8 * np.clip(0.8 + 1.0 * t, 0, 1)
    tb = Tube(curve, width, 1.0, n=90, rfun=rf)
    nx, ny, nz = tb.normal()
    # wet flesh: dark red where it runs back into the throat, pink and glossy towards the lip/point
    v = light(nx, ny, nz, amb=0.12, spec=0.45, power=14) * 0.8 + tb.t * 0.3 - 0.12
    v = np.where(np.abs(tb.s) < 0.07 + 0.06 * (1 - tb.t), v - 0.3, v)               # central groove
    v = v - 0.12 * np.clip(vnoise(6, seed + 3) - 0.5, 0, 1) * 2                       # blotches
    paint(fr, tb.mask, v, R_FLESH, seed=seed, mottle=0.06)
    for side in (-1, 1):
        for k in range(teeth):
            t = 0.52 + k * 0.12
            P = bez(curve, [t])[0]; P2 = bez(curve, [t + 0.01])[0]
            d = P2 - P; d = d / np.linalg.norm(d)
            pr = np.array([-d[1], d[0]]) * side
            r = float(rf(t))
            root = P + pr * (r - 2.0)
            ln = 7 + 5 * (1 - t)
            tipp = root + (pr * 0.42 + d * 0.91) * ln
            tt = Tube([tuple(root), tuple((root + tipp) / 2 + pr * 1.5), tuple(tipp)], 3.0 + 1.4 * (1 - t), 0.3, n=16)
            vv = shade_tube(tt, amb=0.3) + 0.2 * tt.t
            paint(fr, tt.mask, vv, R_BONE, seed=seed + 50 + k, mottle=0.0, gr=0.03)


def gum(fr, cy, rx, ry, seed):
    """a jaw's gum: the wet, ridged inside of the worm's mouth, an elliptical mound on the top or bottom screen edge
    (centre cy off screen), darker into the throat; its ends round off well before the sides of the view"""
    nx = (PX - 160) / rx; ny = (PY - cy) / ry
    e = np.hypot(nx, ny)
    m = e < 1
    nz = np.sqrt(np.clip(1 - e * e, 0, 1))
    v = light(nx, ny, nz, amb=0.15) * 0.7 + 0.25 - np.clip(1 - e, 0, 1) * 0.6
    ridge = np.sin(np.arctan2(PY - cy, PX - 160) * 30 + vnoise(9, seed) * 5)
    v = v + 0.14 * ridge
    paint(fr, m, v, R_THROAT, seed=seed, mottle=0.08, cell=5)


# the two jaws of the star mouth: three petals each, rooted in the gum. (root x, tip dx, petal width scale)
JAW = [(64, 44, 1.0), (160, 0, 1.15), (256, -44, 1.0)]


def jaw(fr, upper, gum_edge, tip_y, width, seed):
    """gum_edge: how far the gum reaches into the screen from its edge; tip_y: where the petal points end"""
    if upper:
        gum(fr, gum_edge - 120, 168, 120, seed)
    else:
        gum(fr, VH - gum_edge + 120, 168, 120, seed)
    order = (0, 2, 1)                                   # the middle petal overlaps its neighbours
    for i in order:
        rx, tdx, ws = JAW[i]
        if upper:
            base, tip = (rx, gum_edge - 46), (rx + tdx, tip_y + (6 if i != 1 else 0))
        else:
            base, tip = (rx, VH - gum_edge + 46), (rx + tdx, tip_y - (6 if i != 1 else 0))
        petal(fr, base, tip, width * ws, (14 if rx < 160 else -14 if rx > 160 else 0) * (1 if upper else -1), seed + i * 3)


def zdmn(f):
    fr = Frame()
    if f == 'A':     # idle: the lower jaw, three petals standing up from the bottom edge
        jaw(fr, False, 34, 132, 30, 1)
    elif f == 'B':   # open: jaws gaping, the upper one showing at the top of the view
        jaw(fr, True, 30, 50, 32, 4)
        jaw(fr, False, 26, 148, 30, 7)
    elif f == 'C':   # bite: the jaws snap shut, petals interlocking across the middle
        jaw(fr, True, 70, 118, 46, 10)
        jaw(fr, False, 70, 82, 46, 13)
        rng = np.random.default_rng(9)
        for _ in range(30):                             # spit and blood in the closing gap
            x, y = int(rng.uniform(40, 280)), int(rng.uniform(88, 112))
            fr.idx[y, x] = [176, 180, 184, 188][rng.integers(4)]
    else:            # lunge: half closed, thrust forward
        jaw(fr, True, 52, 82, 40, 16)
        jaw(fr, False, 50, 118, 40, 19)
    return fr


# ---------------------------------------------------------------- deadflare
def orb_rim(fr, cy, rx, ry, glow, seed):
    """the front-bottom of the deadflare's wrinkled orb (the folds of SKULA5), a low dome at the screen bottom"""
    nx = (PX - 160) / rx; ny = (PY - cy) / ry
    rr = nx * nx + ny * ny
    m = rr < 1
    nz = np.sqrt(np.clip(1 - rr, 0, 1))
    v = light(nx, ny, nz + 0.1, amb=0.14) * 0.64
    # folds like SKULA5: long snaking ridges round the dome, each lit on top with a dark groove between
    N = vnoise(14, seed) * 0.7 + vnoise(6, seed + 1) * 0.3
    a = 3.0 * nx + 1.3 * np.sin(4.0 * ny + 2.5 * nx + seed) + 1.6 * N
    w = np.sin(2 * math.pi * a)
    v = v + 0.16 * w + 0.1 * np.cos(2 * math.pi * a)       # rounded ridge, light from the upper left
    groove = m & (w < -0.72)
    v = np.where(groove, v - 0.3, v)
    paint(fr, m, v, R_SKIN, seed=seed, mottle=0.04)
    if glow:      # the fire inside showing through the folds
        g = groove & ~border(m) & (rr < 0.97)
        gv = np.clip(glow * (0.55 + 0.45 * (1 - rr)) + (grain(seed + 3) - 0.5) * 0.3, 0, 1)
        paint(fr, g, gv, R_GLOW, seed=seed + 4, rim=0, mottle=0)


def leg(fr, ctrl, r0, seed):
    """a SKUL leg: pink-red, ringed, hooking to a point"""
    tb = Tube(ctrl, r0, 1.2, taper=1.1, n=80)
    v = shade_tube(tb, ridge=0.25, amb=0.2)
    v = np.where(((tb.t * tb.length) % 6.0) < 1.0, v - 0.2, v)
    paint(fr, tb.mask, v, R_LEG, seed=seed, mottle=0.05)


def fire(fr, specs, seed, gain=1.0, warp=9.0):
    """mottled flame tongues like the BAL1/SKUL fire art: the screen is warped by noise first so the tongues lick
    and break up, overlapping tongues merge into masses, yellow-white cores, orange to dark red rims.
    specs: (base x, base y, angle, length, half width, sway, phase)"""
    wx = PX + (vnoise(11, seed + 5) - 0.5) * 2 * warp
    wy = PY + (vnoise(11, seed + 6) - 0.5) * 2 * warp
    V = np.zeros((VH, VW))
    for (bx, by, ang, ln, hw, sway, ph) in specs:
        ca, sa = math.cos(ang), math.sin(ang)
        lx, ly = wx - bx, wy - by
        u = (lx * ca + ly * sa) / ln
        w = -lx * sa + ly * ca
        c = sway * np.sin(u * 3.2 + ph) * u
        half = hw * np.clip(1 - u, 0, 1) ** 0.45
        inside = (u >= -0.3) & (u <= 1)
        val = np.clip(1 - (np.abs(w - c) / np.maximum(half, 1e-3)) ** 2, 0, 1) * (1.0 - 0.7 * np.clip(u, 0, 1))
        V = V + np.where(inside, val * gain, 0)
    V = np.clip(V, 0, 1.2) * np.clip((1 - OVAL) * 9, 0, 1)
    V = V * (0.72 + 0.4 * vnoise(4, seed) + 0.18 * vnoise(2, seed + 1))
    m = V > 0.28
    v = np.clip((V - 0.28) / 0.95, 0, 1)
    paint(fr, m, v, R_FIRE, seed=seed + 2, gr=0.08, mottle=0.06, cell=3, rim=1)


def mirror(specs):
    return [(320 - bx, by, -math.pi - ang, ln, hw, sway, ph + 0.9) for bx, by, ang, ln, hw, sway, ph in specs]


def zskl(f):
    fr = Frame(oval=True)
    rng = np.random.default_rng({'A': 11, 'B': 12, 'C': 13}[f])
    if f == 'A':     # idle: legs hooked up either side, the orb's brow below, flames licking behind the legs
        side = [(56, 204, -1.75, 66, 14, 3, 0.0), (32, 204, -1.45, 54, 12, 3, 1.3), (84, 200, -1.6, 40, 10, 2, 2.0)]
        fire(fr, side + mirror(side), seed=21)
        leg(fr, [(74, 216), (66, 180), (86, 140), (112, 150)], 11, 31)
        leg(fr, [(246, 216), (254, 180), (234, 140), (208, 150)], 11, 32)
        orb_rim(fr, 246, 122, 102, 0.0, 41)
    elif f == 'B':   # flare: flames climb high either side, the folds glow, crackle all over
        side = []
        for i in range(6):
            side.append((14 + i * 9, 206 - i * 14, -1.3 - i * 0.04, 96 - i * 9, 17, 4, i * 1.7))
        for i in range(4):
            side.append((70 + i * 24, 210, -1.57 + 0.2 * math.sin(i * 1.9), 52 + 14 * math.sin(i * 2.3) ** 2, 15, 4, i))
        fire(fr, side + mirror(side), seed=22)
        leg(fr, [(70, 216), (54, 170), (72, 118), (102, 126)], 9.5, 33)
        leg(fr, [(250, 216), (266, 170), (248, 118), (218, 126)], 9.5, 34)
        orb_rim(fr, 250, 126, 104, 0.9, 42)
        for _ in range(7):
            sd = rng.random() < 0.5
            x = rng.uniform(26, 70) if sd else rng.uniform(250, 294)
            bolt(fr, x, rng.uniform(110, 170), -math.pi / 2 + rng.uniform(-0.6, 0.6), rng.uniform(30, 55), rng)
    else:            # dash: flame streaming in from all round the view, legs swept back, orb thrust down
        specs = []
        for i in range(22):
            a = i / 22 * 2 * math.pi
            ex, ey = 160 + math.cos(a) * 160, 100 + math.sin(a) * 178
            inward = math.atan2(100 - ey, 160 - ex)
            specs.append((ex, ey, inward + 0.15 * math.sin(i * 2.7), 96 + 20 * math.sin(i * 1.7), 30, 6, i * 0.9))
        fire(fr, specs, seed=23)
        leg(fr, [(52, 222), (44, 192), (62, 170), (82, 176)], 9, 35)
        leg(fr, [(268, 222), (276, 192), (258, 170), (238, 176)], 9, 36)
        orb_rim(fr, 264, 130, 96, 0.6, 43)
        for _ in range(10):      # speed streaks, radiating outwards
            a = rng.uniform(0, 2 * math.pi); r0 = rng.uniform(50, 70)
            for j in range(int(rng.uniform(6, 14))):
                x = int(160 + math.cos(a) * (r0 + j * 2) * 1.3); y = int(100 + math.sin(a) * (r0 + j * 2) * 0.8)
                if 0 <= x < VW and 0 <= y < VH and fr.idx[y, x] < 0:
                    fr.idx[y, x] = [225, 227, 161][min(2, j // 4)]
    return fr


BUILD = {'ZIMP': zimp, 'ZIMF': zimf, 'ZDMN': zdmn, 'ZSKL': zskl}


# ---------------------------------------------------------------- output
def to_rgba(fr):
    out = np.zeros((VH, VW, 4), np.uint8)
    m = fr.idx >= 0
    out[m, :3] = PAL[fr.idx[m]]
    out[m, 3] = 255
    return out


def crop(img):
    ys, xs = np.nonzero(img[..., 3])
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    return img[y0:y1, x0:x1], (int(1 - x0), int(16 - y0)), (x0, y0)


def main():
    out = sys.argv[1]
    arg = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
    sheet, ingame = arg('--sheet'), arg('--ingame')
    os.makedirs(out, exist_ok=True)
    offs = {}; full = {}
    for sp, frames in FRAMES.items():
        for f in frames:
            img = to_rgba(BUILD[sp](f))
            full[sp + f] = img
            c, o, (x0, y0) = crop(img)
            name = sp + f + '0'
            Image.fromarray(c).save(os.path.join(out, name.lower() + '.png'))
            offs[name] = list(o)
            cover = (img[..., 3] > 0).mean() * 100
            print('%s %3dx%-3d at %3d,%3d offsets %s cover %4.1f%%' % (name, c.shape[1], c.shape[0], x0, y0, o, cover))
            if f == 'A' and y0 < IDLE_TOP:
                print('  WARNING: idle frame reaches y %d (limit %d)' % (y0, IDLE_TOP))
            side = int(img[:180, :2, 3].astype(bool).sum() + img[:180, -2:, 3].astype(bool).sum())
            if side:
                print('  WARNING: %d pixels on the left/right edge would show a cut on a 16:9 screen' % side)
    json.dump(offs, open(os.path.join(out, 'offsets.json'), 'w'), indent=1)
    if sheet:
        contact(full, sheet)
    if ingame:
        mock_ingame(full, ingame)


# ---------------------------------------------------------------- previews
def doom_bg():
    """a Freedoom view: STARTAN3 wall, FLOOR4_8 floor in perspective, darkening with distance"""
    wall = assets.texture('STARTAN3'); flr = assets.flat('FLOOR4_8')
    bg = np.zeros((VH, VW, 3), np.float32)
    hor = 104
    for y in range(hor):
        bg[y] = wall[(y + 20) % wall.shape[0], np.arange(VW) % wall.shape[1], :3] * 0.8
    for y in range(hor, VH):
        dist = 2200.0 / (y - hor + 4)
        u = ((np.arange(VW) - 160) * dist / 160).astype(int) % 64
        v = int(dist) % 64
        bg[y] = flr[v, u, :3] * np.clip(1.15 - dist / 700, 0.35, 1)
    return bg.astype(np.uint8)


def ref_frame(name):
    """a Freedoom weapon sprite placed on the 320x200 screen the way hud.py places it"""
    a, (lo, to) = assets.sprite(name)
    img = np.zeros((VH, VW, 4), np.uint8)
    x0, y0 = 1 - lo, 16 - to
    h, w = a.shape[:2]
    ys, xs = slice(max(0, y0), min(VH, y0 + h)), slice(max(0, x0), min(VW, x0 + w))
    img[ys, xs] = a[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0]
    return img


def composite(bg, img):
    c = bg.copy(); m = img[..., 3] > 0; c[m] = img[m, :3]
    return c


def contact(full, path, scale=4):
    bg = doom_bg()
    cells = [(n, ref_frame(n)) for n in ('PISGA0', 'SHTGA0', 'PUNGB0')] + list(full.items())
    cols = 4
    pad = 6 * scale
    cw, ch = VW * scale, VH * scale
    rows = 1 + (len(full) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * (cw + pad), rows * (ch + pad)), (20, 20, 24))
    dr = ImageDraw.Draw(sheet)
    pos = [(0, 0), (1, 0), (2, 0)] + [(i % cols, 1 + i // cols) for i in range(len(full))]
    for (name, img), (cx, cy) in zip(cells, pos):
        im = Image.fromarray(composite(bg, img)).resize((cw, ch), Image.NEAREST)
        x, y = cx * (cw + pad), cy * (ch + pad)
        sheet.paste(im, (x, y))
        dr.rectangle((x, y, x + 200, y + 26), fill=(0, 0, 0))
        dr.text((x + 6, y + 6), name + ('  (Freedoom reference)' if name.endswith('0') else ''), fill=(255, 255, 0))
        dr.line((x, y + IDLE_TOP * scale, x + cw, y + IDLE_TOP * scale), fill=(0, 140, 255))
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    sheet.save(path)
    zoom = os.path.join(os.path.dirname(path), 'zviews_zoom.png')
    sheet.resize((sheet.size[0] // 2, sheet.size[1] // 2), Image.NEAREST).save(zoom)
    print('sheet', path, sheet.size, '| overview', zoom)


def mock_ingame(full, path):
    """1920x1080: the view at Doom's 4:3 pixel aspect (4.5 x 5.4 screen px per Doom px) inside the 16:9 screen,
    status bar as hud.py lays it out (85%)"""
    W, H = 1920, 1080
    SX, SY = 4.5, 5.4
    # world: the Doom background stretched over the whole screen (CS2 draws the world full width)
    bgw = np.zeros((VH, 427, 3), np.uint8)
    b = doom_bg()
    for x in range(427):
        bgw[:, x] = b[:, (x - 53) % VW]
    world = Image.fromarray(bgw).resize((W, H), Image.NEAREST)
    shots = ['ZIMPA', 'ZIMFB', 'ZDMNA', 'ZSKLA']
    tiles = []
    for n in shots:
        scr = world.copy()
        spr = Image.fromarray(full[n]).resize((int(VW * SX), int(VH * SY)), Image.NEAREST)
        scr.paste(spr, ((W - int(VW * SX)) // 2, H - int(VH * SY)), spr)
        sb = assets.graphic('STBAR')[0]
        sbi = np.array(sb)
        face = assets.graphic('STFST01')[0]
        sbi[1:1 + face.shape[0], 143:143 + face.shape[1]][face[..., 3] > 0] = face[face[..., 3] > 0]
        for k, d in enumerate('100'):
            g = assets.graphic('STTNUM' + d)[0]
            x = 90 - (3 - k) * 13
            sbi[3:3 + g.shape[0], x:x + g.shape[1]][g[..., 3] > 0] = g[g[..., 3] > 0]
        sw, sh = int(320 * SX * 0.85), int(32 * SY * 0.85)
        sbim = Image.fromarray(sbi).resize((sw, sh), Image.NEAREST)
        scr.paste(sbim, ((W - sw) // 2, H - sh), sbim)
        d = ImageDraw.Draw(scr)
        d.line((W // 2 - 12, H // 2, W // 2 + 12, H // 2), fill=(0, 255, 0), width=3)
        d.line((W // 2, H // 2 - 12, W // 2, H // 2 + 12), fill=(0, 255, 0), width=3)
        d.rectangle((0, 0, 260, 40), fill=(0, 0, 0)); d.text((10, 12), n + '0 in game (1920x1080)', fill=(255, 255, 0))
        tiles.append(scr)
    out = Image.new('RGB', (W * 2, H * 2))
    for i, t in enumerate(tiles):
        out.paste(t, ((i % 2) * W, (i // 2) * H))
    out.save(path)
    print('ingame', path, out.size)


if __name__ == '__main__':
    main()
