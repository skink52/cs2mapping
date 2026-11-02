"""Space Racer Workshop art: the square preview icon (1024 x 1024), drawn like everything else in the game - at low
resolution in the retro palette, then blown up with square pixels.

usage: workshop.py <out_dir> [car]
writes <out_dir>/icon.png (Steam's limit is 1 MB; this is about 35 KB)"""
import os, sys, math
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import pixfont, retro
from retro import *
import cars as C
from theme import NEON, DEPTH

OUTD = sys.argv[1] if len(sys.argv) > 1 else '.'
HERO = sys.argv[2] if len(sys.argv) > 2 else 'hornet'
B = 256                    # drawing size; the icon is 4x
HZ = 150                   # horizon
VX = B // 2                # vanishing point x
rng = np.random.RandomState(52)


def car_grid(key, boost=True):
    """the car's voxels as the game builds them (boosting: flames out of the engines)"""
    L, W, H = C.DIMS[key]
    g = C.Grid(L + (16 if boost else 0), W, H)
    if boost:
        g2 = C.Grid(L, W, H); C.CARS[key](g2, False)
        g.occ[16:, :, :] = g2.occ; g.col[16:, :, :] = g2.col
        C.CARS[key](C.ShiftedGrid(g, 16), True)
    else:
        C.CARS[key](g, False)
    return g


def car_sprite(key, skin, px, az=188, el=20):
    """a pixel sprite of the car, px wide at drawing size: rendered smooth, shrunk, put in the palette, outlined"""
    im = C.render_voxels(car_grid(key), C.palette(*C.SKINS[skin]), size=360, az=az, el=el, fill=0.96)
    im = im.resize((px, px), Image.BILINEAR)
    q = quantize_rgba(np.array(im), 10)
    a = q[..., 3] > 0
    o = np.zeros_like(a)
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)): o |= np.roll(np.roll(a, dy, 0), dx, 1)
    q[o & ~a] = (0, 0, 0, 255)
    # trim to the drawn part
    ys, xs = np.where(q[..., 3] > 0)
    return q[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def sky():
    img = np.zeros((B, B, 3), np.float32)
    stops = [(0, BLACK), (40, INK), (85, PURPLE), (125, MAGENTA), (HZ, HOT)]
    for y in range(HZ):
        for (y0, c0), (y1, c1) in zip(stops, stops[1:]):
            if y0 <= y <= y1:
                k = (y - y0) / max(1, y1 - y0)
                img[y] = np.array(c0) * (1 - k) + np.array(c1) * k
                break
    img = quantize(img.astype(np.uint8), spread=40)       # dithered bands
    for _ in range(140):                                   # stars, thinning towards the horizon
        x, y = rng.randint(0, B), int(rng.power(0.55) * 110)
        img[y, x] = ICE if rng.rand() < 0.33 else (PALE if rng.rand() < 0.5 else WHITE)
    for x, y in ((30, 22), (214, 40), (180, 14), (60, 70), (236, 92)):   # a few bright crosses
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)): img[y + dy, x + dx] = WHITE
    return img


def sun(img):
    cx, cy, r = VX, HZ - 18, 62
    yy, xx = np.mgrid[0:B, 0:B]
    disc = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
    grad = [CREAM, GOLD, GOLD, ORANGE, ORANGE, HOT, HOT, MAGENTA]
    for y in range(cy - r, min(HZ, cy + r + 1)):
        t = (y - (cy - r)) / (2 * r)
        col = grad[min(len(grad) - 1, int(t * len(grad)))]
        # the stripes: gaps that get thicker towards the bottom of the sun
        if y > cy - 28:
            k = (y - (cy - 28)) / (r + 28)
            period = 8
            gap = 1 + int(k * 4)
            if (y - (cy - 28)) % period < gap: continue
        row = disc[y] & (np.arange(B) >= 0)
        img[y, row] = col


def skyline(img):
    """dark towers along the horizon with a few lit windows, in front of the sun"""
    x = 0
    while x < B:
        w = rng.randint(6, 15)
        h = rng.randint(8, 34) if abs(x - VX) > 40 else rng.randint(4, 14)    # low in the middle: the sun shows
        top = HZ - h
        img[top:HZ, x:x + w] = INK
        img[top, x:x + w] = PLUM
        for wy in range(top + 3, HZ - 2, 4):
            for wx in range(x + 2, min(B, x + w - 2), 3):
                if rng.rand() < 0.28: img[wy, wx] = PINK if rng.rand() < 0.6 else ICE
        x += w + rng.randint(0, 3)


def ground(img):
    for y in range(HZ, B):
        k = (y - HZ) / (B - HZ)
        img[y] = np.array(BLACK) * (1 - k) + np.array(INK) * k
    for j in range(1, 16):                                 # cross lines bunching towards the horizon
        y = HZ + int((B - HZ) * (j / 15) ** 2.1)
        if y < B: img[y] = PURPLE if j < 4 else MAGENTA
    for i in range(-22, 23):                               # lines to the vanishing point
        x_top, x_bot = VX + i * 6, VX + i * 52
        for y in range(HZ, B):
            k = (y - HZ) / (B - HZ)
            x = int(round(x_top + (x_bot - x_top) * k))
            if 0 <= x < B: img[y, x] = MAGENTA if k > 0.15 else PURPLE


def road(img):
    """the track running from the viewer to the sun: dark deck, neon rails, centre dashes"""
    for y in range(HZ + 1, B):
        k = (y - HZ) / (B - HZ)
        half = 3 + k * 118
        x0, x1 = int(VX - half), int(VX + half)
        img[y, max(0, x0):min(B, x1)] = NAVY if (y // 2) % 2 else INK
        rail = max(1, int(k * 5))
        img[y, max(0, x0 - rail):max(0, x0)] = PINK
        img[y, min(B, x1):min(B, x1 + rail)] = PINK
        img[y, max(0, x0 - rail - 1):max(0, x0 - rail)] = MAGENTA
        img[y, min(B, x1 + rail):min(B, x1 + rail + 1)] = MAGENTA
        # centre dashes, longer near the viewer
        d = (1 / max(0.05, k)) * 6
        if int(d) % 2 == 0:
            w = max(1, int(k * 4))
            img[y, VX - w // 2:VX - w // 2 + w] = PINK


def neon_recolour(img):
    """Neon Racer: the grid and the road's rails in cyan instead of magenta"""
    for a, b in ((MAGENTA, SKYBLUE), (PINK, ICE), (PURPLE, BLUE)):
        m = (img[..., 0] == a[0]) & (img[..., 1] == a[1]) & (img[..., 2] == a[2])
        m[:HZ] = False
        img[m] = b


def gates(img):
    """Neon Racer: flight gate rings over the road, shrinking towards the sun"""
    for k, (cy, rx, ry, col, col2) in enumerate(((HZ - 6, 26, 22, ICE, SKYBLUE), (HZ + 8, 48, 40, ICE, SKYBLUE),
                                                (HZ + 34, 92, 76, WHITE, ICE))):
        for a in np.linspace(0, 2 * math.pi, 900):
            for t, c in ((-0.6, col), (0, col), (0.6, col), (1.8 + k, col2), (2.4 + k, col2)):
                x = int(round(VX + (rx + t) * math.cos(a))); y = int(round(cy - (ry + t) * math.sin(a)))
                if 0 <= x < B and 0 <= y < B and y < B - 40: img[y, x] = c
        # a gold boost ring inside the middle gate
        if k == 1:
            for a in np.linspace(0, 2 * math.pi, 400):
                x = int(round(VX + 16 * math.cos(a))); y = int(round(cy - 4 - 14 * math.sin(a)))
                img[y, x] = GOLD


def depth_scene(img):
    """Depth Racer: the scene under the sea - water instead of sky, light shafts, a serpent's coils over the road"""
    for y in range(HZ):
        k = y / HZ
        img[y] = np.array(SKYBLUE) * (1 - k) * 0.35 + np.array(NAVY) * k * 0.9 + np.array(INK) * 0.2
    for x0 in range(10, B, 37):                                     # light shafts
        for y in range(HZ):
            x = int(x0 + y * 0.25)
            if 0 <= x < B and (x + y) % 3: img[y, x] = np.minimum(255, img[y, x] + 25)
    img[0:4, :] = ICE
    for x in range(0, B, 2): img[4 + (x // 2) % 3, x] = WHITE                # the rippling surface
    # coral and kelp silhouettes on the horizon
    for x in range(0, B, 3):
        h = int(8 + 7 * math.sin(x / 9.0) + (x * 7919) % 9)
        img[HZ - h:HZ, x:x + 2] = DEEPTEAL if x % 2 else (40, 20, 60)
    # the sea floor: dim the grid to faint teal lines on dark sand
    floor = img[HZ:].reshape(-1, 3)
    m = (floor.sum(1) > 200)
    floor[m] = (np.array(DEEPTEAL) * 0.8).astype(floor.dtype)
    img[HZ:] = floor.reshape(img[HZ:].shape)
    # the serpent: thick coils arching out of the deep and over the road, head on the right
    xs = np.arange(14, B - 40)
    for x in xs:
        u = (x - 14) / (B - 54)
        y = HZ - 30 - 36 * math.sin(u * math.pi * 2.0) * (0.6 + 0.4 * u)
        r = 4 + 4 * math.sin(min(1, u * 1.4) * math.pi / 2)
        for t in range(int(-r), int(r) + 1):
            yy = int(round(y + t))
            if 0 <= yy < B:
                img[yy, x] = MINT if t < -r + 2 else (TEAL if t < r * 0.4 else DEEPTEAL)
        if int(x) % 7 == 0: img[int(round(y)), x] = SKYBLUE                 # glowing spots along the side
        if int(x) % 5 == 0 and r > 5: img[int(round(y - r - 1)), x] = PINK    # dorsal spines
    hx, hy = B - 40, int(round(HZ - 30 - 36 * math.sin(2.0 * math.pi) * 1.0))
    img[hy - 9:hy + 7, hx:hx + 20] = TEAL                                     # head
    img[hy - 9:hy - 7, hx:hx + 20] = MINT
    img[hy + 2:hy + 7, hx + 6:hx + 26] = DEEPTEAL                             # jaw
    for k in range(hx + 8, hx + 24, 3): img[hy + 1, k] = WHITE                # teeth
    img[hy - 6:hy - 3, hx + 12:hx + 16] = GOLD                                # eye


def speed_lines(img):
    for _ in range(26):
        side = rng.choice([-1, 1])
        y = rng.randint(HZ + 6, B - 4)
        k = (y - HZ) / (B - HZ)
        x_edge = VX + side * (8 + k * 125)
        ln = rng.randint(10, 26)
        for t in range(ln):
            xx = int(x_edge + side * t * 1.0); yy = int(y + t * 0.18 * k)
            if 0 <= xx < B and 0 <= yy < B: img[yy, xx] = ICE if t < ln * 0.6 else SKYBLUE


def paste(img, spr, x, y):
    h, w = spr.shape[:2]
    for yy in range(h):
        for xx in range(w):
            if spr[yy, xx, 3] and 0 <= y + yy < B and 0 <= x + xx < B: img[y + yy, x + xx] = spr[yy, xx, :3]


def main():
    img = sky()
    sun(img)
    skyline(img)
    ground(img)
    road(img)
    if NEON:
        neon_recolour(img)
        gates(img)
    if DEPTH: depth_scene(img)
    speed_lines(img)
    # the hero, seen from behind like the chase camera sees it, flames lit, heading for the sun
    hero = car_sprite(HERO, 't', 150)
    # a hover glow under the hero
    hx, hy = VX + 4 - hero.shape[1] // 2, B - 8 - hero.shape[0]
    yy, xx = np.mgrid[0:B, 0:B]
    glow = ((xx - VX - 4) / 46.0) ** 2 + ((yy - (B - 22)) / 6.0) ** 2 <= 1
    img[glow & ((xx + yy) % 2 == 0)] = ORANGE if NEON else TEAL
    paste(img, hero, hx, hy)
    big = up(img.astype(np.uint8), 4).copy()
    # the logo and the strap line, at full size
    from theme import TITLE
    lg = pixfont.logo(TITLE, 8)
    pixfont.paste(big, lg, (B * 4 - lg.shape[1]) // 2, 34)
    pixfont.draw(big, B * 2, 34 + lg.shape[0] + 10, '32-CAR ANTI-GRAV RACING' if not NEON else ('RACE THE DEEP - 32 CARS' if DEPTH else 'RACE AND FLY - 32 CARS'), 4, ICE, shadow=PURPLE, align='center')
    big = retro.scanlines(big, 4, 0.86)
    os.makedirs(OUTD, exist_ok=True)
    Image.fromarray(big).save(os.path.join(OUTD, 'icon.png'), optimize=True)
    print('icon ->', os.path.join(OUTD, 'icon.png'), '%d KB' % (os.path.getsize(os.path.join(OUTD, 'icon.png')) // 1024))

if __name__ == '__main__':
    main()
