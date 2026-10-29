"""skies.py: pixel-art sky panoramas (equirectangular 2048 x 1024, drawn at 512 x 256 in the retro palette and
upscaled 4x). Layers: gradient bands, a dithered nebula, pixel stars, a big planet (or a striped retro sun) and a
silhouette along the horizon (city towers or mountain peaks). Use the PNG as an env_sky / moondome texture.

A theme is a dict (colours are (r, g, b), usually names from retro.py):
    sky     = (top, mid, horizon)   the gradient from straight up to the horizon (below the horizon fades to black)
    glow    = colour                nebula tint, horizon edge and lit city windows
    planet  = (colour, kind)        kind: 'sun' (striped, low on the horizon), 'ringed', 'banded', 'moon' / 'cratered',
                                    anything else = a plain shaded planet
    scenery = 'city' | 'rings' | 'mountains' ...   horizon silhouette ('city'/'rings' = towers, otherwise peaks)
After make_sky(), skies.LAST_PLANET is (x, y, radius) of the big body at 512 x 256 scale (for framing pictures).

usage:
    skies.py <out.png> [theme] [seed] [style]  theme = one of EXAMPLE_THEMES (default dusk); style = pixel | neon | depth
    import skies; img = skies.make_sky(dict(sky=(BLACK, NAVY, TEAL), glow=MINT, planet=(SKYBLUE, 'ringed')), 'city', 3)

From space-racer-cs2/tools/skies.py (MIT), made project-neutral.
"""
import math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))     # finds retro.py (also under python3 -I)
from retro import *
import retro

W, H = 512, 256

def lerp(a, b, t): return np.array(a, np.float32) * (1 - t) + np.array(b, np.float32) * t

def gradient(top, mid, hor):
    """rows: 0 = straight up, H/2 = horizon, H = straight down"""
    img = np.zeros((H, W, 3), np.float32)
    for y in range(H):
        lat = 1 - y / (H / 2)          # 1 up .. 0 horizon .. -1 down
        if lat >= 0.45: c = lerp(top, mid, (1 - lat) / 0.55)
        elif lat >= 0: c = lerp(mid, hor, (0.45 - lat) / 0.45)
        else: c = lerp(hor, BLACK, min(1, -lat / 0.25))
        img[y] = c
    return img

def stars(img, rng, n=900, big=40):
    ys = (rng.rand(n) ** 1.3 * H * 0.5).astype(int); xs = rng.randint(0, W, n)
    for y, x in zip(ys, xs):
        img[y, x] = WHITE if rng.rand() < 0.5 else PALE
    for _ in range(big):
        y, x = int(rng.rand() ** 1.2 * H * 0.45), rng.randint(2, W - 2)
        col = [WHITE, ICE, CREAM, PINK][rng.randint(4)]
        img[y, x] = WHITE
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)): img[y + dy, x + dx] = col
        if rng.rand() < 0.3:
            for dy, dx in ((0, 2), (0, -2), (2, 0), (-2, 0)):
                if 0 <= y + dy < H: img[y + dy, (x + dx) % W] = col

def nebula(img, rng, colors, strength=0.55, seed=3):
    n1 = retro.noise(H, W, seed, 24); n2 = retro.noise(H, W, seed + 7, 9)
    yy = np.arange(H)[:, None]
    band = np.exp(-((yy - H * 0.3 - 18 * np.sin(np.arange(W)[None, :] / W * 4 * math.pi)) / (H * 0.12)) ** 2)
    m = np.clip((n1 * 0.7 + n2 * 0.3 - 0.45) * 2.2, 0, 1) * band
    c0, c1 = np.array(colors[0], np.float32), np.array(colors[1], np.float32)
    col = c0[None, None, :] * (1 - n2[..., None]) + c1[None, None, :] * n2[..., None]
    img[:] = img * (1 - m[..., None] * strength) + col * m[..., None] * strength

def paste(img, sprite, cx, cy):
    h, w = sprite.shape[:2]
    y0, x0 = int(cy - h / 2), int(cx - w / 2)
    for yy in range(h):
        y = y0 + yy
        if not 0 <= y < H: continue
        for xx in range(w):
            if sprite[yy, xx, 3] > 0: img[y, (x0 + xx) % W] = sprite[yy, xx, :3]

LAST_PLANET = None      # (x, y, radius) of the big body in the last sky made (the loading screen frames it)

def planet(img, rng, color, kind):
    global LAST_PLANET
    cx, cy = rng.randint(60, W - 60), int(H * 0.26)
    if kind == 'sun':
        # a striped retro sun sitting low over the horizon
        R = 46; cy = int(H * 0.5) - 26
        LAST_PLANET = (cx, cy, R)
        for y in range(cy - R, cy + R + 1):
            for x in range(cx - R, cx + R + 1):
                d = math.hypot(x - cx, y - cy)
                if d > R: continue
                t = (y - (cy - R)) / (2 * R)
                c = lerp(GOLD, HOT, t) if t < 0.5 else lerp(HOT, MAGENTA, (t - 0.5) * 2)
                if t > 0.45 and int((y - cy) * 0.55) % 2 == 0 and (y - cy) % max(2, int(6 - t * 4)) < 2: continue
                img[y, x % W] = c
        return
    size = 84 if kind in ('ringed', 'banded') else 64
    LAST_PLANET = (cx, cy, size // 2)
    sp = pixel_sphere(size, color, bands=6 if kind in ('banded', 'ringed') else 0, seed=rng.randint(99))
    if kind in ('moon', 'cratered'):
        for _ in range(9):
            x, y, r = rng.randint(8, size - 8), rng.randint(8, size - 8), rng.randint(2, 6)
            yy, xx = np.mgrid[0:size, 0:size]
            m = (np.hypot(xx - x, yy - y) < r) & (sp[..., 3] > 0)
            sp[m, :3] *= 0.7
    if kind == 'ringed':
        big = np.zeros((size, size * 2, 4), np.float32)
        big[:, size // 2:size // 2 + size] = sp
        yy, xx = np.mgrid[0:size, 0:size * 2]
        e = ((xx - size) / (size * 0.95)) ** 2 + ((yy - size / 2) / (size * 0.2)) ** 2
        ring = (e > 0.75) & (e < 1.0)
        front = ring & (yy > size / 2)
        back = ring & (yy <= size / 2) & (big[..., 3] == 0)
        for m in (front, back):
            big[m, :3] = np.array(CREAM if m is front else SAND, np.float32)
            big[m, 3] = 255
        sp = big
    paste(img, sp, cx, cy)
    # a small moon nearby
    paste(img, pixel_sphere(18, PALE), (cx + 90) % W, cy + 30)

def horizon(img, rng, kind, col):
    """a dark silhouette along the horizon: towers for cities, peaks otherwise"""
    hy = H // 2
    if kind in ('city', 'rings'):
        x = 0
        while x < W:
            w = rng.randint(4, 14); h = rng.randint(4, 26)
            img[hy - h:hy + 1, x:min(W, x + w)] = INK
            for wy in range(hy - h + 2, hy, 3):
                for wx in range(x + 1, x + w - 1, 2):
                    if rng.rand() < 0.3: img[wy, wx % W] = col
            x += w + rng.randint(0, 3)
    else:
        n = retro.noise(1, W, rng.randint(99), 20)[0]
        n2 = retro.noise(1, W, rng.randint(99), 5)[0]
        for x in range(W):
            h = int(6 + 22 * n[x] + 6 * n2[x])
            img[hy - h:hy + 1, x] = INK
            img[hy - h, x] = col

def make_sky(th, scenery=None, seed=1, style='pixel'):
    """one equirect sky (2048 x 1024 RGB uint8) from a theme dict (see the top of this file); scenery overrides th['scenery'].
    style: 'pixel' (retro palette), 'neon' (black sky, glowing horizon grid and skyline), 'depth' (underwater: surface, light shafts)"""
    if style == 'neon': return make_sky_neon(th, scenery or th.get('scenery', 'city'), seed)
    if style == 'depth': return make_sky_depth(th, scenery or th.get('scenery', 'mountains'), seed)
    scenery = scenery or th.get('scenery', 'mountains')
    rng = np.random.RandomState(seed)
    top, mid, hor = th['sky']
    img = gradient(top, mid, hor)
    nebula(img, rng, (th['glow'], mid), seed=seed)
    stars(img, rng)
    planet(img, rng, th['planet'][0], th['planet'][1])
    horizon(img, rng, scenery, th['glow'])
    q = quantize(img, 30)
    return up(q, 4)


def _neon_palette():
    hues = [(0, 235, 255), (255, 40, 200), (255, 140, 20), (110, 255, 60), (150, 80, 255), (255, 40, 70), (255, 210, 60),
            (60, 120, 255)]
    pal = [(0, 0, 0), (6, 8, 16), (14, 16, 30), (26, 28, 48), (255, 255, 255), (200, 240, 255), (255, 230, 245)]
    for h in hues:
        for k in (1.0, 0.6, 0.3, 0.14):
            pal.append(tuple(int(c * k) for c in h))
    return pal
def _depth_palette():
    """the deep sea: blue-black water, teal and green glow, coral and amber life, a pale surface light"""
    hues = [(0, 210, 190), (60, 220, 255), (70, 255, 150), (255, 110, 90), (255, 190, 60), (150, 90, 255), (255, 90, 200),
            (40, 120, 200)]
    pal = [(0, 0, 0), (2, 8, 20), (6, 18, 34), (12, 32, 52), (24, 54, 74), (235, 250, 255), (170, 230, 240), (60, 70, 90), (30, 36, 50)]
    for h in hues:
        for k in (1.0, 0.6, 0.3, 0.14):
            pal.append(tuple(int(c * k) for c in h))
    return pal
NEON_PAL, DEPTH_PAL = _neon_palette(), _depth_palette()

def pixelate(img, k=4, spread=14.0, palette=None):
    """full-size float image -> shrink k x (box average), dither to the palette, nearest-neighbour back up"""
    a = np.asarray(img, np.float32)
    h, w = a.shape[0] // k * k, a.shape[1] // k * k
    small = a[:h, :w].reshape(h // k, k, w // k, k, 3).mean((1, 3))
    return up(quantize(small, spread, palette), k)

# ---------------------------------------------------------------- neon style (from Neon Racer)
def make_sky_neon(th, scenery=None, seed=1):
    """black sky over a glowing horizon, a perspective grid floor below it, a striped sun (or a ringed planet drawn in
    lines), a skyline whose edges glow, and a few stars. Smooth, not pixel art."""
    Wn, Hn = 2048, 1024
    rng = np.random.RandomState(seed)
    top, mid, hor = [np.array(c, np.float32) for c in th['sky']]
    glow = np.array(th['glow'], np.float32); acc = np.array(th.get('accent', th['glow']), np.float32)
    yy, xx = np.mgrid[0:Hn, 0:Wn].astype(np.float32)
    lat = 1 - yy / (Hn / 2)                          # 1 up, 0 horizon, -1 down
    img = np.zeros((Hn, Wn, 3), np.float32)
    up_ = np.clip(lat, 0, 1)[..., None]
    img += top * up_ ** 0.6 + mid * (1 - up_ ** 0.6)
    img += glow * 0.55 * np.exp(-np.abs(lat) / 0.06)[..., None] + glow * 0.18 * np.exp(-np.abs(lat) / 0.25)[..., None]
    # stars
    for _ in range(700):
        x, y = rng.randint(0, Wn), int(rng.rand() ** 1.4 * Hn * 0.42)
        img[y, x] += 160 + 95 * rng.rand()
    # the grid floor: lines across that close up towards the horizon, lines along that fan out
    below = lat < 0
    depth = 1.0 / np.maximum(-lat, 1e-3)              # distance-ish
    rows = np.abs(((depth * 2.0) % 1.0) - 0.5)
    rowline = np.exp(-(0.5 - rows) * 40.0 / np.maximum(depth, 1) ** 0.2)
    ang = (xx / Wn * 2 * math.pi)
    cols = np.abs(((ang / (2 * math.pi) * 64) % 1.0) - 0.5)
    colline = np.exp(-(0.5 - cols) * 30.0 * np.clip(-lat * 6, 0.3, 4))
    fade = np.clip(-lat * 4, 0, 1)
    img += (glow * (np.maximum(rowline, colline) * fade * below)[..., None])
    img[below] *= 0.85
    # sun or planet
    cx, cy = rng.randint(300, Wn - 300), Hn // 2 - 150
    global LAST_PLANET
    if th['planet'][1] == 'sun':
        R = 190; cy = Hn // 2 - 110
        d = np.hypot(xx - cx, yy - cy)
        t = np.clip((yy - (cy - R)) / (2 * R), 0, 1)
        col = (np.array((255, 230, 90), np.float32)[None, None] * (1 - t[..., None]) + acc[None, None] * t[..., None])
        stripe = (t > 0.45) & (((yy - cy) % np.maximum(8, 30 - t * 22)) < (4 + t * 10))
        m = (d < R) & ~stripe & (yy < Hn // 2)
        img[m] = col[m]
        img += acc * 0.5 * np.exp(-np.maximum(d - R, 0) / 40)[..., None] * (yy < Hn // 2)[..., None]
    else:
        R = 150
        d = np.hypot(xx - cx, yy - cy)
        img[d < R] = img[d < R] * 0.2 + np.array((4, 4, 10), np.float32)
        img += acc * np.exp(-np.abs(d - R) / 3.0)[..., None]
        for k in range(4):
            img += acc * 0.35 * np.exp(-np.abs(d - R * (0.85 - k * 0.2)) / 1.5)[..., None] * (d < R)[..., None]
        if th['planet'][1] in ('ringed', 'banded'):
            e = np.hypot((xx - cx) / (R * 1.9), (yy - cy) / (R * 0.35))
            ring = np.exp(-np.abs(e - 1) * 60) * ((yy > cy) | (d > R))
            img += glow * ring[..., None]
    LAST_PLANET = (cx // 4, cy // 4, (190 if th['planet'][1] == 'sun' else 150) // 4)   # in the pixel skies' 512 x 256 units
    # skyline: towers (city) or crystal spikes, black with glowing outlines
    hy = Hn // 2
    x = 0
    sil = np.zeros((Hn, Wn), bool)
    while x < Wn:
        w = rng.randint(14, 60); h = rng.randint(14, 110) if scenery == 'city' else rng.randint(10, 70)
        if scenery == 'city':
            sil[hy - h:hy, x:x + w] = True
        else:
            for c in range(w):
                hh = int(h * (1 - abs(c - w / 2) / (w / 2)))
                sil[hy - hh:hy, (x + c) % Wn] = True
        x += w + rng.randint(0, 10)
    edge = sil & ~(np.roll(sil, 1, 0) & np.roll(sil, -1, 0) & np.roll(sil, 1, 1) & np.roll(sil, -1, 1))
    img[sil] = np.array((3, 3, 8), np.float32)
    img[edge] = glow
    lit = sil & (rng.rand(Hn, Wn) < 0.012)
    img[lit] = acc
    return pixelate(np.clip(img, 0, 255), 4, 10.0, NEON_PAL)

# ---------------------------------------------------------------- depth style: underwater (from Depth Racer)
def make_sky_depth(th, scenery=None, seed=1):
    """looking round under the sea: the rippling bright surface overhead with light shafts slanting down, the water
    darkening to the abyss below, a far ridge of rock and kelp along the 'horizon', drifting marine snow, and the
    silhouette of something very big in the distance. Pixelated like the neon skies."""
    global LAST_PLANET
    Wn, Hn = 2048, 1024
    rng = np.random.RandomState(seed)
    top, mid, low = [np.array(c, np.float32) for c in th['sky']]
    glow = np.array(th['glow'], np.float32); acc = np.array(th.get('accent', th['glow']), np.float32)
    yy, xx = np.mgrid[0:Hn, 0:Wn].astype(np.float32)
    lat = 1 - yy / (Hn / 2)
    up_ = np.clip(lat, 0, 1)[..., None]; dn = np.clip(-lat, 0, 1)[..., None]
    img = mid * (1 - up_) + top * up_ ** 1.6
    img = img * (1 - dn) + low * dn ** 0.5 + mid * 0.25 * (1 - dn) * (lat < 0)[..., None]
    # the surface: a bright rippling band at the very top
    ang = xx / Wn * 2 * math.pi
    rip = 0.5 + 0.5 * np.sin(ang * 40 + 3 * np.sin(ang * 7)) * np.sin(ang * 23)
    surf = np.clip((lat - 0.86) / 0.14, 0, 1) ** 1.5
    img += np.array((150, 230, 240), np.float32) * (surf * (0.4 + 0.6 * rip))[..., None]
    # light shafts: slanted bright bands fading down into the water
    for _ in range(18):
        x0 = rng.uniform(0, Wn); w = rng.uniform(40, 120); slant = rng.uniform(-0.3, 0.3); k = rng.uniform(0.08, 0.2)
        d = np.abs(((xx - x0 - (yy * slant)) + Wn / 2) % Wn - Wn / 2)
        shaft = np.clip(1 - d / w, 0, 1) * np.clip(lat + 0.1, 0, 1) ** 1.5
        img += np.array((120, 200, 210), np.float32) * (shaft * k)[..., None]
    # something huge far away: a whale's silhouette, side on, high in the water
    cx, cy = rng.randint(300, Wn - 300), int(Hn * 0.30)
    L_, H_ = 420, 90
    body = (((xx - cx) / L_) ** 2 + ((yy - cy) / H_) ** 2 <= 1) | (((xx - cx + L_ * 1.05) / 70) ** 2 + ((yy - cy) / 60) ** 2 <= 1) & (xx < cx - L_ * 0.9)
    fluke = (np.abs(xx - (cx - L_ * 1.12)) < 30) & (np.abs(yy - cy) < 110 - np.abs(xx - (cx - L_ * 1.12)) * 2)
    sil = body | fluke
    img[sil] = img[sil] * 0.45 + np.array((4, 14, 24), np.float32) * 0.55
    LAST_PLANET = (cx // 4, cy // 4, L_ // 8)
    # the far seabed: a ridge of rock, with kelp and coral silhouettes standing on it and a glowing rim
    hy = Hn // 2
    ridge = (30 + 40 * np.sin(np.arange(Wn) / Wn * 2 * math.pi * 3 + seed) + 22 * np.sin(np.arange(Wn) / 37.0)).astype(int)
    sil = np.zeros((Hn, Wn), bool)
    for x in range(Wn):
        sil[hy - ridge[x]:hy + 160, x] = True
    for _ in range(140):
        x = rng.randint(0, Wn); h = rng.randint(30, 200); base = hy - ridge[x]
        for k in range(h):
            xo = int(x + 6 * math.sin(k / 18.0 + x))
            if 0 <= xo < Wn and base - k > 0: sil[base - k, max(0, xo - 1):xo + 2] = True
    edge = sil & ~(np.roll(sil, 1, 0) & np.roll(sil, -1, 0) & np.roll(sil, 1, 1) & np.roll(sil, -1, 1))
    img[sil] = np.array((3, 10, 18), np.float32)
    img[edge] = glow * 0.7
    lit = sil & (rng.rand(Hn, Wn) < 0.004)
    img[lit] = acc
    # marine snow: specks drifting everywhere
    for _ in range(1600):
        x, y = rng.randint(0, Wn), rng.randint(0, Hn)
        img[y, x] += 60 + 80 * rng.rand()
    return pixelate(np.clip(img, 0, 255), 4, 10.0, DEPTH_PAL)



EXAMPLE_THEMES = {
    'dusk': dict(sky=(BLACK, PURPLE, HOT), glow=GOLD, planet=(HOT, 'sun'), scenery='city'),
    'ocean': dict(sky=(BLACK, NAVY, DEEPTEAL), glow=TEAL, planet=(SKYBLUE, 'ringed'), scenery='mountains'),
    'neon': dict(sky=(BLACK, PURPLE, MAGENTA), glow=MAGENTA, planet=(SKYBLUE, 'banded'), scenery='city'),
    'mars': dict(sky=(BLACK, INK, WINE), glow=RED, planet=(RED, 'cratered'), scenery='mountains'),
    'jungle': dict(sky=(BLACK, DARKGREEN, TEAL), glow=LIME, planet=(LIME, 'banded'), scenery='mountains'),
    'desert': dict(sky=(BLACK, SOIL, ORANGE), glow=GOLD, planet=(SAND, 'ringed'), scenery='rings'),
}

if __name__ == '__main__':
    import sys
    from PIL import Image
    if len(sys.argv) < 2: sys.exit(__doc__)
    name = sys.argv[2] if len(sys.argv) > 2 else 'dusk'
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    style = sys.argv[4] if len(sys.argv) > 4 else 'pixel'
    img = make_sky(EXAMPLE_THEMES[name], seed=seed, style=style)
    Image.fromarray(img).save(sys.argv[1])
    print('sky', name, img.shape[1], 'x', img.shape[0], '->', sys.argv[1], 'planet at', LAST_PLANET)
