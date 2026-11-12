"""Seam check (12 Nov 2026): every place where the trench walls fail to meet the ground. Offline, read only ("simulated").

usage: python tools/check_seams.py [map.vmap] [--json out.json] [--stage DIR] [--views DIR [--top N]] [--quiet]
       python tools/check_seams.py --selftest        (a constructed scene with planted gaps of known size: each must be found and measured)
  map default: out/step9/chain/5_nav.vmap. --stage (default out/addon) is searched for models before the content addon.
  Exit 0 when no generated-geometry seam is open, 1 otherwise (user-owned ones are listed, never counted), 2 on a usage error.

What it looks at. The trench walls are props (revet_* "wood siding" and iron, 3 u of earth backing at local y 3.2, top at local z 100;
sandbags on the fire and fire-step walls), the ground is world meshes (512-u terrain tiles, the 16-u parapet / parados sheets over the
banks, the mine-tunnel mesh). The generator leaves the terrain carved down to the trench floor up to 48 u behind each wall and lays the
parapet sheet over the bank from where its 16-u grid is >= 2 u from the wall, so every wall run has a slot between its top and the
sheet unless something closes it. Classes:
  siding_top  one per wall run (revetment props in a line): horizontal slit between the siding's top / back (its earth backing) and
              the ground sheet's edge, and vertical opening where the sheet edge stands over the siding top (the opening then faces the
              trench). Measured every 4 u along the top on a 1-u top-surface raster of the real geometry: world meshes from the vmap,
              props from their LOD0 SMDs (the model's own top-surface map, placed with origin / angles / scales).
  hole        any other patch of the bank (outside the dug trench, 0.5-112 u behind a wall) whose top surface is >= 8 u below the
              bank base (layout.ground_low): pit walls, sap walls and mouths, dugout (shelter) fronts, parapet tears.
  mesh_crack  open (boundary) edges of the visible world meshes (terrain, parapets, tunnel; water and tool meshes skipped; the map
              border skipped) that come within 0.05-16 u of another mesh's surface or edge without meeting it (not welded, not buried
              under another surface, a prop or a siding top, not enclosed in a carved void): LOD seams between tiles, parapet sheet
              edges standing over the terrain (a slit under a lip), the tunnel portal. Counted only when a standing eye sees into it
              (the others are listed as not_visible); cracks within 80 u of a reversed revetment are listed with it.
  reversed    revetments whose back points into the dug trench (they face the earth): listed, not sampled.
Each instance gets: position, gap (horizontal width / vertical opening / crack distance, units), depth (how far you see down), the
meshes and props around it with their vis groups, owner (generated = tw_gen / tw_nav; user = tw_user or ungrouped), and
  see_through  a ray from a standing eye in the trench (64 u over the floor) or on the bank (64 u over the ground, 96 u back) through
               the gap reaches something more than 24 u behind / below it, or nothing (a light leak / sightline through the crack);
               rays are cast against the real triangles with back faces culled (the earth backing is single sided).
  hazard       fall_in (the gap is >= 32 u wide and >= 18 u deep: a player box drops in), snag (>= 12 u wide and >= 18 u deep: a foot or
               a grenade goes in), else visual.
Generated vs covered: the rasters are built twice, generated objects only and with the user's objects too. A seam in the generated
geometry that only a user object hides (the sap benches) is listed as "covered by user" and still counts as generated. A crack at one of
the user's static revetments (up to 12 u in front of it or 20 u behind it, under its top: the dressing-station niches the user lined off
the generator's wall line) is the user's and is listed, not counted.
Views (--views DIR): zoomed renders of the worst instances with tools/render.py (the same scene build as out/review2/render_views.py:
meshes from the vmap, our props from their SMDs with baked colour maps, stock props as boxes), a red marker at each instance.
AI-generated (Claude) for skink52.
"""
import argparse, json, math, os, sys, time, pickle, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REPO = os.path.normpath(os.path.join(PROJ, '..', '..'))
sys.path[:] = [os.path.join(REPO, 'tools')] + [p for p in sys.path if os.path.normcase(os.path.abspath(p or '.')) != os.path.normcase(HERE)]
import vmapedit as V      # noqa: E402  (the repo's readers; the project's tools/dmx.py would shadow dmx)
import dmx                # noqa: E402
import numpy as np        # noqa: E402
from scipy import ndimage  # noqa: E402
sys.path.append(os.path.join(REPO, 'create'))
sys.path.append(HERE)     # last: layout.py
import layout as LY       # noqa: E402

OUT = os.path.join(PROJ, 'out')
DEFAULT_MAP = os.path.join(OUT, 'step9', 'chain', '5_nav.vmap')
CONTENT = os.environ.get('TW_CONTENT', r'C:\source1\links\content_addons\mg_trenchwarfare')
STAGE = os.path.join(OUT, 'addon')
CACHE = os.path.join(OUT, 'seams', 'cache')
GEN = ('tw_gen', 'tw_nav')
RES = 1.0                        # raster cell (u)
HOLE_DZ = 8.0                    # a bank cell whose top surface is this far under the bank base is a hole (banks stand >= base - 4.5)
D_IN, D_OUT = 0.5, 112.0         # the bank band behind a wall (true distance) where holes are looked for: the parapet sheets reach 108 u
SLIT_MIN = 1.5                   # a siding-top slit narrower than this (u) is closed (the raster is 1 u)
LIP_MIN = 1.0                    # a sheet edge standing this far over the siding top opens a gap toward the trench
CRACK_MIN, CRACK_MAX = 0.05, 16.0
HULL_W, STAND_EYE = 32.0, 64.0
SIDING = ('revet_',)
SKIP_PROPS = ('tree', 'foliage', 'weed', 'grass', 'leaves', 'bush', 'shrub', 'dogwood', 'viburnum', 'wire_', 'ladder', '/fx/', 'plane_',
              'tl_lantern', 'sign_', 'periscope', 'stump', 'helmet', 'casings')


def owner(vg):
    return 'generated' if vg in GEN else 'user'


# ================================================================ scene from a vmap
def _streams(m, arr):
    return {m.E[s]['name'].decode(): s for s in (m.g(arr, b'streams') or [])}


def _xf(m, n):
    """3x3 (rotation @ scale) and origin of a node"""
    o = np.array(m.g(n, b'origin', [0, 0, 0]) or [0, 0, 0], float)
    a = m.g(n, b'angles', [0, 0, 0]) or [0, 0, 0]
    s = np.array(m.g(n, b'scales', [1, 1, 1]) or [1, 1, 1], float)
    R = np.array(V.rot_matrix(a), float) @ np.diag(s)
    return R, o


def mesh_kind(mats, lo, hi):
    ms = ' '.join(mats)
    if all('/tools/' in x for x in mats): return 'tool'
    if 'water' in ms: return 'water'
    if 'floor_boards' in ms: return 'tunnel'
    if 'hr_ancient_blend' in ms:
        span = hi[:2] - lo[:2]
        if np.all(np.abs(span - 512) < 1) and np.all(np.abs(lo[:2] / 512 - np.round(lo[:2] / 512)) < 1e-3): return 'terrain'
        return 'parapet'
    return 'other'


def read_mesh(m, n, par):
    md = m.g(n, b'meshData')
    if md is None or md < 0: return None
    R, o = _xf(m, n)
    if par is not None and par != m.world and m.g(par, b'origin') is not None:
        R2, o2 = _xf(m, par); R, o = R2 @ R, R2 @ o + o2
    vs = _streams(m, m.g(md, b'vertexData'))
    if 'position:0' not in vs: return None
    P = np.array(dmx.geta(m.E[vs['position:0']], b'data')[2], float) @ R.T + o
    mats = [x.decode() for x in m.g(md, b'materials') or []]
    fei, evi, nxt, vdi, opp, efi = (m.g(md, k) for k in (b'faceEdgeIndices', b'edgeVertexIndices', b'edgeNextIndices', b'vertexDataIndices',
                                                           b'edgeOppositeIndices', b'edgeFaceIndices'))
    fdi = m.g(md, b'faceDataIndices')
    fs = _streams(m, m.g(md, b'faceData'))
    mi = dmx.geta(m.E[fs['materialindex:0']], b'data')[2] if 'materialindex:0' in fs else [0] * len(fei)
    faces, fmat = [], []
    for f, he in enumerate(fei):
        loop, h = [], he
        for _ in range(512):
            loop.append(vdi[evi[h]]); h = nxt[h]
            if h == he: break
        faces.append(loop); fmat.append(mats[mi[fdi[f]]] if mats else '')
    # boundary half-edges (face -1) whose twin has a face: (from, to) vertex indices
    bnd = []
    for h, f in enumerate(efi):
        if f >= 0: continue
        t = opp[h]
        if efi[t] < 0: continue
        bnd.append((vdi[evi[t]], vdi[evi[h]], efi[t]))
    vg = m.g(n, b'customVisGroup') or b''
    vg = vg.decode() if isinstance(vg, bytes) else vg
    lo, hi = P.min(0), P.max(0)
    return dict(i=n, nid=m.g(n, b'nodeID'), vg=vg, owner=owner(vg), mats=mats, kind=mesh_kind(mats, lo, hi), P=P, faces=faces, fmat=fmat,
                bnd=bnd, lo=lo, hi=hi)


def load_scene(path, log=print):
    """meshes + props of a vmap; cached under out/seams/cache by the file's size and time"""
    st = os.stat(path)
    key = hashlib.sha1(('%s|%d|%d' % (os.path.abspath(path), st.st_size, int(st.st_mtime))).encode()).hexdigest()[:16]
    cp = os.path.join(CACHE, 'scene_%s.pkl' % key)
    if os.path.isfile(cp):
        try:
            return pickle.load(open(cp, 'rb'))
        except Exception:
            pass
    t0 = time.time()
    m = V.Map(path)
    meshes, props = [], []
    for n, p in m.walk():
        t = m.type(n)
        if t == b'CMapMesh':
            r = read_mesh(m, n, p)
            if r: meshes.append(r)
        elif t == b'CMapEntity':
            mdl = m.P(n, 'model', '') or ''
            if not mdl.endswith('.vmdl') or not m.cls(n).startswith('prop_'): continue
            R, o = _xf(m, n)
            if p != m.world and m.g(p, b'origin') is not None:
                R2, o2 = _xf(m, p); R, o = R2 @ R, R2 @ o + o2
            vg = m.g(n, b'customVisGroup') or b''
            vg = vg.decode() if isinstance(vg, bytes) else vg
            props.append(dict(i=n, nid=m.g(n, b'nodeID'), cls=m.cls(n), name=m.name(n), model=mdl, R=R, o=o, vg=vg, owner=owner(vg),
                              solid=m.P(n, 'solid', '6')))
    sc = dict(path=os.path.abspath(path), meshes=meshes, props=props)
    os.makedirs(CACHE, exist_ok=True)
    for old in os.listdir(CACHE):
        if old.startswith('scene_') and old != os.path.basename(cp):
            try:
                if time.time() - os.path.getmtime(os.path.join(CACHE, old)) > 3600: os.remove(os.path.join(CACHE, old))
            except OSError:
                pass
    pickle.dump(sc, open(cp, 'wb'), protocol=4)
    log('scene: %d meshes, %d props (%.1f s)' % (len(meshes), len(props), time.time() - t0))
    return sc


def tris_of(me, visible=True):
    """(k, 3, 3) fan triangles of a mesh's faces (only faces with a non-tool material when visible), face index per triangle"""
    out, fi = [], []
    for f, loop in enumerate(me['faces']):
        if visible and ('/tools/' in me['fmat'][f] or 'water' in me['fmat'][f]): continue
        for k in range(1, len(loop) - 1):
            out.append((loop[0], loop[k], loop[k + 1])); fi.append(f)
    if not out: return np.zeros((0, 3, 3)), np.zeros(0, int)
    return me['P'][np.array(out)], np.array(fi)


# ================================================================ model geometry
_MODEL = {}


def model_tris(model):
    """local triangles of a model (LOD0 SMD; out/addon first, then the content addon), or None"""
    if model in _MODEL: return _MODEL[model]
    rel = model[:-5]
    name = os.path.basename(rel)
    if name.endswith('_dyn'): rel = rel[:-4]
    path = None
    for root in (STAGE, CONTENT):
        for suf in ('_lod0.smd', '.smd', '_lod1.smd'):
            p = os.path.join(root, *(rel + suf).split('/'))
            if os.path.isfile(p): path = p; break
        if path: break
    if not path: _MODEL[model] = None; return None
    pts = []
    with open(path, errors='replace') as f:
        tri = False
        for line in f:
            if line.startswith('triangles'): tri = True; continue
            if not tri or line.startswith('end'): continue
            p = line.split()
            if len(p) >= 9: pts.append((-float(p[2]), float(p[1]), float(p[3])))
    T = np.array(pts, float).reshape(-1, 3, 3) if pts else np.zeros((0, 3, 3))
    _MODEL[model] = T
    return T


def sample_tris(T, step):
    """points on every triangle at spacing <= step (vertical faces included): (n, 3)"""
    if not len(T): return np.zeros((0, 3))
    e = np.maximum.reduce([np.linalg.norm(T[:, 1] - T[:, 0], axis=1), np.linalg.norm(T[:, 2] - T[:, 1], axis=1), np.linalg.norm(T[:, 0] - T[:, 2], axis=1)])
    n = np.clip(np.ceil(e / step).astype(int), 1, 400)
    out = []
    for k in np.unique(n):
        sel = T[n == k]
        i, j = np.meshgrid(np.arange(k + 1), np.arange(k + 1), indexing='ij')
        ok = (i + j) <= k
        a = (i[ok] / k)[None, :, None]; b = (j[ok] / k)[None, :, None]
        P = sel[:, 0][:, None, :] * (1 - a - b) + sel[:, 1][:, None, :] * a + sel[:, 2][:, None, :] * b
        out.append(P.reshape(-1, 3))
    return np.concatenate(out)


def sample_seg(A, B, step):
    """points along segments A -> B (n, 3 each) at spacing <= step"""
    L = np.linalg.norm(B - A, axis=1)
    n = np.clip(np.ceil(L / step).astype(int), 1, 4000)
    out = []
    for k in np.unique(n):
        sel = n == k
        t = (np.arange(k + 1) / k)[None, :, None]
        out.append((A[sel][:, None, :] * (1 - t) + B[sel][:, None, :] * t).reshape(-1, 3))
    return np.concatenate(out) if out else np.zeros((0, 3))


_HMAP = {}


def model_hmap(model, cell=0.5):
    """the model's local top-surface map: (x0, y0, cell, Z max) or None"""
    if model in _HMAP: return _HMAP[model]
    T = model_tris(model)
    if T is None or not len(T): _HMAP[model] = None; return None
    S = sample_tris(T, cell * 0.7)
    lo = S[:, :2].min(0) - cell; hi = S[:, :2].max(0) + cell
    nx, ny = int(math.ceil((hi[0] - lo[0]) / cell)) + 1, int(math.ceil((hi[1] - lo[1]) / cell)) + 1
    Z = np.full((nx, ny), -np.inf)
    i = np.floor((S[:, 0] - lo[0]) / cell).astype(int); j = np.floor((S[:, 1] - lo[1]) / cell).astype(int)
    np.maximum.at(Z, (i, j), S[:, 2])
    _HMAP[model] = (lo[0], lo[1], cell, Z)
    return _HMAP[model]


# ================================================================ the top-surface raster of one side's trench band
class Raster:
    def __init__(s, x0, y0, x1, y1, res=RES):
        s.x0, s.y0, s.res = x0, y0, res
        s.nx, s.ny = int(round((x1 - x0) / res)), int(round((y1 - y0) / res))
        s.mesh = np.full((s.nx, s.ny), -np.inf, np.float32)      # world meshes (top surface)
        s.mesh_id = np.full((s.nx, s.ny), -1, np.int32)
        s.gen = np.full((s.nx, s.ny), -np.inf, np.float32)       # generated props
        s.gen_id = np.full((s.nx, s.ny), -1, np.int32)
        s.user = np.full((s.nx, s.ny), -np.inf, np.float32)      # user props
        s.user_id = np.full((s.nx, s.ny), -1, np.int32)

    def xy(s):
        return np.meshgrid(s.x0 + (np.arange(s.nx) + 0.5) * s.res, s.y0 + (np.arange(s.ny) + 0.5) * s.res, indexing='ij')

    def cell(s, x, y):
        return np.floor((np.asarray(x) - s.x0) / s.res).astype(int), np.floor((np.asarray(y) - s.y0) / s.res).astype(int)

    def add_tris(s, T, idx):
        """rasterise triangles (cell centres inside the triangle's xy projection, max z); near-vertical ones by their samples"""
        lo = T.min(1); hi = T.max(1)
        keep = (hi[:, 0] >= s.x0) & (lo[:, 0] <= s.x0 + s.nx * s.res) & (hi[:, 1] >= s.y0) & (lo[:, 1] <= s.y0 + s.ny * s.res)
        T = T[keep]; lo = lo[keep]; hi = hi[keep]
        if not len(T): return
        a, b, c = T[:, 0], T[:, 1], T[:, 2]
        den = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
        area = np.abs(den) / 2
        flat = area > 0.05
        for k in np.nonzero(flat)[0]:
            i0 = max(0, int(math.floor((lo[k, 0] - s.x0) / s.res - 0.5)) ); i1 = min(s.nx - 1, int(math.ceil((hi[k, 0] - s.x0) / s.res - 0.5)))
            j0 = max(0, int(math.floor((lo[k, 1] - s.y0) / s.res - 0.5))); j1 = min(s.ny - 1, int(math.ceil((hi[k, 1] - s.y0) / s.res - 0.5)))
            if i1 < i0 or j1 < j0: continue
            X, Y = np.meshgrid(s.x0 + (np.arange(i0, i1 + 1) + 0.5) * s.res, s.y0 + (np.arange(j0, j1 + 1) + 0.5) * s.res, indexing='ij')
            A, B, C = a[k], b[k], c[k]
            l1 = ((B[1] - C[1]) * (X - C[0]) + (C[0] - B[0]) * (Y - C[1])) / den[k]
            l2 = ((C[1] - A[1]) * (X - C[0]) + (A[0] - C[0]) * (Y - C[1])) / den[k]
            l3 = 1 - l1 - l2
            e = -1e-6
            inn = (l1 >= e) & (l2 >= e) & (l3 >= e)
            if not inn.any(): continue
            Z = (l1 * A[2] + l2 * B[2] + l3 * C[2]).astype(np.float32)
            blk = s.mesh[i0:i1 + 1, j0:j1 + 1]; bid = s.mesh_id[i0:i1 + 1, j0:j1 + 1]
            up = inn & (Z > blk)
            blk[up] = Z[up]; bid[up] = idx
        if (~flat).any():                                  # a vertical face's top in a column is on one of its edges
            Tv = T[~flat]
            S = np.concatenate([sample_seg(Tv[:, k], Tv[:, (k + 1) % 3], s.res * 0.5) for k in range(3)])
            s.add_points(S, idx, s.mesh, s.mesh_id)

    def add_points(s, S, idx, arr, ids):
        i, j = s.cell(S[:, 0], S[:, 1])
        ok = (i >= 0) & (i < s.nx) & (j >= 0) & (j < s.ny)
        if not ok.any(): return
        i, j, z = i[ok], j[ok], S[ok, 2].astype(np.float32)
        before = arr[i, j].copy()
        np.maximum.at(arr, (i, j), z)
        ids[i[(z >= arr[i, j]) & (z > before)], j[(z >= arr[i, j]) & (z > before)]] = idx

    def add_prop(s, pr, idx, user):
        hm = model_hmap(pr['model'])
        if hm is None: return False
        x0, y0, cell, Z = hm
        R, o = pr['R'], pr['o']
        # world bbox of the model
        lx = np.array([x0, x0 + Z.shape[0] * cell]); ly = np.array([y0, y0 + Z.shape[1] * cell])
        fin = Z[np.isfinite(Z)]
        lz = np.array([fin.min() if fin.size else 0, fin.max() if fin.size else 0])
        C = np.array([[x, y, z] for x in lx for y in ly for z in lz]) @ R.T + o
        lo, hi = C.min(0), C.max(0)
        i0, j0 = s.cell(lo[0], lo[1]); i1, j1 = s.cell(hi[0], hi[1])
        i0, j0 = max(0, int(i0)), max(0, int(j0)); i1, j1 = min(s.nx - 1, int(i1)), min(s.ny - 1, int(j1))
        if i1 < i0 or j1 < j0: return False
        X, Y = np.meshgrid(s.x0 + (np.arange(i0, i1 + 1) + 0.5) * s.res, s.y0 + (np.arange(j0, j1 + 1) + 0.5) * s.res, indexing='ij')
        Ri = np.linalg.inv(R)
        # the local column under each world cell: solve for local x, y at the model's mid height (tilts are a few degrees)
        zc = (lz[0] + lz[1]) / 2
        W = np.stack([X.ravel() - o[0], Y.ravel() - o[1], np.full(X.size, 0.0)], 1)
        L = W @ Ri.T
        # correct for the local z the column is read at (tilted props): local = Ri @ (w - o); keep the column's x / y at local z = zc
        dz = (zc - L[:, 2])
        L[:, 0] += dz * (Ri[0, 2] / Ri[2, 2] if abs(Ri[2, 2]) > 1e-6 else 0)
        L[:, 1] += dz * (Ri[1, 2] / Ri[2, 2] if abs(Ri[2, 2]) > 1e-6 else 0)
        ii = np.floor((L[:, 0] - x0) / cell).astype(int); jj = np.floor((L[:, 1] - y0) / cell).astype(int)
        ok = (ii >= 0) & (ii < Z.shape[0]) & (jj >= 0) & (jj < Z.shape[1])
        if not ok.any(): return False
        zl = np.full(X.size, -np.inf); zl[ok] = Z[ii[ok], jj[ok]]
        fin = np.isfinite(zl)
        zw = np.full(X.size, -np.inf)
        Lp = np.stack([L[:, 0], L[:, 1], np.where(fin, zl, 0)], 1)
        zw[fin] = (Lp[fin] @ R.T + o)[:, 2]
        zw = zw.reshape(X.shape).astype(np.float32)
        arr, ids = (s.user, s.user_id) if user else (s.gen, s.gen_id)
        blk = arr[i0:i1 + 1, j0:j1 + 1]; bid = ids[i0:i1 + 1, j0:j1 + 1]
        up = zw > blk
        blk[up] = zw[up]; bid[up] = idx
        return True

    def top(s, user=True):
        a = np.maximum(s.mesh, s.gen)
        return np.maximum(a, s.user) if user else a


def side_box(sg):
    x0, x1 = 1420.0, 2470.0
    if sg < 0: x0, x1 = -x1, -x0
    return x0, -3260.0, x1, 3080.0


def build_raster(sc, sg, log=print):
    t0 = time.time()
    R = Raster(*side_box(sg))
    bx0, by0, bx1, by1 = side_box(sg)
    nt = 0
    for k, me in enumerate(sc['meshes']):
        if me['kind'] in ('tool', 'water'): continue
        if me['hi'][0] < bx0 or me['lo'][0] > bx1 or me['hi'][1] < by0 or me['lo'][1] > by1: continue
        T, _ = tris_of(me)
        if not len(T): continue
        R.add_tris(T, k); nt += len(T)
    npr = 0
    for k, pr in enumerate(sc['props']):
        o = pr['o']
        if not (bx0 - 200 <= o[0] <= bx1 + 200 and by0 - 200 <= o[1] <= by1 + 200) or o[2] < -2000: continue
        if any(t in pr['model'] for t in SKIP_PROPS) or not pr['model'].startswith('models/tw/'): continue
        if R.add_prop(pr, k, pr['owner'] == 'user'): npr += 1
    log('raster %s: %d x %d cells, %d mesh triangles, %d props (%.1f s)' % ('ct' if sg > 0 else 't', R.nx, R.ny, nt, npr, time.time() - t0))
    return R


# ================================================================ the trench footprint (layout) on a raster
_FP = {}


def footprint(R, sg):
    """true signed distance (u) to the dug trench (< 0 inside; the layout's 16-u trench raster, whose cell edges are the wall lines)
    and the bank base (layout.ground_low) on the raster cells"""
    key = (R.x0, R.y0, R.nx, R.ny)
    if key in _FP: return _FP[key]
    X, Y = R.xy()
    L = LY.raster()
    i16 = np.floor((np.abs(X) - LY.RX0) / LY.RES).astype(int); j16 = np.floor((Y - LY.RY0) / LY.RES).astype(int)
    ok = (i16 >= 0) & (i16 < L.nx) & (j16 >= 0) & (j16 < L.ny)
    inside = np.zeros(X.shape, bool)
    inside[ok] = L.mask[i16[ok], j16[ok]]
    d = (ndimage.distance_transform_edt(~inside) - ndimage.distance_transform_edt(inside)) * R.res
    d = np.where(inside, d + 0.5 * R.res, d - 0.5 * R.res).astype(np.float32)       # cell centres: distance to the wall line
    g = np.empty(X.shape, np.float32)
    for c0 in range(0, X.shape[0], 256):
        g[c0:c0 + 256] = LY.ground_low(X[c0:c0 + 256], Y[c0:c0 + 256])
    _FP[key] = (d, g, inside)
    return _FP[key]


# ================================================================ siding tops
def _unit2(v):
    v = np.array([v[0], v[1]], float); n = np.hypot(*v)
    return v / n if n > 1e-9 else v


def _run(o, lead=4):
    """length of the open run behind the siding: from the first open cell within `lead` u of its back to the first closed one (the
    ground, a cover, the next wall); a run that reaches the end of the profile (another trench beyond a thin wall) counts in full"""
    st = np.nonzero(o[:lead])[0]
    if not len(st): return 0
    s0 = int(st[0])
    cl = np.nonzero(~o[s0:])[0]
    return int(cl[0]) if len(cl) else int(len(o) - s0)


def reversed_siding(pr):
    """a revetment whose back (local +y, the earth backing's far side) points into the dug trench: it faces the earth, so its one-sided
    earth backing faces away from the trench (the trench sees through its planks); a Hammer edit or a removable blocker"""
    yb = pr['R'][:2, 1] / max(np.linalg.norm(pr['R'][:2, 1]), 1e-9)
    o = pr['o'][:2]
    din, _ = LY.trench_dist(np.array([o[0] + yb[0] * 10]), np.array([o[1] + yb[1] * 10]))
    dout, _ = LY.trench_dist(np.array([o[0] - yb[0] * 10]), np.array([o[1] - yb[1] * 10]))
    return bool(din[0] < dout[0] - 1)


def capable(pr):
    """a siding the ground may be closed against: generated, or the user's static unnamed ones (never a removable blocker)"""
    return pr['owner'] == 'generated' or (pr['cls'] == 'prop_static' and not pr.get('name'))


def siding_profiles(sc, R, sg, log=print, step=4.0, reach=60):
    """one sample every `step` u along the top of every revetment prop in the raster: the profile of the top surface behind it"""
    d, g, inside = footprint(R, sg)
    top_m, top_g, top_a = R.mesh, R.top(False), R.top(True)
    bx0, by0, bx1, by1 = side_box(sg)
    S = []
    slit_cells = np.zeros(top_m.shape, bool)
    t = np.arange(reach + 1, dtype=float) + 0.5
    for k, pr in enumerate(sc['props']):
        if not any(x in pr['model'] for x in SIDING): continue
        o = pr['o']
        if not (bx0 <= o[0] <= bx1 and by0 <= o[1] <= by1): continue
        if reversed_siding(pr): continue                   # listed by run() as reversed; its 'back' is the trench
        hm = model_hmap(pr['model'])
        if hm is None: continue
        x0, y0, cell, Z = hm
        ys = y0 + (np.arange(Z.shape[1]) + 0.5) * cell
        Zc = np.where(np.isfinite(Z[:, np.abs(ys) <= 7.0]), Z[:, np.abs(ys) <= 7.0], -np.inf).max(1)
        xs = x0 + (np.arange(Z.shape[0]) + 0.5) * cell
        body = xs[Zc > 80.0]                       # the full-height part (earth backing / planks), not a sheet overhang
        if not len(body): continue
        Rm = pr['R']
        sx = np.linalg.norm(Rm[:, 0]); sy = np.linalg.norm(Rm[:, 1])
        n_in = _unit2(Rm[:2, 1])                   # into the earth (local +y)
        along = _unit2(Rm[:2, 0])
        L = (body.max() - body.min()) * sx
        nsmp = max(2, int(round(L / step)) + 1)
        for xl in np.linspace(body.min() + 1.0 / sx, body.max() - 1.0 / sx, nsmp):
            c = int((xl - x0) / cell)
            zt = Zc[max(0, c - 2):c + 3].max()
            W0 = Rm @ np.array([xl, 5.0, zt]) + o
            px = W0[0] + n_in[0] * t; py = W0[1] + n_in[1] * t
            i, j = R.cell(px, py)
            ok = (i >= 0) & (i < R.nx) & (j >= 0) & (j < R.ny)
            if not ok.all(): continue
            pm, pg, pa, pd, pgr = top_m[i, j], top_g[i, j], top_a[i, j], d[i, j], g[i, j]
            ground = pm >= pgr - HOLE_DZ
            te = int(np.argmax(ground)) if ground.any() else reach
            og = (pg < pgr - HOLE_DZ); oa = (pa < pgr - HOLE_DZ)
            wg, wa = _run(og), _run(oa)
            # the profile runs into a dug trench before anything closes it (a wall end, a corner, a thin wall between two trenches):
            # there is no ground to meet there; what is open around it is a hole (hole_instances), not a slot behind this top
            if wg and (pd[1:min(len(pd), 4 + wg)] < 0.5).any(): wg = 0     # (a run that meets another wall line is not this top's slot)
            if wa and (pd[1:min(len(pd), 4 + wa)] < 0.5).any(): wa = 0
            z_edge = float(pm[te]) if ground.any() else float('nan')
            lip = z_edge - W0[2] if ground.any() else 0.0
            # a sheet edge over the siding top: covered when a generated prop (sandbags) rises to the sheet edge between the two
            cov_lip = bool(np.nanmax(np.where(np.isfinite(pg[:te + 1]), pg[:te + 1], -np.inf)) >= z_edge - 0.5) if ground.any() else True
            depth = float(pgr[0] - np.min(np.where(og[:te + 1], pg[:te + 1], np.inf))) if wg and og[:te + 1].any() else (float(pgr[0] - pg[og].min()) if wg else 0.0)
            if not np.isfinite(depth): depth = 999.0
            rec = dict(prop=k, x=float(W0[0]), y=float(W0[1]), z=float(W0[2]), n=[float(n_in[0]), float(n_in[1])], along=[float(along[0]), float(along[1])],
                       edge_t=te, width_gen=wg, width_all=wa, z_edge=z_edge, lip=float(lip), lip_open=bool(lip > LIP_MIN and not cov_lip),
                       depth=depth, g=float(pgr[0]), floor=float(pgr[0] - LY.DEPTH))
            rec['open_gen'] = wg >= SLIT_MIN or rec['lip_open']
            rec['open_all'] = wa >= SLIT_MIN or rec['lip_open']
            S.append(rec)
            if wg:
                slit_cells[i[:te + 1][og[:te + 1]], j[:te + 1][og[:te + 1]]] = True
    log('siding %s: %d samples on %d props, %d open (generated), %d open with user objects' % (
        'ct' if sg > 0 else 't', len(S), len({s['prop'] for s in S}), sum(s['open_gen'] for s in S), sum(s['open_all'] for s in S)))
    return S, slit_cells


def cluster(points, reach):
    """union-find of 2-d points closer than reach: list of index lists"""
    P = np.asarray(points, float)
    if not len(P): return []
    from scipy.spatial import cKDTree
    pairs = cKDTree(P).query_pairs(reach)
    par = list(range(len(P)))
    def f(a):
        while par[a] != a:
            par[a] = par[par[a]]; a = par[a]
        return a
    for a, b in pairs:
        ra, rb = f(a), f(b)
        if ra != rb: par[rb] = ra
    groups = {}
    for i in range(len(P)): groups.setdefault(f(i), []).append(i)
    return sorted(groups.values(), key=lambda g_: -len(g_))


def siding_instances(sc, S, R, sg, which='open_gen'):
    """open siding samples grouped along the wall (closer than 6 u): one instance per open stretch"""
    idx = [k for k, s in enumerate(S) if s[which]]
    out = []
    for grp in cluster([(S[k]['x'], S[k]['y']) for k in idx], 6.0):
        ss = [S[idx[g_]] for g_ in grp]
        worst = max(ss, key=lambda s: (max(s['width_gen'], 0) + max(s['lip'], 0), s['depth']))
        props = sorted({s['prop'] for s in ss})
        own = sorted({sc['props'][p]['owner'] for p in props})
        out.append(dict(cls='siding_top', side='ct' if sg > 0 else 't', x=round(worst['x'], 1), y=round(worst['y'], 1), z=round(worst['z'], 1),
                        n=worst['n'], along=worst['along'], length=round(4.0 * len(ss), 1),
                        gap=float(np.percentile([s['width_gen'] for s in ss], 90)), gap_max=float(max(s['width_gen'] for s in ss)),
                        gap_median=float(np.median([s['width_gen'] for s in ss])),
                        lip=round(max(s['lip'] for s in ss), 1), lip_open=any(s['lip_open'] for s in ss),
                        depth=round(max(s['depth'] for s in ss), 1), edge_t=worst['edge_t'], z_edge=worst['z_edge'], g=worst['g'], floor=worst['floor'],
                        covered_by_user=not any(s['open_all'] for s in ss),
                        owner='user' if 'user' in own else 'generated',
                        props=[dict(nid=sc['props'][p]['nid'], model=sc['props'][p]['model'].split('/')[-1], vg=sc['props'][p]['vg'] or 'ungrouped') for p in props][:12],
                        nprops=len(props), samples=len(ss)))
    return out


def hole_instances(sc, R, sg, slit_cells, near_siding=4):
    """bank cells (0.5-112 u behind a wall, outside the dug trench) whose top surface is HOLE_DZ under the bank base, not already a
    siding-top slit: grouped 8-connected"""
    d, g, inside = footprint(R, sg)
    band = (d > D_IN) & (d < D_OUT)
    top_g, top_a = R.top(False), R.top(True)
    hole = band & (top_g < g - HOLE_DZ)
    sl = ndimage.binary_dilation(slit_cells, iterations=near_siding)
    lab, n = ndimage.label(hole, structure=np.ones((3, 3), bool))
    out = []
    if not n: return out
    X, Y = R.xy()
    objs = ndimage.find_objects(lab)
    for k, slc in enumerate(objs, 1):
        cm = lab[slc] == k
        cells = int(cm.sum())
        if cells < 3: continue
        if (sl[slc][cm]).mean() > 0.5: continue            # the slit behind a siding top: reported as siding_top
        tg = top_g[slc][cm]; gg = g[slc][cm]
        dep = gg - tg
        width = float(2 * ndimage.distance_transform_edt(np.pad(cm, 1))[1:-1, 1:-1].max() * R.res)
        xs, ys = X[slc][cm], Y[slc][cm]
        w = int(np.argmax(np.where(np.isfinite(dep), dep, 1e6)))
        ring = ndimage.binary_dilation(cm, iterations=3) & ~cm
        mids = set(R.mesh_id[slc][ring].tolist()) - {-1}
        pids = (set(R.gen_id[slc][ring].tolist()) | set(R.user_id[slc][ring].tolist())) - {-1}
        uid = set(R.user_id[slc][cm].tolist()) - {-1}
        covered = bool(np.all(top_a[slc][cm] >= g[slc][cm] - HOLE_DZ))
        ax, ay = float(xs.mean()), float(ys.mean())
        place = 'sap mouth' if (abs(abs(ax) - LY.TUN_SAP_XC) < 120 and ay < LY.TUN_PORTAL_Y + 80) else \
                'dugout front' if any(abs(ay - sy) < 120 and abs(abs(ax) - LY.XS - 100) < 130 for sy in LY.SHELTER_Y) else 'bank'
        own = 'user' if any(sc['props'][p]['owner'] == 'user' and any(t in sc['props'][p]['model'] for t in SIDING) for p in pids) else 'generated'
        dmax = float(np.nanmax(np.where(np.isfinite(dep), dep, 999.0)))
        out.append(dict(cls='hole', side='ct' if sg > 0 else 't', place=place, x=round(float(xs[w]), 1), y=round(float(ys[w]), 1),
                        z=round(float(tg[w]) if np.isfinite(tg[w]) else float(gg[w]) - 999.0, 1), cx=round(ax, 1), cy=round(ay, 1), cells=cells,
                        area=round(cells * R.res ** 2, 1), gap=round(width, 1), length=round(cells * R.res ** 2 / max(width, 1.0), 1),
                        depth=round(dmax, 1), g=round(float(gg[w]), 1), covered_by_user=covered, owner=own,
                        meshes=[dict(nid=sc['meshes'][q]['nid'], kind=sc['meshes'][q]['kind'], vg=sc['meshes'][q]['vg'] or 'ungrouped') for q in sorted(mids)][:8],
                        props=[dict(nid=sc['props'][p]['nid'], model=sc['props'][p]['model'].split('/')[-1], vg=sc['props'][p]['vg'] or 'ungrouped') for p in sorted(pids)][:10],
                        user_props_over=len(uid)))
    return out


class Sidings:
    """revetment props and their top line (from the model's top-surface map), looked up at a wall point"""
    def __init__(s, sc):
        s.items = []
        for k, pr in enumerate(sc['props']):
            if not any(t in pr['model'] for t in SIDING) or pr['o'][2] < -2000 or reversed_siding(pr): continue
            hm = model_hmap(pr['model'])
            if hm is None: continue
            x0, y0, cell, Z = hm
            ys = y0 + (np.arange(Z.shape[1]) + 0.5) * cell
            Zc = np.where(np.isfinite(Z[:, np.abs(ys) <= 7.0]), Z[:, np.abs(ys) <= 7.0], -np.inf).max(1)
            xs = x0 + (np.arange(Z.shape[0]) + 0.5) * cell
            body = xs[Zc > 80.0]
            if not len(body): continue
            s.items.append(dict(k=k, owner=pr['owner'], capable=capable(pr), R=pr['R'], Ri=np.linalg.inv(pr['R']), o=pr['o'], x0=x0, cell=cell, Zc=Zc,
                                xmin=float(body.min()), xmax=float(body.max())))
        s.O = np.array([it['o'][:2] for it in s.items])

    def top(s, w):
        """(z of the highest siding top over wall point w, owner of that siding) or (None, None)"""
        t = s.tops(w)
        return max(t)[:2] if t else (None, None)

    def tops(s, w):
        """[(z of the top, owner, capable, the point 1 u behind its face)] of every siding over wall point w"""
        near = np.nonzero(np.hypot(*(s.O - w[None, :2]).T) < 120)[0] if len(s.O) else []
        out = []
        for q in near:
            it = s.items[q]
            L = it['Ri'] @ np.array([w[0] - it['o'][0], w[1] - it['o'][1], 0.0])
            if abs(L[1]) > 16.0 or not (it["xmin"] - 1.5 <= L[0] <= it['xmax'] + 1.5): continue
            xl = min(max(L[0], it['xmin']), it['xmax'])
            c = int((xl - it['x0']) / it['cell'])
            zt = it['Zc'][max(0, c - 2):c + 3].max()
            zw = float((it['R'] @ np.array([L[0], 0.0, zt]) + it['o'])[2])
            inner = it['R'] @ np.array([xl, 1.0, 0.0]) + it['o']        # 1 u behind this siding's face, over the wall point
            out.append((zw, it['owner'], it['capable'], (float(inner[0]), float(inner[1]))))
        return out


    def tucked(s, p, below=5.0, above=1.0, back=(-0.5, 6.0), owner=None):
        """is point p tucked under a siding's top (just behind its face, a few units under its top line)?"""
        near = np.nonzero(np.hypot(*(s.O - p[None, :2]).T) < 120)[0] if len(s.O) else []
        for q in near:
            it = s.items[q]
            if owner and it['owner'] != owner: continue
            L = it['Ri'] @ (np.asarray(p, float) - it['o'])
            if not (back[0] <= L[1] <= back[1]) or not (it['xmin'] - 2 <= L[0] <= it['xmax'] + 2): continue
            c = int((min(max(L[0], it['xmin']), it['xmax']) - it['x0']) / it['cell'])
            zt = it['Zc'][max(0, c - 2):c + 3].max()
            if zt - below <= L[2] <= zt + above: return True
        return False


# ================================================================ open edges of the world meshes
def _pt_tri_dist(P, A, B, C, want_q=False):
    """distances (len(P), len(A)) from points to triangles (closest point on a triangle, vectorised)"""
    P = P[:, None, :]; A = A[None]; B = B[None]; C = C[None]
    ab, ac, ap = B - A, C - A, P - A
    d1 = (ab * ap).sum(-1); d2 = (ac * ap).sum(-1)
    bp = P - B; d3 = (ab * bp).sum(-1); d4 = (ac * bp).sum(-1)
    cp = P - C; d5 = (ab * cp).sum(-1); d6 = (ac * cp).sum(-1)
    va = d3 * d6 - d5 * d4; vb = d5 * d2 - d1 * d6; vc = d1 * d4 - d3 * d2
    den = va + vb + vc
    den = np.where(np.abs(den) < 1e-12, 1e-12, den)
    v = vb / den; w = vc / den
    Q = A + ab * v[..., None] + ac * w[..., None]
    sh = np.broadcast_shapes(P.shape, A.shape)
    Q = np.broadcast_to(Q, sh).copy()

    def setq(mask, val):
        Q[mask] = np.broadcast_to(val, sh)[mask]
    sd = lambda a, b: a / np.where(np.abs(b) < 1e-12, 1e-12, b)
    t_ab = np.clip(sd(d1, d1 - d3), 0, 1); t_ac = np.clip(sd(d2, d2 - d6), 0, 1); t_bc = np.clip(sd(d4 - d3, (d4 - d3) + (d5 - d6)), 0, 1)
    setq((va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0), B + (C - B) * t_bc[..., None])
    setq((vb <= 0) & (d2 >= 0) & (d6 <= 0), A + ac * t_ac[..., None])
    setq((vc <= 0) & (d1 >= 0) & (d3 <= 0), A + ab * t_ab[..., None])
    setq((d6 >= 0) & (d5 <= d6), C)
    setq((d3 >= 0) & (d4 <= d3), B)
    setq((d1 <= 0) & (d2 <= 0), A)
    if want_q: return np.linalg.norm(P - Q, axis=-1), Q
    return np.linalg.norm(P - Q, axis=-1)


MAP_BORDER = (7168.0, 6144.0)
_ENC = {}


def enclosed(sc, p, reach=60.0):
    """a point under a high cover (the ground over a carved void) is enclosed when no level or rising ray from 60 u around reaches
    within 1 u of it past the faces in between (back faces culled)"""
    key = (int(p[0] // 128), int(p[1] // 128))
    if key not in _ENC: _ENC[key] = local_tris(sc, (key[0] * 128 + 64, key[1] * 128 + 64, 0), 260.0)
    T = _ENC[key]
    for a in np.radians(np.arange(0, 360, 30)):
        for dz in (8.0, 40.0):
            e = np.array([p[0] + reach * math.cos(a), p[1] + reach * math.sin(a), p[2] + dz])
            up = _vert_hits(T, e[0], e[1])
            if (up > e[2]).any(): continue                 # an eye under cover (a carved void, under the caps) is not a place to stand
            D = p - e; L = np.linalg.norm(D); D /= L
            if _first_front_hit(e, D, T) > L - 1.0: return False
    return True


def _vert_hits(T, x, y):
    """z of every triangle a vertical line through (x, y) crosses"""
    if not len(T): return np.zeros(0)
    a, b, c = T[:, 0], T[:, 1], T[:, 2]
    den = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    ok = np.abs(den) > 1e-9
    den = np.where(ok, den, 1.0)
    l1 = ((b[:, 1] - c[:, 1]) * (x - c[:, 0]) + (c[:, 0] - b[:, 0]) * (y - c[:, 1])) / den
    l2 = ((c[:, 1] - a[:, 1]) * (x - c[:, 0]) + (a[:, 0] - c[:, 0]) * (y - c[:, 1])) / den
    l3 = 1 - l1 - l2
    inn = ok & (l1 >= -1e-7) & (l2 >= -1e-7) & (l3 >= -1e-7)
    return (l1 * a[:, 2] + l2 * b[:, 2] + l3 * c[:, 2])[inn]


def mesh_cracks(sc, rasters, log=print, bin_=32.0):
    """boundary edges of the visible world meshes that come within CRACK_MIN-CRACK_MAX of another mesh without meeting it"""
    t0 = time.time()
    vis = [k for k, me in enumerate(sc['meshes']) if me['kind'] in ('terrain', 'parapet', 'tunnel', 'other') and me['hi'][2] > -2000]
    TT, TM = [], []
    for k in vis:
        T, _ = tris_of(sc['meshes'][k])
        if len(T): TT.append(T); TM.append(np.full(len(T), k))
    T = np.concatenate(TT); TMk = np.concatenate(TM)
    lo = T.min(1); hi = T.max(1)
    i0 = np.floor((lo[:, 0] - CRACK_MAX) / bin_).astype(int); i1 = np.floor((hi[:, 0] + CRACK_MAX) / bin_).astype(int)
    j0 = np.floor((lo[:, 1] - CRACK_MAX) / bin_).astype(int); j1 = np.floor((hi[:, 1] + CRACK_MAX) / bin_).astype(int)
    bins = {}
    for t in range(len(T)):
        for i in range(i0[t], i1[t] + 1):
            for j in range(j0[t], j1[t] + 1):
                bins.setdefault((i, j), []).append(t)
    # boundary points: both ends and the middle of every open edge; a point on another mesh's boundary vertex is closed outright
    vkey = {}
    for k in vis:
        me = sc['meshes'][k]
        for a, b, f in me['bnd']:
            for v in (a, b):
                vkey.setdefault(tuple(np.round(me['P'][v], 2)), set()).add(k)
    pts, own, edge = [], [], []
    for k in vis:
        me = sc['meshes'][k]
        for a, b, f in me['bnd']:
            if '/tools/' in me['fmat'][f] or 'water' in me['fmat'][f]: continue
            A, B = me['P'][a], me['P'][b]
            M = (A + B) / 2
            if abs(abs(M[0]) - MAP_BORDER[0]) < 1.0 or abs(abs(M[1]) - MAP_BORDER[1]) < 1.0: continue
            wa = len(vkey.get(tuple(np.round(A, 2)), set()) - {k}) > 0; wb = len(vkey.get(tuple(np.round(B, 2)), set()) - {k}) > 0
            for P_, welded in ((A, wa), (M, False), (B, wb)):
                if welded: continue
                pts.append(P_); own.append(k); edge.append((k, int(a), int(b)))
    pts = np.array(pts); own = np.array(own)
    dmin = np.full(len(pts), np.inf); near = np.full(len(pts), -1); qn = np.zeros((len(pts), 3))
    pb = np.floor(pts[:, :2] / bin_).astype(int)
    groups = {}
    for n_, key in enumerate(map(tuple, pb)): groups.setdefault(key, []).append(n_)
    for key, ids in groups.items():
        cand = bins.get(key)
        if not cand: continue
        cand = np.array(cand); ids = np.array(ids)
        for c0 in range(0, len(cand), 3000):
            cc = cand[c0:c0 + 3000]
            for p0 in range(0, len(ids), 256):
                ii = ids[p0:p0 + 256]
                D, Q = _pt_tri_dist(pts[ii], T[cc, 0], T[cc, 1], T[cc, 2], want_q=True)
                D[TMk[cc][None, :] == own[ii][:, None]] = np.inf            # not its own mesh
                j = D.argmin(1); dd = D[np.arange(len(ii)), j]
                better = dd < dmin[ii]
                dmin[ii[better]] = dd[better]; near[ii[better]] = TMk[cc][j[better]]; qn[ii[better]] = Q[np.arange(len(ii)), j][better]
    props_top = [(R, np.maximum(R.gen, R.user)) for R in rasters]
    SD = Sidings(sc)
    cracks = []
    for n_ in np.nonzero((dmin >= CRACK_MIN) & (dmin <= CRACK_MAX))[0]:
        p = pts[n_]
        k_, a_, b_ = edge[n_]
        de = sc['meshes'][k_]['P'][b_] - sc['meshes'][k_]['P'][a_]
        de = de / max(np.linalg.norm(de), 1e-9)
        if abs(np.dot(qn[n_] - p, de)) > 0.7 * dmin[n_]: continue      # the other mesh carries on along the edge: a corner, not a gap
        # hidden: buried under another mesh's surface (a sheet edge under the terrain), under a prop, or tucked under a siding top
        hidden, how = False, ''
        cand = bins.get(tuple(np.floor(p[:2] / bin_).astype(int)))
        if cand:
            cc = np.array(cand); cc = cc[TMk[cc] != own[n_]]
            zs = _vert_hits(T[cc], p[0], p[1])
            if len(zs) and np.any((zs > p[2] + 0.02) & (zs < p[2] + 24.0)): hidden, how = True, 'under a surface'
            elif len(zs) and np.any((zs > p[2] + 0.02) & (zs < p[2] + 150.0)) and enclosed(sc, p): hidden, how = True, 'enclosed'
        if not hidden:
            for R, top in props_top:
                i, j = R.cell(p[0], p[1])
                if 0 <= i < R.nx and 0 <= j < R.ny and top[i, j] > p[2] + 0.5: hidden, how = True, 'under a prop'
        if not hidden and SD.tucked(p): hidden, how = True, 'under a siding top'
        cracks.append(dict(p=p, gap=float(dmin[n_]), mesh=int(own[n_]), other=int(near[n_]), hidden=hidden, how=how, edge=edge[n_]))
    out = []
    vis_cr = [c for c in cracks if not c['hidden']]
    for grp in cluster([c['p'][:2] for c in vis_cr], 24.0):
        cs = [vis_cr[g_] for g_ in grp]
        w = max(cs, key=lambda c: c['gap'])
        me, mo = sc['meshes'][w['mesh']], sc['meshes'][w['other']]
        out.append(dict(cls='mesh_crack', x=round(float(w['p'][0]), 1), y=round(float(w['p'][1]), 1), z=round(float(w['p'][2]), 1),
                        gap=round(w['gap'], 2), gap_median=round(float(np.median([c['gap'] for c in cs])), 2), points=len(cs),
                        length=round(float(np.ptp([c['p'][0] for c in cs]) + np.ptp([c['p'][1] for c in cs])), 1),
                        mesh=dict(nid=me['nid'], kind=me['kind'], vg=me['vg'] or 'ungrouped'), other=dict(nid=mo['nid'], kind=mo['kind'], vg=mo['vg'] or 'ungrouped'),
                        owner='generated' if me['owner'] == 'generated' and mo['owner'] == 'generated' else 'user',
                        edges=sorted({c['edge'] for c in cs})))
    log('mesh edges: %d open-edge points checked (%d visible meshes), %d within %.2f-%.0f u of another mesh (%d hidden under a surface / prop), '
        '%d instances (%.1f s)' % (len(pts), len(vis), len(cracks), CRACK_MIN, CRACK_MAX, len(cracks) - len(vis_cr), len(out), time.time() - t0))
    return out, dict(points=len(pts), cracks=len(cracks), hidden=len(cracks) - len(vis_cr))


# ================================================================ views (tools/render.py; the scene build of out/review2/render_views.py)
_RENDER = {}


def _render_mods():
    if not _RENDER:
        import importlib.util as iu
        for nm in ('geo', 'render'):
            sp = iu.spec_from_file_location('tw_' + nm, os.path.join(HERE, nm + '.py'))
            md = iu.module_from_spec(sp); sys.modules['tw_' + nm] = md; sp.loader.exec_module(md)
            _RENDER[nm] = md
    return _RENDER['geo'], _RENDER['render']


KIND_COL = {'terrain': (104, 96, 70), 'parapet': (122, 110, 78), 'tunnel': (92, 76, 58), 'other': (150, 150, 150)}
_VMODEL = {}


def _view_model(model):
    """LOD1 (else LOD0) triangles of a model for the views"""
    if model in _VMODEL: return _VMODEL[model]
    rel = model[:-5]
    if rel.endswith('_dyn'): rel = rel[:-4]
    T = None
    for root in (STAGE, CONTENT):
        for suf in ('_lod1.smd', '_lod0.smd', '.smd'):
            p = os.path.join(root, *(rel + suf).split('/'))
            if os.path.isfile(p):
                pts = []
                tri = False
                for line in open(p, errors='replace'):
                    if line.startswith('triangles'): tri = True; continue
                    if not tri or line.startswith('end'): continue
                    q = line.split()
                    if len(q) >= 9: pts.append((-float(q[2]), float(q[1]), float(q[3])))
                T = np.array(pts, float).reshape(-1, 3, 3)
                break
        if T is not None: break
    _VMODEL[model] = T
    return T


def _flat(col):
    c = np.full((4, 4, 3), np.array(col, float) / 255.0)
    return dict(color=c, normal=np.tile([0, 0, 1.0], (4, 4, 1)), rough=np.full((4, 4), 0.9), ao=np.ones((4, 4)), metal=np.zeros((4, 4)))


def _prop_col(pr):
    m = pr['model']
    if pr['owner'] == 'user': return (90, 150, 205)                     # user objects: blue
    if 'revet_iron' in m: return (120, 118, 112)
    if 'revet_' in m: return (150, 108, 64)
    if 'sandbag' in m: return (178, 160, 118)
    return (160, 140, 110)


def render_view(sc, eye, target, path, rad=220.0, marks=(), extra=(), title='', W=900, H=560, fov=60):
    """meshes and props within rad of the target, red markers (point lists), extra (tris, colour) e.g. a planned patch"""
    geo, render = _render_mods()
    tg = np.asarray(target, float)
    parts = []

    E = np.asarray(eye, float)

    def add(T, col, cull=True):
        if not len(T): return
        if cull:                                           # back faces culled, as the engine does (the earth backing is one sided)
            nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
            T = T[(nrm * (E - T.mean(1))).sum(1) > 0]
            if not len(T): return
        m = geo.Mesh(); m.V = T.reshape(-1, 3); m.F = np.arange(len(m.V)).reshape(-1, 3); m.T = np.zeros((len(m.V), 2))
        m.recompute_normals(weld=False)
        parts.append((m, np.zeros((len(m.V), 2)), _flat(col)))
    for me in sc['meshes']:
        if me['kind'] not in KIND_COL: continue
        if np.any(me['lo'][:2] > tg[:2] + rad) or np.any(me['hi'][:2] < tg[:2] - rad): continue
        T, _ = tris_of(me)
        c = T.mean(1)
        T = T[(np.abs(c[:, 0] - tg[0]) < rad) & (np.abs(c[:, 1] - tg[1]) < rad)]
        add(T, KIND_COL[me['kind']])
    for pr in sc['props']:
        o = pr['o']
        if abs(o[0] - tg[0]) > rad + 80 or abs(o[1] - tg[1]) > rad + 80 or o[2] < -2000: continue
        if not pr['model'].startswith('models/tw/') or any(t in pr['model'] for t in ('tree', '/fx/', 'plane_')): continue
        T = _view_model(pr['model'])
        if T is None: continue
        add(T @ pr['R'].T + pr['o'], _prop_col(pr))
    for T, col in extra: add(np.asarray(T, float), col, cull=False)
    for p in marks:
        b = geo.rbox(3, 3, 3, r=0, seg=1, center=tuple(p)); b.T = np.zeros((len(b.V), 2))
        parts.append((b, np.zeros((len(b.V), 2)), _flat((230, 30, 30))))
    from PIL import Image, ImageDraw
    img = render.render(parts, eye, target, W, H, fov=fov)
    im = Image.fromarray(img)
    ImageDraw.Draw(im).text((8, 8), title, fill=(255, 255, 0))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    im.save(path)
    return path


def instance_cameras(it):
    """(name, eye, target) pairs for an instance: from the bank looking into the gap, and from inside the trench"""
    p = np.array([it['x'], it['y'], it['z']], float)
    if 'n' in it:
        n = np.array(it['n'] + [0.0]); a = np.array(it.get('along', [-n[1], n[0]]) + [0.0])
        c = p + n * 6
        return [('bank', c + n * 90 + a * 40 + [0, 0, 70], c + [0, 0, -12]),
                ('trench', c - n * 60 + a * 30 + [0, 0, -30], c + [0, 0, -4])]
    q = p.copy()
    if it.get('cls') == 'hole': q[2] = it.get('g', q[2]) - 12.0           # look into the hole from over the bank, not from inside the earth
    return [('above', q + np.array([60.0, 50.0, 80.0]), q), ('low', q + np.array([-70.0, -40.0, 30.0]), q)]


# ================================================================ sightlines through a gap
def _first_front_hit(O, D, T):
    """distance along the unit ray O + t D to the first front-facing triangle (back faces culled, as the engine draws), inf if none"""
    if not len(T): return np.inf
    a, b, c = T[:, 0], T[:, 1], T[:, 2]
    e1, e2 = b - a, c - a
    n = np.cross(e1, e2)
    front = (n @ D) < 0
    p = np.cross(D[None, :], e2)
    det = (e1 * p).sum(1)
    ok = front & (np.abs(det) > 1e-12)
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0)
    s = O[None, :] - a
    u = (s * p).sum(1) * inv
    q = np.cross(s, e1)
    v = (q @ D) * inv
    t = (q * e2).sum(1) * inv
    hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-3)
    return float(t[hit].min()) if hit.any() else np.inf


def local_tris(sc, centre, rad, user=True):
    """world triangles of meshes and props (LOD0) around a point"""
    c = np.asarray(centre, float)
    out = []
    for me in sc['meshes']:
        if me['kind'] in ('tool', 'water'): continue
        if np.any(me['lo'][:2] > c[:2] + rad) or np.any(me['hi'][:2] < c[:2] - rad): continue
        T, _ = tris_of(me)
        if len(T):
            m_ = T.mean(1)
            out.append(T[(np.abs(m_[:, 0] - c[0]) < rad) & (np.abs(m_[:, 1] - c[1]) < rad)])
    for pr in sc['props']:
        o = pr['o']
        if abs(o[0] - c[0]) > rad + 80 or abs(o[1] - c[1]) > rad + 80 or o[2] < -2000: continue
        if not user and pr['owner'] == 'user': continue
        if any(t in pr['model'] for t in SKIP_PROPS) or not pr['model'].startswith('models/tw/'): continue
        T = model_tris(pr['model'])
        if T is not None and len(T): out.append(T @ pr['R'].T + pr['o'])
    return np.concatenate(out) if out else np.zeros((0, 3, 3))


def sightlines(sc, it):
    """which standing eyes see into the gap: a ray to the gap's middle travels more than 2 u past it before it meets a front face"""
    p = np.array([it['x'], it['y'], it['z']], float)
    eyes = {}
    if it['cls'] == 'siding_top':
        n = np.array(it['n'] + [0.0])
        tgt = p + n * (it['edge_t'] / 2.0 + 0.5) + [0, 0, -4.0]
        eyes['bank'] = tgt + n * 96 + [0, 0, it['g'] + 64 - tgt[2]]
        eyes['trench'] = tgt - n * (it['edge_t'] / 2.0 + 41.0) + [0, 0, it['floor'] + 64 - tgt[2]]
        eyes['fire step'] = eyes['trench'] + [0, 0, 40.0]
    elif it['cls'] == 'hole':
        tgt = np.array([it['x'], it['y'], it['g'] - 4.0])
        for k, (dx, dy) in enumerate(((96, 0), (-96, 0), (0, 96), (0, -96))):
            eyes['bank %d' % k] = tgt + [dx, dy, 68.0]
    else:
        tgt = p + [0, 0, -it['gap'] / 2.0]
        for k, (dx, dy) in enumerate(((80, 0), (-80, 0), (0, 80), (0, -80))):
            eyes['low %d' % k] = tgt + [dx, dy, 14.0]
    T = local_tris(sc, tgt, 200.0)
    seen = []
    for nm, e in eyes.items():
        D = tgt - e; L = np.linalg.norm(D); D = D / L
        t = _first_front_hit(e, D, T)
        if t > L + 2.0: seen.append(nm)
    return seen


def hazard(it):
    if it['cls'] == 'mesh_crack': return 'visual'
    w, d = it.get('gap', 0.0), it.get('depth', 0.0)
    if w >= HULL_W and d >= 18: return 'fall_in'
    if w >= 12 and d >= 18: return 'snag'
    return 'visual'


# ================================================================ the whole check
def run(path, log=print, sight=True, max_sight=400):
    t0 = time.time()
    sc = load_scene(path, log)
    rasters, inst, open_len = {}, [], {}
    for sg in (1, -1):
        R = build_raster(sc, sg, log); rasters[sg] = R
        S, slit = siding_profiles(sc, R, sg, log)
        for s in S: s['owner'] = sc['props'][s['prop']]['owner']
        for own in ('generated', 'user'):
            Ss = [s for s in S if s['owner'] == own]
            I = siding_instances(sc, Ss, R, sg)
            for i in I: i['owner'] = own
            inst += I
            open_len[(own, 'ct' if sg > 0 else 't')] = 4.0 * sum(s['open_gen'] for s in Ss)
        inst += hole_instances(sc, R, sg, slit)
    rev = [dict(nid=pr['nid'], model=pr['model'].split('/')[-1], owner=pr['owner'], vg=pr['vg'] or 'ungrouped', cls=pr['cls'], name=pr.get('name', ''),
                o=[round(float(v), 1) for v in pr['o']]) for pr in sc['props'] if any(t in pr['model'] for t in SIDING) and pr['o'][2] > -2000 and reversed_siding(pr)]
    if rev: log('reversed sidings (back to the trench, not sampled): %s' % ', '.join('%d %s %s' % (r['nid'], r['model'], r['owner']) for r in rev))
    cr, cst = mesh_cracks(sc, list(rasters.values()), log)
    inst += cr
    for it in inst:
        it['hazard'] = hazard(it)
    order = sorted(range(len(inst)), key=lambda k: -(inst[k].get('gap', 0) * max(inst[k].get('length', 1), 1)))
    revp = [np.array(r['o'][:2]) for r in rev]
    SDu = Sidings(sc)
    for it in inst:
        if it['cls'] != 'mesh_crack': continue
        # a crack along the reversed revetment is that prop's (listed in reversed_sidings), not the ground's
        if any(np.hypot(it['x'] - q[0], it['y'] - q[1]) < 80 for q in revp): it['at_reversed_siding'] = True
        # a crack right at one of the user's static revetments (up to 12 u in front of it or 20 u behind: the dressing-station niches
        # the user lined, set off the generator's wall line) is the user's wall: listed as user-owned
        if it['owner'] == 'generated' and SDu.tucked(np.array([it['x'], it['y'], it['z']]), below=16.0, above=4.0, back=(-12.0, 20.0), owner='user'):
            it['owner'] = 'user'; it['why_user'] = 'behind a user revetment'
        it['see_through'] = sightlines(sc, it)            # a crack no standing eye can see into is listed, not counted
        it['visible'] = bool(it['see_through'])
    if sight:
        for k in order[:max_sight]:
            it = inst[k]
            if it['cls'] != 'mesh_crack':
                it['see_through'] = sightlines(sc, it)
    def counted(i):
        return not (i['cls'] == 'mesh_crack' and (not i.get('visible') or i.get('at_reversed_siding')))
    gen = [i for i in inst if i['owner'] == 'generated' and counted(i)]
    counts = {}
    for i in inst:
        c = counts.setdefault(i['cls'], dict(generated=0, user=0, generated_covered_by_user=0, not_visible=0, at_reversed_siding=0))
        if i.get('at_reversed_siding'): c['at_reversed_siding'] += 1; continue
        if not counted(i): c['not_visible'] += 1; continue
        c[i['owner']] += 1
        if i['owner'] == 'generated' and i.get('covered_by_user'): c['generated_covered_by_user'] += 1
    res = dict(map=os.path.abspath(path), counts=counts, reversed_sidings=rev, open_siding_length={'%s %s' % k: v for k, v in open_len.items()},
               crack_points=cst, instances=[{k: v for k, v in inst[k].items() if k != 'edges'} for k in order],
               seconds=round(time.time() - t0, 1), ok=not gen)
    return res, sc


def summary_lines(res):
    L = []
    for cls in ('siding_top', 'hole', 'mesh_crack'):
        c = res['counts'].get(cls, dict(generated=0, user=0, generated_covered_by_user=0, not_visible=0, at_reversed_siding=0))
        L.append('  %-10s generated %4d (%d of them hidden only by a user object)   user-owned %3d%s' % (
            cls, c['generated'], c['generated_covered_by_user'], c['user'],
            ('   (+ %d no standing eye sees into, %d at the reversed revetment: listed, not counted)' % (c['not_visible'], c['at_reversed_siding']))
            if cls == 'mesh_crack' else ''))
    L.append('  open siding top (u): ' + ', '.join('%s %.0f' % kv for kv in sorted(res['open_siding_length'].items())))
    shown = [it for it in res['instances'] if not (it['cls'] == 'mesh_crack' and (not it.get('visible') or it.get('at_reversed_siding')))]
    for r_ in res.get('reversed_sidings', []):
        L.append('  reversed siding (faces the earth; left for the user): %s %s %s at %s' % (r_['nid'], r_['model'], r_['owner'], r_['o']))
    for it in shown[:25]:
        L.append('   %-10s %-9s %-7s (%7.1f, %7.1f, %6.1f) gap %5.1f depth %5.1f len %6.1f %s%s%s' % (
            it['cls'], it['owner'], it.get('side', ''), it['x'], it['y'], it['z'], it.get('gap', 0), it.get('depth', 0), it.get('length', 0),
            it['hazard'], (' seen from ' + ', '.join(it['see_through'])) if it.get('see_through') else '',
            (' [%s]' % it['place']) if it.get('place') else ''))
    return L


# ================================================================ selftest: a constructed scene with planted gaps of known size
def _sheet(x0, y0, x1, y1, z, step=16.0, zf=None, kind='parapet', vg='tw_gen', hole=None):
    xs = np.arange(x0, x1 + 1e-6, step); ys = np.arange(y0, y1 + 1e-6, step)
    P = np.array([(x, y, z if zf is None else zf(x, y)) for x in xs for y in ys], float)
    vid = lambda i, j: i * len(ys) + j
    faces = []
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            if hole and hole[0] < cx < hole[2] and hole[1] < cy < hole[3]: continue
            faces.append([vid(i, j), vid(i + 1, j), vid(i + 1, j + 1), vid(i, j + 1)])
    E = {}
    for f, l in enumerate(faces):
        for k in range(4): E[(l[k], l[(k + 1) % 4])] = f
    bnd = [(b, a, f) for (a, b), f in E.items() if (b, a) not in E]
    return dict(i=-1, nid=-1, vg=vg, owner=owner(vg), mats=['x'], kind=kind, P=P, faces=faces, fmat=['materials/x.vmat'] * len(faces), bnd=bnd,
                lo=P.min(0), hi=P.max(0))


def selftest():
    """planted: a 3-u crack between two sheets, a welded pair, a 2.5-u lip over the terrain, an 11-u slot behind a revetment, a closed
    revetment, a 32-u hole in a bank; each must be found (or not) and measured within 1 u"""
    ok = True
    # a long CT wall with the earth at +x (the support trench's rear wall) from the layout
    walls = [(p0, p1, n) for (p0, p1, n) in LY.raster().walls() if n == (-1, 0) and abs(p1[1] - p0[1]) >= 400]
    (p0, p1, n) = walls[len(walls) // 2]
    xw, ya, yb = p0[0], min(p0[1], p1[1]), max(p0[1], p1[1])
    g = float(LY.ground_low(np.array([xw]), np.array([(ya + yb) / 2]))[0])
    model = 'models/tw/revet_planks_a_128/revet_planks_a_128.vmdl'
    if model_tris(model) is None:
        print('selftest: the revetment model is missing (%s): cannot run' % model); return 1
    yaw = math.degrees(math.atan2(-1, 0))                  # local +y -> +x (into the earth)
    R = np.array(V.rot_matrix([0, yaw, 0]), float)
    top = g + 18; base = top - 96
    ym = (ya + yb) / 2
    props = [dict(i=-1, nid=1, cls='prop_static', name='', model=model, R=R, o=np.array([xw, ym - 70.0, base]), vg='tw_gen', owner='generated', solid='6'),
             dict(i=-1, nid=2, cls='prop_static', name='', model=model, R=R, o=np.array([xw, ym + 70.0, base]), vg='tw_gen', owner='generated', solid='6')]
    meshes = [
        _sheet(xw - 80, ya, xw + 200, yb, g - 72, kind='terrain'),                              # the carved floor under it all
        _sheet(xw + 16, ya, xw + 200, ym, top - 4, kind='parapet', hole=(xw + 50, ya + 34, xw + 82, ya + 66)),   # 11-u slot (16 - 5) + a 32-u hole
        _sheet(xw + 5, ym, xw + 200, yb, top - 4, step=1.0 if False else 16.0, kind='parapet'),     # flush with the revet back: closed
    ]
    meshes[2]['P'][:, 0] = np.where(meshes[2]['P'][:, 0] < xw + 6, xw + 4.0, meshes[2]['P'][:, 0])
    # sheet tests far from the trenches
    meshes += [_sheet(3000, 4000, 3128, 4064, 5.0, kind='terrain'), _sheet(3000, 4067, 3128, 4131, 5.0, kind='terrain'),     # 3-u crack
               _sheet(3128, 4000, 3256, 4064, 5.0, kind='terrain'),                                                           # welded
               _sheet(3400, 4000, 3528, 4128, 0.0, kind='terrain'), _sheet(3432, 4032, 3496, 4096, 2.5, kind='parapet'),      # 2.5-u lip
               _sheet(3600, 4000, 3728, 4128, 0.0, kind='terrain'), _sheet(3632, 4032, 3696, 4096, -1.0, kind='parapet')]     # buried edge
    sc = dict(path='selftest', meshes=meshes, props=props)
    for k, me in enumerate(sc['meshes']): me['nid'] = 1000 + k
    Rr = build_raster(sc, 1, log=lambda *a: None)
    S, slit = siding_profiles(sc, Rr, 1, log=lambda *a: None)
    a = [s for s in S if s['prop'] == 0 and abs(s['y'] - (ym - 70)) < 50]
    b = [s for s in S if s['prop'] == 1 and abs(s['y'] - (ym + 70)) < 50]
    wa = float(np.median([s['width_gen'] for s in a])) if a else -1
    ob = sum(s['open_gen'] for s in b)

    def chk(name, cond, got):
        nonlocal ok
        print('  %-52s %s  (%s)' % (name, 'OK' if cond else 'FAIL', got)); ok &= bool(cond)
    chk('slot behind a revetment: 11 u found', a and all(s['open_gen'] for s in a) and abs(wa - 11) <= 1.0, 'median width %.1f u, %d samples' % (wa, len(a)))
    chk('revetment flush with its sheet: closed', b and ob == 0, '%d of %d samples open' % (ob, len(b)))
    H = hole_instances(sc, Rr, 1, slit)
    hh = [h for h in H if abs(h['cx'] - (xw + 64)) < 6 and abs(h['cy'] - (ya + 48)) < 6]
    chk('32-u hole in a bank: found', hh and abs(hh[0]['gap'] - 32) <= 2.0, hh[0]['gap'] if hh else [(h['cx'], h['cy']) for h in H])
    C, st = mesh_cracks(sc, [Rr], log=lambda *a: None)
    cr = [c for c in C if 3990 < c['y'] < 4140 and 2990 < c['x'] < 3140 and c['gap'] > 2]
    chk('3-u crack between two sheets: found', cr and abs(cr[0]['gap_median'] - 3.0) <= 0.5, cr[0]['gap_median'] if cr else 'none')
    wl = [c for c in C if 3120 < c['x'] < 3136 and 4000 <= c['y'] <= 4064]
    chk('welded sheets: not flagged', not wl, '%d flagged' % len(wl))
    lp = [c for c in C if 3420 < c['x'] < 3510 and 4020 < c['y'] < 4110]
    chk('2.5-u lip of a sheet over the terrain: found', lp and abs(lp[0]['gap'] - 2.5) <= 0.3, lp[0]['gap'] if lp else 'none')
    if cr: chk('3-u crack seen by a standing eye', sightlines(sc, cr[0]), sightlines(sc, cr[0]))
    if lp: chk('2.5-u lip seen by a standing eye', sightlines(sc, lp[0]), sightlines(sc, lp[0]))
    bu = [c for c in C if 3620 < c['x'] < 3710 and 4020 < c['y'] < 4110]
    chk('sheet edge 1 u under the terrain: not flagged', not bu, '%d flagged' % len(bu))
    # sightlines: the slot is seen from the bank, the closed wall is not
    it = siding_instances(sc, a, Rr, 1)
    it2 = dict(it[0]) if it else None
    if it2:
        seen = sightlines(sc, it2)
        chk('slot seen from the bank (ray reaches the floor)', 'bank' in seen, seen)
    print('selftest:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


def views(sc, res, out_dir, top=8, log=print):
    """zoomed renders of the worst generated instances of each class (and the user-owned ones)"""
    os.makedirs(out_dir, exist_ok=True)
    made = []
    picks = []
    for cls in ('siding_top', 'hole', 'mesh_crack'):
        picks += [i for i in res['instances'] if i['cls'] == cls and i['owner'] == 'generated'][:top]
        picks += [i for i in res['instances'] if i['cls'] == cls and i['owner'] == 'user'][:2]
    for k, it in enumerate(picks):
        for nm, eye, tg in instance_cameras(it):
            p = os.path.join(out_dir, '%02d_%s_%s_%s.png' % (k, it['cls'], it['owner'][:3], nm))
            render_view(sc, eye, tg, p, rad=200, marks=[(it['x'], it['y'], it['z'])],
                        title='%s %s (%.0f, %.0f, %.0f) gap %.1f depth %.1f %s' % (it['cls'], it['owner'], it['x'], it['y'], it['z'], it.get('gap', 0),
                                                                                 it.get('depth', 0), nm))
            made.append(p)
        log('  view %d/%d: %s' % (k + 1, len(picks), it['cls']))
    return made


def main(argv=None):
    ap = argparse.ArgumentParser(description='seam check: siding tops, bank holes, mesh cracks (read only)')
    ap.add_argument('map', nargs='?', default=None)
    ap.add_argument('--json', default=None)
    ap.add_argument('--stage', default=None)
    ap.add_argument('--views', default=None)
    ap.add_argument('--top', type=int, default=6)
    ap.add_argument('--no-sight', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, 'reconfigure'): s.reconfigure(encoding='utf-8', errors='replace')
    global STAGE
    if a.stage: STAGE = os.path.abspath(a.stage)
    if a.selftest: return selftest()
    path = a.map or next((p for p in (os.path.join(OUT, 'step9', 'chain', '6_nav.vmap'), DEFAULT_MAP) if os.path.isfile(p)), DEFAULT_MAP)
    print('check_seams: %s' % path, flush=True)
    res, sc = run(path, sight=not a.no_sight)
    for l in summary_lines(res): print(l)
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        json.dump(res, open(a.json, 'w', encoding='utf-8'), indent=1, default=float)
    if a.views:
        res['views'] = views(sc, res, a.views, a.top)
        if a.json: json.dump(res, open(a.json, 'w', encoding='utf-8'), indent=1, default=float)
    gen = {k: v['generated'] for k, v in res['counts'].items() if v['generated']}
    print('RESULT: %s (%.0f s)' % ('clean' if res['ok'] else 'FAILED: ' + ', '.join('%s %d' % kv for kv in sorted(gen.items())), res['seconds']))
    return 0 if res['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
