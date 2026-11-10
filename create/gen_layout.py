"""Rooms and corridors from a plan: floors, ceilings, shared walls (each wall built once) with door openings; returns shapes + room data.

  plan = {'z': 0, 'height': 128, 'wall': 8, 'slab': 8, 'ceiling': True,
          'materials': {'floor': ..., 'wall': ..., 'ceiling': ...},
          'rooms': {'hall': [x0, y0, x1, y1], 'side': [...], 'stair': {'box': [...], 'z': 64, 'height': 160}},   (per-room z / height)
          'doors': [['hall', 'side', 64, 96], ...]}        (rooms that share a wall; width, height; the opening is centred on the shared part)
  out = build(plan)  -> {'shapes': [(name, shape)], 'rooms': {name: {'box', 'z', 'centre', 'floor_z'}}, 'doors': [{'between', 'at', 'width'}]}
  write(out, group)  -> CMapMesh nodes in the vmaplib map (vmapgen.open_map first)

Walls are the union of every room outline, made as boxes straddling the outline and merged per wall line, so two rooms side by side share
one wall; door holes are cut with meshedit.subtract. Layout coordinates are the room interiors' wall centre lines.
Ported from layout.py (add_layout: rooms by graph, shared walls, openings) in cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp,
MIT). Not ported: levels joined by add_lift and relative coordinates (use per-room z and a primitives.stairs between them).
"""
import collections, math
import primitives as P, meshedit as M

DEFAULT = {'floor': 'materials/dev/reflectivity_30.vmat', 'wall': 'materials/dev/reflectivity_50.vmat', 'ceiling': 'materials/dev/reflectivity_70.vmat'}   # core pak01


def _room(name, spec, plan):
    if isinstance(spec, dict):
        box = spec['box']; z = spec.get('z', plan.get('z', 0)); h = spec.get('height', plan.get('height', 128))
    else:
        box = spec; z = plan.get('z', 0); h = plan.get('height', 128)
    x0, y0, x1, y1 = [float(v) for v in box]
    if x1 <= x0 or y1 <= y0: raise ValueError('room %s: box must be x0, y0, x1, y1 with x1 > x0, y1 > y0' % name)
    return {'box': (x0, y0, x1, y1), 'z': float(z), 'height': float(h), 'centre': ((x0 + x1) / 2, (y0 + y1) / 2, float(z))}


def _merge(intervals):
    out = []
    for a, b in sorted(intervals):
        if out and a <= out[-1][1] + 1e-6: out[-1][1] = max(out[-1][1], b)
        else: out.append([a, b])
    return out


def shared_edge(ra, rb, eps=1e-6):
    """('x' | 'y', line coordinate, (from, to)) of the wall two rooms share, or None"""
    ax0, ay0, ax1, ay1 = ra['box']; bx0, by0, bx1, by1 = rb['box']
    for line, a_hi, b_lo in ((ax1, ax1, bx0), (ax0, ax0, bx1)):
        if abs(a_hi - b_lo) < eps:
            lo, hi = max(ay0, by0), min(ay1, by1)
            if hi > lo: return ('x', line, (lo, hi))
    for line, a_hi, b_lo in ((ay1, ay1, by0), (ay0, ay0, by1)):
        if abs(a_hi - b_lo) < eps:
            lo, hi = max(ax0, bx0), min(ax1, bx1)
            if hi > lo: return ('y', line, (lo, hi))
    return None


def build(plan):
    mats = dict(DEFAULT, **(plan.get('materials') or {}))
    t = float(plan.get('wall', 8)); slab = float(plan.get('slab', 8))
    rooms = {n: _room(n, s, plan) for n, s in plan['rooms'].items()}
    shapes = []
    for n, r in rooms.items():
        x0, y0, x1, y1 = r['box']
        shapes.append(('floor_' + n, P.box((x0 - t / 2, y0 - t / 2, r['z'] - slab), (x1 + t / 2, y1 + t / 2, r['z']), mats['floor'])))
        if plan.get('ceiling', True):
            shapes.append(('ceiling_' + n, P.box((x0 - t / 2, y0 - t / 2, r['z'] + r['height']), (x1 + t / 2, y1 + t / 2, r['z'] + r['height'] + slab), mats['ceiling'])))
    # wall lines: (axis, coordinate, z0, z1) -> intervals along the line
    lines = collections.defaultdict(list)
    for r in rooms.values():
        x0, y0, x1, y1 = r['box']; z0, z1 = r['z'], r['z'] + r['height']
        lines[('x', x0, z0, z1)].append((y0 - t / 2, y1 + t / 2)); lines[('x', x1, z0, z1)].append((y0 - t / 2, y1 + t / 2))
        lines[('y', y0, z0, z1)].append((x0 + t / 2, x1 - t / 2)); lines[('y', y1, z0, z1)].append((x0 + t / 2, x1 - t / 2))   # end on the x walls' faces
    doors = []
    for spec in plan.get('doors', []):
        a, b = spec[0], spec[1]; w = float(spec[2]) if len(spec) > 2 else 64.0; h = float(spec[3]) if len(spec) > 3 else 96.0
        e = shared_edge(rooms[a], rooms[b])
        if e is None: raise ValueError('door %s-%s: the rooms share no wall' % (a, b))
        axis, c, (lo, hi) = e
        if hi - lo < w: raise ValueError('door %s-%s: the shared wall (%g) is narrower than the door (%g)' % (a, b, hi - lo, w))
        mid = (lo + hi) / 2; z = max(rooms[a]['z'], rooms[b]['z'])
        cut = ((c - t, mid - w / 2, z), (c + t, mid + w / 2, z + h)) if axis == 'x' else ((mid - w / 2, c - t, z), (mid + w / 2, c + t, z + h))
        doors.append({'between': [a, b], 'axis': axis, 'at': [c, mid, z] if axis == 'x' else [mid, c, z], 'width': w, 'height': h, 'cut': cut})
    for (axis, c, z0, z1), iv in sorted(lines.items()):
        for k, (lo, hi) in enumerate(_merge(iv)):
            box = ((c - t / 2, lo, z0), (c + t / 2, hi, z1)) if axis == 'x' else ((lo, c - t / 2, z0), (hi, c + t / 2, z1))
            wall = P.box(box[0], box[1], mats['wall'])
            for d in doors:
                (cx0, cy0, cz0), (cx1, cy1, cz1) = d['cut']
                if cx0 < box[1][0] and cx1 > box[0][0] and cy0 < box[1][1] and cy1 > box[0][1] and cz0 < box[1][2] and cz1 > box[0][2]:
                    wall = M.subtract(wall, P.box(d['cut'][0], d['cut'][1], mats['wall']))
            shapes.append(('wall_%s%g_%d' % (axis, c, k), wall))
    for d in doors: d.pop('cut')
    return {'shapes': shapes, 'rooms': {n: {'box': list(r['box']), 'z': r['z'], 'height': r['height'], 'centre': list(r['centre'])} for n, r in rooms.items()},
            'doors': doors}


def write(out, group='layout'):
    return [P.add(s, group) for _, s in out['shapes']]
