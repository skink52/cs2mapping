"""Far scenery painted into the arena sky panoramas (the "3D skybox" of IRONFRAME, list item M3).

The arenas are copies thousands of units apart that share one sky, and every copy sits in its own moondome shell
(csgo_moondome, g_flCubeParallax 0: the panorama is at infinity, the same from every copy). A real 3D skybox is drawn from
player position / 16, so it would sit wrong from every copy but one. So the far world is drawn INTO the panorama instead:
  sprawl: three depth layers of megacity towers with lit windows, crowns, LED panels and aviation lights, supertalls that
          go up into the overcast, elevated-road light strings, a neon haze band that swallows the bases;
  dunes:  three layers of mesas and buttes in dusk aerial perspective, two refineries with stacks, tanks, flares and smoke,
          lone derricks, a dust band.
No parallax and no animation: blinking lights or flames must be props / particles in the arena.

    import sky_vista; a = sky_vista.apply('sprawl', base)      base: float32 (h, w, 3) 0..255 panorama (row 0 = up, col 0 = yaw 0)
    python -I tools/sky_vista.py <arena> <out dir>             preview pictures (strip + perspective views), nothing deployed

Work happens at 8192 x 4096 in a strip around the horizon; the caller decides the saved size.
"""
import os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
CREATE = os.environ.get('CREATE', os.path.join(HERE, '..', '..', '..', 'create'))
sys.path.insert(0, CREATE); sys.path.insert(0, HERE)
import numpy as np
from PIL import Image, ImageFilter
from noise import fbm, smoothstep

W8, H8 = 8192, 4096
PPD = W8 / 360.0                      # pixels per degree
E_TOP, E_BOT = 40.0, -8.0             # the strip that is worked on


def row_of(e): return (90.0 - e) / 180.0 * H8
R0, R1 = int(row_of(E_TOP)), int(row_of(E_BOT))
SH = R1 - R0


def strip_el():
    """elevation (deg) of every strip row, shape (SH, 1)"""
    return (90.0 - (np.arange(R0, R1) + 0.5) / H8 * 180.0)[:, None].astype(np.float32)


def yaw_noise(freq, seed, z=0.0, octaves=3, n=W8):
    """seamless 0..1 noise along the yaw"""
    a = np.arange(n) / n * 2 * np.pi
    return (fbm(np.cos(a) * freq, np.sin(a) * freq, 0 * a + z, octaves, seed=seed) * 0.5 + 0.5).astype(np.float32)


def blur(a, r):
    """gaussian blur of a float (h, w, 3) 0..255 layer, wrapped along the yaw"""
    pad = int(r * 3) + 1
    b = np.concatenate([a[:, -pad:], a, a[:, :pad]], 1)
    im = Image.fromarray(np.clip(b, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im, np.float32)[:, pad:-pad]


class Strip:
    """body (opaque far scenery, alpha-composited) and emissive (added, blurred for glow) layers on the horizon strip"""
    def __init__(self):
        self.col = np.zeros((SH, W8, 3), np.float32)
        self.a = np.zeros((SH, W8), np.float32)
        self.em = np.zeros((SH, W8, 3), np.float32)

    def rc(self, e):                  # strip row of an elevation
        return int(round(row_of(e))) - R0

    def cols(self, c0, c1):           # wrapped column indices
        return np.arange(c0, c1) % W8

    def box(self, c0, c1, e0, e1, color, alpha=1.0):
        r0, r1 = max(self.rc(e1), 0), min(self.rc(e0), SH)
        if r1 <= r0 or c1 <= c0: return None
        cc = self.cols(c0, c1)
        blk = np.empty((r1 - r0, c1 - c0, 3), np.float32); blk[:] = color
        return r0, r1, cc, blk

    def put(self, r0, r1, cc, blk, alpha=1.0):
        ix = np.ix_(np.arange(r0, r1), cc)
        a = np.asarray(alpha, np.float32)
        if a.ndim == 0: a = np.full(blk.shape[:2], float(a), np.float32)
        self.col[ix] = self.col[ix] * (1 - a[..., None]) + blk * a[..., None]
        self.a[ix] = self.a[ix] * (1 - a) + a
        self.em[ix] *= (1 - a[..., None])           # nearer bodies hide farther lights

    def light(self, r0, r1, cc, blk):
        ix = np.ix_(np.arange(max(r0, 0), min(r1, SH)), cc)
        if blk.shape[0] != ix[0].shape[0]: blk = blk[max(0, -r0):max(0, -r0) + ix[0].shape[0]]
        self.em[ix] = np.maximum(self.em[ix], blk)

    def dot(self, c, e, color, size=2):
        r = self.rc(e)
        if r < 0 or r + size > SH: return
        cc = self.cols(int(c), int(c) + size)
        self.em[np.ix_(np.arange(r, r + size), cc)] = np.maximum(self.em[np.ix_(np.arange(r, r + size), cc)], np.asarray(color, np.float32))

    def composite(self, base, glow=((5, 0.55), (18, 0.35)), body_fade=None, em_fade=None):
        """base: float (H8, W8, 3). body_fade / em_fade: (SH, 1) multipliers by elevation (clouds swallowing tall things)"""
        s = base[R0:R1]
        a = self.a if body_fade is None else self.a * body_fade
        s[:] = s * (1 - a[..., None]) + self.col * a[..., None]
        em = self.em if em_fade is None else self.em * em_fade[..., None]
        add = em.copy()
        for r, k in glow: add += blur(em, r) * k
        s[:] = s + add
        return base


# ---------------------------------------------------------------------------------------------------------------- sprawl
WARM, COOL, CYAN, MAG, AMBER = (255, 214, 150), (205, 226, 255), (70, 230, 255), (255, 70, 200), (255, 170, 70)
HAZE_S = (74, 46, 84)                 # the neon haze the far city sinks into
HZCOL = None                          # per column: the sky's colour just over the horizon (set by sprawl())


def tower(S, rng, c, wdeg, hdeg, haze, detail):
    """one tower as 1-3 stacked boxes; detail 0 far .. 2 near"""
    w = max(3, int(round(wdeg * PPD)))
    hz = HZCOL[int(c) % W8] if HZCOL is not None else np.array(HAZE_S, np.float32)   # the sky behind it: a far tower is never lighter than its sky
    body = np.array((13, 13, 22), np.float32) * (1 - haze) + hz * haze * 0.8
    lit = rng.uniform(0.10, 0.34)
    pal = [WARM, WARM, WARM, COOL, COOL, COOL, (255, 236, 200), CYAN if rng.rand() < 0.5 else MAG][rng.randint(8)]
    k_em = 1.0 - 0.62 * haze
    tiers = [(0.0, 1.0, 1.0)]
    t = rng.rand()
    if detail and t < 0.4: tiers = [(0.0, rng.uniform(0.62, 0.8), 1.0), (None, 1.0, rng.uniform(0.55, 0.75))]
    elif detail and t < 0.62: tiers = [(0.0, 0.55, 1.0), (None, 0.82, 0.72), (None, 1.0, 0.44)]
    elif detail and t < 0.74: tiers = [(0.0, 0.3, 1.0), (None, 0.9, 0.8), (None, 1.0, 0.25)]
    elif t < 0.3: tiers = [(0.0, 0.8, 1.0), (None, 1.0, 0.5)]
    cell = (4, 4) if detail == 2 else (3, 3) if detail == 1 else (2, 2)
    face = rng.uniform(0.25, 0.75); shade = rng.uniform(0.78, 0.9); flip = rng.rand() < 0.5
    prev = 0.0
    for lo, hi, wf in tiers:
        lo = prev if lo is None else lo; prev = hi
        tw = max(2, int(w * wf)); c0 = int(c - tw / 2)
        b = S.box(c0, c0 + tw, hdeg * lo - (2.5 if lo == 0 else 0), hdeg * hi, body)
        if b is None: continue
        r0, r1, cc, blk = b
        hh, ww = blk.shape[:2]
        u = np.arange(ww) / max(ww - 1, 1)
        side = (u > face) if flip else (u < face)                      # two faces: one a step darker
        blk *= np.where(side, shade, 1.0)[None, :, None]
        v = np.arange(hh)[:, None, None] / max(hh - 1, 1)
        blk[:] = blk * (1 - 0.35 * v ** 3) + hz * (0.35 * v ** 3) * 1.1   # street glow climbs the lower floors
        S.put(r0, r1, cc, blk)
        # windows
        cw, ch = cell
        ny, nx = hh // ch + 1, ww // cw + 1
        runs = np.repeat(rng.rand(ny // 5 + 1, 1), 5, 0)[:ny] * 0.7 + rng.rand(ny, 1) * 0.3      # occupied floors come in runs
        on = rng.rand(ny, nx) < lit * (0.35 + 1.3 * runs)
        if rng.rand() < 0.3: on |= (rng.rand(ny, 1) < 0.12)           # whole lit floors
        if rng.rand() < 0.25: on &= (rng.rand(1, nx) < 0.8)           # dark bays
        bright = rng.uniform(0.45, 1.0, (ny, nx)) * on
        tint = np.where(rng.rand(ny, nx, 1) < 0.8, np.array(pal, np.float32), np.array(WARM if pal != WARM else COOL, np.float32))
        if detail == 0: bright = bright * 0.8
        wl = (bright[..., None] * tint).repeat(ch, 0).repeat(cw, 1)[:hh, :ww]
        mask = np.ones((ch, cw), np.float32)
        if cw > 2: mask[:, -1] = 0; mask[-1, :] = 0
        if ch > 3: mask[-2, :] = 0
        if cw == 2: mask[1, :] = 0; mask[:, 1] = 0
        wl *= np.tile(mask, (ny, nx))[:hh, :ww, None]
        wl[:, :1] = 0; wl[:, -1:] = 0; wl[:2] = 0
        S.light(r0, r1, cc, wl * k_em)
    top_c0 = int(c - max(2, int(w * tiers[-1][2])) / 2); top_w = max(2, int(w * tiers[-1][2]))
    if detail and rng.rand() < 0.5:                                    # crown line
        colr = np.array([CYAN, MAG, AMBER, COOL][rng.randint(4)], np.float32) * k_em
        r = S.rc(hdeg)
        if 0 <= r < SH - 2: S.light(r, r + (2 if detail == 2 else 1), S.cols(top_c0, top_c0 + top_w), np.broadcast_to(colr, ((2 if detail == 2 else 1), top_w, 3)).copy())
    if detail and rng.rand() < 0.3:                                    # neon edge strip
        colr = np.array([CYAN, MAG][rng.randint(2)], np.float32) * k_em * 0.9
        r0, r1 = S.rc(hdeg * rng.uniform(0.75, 1.0)), S.rc(hdeg * rng.uniform(0.15, 0.4))
        if r1 > r0 >= 0:
            ce = int(c - w / 2) + (1 if rng.rand() < 0.5 else w - 3)
            S.light(r0, r1, S.cols(ce, ce + (2 if detail == 2 else 1)), np.broadcast_to(colr, (r1 - r0, (2 if detail == 2 else 1), 3)).copy())
    if detail == 2 and rng.rand() < 0.4 and w > 30:                    # LED panel
        pw, ph = int(w * rng.uniform(0.5, 0.8)), int(rng.uniform(1.0, 2.6) * PPD)
        e_top = hdeg * rng.uniform(0.45, 0.85); r0 = S.rc(e_top); c0 = int(c - pw / 2)
        if 0 <= r0 and r0 + ph < SH:
            c1 = np.array([MAG, CYAN, AMBER, (120, 255, 150), (255, 90, 90)][rng.randint(5)], np.float32)
            c2 = np.array([COOL, MAG, CYAN, (255, 240, 120)][rng.randint(4)], np.float32)
            gy = np.linspace(0, 1, ph)[:, None, None]; gx = np.linspace(0, 1, pw)[None, :, None]
            pan = c1 * (1 - gy) + c2 * gy
            bars = (np.sin(gx * rng.uniform(8, 30) + rng.uniform(0, 6)) > rng.uniform(-0.2, 0.6)) * 0.35 + 0.65
            blobs = (rng.rand(max(ph // 6, 1), max(pw // 8, 1), 1) < 0.35).repeat(6, 0).repeat(8, 1)[:ph, :pw] * 0.5 + 0.6
            pan = pan * bars * np.pad(blobs, ((0, ph - blobs.shape[0]), (0, pw - blobs.shape[1]), (0, 0)), mode='edge') * 0.85
            S.light(r0, r0 + ph, S.cols(c0, c0 + pw), pan.astype(np.float32) * k_em)
    if detail and rng.rand() < 0.35:                                   # roof mast
        mh = rng.uniform(0.5, 1.6); mc = top_c0 + int(top_w * rng.uniform(0.25, 0.75))
        b = S.box(mc, mc + (2 if detail == 2 else 1), hdeg, hdeg + mh, body)
        if b: S.put(*b)
        S.dot(mc, hdeg + mh, (255, 40, 30), 2)
    if hdeg > 6.5:                                                     # aviation lights
        S.dot(top_c0, hdeg + 0.05, (255, 40, 30), 2 + (detail == 2)); S.dot(top_c0 + top_w - 2, hdeg + 0.05, (255, 40, 30), 2 + (detail == 2))
    return top_c0, top_w


def spire(S, rng, c, top_w, hdeg, haze):
    body = np.array((13, 13, 22), np.float32) * (1 - haze) + np.array(HAZE_S, np.float32) * haze
    sh = rng.uniform(3.0, 6.5); n = int(sh * PPD)
    for k in range(0, n, 6):
        f = 1 - k / n; ww = max(2, int(top_w * 0.32 * f))
        b = S.box(int(c - ww / 2), int(c - ww / 2) + ww, hdeg + k / PPD, hdeg + (k + 6) / PPD, body)
        if b: S.put(*b)
        if k % 36 == 0 and k: S.dot(int(c) - 1, hdeg + k / PPD, (255, 40, 30), 3)
    S.dot(int(c) - 1, hdeg + sh, (255, 60, 40), 3)


def sprawl(base):
    global HZCOL
    rng = np.random.RandomState(4107)
    S = Strip()
    ref = base[int(row_of(7.0)):int(row_of(2.0))].mean(0)[None]
    HZCOL = blur(ref.repeat(3, 0), 40)[1]
    dens = yaw_noise(2.2, 51, octaves=3); dens2 = yaw_noise(5.0, 52, z=1.0, octaves=2)
    d = np.clip(dens * 0.7 + dens2 * 0.3, 0, 1); d = (d - d.min()) / (d.max() - d.min())

    def pick(n, power):
        p = (0.15 + d ** power); p /= p.sum()
        return np.sort(rng.choice(W8, n, p=p))

    # far: a continuous jagged wall of small towers
    prof = yaw_noise(9.0, 53, z=0.7, octaves=4)
    for c in pick(900, 0.6):
        k = d[c]
        tower(S, rng, c, rng.uniform(0.3, 0.95), 1.0 + 2.6 * prof[c] + 3.4 * k * rng.rand() ** 1.5 + rng.uniform(0, 0.9), rng.uniform(0.62, 0.8), 0)
    # elevated-road light strings in front of the far wall
    for _ in range(5):
        c0, span, e0 = rng.randint(W8), int(rng.uniform(35, 95) * PPD), rng.uniform(0.5, 1.7)
        ph = rng.uniform(0, 6)
        for k in range(0, span, 7):
            e = e0 + 0.18 * math.sin(k / span * math.pi * 2 + ph)
            S.dot((c0 + k) % W8, e, np.array(AMBER) * 0.75, 2)
            if k % 84 == 0:
                b = S.box(c0 + k, c0 + k + 3, -2.0, e - 0.03, np.array(HAZE_S, np.float32) * 0.55)
                if b: S.put(*b)
        b = S.box(c0, c0 + span, e0 - 0.3, e0 - 0.22, np.array(HAZE_S, np.float32) * 0.5)
    # mid
    for c in pick(210, 1.6):
        k = d[c]
        tower(S, rng, c, rng.uniform(0.7, 1.7), rng.uniform(2.5, 5.5) + 7.0 * k * rng.rand() ** 1.3, rng.uniform(0.42, 0.56), 1)
    # near: big towers in clusters, with gaps where the far layers show
    near = pick(64, 3.0)
    for c in near:
        k = d[c]
        tower(S, rng, c, rng.uniform(1.6, 3.4), rng.uniform(5.0, 9.0) + 11.0 * k * rng.rand(), rng.uniform(0.2, 0.32), 2)
    # supertalls: into the overcast
    for c in rng.choice(near, 6, replace=False):
        c = int(c + rng.uniform(-3, 3) * PPD); h = rng.uniform(21.0, 29.0)
        c0, tw = tower(S, rng, c, rng.uniform(2.0, 3.0), h, rng.uniform(0.22, 0.3), 2)
        spire(S, rng, c0 + tw / 2, tw, h, 0.3)

    E = strip_el()
    body_fade = 1 - 0.9 * smoothstep(15.0, 27.0, E)                   # the overcast deck swallows the tops
    em_fade = 1 - 0.7 * smoothstep(17.0, 30.0, E)
    S.composite(base, glow=((4, 0.5), (14, 0.3)), body_fade=body_fade + 0 * S.a, em_fade=(em_fade + 0 * S.a))
    small = S.em[::8, ::8]
    halo = np.asarray(Image.fromarray(np.clip(blur(small, 16) * 3.0, 0, 255).astype(np.uint8)).resize((W8, SH), Image.BICUBIC), np.float32)
    base[R0:R1] += halo * (0.5 + 0.5 * smoothstep(2.0, 14.0, strip_el()))[..., None] * 0.9      # the city lights the mist and the cloud base
    # the haze band that hides every base, and the city's light on the underside of the mist
    s = base[R0:R1]
    yawhue = yaw_noise(1.3, 34, z=2.0, octaves=2)[None, :, None]
    neon = np.array((255, 80, 200), np.float32) * (1 - yawhue) + np.array((70, 200, 255), np.float32) * yawhue
    hz = np.array(HAZE_S, np.float32) * 0.75 + neon * 0.25
    band = np.exp(-np.abs(E - 0.2) / 1.5) * 0.82 + np.exp(-np.maximum(E, 0) / 5.5) * 0.16 * (E > -1.5)
    band = np.clip(band, 0, 0.9) * (0.75 + 0.25 * d[None, :])
    s[:] = s * (1 - band[..., None]) + hz * band[..., None]
    low = smoothstep(0.15, -0.9, E)[..., None]                        # the ground: nothing of the far city shows under the horizon
    gcol = hz * 0.42 * np.exp(np.minimum(E, 0) / 3.0)[..., None] + np.array((9, 8, 12), np.float32)
    s[:] = s * (1 - low) + gcol * low
    return base


# ----------------------------------------------------------------------------------------------------------------- dunes
HAZE_D = np.array((240, 190, 142), np.float32)


def ridge(seed, amp, freq, mesa, butte=0.0, rng=None):
    """skyline elevation (deg) per column: rolling ridge, flattened into mesas, with optional buttes"""
    n = yaw_noise(freq, seed, octaves=4)
    fine = yaw_noise(freq * 6, seed + 1, z=0.5, octaves=3)
    h = n * 0.75 + fine * 0.25
    step = np.clip((h - 0.42) / 0.16, 0, 1)
    h = h * (1 - mesa) + (0.25 + 0.6 * step + 0.06 * fine) * mesa
    e = amp * h
    if butte and rng is not None:
        for _ in range(int(butte)):
            c = rng.randint(W8); w = int(rng.uniform(0.8, 3.2) * PPD); top = amp * rng.uniform(0.9, 1.45)
            x = np.abs(np.arange(-2 * w, 2 * w) / w)
            idx = (c + np.arange(-2 * w, 2 * w)) % W8
            notch = 0.05 * (fine[idx] - 0.5) * top
            cap = top + notch                                           # the flat cap
            cliff = top * (0.62 + 0.38 * np.clip((0.6 - x) / 0.07, 0, 1))  # a near-vertical cliff under its rim
            talus = top * 0.62 * np.clip((1.9 - x) / 1.3, 0, 1) ** 1.4      # the scree skirt
            prof = np.where(x < 0.53, cap, np.where(x < 0.6, cliff, talus)) + notch * 0.5
            e[idx] = np.maximum(e[idx], prof)
    return e.astype(np.float32)


def dunes(base, sun_yaw=60.0):
    rng = np.random.RandomState(2209)
    S = Strip()
    E = strip_el()
    yaw = (np.arange(W8) + 0.5) / W8 * 360.0
    toward = (0.5 + 0.5 * np.cos(np.radians(yaw - sun_yaw))).astype(np.float32)[None, :]
    layers = [(61, 3.0, 3.0, 0.5, 0, (150, 104, 96), 0.72), (63, 4.6, 4.5, 0.8, 10, (112, 72, 74), 0.46), (65, 5.2, 2.6, 0.9, 6, (58, 36, 44), 0.14)]
    streaks = (0.5 + 0.5 * yaw_noise(140.0, 71, octaves=2))[None, :, None]             # gullies down the cliff faces
    strata = (fbm(np.arange(SH)[:, None] * 0.09, 0 * np.arange(SH)[:, None] + 0.3, 0 * np.arange(SH)[:, None], 3, seed=70) * 0.5 + 0.5).astype(np.float32)
    plant_at = []
    for li, (seed, amp, freq, mesa, nb, col, haze) in enumerate(layers):
        e = ridge(seed, amp, freq, mesa, nb, rng)[None, :]
        cover = np.clip((e - E) * PPD + 0.5, 0, 1) * (E > -3.0)       # antialiased silhouette edge
        c = np.array(col, np.float32)[None, None, :] * (1 - haze) + HAZE_D[None, None, :] * haze
        c = c * (1 - 0.3 * toward[..., None]) + HAZE_D[None, None, :] * (0.3 * toward[..., None]) * (0.6 + haze)
        rel = np.clip((e - E) / np.maximum(e, 0.2), 0, 1)             # 0 at the rim, 1 at the foot
        rim = np.exp(-rel * 14.0) * toward * 0.5                      # dusk rim light toward the sun
        c = c * (1 + 0.10 * (strata[:, :, None] - 0.5) * (1 - haze) * 2) + np.array((255, 200, 150), np.float32) * rim[..., None] * (1 - haze * 0.5)
        c = c * (1 + 0.16 * (streaks - 0.5) * (1 - haze))
        c = c * (1 - 0.42 * rel[..., None] ** 2) + HAZE_D[None, None, :] * (0.42 * rel[..., None] ** 2)   # dust at the foot
        S.col[:] = S.col * (1 - cover[..., None]) + c * cover[..., None]
        S.a[:] = S.a * (1 - cover) + cover
        S.em *= (1 - cover[..., None])
        if li == 2:                                                    # industry stands in front of the ranges
            for cy in (205.0, 318.0): plant_at.append(refinery(S, rng, int(cy * PPD), 0.38))
            for cy in rng.uniform(0, 360, 7):
                if min(abs(cy - 205), abs(cy - 318)) > 14: derrick(S, rng, int(cy * PPD), rng.uniform(1.8, 3.0))
    S.composite(base, glow=((4, 0.6), (16, 0.5), (48, 0.3)))
    s = base[R0:R1]
    for c0, tops in plant_at: smoke(s, rng, tops)
    band = np.exp(-np.abs(E - 0.1) / 0.9) * (0.36 + 0.3 * toward)
    s[:] = s * (1 - band[..., None]) + HAZE_D * band[..., None]
    low = smoothstep(0.1, -0.7, E)[..., None]                         # the desert floor: nothing far shows under the horizon
    gcol = HAZE_D * 0.62 * np.exp(np.minimum(E, 0) / 2.5)[..., None] + np.array((92, 68, 52), np.float32) * (1 - np.exp(np.minimum(E, 0) / 2.5))[..., None]
    s[:] = s * (1 - low) + gcol * low
    return base


IND = np.array((52, 38, 42), np.float32)


def refinery(S, rng, c, haze):
    body = IND * (1 - haze * 0.55) + HAZE_D * haze * 0.55
    tops = []
    span = int(15.0 * PPD); K = 2.2
    for k in range(9):                                                 # tanks and sheds
        w = int(rng.uniform(0.35, 1.1) * PPD * K); cc = c + rng.randint(-span // 2, span // 2); h = rng.uniform(0.18, 0.5) * K
        b = S.box(cc, cc + w, -2.0, h, body)
        if b: S.put(*b)
        for j in range(0, w, rng.randint(9, 16)): S.dot(cc + j, h * rng.uniform(0.3, 0.9), np.array(WARM) * rng.uniform(0.5, 0.9), 2)
    for k in range(26):                                                # columns, stacks, cracking towers
        w = rng.randint(4, 12); cc = c + rng.randint(-span // 2, span // 2); h = rng.uniform(0.5, 2.3) * (1.3 if k < 3 else 1.0) * K
        b = S.box(cc, cc + w, -2.0, h, body * rng.uniform(0.85, 1.05))
        if b: S.put(*b)
        if w >= 4:                                                     # platforms with lights
            for e in np.arange(0.5, h, rng.uniform(0.4, 0.7)):
                b = S.box(cc - 2, cc + w + 2, e, e + 0.04, body * 0.9)
                if b: S.put(*b)
                S.dot(cc + w + 1, e + 0.05, np.array(WARM) * 0.9, 2)
        if k < 3:                                                      # flare stacks
            fh = rng.uniform(0.7, 1.2); n = int(fh * PPD)
            for j in range(n):
                f = j / n; ww = max(2, int((1 - f) ** 0.7 * 15 * (0.7 + 0.5 * math.sin(j * 0.45 + k))))
                colr = np.array((255, 236, 170), np.float32) * (1 - f) + np.array((255, 110, 30), np.float32) * f
                S.dot(cc + w // 2 - ww // 2 + int(2 * math.sin(j * 0.5 + k)), h + j / PPD, colr, 1)
                r = S.rc(h + j / PPD)
                if 0 <= r < SH: S.em[r, S.cols(cc + w // 2 - ww // 2, cc + w // 2 + ww // 2 + 1)] = colr
            tops.append((cc + w // 2, h + fh))
        elif h > 3.0:
            S.dot(cc, h + 0.03, (255, 40, 30), 2); tops.append((cc + w // 2, h))
    for k in range(5):                                                 # pipe racks
        cc = c + rng.randint(-span // 2, span // 3); w = int(rng.uniform(1.0, 2.5) * PPD * K); e = rng.uniform(0.3, 1.0)
        b = S.box(cc, cc + w, e, e + 0.05, body)
        if b: S.put(*b)
    return c, tops


def derrick(S, rng, c, h):
    body = IND * 0.6 + HAZE_D * 0.4
    n = int(h * PPD); half = int(0.3 * PPD)
    for j in range(n):
        f = j / n; hw = max(1, int(half * (1 - f)))
        e = j / PPD
        for cc in (c - hw, c + hw):
            b = S.box(cc, cc + 2, e, e + 1.5 / PPD, body)
            if b: S.put(*b)
        if j % 9 == 0:
            b = S.box(c - hw, c + hw + 2, e, e + 1.5 / PPD, body)
            if b: S.put(*b)
    b = S.box(c - half, c + half, -2.0, 0.05, body)
    if b: S.put(*b)
    S.dot(c, h + 0.03, (255, 50, 30), 2); S.dot(c - half, 0.12, np.array(WARM) * 0.8, 2)


def smoke(s, rng, tops):
    """soft dark plumes leaning downwind from the tallest stacks, drawn straight into the strip"""
    for cx, e0 in tops[:5]:
        n = int(rng.uniform(5, 9) * PPD); lean = 1
        k = np.arange(n); f = k / n
        n = n * 2; k = np.arange(n); f = k / n
        e = e0 + 2.2 * f ** 0.6 + 0.25 * np.sin(k * 0.012 + cx)
        wid = (4 + 60 * f ** 0.8)
        al = 0.4 * (1 - f) ** 1.2
        for j in range(0, n, 2):
            r = int(round(row_of(e[j]))) - R0; hw = int(wid[j])
            if r - hw < 0 or r + hw >= SH: continue
            yy = np.arange(-hw, hw + 1); prof = np.exp(-(yy / (hw * 0.55 + 1)) ** 2) * al[j]
            cc = np.array([(cx + lean * j) % W8, (cx + lean * j + 1) % W8])
            blk = s[np.ix_(r + yy, cc)]
            s[np.ix_(r + yy, cc)] = blk * (1 - prof[:, None, None]) + np.array((74, 56, 60), np.float32) * prof[:, None, None]


# ------------------------------------------------------------------------------------------------------------------ api
VISTAS = {'sprawl': sprawl, 'dunes': dunes}


def apply(arena, base):
    """base float (h, w, 3): returns a float (H8, W8, 3) panorama with the far scenery, or base unchanged for an arena without one"""
    if arena not in VISTAS: return base
    if base.shape[0] != H8:
        base = np.asarray(Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).resize((W8, H8), Image.BICUBIC), np.float32)
    return np.clip(VISTAS[arena](base.copy()), 0, 255)


def perspective(pano, yaw_deg, pitch_deg, fov=90.0, w=1600, h=900):
    """what a player sees: a pinhole view cut from the panorama (uint8 in, PIL image out)"""
    H, W = pano.shape[:2]
    f = (w / 2) / math.tan(math.radians(fov / 2))
    xs, ys = np.meshgrid(np.arange(w) - w / 2 + 0.5, np.arange(h) - h / 2 + 0.5)
    d = np.stack([np.full_like(xs, f), -xs, -ys], -1); d /= np.linalg.norm(d, axis=-1, keepdims=True)
    p, yw = math.radians(pitch_deg), math.radians(yaw_deg)
    x = d[..., 0] * math.cos(p) - d[..., 2] * math.sin(p); z = d[..., 0] * math.sin(p) + d[..., 2] * math.cos(p); y = d[..., 1]
    X = x * math.cos(yw) - y * math.sin(yw); Y = x * math.sin(yw) + y * math.cos(yw)
    col = ((np.degrees(np.arctan2(Y, X)) % 360) / 360 * W).astype(int) % W
    row = np.clip(((90 - np.degrees(np.arcsin(np.clip(z, -1, 1)))) / 180 * H).astype(int), 0, H - 1)
    return Image.fromarray(pano[row, col])


if __name__ == '__main__':
    import sky
    arena, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    pano = np.asarray(sky.make(arena))
    print('panorama', pano.shape)
    strip = pano[int(pano.shape[0] * (90 - 32) / 180):int(pano.shape[0] * (90 + 4) / 180)]
    for q in range(4):
        w4 = strip.shape[1] // 4
        Image.fromarray(strip[:, q * w4:(q + 1) * w4]).save(os.path.join(out, 'sky_%s_strip%d.jpg' % (arena, q)), quality=90)
    for yawd, pit in ((20, 8), (110, 8), (205, 6), (318, 6), (260, 14)):
        perspective(pano, yawd, pit).save(os.path.join(out, 'sky_%s_view_%03d.jpg' % (arena, yawd)), quality=90)
    print('previews in', out)
