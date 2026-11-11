"""The artillery board picture, the loading-screen slides and the map icon for mg_monsoon, all drawn from tools/layout.py
through make_radar.py's renderers.

usage: render_board.py [<addon content out>] [--no-slides] [--no-board]         default ../out/addon
  writes <addon>/panorama/images/custom_game/mv/board.png        the plotting-table map (printed 1:25 000 look), 1280 px for a
                                                                 640 px panel: the square x, y in [-6400, 6400], NORTH UP,
                                                                 16 x 16 lettered grid = 10 reticle steps per square
         <addon>/panorama/images/custom_game/mv/board_t.png, board_ct.png   the same map turned so the enemy base is at the
                                                                 top (not used by the HUD yet: docs/SCRIPT.md's HUD contract
                                                                 positions markers north-up for both teams; see docs/HUD.md)
         <addon>/panorama/images/map_icons/screenshots/1080p/mg_monsoon.png, _1.png, _2.png    loading slides (1920 x 1080)
         <addon>/panorama/images/map_icons/map_icon_mg_monsoon.svg
         ../out/board.json    {ext, steps, px, grid}: what the HUD generator and the script agree on
         ../out/slides/*.png  the slides with CS2's loading column and the 4:3 / 21:9 edges drawn on (loading.py overlay)

The board's step grid (docs/SCRIPT.md "HUD contract"): step x = floor((worldX + 6400) / 12800 * 160) left to right,
step y = floor((6400 - worldY) / 12800 * 160) top to bottom. mv_hud.py places step k at (k + 0.5) * 640 / 160 px.
"""
import os, sys, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layout as LY
import make_radar as R
import loading

MAP = 'mg_monsoon'
BOARD_EXT = 6400.0
BOARD_STEPS = 160
BOARD_PX = 640              # size of the map on the HUD (px at 1080 high): 4 px per reticle step (mv_hud.py BOARD_PX)
BOARD_TEX = 1280            # texture size
font = R.font


def board(out):
    d = os.path.join(out, 'panorama/images/custom_game/mv'); os.makedirs(d, exist_ok=True)
    v = R.View(-BOARD_EXT, BOARD_EXT, 2 * BOARD_EXT / BOARD_TEX, BOARD_TEX, BOARD_TEX)
    im = R.render_topo(v, ss=2, label_scale=1.75, age=0.8)
    # a touch darker and lower in contrast than a slide: the markers and read-outs are what must stand out
    a = np.asarray(im, np.float32) / 255.0
    a = (a - 0.5) * 0.88 + 0.47
    im = Image.fromarray((a.clip(0, 1) * 255).astype(np.uint8))
    im.save(os.path.join(d, 'board.png'), optimize=True)
    # enemy-at-the-top variants: T looks south-east (the firebase), CT north-west (the camp): a half turn apart
    for team, rot in (('ct', 0), ('t', 180)):
        im.rotate(rot).save(os.path.join(d, 'board_%s.png' % team), optimize=True)
    json.dump(dict(ext=BOARD_EXT, steps=BOARD_STEPS, px=BOARD_PX, tex=BOARD_TEX, grid=16, north_up=True),
              open(os.path.join(HERE, '..', 'out', 'board.json'), 'w'))
    # self-check: every flag and both batteries are on the step grid, and two neighbouring flags are not on the same step
    seen = {}
    for l, name, (fx, fy) in LY.FLAGS:
        sx = int((fx + BOARD_EXT) / (2 * BOARD_EXT) * BOARD_STEPS); sy = int((BOARD_EXT - fy) / (2 * BOARD_EXT) * BOARD_STEPS)
        assert 0 <= sx < BOARD_STEPS and 0 <= sy < BOARD_STEPS, l
        assert (sx, sy) not in seen, 'flags %s and %s share a board step' % (l, seen[(sx, sy)])
        seen[(sx, sy)] = l
    for g in LY.firebase()['guns'] + LY.camp()['rockets']:
        assert abs(g[0]) < BOARD_EXT and abs(g[1]) < BOARD_EXT, 'a gun is off the board'
    print('board: %d px map (%d steps of %.2f px shown at %d px) -> %s' % (BOARD_TEX, BOARD_STEPS, BOARD_PX / BOARD_STEPS, BOARD_PX, d))
    return im


# ---------------------------------------------------------------- loading slides
def grease(img, pts, col, width, head=True, alpha=215):
    """a grease-pencil arrow through world points already in pixels: smooth curve, soft wobble, arrow head"""
    P = np.array(pts, float)
    t = np.linspace(0, 1, len(P)); tt = np.linspace(0, 1, 90)
    from scipy.interpolate import CubicSpline
    xs = CubicSpline(t, P[:, 0])(tt); ys = CubicSpline(t, P[:, 1])(tt)
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.line(list(zip(xs, ys)), fill=col + (alpha,), width=width, joint='curve')
    if head:
        dx, dy = xs[-1] - xs[-6], ys[-1] - ys[-6]; L = math.hypot(dx, dy) + 1e-6; ux, uy = dx / L, dy / L
        h = width * 3.2
        d.polygon([(xs[-1] + ux * h, ys[-1] + uy * h), (xs[-1] - uy * h * 0.75, ys[-1] + ux * h * 0.75), (xs[-1] + uy * h * 0.75, ys[-1] - ux * h * 0.75)], fill=col + (alpha,))
    # waxy texture: break the stroke up a little
    n = np.random.RandomState(5).rand(img.size[1] // 2 + 1, img.size[0] // 2 + 1)
    n = np.kron(n, np.ones((2, 2)))[:img.size[1], :img.size[0]]
    a = np.asarray(lay).copy(); a[..., 3] = (a[..., 3] * (0.72 + 0.28 * (n > 0.25))).astype(np.uint8)
    img.alpha_composite(Image.fromarray(a))


def plate(img, box, fill=(22, 26, 20, 226), edge=(196, 186, 150, 255), radius=6):
    """a dark olive caption plate with a thin cream keyline and corner ticks"""
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    x0, y0, x1, y1 = box
    sh = Image.new('RGBA', img.size, (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
    ds.rounded_rectangle((x0 + 6, y0 + 8, x1 + 6, y1 + 8), radius, fill=(0, 0, 0, 150))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(9)))
    d.rounded_rectangle(box, radius, fill=fill)
    d.rounded_rectangle((x0 + 5, y0 + 5, x1 - 5, y1 - 5), max(1, radius - 3), outline=edge[:3] + (120,), width=1)
    for (cx, cy, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([(cx + sx * 5, cy + sy * 22), (cx + sx * 5, cy + sy * 5), (cx + sx * 22, cy + sy * 5)], fill=edge, width=2)
    img.alpha_composite(lay)


def tracked(d, xy, s, f, fill, track=0.0, anchor='l'):
    """text with letter spacing; returns the width drawn"""
    ws = [f.getlength(c) for c in s]; sp = f.size * track
    W = sum(ws) + sp * (len(s) - 1)
    x = xy[0] - (W / 2 if anchor == 'm' else W if anchor == 'r' else 0)
    for c, w in zip(s, ws):
        d.text((x, xy[1]), c, font=f, fill=fill, anchor='ls'); x += w + sp
    return W


def wrap(d, xy, s, f, fill, width, lead=1.32):
    x, y = xy; line = ''
    for w in s.split():
        t = (line + ' ' + w).strip()
        if f.getlength(t) > width and line:
            d.text((x, y), line, font=f, fill=fill, anchor='ls'); y += f.size * lead; line = w
        else: line = t
    if line: d.text((x, y), line, font=f, fill=fill, anchor='ls'); y += f.size * lead
    return y


def stamp(img, xy, text, rot=-8, col=(170, 40, 30), size=30):
    f = font(size); w = int(f.getlength(text) * 1.12) + 40; h = int(size * 1.9)
    t = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(t)
    d.rectangle((3, 3, w - 4, h - 4), outline=col + (220,), width=4)
    tracked(d, (w / 2, h / 2 + size * 0.36), text, f, col + (225,), 0.06, 'm')
    n = np.random.RandomState(3).rand(h, w)
    a = np.asarray(t).copy(); a[..., 3] = (a[..., 3] * (n > 0.16)).astype(np.uint8)
    t = Image.fromarray(a).rotate(rot, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(t, (int(xy[0] - t.size[0] / 2), int(xy[1] - t.size[1] / 2)))


def table_light(im, cx=0.42, cy=0.45, strength=0.62):
    """the map lying on a table under a lamp: warm centre, falling off to dark olive at the edges"""
    a = np.asarray(im.convert('RGB'), np.float32) / 255.0
    h, w = a.shape[:2]; yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot((xx - w * cx) / (w * 0.62), (yy - h * cy) / (h * 0.78))
    k = np.clip(1.06 - strength * r ** 1.7, 0.16, 1.06)[..., None]
    a = a * k * np.array([1.0, 0.975, 0.90]) + (1 - np.clip(k, 0, 1)) * np.array([0.020, 0.030, 0.020])
    return Image.fromarray((a.clip(0, 1) * 255).astype(np.uint8)).convert('RGBA')


TITLE_F = lambda s: font(s, weight='Bold')
ROLE_TXT = [
    ('INFANTRY', (236, 226, 192), ['Stand inside a flag ring to take it.', 'Kits at every arms rack: rifle, MG, anti-tank.',
                                   'Hold USE on open ground: call a fire mission.']),
    ('ARTILLERY', (240, 176, 84), ['Sit at the plotting board, lay on a mark.', 'Fetch a round, load, fire.  Watch for SPLASH.',
                                   'Enemy guns flash on the board: hit back.']),
    ('AIR', (132, 214, 150), ['SPACE climbs, CTRL descends, mouse turns.', 'Land by a flag: riders hop out or fast-rope.',
                              'The pad repairs and re-arms the gunship.']),
]


def slide_title():
    W, H = loading.W, loading.H
    v_upp = 2 * BOARD_EXT / W                                  # the whole valley across the slide, no ground beyond the raster
    v = R.View(-BOARD_EXT, 540 * v_upp, v_upp, W, H)
    im = table_light(R.render_topo(v, ss=1, label_scale=1.7, grid_labels=False, age=1.0))
    px = v.px
    # the plan of attack in grease pencil
    B = dict((l, c) for l, n, c in LY.FLAGS)
    blue, red = (38, 84, 190), (190, 44, 34)
    grease(im, [px(*LY.pol(LY.CT_BASE, 900, 150)), px(2100, -2300), px(900, -2500), px(B['e'][0] + 420, B['e'][1] - 40)], blue, 9)
    grease(im, [px(*LY.pol(LY.CT_BASE, 900, 120)), px(3050, -900), px(2900, 200), px(B['d'][0] + 60, B['d'][1] - 430)], blue, 9)
    grease(im, [px(*LY.pol(LY.T_BASE, 800, -20)), px(-2300, 2800), px(-1300, 2650), px(B['c'][0] - 430, B['c'][1] + 30)], red, 9)
    grease(im, [px(*LY.pol(LY.T_BASE, 800, -70)), px(-3100, 1300), px(-2800, 200), px(B['a'][0] - 60, B['a'][1] + 430)], red, 9)
    c = px(*B['b']); d = ImageDraw.Draw(im)
    for r_ in (62, 70): d.ellipse([c[0] - r_, c[1] - r_ * 0.86, c[0] + r_, c[1] + r_ * 0.86], outline=(20, 20, 20, 220), width=3)
    stamp(im, (1150, 640), 'OPERATIONS MAP  1:25 000', rot=-5, size=24)
    # title plate (safe area: x 252-1348, y 104-948)
    plate(im, (268, 116, 1040, 318))
    d = ImageDraw.Draw(im)
    tracked(d, (300, 166), 'SONG MUA VALLEY  /  1968', font(22), (196, 186, 150, 255), 0.22)
    tracked(d, (298, 250), 'MONSOON VALLEY', TITLE_F(80), (240, 232, 204, 255), 0.02)
    d.line([(300, 268), (1008, 268)], fill=(196, 186, 150, 150), width=2)
    tracked(d, (300, 298), 'CONQUEST   5 FLAGS   400 TICKETS   HOLD 3 TO BLEED THE ENEMY', font(17), (160, 200, 150, 255), 0.10)
    # role strip
    x0, y0, cw = 268, 716, 352
    plate(im, (x0, y0, x0 + cw * 3 + 24, 936))
    d = ImageDraw.Draw(im)
    for i, (name, col, lines) in enumerate(ROLE_TXT):
        x = x0 + 26 + i * cw
        if i: d.line([(x - 16, y0 + 22), (x - 16, 936 - 22)], fill=(196, 186, 150, 90), width=1)
        tracked(d, (x, y0 + 50), name, TITLE_F(30), col + (255,), 0.12)
        tracked(d, (x + cw - 46, y0 + 50), '!' + name.lower(), font(16, weight='Regular'), (150, 156, 132, 255), 0.04, 'r')
        y = y0 + 84
        for ln in lines:
            d.rectangle((x, y - 9, x + 5, y - 4), fill=col + (255,))
            y = wrap(d, (x + 14, y), ln, font(17, weight='Regular'), (226, 220, 198, 255), cw - 62) + 5
    return im.convert('RGB')


def slide_flags():
    W, H = loading.W, loading.H
    upp = 2 * BOARD_EXT / W
    v = R.View(-BOARD_EXT, 540 * upp, upp, W, H)
    sat, _ = R.render_sat(v, ss=1, labels=False, grid=False, dim_outside=False, flag_badges=True, label_scale=1.9)
    a = np.asarray(sat, np.float32) / 255.0
    h, w = a.shape[:2]; yy, xx = np.mgrid[0:h, 0:w]
    # dusk grade: warm low sun from the west, haze, dark frame
    a = a * np.array([1.06, 0.98, 0.84]) + np.array([0.05, 0.035, 0.0])
    r = np.hypot((xx - w * 0.44) / (w * 0.66), (yy - h * 0.5) / (h * 0.80))
    a *= np.clip(1.08 - 0.62 * r ** 1.8, 0.14, 1.08)[..., None]
    im = Image.fromarray((a.clip(0, 1) * 255).astype(np.uint8)).convert('RGBA')
    d = ImageDraw.Draw(im); px = v.px
    for l, name, (fx, fy) in LY.FLAGS:
        c = px(fx, fy)
        up = l in ('c', 'd', 'b')
        yy_ = c[1] - 78 if up else c[1] + 92
        f = TITLE_F(26); wd = f.getlength(name.upper()) * 1.14 + 24
        lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        dl.rounded_rectangle((c[0] - wd / 2, yy_ - 28, c[0] + wd / 2, yy_ + 10), 4, fill=(18, 22, 16, 205))
        im.alpha_composite(lay); d = ImageDraw.Draw(im)
        tracked(d, (c[0], yy_), name.upper(), f, (240, 232, 204, 255), 0.10, 'm')
    for cen, name, col, dy in ((LY.CT_BASE, 'US FIREBASE', R.CT_COL, -160), (LY.T_BASE, 'PAVN CAMP', R.T_COL, 150)):
        c = px(cen[0], cen[1]); f = TITLE_F(24)
        tracked(d, (c[0] + 2, c[1] + dy + 2), name, f, (0, 0, 0, 220), 0.14, 'm'); tracked(d, (c[0], c[1] + dy), name, f, col + (255,), 0.14, 'm')
    plate(im, (268, 116, 800, 262))
    d = ImageDraw.Draw(im)
    tracked(d, (298, 196), 'FIVE FLAGS', TITLE_F(64), (240, 232, 204, 255), 0.04)
    tracked(d, (300, 236), 'HOLD THREE AND THE ENEMY BLEEDS TICKETS', font(17), (160, 200, 150, 255), 0.10)
    plate(im, (268, 838, 1316, 936))
    d = ImageDraw.Draw(im)
    x = 296
    for key, txt in (('E', 'kit rack  /  board a helicopter  /  man a gun'), ('HOLD E', 'mark a fire mission'), ('R', 'next deploy point')):
        f = TITLE_F(20); kw = f.getlength(key) + 22
        d.rounded_rectangle((x, 872, x + kw, 906), 5, outline=(240, 232, 204, 255), width=2)
        d.text((x + kw / 2, 890), key, font=f, fill=(240, 232, 204, 255), anchor='mm')
        x += kw + 12
        d.text((x, 890), txt, font=font(18, weight='Regular'), fill=(214, 208, 186, 255), anchor='lm')
        x += font(18, weight='Regular').getlength(txt) + 34
    return im.convert('RGB')


def slide_fire():
    """the fire-mission loop on a close-up of the map"""
    W, H = loading.W, loading.H
    upp = 3.6
    v = R.View(-1650 - 800 * upp + 1650, 300 + 540 * upp, upp, W, H)
    im = table_light(R.render_topo(v, ss=1, label_scale=2.6, grid_labels=False, age=1.0), cx=0.5, cy=0.5, strength=0.55)
    px = v.px; d = ImageDraw.Draw(im)
    # a plotted mission: target cross, 50 % circle, the gun-target line running off toward the firebase
    tgt = (LY.FLAGS[1][2][0] + 520, LY.FLAGS[1][2][1] + 760)
    c = px(*tgt); g = px(*LY.firebase()['guns'][0])
    red = (186, 40, 30, 235)
    d.line([c, g], fill=(30, 30, 30, 200), width=3)
    for r_ in (46, 96): d.ellipse([c[0] - r_, c[1] - r_, c[0] + r_, c[1] + r_], outline=red, width=5)
    for a_ in range(4):
        ang = a_ * math.pi / 2; d.line([(c[0] + 30 * math.cos(ang), c[1] + 30 * math.sin(ang)), (c[0] + 130 * math.cos(ang), c[1] + 130 * math.sin(ang))], fill=red, width=5)
    f = font(26); d.text((c[0] + 112, c[1] - 96), 'MSN 2   GRID %s' % grid_ref(*tgt), font=f, fill=(150, 30, 24, 255), anchor='ls')
    plate(im, (268, 116, 880, 262))
    d = ImageDraw.Draw(im)
    tracked(d, (298, 196), 'FIRE MISSION', TITLE_F(64), (240, 232, 204, 255), 0.04)
    tracked(d, (300, 236), 'THE FIELD CALLS IT.  THE BATTERY ANSWERS.', font(17), (240, 176, 84, 255), 0.10)
    steps = [('1', 'MARK', 'Infantry: hold USE on open ground beyond 10 m.'), ('2', 'LAY', 'Crew: pick the mark on the board, MOUSE1 locks.'),
             ('3', 'LOAD', 'Round from the rack to the breech. MOUSE2 picks the shell.'), ('4', 'FIRE', 'LAID and LOADED: fire. Two seconds of whistle, then SPLASH.')]
    x0, y0 = 268, 748; cw = 262
    plate(im, (x0, y0, x0 + cw * 4 + 24, 936))
    d = ImageDraw.Draw(im)
    for i, (n, name, txt) in enumerate(steps):
        x = x0 + 26 + i * cw
        d.ellipse((x, y0 + 26, x + 46, y0 + 72), outline=(240, 176, 84, 255), width=3)
        d.text((x + 23, y0 + 50), n, font=TITLE_F(28), fill=(240, 176, 84, 255), anchor='mm')
        tracked(d, (x + 60, y0 + 62), name, TITLE_F(34), (240, 232, 204, 255), 0.10)
        wrap(d, (x, y0 + 110), txt, font(17, weight='Regular'), (226, 220, 198, 255), cw - 40)
    return im.convert('RGB')


def grid_ref(x, y):
    E = BOARD_EXT; u = min(max((x + E) / (2 * E), 0), 0.9999); w = min(max((E - y) / (2 * E), 0), 0.9999)
    return chr(65 + int(u * 16)) + str(1 + int(w * 16))


ICON = ('M4 13 H60 V16 H35 V21 H40 C46 21 50 24 52 28 L61 27 L62 20 H64 V33 L52 34 C51 40 47 44 41 44 H22 C15 44 11 39 11 32 '
        'C11 25 16 21 23 21 H29 V16 H4 Z '
        'M17 26 C15 28 14 30 14 33 H26 V26 Z '            # the cockpit glass (a hole)
        'M12 50 H46 V53 H12 Z M20 44 H23 V50 H20 Z M36 44 H39 V50 H36 Z')


def slides(out):
    ims = [slide_title(), slide_flags(), slide_fire()]
    names = loading.write_slides(out, MAP, ims)
    od = os.path.join(HERE, '..', 'out', 'slides'); os.makedirs(od, exist_ok=True)
    for n, im in zip(names, ims):
        loading.cs2_overlay(im).save(os.path.join(od, n.replace('.png', '_cs2.png')))
        im.save(os.path.join(od, n))
    p = loading.write_icon(out, MAP, ICON)
    print('loading screen: %d slides (%s), icon %s' % (len(names), ' '.join(names), p))


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    out = args[0] if args else os.path.join(HERE, '..', 'out', 'addon')
    if '--no-board' not in argv: board(out)
    if '--no-slides' not in argv: slides(out)


if __name__ == '__main__':
    main(sys.argv[1:])
