"""IRONFRAME HUD type: backlit-neon inscriptional serif capitals, baked into one png per character and colour.

The font path is ONE setting (FONT_CANDIDATES / env IFR_HUD_FONT): create/fonts/Cinzel-*.ttf (OFL, Trajan-like) when present, else the Windows
Times New Roman Bold capitals. Trajan itself is Adobe's and is not shipped.

Each glyph picture = soft coloured halo (two gaussian layers, baked, so the HUD pays nothing for glow at run time) + a thin dark keyline +
a near-white core tinted toward the palette colour: a letter cut out of a panel with a coloured lamp behind it.
Widths are proportional: the css gives every glyph class `.s<size> .G.g<code>` its own width, so a row of cells flows like real type.
Two master heights (cap 28 and cap 56 px) are rendered; every size is a scaled copy of one of them.
"""
import os, glob, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
CREATE_FONTS = os.path.normpath(os.path.join(HERE, '..', '..', '..', 'create', 'fonts'))
FONT_CANDIDATES = (sorted(glob.glob(os.path.join(CREATE_FONTS, 'Cinzel-*.ttf')), key=lambda p: ('Bold' not in p, p)) +
                   ['C:/Windows/Fonts/timesbd.ttf'])
FONT_PATH = os.environ.get('IFR_HUD_FONT') or next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)

SIZES = {'XXL': 56, 'XL': 36, 'L': 28, 'M': 22, 'S': 18, 'XS': 14}          # cap height in px at 1080 high; nothing below 14
SIZE_ORDER = ['XXL', 'XL', 'L', 'M', 'S', 'XS']
# masters: crisp (XS, S: light halo), bright (M, L: stronger, wider halo) and bright-big (XL, XXL): key -> (cap height, glow boost)
MASTERS = {'c28': (28, 1.0), 'b28': (28, 1.45), 'b56': (56, 1.45)}
SS = 4                                                                       # supersampling
SQ = float(os.environ.get('IFR_HUD_SQ', '0.85' if FONT_PATH and 'cinzel' in FONT_PATH.lower() else '0.88'))                                                                   # horizontal squeeze (Times / Cinzel caps are very wide; keeps 14 px caps usable)
TRACK = 0.09                                                                 # letter-spacing, share of the cap height
ASC, DESC = 0.14, 0.30                                                       # room above / below the caps (parens, commas, Q)
CHARS = [c for c in range(33, 127) if not 97 <= c <= 122]                    # glyph classes g<code>; lowercase is upper-cased; g32 = a space (width only)
_cache = {}


def master_for(size):
    return 'c28' if size in ('XS', 'S') else 'b28' if size in ('M', 'L') else 'b56'


def _font(cap):
    f0 = _var(ImageFont.truetype(FONT_PATH, 1000))
    b = f0.getbbox('H', anchor='ls')
    ratio = -b[1] / 1000.0                                                   # cap height / em
    return _var(ImageFont.truetype(FONT_PATH, max(8, int(round(cap * SS / ratio))))), ratio


def _var(f):
    """a variable font (Cinzel[wght].ttf) is set to the named instance in IFR_HUD_FONT_VAR (default Bold); static fonts unchanged"""
    try: f.set_variation_by_name(os.environ.get('IFR_HUD_FONT_VAR', 'Bold'))
    except Exception: pass
    return f


class Master:
    def __init__(self, key):
        cap, self.boost = MASTERS[key]
        self.cap = cap
        self.font, self.ratio = _font(cap)
        self.sig_a, self.sig_b = 0.06 * cap * (1 + 0.15 * (self.boost - 1)), 0.19 * cap * (1 + 0.5 * (self.boost - 1))                      # tight lamp glow and wide faint halo
        self.pad = int(round(2.4 * self.sig_b))
        self.h = int(round(self.pad * 2 + cap * (1 + ASC + DESC)))
        self.base = self.pad + cap * ASC + cap                               # baseline y inside the picture
        self.adv = {}
        for c in [32] + CHARS:
            self.adv[c] = int(round(self.font.getlength(chr(c)) / SS * SQ + TRACK * cap))
        self.layers = {}

    def layer(self, c):
        """(core mask, keyline mask, glow alpha) as float arrays at output size"""
        if c in self.layers: return self.layers[c]
        w = self.adv[c] + 2 * self.pad
        W, H = w * SS, self.h * SS
        raw = self.font.getlength(chr(c)) / SS
        gw = int((raw + 4) * SS)
        g = Image.new('L', (gw, H), 0)
        ImageDraw.Draw(g).text((2 * SS, self.base * SS), chr(c), font=self.font, fill=255, anchor='ls')
        g = g.resize((max(1, int(gw * SQ)), H), Image.LANCZOS)
        im = Image.new('L', (W, H), 0)
        im.paste(g, (int((self.pad + TRACK * self.cap / 2) * SS - 2 * SS * SQ), 0))
        core = im.resize((w, self.h), Image.LANCZOS)
        key = im.filter(ImageFilter.MaxFilter(2 * int(SS * 0.6) + 1)).resize((w, self.h), Image.LANCZOS)
        small = im.resize((w, self.h), Image.BOX)
        ga = np.asarray(small.filter(ImageFilter.GaussianBlur(self.sig_a)), np.float32) / 255
        gb = np.asarray(small.filter(ImageFilter.GaussianBlur(self.sig_b)), np.float32) / 255
        glow = np.clip(ga * 1.25 * self.boost + gb * 1.2 * self.boost, 0, 1) * 0.96
        self.layers[c] = (np.asarray(core, np.float32) / 255, np.asarray(key, np.float32) / 255, glow)
        return self.layers[c]

    def render(self, c, col):
        core, key, glow = self.layer(c)
        col = np.array(col, np.float32)
        white = np.array([255, 255, 255], np.float32)
        face = col * 0.18 + white * 0.82                                     # near-white core tinted toward the colour
        h, w = core.shape
        out = np.zeros((h, w, 4), np.float32)
        out[..., :3] = col; out[..., 3] = glow                               # halo
        a_key = np.clip(key * 0.85, 0, 1)                                    # dark keyline keeps the core readable on bright sky
        ra = a_key + out[..., 3] * (1 - a_key)
        out[..., :3] = np.where(ra[..., None] > 0, (out[..., :3] * out[..., 3:4] * (1 - a_key[..., None]) + np.array([4, 8, 12], np.float32) * a_key[..., None]) / np.maximum(ra[..., None], 1e-6), 0)
        out[..., 3] = ra
        rb = core + out[..., 3] * (1 - core)
        out[..., :3] = np.where(rb[..., None] > 0, (face * core[..., None] + out[..., :3] * out[..., 3:4] * (1 - core[..., None])) / np.maximum(rb[..., None], 1e-6), 0)
        out[..., 3] = rb
        out[..., 3] *= 255
        return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), 'RGBA')


def master(key):
    if key not in _cache: _cache[key] = Master(key)
    return _cache[key]


class Metrics:
    """per-size layout numbers (px at 1080 high), all derived from the master so css, driver and checker agree"""
    def __init__(self, size):
        self.size = size
        self.cap = SIZES[size]
        self.m = master(master_for(size))
        self.k = self.cap / self.m.cap
        self.mkey = master_for(size)
        self.pad = int(round(self.m.pad * self.k))
        self.h = int(round(self.m.h * self.k))
        self.base = self.m.base * self.k
        self.adv = {c: max(1, int(round(a * self.k))) for c, a in self.m.adv.items()}

    def text_w(self, text):
        return sum(self.adv.get(ord(ch), self.adv[63]) for ch in text.upper())

    def avg(self):
        s = 'ABCDEFGHIKLMNOPRSTUVWXY0123456789   '
        return sum(self.adv[ord(c)] for c in s) / len(s)


METRICS = {s: Metrics(s) for s in SIZE_ORDER}


def write_sheet(img_dir, colors_by_master):
    """colors_by_master: {master key: {colour key: (r, g, b)}} -> img_dir/f/<master>_<colour>_<code>.png"""
    os.makedirs(os.path.join(img_dir, 'f'), exist_ok=True)
    for f in glob.glob(os.path.join(img_dir, 'f', '*.png')): os.remove(f)
    n = 0
    for mk, cols in colors_by_master.items():
        m = master(mk)
        for key, col in cols.items():
            for c in CHARS:
                m.render(c, col).save(os.path.join(img_dir, 'f', '%s_%s_%d.png' % (mk, key, c)))
                n += 1
    return n


# ---------------------------------------------------------------- real Labels (dynamic text), 10 Nov 2026
# CS2 keeps at most 1024 panel ids per custom_hud_layout ("The maximum number of panel ids has been reached"), so dynamic text cannot be one
# id-carrying panel per character. It is a <Label text="{s:v}"> in a font CS2 ships: Noto Serif Bold (game/csgo/panorama/fonts/notoserif-bold.ttf;
# its fonts.conf loads `notoserif*`). At the same cap height its capitals are within 2 % of the neon glyphs' widths, so the layout boxes hold.
# The advance widths below are the TTF's own (x LABEL_SAFETY, rounded up) and are what the driver measures with; they are cached in
# tools/hud_label_metrics.json so the generator also runs where CS2 is not installed.
LABEL_FAMILY = 'Noto Serif'
LABEL_CSS_FAMILY = '"Noto Serif", notoserif, Stratum2, Arial'
LABEL_FONT_CANDIDATES = [os.environ.get('IFR_LABEL_FONT') or '',
                         r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo\panorama\fonts\notoserif-bold.ttf',
                         r'C:\source1\links\cs2_root\game\csgo\panorama\fonts\notoserif-bold.ttf',
                         '/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf']
LABEL_FONT_PATH = next((p for p in LABEL_FONT_CANDIDATES if p and os.path.exists(p)), None)
LABEL_CAP, LABEL_ASC, LABEL_DESC = 0.714, 1.069, 0.293          # of the font size (Noto Serif Bold)
LABEL_SAFETY = 1.03                                              # Panorama's rasteriser may run a little wider than FreeType's plain advances
LABEL_CHARS = list(range(32, 127)) + list(range(0xA1, 0x180))    # measured code points (ASCII + Latin-1 / Latin Extended-A: names)
LABEL_CACHE = os.path.join(HERE, 'hud_label_metrics.json')


class LabelMetrics:
    """per-size numbers of a Label row: font px, line box height, cap height, where the capitals' top sits under the line top, advances"""
    def __init__(self, size, adv):
        self.size = size
        self.cap = SIZES[size]
        self.px = int(round(self.cap / LABEL_CAP))
        self.h = int(math.ceil(self.px * (LABEL_ASC + LABEL_DESC)))
        self.top = self.px * (LABEL_ASC - LABEL_CAP)          # line top -> cap top
        self.adv = adv
        self.pad = 0

    def text_w(self, text):
        return int(math.ceil(sum(self.adv.get(ord(ch), self.adv[87]) for ch in text.upper())))

    def avg(self):
        s = 'ABCDEFGHIKLMNOPRSTUVWXY0123456789   '
        return sum(self.adv[ord(c)] for c in s) / len(s)


def _label_metrics():
    import json
    out = {}
    if LABEL_FONT_PATH:
        from PIL import ImageFont
        for s in SIZE_ORDER:
            px = int(round(SIZES[s] / LABEL_CAP))
            f = ImageFont.truetype(LABEL_FONT_PATH, px * 8)       # measured large, scaled down: no hinting steps
            out[s] = {c: round(max(1.0, f.getlength(chr(c).upper()) / 8 * LABEL_SAFETY), 2) for c in LABEL_CHARS}      # fractional: rounding each letter up would add 5 % to a row
        try: json.dump({s: {str(c): a for c, a in d.items()} for s, d in out.items()}, open(LABEL_CACHE, 'w'), indent=0, sort_keys=True)
        except OSError: pass
    elif os.path.exists(LABEL_CACHE):
        out = {s: {int(c): a for c, a in d.items()} for s, d in json.load(open(LABEL_CACHE)).items()}
    else:
        raise SystemExit('hud_font: no Noto Serif Bold (set IFR_LABEL_FONT) and no tools/hud_label_metrics.json')
    return {s: LabelMetrics(s, out[s]) for s in SIZE_ORDER}


LMETRICS = _label_metrics()
