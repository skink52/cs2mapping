"""IRONFRAME HUD for CS2 Panorama (custom_hud_layout): the layout xml, its css, the pictures and the baked hud.json.

usage: python -I tools/hud.py <addon out> [<name> [<map>]]     (defaults: names.NAME / names.MAP)

Writes  <out>/panorama/layout/custom_game/<name>.xml + styles/custom_game/<name>.css
        <out>/panorama/images/custom_game/ifr/*  (tools/hud_images.py)
        <out>/_gen/hud.json         the contract the driver (src/cs2/50_hud.js) is baked with (docs/INTERFACES.md section 5)
        build/hud_states.json       every screen state for create/hud_check.py (the gate renders and checks them)

The look: a modern mech cockpit. Thin lines, dark translucent plates, pixel-art text only (pixfont glyph pictures, 2-tone, one class
per character), one accent colour per team state (stTeamT amber, stTeamCT ice), warnings in amber and red. Every named
colour is a css class (cText, cDim, cOk, cWarn, cDanger, cAcc...).
Panorama rules that held up in CS2 (docs/creation/hud.md): one 1080-high screen panel, every panel a fixed size pinned
from the top and the left / centre / right, opacity for show and hide, transforms (never margins) for movement, no id on
the top panel, every class the script switches starts with "st" and has no rule of its own, hittest off.
Class budget (per player): see docs/HUD.md "Budget".
"""
import os, sys, re, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..', '..', 'create')))
import panorama
from panorama import P, px
import hud_images

if len(sys.argv) < 2: sys.exit(__doc__)
OUT = sys.argv[1]
if len(sys.argv) > 2: NAME = sys.argv[2]
else:
    import names; NAME = names.NAME
if len(sys.argv) > 3: MAP = sys.argv[3]
else:
    import names; MAP = names.MAP
PROJ = os.path.normpath(os.path.join(HERE, '..'))
PARTS = json.load(open(os.path.join(PROJ, 'data', 'parts.json'), encoding='utf-8'))
IMG_DIR = os.path.join(OUT, 'panorama', 'images', 'custom_game', 'ifr')
URL = 'file://{images}/custom_game/ifr/'
FONT = panorama.FONT

# ---------------------------------------------------------------- palette (every colour a class)
PAL = {
    'Text': '#f2f6fa', 'Dim': '#b4c4d2', 'Ok': '#5ee08a', 'Warn': '#ffc247', 'Danger': '#ff5a46',
    'Acc': '#9fd8f0', 'Cy': '#38d8ff', 'Mg': '#ff3fd8', 'T': '#ffb04a', 'CT': '#5fd3ff', 'Ally': '#5fd3ff', 'Enemy': '#ff5a46', 'Gold': '#ffd25a',
}
PLATE = '#0a0f14b8'          # dark translucent plate
PLATE2 = '#121a22d0'
LINE = '#3d5a73'             # plate border (solid: pixel art has no soft edges)
TRACK = '#1a242e'            # empty bar

import pixfont as _pf
h = panorama.Hud(img_url=URL, img_dir=IMG_DIR, place_prefix='L', sizes={'XXL': 80, 'XL': 50, 'L': 40, 'M': 30, 'S': 20, 'XS': 20, 'XXS': 10})   # pixel-text cells: 10 font px x 2..8
rule, raw = h.rule, h.raw
PANELS = {}          # id -> {classes: set, vars: set, prio: n}   (prio 0 warnings, 1 lock, 2 gauges, 3 text)
LADDERS = {}         # name -> {panel, steps}
TEXT = {}            # var name -> {panel, max}


# CS2 keeps at most 1024 panel ids per custom_hud_layout: every id the script names in SetHasClass* / SetDialogVariable* takes a place in a table
# that never frees, and past 1024 "The maximum number of panel ids has been reached, no more can be referenced" (server.dll) is logged and the
# panel is never updated again (10 Nov 2026: bars empty, weapons blank, lock marker gone; the per-character glyph cells had 5 000 ids).
# Every id the script can reference is registered here, so the generator knows the total: it prints the table and fails over ID_BUDGET.
ID_BUDGET, ID_CAP = 800, 1024
SCREEN = ['root']            # the screen being built (the id budget table)
def screen(name): SCREEN[0] = name


def reg(id_, classes=(), var=None, prio=2, maxlen=0):
    e = PANELS.setdefault(id_, {'classes': set(), 'vars': set(), 'prio': prio, 'screen': SCREEN[0]})
    e['classes'].update(classes)
    e['prio'] = min(e['prio'], prio)
    if var:
        e['vars'].add('v')
        TEXT[var] = {'panel': id_, 'max': maxlen}


def url(name): return 'url("%s%s")' % (URL, name)


def box(cls, w, hh, border=1, bg=PLATE, line=LINE, **pl):
    """a plate: fixed outer size (the border is part of it)"""
    c = h.place(w=w - 2 * border, h=hh - 2 * border, **pl)
    return '%s %s' % (cls, c)


import hud_font as F
TEXTROW = {}         # text slot panel -> (row panel id, align letter, cells, size, box width)
TRUNC = []           # text slots whose maxlen does not fit their box at the smallest size (the driver cuts by pixel width)
DEF_N = {'XXL': 6, 'XL': 12, 'L': 16, 'M': 24, 'S': 32, 'XS': 40}
GLYPH_COLORS = {}    # master cap -> {colour keys used at sizes that use that master}
TINTS = []
SPU = 2              # spacer step in px (right / centre aligned text is pushed by one spacer class)


# short names for the narrow weapon boxes (fight HUD 112 px, equipped weapons); everything else shows its full name
SHORT = {'AR-22 Rifle': 'AR-22', 'GT-9 Gatling': 'GT-9', 'SG-Scatter': 'SG-SCAT', 'BZ-Hammer': 'BZ-HAMR', 'PB-Moonlight': 'PB-MOON', 'SH-Bulwark': 'SH-BULW',
         'SMG-Hornet': 'SMG-HRN', 'PB-Piercer': 'PB-PIER', 'SC-Longbow': 'SC-LONG', 'EG-Arc Scatter': 'EG-ARC', 'PB-Eclipse': 'PB-ECLP', 'VM-6 Vertical': 'VM-6',
         'DM-2 Dual': 'DM-2', 'GC-Thunder': 'GC-THND', 'VM-12 Storm': 'VM-12', 'ML-Caltrop': 'ML-CALT', 'MM-8 Swarm': 'MM-8'}
for _p in PARTS['parts']:
    if _p['kind'] in ('arm', 'shoulder'):
        _n = SHORT.get(_p['name'], _p['name']).upper()
        assert F.LMETRICS['XS'].text_w(_n) <= 126, 'weapon name too wide for its box: %s (%d px)' % (_n, F.METRICS['XS'].text_w(_n))


def need(color, size): GLYPH_COLORS.setdefault(F.master_for(size), set()).add(color)


def fit_size(size, n, w, metrics=None):
    """largest size <= `size` where min(n, max(10, 60 % of n)) average characters fit the box; else XS (the driver cuts by pixel width)"""
    metrics = metrics or F.METRICS
    nd = min(n, max(10, -(-n * 6 // 10)))
    for sz in F.SIZE_ORDER[F.SIZE_ORDER.index(size):]:
        if w / metrics[sz].avg() >= nd: return sz
    return 'XS'


def row_cls(size, color, extra=''):
    return ('Txt s%s c%s%s %s' % (size, color, {'c28': '', 'b28': ' Bt', 'b56': ' Big'}[F.master_for(size)], extra)).strip()


NEGY = set()


def row_pl(w, hh, M, x=0):
    """placement of a glyph row so the capitals sit centred in a box of height hh; a row taller than its box is lifted with a translatey class
    (a negative margin outside a flow row is not allowed). Returns (place css classes, extra classes)"""
    y = int(round((hh - M.cap) / 2 - (M.base - M.cap)))
    if y >= 0: return h.place(w=w, h=M.h, x=x, y=y), ''
    NEGY.add(-y)
    return h.place(w=w, h=M.h, x=x, y=0), 'Ny%d' % -y


LCOLORS = set()       # colours Labels use (a css class each)


def lbl(var, cls, w, hh, size='S', color='Text', align='left', prio=3, maxlen=0, id_=None, box=None, **pl):
    """dynamic text: ONE id, a real <Label text="{s:v}"> the driver fills with SetDialogVariableStringForPlayer (a text change = 1 engine call).
    It was a row of glyph picture panels, one id per character: 5 000 ids, five times CS2's cap of 1024 per layout (see reg()).
    A box panel WITHOUT an id (`cls` and the placement) holds the Label; the Label is one line box tall (the font's ascent + descent) and sits so
    its capitals are centred in the box, lifted with a translatey class when that is above the box's top. `box`: an id for the box panel, only
    where the script switches classes on it (the kill pop, the XP ticker). maxlen: the longest text expected (it picks the size)."""
    pid = id_ or ('ifr_' + var)
    n0 = maxlen or DEF_N[size]
    gs = fit_size(size, n0, w, F.LMETRICS)
    M = F.LMETRICS[gs]
    cap_chars = int(w / M.avg())
    if cap_chars < n0: TRUNC.append((var, n0, cap_chars, gs))
    reg(pid, prio=prio)
    PANELS[pid]['vars'].add('v')
    TEXT[var] = {'panel': pid, 'max': 160, 'align': align[0].upper(), 'size': gs, 'w': w}
    TEXTROW[pid] = (pid, align[0].upper(), 160, gs, w)
    LCOLORS.add(color)
    hh = max(hh, M.cap + 4)
    y = int(round((hh - M.cap) / 2 - M.top))
    ny = ''
    if y < 0: NEGY.add(-y); ny = ' Ny%d' % -y; y = 0
    lab = P(pid, 'Tx s%s c%s Al%s %s%s' % (gs, color, align[0].upper(), h.place(w=w, h=M.h, x=0, y=y), ny), None, tag='Label', extra='text="{s:v}"')
    return P(box, ('Dy %s %s' % (cls, h.place(w=w, h=hh, **pl))).replace('  ', ' ').strip(), [lab])


LTINTS = []


def tint(sel, color, dyn=False):
    """recolour the text under `sel` (a state-dependent colour rule): Labels by a colour rule; unless `dyn`, static glyph rows too (their pictures)"""
    LTINTS.append((sel, color))
    if not dyn: GLYPH_COLORS.setdefault('c28', set()).add(color); GLYPH_COLORS.setdefault('b28', set()).add(color); TINTS.append((sel + ' .Txt', color))


def slbl(text, cls, w, hh, size='S', color='Text', align='left', id_=None, **pl):
    """static text as neon type: a row of glyph pictures (proportional widths) inside a box that keeps the id and classes"""
    t = text.upper()
    gs = size if size in F.SIZES else 'XS'
    while F.METRICS[gs].text_w(t) > w * 1.1 and gs != 'XS': gs = F.SIZE_ORDER[F.SIZE_ORDER.index(gs) + 1]
    M = F.METRICS[gs]; rw = M.text_w(t)
    need(color, gs)
    if rw > w:                                                                                    # modest overflow: the box grows, anchored by its alignment
        grow = rw - w
        if 'right' not in pl and not pl.get('center'):
            pl = dict(pl); pl['x'] = (pl.get('x') or 0) - (grow if align == 'right' else grow // 2 if align == 'center' else 0)
        w = rw
    hh = max(hh, M.cap + 4)
    ox = 0 if align == 'left' else (w - rw) if align == 'right' else (w - rw) // 2
    kids = [P(None, 'G g%d' % ord(ch if 33 <= ord(ch) < 127 and not 97 <= ord(ch) <= 122 else '?') if ch != ' ' else 'G g32') for ch in t]
    rp, ny = row_pl(rw, hh, M, ox)
    row = P(None, row_cls(gs, color, '%s %s' % (rp, ny)), kids)
    return P(id_, ('Sl %s %s' % (cls, h.place(w=w, h=hh, **pl))).replace('  ', ' ').strip(), [row])


def spacer_units(text_px, w, align):
    """the spacer class index (SPU px steps) that aligns text of width text_px in a box of width w"""
    off = (w - text_px) if align == 'R' else (w - text_px) // 2 if align == 'C' else 0
    return max(0, int(off // SPU))


def cut_text(text, M, w, n):
    """what the driver shows: upper case, cut at n cells and at the box width"""
    out, used = '', 0
    for ch in text.upper()[:n]:
        a = M.adv.get(ord(ch), M.adv[87])
        if used + a > w: break
        out += ch; used += a
    return out.rstrip(), used


# the team accent: root state classes recolour .Acc labels and .AccLine borders
rule('.IfrRoot.stTeamT .AccFill', background_color=PAL['T']); rule('.IfrRoot.stTeamCT .AccFill', background_color=PAL['CT'])
rule('.Plate', background_color=PLATE, border='2px solid ' + LINE)
rule('.Plate2', background_color=PLATE2, border='2px solid ' + LINE)
rule('.Img', background_size='100% 100%', background_repeat='no-repeat')

# ---------------------------------------------------------------- root, screen, groups
rule('.IfrRoot', width='100%', height='100%', opacity='0')
rule('.IfrRoot.stOn', opacity='1')
h.hide_with_scoreboard('IfrRoot')
rule('.Screen', width='100%', height='1080px', overflow='noclip noclip')
ROOT_STATES = ['stOn', 'stFight', 'stSpec', 'stDeath', 'stIntro', 'stPodium', 'stGarage', 'stTeamT', 'stTeamCT']
reg('ifr_root', ROOT_STATES, prio=0)
GROUPS = {'Fight': ('stFight', 'stSpec'), 'Common': ('stFight', 'stSpec', 'stDeath'), 'Intro': ('stIntro',), 'Podium': ('stPodium',),
          'Death': ('stDeath',), 'SpecBar': ('stSpec',), 'Garage': ('stGarage',)}
for g, states in GROUPS.items(): h.show_when(g, 'IfrRoot', *states)
rule('.Fight', transition_property='opacity', transition_duration='0.15s')

# animations (names quoted; a replay needs a new name: pop / pop2 alternate)
raw("@keyframes 'ifrpop' { 0% { transform: scale3d(1.25, 1.25, 1); } 100% { transform: scale3d(1, 1, 1); } }")
raw("@keyframes 'ifrpop2' { 0% { transform: scale3d(1.25, 1.25, 1); } 100% { transform: scale3d(1, 1, 1); } }")
raw("@keyframes 'ifrblink' { 0% { opacity: 1; } 49% { opacity: 1; } 50% { opacity: 0.15; } 100% { opacity: 0.15; } }")
raw("@keyframes 'ifrflash' { 0% { opacity: 1; } 50% { opacity: 0.35; } 100% { opacity: 1; } }")
raw("@keyframes 'ifrhit' { 0% { opacity: 1; transform: scale3d(1.35, 1.35, 1); } 60% { opacity: 1; transform: scale3d(1, 1, 1); } 100% { opacity: 0; transform: scale3d(1, 1, 1); } }")
raw("@keyframes 'ifrhit2' { 0% { opacity: 1; transform: scale3d(1.35, 1.35, 1); } 60% { opacity: 1; transform: scale3d(1, 1, 1); } 100% { opacity: 0; transform: scale3d(1, 1, 1); } }")
raw("@keyframes 'ifrfade' { 0% { opacity: 1; } 70% { opacity: 1; } 100% { opacity: 0; } }")
POP = dict(animation_name='ifrpop', animation_duration='0.25s', animation_timing_function='ease-out')
POP2 = dict(POP, animation_name='ifrpop2')
BLINK = dict(animation_name='ifrblink', animation_duration='0.5s', animation_iteration_count='infinite', animation_timing_function='linear')
FLASH = dict(animation_name='ifrflash', animation_duration='0.3s', animation_iteration_count='infinite')


# ---------------------------------------------------------------- ladders (gauges)
_LADDER_CSS = set()
SEG_DIMS = set()


def ladder(name, fill_cls, track_cls, w, hh, steps=20, color=None, colors=None, pid=None, **pl):
    """a track panel with a fill child whose width is set by stL0..stL<steps> on the fill (registered as ladder `name`).
    color: one fill colour (or 'AccFill' for the team accent); colors: [(upto_step, colour)] steps for AP-style bars."""
    pid = pid or 'ifr_l_' + name
    reg(pid, ['stL%d' % k for k in range(steps + 1)], prio=2)
    LADDERS[name] = {'panel': pid, 'steps': steps}
    if track_cls not in _LADDER_CSS:
        _LADDER_CSS.add(track_cls)
        rule('.' + track_cls, background_color=TRACK)
        rule('.' + fill_cls, width='0px', height=px(hh), **({'background_color': color} if color and color != 'AccFill' else {}))
    for k in range(steps + 1):
        if (fill_cls, k) in _LADDER_CSS: continue
        _LADDER_CSS.add((fill_cls, k))
        props = {'width': px(w * k / steps)}
        if colors:
            for upto, col in colors:
                if k <= upto: props['background_color'] = col; break
        rule('.%s.stL%d' % (fill_cls, k), **props)
    extra = ' AccFill' if color == 'AccFill' else ''
    sw = max(3, int(round(w / steps))); SEG_DIMS.add((sw, hh))
    seg = P(None, 'Seg%dx%d ' % (sw, hh) + h.place(w=w, h=hh, x=0, y=0))
    return P(None, '%s %s' % (track_cls, h.place(w=w, h=hh, **pl)), [P(pid, fill_cls + extra), seg])


screen('fight')
# ================================================================ FIGHT: vitals + weapons (bottom centre)
# 10 Nov 2026 evening playtest: the weapon boxes grew a state row (lock-type launchers say NO LOCK: UNGUIDED / LOCKING 60 % / LOCKED: FIRE /
# OUT OF RANGE, multi-lock HOLD TO LOCK / 3 LOCKED: RELEASE), and the overdrive gauge its own block with a line that says what to press.
# 10 Nov 2026 recording: vitals and weapon boxes met in the middle, right over the pilot's own mech. MECH_GAP px are left clear between
# them and the gap sits on the screen centre (the mech is ~280 px wide at 1080 high from the follow camera).
MECH_GAP = 290
VW, VH, VY = 896 + MECH_GAP - 40, 172, 812            # ends at 984, above CS2's money / health row (y >= 1000)
vit = []
# AP
vit.append(slbl('AP', '', 40, 22, 'XS', 'Dim', x=0, y=2))
vit.append(lbl('ap', '', 150, 24, 'M', 'Text', 'left', x=46, y=0, maxlen=6))
vit.append(lbl('apmax', '', 120, 22, 'XS', 'Dim', 'right', x=240, y=2, maxlen=8))
vit.append(ladder('ap', 'ApFill', 'ApBar', 360, 12, 20, colors=[(5, PAL['Danger']), (10, PAL['Warn']), (20, PAL['Ok'])], x=0, y=26))
# EN (red when stalled, amber when the generator is over-drawn)
vit.append(slbl('EN', '', 40, 22, 'XS', 'Dim', x=0, y=44))
vit.append(lbl('en', '', 150, 22, 'S', 'Text', 'left', x=46, y=43, maxlen=6))
rule('.EnBar.stStall', background_color='#3a1410')
rule('.EnBar.stStall .EnFill', background_color=PAL['Danger'])
rule('.EnBar.stOver .EnFill', background_color=PAL['Warn'])
en_bar = ladder('en', 'EnFill', 'EnBar', 360, 8, 20, color='AccFill', x=0, y=68)
vit.append(en_bar.replace('<Panel class="EnBar', '<Panel id="ifr_enbar" class="EnBar', 1))
reg('ifr_enbar', ['stStall', 'stOver'], prio=0)
rule('.EnStallTag', opacity='0'); rule('.EnStallTag.stOn', opacity='1', **BLINK)
reg('ifr_entag', ['stOn'], prio=0)
vit.append(slbl('STALL', 'EnStallTag', 96, 18, 'XS', 'Danger', 'right', id_='ifr_entag', x=264, y=44))
# stagger meter (the wrapper carries stStaggered: the fill flashes red and the tag blinks)
rule('.Stg', width='360px', height='30px')
rule('.StgTag', opacity='0')
rule('.Stg.stStaggered .StgTag', opacity='1', **BLINK)
rule('.Stg.stStaggered .StgFill', background_color=PAL['Danger'], **FLASH)
reg('ifr_stg', ['stStaggered'], prio=0)
vit.append(P('ifr_stg', 'Stg ' + h.place(w=360, h=30, x=0, y=84), [
    slbl('STAGGER', '', 130, 18, 'XS', 'Dim', x=0, y=0),
    slbl('STAGGERED', 'StgTag', 120, 18, 'XS', 'Danger', 'right', right=0, y=0),
    ladder('stg', 'StgFill', 'StgBar', 360, 6, 20, colors=[(13, PAL['Warn']), (20, PAL['Danger'])], x=0, y=20)]))
# quick-boost cooldown ticks and landing lag
qb_ticks = []
for i in range(4):
    rule('.QbT%d' % i, background_color=PAL['Dim'], opacity='0.25')
    qb_ticks.append(P(None, 'QbT%d %s' % (i, h.place(w=22, h=5, x=i * 26, y=0))))
for k in range(1, 5):
    for i in range(k): rule('.Qb.stL%d .QbT%d' % (k, i), opacity='1', background_color=PAL['Acc'])
reg('ifr_qb', ['stL%d' % k for k in range(5)], prio=2)
LADDERS['qb'] = {'panel': 'ifr_qb', 'steps': 4}
vit.append(P('ifr_qb', 'Qb ' + h.place(w=104, h=6, x=0, y=124), qb_ticks))
rule('.Qb', width='104px', height='6px')
vit.append(slbl('QB', '', 38, 20, 'XS', 'Dim', x=108, y=110))
vit.append(slbl('LANDING', 'Lag', 80, 18, 'XS', 'Warn', id_='ifr_lag', x=150, y=111))
rule('.Lag', opacity='0'); rule('.Lag.stOn', opacity='1')
reg('ifr_lag', ['stOn'], prio=0)
vit.append(slbl('BOOST', 'BoostTag', 96, 18, 'XS', 'Acc', 'right', id_='ifr_boost', x=264, y=109))
rule('.BoostTag', opacity='0'); rule('.BoostTag.stOn', opacity='1'); rule('.BoostTag.stAssault', opacity='1'); tint('.BoostTag.stAssault', 'Warn')
reg('ifr_boost', ['stOn', 'stAssault'], prio=2)

# weapon boxes: 0 RA (Mouse1), 1 LA (Mouse2), 2 RS (R), 3 LS (E); left column = left side, top row = shoulders
WEAPONS = ['ra', 'la', 'rs', 'ls']
WKEYS = {'ra': 'M1', 'la': 'M2', 'rs': 'R', 'ls': 'E'}
WBW, WBH = 244, 80
WX0 = 360 + MECH_GAP                 # the vitals end at x 360
WPOS = {'ls': (WX0, 0), 'rs': (WX0 + 250, 0), 'la': (WX0, 86), 'ra': (WX0 + 250, 86)}
FAMS = hud_images.FAMILIES
# the weapon's state row (ifrHudWeapons): one of stLkNo (no lock: it fires unguided), stLkAcq (locking), stLkOn (locked: fire), stLkOut (out of range)
WLK = ['stLkNo', 'stLkAcq', 'stLkOn', 'stLkOut']
rule('.WBox', background_color=PLATE, border='2px solid ' + LINE, transition_property='background-color', transition_duration='0.1s')
rule('.WBox.stSel', border='2px solid #9fd8f0')
rule('.IfrRoot.stTeamT .WBox.stSel', border='2px solid ' + PAL['T']); rule('.IfrRoot.stTeamCT .WBox.stSel', border='2px solid ' + PAL['CT'])
rule('.WBox.stPop', **POP); rule('.WBox.stPop2', **POP2)
rule('.WBox.stEmpty', background_color='#2a1210c0'); rule('.WBox.stHot', background_color='#2a1210c0')
rule('.WIcon', background_size='100% 100%', background_repeat='no-repeat', opacity='0.9')
for f in FAMS: rule('.WIcon.stW%s' % f, background_image=url('w/%s.png' % f))
rule('.WBox.stEmpty .WIcon', opacity='0.35'); rule('.WBox.stReload .WIcon', opacity='0.5')
rule('.WTag', opacity='0')
rule('.WBox.stReload .WTagR', opacity='1', **BLINK); rule('.WBox.stEmpty .WTagE', opacity='1'); rule('.WBox.stHot .WTagH', opacity='1', **BLINK)
tint('.WBox.stReload .WAmmo', 'Warn'); tint('.WBox.stEmpty .WAmmo', 'Danger'); tint('.WBox.stHot .WAmmo', 'Danger')
rule('.WBox.stCharge .WMagFill', background_color=PAL['Warn'])
rule('.WBox.stNo', opacity='0.3')                      # empty hard-point
rule('.WBox.stReload .WName', opacity='0'); rule('.WBox.stEmpty .WName', opacity='0'); rule('.WBox.stHot .WName', opacity='0')
tint('.WBox.stLkNo .WState', 'Warn'); tint('.WBox.stLkAcq .WState', 'Cy'); tint('.WBox.stLkOn .WState', 'Ok'); tint('.WBox.stLkOut .WState', 'Danger')
rule('.WBox.stLkOn', border='2px solid ' + PAL['Ok']); rule('.WBox.stLkAcq', border='2px solid ' + PAL['Cy'])
wboxes = []
for i, key in enumerate(WEAPONS):
    x, y = WPOS[key]
    pid = 'ifr_w%d' % i
    reg(pid, ['stSel', 'stPop', 'stPop2', 'stReload', 'stEmpty', 'stHot', 'stCharge', 'stNo'] + WLK, prio=1)
    reg(pid + 'i', ['stW%s' % f for f in FAMS], prio=2)
    kids = [
        P(pid + 'i', 'WIcon ' + h.place(w=36, h=36, x=10, y=3)),
        slbl(WKEYS[key], '', 56, 18, 'XS', 'Acc', 'center', x=0, y=38),
        lbl('w%dn' % i, 'WName', 174, 16, 'XS', 'Dim', 'left', x=60, y=2, maxlen=14),
        lbl('w%da' % i, 'WAmmo', 174, 26, 'M', 'Text', 'left', prio=2, x=60, y=16, maxlen=9),
        ladder('w%dm' % i, 'WMagFill', 'WMagBar', 172, 5, 20, color='AccFill', x=60, y=45),
        ladder('w%dc' % i, 'WCdFill', 'WCdBar', 172, 3, 20, color=PAL['Dim'], x=60, y=52),
        slbl('RELOADING', 'WTag WTagR', 90, 16, 'XS', 'Warn', 'right', x=WBW - 100, y=2),
        slbl('EMPTY', 'WTag WTagE', 70, 16, 'XS', 'Danger', 'right', x=WBW - 80, y=2),
        slbl('OVERHEAT', 'WTag WTagH', 90, 16, 'XS', 'Danger', 'right', x=WBW - 100, y=2),
        lbl('w%ds' % i, 'WState', WBW - 12, 18, 'XS', 'Dim', 'left', prio=1, x=6, y=57, maxlen=20),
    ]
    wboxes.append(P(pid, 'WBox ' + h.place(w=WBW - 4, h=WBH - 4, x=x, y=y), kids))
# Overdrive: its own block under the QB row. A gold gauge, the percentage, and one line that always says what to do: how it fills,
# READY: HOLD R+E TOGETHER (the block pulses gold), CHARGING: BLAST IN 0.8 S (cyan). 10 Nov 2026 evening playtest: "no indication what overdrive does".
raw("@keyframes 'ifrpulse' { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }")
PULSE = dict(animation_name='ifrpulse', animation_duration='1.1s', animation_iteration_count='infinite', animation_timing_function='ease-in-out')
_odw = F.METRICS['XS'].text_w('OVERDRIVE')
od_bar = ladder('od', 'OdFill', 'OdBar', 284 - _odw - 14, 8, 20, color=PAL['Gold'], x=6 + _odw + 10, y=7)
rule('.OdBar.stCharge .OdFill', background_color=PAL['Cy'])
reg('ifr_odbar', ['stCharge'], prio=2)
rule('.OdGlow', background_color='#ffd25a26', border='2px solid ' + PAL['Gold'], opacity='0')
rule('.OdBox.stOn .OdGlow', opacity='1', **PULSE)
rule('.OdBox.stCharge .OdGlow', opacity='1', background_color='#38d8ff26', border='2px solid ' + PAL['Cy'])
tint('.OdBox.stOn', 'Gold', True); tint('.OdBox.stCharge', 'Cy', True)
reg('ifr_odready', ['stOn', 'stCharge'], prio=1)
vit.append(P('ifr_odready', 'OdBox ' + h.place(w=360, h=40, x=0, y=132), [
    P(None, 'OdGlow ' + h.place(w=356, h=36, x=0, y=0)),
    slbl('OVERDRIVE', '', _odw + 2, 18, 'XS', 'Gold', x=6, y=1),
    od_bar.replace('<Panel class="OdBar', '<Panel id="ifr_odbar" class="OdBar', 1),
    lbl('odp', '', 66, 18, 'XS', 'Gold', 'right', prio=2, x=288, y=1, maxlen=5),
    lbl('odl', '', 348, 18, 'XS', 'Dim', 'left', prio=1, x=6, y=20, maxlen=34)]))
# buff badges: what you earned, what it does, how long it lasts (a column at the right edge; the radar moved top left, Nov 2026)
BUFFS = [('dmg', 'DAMAGE +25 %', 'Danger'), ('shield', 'SHIELD -40 % DMG', 'Cy'), ('ace', 'ACE +20 % SPEED', 'Gold'), ('radar', 'RADAR PING', 'Ok'), ('arty', 'ARTILLERY', 'Mg')]
BFW = 296
rule('.BfB', background_color=PLATE2, opacity='0'); rule('.BfB.stOn', opacity='1')
bf = []
for i, (k, name, col) in enumerate(BUFFS):
    rule('.BfB.Bf%s' % k, border='2px solid ' + PAL[col])
    reg('ifr_bf_' + k, ['stOn'], prio=2)
    bf.append(P('ifr_bf_' + k, 'BfB Bf%s %s' % (k, h.place(w=BFW - 4, h=40, x=0, y=i * 46)), [
        slbl(name, '', BFW - 16, 18, 'XS', col, 'left', x=6, y=1),
        lbl('bf' + k, '', BFW - 16, 18, 'XS', 'Text', 'left', x=6, y=19, maxlen=26)]))
buffs = P(None, 'Fight ' + h.place(w=BFW, h=5 * 46, right=24, y=470), bf)
# the gap's middle (inner x 360 + MECH_GAP / 2) on the screen centre: the cluster then starts ~100 px under CS2's chat box (x < 576) on
# a 16:9 screen, only while the chat is open (it started right of it before, with the mech under the HUD instead)
VIT_SHIFT = int(round((VW + 20) / 2 - 18 - (360 + MECH_GAP / 2)))
rule('.VitPos', transform='translatex(%dpx)' % VIT_SHIFT)
vitals = P(None, 'Fight VitPos ' + h.place(w=VW + 20, h=VH, center=True, y=VY), [P(None, 'VIn ' + h.place(w=VW, h=VH, x=18, y=0), vit + wboxes)])

# ================================================================ FIGHT: reticle (centre), threats, missile warning
RB, RY = 480, 300           # reticle box (centre at 540)
C = RB / 2
ret = []
# the FCS cone: a thin broken ring 128 px at the widest FCS (10 Nov 2026 playtest: the old 300 px ring scaled up to 400 px was far too large)
rule('.Cone', background_image=url('cone.png'), background_size='100% 100%', background_repeat='no-repeat', opacity='0.45',
     transform_origin='50% 50%', transition_property='transform', transition_duration='0.2s')
for k, s in enumerate((0.7, 0.8, 0.9, 1.0, 1.1)): rule('.Cone.stC%d' % k, transform='scale3d(%.2f, %.2f, 1)' % (s, s))
reg('ifr_cone', ['stC%d' % k for k in range(5)], prio=2)
ret.append(P('ifr_cone', 'Cone ' + h.place(w=128, h=128, x=C - 64, y=C - 64)))
rule('.Shield', background_image=url('shield.png'), background_size='100% 100%', background_repeat='no-repeat', opacity='0')
rule('.Shield.stOn', opacity='0.7')
reg('ifr_shield', ['stOn'], prio=0)
ret.append(P('ifr_shield', 'Shield ' + h.place(w=200, h=200, x=C - 100, y=C - 100)))
rule('.StgRing', background_image=url('stagger.png'), background_size='100% 100%', background_repeat='no-repeat', opacity='0')
rule('.StgRing.stOn', opacity='1', **FLASH)
reg('ifr_stgring', ['stOn'], prio=0)
ret.append(P('ifr_stgring', 'StgRing ' + h.place(w=120, h=120, x=C - 60, y=C - 60)))
rule('.Xhair', background_image=url('xhair.png'), background_size='100% 100%', background_repeat='no-repeat')
rule('.Xhair.stAssist', opacity='1')
ret.append(P(None, 'Xhair ' + h.place(w=48, h=48, x=C - 24, y=C - 24)))
# hit markers: four ticks around the centre, replayed by the stPop / stPop2 parity trick (ifrHudHit): light, heavy (stagger or impact >= 500), kill (x)
HITA = dict(animation_duration='0.3s', animation_timing_function='ease-out', animation_fill_mode='forwards')
rule('.Hit', opacity='0', transform_origin='50% 50%')
rule('.Hit.stPop', opacity='1', animation_name='ifrhit', **HITA); rule('.Hit.stPop2', opacity='1', animation_name='ifrhit2', **HITA)
rule('.HitK .HitR', transform='rotateZ(45deg)')
rule('.HitB', background_color='#ffffffee'); rule('.HitH .HitB', background_color='#ffa028ff'); rule('.HitK .HitB', background_color='#ff3030ff')
for hid, cls, size, th, gap in (('ifr_hit', 'HitL', 56, 3, 8), ('ifr_hitH', 'HitH', 72, 5, 10), ('ifr_hitK', 'HitK', 88, 6, 12)):
    reg(hid, ['stPop', 'stPop2'], prio=0)
    L = size / 2 - gap - 12
    ret.append(P(hid, 'Hit %s ' % cls + h.place(w=size, h=size, x=C - size / 2, y=C - size / 2), [P(None, 'HitR ' + h.place(w=size, h=size, x=0, y=0), [
        P(None, 'HitB ' + h.place(w=12, h=th, x=0, y=size / 2 - th / 2)), P(None, 'HitB ' + h.place(w=12, h=th, x=size - 12, y=size / 2 - th / 2)),
        P(None, 'HitB ' + h.place(w=th, h=12, x=size / 2 - th / 2, y=0)), P(None, 'HitB ' + h.place(w=th, h=12, x=size / 2 - th / 2, y=size - 12))])]))
# the lock bracket: it sits ON the locked mech (10 Nov 2026 evening playtest: "i don't know how to target them"): two wrapper panels carry one
# translate class each (stX<k> / stY<k>, 20 px steps from the screen centre, eased 0.1 s), which the driver sets from the target's place on the
# screen (50_hud.js ifrHudProject). States: stAcq (a target is in the ring: thin amber corners, ACQUIRING), stSoft (white: guns track it),
# stHard1..2 (closing in), stHard3 (red, flashing: LOCKED, missiles track). Name above, the lock progress under it, state word + range + target AP below.
LKS, LKXN, LKYN = 20, 58, 26            # step px, steps each side of the centre (x: +-1160 covers 21:9, y: +-520)
rule('.LkRoot', overflow='noclip noclip'); rule('.LkX', overflow='noclip noclip', transition_property='transform', transition_duration='0.1s', transition_timing_function='linear')
rule('.LkY', overflow='noclip noclip', transition_property='transform', transition_duration='0.1s', transition_timing_function='linear')
for k in range(2 * LKXN + 1): rule('.LkX.stX%d' % k, transform='translatex(%dpx)' % ((k - LKXN) * LKS))
for k in range(2 * LKYN + 1): rule('.LkY.stY%d' % k, transform='translatey(%dpx)' % ((k - LKYN) * LKS))
LKX_CLS = ['stX%d' % k for k in range(2 * LKXN + 1)]; LKY_CLS = ['stY%d' % k for k in range(2 * LKYN + 1)]
rule('.Lock', opacity='0'); rule('.Lock.stAcq', opacity='1'); rule('.Lock.stSoft', opacity='1'); rule('.Lock.stHard1', opacity='1'); rule('.Lock.stHard2', opacity='1'); rule('.Lock.stHard3', opacity='1')
rule('.LockBox', background_image=url('lockbox.png'), background_size='100% 100%', background_repeat='no-repeat', transition_property='transform', transition_duration='0.12s')
rule('.Lock.stAcq .LockBox', background_image=url('lockbox_acq.png'), transform='scale3d(1.12, 1.12, 1)')
rule('.Lock.stHard1 .LockBox', background_image=url('lockbox_hard.png'), transform='scale3d(0.92, 0.92, 1)')
rule('.Lock.stHard2 .LockBox', background_image=url('lockbox_hard.png'), transform='scale3d(0.84, 0.84, 1)')
rule('.Lock.stHard3 .LockBox', background_image=url('lockbox_hard.png'), transform='scale3d(0.76, 0.76, 1)', **FLASH)
rule('.HardRing', background_image=url('hardring.png'), background_size='100% 100%', background_repeat='no-repeat', opacity='0')
rule('.Lock.stHard1 .HardRing', opacity='0.3'); rule('.Lock.stHard2 .HardRing', opacity='0.65'); rule('.Lock.stHard3 .HardRing', opacity='1')
tint('.Lock.stAcq .LockState', 'Warn'); tint('.Lock.stHard3 .LockState', 'Danger')
tint('.Lock.stHard3 .LockName', 'Danger'); tint('.Lock.stHard3 .LockRng', 'Danger')
rule('.Lock.stHard3 .LkpFill', background_color=PAL['Danger'])
reg('ifr_lock', ['stAcq', 'stSoft', 'stHard1', 'stHard2', 'stHard3'], prio=1)
reg('ifr_lkx', LKX_CLS, prio=1); reg('ifr_lky', LKY_CLS, prio=1)
LW, LH = 240, 320
lockp = P('ifr_lock', 'Lock ' + h.place(w=LW, h=LH, x=0, y=0), [
    P(None, 'HardRing ' + h.place(w=240, h=240, x=0, y=30)),
    P(None, 'LockBox ' + h.place(w=200, h=200, x=20, y=50)),
    lbl('tname', 'LockName', 240, 22, 'XS', 'Text', 'center', prio=1, x=0, y=16, maxlen=18),
    ladder('lkp', 'LkpFill', 'LkpBar', 120, 4, 12, color=PAL['Warn'], x=60, y=42),
    lbl('lstate', 'LockState', 240, 20, 'XS', 'Text', 'center', prio=1, x=0, y=252, maxlen=12),
    lbl('rng', 'LockRng', 240, 22, 'S', 'Acc', 'center', prio=1, x=0, y=272, maxlen=8),
    ladder('tap', 'TapFill', 'TapBar', 160, 5, 20, colors=[(5, PAL['Danger']), (10, PAL['Warn']), (20, PAL['Ok'])], x=40, y=300),
])
# multi-lock marks (MM-8 Swarm: hold to lock up to four mechs): a diamond on each, amber and blinking while it locks, red when it is locked
ML_N = 4
rule('.MlM', background_image=url('ml.png'), background_size='100% 100%', background_repeat='no-repeat', opacity='0')
rule('.MlM.stOn', opacity='1', **BLINK); rule('.MlM.stDone', opacity='1', background_image=url('ml_done.png'))
mlp = []
for i in range(ML_N):
    reg('ifr_ml%d' % i, ['stOn', 'stDone'], prio=1); reg('ifr_ml%dx' % i, LKX_CLS, prio=1); reg('ifr_ml%dy' % i, LKY_CLS, prio=1)
    mlp.append(P('ifr_ml%dx' % i, 'LkX ' + h.place(w=LW, h=LH, x=0, y=0), [P('ifr_ml%dy' % i, 'LkY ' + h.place(w=LW, h=LH, x=0, y=0), [
        P('ifr_ml%d' % i, 'MlM ' + h.place(w=56, h=56, x=LW / 2 - 28, y=150 - 28))])]))
# teammate marks (11 Nov 2026; skink52: "it doesnt seem to show who is an enemy and who is friendly"): the prop markers over the mechs cannot
# differ per viewer, so each pilot's HUD puts a green chevron over the heads of up to FR_N teammates on screen (50_hud.js ifrHudAllies).
# One picture (hud_images.py ally_mark), 3 panel ids a mark; the triangle's tip is 0.25 mech heights over the head.
FR_N = 8
rule('.FrM', opacity='0', transition_property='opacity', transition_duration='0.15s'); rule('.FrM.stOn', opacity='0.95'); rule('.FrM.stFar', opacity='0.55')
rule('.FrM', background_image=url('ally.png'), background_size='100% 100%', background_repeat='no-repeat')
for i in range(FR_N):
    reg('ifr_fr%d' % i, ['stOn', 'stFar'], prio=1); reg('ifr_fr%dx' % i, LKX_CLS, prio=1); reg('ifr_fr%dy' % i, LKY_CLS, prio=1)
    mlp.append(P('ifr_fr%dx' % i, 'LkX ' + h.place(w=LW, h=LH, x=0, y=0), [P('ifr_fr%dy' % i, 'LkY ' + h.place(w=LW, h=LH, x=0, y=0), [
        P('ifr_fr%d' % i, 'FrM ' + h.place(w=40, h=40, x=LW / 2 - 20, y=150 - 34))])]))
lockroot = P(None, 'Fight LkRoot ' + h.place(w=LW, h=LH, center=True, y=RY + C - 150), mlp + [
    P('ifr_lkx', 'LkX ' + h.place(w=LW, h=LH, x=0, y=0), [P('ifr_lky', 'LkY ' + h.place(w=LW, h=LH, x=0, y=0), [lockp])])])
ret.append(slbl('ASSIST', 'Assist', 80, 18, 'XS', 'Acc', 'left', id_='ifr_assist', x=C + 44, y=C - 9))
rule('.Assist', opacity='0'); rule('.Assist.stOn', opacity='0.9')
reg('ifr_assist', ['stOn'], prio=1)
# missile warning (top of the reticle box)
ret.append(slbl('MISSILE', 'MWarn', 200, 28, 'S', 'Danger', 'center', id_='ifr_mwarn', x=C - 100, y=0))
rule('.MWarn', opacity='0'); rule('.MWarn.stOn', opacity='1', **BLINK)
reg('ifr_mwarn', ['stOn'], prio=0)
# threat chevrons: 8 directions (0 = ahead, clockwise) x lock / launch / close
import math
TH_R = 175
rule('.Th', background_size='100% 100%', background_repeat='no-repeat', opacity='0')
for d in range(8):
    for kind, cls in (('lock', 'stLock'), ('launch', 'stLaunch'), ('close', 'stClose')):
        props = dict(opacity='1', background_image=url('th%d_%s.png' % (d, kind)))
        if kind == 'launch': props.update(BLINK)
        rule('.Th.Th%d.%s' % (d, cls), **props)
    a = math.radians(d * 45 - 90)
    reg('ifr_th%d' % d, ['stLock', 'stLaunch', 'stClose'], prio=0)
    ret.append(P('ifr_th%d' % d, 'Th Th%d %s' % (d, h.place(w=64, h=64, x=C + TH_R * math.cos(a) - 32, y=C + TH_R * math.sin(a) - 32))))
reticle = P(None, 'Fight ' + h.place(w=RB, h=RB, center=True, y=RY), ret)

screen('common')
# ================================================================ COMMON: radar (top left, where CS2's own radar sits; sv_disable_radar 1 hides that one)
RS, RX, RYY, CELLS, DOTS = 280, 20, 20, 24, 64
rule('.Radar', background_image=url('radar.png'), background_size='100% 100%', background_repeat='no-repeat', overflow='noclip noclip')
rule('.RdG', opacity='0', transition_property='transform', transition_duration='0.12s')
cell = RS / CELLS
for n in range(CELLS * CELLS):
    gx, gy = n % CELLS, n // CELLS
    rule('.RdG.stG%d' % n, opacity='1', transform='translatex(%dpx) translatey(%dpx)' % (round((gx + 0.5) * cell - RS / 2), round((gy + 0.5) * cell - RS / 2)))
GRID = ['stG%d' % n for n in range(CELLS * CELLS)]
rule('.RdDot', width='10px', height='10px', background_color=PAL['Dim'])
rule('.RdDot.stA', background_color=PAL['Ally']); rule('.RdDot.stE', background_color=PAL['Enemy'])
rule('.RdDot.stBig', border='2px solid ' + PAL['Gold'])
rule('.RdDot.stBoss', border='3px solid ' + PAL['Danger'])
rule('.RdDot.stTgt', border='2px solid #ffffff')
rdk = []
for n in range(DOTS):
    reg('ifr_rd%d' % n, GRID + ['stA', 'stE', 'stBig', 'stBoss', 'stTgt'], prio=2)
    rdk.append(P('ifr_rd%d' % n, 'RdG RdDot ' + h.place(w=10, h=10, x=RS / 2 - 5, y=RS / 2 - 5)))
rule('.RdPt', background_size='100% 100%', background_repeat='no-repeat')
for L in 'ABC':
    rule('.RdPt.RdPt%s' % L, background_image=url('pt_%s_n.png' % L))
    rule('.RdPt.RdPt%s.stOwnT' % L, background_image=url('pt_%s_t.png' % L))
    rule('.RdPt.RdPt%s.stOwnCT' % L, background_image=url('pt_%s_ct.png' % L))
    reg('ifr_rd%s' % L, GRID + ['stOwnT', 'stOwnCT', 'stCap'], prio=2)
    rdk.append(P('ifr_rd%s' % L, 'RdG RdPt RdPt%s %s' % (L, h.place(w=22, h=22, x=RS / 2 - 11, y=RS / 2 - 11))))
rule('.RdPt.stCap', **BLINK)
rule('.RdDrop', border='2px solid ' + PAL['Dim'])
rule('.RdDrop.RdDropA', border='2px solid ' + PAL['Ally']); rule('.RdDrop.RdDropE', border='2px solid ' + PAL['Enemy'])
for k, c in (('a', 'A'), ('e', 'E')):
    reg('ifr_rdD%s' % k, GRID, prio=2)
    rdk.append(P('ifr_rdD%s' % k, 'RdG RdDrop RdDrop%s %s' % (c, h.place(w=14, h=14, x=RS / 2 - 8, y=RS / 2 - 8))))
rule('.RdSelf', background_image=url('self.png'), background_size='100% 100%', background_repeat='no-repeat')
rdk.append(P(None, 'RdSelf ' + h.place(w=16, h=16, x=RS / 2 - 8, y=RS / 2 - 8)))
rdk.append(lbl('rrange', '', 80, 16, 'XS', 'Dim', 'right', right=14, y=RS - 24, maxlen=6))
radar = P(None, 'Common Radar ' + h.place(w=RS, h=RS, x=RX, y=RYY), rdk)

# ================================================================ COMMON: mode panel (top centre, under CS2's team counter), objective tier, capture strip
# Everything here stays inside W/2 +- 280 so it clears CS2's kill feed (x >= W - 430) down to 4:3 (W 1440; 10 Nov 2026 playtest).
#   mode box   : the persistent mode tag (TDM / CONQUEST / KOTH / CTF / FFA / SORTIE, its own colour), T score, clock, CT score; the objective line under them
#   objective  : up to 3 chips (Conquest A B C, the KOTH hill in the middle, CTF the T flag left / CT flag right): owner colour, a progress bar, a state word
#   capture    : a wide bar while a zone is being taken / contested, or a flag is carried / dropped (stT / stCT / stCont colour it)
MW_, MH, MY = 560, 76, 72
MODES = ['tb', 'cq', 'sk', 'so', 'kh', 'ctf']
MODE_COL = {'tb': '#ff5a46', 'cq': '#ffd25a', 'sk': '#ff3fd8', 'so': '#5ee08a', 'kh': '#ffc247', 'ctf': '#38d8ff'}
rule('.ModeBox', background_color=PLATE, border='2px solid ' + LINE)
rule('.MTag', background_color='#121a22e0', border='2px solid ' + LINE)
for m_, c_ in MODE_COL.items(): rule('.MTag.stM%s' % m_, border='2px solid ' + c_, background_color=c_ + '30')
reg('ifr_mtag', ['stM%s' % m_ for m_ in MODES], prio=3)
rule('.BossBar', opacity='0'); rule('.ModeBox.stBoss .BossBar', opacity='1')
reg('ifr_modebox', ['stBoss'], prio=3)
# team score: each score sits on a plate in its team colour; YOUR team's plate is lit and underlined by the root's team class (no script writes)
rule('.ScT', background_color='#ffb04a14'); rule('.ScCT', background_color='#5fd3ff14')
rule('.ScBar', opacity='0.35'); rule('.ScBarT', background_color=PAL['T']); rule('.ScBarCT', background_color=PAL['CT'])
rule('.IfrRoot.stTeamT .ScT', background_color='#ffb04a40'); rule('.IfrRoot.stTeamCT .ScCT', background_color='#5fd3ff40')
rule('.IfrRoot.stTeamT .ScBarT', opacity='1'); rule('.IfrRoot.stTeamCT .ScBarCT', opacity='1')
mode = P('ifr_modebox', 'Common ModeBox ' + h.place(w=MW_, h=MH, center=True, y=MY), [
    P('ifr_mtag', 'MTag ' + h.place(w=150, h=40, x=8, y=4), [lbl('mode', '', 146, 36, 'M', 'Text', 'center', x=2, y=2, maxlen=10)]),
    P(None, 'ScT ' + h.place(w=124, h=40, x=164, y=3)), P(None, 'ScCT ' + h.place(w=124, h=40, x=406, y=3)),
    P(None, 'ScBar ScBarT ' + h.place(w=124, h=4, x=164, y=41)), P(None, 'ScBar ScBarCT ' + h.place(w=124, h=4, x=406, y=41)),
    lbl('scoreT', '', 120, 40, 'L', 'T', 'right', x=166, y=4, maxlen=5),
    lbl('clock', '', 110, 40, 'L', 'Text', 'center', x=292, y=4, maxlen=6),
    lbl('scoreCT', '', 120, 40, 'L', 'CT', 'left', x=408, y=4, maxlen=5),
    lbl('sub', '', 540, 22, 'XS', 'Dim', 'center', x=10, y=46, maxlen=48),
    P(None, 'BossBar ' + h.place(w=300, h=6, x=130, y=68), [
        ladder('bap', 'BapFill', 'BapBar', 300, 6, 20, color=PAL['Danger'], x=0, y=0)]),
])
# objective chips
rule('.ObjTier', opacity='0'); rule('.ObjTier.stOn', opacity='1')
reg('ifr_obj', ['stOn'], prio=3)
rule('.Ob', background_color=PLATE, border='2px solid ' + LINE, opacity='0'); rule('.Ob.stOn', opacity='1')
rule('.Ob.stT', border='2px solid ' + PAL['T']); rule('.Ob.stCT', border='2px solid ' + PAL['CT']); rule('.Ob.stCont', border='2px solid ' + PAL['Danger'])
rule('.ObK', background_color='#2a3640', border='2px solid ' + LINE)
rule('.ObK.stOwnT', background_color='#a8641ce0', border='2px solid ' + PAL['T']); rule('.ObK.stOwnCT', background_color='#1f6f94e0', border='2px solid ' + PAL['CT'])
rule('.ObK.stCap', **BLINK)
rule('.ObFill', background_color=PAL['Dim'])
rule('.Ob.stT .ObFill', background_color=PAL['T']); rule('.Ob.stCT .ObFill', background_color=PAL['CT']); rule('.Ob.stCont .ObFill', background_color=PAL['Danger'], **FLASH)
tint('.Ob.stCont .ObTxt', 'Danger')
chips = []
for i in range(3):
    reg('ifr_ob%d' % i, ['stOn', 'stT', 'stCT', 'stCont'], prio=3)
    reg('ifr_obk%d' % i, ['stOwnT', 'stOwnCT', 'stCap'], prio=3)
    chips.append(P('ifr_ob%d' % i, 'Ob ' + h.place(w=180, h=40, x=i * 188, y=0), [            # 184 x 44 with the border
        P('ifr_obk%d' % i, 'ObK ' + h.place(w=40, h=32, x=2, y=2), [lbl('ob%dk' % i, '', 40, 32, 'S', 'Text', 'center', x=0, y=0, maxlen=2)]),
        lbl('ob%dt' % i, 'ObTxt', 128, 22, 'XS', 'Text', 'left', x=50, y=0, maxlen=12),
        ladder('ob%dp' % i, 'ObFill', 'ObBar', 124, 6, 20, x=50, y=28)]))
objt = P('ifr_obj', 'Common ObjTier ' + h.place(w=MW_, h=44, center=True, y=MY + MH + 6), chips)
# the capture strip
rule('.CapStrip', background_color='#0a0f14d8', border='2px solid ' + LINE, opacity='0'); rule('.CapStrip.stOn', opacity='1')
rule('.CapFill', background_color=PAL['Dim'])
rule('.CapStrip.stT', border='2px solid ' + PAL['T']); rule('.CapStrip.stCT', border='2px solid ' + PAL['CT']); rule('.CapStrip.stCont', border='2px solid ' + PAL['Danger'])
rule('.CapStrip.stT .CapFill', background_color=PAL['T']); rule('.CapStrip.stCT .CapFill', background_color=PAL['CT']); rule('.CapStrip.stCont .CapFill', background_color=PAL['Danger'], **FLASH)
tint('.CapStrip.stCont .CapTxt', 'Danger'); tint('.CapStrip.stWarn .CapTxt', 'Warn')
reg('ifr_cap', ['stOn', 'stT', 'stCT', 'stCont', 'stWarn'], prio=1)
capy = MY + MH + 6 + 50
cap = P('ifr_cap', 'Common CapStrip ' + h.place(w=460, h=46, center=True, y=capy), [
    lbl('capl', 'CapTxt', 440, 24, 'S', 'Text', 'center', prio=1, x=8, y=2, maxlen=34),
    ladder('capbar', 'CapFill', 'CapBar', 440, 8, 40, x=8, y=32)])
# badges row: bounty, rookie shield, streak, XP ticker (under the capture strip)
BADGE_W = 620
BADGE_Y = capy + 52
rule('.Badge', opacity='0', transition_property='opacity', transition_duration='0.2s'); rule('.Badge.stOn', opacity='1')
rule('.Badge.stPop', **POP); rule('.Badge.stPop2', **POP2)   # no opacity here: the pop class stays on after the badge is switched off (stOn), and kept it on screen for good
rule('.BIcon', background_size='100% 100%', background_repeat='no-repeat')
rule('.BIcon.Bounty', background_image=url('b_bounty.png')); rule('.BIcon.Rookie', background_image=url('b_rookie.png')); rule('.BIcon.Streak', background_image=url('b_streak.png'))
for pid in ('ifr_bounty', 'ifr_rookie'): reg(pid, ['stOn'], prio=3)
reg('ifr_xp', ['stOn', 'stPop', 'stPop2'], prio=3)
# (the streak badge went: the streak meter under the radar shows the count and the next reward; evening playtest 10 Nov 2026)
badges = P(None, 'Common ' + h.place(w=BADGE_W, h=36, center=True, y=BADGE_Y), [
    P('ifr_bounty', 'Badge ' + h.place(w=150, h=36, x=0, y=0), [P(None, 'BIcon Bounty ' + h.place(w=32, h=32, x=0, y=2)), slbl('BOUNTY', '', 108, 20, 'XS', 'Gold', x=38, y=8)]),
    P('ifr_rookie', 'Badge ' + h.place(w=150, h=36, x=150, y=0), [P(None, 'BIcon Rookie ' + h.place(w=32, h=32, x=0, y=2)), slbl('ROOKIE', '', 108, 20, 'XS', 'CT', x=38, y=8)]),
    lbl('xp', 'Badge', 180, 28, 'S', 'Ok', 'right', id_='ifr_xpv', box='ifr_xp', x=440, y=4, maxlen=10),
])
# kill confirm pop and the message line. 10 Nov 2026 evening playtest ("many in game messages get cut off"): the line is now THREE rows of 18 px
# capitals (was two rows of 14 px), 640 px wide; the driver wraps by pixel width and cell count, breaks a word wider than a row, and shows what
# does not fit as a second page instead of dropping it (50_hud.js ifrHudLine). stHi (a gold bar and gold type) marks a message that asks the
# pilot to do something. Shifted right so the left end clears CS2's chat box down to 4:3 (the chat takes 576 px of 1440).
rule('.KillPop', opacity='0'); rule('.KillPop.stOn', opacity='1'); rule('.KillPop.stPop', **POP); rule('.KillPop.stPop2', **POP2)   # as .Badge: "DESTROYED ..." never left the screen
reg('ifr_kill', ['stOn', 'stPop', 'stPop2'], prio=3)
# 10 Nov 2026 recording: the kill line and the message line lay across the pilot's own mech (the 640 px column, 190 px right of centre).
# They are now a 500 px column of four rows RIGHT of the mech (its left edge 180 px right of the screen centre, its right edge at the
# screen edge on a 4:3 screen), above the weapon boxes.
LINE_W, LINE_ROWS, LINE_PITCH = 500, 4, 26
MSG_SHIFT = 180 + (LINE_W + 20) // 2
rule('.KillPos', transform='translatex(%dpx)' % MSG_SHIFT)
kill = lbl('kill', 'Common KillPop KillPos', LINE_W + 20, 30, 'M', 'Warn', 'center', id_='ifr_killv', box='ifr_kill', center=True, y=662, maxlen=30)
rule('.Line', opacity='0', transform='translatex(%dpx)' % MSG_SHIFT); rule('.Line.stOn', opacity='1')
tint('.Line.stHi', 'Gold', True)
reg('ifr_line', ['stOn', 'stHi'] + ['stR%d' % k for k in range(1, LINE_ROWS + 1)], prio=3)
# the plate is as tall as the rows in use: one plate (and its edge bar) per row count, shown by stR1..3 on the box
rule('.LineBg', background_color='#0a0f14b0', opacity='0'); rule('.LineBar', background_color=LINE, opacity='0'); rule('.Line.stHi .LineBar', background_color=PAL['Gold'])
_lbg = []
for k in range(1, LINE_ROWS + 1):
    rule('.Line.stR%d .LineBg%d' % (k, k), opacity='1'); rule('.Line.stR%d .LineBar%d' % (k, k), opacity='1')
    _lbg += [P(None, 'LineBg LineBg%d ' % k + h.place(w=LINE_W + 20, h=k * LINE_PITCH + 6, x=0, y=0)), P(None, 'LineBar LineBar%d ' % k + h.place(w=4, h=k * LINE_PITCH + 6, x=0, y=0))]
line = P('ifr_line', 'Common Line ' + h.place(w=LINE_W + 20, h=LINE_ROWS * LINE_PITCH + 6, center=True, y=696), _lbg + [
    lbl('line%s' % ('' if k == 0 else str(k + 1)), '', LINE_W, LINE_PITCH, 'S', 'Text', 'center', id_='ifr_line%s' % 'abcdef'[k], x=12, y=3 + k * LINE_PITCH, maxlen=64) for k in range(LINE_ROWS)])

# ================================================================ COMMON: the pilot plate and the streak meter (left column, under the radar)
# 10 Nov 2026 evening playtest: "no real indication of current frags ... or what killstreaks do". Always on screen: YOUR TEAM vs ENEMY score
# (tickets in Conquest, your kills vs the leader in FFA), your kills / deaths / assists, and the streak meter: eight pips with the reward marks
# at 3 / 5 / 8, the next reward by name and what it gives. 340 wide: left of the reticle box (x >= 480 at 4:3), above the chat (y >= 800).
LCW, LCX = 356, 20
PILOT_Y = RYY + RS + 8
rule('.PPl', background_color=PLATE, border='2px solid ' + LINE)
rule('.PSep', background_color=LINE)
def pcell(cap, var, x, w, color, size='M', maxlen=6):
    return [slbl(cap, '', w, 16, 'XS', 'Dim', 'center', x=x, y=2), lbl(var, '', w, 26, size, color, 'center', x=x, y=18, maxlen=maxlen)]
pilot = P(None, 'Common PPl ' + h.place(w=LCW - 4, h=96, x=LCX, y=PILOT_Y),
          pcell('YOUR TEAM', 'pmy', 4, 160, 'Acc') + pcell('ENEMY', 'pen', 172, 160, 'Danger') + [P(None, 'PSep ' + h.place(w=2, h=40, x=167, y=4)), P(None, 'PSep ' + h.place(w=LCW - 16, h=2, x=6, y=48))]
          + [x_ for i_, (c_, v_) in enumerate((('KILLS', 'pk'), ('DEATHS', 'pd'), ('ASSISTS', 'pa'))) for x_ in
             [slbl(c_, '', 108, 16, 'XS', 'Dim', 'center', x=4 + i_ * 110, y=52), lbl(v_, '', 108, 24, 'S', 'Text', 'center', x=4 + i_ * 110, y=68, maxlen=5)]])
STREAK_Y = PILOT_Y + 100 + 6
SPIP, SPW = 8, 38                 # pips and their pitch
rule('.SkMark', border='2px solid ' + PAL['Gold'], opacity='0.9')
rule('.SkPl.stHot', border='2px solid ' + PAL['Gold'])
reg('ifr_streakp', ['stHot', 'stPop', 'stPop2'], prio=3)
rule('.SkPl.stPop', **POP); rule('.SkPl.stPop2', **POP2)
sk = [slbl('KILL STREAK', '', 150, 18, 'XS', 'Dim', x=8, y=3),
      lbl('stk', '', 60, 22, 'S', 'Warn', 'left', x=8 + F.METRICS['XS'].text_w('KILL STREAK') + 10, y=0, maxlen=3),
      ladder('skp', 'SkFill', 'SkBar', SPIP * SPW, 10, SPIP, color=PAL['Warn'], x=10, y=27)]
for n_, lab in ((3, '3'), (5, '5'), (8, '8')):
    sk.append(P(None, 'SkMark ' + h.place(w=SPW - 4, h=10, x=10 + (n_ - 1) * SPW, y=25)))
    sk.append(slbl(lab, '', SPW, 16, 'XS', 'Gold', 'center', x=10 + (n_ - 1) * SPW, y=40))
sk.append(lbl('str', 'SkTxt', LCW - 20, 18, 'XS', 'Text', 'left', x=8, y=58, maxlen=30))
sk.append(lbl('str2', 'SkTxt', LCW - 20, 18, 'XS', 'Dim', 'left', x=8, y=77, maxlen=30))
streakp = P('ifr_streakp', 'Common PPl SkPl ' + h.place(w=LCW - 4, h=98, x=LCX, y=STREAK_Y), sk)
# the pilot's identity and today's contract (S2 / S3, 11 Nov 2026): who you fly as (badge tag, callsign, title: the profile that follows the pilot
# on a SlimeMG server, the session's own stand-alone) and the daily contract nearest to done. Two Labels and one switch (3 ids); hidden when
# there is nothing to say. Ends at y 570: still above CS2's chat box (y >= 600 on the left is kept clear).
IDENT_Y = STREAK_Y + 98 + 6
rule('.Ident', opacity='0', transition_property='opacity', transition_duration='0.25s'); rule('.Ident.stOn', opacity='1')
reg('ifr_ident', ['stOn'], prio=3)
ident = P(None, 'Common ' + h.place(w=LCW, h=56, x=LCX, y=IDENT_Y), [P('ifr_ident', 'PPl Ident ' + h.place(w=LCW - 4, h=52, x=0, y=0), [
    lbl('ptag', '', LCW - 20, 22, 'XS', 'Acc', 'left', x=8, y=3, maxlen=30),
    lbl('dly', '', LCW - 20, 20, 'XS', 'Gold', 'left', x=8, y=27, maxlen=32)])])

screen('cards')
# ================================================================ cards: controls (left) and loadout (right)
# 10 Nov 2026 evening playtest: "not much is easy to understand or jump straight into". The controls card (static: one class shows it) comes up
# at the first spawns of a session, on the first death screens and on !help; the loadout card at every spawn for a few seconds: the four weapons
# with the key that fires each and a role in a word or two, the frame and its trait with the key that uses it.
rule('.Card', background_color='#070c12fa', border='2px solid ' + PAL['Acc'], opacity='0', transition_property='opacity', transition_duration='0.25s')
rule('.Card.stOn', opacity='1')
rule('.CardHd', background_color='#12202cf0')
CTRL_ROWS = [('W A S D', 'MOVE'), ('SHIFT', 'BOOST (HOLD IT)'), ('CTRL', 'QUICK BOOST: DODGE'), ('SPACE', 'JUMP, HOLD TO HOVER'), ('MOUSE 1 / 2', 'ARM WEAPONS'),
             ('R / E', 'SHOULDER WEAPONS'), ('AIM', 'RING ON ENEMY = LOCK'), ('F', 'NEXT TARGET'), ('HOLD F', 'FRAME SKILL (IF ANY)'), ('HOLD R + E', 'OVERDRIVE (GOLD BAR)'),
             ('DEAD: CTRL', 'GARAGE: NEW LOADOUT'), ('CHAT', '!HELP  !GARAGE  !VOTE')]
CPITCH = 20
CKW = max(F.METRICS['XS'].text_w(k_) for k_, _ in CTRL_ROWS) + 12
CAW = max(F.METRICS['XS'].text_w(a_) for _, a_ in CTRL_ROWS) + 8
CCW = 10 + CKW + CAW + 10
CTRL_Y = PILOT_Y        # over the pilot plate and the streak meter while it shows: nothing of ours under y 600 on the left (CS2's chat box)
ck = [P(None, 'CardHd ' + h.place(w=CCW, h=24, x=0, y=0)), slbl('CONTROLS', '', 200, 20, 'XS', 'Acc', x=10, y=2), slbl('!HELP SHOWS THIS', '', 200, 20, 'XS', 'Dim', 'right', x=CCW - 210, y=2)]
for i_, (k_, a_) in enumerate(CTRL_ROWS):
    ck.append(slbl(k_, '', CKW, 20, 'XS', 'Gold', x=10, y=27 + i_ * CPITCH)); ck.append(slbl(a_, '', CAW, 20, 'XS', 'Text', x=10 + CKW, y=27 + i_ * CPITCH))
reg('ifr_ctrl', ['stOn'], prio=3)
# 11 Nov 2026 (skink52: "The !help menu has a lot of text get cut off"): !help was this card plus four long sentences paged through the message line
# (Labels in a font whose in-game width is unverified, 3.5 s a page). Now everything !help says is static neon type on a second card beside the
# controls: no Label, no wrapping, no paging, so nothing can be cut. Both cards stay up 25 s; the bottom edge stays above CS2's chat box (y 600).
HELP_TIPS = ['MISSILES TRACK ONCE THE BRACKET IS RED', 'GOLD BAR FULL: HOLD R + E = OVERDRIVE', 'DEAD: CTRL OR F OPENS THE GARAGE', 'HOLD TAB, THEN LET GO: THIS HELP']
HELP_CMDS = [('!GARAGE', 'CHANGE YOUR MECH'), ('!LOADOUT 1-6', 'USE A SAVED LOADOUT'), ('!SPEC  !BACK', 'WATCH / RETURN'), ('!VOTE', 'VOTE ON THE NEXT MODE'),
             ('!MODE', 'THIS MODE AND SCORE'), ('!PILOT', 'RANK, XP, CREDITS'), ('!CAM', 'CAMERA DISTANCE')]
HKW = max(F.METRICS['XS'].text_w(k_) for k_, _ in HELP_CMDS) + 12
HCW = 10 + max(max(F.METRICS['XS'].text_w(t_) for t_ in HELP_TIPS), HKW + max(F.METRICS['XS'].text_w(a_) for _, a_ in HELP_CMDS)) + 14
hk_ = [P(None, 'CardHd ' + h.place(w=HCW, h=24, x=0, y=0)), slbl('HOW TO FIGHT', '', 200, 20, 'XS', 'Acc', x=10, y=2)]
for i_, t_ in enumerate(HELP_TIPS): hk_.append(slbl(t_, '', HCW - 20, 20, 'XS', 'Text', x=10, y=27 + i_ * CPITCH))
_hy = 27 + len(HELP_TIPS) * CPITCH + 2
hk_ += [P(None, 'CardHd ' + h.place(w=HCW, h=22, x=0, y=_hy)), slbl('CHAT COMMANDS', '', 200, 20, 'XS', 'Acc', x=10, y=_hy + 1)]
for i_, (k_, a_) in enumerate(HELP_CMDS):
    hk_.append(slbl(k_, '', HKW, 20, 'XS', 'Gold', x=10, y=_hy + 25 + i_ * CPITCH)); hk_.append(slbl(a_, '', HCW - HKW - 20, 20, 'XS', 'Text', x=10 + HKW, y=_hy + 25 + i_ * CPITCH))
HELP_H = _hy + 25 + len(HELP_CMDS) * CPITCH + 4
reg('ifr_help', ['stOn'], prio=3)
CTRL_H = 27 + len(CTRL_ROWS) * CPITCH + 4
ctrl = P(None, 'Common ' + h.place(w=CCW + 4, h=CTRL_H + 4, x=LCX, y=CTRL_Y), [P('ifr_ctrl', 'Card ' + h.place(w=CCW, h=CTRL_H, x=0, y=0), ck)])
assert CTRL_Y + max(CTRL_H, HELP_H) + 4 <= 600, 'the help cards reach into the chat box: %d' % (CTRL_Y + max(CTRL_H, HELP_H) + 4)
helpc = P(None, 'Common ' + h.place(w=HCW + 4, h=HELP_H + 4, x=LCX + CCW + 10, y=CTRL_Y), [P('ifr_help', 'Card ' + h.place(w=HCW, h=HELP_H, x=0, y=0), hk_)])
LOW = 496
lk_ = [P(None, 'CardHd ' + h.place(w=LOW, h=24, x=0, y=0)), slbl('YOUR LOADOUT', '', 200, 20, 'XS', 'Acc', x=10, y=2),
       lbl('lcf', '', 240, 20, 'XS', 'Text', 'right', x=LOW - 250, y=2, maxlen=20)]
for i_, tag in enumerate(['M1', 'M2', 'R', 'E']):
    reg('ifr_lci%d' % i_, ['stW%s' % f for f in FAMS], prio=3)
    y_ = 30 + i_ * 30
    lk_ += [slbl(tag, '', 40, 22, 'S', 'Gold', 'center', x=6, y=y_), P('ifr_lci%d' % i_, 'WIcon ' + h.place(w=28, h=28, x=50, y=y_ - 2)),
            lbl('lc%dn' % i_, '', 170, 22, 'XS', 'Text', 'left', x=84, y=y_ + 2, maxlen=14), lbl('lc%dr' % i_, '', 232, 22, 'XS', 'Cy', 'left', x=258, y=y_ + 2, maxlen=20)]
lk_ += [P(None, 'PSep ' + h.place(w=LOW - 16, h=2, x=8, y=152)),
        lbl('lct', '', LOW - 20, 20, 'XS', 'Gold', 'left', x=10, y=156, maxlen=40), lbl('lct2', '', LOW - 20, 20, 'XS', 'Dim', 'left', x=10, y=176, maxlen=40)]
reg('ifr_load', ['stOn'], prio=3)
loadc = P(None, 'Fight ' + h.place(w=LOW + 4, h=206, right=24, y=206), [P('ifr_load', 'Card ' + h.place(w=LOW, h=202, x=0, y=0), lk_)])

screen('slates')
# ================================================================ slates: intro, death, podium, spectator bar
# the intro: the mode in big type with a bar in the mode's colour (the same colours as the fight HUD's mode tag) and the objective in two lines
rule('.IMBar', background_color=LINE)
for m_, c_ in MODE_COL.items(): rule('.IMBar.stM%s' % m_, background_color=c_)
reg('ifr_imbar', ['stM%s' % m_ for m_ in MODES], prio=3)
intro = P(None, 'Intro Plate ' + h.place(w=760, h=452, center=True, y=228), [
    slbl('IRONFRAME', '', 740, 90, 'XXL', 'Acc', 'center', x=9, y=6),
    lbl('arena', '', 740, 40, 'L', 'Text', 'center', x=9, y=96, maxlen=24),
    lbl('imode', '', 740, 50, 'XL', 'Text', 'center', x=9, y=138, maxlen=18),
    P('ifr_imbar', 'IMBar ' + h.place(w=320, h=4, x=220, y=192)),
    lbl('iobj', '', 740, 26, 'S', 'Text', 'center', x=9, y=202, maxlen=52),
    lbl('iobj2', '', 740, 26, 'S', 'Text', 'center', x=9, y=228, maxlen=52),
    *[slbl(t_, '', 740, 22, 'XS', 'Dim', 'center', x=9, y=266 + i_ * 23) for i_, t_ in enumerate((
        'WASD MOVE   SHIFT BOOST   CTRL QUICK-BOOST', 'SPACE JUMP / HOVER   F NEXT TARGET', 'MOUSE 1 / 2 ARM WEAPONS   R / E SHOULDER WEAPONS',
        'KEEP AN ENEMY IN THE RING TO LOCK ON', 'HOLD R + E: OVERDRIVE   !HELP SHOWS THE CONTROLS'))],
    lbl('ihint', '', 740, 36, 'M', 'Warn', 'center', x=9, y=394, maxlen=40),
])
death = P(None, 'Death Plate ' + h.place(w=600, h=264, center=True, y=300), [
    slbl('DESTROYED BY', '', 580, 24, 'XS', 'Dim', 'center', x=9, y=16),
    lbl('killer', '', 580, 60, 'XL', 'Danger', 'center', x=9, y=44, maxlen=24),
    lbl('kframe', '', 580, 26, 'S', 'Acc', 'center', x=9, y=108, maxlen=28),
    lbl('kweapon', '', 580, 26, 'S', 'Text', 'center', x=9, y=136, maxlen=30),
    lbl('respawn', '', 580, 36, 'M', 'Warn', 'center', x=9, y=168, maxlen=32),
    slbl('CTRL OR F: GARAGE (CHANGE WEAPONS AND FRAME)', '', 580, 22, 'XS', 'Dim', 'center', x=9, y=210),
    slbl('SPACE: BACK INTO THE FIGHT', '', 580, 22, 'XS', 'Dim', 'center', x=9, y=232),
])
rule('.PCard', background_color=PLATE2, border='2px solid ' + LINE)
rule('.PCard.stT', border='2px solid ' + PAL['T']); rule('.PCard.stCT', border='2px solid ' + PAL['CT']); rule('.PCard.stMe', background_color='#1e3a48d0')
cards = []
for i, (cx, cy, ch) in enumerate(((260, 100, 150), (8, 130, 120), (512, 130, 120))):
    reg('ifr_pc%d' % i, ['stT', 'stCT', 'stMe'], prio=3)
    cards.append(P('ifr_pc%d' % i, 'PCard ' + h.place(w=240, h=ch, x=cx, y=cy), [
        slbl(('1ST', '2ND', '3RD')[i], '', 220, 30, 'M' if i == 0 else 'S', 'Gold' if i == 0 else 'Dim', 'center', x=9, y=10),
        lbl('pn%d' % i, '', 228, 28, 'S', 'Text', 'center', x=5, y=46, maxlen=12),
        lbl('ps%d' % i, '', 228, 22, 'XS', 'Dim', 'center', x=5, y=78, maxlen=20),
    ]))
tally = []
for i in range(6):
    tally.append(lbl('pt%dl' % i, '', 300, 30, 'S', 'Dim', 'right', x=70, y=300 + i * 34, maxlen=24))
    tally.append(lbl('pt%dv' % i, '', 340, 30, 'S', 'Text', 'left', x=390, y=300 + i * 34, maxlen=24))
podium = P(None, 'Podium Plate ' + h.place(w=760, h=580, center=True, y=196), [    # under CS2's kill feed band (y 72-190) down to 4:3
    lbl('phead', '', 740, 60, 'XL', 'Acc', 'center', x=9, y=10, maxlen=20),
    lbl('psub', '', 740, 24, 'XS', 'Dim', 'center', x=9, y=72, maxlen=40),
] + cards + tally + [lbl('pfoot', '', 740, 28, 'S', 'Warn', 'center', x=9, y=530, maxlen=48)])
# the server's top pilots beside the podium (S3, 11 Nov 2026; the leaderboard payload t1 of docs/SERVER_CONTRACT.md section 10): five rows of
# two Labels (place + name left, rank + XP right), the pilot's own place under them, a header count: 13 ids. Right of the podium plate, its
# right edge 14 px inside a 4:3 screen (720 + 546 + 160 = 1426 of 1440); under CS2's kill feed band like the podium. Shown only on a server
# that sent a leaderboard (stand-alone: hidden).
LBW = 316
rule('.LbPos', transform='translatex(%dpx)' % (380 + 6 + (LBW + 4) // 2))
reg('ifr_lb', ['stOn'], prio=3)
lbk = [P(None, 'CardHd ' + h.place(w=LBW, h=24, x=0, y=0)), slbl('TOP PILOTS', '', 150, 20, 'XS', 'Acc', x=10, y=2),
       lbl('lbh', '', 170, 20, 'XS', 'Dim', 'right', x=LBW - 180, y=2, maxlen=16)]
for i in range(5):
    lbk += [lbl('lb%dn' % i, '', 184, 22, 'XS', 'Text', 'left', x=10, y=30 + i * 24, maxlen=16),
            lbl('lb%dv' % i, '', 112, 22, 'XS', 'Dim', 'right', x=LBW - 122, y=30 + i * 24, maxlen=13)]
lbk += [P(None, 'PSep ' + h.place(w=LBW - 16, h=2, x=8, y=153)), lbl('lbme', '', LBW - 20, 22, 'XS', 'Gold', 'left', x=10, y=159, maxlen=32)]
board = P(None, 'Podium LbPos ' + h.place(w=LBW + 4, h=192, center=True, y=196), [P('ifr_lb', 'Card ' + h.place(w=LBW, h=188, x=0, y=0), lbk)])
# the spectator bar: below the reticle, shifted right like the message line (the objective tier and capture strip now use y 154-254)
rule('.SpecPos', transform='translatex(160px)')
spec = lbl('spec', 'SpecBar Plate SpecPos', 560, 32, 'XS', 'Text', 'center', id_='ifr_spec', center=True, y=650, maxlen=52)

screen('garage')
# ================================================================ garage (armory terminal)
# A 90s arcade / mecha military terminal: dark plates, cyan / blue / purple, magenta for focus. The centre stays transparent: the real mech
# stands in the world there (60_garage.js moves the player's camera to a hangar bay).
# Aspect-safe from 4:3 (1440 wide) to 21:9 (10 Nov 2026 playtest: at 4:3 the right-pinned ITEM INFORMATION plate covered EQUIPPED WEAPONS,
# which looked blank, and the centre block lay over the upgrade tracks). Three columns that never meet at 1440:
#   left  (pinned left, x 20-568):      top bar (credits, K/D/A; ends before CS2's team counter at W/2 - 360) | ARMORY (tabs, 8 rows) | EQUIPPED WEAPONS
#   centre (pinned centre + 60, 400 wide; 580-980 at 1440): bay caption | confirm bar | legend | FRAME statistics (clear of the chat at x < 576)
#   right (pinned right, 430 wide; 990-1420 at 1440): top bar (map, rank) | UPGRADE TRACKS (from y 196, under the kill feed) | ITEM INFORMATION
# CS2 zones: team counter W/2 +- 360 y 0-66, kill feed x >= W - 430 y 72-190, chat x < 576 y >= 800, money row y >= 1000.
TABS = ['ALL', 'PRIMARY', 'SHLD', 'SPECIAL', 'UTILITY', 'FRAMES', 'PAINT', 'SLOTS', 'PILOT', 'SORTIE']   # PILOT (S2): the list rows show the profile, the contracts and the top pilots: no new Labels. SORTIE stays last (W from the first tab reaches it)
CATS = TABS
GROWS, GTRACKS = 8, 8
ROWP = 52                         # list row pitch
GCY, GMG = PAL['Cy'], PAL['Mg']
GBG, GLN = '#050916ec', '#2a8fb8'
_pc = {}
def pl(**kw):
    """h.place with a memo: equal geometry shares one class"""
    k = tuple(sorted(kw.items()))
    if k not in _pc: _pc[k] = h.place(**kw)
    return _pc[k]
def btn(id_, cls, kids):
    """a clickable Button (panorama.P makes every panel hittest=false; the Button itself gets true, its labels stay false)"""
    # CS2's CustomHud validation rejects the whole layout if a Button carries a hittest attribute (9 Nov 2026 playtest)
    reg(id_, prio=3)            # a Button's id counts toward the id budget even when the script only hears its clicks
    return P(id_, cls, kids, tag='Button').replace(' hittest="false"', '', 1)
def corners(w, hh, cls='Br', a=18, t=4):
    out = []
    for cx, cy, sx, sy in ((0, 0, 1, 1), (w, 0, -1, 1), (0, hh, 1, -1), (w, hh, -1, -1)):
        out.append(P(None, cls + ' ' + pl(w=a, h=t, x=cx if sx > 0 else cx - a, y=cy if sy > 0 else cy - t)))
        out.append(P(None, cls + ' ' + pl(w=t, h=a, x=cx if sx > 0 else cx - t, y=cy if sy > 0 else cy - a)))
    return out
def gpanel(x, y, w, hh, title, kids, right=None):
    """a sharp-cornered neon plate; the title sits ON the top border and breaks the line like a fieldset legend (the cover panel hides the line
    behind the letters). The wrapper is 11 px taller than the plate so the legend can stand above its edge."""
    M = F.METRICS['XS']; t = title.upper(); tw = M.text_w(t)
    cw, ch = w - 4, hh - 4
    legend = [P(None, 'LgBg ' + pl(w=tw + 20, h=6, x=14, y=9)),
              slbl(t, '', tw + 4, 22, 'XS', 'Cy', x=24, y=1)]
    body = P(None, 'GP ' + pl(w=cw, h=ch, x=0, y=11), kids + corners(cw, ch) + [P(None, 'InGlow ' + pl(w=cw - 8, h=ch - 8, x=2, y=2))])
    ww = pl(w=w, h=hh + 11, right=right, y=y - 11) if right is not None else pl(w=w, h=hh + 11, x=x, y=y - 11)
    return P(None, 'GW ' + ww, [body] + legend)

rule('.GP', background_color=GBG, border='2px solid ' + GLN); rule('.LgBg', background_color='#050916'); rule('.InGlow', border='3px solid #38d8ff14')
rule('.GHd', background_color='#1d1058f0')
rule('.Br', background_color=GCY); rule('.BrM', background_color=GMG)
rule('.GSep', background_color='#1d3a5a')
rule('.GCat', background_color='#0a1230f0', border='2px solid #1d3f66')
rule('.GCat:hover', background_color='#16336cf0')
rule('.GCat.stSel', background_color='#1b3c96f0', border='2px solid ' + GCY)
tint('.GCat.stSel', 'Text', True)
rule('.GCat.stOff', opacity='0', visibility='collapse')
rule('.GPage.stCol0 .GCat.stSel', border='2px solid ' + GMG)
rule('.GRow', background_color='#09112aea', border='2px solid #12284a')
rule('.GRow:hover', background_color='#13306ceb')
rule('.GRow.stSel', background_color='#14327aec', border='2px solid ' + GCY)
rule('.GPage.stCol1 .GRow.stSel', border='2px solid ' + GMG)
tint('.GRow.stLocked .GName', 'Dim'); tint('.GRow.stLocked .GCost', 'Danger')
tint('.GRow.stBuy .GCost', 'Gold'); tint('.GRow.stPoor .GCost', 'Danger'); tint('.GRow.stPoor .GSub', 'Danger')
tint('.GRow.stOwned .GCost', 'Dim'); tint('.GRow.stEquip .GCost', 'Ok'); tint('.GRow.stEquip .GName', 'Ok')
tint('.GRow.stEquip .GSub', 'Ok')
rule('.GEq', background_color='#00000000'); rule('.GRow.stEquip .GEq', background_color=PAL['Ok']); rule('.GRow.stBuy .GEq', background_color=PAL['Gold'])
rule('.GRow.stLocked .GPic', opacity='0.35')
rule('.GRow.stOff', opacity='0', visibility='collapse')
rule('.GPic', background_size='100% 100%', background_repeat='no-repeat')
for p in PARTS['parts']: rule('.GPic.stP%s' % p['key'], background_image=url('p/%s.png' % p['key']))
rule('.GScroll', background_color='#10224a')
rule('.GThumb', background_color=GCY, opacity='0')
rule('.GThumb.stOn', opacity='1')
SCROLL_H = GROWS * ROWP - 4
for k in range(11): rule('.GThumb.stS%d' % k, transform='translatey(%dpx)' % round((SCROLL_H - 56) * k / 10))
rule('.GBtn', background_color='#1b1060f0', border='2px solid #5a3ad0')
rule('.GBtn:hover', background_color='#34209cf0')
rule('.GUp', background_color='#09112aea', border='2px solid #12284a')
rule('.GUp:hover', background_color='#13306ceb')
rule('.GUp.stSel', background_color='#14327aec', border='2px solid ' + GCY)
rule('.GPage.stCol2 .GUp.stSel', border='2px solid ' + GMG)
tint('.GUp.stPoor .GUCost', 'Danger'); tint('.GUp.stMax .GUCost', 'Ok'); tint('.GUp.stDis .GUCost', 'Dim')
rule('.GUp.stMax .GArrow', opacity='0'); rule('.GUp.stMax .GUNext', opacity='0')
rule('.UpBar', background_color=TRACK); rule('.UpTick', background_color='#09112a')
rule('.GArrow', border_right='2px solid ' + GCY, border_bottom='2px solid ' + GCY, transform='rotatez(-45deg)')
rule('.GsBar.stOver .GsFill', background_color=PAL['Danger'])
rule('.GEq4', background_color='#0a1230d8', border='1px solid #12284a')
tint('.GEq4.stEmpty', 'Dim', True); rule('.GEq4.stEmpty .GPic', opacity='0.25')
rule('.GConf', background_color='#2a0a3af4', border='2px solid ' + GMG, opacity='0', visibility='collapse')
rule('.GConf.stOn', opacity='1', visibility='visible')
rule('.GOk', background_color='#0b5a3af0', border='2px solid ' + PAL['Ok']); rule('.GOk:hover', background_color='#14905af0')
rule('.GNo', background_color='#5a1020f0', border='2px solid ' + PAL['Danger']); rule('.GNo:hover', background_color='#a02038f0')

gk = []
# ---- top bars: credits and K/D/A (left), the sortie map and rank / loadout slot (right); 336 wide each so they end before CS2's team counter at 4:3
def cell(cap, var, x, w, color='Text', maxlen=16, size='S'):
    return [slbl(cap, '', w, 18, 'XS', 'Dim', x=x, y=2), lbl(var, '', w, 26, size, color, x=x, y=19, maxlen=maxlen)]
gk.append(P(None, 'GP ' + pl(w=336, h=50, x=20, y=8), [P(None, 'BrM ' + pl(w=5, h=50, x=0, y=0))]
            + cell('CREDITS', 'gcred', 14, 184, 'Gold', 16) + cell('K / D / A', 'gkda', 212, 116, 'Text', 12)
            + [P(None, 'GSep ' + pl(w=2, h=34, x=204, y=8))] + corners(334, 48)))
gk.append(P(None, 'GP ' + pl(w=336, h=50, right=20, y=8), [P(None, 'BrM ' + pl(w=5, h=50, x=0, y=0))]
            + cell('SORTIE MAP', 'gmap', 14, 150, 'Cy', 14) + cell('RANK / SLOT', 'grank', 176, 152, 'Cy', 16)
            + [P(None, 'GSep ' + pl(w=2, h=34, x=168, y=8))] + corners(334, 48)))

# ---- left: tabs, list (8 rows), tips
LK = [lbl('glist', '', 270, 20, 'XS', 'Dim', 'right', x=140, y=11, maxlen=30)]
for i in range(len(TABS)):
    pid = 'ifr_gc%d' % i
    reg(pid, ['stSel', 'stOff'], prio=3)
    r, c = (0, i) if i < 5 else (1, i - 5)
    LK.append(btn(pid, 'GCat ' + pl(w=104, h=26, x=10 + c * 106, y=32 + r * 30), [lbl('gcn%d' % i, '', 104, 22, 'XS', 'Dim', 'center', x=0, y=2, maxlen=10)]))
LK.append(btn('ifr_gup', 'GBtn ' + pl(w=38, h=18, x=444, y=3), [slbl('UP', '', 38, 18, 'XS', 'Text', 'center', x=0, y=0)]))
LK.append(btn('ifr_gdn', 'GBtn ' + pl(w=38, h=18, x=490, y=3), [slbl('DN', '', 38, 18, 'XS', 'Text', 'center', x=0, y=0)]))
for i in range(GROWS):
    pid = 'ifr_gr%d' % i
    reg(pid, ['stSel', 'stOwned', 'stLocked', 'stEquip', 'stBuy', 'stPoor', 'stOff'], prio=3)
    reg('ifr_grp%d' % i, ['stP%s' % p['key'] for p in PARTS['parts']], prio=3)
    LK.append(btn(pid, 'GRow ' + pl(w=514, h=ROWP - 4, x=10, y=100 + i * ROWP), [
        P(None, 'GEq ' + pl(w=4, h=40, x=3, y=3)),
        P('ifr_grp%d' % i, 'GPic ' + pl(w=42, h=42, x=12, y=2)),
        lbl('gr%dn' % i, 'GName', 270, 24, 'S', 'Text', x=62, y=0, maxlen=22),
        lbl('gr%dt' % i, 'GType', 270, 20, 'XS', 'Dim', x=62, y=25, maxlen=34),
        lbl('gr%dc' % i, 'GCost', 170, 24, 'S', 'Text', 'right', x=336, y=0, maxlen=14),
        lbl('gr%dr' % i, 'GSub', 170, 20, 'XS', 'Dim', 'right', x=336, y=25, maxlen=18)]))
reg('ifr_gthumb', ['stOn'] + ['stS%d' % k for k in range(11)], prio=3)
LK.append(P(None, 'GScroll ' + pl(w=6, h=SCROLL_H, x=536, y=100)))
LK.append(P('ifr_gthumb', 'GThumb ' + pl(w=6, h=56, x=536, y=100)))
TIPY = 100 + GROWS * ROWP + 2
LK.append(lbl('gtip', '', 520, 20, 'XS', 'Dim', x=14, y=TIPY, maxlen=60))
LK.append(lbl('gtip2', '', 520, 20, 'XS', 'Dim', x=14, y=TIPY + 20, maxlen=60))
ARM_H = TIPY + 46
_at = F.METRICS['XS'].text_w('ARMORY')
gk.append(P(None, 'GArm ' + pl(w=548, h=ARM_H + 15, x=20, y=70), [P(None, 'GP ' + pl(w=544, h=ARM_H, x=0, y=11), LK + corners(544, ARM_H) + [P(None, 'InGlow ' + pl(w=536, h=ARM_H - 8, x=2, y=2))]),
            P(None, 'LgBg ' + pl(w=_at + 20, h=6, x=14, y=9)), slbl('ARMORY', '', _at + 4, 22, 'XS', 'Cy', x=24, y=1)]))

# ---- left, under the armory: the equipped weapons (slot, picture, name, key figures)
EK = []
for i, tag in enumerate(['M1', 'M2', 'R', 'E']):          # the slot by the key that fires it (R arm, L arm, R shoulder, L shoulder), as on the fight HUD
    pid = 'ifr_ge%d' % i
    reg(pid, ['stEmpty'], prio=3)
    reg('ifr_gep%d' % i, ['stP%s' % p['key'] for p in PARTS['parts'] if p['kind'] in ('arm', 'shoulder')], prio=3)
    EK.append(P(pid, 'GEq4 ' + pl(w=528, h=23, x=6, y=10 + i * 25), [
        slbl(tag, '', 34, 20, 'XS', 'Cy', 'center', x=2, y=1),
        P('ifr_gep%d' % i, 'GPic ' + pl(w=22, h=22, x=40, y=0)),
        lbl('ge%dn' % i, '', 126, 22, 'XS', 'Text', x=66, y=0, maxlen=11),
        lbl('ge%ds' % i, '', 330, 22, 'XS', 'Dim', 'right', x=194, y=0, maxlen=34)]))
EQ_Y = 70 + 15 + ARM_H + 22
gk.append(gpanel(20, EQ_Y, 548, 118, 'EQUIPPED WEAPONS', EK))

# ---- right: upgrade tracks of the equipped parts, then the item information
RK = [lbl('gutitle', '', 214, 20, 'XS', 'Dim', 'right', x=200, y=10, maxlen=22)]
for i in range(GTRACKS):
    pid = 'ifr_ur%d' % i
    reg(pid, ['stSel', 'stOff', 'stMax', 'stPoor', 'stDis'], prio=3)
    ticks = [P(None, 'UpTick ' + pl(w=2, h=8, x=8 + 18 * j, y=47)) for j in range(1, 5)]
    RK.append(btn(pid, 'GUp ' + pl(w=406, h=60, x=10, y=34 + i * 64), [
        lbl('ur%dn' % i, 'GUName', 252, 22, 'S', 'Text', x=8, y=0, maxlen=22),
        lbl('ur%dc' % i, 'GUCost', 122, 22, 'S', 'Gold', 'right', x=274, y=0, maxlen=12),
        lbl('ur%ds' % i, 'GSub', 390, 20, 'XS', 'Dim', x=8, y=21, maxlen=46),
        ladder('u%d' % i, 'UpFill', 'UpBar', 90, 8, 5, color=GCY, x=8, y=47)] + ticks + [
        lbl('ur%dl' % i, '', 40, 20, 'XS', 'Dim', x=104, y=40, maxlen=6),
        lbl('ur%da' % i, '', 112, 20, 'XS', 'Text', 'right', x=146, y=40, maxlen=12),
        P(None, 'GArrow ' + pl(w=8, h=8, x=264, y=44)),
        lbl('ur%db' % i, 'GUNext', 112, 20, 'XS', 'Ok', x=278, y=40, maxlen=12)]))
gk.append(gpanel(0, 207, 430, 552, 'UPGRADE TRACKS', RK, right=20))
IK = [lbl('gpn', '', 420, 26, 'M', 'Text', x=3, y=20, maxlen=22),
      lbl('gpt', '', 420, 20, 'XS', 'Cy', x=3, y=48, maxlen=56),
      lbl('gpd', '', 420, 20, 'XS', 'Dim', x=3, y=66, maxlen=56),
      lbl('gpd2', '', 420, 20, 'XS', 'Dim', x=3, y=84, maxlen=56),
      lbl('gpd3', '', 420, 20, 'XS', 'Dim', x=3, y=102, maxlen=56),
      lbl('gpk', '', 420, 20, 'XS', 'Text', x=3, y=124, maxlen=56),
      lbl('gcmp', '', 420, 20, 'XS', 'Warn', x=3, y=142, maxlen=56),
      lbl('ghint', '', 420, 20, 'XS', 'Gold', x=3, y=162, maxlen=56),          # the garage's answer line: two rows (10 Nov 2026 evening: 'Welcome back: pick a
      lbl('ghint2', '', 420, 20, 'XS', 'Gold', x=3, y=182, maxlen=56)]         # loadout and SORTIE' and other replies were wider than one row and got cut)
gk.append(gpanel(0, 778, 430, 214, 'ITEM INFORMATION', IK, right=20))

# ---- centre column: what the bay shows, the confirm bar, the key legend, the frame statistics of the draft loadout
CW = 400
CEN = [lbl('gbay', '', CW, 26, 'S', 'Cy', 'center', x=0, y=80, maxlen=30),
       lbl('gbay2', '', CW, 20, 'XS', 'Dim', 'center', x=0, y=108, maxlen=40)]
reg('ifr_gcbar', ['stOn'], prio=3)
CEN.append(P('ifr_gcbar', 'GConf ' + pl(w=CW - 4, h=124, x=0, y=596), [
    lbl('gconf', '', CW - 24, 24, 'S', 'Warn', 'center', x=10, y=4, maxlen=30),
    lbl('gconfb', '', CW - 24, 24, 'S', 'Warn', 'center', x=10, y=28, maxlen=30),
    lbl('gconf2', '', CW - 24, 20, 'XS', 'Dim', 'center', x=10, y=56, maxlen=44),
    btn('ifr_gcy', 'GOk ' + pl(w=166, h=32, x=20, y=82), [slbl('CONFIRM', '', 166, 26, 'XS', 'Ok', 'center', x=0, y=3)]),
    btn('ifr_gcx', 'GNo ' + pl(w=166, h=32, x=206, y=82), [slbl('CANCEL', '', 166, 26, 'XS', 'Danger', 'center', x=0, y=3)])]))
CEN.append(lbl('glegend', '', CW, 20, 'XS', 'Dim', 'center', x=0, y=732, maxlen=48))
CEN.append(lbl('glegend2', '', CW, 20, 'XS', 'Dim', 'center', x=0, y=752, maxlen=48))
GSTATS = ['AP', 'WGT', 'EN', 'SPD', 'BST', 'QB', 'LOCK']
GSKEYS = ['ap', 'weight', 'en', 'speed', 'boost', 'qb', 'lock']
CELLS_AT = {0: (8, 32), 1: (8, 66), 2: (8, 100), 6: (8, 134), 3: (202, 32), 4: (202, 66), 5: (202, 100)}
FK = [lbl('gfn', '', 200, 22, 'XS', 'Text', x=8, y=10, maxlen=16), lbl('gft', '', 178, 20, 'XS', 'Dim', 'right', x=210, y=10, maxlen=14)]
for i, nm in enumerate(GSTATS):
    cx, cy = CELLS_AT[i]
    FK.append(slbl(nm, '', 50, 18, 'XS', 'Dim', x=cx, y=cy + 2))
    bar = ladder('gs%d' % i, 'GsFill', 'GsBar', 184, 6, 20, color=GCY, x=cx, y=cy + 24)
    if i in (1, 2):
        bar = bar.replace('<Panel class="GsBar', '<Panel id="ifr_gsb%d" class="GsBar' % i, 1)
        reg('ifr_gsb%d' % i, ['stOver'], prio=3)
    FK.append(bar)
    FK.append(lbl('gs%dv' % i, '', 132, 20, 'XS', 'Text', 'right', x=cx + 52, y=cy + 2, maxlen=13))
FK.append(lbl('gwarn', '', 186, 22, 'XS', 'Danger', x=202, y=134, maxlen=22))
CEN.append(gpanel(0, 790, CW, 170, 'FRAME', FK))
gk.append(P(None, 'GCen ' + pl(w=CW, h=1000, center=True, y=0), CEN))
# the turn buttons under the mech's feet (10 Nov 2026 evening playtest): the hangar camera keeps the feet at y ~672 (60_garage.js GARAGE_FEET_Y), these
# sit just below, centred on the screen like the mech. A click turns 45 degrees (eased); E / R held turn it too; FRONT faces the camera again.
# stOff hides them while the confirm bar is up (it covers this strip).
rule('.GRot', opacity='1'); rule('.GRot.stOff', opacity='0', visibility='collapse')
reg('ifr_grot', ['stOff'], prio=3)
GRL, GRF = 76, 100            # narrow: at 4:3 the left column ends at x 568 and the mech stands at 720, so the row must stay within +-144 of the centre
gk.append(P('ifr_grot', 'GRot ' + pl(w=2 * GRL + GRF + 16, h=34, center=True, y=686), [
    btn('ifr_grl', 'GBtn ' + pl(w=GRL - 4, h=30, x=0, y=0), [slbl('<  E', '', GRL - 4, 26, 'XS', 'Text', 'center', x=0, y=2)]),
    btn('ifr_grf', 'GBtn ' + pl(w=GRF - 4, h=30, x=GRL + 8, y=0), [slbl('FRONT', '', GRF - 4, 26, 'XS', 'Cy', 'center', x=0, y=2)]),
    btn('ifr_grr', 'GBtn ' + pl(w=GRL - 4, h=30, x=GRL + GRF + 16, y=0), [slbl('R  >', '', GRL - 4, 26, 'XS', 'Text', 'center', x=0, y=2)])]))
rule('.GRoot', width='100%', height='1080px')
rule('.GCen', transform='translatex(60px)')
# the focus column classes (stCol0..2) sit on the garage root so the list and the tracks both see them
reg('ifr_gpage', ['stCol0', 'stCol1', 'stCol2'], prio=3)
garage = P('ifr_gpage', 'Garage GRoot GPage', gk)

# ================================================================ pictures, preload, document
n_img = hud_images.write(IMG_DIR, PARTS['parts'], os.path.join(PROJ, 'preview', 'frames'))
# threat chevrons per kind and point markers per owner
for d in range(8):
    for kind, col in (('lock', (255, 194, 71, 255)), ('launch', (255, 90, 70, 255)), ('close', (232, 240, 246, 255))):
        hud_images.chevron(64, d * 45, col).save(os.path.join(IMG_DIR, 'th%d_%s.png' % (d, kind))); n_img += 1
for L in 'ABC':
    for own, col in (('n', (200, 210, 220, 255)), ('t', (255, 176, 74, 255)), ('ct', (95, 211, 255, 255))):
        im = hud_images.point_marker(L, 28)
        px_ = im.load()
        for yy in range(im.height):
            for xx in range(im.width):
                r, g, b, a = px_[xx, yy]
                if a and r > 128: px_[xx, yy] = col[:3] + (a,)
        im.save(os.path.join(IMG_DIR, 'pt_%s_%s.png' % (L, own))); n_img += 1
# loading slides / radar / icon are compiled with the HUD only when they already exist (a missing url breaks the css compile)
slides = [n for n in range(10) if os.path.exists(os.path.join(OUT, 'panorama/images/map_icons/screenshots/1080p/%s%s.png' % (MAP, '_%d' % n if n else '')))]
pre = ''
if len(slides) >= 1:
    pre = h.preload(MAP, slides=len(slides), radar=os.path.exists(os.path.join(OUT, 'panorama/images/overheadmaps/%s_radar.psd' % MAP)),
                    icon=os.path.exists(os.path.join(OUT, 'panorama/images/map_icons/map_icon_%s.svg' % MAP)))
else:
    print('hud: no loading slides in %s yet; nothing preloaded (re-run hud.py after loading.py)' % OUT)

screen = P(None, 'Screen', [pre, vitals, buffs, reticle, lockroot, radar, pilot, streakp, ident, mode, objt, cap, badges, kill, line, loadc, ctrl, helpc, intro, death, podium, board, spec, garage])
root = P('ifr_root', 'IfrRoot', [screen])
# neon type: css per size / glyph class (proportional widths), colour pictures, team accent and state tints
def rgb(k): return tuple(int(PAL[k][i:i + 2], 16) for i in (1, 3, 5))
for _mk in list(GLYPH_COLORS):
    if 'Acc' in GLYPH_COLORS[_mk]: GLYPH_COLORS[_mk].update(('T', 'CT'))      # the team accent glow
GLYPH_COLORS.setdefault('c28', set()).update(('T', 'CT'))
sheets = {mk: {k: rgb(k) for k in sorted(ks)} for mk, ks in GLYPH_COLORS.items()}
n_glyph_png = F.write_sheet(IMG_DIR, sheets)
for _v in sorted(NEGY): rule('.Ny%d' % _v, transform='translatey(-%dpx)' % _v)
rule('.Txt', flow_children='right', overflow='noclip noclip'); rule('.Dy', overflow='noclip noclip'); rule('.Sl', overflow='noclip noclip')
rule('.G', width='0px', background_size='100% 100%', background_repeat='no-repeat')
# Labels (dynamic text): Noto Serif Bold capitals, one rule per size / colour / alignment. The shadow is a tight DARK contour, not a glow
# in the text's own colour: the 6 px same-colour glow of the first Label build smeared the letter edges (skink52, 10 Nov 2026: "text
# becomes a little hard to read"; white on white at 20 px). Panorama takes one text-shadow, so it is contrast or glow, not both.
def glow(col): return '0px 0px 3px 3.0 #000000f0'
rule('.Tx', font_family=F.LABEL_CSS_FAMILY, font_weight='bold', text_transform='uppercase', white_space='nowrap', color=PAL['Text'], text_shadow=glow(PAL['Text']))
for sz in F.SIZE_ORDER: rule('.Tx.s%s' % sz, font_size='%dpx' % F.LMETRICS[sz].px)
for al, v in (('L', 'left'), ('C', 'center'), ('R', 'right')): rule('.Tx.Al%s' % al, text_align=v)
for k in sorted(LCOLORS): rule('.Tx.c%s' % k, color=PAL[k], text_shadow=glow(PAL[k]))
if 'Acc' in LCOLORS:
    for tc in ('T', 'CT'): rule('.IfrRoot.stTeam%s .Tx.cAcc' % tc, color=PAL[tc], text_shadow=glow(PAL[tc]))
for sel, col in LTINTS: rule('%s .Tx' % sel, color=PAL[col], text_shadow=glow(PAL[col]))
for sz in F.SIZE_ORDER:
    M = F.METRICS[sz]
    rule('.s%s .G' % sz, height='%dpx' % M.h)
    for c in [32] + F.CHARS: rule('.s%s .G.g%d' % (sz, c), width='%dpx' % (M.adv[c] + 2 * M.pad), margin_left='%dpx' % -M.pad, margin_right='%dpx' % -M.pad)
MCLS = {'c28': '', 'b28': '.Bt', 'b56': '.Big'}          # row class that picks the master (crisp, bright, bright big)
for mk, cols in sheets.items():
    for k in cols:
        for c in F.CHARS:
            rule('%s.c%s .G.g%d' % (MCLS[mk], k, c) if MCLS[mk] else '.c%s .G.g%d' % (k, c), background_image=url('f/%s_%s_%d.png' % (mk, k, c)))
for c in F.CHARS:
    for mk in sheets:
        for tc in ('T', 'CT'):
            if tc in sheets[mk] and 'Acc' in sheets[mk]: rule('.IfrRoot.stTeam%s .Txt%s.cAcc .G.g%d' % (tc, MCLS[mk], c), background_image=url('f/%s_%s_%d.png' % (mk, tc, c)))
    for sel, col in TINTS:
        rule('%s .G.g%d' % (sel, c), background_image=url('f/c28_%s_%d.png' % (col, c)))
        rule('%s.Bt .G.g%d' % (sel, c), background_image=url('f/b28_%s_%d.png' % (col, c)))
from PIL import Image as _Im
for sw, hh in sorted(SEG_DIMS):                      # segment overlay: a gap of 2 px at the end of each step, drawn over the fill
    im = _Im.new('RGBA', (sw, hh), (0, 0, 0, 0))
    for x in range(sw - 2, sw):
        for y in range(hh): im.putpixel((x, y), (6, 9, 13, 255))
    im.save(os.path.join(IMG_DIR, 'seg%dx%d.png' % (sw, hh)))
    rule('.Seg%dx%d' % (sw, hh), background_image=url('seg%dx%d.png' % (sw, hh)), background_repeat='repeat-x', background_size='%dpx %dpx' % (sw, hh))
# gradient guard: Panorama crashes above 11 stops (Dogfight, 8 Oct 2026)
for c in h.css:
    for g in re.findall(r'gradient\([^;]*', c):
        assert g.count('color-stop') + g.count('from(') + g.count('to(') <= 11, 'gradient with more than 11 stops: ' + g[:80]
xp, cp = h.write(OUT, NAME, root, dynamic=r'^st[A-Z]\w*$', wrap_cls='IfrWrap')

# ---------------------------------------------------------------- hud.json (the driver's contract) and the check states
def compact(v):
    """a panel's contract entry: plain classes plus ranges [prefix, lo, hi] for stG0..575 and stL0..n (the driver expands them)"""
    cls, ranges = set(v['classes']), []
    for pre in ('stG', 'stL', 'stX', 'stY'):
        nums = sorted(int(c[len(pre):]) for c in cls if re.match(r'^%s\d+$' % pre, c))
        if nums and nums == list(range(nums[0], nums[-1] + 1)) and len(nums) > 3:
            ranges.append([pre, nums[0], nums[-1]])
            cls = set(c for c in cls if not re.match(r'^%s\d+$' % pre, c))
    e = {'classes': sorted(cls), 'vars': sorted(v['vars']), 'prio': v['prio'], 'screen': v['screen']}
    if ranges: e['ranges'] = ranges
    return e


# the id budget: what the script can reference, per screen
IDS = {}
for _k, _v in PANELS.items(): IDS[_v['screen']] = IDS.get(_v['screen'], 0) + 1
IDS_TOTAL = len(PANELS)
hud = {
    'ids': {'total': IDS_TOTAL, 'budget': ID_BUDGET, 'cap': ID_CAP, 'screens': IDS},
    'layout': 'panorama/layout/custom_game/%s.vxml' % NAME, 'name': NAME, 'root': 'ifr_root', 'budget': 900,
    'panels': {k: compact(v) for k, v in sorted(PANELS.items())},
    'ladders': LADDERS, 'text_slots': TEXT,
    'screens': {'fight': ['stFight'], 'spec': ['stSpec'], 'death': ['stDeath'], 'intro': ['stIntro'], 'podium': ['stPodium'], 'garage': ['stGarage'], 'off': []},
    'weapons': WEAPONS, 'families': FAMS, 'radar': {'cells': CELLS, 'dots': DOTS, 'size': RS},
    'short': SHORT, 'glyphs': {'prefix': 'g', 'spu': SPU, 'font': os.path.basename(F.FONT_PATH), 'trunc': [list(t) for t in TRUNC],
                'label': F.LABEL_FAMILY, 'w': {sz: {str(c): F.LMETRICS[sz].adv[c] for c in F.LABEL_CHARS} for sz in F.SIZE_ORDER}}, 'garage': {'cats': CATS, 'rows': GROWS, 'tracks': GTRACKS, 'stats': GSKEYS, 'parts': [p['key'] for p in PARTS['parts']]},
    'cone_steps': 5, 'threat_dirs': 8,
    'lockgrid': {'step': LKS, 'x': LKXN, 'y': LKYN, 'marks': ML_N, 'allies': FR_N}, 'line': {'rows': LINE_ROWS, 'slots': ['line'] + ['line%d' % k for k in range(2, LINE_ROWS + 1)]}, 'streak_pips': SPIP,
}
os.makedirs(os.path.join(OUT, '_gen'), exist_ok=True)
json.dump(hud, open(os.path.join(OUT, '_gen', 'hud.json'), 'w', encoding='utf-8'), indent=0, sort_keys=True)

# states for hud_check (every screen): root classes, texts, a few ladders and radar dots
STATE_CUTS = []
def T(**kw):
    """text for the check states, as the driver shows it: cut by cells and box width, aligned with a spacer class, glyph classes per cell"""
    out = {}
    for k, v in kw.items():
        row = TEXTROW.get(k)
        assert row, 'not a text slot panel: ' + k
        rid, al, n, gs, w = row
        t, used = cut_text(v, F.LMETRICS[gs], w, n)
        if t != v.upper().rstrip(): STATE_CUTS.append('%s (%d px): %r -> %r' % (k, w, v, t))
        out[rid] = {'text': t}
    return out
def A(**kw): return {k: {'add': v if isinstance(v, list) else [v]} for k, v in kw.items()}
def merge(*ds):
    out = {}
    for d in ds:
        for k, v in d.items():
            if k.startswith('_'): out[k] = v
            else: out.setdefault(k, {}).update(v)
    return out
fight_common = merge(
    A(ifr_root=['stOn', 'stFight', 'stTeamT'], ifr_l_ap='stL14', ifr_l_en='stL9', ifr_l_stg='stL6', ifr_qb='stL3', ifr_boost='stOn', ifr_cone='stC2', ifr_l_od='stL20', ifr_odready='stOn', ifr_bf_dmg='stOn', ifr_bf_shield='stOn', ifr_bf_ace='stOn', ifr_bf_radar='stOn', ifr_bf_arty='stOn',
      ifr_w0i='stWrifle', ifr_w1i='stWshotgun', ifr_w2i='stWvm6', ifr_w3i='stWdecoy', ifr_w0='stSel', ifr_l_w0m='stL16', ifr_l_w1m='stL10', ifr_l_w2c='stL8', ifr_l_w3m='stL20',
      ifr_w1='stReload', ifr_w2='stLkNo', ifr_mtag='stMtb', ifr_xp='stOn', ifr_rookie='stOn', ifr_l_skp='stL2', ifr_load='stOn', ifr_ctrl='stOn', ifr_help='stOn',
      ifr_lci0='stWrifle', ifr_lci1='stWshotgun', ifr_lci2='stWvm6', ifr_lci3='stWdecoy',
      ifr_rdDa='stG555', ifr_rdDe='stG20', ifr_line=['stOn', 'stHi', 'stR2'], ifr_kill='stOn', ifr_hit='stPop', ifr_hitH='stPop2', ifr_hitK='stPop',
      **{'ifr_rd%d' % i: ['stG%d' % ((i * 37 + 11) % 576), 'stE' if i % 3 else 'stA'] + (['stBig'] if i == 5 else ['stTgt'] if i == 7 else []) for i in range(18)}),
    T(ifr_bfdmg='12 S LEFT', ifr_bfshield='8 S LEFT', ifr_bface='20 S: OVERDRIVE REFILLS', ifr_bfradar='10 S: ENEMIES ON RADAR', ifr_bfarty='READY: LOCK A TARGET', ifr_ap='6 420', ifr_apmax='/ 9000', ifr_en='2 850',
      ifr_w0n='AR-22', ifr_w0a='24 / 300', ifr_w1n='SG-SCAT', ifr_w1a='0 / 72', ifr_w2n='VM-6', ifr_w2a='72', ifr_w2s='NO LOCK: UNGUIDED', ifr_w0s='', ifr_w1s='RELOAD 1.5 S',
      ifr_w3n='DC-CHAFF', ifr_w3a='2', ifr_mode='TDM', ifr_sub='TEAM DEATHMATCH   FIRST TO 60 KILLS', ifr_scoreT='42', ifr_scoreCT='38', ifr_clock='6:42', ifr_xpv='+40 XP',
      ifr_odp='100 %', ifr_odl='READY: HOLD R+E TOGETHER', ifr_pmy='42', ifr_pen='38', ifr_pk='12', ifr_pd='3', ifr_pa='4', ifr_stk='2', ifr_str='NEXT: 3 KILLS = RADAR PING', ifr_str2='ENEMIES ON RADAR FOR 10 S',
      ifr_lcf='WHITE GLINT', ifr_lc0n='AR-22', ifr_lc0r='MID RANGE', ifr_lc1n='SG-SCAT', ifr_lc1r='CLOSE RANGE', ifr_lc2n='VM-6', ifr_lc2r='LOCK-ON MISSILES', ifr_lc3n='DC-CHAFF', ifr_lc3r='BREAKS LOCKS',
      ifr_lct='SECOND WIND: PASSIVE', ifr_lct2='EN REGEN +40 % AFTER A QUICK BOOST',
      ifr_rrange='6000', ifr_linea='OVERDRIVE READY: HOLD R + E TOGETHER', ifr_lineb='A BLAST AROUND YOU: 2 500 DAMAGE', ifr_killv='DESTROYED   PILOT_SEVEN'))
# the objective HUD per mode: Conquest with B being taken by CT (capture strip on), CTF with the enemy flag carried, KOTH contested
fight_cq = merge(fight_common,
    A(ifr_mtag=['stMcq'], ifr_obj='stOn', ifr_ob0=['stOn', 'stT'], ifr_ob1=['stOn', 'stCT'], ifr_ob2=['stOn', 'stCT'], ifr_obk0='stOwnT', ifr_obk1='stCap', ifr_obk2='stOwnCT',
      ifr_l_ob0p='stL20', ifr_l_ob1p='stL13', ifr_l_ob2p='stL20', ifr_cap=['stOn', 'stCT'], ifr_l_capbar='stL26',
      ifr_rdA='stG60', ifr_rdB='stG300', ifr_rdC='stG540'),
    T(ifr_mode='CONQUEST', ifr_sub='TICKETS   HOLD A B C TO DRAIN THE ENEMY', ifr_scoreT='212', ifr_scoreCT='178', ifr_ob0k='A', ifr_ob1k='B', ifr_ob2k='C',
      ifr_ob0t='T HOLDS', ifr_ob1t='CT 64 %', ifr_ob2t='CT HOLDS', ifr_capl='CT CAPTURING B   64 %'))
fight_ctf = merge(fight_common,
    A(ifr_mtag=['stMctf'], ifr_obj='stOn', ifr_ob0=['stOn', 'stCT'], ifr_ob2=['stOn', 'stT'], ifr_obk0='stOwnT', ifr_obk2='stOwnCT',
      ifr_l_ob0p='stL12', ifr_l_ob2p='stL7', ifr_cap=['stOn', 'stT'], ifr_l_capbar='stL24'),
    T(ifr_mode='CTF', ifr_sub='CAPTURE THE FLAG   3 CAPTURES WIN', ifr_scoreT='1', ifr_scoreCT='2', ifr_ob0k='T', ifr_ob2k='CT',
      ifr_ob0t='TAKEN 60 %', ifr_ob2t='DROP 12 S', ifr_capl='FLAG IN HAND  60 % HOME'))
fight_kh = merge(fight_common,
    A(ifr_mtag=['stMkh'], ifr_obj='stOn', ifr_ob1=['stOn', 'stCont'], ifr_obk1=['stOwnT', 'stCap'], ifr_l_ob1p='stL20', ifr_cap=['stOn', 'stCont'], ifr_l_capbar='stL40'),
    T(ifr_mode='KOTH', ifr_sub='KING OF THE HILL   FIRST TO 150   MOVES 1:12', ifr_scoreT='88', ifr_scoreCT='61', ifr_ob1k='B', ifr_ob1t='CONTESTED', ifr_capl='HILL B CONTESTED'))

def garage_state():
    """a full garage screen: the list rows (every state), 8 upgrade tracks, the confirm bar, long texts"""
    arms = [q for q in PARTS['parts'] if q['kind'] == 'arm']
    st = ['stEquip', 'stOwned', 'stBuy', 'stPoor', 'stLocked', 'stBuy', 'stOwned', 'stBuy', 'stLocked', 'stOwned']
    cls, txt = {'ifr_root': ['stOn', 'stGarage', 'stTeamT'], 'ifr_gpage': ['stCol1'], 'ifr_gc1': ['stSel'], 'ifr_gr2': ['stSel', 'stBuy'],
                'ifr_gthumb': ['stOn', 'stS3'], 'ifr_gcbar': ['stOn'], 'ifr_grot': ['stOff'], 'ifr_ge3': ['stEmpty'], 'ifr_gsb2': ['stOver'], 'ifr_ur1': ['stSel', 'stPoor'], 'ifr_ur7': ['stMax']}, {}
    for i in range(GROWS):
        q = arms[i]
        cls.setdefault('ifr_gr%d' % i, [])
        cls['ifr_gr%d' % i] = sorted(set(cls['ifr_gr%d' % i] + [st[i]]))
        cls['ifr_grp%d' % i] = ['stP' + q['key']]
        txt.update({'ifr_gr%dn' % i: q['name'].upper() + ' +3', 'ifr_gr%dt' % i: 'ARM / PROJECTILE', 'ifr_gr%dc' % i: '12 000 CR' if st[i] in ('stBuy', 'stPoor') else 'EQUIPPED' if st[i] == 'stEquip' else 'OWNED' if st[i] == 'stOwned' else 'R10 NEEDED',
                    'ifr_gr%dr' % i: 'R+L ARM' if st[i] == 'stEquip' else 'NEED CREDITS' if st[i] == 'stPoor' else 'LOCKED' if st[i] == 'stLocked' else 'RANK 10'})
    for i, name in enumerate(TABS): txt['ifr_gcn%d' % i] = name
    for i in range(GTRACKS):
        cls['ifr_l_u%d' % i] = ['stL%d' % (i % 6)]
        txt.update({'ifr_ur%dn' % i: 'R SHLD DAMAGE', 'ifr_ur%dc' % i: '12 000 CR' if i != 7 else 'MAX', 'ifr_ur%ds' % i: 'VM-12 STORM  +2 % / LV', 'ifr_ur%dl' % i: '%d/5' % (i % 6),
                    'ifr_ur%da' % i: '15 000 x6', 'ifr_ur%db' % i: '15 450 x6'})
    for i in range(7): cls['ifr_l_gs%d' % i] = ['stL%d' % (6 + 2 * i)]
    eq = [('AR-22 +2', 'DMG 157  7/S  30/300'), ('SG-SCAT', 'DMG 112x12  1.1/S  8/80'), ('VM-6', 'DMG 470x6  CD 5S  AMMO 72'), ('EMPTY', '')]
    for i in range(4):
        if i < 3: cls['ifr_gep%d' % i] = ['stP' + ('rifle', 'shotgun', 'vm6')[i]]
        txt.update({'ifr_ge%dn' % i: eq[i][0], 'ifr_ge%ds' % i: eq[i][1]})
    txt.update({'ifr_gmap': 'DUNES', 'ifr_gcred': '1 250 000 CR', 'ifr_gkda': '11 / 3 / 4', 'ifr_grank': 'R12 / SLOT 1',
                'ifr_glist': 'ROWS 1 - 8 OF 66', 'ifr_gtip': 'SPACE EQUIPS R, THEN L IN TURN', 'ifr_gtip2': 'F UPGRADES   D OPENS THE TRACKS',
                'ifr_gbay': 'WHITE GLINT', 'ifr_gbay2': 'BAY 3   E / R TURN', 'ifr_gconf': 'BUY PB-MOONLIGHT', 'ifr_gconfb': 'FOR 12 000 CR?', 'ifr_gconf2': 'SPACE CONFIRM / CTRL CANCEL',
                'ifr_gutitle': 'COST BASE X (LV+1)', 'ifr_gfn': 'WHITE GLINT', 'ifr_gft': 'MEDIUM BIPED', 'ifr_gwarn': 'EN OVER x0.96',
                'ifr_gpn': 'PB-MOONLIGHT', 'ifr_gpt': 'ARM / MELEE  RANK 10  12 000 CR', 'ifr_gpd': 'Laser blade. Lunges in to strike', 'ifr_gpd2': 'for huge damage; costs EN.', 'ifr_gpd3': 'EN/SHOT 240  DPS 2 600',
                'ifr_gpk': 'DMG 2600  ROF 1  RNG 600  IMP 1100', 'ifr_gcmp': 'VS R ARM: WT +560  EN +120', 'ifr_ghint': 'RANK 10 NEEDED',
                'ifr_glegend': 'W/S ITEM   SPACE EQUIP   A TABS', 'ifr_glegend2': 'D TRACKS   F UPGRADE   CTRL BACK'})
    for i in range(7): txt['ifr_gs%dv' % i] = '8 000' if i == 6 else '3 920 / 4 600'
    return merge({k: {'add': v} for k, v in cls.items()}, T(**txt))

STATES = {
    'intro': merge(A(ifr_root=['stOn', 'stIntro', 'stTeamCT'], ifr_imbar='stMctf'), T(ifr_arena='DUNES', ifr_imode='CAPTURE THE FLAG', ifr_iobj='TAKE THE ENEMY FLAG TO YOUR OWN FLAG',
                                                                                     ifr_iobj2='WHILE YOURS IS HOME. 3 CAPTURES WIN', ifr_ihint='DROPPING IN 5'), {'_chat_top': 800}),
    'fight': fight_common,
    'fight_cq': fight_cq,
    'fight_ctf': fight_ctf,
    'fight_kh': fight_kh,
    'lock': merge(fight_common, A(ifr_lock='stHard3', ifr_lkx='stX%d' % (LKXN + 9), ifr_lky='stY%d' % (LKYN - 4), ifr_l_tap='stL8', ifr_l_lkp='stL12', ifr_th1='stLock', ifr_th5='stLaunch', ifr_th3='stClose', ifr_mwarn='stOn', ifr_assist='stOn',
                                  ifr_enbar='stStall', ifr_entag='stOn', ifr_stg='stStaggered', ifr_stgring='stOn', ifr_lag='stOn', ifr_shield='stOn',
                                  ifr_ml0='stDone', ifr_ml0x='stX%d' % (LKXN + 14), ifr_ml0y='stY%d' % (LKYN + 2), ifr_ml1='stOn', ifr_ml1x='stX%d' % (LKXN - 5), ifr_ml1y='stY%d' % (LKYN - 6), ifr_fr0='stOn', ifr_fr0x='stX%d' % (LKXN - 16), ifr_fr0y='stY%d' % (LKYN - 3), ifr_fr1='stFar', ifr_fr1x='stX%d' % (LKXN + 22), ifr_fr1y='stY%d' % (LKYN - 1),
                                  ifr_w2=['stLkOn'], ifr_load=[], ifr_ctrl=[], ifr_help=[]),
                  T(ifr_tname='NEXT_ONE', ifr_rng='2 450', ifr_lstate='LOCKED', ifr_w2s='LOCKED: FIRE')),
    'death': merge(A(ifr_root=['stOn', 'stDeath', 'stTeamT'], ifr_line=['stOn', 'stR1'], ifr_mtag='stMcq', ifr_ctrl='stOn'), T(ifr_killer='PILOT_SEVEN', ifr_kweapon='VM-6 VERTICAL MISSILES', ifr_kframe='WHITE GLINT', ifr_respawn='RESPAWN IN 6',
                                                                                 ifr_mode='CONQUEST', ifr_sub='TICKETS', ifr_clock='6:30', ifr_scoreT='200', ifr_scoreCT='170', ifr_linea='CTRL OPENS THE GARAGE',
                                                                                 ifr_pmy='200', ifr_pen='170', ifr_pk='12', ifr_pd='4', ifr_pa='4', ifr_stk='0', ifr_str='NEXT: 3 KILLS = RADAR PING', ifr_str2='ENEMIES ON RADAR FOR 10 S')),
    'spec': merge(fight_common, A(ifr_root=['stOn', 'stSpec', 'stTeamT']), T(ifr_spec='WATCHING PILOT_SEVEN   SPACE: NEXT PILOT')),
    'podium': merge(A(ifr_root=['stOn', 'stPodium', 'stTeamCT'], ifr_pc0='stCT', ifr_pc1='stT', ifr_pc2=['stCT', 'stMe']),
                    T(ifr_phead='VICTORY', ifr_psub='CONQUEST   DUNES', ifr_pn0='ACE_OF_DUNES', ifr_ps0='18 KILLS', ifr_pn1='PILOT_SEVEN', ifr_ps1='14 KILLS', ifr_pn2='YOU', ifr_ps2='11 KILLS',
                      ifr_pt0l='PARTICIPATION', ifr_pt0v='+100 XP', ifr_pt1l='KILLS 11', ifr_pt1v='+440 XP', ifr_pt2l='CAPTURES 2', ifr_pt2v='+120 XP', ifr_pt3l='WIN', ifr_pt3v='+300 XP',
                      ifr_pt4l='TOTAL', ifr_pt4v='+1 240 XP   +620 CR', ifr_pt5l='RANK 12', ifr_pt5v='4 180 / 9 760 XP', ifr_pfoot='VOTE: 1 TEAM BATTLE   2 CONQUEST'),
                    {'_chat_top': 800}),
    'garage': merge(garage_state(), {'_chat_top': 800}),
    'garage_turn': merge(garage_state(), A(ifr_gcbar=[], ifr_grot=[]), {'_chat_top': 800}),      # no question up: the turn buttons under the mech's feet
}
# the pilot's identity strip on every fight screen, the top pilots beside the podium (the widest texts the driver writes)
for _k in ('fight', 'fight_cq', 'fight_ctf', 'fight_kh', 'lock', 'spec', 'death'):
    STATES[_k] = merge(STATES[_k], A(ifr_ident='stOn'), T(ifr_ptag='[ACE] ZZ-TOP 99 ZZ', ifr_dly='DAILY 1/3  SORTIE KILLS 7 / 10'))
STATES['podium'] = merge(STATES['podium'], A(ifr_lb='stOn'), T(ifr_lbh='1 234 PILOTS', ifr_lbme='YOU  # 1 234   R20   132K XP',
    **{'ifr_lb%dn' % i: '%d  %s' % (i + 1, n) for i, n in enumerate(('ZZ-TOP 99 ZZ', 'RAVEN 7', 'SKINK52', 'MAVERICK-404', 'PILOT'))},
    **{'ifr_lb%dv' % i: v for i, v in enumerate(('R50  1.27M', 'R41  800K', 'R20  132K', 'R2  780', 'R1  0'))}))
for c in sorted(set(STATE_CUTS)): print('hud: check state text does not fit ' + c)
os.makedirs(os.path.join(PROJ, 'build'), exist_ok=True)
json.dump(STATES, open(os.path.join(PROJ, 'build', 'hud_states.json'), 'w', encoding='utf-8'), indent=1)
n_cls = sum(len(v['classes']) for v in PANELS.values())
print('hud %s: panel ids the script can reference: %d of budget %d (CS2 cap %d): %s' % (NAME, IDS_TOTAL, ID_BUDGET, ID_CAP, ', '.join('%s %d' % kv for kv in sorted(IDS.items(), key=lambda kv: -kv[1]))))
_xml_set = set(re.findall(r'\bid="([^"]+)"', open(xp, encoding='utf-8').read()))
for _d in sorted(_xml_set - set(PANELS)): print('hud: id in the layout but not registered (remove the id or reg() it): ' + _d)
for _d in sorted(set(PANELS) - _xml_set): print('hud: registered but not in the layout: ' + _d)
_xml_ids = len(_xml_set)
print('hud %s: ids in the layout xml: %d (every one is referencable by the script: none may exist that is not registered)' % (NAME, _xml_ids))
assert _xml_ids == IDS_TOTAL, 'ids in the xml (%d) != ids registered (%d): a panel has an id the budget does not count' % (_xml_ids, IDS_TOTAL)
if IDS_TOTAL > ID_BUDGET: sys.exit('hud: %d panel ids, over the budget of %d (CS2 stops updating panels past %d ids): use fewer ids (class changes on a parent, one Label per text)' % (IDS_TOTAL, ID_BUDGET, ID_CAP))
print('hud %s: %d panels in the contract, %d switchable classes, %d text slots, %d ladders, %d pictures, %d states -> %s' %
      (NAME, len(PANELS), n_cls, len(TEXT), len(LADDERS), n_img, len(STATES), os.path.join(OUT, '_gen', 'hud.json')))
