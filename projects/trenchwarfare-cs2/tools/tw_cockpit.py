"""Vintage cockpit instrument art for the flight HUD (panorama/images/custom_game/tw/fly_*.png): wooden dash, aged dial faces
(airspeed, altimeter, tachometer, bank), compass card, needles, brass bezels, bomb lamps, ring-and-bead gunsight.
Also returns the CSS / XML for the tw_fly panel (used by tw_hud.py)."""
import os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from noise import fbm

SERIF = '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'
BASK = '/usr/share/fonts/truetype/baskerville/GFSBaskerville.otf'
S = 512                       # dial texture size


def font(sz, path=BASK):
    try: return ImageFont.truetype(path, sz)
    except Exception: return ImageFont.truetype(SERIF, sz)


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
            q = ang(t); d.ellipse((c + math.cos(q) * R * 0.93 - 7, c + math.sin(q) * R * 0.93 - 7, c + math.cos(q) * R * 0.93 + 7, c + math.sin(q) * R * 0.93 + 7), fill=(170, 30, 24, 255))
    steps = (len(marks) - 1) * minor
    for k in range(steps + 1):
        v = v0 + (v1 - v0) * k / steps; q = ang(v); big = k % minor == 0
        r0 = R * (0.80 if big else 0.87)
        d.line([(c + math.cos(q) * r0, c + math.sin(q) * r0), (c + math.cos(q) * R, c + math.sin(q) * R)], fill=ink, width=7 if big else 3)
    f = font(int(S * 0.10))
    for v, txt in marks:
        q = ang(v); x, y = c + math.cos(q) * R * 0.63, c + math.sin(q) * R * 0.63
        d.text((x, y), txt, font=f, fill=ink, anchor='mm')
    if title: d.text((c, c + S * 0.17), title, font=font(int(S * 0.062), SERIF), fill=ink, anchor='mm')
    if unit: d.text((c, c + S * 0.25), unit, font=font(int(S * 0.05)), fill=(170, 160, 135, 255), anchor='mm')
    return circle_mask(im, 6)


def card():
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im); c = S / 2
    d.ellipse((8, 8, S - 8, S - 8), fill=(30, 28, 24, 255))
    ink = (226, 214, 180, 255); R = S * 0.45
    for k in range(72):
        q = math.radians(k * 5 - 90); big = k % 6 == 0
        r0 = R * (0.80 if big else 0.88)
        d.line([(c + math.cos(q) * r0, c + math.sin(q) * r0), (c + math.cos(q) * R, c + math.sin(q) * R)], fill=ink, width=6 if big else 3)
    f = font(int(S * 0.13)); f2 = font(int(S * 0.07))
    for k, txt in enumerate(['N', '3', '6', 'E', '12', '15', 'S', '21', '24', 'W', '30', '33']):
        q = math.radians(k * 30 - 90); x, y = c + math.cos(q) * R * 0.62, c + math.sin(q) * R * 0.62
        lab = Image.new('RGBA', (S // 3, S // 3), (0, 0, 0, 0))
        ImageDraw.Draw(lab).text((S // 6, S // 6), txt, font=f if len(txt) == 1 else f2, fill=(200, 40, 30, 255) if txt == 'N' else ink, anchor='mm')
        lab = lab.rotate(-k * 30, resample=Image.BICUBIC)
        im.alpha_composite(lab, (int(x - S // 6), int(y - S // 6)))
    return im


def needle(color=(236, 228, 200), length=0.42, tail=0.12, width=0.022):
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im); c = S / 2
    w = S * width
    d.polygon([(c, c - S * length), (c + w, c), (c, c + S * tail), (c - w, c)], fill=color + (255,), outline=(20, 18, 14, 255))
    d.ellipse((c - S * 0.05, c - S * 0.05, c + S * 0.05, c + S * 0.05), fill=(40, 36, 30, 255), outline=(170, 140, 80, 255), width=4)
    return im.filter(ImageFilter.GaussianBlur(0.6))


def lubber():
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im); c = S / 2
    d.polygon([(c, S * 0.10), (c + 16, S * 0.02), (c - 16, S * 0.02)], fill=(240, 200, 90, 255))
    d.line([(c, S * 0.10), (c, S * 0.9)], fill=(240, 200, 90, 120), width=3)
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
    # glass glint
    g = np.clip(1 - np.hypot(x - 0.36, y - 0.3) / 0.28, 0, 1) ** 2 * (r < 0.86)
    a[..., :3] += (g * 255)[..., None] * (1 - ring[..., None]); a[..., 3] = np.maximum(a[..., 3], g * 70)
    # screws
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    for q in (45, 135, 225, 315):
        qq = math.radians(q); x0, y0 = S / 2 + math.cos(qq) * S * 0.465, S / 2 + math.sin(qq) * S * 0.465
        d.ellipse((x0 - 9, y0 - 9, x0 + 9, y0 + 9), fill=(120, 96, 50, 255)); d.line([(x0 - 7, y0), (x0 + 7, y0)], fill=(50, 40, 20, 255), width=3)
    return im


def dash(w=1920, h=330):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    g = fbm(x / 900.0, y / 40.0, 0.3, 4, seed=61) + 0.35 * np.sin((y + 30 * fbm(x / 300.0, y / 80.0, 1.1, 3, seed=62)) / 3.1)
    base = np.array([96, 58, 30], np.float32)
    a = base[None, None] * (0.78 + 0.22 * g[..., None])
    a[..., 0] += 18 * fbm(x / 120.0, y / 120.0, 2.0, 2, seed=63)
    edge = np.clip(1 - np.abs(y - 0) / 6, 0, 1)
    a = a * (1 - 0.35 * edge[..., None])
    arch = (y < 40 * (1 - ((x - w / 2) / (w / 2)) ** 2) + 0)    # cut a gentle arch along the top edge
    alpha = np.where(arch, 0, 255).astype(np.float32)
    # leather coaming along the top
    top = 40 * (1 - ((x - w / 2) / (w / 2)) ** 2)
    rim = (y >= top) & (y < top + 22)
    a[rim] = np.array([40, 26, 18], np.float32) * (0.85 + 0.15 * g[rim, None])
    out = np.dstack([np.clip(a, 0, 255), alpha]).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')


def lamp(on):
    im = Image.new('RGBA', (96, 96), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse((4, 4, 92, 92), fill=(150, 118, 60, 255))
    d.ellipse((16, 16, 80, 80), fill=(255, 190, 70, 255) if on else (60, 40, 22, 255))
    if on: d.ellipse((26, 22, 46, 40), fill=(255, 245, 200, 255))
    return im


def sight(size=512):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im); c = size / 2
    col = (20, 18, 16, 230)
    for r, w in ((0.46, 6), (0.24, 4)):
        d.ellipse((c - size * r, c - size * r, c + size * r, c + size * r), outline=col, width=w)
    for q in (0, 90, 180, 270):
        qq = math.radians(q)
        d.line([(c + math.cos(qq) * size * 0.24, c + math.sin(qq) * size * 0.24), (c + math.cos(qq) * size * 0.46, c + math.sin(qq) * size * 0.46)], fill=col, width=4)
    d.ellipse((c - 7, c - 7, c + 7, c + 7), fill=(200, 160, 60, 255))
    return im


def counter_bg():
    im = Image.new('RGBA', (220, 76), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, 219, 75), 10, fill=(150, 118, 60, 255)); d.rounded_rectangle((8, 8, 211, 67), 6, fill=(16, 14, 12, 255))
    for k in range(1, 4): d.line([(8 + k * 51, 10), (8 + k * 51, 66)], fill=(70, 60, 50, 255), width=2)
    return im


def build(imgdir):
    os.makedirs(imgdir, exist_ok=True)
    P = lambda n: os.path.join(imgdir, n)
    dial([(0, '0'), (50, '50'), (100, '100'), (150, '150'), (200, '200'), (250, '250'), (300, '300')], title='VITESSE', unit='km/h', red=(250, 300), seed=1).save(P('fly_asi.png'))
    dial([(k, str(k)) for k in range(0, 11)], a0=0, a1=360, title='ALTIMETRE', unit='x 100 m', seed=2, minor=5).save(P('fly_alt.png'))
    dial([(k, str(k)) for k in range(4, 21, 2)], title='TOURS', unit='x 100 / min', red=(17, 20), seed=3).save(P('fly_rpm.png'))
    dial([(-60, '60'), (-30, '30'), (0, '0'), (30, '30'), (60, '60')], a0=-60, a1=60, title='INCLIN.', unit='', seed=4, minor=3).save(P('fly_bank.png'))
    card().save(P('fly_card.png')); lubber().save(P('fly_lubber.png'))
    needle().save(P('fly_needle.png')); needle((236, 210, 120), 0.40, 0.08).save(P('fly_needle_short.png'))
    bezel().save(P('fly_bezel.png'))
    lamp(False).save(P('fly_lamp_off.png')); lamp(True).save(P('fly_lamp_on.png'))
    counter_bg().save(P('fly_counter.png'))


def css_xml(rule, IMG, lab):
    G = 150
    rule('#tw_fly', width='100%', height='100%', opacity='0', transition_property='opacity', transition_duration='0.3s')
    rule('#tw_fly.show', opacity='1')
    rule('#tw_dash', width='100%', height='240px', vertical_align='bottom', flow_children='right', overflow='noclip')
    rule('#tw_dashrow', horizontal_align='center', vertical_align='bottom', margin_bottom='34px', flow_children='right', overflow='noclip')
    rule('.Gauge', width='%dpx' % G, height='%dpx' % G, margin_left='6px', margin_right='6px', overflow='noclip', opacity='0.92')
    rule('.GLayer', width='100%', height='100%', background_size='100% 100%', transition_property='transform', transition_duration='0.12s')
    rule('.GFace', width='100%', height='100%', background_size='100% 100%')
    for n in ('asi', 'alt', 'rpm', 'bank'):
        rule('#tw_g_%s' % n, background_image='url("%sfly_%s.png")' % (IMG, n))
    rule('.Needle', background_image='url("%sfly_needle.png")' % IMG)
    rule('#tw_card', background_image='url("%sfly_card.png")' % IMG)
    rule('.Lubber', background_image='url("%sfly_lubber.png")' % IMG)
    rule('.Bezel', background_image='url("%sfly_bezel.png")' % IMG)
    for i in range(72):
        rule('.GLayer.a%d' % i, transform='rotateZ(%ddeg)' % (i * 5))
    rule('#tw_side', flow_children='down', margin_left='24px', vertical_align='center')
    rule('#tw_counter', width='160px', height='56px', background_image='url("%sfly_counter.png")' % IMG, background_size='100% 100%')
    rule('#tw_ammo_txt', font_family='"Courier New", monospace', font_size='32px', color='#f0e6c8', horizontal_align='center', vertical_align='center', letter_spacing='14px', margin_left='12px')
    rule('.SideCap', font_family='Georgia, "Times New Roman", serif', font_size='18px', color='#e8d4a0', margin_top='4px', horizontal_align='center')
    rule('#tw_lamps', flow_children='right', horizontal_align='center', margin_top='10px')
    rule('.Lamp', width='40px', height='40px', margin_left='8px', margin_right='8px', background_image='url("%sfly_lamp_off.png")' % IMG, background_size='100% 100%')
    rule('.Lamp.on', background_image='url("%sfly_lamp_on.png")' % IMG)
    rule('#tw_alt_drum', font_family='"Courier New", monospace', font_size='16px', color='#e8dcc0', horizontal_align='center', margin_top='%dpx' % int(G * 0.62))
    rule('#tw_hdg_txt', font_family='"Courier New", monospace', font_size='18px', color='#f0d48a', horizontal_align='center', margin_top='%dpx' % int(G * 0.68))
    rule('#tw_fly_info', font_family='Georgia, "Times New Roman", serif', font_size='22px', color='#f0d48a', horizontal_align='center', vertical_align='bottom', margin_bottom='4px')
    rule('#tw_fly_help', font_family='Georgia, "Times New Roman", serif', font_size='17px', color='#d8c8a0', horizontal_align='right', vertical_align='bottom', margin_right='30px', margin_bottom='210px')

    def gauge(face, layer_id, layer_cls, extra=''):
        return ('<Panel class="Gauge" hittest="false"><Panel id="%s" class="GFace" hittest="false" />'
                '<Panel id="%s" class="GLayer %s" hittest="false" />%s<Panel class="GFace Bezel" hittest="false" /></Panel>' % (face, layer_id, layer_cls, extra))
    compass = ('<Panel class="Gauge" hittest="false"><Panel id="tw_card" class="GLayer" hittest="false" />'
               '<Panel class="GFace Lubber" hittest="false" />%s<Panel class="GFace Bezel" hittest="false" /></Panel>' % lab('tw_hdg_txt'))
    xml = ('<Panel id="tw_fly" hittest="false">'
           '<Label id="tw_fly_help" text="MOUSE aim   A/D roll   W/S throttle   LMB guns   RMB bomb" />'
           '<Panel id="tw_dash" hittest="false"><Panel id="tw_dashrow" hittest="false">'
           + gauge('tw_g_bank', 'tw_n_bank', 'Needle')
           + gauge('tw_g_asi', 'tw_n_asi', 'Needle')
           + compass
           + gauge('tw_g_alt', 'tw_n_alt', 'Needle', lab('tw_alt_drum'))
           + gauge('tw_g_rpm', 'tw_n_rpm', 'Needle')
           + '<Panel id="tw_side" hittest="false"><Panel id="tw_counter" hittest="false">%s</Panel><Label class="SideCap" text="CARTOUCHES" />'
             '<Panel id="tw_lamps" hittest="false"><Panel id="tw_bomb1" class="Lamp" hittest="false" /><Panel id="tw_bomb2" class="Lamp" hittest="false" /></Panel>'
             '<Label class="SideCap" text="BOMBES" /></Panel>' % lab('tw_ammo_txt')
           + '</Panel>%s</Panel></Panel>' % lab('tw_fly_info'))
    return xml
