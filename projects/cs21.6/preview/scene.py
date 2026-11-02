"""Reads a Hammer .vmap back (meshes, materials, texcoords) and writes a render scene for view.html.

usage: python3 preview/scene.py <map.vmap> <addon dir> <out dir>
Writes <out>/scene.json + scene.bin. Reading the vmap (rather than the converter's own data) checks what Hammer will see.
"""
import os, sys, json, re
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
import dmx9

vmap, addon, out = sys.argv[1:4]
dm = dmx9.DMX.load(vmap)


def walk(e, out):
    for c in e.get('children', []) or []:
        out.append(c); walk(c, out)
    return out


def matinfo(path):
    """(kind, color png, trans png, opacity)"""
    if path.startswith('materials/tools/'): return ('tool', None, None, 1)
    f = os.path.join(addon, path)
    if not os.path.exists(f): return ('missing', None, None, 1)
    t = open(f).read()
    col = re.search(r'TextureColor "([^"]+)"', t)
    tr = re.search(r'TextureTranslucency "([^"]+)"', t)
    op = re.search(r'g_flOpacityScale "([^"]+)"', t)
    if 'csgo_moondome' in t:
        cube = re.search(r'TextureCubeMap "([^"]+)"', t).group(1)
        return ('sky', cube, None, 1)
    return ('tex', col.group(1) if col else None, tr.group(1) if tr else None, float(op.group(1)) if op else 1.0)


batches = {}
for node in walk(dm.root['world'], []):
    if node.type != 'CMapMesh': continue
    md = node['meshData']
    o = np.array(node['origin'])
    pos = np.array(md['vertexData']['streams'][0]['data'], np.float64)
    fvd = {s.name: s['data'] for s in md['faceVertexData']['streams']}
    tc = fvd['texcoord:0']
    fdat = {s.name: s['data'] for s in md['faceData']['streams']}
    mi = fdat['materialindex:0']
    mats = md['materials']
    ev, en, evd = md['edgeVertexIndices'], md['edgeNextIndices'], md['edgeVertexDataIndices']
    vdi = md['vertexDataIndices']
    for f, h0 in enumerate(md['faceEdgeIndices']):
        loop = []; h = h0
        while True:
            loop.append(h); h = en[h]
            if h == h0: break
        mat = mats[mi[md['faceDataIndices'][f]]]
        B = batches.setdefault(mat, ([], []))
        P = [pos[vdi[ev[h]]] + o for h in loop]
        U = [tc[evd[h]] for h in loop]
        for k in range(1, len(loop) - 1):
            for j in (0, k, k + 1):
                B[0].append(P[j]); B[1].append(U[j])
meta = []
blob = bytearray()
for mat, (P, U) in sorted(batches.items()):
    kind, col, tr, op = matinfo(mat)
    if kind == 'tool': continue
    a = np.array(P, np.float32).reshape(-1); b = np.array(U, np.float32).reshape(-1)
    meta.append({'mat': mat, 'kind': kind, 'color': col, 'trans': tr, 'opacity': op, 'off': len(blob), 'n': len(P)})
    blob += a.tobytes(); blob += b.tobytes()
os.makedirs(out, exist_ok=True)
open(os.path.join(out, 'scene.bin'), 'wb').write(blob)
json.dump(meta, open(os.path.join(out, 'scene.json'), 'w'))
print('batches', len(meta), 'triangles', sum(m['n'] for m in meta) // 3)
