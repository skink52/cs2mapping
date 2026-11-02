"""The 1.6 HUD and menus for CS2 Panorama (custom_hud_layout cs16_hud), made from the player's own 1.6 files.

usage: python3 tools/hud.py <cstrike dir> <addon out dir>

Writes panorama/layout/custom_game/cs16.xml, panorama/styles/custom_game/cs16.css, the pictures under
panorama/images/custom_game/cs16/, _gen/hud.json (menu texts for the script, from resource/cstrike_english.txt) and
_gen/hud_ids.json (panel ids, for the test harness).

Pictures: the HUD numbers and icons come from sprites/640hud7.spr (positions from sprites/hud.txt and the weapon_*.txt
ammo icons). 1.6 drew them additively, tinted with the HUD colour (orange 255 160 0, red 255 16 16, green 0 160 0); here
each is a picture in each colour with the sprite's brightness as its alpha. Menu pictures are the 1.6 VGUI pictures
(gfx/vgui/*.tga).

Layout rules (learned in space-racer-cs2): one Screen panel 1080 px high; every panel has a fixed size and is pinned from
the top and from the left edge, the centre or the right edge; panels are shown and hidden with opacity; classes the
script switches never have a rule of their own (only compound selectors), and state classes on cs_root start with "st".
"""
import os, sys, re, json, struct
import numpy as np
from PIL import Image

CS, OUT = sys.argv[1], sys.argv[2]
IMG = 'file://{images}/custom_game/cs16/'
IMGDIR = os.path.join(OUT, 'panorama/images/custom_game/cs16')
os.makedirs(IMGDIR, exist_ok=True)
FONT = 'Verdana, Tahoma, Arial'
S = 1.5                                   # 640-res sprites to 1080 px (about what 1024 x 768 looked like)
COLORS = {'O': (255, 160, 0), 'R': (255, 16, 16), 'G': (0, 160, 0)}
css, ids = [], []


def rule(sel, **props):
    css.append('%s { %s }' % (sel, ' '.join('%s: %s;' % (k.replace('_', '-'), v) for k, v in props.items())))


def P(id_=None, cls=None, kids=None, tag='Panel', extra='', hit=False):
    a = []
    if id_: a.append('id="%s"' % id_); ids.append(id_)
    if cls: a.append('class="%s"' % cls)
    if tag != 'Button': a.append('hittest="%s"' % ('true' if hit else 'false'))
    if extra: a.append(extra)
    if kids is None: return '<%s %s />' % (tag, ' '.join(a))
    return '<%s %s>\n%s\n</%s>' % (tag, ' '.join(a), '\n'.join(kids), tag)


def L(id_, cls, text='{s:v}'):
    return P(id_, cls, tag='Label', extra='text="%s"' % text)


def px(v): return '%dpx' % int(round(v))


_pl = [0]
def place(x=None, y=0, w=None, h=None, right=None, center=False, pct=None):
    """a class pinning a panel: from the left (x px or pct %), the centre or the right edge, and from the top"""
    _pl[0] += 1
    c = 'P%d' % _pl[0]
    pr = {}
    if w is not None: pr['width'] = px(w)
    if h is not None: pr['height'] = px(h)
    if center: pr['horizontal_align'] = 'center'
    elif right is not None: pr['horizontal_align'] = 'right'; pr['margin_right'] = px(right)
    elif pct is not None: pr['margin_left'] = '%g%%' % pct
    else: pr['margin_left'] = px(x or 0)
    pr['margin_top'] = px(y)
    rule('.' + c, **pr)
    return c


# ---------------------------------------------------------------- 1.6 sprites (.spr v2) and the HUD sprite table
def read_spr(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'IDSP', path
    ver, typ, fmt, rad, w, h, nf, beam, sync = struct.unpack_from('<iiifiiifi', d, 4)
    p = 40
    n = struct.unpack_from('<h', d, p)[0]; p += 2
    pal = np.frombuffer(d, np.uint8, n * 3, p).reshape(n, 3); p += n * 3
    ftype, ox, oy, fw, fh = struct.unpack_from('<iiiii', d, p); p += 20
    pix = np.frombuffer(d, np.uint8, fw * fh, p).reshape(fh, fw)
    return pal[pix], fmt


hudtxt = {}
for line in open(os.path.join(CS, 'sprites/hud.txt'), encoding='latin-1'):
    f = line.split()
    if len(f) == 7 and f[1] == '640': hudtxt[f[0]] = (f[2], int(f[3]), int(f[4]), int(f[5]), int(f[6]))
sprites = {}


def sprite(name, rect=None):
    file, x, y, w, h = rect or hudtxt[name]
    if file not in sprites: sprites[file] = read_spr(os.path.join(CS, 'sprites', file + '.spr'))[0]
    return sprites[file][y:y + h, x:x + w].astype(np.float32)


def tinted(rgb, color, scale=2.0):
    """additive sprite -> picture in the HUD colour with the sprite's brightness as alpha (2x for crisp scaling)"""
    a = rgb.max(axis=2) / 255.0
    out = np.zeros(rgb.shape[:2] + (4,), np.uint8)
    out[..., :3] = color
    out[..., 3] = np.clip(a ** 0.85 * 255, 0, 255)
    im = Image.fromarray(out, 'RGBA')
    return im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)


def hud_pic(key, rgb, colors=('O', 'R', 'G')):
    for c in colors:
        tinted(rgb, COLORS[c]).save(os.path.join(IMGDIR, 'h_%s_%s.png' % (key, c)))
    return rgb.shape[1] * S, rgb.shape[0] * S


SIZE = {}
for k in range(10): SIZE['d%d' % k] = hud_pic('d%d' % k, sprite('number_%d' % k))
for name, key in [('cross', 'cross'), ('suit_full', 'suit'), ('suit_empty', 'suite'), ('suithelmet_full', 'suith'), ('dollar', 'dollar'),
                  ('plus', 'plus'), ('minus', 'minus'), ('stopwatch', 'stopwatch'), ('c4', 'c4'), ('defuser', 'defuser'),
                  ('buyzone', 'buyzone'), ('divider', 'divider')]:
    SIZE[key] = hud_pic(key, sprite(name))
# the timer's colon: two small squares like 1.6's
col = np.zeros((25, 6, 3), np.float32); col[7:11, 1:5] = 255; col[16:20, 1:5] = 255
SIZE['colon'] = hud_pic('colon', col)
# ammo icons from the weapon_*.txt files, one per 1.6 ammo type (and per grenade)
AMMO_FROM = {'9mm': 'glock18', '45acp': 'usp', '357sig': 'p228', '50ae': 'deagle', '57mm': 'p90', 'buckshot': 'm3', '556nato': 'm4a1',
             '556natobox': 'm249', '762nato': 'ak47', '338magnum': 'awp', 'hegrenade': 'hegrenade', 'flashbang': 'flashbang', 'smokegrenade': 'smokegrenade'}
for am, wf in AMMO_FROM.items():
    for line in open(os.path.join(CS, 'sprites/weapon_%s.txt' % wf), encoding='latin-1'):
        f = line.split()
        if len(f) == 7 and f[0] == 'ammo' and f[1] == '640':
            SIZE['am_' + am] = hud_pic('am_' + am, sprite(None, (f[2], int(f[3]), int(f[4]), int(f[5]), int(f[6]))))
            break

# ---------------------------------------------------------------- VGUI pictures for the menus
VGUI = {'glock18': 'glock18', 'usp': 'usp45', 'p228': 'p228', 'deagle': 'deserteagle', 'fiveseven': 'fiveseven', 'elite': 'elites', 'm3': 'm3',
        'xm1014': 'xm1014', 'tmp': 'tmp', 'mp5navy': 'mp5', 'mac10': 'mac10', 'ump45': 'ump45', 'p90': 'p90', 'famas': 'famas', 'scout': 'scout',
        'ak47': 'ak47', 'galil': 'galil', 'm4a1': 'm4a1', 'aug': 'aug', 'sg550': 'sg550', 'sg552': 'sg552', 'awp': 'awp', 'g3sg1': 'g3sg1',
        'm249': 'm249', 'kevlar': 'kevlar', 'vesthelm': 'kevlar_helmet', 'flashbang': 'flashbang', 'hegrenade': 'hegrenade',
        'smokegrenade': 'smokegrenade', 'defuser': 'defuser', 'nvg': 'nightvision', 'not_available': 'not_available',
        'terror': 'terror', 'leet': 'leet', 'arctic': 'arctic', 'guerilla': 'guerilla', 'urban': 'urban', 'gsg9': 'gsg9', 'sas': 'sas',
        'gign': 'gign', 't_random': 't_random', 'ct_random': 'ct_random'}
PIC = {}
for key, tga in VGUI.items():
    f = os.path.join(CS, 'gfx/vgui/%s.tga' % tga)
    if not os.path.exists(f): print('missing picture', f); continue
    im = Image.open(f).convert('RGBA')
    im.save(os.path.join(IMGDIR, 'pic_%s.png' % key))
    PIC[key] = im.size

# ---------------------------------------------------------------- menu texts (resource/cstrike_english.txt)
eng = {}
raw = open(os.path.join(CS, 'resource/cstrike_english.txt'), 'rb').read()
txt = raw.decode('utf-16') if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else raw.decode('utf-8', 'replace')
for k, v in re.findall(r'"([^"\n]+)"\s+"([^"]*)"', txt): eng[k.lower()] = v.replace('\\n', '\n')
def s(key, default=''): return eng.get(key.lower(), default)
def label(key, default): return re.sub(r'^&\S\s*', '', s(key, default)).strip()
ITEMS = {'glock18': ('Glock18', 'Glock'), 'usp': ('USP45', 'USP45'), 'p228': ('P228', 'P228'), 'deagle': ('DesertEagle', 'DesertEagle'),
         'fiveseven': ('FiveSeven', 'FiveSeven'), 'elite': ('Elites', 'Elites'), 'm3': ('m3', 'M3'), 'xm1014': ('xm1014', 'XM1014'),
         'tmp': ('Tmp', 'TMP'), 'mp5navy': ('MP5', 'MP5'), 'mac10': ('MAC10', 'Mac10'), 'ump45': ('UMP45', 'UMP45'), 'p90': ('P90', 'P90'),
         'famas': ('Famas', 'Famas'), 'scout': ('Scout_CT', 'Scout'), 'ak47': ('AK47', 'AK47'), 'galil': ('Galil', 'Galil'), 'm4a1': ('M4A1', 'M4A1'),
         'aug': ('Aug', 'Aug'), 'sg550': ('SG550', 'SG550'), 'sg552': ('SG552', 'SG552'), 'awp': ('AWP_CT', 'AWP'), 'g3sg1': ('G3SG1', 'G3SG1'),
         'm249': ('M249', 'M249')}
FIELDS = ['Price', 'Origin', 'Calibre', 'ClipCapacity', 'RateOfFire', 'WeightLoaded', 'ProjectileWeight', 'MuzzleVelocity', 'MuzzleEnergy']
items = {}
for iid, (lk, pk) in ITEMS.items():
    lines = ['%s%s' % (s('CStrike_%sLabel' % f, f.upper()), s('CStrike_%s%s' % (pk, f))) for f in FIELDS if s('CStrike_%s%s' % (pk, f))]
    items[iid] = {'label': label('Cstrike_' + lk, iid.upper()), 'info': '\n'.join(lines)}
for iid, lk, pk in [('kevlar', 'Kevlar', 'Kevlar'), ('vesthelm', 'Kevlar_Helmet', 'KevlarHelmet'), ('flashbang', 'Flashbang', 'Flashbang'),
                    ('hegrenade', 'HE_Grenade', 'HEGrenade'), ('smokegrenade', 'Smoke_Grenade', 'SmokeGrenade'), ('defuser', 'Defuser', 'Defuser'),
                    ('nvg', 'NightVision_Button_CT', 'Nightvision')]:
    info = [s('CStrike_PriceLabel', 'PRICE') + s('Cstrike_%sPrice' % pk), s('Cstrike_DescriptionLabel', 'DESCRIPTION') + s('Cstrike_%sDescription' % pk)]
    items[iid] = {'label': label('Cstrike_' + lk, iid.upper()), 'info': '\n'.join(re.sub(r'\s*\n\s*', ' ', x).strip() for x in info if x.strip())}
cats = {'pistol': label('Cstrike_Pistols', 'PISTOLS'), 'shotgun': label('Cstrike_Shotguns', 'SHOTGUNS'), 'smg': label('Cstrike_SubMachineGuns', 'SMG'),
        'rifle': label('Cstrike_Rifles', 'RIFLES'), 'mg': label('Cstrike_MachineGuns', 'MACHINE GUNS'), 'ammo1': label('Cstrike_Prim_Ammo', 'PRIMARY AMMO'),
        'ammo2': label('Cstrike_Sec_Ammo', 'SECONDARY AMMO'), 'equip': label('Cstrike_Equipment', 'EQUIPMENT')}
classes = {}
for cid, lk, dk in [('terror', 'Terror', 'Terror'), ('leet', 'L337_Krew', 'Leet'), ('arctic', 'Arctic', 'Arctic'), ('guerilla', 'Guerilla', 'Guerilla'),
                    ('urban', 'Urban', 'Urban'), ('gsg9', 'GSG9', 'GSG9'), ('sas', 'SAS', 'SAS'), ('gign', 'GIGN', 'GIGN')]:
    classes[cid] = {'label': label('Cstrike_' + lk, cid.upper()), 'info': re.sub(r'\s*\n\s*', ' ', s('Cstrike_%s_Label' % dk)).strip()}
titles = {'buy': s('Cstrike_Buy_Menu', 'Buy Menu'), 'cancel': label('Cstrike_Cancel', 'CANCEL'), 'rebuy': label('Cstrike_BuyMenuRebuy', 'RE-BUY PREVIOUS'),
          'auto': label('Cstrike_Auto_Select', 'AUTO-SELECT'), 'class_2': s('Cstrike_Join_Class', 'CHOOSE A CLASS'), 'class_3': s('Cstrike_Join_Class', 'CHOOSE A CLASS')}
os.makedirs(os.path.join(OUT, '_gen'), exist_ok=True)
json.dump({'items': items, 'cats': cats, 'classes': classes, 'titles': titles}, open(os.path.join(OUT, '_gen/hud.json'), 'w'), indent=1)

# ---------------------------------------------------------------- css: base
rule('.CsWrap', width='100%', height='100%')
rule('.CsRoot', width='100%', height='100%')
rule('.HudP', width='100%', height='1080px', opacity='0')
rule('.CsRoot.stOn .HudP', opacity='1')
rule('.Screen', width='100%', height='1080px')
rule('.HUD_SCOREBOARD_VISIBLE .CsRoot', opacity='0')
rule('.CsRoot Label', font_family=FONT, color='#f0f0f0', text_shadow='1px 1px 0px #000000', font_weight='bold')
rule('.Pic', background_size='100% 100%', background_repeat='no-repeat')
# digits and icons in the three HUD colours; the colour class sits on the box (cO / cR / cG)
for c in COLORS:
    for k in range(10): rule('.c%s .Dig.d%d' % (c, k), background_image='url("%sh_d%d_%s.png")' % (IMG, k, c))
    for key in ['cross', 'suit', 'suite', 'suith', 'dollar', 'plus', 'minus', 'stopwatch', 'c4', 'defuser', 'buyzone', 'divider', 'colon'] + \
               ['am_' + a for a in AMMO_FROM]:
        rule('.c%s .Ico.%s' % (c, key), background_image='url("%sh_%s_%s.png")' % (IMG, key, c))
rule('.Dig', width=px(SIZE['d0'][0]), height=px(SIZE['d0'][1]), margin_right=px(3 * S), background_size='100% 100%', background_repeat='no-repeat')
rule('.Ico', background_size='100% 100%', background_repeat='no-repeat')
rule('.Row', flow_children='right')
# 1.6 HUD brightness: a changed value lights up, then settles back
rule('.Hb', opacity='0.62', transition_property='opacity', transition_duration='1.0s')
rule('.Hb.hot', opacity='1', transition_duration='0.05s')

FH = round(25 * S)                     # 1.6 font height
BOT = 1080 - FH - FH // 2              # the bottom row (1.6: ScreenHeight - FontHeight * 1.5)
DW = SIZE['d0'][0] + 3 * S             # one digit cell


def icon(id_, key, w, h, y=0, x=0, cls=''):
    return P(id_, ('Ico %s %s ' % (key or '', cls)).strip() + ' ' + place(x=x, y=y, w=w, h=h))


def digits(row, n, x, y):
    return P(row, 'Row ' + place(x=x, y=y, w=n * DW, h=FH), [P('%s_%d' % (row, k), 'Dig') for k in range(n)])


# ---------------------------------------------------------------- bottom row: health, armour, timer, ammo; money above the ammo
iw = SIZE['cross'][0]
health = P('cs_hpb', 'Hb cO Alive ' + place(x=18, y=BOT, w=iw + 8 + 3 * DW, h=FH), [
    icon(None, 'cross', iw, iw, y=(FH - iw) / 2), digits('cs_hp', 3, iw + 8, 0)])
armor = P('cs_apb', 'Hb cO Alive ' + place(pct=20, y=BOT, w=iw + 8 + 3 * DW, h=FH), [
    icon('cs_api', None, iw, iw, y=(FH - iw) / 2), digits('cs_ap', 3, iw + 8, 0)])
cw = SIZE['colon'][0]
tw = iw + 10 + 4 * DW + cw + 4
timer = P('cs_tmb', 'Hb cO Timer ' + place(center=True, y=BOT, w=tw, h=FH), [
    icon(None, 'stopwatch', iw, iw, y=(FH - iw) / 2),
    P(None, 'Row ' + place(x=iw + 10, y=0, w=2 * DW, h=FH), [P('cs_tm_0', 'Dig'), P('cs_tm_1', 'Dig')]),
    icon(None, 'colon', cw, FH, x=iw + 10 + 2 * DW),
    P(None, 'Row ' + place(x=iw + 10 + 2 * DW + cw + 4, y=0, w=2 * DW, h=FH), [P('cs_tm_2', 'Dig'), P('cs_tm_3', 'Dig')])])
dvw, dvh = SIZE['divider']
aw = 3 * DW + 12 + dvw + 12 + 3 * DW + 8 + iw
ammo = P('cs_amb', 'cO Ammo ' + place(right=18, y=BOT, w=aw, h=FH), [
    P(None, 'Clip ' + place(x=0, y=0, w=3 * DW + 12 + dvw, h=FH), [digits('cs_ac', 3, 0, 0), icon(None, 'divider', dvw, FH, x=3 * DW + 12, y=0)]),
    digits('cs_ar', 3, 3 * DW + 24 + dvw, 0),
    icon('cs_ami', None, iw, iw, x=aw - iw, y=(FH - iw) / 2)])
dw_ = SIZE['dollar'][0]
mw = dw_ + 6 + 5 * DW
money = P('cs_mnb', 'Hb cO ' + place(right=18, y=BOT - 2 * FH, w=mw, h=FH), [icon(None, 'dollar', dw_, FH), digits('cs_mn', 5, dw_ + 6, 0)])
pw = SIZE['plus'][0]
delta = P('cs_mdb', 'Delta cG ' + place(right=18, y=BOT - 3 * FH - 8, w=pw + 6 + 5 * DW, h=FH), [
    P('cs_mds', 'Ico ' + place(x=0, y=(FH - SIZE['plus'][1]) / 2, w=pw, h=SIZE['plus'][1])), digits('cs_md', 5, pw + 6, 0)])
rule('.Delta', opacity='0')
rule('.Delta.on', opacity='1')
rule('.CsRoot .Ammo', opacity='0')
rule('.CsRoot.stAlive .Ammo.on', opacity='0.62')
rule('.Ammo.noclip .Clip', opacity='0')
rule('.CsRoot .Alive', opacity='0')
rule('.CsRoot.stAlive .Alive', opacity='0.62')
rule('.CsRoot.stAlive .Alive.hot', opacity='1')
rule('.CsRoot .Timer', opacity='0')
rule('.CsRoot.stTimer .Timer', opacity='0.62')
bottom = P(None, 'Bottom ' + place(x=0, y=0, w=None, h=1080), [health, armor, timer, ammo, money, delta])
rule('.Bottom', width='100%')
rule('.stRaised .Bottom', transform='translate3d(0px, -84px, 0px)')

# status icons (left, middle of the screen): buy zone, C4 (blinks in a bomb site), defuse kit
bw = SIZE['buyzone'][0]
status = [P('cs_ibuy', 'Stat cG ' + place(x=18, y=470, w=bw, h=bw), [P(None, 'Ico buyzone ' + place(x=0, y=0, w=bw, h=bw))]),
          P('cs_ic4', 'Stat cG ' + place(x=18, y=470 + bw + 10, w=bw, h=bw), [P(None, 'Ico c4 ' + place(x=0, y=0, w=bw, h=bw))]),
          P('cs_idef', 'Stat cG ' + place(x=18, y=470 + 2 * (bw + 10), w=bw, h=bw), [P(None, 'Ico defuser ' + place(x=0, y=0, w=bw, h=bw))])]
rule('.CsRoot .Stat', opacity='0')
rule('.CsRoot.stAlive .Stat.on', opacity='0.85')
css.append("@keyframes 'csblink' { 0% { opacity: 1; } 49% { opacity: 1; } 50% { opacity: 0.15; } 100% { opacity: 0.15; } }")
rule('.CsRoot.stAlive .Stat.on.blink', animation_name='csblink', animation_duration='0.5s', animation_iteration_count='infinite')

# centre message (1.6 centre print) and the small top line
msg = P('cs_msgb', 'Msg ' + place(center=True, y=330, w=1100, h=220), [L('cs_msg', 'MsgText ' + place(x=0, y=0, w=1100, h=220))])
rule('.Msg', opacity='0', transition_property='opacity', transition_duration='0.3s')
rule('.Msg.on', opacity='1', transition_duration='0.05s')
rule('.MsgText', font_size='28px', text_align='center', color='#f2f2f2')
top = P('cs_topb', 'Top ' + place(center=True, y=118, w=800, h=40), [L('cs_top', 'TopText ' + place(x=0, y=0, w=800, h=40))])
rule('.Top', opacity='0', transition_property='opacity', transition_duration='0.6s')
rule('.Top.on', opacity='0.9')
rule('.TopText', font_size='24px', text_align='center', color='#ffa000', letter_spacing='2px')

# ---------------------------------------------------------------- the menu box (buy menu / class menu)
MW, MH, RW, RH, RG, RY = 1040, 660, 450, 44, 6, 74
rows = []
for i in range(10):
    y = RY + i * (RH + RG)
    rows.append(P('cs_mb%d' % i, 'MRow ' + place(x=24, y=y, w=RW, h=RH), [
        L('cs_ml%d' % i, 'MLabel ' + place(x=14, y=8, w=330, h=30)),
        L('cs_mp%d' % i, 'MPrice ' + place(right=12, y=8, w=90, h=30)),
        # what hovering the row shows on the right: the 1.6 picture and description
        P('cs_mh%d' % i, 'MInfo ' + place(x=0, y=0, w=520, h=560), [
            P('cs_mpic%d' % i, 'MPic ' + place(x=0, y=0, w=512, h=232)),
            L('cs_mi%d' % i, 'MInfoText ' + place(x=0, y=246, w=520, h=300))]),
    ], tag='Button'))
    rule('#cs_mh%d' % i, transform='translate3d(%dpx, %dpx, 0px)' % (RW + 36, RY - y))
menu = P('cs_menu', 'Menu ' + place(center=True, y=150, w=MW, h=MH), [
    L('cs_mtitle', 'MTitle ' + place(x=24, y=18, w=MW - 48, h=40)),
    *rows,
    L('cs_mfoot', 'MFoot ' + place(x=24, y=MH - 46, w=300, h=32)),
    L(None, 'MHint MHintMouse ' + place(right=24, y=MH - 42, w=640, h=28), text='CLICK A ROW  -  F TO CLOSE'),
    L(None, 'MHint MHintKeys ' + place(right=24, y=MH - 42, w=640, h=28), text='W / S TO MOVE  -  E TO CHOOSE  -  R TO GO BACK  -  F TO CLOSE'),
])
rule('.Menu', background_color='#000000c0', border='2px solid #ffa00080', opacity='0')
rule('.CsRoot.stMenu .Menu', opacity='1')
rule('.MTitle', font_size='30px', color='#ffa000')
rule('.MRow', background_color='#00000000', border='1px solid #ffa00040', opacity='0', overflow='noclip')
rule('.MRow.on', opacity='1')
rule('.MRow.on:hover', background_color='#ffa00055')
rule('.MRow.on.sel', background_color='#ffa00055')
rule('.MLabel', font_size='21px', color='#ffa000')
rule('.MPrice', font_size='21px', color='#ffa000', text_align='right')
rule('.MRow.dis .MLabel', color='#7a6a50')
rule('.MRow.dis .MPrice', color='#7a6a50')
rule('.MInfo', opacity='0')
rule('.MRow.on:hover .MInfo', opacity='1')
rule('.MRow.on.sel .MInfo', opacity='1')
rule('.MInfoText', font_size='19px', color='#ffa000')
rule('.MFoot', font_size='24px', color='#00c000')
rule('.MHint', font_size='16px', color='#ffa000a0', text_align='right', opacity='0')
rule('.CsRoot.stMenu .MHintMouse', opacity='1')
rule('.CsRoot.stMenu.stKeys .MHintMouse', opacity='0')
rule('.CsRoot.stMenu.stKeys .MHintKeys', opacity='1')
rule('.MPic', background_repeat='no-repeat', background_position='0px 0px')
for key, (w, h) in PIC.items():
    k = min(512 / w, 232 / h, 2.0)
    rule('.MPic.pic_%s' % key, background_image='url("%spic_%s.png")' % (IMG, key), background_size='%dpx %dpx' % (round(w * k), round(h * k)))

# never shown: these make CS2 compile the radar, the map icon and the loading screens (tools/loading.py) with the HUD
nshots = json.load(open(os.path.join(OUT, '_gen/loading.json')))['shots'] if os.path.exists(os.path.join(OUT, '_gen/loading.json')) else 0
PRELOAD = [('CsPreR', 'overheadmaps/mg_cs16_radar.psd'), ('CsPreI', 'map_icons/map_icon_mg_cs16.svg')]
PRELOAD += [('CsPreS%d' % n, 'map_icons/screenshots/1080p/mg_cs16%s.png' % ('_%d' % n if n else '')) for n in range(nshots)]
for cls, src in PRELOAD:
    rule('.' + cls, width='1px', height='1px', opacity='0', background_image='url("file://{images}/%s")' % src)
rule('.CsPreload', width='1px', height='1px', opacity='0')
preload = P(None, 'CsPreload ' + place(x=0, y=0, w=1, h=1), [P(None, cls) for cls, _ in PRELOAD])

# ---------------------------------------------------------------- xml
hudp = P(None, 'HudP', [bottom, *status, top, msg])           # the HUD, off with !hud off; menus stay usable
screen = P(None, 'Screen', [preload, hudp, menu])
root = P('cs_root', 'CsRoot', [screen])
doc = ('<root>\n\t<styles>\n\t\t<include src="file://{resources}/styles/custom_game/cs16.css" />\n\t</styles>\n'
       '\t<Panel class="CsWrap" hittest="false">\n' + root + '\n\t</Panel>\n</root>\n')
os.makedirs(os.path.join(OUT, 'panorama/layout/custom_game'), exist_ok=True)
os.makedirs(os.path.join(OUT, 'panorama/styles/custom_game'), exist_ok=True)
open(os.path.join(OUT, 'panorama/layout/custom_game/cs16.xml'), 'w', newline='\n').write(doc)
open(os.path.join(OUT, 'panorama/styles/custom_game/cs16.css'), 'w', newline='\n').write('\n'.join(css) + '\n')
assert len(ids) == len(set(ids)), 'duplicate panel ids'
# classes the script switches must never have a rule of their own (a lone ".name { }")
DYNAMIC = re.compile(r'^(st[A-Z]\w*|on|hot|dis|sel|blink|noclip|c[ORG]|d\d|suit[eh]?|plus|minus|am_\w+|pic_\w+)$')
lone = [m.group(1) for m in (re.match(r'^\.([\w-]+) \{', c) for c in css) if m]
bad = sorted(set(c for c in lone if DYNAMIC.match(c)))
assert not bad, 'switched classes with rules of their own: %s' % bad
json.dump(sorted(set(ids)), open(os.path.join(OUT, '_gen/hud_ids.json'), 'w'))
print('hud: %d css rules, %d panels, %d pictures' % (len(css), len(set(ids)), len(os.listdir(IMGDIR))))
