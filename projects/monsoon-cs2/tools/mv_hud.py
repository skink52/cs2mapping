"""mg_monsoon HUD (custom_hud_layout mv_hud): panorama/layout/custom_game/mg_monsoon.xml + styles .css + pictures in
panorama/images/custom_game/mv/, and out/hud.json for the script build.

usage: mv_hud.py [<addon content out>] [--no-art] [--no-check]          default ../out/addon
  --no-art     keep the pictures already there (layout / css work only)
  --no-check   skip the hud_check.py gate (it runs over out/hud_states.json and draws out/hud/hud_<state>.png)

Every panel id, class and swap group is the one in docs/SCRIPT.md "HUD contract" (the table is parsed here and the build
fails on a missing id, a class with no css rule, or an id the contract does not list). Static art has no id.
Layout rules: docs/creation/hud.md (fixed sizes pinned from the top, show / hide by opacity, positions by transform classes,
clear of CS2's own HUD zones). Design notes and the state list: docs/HUD.md.
"""
import os, re, sys, json, math, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import panorama
from panorama import P

NAME = 'mg_monsoon'
IMG = 'file://{images}/custom_game/mv/'
FONT = 'Stratum2, "Stratum2 Bold", Arial'
SLIDES = 3
# ---- numbers shared with the script (docs/SCRIPT.md) and render_board.py
BOARD_EXT, BOARD_STEPS, BOARD_PX = 6400, 160, 640
STEP = BOARD_PX / BOARD_STEPS            # 4 px per reticle step
MK = 64                                  # every board marker is a 64 px square, its art centred
CEP_STEP, CEP_N = 60.0, 9                # cepN radius = (N + 1) * 60 world units
G = 148                                  # gauge size
AI_SCALE, AI_PPD = 2.6, 3.4              # horizon card: drawn 2.6 x the window, 3.4 px per degree of pitch
TAPE_STEP, TAPE_WIN, TAPE_H = 12, 300, 36  # heading tape: px per 5 degrees, window
# ---- palette
INK = (14, 18, 12); OLIVE = (22, 27, 18); KEY = (196, 186, 150); CREAM = (236, 226, 192); AMBER = (240, 176, 84)
GREEN = (132, 214, 150); PHOS = (156, 240, 168); RED = (230, 72, 54); TCOL = (234, 190, 84); CTCOL = (104, 163, 229); GREY = (150, 154, 140)
FEED_GOOD = (150, 226, 140); FEED_BAD = (240, 112, 84)
# ---- box sizes used by both the art and the layout
INFO_W, ST_W, GUN_H = 360, 360, 104
REQ_Y, REQ_H = 480, 50                                      # requisition row: under the status box (336 + 136), clear of the chat (600)
FEED_W, FEED_H, FEED_Y, FEED_DY = 460, 26, 198, 28          # event feed: 3 lines under CS2's kill feed (which ends ~y 190)
OBJ_H = 224                                                 # objective panel: bar 0-72, clock tab 70-94, capture ring 104-220
FLAGS = [('a', 'PADDIES'), ('b', 'BRIDGE'), ('c', 'VILLAGE'), ('d', 'TEMPLE'), ('e', 'CRASH SITE')]
FB = ['C:/Windows/Fonts/bahnschrift.ttf', 'C:/Windows/Fonts/arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf']


def HEXC(c):
    return '#%02x%02x%02x' % tuple(c)


def font(size, weight='Bold'):
    for p in FB:
        if os.path.exists(p):
            f = ImageFont.truetype(p, max(4, int(round(size))))
            try: f.set_variation_by_name(weight)
            except Exception: pass
            return f
    return ImageFont.load_default()


# ================================================================ drawing helpers (everything drawn 3x and scaled down)
SS = 3


class Art:
    """a w x h picture (display px) drawn at k x SS and saved at k x (k = 2: crisp when Panorama scales to 1440p / 4K)"""

    def __init__(self, w, h, k=2):
        self.w, self.h, self.k = w, h, k
        self.s = k * SS
        self.im = Image.new('RGBA', (int(w * self.s), int(h * self.s)), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def S(self, *v):
        return [x * self.s for x in v]

    def _w(self, kw):
        if 'width' in kw: kw['width'] = max(1, int(round(kw['width'] * self.s)))
        return kw

    def rect(self, x0, y0, x1, y1, r=0, **kw):
        kw = self._w(kw)
        if r: self.d.rounded_rectangle(self.S(x0, y0, x1, y1), r * self.s, **kw)
        else: self.d.rectangle(self.S(x0, y0, x1, y1), **kw)

    def line(self, pts, fill, width=1):
        self.d.line([(x * self.s, y * self.s) for x, y in pts], fill=fill, width=max(1, int(round(width * self.s))), joint='curve')

    def poly(self, pts, **kw):
        self.d.polygon([(x * self.s, y * self.s) for x, y in pts], **self._w(kw))

    def circ(self, cx, cy, r, **kw):
        self.d.ellipse(self.S(cx - r, cy - r, cx + r, cy + r), **self._w(kw))

    def arc(self, cx, cy, r, a0, a1, fill, width):
        """a0, a1 in degrees clockwise from the top"""
        self.d.arc(self.S(cx - r, cy - r, cx + r, cy + r), a0 - 90, a1 - 90, fill=fill, width=max(1, int(round(width * self.s))))

    def text(self, x, y, s, size, fill, anchor='ls', track=0.0, weight='Bold', shadow=False):
        f = font(size * self.s, weight)
        ws = [f.getlength(c) for c in s]; sp = size * self.s * track
        W = sum(ws) + sp * (len(s) - 1)
        x0 = x * self.s - (W / 2 if anchor[0] == 'm' else W if anchor[0] == 'r' else 0)
        for c, w in zip(s, ws):
            if shadow: self.d.text((x0 + self.s, y * self.s + self.s), c, font=f, fill=(0, 0, 0, 200), anchor='l' + anchor[1])
            self.d.text((x0, y * self.s), c, font=f, fill=fill, anchor='l' + anchor[1]); x0 += w + sp
        return W / self.s

    def glow(self, radius=2.0, strength=0.8, color=None):
        """adds a soft halo of what is drawn so far (phosphor / lamp bloom)"""
        b = self.im.filter(ImageFilter.GaussianBlur(radius * self.s))
        if color is not None:
            al = b.getchannel('A'); b = Image.new('RGBA', b.size, tuple(color) + (0,)); b.putalpha(al)
        b.putalpha(b.getchannel('A').point(lambda v: int(min(255, v * strength))))
        self.im = Image.alpha_composite(b, self.im); self.d = ImageDraw.Draw(self.im)

    def paste(self, other):
        self.im = Image.alpha_composite(self.im, other.im); self.d = ImageDraw.Draw(self.im)

    def out(self):
        return self.im.resize((int(self.w * self.k), int(self.h * self.k)), Image.LANCZOS)

    def save(self, d, name):
        self.out().save(os.path.join(d, name + '.png'), optimize=True)


def noise_img(w, h, seed, blur=0.0, amp=1.0):
    n = np.random.RandomState(seed).rand(h, w).astype(np.float32)
    im = Image.fromarray((n * 255).astype(np.uint8))
    if blur: im = im.filter(ImageFilter.GaussianBlur(blur))
    return (np.asarray(im, np.float32) / 255.0 - 0.5) * amp


def lerp3(c0, c1, t):
    return tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))


def plate(w, h, head=0, title=None, accent=KEY, alpha=222, sub=None, tick=True, seed=1):
    """the HUD's panel: dark olive glass, a fine keyline, corner ticks, an optional header band with a stencil title"""
    a = Art(w, h)
    a.rect(0, 0, w, h, 5, fill=OLIVE + (alpha,))
    if head:
        hc = (10, 13, 9, min(255, alpha + 20))
        a.rect(0, 0, w, head, 5, fill=hc); a.rect(0, head - 6, w, head, fill=hc)
        a.line([(0, head), (w, head)], accent + (150,), 1)
        a.rect(10, head / 2 - 5, 14, head / 2 + 5, fill=accent + (255,))
        if title: a.text(22, head / 2 + 0.5, title, min(16, head * 0.5), accent + (255,), 'lm', 0.16)
        if sub: a.text(w - 12, head / 2 + 0.5, sub, min(12, head * 0.36), GREY + (230,), 'rm', 0.12, 'Regular')
    a.rect(3, 3, w - 3, h - 3, 3, outline=KEY + (70,), width=1)
    if tick:
        for (cx, cy, sx, sy) in ((0, 0, 1, 1), (w, 0, -1, 1), (0, h, 1, -1), (w, h, -1, -1)):
            a.line([(cx + sx * 3, cy + sy * 16), (cx + sx * 3, cy + sy * 3), (cx + sx * 16, cy + sy * 3)], accent + (255,), 1.6)
    im = np.asarray(a.im, np.float32)                       # glass grain + a faint top light
    n = noise_img(im.shape[1], im.shape[0], seed, 0.6, 14.0)
    yy = np.linspace(1, 0, im.shape[0])[:, None]
    im[..., :3] = np.clip(im[..., :3] + n[..., None] + 10 * yy[..., None] ** 3, 0, 255)
    a.im = Image.fromarray(im.astype(np.uint8)); a.d = ImageDraw.Draw(a.im)
    return a


def seg_track(a, x, y, n, sw, sh, gap=2, col=(0, 0, 0, 150), edge=KEY + (90,)):
    for i in range(n):
        a.rect(x + i * sw, y, x + i * sw + sw - gap, y + sh, fill=col, outline=edge, width=0.6)


def seg_fill(n, sw, sh, cols, gap=2):
    """n lit segments; cols(i) -> colour"""
    a = Art(n * sw, sh)
    for i in range(n):
        c = cols(i)
        a.rect(i * sw, 0, i * sw + sw - gap, sh, fill=tuple(c) + (255,))
        a.rect(i * sw, 0, i * sw + sw - gap, sh * 0.4, fill=tuple(min(255, int(v * 1.25 + 20)) for v in c) + (255,))
    return a


def frames(D, art, name, steps, from_right=False):
    """one picture per bar step (`<name>_<k>`, k = 0..steps): the full bar `art` cut to k / steps of its width, from the left
    (or the right). Bars switch pictures instead of sliding a fill inside a clipping track: nothing hangs out of its box,
    no reliance on overflow clip, and hud_check.py draws exactly what Panorama will."""
    full = art.out(); W, H = full.size
    for k in range(steps + 1):
        f = Image.new('RGBA', (W, H), (0, 0, 0, 0)); w = int(round(W * k / float(steps)))
        if w:
            box = (W - w, 0, W, H) if from_right else (0, 0, w, H)
            f.paste(full.crop(box), box[:2])
        f.save(os.path.join(D, '%s_%d.png' % (name, k)), optimize=True)


def put(a, other, x, y):
    """composite Art `other` into Art `a` with its top left at (x, y) display px"""
    a.im.alpha_composite(other.im, (int(round(x * a.s)), int(round(y * a.s)))); a.d = ImageDraw.Draw(a.im)


# ---- geometry shared by the art and the layout
GX = [44, 204, 364, 524]; GY = 44                 # gauges on the dash: ASI, horizon, ALT, VSI
HPX, RTBX, RKX = 200, 440, 532                    # top strip of the dash
BW, BH = 900, 772                                 # board panel
MX, MY = 12, 52                                   # map inside the board panel
SX = MX + BOARD_PX + 12                           # side column x (224 wide)
FY = MY + BOARD_PX + 12                           # footer y
LAMPS = [('idle', 'STANDBY', (170, 174, 150), 0, 0), ('laying', 'LAYING', AMBER, 116, 0), ('laid', 'LAID', (120, 226, 140), 0, 40),
         ('disabled', 'DISABLED', RED, 116, 40)]


# ================================================================ pictures
def art_common(D):
    a = plate(640, 372, 40, 'BRIEFING', AMBER, sub='MG_MONSOON  /  SONG MUA VALLEY')
    a.rect(20, 252, 620, 296, 3, fill=(0, 0, 0, 110), outline=AMBER + (150,), width=1)
    a.line([(20, 316), (620, 316)], KEY + (60,), 1)
    a.save(D, 'pl_brief')
    plate(INFO_W, 330, 44, None, GREEN).save(D, 'pl_info')
    a = Art(640, 100)
    a.rect(0, 0, 640, 100, 0, fill=(8, 10, 7, 170))
    im = np.asarray(a.im, np.float32).copy(); xx = np.linspace(-1, 1, im.shape[1])[None, :]
    im[..., 3] *= np.clip(1.25 - xx ** 2 * 1.25, 0, 1)                      # fades out to both sides
    a.im = Image.fromarray(im.astype(np.uint8)); a.d = ImageDraw.Draw(a.im)
    a.line([(120, 4), (520, 4)], AMBER + (230,), 1.6); a.line([(120, 96), (520, 96)], AMBER + (230,), 1.6)
    for x in (120, 520):
        for y in (4, 96): a.poly([(x, y - 4), (x + 5, y), (x, y + 4), (x - 5, y)], fill=AMBER + (255,))
    a.save(D, 'pl_banner')
    plate(560, 52, 0, None, AMBER, 200).save(D, 'pl_toast')
    plate(480, 46, 0, None, KEY, 190).save(D, 'pl_prompt')
    a = plate(ST_W, 136, 0, None, AMBER, 205)
    a.rect(0, 0, 5, 136, 0, fill=AMBER + (255,)); a.line([(18, 42), (ST_W - 18, 42)], KEY + (70,), 1)
    a.save(D, 'pl_status')
    a = plate(320, 42, 0, None, AMBER, 200, tick=False)
    a.rect(30, 27, 290, 35, 0, fill=(0, 0, 0, 170), outline=KEY + (110,), width=0.6)
    a.save(D, 'pl_hold')
    # requisition row (batch G): a slim plate under the status box, a supply-crate stencil, and a green edge when an upgrade is ready
    a = plate(ST_W, REQ_H, 0, None, GREEN, 200, tick=False)
    a.rect(0, 0, 5, REQ_H, 0, fill=GREEN + (255,))
    cx, cy = 30, REQ_H / 2                                   # crate stencil: box, lid line, two slats
    a.rect(cx - 12, cy - 9, cx + 12, cy + 10, 2, outline=KEY + (230,), width=1.6)
    a.line([(cx - 12, cy - 3), (cx + 12, cy - 3)], KEY + (230,), 1.4)
    a.line([(cx - 4, cy - 3), (cx - 4, cy + 10)], KEY + (160,), 1); a.line([(cx + 4, cy - 3), (cx + 4, cy + 10)], KEY + (160,), 1)
    a.save(D, 'pl_req')
    a = Art(ST_W, REQ_H)
    a.rect(1, 1, ST_W - 1, REQ_H - 1, 4, outline=GREEN + (255,), width=2)
    a.rect(0, 0, 5, REQ_H, 0, fill=(200, 255, 200, 255))
    a.glow(3.0, 0.9, GREEN)
    a.save(D, 'req_ready')
    f = Art(260, 8)
    f.rect(0, 0, 260, 8, fill=AMBER + (255,)); f.rect(0, 0, 260, 3, fill=(255, 214, 140, 255))
    for i in range(1, 20): f.rect(i * 13 - 0.5, 0, i * 13 + 0.5, 8, fill=(40, 30, 10, 255))
    frames(D, f, 'hold', 20)
    a = plate(300, GUN_H, 0, None, AMBER, 210)                # name, belt read-out, rule, heat meter
    a.line([(18, 64), (282, 64)], KEY + (60,), 1)
    a.text(18, 79.5, 'HEAT', 11, GREY + (255,), 'lm', 0.2)
    seg_track(a, 64, 72, 10, 22, 14)
    a.text(64, 96, 'COOL', 8.5, GREEN + (200,), 'lm', 0.2, 'Regular'); a.text(282, 96, 'LOCKOUT', 8.5, RED + (220,), 'rm', 0.2, 'Regular')
    a.save(D, 'pl_gun')
    frames(D, seg_fill(10, 22, 14, lambda i: lerp3((240, 200, 90), (236, 60, 40), (i - 3) / 6.0) if i > 3 else lerp3((132, 214, 150), (240, 200, 90), i / 3.0)), 'heat', 10)
    a = Art(300, GUN_H)
    a.rect(0, 0, 300, GUN_H, 5, fill=(120, 14, 8, 70), outline=RED + (255,), width=2)
    a.rect(176, 38, 288, 60, 3, fill=RED + (240,)); a.text(232, 49.5, 'OVERHEAT', 13, (20, 6, 4, 255), 'mm', 0.12)
    a.save(D, 'gun_hot')
    for tone, col in (('n', KEY), ('good', FEED_GOOD), ('bad', FEED_BAD)):   # event feed line: a dark band fading out to the left
        a = Art(FEED_W, FEED_H)
        im = np.zeros((int(FEED_H * a.s), int(FEED_W * a.s), 4), np.float32)
        xx = np.linspace(0, 1, im.shape[1])[None, :]
        im[..., 0:3] = (8, 10, 7); im[..., 3] = np.clip(xx / 0.5, 0, 1) ** 1.3 * 190
        a.im = Image.fromarray(im.astype(np.uint8), 'RGBA'); a.d = ImageDraw.Draw(a.im)
        a.rect(FEED_W - 4, 3, FEED_W, FEED_H - 3, 0, fill=col + (255,))
        a.save(D, 'feed_' + tone)


def art_objective(D):
    a = Art(560, 96)
    put(a, plate(96, 26, 0, None, KEY, 214, tick=False, seed=3), 232, 68)     # the clock's tab under the bar, clear of the badges
    put(a, plate(560, 72, 0, None, KEY, 214), 0, 0)
    a.rect(236, 70, 324, 72, 0, fill=OLIVE + (214,))                         # tab and bar read as one piece
    for x0, col in ((14, TCOL), (426, CTCOL)):
        a.rect(x0, 50, x0 + 120, 58, 0, fill=(0, 0, 0, 170), outline=col + (130,), width=0.6)
    a.text(134, 34, 'PAVN', 11, TCOL + (255,), 'rs', 0.18); a.text(426, 34, 'US', 11, CTCOL + (255,), 'ls', 0.18)
    a.save(D, 'pl_obj')
    for nm, col in (('t', TCOL), ('ct', CTCOL)):              # ticket bars drain towards the flags
        f = Art(120, 8)
        for i in range(20): f.rect(i * 6, 0, i * 6 + 5.2, 8, fill=col + (255,)); f.rect(i * 6, 0, i * 6 + 5.2, 3, fill=lerp3(col, (255, 255, 255), 0.35) + (255,))
        frames(D, f, 'tk_' + nm, 20, from_right=(nm == 'ct'))
    for nm, col in (('n', (128, 132, 120)), ('t', TCOL), ('ct', CTCOL)):
        b = Art(48, 48)
        b.circ(24, 24, 22.5, fill=(10, 13, 9, 235), outline=col + (255,), width=3.4 if nm != 'n' else 2)
        if nm != 'n': b.circ(24, 24, 18.5, fill=lerp3(col, (0, 0, 0), 0.62) + (255,))
        b.save(D, 'flag_' + nm)
        if nm == 'n': continue
        for k in range(11):                                   # capture fill: the badge filling up from the bottom, one picture per step
            c = Art(40, 40)
            if k:
                lvl = 38.5 - 37.0 * k / 10.0
                m = Art(40, 40); m.circ(20, 20, 18.5, fill=(255, 255, 255, 255))
                c.rect(0, lvl, 40, 40, fill=lerp3(col, (255, 255, 255), 0.10) + (215,))
                c.rect(0, lvl, 40, lvl + 1.4, fill=lerp3(col, (255, 255, 255), 0.55) + (255,))
                c.im.putalpha(ImageChops.multiply(c.im.getchannel('A'), m.im.getchannel('A'))); c.d = ImageDraw.Draw(c.im)
            c.save(D, 'flagcap_%s_%d' % (nm, k))
    for l, name in FLAGS:
        b = Art(48, 48); b.text(24, 25, l.upper(), 26, CREAM + (255,), 'mm', shadow=True); b.save(D, 'flag_l_' + l)
        c = Art(160, 24)
        c.rect(0, 0, 160, 24, 3, fill=(8, 10, 7, 215)); c.text(80, 12.5, name, 13, CREAM + (255,), 'mm', 0.18)
        c.save(D, 'cap_name_' + l)
        k = Art(84, 84); k.circ(42, 42, 27, fill=(8, 10, 7, 225)); k.text(42, 43.5, l.upper(), 38, CREAM + (255,), 'mm'); k.save(D, 'cap_core_' + l)
    w = Art(48, 48)
    for k in range(12): w.arc(24, 24, 23, k * 30, k * 30 + 15, RED + (255,), 3.2)
    w.glow(1.5, 0.9); w.save(D, 'flag_warn')
    hh = Art(48, 62)
    hh.poly([(24, 51), (31, 61), (17, 61)], fill=CREAM + (255,)); hh.glow(1.5, 0.7); hh.save(D, 'flag_here')
    for nm, col in (('n', None), ('t', TCOL), ('ct', CTCOL)):       # capture ring: 10 steps clockwise from the top
        for k in range(11):
            if nm == 'n' and k: break
            if nm != 'n' and k == 0: continue
            r = Art(84, 84)
            r.circ(42, 42, 40, fill=(8, 10, 7, 120))
            r.arc(42, 42, 38, 0, 360, (0, 0, 0, 190), 9)
            for t in range(10): r.arc(42, 42, 38, t * 36 - 0.6, t * 36 + 0.6, KEY + (120,), 9)
            if col:
                g = Art(84, 84); g.arc(42, 42, 37.5, 0, k * 36, col + (255,), 7); g.glow(2.0, 0.8); r.paste(g)
            r.save(D, 'ring_n' if nm == 'n' else 'ring_%s_%d' % (nm, k))
    c = Art(160, 24)
    c.rect(0, 0, 160, 24, 3, fill=RED + (240,)); c.text(80, 12.5, 'CONTESTED', 13, (24, 8, 6, 255), 'mm', 0.2)
    c.save(D, 'cap_contest')


def dial_face(kind):
    a = Art(G, G)
    c = G / 2.0; R = G * 0.445
    n = int(G * a.s)
    yy, xx = np.mgrid[0:n, 0:n] / float(n)
    r = np.hypot(xx - 0.5, yy - 0.5) * 2
    lum = np.clip(1.0 - 0.75 * np.hypot(xx - 0.36, yy - 0.30), 0.2, 1.0)      # deep green-black glass, lighter upper left
    rgb = np.stack([10 + 12 * lum, 17 + 26 * lum, 13 + 17 * lum], -1) + noise_img(n, n, 5, 0.5, 5.0)[..., None]
    al = np.clip((0.985 - r) * n / 3.0, 0, 1) * 255
    a.im = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), al]).astype(np.uint8), 'RGBA'); a.d = ImageDraw.Draw(a.im)
    m = Art(G, G)                                           # the phosphor markings (they get the glow)
    pt = lambda ang, rad: (c + rad * math.sin(math.radians(ang)), c - rad * math.cos(math.radians(ang)))

    def tick(ang, l, w, col=PHOS): m.line([pt(ang, R - l), pt(ang, R)], col + (255,), w)

    def num(ang, s_, rad=R - 21, size=13, col=PHOS): m.text(*pt(ang, rad), s_, size, col + (255,), 'mm')
    unit = None
    if kind == 'asi':                                       # 0..100 km/h over 300 degrees clockwise from the top
        m.arc(c, c, R - 1.5, 0, 240, GREEN + (150,), 2.2); m.arc(c, c, R - 1.5, 240, 270, AMBER + (255,), 2.6); m.arc(c, c, R - 1.5, 270, 300, RED + (255,), 2.6)
        for v in range(0, 101, 5): tick(v * 3.0, 11 if v % 10 == 0 else 6, 1.8 if v % 10 == 0 else 1.0)
        for v in range(0, 101, 20): num(v * 3.0, str(v))
        m.text(c, c + 19, 'AIRSPEED', 7.5, PHOS + (210,), 'mm', 0.16); unit = 'KM/H'
    elif kind == 'alt':                                     # one turn = 100 m
        for v in range(0, 100, 2): tick(v * 3.6, 11 if v % 10 == 0 else 5, 1.8 if v % 10 == 0 else 1.0)
        for v in range(10): num(v * 36.0, str(v), size=14)
        m.text(c, c + 19, 'RADAR ALT', 7.5, PHOS + (210,), 'mm', 0.16); unit = 'x 10 M'
    else:                                                   # zero at 9 o'clock, +-10 m/s = +-135 degrees
        for v in range(-10, 11): tick(270 + v * 13.5, 11 if v % 5 == 0 else 6, 1.8 if v % 5 == 0 else 1.0)
        for v, s_ in ((0, '0'), (5, '5'), (-5, '5'), (10, '10'), (-10, '10')): num(270 + v * 13.5, s_)
        m.arc(c, c, R - 1.5, 135, 202.5, RED + (230,), 2.6)                       # sinking faster than 5 m/s
        m.text(c - 4, c - 27, 'UP', 8, PHOS + (230,), 'mm', 0.1); m.text(c - 4, c + 28, 'DN', 8, PHOS + (230,), 'mm', 0.1)
        m.text(c + 30, c - 6, 'VERT', 7.5, PHOS + (210,), 'mm', 0.16); m.text(c + 30, c + 5, 'M / S', 7, PHOS + (180,), 'mm', 0.1, 'Regular')
    if unit:                                                # the digital window under the hub
        m.rect(c - 25, c - 35, c + 25, c - 14, 2, fill=(2, 5, 3, 255), outline=PHOS + (150,), width=0.8)
        m.text(c, c + 29, unit, 6.5, PHOS + (190,), 'mm', 0.16, 'Regular')
    m.glow(1.6, 0.55, PHOS)
    a.paste(m)
    return a


def bezel(ai=False):
    """the ring round a gauge: black anodised metal with a worn lip, four screws, inner shadow and the glass glint"""
    a = Art(G, G); n = int(G * a.s)
    yy, xx = np.mgrid[0:n, 0:n] / float(n)
    dx, dy = xx - 0.5, yy - 0.5
    r = np.hypot(dx, dy) * 2; ang = np.arctan2(dy, dx)
    inner = 0.84 if ai else 0.915
    lum = 0.5 + 0.5 * np.cos(ang + 2.4)                     # lit from the upper left
    ring = np.clip((r - inner) * n / 4.0, 0, 1) * np.clip((1.0 - r) * n / 3.0, 0, 1)
    prof = np.clip((r - inner) / (1 - inner), 0, 1)
    shade = 24 + 64 * lum * np.sin(prof * np.pi) ** 0.7
    rgb = np.stack([shade * 0.95, shade, shade * 0.86], -1) + noise_img(n, n, 8, 0.7, 7.0)[..., None]
    lip = np.clip(1 - np.abs(r - inner) * n / 5.0, 0, 1)
    rgb = rgb + lip[..., None] * (lum[..., None] * 100 - 30)
    inside = r < inner
    sh = np.clip((r - (inner - 0.18)) / 0.18, 0, 1) ** 2 * 150            # shadow the bezel throws on the glass
    gl = np.clip(1 - np.hypot(xx - 0.34, yy - 0.27) / 0.24, 0, 1) ** 2 * 40 + \
        np.clip(1 - np.abs(r - (inner - 0.07)) / 0.03, 0, 1) * np.clip(np.cos(ang - 0.9), 0, 1) ** 3 * 30
    lit = gl > 1
    rgb_in = np.where(lit[..., None], np.array([200.0, 240.0, 210.0]), 0.0)
    al_in = np.where(lit, gl, sh)
    out_rgb = np.where(inside[..., None], rgb_in, rgb); out_a = np.where(inside, al_in, ring * 255)
    a.im = Image.fromarray(np.dstack([np.clip(out_rgb, 0, 255), np.clip(out_a, 0, 255)]).astype(np.uint8), 'RGBA'); a.d = ImageDraw.Draw(a.im)
    c = G / 2.0
    if not ai:
        for q in (45, 135, 225, 315):
            x, y = c + math.cos(math.radians(q)) * G * 0.478, c + math.sin(math.radians(q)) * G * 0.478
            a.circ(x, y, 2.6, fill=(60, 64, 52, 255), outline=(8, 9, 7, 255), width=0.6); a.line([(x - 1.8, y - 0.9), (x + 1.8, y + 0.9)], (10, 11, 9, 255), 0.7)
    else:
        R = G * 0.5 * inner
        pt = lambda an, rad: (c + rad * math.sin(math.radians(an)), c - rad * math.cos(math.radians(an)))
        for an in (-60, -45, -30, -20, -10, 10, 20, 30, 45, 60):
            a.line([pt(an, R + 1.5), pt(an, R + (9 if an % 30 == 0 else 6))], CREAM + (255,), 1.6 if an % 30 == 0 else 1.0)
        a.poly([pt(0, R + 1.5), pt(-4.5, R + 10), pt(4.5, R + 10)], fill=CREAM + (255,))
        sh_ = Art(G, G); o = Art(G, G)                       # the fixed aircraft symbol
        for sx in (-1, 1):
            sh_.line([(c + sx * 40, c + 1.5), (c + sx * 14, c + 1.5), (c + sx * 8, c + 8.5)], (0, 0, 0, 170), 3.8)
            o.line([(c + sx * 40, c), (c + sx * 14, c), (c + sx * 8, c + 7)], AMBER + (255,), 3)
        o.circ(c, c, 2.6, fill=AMBER + (255,))
        a.paste(sh_); a.paste(o)
    return a


def needle(left=False):
    a = Art(G, G); c = G / 2.0
    sh = Art(G, G); sh.poly([(c + 1.5, c - G * 0.40 + 2), (c + 4.3, c + 2), (c + 1.5, c + G * 0.10 + 2), (c - 1.3, c + 2)], fill=(0, 0, 0, 150))
    sh.im = sh.im.filter(ImageFilter.GaussianBlur(1.2 * sh.s)); a.paste(sh)
    a.poly([(c, c - G * 0.40), (c + 2.6, c - 6), (c + 2.6, c + G * 0.10), (c - 2.6, c + G * 0.10), (c - 2.6, c - 6)], fill=(238, 240, 230, 255))
    a.poly([(c, c - G * 0.40), (c + 2.0, c - G * 0.27), (c - 2.0, c - G * 0.27)], fill=AMBER + (255,))
    a.rect(c - 2.6, c + G * 0.05, c + 2.6, c + G * 0.10, fill=(30, 32, 28, 255))
    a.circ(c, c, 7, fill=(22, 24, 20, 255), outline=(90, 94, 80, 255), width=1); a.circ(c - 1.5, c - 1.5, 2, fill=(120, 124, 108, 255))
    if left: a.im = a.im.rotate(90, resample=Image.BICUBIC); a.d = ImageDraw.Draw(a.im)      # the VSI's zero is at 9 o'clock
    return a


AI_R = G * 0.5 * 0.84 + 1.5                                 # radius of the horizon disc (just under the bezel's lip)


def ai_disc(shift):
    """the horizon ball as seen through the window, horizon `shift` px below the centre (positive = nose up): a round picture,
    transparent outside the disc, so the roll rotation never shows a corner. One picture per pitch step (ai_0..ai_20)."""
    a = Art(G, G, k=3); n = int(G * a.s); c = G / 2.0; s = a.s
    yy, xx = np.mgrid[0:n, 0:n] / float(s)
    dy = yy - (c + shift)                                   # px below the horizon line
    t_sky = np.clip(-dy / 70.0, 0, 1); t_gnd = np.clip(dy / 70.0, 0, 1)
    sky = np.array([88, 150, 168]) * (1 - t_sky[..., None]) + np.array([30, 74, 98]) * t_sky[..., None]       # paler at the horizon
    gnd = np.array([122, 88, 50]) * (1 - t_gnd[..., None]) + np.array([62, 44, 26]) * t_gnd[..., None]
    rgb = np.where((dy < 0)[..., None], sky, gnd)
    rr = np.hypot(xx - c, yy - c)
    al = np.clip((AI_R - rr) * s / 1.5, 0, 1) * 255
    a.im = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), al]).astype(np.uint8), 'RGBA'); a.d = ImageDraw.Draw(a.im)
    m = Art(G, G, k=3); W_ = (248, 246, 232, 255)
    m.line([(0, c + shift), (G, c + shift)], W_, 1.6)
    for deg in range(-40, 41, 5):
        if deg == 0: continue
        y = c + shift - deg * AI_PPD
        if y < 4 or y > G - 4: continue
        w = 20 if deg % 10 == 0 else 9
        m.line([(c - w, y), (c + w, y)], W_, 1.3 if deg % 10 == 0 else 1.0)
        if deg % 10 == 0:
            for sx in (-1, 1): m.text(c + sx * (w + 8), y + 0.4, str(abs(deg)), 8, W_, 'mm')
    sh =Art(G, G, k=3); sh.im = m.im.filter(ImageFilter.GaussianBlur(0.8 * m.s)); sh.im.putalpha(sh.im.getchannel('A').point(lambda v: int(v * 0.6)))
    sh.im = Image.merge('RGBA', [Image.new('L', sh.im.size, 0)] * 3 + [sh.im.getchannel('A')])
    a.paste(sh); a.paste(m)
    a.im.putalpha(ImageChops.multiply(a.im.getchannel('A'), Image.fromarray(al.astype(np.uint8))))
    return a


def gauge_blank():
    """the cover plate in a gauge well for seats that do not get that instrument (gunner, rider)"""
    a = Art(G, G); c = G / 2.0
    a.circ(c, c, G * 0.47, fill=(46, 51, 36, 255), outline=(16, 18, 13, 255), width=2.2)
    a.circ(c, c, G * 0.47 - 3, outline=(96, 102, 76, 160), width=0.8)
    for q in (45, 135, 225, 315):
        x, y = c + math.cos(math.radians(q)) * G * 0.36, c + math.sin(math.radians(q)) * G * 0.36
        a.circ(x, y, 3.2, fill=(66, 70, 54, 255), outline=(12, 13, 10, 255), width=0.7); a.line([(x - 2.2, y - 1), (x + 2.2, y + 1)], (14, 15, 11, 255), 0.8)
    a.text(c, c + 1, 'NOT FITTED', 9, (150, 152, 120, 190), 'mm', 0.2)
    return a


def ai_pointer():
    a = Art(G, G); c = G / 2.0; R = G * 0.5 * 0.84
    a.poly([(c, c - R + 1), (c - 4.5, c - R + 11), (c + 4.5, c - R + 11)], fill=AMBER + (255,), outline=(20, 14, 6, 255), width=0.6)
    return a


def art_fly(D):
    for k in ('asi', 'alt', 'vsi'): dial_face(k).save(D, 'g_' + k)
    bezel().save(D, 'g_bezel')
    needle().save(D, 'g_needle'); needle(True).save(D, 'g_needle_vsi')
    for k in range(21): ai_disc((k - 10) * 2 * AI_PPD).save(D, 'ai_%d' % k)
    ai_pointer().save(D, 'ai_ptr'); gauge_blank().save(D, 'g_blank')
    for old in ('ai_card.png', 'tape.png', 'hp_fill.png', 'hold_fill.png', 'heat_fill.png', 'tk_t.png', 'tk_ct.png', 'flagcap_n.png', 'flagcap_t.png', 'flagcap_ct.png'):
        if os.path.exists(os.path.join(D, old)): os.remove(os.path.join(D, old))      # pass 1 pictures the frames replace
    W, H = 716, 200                                          # the dash: olive-drab panel, gauge wells, a top strip
    a = Art(W, H)
    a.poly([(18, 0), (W - 18, 0), (W, 22), (W, H), (0, H), (0, 22)], fill=(52, 58, 40, 246))
    im = np.asarray(a.im, np.float32).copy()
    n = noise_img(im.shape[1], im.shape[0], 21, 0.8, 16.0) + noise_img(im.shape[1], im.shape[0], 22, 6.0, 30.0)
    yy = np.linspace(0, 1, im.shape[0])[:, None]
    im[..., :3] = np.clip(im[..., :3] * (1.08 - 0.34 * yy[..., None]) + n[..., None], 0, 255)
    a.im = Image.fromarray(im.astype(np.uint8)); a.d = ImageDraw.Draw(a.im)
    a.line([(18, 1), (W - 18, 1)], (150, 156, 120, 200), 1.2); a.line([(18, 0), (0, 22)], (120, 126, 96, 200), 1.2); a.line([(W - 18, 0), (W, 22)], (20, 22, 16, 220), 1.2)
    for x in GX:
        a.circ(x + G / 2, GY + G / 2, G / 2 + 3, fill=(14, 16, 12, 255), outline=(96, 102, 78, 255), width=1)
    for x in (10, W - 10):
        for y in (34, 110, 188): a.circ(x, y, 2.6, fill=(34, 38, 28, 255), outline=(110, 116, 90, 255), width=0.6)
    a.text(HPX - 10, 23, 'AIRFRAME', 10, CREAM + (235,), 'rm', 0.16)
    a.rect(HPX - 4, 13, HPX + 220 + 2, 33, 2, fill=(8, 10, 7, 255), outline=(110, 116, 90, 255), width=0.8)
    seg_track(a, HPX, 16, 20, 11, 14, col=(22, 26, 18, 255), edge=(60, 66, 50, 255))
    a.rect(RTBX, 10, RTBX + 64, 36, 3, fill=(40, 10, 8, 255), outline=(110, 116, 90, 255), width=0.8); a.text(RTBX + 32, 23.5, 'RTB', 14, (110, 34, 26, 255), 'mm', 0.2)
    a.rect(RKX, 10, RKX + 140, 36, 3, fill=(4, 8, 5, 255), outline=(110, 116, 90, 255), width=0.8)
    a.save(D, 'dash')
    # the horizon's window is a square (Panorama clips to rectangles): the bezel picture carries the dash's own pixels
    # outside the ring, so the card's corners never show
    bz = bezel(True).out(); dz = a.out().crop((GX[1] * 2, GY * 2, (GX[1] + G) * 2, (GY + G) * 2))
    n_ = G * 2; yy_, xx_ = np.mgrid[0:n_, 0:n_]; rr_ = np.hypot(xx_ - n_ / 2 + 0.5, yy_ - n_ / 2 + 0.5) / (n_ / 2)
    dz.putalpha(Image.fromarray((np.clip((rr_ - 0.93) * 40, 0, 1) * 255).astype(np.uint8)))
    Image.alpha_composite(dz, bz).save(os.path.join(D, 'g_bezel_ai.png'), optimize=True)
    l = Art(64, 26)
    l.rect(0, 0, 64, 26, 3, fill=(236, 60, 40, 255)); l.rect(1, 1, 63, 10, 3, fill=(255, 130, 100, 255)); l.text(32, 13.5, 'RTB', 14, (40, 6, 4, 255), 'mm', 0.2)
    l.save(D, 'rtb_on')
    frames(D, seg_fill(20, 11, 14, lambda i: (226, 62, 44) if i < 7 else ((240, 190, 80) if i < 10 else (132, 214, 150))), 'hp', 20)
    TW = 72 * TAPE_STEP + TAPE_WIN                           # heading 0 sits at TAPE_WIN / 2 when the tape is not shifted
    t = Art(TW, TAPE_H)
    t.rect(0, 0, TW, TAPE_H, fill=(6, 12, 8, 235))
    names = {0: 'N', 90: 'E', 180: 'S', 270: 'W'}
    for deg in range(-90, 451, 5):
        x = TAPE_WIN / 2 + deg / 5.0 * TAPE_STEP
        if x < -10 or x > TW + 10: continue
        dd = deg % 360
        t.line([(x, TAPE_H - (11 if dd % 30 == 0 else (8 if dd % 10 == 0 else 5))), (x, TAPE_H)], PHOS + (255,), 1.6 if dd % 30 == 0 else 1.0)
        if dd % 30 == 0: t.text(x, 12.5, names.get(dd, '%02d' % (dd // 10)), 15 if dd in names else 13, (AMBER if dd in names else PHOS) + (255,), 'mm', 0.04)
    t.glow(1.4, 0.45, PHOS)
    full = t.out(); k_ = t.k                                 # one window-sized picture per heading step (tape_0..tape_71)
    for h_ in range(72):
        x0 = int(round(h_ * TAPE_STEP * k_))
        full.crop((x0, 0, x0 + TAPE_WIN * k_, TAPE_H * k_)).save(os.path.join(D, 'tape_%d.png' % h_), optimize=True)
    FW = TAPE_WIN + 24
    fr = Art(FW, 86); cx = FW / 2.0
    for i in range(34):                                      # glass fade at both ends of the window
        al = int(215 * (1 - i / 34.0) ** 1.5)
        fr.rect(12 + i, 12, 13 + i, TAPE_H + 12, fill=(6, 10, 7, al)); fr.rect(FW - 13 - i, 12, FW - 12 - i, TAPE_H + 12, fill=(6, 10, 7, al))
    fr.rect(6, 6, FW - 6, TAPE_H + 18, 4, outline=(14, 16, 12, 255), width=7); fr.rect(8, 8, FW - 8, TAPE_H + 16, 3, outline=(104, 110, 84, 255), width=2.2)
    fr.poly([(cx, 24), (cx - 7, 9), (cx + 7, 9)], fill=AMBER + (255,), outline=(20, 14, 6, 255), width=0.6)
    fr.line([(cx, 24), (cx, TAPE_H + 12)], AMBER + (210,), 1.2)
    fr.rect(cx - 36, TAPE_H + 22, cx + 36, 84, 3, fill=(4, 8, 5, 240), outline=AMBER + (220,), width=1.2)
    fr.save(D, 'tape_frame')
    plate(280, 196, 34, 'CREW', GREEN, 208).save(D, 'pl_crew')


def marker(kind, sel=False):
    a = Art(MK, MK); c = MK / 2.0
    pale = (246, 240, 214)
    if kind == 'ret':
        for w, cc in ((4.6, pale + (235,)), (2.0, (20, 22, 18, 255))):
            a.circ(c, c, 13, outline=cc, width=w)
            for q in range(4):
                dx, dy = math.cos(q * math.pi / 2), math.sin(q * math.pi / 2)
                a.line([(c + dx * 7, c + dy * 7), (c + dx * 29, c + dy * 29)], cc, w)
        a.circ(c, c, 1.6, fill=RED + (255,))
    elif kind == 'lock':
        for w, cc in ((5.0, pale + (230,)), (2.4, (196, 30, 22, 255))):
            a.poly([(c, c - 11), (c + 11, c), (c, c + 11), (c - 11, c)], outline=cc, width=w)
        a.line([(c - 4, c), (c + 4, c)], (196, 30, 22, 255), 1.6); a.line([(c, c - 4), (c, c + 4)], (196, 30, 22, 255), 1.6)
    elif kind == 'gpos':
        a.line([(c, c - 9), (c, c - 18)], (22, 60, 140, 255), 2.6)
        a.rect(c - 9, c - 9, c + 9, c + 9, 2, fill=pale + (240,), outline=(22, 60, 140, 255), width=2.4)
        a.circ(c, c, 3.4, fill=(22, 60, 140, 255))
    elif kind == 'imp':
        for w, cc in ((5.0, pale + (220,)), (2.6, (30, 26, 22, 255))):
            a.line([(c - 8, c - 8), (c + 8, c + 8)], cc, w); a.line([(c - 8, c + 8), (c + 8, c - 8)], cc, w)
    elif kind == 'msn':
        col = (236, 120, 20)
        if sel:
            for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                br = [(c + sx * 22, c + sy * 12), (c + sx * 22, c + sy * 22), (c + sx * 12, c + sy * 22)]
                a.line(br, (20, 18, 14, 255), 3.4); a.line(br, (255, 236, 150, 255), 1.6)
        a.circ(c, c, 12, fill=pale + (215,), outline=(20, 18, 14, 255), width=4.4); a.circ(c, c, 12, outline=col + (255,), width=2.6)
        a.poly([(c - 2, c + 1), (c - 2, c - 7), (c + 7, c - 3)], fill=col + (255,)); a.line([(c - 2, c - 7), (c - 2, c + 7)], (20, 18, 14, 255), 1.6)
    elif kind == 'fl':
        col = (214, 26, 20); pts = []
        for k in range(16):
            r = 15 if k % 2 == 0 else 7; q = k * math.pi / 8
            pts.append((c + r * math.sin(q), c - r * math.cos(q)))
        a.poly(pts, fill=(255, 226, 120, 240) if sel else pale + (225,), outline=col + (255,), width=2.2)
        a.circ(c, c, 3, fill=col + (255,))
        if sel: a.circ(c, c, 21, outline=(20, 18, 14, 255), width=3.0); a.circ(c, c, 21, outline=(255, 236, 150, 255), width=1.4)
    return a


def art_board(D):
    for k in ('ret', 'lock', 'gpos', 'imp', 'msn', 'fl'): marker(k).save(D, 'm_' + k)
    marker('msn', True).save(D, 'm_msn_sel'); marker('fl', True).save(D, 'm_fl_sel')
    for i in range(CEP_N):
        r = (i + 1) * CEP_STEP * BOARD_PX / (2.0 * BOARD_EXT)
        a = Art(MK, MK)
        a.circ(MK / 2, MK / 2, r, fill=(196, 30, 22, 36))
        for k in range(0, 360, 30): a.arc(MK / 2, MK / 2, r, k, k + 20, (196, 30, 22, 255), 1.5)
        a.save(D, 'cep%d' % i)
    W, H = BW, BH
    a = plate(W, H, 40, 'FIRE DIRECTION CENTER', AMBER, 246, sub='PLOTTING BOARD   1:25 000   GRID A-P / 1-16')
    a.rect(MX - 3, MY - 3, MX + BOARD_PX + 3, MY + BOARD_PX + 3, 0, fill=(6, 8, 5, 255), outline=(110, 116, 90, 255), width=1.2)
    for (nm, lab, col, lx, ly) in LAMPS:                     # state lamps, unlit
        a.rect(SX + lx, MY + ly, SX + lx + 108, MY + ly + 32, 3, fill=lerp3(col, (0, 0, 0), 0.86) + (255,), outline=(90, 96, 74, 255), width=0.8)
        a.text(SX + lx + 54, MY + ly + 16.5, lab, 12, lerp3(col, (0, 0, 0), 0.55) + (255,), 'mm', 0.16)
    for y in (84, 254, 484): a.line([(SX, MY + y), (SX + 224, MY + y)], KEY + (60,), 1)
    a.text(SX, MY + 272, 'LEGEND', 10, GREY + (255,), 'lm', 0.22)
    leg = [('ret', 'YOUR RETICLE'), ('lock', 'LOCKED TARGET, 50 % CIRCLE'), ('gpos', 'YOUR GUN'), ('imp', 'YOUR LAST IMPACTS'), ('msn', 'FIRE MISSION FROM THE FIELD'), ('fl', 'ENEMY GUN FLASH')]
    for i, (k, txt) in enumerate(leg):
        y = MY + 300 + i * 30
        a.rect(SX, y - 13, SX + 30, y + 13, 2, fill=(206, 198, 170, 255))
        mk_ = marker(k).im.resize((int(34 * a.s), int(34 * a.s)), Image.LANCZOS)
        a.im.alpha_composite(mk_, (int((SX - 2) * a.s), int((y - 17) * a.s))); a.d = ImageDraw.Draw(a.im)
        a.text(SX + 40, y + 0.5, txt, 10, CREAM + (235,), 'lm', 0.04, 'Regular')
    a.text(SX, MY + 502, 'CONTROLS', 10, GREY + (255,), 'lm', 0.22)
    keys = [('W A S D', 'move the reticle'), ('SHIFT', 'fine steps'), ('R', 'next mission / flash'), ('MOUSE 1', 'lock, then fire'), ('E', 'leave the board')]
    for i, (k, txt) in enumerate(keys):
        y = MY + 528 + i * 24
        a.rect(SX, y - 9, SX + 66, y + 9, 3, outline=CREAM + (220,), width=0.8); a.text(SX + 33, y + 0.5, k, 9.5, CREAM + (255,), 'mm', 0.08)
        a.text(SX + 76, y + 0.5, txt, 10.5, CREAM + (220,), 'lm', 0.04, 'Regular')
    a.rect(12, FY - 4, W - 12, H - 12, 3, fill=(0, 0, 0, 120), outline=KEY + (60,), width=0.8)
    a.save(D, 'pl_board')
    for (nm, lab, col, lx, ly) in LAMPS:
        l = Art(108, 32)
        l.rect(0, 0, 108, 32, 3, fill=tuple(col) + (255,)); l.rect(1, 1, 107, 12, 3, fill=lerp3(col, (255, 255, 255), 0.4) + (255,))
        l.text(54, 16.5, lab, 12, lerp3(col, (0, 0, 0), 0.85) + (255,), 'mm', 0.16)
        l.save(D, 'lamp_' + nm)
    n = BOARD_PX                                             # the glass over the map: edge shadow and a soft reflection
    yy, xx = np.mgrid[0:n, 0:n] / float(n)
    e = np.minimum(np.minimum(xx, 1 - xx), np.minimum(yy, 1 - yy))
    sh = np.clip(1 - e / 0.035, 0, 1) ** 2 * 150
    gl = np.clip(1 - np.abs((xx + yy) - 0.42) / 0.10, 0, 1) ** 2 * 18
    rgb = np.where(gl > sh, 255, 0)
    Image.fromarray(np.dstack([rgb, rgb, rgb, np.maximum(sh, gl)]).astype(np.uint8), 'RGBA').save(os.path.join(D, 'board_glass.png'), optimize=True)


# ================================================================ layout + css
def build(out, art=True):
    D = os.path.join(out, 'panorama/images/custom_game/mv'); os.makedirs(D, exist_ok=True)
    if art:
        art_common(D); art_objective(D); art_fly(D); art_board(D)
    h = panorama.Hud(img_url=IMG, img_dir=D, place_prefix='q')
    R = h.rule
    url = lambda n: 'url("%s%s.png")' % (IMG, n)
    cnt = [0]; pics = {}

    def pin(x=None, y=0, w=None, hh=None, right=None, center=False, off=0, **more):
        """a class that pins a box: from the left (x), the right edge (right), or centred (+ off px to the right)"""
        cnt[0] += 1; c = 'q%d' % cnt[0]
        p = dict(width='%dpx' % w, height='%dpx' % hh)
        if center:
            p['horizontal_align'] = 'center'
            if off: p['margin_left'] = '%dpx' % off
        elif right is not None: p['horizontal_align'] = 'right'; p['margin_right'] = '%dpx' % right
        else: p['margin_left'] = '%dpx' % (x or 0)
        p['margin_top'] = '%dpx' % y
        p.update(more)
        R('.' + c, **p)
        return c

    def pic(name):
        if name not in pics:
            pics[name] = 'i_' + name; R('.i_' + name, background_image=url(name))
        return pics[name]

    def img(name, x, y, w, hh, cls=''):
        return P(None, ' '.join(c for c in ('Pic', cls, pic(name), pin(x, y, w, hh)) if c))

    def lab(id_, x, y, w, hh, size, color=CREAM, align='left', cls='', **more):
        c = pin(x, y, w, hh, font_size='%dpx' % size, color=HEXC(color), text_align=align, **more)
        return P(id_, (cls + ' ' + c).strip(), tag='Label', extra='text="{s:v}"')

    BLINK = dict(animation_name='"mvblink"', animation_iteration_count='infinite')
    R('.HudWrap', width='100%', height='100%')
    R('.Screen', width='100%', height='1080px')
    R('.Screen Label', font_family=FONT, font_weight='bold', color=HEXC(CREAM), text_shadow='1px 1px 2px 2.0 #000000', white_space='nowrap')
    R('.Pic', background_size='100% 100%', background_repeat='no-repeat')
    R('.Clip', overflow='clip')
    R('.NoClip', overflow='noclip')
    # every show / hide is an opacity change (hud.md); `show` and `on` only ever appear together with a panel class
    R('.Box', opacity='0', transition_property='opacity', transition_duration='0.25s')
    R('.Box.show', opacity='1')
    h.raw('@keyframes "mvblink" { 0% { opacity: 1.0; } 50% { opacity: 0.3; } 100% { opacity: 1.0; } }')
    body = []

    # ---------------------------------------------------------------- objective bar + capture ring (top centre)
    # bars switch one picture per step (frames()): no sliding fill, no clipping track
    kids = [img('pl_obj', 0, 0, 560, 96),
            lab('mv_tk_t', 14, 4, 76, 42, 34, TCOL, 'left', 'Tk'), lab('mv_tk_ct', 470, 4, 76, 42, 34, CTCOL, 'right', 'Tk'),
            P('mv_tkbar_t', 'Pic TkT ' + pic('tk_t_20') + ' ' + pin(14, 50, 120, 8)),
            P('mv_tkbar_ct', 'Pic TkCT ' + pic('tk_ct_20') + ' ' + pin(426, 50, 120, 8)),
            lab('mv_clock', 236, 72, 88, 20, 16, CREAM, 'center', letter_spacing='1px')]
    R('.Tk.bleed', color=HEXC(RED), animation_duration='0.9s', **BLINK)
    for n in range(21):
        R('.TkT.w%d' % n, background_image=url('tk_t_%d' % n)); R('.TkCT.w%d' % n, background_image=url('tk_ct_%d' % n))
    # one transparent 560 x OBJ_H panel per flag: its badge sits in the bar, its capture ring under the bar (shown by `here`)
    R('.FlagBg', background_image=url('flag_n'))
    for o in ('n', 't', 'ct'): R('.Flag.own_%s .FlagBg' % o, background_image=url('flag_' + o))
    R('.FlagCap', background_size='100% 100%')
    for o in ('t', 'ct'):
        R('.Flag.capt_%s .FlagCap' % o, background_image=url('flagcap_%s_0' % o))
        for n in range(11): R('.Flag.capt_%s.cap%d .FlagCap' % (o, n), background_image=url('flagcap_%s_%d' % (o, n)))
    R('.CapRing', background_image=url('ring_n'))
    for o in ('t', 'ct'):
        for n in range(1, 11): R('.Flag.capt_%s.cap%d .CapRing' % (o, n), background_image=url('ring_%s_%d' % (o, n)))
    for c in ('FlagWarn', 'FlagHere', 'CapBox', 'CapWarn'): R('.' + c, opacity='0', transition_property='opacity', transition_duration='0.2s')
    R('.Flag.contest .FlagWarn', opacity='1', animation_duration='0.7s', **BLINK)
    R('.Flag.contest .CapWarn', opacity='1')
    R('.Flag.here .FlagHere', opacity='1'); R('.Flag.here .CapBox', opacity='1')
    for i, (l, name) in enumerate(FLAGS):
        slot = P(None, pin(144 + i * 56, 2, 48, 62), [
            P(None, 'Pic FlagBg ' + pin(0, 2, 48, 48)),
            P(None, 'Pic FlagCap ' + pin(4, 6, 40, 40)),
            img('flag_l_' + l, 0, 2, 48, 48), img('flag_warn', 0, 2, 48, 48, 'FlagWarn'), img('flag_here', 0, 0, 48, 62, 'FlagHere')])
        capbox = P(None, 'CapBox ' + pin(200, 104, 160, 116), [
            P(None, 'Pic CapRing ' + pin(38, 0, 84, 84)), img('cap_core_' + l, 38, 0, 84, 84),
            img('cap_name_' + l, 0, 90, 160, 24), img('cap_contest', 0, 90, 160, 24, 'CapWarn')])
        kids.append(P('mv_flag_' + l, 'Flag ' + pin(0, 0, 560, OBJ_H), [slot, capbox]))
    body.append(P('mv_obj', 'Box ' + pin(None, 72, 560, OBJ_H, center=True), kids))
    # ---------------------------------------------------------------- event feed (HUD additions): top right, under CS2's kill feed
    R('.Feed', background_image=url('feed_n'), background_size='100% 100%', padding_right='16px', font_size='18px', text_align='right',
      color=HEXC(CREAM), letter_spacing='0.5px', text_shadow='0px 0px 4px 2.0 #000000e0')
    R('.Feed.feed_good', color=HEXC(FEED_GOOD), background_image=url('feed_good'))
    R('.Feed.feed_bad', color=HEXC(FEED_BAD), background_image=url('feed_bad'))
    for k in range(1, 4):
        body.append(P('mv_feed_%d' % k, 'Box Feed ' + pin(None, FEED_Y + (k - 1) * FEED_DY, FEED_W, FEED_H, right=24),
                      tag='Label', extra='text="{s:v}"'))

    # ---------------------------------------------------------------- briefing card (lobby), role card (right)
    body.append(P('mv_brief', 'Box ' + pin(None, 216, 640, 372, center=True), [
        img('pl_brief', 0, 0, 640, 372),
        lab('mv_brief_role', 20, 50, 600, 64, 50, AMBER, 'center', letter_spacing='3px'),
        lab('mv_brief_l1', 30, 124, 580, 30, 23, CREAM, 'center'), lab('mv_brief_l2', 30, 160, 580, 30, 23, CREAM, 'center'),
        lab('mv_brief_l3', 30, 196, 580, 30, 23, CREAM, 'center'),
        lab('mv_brief_spawn', 30, 258, 580, 32, 25, AMBER, 'center', letter_spacing='1px'),
        lab('mv_brief_count', 30, 328, 580, 28, 21, GREEN, 'center')]))
    # right column, under the event feed; 360 wide so it clears the briefing card on 4:3 (1440: brief 400-1040, info 1060-1420)
    body.append(P('mv_info', 'Box ' + pin(None, 290, INFO_W, 330, right=20), [
        img('pl_info', 0, 0, INFO_W, 330), lab('mv_info_title', 24, 6, INFO_W - 40, 34, 25, GREEN, 'left', letter_spacing='2px')] +
        [lab('mv_info_l%d' % k, 22, 58 + (k - 1) * 42, INFO_W - 40, 26, 19, CREAM) for k in range(1, 6)] +
        [lab('mv_info_foot', 22, 292, INFO_W - 40, 24, 16, GREY)]))
    # ---------------------------------------------------------------- banner, toast, prompt, hold
    body.append(P('mv_banner', 'Box ' + pin(None, 300, 640, 100, center=True), [
        img('pl_banner', 0, 0, 640, 100),
        lab('mv_banner_title', 0, 8, 640, 54, 44, AMBER, 'center', letter_spacing='4px'),
        lab('mv_banner_sub', 0, 62, 640, 28, 21, CREAM, 'center', letter_spacing='1px')]))
    body.append(P('mv_toast', 'Box ' + pin(None, 680, 560, 52, center=True), [
        img('pl_toast', 0, 0, 560, 52), lab('mv_toast_text', 10, 8, 540, 36, 27, AMBER, 'center', letter_spacing='1px')]))
    body.append(P('mv_prompt', 'Box ' + pin(None, 612, 480, 46, center=True), [
        img('pl_prompt', 0, 0, 480, 46), lab('mv_prompt_text', 10, 7, 460, 32, 24, (255, 255, 255), 'center')]))
    for n in range(21): R('.HoldFill.p%d' % n, background_image=url('hold_%d' % n))
    body.append(P('mv_hold', 'Box ' + pin(None, 556, 320, 42, center=True), [          # ends y 598: clear of the 4:3 chat box (y 600)
        img('pl_hold', 0, 0, 320, 42), lab('mv_hold_text', 10, 3, 300, 22, 16, AMBER, 'center', letter_spacing='2px'),
        P('mv_hold_bar', 'Pic HoldFill ' + pic('hold_0') + ' ' + pin(30, 27, 260, 8))]))
    # ---------------------------------------------------------------- status box (left, under CS2's radar)
    body.append(P('mv_status', 'Box ' + pin(24, 336, ST_W, 136), [
        img('pl_status', 0, 0, ST_W, 136), lab('mv_st_role', 18, 8, ST_W - 30, 30, 20, AMBER, 'left', letter_spacing='1px'),
        lab('mv_st_l1', 18, 50, ST_W - 30, 24, 18), lab('mv_st_l2', 18, 77, ST_W - 30, 24, 18), lab('mv_st_l3', 18, 104, ST_W - 30, 24, 17, GREY)]))
    # ---------------------------------------------------------------- requisition row (batch G, docs/WEAPONS.md): points, next upgrade
    R('.ReqReady', opacity='0', transition_property='opacity', transition_duration='0.3s')
    R('.Req.ready .ReqReady', opacity='1', animation_duration='1.6s', **BLINK)
    body.append(P('mv_req', 'Box Req ' + pin(24, REQ_Y, ST_W, REQ_H), [
        img('pl_req', 0, 0, ST_W, REQ_H), img('req_ready', 0, 0, ST_W, REQ_H, 'ReqReady'),
        lab('mv_req_pts', 54, 4, 130, 26, 20, GREEN, 'left', letter_spacing='1px'),
        lab('mv_req_next', 54, 28, ST_W - 66, 18, 14, CREAM, 'left', letter_spacing='0.5px')]))
    # ---------------------------------------------------------------- gun box (bottom right): name, belt (HUD addition), heat
    for n in range(11): R('.HeatFill.ht%d' % n, background_image=url('heat_%d' % n))
    R('.GunHot', opacity='0')
    R('.Gun.hot .GunHot', opacity='1', animation_duration='0.5s', **BLINK)
    body.append(P('mv_gun', 'Box Gun ' + pin(None, 880, 300, GUN_H, right=24), [
        img('pl_gun', 0, 0, 300, GUN_H), img('gun_hot', 0, 0, 300, GUN_H, 'GunHot'),      # the red overlay under the text, not over it
        lab('mv_gun_name', 18, 8, 264, 28, 22, AMBER, 'left', letter_spacing='1px'),
        lab('mv_gun_ammo', 18, 38, 150, 22, 17, CREAM, 'left', letter_spacing='1px'),
        P('mv_gun_heat', 'Pic HeatFill ' + pic('heat_0') + ' ' + pin(64, 72, 220, 14))]))

    # ---------------------------------------------------------------- helicopter instruments
    R('.Full', width='100%', height='1080px')
    R('.Rot', background_size='100% 100%', transition_property='transform', transition_duration='0.12s')
    for n in range(72): R('.Rot.a%d' % n, transform='rotateZ(%ddeg)' % (n * 5))
    # horizon: one round picture per pitch step inside the rolling panel; heading tape: one window picture per heading step
    for n in range(21): R('.AiPitch.pit%d' % n, background_image=url('ai_%d' % n))
    for n in range(72): R('.Tape.h%d' % n, background_image=url('tape_%d' % n))
    for n in range(21): R('.HpFill.hp%d' % n, background_image=url('hp_%d' % n))
    R('.RtbOn', opacity='0'); R('.RtbOn.on', opacity='1', animation_duration='0.6s', **BLINK)
    R('.Seat.me', color=HEXC(AMBER))
    R('.PilotOnly', opacity='1', transition_property='opacity', transition_duration='0.2s')
    R('.Fly.seat_pilot .PilotOnly', opacity='1')
    R('.Fly.seat_gunner .PilotOnly', opacity='0'); R('.Fly.seat_rider .PilotOnly', opacity='0')
    glow = dict(text_shadow='0px 0px 5px 1.5 #58e07a90')

    def gauge(i, face, needle_id, needle_pic, txt_id=None, pilot=True):
        k = [img(face, 0, 0, G, G)]
        if txt_id: k.append(lab(txt_id, G // 2 - 25, G // 2 - 36, 50, 22, 17, PHOS, 'center', **glow))
        k += [P(needle_id, 'Rot ' + pic(needle_pic) + ' ' + pin(0, 0, G, G)), img('g_bezel', 0, 0, G, G)]
        g = P(None, ('PilotOnly ' if pilot else '') + pin(GX[i], GY, G, G), k)
        return [img('g_blank', GX[i], GY, G, G), g] if pilot else [g]      # gunner / rider see a cover plate, not an empty hole
    horizon = P(None, pin(GX[1], GY, G, G), [
        P('mv_ai_roll', 'Rot ' + pin(0, 0, G, G), [
            P('mv_ai_pitch', 'Pic AiPitch ' + pic('ai_10') + ' ' + pin(0, 0, G, G)),
            img('ai_ptr', 0, 0, G, G)]),
        img('g_bezel_ai', 0, 0, G, G)])
    dash = P(None, pin(None, 792, 716, 200, center=True), [
        img('dash', 0, 0, 716, 200),
        P('mv_heli_hp', 'Pic HpFill ' + pic('hp_20') + ' ' + pin(HPX, 16, 220, 14)),
        P('mv_rtb', 'Pic RtbOn ' + pic('rtb_on') + ' ' + pin(RTBX, 10, 64, 26)),
        P(None, 'PilotOnly ' + pin(RKX, 10, 140, 26), [lab('mv_rkt_txt', 0, 1, 140, 24, 19, PHOS, 'center', letter_spacing='2px', **glow)])] +
        gauge(0, 'g_asi', 'mv_n_asi', 'g_needle', 'mv_spd_txt') + [horizon] +
        gauge(2, 'g_alt', 'mv_n_alt', 'g_needle', 'mv_alt_txt', pilot=False) + gauge(3, 'g_vsi', 'mv_n_vsi', 'g_needle_vsi'))
    tape = P(None, pin(None, 190, TAPE_WIN + 24, 86, center=True), [
        P('mv_hdg', 'Pic Tape ' + pic('tape_0') + ' ' + pin(12, 12, TAPE_WIN, TAPE_H)),
        img('tape_frame', 0, 0, TAPE_WIN + 24, 86),
        lab('mv_hdg_txt', (TAPE_WIN + 24) // 2 - 36, TAPE_H + 23, 72, 26, 21, AMBER, 'center', letter_spacing='2px')])
    crew = P(None, pin(None, 640, 280, 196, right=24), [img('pl_crew', 0, 0, 280, 196)] +
             [lab('mv_seat_%d' % k, 16, 40 + (k - 1) * 25, 250, 23, 17, CREAM, 'left', 'Seat') for k in range(1, 7)])
    info = lab('mv_fly_info', None, 758, 700, 26, 19, AMBER, 'center', letter_spacing='1px')
    info = P('mv_fly_info', pin(None, 758, 700, 26, center=True, font_size='19px', color=HEXC(AMBER), text_align='center', letter_spacing='1px'), tag='Label', extra='text="{s:v}"')
    body.append(P('mv_fly', 'Box Fly Full', [tape, info, dash, crew]))

    # ---------------------------------------------------------------- artillery board
    R('.MCol', overflow='noclip', opacity='0', transition_property='transform', transition_duration='0.08s')
    R('.MCol.on', opacity='1')
    R('.MSq', background_size='100% 100%', overflow='noclip', transition_property='transform', transition_duration='0.08s')
    for n in range(BOARD_STEPS):
        t = int(round((n + 0.5) * STEP - MK / 2))
        R('.MCol.x%d' % n, transform='translatex(%dpx)' % t); R('.MSq.y%d' % n, transform='translatey(%dpx)' % t)
    R('.MCol.sel .MsnSq', background_image=url('m_msn_sel')); R('.MCol.sel .FlSq', background_image=url('m_fl_sel'))
    R('.Cep', background_size='100% 100%', opacity='0'); R('.Cep.on', opacity='1')
    for n in range(CEP_N): R('.Cep.cep%d' % n, background_image=url('cep%d' % n))
    R('.Lamp', opacity='0', transition_property='opacity', transition_duration='0.15s')
    for nm, lab_, col, lx, ly in LAMPS: R('.Board.lay_%s .Lamp_%s' % (nm, nm), opacity='1')
    R('.MCol.Old1.on', opacity='0.62'); R('.MCol.Old2.on', opacity='0.36')

    def mk(id_, kind, extra='', child=None):
        return P(id_, ' '.join(c for c in ('MCol', extra, pin(0, 0, MK, BOARD_PX)) if c),
                 [P(id_ + 'y', 'MSq %sSq %s %s' % (kind.capitalize(), pic('m_' + kind), pin(0, 0, MK, MK)), child)])
    marks = [mk('mv_fl%d' % i, 'fl') for i in range(4)] + [mk('mv_msn%d' % i, 'msn') for i in range(5)] + \
            [mk('mv_imp2', 'imp', 'Old2'), mk('mv_imp1', 'imp', 'Old1'), mk('mv_imp0', 'imp'), mk('mv_gpos', 'gpos'),
             mk('mv_lock', 'lock', child=[P('mv_cep', 'Cep ' + pin(0, 0, MK, MK))]), mk('mv_ret', 'ret')]
    bmap = P(None, 'Pic Clip ' + pic('board') + ' ' + pin(MX, MY, BOARD_PX, BOARD_PX), marks + [img('board_glass', 0, 0, BOARD_PX, BOARD_PX)])
    side = [img('lamp_' + nm, SX + lx, MY + ly, 108, 32, 'Lamp Lamp_' + nm) for nm, lab_, col, lx, ly in LAMPS] + [
        lab('mv_b_gun', SX, MY + 94, 224, 30, 23, AMBER, 'left', letter_spacing='1px'),
        lab('mv_b_shell', SX, MY + 128, 224, 26, 19, CREAM),
        lab('mv_b_range', SX, MY + 174, 224, 28, 21, PHOS), lab('mv_b_grid', SX, MY + 206, 224, 28, 21, PHOS)]
    foot = [lab('mv_b_state', 24, FY + 1, 540, 30, 23, GREEN, 'left', letter_spacing='1px'),
            lab('mv_b_msn', BW - 24 - 300, FY + 4, 300, 26, 19, AMBER, 'right'),
            lab('mv_b_stats', 24, FY + 31, 540, 22, 16, GREY, 'left', letter_spacing='1px')]
    # y 196: under the objective bar and its clock tab (ends y 166) and below CS2's kill feed (ends ~y 190) at every width
    body.append(P('mv_board', 'Box Board ' + pin(None, 196, BW, BH, center=True, off=70), [img('pl_board', 0, 0, BW, BH), bmap] + side + foot))

    body.append(h.preload(NAME, slides=SLIDES, radar=False, icon=True, prefix='MvPre'))
    h.hide_with_scoreboard('Box')
    dyn = r'^(show|on|me|hot|bleed|contest|here|sel|own_\w+|capt_\w+|cap\d+|p\d+|w\d+|a\d+|h\d+|pit\d+|hp\d+|ht\d+|x\d+|y\d+|cep\d+|lay_\w+|seat_\w+|feed_\w+)$'
    xp, cp = h.write(out, NAME, P(None, 'Screen', body), dynamic=dyn)
    return h, xp, cp


# ================================================================ the contract (docs/SCRIPT.md) and out/hud.json
def contract():
    p = os.path.join(HERE, '..', 'docs', 'SCRIPT.md')
    if not os.path.exists(p): return None
    md = open(p, encoding='utf-8').read()
    m = re.search(r'HUD-CONTRACT-BEGIN[^\n]*\n(.*?)<!-- HUD-CONTRACT-END', md, re.S)
    if not m: return None
    rows = m.group(1)
    m2 = re.search(r'HUD-ADDITIONS-BEGIN[^\n]*\n(.*?)<!-- HUD-ADDITIONS-END', md, re.S)    # "HUD additions (pass 1)": built too
    if m2: rows += '\n' + m2.group(1)
    c = {}
    for line in rows.split('\n'):
        f = [s.strip() for s in line.split('|')]
        if len(f) < 5 or not f[1].startswith('mv_'): continue
        e = c.setdefault(f[1], dict(text=False, classes=[], swaps=[]))
        if f[2] == 'text': e['text'] = True; continue
        grp = []
        for part in [s.strip() for s in f[3].split(',') if s.strip()]:
            r = re.match(r'^([a-z_]+?)(\d+)\.\.\1(\d+)$', part)
            grp += ['%s%d' % (r.group(1), i) for i in range(int(r.group(2)), int(r.group(3)) + 1)] if r else [part]
        e['classes'] += grp
        if f[2] == 'swap': e['swaps'].append(grp)
    return c


def check_contract(xp, cp):
    """ids and classes against docs/SCRIPT.md; returns (problems, contract)"""
    con = contract()
    if con is None: return ['docs/SCRIPT.md has no HUD contract table'], None
    xml = open(xp, encoding='utf-8').read(); css = open(cp, encoding='utf-8').read()
    ids = re.findall(r'<(\w+) id="([^"]+)"[^>]*>', xml)
    idset = set(i for _, i in ids); tags = dict((i, t) for t, i in ids)
    prob = ['contract id missing from the layout: ' + i for i in con if i not in idset]
    prob += ['layout id not in the contract: ' + i for i in sorted(idset) if i not in con]
    cls_css = set(re.findall(r'\.([A-Za-z_][\w-]*)', css))
    for i, e in con.items():
        if i not in idset: continue
        if e['text'] and (tags[i] != 'Label' or not re.search(r'id="%s"[^>]*text="\{s:v\}"' % re.escape(i), xml)): prob.append('%s must be a Label with text="{s:v}"' % i)
        for c in e['classes']:
            if c not in cls_css: prob.append('%s: class %s has no css rule' % (i, c))
    return prob, con


def write_hud_json(con, n_ids):
    p = os.path.join(HERE, '..', 'out', 'hud.json')
    old = json.load(open(p)) if os.path.exists(p) else {}
    data = {k: v for k, v in old.items() if k == 'apache'}            # keep what another tool put there for the script
    data.update(board_steps=BOARD_STEPS, board_ext=BOARD_EXT, board_px=BOARD_PX, board_step_px=STEP, cep_step=CEP_STEP, cep_n=CEP_N,
                needle_steps=72, needle_deg=5, heading_steps=72, pitch_steps=21, pitch_deg_per_step=2, pitch_level=10,
                hold_steps=21, ticket_steps=21, cap_steps=11, hp_steps=21, heat_steps=11, seats=6, missions=5, flashes=4, impacts=3,
                panel_ids=n_ids, layout=NAME)
    if con:
        data['ids'] = sorted(con)
        data['text_ids'] = sorted(i for i, e in con.items() if e['text'])
        data['swap_counts'] = {i: [len(g) for g in e['swaps']] for i, e in con.items() if e['swaps']}
    json.dump(data, open(p, 'w'), indent=1)
    return p


# ================================================================ states for hud_check.py (and docs/HUD.md)
def states():
    obj = {'mv_obj': {'add': ['show']}, 'mv_tk_t': {'text': '312'}, 'mv_tk_ct': {'text': '287', 'add': ['bleed']}, 'mv_clock': {'text': '14:32'},
           'mv_tkbar_t': {'add': ['w16']}, 'mv_tkbar_ct': {'add': ['w14']},
           'mv_flag_a': {'add': ['own_t', 'cap0']}, 'mv_flag_b': {'add': ['own_n', 'cap6', 'capt_ct']}, 'mv_flag_c': {'add': ['own_t', 'cap0']},
           'mv_flag_d': {'add': ['own_ct', 'cap3', 'capt_t', 'contest']}, 'mv_flag_e': {'add': ['own_ct', 'cap0']}}
    return {
        'lobby': {'_chat_top': 800,
                  'mv_brief': {'add': ['show']}, 'mv_brief_role': {'text': 'INFANTRY'}, 'mv_brief_l1': {'text': 'Take and hold the five flags of the valley.'},
                  'mv_brief_l2': {'text': 'Kits at the arms rack: !rifle  !mg  !at'}, 'mv_brief_l3': {'text': 'Hold USE on open ground to call a fire mission.'},
                  'mv_brief_spawn': {'text': 'DEPLOY: BRIDGE   [R] next'}, 'mv_brief_count': {'text': 'Deploying in 7   -   !infantry  !artillery  !air'},
                  'mv_info': {'add': ['show']}, 'mv_info_title': {'text': 'ROLES'}, 'mv_info_l1': {'text': '!infantry   rifle, MG or anti-tank'},
                  'mv_info_l2': {'text': '!artillery   crew a gun (3 of 6 free)'}, 'mv_info_l3': {'text': '!air   pilot slot (1 of 3 free)'},
                  'mv_info_l4': {'text': '!spawn a-e | base'}, 'mv_info_l5': {'text': '!swap   change team'}, 'mv_info_foot': {'text': '!roles shows this card again'},
                  'mv_feed_1': {'add': ['show'], 'text': 'We are down to 50 tickets'}},
        'infantry': dict(obj, **{
            'mv_status': {'add': ['show']}, 'mv_st_role': {'text': 'INFANTRY  /  MACHINE GUNNER'}, 'mv_st_l1': {'text': 'M60   kit rack: E'},
            'mv_st_l2': {'text': 'Fire missions: 1 ready'}, 'mv_st_l3': {'text': 'Merit 3'},
            'mv_req': {'add': ['show', 'ready']}, 'mv_req_pts': {'text': 'REQ 45  +10'}, 'mv_req_next': {'text': 'SNIPER READY  -  F at a rack'},
            'mv_hold': {'add': ['show']}, 'mv_hold_text': {'text': 'CALLING FIRE MISSION'}, 'mv_hold_bar': {'add': ['p13']},
            'mv_prompt': {'add': ['show']}, 'mv_prompt_text': {'text': '[E]  Board the helicopter (door gunner)'},
            'mv_toast': {'add': ['show']}, 'mv_toast_text': {'text': 'SPLASH  -  GRID F7'},
            'mv_feed_1': {'add': ['show', 'feed_good'], 'text': 'We took B BRIDGE'},
            'mv_feed_2': {'add': ['show', 'feed_bad'], 'text': 'Our howitzer 2 is knocked out'},
            'mv_feed_3': {'add': ['show'], 'text': 'p12 shot down a UH-1 over C VILLAGE'}}),
        'capture': dict(obj, **{'mv_flag_b': {'add': ['own_n', 'cap6', 'capt_ct', 'here']},
                                'mv_banner': {'add': ['show']}, 'mv_banner_title': {'text': 'VILLAGE TAKEN'}, 'mv_banner_sub': {'text': 'US forces hold 3 of 5: the enemy is bleeding'},
                                'mv_status': {'add': ['show']}, 'mv_st_role': {'text': 'INFANTRY  /  RIFLEMAN'}, 'mv_st_l1': {'text': 'M16A1'},
                                'mv_st_l2': {'text': 'Capturing BRIDGE'}, 'mv_st_l3': {'text': 'Merit 1'},
                                'mv_req': {'add': ['show']}, 'mv_req_pts': {'text': 'REQ 25  +15'}, 'mv_req_next': {'text': 'SHOTGUN IN 5'},
                                'mv_info': {'add': ['show']}, 'mv_info_title': {'text': 'ARMORY   REQ 25'},
                                'mv_info_l1': {'text': '> FRAG POUCH  M26 + SMOKE  20'}, 'mv_info_l2': {'text': '   SHOTGUN  ITHACA 37  30'},
                                'mv_info_l3': {'text': '   CARBINE  XM177E2  35'}, 'mv_info_l4': {'text': '   SNIPER  M21  45'}, 'mv_info_l5': {'text': ''},
                                'mv_info_foot': {'text': '[F] next   [E] requisition'}}),
        'contested': dict(obj, **{'mv_flag_b': {'add': ['own_t', 'cap4', 'capt_ct', 'here', 'contest']}}),
        'fly_pilot': dict(obj, **{
            'mv_fly': {'add': ['show', 'seat_pilot']}, 'mv_ai_roll': {'add': ['a3']}, 'mv_ai_pitch': {'add': ['pit7']}, 'mv_n_asi': {'add': ['a41']},
            'mv_n_alt': {'add': ['a23']}, 'mv_n_vsi': {'add': ['a6']}, 'mv_hdg': {'add': ['h9']}, 'mv_hdg_txt': {'text': '045'}, 'mv_alt_txt': {'text': '132'},
            'mv_spd_txt': {'text': '68'}, 'mv_heli_hp': {'add': ['hp6']}, 'mv_rtb': {'add': ['on']}, 'mv_rkt_txt': {'text': 'RKT 22'},
            'mv_seat_1': {'text': 'PILOT    skink52', 'add': ['me']}, 'mv_seat_2': {'text': 'GUNNER   Bot Wesley'}, 'mv_seat_3': {'text': 'WING L   -'},
            'mv_seat_4': {'text': 'WING R   Maru'}, 'mv_fly_info': {'text': 'AIRFRAME 30 %  -  RETURN TO THE PAD TO REPAIR'}}),
        'fly_gunner': dict(obj, **{
            'mv_fly': {'add': ['show', 'seat_gunner']}, 'mv_ai_roll': {'add': ['a70']}, 'mv_ai_pitch': {'add': ['pit12']}, 'mv_n_alt': {'add': ['a9']},
            'mv_hdg': {'add': ['h40']}, 'mv_hdg_txt': {'text': '200'}, 'mv_alt_txt': {'text': '45'}, 'mv_heli_hp': {'add': ['hp17']},
            'mv_seat_1': {'text': 'PILOT    Bot Kyle'}, 'mv_seat_2': {'text': 'GUNNER   skink52', 'add': ['me']}, 'mv_seat_3': {'text': 'RIDER    -'},
            'mv_gun': {'add': ['show']}, 'mv_gun_name': {'text': 'PK DOOR GUN'}, 'mv_gun_ammo': {'text': 'BELT 87'}, 'mv_gun_heat': {'add': ['ht6']},
            'mv_feed_1': {'add': ['show', 'feed_bad'], 'text': 'C VILLAGE is under attack'}}),
        'mounted_hot': dict(obj, **{'mv_gun': {'add': ['show', 'hot']}, 'mv_gun_name': {'text': 'M2 .50 CAL'}, 'mv_gun_ammo': {'text': 'RELOADING 3 s'},
                                    'mv_gun_heat': {'add': ['ht10']},
                                    'mv_prompt': {'add': ['show']}, 'mv_prompt_text': {'text': '[E]  Leave the gun'}}),
        'board': dict(obj, **{
            '_chat_top': 800, 'mv_tk_ct': {'text': '287'},
            'mv_board': {'add': ['show', 'lay_laid']}, 'mv_ret': {'add': ['on', 'x74']}, 'mv_rety': {'add': ['y52']},
            'mv_lock': {'add': ['on', 'x76']}, 'mv_locky': {'add': ['y50']}, 'mv_cep': {'add': ['on', 'cep4']},
            'mv_gpos': {'add': ['on', 'x121']}, 'mv_gposy': {'add': ['y116']},
            'mv_imp0': {'add': ['on', 'x78']}, 'mv_imp0y': {'add': ['y47']}, 'mv_imp1': {'add': ['on', 'x70']}, 'mv_imp1y': {'add': ['y55']},
            'mv_imp2': {'add': ['on', 'x82']}, 'mv_imp2y': {'add': ['y58']},
            'mv_msn0': {'add': ['on', 'sel', 'x76']}, 'mv_msn0y': {'add': ['y50']}, 'mv_msn1': {'add': ['on', 'x47']}, 'mv_msn1y': {'add': ['y90']},
            'mv_msn2': {'add': ['on', 'x112']}, 'mv_msn2y': {'add': ['y68']},
            'mv_fl0': {'add': ['on', 'x34']}, 'mv_fl0y': {'add': ['y38']}, 'mv_fl1': {'add': ['on', 'x30']}, 'mv_fl1y': {'add': ['y47']},
            'mv_b_range': {'text': 'RANGE 2240 m'}, 'mv_b_grid': {'text': 'GRID H5  LOCKED'}, 'mv_b_gun': {'text': 'GUN 2  LAID'},
            'mv_b_shell': {'text': 'LOADED: HE'}, 'mv_b_state': {'text': 'READY - MOUSE1 / SPACE TO FIRE'},
            'mv_b_msn': {'text': 'MISSION 1/3  Maru  H5  32s'}, 'mv_b_stats': {'text': 'ROUNDS 12   HITS 3   MISSIONS 2'}}),
    }


def fly_preview(D, path, roll=15, pitch=-6, spd=68, alt=132, vsi=3, hdg=45, hp=6, pilot=True):
    """the instrument cluster drawn the way Panorama will (needle and horizon rotations, the class-picked frames): hud_check.py
    does not rotate, so this is the picture to judge the gauges by. pitch in degrees, nose up positive (pit = 10 + pitch / 2)."""
    L = lambda n: Image.open(os.path.join(D, n + '.png')).convert('RGBA')
    k = 2; W, H = 716 * k, 310 * k
    yy = np.linspace(0, 1, H)[:, None, None]
    bg = np.array([120, 150, 150]) * (1 - yy) + np.array([52, 70, 40]) * yy
    im = Image.fromarray(np.dstack([np.repeat(bg, W, 1), np.full((H, W), 255)]).astype(np.uint8), 'RGBA')
    oy = 110 * k
    im.alpha_composite(L('dash'), (0, oy))
    im.alpha_composite(L('hp_%d' % max(0, min(20, hp))), (HPX * k, oy + 16 * k))
    if hp < 10: im.alpha_composite(L('rtb_on'), (RTBX * k, oy + 10 * k))

    def put(layer, i): im.alpha_composite(layer.resize((G * k, G * k), Image.LANCZOS), (GX[i] * k, oy + GY * k))
    if pilot:
        put(L('g_asi'), 0); put(L('g_needle').rotate(-spd * 3.0, resample=Image.BICUBIC), 0); put(L('g_bezel'), 0)
        put(L('g_vsi'), 3); put(L('g_needle_vsi').rotate(-vsi * 13.5, resample=Image.BICUBIC), 3); put(L('g_bezel'), 3)
    else:
        put(L('g_blank'), 0); put(L('g_blank'), 3)
    put(L('g_alt'), 2); put(L('g_needle').rotate(-(alt % 100) * 3.6, resample=Image.BICUBIC), 2); put(L('g_bezel'), 2)
    pit = max(0, min(20, int(round(10 + pitch / 2.0))))
    ball = L('ai_%d' % pit).resize((G * k, G * k), Image.LANCZOS)
    ball.alpha_composite(L('ai_ptr').resize((G * k, G * k), Image.LANCZOS))
    put(ball.rotate(-roll, resample=Image.BICUBIC), 1); put(L('g_bezel_ai'), 1)
    tx = (716 - TAPE_WIN - 24) // 2
    im.alpha_composite(L('tape_%d' % (int(round(hdg / 5.0)) % 72)), ((tx + 12) * k, 12 * k)); im.alpha_composite(L('tape_frame'), (tx * k, 0))
    d = ImageDraw.Draw(im)
    d.text(((tx + 12 + TAPE_WIN / 2) * k, (TAPE_H + 41) * k), '%03d' % hdg, font=font(19 * k), fill=AMBER + (255,), anchor='mm')
    f = font(17 * k)
    if pilot:
        d.text(((GX[0] + G / 2) * k, oy + (GY + G / 2 - 24) * k), str(spd), font=f, fill=PHOS + (255,), anchor='mm')
        d.text(((RKX + 70) * k, oy + 23 * k), 'RKT 22', font=f, fill=PHOS + (255,), anchor='mm')
    d.text(((GX[2] + G / 2) * k, oy + (GY + G / 2 - 24) * k), str(alt), font=f, fill=PHOS + (255,), anchor='mm')
    im.convert('RGB').save(path)


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    out = args[0] if args else os.path.join(HERE, '..', 'out', 'addon')
    h, xp, cp = build(out, art='--no-art' not in argv)
    D = os.path.join(out, 'panorama/images/custom_game/mv')
    xml = open(xp, encoding='utf-8').read(); css = open(cp, encoding='utf-8').read()
    n_ids = len(re.findall(r'id="', xml))
    bad = []
    if n_ids > 400: bad.append('%d panel ids (budget 400, CS2 limit 1024)' % n_ids)
    for u in sorted(set(re.findall(r'custom_game/mv/([\w.]+)', css))):          # a css url with no picture kills the whole layout in CS2
        if not os.path.exists(os.path.join(D, u)): bad.append('css names a missing picture: ' + u + ('  (run render_board.py)' if u.startswith('board') else ''))
    for u in sorted(set(re.findall(r'\{images\}/(map_icons/[^"]+)', css))):
        if not os.path.exists(os.path.join(out, 'panorama/images', u)): bad.append('preload names a missing file (run render_board.py first): ' + u)
    prob, con = check_contract(xp, cp)
    bad += prob
    hp = write_hud_json(con, n_ids)
    od = os.path.join(HERE, '..', 'out'); os.makedirs(os.path.join(od, 'hud'), exist_ok=True)
    sp = os.path.join(od, 'hud_states.json'); json.dump(states(), open(sp, 'w'), indent=1)
    fly_preview(D, os.path.join(od, 'hud', 'fly_preview.png'))
    fly_preview(D, os.path.join(od, 'hud', 'fly_preview_2.png'), roll=-25, pitch=12, spd=20, alt=45, vsi=-6, hdg=200, hp=17)
    fly_preview(D, os.path.join(od, 'hud', 'fly_preview_gunner.png'), roll=-10, pitch=4, alt=45, hdg=200, hp=17, pilot=False)
    print('hud: %d panel ids (contract: %s), %d pictures, %s' % (n_ids, len(con) if con else 'not found', len(os.listdir(D)), hp))
    for b in bad: print('HUD:', b)
    rc = 0
    if '--no-check' not in argv:
        rc = subprocess.call([sys.executable, '-I', os.path.join(HERE, 'hud_check.py'), '--addon', out, '--name', NAME, '--states', sp,
                              '--out', os.path.join(od, 'hud', 'hud')])
    sys.exit(1 if (bad or rc) else 0)


if __name__ == '__main__':
    main(sys.argv[1:])
