"""Texture lookup for the radar: a material name -> tiled RGB image (from the addon's own source png/tga when it has one)
or a flat colour guessed from the name (stock CS2 materials, whose textures aren't readable from the workspace)."""
import os, re
import numpy as np
from PIL import Image

# keyword -> colour, first match wins; colour words checked first so 'concrete_painted_blue' stays blue
COLOUR_WORDS = [('black', (28, 28, 30)), ('white', (215, 215, 210)), ('red', (150, 45, 40)), ('blue', (55, 85, 150)), ('green', (60, 120, 60)),
                ('yellow', (190, 170, 60)), ('orange', (200, 120, 40)), ('purple', (110, 60, 140)), ('violet', (110, 60, 140)), ('magenta', (160, 50, 140)),
                ('pink', (200, 110, 150)), ('cyan', (60, 160, 170)), ('aqua', (60, 160, 170)), ('brown', (110, 80, 55)), ('grey', (128, 128, 128)), ('gray', (128, 128, 128))]
KINDS = [('water', (40, 90, 130)), ('coast', (40, 90, 130)), ('canal', (40, 90, 130)), ('grass', (78, 110, 52)), ('mulch', (90, 75, 50)), ('dirt', (115, 95, 70)),
         ('mud', (100, 85, 60)), ('sand', (190, 170, 125)), ('gravel', (135, 130, 120)), ('rock', (120, 115, 108)), ('stone', (140, 135, 125)),
         ('cobble', (120, 115, 105)), ('asphalt', (70, 70, 72)), ('blacktop', (70, 70, 72)), ('road', (80, 80, 80)), ('marble', (200, 195, 185)),
         ('tile', (170, 165, 150)), ('vinyl', (160, 150, 135)), ('carpet', (120, 60, 55)), ('wood', (140, 105, 65)), ('plank', (140, 105, 65)),
         ('brick', (150, 95, 75)), ('plaster', (190, 180, 160)), ('cinder', (150, 150, 145)), ('concrete', (150, 150, 145)), ('glass', (150, 180, 190)),
         ('grate', (90, 92, 95)), ('grating', (90, 92, 95)), ('fence', (110, 110, 110)), ('metal', (110, 112, 118)), ('steel', (110, 112, 118)),
         ('rubber', (50, 50, 50)), ('snow', (225, 230, 235)), ('ice', (200, 220, 235)), ('lava', (200, 80, 20)), ('dev_measure', (150, 150, 150)),
         ('spray', (160, 160, 160)), ('decal', (160, 160, 160)), ('arrow', (160, 160, 160))]
DEFAULT = (140, 140, 140)

def guess_colour(mat):
    n = mat.lower().replace('\\', '/')
    base = re.sub(r'\.vmat$', '', n.rsplit('/', 1)[-1])
    for w, c in COLOUR_WORDS:
        if re.search(r'(^|[_\-/])' + w + r'([_\-0-9]|$)', base): return c
    for w, c in KINDS:
        if w in n: return c
    m = re.search(r'dev[_/].*?(\d{2})', base)                 # dev_55, dev_gray-09, valuesand30: grey level
    if m:
        v = int(m.group(1)); return (int(v * 2.3 + 20),) * 3
    return DEFAULT

class Textures:
    def __init__(s, roots, tile_units=128.0):
        s.roots = [r for r in roots if r and os.path.isdir(r)]; s.tile = tile_units; s.cache = {}
        s.index = {}
        for r in s.roots:
            for dp, _, fs in os.walk(r):
                for f in fs:
                    fl = f.lower()
                    if fl.endswith(('.png', '.tga', '.jpg')) and not re.search(r'_(normal|mask|rough|trans|selfillum|ao|metal|height|spec|bump)\.', fl):
                        rel = os.path.relpath(os.path.join(dp, f), r).replace('\\', '/').lower()
                        s.index.setdefault(re.sub(r'\.(png|tga|jpg)$', '', rel), os.path.join(dp, f))
    def find(s, mat):
        stem = re.sub(r'^materials/', '', mat.lower().replace('\\', '/'))[:-5] if mat.lower().endswith('.vmat') else mat.lower()
        for k in (stem, stem + '_color', stem + '_diffuse', stem + '_basecolor'):
            if k in s.index: return s.index[k]
        return None
    def get(s, mat, px_per_tile):
        """(tile RGB uint8 array of px_per_tile x px_per_tile, is_texture). Flat colour arrays are 1x1."""
        key = (mat, px_per_tile)
        if key in s.cache: return s.cache[key]
        p = s.find(mat); out = None
        if p:
            try:
                im = Image.open(p).convert('RGB')
                n = max(4, int(px_per_tile))
                if im.width > 512: im = im.resize((512, int(512 * im.height / im.width)))
                out = (np.asarray(im.resize((n, n), Image.LANCZOS)), True)
            except Exception: out = None
        if out is None: out = (np.array(guess_colour(mat), dtype=np.uint8).reshape(1, 1, 3), False)
        s.cache[key] = out
        return out
