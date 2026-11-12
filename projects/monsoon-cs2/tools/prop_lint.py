"""Offline sanity check of built procedural props (the model-side counterpart of check_mesh.py, which checks vmap meshes).

usage: python prop_lint.py [--addon ../out/addon] [names...]      (default: every prop in props.json)

Per prop, per LOD SMD: NaN / inf positions or normals, zero-length normals, degenerate triangles (area < 1e-6 u^2), triangles whose
corners are more than 2 km apart (exploded vertices), atlas UVs outside 0..1 (tiling stock materials may exceed it), SMD material
names without a vmdl remap; per vmdl: every remapped vmat and every texture it names exists (or is a CS2 game material), every hull
SMD has a non-degenerate convex hull. Exit 1 if any prop is bad. AI-generated (Claude) for skink52.
"""
import os, sys, re, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def read_smd(path):
    lines = open(path).read().split('\n')
    if 'triangles' not in lines:          # an animation SMD (nodes + skeleton only, e.g. flag_pole's anims/flag_NN.smd)
        return None, None
    i = lines.index('triangles') + 1
    mats, rows = [], []
    while i + 3 < len(lines) and lines[i] != 'end':
        mats.append(lines[i]); rows.append([lines[i + k].split()[1:9] for k in (1, 2, 3)]); i += 4
    return mats, np.array(rows, float) if rows else np.zeros((0, 3, 8))


def game_has(rel):
    try:
        import vtexread as V
        return (rel + '_c') in V.index()
    except Exception:
        return None


def lint(addon, name, info):
    errs = []
    mdir = os.path.join(addon, os.path.dirname(info['model']))
    vmdl = os.path.join(addon, info['model'])
    if not os.path.isfile(vmdl): return ['no vmdl']
    txt = open(vmdl).read()
    remap = dict(re.findall(r'from = "([^"]+)"\s*to = "([^"]+)"', txt))
    smds = re.findall(r'filename = "([^"]+\.smd)"', txt)
    for s in smds:
        p = os.path.join(addon, s)
        if not os.path.isfile(p): errs.append('missing %s' % s); continue
        mats, T = read_smd(p)
        if T is None:
            if 'skeleton' not in open(p).read(): errs.append('%s: no triangles and no skeleton' % os.path.basename(s))
            continue
        if 'hull' in os.path.basename(s):
            from scipy.spatial import ConvexHull
            try:
                h = ConvexHull(T[..., :3].reshape(-1, 3))
                if h.volume < 1.0: errs.append('%s: hull volume %.2f' % (os.path.basename(s), h.volume))
            except Exception as ex:
                errs.append('%s: hull %s' % (os.path.basename(s), type(ex).__name__))
            continue
        if not len(T): errs.append('%s: no triangles' % os.path.basename(s)); continue
        P, N, UV = T[..., :3], T[..., 3:6], T[..., 6:8]
        if not np.isfinite(T).all(): errs.append('%s: NaN/inf' % os.path.basename(s))
        if (np.linalg.norm(N, axis=2) < 0.5).any(): errs.append('%s: %d zero normals' % (os.path.basename(s), int((np.linalg.norm(N, axis=2) < 0.5).sum())))
        a = np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1) / 2
        nd = int((a < 1e-6).sum())
        if nd: errs.append('%s: %d degenerate triangles' % (os.path.basename(s), nd))
        span = np.linalg.norm(P - P.mean(1, keepdims=True), axis=2).max()
        if span > 80000: errs.append('%s: exploded triangle (%.0f u)' % (os.path.basename(s), span))
        for mname in sorted(set(mats)):
            if mname + '.vmat' not in remap and mname not in remap: errs.append('%s: material %s not remapped' % (os.path.basename(s), mname))
            if not mname.startswith('stock_'):
                sel = np.array([m == mname for m in mats])
                u = UV[sel]
                tol = 0.01 if os.path.basename(s).endswith('d.smd') else 0.002   # decimated LODs (lod_decimate *_lodNd.smd) re-project a hair out
                if (u < -tol).any() or (u > 1 + tol).any(): errs.append('%s: atlas uv outside 0..1 on %s (%.4f..%.4f)' % (os.path.basename(s), mname, u.min(), u.max()))
    for frm, vm in remap.items():
        p = os.path.join(addon, vm)
        if os.path.isfile(p):
            for k, t in re.findall(r'\t(Texture\w+) "([^"\[]+)"', open(p).read()):
                if not os.path.isfile(os.path.join(addon, t)): errs.append('%s: missing %s' % (vm, t))
        else:
            g = game_has(vm)
            if g is False: errs.append('missing vmat %s (not in the addon or the game)' % vm)
    return errs


def main(argv):
    addon = os.path.join(HERE, '..', 'out', 'addon'); names = []
    it = iter(argv)
    for a in it:
        if a == '--addon': addon = next(it)
        else: names.append(a)
    props = json.load(open(os.path.join(addon, '..', 'props.json')))
    bad = 0
    for n in (names or sorted(props)):
        e = lint(addon, n, props[n])
        if e: bad += 1; print('%s BAD: %s' % (n, '; '.join(e[:6])))
    print('prop_lint: %d props, %d bad' % (len(names or props), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
