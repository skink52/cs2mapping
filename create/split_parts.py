"""Splits a named part (a propeller, a wheel, a turret) out of a model's SMD into its own prop_dynamic model whose origin is on
the part's hub, so a script can spin or move it. The part is every connected piece (vertices welded at 0.05 u) lying entirely
beyond a threshold along one axis. The body SMD loses those triangles; the hub offset is written to a JSON for the script /
map generator (place the part at body origin + hub rotated by the body's angles).

usage: split_parts.py <model .smd> --name prop --axis x --min 120 [--max ...] [--hub x,y,z] [--keep <dir>] [--hubs hubs.json]
  --axis/--min/--max: Hammer axes (SMD (x, y, z) is Hammer (-y, x, z)); pieces with every vertex >= min (and <= max) go.
  Writes <model>_<name>.smd + .vmdl next to the input (material remaps copied from <model>.vmdl when it exists, or --material).
  Idempotent: the unsplit SMD is saved to --keep (default: <CS2_ADDON_OUT>/../split_full) on the first run and re-used.
  Hub: mean along the axis, bounding-box centre across it (or --hub, in Hammer units, model space).

From trenchwarfare-cs2/tools/split_props.py (MIT), made project-neutral.
"""
import os, re, sys, json, shutil, argparse
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
import modelio

OUT = os.environ.get('CS2_ADDON_OUT', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'addon'))
AX = {'x': 0, 'y': 1, 'z': 2}


def read_smd(path):
    L = open(path).read().split('\n'); i = L.index('triangles')
    head, tris, k = L[:i + 1], [], i + 1
    while k < len(L) and L[k].strip() != 'end':
        tris.append(L[k:k + 4]); k += 4
    return head, tris


def split(smd, name, axis='x', lo=None, hi=None, hub=None, keep=None, material=None):
    d = os.path.dirname(os.path.abspath(smd)); base = os.path.splitext(os.path.basename(smd))[0]
    keep = keep or os.path.join(os.path.dirname(os.path.abspath(OUT)), 'split_full')
    os.makedirs(keep, exist_ok=True)
    full = os.path.join(keep, base + '.smd')
    if not os.path.exists(full): shutil.copy(smd, full)          # first run: keep the unsplit mesh
    head, tris = read_smd(full)
    S = np.array([[[float(v) for v in r.split()[1:4]] for r in t[1:]] for t in tris])     # SMD coords
    P = np.stack([-S[..., 1], S[..., 0], S[..., 2]], -1)                                    # Hammer coords
    key = np.round(P.reshape(-1, 3) / 0.05).astype(np.int64)
    _, vid = np.unique(key, axis=0, return_inverse=True); vid = vid.reshape(-1, 3)
    n = vid.max() + 1
    r = np.concatenate([vid[:, 0], vid[:, 1], vid[:, 2]]); c = np.concatenate([vid[:, 1], vid[:, 2], vid[:, 0]])
    _, lab = connected_components(coo_matrix((np.ones(len(r)), (r, c)), shape=(n, n)), directed=False)
    tl = lab[vid[:, 0]]
    a = AX[axis]
    part = np.zeros(len(tris), bool)
    for cid in np.unique(tl):
        sel = tl == cid; q = P[sel][..., a]
        if (lo is None or q.min() >= lo) and (hi is None or q.max() <= hi): part |= sel
    if not part.any(): raise SystemExit('no piece lies entirely in the range on %s' % axis)
    if part.all(): raise SystemExit('the whole model is in the range: nothing would be left')
    Q = P[part].reshape(-1, 3)
    if hub is None:
        hub = (Q.min(0) + Q.max(0)) / 2; hub[a] = Q[:, a].mean()
    hub = np.asarray(hub, float)
    tail = ['end', '']
    open(smd, 'w', newline='\n').write('\n'.join(head + [l for t, p in zip(tris, part) if not p for l in t] + tail))
    sh = np.array([hub[1], -hub[0], hub[2]])                                                 # hub in SMD coords
    out = []
    for t, p, s in zip(tris, part, S):
        if not p: continue
        out.append(t[0])
        for row, sv in zip(t[1:], s):
            q = row.split(); q[1:4] = ['%.4f' % v for v in sv - sh]; out.append(' '.join(q))
    pn = '%s_%s' % (base, name)
    open(os.path.join(d, pn + '.smd'), 'w', newline='\n').write('\n'.join(head + out + tail))
    # material remaps: from the body's vmdl when there is one
    mats = sorted({t[0].strip() for t, p in zip(tris, part) if p})
    remaps = []
    body_vmdl = os.path.join(d, base + '.vmdl')
    if os.path.exists(body_vmdl):
        txt = open(body_vmdl).read()
        remaps = [(f, t) for f, t in re.findall(r'from = "([^"]*)"\s*to = "([^"]*)"', txt) if f in mats or f.rsplit('.', 1)[0] in mats]
    if not remaps and material: remaps = [(m, material) for m in mats]
    if not remaps: print('split: no material remaps found for %s: pass --material' % mats)
    p = os.path.abspath(d).replace('\\', '/')
    rel_dir = p[p.rindex('/models/') + 1:] if '/models/' in p else 'models/' + os.path.basename(d)
    open(os.path.join(d, pn + '.vmdl'), 'w', newline='\n').write(
        modelio.vmdl_text(pn, rel_dir, [pn], remaps, [], archetype='', entity='prop_dynamic', single_lod=True))
    print('%s: %s %d tris (hub %s), body %d tris' % (base, name, part.sum(), hub.round(3).tolist(), (~part).sum()))
    return dict(model='%s/%s.vmdl' % (rel_dir, pn), hub=hub.round(3).tolist(), tris=int(part.sum()))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='split a part out of an SMD into its own prop_dynamic model')
    ap.add_argument('smd'); ap.add_argument('--name', required=True); ap.add_argument('--axis', default='x', choices='xyz')
    ap.add_argument('--min', type=float); ap.add_argument('--max', type=float)
    ap.add_argument('--hub', help='x,y,z in Hammer units (model space)'); ap.add_argument('--keep'); ap.add_argument('--material')
    ap.add_argument('--hubs', help='JSON file collecting {model: hub} entries')
    a = ap.parse_args()
    if a.min is None and a.max is None: ap.error('give --min and/or --max')
    info = split(a.smd, a.name, a.axis, a.min, a.max, [float(v) for v in a.hub.split(',')] if a.hub else None, a.keep, a.material)
    if a.hubs:
        h = json.load(open(a.hubs)) if os.path.exists(a.hubs) else {}
        h[info['model']] = info['hub']; json.dump(h, open(a.hubs, 'w'), indent=1)
