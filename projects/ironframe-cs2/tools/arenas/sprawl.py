"""IRONFRAME: Sprawl (mg_ironframe_sprawl). A ruined night city in the rain: a 6 x 6 grid of blocks (pitch 2400 u: 1500-u blocks,
900-u avenues) of generated towers (800-3000 u tall, emissive window walls, roof parapets, podium slabs), the four central
blocks replaced by a flooded plaza with a dais (point B), two elevated highway slabs (z 700) with pillars and end ramps,
coloured light_omni2 accents, height fog. T drops over the x = -4800 avenue, CT over x = +4800. Points A and C are podium roofs
(z 400) in the NW and SE blocks. Towers taller than 900 u are obstacles for the nav grid; podiums and low roofs are walkable.

IF_SPRAWL_CITY=ops (the default): the towers, streets, signs and rain are NOT written here. This module keeps the layout, the ground,
the plaza, the highways and the nav bookkeeping (SOLIDS / STRUCT), and writes _gen/sprawl_plan.json; tools/arenas/sprawl_ops.py turns
the plan into a create/mapops.py batch (cs2-map-mcp toolset: facades, ruins, storefronts, neon signs, kerbed streets, rain).
IF_SPRAWL_CITY=boxes: the old sketch (plain boxes with stock window textures).
"""
import json, math, os
import numpy as np
from noise import fbm, smoothstep
import vmapgen as G
import arenas.common as C
from arenas.common import M, P

# 22 mechs per arena, 3 copies per map (skink52, 10 Nov 2026): 4 x 4 blocks, ~10 700 u (Dunes' 14 000 was sized for 32)
HALF = 5376.0; PLAY = 5200.0
PITCH = 2400.0; BLOCK = 1500.0; AVENUE = PITCH - BLOCK
CENTRES = [-3600.0, -1200.0, 1200.0, 3600.0]
PLAZA_H = 1950.0; PLAZA_Z = -40.0; WATER_Z = -5.0
HIGHWAY_Z = 700.0; HW_T = 60.0; HW_W = 800.0
A_POS, C_POS = (-3600.0, 3600.0), (3600.0, -3600.0); PODIUM_Z = 400.0
SOLIDS = []; STRUCT = []
CITY = os.environ.get('IF_SPRAWL_CITY', 'ops') == 'ops'
PLAN = dict(towers=[], neon=[], lamps=[], containers=[])


def height(X, Y):
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    Z = (0 * X) if CITY else 2.0 * fbm(X / 900.0, Y / 900.0, 0 * X + 0.2, 2, seed=51)     # flat under the kerbed streets
    plaza = 1 - smoothstep(PLAZA_H - 260.0, PLAZA_H, np.maximum(np.abs(X), np.abs(Y)))
    return Z + PLAZA_Z * plaza


def ground(X, Y):
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    Z = height(X, Y)
    for (x0, y0, z0, x1, y1, z1, wt) in SOLIDS:
        if not wt: continue
        Z = np.where((X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1), np.maximum(Z, z1), Z)
    return Z


def ground_at(x, y):
    """one point of ground() (tools/arenas/objectives.py places pads and rings with it); the street surface is 2 u above it"""
    return float(ground(np.array([x], float), np.array([y], float))[0]) + (2.0 if CITY else 0.0)


def solid(X, Y):
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    out = np.zeros(X.shape, bool)
    for (x0, y0, z0, x1, y1, z1, wt) in SOLIDS:
        if wt: continue
        out |= (X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1)
    return out


def walk_ok(X, Y):
    """not in the water (the dais and the plaza rim are fine)"""
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    inwater = (np.maximum(np.abs(X), np.abs(Y)) < PLAZA_H - 100) & (np.maximum(np.abs(X), np.abs(Y)) > 340)
    return ~inwater


def tower(ctx, x0, y0, x1, y1, z0, h, rng, windows=True):
    top = z0 + h
    lit = bool(windows and rng.uniform() < 0.8)
    side = M['windows_lit'] if lit else M['windows']
    rec = dict(box=[x0, y0, z0, x1, y1, top], lit=lit, walk_roof=h <= 900.0, roof_box=None, seed=int(rng.randint(1 << 30)))
    if not CITY: ctx.box((x0, y0, z0 - 20, x1, y1, top), dict(top=M['concrete_dark'], side=side, bottom=M['concrete']))
    SOLIDS.append((x0, y0, z0, x1, y1, top, h <= 900.0))
    # parapets (200 tall, 80 thick) and a roof box
    t = 80.0
    if not CITY:
        for b in ((x0, y0, top, x1, y0 + t, top + 200), (x0, y1 - t, top, x1, y1, top + 200), (x0, y0, top, x0 + t, y1, top + 200), (x1 - t, y0, top, x1, y1, top + 200)):
            ctx.box(b, M['concrete2'])
    if (x1 - x0) > 700 and rng.uniform() < 0.7:
        rx, ry = rng.uniform(x0 + 200, x1 - 400), rng.uniform(y0 + 200, y1 - 400)
        if not CITY: ctx.box((rx, ry, top, rx + 240, ry + 200, top + 260), dict(top=M['roof_metal'], side=M['concrete2']))
        rec['roof_box'] = [rx, ry, top, rx + 240, ry + 200, top + 260]
        if h <= 900.0: SOLIDS.append((rx, ry, top, rx + 240, ry + 200, top + 260, False))
    PLAN['towers'].append(rec)
    STRUCT.append((x0, y0, x1, y1))
    return top


def street_wall(cx, cy):
    """the block slabs' sides: a street wall of shops and two storeys over them (tools/arenas/sprawl_detail_mats.storefront, a 256-u
    tile at the default 0.25 scale, its pavement row at z = 0) instead of bare concrete. The boxes mode keeps the concrete."""
    return 'materials/ifr/sprawl/d_shop_%d.vmat' % (int(abs(cx * 7 + cy * 13) / 1200) % 4) if CITY else M['concrete']


def block(ctx, cx, cy, rng, kind):
    x0, y0, x1, y1 = cx - BLOCK / 2, cy - BLOCK / 2, cx + BLOCK / 2, cy + BLOCK / 2
    if CITY: PLAN.setdefault('blocks', []).append(dict(centre=[cx, cy], kind=kind))
    if kind == 'podium':
        ctx.box((x0, y0, -20, x1, y1, PODIUM_Z), dict(top=M['concrete_floor'], side=street_wall(cx, cy), bottom=M['concrete']))
        SOLIDS.append((x0, y0, 0, x1, y1, PODIUM_Z, True)); STRUCT.append((x0, y0, x1, y1))
        # ramp up to the podium on the side facing the plaza (25 degrees, 900 wide)
        sx = -1 if cx > 0 else 1; run = PODIUM_Z / math.tan(math.radians(25.0)); L = math.hypot(run, PODIUM_Z)
        xe = x1 if sx > 0 else x0
        ctx.obox((xe + sx * run / 2, cy, PODIUM_Z / 2 - 30), (L / 2 + 20, 450, 30), 0.0, -25.0 * sx, mats=dict(top=M['concrete_floor'], side=M['concrete'], bottom=M['concrete']))
        for k in range(4):
            xa, xb = sorted((xe + sx * run * k / 4, xe + sx * run * (k + 1) / 4)); SOLIDS.append((xa, cy - 450, 0, xb, cy + 450, PODIUM_Z * (1 - (k + 0.5) / 4), True))
        # two mid-height towers on the podium, leaving the roof between them as the point
        tower(ctx, x0 + 60, y0 + 60, x0 + 560, y0 + 620, PODIUM_Z, rng.uniform(900, 1400), rng)
        tower(ctx, x1 - 560, y1 - 620, x1 - 60, y1 - 60, PODIUM_Z, rng.uniform(900, 1400), rng)
        for (px, py) in ((x0 + 900, y0 + 300), (x1 - 300, y1 - 900)):
            ctx.obox((px, py, PODIUM_Z + 200), (260, 60, 200), rng.uniform(0, 360), mats=M['concrete2']); SOLIDS.append((px - 200, py - 200, PODIUM_Z, px + 200, py + 200, PODIUM_Z + 400, False))
        return
    if kind == 'low':
        n = rng.randint(2, 4)
        for k in range(n):
            w, dd = rng.uniform(500, 700), rng.uniform(500, 700)
            px = rng.uniform(x0 + 40, x1 - 40 - w); py = rng.uniform(y0 + 40, y1 - 40 - dd)
            tower(ctx, px, py, px + w, py + dd, 0.0, rng.uniform(500, 900), rng, windows=rng.uniform() < 0.5)
        return
    # 'tall': one big tower + one or two smaller ones, all on a 200-u base slab
    ctx.box((x0, y0, -20, x1, y1, 200.0), dict(top=M['concrete_floor'], side=street_wall(cx, cy), bottom=M['concrete']))
    SOLIDS.append((x0, y0, 0, x1, y1, 200.0, True))
    w, dd = rng.uniform(800, 1100), rng.uniform(800, 1100)
    px = rng.uniform(x0 + 60, x1 - 60 - w); py = rng.uniform(y0 + 60, y1 - 60 - dd)
    tower(ctx, px, py, px + w, py + dd, 200.0, rng.uniform(1500, 2800), rng)
    for k in range(rng.randint(1, 3)):
        sw, sd = rng.uniform(380, 560), rng.uniform(380, 560)
        for _ in range(12):
            qx = rng.uniform(x0 + 40, x1 - 40 - sw); qy = rng.uniform(y0 + 40, y1 - 40 - sd)
            if qx + sw < px or qx > px + w or qy + sd < py or qy > py + dd:
                tower(ctx, qx, qy, qx + sw, qy + sd, 200.0, rng.uniform(600, 1300), rng); break


def highway(ctx, axis, at, cross=None):
    """elevated slab along x (axis 'x', at y = at) or along y, with pillars every 1200 and 26-degree ramps at both ends.
    cross: where the other highway's centre line meets this one (same deck height: a flat junction). The side barriers stop at the
    junction's corners with a corner post each; they used to run straight across the other road (skink52, 10 Nov 2026: "the side
    barriers of the roads cross over in an odd fashion at the joins"). The ramps carry barriers too, and both ends have posts."""
    L0, L1 = -3600.0, 3600.0
    z0, z1 = HIGHWAY_Z, HIGHWAY_Z + HW_T
    off = HW_W / 2 - 40                       # barrier centre line from the deck centre
    def bx(a0, a1, w0, w1, zb, zt, mat):      # a box given along-axis and across-axis ranges
        ctx.box((a0, w0, zb, a1, w1, zt) if axis == 'x' else (w0, a0, zb, w1, a1, zt), mat)
    bx(L0, L1, at - HW_W / 2, at + HW_W / 2, z0, z1, dict(top=M['asphalt2'], side=M['concrete'], bottom=M['concrete']))
    if axis == 'x':
        SOLIDS.append((L0, at - HW_W / 2, z0, L1, at + HW_W / 2, z1, True)); STRUCT.append((L0 - 1500, at - HW_W / 2, L1 + 1500, at + HW_W / 2))
    else:
        SOLIDS.append((at - HW_W / 2, L0, z0, at + HW_W / 2, L1, z1, True)); STRUCT.append((at - HW_W / 2, L0 - 1500, at + HW_W / 2, L1 + 1500))
    # barrier runs: the whole deck, minus the junction mouth
    runs, posts = [], [L0, L1]
    if cross is not None and L0 < cross < L1:
        runs = [(L0, cross - HW_W / 2), (cross + HW_W / 2, L1)]; posts += [cross - HW_W / 2, cross + HW_W / 2]
    else: runs = [(L0, L1)]
    for s in (-1, 1):
        w = at + s * off
        for a0, a1 in runs:
            bx(a0, a1, w - 40, w + 40, z1, z1 + 120, M['concrete2'])
            bx(a0, a1, w - 48, w + 48, z1 + 120, z1 + 132, M['concrete'])            # a coping on the barrier
        for q in posts:                       # end and junction-corner posts
            bx(q - 60, q + 60, w - 60, w + 60, z1, z1 + 170, M['concrete2'])
    for q in np.arange(L0 + 600, L1, 1200.0):
        if axis == 'y' and abs(q) < 2400: continue      # the N-S highway crosses the E-W one: no pillar in the crossing avenue
        bx(q - 110, q + 110, at - 110, at + 110, -20, z0, M['concrete'])
        bx(q - 150, q + 150, at - HW_W / 2 + 40, at + HW_W / 2 - 40, z0 - 60, z0, M['concrete'])   # a pillar head under the deck
        SOLIDS.append((q - 110, at - 110, 0, q + 110, at + 110, z0, False) if axis == 'x' else (at - 110, q - 110, 0, at + 110, q + 110, z0, False))
    ang = math.radians(26.0)
    run = HIGHWAY_Z / math.tan(ang); L = math.hypot(run, HIGHWAY_Z)
    for e in (-1, 1):
        end = L1 if e > 0 else L0
        mid_t = (end + e * run / 2, at, HIGHWAY_Z / 2 - HW_T / 2)
        c = (mid_t[0], mid_t[1], mid_t[2]) if axis == 'x' else (at, mid_t[0], mid_t[2])
        ctx.obox(c, (L / 2 + 20, HW_W / 2, HW_T / 2), 0.0 if axis == 'x' else 90.0, 26.0 * e, mats=dict(top=M['asphalt2'], side=M['concrete'], bottom=M['concrete']))
        # the ramp's side barriers: the same box as the deck's, laid on the ramp (its centre lifted along the ramp's normal)
        d = HW_T / 2 + 60
        for s in (-1, 1):
            along, zc, w = mid_t[0] + e * math.sin(ang) * d, mid_t[2] + math.cos(ang) * d, at + s * off
            ctx.obox((along, w, zc) if axis == 'x' else (w, along, zc), (L / 2 - 30, 40, 60), 0.0 if axis == 'x' else 90.0, 26.0 * e, mats=M['concrete2'])
        for k in range(5):
            a, b = sorted((end + e * run * k / 5, end + e * run * (k + 1) / 5)); zt = HIGHWAY_Z * (1 - (k + 0.5) / 5)
            SOLIDS.append((a, at - HW_W / 2, 0, b, at + HW_W / 2, zt, True) if axis == 'x' else (at - HW_W / 2, a, 0, at + HW_W / 2, b, zt, True))


def plaza(ctx):
    h = PLAZA_H
    # the broadcast arch's four legs (tools/arenas/sprawl_detail.py: solid bars out of the water at (+-700, +-700), leaning in): the AI's
    # nav grid has to know them (11 Nov 2026: they were solid in the map only, so a bot could walk into one)
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        cx, cy = 680.0 * sx, 680.0 * sy
        SOLIDS.append((cx - 120, cy - 120, PLAZA_Z - 8, cx + 120, cy + 120, 460.0, False))
    # water sheet (depth 5) over the sunken plaza, a concrete dais in the middle for point B, broken pillars round the rim
    ctx.water((-h + 60, -h + 60, WATER_Z - 5, h - 60, h - 60, WATER_Z))
    ctx.box((-340, -340, PLAZA_Z - 10, 340, 340, 40.0), dict(top=M['concrete_floor'], side=M['concrete2'], bottom=M['concrete']))
    SOLIDS.append((-340, -340, PLAZA_Z, 340, 340, 40.0, True))
    for (px, py) in ((-1400, -1400), (1400, -1400), (-1400, 1400), (1400, 1400), (0, -1500), (0, 1500), (-1500, 0), (1500, 0)):
        ctx.box((px - 90, py - 90, PLAZA_Z - 10, px + 90, py + 90, 420.0), M['concrete']); SOLIDS.append((px - 90, py - 90, PLAZA_Z, px + 90, py + 90, 420.0, False))
    for k, col in enumerate(('255 60 200', '60 220 255', '255 160 60', '60 220 255')):
        a = math.radians(45 + k * 90); ctx.lamp((1000 * math.cos(a), 1000 * math.sin(a), 520), 70000, 1700, col, shadows=(k < 3))
    STRUCT.append((-h, -h, h, h))


def material(cx, cy):
    if max(abs(cx), abs(cy)) < PLAZA_H: return M['concrete_dark']
    dx = min(abs(cx - c) for c in CENTRES); dy = min(abs(cy - c) for c in CENTRES)
    return M['asphalt'] if (dx > BLOCK / 2 or dy > BLOCK / 2) else M['concrete_floor']


def radar_zones(X, Y, Z):
    col = np.full(X.shape + (3,), 0.22)
    dx = np.min(np.abs(X[..., None] - np.array(CENTRES)), -1); dy = np.min(np.abs(Y[..., None] - np.array(CENTRES)), -1)
    blockish = ((dx <= BLOCK / 2) & (dy <= BLOCK / 2))[..., None]
    col = np.where(blockish, np.array([0.38, 0.36, 0.40]), col)
    water = (np.maximum(np.abs(X), np.abs(Y)) < PLAZA_H - 60)[..., None]
    col = np.where(water, np.array([0.15, 0.25, 0.38]), col)
    high = (Z > 300)[..., None]
    col = np.where(high, np.array([0.55, 0.5, 0.58]), col)
    return col


def build(ctx):
    rng = np.random.RandomState(12)
    T = G.Terrain(height, -HALF, -HALF, HALF, HALF, tile=512, res=lambda cx, cy: 256 if max(abs(cx), abs(cy)) < 2600 else 512)
    nq = T.build(material, group=ctx.group)
    print('sprawl ground: %d tiles, %d quads' % (len(T.tiles), nq))
    plaza(ctx)
    for cx in CENTRES:
        for cy in CENTRES:
            if abs(cx) < 2000 and abs(cy) < 2000: continue
            if (cx, cy) in (A_POS, C_POS): block(ctx, cx, cy, rng, 'podium'); continue
            ring = max(abs(cx), abs(cy))
            kind = 'tall' if (ring < 5000 and rng.uniform() < 0.65) or (ring > 5000 and rng.uniform() < 0.3) else 'low'
            block(ctx, cx, cy, rng, kind)
    highway(ctx, 'x', 2400.0, cross=-2400.0); highway(ctx, 'y', -2400.0, cross=2400.0)
    # street lights at avenue crossings (unshadowed, capped range) and neon accents on tower bases
    for cx in (-4800.0, -2400.0, 0.0, 2400.0, 4800.0):
        for cy in (-4800.0, -2400.0, 0.0, 2400.0, 4800.0):
            if abs(cx) < 2000 and abs(cy) < 2000: continue
            ctx.lamp((cx, cy, 520), 30000, 1300, '255 225 190'); PLAN['lamps'].append([cx, cy])
    neon = ('255 60 200', '60 220 255', '255 160 60', '120 255 120')
    for k in range(20):
        cx = CENTRES[rng.randint(len(CENTRES))]; cy = CENTRES[rng.randint(len(CENTRES))]
        if abs(cx) < 2000 and abs(cy) < 2000: continue
        side = rng.randint(4); off = BLOCK / 2 + 120
        pos = ((cx + off, cy + rng.uniform(-600, 600)), (cx - off, cy + rng.uniform(-600, 600)), (cx + rng.uniform(-600, 600), cy + off), (cx + rng.uniform(-600, 600), cy - off))[side]
        lz, lc = rng.uniform(200, 700), neon[rng.randint(4)]
        ctx.lamp((pos[0], pos[1], lz), 25000, 900, lc, baked_only=True)
        PLAN['neon'].append(dict(pos=[pos[0], pos[1], lz], color=lc, block=[cx, cy], side=int(side)))
    # scattered containers and junk at mech scale in the avenues
    for k in range(30):
        cx = CENTRES[rng.randint(len(CENTRES))] + rng.choice([-1, 1]) * (BLOCK / 2 + (340 if CITY else 260)); cy = rng.uniform(-PLAY + 600, PLAY - 600)   # ops: clear of the kerb
        if abs(cx) < 2200 and abs(cy) < 2200: continue
        if abs(cy - 2400) < 500 and abs(cx) < 5100: continue
        if CITY and min(abs(cy - (a + b) / 2) for a, b in zip([CENTRES[0] - PITCH] + CENTRES, CENTRES + [CENTRES[-1] + PITCH])) < 700: continue   # not across a crossing
        yaw = rng.uniform(80, 100)
        if CITY: yaw -= 90.0                  # the container's long side (288 x 2.4 = 690 u) along the avenue, not across the kerbs
        ctx.prop(P['container'], (cx, cy, height(np.array([cx]), np.array([cy]))[0] + (2 if CITY else -6)), yaw, 2.4); PLAN['containers'].append([cx, cy, yaw])
        SOLIDS.append((cx - 200, cy - 400, 0, cx + 200, cy + 400, 340, False))
    def drops(x, n=8):
        return [(x, -3500 + i * 7000.0 / (n - 1), 1500.0, 0.0 if x < 0 else 180.0) for i in range(n)]
    ffa = [(x, y, 1500.0, (math.degrees(math.atan2(-y, -x))) % 360) for (x, y) in ((2400, 2400), (-2400, 2400), (2400, -2400), (-2400, -2400), (0, 4800), (0, -4800), (4800, 0), (-4800, 0))]
    if CITY:
        PLAN.update(centres=CENTRES, block=BLOCK, avenue=AVENUE, plaza=PLAZA_H, highways=[['x', 2400.0], ['y', -2400.0]], highway_z=HIGHWAY_Z + HW_T,
                    hw_w=HW_W, play=PLAY, half=HALF, points=dict(A=[A_POS[0], A_POS[1], PODIUM_Z], B=[0.0, 0.0, 40.0], C=[C_POS[0], C_POS[1], PODIUM_Z]))
        gen = os.path.join(ctx.out, '_gen'); os.makedirs(gen, exist_ok=True)
        json.dump(PLAN, open(os.path.join(gen, 'sprawl_plan.json'), 'w'), indent=1)
        print('sprawl plan: %d towers, %d neon spots, %d lamps -> _gen/sprawl_plan.json (city: tools/arenas/sprawl_ops.py)' % (len(PLAN['towers']), len(PLAN['neon']), len(PLAN['lamps'])))
    A = dict(
        bounds=((-PLAY, -PLAY, -100.0), (PLAY, PLAY, 5000.0)), ground=ground, solid=solid, struct=list(STRUCT), walk_ok=walk_ok,
        points=[('A', (A_POS[0], A_POS[1], PODIUM_Z), 700), ('B', (0.0, 0.0, 40.0), 700), ('C', (C_POS[0], C_POS[1], PODIUM_Z), 700)],
        drops=dict(t=drops(-4800.0), ct=drops(4800.0), ffa=ffa),
        landmarks=[('Plaza', (0.0, 0.0, 40.0)), ('Podium A', (A_POS[0], A_POS[1], PODIUM_Z)), ('Podium C', (C_POS[0], C_POS[1], PODIUM_Z)),
                   ('Highway East-West', (0.0, 2400.0, HIGHWAY_Z + HW_T)), ('Highway North-South', (-2400.0, 0.0, HIGHWAY_Z + HW_T)),
                   ('West Avenue', (-4800.0, 0.0, 0.0)), ('East Avenue', (4800.0, 0.0, 0.0))],
        env=dict(sun_angles=(62.0, 300.0, 0.0), sun_color='110 125 170', sun_brightness=0.35, sky_color='40 36 60', sky_intensity=0.55, sun_fog=0.9,
                 sky_tint='255 255 255', sky_brightness=1.0, exposure=(0.9, 2.6), post='postprocess/ifr_sprawl.vpost', ambient=(2600, '220 220 255'), sun_diameter=0.3,
                 fog=dict(cubemapfogstartdistance=300, cubemapfogenddistance=7000, cubemapfogheightstart=0.0, cubemapfogheightend=1800.0, cubemapfogmaxopacity=0.9, cubemapfogfalloffexponent=1.4),
                 vfog=dict(FogStrength=0.9, TintColor='120 110 150', NoiseStrength=0.7, DrawDistance=1400)),
        shell=(-HALF, -HALF, -1024.0, HALF, HALF, 6144.0), play=(-HALF, -HALF, -100.0, HALF, HALF, 5000.0), ground_probe_top=1200.0,
        hints=[((-6900.0, -6900.0, -100.0, 6900.0, 6900.0, 1800.0), 'Lower')], lmres='terrain', radar_zones=radar_zones, terrain=T)
    return A
