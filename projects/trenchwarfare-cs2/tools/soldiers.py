"""Tripo/Mixamo-rigged soldier GLBs -> CS2 player models (agent skeleton, animgraph, hitboxes, ragdoll from a template).

usage: python3 tools/soldiers.py <template dir> <addon out> <name>=<soldier.glb> [...] [--arms gb=<arms.glb> --arms de=<arms.glb>]
With --bare-hands (tw29, in use) the hand is tools/bare_hands.py's skinned stock glove hand and only the sleeves come from --arms.
Without --arms (tw28) the template's own stock agent arms/sleeves are copied to models/tw/players/arms_stock/.
                                 [--side name=gb|de] [--preview dir]

template dir: a CS2 agent rebuilt for ModelDoc (Octodad in mg_mario_party: *_cs2.vmdl with ragdoll joints, *_thirdperson_body.dmx,
*_firstperson_arms.dmx, *_firstperson_sleeves.dmx, *_tools_preview.dmx).

Body: every Mixamo bone is matched to a CS2 bone; its piece of the mesh is turned so the bone points the way the CS2 bone points
(T-pose -> CS2 A-pose, no twist; hands also line up the thumb), stretched along the bone to the CS2 length and put on the CS2 joint;
vertices follow their own skin weights (linear blend), then the weights are renamed to CS2 bones and spread over the twist bones.
If the GLB's skeleton transforms are broken, joints are estimated from where neighbouring bones' weights meet.

Arms (first person): an unrigged arm pair (shoulder at the top, hands down) is cut into hand (skin) and sleeve (cloth) by texture,
fitted segment by segment onto the template's arm bones, sleeve/forearm weights by position along the bone, hand and finger
weights copied from the template's glove mesh after the fit.

Writes models/tw/players/<name>/<name>.vmdl + _body.dmx, models/tw/players/arms_<side>/ (arms, sleeves), models/tw/players/shared/,
materials/models/tw/players/<name>/.
"""
import os, sys, re, copy
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx9
from dmx9 import Element
from glbskin import GLB, load_skinned, joints_from_weights, joints_bind, quat_mat

MODEL_DIR = 'models/tw/players'
MAT_DIR = 'materials/models/tw/players'
TEX_MAX = 2048


def gl2cs(P): return np.stack([P[:, 2], P[:, 0], P[:, 1]], 1)        # glTF Y-up facing +Z -> CS2 Z-up facing +X, left +Y


# ---------------------------------------------------------------- template
class Template:
    def __init__(self, d):
        fs = os.listdir(d)
        f = lambda sfx: os.path.join(d, next(x for x in fs if x.endswith(sfx)))
        self.vmdl, self.body, self.arms = f('.vmdl'), f('_thirdperson_body.dmx'), f('_firstperson_arms.dmx')
        self.sleeves, self.preview = f('_firstperson_sleeves.dmx'), f('_tools_preview.dmx')
        self.W = joint_world(dmx9.DMX.load(self.body))

    def J(self, n): return self.W[n][1]


def joint_world(dm):
    W = {}
    def walk(j, R, t):
        tr = j['transform']; R2 = R @ quat_mat(tr['orientation']); t2 = R @ np.array(tr['position']) + t
        W[j.name] = (R2, t2)
        for c in j['children'] or []:
            if c.type == 'DmeJoint': walk(c, R2, t2)
    for c in dm.root['skeleton']['children']:
        if c.type == 'DmeJoint': walk(c, np.eye(3), np.zeros(3))
    return W


# ---------------------------------------------------------------- bone tables
FING = {'Index': 'index', 'Middle': 'middle', 'Ring': 'ring', 'Pinky': 'pinky', 'Thumb': 'thumb'}
WMAP = {'Hips': 'pelvis', 'Spine': 'spine_1', 'Spine1': 'spine_2', 'Spine2': 'spine_3', 'Neck': 'neck_0', 'Head': 'head_0',
        'HeadTop_End': 'head_0'}
SEG = {('Spine', 'Spine1'): ('spine_1', 'spine_2'), ('Spine1', 'Spine2'): ('spine_2', 'spine_3'),
       ('Spine2', 'Neck'): ('spine_3', 'neck_0'), ('Neck', 'Head'): ('neck_0', 'head_0')}
TIP = {'Head': 'Neck', 'HeadTop_End': 'Neck'}          # bones that keep their parent's turn, no stretch
for S, s in (('Left', 'L'), ('Right', 'R')):
    WMAP.update({S + 'Shoulder': 'clavicle_' + s, S + 'Arm': 'arm_upper_' + s, S + 'ForeArm': 'arm_lower_' + s, S + 'Hand': 'hand_' + s,
                 S + 'UpLeg': 'leg_upper_' + s, S + 'Leg': 'leg_lower_' + s, S + 'Foot': 'ankle_' + s, S + 'ToeBase': 'ball_' + s,
                 S + 'Toe_End': 'ball_' + s})
    SEG.update({(S + 'Shoulder', S + 'Arm'): ('clavicle_' + s, 'arm_upper_' + s), (S + 'Arm', S + 'ForeArm'): ('arm_upper_' + s, 'arm_lower_' + s),
                (S + 'ForeArm', S + 'Hand'): ('arm_lower_' + s, 'hand_' + s), (S + 'Hand', S + 'HandMiddle1'): ('hand_' + s, 'finger_middle_0_' + s),
                (S + 'UpLeg', S + 'Leg'): ('leg_upper_' + s, 'leg_lower_' + s), (S + 'Leg', S + 'Foot'): ('leg_lower_' + s, 'ankle_' + s)})
    TIP[S + 'ToeBase'] = S + 'Foot'; TIP[S + 'Toe_End'] = S + 'Foot'
    for F, f in FING.items():
        for k in (1, 2, 3, 4): WMAP[f'{S}Hand{F}{k}'] = f'finger_{f}_{min(k, 3) - 1}_{s}'
        SEG[(f'{S}Hand{F}1', f'{S}Hand{F}2')] = (f'finger_{f}_0_{s}', f'finger_{f}_1_{s}')
        SEG[(f'{S}Hand{F}2', f'{S}Hand{F}3')] = (f'finger_{f}_1_{s}', f'finger_{f}_2_{s}')
        TIP[f'{S}Hand{F}3'] = f'{S}Hand{F}2'; TIP[f'{S}Hand{F}4'] = f'{S}Hand{F}2'
TWIST = {}      # CS2 bone -> (child joint that ends it, twist bones in order)
for s in 'LR':
    TWIST['arm_upper_' + s] = ('arm_lower_' + s, ['arm_upper_%s_TWIST' % s, 'arm_upper_%s_TWIST1' % s])
    TWIST['arm_lower_' + s] = ('hand_' + s, ['arm_lower_%s_TWIST' % s, 'arm_lower_%s_TWIST1' % s])
    TWIST['leg_upper_' + s] = ('leg_lower_' + s, ['leg_upper_%s_TWIST' % s, 'leg_upper_%s_TWIST1' % s])


def arc(a, b):
    v = np.cross(a, b); c = float(np.dot(a, b))
    if c < -0.9999:
        ax = np.cross(a, [1, 0, 0]) if abs(a[0]) < 0.9 else np.cross(a, [0, 1, 0]); ax /= np.linalg.norm(ax)
        return 2 * np.outer(ax, ax) - np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1 + c)


def frame(p, s):
    x = p / np.linalg.norm(p); z = np.cross(x, s); z /= np.linalg.norm(z); y = np.cross(z, x)
    return np.stack([x, y, z], 1)


def unit(v): return v / np.linalg.norm(v)


# ---------------------------------------------------------------- one soldier body
def body_transforms(T, J, floor):
    """per Mixamo bone: (pivot, target, R, axis or None, along)"""
    out = {}
    hip = (J['LeftUpLeg'] + J['RightUpLeg']) / 2; hipcs = (T.J('leg_upper_L') + T.J('leg_upper_R')) / 2
    out['Hips'] = (hip, hipcs, np.eye(3), None, 1.0)
    for (a, b), (c, d) in SEG.items():
        if a not in J or b not in J: continue
        u = J[b] - J[a]; ucs = T.J(d) - T.J(c); L, Lcs = np.linalg.norm(u), np.linalg.norm(ucs)
        if a.endswith('Hand'):
            th = a + 'Thumb1'; s = a[0]
            R = frame(ucs, T.J('finger_thumb_0_' + ('L' if a.startswith('Left') else 'R')) - T.J(c)) @ frame(u, J[th] - J[a]).T
        else:
            R = arc(u / L, ucs / Lcs)
        out[a] = (J[a], T.J(c), R, u / L, float(np.clip(Lcs / L, 0.6, 1.8)))
    for S, s in (('Left', 'L'), ('Right', 'R')):       # feet: sole stays flat on the floor, the foot only turns about z
        a = S + 'Foot'
        if a in J and S + 'ToeBase' in J:
            u = J[S + 'ToeBase'] - J[a]; ucs = T.J('ball_' + s) - T.J('ankle_' + s)
            h = unit(np.array([u[0], u[1], 0.])); hc = unit(np.array([ucs[0], ucs[1], 0.]))
            q = T.J('ankle_' + s).copy(); q[2] = J[a][2] - floor
            out[a] = (J[a], q, arc(h, hc), None, 1.0)
    order = sorted(TIP, key=lambda n: n.count('3') + n.count('4') * 2 + n.count('End') * 3)
    for n in order:
        p = TIP[n]
        if n in out or n not in J or p not in out: continue
        pv, pq, R, ax, al = out[p]
        cs = WMAP[n]
        tgt = T.J(cs) if not n.endswith(('Toe_End', 'HeadTop_End', '4')) and not n.endswith('ToeBase') else None
        if tgt is None: tgt = move1(J[n], out[p])
        out[n] = (J[n], tgt, R, None, 1.0)
    return out


def move1(x, tr):
    p, q, R, ax, al = tr
    d = x - p
    if ax is not None:
        a = (d @ ax) * ax; d = a * al + (d - a)
    return R @ d + q


def move(X, tr):
    p, q, R, ax, al = tr
    d = X - p
    if ax is not None:
        a = (d @ ax)[:, None] * ax; d = a * al + (d - a)
    return d @ R.T + q


def transfer_weights(P, N, F, donor):
    """skin weights for a mesh whose export lost them, copied from another Tripo soldier in the same T-pose: both are normalised
    (arm span, height, torso centre), each vertex takes the inverse-distance mix of its nearest donor vertices (position + a little
    normal, so an inner arm doesn't pick the torso), then the weights are smoothed over the mesh a few times"""
    from scipy.spatial import cKDTree
    gd, md, names, parent, Wdd = load_skinned(donor)
    def frame_of(X):
        y0, y1 = X[:, 1].min(), X[:, 1].max(); span = np.abs(X[:, 0]).max()
        torso = X[np.abs(X[:, 0]) < 0.12 * span]
        return np.median(torso[:, 0]), y0, np.median(torso[:, 2]), span, y1 - y0
    def norm(X, f):
        cx, y0, cz, span, h = f
        return np.stack([(X[:, 0] - cx) / span, (X[:, 1] - y0) / h, (X[:, 2] - cz) / h], 1)
    def denorm(X, f):
        cx, y0, cz, span, h = f
        return np.stack([X[:, 0] * span + cx, X[:, 1] * h + y0, X[:, 2] * h + cz], 1)
    fd, ft = frame_of(md['P']), frame_of(P)
    A = np.hstack([norm(md['P'], fd), 0.03 * md['N']]); B = np.hstack([norm(P, ft), 0.03 * N])
    Jd = joints_bind(gd, names) or joints_from_weights(md['P'], names, parent, Wdd)
    Jt = {n: denorm(norm(v[None], fd), ft)[0] for n, v in Jd.items()}
    dist, nn = cKDTree(A).query(B, k=6)
    iw = 1 / (dist + 1e-3); iw /= iw.sum(1, keepdims=True)
    W = (Wdd[nn] * iw[:, :, None]).sum(1)
    nb = [[] for _ in range(len(P))]
    for a, b, c in F: nb[a] += [b, c]; nb[b] += [a, c]; nb[c] += [a, b]
    rows = np.repeat(np.arange(len(P)), [len(x) for x in nb]); cols = np.concatenate([np.array(x, int) for x in nb])
    from scipy.sparse import csr_matrix
    Aj = csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(P), len(P)))
    deg = np.asarray(Aj.sum(1)).ravel() + 1e-9
    for _ in range(3): W = 0.5 * W + 0.5 * (Aj @ W) / deg[:, None]
    top = np.argsort(-W, 1)[:, 4:]; np.put_along_axis(W, top, 0, 1)
    W /= W.sum(1, keepdims=True)
    return names, parent, W, Jt


def convert_body(T, glb_path, name, out, donor=None):
    g, m, names, parent, Wd = load_skinned(glb_path)
    used = (Wd.sum(0) > 0).sum()
    if used < 20:
        if not donor: raise SystemExit('%s: only %d bones carry weights - the rig is broken, re-export it (or give name=glb@donor.glb)' % (glb_path, used))
        names, parent, Wd, Jb = transfer_weights(m['P'], m['N'], m['F'], donor)
        print('%s: rig broken (%d bones weighted) - weights and joints copied from %s' % (name, used, os.path.basename(donor)))
    else:
        Jb = joints_bind(g, names)
    P = gl2cs(m['P']); N = gl2cs(m['N'])
    Jg = Jb if Jb is not None else joints_from_weights(m['P'], names, parent, Wd)
    J = {n: gl2cs(v[None])[0] for n, v in Jg.items()}
    floor = P[:, 2].min()
    s = (T.J('head_0')[2] - 0) / (J['Head'][2] - floor)
    P = (P - [0, 0, floor]) * s; J = {n: (v - [0, 0, floor]) * s for n, v in J.items()}
    centre = (J['LeftUpLeg'] + J['RightUpLeg']) / 2
    P[:, :2] -= centre[:2]; J = {n: v - [centre[0], centre[1], 0] for n, v in J.items()}
    tr = body_transforms(T, J, 0.0)
    missing = [n for n in names if n not in tr and Wd[:, names.index(n)].sum() > 0]
    for n in missing:          # follow the nearest transformed ancestor
        p = parent[n]
        while p is not None and p not in tr: p = parent[p]
        tr[n] = tr[p or 'Hips']
    V = np.zeros_like(P); NN = np.zeros_like(N)
    for k, n in enumerate(names):
        w = Wd[:, k]; sel = w > 0
        if not sel.any(): continue
        V[sel] += w[sel, None] * move(P[sel], tr[n]); NN[sel] += w[sel, None] * (N[sel] @ tr[n][2].T)
    NN /= np.linalg.norm(NN, axis=1, keepdims=True) + 1e-12
    # weights: CS2 names, spread over twist bones by position along the bone
    W = [dict() for _ in range(len(V))]
    for k, n in enumerate(names):
        cs = WMAP.get(n)
        if cs is None:
            p = parent[n]
            while p is not None and p not in WMAP: p = parent[p]
            cs = WMAP.get(p, 'pelvis')
        w = Wd[:, k]
        for i in np.nonzero(w > 1e-4)[0]:
            for b, f in spread(T, cs, V[i]): W[i][b] = W[i].get(b, 0) + w[i] * f
    weights = []
    for d in W:
        top = sorted(d.items(), key=lambda x: -x[1])[:4]; t = sum(x for _, x in top)
        weights.append([(b, x / t) for b, x in top])
    mat = write_material(g, name, out)
    d = os.path.join(out, MODEL_DIR, name); os.makedirs(d, exist_ok=True)
    F = m['F'].tolist()
    n = len(V)
    write_dmx(T.body, os.path.join(d, name + '_body.dmx'), name + '_body', V, NN, list(range(n)), list(range(n)), m['UV'].tolist(),
              [mat], [F], weights)
    return V, F, weights, s


def spread(T, cs, x):
    if cs not in TWIST: return [(cs, 1.0)]
    end, tw = TWIST[cs]
    a, b = T.J(cs), T.J(end); L = b - a
    t = float(np.clip((x - a) @ L / (L @ L), 0, 1))
    nodes = [(cs, 0.0)] + [(n, float((T.J(n) - a) @ L / (L @ L))) for n in tw]
    if t >= nodes[-1][1]: return [(nodes[-1][0], 1.0)]
    for (n0, t0), (n1, t1) in zip(nodes, nodes[1:]):
        if t <= t1:
            f = (t - t0) / max(t1 - t0, 1e-6); return [(n0, 1 - f), (n1, f)]
    return [(cs, 1.0)]


# ---------------------------------------------------------------- materials
def write_material(g, name, out, sub=None):
    sub = sub or name
    d = os.path.join(out, MAT_DIR, sub); os.makedirs(d, exist_ok=True)
    mi = g.material_images(); m = g.j['materials'][0]; pb = m.get('pbrMetallicRoughness', {})
    rel = lambda fn: '%s/%s/%s' % (MAT_DIR, sub, fn)
    def save(im, fn, mode):
        im = im.convert(mode)
        if max(im.size) > TEX_MAX: im = im.resize((TEX_MAX, TEX_MAX * im.height // im.width), Image.LANCZOS)
        im.save(os.path.join(d, fn)); return rel(fn)
    lines = ['// %s (Tripo3D soldier, converted from glTF)' % name, 'Layer0', '{', '\tshader "csgo_complex.vfx"', '\tF_SPECULAR 1']
    lines.append('\tTextureColor "%s"' % save(g.image(mi['baseColorTexture']), name + '_color.png', 'RGB'))
    if 'normalTexture' in mi: lines.append('\tTextureNormal "%s"' % save(g.image(mi['normalTexture']), name + '_normal.png', 'RGB'))
    if 'metallicRoughnessTexture' in mi:
        mr = np.asarray(g.image(mi['metallicRoughnessTexture']).convert('RGB'))
        rf = pb.get('roughnessFactor', 1.0); mf = pb.get('metallicFactor', 1.0)
        lines.append('\tTextureRoughness "%s"' % save(Image.fromarray(np.clip(mr[..., 1] * rf, 0, 255).astype(np.uint8)), name + '_rough.png', 'L'))
        # Tripo's metal channel is low noise over cloth and skin (mean 0.03-0.12): left out, everything dielectric
    lines.append('}')
    open(os.path.join(d, name + '.vmat'), 'w', newline='\n').write('\n'.join(lines) + '\n')
    return rel(name + '.vmat')


# ---------------------------------------------------------------- DMX writing (a mesh into a copy of a template DMX)
def write_dmx(tpl, path, name, V, N, cpos, cnorm, cuv, mats, sets, weights, jc_out=4):
    agree = 0
    for faces in sets:
        for a, b, c in faces[::7]:
            p = V[[cpos[a], cpos[b], cpos[c]]]; n = N[[cnorm[a], cnorm[b], cnorm[c]]].sum(0)
            agree += 1 if np.dot(np.cross(p[1] - p[0], p[2] - p[0]), n) > 0 else -1
    if agree < 0: sets = [[[a, c, b] for a, b, c in faces] for faces in sets]
    P = V[cpos]; UV = np.array(cuv, float); NN = N[cnorm]
    tan = np.zeros((len(cpos), 3))
    for faces in sets:
        f = np.array(faces)
        p0, p1, p2 = P[f[:, 0]], P[f[:, 1]], P[f[:, 2]]; t0, t1, t2 = UV[f[:, 0]], UV[f[:, 1]], UV[f[:, 2]]
        e1, e2, d1, d2 = p1 - p0, p2 - p0, t1 - t0, t2 - t0
        r = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]; ok = np.abs(r) > 1e-12
        tf = np.zeros_like(e1); tf[ok] = (e1[ok] * d2[ok, 1:2] - e2[ok] * d1[ok, 1:2]) / r[ok, None]
        for k in range(3): np.add.at(tan, f[:, k], tf)
    tan -= NN * (tan * NN).sum(1, keepdims=True)
    ln = np.linalg.norm(tan, axis=1); bad = ln < 1e-9
    tan[bad] = np.cross(NN[bad], [0, 0, 1]) + 1e-6; tan /= np.linalg.norm(tan, axis=1, keepdims=True)
    dm = dmx9.DMX.load(tpl)
    meshes = [e for e in dm.elements if e.type == 'DmeMesh']
    mesh = meshes[0]
    vd = mesh['currentState']
    model = dm.root['model']
    gone = [c for c in model['children'] if c is not None and c.type == 'DmeDag' and any(c.get('shape') is x for x in meshes[1:])]
    if gone:
        model['children'] = [c for c in model['children'] if not any(c is g for g in gone)]
        model['jointList'] = [j for j in model['jointList'] if not any(j is g for g in gone)]
        model['baseStates'] = model['baseStates'][:len(model['baseStates']) - len(gone)]
    jidx = {j.name: i for i, j in enumerate(dm.root['skeleton']['jointList']) if j.type == 'DmeJoint'}
    fs0 = mesh['faceSets'][0]
    nc = len(cpos)
    vd['jointCount'] = jc_out; jc = jc_out
    vd['position$0'] = [tuple(map(float, V[cpos[i]])) for i in range(nc)]
    vd['normal$0'] = [tuple(map(float, NN[i])) for i in range(nc)]
    vd['texcoord$0'] = [(float(u), float(1 - v) if vd.get('flipVCoordinates') else float(v)) for u, v in cuv]
    vd['tangent$0'] = [tuple(map(float, tan[i])) + (1.0,) for i in range(nc)]
    for k in list(vd.attrs):
        if k.startswith('texcoord$1'): del vd.attrs[k]
    fmt = vd.get('vertexFormat')
    if fmt: vd['vertexFormat'] = [f for f in fmt if f != 'texcoord$1']
    wts, ids = [], []
    for i in range(nc):
        w = sorted(weights[cpos[i]], key=lambda x: -x[1])[:jc]
        tot = sum(x for _, x in w) or 1.0
        wts += [x / tot for _, x in w] + [0.0] * (jc - len(w)); ids += [jidx[j] for j, _ in w] + [0] * (jc - len(w))
    vd['blendweights$0'] = wts; vd['blendindices$0'] = ids
    seq = list(range(nc))
    for k in ('position$0Indices', 'normal$0Indices', 'texcoord$0Indices', 'tangent$0Indices'): vd[k] = seq
    new_sets = []
    for mat, faces in zip(mats, sets):
        fs = Element('DmeFaceSet', 'faceSet')
        for k, (t, v) in fs0.attrs.items(): fs.attrs[k] = [t, copy.copy(v)]
        me = Element('DmeMaterial', 'material')
        for k, (t, v) in fs0['material'].attrs.items(): me.attrs[k] = [t, v]
        me['mtlName'] = mat.replace('/', '\\')
        fs['material'] = me
        fl = []
        for f in faces: fl += list(f) + [-1]
        fs['faces'] = fl
        new_sets.append(fs)
    mesh['faceSets'] = new_sets
    mesh.name = name
    for e in dm.elements:
        if e.type == 'DmeDag' and e.get('shape') is mesh: e.name = name
    dm.save(path)


# ---------------------------------------------------------------- vmdl
def write_vmdl(T, out, name, side, bare=False):
    t = open(T.vmdl, encoding='utf-8').read()
    def swap(mesh, path):
        nonlocal t
        t2 = re.sub(r'(name = "%s"\s*\n\s*filename = ")[^"]+(")' % re.escape(mesh), r'\g<1>%s\g<2>' % path, t)
        assert t2 != t, 'no render mesh named ' + mesh
        t = t2
    swap('thirdperson_body', '%s/%s/%s_body.dmx' % (MODEL_DIR, name, name))
    swap('firstperson_default_gloves_arms', '%s/hands_bare/arms.dmx' % MODEL_DIR if bare else '%s/arms_%s/arms.dmx' % (MODEL_DIR, side))
    swap('firstperson_sleeves', '%s/arms_%s/sleeves.dmx' % (MODEL_DIR, side))
    t = re.sub(r'(source_filename = ")[^"]*_tools_preview\.dmx(")', r'\g<1>%s/shared/tools_preview.dmx\g<2>' % MODEL_DIR, t)
    assert 'octodad' not in t.lower(), 'template name left in the vmdl'
    d = os.path.join(out, MODEL_DIR, name); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, name + '.vmdl'), 'w', encoding='utf-8', newline='\n').write(t)


if __name__ == '__main__':
    args = sys.argv[1:]
    tpl, out = args[0], args[1]
    T = Template(tpl)
    bodies, arms, sides, preview, bare = [], {}, {}, None, False
    i = 2
    while i < len(args):
        a = args[i]
        if a == '--arms': k, v = args[i + 1].split('=', 1); arms[k] = v; i += 2
        elif a == '--side': k, v = args[i + 1].split('=', 1); sides[k] = v; i += 2
        elif a == '--preview': preview = args[i + 1]; i += 2
        elif a == '--bare-hands': bare = True; i += 1
        else: bodies.append(a.split('=', 1)); i += 1
    sh = os.path.join(out, MODEL_DIR, 'shared'); os.makedirs(sh, exist_ok=True)
    import shutil
    shutil.copy(T.preview, os.path.join(sh, 'tools_preview.dmx'))
    for side, path in arms.items():
        import arms as ARMS
        ARMS.build(T, path, side, out, preview)
    if bare:
        import bare_hands
        bare_hands.main(T.arms, out)
    if not arms:
        st = os.path.join(out, MODEL_DIR, 'arms_stock'); os.makedirs(st, exist_ok=True)
        shutil.copy(T.arms, os.path.join(st, 'arms.dmx')); shutil.copy(T.sleeves, os.path.join(st, 'sleeves.dmx'))
    for name, path in bodies:
        try:
            donor = None
            if '@' in path: path, donor = path.split('@', 1)
            V, F, W, s = convert_body(T, path, name, out, donor)
        except SystemExit as e:
            print('SKIP', e); continue
        write_vmdl(T, out, name, sides.get(name, 'gb' if 'gb' in name else 'de') if arms else 'stock', bare and bool(arms))
        print(name, 'verts', len(V), 'tris', len(F), 'scale %.1f' % s, 'height %.1f' % V[:, 2].max())
        if preview:
            import preview_soldier
            preview_soldier.sheet(T, V, np.array(F), W, os.path.join(preview, name + '.png'))
