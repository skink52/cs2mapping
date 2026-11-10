"""Objective dressing for an IRONFRAME arena map (10 Nov 2026 playtest: zones and flags were hard to find). Layers onto the map as
last saved in Hammer, in its own vis group `ifr_objectives` (a re-run replaces only that group; the arena generator's `ifr_gen`
regeneration leaves it alone), and writes the objective markers of docs/ARENAS.md "Objective markers":
  every capture zone ifr_point_<ID> found in the map (its position is the source of truth), in every stacked arena copy:
    a flat lit ring inlay at the zone radius (warm white, team-neutral: the live owner colour is the script's / plugin's job) with a
    dark kerb band outside it, a low octagonal dais at the centre (cover), a mast beside it carrying a lit four-sided letter sign
    (the letter on every face, reading the right way round), a warm lamp under the sign, and ifr_point_<ID>_edge on the ring (radius)
  each team's flag stand (SITES[arena]['flags'], placed here because the maps had none):
    a raised 12-sided pad with two team-coloured lit inlay rings, a socket, two pylons with lit team strips and team-coloured lamps,
    and the info_target ifr_flag_t / ifr_flag_ct on the pad top
Self-lit materials are tools/objective_fx.py's (materials/ifr/fx/fx_obj_<c>_16.vmat), so run that first (it compiles them).
layout() returns the geometry as plain meshes so tools/objectives_preview.py renders exactly what goes into the map.
usage: python -I tools/arenas/objectives.py <map .vmap (a backup copy)> <out .vmap> [addon out dir] [--arena dunes] [--no-arena-json]
       (also writes the stands into out/addon/_gen/arena.json `flags` unless --no-arena-json, and <out>.entities.json)
"""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); TOOLS = os.path.dirname(HERE); PROJ = os.path.dirname(TOOLS)
CREATE = os.path.normpath(os.path.join(PROJ, '..', '..', 'create'))
sys.path.insert(0, CREATE); sys.path.insert(0, TOOLS)

GROUP = 'ifr_objectives'
EMIS = lambda c: 'materials/ifr/fx/fx_obj_%s_16.vmat' % c       # tools/objective_fx.py (n warm white, t orange, ct cyan)
MAT = dict(concrete='materials/concrete/hr_c/hr_concrete_wall_006.vmat', concrete_dark='materials/concrete/hr_c/hr_concrete_floor_001_dark.vmat',
           trim='materials/de_nuke/hr_nuke/hr_metal_trim_001.vmat', panel='materials/de_train/hr_train_s2/metal/hrts2_metal_panelling_01.vmat',
           plate='materials/de_overpass/metal/steel_ground_plate_1.vmat')
COLOR = {'t': '255 150 60', 'ct': '70 200 255', 'n': '255 225 180'}
# per arena: flag stand centres (x, y). Dunes: on the flat dune ground in front of each team's drop line, 8 400 u apart
# (the old default, the first drop point, put them 11 200 u apart in the corners), clear of the plateaus, canyon and refinery.
SITES = {'dunes': dict(flags={'t': (-4200.0, 0.0), 'ct': (4200.0, 0.0)}),
         # Sprawl: on the y = 0 avenue between the two west / east blocks, 7 200 u apart, clear of the highways and the crossings' lamps
         'sprawl': dict(flags={'t': (-3600.0, 0.0), 'ct': (3600.0, 0.0)})}
FONT = {'A': ['01110', '10001', '10001', '11111', '10001', '10001', '10001'], 'B': ['11110', '10001', '10001', '11110', '10001', '10001', '11110'],
        'C': ['01111', '10000', '10000', '10000', '10000', '10000', '01111'], 'D': ['11110', '10001', '10001', '10001', '10001', '10001', '11110'],
        'E': ['11111', '10000', '10000', '11110', '10000', '10000', '11111']}


# ---------------------------------------------------------------- geometry as plain meshes: (verts, faces CCW from outside, face mats, opts)
def box(c, h, yaw=0.0, mat=MAT['concrete']):
    ca, sa = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    V = []
    for k in range(8):
        dx, dy, dz = (h[0] if k & 1 else -h[0]), (h[1] if k & 2 else -h[1]), (h[2] if k & 4 else -h[2])
        V.append((c[0] + dx * ca - dy * sa, c[1] + dx * sa + dy * ca, c[2] + dz))
    F = [[0, 2, 3, 1], [4, 5, 7, 6], [0, 4, 6, 2], [1, 3, 7, 5], [0, 1, 5, 4], [2, 6, 7, 3]]
    mats = mat if isinstance(mat, list) else [mat] * 6
    return V, F, mats


def prism(cx, cy, z0, z1, r0, r1, n, side, top, rot=0.0):
    th = [rot + 2 * math.pi * k / n for k in range(n)]
    V = [(cx + r0 * math.cos(t), cy + r0 * math.sin(t), z0) for t in th] + [(cx + r1 * math.cos(t), cy + r1 * math.sin(t), z1) for t in th]
    F = [list(range(n))[::-1], [n + i for i in range(n)]] + [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
    return V, F, [side, top] + [side] * n


def band(cx, cy, r0, r1, n, zf, mat, segs=None):
    """a flat ring strip (open mesh, top only) following zf(x, y); segs: draw only these segment indices (dashes)"""
    V, F = [], []
    for k in range(n):
        if segs is not None and k not in segs: continue
        a, b = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        q = [(r0 * math.cos(a), r0 * math.sin(a)), (r1 * math.cos(a), r1 * math.sin(a)), (r1 * math.cos(b), r1 * math.sin(b)), (r0 * math.cos(b), r0 * math.sin(b))]
        i0 = len(V)
        for x, y in q: V.append((cx + x, cy + y, zf(cx + x, cy + y)))
        F.append([i0, i0 + 1, i0 + 2, i0 + 3])
    return V, F, [mat] * len(F)


def merge(parts):
    V, F, M = [], [], []
    for v, f, m in parts:
        o = len(V); V += list(v); F += [[i + o for i in face] for face in f]; M += list(m)
    return V, F, M


def glyph(ch, centre, normal_yaw, px, depth, mat):
    """the letter's pixel blocks standing out of a face whose outward normal points along normal_yaw; reads right way round from outside"""
    ny = math.radians(normal_yaw); nx_, ny_ = math.cos(ny), math.sin(ny)
    rx, ry = -ny_, nx_                     # the viewer looks along -normal: right = (-n) x up
    parts = []
    for j, row in enumerate(FONT[ch]):
        for i, bit in enumerate(row):
            if bit != '1': continue
            off = (i - 2) * px
            c = (centre[0] + nx_ * depth / 2 + rx * off, centre[1] + ny_ * depth / 2 + ry * off, centre[2] + (3 - j) * px)
            parts.append(box(c, (depth / 2, px / 2 - 1, px / 2 - 1), normal_yaw, mat))
    return merge(parts)


def layout(points, flags, ground):
    """points [(id, x, y, z, radius)], flags {'t': (x, y), 'ct': (x, y)}, ground(x, y) -> terrain height.
    -> dict(meshes=[(V, F, mats, opts)], lamps=[(pos, lumens, range, colour)], targets=[(name, pos)], flags={team: [x, y, z]}, zones=[...])"""
    meshes, lamps, targets, out_flags, zones = [], [], [], {}, []
    for pid, x, y, z, r in points:
        gz = lambda px_, py_, z_=z: max(ground(px_, py_), z_ - 40) + 3     # flush on the plateau top, never under the marker by much
        meshes.append((*band(x, y, r - 14, r + 14, 96, gz, EMIS('n')), dict(bake=False, shadows=False, physics='none')))
        meshes.append((*band(x, y, r + 14, r + 46, 96, gz, MAT['trim']), dict(bake=True, shadows=False, physics='none')))
        meshes.append((*band(x, y, r - 70, r - 52, 96, gz, EMIS('n'), segs=set(range(0, 96, 4)) | set(range(1, 96, 4))), dict(bake=False, shadows=False, physics='none')))
        meshes.append((*prism(x, y, z - 60, z + 110, 230, 200, 8, MAT['concrete'], MAT['concrete_dark'], rot=math.pi / 8), dict()))
        # mast and sign beside the dais, on the side away from the arena centre (north for the centre zone)
        d = math.hypot(x, y); ux, uy = (x / d, y / d) if d > 1 else (0.0, 1.0)
        mx, my = x + ux * 330, y + uy * 330
        mz = max(ground(mx, my), z - 40)
        meshes.append((*prism(mx, my, mz - 50, mz + 40, 110, 95, 8, MAT['concrete'], MAT['concrete_dark'], rot=math.pi / 8), dict()))
        meshes.append((*box((mx, my, mz + 40 + 330), (28, 28, 330), 0, MAT['trim']), dict()))
        sz = mz + 40 + 660 + 180
        meshes.append((*box((mx, my, sz), (160, 160, 180), 0, MAT['panel']), dict()))
        for yaw in (0, 90, 180, 270):
            ny = math.radians(yaw)
            meshes.append((*glyph(pid, (mx + 160 * math.cos(ny), my + 160 * math.sin(ny), sz), yaw, 42, 10, EMIS('n')), dict(bake=False, shadows=False, physics='none')))
        lamps.append(((mx, my, sz - 240), 30000, 1100, COLOR['n']))
        targets.append(('ifr_point_%s_edge' % pid, (x + r, y, gz(x + r, y) + 5)))
        zones.append(dict(id=pid, pos=(x, y, z), radius=r, sign=(mx, my, sz)))
    for team, (x, y) in flags.items():
        c = 't' if team == 't' else 'ct'
        hs = [ground(x + rr * math.cos(a), y + rr * math.sin(a)) for rr in (0, 250, 470) for a in [k * math.pi / 6 for k in range(12)]]
        top = max(hs) + 10; bot = min(hs) - 60
        meshes.append((*prism(x, y, bot, top, 520, 440, 12, MAT['concrete'], MAT['plate'], rot=math.pi / 12), dict()))
        flat = lambda px_, py_, t=top: t + 1
        meshes.append((*band(x, y, 228, 252, 48, flat, EMIS(c)), dict(bake=False, shadows=False, physics='none')))
        meshes.append((*band(x, y, 396, 414, 48, flat, EMIS(c)), dict(bake=False, shadows=False, physics='none')))
        meshes.append((*prism(x, y, top - 4, top + 26, 64, 52, 8, MAT['trim'], MAT['trim']), dict()))
        d = math.hypot(x, y); ux, uy = (x / d, y / d) if d > 1 else (1.0, 0.0)
        px_, py_ = -uy, ux                                         # pylons either side, across the line to the centre
        yaw = math.degrees(math.atan2(uy, ux))
        for s in (-1, 1):
            bx, by = x + px_ * 600 * s, y + py_ * 600 * s
            bz = ground(bx, by)
            meshes.append((*box((bx, by, bz + 300 - 40), (44, 44, 340), yaw, MAT['concrete']), dict()))
            # the lit strip on the face toward the stand
            fx_, fy_ = bx - px_ * 46 * s, by - py_ * 46 * s
            meshes.append((*box((fx_, fy_, bz + 330), (22, 4, 270), yaw, EMIS(c)), dict(bake=False, shadows=False, physics='none')))
            lamps.append(((bx - px_ * 120 * s, by - py_ * 120 * s, bz + 560), 30000, 1400, COLOR[c]))
        targets.append(('ifr_flag_%s' % team, (x, y, top + 2)))
        out_flags[team] = [round(x, 1), round(y, 1), round(top + 2, 1)]
    return dict(meshes=meshes, lamps=lamps, targets=targets, flags=out_flags, zones=zones)


# ---------------------------------------------------------------- into the map
def map_points(d, G):
    """the zones as the map has them, per arena copy: {copy: [(id, x, y, z, radius)]}, offsets {copy: (dx, dy, dz) from copy 0}.
    Stacked copies (ifr_arena_2..4) repeat every ifr_point_<ID>; same-ID markers sorted by z from the top are copies 0, 1, ...,
    except that the copy nearest ifr_arena_1 (the generated arena) is always copy 0.
    Radius from an existing _edge marker outside our group (nearest the centre), else 700."""
    pts, edges = {}, {}
    for c in G.entities(d):
        p = G.props_of(c); tn = p.get('targetname') or ''
        if p.get('classname') != 'info_target' or not tn.startswith('ifr_point_'): continue
        o = tuple(float(v) for v in c.get('origin'))
        if tn.endswith('_edge'):
            if c.get('customVisGroup', '') != GROUP: edges.setdefault(tn[len('ifr_point_'):-5], []).append(o)
        else: pts.setdefault(tn[len('ifr_point_'):], []).append(o)
    ids = sorted(k for k in pts if k in FONT)
    n = min(len(pts[k]) for k in ids) if ids else 0
    if ids and any(len(pts[k]) != n for k in ids): print('WARNING: zone markers per ID differ (%s): dressing %d copies' % (', '.join('%s x%d' % (k, len(pts[k])) for k in ids), n))
    for k in ids: pts[k].sort(key=lambda o: -o[2])
    # copy 0 must be the generated arena (gk / SITES are in its frame): the copy nearest ifr_arena_1 (copies.py puts it at the
    # generated origin); without it the topmost copy (Dunes: copies at 0 and -8664). Sprawl stacks one above (+8664).
    a1 = [tuple(float(v) for v in c.get('origin')) for c in G.entities(d)
          if (G.props_of(c).get('targetname') or '') == 'ifr_arena_1']
    if ids and n and a1:
        zs = [sum(pts[k][ci][2] for k in ids) / len(ids) for ci in range(n)]
        ref = min(range(n), key=lambda ci: abs(zs[ci] - a1[0][2]))
        if ref:
            for k in ids: pts[k] = [pts[k][ref]] + [o for i, o in enumerate(pts[k]) if i != ref]
    out, offs = {}, {}
    for ci in range(n):
        offs[ci] = tuple(sum(pts[k][ci][a] - pts[k][0][a] for k in ids) / len(ids) for a in range(3))
        out[ci] = []
        for pid in ids:
            x, y, z = pts[pid][ci]; r = 700.0
            near = [e for e in edges.get(pid, []) if abs(e[2] - z) < 2000]
            if near: e = min(near, key=lambda e: math.hypot(e[0] - x, e[1] - y)); r = round(math.hypot(e[0] - x, e[1] - y))
            out[ci].append((pid, x, y, z - 8, r))
    return out, offs


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    if len(args) < 2: sys.exit(__doc__)
    src, out = args[0], args[1]; addon = args[2] if len(args) > 2 else os.path.join(PROJ, 'out', 'addon')
    arena = argv[argv.index('--arena') + 1] if '--arena' in argv else 'dunes'
    import importlib
    import vmapgen as G, vmesh
    from arenas.common import Ctx
    mod = importlib.import_module('arenas.' + arena)
    ground = mod.ground_at
    d = G.open_map(src, addon)
    copies, offs = map_points(d, G)
    for c in G.entities(d):                     # a stand placed by hand outside our group would make two of a name
        p = G.props_of(c)
        if (p.get('targetname') or '') in ('ifr_flag_t', 'ifr_flag_ct') and c.get('customVisGroup', '') != GROUP:
            print('WARNING: the map already has %s outside %s; it now has two (delete one in Hammer)' % (p.get('targetname'), GROUP))
    ctx = Ctx(d, out, None, GROUP)
    first = None
    for ci, pts in sorted(copies.items()):
        ox, oy, oz = offs[ci]
        gk = lambda x, y, ox=ox, oy=oy, oz=oz: ground(x - ox, y - oy) + oz        # the copy's terrain = the arena's, shifted
        for pid, x, y, z, r in pts: print('copy %d zone %s at (%.0f, %.0f, %.0f) r %d, terrain there %.0f' % (ci + 1, pid, x, y, z, r, gk(x, y)))
        fl = {t: (fx + ox, fy + oy) for t, (fx, fy) in SITES[arena]['flags'].items()}
        L = layout(pts, fl, gk)
        for V, F, mats, o in L['meshes']:
            ctx.mesh(vmesh.polymesh_open(V, F, mats, scale=0.25), bake=o.get('bake', True), shadows=o.get('shadows', True), physics=o.get('physics', 'default'))
        for pos, lm, rng, col in L['lamps']: ctx.lamp(pos, lm, rng, col)
        for name, pos in L['targets']: ctx.target(name, pos)
        print('copy %d (offset %.0f %.0f %.0f): %d zones (%s), %d flag stands, %d meshes, %d lamps, %d markers' % (
            ci + 1, ox, oy, oz, len(pts), ' '.join('%s r%d' % (p[0], p[4]) for p in pts), len(L['flags']), len(L['meshes']), len(L['lamps']), len(L['targets'])))
        if first is None: first = L
    G.finish(d, out, group=GROUP, first_run_cleanup=False, entities_json=out + '.entities.json')
    print('objectives: %d arena copies -> %s' % (len(copies), out))
    L = first or dict(flags={})
    if '--no-arena-json' not in argv:
        aj = os.path.join(addon, '_gen', 'arena.json')
        if os.path.exists(aj):
            j = json.load(open(aj, encoding='utf-8')); j['flags'] = L['flags']
            json.dump(j, open(aj, 'w', encoding='utf-8'), separators=(',', ':'))
            print('arena.json flags =', L['flags'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
