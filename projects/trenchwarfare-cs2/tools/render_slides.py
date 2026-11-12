"""Loading-screen slides and the map icon for mg_trenchwarfare, drawn from the radar's own top view (tools/make_radar.py
out/radar_clean.png, which comes from tools/layout.py and the map's props) with monsoon's slide method (render_board.py:
the map on a lamp-lit table, grease-pencil plans, dark caption plates, a rubber stamp). Written through create/loading.py.

usage: render_slides.py [<addon content out>]          default ../out/addon
  writes <addon>/panorama/images/map_icons/screenshots/1080p/mg_trenchwarfare.png, _1.png, _2.png  (1920 x 1080)
         <addon>/panorama/images/map_icons/map_icon_mg_trenchwarfare.svg                         (a Brodie helmet)
         ../out/step8/slides/*.png and *_cs2.png (CS2's loading column, 4:3 and 21:9 edges drawn on: loading.py overlay)
Content stays inside CS2's safe area: x 252-1348 (4:3 cut + CS2's column), y 128-952 (21:9 cut). The HUD css preloads the
three slides and the icon (tools/tw_hud.py) so they compile with the layout."""
import os, sys, json, math, re
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layout as LY
import loading

ROOT = os.path.join(HERE, '..')
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'out', 'addon')
MAP = 'mg_trenchwarfare'
W, H = loading.W, loading.H
FONTS = {'title': 'C:/Windows/Fonts/STENCIL.TTF', 'serif': 'C:/Windows/Fonts/georgiab.ttf', 'serif_r': 'C:/Windows/Fonts/georgia.ttf',
         'sans': 'C:/Windows/Fonts/bahnschrift.ttf', 'type': 'C:/Windows/Fonts/courbd.ttf'}


def font(size, kind='sans', weight='SemiBold'):
    f = ImageFont.truetype(FONTS[kind], int(size))
    if kind == 'sans':
        try: f.set_variation_by_name(weight)
        except Exception: pass
    return f


cfg = open(os.path.join(ROOT, 'src', 'modules', '00_config.js'), encoding='utf-8').read()
STREAK = int(re.search(r'STREAK_UPGRADE:\s*(\d+)', cfg).group(1))
UNLOCK = re.findall(r'\{ name: "(\w+)", kills: (\d+), time: (\d+)', cfg)


class View:
    """a window on the world: x0 (left), y0 (top), units per slide pixel"""
    def __init__(self, x0, y0, upp):
        self.x0, self.y0, self.upp = x0, y0, upp
    def px(self, x, y): return ((x - self.x0) / self.upp, (self.y0 - y) / self.upp)


def topview(v, src='radar_clean.png'):
    """the radar master cropped to the view (padded with the wood colour beyond its square)"""
    R = Image.open(os.path.join(ROOT, 'out', src)).convert('RGB')
    rg = json.load(open(os.path.join(ROOT, 'out', 'radar_region.json')))
    k = R.size[0] / rg['span']
    x0 = (v.x0 - rg['x0']) * k; y0 = (rg['y0'] - v.y0) * k; sw = W * v.upp * k; sh = H * v.upp * k
    can = Image.new('RGB', (int(round(sw)), int(round(sh))), (40, 54, 33))
    can.paste(R, (int(round(-x0)), int(round(-y0))))
    return can.resize((W, H), Image.LANCZOS).convert('RGBA')


def table_light(im, cx=0.42, cy=0.45, strength=0.62):
    a = np.asarray(im.convert('RGB'), np.float32) / 255.0
    h, w = a.shape[:2]; yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot((xx - w * cx) / (w * 0.62), (yy - h * cy) / (h * 0.78))
    k = np.clip(1.06 - strength * r ** 1.7, 0.16, 1.06)[..., None]
    a = a * k * np.array([1.0, 0.975, 0.90]) + (1 - np.clip(k, 0, 1)) * np.array([0.020, 0.030, 0.020])
    return Image.fromarray((a.clip(0, 1) * 255).astype(np.uint8)).convert('RGBA')


def grease(img, pts, col, width, alpha=215):
    P = np.array(pts, float)
    from scipy.interpolate import CubicSpline
    t = np.linspace(0, 1, len(P)); tt = np.linspace(0, 1, 90)
    xs = CubicSpline(t, P[:, 0])(tt); ys = CubicSpline(t, P[:, 1])(tt)
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.line(list(zip(xs, ys)), fill=col + (alpha,), width=width, joint='curve')
    dx, dy = xs[-1] - xs[-6], ys[-1] - ys[-6]; L = math.hypot(dx, dy) + 1e-6; ux, uy = dx / L, dy / L; h = width * 3.2
    d.polygon([(xs[-1] + ux * h, ys[-1] + uy * h), (xs[-1] - uy * h * 0.75, ys[-1] + ux * h * 0.75), (xs[-1] + uy * h * 0.75, ys[-1] - ux * h * 0.75)], fill=col + (alpha,))
    n = np.random.RandomState(5).rand(img.size[1] // 2 + 1, img.size[0] // 2 + 1)
    n = np.kron(n, np.ones((2, 2)))[:img.size[1], :img.size[0]]
    a = np.asarray(lay).copy(); a[..., 3] = (a[..., 3] * (0.72 + 0.28 * (n > 0.25))).astype(np.uint8)
    img.alpha_composite(Image.fromarray(a))


def plate(img, box, fill=(30, 30, 22, 228), edge=(190, 158, 92, 255), radius=6):
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    x0, y0, x1, y1 = box
    sh = Image.new('RGBA', img.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle((x0 + 6, y0 + 8, x1 + 6, y1 + 8), radius, fill=(0, 0, 0, 150))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(9)))
    d.rounded_rectangle(box, radius, fill=fill)
    d.rounded_rectangle((x0 + 5, y0 + 5, x1 - 5, y1 - 5), max(1, radius - 3), outline=edge[:3] + (110,), width=1)
    for (cx, cy, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([(cx + sx * 5, cy + sy * 22), (cx + sx * 5, cy + sy * 5), (cx + sx * 22, cy + sy * 5)], fill=edge, width=2)
        d.ellipse((cx + sx * 12 - 3, cy + sy * 12 - 3, cx + sx * 12 + 3, cy + sy * 12 + 3), fill=(120, 96, 52, 255))
    img.alpha_composite(lay)


def tracked(d, xy, s, f, fill, track=0.0, anchor='l'):
    ws = [f.getlength(c) for c in s]; sp = f.size * track
    Wd = sum(ws) + sp * (len(s) - 1)
    x = xy[0] - (Wd / 2 if anchor == 'm' else Wd if anchor == 'r' else 0)
    for c, w in zip(s, ws):
        d.text((x, xy[1]), c, font=f, fill=fill, anchor='ls'); x += w + sp
    return Wd


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
    f = font(size, 'title'); w = int(f.getlength(text) * 1.08) + 40; h = int(size * 1.8)
    t = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(t)
    d.rectangle((3, 3, w - 4, h - 4), outline=col + (220,), width=4)
    d.text((w / 2, h / 2 + 2), text, font=f, fill=col + (225,), anchor='mm')
    n = np.random.RandomState(3).rand(h, w)
    a = np.asarray(t).copy(); a[..., 3] = (a[..., 3] * (n > 0.16)).astype(np.uint8)
    t = Image.fromarray(a).rotate(rot, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(t, (int(xy[0] - t.size[0] / 2), int(xy[1] - t.size[1] / 2)))


CREAM = (240, 232, 204, 255); BRASS = (196, 168, 104, 255); BLUE = (40, 80, 180); RED = (186, 40, 30)
ROLES = [('INFANTRY', (236, 226, 192), '!infantry', ['Hold the fire trench. Rifle, pistol, knife.', '%d kills without dying: the marksman rifle.' % STREAK,
                                                     'Dressing stations in the support trench heal you.']),
         ('MORTARS', (240, 176, 84), '!mortar', ['Crews of two at the pits behind the line.', 'Plot at the table, fetch a bomb, load, fire.',
                                                 'Watch the fall of shot on the trench map.']),
         ('AIRCRAFT', (150, 200, 230), '!air', ['Dr.I against SPAD over the line.', 'Mouse steers, W / S throttle, A / D roll.',
                                                'Guns on MOUSE 1, two bombs on MOUSE 2.'])]


def slide_title():
    upp = 8601.6 / 1920 * 0.98                                          # the whole radar square across the slide
    v = View(-W / 2 * upp, 400 + H / 2 * upp, upp)
    im = table_light(topview(v))
    px = v.px
    # the attack plans: both sides going over (grease pencil)
    grease(im, [px(1950, 1180), px(950, 1080), px(-250, 820), px(-1480, 930)], BLUE, 9)
    grease(im, [px(-1950, 120), px(-900, -60), px(300, 60), px(1480, -180)], RED, 9)
    stamp(im, (1130, 300), 'SECRET', rot=-6, size=28)
    plate(im, (268, 116, 1060, 318))
    d = ImageDraw.Draw(im)
    tracked(d, (300, 166), 'THE WESTERN FRONT  /  1917', font(22, 'sans'), BRASS, 0.20)
    tracked(d, (296, 252), 'TRENCH WARFARE', font(76, 'title'), CREAM, 0.03)
    d.line([(300, 270), (1028, 270)], fill=(196, 168, 104, 150), width=2)
    tracked(d, (300, 298), 'INFANTRY   TRENCH MORTARS   AIRCRAFT   AREAS OPEN AS THE ROUND GOES ON', font(16, 'sans'), (170, 196, 150, 255), 0.10)
    x0, y0, cw = 268, 716, 352
    plate(im, (x0, y0, x0 + cw * 3 + 24, 936))
    d = ImageDraw.Draw(im)
    for i, (name, col, cmd, lines) in enumerate(ROLES):
        x = x0 + 26 + i * cw
        if i: d.line([(x - 16, y0 + 22), (x - 16, 936 - 22)], fill=(196, 168, 104, 90), width=1)
        tracked(d, (x, y0 + 52), name, font(30, 'title'), col + (255,), 0.10)
        tracked(d, (x + cw - 46, y0 + 52), cmd, font(16, 'sans', 'Regular'), (160, 160, 136, 255), 0.04, 'r')
        y = y0 + 88
        for ln in lines:
            d.rectangle((x, y - 9, x + 5, y - 4), fill=col + (255,))
            y = wrap(d, (x + 14, y), ln, font(17, 'sans', 'Regular'), (226, 220, 198, 255), cw - 62) + 5
    return im.convert('RGB')


def slide_mortar():
    """the plotting board on the table: the CT trench map, a plotted target, the four steps"""
    bg = table_light(Image.new('RGBA', (W, H), (92, 62, 36, 255)), cx=0.38, strength=0.5)
    a = np.asarray(bg, np.float32)
    yy, xx = np.mgrid[0:H, 0:W]
    a[..., :3] *= (0.85 + 0.15 * np.sin((yy + 20 * np.sin(xx / 160.0)) / 3.0))[..., None] * 0.9 + 0.1
    bg = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    mp = Image.open(os.path.join(OUT, 'panorama/images/custom_game/tw/target_ct.png')).convert('RGBA').resize((760, 760), Image.LANCZOS)
    mp = mp.rotate(4, expand=True, resample=Image.BICUBIC)
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ImageDraw.Draw(sh).rectangle((300, 150, 300 + mp.size[0] - 30, 150 + mp.size[1] - 30), fill=(0, 0, 0, 160))
    bg.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)))
    bg.alpha_composite(mp, (280, 128))
    d = ImageDraw.Draw(bg)
    # a plotted target on the enemy fire trench, the gun-target line to crew 2
    c = (640, 330); g = (860, 790)
    red = (176, 30, 22, 235)
    d.line([c, g], fill=(30, 30, 30, 170), width=3)
    for r_ in (26, 54): d.ellipse([c[0] - r_, c[1] - r_, c[0] + r_, c[1] + r_], outline=red, width=5)
    d.text((c[0] + 64, c[1] - 40), 'TGT 1   GRID H5', font=font(24, 'type'), fill=(150, 30, 24, 255))
    plate(bg, (1010, 150, 1340, 300))
    d = ImageDraw.Draw(bg)
    tracked(d, (1036, 216), 'MORTARS', font(46, 'title'), CREAM, 0.04)
    tracked(d, (1038, 262), 'TWO MEN, ONE TUBE', font(17, 'sans'), (240, 176, 84, 255), 0.12)
    steps = [('1', 'PLOT', 'At the table: E, then W A S D moves the sight; MOUSE 1 locks.'),
             ('2', 'FETCH', 'A bomb from the ammunition box with E.'),
             ('3', 'LOAD', 'E at the tube. The board says LOADED.'),
             ('4', 'FIRE', 'SPACE at the table. Two seconds of whistle, then the burst.')]
    y = 340
    plate(bg, (1010, 320, 1340, 900))
    d = ImageDraw.Draw(bg)
    for n, name, txt in steps:
        d.ellipse((1034, y + 6, 1074, y + 46), outline=(240, 176, 84, 255), width=3)
        d.text((1054, y + 26), n, font=font(24, 'serif'), fill=(240, 176, 84, 255), anchor='mm')
        tracked(d, (1090, y + 38), name, font(28, 'title'), CREAM, 0.06)
        y = wrap(d, (1036, y + 80), txt, font(17, 'sans', 'Regular'), (226, 220, 198, 255), 280) + 18
    return bg.convert('RGB')


def slide_front():
    """the areas that open during the round (dusk grade). The map is turned a quarter: the wood (north) right, the mine
    galleries left, the German line at the top, so both areas fit inside the safe area."""
    upp = 7.0
    ylo = -3640 - 300 * upp                                            # slide x 300 = the galleries
    xtop = -H / 2 * upp                                                # slide y 0 = world x -3780
    v = View(xtop, ylo + W * upp, upp)                                 # a north-up view of the turned window (H wide, W high)
    R = Image.open(os.path.join(ROOT, 'out', 'radar_clean.png')).convert('RGB')
    rg = json.load(open(os.path.join(ROOT, 'out', 'radar_region.json')))
    k = R.size[0] / rg['span']
    sx = (xtop - rg['x0']) * k; sy = (rg['y0'] - (ylo + W * upp)) * k
    can = Image.new('RGB', (int(round(H * upp * k)), int(round(W * upp * k))), (40, 54, 33))
    can.paste(R, (int(round(-sx)), int(round(-sy))))
    im = can.resize((H, W), Image.LANCZOS).rotate(-90, expand=True).convert('RGBA')   # clockwise: north to the right
    def px(x, y): return ((y - ylo) / upp, (x - xtop) / upp)
    a = np.asarray(im, np.float32)[..., :3] / 255.0
    h, w = a.shape[:2]; yy, xx = np.mgrid[0:h, 0:w]
    a = a * np.array([1.06, 0.97, 0.82]) + np.array([0.05, 0.03, 0.0])
    r = np.hypot((xx - w * 0.5) / (w * 0.66), (yy - h * 0.5) / (h * 0.80))
    a *= np.clip(1.08 - 0.62 * r ** 1.8, 0.14, 1.08)[..., None]
    im = Image.fromarray((a.clip(0, 1) * 255).astype(np.uint8)).convert('RGBA')
    d = ImageDraw.Draw(im)
    names = {'woodsopen': ('THE WOOD', (0, 3950), 'ladders at the north end of the fire trenches'),
             'undergroundopen': ('MINE GALLERIES', (0, -3640), 'saps at the south end of the support trenches')}
    for nm, kills, secs in UNLOCK:
        title, (x, y), where = names.get(nm, (nm.upper(), (0, 0), ''))
        c = px(x, y)
        f = font(30, 'title'); f2 = font(15, 'sans')
        l1 = 'OPENS AFTER %s KILLS OR %d MINUTES' % (kills, int(secs) // 60); l2 = where.upper()
        wd = max(f.getlength(title), f2.getlength(l1) * 1.08, f2.getlength(l2) * 1.08) + 50
        cx, yb = (620, 430) if y < 0 else (1020, 640)
        tip = (c[0] + (40 if y < 0 else -40), c[1])
        grease(im, [(cx + (-wd / 2 if y < 0 else wd / 2) * 0.8, yb + (60 if y < 0 else -40)), ((cx + tip[0]) / 2, (yb + tip[1]) / 2 + 40), tip], (240, 176, 84), 6)
        lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        dl.rounded_rectangle((cx - wd / 2, yb - 40, cx + wd / 2, yb + 62), 5, fill=(18, 20, 14, 225))
        im.alpha_composite(lay); d = ImageDraw.Draw(im)
        tracked(d, (cx, yb), title, f, CREAM, 0.08, 'm')
        tracked(d, (cx, yb + 28), l1, f2, (240, 176, 84, 255), 0.06, 'm')
        tracked(d, (cx, yb + 50), l2, f2, (214, 208, 186, 255), 0.06, 'm')
    for (x, y, txt, col) in ((-1330, 1610, 'GERMAN LINES', (222, 150, 140)), (1300, 1610, 'BRITISH LINES', (160, 180, 230))):
        c = px(x, y); f = font(26, 'title')
        tracked(d, (c[0] + 2, c[1] + 2), txt, f, (0, 0, 0, 220), 0.12, 'm'); tracked(d, (c[0], c[1]), txt, f, col + (255,), 0.12, 'm')
    plate(im, (268, 116, 830, 262))
    d = ImageDraw.Draw(im)
    tracked(d, (298, 196), 'THE FRONT MOVES', font(54, 'title'), CREAM, 0.03)
    tracked(d, (300, 236), 'KILLS AND TIME BLOW NEW WAYS OPEN', font(17, 'sans'), (170, 196, 150, 255), 0.10)
    plate(im, (268, 838, 1316, 936))
    d = ImageDraw.Draw(im)
    x = 296
    for key, txt in (('!roles', 'who is where'), ('!swap', 'back to the old rifle'), ('!uniform', 'period uniform on / off'), ('!pos', 'your radar square')):
        f = font(20, 'sans'); kw = f.getlength(key) + 22
        d.rounded_rectangle((x, 872, x + kw, 906), 5, outline=CREAM, width=2)
        d.text((x + kw / 2, 889), key, font=f, fill=CREAM, anchor='mm')
        x += kw + 10
        d.text((x, 889), txt, font=font(18, 'sans', 'Regular'), fill=(214, 208, 186, 255), anchor='lm')
        x += font(18, 'sans', 'Regular').getlength(txt) + 28
    return im.convert('RGB')


ICON = ('M3 39 C9 34 15 33 17 33 C18 22 24 16 32 16 C40 16 46 22 47 33 C49 33 55 34 61 39 C56 44 45 46 32 46 C19 46 8 44 3 39 Z '   # a Brodie helmet: shallow dome, wide brim
        'M17 30 H47 V33 H17 Z '                                         # the band where dome meets brim (cut)
        'M30 19 H34 V22 H30 Z')                                          # the crown rivet (cut)


def main():
    ims = [slide_title(), slide_mortar(), slide_front()]
    names = loading.write_slides(OUT, MAP, ims, css_check=True)
    od = os.path.join(ROOT, 'out', 'step8', 'slides'); os.makedirs(od, exist_ok=True)
    for n, im in zip(names, ims):
        loading.cs2_overlay(im).save(os.path.join(od, n.replace('.png', '_cs2.png')))
        im.save(os.path.join(od, n))
    p = loading.write_icon(OUT, MAP, ICON)
    print('loading screen: %d slides (%s), icon %s' % (len(names), ' '.join(names), p))


if __name__ == '__main__':
    main()
