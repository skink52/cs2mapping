"""read/write the converted glb props (single SMD + per-material csgo_complex vmats) for re-texturing and previews"""
import os, re
import numpy as np
from PIL import Image
import geo

ADDON = os.environ.get('CS2_ADDON_OUT', os.path.join(os.path.dirname(__file__), '..', 'out', 'addon'))
SUB = os.environ.get('CS2_MODEL_PREFIX', 'ext')


def load(name):
    """{material: dict(P (n,3,3), N (n,3,3), UV (n,3,2), bone)} in SMD coordinates + header lines"""
    path = os.path.join(ADDON, 'models/%s/%s/%s.smd' % (SUB, name, name))
    L = open(path).read().split('\n')
    i = L.index('triangles')
    head = L[:i + 1]
    mats = {}
    k = i + 1
    while k < len(L) and L[k] != 'end':
        m = L[k]; rows = [L[k + j].split() for j in (1, 2, 3)]
        g = mats.setdefault(m, dict(P=[], N=[], UV=[], bone=[]))
        g['P'].append([[float(r[1]), float(r[2]), float(r[3])] for r in rows])
        g['N'].append([[float(r[4]), float(r[5]), float(r[6])] for r in rows])
        g['UV'].append([[float(r[7]), float(r[8])] for r in rows])
        g['bone'].append(rows[0][0])
        k += 4
    for g in mats.values():
        for key in ('P', 'N', 'UV'): g[key] = np.array(g[key])
    return mats, head


def save(name, mats, head, path=None):
    path = path or os.path.join(ADDON, 'models/%s/%s/%s.smd' % (SUB, name, name))
    out = list(head)
    for m, g in mats.items():
        for t in range(len(g['P'])):
            out.append(m)
            for j in range(3):
                p, n, uv = g['P'][t, j], g['N'][t, j], g['UV'][t, j]
                out.append('%s %.5f %.5f %.5f %.5f %.5f %.5f %.6f %.6f' % (g['bone'][t], p[0], p[1], p[2], n[0], n[1], n[2], uv[0], uv[1]))
    out.append('end')
    open(path, 'w', newline='\n').write('\n'.join(out) + '\n')


def vmat_tex(name, mat, key='TextureColor'):
    p = os.path.join(ADDON, 'materials/models/%s/%s/%s.vmat' % (SUB, name, mat))
    if not os.path.exists(p): p = os.path.join(ADDON, 'materials/models/%s/%s/%s.vmat' % (SUB, name, mat.split('/')[-1]))
    m = re.search(r'%s "([^"]+)"' % key, open(p).read())
    return m.group(1) if m else None


def preview_meshes(name, mats, override=None):
    """render.py meshes in hammer orientation (x,y,z) = (-smd y, smd x, smd z)"""
    out = []
    for m, g in mats.items():
        P = g['P'].reshape(-1, 3); N = g['N'].reshape(-1, 3)
        mm = geo.Mesh(); mm.V = np.stack([-P[:, 1], P[:, 0], P[:, 2]], 1); mm.N = np.stack([-N[:, 1], N[:, 0], N[:, 2]], 1)
        mm.F = np.arange(len(mm.V)).reshape(-1, 3); mm.T = np.zeros((len(mm.V), 2))
        if override and m in override:
            col = override[m]
        else:
            tp = vmat_tex(name, m)
            col = np.asarray(Image.open(os.path.join(ADDON, tp)).convert('RGB'), np.float32) / 255.0
        S0, S1 = col.shape[:2]
        uv = g['UV'].reshape(-1, 2).copy(); uv[:, 1] = 1 - uv[:, 1]
        bk = dict(color=col, normal=np.tile([0, 0, 1.0], (S0, S1, 1)), rough=np.full((S0, S1), 0.8), ao=np.ones((S0, S1)), metal=np.zeros((S0, S1)))
        out.append((mm, uv, bk))
    return out
