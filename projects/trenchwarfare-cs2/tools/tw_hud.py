"""mg_trenchwarfare HUD (custom_hud_layout tw_hud): panorama/layout/custom_game/mg_trenchwarfare.xml + css + every picture it uses,
built against the HUD contract in docs/HUD.md and gated by tools/hud_check.py (copy of create/hud_check.py).

usage: tw_hud.py [<addon content out>] [--no-art] [--no-check]          default ../out/addon
  writes <addon>/panorama/layout/custom_game/mg_trenchwarfare.xml, styles/custom_game/mg_trenchwarfare.css,
         <addon>/panorama/images/custom_game/tw/*.png (plates, paper, markers, cockpit art; NOT target_t/ct.png: render_sight.py),
         ../out/hud.json {tm, steps, marker, ids}, ../out/step8/hud_states.json, ../out/step8/hud/hud_<state>[_W].png (the gate's pictures)
  exits 1 on a contract break (docs/HUD.md table vs layout, css and src/modules/*.js) or any hud_check.py problem.

Layout rules (create/hud_check.py, learned in CS2): one Screen panel 1080 high, every panel a fixed size pinned from the top
(left / centre / right), no margin-bottom, no vertical-align, no fit-children; moving parts are class swaps (translate / rotate)
of fixed panels. Every plate picture is drawn at the size it is shown, so no border is ever stretched. Live text is Stratum2 /
Noto Serif / Noto Mono (fonts CS2 ships in csgo/panorama/fonts); titles and help that never change are baked into the pictures."""
import os, sys, re, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tw_cockpit

ROOT = os.path.join(HERE, '..')
args = [a for a in sys.argv[1:] if not a.startswith('--')]
OUT = args[0] if args else os.path.join(ROOT, 'out', 'addon')
NAME = 'mg_trenchwarfare'
IMG = 'file://{images}/custom_game/tw/'
IMGDIR = os.path.join(OUT, 'panorama/images/custom_game/tw'); os.makedirs(IMGDIR, exist_ok=True)
TM = 640             # map on the plotting board (px)
STEPS = 192          # marker steps per axis = CONFIG.TARGET_STEPS
MK = 80              # every marker is an MK x MK square, its art centred
LIVE = 'Stratum2, "Stratum2 Bold", Arial'
SERIF = '"Noto Serif", Georgia, serif'
MONO = '"Noto Mono", "Courier New", monospace'
CS2FONTS = 'C:/source1/links/cs2_root/game/csgo/panorama/fonts'

FONTS = {'serif': ['C:/Windows/Fonts/georgiab.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'],
         'serif_r': ['C:/Windows/Fonts/georgia.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'],
         'book': ['C:/Windows/Fonts/BOOKOSB.TTF', 'C:/Windows/Fonts/georgiab.ttf'],
         'stencil': ['C:/Windows/Fonts/STENCIL.TTF', 'C:/Windows/Fonts/impact.ttf', 'C:/Windows/Fonts/georgiab.ttf'],
         'type': ['C:/Windows/Fonts/courbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf'],
         'sans': ['C:/Windows/Fonts/bahnschrift.ttf', 'C:/Windows/Fonts/arialbd.ttf']}


def font(sz, kind='serif'):
    for p in FONTS[kind]:
        if os.path.exists(p):
            f = ImageFont.truetype(p, int(sz))
            if 'bahnschrift' in p:
                try: f.set_variation_by_name('SemiBold Condensed')
                except Exception: pass
            return f
    return ImageFont.load_default()


# ================================================================ contract (docs/HUD.md)
def read_contract():
    text = open(os.path.join(ROOT, 'docs', 'HUD.md'), encoding='utf-8').read()
    m = re.search(r'<!-- HUD-CONTRACT-BEGIN -->(.*?)<!-- HUD-CONTRACT-END -->', text, re.S)
    if not m: sys.exit('tw_hud: no HUD contract table in docs/HUD.md')
    rows = {}
    for line in m.group(1).splitlines():
        if not line.startswith('| `'): continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        ids = re.findall(r'`(tw_\w+)`', cells[0])
        kind = cells[1]
        classes = []
        for tok in re.findall(r'`([^`]+)`', cells[2]):
            r = re.match(r'^([a-z]+)(\d+)\.\.\1(\d+)$', tok)
            classes += ['%s%d' % (r.group(1), k) for k in range(int(r.group(2)), int(r.group(3)) + 1)] if r else [tok]
        for i in ids: rows[i] = dict(kind=kind, classes=classes)
    return rows


def script_ids():
    """literal ids the script writes, and the prefixes it builds ids from ("tw_info_l" + n, "tw_imp" + i, id + "y")"""
    lit, pre = set(), set()
    for f in sorted(os.listdir(os.path.join(ROOT, 'src', 'modules'))):
        if not f.endswith('.js'): continue
        s = open(os.path.join(ROOT, 'src', 'modules', f), encoding='utf-8').read()
        for m in re.finditer(r'\b(hText|hClass|hSwap|placeMarker|toast|info)\(\s*\w+\s*,\s*"(tw_\w+)"(\s*\+)?', s):
            if m.group(1) in ('toast', 'info'): continue
            (pre if m.group(3) else lit).add(m.group(2))
        if 'function placeMarker' in s and 'id + "y"' in s: pre.add('<marker>y')
    return lit, pre


# ================================================================ pictures
def smooth_noise(h, w, cell, seed):
    r = np.random.RandomState(seed).rand(h // cell + 3, w // cell + 3).astype(np.float32)
    return np.asarray(Image.fromarray((r * 255).astype(np.uint8)).resize((w + 2 * cell, h + 2 * cell), Image.BICUBIC), np.float32)[cell:cell + h, cell:cell + w] / 255.0


def rgba(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'RGBA')


def plate(w, h, seed=1, alpha=0.88, rules=(), base=(38, 37, 27)):
    """the dark olive canvas plate every live card sits on: weave, mottling, darker rim, brass keyline, corner brackets, rivets"""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    weave = 0.035 * np.sin(x * np.pi / 1.6) * np.sin(y * np.pi / 1.6)
    mott = smooth_noise(h, w, 22, seed) * 0.16 + smooth_noise(h, w, 5, seed + 1) * 0.06
    e = np.minimum(np.minimum(x, w - 1 - x), np.minimum(y, h - 1 - y))
    rim = 0.78 + 0.22 * np.clip(e / 18.0, 0, 1)
    k = (0.86 + mott + weave) * rim
    a = np.zeros((h, w, 4), np.float32)
    a[..., :3] = np.array(base, np.float32) * k[..., None]
    a[..., 3] = 255 * alpha
    im = rgba(a)
    m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), 7, fill=255)
    im.putalpha(Image.fromarray((np.asarray(m, np.float32) / 255 * np.asarray(im.getchannel('A'), np.float32)).astype(np.uint8)))
    d = ImageDraw.Draw(im)
    brass = (186, 152, 86)
    d.rounded_rectangle((5, 5, w - 6, h - 6), 5, outline=brass + (110,), width=1)
    L = min(22, w // 6, h // 4)
    for (cx, cy, sx, sy) in ((5, 5, 1, 1), (w - 6, 5, -1, 1), (5, h - 6, 1, -1), (w - 6, h - 6, -1, -1)):
        d.line([(cx, cy + sy * L), (cx, cy), (cx + sx * L, cy)], fill=brass + (235,), width=2)
        rx, ry = cx + sx * 9, cy + sy * 9
        d.ellipse((rx - 3, ry - 3, rx + 3, ry + 3), fill=(120, 96, 52, 255)); d.point((rx - 1, ry - 1), fill=(240, 210, 140, 255))
    for (ry, col) in rules:
        for i in range(w - 60):
            fx = i / (w - 60); al = int(200 * min(1, fx * 5, (1 - fx) * 5))
            d.point((30 + i, ry), fill=col + (al,)); d.point((30 + i, ry + 1), fill=(0, 0, 0, al // 3))
    return im


def band(w, h, seed=3):
    """a dark band that fades out to both ends, brass hairlines along top and bottom (prompt, toast)"""
    x = np.arange(w, dtype=np.float32) / (w - 1)
    prof = np.clip(np.minimum(x, 1 - x) / 0.2, 0, 1) ** 1.3
    a = np.zeros((h, w, 4), np.float32)
    mott = smooth_noise(h, w, 18, seed) * 0.15
    a[..., :3] = np.array([24, 23, 17], np.float32) * (0.9 + mott)[..., None]
    a[..., 3] = 205 * prof[None, :]
    for ry in (1, h - 3):
        a[ry:ry + 2, :, :3] = (186, 152, 86); a[ry:ry + 2, :, 3] = 220 * prof[None, :]
    return rgba(a)


def paper(w, h, seed=7, tone=(224, 212, 178)):
    """aged field-message paper: fibres, foxing, a fold, darker edges"""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    n1 = smooth_noise(h, w, 40, seed); n2 = smooth_noise(h, w, 6, seed + 1); n3 = smooth_noise(h, w, 90, seed + 2)
    k = 0.93 + 0.06 * n1 + 0.04 * n2
    e = np.minimum(np.minimum(x, w - 1 - x), np.minimum(y, h - 1 - y))
    k *= 0.80 + 0.20 * np.clip(e / 26.0, 0, 1) ** 0.7
    fox = np.clip((n3 - 0.72) * 3.0, 0, 1) * 0.10                      # brown spotting
    fold = 1 - 0.05 * np.exp(-((x - w * 0.5) / 2.5) ** 2) + 0.03 * np.exp(-((x - w * 0.5 - 4) / 3.0) ** 2)
    a = np.zeros((h, w, 4), np.float32)
    a[..., :3] = np.array(tone, np.float32) * (k * fold)[..., None] - fox[..., None] * np.array([40, 60, 90])
    a[..., 3] = 250
    im = rgba(a)
    m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), 4, fill=255)
    im.putalpha(m.point(lambda v: min(v, 250)))
    return im


def stamp(im, xy, text, rot=-7, col=(160, 34, 26), size=30, kind='stencil'):
    f = font(size, kind); w = int(f.getlength(text)) + 34; h = int(size * 1.7)
    t = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(t)
    d.rectangle((2, 2, w - 3, h - 3), outline=col + (230,), width=3)
    d.text((w / 2, h / 2 + 1), text, font=f, fill=col + (230,), anchor='mm')
    n = np.random.RandomState(3).rand(h, w)
    a = np.asarray(t).copy(); a[..., 3] = (a[..., 3] * (0.55 + 0.45 * (n > 0.22))).astype(np.uint8)
    t = Image.fromarray(a).rotate(rot, expand=True, resample=Image.BICUBIC)
    im.alpha_composite(t, (int(xy[0] - t.size[0] / 2), int(xy[1] - t.size[1] / 2)))


def ruled(d, x0, x1, ys, col=(120, 140, 170, 90)):
    for y in ys: d.line([(x0, y), (x1, y)], fill=col, width=1)


def brief_sheet(w, h):
    """the orders sheet: a printed field-message form (header, ruled lines), an ORDERS stamp"""
    im = paper(w, h, 11)
    d = ImageDraw.Draw(im)
    ink = (54, 44, 34, 235)
    d.text((34, 26), 'FIELD MESSAGE', font=font(19, 'type'), fill=ink)
    d.text((w - 34, 26), 'No. ........', font=font(16, 'type'), fill=ink, anchor='ra')
    d.line([(30, 56), (w - 30, 56)], fill=ink, width=2); d.line([(30, 60), (w - 30, 60)], fill=ink, width=1)
    d.text((34, 72), 'TO:  ALL RANKS IN THE LINE', font=font(14, 'type'), fill=(70, 60, 48, 220))
    ruled(d, 40, w - 40, [222 + 36 * k for k in range(3)])
    d.line([(30, 350), (w - 30, 350)], fill=(70, 60, 48, 140), width=1)
    d.text((34, h - 30), 'Received ........   Sent ........', font=font(13, 'type'), fill=(90, 78, 62, 200))
    stamp(im, (w - 112, 88), 'ORDERS', rot=-6, size=24)
    return im


def ledger(w, h):
    """the plotting board's card: title, live-value lines, the marker key, the controls"""
    im = paper(w, h, 21, tone=(222, 212, 182))
    d = ImageDraw.Draw(im)
    ink = (50, 42, 32, 240)
    d.text((w / 2, 30), 'MORTAR', font=font(30, 'stencil'), fill=(60, 52, 40, 245), anchor='mm')
    d.text((w / 2, 62), 'PLOTTING BOARD', font=font(15, 'type'), fill=ink, anchor='mm')
    d.line([(16, 82), (w - 16, 82)], fill=ink, width=2)
    ruled(d, 16, w - 16, [148 + 32 * k for k in range(3)] + [218 + 64])
    d.text((16, 98), 'FIRE ORDER', font=font(13, 'type'), fill=(110, 40, 30, 230))
    # marker key
    y0 = 344
    d.text((16, y0), 'KEY', font=font(13, 'type'), fill=(110, 40, 30, 230))
    keys = [('pit', 'your mortar'), ('locked', 'target locked'), ('impact', 'fall of shot'), ('reticle', 'the sight')]
    for i, (pic, cap) in enumerate(keys):
        icon = MARKERS[pic]().resize((34, 34), Image.LANCZOS)
        im.alpha_composite(icon, (14, y0 + 20 + i * 38))
        d.text((56, y0 + 37 + i * 38), cap, font=font(15, 'serif_r'), fill=ink, anchor='lm')
    y1 = 528
    d.line([(16, y1 - 8), (w - 16, y1 - 8)], fill=ink, width=1)
    for i, (k, v) in enumerate((('W A S D', 'move the sight'), ('SHIFT', 'fine adjust'), ('MOUSE 1', 'lock the target'),
                                ('SPACE', 'fire when loaded'), ('E', 'leave the table'))):
        y = y1 + 6 + i * 22
        d.text((16, y), k, font=font(13, 'type'), fill=(110, 40, 30, 235))
        d.text((92, y), v, font=font(14, 'serif_r'), fill=ink)
    return im


def board(w, h, map_xy, map_size, card_xy, card_size):
    """the plotting board: wood, a recess for the map, the ledger card pinned at the right"""
    im = tw_cockpit.wood(w, h, seed=81, base=(104, 70, 40))
    sh = Image.new('RGBA', (w, h), (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
    mx, my = map_xy; cx, cy = card_xy
    ds.rectangle((mx - 6, my - 2, mx + map_size + 8, my + map_size + 10), fill=(0, 0, 0, 190))
    ds.rectangle((cx - 4, cy, cx + card_size[0] + 8, cy + card_size[1] + 8), fill=(0, 0, 0, 150))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
    d = ImageDraw.Draw(im)
    d.rectangle((mx - 3, my - 3, mx + map_size + 2, my + map_size + 2), fill=(26, 20, 14, 255), outline=(176, 142, 74, 255), width=2)
    im.alpha_composite(ledger(*card_size), card_xy)
    d = ImageDraw.Draw(im)
    for (x, y) in ((cx + card_size[0] / 2, cy + 8),):                   # drawing pin
        d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=(150, 30, 24, 255), outline=(70, 14, 10, 255)); d.point((x - 2, y - 2), fill=(255, 190, 170, 255))
    for (x, y) in ((10, 10), (w - 10, 10), (10, h - 10), (w - 10, h - 10)): tw_cockpit.screw(d, x, y, 5)
    d.rectangle((0, 0, w - 1, h - 1), outline=(36, 24, 14, 255), width=3)
    return im


def _canvas():
    return Image.new('RGBA', (MK, MK), (0, 0, 0, 0))


def m_reticle():
    """the sight: a black ink ring and cross with a pale halo so it reads on dark wood as well as paper"""
    im = _canvas(); c = MK / 2
    for col, wd in (((246, 238, 214, 170), 6), ((24, 20, 16, 255), 3)):
        d = ImageDraw.Draw(im)
        d.ellipse((c - 24, c - 24, c + 24, c + 24), outline=col, width=wd)
        for a, b in (((c, 4), (c, c - 10)), ((c, c + 10), (c, MK - 4)), ((4, c), (c - 10, c)), ((c + 10, c), (MK - 4, c))):
            d.line([a, b], fill=col, width=wd)
    ImageDraw.Draw(im).ellipse((c - 2.5, c - 2.5, c + 2.5, c + 2.5), fill=(170, 30, 24, 255))
    return im


def m_locked():
    """target locked: a red grease-pencil ring with a cross through it"""
    im = _canvas(); c = MK / 2; d = ImageDraw.Draw(im)
    red = (176, 30, 22, 255)
    d.ellipse((c - 19, c - 19, c + 19, c + 19), outline=(250, 240, 220, 150), width=7)
    d.ellipse((c - 19, c - 19, c + 19, c + 19), outline=red, width=4)
    d.line([(c - 12, c - 12), (c + 12, c + 12)], fill=red, width=4); d.line([(c + 12, c - 12), (c - 12, c + 12)], fill=red, width=4)
    return im


def m_impact():
    """fall of shot: a black ink burst"""
    im = _canvas(); c = MK / 2; d = ImageDraw.Draw(im)
    pts = []
    for k in range(16):
        r = 14 if k % 2 == 0 else 6
        a = k * math.pi / 8
        pts.append((c + math.cos(a) * r, c + math.sin(a) * r))
    d.polygon(pts, fill=(250, 240, 220, 120)); d.polygon([(c + (x - c) * 0.8, c + (y - c) * 0.8) for x, y in pts], fill=(28, 22, 18, 255))
    return im


def m_pit():
    """your own mortar: a filled blue triangle (own works were blue on British trench maps)"""
    im = _canvas(); c = MK / 2; d = ImageDraw.Draw(im)
    tri = [(c, c - 12), (c + 11, c + 8), (c - 11, c + 8)]
    d.polygon([(c, c - 16), (c + 15, c + 11), (c - 15, c + 11)], fill=(250, 240, 220, 200))
    d.polygon(tri, fill=(32, 70, 150, 255))
    return im


MARKERS = {'reticle': m_reticle, 'locked': m_locked, 'impact': m_impact, 'pit': m_pit}


def make_art():
    P = lambda n: os.path.join(IMGDIR, n)
    plate(880, 120, 1, rules=((74, (150, 40, 30)),)).save(P('banner.png'))
    brief_sheet(760, 430).save(P('brief.png'))
    plate(400, 150, 2, rules=((50, (186, 152, 86)),)).save(P('status.png'))
    plate(520, 330, 3, rules=((68, (186, 152, 86)),)).save(P('info.png'))
    band(700, 52, 4).save(P('prompt.png'))
    band(760, 52, 5).save(P('toast.png'))
    board(920, 690, (24, 24), TM, (684, 24), (216, 642)).save(P('board.png'))
    for k, f in MARKERS.items(): f().save(P('m_%s.png' % k))
    tw_cockpit.build(IMGDIR, GAUGE_CENTRES, 64, (DASH_W, DASH_H), (SIDE_W, SIDE_H), [('ROUNDS', 72), ('BOMBS', 156)])
    for stale in ('panel.png', 'scan.png', 'reticle.png', 'locked.png', 'impact.png', 'pit.png'):   # the tw7-tw35 pictures
        if os.path.exists(P(stale)): os.remove(P(stale))


# ================================================================ layout + css
css = []
def rule(sel, **p):
    css.append('%s {\n%s}\n' % (sel, ''.join('\t%s: %s;\n' % (k.replace('_', '-'), v) for k, v in p.items())))


def px(v): return '%dpx' % v


def box(sel, w, h, x=None, y=0, right=None, center=False, cx=0, **more):
    """a fixed box pinned from the top: from the left (x), the right (right) or the centre (+cx)"""
    p = dict(width=px(w), height=px(h), margin_top=px(y))
    if center:
        p['horizontal_align'] = 'center'
        if cx: p['margin_left'] = px(cx)
    elif right is not None:
        p['horizontal_align'] = 'right'; p['margin_right'] = px(right)
    else:
        p['margin_left'] = px(x or 0)
    p.update(more); rule(sel, **p)


def fades(sel, dur='0.3s'):
    rule(sel, opacity='0', transition_property='opacity', transition_duration=dur)
    rule(sel + '.show', opacity='1')


def bg(name): return dict(background_image='url("%s%s")' % (IMG, name), background_size='100% 100%')


def label(sel, w, h, x=0, y=0, size=20, fam=LIVE, color='#e8dcc0', align='left', **more):
    p = dict(width=px(w), height=px(h), margin_left=px(x), margin_top=px(y), font_family=fam, font_size=px(size), color=color, text_align=align)
    p.update(more); rule(sel, **p)


def P(id_=None, cls='', kids='', tag='Panel', text=None):
    a = ' id="%s"' % id_ if id_ else ''
    c = ' class="%s"' % cls if cls else ''
    if tag == 'Label': return '<Label%s%s text="%s" />' % (a, c, text if text is not None else '{s:v}')
    return '<Panel%s%s hittest="false">%s</Panel>' % (a, c, kids)


INK = '#2e2418'
NOSHADOW = '0px 0px 0px 0.0 #00000000'
GAP = 12; GS = tw_cockpit.G
DASH_W, DASH_H = 760, 196
ROW_X, ROW_Y = (DASH_W - (5 * GS + 4 * GAP)) // 2, 34
GAUGE_CENTRES = [(ROW_X + GS / 2 + k * (GS + GAP), ROW_Y + GS / 2) for k in range(5)]
SIDE_W, SIDE_H = 150, 172


def build_layout():
    rule('.TWRoot', width='100%', height='100%')
    rule('.Screen', width='100%', height='1080px')
    rule('.TWRoot Label', font_family=LIVE, color='#e8dcc0', text_shadow='0px 1px 3px 1.5 #000000', font_weight='bold')
    parts = []

    # ---- headline banner
    box('#tw_banner', 880, 120, center=True, y=84, **bg('banner.png')); fades('#tw_banner', '0.4s')
    label('#tw_banner_title', 840, 56, 20, 12, 40, SERIF, '#f0d48a', 'center', letter_spacing='2px')
    label('#tw_banner_sub', 820, 32, 30, 80, 21, LIVE, '#e8dcc0', 'center')
    parts.append(P('tw_banner', '', P('tw_banner_title', tag='Label') + P('tw_banner_sub', tag='Label')))

    # ---- orders sheet (briefing room)
    box('#tw_brief', 760, 430, center=True, y=214, **bg('brief.png')); fades('#tw_brief')
    label('#tw_brief_role', 720, 60, 20, 112, 44, SERIF, '#3a2414', 'center', text_shadow=NOSHADOW, letter_spacing='2px')
    for k in range(3):
        label('#tw_brief_l%d' % (k + 1), 680, 32, 40, 192 + 36 * k, 21, SERIF, INK, 'center', text_shadow=NOSHADOW, font_weight='normal')
    label('#tw_brief_count', 700, 30, 30, 362, 19, LIVE, '#7a2216', 'center', text_shadow=NOSHADOW)
    parts.append(P('tw_brief', '', ''.join(P(i, tag='Label') for i in ('tw_brief_role', 'tw_brief_l1', 'tw_brief_l2', 'tw_brief_l3', 'tw_brief_count'))))

    # ---- status card (under the radar)
    box('#tw_status', 400, 150, x=18, y=330, **bg('status.png')); fades('#tw_status')
    label('#tw_st_role', 360, 32, 22, 12, 22, SERIF, '#f0d48a', letter_spacing='1px')
    for k in range(3): label('#tw_st_l%d' % (k + 1), 360, 26, 22, 58 + 28 * k, 18)
    parts.append(P('tw_status', '', ''.join(P(i, tag='Label') for i in ('tw_st_role', 'tw_st_l1', 'tw_st_l2', 'tw_st_l3'))))

    # ---- orders card (right)
    box('#tw_info', 520, 330, right=22, y=214, **bg('info.png')); fades('#tw_info')
    label('#tw_info_title', 470, 42, 26, 18, 29, SERIF, '#f0d48a', letter_spacing='2px')
    for k in range(5): label('#tw_info_l%d' % (k + 1), 470, 30, 26, 80 + 34 * k, 19)
    label('#tw_info_foot', 470, 46, 26, 260, 16, LIVE, '#b9c48e')
    parts.append(P('tw_info', '', ''.join(P(i, tag='Label') for i in ['tw_info_title'] + ['tw_info_l%d' % k for k in range(1, 6)] + ['tw_info_foot'])))

    # ---- prompt + toast
    box('#tw_prompt', 700, 52, center=True, y=598, **bg('prompt.png')); fades('#tw_prompt', '0.15s')
    label('#tw_prompt_text', 640, 32, 30, 11, 23, LIVE, '#ffffff', 'center')
    box('#tw_toast', 760, 52, center=True, y=662, **bg('toast.png')); fades('#tw_toast', '0.25s')
    label('#tw_toast_text', 720, 32, 20, 11, 22, LIVE, '#ffcf6a', 'center')
    parts.append(P('tw_prompt', '', P('tw_prompt_text', tag='Label')))
    parts.append(P('tw_toast', '', P('tw_toast_text', tag='Label')))

    # ---- mortar plotting board
    box('#tw_target', 920, 690, center=True, cx=80, y=196, **bg('board.png')); fades('#tw_target', '0.2s')
    rule('#tw_tmap', width=px(TM), height=px(TM), margin_left='24px', margin_top='24px', background_size='100% 100%')
    rule('#tw_tmap.mt', background_image='url("%starget_t.png")' % IMG)
    rule('#tw_tmap.mct', background_image='url("%starget_ct.png")' % IMG)
    rule('.MCol', width=px(MK), height=px(TM), opacity='0')
    rule('.MCol.on', opacity='1')
    rule('.MSq', width=px(MK), height=px(MK), background_size='100% 100%')
    for cls, pic in (('Ret', 'reticle'), ('Lock', 'locked'), ('Imp', 'impact'), ('Pit', 'pit')):
        rule('.MSq.%s' % cls, background_image='url("%sm_%s.png")' % (IMG, pic))
    for i in range(STEPS):
        c = (i + 0.5) * TM / STEPS
        rule('.MCol.x%d' % i, transform='translatex(%dpx)' % int(round(c - MK / 2)))
        rule('.MSq.y%d' % i, transform='translatey(%dpx)' % int(round(c - MK / 2)))
    def marker(mid, cls):
        return P(mid, 'MCol', P(mid + 'y', 'MSq ' + cls))
    marks = marker('tw_pit', 'Pit') + ''.join(marker('tw_imp%d' % k, 'Imp') for k in range(3)) + marker('tw_lock', 'Lock') + marker('tw_ret', 'Ret')
    rule('#tw_tside', width='216px', height='642px', margin_left='684px', margin_top='24px')
    for k, i in enumerate(('tw_t_range', 'tw_t_grid', 'tw_t_tube')):
        label('#' + i, 196, 28, 12, 118 + 32 * k, 17, MONO, INK, text_shadow=NOSHADOW)
    label('#tw_t_state', 200, 52, 10, 230, 15, SERIF, '#8a1f14', text_shadow=NOSHADOW)
    side = P('tw_tside', '', ''.join(P(i, tag='Label') for i in ('tw_t_range', 'tw_t_grid', 'tw_t_tube', 'tw_t_state')))
    parts.append(P('tw_target', '', P('tw_tmap', '', marks) + side))

    # ---- flight
    rule('#tw_fly', width='100%', height='1080px', opacity='0', transition_property='opacity', transition_duration='0.3s')
    rule('#tw_fly.show', opacity='1')
    label('#tw_fly_help', 600, 26, 0, 724, 17, SERIF, '#e2d4ac', 'right', horizontal_align='right', margin_right='28px', font_weight='normal')
    label('#tw_fly_info', 640, 30, 0, 764, 20, SERIF, '#f0d48a', 'center', horizontal_align='center', letter_spacing='1px')
    box('#tw_dash', DASH_W, DASH_H, center=True, y=800, **bg('fly_dash.png'))
    rule('#tw_dashrow', width=px(5 * GS + 4 * GAP), height=px(GS), margin_left=px(ROW_X), margin_top=px(ROW_Y), flow_children='right')
    rule('.Gauge', width=px(GS), height=px(GS), margin_left=px(GAP))
    rule('.Gauge.First', margin_left='0px')
    rule('.GFace', width=px(GS), height=px(GS), background_size='100% 100%')
    rule('.GLayer', width=px(GS), height=px(GS), background_size='100% 100%', transition_property='transform', transition_duration='0.12s')
    for n in ('asi', 'alt', 'rpm', 'bank'): rule('#tw_g_%s' % n, background_image='url("%sfly_%s.png")' % (IMG, n))
    rule('.Needle', background_image='url("%sfly_needle.png")' % IMG)
    rule('#tw_card', background_image='url("%sfly_card.png")' % IMG)
    rule('.Lubber', background_image='url("%sfly_lubber.png")' % IMG)
    rule('.Bezel', background_image='url("%sfly_bezel.png")' % IMG)
    for i in range(72): rule('.GLayer.a%d' % i, transform='rotateZ(%ddeg)' % (i * 5))
    label('#tw_alt_drum', 46, 18, (GS - 46) // 2, 96, 13, MONO, '#e8dcc0', 'center', background_color='#0c0a08e6', text_shadow=NOSHADOW)
    label('#tw_hdg_txt', 40, 18, (GS - 40) // 2, 74, 14, MONO, '#f0d48a', 'center', background_color='#0c0a08d0', text_shadow=NOSHADOW)

    def gauge(face, layer, cls, extra='', first=False):
        return P(None, 'Gauge' + (' First' if first else ''), P(face, 'GFace') + P(layer, 'GLayer ' + cls) + extra + P(None, 'GFace Bezel'))
    compass = P(None, 'Gauge', P('tw_card', 'GLayer') + P(None, 'GFace Lubber') + P('tw_hdg_txt', tag='Label') + P(None, 'GFace Bezel'))
    row = (gauge('tw_g_bank', 'tw_n_bank', 'Needle', first=True) + gauge('tw_g_asi', 'tw_n_asi', 'Needle') + compass +
           gauge('tw_g_alt', 'tw_n_alt', 'Needle', P('tw_alt_drum', tag='Label')) + gauge('tw_g_rpm', 'tw_n_rpm', 'Needle'))
    box('#tw_side', SIDE_W, SIDE_H, center=True, cx=DASH_W // 2 + 10 + SIDE_W // 2, y=812, **bg('fly_side.png'))
    rule('#tw_counter', width='130px', height='48px', margin_left='10px', margin_top='14px', **bg('fly_counter.png'))
    label('#tw_ammo_txt', 130, 40, 0, 6, 26, MONO, '#f0e6c8', 'center', letter_spacing='9px')
    rule('#tw_lamps', width='104px', height='44px', margin_left='23px', margin_top='98px', flow_children='right')
    rule('.Lamp', width='44px', height='44px', margin_left='16px', **bg('fly_lamp_off.png'))
    rule('.Lamp.First', margin_left='0px')
    rule('.Lamp.on', background_image='url("%sfly_lamp_on.png")' % IMG)
    side = P('tw_side', '', P('tw_counter', '', P('tw_ammo_txt', tag='Label')) +
             P('tw_lamps', '', P('tw_bomb1', 'Lamp First') + P('tw_bomb2', 'Lamp')))
    fly = P('tw_fly', '', P('tw_fly_help', tag='Label', text='MOUSE aim    A / D roll    W / S throttle    MOUSE 1 guns    MOUSE 2 bomb') +
            P('tw_fly_info', tag='Label') + P('tw_dash', '', P('tw_dashrow', '', row)) + side)
    parts.append(fly)

    # ---- never shown: makes CS2 compile the loading slides and the map icon along with the HUD (create/panorama.py preload)
    pre = ['map_icons/screenshots/1080p/%s%s.png' % (NAME, '_%d' % n if n else '') for n in range(SLIDES)] + ['map_icons/map_icon_%s.svg' % NAME]
    kids = ''
    for i, src in enumerate(pre):
        rule('.HudPre%d' % (i + 1), width='1px', height='1px', opacity='0', visibility='collapse', background_image='url("file://{images}/%s")' % src)
        kids += P(None, 'HudPre%d' % (i + 1))
    rule('.HudPreload', width='1px', height='1px', visibility='collapse')
    parts.append(P(None, 'HudPreload', kids))

    body = P(None, 'TWRoot', P(None, 'Screen', '\n\t\t\t'.join([''] + parts) + '\n\t\t'))
    return ('<root>\n\t<styles>\n\t\t<include src="file://{resources}/styles/custom_game/%s.css" />\n\t</styles>\n\t%s\n</root>\n' % (NAME, body))


SLIDES = 3


# ================================================================ checks
def check_contract(xml, css_text):
    con = read_contract()
    prob = []
    xids = re.findall(r'\bid="([^"]+)"', xml)
    dup = sorted(set(i for i in xids if xids.count(i) > 1))
    prob += ['duplicate panel id %s' % i for i in dup]
    has_cls = lambda c: re.search(r'\.%s(?![\w-])' % re.escape(c), css_text) is not None
    for i, r in con.items():
        if i not in xids: prob.append('contract id %s is not in the layout' % i)
        for c in r['classes']:
            if not has_cls(c): prob.append('class .%s (of %s) has no css rule' % (c, i))
    lit, pre = script_ids()
    for i in sorted(lit):
        if i not in con: prob.append('the script writes %s, which is not in the docs/HUD.md contract' % i)
    for p in sorted(pre):
        if p == '<marker>y': continue
        if not any(i.startswith(p) for i in con): prob.append('the script builds ids from "%s", which matches no contract id' % p)
    used = lambda i: i in lit or any(i.startswith(p) and re.match(r'^\d+y?$', i[len(p):]) for p in pre if p != '<marker>y') or \
        (i.endswith('y') and (i[:-1] in lit or any(i[:-1].startswith(p) for p in pre if p != '<marker>y')))
    for i in con:
        if not used(i): prob.append('contract id %s is not written by the script (stale row?)' % i)
    return prob, con, xids


def states():
    s = {}
    s['lobby'] = {'_chat_top': 800, 'tw_brief': {'add': ['show']}, 'tw_brief_role': {'text': 'TRENCH MORTAR CREW'},
                  'tw_brief_l1': {'text': 'Crew 2 of 5. Plot targets at the map table,'}, 'tw_brief_l2': {'text': 'fetch bombs from the ammunition box,'},
                  'tw_brief_l3': {'text': 'load and fire the mortar. Swap jobs freely.'},
                  'tw_brief_count': {'text': 'Moving up in 3s   (chat: !mortar  !infantry  !roles)'},
                  'tw_info': {'add': ['show']}, 'tw_info_title': {'text': 'COMBAT ROLES'}, 'tw_info_l1': {'text': 'INFANTRY (11)  -  !infantry'},
                  'tw_info_l2': {'text': 'MORTARS (4/10)  -  !mortar'}, 'tw_info_l3': {'text': 'AIRCRAFT (2/5)  -  !air'},
                  'tw_info_l4': {'text': '!swap  -  switch between unlocked primaries'}, 'tw_info_foot': {'text': "Type a role's command to see its orders and ask for it."},
                  'tw_toast': {'add': ['show']}, 'tw_toast_text': {'text': 'Mortar crews are full - you\'re next in line'}}
    s['infantry'] = {'tw_status': {'add': ['show']}, 'tw_st_role': {'text': 'INFANTRY'}, 'tw_st_l1': {'text': 'Rifle: Lee-Enfield'},
                     'tw_st_l2': {'text': 'Streak 2 / 3 for an upgrade'}, 'tw_st_l3': {'text': 'Kills: 7'},
                     'tw_prompt': {'add': ['show']}, 'tw_prompt_text': {'text': 'Dressing station - patching you up'},
                     'tw_toast': {'add': ['show']}, 'tw_toast_text': {'text': 'Standard agent model from your next deploy - !uniform to undo'},
                     'tw_banner': {'add': ['show']}, 'tw_banner_title': {'text': 'MARKSMAN'}, 'tw_banner_sub': {'text': 'Mondragon self-loader issued.  SHIFT+E or !swap: back to the Gewehr 98'}}
    s['unlock'] = {'tw_status': {'add': ['show']}, 'tw_st_role': {'text': 'TRENCH MORTAR CREW'}, 'tw_st_l1': {'text': 'Crew 3  -  mate: Pte. Atkins'},
                   'tw_st_l2': {'text': 'Tube: LOADED   Target: set'}, 'tw_st_l3': {'text': 'Mortar kills: 4   (bomb in hand)'},
                   'tw_banner': {'add': ['show']}, 'tw_banner_title': {'text': 'THE WAY TO THE WOOD IS OPEN'},
                   'tw_banner_sub': {'text': 'Ladder at the north end of the fire trench'},
                   'tw_info': {'add': ['show']}, 'tw_info_title': {'text': 'AIRCRAFT'}, 'tw_info_l1': {'text': '!air to nominate to be a pilot.'},
                   'tw_info_l2': {'text': 'Mouse steers, W/S throttle, A/D roll.'}, 'tw_info_l3': {'text': 'MOUSE1 guns, MOUSE2 bombs.'},
                   'tw_info_l4': {'text': '2 lives, back to ground.'}, 'tw_info_foot': {'text': "Nominated - you're more likely to be posted to the aerodrome."}}
    def mark(st, mid, x, y):
        st[mid] = {'add': ['on', 'x%d' % x]}; st[mid + 'y'] = {'add': ['y%d' % y]}
    for team, pic in (('sight_ct', 'mct'), ('sight_t', 'mt')):
        st = {'tw_target': {'add': ['show']}, 'tw_tmap': {'add': [pic]},
              'tw_t_range': {'text': 'RANGE  118 m'}, 'tw_t_grid': {'text': 'GRID  H6   LOCKED'}, 'tw_t_tube': {'text': 'TUBE  LOADED'},
              'tw_t_state': {'text': 'READY - JUMP TO FIRE'}, 'tw_toast': {'add': ['show']}, 'tw_toast_text': {'text': 'Target locked: H6'}}
        mark(st, 'tw_pit', 140, 176); mark(st, 'tw_imp0', 88, 70); mark(st, 'tw_imp1', 97, 64); mark(st, 'tw_lock', 92, 66); mark(st, 'tw_ret', 100, 58)
        s[team] = st
    s['fly'] = {'tw_fly': {'add': ['show']}, 'tw_n_asi': {'add': ['a14']}, 'tw_n_alt': {'add': ['a20']}, 'tw_n_rpm': {'add': ['a8']},
                'tw_card': {'add': ['a62']}, 'tw_n_bank': {'add': ['a69']}, 'tw_alt_drum': {'text': '0 4'}, 'tw_hdg_txt': {'text': '050'},
                'tw_ammo_txt': {'text': '0437'}, 'tw_bomb1': {'add': ['on']},
                'tw_fly_info': {'text': 'LIVES 2   KILLS 3   BOMB 6s'}, 'tw_toast': {'add': ['show']}, 'tw_toast_text': {'text': 'Bomb away!'}}
    return s


def background(path):
    """what the gate draws the HUD over: a bright overcast sky over a dark parapet and mud (worst cases for both text colours)"""
    W, H = 2333, 1080
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    sky = np.array([178, 182, 176], np.float32) + (y / H)[..., None] * np.array([-30, -28, -24])
    hor = 560 + 40 * np.sin(x / 210.0) + 18 * np.sin(x / 47.0)
    mud = np.array([70, 58, 44], np.float32) * (0.75 + 0.25 * smooth_noise(H, W, 30, 9))[..., None]
    a = np.where((y > hor)[..., None], mud, sky)
    a = a * (0.92 + 0.08 * smooth_noise(H, W, 7, 10))[..., None]
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(path)


def main():
    global css
    if '--no-art' not in sys.argv: make_art()
    css = []
    xml = build_layout()
    lay = os.path.join(OUT, 'panorama/layout/custom_game'); sty = os.path.join(OUT, 'panorama/styles/custom_game')
    os.makedirs(lay, exist_ok=True); os.makedirs(sty, exist_ok=True)
    css_text = '\n'.join(css)
    open(os.path.join(lay, NAME + '.xml'), 'w', newline='\n', encoding='utf-8').write(xml)
    open(os.path.join(sty, NAME + '.css'), 'w', newline='\n', encoding='utf-8').write(css_text)
    prob, con, xids = check_contract(xml, css_text)
    # every picture the css names exists (target_t/ct come from render_sight.py; slides and icon from render_slides.py)
    for u in sorted(set(re.findall(r'\{images\}/([^"\')]+)', css_text))):
        if not os.path.exists(os.path.join(OUT, 'panorama/images', u)):
            (prob if 'custom_game/' in u else NOTES).append('picture missing: %s' % u)
    json.dump(dict(tm=TM, steps=STEPS, marker=MK, ids=sorted(con)), open(os.path.join(ROOT, 'out', 'hud.json'), 'w'))
    s8 = os.path.join(ROOT, 'out', 'step8'); os.makedirs(os.path.join(s8, 'hud'), exist_ok=True)
    json.dump(states(), open(os.path.join(s8, 'hud_states.json'), 'w'), indent=1)
    print('hud: %d css rules, %d panel ids (%d in the contract), %d KB css' % (len(css), len(xids), len(con), len(css_text) // 1024))
    for n in NOTES: print('NOTE:', n)
    for p in prob: print('CONTRACT:', p)
    rc = 1 if prob else 0
    if '--no-check' not in sys.argv:
        import hud_check
        bgp = os.path.join(s8, 'hud_bg.png')
        if not os.path.exists(bgp): background(bgp)
        lf = []
        for fam, f in (('Noto Serif', 'notoserif-bold.ttf'), ('"Noto Serif"', 'notoserif-bold.ttf'), ('Stratum2', None), ('"Noto Mono"', 'notomono-regular.ttf'), ('Noto Mono', 'notomono-regular.ttf')):
            path = os.path.join(CS2FONTS, f) if f else 'C:/Windows/Fonts/bahnschrift.ttf'
            if os.path.exists(path): lf += ['--label-font', '%s=%s' % (fam.strip('"'), path)]
        rc |= hud_check.main(['--addon', OUT, '--name', NAME, '--states', os.path.join(s8, 'hud_states.json'), '--out', os.path.join(s8, 'hud', 'hud'),
                              '--bg', bgp] + lf)
    sys.exit(rc)


NOTES = []
if __name__ == '__main__':
    main()
