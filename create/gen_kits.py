"""Kits of stock parts: place props by their real bounds against floors and walls, in rows and stacks, facing the way you want.

  kit = load('street_small')                 (create/kits/<name>.json, or a path); parts(kit, category=, mount=, tags=)
  place(part, at, normal=(0, 0, 1), facing=(1, 0, 0)) -> {model, origin, angles}
        floor parts stand on `at` facing `facing`; wall parts hang with their back on the wall at `at`, front along the wall `normal`
  row(part, start, end, gap=8, normal=..., facing=...) -> placements    as many as fit between start and end, evenly spaced
  stack(part, at, count=2, facing=...)       -> placements    one on top of the other (crates)
  measure(models) -> {model: bounds}          via tools/visualcheck.ModelBounds (Node + create/s2/bounds_batch.mjs), to add parts to a kit
  props(placements, group)                    prop_static entities in the vmaplib map
Part fields: key, model, category, mount (floor | wall | ceiling), front (+x | -x | +y | -y: the model's front axis), bounds, tags.

Ported from kits.py + data/kits/*.json in cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT): parts with mount, front and
bounds, placed against a surface. Their nine kits (Inferno / Mirage buildings, harbour, market, rocks, vegetation ...) are not copied:
create/kits/street_small.json is a small set measured here; measure() + a JSON file adds more.
"""
import json, math, os
import primitives as P

KITS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kits')
FRONT_YAW = {'+x': 0.0, '+y': 90.0, '-x': 180.0, '-y': 270.0}
FRONT_VEC = {'+x': (1, 0), '+y': (0, 1), '-x': (-1, 0), '-y': (0, -1)}


def load(name):
    path = name if os.path.isfile(name) else os.path.join(KITS, name + '.json')
    with open(path, encoding='utf-8') as f: kit = json.load(f)
    keys = [p['key'] for p in kit['parts']]
    if len(keys) != len(set(keys)): raise ValueError('duplicate part keys in %s' % path)
    for p in kit['parts']:
        if p.get('front', '+x') not in FRONT_YAW: raise ValueError('%s: front must be +x, -x, +y or -y' % p['key'])
        if p.get('mount', 'floor') not in ('floor', 'wall', 'ceiling'): raise ValueError('%s: mount must be floor, wall or ceiling' % p['key'])
    return kit


def part(kit, key):
    for p in kit['parts']:
        if p['key'] == key: return p
    raise KeyError('no part %s in kit %s' % (key, kit.get('kit')))


def parts(kit, category=None, mount=None, tags=None):
    return [p for p in kit['parts'] if (category is None or p.get('category') == category) and (mount is None or p.get('mount', 'floor') == mount)
            and (not tags or set(tags) <= set(p.get('tags', [])))]


def _yaw_to(front, direction):
    want = math.degrees(math.atan2(direction[1], direction[0]))
    return (want - FRONT_YAW[front]) % 360.0


def _rot(v, yaw):
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c)


def place(p, at, normal=(0, 0, 1), facing=(1, 0, 0)):
    lo, hi = p['bounds']; front = p.get('front', '+x'); mount = p.get('mount', 'floor')
    fx, fy = FRONT_VEC[front]
    if mount == 'floor':
        yaw = _yaw_to(front, facing)
        origin = (at[0], at[1], at[2] - lo[2])
    elif mount == 'ceiling':
        yaw = _yaw_to(front, facing)
        origin = (at[0], at[1], at[2] - hi[2])
    else:
        n = (normal[0], normal[1])
        if abs(normal[2]) > 0.5 or math.hypot(*n) < 1e-6: raise ValueError('%s is a wall part: give a horizontal wall normal' % p['key'])
        yaw = _yaw_to(front, n)
        back = lo[0] if fx > 0 else -hi[0] if fx < 0 else lo[1] if fy > 0 else -hi[1]     # how far behind the origin the back sits
        nn = math.hypot(*n); ux, uy = n[0] / nn, n[1] / nn
        origin = (at[0] - ux * back, at[1] - uy * back, at[2])
    return {'model': p['model'], 'origin': [round(c, 3) for c in origin], 'angles': [0.0, round(yaw, 3), 0.0], 'key': p['key']}


def footprint(p, axis_dir):
    """extent of the part along a world direction once it faces the default way (for spacing rows)"""
    lo, hi = p['bounds']
    return max(abs(hi[0] - lo[0]) * abs(axis_dir[0]) + abs(hi[1] - lo[1]) * abs(axis_dir[1]), 1.0)


def row(p, start, end, gap=8.0, normal=(0, 0, 1), facing=(1, 0, 0)):
    d = [end[i] - start[i] for i in range(3)]; L = math.hypot(d[0], d[1])
    if L < 1e-6: return [place(p, start, normal, facing)]
    u = (d[0] / L, d[1] / L)
    probe = place(p, (0, 0, 0), normal, facing)
    lo, hi = p['bounds']
    corners = [_rot((x, y), probe['angles'][1]) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])]
    along = [c[0] * u[0] + c[1] * u[1] for c in corners]
    size = max(along) - min(along)
    n = max(1, int((L + gap) // (size + gap)))
    step = L / n
    return [place(p, [start[i] + d[i] * ((k + 0.5) * step / L) for i in range(3)], normal, facing) for k in range(n)]


def stack(p, at, count=2, facing=(1, 0, 0), jitter=0.0):
    h = p['bounds'][1][2] - p['bounds'][0][2]
    return [place(p, (at[0], at[1], at[2] + k * h), (0, 0, 1), (math.cos(math.radians(jitter * k)) * facing[0] - math.sin(math.radians(jitter * k)) * facing[1],
                                                                 math.sin(math.radians(jitter * k)) * facing[0] + math.cos(math.radians(jitter * k)) * facing[1], 0))
            for k in range(count)]


def measure(models):
    import sys
    tools = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools')
    if tools not in sys.path: sys.path.append(tools)
    import visualcheck
    mb = visualcheck.ModelBounds()
    out = mb.get_many(list(models)); mb.save()
    return out


def props(placements, group='kit', cls='prop_static', **keys):
    return [P.entity(cls, it['origin'], it['angles'], group=group, strict=False, model=it['model'], **keys) for it in placements]
