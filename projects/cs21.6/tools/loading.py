"""Radar (overview), loading screens and map icon for mg_cs16.

usage: python3 tools/loading.py <map.vmap> <addon out dir> <game out dir> [shot.png ...]

  radar           panorama/images/overheadmaps/mg_cs16_radar.psd: the three maps from above (floors coloured by texture,
                  lighter = higher), map names on them; game: resource/overviews/mg_cs16.txt places it in the world
  loading screens panorama/images/map_icons/screenshots/1080p/mg_cs16.png, _1, _2 ... from the shots given
                  (preview/shot.py renders of the converted maps) with a title line
  map icon        panorama/images/map_icons/map_icon_mg_cs16.svg
tools/hud.py lists these pictures in the HUD stylesheet so CS2 compiles them (as hellmatch-cs2 does).
"""
import os, sys, re, json, struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx9

VMAP, OUT, GAME = sys.argv[1:4]
SHOTS = sys.argv[4:]
MAP = 'mg_cs16'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
maps = json.load(open(os.path.join(OUT, '_gen/maps.json')))['maps']


def write_psd(path, img):
    """flat 8-bit RGB Photoshop file (no layers): what CS2's compiler reads for *_radar_psd"""
    arr = np.array(img.convert('RGB'))
    h, w = arr.shape[:2]
    with open(path, 'wb') as f:
        f.write(b'8BPS' + struct.pack('>H6xHIIHH', 1, 3, h, w, 8, 3))
        f.write(struct.pack('>I', 0) * 3 + struct.pack('>H', 0))
        for c in range(3): f.write(arr[..., c].tobytes())


# ---------------------------------------------------------------- radar from the vmap's floors
dm = dmx9.DMX.load(VMAP)
avg = {}
def colour(mat):
    if mat not in avg:
        c = (110, 110, 110)
        f = os.path.join(OUT, mat)
        if os.path.exists(f):
            m = re.search(r'TextureColor "([^"]+)"', open(f).read())
            if m and os.path.exists(os.path.join(OUT, m.group(1))):
                c = tuple(int(x) for x in np.asarray(Image.open(os.path.join(OUT, m.group(1))).convert('RGB')).reshape(-1, 3).mean(0))
        avg[mat] = c
    return avg[mat]
def walk(e, out):
    for c in e.get('children', []) or []:
        out.append(c); walk(c, out)
    return out
polys = []
for node in walk(dm.root['world'], []):
    if node.type != 'CMapMesh': continue
    md = node['meshData']; o = np.array(node['origin'])
    pos = np.array(md['vertexData']['streams'][0]['data'])
    mats = md['materials']; mi = {s.name: s['data'] for s in md['faceData']['streams']}['materialindex:0']
    ev, en, vdi = md['edgeVertexIndices'], md['edgeNextIndices'], md['vertexDataIndices']
    for f, h0 in enumerate(md['faceEdgeIndices']):
        mat = mats[mi[md['faceDataIndices'][f]]]
        if mat.startswith('materials/tools/') or 'moondome' in mat or '/sky/' in mat: continue
        L = []; h = h0
        while True:
            L.append(pos[vdi[ev[h]]] + o); h = en[h]
            if h == h0: break
        P = np.array(L)
        n = np.cross(P[1] - P[0], P[2] - P[0])
        if np.linalg.norm(n) == 0 or n[2] / np.linalg.norm(n) < 0.5: continue
        polys.append((P[:, 2].mean(), P, mat))
polys.sort(key=lambda t: t[0])
lo = np.min([m['bounds'][0] for m in maps], axis=0); hi = np.max([m['bounds'][1] for m in maps], axis=0)
size = max(hi[0] - lo[0], hi[1] - lo[1]) + 512
cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
pos_x, pos_y = cx - size / 2, cy + size / 2
R, SS = 1024, 2
scale = size / R
img = Image.new('RGB', (R * SS, R * SS), (0, 0, 0))
d = ImageDraw.Draw(img)
px = lambda x, y: ((x - pos_x) / scale * SS, (pos_y - y) / scale * SS)
for z, P, mat in polys:
    m = next((m for m in maps if m['bounds'][0][0] - 64 <= P[:, 0].mean() <= m['bounds'][1][0] + 64 and m['bounds'][0][1] - 64 <= P[:, 1].mean() <= m['bounds'][1][1] + 64), None)
    if not m: continue
    k = 0.35 + 0.65 * (z - m['bounds'][0][2]) / max(1, m['bounds'][1][2] - m['bounds'][0][2])
    d.polygon([px(p[0], p[1]) for p in P], fill=tuple(int(v * k) for v in colour(mat)))
img = img.resize((R, R), Image.LANCZOS)
d = ImageDraw.Draw(img)
f = ImageFont.truetype(FONT, 22)
for m in maps:
    x, y = px((m['bounds'][0][0] + m['bounds'][1][0]) / 2, m['bounds'][1][1])
    d.text((x / SS, max(30, y / SS - 6)), m['title'], font=f, fill=(255, 220, 140), anchor='md', stroke_width=2, stroke_fill=(0, 0, 0))
    for s in m['sites']:
        sx, sy = px((s['mins'][0] + s['maxs'][0]) / 2, (s['mins'][1] + s['maxs'][1]) / 2)
        d.text((sx / SS, sy / SS), s['letter'], font=f, fill=(255, 80, 60), anchor='mm', stroke_width=2, stroke_fill=(0, 0, 0))
path = os.path.join(OUT, 'panorama/images/overheadmaps'); os.makedirs(path, exist_ok=True)
write_psd(os.path.join(path, MAP + '_radar.psd'), img)
os.makedirs(os.path.join(OUT, '_gen'), exist_ok=True)
img.save(os.path.join(OUT, '_gen/radar_preview.png'))
ov = os.path.join(GAME, 'resource/overviews'); os.makedirs(ov, exist_ok=True)
open(os.path.join(ov, MAP + '.txt'), 'w', newline='\n').write(
    '"%s"\n{\n\t"material"\t"overviews/%s_radar"\n\t"pos_x"\t"%d"\n\t"pos_y"\t"%d"\n\t"scale"\t"%.3f"\n\t"rotate"\t"0"\n\t"zoom"\t"1.0"\n}\n'
    % (MAP, MAP, round(pos_x), round(pos_y), scale))

# ---------------------------------------------------------------- loading screens: map shots with a title line
shots_dir = os.path.join(OUT, 'panorama/images/map_icons/screenshots/1080p'); os.makedirs(shots_dir, exist_ok=True)
big, small = ImageFont.truetype(FONT, 64), ImageFont.truetype(FONT, 30)
for i, shot in enumerate(SHOTS):
    im = Image.open(shot).convert('RGB').resize((1920, 1080), Image.LANCZOS)
    ov_ = Image.new('RGBA', im.size, (0, 0, 0, 0)); od = ImageDraw.Draw(ov_)
    od.rectangle([0, 860, 1920, 1080], fill=(0, 0, 0, 150))
    im = Image.alpha_composite(im.convert('RGBA'), ov_)
    dd = ImageDraw.Draw(im)
    dd.text((80, 890), 'COUNTER-STRIKE 1.6', font=big, fill=(255, 176, 0))
    dd.text((80, 975), 'de_dust2  -  de_train  -  de_nuke      F in a buy zone: buy menu      !help', font=small, fill=(235, 235, 235))
    im.convert('RGB').save(os.path.join(shots_dir, MAP + ('_%d' % i if i else '') + '.png'))

# ---------------------------------------------------------------- map icon: "1.6" in a crosshair ring (white, like the stock icons)
icons = os.path.join(OUT, 'panorama/images/map_icons'); os.makedirs(icons, exist_ok=True)
open(os.path.join(icons, 'map_icon_%s.svg' % MAP), 'w', newline='\n').write(
    '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
    '<path fill="#ffffff" fill-rule="evenodd" d="M32 4a28 28 0 1 0 0.01 0zM32 9a23 23 0 1 1-0.01 0z"/>'
    '<rect fill="#ffffff" x="30" y="0" width="4" height="12"/><rect fill="#ffffff" x="30" y="52" width="4" height="12"/>'
    '<rect fill="#ffffff" x="0" y="30" width="12" height="4"/><rect fill="#ffffff" x="52" y="30" width="12" height="4"/>'
    # "1.6" in blocks (no fonts in the icon)
    '<rect fill="#ffffff" x="19" y="22" width="4" height="20"/><rect fill="#ffffff" x="27" y="38" width="4" height="4"/>'
    '<rect fill="#ffffff" x="35" y="22" width="11" height="4"/><rect fill="#ffffff" x="35" y="22" width="4" height="20"/>'
    '<rect fill="#ffffff" x="35" y="30" width="11" height="4"/><rect fill="#ffffff" x="42" y="30" width="4" height="12"/>'
    '<rect fill="#ffffff" x="35" y="38" width="11" height="4"/></svg>\n')
json.dump({'shots': len(SHOTS)}, open(os.path.join(OUT, '_gen/loading.json'), 'w'))
print('radar pos %d %d scale %.2f; %d loading screens; icon' % (pos_x, pos_y, scale, len(SHOTS)))
