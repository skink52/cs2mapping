"""Steam Workshop preview images for Hellmatch ZE: out/workshop/workshop_square.jpg (main thumbnail, 1080x1080) and
out/workshop/workshop_wide.jpg (gallery, 1920x1080), each under 1 MB, plus PNG copies in preview/ to look at.

usage: workshop_art.py <addon_out>   (needs the sky and _gen/levels.json from the build)

Layers: an arena render (ref/art, Freedoom textures, sky put in by title.scene) darkened and tinted towards hell-red;
a horde of Freedoom's own monster sprites (front views, nearest-neighbour upscaled, lit from below by an orange rim)
advancing from the bottom; the HELLMATCH ZE logo (title.logo, our own art in the HUD font) and plain HUD-font lines.
Freedoom's logos are not used. The level count comes from the build's levels.
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets, title

OUT = sys.argv[1]
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
DIST = os.path.join(ROOT, 'out/workshop')
PREVIEW = os.path.join(ROOT, 'preview')
SKY = os.path.join(OUT, 'materials/fdm/sky/sky_color.png')
LEVELS = json.load(open(os.path.join(OUT, '_gen/levels.json')))
NMAPS = len({L['base'] for L in LEVELS if not L.get('finale')})   # ZE levels; the escape finale arena is not one
DISCLAIMER = 'USES CONTENT FROM THE FREEDOOM PROJECT (BSD LICENCE). NOT AFFILIATED WITH OR ENDORSED BY THE FREEDOOM PROJECT.'


def shade(img, top, top_h, bottom, bottom_h, vignette=0.35, tint=(1.10, 0.78, 0.70)):
    a = np.array(img.convert('RGB')).astype(np.float32)
    H, W = a.shape[:2]
    y = np.arange(H)[:, None]
    k = np.ones((H, 1), np.float32)
    k -= top * np.clip(1 - y / (H * top_h), 0, 1)
    k -= bottom * np.clip((y - H * (1 - bottom_h)) / (H * bottom_h), 0, 1)
    yy, xx = np.mgrid[0:H, 0:W]
    v = 1 - vignette * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / 2
    a *= np.clip(k, 0, 1)[..., None] * v[..., None]
    a *= np.array(tint, np.float32)          # hell-red grade: ZE's arenas are overrun
    return Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert('RGBA')


def demon(name, height, light=1.0):
    """a Freedoom sprite frame (e.g. 'CYBRE1'), upscaled with crisp pixels to `height` px, darkened to `light`, with an
    orange rim glow from below (the fires of the level behind the horde)"""
    s = assets.sprite(name)
    if s is None: raise SystemExit('workshop_art: sprite %s not found' % name)
    a = s[0].astype(np.float32)
    k = max(1, int(round(height / a.shape[0])))
    im = Image.fromarray(a.clip(0, 255).astype(np.uint8), 'RGBA').resize((a.shape[1] * k, a.shape[0] * k), Image.NEAREST)
    arr = np.array(im).astype(np.float32)
    H = arr.shape[0]
    grad = (0.55 + 0.45 * (1 - np.arange(H) / H))[:, None, None]     # darker towards the feet
    arr[..., :3] *= grad * light
    im = Image.fromarray(arr.clip(0, 255).astype(np.uint8), 'RGBA')
    pad = 12 * k // 2 + 8
    canvas = Image.new('RGBA', (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    al = Image.new('L', canvas.size, 0); al.paste(im.getchannel('A'), (pad, pad))
    glow = al.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(max(2, k * 1.5)))
    g = Image.new('RGBA', canvas.size, (255, 90, 20, 0)); g.putalpha(glow.point(lambda v: int(v * 0.55 * light)))
    canvas.alpha_composite(g)
    canvas.alpha_composite(im, (pad, pad))
    return canvas


def horde(base, rows):
    """rows: [(y_feet, [(sprite, x_centre, height, light), ...]), ...] back row first"""
    for y, items in rows:
        for name, x, h, light in items:
            d = demon(name, h, light)
            base.alpha_composite(d, (int(x - d.width / 2), int(y - d.height + 8)))


def floor_fog(base, y0, strength=0.9):
    """dark fog over the bottom so the horde stands in the level, not on top of it"""
    W, H = base.size
    a = np.zeros((H, W, 4), np.uint8)
    t = np.clip((np.arange(H) - y0) / max(1, H - y0), 0, 1)
    a[..., 0] = 30; a[..., 1] = 6; a[..., 2] = 4
    a[..., 3] = (t[:, None] * 255 * strength).astype(np.uint8)
    base.alpha_composite(Image.fromarray(a, 'RGBA'))


def fit(text, max_w, scale, tint=(235, 235, 235)):
    """HUD-font text at the largest scale (up to `scale`) that fits `max_w`."""
    while scale > 1 and title.hud_text(text, scale, tint).width > max_w: scale -= 1
    return title.hud_text(text, scale, tint)


def centred(base, im, y):
    base.alpha_composite(im, ((base.width - im.width) // 2, y))


def save(img, name):
    os.makedirs(DIST, exist_ok=True)
    p = os.path.join(DIST, name)
    for q in (92, 88, 84, 80, 76):
        img.convert('RGB').save(p, quality=q, optimize=True)
        if os.path.getsize(p) < 1000000: break
    img.convert('RGB').resize((img.width // 2, img.height // 2), Image.LANCZOS).save(os.path.join(PREVIEW, 'workshop_' + name.split('_', 1)[1].replace('.jpg', '.png')))
    print(name, img.size, '%d KB' % (os.path.getsize(p) // 1024))


GOLD, WHITE, GREY = (255, 200, 60), (235, 235, 235), (190, 190, 190)
LINE = '%d LEVELS - TWO TEAMS - ONE WAY OUT' % NMAPS

# square thumbnail: logo top, horde bottom
sq = shade(title.scene('square', SKY), 0.6, 0.45, 0.35, 0.3)
horde(sq, [
    (770, [('BOSSA1', 190, 200, 0.45), ('FATTA1', 890, 210, 0.5)]),
    (900, [('TROOA1', 130, 230, 0.7), ('CYBRE1', 540, 470, 0.8), ('BOS2A1', 950, 230, 0.7)]),
    (1060, [('SARGE1', 280, 300, 1.0), ('TROOG1', 800, 310, 1.0), ('SKULC1', 90, 150, 1.0), ('SKULA1', 1000, 140, 1.0)]),
])
floor_fog(sq, 980, 0.6)
lg = title.logo(960)
centred(sq, lg, 40)
centred(sq, fit('ZOMBIE ESCAPE IN COUNTER-STRIKE 2', sq.width - 80, 5), 40 + lg.height + 14)
centred(sq, fit(LINE, sq.width - 80, 5, GOLD), sq.height - 74)
save(sq, 'workshop_square.jpg')

# wide gallery image: logo centre top, horde across the bottom, rules line, disclaimer
wd = shade(title.scene('wide', SKY), 0.6, 0.45, 0.4, 0.3)
horde(wd, [
    (720, [('BOSSA1', 250, 210, 0.45), ('HEADA1', 700, 150, 0.45), ('BOS2A1', 1230, 210, 0.45), ('FATTA1', 1680, 220, 0.5)]),
    (880, [('TROOA1', 470, 240, 0.7), ('CYBRE1', 960, 470, 0.8), ('BSPIA1D1', 1460, 220, 0.7)]),
    (1020, [('SARGE1', 160, 310, 1.0), ('TROOG1', 650, 320, 1.0), ('SARGA1', 1290, 300, 1.0), ('TROOA1', 1780, 310, 1.0),
            ('SKULC1', 390, 160, 1.0), ('SKULA1', 1560, 150, 1.0)]),
])
floor_fog(wd, 900, 0.7)
lg = title.logo(1100)
centred(wd, lg, 34)
centred(wd, fit('ZOMBIE ESCAPE IN COUNTER-STRIKE 2', wd.width - 160, 6), 34 + lg.height + 12)
centred(wd, fit('HOLD THE LINE - KILL THE GUARDIAN - GET OUT', wd.width - 160, 4, WHITE), 34 + lg.height + 80)
centred(wd, fit(LINE, wd.width - 160, 5, GOLD), wd.height - 118)
centred(wd, title.hud_text(DISCLAIMER, 2, GREY), wd.height - 46)
save(wd, 'workshop_wide.jpg')
