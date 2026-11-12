"""Sanity checks for half-edge meshes in a vmap."""
import sys, numpy as np, dmx
def check(m):
    ev=np.array(m.get('edgeVertexIndices')); eo=np.array(m.get('edgeOppositeIndices')); en=np.array(m.get('edgeNextIndices'))
    ef=np.array(m.get('edgeFaceIndices')); fe=np.array(m.get('faceEdgeIndices')); ve=np.array(m.get('vertexEdgeIndices'))
    n=len(ev); errs=[]
    if not (eo[eo]==np.arange(n)).all(): errs.append('opp')
    src=ev[eo]
    if not (src[en]==ev).all(): errs.append('next-chain')   # next starts where this ends
    if not (ef[en]==ef).all(): errs.append('next-face')
    for f,e in enumerate(fe):
        if ef[e]!=f: errs.append('faceedge'); break
    if not (src[ve]==np.arange(len(ve))).all(): errs.append('vertexedge')
    # next must be a permutation and each vertex's ring (opposite -> next) must reach all its outgoing half-edges: a vertex
    # where two face fans only touch breaks both, and resourcecompiler's map load spins forever on it (12 Nov 2026)
    if len(np.unique(en))!=n: errs.append('next-not-permutation')
    else:
        out=np.bincount(src,minlength=len(ve))
        for v in range(len(ve)):
            e0=ve[v]; e=e0; k=0
            while k<=out[v]:
                k+=1; e=en[eo[e]]
                if e==e0: break
            if k!=out[v]: errs.append('pinch vertex'); break
    nv=len(m.get('vertexData').get('streams')[0].get('data'))
    if nv!=len(ve): errs.append('nverts')
    fvd=m.get('faceVertexData')
    for s in fvd.get('streams'):
        if len(s.get('data'))!=n: errs.append('fvd size '+s.name)
    # a toolslightmapres shell with tens of thousands of faces makes the lightmap charting crawl: 47,912 faces ran 26+ min on one core
    # without finishing, 3,170 faces took 14 s (12 Nov 2026)
    mats=m.get('materials') or []
    if any('toolslightmapres' in x for x in mats) and len(fe)>LMRES_MAX: errs.append('toolslightmapres shell %d faces > %d' % (len(fe), LMRES_MAX))
    return errs
LMRES_MAX=8000
for p in sys.argv[1:]:
    d=dmx.DMX.load(p); bad=0; tot=0
    for e in d.elements:
        if e.type=='CDmePolygonMesh':
            tot+=1; er=check(e)
            if er: bad+=1; print(p, er) if bad<5 else None
    print(p, tot, 'meshes', bad, 'bad')
