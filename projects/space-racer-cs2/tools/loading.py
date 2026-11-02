"""Loading screen slides, radar (overview) image, overview file and map icon for the map.
  panorama/images/map_icons/screenshots/1080p/<map>.png, <map>_1.png ...   loading screen slides
  panorama/images/overheadmaps/<map>_radar.psd             radar / overview
  panorama/images/map_icons/map_icon_<map>.svg             map icon
  resource/overviews/<map>.txt                             where the radar sits in the world (copy into the GAME addon folder)
usage: loading.py <addon_out_dir> <map name> [preview_dir]
  preview_dir gets loading.png (the first slide), loading_all.png (all of them) and loading_cs2.png (the first slide
  with CS2's column and loading bar sketched on, and where 4:3 and 21:9 screens cut it)

CS2's loading screen (panorama/scripts/loadingscreen.vts) shows <map>.png and <map>_1.png ... <map>_9.png as a
slideshow, 4 seconds each, starting on a random one - and shows nothing at all when there is only one picture. Over
the slides it draws its own column on the right (map name, icon, mode; 300 px wide, 20 px from the edge, the slide
blurred behind it) and the loading bar. A slide is scaled to cover the screen, so a 4:3 screen loses 240 px on each
side and an ultrawide one some of the top and bottom.

So every slide keeps the same frame: the logo and a CONTROLS panel (keys and chat commands) in the same place,
inside x 252-1348 - clear of CS2's column at 16:9 and 16:10 and not cut off at 4:3 - and a second panel below it
that changes from slide to slide: the cars, the tracks, how to win, what is on the track. All of it sits in
y 104-948, which an ultrawide (21:9) screen still shows. The background is a different track's sky on each slide.
hud.py makes CS2 compile the slides (SprPre rules)."""
import os, sys, json, math, struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__))
import pixfont, skies
from retro import *
import retro
from theme import NEON, DEPTH, TITLE, defs
RTHEMES, RDEFS = defs().THEMES, defs().TRACKS

OUT, MAP = sys.argv[1], sys.argv[2]
PREVIEW = sys.argv[3] if len(sys.argv) > 3 else None
FONT_B = '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf'
FONT_R = '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf'
def font(sz, bold=True): return ImageFont.truetype(FONT_B if bold else FONT_R, sz)
tracks = json.load(open(os.path.join(OUT, '_gen/tracks.json')))
THEME = {k: tuple(v['rail']) for k, v in RTHEMES.items()}

def text(d, xy, s, f, fill=(255, 255, 255), anchor='la', stroke=3):
    d.text(xy, s, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=(0, 0, 0))

def track_outline(T, size, color, width=4):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ext = T['ext']; sc = (size / 2 - 2) / ext
    road = T.get('road', [1] * T['n'])
    pts = [(size / 2 + x * sc, size / 2 - y * sc) for x, y in zip(T['x'], T['y'])]
    for i in range(T['n']):
        if not road[i]: continue
        a, b = pts[i], pts[(i + 1) % T['n']]
        d.line([a, b], fill=color + (255,), width=width)
    return img

# ---------------------------------------------------------------- loading screen slides
W, H = 1920, 1080
LW, LH = W // 4, H // 4                 # drawn at 480 x 270, blown up 4x like everything else
X0, X1 = 252, 1348                      # the safe band: clear of CS2's column at 16:9, not cut off at 4:3
CX = (X0 + X1) // 2
HZ = 128                                # horizon row at 1x
S3 = 24                                 # one character of the scale-3 pixel font

# the frame on every slide
DRIVE = [('W / S', 'GAS / BRAKE'), ('A / D', 'STEER'), ('MOUSE 1', 'BOOST'), ('MOUSE 2', 'SPIN ATTACK'), ('SPACE', 'DRIFT'), ('E', 'CAR ABILITY')]
CHAT = [('R / !CAR', 'CAR PICKER'), ('!CAR 1-4', 'QUICK PICK'), ('!CAM', 'CAMERA VIEW'), ('!SHADE', 'YOUR COLOUR'),
        ('!VOTE', 'NEXT TRACK'), ('!HELP', 'ALL CONTROLS')]
WATCH = 'WATCHING: MOUSE 1/2 NEXT CAR, E NEXT ARENA'
LOGO_Y = 104                             # the logo picture's top (its letters start 28 px lower)
CTRL_Y0, CTRL_Y1 = 248, 588              # the controls panel
FEAT_Y0, FEAT_Y1 = 604, 948              # the panel that changes

# the slides: what the second panel shows, and whose sky is behind it (slide 0 is <map>.png, then <map>_1.png ...)
SLIDES = [('cars', 'oval'), ('tracks', 'crosswire'), ('win', 'spire'), ('track', 'skyway')]
if NEON: SLIDES = [('cars', 'grid'), ('tracks', 'voidhop'), ('win', 'pulse'), ('track', 'dive')]
if DEPTH: SLIDES = [('cars', 'kelp'), ('tracks', 'abyss'), ('win', 'coral'), ('track', 'wreck')]

CARS = [('hornet', 'HORNET', 'DRIFT CHARGE', ['LIGHT AND SHARP', 'E: SEEKER BOLT']),
        ('meteor', 'METEOR', 'RAM', ['BUMPS HURT THEM', 'E: SHOCKWAVE']),
        ('comet', 'COMET', 'AFTERBURN', ['BIGGEST BOOST', 'E: NOVA BURN']),
        ('bastion', 'BASTION', 'SLIPSTREAM', ['TOUGHEST SHIELD', 'E: AEGIS'])]
TRACK_TAGS = {'oval': 'FLAT OUT', 'hairpin': 'THREE HAIRPINS', 'crosswire': 'SPIRAL LOOP', 'nullgap': 'NO RAILS',
              'spire': 'CLIMB AND DIVE', 'ringworld': 'OVER AND UNDER', 'skyway': 'BIG JUMPS', 'helix': 'CORKSCREW'}
TRACK_TAGS.update({'grid': 'FLAT OUT', 'pulse': 'TWO HAIRPINS', 'voidhop': 'FLY THE GAP', 'stream': 'ROLLERCOASTER',
                   'dive': 'FLY DOWN', 'overclock': 'OVER AND UNDER'})
TRACK_TAGS.update({'kelp': 'SERPENT JUMP', 'coral': 'MANTA GLIDE', 'wreck': 'THROUGH THE HULL', 'vents': 'WHALE CROSSING',
                   'abyss': 'GLIDE THE TRENCH', 'lantern': 'NO RAILS'})


def background(theme_id, seed):
    """the track's own sky (the one the race uses), turned so its planet sits beside the panels, over a neon floor"""
    k = [t['id'] for t in RDEFS].index(theme_id)        # (a track id; in Space Racer each track's theme has its id)
    th = RTHEMES[RDEFS[k]['theme']]
    sky = skies.make_sky(RDEFS[k]['theme'], th, RDEFS[k]['scenery'], k + 5)[::4, ::4]
    px, py, pr = skies.LAST_PLANET
    want = 372                                          # the planet's x at 1x: right of the panels (x 1488)
    sky = np.roll(sky, want - px, axis=1)[:, :LW]
    canvas = np.zeros((LH, LW, 3), np.uint8)
    canvas[:HZ] = sky[skies.H // 2 - HZ:skies.H // 2]
    fl = th.get('floor', MAGENTA)
    if DEPTH: return up(seabed(canvas, fl, seed), 4).copy()
    for y in range(HZ, LH):
        k_ = (y - HZ) / (LH - HZ)
        canvas[y] = (np.array(BLACK) * (1 - k_) + np.array(INK) * k_).astype(np.uint8)
    for j in range(1, 16):                              # cross lines bunching towards the horizon
        y = HZ + int((LH - HZ) * (j / 15) ** 2.2)
        if y < LH: canvas[y] = fl if j > 2 else shade(fl, 0.55)
    vx = CX // 4
    for i in range(-34, 35):                            # lines running to the vanishing point
        x_top, x_bot = vx + i * 8, vx + i * 70
        for y in range(HZ + 1, LH):
            k_ = (y - HZ) / (LH - HZ)
            x = int(round(x_top + (x_bot - x_top) * k_))
            if 0 <= x < LW: canvas[y, x] = fl if k_ > 0.12 else shade(fl, 0.55)
    return up(canvas, 4).copy()


def seabed(canvas, fl, seed):
    """Depth Racer: a sandy sea floor fading into the murk instead of the neon grid - rippled sand bunching towards
    the horizon, faint glowing specks and a few dark rocks"""
    rng = np.random.default_rng(seed + 11)
    murk, sand = np.array((8, 40, 56), float), np.array((40, 44, 52), float)
    for y in range(HZ, LH):
        k_ = ((y - HZ) / (LH - HZ)) ** 0.7
        canvas[y] = (murk * (1 - k_) + sand * k_).astype(np.uint8)
    xs = np.arange(LW)
    for j in range(1, 22):                              # sand ripples, wavy, closer together further away
        k_ = (j / 21) ** 2.0
        y0 = HZ + (LH - HZ) * k_
        ys = (y0 + np.sin(xs / (6 + 30 * k_) + j * 1.7) * (1 + 4 * k_)).astype(int)
        col = np.array(shade(fl, 0.18 + 0.3 * k_), np.uint8)
        ok = (ys > HZ) & (ys < LH)
        canvas[ys[ok], xs[ok]] = col
    for _ in range(26):                                 # rocks
        k_ = rng.uniform(0.15, 1.0) ** 1.5
        cy, cx = int(HZ + (LH - HZ) * k_), int(rng.uniform(0, LW))
        r = max(1, int((2 + 10 * k_) * rng.uniform(0.6, 1.2)))
        for dy in range(-r, 1):
            w = int(r * 1.6 * (1 - (dy / r) ** 2) ** 0.5)
            yy = cy + dy
            if HZ < yy < LH: canvas[yy, max(0, cx - w):min(LW, cx + w)] = (10, 18, 26) if dy > -r // 2 else (18, 30, 40)
    for _ in range(140):                                # glowing specks drifting over the floor
        y, x = int(rng.uniform(HZ + 2, LH)), int(rng.uniform(0, LW))
        canvas[y, x] = shade(fl, rng.uniform(0.5, 1.0))
    return canvas


def panel(big, x0, y0, x1, y1, edge, dark=0.13):
    """a dark glass panel with a 4-pixel neon edge and a darker line inside it"""
    big[y0:y1, x0:x1] = (big[y0:y1, x0:x1] * dark).astype(np.uint8)
    for (a, b, c, d) in ((y0, y0 + 4, x0, x1), (y1 - 4, y1, x0, x1), (y0, y1, x0, x0 + 4), (y0, y1, x1 - 4, x1)):
        big[a:b, c:d] = edge
    sh = shade(edge, 0.35)
    for (a, b, c, d) in ((y0 + 4, y0 + 8, x0 + 4, x1 - 4), (y1 - 8, y1 - 4, x0 + 4, x1 - 4),
                         (y0 + 4, y1 - 4, x0 + 4, x0 + 8), (y0 + 4, y1 - 4, x1 - 8, x1 - 4)):
        big[a:b, c:d] = sh


def heading(big, x, y, s, color, shadow, align='center'):
    pixfont.draw(big, x, y, s, 4, color, shadow=shadow, align=align)


def frame(big):
    """the part that is the same on every slide: logo, strap line, the controls panel"""
    lg = pixfont.logo(TITLE, 7)
    pixfont.paste(big, lg, CX - lg.shape[1] // 2, LOGO_Y)
    pixfont.draw(big, CX, LOGO_Y + 96, '32-CAR ANTI-GRAV RACING', 3, ICE, shadow=PURPLE, align='center')
    panel(big, X0, CTRL_Y0, X1, CTRL_Y1, TEAL)
    lx, rx = X0 + 28, CX + 8                            # the two columns
    heading(big, lx, CTRL_Y0 + 20, 'DRIVE', GOLD, RUST, 'left')
    heading(big, rx, CTRL_Y0 + 20, 'CHAT (! OR /)', PINK, PURPLE, 'left')
    big[CTRL_Y0 + 20:CTRL_Y1 - 72, CX - 4:CX] = DEEPTEAL      # a line between the columns
    y = CTRL_Y0 + 68
    for i in range(max(len(DRIVE), len(CHAT))):
        if i < len(DRIVE):
            k, v = DRIVE[i]
            pixfont.draw(big, lx, y, k, 3, GOLD); pixfont.draw(big, lx + 9 * S3, y, v, 3, WHITE)
        if i < len(CHAT):
            k, v = CHAT[i]
            pixfont.draw(big, rx, y, k, 3, PINK); pixfont.draw(big, rx + 9 * S3, y, v, 3, WHITE)
        y += 36
    big[CTRL_Y1 - 60:CTRL_Y1 - 56, X0 + 24:X1 - 24] = DEEPTEAL
    pixfont.draw(big, CX, CTRL_Y1 - 44, WATCH, 3, ICE, align='center')


def pixel_car(key, px):
    """the car's big render, shrunk to px at 1x, put in the palette and outlined, then blown up 4x"""
    p = os.path.join(OUT, '_gen', 'big_%s.png' % key)
    im = np.array(Image.open(p).convert('RGBA').resize((px, px), Image.BILINEAR))
    q = quantize_rgba(im, 12)
    a = q[..., 3] > 0; o = np.zeros_like(a)
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)): o |= np.roll(np.roll(a, dy, 0), dx, 1)
    q[o & ~a] = (0, 0, 0, 255)
    ys, xs = np.where(q[..., 3] > 0)                    # just the car, no empty margin
    return up(q[ys.min():ys.max() + 1, xs.min():xs.max() + 1], 4)


def feat_cars(big, edge):
    heading(big, CX, FEAT_Y0 + 20, 'FOUR CARS - PERK AND E ABILITY', GOLD, RUST)
    cw = (X1 - X0) // 4
    for i, (key, name, perk, lines) in enumerate(CARS):
        cx = X0 + cw * i + cw // 2
        spr = pixel_car(key, 50)
        pixfont.paste(big, spr, cx - spr.shape[1] // 2, FEAT_Y0 + 196 - spr.shape[0])     # cars stand on one line
        y = FEAT_Y0 + 210
        pixfont.draw(big, cx, y, name, 4, WHITE, shadow=PURPLE, align='center')
        pixfont.draw(big, cx, y + 42, perk, 2, GOLD, align='center')
        for j, ln in enumerate(lines):
            pixfont.draw(big, cx, y + 68 + j * 22, ln, 2, PINK if ln.startswith('E:') else PALE, align='center')


def feat_tracks(big, edge):
    heading(big, CX, FEAT_Y0 + 20, '%s TRACKS - 2 OR 3 LAPS' % ['', 'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT'][len(RDEFS)], GOLD, RUST)
    cw = (X1 - X0) // 4
    for i, T in enumerate(tracks):
        th = RTHEMES[T['theme']]
        cx = X0 + cw * (i % 4) + cw // 2
        y = FEAT_Y0 + 62 + (i // 4) * 138
        im = track_outline(T, 23, tuple(th['rail']), 1)
        a = np.array(im); a[..., 3] = np.where(a[..., 3] > 90, 255, 0)
        a = up(a, 4)
        pixfont.paste(big, a, cx - a.shape[1] // 2, y)
        pixfont.draw(big, cx, y + 96, T['title'], 2, WHITE, align='center')
        pixfont.draw(big, cx, y + 116, TRACK_TAGS.get(T['id'], ''), 2, tuple(th['line']), align='center')


def feat_win(big, edge):
    heading(big, CX, FEAT_Y0 + 20, 'HOW TO WIN', GOLD, RUST)
    rows = [('THE TOP 3 TAKE THE KILLS', 3, ICE), ('1ST 50%   2ND 30%   3RD 20%', 4, GOLD), (None, 0, None),
            ('WRECK A CAR AND THAT KILL IS YOURS', 3, WHITE), (None, 0, None),
            ('MOST OF YOUR SIDE IN THE TOP 8', 3, LIME), ('WINS THE ROUND FOR T OR CT', 3, LIME), (None, 0, None),
            ('DRAFT BEHIND A CAR TO FILL YOUR CHARGE', 3, PINK)]
    y = FEAT_Y0 + 72
    for s, sc, col in rows:
        if s is None: y += 14; continue
        pixfont.draw(big, CX, y, s, sc, col, align='center')
        y += 12 + 8 * sc


def icon(kind):
    """little 16 x 12 pictures of what is on the track (1x; blown up 4x)"""
    g = np.zeros((12, 16, 4), np.uint8)
    def put(y, x, c):
        if 0 <= y < 12 and 0 <= x < 16: g[y, x] = tuple(c) + (255,)
    if kind == 'boost':                                  # road tile with gold chevrons pointing ahead (up)
        g[:, 2:14] = tuple(INK) + (255,)
        for k in (1, 6):
            for d in range(5):
                put(k + d + 1, 7 - d, ORANGE); put(k + d + 1, 8 + d, ORANGE)
                put(k + d, 7 - d, GOLD); put(k + d, 8 + d, GOLD)
    elif kind == 'charge':                               # a glowing panel with a plus
        g[1:11, 1:15] = tuple(DEEPTEAL) + (255,)
        g[2:10, 2:14] = tuple(TEAL) + (255,)
        g[5:7, 4:12] = tuple(MINT) + (255,); g[2:10, 7:9] = tuple(MINT) + (255,)
    elif kind == 'ramp':                                 # a striped wedge, seen from the side
        for x in range(16):
            h = int(x * 0.6) + 1
            for y in range(11 - h, 12):
                put(y, x, GOLD if ((x + y) // 2) % 2 else INK)
            put(11 - h, x, CREAM)
    elif kind == 'slick':                                # purple and pink waves
        for row, col in ((2, PINK), (6, MAGENTA), (10, PURPLE)):
            for x in range(16):
                put(row + int(round(math.sin(x / 16 * 2 * math.pi * 2) * 1.4)), x, col)
    elif kind == 'pulse':                                # the laser fence with chevrons under it
        for x in range(1, 16, 3):
            for y in range(1, 8): put(y, x, PINK if y % 2 else MAGENTA)
        g[3, :] = tuple(PINK) + (255,)
        for d in range(4):
            put(8 + d, 7 - d, ICE); put(8 + d, 8 + d, ICE)
    elif kind == 'fly':                                  # a gate ring with a car going through it, nose up
        for a in range(48):
            t = a / 48 * 2 * math.pi
            put(int(round(5.5 + 5 * math.sin(t))), int(round(7.5 + 6 * math.cos(t))), SKYBLUE if a % 6 < 3 else ICE)
        for x, y in ((5, 8), (6, 7), (7, 7), (8, 6), (9, 6), (10, 5)): put(y, x, GOLD); put(y + 1, x, ORANGE)
        put(4, 11, WHITE)
    elif kind == 'creature':                             # a sea serpent's coils breaking the water
        for x in range(16):
            y = int(round(6 + 3.2 * math.sin(x / 16 * 2 * math.pi * 1.5)))
            put(y, x, TEAL); put(y + 1, x, DEEPTEAL)
            if x % 4 == 1: put(y - 1, x, MINT)
        put(int(round(6 + 3.2 * math.sin(15 / 16 * 2 * math.pi * 1.5))) - 1, 15, GOLD)
    elif kind == 'shield':                               # the shield bar running out
        g[3:9, 0:16] = tuple(BLACK) + (255,)
        for s in range(5):
            x = 1 + s * 3
            g[4:8, x:x + 2] = tuple(RED if s == 0 else (INK if s > 1 else SALMON)) + (255,)
    return up(g, 4)


def feat_track(big, edge):
    heading(big, CX, FEAT_Y0 + 20, 'ON THE TRACK', GOLD, RUST)
    items = [('boost', 'GOLD PADS', 'FREE SPEED', GOLD), ('charge', 'CYAN PADS', 'CHARGE + SHIELD', MINT),
             ('ramp', 'RAMPS', 'HIT THEM FAST', CREAM), ('slick', 'PURPLE WAVES', 'LOW GRIP', PINK),
             ('pulse', 'THE PULSE', 'CATCH-UP CHARGE', PINK), ('shield', 'SHIELD AT 0', 'WRECKED', SALMON)]
    if DEPTH:     # glides, rings and the sea creatures
        items = [('boost', 'GOLD PADS/RINGS', 'FREE SPEED', GOLD), ('charge', 'CYAN PADS/RINGS', 'CHARGE + SHIELD', MINT),
                 ('fly', 'GLIDE: W DOWN S UP', 'SWIM THE GATES', ICE), ('creature', 'SEA CREATURES', 'TIME YOUR RUN', TEAL),
                 ('ramp', 'RAMPS', 'HIT THEM FAST', CREAM), ('shield', 'SHIELD AT 0', 'WRECKED', SALMON)]
    elif NEON:    # flight sections: W / S fly up and down there; the rings work like the pads
        items = [('boost', 'GOLD PADS/RINGS', 'FREE SPEED', GOLD), ('charge', 'CYAN PADS/RINGS', 'CHARGE + SHIELD', MINT),
                 ('fly', 'FLIGHT: W DOWN S UP', 'FLY THE GATES', ICE), ('ramp', 'RAMPS', 'HIT THEM FAST', CREAM),
                 ('slick', 'PURPLE WAVES', 'LOW GRIP', PINK), ('shield', 'SHIELD AT 0', 'WRECKED', SALMON)]
    colw = (X1 - X0) // 2
    for i, (kind, title, desc, col) in enumerate(items):
        x = X0 + 44 + (i % 2) * colw
        y = FEAT_Y0 + 76 + (i // 2) * 88
        ic = icon(kind)
        pixfont.paste(big, ic, x, y)
        pixfont.draw(big, x + 88, y - 2, title, 3, col)
        pixfont.draw(big, x + 88, y + 30, desc, 3, WHITE)


FEATURES = {'cars': feat_cars, 'tracks': feat_tracks, 'win': feat_win, 'track': feat_track}


def slide(kind, theme_id, n):
    big = background(theme_id, n)
    frame(big)
    edge = tuple(RTHEMES[[t for t in RDEFS if t['id'] == theme_id][0]['theme']]['rail'])
    panel(big, X0, FEAT_Y0, X1, FEAT_Y1, edge)
    FEATURES[kind](big, edge)
    # which slide of how many: little dots under the panels
    for i in range(len(SLIDES)):
        x = CX - (len(SLIDES) * 28) // 2 + i * 28 + 6
        big[FEAT_Y1 + 16:FEAT_Y1 + 32, x:x + 16] = edge if i == n else INK
        if i != n: big[FEAT_Y1 + 20:FEAT_Y1 + 28, x + 4:x + 12] = MAUVE
    return retro.scanlines(big, 4, 0.82)


def cs2_overlay(img):
    """the slide as CS2 shows it at 16:9 (its column and loading bar sketched in), plus where 4:3 and 21:9 cut"""
    im = Image.fromarray(img).convert('RGB')
    d = ImageDraw.Draw(im, 'RGBA')
    d.rectangle([1600, 50, 1899, 1059], fill=(0, 0, 0, 150), outline=(255, 255, 255, 120))
    text(d, (1750, 120), 'CS2: MAP NAME', font(22), (230, 230, 230), anchor='mm')
    text(d, (1750, 150), 'ICON, MODE', font(18), (200, 200, 200), anchor='mm')
    d.rectangle([1620, 1020, 1879, 1027], fill=(30, 150, 210, 230))
    text(d, (1622, 996), 'LOADING...', font(18), (200, 200, 200))
    for x in (240, 1680):
        d.line([(x, 0), (x, 1079)], fill=(255, 80, 80, 220), width=3)
    text(d, (246, 1048), '4:3 edge', font(20), (255, 120, 120))
    d.line([(1360, 0), (1360, 1079)], fill=(255, 160, 60, 160), width=2)
    text(d, (1366, 1048), "4:3: CS2's column from here", font(18), (255, 170, 80))
    for y in (128, 952):
        d.line([(0, y), (1919, y)], fill=(80, 200, 255, 200), width=3)
    text(d, (8, 132), '21:9 edge', font(20), (120, 210, 255))
    return im


def loading_slides():
    path = os.path.join(OUT, 'panorama/images/map_icons/screenshots/1080p'); os.makedirs(path, exist_ok=True)
    for f in os.listdir(path):                          # no stale extra slides from an older build
        if f.startswith(MAP) and f.endswith('.png'): os.remove(os.path.join(path, f))
    names = []
    for n, (kind, theme_id) in enumerate(SLIDES):
        img = slide(kind, theme_id, n)
        name = MAP + ('_%d' % n if n else '') + '.png'
        Image.fromarray(img).save(os.path.join(path, name), optimize=True)
        names.append(name)
        if PREVIEW and n == 0:
            Image.fromarray(img).save(os.path.join(PREVIEW, 'loading.png'), optimize=True)
            cs2_overlay(img).save(os.path.join(PREVIEW, 'loading_cs2.png'), optimize=True)
    # each slide must be compiled with the map: hud.py's never-shown SprPre rules point at them
    css = ''
    cdir = os.path.join(OUT, 'panorama/styles/custom_game')
    for f in os.listdir(cdir) if os.path.isdir(cdir) else []:
        if f.endswith('.css'): css += open(os.path.join(cdir, f)).read()
    missing = [n for n in names if 'screenshots/1080p/' + n not in css]
    assert not missing, 'loading slides the HUD css does not reference (raise LOADING_SLIDES in hud.py): %s' % missing
    if PREVIEW:
        # all the slides on one sheet
        sheet = Image.new('RGB', (W, H), (0, 0, 0))
        for n, name in enumerate(names):
            im = Image.open(os.path.join(path, name)).resize((W // 2, H // 2), Image.LANCZOS)
            sheet.paste(im, ((n % 2) * W // 2, (n // 2) * H // 2))
        sheet.save(os.path.join(PREVIEW, 'loading_all.png'), optimize=True)
    return names

# ---------------------------------------------------------------- radar
def write_psd(path, img):
    arr = np.array(img.convert('RGB')); h, w = arr.shape[:2]
    with open(path, 'wb') as f:
        f.write(b'8BPS' + struct.pack('>H6xHIIHH', 1, 3, h, w, 8, 3))
        f.write(struct.pack('>I', 0)); f.write(struct.pack('>I', 0)); f.write(struct.pack('>I', 0)); f.write(struct.pack('>H', 0))
        for c in range(3): f.write(arr[..., c].tobytes())

def radar():
    xs, ys = [], []
    for T in tracks:
        o = T['off']; xs += [o[0] - T['ext'], o[0] + T['ext']]; ys += [o[1] - T['ext'], o[1] + T['ext']]
    m = 300
    minx, maxx, miny, maxy = min(xs) - m, max(xs) + m, min(ys) - m, max(ys) + m
    size = max(maxx - minx, maxy - miny)
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    pos_x, pos_y = cx - size / 2, cy + size / 2
    R = 1024; scale = size / R; S = 2
    img = Image.new('RGB', (R * S, R * S), (6, 8, 18))
    d = ImageDraw.Draw(img)
    px = lambda x, y: ((x - pos_x) / scale * S, (pos_y - y) / scale * S)
    for T in tracks:
        o = T['off']; col = THEME.get(T['theme'], (255, 255, 255)); road = T.get('road', [1] * T['n'])
        w = max(2, int(T['hw'][0] * 2 / scale * S * 0.8))
        for i in range(T['n']):
            if not road[i]: continue
            j = (i + 1) % T['n']
            d.line([px(o[0] + T['x'][i], o[1] + T['y'][i]), px(o[0] + T['x'][j], o[1] + T['y'][j])], fill=tuple(int(c * 0.5) for c in col), width=w)
            d.line([px(o[0] + T['x'][i], o[1] + T['y'][i]), px(o[0] + T['x'][j], o[1] + T['y'][j])], fill=col, width=S * 2)
    img = img.resize((R, R), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    # the two layers share the same four squares: label each square with both names
    quads = {}
    for T in tracks: quads.setdefault((T['off'][0], T['off'][1]), []).append(T['title'])
    for (ox, oy), names in quads.items():
        x, y = px(ox, oy)
        for k, nm in enumerate(names):
            text(d, (x / S, y / S - 14 + k * 30), nm, font(22), (255, 255, 255), anchor='mm', stroke=3)
    path = os.path.join(OUT, 'panorama/images/overheadmaps'); os.makedirs(path, exist_ok=True)
    write_psd(os.path.join(path, MAP + '_radar.psd'), img)
    img.save(os.path.join(OUT, '_gen', 'radar_preview.png'))
    ov = os.path.join(OUT, 'resource/overviews'); os.makedirs(ov, exist_ok=True)
    open(os.path.join(ov, MAP + '.txt'), 'w', newline='\n').write(
        '"%s"\n{\n\t"material"\t"overviews/%s"\n\t"pos_x"\t"%d"\n\t"pos_y"\t"%d"\n\t"scale"\t"%.3f"\n\t"rotate"\t"0"\n\t"zoom"\t"1.0"\n}\n'
        % (MAP, MAP, round(pos_x), round(pos_y), scale))
    return pos_x, pos_y, scale

def map_icon():
    # a white chevron-arrow racer silhouette, like the stock map icons
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
           '<path fill="#ffffff" d="M32 4 L52 50 L40 44 L32 58 L24 44 L12 50 Z"/>'
           '<path fill="#000000" fill-opacity="0.35" d="M32 18 L42 42 L32 37 L22 42 Z"/></svg>\n')
    path = os.path.join(OUT, 'panorama/images/map_icons'); os.makedirs(path, exist_ok=True)
    open(os.path.join(path, 'map_icon_%s.svg' % MAP), 'w', newline='\n').write(svg)

names = loading_slides()
p = radar()
map_icon()
print('loading screen: %d slides (%s), radar (pos %.0f, %.0f, scale %.2f), icon' % ((len(names), ' '.join(names)) + p))
