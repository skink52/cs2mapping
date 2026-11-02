"""Splits each aircraft's propeller out of the weathered plane SMD into its own prop_dynamic model (origin on the hub, axis +x)
so the script can spin it. Idempotent: works from out/ext_full/<plane>.smd (the unsplit SMD, saved on the first run).
Usage: split_props.py <addon>; writes models/tw/ext/<plane>/<plane>_prop.{smd,vmdl} and props.json (hub offsets)."""
import os, sys, json, shutil
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
import modelio

OUT = sys.argv[1]
FULL = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'ext_full')
FRONT = {'plane_dr1': 120.0, 'plane_spad7': 114.5}      # components entirely forward of this x are the propeller + hub
os.makedirs(FULL, exist_ok=True)
hubs = {}
for name, xf in FRONT.items():
    d = os.path.join(OUT, 'models/tw/ext', name)
    src = os.path.join(FULL, name + '.smd')
    if not os.path.exists(src): shutil.copy(os.path.join(d, name + '.smd'), src)
    L = open(src).read().split('\n'); i = L.index('triangles')
    head, tris = L[:i + 1], []
    k = i + 1
    while L[k] != 'end':
        tris.append(L[k:k + 4]); k += 4
    S = np.array([[[float(v) for v in r.split()[1:4]] for r in t[1:]] for t in tris])          # smd coords
    P = np.stack([-S[..., 1], S[..., 0], S[..., 2]], -1)                                        # hammer coords (nose +x)
    key = np.round(P.reshape(-1, 3) / 0.05).astype(np.int64); _, vid = np.unique(key, axis=0, return_inverse=True); vid = vid.reshape(-1, 3)
    n = vid.max() + 1; r = np.concatenate([vid[:, 0], vid[:, 1], vid[:, 2]]); c = np.concatenate([vid[:, 1], vid[:, 2], vid[:, 0]])
    _, lab = connected_components(coo_matrix((np.ones(len(r)), (r, c)), shape=(n, n)), directed=False)
    tl = lab[vid[:, 0]]
    prop = np.zeros(len(tris), bool)
    for cid in np.unique(tl):
        sel = tl == cid
        if P[sel][..., 0].min() >= xf: prop |= sel
    Q = P[prop].reshape(-1, 3)
    hub = np.array([Q[:, 0].mean(), (Q[:, 1].min() + Q[:, 1].max()) / 2, (Q[:, 2].min() + Q[:, 2].max()) / 2])
    hubs[name] = hub.round(3).tolist()
    tail = ['end', '']
    open(os.path.join(d, name + '.smd'), 'w', newline='\n').write('\n'.join(head + [l for t, p in zip(tris, prop) if not p for l in t] + tail))
    sh = np.array([hub[1], -hub[0], hub[2]])                                                     # hub in smd coords
    out = []
    for t, p, s in zip(tris, prop, S):
        if not p: continue
        out.append(t[0])
        for row, sv in zip(t[1:], s):
            q = row.split(); q[1:4] = ['%.4f' % v for v in sv - sh]; out.append(' '.join(q))
    pn = name + '_prop'
    open(os.path.join(d, pn + '.smd'), 'w', newline='\n').write('\n'.join(head + out + tail))
    tname = name + '_skin'
    open(os.path.join(d, pn + '.vmdl'), 'w', newline='\n').write(
        modelio.vmdl_text(pn, 'models/tw/ext/%s' % name, [pn], [(tname + '.vmat', 'materials/models/tw/ext/%s/%s.vmat' % (name, tname))], [],
                          archetype='', entity='prop_dynamic'))
    print('%s: propeller %d tris (hub %s), body %d tris' % (name, prop.sum(), hubs[name], (~prop).sum()))
json.dump(hubs, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'prop_hubs.json'), 'w'), indent=1)
