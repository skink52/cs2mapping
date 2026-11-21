# Loading screen picture, radar (overview) image, overview file and map icon.
#   panorama/images/map_icons/screenshots/1080p/<map>.png, _1, _2   loading screens (CS2 asks for <map>_png)
#   ... _3, _4, ...: one per ZE level (title, Freedoom author credit, the stage list, the level's automap with the
#   hold zones, the boss and the start); the loading screen cycles the numbered pictures
#   panorama/images/overheadmaps/<map>_radar.psd                     radar / overview (CS2 asks for <map>_radar_psd)
#   panorama/images/map_icons/map_icon_<map>.svg                     map icon (CS2 asks for map_icon_<map>.vsvg)
#   game/resource/overviews/<map>.txt                                where the radar sits in the world (GAME folder)
# <map> is names.MAP (mg_hellescape).
# Title art and backgrounds come from tools/title.py (our own, not Freedoom's FreeDM logo).
# The HUD stylesheet refers to the three images so CS2 compiles them along with the HUD.
import json, os, re, struct, sys
import numpy as np
from PIL import Image, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets, title, names

OUT = sys.argv[1]                      # out/addon (content)
GAME_OUT = sys.argv[2]                 # out/game (files for the compiled addon folder)
MAP = names.MAP
FD = assets.FD
DISCLAIMER = 'USES CONTENT FROM THE FREEDOOM PROJECT (BSD LICENCE). NOT AFFILIATED WITH OR ENDORSED BY THE FREEDOOM PROJECT.'

def glyph(code):
    g = assets.graphic('STCFN%03d' % code) if 33 <= code <= 95 else None
    return g[0] if g else None

def text_image(text, scale, tint=None):
    text = text.upper()
    gl = [glyph(ord(c)) for c in text]
    w = sum(g.shape[1] if g is not None else 4 for g in gl)
    img = np.zeros((8, max(1, w), 4), np.uint8)
    x = 0
    for g in gl:
        if g is None: x += 4; continue
        h, gw = g.shape[:2]
        img[:min(8, h), x:x + gw] = g[:8]
        x += gw
    im = Image.fromarray(img, 'RGBA').resize((max(1, w) * scale, 8 * scale), Image.NEAREST)
    if tint:
        arr = np.array(im).astype(np.float32)
        lum = arr[..., :3].max(axis=2, keepdims=True) / 255.0
        arr[..., :3] = lum * np.array(tint, np.float32)
        im = Image.fromarray(arr.clip(0, 255).astype(np.uint8), 'RGBA')
    return im

def paste_text(base, text, x, y, scale, tint=None, shadow=True):
    t = text_image(text, scale, tint)
    if shadow:
        sh = Image.new('RGBA', t.size, (0, 0, 0, 0)); sh.putalpha(t.getchannel('A'))
        base.alpha_composite(sh, (x + scale, y + scale))
    base.alpha_composite(t, (x, y))
    return t.size

# ---------------------------------------------------------------- loading screen 1920x1080
_LV = json.load(open(os.path.join(OUT, '_gen/levels.json')))
LEVEL_CREDITS = []
for _L in _LV:
    _au = ' '.join(re.sub(r'"[^"]*"', '', _L.get('author') or '').split())     # nicknames dropped to fit one line
    _c = '%s %s%s%s' % (_L['name'], _L['title'].upper(), (' BY ' + _au.upper()) if _au else '', ' (FINALE)' if _L.get('finale') else '')
    if _c not in LEVEL_CREDITS: LEVEL_CREDITS.append(_c)


def wrap(text, scale, width):
    """split text into lines no wider than `width` pixels at this scale (continuation lines indented)"""
    out, cur = [], ''
    for w in text.split():
        nxt = (cur + ' ' + w) if cur else w
        if cur and text_image(nxt, scale).width > width:
            out.append(cur); cur = '   ' + w
        else: cur = nxt
    if cur: out.append(cur)
    return out

def loading_screen():
    W, H = 1920, 1080
    bg = title.scene('wide', os.path.join(OUT, 'materials/fdm/sky/sky_color.png')).filter(ImageFilter.GaussianBlur(3))
    arr = np.array(bg).astype(np.float32) * 0.42
    yy, xx = np.mgrid[0:H, 0:W]
    vign = 1 - 0.6 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / 2
    arr *= vign[..., None]
    base = Image.fromarray(arr.clip(0, 255).astype(np.uint8)).convert('RGBA')
    base.alpha_composite(title.logo(760), (100, 40))
    gold, white, grey = (255, 200, 60), (235, 235, 235), (165, 165, 165)
    paste_text(base, 'ZOMBIE ESCAPE INSIDE COUNTER-STRIKE 2', 130, 250, 4, white)
    paste_text(base, 'HOLD THE LINE. KILL THE GUARDIAN. GET OUT.', 130, 300, 3, grey)
    # how a round goes, left
    y = 560
    paste_text(base, 'EVERY ROUND', 130, y, 4, gold); y += 56
    for line in ['BOTH TEAMS RUN THE SAME LEVEL', 'HOLD ZONES TO OPEN GATES', 'DEFEAT THE GUARDIAN', 'ESCAPE, THEN WIN THE FINALE',
                 'DIE AND YOU RISE AS A DEMON', "IN THE OTHER TEAM'S LEVEL", '']:
        if line: paste_text(base, line, 130, y, 3, white)
        y += 36
    # level credits top right, between the tagline and the controls box (round 4: seven levels no longer fit under the
    # round text without running under the controls box)
    lines = [ln for L in LEVEL_CREDITS for ln in wrap(L, 2, 1880 - 1000)]
    yc = max(292, 548 - 24 * (len(lines) + 1))     # below the title line, right of the tagline, above the controls box
    paste_text(base, 'LEVELS FROM FREEDOOM', 1000, yc, 2, gold); yc += 24
    for L in lines:
        paste_text(base, L, 1000, yc, 2, grey); yc += 24
    # controls, right
    base.alpha_composite(Image.new('RGBA', (1120, 456), (0, 0, 0, 175)), (760, 560))
    x0, x1, y = 800, 1080, 590
    paste_text(base, 'CONTROLS', x0, y, 5, gold); y += 66
    rows = [('W A S D', 'MOVE'), ('MOUSE', 'AIM'), ('MOUSE 1', 'FIRE'), ('E / SPACE', 'USE, OPEN DOORS'),
            ('R / MOUSE 2', 'NEXT WEAPON'), ('F', 'PREVIOUS WEAPON'), ('SHIFT', 'WALK'),
            ('AS A DEMON', 'MOUSE 1 CLAW / BITE'), ('', 'MOUSE 2 OR R: ABILITY'), ('CHAT', '!HELP !HUD !SPEC !AFK !BACK')]
    for a, b in rows:
        if a: paste_text(base, a, x0, y, 3, gold)
        paste_text(base, b, x1, y, 3, white); y += 36
    paste_text(base, '(/HELP WORKS TOO)', x1, y, 3, grey)
    paste_text(base, DISCLAIMER, 130, 1040, 2, grey)
    path = os.path.join(OUT, 'panorama/images/map_icons/screenshots/1080p')
    os.makedirs(path, exist_ok=True)
    # the loading screen cycles the numbered screenshots (like Valve's maps); the plain one is used for the map tile
    base.convert('RGB').save(os.path.join(path, MAP + '.png'))
    base.convert('RGB').save(os.path.join(path, MAP + '_1.png'))
    return base

def overview_screen(radar_img):
    W, H = 1920, 1080
    base = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    r = radar_img.resize((1000, 1000), Image.LANCZOS)
    base.alpha_composite(r, (900, 40))
    gold, white, grey = (255, 200, 60), (235, 235, 235), (165, 165, 165)
    base.alpha_composite(title.logo(700), (70, 50))
    y = 440
    paste_text(base, 'ZOMBIE ESCAPE', 110, y, 5, gold); y += 80
    for line in ['T AND CT EACH RUN A COPY OF THE LEVEL', 'FIRST TEAM OUT WINS', '', 'TIMED HOLDS, A BOSS STAGE,', 'A LAST STAND AT THE EXIT', '',
                 'THE DEAD COME BACK AS IMPS,', 'FLESH WORMS AND DEADFLARES', 'TO HUNT THE OTHER TEAM']:
        if line: paste_text(base, line, 110, y, 3, white)
        y += 38
    paste_text(base, DISCLAIMER, 110, 1040, 2, grey)
    path = os.path.join(OUT, 'panorama/images/map_icons/screenshots/1080p')
    base.convert('RGB').save(os.path.join(path, MAP + '_2.png'))

# ---------------------------------------------------------------- radar: every level as a Doom automap
def write_psd(path, img):
    """Flat 8-bit RGB Photoshop file (no layers, raw data): what CS2's compiler reads for *_radar_psd."""
    arr = np.array(img.convert('RGB'))
    h, w = arr.shape[:2]
    with open(path, 'wb') as f:
        f.write(b'8BPS' + struct.pack('>H6xHIIHH', 1, 3, h, w, 8, 3))
        f.write(struct.pack('>I', 0))     # colour mode data
        f.write(struct.pack('>I', 0))     # image resources
        f.write(struct.pack('>I', 0))     # layer and mask info
        f.write(struct.pack('>H', 0))     # raw image data, planar
        for c in range(3): f.write(arr[..., c].tobytes())

def radar():
    levels = json.load(open(os.path.join(OUT, '_gen/levels.json')))
    xs, ys = [], []
    for L in levels:
        bb, off = L['bb'], L['off']
        xs += [off[0] + bb[0], off[0] + bb[2]]; ys += [off[1] + bb[1], off[1] + bb[3]]
    margin = 256
    minx, maxx, miny, maxy = min(xs) - margin, max(xs) + margin, min(ys) - margin, max(ys) + margin
    size = max(maxx - minx, maxy - miny)
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    pos_x, pos_y = cx - size / 2, cy + size / 2
    R = 1024
    scale = size / R
    S = 2   # draw at 2x, then shrink for smooth lines
    img = Image.new('RGB', (R * S, R * S), (0, 0, 0))
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    to_px = lambda x, y: ((x - pos_x) / scale * S, (pos_y - y) / scale * S)
    for L in levels:
        v, off, secs = L['v'], L['off'], L['s']
        for ln in L['l']:
            a, b, flags, special, tag, fs, bs = ln[:7]
            x1, y1, x2, y2 = v[a * 2] + off[0], v[a * 2 + 1] + off[1], v[b * 2] + off[0], v[b * 2 + 1] + off[1]
            if bs < 0: col = (200, 40, 40)                               # wall
            elif secs[fs][0] != secs[bs][0]: col = (150, 110, 60)        # step / ledge
            elif secs[fs][1] != secs[bs][1]: col = (200, 180, 60)        # ceiling change
            else: continue
            d.line([to_px(x1, y1), to_px(x2, y2)], fill=col, width=2 * S if bs < 0 else S)
    img = img.resize((R, R), Image.LANCZOS).convert('RGBA')
    for L in levels:
        bb, off = L['bb'], L['off']
        px, py = to_px(off[0] + (bb[0] + bb[2]) / 2, off[1] + (bb[1] + bb[3]) / 2)
        t = text_image(L['title'] + (' (T)' if L.get('side') == 't' else ' (CT)' if L.get('side') == 'c' else ' (FINALE)' if L.get('finale') else ''), 2, (255, 255, 255))
        img.alpha_composite(t, (int(px / S - t.width / 2), int(py / S - t.height / 2)))
    path = os.path.join(OUT, 'panorama/images/overheadmaps')
    os.makedirs(path, exist_ok=True)
    write_psd(os.path.join(path, MAP + '_radar.psd'), img)
    img.convert('RGB').save(os.path.join(OUT, '_gen', 'radar_preview.png'))
    overview_screen(img)
    ov = os.path.join(GAME_OUT, 'resource/overviews')
    os.makedirs(ov, exist_ok=True)
    with open(os.path.join(ov, MAP + '.txt'), 'w', newline='\n') as f:
        f.write('"%s"\n{\n\t"material"\t"overviews/%s"\n\t"pos_x"\t"%d"\n\t"pos_y"\t"%d"\n\t"scale"\t"%.3f"\n\t"rotate"\t"0"\n\t"zoom"\t"1.0"\n}\n'
                % (MAP, MAP, round(pos_x), round(pos_y), scale))
    return pos_x, pos_y, scale

# ---------------------------------------------------------------- map icon (white, like the stock map icons)
def icon():
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
           '<path fill="#ffffff" fill-rule="evenodd" d="M32 4a28 28 0 1 0 0.01 0zM32 10a22 22 0 1 1-0.01 0z"/>'
           '<rect fill="#ffffff" x="29" y="0" width="6" height="16"/><rect fill="#ffffff" x="29" y="48" width="6" height="16"/>'
           '<rect fill="#ffffff" x="0" y="29" width="16" height="6"/><rect fill="#ffffff" x="48" y="29" width="16" height="6"/>'
           '<path fill="#ffffff" d="M21 21h6v8h10v-8h6v22h-6v-8H27v8h-6z"/></svg>\n')
    path = os.path.join(OUT, 'panorama/images/map_icons')
    os.makedirs(path, exist_ok=True)
    open(os.path.join(path, 'map_icon_%s.svg' % MAP), 'w', newline='\n').write(svg)

# ---------------------------------------------------------------- one loading screen per ZE level
STAGE_COL = [(80, 200, 255), (120, 255, 120), (255, 120, 255), (255, 200, 60), (255, 255, 255)]
MONSTER_NAMES = {'BARON': 'PAIN LORD', 'KNIGHT': 'PAIN BRINGER', 'MANCUBUS': 'COMBAT SLUG', 'ARACHNOTRON': 'TECHNOSPIDER',
                 'CYBERDEMON': 'ASSAULT TRIPOD', 'MASTERMIND': 'LARGE TECHNOSPIDER', 'CACO': 'TRILOBITE',
                 'REVENANT': 'DARK SOLDIER', 'ARCHVILE': 'FLAME BRINGER', 'PAINELEMENTAL': 'SUMMONER'}


def level_map(L, W, H):
    """the level as a Doom automap (walls red, steps brown, ceiling changes yellow) with the ZE overlay: hold zones in
    their stage colour and numbered, the boss spot, the player start"""
    from PIL import ImageDraw
    v, secs, ze = L['v'], L['s'], L.get('ze') or {}
    bb = L['bb']
    pad = 30
    sc = min((W - 2 * pad) / max(1, bb[2] - bb[0]), (H - 2 * pad) / max(1, bb[3] - bb[1]))
    ox = pad + ((W - 2 * pad) - (bb[2] - bb[0]) * sc) / 2; oy = pad + ((H - 2 * pad) - (bb[3] - bb[1]) * sc) / 2
    S = 2
    P = lambda x, y: ((ox + (x - bb[0]) * sc) * S, (oy + (bb[3] - y) * sc) * S)
    img = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    stages = ze.get('stages', [])
    zone_of = {}
    for k, st in enumerate(stages):
        z = st.get('zone') or {}
        for sid in ([z['sector']] if 'sector' in z else z.get('sectors', [])): zone_of.setdefault(sid, k)
    marks = []
    for ln in L['l']:
        a, b, flags, special, tag, fs, bs = ln[:7]
        p1, p2 = P(v[a * 2], v[a * 2 + 1]), P(v[b * 2], v[b * 2 + 1])
        if bs < 0: col, w = (200, 40, 40), 2 * S
        elif secs[fs][0] != secs[bs][0]: col, w = (150, 110, 60), S
        elif secs[fs][1] != secs[bs][1]: col, w = (200, 180, 60), S
        else: col, w = None, 0
        k = zone_of.get(fs, zone_of.get(bs)) if bs < 0 or (fs in zone_of) != (bs in zone_of) else None
        if k is not None:
            col, w = STAGE_COL[k % len(STAGE_COL)], 3 * S
            marks.append((k, p1, p2))
        if col: d.line([p1, p2], fill=col, width=w)
    for k, st in enumerate(stages):
        z = st.get('zone') or {}
        if 'box' in z:
            x1, y1, x2, y2 = z['box']; q1, q2 = P(x1, y2), P(x2, y1)
            d.rectangle([q1, q2], outline=STAGE_COL[k % len(STAGE_COL)], width=3 * S)
            marks.append((k, q1, q2))
    img = img.resize((W, H), Image.LANCZOS)
    # stage numbers at the middle of each zone, the boss, the start
    cen = {}
    for k, p1, p2 in marks:
        c = cen.setdefault(k, [0, 0, 0]); c[0] += (p1[0] + p2[0]) / 2 / S; c[1] += (p1[1] + p2[1]) / 2 / S; c[2] += 1
    for k, (x, y, n) in cen.items():
        t = text_image(str(stages[k].get('id', k + 1)), 4, STAGE_COL[k % len(STAGE_COL)])
        img.alpha_composite(t, (int(x / n - t.width / 2), int(y / n - t.height / 2)))
    for k, st in enumerate(stages):
        if 'boss' in st:
            x, y = P(*st['boss']['at'][:2]); x /= S; y /= S
            t = text_image('BOSS', 2, (255, 80, 255))
            img.alpha_composite(t, (int(x - t.width / 2), int(y - t.height / 2)))
    for t in L.get('t', []):
        if t[3] == 1:
            x, y = P(t[0], t[1]); x /= S; y /= S
            s_ = text_image('START', 2, (80, 255, 80)); img.alpha_composite(s_, (int(x - s_.width / 2), int(y - s_.height / 2)))
            break
    return img


def stage_line(st):
    if 'boss' in st:
        b = st['boss'].get('type', '')
        return 'BOSS: %s' % MONSTER_NAMES.get(b, b)
    if st.get('escape'): return 'ESCAPE: HOLD THE EXIT %dS' % st.get('hold', 0)
    return 'HOLD %dS' % st.get('hold', 0)


def level_screens(first=3):
    seen = []
    for L in _LV:
        if L.get('side') not in (None, 't') or L['base'] in seen: continue
        seen.append(L['base'])
    W, H = 1920, 1080
    path = os.path.join(OUT, 'panorama/images/map_icons/screenshots/1080p')
    gold, white, grey = (255, 200, 60), (235, 235, 235), (165, 165, 165)
    out = []
    for k, base_id in enumerate(seen):
        L = next(x for x in _LV if x['base'] == base_id and x.get('side') in (None, 't'))
        ze = L.get('ze') or {}
        bg = title.scene('wide', os.path.join(OUT, 'materials/fdm/sky/sky_color.png')).filter(ImageFilter.GaussianBlur(6))
        arr = np.array(bg).astype(np.float32) * 0.22
        base = Image.fromarray(arr.clip(0, 255).astype(np.uint8)).convert('RGBA')
        base.alpha_composite(Image.new('RGBA', (1060, 1000), (0, 0, 0, 150)), (820, 40))
        base.alpha_composite(level_map(L, 1040, 980), (830, 50))
        base.alpha_composite(title.logo(560), (90, 40))
        y = 190
        paste_text(base, (ze.get('title') or L['title']).upper(), 100, y, 6, gold); y += 70
        au = ' '.join(re.sub(r'"[^"]*"', '', L.get('author') or '').split()).upper()
        paste_text(base, 'FREEDOOM %s%s' % (L['name'], ' BY' if au else ''), 100, y, 3, white); y += 34
        # long author lists wrap at about 30 characters
        line = ''
        for wd in au.split():
            if len(line) + len(wd) + 1 > 30:
                paste_text(base, line, 100, y, 3, white); y += 34; line = wd
            else: line = (line + ' ' + wd).strip()
        if line: paste_text(base, line, 100, y, 3, white); y += 34
        y += 30
        paste_text(base, 'STAGES', 100, y, 5, gold); y += 64
        for i, st in enumerate(ze.get('stages', [])):
            col = STAGE_COL[i % len(STAGE_COL)]
            paste_text(base, '%s %s' % (st.get('id', i + 1), st.get('name', '').upper()), 100, y, 3, col); y += 32
            paste_text(base, '  ' + stage_line(st), 100, y, 2, grey); y += 36
        y += 20
        tl = ze.get('time_limit')
        if tl: paste_text(base, 'ROUND LIMIT %d:%02d' % (tl // 60, tl % 60), 100, y, 3, white); y += 40
        paste_text(base, 'FIRST TEAM OUT WINS', 100, y, 3, white)
        paste_text(base, DISCLAIMER, 100, 1040, 2, grey)
        name = '%s_%d.png' % (MAP, first + k)
        base.convert('RGB').save(os.path.join(path, name))
        out.append(name)
    return out

loading_screen()
p = radar()
icon()
print('level loading screens:', ' '.join(level_screens()))
print('loading screen, radar (pos %.0f, %.0f, scale %.2f), icon' % p)
