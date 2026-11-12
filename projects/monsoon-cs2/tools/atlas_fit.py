"""Shrink baked prop atlases that are bigger than the texel-density rule needs (build_prop.atlas_size: the smallest power of two that
reaches 1/slack of the target), without re-baking: the UVs are normalised, so halving every PNG of an atlas keeps the mapping and
the result is a filtered copy of the larger bake (playtest 1 batch P, 13 Nov 2026: the first rebuild rounded every atlas up).

usage: python atlas_fit.py [--addon ../out/addon] [--dry] names...
Reads the measured median density per atlas from tex_budget.density; halves the atlas while the halved density stays >= target/slack
and the size > min. Only opaque 'main' atlases (decal, cut and stock materials are left alone). Normal maps are renormalised.
"""
import os, sys, re, json
import numpy as np
from PIL import Image
import tex_budget as TB

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = json.load(open(os.path.join(HERE, 'toolkit.json'))).get('texel_density', {})
TARGET = float(CONF.get('px_per_unit', 12.8)); SLACK = float(CONF.get('slack', 1.4)); MIN = int(CONF.get('min', 256))


def main(argv):
    addon = os.path.join(HERE, '..', 'out', 'addon'); dry = '--dry' in argv
    names = [a for a in argv if not a.startswith('--')]
    if '--addon' in argv: addon = argv[argv.index('--addon') + 1]; names = [n for n in names if n != addon]
    props = json.load(open(os.path.join(addon, '..', 'props.json')))
    total = 0
    for n in names:
        info = props[n]
        mdir = os.path.join(addon, os.path.dirname(info['model']))
        smd = os.path.join(mdir, n + '_lod0.smd')
        rem = TB.vmdl_remaps(os.path.join(addon, info['model']))
        groups = TB.read_smd(smd)
        key = n + '_main'
        if key not in groups: continue
        vm = rem.get(key + '.vmat')
        tx = TB.vmat_textures(addon, vm)
        col = os.path.join(addon, tx['TextureColor'])
        size = Image.open(col).size[0]
        d, _ = TB.density(groups[key], (size, size))
        s = size
        while s > MIN and d * (s / 2) / size >= TARGET / SLACK: s //= 2
        if s == size: continue
        print('%-20s %4d -> %4d  (%.0f -> %.0f px/m)' % (n, size, s, d * 40, d * 40 * s / size))
        total += 1
        if dry: continue
        for k, t in tx.items():
            p = os.path.join(addon, t)
            im = Image.open(p)
            if im.size[0] != size: continue
            if k == 'TextureNormal':
                a = np.asarray(im.convert('RGB').resize((s, s), Image.LANCZOS), np.float32) / 127.5 - 1
                a /= np.linalg.norm(a, axis=-1, keepdims=True) + 1e-9
                Image.fromarray(((a + 1) * 127.5).clip(0, 255).astype(np.uint8)).save(p, optimize=True)
            else:
                im.resize((s, s), Image.LANCZOS).save(p, optimize=True)
    print('%d atlases shrunk%s' % (total, ' (dry run)' if dry else ''))


if __name__ == '__main__':
    main(sys.argv[1:])
