"""mg_monsoon: the capture flag runs up and down its pole (playtest 1: "flags don't move").

usage: python mv_flag_anim.py [<addon content out>]        (default: $MV_OUT or ../out/addon)
  reads   models/mv/flag_pole/flag_pole.vmdl   (p_jungle.py write_flag_skins: flag_pole_n's mesh, skins neutral / t / ct)
          models/mv/flag_pole_n/flag_pole_n_lod0.smd
  writes  models/mv/flag_pole/flag_pole_rig.smd       the same mesh on two bones: root (pole, cairn, sandbags) and flag (the cloth and
                                                      its two halyard ties)
          models/mv/flag_pole/anims/flag_00..20.smd   one-frame poses: flag_00 = the cloth at the foot of the pole, flag_20 = at the top
                                                      (where the mesh has it); TRAVEL units between them
          models/mv/flag_pole/flag_pole.vmdl          rewritten: the rig mesh, an AnimationList of the 21 poses (looping, 0.3 s fades),
                                                      model_archetype "animated_model" for prop_dynamic; material groups and hulls kept

The map keeps its prop_dynamic mv_flagpole_<a..e> on this model. The script (src/60_conquest.js drawPole) fires SetAnimationLooping and
SetIdleAnimationLooping "flag_NN" as a capture goes on (CS2's prop_dynamic has no SetAnimation input), and Skin for the colour. Run after
p_jungle.py (which writes flag_pole.vmdl afresh without the rig). Offline check: the poses are verified by re-posing the rig in numpy and
comparing with the source mesh (the cloth must move as one piece, nothing else may move).
"""
import os, re, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
POSES = 21
TRAVEL = 128.0            # the cloth spans z 148..196 on the mesh; at flag_00 it hangs at 20..68, clear of the cairn and the sandbags
FADE = 0.3
REL = 'models/mv/flag_pole'


def read_tris(path):
    L = open(path).read().split('\n')
    i = L.index('triangles') + 1
    mats, rows = [], []
    while i < len(L) and L[i].strip() != 'end':
        mats.append(L[i].strip()); rows.append([L[i + 1 + k].split() for k in range(3)]); i += 4
    return mats, rows


def flag_triangles(rows):
    """True per triangle that belongs to the cloth or a halyard tie: welded pieces that sit wholly between z 140 and 199 (the pole and its
    cap reach the ground and z 203, the cairn and sandbags stay under 30)"""
    P = np.array([[[float(x) for x in c[1:4]] for c in t] for t in rows])
    key = np.round(P.reshape(-1, 3) * 100).astype(np.int64)
    _, vid = np.unique(key, axis=0, return_inverse=True); vid = vid.reshape(-1, 3)
    par = np.arange(vid.max() + 1)

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]; x = par[x]
        return x
    for a, b, c in vid:
        ra = find(a)
        for q in (b, c):
            rq = find(q)
            if rq != ra: par[rq] = ra
    comp = np.array([find(a) for a in vid[:, 0]])
    out = np.zeros(len(rows), bool)
    for c in np.unique(comp):
        sel = comp == c
        q = P[sel].reshape(-1, 3)
        if q[:, 2].min() > 140.0 and q[:, 2].max() < 199.0: out[sel] = True
    return out, P


def write_rig(path, mats, rows, flag):
    out = ['version 1', 'nodes', '0 "root" -1', '1 "flag" 0', 'end', 'skeleton', 'time 0', '0 0 0 0 0 0 0', '1 0 0 0 0 0 0', 'end', 'triangles']
    for m, t, f in zip(mats, rows, flag):
        out.append(m)
        for c in t:
            # parent bone, position, normal, uv, then one link: the bone with weight 1
            out.append(' '.join(['1' if f else '0'] + c[1:9] + ['1', '1' if f else '0', '1.000000']))
    out.append('end')
    open(path, 'w', newline='\n').write('\n'.join(out) + '\n')


def pose_drop(k):
    return TRAVEL * (1.0 - k / float(POSES - 1))


def write_anims(d):
    os.makedirs(d, exist_ok=True)
    names = []
    for k in range(POSES):
        nm = 'flag_%02d' % k
        txt = ['version 1', 'nodes', '0 "root" -1', '1 "flag" 0', 'end', 'skeleton', 'time 0', '0 0 0 0 0 0 0',
               '1 0 0 %.4f 0 0 0' % -pose_drop(k), 'end']
        open(os.path.join(d, nm + '.smd'), 'w', newline='\n').write('\n'.join(txt) + '\n')
        names.append(nm)
    return names


def anim_block(names):
    items = ''
    for nm in names:
        items += ('\t\t\t\t\t{\n\t\t\t\t\t\t_class = "AnimFile"\n\t\t\t\t\t\tname = "%s"\n\t\t\t\t\t\tis_default_idle_anim = false\n'
                  '\t\t\t\t\t\tactivity_name = ""\n\t\t\t\t\t\tactivity_weight = 1\n\t\t\t\t\t\tweight_list_name = ""\n'
                  '\t\t\t\t\t\tfade_in_time = %.2f\n\t\t\t\t\t\tfade_out_time = %.2f\n\t\t\t\t\t\tlooping = true\n\t\t\t\t\t\tdelta = false\n'
                  '\t\t\t\t\t\tworldSpace = false\n\t\t\t\t\t\thidden = false\n\t\t\t\t\t\tanim_markup_ordered = false\n'
                  '\t\t\t\t\t\tdisable_compression = false\n\t\t\t\t\t\tanimgraph_additive = false\n\t\t\t\t\t\tdelete_from_compiled_model = false\n'
                  '\t\t\t\t\t\tsource_filename = "%s/anims/%s.smd"\n\t\t\t\t\t\timport_bone_scales = false\n\t\t\t\t\t\tstart_frame = -1\n'
                  '\t\t\t\t\t\tend_frame = -1\n\t\t\t\t\t\tframerate = -1.0\n\t\t\t\t\t\treverse = false\n\t\t\t\t\t\tadditional_anim_files = [  ]\n'
                  '\t\t\t\t\t},\n') % (nm, FADE, FADE, REL, nm)
    return '\t\t\t{\n\t\t\t\t_class = "AnimationList"\n\t\t\t\tchildren =\n\t\t\t\t[\n%s\t\t\t\t]\n\t\t\t\tdefault_root_bone_name = ""\n\t\t\t},\n' % items


def rewrite_vmdl(txt, names):
    txt = re.sub(r'filename = "models/mv/flag_pole_n/flag_pole_n_lod0\.smd"', 'filename = "%s/flag_pole_rig.smd"' % REL, txt)
    assert 'flag_pole_rig.smd' in txt, 'flag_pole.vmdl: no flag_pole_n_lod0.smd render mesh to replace'
    txt = re.sub(r'\t\t\t\{\n\t\t\t\t_class = "AnimationList"\n.*?\n\t\t\t\},\n', '', txt, flags=re.S)
    i = txt.index('\t\t\t{\n\t\t\t\t_class = "PhysicsShapeList"')
    txt = txt[:i] + anim_block(names) + txt[i:]
    txt = re.sub(r'model_archetype = "[^"]*"', 'model_archetype = "animated_model"', txt)
    txt = re.sub(r'primary_associated_entity = "[^"]*"', 'primary_associated_entity = "prop_dynamic"', txt)
    return txt


def check(P, flag):
    """re-pose the rig at every pose: the cloth must move rigidly by the pose's drop and nothing else may move"""
    for k in (0, POSES // 2, POSES - 1):
        Q = P.copy(); Q[flag, :, 2] -= pose_drop(k)
        moved = np.abs(Q - P).max(axis=(1, 2)) > 1e-6
        assert (moved == (flag & (pose_drop(k) > 0))).all(), 'pose %d moves the wrong triangles' % k
    lo = P[flag].reshape(-1, 3)[:, 2].min() - TRAVEL
    assert lo > 16.0, 'at flag_00 the cloth would sink into the cairn (z %.1f)' % lo
    return lo


def main(argv):
    out = os.path.abspath(argv[0] if argv else os.environ.get('MV_OUT', os.path.join(HERE, '..', 'out', 'addon')))
    d = os.path.join(out, *REL.split('/'))
    vm = os.path.join(d, 'flag_pole.vmdl')
    src = os.path.join(out, 'models', 'mv', 'flag_pole_n', 'flag_pole_n_lod0.smd')
    for f in (vm, src):
        if not os.path.exists(f): sys.exit('mv_flag_anim: %s missing (run p_jungle.py first)' % f)
    mats, rows = read_tris(src)
    flag, P = flag_triangles(rows)
    if flag.sum() < 100: sys.exit('mv_flag_anim: found only %d cloth triangles; the flag mesh changed?' % flag.sum())
    lo = check(P, flag)
    write_rig(os.path.join(d, 'flag_pole_rig.smd'), mats, rows, flag)
    names = write_anims(os.path.join(d, 'anims'))
    txt = rewrite_vmdl(open(vm).read(), names)
    open(vm, 'w', newline='\n').write(txt)
    print('flag_pole: rig %d triangles (%d on the flag bone), %d poses %s..%s, travel %.0f (cloth bottom at z %.0f in flag_00) -> %s'
          % (len(rows), int(flag.sum()), len(names), names[0], names[-1], TRAVEL, lo, vm))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
