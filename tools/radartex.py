"""Texture lookup for the radar: a material name -> tiled RGB image (from the addon's own source png/tga when it has one,
else the stock texture decoded from CS2's VPKs when they're given (vtexc.py), else a flat colour guessed from the name).
Blend materials: `layers(mat)` gives every colour layer in order (TextureColor1..4 / g_tColor1..4) so radar.py can mix them
by the mesh's painted blend weights."""
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
    if base.startswith('blend'):                       # blend<A><B>: CS:GO's base texture is A (blendsandgrass -> sand)
        hits = [(base.find(w), c) for w, c in KINDS if w in base]
        if hits: return min(hits)[1]
    for w, c in KINDS:
        if w in n: return c
    m = re.search(r'dev[_/].*?(\d{2})', base)                 # dev_55, dev_gray-09, valuesand30: grey level
    if m:
        v = int(m.group(1)); return (int(v * 2.3 + 20),) * 3
    return DEFAULT

LAYER_RE = re.compile(r'^(?:g_tColor|TextureColor)([1-4A-D]?)$', re.I)

def _layer_no(name):
    m = LAYER_RE.match(name)
    if not m: return None
    k = m.group(1).upper()
    return 0 if not k else ('1234'.index(k) if k.isdigit() else 'ABCD'.index(k))

class Textures:
    def __init__(s, roots, tile_units=128.0, vpks=()):
        s.roots = [r for r in roots if r and os.path.isdir(r)]; s.tile = tile_units; s.cache = {}
        s.vpk_paths = [v for v in vpks if v and os.path.isfile(v)]; s._vpks = None; s.layer_cache = {}; s.img_cache = {}
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
        # the material's own colour texture: a rebuilt CS:GO blend material is one layer whose image has another name
        # (blendsandgrass008a.vmat -> sandfloor009a.png; the name alone guessed grass, ttt_island17_pezversion 8 Nov 2026)
        for r in s.roots:
            vp = os.path.join(r, stem + '.vmat')
            if not os.path.isfile(vp): continue
            try: txt = open(vp, encoding='utf-8', errors='ignore').read()
            except OSError: continue
            for t in re.findall(r'TextureColor[A-Z0-9_]*\s+"([^"]+)"', txt):
                k = re.sub(r'\.(png|tga|jpg|psd)$', '', re.sub(r'^materials/', '', t.lower().replace('\\', '/')))
                if k in s.index: return s.index[k]
        return None
    def vpk_read(s, path):
        """bytes of a file in CS2's VPKs, or None"""
        if s._vpks is None:
            import vpk
            s._vpks = []
            for v in s.vpk_paths:
                try: s._vpks.append((v, vpk.VPK(v)))
                except Exception: pass
        path = path.lower().replace('\\', '/')
        for dp, v in s._vpks:
            if not v.has(path): continue
            arc = v.archive_of(path); d = os.path.dirname(dp); base = os.path.basename(dp).replace('_dir.vpk', '')
            try: return v.read(path, {arc: os.path.join(d, '%s_%03d.vpk' % (base, arc))} if arc is not None and arc != 0x7fff else {})
            except Exception: return None
        return None
    def layers(s, mat):
        """The material's colour layers in order: [('file', path) | ('vpk', texture path)]. One entry for an ordinary
        material, two to four for a blend. Addon source vmat first, then the stock compiled vmat_c."""
        if mat in s.layer_cache: return s.layer_cache[mat]
        out = []
        stem = re.sub(r'^materials/', '', mat.lower().replace('\\', '/'))
        stem = stem[:-5] if stem.endswith('.vmat') else stem
        for r in s.roots:
            vp = os.path.join(r, stem + '.vmat')
            if not os.path.isfile(vp): continue
            try: txt = open(vp, encoding='utf-8', errors='ignore').read()
            except OSError: continue
            got = {}
            for name, t in re.findall(r'(\w+)\s+"([^"]+)"', txt):
                k = _layer_no(name)
                if k is None or k in got: continue
                key = re.sub(r'\.(png|tga|jpg|psd)$', '', re.sub(r'^materials/', '', t.lower().replace('\\', '/')))
                if key in s.index: got[k] = ('file', s.index[key])
            out = [got[k] for k in sorted(got)]
            if out: break
        if not out and s.vpk_paths:
            raw = s.vpk_read('materials/' + stem + '.vmat_c')
            if raw:
                try:
                    import vmatc
                    kv = vmatc.parse(raw); got = {}
                    for p in kv.get('m_textureParams') or []:
                        k = _layer_no(p['m_name'])
                        if k is not None and p['m_pValue'] and k not in got: got[k] = ('vpk', p['m_pValue'])
                    out = [got[k] for k in sorted(got)]
                except Exception: out = []
        if not out:
            p = s.find(mat)
            if p: out = [('file', p)]
        s.layer_cache[mat] = out
        return out
    def image(s, src, n):
        """one layer as an n x n RGB uint8 tile (None if unreadable)"""
        key = (src, n)
        if key in s.img_cache: return s.img_cache[key]
        im = None
        try:
            if src[0] == 'file':
                im = Image.open(src[1]).convert('RGB')
            else:
                import vtexc
                raw = s.vpk_read(src[1] if src[1].endswith('_c') else src[1] + '_c')
                a = vtexc.decode(raw, max(64, min(512, n))) if raw else None
                im = Image.fromarray(a) if a is not None else None
        except Exception: im = None
        out = None
        if im is not None:
            if im.width > 512: im = im.resize((512, int(512 * im.height / im.width)))
            out = np.asarray(im.resize((n, n), Image.LANCZOS))
        s.img_cache[key] = out
        return out
    def get_layers(s, mat, px_per_tile):
        """[n x n RGB tile per colour layer] (empty when no layer image could be read)"""
        n = max(4, int(px_per_tile))
        out = [s.image(src, n) for src in s.layers(mat)]
        return out if out and all(o is not None for o in out) else []
    def get(s, mat, px_per_tile):
        """(tile RGB uint8 array of px_per_tile x px_per_tile, is_texture). Flat colour arrays are 1x1."""
        key = (mat, px_per_tile)
        if key in s.cache: return s.cache[key]
        if mat.startswith('#rgb:'):                     # flat colour given by the caller (radar_props.py: a prop's average texture colour)
            out = (np.array([int(x) for x in mat[5:].split(',')], dtype=np.uint8).reshape(1, 1, 3), False); s.cache[key] = out; return out
        out = None
        ls = s.get_layers(mat, px_per_tile)
        if ls: out = (ls[0], True)                      # the base layer (a blend's first texture)
        if out is None: out = (np.array(guess_colour(mat), dtype=np.uint8).reshape(1, 1, 3), False)
        s.cache[key] = out
        return out
