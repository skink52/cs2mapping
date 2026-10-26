r"""panorama.py: helpers for generating a CS2 custom HUD (custom_hud_layout): the layout xml, its css and the
pixel-text glyph pictures, written the way that has held up in CS2 (static layout, everything a fixed size and pinned
from the top; the script only switches classes). Check the result with hud_check.py.

What is here:
  Hud.rule(sel, **props) / raw(text)      css rules (props use _ for -, e.g. margin_top='10px')
  P(id, cls, children, tag, extra)         a panel (always hittest="false"); Label: tag='Label', extra='text="{s:v}"'
  Hud.place(x=, y=, w=, h=, right=, center=)   one class that pins a box (from the left / right edge or centred, from the top)
  Hud.show_when(cls, root_cls, *states)    `cls` is hidden (opacity 0) unless the root panel has one of the states
  Hud.glyph_font(...) + gtext() / stext()  pixel-text rows: one image panel per character; the script sets each cell's
                                           glyph class (g65 = 'A') and the row's colour class (cW, cY...)
  Hud.char_line(prefix, n, cls)            a fixed row of n character panels <prefix>0..n-1 plus a <prefix>img slot for a
                                           whole-string picture (Hellmatch style)
  Hud.preload(map_name, slides)            never-shown panels that make CS2 compile the loading slides, radar and icon
  Hud.hide_with_scoreboard(cls)            hide `cls` panels while CS2's scoreboard / end-of-match screen is up
  Hud.write(addon_out, name, body, dynamic=regex)   writes panorama/layout/custom_game/<name>.xml + styles .css and
                                           asserts: no duplicate ids, and no class the script switches has a lone rule
                                           (".sel { }" alone would give every panel that gets the class that rule's layout)

Worked example (a score line and a centre message; python3 -c "import panorama; panorama.example('out/addon')"):

    import panorama
    from panorama import P
    h = panorama.Hud(img_url='file://{images}/custom_game/mygame/', img_dir='out/addon/panorama/images/custom_game/mygame')
    h.rule('.MyWrap', width='100%', height='100%')
    h.rule('.MyRoot', width='100%', height='100%', opacity='0')       # invisible until the script sets a state
    h.rule('.MyRoot.stOn', opacity='1')
    h.rule('.Screen', width='100%', height='1080px')
    h.glyph_font(colors={'W': (255, 255, 255), 'Y': (255, 190, 40)})  # writes f/<colour>_<code>.png with pixfont
    body = P('my_root', 'MyRoot', [P(None, 'Screen', [
        h.stext('SCORE', 'S', 'Y', x=24, y=300),
        h.gtext('my_score', 4, 'M', 'W', align='right', x=24, y=330),
        h.gtext('my_msg', 30, 'S', 'W', center=True, y=760),
        h.preload('mg_mygame', slides=2)])])
    h.write('out/addon', 'mygame', body, dynamic=r'^(st[A-Z]\w*|g\d+|c[WY])$')
    # script side: hud.SetHasClass('my_root', 'stOn', true); per cell hud.SetHasClass('my_score_0', 'g' + code, true)...

Rules of thumb (from the CS2 tests of Space Racer and Hellmatch): one Screen panel 1080 px high holds everything;
no vertical centre/bottom alignment, no negative margins (except inside flow-right glyph rows), no fit-children;
show / hide with opacity (class-toggled visibility: collapse also works); state classes start with "st" so they
never share a name with a panel class; keep the top panel without an id (wrap it).

From space-racer-cs2/tools/hud.py and hellmatch-cs2/tools/hud.py (MIT), made project-neutral.
"""
import os, re, json

FONT = 'Stratum2, "Stratum2 Bold", Arial'     # CS2's HUD font for Labels
SIZES = {'XXL': 84, 'XL': 52, 'L': 40, 'M': 30, 'S': 22, 'XS': 17}   # pixel-text sizes (cell height, px)


def px(v):
    return '%dpx' % int(round(v))


def P(id_=None, cls=None, children=None, tag='Panel', extra=''):
    """one panel as xml text; children = list of xml strings (None = an empty element)"""
    a = []
    if id_: a.append('id="%s"' % id_)
    if cls: a.append('class="%s"' % cls)
    a.append('hittest="false"')
    if extra: a.append(extra)
    if children is None: return '<%s %s />' % (tag, ' '.join(a))
    return '<%s %s>\n%s\n</%s>' % (tag, ' '.join(a), '\n'.join(c for c in children if c), tag)


class Hud:
    def __init__(self, img_url='file://{images}/custom_game/hud/', img_dir=None, place_prefix='L', sizes=None):
        self.css = []
        self.img_url, self.img_dir = img_url, img_dir
        self.place_prefix = place_prefix
        self._pl = 0
        self.sizes = dict(sizes or SIZES)
        self.text_slots, self.text_align = {}, {}
        self.charset = ''

    # ------------------------------------------------ css
    def rule(self, sel, **props):
        body = ' '.join('%s: %s;' % (k.replace('_', '-'), v) for k, v in props.items())
        self.css.append('%s { %s }' % (sel, body))

    def raw(self, text):
        self.css.append(text)

    def place(self, x=None, y=0, w=None, h=None, right=None, center=False):
        """a new class (L1, L2...) that pins a panel inside its parent: from the left edge (x), centred, or from the
        right edge (right); always from the top (y); with a fixed size"""
        self._pl += 1
        c = '%s%d' % (self.place_prefix, self._pl)
        props = {}
        if w is not None: props['width'] = px(w)
        if h is not None: props['height'] = px(h)
        if center: props['horizontal_align'] = 'center'
        elif right is not None: props['horizontal_align'] = 'right'; props['margin_right'] = px(right)
        else: props['margin_left'] = px(x or 0)
        props['margin_top'] = px(y)
        self.rule('.' + c, **props)
        return c

    def show_when(self, cls, root_cls, *states):
        """`cls` panels are hidden unless the root panel (class root_cls) has one of the states"""
        self.rule('.' + cls, opacity='0')
        for s in states: self.rule('.%s.%s .%s' % (root_cls, s, cls), opacity='1')

    def hide_with_scoreboard(self, cls, only_with=None):
        """CS2 puts HUD_SCOREBOARD_VISIBLE / HUD_ENDOFMATCH_VISIBLE on an ancestor of the custom HUD while those are up.
        only_with: an extra class the panel must have too (a per-player opt-in, e.g. 'hidescores')"""
        sel = '.' + cls + ('.' + only_with if only_with else '')
        for anc in ('HUD_SCOREBOARD_VISIBLE', 'HUD_ENDOFMATCH_VISIBLE'):
            self.rule('.%s %s' % (anc, sel), visibility='collapse')

    # ------------------------------------------------ pixel text: one image panel per character
    def glyph_font(self, colors, charset=None, scale=6, write=True, shade_lower=0.78):
        """glyph pictures (pixfont, 10x10 font px incl. a 1-px black outline, saved `scale`x) and their css.
        colors: {key: (r, g, b)} -> row classes c<key>. Classes: .Txt (row), .G (cell), .s<size>, .g<code>."""
        import numpy as np
        import pixfont
        from PIL import Image
        self.charset = charset or ''.join(sorted(c for c in pixfont.GLYPHS if c != '\x7f'))
        if write:
            os.makedirs(os.path.join(self.img_dir, 'f'), exist_ok=True)
            for ck, col in colors.items():
                for ch in self.charset:
                    if ch == ' ': continue
                    img = pixfont.render(ch, scale=1, color=col, outline=(0, 0, 0))
                    m = pixfont.glyph(ch)
                    for y in range(5, 8):          # a darker lower half for a bit of depth
                        for x in range(8):
                            if m[y, x]: img[y + 1, x + 1, :3] = [int(c * shade_lower) for c in col]
                    Image.fromarray(np.repeat(np.repeat(img, scale, 0), scale, 1)).save(
                        os.path.join(self.img_dir, 'f', '%s_%d.png' % (ck, ord(ch))))
        self.rule('.Txt', flow_children='right')
        self.rule('.G', background_size='100% 100%', background_repeat='no-repeat')
        for s, sz in self.sizes.items():          # cells overlap by a tenth (the outline), only safe in flow-right rows
            self.rule('.s%s .G' % s, width=px(sz), height=px(sz), margin_right='-%dpx' % (sz // 10))
        for ck in colors:
            for ch in self.charset:
                if ch != ' ':
                    self.rule('.c%s .G.g%d' % (ck, ord(ch)), background_image='url("%sf/%s_%d.png")' % (self.img_url, ck, ord(ch)))

    def adv(self, size):
        return self.sizes[size] - self.sizes[size] // 10

    def row_w(self, n, size):
        """width of a row of n cells"""
        return n * self.adv(size) + self.sizes[size] // 10

    def gtext(self, id_, n, size, color='W', static=None, extra='', align='center', **pl):
        """a pixel-text row of n glyph panels (ids id_0..id_n-1) pinned with place(**pl); `static` text fixes the
        glyph classes in the layout. Rows keep all their cells, so they never change size."""
        kids = []
        for k in range(n):
            g = ''
            if static is not None and k < len(static) and static[k] != ' ':
                ch = static[k].upper()
                g = ' g%d' % ord(ch if ch in self.charset else '?')
            kids.append(P('%s_%d' % (id_, k) if id_ and static is None else None, 'G' + g))
        if id_ and static is None: self.text_slots[id_] = n; self.text_align[id_] = align
        cls = 'Txt s%s c%s' % (size, color) + (' ' + extra if extra else '')
        cls += ' ' + self.place(w=self.row_w(n, size), h=self.sizes[size], **pl)
        return P(id_, cls, kids)

    def stext(self, text, size, color='W', extra='', **pl):
        """fixed text written into the layout"""
        return self.gtext(None, len(text), size, color, static=text, extra=extra, **pl)

    def char_line(self, prefix, n, cls):
        """Hellmatch-style text line: <prefix>img (a whole-string picture, class TImg t<n>) then n character panels
        <prefix>0..n-1 (class Ch c<code>) in a flow-right row with class `cls` (add its own .Line/.Ch/.TImg rules)"""
        return P(None, 'Line ' + cls, [P(prefix + 'img', 'TImg')] + [P(prefix + str(i), 'Ch') for i in range(n)])

    # ------------------------------------------------ loading screen / radar / icon
    def preload(self, map_name, slides=2, radar=True, icon=True, prefix='HudPre'):
        """never-shown 1-px panels whose background images make CS2 compile the loading-screen slides
        (map_icons/screenshots/1080p/<map>.png, <map>_1.png ...), the radar (overheadmaps/<map>_radar.psd) and the
        map icon (map_icons/map_icon_<map>.svg) along with the HUD. Returns the panel xml; loading.py writes the files."""
        srcs = ['map_icons/screenshots/1080p/%s%s.png' % (map_name, '_%d' % n if n else '') for n in range(slides)]
        if radar: srcs.append('overheadmaps/%s_radar.psd' % map_name)
        if icon: srcs.append('map_icons/map_icon_%s.svg' % map_name)
        kids = []
        for i, src in enumerate(srcs):
            c = '%s%d' % (prefix, i + 1)
            self.rule('.' + c, width='1px', height='1px', opacity='0', visibility='collapse',
                      background_image='url("file://{images}/%s")' % src)
            kids.append(P(None, c))
        self.rule('.%sload' % prefix, width='1px', height='1px', visibility='collapse')
        return P(None, '%sload' % prefix, kids)

    # ------------------------------------------------ output
    def document(self, name, body, wrap_cls='HudWrap'):
        """the layout xml: the stylesheet include and a plain full-screen wrapper (the top panel may not have an id)"""
        if not any(re.match(r'^\.%s \{' % wrap_cls, c) for c in self.css):
            self.rule('.' + wrap_cls, width='100%', height='100%')
        return ('<root>\n\t<styles>\n\t\t<include src="file://{resources}/styles/custom_game/%s.css" />\n\t</styles>\n'
                '\t<Panel class="%s" hittest="false">\n%s\n\t</Panel>\n</root>\n' % (name, wrap_cls, body))

    def write(self, addon_out, name, body, dynamic=None, wrap_cls='HudWrap', gen_dir=None):
        """writes the xml + css, checks them (see check()), and if gen_dir is given writes hud_ids.json (every panel
        id, for a mock engine) and hud_text.json (text rows: slots, align, charset). Returns (xml_path, css_path)."""
        doc = self.document(name, body, wrap_cls)
        check(doc, self.css, dynamic)
        lay = os.path.join(addon_out, 'panorama/layout/custom_game'); sty = os.path.join(addon_out, 'panorama/styles/custom_game')
        os.makedirs(lay, exist_ok=True); os.makedirs(sty, exist_ok=True)
        xp, cp = os.path.join(lay, name + '.xml'), os.path.join(sty, name + '.css')
        open(xp, 'w', newline='\n', encoding='utf-8').write(doc)
        open(cp, 'w', newline='\n', encoding='utf-8').write('\n'.join(self.css) + '\n')
        if gen_dir:
            os.makedirs(gen_dir, exist_ok=True)
            json.dump(sorted(set(re.findall(r'id="([^"]+)"', doc))), open(os.path.join(gen_dir, 'hud_ids.json'), 'w'))
            json.dump(dict(slots=self.text_slots, align=self.text_align, charset=self.charset),
                      open(os.path.join(gen_dir, 'hud_text.json'), 'w'))
        print('hud %s: %d css rules, %d panel ids' % (name, len(self.css), len(re.findall(r'id="', doc))))
        return xp, cp


def check(doc, css, dynamic=None):
    """asserts: no duplicate panel ids; no class matching `dynamic` (regex of classes the script switches) has a lone
    rule of its own ('.sel { ... }'). In the first Space Racer CS2 test the root's state class picked up a panel
    class's lone rule (a box aligned to the bottom), which threw the whole HUD around."""
    ids = re.findall(r'id="([^"]+)"', doc)
    dup = sorted(set(i for i in ids if ids.count(i) > 1))
    assert not dup, 'duplicate panel ids: %s' % dup
    if dynamic:
        rx = re.compile(dynamic) if isinstance(dynamic, str) else dynamic
        lone = [m.group(1) for m in (re.match(r'^\.([\w-]+) \{', c) for c in css) if m]
        bad = sorted(set(c for c in lone if rx.match(c)))
        assert not bad, 'switched classes with rules of their own: %s' % bad


def example(addon_out):
    """the worked example from the docstring, written into addon_out"""
    img_dir = os.path.join(addon_out, 'panorama/images/custom_game/mygame')
    h = Hud(img_url='file://{images}/custom_game/mygame/', img_dir=img_dir)
    h.rule('.MyRoot', width='100%', height='100%', opacity='0')
    h.rule('.MyRoot.stOn', opacity='1')
    h.rule('.Screen', width='100%', height='1080px')
    h.rule('.MyRoot Label', font_family=FONT, color='#ffffff')
    h.glyph_font(colors={'W': (255, 255, 255), 'Y': (255, 190, 40)})
    h.rule('.Box', background_color='#14102480', border='4px solid #20c8aa')
    h.show_when('Box', 'MyRoot', 'stOn')
    h.hide_with_scoreboard('Box', 'hidescores')
    body = P('my_root', 'MyRoot', [P(None, 'Screen', [
        P(None, 'Box ' + h.place(x=24, y=300, w=200, h=90), [
            h.stext('SCORE', 'S', 'Y', x=10, y=8),
            h.gtext('my_score', 4, 'M', 'W', align='right', right=10, y=44)]),
        P('my_name', 'Name ' + h.place(x=24, y=400, w=200, h=26), tag='Label', extra='text="{s:name}"'),
        h.gtext('my_msg', 30, 'S', 'W', center=True, y=760),
        h.preload('mg_mygame', slides=2)])])
    return h.write(addon_out, 'mygame', body, dynamic=r'^(st[A-Z]\w*|g\d+|c[WY]|hidescores)$',
                   gen_dir=os.path.join(addon_out, '_gen'))


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2: sys.exit('usage: panorama.py <addon_out>   (writes the worked example HUD there)')
    print(*example(sys.argv[1]))
