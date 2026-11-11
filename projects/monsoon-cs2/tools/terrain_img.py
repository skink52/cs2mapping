"""Image-driven terrain: height fields as 16-bit images, erosion and other image operations on them, and paint / foliage images derived from them.

  python terrain_img.py export <module.py:function> --bounds x0,y0,x1,y1 --cell 32 --out height.png      a height function -> 16-bit PNG + .json
  python terrain_img.py detail <height.png> --out <dir> [--protect mask.png] [--feather 6] [--recipe r.json] [--seed 1]
        erodes the height image and writes detail.png (what to ADD to the height; exactly 0 where the mask is white), eroded.png,
        hillshade_before/after.png, splat_rock/mud/grass.png, density_trees/undergrowth.png, cavity.png and report.json
  python terrain_img.py shade <height.png> <out.png>                                                      a hillshade to look at
Library (arrays are Z[i, j] with x along i, like vmapgen.Terrain's grids; a Field carries bounds + cell and is callable as f(X, Y)):
  Field.from_fn(fn, bounds, cell) / Field.load(png, bounds=, height_range=) / .save(png) / f(X, Y)   bilinear, so a Field is a vmapgen.Terrain
        height function or a detail layer: height = lambda X, Y: base(X, Y) + detail(X, Y)
  apply_ops(F, ops)        cs2-map-mcp's add_terrain ops on a Field: hill, valley, ridge, plateau, noise, flatten, heightmap (+ ours: level by a mask image)
  hydraulic / thermal / gullies / terraces / outcrops (Z, cell, ...) -> Z      erosion and rock detail
  flow(Z, cell) -> upstream area in cells;  fill_pits;  slope_deg;  cavity;  hillshade
  discs / along / below / feather     protect masks (flags, roads, water); detail(Z, cell, protect, recipe) -> the layer to add, 0 where protect == 1
  splat(Z, cell)           -> {'rock', 'mud', 'grass', 'trees', 'undergrowth', 'cavity'} 0..1 images for vertex paint and foliage
  scatter_density(density Field, spacing, seed) -> [(x, y)]     points by a density image, for gen_world.place / your own placer
  load_mask(png, like=Field) -> 0..1 array      a painted layout image (roads, clearings) as a mask on a Field's grid

Image convention (cs2-map-mcp's): pixel column i is the i-th x step and row j the j-th y step from the bounds' minimum, so row 0 is the
lowest y (the PNG looks upside down in a viewer; the hillshades are written north up). 8-bit or 16-bit greyscale.

From cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT): the heightmap PNG -> terrain route (16-bit, height_range, bilinear
resize) and the terrain op set of its terrain.py (hill / valley / ridge / plateau / noise / flatten, radial and path smoothsteps).
Fresh code. NOT from cs2-map-mcp (it has no erosion, no splat or density images; its scatter takes a number per area): the erosion,
gully, outcrop, protect-mask, splat and density parts, written here on the usual published methods (batched droplet erosion after
H. Beyer 2015, talus relaxation, priority-flood pit filling after Barnes 2014, multiple-flow-direction accumulation). numpy + Pillow only.
"""
import argparse, heapq, importlib.util, json, math, os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import noise as N


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, float) - a) / (b - a) if b != a else (np.asarray(x, float) >= a) * 1.0, 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- the field and its image
class Field:
    """Z[i, j] at x0 + i * cell, y0 + j * cell. Call it with arrays of world x, y for the bilinear value (clamped at the edges)."""

    def __init__(self, Z, bounds, cell):
        self.Z = np.asarray(Z, float); self.bounds = tuple(float(v) for v in bounds); self.cell = float(cell)
        nx = int(round((self.bounds[2] - self.bounds[0]) / self.cell)); ny = int(round((self.bounds[3] - self.bounds[1]) / self.cell))
        if self.Z.shape != (nx + 1, ny + 1): raise ValueError('Z is %s, bounds / cell need %s' % (self.Z.shape, (nx + 1, ny + 1)))

    @staticmethod
    def grid(bounds, cell):
        x0, y0, x1, y1 = bounds
        nx = int(round((x1 - x0) / cell)); ny = int(round((y1 - y0) / cell))
        if nx < 1 or ny < 1 or abs(x0 + nx * cell - x1) > 1e-6 or abs(y0 + ny * cell - y1) > 1e-6:
            raise ValueError('bounds must be a whole number of cells each way')
        return np.meshgrid(x0 + np.arange(nx + 1) * float(cell), y0 + np.arange(ny + 1) * float(cell), indexing='ij')

    @classmethod
    def from_fn(cls, fn, bounds, cell):
        X, Y = cls.grid(bounds, cell)
        return cls(np.asarray(fn(X, Y), float), bounds, cell)

    @property
    def XY(self): return self.grid(self.bounds, self.cell)

    def like(self, Z): return Field(Z, self.bounds, self.cell)

    def __call__(self, X, Y):
        X = np.asarray(X, float); Y = np.asarray(Y, float)
        n, m = self.Z.shape
        u = np.clip((X - self.bounds[0]) / self.cell, 0, n - 1); v = np.clip((Y - self.bounds[1]) / self.cell, 0, m - 1)
        i = np.minimum(u.astype(int), n - 2); j = np.minimum(v.astype(int), m - 2)
        fu = u - i; fv = v - j; Z = self.Z
        return (Z[i, j] * (1 - fu) + Z[i + 1, j] * fu) * (1 - fv) + (Z[i, j + 1] * (1 - fu) + Z[i + 1, j + 1] * fu) * fv

    def save(self, path, lo=None, hi=None):
        """16-bit PNG + <path>.json (bounds, cell, lo, step: z = lo + step * pixel). If the range spans 0, 0 lands exactly on a level,
        so a detail layer's untouched areas read back as exactly 0."""
        lo = float(self.Z.min() if lo is None else lo); hi = float(self.Z.max() if hi is None else hi)
        if hi <= lo: hi = lo + 1.0
        step = (hi - lo) / 65535.0
        if lo < 0 < hi:
            step = (hi - lo) / 65534.0                       # one spare level, then shift lo down so that -lo / step is whole
            k = math.ceil(-lo / step); lo = -k * step
        pix = np.clip(np.rint((self.Z - lo) / step), 0, 65535).astype(np.uint16)
        Image.fromarray(np.ascontiguousarray(pix.T)).save(path)
        meta = {'bounds': list(self.bounds), 'cell': self.cell, 'lo': lo, 'step': step, 'row0': 'ymin', 'size': [pix.shape[0], pix.shape[1]]}
        with open(path + '.json', 'w') as f: json.dump(meta, f, indent=1)
        return meta

    @classmethod
    def load(cls, path, bounds=None, cell=None, height_range=None):
        """A greyscale PNG (8 or 16 bit). With its .json sidecar nothing else is needed. Without: bounds + height_range [min, max]
        (pixel 0 = min, full white = max) and optionally cell (the image is resized bilinearly to the grid, as cs2-map-mcp does)."""
        with Image.open(path) as im:
            if im.mode not in ('L', 'I;16', 'I;16L', 'I;16B', 'I'): raise ValueError('heightmap must be greyscale (L or 16-bit), got ' + im.mode)
            if im.width * im.height > 16777216: raise ValueError('heightmap exceeds 16 million pixels')
            full = 255.0 if im.mode == 'L' else 65535.0
            pix = im.convert('F')
            side = path + '.json'
            if os.path.isfile(side) and bounds is None and height_range is None:
                with open(side) as f: meta = json.load(f)
                return cls(np.asarray(pix, float).T * meta['step'] + meta['lo'], meta['bounds'], meta['cell'])
            if bounds is None or height_range is None: raise ValueError('no .json sidecar: give bounds and height_range')
            if cell is None: cell = (bounds[2] - bounds[0]) / (im.width - 1)
            nx = int(round((bounds[2] - bounds[0]) / cell)); ny = int(round((bounds[3] - bounds[1]) / cell))
            if pix.size != (nx + 1, ny + 1): pix = pix.resize((nx + 1, ny + 1), Image.Resampling.BILINEAR)
            lo, hi = height_range
            return cls(np.asarray(pix, float).T / full * (hi - lo) + lo, bounds, cell)


def save8(path, A):
    """a 0..1 array as an 8-bit PNG in the same layout as the height images (row 0 = lowest y)"""
    Image.fromarray(np.ascontiguousarray(np.clip(np.rint(np.asarray(A, float) * 255), 0, 255).astype(np.uint8).T)).save(path)


def load_mask(path, like=None, channel=None, threshold=None):
    """a painted image as a 0..1 array [i, j]; resized to like's grid (a Field or a shape). channel 0..3 picks R/G/B/A of a colour image."""
    with Image.open(path) as im:
        if channel is not None: im = im.convert('RGBA').getchannel(channel)
        elif im.mode not in ('L', 'I;16', 'I;16L', 'I;16B', 'I'): im = im.convert('L')
        full = 255.0 if im.mode == 'L' else 65535.0
        im = im.convert('F')
        shape = like.Z.shape if isinstance(like, Field) else like
        if shape is not None and im.size != tuple(shape): im = im.resize(tuple(shape), Image.Resampling.BILINEAR)
        A = np.asarray(im, float).T / full
    return (A >= threshold).astype(float) if threshold is not None else A


# ---------------------------------------------------------------- array helpers
def _nb(A, di, dj):
    """A[i + di, j + dj] with the edge repeated"""
    n, m = A.shape
    P = np.pad(A, 1, mode='edge')
    return P[1 + di:1 + di + n, 1 + dj:1 + dj + m]


def blur(A, r):
    """gaussian blur, sigma r cells (edge repeated)"""
    if r <= 0: return np.asarray(A, float).copy()
    k = max(1, int(math.ceil(2.5 * r)))
    w = np.exp(-0.5 * (np.arange(-k, k + 1) / float(r)) ** 2); w /= w.sum()
    A = np.asarray(A, float); n, m = A.shape
    P = np.pad(A, ((k, k), (0, 0)), mode='edge'); B = sum(w[t] * P[t:t + n] for t in range(2 * k + 1))
    P = np.pad(B, ((0, 0), (k, k)), mode='edge'); return sum(w[t] * P[:, t:t + m] for t in range(2 * k + 1))


def slope_deg(Z, cell):
    return np.degrees(np.arctan(np.hypot(np.gradient(Z, cell, axis=0), np.gradient(Z, cell, axis=1))))


def cavity(Z, cell, radius=96.0):
    """-1 (ridge / convex) .. +1 (hollow / concave) against the surroundings within radius"""
    d = blur(Z, radius / cell) - Z
    return np.clip(d / max(1e-6, 2.5 * d.std()), -1, 1)


def hillshade(Z, cell, azimuth=315.0, altitude=40.0, exaggerate=1.0, tint=True):
    """uint8 RGB picture [row, col], north (max y) up, sun from the north-west: for looking at a height field, not for the game"""
    gx = np.gradient(Z, cell, axis=0) * exaggerate; gy = np.gradient(Z, cell, axis=1) * exaggerate
    az = math.radians(azimuth); al = math.radians(altitude)
    lx, ly, lz = math.sin(az) * math.cos(al), math.cos(az) * math.cos(al), math.sin(al)       # azimuth clockwise from north (+y)
    sh = np.clip((-gx * lx - gy * ly + lz) / np.sqrt(gx * gx + gy * gy + 1), 0, 1)
    sh = 0.25 + 0.75 * sh
    if tint:
        t = (Z - Z.min()) / max(1e-6, Z.max() - Z.min())
        ramp = np.array([[92, 128, 96], [150, 168, 110], [190, 178, 130], [214, 204, 180]], float)
        u = t * (len(ramp) - 1); k = np.minimum(u.astype(int), len(ramp) - 2); f = (u - k)[..., None]
        rgb = ramp[k] * (1 - f) + ramp[k + 1] * f
    else:
        rgb = np.full(Z.shape + (3,), 215.0)
    img = np.clip(rgb * sh[..., None], 0, 255).astype(np.uint8)
    return np.ascontiguousarray(np.transpose(img, (1, 0, 2))[::-1])


def save_hillshade(path, Z, cell, outline=None, scale=1, **kw):
    """outline: a 0..1 array whose 0.5 contour is drawn in red (the protect mask). scale: integer upsample for small grids"""
    img = hillshade(Z, cell, **kw)
    if outline is not None:
        o = np.asarray(outline) >= 0.5
        edge = o & ~(_nb(o, 1, 0) & _nb(o, -1, 0) & _nb(o, 0, 1) & _nb(o, 0, -1))
        img[np.transpose(edge)[::-1]] = (220, 40, 40)
    im = Image.fromarray(img)
    if scale != 1: im = im.resize((im.width * scale, im.height * scale), Image.Resampling.BICUBIC)
    im.save(path)


# ---------------------------------------------------------------- cs2-map-mcp's terrain ops
def seg_dist(X, Y, pts):
    """distance to a polyline and the fraction 0..1 of its length at the nearest point"""
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    P = np.asarray(pts, float)[:, :2]
    seg = np.hypot(*(P[1:] - P[:-1]).T); cum = np.concatenate([[0], np.cumsum(seg)]); total = max(cum[-1], 1e-9)
    best = np.full(X.shape, np.inf); frac = np.zeros(X.shape)
    for k in range(len(P) - 1):
        ax, ay = P[k]; bx, by = P[k + 1]; L2 = max(seg[k] ** 2, 1e-12)
        t = np.clip(((X - ax) * (bx - ax) + (Y - ay) * (by - ay)) / L2, 0, 1)
        d = np.hypot(X - (ax + t * (bx - ax)), Y - (ay + t * (by - ay)))
        m = d < best
        best = np.where(m, d, best); frac = np.where(m, (cum[k] + t * seg[k]) / total, frac)
    return best, frac


def _poly_inside_dist(X, Y, poly):
    """(inside bool, distance to the outline)"""
    P = [tuple(p[:2]) for p in poly]
    inside = np.zeros(X.shape, bool)
    for (ax, ay), (bx, by) in zip(P, P[1:] + P[:1]):
        if ay == by: continue
        cross = ((ay > Y) != (by > Y)) & (X < (bx - ax) * (Y - ay) / (by - ay) + ax)
        inside ^= cross
    return inside, seg_dist(X, Y, P + P[:1])[0]


def apply_ops(F, ops):
    """the ops of cs2-map-mcp's add_terrain, in order, on a Field; returns a new Field.
      {'op': 'hill' | 'valley', 'center': [x, y], 'radius': r, 'height': h}
      {'op': 'ridge', 'path': [[x, y], ...], 'width': w, 'height': h}
      {'op': 'plateau', 'polygon': [[x, y], ...], 'z': z, 'falloff': f}
      {'op': 'noise', 'amplitude': a, 'scale': s, 'seed': n}
      {'op': 'flatten', 'path': [[x, y], ...], 'width': w, 'z': z | 'follow', 'falloff': f}      'follow' grades between the ends
      {'op': 'heightmap', 'image': png, 'height_range': [lo, hi], 'mode': 'set' | 'add'}
      {'op': 'level', 'mask': png | array, 'z': z | 'mean', 'falloff': f}     ours: flatten where a painted mask is white"""
    X, Y = F.XY; Z = F.Z.copy()
    for op in ops:
        kind = op['op']
        if kind in ('hill', 'valley'):
            d = np.hypot(X - op['center'][0], Y - op['center'][1])
            Z += abs(op['height']) * (-1 if kind == 'valley' else 1) * smoothstep(0, 1, 1 - d / op['radius'])
        elif kind == 'ridge':
            d, _ = seg_dist(X, Y, op['path'])
            Z += op['height'] * smoothstep(0, 1, 1 - d / (op['width'] / 2.0))
        elif kind == 'plateau':
            inside, d = _poly_inside_dist(X, Y, op['polygon'])
            w = np.where(inside, 1.0, 1 - smoothstep(0, max(op.get('falloff', 128.0), 1e-6), d))
            Z = Z * (1 - w) + op['z'] * w
        elif kind == 'noise':
            Z += op['amplitude'] * N.fbm(X / op['scale'], Y / op['scale'], 0.37, 4, seed=int(op.get('seed', 0)))
        elif kind == 'flatten':
            d, frac = seg_dist(X, Y, op['path'])
            if op.get('z', 'follow') == 'follow':
                ends = F.like(Z)(np.array([op['path'][0][0], op['path'][-1][0]]), np.array([op['path'][0][1], op['path'][-1][1]]))
                target = ends[0] + (ends[1] - ends[0]) * frac
            else: target = float(op['z'])
            w = 1 - smoothstep(op['width'] / 2.0, op['width'] / 2.0 + max(op.get('falloff', 96.0), 1e-6), d)
            Z = Z * (1 - w) + target * w
        elif kind == 'heightmap':
            H = Field.load(op['image'], bounds=F.bounds, cell=F.cell, height_range=op['height_range']).Z
            Z = Z + H if op.get('mode', 'set') == 'add' else H
        elif kind == 'level':
            M = load_mask(op['mask'], F) if isinstance(op['mask'], str) else np.asarray(op['mask'], float)
            hard = M >= 0.5
            if not hard.any(): continue
            z = float(Z[hard].mean()) if op.get('z', 'mean') == 'mean' else float(op['z'])
            w = feather(hard, op.get('falloff', 96.0) / F.cell)
            Z = Z * (1 - w) + z * w
        else:
            raise ValueError('unknown terrain op %r' % kind)
    return F.like(Z)


# ---------------------------------------------------------------- masks
def discs(X, Y, items):
    """bool: inside any (x, y, r)"""
    m = np.zeros(np.shape(X), bool)
    for x, y, r in items: m |= np.hypot(X - x, Y - y) <= r
    return m


def along(X, Y, items):
    """bool: within half_width of any (half_width, [(x, y), ...]) polyline"""
    m = np.zeros(np.shape(X), bool)
    for hw, pts in items: m |= seg_dist(X, Y, pts)[0] <= hw
    return m


def below(Z, level): return np.asarray(Z) <= level


def feather(mask, px, grow=2):
    """0..1 weights: 1 on the mask (grown by `grow` cells, so values interpolated between grid points stay inside it), falling smoothly
    to 0 over px cells outside. Chamfer distance, numpy only."""
    hard = np.asarray(mask) >= 0.5 if np.asarray(mask).dtype != bool else np.asarray(mask)
    for _ in range(int(grow)):
        hard = hard | _nb(hard, 1, 0) | _nb(hard, -1, 0) | _nb(hard, 0, 1) | _nb(hard, 0, -1) | _nb(hard, 1, 1) | _nb(hard, -1, -1) | _nb(hard, 1, -1) | _nb(hard, -1, 1)
    if px <= 0: return hard.astype(float)
    d = np.where(hard, 0.0, 1e9)
    for _ in range(int(math.ceil(px)) + 1):
        for di, dj, c in ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.4142), (-1, -1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142)):
            d = np.minimum(d, _nb(d, di, dj) + c)
    w = 1.0 - smoothstep(0.0, float(px), d)
    w[hard] = 1.0
    return w


# ---------------------------------------------------------------- water flow
_NB8 = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.41421356), (-1, -1, 1.41421356), (1, -1, 1.41421356), (-1, 1, 1.41421356))


def fill_pits(Z, eps=1e-4):
    """priority-flood: raises every closed hollow to its spill level (+ eps per step so the filled flats still drain to the edge)"""
    n, m = Z.shape
    out = Z.astype(float).tolist(); done = [[False] * m for _ in range(n)]
    heap = []
    for i in range(n):
        for j in ((0, m - 1) if 0 < i < n - 1 else range(m)):
            heap.append((out[i][j], i, j)); done[i][j] = True
    heapq.heapify(heap)
    push, pop = heapq.heappush, heapq.heappop
    while heap:
        z, i, j = pop(heap)
        for di, dj, _ in _NB8:
            a = i + di; b = j + dj
            if 0 <= a < n and 0 <= b < m and not done[a][b]:
                done[a][b] = True
                if out[a][b] <= z: out[a][b] = z + eps
                push(heap, (out[a][b], a, b))
    return np.array(out)


def flow(Z, cell=1.0, power=1.6, fill=True, rain=None):
    """upstream area per cell, in cells (1 = only its own rain). Multiple flow directions: each cell hands its water to its lower
    neighbours in proportion to slope ** power (higher = narrower streams)."""
    S = fill_pits(Z) if fill else np.asarray(Z, float)
    n, m = S.shape
    W = np.zeros((8, n, m))
    for k, (di, dj, dist) in enumerate(_NB8):
        drop = (S - _nb(S, di, dj)) / dist
        W[k] = np.maximum(drop, 0) ** power
        if di: W[k][-1 if di > 0 else 0, :] = 0                  # nothing flows off the grid: edge cells keep their water
        if dj: W[k][:, -1 if dj > 0 else 0] = 0
    tot = W.sum(0); W /= np.where(tot > 0, tot, 1)
    A = (np.ones(n * m) if rain is None else np.asarray(rain, float).ravel().copy()).tolist()
    order = np.argsort(-S, axis=None, kind='stable').tolist()
    offs = [di * m + dj for di, dj, _ in _NB8]
    Wl = [W[k].ravel().tolist() for k in range(8)]
    for c in order:
        a = A[c]
        for k in range(8):
            w = Wl[k][c]
            if w > 0.0: A[c + offs[k]] += a * w
    return np.array(A).reshape(n, m)


# ---------------------------------------------------------------- erosion and rock
def gullies(Z, cell, depth=24.0, area0=12.0, area1=900.0, width=1.0, slope0=2.0, slope1=10.0, power=0.8, acc=None):
    """cuts stream beds where water gathers: depth grows with log(upstream area) between area0 and area1 (cells), and only on ground
    steeper than slope0..slope1 degrees (flat ground silts up instead of cutting). Returns (Z, upstream area)."""
    A = flow(Z, cell) if acc is None else acc
    t = np.clip((np.log(A) - math.log(area0)) / (math.log(area1) - math.log(area0)), 0, 1) ** power
    s = smoothstep(slope0, slope1, slope_deg(blur(Z, 2.0), cell))
    carve = depth * t * s
    # a narrow bed inside a wider ravine whose sides lean back; big streams get the wide ravine, rills only the bed
    carve = np.maximum(np.maximum(blur(carve, width) * 1.2, 0.4 * carve), blur(carve * t, width * 3.0) * 2.2)
    return Z - carve, A


def hydraulic(Z, cell, drops=None, steps=56, seed=1, inertia=0.25, capacity=5.0, erosion=0.3, deposition=0.3, evaporation=0.025,
              gravity=6.0, min_slope=0.01, batch=None, radius=0.8, rain=None):
    """droplet erosion, a batch of drops per pass (all numpy). drops defaults to 2 per cell. rain: 0..1 weights where drops start
    (None = everywhere). Heights are worked in cells, so the result does not depend on the unit."""
    H = np.asarray(Z, float) / cell
    n, m = H.shape
    rng = np.random.RandomState(seed)
    drops = int(drops if drops is not None else 2 * n * m)
    batch = int(batch or max(256, n * m // 16))
    p = None
    if rain is not None:
        p = np.asarray(rain, float)[:n - 1, :m - 1].ravel(); p = p / p.sum()
    left = drops
    while left > 0:
        k = min(batch, left); left -= k
        if p is None:
            px = rng.uniform(0, n - 1.001, k); py = rng.uniform(0, m - 1.001, k)
        else:
            c = rng.choice(len(p), k, p=p)
            px = np.minimum(c // (m - 1) + rng.uniform(0, 1, k), n - 1.001); py = np.minimum(c % (m - 1) + rng.uniform(0, 1, k), m - 1.001)
        dx = np.zeros(k); dy = np.zeros(k); vel = np.ones(k); water = np.ones(k); sed = np.zeros(k); alive = np.ones(k, bool)
        for _ in range(steps):
            ix = px.astype(int); iy = py.astype(int); fx = px - ix; fy = py - iy
            h00 = H[ix, iy]; h10 = H[ix + 1, iy]; h01 = H[ix, iy + 1]; h11 = H[ix + 1, iy + 1]
            gx = (h10 - h00) * (1 - fy) + (h11 - h01) * fy; gy = (h01 - h00) * (1 - fx) + (h11 - h10) * fx
            h0 = (h00 * (1 - fx) + h10 * fx) * (1 - fy) + (h01 * (1 - fx) + h11 * fx) * fy
            dx = dx * inertia - gx * (1 - inertia); dy = dy * inertia - gy * (1 - inertia)
            l = np.hypot(dx, dy); still = l < 1e-9
            if still.any():
                a = rng.uniform(0, 2 * math.pi, k); dx = np.where(still, np.cos(a), dx); dy = np.where(still, np.sin(a), dy); l = np.where(still, 1.0, l)
            dx /= l; dy /= l
            nx = px + dx; ny = py + dy
            alive &= (nx >= 0) & (nx < n - 1.001) & (ny >= 0) & (ny < m - 1.001)
            if not alive.any(): break
            nx = np.clip(nx, 0, n - 1.001); ny = np.clip(ny, 0, m - 1.001)
            jx = nx.astype(int); jy = ny.astype(int); ux = nx - jx; uy = ny - jy
            h1 = (H[jx, jy] * (1 - ux) + H[jx + 1, jy] * ux) * (1 - uy) + (H[jx, jy + 1] * (1 - ux) + H[jx + 1, jy + 1] * ux) * uy
            dh = h1 - h0
            cap = np.maximum(-dh, min_slope) * vel * water * capacity
            dep = np.where(dh > 0, np.minimum(dh, sed), np.where(sed > cap, (sed - cap) * deposition, 0.0))
            ero = np.where((dh <= 0) & (sed <= cap), np.minimum((cap - sed) * erosion, -dh), 0.0)
            amount = np.where(alive, dep - ero, 0.0)
            sed = sed - amount
            D = np.zeros_like(H)
            np.add.at(D, (ix, iy), amount * (1 - fx) * (1 - fy)); np.add.at(D, (ix + 1, iy), amount * fx * (1 - fy))
            np.add.at(D, (ix, iy + 1), amount * (1 - fx) * fy); np.add.at(D, (ix + 1, iy + 1), amount * fx * fy)
            H += np.clip(blur(D, radius) if radius > 0 else D, -0.04, 0.04)       # many drops on one cell in one pass must not dig a shaft
            vel = np.minimum(np.sqrt(np.maximum(vel * vel - dh * gravity, 0.01)), 6.0); water *= 1 - evaporation
            px = np.where(alive, nx, px); py = np.where(alive, ny, py)
    return H * cell


def thermal(Z, cell, talus=38.0, iters=30, rate=0.5):
    """slopes steeper than talus degrees slump onto the cells below (scree): takes the knife edges off after cutting"""
    Z = np.asarray(Z, float).copy()
    lim = math.tan(math.radians(talus)) * cell
    for _ in range(int(iters)):
        D = np.zeros_like(Z)
        for di, dj, dist in _NB8:
            ex = np.maximum(Z - _nb(Z, di, dj) - lim * dist, 0) * (rate / 16.0)     # this cell's surplus over the neighbour (di, dj)
            n, m = Z.shape
            P = np.zeros((n + 2, m + 2)); P[1 + di:1 + di + n, 1 + dj:1 + dj + m] = ex     # hand it to that neighbour
            P[1] += P[0]; P[n] += P[n + 1]; P[:, 1] += P[:, 0]; P[:, m] += P[:, m + 1]     # what fell off the grid stays on the edge
            D += P[1:n + 1, 1:m + 1] - ex
        Z += D
    return Z


def terraces(Z, step=64.0, sharp=0.6, weight=None, offset=0.0):
    """steps the height into benches `step` high. sharp 0 = no change .. 1 = flat benches with steep risers. weight: 0..1 where to apply"""
    q = (np.asarray(Z, float) - offset) / step
    f = q - np.floor(q)
    e = 1.0 + 6.0 * sharp
    g = np.where(f < 0.5, 0.5 * (2 * f) ** e, 1 - 0.5 * (2 * (1 - f)) ** e)      # holds near the bench levels, rises fast between them
    T = (np.floor(q) + g) * step + offset
    return T if weight is None else Z + (T - Z) * np.clip(weight, 0, 1)


def outcrops(Z, cell, X, Y, height=28.0, slope0=16.0, slope1=30.0, scale=420.0, strata=18.0, seed=7, weight=None):
    """rock breaking through on steep ground: ridged-noise knobs with ledges (strata units high) where the slope passes slope0..slope1.
    Returns (Z, rock 0..1)."""
    sl = slope_deg(blur(Z, 1.5), cell)
    patch = smoothstep(0.42, 0.68, N.fbm(X / (scale * 2.2), Y / (scale * 2.2), 3.1, 3, seed=seed) * 0.5 + 0.5)       # not every slope has rock
    w = smoothstep(slope0, slope1, sl) * patch
    if weight is not None: w = w * np.clip(weight, 0, 1)
    r = N.ridged(X / scale, Y / scale, 1.7, 4, seed=seed + 1)
    knob = np.clip((r - 0.35) / 0.5, 0, 1) ** 1.3 * height
    if strata: knob = terraces(knob, strata, 0.75)
    rock = np.clip(w * np.clip(knob / max(height, 1e-6) * 2.0, 0, 1), 0, 1)
    return Z + knob * w, rock


RECIPE = {
    'gully_depth': 48.0, 'gully_area0': 20.0, 'gully_area1': 2500.0, 'gully_width': 1.0, 'gully_slope0': 2.0, 'gully_slope1': 9.0,
    'gully_passes': 6,             # each pass follows the beds the last one cut, so branches join into a network
    'gully_wander': 14.0, 'gully_wander_scale': 700.0,      # noise (units, wavelength) added for routing only: makes parallel rills on an even slope converge
    'drops': 1.0,                  # droplets per cell (0 = no droplet erosion)
    'drop_steps': 48, 'drop_capacity': 3.0, 'drop_erosion': 0.15, 'drop_deposition': 0.3, 'drop_radius': 0.8,
    'drop_steep': [9.0, 18.0], 'drop_steep_cut': 0.75,
    'drop_highpass': 8.0,          # cells: the droplets' broad lowering is taken out, only their fine relief is kept (0 = keep all)
    'thermal_talus': 40.0, 'thermal_iters': 20,
    'terrace_step': 0.0, 'terrace_sharp': 0.5, 'terrace_slope0': 6.0, 'terrace_slope1': 14.0,       # benches on slopes in that range
    'outcrop_height': 26.0, 'outcrop_slope0': 15.0, 'outcrop_slope1': 28.0, 'outcrop_scale': 420.0, 'outcrop_strata': 16.0,
    'max_cut': 60.0, 'max_fill': 40.0,       # the layer is soft-limited to -max_cut .. +max_fill
    'seed': 1,
}


def _soft(D, lim): return lim * np.tanh(D / lim) if lim > 0 else D * 0


def detail(F, protect=None, recipe=None, log=None):
    """The detail layer for a height Field: erode, then keep only the difference, limited, and exactly 0 where protect == 1.
    protect: 0..1 array (use feather() on your hard masks). Returns (D Field, info dict with 'acc', 'rock', 'eroded')."""
    r = dict(RECIPE, **(recipe or {}))
    say = log or (lambda *a: None)
    Z0 = F.Z; cell = F.cell; X, Y = F.XY
    free = None if protect is None else 1.0 - np.clip(protect, 0, 1)
    Z = Z0.copy(); A = None
    wander = r['gully_wander'] * N.fbm(X / r['gully_wander_scale'], Y / r['gully_wander_scale'], 5.3, 3, seed=r['seed'] + 2) if r['gully_wander'] else 0.0
    for k in range(int(r['gully_passes']) if r['gully_depth'] else 0):
        Zg, A = gullies(Z, cell, r['gully_depth'] / r['gully_passes'], r['gully_area0'], r['gully_area1'], r['gully_width'], r['gully_slope0'], r['gully_slope1'],
                        acc=flow(Z + wander, cell))
        Zg = np.minimum(fill_pits(Zg, 0.0), Z)          # a cut never leaves a new closed hollow: those silt up to their spill level
        Z = Zg if free is None else Z + (Zg - Z) * free
        say('gullies pass %d: deepest cut %.1f' % (k + 1, float((Z0 - Z).max())))
    if r['terrace_step']:
        w = smoothstep(r['terrace_slope0'], r['terrace_slope1'], slope_deg(blur(Z, 2.0), cell))
        Z = terraces(Z, r['terrace_step'], r['terrace_sharp'], w if free is None else w * free)
    if r['drops']:
        Zh = hydraulic(Z, cell, int(r['drops'] * Z.size), r['drop_steps'], r['seed'], capacity=r['drop_capacity'], erosion=r['drop_erosion'],
                       deposition=r['drop_deposition'], radius=r['drop_radius'])
        dh = Zh - Z
        if r['drop_highpass']: dh = dh - blur(dh, r['drop_highpass'])
        if r['drop_steep']:                             # on steep faces drops cut a dense hatch of rills: fade them out there
            dh = dh * (1.0 - r['drop_steep_cut'] * smoothstep(r['drop_steep'][0], r['drop_steep'][1], slope_deg(blur(Z0, 3.0), cell)))
        Zn = Z + dh if free is None else Z + dh * free
        # drops landing in one pass can dig pocks: hollows that were not there before silt up to their spill level
        Z = Zn + np.maximum((fill_pits(Zn, 0.0) - Zn) - (fill_pits(Z, 0.0) - Z), 0.0) * (1.0 if free is None else free)
        say('droplets: %d, change %.1f .. %.1f' % (int(r['drops'] * Z.size), float((Z - Z0).min()), float((Z - Z0).max())))
    rock = np.zeros_like(Z)
    if r['outcrop_height']:
        Z, rock = outcrops(Z, cell, X, Y, r['outcrop_height'], r['outcrop_slope0'], r['outcrop_slope1'], r['outcrop_scale'], r['outcrop_strata'],
                           seed=r['seed'] + 6, weight=free)
    if r['thermal_iters']:
        Zt = thermal(Z, cell, r['thermal_talus'], r['thermal_iters'])
        Z = Zt if free is None else Z + (Zt - Z) * free
    D = Z - Z0
    D = np.where(D < 0, _soft(D, r['max_cut']), _soft(D, r['max_fill']))
    if free is not None: D = D * free
    D[np.abs(D) < 1e-9] = 0.0
    say('detail layer: %.1f .. %.1f, rms %.2f' % (float(D.min()), float(D.max()), float(np.sqrt((D * D).mean()))))
    return F.like(D), {'acc': A, 'rock': rock if free is None else rock * free, 'eroded': F.like(Z0 + D)}


# ---------------------------------------------------------------- paint and foliage images
def splat(Z, cell, acc=None, rock=None, rock_slope=(30.0, 46.0), wet_area=(10.0, 400.0), water_z=None, wet_height=48.0, seed=3, XY=None):
    """0..1 images from the shape of the ground:
      rock         steep faces and outcrops                      mud     where water gathers (stream beds, hollows, just above water_z)
      grass        the rest                                      cavity  0.5 = level, 1 = hollow, 0 = ridge (multiply a tint by it)
      trees        canopy density: gentle to middling slopes, off the rock and out of the beds, thicker beside streams
      undergrowth  ferns / grass tufts: damp, not rock, thinning under water lines"""
    sl = slope_deg(Z, cell)
    A = flow(Z, cell) if acc is None else acc
    wet = np.clip((np.log(A) - math.log(wet_area[0])) / (math.log(wet_area[1]) - math.log(wet_area[0])), 0, 1)
    wet = wet * smoothstep(0.4, 2.0, slope_deg(blur(Z, 2.0), cell))      # on dead level ground the routing is arbitrary: no beds there
    bed = blur(wet, 0.7)
    cav = cavity(Z, cell)
    rk = smoothstep(rock_slope[0], rock_slope[1], sl)
    if rock is not None: rk = np.maximum(rk, np.clip(rock, 0, 1))
    damp = np.clip(blur(wet, 3.0) * 1.6 + 0.35 * np.clip(cav, 0, 1), 0, 1)
    if water_z is not None: damp = np.maximum(damp, 1 - smoothstep(0, wet_height, Z - water_z))
    mud = np.clip(np.maximum(bed, 0.6 * damp) * (1 - rk), 0, 1)
    grass = np.clip(1 - np.maximum(rk, mud), 0, 1)
    if XY is not None: nz = N.fbm(XY[0] / 300.0, XY[1] / 300.0, 0.9, 3, seed=seed) * 0.5 + 0.5
    else: nz = np.full(Z.shape, 0.5)
    trees = (1 - smoothstep(34.0, 48.0, sl)) * (1 - rk) * (1 - smoothstep(0.35, 0.8, bed)) * (0.55 + 0.45 * np.clip(blur(wet, 4.0) * 2.0, 0, 1) + 0.3 * (nz - 0.5))
    if water_z is not None: trees = trees * smoothstep(4.0, 24.0, Z - water_z)
    under = (0.35 + 0.65 * damp) * (1 - rk) * (1 - 0.7 * smoothstep(0.5, 0.9, bed)) * (0.8 + 0.4 * (nz - 0.5))
    if water_z is not None: under = under * smoothstep(-4.0, 10.0, Z - water_z)
    return {'rock': rk, 'mud': mud, 'grass': grass, 'trees': np.clip(trees, 0, 1), 'undergrowth': np.clip(under, 0, 1), 'cavity': 0.5 + 0.5 * cav,
            'slope': sl, 'acc': A}


def scatter_density(density, spacing=128.0, seed=1, jitter=0.9, limit=None):
    """Points by a density Field (0 = none, 1 = one per spacing x spacing): a jittered grid, each point kept with the density under it,
    so the same seed gives the same points. Returns [(x, y)]."""
    x0, y0, x1, y1 = density.bounds
    rng = np.random.RandomState(seed)
    gx = np.arange(x0 + spacing / 2, x1, spacing); gy = np.arange(y0 + spacing / 2, y1, spacing)
    GX, GY = np.meshgrid(gx, gy, indexing='ij')
    GX = GX + rng.uniform(-0.5, 0.5, GX.shape) * spacing * jitter; GY = GY + rng.uniform(-0.5, 0.5, GY.shape) * spacing * jitter
    keep = rng.uniform(0, 1, GX.shape) < density(GX, GY)
    pts = list(zip(GX[keep].tolist(), GY[keep].tolist()))
    if limit is not None and len(pts) > limit:
        pts = [pts[i] for i in sorted(rng.choice(len(pts), int(limit), replace=False).tolist())]
    return pts


# ---------------------------------------------------------------- command line
def run_detail(height_png, out_dir, protect_png=None, feather_px=6.0, recipe=None, water_z=None, scale=1, log=print):
    """the whole pass on files; returns the report dict (also written as report.json)"""
    F = Field.load(height_png)
    P = None; hard = None
    if protect_png:
        hard = load_mask(protect_png, F) >= 0.5
        P = feather(hard, feather_px)
    D, info = detail(F, P, recipe, log)
    E = info['eroded']
    os.makedirs(out_dir, exist_ok=True)
    amp = max(float(np.abs(D.Z).max()), 1.0)
    D.save(os.path.join(out_dir, 'detail.png'), -amp, amp)
    E.save(os.path.join(out_dir, 'eroded.png'))
    save_hillshade(os.path.join(out_dir, 'hillshade_before.png'), F.Z, F.cell, scale=scale)
    save_hillshade(os.path.join(out_dir, 'hillshade_after.png'), E.Z, F.cell, scale=scale)
    save_hillshade(os.path.join(out_dir, 'hillshade_after_masks.png'), E.Z, F.cell, outline=hard, scale=scale)
    S = splat(E.Z, F.cell, rock=info['rock'], water_z=water_z, XY=F.XY)
    for k in ('rock', 'mud', 'grass', 'cavity'): save8(os.path.join(out_dir, 'splat_%s.png' % k), S[k])
    for k in ('trees', 'undergrowth'): save8(os.path.join(out_dir, 'density_%s.png' % k), S[k])
    back = Field.load(os.path.join(out_dir, 'detail.png'))
    s0 = slope_deg(F.Z, F.cell); s1 = slope_deg(E.Z, F.cell)
    rep = {'grid': list(F.Z.shape), 'cell': F.cell, 'detail_min': float(D.Z.min()), 'detail_max': float(D.Z.max()),
           'detail_rms': float(np.sqrt((D.Z ** 2).mean())),
           'protected_cells': int(hard.sum()) if hard is not None else 0,
           'max_change_in_protected': float(np.abs(D.Z[hard]).max()) if hard is not None and hard.any() else 0.0,
           'max_change_in_protected_after_png': float(np.abs(back.Z[hard]).max()) if hard is not None and hard.any() else 0.0,
           'png_roundtrip_error': float(np.abs(back.Z - D.Z).max()),
           'steep_over_45_before': float((s0 > 45).mean()), 'steep_over_45_after': float((s1 > 45).mean())}
    with open(os.path.join(out_dir, 'report.json'), 'w') as f: json.dump(rep, f, indent=1)
    log(json.dumps(rep))
    return rep


def _load_fn(spec):
    path, _, name = spec.rpartition(':')
    d = os.path.dirname(os.path.abspath(path))
    if d not in sys.path: sys.path.insert(1, d)
    sp = importlib.util.spec_from_file_location(os.path.splitext(os.path.basename(path))[0], path)
    mod = importlib.util.module_from_spec(sp); sp.loader.exec_module(mod)
    return getattr(mod, name)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    e = sub.add_parser('export'); e.add_argument('fn'); e.add_argument('--bounds', required=True); e.add_argument('--cell', type=float, default=32.0); e.add_argument('--out', required=True)
    d = sub.add_parser('detail'); d.add_argument('height'); d.add_argument('--out', required=True); d.add_argument('--protect'); d.add_argument('--feather', type=float, default=6.0)
    d.add_argument('--recipe'); d.add_argument('--seed', type=int); d.add_argument('--water-z', type=float); d.add_argument('--scale', type=int, default=1)
    s = sub.add_parser('shade'); s.add_argument('height'); s.add_argument('out'); s.add_argument('--scale', type=int, default=1)
    a = ap.parse_args(argv)
    if a.cmd == 'export':
        F = Field.from_fn(_load_fn(a.fn), [float(v) for v in a.bounds.split(',')], a.cell)
        print(json.dumps(F.save(a.out)))
    elif a.cmd == 'detail':
        recipe = {}
        if a.recipe:
            with open(a.recipe) as f: recipe = json.load(f)
        if a.seed is not None: recipe['seed'] = a.seed
        run_detail(a.height, a.out, a.protect, a.feather, recipe, a.water_z, a.scale)
    else:
        F = Field.load(a.height); save_hillshade(a.out, F.Z, F.cell, scale=a.scale)


if __name__ == '__main__':
    main()
