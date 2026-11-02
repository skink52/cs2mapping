# Loading screen picture, radar (overview) image, overview file and map icon.
#   panorama/images/map_icons/screenshots/1080p/<map>.png, _1, _2   loading screens (CS2 asks for <map>_png)
#   panorama/images/overheadmaps/<map>_radar.psd                     radar / overview (CS2 asks for <map>_radar_psd)
#   panorama/images/map_icons/map_icon_<map>.svg                     map icon (CS2 asks for map_icon_<map>.vsvg)
#   game/resource/overviews/<map>.txt                                where the radar sits in the world (GAME folder)
# <map> is names.MAP (mg_hellmatch).
# Title art and backgrounds come from tools/title.py (our own, not Freedoom's FreeDM logo).
# The HUD stylesheet refers to the three images so CS2 compiles them along with the HUD.
import json, os, struct, sys
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
    paste_text(base, 'DEATHMATCH INSIDE COUNTER-STRIKE 2', 130, 250, 4, white)
    paste_text(base, 'OLD-SCHOOL FPS ACTION FOR UP TO 64 PLAYERS', 130, 300, 3, grey)
    # modes, left
    y = 590
    paste_text(base, 'EVERY ROUND', 130, y, 4, gold); y += 56
    for line in ['FREE FOR ALL', 'TEAM DEATHMATCH', 'BOSS BATTLE', 'TEAM ELIMINATION', 'LAST MAN STANDING', '', '32 DEATHMATCH LEVELS', 'UP TO 4 ARENAS AT ONCE']:
        if line: paste_text(base, line, 130, y, 3, white)
        y += 36
    # controls, right
    base.alpha_composite(Image.new('RGBA', (1120, 470), (0, 0, 0, 175)), (760, 560))
    x0, x1, y = 800, 1080, 590
    paste_text(base, 'CONTROLS', x0, y, 5, gold); y += 66
    rows = [('W A S D', 'MOVE'), ('MOUSE', 'AIM'), ('MOUSE 1', 'FIRE'), ('E / SPACE', 'USE, OPEN DOORS'),
            ('R / MOUSE 2', 'NEXT WEAPON'), ('F', 'PREVIOUS WEAPON'), ('SHIFT', 'WALK'),
            ('WATCHING', 'MOUSE 1/2 PLAYER, E/SPACE ARENA'), ('CHAT', '!HELP !HUD !SPEC !AFK !BACK')]
    for a, b in rows:
        paste_text(base, a, x0, y, 3, gold); paste_text(base, b, x1, y, 3, white); y += 36
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
    paste_text(base, '32 DEATHMATCH LEVELS', 110, y, 5, gold); y += 80
    for line in ['UP TO 64 PLAYERS, 4 ARENAS', 'SAME MODE IN EVERY ARENA', '', 'FREE FOR ALL', 'TEAM DEATHMATCH',
                 'BOSS BATTLE: CO-OP VS MONSTERS', 'TEAM ELIMINATION', 'LAST MAN STANDING', '',
                 'WEAPON STARTS, STRAY MONSTERS', 'LATE JOINERS REPLACE BOTS', 'FAST SOUNDTRACK']:
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
        t = text_image(L['title'], 2, (255, 255, 255))
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

loading_screen()
p = radar()
icon()
print('loading screen, radar (pos %.0f, %.0f, scale %.2f), icon' % p)
