#!/usr/bin/env python3
"""hole_check.py: which frame meshes show their inside (holes, inverted faces) from outside?

CS2 culls back faces, so wherever the NEAREST surface seen from a direction faces away from the viewer, the player looks through the
mesh ("Bastion's back is invisible", 10 Nov 2026 playtest). For every frame part (legs / upper) and every LOD (the .smd files next to
the .vmdl in out/addon/models/ifr/frames/<key>/), the triangles are point-sampled into a depth buffer from six directions; the share
of silhouette pixels whose nearest surface is back-facing is the hole share of that view. The winding convention is taken from the
mesh itself (the side the majority of nearest surfaces face).

usage: python -I tools/hole_check.py [--only key,..] [--limit 16] [--lods] [--res 192] [--json out.json]
exit 1 when a side view (front / back / left / right) of a part is over --limit percent; -v prints every part and view.
Sound meshes read 5-12 % (silhouette edges, cockpit interiors); Bastion's back, with its torso block in the legs model, read 29-30 %.
"""
import os, sys, json, glob, argparse
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
VIEWS = {'front': (1, 0, 0), 'back': (-1, 0, 0), 'left': (0, 1, 0), 'right': (0, -1, 0), 'top': (0, 0, 1), 'bottom': (0, 0, -1)}


def read_smd(path):
    """-> (n, 3, 3) float array of triangle corners (reference pose)"""
    tris, cur, on = [], [], False
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            s = line.strip()
            if not on:
                if s == 'triangles': on = True
                continue
            if s == 'end': break
            p = s.split()
            if len(p) < 9:      # the material line
                cur = []
                continue
            try: cur.append((float(p[1]), float(p[2]), float(p[3])))
            except ValueError: cur = []; continue
            if len(cur) == 3: tris.append(cur); cur = []
    return np.array(tris, dtype=np.float64).reshape(-1, 3, 3)


def view_holes(T, d, res):
    """share of silhouette pixels whose nearest surface faces away from a viewer looking along -d (the viewer sits at +d)"""
    d = np.array(d, dtype=np.float64)
    up = np.array((0, 0, 1.0)) if abs(d[2]) < 0.9 else np.array((1.0, 0, 0))
    r = np.cross(up, d); r /= np.linalg.norm(r); u = np.cross(d, r)
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    area = np.linalg.norm(n, axis=1)
    ok = area > 1e-9
    T, n, area = T[ok], n[ok], area[ok]
    facing = (n @ d)            # sign: which way the winding faces relative to the viewer
    P = T.reshape(-1, 3)
    x, y, z = P @ r, P @ u, P @ d
    lo = np.array((x.min(), y.min())); span = max(x.max() - lo[0], y.max() - lo[1], 1e-6)
    px = span / res
    # samples per triangle: about 3 per pixel of its projected area, at least 3
    pa = 0.5 * np.abs(facing)
    k = np.clip(np.ceil(pa / (px * px) * 3).astype(int), 3, 4000)
    idx = np.repeat(np.arange(len(T)), k)
    rng = np.random.default_rng(7)
    a = rng.random(len(idx)); b = rng.random(len(idx))
    flip = a + b > 1; a[flip] = 1 - a[flip]; b[flip] = 1 - b[flip]
    S = T[idx, 0] + (T[idx, 1] - T[idx, 0]) * a[:, None] + (T[idx, 2] - T[idx, 0]) * b[:, None]
    sx = np.clip(((S @ r - lo[0]) / px).astype(int), 0, res - 1); sy = np.clip(((S @ u - lo[1]) / px).astype(int), 0, res - 1)
    sz = S @ d
    cell = sy * res + sx
    order = np.lexsort((-sz, cell))          # per cell, the nearest sample (largest z toward the viewer) first
    cell_o = cell[order]
    first = np.ones(len(order), dtype=bool); first[1:] = cell_o[1:] != cell_o[:-1]
    nearest = order[first]
    f = facing[idx[nearest]]
    return f, len(nearest)


def part_holes(path, res):
    T = read_smd(path)
    if len(T) < 8: return None
    out, signs = {}, []
    per = {}
    for name, d in VIEWS.items():
        f, n = view_holes(T, d, res)
        per[name] = (f, n); signs.append(np.sign(f).sum())
    conv = 1.0 if sum(signs) >= 0 else -1.0     # the winding the mesh as a whole uses
    for name, (f, n) in per.items():
        out[name] = round(100.0 * float((f * conv < 0).sum()) / max(1, n), 2)
    return {'tris': int(len(T)), 'views': out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default=''); ap.add_argument('--limit', type=float, default=16.0); ap.add_argument('--res', type=int, default=192)
    ap.add_argument('--lods', action='store_true', help='also check the LOD files (coarse LODs read 10-30 %% by themselves)')
    ap.add_argument('--json', default=''); ap.add_argument('-v', action='store_true')
    ap.add_argument('--dir', default=os.path.join(ROOT, 'out', 'addon', 'models', 'ifr', 'frames'))
    a = ap.parse_args()
    only = set(k for k in a.only.split(',') if k)
    res, bad = {}, 0
    for d in sorted(glob.glob(os.path.join(a.dir, '*'))):
        key = os.path.basename(d)
        if only and key not in only: continue
        for smd in sorted(glob.glob(os.path.join(d, key + '_*.smd'))):
            part = os.path.basename(smd)[len(key) + 1:-4]
            if 'hull' in part or ('lod' in part and not a.lods): continue
            r = part_holes(smd, a.res)
            if not r: continue
            res.setdefault(key, {})[part] = r
            worst = max(((k2, v2) for k2, v2 in r['views'].items() if k2 not in ('top', 'bottom')), key=lambda kv: kv[1])   # top / bottom look into the waist cut
            flag = worst[1] > a.limit
            bad += flag
            if flag or a.v:
                print('%-18s %-12s %6d tris  worst %-6s %5.1f %%  %s%s' % (key, part, r['tris'], worst[0], worst[1],
                      ' '.join('%s %.1f' % kv for kv in r['views'].items()) if (a.v or flag) else '', '   <-- HOLES' if flag else ''))
    if a.json: json.dump(res, open(a.json, 'w'), indent=1)
    print('hole_check: %d frame(s), %d part / LOD file(s) over %.1f %%' % (len(res), bad, a.limit))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
