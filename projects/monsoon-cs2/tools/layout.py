"""mg_monsoon layout: the one source of truth for the valley. Shared by make_map.py (terrain, water, props, entities), make_radar.py,
render_board.py (the artillery board picture), make_skybox.py (MAP_X/MAP_Y/ground_low) and the script config (export_json()).

Units: Source units, Z up. CT (US) firebase south-east, T (PAVN) camp north-west. The river runs west -> east.
All height functions take numpy arrays (or floats) and are vectorised.
"""
import json, math
import numpy as np
from noise import fbm, smoothstep

# ---------------------------------------------------------------- extents
MAP_X, MAP_Y = 6400, 5120            # play space half extents
TERRAIN_X, TERRAIN_Y = 7168, 6144    # terrain mesh half extents (multiples of 512)
SKY_X, SKY_Y = 7424, 6400            # sky shell half extents
SKY_Z0, SKY_Z1 = -900, 5600
AIR_X, AIR_Y, AIR_Z = 7000, 5700, 4200   # helicopter soft box (hard wall +600)
LOBBY_Z = -3400                      # briefing room below the map
PARK_Z = -4200                       # parked effect props (tracers, rockets, markers)

# ---------------------------------------------------------------- water
WATER_Z = -30.0          # river and marsh water level
RIVER_HW = 150.0         # water half width
BANK_W = 260.0           # distance from the centre line where the bank meets the floodplain
BED_Z = -62.0
FALL_X = -5600.0         # the waterfall: the river upstream (x < FALL_X) is 110 higher
FALL_H = 110.0
UPPER_WATER_Z = WATER_Z + FALL_H
MARSH_X0 = 5000.0        # east of this the floodplain dips into marsh pools

# ---------------------------------------------------------------- places (x, y) / (x, y, z)
CT_BASE = (3900.0, -2900.0)       # firebase hill centre
CT_PLATEAU_R, CT_FOOT_R, CT_Z = 760.0, 1750.0, 620.0
T_BASE = (-3900.0, 2900.0)        # camp saddle centre
T_PLATEAU_R, T_FOOT_R, T_Z = 700.0, 1500.0, 300.0
TEMPLE = (2600.0, 900.0); TEMPLE_R, TEMPLE_FOOT, TEMPLE_H = 420.0, 820.0, 160.0
VILLAGE = (-300.0, 2400.0); VILLAGE_R, VILLAGE_FOOT, VILLAGE_Z = 650.0, 1000.0, 120.0
CRASH = (300.0, -2400.0); CRASH_R, CRASH_FOOT, CRASH_Z = 600.0, 950.0, 110.0
# karst towers: (x, y, base radius, height above the ground, seed). Separate meshes; the terrain gets a talus skirt.
KARST = [(-5000.0, 3700.0, 420.0, 1500.0, 1), (-4300.0, 4500.0, 360.0, 1250.0, 2), (-3000.0, 4350.0, 300.0, 1000.0, 3),
         (1400.0, 3900.0, 380.0, 1300.0, 4), (4900.0, 3200.0, 320.0, 1100.0, 5), (-1500.0, -4100.0, 340.0, 1200.0, 6),
         (-5300.0, -2200.0, 300.0, 900.0, 7), (5700.0, -1300.0, 250.0, 800.0, 8)]
# karst tops you can land on (the three biggest get a flat crown; others are jagged)
KARST_LANDABLE = (1, 4, 6)

# paddies: terraced cells on the south bank west of the bridge, in river-relative coordinates (x, yr = y - river_y(x))
PADDY_X0, PADDY_X1 = -3500.0, -1800.0
PADDY_YR0, PADDY_YR1 = -1470.0, -560.0       # yr range (negative = south of the river)
PADDY_CELL_X, PADDY_CELL_Y = 425.0, 303.3    # 4 x 3 cells
PADDY_DIKE_HW = 18.0                         # dike half width
PADDY_DIKE_H = 22.0                          # dike top above the cell floor
PADDY_WATER_D = 5.0                          # water depth in a cell
# a second, smaller group on the north bank near the village (looks only; no flag)
PADDY2_X0, PADDY2_X1 = -1500.0, -650.0
PADDY2_YR0, PADDY2_YR1 = 420.0, 1026.0
PADDY2_CELL_X, PADDY2_CELL_Y = 425.0, 303.0


def river_y(x):
    """centre line of the river (y for a given x)"""
    x = np.asarray(x, float)
    return 380.0 * np.sin(x / 2000.0 + 0.3) + 140.0 * np.sin(x / 700.0 + 1.7)


def river_dir(x):
    """unit tangent of the centre line"""
    x = np.asarray(x, float)
    dy = 380.0 / 2000.0 * np.cos(x / 2000.0 + 0.3) + 140.0 / 700.0 * np.cos(x / 700.0 + 1.7)
    l = np.sqrt(1 + dy * dy)
    return 1.0 / l, dy / l


# flags (conquest points): letter, name, (x, y). A and B sit where the river geometry puts them.
def _flags():
    ya = float(river_y(-2600.0)) - 960.0
    yb = float(river_y(0.0))
    return [('a', 'Paddies', (-2600.0, ya)), ('b', 'Bridge', (0.0, yb)), ('c', 'Village', VILLAGE),
            ('d', 'Temple', TEMPLE), ('e', 'Crash Site', CRASH)]


FLAGS = _flags()
FLAG_R = 350.0           # capture radius
BRIDGE_X = 0.0
BRIDGE_Y = float(river_y(0.0))
BRIDGE_LEN = 2 * BANK_W + 120     # deck from bank to bank (+ abutments)

# roads: (half width, [(x, y), ...]); trails are narrower
ROADS = [
    (60.0, [(3240.0, -2400.0), (2700.0, -2650.0), (2600.0, -2150.0), (2200.0, -2300.0), (1300.0, -2420.0), (300.0, -2400.0),
            (-100.0, -1600.0), (0.0, BRIDGE_Y - 420.0)]),
    (60.0, [(0.0, BRIDGE_Y + 420.0), (-150.0, 1200.0), (-300.0, 2400.0), (-1500.0, 2700.0), (-2700.0, 2750.0), (-3900.0, 2900.0)]),
    (45.0, [(-200.0, 1400.0), (600.0, 1150.0), (1500.0, 950.0), (2150.0, 870.0)]),            # spur to the temple foot
    (35.0, [(-2600.0, float(river_y(-2600.0)) - 960.0), (-1200.0, -1950.0), (300.0, -2400.0)]),   # trail A - E
    (35.0, [(-2600.0, float(river_y(-2600.0)) - 960.0), (-1300.0, -800.0), (-200.0, BRIDGE_Y - 420.0)]),   # trail A - bridge
    (35.0, [(-300.0, 2400.0), (1200.0, 1900.0), (2250.0, 1150.0)]),                            # trail village - temple
    (35.0, [(-3900.0, 2900.0), (-3300.0, 1900.0), (-2800.0, 700.0), (-2600.0, float(river_y(-2600.0)) + 420.0)]),   # camp - river north bank
]

# bomb craters on the approaches: (x, y, radius, depth)
_cr = np.random.RandomState(1968)
CRATERS = []
for (cx, cy, n, spread) in ((1400.0, -2000.0, 7, 900.0), (900.0, 1500.0, 6, 800.0), (3100.0, -1800.0, 6, 700.0), (-1200.0, 1500.0, 5, 700.0),
                            (-2200.0, 2400.0, 5, 600.0), (2200.0, -300.0, 4, 600.0), (-3800.0, -2600.0, 4, 700.0)):
    for _ in range(n):
        CRATERS.append((cx + _cr.uniform(-spread, spread), cy + _cr.uniform(-spread * 0.7, spread * 0.7), _cr.uniform(80, 150), _cr.uniform(18, 30)))


# tributary gullies (dry-season creek beds, monsoon mud): (half width, depth, [(x, y)...]) carved into the ground, mud paint
GULLIES = [(42.0, 22.0, [(3400.0, -2050.0), (2900.0, -1500.0), (2500.0, -900.0), (2100.0, float(river_y(2100.0)) - 300.0)]),
           (38.0, 20.0, [(-4200.0, 2100.0), (-3700.0, 1500.0), (-3300.0, 900.0), (-3100.0, float(river_y(-3100.0)) + 300.0)]),
           (30.0, 16.0, [(1900.0, 3300.0), (1500.0, 2500.0), (1100.0, 1700.0), (900.0, float(river_y(900.0)) + 300.0)]),
           (30.0, 16.0, [(-1200.0, -3600.0), (-900.0, -2900.0), (-1500.0, -2300.0), (-1700.0, float(river_y(-1700.0)) - 300.0)])]
# an oxbow lake (old meander) on the south floodplain between A and E: crescent of points, water at WATER_Z
OXBOW = [(-1700.0, -1250.0), (-1450.0, -1420.0), (-1150.0, -1480.0), (-850.0, -1400.0), (-650.0, -1200.0)]
OXBOW_HW, OXBOW_DEPTH = 110.0, 60.0


# ---------------------------------------------------------------- helpers
def _dist(x, y, p):
    return np.hypot(np.asarray(x, float) - p[0], np.asarray(y, float) - p[1])


def seg_dist(x, y, pts):
    """distance from points to a polyline and the parameter (0..1 along the whole line) of the nearest point"""
    x = np.asarray(x, float); y = np.asarray(y, float)
    P = np.asarray(pts, float)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); cum = np.concatenate([[0], np.cumsum(seg)]); L = cum[-1]
    best = np.full(x.shape, 1e9); tbest = np.zeros(x.shape)
    for i in range(len(P) - 1):
        a, b = P[i], P[i + 1]; d = b - a; l2 = max(float(d @ d), 1e-9)
        t = np.clip(((x - a[0]) * d[0] + (y - a[1]) * d[1]) / l2, 0, 1)
        dist = np.hypot(x - (a[0] + t * d[0]), y - (a[1] + t * d[1]))
        m = dist < best
        best = np.where(m, dist, best); tbest = np.where(m, (cum[i] + t * seg[i]) / max(L, 1e-9), tbest)
    return best, tbest


def plateau(x, y, centre, r_flat, r_foot, z, base, warp=0.12, seed=0):
    """lerp the terrain to a flat plateau of height z inside r_flat, falling to the base by r_foot; the rim is warped by noise"""
    d = _dist(x, y, centre)
    ang = np.arctan2(np.asarray(y, float) - centre[1], np.asarray(x, float) - centre[0])
    w = 1.0 + warp * fbm(np.cos(ang) * 2.1, np.sin(ang) * 2.1, seed * 0.37, 3, seed=seed + 40)
    s = 1.0 - smoothstep(r_flat * w, r_foot * w, d)
    s = s * s * (3 - 2 * s)   # ease, so the foot and the rim blend smoothly
    return base + (z - base) * s


# ---------------------------------------------------------------- the ground
def base_terrain(x, y):
    """valley profile + hills + noise, before the river carve and the features"""
    x = np.asarray(x, float); y = np.asarray(y, float)
    yr = y - river_y(x); a = np.abs(yr)
    h = 10.0 + 40.0 * smoothstep(500.0, 1300.0, a) + 200.0 * smoothstep(1300.0, 2800.0, a) + 190.0 * smoothstep(2800.0, 4300.0, a)
    h += 320.0 * smoothstep(4600.0, 6800.0, a)                       # beyond the play space the valley sides keep rising
    # the west end narrows into the gorge, the east end opens into the marsh
    gorge = smoothstep(-4900.0, -6100.0, x)
    h += gorge * 260.0 * smoothstep(180.0, 520.0, a)
    marsh = smoothstep(MARSH_X0, MARSH_X0 + 700.0, x) * (1.0 - smoothstep(700.0, 1000.0, a))
    n_big = fbm(x / 900.0, y / 900.0, 0.3, 4, seed=1)
    n_mid = fbm(x / 260.0, y / 260.0, 0.7, 3, seed=2)
    rough = 0.35 + 0.65 * smoothstep(400.0, 1600.0, a)                 # the floodplain is calmer than the slopes
    h += (18.0 * n_big + 7.0 * n_mid) * rough
    h = h * (1.0 - marsh) + marsh * (-22.0 + 28.0 * fbm(x / 170.0, y / 170.0, 1.1, 3, seed=3))
    return h


def paddy_height(x, yr, x0, x1, yr0, yr1, cx, cy, rows_up, z0):
    """terraced cells: floors stepping up away from the river, dikes between them. Returns (height, inside mask, cell floor z)"""
    x = np.asarray(x, float); yr = np.asarray(yr, float)
    inside = (x >= x0) & (x <= x1) & (yr >= yr0) & (yr <= yr1)
    u = (x - x0) / cx; v = (yr - yr0) / cy
    col = np.floor(u); row = np.floor(v)
    nrow = int(round((yr1 - yr0) / cy))
    ridx = (nrow - 1 - row) if rows_up < 0 else row       # rows_up: which way the terraces climb (away from the river)
    floor = z0 + 8.0 * ridx + 1.5 * col
    du = np.minimum(u - col, col + 1 - u) * cx; dv = np.minimum(v - row, row + 1 - v) * cy
    d = np.minimum(du, dv)                                   # distance to the nearest dike centre line
    # the dike top sits over the higher neighbour's floor
    nb_floor = floor + 8.0 * (dv < du) * (ridx < nrow - 1) * 0 + 0   # placeholder, refined below
    dike = 1.0 - smoothstep(PADDY_DIKE_HW - 6.0, PADDY_DIKE_HW + 10.0, d)
    # near a dike shared with a higher row the floor side rises to that dike's top
    top = floor + PADDY_DIKE_H + 8.0 * ((dv < du) & (((v - row) > 0.5) == (rows_up > 0)) & (ridx < nrow - 1))
    top = np.where(d < PADDY_DIKE_HW + 10.0, top, floor)
    h = floor + (top - floor) * dike - PADDY_WATER_D * (1.0 - dike) * smoothstep(PADDY_DIKE_HW + 10.0, PADDY_DIKE_HW + 40.0, d)
    return h, inside, floor


def features(x, y, h):
    """flags' terraces, bases, karst skirts, paddies, roads, craters"""
    x = np.asarray(x, float); y = np.asarray(y, float)
    yr = y - river_y(x)
    # bases and knolls
    h = plateau(x, y, CT_BASE, CT_PLATEAU_R, CT_FOOT_R, CT_Z, h, warp=0.10, seed=11)
    h = plateau(x, y, T_BASE, T_PLATEAU_R, T_FOOT_R, T_Z, h, warp=0.14, seed=12)
    h = plateau(x, y, VILLAGE, VILLAGE_R, VILLAGE_FOOT, VILLAGE_Z, h, warp=0.12, seed=13)
    h = plateau(x, y, CRASH, CRASH_R, CRASH_FOOT, CRASH_Z, h, warp=0.12, seed=14)
    hb = float(base_terrain(*TEMPLE))
    h = plateau(x, y, TEMPLE, TEMPLE_R, TEMPLE_FOOT, hb + TEMPLE_H, h, warp=0.10, seed=15)
    # karst skirts (talus cones under the towers)
    for (kx, ky, kr, kh, ks) in KARST:
        d = _dist(x, y, (kx, ky))
        h = h + 140.0 * (1.0 - smoothstep(kr - 60.0, kr + 420.0, d)) * (1.0 + 0.08 * fbm(x / 90.0, y / 90.0, ks, 2, seed=20 + ks))
    # paddies
    for (x0, x1, yr0, yr1, cx, cy, rows_up) in ((PADDY_X0, PADDY_X1, PADDY_YR0, PADDY_YR1, PADDY_CELL_X, PADDY_CELL_Y, -1),
                                               (PADDY2_X0, PADDY2_X1, PADDY2_YR0, PADDY2_YR1, PADDY2_CELL_X, PADDY2_CELL_Y, 1)):
        z0 = 14.0 if rows_up < 0 else 16.0
        ph, inside, _ = paddy_height(x, yr, x0, x1, yr0, yr1, cx, cy, rows_up, z0)
        # blend into the surroundings over 70 u outside the region
        dx = np.maximum(np.maximum(x0 - x, x - x1), 0); dy = np.maximum(np.maximum(yr0 - yr, yr - yr1), 0)
        dout = np.hypot(dx, dy)
        w = 1.0 - smoothstep(0.0, 70.0, dout)
        h = h * (1 - w) + ph * w
    # gullies and the oxbow
    for (hw, dep, pts) in GULLIES:
        d, u = seg_dist(x, y, pts)
        prof = (1.0 - smoothstep(hw * 0.3, hw * 1.6, d))
        h = h - dep * prof * prof * (0.7 + 0.3 * fbm(x / 120.0, y / 120.0, 3.3, 2, seed=50))
    d, u = seg_dist(x, y, OXBOW)
    h = h - OXBOW_DEPTH * (1.0 - smoothstep(OXBOW_HW * 0.35, OXBOW_HW * 1.5, d)) ** 1.5
    # craters
    for (cx, cy, r, dep) in CRATERS:
        d = _dist(x, y, (cx, cy)) / r
        bowl = np.where(d < 1.0, -dep * (1.0 - d * d) ** 2, 0.0) + np.where((d > 0.8) & (d < 1.5), dep * 0.18 * np.sin(np.clip((d - 0.8) / 0.7, 0, 1) * np.pi), 0.0)
        h = h + bowl
    return h


def _road_profile(pts, hw):
    """heights along a road: the carved terrain sampled at the vertices and smoothed, so the road climbs gently"""
    P = np.asarray(pts, float)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1); cum = np.concatenate([[0], np.cumsum(seg)])
    n = max(8, int(cum[-1] / 60))
    t = np.linspace(0, cum[-1], n + 1)
    xs = np.interp(t, cum, P[:, 0]); ys = np.interp(t, cum, P[:, 1])
    z = carved(xs, ys, roads=False)
    z = np.convolve(np.pad(z, 3, mode='edge'), np.ones(7) / 7, mode='valid')
    return cum[-1], t, z


_ROAD_CACHE = {}


def roads_apply(x, y, h):
    x = np.asarray(x, float); y = np.asarray(y, float)
    for k, (hw, pts) in enumerate(ROADS):
        if k not in _ROAD_CACHE: _ROAD_CACHE[k] = _road_profile(pts, hw)
        L, t, z = _ROAD_CACHE[k]
        d, u = seg_dist(x, y, pts)
        zr = np.interp(u * L, t, z)
        w = 1.0 - smoothstep(hw, hw * 2.3, d)
        h = h * (1 - w) + zr * w
    return h


def carved(x, y, roads=True):
    """terrain after the river carve (the ground players stand on, roads optional)"""
    x = np.asarray(x, float); y = np.asarray(y, float)
    h = features(x, y, base_terrain(x, y))
    yr = y - river_y(x); a = np.abs(yr)
    # river bed: upstream of the fall the whole channel is FALL_H higher; a plunge pool right below the fall
    up = smoothstep(FALL_X + 24.0, FALL_X - 24.0, x) * FALL_H
    pool = -22.0 * smoothstep(FALL_X + 330.0, FALL_X + 40.0, x) * smoothstep(FALL_X - 20.0, FALL_X + 20.0, x)
    bed = BED_Z + 20.0 * (np.minimum(a, RIVER_HW) / RIVER_HW) ** 2 + up + pool
    bank = smoothstep(RIVER_HW, BANK_W, a)
    hb = np.maximum(h, bed + 22.0 + up * 0)       # the floodplain never sits below the bank top
    hr = bed * (1 - bank) + hb * bank
    h = np.where(a < BANK_W, hr, h)
    # marsh pools east: let the ground dip under the water
    if roads: h = roads_apply(x, y, h)
    return h


def height(x, y):
    """final ground height"""
    return carved(x, y, roads=True)


def ground_low(x, y):
    """for make_skybox.py: the terrain beyond the edge (no roads, no features)"""
    return base_terrain(x, y)


def slope(x, y, eps=8.0):
    """slope in degrees"""
    x = np.asarray(x, float); y = np.asarray(y, float)
    dzdx = (height(x + eps, y) - height(x - eps, y)) / (2 * eps)
    dzdy = (height(x, y + eps) - height(x, y - eps)) / (2 * eps)
    return np.degrees(np.arctan(np.hypot(dzdx, dzdy)))


# ---------------------------------------------------------------- masks
def in_play(x, y):
    return (np.abs(np.asarray(x, float)) <= MAP_X) & (np.abs(np.asarray(y, float)) <= MAP_Y)


def water_dist(x, y):
    """distance to the river centre line (approx: along y) """
    return np.abs(np.asarray(y, float) - river_y(x))


def road_dist(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    best = np.full(x.shape, 1e9); hwb = np.zeros(x.shape)
    for hw, pts in ROADS:
        d, _ = seg_dist(x, y, pts)
        m = d - hw < best - hwb
        best = np.where(m, d, best); hwb = np.where(m, hw, hwb)
    return best, hwb


def in_paddies(x, y):
    x = np.asarray(x, float); yr = np.asarray(y, float) - river_y(x)
    a = (x >= PADDY_X0 - 40) & (x <= PADDY_X1 + 40) & (yr >= PADDY_YR0 - 40) & (yr <= PADDY_YR1 + 40)
    b = (x >= PADDY2_X0 - 40) & (x <= PADDY2_X1 + 40) & (yr >= PADDY2_YR0 - 40) & (yr <= PADDY2_YR1 + 40)
    return a | b


def karst_dist(x, y):
    """distance to the nearest karst base circle (negative inside)"""
    x = np.asarray(x, float); y = np.asarray(y, float)
    best = np.full(x.shape, 1e9)
    for (kx, ky, kr, kh, ks) in KARST:
        best = np.minimum(best, _dist(x, y, (kx, ky)) - kr)
    return best


def clearing(x, y):
    """0..1: how open the ground is (1 = no trees): flags, bases, roads, water, paddies, karst, pads and pits"""
    x = np.asarray(x, float); y = np.asarray(y, float)
    c = np.zeros(x.shape)
    for _, _, (fx, fy) in FLAGS: c = np.maximum(c, 1.0 - smoothstep(FLAG_R + 120.0, FLAG_R + 420.0, _dist(x, y, (fx, fy))))
    c = np.maximum(c, 1.0 - smoothstep(CT_PLATEAU_R + 80.0, CT_PLATEAU_R + 380.0, _dist(x, y, CT_BASE)))
    c = np.maximum(c, 0.55 * (1.0 - smoothstep(T_PLATEAU_R - 100.0, T_PLATEAU_R + 300.0, _dist(x, y, T_BASE))))   # the camp keeps trees
    rd, hw = road_dist(x, y); c = np.maximum(c, 1.0 - smoothstep(hw + 30.0, hw + 110.0, rd))
    c = np.maximum(c, 1.0 - smoothstep(BANK_W - 40.0, BANK_W + 160.0, water_dist(x, y)))
    c = np.maximum(c, in_paddies(x, y).astype(float))
    c = np.maximum(c, 1.0 - smoothstep(-20.0, 90.0, karst_dist(x, y)))
    return np.clip(c, 0, 1)


def jungle(x, y):
    """tree density 0..1 before clearings: dense on the slopes and around the camp, patchy groves on the floodplain"""
    x = np.asarray(x, float); y = np.asarray(y, float)
    a = water_dist(x, y)
    slopes = smoothstep(1100.0, 2200.0, a)
    groves = smoothstep(0.15, 0.45, fbm(x / 520.0, y / 520.0, 2.2, 3, seed=31)) * 0.75
    camp = 0.8 * (1.0 - smoothstep(T_PLATEAU_R, T_FOOT_R + 600.0, _dist(x, y, T_BASE)))
    farms = smoothstep(0.42, 0.62, fbm(x / 1400.0 + 3.0, y / 1400.0, 5.5, 2, seed=33) * 0.5 + 0.5) * smoothstep(1300.0, 1800.0, a)
    slopes = slopes * (1.0 - 0.85 * farms)                              # hillside farm clearings and burnt patches
    d = np.maximum(np.maximum(slopes, groves), camp)
    gorge = smoothstep(-4900.0, -5600.0, x) * smoothstep(300.0, 800.0, a)
    d = np.maximum(d, gorge)
    return np.clip(d * (1.0 - clearing(x, y)), 0, 1)


def grass(x, y):
    """elephant grass 0..1: open floodplain and terraces, not under dense jungle"""
    x = np.asarray(x, float); y = np.asarray(y, float)
    a = water_dist(x, y)
    g = smoothstep(0.0, 0.35, fbm(x / 380.0, y / 380.0, 4.4, 3, seed=32)) * (1.0 - smoothstep(1800.0, 2800.0, a)) * smoothstep(BANK_W + 60.0, BANK_W + 300.0, a)
    return np.clip(g * (1.0 - jungle(x, y)) * (1.0 - clearing(x, y) * 0.85), 0, 1)


# ---------------------------------------------------------------- terrain paint (Valve blend materials; weight 1 = layer B)
def grid_slope(Z, cell):
    """slope in degrees of a regular height grid Z[i, j] (x along i)"""
    dzdx = np.gradient(Z, cell, axis=0); dzdy = np.gradient(Z, cell, axis=1)
    return np.degrees(np.arctan(np.hypot(dzdx, dzdy)))


def paint_weight(x, y, z, sl=None, gully_mud=True):
    """returns (blend B weight 0..1, tint 0.6..1.0) for the ground material of a point. sl: slope in degrees (else computed)"""
    x = np.asarray(x, float); y = np.asarray(y, float)
    a = water_dist(x, y)
    if sl is None: sl = slope(x, y)
    wet = 1.0 - smoothstep(BANK_W, BANK_W + 420.0, a)                  # mud near the water
    rd, hw = road_dist(x, y); road = 1.0 - smoothstep(hw - 10.0, hw + 40.0, rd)
    rock = smoothstep(28.0, 48.0, sl)
    j = jungle(x, y)
    n = fbm(x / 140.0, y / 140.0, 0.5, 3, seed=41) * 0.5 + 0.5
    # the valley material is mud(A)/grass(B): grass where dry and flat, mud where wet, on roads and under the canopy
    if gully_mud:
        for (hw, dep, pts) in GULLIES:
            d, _ = seg_dist(x, y, pts); wet = np.maximum(wet, 1.0 - smoothstep(hw, hw * 2.2, d))
        d, _ = seg_dist(x, y, OXBOW); wet = np.maximum(wet, 1.0 - smoothstep(OXBOW_HW, OXBOW_HW * 1.8, d))
    w = np.clip(1.0 - wet * 0.9 - road - j * 0.6 - rock + (n - 0.5) * 0.35, 0, 1)
    tint = np.clip(1.0 - 0.35 * j - 0.12 * wet + 0.08 * (n - 0.5), 0.55, 1.0)
    return w, tint


# ---------------------------------------------------------------- points of interest
def gz(x, y, clearance=0.0):
    return float(height(np.array([x], float), np.array([y], float))[0]) + clearance


def ring(centre, r, n, start=0.0):
    return [(centre[0] + r * math.cos(start + 2 * math.pi * k / n), centre[1] + r * math.sin(start + 2 * math.pi * k / n)) for k in range(n)]


def firebase():
    """CT firebase plan (everything on the plateau, z = CT_Z): pits, pads, bunkers, FDC"""
    c = CT_BASE
    return dict(
        centre=c, z=CT_Z,
        fdc=(c[0] - 40.0, c[1] + 60.0),                                   # the FDC bunker (plotting table inside)
        guns=[(c[0] + 300.0 * math.cos(a), c[1] + 300.0 * math.sin(a)) for a in (math.radians(150), math.radians(230), math.radians(310))],
        ammo=(c[0] + 180.0, c[1] + 140.0),
        pads=[(c[0] + 520.0, c[1] + 120.0), (c[0] + 520.0, c[1] - 240.0), (c[0] + 240.0, c[1] + 460.0)],
        pad_yaw=180.0,
        toc=(c[0] - 330.0, c[1] + 330.0),
        tents=[(c[0] - 420.0, c[1] - 60.0), (c[0] - 420.0, c[1] - 200.0), (c[0] - 300.0, c[1] - 420.0)],
        bunkers=ring(c, CT_PLATEAU_R - 110.0, 6, start=math.radians(15)),
        m2=[0, 2, 4],                                                      # bunker indices with an M2
        tower=(c[0] + 560.0 * math.cos(math.radians(60)), c[1] + 560.0 * math.sin(math.radians(60))),
        gate=(c[0] + (CT_PLATEAU_R - 40.0) * math.cos(math.radians(142)), c[1] + (CT_PLATEAU_R - 40.0) * math.sin(math.radians(142))),
        wire_r=CT_PLATEAU_R - 30.0,
        rack=(c[0] + 60.0, c[1] - 160.0),
        spawns=ring(c, 170.0, 16, start=0.3))


def camp():
    """T camp plan: rocket pits, AA pits, hooches, heli clearing, tunnel portal, FDC hooch"""
    c = T_BASE
    return dict(
        centre=c, z=T_Z,
        fdc=(c[0] + 60.0, c[1] - 80.0),
        rockets=[(c[0] + 330.0 * math.cos(a), c[1] + 330.0 * math.sin(a)) for a in (math.radians(-60), math.radians(-20), math.radians(20), math.radians(60))],
        ammo=(c[0] + 160.0, c[1] + 40.0),
        aa=[(c[0] - 380.0, c[1] + 300.0), (c[0] + 120.0, c[1] + 480.0)],
        pads=[(c[0] - 520.0, c[1] - 200.0), (c[0] - 480.0, c[1] + 160.0), (c[0] - 200.0, c[1] - 520.0)],
        pad_yaw=0.0,
        hooches=[(c[0] - 150.0, c[1] + 260.0), (c[0] - 320.0, c[1] + 20.0), (c[0] + 20.0, c[1] + 330.0), (c[0] - 60.0, c[1] - 330.0), (c[0] + 260.0, c[1] + 300.0)],
        tunnel=(c[0] + 120.0, c[1] - 240.0),
        rack=(c[0] - 40.0, c[1] + 120.0),
        spawns=ring(c, 160.0, 16, start=0.7))


# tunnel plan (T camp): portals and the gallery graph, in the x/y plane; depth below the ground is handled by make_map
TUNNEL_FLOOR_Z = T_Z - 230.0
TUNNEL_PORTALS = [(T_BASE[0] + 120.0, T_BASE[1] - 240.0),          # camp (inside the base)
                  (-3100.0, 1750.0),                                # north-west slope exit toward the paddies trail
                  (-2300.0, 2850.0)]                                # exit toward the village road
TUNNEL_GALLERIES = [[(T_BASE[0] + 120.0, T_BASE[1] - 240.0), (-3600.0, 2400.0), (-3300.0, 2050.0), (-3100.0, 1750.0)],
                    [(-3600.0, 2400.0), (-3000.0, 2600.0), (-2300.0, 2850.0)],
                    [(-3300.0, 2050.0), (-3000.0, 2600.0)]]        # cross cut
TUNNEL_CHAMBER = (-3300.0, 2350.0)


def flag_spawns(letter):
    for l, name, c in FLAGS:
        if l == letter:
            return ring(c, 230.0, 8, start=0.4)
    raise KeyError(letter)


def mounted_guns():
    """neutral emplaced guns: (name, kind, (x, y), yaw)"""
    b = FLAGS[1][2]; d = TEMPLE
    return [('bridge', 'm2', (b[0] + 150.0, b[1] - BANK_W - 160.0), 90.0),
            ('temple', 'dshk', (d[0] + 60.0, d[1] - 40.0), -90.0)]


# ---------------------------------------------------------------- export for the script / radar / board
def export(path):
    fb = firebase(); cp = camp()
    data = dict(
        map=dict(x=MAP_X, y=MAP_Y, air=[AIR_X, AIR_Y, AIR_Z], water_z=WATER_Z, lobby_z=LOBBY_Z, park_z=PARK_Z),
        flags=[dict(id=l, name=n, x=c[0], y=c[1], z=gz(*c), r=FLAG_R) for l, n, c in FLAGS],
        ct=dict(centre=list(CT_BASE), z=CT_Z, guns=[list(g) for g in fb['guns']], fdc=list(fb['fdc']), pads=[list(p) for p in fb['pads']], pad_yaw=fb['pad_yaw']),
        t=dict(centre=list(T_BASE), z=T_Z, guns=[list(g) for g in cp['rockets']], fdc=list(cp['fdc']), pads=[list(p) for p in cp['pads']], pad_yaw=cp['pad_yaw']),
        karst=[dict(x=k[0], y=k[1], r=k[2], h=k[3], top=gz(k[0], k[1]) + k[3]) for k in KARST],
        river=[[float(x), float(river_y(x))] for x in np.linspace(-MAP_X, MAP_X, 65)],
    )
    json.dump(data, open(path, 'w'), indent=1)
    return data


if __name__ == '__main__':
    import sys
    print(json.dumps(export(sys.argv[1] if len(sys.argv) > 1 else 'layout.json'), indent=1)[:2000])
