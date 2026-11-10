"""hud_images.py: every picture the IRONFRAME HUD uses, drawn with Pillow (no source art): weapon family icons, part
pictures for the garage (cards with the family glyph; a real render in preview/frames/<key>.png replaces a frame's glyph when
present), the reticle rings and brackets, the radar backdrop, threat chevrons and badges.

usage: hud_images.py <addon out> [<parts.json>]    (hud.py calls write(img_dir, parts) itself)
Everything is drawn at 4x and shrunk with a Lanczos filter (anti-aliased, no pixel art since Nov 2026). Icons, badges and card glyphs
get the same baked backlit-neon treatment as the HUD type (tools/hud_font.py): a near-white core tinted toward the colour, a thin dark
keyline and two gaussian halo layers in the colour, inset so the halo is never cut.
"""
import os, sys, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WHITE = (255, 255, 255, 255)
SS = 4                       # supersampling

ARM_FAMILIES = ['rifle', 'gatling', 'shotgun', 'laser', 'bazooka', 'grenade', 'blade', 'plasma', 'rail', 'handmsl', 'shield', 'smg',
                'pilebunker', 'sniper', 'burstrifle', 'flamer', 'eshotgun', 'heavyblade']
SHOULDER_FAMILIES = ['vm6', 'dualmsl', 'lasercannon', 'grenadecannon', 'autocannon', 'flak', 'pulseshield', 'repair', 'decoy', 'vm12',
                     'minelayer', 'orbitdrones', 'multimsl', 'clusterart']
FAMILIES = ARM_FAMILIES + SHOULDER_FAMILIES
KIND_GLYPH = {'generator': 'gen', 'booster': 'bst', 'fcs': 'fcs', 'paint': 'paint'}


def _canvas(size):
    s = size * SS
    img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), s


def _shrink(img, size, unit=None):
    """supersampled drawing -> size x size, anti-aliased (Lanczos). `unit` is ignored (it was the pixel-art block size)"""
    return img.resize((size, size), Image.LANCZOS)


# the HUD palette (tools/hud.py PAL) for the neon halos
CY = (56, 216, 255); ACC = (159, 216, 240); GOLD = (255, 210, 90); T_ORANGE = (255, 120, 50); CT_BLUE = (95, 211, 255)


def neon(drawn, size, col, inset=0.8, boost=1.0, mono=True):
    """backlit neon from a supersampled RGBA drawing (any square size): the shape shrunk to `inset` of the picture, a near-white
    core tinted toward `col` (mono) or toward its own colours, a thin dark keyline and two baked gaussian halo layers in `col`
    (hud_font.Master.render, the same recipe as the glyphs)"""
    S = size * SS
    inner = max(1, int(round(S * inset)))
    src = drawn.convert('RGBA').resize((inner, inner), Image.LANCZOS)
    big = Image.new('RGBA', (S, S), (0, 0, 0, 0)); big.paste(src, ((S - inner) // 2, (S - inner) // 2))
    m = big.getchannel('A')
    core = np.asarray(m.resize((size, size), Image.LANCZOS), np.float32) / 255
    key = np.asarray(m.filter(ImageFilter.MaxFilter(2 * int(SS * 0.75) + 1)).resize((size, size), Image.LANCZOS), np.float32) / 255
    small = m.resize((size, size), Image.BOX)
    sa, sb = 0.022 * size * (1 + 0.15 * (boost - 1)), 0.07 * size * (1 + 0.5 * (boost - 1))
    ga = np.asarray(small.filter(ImageFilter.GaussianBlur(sa)), np.float32) / 255
    gb = np.asarray(small.filter(ImageFilter.GaussianBlur(sb)), np.float32) / 255
    glow = np.clip(ga * 1.25 * boost + gb * 1.2 * boost, 0, 1) * 0.96
    col = np.array(col[:3], np.float32); white = np.array([255, 255, 255], np.float32)
    if mono: face = np.broadcast_to(col * 0.18 + white * 0.82, (size, size, 3))
    else:
        pm = np.asarray(big, np.float32)
        pm[..., :3] *= pm[..., 3:4] / 255                                   # premultiply, shrink, un-premultiply
        sm = np.asarray(Image.fromarray(np.clip(pm, 0, 255).astype(np.uint8), 'RGBA').resize((size, size), Image.LANCZOS), np.float32)
        a = np.maximum(sm[..., 3:4], 1) / 255
        rgb = np.clip(sm[..., :3] / a, 0, 255)
        face = rgb * 0.55 + white * 0.45
    out = np.zeros((size, size, 4), np.float32)
    out[..., :3] = col; out[..., 3] = glow
    a_key = np.clip(key * 0.85, 0, 1)
    ra = a_key + out[..., 3] * (1 - a_key)
    out[..., :3] = np.where(ra[..., None] > 0, (out[..., :3] * out[..., 3:4] * (1 - a_key[..., None]) + np.array([4, 8, 12], np.float32) * a_key[..., None]) / np.maximum(ra[..., None], 1e-6), 0)
    out[..., 3] = ra
    rb = core + out[..., 3] * (1 - core)
    out[..., :3] = np.where(rb[..., None] > 0, (face * core[..., None] + out[..., :3] * out[..., 3:4] * (1 - core[..., None])) / np.maximum(rb[..., None], 1e-6), 0)
    out[..., 3] = rb * 255
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), 'RGBA')


def _font(px):
    for p in ('C:/Windows/Fonts/arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        if os.path.exists(p): return ImageFont.truetype(p, px)
    return ImageFont.load_default()


# ---------------------------------------------------------------- weapon family icons (line art, white)
def _line(d, pts, w, col=WHITE):
    d.line([(x * SS, y * SS) for x, y in pts], fill=col, width=int(w * SS), joint='curve')


def _rect(d, x0, y0, x1, y1, w=0, fill=None, col=WHITE):
    d.rectangle([x0 * SS, y0 * SS, x1 * SS, y1 * SS], outline=col if w else None, width=int(w * SS), fill=fill)


def _ellipse(d, x0, y0, x1, y1, w=0, fill=None, col=WHITE):
    d.ellipse([x0 * SS, y0 * SS, x1 * SS, y1 * SS], outline=col if w else None, width=int(w * SS) if w else 0, fill=fill)


def _poly(d, pts, fill=None, w=0, col=WHITE):
    d.polygon([(x * SS, y * SS) for x, y in pts], fill=fill, outline=col if w else None, width=int(w * SS) if w else 0)


def _missile(d, cx, top, h, w):
    """a missile pointing up, nose at `top`"""
    _poly(d, [(cx, top), (cx + w / 2, top + w), (cx + w / 2, top + h), (cx - w / 2, top + h), (cx - w / 2, top + w)], fill=WHITE)
    _poly(d, [(cx - w / 2, top + h - w), (cx - w, top + h), (cx - w / 2, top + h)], fill=WHITE)
    _poly(d, [(cx + w / 2, top + h - w), (cx + w, top + h), (cx + w / 2, top + h)], fill=WHITE)


def icon(family, size=96, unit=None, col=CY, plain=False):
    """a weapon family icon: the silhouette drawn on a 96 grid, as backlit neon in `col` (plain=True: the bare white shape)"""
    img, d, s = _canvas(96)
    f = family
    if f in ('rifle', 'smg'):
        long = f == 'rifle'
        _rect(d, 10 if long else 22, 42, 86, 52, fill=WHITE)                  # barrel/receiver
        _rect(d, 56, 36, 84, 58, fill=WHITE)                                   # body
        _poly(d, [(84, 40), (94, 44), (94, 56), (84, 58)], fill=WHITE)         # stock
        _poly(d, [(60, 58), (72, 58), (68, 78), (58, 78)], fill=WHITE)         # magazine
        if long: _rect(d, 30, 36, 46, 42, fill=WHITE)                          # sight
    elif f == 'gatling':
        for y in (36, 46, 56): _rect(d, 8, y, 60, y + 6, fill=WHITE)
        _ellipse(d, 54, 28, 84, 68, fill=WHITE)
        _rect(d, 72, 44, 92, 52, fill=WHITE)
    elif f == 'shotgun':
        _rect(d, 6, 40, 70, 50, fill=WHITE)
        _rect(d, 6, 52, 70, 58, fill=WHITE)
        _rect(d, 30, 60, 50, 66, fill=WHITE)
        _poly(d, [(68, 36), (92, 42), (92, 62), (68, 60)], fill=WHITE)
    elif f in ('laser', 'lasercannon'):
        big = f == 'lasercannon'
        _rect(d, 30, 40 if big else 44, 90, 56 if big else 52, fill=WHITE)
        _ellipse(d, 6, 32, 38, 64, w=5)
        _ellipse(d, 17, 43, 27, 53, fill=WHITE)
        for a in (-30, 0, 30):
            r = math.radians(a)
            _line(d, [(22 - 18 * math.cos(r), 48 - 18 * math.sin(r)), (22 - 30 * math.cos(r), 48 - 30 * math.sin(r))], 3)
        if big: _rect(d, 50, 56, 70, 72, fill=WHITE)
    elif f == 'bazooka':
        _rect(d, 8, 36, 80, 60, fill=WHITE)
        _poly(d, [(80, 30), (94, 36), (94, 60), (80, 66)], fill=WHITE)
        _rect(d, 36, 60, 50, 74, fill=WHITE)
    elif f == 'grenade':
        _ellipse(d, 54, 50, 84, 80, fill=WHITE)
        _rect(d, 64, 42, 74, 52, fill=WHITE)
        pts = [(12 + t * 0.6, 70 - 50 * math.sin(math.pi * t / 60)) for t in range(0, 61, 4)]
        _line(d, pts, 4)
    elif f == 'grenadecannon':
        _poly(d, [(20, 70), (70, 20), (84, 34), (34, 84)], fill=WHITE)
        _rect(d, 10, 72, 50, 88, fill=WHITE)
        _ellipse(d, 70, 10, 90, 30, w=4)
    elif f == 'blade':
        _poly(d, [(18, 84), (26, 78), (80, 14), (86, 22), (28, 86)], fill=WHITE)
        _line(d, [(14, 66), (34, 86)], 6)
        _line(d, [(10, 90), (20, 80)], 6)
    elif f == 'plasma':
        _ellipse(d, 30, 30, 66, 66, fill=WHITE)
        _ellipse(d, 16, 16, 80, 80, w=4)
        for a in range(0, 360, 60):
            r = math.radians(a)
            _line(d, [(48 + 36 * math.cos(r), 48 + 36 * math.sin(r)), (48 + 44 * math.cos(r), 48 + 44 * math.sin(r))], 4)
    elif f == 'rail':
        _rect(d, 4, 44, 92, 50, fill=WHITE)
        for x in range(12, 60, 10): _rect(d, x, 36, x + 5, 58, fill=WHITE)
        _rect(d, 64, 38, 90, 60, fill=WHITE)
        _poly(d, [(72, 60), (84, 60), (80, 76), (70, 76)], fill=WHITE)
    elif f == 'handmsl':
        for i, cx in enumerate((24, 40, 56, 72)): _missile(d, cx, 20 + (i % 2) * 10, 48, 9)
    elif f == 'shield':
        _poly(d, [(20, 14), (76, 14), (76, 50), (48, 86), (20, 50)], w=5)
        _line(d, [(48, 26), (48, 72)], 4)
    elif f in ('vm6', 'vm12'):
        cols, rows = (3, 2) if f == 'vm6' else (4, 3)
        w = 10 if f == 'vm6' else 8
        for r in range(rows):
            for c in range(cols):
                cx = 48 + (c - (cols - 1) / 2) * (w * 2.4)
                _missile(d, cx, 14 + r * (72 / rows), 60 / rows, w)
    elif f == 'dualmsl':
        _missile(d, 34, 12, 72, 14); _missile(d, 62, 12, 72, 14)
    elif f == 'autocannon':
        _rect(d, 6, 44, 70, 52, fill=WHITE)
        _rect(d, 56, 34, 90, 62, fill=WHITE)
        _ellipse(d, 60, 60, 88, 88, fill=WHITE)
        _ellipse(d, 68, 68, 80, 80, fill=(0, 0, 0, 0))
    elif f == 'flak':
        for a in range(0, 360, 45):
            r = math.radians(a)
            _line(d, [(48 + 14 * math.cos(r), 48 + 14 * math.sin(r)), (48 + 40 * math.cos(r), 48 + 40 * math.sin(r))], 5)
        _ellipse(d, 36, 36, 60, 60, fill=WHITE)
    elif f == 'pulseshield':
        pts = [(48 + 38 * math.cos(math.radians(a)), 48 + 38 * math.sin(math.radians(a))) for a in range(30, 391, 60)]
        _poly(d, pts, w=5)
        _ellipse(d, 36, 36, 60, 60, w=4)
    elif f == 'repair':
        _rect(d, 38, 12, 58, 84, fill=WHITE); _rect(d, 12, 38, 84, 58, fill=WHITE)
    elif f == 'decoy':
        for a in (-50, -25, 0, 25, 50):
            r = math.radians(a - 90)
            _line(d, [(48, 84), (48 + 56 * math.cos(r), 84 + 56 * math.sin(r))], 3)
            _ellipse(d, 48 + 56 * math.cos(r) - 6, 84 + 56 * math.sin(r) - 6, 48 + 56 * math.cos(r) + 6, 84 + 56 * math.sin(r) + 6, fill=WHITE)
    # the arsenal expansion (parts 113-118, 211-214): they had no icon (a square in the garage, nothing in the weapon box)
    elif f == 'pilebunker':
        _rect(d, 44, 36, 86, 62, fill=WHITE)                                   # the ram housing
        _rect(d, 24, 44, 46, 54, fill=WHITE)                                   # the piston
        _poly(d, [(4, 49), (24, 42), (24, 56)], fill=WHITE)                    # the stake point
        _rect(d, 58, 62, 70, 78, fill=WHITE)
    elif f == 'sniper':
        _rect(d, 2, 46, 64, 50, fill=WHITE)                                    # a long thin barrel
        _rect(d, 56, 42, 88, 56, fill=WHITE)
        _poly(d, [(88, 44), (95, 46), (95, 58), (88, 56)], fill=WHITE)
        _rect(d, 50, 30, 76, 37, fill=WHITE); _rect(d, 60, 37, 64, 42, fill=WHITE)   # scope
        _poly(d, [(64, 56), (74, 56), (70, 70), (62, 70)], fill=WHITE)
    elif f == 'burstrifle':
        _rect(d, 24, 42, 86, 52, fill=WHITE); _rect(d, 56, 36, 84, 58, fill=WHITE)
        _poly(d, [(84, 40), (94, 44), (94, 56), (84, 58)], fill=WHITE); _poly(d, [(60, 58), (72, 58), (68, 76), (58, 76)], fill=WHITE)
        for x in (4, 11, 18): _ellipse(d, x, 44, x + 5, 50, fill=WHITE)      # the three-round burst
    elif f == 'flamer':
        _rect(d, 48, 42, 90, 56, fill=WHITE); _rect(d, 36, 45, 50, 53, fill=WHITE)
        _ellipse(d, 60, 56, 78, 74, fill=WHITE)                                # the tank
        _poly(d, [(36, 49), (22, 36), (24, 46), (8, 40), (18, 52), (6, 60), (24, 56), (22, 64)], fill=WHITE)   # flame tongue
    elif f == 'eshotgun':
        _rect(d, 30, 40, 76, 50, fill=WHITE); _rect(d, 30, 52, 76, 58, fill=WHITE)
        _poly(d, [(74, 36), (94, 42), (94, 62), (74, 60)], fill=WHITE)
        _poly(d, [(20, 26), (8, 50), (17, 50), (10, 72), (28, 44), (19, 44), (26, 26)], fill=WHITE)   # the arc bolt
    elif f == 'heavyblade':
        _poly(d, [(14, 80), (28, 72), (82, 10), (90, 18), (34, 86), (20, 90)], fill=WHITE)            # a broad blade
        _line(d, [(10, 62), (36, 88)], 7)
        _line(d, [(6, 92), (16, 82)], 7)
    elif f == 'minelayer':
        _ellipse(d, 24, 30, 72, 78, fill=WHITE)
        for a in range(0, 360, 45):
            r = math.radians(a)
            _line(d, [(48 + 24 * math.cos(r), 54 + 24 * math.sin(r)), (48 + 34 * math.cos(r), 54 + 34 * math.sin(r))], 5)
        _ellipse(d, 42, 48, 54, 60, fill=(0, 0, 0, 0))
    elif f == 'orbitdrones':
        _ellipse(d, 12, 12, 84, 84, w=3)
        _ellipse(d, 36, 36, 60, 60, fill=WHITE)
        for a in (-90, 30, 150):
            r = math.radians(a); x, y = 48 + 36 * math.cos(r), 48 + 36 * math.sin(r)
            _ellipse(d, x - 9, y - 9, x + 9, y + 9, fill=WHITE)
    elif f == 'multimsl':
        for i, a in enumerate((-30, -10, 10, 30)):
            sm = Image.new('RGBA', (96 * SS, 96 * SS), (0, 0, 0, 0)); _missile(ImageDraw.Draw(sm), 48, 20, 50, 9)
            img.alpha_composite(sm.rotate(-a, resample=Image.BICUBIC, center=(48 * SS, 86 * SS)))
        _line(d, [(14, 8), (6, 8), (6, 16)], 3); _line(d, [(82, 8), (90, 8), (90, 16)], 3)   # lock brackets
    elif f == 'clusterart':
        pts = [(8 + t * 0.7, 80 - 52 * math.sin(math.pi * t / 80)) for t in range(0, 61, 4)]
        _line(d, pts, 4)
        _ellipse(d, 44, 24, 60, 40, fill=WHITE)
        for x, y in ((62, 50), (74, 58), (84, 70), (70, 74), (60, 66)): _ellipse(d, x - 5, y - 5, x + 5, y + 5, fill=WHITE)
    elif f == 'gen':
        _poly(d, [(54, 8), (26, 54), (46, 54), (40, 88), (70, 40), (50, 40)], fill=WHITE)
    elif f == 'bst':
        _poly(d, [(48, 8), (68, 48), (60, 60), (36, 60), (28, 48)], fill=WHITE)
        _poly(d, [(36, 62), (60, 62), (48, 90)], fill=(255, 255, 255, 170))
    elif f == 'fcs':
        _ellipse(d, 14, 14, 82, 82, w=4)
        _line(d, [(48, 4), (48, 30)], 4); _line(d, [(48, 66), (48, 92)], 4)
        _line(d, [(4, 48), (30, 48)], 4); _line(d, [(66, 48), (92, 48)], 4)
        _ellipse(d, 42, 42, 54, 54, fill=WHITE)
    elif f == 'paint':
        _ellipse(d, 10, 16, 86, 80, w=4)
        for cx, cy in ((30, 36), (48, 28), (66, 36), (72, 54)): _ellipse(d, cx - 7, cy - 7, cx + 7, cy + 7, fill=WHITE)
    elif f == 'frame':
        _frame_silhouette(d, 'medium')
    else:
        _rect(d, 20, 20, 76, 76, w=4)
    return _shrink(img, size) if plain else neon(img, size, col)


def _frame_silhouette(d, cls, scale=1.0, ox=0, oy=0):
    """a simple mech silhouette by weight class, in a 96 grid"""
    wide = {'light': 0.8, 'medium': 1.0, 'heavy': 1.25, 'boss': 1.4}.get(cls, 1.0)
    def R(x0, y0, x1, y1):
        cx = 48
        _rect(d, ox + cx + (x0 - cx) * wide * scale, oy + y0 * scale, ox + cx + (x1 - cx) * wide * scale, oy + y1 * scale, fill=WHITE)
    R(40, 10, 56, 22)          # head
    R(30, 24, 66, 54)          # core
    R(18, 26, 30, 50); R(66, 26, 78, 50)   # arms
    R(14, 50, 24, 62); R(72, 50, 82, 62)   # hands/weapons
    R(34, 56, 46, 86); R(50, 56, 62, 86)   # legs
    R(30, 84, 48, 92); R(48, 84, 66, 92)   # feet


# ---------------------------------------------------------------- part pictures (garage cards)
def part_card(part, size=256, render=None):
    """a square card for a part, in the HUD's box style: dark plate, sharp 2 px border with a faint inner glow, and the part as
    backlit neon (the family glyph; a frame's render from preview/frames, shrunk smoothly, when there is one). No name: the garage
    rows and the equipped panel print it in the HUD type."""
    img = Image.new('RGBA', (size, size), (12, 18, 28, 235))
    d = ImageDraw.Draw(img)
    b = max(2, size // 128)
    d.rectangle([0, 0, size - 1, size - 1], outline=(61, 90, 115, 255), width=b)                            # LINE
    d.rectangle([b, b, size - 1 - b, size - 1 - b], outline=(56, 216, 255, 38), width=max(2, size // 64))   # InGlow
    kind = part.get('kind')
    if render is not None:
        r = render.convert('RGBA')
        box = int(size * 0.84)
        sc = min(box / r.width, box / r.height)
        r = r.resize((max(1, int(r.width * sc)), max(1, int(r.height * sc))), Image.LANCZOS)
        halo = Image.new('RGBA', r.size, CY + (0,))
        halo.putalpha(r.getchannel('A').filter(ImageFilter.GaussianBlur(size * 0.03)).point(lambda v: int(v * 0.55)))
        img.alpha_composite(halo, ((size - r.width) // 2, (size - r.height) // 2))
        img.alpha_composite(r, ((size - r.width) // 2, (size - r.height) // 2))
        return img
    if kind == 'frame':
        big, dd, _ = _canvas(96)
        _frame_silhouette(dd, part.get('class', 'medium'))
        g = neon(big, size, ACC, inset=0.78)
    else:
        fam = part.get('key') if kind in ('arm', 'shoulder') else KIND_GLYPH.get(kind, 'frame')
        col = tuple(part.get('tint', list(CY)))[:3] if kind == 'paint' else CY
        g = icon(fam, size, col=col)
    img.alpha_composite(g)
    return img


# ---------------------------------------------------------------- reticle, radar, chevrons, badges
def ring(size, radius, width, gaps=0, gap_deg=18, ticks=0, col=WHITE, dashes=0):
    img, d, s = _canvas(size)
    c = size / 2
    bb = [(c - radius) * SS, (c - radius) * SS, (c + radius) * SS, (c + radius) * SS]
    if dashes:
        step = 360 / dashes
        for i in range(dashes):
            d.arc(bb, i * step, i * step + step * 0.55, fill=col, width=int(width * SS))
    elif gaps:
        step = 360 / gaps
        for i in range(gaps):
            d.arc(bb, i * step + gap_deg / 2, (i + 1) * step - gap_deg / 2, fill=col, width=int(width * SS))
    else:
        d.ellipse(bb, outline=col, width=int(width * SS))
    for i in range(ticks):
        a = math.radians(i * 360 / ticks - 90)
        r0, r1 = radius - 10, radius - 2
        _line(d, [(c + r0 * math.cos(a), c + r0 * math.sin(a)), (c + r1 * math.cos(a), c + r1 * math.sin(a))], width, col)
    return _shrink(img, size)


def crosshair(size=48):
    img, d, s = _canvas(size)
    c = size / 2
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        _line(d, [(c + dx * 7, c + dy * 7), (c + dx * 20, c + dy * 20)], 2.2)
    _ellipse(d, c - 2, c - 2, c + 2, c + 2, fill=WHITE)
    return _shrink(img, size)


def brackets(size=200, arm=28, w=3, col=WHITE, inset=2):
    img, d, s = _canvas(size)
    e = size - 1 - inset
    for (x, y, sx, sy) in ((inset, inset, 1, 1), (e, inset, -1, 1), (inset, e, 1, -1), (e, e, -1, -1)):
        _line(d, [(x, y + sy * arm), (x, y), (x + sx * arm, y)], w, col)
    return _shrink(img, size)


def diamond(size=56, col=WHITE, fill=False, w=3, ring_col=None):
    """a lock mark: a diamond outline (a multi-lock target being locked) or a filled one inside a thin ring (locked)"""
    img, d, s = _canvas(size)
    c, r = size / 2, size / 2 - (10 if ring_col else 6)
    pts = [(c, c - r), (c + r, c), (c, c + r), (c - r, c)]
    if fill: _poly(d, pts, fill=col)
    else: _line(d, pts + [pts[0]], w, col)
    _ellipse(d, c - 2.5, c - 2.5, c + 2.5, c + 2.5, fill=(255, 255, 255, 255) if fill else col)
    if ring_col: _ellipse(d, 2, 2, size - 3, size - 3, w=2, col=ring_col)
    return _shrink(img, size)


def chevron(size=64, angle=0, col=WHITE):
    """a chevron pointing up, rotated `angle` degrees clockwise (0 = up, 90 = right)"""
    img, d, s = _canvas(size)
    c = size / 2
    _poly(d, [(c, 8), (c + 22, 34), (c + 12, 34), (c, 20), (c - 12, 34), (c - 22, 34)], fill=col)
    _poly(d, [(c, 30), (c + 14, 48), (c + 7, 48), (c, 40), (c - 7, 48), (c - 14, 48)], fill=(col[0], col[1], col[2], 150))
    img = img.rotate(-angle, resample=Image.BICUBIC)
    return _shrink(img, size)


def radar_bg(size=280):
    img, d, s = _canvas(size)
    c = size / 2
    _ellipse(d, 1, 1, size - 2, size - 2, fill=(8, 12, 18, 200))
    _ellipse(d, 1, 1, size - 2, size - 2, w=4, col=(170, 200, 220, 230))
    for r in (c * 0.33, c * 0.66):
        _ellipse(d, c - r, c - r, c + r, c + r, w=4, col=(90, 120, 145, 200))
    _line(d, [(c, 2), (c, size - 2)], 4, (90, 120, 145, 200)); _line(d, [(2, c), (size - 2, c)], 4, (90, 120, 145, 200))
    _poly(d, [(c, 6), (c - 7, 20), (c + 7, 20)], fill=(200, 225, 240, 220))      # forward marker
    return _shrink(img, size)


def self_marker(size=16):
    img, d, s = _canvas(size)
    _poly(d, [(8, 1), (15, 15), (8, 11), (1, 15)], fill=WHITE)
    return _shrink(img, size)


def badge(kind, size=40):
    img, d, s = _canvas(size)
    c = size / 2
    if kind == 'bounty':
        pts = []
        for i in range(10):
            r = 18 if i % 2 == 0 else 8
            a = math.radians(i * 36 - 90)
            pts.append((c + r * math.cos(a), c + r * math.sin(a)))
        _poly(d, pts, fill=(255, 200, 60, 255))
    elif kind == 'rookie':
        _poly(d, [(8, 6), (32, 6), (32, 22), (20, 36), (8, 22)], fill=(110, 200, 255, 255))
        _line(d, [(14, 20), (19, 25), (27, 14)], 3, (10, 20, 30, 255))
    elif kind == 'streak':
        _poly(d, [(20, 2), (30, 16), (27, 26), (34, 24), (28, 38), (12, 38), (6, 24), (13, 26), (10, 14)], fill=(255, 120, 50, 255))
        _poly(d, [(20, 18), (26, 28), (20, 36), (14, 28)], fill=(255, 230, 120, 255))
    elif kind == 'skull':
        _ellipse(d, 8, 4, 32, 28, fill=WHITE)
        _rect(d, 13, 24, 27, 34, fill=WHITE)
        _ellipse(d, 12, 12, 19, 19, fill=(0, 0, 0, 0)); _ellipse(d, 21, 12, 28, 19, fill=(0, 0, 0, 0))
    halo = {'bounty': GOLD, 'rookie': CT_BLUE, 'streak': T_ORANGE}.get(kind, ACC)
    return neon(img, size, halo, inset=0.86, mono=False)


def point_marker(letter, size=28):
    """capture-point marker: a white hexagon with the letter cut in black, in the HUD's serif (hud.py recolours the white)"""
    S = size * SS
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.regular_polygon((S / 2, S / 2, S / 2 - SS), 6, rotation=30, fill=(255, 255, 255, 255))
    try:
        import hud_font
        f = ImageFont.truetype(hud_font.FONT_PATH, int(S * 0.62)); hud_font._var(f)
    except Exception:
        f = _font(int(S * 0.6))
    d.text((S / 2, S / 2 + S * 0.03), letter, font=f, fill=(0, 0, 0, 255), anchor='mm')
    return img.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- write everything
def write(img_dir, parts, frames_dir=None):
    """writes every picture under img_dir; returns the number written"""
    os.makedirs(os.path.join(img_dir, 'w'), exist_ok=True)
    os.makedirs(os.path.join(img_dir, 'p'), exist_ok=True)
    n = 0
    for fam in FAMILIES + ['gen', 'bst', 'fcs', 'paint', 'frame']:
        icon(fam).save(os.path.join(img_dir, 'w', fam + '.png')); n += 1
    for part in parts:
        render = None
        if frames_dir and part.get('kind') == 'frame':
            p = os.path.join(frames_dir, part['key'] + '.png')
            if os.path.exists(p):
                try: render = Image.open(p)
                except OSError: render = None
        part_card(part, render=render).save(os.path.join(img_dir, 'p', part['key'] + '.png')); n += 1
    crosshair().save(os.path.join(img_dir, 'xhair.png'))
    # the FCS cone ring: a thin broken circle, drawn 128 px (10 Nov 2026 playtest: the 300-400 px ring was far too large); the HUD scales it 0.7-1.1
    ring(128, 58, 2.0, gaps=4, gap_deg=40).save(os.path.join(img_dir, 'cone.png'))
    brackets(200).save(os.path.join(img_dir, 'lockbox.png'))
    brackets(170, arm=22, w=4, col=(255, 90, 70, 255)).save(os.path.join(img_dir, 'lockbox_hard.png'))
    # evening playtest 10 Nov 2026: the bracket has an "acquiring" look (thin amber corners) and multi-lock targets get a diamond each
    brackets(200, arm=16, w=2, col=(255, 194, 71, 255)).save(os.path.join(img_dir, 'lockbox_acq.png'))
    diamond(56, (255, 194, 71, 255)).save(os.path.join(img_dir, 'ml.png'))
    diamond(56, (255, 90, 70, 255), fill=True, ring_col=(255, 90, 70, 255)).save(os.path.join(img_dir, 'ml_done.png'))
    n += 3
    ring(240, 112, 3.5, ticks=12).save(os.path.join(img_dir, 'hardring.png'))
    ring(200, 92, 2.5, dashes=24, col=(120, 220, 255, 255)).save(os.path.join(img_dir, 'shield.png'))   # spawn protection (was 420 px)
    ring(120, 52, 3, dashes=8, col=(255, 90, 70, 255)).save(os.path.join(img_dir, 'stagger.png'))
    radar_bg().save(os.path.join(img_dir, 'radar.png'))
    self_marker().save(os.path.join(img_dir, 'self.png'))
    n += 9
    for i in range(8): chevron(64, i * 45).save(os.path.join(img_dir, 'th%d.png' % i)); n += 1
    for b in ('bounty', 'rookie', 'streak', 'skull'): badge(b).save(os.path.join(img_dir, 'b_%s.png' % b)); n += 1
    for L in 'ABC': point_marker(L).save(os.path.join(img_dir, 'pt_%s.png' % L)); n += 1
    return n


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit('usage: hud_images.py <addon out> [<parts.json>]')
    here = os.path.dirname(os.path.abspath(__file__))
    pj = sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, '..', 'data', 'parts.json')
    parts = json.load(open(pj, encoding='utf-8'))['parts']
    d = os.path.join(sys.argv[1], 'panorama/images/custom_game/ifr')
    n = write(d, parts, os.path.join(here, '..', 'preview', 'frames'))
    print('hud images: %d written to %s' % (n, d))
