"""Hangar crew (list item M5; skink52: "pilot models in the hangar ... gmod pilot and worker models"): converted GMod player
models, posed and written as STATIC props for the garage bays.

    python -I tools/hangar_crew.py <addon out dir> [--preview DIR] [--only key,..]

For each entry of CREW: the GMod model goes through create/playermodels/gmod2cs2.convert into a scratch folder (materials +
textures come out of it; env GMOD_STATIC_DUMP makes it leave the skinned mesh and the CS2 skeleton as a pickle), the mesh is
posed with create/playermodels/poses.py (pose_world / skin; normals turned with the same matrices), scaled to SCALE (the
arenas' human scale, tools/arenas/sprawl_detail.py: a mech is 15 m) and written as models/ifr/crew/<key>.vmdl (one SMD, a
material remap per source material, no collision). The model's own materials are copied to the addon under their converter
paths (materials/models/player/gmod/<slug>/). Nothing of this goes in git: third-party models (workshop ids in CREW).
Needs the player-model work folder (C:\\source1\\playermodels: extract\\<id>\\, template\\). out/addon/_gen/crew.json lists what
was built (tools/patch_crew.py places them).
"""
import os, sys, json, pickle, shutil, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
CREATE = os.path.normpath(os.path.join(HERE, '..', '..', '..', 'create'))
PM = os.path.join(CREATE, 'playermodels')
sys.path.insert(0, CREATE); sys.path.insert(0, PM)
import numpy as np

WORK = os.environ.get('PM_WORK', r'C:\source1\playermodels')
SCALE = 0.6
X, Y, Z = np.array([1., 0, 0]), np.array([0, 1., 0]), np.array([0, 0, 1.])
# arms out of the A pose, at the sides. Turning only the upper arm down about the shoulder joint folds the deltoid into the chest: the
# shoulders came out rolled forward and too narrow (skink52, 11 Nov 2026). So the arms drop less (they hang a little off the body,
# as over a vest), the collar bones go back a touch, the chest opens, and 'shift' moves each arm (the joint and everything below
# it) outward and up, which the skin between collar bone and arm stretches over: the shoulder line is as wide as in the A pose.
DOWN = {'clavicle_L': [(Z, 5)], 'clavicle_R': [(Z, -5)], 'arm_upper_L': [(X, -23), (Y, 8)], 'arm_upper_R': [(X, 23), (Y, 8)],
        'arm_lower_L': [(X, -6), (Y, -20)], 'arm_lower_R': [(X, 6), (Y, -16)], 'spine_3': [(Y, -5)],
        'shift': {'arm_upper_L': (0.0, 1.5, 0.6), 'arm_upper_R': (0.0, -1.5, 0.6)}}
POSES = {
    # looking up at the machine, weight on one leg
    'look_up': dict(DOWN, head_0=[(Y, -24), (Z, 8)], neck_0=[(Y, -10)], spine_2=[(Y, -5)], spine_1=[(Z, 6)], leg_upper_R=[(X, -5)], leg_upper_L=[(X, 4)]),
    # marshalling: both arms up, guiding the mech into the bay
    'marshal': {'arm_upper_L': [(X, 104)], 'arm_upper_R': [(X, -118)], 'arm_lower_L': [(X, 22)], 'arm_lower_R': [(X, -12)], 'head_0': [(Y, -16)], 'neck_0': [(Y, -8)],
                'leg_upper_L': [(X, 6)], 'leg_upper_R': [(X, -6)]},
    # reading a slate held in both hands, head down
    'slate': {'arm_upper_L': [(X, -34), (Y, -16)], 'arm_upper_R': [(X, 34), (Y, -16)], 'arm_lower_L': [(Y, -78), (Z, -30)], 'arm_lower_R': [(Y, -78), (Z, 30)],
              'head_0': [(Y, 20)], 'neck_0': [(Y, 8)], 'spine_2': [(Y, 5)]},
    # down at a foot actuator, arms forward
    'kneel': {'drop': 22, 'leg_upper_L': [(Y, -100)], 'leg_upper_R': [(Y, -100)], 'leg_lower_L': [(Y, 125)], 'leg_lower_R': [(Y, 125)], 'ankle_L': [(Y, -25)], 'ankle_R': [(Y, -25)],
              'spine_1': [(Y, 22)], 'arm_upper_L': [(X, -36), (Y, -58)], 'arm_upper_R': [(X, 36), (Y, -50)], 'arm_lower_L': [(Y, -22), (Z, -12)], 'arm_lower_R': [(Y, -30), (Z, 12)], 'head_0': [(Y, 10)]},
    # at ease, head turned to the side (a pilot waiting for the sortie)
    'at_ease': dict(DOWN, head_0=[(Z, 28)], neck_0=[(Z, 10)], spine_1=[(Z, -5)], leg_upper_L=[(X, 5)], leg_upper_R=[(X, -5)]),
}
# key -> (slug, workshop id, mdl inside the item, pose)
CREW = {
    'pilot_look': ('ua_eclipse_pilot', 3772745299, 'models/urbanassault/ua_eclipsedivisionpilot.mdl', 'look_up'),
    'pilot_ease': ('ua_eclipse_pilot', 3772745299, 'models/urbanassault/ua_eclipsedivisionpilot.mdl', 'at_ease'),
    'worker_marshal': ('ua_hmcworker', 3772745299, 'models/urbanassault/ua_hmcworker.mdl', 'marshal'),
    'worker_kneel': ('ua_hmcworker', 3772745299, 'models/urbanassault/ua_hmcworker.mdl', 'kneel'),
    'tech_slate': ('mechanic', 734781319, 'models/player/mechanic.mdl', 'slate'),
    'tech_ease': ('mechanic', 734781319, 'models/player/mechanic.mdl', 'at_ease'),
}


class Skel:
    def __init__(self, d): self.W, self.parent, self.order = d['W'], d['parent'], d['order']


def convert(slug, wid, mdl, stage):
    """the converter's own run into `stage`; returns the dump"""
    import gmod2cs2, fetch
    cat = json.load(open(os.path.join(PM, 'catalog.json'), encoding='utf-8'))
    root = os.path.join(WORK, 'extract', str(wid))
    roots = [root] + fetch.base_roots(fetch.paths(cat))
    tpl = gmod2cs2.Template(os.environ.get('PM_TEMPLATE', os.path.join(WORK, 'template')))
    dump = os.path.join(stage, slug + '.pkl')
    os.environ['GMOD_STATIC_DUMP'] = dump
    try:
        gmod2cs2.convert(os.path.join(root, *mdl.split('/')), slug, roots, tpl, stage, 0, None, 1024, None, log=lambda s: None, mode='own')
    finally:
        os.environ.pop('GMOD_STATIC_DUMP', None)
    return pickle.load(open(dump, 'rb'))


def posed(d, pose):
    import poses
    t = Skel(d)
    spec = {k: v for k, v in POSES[pose].items() if k == 'drop' or k in t.W}
    miss = [k for k in POSES[pose] if k not in ('drop', 'shift') and k not in t.W]
    if miss: print('   pose %s: joints not on this skeleton: %s' % (pose, ', '.join(miss)))
    S = poses.pose_world(t, spec)
    for j0, dv in (POSES[pose].get('shift') or {}).items():      # a joint and its subtree moved as one (model units, before SCALE)
        if j0 not in t.W: continue
        T = np.eye(4); T[:3, 3] = dv
        for j in t.order:
            a = j
            while a is not None and a != j0: a = t.parent[a]
            if a == j0: S[j] = T @ S[j]
    V, N = np.asarray(d['V'], float), np.asarray(d['N'], float)
    Q = poses.skin(V, d['weights'], S)
    M = np.zeros_like(N)
    for i, w in enumerate(d['weights']):
        tot = sum(x for _, x in w) or 1
        for j, x in w: M[i] += x / tot * (S[j][:3, :3] @ N[i])
    M /= np.maximum(np.linalg.norm(M, axis=1, keepdims=True), 1e-9)
    Q[:, 2] -= Q[:, 2].min()                      # feet on the floor whatever the pose
    return Q, M


def write_smd(path, V, N, UV, sets, names):
    """one SMD, a material name per triangle set. ModelDoc turns SMD 90 degrees: write (y, -x, z); SMD v = 1 - v_img (create/modelio.py)"""
    L = ['version 1', 'nodes', '0 "root" -1', 'end', 'skeleton', 'time 0', '0 0 0 0 0 0 0', 'end', 'triangles']
    fmt = '0 %.4f %.4f %.4f %.4f %.4f %.4f %.5f %.5f'
    for faces, nm in zip(sets, names):
        for f in faces:
            L.append(nm)
            for i in f:
                x, y, z = V[i]; nx, ny, nz = N[i]
                L.append(fmt % (y, -x, z, ny, -nx, nz, UV[i, 0], 1 - UV[i, 1]))
    L.append('end')
    open(path, 'w', newline='\n').write('\n'.join(L) + '\n')


def main(out, preview=None, only=None):
    import modelio
    stage = tempfile.mkdtemp(prefix='ifr_crew_')
    rel = 'models/ifr/crew'
    os.makedirs(os.path.join(out, rel), exist_ok=True)
    dumps, built = {}, {}
    for key, (slug, wid, mdl, pose) in CREW.items():
        if only and key not in only: continue
        if slug not in dumps:
            print('crew: converting %s' % slug, flush=True)
            dumps[slug] = convert(slug, wid, mdl, stage)
            src = os.path.join(stage, 'materials', 'models', 'player', 'gmod', slug)
            dst = os.path.join(out, 'materials', 'models', 'player', 'gmod', slug)
            if os.path.isdir(dst): shutil.rmtree(dst)
            shutil.copytree(src, dst)
        d = dumps[slug]
        Q, M = posed(d, pose)
        UV = np.asarray(d['UV'], float)
        if preview:
            from preview import render
            os.makedirs(preview, exist_ok=True)
            render(Q, UV, [(np.asarray(f), tx) for f, tx in zip(d['sets'], d['texs'])], os.path.join(preview, 'crew_%s.png' % key), views=('front', 'three', 'side'), H=560,
                   label='%s  (%s, %s)' % (key, slug, pose))
        names = ['crew_%s_%d.vmat' % (key, k) for k in range(len(d['sets']))]
        write_smd(os.path.join(out, rel, key + '.smd'), Q * SCALE, M, UV, d['sets'], names)
        txt = modelio.vmdl_text(key, rel, [key], list(zip(names, d['mats'])), [], single_lod=True)
        open(os.path.join(out, rel, key + '.vmdl'), 'w', newline='\n').write(txt)
        built[key] = {'model': '%s/%s.vmdl' % (rel, key), 'slug': slug, 'pose': pose, 'height': round(float(Q[:, 2].max() * SCALE), 1),
                      'triangles': int(sum(len(f) for f in d['sets'])), 'materials': list(d['mats'])}
        print('crew: %s  %d tris, %.0f u tall, %d materials' % (key, built[key]['triangles'], built[key]['height'], len(names)), flush=True)
    gen = os.path.join(out, '_gen'); os.makedirs(gen, exist_ok=True)
    json.dump({'scale': SCALE, 'crew': built}, open(os.path.join(gen, 'crew.json'), 'w'), indent=1)
    shutil.rmtree(stage, ignore_errors=True)


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    main(a[0], a[a.index('--preview') + 1] if '--preview' in a else None, set(a[a.index('--only') + 1].split(',')) if '--only' in a else None)
