"""Rebuild CS:GO displacements the importer dropped, straight from the BSP (dispinfo/dispverts), as closed meshes:
displaced top surface with the original texture projection, 4-unit toolsnodraw back and sides.
Usage: disprestore.py <vmap in> <bsp> <vmap out>   (SUB maps materials with no CS2 copy to a stand-in)"""
import struct, numpy as np

def load_disps(path):
    d = open(path, 'rb').read()
    L = [struct.unpack_from('<iii4s', d, 8 + 16 * i) for i in range(64)]
    def lump(i): o, n, v, c = L[i]; return d[o:o + n]
    verts = np.frombuffer(lump(3), '<f4').reshape(-1, 3).astype(np.float64)
    edges = np.frombuffer(lump(12), '<u2').reshape(-1, 2)
    surf = np.frombuffer(lump(13), '<i4')
    ti = lump(6); tex = [struct.unpack_from('<16f2i', ti, i * 72) for i in range(len(ti) // 72)]
    td = lump(2); tdata = [struct.unpack_from('<3f5i', td, i * 32) for i in range(len(td) // 32)]
    sdt = np.frombuffer(lump(44), '<i4'); sd = lump(43)
    def tname(t):
        off = sdt[tdata[t][3]]; return sd[off:sd.index(b'\0', off)].decode('latin1').lower()
    di = lump(26); dv = np.frombuffer(lump(33), '<f4').reshape(-1, 5).astype(np.float64)
    fl = lump(7)
    out = []
    for i in range(len(fl) // 56):
        planenum, side, onnode, fe, ne, texinfo, dispinfo = struct.unpack_from('<HBBihhh', fl, i * 56)
        if dispinfo < 0: continue
        corners = []
        for k in range(fe, fe + ne):
            s = surf[k]; corners.append(verts[edges[s][0]] if s >= 0 else verts[edges[-s][1]])
        start = np.array(struct.unpack_from('<3f', di, dispinfo * 176))
        vstart, tstart, power = struct.unpack_from('<3i', di, dispinfo * 176 + 12)
        c0 = int(np.argmin([np.linalg.norm(c - start) for c in corners]))
        C = [corners[(c0 + k) % 4] for k in range(4)]
        n = 2 ** power + 1
        base = np.zeros((n, n, 3)); pos = np.zeros((n, n, 3)); alpha = np.zeros((n, n))
        for r in range(n):
            a = C[0] + (C[1] - C[0]) * r / (n - 1)
            b = C[3] + (C[2] - C[3]) * r / (n - 1)
            for c in range(n):
                p = a + (b - a) * c / (n - 1)
                v = dv[vstart + r * n + c]
                base[r, c] = p; pos[r, c] = p + v[:3] * v[3]; alpha[r, c] = v[4]
        t = tex[texinfo]
        s_vec = np.array(t[0:4]); t_vec = np.array(t[4:8])
        w, h = tdata[t[17]][4], tdata[t[17]][5]
        fn = np.cross(C[1] - C[0], C[3] - C[0]); fn /= np.linalg.norm(fn)
        out.append(dict(face=i, mat=tname(t[17]), n=n, base=base, pos=pos, alpha=alpha, s=s_vec, t=t_vec, w=w, h=h, corners=np.array(C), fnormal=fn))
    return out

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx
from vmapedit import Map

VMAP, BSP, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
SUB = {'nature/blendgrassgravel001a': 'grass/hr_grass/grass_b', 'de_aztec/road01_cheap': 'de_aztec/hpe_aztec_stone01_dirt'}
NODRAW = b'materials/tools/toolsnodraw.vmat'
THICK = 4.0

m = Map(VMAP)
# template: an imported world mesh with the standard stream layout
tmpl = None
for n, _ in m.walk():
    if m.type(n) == b'CMapMesh':
        md = m.g(n, b'meshData')
        fd = dmx.get(m.E[md], b'faceData')
        names = [m.E[s]['name'] for s in dmx.get(m.E[fd], b'streams')]
        if names == [b'textureScale:0', b'textureAxisU:0', b'textureAxisV:0', b'materialindex:0', b'flags:0', b'lightmapScaleBias:0']:
            tmpl = n; break
assert tmpl is not None

def stream(arr_el, prefix):
    for s in dmx.get(m.E[arr_el], b'streams'):
        if m.E[s]['name'].startswith(prefix): return m.E[s]
def setd(el, name, v):
    for a in el['attrs']:
        if a[0] == name: a[2] = v; return
    raise KeyError(name)

def build(d):
    n = d['n']; P = d['pos']; B = d['base']
    # outward normal of the original face: Source faces wind clockwise, so flip the corner cross product
    N0 = -d['fnormal']
    # per-vertex smooth normals of the displaced grid
    gu = np.gradient(P, axis=1); gv = np.gradient(P, axis=0)
    VN = np.cross(gu, gv)
    if np.mean(np.einsum('ijk,k->ij', VN, N0)) < 0: VN = -VN
    VN /= np.linalg.norm(VN, axis=2, keepdims=True) + 1e-12
    top = P.reshape(-1, 3); bot = (P - VN * THICK).reshape(-1, 3)
    verts = np.vstack([top, bot]); off = n * n
    idx = lambda r, c: r * n + c
    faces = []  # (loop, kind)
    Bf = B.reshape(-1, 3)
    flip = np.dot(np.cross(Bf[idx(0, 1)] - Bf[idx(0, 0)], Bf[idx(1, 1)] - Bf[idx(0, 0)]), N0) < 0
    for r in range(n - 1):
        for c in range(n - 1):
            q = [idx(r, c), idx(r, c + 1), idx(r + 1, c + 1), idx(r + 1, c)]
            if flip: q = q[::-1]
            faces.append((q, 'top'))
            faces.append(([x + off for x in q[::-1]], 'bot'))
    # sides: walk the boundary in the same direction as the top faces use it
    ring = [idx(0, c) for c in range(n - 1)] + [idx(r, n - 1) for r in range(n - 1)] + \
           [idx(n - 1, c) for c in range(n - 1, 0, -1)] + [idx(r, 0) for r in range(n - 1, 0, -1)]
    tophe = set()
    for q, k in faces:
        if k == 'top':
            for i in range(4): tophe.add((q[i], q[(i + 1) % 4]))
    for i in range(len(ring)):
        x, y = ring[i], ring[(i + 1) % len(ring)]
        a, b = (x, y) if (x, y) in tophe else (y, x)
        faces.append(([b, a, a + off, b + off], 'side'))
    # half-edges
    he_id = {}; nund = 0
    for q, _ in faces:
        for i in range(len(q)):
            a, b = q[i], q[(i + 1) % len(q)]
            if (b, a) in he_id: he_id[(a, b)] = he_id[(b, a)] ^ 1
            else: he_id[(a, b)] = 2 * nund; nund += 1
    nhe = 2 * nund
    assert len(he_id) == nhe, 'mesh not closed'
    evi = [0] * nhe; eni = [0] * nhe; efi = [0] * nhe; vei = [0] * len(verts); fei = []
    for f, (q, _) in enumerate(faces):
        hs = [he_id[(q[i], q[(i + 1) % len(q)])] for i in range(len(q))]
        fei.append(hs[0])
        for i, h in enumerate(hs):
            evi[h] = q[(i + 1) % len(q)]; eni[h] = hs[(i + 1) % len(hs)]; efi[h] = f; vei[q[i]] = h
    # texture projection from the CS:GO texinfo
    s, t = d['s'], d['t']; su = 1 / np.linalg.norm(s[:3]); sv = 1 / np.linalg.norm(t[:3])
    au = list(s[:3] * su) + [float(s[3])]; av = list(t[:3] * sv) + [float(t[3])]
    W, H = max(d['w'], 1), max(d['h'], 1)
    baseflat = np.vstack([B.reshape(-1, 3), B.reshape(-1, 3)])
    fv_tc = [None] * nhe; fv_n = [None] * nhe; fv_t = [None] * nhe
    VNf = np.vstack([VN.reshape(-1, 3), -VN.reshape(-1, 3)])
    for f, (q, k) in enumerate(faces):
        pts = verts[q]; fn = np.cross(pts[1] - pts[0], pts[2] - pts[0]); fn /= np.linalg.norm(fn) + 1e-12
        for i in range(len(q)):
            h = he_id[(q[i - 1], q[i])]  # half-edge arriving at q[i]
            v = q[i]
            if k == 'top':
                p = baseflat[v]
                fv_tc[h] = [float((p @ s[:3] + s[3]) / W), float((p @ t[:3] + t[3]) / H)]
                nn = VNf[v]
            else:
                fv_tc[h] = [0.0, 0.0]; nn = fn
            tg = np.array(au[:3]) - nn * np.dot(au[:3], nn)
            if np.linalg.norm(tg) < 1e-6: tg = np.cross(nn, [0, 0, 1]) if abs(nn[2]) < 0.9 else np.cross(nn, [0, 1, 0])
            tg /= np.linalg.norm(tg)
            fv_n[h] = [float(x) for x in nn]; fv_t[h] = [float(x) for x in tg] + [-1.0]
    mat = SUB.get(d['mat'], d['mat'])
    matpath = ('materials/' + mat + '.vmat').encode()
    mats = [matpath] if matpath == NODRAW else [matpath, NODRAW]
    fmat = [0 if k == 'top' else len(mats) - 1 for _, k in faces]
    nf = len(faces)
    # copy the template node and fill it
    memo = {}; nid = [m.next_node_id()]
    node = m.import_subtree(m, tmpl, memo, nid)
    md = m.g(node, b'meshData'); MD = m.E[md]
    ctr = verts.mean(0)
    setd(MD, b'vertexEdgeIndices', vei); setd(MD, b'vertexDataIndices', list(range(len(verts))))
    setd(MD, b'edgeVertexIndices', evi); setd(MD, b'edgeOppositeIndices', [h ^ 1 for h in range(nhe)])
    setd(MD, b'edgeNextIndices', eni); setd(MD, b'edgeFaceIndices', efi)
    setd(MD, b'edgeDataIndices', [h // 2 for h in range(nhe)]); setd(MD, b'edgeVertexDataIndices', list(range(nhe)))
    setd(MD, b'faceEdgeIndices', fei); setd(MD, b'faceDataIndices', list(range(nf)))
    setd(MD, b'materials', mats)
    vd = dmx.get(MD, b'vertexData'); setd(m.E[vd], b'size', len(verts))
    setd(stream(vd, b'position'), b'data', [[float(x) for x in p - ctr] for p in verts])
    fvd = dmx.get(MD, b'faceVertexData'); setd(m.E[fvd], b'size', nhe)
    setd(stream(fvd, b'texcoord'), b'data', fv_tc); setd(stream(fvd, b'normal'), b'data', fv_n); setd(stream(fvd, b'tangent'), b'data', fv_t)
    ed = dmx.get(MD, b'edgeData'); setd(m.E[ed], b'size', nund); setd(stream(ed, b'flags'), b'data', [0] * nund)
    fd = dmx.get(MD, b'faceData'); setd(m.E[fd], b'size', nf)
    setd(stream(fd, b'textureScale'), b'data', [[float(su), float(sv)] if k == 'top' else [0.25, 0.25] for _, k in faces])
    setd(stream(fd, b'textureAxisU'), b'data', [au if k == 'top' else [1.0, 0.0, 0.0, 0.0] for _, k in faces])
    setd(stream(fd, b'textureAxisV'), b'data', [av if k == 'top' else [0.0, 0.0, -1.0, 0.0] for _, k in faces])
    setd(stream(fd, b'materialindex'), b'data', fmat)
    setd(stream(fd, b'flags'), b'data', [0] * nf); setd(stream(fd, b'lightmapScaleBias'), b'data', [0] * nf)
    sd = dmx.get(MD, b'subdivisionData'); setd(m.E[sd], b'subdivisionLevels', [0] * nhe)
    setd(m.E[node], b'origin', [float(x) for x in ctr]); setd(m.E[node], b'angles', [0.0, 0.0, 0.0]); setd(m.E[node], b'scales', [1.0, 1.0, 1.0])
    for a in m.E[node]['attrs']:
        if a[0] == b'visexclude': a[2] = False if a[1] == 4 else a[2]
    dmx.geta(m.E[m.world], b'children')[2].append(node)
    return node, mat

D = load_disps(BSP)
from collections import Counter
used = Counter()
for d in D:
    _, mat = build(d); used[(d['mat'], mat)] += 1
m.prune()
size = m.save(OUT)
print('added', len(D), 'meshes', dict(used), 'bytes', size)
