"""Mesh editing on primitives.py Shapes (verts, faces, mats): extrude / inset faces, bevel edges, subdivide, bend / twist / taper / noise /
smooth deformers, mirror, weld; CSG (union, subtract, intersect, cut); per-face UV control and vertex paint when writing to a map.

Every operation returns a new Shape and keeps faces counter-clockwise from outside; run primitives.check(shape) on the result.

  extrude(shape, faces, distance)          push the selected faces out along their normals, with side walls (a region moves as one)
  inset(shape, faces, amount)              a smaller copy of each face inside it plus a ring of quads (window frames, panels)
  bevel(shape, radius, segments=1, edges=None, min_angle=5)
                                           round (segments > 1) or chamfer (1) sharp edges; CONVEX shapes only (raises otherwise).
                                           edges: None = every edge sharper than min_angle, or fn(a, b) -> bool on the edge's end points
  subdivide(shape, n=2)                    quads -> n x n, triangles -> n^2; other faces get the new edge points (stays closed)
  twist(shape, degrees, axis='z')  taper(shape, scale, axis='z')  bend(shape, degrees, axis='z', toward='x')
  noise(shape, amplitude, size=64, seed=1)  smooth(shape, iterations=1, factor=0.5)  move(shape, faces, offset)
  mirror(shape, axis='x', at=0.0)          the shape and its mirror image (two bodies; keep them apart or union them)
  weld(shape, eps=1e-3)                    merge coincident vertices, drop collapsed faces, fill T-junctions
  union(a, b)  subtract(a, b)  intersect(a, b)   BSP CSG; the cutter's faces keep their own materials (cut_mesh: subtract)
  select(shape, normal=None, min_dot=0.9, box=None, material=None) -> face indices
  uv(face spec) / write(shape, uv={face: spec}, paint=fn(p) -> 0..1, tint=fn(p) -> (r,g,b,a), group='')   CMapMesh with custom UVs / paint

Ported from meshedit.py, meshops.py (BSP CSG, T-junction welding) and the set_uv / paint_blend operations of cs2-map-mcp by Rmgs123
(github.com/Rmgs123/cs2-map-mcp, MIT); fresh code on create/primitives.py and create/vmesh.py.
"""
import math, random, sys
import primitives as P

EPS = 1e-5


def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def _mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def _unit(a):
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-12 else (0.0, 0.0, 0.0)
def _lerp(a, b, t): return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)
AX = {'x': 0, 'y': 1, 'z': 2}


def face_normal(shape, f): return _unit(P.newell(shape[0], shape[1][f]))
def centroid(shape, f):
    pts = [shape[0][i] for i in shape[1][f]]
    return tuple(sum(p[k] for p in pts) / len(pts) for k in range(3))


def _out(verts, faces, mats):
    return weld(([tuple(map(float, v)) for v in verts], [list(f) for f in faces], list(mats)))


# ------------------------------------------------------------------------------------------------ selection
def select(shape, normal=None, min_dot=0.9, box=None, material=None):
    out = []
    for i in range(len(shape[1])):
        if normal is not None and _dot(face_normal(shape, i), _unit(normal)) < min_dot: continue
        if box is not None:
            c = centroid(shape, i)
            if not all(box[0][k] <= c[k] <= box[1][k] for k in range(3)): continue
        if material is not None and shape[2][i] != material: continue
        out.append(i)
    return out


# ------------------------------------------------------------------------------------------------ face operations
def extrude(shape, faces, distance):
    verts, fs, mats = list(shape[0]), [list(f) for f in shape[1]], list(shape[2])
    sel = set(faces)
    owner = {}
    for i, f in enumerate(fs):
        for k in range(len(f)): owner[(f[k], f[(k + 1) % len(f)])] = i
    vn = {}
    for i in sel:
        n = face_normal(shape, i)
        for v in fs[i]: vn[v] = _add(vn.get(v, (0.0, 0.0, 0.0)), n)
    new = {}
    for v, n in vn.items():
        new[v] = len(verts); verts.append(_add(verts[v], _mul(_unit(n), distance)))
    sides = []
    for i in sel:
        f = fs[i]
        for k in range(len(f)):
            a, b = f[k], f[(k + 1) % len(f)]
            if owner.get((b, a)) not in sel:
                sides.append(([a, b, new[b], new[a]], mats[i]))
    for i in sel: fs[i] = [new[v] for v in fs[i]]
    for loop, m in sides: fs.append(loop); mats.append(m)
    return _out(verts, fs, mats)


def inset(shape, faces, amount):
    verts, fs, mats = list(shape[0]), [], []
    sel = set(faces)
    for i, f in enumerate(shape[1]):
        if i not in sel:
            fs.append(list(f)); mats.append(shape[2][i]); continue
        c = centroid(shape, i)
        inner = []
        for v in f:
            p = verts[v]; d = math.sqrt(_dot(_sub(c, p), _sub(c, p)))
            t = min(0.95, amount / d) if d > 0 else 0.0
            inner.append(len(verts)); verts.append(_lerp(p, c, t))
        fs.append(inner); mats.append(shape[2][i])
        for k in range(len(f)):
            fs.append([f[k], f[(k + 1) % len(f)], inner[(k + 1) % len(f)], inner[k]]); mats.append(shape[2][i])
    return _out(verts, fs, mats)


def move(shape, faces, offset):
    vs = {v for i in faces for v in shape[1][i]}
    verts = [_add(p, offset) if i in vs else p for i, p in enumerate(shape[0])]
    return _out(verts, shape[1], shape[2])


# ------------------------------------------------------------------------------------------------ deformers
def _span(shape, ax):
    vals = [p[ax] for p in shape[0]]
    return min(vals), max(vals)


def _centre(shape):
    v = shape[0]
    return tuple((min(p[k] for p in v) + max(p[k] for p in v)) / 2 for k in range(3))


def twist(shape, degrees, axis='z'):
    a = AX[axis]; lo, hi = _span(shape, a); c = _centre(shape)
    i, j = [k for k in range(3) if k != a]
    out = []
    for p in shape[0]:
        t = (p[a] - lo) / (hi - lo) if hi > lo else 0.0
        ang = math.radians(degrees) * t; cs, sn = math.cos(ang), math.sin(ang)
        q = list(p); x, y = p[i] - c[i], p[j] - c[j]
        q[i] = c[i] + x * cs - y * sn; q[j] = c[j] + x * sn + y * cs
        out.append(tuple(q))
    return _out(out, shape[1], shape[2])


def taper(shape, scale, axis='z'):
    a = AX[axis]; lo, hi = _span(shape, a); c = _centre(shape)
    out = []
    for p in shape[0]:
        t = (p[a] - lo) / (hi - lo) if hi > lo else 0.0
        s = 1.0 + (scale - 1.0) * t
        out.append(tuple(p[k] if k == a else c[k] + (p[k] - c[k]) * s for k in range(3)))
    return _out(out, shape[1], shape[2])


def bend(shape, degrees, axis='z', toward='x'):
    """bend the length along `axis` into an arc of `degrees`, curving toward +`toward`; the low end stays put"""
    if abs(degrees) < 1e-9: return _out(shape[0], shape[1], shape[2])
    a, b = AX[axis], AX[toward]
    lo, hi = _span(shape, a); c = _centre(shape)
    L = hi - lo; theta = math.radians(degrees); R = L / theta
    out = []
    for p in shape[0]:
        s = p[a] - lo; off = p[b] - c[b]
        phi = s / R; r = R - off
        q = list(p)
        q[a] = lo + r * math.sin(phi)
        q[b] = c[b] + R - r * math.cos(phi)
        out.append(tuple(q))
    return _out(out, shape[1], shape[2])


def _vnoise(seed):
    rnd = random.Random(seed); perm = list(range(256)); rnd.shuffle(perm); perm += perm
    vals = [rnd.uniform(-1, 1) for _ in range(256)]
    def at(ix, iy, iz): return vals[perm[(perm[(perm[ix & 255] + iy) & 255] + iz) & 255]]
    def n(x, y, z):
        ix, iy, iz = math.floor(x), math.floor(y), math.floor(z); fx, fy, fz = x - ix, y - iy, z - iz
        s = lambda t: t * t * (3 - 2 * t)
        u, v, w = s(fx), s(fy), s(fz)
        out = 0.0
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    out += at(ix + dx, iy + dy, iz + dz) * (u if dx else 1 - u) * (v if dy else 1 - v) * (w if dz else 1 - w)
        return out
    return n


def vertex_normals(shape):
    vn = [(0.0, 0.0, 0.0)] * len(shape[0])
    for i, f in enumerate(shape[1]):
        n = P.newell(shape[0], f)
        for v in f: vn[v] = _add(vn[v], n)
    return [_unit(n) for n in vn]


def noise(shape, amplitude, size=64.0, seed=1):
    n = _vnoise(seed); vn = vertex_normals(shape)
    out = [_add(p, _mul(vn[i], amplitude * n(p[0] / size, p[1] / size, p[2] / size))) for i, p in enumerate(shape[0])]
    return _out(out, shape[1], shape[2])


def smooth(shape, iterations=1, factor=0.5):
    nb = [set() for _ in shape[0]]
    for f in shape[1]:
        for k in range(len(f)): nb[f[k]].add(f[(k + 1) % len(f)]); nb[f[(k + 1) % len(f)]].add(f[k])
    v = list(shape[0])
    for _ in range(iterations):
        v = [_lerp(p, tuple(sum(v[j][k] for j in nb[i]) / len(nb[i]) for k in range(3)), factor) if nb[i] else p for i, p in enumerate(v)]
    return _out(v, shape[1], shape[2])


def mirror(shape, axis='x', at=0.0):
    a = AX[axis]
    ref = [tuple(2 * at - p[k] if k == a else p[k] for k in range(3)) for p in shape[0]]
    return P.merge(shape, (ref, [list(reversed(f)) for f in shape[1]], list(shape[2])))


def subdivide(shape, n=2):
    verts = list(shape[0]); key = {}
    def pt(p):
        k = tuple(round(x, 5) for x in p)
        if k not in key: key[k] = len(verts); verts.append(p)
        return key[k]
    for i, p in enumerate(shape[0]): key.setdefault(tuple(round(x, 5) for x in p), i)
    fs, mats = [], []
    for fi, f in enumerate(shape[1]):
        m = shape[2][fi]; Q = [verts[v] for v in f]
        if len(f) == 4:
            grid = [[pt(_lerp(_lerp(Q[0], Q[3], t), _lerp(Q[1], Q[2], t), s)) for s in [i / n for i in range(n + 1)]] for t in [j / n for j in range(n + 1)]]
            for j in range(n):
                for i in range(n):
                    fs.append([grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]]); mats.append(m)
        elif len(f) == 3:
            row = lambda j: [pt(_lerp(_lerp(Q[0], Q[2], j / n), _lerp(Q[1], Q[2], j / n), (i / (n - j)) if n - j else 0.0)) for i in range(n - j + 1)]
            rows = [row(j) for j in range(n + 1)]
            for j in range(n):
                a, b = rows[j], rows[j + 1]
                for i in range(len(b)):
                    fs.append([a[i], a[i + 1], b[i]]); mats.append(m)
                    if i + 1 < len(b): fs.append([a[i + 1], b[i + 1], b[i]]); mats.append(m)
        else:
            loop = []
            for k in range(len(f)):
                a, b = Q[k], Q[(k + 1) % len(f)]
                loop += [pt(_lerp(a, b, s / n)) for s in range(n)]
            fs.append(loop); mats.append(m)
    return _out(verts, fs, mats)


# ------------------------------------------------------------------------------------------------ welding / T-junctions
def weld(shape, eps=1e-3):
    verts, faces, mats = shape
    key, out_v, remap = {}, [], []
    for p in verts:
        k = tuple(int(round(x / eps)) for x in p)
        if k not in key: key[k] = len(out_v); out_v.append(p)
        remap.append(key[k])
    fs, ms = [], []
    for f, m in zip(faces, mats):
        loop = []
        for v in f:
            v = remap[v]
            if not loop or loop[-1] != v: loop.append(v)
        while len(loop) > 1 and loop[0] == loop[-1]: loop.pop()
        if len(set(loop)) >= 3 and math.sqrt(_dot(P.newell(out_v, loop), P.newell(out_v, loop))) > eps * eps:
            fs.append(loop); ms.append(m)
    used = sorted({v for f in fs for v in f})
    idx = {v: i for i, v in enumerate(used)}
    out_v = [out_v[v] for v in used]
    fs = [[idx[v] for v in f] for f in fs]
    fs = _fill_tjunctions(out_v, fs, eps)
    fs = [P.convex_first(out_v, f) for f in fs]
    return out_v, fs, ms


def _fill_tjunctions(verts, faces, eps):
    """put every vertex that lies inside a face edge into that edge, so neighbouring faces share edges exactly (needed after CSG)"""
    grid = {}
    cell = 64.0
    for i, p in enumerate(verts):
        grid.setdefault((int(p[0] // cell), int(p[1] // cell), int(p[2] // cell)), []).append(i)
    def candidates(a, b):
        lo = [min(a[k], b[k]) - eps for k in range(3)]; hi = [max(a[k], b[k]) + eps for k in range(3)]
        for x in range(int(lo[0] // cell), int(hi[0] // cell) + 1):
            for y in range(int(lo[1] // cell), int(hi[1] // cell) + 1):
                for z in range(int(lo[2] // cell), int(hi[2] // cell) + 1):
                    yield from grid.get((x, y, z), ())
    out = []
    for f in faces:
        loop = []
        for k in range(len(f)):
            ia, ib = f[k], f[(k + 1) % len(f)]
            a, b = verts[ia], verts[ib]; d = _sub(b, a); L2 = _dot(d, d)
            loop.append(ia)
            if L2 < eps * eps: continue
            mids = []
            for c in candidates(a, b):
                if c in (ia, ib): continue
                t = _dot(_sub(verts[c], a), d) / L2
                if t <= 1e-6 or t >= 1 - 1e-6: continue
                q = _add(a, _mul(d, t)); e = _sub(verts[c], q)
                if _dot(e, e) < eps * eps: mids.append((t, c))
            loop += [c for _, c in sorted(mids)]
        out.append(loop)
    return out


# ------------------------------------------------------------------------------------------------ CSG (BSP)
class _Poly:
    __slots__ = ('pts', 'n', 'w', 'mat')
    def __init__(s, pts, mat, plane=None):
        s.pts = pts; s.mat = mat
        if plane: s.n, s.w = plane
        else:
            n = _unit(P.newell(pts, list(range(len(pts))))); s.n = n; s.w = _dot(n, pts[0])
    def flip(s):
        s.pts = s.pts[::-1]; s.n = _mul(s.n, -1); s.w = -s.w


COPL, FRONT, BACK, SPAN = 0, 1, 2, 3


def _split(n, w, poly, cof, cob, front, back):
    types = []; t_all = 0
    for p in poly.pts:
        d = _dot(n, p) - w
        t = BACK if d < -EPS else FRONT if d > EPS else COPL
        t_all |= t; types.append(t)
    if t_all == COPL: (cof if _dot(n, poly.n) > 0 else cob).append(poly)
    elif t_all == FRONT: front.append(poly)
    elif t_all == BACK: back.append(poly)
    else:
        f, b = [], []
        k = len(poly.pts)
        for i in range(k):
            j = (i + 1) % k; ti, tj = types[i], types[j]; vi, vj = poly.pts[i], poly.pts[j]
            if ti != BACK: f.append(vi)
            if ti != FRONT: b.append(vi)
            if (ti | tj) == SPAN:
                t = (w - _dot(n, vi)) / _dot(n, _sub(vj, vi)); v = _lerp(vi, vj, t)
                f.append(v); b.append(v)
        if len(f) >= 3: front.append(_Poly(f, poly.mat, (poly.n, poly.w)))
        if len(b) >= 3: back.append(_Poly(b, poly.mat, (poly.n, poly.w)))


class _Node:
    def __init__(s, polys=None):
        s.n = None; s.w = 0.0; s.front = s.back = None; s.polys = []
        if polys: s.build(polys)
    def invert(s):
        stack = [s]
        while stack:
            x = stack.pop()
            for p in x.polys: p.flip()
            if x.n is not None: x.n = _mul(x.n, -1); x.w = -x.w
            x.front, x.back = x.back, x.front
            stack += [c for c in (x.front, x.back) if c]
    def clip_polys(s, polys):
        if s.n is None: return list(polys)
        f, b = [], []
        for p in polys: _split(s.n, s.w, p, f, b, f, b)
        f = s.front.clip_polys(f) if s.front else f
        b = s.back.clip_polys(b) if s.back else []
        return f + b
    def clip_to(s, other):
        stack = [s]
        while stack:
            x = stack.pop()
            x.polys = other.clip_polys(x.polys)
            stack += [c for c in (x.front, x.back) if c]
    def all(s):
        out, stack = [], [s]
        while stack:
            x = stack.pop(); out += x.polys; stack += [c for c in (x.front, x.back) if c]
        return out
    def build(s, polys):
        if not polys: return
        if s.n is None: s.n, s.w = polys[0].n, polys[0].w
        f, b = [], []
        for p in polys: _split(s.n, s.w, p, s.polys, s.polys, f, b)
        if f:
            if s.front is None: s.front = _Node()
            s.front.build(f)
        if b:
            if s.back is None: s.back = _Node()
            s.back.build(b)


def _polys(shape):
    return [_Poly([tuple(shape[0][v]) for v in f], m) for f, m in zip(shape[1], shape[2])]


def _shape(polys):
    verts, faces, mats = [], [], []
    for p in polys:
        faces.append(list(range(len(verts), len(verts) + len(p.pts)))); verts += p.pts; mats.append(p.mat)
    return weld((verts, faces, mats))


def _csg(a, b, op):
    lim = sys.getrecursionlimit(); sys.setrecursionlimit(max(lim, 20000))
    try:
        A, B = _Node(_polys(a)), _Node(_polys(b))
        if op == 'union':
            A.clip_to(B); B.clip_to(A); B.invert(); B.clip_to(A); B.invert(); A.build(B.all())
        elif op == 'subtract':
            A.invert(); A.clip_to(B); B.clip_to(A); B.invert(); B.clip_to(A); B.invert(); A.build(B.all()); A.invert()
        else:
            A.invert(); B.clip_to(A); B.invert(); A.clip_to(B); B.clip_to(A); A.build(B.all()); A.invert()
        return _shape(A.all())
    finally:
        sys.setrecursionlimit(lim)


def union(a, b): return _csg(a, b, 'union')
def subtract(a, b): return _csg(a, b, 'subtract')
def intersect(a, b): return _csg(a, b, 'intersect')
cut = subtract


# ------------------------------------------------------------------------------------------------ bevel (convex)
def is_convex(shape, eps=1e-3):
    for i, f in enumerate(shape[1]):
        n = face_normal(shape, i); w = _dot(n, shape[0][f[0]])
        if any(_dot(n, p) - w > eps for p in shape[0]): return False
    return True


def clip_plane(shape, n, w, cap_mat=None):
    """keep the part of a convex shape where dot(n, x) <= w; the cut gets a cap face"""
    keep, cut_pts = [], []
    for f, m in zip(shape[1], shape[2]):
        poly = _Poly([tuple(shape[0][v]) for v in f], m)
        fr, bk = [], []
        _split(n, w, poly, bk, bk, fr, bk)
        keep += bk
        for p in bk:
            cut_pts += [q for q in p.pts if abs(_dot(n, q) - w) < 1e-4]
    if len(cut_pts) >= 3:
        c = tuple(sum(p[k] for p in cut_pts) / len(cut_pts) for k in range(3))
        u = _unit(_cross(n, (0, 0, 1) if abs(n[2]) < 0.9 else (1, 0, 0))); v = _cross(n, u)
        uniq = {}
        for p in cut_pts: uniq[tuple(round(x, 4) for x in p)] = p
        ring = sorted(uniq.values(), key=lambda p: math.atan2(_dot(_sub(p, c), v), _dot(_sub(p, c), u)))
        if len(ring) >= 3:
            cap = _Poly(ring, cap_mat or (keep[0].mat if keep else P.DEFAULT_MAT))
            if _dot(cap.n, n) < 0: cap.flip()
            keep.append(cap)
    return _shape(keep)


def bevel(shape, radius, segments=1, edges=None, min_angle=5.0):
    if not is_convex(shape): raise ValueError('bevel works on convex shapes only (bevel the convex parts, then union them)')
    planes = []
    fs = shape[1]
    owner = {}
    for i, f in enumerate(fs):
        for k in range(len(f)): owner[(f[k], f[(k + 1) % len(f)])] = i
    done = set()
    for (a, b), i in owner.items():
        if (b, a) not in owner or (b, a) in done: continue
        done.add((a, b))
        j = owner[(b, a)]
        n1, n2 = face_normal(shape, i), face_normal(shape, j)
        k = _dot(n1, n2)
        if math.degrees(math.acos(max(-1.0, min(1.0, k)))) < min_angle: continue
        pa, pb = shape[0][a], shape[0][b]
        if edges is not None and not edges(pa, pb): continue
        c = _add(pa, _mul(_add(n1, n2), -radius / (1.0 + k)))      # centre of the rounding circle for this edge
        for s in range(1, segments + 1):
            t = s / (segments + 1)
            nn = _unit(_add(_mul(n1, 1 - t), _mul(n2, t)))
            planes.append((nn, _dot(nn, c) + radius, shape[2][i]))
    out = shape
    for n, w, m in planes:
        out = clip_plane(out, n, w, m)
    return out


# ------------------------------------------------------------------------------------------------ writing with UVs and paint
def uv(axis_u=None, axis_v=None, scale=0.25, shift=(0.0, 0.0), rotate=0.0, fit=None):
    """a face's texture mapping in Hammer's terms: world axes (default: Hammer's by the face's dominant normal axis), scale = world units
    per texel (0.25 = Hammer's default), shift in texels, rotate in degrees about the face normal, or fit=(repeats_u, repeats_v) to fit
    the texture over the face that many times"""
    return {'u': axis_u, 'v': axis_v, 'scale': scale, 'shift': shift, 'rotate': rotate, 'fit': fit}


def _axes(n):
    ax = max(range(3), key=lambda k: abs(n[k]))
    if ax == 2: return (1.0, 0.0, 0.0), (0.0, -1.0, 0.0)
    if ax == 0: return (0.0, 1.0, 0.0), (0.0, 0.0, -1.0)
    return (1.0, 0.0, 0.0), (0.0, 0.0, -1.0)


def face_uvs(shape, f, spec, tex=(1024, 1024)):
    """-> (axis_u, axis_v, (scale_u, scale_v), (shift_u, shift_v), [uv per corner])"""
    n = face_normal(shape, f)
    u, v = spec.get('u'), spec.get('v')
    if u is None or v is None: u, v = _axes(n)
    if spec.get('rotate'):
        a = math.radians(spec['rotate']); cs, sn = math.cos(a), math.sin(a)
        u, v = _add(_mul(u, cs), _mul(v, sn)), _add(_mul(v, cs), _mul(u, -sn))
    su = sv = spec.get('scale', 0.25)
    if isinstance(su, (tuple, list)): su, sv = su
    shift = list(spec.get('shift') or (0.0, 0.0))
    pts = [shape[0][i] for i in shape[1][f]]
    if spec.get('fit'):
        ru, rv = spec['fit']
        pu = [_dot(p, u) for p in pts]; pv = [_dot(p, v) for p in pts]
        su = (max(pu) - min(pu)) / (tex[0] * ru) or 0.25; sv = (max(pv) - min(pv)) / (tex[1] * rv) or 0.25
        shift = [-min(pu) / su, -min(pv) / sv]
    coords = [(_dot(p, u) / (tex[0] * su) + shift[0] / tex[0], _dot(p, v) / (tex[1] * sv) + shift[1] / tex[1]) for p in pts]
    return u, v, (su, sv), tuple(shift), coords


def write(shape, uv_specs=None, paint=None, tint=None, group='', attach=True, **node_opts):
    """a CMapMesh for vmaplib's map (vmapgen.open_map first) with per-face UVs, vertex paint (blend 0..1 per vertex: the second material of
    a blend shader) and vertex tint; returns the node"""
    import numpy as np, vmesh
    probs = P.check(shape)
    if probs: raise ValueError('not a closed outward mesh: ' + '; '.join(probs[:3]))
    v, f, m = shape
    pa = ti = None
    if paint is not None: pa = np.array([[float(paint(p)), 0.0, 0.35, 0.0] for p in v])   # make_skybox.py's blend layout
    if tint is not None: ti = np.array([[c / 255.0 if c > 1 else c for c in tint(p)] for p in v])
    if pa is not None and ti is None: ti = np.ones((len(v), 4))
    mesh = vmesh.polymesh_open(v, f, m, paint=pa, tint=ti)
    if uv_specs: apply_uvs(mesh, shape, uv_specs)
    return vmesh.mesh_node(mesh, group, attach=attach, **node_opts)


def apply_uvs(mesh, shape, specs):
    """rewrite texcoords and the face texture axes / scale of a CDmePolygonMesh element written from `shape` by vmesh.polymesh_open"""
    import vmesh
    get = lambda name: next(a for a in mesh.attrs if a[0] == name)[2]
    dest, efaces = get('edgeVertexIndices'), get('edgeFaceIndices')
    def stream(part, prefix):
        arr = get(part)
        for st in arr.get('streams'):
            if st.name.startswith(prefix): return st
    tc = stream('faceVertexData', 'texcoord').attr('data')[2]
    au = stream('faceData', 'textureAxisU').attr('data')[2]; av = stream('faceData', 'textureAxisV').attr('data')[2]
    sc = stream('faceData', 'textureScale').attr('data')[2]
    per = {}
    for fi, spec in specs.items():
        tex = vmesh.TEX_SIZE.get(shape[2][fi], (1024, 1024))
        u, v, (su, sv), shift, coords = face_uvs(shape, fi, spec, tex)
        per[fi] = {vi: c for vi, c in zip(shape[1][fi], coords)}
        au[fi] = tuple(u) + (float(shift[0]),); av[fi] = tuple(v) + (float(shift[1]),); sc[fi] = (float(su), float(sv))
    for h, fi in enumerate(efaces):
        if fi in per: tc[h] = tuple(per[fi][dest[h]])
    return mesh
