"""A small stand-in for CS2's Panorama, just enough for the Space Racer HUD: reads the generated layout xml and css,
lays the panels out the way the HUD is written (fixed sizes, pinned from the top and the left / centre / right, pixel
text rows flowing right) and draws them with the real HUD pictures. It also checks the layout rules the HUD relies on
(every panel has a fixed size, nothing hangs off its parent, no vertical centring, no negative margins outside text
rows), checks that nothing of ours sits where CS2 draws its own HUD over it (chat, kill feed, team counter, money /
health row; see cs2_zones) and prints anything that breaks them.

usage: hud_render.py <addon_out_dir> <background.png> <out_prefix>
writes <out_prefix>_race.png, _grid.png, _lobby.png, _results.png, _help.png at 1920x1080, _race_wide.png at 2333x1080
(the screen in Zach's recording), _race_43.png at 1440x1080 and _cs2.png (the race HUD with CS2's own places marked)."""
import os, re, sys, json
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

OUT = IMGDIR = ROOT = RULES = HT = None     # set by init() (importable: preview/workshop_shots.py lays out the HUD too)
BYID = {}
H = 1080
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf'

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
    return dict(tag=tag.group(0) if tag else None, ids=re.findall(r'#([\w-]+)', s), cls=re.findall(r'\.([\w-]+)', s))

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
        tx = sum(float(v) for v in re.findall(r'translatex\(\s*(-?[\d.]+)px', tr))
        ty = sum(float(v) for v in re.findall(r'translatey\(\s*(-?[\d.]+)px', tr))
        o = op * float(st.get('opacity', '1'))
        out.append((k, kx + tx, ky + ty, ow, oh, bw, o, st))
        layout(k, kx + bw + tx, ky + bw + ty, kw, kh, o, out, W, p)

# ---------------------------------------------------------------- drawing
_img = {}
def picture(url):
    m = re.search(r'custom_game/spr/([^"\)]+)', url)
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

# ---------------------------------------------------------------- CS2's own HUD: ours keeps out of its places
# CS2 draws chat, the kill feed, the team counter and the money / health row on top of a custom HUD, so nothing of
# ours may sit under them (numbers from CS2's hudchat / huddeathnotice / hud styles, 1080 high). Checked at 16:9 and
# wider; on 4:3 the chat is 40% of the screen's width, so long centre lines can reach it there.
def cs2_zones(W, state):
    z = [('CS2 KILL FEED', W - 430, 72, W, 190),                  # right, margin-top 72, ~36 px a line (3 lines here)
         ('CS2 TEAM COUNTER', W / 2 - 360, 0, W / 2 + 360, 66),    # avatars, round time, scores
         ('CS2 MONEY / HEALTH', 0, 1000, W, H)]
    # chat (box x 18-571, its text 28-561): its last few lines always (up from about y 934), the whole box (from y 609)
    # while someone types. In the lobby the first car card may sit behind the open chat box (CS2 draws the box over it).
    z.append(('CS2 CHAT', 0, 800 if state == 'lobby' else 600, 576, 1010))
    return z

def drawn(item):
    k, x, y, w, h, bw, op, st = item
    if op <= 0.01 or w <= 0 or h <= 0 or 'Full' in k.cls: return False
    bg = color(st.get('background-color', '#00000000'))
    return bool((bg and bg[3]) or ('background-image' in st and picture(st['background-image']) is not None)
                or 'border' in st or (k.tag == 'Label' and k.text))

def top_of(k):
    """the HUD piece a panel belongs to: its ancestor straight under the Screen panel"""
    while k.parent is not None and 'Screen' not in k.parent.cls: k = k.parent
    return k

def zone_check(items, W, state):
    rect = {id(it[0]): it[1:5] for it in items}
    for (zn, x0, y0, x1, y1) in cs2_zones(W, state):
        hit = []
        for it in items:
            if not drawn(it): continue
            k, x, y, w, h = it[:5]
            if x < x1 and x + w > x0 and y < y1 and y + h > y0:
                t = top_of(k)
                if t not in hit: hit.append(t)
        for t in hit:
            x, y, w, h = rect.get(id(t), (0, 0, 0, 0))
            nm = t.id or '.'.join(sorted(c for c in t.base if not re.match(r'^L\d+$', c)))
            problems.append('%s at %d wide: %s (%d,%d %dx%d) is under %s' % (state, W, nm, x, y, w, h, zn))

def zones_picture(img, W, state, name):
    im = img.convert('RGB')            # (drawing in RGBA onto an RGB picture blends; onto RGBA it would overwrite)
    d = ImageDraw.Draw(im, 'RGBA')
    f = ImageFont.truetype(FONT, 22)
    for (zn, x0, y0, x1, y1) in cs2_zones(W, state):
        d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=(255, 255, 255, 46), outline=(255, 255, 255, 220), width=3)
        d.text((x0 + 10, y0 + 6), zn, font=f, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
    im.convert('RGB').save(name)

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
            tx0 = bw
            if st.get('text-align') == 'right': tx0 = w - bw - d.textlength(k.text.upper(), font=f) - 2
            d.text((tx0 + 2, bw + 2), k.text.upper(), font=f, fill=(0, 0, 0, 255))
            d.text((tx0, bw), k.text.upper(), font=f, fill=col)
        if op < 1:
            a = layer.getchannel('A').point(lambda v: int(v * op)); layer.putalpha(a)
        img.alpha_composite(layer, (int(round(x)), int(round(y))))

# ---------------------------------------------------------------- state -> picture
def reset():
    def r(n):
        n.cls = set(n.base); n.text_v = None
        if n.tag == 'Label': n.text = ''
        for k in n.kids: r(k)
    r(ROOT)

def add(id_, *cls):
    n = BYID[id_]
    for c in cls:
        if c: n.cls.add(c)
def swap(id_, prefix_re, cls):
    n = BYID[id_]
    n.cls = set(c for c in n.cls if not re.match(prefix_re, c))
    if cls: n.cls.add(cls)

COL = {'gold': 'cY', 'red': 'cR', 'green': 'cG', 'cyan': 'cC', 'pink': 'cP', 'white': 'cW'}
def text(id_, t, color=None, fx=None):
    n = HT['slots'][id_]
    t = t[:n]
    al = HT['align'].get(id_, 'left')
    if al == 'center': t = ' ' * ((n - len(t)) // 2) + t
    elif al == 'right': t = t.rjust(n)
    for k in range(n):
        ch = t[k] if k < len(t) else ' '
        swap('%s_%d' % (id_, k), r'^g\d+$', None if ch == ' ' else 'g%d' % ord(ch.upper() if ch.upper() in HT['charset'] else '?'))
    if color: swap(id_, r'^c[WYCRGP]$', COL.get(color, color))
    if fx: add(id_, fx)

def dots(cells, me, lead):
    for k, c in enumerate(cells):
        add('spr_md%d' % k, 'On', 'x%d' % c[0]); add('spr_mdy%d' % k, 'y%d' % c[1], c[2])
    add('spr_dot', 'On', 'x%d' % me[0]); add('spr_doty', 'y%d' % me[1])
    add('spr_ldot', 'On', 'x%d' % lead[0]); add('spr_ldoty', 'y%d' % lead[1])

def race_state(grid=False, results=False):
    reset()
    add('spr_root', 'stOn')
    if grid: add('spr_root', 'stPickMini')
    if results: add('spr_root', 'stRes')
    add('spr_mmimg', 'mm_oval')
    text('spr_pos', '3', 'green'); text('spr_suf', 'RD', 'green'); text('spr_posof', '/32', 'pink')
    text('spr_tt', 'T 5', 'gold'); text('spr_tct', '3 CT', 'cyan')
    text('spr_lap', 'FINAL LAP' if not grid else 'LAP 1/3', 'red' if not grid else 'gold')
    text('spr_clock', 'GRID' if grid else '1:42', 'gold' if grid else 'white')
    text('spr_laptime', '-' if grid else '0:31.2', 'white'); text('spr_best', '-' if grid else '0:29.8', 'gold')
    if results:
        rows = [('1ST', 'SKINK52', '1:42.31'), ('2ND', 'BOT14', '+0.84'), ('3RD', 'MARLOW', '+2.10'), ('4TH', 'BOT3', '+3.95'),
                ('5TH', 'VEXIS', '+5.02'), ('6TH', 'BOT28', '+9.77'), ('7TH', 'BOT9', 'WRECKED'), ('12TH', 'YOU', '+21.40')]
        for i, (p_, n_, t_) in enumerate(rows):
            BYID['spr_rbp%d' % i].text = p_; BYID['spr_rbn%d' % i].text = n_; BYID['spr_rbt%d' % i].text = t_
            add('spr_rb%d' % i, 'T' if i % 2 == 0 else 'CT')
            if i < 3: add('spr_rb%d' % i, 'p%d' % (i + 1))
        add('spr_rb7', 'me')
        text('spr_msg', 'WRECKED - 12TH OF 32 - BEST LAP 0:29.8', 'cyan')     # the longest bottom line there is
    text('spr_abtxt', 'E SEEKER BOLT', 'cY'); add('spr_abfill', 'w20'); add('spr_abil', 'ready')
    if grid:
        text('spr_ctr', 'NULL GAP', 'gold'); text('spr_sub', 'YOU START 32ND OF 32  -  NO ATTACKS FOR 6 SECONDS', 'white'); text('spr_abtxt', 'ATTACKS IN 6', 'cW')
        add('spr_mcard2', 'sel')
        for i, k in enumerate(['hornet', 'meteor', 'comet', 'bastion']): swap('spr_mimg%d' % i, r'^pic_', 'pic_%s_ct' % k)
    elif not results:
        text('spr_ctr', 'WRONG WAY', 'red'); text('spr_msg', '+40 CHARGE FROM THE PULSE', 'cyan')
        add('spr_turn', 'l2')
    text('spr_spd', '1286', 'gold')
    add('spr_shfill', 'w14'); add('spr_chfill', 'w9'); add('spr_spfill', 'w17'); add('spr_speed', 'pad')
    names = ['SKINK52', 'BOT14', 'YOU', 'BOT3', 'MARLOW', 'BOT28', 'VEXIS', 'BOT9']
    for i, nm in enumerate(names):
        BYID['spr_stn%d' % i].text = '%d  %s' % (i + 1, nm)
        add('spr_st%d' % i, 'T' if i % 2 == 0 else 'CT')
    add('spr_st2', 'me')
    import random
    rnd = random.Random(3)
    cells = [(rnd.randint(3, 20) * 2, rnd.randint(3, 20) * 2, rnd.choice(['T', 'CT'])) for _ in range(9)]
    dots(cells, (30, 28), (14, 20))

def vote_state(lobby=False):
    # the end of a race with the vote box (a voter: 2nd place, 2 votes, voted HAIRPIN HARBOUR)
    if lobby: lobby_state(); BYID['spr_root'].cls.discard('stPick')
    else: race_state(results=True)
    add('spr_root', 'stVote')
    for i, (nm, n) in enumerate([('SWITCHBACK SPIRE', '3'), ('HAIRPIN HARBOUR', '2'), ('SKYWAY', ''), ('NULL GAP', '1')]):
        text('spr_vn%d' % i, nm, 'gold' if i == 1 else 'white', 'pulse' if i == 1 else None); text('spr_vc%d' % i, n, 'cyan')
    text('spr_vf', 'YOUR VOTE X2  W/S', 'gold')

def lobby_state():
    reset()
    add('spr_root', 'stLobby', 'stPick')
    text('spr_lob1', 'THE RACE STARTS IN 7', 'white'); text('spr_lob2', 'YOUR CAR: METEOR - RAM  (A / D TO CHANGE)', 'gold')
    text('spr_lob3', 'NEXT: SOLAR OVAL - 3 LAPS  RECORD 0:41.2 SKINK52', 'cyan')
    add('spr_card1', 'sel')
    for i, k in enumerate(['hornet', 'meteor', 'comet', 'bastion']): swap('spr_cimg%d' % i, r'^pic_', 'pic_%s_t' % k)
    text('spr_msg', 'CAMERA: HIGH  (!CAM HIGH/FAR/NEAR)', 'cyan')

def help_state():
    race_state(); add('spr_root', 'stHelp'); text('spr_ctr', ''); text('spr_msg', '')

def render(W, bgpath, name):
    bg = Image.open(bgpath).convert('RGBA')
    sc = max(W / bg.width, H / bg.height)
    bg = bg.resize((int(bg.width * sc + 1), int(bg.height * sc + 1)), Image.BILINEAR)
    bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    ROOT.st = style(ROOT)
    items = []
    ROOT.st = style(ROOT)
    layout(ROOT, 0, 0, W, H, 1.0, items, W)
    img = bg.copy()
    draw(items, img)
    img.convert('RGB').save(name)
    return img

def check(W, state):
    """layout only, then CS2's places (see cs2_zones)"""
    ROOT.st = style(ROOT)
    items = []
    layout(ROOT, 0, 0, W, H, 1.0, items, W)
    zone_check(items, W, state)

def main():
    global BG, PREFIX
    init(sys.argv[1]); BG, PREFIX = sys.argv[2], sys.argv[3]
    shots = []
    race_state(); img = render(1920, BG, PREFIX + '_race.png'); shots.append(img)
    zones_picture(img, 1920, 'race', PREFIX + '_cs2.png')
    race_state(); render(2333, BG, PREFIX + '_race_wide.png')
    race_state(); render(1440, BG, PREFIX + '_race_43.png')
    race_state(grid=True); shots.append(render(1920, BG, PREFIX + '_grid.png'))
    lobby_state(); shots.append(render(1920, BG, PREFIX + '_lobby.png'))
    race_state(results=True); render(1920, BG, PREFIX + '_results.png')
    help_state(); render(1920, BG, PREFIX + '_help.png')
    vote_state(); render(1920, BG, PREFIX + '_vote.png')
    vote_state(); render(1440, BG, PREFIX + '_vote_43.png')
    for W in (1920, 2333):           # 16:9 and Zach's wide screen
        race_state(); check(W, 'race')
        race_state(grid=True); check(W, 'grid')
        race_state(results=True); check(W, 'results')
        lobby_state(); check(W, 'lobby')
        help_state(); check(W, 'help')
        vote_state(); check(W, 'results')
        vote_state(lobby=True); check(W, 'lobby')
    seen = set()
    for p in problems:
        if p not in seen: seen.add(p); print('LAYOUT:', p)
    print('hud render ->', PREFIX + '_*.png', '(%d layout notes)' % len(seen))
    sys.exit(1 if seen else 0)

if __name__ == '__main__':
    main()
