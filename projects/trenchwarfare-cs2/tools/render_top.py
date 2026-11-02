"""Top-down renders of the battlefield: mortar targeting screens (digital bird's-eye, one per team), radar, paper map."""
import os, sys, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage
import layout as LY
from noise import fbm

OUT = sys.argv[1] if len(sys.argv) > 1 else '../out/addon'
GAME = sys.argv[2] if len(sys.argv) > 2 else '../out/game'
EXT = 4600.0                     # targetable square: x, y in [-EXT, EXT] (must match CONFIG.TARGET_EXT); covers the wood
N = 1024
xs = np.linspace(-EXT, EXT, N); ys = np.linspace(EXT, -EXT, N)      # image rows go from +y down
X, Y = np.meshgrid(xs, ys)
Z = LY.height(X, Y)
P, D = LY.parapet(X, Y)
bank = (D >= 2) & (D <= 116)
Zs = np.where(bank, np.maximum(Z, P), Z)
gy, gx = np.gradient(Zs, 2 * EXT / N)
light = np.array([-0.6, 0.5, 0.62]); light /= np.linalg.norm(light)
nrm = np.stack([-gx, gy, np.ones_like(Zs)], -1); nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
shade = np.clip(nrm @ light, 0, 1)
D2, _ = LY.trench_dist(X, Y)
trench = D2 < 0
ax = np.abs(X)
mud = (ax < 1520)
col = np.zeros((N, N, 3)); col[:] = (0.34, 0.36, 0.26)
col[ax < 3900] = (0.36, 0.33, 0.26)
col[mud] = (0.30, 0.26, 0.21)
n = fbm(X / 300, Y / 300, 1, 3, seed=5)[..., None]
col = col * (0.9 + 0.2 * n)
col[trench] = (0.12, 0.10, 0.08)
img = col * (0.35 + 0.75 * shade[..., None])
water = np.zeros((N, N), bool)
for (cx, cy, r, dep) in LY.CRATERS:
    if abs(cx) < 1350 and r > 95:
        water |= (X - cx) ** 2 + (Y - cy) ** 2 < (r * 0.55) ** 2
img[water] = (0.20, 0.22, 0.20)
base = np.clip(img, 0, 1)
def to_px(x, y): return ((x + EXT) / (2 * EXT) * N, (EXT - y) / (2 * EXT) * N)
im = Image.fromarray((base * 255).astype(np.uint8))
dr = ImageDraw.Draw(im)
for s in (-1, 1):
    for xw in (1390, 1235):
        for y in np.arange(-3100, 3100, 128):
            a = to_px(s * xw, y); b = to_px(s * xw, y + 110)
            dr.line([a, b], fill=(70, 60, 50), width=1)
    for (cx, cy) in LY.mortar_pits(s):
        p = to_px(cx, cy); r = 152 / (2 * EXT) * N
        dr.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), outline=(120, 105, 80), width=2)
base_img = im
os.makedirs(os.path.join(OUT, 'panorama/images/custom_game/tw'), exist_ok=True)
base_img.save(os.path.join(os.path.dirname(__file__), '..', 'preview', 'topdown.png'))

# the mortar sight shows the painted radar (forest, wood clearing, tunnels...) cropped to the targetable square
_rc = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'radar_clean.png')
if os.path.exists(_rc):
    R_ = Image.open(_rc).convert('RGB'); S_ = R_.size[0]
    rg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'radar_region.json')))
    k_ = S_ / rg['span']                                   # radar pixels per world unit; the target square may run past its edge
    box = ((-EXT - rg['x0']) * k_, (rg['y0'] - EXT) * k_, (EXT - rg['x0']) * k_, (rg['y0'] + EXT) * k_)
    canvas_ = Image.new('RGB', (int(box[2] - box[0]), int(box[3] - box[1])), (50, 58, 40))
    canvas_.paste(R_, (int(-box[0]), int(-box[1])))
    base_img = canvas_.resize((N, N), Image.LANCZOS)

def digital(img, team):
    """bird's-eye 'digital' look: luminance, edge boost, green phosphor, grid, scanlines; enemy at the top"""
    a = np.asarray(img.convert('L'), np.float32) / 255.0
    e = np.abs(ndimage.sobel(a, 0)) + np.abs(ndimage.sobel(a, 1))
    a = np.clip(a * 1.25 + e * 0.9 - 0.1, 0, 1)
    rgb = np.stack([a * 0.35, a * 0.95 + 0.04, a * 0.55 + 0.02], -1)
    k = N // 16
    grid = np.zeros((N, N), bool); grid[::k, :] = True; grid[:, ::k] = True
    rgb[grid] = rgb[grid] * 0.5 + np.array([0.1, 0.45, 0.25])
    rgb[::3] *= 0.82
    out = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    # orient: CT's enemy is -x -> rotate so -x points up; T: +x up
    out = out.rotate(-90 if team == 'ct' else 90, expand=True)
    return out.resize((768, 768), Image.LANCZOS)

for team in ('t', 'ct'):
    digital(base_img, team).save(os.path.join(OUT, 'panorama/images/custom_game/tw/target_%s.png' % team))

# radar + overview: tools/make_radar.py

# paper trench map for the plotting tables
pa = np.asarray(base_img.convert('L'), np.float32) / 255
cont = (np.abs(((Zs / 12.0) % 1) - 0.5) < 0.06).astype(np.float32)
paper = np.stack([0.86 - 0.25 * (1 - pa), 0.80 - 0.25 * (1 - pa), 0.66 - 0.22 * (1 - pa)], -1)
paper = paper * (1 - 0.25 * cont[..., None])
paper[trench] = (0.55, 0.12, 0.10)
pim = Image.fromarray((np.clip(paper, 0, 1) * 255).astype(np.uint8)).resize((512, 512), Image.LANCZOS)
pim = pim.convert('RGBA'); pim.putalpha(255)
pim.save(os.path.join(os.path.dirname(__file__), 'trench_map_small.png'))
json.dump(dict(ext=EXT, size=768), open(os.path.join(os.path.dirname(__file__), '..', 'out', 'target_map.json'), 'w'))
print('top-down renders done')
