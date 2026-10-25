"""Load static meshes from a binary FBX into Source space (inches, Z-up, +X forward)."""
import math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fbxparse import read_fbx

def rotm(deg):
    rx, ry, rz = [math.radians(float(v)) for v in deg]
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    X = np.array([[1,0,0],[0,cx,-sx],[0,sx,cx]]); Y = np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]]); Z = np.array([[cz,-sz,0],[sz,cz,0],[0,0,1]])
    return Z @ Y @ X

class Part:
    def __init__(self, name, V, N, T, F):
        self.name, self.V, self.N, self.T, self.F = name, V, N, T, F

def load(path, axes='zxy', scale=1.0, flipv=False):
    root, ver = read_fbx(path)
    objs = root.first('Objects'); con = root.first('Connections')
    byid = {o.props[0]: o for o in objs.children}
    gs = root.first('GlobalSettings')
    unit = gs.prop70('UnitScaleFactor')[0] if gs and gs.prop70('UnitScaleFactor') else 1.0
    TO_IN = unit / 2.54 * scale
    children = {}; geom_of = {}
    for c in con.children:
        if c.props[0] != 'OO': continue
        a, b = byid.get(c.props[1]), c.props[2]
        if a is None: continue
        if a.name == 'Model': children.setdefault(b, []).append(a.props[0])
        elif a.name == 'Geometry': geom_of[b] = a
    def local(m):
        g = lambda k, d: np.array(m.prop70(k) or d, dtype=np.float64)
        T = g('Lcl Translation', [0,0,0]); R = g('Lcl Rotation', [0,0,0]); S = g('Lcl Scaling', [1,1,1])
        Rpre = g('PreRotation', [0,0,0]); Rpost = g('PostRotation', [0,0,0])
        Roff = g('RotationOffset', [0,0,0]); Rp = g('RotationPivot', [0,0,0]); Soff = g('ScalingOffset', [0,0,0]); Sp = g('ScalingPivot', [0,0,0])
        def tr(v): M = np.eye(4); M[:3,3] = v; return M
        def rt(d): M = np.eye(4); M[:3,:3] = rotm(d); return M
        def sc(v): M = np.eye(4); M[:3,:3] = np.diag(v); return M
        return tr(T) @ tr(Roff) @ tr(Rp) @ rt(Rpre) @ rt(R) @ np.linalg.inv(rt(Rpost)) @ tr(-Rp) @ tr(Soff) @ tr(Sp) @ sc(S) @ tr(-Sp)
    def geo(m):
        g = lambda k, d: np.array(m.prop70(k) or d, dtype=np.float64)
        M = np.eye(4); M[:3,3] = g('GeometricTranslation', [0,0,0])
        R = np.eye(4); R[:3,:3] = rotm(g('GeometricRotation', [0,0,0]))
        S = np.eye(4); S[:3,:3] = np.diag(g('GeometricScaling', [1,1,1]))
        return M @ R @ S
    world = {}
    def walk(mid, P):
        m = byid[mid]; W = P @ local(m); world[mid] = W
        for c in children.get(mid, []): walk(c, W)
    for mid in children.get(0, []): walk(mid, np.eye(4))
    AXI = {'x':0, 'y':1, 'z':2}; AX = np.zeros((3,3))
    for i, a in enumerate(axes): AX[i, AXI[a.lower()]] = -1 if a.isupper() else 1
    parts = []
    for mid, W in world.items():
        m = byid[mid]; g = geom_of.get(mid)
        if g is None: continue
        Wg = W @ geo(m)
        verts = np.array(g.first('Vertices').props[0], dtype=np.float64).reshape(-1,3)
        pvi = np.array(g.first('PolygonVertexIndex').props[0], dtype=np.int64)
        ln = g.first('LayerElementNormal'); nrm_d = np.array(ln.first('Normals').props[0]).reshape(-1,3)
        nmap = ln.first('MappingInformationType').props[0]
        if ln.first('ReferenceInformationType').props[0] == 'IndexToDirect': nrm_d = nrm_d[np.array(ln.first('NormalsIndex').props[0])]
        lu = g.first('LayerElementUV')
        if lu is not None:
            uv_d = np.array(lu.first('UV').props[0]).reshape(-1,2); umap = lu.first('MappingInformationType').props[0]
            if lu.first('ReferenceInformationType').props[0] == 'IndexToDirect': uv_d = uv_d[np.array(lu.first('UVIndex').props[0])]
        else: uv_d = None; umap = 'ByPolygonVertex'
        polys = []; cur = []
        for k, i in enumerate(pvi):
            if i < 0: cur.append((~i, k)); polys.append(cur); cur = []
            else: cur.append((i, k))
        R3 = Wg[:3,:3]; Ninv = np.linalg.inv(R3).T; flip = np.linalg.det(R3) < 0
        cv=[]; cn=[]; ct=[]; cf=[]; ci = 0
        for poly in polys:
            idx = []
            for vi, k in poly:
                p = AX @ (R3 @ verts[vi] + Wg[:3,3]) * TO_IN
                n = AX @ (Ninv @ (nrm_d[k] if nmap == 'ByPolygonVertex' else nrm_d[vi])); n /= (np.linalg.norm(n) or 1)
                u = np.zeros(2) if uv_d is None else (uv_d[k] if umap == 'ByPolygonVertex' else uv_d[vi]).copy()
                if flipv: u[1] = 1 - u[1]
                cv.append(p); cn.append(n); ct.append(u); idx.append(ci); ci += 1
            for t in range(1, len(idx)-1):
                tri = [idx[0], idx[t], idx[t+1]]
                if flip: tri = tri[::-1]
                cf.append(tri)
        parts.append(Part(m.props[1].split('\x00')[0], np.array(cv), np.array(cn), np.array(ct), np.array(cf)))
    return parts

def weld(V, N, T, F, nd=4):
    key = np.round(np.hstack([V, N, T]), nd)
    _, uniq, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    return V[uniq], N[uniq], T[uniq], inv.reshape(-1)[F]

def components(V, F, nd=4):
    """face -> component id, by shared vertex position"""
    key = np.round(V, nd); _, inv = np.unique(key, axis=0, return_inverse=True); inv = inv.reshape(-1)
    par = np.arange(inv.max()+1)
    def f(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    for a, b, c in F:
        ra = f(inv[a]); par[f(inv[b])] = ra; par[f(inv[c])] = f(ra)
    return np.array([f(inv[a]) for a, _, _ in F])

def tangents(V, N, T, F):
    tan = np.zeros((len(V), 3)); bit = np.zeros((len(V), 3))
    i0, i1, i2 = F[:,0], F[:,1], F[:,2]
    e1 = V[i1]-V[i0]; e2 = V[i2]-V[i0]; d1 = T[i1]-T[i0]; d2 = T[i2]-T[i0]
    r = d1[:,0]*d2[:,1] - d2[:,0]*d1[:,1]; r = np.where(np.abs(r) < 1e-12, 1e-12, r); r = 1.0 / r
    sd = (e1*d2[:,1:2] - e2*d1[:,1:2]) * r[:,None]; td = (e2*d1[:,0:1] - e1*d2[:,0:1]) * r[:,None]
    for i in (i0, i1, i2): np.add.at(tan, i, sd); np.add.at(bit, i, td)
    t = tan - N * np.sum(N*tan, axis=1, keepdims=True)
    ln = np.linalg.norm(t, axis=1, keepdims=True); t = np.where(ln > 1e-9, t / np.where(ln > 1e-9, ln, 1), np.array([[1.0,0,0]]))
    w = np.where(np.sum(np.cross(N, t) * bit, axis=1) < 0, -1.0, 1.0)
    return np.hstack([t, w[:,None]])
