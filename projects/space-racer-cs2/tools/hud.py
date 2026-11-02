"""Space Racer HUD for CS2 Panorama (custom_hud_layout): layout xml + css + every picture it uses.

usage: hud.py <addon_out_dir> [name] [map]

The retro look: all game text is drawn with the original 8x8 pixel font (tools/pixfont.py). A text slot is a row of
small image panels, one per character; the script sets each panel's glyph class (g65 = 'A') and the row's colour
class (cW white, cY gold, cC cyan, cR red, cG green, cP pink), so only characters that change are sent. Static text
is written straight into the layout the same way. Player names in the standings stay as Labels.
Bars are segmented pixel bars, the minimap is pixelated, and a CRT scanline overlay can be toggled with !crt.

Layout rules (from the first CS2 test, 17 Oct: CS2 put the top panels at the bottom of the screen, stacked the centre
text, squashed the bars and never showed the car cards). The layout is now static, so Panorama lays it out once:
- one Screen panel, a fixed 1080 px high (Panorama scales every screen to 1080 high) and the full width, holds it all;
- every panel has a fixed size and is pinned from the top (margin-top) and from the left edge, the centre or the
  right edge. No vertical centre/bottom alignment, no negative margins, no fit-children containers;
- panels are shown and hidden with opacity, never visibility: collapse, so nothing is laid out again at runtime;
- the script only swaps classes that change pictures, colours, opacity and transforms (the minimap dots move with
  transforms; bar fills change width, which Panorama does redo);
- state classes on spr_root start with "st" and no panel class may share a name with a state class (see below).
preview/hud_render.py lays this out like Panorama would and flags anything that breaks these rules.
"""
import os, sys, re, json
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import pixfont
from retro import *
import retro

OUT = sys.argv[1]
NAME = sys.argv[2] if len(sys.argv) > 2 else 'space_racer'
MAP = sys.argv[3] if len(sys.argv) > 3 else 'mg_' + NAME
IMG = 'file://{images}/custom_game/spr/'
IMGDIR = os.path.join(OUT, 'panorama/images/custom_game/spr')
FONT = 'Stratum2, "Stratum2 Bold", Arial'
os.makedirs(os.path.join(IMGDIR, 'f'), exist_ok=True)
css = []
def rule(sel, **props):
    body = ' '.join('%s: %s;' % (k.replace('_', '-'), v) for k, v in props.items())
    css.append('%s { %s }' % (sel, body))
def raw(text): css.append(text)

def P(id_=None, cls=None, children=None, tag='Panel', extra=''):
    a = []
    if id_: a.append('id="%s"' % id_)
    if cls: a.append('class="%s"' % cls)
    a.append('hittest="false"')
    if extra: a.append(extra)
    if children is None: return '<%s %s />' % (tag, ' '.join(a))
    return '<%s %s>\n%s\n</%s>' % (tag, ' '.join(a), '\n'.join(children), tag)
def save(img, rel):
    Image.fromarray(np.ascontiguousarray(img)).save(os.path.join(IMGDIR, rel))
    return IMG + rel
def px(v): return '%dpx' % int(round(v))

# ---------------------------------------------------------------- the car table (picker stats) from the game's source
defs = open(os.path.join(os.path.dirname(__file__), '..', 'src/core/00_defs.js')).read()
cars = {}
for m in re.finditer(r"(\w+):\s*\{ key: '(\w+)',\s*name: '(\w+)',(.*?)perk: '([^']+)', desc: '([^']+)'", defs, re.S):
    key, name, body, perk, desc = m.group(2), m.group(3), m.group(4), m.group(5), m.group(6)
    kv = dict((k, float(v)) for k, v in re.findall(r"(\w+): ([\d.]+)", body))
    cars[key] = dict(name=name, perk=perk, desc=desc, **kv)
KEYS = ['hornet', 'meteor', 'comet', 'bastion']
assert all(k in cars for k in KEYS), cars.keys()

# ---------------------------------------------------------------- placement
_pl = [0]
def place(x=None, y=0, w=None, h=None, right=None, center=False):
    """a class that pins a panel inside its parent: from the left edge (x), centred, or from the right edge (right);
    always from the top (y); with a fixed size"""
    _pl[0] += 1
    c = 'L%d' % _pl[0]
    props = {}
    if w is not None: props['width'] = px(w)
    if h is not None: props['height'] = px(h)
    if center: props['horizontal_align'] = 'center'
    elif right is not None: props['horizontal_align'] = 'right'; props['margin_right'] = px(right)
    else: props['margin_left'] = px(x or 0)
    props['margin_top'] = px(y)
    rule('.' + c, **props)
    return c

# ---------------------------------------------------------------- glyph images
COLORS = {'W': WHITE, 'Y': GOLD, 'C': ICE, 'R': SALMON, 'G': LIME, 'P': PINK}
CHARSET = ''.join(sorted(c for c in pixfont.GLYPHS if c != '\x7f'))
GS = 6          # glyph pictures are 10 x 10 font pixels, saved 6x (60 x 60)
for ck, col in COLORS.items():
    for ch in CHARSET:
        if ch == ' ': continue
        img = pixfont.render(ch, scale=1, color=col, outline=BLACK)     # 10 x 10 with a 1-px black outline
        # a shade on the lower half of each letter for a bit of depth
        m = pixfont.glyph(ch)
        for y in range(5, 8):
            for x in range(8):
                if m[y, x]: img[y + 1, x + 1, :3] = np.array(shade(col, 0.78), np.uint8)
        save(up(img, GS), 'f/%s_%d.png' % (ck, ord(ch)))
SIZES = {'XXL': 84, 'XL': 52, 'L': 40, 'M': 30, 'S': 22, 'XS': 17}
def adv(size): return SIZES[size] - SIZES[size] // 10
def row_w(n, size): return n * adv(size) + SIZES[size] // 10      # n cells, each overlapping the next by a tenth
TEXT_SLOTS = {}
TEXT_ALIGN = {}

def gtext(id_, n, size, color='W', static=None, extra='', align='center', **pl):
    """a pixel-text row of n glyph panels (ids id_0..id_n-1), pinned with place(**pl); `static` text fixes the
    glyph classes in the layout. Rows always keep all their cells, so they never change size."""
    kids = []
    for k in range(n):
        g = ''
        if static is not None and k < len(static):
            ch = static[k].upper()
            g = ' g%d' % ord(ch if ch in CHARSET else '?')
        kids.append(P('%s_%d' % (id_, k) if id_ and static is None else None, 'G' + g))
    if id_ and static is None: TEXT_SLOTS[id_] = n; TEXT_ALIGN[id_] = align
    cls = 'Txt s%s c%s' % (size, color) + (' ' + extra if extra else '')
    cls += ' ' + place(w=row_w(n, size), h=SIZES[size], **pl)
    return P(id_, cls, kids)

def stext(text, size, color='W', extra='', **pl):
    return gtext(None, len(text), size, color, static=text, extra=extra, **pl)

# glyph css
rule('.Txt', flow_children='right')
rule('.G', background_size='100% 100%', background_repeat='no-repeat')
for s, sz in SIZES.items():
    rule('.s%s .G' % s, width=px(sz), height=px(sz), margin_right='-%dpx' % (sz // 10))
for ck in COLORS:
    for ch in CHARSET:
        if ch != ' ': rule('.c%s .G.g%d' % (ck, ord(ch)), background_image='url("%sf/%s_%d.png")' % (IMG, ck, ord(ch)))
raw("@keyframes 'sprblink' { 0% { opacity: 1; } 55% { opacity: 1; } 56% { opacity: 0; } 100% { opacity: 0; } }")
raw("@keyframes 'sprpulse' { 0% { transform: scale3d(1.0, 1.0, 1); } 50% { transform: scale3d(1.06, 1.06, 1); } 100% { transform: scale3d(1.0, 1.0, 1); } }")
raw("@keyframes 'sprpop' { 0% { transform: scale3d(1.6, 1.6, 1); opacity: 0.2; } 100% { transform: scale3d(1.0, 1.0, 1); opacity: 1; } }")
# the same again under a second name: the script alternates pop / pop2 so every new message replays the pop
raw("@keyframes 'sprpop2' { 0% { transform: scale3d(1.6, 1.6, 1); opacity: 0.2; } 100% { transform: scale3d(1.0, 1.0, 1); opacity: 1; } }")
rule('.Txt.blink', animation_name='sprblink', animation_duration='0.6s', animation_iteration_count='infinite', animation_timing_function='linear')
rule('.Txt.pulse', animation_name='sprpulse', animation_duration='0.5s', animation_iteration_count='infinite')
rule('.Txt.pop', animation_name='sprpop', animation_duration='0.3s')
rule('.Txt.pop2', animation_name='sprpop2', animation_duration='0.3s')

# ---------------------------------------------------------------- pictures: bars, scanlines, frames, logo, minimap dots
def seg_bar(color, segs=20, h=6, w=4):
    """a segmented bar at font-pixel scale: `segs` blocks with 1-px dark gaps and a lighter top row; saved 4x"""
    W_ = segs * (w + 1) + 1
    img = np.zeros((h, W_, 4), np.uint8)
    for k in range(segs):
        x0 = 1 + k * (w + 1)
        img[1:h - 1, x0:x0 + w, :3] = color; img[1:h - 1, x0:x0 + w, 3] = 255
        img[1, x0:x0 + w, :3] = shade(color, 1.35)
        img[h - 2, x0:x0 + w, :3] = shade(color, 0.7)
    return up(img, 4)
BAR_W, BAR_H = 404, 24     # (20 * 5 + 1) * 4 = 404 x 6 * 4
for key, col in (('green', LIME), ('red', RED), ('cyan', ICE), ('gold', GOLD), ('white', WHITE), ('orange', ORANGE), ('pink', PINK), ('dark', INK)):
    save(seg_bar(col), 'bar_%s.png' % key)
# scanlines: every 3rd row dark, alpha
sl = np.zeros((6, 6, 4), np.uint8); sl[0:2, :, 3] = 70
save(sl, 'scan.png')
# a soft vignette in pixel steps
V = 64
yy, xx = np.mgrid[0:V, 0:V]
r = np.hypot((xx + 0.5) / V - 0.5, (yy + 0.5) / V - 0.5) * 2
vg = np.zeros((V, V, 4), np.uint8); vg[..., 3] = (np.clip((r - 0.75) / 0.6, 0, 1) * 160).astype(np.uint8) // 32 * 32
save(up(vg, 4), 'vignette.png')
# boost speed lines: pixel streaks radiating from the centre, only round the edges of the screen (two frames)
def speedlines(seed, cols=(WHITE, ICE, FROST), n=70):
    W_, H_ = 480, 270
    rng = np.random.RandomState(seed)
    img = np.zeros((H_, W_, 4), np.uint8)
    cx, cy = W_ / 2, H_ / 2
    for _ in range(n):
        a = rng.rand() * 2 * np.pi
        r0 = rng.uniform(0.62, 0.85); r1 = r0 + rng.uniform(0.15, 0.45)
        col = cols[rng.randint(len(cols))]
        for k in np.linspace(r0, r1, 120):
            x = int(cx + np.cos(a) * k * W_ * 0.62); y = int(cy + np.sin(a) * k * H_ * 0.62)
            if 0 <= x < W_ and 0 <= y < H_: img[y, x, :3] = col; img[y, x, 3] = 150
    return up(img, 4)
save(speedlines(1), 'speed0.png'); save(speedlines(2), 'speed1.png')
save(speedlines(3, (GOLD, CREAM, ORANGE), 95), 'speedp0.png'); save(speedlines(4, (GOLD, CREAM, ORANGE), 95), 'speedp1.png')

# turn-ahead arrows: one or two chevrons, left or right, centred in a 32 x 16 picture (saved 4x: 128 x 64) so every
# arrow fills the same panel
def turn_arrow(n, right, col):
    G = 16
    img = np.zeros((G, 32, 4), np.uint8)
    x0 = 16 - n * 8
    for k in range(n):
        for y in range(G):
            dx = abs(y - (G - 1) / 2)
            for t in range(4):
                x = int(x0 + k * G + 4 + dx * 0.7 + t)
                if x0 + k * G <= x < x0 + (k + 1) * G:
                    img[y, x, :3] = col; img[y, x, 3] = 255
    # outline
    a_ = img[..., 3] > 0
    o = np.zeros_like(a_)
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)): o |= np.roll(np.roll(a_, dy, 0), dx, 1)
    img[o & ~a_] = (0, 0, 0, 255)
    if right: img = img[:, ::-1]
    return up(img, 4)
for n in (1, 2):
    for right in (0, 1):
        save(turn_arrow(n, right, GOLD if n == 1 else SALMON), 'turn_%s%d.png' % ('r' if right else 'l', n))

# the SPACE RACER logo: chrome-gradient pixel letters with an outline and a deep drop shadow
from theme import TITLE, NEON, DEPTH
LOGO = pixfont.logo(TITLE)
save(LOGO, 'logo.png')
RES = pixfont.logo('RESULTS', 6)
save(RES, 'logo_results.png')

# picker car pictures: pixelated versions of cars.py's renders (they are smooth), quantised to the palette and saved
# at exactly the size the card shows them (64 x 64 pixels, 3x = 192) so they stay crisp
PIC, MPIC = 192, 128
for k in KEYS:
    for side in ('neutral', 't', 'ct'):
        p = os.path.join(IMGDIR, 'car_%s_%s.png' % (k, side))
        if not os.path.exists(p): continue
        im = Image.open(p).convert('RGBA')
        small = np.array(im.resize((64, 64), Image.BILINEAR))
        q = quantize_rgba(small, 14)
        # 1-px black outline round the car
        a = q[..., 3] > 0
        o = np.zeros_like(a)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)): o |= np.roll(np.roll(a, dy, 0), dx, 1)
        edge = o & ~a
        q[edge, :3] = BLACK; q[edge, 3] = 255
        save(up(q, PIC // 64), 'pcar_%s_%s.png' % (k, side))
        save(up(q, MPIC // 64), 'pcars_%s_%s.png' % (k, side))      # the small grid picker's picture

# ---------------------------------------------------------------- base: wrappers, the Screen, full-screen layers
# The script puts state classes on spr_root: stOn (racing / watching), stLobby, stPick (car picker), stHelp, stRes
# (results), stSpec (watching someone), stBoost. They all start with "st" so they can never match a panel's own class:
# in the first CS2 test the root's "Pick" state picked up the picker panel's .Pick rule (a narrow flow-down box
# aligned to the bottom), which is what threw the whole HUD around.
# The HUD is invisible (opacity 0) until the script gives spr_root stOn / stLobby / stPick / stHelp.
rule('.SprWrap', width='100%', height='100%')
rule('.SprOpts', width='100%', height='100%')
rule('.SprRoot', width='100%', height='100%', opacity='0')
for c in ('stOn', 'stLobby', 'stPick', 'stPickMini', 'stHelp', 'stVote'):
    rule('.SprRoot.' + c, opacity='1')
rule('.Screen', width='100%', height='1080px')
rule('.Full', width='100%', height='100%')
rule('.SprRoot Label', font_family=FONT, color='#ffffff', text_shadow='2px 2px 0px #000000', text_transform='uppercase', letter_spacing='2px', font_weight='bold')

def show_when(cls, *states):
    """`cls` panels are hidden unless spr_root has one of the states"""
    rule('.' + cls, opacity='0')
    for s in states: rule('.SprRoot.%s .%s' % (s, cls), opacity='1')
for c in ('MiniMap', 'TopBlock', 'ClockBox', 'Bars', 'Speed', 'Stand'):
    show_when(c, 'stOn')
rule('.SprRoot.stOn.stSpec .Bars', opacity='0.75')
# while the car picker is up the bottom boxes and the standings make way for the cards (after stSpec: this one wins)
for c in ('Bars', 'Speed', 'Stand'):
    rule('.SprRoot.stOn.stPick .' + c, opacity='0')
    rule('.SprRoot.stOn.stPickMini .' + c, opacity='0')
show_when('LobbyLines', 'stLobby')
show_when('Logo', 'stLobby')
show_when('Pick', 'stPick')
show_when('PickMini', 'stPickMini')
show_when('Help', 'stHelp')
show_when('Vote', 'stVote')
show_when('ResLogo', 'stRes')
rule('.SprRoot.stOn.stRes .TopBlock', opacity='0')
show_when('ResBoard', 'stRes')
rule('.SprRoot.stOn.stRes .Stand', opacity='0')       # the results board takes over from the standings
show_when('SpeedFx', 'stBoost')
show_when('SpeedFxPad', 'stPadb')       # a boost pad / turbo start: gold streaks instead of the white ones

# CRT overlay (on unless the player turns it off with !crt)
rule('.Crt', background_image='url("%sscan.png")' % IMG, background_size='6px 6px', background_repeat='repeat', opacity='0.55')
rule('.Vig', background_image='url("%svignette.png")' % IMG, background_size='100% 100%', opacity='0.9')
rule('.SprOpts.nocrt .Crt', opacity='0')
rule('.SprOpts.nocrt .Vig', opacity='0')
for k in (0, 1):
    rule('.Speed%d' % k, background_image='url("%sspeed%d.png")' % (IMG, k), background_size='100% 100%',
         animation_name='sprblink', animation_duration='0.16s', animation_iteration_count='infinite',
         animation_delay='%.2fs' % (k * 0.08))
    rule('.SpeedP%d' % k, background_image='url("%sspeedp%d.png")' % (IMG, k), background_size='100% 100%',
         animation_name='sprblink', animation_duration='0.12s', animation_iteration_count='infinite',
         animation_delay='%.2fs' % (k * 0.06))
# full-screen flash
rule('.Flash', background_color='#00000000', transition_property='background-color', transition_duration='0.08s')
rule('.Flash.hit', background_color='#ff303040')
rule('.Flash.pulse', background_color='#40e0ff38')
rule('.Flash.wreck', background_color='#ff600080')

FRAME = {'cyan': TEAL, 'gold': GOLD, 'pink': MAGENTA, 'white': LILAC, 'orange': ORANGE, 'blue': SKYBLUE}
def hexc(c, a=None): return '#%02x%02x%02x' % tuple(c) + ('%02x' % a if a is not None else '')
BORDER = 4
_framed = set()
def box(cls, key, w, h, **pl):
    """a hard pixel frame (4-px border in a palette colour round a dark see-through box); w x h is the inside,
    children are pinned inside it"""
    if cls not in _framed:
        _framed.add(cls)
        rule('.' + cls, border='%dpx solid %s' % (BORDER, hexc(FRAME[key])), background_color=hexc(INK, 216))
    return cls + ' ' + place(w=w, h=h, **pl)

# ---------------------------------------------------------------- minimap: the pixel track and a dot for every car
MM = 192                     # the track picture (48 x 48 pixels, 4x)
MMCELLS = 48                 # dots snap to the picture's own pixels
MAXDOTS = 32
for tid in [t['id'] for t in json.load(open(os.path.join(OUT, '_gen/tracks.json')))]:
    rule('.MapImg.mm_%s' % tid, background_image='url("%smm_%s.png")' % (IMG, tid))
rule('.MapImg', background_size='100% 100%', background_repeat='no-repeat', overflow='noclip')
# dots are moved with transforms: x on the outer panel, y on the inner square (both start at the map's corner).
# The outer panel is a column as tall as the map, so the square moved down by its y class stays inside it: Panorama
# clips a child to its parent, and with an 8 px tall outer panel every square moved more than a few pixels down was
# cut away (the minimap showed no moving dots in CS2). overflow noclip as well, to be sure.
DOT, DOTL = 8, 12
rule('.Dot', width=px(DOT), height=px(MM), opacity='0', overflow='noclip')
rule('.DotL', width=px(DOTL), height=px(MM), opacity='0', overflow='noclip')
rule('.Dot.On', opacity='1'); rule('.DotL.On', opacity='1')
rule('.DotSq', width=px(DOT - 2), height=px(DOT - 2), border='1px solid #000000', background_color=hexc(LILAC))
rule('.DotSqL', width=px(DOTL - 4), height=px(DOTL - 4), border='2px solid #000000', background_color='#ffffff')
rule('.DotSq.T', background_color=hexc(ORANGE))
rule('.DotSq.CT', background_color=hexc(SKYBLUE))
rule('.DotSq.Out', background_color=hexc(PLUM))
rule('.DotL.me .DotSqL', animation_name='sprblink', animation_duration='0.5s', animation_iteration_count='infinite')
rule('.DotL.Lead .DotSqL', background_color=hexc(GOLD))
for i in range(MMCELLS):
    c = i * (MM // MMCELLS) + MM // MMCELLS / 2          # centre of picture pixel i
    rule('.Dot.x%d' % i, transform='translatex(%dpx)' % int(round(c - DOT / 2)))
    rule('.DotSq.y%d' % i, transform='translatey(%dpx)' % int(round(c - DOT / 2)))
    rule('.DotL.x%d' % i, transform='translatex(%dpx)' % int(round(c - DOTL / 2)))
    rule('.DotSqL.y%d' % i, transform='translatey(%dpx)' % int(round(c - DOTL / 2)))
dots = [P('spr_md%d' % k, 'Dot', [P('spr_mdy%d' % k, 'DotSq')]) for k in range(MAXDOTS)]
dots += [P('spr_ldot', 'DotL Lead', [P('spr_ldoty', 'DotSqL')]), P('spr_dot', 'DotL me', [P('spr_doty', 'DotSqL')])]
# CS2 keeps drawing its own HUD on top of ours, so ours stays out of the places it uses (preview/hud_render.py checks):
# chat bottom-left (x 18-571, y 609-1000 at 1080 high), the kill feed top-right (from y 75 down), the team counter
# top centre (to about y 65) and the money / health row along the bottom edge. So the left column is the minimap with
# the clock under it, the right column the standings with shield / charge and speed below them.
COL_W = MM + 24              # the left column's boxes: the minimap and the clock, the same width
minimap = P('spr_mm', box('MiniMap', 'cyan', COL_W, COL_W, x=24, y=24), [
    P('spr_mmimg', 'MapImg ' + place(x=12, y=12, w=MM, h=MM), dots)])

# ---------------------------------------------------------------- top centre: position, lap, the bend ahead
rule('.Turn', background_size='100% 100%', background_repeat='no-repeat', opacity='0')
for side in ('l', 'r'):
    for n in (1, 2):
        rule('.Turn.%s%d' % (side, n), opacity='1', background_image='url("%sturn_%s%d.png")' % (IMG, side, n))
        if n == 2: rule('.Turn.%s%d' % (side, n), animation_name='sprblink', animation_duration='0.4s', animation_iteration_count='infinite')
POS_W = row_w(2, 'XXL') + 6 + row_w(2, 'L') + 10 + row_w(3, 'M')
TB_W = 620
px0 = (TB_W - POS_W) // 2
# the live team score under the lap: "T 5 - 3 CT" (top-8 places per side, all arenas), T in gold, CT in cyan
TT_W, TC_W = row_w(4, 'S'), row_w(5, 'S')
top = P(None, 'TopBlock ' + place(center=True, y=72, w=TB_W, h=224), [      # under CS2's team counter
    gtext('spr_pos', 2, 'XXL', 'W', align='right', x=px0, y=0),
    gtext('spr_suf', 2, 'L', 'W', align='left', x=px0 + row_w(2, 'XXL') + 6, y=84 - 40 - 10),
    gtext('spr_posof', 3, 'M', 'P', align='left', x=px0 + row_w(2, 'XXL') + 6 + row_w(2, 'L') + 10, y=84 - 30 - 10),
    gtext('spr_lap', 9, 'M', 'Y', center=True, y=90),
    gtext('spr_tt', 4, 'S', 'Y', align='right', x=TB_W // 2 - 18 - TT_W, y=126),
    stext('-', 'S', 'W', center=True, y=126),
    gtext('spr_tct', 5, 'S', 'C', align='left', x=TB_W // 2 + 18, y=126),
    P('spr_turn', 'Turn ' + place(center=True, y=158, w=128, h=64)),
])
clock = P(None, box('ClockBox', 'pink', COL_W, 118, x=24, y=24 + COL_W + 2 * BORDER + 12), [
    stext('TIME', 'XS', 'P', right=10, y=6),
    gtext('spr_clock', 7, 'M', 'W', align='right', right=8, y=26),
    stext('LAP', 'XS', 'P', x=10, y=67),
    gtext('spr_laptime', 7, 'S', 'W', align='right', right=8, y=63),
    stext('BEST', 'XS', 'Y', x=10, y=93),
    gtext('spr_best', 7, 'S', 'Y', align='right', right=8, y=89),
])

# ---------------------------------------------------------------- shield / charge over speed (bottom right)
# (bottom-left is CS2's chat; the speed box ends at y 984, clear of CS2's money / health row along the bottom edge)
rule('.Bar', background_image='url("%sbar_dark.png")' % IMG, background_size='%dpx %dpx' % (BAR_W, BAR_H))
rule('.Fill', height='100%', width='0px', background_size='%dpx %dpx' % (BAR_W, BAR_H), background_repeat='no-repeat', background_position='0px 0px')
for i in range(21): rule('.Fill.w%d' % i, width='%dpx' % (20 * i + 2) if i else '0px')     # whole segments: 20 px each at 4x
def barimg(key): return 'url("%sbar_%s.png")' % (IMG, key)
rule('#spr_shfill', background_image=barimg('green'))
rule('#spr_shield.low #spr_shfill', background_image=barimg('red'))
rule('#spr_shield.low', animation_name='sprblink', animation_duration='0.8s', animation_iteration_count='infinite')
rule('#spr_chfill', background_image=barimg('cyan'))
rule('#spr_charge.boosting #spr_chfill', background_image=barimg('gold'))
rule('#spr_charge.charging #spr_chfill', background_image=barimg('pink'))
rule('#spr_spfill', background_image=barimg('white'))
# the E ability: its name and a bar that refills over the cooldown (gold and blinking when ready, red when short of charge)
rule('#spr_abfill', background_image=barimg('white'))
rule('#spr_abil.ready #spr_abfill', background_image=barimg('gold'))
rule('#spr_abil.low #spr_abfill', background_image=barimg('red'))
rule('.Speed.pad #spr_spfill', background_image=barimg('orange'))
rule('.Speed.pad', border='%dpx solid %s' % (BORDER, hexc(ORANGE)))
BOX_Y = 852
BARS_H = 182
bars = P(None, box('Bars', 'cyan', 432, BARS_H, right=24, y=BOX_Y - (BARS_H + 2 * BORDER) - 12), [
    stext('SHIELD', 'S', 'G', x=14, y=8),
    P('spr_shield', 'Bar ' + place(x=14, y=34, w=BAR_W, h=BAR_H), [P('spr_shfill', 'Fill')]),
    stext('CHARGE', 'S', 'C', x=14, y=66),
    P('spr_charge', 'Bar ' + place(x=14, y=92, w=BAR_W, h=BAR_H), [P('spr_chfill', 'Fill')]),
    gtext('spr_abtxt', 14, 'S', 'W', align='left', x=14, y=124),
    P('spr_abil', 'Bar ' + place(x=14, y=150, w=BAR_W, h=BAR_H), [P('spr_abfill', 'Fill')]),
])
speed = P('spr_speed', box('Speed', 'gold', 432, 124, right=24, y=BOX_Y), [
    gtext('spr_spd', 4, 'XL', 'W', align='right', right=14 + row_w(4, 'S') + 6, y=8),
    stext('KM/H', 'S', 'Y', right=14, y=8 + 52 - 22 - 2),
    P(None, 'Bar ' + place(right=14, y=92, w=BAR_W, h=BAR_H), [P('spr_spfill', 'Fill')]),
])

# ---------------------------------------------------------------- standings (right): rows with a side-coloured tab; names are Labels
rule('.StRow', background_color='#14102480')
rule('.StTab', background_color='#5a4670')
rule('.StRow.T .StTab', background_color='#dc781e')
rule('.StRow.CT .StTab', background_color='#3c78dc')
rule('.StRow.me', background_color='#ffffff38')
rule('.StRow.me .StTab', background_color='#ffffff')
rule('.StName', font_size='19px', color='#ffffff')
rule('.StRow.me .StName', color='#ffbe28')
stand = P(None, box('Stand', 'white', 340, 296, right=24, y=330), [
    P('spr_st%d' % i, 'StRow ' + place(x=10, y=6 + i * 36, w=320, h=32), [
        P(None, 'StTab ' + place(x=0, y=0, w=8, h=32)),
        P('spr_stn%d' % i, 'StName ' + place(x=16, y=4, w=300, h=26), tag='Label', extra='text="{s:v}"'),
    ]) for i in range(8)])

# ---------------------------------------------------------------- results board (centre, after the race): place, name, time
RB_ROWS, RB_H = 8, 40
rule('.RbRow', background_color='#14102480')
rule('.RbTab', background_color='#5a4670')
rule('.RbRow.T .RbTab', background_color='#dc781e')
rule('.RbRow.CT .RbTab', background_color='#3c78dc')
rule('.RbRow.me', background_color='#ffffff38')
rule('.RbRow.me .RbTab', background_color='#ffffff')
rule('.RbPos', font_size='24px', color='#c8b4d2')
rule('.RbRow.p1 .RbPos', color='#ffbe28')
rule('.RbRow.p2 .RbPos', color='#e6e6f0')
rule('.RbRow.p3 .RbPos', color='#dc8c50')
rule('.RbName', font_size='24px', color='#ffffff')
rule('.RbRow.me .RbName', color='#ffbe28')
rule('.RbTime', font_size='24px', color='#a0f0ff', text_align='right')
resboard = P(None, box('ResBoard', 'gold', 760, RB_ROWS * RB_H + 16, center=True, y=272), [
    P('spr_rb%d' % i, 'RbRow ' + place(x=10, y=8 + i * RB_H, w=740, h=RB_H - 4), [
        P(None, 'RbTab ' + place(x=0, y=0, w=8, h=RB_H - 4)),
        P('spr_rbp%d' % i, 'RbPos ' + place(x=20, y=3, w=90, h=30), tag='Label', extra='text="{s:v}"'),
        P('spr_rbn%d' % i, 'RbName ' + place(x=116, y=3, w=380, h=30), tag='Label', extra='text="{s:v}"'),
        P('spr_rbt%d' % i, 'RbTime ' + place(right=14, y=3, w=210, h=30), tag='Label', extra='text="{s:v}"'),
    ]) for i in range(RB_ROWS)])

# ---------------------------------------------------------------- the car picker: four cards with the car, its perk and stats
CARD_W, CARD_H, CARD_GAP = 292, 412, 12
rule('.Card.sel', transform='scale3d(1.06, 1.06, 1)', border='%dpx solid %s' % (BORDER, hexc(FRAME['gold'])), background_color='#2a1f3ae0')
rule('.Card.sel .CarPic', animation_name='sprpulse', animation_duration='0.9s', animation_iteration_count='infinite')
rule('.CarPic', background_size='100% 100%', background_repeat='no-repeat')
for k in KEYS:
    for side in ('neutral', 't', 'ct'):
        rule('.CarPic.pic_%s_%s' % (k, side), background_image='url("%spcar_%s_%s.png")' % (IMG, k, side))
rule('.StatBar', background_image='url("%sbar_dark.png")' % IMG, background_size='%dpx 12px' % (BAR_W // 3 + 1))
rule('.StatFill', height='100%', background_image=barimg('gold'), background_size='%dpx 12px' % (BAR_W // 3 + 1), background_repeat='no-repeat')
def stat(lo, hi, v): return int(100 * (v - lo) / (hi - lo))
for k in KEYS:
    c = cars[k]
    c['s_speed'] = stat(950, 1150, c['maxSpeed'] * c['boost'] / 1.3)
    c['s_accel'] = stat(420, 690, c['accel'])
    c['s_turn'] = stat(1.9, 2.9, c['turn'])
    c['s_shield'] = stat(70, 140, c['shield'])
    c['s_charge'] = stat(90, 150, c['charge'])
STATS = ('speed', 'accel', 'turn', 'shield', 'charge')
for k in KEYS:
    for nm in STATS:
        v = max(10, min(100, cars[k]['s_' + nm]))
        rule('.StatFill.%s_%s' % (k, nm), width='%dpx' % int(round(v / 5) * 5 * 1.3))
cards = []
for i, k in enumerate(KEYS):
    c = cars[k]
    kids = [P('spr_cimg%d' % i, 'CarPic pic_%s_neutral ' % k + place(center=True, y=6, w=PIC, h=PIC)),
            stext(c['name'], 'L', 'W', center=True, y=PIC + 12),
            stext(c['perk'], 'XS', 'C', center=True, y=PIC + 58)]
    for j, nm in enumerate(STATS):
        y = PIC + 84 + j * 26
        kids.append(stext(nm.upper(), 'XS', 'C', x=16, y=y))
        kids.append(P(None, 'StatBar ' + place(x=128, y=y + 3, w=130, h=12), [P(None, 'StatFill %s_%s' % (k, nm))]))
    cards.append(P('spr_card%d' % i, box('Card', 'white', CARD_W, CARD_H, x=i * (CARD_W + 2 * BORDER + CARD_GAP), y=46), kids))
PICK_W = 4 * (CARD_W + 2 * BORDER) + 3 * CARD_GAP
# (high enough that the last half-dozen chat lines, bottom-left, show under the cards)
pick = P('spr_pick', 'Pick ' + place(center=True, y=326, w=PICK_W, h=46 + CARD_H + 2 * BORDER + 20),
         [stext('A / D CHOOSE   E TO CONFIRM', 'M', 'Y', extra='blink', center=True, y=0)] + cards)

# the small picker on the grid: four little cards along the bottom right (where shield / charge and speed come up
# once the lights start) so the flyover's view of the field stays clear and CS2's chat (bottom-left) stays readable
MC_W, MC_H, MC_GAP = 200, 172, 10
rule('.MCard.sel', transform='scale3d(1.06, 1.06, 1)', border='%dpx solid %s' % (BORDER, hexc(FRAME['gold'])), background_color='#2a1f3ae0')
rule('.MCard.sel .MCarPic', animation_name='sprpulse', animation_duration='0.9s', animation_iteration_count='infinite')
rule('.MCarPic', background_size='100% 100%', background_repeat='no-repeat')
for k in KEYS:
    for side in ('neutral', 't', 'ct'):
        rule('.MCarPic.pic_%s_%s' % (k, side), background_image='url("%spcars_%s_%s.png")' % (IMG, k, side))
mcards = []
for i, k in enumerate(KEYS):
    c = cars[k]
    mcards.append(P('spr_mcard%d' % i, box('MCard', 'white', MC_W, MC_H, x=i * (MC_W + 2 * BORDER + MC_GAP), y=28), [
        P('spr_mimg%d' % i, 'MCarPic pic_%s_neutral ' % k + place(center=True, y=0, w=MPIC, h=MPIC)),
        stext(c['name'], 'S', 'W', center=True, y=MPIC),
        stext(c['perk'], 'XS', 'C', center=True, y=MPIC + 24),
    ]))
MPICK_W = 4 * (MC_W + 2 * BORDER) + 3 * MC_GAP
pickmini = P('spr_mpick', 'PickMini ' + place(right=24, y=1080 - 96 - (28 + MC_H + 2 * BORDER), w=MPICK_W, h=28 + MC_H + 2 * BORDER),
             [stext('A / D CHOOSE   E TO CONFIRM', 'S', 'Y', extra='blink', center=True, y=0)] + mcards)

# ---------------------------------------------------------------- lobby: the logo and three pixel lines; results banner; help
logo = P(None, 'Logo ' + place(center=True, y=70, w=LOGO.shape[1], h=LOGO.shape[0]))
rule('.Logo', background_image='url("%slogo.png")' % IMG, background_size='100% 100%', background_repeat='no-repeat',
     animation_name='sprpulse', animation_duration='2.4s', animation_iteration_count='infinite')
res = P(None, 'ResLogo ' + place(center=True, y=160, w=RES.shape[1], h=RES.shape[0]))
rule('.ResLogo', background_image='url("%slogo_results.png")' % IMG, background_size='100% 100%',
     animation_name='sprpulse', animation_duration='1.2s', animation_iteration_count='infinite')
lobby = P(None, 'LobbyLines ' + place(center=True, y=212, w=row_w(60, 'S'), h=3 * 34), [
    gtext('spr_lob1', 60, 'S', 'W', center=True, y=0),
    gtext('spr_lob2', 60, 'S', 'Y', center=True, y=34),
    gtext('spr_lob3', 60, 'S', 'C', center=True, y=68)])
HELP = [(TITLE + ' - HOW TO DRIVE', 'Y'), ('W / S    GAS / BRAKE', 'W'), ('A / D    STEER', 'W'), ('MOUSE 1  BOOST (USES CHARGE)', 'W'),
        ('MOUSE 2  SPIN ATTACK', 'W'), ('SPACE    DRIFT (FILLS CHARGE)', 'W'), ('E        YOUR CAR\'S ABILITY', 'W'), ('R        PICK A CAR', 'W'),
        ('', 'W'), ('GOLD PADS: FREE SPEED', 'Y'), ('CYAN PADS: CHARGE + SHIELD', 'C'),
        ('RAMPS: HIT THEM FAST!', 'R') if not NEON else (('GLIDES' if DEPTH else 'FLYING') + ': W DOWN  S UP  RINGS!', 'R'),
        ('BANKED BENDS GRIP HARDER', 'G') if not DEPTH else ('WATCH FOR SEA CREATURES!', 'G'), ('', 'W'), ('!CAR 1-4  !CAM  !CRT  !TILT', 'P'), ('!SHADE !VOTE !SPEC !AFK !BACK', 'P')]
help_ = P('spr_help', box('Help', 'cyan', 640, len(HELP) * 28 + 24, center=True, y=180),
          [stext(t or ' ', 'S', c, x=20, y=14 + i * 28) for i, (t, c) in enumerate(HELP)])

# ---------------------------------------------------------------- the track vote (left, under the clock; after a race)
# The top 3 of a finished race vote the next track with W / S (or !vote 1-4): four tracks with the votes each has,
# the voter's pick in gold. Everyone watching that race sees the box too. It sits between the clock box (ends y 386)
# and CS2's chat (from y 600), and left of the results board even on a 4:3 screen (board from x 336 there).
VOTE_W, VOTE_ROWS = 300, 4
vote = P('spr_vote', box('Vote', 'gold', VOTE_W, 180, x=24, y=400), [
    stext('TRACK VOTE', 'S', 'Y', center=True, y=8),
    *[gtext('spr_vn%d' % i, 16, 'XS', 'W', align='left', x=8, y=42 + i * 26) for i in range(VOTE_ROWS)],
    *[gtext('spr_vc%d' % i, 1, 'XS', 'C', align='right', right=8, y=42 + i * 26) for i in range(VOTE_ROWS)],
    gtext('spr_vf', 18, 'XS', 'Y', center=True, y=42 + VOTE_ROWS * 26 + 8),
])

# ---------------------------------------------------------------- centre messages and the bottom message line
centre = [
    gtext('spr_ctr', 20, 'XL', 'W', center=True, y=310),
    gtext('spr_ctr2', 40, 'M', 'W', center=True, y=322),
    gtext('spr_sub', 52, 'S', 'W', center=True, y=392),
    # 38 cells (762 px) at most, so even the longest line stays right of CS2's chat (x 571) on a 16:9 screen
    gtext('spr_msg', 38, 'S', 'C', center=True, y=822),
]

# never shown: these make CS2 compile the loading screen slides, the radar and the map icon along with the HUD.
# CS2 shows no slide at all when a map has only one, so tools/loading.py draws LOADING_SLIDES of them
# (<map>.png, <map>_1.png ...) and checks that each one is in this list.
LOADING_SLIDES = 4
PRELOAD = [('SprPre2', 'overheadmaps/%s_radar.psd' % MAP), ('SprPre3', 'map_icons/map_icon_%s.svg' % MAP)]
PRELOAD += [('SprPre%d' % (1 if n == 0 else 3 + n), 'map_icons/screenshots/1080p/%s%s.png' % (MAP, '_%d' % n if n else ''))
            for n in range(LOADING_SLIDES)]
PRELOAD.sort()
for cls, src in PRELOAD:
    rule('.' + cls, width='1px', height='1px', opacity='0', visibility='collapse', background_image='url("file://{images}/%s")' % src)
rule('.SprPreload', width='1px', height='1px', visibility='collapse')

# ---------------------------------------------------------------- xml
screen = P(None, 'Screen', [
    P(None, 'SprPreload', [P(None, cls) for cls, _ in PRELOAD]),
    P('spr_flash', 'Flash Full'),
    P(None, 'SpeedFx Full', [P(None, 'Speed0 Full'), P(None, 'Speed1 Full')]),
    P(None, 'SpeedFxPad Full', [P(None, 'SpeedP0 Full'), P(None, 'SpeedP1 Full')]),
    logo, res, minimap, top, clock,
    *centre,
    bars, speed, stand, resboard, vote, lobby, pick, pickmini, help_,
    P(None, 'Vig Full'),
    P(None, 'Crt Full'),
])
root = P('spr_root', 'SprRoot', [screen])
doc = ('<root>\n\t<styles>\n\t\t<include src="file://{resources}/styles/custom_game/%s.css" />\n\t</styles>\n'
       '\t<Panel class="SprWrap" hittest="false">\n' % NAME + P('spr_opts', 'SprOpts', [root]) + '\n\t</Panel>\n</root>\n')
os.makedirs(os.path.join(OUT, 'panorama/layout/custom_game'), exist_ok=True)
os.makedirs(os.path.join(OUT, 'panorama/styles/custom_game'), exist_ok=True)
open(os.path.join(OUT, 'panorama/layout/custom_game/%s.xml' % NAME), 'w', newline='\n').write(doc)
open(os.path.join(OUT, 'panorama/styles/custom_game/%s.css' % NAME), 'w', newline='\n').write('\n'.join(css) + '\n')
ids = re.findall(r'id="([^"]+)"', doc)
assert len(ids) == len(set(ids)), 'duplicate panel ids'
# classes the script switches on and off must never have a rule of their own (a lone ".Name { }"): the panel getting
# the class would pick up that rule's layout (the first CS2 test's bug)
DYNAMIC = re.compile(r'^(st[A-Z]\w*|On|sel|low|ready|boosting|charging|pad|me|T|CT|N|Out|Lead|blink|pulse|pop2?|hit|wreck|nocrt|[lr][12]|p[123]|[xyw]\d+|mm_\w+|pic_\w+|g\d+|c[WYCRGP])$')
lone = [m.group(1) for m in (re.match(r'^\.([\w-]+) \{', c) for c in css) if m]
bad = sorted(set(c for c in lone if DYNAMIC.match(c)))
assert not bad, 'switched classes with rules of their own: %s' % bad
json.dump(sorted(set(ids)), open(os.path.join(OUT, '_gen/hud_ids.json'), 'w'))
json.dump(dict(slots=TEXT_SLOTS, align=TEXT_ALIGN, charset=CHARSET, colors=sorted(COLORS), mm_cells=MMCELLS, max_dots=MAXDOTS),
          open(os.path.join(OUT, '_gen/hud_text.json'), 'w'))
# the layout, for the preview: every pinned class's box
json.dump(dict(pl=_pl[0]), open(os.path.join(OUT, '_gen/hud_layout.json'), 'w'))
print('hud: %d css rules, %d panel ids, %d text rows, %d glyph pictures' % (len(css), len(set(ids)), len(TEXT_SLOTS), len(COLORS) * (len(CHARSET) - 1)))
