"""The Nanite Temple HUD: a flat, CS2-like layer of Labels (Stratum2) in thin dark boxes with a cyan edge. Nothing in CS2's own zones.

  top centre   phase line:  VAULT 2 / 3  1:42   |  STAGING  BREACH IN 0:23  |  SHOWDOWN 3:10  4 SQUADS LEFT
  left         class tile: class name, ability state (DASH READY / DASH 3.4 s / SURGE 2.1 s), squad + area line under it
  centre       one message line (vault cleared, the breach, eliminations), cleared by the script after a few seconds
  right        class picker (lobby and staging only): the three classes, the current one lit; chat !ninja !monk !chrono or a lobby kiosk picks
  full screen  chrono vignette (a magenta edge) while the surge runs

usage: hud.py <addon_out> <name> <map>     writes panorama/layout/custom_game/<name>.xml + styles + images, and build/hud_states.json
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
CREATE = os.environ.get('CREATE', os.path.join(HERE, '..', '..', '..', 'create'))
sys.path.insert(0, CREATE)
from PIL import Image
import panorama
from panorama import P

OUT, NAME, MAP = sys.argv[1], sys.argv[2], sys.argv[3]
IMG = 'custom_game/%s' % NAME
img_dir = os.path.join(OUT, 'panorama/images', IMG); os.makedirs(img_dir, exist_ok=True)

# the surge vignette: transparent middle, magenta edges
W, H = 480, 270
vig = Image.new('RGBA', (W, H), (0, 0, 0, 0)); px = vig.load()
for y in range(H):
    for x in range(W):
        dx, dy = (x / W - 0.5) * 2, (y / H - 0.5) * 2
        d = (dx * dx * 0.9 + dy * dy) ** 0.5
        a = max(0.0, min(1.0, (d - 0.82) / 0.45)) ** 1.5
        px[x, y] = (255, 60, 200, int(a * 120))
vig.save(os.path.join(img_dir, 'vignette.png'))

CY = '#3ee6ff'; CYd = '#1b6f80'; BG = '#070b0ecc'; TXT = '#eaf7fa'; DIM = '#9ab8c0'; AMB = '#ffb43c'; MAG = '#ff3cc8'
FONT = panorama.FONT
h = panorama.Hud(img_url='file://{images}/%s/' % IMG, img_dir=img_dir, place_prefix='NtL')
h.rule('.NtHost', width='100%', height='100%')
h.rule('.Nt', width='100%', height='100%', opacity='0', font_family=FONT)
h.rule('.Nt.stOn', opacity='1')
h.hide_with_scoreboard('Nt')
# vignette under everything
h.rule('.Vig', width='100%', height='100%', opacity='0', background_image='url("file://{images}/%s/vignette.png")' % IMG, background_size='100% 100%', background_repeat='no-repeat')
h.rule('.Nt.stVig .Vig', opacity='1')
# top phase line (below the team counter at y 0..66, narrower than the kill feed's gap)
h.rule('.Top', width='560px', height='44px', horizontal_align='center', margin_top='74px', background_color=BG, border='1px solid ' + CYd, border_radius='6px', opacity='0')
h.rule('.Nt.stTop .Top', opacity='1')
h.rule('.TopText', width='540px', height='32px', margin_left='10px', margin_top='6px', text_align='center', font_size='22px', font_weight='bold', color=TXT, letter_spacing='1px')
h.rule('.Nt.stBreach .Top', border='1px solid ' + MAG)
h.rule('.Nt.stStage .Top', border='1px solid ' + AMB)
# class tile (left, under the radar)
h.rule('.Tile', width='320px', height='78px', margin_left='24px', margin_top='330px', background_color=BG, border='1px solid ' + CYd, border_left='4px solid ' + CY, border_radius='6px', opacity='0')
h.rule('.Nt.stRun .Tile', opacity='1')
h.rule('.Tile.stMonk', border_left='4px solid ' + AMB)
h.rule('.Tile.stChrono', border_left='4px solid ' + MAG)
h.rule('.ClsText', width='296px', height='30px', margin_left='14px', margin_top='6px', font_size='22px', font_weight='bold', color=TXT, letter_spacing='1px')
h.rule('.AbilText', width='296px', height='28px', margin_left='14px', margin_top='40px', font_size='19px', color=DIM)
h.rule('.Tile.stReady .AbilText', color=CY)
h.rule('.Tile.stActive .AbilText', color='#ffffff')
h.rule('.Info', width='420px', height='30px', margin_left='24px', margin_top='414px', font_size='17px', color=DIM, text_shadow='1px 1px 2px #000000', opacity='0')
h.rule('.Nt.stRun .Info', opacity='1')
# centre message
h.rule('.Msg', width='760px', height='44px', horizontal_align='center', margin_top='660px', text_align='center', font_size='24px', font_weight='bold', color=TXT, letter_spacing='1px', text_shadow='0px 0px 8px #000000', opacity='0')
h.rule('.Nt.stMsg .Msg', opacity='1')
h.rule('.Sub', width='760px', height='30px', horizontal_align='center', margin_top='704px', text_align='center', font_size='18px', color=DIM, text_shadow='0px 0px 6px #000000', opacity='0')
h.rule('.Nt.stMsg .Sub', opacity='1')
# class picker (right side; shown in the lobby and staging)
h.rule('.Pick', width='360px', height='226px', horizontal_align='right', margin_right='24px', margin_top='330px', background_color=BG, border='1px solid ' + CYd, border_radius='6px', opacity='0')
h.rule('.Nt.stPick .Pick', opacity='1')
h.rule('.PickTitle', width='340px', height='30px', margin_left='12px', margin_top='8px', font_size='14px', font_weight='bold', color=DIM, letter_spacing='1px')
for i in range(3):
    h.rule('.Row%d' % i, width='340px', height='48px', margin_left='10px', margin_top='%dpx' % (42 + i * 52), border_radius='4px', background_color='#00000000')
h.rule('.PRow.stSel', background_color='#3ee6ff22', border='1px solid ' + CYd)
h.rule('.PName', width='200px', height='26px', margin_left='10px', margin_top='3px', font_size='19px', font_weight='bold', color=TXT)
h.rule('.PKey', width='120px', height='22px', horizontal_align='right', margin_right='10px', margin_top='5px', text_align='right', font_size='15px', color=CY)
h.rule('.PDesc', width='320px', height='20px', margin_left='10px', margin_top='27px', font_size='14px', color=DIM)
h.rule('.PickHelp', width='340px', height='18px', margin_left='12px', margin_top='198px', font_size='13px', color=DIM)

ROWS = [('VECTOR', 'crouch + E', 'dash along the crosshair; melee kills reset it'),
        ('WARDEN', 'R on empty mag', 'an aegis that cuts outside hits by 70%'),
        ('ECHO', 'F', '+40% speed and a full mag; a lethal hit rewinds you')]
pick_rows = [P('Row%d' % i, 'PRow Row%d' % i, [
    P(None, 'PName', tag='Label', extra='text="%s"' % n), P(None, 'PKey', tag='Label', extra='text="%s"' % k),
    P(None, 'PDesc', tag='Label', extra='text="%s"' % d)]) for i, (n, k, d) in enumerate(ROWS)]

body = P('Nt', 'Nt', [
    P(None, 'Vig'),
    P(None, 'Top', [P('TopT', 'TopText', tag='Label', extra='text="{s:t}"')]),
    P('Tile', 'Tile', [P('Cls', 'ClsText', tag='Label', extra='text="{s:c}"'), P('Abil', 'AbilText', tag='Label', extra='text="{s:a}"')]),
    P('Info', 'Info', tag='Label', extra='text="{s:i}"'),
    P('Msg', 'Msg', tag='Label', extra='text="{s:m}"'),
    P('Sub', 'Sub', tag='Label', extra='text="{s:u}"'),
    P('Pick', 'Pick', [P(None, 'PickTitle', tag='Label', extra='text="CLASS   chat !vector !warden !echo, or E at a kiosk"')] + pick_rows +
                     [P(None, 'PickHelp', tag='Label', extra='text="nanites = your money: buy in the staging room"')]),
    h.preload(MAP, slides=2, radar=False, icon=False),
])
h.write(OUT, NAME, body, dynamic=r'^st[A-Z]\w*$', wrap_cls='NtHost', gen_dir=os.path.join(OUT, '_gen'))

states = {
    'lobby': {'Nt': {'add': ['stOn', 'stTop', 'stPick']}, 'TopT': {'text': 'NANITE TEMPLE   14 PLAYERS   STARTING IN 0:08'}, 'Row0': {'add': ['stSel']}},
    'vault': {'Nt': {'add': ['stOn', 'stTop', 'stRun', 'stMsg']}, 'TopT': {'text': 'VAULT 2 / 3    1:42'}, 'Cls': {'text': 'VECTOR'},
              'Tile': {'add': ['stReady']}, 'Abil': {'text': 'DASH READY'}, 'Info': {'text': 'SQUAD 3   5 / 5 ALIVE   AREA  VAULT 07  RING'},
              'Msg': {'text': 'VAULT CLEARED'}, 'Sub': {'text': 'stand on the amber plate to move on'}},
    'surge': {'Nt': {'add': ['stOn', 'stTop', 'stRun', 'stVig']}, 'TopT': {'text': 'SHOWDOWN 3:10    4 SQUADS LEFT'}, 'Cls': {'text': 'ECHO'},
              'Tile': {'add': ['stChrono', 'stActive']}, 'Abil': {'text': 'REWIND ARMED 2.1 s'}, 'Info': {'text': 'SQUAD 1   3 / 5 ALIVE   AREA  THE ARENA'}},
    'staging': {'Nt': {'add': ['stOn', 'stTop', 'stRun', 'stPick', 'stStage']}, 'TopT': {'text': 'STAGING    BREACH IN 0:23'}, 'Cls': {'text': 'WARDEN'},
                'Tile': {'add': ['stMonk']}, 'Abil': {'text': 'AEGIS 12.0 s'}, 'Info': {'text': 'SQUAD 6   4 / 4 ALIVE   AREA  STAGING'}, 'Row1': {'add': ['stSel']}},
}
os.makedirs(os.path.join(HERE, '..', 'build'), exist_ok=True)
json.dump(states, open(os.path.join(HERE, '..', 'build', 'hud_states.json'), 'w'), indent=1)
print('hud states -> build/hud_states.json')
