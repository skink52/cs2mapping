"""IRONFRAME Sprawl detail pass: the materials (matkit) of tools/arenas/sprawl_detail.py, all under materials/ifr/sprawl/ with the
prefix d_ (compiled by rebuild_sprawl.sh's `--also materials/ifr/sprawl/*.vmat`).

Every material here except the storefronts carries `mapbuilder.nonsolid`: the detail meshes are dressing, mechs and bullets must pass
through them (mech movement sweeps the world: docs/DESIGN.md). Scale: 4 px = 1 u on the 256-u storefront tile; human scale on this
map is S = 0.6 of CS2's (a storey = 77 u, a 300-u mech = 4 storeys = ~13-15 m).
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', '..', '..', 'create')))
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import matkit

MDIR = 'materials/ifr/sprawl'
JP = ['YuGothB.ttc', 'msgothic.ttc', 'msyhbd.ttc', 'arialbd.ttf']
EN = ['bahnschrift.ttf', 'arialbd.ttf']
KANJI = ['ラーメン', '薬局', 'ホテル', '質屋', '電器', '酒場', '寿司', '麻雀', 'カラオケ', '居酒屋', '喫茶', '銀行', '書店', '理容', '弁当', '24時間', '不動産', '歯科']
BRANDS = [('NEO-COLA', 'のどごし爽快'), ('ミライ銀行', 'MIRAI BANK'), ('KUROGANE', '黒鉄重工業'), ('ARMS EXPO 2099', '機動兵器見本市'), ('サイバー麺', 'CYBER NOODLE'),
          ('HOTEL ORBIT', '軌道ホテル'), ('IRONFRAME LEAGUE', '今夜決勝'), ('DRONE TAXI', '空のタクシー'), ('超電磁', 'HYPER MAGNETIC'), ('TELECOM 9G', '全域接続'),
          ('SAKURA BEER', '桜麦酒'), ('PACHINKO KING', 'パチンコ王')]
PAL = [((255, 40, 150), (60, 10, 90)), ((30, 200, 255), (10, 30, 110)), ((255, 170, 40), (140, 20, 20)), ((120, 255, 140), (10, 70, 60)),
       ((255, 255, 255), (200, 30, 40)), ((250, 230, 60), (30, 30, 30)), ((255, 90, 60), (40, 10, 60)), ((150, 120, 255), (20, 10, 70))]


def font(names, px):
    for n in names:
        try: return ImageFont.truetype(n, px)
        except OSError: pass
    return ImageFont.load_default()


def fit_text(d, text, box, names, fill, maxpx=None, stroke=0, stroke_fill=None):
    """draw text centred in box (x0, y0, x1, y1), as large as fits"""
    x0, y0, x1, y1 = box; w, h = x1 - x0, y1 - y0
    px = int(maxpx or h)
    while px > 6:
        f = font(names, px); bb = d.textbbox((0, 0), text, font=f, stroke_width=stroke)
        if bb[2] - bb[0] <= w * 0.94 and bb[3] - bb[1] <= h * 0.9: break
        px = int(px * 0.9)
    f = font(names, px); bb = d.textbbox((0, 0), text, font=f, stroke_width=stroke)
    d.text((x0 + (w - (bb[2] - bb[0])) / 2 - bb[0], y0 + (h - (bb[3] - bb[1])) / 2 - bb[1]), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)


def vtext(d, text, box, fill):
    x0, y0, x1, y1 = box; n = max(1, len(text)); ch = (y1 - y0) / n
    for i, c in enumerate(text): fit_text(d, c, (x0, y0 + i * ch, x1, y0 + (i + 1) * ch), JP, fill)


def led(img, pitch=4, dark=0.72):
    """LED wall look: a faint pixel grid"""
    a = np.asarray(img, float).copy()
    a[::pitch] *= dark; a[:, ::pitch] *= dark
    return np.clip(a, 0, 255).astype(np.uint8)


def ad(seed, w=1024, h=512):
    """one LED advertising screen: a two-colour gradient, a graphic, a brand and a tag line"""
    r = np.random.RandomState(seed)
    (c1, c2) = PAL[seed % len(PAL)]; brand, tag = BRANDS[seed % len(BRANDS)]
    y, x = np.mgrid[0:h, 0:w]
    t = np.clip((x / w * r.uniform(0.3, 0.9) + y / h * r.uniform(0.3, 0.9)), 0, 1)[..., None]
    img = Image.fromarray((np.array(c2) * (1 - t) * 0.9 + np.array(c1) * t * 0.55).astype(np.uint8))
    d = ImageDraw.Draw(img)
    kind = seed % 4
    if kind == 0: d.ellipse([w * 0.62, -h * 0.2, w * 1.1, h * 0.75], fill=c1)
    elif kind == 1:
        for k in range(6): d.polygon([(w * (0.55 + k * 0.09), h), (w * (0.62 + k * 0.09), h), (w * (0.82 + k * 0.09), 0), (w * (0.75 + k * 0.09), 0)], fill=tuple(int(v * (0.5 + 0.08 * k)) for v in c1))
    elif kind == 2: d.rectangle([w * 0.04, h * 0.08, w * 0.96, h * 0.92], outline=c1, width=10)
    else:
        for k in range(5): d.arc([w * 0.5 - k * 60, h * 0.1 - k * 30, w * 1.2 + k * 60, h * 1.5 + k * 30], 180, 300, fill=c1, width=14)
    fit_text(d, brand, (w * 0.05, h * 0.16, w * 0.9, h * 0.62), JP if any(ord(c) > 255 for c in brand) else EN, (255, 255, 255), stroke=4, stroke_fill=tuple(int(v * 0.25) for v in c2))
    fit_text(d, tag, (w * 0.08, h * 0.64, w * 0.8, h * 0.86), JP if any(ord(c) > 255 for c in tag) else EN, c1)
    return led(img)


def poster(seed, w=256, h=512):
    """a vertical lightbox poster / sign: colour field, vertical kanji, a small latin strap"""
    (c1, c2) = PAL[(seed * 3 + 1) % len(PAL)]
    img = Image.new('RGB', (w, h), tuple(int(v * 0.8) for v in c2)); d = ImageDraw.Draw(img)
    d.rectangle([8, 8, w - 9, h - 9], outline=c1, width=6)
    vtext(d, KANJI[seed % len(KANJI)], (w * 0.2, h * 0.06, w * 0.8, h * 0.8), (255, 255, 255))
    b = BRANDS[(seed * 5) % len(BRANDS)][0]
    fit_text(d, b, (w * 0.08, h * 0.83, w * 0.92, h * 0.95), JP if any(ord(c) > 255 for c in b) else EN, c1)
    return np.asarray(img)


def ticker(seed, w=1024, h=256):      # power-of-two sides: the compiler refuses 1024 x 192 ("Cannot filter non-power-of-two texture")
    img = Image.new('RGB', (w, h), (8, 6, 4)); d = ImageDraw.Draw(img)
    col = [(255, 170, 40), (60, 220, 255), (255, 70, 60)][seed % 3]
    text = ['決勝 21:00  IRONFRAME LEAGUE', '豪雨警報  FLOOD WARNING', 'KUROGANE ▲4.2   MIRAI ▼1.1'][seed % 3]
    fit_text(d, text, (10, 10, w - 10, h - 10), JP, col)
    a = np.asarray(img, float); a[::4] *= 0.5; a[:, ::4] *= 0.5                      # dot matrix
    return np.clip(a, 0, 255).astype(np.uint8)


def storefront(seed, size=1024):
    """a street wall tile, 256 u wide x 256 u tall at uv scale 0.25, anchored at z = 0 (row 1024 = the pavement):
    rows 716-1024 the shops (4 bays of 64 u: lit glass with a door, a shutter, a noren curtain; a lit fascia sign over each),
    rows 224-716 two upper storeys (windows, some lit, vertical lightbox signs), rows 0-224 a third storey band (so the tile also
    wraps on the 400-u podiums). Alpha = self-illumination."""
    r = np.random.RandomState(seed)
    base = (matkit.fbm(size, 16, seed) * 22 + 50)
    wallc = np.array([(1.0, 0.97, 0.92), (0.9, 0.95, 1.0), (1.0, 0.9, 0.85), (0.85, 0.85, 0.85)][seed % 4])
    img = Image.fromarray((base[..., None] * wallc).astype(np.uint8)); mask = Image.new('L', (size, size), 0)
    d = ImageDraw.Draw(img); m = ImageDraw.Draw(mask)
    glass = [(255, 214, 160), (255, 236, 200), (190, 230, 255), (240, 240, 230), (255, 222, 170), (255, 190, 215)]
    def windows(y0, y1):
        for b in range(8):
            x0 = b * 128 + 20; x1 = x0 + 88
            if r.uniform() < 0.42:
                c = tuple(int(v * r.uniform(0.55, 0.95)) for v in glass[r.randint(len(glass))])
                d.rectangle([x0, y0, x1, y1], fill=c); m.rectangle([x0, y0, x1, y1], fill=int(r.uniform(140, 230)))
                if r.uniform() < 0.4:
                    for yy in range(y0, y1, 7): d.line([x0, yy, x1, yy], fill=tuple(int(v * 0.4) for v in c))
            else: d.rectangle([x0, y0, x1, y1], fill=(16, 20, 28))
            d.rectangle([x0, y0, x1, y1], outline=(28, 28, 30), width=3); d.line([(x0 + x1) // 2, y0, (x0 + x1) // 2, y1], fill=(28, 28, 30), width=3)
            d.rectangle([x0 - 6, y1 + 2, x1 + 6, y1 + 8], fill=(88, 88, 86))                                  # sill
    windows(40, 190); windows(270, 430); windows(516, 676)
    for yy in (224, 470, 716): d.rectangle([0, yy - 12, size, yy], fill=(34, 34, 38))                         # floor bands
    for b in range(4):                                                                                        # lightbox signs between the upper windows
        if r.uniform() < 0.7:
            x = b * 256 + 118 + r.randint(-4, 5); y0 = r.choice([250, 300, 496]); y1 = min(700, y0 + r.randint(150, 400))
            c1, c2 = PAL[r.randint(len(PAL))]
            d.rectangle([x, y0, x + 22, y1], fill=c2, outline=c1, width=2); m.rectangle([x, y0, x + 22, y1], fill=255)
            vtext(d, KANJI[r.randint(len(KANJI))], (x + 2, y0 + 4, x + 20, y1 - 4), (255, 255, 255))
    for b in range(4):                                                                                        # the shops
        x0, x1 = b * 256 + 10, (b + 1) * 256 - 10; y0, y1 = 790, 1016
        d.rectangle([b * 256, 716, b * 256 + 9, 1024], fill=(40, 40, 44)); d.rectangle([(b + 1) * 256 - 9, 716, (b + 1) * 256, 1024], fill=(40, 40, 44))
        c1, c2 = PAL[r.randint(len(PAL))]
        d.rectangle([x0, 722, x1, 782], fill=c2); m.rectangle([x0, 722, x1, 782], fill=235)                    # fascia sign
        word = KANJI[r.randint(len(KANJI))] if r.uniform() < 0.7 else BRANDS[r.randint(len(BRANDS))][0]
        fit_text(d, word, (x0 + 4, 724, x1 - 4, 780), JP if any(ord(c) > 255 for c in word) else EN, c1 if sum(c1) > 380 else (255, 255, 255))
        kind = r.choice(['glass', 'glass', 'glass', 'shutter', 'noren'])
        if kind == 'shutter':
            d.rectangle([x0, y0, x1, y1], fill=(98, 100, 104))
            for yy in range(y0, y1, 9): d.line([x0, yy, x1, yy], fill=(62, 64, 68), width=2)
            if r.uniform() < 0.6:                                                                             # a tag
                pts = [(r.randint(x0 + 20, x1 - 20), r.randint(y0 + 60, y1 - 30)) for _ in range(6)]
                d.line(pts, fill=PAL[r.randint(len(PAL))][0], width=5, joint='curve')
        else:
            c = tuple(int(v * r.uniform(0.7, 1.0)) for v in glass[r.randint(len(glass))])
            d.rectangle([x0, y0, x1, y1], fill=c); m.rectangle([x0, y0, x1, y1], fill=225)
            for k in range(r.randint(3, 7)):                                                                  # goods / people silhouettes in the window
                sx = r.randint(x0 + 8, x1 - 40); sw = r.randint(14, 34); sh = r.randint(30, 110)
                d.rectangle([sx, y1 - sh, sx + sw, y1], fill=tuple(int(v * r.uniform(0.25, 0.6)) for v in c))
            dx = r.randint(x0 + 20, x1 - 90)                                                                  # the door
            d.rectangle([dx, y0 + 40, dx + 64, y1], outline=(24, 24, 28), width=5); d.line([dx + 32, y0 + 40, dx + 32, y1], fill=(24, 24, 28), width=4)
            d.line([x0, y0 + 40, x1, y0 + 40], fill=(24, 24, 28), width=5)
            if kind == 'noren':
                nc = [(40, 60, 140), (150, 30, 30), (240, 235, 220)][r.randint(3)]
                for k in range(5): d.rectangle([x0 + 6 + k * 46, y0, x0 + 46 + k * 46, y0 + 70], fill=nc)
                m.rectangle([x0, y0, x1, y0 + 70], fill=40)
        d.rectangle([x0, y0, x1, y1], outline=(22, 22, 26), width=4)
        d.rectangle([b * 256, 1016, (b + 1) * 256, 1024], fill=(60, 60, 60))                                  # plinth
    return np.dstack([np.asarray(img), np.asarray(mask)])


def vending(seed, w=256, h=512):
    c = [(225, 40, 40), (40, 90, 200), (235, 235, 235), (40, 150, 90)][seed % 4]
    img = Image.new('RGB', (w, h), c); mask = Image.new('L', (w, h), 50); d = ImageDraw.Draw(img); m = ImageDraw.Draw(mask)
    d.rectangle([18, 30, w - 19, 300], fill=(235, 245, 255)); m.rectangle([18, 30, w - 19, 300], fill=255)
    r = np.random.RandomState(seed)
    for row in range(3):
        for k in range(7):
            x = 26 + k * 30; y = 44 + row * 86
            d.rectangle([x, y, x + 20, y + 58], fill=tuple(int(v) for v in r.randint(40, 255, 3))); d.rectangle([x + 4, y + 66, x + 16, y + 72], fill=(255, 60, 40) if r.uniform() < 0.3 else (60, 120, 255))
    d.rectangle([150, 320, 230, 400], fill=(20, 20, 24)); d.rectangle([40, 430, w - 40, 480], fill=(15, 15, 18))
    fit_text(d, ['ドリンク', 'COLD', 'たばこ', 'お茶'][seed % 4], (20, 318, 140, 400), JP, (255, 255, 255))
    return np.dstack([np.asarray(img), np.asarray(mask)])


def kiosk(seed, w=512, h=256):
    c1, c2 = PAL[(seed * 2 + 3) % len(PAL)]
    img = Image.new('RGB', (w, h), (40, 42, 46)); mask = Image.new('L', (w, h), 0); d = ImageDraw.Draw(img); m = ImageDraw.Draw(mask)
    d.rectangle([0, 0, w, 62], fill=c2); m.rectangle([0, 0, w, 62], fill=240)
    fit_text(d, ['たこ焼き', 'KIOSK', '新聞・雑誌', 'おでん', 'TICKETS 切符', 'コーヒー'][seed % 6], (10, 4, w - 10, 58), JP, c1 if sum(c1) > 380 else (255, 255, 255))
    d.rectangle([24, 80, w - 24, 190], fill=(255, 226, 170)); m.rectangle([24, 80, w - 24, 190], fill=230)
    r = np.random.RandomState(seed)
    for k in range(14):
        x = r.randint(30, w - 60); d.rectangle([x, r.randint(120, 170), x + r.randint(10, 30), 190], fill=tuple(int(v) for v in r.randint(30, 200, 3)))
    d.rectangle([24, 80, w - 24, 190], outline=(20, 20, 22), width=5)
    for k in range(9): d.rectangle([24 + k * 52, 200, 66 + k * 52, 246], fill=tuple(int(v) for v in r.randint(60, 240, 3)))   # magazine rack
    return np.dstack([np.asarray(img), np.asarray(mask)])


def tram(w=1024, h=256):
    img = Image.new('RGB', (w, h), (232, 196, 60)); mask = Image.new('L', (w, h), 0); d = ImageDraw.Draw(img); m = ImageDraw.Draw(mask)
    d.rectangle([0, 150, w, 190], fill=(30, 70, 60)); d.rectangle([0, 190, w, h], fill=(210, 205, 195)); d.rectangle([0, 236, w, h], fill=(30, 30, 32))
    for k in range(8):
        x = 30 + k * 124
        d.rectangle([x, 40, x + 96, 140], fill=(255, 236, 190)); m.rectangle([x, 40, x + 96, 140], fill=235)
        d.rectangle([x, 40, x + 96, 140], outline=(30, 30, 32), width=5)
        if k in (1, 4, 6): d.rectangle([x + 20, 36, x + 76, 236], outline=(30, 30, 32), width=5)             # doors
    d.rectangle([0, 0, w, 28], fill=(60, 60, 62)); d.rectangle([420, 4, 600, 26], fill=(10, 10, 8)); m.rectangle([420, 4, 600, 26], fill=255)
    fit_text(d, '中央広場  7', (424, 5, 596, 25), JP, (255, 170, 40))
    return np.dstack([np.asarray(img), np.asarray(mask)])


def hwsign(seed, w=1024, h=512):
    img = Image.new('RGB', (w, h), (16, 96, 62)); d = ImageDraw.Draw(img)
    d.rounded_rectangle([10, 10, w - 11, h - 11], radius=30, outline=(240, 240, 235), width=10)
    top, bot, no = [('中央広場', 'CENTRAL PLAZA', '4'), ('湾岸線', 'BAYSHORE', 'B'), ('新都心', 'NEW CITY CENTER', '9'), ('出口 北', 'EXIT NORTH', '12')][seed % 4]
    fit_text(d, top, (190, 40, w - 60, 280), JP, (245, 245, 240)); fit_text(d, bot, (190, 300, w - 60, 440), EN, (245, 245, 240))
    d.rounded_rectangle([40, 60, 170, 190], radius=24, fill=(245, 245, 240)); fit_text(d, no, (50, 70, 160, 180), EN, (16, 96, 62))
    d.polygon([(105, 250), (165, 340), (125, 340), (125, 450), (85, 450), (85, 340), (45, 340)], fill=(245, 245, 240))
    return np.asarray(img)


def led_text(text, col, w=512, h=128):
    img = Image.new('RGB', (w, h), (6, 5, 4)); d = ImageDraw.Draw(img)
    fit_text(d, text, (8, 8, w - 8, h - 8), JP, col)
    a = np.asarray(img, float); a[::4] *= 0.5; a[:, ::4] *= 0.5
    return np.clip(a, 0, 255).astype(np.uint8)


def ac_front(size=128):
    img = Image.new('RGB', (size, size), (198, 196, 186)); d = ImageDraw.Draw(img)
    d.ellipse([14, 20, 100, 106], fill=(52, 54, 56)); d.ellipse([20, 26, 94, 100], outline=(120, 120, 116), width=3)
    for k in range(6): d.line([57, 63, 57 + 36 * np.cos(k * 1.047), 63 + 36 * np.sin(k * 1.047)], fill=(120, 120, 116), width=3)
    for yy in range(22, 106, 9): d.line([14, yy, 100, yy], fill=(150, 150, 146), width=1)
    d.rectangle([106, 22, 122, 60], fill=(170, 168, 160)); d.rectangle([0, 0, size - 1, size - 1], outline=(140, 138, 130), width=3)
    d.line([0, 112, size, 118], fill=(150, 120, 90), width=3)                                               # a rust streak
    return np.asarray(img)


def flat(rgbc, seed, size=128, amp=10, streak=0.0):
    n = matkit.fbm(size, 8, seed) - 0.5
    img = np.array(rgbc, float)[None, None] + n[..., None] * amp * 2
    if streak: img *= (1 - streak * matkit.fbm(size, 4, seed + 9)[:, :1] * np.linspace(0, 1, size)[:, None])[..., None]
    return np.clip(img, 0, 255).astype(np.uint8)


def marking(kind, size=256):
    """road paint as an alpha-tested plate: RGB paint (worn), alpha = where paint is. v runs along the road."""
    wear = matkit.fbm(size, 24, 5) * 0.6 + matkit.fbm(size, 64, 6) * 0.4
    a = np.zeros((size, size)); col = np.array((205, 205, 198), float)
    y, x = np.mgrid[0:size, 0:size]
    if kind == 'dash': a[: size // 2] = 1
    elif kind == 'solid': a[:] = 1
    elif kind == 'zebra': a[(x // (size // 8)) % 2 == 0] = 1
    elif kind == 'stop': a[:] = 1
    elif kind == 'yellow': a[:] = 1; col = np.array((215, 165, 30), float)
    elif kind == 'hatch': a[((x + y) // (size // 8)) % 2 == 0] = 1; col = np.array((215, 165, 30), float)
    elif kind == 'chevron':
        a[:] = 1; img = np.where((((np.abs(x - size / 2) + y) // (size // 6)) % 2 == 0)[..., None], np.array((200, 40, 35)), np.array((225, 225, 220)))
    elif kind == 'arrow':
        im = Image.new('L', (size, size), 0); d = ImageDraw.Draw(im)
        d.polygon([(size * 0.5, size * 0.04), (size * 0.86, size * 0.42), (size * 0.62, size * 0.42), (size * 0.62, size * 0.96), (size * 0.38, size * 0.96), (size * 0.38, size * 0.42), (size * 0.14, size * 0.42)], fill=255)
        a = np.asarray(im) / 255.0
    elif kind == 'turn':
        im = Image.new('L', (size, size), 0); d = ImageDraw.Draw(im)
        d.line([(size * 0.6, size * 0.96), (size * 0.6, size * 0.4), (size * 0.3, size * 0.4)], fill=255, width=int(size * 0.14))
        d.polygon([(size * 0.06, size * 0.4), (size * 0.34, size * 0.18), (size * 0.34, size * 0.62)], fill=255)
        a = np.asarray(im) / 255.0
    elif kind == 'helipad':
        im = Image.new('L', (size, size), 0); d = ImageDraw.Draw(im)
        d.ellipse([8, 8, size - 9, size - 9], outline=255, width=14); fit_text(d, 'H', (size * 0.25, size * 0.2, size * 0.75, size * 0.8), EN, 255)
        a = np.asarray(im) / 255.0; col = np.array((225, 190, 40), float)
    elif kind == 'manhole':
        im = Image.new('L', (size, size), 0); d = ImageDraw.Draw(im); d.ellipse([4, 4, size - 5, size - 5], fill=255)
        a = np.asarray(im) / 255.0
        g = 58 + 26 * ((x // 16 + y // 16) % 2) + 20 * (np.hypot(x - size / 2, y - size / 2) > size * 0.42)
        img = np.stack([g * 1.0, g * 0.95, g * 0.88], -1)
    elif kind == 'bus':
        im = Image.new('L', (size, size), 0); d = ImageDraw.Draw(im); vtext(d, 'バス', (size * 0.2, size * 0.05, size * 0.8, size * 0.95), 255)
        a = np.asarray(im) / 255.0; col = np.array((215, 165, 30), float)
    if kind not in ('chevron', 'manhole'): img = col[None, None] * (0.75 + 0.25 * wear)[..., None]
    if kind not in ('manhole', 'chevron'): a = a * (wear > 0.28)                                               # worn through
    return np.dstack([np.clip(img, 0, 255).astype(np.uint8), (a * 255).astype(np.uint8)])


def puddle(seed, size=256):
    n = matkit.fbm(size, 3, seed) * 0.7 + matkit.fbm(size, 9, seed + 1) * 0.3
    y, x = np.mgrid[0:size, 0:size]; rad = np.hypot(x - size / 2, y - size / 2) / (size / 2)
    a = np.clip((n - 0.34 - 0.5 * rad ** 3) * 6, 0, 1)
    rgb = np.zeros((size, size, 3), np.uint8); rgb[:] = (10, 12, 16)
    return np.dstack([rgb, (a * 200).astype(np.uint8)])


def _write(content, name, img, nonsolid=True, **kw):
    path = matkit.write_material(content, MDIR, name, img, **kw)
    if nonsolid:
        f = os.path.join(content, *path.split('/'))
        t = open(f, encoding='utf-8').read()
        if 'mapbuilder.nonsolid' not in t:
            t = t.replace('\tSystemAttributes', '\tAttributes\n\t{\n\t\t"mapbuilder.nonsolid" "1"\n\t}\n\tSystemAttributes', 1)
            open(f, 'w', encoding='utf-8').write(t)
    return path


SOLID_COLOURS = dict(   # name: (rgb, roughness, metalness)
    metal_dark=((44, 46, 50), 0.45, 0.6), metal_grey=((118, 122, 126), 0.5, 0.5), metal_galv=((150, 156, 160), 0.32, 0.8), white=((214, 214, 208), 0.55, 0.0),
    yellow=((214, 168, 34), 0.55, 0.0), red=((168, 42, 36), 0.5, 0.0), green=((36, 104, 70), 0.5, 0.0), blue=((40, 76, 150), 0.5, 0.0), orange=((226, 104, 30), 0.5, 0.0),
    rubber=((22, 22, 24), 0.8, 0.0), conc=((126, 124, 120), 0.82, 0.0), conc_dark=((70, 70, 72), 0.8, 0.0), stone=((176, 170, 158), 0.5, 0.0),
    wood=((112, 82, 52), 0.75, 0.0), glass=((18, 26, 34), 0.06, 0.2), rust=((112, 64, 40), 0.7, 0.3), hedge=((34, 66, 36), 0.9, 0.0), tarp=((40, 70, 140), 0.6, 0.0),
    beige=((196, 188, 164), 0.6, 0.0))
GLOWS = dict(white=((225, 238, 255), 5.0), warm=((255, 206, 150), 5.0), sodium=((255, 150, 60), 6.0), cyan=((60, 220, 255), 6.0), magenta=((255, 60, 200), 6.0),
             amber=((255, 170, 40), 6.0), red=((255, 36, 24), 7.0), green=((60, 255, 130), 6.0))


def materials(content):
    """write every detail material; -> {key: material path}"""
    out = {}
    for k, (c, rough, metal) in SOLID_COLOURS.items():
        out[k] = _write(content, 'd_' + k, flat(c, sum(map(ord, k)) % 97, streak=0.25 if k in ('white', 'beige', 'metal_galv', 'conc') else 0.0), roughness=rough, metalness=metal)
    for k, (c, glow) in GLOWS.items():
        out['e_' + k] = _write(content, 'd_e_' + k, flat(c, 3, 32, amp=0), kind='emissive', roughness=0.5, glow=glow)
    for k in range(8): out['screen_%d' % k] = _write(content, 'd_screen_%d' % k, ad(k), kind='emissive', roughness=0.25, glow=3.2)
    for k in range(8): out['poster_%d' % k] = _write(content, 'd_poster_%d' % k, poster(k), kind='emissive', roughness=0.3, glow=2.6)
    for k in range(4): out['billboard_%d' % k] = _write(content, 'd_billboard_%d' % k, ad(k + 8), kind='emissive', roughness=0.4, glow=1.4)
    for k in range(3): out['ticker_%d' % k] = _write(content, 'd_ticker_%d' % k, ticker(k), kind='emissive', roughness=0.3, glow=5.0)
    for k in range(4): out['shop_%d' % k] = _write(content, 'd_shop_%d' % k, storefront(300 + k), nonsolid=False, kind='emissive', roughness=0.35, glow=2.2)
    for k in range(4): out['vend_%d' % k] = _write(content, 'd_vend_%d' % k, vending(k), kind='emissive', roughness=0.3, glow=3.0)
    for k in range(6): out['kiosk_%d' % k] = _write(content, 'd_kiosk_%d' % k, kiosk(k), kind='emissive', roughness=0.4, glow=2.4)
    out['tram'] = _write(content, 'd_tram', tram(), kind='emissive', roughness=0.35, glow=2.0)
    for k in range(4): out['hwsign_%d' % k] = _write(content, 'd_hwsign_%d' % k, hwsign(k), kind='emissive', roughness=0.5, glow=0.9)
    out['led_amber'] = _write(content, 'd_led_amber', led_text('この先 冠水  FLOODING AHEAD', (255, 170, 40)), kind='emissive', roughness=0.3, glow=5.0)
    out['led_red'] = _write(content, 'd_led_red', led_text('通行止  ROAD CLOSED', (255, 60, 40)), kind='emissive', roughness=0.3, glow=5.0)
    out['ac'] = _write(content, 'd_ac', ac_front(), roughness=0.5)
    for kind in ('dash', 'solid', 'zebra', 'stop', 'yellow', 'hatch', 'chevron', 'arrow', 'turn', 'helipad', 'manhole', 'bus'):
        out['mk_' + kind] = _write(content, 'd_mk_' + kind, marking(kind), roughness=0.5 if kind != 'manhole' else 0.3, metalness=0.7 if kind == 'manhole' else 0.0, alpha='test')
    for k in range(3): out['puddle_%d' % k] = _write(content, 'd_puddle_%d' % k, puddle(40 + k), roughness=0.03, alpha='translucent')
    return out


if __name__ == '__main__':
    m = materials(sys.argv[1]); print('%d detail materials -> %s/%s' % (len(m), sys.argv[1], MDIR))
