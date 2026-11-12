"""Vintage cockpit instrument art for the flight HUD (panorama/images/custom_game/tw/fly_*.png): aged dial faces (airspeed,
altimeter, tachometer, bank), compass card, needles, brass bezels, bomb lamps, the ammunition counter window, and the
varnished-wood dash and side plates the gauges sit in. Layout and css: tools/tw_hud.py (docs/HUD.md).
Every picture is made at the size tw_hud.py shows it (or twice that for the dials, which rotate), so nothing is stretched."""
import os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from noise import fbm

FONTS = {'serif': ['C:/Windows/Fonts/georgiab.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'],
         'book': ['C:/Windows/Fonts/BOOKOSB.TTF', 'C:/Windows/Fonts/georgiab.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'],
         'sans': ['C:/Windows/Fonts/bahnschrift.ttf', 'C:/Windows/Fonts/arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf']}
S = 256                       # dial texture size (shown at 128 px: 2x for the rotation)
G = 128                       # gauge size on screen (tw_hud.py)


def font(sz, kind='book'):
    for p in FONTS[kind]:
        if os.path.exists(p):
            f = ImageFont.truetype(p, int(sz))
            if 'bahnschrift' in p:
                try: f.set_variation_by_name('SemiBold Condensed')
                except Exception: pass
            return f
    return ImageFont.load_default()


def aged(size, base=(34, 31, 27), dark=0.3, seed=0):
    y, x = np.mgrid[0:size, 0:size] / size
    n = fbm(x * 6 + seed, y * 6, 0.5, 4, seed=50 + seed) * 0.5 + fbm(x * 30, y * 30 + seed, 1.5, 2, seed=51) * 0.15
    r = np.hypot(x - 0.5, y - 0.5) * 2
    shade = 1 - dark * np.clip(r - 0.55, 0, 1) * 2.2 - 0.06 * n
    a = np.array(base, np.float32)[None, None] * shade[..., None]
    a[..., 2] -= 3 * np.clip(n, 0, 1)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert('RGBA')


def circle_mask(img, inset=0):
    m = Image.new('L', img.size, 0); ImageDraw.Draw(m).ellipse((inset, inset, img.size[0] - inset - 1, img.size[1] - inset - 1), fill=255)
    img.putalpha(m); return img


def dial(marks, a0=-150, a1=150, title='', unit='', red=None, seed=0, minor=5):
    im = aged(S, seed=seed); d = ImageDraw.Draw(im); c = S / 2
    R = S * 0.44
    ink = (228, 218, 190, 255)
    vals = [m[0] for m in marks]; v0, v1 = vals[0], vals[-1]
    ang = lambda v: math.radians(a0 + (a1 - a0) * (v - v0) / (v1 - v0) - 90)
    if red is not None:
        for k in range(60):
            t = red[0] + (red[1] - red[0]) * k / 59
            q = ang(t); r_ = S * 0.014
            d.ellipse((c + math.cos(q) * R * 0.93 - r_, c + math.sin(q) * R * 0.93 - r_, c + math.cos(q) * R * 0.93 + r_, c + math.sin(q) * R * 0.93 + r_), fill=(170, 30, 24, 255))
    steps = (len(marks) - 1) * minor
    for k in range(steps + 1):
        v = v0 + (v1 - v0) * k / steps; q = ang(v); big = k % minor == 0
        r0 = R * (0.80 if big else 0.87)
        d.line([(c + math.cos(q) * r0, c + math.sin(q) * r0), (c + math.cos(q) * R, c + math.sin(q) * R)], fill=ink, width=4 if big else 2)
    f = font(S * 0.105)
    for v, txt in marks:
        q = ang(v); x, y = c + math.cos(q) * R * 0.62, c + math.sin(q) * R * 0.62
        d.text((x, y), txt, font=f, fill=ink, anchor='mm')
    if title: d.text((c, c + S * 0.17), title, font=font(S * 0.068, 'serif'), fill=ink, anchor='mm')
    if unit: d.text((c, c + S * 0.255), unit, font=font(S * 0.056), fill=(170, 160, 135, 255), anchor='mm')
    return circle_mask(im, 3)


def card():
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im); c = S / 2
    d.ellipse((4, 4, S - 4, S - 4), fill=(30, 28, 24, 255))
    ink = (226, 214, 180, 255); R = S * 0.45
    for k in range(72):
        q = math.radians(k * 5 - 90); big = k % 6 == 0
        r0 = R * (0.80 if big else 0.88)
        d.line([(c + math.cos(q) * r0, c + math.sin(q) * r0), (c + math.cos(q) * R, c + math.sin(q) * R)], fill=ink, width=3 if big else 1)
    f = font(S * 0.13); f2 = font(S * 0.075)
    for k, txt in enumerate(['N', '3', '6', 'E', '12', '15', 'S', '21', '24', 'W', '30', '33']):
        q = math.radians(k * 30 - 90); x, y = c + math.cos(q) * R * 0.62, c + math.sin(q) * R * 0.62
        lab = Image.new('RGBA', (S // 3, S // 3), (0, 0, 0, 0))
        ImageDraw.Draw(lab).text((S // 6, S // 6), txt, font=f if len(txt) == 1 else f2, fill=(200, 40, 30, 255) if txt == 'N' else ink, anchor='mm')
        lab = lab.rotate(-k * 30, resample=Image.BICUBIC)
        im.alpha_composite(lab, (int(x - S // 6), int(y - S // 6)))
    return im


def needle(color=(236, 228, 200), length=0.42, tail=0.12, width=0.024):
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im); c = S / 2
    w = S * width
    d.polygon([(c, c - S * length), (c + w, c), (c, c + S * tail), (c - w, c)], fill=color + (255,), outline=(20, 18, 14, 255))
    d.ellipse((c - S * 0.05, c - S * 0.05, c + S * 0.05, c + S * 0.05), fill=(40, 36, 30, 255), outline=(170, 140, 80, 255), width=2)
    return im.filter(ImageFilter.GaussianBlur(0.4))


def lubber():
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im); c = S / 2
    d.polygon([(c, S * 0.10), (c + 8, S * 0.02), (c - 8, S * 0.02)], fill=(240, 200, 90, 255))
    d.line([(c, S * 0.10), (c, S * 0.9)], fill=(240, 200, 90, 110), width=2)
    return im


def bezel():
    y, x = np.mgrid[0:S, 0:S] / S
    r = np.hypot(x - 0.5, y - 0.5) * 2
    a = np.zeros((S, S, 4), np.float32)
    ring = (r > 0.86) & (r < 1.0)
    ang = np.arctan2(y - 0.5, x - 0.5)
    lum = 0.55 + 0.35 * np.cos(ang + 2.3) + 0.08 * np.sin(r * 90)
    brass = np.stack([200 * lum + 30, 160 * lum + 20, 80 * lum + 10], -1)
    a[ring, :3] = brass[ring]; a[ring, 3] = 255
    g = np.clip(1 - np.hypot(x - 0.36, y - 0.3) / 0.28, 0, 1) ** 2 * (r < 0.86)
    a[..., :3] += (g * 255)[..., None] * (1 - ring[..., None]); a[..., 3] = np.maximum(a[..., 3], g * 70)
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    for q in (45, 135, 225, 315):
        qq = math.radians(q); x0, y0 = S / 2 + math.cos(qq) * S * 0.465, S / 2 + math.sin(qq) * S * 0.465
        d.ellipse((x0 - 5, y0 - 5, x0 + 5, y0 + 5), fill=(120, 96, 50, 255)); d.line([(x0 - 4, y0), (x0 + 4, y0)], fill=(50, 40, 20, 255), width=2)
    return im


def wood(w, h, seed=61, base=(96, 58, 30)):
    """varnished walnut: long grain with a little figure, darker towards the edges"""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    g = fbm(x / 420.0, y / 26.0, 0.3, 4, seed=seed) + 0.35 * np.sin((y + 18 * fbm(x / 160.0, y / 60.0, 1.1, 3, seed=seed + 1)) / 2.2)
    a = np.array(base, np.float32)[None, None] * (0.78 + 0.22 * g[..., None])
    a[..., 0] += 14 * fbm(x / 70.0, y / 70.0, 2.0, 2, seed=seed + 2)
    e = np.minimum(np.minimum(x, w - 1 - x), np.minimum(y, h - 1 - y))
    a *= (0.72 + 0.28 * np.clip(e / 14.0, 0, 1))[..., None]
    sheen = np.exp(-((y - h * 0.25) / (h * 0.18)) ** 2) * 0.10
    a += sheen[..., None] * 255 * 0.3
    return Image.fromarray(np.dstack([np.clip(a, 0, 255), np.full((h, w), 255.0)]).astype(np.uint8), 'RGBA')


def screw(d, x, y, r=5):
    d.ellipse((x - r, y - r, x + r, y + r), fill=(150, 120, 64, 255), outline=(70, 54, 26, 255))
    d.line([(x - r + 2, y - 1), (x + r - 2, y + 1)], fill=(60, 46, 22, 255), width=2)


def dash_plate(w, h, centres, r):
    """the instrument board: wood, a leather roll along the top, a dark recess behind each gauge, brass screws"""
    im = wood(w, h)
    a = np.asarray(im).copy()
    top = 16
    a[:top, :, :3] = (np.array([46, 30, 20]) * (0.8 + 0.2 * np.sin(np.arange(top) / top * np.pi))[:, None, None]).astype(np.uint8)
    im = Image.fromarray(a)
    sh = Image.new('RGBA', (w, h), (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
    for (cx, cy) in centres:
        ds.ellipse((cx - r - 7, cy - r - 4, cx + r + 7, cy + r + 10), fill=(0, 0, 0, 170))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(5)))
    d = ImageDraw.Draw(im)
    for (cx, cy) in centres:
        d.ellipse((cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3), fill=(18, 14, 10, 255))
    for (x, y) in ((12, top + 10), (w - 12, top + 10), (12, h - 12), (w - 12, h - 12)): screw(d, x, y)
    d.rectangle((0, 0, w - 1, h - 1), outline=(30, 20, 12, 255), width=2)
    return im


def side_plate(w, h, captions):
    """the right-hand panel: the counter window and the bomb lamps on wood, engraved brass captions"""
    im = wood(w, h, seed=71)
    d = ImageDraw.Draw(im)
    f = font(13, 'serif')
    for (text, y) in captions:
        tw = d.textlength(text, font=f) + 16
        d.rounded_rectangle(((w - tw) / 2, y - 10, (w + tw) / 2, y + 10), 3, fill=(176, 142, 74, 255), outline=(98, 76, 36, 255))
        d.text((w / 2, y + 1), text, font=f, fill=(40, 30, 14, 255), anchor='mm')
    for (x, y) in ((9, 9), (w - 9, 9), (9, h - 9), (w - 9, h - 9)): screw(d, x, y, 4)
    d.rectangle((0, 0, w - 1, h - 1), outline=(30, 20, 12, 255), width=2)
    return im


def lamp(on):
    im = Image.new('RGBA', (88, 88), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse((2, 2, 86, 86), fill=(150, 118, 60, 255), outline=(80, 60, 28, 255), width=3)
    d.ellipse((14, 14, 74, 74), fill=(255, 190, 70, 255) if on else (54, 36, 20, 255))
    if on:
        g = Image.new('RGBA', (88, 88), (0, 0, 0, 0)); ImageDraw.Draw(g).ellipse((8, 8, 80, 80), fill=(255, 200, 90, 110))
        im = Image.alpha_composite(g.filter(ImageFilter.GaussianBlur(5)), im); d = ImageDraw.Draw(im)
        d.ellipse((24, 20, 42, 36), fill=(255, 245, 200, 255))
    else:
        d.ellipse((24, 20, 38, 32), fill=(90, 70, 50, 255))
    return im


def counter_bg(w=130, h=48):
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), 7, fill=(160, 126, 64, 255), outline=(84, 62, 28, 255), width=2)
    d.rounded_rectangle((6, 6, w - 7, h - 7), 4, fill=(14, 12, 10, 255))
    for k in range(1, 4): d.line([(6 + k * (w - 12) / 4, 8), (6 + k * (w - 12) / 4, h - 9)], fill=(64, 56, 46, 255), width=1)
    d.line([(8, 9), (w - 9, 9)], fill=(255, 255, 255, 40), width=2)
    return im


def build(imgdir, gauge_centres, gauge_r, dash_size, side_size, side_captions):
    os.makedirs(imgdir, exist_ok=True)
    P = lambda n: os.path.join(imgdir, n)
    dial([(0, '0'), (50, '50'), (100, '100'), (150, '150'), (200, '200'), (250, '250'), (300, '300')], title='AIRSPEED', unit='km/h', red=(250, 300), seed=1).save(P('fly_asi.png'))
    dial([(k, str(k)) for k in range(0, 10)] + [(10, '0')], a0=0, a1=360, title='ALT x100m', unit='', seed=2, minor=5).save(P('fly_alt.png'))
    dial([(k, str(k)) for k in range(4, 21, 2)], title='R.P.M.', unit='x 100', red=(17, 20), seed=3).save(P('fly_rpm.png'))
    dial([(-60, '60'), (-30, '30'), (0, '0'), (30, '30'), (60, '60')], a0=-60, a1=60, title='BANK', unit='', seed=4, minor=3).save(P('fly_bank.png'))
    card().save(P('fly_card.png')); lubber().save(P('fly_lubber.png'))
    needle().save(P('fly_needle.png'))
    bezel().save(P('fly_bezel.png'))
    lamp(False).save(P('fly_lamp_off.png')); lamp(True).save(P('fly_lamp_on.png'))
    counter_bg().save(P('fly_counter.png'))
    dash_plate(dash_size[0], dash_size[1], gauge_centres, gauge_r).save(P('fly_dash.png'))
    side_plate(side_size[0], side_size[1], side_captions).save(P('fly_side.png'))
    for stale in ('fly_needle_short.png',):
        if os.path.exists(P(stale)): os.remove(P(stale))
