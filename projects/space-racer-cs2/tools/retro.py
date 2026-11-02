"""retro.py: the retro pixel-art look shared by the generators: one original 32-colour palette (named colours
BLACK, INK, ... SAND), ordered (Bayer) dithering down to it, chunky nearest-neighbour upscaling, shading, scanlines,
value noise and pixel-art planets. Numpy only.

Draw at low resolution, `quantize` to the palette, `up` by 4: that is the whole recipe.

usage (import it):
    from retro import *          # palette names (GOLD, TEAL, ...) and quantize / up / shade / nearest ...
    q = quantize(img_rgb, 28)    # (h, w, 3) -> palette colours, dithered
    big = up(q, 4)               # 4x nearest-neighbour
    planet = pixel_sphere(64, SKYBLUE, bands=6)

From space-racer-cs2/tools/retro.py (MIT), made project-neutral.
"""
import numpy as np

# 32 colours, grouped by hue. Index 0 is black, 6 is white.
PALETTE = [
    (0, 0, 0), (24, 20, 37), (52, 40, 72), (90, 70, 110), (140, 110, 150), (200, 180, 210), (255, 255, 255),
    (24, 32, 56), (40, 64, 120), (60, 120, 220), (120, 200, 255), (180, 240, 255),
    (0, 120, 100), (20, 200, 170), (130, 255, 225),
    (40, 100, 40), (80, 200, 60), (170, 255, 110),
    (120, 60, 20), (220, 120, 30), (255, 190, 40), (255, 240, 150), (255, 100, 30),
    (140, 20, 40), (240, 60, 60), (255, 130, 110),
    (110, 30, 120), (220, 60, 200), (255, 150, 240),
    (60, 40, 30), (120, 90, 70), (200, 160, 120),
]
PAL = np.array(PALETTE, np.float32)
BLACK, INK, PLUM, MAUVE, LILAC, PALE, WHITE = PALETTE[0:7]
NAVY, BLUE, SKYBLUE, ICE, FROST = PALETTE[7:12]
DEEPTEAL, TEAL, MINT = PALETTE[12:15]
DARKGREEN, GREEN, LIME = PALETTE[15:18]
RUST, ORANGE, GOLD, CREAM, HOT = PALETTE[18:23]
WINE, RED, SALMON = PALETTE[23:26]
PURPLE, MAGENTA, PINK = PALETTE[26:29]
SOIL, TAN, SAND = PALETTE[29:32]

BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) / 16.0 - 0.5 + 1 / 32.0
BAYER2 = np.array([[0, 2], [3, 1]], np.float32) / 4.0 - 0.5 + 1 / 8.0

def quantize(img, spread=28.0, palette=None, bayer=BAYER4):
    """nearest palette colour per pixel after adding an ordered-dither offset (spread = dither strength in 0..255 units).
    img: (h, w, 3) any numeric; returns uint8 (h, w, 3)."""
    pal = PAL if palette is None else np.array(palette, np.float32)
    a = np.asarray(img, np.float32)[..., :3]
    h, w = a.shape[:2]
    ty = np.tile(bayer, (h // bayer.shape[0] + 1, w // bayer.shape[1] + 1))[:h, :w]
    a = a + (ty * spread)[..., None]
    flat = a.reshape(-1, 3)
    # distance to every palette entry, in chunks to keep memory small
    out = np.empty(flat.shape[0], np.int32)
    CH = 65536
    for s in range(0, flat.shape[0], CH):
        d = ((flat[s:s + CH, None, :] - pal[None, :, :]) ** 2).sum(2)
        out[s:s + CH] = d.argmin(1)
    return pal[out].reshape(h, w, 3).astype(np.uint8)

def quantize_rgba(img, spread=28.0, palette=None):
    """like quantize but keeps the alpha channel (alpha is thresholded to 0 / 255 for a clean pixel edge)"""
    a = np.asarray(img)
    rgb = quantize(a[..., :3], spread, palette)
    alpha = (a[..., 3] >= 128).astype(np.uint8) * 255 if a.shape[-1] > 3 else np.full(rgb.shape[:2], 255, np.uint8)
    return np.dstack([rgb, alpha])

def up(img, k=4):
    """nearest-neighbour upscale by an integer factor (chunky pixels)"""
    a = np.asarray(img)
    return np.repeat(np.repeat(a, k, 0), k, 1)

def nearest(color):
    """the palette colour closest to an (r, g, b)"""
    d = ((PAL - np.array(color, np.float32)) ** 2).sum(1)
    return PALETTE[int(d.argmin())]

def shade(color, k):
    """a palette colour scaled by k (0..2), snapped back to the palette"""
    return nearest(tuple(min(255, max(0, c * k)) for c in color))

def scanlines(img, every=4, dark=0.72):
    """darken every n-th row (a CRT look for pictures that are not game textures)"""
    a = np.asarray(img).astype(np.float32).copy()
    a[::every, :, :3] *= dark
    return a.clip(0, 255).astype(np.uint8)

def noise(h, w, seed, scale=8):
    """smooth value noise in 0..1"""
    rng = np.random.RandomState(seed)
    small = rng.rand(h // scale + 2, w // scale + 2)
    y = np.linspace(0, h / scale, h, endpoint=False); x = np.linspace(0, w / scale, w, endpoint=False)
    yi = np.floor(y).astype(int); xi = np.floor(x).astype(int)
    fy = (y - yi)[:, None]; fx = (x - xi)[None, :]
    fy = fy * fy * (3 - 2 * fy); fx = fx * fx * (3 - 2 * fx)
    a = small[yi][:, xi]; b = small[yi][:, xi + 1]; c = small[yi + 1][:, xi]; d = small[yi + 1][:, xi + 1]
    return a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy

def pixel_sphere(size, color, light=(-0.5, -0.6), rings=False, bands=0, seed=1):
    """an RGBA pixel-art planet: a shaded disc (3 shade steps), optional latitude bands and a ring"""
    r = size / 2
    yy, xx = np.mgrid[0:size, 0:size]
    dx = (xx + 0.5 - r) / r; dy = (yy + 0.5 - r) / r
    d2 = dx * dx + dy * dy
    inside = d2 <= 1
    nz = np.sqrt(np.clip(1 - d2, 0, 1))
    lit = (dx * light[0] + dy * light[1] + nz * 0.8)
    img = np.zeros((size, size, 4), np.float32)
    base = np.array(color, np.float32)
    k = np.where(lit > 0.55, 1.25, np.where(lit > 0.15, 1.0, np.where(lit > -0.2, 0.7, 0.45)))
    if bands:
        n = noise(size, size, seed, max(2, size // 16))
        band = np.sin((dy * 0.9 + n * 0.25) * bands * np.pi) > 0.2
        k = k * np.where(band, 0.85, 1.0)
    img[..., :3] = base[None, None, :] * k[..., None]
    img[..., 3] = inside * 255
    return img

def write_png(path, rgb):
    from PIL import Image
    Image.fromarray(np.ascontiguousarray(np.asarray(rgb).astype(np.uint8))).save(path)
