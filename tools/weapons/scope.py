import numpy as np
def cylinder(x0, x1, r, cy, cz, seg=20, caps=True, voff=0.0):
    V=[]; N=[]; T=[]; F=[]
    ang = np.linspace(0, 2*np.pi, seg, endpoint=False)
    for x in (x0, x1):
        for a in ang:
            V.append([x, cy + r*np.cos(a), cz + r*np.sin(a)]); N.append([0, np.cos(a), np.sin(a)]); T.append([a/(2*np.pi), voff + (x - x0)/10.0])
    for i in range(seg):
        j = (i+1) % seg
        F.append([i, j, seg+i]); F.append([j, seg+j, seg+i])
    if caps:
        for x, nx in ((x0, -1), (x1, 1)):
            c = len(V); V.append([x, cy, cz]); N.append([nx, 0, 0]); T.append([0.5, voff + 0.5])
            ring = 0 if x == x0 else seg
            for i in range(seg):
                j = (i+1) % seg
                F.append([c, ring+j, ring+i] if nx < 0 else [c, ring+i, ring+j])
    return np.array(V, float), np.array(N, float), np.array(T, float), np.array(F, int)
def box(x0, x1, y0, y1, z0, z1):
    c = [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
    faces = [([0,3,2,1],[0,0,-1]),([4,5,6,7],[0,0,1]),([0,1,5,4],[0,-1,0]),([2,3,7,6],[0,1,0]),([1,2,6,5],[1,0,0]),([0,4,7,3],[-1,0,0])]
    V=[]; N=[]; T=[]; F=[]
    for q, n in faces:
        b = len(V)
        for k, i in enumerate(q): V.append(c[i]); N.append(n); T.append([(k in (1,2))*1.0, (k in (2,3))*1.0])
        F.append([b, b+1, b+2]); F.append([b, b+2, b+3])
    return np.array(V, float), np.array(N, float), np.array(T, float), np.array(F, int)
def merge(parts):
    V=[]; N=[]; T=[]; F=[]; base = 0
    for v, n, t, f in parts:
        V.append(v); N.append(n); T.append(t); F.append(f + base); base += len(v)
    return np.vstack(V), np.vstack(N), np.vstack(T), np.vstack(F)
def scope(x0, x1, y, z, r, base_z, mounts):
    """x0..x1 tube extent, (y,z) axis, r radius, base_z = receiver top, mounts = list of x positions"""
    parts = [cylinder(x0+1.4, x1-2.0, r, y, z),
             cylinder(x1-2.0, x1, r*1.35, y, z),           # objective bell
             cylinder(x0, x0+1.4, r*1.15, y, z),           # eyepiece
             cylinder(x1-2.0-0.3, x1-2.0+0.3, r*1.1, y, z), # ring at bell
             cylinder(x0+1.4-0.3, x0+1.4+0.3, r*1.1, y, z)]
    for mx in mounts:
        parts.append(box(mx-0.4, mx+0.4, y-0.45, y+0.45, base_z, z))                   # post
        parts.append(cylinder(mx-0.45, mx+0.45, r*1.12, y, z))                         # ring
    return merge(parts)
