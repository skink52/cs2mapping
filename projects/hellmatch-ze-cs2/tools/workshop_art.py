"""Steam Workshop preview images: dist/workshop_square.jpg (main thumbnail) and dist/workshop_wide.jpg (gallery).

usage: workshop_art.py <addon_out>   (needs the sky from the build)
"""
import os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import title

OUT = sys.argv[1]
DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dist')
SKY = os.path.join(OUT, 'materials/fdm/sky/sky_color.png')

def shade(img, top, top_h, bottom, bottom_h, vignette=0.35):
    a = np.array(img.convert('RGB')).astype(np.float32)
    H, W = a.shape[:2]
    y = np.arange(H)[:, None]
    k = np.ones((H, 1), np.float32)
    k -= top * np.clip(1 - y / (H * top_h), 0, 1)
    k -= bottom * np.clip((y - H * (1 - bottom_h)) / (H * bottom_h), 0, 1)
    yy, xx = np.mgrid[0:H, 0:W]
    v = 1 - vignette * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / 2
    a *= np.clip(k, 0, 1)[..., None] * v[..., None]
    return Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert('RGBA')

def fit(text, max_w, scale, tint=(235, 235, 235)):
    """HUD-font text at the largest scale (up to `scale`) that fits `max_w`."""
    while scale > 1 and title.hud_text(text, scale, tint).width > max_w: scale -= 1
    return title.hud_text(text, scale, tint)

def centred(base, im, y):
    base.alpha_composite(im, ((base.width - im.width) // 2, y))

def save(img, name):
    os.makedirs(DIST, exist_ok=True)
    p = os.path.join(DIST, name)
    for q in (92, 88, 84, 80):
        img.convert('RGB').save(p, quality=q, optimize=True)
        if os.path.getsize(p) < 1000000: break
    print(name, img.size, '%d KB' % (os.path.getsize(p) // 1024))

# square thumbnail
sq = shade(title.scene('square', SKY), 0.55, 0.45, 0.55, 0.25)
lg = title.logo(960)
centred(sq, lg, 50)
centred(sq, fit('RETRO DEATHMATCH IN COUNTER-STRIKE 2', sq.width - 80, 5), 50 + lg.height + 10)
centred(sq, fit('32 LEVELS - UP TO 64 PLAYERS', sq.width - 80, 5, (255, 200, 60)), sq.height - 100)
save(sq, 'workshop_square.jpg')

# wide gallery image
wd = shade(title.scene('wide', SKY), 0.55, 0.45, 0.6, 0.22)
lg = title.logo(1100)
centred(wd, lg, 40)
centred(wd, fit('RETRO DEATHMATCH IN COUNTER-STRIKE 2', wd.width - 160, 6), 40 + lg.height + 10)
centred(wd, fit('32 LEVELS - 5 MODES - UP TO 64 PLAYERS', wd.width - 160, 5, (255, 200, 60)), wd.height - 140)
centred(wd, title.hud_text('USES CONTENT FROM THE FREEDOOM PROJECT (BSD LICENCE). NOT AFFILIATED WITH OR ENDORSED BY THE FREEDOOM PROJECT.', 2, (190, 190, 190)), wd.height - 50)
save(wd, 'workshop_wide.jpg')
