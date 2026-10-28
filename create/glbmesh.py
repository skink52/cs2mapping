"""Load a single-texture glTF binary (.glb, e.g. from Tripo3D), decimate it and render previews.

load(path) -> V (n,3) in metres, glTF Y-up; UV (n,2); F (m,3); base colour PIL image
decimate(V, UV, F, cell): seam-aware vertex clustering. Every grid cell gets one position (the point that best fits the
planes of its faces, a quadric solve pulled towards the mean); vertices keep their UV chart, so each chart's vertices in
a cell share a UV (the chart's mean there) while every chart uses the cell's position - no cracks along UV seams.
"""
import struct, json, io
import numpy as np
from PIL import Image

CT = {5120: 'i1', 5121: 'u1', 5122: 'i2', 5123: 'u2', 5125: 'u4', 5126: 'f4'}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}

def _mat4(n):
    if 'matrix' in n: return np.array(n['matrix'], np.float64).reshape(4, 4).T
    M = np.eye(4); t = n.get('translation', [0, 0, 0]); x, y, z, w = n.get('rotation', [0, 0, 0, 1]); s = n.get('scale', [1, 1, 1])
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M[:3, :3] = R * np.array(s); M[:3, 3] = t
    return M

def load(path):
    d = open(path, 'rb').read()
    off = 12; ch = []
    while off < len(d):
        cl, _ = struct.unpack_from('<II', d, off); ch.append(d[off + 8:off + 8 + cl]); off += 8 + cl
    g = json.loads(ch[0]); b = ch[1]
    def acc(i):
        a = g['accessors'][i]; bv = g['bufferViews'][a['bufferView']]; n = NC[a['type']]; dt = np.dtype(CT[a['componentType']])
        st = bv.get('byteStride', n * dt.itemsize); o = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        raw = np.frombuffer(b, np.uint8, count=st * (a['count'] - 1) + n * dt.itemsize, offset=o)
        return np.lib.stride_tricks.as_strided(raw, (a['count'], n * dt.itemsize), (st, 1)).copy().view(dt).reshape(a['count'], n).astype(np.float64)
    # world transform of the first node that holds a mesh
    W = np.eye(4); mesh = 0
    def walk(i, P):
        nonlocal W, mesh
        n = g['nodes'][i]; M = P @ _mat4(n)
        if 'mesh' in n: W = M; mesh = n['mesh']; return True
        return any(walk(c, M) for c in n.get('children', []))
    for r in g['scenes'][g.get('scene', 0)]['nodes']:
        if walk(r, np.eye(4)): break
    Vs, UVs, Fs = [], [], []; base = 0; tex = None
    for p in g['meshes'][mesh]['primitives']:
        V = acc(p['attributes']['POSITION']); UV = acc(p['attributes']['TEXCOORD_0'])
        F = acc(p['indices']).astype(np.int64).reshape(-1, 3) if 'indices' in p else np.arange(len(V)).reshape(-1, 3)
        V = (np.c_[V, np.ones(len(V))] @ W.T)[:, :3]
        Vs.append(V); UVs.append(UV); Fs.append(F + base); base += len(V)
        if tex is None:
            mat = g['materials'][p.get('material', 0)]
            ti = mat.get('pbrMetallicRoughness', {}).get('baseColorTexture', {}).get('index')
            if ti is not None:
                im = g['images'][g['textures'][ti]['source']]; bv = g['bufferViews'][im['bufferView']]
                o = bv.get('byteOffset', 0)
                tex = Image.open(io.BytesIO(b[o:o + bv['byteLength']])).convert('RGB')
    return np.vstack(Vs), np.vstack(UVs), np.vstack(Fs), tex

def _charts(UV, F):
    """UV chart per vertex: vertices joined by faces (vertices at the same UV seam are already split in glTF)"""
    n = len(UV)
    parent = np.arange(n)
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    # union along face edges, vectorised by repeated pointer jumping
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    lab = np.arange(n)
    for _ in range(64):
        m = np.minimum(lab[e[:, 0]], lab[e[:, 1]])
        new = lab.copy()
        np.minimum.at(new, e[:, 0], m); np.minimum.at(new, e[:, 1], m)
        new = new[new]
        if np.array_equal(new, lab): break
        lab = new
    return lab

def weld(V, UV, F, eps=1e-6):
    """merge vertices with the same position AND uv (glTF exports often duplicate them per face)"""
    key = np.round(np.c_[V / eps * 1e-3, UV * 1e5]).astype(np.int64)
    _, idx, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    return V[idx], UV[idx], inv.reshape(-1)[F]

def decimate(V, UV, F, cell):
    lab = _charts(UV, F)
    q = np.floor((V - V.min(0)) / cell).astype(np.int64)
    ck = q[:, 0] * 73856093 ^ q[:, 1] * 19349663 ^ q[:, 2] * 83492791
    _, cid = np.unique(ck, return_inverse=True); cid = cid.reshape(-1)
    nc = cid.max() + 1
    # face planes -> quadric per cell
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    nrm = np.cross(b - a, c - a); area = np.linalg.norm(nrm, axis=1)
    nrm = nrm / np.maximum(area, 1e-12)[:, None]; dd = -(nrm * a).sum(1)
    A = np.zeros((nc, 3, 3)); bb = np.zeros((nc, 3))
    w = area
    for k in range(3):
        cc = cid[F[:, k]]
        np.add.at(A, cc, (w[:, None, None] * nrm[:, :, None] * nrm[:, None, :]))
        np.add.at(bb, cc, -(w * dd)[:, None] * nrm)
    cnt = np.bincount(cid, minlength=nc).astype(float)
    mean = np.zeros((nc, 3)); np.add.at(mean, cid, V); mean /= np.maximum(cnt, 1)[:, None]
    reg = (np.trace(A, axis1=1, axis2=2) * 0.05 + 1e-9)[:, None, None] * np.eye(3)
    P = np.linalg.solve(A + reg, (bb + (reg[:, 0, 0])[:, None] * mean)[..., None])[..., 0]
    # keep the solved point inside its cell's reach
    off = P - mean; lim = cell * 0.9
    P = mean + np.clip(off, -lim, lim)
    # new vertices: (cell, chart)
    key = cid * (lab.max() + 1) + lab
    uk, nid = np.unique(key, return_inverse=True); nid = nid.reshape(-1)
    nv = len(uk)
    NU = np.zeros((nv, 2)); np.add.at(NU, nid, UV); NU /= np.bincount(nid, minlength=nv)[:, None]
    NV = P[uk // (lab.max() + 1)]
    NF = nid[F]
    ok = (NF[:, 0] != NF[:, 1]) & (NF[:, 1] != NF[:, 2]) & (NF[:, 2] != NF[:, 0])
    NF = NF[ok]
    NF = np.unique(np.sort(NF, 1), axis=0, return_index=True)[1]
    NF = nid[F][ok][np.sort(NF)]
    used = np.unique(NF); remap = -np.ones(nv, np.int64); remap[used] = np.arange(len(used))
    return NV[used], NU[used], remap[NF]

def decimate_to(V, UV, F, target):
    """binary search the cell size for about `target` triangles"""
    ext = (V.max(0) - V.min(0)).max()
    lo, hi = ext / 2000, ext / 20
    best = None
    for _ in range(14):
        mid = (lo * hi) ** 0.5
        r = decimate(V, UV, F, mid)
        if len(r[2]) > target: lo = mid
        else: hi = mid; best = r
        if best is not None and abs(len(best[2]) - target) < target * 0.06: break
    return best if best is not None else r

def render(V, UV, F, tex, eye, target, W=480, H=360, fov=35, bg=(14, 14, 22)):
    """textured z-buffer render with a little head-on shading (for previews only)"""
    eye = np.asarray(eye, float); f = np.asarray(target, float) - eye; f /= np.linalg.norm(f)
    r = np.cross(f, (0, 0, 1)); r /= np.linalg.norm(r); u = np.cross(r, f)
    cam = (V - eye) @ np.stack([r, u, f]).T
    fpx = 0.5 * W / np.tan(np.radians(fov) / 2)
    z = cam[:, 2]; sx = W / 2 + fpx * cam[:, 0] / np.maximum(z, 1e-3); sy = H / 2 - fpx * cam[:, 1] / np.maximum(z, 1e-3)
    T = np.asarray(tex.convert('RGB'), np.float32); th, tw = T.shape[:2]
    img = np.zeros((H, W, 3), np.float32); img[:] = bg; zb = np.full((H, W), np.inf)
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    n = np.cross(b - a, c - a); n /= np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
    shade = 0.55 + 0.45 * np.abs(n @ -f)
    for k in np.argsort(-z[F].mean(1)):
        i0, i1, i2 = F[k]
        if min(z[i0], z[i1], z[i2]) < 1e-3: continue
        xs = np.array([sx[i0], sx[i1], sx[i2]]); ys = np.array([sy[i0], sy[i1], sy[i2]])
        x0, x1 = max(int(xs.min()), 0), min(int(xs.max()) + 1, W - 1); y0, y1 = max(int(ys.min()), 0), min(int(ys.max()) + 1, H - 1)
        if x1 < x0 or y1 < y0: continue
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
        if abs(den) < 1e-9: continue
        l0 = ((ys[1] - ys[2]) * (X - xs[2]) + (xs[2] - xs[1]) * (Y - ys[2])) / den
        l1 = ((ys[2] - ys[0]) * (X - xs[2]) + (xs[0] - xs[2]) * (Y - ys[2])) / den
        l2 = 1 - l0 - l1
        m = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
        if not m.any(): continue
        zz = l0 * z[i0] + l1 * z[i1] + l2 * z[i2]
        sub = zb[y0:y1 + 1, x0:x1 + 1]
        m &= zz < sub
        if not m.any(): continue
        uu = l0 * UV[i0, 0] + l1 * UV[i1, 0] + l2 * UV[i2, 0]; vv = l0 * UV[i0, 1] + l1 * UV[i1, 1] + l2 * UV[i2, 1]
        tx = np.clip((uu % 1) * tw, 0, tw - 1).astype(int); ty = np.clip((vv % 1) * th, 0, th - 1).astype(int)
        sub[m] = zz[m]
        img[y0:y1 + 1, x0:x1 + 1][m] = T[ty[m], tx[m]] * shade[k]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
