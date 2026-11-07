"""Still poses for checking a converted model: CS2's own shooting pose (the template's preview pose) and a running stride, a deep crouch, arms raised
overhead (shoulders, armpits) and a body twist with the head turned (neck). Built on the CS2 skeleton the model is skinned to.

    from poses import pose_sheet
    pose_sheet(t, V, UV, groups, weights, 'out.png', label)     # t: gmod2cs2.Template (or its own-joints copy)

Views: env POSE_VIEWS (default front,three; e.g. side,three to see knees and elbows bend).

Each pose is {joint: [(world axis, degrees), ...]}: the joint and everything below it turn about that axis through the joint's
bind-pose position (model faces +X, left is +Y, up is +Z). 'drop' lowers the whole body (crouch). Rotations compose down the chain.
"""
import numpy as np
from PIL import Image

X, Y, Z = np.array([1., 0, 0]), np.array([0, 1., 0]), np.array([0, 0, 1.])
BOX = (np.array([-32., -42, -2]), np.array([36., 42, 100]))   # the same frame for every pose and model (a cape doesn't pull the camera)
POSES = {
    'run': {'leg_upper_R': [(Y, -50)], 'leg_lower_R': [(Y, 65)], 'leg_upper_L': [(Y, 30)], 'leg_lower_L': [(Y, 45)],
            'arm_upper_L': [(Y, -40)], 'arm_lower_L': [(Y, -60)], 'arm_upper_R': [(Y, 35)], 'arm_lower_R': [(Y, -40)],
            'spine_1': [(Y, 8)]},
    'crouch': {'drop': 22, 'leg_upper_L': [(Y, -100)], 'leg_upper_R': [(Y, -100)], 'leg_lower_L': [(Y, 125)], 'leg_lower_R': [(Y, 125)],
               'ankle_L': [(Y, -25)], 'ankle_R': [(Y, -25)], 'spine_1': [(Y, 25)], 'arm_lower_L': [(Y, -45)], 'arm_lower_R': [(Y, -45)]},
    'arms up': {'arm_upper_L': [(X, 115)], 'arm_upper_R': [(X, -115)], 'arm_lower_L': [(X, 15)], 'arm_lower_R': [(X, -15)]},
    'twist': {'spine_1': [(Z, 15)], 'spine_2': [(Z, 15)], 'neck_0': [(Z, 15), (X, 10)], 'head_0': [(Z, 30), (X, 12)],
              'arm_upper_L': [(Y, -30)], 'arm_upper_R': [(Y, 30)]},
}


def rot(axis, deg):
    a = np.radians(deg); u = axis / np.linalg.norm(axis); c, s = np.cos(a), np.sin(a)
    K = np.array([[0, -u[2], u[1]], [u[2], 0, -u[0]], [-u[1], u[0], 0]])
    return np.eye(3) + s * K + (1 - c) * K @ K


def mat(R, t):
    M = np.eye(4); M[:3, :3] = R; M[:3, 3] = t; return M


def pose_world(t, spec):
    """{joint: 4x4 skinning matrix (posed @ inverse bind)} for a pose spec"""
    bind = {j: mat(*t.W[j]) for j in t.order}
    posed = {}
    drop = mat(np.eye(3), [0, 0, -spec.get('drop', 0)])
    for j in t.order:
        D = np.eye(4)
        for axis, deg in spec.get(j, []):
            pj = t.W[j][1]
            D = mat(rot(axis, deg), pj - rot(axis, deg) @ pj) @ D
        p = t.parent[j]
        if p is None: posed[j] = drop @ D @ bind[j]
        else: posed[j] = posed[p] @ np.linalg.inv(bind[p]) @ D @ bind[j]
    return {j: posed[j] @ np.linalg.inv(bind[j]) for j in t.order}


def skin(V, weights, S):
    Q = np.zeros_like(V)
    Vh = np.hstack([V, np.ones((len(V), 1))])
    for i, w in enumerate(weights):
        tot = sum(x for _, x in w) or 1
        for j, x in w:
            Q[i] += x / tot * (S[j] @ Vh[i])[:3]
    return Q


def shoot_pose(t):
    """CS2's own preview pose (the template's tools_preview: a rifle held ready) as skinning matrices"""
    P = t.preview_pose()
    return {j: mat(*P[j]) @ np.linalg.inv(mat(*t.W[j])) for j in t.order}


def pose_sheet(t, V, UV, groups, weights, out, label, H=520):
    """one picture: CS2's shooting pose first, then each of POSES; two views each, textured as the groups are"""
    from preview import render
    import os
    tiles = []
    todo = [('shooting', shoot_pose(t))] + [(n, pose_world(t, spec)) for n, spec in POSES.items()]
    for name, S in todo:
        Q = skin(V, weights, S)
        p = out[:-4] + '_%s.png' % name.replace(' ', '')
        render(Q, UV, groups, p, views=tuple(os.environ.get('POSE_VIEWS', 'front,three').split(',')), H=H, label='%s  %s' % (label, name), box=BOX)
        tiles.append(Image.open(p).convert('RGB')); os.remove(p)
    w = max(im.width for im in tiles); cols = 3
    sheet = Image.new('RGB', (w * cols, H * ((len(tiles) + cols - 1) // cols)), (46, 50, 58))
    for k, im in enumerate(tiles): sheet.paste(im, ((k % cols) * w, (k // cols) * H))
    sheet.save(out)
    return out
