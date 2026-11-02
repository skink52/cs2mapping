"""mg_trenchwarfare layout: one source of truth for the map generator, the radar/targeting renders and the script.

World: x runs between the lines (T / German side west, x < 0; CT / British side east, x > 0), y along the front.
Everything is generated for the CT side and mirrored (x -> -x) for T.
"""
import numpy as np
from scipy import ndimage
from noise import fbm, perlin, hash01

SIDES = {'ct': 1, 't': -1}
MAP_X, MAP_Y = 7168, 6144          # terrain half extents
SKY_Z0, SKY_Z1 = -700, 6400

# ---------------------------------------------------------------- trench plan (CT side, x > 0)
XF, XB = 1641.0, 1791.0            # fire-trench bay / traverse-passage centre lines
XS = 2150.0                        # support trench
HW = 36.0                          # half width (72 wide floor)
STEP_D = 30.0                      # fire-step depth (in front of the bay floor)
P = 384.0; NBAY = 15; Y0 = -NBAY * P / 2.0
DEPTH = 72.0                       # floor below local ground
COMM_Y = [-1920.0, 0.0, 1920.0]    # communication trenches
SHELTER_Y = [-1056.0, 576.0, 2304.0]  # heal shelters off the support trench
MORTAR_X = 3200.0
MORTAR_Y = [-1600.0, -800.0, 0.0, 800.0, 1600.0]
HANGAR_X = 6150.0
RES = 16.0                         # trench raster cell
RX0, RX1 = 1300.0, 2600.0          # raster extent (x), CT side
RY0, RY1 = -3200.0, 3200.0


def fire_centreline():
    pts = []
    for i in range(NBAY):
        ya = Y0 + i * P
        pts += [(XF, ya), (XF, ya + 256), (XB, ya + 256), (XB, ya + P)]
    pts.append((XF, Y0 + NBAY * P))
    # collapse: consecutive (XB, ya+P) -> (XF, ya+P) jog handled as a segment
    return pts


def segments():
    """axis-aligned centre-line segments with a kind tag"""
    segs = []
    pts = fire_centreline()
    for a, b in zip(pts[:-1], pts[1:]):
        segs.append((a, b, 'fire'))
    yA, yB = Y0 + 96, Y0 + NBAY * P - 96
    # support trench with a small dog-leg every 768
    ys = np.arange(yA, yB + 1, 768.0)
    sp = []
    for k, y in enumerate(ys):
        x = XS + (48 if k % 2 else 0)
        sp.append((x, y))
        if k + 1 < len(ys):
            sp.append((x, y + 640)); sp.append((XS + (0 if k % 2 else 48), y + 640))
    for a, b in zip(sp[:-1], sp[1:]):
        if a != b: segs.append((a, b, 'support'))
    # communication trenches from the traverse passage back to the support trench, one zig-zag each
    for y in COMM_Y:
        y0 = y + 64
        xs = [XB, 1930, 1930, XS]
        yy = [y0, y0, y0 + 96, y0 + 96]
        for k in range(3):
            segs.append(((xs[k], yy[k]), (xs[k + 1], yy[k + 1]), 'comm'))
    # shelter niches
    for y in SHELTER_Y:
        segs.append(((XS, y), (XS + 150, y), "niche"))
    return segs


def support_x_at(y):
    """support trench centre x at y"""
    best = None
    for (a, b, kind) in segments():
        if kind != 'support': continue
        if a[0] == b[0] and min(a[1], b[1]) - HW <= y <= max(a[1], b[1]) + HW:
            best = a[0]
    return best if best is not None else XS


def rects():
    """union of rectangles (x0, y0, x1, y1, kind) that make up the dug trench (CT side)"""
    out = []
    for (a, b, kind) in segments():
        w = HW if kind != 'niche' else 56
        x0, x1 = min(a[0], b[0]) - (HW if kind == 'niche' else w), max(a[0], b[0]) + w
        y0, y1 = min(a[1], b[1]) - w, max(a[1], b[1]) + w
        if kind == 'niche': x0 = min(a[0], b[0]); x1 = max(a[0], b[0]) + 8
        out.append((x0, y0, x1, y1, kind))
    # fire-steps: in front of every bay
    for i in range(NBAY):
        ya = Y0 + i * P
        out.append((XF - HW - STEP_D, ya - HW + 4, XF - HW, ya + 256 + HW - 4, 'step'))
    return out


def firesteps():
    """(x_wall, y0, y1) front-wall runs where fire-step props go"""
    return [(XF - HW - STEP_D, Y0 + i * P - HW + 4, Y0 + i * P + 256 + HW - 4) for i in range(NBAY)]


class Raster:
    def __init__(self):
        self.nx = int((RX1 - RX0) / RES); self.ny = int((RY1 - RY0) / RES)
        m = np.zeros((self.nx, self.ny), bool)
        for (x0, y0, x1, y1, kind) in rects():
            i0 = int(round((x0 - RX0) / RES)); i1 = int(round((x1 - RX0) / RES))
            j0 = int(round((y0 - RY0) / RES)); j1 = int(round((y1 - RY0) / RES))
            m[max(i0, 0):i1, max(j0, 0):j1] = True
        self.mask = m
        dout, ind = ndimage.distance_transform_edt(~m, return_indices=True)
        din = ndimage.distance_transform_edt(m)
        self.sd = (dout - din) * RES            # signed distance (units) at cell centres, <0 inside
        self.near_x = RX0 + (ind[0] + 0.5) * RES  # nearest trench cell centre x

    def sample(self, x, y):
        """signed distance and nearest trench x for CT-side coordinates (bilinear on the cell grid)"""
        fx = (np.asarray(x) - RX0) / RES - 0.5; fy = (np.asarray(y) - RY0) / RES - 0.5
        inside = (fx > -1) & (fx < self.nx) & (fy > -1) & (fy < self.ny)
        c = np.stack([np.clip(fx, 0, self.nx - 1), np.clip(fy, 0, self.ny - 1)])
        d = ndimage.map_coordinates(self.sd, c, order=1, mode='nearest')
        nx = ndimage.map_coordinates(self.near_x, c, order=0, mode='nearest')
        far = np.minimum(np.abs(np.asarray(x) - XS) - 600, 0) * 0 + 4000
        return np.where(inside, d, 4000.0), nx

    def walls(self):
        """boundary runs between trench and earth: list of (p0, p1, inward_normal) in CT coordinates"""
        m = self.mask
        out = []
        # vertical boundaries (walls running along y): between cell (i-1, j) and (i, j)
        for i in range(1, self.nx):
            diff = m[i - 1] != m[i]
            j = 0
            while j < self.ny:
                if diff[j]:
                    k = j
                    while k < self.ny and diff[k] and m[i - 1, k] == m[i - 1, j]: k += 1
                    x = RX0 + i * RES
                    n = (1, 0) if m[i, j] else (-1, 0)
                    out.append(((x, RY0 + j * RES), (x, RY0 + k * RES), n))
                    j = k
                else:
                    j += 1
        for j in range(1, self.ny):
            diff = m[:, j - 1] != m[:, j]
            i = 0
            while i < self.nx:
                if diff[i]:
                    k = i
                    while k < self.nx and diff[k] and m[k, j - 1] == m[i, j - 1]: k += 1
                    y = RY0 + j * RES
                    n = (0, 1) if m[i, j] else (0, -1)
                    out.append(((RX0 + i * RES, y), (RX0 + k * RES, y), n))
                    i = k
                else:
                    i += 1
        return out


# ---------------------------------------------------------------- craters
def craters(seed=7):
    rng = np.random.RandomState(seed)
    out = []
    def add(n, xr, yr, rr, dep):
        for _ in range(n):
            out.append((rng.uniform(*xr), rng.uniform(*yr), rng.uniform(*rr), rng.uniform(*dep)))
    add(170, (-1480, 1480), (-3600, 3600), (70, 190), (0.35, 0.55))     # big, overlapping: no man's land
    add(420, (-1500, 1500), (-3700, 3700), (24, 70), (0.3, 0.5))
    for s in (-1, 1):
        add(40, sorted((s * 2350, s * 3900)), (-3300, 3300), (40, 150), (0.25, 0.45))   # behind the lines
        add(30, sorted((s * 3900, s * 5200)), (-4200, 4200), (40, 120), (0.2, 0.35))
    add(60, (-1500, 1500), (-5800, 5800), (40, 140), (0.25, 0.4))       # flanks of no man's land
    return np.array(out)


CRATERS = craters()
_R = None
def raster():
    global _R
    if _R is None: _R = Raster()
    return _R


def ground_low(x, y):
    return 22 * fbm(x / 2600.0, y / 2600.0, 0.5, 3, seed=11) + 6 * fbm(x / 900.0, y / 900.0, 1.5, 2, seed=12)


def trench_dist(x, y):
    """signed distance to the nearest trench (either side) and whether that point is on the front side"""
    R = raster()
    x = np.asarray(x, float); y = np.asarray(y, float)
    side = np.sign(x); side[side == 0] = 1
    d, nx = R.sample(np.abs(x), y)
    front = (np.abs(x) < nx)       # earth between the wall and no man's land
    return d, front


def bank(d, front):
    """parapet (front) / parados (rear) height above local ground at distance d (>0) from the wall"""
    top = np.where(front, 8.0, 20.0)
    t = np.clip((d - 2.0) / 110.0, 0, 1)
    return top * (1 - t) ** 1.6 - 2.5 * t


def crater_field(x, y, near_trench):
    h = np.zeros_like(x)
    for (cx, cy, r, dep) in CRATERS:
        ext = r * 1.9
        sel = (np.abs(x - cx) < ext) & (np.abs(y - cy) < ext)
        if not sel.any(): continue
        rho = np.sqrt((x[sel] - cx) ** 2 + (y[sel] - cy) ** 2) / r
        dd = dep * r
        inner = -dd * np.clip(1 - rho ** 2, 0, None) ** 1.3 + 0.12 * dd * rho ** 3
        outer = 0.12 * dd * np.exp(-(rho - 1) * 3.0)
        v = np.where(rho < 1, inner, outer)
        v *= 1 + 0.25 * perlin(x[sel] / (r * 0.6), y[sel] / (r * 0.6), cx * 0.01)
        h[sel] += v
    return h * (1 - near_trench)


def height(x, y):
    """main terrain height (the trench pit floor where carved; under the parapet layer next to trenches)"""
    x = np.asarray(x, float); y = np.asarray(y, float)
    g0 = ground_low(x, y)
    d, front = trench_dist(x, y)
    near = np.clip(1 - (np.minimum(np.abs(d), 4000) - 120) / 260.0, 0, 1)
    nml = np.clip(1 - (np.abs(x) - 1350) / 250.0, 0, 1)
    churn = 7 * fbm(x / 160.0, y / 160.0, 2.5, 4, seed=13) * nml + 3 * fbm(x / 60.0, y / 60.0, 3.5, 2, seed=14)
    g = g0 + churn * (1 - near) + crater_field(x, y, near)
    # mortar pits
    for s in (-1, 1):
        for my in MORTAR_Y:
            r = np.sqrt((x - s * MORTAR_X) ** 2 + (y - my) ** 2)
            g = g - 22 * np.clip(1 - (r / 198.0) ** 16, 0, 1)
    carved = d < 48
    under = (d >= 48) & (d < 116)
    z = np.where(carved, g0 - DEPTH, np.where(under, g0 + bank(np.maximum(d, 0), front) - 4, g))
    return z


def parapet(x, y):
    """parapet/parados layer height (valid where 2 <= d <= 116)"""
    g0 = ground_low(x, y)
    d, front = trench_dist(x, y)
    return g0 + bank(np.maximum(d, 0), front) + 1.5 * fbm(x / 40.0, y / 40.0, 4.5, 2, seed=15), d


# ---------------------------------------------------------------- points of interest
def floor_z(x, y):
    return float(ground_low(np.array([x]), np.array([y]))[0] - DEPTH)


def ground_at(x, y):
    return float(height(np.array([float(x)]), np.array([float(y)]))[0])


def infantry_spawns(s):
    """20 per side: one in each bay (on the floor, facing the enemy) + 5 in the support trench"""
    out = []
    for i in range(NBAY):
        y = Y0 + i * P + 128
        out.append((s * (XF + 8), y))
    for y in (-2600, -1300, 300, 1300, 2600):
        out.append((s * support_x_at(y), y))
    return out


def heal_points(s):
    return [(s * (XS + 64), y) for y in SHELTER_Y]


def mortar_pits(s):
    return [(s * MORTAR_X, y) for y in MORTAR_Y]


def mortar_stations(s, k):
    """mortar tube (centre), plotting table, ammo box for pit k (0-based); rear = away from the enemy"""
    cx, cy = s * MORTAR_X, MORTAR_Y[k]
    rear = s
    return dict(mortar=(cx, cy), table=(cx + rear * 85, cy + 55), ammo=(cx + rear * 60, cy - 75))


def plane_spawns(s):
    return [(s * (HANGAR_X - 640 + (60 if k % 2 else 0)), y) for k, y in enumerate((-720, -360, 0, 360, 720))]


# ---------------------------------------------------------------- mine tunnels at the south end (both sides meet under no man's land)
TUN_CELL = 16.0
TUN_FLOOR = -260.0
TUN_PORTAL_Y = -2816.0; TUN_SAP_Y = -3232.0; TUN_SAP_X = (2096.0, 2192.0); TUN_SAP_XC = 2144.0
TUN_LANDING = (2032.0, -3360.0, 2208.0, -3232.0)


def tunnels():
    """(x0, y0, x1, y1, kind) world rects on a 16-unit grid, both sides; kinds: sap, landing, gallery, cross, post, chamber.
    The sap leaves the south end of the support trench (XS)."""
    ct = [(2096, -3232, 2192, -2816, 'sap'), (2032, -3360, 2208, -3232, 'landing'),
          (176, -3312, 2032, -3232, 'gallery'), (1952, -3488, 2032, -3312, 'cross'), (176, -3488, 1952, -3408, 'gallery'),
          (736, -3408, 816, -3312, 'cross'), (1376, -3408, 1456, -3312, 'cross'), (992, -3232, 1056, -3168, 'post'), (432, -3536, 496, -3488, 'post'),
          (1648, -3232, 1712, -3168, 'post')]
    out = []
    for (x0, y0, x1, y1, k) in ct:
        out.append((float(x0), float(y0), float(x1), float(y1), k)); out.append((float(-x1), float(y0), float(-x0), float(y1), k))
    out.append((-176.0, -3536.0, 176.0, -3200.0, 'chamber'))
    return out
