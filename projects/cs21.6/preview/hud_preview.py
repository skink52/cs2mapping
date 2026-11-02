"""Draws the generated 1.6 HUD (panorama xml + css + pictures) the way the layout is written, over a background
picture, to check it before it goes into CS2. Also flags panels without a fixed size or hanging off their parent.

usage: python3 preview/hud_preview.py <addon out dir> <background.png> <out prefix>
writes <prefix>_alive.png, _raised.png, _buy.png, _rifles.png, _class.png, _43.png (1440 x 1080)
"""
import os, re, sys, json
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

OUT, BG, PREFIX = sys.argv[1:4]
IMGDIR = os.path.join(OUT, 'panorama/images/custom_game/cs16')
H = 1080
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
BYID = {}

# ---------------------------------------------------------------- css
def parse_css(text):
    rules = []
    order = 0
    for line in text.split('\n'):
        line = line.strip()
        if not line or line.startswith('@'): continue
        m = re.match(r'^(.*?)\{(.*)\}$', line)
        if not m: continue
        sel, body = m.group(1).strip(), m.group(2)
        props = {}
        for decl in body.split(';'):
            if ':' not in decl: continue
            k, v = decl.split(':', 1)
            props[k.strip()] = v.strip()
        for s in sel.split(','):
            parts = [compound(p) for p in s.split()]
            spec = (sum(len(p['ids']) for p in parts), sum(len(p['cls']) for p in parts), sum(1 for p in parts if p['tag']))
            rules.append(dict(sel=s.strip(), parts=parts, spec=spec, order=order, props=props))
            order += 1
    return rules

def compound(s):
    tag = re.match(r'^[A-Za-z]\w*', s)
    return dict(tag=tag.group(0) if tag else None, ids=re.findall(r'#([\w-]+)', s), cls=re.findall(r'\.([\w-]+)', s) + (['__hover'] if ':hover' in s else []))

def matches(c, node):
    if c['tag'] and c['tag'] != node.tag: return False
    if c['ids'] and node.id not in c['ids']: return False
    return all(k in node.cls for k in c['cls'])

def rule_matches(r, node):
    parts = r['parts']
    if not matches(parts[-1], node): return False
    a = node.parent
    for c in reversed(parts[:-1]):
        while a is not None and not matches(c, a): a = a.parent
        if a is None: return False
        a = a.parent
    return True

# ---------------------------------------------------------------- xml
class Node:
    def __init__(self, el, parent):
        self.tag = el.tag; self.id = el.get('id'); self.base = set((el.get('class') or '').split()); self.cls = set(self.base)
        self.text = el.get('text'); self.parent = parent
        self.kids = [Node(c, self) for c in el if c.tag in ('Panel', 'Label', 'Image', 'Button')]

def load(out):
    name = [f for f in os.listdir(os.path.join(out, 'panorama/layout/custom_game')) if f.endswith('.xml')][0]
    tree = ET.parse(os.path.join(out, 'panorama/layout/custom_game', name)).getroot()
    top = [c for c in tree if c.tag == 'Panel'][0]
    css = open(os.path.join(out, 'panorama/styles/custom_game', name[:-4] + '.css')).read()
    return Node(top, None), parse_css(css)

def index(n):
    if n.id: BYID[n.id] = n
    for k in n.kids: index(k)

def init(out):
    """read the generated layout, css and text table of the addon in `out`"""
    global OUT, IMGDIR, ROOT, RULES, HT
    OUT = out
    IMGDIR = os.path.join(OUT, 'panorama/images/custom_game/spr')
    ROOT, RULES = load(OUT)
    BYID.clear(); index(ROOT)
    HT = json.load(open(os.path.join(OUT, '_gen/hud_text.json')))

def style(node):
    st = {}
    for r in sorted((r for r in RULES if rule_matches(r, node)), key=lambda r: (r['spec'], r['order'])):
        st.update(r['props'])
    return st

def pxv(v, ref):
    if v is None: return None
    v = v.strip()
    if v.endswith('px'): return float(v[:-2])
    if v.endswith('%'): return float(v[:-1]) / 100 * ref
    return None

# ---------------------------------------------------------------- layout
problems = []
def layout(node, x, y, w, h, op, out, W, path=''):
    """node's content box is (x, y, w, h); lays out and collects draw items for its children"""
    st_parent = node.st
    flow = st_parent.get('flow-children', 'none')
    cx = x
    for k in node.kids:
        st = k.st = style(k)
        p = path + '/' + (k.id or '.'.join(sorted(k.base))[:24])
        if st.get('visibility') == 'collapse': continue
        bw = 0
        if 'border' in st: bw = float(st['border'].split()[0][:-2])
        kw, kh = pxv(st.get('width'), w), pxv(st.get('height'), h)
        if kw is None or kh is None:
            if k.tag == 'Panel' and 'G' not in k.cls: problems.append('no fixed size: ' + p)
            kw = kw or 0; kh = kh or 0
        ml, mt, mr = (pxv(st.get(s), w) or 0 for s in ('margin-left', 'margin-top', 'margin-right'))
        if 'margin-bottom' in st: problems.append('margin-bottom used: ' + p)
        if st.get('vertical-align') not in (None, 'top'): problems.append('vertical-align %s: %s' % (st.get('vertical-align'), p))
        if mt < 0 or (ml < 0 and flow == 'none') or (mr < 0 and flow == 'none'): problems.append('negative margin: ' + p)
        ow, oh = kw + 2 * bw, kh + 2 * bw
        if flow == 'right':
            kx = cx + ml; ky = y + mt; cx = kx + ow + mr
        else:
            al = st.get('horizontal-align', 'left')
            kx = x + ml if al == 'left' else x + (w - ow) / 2 + ml - mr if al == 'center' else x + w - ow - mr
            ky = y + mt
            if flow == 'none' and node.parent is not None and (kx < x - 0.5 or kx + ow > x + w + 0.5 or ky + oh > y + h + 0.5) and 'Dot' not in ' '.join(k.cls) and 'DotSq' not in ' '.join(k.cls):
                if not (W < 1900 and ('Screen' in node.cls)):
                    problems.append('outside parent (%dx%d at %d,%d in %dx%d): %s' % (ow, oh, kx - x, ky - y, w, h, p))
        # transforms (translate only)
        tr = st.get('transform', '')
        m3 = re.search(r'translate3d\(\s*(-?[\d.]+)px,\s*(-?[\d.]+)px', tr)
        tx, ty = (float(m3.group(1)), float(m3.group(2))) if m3 else (0.0, 0.0)
        o = op * float(st.get('opacity', '1'))
        out.append((k, kx + tx, ky + ty, ow, oh, bw, o, st))
        layout(k, kx + bw + tx, ky + bw + ty, kw, kh, o, out, W, p)

# ---------------------------------------------------------------- drawing
_img = {}
def picture(url):
    m = re.search(r'custom_game/cs16/([^"\)]+)', url)
    if not m: return None
    p = os.path.join(IMGDIR, m.group(1))
    if p not in _img: _img[p] = Image.open(p).convert('RGBA') if os.path.exists(p) else None
    return _img[p]

def color(v):
    v = v.strip()
    if v.startswith('#'):
        h_ = v[1:]
        if len(h_) == 6: return tuple(int(h_[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
        if len(h_) == 8: return tuple(int(h_[i:i + 2], 16) for i in (0, 2, 4, 6))
    return None

def draw(items, img):
    font_cache = {}
    for (k, x, y, w, h, bw, op, st) in items:
        if op <= 0.01 or w <= 0 or h <= 0: continue
        layer = Image.new('RGBA', (int(w) + 2, int(h) + 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        bg = color(st.get('background-color', '#00000000'))
        if bg and bg[3]: d.rectangle([0, 0, w - 1, h - 1], fill=bg)
        if 'background-image' in st:
            pic = picture(st['background-image'])
            if pic is not None:
                cw, ch = w - 2 * bw, h - 2 * bw
                bs = st.get('background-size', 'auto')
                if bs.startswith('100% 100%'): sw, sh = cw, ch
                elif bs.endswith('px') and len(bs.split()) == 2: sw, sh = (float(t[:-2]) for t in bs.split())
                else: sw, sh = pic.size
                if st.get('background-repeat') == 'repeat':
                    tile = pic.resize((max(1, int(sw)), max(1, int(sh))), Image.NEAREST)
                    for ty_ in range(0, int(ch), max(1, int(sh))):
                        for tx_ in range(0, int(cw), max(1, int(sw))): layer.alpha_composite(tile, (int(bw + tx_), int(bw + ty_)))
                else:
                    pr = pic.resize((max(1, int(round(sw))), max(1, int(round(sh)))), Image.NEAREST).crop((0, 0, int(cw), int(ch)))
                    layer.alpha_composite(pr, (int(bw), int(bw)))
        if bw:
            bc = color(st['border'].split()[-1])
            for t in range(int(bw)): d.rectangle([t, t, w - 1 - t, h - 1 - t], outline=bc)
        if k.tag == 'Label' and k.text:
            fs = int(pxv(st.get('font-size', '18px'), 0) or 18)
            f = font_cache.get(fs) or ImageFont.truetype(FONT, fs); font_cache[fs] = f
            col = color(st.get('color', '#ffffff')) or (255, 255, 255, 255)
            for li, line in enumerate(k.text.split('\n')):
                tx0 = bw
                lw = d.textlength(line, font=f)
                if st.get('text-align') == 'right': tx0 = w - bw - lw - 2
                elif st.get('text-align') == 'center': tx0 = (w - lw) / 2
                ly = bw + li * fs * 1.3
                d.text((tx0 + 1, ly + 1), line, font=f, fill=(0, 0, 0, 255))
                d.text((tx0, ly), line, font=f, fill=col)
        if op < 1:
            a = layer.getchannel('A').point(lambda v: int(v * op)); layer.putalpha(a)
        img.alpha_composite(layer, (int(round(x)), int(round(y))))


class Node:
    def __init__(self, el, parent):
        self.tag = el.tag; self.id = el.get('id'); self.base = set((el.get('class') or '').split()); self.cls = set(self.base)
        self.text0 = el.get('text'); self.text = self.text0; self.parent = parent
        self.kids = [Node(c, self) for c in el if c.tag in ('Panel', 'Label', 'Image', 'Button')]


tree = ET.parse(os.path.join(OUT, 'panorama/layout/custom_game/cs16.xml')).getroot()
ROOT = Node([c for c in tree if c.tag == 'Panel'][0], None)
RULES = parse_css(open(os.path.join(OUT, 'panorama/styles/custom_game/cs16.css')).read())
def index(n):
    if n.id: BYID[n.id] = n
    for k in n.kids: index(k)
index(ROOT)
HUDJ = json.load(open(os.path.join(OUT, '_gen/hud.json')))


def reset():
    def r(n):
        n.cls = set(n.base); n.text = '' if n.text0 == '{s:v}' else n.text0
        for k in n.kids: r(k)
    r(ROOT)
def on(id_, *cls):
    for c in cls: BYID[id_].cls.add(c)
def off(id_, *cls):
    for c in cls: BYID[id_].cls.discard(c)
def var(id_, text): BYID[id_].text = text
def num(row, n, cells, pad=0):
    s = str(n).rjust(pad, '0') if pad else str(n)
    s = s[-cells:]
    for k in range(cells):
        j = k - (cells - len(s))
        node = BYID['%s_%d' % (row, k)]
        node.cls = set(c for c in node.cls if not re.match(r'^d\d$', c))
        if j >= 0: node.cls.add('d' + s[j])


def alive_state():
    reset()
    on('cs_root', 'stOn', 'stAlive', 'stTimer')
    num('cs_hp', 100, 3); num('cs_ap', 87, 3); on('cs_api', 'suith')
    num('cs_tm', 145, 4, 3); num('cs_mn', 3250, 5); num('cs_ac', 30, 3); num('cs_ar', 90, 3)
    on('cs_amb', 'on'); on('cs_ami', 'am_762nato'); on('cs_ibuy', 'on'); on('cs_ic4', 'on')
    on('cs_mdb', 'on'); on('cs_mds', 'plus'); num('cs_md', 300, 5); on('cs_hpb', 'hot')
    on('cs_topb', 'on'); var('cs_top', 'DE_DUST2')


def menu_state(page):
    alive_state()
    on('cs_root', 'stMenu')
    if page == 'main':
        var('cs_mtitle', 'Buy Menu')
        rows = [(str(i + 1), HUDJ['cats'][k], '', None, '') for i, k in enumerate(['pistol', 'shotgun', 'smg', 'rifle', 'mg', 'ammo1', 'ammo2', 'equip'])]
        rows += [('R', 'RE-BUY PREVIOUS', '', None, ''), ('0', 'CANCEL', '', None, '')]
        hover = 3
    elif page == 'rifle':
        var('cs_mtitle', HUDJ['cats']['rifle'])
        ids = ['galil', 'ak47', 'scout', 'sg552', 'awp', 'g3sg1']
        prices = [2000, 2500, 2750, 3500, 4750, 5000]
        rows = [(str(i + 1), HUDJ['items'][k]['label'], '$%d' % p, 'pic_' + k, HUDJ['items'][k]['info']) for i, (k, p) in enumerate(zip(ids, prices))]
        rows.append(('0', 'CANCEL', '', None, ''))
        hover = 1
    else:
        var('cs_mtitle', 'CHOOSE A CLASS')
        ids = ['terror', 'leet', 'arctic', 'guerilla']
        rows = [(str(i + 1), HUDJ['classes'][k]['label'], '', 'pic_' + k, HUDJ['classes'][k]['info']) for i, k in enumerate(ids)]
        rows.append(('5', 'AUTO-SELECT', '', 'pic_t_random', ''))
        hover = 0
    var('cs_mfoot', '$3250')
    for i, (key, text, price, pic, info) in enumerate(rows):
        on('cs_mb%d' % i, 'on'); var('cs_ml%d' % i, key + '  ' + text); var('cs_mp%d' % i, price)
        if pic: on('cs_mpic%d' % i, pic)
        var('cs_mi%d' % i, info)
        if price and int(price[1:]) > 3250: on('cs_mb%d' % i, 'dis')
    on('cs_mb%d' % hover, '__hover')


def render(name, W=1920):
    ROOT.st = style(ROOT)
    items = []
    layout(ROOT, 0, 0, W, H, 1.0, items, W)
    bg = Image.open(BG).convert('RGBA').resize((W, H))
    draw(items, bg)
    bg.convert('RGB').save('%s_%s.png' % (PREFIX, name))


problems = []
alive_state(); render('alive')
on('cs_root', 'stRaised'); render('raised')
alive_state(); on('cs_ic4', 'blink'); render('43', 1440)
menu_state('main'); render('buy')
menu_state('rifle'); render('rifles')
menu_state('class'); render('class')
for p in sorted(set(problems)): print('problem:', p)
print('written', PREFIX + '_*.png')
