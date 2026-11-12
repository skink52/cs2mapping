"""Dynamic-archetype twins of our models, for map entities that are (or become) prop_dynamic (remaster step 5, REVIEW_WORLD_1 H2/H4).
Reads the content addon's model sources (read only) and writes the twins into a staging folder; nothing is written into the addon.

usage: python tools/dyn_models.py [--addon DIR] [--out DIR] [--list FILE]
  defaults: --addon C:/source1/links/content_addons/mg_trenchwarfare, --out <project>/out/addon (staging), --list <out>/../step5_models.txt

What it makes (paths relative to the addon; all new files, the originals are untouched):
  models/tw/revet_planks_broken/revet_planks_broken_dyn.vmdl            the undergroundopen blockers (H2)
  models/tw/revet_planks_broken_128/revet_planks_broken_128_dyn.vmdl    the woodsopen blockers (H2)
  models/tw/tl_bench/tl_bench_dyn.vmdl                                  only used by patch_world_1.py --user-h1 unlock
    = the original .vmdl with model_archetype "" (a static_prop_model on a prop_dynamic may be DELETED by the map compile:
      docs/BUILD.md in monsoon, unconfirmed for this compiler) and primary_associated_entity "prop_dynamic". Same SMDs, same hulls.
  models/tw/minenwerfer/minenwerfer_dyn.vmdl (+ minenwerfer_dyn_lod0/1.smd, anims/minenwerfer_idle.smd, anims/minenwerfer_fire.smd)
  models/tw/ext/mortar_58mm/mortar_58mm_dyn.vmdl (+ mortar_58mm_dyn.smd, anims/mortar_58mm_idle.smd, anims/mortar_58mm_fire.smd)
    = the mortar tubes as animated props for mortar_<tg>_K (CONTRACT; the script's SetAnimation "fire", CONFIG.MORTAR_FIRE_ANIM).
      Skeleton root -> body -> barrel. The render SMDs are the originals with every triangle weighted to body or barrel (the barrel
      picked by geometry, below); the hull stays the original SMD on the root (it never moves). Animations at 30 fps:
        idle  the rest pose, default idle, looping (StartingAnim / IdleAnim "idle")
        fire  0.8 s, not looping, ends exactly in the rest pose:
              minenwerfer (lMW n.A. has recoil cylinders): the tube slides 4.5 u back along its axis in 2 frames and runs out again
              over 0.6 s; the carriage thumps 0.8 u down and settles.
              mortar_58mm (tube fixed in trunnions on a wooden bed): the bed thumps 1.4 u down with a 0.7 degree rock, the tube flips
              1.5 degrees about the trunnion axle and settles.
      Barrel selection: minenwerfer from its generator (tools/p_minenwerfer.py: tube + bore within 6.8 u of the tube axis through the
      pivot (0, 0, 29.4) at 50 degrees; the cradle band (7.1 u) and recoil cylinders (8.3 u) stay on the body). mortar_58mm: the
      largest elongated connected piece (tube + trunnion axle, one mesh in the Sketchfab source); the axle centre is the pivot.
Writes the list of staged files (addon-relative) to --list. Level: "untested" until compiled (docs/reference/compatibility.md).
"""
import argparse, math, os, re, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
ADDON = r'C:\source1\links\content_addons\mg_trenchwarfare'
FPS = 30.0
NF = 24                                     # fire: 0.8 s

TWINS = ['models/tw/revet_planks_broken/revet_planks_broken.vmdl', 'models/tw/revet_planks_broken_128/revet_planks_broken_128.vmdl',
         'models/tw/tl_bench/tl_bench.vmdl']
written = []


def rd(addon, rel):
    p = os.path.join(addon, rel.replace('/', os.sep))
    if not os.path.isfile(p): sys.exit('dyn_models: missing source %s' % p)
    return open(p, encoding='utf-8', errors='strict').read()


def wr(out, rel, text):
    p = os.path.join(out, rel.replace('/', os.sep))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', newline='\n', encoding='utf-8') as f: f.write(text)
    written.append(rel)


def dyn_header(txt):
    """static -> dynamic archetype; refuses a vmdl that does not say static_prop_model exactly once"""
    if len(re.findall(r'model_archetype = "static_prop_model"', txt)) != 1: raise ValueError('expected one static_prop_model archetype')
    txt = txt.replace('model_archetype = "static_prop_model"', 'model_archetype = ""')
    txt = re.sub(r'primary_associated_entity = "[^"]*"', 'primary_associated_entity = "prop_dynamic"', txt)
    return txt


def twin(addon, out, rel):
    txt = dyn_header(rd(addon, rel))
    dst = rel[:-5] + '_dyn.vmdl'
    wr(out, dst, txt)
    return dst


# ---------------------------------------------------------------- SMD reweighting
def read_smd(text):
    L = text.split('\n')
    i = L.index('triangles') + 1
    tris = []
    while i < len(L) and L[i].strip() != 'end':
        mat = L[i]; vs = [L[i + k].split() for k in (1, 2, 3)]
        tris.append((mat, vs)); i += 4
    return tris


def write_rig_smd(tris, bone_of_tri, pivot):
    out = ['version 1', 'nodes', '0 "root" -1', '1 "body" 0', '2 "barrel" 1', 'end', 'skeleton', 'time 0',
           '0 0 0 0 0 0 0', '1 0 0 0 0 0 0', '2 %.4f %.4f %.4f 0 0 0' % tuple(pivot), 'end', 'triangles']
    for (mat, vs), b in zip(tris, bone_of_tri):
        out.append(mat)
        for q in vs: out.append('%d %s 1 %d 1' % (b, ' '.join(q[1:9]), b))
    out.append('end')
    return '\n'.join(out) + '\n'


def pos(tris): return np.array([[[float(v) for v in q[1:4]] for q in vs] for _, vs in tris])


def axis_dist(P, p0, d):
    r = P - p0; t = r @ d
    return np.linalg.norm(r - t[..., None] * d, axis=-1), t


def anim_smd(frames):
    """frames: list of (body (tx, ty, tz, rx, ry, rz), barrel (px, py, pz, rx, ry, rz)) in SMD space, radians"""
    out = ['version 1', 'nodes', '0 "root" -1', '1 "body" 0', '2 "barrel" 1', 'end', 'skeleton']
    for f, (b, br) in enumerate(frames):
        out += ['time %d' % f, '0 0 0 0 0 0 0', '1 ' + ' '.join('%.5f' % v for v in b), '2 ' + ' '.join('%.5f' % v for v in br)]
    out.append('end')
    return '\n'.join(out) + '\n'


def recoil(f):
    """0 -> 1 in 2 frames, held 1 frame, back to 0 by frame 20 (smoothstep); exactly 0 after"""
    if f <= 0: return 0.0
    if f <= 2: return (0.65, 1.0)[f - 1]
    if f == 3: return 0.95
    s = min(1.0, (f - 3) / 17.0)
    return 0.95 * (1 - s * s * (3 - 2 * s))


THUMP = [0, -0.7, -1.0, -0.6, -0.1, 0.15, 0.05, 0.0]
def thump(f): return THUMP[f] if f < len(THUMP) else 0.0


def anim_entries(model_dir, base):
    def node(name, src, idle, loop, fade):
        return ('\t\t\t\t\t{\n\t\t\t\t\t\t_class = "AnimFile"\n\t\t\t\t\t\tname = "%s"\n\t\t\t\t\t\tis_default_idle_anim = %s\n'
                '\t\t\t\t\t\tactivity_name = ""\n\t\t\t\t\t\tactivity_weight = 1\n\t\t\t\t\t\tweight_list_name = ""\n'
                '\t\t\t\t\t\tfade_in_time = %s\n\t\t\t\t\t\tfade_out_time = %s\n\t\t\t\t\t\tlooping = %s\n\t\t\t\t\t\tdelta = false\n'
                '\t\t\t\t\t\tworldSpace = false\n\t\t\t\t\t\thidden = false\n\t\t\t\t\t\tanim_markup_ordered = false\n'
                '\t\t\t\t\t\tdisable_compression = false\n\t\t\t\t\t\tanimgraph_additive = false\n\t\t\t\t\t\tdelete_from_compiled_model = false\n'
                '\t\t\t\t\t\tsource_filename = "%s/anims/%s.smd"\n\t\t\t\t\t\timport_bone_scales = false\n\t\t\t\t\t\tstart_frame = -1\n'
                '\t\t\t\t\t\tend_frame = -1\n\t\t\t\t\t\tframerate = %.1f\n\t\t\t\t\t\treverse = false\n\t\t\t\t\t\tadditional_anim_files = [  ]\n\t\t\t\t\t},\n'
                % (name, 'true' if idle else 'false', fade, fade, 'true' if loop else 'false', model_dir, src, FPS))
    return ('\t\t\t{\n\t\t\t\t_class = "BoneMarkupList"\n\t\t\t\tbone_cull_type = "None"\n\t\t\t},\n'
            '\t\t\t{\n\t\t\t\t_class = "AnimationList"\n\t\t\t\tchildren =\n\t\t\t\t[\n'
            + node('idle', base + '_idle', True, True, '0.1') + node('fire', base + '_fire', False, False, '0.05')
            + '\t\t\t\t]\n\t\t\t\tdefault_root_bone_name = ""\n\t\t\t},\n')


def animated_twin(addon, out, rel, smd_names, classify, frames_fn):
    """rel: the static vmdl; smd_names: the render SMD file names it uses (same folder); classify(P) -> (bone per tri, pivot)"""
    d = rel.rsplit('/', 1)[0]; base = rel.rsplit('/', 1)[1][:-5]
    txt = dyn_header(rd(addon, rel))
    pivot = None
    for nm in smd_names:
        src = '%s/%s.smd' % (d, nm)
        tris = read_smd(rd(addon, src))
        bones, pv = classify(pos(tris))
        if pivot is None: pivot = pv
        dst_nm = nm.replace(base, base + '_dyn', 1)
        wr(out, '%s/%s.smd' % (d, dst_nm), write_rig_smd(tris, bones, pivot))
        n = txt.count('filename = "%s"' % src)
        if n != 1: raise ValueError('%s: %d references to %s' % (rel, n, src))
        txt = txt.replace('filename = "%s"' % src, 'filename = "%s/%s.smd"' % (d, dst_nm))
        print('  %s: %d triangles, %d on the barrel' % (dst_nm, len(bones), int(np.sum(np.array(bones) == 2))))
    rest = ((0, 0, 0, 0, 0, 0), tuple(pivot) + (0, 0, 0))
    wr(out, '%s/anims/%s_idle.smd' % (d, base), anim_smd([rest, rest]))
    wr(out, '%s/anims/%s_fire.smd' % (d, base), anim_smd(frames_fn(pivot)))
    # the bone markup and the clips go in front of the physics shapes
    k = txt.index('\t\t\t{\n\t\t\t\t_class = "PhysicsShapeList"')
    txt = txt[:k] + anim_entries(d, base) + txt[k:]
    dst = '%s/%s_dyn.vmdl' % (d, base)
    wr(out, dst, txt)
    return dst


# ---------------------------------------------------------------- the two mortars
EL = math.radians(50.0); SC = 1.4
MW_PIV = np.array([0.0, 0.0, 21.0 * SC])                       # SMD space = (model y, -model x, z)
MW_D = np.array([0.0, -math.cos(EL), math.sin(EL)])


def mw_classify(P):
    r, t = axis_dist(P, MW_PIV, MW_D)
    on = (r.max(1) <= 6.8) & (t.min(1) >= -13.0 * SC - 1.0) & (t.max(1) <= 25.6 * SC + 1.0)
    return np.where(on, 2, 1), MW_PIV


def mw_frames(pivot):
    fr = []
    for f in range(NF):
        b = (0, 0, 0.8 * thump(f), 0, 0, 0)
        p = np.asarray(pivot) - MW_D * 4.5 * recoil(f)
        fr.append((b, tuple(p) + (0, 0, 0)))
    return fr


_M58 = {}


def m58_classify(P):
    """the tube is the largest piece longer than 50 u running mostly up; pivot = its trunnion axle centre (vertices beyond the tube
    radius across x)"""
    flat = P.reshape(-1, 3); key = np.round(flat, 2)
    _, inv = np.unique(key, axis=0, return_inverse=True); inv = inv.reshape(-1, 3)
    par = list(range(inv.max() + 1))
    def f_(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    for a, b, c in inv:
        ra = f_(a); par[f_(b)] = ra; par[f_(c)] = ra
    lab = np.array([f_(a) for a in inv[:, 0]])
    best = None
    for l in np.unique(lab):
        q = P[lab == l].reshape(-1, 3); c = q.mean(0)
        u, s, vt = np.linalg.svd(q - c, full_matrices=False); e = (q - c) @ vt[0]
        ln = e.max() - e.min()
        if ln > 50 and abs(vt[0][2]) > 0.8 and abs(c[0]) < 3 and (best is None or (lab == l).sum() > best[1]):
            best = (l, (lab == l).sum())
    if best is None: raise ValueError('mortar_58mm: no tube piece found')
    on = lab == best[0]
    q = P[on].reshape(-1, 3)
    pins = q[np.abs(q[:, 0]) > 8.0]
    if len(pins) < 8: raise ValueError('mortar_58mm: trunnion axle not found')
    pivot = np.array([0.0, pins[:, 1].mean(), pins[:, 2].mean()])
    if not _M58: _M58.update(pivot=pivot, tris=int(on.sum()))
    return np.where(on, 2, 1), _M58['pivot']


def m58_frames(pivot):
    fr = []
    for f in range(NF):
        k = thump(f)
        b = (0, 0, 1.4 * k, math.radians(0.7) * k, 0, 0)
        fr.append((b, tuple(pivot) + (math.radians(1.5) * recoil(f), 0, 0)))
    return fr


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--addon', default=ADDON); ap.add_argument('--out', default=os.path.join(PROJ, 'out', 'addon'))
    ap.add_argument('--list', default=None)
    a = ap.parse_args(argv)
    out = os.path.abspath(a.out)
    if os.path.normcase(out).startswith(os.path.normcase(os.path.abspath(a.addon))): sys.exit('dyn_models: --out must not be inside the addon')
    made = {}
    for rel in TWINS: made[rel] = twin(a.addon, out, rel)
    made['models/tw/minenwerfer/minenwerfer.vmdl'] = animated_twin(a.addon, out, 'models/tw/minenwerfer/minenwerfer.vmdl',
                                                                   ['minenwerfer_lod0', 'minenwerfer_lod1'], mw_classify, mw_frames)
    made['models/tw/ext/mortar_58mm/mortar_58mm.vmdl'] = animated_twin(a.addon, out, 'models/tw/ext/mortar_58mm/mortar_58mm.vmdl',
                                                                       ['mortar_58mm'], m58_classify, m58_frames)
    lst = a.list or os.path.join(os.path.dirname(out), 'step5_models.txt')
    with open(lst, 'w', newline='\n') as f:
        f.write('\n'.join(written) + '\n')
    for k, v in made.items(): print('%s -> %s' % (k, v))
    print('%d files staged under %s; list in %s' % (len(written), out, lst))
    return made


if __name__ == '__main__':
    main()
