"""First-person default gloves of any CS2 agent as a ModelDoc DMX on the template skeleton.
Input: the agent's firstperson_default_gloves_arms glove draw call extracted from its vmdl_c (cs2mapping create/s2: extractAgent with
meshGroupMask 0xffff -> JSON {material, P, N, UV, J (bone names), W, I}); container: a stock arms DMX on the same skeleton (the template's
arms_stock/arms.dmx). The glove mesh element is rewritten with the agent's vertices, weights (bone names -> the container's jointList),
UVs (vmdl_c UVs are already in DMX orientation, verified on tm_phoenix: exact match), normals and UV-derived tangents; every other
mesh (bare forearm) is dropped.
usage: python3 tools/agent_gloves.py <glove.json> <container arms dmx> <out dmx>"""
import sys, json
import numpy as np
import dmx9


def tangents(P, N, UV, F):
    t = np.zeros_like(P); b = np.zeros_like(P)
    p0, p1, p2 = P[F[:, 0]], P[F[:, 1]], P[F[:, 2]]
    w0, w1, w2 = UV[F[:, 0]], UV[F[:, 1]], UV[F[:, 2]]
    e1, e2 = p1 - p0, p2 - p0; d1, d2 = w1 - w0, w2 - w0
    r = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]; r = np.where(np.abs(r) < 1e-12, 1e-12, r)
    sd = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / r[:, None]; td = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / r[:, None]
    for k in range(3): np.add.at(t, F[:, k], sd); np.add.at(b, F[:, k], td)
    t = t - N * (t * N).sum(1, keepdims=True); t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-12)
    w = np.where((np.cross(N, t) * b).sum(1) < 0, -1.0, 1.0)
    return np.concatenate([t, w[:, None]], 1)


def build(glove_json, container, out):
    g = json.load(open(glove_json))
    P = np.array(g['P']).reshape(-1, 3); N = np.array(g['N']).reshape(-1, 3); UV = np.array(g['UV']).reshape(-1, 2)
    J = np.array(g['J']).reshape(-1, 4); W = np.array(g['W']).reshape(-1, 4); F = np.array(g['I']).reshape(-1, 3)
    dm = dmx9.DMX.load(container); model = dm.root['model']
    jl = [j.name for j in model['jointList']]
    missing = sorted(set(J[W > 0]) - set(jl)); assert not missing, 'bones not in the container skeleton: %s' % missing
    jix = {n: i for i, n in enumerate(jl)}
    keep = None
    for c in list(model['children']):
        sh = c.get('shape') if c.type == 'DmeDag' else None
        if sh is None: continue
        if keep is None and any('glove' in fs['material']['mtlName'] for fs in sh['faceSets']): keep = sh; continue
        model['children'].remove(c)
        model['jointList'][:] = [j for j in model['jointList'] if j is not c]
    assert keep is not None, 'no glove mesh in ' + container
    vd = keep['currentState']; n = len(P); ident = list(range(n))
    T4 = tangents(P, N, UV, F)
    vd['position$0'] = [tuple(map(float, p)) for p in P]; vd['position$0Indices'] = ident
    vd['normal$0'] = [tuple(map(float, p)) for p in N]; vd['normal$0Indices'] = ident
    vd['texcoord$0'] = [tuple(map(float, p)) for p in UV]; vd['texcoord$0Indices'] = ident
    vd['tangent$0'] = [tuple(map(float, p)) for p in T4]; vd['tangent$0Indices'] = ident
    vd['jointCount'] = 4
    vd['blendindices$0'] = [int(jix.get(x, 0)) for x in J.ravel()]
    vd['blendweights$0'] = [float(x) for x in W.ravel()]
    fs = keep['faceSets'][0]; keep['faceSets'] = [fs]
    fs['material']['mtlName'] = g['material']
    fl = []
    for f in F: fl += [int(f[0]), int(f[1]), int(f[2]), -1]
    fs['faces'] = fl
    keep.name = g['material'].split('/')[-1].replace('.vmat', '')
    if keep.get('bindState') is not None:
        for k in ('position$0', 'normal$0'):
            if k in keep['bindState'].attrs: keep['bindState'][k] = vd[k]
    dm.save(out)
    print('%s: %d verts, %d tris, %s' % (out, n, len(F), g['material']))


if __name__ == '__main__':
    build(*sys.argv[1:4])
