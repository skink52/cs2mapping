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
    nv=len(m.get('vertexData').get('streams')[0].get('data'))
    if nv!=len(ve): errs.append('nverts')
    fvd=m.get('faceVertexData')
    for s in fvd.get('streams'):
        if len(s.get('data'))!=n: errs.append('fvd size '+s.name)
    return errs
for p in sys.argv[1:]:
    d=dmx.DMX.load(p); bad=0; tot=0
    for e in d.elements:
        if e.type=='CDmePolygonMesh':
            tot+=1; er=check(e)
            if er: bad+=1; print(p, er) if bad<5 else None
    print(p, tot, 'meshes', bad, 'bad')
