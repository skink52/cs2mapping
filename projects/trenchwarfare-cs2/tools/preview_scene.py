"""Renders part of the generated map (terrain + parapets + our props with their baked textures) to check placement.
usage: preview_scene.py <vmap> <out.png> cx cy radius eye_x eye_y eye_z [target_z]"""
import os, sys, json, math
import numpy as np
from PIL import Image
import dmx, layout as LY, geo, render

VMAP, OUTP = sys.argv[1], sys.argv[2]
cx, cy, rad, ex, ey, ez = map(float, sys.argv[3:9]); tz = float(sys.argv[9]) if len(sys.argv) > 9 else 0
ADDON = os.path.join(os.path.dirname(VMAP), '..')
d = dmx.DMX.load(VMAP)
cache = {}
def _tex(path, mode='RGB', size=512):
    if not os.path.exists(path): return None
    return np.asarray(Image.open(path).convert(mode).resize((size, size)), np.float32) / 255.0


def load_model(model):
    """list of (mesh, uv, textures) per SMD material group"""
    if model in cache: return cache[model]
    rel = model[:-5]
    name = os.path.basename(rel)
    if name.endswith('_dyn'): rel = rel[:-4]; name = name[:-4]
    smd = os.path.join(ADDON, rel + '_lod0.smd')
    if not os.path.exists(smd): smd = os.path.join(ADDON, rel + '.smd')
    if not os.path.exists(smd): cache[model] = None; return None
    groups = {}
    with open(smd) as f:
        tri = False; cur = None
        for line in f:
            if line.startswith('triangles'): tri = True; continue
            if not tri or line.startswith('end'): continue
            p = line.split()
            if len(p) < 9: cur = line.strip(); continue
            g = groups.setdefault(cur, ([], [], []))
            g[0].append((-float(p[2]), float(p[1]), float(p[3]))); g[1].append((-float(p[5]), float(p[4]), float(p[6]))); g[2].append((float(p[7]), 1 - float(p[8])))
    tdir = os.path.join(ADDON, 'materials', rel.rsplit('/', 1)[0])
    out = []
    for mat, (V, N, T) in groups.items():
        m = geo.Mesh(); m.V = np.array(V); m.N = np.array(N); m.T = np.zeros((len(V), 2)); m.F = np.arange(len(V)).reshape(-1, 3)
        col = nrm = None
        if mat and mat.startswith('stock_'):
            col = _tex('/tmp/claude-0/stockprev/%s.png' % mat[6:])
        elif mat:
            base = mat[:-5] if mat.endswith('_main') else mat
            col = _tex(os.path.join(tdir, '%s_color.png' % base)) if os.path.exists(os.path.join(tdir, '%s_color.png' % base)) else _tex(os.path.join(tdir, '%s_color.png' % name))
            nrm = _tex(os.path.join(tdir, '%s_normal.png' % base))
            if col is None:     # converted glb models: <name>_cN.png
                import glob
                cands = sorted(glob.glob(os.path.join(tdir, '*_c*.png')))
                col = _tex(cands[0]) if cands else None
        if col is None: col = np.full((4, 4, 3), 0.5)
        S_ = col.shape[0]
        bk = dict(color=col, normal=(nrm * 2 - 1) if nrm is not None else np.tile([0, 0, 1.0], (S_, S_, 1)), rough=np.full((S_, S_), 0.8),
                  ao=np.ones((S_, S_)), metal=np.zeros((S_, S_)))
        out.append((m, np.array(T), bk))
    cache[model] = out
    return out

scene = []
for c in d.root.get('world').get('children'):
    if c.type != 'CMapEntity': continue
    ep = c.get('entity_properties')
    if ep.get('classname') not in ('prop_static', 'prop_dynamic'): continue
    o = c.get('origin')
    if abs(o[0] - cx) > rad or abs(o[1] - cy) > rad: continue
    mdl = load_model(ep.get('model'))
    if mdl is None: continue
    a = c.get('angles'); s = c.get('scales')
    R = geo.euler(a[1], a[0], a[2]) @ np.diag(s)
    for (m, uv, bk) in mdl:
        mm = geo.Mesh(); mm.V = m.V @ R.T + np.array(o); mm.N = m.N @ geo.euler(a[1], a[0], a[2]).T; mm.F = m.F; mm.T = m.T
        scene.append((mm, uv, bk))
# terrain + parapets
xs = np.arange(cx - rad, cx + rad + 1, 16.0); ys = np.arange(cy - rad, cy + rad + 1, 16.0)
X, Y = np.meshgrid(xs, ys, indexing='ij')
for layer in ('main', 'par'):
    if layer == 'main': Z = LY.height(X, Y); valid = np.ones((len(xs) - 1, len(ys) - 1), bool)
    else:
        Z, D = LY.parapet(X, Y); ok = (D >= 2) & (D <= 116); valid = ok[:-1, :-1] & ok[1:, :-1] & ok[:-1, 1:] & ok[1:, 1:]
    V = np.stack([X, Y, Z], -1).reshape(-1, 3)
    idx = np.arange(len(V)).reshape(X.shape)
    F = []
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            if not valid[i, j]: continue
            a_, b_, c_, d_ = idx[i, j], idx[i + 1, j], idx[i + 1, j + 1], idx[i, j + 1]
            F += [(a_, b_, c_), (a_, c_, d_)]
    if not F: continue
    m = geo.Mesh(); m.V = V; m.F = np.array(F); m.T = np.zeros((len(V), 2)); m.recompute_normals(weld=False)
    col = np.full((8, 8, 3), (0.33, 0.27, 0.21) if layer == 'main' else (0.38, 0.31, 0.24))
    bk = dict(color=col, normal=np.tile([0, 0, 1.0], (8, 8, 1)), rough=np.full((8, 8), 0.9), ao=np.ones((8, 8)), metal=np.zeros((8, 8)))
    scene.append((m, np.zeros((len(V), 2)), bk))
for pe in os.environ.get('PLAYERS', '').split(';'):
    if not pe: continue
    px, py, pz = map(float, pe.split(','))
    b = geo.rbox(32, 32, 72, r=2, seg=1, center=(px, py, pz + 36))
    b.T = np.zeros((len(b.V), 2))
    scene.append((b, np.zeros((len(b.V), 2)), dict(color=np.full((8, 8, 3), (0.2, 0.35, 0.8)), normal=np.tile([0, 0, 1.0], (8, 8, 1)), rough=np.full((8, 8), 0.6), ao=np.ones((8, 8)), metal=np.zeros((8, 8)))))
tgt = tuple(map(float, os.environ['TARGET'].split(','))) if os.environ.get('TARGET') else (cx, cy, tz)
img = render.render(scene, (ex, ey, ez), tgt, 1280, 760, fov=float(os.environ.get('FOV', 60)))
Image.fromarray(img).save(OUTP)
print('rendered %d objects' % len(scene))
