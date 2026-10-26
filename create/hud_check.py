"""hud_check.py: a small stand-in for CS2's Panorama, enough to check a custom_hud_layout before CS2 sees it.

It reads the layout xml and its css, lays the panels out the way Panorama would for a static HUD (fixed sizes,
pinned from the top and from the left / centre / right, rows that flow right or down, translate transforms, opacity)
and draws them with the real HUD pictures. Then it checks:
  - the layout rules learned in CS2: every Panel has a fixed width and height (no fit-children), no margin-bottom,
    no vertical-align other than top, no negative margins outside flow rows, nothing hanging off its parent;
  - only the panel types a custom HUD supports (Panel, Label, Image, Button), no duplicate ids, no id on the
    top panel (CS2's CustomHud validation refuses it);
  - CS2's own HUD zones: nothing of ours under the kill feed, the team counter, the money / health row or the chat
    (CS2 draws those on top of a custom HUD). See cs2_zones().
It prints every problem as "LAYOUT: ..." and exits 1 if there is any, so a build script can stop on it.

usage:
  hud_check.py <layout.xml> [options]
  hud_check.py --addon <addon content root> --name <layout name> [options]
options:
  --css PATH          stylesheet (default: the layout's <include>, else <layout>.css next to the xml)
  --images DIR        what file://{images}/ means (default: the panorama/images folder above the layout)
  --states FILE.json  states to draw and check (see below); default: one state, the layout as written
  --out PREFIX        pictures: PREFIX_<state>.png (1920 wide), PREFIX_<state>_<W>.png, PREFIX_cs2.png (zones marked)
  --bg PNG            picture behind the HUD (default: a grey gradient)
  --check-widths 1920,2333     screen widths to check (Panorama scales every screen to 1080 high)
  --picture-widths 1920,2333,1440
  --allow-outside CLS / --allow-nosize CLS / --allow-valign   relax a rule for panels with class CLS (repeatable)
  --glyph-class g%d   class pattern the "glyphs" state key sets on each character panel

States JSON: {"state name": {"panelId": {"add": [classes], "remove": [classes], "text": "label text",
                                          "glyphs": "TEXT"}, "_extends": "other state", "_chat_top": 800}}
  "glyphs" sets glyph_class % ord(char) on the panel's children in order (one image panel per character, as
  panorama.py's pixel-text rows are built); "_chat_top" is where CS2's chat box starts in that state (600 while
  someone types, ~800 for only the last chat lines; default 600).

From space-racer-cs2/preview/hud_render.py (MIT), made project-neutral.
"""
import os, re, sys, json, argparse
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

H = 1080                                    # Panorama lays every screen out 1080 high
SUPPORTED = ('Panel', 'Label', 'Image', 'Button')
SKIP_TAGS = ('styles', 'scripts', 'snippets')
FONT_CANDIDATES = ['/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf',
                   '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                   '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
                   'C:/Windows/Fonts/arialbd.ttf', '/Library/Fonts/Arial Bold.ttf']
_fonts = {}


def font(size):
    """a bold sans font at `size` px; Pillow's built-in font if none of the usual ones is installed"""
    if size not in _fonts:
        f = None
        for p in FONT_CANDIDATES:
            if os.path.exists(p):
                f = ImageFont.truetype(p, size); break
        if f is None:
            try: f = ImageFont.load_default(size)
            except TypeError: f = ImageFont.load_default()
        _fonts[size] = f
    return _fonts[size]


# ---------------------------------------------------------------- css
def parse_css(text):
    """css text -> list of rules {sel, parts, spec, order, props}. Comments and @keyframes blocks are skipped.
    parts = [(compound, combinator)] where combinator is ' ' (descendant) or '>' (child) to the NEXT part."""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    rules, order, i = [], 0, 0
    while True:
        j = text.find('{', i)
        if j < 0: break
        sel = text[i:j].strip()
        depth, k = 1, j + 1
        while k < len(text) and depth:
            depth += {'{': 1, '}': -1}.get(text[k], 0); k += 1
        body = text[j + 1:k - 1]
        i = k
        if sel.startswith('@') or not sel: continue
        props = {}
        for decl in body.split(';'):
            if ':' not in decl: continue
            a, b = decl.split(':', 1)
            props[a.strip().lower()] = b.replace('!important', '').strip()
        for s in sel.split(','):
            s = s.strip()
            if not s: continue
            toks = re.findall(r'>|[^\s>]+', s)
            parts, comb = [], ' '
            for t in toks:
                if t == '>': comb = '>'; continue
                parts.append([compound(t), ' '])
                if len(parts) > 1: parts[-2][1] = comb
                comb = ' '
            spec = (sum(len(p[0]['ids']) for p in parts), sum(len(p[0]['cls']) for p in parts),
                    sum(1 for p in parts if p[0]['tag']))
            rules.append(dict(sel=s, parts=parts, spec=spec, order=order, props=props))
            order += 1
    return rules


def compound(s):
    tag = re.match(r'^[A-Za-z]\w*', s)
    return dict(tag=tag.group(0) if tag else None, ids=re.findall(r'#([\w-]+)', s), cls=re.findall(r'\.([\w-]+)', s),
                pseudo=':' in s)      # :hover etc. never match a hittest-off HUD


def matches(c, node):
    if c['pseudo']: return False
    if c['tag'] and c['tag'] != node.tag: return False
    if c['ids'] and node.id not in c['ids']: return False
    return all(k in node.cls for k in c['cls'])


def rule_matches(r, node):
    """does css rule r apply to node (descendant ' ' and child '>' combinators)"""
    parts = r['parts']
    if not matches(parts[-1][0], node): return False
    a = node.parent
    for c, comb in reversed(parts[:-1]):
        if comb == '>':
            if a is None or not matches(c, a): return False
        else:
            while a is not None and not matches(c, a): a = a.parent
            if a is None: return False
        a = a.parent
    return True


def pxv(v, ref):
    """'12px' -> 12, '50%' of ref; anything else (fit-children, auto...) -> None"""
    if v is None: return None
    v = v.strip()
    try:
        if v.endswith('px'): return float(v[:-2])
        if v.endswith('%'): return float(v[:-1]) / 100 * ref
        if re.match(r'^-?[\d.]+$', v): return float(v)
    except ValueError: pass
    return None


def color(v):
    v = (v or '').strip().lower()
    if v.startswith('#'):
        h = v[1:]
        if len(h) in (3, 4): h = ''.join(c * 2 for c in h)
        if len(h) == 6: return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
        if len(h) == 8: return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4, 6))
    m = re.match(r'rgba?\(([^)]*)\)', v)
    if m:
        p = [float(t) for t in m.group(1).replace('/', ',').split(',') if t.strip()]
        a = p[3] if len(p) > 3 else 1.0
        return tuple(int(c) for c in p[:3]) + (int(a * 255 if a <= 1 else a),)
    if v == 'white': return (255, 255, 255, 255)
    if v == 'black': return (0, 0, 0, 255)
    return None


# ---------------------------------------------------------------- xml
class Node:
    def __init__(self, el, parent):
        self.tag = el.tag; self.id = el.get('id'); self.base = set((el.get('class') or '').split())
        self.cls = set(self.base); self.parent = parent; self.st = {}
        self.xml_text = el.get('text') or ''; self.src = el.get('src')
        self.text = '' if '{' in self.xml_text else self.xml_text      # dialog variables start empty
        self.kids = [Node(c, self) for c in el if c.tag not in SKIP_TAGS and isinstance(c.tag, str)]

    def walk(self):
        yield self
        for k in self.kids: yield from k.walk()


class Hud:
    """one layout + stylesheet. apply() a state, layout() it at a screen width, render() / check() it."""

    def __init__(self, xml_path, css_path=None, images=None, opts=None):
        self.opts = dict(allow_outside=[], allow_nosize=[], allow_valign=False, glyph_class='g%d', screen_class='Screen')
        self.opts.update(opts or {})
        self.problems, self.notes = [], []
        tree = ET.parse(xml_path).getroot()
        tops = [c for c in tree if c.tag not in SKIP_TAGS]
        if not tops: raise SystemExit('no panel in ' + xml_path)
        self.root = Node(tops[0], None)
        if self.root.id: self.problems.append('the top panel has an id (%s): CS2 refuses that; wrap it in a plain panel' % self.root.id)
        pan = self._panorama_dir(xml_path)
        if css_path is None:
            css_path = os.path.splitext(xml_path)[0] + '.css'
            for inc in tree.iter('include'):
                s = inc.get('src', '')
                if s.endswith('.css') and pan and os.path.exists(os.path.join(pan, s.split('{resources}/')[-1])):
                    css_path = os.path.join(pan, s.split('{resources}/')[-1]); break
        self.css_path = css_path
        self.rules = parse_css(open(css_path, encoding='utf-8').read())
        self.images = images or (os.path.join(pan, 'images') if pan else os.path.dirname(xml_path))
        self.byid = {}
        for n in self.root.walk():
            if n.tag not in SUPPORTED: self.problems.append('panel type <%s> is not supported by custom_hud_layout (%s)' % (n.tag, n.id or '?'))
            if n.id:
                if n.id in self.byid: self.problems.append('duplicate panel id: ' + n.id)
                self.byid[n.id] = n
        self._img = {}

    @staticmethod
    def _panorama_dir(path):
        p = os.path.abspath(path)
        while p and os.path.basename(p) != 'panorama':
            q = os.path.dirname(p)
            if q == p: return None
            p = q
        return p

    # ------------------------------------------------ state
    def reset(self):
        for n in self.root.walk():
            n.cls = set(n.base)
            n.text = '' if '{' in n.xml_text else n.xml_text

    def apply(self, state, states=None):
        """state: {panelId: {add, remove, text, glyphs}}; '_extends' names a state in `states` applied first"""
        if state.get('_extends') and states: self.apply(states[state['_extends']], states)
        for pid, ch in state.items():
            if pid.startswith('_'): continue
            n = self.byid.get(pid)
            if n is None: self.problems.append('state names a panel that is not in the layout: ' + pid); continue
            for c in ch.get('remove', []): n.cls.discard(c)
            for c in ch.get('add', []): n.cls.add(c)
            if 'text' in ch: n.text = ch['text']
            if 'glyphs' in ch: self.glyphs(n, ch['glyphs'], ch.get('align', 'left'))

    def glyphs(self, n, text, align='left'):
        cells = n.kids
        t = text[:len(cells)]
        if align == 'center': t = ' ' * ((len(cells) - len(t)) // 2) + t
        elif align == 'right': t = t.rjust(len(cells))
        pat = self.opts['glyph_class']
        rx = re.compile('^' + re.escape(pat).replace('%d', r'\d+') + '$')
        for k, cell in enumerate(cells):
            cell.cls = set(c for c in cell.cls if not rx.match(c))
            ch = t[k] if k < len(t) else ' '
            if ch != ' ': cell.cls.add(pat % ord(ch.upper()))

    # ------------------------------------------------ style + layout
    def style(self, node):
        st = {}
        for r in sorted((r for r in self.rules if rule_matches(r, node)), key=lambda r: (r['spec'], r['order'])):
            st.update(r['props'])
        return st

    def _has(self, k, names):
        return any(c in k.cls for c in names)

    def layout(self, W):
        """lays the whole HUD out on a W x 1080 screen; returns draw items (node, x, y, w, h, border, opacity, style)"""
        self.root.st = self.style(self.root)
        items = []
        self._layout(self.root, 0, 0, W, H, float(self.root.st.get('opacity', '1') or 1), items, W, '')
        return items

    def _layout(self, node, x, y, w, h, op, out, W, path):
        flow = node.st.get('flow-children', 'none')
        cx, cy = x, y
        for k in node.kids:
            st = k.st = self.style(k)
            p = path + '/' + (k.id or '.'.join(sorted(k.base))[:24] or k.tag)
            if st.get('visibility') == 'collapse': continue
            bw = 0.0
            if 'border' in st: bw = pxv(st['border'].split()[0], 0) or 0.0
            kw, kh = pxv(st.get('width'), w), pxv(st.get('height'), h)
            if k.tag == 'Image' and k.src and (kw is None or kh is None):
                pic = self.picture(k.src)
                if pic is not None: kw = pic.width if kw is None else kw; kh = pic.height if kh is None else kh
            if kw is None or kh is None:
                if k.tag == 'Panel' and not self._has(k, self.opts['allow_nosize']):
                    self.problems.append('no fixed size (width %s, height %s): %s' % (st.get('width'), st.get('height'), p))
                kw = kw or 0; kh = kh or 0
            ml, mt, mr = (pxv(st.get(s), w) or 0 for s in ('margin-left', 'margin-top', 'margin-right'))
            mb = pxv(st.get('margin-bottom'), h) or 0
            if 'margin-bottom' in st: self.problems.append('margin-bottom used: ' + p)
            va = st.get('vertical-align', 'top')
            if va != 'top' and not self.opts['allow_valign']: self.problems.append('vertical-align %s: %s' % (va, p))
            if mt < 0 or (ml < 0 and flow == 'none') or (mr < 0 and flow == 'none'): self.problems.append('negative margin: ' + p)
            ow, oh = kw + 2 * bw, kh + 2 * bw
            if flow == 'right':
                kx = cx + ml; ky = y + mt; cx = kx + ow + mr
            elif flow == 'down':
                ky = cy + mt; cy = ky + oh + mb
                al = st.get('horizontal-align', 'left')
                kx = x + ml if al == 'left' else x + (w - ow) / 2 + ml - mr if al == 'center' else x + w - ow - mr
            else:
                al = st.get('horizontal-align', 'left')
                kx = x + ml if al == 'left' else x + (w - ow) / 2 + ml - mr if al == 'center' else x + w - ow - mr
                ky = y + mt if va == 'top' else y + (h - oh) / 2 + mt - mb if va == 'center' else y + h - oh - mb
                narrow = W < 1900 and self.opts['screen_class'] in node.cls      # 4:3: the screen panel is cut, not wrong
                if node.parent is not None and not narrow and not self._has(k, self.opts['allow_outside']) and \
                        (kx < x - 0.5 or kx + ow > x + w + 0.5 or ky < y - 0.5 or ky + oh > y + h + 0.5):
                    self.problems.append('outside parent (%dx%d at %d,%d in %dx%d): %s' % (ow, oh, kx - x, ky - y, w, h, p))
            tr = st.get('transform', '')
            tx = sum(float(v) for v in re.findall(r'translatex\(\s*(-?[\d.]+)px', tr, re.I))
            ty = sum(float(v) for v in re.findall(r'translatey\(\s*(-?[\d.]+)px', tr, re.I))
            m3 = re.search(r'translate3d\(\s*(-?[\d.]+)px\s*,\s*(-?[\d.]+)px', tr)
            if m3: tx += float(m3.group(1)); ty += float(m3.group(2))
            try: o = op * float(st.get('opacity', '1'))
            except ValueError: o = op
            out.append((k, kx + tx, ky + ty, ow, oh, bw, o, st))
            self._layout(k, kx + bw + tx, ky + bw + ty, kw, kh, o, out, W, p)

    # ------------------------------------------------ pictures
    def picture(self, url):
        """file://{images}/x.png, s2r://panorama/images/x_png.vtex or a plain path -> RGBA image (None if missing)"""
        m = re.search(r'\{images\}/([^"\')]+)', url) or re.search(r'panorama/images/([^"\')]+)', url)
        rel = m.group(1) if m else url.strip('"\' ')
        rel = re.sub(r'_(png|psd|tga|jpg)\.vtex(_c)?$', r'.\1', rel)
        p = os.path.join(self.images, rel)
        if p not in self._img:
            self._img[p] = Image.open(p).convert('RGBA') if os.path.exists(p) else None
            if self._img[p] is None: self.notes.append('missing image (drawn as a placeholder): ' + rel)
        return self._img[p]

    def _bgurl(self, st):
        m = re.search(r'url\(\s*["\']?([^"\')]+)', st.get('background-image', ''))
        return m.group(1) if m else None

    def drawn(self, item, W):
        """does this item put anything on screen (full-screen layers like flashes or overlays don't count)"""
        k, x, y, w, h, bw, op, st = item
        if op <= 0.01 or w <= 0 or h <= 0 or 'Full' in k.cls: return False
        if w >= 0.9 * W and h >= 0.9 * H: return False
        bg = color(st.get('background-color'))
        return bool((bg and bg[3]) or self._bgurl(st) or 'border' in st or (k.tag == 'Label' and k.text) or
                    (k.tag == 'Image' and k.src))

    def draw(self, items, img):
        for (k, x, y, w, h, bw, op, st) in items:
            if op <= 0.01 or w < 1 or h < 1: continue
            layer = Image.new('RGBA', (int(w) + 2, int(h) + 2), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            bg = color(st.get('background-color'))
            if bg and bg[3]: d.rectangle([0, 0, w - 1, h - 1], fill=bg)
            url = self._bgurl(st) or (k.src if k.tag == 'Image' else None)
            if url:
                cw, ch = w - 2 * bw, h - 2 * bw
                pic = self.picture(url)
                if pic is None:
                    d.rectangle([bw, bw, w - 1 - bw, h - 1 - bw], outline=(255, 0, 255, 200), width=2)
                    d.line([bw, bw, w - 1 - bw, h - 1 - bw], fill=(255, 0, 255, 120), width=1)
                else:
                    bs = st.get('background-size', '100% 100%' if k.tag == 'Image' else 'auto')
                    if bs.startswith('100% 100%'): sw, sh = cw, ch
                    elif bs == 'contain' or bs == 'cover':
                        s = (min if bs == 'contain' else max)(cw / pic.width, ch / pic.height); sw, sh = pic.width * s, pic.height * s
                    elif len(bs.split()) == 2: sw, sh = (pxv(t, r) or r for t, r in zip(bs.split(), (cw, ch)))
                    else: sw, sh = pic.size
                    tile = pic.resize((max(1, int(round(sw))), max(1, int(round(sh)))), Image.NEAREST)
                    if st.get('background-repeat') == 'repeat':
                        for ty_ in range(0, max(1, int(ch)), max(1, int(sh))):
                            for tx_ in range(0, max(1, int(cw)), max(1, int(sw))):
                                layer.alpha_composite(tile.crop((0, 0, min(tile.width, int(cw) - tx_), min(tile.height, int(ch) - ty_))), (int(bw + tx_), int(bw + ty_)))
                    else:
                        layer.alpha_composite(tile.crop((0, 0, int(cw), int(ch))), (int(bw), int(bw)))
            if bw:
                bc = color(st['border'].split()[-1]) or (255, 255, 255, 255)
                for t in range(int(bw)): d.rectangle([t, t, w - 1 - t, h - 1 - t], outline=bc)
            if k.tag == 'Label' and k.text:
                f = font(int(pxv(st.get('font-size', '18px'), 0) or 18))
                col = color(st.get('color', '#ffffff')) or (255, 255, 255, 255)
                s = k.text.upper() if st.get('text-transform') == 'uppercase' else k.text
                tx0 = bw
                if st.get('text-align') == 'right': tx0 = w - bw - d.textlength(s, font=f) - 2
                elif st.get('text-align') == 'center': tx0 = (w - d.textlength(s, font=f)) / 2
                d.text((tx0 + 2, bw + 2), s, font=f, fill=(0, 0, 0, 255))
                d.text((tx0, bw), s, font=f, fill=col)
            if op < 1:
                layer.putalpha(layer.getchannel('A').point(lambda v: int(v * op)))
            img.alpha_composite(layer, (int(round(x)), int(round(y))))

    def render(self, W, bg=None):
        """the HUD drawn on a W x 1080 picture (over bg, a path or None for a grey gradient)"""
        if bg:
            b = Image.open(bg).convert('RGBA')
            sc = max(W / b.width, H / b.height)
            b = b.resize((int(b.width * sc + 1), int(b.height * sc + 1)), Image.BILINEAR)
            img = b.crop(((b.width - W) // 2, (b.height - H) // 2, (b.width - W) // 2 + W, (b.height - H) // 2 + H))
        else:
            img = Image.linear_gradient('L').resize((W, H)).point(lambda v: 40 + v // 3).convert('RGBA')
        self.draw(self.layout(W), img)
        return img

    def check(self, W, state_name='', chat_top=600):
        """layout rules (collected while laying out) and CS2's own HUD zones"""
        items = self.layout(W)
        zone_check(self, items, W, state_name, chat_top)


# ---------------------------------------------------------------- CS2's own HUD: ours keeps out of its places
def cs2_zones(W, chat_top=600):
    """CS2 draws chat, the kill feed, the team counter and the money / health row on top of a custom HUD (numbers from
    CS2's hudchat / huddeathnotice / hud styles, 1080 high). Checked at 16:9 and wider; on 4:3 the chat is 40% of the
    screen's width, so long centre lines can reach it there.
    Chat: box x 18-571 (text 28-561); its last few lines always show (up from ~y 934), the whole box (from y 609)
    while someone types: chat_top 600 = typing, 800 = a state where only the last lines matter (e.g. a lobby)."""
    return [('CS2 KILL FEED', W - 430, 72, W, 190),                  # right, margin-top 72, ~36 px a line (3 lines)
            ('CS2 TEAM COUNTER', W / 2 - 360, 0, W / 2 + 360, 66),    # avatars, round time, scores
            ('CS2 MONEY / HEALTH', 0, 1000, W, H),
            ('CS2 CHAT', 0, chat_top, 576, 1010)]


def top_of(hud, k):
    """the HUD piece a panel belongs to: its ancestor straight under the screen panel (or under the top panel)"""
    sc = hud.opts['screen_class']
    has_screen = any(sc in n.cls for n in hud.root.walk())
    while k.parent is not None and k.parent.parent is not None and \
            not (sc in k.parent.cls if has_screen else k.parent is hud.root): k = k.parent
    return k


def zone_check(hud, items, W, state='', chat_top=600):
    rect = {id(it[0]): it[1:5] for it in items}
    for (zn, x0, y0, x1, y1) in cs2_zones(W, chat_top):
        hit = []
        for it in items:
            if not hud.drawn(it, W): continue
            k, x, y, w, h = it[:5]
            if x < x1 and x + w > x0 and y < y1 and y + h > y0:
                t = top_of(hud, k)
                if t not in hit: hit.append(t)
        for t in hit:
            x, y, w, h = rect.get(id(t), (0, 0, 0, 0))
            nm = t.id or '.'.join(sorted(c for c in t.base if not re.match(r'^L\d+$', c))) or t.tag
            hud.problems.append('%s at %d wide: %s (%d,%d %dx%d) is under %s' % (state or 'layout', W, nm, x, y, w, h, zn))


def zones_picture(img, W, name, chat_top=600):
    """the picture with CS2's own HUD places marked"""
    im = img.convert('RGB')
    d = ImageDraw.Draw(im, 'RGBA')
    for (zn, x0, y0, x1, y1) in cs2_zones(W, chat_top):
        d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=(255, 255, 255, 46), outline=(255, 255, 255, 220), width=3)
        d.text((x0 + 10, y0 + 6), zn, font=font(22), fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
    im.save(name)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Panorama custom HUD layout check (see the docstring at the top).')
    ap.add_argument('layout', nargs='?')
    ap.add_argument('--addon'); ap.add_argument('--name')
    ap.add_argument('--css'); ap.add_argument('--images'); ap.add_argument('--states'); ap.add_argument('--out')
    ap.add_argument('--bg')
    ap.add_argument('--check-widths', default='1920,2333'); ap.add_argument('--picture-widths', default='1920,2333,1440')
    ap.add_argument('--allow-outside', action='append', default=[]); ap.add_argument('--allow-nosize', action='append', default=[])
    ap.add_argument('--allow-valign', action='store_true')
    ap.add_argument('--glyph-class', default='g%d'); ap.add_argument('--screen-class', default='Screen')
    a = ap.parse_args(argv)
    if a.addon:
        if not a.name: ap.error('--addon needs --name')
        xml = os.path.join(a.addon, 'panorama/layout/custom_game', a.name + '.xml')
        css = a.css or os.path.join(a.addon, 'panorama/styles/custom_game', a.name + '.css')
        images = a.images or os.path.join(a.addon, 'panorama/images')
    elif a.layout:
        xml, css, images = a.layout, a.css, a.images
    else:
        ap.error('give a layout xml or --addon/--name')
    hud = Hud(xml, css, images, dict(allow_outside=a.allow_outside, allow_nosize=a.allow_nosize, allow_valign=a.allow_valign,
                                     glyph_class=a.glyph_class, screen_class=a.screen_class))
    states = json.load(open(a.states, encoding='utf-8')) if a.states else {'default': {}}
    cw = [int(v) for v in a.check_widths.split(',') if v]
    pw = [int(v) for v in a.picture_widths.split(',') if v] if a.out else []
    first = True
    for name, st in states.items():
        if name.startswith('_'): continue
        chat = st.get('_chat_top', 600)
        for W in cw:
            hud.reset(); hud.apply(st, states); hud.check(W, name, chat)
        for W in pw:
            hud.reset(); hud.apply(st, states)
            img = hud.render(W, a.bg)
            img.convert('RGB').save('%s_%s%s.png' % (a.out, name, '' if W == 1920 else '_%d' % W))
            if first and W == pw[0]:
                zones_picture(img, W, a.out + '_cs2.png', chat); first = False
    seen = []
    for p in hud.problems:
        if p not in seen: seen.append(p); print('LAYOUT:', p)
    for n in sorted(set(hud.notes)): print('NOTE:', n)
    print('hud check: %s, %d state(s), %d problem(s)%s' % (os.path.basename(xml), len([s for s in states if not s.startswith('_')]),
                                                        len(seen), (' -> %s_*.png' % a.out) if a.out else ''))
    return 1 if seen else 0


if __name__ == '__main__':
    sys.exit(main())
