"""Rigged glTF binary (.glb: Tripo, Mixamo-rigged exports, Sketchfab characters) -> the model dict create/mdl2cs2.py works on
(the same one its Source MDL loader returns), so a GLB goes through the same split / pivot / hit spheres / hardpoints / clips /
damage skins path as a GMod model.

  M = load(path, rename='valve', decimate=None, log=print)
      -> dict(V, N, UV (v from the top), own, W, B, bones [{name, parent, pos}], meshes [(texture name, faces, [], 0)],
              roots, warnings, images {texture name: RGB uint8})
  python -I create/glbrig.py <file.glb>        prints the summary (bones, triangles, size, texture)

The GLB is data only: JSON + buffers are parsed with numpy; images are decoded with Pillow; nothing in the file is executed.
- Skinned rest pose: every vertex = sum_k w_k * (joint world @ inverse bind) * v, so node transforms on the mesh are irrelevant.
- Axes: glTF Y-up -> Z-up as (x, -z, y); units stay as given (mdl2cs2 scales by --height).
- rename='valve': Mixamo bone names (mixamorig:Hips, LeftUpLeg, LeftForeArm, ...) become ValveBiped.Bip01_* so the leg/arm chain
  finders (mech_anim.py, mdl2cs2's leg split and hardpoints) recognise them. 'keep' leaves them.
- decimate=N: quadric edge-collapse (fast-simplification, pip) on the unwelded mesh with its open borders kept, so UV seams
  (borders of the unwelded mesh) never move or crack; interior vertices keep the UV and weights of the original vertex they collapse to.
"""
import io, json, os, re, struct, sys
import numpy as np
from PIL import Image

CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}

MIXAMO = {'hips': 'Pelvis', 'spine': 'Spine', 'spine1': 'Spine1', 'spine2': 'Spine2', 'neck': 'Neck1', 'head': 'Head1',
          'leftshoulder': 'L_Clavicle', 'leftarm': 'L_UpperArm', 'leftforearm': 'L_Forearm', 'lefthand': 'L_Hand',
          'rightshoulder': 'R_Clavicle', 'rightarm': 'R_UpperArm', 'rightforearm': 'R_Forearm', 'righthand': 'R_Hand',
          'leftupleg': 'L_Thigh', 'leftleg': 'L_Calf', 'leftfoot': 'L_Foot', 'lefttoebase': 'L_Toe0',
          'rightupleg': 'R_Thigh', 'rightleg': 'R_Calf', 'rightfoot': 'R_Foot', 'righttoebase': 'R_Toe0'}
FINGERS = {'thumb': 0, 'index': 1, 'middle': 2, 'ring': 3, 'pinky': 4}


def read_glb(path):
    d = open(path, 'rb').read()
    magic, ver, ln = struct.unpack_from('<III', d, 0)
    if magic != 0x46546C67: raise ValueError('not a glb file')
    off, js, bn = 12, None, b''
    while off < min(ln, len(d)):
        cl, ct = struct.unpack_from('<II', d, off)
        if ct == 0x4E4F534A: js = json.loads(d[off + 8:off + 8 + cl].decode('utf-8'))
        elif ct == 0x004E4942: bn = d[off + 8:off + 8 + cl]
        off += 8 + cl
    if js is None: raise ValueError('glb has no JSON chunk')
    return js, bn


def accessor(g, b, i):
    a = g['accessors'][i]; bv = g['bufferViews'][a['bufferView']]; n = NC[a['type']]; dt = np.dtype(CT[a['componentType']])
    st = bv.get('byteStride', n * dt.itemsize); o = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    raw = np.frombuffer(b, np.uint8, count=st * (a['count'] - 1) + n * dt.itemsize, offset=o)
    out = np.lib.stride_tricks.as_strided(raw, (a['count'], n * dt.itemsize), (st, 1)).copy().view(dt).reshape(a['count'], n)
    if a.get('normalized') and dt.kind in 'iu': out = out.astype(np.float32) / np.iinfo(dt).max
    return out


def node_local(n):
    if 'matrix' in n: return np.array(n['matrix'], np.float64).reshape(4, 4).T
    M = np.eye(4); t = n.get('translation', [0, 0, 0]); x, y, z, w = n.get('rotation', [0, 0, 0, 1]); s = n.get('scale', [1, 1, 1])
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M[:3, :3] = R * np.array(s); M[:3, 3] = t
    return M


def world_mats(g):
    nodes = g['nodes']; par = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}
    W = [None] * len(nodes)
    def get(i):
        if W[i] is None:
            W[i] = (get(par[i]) if i in par else np.eye(4)) @ node_local(nodes[i])
        return W[i]
    for i in range(len(nodes)): get(i)
    return W, par


def valve_name(name):
    n = re.sub(r'^.*?:', '', name)                       # mixamorig:LeftArm -> LeftArm
    k = n.lower()
    if k in MIXAMO: return 'ValveBiped.Bip01_' + MIXAMO[k]
    m = re.match(r'(left|right)hand(thumb|index|middle|ring|pinky)(\d)$', k)
    if m: return 'ValveBiped.Bip01_%s_Finger%d%d' % ('L' if m.group(1) == 'left' else 'R', FINGERS[m.group(2)], max(0, int(m.group(3)) - 1))
    return n


def image_of(g, b, mat_index):
    try:
        mat = g['materials'][mat_index]; ti = mat['pbrMetallicRoughness']['baseColorTexture']['index']
        img = g['images'][g['textures'][ti]['source']]; bv = g['bufferViews'][img['bufferView']]; o = bv.get('byteOffset', 0)
        im = Image.open(io.BytesIO(b[o:o + bv['byteLength']])); im.load()
        f = mat['pbrMetallicRoughness'].get('baseColorFactor')
        a = np.asarray(im.convert('RGB'))
        if f and any(abs(x - 1) > 0.01 for x in f[:3]): a = np.clip(a * np.array(f[:3]), 0, 255).astype(np.uint8)
        return a, mat.get('name', 'm%d' % mat_index)
    except (KeyError, IndexError, TypeError):
        f = (g.get('materials') or [{}])[mat_index if mat_index is not None else 0].get('pbrMetallicRoughness', {}).get('baseColorFactor', [0.6, 0.6, 0.6, 1])
        return np.full((8, 8, 3), [int(255 * x) for x in f[:3]], np.uint8), 'flat%d' % (mat_index or 0)


def decimate_mesh(V, F, target, log=print):
    """quadric edge collapse (fast-simplification) of the position-welded mesh to ~target triangles, then UV charts rebuilt: every
    new corner takes the uv / weights / normal of the nearest original vertex of its own chart that collapsed into it, so seams stay
    seams (no cross-chart uv smear) and nothing cracks. -> (V, F, src): src[i] = the original vertex new vertex i copies attributes from"""
    import fast_simplification as fs
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    q = np.round(V / max(1e-9, np.abs(V).max() * 1e-6)).astype(np.int64)
    _, wid = np.unique(q, axis=0, return_inverse=True); wid = wid.ravel()
    nw = wid.max() + 1
    Vw = np.zeros((nw, 3)); Vw[wid] = V
    Fw = wid[F]
    red = 1.0 - target / float(len(F))
    if red <= 0: return V, F, np.arange(len(V))
    _, _, coll = fs.simplify(Vw.astype(np.float32), Fw.astype(np.int32), target_reduction=red, return_collapses=True, agg=7.0)
    p2, f2, imap = fs.replay_simplification(Vw.astype(np.float32), Fw.astype(np.int32), coll)
    imap = np.asarray(imap, np.int64); p2 = np.asarray(p2, np.float64)
    # charts: connected components of the unwelded mesh (seams duplicate vertices)
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]]])
    _, chart = connected_components(coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(len(V), len(V))), directed=False)
    nf = imap[Fw]
    keep = (nf[:, 0] != nf[:, 1]) & (nf[:, 1] != nf[:, 2]) & (nf[:, 0] != nf[:, 2])
    srt = np.sort(nf[keep], 1); _, first = np.unique(srt, axis=0, return_index=True)
    kf = np.nonzero(keep)[0][np.sort(first)]                       # surviving faces (duplicates removed), original order
    key = imap[wid] * (chart.max() + 1) + chart                     # (new welded vertex, chart) per original vertex
    d = np.linalg.norm(V - p2[imap[wid]], axis=1)
    order = np.lexsort((d, key)); firstk = np.ones(len(order), bool); firstk[1:] = key[order][1:] != key[order][:-1]
    ukeys = key[order][firstk]; src = order[firstk]
    pos = np.searchsorted(ukeys, key[F[kf]])
    newF = pos.reshape(-1, 3)
    newV = p2[imap[wid[src]]]
    log('  decimated %d -> %d triangles (welded quadric collapse, %d uv charts kept)' % (len(F), len(newF), chart.max() + 1))
    return newV, newF, src


def load(path, rename='valve', decimate=None, log=print):
    g, b = read_glb(path)
    warns = []
    W, par = world_mats(g)
    skins = g.get('skins') or []
    mesh_nodes = [i for i, n in enumerate(g['nodes']) if 'mesh' in n]
    if not mesh_nodes: raise ValueError('glb has no mesh')
    skin = skins[g['nodes'][mesh_nodes[0]].get('skin', 0)] if skins else None
    joints = skin['joints'] if skin else []
    IBM = accessor(g, b, skin['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1) if skin and 'inverseBindMatrices' in skin else \
        np.array([np.linalg.inv(W[j]) for j in joints]) if joints else np.zeros((0, 4, 4))
    JM = np.array([W[j] @ IBM[k] for k, j in enumerate(joints)]) if joints else np.zeros((0, 4, 4))
    Vs, Ns, UVs, Js, Ws, Fs, mats = [], [], [], [], [], [], []
    base = 0
    for ni in mesh_nodes:
        node = g['nodes'][ni]
        for pr in g['meshes'][node['mesh']]['primitives']:
            if pr.get('mode', 4) != 4: continue
            at = pr['attributes']
            P = accessor(g, b, at['POSITION']).astype(np.float64)
            N = accessor(g, b, at['NORMAL']).astype(np.float64) if 'NORMAL' in at else np.zeros_like(P)
            UV = accessor(g, b, at['TEXCOORD_0']).astype(np.float64) if 'TEXCOORD_0' in at else np.zeros((len(P), 2))
            F = accessor(g, b, pr['indices']).reshape(-1, 3).astype(np.int64) if 'indices' in pr else np.arange(len(P)).reshape(-1, 3)
            if joints and 'JOINTS_0' in at:
                J = accessor(g, b, at['JOINTS_0']).astype(np.int64); Wt = accessor(g, b, at['WEIGHTS_0']).astype(np.float64)
                if Wt.max() > 1.5: Wt /= 255.0 if Wt.max() <= 255 else 65535.0
                Wt /= np.maximum(Wt.sum(1, keepdims=True), 1e-9)
                M = np.einsum('nk,nkij->nij', Wt, JM[J])              # skinned rest pose
            else:
                J = np.zeros((len(P), 4), np.int64); Wt = np.zeros((len(P), 4)); Wt[:, 0] = 1
                M = np.repeat(W[ni][None], len(P), 0); warns.append('mesh node %d not skinned: node transform used' % ni)
            P = np.einsum('nij,nj->ni', M[:, :3, :3], P) + M[:, :3, 3]
            N = np.einsum('nij,nj->ni', M[:, :3, :3], N); N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
            Vs.append(P); Ns.append(N); UVs.append(UV); Js.append(J); Ws.append(Wt); Fs.append(F + base); mats += [pr.get('material', 0)] * len(F)
            base += len(P)
    V = np.vstack(Vs); N = np.vstack(Ns); UV = np.vstack(UVs); J = np.vstack(Js); Wt = np.vstack(Ws); F = np.vstack(Fs); mats = np.array(mats)
    if decimate and len(F) > decimate:
        V, F2, surv = decimate_mesh(V, F, int(decimate), log)
        # material per new face: from any original face (single-material Tripo models: trivially the same)
        N, UV, J, Wt = N[surv], UV[surv], J[surv], Wt[surv]
        mats = np.full(len(F2), mats[0]) if len(set(mats.tolist())) == 1 else mats[:len(F2)]
        if len(set(mats.tolist())) > 1: warns.append('decimated multi-material mesh: face materials approximate')
        F = F2
        # recompute smooth normals per position-welded vertex within each UV chart (the survivors' normals came from moved neighbours)
        fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
        acc = np.zeros_like(V)
        for k in range(3): np.add.at(acc, F[:, k], fn)
        ok = np.linalg.norm(acc, axis=1) > 1e-12
        N[ok] = acc[ok] / np.linalg.norm(acc[ok], axis=1, keepdims=True)
    # axes: glTF Y-up -> Z-up (x, -z, y)
    ax = lambda a: np.stack([a[:, 0], -a[:, 2], a[:, 1]], 1)
    V = ax(V); N = ax(N)
    # bones
    names = [g['nodes'][j].get('name', 'joint%d' % k) for k, j in enumerate(joints)]
    jidx = {j: k for k, j in enumerate(joints)}
    bones = []
    for k, j in enumerate(joints):
        p = par.get(j); pk = -1
        while p is not None and pk < 0:
            if p in jidx: pk = jidx[p]
            else: p = par.get(p)
        pos = W[j][:3, 3]
        bones.append({'name': valve_name(names[k]) if rename == 'valve' else names[k], 'parent': pk, 'src': names[k],      # src: the original name (mech_anim's mixamo family)
                      'pos': np.array([pos[0], -pos[2], pos[1]]), 'from': os.path.basename(path)})
    if not bones:
        bones = [{'name': 'root', 'parent': -1, 'pos': np.zeros(3), 'from': os.path.basename(path)}]
    heavy = J[np.arange(len(J)), Wt.argmax(1)]
    meshes, images = [], {}
    for mi in sorted(set(mats.tolist())):
        img, mname = image_of(g, b, mi)
        tex = re.sub(r'[^a-z0-9_]+', '_', ('%s_%d' % (os.path.splitext(os.path.basename(path))[0], mi)).lower()).strip('_')
        images[tex] = img
        meshes.append((tex, F[mats == mi], [], 0))
    UVt = UV.copy()                                          # glTF uv: v from the top already (image convention)
    return dict(V=V, N=N, UV=UVt, own=heavy, W=Wt, B=J, bones=bones, meshes=meshes, roots=[os.path.dirname(os.path.abspath(path))],
                warnings=warns, images=images)


if __name__ == '__main__':
    M = load(sys.argv[1], decimate=int(sys.argv[2]) if len(sys.argv) > 2 else None)
    lo, hi = M['V'].min(0), M['V'].max(0)
    print('tris', sum(len(f) for _, f, _, _ in M['meshes']), 'verts', len(M['V']), 'bounds', lo.round(3), hi.round(3))
    print('bones', len(M['bones']), [b['name'] for b in M['bones']][:30])
    print('textures', {k: v.shape for k, v in M['images'].items()}, 'warnings', M['warnings'])
