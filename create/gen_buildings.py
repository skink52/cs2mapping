"""Buildings and street fronts from primitives + CSG: hollow shells with floors, window and door openings (glass, sills, frames), flat roofs
with parapets or gable roofs, rows of varied houses along a street line, and cheap closed "district" blocks for the far parts of big maps.

  b = building((x0, y0, x1, y1), floors=2, style='plaster', front='-y', windows=3, door=True, roof='flat' | 'gable', seed=1)
      -> {'shapes': [(name, shape)], 'door': [x, y, z] (outside the door), 'top': z}
  row = street_front(start_xy, end_xy, depth=384, side='left', min_width=256, max_width=448, floors=(2, 4), styles=None, seed=1)
  blocks = district((x0, y0, x1, y1), block=512, street=192, floors=(2, 6), seed=1)   closed boxes, no interiors (backdrops)
  write(result, group)  -> CMapMesh nodes (vmaplib map open)
Styles (STYLES): plaster, brick, concrete, wood; each a set of materials (stock CS2 paths) and trim sizes. Add your own dict.

Ported from buildings.py / facades.py / districts.py in cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT): houses with depth,
facade rows and cheap districts. Their data-heavy Inferno look (facade kits, arcades, loggias, wear decals, 60 KB of facade rules) is
not ported: the styles here are a small set; the kit placement for real facade parts is gen_kits.py.
"""
import math, random
import primitives as P, meshedit as M

# every material here was checked to exist in CS2's pak01 (csgo or core) on 10 Nov 2026 (test_generators.py checks again where CS2 is installed)
_GLASS, _FLOOR, _FRAME = 'materials/cs_office/cs_office_glass_01.vmat', 'materials/concrete/concrete_floor_04.vmat', 'materials/dev/reflectivity_10.vmat'
STYLES = {
    'plaster':  {'wall': 'materials/de_inferno/plaster/infern_plaster_07b_base.vmat', 'trim': 'materials/cs_italy/trim/terracotta_trim_blend_01.vmat',
                 'roof': 'materials/shared_base/roofing/shifer_corrugated_roof_tile_001.vmat', 'glass': _GLASS, 'floor': _FLOOR, 'frame': _FRAME},
    'brick':    {'wall': 'materials/de_train/train_brick_wall_01.vmat', 'trim': _FLOOR,
                 'roof': 'materials/shared_base/roofing/shifer_corrugated_roof_tile_001.vmat', 'glass': _GLASS, 'floor': _FLOOR, 'frame': _FRAME},
    'concrete': {'wall': 'materials/concrete/hr_c/hr_concrete_wall_004.vmat', 'trim': _FLOOR, 'roof': _FLOOR, 'glass': _GLASS, 'floor': _FLOOR,
                 'frame': _FRAME},
    'wood':     {'wall': 'materials/anubis/anubis_wood_planks01.vmat', 'trim': 'materials/dev/reflectivity_70.vmat',
                 'roof': 'materials/shared_base/roofing/shifer_corrugated_roof_tile_001.vmat', 'glass': _GLASS, 'floor': _FLOOR, 'frame': _FRAME},
}
FRONTS = {'-y': (1, -1), '+y': (1, 1), '-x': (0, -1), '+x': (0, 1)}      # (axis of the facade's normal, sign)


def building(fp, floors=2, floor_h=128.0, wall=12.0, style='plaster', front='-y', windows=3, window=(48.0, 64.0), sill=36.0,
             door=True, door_size=(64.0, 104.0), roof='flat', parapet=24.0, interior_floors=True, seed=1, all_sides=True):
    st = STYLES[style] if isinstance(style, str) else style
    x0, y0, x1, y1 = [float(v) for v in fp]
    H = floors * floor_h
    rnd = random.Random(seed)
    shell = M.subtract(P.box((x0, y0, 0), (x1, y1, H), st['wall']), P.box((x0 + wall, y0 + wall, -1), (x1 - wall, y1 - wall, H + 1), st['wall']))
    extras = []
    cuts = []
    sides = [front] + ([s for s in FRONTS if s != front] if all_sides else [])
    door_at = None
    for side in sides:
        ax, sg = FRONTS[side]
        if ax == 1: c = y0 if sg < 0 else y1; lo, hi = x0, x1
        else: c = x0 if sg < 0 else x1; lo, hi = y0, y1
        span = hi - lo
        n = windows if side == front else max(1, int(windows * (span / max(1.0, (x1 - x0)))))
        n = max(0, min(n, int((span - wall * 2) // (window[0] + 24))))
        for f in range(floors):
            for k in range(n):
                u = lo + span * (k + 0.5) / n
                if f == 0 and side == front and door and k == n // 2: continue      # the door takes the middle bay
                zb = f * floor_h + sill
                cuts.append((ax, c, u, zb, window[0], window[1], 'window'))
        if side == front and door:
            u = lo + span * ((n // 2) + 0.5) / max(n, 1) if n else (lo + hi) / 2
            cuts.append((ax, c, u, 0.0, door_size[0], door_size[1], 'door'))
            out = 32.0 * sg
            door_at = [u, c + out, 0.0] if ax == 1 else [c + out, u, 0.0]
    for ax, c, u, zb, w, h, kind in cuts:
        if ax == 1: box = ((u - w / 2, c - wall * 2, zb), (u + w / 2, c + wall * 2, zb + h))
        else: box = ((c - wall * 2, u - w / 2, zb), (c + wall * 2, u + w / 2, zb + h))
        shell = M.subtract(shell, P.box(box[0], box[1], st['frame']))
        if kind == 'window':
            g = 1.0                                                   # glass pane in the middle of the wall, sill under it
            if ax == 1:
                mid = c + (wall / 2 if c == y0 else -wall / 2)
                extras.append(('glass', P.box((u - w / 2, mid - g / 2, zb), (u + w / 2, mid + g / 2, zb + h), st['glass'])))
                o = -1 if c == y0 else 1
                extras.append(('sill', P.box((u - w / 2 - 4, min(c, c + o * 6), zb - 4), (u + w / 2 + 4, max(c, c + o * 6), zb), st['trim'])))
            else:
                mid = c + (wall / 2 if c == x0 else -wall / 2)
                extras.append(('glass', P.box((mid - g / 2, u - w / 2, zb), (mid + g / 2, u + w / 2, zb + h), st['glass'])))
                o = -1 if c == x0 else 1
                extras.append(('sill', P.box((min(c, c + o * 6), u - w / 2 - 4, zb - 4), (max(c, c + o * 6), u + w / 2 + 4, zb), st['trim'])))
    shapes = [('shell', shell)] + extras
    if interior_floors:
        for f in range(1, floors):
            shapes.append(('floor%d' % f, P.box((x0 + wall, y0 + wall, f * floor_h - 8), (x1 - wall, y1 - wall, f * floor_h), st['floor'])))
    shapes.append(('ground_floor', P.box((x0 + wall, y0 + wall, -8), (x1 - wall, y1 - wall, 0), st['floor'])))
    top = H
    if roof == 'flat':
        shapes.append(('roof', P.box((x0, y0, H), (x1, y1, H + 8), st['roof'])))
        if parapet:
            ring = M.subtract(P.box((x0, y0, H + 8), (x1, y1, H + 8 + parapet), st['trim']), P.box((x0 + 8, y0 + 8, H + 7), (x1 - 8, y1 - 8, H + 9 + parapet), st['trim']))
            shapes.append(('parapet', ring))
        top = H + 8 + parapet
    elif roof == 'gable':
        rise = min(x1 - x0, y1 - y0) * 0.35
        if (x1 - x0) >= (y1 - y0):                                     # ridge along x
            prof = [(y0 - 12, H), (y1 + 12, H), ((y0 + y1) / 2, H + rise)]
            sh = P.extrude([(p[0], p[1]) for p in prof], (x1 - x0) + 24, 'yz', (x0 - 12, 0, 0), st['roof'])
        else:
            prof = [(x0 - 12, H), (x1 + 12, H), ((x0 + x1) / 2, H + rise)]
            sh = P.extrude(prof, (y1 - y0) + 24, 'xz', (0, y0 - 12, 0), st['roof'])
        shapes.append(('roof', sh)); shapes.append(('ceiling', P.box((x0, y0, H), (x1, y1, H + 8), st['floor'])))
        top = H + rise
    else:
        raise ValueError('roof: flat or gable')
    return {'shapes': shapes, 'door': door_at, 'top': top, 'footprint': [x0, y0, x1, y1]}


def street_front(start, end, depth=384.0, side='left', min_width=256.0, max_width=448.0, floors=(2, 4), styles=None, seed=1, **kw):
    """houses side by side along the line start -> end (axis-aligned lines), fronts facing the line; -> list of building() results"""
    rnd = random.Random(seed)
    styles = styles or list(STYLES)
    (sx, sy), (ex, ey) = start, end
    along_x = abs(ex - sx) >= abs(ey - sy)
    if along_x and abs(ey - sy) > 1e-6 or (not along_x and abs(ex - sx) > 1e-6): raise ValueError('street_front takes an axis-aligned line')
    a0, a1 = (min(sx, ex), max(sx, ex)) if along_x else (min(sy, ey), max(sy, ey))
    c = sy if along_x else sx
    left = side == 'left'
    out = []; u = a0
    while a1 - u >= min_width:
        w = min(rnd.uniform(min_width, max_width), a1 - u)
        if a1 - (u + w) < min_width: w = a1 - u
        if along_x:
            fp = (u, c, u + w, c + depth) if left else (u, c - depth, u + w, c)
            front = '-y' if left else '+y'
        else:
            fp = (c - depth, u, c, u + w) if left else (c, u, c + depth, u + w)
            front = '+x' if left else '-x'
        out.append(building(fp, rnd.randint(*floors), style=rnd.choice(styles), front=front, windows=max(1, int(w // 128)),
                            roof=rnd.choice(['flat', 'flat', 'gable']), seed=rnd.randint(0, 10 ** 6), **kw))
        u += w
    return out


def district(area, block=512.0, street=192.0, floors=(2, 6), floor_h=128.0, seed=1, style='concrete'):
    """closed boxes on a street grid (no interiors, no openings): cheap far-away town for big maps; -> list of shapes"""
    rnd = random.Random(seed)
    x0, y0, x1, y1 = area
    st = STYLES[style] if isinstance(style, str) else style
    out = []
    x = x0
    while x + block <= x1 + 1e-6:
        y = y0
        while y + block <= y1 + 1e-6:
            n = rnd.randint(1, 3)                                    # split a block into 1-3 buildings of different heights
            cuts = sorted(rnd.uniform(0.3, 0.7) * block for _ in range(n - 1))
            edges = [0.0] + cuts + [block]
            for i in range(n):
                h = rnd.randint(*floors) * floor_h
                out.append(('block', P.box((x + edges[i], y, 0), (x + edges[i + 1], y + block, h), st['wall'])))
                out.append(('block_roof', P.box((x + edges[i], y, h), (x + edges[i + 1], y + block, h + 8), st['roof'])))
            y += block + street
        x += block + street
    return out


def write(result, group='buildings'):
    items = result if isinstance(result, list) else [result]
    nodes = []
    for it in items:
        shapes = it['shapes'] if isinstance(it, dict) else [it]
        for _, s in shapes: nodes.append(P.add(s, group))
    return nodes
