"""Cut HUD backgrounds out of a banner image (a server's artwork) for the TTT HUD.

    python3 tools/hud_theme.py <banner.png> [out_dir] [--dark 0.55]

Crops are fractions of the banner's picture area (letterbox bars trimmed), chosen to miss the centred title and logo most banners have:
the left and right edges and the bottom band. Edit CROPS for other artwork. Writes kf.png (killfeed panel), sb.png (scoreboard, the left
edge mirrored), top.png (top-bar cover), shop.png into addon/panorama/images/custom_game/ttt/ (git-ignored: the artwork belongs to its
owner). Without them the HUD falls back to flat colours.
"""
import os, sys
import numpy as np
from PIL import Image, ImageFilter

#          name    size          crop (x0, y0, x1, y1) as fractions   darken  blur  mirror
CROPS = [('kf',   (960, 600),   (0.763, 0.00, 1.000, 0.34),          1.00,   0,    False),
         ('top',  (1280, 200),  (0.800, 0.40, 1.000, 0.52),          1.20,   0,    False),
         ('shop', (840, 672),   (0.000, 0.43, 0.244, 0.88),          0.90,   0,    False),
         ('sb',   (1240, 920),  (0.000, 0.08, 0.251, 0.93),          0.75,   1.5,  True)]

args = [a for a in sys.argv[1:] if not a.startswith('--')]
dark = 0.55
if '--dark' in sys.argv:
    v = sys.argv[sys.argv.index('--dark') + 1]; dark = float(v); args.remove(v)
src = args[0]
out = args[1] if len(args) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'addon', 'panorama', 'images', 'custom_game', 'ttt')
os.makedirs(out, exist_ok=True)

im = Image.open(src).convert('RGB')
lum = np.asarray(im).astype(float).mean(axis=2)
rows = np.where(lum.mean(axis=1) > 4)[0]
band = im.crop((0, rows[0] + 6, im.width, rows[-1] - 6))      # skip letterbox bars and the edge lines
W0, H0 = band.size

for name, (W, H), (fx0, fy0, fx1, fy1), d, blur, mirror in CROPS:
    c = band.crop((int(fx0 * W0), int(fy0 * H0), int(fx1 * W0), int(fy1 * H0)))
    if mirror:
        m = Image.new('RGB', (c.width * 2, c.height)); m.paste(c, (0, 0)); m.paste(c.transpose(Image.FLIP_LEFT_RIGHT), (c.width, 0)); c = m
    s = max(W / c.width, H / c.height)                           # cover, centred
    c = c.resize((max(W, round(c.width * s)), max(H, round(c.height * s))), Image.LANCZOS)
    x, y = (c.width - W) // 2, (c.height - H) // 2
    c = c.crop((x, y, x + W, y + H))
    if blur: c = c.filter(ImageFilter.GaussianBlur(blur))
    c = Image.fromarray(np.clip(np.asarray(c).astype(float) * dark * d, 0, 255).astype(np.uint8))
    c.save(os.path.join(out, name + '.png'), optimize=True)
print('wrote', ', '.join(n + '.png' for n, *_ in CROPS), 'to', os.path.normpath(out))
