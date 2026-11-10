"""Damage skins for converted models: `scorched` and `wrecked` colour textures + vmats + two extra MaterialGroups in a vmdl.

  apply_vmdl(out_root, vmdl_rel)   reads the vmdl's DefaultMaterialGroup remaps, writes <tex>_scorched/_wrecked.png and
                                   <vmat>_scorched/_wrecked.vmat next to each material (the vmat is copied, only TextureColor changes, so the
                                   normal / roughness / tint / self-illum stay and a script's SetColor paint tint keeps working) and adds the
                                   groups (default group stays index 0, scorched = 1, wrecked = 2). Idempotent.
Used by create/mdl2cs2.py --damage-skins and by projects/ironframe-cs2/tools/damage_skins.py (existing conversions).
"""
import os, re, zlib
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

NAMES = ('scorched', 'wrecked')


def _fbm(h, w, rng, base=64, octaves=5, gain=0.55):
    out = np.zeros((h, w), np.float32); amp, tot = 1.0, 0.0
    cell = base
    for _ in range(octaves):
        ch, cw = max(2, h // cell + 2), max(2, w // cell + 2)
        im = Image.fromarray(rng.random((ch, cw)).astype(np.float32), 'F').resize((w, h), Image.BICUBIC)
        out += amp * np.asarray(im); tot += amp; amp *= gain; cell = max(2, cell // 2)
    out /= tot
    lo, hi = np.percentile(out, 1), np.percentile(out, 99)
    return np.clip((out - lo) / max(1e-6, hi - lo), 0, 1)


def _smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)


def _lines(h, w, rng, n, length, color, width=1, vertical_bias=0.0, blur=0.6):
    """a layer (rgb, alpha) of short bright scratches"""
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    s = max(h, w) / 1024.0
    for _ in range(n):
        x, y = rng.random() * w, rng.random() * h
        ang = (np.pi / 2 if rng.random() < vertical_bias else rng.random() * np.pi) + rng.normal(0, 0.12)
        L = length * (0.4 + rng.random()) * max(s, 0.25)
        c = tuple(int(v * (0.75 + 0.25 * rng.random())) for v in color)
        d.line([(x, y), (x + np.cos(ang) * L, y + np.sin(ang) * L)], fill=c + (255,), width=max(1, int(round(width * max(s, 0.5)))))
    if blur: im = im.filter(ImageFilter.GaussianBlur(blur * max(1.0, s)))
    a = np.asarray(im, np.float32) / 255.0
    return a[..., :3], a[..., 3:4]


def scorched(col, seed):
    h, w = col.shape[:2]; rng = np.random.default_rng(seed); c = col.astype(np.float32) / 255.0
    soot = _fbm(h, w, rng, 96, 5); fine = _fbm(h, w, rng, 6, 3, 0.7)
    m = _smooth(soot, 0.64, 0.82)[..., None]          # ~15 % coverage: soot patches, not camouflage (skink52 review)
    edge = np.exp(-((soot - 0.66) / 0.03) ** 2)[..., None]             # glowing rim where the burn starts
    out = c * 0.9                                                      # the paint stays readable: only the patches go dark
    out = out * (1 - m * 0.75) + (np.array([0.05, 0.045, 0.04]) * (0.6 + 0.8 * fine[..., None])) * m * 0.9
    out += edge * np.array([0.42, 0.17, 0.04]) * 0.55
    out *= (0.94 + 0.12 * fine[..., None])
    rgb, a = _lines(h, w, rng, max(6, int(14 * max(h, w) / 512)), 60, (255, 170, 70), 1)
    out = out * (1 - a * 0.9) + rgb * a * 0.9
    return (np.clip(out, 0, 1) * 255).astype(np.uint8)


def wrecked(col, seed):
    h, w = col.shape[:2]; rng = np.random.default_rng(seed + 7); c = col.astype(np.float32) / 255.0
    soot = _fbm(h, w, rng, 64, 6); fine = _fbm(h, w, rng, 5, 3, 0.7)
    m = _smooth(soot, 0.52, 0.72)[..., None]          # the mech stays recognisable when wrecked
    cell = max(8, min(h, w) // 12)                                     # blackened panels: blocky cells, hard edged
    gh, gw = h // cell + 2, w // cell + 2
    blocks = (rng.random((gh, gw)) < 0.14).astype(np.float32)
    blocks = np.asarray(Image.fromarray(blocks, 'F').resize((gw * cell, gh * cell), Image.NEAREST))[:h, :w, None]
    edge = np.exp(-((soot - 0.53) / 0.03) ** 2)[..., None]
    out = c * 0.68
    out = out * (1 - m * 0.9) + np.array([0.03, 0.028, 0.026]) * (0.5 + fine[..., None]) * m
    out = out * (1 - blocks * 0.85) + np.array([0.02, 0.02, 0.02]) * blocks * 0.85
    out += edge * np.array([0.5, 0.2, 0.05]) * 0.6
    rust = _smooth(_fbm(h, w, rng, 48, 4), 0.62, 0.8)[..., None] * (1 - blocks)
    out = out * (1 - rust * 0.5) + np.array([0.30, 0.13, 0.05]) * rust * 0.5
    rgb, a = _lines(h, w, rng, max(10, int(26 * max(h, w) / 512)), 140, (175, 175, 182), 1, vertical_bias=0.7, blur=0.8)      # bare metal streaks
    out = out * (1 - a * 0.75) + rgb * 0.8 * a * 0.75
    rgb, a = _lines(h, w, rng, max(4, int(10 * max(h, w) / 512)), 50, (255, 150, 50), 1)
    out = out * (1 - a * 0.9) + rgb * a * 0.9
    out *= (0.9 + 0.2 * fine[..., None])
    return (np.clip(out, 0, 1) * 255).astype(np.uint8)


def variants(png_path, force=False):
    """writes <png>_scorched.png / _wrecked.png beside the colour map; -> {name: path}"""
    stem = png_path[:-4] if png_path.lower().endswith('.png') else png_path
    outs = {n: '%s_%s.png' % (stem, n) for n in NAMES}
    if not force and all(os.path.exists(p) for p in outs.values()): return outs
    col = np.asarray(Image.open(png_path).convert('RGB'))
    seed = zlib.crc32(os.path.basename(png_path).encode())
    for n, f in (('scorched', scorched), ('wrecked', wrecked)):
        Image.fromarray(f(col, seed)).save(outs[n], optimize=True)
    return outs


def material_variants(out_root, vmat_rel):
    """-> {name: vmat rel path} (writes the png + vmat variants of one vmat)"""
    vp = os.path.join(out_root, vmat_rel.replace('/', os.sep))
    txt = open(vp, encoding='utf-8').read()
    m = re.search(r'TextureColor "([^"]+)"', txt)
    if not m: return {}
    col_rel = m.group(1); cp = os.path.join(out_root, col_rel.replace('/', os.sep))
    if not os.path.exists(cp): return {}
    variants(cp)
    res = {}
    for n in NAMES:
        new_rel = vmat_rel[:-5] + '_%s.vmat' % n
        t2 = txt.replace(col_rel, col_rel[:-4] + '_%s.png' % n, 1)
        t2 = '// damage skin %s of %s\n' % (n, os.path.basename(vmat_rel)) + t2
        open(os.path.join(out_root, new_rel.replace('/', os.sep)), 'w', newline='\n').write(t2)
        res[n] = new_rel
    return res


def _group(name, remaps):
    rm = ''.join('\t\t\t\t\t\t\t{\n\t\t\t\t\t\t\t\tfrom = "%s"\n\t\t\t\t\t\t\t\tto = "%s"\n\t\t\t\t\t\t\t},\n' % r for r in remaps)
    return '\t\t\t\t\t{\n\t\t\t\t\t\t_class = "MaterialGroup"\n\t\t\t\t\t\tname = "%s"\n\t\t\t\t\t\tremaps =\n\t\t\t\t\t\t[\n%s\t\t\t\t\t\t]\n\t\t\t\t\t},\n' % (name, rm)


def apply_vmdl(out_root, vmdl_rel):
    """-> number of materials given damage variants (0 when already done / nothing to do)"""
    p = os.path.join(out_root, vmdl_rel.replace('/', os.sep)); txt = open(p, encoding='utf-8').read()
    if 'name = "scorched"' in txt: return 0
    mm = re.search(r'_class = "DefaultMaterialGroup"\s*remaps =\s*\[(.*?)\]\s*use_global_default', txt, re.S)
    if not mm: return 0
    pairs = re.findall(r'from = "([^"]+)"\s*to = "([^"]+)"', mm.group(1))
    per = {n: [] for n in NAMES}; done = 0
    for frm, to in pairs:
        mv = material_variants(out_root, to)
        if not mv: continue
        done += 1
        for n in NAMES: per[n].append((to, mv[n]))             # from = the default group's full material path
    if not done: return 0
    anchor = 'global_default_material = ""\n\t\t\t\t\t},\n'
    if anchor not in txt: raise RuntimeError('vmdl layout not recognised: ' + vmdl_rel)
    txt = txt.replace(anchor, anchor + ''.join(_group(n, per[n]) for n in NAMES), 1)
    open(p, 'w', newline='\n').write(txt)
    return done
