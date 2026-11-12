"""Project-neutral gameplay checks on a vmap (offline; "simulated" in the words of docs/reference/compatibility.md).

Fork of projects/monsoon-cs2/tools/check_play.py (registered in create/libsync.json): the grid, walk graph, reach / pockets, routes,
line of sight, cover, clipping, water, terrain and nav checks are generic; everything that names a project's entities, models or
layout comes from an Adapter the project passes in. A project keeps a small tools/check_play.py:

    sys.path.insert(0, '<repo>/create'); import check_play as CP
    class MyMap(CP.Adapter):
        extent = (-6400, -5120, 6400, 5120)
        model_roots = [r'<content addon>']
        def worlds(self, ctx): return {'ct': ctx.points(r'spawn_ct_\\d+'), 't': ctx.points(r'spawn_t_\\d+')}
        ...
    sys.exit(CP.cli(MyMap()))

usage (through the adapter): check_play.py <map.vmap> [--json out.json] [--only 1,2,T1] [--verbose] [--map out.png [x0,y0,x1,y1]] [--nav-plan]

The scene is rebuilt from the vmap itself: world meshes (classified per face by material: terrain, world, player clip, water; tool
materials skipped, ladder volumes and nav markup kept aside), and every solid prop's physics hulls (the PhysicsHullFile / PhysicsMeshFile
SMDs its .vmdl names, under the adapter's model_roots); stock models collide as a trunk cylinder, a box, or not at all (Adapter.collide).
Everything is rasterised on a 16-u grid into
  surfaces  up-facing faces: where feet can be (several layers per cell)
  blockers  walls and undersides, widened by 12 u (a player is 32 wide): z intervals a body cannot overlap
and a directed walk graph is built over it (step up 18 u per cell, drops allowed, body 18..68 u above the feet must be free, ladder
volumes join the nodes beside them). Props the script removes at run time (Adapter.removable: blockers that open an area) are left out
of the graph ("open" state) and added back as extra blocked nodes ("closed" state, the round start).

 1 walkability   each world (Adapter.worlds: named point sets, e.g. one team's spawns) is one strongly connected component in the closed
                 state; worlds that must stay apart (Adapter.separate) do not reach each other; every target (Adapter.targets) is
                 reachable from its world and back in its state; stuck pockets (> 200 u2 a player can get into and never out of) with
                 and without a jump (54 u)
 1b routes       walking distance on the walk graph from a world to each route point (Adapter.routes); mirror pairs within 15 %
 2 sightlines    point sets that must not see each other (Adapter.no_sight); hard = solid geometry only
 3 cover         head-height (>= 62 u) cover pieces within a radius of each cover site (Adapter.cover_sites), crouch-height listed
 6 clipping      props buried (> 35 % of their bounds under the ground / inside world geometry), floating (> 6 u over any support),
                 tree crowns through buildings, non-solid dressing inside solid props, props under water that are not water props
 7 water         sheet edges above the ground (visible edge), sheets overlapping at one height (z-fight), deep walkable spots
 8 terrain       path slopes (Adapter.paths), ground through walk-in floors (Adapter.floors), terrain holes with nothing under them
 9 nav           WALKABLESEED boxes on walkable ground, NONAV boxes over no protected point (Adapter.nav_protect), ladder volumes
                 with walkable ground at the bottom and the top, and the walkable area the seeds flood (an estimate of the nav size).
                 Nav estimate and gate (when the adapter sets nav_cal or lists nav_stations / nav_routes, or with --nav-plan): the open
                 walk graph flooded from the seeds (Adapter.nav_seed_ok) and the worlds in Adapter.nav_starts with every node inside a
                 NONAV box taken out (what island removal leaves), in 16-u cells, m2 and nav areas projected linearly from a compile
                 (Adapter.nav_cal = dict(areas=, cells=)); fails when a station (Adapter.nav_stations) is off that nav or a bot route
                 (Adapter.nav_routes: world -> point) is lost or has no way back; warns over Adapter.nav_target areas or when a bot's
                 nav route is over Adapter.nav_detour x the walking route of the same label (1b)
    --nav-plan   check 9 with the boxes Adapter.planned_navboxes(sc) returns (the markup the generator would write now) instead of
                 the vmap's: a markup change measured before the map is regenerated
 project checks  Adapter.extra_checks(ctx): [(id, title, fn(ctx) -> dict(result, fail, warn, lines))]
Exit code 1 when a check fails. Numbers go to Adapter.out_json (or --json).
"""
import os, sys, json, math, glob, re, time, pickle
from collections import Counter, defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if os.path.join(REPO, 'tools') not in sys.path: sys.path.append(os.path.join(REPO, 'tools'))      # vmapedit, dmx (repo tools/)

K_TERRAIN, K_WORLD, K_CLIP, K_HULL, K_WATER, K_TRUNK = 0, 1, 2, 3, 4, 5
KIND_NAME = {K_TERRAIN: 'terrain', K_WORLD: 'world', K_CLIP: 'clip', K_HULL: 'hull', K_WATER: 'water', K_TRUNK: 'trunk'}
PADW = 12.0                    # blockers are widened by this (player half width 16, a little slack for doorways)
STEP, JUMP, BODY0, BODY1 = 18.0, 54.0, 18.5, 68.0

# grid globals, set by setup_grid() from the adapter's extent
CELL = 16.0
X0 = Y0 = 0.0
NX = NY = NC = 0


def setup_grid(extent, cell=16.0, margin=320.0):
    global CELL, X0, Y0, NX, NY, NC
    x0, y0, x1, y1 = extent
    CELL = float(cell); X0, Y0 = x0 - margin, y0 - margin
    NX, NY = int(math.ceil((x1 - x0 + 2 * margin) / CELL)), int(math.ceil((y1 - y0 + 2 * margin) / CELL))
    NC = NX * NY


def short(m):
    return m.split('/')[-1][:-5] if m.endswith('.vmdl') else m


def has(model, frags):
    return any(k in model for k in frags)


# ================================================================ the adapter
class Adapter:
    """What a project tells the checks. Override what applies; every hook gets the Ctx (see below) and returns plain data.
    Points are (name, x, y, z) tuples with z at the entity origin (a teleport destination or info_target a few units over the floor)."""
    name = 'map'
    extent = (-8192.0, -8192.0, 8192.0, 8192.0)     # play space x0, y0, x1, y1 (the grid adds a 320-u margin)
    cell = 16.0
    model_roots = []            # folders a model path resolves under (content addon first): .vmdl text and the SMDs it names
    vpk_dir = None              # folder with pak01_dir.vpk: stock model bounds are measured from it (create/s2/bounds_batch.mjs)
    cache_dir = None            # scene cache and measured stock bounds (default: the system temp folder)
    out_json = None             # numbers of the last run
    terrain_mats = ()           # material fragments that are terrain (a terrain face is never a blocker: its slope is the walk test)
    water_mats = ('water',)
    skip_mats = ('toolstrigger', 'toolslightmapres', 'toolsskybox', 'toolsblocklight', 'toolsfog', 'toolsskip', 'toolshint',
                 'toolsoccluder', 'toolsbuyzone', 'toolsbombsite', 'toolsnpcclip', 'toolsavoidance')
    clip_mats = ('toolsplayerclip', 'toolsclip')
    skip_classes = ('trigger_', 'func_buyzone', 'func_bomb_target', 'func_nav_blocker', 'env_', 'post_processing_volume', 'visibility_hint',
                    'func_illusionary', 'cs_minimap_boundary', 'light_')
    removable = ()              # targetnames of props the script removes during a round (area blockers): the "open" state lacks them
    foliage = ('foliage', 'weeds', 'grass', 'leaves', 'bush', 'shrub', 'fern')
    trees = ('tree',)
    buildings = ()
    water_ok = ()               # model fragments allowed under water
    stack_models = ('sandbag',) # cover: stacked courses of these count as one piece per 96-u column
    floors = {}                 # walk-in props: short model name -> local floor rect (x0, y0, x1, y1, z) the ground must stay under
    trunk_r = {'poplar': 12, 'maple': 14, 'beech': 9, 'oak': 16, 'pine': 10, 'palm': 10}   # stock tree trunks by name fragment
    no_collide = ('foliage/weeds', 'foliage/ground', 'grass', 'weed', 'leaves', 'bush', 'shrub', 'dogwood', 'viburnum', 'fern', '_vista')
    box_collide = ('rock', 'boulder', 'cliff')   # stock models that collide as 80 % of their bounds
    path_max_slope = 20.0
    bury_min_h = 10.0           # props lower than this (debris, helmets) are not tested for burying: sinking them in is dressing
    float_reach = 400.0         # a support further below than this is another level (a room under the map), not the ground
    water_edge_tol = 0.5        # a sheet edge this far over the ground counts as touching it

    # ---- scene
    def skip_mesh(self, lo, hi, mats):
        """True: leave this mesh out of the scene entirely (a lobby far below, a skybox shell)"""
        return False

    def skip_entity(self, e):
        return False

    def collide(self, model):
        """'hull' (ours: the vmdl's physics files), 'trunk', 'box' or None for a stock model; None = no collision"""
        if any(model.startswith(r) for r in ()): return 'hull'
        if has(model, self.no_collide): return None
        if any(k in model for k in self.trunk_r): return 'trunk'
        if has(model, self.box_collide): return 'box'
        return 'box'

    def trunk_radius(self, model):
        for k, r in self.trunk_r.items():
            if k in model: return float(r)
        return 10.0

    # ---- checks (all optional)
    def inplay(self, x, y, z):
        x0, y0, x1, y1 = self.extent
        return x0 - 200 <= x <= x1 + 200 and y0 - 200 <= y <= y1 + 200

    def worlds(self, ctx): return {}
    def separate(self, ctx): return []
    def targets(self, ctx): return []
    def routes(self, ctx): return []
    def mirror_pairs(self, ctx): return []
    def no_sight(self, ctx): return []
    def cover_sites(self, ctx): return []
    def clip_tag(self, p): return None
    def paths(self, ctx): return []
    def nav_protect(self, ctx): return []
    # ---- nav estimate and gate (check 9; all optional, see the docstring)
    nav_cal = None              # dict(areas=N, cells=M) from a compile ("Nav mesh ... loaded with N nav areas" against M flooded cells)
    nav_target = None           # warn above this many estimated nav areas
    nav_detour = 1.35           # warn when a bot's nav route is this much longer than the walking route of the same 1b label
    def nav_stations(self, ctx): return []      # (name, x, y, z[, rxy, rz, dz]) that must be on the nav (default radii 48 / 40, dz -8)
    def nav_routes(self, ctx): return []        # (label, world, (x, y, z)): bots must route from the world's start nodes there and back
    def nav_starts(self, ctx): return []        # world labels whose start nodes also start the flood (bots spawn there)
    def nav_seed_ok(self, box): return True     # False: a WALKABLESEED box left out of the flood (one in a lobby far below the map)
    def planned_navboxes(self, sc): return None # --nav-plan: [(prop, name, (x0, y0, z0, x1, y1, z1))] the generator would write now
    def water_edge_ok(self, x, y, z): return False
    def hole_ok(self, x, y): return False
    def extra_checks(self, ctx): return []


# ================================================================ geometry sources
_SMD = {}


def smd_tris(path, scale=1.0):
    """triangles of an SMD in Hammer model space: (N, 3, 3) positions, wound outward (SMD (x, y, z) -> Hammer (-y, x, z), the convention
    of the repo's prop builders and converters)"""
    k = (path, scale)
    if k in _SMD: return _SMD[k]
    V = []; Nn = []
    tri = False
    for l in open(path, errors='ignore'):
        s = l.strip()
        if s == 'triangles': tri = True; continue
        if not tri: continue
        q = s.split()
        if len(q) >= 9 and q[0].lstrip('-').isdigit():
            try:
                V.append((-float(q[2]), float(q[1]), float(q[3]))); Nn.append((-float(q[5]), float(q[4]), float(q[6])))
            except ValueError: pass
    n = len(V) // 3
    if not n: _SMD[k] = np.zeros((0, 3, 3)); return _SMD[k]
    T = np.array(V[:n * 3], float).reshape(n, 3, 3) * scale; N = np.array(Nn[:n * 3], float).reshape(n, 3, 3).mean(1)
    fn = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    flip = (fn * N).sum(1) < 0
    T[flip] = T[flip][:, ::-1]
    _SMD[k] = T
    return T


_PH = {}


def phys_tris(path, scale=1.0, mode='SingleHull'):
    """collision triangles of one physics file as the compiler builds it: a PhysicsHullFile is convex (SingleHull: one hull round
    every vertex in the file; HullPerElement: one per connected piece), a PhysicsMeshFile is the triangles as they are. 12 Nov 2026:
    an arch-shaped shelter hull in one SingleHull file is a solid lump in game, so the raw triangles under-report what blocks."""
    k = (path, scale, mode)
    if k in _PH: return _PH[k]
    T = smd_tris(path, scale)
    if mode == 'mesh' or len(T) < 2: _PH[k] = T; return T
    pieces = [T.reshape(-1, 3)]
    if mode != 'SingleHull':
        # connected pieces by shared (rounded) vertex positions
        V = np.round(T.reshape(-1, 3), 2); _, inv = np.unique(V, axis=0, return_inverse=True); inv = inv.ravel()
        par = list(range(inv.max() + 1))
        def f_(a):
            while par[a] != a: par[a] = par[par[a]]; a = par[a]
            return a
        for t in inv.reshape(-1, 3):
            a, b, c = f_(t[0]), f_(t[1]), f_(t[2]); par[b] = a; par[f_(c)] = a
        root = np.array([f_(v) for v in inv]).reshape(-1, 3)[:, 0]
        pieces = [T[root == r].reshape(-1, 3) for r in np.unique(root)]
    out = []
    from scipy.spatial import ConvexHull
    for P in pieces:
        P = np.unique(np.round(P, 3), axis=0)
        if len(P) < 4: continue
        try: h = ConvexHull(P)
        except Exception:
            try: h = ConvexHull(P, qhull_options='QJ')
            except Exception: continue
        S = P[h.simplices]
        n = np.cross(S[:, 1] - S[:, 0], S[:, 2] - S[:, 0])
        flip = (n * h.equations[:, :3]).sum(1) < 0
        S[flip] = S[flip][:, ::-1]
        out.append(S)
    _PH[k] = np.concatenate(out) if out else T
    return _PH[k]


def box_tris(lo, hi):
    x0, y0, z0 = lo; x1, y1, z1 = hi
    c = np.array([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], float)
    q = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return np.array([[c[a], c[b], c[d]] for (a, b, d_, e) in q for (a, b, d) in ((a, b, d_), (a, d_, e))])


_DEPS = None                   # while load_scene builds a scene: rel path -> the file it resolved to (or None), for the cache check


def resolve(A, rel):
    out = None
    for r in A.model_roots:
        p = os.path.join(r, rel.replace('/', os.sep))
        if os.path.isfile(p): out = p; break
    if _DEPS is not None: _DEPS[rel] = out
    return out


def _file_sig(p):
    if p is None: return None
    try: st = os.stat(p); return (p, st.st_size, st.st_mtime_ns)
    except OSError: return (p, -1, -1)


def _deps_current(A, deps):
    """True when every model path the cached scene resolved still resolves to the same file, unchanged (a model rebuilt in the
    staging folder, a model newly staged, a different --stage)"""
    for rel, sig in deps.items():
        p = None
        for r in A.model_roots:
            q = os.path.join(r, rel.replace('/', os.sep))
            if os.path.isfile(q): p = q; break
        if _file_sig(p) != (tuple(sig) if sig else None): return False
    return True


def scene_key(path, A):
    """what a cached scene depends on besides the model files: the vmap (its full path, size and time), this file, the adapter's
    file, the grid and the model roots. 12 Nov 2026: the key was the adapter name + the vmap's size and whole-second time only, so a
    scene built without --stage (tools/patch_nav.py --estimate) was served to a later --stage run of the same map (a false
    'separation' failure: the content addon's older models), and each new map evicted every other map's scene."""
    import hashlib, inspect
    st = os.stat(path)
    try: af = inspect.getsourcefile(type(A)) or ''
    except Exception: af = ''
    parts = [A.name, os.path.normcase(os.path.abspath(path)), st.st_size, st.st_mtime_ns, os.stat(os.path.abspath(__file__)).st_mtime_ns,
             (os.path.normcase(os.path.abspath(af)), os.stat(af).st_mtime_ns) if af and os.path.isfile(af) else '', list(map(float, A.extent)), float(A.cell),
             [os.path.normcase(os.path.abspath(r)) for r in A.model_roots], type(A).__name__]
    return '%s_%s' % (A.name, hashlib.sha1(repr(parts).encode()).hexdigest()[:20])


def vmdl_files(A, model):
    """(render SMDs, [(physics SMD, scale)], model_archetype) named by a .vmdl under the model roots; None if the vmdl is not there"""
    p = resolve(A, model)
    if p is None: return None
    t = open(p, encoding='utf-8', errors='ignore').read()
    phys = []; render = []
    for m in re.finditer(r'_class\s*=\s*"(PhysicsHullFile|PhysicsMeshFile|RenderMeshFile)"', t):
        nxt = t.find('_class', m.end())
        blk = t[m.end(): nxt if nxt > 0 else len(t)]
        f = re.search(r'filename\s*=\s*"([^"]+)"', blk); s = re.search(r'import_scale\s*=\s*([-\d.eE]+)', blk)
        md = re.search(r'import_mode\s*=\s*"([^"]*)"', blk)
        if not f: continue
        fp = resolve(A, f.group(1))
        if fp is None or not fp.lower().endswith('.smd'): continue
        sc = float(s.group(1)) if s else 1.0
        if m.group(1) == 'RenderMeshFile': render.append((fp, sc))
        else: phys.append((fp, sc, 'mesh' if m.group(1) == 'PhysicsMeshFile' else (md.group(1) if md else 'SingleHull')))
    a = re.search(r'model_archetype\s*=\s*"([^"]*)"', t)
    return render, phys, (a.group(1) if a else '')


class Bounds:
    """model -> (lo, hi) in model units: ours from the render SMD (first LOD), stock from the VPK (measured once, cached)"""
    def __init__(self, A, stock_models):
        self.A = A; self.c = {}
        self.stock = {}
        cd = cache_dir(A)
        cp = os.path.join(cd, 'stock_bounds.json')
        have = json.load(open(cp)) if os.path.exists(cp) else {}
        need = [m for m in sorted(stock_models) if m not in have]
        if need and A.vpk_dir and os.path.exists(os.path.join(A.vpk_dir, 'pak01_dir.vpk')):
            import subprocess, tempfile
            lst = os.path.join(cd, 'stock_list.json'); out = os.path.join(cd, 'stock_out.json')
            json.dump([{'path': m + '_c', 'vpk': A.vpk_dir} for m in need], open(lst, 'w'))
            subprocess.run(['node', os.path.join(HERE, 's2', 'bounds_batch.mjs'), lst, out], capture_output=True, text=True)
            if os.path.exists(out):
                for k, v in json.load(open(out)).items():
                    have[k[:-2]] = v if 'lo' in v else None
                json.dump(have, open(cp, 'w'))
        for m, v in have.items():
            if v: self.stock[m] = (tuple(v['lo']), tuple(v['hi']))

    def __call__(self, model):
        if model in self.c: return self.c[model]
        r = None
        if model in self.stock: r = self.stock[model]
        else:
            vf = vmdl_files(self.A, model)
            if vf and vf[0]:
                T = np.concatenate([smd_tris(f, s).reshape(-1, 3) for f, s in vf[0][:1]])
                if len(T): r = (tuple(T.min(0)), tuple(T.max(0)))
            if r is None and vf and vf[1]:
                T = np.concatenate([smd_tris(f[0], f[1]).reshape(-1, 3) for f in vf[1]])
                if len(T): r = (tuple(T.min(0)), tuple(T.max(0)))
        if r is None: r = ((-12.0, -12.0, 0.0), (12.0, 12.0, 24.0))
        self.c[model] = r
        return r


def cache_dir(A):
    d = A.cache_dir or os.path.join(os.environ.get('TEMP', '/tmp'), 'check_play_cache')
    os.makedirs(d, exist_ok=True)
    return d


def rot_matrix(ang):
    p, y, r = (math.radians(a) for a in ang)
    cp, sp, cy, sy, cr, sr = math.cos(p), math.sin(p), math.cos(y), math.sin(y), math.cos(r), math.sin(r)
    return np.array([[cp * cy, sp * sr * cy - cr * sy, sp * cr * cy + sr * sy], [cp * sy, sp * sr * sy + cr * cy, sp * cr * sy - sr * cy], [-sp, cp * sr, cp * cr]])


def _s(v):
    return v.decode() if isinstance(v, bytes) else (v if isinstance(v, str) else '')


def load_scene(path, A, verbose=False):
    """entities + triangle soup of the vmap, cached by scene_key() (map path / size / time, model roots, this file and the adapter's)
    and checked against every model file the scene was built from"""
    global _DEPS
    key = scene_key(path, A)
    cp = os.path.join(cache_dir(A), 'play_scene_%s.pkl' % key)
    if os.path.exists(cp):
        try:
            sc_ = pickle.load(open(cp, 'rb'))
            if isinstance(sc_.get('deps'), dict) and _deps_current(A, sc_['deps']):
                sc_['cached'] = True
                if verbose: print('  scene from the cache %s' % os.path.basename(cp))
                return sc_
            if verbose: print('  cached scene is stale (a model file changed): rebuilding')
        except Exception: pass
    _DEPS = {}
    try:
        sc_ = _build_scene(path, A, verbose, key)
        deps = {rel: _file_sig(p) for rel, p in sorted(_DEPS.items())}
    finally:
        _DEPS = None
    sc_['deps'] = deps
    sc_['model_roots'] = list(A.model_roots)
    tmp = cp + '.%d.tmp' % os.getpid()
    pickle.dump(sc_, open(tmp, 'wb'), protocol=4)
    os.replace(tmp, cp)
    # keep the 4 newest scenes of this adapter (a chain checks several maps, with and without a staging folder)
    old = sorted(glob.glob(os.path.join(cache_dir(A), 'play_scene_%s_*.pkl' % A.name)), key=lambda f: os.path.getmtime(f), reverse=True)
    for f in old[4:]:
        try: os.remove(f)
        except OSError: pass
    sc_['cached'] = False
    return sc_


def _build_scene(path, A, verbose, key):
    import vmapedit as V
    t0 = time.time()
    m = V.Map(path)
    par = m.parent_of()
    ents = []
    for e in m.entities():
        o = m.origin(e)
        ents.append(dict(i=e, cls=m.cls(e), name=m.name(e), model=m.P(e, 'model', '') or '', o=tuple(float(v) for v in o),
                         a=tuple(float(v) for v in m.g(e, b'angles', [0, 0, 0])), s=tuple(float(v) for v in (m.g(e, b'scales', None) or (1, 1, 1))),
                         solid=str(m.P(e, 'solid', '') or ''), msg=m.P(e, 'message', '') or '', vg=_s(m.g(e, b'customVisGroup', b'')),
                         nav=m.P(e, 'navProperty_NavGen', '') or '', parent=m.P(e, 'parentname', '') or ''))
    stock = {r['model'] for r in ents if r['model'].endswith('.vmdl') and resolve(A, r['model']) is None}
    B = Bounds(A, stock)
    # ---- world meshes
    tris = []; kinds = []; srcs = []; meshes = []; ladders = []; navboxes = []
    for n, _ in m.walk():
        if m.type(n) != b'CMapMesh': continue
        md = m.g(n, b'meshData')
        if md is None or md < 0: continue
        p_ = par.get(n); pcls = m.cls(p_) if p_ is not None and m.type(p_) == b'CMapEntity' else ''
        mats = [x.decode().lower() for x in m.g(md, b'materials') or []]
        pos = None
        for st_ in m.g(m.g(md, b'vertexData'), b'streams') or []:
            if m.E[st_]['name'].startswith(b'position'): pos = m.g(st_, b'data')
        fd = m.g(md, b'faceData'); mi = None
        for st_ in m.g(fd, b'streams') or []:
            if m.E[st_]['name'].startswith(b'materialindex'): mi = m.g(st_, b'data')
        fei, evi, nxt, vdi, fdi = (m.g(md, k) for k in (b'faceEdgeIndices', b'edgeVertexIndices', b'edgeNextIndices', b'vertexDataIndices', b'faceDataIndices'))
        if pos is None or fei is None: continue
        o = m.g(n, b'origin', [0, 0, 0]); a = m.g(n, b'angles', [0, 0, 0]); sc = m.g(n, b'scales', [1, 1, 1])
        P = np.array(pos, float) * np.array(sc, float)              # a tied mesh's origin is in world space too (func_brush checked, Nov 2026)
        if any(a): P = P @ rot_matrix(a).T
        P = P + np.array(o, float)
        lo, hi = P.min(0).tolist(), P.max(0).tolist()
        vg = _s(m.g(n, b'customVisGroup', b'')) or (_s(m.g(p_, b'customVisGroup', b'')) if p_ is not None else '')
        if A.skip_mesh(lo, hi, mats): continue
        mat0 = mats[0] if mats else ''
        if 'toolsnavattribute' in mat0 or pcls == 'func_nav_markup':
            prop = m.P(p_, 'navProperty_NavGen', '') if p_ is not None else ''
            navboxes.append((prop, m.name(p_) if p_ is not None else '', lo + hi)); continue
        if 'toolsinvisibleladder' in mat0:
            ladders.append(dict(box=lo + hi, vg=vg, node=n, mat=mat0)); continue
        if pcls and any(pcls.startswith(c) for c in A.skip_classes): continue
        is_water = any(any(w in mm for w in A.water_mats) for mm in mats)
        def kind_of(mat):
            if any(c in mat for c in A.clip_mats): return K_CLIP
            if 'toolsnodraw' in mat: return None if is_water else K_WORLD
            if any(c in mat for c in A.skip_mats) or 'materials/tools/' in mat: return None
            if any(w in mat for w in A.water_mats): return K_WATER
            if any(t in mat for t in A.terrain_mats): return K_TERRAIN
            return K_WORLD
        fk = [kind_of(mm) for mm in mats] or [K_WORLD]
        mid = len(meshes)
        kinds_here = set()
        for f, he in enumerate(fei):
            fi = fdi[f] if fdi and f < len(fdi) else f
            k = fk[mi[fi]] if mi is not None and fi < len(mi) and 0 <= mi[fi] < len(fk) else fk[0]
            if k is None: continue
            loop = []; h = he
            for _ in range(64):
                loop.append(vdi[evi[h]]); h = nxt[h]
                if h == he: break
            for kk in range(1, len(loop) - 1):
                tris.append((P[loop[0]], P[loop[kk]], P[loop[kk + 1]])); kinds.append(k); srcs.append(-1 - mid)
            kinds_here.add(k)
        if not kinds_here: continue
        kind = K_WATER if K_WATER in kinds_here else K_TERRAIN if K_TERRAIN in kinds_here else K_CLIP if kinds_here == {K_CLIP} else K_WORLD
        meshes.append(dict(kind=kind, mat=mat0, lo=lo, hi=hi, mats=mats, node=n, vg=vg, parent=pcls, pname=m.name(p_) if p_ is not None else ''))
    if verbose: print('  meshes: %d (%d tris) %.1fs' % (len(meshes), len(tris), time.time() - t0))
    # ---- props: hull triangles, trunks, visual bounds
    props = []; trunks = []
    for i, r in enumerate(ents):
        if r['cls'] not in ('prop_static', 'prop_dynamic', 'prop_physics', 'prop_physics_override', 'prop_dynamic_override') or not r['model'].endswith('.vmdl'): continue
        if A.skip_entity(r): continue
        lo, hi = B(r['model']); R = rot_matrix(r['a']); sc = np.array(r['s'])
        c8 = np.array([(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])], float) * sc
        w8 = c8 @ R.T + np.array(r['o'])
        if A.skip_mesh(w8.min(0).tolist(), w8.max(0).tolist(), []): continue
        ours = resolve(A, r['model']) is not None
        solid = r['solid'] != '0'
        p = dict(i=i, model=r['model'], name=r['name'], o=r['o'], a=r['a'], yaw=r['a'][1], s=r['s'], lo=w8.min(0).tolist(), hi=w8.max(0).tolist(), solid=solid,
                 cls=r['cls'], vg=r['vg'], mlo=list(lo), mhi=list(hi), poly=[(w8[k][0], w8[k][1]) for k in (0, 4, 6, 2)], hull=None, ours=ours,
                 removable=r['name'] in A.removable and r['name'] != '')
        if solid:
            if ours:
                vf = vmdl_files(A, r['model'])
                T0 = np.concatenate([phys_tris(*f) for f in vf[1]]) if vf and vf[1] else np.zeros((0, 3, 3))
                if len(T0):
                    T = (T0 * sc) @ R.T + np.array(r['o'])
                    p['hull'] = 'tris'
                    for t in T: tris.append((t[0], t[1], t[2])); kinds.append(K_HULL); srcs.append(len(props))
                else: p['solid'] = False                        # no physics in the vmdl: nothing to bump into
            else:
                c = A.collide(r['model'])
                if c == 'trunk':
                    p['hull'] = 'trunk'; trunks.append((r['o'][0], r['o'][1], r['o'][2] - 10.0, r['o'][2] + hi[2] * r['s'][2], A.trunk_radius(r['model']) * r['s'][0], len(props)))
                elif c == 'box':
                    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
                    T0 = box_tris((cx + (lo[0] - cx) * 0.8, cy + (lo[1] - cy) * 0.8, lo[2]), (cx + (hi[0] - cx) * 0.8, cy + (hi[1] - cy) * 0.8, lo[2] + (hi[2] - lo[2]) * 0.85))
                    T = (T0 * sc) @ R.T + np.array(r['o'])
                    p['hull'] = 'tris'
                    for t in T: tris.append((t[0], t[1], t[2])); kinds.append(K_HULL); srcs.append(len(props))
                else: p['solid'] = False
        props.append(p)
    sc_ = dict(ents=ents, tris=np.array(tris, float).reshape(-1, 3, 3), kinds=np.array(kinds, np.int8), srcs=np.array(srcs, np.int64), meshes=meshes,
               props=props, trunks=trunks, ladders=ladders, navboxes=navboxes, key=key, stock=sorted(stock), stock_measured=sorted(B.stock))
    if verbose: print('  scene: %d tris, %d props, %.1fs' % (len(tris), len(props), time.time() - t0))
    return sc_


# ================================================================ rasteriser
def raster(T, expand=0.0, chunk=3000000):
    """triangles (N, 3, 3) -> per covered cell centre: (tri index, flat cell, z of the plane there, zlo, zhi over the widened cell)"""
    N = len(T)
    if N == 0: return [np.zeros(0, np.int64)] * 2 + [np.zeros(0)] * 3
    x = T[:, :, 0]; y = T[:, :, 1]; z = T[:, :, 2]
    ix0 = np.ceil((x.min(1) - expand - X0) / CELL - 0.5).astype(np.int64); ix1 = np.floor((x.max(1) + expand - X0) / CELL - 0.5).astype(np.int64)
    iy0 = np.ceil((y.min(1) - expand - Y0) / CELL - 0.5).astype(np.int64); iy1 = np.floor((y.max(1) + expand - Y0) / CELL - 0.5).astype(np.int64)
    w = ix1 - ix0 + 1; h = iy1 - iy0 + 1
    nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    area2 = nrm[:, 2]
    elen = np.stack([np.hypot(x[:, (k + 1) % 3] - x[:, k], y[:, (k + 1) % 3] - y[:, k]) for k in range(3)], 1)
    degen = np.abs(area2) < 1e-3 * np.maximum(elen.max(1), 1e-6) ** 2 + 1e-9
    zmin = z.min(1); zmax = z.max(1)
    out = [[], [], [], [], []]
    size = np.maximum(w, h)
    ok = (w > 0) & (h > 0)
    for k in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 4096):
        sel = np.nonzero(ok & (size <= k) & (size > k // 2 if k > 1 else True))[0]
        if k == 4096: sel = np.nonzero(ok & (size > 1024))[0]
        if not len(sel): continue
        kk = int(size[sel].max()) if k == 4096 else k
        per = max(1, chunk // (kk * kk))
        for c0 in range(0, len(sel), per):
            s = sel[c0:c0 + per]
            dx = np.arange(kk)[None, :, None]; dy = np.arange(kk)[None, None, :]
            gx = ix0[s, None, None] + dx; gy = iy0[s, None, None] + dy
            valid = (dx < w[s, None, None]) & (dy < h[s, None, None]) & (gx >= 0) & (gx < NX) & (gy >= 0) & (gy < NY)
            px = X0 + (gx + 0.5) * CELL; py = Y0 + (gy + 0.5) * CELL
            sg = np.where(area2[s] >= 0, 1.0, -1.0)[:, None, None]
            ins = valid & ~degen[s, None, None]
            for e in range(3):
                ax = x[s, e][:, None, None]; ay = y[s, e][:, None, None]; bx = x[s, (e + 1) % 3][:, None, None]; by = y[s, (e + 1) % 3][:, None, None]
                ln = np.maximum(elen[s, e][:, None, None], 1e-9)
                d = ((bx - ax) * (py - ay) - (by - ay) * (px - ax)) / ln * sg
                ins &= d >= -expand - 1e-4
            if expand > 0:
                dg = np.nonzero(degen[s])[0]
                if len(dg):                              # vertical faces: distance to the longest edge
                    e = elen[s[dg]].argmax(1)
                    ax = x[s[dg], e][:, None, None]; ay = y[s[dg], e][:, None, None]; bx = x[s[dg], (e + 1) % 3][:, None, None]; by = y[s[dg], (e + 1) % 3][:, None, None]
                    l2 = np.maximum((bx - ax) ** 2 + (by - ay) ** 2, 1e-9)
                    t = np.clip(((px[dg] - ax) * (bx - ax) + (py[dg] - ay) * (by - ay)) / l2, 0, 1)
                    dd = np.hypot(px[dg] - (ax + t * (bx - ax)), py[dg] - (ay + t * (by - ay)))
                    ins[dg] = valid[dg] & (dd <= expand)
            nz = np.where(np.abs(nrm[s, 2]) < 1e-9, 1e-9, nrm[s, 2])
            gxz = (-nrm[s, 0] / nz)[:, None, None]; gyz = (-nrm[s, 1] / nz)[:, None, None]
            zc = z[s, 0][:, None, None] + gxz * (px - x[s, 0][:, None, None]) + gyz * (py - y[s, 0][:, None, None])
            zc = np.clip(zc, zmin[s, None, None], zmax[s, None, None])
            gr = np.minimum(np.hypot(gxz, gyz) * (expand + CELL * 0.5), (zmax - zmin)[s, None, None])
            gr = np.where(degen[s, None, None], (zmax - zmin)[s, None, None], gr)
            zl = np.maximum(zc - gr, zmin[s, None, None]); zh = np.minimum(zc + gr, zmax[s, None, None])
            zl = np.where(degen[s, None, None], zmin[s, None, None], zl); zh = np.where(degen[s, None, None], zmax[s, None, None], zh)
            ii = np.nonzero(ins)
            out[0].append(s[ii[0]]); out[1].append((gx[ii[0], ii[1], 0] * NY + gy[ii[0], 0, ii[2]]).astype(np.int64))
            out[2].append(zc[ins]); out[3].append(zl[ins]); out[4].append(zh[ins])
    return [np.concatenate(o) if o else np.zeros(0, np.int64 if i < 2 else float) for i, o in enumerate(out)]


def cell_of(x, y):
    """grid cell index, -1 outside the grid (a point past the y edge must not wrap into the next column)"""
    i = int((x - X0) // CELL); j = int((y - Y0) // CELL)
    return i * NY + j if 0 <= i < NX and 0 <= j < NY else -1


def cell_xy(c):
    return X0 + (c // NY + 0.5) * CELL, Y0 + (c % NY + 0.5) * CELL


def node_xyz(G, n):
    k, c = divmod(int(n), NC)
    x, y = cell_xy(c)
    return x, y, float(G.Z[k, c])


class Grid:
    """surfaces, blockers and the walk graph (open state: props in sc['props'] marked removable are left out)"""
    def __init__(self, sc, verbose=False):
        t0 = time.time()
        rem = np.array([p['removable'] for p in sc['props']] + [False], bool)
        T = sc['tris']; kinds = sc['kinds']; srcs = sc['srcs']
        keep = ~((srcs >= 0) & rem[np.clip(srcs, 0, len(rem) - 1)] & (srcs < len(sc['props'])))
        self.rem_tris = T[~keep]
        T = T[keep]; kinds = kinds[keep]; srcs = srcs[keep]
        self.T, self.T_kind, self.T_src = T, kinds, srcs
        nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); nl = np.linalg.norm(nrm, axis=1); nzu = nrm[:, 2] / np.maximum(nl, 1e-12)
        self.sc = sc
        solidk = (kinds != K_WATER)
        up = (nzu > 0.05) & solidk & (nl > 1e-9)
        ti, cl, zc, _, _ = raster(T[up], 0.0)
        idx = np.nonzero(up)[0][ti]
        self.s_cell, self.s_z, self.s_kind, self.s_src, self.s_nz = cl, zc, kinds[idx], srcs[idx], nzu[idx]
        blk = (nzu <= 0.05) & solidk & (kinds != K_TERRAIN) & (nl > 1e-9)
        ti, cl, zc, zl, zh = raster(T[blk], PADW)
        idx = np.nonzero(blk)[0][ti]
        b_cell, b_lo, b_hi, b_src, b_kind = [cl], [zl], [zh], [srcs[idx]], [kinds[idx]]
        for (x, y, z0, z1, r, pi) in sc['trunks']:
            if sc['props'][pi]['removable']: continue
            c, lo_, hi_ = self.disc(x, y, r + PADW)
            b_cell.append(c); b_lo.append(np.full(len(c), z0)); b_hi.append(np.full(len(c), z1)); b_src.append(np.full(len(c), pi)); b_kind.append(np.full(len(c), K_TRUNK, np.int8))
        self.b_cell = np.concatenate(b_cell); self.b_lo = np.concatenate(b_lo); self.b_hi = np.concatenate(b_hi); self.b_src = np.concatenate(b_src); self.b_kind = np.concatenate(b_kind)
        # water level per cell
        wt = kinds == K_WATER
        ti, cl, zc, _, _ = raster(T[wt], 0.0)
        self.water = np.full(NC, -1e9); np.maximum.at(self.water, cl, zc)
        self.w_cell, self.w_z, self.w_src = cl, zc, srcs[np.nonzero(wt)[0][ti]]
        # terrain top per cell (the mesh)
        self.terr = np.full(NC, -1e9); tm = self.s_kind == K_TERRAIN
        np.maximum.at(self.terr, self.s_cell[tm], self.s_z[tm])
        # ---- nodes: cluster the surfaces of each cell by height (12 u), highest first
        o = np.lexsort((-self.s_z, self.s_cell)); c = self.s_cell[o]; z = self.s_z[o]; kd = self.s_kind[o]; sr = self.s_src[o]; nzz = self.s_nz[o]
        newc = np.r_[True, c[1:] != c[:-1]]
        keepn = np.ones(len(o), bool); layer = np.zeros(len(o), np.int64)
        cl_ = c.tolist(); zl_ = z.tolist()
        last_c = -1; last_z = 0.0; lay = 0
        for i in range(len(cl_)):
            if cl_[i] != last_c: last_c = cl_[i]; last_z = zl_[i]; lay = 0
            elif last_z - zl_[i] > 12.0: last_z = zl_[i]; lay += 1
            else: keepn[i] = False
            layer[i] = lay
        self.K = K = int(min(layer[keepn].max() + 1, 10)) if keepn.any() else 1
        k_ = keepn & (layer < K)
        self.Z = np.full((K, NC), -np.inf); self.Z[layer[k_], c[k_]] = z[k_]
        self.kind = np.full((K, NC), -1, np.int8); self.kind[layer[k_], c[k_]] = kd[k_]
        self.src = np.full((K, NC), 0, np.int64); self.src[layer[k_], c[k_]] = sr[k_]
        self.nz = np.zeros((K, NC)); self.nz[layer[k_], c[k_]] = nzz[k_]
        self.exists = np.isfinite(self.Z)
        self.blocked = self.blocked_by(self.b_cell, self.b_lo, self.b_hi, self.b_src, BODY0)
        self.walk = self.graph(STEP); self.jump = None
        self.blocked_jump = self.blocked_by(self.b_cell, self.b_lo, self.b_hi, None, JUMP + 0.5)
        self._closed = None
        if verbose: print('  grid %dx%d: %d surface samples, %d blocker samples, %d layers, %d nodes, %.1fs' % (NX, NY, len(self.s_z), len(self.b_cell), K, int(self.exists.sum()), time.time() - t0))

    def disc(self, x, y, rr):
        i0 = int((x - rr - X0) // CELL); i1 = int((x + rr - X0) // CELL); j0 = int((y - rr - Y0) // CELL); j1 = int((y + rr - Y0) // CELL)
        ii, jj = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1), indexing='ij')
        ok = (np.hypot(X0 + (ii + 0.5) * CELL - x, Y0 + (jj + 0.5) * CELL - y) <= rr) & (ii >= 0) & (ii < NX) & (jj >= 0) & (jj < NY)
        c = (ii[ok] * NY + jj[ok]).astype(np.int64)
        if not len(c):
            c0 = cell_of(x, y); c = np.array([c0] if c0 >= 0 else [], np.int64)
        return c, None, None

    def blocked_by(self, b_cell, b_lo, b_hi, b_src, body0):
        K = self.K
        bl = np.zeros((K, NC), bool)
        if b_src is not None: self.blk_src = np.full((K, NC), -10 ** 9, np.int64)
        for k in range(K):
            zk = self.Z[k, b_cell]
            hit = (b_lo < zk + BODY1) & (b_hi > zk + body0)
            bl[k, b_cell[hit]] = True
            if b_src is not None: self.blk_src[k, b_cell[hit]] = b_src[hit]
            for j in range(k):
                d = self.Z[j] - self.Z[k]
                cz = self.exists[k] & (d > body0) & (d < BODY1)
                bl[k] |= cz
                if b_src is not None: self.blk_src[k][cz & (self.blk_src[k] == -10 ** 9)] = self.src[j][cz & (self.blk_src[k] == -10 ** 9)]
        return bl

    def target(self, k1, di, dj, up):
        """for every node of layer k1: (valid, target layer) of the move to the neighbour cell (di, dj)"""
        K = self.K
        Zs = self.Z[k1].reshape(NX, NY)
        tgt = np.full((NX, NY), -1, np.int64)
        sl_s = (slice(max(0, -di), NX - max(0, di)), slice(max(0, -dj), NY - max(0, dj)))
        sl_t = (slice(max(0, di), NX - max(0, -di)), slice(max(0, dj), NY - max(0, -dj)))
        zs = Zs[sl_s]
        t = np.full(zs.shape, -1, np.int64); ztt = np.full(zs.shape, -np.inf)
        for k2 in range(K):
            z2 = self.Z[k2].reshape(NX, NY)[sl_t]
            m = (t < 0) & (z2 <= zs + up) & np.isfinite(z2)
            t[m] = k2; ztt[m] = z2[m]
        bl = np.zeros(zs.shape, bool)
        for k2 in range(K): bl |= (t == k2) & self.blocked[k2].reshape(NX, NY)[sl_t]
        for k2 in range(K):                              # a surface in the way at body height (a step too high to take) stops the move
            z2 = self.Z[k2].reshape(NX, NY)[sl_t]
            bl |= (z2 > zs + up) & (z2 < zs + BODY1)
        ok = (t >= 0) & ~bl & np.isfinite(zs) & ~self.blocked[k1].reshape(NX, NY)[sl_s] & (zs - ztt < 2500.0)
        valid = np.zeros((NX, NY), bool); valid[sl_s] = ok; tgt[sl_s] = t
        return valid, tgt

    def graph(self, up):
        from scipy import sparse
        rows = []; cols = []
        base = np.arange(NC).reshape(NX, NY)
        for k1 in range(self.K):
            if not self.exists[k1].any(): continue
            card = {}
            for (di, dj) in ((1, 0), (-1, 0), (0, 1), (0, -1)): card[(di, dj)] = self.target(k1, di, dj, up)
            for (di, dj) in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                v, t = card[(di, dj)] if (di, dj) in card else self.target(k1, di, dj, up)
                if di and dj: v = v & card[(di, 0)][0] & card[(0, dj)][0]
                ii, jj = np.nonzero(v)
                rows.append(k1 * NC + base[ii, jj]); cols.append(t[ii, jj] * NC + base[ii + di, jj + dj])
        # stepping off a ledge past the 12-u strip beside its own wall: two or three cells out and down, when nothing between reaches body height
        bmax = np.full(NC, -np.inf); np.maximum.at(bmax, self.b_cell, self.b_hi)
        top = self.Z[0].reshape(NX, NY); bm = bmax.reshape(NX, NY)
        for k1 in range(self.K):
            if not self.exists[k1].any(): continue
            Zs = self.Z[k1].reshape(NX, NY)
            for (di, dj) in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                for nn in (2, 3):
                    v2, t2 = self.target(k1, nn * di, nn * dj, 0.0)
                    lo_i, hi_i = max(0, -nn * di), NX - max(0, nn * di); lo_j, hi_j = max(0, -nn * dj), NY - max(0, nn * dj)
                    zs = Zs[lo_i:hi_i, lo_j:hi_j]
                    clear = np.ones(zs.shape, bool)
                    for q in range(1, nn):
                        sl_m = (slice(lo_i + q * di, hi_i + q * di), slice(lo_j + q * dj, hi_j + q * dj))
                        clear &= (top[sl_m] <= zs + STEP) & (bm[sl_m] <= zs + BODY0)
                    ok = np.zeros((NX, NY), bool); ok[lo_i:hi_i, lo_j:hi_j] = clear
                    zt = np.full((NX, NY), np.inf)
                    for k2 in range(self.K):
                        mm = v2 & (t2 == k2)
                        ii, jj = np.nonzero(mm)
                        zt[ii, jj] = self.Z[k2].reshape(NX, NY)[ii + nn * di, jj + nn * dj]
                    v = v2 & ok & (Zs - zt > STEP)
                    ii, jj = np.nonzero(v)
                    rows.append(k1 * NC + base[ii, jj]); cols.append(t2[ii, jj] * NC + base[ii + nn * di, jj + nn * dj])
        # ladders: every node beside a ladder volume is joined to every other one
        self.ladder_nodes = []
        for L_ in self.sc['ladders']:
            ids = self.ladder_ids(L_['box'])
            self.ladder_nodes.append(ids)
            for a in ids:
                for b in ids:
                    if a != b: rows.append(np.array([a])); cols.append(np.array([b]))
        r = np.concatenate(rows); c = np.concatenate(cols)
        n = self.K * NC
        return sparse.csr_matrix((np.ones(len(r), np.int8), (r, c)), shape=(n, n))

    def ladder_ids(self, box, reach=28.0):
        (x0, y0, z0, x1, y1, z1) = box
        ids = []
        for i in range(int((x0 - reach - X0) // CELL), int((x1 + reach - X0) // CELL) + 1):
            for j in range(int((y0 - reach - Y0) // CELL), int((y1 + reach - Y0) // CELL) + 1):
                if not (0 <= i < NX and 0 <= j < NY): continue
                for k in range(self.K):
                    zz = self.Z[k, i * NY + j]
                    if np.isfinite(zz) and z0 - 24 <= zz <= z1 + 24 and not self.blocked[k, i * NY + j]: ids.append(k * NC + i * NY + j)
        return ids

    def closed(self):
        """the walk graph with the removable props back in (round start): their cells are blocked at body height"""
        if self._closed is not None: return self._closed
        from scipy import sparse
        T = self.rem_tris
        if not len(T): self._closed = self.walk; self.extra_blocked = np.zeros((self.K, NC), bool); return self.walk
        ti, cl, zc, zl, zh = raster(T, PADW)
        eb = np.zeros((self.K, NC), bool)
        for k in range(self.K):
            zk = self.Z[k, cl]
            hit = (zl < zk + BODY1) & (zh > zk + BODY0)
            eb[k, cl[hit]] = True
        self.extra_blocked = eb
        keep = (~eb.ravel()).astype(np.int8)
        D = sparse.diags(keep)
        self._closed = (D @ self.walk @ D).tocsr()
        self._closed.eliminate_zeros()
        return self._closed

    def nodes_near(self, x, y, z, rxy=40.0, rz=40.0, closed=False):
        out = []
        n = int(math.ceil(rxy / CELL))
        ci = int((x - X0) // CELL); cj = int((y - Y0) // CELL)
        eb = self.extra_blocked if closed and self._closed is not None else None
        for i in range(ci - n, ci + n + 1):
            for j in range(cj - n, cj + n + 1):
                if not (0 <= i < NX and 0 <= j < NY): continue
                if math.hypot(X0 + (i + 0.5) * CELL - x, Y0 + (j + 0.5) * CELL - y) > rxy: continue
                for k in range(self.K):
                    zz = self.Z[k, i * NY + j]
                    if np.isfinite(zz) and abs(zz - z) <= rz and not self.blocked[k, i * NY + j] and (eb is None or not eb[k, i * NY + j]): out.append(k * NC + i * NY + j)
        return out

    def top(self, x, y):
        c = cell_of(x, y)
        return float(self.Z[0, c]) if 0 <= c < NC else -np.inf

    def ground(self, x, y, zref):
        """highest surface at or below zref + 12 at a point (the support under something)"""
        c = cell_of(x, y)
        if not 0 <= c < NC: return -np.inf
        zs = self.Z[:, c]; zs = zs[np.isfinite(zs) & (zs <= zref + 12.0)]
        return float(zs.max()) if len(zs) else -np.inf

    def terrain_z(self, x, y):
        """exact height of the terrain mesh at a point (-1e9 where there is none)"""
        if not hasattr(self, '_tz'):
            m = (self.T_kind == K_TERRAIN)
            Tt = self.T[m]
            nrm = np.cross(Tt[:, 1] - Tt[:, 0], Tt[:, 2] - Tt[:, 0])
            Tt = Tt[nrm[:, 2] > 1e-6]
            ti, cl, _, _, _ = raster(Tt, CELL)
            o = np.argsort(cl, kind='stable')
            self._tz = (Tt, cl[o], ti[o])
        Tt, cl, ti = self._tz
        c = cell_of(x, y)
        if c < 0: return -1e9
        a, b = np.searchsorted(cl, c, 'left'), np.searchsorted(cl, c, 'right')
        best = -1e9
        for t in Tt[ti[a:b]]:
            d = (t[1, 0] - t[0, 0]) * (t[2, 1] - t[0, 1]) - (t[2, 0] - t[0, 0]) * (t[1, 1] - t[0, 1])
            if abs(d) < 1e-9: continue
            u = ((x - t[0, 0]) * (t[2, 1] - t[0, 1]) - (t[2, 0] - t[0, 0]) * (y - t[0, 1])) / d
            v = ((t[1, 0] - t[0, 0]) * (y - t[0, 1]) - (x - t[0, 0]) * (t[1, 1] - t[0, 1])) / d
            if u >= -1e-6 and v >= -1e-6 and u + v <= 1 + 1e-6:
                best = max(best, t[0, 2] + u * (t[1, 2] - t[0, 2]) + v * (t[2, 2] - t[0, 2]))
        return best


def reach(g, start, reverse=False):
    from scipy.sparse import csgraph
    from scipy import sparse
    n = g.shape[0]
    seen = np.zeros(n, bool)
    if not len(start): return seen
    gg = g.T.tocsr() if reverse else g
    aug = sparse.vstack([sparse.hstack([gg, sparse.csr_matrix((n, 1), dtype=np.int8)]),
                         sparse.csr_matrix((np.ones(len(start), np.int8), (np.zeros(len(start), np.int64), np.array(start))), shape=(1, n + 1))]).tocsr()
    order = csgraph.breadth_first_order(aug, n, directed=True, return_predecessors=False)
    seen[order[order < n]] = True
    return seen


# ================================================================ nav estimate (check 9)
# Ported from projects/monsoon-cs2/tools/check_play.py (pass 3, 12 Nov 2026). There two compiles calibrated it: 378,891 flooded cells
# = 33,661 areas (0.089 per cell, open valley kept) and 115,469 cells = 15,033 areas (0.130 per cell, mostly bases, village, roads);
# pass 4 trimmed the open rims: 90,815 cells = 12,597 areas (0.139). Recalibrate Adapter.nav_cal after each compile whose markup changed:
# the projection is linear in the flooded cells and good to about 1.5x for a very different markup; the cell count is the solid number.
def nonav_nodes(G, boxes):
    """bool (K * NC): nodes whose feet are inside a NONAV box (nav generation makes no area there and cannot cross it)"""
    out = np.zeros((G.K, NX, NY), bool); Z = G.Z.reshape(G.K, NX, NY)
    for (x0, y0, z0, x1, y1, z1) in boxes:
        i0 = max(0, int(math.floor((x0 - X0) / CELL - 0.5)) + 1); i1 = min(NX, int(math.ceil((x1 - X0) / CELL - 0.5)))
        j0 = max(0, int(math.floor((y0 - Y0) / CELL - 0.5)) + 1); j1 = min(NY, int(math.ceil((y1 - Y0) / CELL - 0.5)))
        if i1 <= i0 or j1 <= j0: continue
        zz = Z[:, i0:i1, j0:j1]
        out[:, i0:i1, j0:j1] |= (zz >= z0) & (zz <= z1)
    return out.reshape(G.K * NC)


def nav_estimate(G, boxes, seeds, starts=(), cal=None):
    """flood the open walk graph from the WALKABLESEED boxes `seeds` and the node ids `starts` with the nodes inside the NONAV `boxes`
    taken out: the nodes the nav mesh would cover (island removal drops the rest).
    -> dict(cells, area_m2, areas (None without cal), unmarked_cells, boxes, seeds, nav (bool per node), Wn (nav graph), start)"""
    from scipy import sparse
    walkable = (G.exists & ~G.blocked).ravel()
    ok = walkable & ~nonav_nodes(G, boxes)
    start = list(starts)
    for b in seeds: start += G.nodes_near((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, b[2] - 2.0, 40.0, 16.0)
    start = sorted(set(i for i in start if ok[i]))
    D = sparse.diags(ok.astype(np.int8), dtype=np.int8); Wn = (D @ G.walk @ D).tocsr(); Wn.eliminate_zeros()
    nav = reach((Wn + Wn.T).tocsr(), start) if start else np.zeros(len(ok), bool)
    Dw = sparse.diags(walkable.astype(np.int8), dtype=np.int8); Wa = (Dw @ G.walk @ Dw).tocsr()
    allw = reach((Wa + Wa.T).tocsr(), start) if start else np.zeros(len(ok), bool)
    cells = int(nav.sum())
    areas = int(round(cells * cal['areas'] / cal['cells'])) if cal and cal.get('cells') else None
    return dict(cells=cells, area_m2=round(cells * (CELL * 0.0254) ** 2), areas=areas, unmarked_cells=int(allw.sum()), boxes=len(boxes), seeds=len(seeds),
                nav=nav, Wn=Wn, start=start)


def nav_gate(ctx, ne, walk_routes=None):
    """stations on the nav and bot routes on it (Adapter.nav_stations / nav_routes) -> dict(off, lost, routes, detours)"""
    from scipy.sparse import csgraph
    from scipy import sparse
    A, G = ctx.A, ctx.G; nav = ne['nav']
    off = []
    for s in A.nav_stations(ctx):
        nm, x, y, z = s[:4]; rxy, rz, dz = (tuple(s[4:7]) + (48.0, 40.0, -8.0)[len(s[4:7]):])
        if not any(nav[i] for i in G.nodes_near(x, y, z + dz, rxy, rz)): off.append(nm)
    routes = {}; lost = []; detours = []
    rts = A.nav_routes(ctx)
    if rts:
        Wn = ne['Wn'].tocoo(); ca = Wn.row % NC; cb = Wn.col % NC
        Gn = sparse.csr_matrix((CELL * np.hypot(ca // NY - cb // NY, ca % NY - cb % NY) + 0.01, (Wn.row, Wn.col)), shape=Wn.shape)
        dist = {}; back = {}
        for (label, w, (x, y, z)) in rts:
            if w not in dist:
                st = [i for i in ctx.home.get(w, []) if nav[i]]
                dist[w] = csgraph.dijkstra(Gn, indices=st, min_only=True) if st else None
                back[w] = reach(ne['Wn'], st, reverse=True) if st else None
            if dist[w] is None: lost.append('%s (world %s has no nav)' % (label, w)); routes[label] = None; continue
            ids = [i for i in G.nodes_near(x, y, z - 8.0, 120.0, 80.0) if nav[i]]
            d = min((dist[w][i] for i in ids), default=np.inf)
            routes[label] = round(float(d)) if np.isfinite(d) else None
            if not np.isfinite(d): lost.append(label)
            elif not any(back[w][i] for i in ids): lost.append(label + ' (no way back)')
            wr = (walk_routes or {}).get(label)
            if wr and np.isfinite(d) and d > A.nav_detour * wr: detours.append('%s nav %d vs walk %d' % (label, d, wr))
    return dict(off=off, lost=lost, routes=routes, detours=detours)


# ================================================================ line of sight (2.5D)
class Sight:
    def __init__(self, G, sc, A):
        self.G = G
        hs = np.where(G.terr > -1e8, G.terr, G.Z[0])
        hs = np.where(np.isfinite(hs), hs, -1e5)
        solid = hs.copy()
        m = (G.s_kind == K_WORLD) | (G.s_kind == K_HULL)
        np.maximum.at(solid, G.s_cell[m], G.s_z[m])
        m = (G.b_kind == K_WORLD) | (G.b_kind == K_HULL) | (G.b_kind == K_TRUNK)
        np.maximum.at(solid, G.b_cell[m], G.b_hi[m])
        self.hard = solid.reshape(NX, NY)
        soft = solid.copy(); vis = solid.copy()
        for p in sc['props']:
            if p['removable']: continue
            fol = has(p['model'], A.foliage) or has(p['model'], A.trees)
            ex = max(p['hi'][0] - p['lo'][0], p['hi'][1] - p['lo'][1]); hgt = p['hi'][2] - p['lo'][2]
            r = ex * (0.30 if has(p['model'], A.trees) else 0.42)
            cx, cy = (p['lo'][0] + p['hi'][0]) / 2, (p['lo'][1] + p['hi'][1]) / 2
            c, _, _ = G.disc(cx, cy, max(r, CELL * 0.6))
            if not len(c): continue
            np.maximum.at(vis, c, p['hi'][2])
            if fol and hgt >= 60.0: np.maximum.at(soft, c, p['hi'][2] - (0.12 * hgt if hgt > 200 else 0.0))
        self.soft = soft.reshape(NX, NY); self.vis = vis.reshape(NX, NY)

    def los(self, A, B, soft=False, skip=48.0):
        """A, B: (N, 3) eye / target points -> bool (N): nothing between them rises above the line (the first / last `skip` u are free)"""
        H = self.soft if soft else self.hard
        A = np.asarray(A, float).reshape(-1, 3); B = np.asarray(B, float).reshape(-1, 3)
        if not len(A): return np.zeros(0, bool)
        d = np.hypot(B[:, 0] - A[:, 0], B[:, 1] - A[:, 1]); n = int(max(2, d.max() / (CELL * 0.5)))
        vis = np.ones(len(A), bool)
        for s in range(1, n):
            t = s / n
            dd = d * t
            x = A[:, 0] + (B[:, 0] - A[:, 0]) * t; y = A[:, 1] + (B[:, 1] - A[:, 1]) * t; z = A[:, 2] + (B[:, 2] - A[:, 2]) * t
            i = np.clip(((x - X0) // CELL).astype(np.int64), 0, NX - 1); j = np.clip(((y - Y0) // CELL).astype(np.int64), 0, NY - 1)
            vis &= (H[i, j] <= z) | (dd < skip) | (d - dd < skip)
        return vis


# ================================================================ context handed to the adapter
class Ctx:
    def __init__(self, path, A, sc, G, verbose):
        self.path, self.A, self.sc, self.G, self.verbose = path, A, sc, G, verbose
        self.ents = sc['ents']; self.props = sc['props']
        self.named = defaultdict(list)
        for e in self.ents:
            if e['name']: self.named[e['name']].append(e)
        self.by = {n: v[0] for n, v in self.named.items()}
        self._SG = None; self._reach = {}; self._scc = {}; self._w = {}
        self.home = {}            # world label -> start node ids
        self.res = {}

    @property
    def SG(self):
        if self._SG is None: self._SG = Sight(self.G, self.sc, self.A)
        return self._SG

    def points(self, pattern, cls=None):
        """(name, x, y, z) of the entities whose name matches the regex (sorted by name with numbers in order)"""
        rx = re.compile(pattern)
        out = [(e['name'], e['o'][0], e['o'][1], e['o'][2]) for e in self.ents if e['name'] and rx.fullmatch(e['name']) and (cls is None or e['cls'] == cls)]
        return sorted(out, key=lambda p: [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', p[0])])

    def graph(self, state):
        return self.G.closed() if state == 'closed' else self.G.walk

    def nodes(self, x, y, z, rxy=40.0, rz=40.0, dz=-8.0, state='open'):
        return self.G.nodes_near(x, y, z + dz, rxy, rz, closed=(state == 'closed'))

    def scc(self, state):
        if state not in self._scc:
            from scipy.sparse import csgraph
            self._scc[state] = csgraph.connected_components(self.graph(state), directed=True, connection='strong')[1]
        return self._scc[state]

    def reach_of(self, world, state, reverse=False):
        k = (world, state, reverse)
        if k not in self._reach: self._reach[k] = reach(self.graph(state), self.home.get(world, []), reverse)
        return self._reach[k]

    def world_mask(self, world, state):
        """nodes a world can walk to and back from"""
        return self.reach_of(world, state) & self.reach_of(world, state, True)

    def weighted(self, state):
        if state not in self._w:
            from scipy import sparse
            W_ = self.graph(state).tocoo(); ca = W_.row % NC; cb = W_.col % NC
            wgt = CELL * np.hypot(ca // NY - cb // NY, ca % NY - cb % NY) + 0.01
            self._w[state] = sparse.csr_matrix((wgt, (W_.row, W_.col)), shape=W_.shape)
        return self._w[state]

    def node_xyz(self, n): return node_xyz(self.G, n)


# ================================================================ the checks
def run(path, A, only=None, out_json=None, verbose=False, plot=None, box=None, nav_plan=False):
    t0 = time.time()
    setup_grid(A.extent, A.cell)
    sc = load_scene(path, A, verbose)
    if nav_plan:
        planned = A.planned_navboxes(sc)
        if planned is None: raise SystemExit('--nav-plan: the adapter has no planned_navboxes()')
        sc = dict(sc, navboxes=list(planned))
    if verbose: print('  scene ready %.1fs' % (time.time() - t0))
    G = Grid(sc, verbose)
    ctx = Ctx(path, A, sc, G, verbose)
    ents = sc['ents']; props = sc['props']; by = ctx.by
    res = ctx.res; fails = []; warn = []
    timing = {}
    def want(k): return only is None or str(k) in only
    def lap(k): timing[k] = round(time.time() - t0, 1)

    # ---------------------------------------------------------------- 1 walkability
    worlds = A.worlds(ctx)
    for w, pts in worlds.items():
        ctx.home[w] = sorted(set(sum((ctx.nodes(p[1], p[2], p[3], state='closed') for p in pts), [])))
    if want(1):
        lab = ctx.scc('closed')
        wres = {}
        for w, pts in worlds.items():
            per = [(p, [n for n in ctx.nodes(p[1], p[2], p[3], state='closed')]) for p in pts]
            labs = Counter(lab[n] for _, ns in per for n in ns)
            main_l = labs.most_common(1)[0][0] if labs else -1
            bad = [p[0] for p, ns in per if not any(lab[n] == main_l for n in ns)]
            nowhere = [p[0] for p, ns in per if not ns]
            ctx.home[w] = sorted(set(n for _, ns in per for n in ns if lab[n] == main_l))
            wres[w] = dict(points=len(pts), split=bad, no_ground=nowhere, cells=int((lab == main_l).sum()) if main_l >= 0 else 0)
            if bad: fails.append('walkability')
        leaks = []
        for a, b in A.separate(ctx):
            ra = ctx.reach_of(a, 'closed'); rb = ctx.reach_of(b, 'closed')
            if any(ra[n] for n in ctx.home.get(b, [])): leaks.append('%s reaches %s' % (a, b))
            if any(rb[n] for n in ctx.home.get(a, [])): leaks.append('%s reaches %s' % (b, a))
        unreach = []; tgt_res = []
        for t in A.targets(ctx):
            st = t.get('state', 'closed'); w = t.get('world')
            ids = ctx.nodes(t['x'], t['y'], t['z'], t.get('rxy', 40.0), t.get('rz', 40.0), t.get('dz', -8.0), state=st)
            ws = [w] if w else list(worlds)
            ok = {ww: any(ctx.reach_of(ww, st)[i] and ctx.reach_of(ww, st, True)[i] for i in ids) for ww in ws}
            good = all(ok.values()) if t.get('all') else any(ok.values())
            tgt_res.append(dict(name=t['name'], state=st, ok=good, by=ok, ground=len(ids) > 0))
            if not good: unreach.append((t['name'], st, 'no walkable ground there' if not ids else 'not reached by ' + ','.join(k for k, v in ok.items() if not v), [round(t['x']), round(t['y']), round(t['z'])]))
        # pockets, in the open state, from every world
        G_ = ctx.graph('open')
        Rw = np.zeros(G.K * NC, bool)
        for w in worlds: Rw |= ctx.world_mask(w, 'open')
        ctx.R = Rw
        fwd = reach(G_, np.nonzero(Rw)[0]); back = reach(G_, np.nonzero(Rw)[0], reverse=True)
        stuck = fwd & ~back
        walk_blocked = G.blocked; G.blocked = G.blocked_jump
        G.jump = G.graph(JUMP); G.blocked = walk_blocked
        backj = reach(G.jump, np.nonzero(Rw)[0], reverse=True)
        from scipy import ndimage
        pockets = []
        st2 = stuck.reshape(G.K, NX, NY).any(0)
        labp, npk = ndimage.label(st2, structure=np.ones((3, 3)))
        hardstuck = (stuck & ~backj).reshape(G.K, NX, NY).any(0)
        if npk:
            sizes = ndimage.sum(st2, labp, np.arange(1, npk + 1)); com = ndimage.center_of_mass(st2, labp, np.arange(1, npk + 1))
            hs = ndimage.sum(hardstuck, labp, np.arange(1, npk + 1))
            zz = np.where(stuck.reshape(G.K, NC), G.Z, -np.inf).max(0)
            for k in range(npk):
                x = X0 + (com[k][0] + 0.5) * CELL; y = Y0 + (com[k][1] + 0.5) * CELL
                cc = np.nonzero((labp == k + 1).ravel())[0]
                z = float(np.max(zz[cc]))
                if not A.inplay(x, y, z): continue
                pockets.append(dict(x=round(x), y=round(y), z=round(z) if np.isfinite(z) else None, area=int(sizes[k] * CELL * CELL), no_jump_out=int(hs[k] * CELL * CELL)))
        pockets.sort(key=lambda p: -p['area'])
        big = [p for p in pockets if p['area'] > 200]
        hard = [p for p in big if p['no_jump_out'] > 200]
        res['1'] = dict(worlds=wres, leaks=leaks, targets=tgt_res, unreachable=unreach, walkable_cells=int(Rw.sum()), pockets=len(big), pockets_no_jump=len(hard),
                        pocket_area=int(sum(p['area'] for p in big)), pocket_list=big[:80])
        print('1 walkability: ' + '; '.join('%s %d/%d points in one world (%d cells)%s' % (w, v['points'] - len(v['split']), v['points'], v['cells'],
              (' NOT JOINED: ' + ', '.join(v['split'][:8])) if v['split'] else '') for w, v in wres.items()))
        print('    separation: %s' % ('; '.join(leaks) if leaks else 'held (%d pairs)' % len(A.separate(ctx))))
        print('    %d targets, %d unreachable; stuck pockets %d (%d u2), %d of them not escapable by a jump' % (len(tgt_res), len(unreach), len(big), res['1']['pocket_area'], len(hard)))
        for u in unreach[:30]: print('    unreachable:', u)
        for p in big[:25 if verbose else 12]: print('    pocket at (%d, %d, %s): %d u2%s' % (p['x'], p['y'], p['z'], p['area'], '' if p['no_jump_out'] > 200 else ' (a jump gets out)'))
        if leaks: fails.append('separation')
        if unreach or hard: fails.append('walkability')
        lap('1')

    # ---------------------------------------------------------------- 1b routes
    rts = A.routes(ctx)
    if (want(1) or want('1b')) and rts:
        from scipy.sparse import csgraph as _cg
        dist = {}
        routes = {}
        for (label, w, st, (x, y, z)) in rts:
            if (w, st) not in dist:
                start = ctx.home.get(w, [])
                dist[(w, st)] = _cg.dijkstra(ctx.weighted(st), indices=start, min_only=True) if start else np.full(G.K * NC, np.inf)
            ids = ctx.nodes(x, y, z, 120.0, 80.0, state=st)
            d = min((dist[(w, st)][i] for i in ids), default=np.inf)
            routes[label] = round(float(d)) if np.isfinite(d) else None
        bal = {}
        for (a, b) in A.mirror_pairs(ctx):
            if routes.get(a) and routes.get(b): bal['%s / %s' % (a, b)] = round(routes[a] / routes[b], 3)
        res['1b'] = dict(routes=routes, mirror=bal)
        print('1b routes (walking distance): ' + ', '.join('%s %s' % (k, v if v is not None else 'NO ROUTE') for k, v in routes.items()))
        if bal: print('    mirror ratios (1.00 = even): ' + ', '.join('%s %.2f' % kv for kv in bal.items()))
        if any(abs(v - 1.0) > 0.15 for v in bal.values()): warn.append('route balance off by more than 15 %%: %s' % ', '.join('%s %.2f' % kv for kv in bal.items() if abs(kv[1] - 1.0) > 0.15))
        if any(v is None for v in routes.values()): fails.append('routes')
        lap('1b')

    # ---------------------------------------------------------------- 2 sightlines
    ns = A.no_sight(ctx)
    if want(2) and ns:
        out2 = {}
        for s in ns:
            P = np.array([a for a in s['A'] for b in s['B']], float); Q = np.array([b for a in s['A'] for b in s['B']], float)
            if not len(P): out2[s['label']] = dict(pairs=0, seen=0); continue
            v = ctx.SG.los(P[:, -3:], Q[:, -3:], soft=s.get('soft', False))
            ex = [([round(c) for c in P[i][-3:]], [round(c) for c in Q[i][-3:]]) for i in np.nonzero(v)[0][:6]]
            out2[s['label']] = dict(pairs=len(P), seen=int(v.sum()), allowed=s.get('max', 0), examples=ex)
            if v.sum() > s.get('max', 0): fails.append('sightlines')
        res['2'] = out2
        print('2 sightlines (pairs with a clear line / pairs): ' + ', '.join('%s %d/%d' % (k, v['seen'], v['pairs']) for k, v in out2.items()))
        for k, v in out2.items():
            for e in v.get('examples', [])[:3] if v['seen'] > v.get('allowed', 0) else []: print('    %s: %s sees %s' % (k, e[0], e[1]))
        lap('2')

    # ---------------------------------------------------------------- 3 cover density
    cs = A.cover_sites(ctx)
    if want(3) and cs:
        cover = {}
        so3 = np.argsort(G.s_cell, kind='stable'); c3 = G.s_cell[so3]; z3 = G.s_z[so3]; r3 = G.s_src[so3]
        for n_, p in enumerate(props): p['_n'] = n_
        def support(p, x, y, zref):
            c = cell_of(x, y)
            if not 0 <= c < NC: return -np.inf
            i0, i1 = np.searchsorted(c3, c, 'left'), np.searchsorted(c3, c, 'right')
            zz = z3[i0:i1][(r3[i0:i1] != p['_n']) & (z3[i0:i1] <= zref)]
            return float(zz.max()) if len(zz) else -np.inf
        for (label, fx, fy, fz, rad, need) in cs:
            head = set(); crouch = set(); bags = {}
            for pi, p in enumerate(props):
                if not p['solid'] or p['hull'] is None or p['removable']: continue
                cx, cy = (p['lo'][0] + p['hi'][0]) / 2, (p['lo'][1] + p['hi'][1]) / 2
                if math.hypot(cx - fx, cy - fy) > rad: continue
                base = support(p, cx, cy, p['lo'][2] + 20.0)
                if not np.isfinite(base): base = p['lo'][2]
                wdt = max(p['mhi'][0] - p['mlo'][0], p['mhi'][1] - p['mlo'][1]) * p['s'][0]
                if p['hull'] == 'trunk': wdt = 2 * A.trunk_radius(p['model']) * p['s'][0]
                if wdt < 28.0 or abs(base - fz) > 160: continue
                if has(p['model'], A.stack_models):
                    key = ('bag', round(cx / 96), round(cy / 96)); b0, b1 = bags.get(key, (1e9, -1e9))
                    bags[key] = (min(b0, support(p, cx, cy, p['lo'][2] + 6.0)), max(b1, p['hi'][2])); continue
                top = p['hi'][2] - base
                if top >= 62.0: head.add(pi)
                elif top >= 36.0: crouch.add(pi)
            for key, (b0, b1) in bags.items():
                if not np.isfinite(b0) or abs(b0 - fz) > 160: continue
                if b1 - b0 >= 62.0: head.add(key)
                elif b1 - b0 >= 36.0: crouch.add(key)
            for mi, ms in enumerate(sc['meshes']):
                if ms['kind'] != K_WORLD or ms['hi'][2] - ms['lo'][2] > 600: continue
                if math.hypot(max(ms['lo'][0] - fx, 0, fx - ms['hi'][0]), max(ms['lo'][1] - fy, 0, fy - ms['hi'][1])) > rad: continue
                gs = [G.terr[cell_of(x, y)] for x in (ms['lo'][0] - 24, ms['hi'][0] + 24) for y in (ms['lo'][1] - 24, ms['hi'][1] + 24) if 0 <= cell_of(x, y) < NC]
                if not gs or min(gs) < -1e8: continue
                g = min(gs)
                if ms['hi'][2] - g >= 62.0: head.add(('mesh', mi))
                elif ms['hi'][2] - g >= 36.0: crouch.add(('mesh', mi))
            cover[label] = dict(head=len(head), crouch=len(crouch), need=need)
            if len(head) < need: fails.append('cover')
        res['3'] = cover
        print('3 cover (head-height / crouch-height pieces, minimum): ' + ', '.join('%s %d / %d (%d)' % (l, v['head'], v['crouch'], v['need']) for l, v in cover.items()))
        lap('3')

    # ---------------------------------------------------------------- 6 prop clipping
    if want(6):
        buried = []; floating = []; inwater = []; crown = []; inside = []; by_design = Counter()
        bld = [p for p in props if has(p['model'], A.buildings) and p['solid']] if A.buildings else []
        solids = [p for p in props if p['solid'] and p['hull'] == 'tris' and not p['removable']]
        sgrid = defaultdict(list)
        for n_, p in enumerate(props): p['_n'] = n_
        o_ = np.argsort(sc['srcs'], kind='stable'); ss = sc['srcs'][o_]
        hull_idx = (o_, ss)
        for p in solids:
            for i in range(int(p['lo'][0] // 256), int(p['hi'][0] // 256) + 1):
                for j in range(int(p['lo'][1] // 256), int(p['hi'][1] // 256) + 1): sgrid[(i, j)].append(p)
        so_ = np.argsort(G.s_cell, kind='stable'); s_c = G.s_cell[so_]; s_zz = G.s_z[so_]; s_sr = G.s_src[so_]
        for p in props:
            if p['cls'] != 'prop_static' and not p.get('check_clip'): continue
            nm = short(p['model']); zlo, zhi = p['lo'][2], p['hi'][2]; h = max(zhi - zlo, 1.0)
            if not A.inplay(p['o'][0], p['o'][1], p['o'][2]): continue
            px = np.array(p['poly']); c0 = px.mean(0)
            samp = [tuple(c0)] + [tuple(c0 + (q - c0) * 0.6) for q in px]
            if has(p['model'], A.trees): samp = [(p['o'][0], p['o'][1])]
            t = A.clip_tag(p)
            fr = []; gaps = []; enclosed = False
            for (x, y) in samp:
                c = cell_of(x, y)
                if not 0 <= c < NC: continue
                zs = G.Z[:, c]; kd = G.kind[:, c]
                tw = zs[np.isfinite(zs) & ((kd == K_TERRAIN) | (kd == K_WORLD))]
                roof = bool((tw > zhi + 1.0).any())
                tw = tw[tw <= zhi + 1.0]                       # ground over the prop's top (a sap, a tunnel roof) does not bury it
                fr.append(float(np.clip((tw.max() - zlo) / h, 0, 1)) if len(tw) else 0.0)
                i0_, i1_ = np.searchsorted(s_c, c, 'left'), np.searchsorted(s_c, c, 'right')
                zr_ = s_zz[i0_:i1_][s_sr[i0_:i1_] != p['_n']]
                sup = zr_[(zr_ <= zlo + 12.0) & (zr_ >= zlo - A.float_reach)]    # nothing within reach below: sunk in, not floating
                gaps.append(zlo - float(sup.max()) if len(sup) else -1e9)
                if roof and not len(sup): enclosed = True       # ground over it and nothing under it: sunk right in
            if not fr: continue
            fol = has(p['model'], A.foliage)
            if (np.mean(fr) > 0.35 and h >= A.bury_min_h) or min(gaps) > 6.0 or enclosed:
                # the 16-u cells miss thin supports (a sandbag on a 4-u plank lip) and narrow lips: test again on 5 x 5 exact samples
                fr2, g2 = _refine(G, sc, props, sgrid, p, A)
                fr = [fr2]; gaps = [g2]
            rec = (round(float(np.mean(fr)), 2), nm, round(p['o'][0]), round(p['o'][1]), round(p['o'][2]), p['i'], p['vg'])
            if np.mean(fr) > 0.35 and not fol and h >= A.bury_min_h:
                if t and t not in ('float',): by_design['buried ' + t] += 1
                else: buried.append(rec)
            if min(gaps) > 6.0:
                rec = (round(min(gaps), 1),) + rec[1:]
                if t and t not in ('bury',): by_design['floating ' + t] += 1
                else: floating.append(rec)
            c = cell_of(p['o'][0], p['o'][1])
            if 0 <= c < NC and G.water[c] > -1e8 and G.terr[c] > -1e8 and G.water[c] - max(G.terr[c], p['o'][2]) > 8.0 and not has(p['model'], A.water_ok) and t != 'water':
                inwater.append((round(float(G.water[c] - G.terr[c]), 1), nm, round(p['o'][0]), round(p['o'][1]), round(p['o'][2]), p['i'], p['vg']))
            if bld and has(p['model'], A.trees) and '_roots' not in p['model']:
                ex = 0.3 * max(p['mhi'][0] - p['mlo'][0], p['mhi'][1] - p['mlo'][1]) * p['s'][0]; cz0 = zlo + 0.4 * h
                for b in bld:
                    if b['hi'][2] < cz0 + 10: continue
                    bx = np.array(b['poly'])
                    d = 0.0 if _inside(p['o'][0], p['o'][1], bx) else min(_seg_d(p['o'][0], p['o'][1], bx[k], bx[(k + 1) % 4]) for k in range(4))
                    if d < ex * 0.8: crown.append((short(p['model']), short(b['model']), round(p['o'][0]), round(p['o'][1]), round(d)))
            if not p['solid'] and h > 12 and not fol:
                for b in sgrid.get((int(p['o'][0] // 256), int(p['o'][1] // 256)), ()):
                    if b is p or b['hi'][2] < p['o'][2] + 6 or b['lo'][2] > p['o'][2] + 0.5 * h: continue
                    if not (b['lo'][0] < p['o'][0] < b['hi'][0] and b['lo'][1] < p['o'][1] < b['hi'][1]): continue
                    if _in_hull(sc, hull_idx, b['_n'], p['o'][0], p['o'][1], p['o'][2] + min(10.0, 0.4 * h)):
                        inside.append((nm, short(b['model']), round(p['o'][0]), round(p['o'][1]), round(p['o'][2]), p['i'], p['vg'])); break
        buried.sort(reverse=True); floating.sort(reverse=True)
        res['6'] = dict(buried=len(buried), floating=len(floating), in_water=len(inwater), crown_in_building=len(crown), dressing_inside_solid=len(inside),
                        by_design=dict(by_design), buried_list=buried[:120], floating_list=floating[:120], in_water_list=inwater[:60], crown_list=crown[:40], inside_list=inside[:80])
        print('6 clipping: %d buried > 35 %%, %d floating > 6 u, %d under water, %d tree crowns through buildings, %d dressing props inside solids; by design (adapter tags): %s'
              % (len(buried), len(floating), len(inwater), len(crown), len(inside), dict(by_design) or 'none'))
        for label, lst in (('buried', buried), ('floating', floating), ('under water', inwater), ('crown', crown), ('inside', inside)):
            cnt = Counter(b[1] if label in ('buried', 'floating', 'under water') else b[0] + ' in ' + b[1] for b in lst)
            if cnt: print('    %s: %s' % (label, ', '.join('%s x%d' % kv for kv in cnt.most_common(10))))
            for b in lst[:6 if not verbose else 30]: print('       ', b)
        if buried or floating or inwater or crown or inside: fails.append('clipping')
        lap('6')

    # ---------------------------------------------------------------- 7 water
    if want(7):
        T = G.T; wt = np.nonzero(G.T_kind == K_WATER)[0]
        edges = defaultdict(int); eg = {}
        for ti in wt:
            t = T[ti]
            nz_ = np.cross(t[1] - t[0], t[2] - t[0])[2]
            if nz_ <= 1e-6: continue                        # the sheet's top only
            for k in range(3):
                a = tuple(np.round(t[k], 1)); b = tuple(np.round(t[(k + 1) % 3], 1)); key = (min(a, b), max(a, b)); edges[key] += 1; eg[key] = G.T_src[ti]
        exposed = []; npts = 0
        for (a, b), n in edges.items():
            if n != 1: continue
            ln = math.hypot(b[0] - a[0], b[1] - a[1]); m_ = max(1, int(ln // 16))
            for s in range(m_ + 1):
                x = a[0] + (b[0] - a[0]) * s / m_; y = a[1] + (b[1] - a[1]) * s / m_; z = a[2] + (b[2] - a[2]) * s / m_
                if not A.inplay(x, y, z): continue
                c = cell_of(x, y); npts += 1
                if A.water_edge_ok(x, y, z): continue
                g = G.terrain_z(x, y)
                if g < -1e8: g = G.ground(x, y, z - 13.0)
                if g < z - A.water_edge_tol:
                    cont = False
                    for d in (0, 1, -1, NY, -NY, NY + 1, NY - 1, -NY + 1, -NY - 1):
                        cc = c + d
                        if 0 <= cc < NC:
                            mm = G.w_cell == cc
                            if mm.any() and (np.abs(G.w_z[mm] - z) < 2).any() and (G.w_src[mm] != eg[(a, b)]).any(): cont = True; break
                    if not cont: exposed.append((round(x), round(y), round(z, 1), round(float(z - g), 1), int(-1 - eg[(a, b)])))
        o = np.lexsort((G.w_z, G.w_cell)); c = G.w_cell[o]; z = G.w_z[o]; s = G.w_src[o]
        zf = (c[1:] == c[:-1]) & (np.abs(z[1:] - z[:-1]) < 1.5) & (s[1:] != s[:-1])
        zcells = np.unique(c[1:][zf]); zcells = [cc for cc in zcells if G.terr[cc] < G.water[cc] - 0.5]
        Rw = getattr(ctx, 'R', None)
        deep = int(((G.water - G.terr > 60.0) & (G.terr > -1e8) & (Rw.reshape(G.K, NC).any(0) if Rw is not None else True)).sum())
        ex_cl = _cluster([(e[0], e[1]) for e in exposed], 200.0)
        res['7'] = dict(edge_points=npts, exposed_points=len(exposed), exposed_places=len(ex_cl), zfight_cells=len(zcells), deep_walkable_cells=deep,
                        exposed_list=[dict(x=round(cx), y=round(cy), n=n) for cx, cy, n in ex_cl[:40]], exposed_points_list=exposed[:80],
                        zfight_list=[[round(v) for v in cell_xy(cc)] for cc in zcells[:20]])
        print('7 water: %d sheet edge points, %d above the ground in %d places; %d cells where two sheets overlap at one height; %d walkable cells deeper than 60 u'
              % (npts, len(exposed), len(ex_cl), len(zcells), deep))
        for cx, cy, n in ex_cl[:10]: print('    exposed edge near (%d, %d): %d points' % (cx, cy, n))
        for cc in zcells[:6]: print('    z-fight at', [round(v) for v in cell_xy(cc)])
        if exposed or zcells: fails.append('water')
        lap('7')

    # ---------------------------------------------------------------- 8 terrain
    if want(8):
        steep = []; worst_s = 0.0
        for (label, hw, pts) in A.paths(ctx):
            Pp = np.array(pts, float); seg = np.linalg.norm(np.diff(Pp, axis=0), axis=1)
            for a, b, d in zip(Pp[:-1], Pp[1:], seg):
                if d < 1: continue
                u = (b - a) / d; nr = np.array([-u[1], u[0]])
                for s in np.arange(0.0, max(d - 48.0, 1.0), 32.0):
                    p = a + u * s; q = p + u * 64.0
                    for off in (0.0, hw * 0.5, -hw * 0.5):
                        z0, z1 = _path_z(G, *(p + nr * off)), _path_z(G, *(q + nr * off))
                        if z0 < -1e8 or z1 < -1e8: continue
                        sl = math.degrees(math.atan(abs(z1 - z0) / 64.0)); worst_s = max(worst_s, sl)
                        if sl >= A.path_max_slope: steep.append((label, round(p[0]), round(p[1]), round(sl, 1)))
        poke = []
        for p in props:
            f = A.floors.get(short(p['model']))
            if f is None: continue
            c_, s_ = math.cos(math.radians(p['yaw'])), math.sin(math.radians(p['yaw']))
            worst = -1e9
            for lx in np.linspace(f[0] + 6, f[2] - 6, 9):
                for ly in np.linspace(f[1] + 6, f[3] - 6, 9):
                    x = p['o'][0] + c_ * lx - s_ * ly; y = p['o'][1] + s_ * lx + c_ * ly
                    cc = cell_of(x, y)
                    if cc < 0: continue
                    zs = G.Z[:, cc]; kd = G.kind[:, cc]
                    tw = zs[np.isfinite(zs) & (kd == K_TERRAIN)]
                    tw = tw[tw < p['o'][2] + f[4] + 200.0]
                    if len(tw): worst = max(worst, float(tw.max()) - (p['o'][2] + f[4]))
            if worst > 0.5: poke.append((round(worst, 1), short(p['model']), round(p['o'][0]), round(p['o'][1]), p['i'], p['vg']))
        tm = (G.terr > -1e8).reshape(NX, NY)
        from scipy import ndimage
        hole = ~tm & ndimage.binary_fill_holes(tm)
        hole_cells = np.nonzero(hole.ravel())[0]
        open_gap = []
        for cc in hole_cells:
            x, y = cell_xy(cc)
            if A.hole_ok(x, y): continue
            zs = G.Z[:, cc]; kd = G.kind[:, cc]
            if not (np.isfinite(zs) & ((kd == K_WORLD) | (kd == K_HULL))).any(): open_gap.append(cc)
        gap_cl = _cluster([cell_xy(cc) for cc in open_gap], 100.0)
        res['8'] = dict(path_max_slope=round(worst_s, 1), path_steep=len(steep), floor_poke=poke, hole_cells=int(len(hole_cells)), hole_uncovered=len(open_gap),
                        steep_list=steep[:40], hole_gap_list=[dict(x=round(a), y=round(b), n=n) for a, b, n in gap_cl[:20]])
        print('8 terrain: paths max slope %.1f deg (%d samples >= %.0f); ground through %d walk-in floors; %d hole cells, %d with nothing under them'
              % (worst_s, len(steep), A.path_max_slope, len(poke), len(hole_cells), len(open_gap)))
        for s_ in _cluster([(s[1], s[2]) for s in steep], 250.0)[:8]: print('    steep path near (%d, %d): %d samples' % s_)
        for p in poke[:10]: print('    ground %.1f u through the floor of %s at (%d, %d)' % p[:4])
        for a, b, n in gap_cl[:8]: print('    uncovered hole near (%d, %d): %d cells' % (a, b, n))
        if steep or poke or open_gap: fails.append('terrain')
        lap('8')

    # ---------------------------------------------------------------- 9 nav markup and ladders
    if want(9):
        Rw = getattr(ctx, 'R', None)
        if Rw is None:
            Rw = np.zeros(G.K * NC, bool)
            for w in worlds: Rw |= ctx.world_mask(w, 'open')
        seeds = [b for b in sc['navboxes'] if b[0] == 'WALKABLESEED']; nonav = [b for b in sc['navboxes'] if b[0] == 'NONAV']
        bad_seed = []; seed_nodes = []
        for prop, name, b in seeds:
            ids = G.nodes_near((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, b[2] - 2.0, 30.0, 24.0)
            seed_nodes += ids
            if not any(Rw[i] for i in ids): bad_seed.append((name, [round(v) for v in b[:3]], 'no walkable ground' if not ids else 'off the walkable world'))
        covered = []
        for (nm, x, y, z) in A.nav_protect(ctx):
            for prop, name, b in nonav:
                if b[0] < x < b[3] and b[1] < y < b[4] and b[2] < z + 36.0 and b[5] > z: covered.append((nm, round(x), round(y), name)); break
        lad = []
        for L_, ids in zip(sc['ladders'], G.ladder_nodes):
            bx = L_['box']
            zs = [node_xyz(G, n)[2] for n in ids]
            bot = [z for z in zs if z <= bx[2] + 24]; topz = [z for z in zs if z >= bx[5] - 40]
            ok_b = any(Rw[n] for n, z in zip(ids, zs) if z <= bx[2] + 24); ok_t = bool(topz)
            lad.append(dict(box=[round(v) for v in bx], vg=L_['vg'], bottom_nodes=len(bot), top_nodes=len(topz), bottom_floor=round(max(bot)) if bot else None,
                            top_floor=round(min(topz)) if topz else None, bottom_in_world=ok_b, gap_bottom=round(bx[2] - max(bot), 1) if bot else None))
        flood = reach(ctx.graph('open'), sorted(set(seed_nodes))) if seed_nodes else np.zeros(1, bool)
        res['9'] = dict(seeds=len(seeds), bad_seeds=bad_seed, nonav=len(nonav), covered=len(covered), ladders=lad,
                        seed_flood_cells=int(flood.sum()), seed_flood_m2=round(float(flood.sum()) * CELL * CELL * 0.0254 ** 2 * 1, 0))
        print('9 nav: %d seeds, %d not on the walkable world; %d NONAV boxes cover %d protected points; %d ladder volumes (%d without walkable ground at the bottom, '
              '%d at the top); the seeds flood %d cells (%.0f m2) of the open walk graph'
              % (len(seeds), len(bad_seed), len(nonav), len(covered), len(lad), sum(1 for l in lad if not l['bottom_nodes']), sum(1 for l in lad if not l['top_nodes']),
                 int(flood.sum()), res['9']['seed_flood_m2']))
        for b in bad_seed[:8]: print('    seed', b)
        for c in covered[:10]: print('    NONAV over', c)
        for l in lad: print('    ladder volume %s (%s): bottom nodes %d (floor %s, volume starts %s u above it), top nodes %d (floor %s)'
                            % (l['box'], l['vg'] or 'ungrouped', l['bottom_nodes'], l['bottom_floor'], l['gap_bottom'], l['top_nodes'], l['top_floor']))
        if bad_seed or covered or any(not l['bottom_nodes'] or not l['top_nodes'] for l in lad): fails.append('nav')
        if nav_plan: print('    (boxes from the nav plan, not the vmap)')
        # the nav the compile would make (estimate), every station on it, every bot route on it (ported from monsoon-cs2, pass 3)
        stations = A.nav_stations(ctx); nroutes = A.nav_routes(ctx)
        if A.nav_cal or stations or nroutes or nav_plan:
            starts = sum((list(ctx.home.get(w, [])) for w in A.nav_starts(ctx)), [])
            ne = nav_estimate(G, [b for p, n, b in nonav], [b for p, n, b in seeds if A.nav_seed_ok(b)], starts, A.nav_cal)
            gate = nav_gate(ctx, ne, res.get('1b', {}).get('routes'))
            res['9'].update(nav_cells=ne['cells'], nav_m2=ne['area_m2'], nav_areas_est=ne['areas'], unmarked_cells=ne['unmarked_cells'],
                            stations_off_nav=gate['off'], bot_routes=gate['routes'], bot_routes_lost=gate['lost'], bot_detours=gate['detours'], nav_plan=bool(nav_plan))
            print('    nav estimate: %d walk cells of %g u (%d m2) flooded from %d seeds + %d start nodes, %d without the NONAV boxes%s'
                  % (ne['cells'], CELL, ne['area_m2'], ne['seeds'], len(starts), ne['unmarked_cells'],
                     '; ~%d nav areas (linear in cells: %d cells = %d areas)' % (ne['areas'], A.nav_cal['cells'], A.nav_cal['areas']) if ne['areas'] is not None else ''))
            if nroutes: print('    bot routes on the nav: ' + ', '.join('%s %s' % (k, v if v is not None else 'LOST') for k, v in gate['routes'].items()))
            if stations: print('    stations off the nav: %d of %d%s' % (len(gate['off']), len(stations), (' ' + ', '.join(gate['off'][:12])) if gate['off'] else ''))
            for x_ in gate['lost']: print('    bots cannot route', x_)
            if gate['off'] or gate['lost']: fails.append('nav')
            if gate['detours']: warn.append('bot nav detours over %.2f x the walking route: %s' % (A.nav_detour, '; '.join(gate['detours'])))
            if ne['areas'] and A.nav_target and ne['areas'] > A.nav_target: warn.append('nav estimate ~%d areas (target under %d)' % (ne['areas'], A.nav_target))
        lap('9')

    # ---------------------------------------------------------------- project checks
    for (cid, title, fn) in A.extra_checks(ctx):
        if not want(cid): continue
        r = fn(ctx) or {}
        res[cid] = r.get('result', {})
        print('%s %s: %s' % (cid, title, r.get('summary', '')))
        for l in r.get('lines', [])[: (60 if verbose else 14)]: print('    ' + l)
        for f in r.get('fail', []): fails.append(cid + ' ' + f)
        warn += [cid + ' ' + w for w in r.get('warn', [])]
        lap(cid)

    res['fails'] = fails; res['warnings'] = warn; res['timing'] = timing
    res['scene'] = dict(map=os.path.abspath(path), key=sc.get('key'), from_cache=bool(sc.get('cached')), model_roots=list(A.model_roots))
    for w in warn: print('WARNING ' + w)
    oj = out_json or A.out_json
    if oj:
        os.makedirs(os.path.dirname(os.path.abspath(oj)), exist_ok=True)
        json.dump(res, open(oj, 'w'), indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
    if plot: render(ctx, plot, box)
    nchk = len([k for k in res if k not in ('fails', 'warnings', 'timing', 'scene')])
    print('RESULT: %s  (%.0f s)' % ('clean (%d checks)' % nchk if not fails else 'FAILED: ' + ', '.join(sorted(set(fails), key=fails.index)), time.time() - t0))
    ctx.fails = fails
    return ctx


def render(ctx, dst, box=None, marks=(), scale=None):
    """top-down picture: the highest surface shaded, the walkable worlds tinted, blocked cells dark red, pockets magenta, prop footprints,
    ladder volumes cyan, named points; marks: [(x, y, label)] drawn as yellow rings"""
    from PIL import Image, ImageDraw
    G = ctx.G
    x0, y0, x1, y1 = box or (X0, Y0, X0 + NX * CELL, Y0 + NY * CELL)
    i0, i1 = max(0, int((x0 - X0) // CELL)), min(NX, int((x1 - X0) // CELL) + 1); j0, j1 = max(0, int((y0 - Y0) // CELL)), min(NY, int((y1 - Y0) // CELL) + 1)
    Z = G.Z[0].reshape(NX, NY)[i0:i1, j0:j1]
    Zf = np.where(np.isfinite(Z), Z, np.nan)
    lo, hi = np.nanpercentile(Zf, 2) if np.isfinite(Zf).any() else 0, np.nanpercentile(Zf, 98) if np.isfinite(Zf).any() else 1
    t = np.clip((np.nan_to_num(Zf, nan=lo) - lo) / max(hi - lo, 1), 0, 1)
    gx, gy = np.gradient(np.nan_to_num(Zf, nan=lo))
    shade = np.clip(0.8 + 0.04 * (gx + gy), 0.4, 1.2)
    rgb = np.stack([90 + 100 * t, 90 + 100 * t, 80 + 90 * t], -1) * shade[..., None]
    R = getattr(ctx, 'R', None)
    if R is not None:
        top_walk = R.reshape(G.K, NX, NY).any(0)[i0:i1, j0:j1]
        rgb[top_walk] = rgb[top_walk] * 0.55 + np.array([60, 160, 255]) * 0.45
    blk = (G.blocked & G.exists).reshape(G.K, NX, NY)[0][i0:i1, j0:j1]
    rgb[blk] = rgb[blk] * 0.6 + np.array([140, 30, 30]) * 0.4
    w = (G.water.reshape(NX, NY)[i0:i1, j0:j1] > np.nan_to_num(Zf, nan=-1e9) - 0.5)
    rgb[w] = rgb[w] * 0.4 + np.array([40, 90, 200]) * 0.6
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8).transpose(1, 0, 2)[::-1])
    k = scale or max(1, int(900 / max(img.size)))
    img = img.resize((img.size[0] * k, img.size[1] * k), Image.NEAREST)
    dr = ImageDraw.Draw(img)
    px = lambda x, y: ((x - (X0 + i0 * CELL)) / CELL * k, ((Y0 + j1 * CELL) - y) / CELL * k)
    pk = ctx.res.get('1', {}).get('pocket_list', [])
    for p in pk:
        a, b = px(p['x'], p['y']); r = max(3, math.sqrt(p['area']) / CELL * k / 2)
        dr.ellipse((a - r, b - r, a + r, b + r), outline=(255, 0, 255))
    for p in ctx.props:
        if not (x0 - 200 <= p['o'][0] <= x1 + 200 and y0 - 200 <= p['o'][1] <= y1 + 200): continue
        col = (255, 140, 0) if p['removable'] else (235, 235, 235) if p['solid'] else (120, 200, 120)
        dr.polygon([px(*q) for q in p['poly']], outline=col)
    for L_ in ctx.sc['ladders']:
        b = L_['box']; dr.rectangle([px(b[0], b[4]), px(b[3], b[1])], outline=(0, 255, 255), width=2)
    for e in ctx.ents:
        if e['cls'] in ('info_teleport_destination', 'info_target') and x0 <= e['o'][0] <= x1 and y0 <= e['o'][1] <= y1:
            a, b = px(e['o'][0], e['o'][1]); dr.ellipse((a - 3, b - 3, a + 3, b + 3), fill=(80, 255, 120))
    for (x, y, label) in marks:
        a, b = px(x, y); dr.ellipse((a - 14, b - 14, a + 14, b + 14), outline=(255, 255, 0), width=2); dr.text((a + 16, b - 6), str(label), fill=(255, 255, 0))
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    img.save(dst); print('map ->', dst)


def _path_z(G, x, y):
    """a path is on the ground: the terrain mesh where there is one, else the top surface"""
    z = G.terrain_z(x, y)
    return z if z > -1e8 else G.ground(x, y, 1e5)


def _refine(G, sc, props, sgrid, p, A):
    """(buried fraction, floating gap) of a prop from exact terrain heights on 5 x 5 points over 80 % of its footprint, world surfaces in those
    cells, and the tops of other solid props whose boxes overlap it. A sample where the ground rises above the prop's base + 6 is embedded
    (supported); ground over the prop's top (a sap roof) is not counted"""
    zlo, zhi = p['lo'][2], p['hi'][2]; h = max(zhi - zlo, 1.0)
    P = np.array(p['poly']); c0 = P.mean(0)
    a, b, d = P[1] - P[0], P[3] - P[0], P[0]
    fr = []; gaps = []
    others = []
    for q in sgrid.get((int(p['o'][0] // 256), int(p['o'][1] // 256)), ()):
        if q is p or q['removable']: continue
        if q['lo'][0] < p['hi'][0] and q['hi'][0] > p['lo'][0] and q['lo'][1] < p['hi'][1] and q['hi'][1] > p['lo'][1]: others.append(q['hi'][2])
    for u in np.linspace(0.1, 0.9, 5):
        for v in np.linspace(0.1, 0.9, 5):
            x, y = d + a * u + b * v
            tz = G.terrain_z(x, y)
            c = cell_of(x, y)
            ws = []
            if c >= 0:
                zs = G.Z[:, c]; kd = G.kind[:, c]
                ws = [float(z) for z, k in zip(zs, kd) if np.isfinite(z) and k == K_WORLD]
            ground = [z for z in [tz] + ws if z > -1e8]
            under = [z for z in ground if z <= zhi + 1.0]
            sup = [z for z in ground + others if zlo - A.float_reach <= z <= zlo + 12.0]
            near = [z for z in ground + others if zlo - A.float_reach <= z <= zhi + 1.0]
            if not near and any(z > zhi + 1.0 for z in ground): fr.append(1.0)     # ground over it, nothing under or in it: buried whole
            else: fr.append(float(np.clip((max(under) - zlo) / h, 0, 1)) if under else 0.0)
            if any(zlo + 6.0 < z <= zhi + 1.0 for z in ground) or (not near and any(z > zhi + 1.0 for z in ground)): gaps.append(-1.0); continue
            gaps.append(zlo - max(sup) if sup else -1e9)
    return float(np.mean(fr)), float(min(gaps))


def _seg_d(x, y, a, b):
    ax, ay = a; bx, by = b
    l2 = max((bx - ax) ** 2 + (by - ay) ** 2, 1e-9); t = min(1.0, max(0.0, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / l2))
    return math.hypot(x - (ax + t * (bx - ax)), y - (ay + t * (by - ay)))


def _inside(x, y, poly):
    s = None
    for k in range(len(poly)):
        a = poly[k]; b = poly[(k + 1) % len(poly)]
        c = (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])
        if abs(c) < 1e-9: continue
        if s is None: s = c > 0
        elif (c > 0) != s: return False
    return True


def _in_hull(sc, hull_idx, n, x, y, z):
    """is the point inside prop n's physics hulls: parity of the hull faces a ray straight up crosses"""
    o_, ss = hull_idx
    a = np.searchsorted(ss, n, 'left'); b = np.searchsorted(ss, n, 'right')
    T = sc['tris'][o_[a:b]]
    if not len(T): return False
    d = (T[:, 1, 0] - T[:, 0, 0]) * (T[:, 2, 1] - T[:, 0, 1]) - (T[:, 2, 0] - T[:, 0, 0]) * (T[:, 1, 1] - T[:, 0, 1])
    ok = np.abs(d) > 1e-9; d = np.where(ok, d, 1.0)
    u = ((x - T[:, 0, 0]) * (T[:, 2, 1] - T[:, 0, 1]) - (T[:, 2, 0] - T[:, 0, 0]) * (y - T[:, 0, 1])) / d
    v = ((T[:, 1, 0] - T[:, 0, 0]) * (y - T[:, 0, 1]) - (x - T[:, 0, 0]) * (T[:, 1, 1] - T[:, 0, 1])) / d
    hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1)
    zz = T[:, 0, 2] + u * (T[:, 1, 2] - T[:, 0, 2]) + v * (T[:, 2, 2] - T[:, 0, 2])
    return int((hit & (zz > z)).sum()) % 2 == 1


def _cluster(pts, r):
    """greedy clusters of points: [(cx, cy, n)] largest first"""
    out = []
    for (x, y) in pts:
        for c in out:
            if math.hypot(c[0] / c[2] - x, c[1] / c[2] - y) < r: c[0] += x; c[1] += y; c[2] += 1; break
        else: out.append([x, y, 1])
    return sorted(((c[0] / c[2], c[1] / c[2], c[2]) for c in out), key=lambda c: -c[2])


cluster = _cluster


def cli(A, argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ('-h', '--help'): print(__doc__); return 2
    only = None; oj = None; plot = box = None
    if '--only' in argv: only = set(argv[argv.index('--only') + 1].split(','))
    if '--json' in argv: oj = argv[argv.index('--json') + 1]
    if '--map' in argv:
        i = argv.index('--map'); plot = argv[i + 1]
        if len(argv) > i + 2 and re.fullmatch(r'[-\d.,]+', argv[i + 2]): box = [float(v) for v in argv[i + 2].split(',')]
    ctx = run(argv[0], A, only, oj, '--verbose' in argv, plot, box, nav_plan='--nav-plan' in argv)
    return 1 if ctx.fails else 0


if __name__ == '__main__':
    print(__doc__); sys.exit(2)
