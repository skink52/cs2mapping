"""IRONFRAME: Dunes (mg_ironframe_dunes). Desert canyon at dusk: a mesa ring at the edge rising to the sky wall, a winding
central canyon (north-south) that widens round a central island plateau (point B), two bank plateaus (A west, C east) joined
to the island by giant pipe bridges, a wrecked megastructure straddling the canyon in the south, a refinery on a pad in the
north-east, dune fields everywhere else. T drops in the west, CT in the east.

Scale: mechs are 240-336 u tall and move at up to 2800 u/s: every passage is >= 600 u, cover walls are 420-480 u tall,
ramps are <= 28 degrees, the terrain is 128-u cells in the play area.
"""
import math
import numpy as np
from scipy import ndimage
from noise import fbm, smoothstep
import vmapgen as G
import arenas.common as C
from arenas.common import M, P

HALF = 7168.0            # terrain / sky shell half extent (28 tiles of 512)
PLAY = 7000.0            # play bounds (INTERFACES: 14000 x 14000)
A_POS, B_POS, C_POS = (-3300.0, 2500.0), (0.0, 0.0), (3300.0, -2500.0)
A_Z, B_Z, C_Z = 760.0, 580.0, 760.0
PLATEAU_R = 1100.0; ISLAND_R = 780.0
WRECK = (0.0, -3600.0); WRECK_Z = 300.0
REF = (3400.0, 3500.0); REF_Z = 430.0
DECK_Z = WRECK_Z + 1200.0            # megastructure deck top


# ---------------------------------------------------------------- heightfield
def canyon_cx(Y):
    return 420.0 * np.sin(Y / 2700.0) + 110.0 * fbm(Y / 900.0, 0 * Y + 0.3, 0 * Y + 0.7, 2, seed=7)


def canyon_depth(X, Y):
    cx = canyon_cx(Y)
    dist = np.abs(X - cx)
    hw = 720.0 + 150.0 * fbm(Y / 1500.0, 0 * Y + 0.2, 0 * Y + 4.0, 2, seed=8)
    hw = hw + 950.0 * (1 - smoothstep(900.0, 2300.0, np.abs(Y)))          # the basin round the island
    prof = 1 - smoothstep(hw, hw + 300.0, dist)
    fade = 1 - smoothstep(4600.0, 5500.0, np.abs(Y))
    island = smoothstep(ISLAND_R - 40.0, ISLAND_R + 420.0, np.hypot(X - B_POS[0], Y - B_POS[1]))
    return 330.0 * prof * fade * island


def pad(Z, X, Y, cx, cy, r, z, soft=520.0):
    w = 1 - smoothstep(r, r + soft, np.hypot(X - cx, Y - cy))
    return Z * (1 - w) + z * w


def height(X, Y):
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    base = 250.0 + 110.0 * fbm(X / 2600.0, Y / 2600.0, 0 * X + 0.3, 4, seed=3) + 22.0 * fbm(X / 700.0, Y / 700.0, 0 * X + 1.1, 3, seed=4)
    wind = fbm(X / 1800.0, Y / 1800.0, 0 * X + 2.0, 3, seed=5)
    phase = (X * 0.86 + Y * 0.5) / 330.0 + 2.4 * wind
    s = 0.5 + 0.5 * np.sin(phase)
    dunes = 95.0 * s ** 1.7 * (0.55 + 0.45 * (0.5 + 0.5 * fbm(X / 1300.0, Y / 1300.0, 0 * X, 3, seed=6)))
    Z = base + dunes
    # pads: plateaus and structure sites
    Z = pad(Z, X, Y, A_POS[0], A_POS[1], PLATEAU_R, A_Z); Z = pad(Z, X, Y, C_POS[0], C_POS[1], PLATEAU_R, C_Z)
    Z = pad(Z, X, Y, B_POS[0], B_POS[1], ISLAND_R, B_Z, soft=420.0)
    Z = pad(Z, X, Y, WRECK[0], WRECK[1], 1700.0, WRECK_Z, soft=700.0)
    Z = pad(Z, X, Y, REF[0], REF[1], 1250.0, REF_Z, soft=600.0)
    # mesa ring: rises to the sky wall, terraced
    rq = np.maximum(np.abs(X), np.abs(Y))
    t = smoothstep(5400.0, HALF, rq)
    rise = 1650.0 * t ** 1.5
    terr = rise + 45.0 * np.sin(rise / 150.0) * t + 60.0 * t * fbm(X / 600.0, Y / 600.0, 0 * X + 5.0, 3, seed=9)
    Z = Z + terr
    Z = Z - canyon_depth(X, Y)
    return np.maximum(Z, 24.0)


def ground_at(x, y):
    return float(height(np.array([float(x)]), np.array([float(y)]))[0])


def slope(X, Y, h=24.0):
    zx = height(X + h, Y) - height(X - h, Y); zy = height(X, Y + h) - height(X, Y - h)
    return np.hypot(zx, zy) / (2 * h)


# ---------------------------------------------------------------- structures (axis boxes the nav grid knows about)
SOLIDS = []       # (x0, y0, z0, x1, y1, z1, walk_top): walk_top = a mech stands on top; else it is an obstacle
STRUCT = []       # footprints for nav.struct


def solid_box(ctx, b, mats, walk_top=True, **kw):
    ctx.box(b, mats, **kw)
    SOLIDS.append(tuple(b) + (walk_top,))


def ground(X, Y):
    """terrain plus the tops of walkable structure boxes"""
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    Z = height(X, Y)
    for (x0, y0, z0, x1, y1, z1, wt) in SOLIDS:
        if not wt: continue
        inside = (X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1)
        Z = np.where(inside, np.maximum(Z, z1), Z)
    return Z


def solid(X, Y):
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    out = np.zeros(X.shape, bool)
    for (x0, y0, z0, x1, y1, z1, wt) in SOLIDS:
        if wt: continue
        out |= (X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1)
    return out


def bridge(ctx, p0, z0, p1, z1, r=170.0, deck_w=720.0):
    """giant pipe with a deck on top between two plateau edges; the deck top meets the plateau height at each end"""
    p0 = np.array(p0, float); p1 = np.array(p1, float)
    d = p1 - p0; L = float(np.hypot(*d)); yaw = math.degrees(math.atan2(d[1], d[0]))
    deck_t = 48.0
    c0 = np.array([p0[0], p0[1], z0 - deck_t - r]); c1 = np.array([p1[0], p1[1], z1 - deck_t - r])
    ctx.cylinder(c0, c1, r, dict(side=M['rust'], cap=M['metal_trim']), n=18)
    mid = (c0 + c1) / 2 + np.array([0, 0, r + deck_t / 2])
    pitch = -math.degrees(math.atan2(z1 - z0, L))
    ctx.obox(mid, (L / 2 + 40, deck_w / 2, deck_t / 2), yaw, pitch, mats=dict(top=M['metal_floor'], side=M['rust'], bottom=M['rust']))
    for s in (-1, 1):
        off = np.array([-d[1], d[0]]) / L * s * (deck_w / 2 - 30)
        ctx.obox(mid + np.array([off[0], off[1], deck_t / 2 + 70]), (L / 2 + 40, 30, 70), yaw, pitch, mats=M['metal_trim'])
    # nav: the deck as walkable strips along the line (axis-aligned pieces)
    n = max(2, int(L // 400))
    for k in range(n):
        t0, t1 = k / n, (k + 1) / n
        a = p0 + d * t0; b = p0 + d * t1; zt = z0 + (z1 - z0) * (t0 + t1) / 2
        x0, x1 = sorted((a[0], b[0])); y0, y1 = sorted((a[1], b[1]))
        SOLIDS.append((x0 - deck_w / 2, y0 - deck_w / 2, zt - 400, x1 + deck_w / 2, y1 + deck_w / 2, zt, True))
    STRUCT.append((min(p0[0], p1[0]) - 400, min(p0[1], p1[1]) - 400, max(p0[0], p1[0]) + 400, max(p0[1], p1[1]) + 400))


def megastructure(ctx):
    """the wreck: 4 x 3 concrete pillars, a metal deck 1200 u up spanning the canyon with a hole, two collapsed-slab ramps,
    girders, leaning siding panels"""
    cx, cy = WRECK
    cols = [cx - 1500, cx - 500, cx + 500, cx + 1500]; rows = [cy - 800, cy, cy + 800]
    tall = {(0, 0), (3, 2), (0, 2)}                      # pillars that still carry the roof frame
    broken = {(1, 2), (3, 0)}
    for i, px in enumerate(cols):
        for j, py in enumerate(rows):
            gz = ground_at(px, py) - 60
            top = 2650.0 if (i, j) in tall else (DECK_Z - 450 if (i, j) in broken else DECK_Z)
            solid_box(ctx, (px - 160, py - 160, gz, px + 160, py + 160, top), dict(top=M['concrete_dark'], side=M['concrete']), walk_top=False)
    deck_t = 80.0
    for j, py in enumerate(rows):
        if j == 1:
            # middle strip with a 1400-u hole over the canyon
            solid_box(ctx, (cols[0] - 160, py - 320, DECK_Z - deck_t, cx - 700, py + 320, DECK_Z), dict(top=M['metal_floor'], side=M['rust'], bottom=M['rust']))
            solid_box(ctx, (cx + 700, py - 320, DECK_Z - deck_t, cols[3] + 160, py + 320, DECK_Z), dict(top=M['metal_floor'], side=M['rust'], bottom=M['rust']))
        else:
            x1 = cols[3] + 160 if (3, j) not in broken else cols[2] + 160
            x0 = cols[0] - 160 if (0, j) not in broken else cols[1] - 160
            solid_box(ctx, (x0, py - 320, DECK_Z - deck_t, x1, py + 320, DECK_Z), dict(top=M['metal_floor'], side=M['rust'], bottom=M['rust']))
    # connecting strips between the rows (so the deck is one surface with 160-u slots, not three islands)
    for px in (cols[0] + 500, cols[2] + 500):
        solid_box(ctx, (px - 300, rows[0] + 320, DECK_Z - deck_t, px + 300, rows[2] - 320, DECK_Z), dict(top=M['grate'], side=M['rust'], bottom=M['rust']))
    # girders between the tall pillars and along the deck edges (cover on the deck, 300 x 300)
    for (a, b) in (((0, 0), (0, 2)), ((0, 2), (3, 2))):
        pa = (cols[a[0]], rows[a[1]]); pb = (cols[b[0]], rows[b[1]])
        x0, x1 = sorted((pa[0], pb[0])); y0, y1 = sorted((pa[1], pb[1]))
        ctx.box((x0 - 150, y0 - 150, 2350.0, x1 + 150, y1 + 150, 2650.0), M['rust'])
    for py in (rows[0] - 320 + 150, rows[2] + 320 - 150):
        for (xa, xb) in ((cols[0] + 200, cols[1] - 200), (cols[2] + 200, cols[3] - 200)):
            solid_box(ctx, (xa, py - 150, DECK_Z, xb, py + 150, DECK_Z + 300), M['rust'], walk_top=False)
    # ramps: collapsed slabs from the deck ends down to the sand, 900 wide, 26 degrees
    for s in (-1, 1):
        x_edge = cols[3 if s > 0 else 0] + s * 160
        gz = ground_at(x_edge + s * 2700, cy)
        dz = DECK_Z - gz; run = dz / math.tan(math.radians(26.0)); L = math.hypot(run, dz)
        mid = (x_edge + s * run / 2, cy, (DECK_Z + gz) / 2 - deck_t / 2)
        pitch = -s * 26.0 if s > 0 else 26.0
        ctx.obox(mid, (L / 2 + 30, 450, deck_t / 2), 0.0, 26.0 * s, mats=dict(top=M['metal_floor'], side=M['rust'], bottom=M['rust']))
        n = 6
        for k in range(n):
            t0, t1 = k / n, (k + 1) / n
            xa, xb = sorted((x_edge + s * run * t0, x_edge + s * run * t1)); zt = DECK_Z - dz * (t0 + t1) / 2
            SOLIDS.append((xa, cy - 450, zt - 300, xb, cy + 450, zt, True))
    # leaning siding panels and fallen girders round the base
    rng = np.random.RandomState(41)
    for k in range(10):
        px = cx + rng.uniform(-2100, 2100); py = cy + rng.uniform(-1300, 1300)
        if abs(px - canyon_cx(np.array([py]))[0]) < 900: continue
        gz = ground_at(px, py); yaw = rng.uniform(0, 360)
        ctx.obox((px, py, gz + 330), (420, 24, 380), yaw, 0.0, rng.uniform(-22, 22), mats=M['corrugated'])
        SOLIDS.append(C.rot_bbox(px, py, 420, 160, yaw, gz, gz + 700))
    for k in range(5):
        px = cx + rng.uniform(-1800, 1800); py = cy + rng.uniform(-1500, 1500)
        gz = ground_at(px, py)
        ctx.obox((px, py, gz + 120), (650, 120, 120), rng.uniform(0, 360), rng.uniform(-6, 6), mats=M['rust'])
    STRUCT.append((cols[0] - 400, rows[0] - 700, cols[3] + 400, rows[2] + 700))
    STRUCT.append((cols[3], cy - 600, cols[3] + 2900, cy + 600)); STRUCT.append((cols[0] - 2900, cy - 600, cols[0], cy + 600))
    # lights under the deck and on the roof frame
    for px in (cols[0] + 500, cols[2] + 500):
        ctx.lamp((px, cy, DECK_Z - 120), 60000, 1400, '255 190 130', shadows=(px < cx))
    ctx.lamp((cols[0], rows[2], 2750), 40000, 1600, '255 120 80')
    ctx.lamp((cols[3], rows[2], 2750), 40000, 1600, '255 120 80')


def refinery(ctx):
    cx, cy = REF; z = REF_Z
    tanks = [(cx - 600, cy + 400, 400.0, 650.0), (cx + 250, cy + 650, 380.0, 700.0), (cx - 150, cy - 500, 440.0, 560.0)]
    for (tx, ty, r, h) in tanks:
        ctx.cylinder((tx, ty, z - 20), (tx, ty, z + h), r, dict(side=M['corrugated'], cap=M['metal_floor']), n=24)
        SOLIDS.append((tx - r, ty - r, z, tx + r, ty + r, z + h, False))
        ctx.cylinder((tx, ty, z + h), (tx, ty, z + h + 60), r * 0.3, M['metal_trim'], n=12)
    # stack
    ctx.cylinder((cx + 750, cy - 150, z - 20), (cx + 750, cy - 150, z + 1750), 150.0, dict(side=M['concrete'], cap=M['concrete_dark']), n=16)
    SOLIDS.append((cx + 600, cy - 300, z, cx + 900, cy, z + 1750, False))
    # control block (walkable roof, reached by a ramp) and a pipe rack
    bb = (cx + 150, cy - 1150, z - 20, cx + 1150, cy - 450, z + 520)
    solid_box(ctx, bb, dict(top=M['concrete_floor'], side=M['concrete2']))
    ctx.obox((cx + 1150 + 560, cy - 800, z + 260 - 24), (600, 330, 24), 0.0, -24.0, mats=dict(top=M['metal_floor'], side=M['rust'], bottom=M['rust']))
    for k in range(4):
        xa = cx + 1150 + k * 280; SOLIDS.append((xa, cy - 1130, z, xa + 280, cy - 470, z + 520 - k * 130, True))
    for k, zz in enumerate((z + 380, z + 560)):
        ctx.cylinder((cx - 1100, cy - 100 + k * 30, zz), (cx + 600, cy - 100 + k * 30, zz), 70.0, M['rust'], n=12)
    for px in np.arange(cx - 1000, cx + 601, 500):
        ctx.box((px - 60, cy - 160, z - 20, px + 60, cy - 40, z + 640), M['metal_trim'])
        SOLIDS.append((px - 60, cy - 160, z, px + 60, cy - 40, z + 640, False))
    # stock props at mech scale
    ctx.prop(P['silo'], (cx - 1000, cy + 900, z), 20, 3.0); ctx.prop(P['silo'], (cx - 700, cy + 1050, z), 70, 3.0)
    ctx.prop(P['cooling'], (cx + 900, cy + 500, z), 0, 2.6)
    ctx.prop(P['cell_tower'], (cx + 1100, cy + 1000, z), 0, 1.6)
    for k in range(5):
        ctx.prop(P['container'], (cx - 1000 + k * 330, cy - 1100, z), 90 + (k % 2) * 4, 2.5)
    ctx.prop(P['tanker'], (cx - 900, cy - 700, z), 0, 2.2); ctx.prop(P['tanker'], (cx - 900, cy - 480, z), 0, 2.2)
    for k in range(4):
        ctx.prop(P['pipe1024'], (cx - 1200 + k * 1024 * 1.5, cy + 1250, z + 30), 0, 1.5, solid='0')
    STRUCT.append((cx - 1300, cy - 1300, cx + 1900, cy + 1300))
    for (lx, ly, sh) in ((cx - 200, cy + 100, True), (cx + 700, cy - 800, False), (cx - 900, cy + 800, False)):
        ctx.lamp((lx, ly, z + 520), 50000, 1300, '255 150 70', shadows=sh)


def plateau_cover(ctx, cx, cy, z, rng, n=7):
    for k in range(n):
        a = rng.uniform(0, 2 * math.pi); r = rng.uniform(250, PLATEAU_R - 200)
        px, py = cx + r * math.cos(a), cy + r * math.sin(a)
        yaw = rng.uniform(0, 360)
        ctx.obox((px, py, z + 210), (450, 70, 230), yaw, mats=dict(top=M['concrete_dark'], side=M['concrete']))
        SOLIDS.append(C.rot_bbox(px, py, 450, 70, yaw, z, z + 440))


def canyon_rocks(ctx, rng, n=14):
    for k in range(n):
        y = rng.uniform(-4300, 4300)
        if abs(y) < 900: continue
        x = canyon_cx(np.array([y]))[0] + rng.uniform(-420, 420)
        gz = ground_at(x, y); s = rng.uniform(230, 360); yaw = rng.uniform(0, 360)
        ctx.obox((x, y, gz + s * 0.7), (s, s * 0.8, s * 0.9), yaw, rng.uniform(-8, 8), rng.uniform(-8, 8), mats=M['stone'])
        SOLIDS.append(C.rot_bbox(x, y, s, s * 0.8, yaw, gz, gz + s * 1.6))


def dune_props(ctx, rng):
    def ok(x, y):
        if abs(x - canyon_cx(np.array([y]))[0]) < 1100 and abs(y) < 5200: return False
        for (cx, cy, r) in ((A_POS[0], A_POS[1], 1500), (C_POS[0], C_POS[1], 1500), (WRECK[0], WRECK[1], 2300), (REF[0], REF[1], 1800)):
            if math.hypot(x - cx, y - cy) < r: return False
        return max(abs(x), abs(y)) < 5300
    k = 0
    while k < 26:
        x, y = rng.uniform(-5300, 5300), rng.uniform(-5300, 5300)
        if not ok(x, y): continue
        gz = ground_at(x, y); yaw = rng.uniform(0, 360)
        for j in range(rng.randint(1, 4)):
            ox, oy = x + j * 340 * math.cos(math.radians(yaw + 90)), y + j * 340 * math.sin(math.radians(yaw + 90))
            ctx.prop(P['container'], (ox, oy, ground_at(ox, oy) - 10), yaw + rng.uniform(-6, 6), 2.5, roll=rng.uniform(-3, 3))
            SOLIDS.append(C.rot_bbox(ox, oy, 150, 360, yaw, gz, gz + 340))      # 120 x 288 x 136 model at 2.5x
        k += 1
    for (x, y) in ((-6000, -6000), (6000, 6000), (-6100, 5900), (6100, -5900)):
        gz = ground_at(x, y); ctx.prop(P['cell_tower'], (x, y, gz - 20), rng.uniform(0, 360), 2.2)
    for k in range(8):
        x, y = rng.uniform(-5000, 5000), rng.uniform(-5000, 5000)
        if ok(x, y): ctx.prop(P['garbage'], (x, y, ground_at(x, y) - 4), rng.uniform(0, 360), 3.0)


# ---------------------------------------------------------------- terrain paint and materials
def paint(X, Y, Z):
    sl = slope(X, Y)
    rock = smoothstep(0.35, 0.75, sl)
    n1 = fbm(X / 900.0, Y / 900.0, 0 * X + 0.3, 4, seed=21); n2 = fbm(X / 260.0, Y / 260.0, 0 * X + 1.3, 3, seed=22)
    crest = 0.5 + 0.5 * np.sin((X * 0.86 + Y * 0.5) / 330.0 + 2.4 * fbm(X / 1800.0, Y / 1800.0, 0 * X + 2.0, 3, seed=5))
    w_sand = np.clip(0.5 + 0.35 * n1 + 0.25 * n2 + 0.3 * (crest - 0.5), 0, 1)       # sand02 <-> sand03 (B = darker, in the troughs)
    w_rock = np.clip(1 - rock + 0.2 * n2, 0, 1)                                       # stone <-> smooth: smooth where flat
    stony = (sl > 0.3) | (canyon_depth(X, Y) > 60) | (np.maximum(np.abs(X), np.abs(Y)) > 5500)
    w = np.where(stony, w_rock, w_sand)
    t = np.clip(0.86 + 0.1 * n1 + 0.05 * n2, 0.7, 1.0)
    t = t * (1 - 0.18 * np.clip(canyon_depth(X, Y) / 330.0, 0, 1))
    pa = np.stack([w, np.zeros_like(w), np.full(w.shape, 0.35), np.zeros_like(w)], -1)
    ti = np.stack([t, t, t, np.ones_like(t)], -1)
    return pa, ti


_MATGRID = {}
def material(cx, cy):
    """per-cell material from a 64-u raster computed once (a scalar fbm call per cell would take minutes)"""
    if not _MATGRID:
        xs = np.arange(-HALF, HALF + 1, 64.0); X, Y = np.meshgrid(xs, xs, indexing='ij')
        stony = (slope(X, Y) > 0.3) | (canyon_depth(X, Y) > 60) | (np.maximum(np.abs(X), np.abs(Y)) > 5500)
        _MATGRID['stony'] = stony; _MATGRID['n'] = len(xs)
    i = int(np.clip(round((cx + HALF) / 64.0), 0, _MATGRID['n'] - 1)); j = int(np.clip(round((cy + HALF) / 64.0), 0, _MATGRID['n'] - 1))
    return M['rock_blend'] if _MATGRID['stony'][i, j] else M['sand_blend']


def tile_res(cx, cy):
    return 64 if max(abs(cx), abs(cy)) < 6100 else 128


def radar_zones(X, Y, Z):
    sl = slope(X, Y)
    sand = np.array([0.82, 0.68, 0.46]); rock = np.array([0.55, 0.42, 0.34]); dark = np.array([0.42, 0.33, 0.28])
    rocky = smoothstep(0.3, 0.7, sl)[..., None]
    col = sand * (1 - rocky) + rock * rocky
    cd = np.clip(canyon_depth(X, Y) / 330.0, 0, 1)[..., None]
    col = col * (1 - cd) + dark * cd
    return col


# ---------------------------------------------------------------- build
def build(ctx):
    rng = np.random.RandomState(7)
    T = G.Terrain(height, -HALF, -HALF, HALF, HALF, tile=512, res=tile_res)
    nq = T.build(material, paint=paint, group=ctx.group)
    print('dunes terrain: %d tiles, %d quads' % (len(T.tiles), nq))
    megastructure(ctx)
    refinery(ctx)
    plateau_cover(ctx, A_POS[0], A_POS[1], A_Z, rng); plateau_cover(ctx, C_POS[0], C_POS[1], C_Z, rng)
    plateau_cover(ctx, B_POS[0], B_POS[1], B_Z, rng, n=4)
    canyon_rocks(ctx, rng)
    dune_props(ctx, rng)
    # pipe bridges A -> B -> C
    for (pa, za) in ((A_POS, A_Z), (C_POS, C_Z)):
        d = np.array(B_POS) - np.array(pa); d /= np.hypot(*d)
        p0 = np.array(pa) + d * (PLATEAU_R - 80); p1 = np.array(B_POS) - d * (ISLAND_R - 80)
        bridge(ctx, p0, za, p1, B_Z)
    # point lights so A/B/C are visible from afar at dusk
    for (pos, z, col) in ((A_POS, A_Z, '120 200 255'), (B_POS, B_Z, '255 255 255'), (C_POS, C_Z, '255 170 90')):
        ctx.lamp((pos[0], pos[1], z + 700), 90000, 1800, col)
    # gameplay positions
    def drops(x, n=8):
        out = []
        for i in range(n):
            y = -3500 + i * 7000.0 / (n - 1)
            out.append((x, y, ground_at(x, y) + 1500.0, 0.0 if x < 0 else 180.0))
        return out
    ffa = []
    for i in range(8):
        a = math.radians(22.5 + i * 45.0); x, y = 4300 * math.cos(a), 4300 * math.sin(a)
        ffa.append((x, y, ground_at(x, y) + 1500.0, (math.degrees(a) + 180.0) % 360))
    A = dict(
        bounds=((-PLAY, -PLAY, 0.0), (PLAY, PLAY, 5000.0)), ground=ground, solid=solid, struct=list(STRUCT), walk_ok=None,
        points=[('A', (A_POS[0], A_POS[1], A_Z), 700), ('B', (B_POS[0], B_POS[1], B_Z), 700), ('C', (C_POS[0], C_POS[1], C_Z), 700)],
        drops=dict(t=drops(-5600.0), ct=drops(5600.0), ffa=ffa),
        landmarks=[('Wreck', (WRECK[0], WRECK[1], DECK_Z)), ('Refinery', (REF[0], REF[1], REF_Z)), ('Plateau A', (A_POS[0], A_POS[1], A_Z)),
                   ('Island', (B_POS[0], B_POS[1], B_Z)), ('Plateau C', (C_POS[0], C_POS[1], C_Z)), ('North Pass', (0.0, 5000.0, ground_at(0, 5000))),
                   ('South Canyon', (float(canyon_cx(np.array([-4800.0]))[0]), -4800.0, ground_at(canyon_cx(np.array([-4800.0]))[0], -4800))),
                   ('West Rim', (-6200.0, 0.0, ground_at(-6200, 0))), ('East Rim', (6200.0, 0.0, ground_at(6200, 0)))],
        env=dict(sun_angles=(14.0, 240.0, 0.0), sun_color='255 196 140', sun_brightness=2.0, sky_color='150 118 160', sky_intensity=1.25, sun_fog=0.6,
                 sky_tint='255 245 235', sky_brightness=1.0, exposure=(0.6, 1.7), ambient=(3000, '255 220 180'),
                 fog=dict(cubemapfogstartdistance=600, cubemapfogenddistance=11000, cubemapfogheightstart=200.0, cubemapfogheightend=2400.0, cubemapfogmaxopacity=0.8),
                 vfog=dict(FogStrength=0.5, TintColor='230 190 150', NoiseStrength=0.5)),
        shell=(-HALF, -HALF, -1024.0, HALF, HALF, 6144.0), play=(-HALF, -HALF, 0.0, HALF, HALF, 5000.0), ground_probe_top=1200.0,
        # vis: one Lowest over everything (common.hints) + this Lower box over the structure band. Compiled 9 Nov 2026 in 37.4 min
        # (30,064 initial clusters, LOS scan 22 min, merge to 4,094 about 8 min). hints=[] (Lowest only) should cut that but is untested.
        hints=[((-4700.0, -5000.0, 0.0, 4700.0, 5000.0, 1700.0), 'Lower')], lmres='terrain', radar_zones=radar_zones, relief_height=height, terrain=T)
    return A
