"""IRONFRAME pixel-art loading slides + Workshop icon. Everything is drawn at 480x270 (icon 256x256) in a tight dusk palette and
upscaled x4 nearest-neighbour so CS2's filtering keeps it sharp. Used by tools/map_slides.py (pixel mode, default) and tools/loading.py."""
import os, sys, math, random
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'create'))
import pixfont

LW, LH = 480, 270
# fixed colours (drawn after quantising, so they are always exact)
INK = (14, 10, 24); MECH0 = (24, 17, 40); MECH1 = (44, 31, 66); MECH2 = (70, 50, 96); RIM = (255, 168, 96); RIM2 = (255, 214, 140)
FAR = (92, 58, 100); FAR2 = (122, 76, 112)
WHITE = (240, 236, 255); CYAN = (96, 224, 255); ORANGE = (255, 150, 60); DIM = (150, 140, 190); PANEL = (20, 14, 38); PANEL2 = (52, 40, 86)
FIXED = [INK, MECH0, MECH1, MECH2, RIM, RIM2, FAR, FAR2, WHITE, CYAN, ORANGE, DIM, PANEL, PANEL2]
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], float) / 16.0 - 0.5


def palette_from(bgs, n=24):
    """one shared adaptive palette for all backdrops so the slides feel like one game"""
    big = Image.new('RGB', (LW, LH * len(bgs)))
    for i, b in enumerate(bgs): big.paste(b, (0, i * LH))
    q = big.quantize(colors=n, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = np.array(q.getpalette()[:n * 3], np.uint8).reshape(-1, 3)
    cols = [tuple(int(x) for x in c) for c in pal]
    return cols, cols + [c for c in FIXED if c not in cols]


def quantize(img, cols, dither=22):
    """ordered-dither (Bayer 4x4) to the adaptive palette, nearest colour"""
    a = np.asarray(img.convert('RGB'), float)
    h, w = a.shape[:2]
    t = np.tile(BAYER, (h // 4 + 1, w // 4 + 1))[:h, :w]
    a = np.clip(a + t[..., None] * dither, 0, 255)
    pal = np.array(cols, float)
    d = ((a[:, :, None, :] - pal[None, None, :, :]) ** 2).sum(-1)
    return Image.fromarray(pal[d.argmin(-1)].astype(np.uint8))


# ---------------------------------------------------------------- pixel mech silhouettes
def mech(img, x, gy, h, face=1, col=(MECH0, MECH1, MECH2), rim=RIM, rim2=RIM2, eye=CYAN, pose=0):
    """a bipedal heavy mech standing on (x, gy), h px tall, facing right (face=1) or left (-1); hard-edged polygons, rim-lit"""
    d = ImageDraw.Draw(img); u = h / 120.0
    def P(pts): return [(x + face * px * u, gy + py * u) for px, py in pts]
    def poly(pts, c, dx=0):
        d.polygon([(round(a + dx), round(b)) for a, b in P(pts)], fill=c)
    parts = [   # back to front; shade 0 dark, 1 mid, 2 light
        ([(-24, -2), (-8, -2), (-6, -30), (-16, -52), (-28, -48), (-30, -26)], 0),            # back leg
        ([(-32, 0), (-12, 0), (-12, -6), (-30, -8)], 0),                                      # back foot
        ([(2, -2), (22, -2), (18, -28), (24, -50), (6, -54), (-2, -28)], 1),                  # front leg
        ([(-2, 0), (30, 0), (28, -7), (4, -9)], 1),                                           # front foot
        ([(-18, -50), (20, -50), (22, -60), (-20, -60)], 0),                                  # pelvis
        ([(-24, -60), (26, -60), (32, -84), (18, -96), (-14, -96), (-28, -84)], 1),           # torso
        ([(-10, -96), (14, -96), (12, -108), (-4, -110), (-12, -102)], 2),                    # head
        ([(-46, -100), (-26, -100), (-24, -74), (-46, -76)], 0),                              # rear shoulder pod
        ([(24, -102), (46, -102), (48, -76), (26, -76)], 1),                                  # front shoulder pod
        ([(26, -74), (64, -80 + pose), (68, -72 + pose), (26, -62)], 0),                      # gun arm
        ([(60, -83 + pose), (96, -85 + pose), (96, -79 + pose), (60, -77 + pose)], 0),        # barrel
    ]
    s = max(1, round(h / 90))
    for pts, sh in parts: poly(pts, rim, -face * s)                                           # rim light on the sun side
    for pts, sh in parts: poly(pts, col[sh])
    ex = x + face * 6 * u; ey = round(gy - 103 * u)
    d.rectangle((round(min(ex, ex + face * 7 * u)), ey, round(max(ex, ex + face * 7 * u)), ey + max(0, int(h / 50))), fill=eye)
    if h >= 50:
        for a, b in (((-18, -88), (24, -88)), ((-16, -72), (26, -72))):
            q = P([a, b]); d.line([(round(q[0][0]), round(q[0][1])), (round(q[1][0]), round(q[1][1]))], fill=col[0])
        q = P([(-20, -94), (6, -94)]); d.line([(round(q[0][0]), round(q[0][1])), (round(q[1][0]), round(q[1][1]))], fill=rim2)


def ground_ridge(seed, y0, amp, c, rim, img, w=LW, h=LH):
    r = random.Random(seed); pts = []
    for x in range(0, w + 12, 12):
        pts.append((x, y0 + math.sin(x / 61.0 + seed) * amp + r.uniform(-amp / 3, amp / 3)))
    d = ImageDraw.Draw(img)
    d.polygon([(round(a), round(b)) for a, b in pts + [(w, h), (0, h)]], fill=c)
    d.line([(round(a), round(b)) for a, b in pts], fill=rim)


# ---------------------------------------------------------------- UI pieces
def frame(img, box, fill=PANEL, edge=PANEL2, hi=CYAN):
    d = ImageDraw.Draw(img); x0, y0, x1, y1 = box
    d.rectangle(box, fill=fill, outline=edge)
    d.line((x0, y0, x0 + 6, y0), fill=hi); d.line((x0, y0, x0, y0 + 6), fill=hi)
    d.line((x1, y1, x1 - 6, y1), fill=hi); d.line((x1, y1, x1, y1 - 6), fill=hi)


def txt(img, x, y, s, scale=1, color=WHITE, outline=INK, shadow=None, align='left'):
    a = np.asarray(img).copy()
    pixfont.draw(a, x, y, s, scale, color, outline, shadow, align)
    img.paste(Image.fromarray(a))


def title_block(img, arena, caption, tip, n, total=4):
    X = 66
    txt(img, X + 2, 27, 'IRONFRAME', 3, MECH1, None)
    txt(img, X, 25, 'IRONFRAME', 3, WHITE, INK)
    d = ImageDraw.Draw(img)
    d.rectangle((X, 56, X + 215, 57), fill=ORANGE)
    d.rectangle((X + 120, 58, X + 215, 58), fill=RIM2)
    txt(img, X, 63, arena, 2, CYAN, INK)
    txt(img, X, 84, caption, 1, WHITE, INK)
    bx0, by0, bx1, by1 = 64, 206, 300, 232      # inside x 63..337 (a 4:3 crop keeps it) and y 26..244 (21:9 keeps it)
    frame(img, (bx0, by0, bx1, by1))
    txt(img, bx0 + 6, by0 + 4, tip[0], 1, ORANGE, None)
    txt(img, bx0 + 6, by0 + 14, tip[1], 1, WHITE, None)
    for i in range(total):
        d.rectangle((bx0 + i * 12, by1 + 5, bx0 + i * 12 + 7, by1 + 7), fill=ORANGE if i == n else PANEL2)


def to_1080(img): return img.resize((LW * 4, LH * 4), Image.NEAREST)


TIPS = [
    ('MOUSE1 MOUSE2 R E', 'FIRE ALL FOUR HARDPOINTS'),
    ('SHIFT BOOST  CTRL DODGE', 'SPACE HOVER  WATCH EN'),
    ('F LOCKS NEXT TARGET', 'STAGGER THEM FOR BIG DAMAGE'),
    ('CTRL OR F WHILE DEAD', 'OPEN GARAGE  !HELP FOR MORE'),
]
CAPS = ['HOLD THE CANYON', 'EVERY RIDGE IS COVER', 'BOOST  DODGE  LOCK ON', '64 PILOTS  ONE ARENA']


def build(backdrops, arena='DUNES'):
    """backdrops: 4 RGB 480x270 renders of the map under its sky. Returns 4 images at 1920x1080 (nearest-neighbour x4)."""
    acols, cols = palette_from(backdrops)
    out = []
    fg = [(350, 100, -1), (360, 112, -1), (352, 84, -1), (348, 96, -1)]
    far = [[(210, 150, 22, 1), (250, 152, 16, -1)], [(120, 148, 18, 1), (176, 150, 24, 1), (60, 150, 12, 1)],
           [(300, 150, 20, -1), (360, 150, 14, -1)], [(90, 150, 22, 1), (180, 150, 16, 1), (260, 150, 18, -1)]]
    for i, bg in enumerate(backdrops):
        im = quantize(bg, acols)
        for (x, y, h, f) in far[i]:
            mech(im, x, y, h, f, col=(FAR, FAR, FAR2), rim=FAR2, rim2=FAR2, eye=FAR2)
        ground_ridge(i * 3 + 1, 238, 6, MECH1, MECH2, im)
        x, h, f = fg[i]
        mech(im, x, 252, h, f, pose=(i % 2) * 3)
        ground_ridge(i * 3 + 2, 258, 4, MECH0, MECH1, im)
        title_block(im, arena, CAPS[i], TIPS[i], i)
        out.append(to_1080(im))
    return out


def workshop_icon():
    """1024x1024 pixel icon: drawn at 256x256, x4"""
    s = 256
    im = Image.new('RGB', (s, s)); d = ImageDraw.Draw(im)
    sky = [(18, 12, 44), (44, 24, 84), (96, 40, 110), (172, 70, 110), (240, 120, 90), (255, 190, 110), (255, 226, 160)]
    hz = 170
    for y in range(hz):
        t = y / hz * (len(sky) - 1); k = int(t); f = t - k
        for x in range(0, s, 1):
            c = sky[k] if f + BAYER[y % 4][x % 4] * 0.6 < 0.5 else sky[min(k + 1, len(sky) - 1)]
            d.point((x, y), fill=c)
    rr = random.Random(5)
    for _ in range(40): d.point((rr.randrange(s), rr.randrange(70)), fill=WHITE)
    d.ellipse((150, 118, 190, 158), fill=(255, 226, 160)); d.ellipse((156, 124, 184, 152), fill=(255, 240, 200))
    d.rectangle((0, hz, s, s), fill=(120, 54, 84))
    ground_ridge(7, 176, 5, (96, 40, 78), (170, 80, 100), im, s, s)
    ground_ridge(9, 188, 5, (60, 28, 62), (120, 60, 90), im, s, s)
    mech(im, 92, 232, 150, 1, pose=2)
    mech(im, 196, 190, 34, -1, col=(FAR, FAR, FAR2), rim=FAR2, rim2=FAR2, eye=FAR2)
    ground_ridge(11, 236, 3, MECH0, MECH1, im, s, s)
    txt(im, s // 2 + 1, 15, 'IRONFRAME', 3, MECH1, None, None, 'center')
    txt(im, s // 2, 14, 'IRONFRAME', 3, WHITE, INK, None, 'center')
    ImageDraw.Draw(im).rectangle((s // 2 - 108, 42, s // 2 + 107, 43), fill=ORANGE)
    txt(im, s // 2, 48, 'MECH ARENA COMBAT', 1, CYAN, INK, None, 'center')
    return im.resize((1024, 1024), Image.NEAREST)
