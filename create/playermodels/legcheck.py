"""Leg check: which converted models have knees or feet that tear when CS2 bends them. For each model, the leg skin is posed in
poses.py's run and crouch and every leg triangle edge compared with its rest length; edges stretched past 1.8x or crushed below
0.35x are counted (a clean knee stays well inside). Prints the worst first.

    python -I legcheck.py <catalog.json> [--batch N | --only a,b] [--jobs 8]
"""
import json, os, sys
import numpy as np
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def check(args):
    slug, it, tpl_path, work, root = args
    import gmod2cs2 as g, poses
    from srcmdl import SrcModel
    try:
        mdl = os.path.join(root, *it['mdl'].split('/'))
        m = SrcModel(mdl); t = g.Template(tpl_path)
        conv = g.Converter(m, t, log=lambda s: None); conv.fixed_scale = it.get('scale')
        mode = it.get('mode') or ('rigid' if it.get('fun') else 'own')
        conv.transforms(mode)
        if mode in ('own', 'ownall'): t = g.own_template(t, conv.own_joints); conv.t = t
        meshes = m.default_meshes(it.get('bodygroups'))
        used, remap, V, N, W = conv.convert_mesh(meshes)
        tris = np.vstack([remap[me['tris']] for me in meshes if len(me['tris'])])
        leg = np.array([sum(x for j, x in w if j.startswith(('leg_', 'ankle_', 'ball_'))) > 0.5 for w in W])
        tl = tris[leg[tris].all(1)]
        if not len(tl): return slug, None
        e = np.vstack([tl[:, [0, 1]], tl[:, [1, 2]], tl[:, [2, 0]]])
        L0 = np.linalg.norm(V[e[:, 0]] - V[e[:, 1]], axis=1); ok = L0 > 0.05
        out = {}
        for name in ('run', 'crouch'):
            Q = poses.skin(V, W, poses.pose_world(t, poses.POSES[name]))
            r = np.linalg.norm(Q[e[ok, 0]] - Q[e[ok, 1]], axis=1) / L0[ok]
            out[name] = (float(((r > 1.8) | (r < 0.35)).mean() * 100), float(r.max()))
        return slug, out
    except Exception as ex:
        return slug, 'error: %s' % ex


def main():
    import fetch
    a = sys.argv[1:]
    cat = json.load(open(a[0], encoding='utf-8')); p = fetch.paths(cat)
    only = set(a[a.index('--only') + 1].split(',')) if '--only' in a else None
    batch = int(a[a.index('--batch') + 1]) if '--batch' in a else None
    jobs = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 8
    todo = []
    for it in cat['items']:
        if not it.get('chosen') or (only and it['slug'] not in only) or (batch and it.get('batch') != batch): continue
        root = os.path.join(p['work'], 'fbx', it['slug']) if it.get('fbx') else os.path.join(p['work'], 'extract', str(it['id']))
        todo.append((it['slug'], it, p['template'], p['work'], root))
    with Pool(jobs) as pool: res = pool.map(check, todo)
    def worst(r): return -max(v[0] for v in r[1].values()) if isinstance(r[1], dict) else 0
    for slug, r in sorted(res, key=worst):
        if isinstance(r, dict): print('%-24s run %5.2f%% (max x%.1f)  crouch %5.2f%% (max x%.1f)' % (slug, r['run'][0], r['run'][1], r['crouch'][0], r['crouch'][1]))
        else: print('%-24s %s' % (slug, r))


if __name__ == '__main__':
    main()
