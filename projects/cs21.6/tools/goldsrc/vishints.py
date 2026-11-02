"""Low vis hints fitted to a 1.6 map, so CS2's vis keeps 64-unit regions only where there is something to see.

The old hint was one Low box over the whole map's bounds, which is mostly solid rock and the void around the sky brushes.
Here Low covers every 256-unit cell that holds either
  - air connected to a spawn (sampled every 8 units in the map's own hull 0, so doors and func_walls don't split it), or
  - any face that is drawn (world, sky, brush entities; sampled 1 unit in front of the face),
so everywhere a player can be or look at keeps exactly the resolution it had; only cells with neither (inside solid, outside
the sealed map) fall to the one Lowest box over everything. The cells are joined into boxes (skink52's cs2portdocs visfit.py:
cells -> boxes -> merged while mostly made of their own cells; extra cells only ever get the finer hint).
"""
import numpy as np
from scipy import ndimage

CELL = 256.0
SOLID, SKY = -2, -6


def air_cells(g, off, seeds):
    """cells (vmap coordinates) holding hull-0 air connected to the seed points (1.6 coordinates)"""
    lab, _ = ndimage.label((g.c != SOLID) & (g.c != SKY))
    keep = {int(lab[tuple(i)]) for i in g.index(np.array(seeds, float))} - {0}
    idx = np.argwhere(np.isin(lab, list(keep)))
    pts = g.lo + (idx + 0.5) * g.vs + off
    return set(map(tuple, np.floor(pts / CELL).astype(int)))


def face_points(V, step):
    """points covering a convex polygon, at most `step` apart"""
    V = np.asarray(V, float); out = []
    for i in range(1, len(V) - 1):
        a, b, c = V[0], V[i], V[i + 1]
        n = int(max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b)) / step) + 1
        u, v = np.meshgrid(np.arange(n + 1), np.arange(n + 1))
        k = u + v <= n
        out.append(a + np.outer(u[k] / n, b - a) + np.outer(v[k] / n, c - a))
    return np.vstack(out) if out else V[:0]


def _inset(V, by=2.0):
    """polygon pulled `by` units in from its edges (off neighbouring faces' planes)"""
    c = V.mean(0); d = V - c
    L = np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-6)
    return c + d * np.maximum(0.0, (L - by) / L)


class Grid:
    """hull-0 contents of a 1.6 map sampled at voxel centres (lo + (i + 0.5) * vs), 1.6 coordinates"""
    def __init__(self, b, vs=8.0):
        m = b.models[0]
        self.vs = vs
        self.lo = np.floor((np.array(m['mins'], float) - 32) / vs) * vs
        hi = np.ceil((np.array(m['maxs'], float) + 32) / vs) * vs
        self.shape = tuple(int(x) for x in (hi - self.lo) / vs)
        xs, ys, zs = (self.lo[a] + (np.arange(self.shape[a]) + 0.5) * vs for a in range(3))
        X, Y = np.meshgrid(xs, ys, indexing='ij')
        self.c = np.empty(self.shape, np.int8)
        for k, z in enumerate(zs):
            self.c[:, :, k] = b.point_contents(np.stack([X, Y, np.full_like(X, z)], -1), 0)

    def index(self, P):
        return np.clip(np.floor((np.asarray(P) - self.lo) / self.vs).astype(int), 0, np.array(self.shape) - 1)


def _crossings(g, V, n):
    """for each axis: flat indices (lower voxel of the pair) of voxel-centre segments the polygon cuts, and the sign of the
    normal along that axis (+1: the face's front looks at the higher voxel)"""
    out = []
    d = n @ V[0]
    for k in range(3):
        if abs(n[k]) < 1e-6: continue
        a1, a2 = [a for a in range(3) if a != k]
        lo, vs = g.lo, g.vs
        r1 = np.arange(int(np.ceil((V[:, a1].min() - lo[a1]) / vs - 0.5)), int(np.floor((V[:, a1].max() - lo[a1]) / vs - 0.5)) + 1)
        r2 = np.arange(int(np.ceil((V[:, a2].min() - lo[a2]) / vs - 0.5)), int(np.floor((V[:, a2].max() - lo[a2]) / vs - 0.5)) + 1)
        r1 = r1[(r1 >= 0) & (r1 < g.shape[a1])]; r2 = r2[(r2 >= 0) & (r2 < g.shape[a2])]
        if not len(r1) or not len(r2): continue
        J1, J2 = np.meshgrid(r1, r2, indexing='ij'); J1 = J1.ravel(); J2 = J2.ravel()
        u = lo[a1] + (J1 + 0.5) * vs; v = lo[a2] + (J2 + 0.5) * vs
        # inside the polygon in the (a1, a2) projection; a point on an edge counts (two faces sharing a diagonal edge through a
        # voxel centre must not leave a gap there)
        P2 = V[:, [a1, a2]]; E = np.roll(P2, -1, 0) - P2
        cr = (E[:, 0:1] * (v[None] - P2[:, 1:2]) - E[:, 1:2] * (u[None] - P2[:, 0:1])) / np.maximum(np.hypot(E[:, 0:1], E[:, 1:2]), 1e-9)
        inside = np.all(cr > -1e-3, 0) | np.all(cr < 1e-3, 0)
        if not inside.any(): continue
        x = (d - n[a1] * u[inside] - n[a2] * v[inside]) / n[k]
        t = (x - lo[k]) / vs - 0.5
        for i in {0: np.floor(t - 1e-3), 1: np.floor(t + 1e-3)}.values():   # a face through a voxel centre cuts both pairs
            i = i.astype(int)
            ok = (i >= 0) & (i < g.shape[k] - 1)
            idx = [None] * 3; idx[k] = i[ok]; idx[a1] = J1[inside][ok]; idx[a2] = J2[inside][ok]
            out.append((k, int(np.sign(n[k])), np.ravel_multi_index(idx, g.shape)))
    return out


def unseen_sky(b, g, drawn, sky):
    """the sky faces (BSP face indices from `sky`) nobody can see: everything just in front of them is inside a sky brush
    (or solid), and that part of the sky brush can't be looked into from open air without looking through a drawn face.
    1.6 maps keep such faces (to the 1.6 compiler a sky brush's inside is open space), but they double the sky vis works on.
    drawn: every drawn world face (they're what can hide a sky brush's inside)."""
    VIEW = (g.c != SOLID) & (g.c != SKY)
    SKYV = g.c == SKY
    hi = [[] for _ in range(3)]; lo = [[] for _ in range(3)]     # pairs closed to a viewer in the higher / lower voxel
    for fi in drawn:
        for k, s, idx in _crossings(g, b.face_verts(fi), b.face_normal(fi)):
            (hi if s > 0 else lo)[k].append(idx)
    seeds = []
    for k in range(3):
        H = np.unique(np.concatenate(hi[k])) if hi[k] else np.zeros(0, int)
        L = np.unique(np.concatenate(lo[k])) if lo[k] else np.zeros(0, int)
        n = g.shape[k]
        a = [slice(None)] * 3; a[k] = slice(0, n - 1); a = tuple(a)
        bb = [slice(None)] * 3; bb[k] = slice(1, n); bb = tuple(bb)
        # sky below, open air above: the viewer above looks down into the sky voxel
        m = np.zeros(g.shape, bool); m[a] = SKYV[a] & VIEW[bb]
        f = np.flatnonzero(m); f = f[~np.isin(f, H)]
        seeds.append(f)
        # open air below, sky above
        m = np.zeros(g.shape, bool); m[a] = VIEW[a] & SKYV[bb]
        f = np.flatnonzero(m); f = f[~np.isin(f, L)]
        step = int(np.prod(g.shape[k + 1:]))                      # flat index of the higher voxel
        seeds.append(f + step)
    lab, _ = ndimage.label(SKYV, structure=np.ones((3, 3, 3)))
    seeds = np.concatenate(seeds)
    open_sky = np.isin(lab, np.unique(lab.ravel()[seeds])) & SKYV
    out = set()
    for fi in sky:
        V = _inset(b.face_verts(fi)); n = b.face_normal(fi)
        P = face_points(V, 16.0)
        ct = b.point_contents(P + n, 0)
        if not np.all((ct == SOLID) | (ct == SKY)): continue        # open air right in front
        v = tuple(g.index(P + n * 2).T)
        if np.all(SKYV[v] & ~open_sky[v]): out.add(fi)
    return out


def face_cells(polys, step=32.0):
    """cells touched by polygons (vmap coordinates), sampled every `step` units"""
    out = set()
    for V in polys:
        out |= set(map(tuple, np.floor(face_points(V, step) / CELL).astype(int)))
    return out


def boxes_from_cells(cells):
    left = set(cells); out = []
    while left:
        i, j, k = min(left)
        x1 = i
        while (x1 + 1, j, k) in left: x1 += 1
        y1 = j
        while all((x, y1 + 1, k) in left for x in range(i, x1 + 1)): y1 += 1
        z1 = k
        while all((x, y, z1 + 1) in left for x in range(i, x1 + 1) for y in range(j, y1 + 1)): z1 += 1
        for x in range(i, x1 + 1):
            for y in range(j, y1 + 1):
                for z in range(k, z1 + 1): left.discard((x, y, z))
        out.append(((i, j, k), (x1 + 1, y1 + 1, z1 + 1)))
    return out


def merge_boxes(boxes, own, fill=0.75, cap=4096):
    """join boxes whose union is mostly own cells (boxes stay disjoint)"""
    boxes = [(tuple(a), tuple(b)) for a, b in boxes]
    if len(boxes) < 2: return boxes
    allc = np.array(list(own)); o = allc.min(0); sz = allc.max(0) - o + 1
    g = np.zeros(sz + 1, np.int32)
    for c in own: g[tuple(np.array(c) - o + 1)] = 1
    S = g.cumsum(0).cumsum(1).cumsum(2)
    def cnt(a, b):
        x0, y0, z0 = np.array(a) - o; x1, y1, z1 = np.array(b) - o
        return int(S[x1, y1, z1] - S[x0, y1, z1] - S[x1, y0, z1] - S[x1, y1, z0] + S[x0, y0, z1] + S[x0, y1, z0] + S[x1, y0, z0] - S[x0, y0, z0])
    while len(boxes) > 1:
        A = np.array([bx[0] for bx in boxes]); B = np.array([bx[1] for bx in boxes])
        best = None
        for i in range(len(boxes)):
            ua = np.minimum(A[i], A[i + 1:]); ub = np.maximum(B[i], B[i + 1:])
            for a, b in zip(ua, ub):
                v = int(np.prod(b - a))
                if v > cap: continue
                n = cnt(a, b)
                if n / v < fill or (best and n / v <= best[0]): continue
                ins = np.all((A >= a) & (B <= b), 1); ovl = np.all((A < b) & (B > a), 1)
                if (ovl & ~ins).any(): continue
                best = (n / v, tuple(a), tuple(b), ins)
        if not best: break
        _, a, b, ins = best
        boxes = [bx for k, bx in enumerate(boxes) if not ins[k]] + [(a, b)]
    return boxes


def low_boxes(cells, max_boxes=40):
    """(mins, maxs) boxes in vmap units covering every cell (and a few extra)"""
    for fill in (0.75, 0.6, 0.5):
        bx = merge_boxes(boxes_from_cells(cells), cells, fill)
        if len(bx) <= max_boxes: break
    return [(np.array(a) * CELL, np.array(b) * CELL) for a, b in bx]
