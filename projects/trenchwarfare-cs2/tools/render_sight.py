"""The mortar plotting board's map: a printed WW1 trench map of the targetable square, one per team, enemy line at the top
(panorama/images/custom_game/tw/target_t.png, target_ct.png; shown 640 px on the board by tools/tw_hud.py).

usage: render_sight.py [<addon content out>]          default ../out/addon; needs ../out/radar_clean.png (tools/make_radar.py)
  writes target_t.png, target_ct.png (1024 px), ../out/target_map.json {ext, size, steps}, ../out/step8/sight_check.png (both
  maps side by side with the mortar pits drawn through the script's worldToSight: they must sit on the printed pits)

Look: the radar's top view printed on paper (desaturated, warm, an ink edge layer), the trench lines in the British trench-map
convention, own works blue and the enemy's red, every mortar pit as a ring, the 16 x 16 squares the sight's GRID read-out names
(70_mortar.js gridRef: letter = column across, number = row down, per team), a north arrow, paper grain and folds.
Orientation = 70_mortar.js sightToWorld: CT: u (across) = (y + E) / 2E, v (down) = (x + E) / 2E; T: u = (E - y) / 2E, v = (E - x) / 2E."""
import os, sys, json, re, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy import ndimage
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layout as LY

ROOT = os.path.join(HERE, '..')
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'out', 'addon')
cfg = open(os.path.join(ROOT, 'src', 'modules', '00_config.js'), encoding='utf-8').read()
EXT = float(re.search(r'TARGET_EXT:\s*([\d.]+)', cfg).group(1))
STEPS = int(re.search(r'TARGET_STEPS:\s*(\d+)', cfg).group(1))
N = 2048                    # working size of the square [-EXT, EXT]
S = 1024                    # shipped size
F = lambda p, s: ImageFont.truetype(p, int(s))
GEORGIA_B = 'C:/Windows/Fonts/georgiab.ttf'; GEORGIA = 'C:/Windows/Fonts/georgia.ttf'; COUR = 'C:/Windows/Fonts/courbd.ttf'
STENCIL = 'C:/Windows/Fonts/STENCIL.TTF'


def world_crop():
    """the radar's unlabelled 4096 px master cropped (and padded) to the targetable square, north up"""
    R = Image.open(os.path.join(ROOT, 'out', 'radar_clean.png')).convert('RGB')
    rg = json.load(open(os.path.join(ROOT, 'out', 'radar_region.json')))
    k = R.size[0] / rg['span']
    box = [(-EXT - rg['x0']) * k, (rg['y0'] - EXT) * k, (EXT - rg['x0']) * k, (rg['y0'] + EXT) * k]
    W = int(round(box[2] - box[0])); H = int(round(box[3] - box[1]))
    can = Image.new('RGB', (W, H), (52, 62, 40))
    can.paste(R, (int(round(-box[0])), int(round(-box[1]))))
    # outside the radar square: the wood carries on (dark green, mottled), so the paper print reads as forest there
    a = np.asarray(can, np.float32)
    mask = np.ones(a.shape[:2], bool)
    x0, y0 = int(round(-box[0])), int(round(-box[1]))
    mask[max(0, y0):y0 + R.size[1], max(0, x0):x0 + R.size[0]] = False
    n = ndimage.gaussian_filter(np.random.RandomState(4).rand(*a.shape[:2]), 4)
    n = (n - n.mean()) / (n.std() + 1e-9)                             # unit mottling
    fill = np.stack([40 + 9 * n, 56 + 12 * n, 33 + 7 * n], -1)
    a[mask] = fill[mask]
    return Image.fromarray(a.clip(0, 255).astype(np.uint8)).resize((N, N), Image.LANCZOS)


def to_px(x, y):
    return ((x + EXT) / (2 * EXT) * N, (EXT - y) / (2 * EXT) * N)


def printed(img):
    """the top view as a lithographed map: desaturated and warm, tones squeezed into the paper's range, an ink edge layer"""
    a = np.asarray(img, np.float32) / 255.0
    L = a @ np.array([0.30, 0.55, 0.15])
    lo, hi = np.percentile(L, 2), np.percentile(L, 98.5)
    Ln = np.clip((L - lo) / (hi - lo), 0, 1)
    paper = np.array([0.925, 0.885, 0.78])
    tint = a / (a.mean(-1, keepdims=True) + 1e-3)                     # keep a little of the hue (woods green, water blue)
    tone = paper * (0.50 + 0.50 * Ln[..., None]) * (0.80 + 0.20 * np.clip(tint, 0.6, 1.4))
    e = np.hypot(ndimage.sobel(ndimage.gaussian_filter(L, 1.0), 0), ndimage.sobel(ndimage.gaussian_filter(L, 1.0), 1))
    e = np.clip(e * 2.2, 0, 1) ** 1.2
    ink = np.array([0.30, 0.24, 0.18])
    out = tone * (1 - 0.55 * e[..., None]) + ink * 0.55 * e[..., None]
    return out


def trench_lines(own_sign):
    """own works blue, the enemy's red (British trench-map convention), drawn over the print as two-tone lines"""
    lay = Image.new('RGBA', (N, N), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    for s in (-1, 1):
        col = (38, 76, 160, 235) if s == own_sign else (176, 34, 26, 235)
        m = Image.new('L', (N, N), 0); dm = ImageDraw.Draw(m)
        for (x0, y0, x1, y1, k) in LY.rects():
            a, b = sorted((s * x0, s * x1))
            p0 = to_px(a, y1); p1 = to_px(b, y0)
            dm.rectangle([p0, p1], fill=255)
        mm = np.asarray(m) > 0
        edge = ndimage.binary_dilation(mm, iterations=4) & ~ndimage.binary_erosion(mm, iterations=1)
        fill = np.zeros((N, N, 4), np.uint8); fill[edge] = col; fill[mm & ~edge] = col[:3] + (60,)
        lay = Image.alpha_composite(lay, Image.fromarray(fill))
        d = ImageDraw.Draw(lay)
        for (cx, cy) in LY.mortar_pits(s):
            p = to_px(cx, cy); r = 196 / (2 * EXT) * N
            d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), outline=col, width=5)
            d.ellipse((p[0] - 7, p[1] - 7, p[0] + 7, p[1] + 7), fill=col)
    return lay


def finish(img, team, rng):
    """paper grain, two folds, foxing, a darker rim; then the grid, letters, north arrow and the sheet title"""
    a = np.asarray(img.convert('RGB'), np.float32) / 255.0
    h, w = a.shape[:2]; y, x = np.mgrid[0:h, 0:w] / h
    grain = ndimage.gaussian_filter(rng.rand(h, w), 0.8) - 0.5
    stain = ndimage.gaussian_filter(rng.rand(h // 8, w // 8), 3)
    stain = np.kron(stain, np.ones((8, 8)))[:h, :w]
    a *= (1 + 0.05 * grain[..., None]) * (1 - 0.10 * np.clip((stain - 0.52) * 6, 0, 1)[..., None])
    for f in (0.5,):
        a *= (1 - 0.05 * np.exp(-((x - f) / 0.004) ** 2))[..., None]; a *= (1 - 0.04 * np.exp(-((y - f) / 0.004) ** 2))[..., None]
    r = np.hypot(x - 0.5, y - 0.5)
    a *= np.clip(1.07 - 0.35 * r ** 2.2, 0.75, 1.05)[..., None]
    im = Image.fromarray((a.clip(0, 1) * 255).astype(np.uint8)).convert('RGBA')
    d = ImageDraw.Draw(im)
    ink = (52, 40, 30, 200)
    for k in range(1, 16):
        t = w * k / 16
        d.line([(t, 0), (t, h)], fill=(52, 40, 30, 70), width=1); d.line([(0, t), (w, t)], fill=(52, 40, 30, 70), width=1)
    fG = F(GEORGIA_B, 24)
    for k in range(16):
        c = w * (k + 0.5) / 16
        d.text((c, 8), chr(65 + k), font=fG, fill=ink, anchor='mt', stroke_width=2, stroke_fill=(236, 226, 200, 200))
        d.text((8, c), str(k + 1), font=fG, fill=ink, anchor='lm', stroke_width=2, stroke_fill=(236, 226, 200, 200))
    # north arrow: north (+y) is to the right on the CT map (u grows with y), to the left on the T map
    cx, cy = w - 70, h - 62; L = 34; sgn = 1 if team == 'ct' else -1
    d.polygon([(cx + sgn * L, cy), (cx - sgn * L * 0.4, cy - 11), (cx - sgn * L * 0.15, cy), (cx - sgn * L * 0.4, cy + 11)], fill=(52, 40, 30, 220))
    d.text((cx + sgn * (L + 14), cy), 'N', font=F(GEORGIA_B, 20), fill=(52, 40, 30, 230), anchor='mm')
    # sheet title, bottom left
    t = 'TRENCH MAP'; sub = 'own works blue, enemy red'
    d.rectangle((46, h - 96, 46 + 420, h - 30), fill=(236, 226, 200, 220), outline=(52, 40, 30, 200), width=2)
    d.text((60, h - 77), t, font=F(STENCIL, 30), fill=(52, 40, 30, 235), anchor='lm')
    d.text((60, h - 46), sub, font=F(GEORGIA, 16), fill=(52, 40, 30, 225), anchor='lm')
    d.rectangle((0, 0, w - 1, h - 1), outline=(52, 40, 30, 255), width=3)
    return im


def sight_pos(team, x, y):
    """70_mortar.js worldToSight, in pixels of a w-wide sight picture (u across, v down)"""
    E = EXT
    u, v = ((y + E) / (2 * E), (x + E) / (2 * E)) if team == 'ct' else ((E - y) / (2 * E), (E - x) / (2 * E))
    return u, v


def main():
    base = world_crop()
    p = printed(base)
    d_ = os.path.join(OUT, 'panorama/images/custom_game/tw'); os.makedirs(d_, exist_ok=True)
    shots = []
    for team in ('t', 'ct'):
        own = -1 if team == 't' else 1
        im = Image.fromarray((p.clip(0, 1) * 255).astype(np.uint8)).convert('RGBA')
        im = Image.alpha_composite(im, trench_lines(own))
        im = im.rotate(90 if team == 't' else -90)                  # enemy at the top (render_top.py's old orientation, = sightToWorld)
        im = im.resize((S, S), Image.LANCZOS)
        im = finish(im, team, np.random.RandomState(7 if team == 't' else 8))
        im.convert('RGB').save(os.path.join(d_, 'target_%s.png' % team), optimize=True)
        # check picture: the pits through the script's own sight math must land on the printed pit rings
        chk = im.copy(); dc = ImageDraw.Draw(chk)
        for s in (-1, 1):
            for (cx, cy) in LY.mortar_pits(s):
                u, v = sight_pos(team, cx, cy); q = (u * S, v * S)
                dc.ellipse((q[0] - 9, q[1] - 9, q[0] + 9, q[1] + 9), outline=(255, 0, 255, 255), width=3)
        shots.append(chk)
    json.dump(dict(ext=EXT, size=S, steps=STEPS), open(os.path.join(ROOT, 'out', 'target_map.json'), 'w'))
    s8 = os.path.join(ROOT, 'out', 'step8'); os.makedirs(s8, exist_ok=True)
    sheet = Image.new('RGB', (2 * S + 20, S), (30, 30, 30)); sheet.paste(shots[0], (0, 0)); sheet.paste(shots[1], (S + 20, 0))
    sheet.save(os.path.join(s8, 'sight_check.png'))
    print('sight maps: target_t.png, target_ct.png (%d px, EXT %d, %d steps) -> %s' % (S, EXT, STEPS, d_))


if __name__ == '__main__':
    main()
