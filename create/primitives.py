"""Closed solid primitives for generated maps, plus FGD-checked entities and I/O wiring.

Every shape function returns a Shape: (verts, faces, mats) with faces as vertex-index loops counter-clockwise seen from OUTSIDE, which is
what vmaplib.polymesh() (closed meshes) and vmesh.polymesh_open() take. Units are inches, +Z up, yaw 0 = +X.

  box(mins, maxs, mat)                         wedge(mins, maxs, rise='+x', mat)     ramp up toward the rise side
  cylinder(center_xy, radius, z0, z1, sides)   prism(polygon_xy, z0, z1, mat)        any simple polygon (concave allowed), extruded in z
  stairs(mins, maxs, steps, rise='+x')         one closed solid, treads + risers + a flat underside
  arch(center, width, height, depth, thickness, segments, axis='x')   a round arch (half ring) over a doorway, extruded along depth
  extrude(profile_2d, depth, plane='xz', at=(0,0,0))                  any simple 2D profile, extruded along the plane's normal
  revolve(profile_rz, sides, center=(0,0,0))   lathe: (r, z) points bottom to top; r = 0 points close the ends (columns, domes, bowls)
  sweep(path_xyz, section_2d, closed=False)    a 2D section (e.g. rect(w, h) or circle(r, n)) carried along a polyline (pipes, kerbs, rails);
                                               mitred corners, the section stays upright on slopes
  rect(w, h), circle(r, n)                     2D sections for sweep / extrude
  merge(*shapes), translate(shape, d), rotate_z(shape, deg, pivot), materials(shape, {face_index: mat} | callable)
  check(shape) -> list of problems (open edges, non-manifold edges, wrong winding, degenerate faces); volume(shape) > 0 when outward

Map side (vmaplib must have been pointed at the map with vmapgen.open_map()):
  add(shape, group='')                         -> CMapMesh node (vmaplib.polymesh + mesh_node, queued for vmapgen.finish)
  entity(cls, origin, angles=(0,0,0), group='', defaults=True, strict=True, **keys)
                                               FGD defaults (what Hammer writes for a freshly placed entity) + your keys; strict
                                               rejects classes / keys the installed FGDs don't define (tools/fgdcat.py)
  connect(src, output, target, input, param='', delay=0, times=-1, check_output=True)   append an I/O connection to an entity node
  brush_entity(cls, shape, group='', **keys)   a brush entity (trigger_*, func_*) owning the shape's mesh

Shapes, defaults-filled entities and wiring follow the map_edit operations of cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT:
mesh.py box/wedge/cylinder/stairs/prism, shapes.py arch, meshops revolve / extrude along paths, project.py add_entity / connect).
Fresh code on skink52's vmaplib / vmesh writers.
"""
import math, os, sys

Shape = tuple
DEFAULT_MAT = 'materials/dev/reflectivity_50.vmat'


# ------------------------------------------------------------------------------------------------ vector helpers
def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def _mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def _len(a): return math.sqrt(_dot(a, a))
def _unit(a):
    n = _len(a)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-12 else (0.0, 0.0, 0.0)


def _area2(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))


def _ccw(poly):
    """2D polygon in counter-clockwise order, no repeated closing point"""
    poly = [tuple(map(float, p[:2])) for p in poly]
    if len(poly) > 1 and poly[0] == poly[-1]: poly = poly[:-1]
    return poly if _area2(poly) > 0 else poly[::-1]


def newell(verts, loop):
    """face normal (not unit) by Newell's method: right for concave faces too"""
    n = [0.0, 0.0, 0.0]
    for i in range(len(loop)):
        a, b = verts[loop[i]], verts[loop[(i + 1) % len(loop)]]
        n[0] += (a[1] - b[1]) * (a[2] + b[2]); n[1] += (a[2] - b[2]) * (a[0] + b[0]); n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return tuple(n)


def convex_first(verts, loop):
    """rotate a loop so its first corner is convex: vmaplib takes a face's normal from its first three corners"""
    n = newell(verts, loop); k = len(loop)
    best, bi = -1.0, 0
    for i in range(k):
        a, b, c = verts[loop[i]], verts[loop[(i + 1) % k]], verts[loop[(i + 2) % k]]
        d = _dot(_cross(_sub(b, a), _sub(c, a)), n)
        if d > best: best, bi = d, i
    return loop[bi:] + loop[:bi]


def _finish(verts, faces, mats):
    faces = [convex_first(verts, f) for f in faces]
    if volume((verts, faces, mats)) < 0: faces = [convex_first(verts, f[::-1]) for f in faces]
    return [tuple(map(float, v)) for v in verts], faces, list(mats)


def volume(shape):
    """signed volume (divergence theorem); > 0 when faces wind outward"""
    verts, faces, _ = shape; vol = 0.0
    for f in faces:
        a = verts[f[0]]
        for i in range(1, len(f) - 1):
            vol += _dot(a, _cross(verts[f[i]], verts[f[i + 1]]))
    return vol / 6.0


def check(shape):
    """problems that make Hammer / the compiler reject or mis-light a mesh"""
    verts, faces, mats = shape; out = []
    if len(mats) != len(faces): out.append('materials: %d for %d faces' % (len(mats), len(faces)))
    edges = {}
    for fi, f in enumerate(faces):
        if len(f) < 3 or len(set(f)) != len(f): out.append('face %d: fewer than 3 distinct corners' % fi); continue
        if _len(newell(verts, f)) < 1e-9: out.append('face %d: zero area' % fi)
        for i in range(len(f)):
            e = (f[i], f[(i + 1) % len(f)])
            if e in edges: out.append('edge %s used twice in one direction (faces %d, %d): wrong winding or non-manifold' % (e, edges[e], fi))
            edges[e] = fi
    open_ = [e for e in edges if (e[1], e[0]) not in edges]
    if open_: out.append('%d open edges (first %s)' % (len(open_), open_[0]))
    if not out and volume(shape) <= 0: out.append('faces wind inward (negative volume)')
    return out


# ------------------------------------------------------------------------------------------------ shapes
def box(mins, maxs, mat=DEFAULT_MAT):
    x0, y0, z0 = mins; x1, y1, z1 = maxs
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [[3, 2, 1, 0], [4, 5, 6, 7], [0, 1, 5, 4], [2, 3, 7, 6], [1, 2, 6, 5], [3, 0, 4, 7]]
    return _finish(v, f, [mat] * 6)


def _axis_frame(rise):
    """(index of the rising axis, its sign)"""
    rise = rise.strip().lower()
    if rise not in ('+x', '-x', '+y', '-y'): raise ValueError('rise must be +x, -x, +y or -y')
    return (0 if rise[1] == 'x' else 1), (1 if rise[0] == '+' else -1)


def wedge(mins, maxs, rise='+x', mat=DEFAULT_MAT):
    """a ramp: full height at the rise side, zero at the other"""
    ax, sg = _axis_frame(rise)
    lo, hi = mins[ax], maxs[ax]
    a0, a1 = (lo, hi) if sg > 0 else (hi, lo)            # a0 low edge, a1 high edge
    o = 1 - ax
    prof = [(a0, mins[2]), (a1, mins[2]), (a1, maxs[2])]  # (along, z)
    return _profile_solid(prof, ax, (mins[o], maxs[o]), mat)


def _profile_solid(prof, ax, span, mat):
    """a profile in the (axis ax, z) plane extruded across the other horizontal axis from span[0] to span[1]"""
    o = 1 - ax
    def pt(a, z, s):
        p = [0.0, 0.0, z]; p[ax] = a; p[o] = s; return tuple(p)
    n = len(prof)
    verts = [pt(a, z, span[0]) for a, z in prof] + [pt(a, z, span[1]) for a, z in prof]
    faces = [list(range(n - 1, -1, -1)), list(range(n, 2 * n))]
    faces += [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
    return _finish(verts, faces, [mat] * len(faces))


def stairs(mins, maxs, steps, rise='+x', mat=DEFAULT_MAT, tread_mat=None):
    """steps treads from the low side up to maxs z at the rise side; solid down to mins z"""
    if steps < 1: raise ValueError('steps >= 1')
    ax, sg = _axis_frame(rise)
    lo, hi = mins[ax], maxs[ax]
    run = (hi - lo) / steps; h = (maxs[2] - mins[2]) / steps
    start = lo if sg > 0 else hi; d = run * sg
    prof = [(start, mins[2])]
    for i in range(steps):
        a = start + d * i
        prof += [(a, mins[2] + h * (i + 1)), (a + d, mins[2] + h * (i + 1))]
    prof.append((start + d * steps, mins[2]))
    prof = [p for i, p in enumerate(prof) if i == 0 or p != prof[i - 1]]
    verts, faces, mats = _profile_solid(prof if _area2(prof) > 0 else prof[::-1], ax, (mins[1 - ax], maxs[1 - ax]), mat)
    if tread_mat:
        return materials((verts, faces, mats), lambda i, nrm: tread_mat if nrm[2] > 0.99 else None)
    return verts, faces, mats


def prism(polygon, z0, z1, mat=DEFAULT_MAT, top=None, bottom=None, sides=None):
    poly = _ccw(polygon)
    n = len(poly)
    if n < 3: raise ValueError('a prism needs 3+ points')
    verts = [(x, y, z0) for x, y in poly] + [(x, y, z1) for x, y in poly]
    faces = [list(range(n - 1, -1, -1)), list(range(n, 2 * n))] + [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
    mats = [bottom or mat, top or mat] + [sides or mat] * n
    return _finish(verts, faces, mats)


def cylinder(center, radius, z0, z1, sides=16, mat=DEFAULT_MAT):
    return prism(circle(radius, sides, center[:2]), z0, z1, mat)


def rect(w, h, center=(0.0, 0.0)):
    cx, cy = center
    return [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]


def circle(r, n=16, center=(0.0, 0.0)):
    return [(center[0] + r * math.cos(2 * math.pi * i / n), center[1] + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


_PLANES = {'xz': ((1, 0, 0), (0, 0, 1), (0, 1, 0)), 'yz': ((0, 1, 0), (0, 0, 1), (1, 0, 0)), 'xy': ((1, 0, 0), (0, 1, 0), (0, 0, 1))}


def extrude(profile, depth, plane='xz', at=(0.0, 0.0, 0.0), mat=DEFAULT_MAT):
    """a 2D profile (u, v) in the plane, pushed depth along the plane's normal (xz: +y, yz: +x, xy: +z)"""
    u, v, n = _PLANES[plane]
    poly = _ccw(profile); k = len(poly)
    P = lambda a, b, w: _add(at, _add(_add(_mul(u, a), _mul(v, b)), _mul(n, w)))
    verts = [P(a, b, 0.0) for a, b in poly] + [P(a, b, depth) for a, b in poly]
    faces = [list(range(k)), list(range(2 * k - 1, k - 1, -1))] + [[i, k + i, k + (i + 1) % k, (i + 1) % k] for i in range(k)]
    return _finish(verts, faces, [mat] * len(faces))


def arch(center, width, height, depth, thickness=16.0, segments=12, axis='x', mat=DEFAULT_MAT):
    """a round-topped arch (a half ring) whose opening is width wide and height tall at the crown, standing on center (feet z),
    spanning along axis ('x': the opening runs along x, the arch is depth thick along y)"""
    r_in = width / 2.0; r_out = r_in + thickness
    spring = height - r_in                                 # the arc springs at this height above the feet
    if spring < 0: raise ValueError('height must be at least width / 2')
    outer = [(r_out * math.cos(math.pi * i / segments), spring + r_out * math.sin(math.pi * i / segments)) for i in range(segments + 1)]
    inner = [(r_in * math.cos(math.pi * i / segments), spring + r_in * math.sin(math.pi * i / segments)) for i in range(segments, -1, -1)]
    prof = [(r_out, 0.0)] + outer + [(-r_out, 0.0), (-r_in, 0.0)] + inner + [(r_in, 0.0)]
    prof = [p for i, p in enumerate(prof) if i == 0 or (abs(p[0] - prof[i - 1][0]) > 1e-6 or abs(p[1] - prof[i - 1][1]) > 1e-6)]
    cx, cy, cz = center
    if axis == 'x': return extrude(prof, depth, 'xz', (cx, cy - depth / 2.0, cz), mat)
    return extrude(prof, depth, 'yz', (cx - depth / 2.0, cy, cz), mat)


def revolve(profile, sides=16, center=(0.0, 0.0, 0.0), mat=DEFAULT_MAT):
    """lathe a (r, z) profile, listed bottom to top along the outside, about the z axis through center.
    Points with r = 0 sit on the axis and close that end; open ends get a flat cap."""
    if len(profile) < 2: raise ValueError('a profile needs 2+ points')
    cx, cy, cz = center
    verts, rings = [], []
    for r, z in profile:
        if abs(r) < 1e-9:
            rings.append([len(verts)] * sides); verts.append((cx, cy, cz + z))
        else:
            rings.append(list(range(len(verts), len(verts) + sides)))
            verts += [(cx + r * math.cos(2 * math.pi * i / sides), cy + r * math.sin(2 * math.pi * i / sides), cz + z) for i in range(sides)]
    faces = []
    for a, b in zip(rings, rings[1:]):
        for i in range(sides):
            j = (i + 1) % sides
            loop = [a[i], a[j], b[j], b[i]]
            loop = [x for k, x in enumerate(loop) if x not in loop[:k]]
            if len(loop) >= 3: faces.append(loop)
    if len(set(rings[0])) > 1: faces.append(rings[0][::-1])
    if len(set(rings[-1])) > 1: faces.append(list(rings[-1]))
    return _finish(verts, faces, [mat] * len(faces))


def sweep(path, section, closed=False, mat=DEFAULT_MAT, up=(0.0, 0.0, 1.0)):
    """carry a 2D section (x = sideways, y = up) along a 3D polyline; mitred corners; capped ends unless closed"""
    pts = [tuple(map(float, p)) for p in path]
    if len(pts) < 2: raise ValueError('a path needs 2+ points')
    sec = _ccw(section); k = len(sec); n = len(pts)
    def tangent(i):
        if closed:
            a, b = pts[i - 1], pts[(i + 1) % n]
            t0, t1 = _unit(_sub(pts[i], a)), _unit(_sub(b, pts[i]))
        else:
            t0 = _unit(_sub(pts[i], pts[i - 1])) if i > 0 else None
            t1 = _unit(_sub(pts[i + 1], pts[i])) if i < n - 1 else None
            t0, t1 = t0 or t1, t1 or t0
        t = _unit(_add(t0, t1)); scale = 1.0 / max(0.25, _dot(t, t1))   # mitre: widen at the corner
        return t, scale, t1
    verts = []
    for i in range(n):
        t, s, seg = tangent(i)
        side = _unit(_cross(seg, up)) if _len(_cross(seg, up)) > 1e-6 else (1.0, 0.0, 0.0)
        upv = _cross(side, seg)
        side_m = _unit(_cross(t, upv)) if _len(_cross(t, upv)) > 1e-6 else side
        for a, b in sec:
            verts.append(_add(pts[i], _add(_mul(side_m, a * s), _mul(upv, b))))
    faces = []
    segs = n if closed else n - 1
    for i in range(segs):
        r0, r1 = i * k, ((i + 1) % n) * k
        for j in range(k):
            faces.append([r0 + j, r1 + j, r1 + (j + 1) % k, r0 + (j + 1) % k])
    if not closed:
        faces.append(list(range(k)))
        faces.append(list(range(n * k - 1, (n - 1) * k - 1, -1)))
    return _finish(verts, faces, [mat] * len(faces))


# ------------------------------------------------------------------------------------------------ shape edits
def merge(*shapes):
    verts, faces, mats = [], [], []
    for v, f, m in shapes:
        o = len(verts); verts += list(v); faces += [[i + o for i in loop] for loop in f]; mats += list(m)
    return verts, faces, mats


def translate(shape, d):
    v, f, m = shape
    return [_add(p, tuple(d)) for p in v], [list(x) for x in f], list(m)


def rotate_z(shape, deg, pivot=(0.0, 0.0, 0.0)):
    v, f, m = shape; c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    out = [(pivot[0] + (p[0] - pivot[0]) * c - (p[1] - pivot[1]) * s, pivot[1] + (p[0] - pivot[0]) * s + (p[1] - pivot[1]) * c, p[2]) for p in v]
    return out, [list(x) for x in f], list(m)


def materials(shape, rule):
    """rule: {face index: material} or fn(face index, unit normal) -> material or None (keep)"""
    v, f, m = shape; m = list(m)
    for i, loop in enumerate(f):
        new = rule.get(i) if isinstance(rule, dict) else rule(i, _unit(newell(v, loop)))
        if new: m[i] = new
    return v, [list(x) for x in f], m


# ------------------------------------------------------------------------------------------------ map side
def _catalog():
    here = os.path.dirname(os.path.abspath(__file__))
    tools = os.path.join(os.path.dirname(here), 'tools')
    if tools not in sys.path: sys.path.append(tools)       # appended: create/dmx.py must keep winning `import dmx`
    import fgdcat
    return fgdcat.load()


CATALOG = None   # set to an fgdcat.Catalog to skip loading the installed FGDs (tests)


def _cat():
    global CATALOG
    if CATALOG is None: CATALOG = _catalog()
    return CATALOG


def add(shape, group=''):
    import vmaplib
    probs = check(shape)
    if probs: raise ValueError('shape is not a closed outward mesh: ' + '; '.join(probs[:3]))
    v, f, m = shape
    return vmaplib.mesh_node(vmaplib.polymesh(v, f, m), group=group)


def entity(cls, origin, angles=(0, 0, 0), group='', defaults=True, strict=True, **keys):
    """an entity the way Hammer places it: every FGD default, then your keys (use key__sub for keys with dots, e.g. local__origin)"""
    import vmaplib
    keys = {k.replace('__', '.'): v for k, v in keys.items()}
    cat = _cat() if (defaults or strict) else None
    if strict and not cat.is_entity(cls):
        raise ValueError('%s is not an entity class in the installed FGDs; similar: %s' % (cls, ', '.join(cat.similar(cls))))
    kv = {}
    if defaults and cat is not None and cat.is_entity(cls):
        kv.update({k: v for k, v in cat.defaults(cls).items() if k.lower() != 'classname'})
    if strict and cat is not None:
        known = set(cat.keys(cls)) | cat.helper_keys(cls) | {'targetname', 'parentname', 'vscripts', 'spawnflags'}
        bad = [k for k in keys if k.lower() not in known]
        if bad: raise ValueError('%s has no key %s in the installed FGDs' % (cls, ', '.join(bad)))
    low = {k.lower(): k for k in kv}
    for k, v in keys.items():
        kv.pop(low.get(k.lower(), k), None); kv[k] = v
    return vmaplib.ent(cls, origin, angles, group, **{k: str(v) for k, v in kv.items()})


def connect(src, output, target, input, param='', delay=0.0, times=-1, check_output=True):
    """append an output -> target.input connection to an entity node made by entity() / vmaplib.ent()"""
    from vmaplib import Element, T_STRING, T_INT, T_FLOAT, T_ELEMENT, ARRAY    # create/dmx's types, whatever `dmx` is in this process
    if check_output:
        cls = src.get('entity_properties').get('classname')
        cat = _cat()
        if cat.is_entity(cls):
            outs = cat.io(cls)[1]
            if outs and output.lower() not in outs:
                raise ValueError('%s has no output %s (it has: %s)' % (cls, output, ', '.join(sorted(o[0] for o in outs.values()))[:300]))
    c = Element('DmeConnectionData', '')
    c.attrs = [['outputName', T_STRING, output], ['targetType', T_INT, 7], ['targetName', T_STRING, target], ['inputName', T_STRING, input],
               ['overrideParam', T_STRING, str(param)], ['delay', T_FLOAT, float(delay)], ['timesToFire', T_INT, int(times)]]
    a = src.attr('connectionsData')
    if a is None: src.attrs.append(['connectionsData', T_ELEMENT + ARRAY, [c]])
    else: a[2].append(c)
    return c


def brush_entity(cls, shape, group='', **keys):
    """a brush entity (trigger_multiple, func_brush ...) with the shape as its mesh; origin at the shape's centre"""
    import vmaplib
    v = shape[0]
    centre = tuple((min(p[i] for p in v) + max(p[i] for p in v)) / 2.0 for i in range(3))
    e = entity(cls, centre, group=group, **keys)
    probs = check(shape)
    if probs: raise ValueError('shape is not a closed outward mesh: ' + '; '.join(probs[:3]))
    e.attr('children')[2].append(vmaplib.mesh_node(vmaplib.polymesh(*shape), group=group, attach=False))
    return e
