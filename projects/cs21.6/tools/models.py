"""The 1.6 player models as CS2 player models: each 1.6 model's mesh is moved onto CS2's player skeleton so CS2's own
animations, hit boxes, ragdoll and weapon attachments work with it.

usage: python3 tools/models.py <cstrike dir> <CS2 player model template dir> <addon out dir> [preview dir]

  template dir  a CS2 player model decompiled to ModelDoc (Source 2 Viewer): <name>.vmdl, <name>_thirdperson_body.dmx,
                _firstperson_arms.dmx, _firstperson_sleeves.dmx, _tools_preview.dmx. The skeleton, hit boxes, ragdoll,
                attachments, sleeves and animation graph are kept; the third-person body and first-person arms are replaced.

How the mesh is moved: every 1.6 bone is matched to a CS2 bone (Bip01 L UpperArm -> arm_upper_L ...). Each piece of
the mesh keeps its shape but is turned so its bone points the way the CS2 bone points (the 1.6 T-pose becomes CS2's
A-pose), stretched along the bone to the CS2 bone's length, and put at the CS2 joint. 1.6 models give each vertex one
bone, as here, so joints bend the way they did in 1.6.

The first-person arms are the 1.6 view-model hands (fingerless gloves, bare forearms, from v_ak47.mdl) moved onto CS2's
arm, hand and finger bones the same way, each piece rolled with the palm so fingers bend the right way; the forearm is
sized like the template's so the template's rolled-up sleeves still sit over the elbow.

Writes models/player/cs16/<class>/<class>.vmdl (+ _body.dmx), models/player/cs16/shared/ (1.6 hands, the template's
sleeves and preview pose), materials/models/player/cs16/<class>/ and hands/ (*.vmat + png), and preview pictures (bind
pose and the template's preview pose).
"""
import os, sys, re, shutil, copy
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'goldsrc'))
import dmx9
from dmx9 import Element, T_ELEMENT, T_INT, T_FLOAT, T_STRING, T_VEC2, T_VEC3, T_VEC4, ARRAY
from mdl import MDL, quat_mat

CS, TPL, OUT = sys.argv[1:4]
PREVIEW = sys.argv[4] if len(sys.argv) > 4 else None
CLASSES = ['terror', 'leet', 'arctic', 'guerilla', 'urban', 'gsg9', 'sas', 'gign']
MODEL_DIR = 'models/player/cs16'
MAT_DIR = 'materials/models/player/cs16'
GIRTH = 1.12            # CS2 agents are bigger than the 1.6 models: widen everything by this much
FLOOR_CS = 0.0          # the floor under CS2's skeleton in its bind pose

# ---------------------------------------------------------------- the template (CS2 skeleton in its bind pose)
tfiles = os.listdir(TPL)
def tfile(suffix): return os.path.join(TPL, next(f for f in tfiles if f.endswith(suffix)))
TPL_VMDL, TPL_BODY = tfile('.vmdl'), tfile('_thirdperson_body.dmx')
body_tpl = dmx9.DMX.load(TPL_BODY)
skel = body_tpl.root['skeleton']
JOINTS = [j.name for j in skel['jointList']]
JIDX = {n: i for i, n in enumerate(JOINTS)}


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
WCS = joint_world(body_tpl)
def J(n): return WCS[n][1]

# ---------------------------------------------------------------- 1.6 bone -> (CS2 bone, the 1.6 bone whose piece transform it uses)
MAP = {}
def side(s, S):
    m = {
        f'Bip01 {S} Clavicle': ('clavicle_' + s, None), f'Bip01 {S} UpperArm': ('arm_upper_' + s, None),
        f'-- {S} shoulder outside': ('arm_upper_' + s, f'Bip01 {S} UpperArm'), f'-- {S} Shoulder inside': ('arm_upper_' + s, f'Bip01 {S} UpperArm'),
        f'-- {S} bicep twist': ('arm_upper_' + s, f'Bip01 {S} UpperArm'),
        f'Bip01 {S} Forearm': ('arm_lower_' + s, None), f'-- {S} Elbow': ('arm_lower_' + s, f'Bip01 {S} Forearm'),
        f'-- {S} Forearm twist': ('arm_lower_' + s, f'Bip01 {S} Forearm'), f'-- {S} forearm twist': ('arm_lower_' + s, f'Bip01 {S} Forearm'),
        f'Bip01 {S} Hand': ('hand_' + s, None), f'-- {S} wrist': ('hand_' + s, f'Bip01 {S} Hand'),
        f'Bip01 {S} Finger0': ('finger_thumb_0_' + s, None), f'Bip01 {S} Finger01': ('finger_thumb_1_' + s, None),
        f'Bip01 {S} Finger1': ('finger_middle_0_' + s, None), f'Bip01 {S} Finger11': ('finger_middle_1_' + s, None),
        f'-- {S} knuckle': ('finger_middle_0_' + s, f'Bip01 {S} Finger1'),
        f'Bip01 {S} Thigh': ('leg_upper_' + s, None), f'Bip01 {S} Calf': ('leg_lower_' + s, None),
        f'-- {S} Knee': ('leg_lower_' + s, f'Bip01 {S} Calf'), f'Bip01 {S} Foot': ('ankle_' + s, None),
        f'-- {S} ankle': ('ankle_' + s, f'Bip01 {S} Foot'), f'-- {S} Ankle': ('ankle_' + s, f'Bip01 {S} Foot'),
        f'Bip01 {S} Toe0': ('ball_' + s, None),
        f'-- {S} butt': ('pelvis', 'Bip01 Pelvis'), f'-- {S} Butt': ('pelvis', 'Bip01 Pelvis'),
    }
    MAP.update(m)
side('L', 'L'); side('R', 'R')
MAP.update({'Bip01': ('pelvis', 'Bip01 Pelvis'), 'Bip01 Pelvis': ('pelvis', None), 'Bip01 Spine': ('spine_0', None),
            'Bip01 Spine1': ('spine_1', None), 'Bip01 Spine2': ('spine_2', None), 'Bip01 Spine3': ('spine_3', None),
            'Bip01 Neck': ('neck_0', None), '-- Neck smooth': ('neck_0', 'Bip01 Neck'), 'Bip01 Head': ('head_0', None),
            'Bone01': ('head_0', 'Bip01 Head'), 'Bomb': ('spine_2', 'Bip01 Spine2')})
# the bone each piece points along (1.6 child -> CS2 child)
SEG16, SEGCS = {}, {}
for s, S in (('L', 'L'), ('R', 'R')):
    for a, b, c, d in [(f'Bip01 {S} Clavicle', f'Bip01 {S} UpperArm', 'clavicle_' + s, 'arm_upper_' + s),
                       (f'Bip01 {S} UpperArm', f'Bip01 {S} Forearm', 'arm_upper_' + s, 'arm_lower_' + s),
                       (f'Bip01 {S} Forearm', f'Bip01 {S} Hand', 'arm_lower_' + s, 'hand_' + s),
                       (f'Bip01 {S} Hand', f'Bip01 {S} Finger1', 'hand_' + s, 'finger_middle_0_' + s),
                       (f'Bip01 {S} Finger0', f'Bip01 {S} Finger01', 'finger_thumb_0_' + s, 'finger_thumb_1_' + s),
                       (f'Bip01 {S} Finger1', f'Bip01 {S} Finger11', 'finger_middle_0_' + s, 'finger_middle_1_' + s),
                       (f'Bip01 {S} Thigh', f'Bip01 {S} Calf', 'leg_upper_' + s, 'leg_lower_' + s),
                       (f'Bip01 {S} Calf', f'Bip01 {S} Foot', 'leg_lower_' + s, 'ankle_' + s),
                       (f'Bip01 {S} Foot', f'Bip01 {S} Toe0', 'ankle_' + s, 'ball_' + s)]:
        SEG16[a] = b; SEGCS[a] = (c, d)
for a, b, c, d in [('Bip01 Spine', 'Bip01 Spine1', 'spine_0', 'spine_1'), ('Bip01 Spine1', 'Bip01 Spine2', 'spine_1', 'spine_2'),
                   ('Bip01 Spine2', 'Bip01 Spine3', 'spine_2', 'spine_3'), ('Bip01 Spine3', 'Bip01 Neck', 'spine_3', 'neck_0'),
                   ('Bip01 Neck', 'Bip01 Head', 'neck_0', 'head_0')]:
    SEG16[a] = b; SEGCS[a] = (c, d)
# terminal pieces turn with their parent piece: fingertips, toes, head
INHERIT = {}
for s in 'LR':
    INHERIT[f'Bip01 {s} Finger01'] = f'Bip01 {s} Finger0'
    INHERIT[f'Bip01 {s} Finger11'] = f'Bip01 {s} Finger1'
    INHERIT[f'Bip01 {s} Toe0'] = f'Bip01 {s} Foot'
INHERIT['Bip01 Head'] = 'Bip01 Neck'

UNKNOWN = set()
G = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], float)     # 1.6 faces -Y in its reference pose; CS2 faces +X


def arc(a, b):
    """rotation taking unit vector a onto unit vector b by the shortest arc"""
    v = np.cross(a, b); c = float(np.dot(a, b))
    if c < -0.9999:
        ax = np.cross(a, [1, 0, 0]) if abs(a[0]) < 0.9 else np.cross(a, [0, 1, 0])
        ax /= np.linalg.norm(ax)
        return 2 * np.outer(ax, ax) - np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1 + c)


def frame(p, s):
    """orthonormal frame from a primary and a secondary direction"""
    x = p / np.linalg.norm(p); z = np.cross(x, s); z /= np.linalg.norm(z); y = np.cross(z, x)
    return np.stack([x, y, z], 1)


def piece_transforms(m, floor16):
    """per 1.6 bone: (pivot16, pivotCS, R, axis16, along) mapping a reference-pose point to the CS2 bind pose"""
    names = [b['name'] for b in m.bones]
    T16 = {n: G @ m.T[i] for i, n in enumerate(names)}
    out = {}
    # hips: the pelvis piece hangs from the line between the thighs in both skeletons
    hip16 = (T16['Bip01 L Thigh'] + T16['Bip01 R Thigh']) / 2
    hipcs = (J('leg_upper_L') + J('leg_upper_R')) / 2
    out['Bip01 Pelvis'] = (hip16, hipcs, np.eye(3), None, GIRTH)
    order = [n for n in names if n in SEG16] + [n for n in names if n in INHERIT]
    for n in order:
        if n in SEG16:
            c16, (ccs, ccs2) = SEG16[n], SEGCS[n]
            d16 = T16[c16] - T16[n]; dcs = J(ccs2) - J(ccs)
            L16, Lcs = np.linalg.norm(d16), np.linalg.norm(dcs)
            u16, ucs = d16 / L16, dcs / Lcs
            if n.endswith('Foot'):
                # feet: the 1.6 boot keeps its sole flat on the floor; it only turns to point where CS2's foot points
                h16 = np.array([u16[0], u16[1], 0.]); hcs = np.array([ucs[0], ucs[1], 0.])
                R = arc(h16 / np.linalg.norm(h16), hcs / np.linalg.norm(hcs))
                pcs = J(ccs).copy(); pcs[2] = FLOOR_CS + (T16[n][2] - floor16) * GIRTH
                out[n] = (T16[n], pcs, R, None, GIRTH)
                continue
            if 'Hand' in n:
                # hands: also line the thumb up, so the palm faces the right way
                s = n.split()[1]
                t16 = T16[f'Bip01 {s} Finger0'] - T16[n]; tcs = J(f'finger_thumb_0_{s}') - J(ccs)
                R = frame(ucs, tcs) @ frame(u16, t16).T
            elif n.startswith('Bip01 Spine') or n == 'Bip01 Neck':
                R = arc(u16, ucs)
            else:
                R = arc(u16, ucs)
            along = float(np.clip(Lcs / L16, 0.6, 1.8))
            out[n] = (T16[n], J(ccs), R, u16, along)
        elif n.endswith('Toe0'):
            out[n] = out[INHERIT[n]]
        else:
            p = out[INHERIT[n]]
            out[n] = (T16[n], J(MAP[n][0]), p[2], None, GIRTH)
    for n in names:
        if n in out or n not in MAP: continue
        main = MAP[n][1]
        if main and main in out: out[n] = out[main]
    # bones this table doesn't know: follow the nearest known parent (and say so)
    for i, n in enumerate(names):
        if n in out: continue
        p = m.bones[i]['parent']
        while p >= 0 and names[p] not in out: p = m.bones[p]['parent']
        out[n] = out[names[p]] if p >= 0 else out['Bip01 Pelvis']
        MAP.setdefault(n, (MAP[names[p]][0] if p >= 0 and names[p] in MAP else 'pelvis', None))
        UNKNOWN.add(n)
    return out, names


def move(points, tr):
    p16, pcs, R, axis, along = tr
    x = points - p16
    if axis is not None:
        a = (x @ axis)[:, None] * axis
        x = a * along + (x - a) * GIRTH
    else:
        x = x * along
    return x @ R.T + pcs


# ---------------------------------------------------------------- textures
def write_material(cls, tex_i, m):
    t = m.textures[tex_i]
    base = re.sub(r'[^a-z0-9_]', '_', os.path.splitext(t['name'])[0].lower())
    d = os.path.join(OUT, MAT_DIR, cls); os.makedirs(d, exist_ok=True)
    rgba = m.texture_rgba(tex_i)
    im = Image.fromarray(rgba, 'RGBA')
    im = im.resize((im.width * 2, im.height * 2), Image.BICUBIC)
    im.convert('RGB').save(os.path.join(d, base + '_color.png'))
    lines = ['// CS 1.6 player texture %s (%s)' % (t['name'], cls), 'Layer0', '{', '\tshader "csgo_complex.vfx"',
             '\tTextureColor "%s/%s/%s_color.png"' % (MAT_DIR, cls, base)]
    if t['flags'] & 0x40:
        Image.fromarray(np.repeat(rgba[..., 3:], 3, 2)).resize((im.width, im.height), Image.NEAREST).save(os.path.join(d, base + '_trans.png'))
        lines += ['\tF_ALPHA_TEST 1', '\tTextureTranslucency "%s/%s/%s_trans.png"' % (MAT_DIR, cls, base), '\tg_flAlphaTestReference "0.500"']
    lines += ['\tTextureNormal "materials/default/default_normal.tga"', '\tTextureRoughness "[0.780000 0.780000 0.780000 0.000000]"',
              '\tTextureMetalness "materials/default/default_metal.tga"', '}']
    open(os.path.join(d, base + '.vmat'), 'w', newline='\n').write('\n'.join(lines) + '\n')
    return '%s/%s/%s.vmat' % (MAT_DIR, cls, base), t['w'], t['h']



# ---------------------------------------------------------------- writing a mesh into a copy of a template DMX
def write_dmx(tpl, path, name, V, N, cpos, cnorm, cuv, mats, sets, weights):
    """V/N: positions/normals; cpos/cnorm/cuv: per corner; sets: faces (corner triples) per material in mats;
    weights: per position, [(joint name, weight), ...]. The template's first mesh gets this geometry, other meshes go.
    Returns the face sets as written (winding fixed)."""
    # winding: CS2 wants the faces counter-clockwise seen from the front (the side the normals point to)
    agree = 0
    for faces in sets:
        for a, b, c in faces:
            p = V[[cpos[a], cpos[b], cpos[c]]]
            n = N[[cnorm[a], cnorm[b], cnorm[c]]].sum(0)
            agree += 1 if np.dot(np.cross(p[1] - p[0], p[2] - p[0]), n) > 0 else -1
    if agree < 0: sets = [[[a, c, b] for a, b, c in faces] for faces in sets]
    # tangents along u
    P = V[cpos]; UV = np.array(cuv); NN = N[cnorm]
    tan = np.zeros((len(cpos), 3))
    for faces in sets:
        for f in faces:
            p0, p1, p2 = P[f]; t0, t1, t2 = UV[f]
            e1, e2 = p1 - p0, p2 - p0; d1, d2 = t1 - t0, t2 - t0
            r = d1[0] * d2[1] - d2[0] * d1[1]
            if abs(r) < 1e-12: continue
            tan[f] += (e1 * d2[1] - e2 * d1[1]) / r
    tan -= NN * (tan * NN).sum(1, keepdims=True)
    ln = np.linalg.norm(tan, axis=1); bad = ln < 1e-9
    tan[bad] = np.cross(NN[bad], [0, 0, 1]) + 1e-6; tan /= np.linalg.norm(tan, axis=1, keepdims=True)
    dm = dmx9.DMX.load(tpl)
    meshes = [e for e in dm.elements if e.type == 'DmeMesh']
    mesh = meshes[0]
    vd = mesh['currentState'] or next(e for e in dm.elements if e.type == 'DmeVertexData')
    model = dm.root['model']
    gone = [c for c in model['children'] if c is not None and c.type == 'DmeDag' and any(c.get('shape') is x for x in meshes[1:])]
    if gone:   # the other meshes' dags also sit at the end of the joint list, with a base state each
        model['children'] = [c for c in model['children'] if not any(c is g for g in gone)]
        model['jointList'] = [j for j in model['jointList'] if not any(j is g for g in gone)]
        model['baseStates'] = model['baseStates'][:len(model['baseStates']) - len(gone)]
    jidx = {j.name: i for i, j in enumerate(dm.root['skeleton']['jointList']) if j.type == 'DmeJoint'}
    fs0 = mesh['faceSets'][0]
    nc = len(cpos)
    jc = vd['jointCount']
    vd['position$0'] = [tuple(map(float, V[cpos[i]])) for i in range(nc)]
    vd['normal$0'] = [tuple(map(float, NN[i])) for i in range(nc)]
    vd['texcoord$0'] = [(float(u), float(1 - v) if vd.get('flipVCoordinates') else float(v)) for u, v in cuv]
    vd['tangent$0'] = [tuple(map(float, tan[i])) + (1.0,) for i in range(nc)]
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
        me['mtlName'] = mat.replace('/', '\\')          # (written the way Source 2 Viewer writes it)
        fs['material'] = me
        fl = []
        for f in faces: fl += f + [-1]
        fs['faces'] = fl
        new_sets.append(fs)
    mesh['faceSets'] = new_sets
    mesh.name = name
    for e in dm.elements:
        if e.type == 'DmeDag' and e.get('shape') is mesh: e.name = name
    dm.save(path)
    return sets

# ---------------------------------------------------------------- one class
def build(cls, pack=False):
    """the body (and with pack=True the 1.6 bomb pack / defuse kit body part) as <cls>[_pack].vmdl"""
    m = MDL(os.path.join(CS, 'models/player/%s/%s.mdl' % (cls, cls)))
    body = m.bodyparts[0]['models'][0]
    Vb, _ = m.world(body)
    tr, names = piece_transforms(m, Vb[:, 2].min())
    models = [body]
    if pack and len(m.bodyparts) > 1 and len(m.bodyparts[1]['models']) > 1: models.append(m.bodyparts[1]['models'][1])
    allV, allN, allJ = [], [], []
    by_mat = {}                 # material -> (faces, texture index)
    corner_key, cpos, cnorm, cuv = {}, [], [], []
    vo = no = 0
    for model in models:
        V, N = m.world(model)
        V16 = V @ G.T; N16 = N @ G.T
        for i in range(len(V)):
            bn = names[model['vbone'][i]]
            t = tr.get(bn) or tr['Bip01 Pelvis']
            allV.append(move(V16[i:i + 1], t)[0])
            allJ.append(JIDX[MAP.get(bn, ('pelvis',))[0]])
        for i in range(len(N)):
            bn = names[model['nbone'][i]]
            t = tr.get(bn) or tr['Bip01 Pelvis']
            n = t[2] @ N16[i]; allN.append(n / (np.linalg.norm(n) or 1))
        # corners: (vertex, normal, s, t) -> one DMX vertex each
        for me in model['meshes']:
            tex = m.skinref[me['skin']] if me['skin'] < len(m.skinref) else me['skin']
            mat, w, h = write_material(cls, tex, m)
            faces = by_mat.setdefault(mat, ([], tex))[0]
            for tri in me['tris']:
                idx = []
                for (vi, ni, s_, t_) in tri:
                    k = (vi + vo, ni + no, s_, t_)
                    if k not in corner_key:
                        corner_key[k] = len(cpos); cpos.append(vi + vo); cnorm.append(ni + no); cuv.append((s_ / w, t_ / h))
                    idx.append(corner_key[k])
                faces.append(idx)
        vo += len(V); no += len(N)
    newV, newN, vj = np.array(allV), np.array(allN), np.array(allJ)
    mats = list(by_mat); sets = [by_mat[k][0] for k in mats]; texs = [m.texture_rgba(by_mat[k][1]) for k in mats]
    tri_count = sum(len(f) for f in sets)
    sfx = '_pack' if pack else ''
    d = os.path.join(OUT, MODEL_DIR, cls); os.makedirs(d, exist_ok=True)
    sets = write_dmx(TPL_BODY, os.path.join(d, '%s%s_body.dmx' % (cls, sfx)), 'cs16_%s%s_body' % (cls, sfx),
                     newV, newN, cpos, cnorm, cuv, mats, sets, [[(JOINTS[j], 1.0)] for j in vj])
    # ---- the vmdl: the template's, with our body and the shared first-person arms
    t = open(TPL_VMDL, encoding='utf-8').read()
    def swap(name, path):
        nonlocal t
        t2 = re.sub(r'(name = "%s"\s*\n\s*filename = ")[^"]+(")' % re.escape(name), r'\g<1>%s\g<2>' % path, t)
        assert t2 != t, 'no render mesh named ' + name
        t = t2
    swap('thirdperson_body', '%s/%s/%s%s_body.dmx' % (MODEL_DIR, cls, cls, sfx))
    swap('firstperson_default_gloves_arms', MODEL_DIR + '/shared/firstperson_arms.dmx')
    swap('firstperson_sleeves', MODEL_DIR + '/shared/firstperson_sleeves.dmx')
    t = re.sub(r'(source_filename = ")[^"]*_tools_preview\.dmx(")', r'\g<1>%s/shared/tools_preview.dmx\g<2>' % MODEL_DIR, t)
    open(os.path.join(d, '%s%s.vmdl' % (cls, sfx)), 'w', encoding='utf-8', newline='\n').write(t)
    return newV[cpos], np.array(cuv), sets, texs, vj[cpos], tri_count, len(mats)



# ---------------------------------------------------------------- first-person arms: the 1.6 view-model hands
VMODEL = 'models/v_ak47.mdl'      # every 1.6 rifle / pistol view model has the same two hands (rhand / lhand)
HANDS16 = {   # its bones: forearm, hand, then thumb and finger chains (base, middle, tip)
    'R': dict(part='rhand', arm='Bone04', hand='Bone_Righthand', thumb=('Bone27', 'Bone28', 'Bone29'),
              index=('Bone31', 'Bone32', 'Bone33'), middle=('Bone35', 'Bone36', 'Bone37'),
              ring=('Bone39', 'Bone40', 'Bone41'), pinky=('Bone43', 'Bone44', 'Bone45')),
    'L': dict(part='lhand', arm='Bone01', hand='Bone_Lefthand', thumb=('Bone05', 'Bone06', 'Bone07'),
              index=('Bone21', 'Bone22', 'Bone23'), middle=('Bone17', 'Bone18', 'Bone19'),
              ring=('Bone13', 'Bone14', 'Bone15'), pinky=('Bone09', 'Bone10', 'Bone11')),
}
FINGERS = ('thumb', 'index', 'middle', 'ring', 'pinky')
ELBOW_TUCK = 1.7     # the forearm ends this far past CS2's elbow, square, under the template's rolled-up sleeve
UPPER_STUB = 6.5     # and carries on this far up the upper arm, as CS2's own first-person arms do


def _slice_radius(P, origin, u, lo, hi, how=np.median):
    """distance from the centre line (median or max) of the points whose position along u (from origin) is in [lo, hi]"""
    t = (P - origin) @ u
    Q = P[(t >= lo) & (t <= hi)]
    q = Q - origin; q = q - np.outer(q @ u, u)
    return float(how(np.linalg.norm(q - q.mean(0), axis=1)))


def hand_transforms(T16, s, H, arm_verts16, tpl_arm):
    """per 1.6 bone of one hand: (pivot16, pivotCS, R, axis16, along, girth, CS joint)"""
    out = {}
    lat16 = T16[H['index'][0]] - T16[H['pinky'][0]]
    latcs = J('finger_index_0_' + s) - J('finger_pinky_0_' + s)
    girth = np.linalg.norm(latcs) / np.linalg.norm(lat16)
    # hand: from the wrist to the middle finger's knuckle, palm turned so index and pinky sit where CS2's do
    h16, hcs = T16[H['hand']], J('hand_' + s)
    u16 = T16[H['middle'][0]] - h16; ucs = J('finger_middle_0_' + s) - hcs
    Rh = frame(ucs, latcs) @ frame(u16, lat16).T
    out[H['hand']] = (h16, hcs, Rh, u16 / np.linalg.norm(u16), np.linalg.norm(ucs) / np.linalg.norm(u16), girth, 'hand_' + s)
    palm16 = np.cross(u16, lat16); palmcs = np.cross(ucs, latcs)
    # fingers: each piece along its CS2 bone, rolled with the palm (the thumb with the palm's normal)
    for f in FINGERS:
        b = H[f]; c = ['finger_%s_%d_%s' % (f, k, s) for k in range(3)]
        sec16, seccs = (palm16, palmcs) if f == 'thumb' else (lat16, latcs)
        along = 1.0
        for k in range(3):
            if k < 2: d16 = T16[b[k + 1]] - T16[b[k]]; dcs = J(c[k + 1]) - J(c[k]); along = np.linalg.norm(dcs) / np.linalg.norm(d16)
            else: d16 = T16[b[2]] - T16[b[1]]; dcs = J(c[2]) - J(c[1])
            R = frame(dcs, seccs) @ frame(d16, sec16).T
            out[b[k]] = (T16[b[k]], J(c[k]), R, d16 / np.linalg.norm(d16), along, girth, c[k])
    # forearm: from the wrist back; its far end lands on CS2's elbow, its thickness matches the template's bare arm
    a16 = h16 - T16[H['arm']]; a16 /= np.linalg.norm(a16)
    acs = hcs - J('arm_lower_' + s); Lcs = np.linalg.norm(acs); acs /= Lcs
    far = float(((h16 - arm_verts16) @ a16).max())
    gw = _slice_radius(tpl_arm, hcs, -acs, 0.0, 0.25 * Lcs) / _slice_radius(arm_verts16, h16, -a16, -1.0, 0.25 * far)
    # the elbow end: no wider anywhere than the template's arm there, so it fits inside the rolled-up sleeve
    ge = _slice_radius(tpl_arm, hcs, -acs, 0.75 * Lcs, Lcs) / _slice_radius(arm_verts16, h16, -a16, 0.75 * far, far + 1.0, np.max)
    Ra = frame(acs, latcs) @ frame(a16, lat16).T
    out[H['arm']] = (h16, hcs, Ra, a16, (Lcs + ELBOW_TUCK) / far, (gw, ge, far), 'arm_lower_' + s)
    return out


def move_piece(x, tr):
    p16, pcs, R, axis, along, girth = tr[:6]
    d = x - p16
    t = d @ axis
    if isinstance(girth, tuple):      # forearm: thickness from the wrist's to the elbow's
        gw, ge, far = girth
        girth = gw + (ge - gw) * float(np.clip(-t / far, 0, 1))
    a = t * axis
    return (a * along + (d - a) * girth) @ R.T + pcs


def arm_weights(x, bone, tr, s, H):
    """CS2 joints and weights for a moved vertex"""
    if bone.endswith('/stub'): return [('arm_upper_' + s, 1.0)]
    cj = tr[bone][6]
    if bone == H['arm']:          # along the forearm: elbow -> twist -> twist1, as CS2's arms are weighted
        e = J('arm_lower_' + s); u = J('hand_' + s) - e; L = np.linalg.norm(u); u /= L
        js = ['arm_lower_' + s, 'arm_lower_%s_TWIST' % s, 'arm_lower_%s_TWIST1' % s]
        ts = [0.0] + [float((J(j) - e) @ u / L) for j in js[1:]]
        t = float((x - e) @ u / L)
        ts[0] = 0.12
        if t <= ts[0]:            # round the elbow: over to the upper arm by the end tucked under the sleeve
            w = float(np.clip((ts[0] - t) / (ts[0] + ELBOW_TUCK / L), 0, 1))
            return [(js[0], 1 - w), ('arm_upper_' + s, w)]
        for k in range(2):
            if t <= ts[k + 1]:
                w = (t - ts[k]) / (ts[k + 1] - ts[k]); return [(js[k], 1 - w), (js[k + 1], w)]
        return [(js[2], 1.0)]
    if bone == H['hand']:         # the knuckle end of the palm follows the finger it belongs to
        h = J('hand_' + s); u = J('finger_middle_0_' + s) - h; L = np.linalg.norm(u); u /= L
        w = float(np.clip(((x - h) @ u / L - 0.45) / 0.45, 0, 1))
        if w <= 0: return [(cj, 1.0)]
        meta = min(('index', 'middle', 'ring', 'pinky'), key=lambda f: np.linalg.norm(x - J('finger_%s_0_%s' % (f, s))))
        return [(cj, 1 - w), ('finger_%s_meta_%s' % (meta, s), w)]
    return [(cj, 1.0)]


def _split4(c):
    """a triangle of corners (position, bone, normal, uv) cut into four"""
    def mid(p, q):
        n = p[2] + q[2]
        return ((p[0] + q[0]) / 2, p[1], n / (np.linalg.norm(n) or 1), ((p[3][0] + q[3][0]) / 2, (p[3][1] + q[3][1]) / 2))
    a, b, cc = c; ab, bc, ca = mid(a, b), mid(b, cc), mid(cc, a)
    return [[a, ab, ca], [ab, b, bc], [ca, bc, cc], [ab, bc, ca]]


def build_arms():
    """the 1.6 view-model hands and bare forearms on CS2's first-person arm bones -> shared/firstperson_arms.dmx"""
    m = MDL(os.path.join(CS, VMODEL))
    names = [b['name'] for b in m.bones]; T16 = {n: m.T[i] for i, n in enumerate(names)}
    # the template's bare forearms (to size ours like them, so its rolled-up sleeves still sit over the elbow)
    ta = dmx9.DMX.load(tfile('_firstperson_arms.dmx'))
    BP = np.array([e for e in ta.elements if e.type == 'DmeMesh'][1]['currentState']['position$0'])
    pos, nrm, W, vkey, nkey, arm_tris = [], [], [], {}, {}, []
    by_mat = {}; corner_key, cpos, cnorm, cuv = {}, [], [], []
    for s, H in HANDS16.items():
        model = next(mo for bp in m.bodyparts if bp['name'] == H['part'] for mo in bp['models'])
        V, N = m.world(model)
        vb = [names[b] for b in model['vbone']]; nb = [names[b] for b in model['nbone']]
        armv = V[[b == H['arm'] for b in vb]]
        tr = hand_transforms(T16, s, H, armv, BP[BP[:, 1] * J('hand_' + s)[1] > 0])
        # the forearm's elbow end: cut square, just past the elbow
        h16 = T16[H['hand']]; a16 = tr[H['arm']][3]; far = float(((h16 - armv) @ a16).max())
        elbow = J('arm_lower_' + s); up = elbow - J('hand_' + s); up /= np.linalg.norm(up)
        def place(i):
            x = move_piece(V[i], tr[vb[i]])
            if vb[i] == H['arm'] and (h16 - V[i]) @ a16 > 0.6 * far:
                x = x - ((x - elbow) @ up - ELBOW_TUCK) * up
            return x
        def turn(i):
            r = tr[nb[i]][2] @ N[i]
            return r / (np.linalg.norm(r) or 1)
        def vid(x, b):
            k = (b,) + tuple(np.round(x, 3))
            if k not in vkey:
                vkey[k] = len(pos); pos.append(x); W.append(arm_weights(x, b, tr, s, H))
            return vkey[k]
        def nid(n):
            k = tuple(np.round(n, 5))
            if k not in nkey: nkey[k] = len(nrm); nrm.append(n)
            return nkey[k]
        for me in model['meshes']:
            tex = m.skinref[me['skin']] if me['skin'] < len(m.skinref) else me['skin']
            mat, w, h = write_material('hands', tex, m)
            faces = by_mat.setdefault(mat, ([], tex))[0]
            for tri in me['tris']:
                pieces = [[(place(vi), vb[vi], turn(ni), (s_ / w, t_ / h)) for vi, ni, s_, t_ in tri]]
                if all(c[1] == H['arm'] for c in pieces[0]):      # the long forearm faces get rows of vertices to bend with
                    for _ in range(2): pieces = [q for p in pieces for q in _split4(p)]
                for p in pieces:
                    idx = []
                    for x, b, n, uv in p:
                        k = (vid(x, b), nid(n), round(uv[0], 6), round(uv[1], 6))
                        if k not in corner_key:
                            corner_key[k] = len(cpos); cpos.append(k[0]); cnorm.append(k[1]); cuv.append(uv)
                        idx.append(corner_key[k])
                    faces.append(idx)
                    if all(c[1] == H['arm'] for c in p): arm_tris.append((faces, idx))
        # a short bare upper arm from the forearm's open end, up under and past the rolled-up sleeve
        shoulder = J('arm_upper_' + s) - elbow; shoulder /= np.linalg.norm(shoulder)
        on_end = lambda c: abs((pos[cpos[c]] - elbow) @ up - ELBOW_TUCK) < 0.05
        used = {}
        for faces, (a, b, c) in arm_tris:
            for e in ((a, b), (b, c), (c, a)):
                key = tuple(sorted((cpos[e[0]], cpos[e[1]])))
                used.setdefault(key, []).append((faces, e))
        for key, uses in used.items():
            if len(uses) != 1: continue
            faces, (a, b) = uses[0]
            if not (on_end(a) and on_end(b)): continue
            top = []
            for c in (a, b):
                x = pos[cpos[c]] + shoulder * UPPER_STUB
                k = (vid(x, H['arm'] + '/stub'), cnorm[c], round(cuv[c][0], 6), round(cuv[c][1], 6))
                if k not in corner_key:
                    corner_key[k] = len(cpos); cpos.append(k[0]); cnorm.append(k[1]); cuv.append(cuv[c])
                top.append(corner_key[k])
            faces += [[b, a, top[0]], [b, top[0], top[1]]]
        arm_tris.clear()
    V, N = np.array(pos), np.array(nrm)
    mats = list(by_mat); sets = [by_mat[k][0] for k in mats]; texs = [m.texture_rgba(by_mat[k][1]) for k in mats]
    sets = write_dmx(tfile('_firstperson_arms.dmx'), os.path.join(OUT, MODEL_DIR, 'shared', 'firstperson_arms.dmx'), 'cs16_hands',
                     V, N, cpos, cnorm, cuv, mats, sets, W)
    print('hands     %4d vertices, %4d triangles, %d materials (from %s)' % (len(cpos), sum(len(f) for f in sets), len(mats), VMODEL))
    return V[cpos], np.array(cuv), sets, texs, [W[i] for i in cpos]

# ---------------------------------------------------------------- checks: pictures of the bind pose and a posed body
def posed_preview():
    tp = dmx9.DMX.load(tfile('_tools_preview.dmx'))
    pose = {}
    for ch in (e for e in tp.elements if e.type == 'DmeChannel'):
        el, at, log = ch['toElement'], ch['toAttribute'], ch['log']
        if el is None or log is None or at not in ('position', 'orientation'): continue
        lay = log['layers'][0]
        if lay['values']: pose.setdefault(el.name, {})[at] = lay['values'][0]
    # posed world transforms with the template's hierarchy
    Wp = {}
    def walk(j, R, tt):
        tr = j['transform']
        p = pose.get(j.name, {}); pos = p.get('position', tr['position']); q = p.get('orientation', tr['orientation'])
        R2 = R @ quat_mat(q); t2 = R @ np.array(pos) + tt
        Wp[j.name] = (R2, t2)
        for c in j['children'] or []:
            if c.type == 'DmeJoint': walk(c, R2, t2)
    for c in skel['children']:
        if c.type == 'DmeJoint': walk(c, np.eye(3), np.zeros(3))
    return Wp


# ---------------------------------------------------------------- run
shared = os.path.join(OUT, MODEL_DIR, 'shared'); os.makedirs(shared, exist_ok=True)
shutil.copy(tfile('_firstperson_sleeves.dmx'), os.path.join(shared, 'firstperson_sleeves.dmx'))
shutil.copy(tfile('_tools_preview.dmx'), os.path.join(shared, 'tools_preview.dmx'))
Wp = posed_preview() if PREVIEW else None
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'preview'))
from model_render import render
MARK = np.array([WCS[n][1] for n in WCS if 'TWIST' not in n and 'finger' not in n and n not in ('eye_target', 'wpn', 'wpnPivot', 'root_motion')])
for cls in CLASSES:
    build(cls, pack=False)
    P, UV, sets, texs, cj, ntri, nmat = build(cls, pack=True)
    print('%-9s %4d vertices, %4d triangles with the pack, %d materials' % (cls, len(P), ntri, nmat) + ('; bones following a parent: ' + ', '.join(sorted(UNKNOWN)) if UNKNOWN else ''))
    UNKNOWN.clear()
    if PREVIEW:
        os.makedirs(PREVIEW, exist_ok=True)
        groups = [(np.array(f), t) for f, t in zip(sets, texs)]
        render(P, UV, groups, os.path.join(PREVIEW, 'model_%s_bind.png' % cls), views=('front', 'side', 'back'), H=700, marks=MARK)
        # skinned to the template's preview pose: each vertex follows its joint
        Q = np.zeros_like(P)
        for i, j in enumerate(cj):
            n = JOINTS[j]; Rb, tb = WCS[n]; Rp, tp_ = Wp[n]
            Q[i] = Rp @ (Rb.T @ (P[i] - tb)) + tp_
        render(Q, UV, groups, os.path.join(PREVIEW, 'model_%s_posed.png' % cls), views=('front', 'three', 'side'), H=700)
P, UV, sets, texs, wl = build_arms()
if PREVIEW:
    for s in 'RL':
        keep = [np.array([f for f in faces if P[f[0]][1] * J('hand_' + s)[1] > 0]) for faces in sets]
        groups = [(f, t) for f, t in zip(keep, texs) if len(f)]
        render(P, UV, groups, os.path.join(PREVIEW, 'hands_%s_bind.png' % s), views=('front', 'side', 'back'), H=700)
        Q = np.zeros_like(P)
        for i, w in enumerate(wl):
            for n, x in w:
                Rb, tb = WCS[n]; Rp, tp_ = Wp[n]
                Q[i] += x * (Rp @ (Rb.T @ (P[i] - tb)) + tp_)
        render(Q, UV, groups, os.path.join(PREVIEW, 'hands_%s_posed.png' % s), views=('front', 'three', 'side'), H=700)
