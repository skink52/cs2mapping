"""glTF binary (.glb) -> CS2 static prop with every material: SMD (render + convex hull), csgo_complex vmats, PNG textures.
Handles multi-material models (Sketchfab etc.). Output goes under models/<CS2_MODEL_PREFIX or 'ext'>/<name> unless --sub is given.

usage: glb2cs2_multi.py model.glb <addon content root> <name> [--length L | --scale S] [--yaw deg] [--maxtex 2048] [--surface metal]
  --length: scale so the longest horizontal side is L units; otherwise metres -> inches (x39.37)
"""
import struct, json, io, os, sys, argparse
import numpy as np
from PIL import Image
from scipy.spatial import ConvexHull

ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('out'); ap.add_argument('name')
ap.add_argument('--length', type=float, default=0); ap.add_argument('--scale', type=float, default=0)
ap.add_argument('--yaw', type=float, default=0); ap.add_argument('--maxtex', type=int, default=2048)
ap.add_argument('--surface', default='metal'); ap.add_argument('--sub', default='')
ap.add_argument('--keep', default='', help='comma list of node/mesh name substrings to keep (default all)')
ap.add_argument('--drop', default='', help='comma list of node/mesh name substrings to drop')
ap.add_argument('--credit', default='')
A = ap.parse_args()
name = A.name
sub = A.sub or 'models/%s/%s' % (os.environ.get('CS2_MODEL_PREFIX', 'ext'), name)
mdir = os.path.join(A.out, sub); tdir = os.path.join(A.out, 'materials', sub)
os.makedirs(mdir, exist_ok=True); os.makedirs(tdir, exist_ok=True)

d = open(A.src, 'rb').read()
ln = struct.unpack_from('<I', d, 8)[0]; off = 12; ch = []
while off < ln:
    cl, ct = struct.unpack_from('<II', d, off); ch.append(d[off + 8:off + 8 + cl]); off += 8 + cl
g = json.loads(ch[0]); b = ch[1] if len(ch) > 1 else b''
CT = {5120: 'i1', 5121: 'u1', 5122: 'i2', 5123: 'u2', 5125: 'u4', 5126: 'f4'}; NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}
def acc(i):
    a = g['accessors'][i]; bv = g['bufferViews'][a['bufferView']]; n = NC[a['type']]; dt = np.dtype(CT[a['componentType']])
    st = bv.get('byteStride', n * dt.itemsize); o = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    raw = np.frombuffer(b, dtype=np.uint8, count=st * (a['count'] - 1) + n * dt.itemsize, offset=o)
    out = np.lib.stride_tricks.as_strided(raw, (a['count'], n * dt.itemsize), (st, 1)).copy().view(dt).reshape(a['count'], n).astype(np.float64)
    if a.get('normalized'):
        out /= {5121: 255.0, 5123: 65535.0, 5120: 127.0, 5122: 32767.0}.get(a['componentType'], 1.0)
    return out
def mat4(n):
    if 'matrix' in n: return np.array(n['matrix'], dtype=np.float64).reshape(4, 4).T
    M = np.eye(4); t = n.get('translation', [0, 0, 0]); q = n.get('rotation', [0, 0, 0, 1]); s = n.get('scale', [1, 1, 1])
    x, y, z, w = q
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M[:3, :3] = R * np.array(s); M[:3, 3] = t; return M
world = {}
def walk(i, Pm, path):
    n = g['nodes'][i]; W = Pm @ mat4(n); nm = path + '/' + n.get('name', '')
    world[i] = (W, nm)
    for c in n.get('children', []): walk(c, W, nm)
for r in g['scenes'][g.get('scene', 0)]['nodes']: walk(r, np.eye(4), '')
keep = [k.lower() for k in A.keep.split(',') if k]; drop = [k.lower() for k in A.drop.split(',') if k]
AX = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=np.float64)
parts = {}   # material index -> lists
for ni, (W, path) in world.items():
    n = g['nodes'][ni]
    if 'mesh' not in n: continue
    mesh = g['meshes'][n['mesh']]
    label = (path + '/' + mesh.get('name', '')).lower()
    if keep and not any(k in label for k in keep): continue
    if drop and any(k in label for k in drop): continue
    for p in mesh['primitives']:
        if p.get('mode', 4) != 4: continue
        pos = acc(p['attributes']['POSITION'])
        pos = (W[:3, :3] @ pos.T).T + W[:3, 3]; pos = (AX @ pos.T).T
        if 'NORMAL' in p['attributes']:
            nrm = acc(p['attributes']['NORMAL']); nrm = (AX @ (np.linalg.inv(W[:3, :3]).T @ nrm.T)).T
            nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
        else:
            nrm = np.zeros_like(pos); nrm[:, 2] = 1
        uv = acc(p['attributes']['TEXCOORD_0']) if 'TEXCOORD_0' in p['attributes'] else np.zeros((len(pos), 2))
        idx = acc(p['indices']).reshape(-1, 3).astype(np.int64) if 'indices' in p else np.arange(len(pos)).reshape(-1, 3)
        if np.linalg.det(W[:3, :3]) < 0: idx = idx[:, ::-1]
        L = parts.setdefault(p.get('material', -1), dict(V=[], N=[], T=[], F=[], base=0))
        L['V'].append(pos); L['N'].append(nrm); L['T'].append(uv); L['F'].append(idx + L['base']); L['base'] += len(pos)
for k, L in parts.items():
    for key in ('V', 'N', 'T', 'F'): L[key] = np.vstack(L[key])
allV = np.vstack([L['V'] for L in parts.values()])
lo, hi = allV.min(0), allV.max(0)
if A.length:
    s = A.length / max(hi[0] - lo[0], hi[1] - lo[1])
elif A.scale:
    s = A.scale
else:
    s = 39.3701
yaw = np.radians(A.yaw); Rz = np.array([[np.cos(yaw), -np.sin(yaw), 0], [np.sin(yaw), np.cos(yaw), 0], [0, 0, 1]])
c = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
for L in parts.values():
    L['V'] = ((L['V'] - c) * s) @ Rz.T; L['N'] = L['N'] @ Rz.T
allV = np.vstack([L['V'] for L in parts.values()])
print('%s: tris %d, bounds %s .. %s, materials %d' % (name, sum(len(L['F']) for L in parts.values()), allV.min(0).round(1), allV.max(0).round(1), len(parts)))

# textures (deduplicated by image index)
saved = {}
def img(ti):
    t = g['textures'][ti]; src = t.get('source')
    if src is None:
        for ext in t.get('extensions', {}).values():
            if 'source' in ext: src = ext['source']
    im = g['images'][src]; bv = g['bufferViews'][im['bufferView']]
    pil = Image.open(io.BytesIO(b[bv.get('byteOffset', 0):bv.get('byteOffset', 0) + bv['byteLength']]))
    if max(pil.size) > A.maxtex:
        r = A.maxtex / max(pil.size); pil = pil.resize((max(4, int(pil.size[0] * r)), max(4, int(pil.size[1] * r))), Image.LANCZOS)
    return pil, src
def save(pil, key, mode):
    if key in saved: return saved[key]
    fn = '%s_%s.png' % (name, key.replace('/', '_'))
    pil.convert(mode).save(os.path.join(tdir, fn), optimize=True)
    saved[key] = 'materials/%s/%s' % (sub, fn); return saved[key]
remaps = []; smd_mats = {}
for k in parts:
    m = g['materials'][k] if k >= 0 and 'materials' in g else {}
    pbr = m.get('pbrMetallicRoughness', {})
    mname = '%s_m%d' % (name, k if k >= 0 else 0)
    lines = ['// %s material %d (converted from glTF)%s' % (name, k, ('; ' + A.credit) if A.credit else ''), '', 'Layer0', '{', '\tshader "csgo_complex.vfx"', '\tF_SPECULAR 1']
    if m.get('doubleSided'): lines.append('\tF_RENDER_BACKFACES 1')
    alpha = m.get('alphaMode', 'OPAQUE')
    tint = pbr.get('baseColorFactor', [1, 1, 1, 1])
    if 'baseColorTexture' in pbr:
        pil, src = img(pbr['baseColorTexture']['index'])
        hasa = pil.mode in ('RGBA', 'LA') and np.asarray(pil.convert('RGBA'))[..., 3].min() < 250
        lines.append('\tTextureColor "%s"' % save(pil, 'c%d' % src, 'RGB'))
        if alpha != 'OPAQUE' and hasa:
            a = pil.convert('RGBA').split()[3]
            lines.append('\tF_ALPHA_TEST 1' if alpha == 'MASK' else '\tF_TRANSLUCENT 1')
            lines.append('\tTextureTranslucency "%s"' % save(a, 'a%d' % src, 'L'))
            if alpha == 'MASK': lines.append('\tg_flAlphaTestReference "%.3f"' % m.get('alphaCutoff', 0.5))
    else:
        cimg = Image.new('RGB', (4, 4), tuple(int(255 * (min(1, max(0, v)) ** (1 / 2.2))) for v in tint[:3]))
        lines.append('\tTextureColor "%s"' % save(cimg, 'flat%d' % k, 'RGB'))
    if any(abs(v - 1) > 1e-3 for v in tint[:3]) and 'baseColorTexture' in pbr:
        lines.append('\tg_vColorTint "[%.4f %.4f %.4f 0.000000]"' % tuple(tint[:3]))
    if 'normalTexture' in m:
        pil, src = img(m['normalTexture']['index']); lines.append('\tTextureNormal "%s"' % save(pil, 'n%d' % src, 'RGB'))
    if 'metallicRoughnessTexture' in pbr:
        pil, src = img(pbr['metallicRoughnessTexture']['index']); mr = np.asarray(pil.convert('RGB'))
        rf = pbr.get('roughnessFactor', 1.0); mf = pbr.get('metallicFactor', 1.0)
        lines.append('\tTextureRoughness "%s"' % save(Image.fromarray(np.clip(mr[..., 1] * rf, 0, 255).astype(np.uint8)), 'r%d' % src, 'L'))
        if mf > 0.01:
            lines += ['\tF_METALNESS_TEXTURE 1', '\tTextureMetalness "%s"' % save(Image.fromarray(np.clip(mr[..., 2] * mf, 0, 255).astype(np.uint8)), 'm%d' % src, 'L')]
    else:
        r = int(round(pbr.get('roughnessFactor', 0.8) * 255))
        lines.append('\tTextureRoughness "%s"' % save(Image.new('L', (4, 4), r), 'rf%d' % r, 'L'))
        lines.append('\tg_flMetalness "%.3f"' % pbr.get('metallicFactor', 0.0))
    if 'occlusionTexture' in m:
        pil, src = img(m['occlusionTexture']['index'])
        lines += ['\tTextureAmbientOcclusion "%s"' % save(pil.convert('RGB').split()[0], 'o%d' % src, 'L'), '\tg_flAmbientOcclusionDirectDiffuse "0.000"']
    lines.append('}')
    open(os.path.join(tdir, mname + '.vmat'), 'w', newline='\n').write('\n'.join(lines) + '\n')
    remaps.append(('%s.vmat' % mname, 'materials/%s/%s.vmat' % (sub, mname)))
    smd_mats[k] = mname

def smd(path, groups):
    out = ["version 1", "nodes", '0 "root" -1', "end", "skeleton", "time 0", "0 0 0 0 0 0 0", "end", "triangles"]
    fmt = "0 %.4f %.4f %.4f %.4f %.4f %.4f %.5f %.5f"
    for mn, L in groups:
        V, N, T = L['V'], L['N'], L['T']
        for f in L['F']:
            out.append(mn)
            for i in f:
                x, y, z = V[i]; nx, ny, nz = N[i]
                out.append(fmt % (y, -x, z, ny, -nx, nz, T[i, 0], 1 - T[i, 1]))
    out.append("end")
    open(path, 'w', newline='\n').write('\n'.join(out) + '\n')
smd(os.path.join(mdir, name + '.smd'), [(smd_mats[k], L) for k, L in parts.items()])
# convex hull for collision (decimated point set)
pts = allV[np.random.RandomState(0).choice(len(allV), min(len(allV), 6000), replace=False)]
h = ConvexHull(pts)
hl = ["version 1", "nodes", '0 "root" -1', "end", "skeleton", "time 0", "0 0 0 0 0 0 0", "end", "triangles"]
for sidx, eq in zip(h.simplices, h.equations):
    a_, b_, c_ = pts[sidx]
    if np.dot(np.cross(b_ - a_, c_ - a_), eq[:3]) < 0: sidx = sidx[::-1]
    hl.append('phys')
    for i in sidx:
        x, y, z = pts[i]; hl.append('0 %.3f %.3f %.3f %.3f %.3f %.3f 0 0' % (y, -x, z, eq[1], -eq[0], eq[2]))
hl.append('end'); open(os.path.join(mdir, name + '_hull.smd'), 'w', newline='\n').write('\n'.join(hl) + '\n')
sys.path.insert(0, os.path.dirname(__file__))
import modelio
open(os.path.join(mdir, name + '.vmdl'), 'w', newline='\n').write(modelio.vmdl_text(name, sub, [name], remaps, [name + '_hull'], surface=A.surface, entity=''))
json.dump(dict(model='%s/%s.vmdl' % (sub, name), mins=allV.min(0).tolist(), maxs=allV.max(0).tolist()), open(os.path.join(mdir, name + '.json'), 'w'))
