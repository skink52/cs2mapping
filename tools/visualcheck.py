"""Read-only visual checks of a .vmap: floating props, props buried in geometry or in each other, z-fighting faces, open render meshes.

  python visualcheck.py <map.vmap> [--json] [--addon NAME] [--no-zfight] [--limit N] [--box x0,y0,z0,x1,y1,z1]

Never writes the map. Exit 0 = nothing at warning level, 1 = warnings.

  warning prop_floating    a prop's base hangs more than 16 u over the nearest floor / prop top under it, and it touches no wall or ceiling
  warning prop_in_geometry a wall / brush face cuts more than 12 u into a prop's box (rotated with the prop), or the floor reaches over a
                           third of its height (bases sunk a little are normal; foliage, trees and rocks may sink into the ground)
  warning prop_overlap     two different props' boxes share more than 12 u on every axis and half the smaller box (rows of one model,
                           foliage and models over 512 u are left out)
  warning z_fighting       coplanar overlapping visible faces of different materials (tools/zfight.py; zfight.py <map> <out> fixes them)
  info    z_fighting_same  the same, one material (barely shows)
  info    open_mesh        a drawn mesh with open edges (light leaks / see-through seams from behind)
  info    bounds_unknown   props whose model bounds couldn't be read (skipped by the prop checks)

Model bounds: compiled .vmdl_c from the addon's game folder or CS2's pak01 VPK, read by create/s2/bounds_batch.mjs (prop_mesh.mjs's reader,
Node 22.15+); when that can't read a model, the SMD / OBJ meshes its source .vmdl names in the addon content. Cached in
%LOCALAPPDATA%\\cs2mapping\\model_bounds.json (env CS2MAP_CACHE overrides). Props parented to something, physics props (they settle),
hidden helpers (renderamt 0 and not solid) and precache-room props (targetname with "cache") are skipped; models over 512 u are left
out of the overlap check (building pieces).

The checks and tolerances follow visual.py in cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT), where model bounds come from
Source2Viewer; fresh code on skink52's vmapedit, mapsanity (solid faces) and zfight.py.
"""
import argparse, collections, json, math, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vmapedit as V, mapsanity, fgdcheck

SUPPORT_GAP, CONTACT, DEPTH = 16.0, 12.0, 12.0
CELL = 128.0
NATURAL = re.compile(r'foliage|tree|rock|cliff|plant|bush|grass|shrub|vine|stone|boulder|log_|stump')
PROP_CLASSES = ('prop_static', 'prop_dynamic', 'prop_dynamic_override', 'prop_door_rotating', 'prop_dynamic_glow')
PHYSICS = ('prop_physics', 'prop_physics_override', 'prop_physics_multiplayer', 'prop_physics_respawnable', 'prop_ragdoll')
SEV = {'prop_floating': 'warning', 'prop_in_geometry': 'warning', 'prop_overlap': 'warning', 'z_fighting': 'warning',
       'z_fighting_same': 'info', 'open_mesh': 'info', 'bounds_unknown': 'info'}
NODE = os.environ.get('NODE', 'node')
BATCH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'create', 's2', 'bounds_batch.mjs')


def _mesh_points(path):
    """vertex positions of an SMD (triangles block) or OBJ file"""
    try:
        with open(path, encoding='utf-8', errors='replace') as f: lines = f.read().splitlines()
    except OSError:
        return []
    out = []
    if path.lower().endswith('.obj'):
        for ln in lines:
            if ln.startswith('v '):
                try: out.append([float(x) for x in ln.split()[1:4]])
                except ValueError: pass
        return out
    tri = False
    for ln in lines:
        w = ln.split()
        if not w: continue
        if w[0] == 'triangles': tri = True; continue
        if w[0] == 'end': tri = False; continue
        if tri and len(w) >= 4:
            try: out.append([float(w[1]), float(w[2]), float(w[3])])
            except ValueError: pass
    return out


def cache_path():
    return os.environ.get('CS2MAP_CACHE') or os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'cs2mapping', 'model_bounds.json')


class ModelBounds:
    """model path -> ((lo), (hi)) in model units; None when unreadable"""
    def __init__(s, cs2=None, addon=None, cache=None, reader=None):
        import fgdcat
        s.cs2 = cs2 or fgdcat.cs2_root(); s.addon = addon
        s.path = cache or cache_path()
        try:
            with open(s.path, encoding='utf-8') as f: s.cache = json.load(f)
        except (OSError, ValueError):
            s.cache = {}
        s.reader = reader or s._node_reader
        s.dirty = False

    def _compiled(s, model):
        rel = model.replace('\\', '/').lower()
        rel = rel if rel.endswith('_c') else rel + '_c'
        if s.addon:
            p = os.path.join(s.cs2, 'game', 'csgo_addons', s.addon, rel)
            if os.path.exists(p): return p, None
        return rel, os.path.join(s.cs2, 'game', 'csgo')

    def _node_reader(s, items):
        """[(path, vpk folder or None)] -> {path: {lo, hi}} via create/s2/bounds_batch.mjs (one Node run; bad models skipped)"""
        tmp_in, tmp_out = s.path + '.list.json', s.path + '.out.json'
        os.makedirs(os.path.dirname(tmp_in), exist_ok=True)
        with open(tmp_in, 'w', encoding='utf-8') as f: json.dump([{'path': p, 'vpk': v} for p, v in items], f)
        try:
            r = subprocess.run([NODE, BATCH, tmp_in, tmp_out], capture_output=True, text=True,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=1800)
            if r.returncode != 0: return {}
            with open(tmp_out, encoding='utf-8') as f: got = json.load(f)
        except (OSError, ValueError, subprocess.SubprocessError):
            return {}
        finally:
            for p in (tmp_in, tmp_out):
                try: os.remove(p)
                except OSError: pass
        return {k.replace(chr(92), '/').lower(): v for k, v in got.items() if 'lo' in v}

    def _source_bounds(s, model):
        """bounds from the model's source: the addon's .vmdl names SMD / OBJ render meshes (skink52's generated props are SMD)"""
        if not s.addon: return None
        src = os.path.join(s.cs2, 'content', 'csgo_addons', s.addon, model.replace('/', os.sep))
        try:
            with open(src, encoding='utf-8', errors='replace') as f: text = f.read()
        except OSError:
            return None
        scale = 1.0
        ms = re.search(r'import_scale\s*=\s*([-0-9.eE]+)', text)
        if ms: scale = float(ms.group(1))
        lo, hi = [1e18] * 3, [-1e18] * 3
        for ref in re.findall(r'"([^"]+\.(?:smd|obj))"', text, re.I):
            if 'phys' in ref.lower() or 'hull' in ref.lower(): continue      # collision meshes can be larger than what is drawn
            p = os.path.join(s.cs2, 'content', 'csgo_addons', s.addon, ref.replace('/', os.sep))
            for xyz in _mesh_points(p):
                for i in range(3): lo[i] = min(lo[i], xyz[i] * scale); hi[i] = max(hi[i], xyz[i] * scale)
        return [lo, hi] if lo[0] < 1e17 else None

    def get_many(s, models):
        todo = {}
        for m in models:
            key = m.replace('\\', '/').lower()
            if key not in s.cache: todo[key] = s._compiled(m)
        if todo:
            got = s.reader(list(todo.values()))
            for key, (p, vpk) in todo.items():
                hit = got.get(p.replace('\\', '/').lower()) or next((v for k, v in got.items() if k.endswith(key + ('' if key.endswith('_c') else '_c'))), None)
                s.cache[key] = [hit['lo'], hit['hi']] if hit else s._source_bounds(key[:-2] if key.endswith('_c') else key)
            s.dirty = True
        return {m: s.cache.get(m.replace('\\', '/').lower()) for m in models}

    def save(s):
        if not s.dirty: return
        os.makedirs(os.path.dirname(s.path), exist_ok=True)
        with open(s.path, 'w', encoding='utf-8') as f: json.dump(s.cache, f)
        s.dirty = False


# ------------------------------------------------------------------------------------------------ geometry
def _num(x, d=1.0):
    try: return float(x)
    except (TypeError, ValueError): return d


def frame(m, e, lo, hi):
    """oriented box of a prop: centre, axes (3 unit vectors), half sizes, world AABB"""
    o = m.origin(e); ang = list(m.g(e, b'angles', [0, 0, 0]))
    sc = list(m.g(e, b'scales', [1, 1, 1])); k = _num(m.P(e, 'modelscale', '1'))
    lo = [lo[i] * sc[i] * k for i in range(3)]; hi = [hi[i] * sc[i] * k for i in range(3)]
    R = V.rot_matrix(ang)
    axes = [(R[0][c], R[1][c], R[2][c]) for c in range(3)]
    cl = [(lo[i] + hi[i]) / 2 for i in range(3)]; half = [abs(hi[i] - lo[i]) / 2 for i in range(3)]
    centre = V.xform(cl, o, ang)
    ext = [sum(abs(axes[c][i]) * half[c] for c in range(3)) for i in range(3)]
    return {'centre': centre, 'axes': axes, 'half': half, 'lo': [centre[i] - ext[i] for i in range(3)], 'hi': [centre[i] + ext[i] for i in range(3)]}


def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def tri_box(tri, half):
    """separating-axis test of a triangle (in the box's frame) against a box centred at 0 with half sizes `half`"""
    v0, v1, v2 = tri
    for i in range(3):
        if min(v0[i], v1[i], v2[i]) > half[i] or max(v0[i], v1[i], v2[i]) < -half[i]: return False
    e = [_sub(v1, v0), _sub(v2, v1), _sub(v0, v2)]
    n = _cross(e[0], e[1])
    r = sum(half[i] * abs(n[i]) for i in range(3))
    if abs(_dot(n, v0)) > r: return False
    for ed in e:
        for ax in ((0, -ed[2], ed[1]), (ed[2], 0, -ed[0]), (-ed[1], ed[0], 0)):
            p = [_dot(ax, v) for v in tri]
            r = sum(half[i] * abs(ax[i]) for i in range(3))
            if min(p) > r or max(p) < -r: return False
    return True


def _local(f, p):
    d = _sub(p, f['centre'])
    return tuple(_dot(d, a) for a in f['axes'])


class Grid:
    def __init__(s, cell=CELL):
        s.cell = cell; s.b = collections.defaultdict(list)

    def _keys(s, lo, hi):
        c = s.cell
        for x in range(int(math.floor(lo[0] / c)), int(math.floor(hi[0] / c)) + 1):
            for y in range(int(math.floor(lo[1] / c)), int(math.floor(hi[1] / c)) + 1):
                yield x, y

    def add(s, item, lo, hi):
        ks = list(s._keys(lo, hi))
        if len(ks) > 4096: ks = ks[:4096]          # enormous faces: indexed along their first cells only (sky shells)
        for k in ks: s.b[k].append(item)

    def near(s, lo, hi):
        seen = set(); out = []
        for k in s._keys(lo, hi):
            for it in s.b.get(k, ()):
                if id(it) not in seen: seen.add(id(it)); out.append(it)
        return out


def _tri_aabb(t):
    return [min(p[i] for p in t) for i in range(3)], [max(p[i] for p in t) for i in range(3)]


def open_meshes(m):
    """drawn meshes with boundary half-edges (face -1)"""
    out = []
    for n, owner in _meshes_with_owner(m):
        if owner and owner.startswith(mapsanity.NONSOLID_CLASSES): continue
        md = m.g(n, b'meshData')
        if md is None: continue
        ef = m.g(md, b'edgeFaceIndices') or []
        mats = [x.decode('utf-8', 'replace') if isinstance(x, (bytes, bytearray)) else str(x) for x in (m.g(md, b'materials') or [])]
        if not mats or all('tools' in x.lower() for x in mats): continue
        k = sum(1 for f in ef if f < 0)
        if k: out.append((n, k // 1, mats[0]))
    return out


def _meshes_with_owner(m):
    def visit(node, owner):
        if m.type(node) == b'CMapEntity': owner = m.cls(node).lower()
        if m.type(node) == b'CMapMesh': yield node, owner
        for c in m.children(node): yield from visit(c, owner)
    yield from visit(m.world, '')


def check(m, bounds, content=None, use_zfight=True, box=None):
    found = []
    def add(code, text, e=None, at=None):
        f = {'severity': SEV[code], 'code': code, 'text': text}
        if e is not None: f['node'] = m.g(e, b'nodeID')
        if at is not None: f['at'] = [round(x, 1) for x in at]
        found.append(f)
    inside = (lambda p: all(box[0][i] <= p[i] <= box[1][i] for i in range(3))) if box else (lambda p: True)

    props = []
    for e in m.entities():
        c = m.cls(e).lower(); model = m.P(e, 'model', '')
        if not model.lower().endswith('.vmdl') or not (c in PROP_CLASSES or c.startswith('prop_')) or c in PHYSICS: continue
        if m.P(e, 'parentname', ''): continue
        if 'cache' in m.name(e).lower(): continue          # precache rooms (vmapgen.cache_room): one hidden copy per model, out of play
        if m.P(e, 'renderamt', '255').strip() == '0' and m.P(e, 'solid', '6').strip() == '0': continue
        if not inside(m.origin(e)): continue
        props.append((e, model))
    got = bounds.get_many(sorted({mo for _, mo in props}))
    unknown = sorted({mo for _, mo in props if not got.get(mo)})
    if unknown: add('bounds_unknown', '%d models without readable bounds (first: %s)' % (len(unknown), ', '.join(unknown[:5])))
    frames = []
    for e, mo in props:
        b = got.get(mo)
        if b: frames.append((e, mo, frame(m, e, b[0], b[1])))

    tris = mapsanity.solid_triangles(m)
    grid = Grid()
    for t in tris:
        lo, hi = _tri_aabb(t); grid.add((t, lo, hi), lo, hi)
    pgrid = Grid()
    for item in frames: pgrid.add(item, item[2]['lo'], item[2]['hi'])

    for e, mo, f in frames:
        lo, hi = f['lo'], f['hi']
        # ---- buried: a solid face reaching DEPTH into the box (box shrunk by DEPTH on every side that is big enough)
        core = [max(h - DEPTH, 0.0) for h in f['half']]
        if all(c > 0 for c in core):
            near = grid.near([lo[i] - 1 for i in range(3)], [hi[i] + 1 for i in range(3)])
            natural = NATURAL.search(mo.lower())
            for t, tlo, thi in near:
                if tlo[2] > hi[2] or thi[2] < lo[2]: continue
                n = _cross(_sub(t[1], t[0]), _sub(t[2], t[0])); ln = math.sqrt(_dot(n, n)) or 1.0
                if abs(n[2]) / ln > 0.7 and (natural or max(p[2] for p in t) < lo[2] + (hi[2] - lo[2]) / 3):
                    continue                     # ground: bases sunk into floors and terrain are normal; plants and rocks may sink deep
                if tri_box([_local(f, p) for p in t], core):
                    add('prop_in_geometry', '%s at %s: a world / brush face cuts over %g u into it' % (mo, ' '.join('%g' % round(x) for x in m.origin(e)), DEPTH), e, f['centre'])
                    break
        # ---- floating: nothing under the base within SUPPORT_GAP, and no wall / ceiling contact
        base = lo[2]
        cx, cy = f['centre'][0], f['centre'][1]
        hx, hy = (hi[0] - lo[0]) / 4, (hi[1] - lo[1]) / 4
        samples = [(cx, cy), (cx - hx, cy - hy), (cx + hx, cy - hy), (cx + hx, cy + hy), (cx - hx, cy + hy)]
        best = None
        near = grid.near([lo[0] - 1, lo[1] - 1, base - 4096], [hi[0] + 1, hi[1] + 1, base + 1])
        for x, y in samples:
            for t, tlo, thi in near:
                if tlo[2] > base + CONTACT: continue
                z = mapsanity.z_at(t, x, y)
                if z is not None and z <= base + CONTACT and (best is None or z > best): best = z
        for e2, mo2, f2 in pgrid.near(lo, hi):
            if e2 == e: continue
            if f2['lo'][0] < hi[0] and f2['hi'][0] > lo[0] and f2['lo'][1] < hi[1] and f2['hi'][1] > lo[1] and f2['hi'][2] <= base + CONTACT:
                if best is None or f2['hi'][2] > best: best = f2['hi'][2]
        gap = None if best is None else base - best
        if gap is None or gap > SUPPORT_GAP:
            pad = [CONTACT] * 3
            touch = False
            for t, tlo, thi in grid.near([lo[i] - CONTACT for i in range(3)], [hi[i] + CONTACT for i in range(3)]):
                if tri_box([_local(f, p) for p in t], [f['half'][i] + pad[i] for i in range(3)]): touch = True; break
            if not touch:
                add('prop_floating', '%s at %s: base %s' % (mo, ' '.join('%g' % round(x) for x in m.origin(e)),
                    'over nothing within 4096 u' if gap is None else 'hangs %.0f u over the surface under it' % gap), e, f['centre'])
    # ---- props inside props
    seen = set()
    for e, mo, f in frames:
        for e2, mo2, f2 in pgrid.near(f['lo'], f['hi']):
            if e2 == e or (e2, e) in seen: continue
            seen.add((e, e2))
            ov = [min(f['hi'][i], f2['hi'][i]) - max(f['lo'][i], f2['lo'][i]) for i in range(3)]
            if max(f['half']) > 256 or max(f2['half']) > 256: continue    # architecture-sized models: their boxes overlap by design
            if mo == mo2 or NATURAL.search(mo.lower()) or NATURAL.search(mo2.lower()): continue   # rows / stacks of one model, foliage
            if all(o > DEPTH for o in ov):
                small = min(f['half'][0] * f['half'][1] * f['half'][2], f2['half'][0] * f2['half'][1] * f2['half'][2])
                if small > 0 and ov[0] * ov[1] * ov[2] / 8 > 0.5 * small:
                    add('prop_overlap', '%s and %s at %s share %s u' % (mo, mo2, ' '.join('%g' % round(x) for x in m.origin(e)),
                        ' x '.join('%.0f' % o for o in ov)), e, f['centre'])
    if use_zfight:
        import zfight
        pairs = zfight.find(m, content)
        for p in sorted(pairs, key=lambda p: -p['overlap'])[:400]:
            if box and not inside(p['at']): continue
            code = 'z_fighting' if p['a'][2] != p['b'][2] else 'z_fighting_same'
            add(code, '%s | %s at %s, %.0f sq u' % (p['a'][2], p['b'][2], ' '.join(map(str, p['at'])), p['overlap']), at=p['at'])
    for n, k, mat in open_meshes(m):
        pts = m.mesh_points(n)
        at = [sum(p[i] for p in pts) / len(pts) for i in range(3)] if pts else None
        if at is None or inside(at): add('open_mesh', 'mesh (%s) has %d open half-edges' % (mat, k), n, at)
    return found


def run(path, addon=None, use_zfight=True, box=None, bounds=None, limit=0):
    import fgdcat
    m = V.Map(path)
    addon = addon or fgdcheck.addon_of(path)
    cs2 = fgdcat.cs2_root()
    content = os.path.join(cs2, 'content', 'csgo_addons', addon) if addon else None
    mb = bounds or ModelBounds(cs2, addon)
    found = check(m, mb, content, use_zfight, box)
    if hasattr(mb, 'save'): mb.save()
    c = collections.Counter('%s/%s' % (f['severity'], f['code']) for f in found)
    return {'map': os.path.basename(path), 'addon': addon, 'warnings': sum(f['severity'] == 'warning' for f in found),
            'counts': dict(sorted(c.items())), 'findings': found[:limit] if limit else found}


def main(argv=None):
    ap = argparse.ArgumentParser(description='Read-only visual checks of a .vmap')
    ap.add_argument('vmap'); ap.add_argument('--json', action='store_true'); ap.add_argument('--addon')
    ap.add_argument('--no-zfight', action='store_true'); ap.add_argument('--limit', type=int, default=0); ap.add_argument('--box')
    a = ap.parse_args(argv)
    box = None
    if a.box:
        v = [float(x) for x in a.box.split(',')]; box = (v[:3], v[3:])
    try:
        res = run(a.vmap, a.addon, not a.no_zfight, box, limit=a.limit)
    except (OSError, ValueError) as ex:
        print('cannot read %s: %s' % (a.vmap, ex), file=sys.stderr); return 2
    if a.json: print(json.dumps(res, indent=1))
    else:
        for f in res['findings']: print('%s\t%s\t%s' % (f['severity'], f['code'], f['text']))
        print('# %s: %d warnings; %s' % (res['map'], res['warnings'], ', '.join('%s %d' % kv for kv in res['counts'].items()) or 'clean'))
    return 1 if res['warnings'] else 0


if __name__ == '__main__':
    sys.exit(main())
