"""Period scope meshes: lathe profiles along X plus turret, rings and mounts. Returns (V, N, T, F, mat_id per face) with mat 0 = blued steel, 1 = brass."""
import numpy as np

def lathe(profile, cy, cz, seg=24, mat=0, cap_start=True, cap_end=True):
    """profile: list of (x, r) in order; surface of revolution about the X axis through (cy, cz)"""
    V=[]; N=[]; T=[]; F=[]
    ang = np.linspace(0, 2*np.pi, seg, endpoint=False)
    P = np.array(profile, float)
    for k, (x, r) in enumerate(P):
        # normal from neighbouring profile slope
        x0, r0 = P[max(k-1, 0)]; x1, r1 = P[min(k+1, len(P)-1)]
        dx, dr = x1 - x0, r1 - r0; ln = np.hypot(dx, dr) or 1.0
        nx, nr = -dr/ln, dx/ln
        for a in ang:
            V.append([x, cy + r*np.cos(a), cz + r*np.sin(a)]); N.append([nx, nr*np.cos(a), nr*np.sin(a)]); T.append([a/(2*np.pi), (x - P[0,0]) / 12.0])
    for k in range(len(P)-1):
        for i in range(seg):
            j = (i+1) % seg; a0 = k*seg; a1 = (k+1)*seg
            F.append([a0+i, a0+j, a1+i]); F.append([a0+j, a1+j, a1+i])
    for cap, k, nx in ((cap_start, 0, -1), (cap_end, len(P)-1, 1)):
        if not cap: continue
        x = P[k,0]; c = len(V); V.append([x, cy, cz]); N.append([nx, 0, 0]); T.append([0.5, 0.5]); ring = k*seg
        for i in range(seg):
            j = (i+1) % seg
            F.append([c, ring+j, ring+i] if nx < 0 else [c, ring+i, ring+j])
    return np.array(V), np.array(N), np.array(T), np.array(F), np.full(len(F), mat)

def vcyl(x, y, z0, z1, r, seg=16, mat=0):
    """vertical cylinder (turret) from z0 to z1 centred at (x, y)"""
    V=[]; N=[]; T=[]; F=[]
    ang = np.linspace(0, 2*np.pi, seg, endpoint=False)
    for z in (z0, z1):
        for a in ang: V.append([x + r*np.cos(a), y + r*np.sin(a), z]); N.append([np.cos(a), np.sin(a), 0]); T.append([a/(2*np.pi), (z-z0)])
    for i in range(seg):
        j = (i+1) % seg; F.append([i, j, seg+i]); F.append([j, seg+j, seg+i])
    c = len(V); V.append([x, y, z1]); N.append([0,0,1]); T.append([0.5,0.5])
    for i in range(seg):
        j = (i+1) % seg; F.append([c, seg+i, seg+j])
    return np.array(V), np.array(N), np.array(T), np.array(F), np.full(len(F), mat)

def box(x0, x1, y0, y1, z0, z1, mat=0):
    c = [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
    faces = [([0,3,2,1],[0,0,-1]),([4,5,6,7],[0,0,1]),([0,1,5,4],[0,-1,0]),([2,3,7,6],[0,1,0]),([1,2,6,5],[1,0,0]),([0,4,7,3],[-1,0,0])]
    V=[]; N=[]; T=[]; F=[]
    for q, n in faces:
        b = len(V)
        for k, i in enumerate(q): V.append(c[i]); N.append(n); T.append([(k in (1,2))*1.0, (k in (2,3))*1.0])
        F.append([b, b+1, b+2]); F.append([b, b+2, b+3])
    return np.array(V, float), np.array(N, float), np.array(T, float), np.array(F), np.full(len(F), mat)

def disc(x, r, cy, cz, nx, seg=24, mat=3):
    """flat disc facing nx (+1/-1 along X)"""
    ang = np.linspace(0, 2*np.pi, seg, endpoint=False)
    V = [[x, cy, cz]] + [[x, cy + r*np.cos(a), cz + r*np.sin(a)] for a in ang]
    N = [[nx, 0, 0]] * (seg+1); T = [[0.5, 0.5]] + [[0.5+0.5*np.cos(a), 0.5+0.5*np.sin(a)] for a in ang]
    F = [[0, 1+i, 1+(i+1)%seg] if nx > 0 else [0, 1+(i+1)%seg, 1+i] for i in range(seg)]
    return np.array(V, float), np.array(N, float), np.array(T, float), np.array(F), np.full(len(F), mat)

def lens_end(xe, d, R, y, z, lip_mat=0):
    """lip ring protruding past the tube end, dark inner wall, recessed glass disc. d = +1 front, -1 rear"""
    a, b = (xe - 0.3, xe + 0.06) if d > 0 else (xe - 0.06, xe + 0.3)
    parts = [lathe([(a, R+0.05), (b, R+0.05)], y, z, mat=lip_mat, cap_start=(d < 0), cap_end=(d > 0))]
    parts.append(lathe([(a, R-0.03), (b, R-0.03)], y, z, mat=0, cap_start=False, cap_end=False))   # inner wall (normals outward, visible edge)
    parts.append(disc(xe - 0.14*d, R-0.03, y, z, d, mat=3))
    return parts

def merge(parts):
    V=[]; N=[]; T=[]; F=[]; M=[]; base = 0
    for v, n, t, f, m in parts:
        V.append(v); N.append(n); T.append(t); F.append(f + base); M.append(m); base += len(v)
    return np.vstack(V), np.vstack(N), np.vstack(T), np.vstack(F), np.concatenate(M)

def ring_mount(x, y, z, r_tube, base_z, width=0.5, post=0.5, mat=0):
    """split ring around the tube + post + foot down to the receiver"""
    parts = [lathe([(x-width/2, r_tube+0.08), (x+width/2, r_tube+0.08)], y, z, mat=mat)]
    parts.append(box(x-post/2, x+post/2, y-0.3, y+0.3, base_z, z - r_tube*0.6, mat))
    parts.append(box(x-post/2-0.25, x+post/2+0.25, y-0.45, y+0.45, base_z, base_z+0.3, mat))
    return parts

def arm_mount(x, y, z, r_tube, base_z, y_post, width=0.5, post=0.5, mat=0):
    """ring on the tube + horizontal arm back to a vertical post standing on the rifle centreline (offset mount)"""
    parts = [lathe([(x-width/2, r_tube+0.08), (x+width/2, r_tube+0.08)], y, z, mat=mat)]
    lo_y, hi_y = sorted((y_post, y))
    parts.append(box(x-post/2, x+post/2, lo_y-0.2, hi_y+0.2, z-0.28, z+0.0, mat))             # arm at axis height
    parts.append(box(x-post/2, x+post/2, y_post-0.3, y_post+0.3, base_z, z-0.2, mat))        # post
    parts.append(box(x-post/2-0.25, x+post/2+0.25, y_post-0.45, y_post+0.45, base_z, base_z+0.3, mat))
    return parts

def allied(x0, y, z, base_z, mounts, y_post=None):
    """Periscopic Prism / Aldis style: slim blued tube, brass bands, small top turret, flared bell objective"""
    L = 11.0; r = 0.5
    prof = [(x0+0.3, 0.6), (x0+0.9, 0.6), (x0+0.95, r), (x0+8.3, r), (x0+9.3, 0.82), (x0+L-0.3, 0.84)]
    parts = [lathe(prof, y, z, mat=0, cap_start=False, cap_end=False)]
    parts += lens_end(x0, -1, 0.6, y, z, lip_mat=1)                                     # brass eyepiece ring + glass
    parts += lens_end(x0+L, 1, 0.84, y, z, lip_mat=1)                                   # brass objective lip + glass
    parts.append(lathe([(x0+4.6, r+0.06), (x0+5.5, r+0.06)], y, z, mat=1))               # brass centre band
    parts.append(vcyl(x0+3.2, y, z + r - 0.05, z + r + 0.35, 0.32, mat=0))               # elevation turret
    parts.append(vcyl(x0+3.2, y, z + r + 0.35, z + r + 0.45, 0.26, mat=1))               # brass cap
    for mx, bz in zip(mounts, base_z):
        parts += ring_mount(mx, y, z, r, bz) if y_post is None else arm_mount(mx, y, z, r, bz, y_post)
    return merge(parts)

def axis(x0, y, z, base_z, mounts, y_post=None):
    """Goerz/Oigee Berlin style: straight tube, big tapered objective bell, flat top drum, claw mounts"""
    L = 11.5; r = 0.5
    prof = [(x0+0.3, 0.58), (x0+0.8, 0.58), (x0+0.85, r), (x0+6.3, r), (x0+8.0, 0.92), (x0+L-0.3, 0.92)]
    parts = [lathe(prof, y, z, mat=0, cap_start=False, cap_end=False)]
    parts += lens_end(x0, -1, 0.58, y, z); parts += lens_end(x0+L, 1, 0.92, y, z)
    parts.append(vcyl(x0+3.0, y, z + r - 0.05, z + r + 0.22, 0.48, mat=0))               # flat adjustment drum
    parts.append(vcyl(x0+3.0, y, z + r + 0.22, z + r + 0.3, 0.3, mat=0))
    parts.append(box(x0+3.0-0.55, x0+3.0+0.55, y-0.08, y+0.08, z + r - 0.05, z + r + 0.1, mat=0))   # index bar
    for mx, bz in zip(mounts, base_z):
        parts += ring_mount(mx, y, z, r, bz, width=0.45, post=0.45) if y_post is None else arm_mount(mx, y, z, r, bz, y_post, width=0.45, post=0.45)
    return merge(parts)
