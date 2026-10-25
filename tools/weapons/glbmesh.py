"""Load a GLB into Parts (one per node/primitive) in Source space (inches, Z-up); exports embedded textures."""
import struct, json, io, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fbxmesh import Part

CT = {5120:'i1',5121:'u1',5122:'i2',5123:'u2',5125:'u4',5126:'f4'}; NC = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}

def read_glb(path):
    d = open(path, 'rb').read(); ln = struct.unpack_from('<I', d, 8)[0]; off = 12; ch = []
    while off < ln:
        cl, ct = struct.unpack_from('<II', d, off); ch.append(d[off+8:off+8+cl]); off += 8+cl
    return json.loads(ch[0]), ch[1]

def accessor(g, b, i):
    a = g['accessors'][i]; bv = g['bufferViews'][a['bufferView']]; n = NC[a['type']]; dt = np.dtype(CT[a['componentType']])
    st = bv.get('byteStride', n*dt.itemsize); o = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    raw = np.frombuffer(b, dtype=np.uint8, count=st*(a['count']-1)+n*dt.itemsize, offset=o)
    return np.lib.stride_tricks.as_strided(raw, (a['count'], n*dt.itemsize), (st, 1)).copy().view(dt).reshape(a['count'], n)

def node_matrix(n):
    if 'matrix' in n: return np.array(n['matrix'], dtype=np.float64).reshape(4,4).T
    M = np.eye(4); t = n.get('translation',[0,0,0]); q = n.get('rotation',[0,0,0,1]); s = n.get('scale',[1,1,1])
    x,y,z,w = q; R = np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
    M[:3,:3] = R*np.array(s); M[:3,3] = t; return M

def load(path, scale=1.0, axes=None):
    """default glTF (Y-up, -Z forward) -> Source: x->x, -z->y, y->z, then optional extra axes permutation string like fbxmesh"""
    g, b = read_glb(path); S = 39.3701 * scale
    world = {}
    def walk(i, P):
        W = P @ node_matrix(g['nodes'][i]); world[i] = W
        for c in g['nodes'][i].get('children', []): walk(c, W)
    for r in g['scenes'][g.get('scene', 0)]['nodes']: walk(r, np.eye(4))
    AX = np.array([[1,0,0],[0,0,-1],[0,1,0]], dtype=np.float64)
    if axes:
        AXI = {'x':0,'y':1,'z':2}; A2 = np.zeros((3,3))
        for i, a in enumerate(axes): A2[i, AXI[a.lower()]] = -1 if a.isupper() else 1
        AX = A2 @ AX
    parts = []; mats = {}
    for ni, W in world.items():
        n = g['nodes'][ni]
        if 'mesh' not in n: continue
        mesh = g['meshes'][n['mesh']]
        for pi, p in enumerate(mesh['primitives']):
            if p.get('mode', 4) != 4: continue
            pos = accessor(g, b, p['attributes']['POSITION']).astype(np.float64)
            pos = (W[:3,:3] @ pos.T).T + W[:3,3]; pos = (AX @ pos.T).T * S
            nrm = accessor(g, b, p['attributes']['NORMAL']).astype(np.float64) if 'NORMAL' in p['attributes'] else None
            if nrm is not None:
                nrm = (AX @ (np.linalg.inv(W[:3,:3]).T @ nrm.T)).T; nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
            uv = accessor(g, b, p['attributes']['TEXCOORD_0']).astype(np.float64) if 'TEXCOORD_0' in p['attributes'] else np.zeros((len(pos), 2))
            uv = uv.copy(); uv[:,1] = 1 - uv[:,1]   # glTF top-left -> bottom-left (same convention as FBX/OBJ parts)
            idx = accessor(g, b, p['indices']).reshape(-1,3).astype(np.int64) if 'indices' in p else np.arange(len(pos)).reshape(-1,3)
            if np.linalg.det(W[:3,:3]) < 0: idx = idx[:, ::-1]
            if nrm is None:
                nrm = np.zeros_like(pos); fn = np.cross(pos[idx[:,1]]-pos[idx[:,0]], pos[idx[:,2]]-pos[idx[:,0]])
                for k in range(3): np.add.at(nrm, idx[:,k], fn)
                nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
            name = n.get('name', f'node{ni}') + (f'#{pi}' if len(mesh['primitives']) > 1 else '')
            part = Part(name, pos, nrm, uv, idx); part.material = p.get('material'); parts.append(part)
    return g, b, parts

def export_textures(g, b, mat_index, outdir, prefix):
    """returns dict kind->png path for the glTF material (color/normal/rough/metal/ao); rough/metal split from metallicRoughness"""
    m = g['materials'][mat_index]; pbr = m.get('pbrMetallicRoughness', {}); os.makedirs(outdir, exist_ok=True); out = {}
    def img(ti):
        im = g['images'][g['textures'][ti]['source']]; bv = g['bufferViews'][im['bufferView']]
        return Image.open(io.BytesIO(b[bv['byteOffset']:bv['byteOffset']+bv['byteLength']]))
    if 'baseColorTexture' in pbr:
        p = os.path.join(outdir, prefix+'_color.png'); img(pbr['baseColorTexture']['index']).convert('RGB').save(p); out['color'] = p
    if 'normalTexture' in m:
        p = os.path.join(outdir, prefix+'_normal.png'); img(m['normalTexture']['index']).convert('RGB').save(p); out['normal'] = p
    if 'metallicRoughnessTexture' in pbr:
        mr = np.array(img(pbr['metallicRoughnessTexture']['index']).convert('RGB'))
        p = os.path.join(outdir, prefix+'_rough.png'); Image.fromarray(mr[:,:,1]).save(p); out['rough'] = p
        p = os.path.join(outdir, prefix+'_metal.png'); Image.fromarray(mr[:,:,2]).save(p); out['metal'] = p
    else:
        r = int(round(pbr.get('roughnessFactor', 1)*255)); p = os.path.join(outdir, prefix+'_rough.png'); Image.new('L', (4,4), r).save(p); out['rough'] = p
        mf = int(round(pbr.get('metallicFactor', 1)*255)); p = os.path.join(outdir, prefix+'_metal.png'); Image.new('L', (4,4), mf).save(p); out['metal'] = p
    if 'occlusionTexture' in m:
        p = os.path.join(outdir, prefix+'_ao.png'); img(m['occlusionTexture']['index']).convert('L').save(p); out['ao'] = p
    return out
