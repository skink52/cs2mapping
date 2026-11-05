"""How well a converted model's visible body fills the CS2 hit boxes it inherits from the template.

The converted models keep the template's (stock agent) hit box set, capsules on CS2's bones, so every model is hit exactly like a stock
agent. What can go wrong is the other way round: body you can see but can't hit (shots pass through), or empty hit box you can hit.
Per hit box group (head, chest, arms, legs ...) this reports the share of the mesh's surface points that lie outside every capsule (miss
area) and, for the head, how far the head's centre is from the head capsule's. The stock template body gives the baseline.

usage: python3 -I hitboxes.py <template dir> <model.mdl> [...]     (gmod2cs2 runs it for every model and adds warnings)
"""
import os, re, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def capsules(vmdl_text):
    """[(name, bone, p0, p1, radius)] of the template's HitboxCapsule entries (points in bone space)"""
    out = []
    for blk in re.findall(r'_class = "HitboxCapsule"(.*?)\}', vmdl_text, re.S):
        g = lambda k: re.search(k + r'\s*=\s*([^\n]+)', blk).group(1).strip()
        vec = lambda k: np.array([float(x) for x in re.findall(r'-?[\d.]+(?:e-?\d+)?', g(k))])
        out.append((g('name').strip('"'), g('parent_bone').strip('"'), vec('point0'), vec('point1'), float(g('radius'))))
    return out


GROUPS = {'head': ('head_0',), 'neck': ('neck_0',), 'chest': ('spine_2', 'spine_3'), 'stomach': ('pelvis', 'spine_0', 'spine_1'),
          'arms': ('arm_upper', 'arm_lower', 'hand'), 'legs': ('leg_upper', 'leg_lower', 'ankle')}


def group_of(joint):
    j = joint.lower()
    for g, keys in GROUPS.items():
        if any(j.startswith(k.lower()) for k in keys): return g
    if j.startswith(('finger', 'clavicle', 'scap')): return 'arms'
    if j.startswith('ball'): return 'legs'
    if j.startswith('eye'): return 'head'
    return None


def seg_dist(P, a, b):
    ab = b - a; t = np.clip(((P - a) @ ab) / max(ab @ ab, 1e-9), 0, 1)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1)


def fit(tpl, V, W, caps=None):
    """V (n,3) bind-pose vertices on the CS2 skeleton, W per vertex [(joint, w)]. Returns per group: share of vertices outside every
    capsule (with 0.5 u grace), and head_offset (u) between head-vertex centre and the head capsule's centre."""
    caps = caps or capsules(open(tpl.vmdl, encoding='utf-8').read())
    J = {n.lower(): v for n, v in tpl.W.items()}
    world = []
    for name, bone, p0, p1, r in caps:
        R, t = J[bone.lower()]
        world.append((name, R @ p0 + t, R @ p1 + t, r))
    inside = np.zeros(len(V), bool)
    for name, a, b, r in world: inside |= seg_dist(V, a, b) <= r + 0.5
    grp = np.array([group_of(max(w, key=lambda x: x[1])[0]) if w else None for w in W], object)
    res = {}
    for g in GROUPS:
        sel = grp == g
        if sel.sum() > 20: res[g] = round(float((~inside[sel]).mean()), 3)
    head = next(((a + b) / 2 for n, a, b, r in world if n.lower() == 'head_0'), None)
    hs = grp == 'head'
    if head is not None and hs.sum():
        c = (V[hs].min(0) + V[hs].max(0)) / 2
        res['head_offset'] = round(float(np.linalg.norm(c - head)), 2)
        res['head_offset_xyz'] = [round(float(x), 2) for x in c - head]
    return res


def stock(tpl):
    if not hasattr(tpl, '_hitfit'):
        V, W = tpl.mesh()
        tpl._hitfit = fit(tpl, V, W)
    return tpl._hitfit


if __name__ == '__main__':
    import gmod2cs2 as g
    from srcmdl import SrcModel
    t = g.Template(sys.argv[1])
    print('stock agent body', stock(t))
    for path in sys.argv[2:]:
        m = SrcModel(path); cv = g.Converter(m, t, log=lambda s: None); cv.transforms()
        used, remap, V, N, W = cv.convert_mesh(m.default_meshes())
        print(os.path.basename(path), fit(t, V, W))
