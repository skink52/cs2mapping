"""Doom status bar HUD for CS2 Panorama (custom_hud_layout), built from the Freedoom graphics.

The Doom screen (320x200, shown at 4:3) maps to a 1440x1080 panel centred on screen:
one Doom pixel is 4.5 px wide and 5.4 px tall, exactly as Doom stretched its pixels.
"""
import os, sys, json
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import assets, names

OUT = sys.argv[1]
WFRAMES = json.load(open(sys.argv[2]))
SX, SY = 4.5, 5.4
UP = 6
IMG = os.path.join(OUT, 'panorama/images/custom_game/fdm')
os.makedirs(IMG, exist_ok=True)
URL = 'file://{images}/custom_game/fdm/'

def save(name, rgba):
    big = np.repeat(np.repeat(rgba, UP, 0), UP, 1)
    Image.fromarray(big).save(os.path.join(IMG, name.lower() + '.png'))
    return URL + name.lower() + '.png'

def px(v, s): return '%.1fpx' % (v * s)

css = []
def rule(sel, **props):
    body = ' '.join('%s: %s;' % (k.replace('_', '-'), v) for k, v in props.items())
    css.append('%s { %s }' % (sel, body))

def img_rule(sel, name, x=None, y=None, src='graphics'):
    r = assets.graphic(name) if src == 'graphics' else assets.sprite(name)
    if r is None:
        print('missing', name); return None
    rgba, (lo, to) = r
    h, w = rgba.shape[:2]
    url = save(name, rgba)
    props = dict(width=px(w, SX), height=px(h, SY), background_image='url("%s")' % url,
                 background_size='100% 100%', background_repeat='no-repeat')
    if x is not None:
        props['margin_left'] = px(x - lo, SX); props['margin_top'] = px(y - to, SY)
    rule(sel, **props)
    return (w, h, lo, to)

xml = []
def P(id_=None, cls=None, children=None):
    a = []
    if id_: a.append('id="%s"' % id_)
    if cls: a.append('class="%s"' % cls)
    a.append('hittest="false"')
    if children is None: return '<Panel %s />' % ' '.join(a)
    return '<Panel %s>\n%s\n</Panel>' % (' '.join(a), '\n'.join(children))

# ---------------------------------------------------------------- base layout
rule('.FdmWrap', width='100%', height='100%')
rule('.FdmRoot', width='100%', height='100%', visibility='collapse')
rule('.FdmRoot.On', visibility='visible')
# CS2 sets these classes on an ancestor panel: players who chose it (!hud scores) get the Doom HUD out of the way
# of the scoreboard; by default it stays
rule('.FdmOpts', width='100%', height='100%')
rule('.HUD_SCOREBOARD_VISIBLE .FdmOpts.hidescores', visibility='collapse')
rule('.HUD_ENDOFMATCH_VISIBLE .FdmOpts.hidescores', visibility='collapse')
# lobby: only the text lines
rule('.FdmRoot.Lobby', visibility='visible')
for c in ('Flash', 'Wpn', 'Team', 'SBar', 'MsgLine', 'XHair'):
    rule('.FdmRoot.Lobby .' + c, visibility='collapse')
rule('.Flash', width='100%', height='100%', background_color='#00000000')
for i in range(8):
    rule('.Flash.red%d' % (i + 1), background_color='#ff0000%02x' % int(255 * (i + 1) * 0.9 / 8))
for i in range(4):
    rule('.Flash.gold%d' % (i + 1), background_color='#d7ba45%02x' % int(255 * (i + 1) * 0.5 / 4))
rule('.Flash.invul', background_color='#ffffff30')
rule('.Screen', width='1440px', height='1080px', horizontal_align='center', vertical_align='bottom')

# weapon (psprite): positioned for sx = 1, sy = WEAPONTOP; the script moves it with sy* classes
rule('.Wpn', width='1440px', height='1080px', transition_property='transform', transition_duration='0.03s')
for n in range(25):
    rule('.Wpn.sy%d' % n, transform='translatey(%s)' % px(n * 4, SY))
rule('.WBob', width='1440px', height='1080px')
def bob_frames(name, amp):
    ax, ay = px(amp, SX), px(amp, SY)
    css.append('@keyframes \'' + name + '\' { 0% { transform: translatex(' + ax + ') translatey(0px); } 25% { transform: translatex(0px) translatey(' + ay + '); } '
               '50% { transform: translatex(-' + ax + ') translatey(0px); } 75% { transform: translatex(0px) translatey(' + ay + '); } '
               '100% { transform: translatex(' + ax + ') translatey(0px); } }')
bob_frames('fdmbob1', 7)
bob_frames('fdmbob2', 16)
rule('.WBob.bob1', animation_name='fdmbob1', animation_duration='1.83s', animation_iteration_count='infinite', animation_timing_function='linear')
rule('.WBob.bob2', animation_name='fdmbob2', animation_duration='1.83s', animation_iteration_count='infinite', animation_timing_function='linear')
rule('.WSpr', width='0px', height='0px')
for name in WFRAMES:
    spr, fr = name[:4], name[4]
    r = assets.sprite(name)
    if r is None: print('missing weapon frame', name); continue
    rgba, (lo, to) = r
    h, w = rgba.shape[:2]
    url = save('w_' + name, rgba)
    rule('.WSpr.w_%s_%s' % (spr.lower(), fr.lower()), width=px(w, SX), height=px(h, SY),
         margin_left=px(1 - lo, SX), margin_top=px(32 - to - 16, SY),
         background_image='url("%s")' % url, background_size='100% 100%', background_repeat='no-repeat')

# status bar
# status bar: centred at 85% by default; each player can pick another size with !hud
# (moving it by class doesn't work: Panorama won't re-place a panel when only its alignment changes)
SBAR_SCALE = 0.85
rule('.SBarBox', width=px(320, SX), height=px(34, SY), horizontal_align='center', vertical_align='bottom',
     transform_origin='50% 100%', transform='scale3d(%.2f, %.2f, 1)' % (SBAR_SCALE, SBAR_SCALE))
rule('.SBarBox.classic', transform='scale3d(1, 1, 1)')
rule('.SBarBox.small', transform='scale3d(0.65, 0.65, 1)')
rule('.SBar', width=px(320, SX), height=px(32, SY), margin_top=px(2, SY))
stbar = img_rule('.SBarBg', 'STBAR', 0, 0)
sbar_children = [P(None, 'SBarBg')]

def digits(prefix, n, x_right, y, w, big):
    out = []
    for i in range(n):
        x = x_right - (n - i) * w
        out.append(P(prefix + str(i), 'Dig %s' % ('Big' if big else 'Small')))
        rule('#%s%d' % (prefix, i), margin_left=px(x, SX), margin_top=px(y - 168, SY))
    return out

rule('.Dig', width='0px', height='0px', background_size='100% 100%', background_repeat='no-repeat')
for d in range(10):
    g = assets.graphic('STTNUM%d' % d)
    url = save('bn%d' % d, g[0]); h, w = g[0].shape[:2]
    rule('.Dig.bn%d' % d, width=px(w, SX), height=px(h, SY), background_image='url("%s")' % url)
    g = assets.graphic('STYSNUM%d' % d)
    url = save('yn%d' % d, g[0]); h, w = g[0].shape[:2]
    rule('.Dig.yn%d' % d, width=px(w, SX), height=px(h, SY), background_image='url("%s")' % url)
g = assets.graphic('STTMINUS'); url = save('bnm', g[0]); h, w = g[0].shape[:2]
rule('.Dig.bnm', width=px(w, SX), height=px(h, SY), background_image='url("%s")' % url)

BW, SW = 13, 4
sbar_children += digits('fdm_ammo', 3, 44, 171, BW, True)
sbar_children += digits('fdm_hp', 3, 90, 171, BW, True)
sbar_children += digits('fdm_frag', 3, 138, 171, BW, True)
sbar_children += digits('fdm_ar', 3, 221, 171, BW, True)
for nm, x in (('PctH', 90), ('PctA', 221)):
    img_rule('.%s' % nm, 'STTPRCNT', x, 171 - 168)
    sbar_children.append(P(None, nm))
ammo_y = [173, 179, 191, 185]
for i in range(4):
    sbar_children += digits('fdm_am%dc' % i, 3, 288, ammo_y[i], SW, False)
    sbar_children += digits('fdm_am%dm' % i, 3, 314, ammo_y[i], SW, False)

# face + coloured background (player colour)
COLORS = ['#3c7a28', '#3c5aff', '#966432', '#e61e1e', '#c8c8c8', '#fadc28', '#28dcdc', '#dc3cdc',
          '#ff8c1e', '#783cc8', '#5aa028', '#ff78aa', '#646464', '#1e7878', '#b48c5a', '#ffffff']
rule('.FaceB', width=px(35, SX), height=px(31, SY), margin_left=px(143, SX), margin_top=px(1, SY), opacity='0.55')
for i, c in enumerate(COLORS):
    rule('.FaceB.fb%d' % i, background_color=c)
sbar_children.append(P('fdm_faceb', 'FaceB'))
rule('.Face', width='0px', height='0px', background_size='100% 100%', background_repeat='no-repeat')
faces = []
for pain in range(5):
    faces += ['STFST%d0' % pain, 'STFST%d1' % pain, 'STFST%d2' % pain, 'STFTR%d0' % pain, 'STFTL%d0' % pain,
              'STFOUCH%d' % pain, 'STFEVL%d' % pain, 'STFKILL%d' % pain]
faces += ['STFGOD0', 'STFDEAD0']
for i, f in enumerate(faces):
    img_rule('.Face.f%d' % i, f, 143, 0)
sbar_children.append(P('fdm_face', 'Face'))

# ---------------------------------------------------------------- Doom font lines
rule('.Line', flow_children='right', height=px(8, SY))
rule('.Ch', width='0px', height=px(8, SY), background_size='100% 100%', background_repeat='no-repeat')
rule('.Ch.csp', width=px(4, SX))
rule('.Big .Ch', height=px(16, SY))
rule('.Big .Ch.csp', width=px(8, SX))
GLYPH_W = {}
for code in list(range(33, 96)):
    g = assets.graphic('STCFN%03d' % code)
    if g is None: continue
    rgba, (lo, to) = g
    h, w = rgba.shape[:2]
    GLYPH_W[code] = w
    url = save('c%d' % code, rgba)
    rule('.Ch.c%d' % code, width=px(w, SX), height=px(h, SY), background_image='url("%s")' % url, margin_top=px(-to, SY) if to else '0px')
    rule('.Big .Ch.c%d' % code, width=px(w * 2, SX), height=px(h * 2, SY))

json.dump(GLYPH_W, open(os.path.join(os.path.dirname(sys.argv[2]), 'hud_glyph_w.json'), 'w'))
STRINGS = json.load(open(os.path.join(os.path.dirname(sys.argv[2]), 'hud_strings.json')))
rule('.TImg', width='0px', height=px(8, SY), background_size='100% 100%', background_repeat='no-repeat')
rule('.Big .TImg', height=px(16, SY))
for ti, text in enumerate(STRINGS):
    glyphs = []
    for ch in text:
        code = ord(ch)
        g = assets.graphic('STCFN%03d' % code) if 33 <= code <= 95 else None
        glyphs.append(g[0] if g else None)
    W = sum(g.shape[1] if g is not None else 4 for g in glyphs); H = 8
    img = np.zeros((H, max(W, 1), 4), np.uint8); x = 0
    for g in glyphs:
        if g is None: x += 4; continue
        hh, ww = g.shape[:2]; img[:min(hh, H), x:x + ww] = g[:H]; x += ww
    url = save('t%d' % ti, img)
    rule('.TImg.t%d' % ti, width=px(W, SX), background_image='url("%s")' % url)
    rule('.Big .TImg.t%d' % ti, width=px(W * 2, SX))

def line(prefix, n, cls):
    return P(None, 'Line ' + cls, [P(prefix + 'img', 'TImg')] + [P(prefix + str(i), 'Ch') for i in range(n)])

rule('.MsgLine', margin_left=px(1, SX), margin_top=px(1, SY))
rule('.MsgLine.MsgLine2', margin_top=px(10, SY))  # second line for long messages (the script wraps them)
rule('.CtrLine', horizontal_align='center', margin_top=px(60, SY))
rule('.InfLine1', horizontal_align='right', margin_right=px(2, SX), margin_top=px(10, SY))
rule('.InfLine2', horizontal_align='right', margin_right=px(2, SX), margin_top=px(19, SY))
rule('.SpecLine', horizontal_align='center', margin_top=px(158, SY))
rule('.SpecLine.SpecLine2', margin_top=px(149, SY))  # the line above: who a spectator watches, or the !help keys
# !text: per-player size of the Doom font lines (class on the screen panel). Each line scales from the edge it is
# anchored to; the second line of a pair moves by the size change so the two never overlap
TEXT_SIZES = {'tiny': 0.6, 'small': 0.8, 'large': 1.25, 'huge': 1.5}
for cls, s in TEXT_SIZES.items():
    sc = 'scale3d(%.2f, %.2f, 1)' % (s, s)
    shift = px(9 * (s - 1), SY)
    rule('.Screen.%s .MsgLine' % cls, transform_origin='0% 0%', transform=sc)
    rule('.Screen.%s .MsgLine.MsgLine2' % cls, transform='translatey(%s) %s' % (shift, sc))
    rule('.Screen.%s .InfLine1' % cls, transform_origin='100% 0%', transform=sc)
    rule('.Screen.%s .InfLine2' % cls, transform_origin='100% 0%', transform='translatey(%s) %s' % (shift, sc))
    rule('.Screen.%s .CtrLine' % cls, transform_origin='50% 0%', transform=sc)
    rule('.Screen.%s .SpecLine' % cls, transform_origin='50% 100%', transform=sc)
    rule('.Screen.%s .SpecLine.SpecLine2' % cls, transform='translatey(-%s) %s' % (shift, sc) if s >= 1 else 'translatey(%s) %s' % (px(9 * (1 - s), SY), sc))
rule('.Team', width=px(320, SX), height=px(2, SY))
rule('.Team.teamred', background_color='#e61e1ecc')
rule('.Team.teamblue', background_color='#3c5affcc')

screen = P('fdm_screen', 'Screen', [
    P('fdm_wpn', 'Wpn', [P('fdm_wbob', 'WBob', [P('fdm_wspr', 'WSpr'), P('fdm_wflash', 'WSpr')])]),
    line('fdm_msg', 56, 'MsgLine'),
    line('fdm_msgb', 56, 'MsgLine MsgLine2'),
    line('fdm_ctr', 24, 'CtrLine Big'),
    line('fdm_inf1_', 32, 'InfLine1'),
    line('fdm_inf2_', 32, 'InfLine2'),
    line('fdm_spec', 32, 'SpecLine'),
    line('fdm_spec2_', 40, 'SpecLine SpecLine2'),
])
# crosshair: a small cross at the true screen centre (where shots go), drawn like the Doom source ports do
xh = np.zeros((7, 7, 4), np.uint8)
for k in range(7):
    if k != 3: xh[3, k] = (0, 255, 0, 255); xh[k, 3] = (0, 255, 0, 255)
xh_url = save('xhair', xh)
rule('.XHair', width=px(7, SX), height=px(7, SY), horizontal_align='center', vertical_align='center',
     background_image='url("%s")' % xh_url, background_size='100% 100%', background_repeat='no-repeat', opacity='0.8')
sbarbox = P('fdm_sbarbox', 'SBarBox', [P('fdm_team', 'Team'), P('fdm_sbar', 'SBar', sbar_children)])
# never shown: these make CS2 compile the loading screen picture, the radar and the map icon with the HUD
# (the game looks for map_icons/screenshots/1080p/<map>_png, overheadmaps/<map>_radar_psd, map_icon_<map>)
M = names.MAP
PRELOAD = (('FdmPre1', 'map_icons/screenshots/1080p/%s.png' % M), ('FdmPre2', 'overheadmaps/%s_radar.psd' % M),
           ('FdmPre3', 'map_icons/map_icon_%s.svg' % M), ('FdmPre4', 'map_icons/screenshots/1080p/%s_1.png' % M),
           ('FdmPre5', 'map_icons/screenshots/1080p/%s_2.png' % M))
for cls, src in PRELOAD:
    rule('.' + cls, width='1px', height='1px', opacity='0', visibility='collapse', background_image='url("file://{images}/%s")' % src)
preload = P(None, 'FdmPreload', [P(None, cls) for cls, _ in PRELOAD])
rule('.FdmPreload', width='1px', height='1px', visibility='collapse')
root = P('fdm_root', 'FdmRoot', [P('fdm_flash', 'Flash'), screen, sbarbox, preload])
# the root panel may not carry an id (CustomHud validation), so fdm_root sits inside a plain full-screen panel
doc = ('<root>\n\t<styles>\n\t\t<include src="file://{resources}/styles/custom_game/freedm.css" />\n\t</styles>\n'
       '\t<Panel class="FdmWrap" hittest="false">\n' + P('fdm_opts', 'FdmOpts', [root]) + '\n\t</Panel>\n</root>\n')
os.makedirs(os.path.join(OUT, 'panorama/layout/custom_game'), exist_ok=True)
os.makedirs(os.path.join(OUT, 'panorama/styles/custom_game'), exist_ok=True)
open(os.path.join(OUT, 'panorama/layout/custom_game/freedm.xml'), 'w', newline='\n').write(doc)
open(os.path.join(OUT, 'panorama/styles/custom_game/freedm.css'), 'w', newline='\n').write('\n'.join(css) + '\n')
print('hud: %d css rules, %d images' % (len(css), len(os.listdir(IMG))))
