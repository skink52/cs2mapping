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
HIGHWAY_Z = 700.0; HW_T = 60.0; HW_W = 900.0   # 900: the avenue's width, so each end splits into two lanes with the street between
LANE_IN = 150.0          # the split ramps (skink52, 12 Nov 2026: one embankment over the whole avenue "removed playable area"): an off
                         # lane and an on lane from |t| = LANE_IN to HW_W / 2, the street running on between them (300 u) and under them
                         # where they are high (viaduct on columns), an embankment only where a mech could not stand under them
UNDER_CLEAR = 400.0      # the lowest underside a mech walks under (heavy frames 336 u)
SHELL_H = 7424.0         # sky shell half-size: the playable city (PLAY 5200) plus a ring of outer blocks and the quarantine wall behind them
EDGE_C = 6000.0          # the outer blocks' centres (the grid's next row); WALL_IN: the wall's inner face
WALL_IN, WALL_H = 7150.0, 1900.0
HW_END = 2860.0          # the decks run +-HW_END: just past the avenue crossing at 2400 (1950-2850)
HW_FOOT = 4335.0         # where the ramps reach the ground: the kerb of the outer ring road (4350-5250), not across it
HW_PIERS = [-1800.0, -600.0, 600.0, 1800.0]      # in the avenue under the deck, clear of every crossing
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


def tower(ctx, x0, y0, x1, y1, z0, h, rng, windows=True, edge=False):
    """edge: an outer-ring tower (outside the play bounds: no nav solid, no structure entry; the city layer never ruins it)"""
    top = z0 + h
    lit = bool(windows and rng.uniform() < 0.8)
    side = M['windows_lit'] if lit else M['windows']
    rec = dict(box=[x0, y0, z0, x1, y1, top], lit=lit, walk_roof=h <= 900.0, roof_box=None, seed=int(rng.randint(1 << 30)))
    if edge: rec['edge'] = True
    if not CITY: ctx.box((x0, y0, z0 - 20, x1, y1, top), dict(top=M['concrete_dark'], side=side, bottom=M['concrete']))
    if not edge: SOLIDS.append((x0, y0, z0, x1, y1, top, h <= 900.0))
    # parapets (200 tall, 80 thick) and a roof box
    t = 80.0
    if not CITY:
        for b in ((x0, y0, top, x1, y0 + t, top + 200), (x0, y1 - t, top, x1, y1, top + 200), (x0, y0, top, x0 + t, y1, top + 200), (x1 - t, y0, top, x1, y1, top + 200)):
            ctx.box(b, M['concrete2'])
    if (x1 - x0) > 700 and rng.uniform() < 0.7:
        rx, ry = rng.uniform(x0 + 200, x1 - 400), rng.uniform(y0 + 200, y1 - 400)
        if not CITY: ctx.box((rx, ry, top, rx + 240, ry + 200, top + 260), dict(top=M['roof_metal'], side=M['concrete2']))
        rec['roof_box'] = [rx, ry, top, rx + 240, ry + 200, top + 260]
        if h <= 900.0 and not edge: SOLIDS.append((rx, ry, top, rx + 240, ry + 200, top + 260, False))
    PLAN['towers'].append(rec)
    if not edge: STRUCT.append((x0, y0, x1, y1))
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


def sign_mount(cx, cy, side, along, lz):
    """where a neon blade sign hangs: on the face of a real tower of block (cx, cy) that looks out on the `side` (0 +x, 1 -x, 2 +y,
    3 -y) street, within 420 u of the block edge. They used to hang at the block edge whatever stood there, so over a low block's
    car park or a set-back tower they floated in the air with a bracket to nothing. Returns ((x, y, z) of the blade's centre, the
    face coordinate) or None. The blade's bottom stays above the street band and canopy (z0 + 300) and its top under the roof."""
    best = None
    for t in PLAN['towers']:
        x0, y0, z0, x1, y1, top = t['box']
        if abs((x0 + x1) / 2 - cx) > BLOCK / 2 or abs((y0 + y1) / 2 - cy) > BLOCK / 2: continue
        face = (x1, x0, y1, y0)[side]; edge = (cx + BLOCK / 2, cx - BLOCK / 2, cy + BLOCK / 2, cy - BLOCK / 2)[side]
        lo, hi = (y0, y1) if side < 2 else (x0, x1)
        z = max(lz, z0 + 560.0)
        if abs(edge - face) > 420 or hi - lo < 300 or z + 300 > top: continue
        if best is None or abs(edge - face) < best[0]: best = (abs(edge - face), face, lo, hi, z)
    if not best: return None
    _, face, lo, hi, z = best
    a = min(max(along, lo + 130), hi - 130); out = face + (1, -1, 1, -1)[side] * 90       # the blade's middle, 90 u out from the wall
    return ((out, a, z) if side < 2 else (a, out, z)), face


def edge_block(ctx, cx, cy, rng):
    """an outer-ring block (skink52, 12 Nov 2026: past the ring road there was bare ground and then the sky shell). The city goes on:
    a 200-u street-wall slab like a tall block's, a row of towers on the side facing the arena (gaps narrower than a tower, so
    the sky never shows through at street level) and a taller one set back behind them for a layered skyline. Outside PLAY: no
    nav solids. The city layer builds them like any tower (facades, storefronts, crowns), never as ruins."""
    x0, y0, x1, y1 = cx - BLOCK / 2, cy - BLOCK / 2, cx + BLOCK / 2, cy + BLOCK / 2
    ctx.box((x0, y0, -20, x1, y1, 200.0), dict(top=M['concrete_floor'], side=street_wall(cx, cy), bottom=M['concrete']))
    if CITY: PLAN.setdefault('blocks', []).append(dict(centre=[cx, cy], kind='edge'))
    corner = abs(cx) > 5000 and abs(cy) > 5000
    if corner:                                    # one broad tower over the whole block
        tower(ctx, x0 + 60, y0 + 60, x1 - 60, y1 - 60, 200.0, rng.uniform(1800, 2600), rng, edge=True)
        return
    along_x = abs(cy) > 5000                      # the row runs along x on the north / south sides
    inward = -1.0 if (cy if along_x else cx) > 0 else 1.0
    face = (cy if along_x else cx) + inward * (BLOCK / 2 - 50)       # the row's front line, 50 u back from the block edge
    a = -BLOCK / 2 + 50
    while a < BLOCK / 2 - 300:
        w = min(rng.uniform(420, 640), BLOCK / 2 - 50 - a)
        d = rng.uniform(560, 820); h = rng.uniform(1300, 2700)
        lo, hi = sorted((face, face - inward * d))
        if along_x: tower(ctx, cx + a, lo, cx + a + w, hi, 200.0, h, rng, edge=True)
        else: tower(ctx, lo, cy + a, hi, cy + a + w, 200.0, h, rng, edge=True)
        a += w + rng.uniform(60, 140)
    back = (cy if along_x else cx) - inward * (BLOCK / 2 - 60)
    lo, hi = sorted((back, back + inward * 520)); s0, s1 = rng.uniform(-600, -200), rng.uniform(200, 600)
    if along_x: tower(ctx, cx + s0, lo, cx + s1, hi, 200.0, rng.uniform(2800, 3900), rng, edge=True)
    else: tower(ctx, lo, cy + s0, hi, cy + s1, 200.0, rng.uniform(2800, 3900), rng, edge=True)


def outer_ring(ctx):
    """everything between the play bounds and the sky shell: the ground (the terrain stops at HALF), the outer blocks, a
    concrete barricade across every street that leaves the ring road (with floodlights), and the quarantine wall: a 1900-u
    flood / quarantine wall round the whole city behind the outer blocks, seen down the barricaded streets and over the lower
    roofs, with buttresses, a lit walkway lip and red warning lamps. It closes every sight line before the sky shell does."""
    rng = np.random.RandomState(77)              # its own stream: the arena's own layout keeps its random draws
    S, H = SHELL_H, HALF
    for (x0, y0, x1, y1) in ((-S, H, S, S), (-S, -S, S, -H), (H, -H, S, H), (-S, -H, -H, H)):     # the ground band round the terrain
        ctx.box((x0, y0, -40, x1, y1, 0.0), dict(top=M['asphalt'], side=M['concrete'], bottom=M['concrete']))
    lines = [-EDGE_C, -3600.0, -1200.0, 1200.0, 3600.0, EDGE_C]
    for cx in lines:
        for cy in lines:
            if max(abs(cx), abs(cy)) == EDGE_C: edge_block(ctx, cx, cy, rng)
    # the barricades: a line of precast concrete T-wall sections across each street that leaves the ring (x or y = +-2400, 0,
    # +-4800), just past the kerb: 120-u sections 230 tall on a footing, set by hand (a little out of line and turned), one missing
    out = 5420.0
    for street in (-4800.0, -2400.0, 0.0, 2400.0, 4800.0):
        for side in (-1, 1):
            for axis in 'xy':
                # axis 'x': the street runs along x at y = street and leaves the ring on the east / west (x = side * out)
                gap = rng.randint(1, 6)
                for i in range(7):
                    across = -AVENUE / 2 + 30 + 120 * i + 60
                    if i == gap and rng.uniform() < 0.5: continue
                    a = side * (out + rng.uniform(-10, 10)); t = street + across
                    yaw = (0.0 if axis == 'x' else 90.0) + rng.uniform(-4, 4)            # local x: through the wall, y: along it
                    cx_, cy_ = (a, t) if axis == 'x' else (t, a)
                    ctx.obox((cx_, cy_, 12), (40, 58, 14), yaw, mats=M['concrete'])                                  # the footing
                    ctx.obox((cx_, cy_, 26 + 102), (11, 58, 102), yaw, mats=dict(top=M['concrete2'], side=M['concrete2'], bottom=M['concrete']))
                for k, t in enumerate((-AVENUE / 2 + 40, AVENUE / 2 - 40)):          # a floodlight mast at each end, aimed at the ring road
                    a = side * (out + 150); x, y = (a, street + t) if axis == 'x' else (street + t, a)
                    ctx.box((x - 14, y - 14, 0, x + 14, y + 14, 620), M['metal_trim'])
                    lx, ly = (a - side * 60, street + t) if axis == 'x' else (street + t, a - side * 60)
                    ctx.box((min(x, lx) - 30, min(y, ly) - 30, 600, max(x, lx) + 30, max(y, ly) + 30, 640), dict(top=M['metal_trim'], side=M['metal_trim'], bottom=M['window_glass_lit']))
                    if k == 0: ctx.lamp((lx, ly, 560), 22000, 1100, '255 236 200', baked_only=True)
    # the quarantine wall
    for (x0, y0, x1, y1) in ((-S, WALL_IN, S, WALL_IN + 220), (-S, -WALL_IN - 220, S, -WALL_IN), (WALL_IN, -WALL_IN, WALL_IN + 220, WALL_IN), (-WALL_IN - 220, -WALL_IN, -WALL_IN, WALL_IN)):
        ctx.box((x0, y0, -20, x1, y1, WALL_H), dict(top=M['concrete_dark'], side=M['concrete'], bottom=M['concrete']))
    for zb in (380.0, 760.0, 1140.0, 1520.0):                             # cast-in courses: the wall's scale reads at a glance
        for (x0, y0, x1, y1) in ((-WALL_IN, WALL_IN - 22, WALL_IN, WALL_IN), (-WALL_IN, -WALL_IN, WALL_IN, -WALL_IN + 22),
                                 (WALL_IN - 22, -WALL_IN, WALL_IN, WALL_IN), (-WALL_IN, -WALL_IN, -WALL_IN + 22, WALL_IN)):
            ctx.box((x0, y0, zb, x1, y1, zb + 16), M['concrete2'])
    PLAN['wall'] = dict(inner=WALL_IN, h=WALL_H, streets=[-4800.0, -2400.0, 0.0, 2400.0, 4800.0])
    for k in range(-9, 10):
        q = k * 780.0
        board = min(abs(q - c) for c in PLAN['wall']['streets']) < 580     # a street end: its board hangs there (sprawl_ops wall_ops), no buttress
        for nx, ny in ((0, -1), (0, 1), (-1, 0), (1, 0)):                # buttresses on the inner face, a lit lip on top, warning lamps
            if ny: x, y = q, ny * WALL_IN
            else: x, y = nx * WALL_IN, q
            ax, ay = (60, 0) if ny else (0, 60)
            inx, iny = -nx * 110, -ny * 110
            if not board: ctx.box((min(x - ax, x - ax + inx), min(y - ay, y - ay + iny), -20, max(x + ax, x + ax + inx), max(y + ay, y + ay + iny), WALL_H - 160), M['concrete2'])
            lx0, ly0 = (x - 390, y + (-ny) * 40) if ny else (x + (-nx) * 40, y - 390)
            lx1, ly1 = (x + 390, y) if ny else (x, y + 390)
            ctx.box((min(lx0, lx1), min(ly0, ly1), WALL_H - 40, max(lx0, lx1), max(ly0, ly1), WALL_H - 28), dict(top=M['metal_trim'], side=M['metal_trim'], bottom=M['window_glass_lit']))
            if k % 3 == 0:                                               # a lamp housing on the wall top, 60 u in from the inner edge
                hx, hy = (x, y + ny * 60) if ny else (x + nx * 60, y)
                ctx.box((hx - 16, hy - 16, WALL_H, hx + 16, hy + 16, WALL_H + 40), M['window_glass_lit'])


def highway(ctx, axis, at, cross=None):
    """elevated slab along x (axis 'x', at y = at) or along y, on the HW_PIERS pillars, with ramps at both ends down to HW_FOOT.
    cross: where the other highway's centre line meets this one (same deck height: a flat junction). The side barriers stop at the
    junction's corners with a corner post each; they used to run straight across the other road (skink52, 10 Nov 2026: "the side
    barriers of the roads cross over in an odd fashion at the joins"). The ramps carry barriers too, and both ends have posts."""
    L0, L1 = -HW_END, HW_END
    z0, z1 = HIGHWAY_Z, HIGHWAY_Z + HW_T
    off = HW_W / 2 - 20                       # barrier centre line from the deck centre (40 thick: the ramp lanes' outer barrier lines up)
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
            bx(a0, a1, w - 20, w + 20, z1, z1 + 120, M['concrete2'])
            bx(a0, a1, w - 26, w + 26, z1 + 120, z1 + 132, M['concrete'])            # a coping on the barrier
        for q in posts:                       # end and junction-corner posts
            bx(q - 50, q + 50, w - 30, w + 20, z1, z1 + 170, M['concrete2']) if s > 0 else bx(q - 50, q + 50, w - 20, w + 30, z1, z1 + 170, M['concrete2'])
    for q in HW_PIERS:
        bx(q - 110, q + 110, at - 110, at + 110, -20, z0, M['concrete'])
        bx(q - 150, q + 150, at - HW_W / 2 + 40, at + HW_W / 2 - 40, z0 - 60, z0, M['concrete'])   # a pillar head under the deck
        SOLIDS.append((q - 110, at - 110, 0, q + 110, at + 110, z0, False) if axis == 'x' else (at - 110, q - 110, 0, at + 110, q + 110, z0, False))
    # the ramps (12 Nov 2026: split, see LANE_IN): from the deck's end down to the kerb of the outer ring road (HW_FOOT). They used to start at 3600 and come down at 5035,
    # right across that road at half height (skink52, 11 Nov 2026: "they ramp down halfway into the roads below"). The top surface runs
    # from the deck's top edge to the ground (it used to sit 57 u under the deck: a lip), and under it stands a stepped concrete
    # fill, so the ramp is an embankment and not a plank (the nav solids always said so: there was an unseen wall under it).
    run = HW_FOOT - L1; ang = math.atan2(z1, run); Lr = math.hypot(run, z1); deg = math.degrees(ang)
    sn, cs = math.sin(ang), math.cos(ang)
    tc, hw = (LANE_IN + HW_W / 2) / 2, (HW_W / 2 - LANE_IN) / 2           # a lane's centre line and half width (300, 150)
    under = lambda d: z1 * (1 - d / run) - HW_T / cs                       # the lane slab's underside, d along from the deck end
    d_open = run * (1 - (UNDER_CLEAR + HW_T / cs) / z1)                    # up to here a mech walks under the lane (viaduct)
    yaw = 0.0 if axis == 'x' else 90.0
    P3 = lambda a, t, z: (a, at + t, z) if axis == 'x' else (at + t, a, z)
    for e in (-1, 1):
        end = L1 if e > 0 else L0
        top_mid = (end + e * run / 2, z1 / 2)                               # (along, z) of a lane's top surface middle
        nrm = lambda k: (top_mid[0] + e * sn * k, top_mid[1] + cs * k)       # k u off the surface along its normal
        # the gore: a crash barrier across the deck's middle where the two lanes part (the street below shows through)
        g0, g1 = sorted((end - e * 46, end - e * 4))
        bx(g0, g1, at - LANE_IN - 8, at + LANE_IN + 8, z1, z1 + 112, M['concrete2'])
        bx(g0 - 3, g1 + 3, at - LANE_IN - 12, at + LANE_IN + 12, z1 + 112, z1 + 122, M['concrete'])
        for s in (-1, 1):
            ca, cz = nrm(-HW_T / 2)
            ctx.obox(P3(ca, s * tc, cz), (Lr / 2 + 6, hw, HW_T / 2), yaw, deg * e, mats=dict(top=M['asphalt2'], side=M['concrete'], bottom=M['concrete']))
            ba, bz = nrm(60)                                                # the outer barrier: concrete, flush with the deck's
            ctx.obox(P3(ba, s * off, bz), (Lr / 2 - 30, 20, 60), yaw, deg * e, mats=M['concrete2'])
            ra, rz = nrm(64)                                                # the inner side: a steel guard rail on posts
            ctx.obox(P3(ra, s * (LANE_IN + 8), rz), (Lr / 2 - 30, 4, 11), yaw, deg * e, mats=M['metal_trim'])
            d = 30.0
            while d < run - 40:
                a = end + e * d; zs = z1 * (1 - d / run)
                bx(a - 4, a + 4, at + s * (LANE_IN + 8) - 4, at + s * (LANE_IN + 8) + 4, zs - HW_T, zs + 70, M['metal_trim'])
                d += 170.0
            fa = end + e * (run - 40)                                       # low end blocks where the barrier and the rail meet the ground
            bx(min(fa, fa + e * 70), max(fa, fa + e * 70), at + s * off - 30, at + s * off + 30, -10, 96, M['concrete2'])
            bx(min(fa, fa + e * 40), max(fa, fa + e * 40), at + s * (LANE_IN + 8) - 14, at + s * (LANE_IN + 8) + 14, -10, 60, M['concrete2'])
            # where it is high: columns at the lane's outer edge under pitched cap beams (the street runs on underneath)
            for d in (run * 0.14, run * 0.33):
                if under(d) < UNDER_CLEAR + 60: continue
                a = end + e * d; zs = z1 * (1 - d / run)
                bc, bz2 = a - e * sn * (HW_T + 26), zs - cs * (HW_T + 26)
                ctx.obox(P3(bc, s * tc, bz2), (36, hw - 6, 26), yaw, deg * e, mats=M['concrete'])
                c0 = s * (HW_W / 2 - 46)
                bx(a - 34, a + 34, at + c0 - 34, at + c0 + 34, -10, bz2, M['concrete'])
            # where it is low: an embankment, a block laid parallel to the lane right under its slab from d_open to the foot, deep
            # enough to reach the ground at d_open (the rest of it is under the street). Steps left saw-tooth gaps under the slab.
            dep = (under(d_open) + 30.0) * cs                                # its thickness, square to the slope
            dm = (d_open + run) / 2; Le = (run - d_open) / 2 / cs + 4      # half its length along the slope
            zs_m = z1 * (1 - dm / run)
            ea, ez = end + e * dm - e * sn * (HW_T + dep / 2 - 1), zs_m - cs * (HW_T + dep / 2 - 1)
            ctx.obox(P3(ea, s * tc, ez), (Le, hw - 6, dep / 2), yaw, deg * e, mats=M['concrete'])
            for k in range(6):                                              # nav: the lane in steps (the street between stays ground)
                a, b = sorted((end + e * run * k / 6, end + e * run * (k + 1) / 6))
                zt = z1 * (1 - (k + 0.5) / 6)
                lo, hi = sorted((at + s * LANE_IN, at + s * HW_W / 2))
                SOLIDS.append((a, lo, 0, b, hi, zt, True) if axis == 'x' else (lo, a, 0, hi, b, zt, True))


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
    outer_ring(ctx)                              # before the signs: the outer blocks' fronts carry signs too (own random stream)
    def hang(cx, cy, side, along, lz, lc):
        mount = sign_mount(cx, cy, side, along, lz)
        if not mount: return False
        (sx, sy, sz), face = mount
        if any(math.hypot(sx - n['pos'][0], sy - n['pos'][1]) < 500 for n in PLAN['neon']): return False
        nx, ny = ((1, 0), (-1, 0), (0, 1), (0, -1))[side]
        ctx.lamp((sx + nx * 170, sy + ny * 170, sz), 25000, 900, lc, baked_only=True)      # in front of the blade, not inside it
        PLAN['neon'].append(dict(pos=[sx, sy, sz], color=lc, block=[cx, cy], side=int(side), face=face))
        return True
    for k in range(20):
        cx = CENTRES[rng.randint(len(CENTRES))]; cy = CENTRES[rng.randint(len(CENTRES))]
        if abs(cx) < 2000 and abs(cy) < 2000: continue
        side = rng.randint(4); off = BLOCK / 2 + 120
        pos = ((cx + off, cy + rng.uniform(-600, 600)), (cx - off, cy + rng.uniform(-600, 600)), (cx + rng.uniform(-600, 600), cy + off), (cx + rng.uniform(-600, 600), cy - off))[side]
        lz, lc = rng.uniform(200, 700), neon[rng.randint(4)]
        hang(cx, cy, side, pos[1] if side < 2 else pos[0], lz, lc)       # only on a wall (12 Nov 2026: "signs that float unnaturally")
    # topped up to 22 from a stream of their own (fewer spots have a wall), the outer blocks' fronts on the ring road included
    srng = np.random.RandomState(53); grid = [-EDGE_C] + CENTRES + [EDGE_C]
    for k in range(400):
        if len(PLAN['neon']) >= 22: break
        cx, cy = grid[srng.randint(len(grid))], grid[srng.randint(len(grid))]; side = srng.randint(4)
        if abs(cx) < 2000 and abs(cy) < 2000: continue
        if max(abs(cx), abs(cy)) == EDGE_C and side != ((0 if cx < 0 else 1) if abs(cx) == EDGE_C else (3 if cy > 0 else 2)): continue   # outer: the front only
        if abs(cx) == EDGE_C and abs(cy) == EDGE_C: continue
        hang(cx, cy, side, (cy if side < 2 else cx) + srng.uniform(-600, 600), srng.uniform(200, 900), neon[srng.randint(4)])
    # (the avenue containers are gone: skink52, 12 Nov 2026, "Containers can all be removed, we don't need them")
    def drops(x, n=8):
        return [(x, -3500 + i * 7000.0 / (n - 1), 1500.0, 0.0 if x < 0 else 180.0) for i in range(n)]
    ffa = [(x, y, 1500.0, (math.degrees(math.atan2(-y, -x))) % 360) for (x, y) in ((2400, 2400), (-2400, 2400), (2400, -2400), (-2400, -2400), (0, 4800), (0, -4800), (4800, 0), (-4800, 0))]
    if CITY:
        PLAN.update(centres=CENTRES, block=BLOCK, avenue=AVENUE, plaza=PLAZA_H, highways=[['x', 2400.0], ['y', -2400.0]], highway_z=HIGHWAY_Z + HW_T, hw_end=HW_END, hw_foot=HW_FOOT, hw_piers=HW_PIERS,
                    hw_w=HW_W, play=PLAY, half=WALL_IN, lane_in=LANE_IN, under_clear=UNDER_CLEAR, points=dict(A=[A_POS[0], A_POS[1], PODIUM_Z], B=[0.0, 0.0, 40.0], C=[C_POS[0], C_POS[1], PODIUM_Z]))
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
        shell=(-SHELL_H, -SHELL_H, -1024.0, SHELL_H, SHELL_H, 6144.0), play=(-HALF, -HALF, -100.0, HALF, HALF, 5000.0), ground_probe_top=1200.0,
        hints=[((-6900.0, -6900.0, -100.0, 6900.0, 6900.0, 1800.0), 'Lower')], lmres='terrain', radar_zones=radar_zones, terrain=T)
    return A
