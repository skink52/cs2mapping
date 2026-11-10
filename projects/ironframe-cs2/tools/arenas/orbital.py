"""IRONFRAME: Orbital (mg_ironframe_orbital). Industrial platforms over a cloud sea round a space-elevator column.
Tier 0 (z 0): the 4000 x 4000 central platform round the column (point B). Tier 1 (z 1500): four 2400 x 2400 platforms at
(+-3800, +-3800) joined into a ring by 700-u gantries; points A (north-west) and C (south-east). Tier 2 (z 3000): the column
deck (2400 x 2400) and two outlying fins at (0, +-5600), flight only. Ramps (29 degrees) from tier 0 to each tier-1 platform.
Below everything is the void: bounds.min.z = -600 is the death height the core applies. T drops over the west platforms
(x = -3800), CT over the east (x = +3800).
"""
import math
import numpy as np
from noise import fbm, smoothstep
import vmapgen as G
import fx_models
import arenas.common as C
from arenas.common import M, P

HALF = 7168.0; PLAY = 7000.0
DEATH_Z = -600.0
T0, T1, T2 = 0.0, 1500.0, 3000.0
CENTRAL = 2000.0; PLAT = 1200.0; PLAT_AT = 3800.0; GANTRY_W = 700.0
COL_R = 420.0
SOLIDS = []; STRUCT = []; LMRES = []


def plate(ctx, b, mats=None, walk=True, lm=True):
    x0, y0, z0, x1, y1, z1 = b
    ctx.box(b, mats or dict(top=M['grate'], side=M['steel_plate'], bottom=M['panel']))
    SOLIDS.append((x0, y0, z0, x1, y1, z1, walk)); STRUCT.append((x0, y0, x1, y1))
    if lm: LMRES.append((x0, y0, z1 - 8, x1, y1, z1 + 400))


def railing(ctx, b, z, inset=40.0, h=120.0, gaps=()):
    """120-u kerb round a platform top (mech scale: a trip rail, not a wall); gaps: ('n'|'s'|'e'|'w', c0, c1) openings"""
    x0, y0, x1, y1 = b
    def seg(side, a, bb):
        if side in 'ns':
            y = y1 - inset if side == 'n' else y0 + inset
            ctx.box((a, y - 30, z, bb, y + 30, z + h), M['metal_trim'])
        else:
            x = x1 - inset if side == 'e' else x0 + inset
            ctx.box((x - 30, a, z, x + 30, bb, z + h), M['metal_trim'])
    for side in 'nsew':
        lo, hi = (x0 + inset, x1 - inset) if side in 'ns' else (y0 + inset, y1 - inset)
        cuts = sorted([(c0, c1) for (s, c0, c1) in gaps if s == side])
        a = lo
        for (c0, c1) in cuts:
            if c0 > a: seg(side, a, c0)
            a = c1
        if a < hi: seg(side, a, hi)


def ground(X, Y):
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    Z = np.full(X.shape, DEATH_Z)
    for (x0, y0, z0, x1, y1, z1, wt) in SOLIDS:
        if not wt: continue
        Z = np.where((X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1), np.maximum(Z, z1), Z)
    return Z


def solid(X, Y):
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    out = np.zeros(X.shape, bool)
    for (x0, y0, z0, x1, y1, z1, wt) in SOLIDS:
        if wt: continue
        out |= (X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1)
    return out


def walk_ok(X, Y):
    return ground(X, Y) > DEATH_Z + 1


def ramp(ctx, p0, z0, p1, z1, w=GANTRY_W, t=60.0):
    p0 = np.array(p0, float); p1 = np.array(p1, float); d = p1 - p0; L = float(np.hypot(*d))
    yaw = math.degrees(math.atan2(d[1], d[0])); pitch = -math.degrees(math.atan2(z1 - z0, L))
    S = math.hypot(L, z1 - z0)
    mid = ((p0 + p1) / 2).tolist() + [(z0 + z1) / 2 - t / 2]
    ctx.obox(mid, (S / 2 + 20, w / 2, t / 2), yaw, pitch, mats=dict(top=M['grate'], side=M['steel_plate'], bottom=M['panel']))
    for s in (-1, 1):
        off = np.array([-d[1], d[0]]) / L * s * (w / 2 - 40)
        ctx.obox([mid[0] + off[0], mid[1] + off[1], mid[2] + t / 2 + 60], (S / 2 + 20, 30, 60), yaw, pitch, mats=M['metal_trim'])
    n = max(2, int(L // 350))
    for k in range(n):
        a = p0 + d * k / n; b = p0 + d * (k + 1) / n; zt = z0 + (z1 - z0) * (k + 0.5) / n
        x0, x1 = sorted((a[0], b[0])); y0, y1 = sorted((a[1], b[1]))
        SOLIDS.append((x0 - w / 2, y0 - w / 2, zt - 300, x1 + w / 2, y1 + w / 2, zt, True))
    STRUCT.append((min(p0[0], p1[0]) - w, min(p0[1], p1[1]) - w, max(p0[0], p1[0]) + w, max(p0[1], p1[1]) + w))


def machinery(ctx, cx, cy, z, rng, n=5, r=1000.0):
    for k in range(n):
        a = rng.uniform(0, 2 * math.pi); d = rng.uniform(250, r)
        px, py = cx + d * math.cos(a), cy + d * math.sin(a)
        kind = rng.randint(3)
        if kind == 0:
            ctx.cylinder((px, py, z), (px, py, z + rng.uniform(380, 620)), rng.uniform(150, 240), dict(side=M['corrugated'], cap=M['metal_floor']), n=14)
            SOLIDS.append((px - 240, py - 240, z, px + 240, py + 240, z + 620, False))
        elif kind == 1:
            ctx.obox((px, py, z + 200), (420, 80, 200), rng.uniform(0, 360), mats=dict(top=M['metal_floor'], side=M['panel'], bottom=M['panel']))
            SOLIDS.append((px - 300, py - 300, z, px + 300, py + 300, z + 400, False))
        else:
            ctx.prop(P['container'], (px, py, z), rng.uniform(0, 360), 2.4)
            SOLIDS.append((px - 380, py - 380, z, px + 380, py + 380, z + 340, False))


def radar_zones(X, Y, Z):
    col = np.full(X.shape + (3,), 0.86)
    on = (Z > DEATH_Z + 1)[..., None]
    t = np.clip((Z - T0) / (T2 - T0), 0, 1)[..., None]
    steel = np.array([0.3, 0.33, 0.38]) * (1 - t) + np.array([0.6, 0.63, 0.7]) * t
    return np.where(on, steel, col)


def build(ctx):
    rng = np.random.RandomState(23)
    glow = fx_models.emissive(ctx.out, 'materials/models/%s/fx' % C.PREFIX, 'ifr_orbital_cyan', (60, 220, 255), 14.0, 'IRONFRAME Orbital: edge strip glow (AI-generated)')
    import vmesh; vmesh.TEX_SIZE[glow] = (4, 4)
    # tier 0: central platform with the column through it
    c = CENTRAL
    plate(ctx, (-c, -c, T0 - 160, c, c, T0))
    railing(ctx, (-c, -c, c, c), T0, gaps=[('e', -600, 600), ('w', -600, 600), ('n', -600, 600), ('s', -600, 600)])
    ctx.cylinder((0, 0, DEATH_Z - 600), (0, 0, 4700.0), COL_R, dict(side=M['concrete'], cap=M['concrete_dark']), n=24)
    SOLIDS.append((-COL_R, -COL_R, DEATH_Z, COL_R, COL_R, 4700.0, False))
    for zz in (T0 + 400, T1 + 400, T2 + 400, 4200.0):
        ctx.cylinder((0, 0, zz), (0, 0, zz + 60), COL_R + 24, glow, n=24)
    machinery(ctx, 0, 0, T0, rng, n=7, r=1500.0)
    # tier 1: four platforms joined into a ring by gantries; ramps from tier 0
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = sx * PLAT_AT, sy * PLAT_AT
            plate(ctx, (px - PLAT, py - PLAT, T1 - 140, px + PLAT, py + PLAT, T1))
            gaps = [('w' if sx > 0 else 'e', py - 350, py + 350), ('s' if sy > 0 else 'n', px - 350, px + 350)]
            railing(ctx, (px - PLAT, py - PLAT, px + PLAT, py + PLAT), T1, gaps=gaps)
            machinery(ctx, px, py, T1, rng, n=4, r=800.0)
            # ramp from the central platform edge midpoint toward this platform's inner corner
            p0 = (sx * c, sy * 600.0); p1 = (sx * (PLAT_AT - PLAT + 300), sy * (PLAT_AT - PLAT + 300))
            ramp(ctx, p0, T0, p1, T1)
            # underside struts down to nothing (visual), a light under the platform
            for (ox, oy) in ((-900, -900), (900, -900), (-900, 900), (900, 900)):
                ctx.box((px + ox - 70, py + oy - 70, T1 - 900, px + ox + 70, py + oy + 70, T1 - 140), M['rust'])
            ctx.lamp((px, py, T1 - 300), 60000, 1800, '150 200 255')
    for s in (-1, 1):
        plate(ctx, (s * PLAT_AT - GANTRY_W / 2, -PLAT_AT + PLAT, T1 - 100, s * PLAT_AT + GANTRY_W / 2, PLAT_AT - PLAT, T1))
        plate(ctx, (-PLAT_AT + PLAT, s * PLAT_AT - GANTRY_W / 2, T1 - 100, PLAT_AT - PLAT, s * PLAT_AT + GANTRY_W / 2, T1))
        for k in range(-2, 3):
            ctx.box((s * PLAT_AT - GANTRY_W / 2 + 10, k * 1000 - 30, T1, s * PLAT_AT - GANTRY_W / 2 + 70, k * 1000 + 30, T1 + 120), M['metal_trim'])
    # tier 2: column deck and two fins
    plate(ctx, (-PLAT, -PLAT, T2 - 140, PLAT, PLAT, T2))
    railing(ctx, (-PLAT, -PLAT, PLAT, PLAT), T2)
    machinery(ctx, 0, 0, T2, rng, n=4, r=900.0)
    for s in (-1, 1):
        plate(ctx, (-800, s * 5600 - 600, T2 - 120, 800, s * 5600 + 600, T2))
        railing(ctx, (-800, s * 5600 - 600, 800, s * 5600 + 600), T2)
        ctx.box((-70, s * 5600 - 70, T2 - 1400, 70, s * 5600 + 70, T2 - 120), M['rust'])
        ctx.lamp((0, s * 5600, T2 + 400), 40000, 1200, '255 200 120')
    # edge glow strips on every tier-0/1 platform (thin emissive boxes, no bake)
    for (x0, y0, z0, x1, y1, z1, wt) in list(SOLIDS):
        if not wt or (z1 - z0) < 90 or (x1 - x0) < 2000: continue
        for b in ((x0, y0, z1 - 30, x1, y0 + 16, z1 - 10), (x0, y1 - 16, z1 - 30, x1, y1, z1 - 10), (x0, y0, z1 - 30, x0 + 16, y1, z1 - 10), (x1 - 16, y0, z1 - 30, x1, y1, z1 - 10)):
            ctx.box(b, glow, bake=False, shadows=False, visexclude=True)
    # lights on the decks (one shadowed per tier)
    ctx.lamp((0, 0, T2 + 600), 90000, 2400, '255 255 255', shadows=True)
    ctx.lamp((-PLAT_AT, PLAT_AT, T1 + 600), 70000, 2000, '120 200 255', shadows=True)
    ctx.lamp((PLAT_AT, -PLAT_AT, T1 + 600), 70000, 2000, '255 170 90', shadows=True)
    ctx.lamp((0, 0, T0 + 700), 60000, 2200, '255 240 220')
    def drops(x, n=8):
        return [(x, -4600 + i * 9200.0 / (n - 1), T1 + 1500.0, 0.0 if x < 0 else 180.0) for i in range(n)]
    ffa = [(1400 * math.cos(math.radians(22.5 + 45 * i)), 1400 * math.sin(math.radians(22.5 + 45 * i)), T0 + 1500.0, (202.5 + 45 * i) % 360) for i in range(8)]
    A = dict(
        bounds=((-PLAY, -PLAY, DEATH_Z), (PLAY, PLAY, 5000.0)), ground=ground, solid=solid, struct=list(STRUCT), walk_ok=walk_ok,
        points=[('A', (-PLAT_AT, PLAT_AT, T1), 700), ('B', (0.0, -1300.0, T0), 700), ('C', (PLAT_AT, -PLAT_AT, T1), 700)],
        drops=dict(t=drops(-PLAT_AT), ct=drops(PLAT_AT), ffa=ffa),
        landmarks=[('Column', (0.0, 0.0, T0)), ('Central Platform', (0.0, 0.0, T0)), ('Column Deck', (0.0, 0.0, T2)), ('North Fin', (0.0, 5600.0, T2)),
                   ('South Fin', (0.0, -5600.0, T2)), ('Platform NW', (-PLAT_AT, PLAT_AT, T1)), ('Platform NE', (PLAT_AT, PLAT_AT, T1)),
                   ('Platform SW', (-PLAT_AT, -PLAT_AT, T1)), ('Platform SE', (PLAT_AT, -PLAT_AT, T1))],
        env=dict(sun_angles=(48.0, 315.0, 0.0), sun_color='255 250 240', sun_brightness=2.6, sky_color='170 190 230', sky_intensity=1.4, sun_fog=0.3,
                 sky_tint='255 255 255', sky_brightness=1.0, exposure=(0.5, 1.4), ambient=(3000, '220 230 255'), sun_diameter=0.5,
                 fog=dict(cubemapfogstartdistance=1500, cubemapfogenddistance=14000, cubemapfogheightstart=-600.0, cubemapfogheightend=400.0, cubemapfogmaxopacity=0.7, cubemapfogfalloffexponent=1.1),
                 vfog=dict(FogStrength=0.25, TintColor='225 230 240', NoiseStrength=0.3)),
        shell=(-HALF, -HALF, -1600.0, HALF, HALF, 6144.0), play=(-HALF, -HALF, DEATH_Z, HALF, HALF, 5000.0), ground_probe_top=1200.0,
        hints=[((-5200.0, -6400.0, -300.0, 5200.0, 6400.0, 3600.0), 'Lower')], lmres=list(LMRES), radar_zones=radar_zones)
    return A
