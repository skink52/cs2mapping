"""Workshop screenshots: the racer's view rendered from the real track and car models (preview/chase_view.py) with
the real HUD laid over it (preview/hud_render.py), 1920 x 1080. Software renders, not CS2 captures: no CS2 lighting,
CS2's own HUD (chat, kill feed, money / health) is not drawn, and every car sits level with the road.

usage: workshop_shots.py <addon_out_dir> <out_dir> [shot names...]"""
import os, sys, json, random, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hud_render as HR
from PIL import Image

OUT, DST = sys.argv[1], sys.argv[2]
ONLY = sys.argv[3:]
HERE = os.path.dirname(os.path.abspath(__file__))
TR = {t['id']: t for t in json.load(open(os.path.join(OUT, '_gen/tracks.json')))}
NAMES = ['NOVA', 'KESTREL', 'VEXIS', 'MARLOW', 'ZIGGY', 'ORBIT', 'PIXL', 'RAYNE', 'BLITZ', 'ACE', 'SOLSTICE', 'DRIFTER']
os.makedirs(DST, exist_ok=True)
HR.init(OUT)


def background(name, track, frac, preset='high', **env):
    path = os.path.join(DST, '_bg_%s.png' % name)
    e = dict(os.environ, SIZE='1920x1080')
    e.update({k: str(v) for k, v in env.items()})
    subprocess.run([sys.executable, '-I', os.path.join(HERE, 'chase_view.py'), OUT, track, str(frac), preset, path], env=e,
                   check=True, stdout=subprocess.DEVNULL)
    return path


def point(T, s, lat=0.0):
    n, step = T['n'], T['step']; s %= T['length']; f = s / step; i = int(f) % n; j = (i + 1) % n; t = f - int(f)
    return (T['x'][i] + (T['x'][j] - T['x'][i]) * t - T['ty'][i] * lat, T['y'][i] + (T['y'][j] - T['y'][i]) * t + T['tx'][i] * lat)


def cell(T, s, lat=0.0, step=1):
    """the minimap cell of a car (the HUD script's dotCells)"""
    x, y = point(T, s, lat)
    mm = T['mm']; half = mm['size'] / 2
    c = [min(47, max(0, int((half + x * mm['scale']) / mm['size'] * 48))), min(47, max(0, int((half - y * mm['scale']) / mm['size'] * 48)))]
    if step > 1: c = [c[0] - c[0] % step, c[1] - c[1] % step]
    return c


def pack_env(pack):
    return ';'.join('%d:%d:%s:%s' % p for p in pack)


def field(T, s0, pack, seed):
    """minimap dots: the pack round our car and the rest of a 32-car field spread round the lap"""
    rnd = random.Random(seed)
    cells = [cell(T, s0 + ds, lat, 2) + [('T' if skin == 't' else 'CT')] for ds, lat, key, skin in pack]
    while len(cells) < 31:
        s = s0 + rnd.uniform(-0.45, 0.4) * T['length']
        cells.append(cell(T, s, rnd.uniform(-150, 150), 2) + [rnd.choice(['T', 'CT'])])
    lead_ds = max(ds for ds, _, _, _ in pack) if pack else 0
    return cells, cell(T, s0), cell(T, s0 + lead_ds + 2500)


def race_hud(T, s0, pack, seed, pos, suf, poscol, lap, lapcol, clock, laptime, best, spd, shield, charge, standings, me_row,
             tally=('T 5', '3 CT'), turn=None, msg='', ctr='', ctrcol='white', boost=False, pad=False):
    HR.reset()
    HR.add('spr_root', 'stOn')
    if boost: HR.add('spr_root', 'stBoost')
    HR.add('spr_mmimg', 'mm_' + T['id'])
    HR.text('spr_pos', pos, poscol); HR.text('spr_suf', suf, poscol); HR.text('spr_posof', '/32', 'pink')
    HR.text('spr_lap', lap, lapcol)
    HR.text('spr_tt', tally[0], 'gold'); HR.text('spr_tct', tally[1], 'cyan')
    HR.text('spr_clock', clock, 'white'); HR.text('spr_laptime', laptime, 'white'); HR.text('spr_best', best, 'gold')
    HR.text('spr_spd', spd, 'gold' if boost else 'white')
    HR.add('spr_shfill', 'w%d' % shield); HR.add('spr_chfill', 'w%d' % charge)
    if boost: HR.add('spr_charge', 'boosting')
    HR.add('spr_spfill', 'w%d' % min(20, int(int(spd) / 70)))
    if pad: HR.add('spr_speed', 'pad')
    for i, (nm, side) in enumerate(standings):
        HR.BYID['spr_stn%d' % i].text = '%d  %s' % (i + 1, nm)
        HR.add('spr_st%d' % i, side)
    HR.add('spr_st%d' % me_row, 'me')
    if turn: HR.add('spr_turn', turn)
    if msg: HR.text('spr_msg', msg, 'cyan')
    if ctr: HR.text('spr_ctr', ctr, ctrcol)
    cells, me, lead = field(T, s0, pack, seed)
    HR.dots(cells, me, lead)


def shot_loop():
    """Crosswire: into the spiral loop round the crossing, the exit deck overhead"""
    T = TR['crosswire']; f = 0.505; s0 = f * T['length']
    pack = [(260, -170, 'meteor_boost', 'ct'), (650, 90, 'comet', 't'), (1150, -110, 'hornet_boost', 'ct'), (1750, 60, 'bastion', 't'),
            (2500, -40, 'meteor', 'ct')]
    bg = background('loop', 'crosswire', f, SKIN='t', PACK=pack_env(pack))
    race_hud(T, s0, pack, 1, '3', 'RD', 'green', 'LAP 2/3', 'gold', '1:12', '0:31.4', '0:30.9', '1194', 15, 11,
             [('NOVA', 'CT'), ('KESTREL', 'T'), ('YOU', 'T'), ('VEXIS', 'CT'), ('MARLOW', 'T'), ('ZIGGY', 'CT'), ('ORBIT', 'CT'), ('PIXL', 'T')], 2,
             turn='l1')
    return bg


def shot_pack():
    """Solar Oval just after the start: the field bunched up, boosting"""
    T = TR['oval']; f = 0.03; s0 = f * T['length']
    pack = [(150, 160, 'comet_boost', 't'), (210, -190, 'bastion', 'ct'), (340, 30, 'hornet_boost', 't'), (450, 220, 'meteor', 'ct'),
            (560, -130, 'comet', 'ct'), (690, 110, 'hornet', 't'), (830, -220, 'meteor_boost', 't'), (980, 40, 'bastion', 'ct'),
            (1150, 190, 'hornet', 'ct'), (1350, -90, 'comet', 't')]
    bg = background('pack', 'oval', f, SKIN='ct', PACK=pack_env(pack))
    race_hud(T, s0, pack, 2, '8', 'TH', 'white', 'LAP 1/3', 'gold', '0:04', '0:04.1', '-', '1312', 20, 14,
             [('BLITZ', 'T'), ('ACE', 'T'), ('RAYNE', 'CT'), ('SOLSTICE', 'CT'), ('DRIFTER', 'T'), ('NOVA', 'CT'), ('PIXL', 'T'), ('YOU', 'CT')], 7,
             tally=('T 4', '4 CT'), msg='+40 CHARGE FROM THE PULSE', boost=True, pad=True)
    return bg


def shot_jump():
    """Skyway: off the lip of a jump, the landing ahead and the cloud sea far below"""
    T = TR['skyway']; f = 0.078; s0 = f * T['length']
    pack = [(600, 120, 'hornet_boost', 'ct'), (1200, -140, 'comet', 't'), (1900, 40, 'bastion', 'ct')]
    bg = background('jump', 'skyway', f, SKIN='t', PACK=pack_env(pack), AIR=200)
    race_hud(T, s0, pack, 3, '2', 'ND', 'green', 'FINAL LAP', 'red', '1:38', '0:22.7', '0:22.1', '1340', 12, 6,
             [('KESTREL', 'CT'), ('YOU', 'T'), ('MARLOW', 'T'), ('VEXIS', 'CT'), ('NOVA', 'CT'), ('ZIGGY', 'T'), ('ACE', 'CT'), ('PIXL', 'T')], 1,
             tally=('T 6', '2 CT'), boost=True)
    return bg


def shot_grid():
    """the grid: the flyover swoops down the straight to the waiting field; last chance to swap cars"""
    T = TR['skyway']
    bg = background('grid', 'skyway', 0.8, 'fly')
    HR.reset()
    HR.add('spr_root', 'stOn', 'stPickMini')
    HR.add('spr_mmimg', 'mm_skyway')
    HR.text('spr_pos', '3', 'green'); HR.text('spr_suf', 'RD', 'green'); HR.text('spr_posof', '/32', 'pink')
    HR.text('spr_lap', 'LAP 1/3', 'gold'); HR.text('spr_tt', 'T 0', 'gold'); HR.text('spr_tct', '0 CT', 'cyan')
    HR.text('spr_clock', 'GRID', 'gold'); HR.text('spr_laptime', '-', 'white'); HR.text('spr_best', '-', 'gold')
    HR.text('spr_ctr', 'SKYWAY', 'gold'); HR.text('spr_sub', 'YOU START 3RD OF 32  -  LIGHTS IN 6', 'white')
    HR.add('spr_mcard0', 'sel')
    for i, k in enumerate(['hornet', 'meteor', 'comet', 'bastion']): HR.swap('spr_mimg%d' % i, r'^pic_', 'pic_%s_t' % k)
    cells = [cell(T, -(190 + (k // 4) * 160 + ((k // 4) % 2) * 60), ((k % 4) - 1.5) * 140, 2) + [('T' if k % 2 == 0 else 'CT')] for k in range(31)]
    HR.dots(cells, cell(T, -350), cell(T, -190))
    return bg


def gantry_view(T, behind=25):
    """the in-game results camera: circling the start gantry 1500 out and 650 up; here from the grid side"""
    import math
    x0, y0, z0 = T['x'][0], T['y'][0], T['z'][0]
    a = math.atan2(T['ty'][0], T['tx'][0]) + math.pi + math.radians(behind)
    return '%.0f,%.0f,%.0f' % (x0 + 1500 * math.cos(a), y0 + 1500 * math.sin(a), z0 + 650), '%.0f,%.0f,%.0f' % (x0, y0, z0 + 250)


def shot_results():
    """the end of a race: the results board, times and gaps, podium in gold, silver and bronze"""
    T = TR['ringworld']
    eye, at = gantry_view(T)
    bg = background('results', 'ringworld', 0.0, 'high', EYE=eye, AT=at)
    HR.reset()
    HR.add('spr_root', 'stOn', 'stRes')
    HR.add('spr_mmimg', 'mm_ringworld')
    HR.text('spr_clock', 'RESULTS', 'gold'); HR.text('spr_laptime', '0:29.8', 'white'); HR.text('spr_best', '0:29.2', 'gold')
    HR.text('spr_spd', '0', 'white'); HR.add('spr_shfill', 'w9'); HR.add('spr_chfill', 'w4')
    rows = [('1ST', 'KESTREL', '1:31.26'), ('2ND', 'YOU', '+0.38'), ('3RD', 'NOVA', '+1.92'), ('4TH', 'VEXIS', '+2.40'),
            ('5TH', 'MARLOW', '+4.07'), ('6TH', 'ZIGGY', '+5.55'), ('7TH', 'ORBIT', 'WRECKED'), ('8TH', 'PIXL', '+9.13')]
    for i, (p_, n_, t_) in enumerate(rows):
        HR.BYID['spr_rbp%d' % i].text = p_; HR.BYID['spr_rbn%d' % i].text = n_; HR.BYID['spr_rbt%d' % i].text = t_
        HR.add('spr_rb%d' % i, 'CT' if i in (0, 3, 5) else 'T')
        if i < 3: HR.add('spr_rb%d' % i, 'p%d' % (i + 1))
    HR.add('spr_rb1', 'me')
    HR.text('spr_msg', 'YOU: 2ND OF 32 - BEST LAP 0:29.2', 'cyan')
    HR.dots([cell(T, k * 400.0, 0, 2) + ['T' if k % 2 else 'CT'] for k in range(31)], cell(T, 300), cell(T, 0))
    return bg


def shot_lobby():
    """the lobby: the view circles the next track from high above while you pick a car"""
    T = TR['spire']
    import math
    r, h, zc, ang = T['ext'] * 0.95, T['ext'] * 0.6, (T['zmin'] + T['zmax']) / 2, math.radians(-50)
    bg = background('lobby', 'spire', 0.0, 'high', EYE='%.0f,%.0f,%.0f' % (r * math.cos(ang), r * math.sin(ang), T['zmax'] + h), AT='0,0,%.0f' % zc)
    HR.reset()
    HR.add('spr_root', 'stLobby', 'stPick')
    HR.text('spr_lob1', 'THE RACE STARTS IN 7', 'white')
    HR.text('spr_lob2', 'YOUR CAR: COMET - AFTERBURN  (A / D TO CHANGE)', 'gold')
    HR.text('spr_lob3', 'NEXT: SWITCHBACK SPIRE - 2 LAPS  RECORD 0:38.0 KESTREL', 'cyan')
    HR.add('spr_card2', 'sel')
    for i, k in enumerate(['hornet', 'meteor', 'comet', 'bastion']): HR.swap('spr_cimg%d' % i, r'^pic_', 'pic_%s_ct' % k)
    return bg


TRACK_VIEWS = [('oval', 0.47), ('hairpin', 0.30), ('crosswire', 0.505), ('nullgap', 0.25), ('spire', 0.35), ('ringworld', 0.25),
               ('skyway', 0.35), ('helix', 0.45)]


def shot_tracks():
    """all eight tracks in one picture, each from the racer's seat, with its name"""
    sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
    import numpy as np, pixfont
    from retro import GOLD, ICE, PURPLE, INK, MAGENTA, WHITE
    canvas = np.zeros((1080, 1920, 3), np.uint8); canvas[:] = INK
    lg = pixfont.logo('8 ORIGINAL TRACKS', 6)
    pixfont.paste(canvas, lg, (1920 - lg.shape[1]) // 2, 40)
    pixfont.draw(canvas, 960, 40 + lg.shape[0] + 18, 'EACH WITH ITS OWN SKY, SCENERY AND SET PIECE', 4, ICE, shadow=PURPLE, align='center')
    TW, TH_, G = 465, 410, 12
    for k, (tid, f) in enumerate(TRACK_VIEWS):
        pack = [(650, 110, 'comet', 'ct'), (1300, -130, 'hornet_boost', 't'), (2100, 50, 'bastion', 'ct')]
        bgp = os.path.join(DST, '_bg_track_%s.png' % tid)
        e = dict(os.environ, SIZE='960x540', SKIN='t' if k % 2 == 0 else 'ct', PACK=pack_env(pack))
        subprocess.run([sys.executable, '-I', os.path.join(HERE, 'chase_view.py'), OUT, tid, str(f), 'high', bgp], env=e, check=True,
                       stdout=subprocess.DEVNULL)
        im = Image.open(bgp).convert('RGB'); os.remove(bgp)
        cw = int(540 * TW / TH_)
        im = im.crop(((960 - cw) // 2, 0, (960 - cw) // 2 + cw, 540)).resize((TW, TH_), Image.LANCZOS)
        x = G + (k % 4) * (TW + G); y = 1080 - 2 * (TH_ + G) + (k // 4) * (TH_ + G)
        canvas[y - 4:y + TH_ + 4, x - 4:x + TW + 4] = MAGENTA
        canvas[y:y + TH_, x:x + TW] = np.array(im)
        canvas[y + TH_ - 46:y + TH_, x:x + TW] = (canvas[y + TH_ - 46:y + TH_, x:x + TW] * 0.35).astype(np.uint8)
        pixfont.draw(canvas, x + TW // 2, y + TH_ - 38, TR[tid]['title'], 3, GOLD, shadow=PURPLE, align='center')
    out = os.path.join(DST, '_bg_tracks.png')
    Image.fromarray(canvas).save(out)
    return out


def shot_info():
    """the map's own loading screen: its first slide (the logo, the controls and the four cars)"""
    d = os.path.join(OUT, 'panorama/images/map_icons/screenshots/1080p')
    return os.path.join(d, sorted(f for f in os.listdir(d) if f.endswith('.png'))[0])     # <map>.png before <map>_1.png


def save_small(im, out):
    """PNG under Steam's 1 MB a picture: as it is if it fits, else in 256 colours (looks the same on pixel art)"""
    im.save(out, optimize=True)
    if os.path.getsize(out) > 975000:
        im.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(out, optimize=True)
    assert os.path.getsize(out) <= 975000, out


SHOTS = [('1_loop', shot_loop), ('2_pack', shot_pack), ('3_jump', shot_jump), ('4_grid', shot_grid), ('5_results', shot_results),
         ('6_lobby', shot_lobby), ('7_tracks', shot_tracks), ('8_info', shot_info)]
for name, fn in SHOTS:
    if ONLY and name not in ONLY: continue
    bgpath = fn()
    out = os.path.join(DST, 'screenshot_%s.png' % name)
    if name in ('7_tracks', '8_info'):              # pictures of their own, no race HUD over them
        Image.open(bgpath).convert('RGB').save(out)
    else:
        HR.render(1920, bgpath, out)
    save_small(Image.open(out).convert('RGB'), out)
    kb = os.path.getsize(out) // 1024
    if os.path.basename(bgpath).startswith('_bg_'): os.remove(bgpath)
    print('%-10s -> %s (%d KB)' % (name, out, kb))
