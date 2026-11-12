"""Terrain patch (remaster step 7): erosion and battlefield detail on the generated terrain tiles, as one guarded delta patch.
Reads the input map (never writes it); writes the patched copy, the guard's target list, a report and the deploy list under out/.

usage: python tools/patch_terrain.py [--in V] [--out V] [--stage DIR] [--no-fx] [--no-dense] [--seed N] [--quick]
  defaults: --in out/mg_trenchwarfare_models.vmap, --out out/mg_trenchwarfare_terrain.vmap, --stage out/addon
  then:     python tools/patch_guard.py <in> <out> out/step7/patch_terrain.targets.json --strict
Chain order: patch_world_1 -> patch_models -> patch_terrain -> patch_nav (takes --in / --out like the others).

What it changes (only nodes it finds and verifies; everything is declared in the targets file):
  terrain   the 672 generated terrain tiles (CMapMesh in tw_gen, one Valve blend material, 512 x 512, 32 / 64 / 128 u grid). Vertex heights
            get a detail layer: fresh shell craters, tank-track mud ruts behind the four tanks in no man's land, puddle basins, lorry ruts
            along the airfield edges, subtle noise, then droplet erosion and scree relaxation (create/terrain_img.py) over all of it.
            Vertex paint follows: wet dark mud in the new hollows, dirt in the ruts. Normals are recomputed; UVs (planar x/y) stay valid.
            The tiles the ruts cross and the open no man's land tiles (>= 40 % unprotected) are re-gridded at 16 u (their old surface is
            reproduced exactly under the 00-11 quad split, so only the detail moves them); every other tile keeps its topology and only
            its heights and paint change. --no-dense keeps every grid.
  protect   a hard mask on a 16-u lattice: trenches and banks (layout trench distance < 170 and the parapet sheets), saps and galleries,
            mortar pits, spawns / deploy posts / heal points / seats, the airfield runway and the plane lanes, ladder volumes and props,
            every prop footprint (trees by trunk disc), the user's 13 env_explosions, water sheets, clips, nav markup, the woods skirmish,
            the user's objects and the terrain edge. Any face that touches the mask keeps every vertex exactly (bit for bit), and the
            layer fades in over FEATHER units outside those faces, so there is no seam or step at a mask edge.
  lightmap  the battlefield toolslightmapres shell (tw_gen) follows the new ground where it went lower or higher than its band.
  fx        smoke drifting from a few fresh shell holes (cheap stock smoke, start on) and a rain tile set over the two trench systems
            (create/fxkit.weather_tiles, start OFF; ent_fire tw_rain FireUser1 / FireUser2) - no fog particles (tw32 FPS lesson).
Light: the user's tuned rig (light_environment, env_sky, env_cubemap_fog, post processing) is left as it is; see the report.
"""
import argparse, json, math, os, sys, time, zlib, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REPO = os.path.normpath(os.path.join(PROJ, '..', '..'))
sys.path[:] = [os.path.join(REPO, 'tools')] + [p for p in sys.path if os.path.normcase(os.path.abspath(p or '.')) != os.path.normcase(HERE)]
import vmapedit as V      # noqa: E402  (the repo's readers: the project's tools/dmx.py would shadow dmx)
import dmx                # noqa: E402
import safepath           # noqa: E402
sys.path.append(os.path.join(REPO, 'create'))
import numpy as np        # noqa: E402
from scipy import ndimage  # noqa: E402
import terrain_img as TI  # noqa: E402
sys.path.append(HERE)     # last: layout.py (and its noise import, identical to create/noise.py)
import layout as LY       # noqa: E402

OUT = os.path.join(PROJ, 'out')
STEP = os.path.join(OUT, 'step7')
BLEND_BATTLE = 'materials/de_ancient/hr_ancient_blend_groundmud03-groundgrass_01_wet.vmat'   # x channel: 0 mud .. 1 grass
BLEND_FOREST = 'materials/de_ancient/hr_ancient_blend_groundgrass01-grounddirt01-wet.vmat'    # x channel: 0 grass .. 1 dirt
BLENDS = (BLEND_BATTLE, BLEND_FOREST)
LMRES = 'materials/tools/toolslightmapres.vmat'
TILE = 512
CELL = 16.0                                   # the lattice every vertex sits on
X0, Y0, X1, Y1 = -7168.0, -6144.0, 7168.0, 6144.0
NX, NY = int((X1 - X0) / CELL) + 1, int((Y1 - Y0) / CELL) + 1
FEATHER = 64.0
STEEP = 40.0                                  # mud on faces steeper than this stretches visibly (planar x / y texture)
COS_STEEP = math.cos(math.radians(STEEP))
MAX_CUT, MAX_FILL = 16.0, 9.0
SMOKE_FX = 'particles/burning_fx/barrel_burning_engine_smoke_cheap.vpcf'
RAIN_FX = 'particles/rain_fx/rain.vpcf'


def lat_xy():
    return np.meshgrid(X0 + np.arange(NX) * CELL, Y0 + np.arange(NY) * CELL, indexing='ij')


def li(x): return int(round((x - X0) / CELL))
def lj(y): return int(round((y - Y0) / CELL))


class Mismatch(Exception): pass


# ================================================================ map reading
def streams(m, arr):
    return {m.E[s]['name'].decode(): s for s in (m.g(arr, b'streams') or [])}


def sdata(m, s): return dmx.geta(m.E[s], b'data')


def find_tiles(m):
    """the generated terrain tiles: CMapMesh directly under the world, vis group tw_gen, one blend material, 512 x 512 on the tile grid,
    every vertex on a regular 32 / 64 / 128 grid. Returns (tiles, skipped)."""
    tiles, skipped = [], []
    for n in m.children(m.world):
        if m.type(n) != b'CMapMesh': continue
        md = m.g(n, b'meshData')
        if md is None or md < 0: continue
        mats = [x.decode() for x in m.g(md, b'materials') or []]
        if len(mats) != 1 or mats[0] not in BLENDS: continue
        vg = m.g(n, b'customVisGroup') or b''
        vg = vg.decode() if isinstance(vg, bytes) else vg
        st = streams(m, m.g(md, b'vertexData'))
        P = np.array(sdata(m, st['position:0'])[2], float)
        lo, hi = P.min(0), P.max(0)
        tx, ty = math.floor(lo[0] / TILE) * TILE, math.floor(lo[1] / TILE) * TILE
        res = None
        for r in (32, 64, 128):
            if np.all(np.abs((P[:, 0] - tx) / r - np.round((P[:, 0] - tx) / r)) < 1e-4) and np.all(np.abs((P[:, 1] - ty) / r - np.round((P[:, 1] - ty) / r)) < 1e-4):
                res = r
        if res is None or res == 16 or hi[0] - tx > TILE + 1e-3 or hi[1] - ty > TILE + 1e-3:
            if res != 16 and (hi[0] - lo[0]) <= TILE + 1: skipped.append((n, 'not on a 32/64/128 grid in one tile'))
            continue                                         # the 16-u parapet sheets and anything else
        why = None
        if vg != 'tw_gen': why = 'vis group %r (not ours)' % vg
        elif list(m.g(n, b'origin')) != [0.0, 0.0, 0.0] or any(m.g(n, b'angles')) or list(m.g(n, b'scales')) != [1.0, 1.0, 1.0]: why = 'moved / rotated / scaled'
        # the grid at res must hold every vertex once (a user-split or welded face would break the per-vertex patch)
        gi = np.round((P[:, 0] - tx) / res).astype(int); gj = np.round((P[:, 1] - ty) / res).astype(int)
        if why is None and len(set(zip(gi.tolist(), gj.tolist()))) != len(P): why = 'duplicate vertices'
        nfaces = len(m.g(md, b'faceEdgeIndices'))
        if why is None and nfaces > (TILE // res) ** 2: why = 'more faces than grid cells'
        if why: skipped.append((n, why)); continue
        tiles.append(dict(i=n, nid=m.g(n, b'nodeID'), md=md, mat=mats[0], res=res, tx=tx, ty=ty, P=P, gi=gi, gj=gj, nfaces=nfaces,
                          full=nfaces == (TILE // res) ** 2))
    return tiles, skipped


def tile_grid(t):
    """(n+1, n+1) height grid of a tile (nan where the tile has no vertex)"""
    n = TILE // t['res']
    Z = np.full((n + 1, n + 1), np.nan)
    Z[t['gi'], t['gj']] = t['P'][:, 2]
    return Z


def tri_interp(Z, r, x, y):
    """height of a grid sheet (cell r, origin 0) at local x, y under the 00-11 split (check_play's fan from the face's first vertex)"""
    n = Z.shape[0] - 1
    u = np.clip(x / r, 0, n - 1e-9); v = np.clip(y / r, 0, n - 1e-9)
    i = np.minimum(u.astype(int), n - 1); j = np.minimum(v.astype(int), n - 1); fu = u - i; fv = v - j
    z00 = Z[i, j]; z10 = Z[i + 1, j]; z01 = Z[i, j + 1]; z11 = Z[i + 1, j + 1]
    low = fu >= fv                     # triangle (00, 10, 11)
    return np.where(low, z00 + fu * (z10 - z00) + fv * (z11 - z10), z00 + fv * (z01 - z00) + fu * (z11 - z01))


# ================================================================ protect mask
def scene_props(vmap, stage):
    """prop footprints from the same scene check_play builds (hull / bounds per model, cached by the vmap's size and time)"""
    spec = importlib.util.spec_from_file_location('tw_check_play', os.path.join(HERE, 'check_play.py'))
    TP = importlib.util.module_from_spec(spec); sys.modules['tw_check_play'] = TP; spec.loader.exec_module(TP)
    TP.A.model_roots = [os.path.abspath(stage)] + list(TP.A.model_roots)
    sc = TP.CP.load_scene(vmap, TP.A)
    return sc, TP


def poly_fill(M, poly, grow):
    """mark lattice points inside a convex-ish polygon grown by `grow` units"""
    P = np.array(poly, float)
    lo = P.min(0) - grow - CELL; hi = P.max(0) + grow + CELL
    i0, i1 = max(0, li(lo[0])), min(NX - 1, li(hi[0])); j0, j1 = max(0, lj(lo[1])), min(NY - 1, lj(hi[1]))
    if i0 > i1 or j0 > j1: return
    gx, gy = np.meshgrid(X0 + np.arange(i0, i1 + 1) * CELL, Y0 + np.arange(j0, j1 + 1) * CELL, indexing='ij')
    inside, d = TI._poly_inside_dist(gx, gy, [tuple(q) for q in P])
    M[i0:i1 + 1, j0:j1 + 1] |= inside | (d <= grow)


def mesh_faces(m, n):
    """world-space face loops of a CMapMesh: [(k, 3) arrays]"""
    md = m.g(n, b'meshData')
    pos = np.array(sdata(m, streams(m, m.g(md, b'vertexData'))['position:0'])[2], float) if 'position:0' in streams(m, m.g(md, b'vertexData')) else None
    if pos is None: return []
    o = np.array(m.g(n, b'origin', [0, 0, 0]), float); a = m.g(n, b'angles', [0, 0, 0]); sc = np.array(m.g(n, b'scales', [1, 1, 1]), float)
    P = pos * sc
    if any(a): P = np.array([V.xform(list(q), [0, 0, 0], a) for q in P])
    P = P + o
    fei, evi, nxt, vdi = (m.g(md, k) for k in (b'faceEdgeIndices', b'edgeVertexIndices', b'edgeNextIndices', b'vertexDataIndices'))
    out = []
    for he in fei:
        loop, h = [], he
        for _ in range(256):
            loop.append(vdi[evi[h]]); h = nxt[h]
            if h == he: break
        out.append(P[loop])
    return out


def rect_fill(M, x0, y0, x1, y1, grow=0.0):
    i0, i1 = max(0, li(x0 - grow)), min(NX - 1, li(x1 + grow)); j0, j1 = max(0, lj(y0 - grow)), min(NY - 1, lj(y1 + grow))
    if i0 <= i1 and j0 <= j1: M[i0:i1 + 1, j0:j1 + 1] = True


def disc_fill(M, x, y, r):
    i0, i1 = max(0, li(x - r) - 1), min(NX - 1, li(x + r) + 1); j0, j1 = max(0, lj(y - r) - 1), min(NY - 1, lj(y + r) + 1)
    if i0 > i1 or j0 > j1: return
    gx, gy = np.meshgrid(X0 + np.arange(i0, i1 + 1) * CELL, Y0 + np.arange(j0, j1 + 1) * CELL, indexing='ij')
    M[i0:i1 + 1, j0:j1 + 1] |= np.hypot(gx - x, gy - y) <= r


TREES = ('models/foliage/trees/', 'tree_poplar', 'maple_tree', 'tree_small_beech')


def protect_mask(m, sc, tiles, log):
    """hard mask (bool on the lattice) and a per-layer record of what made it"""
    X, Y = lat_xy()
    layers = {}
    def layer(name):
        layers[name] = np.zeros((NX, NY), bool); return layers[name]
    # trenches, fire steps, banks and parapets: the layout's trench distance (both sides) and the parapet sheets themselves
    L = layer('trenches')
    d, _ = LY.trench_dist(X, Y)
    L |= d < 170.0
    par = m.parent_of()
    tile_ids = {t['i'] for t in tiles}
    for n, p in m.walk():
        if m.type(n) != b'CMapMesh' or n in tile_ids: continue
        md = m.g(n, b'meshData')
        if md is None or md < 0: continue
        mats = [x.decode().lower() for x in m.g(md, b'materials') or []]
        faces = mesh_faces(m, n)
        if not faces: continue
        allp = np.concatenate(faces)
        lo, hi = allp.min(0), allp.max(0)
        if hi[2] < -1000: continue                                          # the lobby
        pcls = m.cls(p) if m.type(p) == b'CMapEntity' else ''
        vg = m.g(n, b'customVisGroup') or b''; vg = vg.decode() if isinstance(vg, bytes) else vg
        if mats and mats[0] in BLENDS: name, grow = 'parapets', 16.0        # parapet / parados sheets (16 u)
        elif any('water' in x for x in mats): name, grow = 'water sheets', 48.0
        elif any('toolsinvisibleladder' in x for x in mats): name, grow = 'ladder volumes', 128.0
        elif pcls == 'func_nav_markup' or any('toolsnavattribute' in x for x in mats): name, grow = 'nav markup', 48.0
        elif any('toolsplayerclip' in x or 'toolsclip' in x for x in mats): name, grow = 'clips', 24.0
        elif any(LMRES in x or 'toolsskybox' in x for x in mats): continue
        elif vg in ('', 'tw_user'): name, grow = 'user objects', 48.0
        else: name, grow = 'other world meshes', 32.0                       # the gallery mesh and anything unforeseen
        L = layers[name] if name in layers else layer(name)
        for f in faces: poly_fill(L, f[:, :2], grow)
    # saps and galleries (the ground over them must not drop toward the roofs)
    L = layer('saps and galleries')
    for (x0, y0, x1, y1, k) in LY.tunnels(): rect_fill(L, x0, y0, x1, y1, 112.0)
    # entities
    Lpit = layer('mortar pits'); Lpt = layer('spawns, posts, seats, heal points'); Lex = layer('user explosions'); Lfx = layer('ground effects')
    Lus = layers.get('user objects') if 'user objects' in layers else layer('user objects')
    for e in m.entities():
        c = m.cls(e); o = m.origin(e); nm = m.name(e)
        if o[2] < -1000: continue
        vg = m.g(e, b'customVisGroup') or b''; vg = vg.decode() if isinstance(vg, bytes) else vg
        if nm.startswith('mortarpit_'): disc_fill(Lpit, o[0], o[1], 340.0)
        if c in ('info_player_terrorist', 'info_player_counterterrorist', 'info_teleport_destination', 'info_target', 'func_nav_markup'):
            disc_fill(Lpt, o[0], o[1], 112.0)
        if c == 'env_explosion': disc_fill(Lex, o[0], o[1], 200.0)
        if c in ('info_particle_system', 'env_shake', 'point_soundevent') and o[2] < 200: disc_fill(Lfx, o[0], o[1], 64.0)
        if vg in ('', 'tw_user') and c not in ('prop_static', 'prop_dynamic'): disc_fill(Lus, o[0], o[1], 128.0)
    # every prop footprint (trees by a trunk disc: their crowns overhang everything)
    Lpr = layer('prop footprints'); Ltr = layer('tree trunks'); Lld = layer('ladders')
    for p in sc['props']:
        if p['o'][2] < -1000: continue
        mdl = p['model']
        if any(k in mdl for k in TREES) and 'shattered' not in mdl:
            disc_fill(Ltr, p['o'][0], p['o'][1], 48.0 * max(p['s'][0], 0.5) + 16.0)
        else:
            grow = 64.0 if 'ladder' in mdl else 12.0       # 12: a footprint smaller than a lattice step still marks a point
            poly_fill(Lld if 'ladder' in mdl else (Lus if p['vg'] in ('', 'tw_user') else Lpr), p['poly'], grow)
    # airfield: the runway (parked planes, hangar, stores) and the plane lanes over the rear to the mortar line
    L = layer('runways and plane lanes')
    for s in (-1, 1):
        a, b = sorted((s * 4236.0, s * 7014.0)); rect_fill(L, a, -940.0, b, 940.0)
        a, b = sorted((s * 3200.0, s * 4300.0)); rect_fill(L, a, -900.0, b, 900.0)
    # the woods skirmish: track, fence, clearing, exit ladders (walkable, user-edited)
    L = layer('woods skirmish')
    rect_fill(L, -1400.0, 2750.0, 1400.0, 4560.0)
    for s in (-1, 1):
        L |= TI.along(X, Y, [(170.0, [(s * 1716.0, 2860.0), (s * 1716.0, 2995.0), (s * 1080.0, 3560.0)])])
    # the terrain edge meets the 3D skybox
    L = layer('terrain edge')
    L |= (np.abs(X) >= X1 - 192.0) | (np.abs(Y) >= Y1 - 192.0)
    hard = np.zeros((NX, NY), bool)
    for k, v in layers.items(): hard |= v
    log('protect mask: %.1f %% of the lattice; ' % (100 * hard.mean()) + ', '.join('%s %.1f %%' % (k, 100 * v.mean()) for k, v in layers.items()))
    return hard, layers


# ================================================================ tile plans, frozen faces, feather
class Plan:
    """a tile's grid lines (world x, y) after the patch: the original grid, or 16 u where it is re-gridded"""
    def __init__(s, t, dense):
        s.t = t; s.dense = dense; s.r = 16 if dense else t['res']
        s.xs = t['tx'] + np.arange(TILE // s.r + 1) * float(s.r); s.ys = t['ty'] + np.arange(TILE // s.r + 1) * float(s.r)


def frozen_region(plans, hard):
    """lattice region covered by every face (of the new grids) that touches the hard mask (+1 lattice step): those faces keep their
    vertices exactly. Uses a summed-area table for the rectangle queries."""
    H = hard
    S = np.zeros((NX + 1, NY + 1), np.int64); S[1:, 1:] = H.cumsum(0).cumsum(1)
    R = np.zeros((NX, NY), bool)
    nfz = 0
    for pl in plans:
        t = pl.t
        a = ((pl.xs - X0) / CELL).round().astype(int); b = ((pl.ys - Y0) / CELL).round().astype(int)
        A0, B0 = np.meshgrid(a[:-1], b[:-1], indexing='ij'); A1, B1 = np.meshgrid(a[1:], b[1:], indexing='ij')
        cnt = S[A1 + 1, B1 + 1] - S[A0, B1 + 1] - S[A1 + 1, B0] + S[A0, B0]
        fz = cnt > 0
        for ii, jj in zip(*np.nonzero(fz)):
            R[a[ii]:a[ii + 1] + 1, b[jj]:b[jj + 1] + 1] = True
        nfz += int(fz.sum())
    # along an edge shared with a coarser tile the finer tile's edge vertices follow the coarse ones: a frozen point anywhere on one
    # coarse segment freezes the whole segment (both coarse vertices), or the seam would pull a frozen face
    nb = {(pl.t['tx'], pl.t['ty']): pl for pl in plans}
    for pl in plans:
        tx, ty = pl.t['tx'], pl.t['ty']
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            q = nb.get((tx + dx * TILE, ty + dy * TILE))
            if q is None or q.r <= pl.r: continue
            k = int(q.r / CELL)
            for s0 in range(0, int(TILE / CELL), k):
                if dx: i = li(tx if dx < 0 else tx + TILE); seg = (slice(i, i + 1), slice(lj(ty) + s0, lj(ty) + s0 + k + 1))
                else: j = lj(ty if dy < 0 else ty + TILE); seg = (slice(li(tx) + s0, li(tx) + s0 + k + 1), slice(j, j + 1))
                if R[seg].any(): R[seg] = True
    return R, nfz


def free_weight(R):
    """0 on the frozen region, rising smoothly to 1 over FEATHER units outside it"""
    d = ndimage.distance_transform_edt(~R) * CELL
    w = TI.smoothstep(0.0, FEATHER, d)
    w[R] = 0.0
    return w


def res_map(plans):
    """per lattice point: the coarsest grid among the tiles that hold it (shared edge points take the coarser neighbour)"""
    M = np.zeros((NX, NY), np.int32)
    for pl in plans:
        i0, j0 = li(pl.t['tx']), lj(pl.t['ty']); n = int(TILE / CELL)
        M[i0:i0 + n + 1, j0:j0 + n + 1] = np.maximum(M[i0:i0 + n + 1, j0:j0 + n + 1], pl.r)
    return M


def base_lattice(tiles):
    """current terrain height on the lattice (each tile's surface under the 00-11 split; nan where there is no terrain)"""
    H = np.full((NX, NY), np.nan)
    n = int(TILE / CELL)
    loc = np.arange(n + 1) * CELL
    LX, LYy = np.meshgrid(loc, loc, indexing='ij')
    for t in tiles:
        Z = tile_grid(t)
        h = tri_interp(Z, t['res'], LX, LYy)
        i0, j0 = li(t['tx']), lj(t['ty'])
        blk = H[i0:i0 + n + 1, j0:j0 + n + 1]
        ok = np.isfinite(h)
        blk[ok] = h[ok]
    miss = ~np.isfinite(H)
    if miss.any():
        idx = ndimage.distance_transform_edt(miss, return_distances=False, return_indices=True)
        H = H[tuple(idx)]
    return H, miss


def cell_res(plans):
    """res of the tile holding each 16-u lattice cell (NX - 1, NY - 1)"""
    C = np.zeros((NX - 1, NY - 1), np.int32)
    n = int(TILE / CELL)
    for pl in plans:
        i0, j0 = li(pl.t['tx']), lj(pl.t['ty'])
        C[i0:i0 + n, j0:j0 + n] = pl.r
    return C


def seam_distance(plans):
    """distance (units) from every lattice point to the nearest edge between tiles of different grid size"""
    C = cell_res(plans)
    S = np.zeros((NX, NY), bool)
    a = C[:-1, :] != C[1:, :]; S[1:-1, :-1] |= a; S[1:-1, 1:] |= a
    b = C[:, :-1] != C[:, 1:]; S[:-1, 1:-1] |= b; S[1:, 1:-1] |= b
    if not S.any(): return np.full((NX, NY), 1e9)
    return ndimage.distance_transform_edt(~S) * CELL


# ================================================================ the detail layer
def fbm(X, Y, scale, seed, octaves=4):
    return TI.N.fbm(X / scale, Y / scale, 0.37 + seed * 0.11, octaves, seed=seed)


def crater_shape(X, Y, cx, cy, r, dd, ph):
    """a fresh shell hole: bowl, raised lip, ejecta fading out to ~2.2 r; returns (dz, bowl 0..1, ejecta 0..1)"""
    rho = np.hypot(X - cx, Y - cy) / r
    ang = np.arctan2(Y - cy, X - cx)
    wob = 1.0 + 0.10 * np.sin(3 * ang + ph) + 0.06 * np.sin(5 * ang + 2.1 * ph)
    q = rho / wob
    bowl = -dd * np.clip(1 - q ** 2, 0, None) ** 1.25
    lip = 0.22 * dd * np.exp(-((q - 1.0) / 0.22) ** 2)
    ej = 0.07 * dd * np.exp(-(q - 1.0) * 2.2) * (q > 1.0) * (1 + 0.5 * np.sin(7 * ang + ph))
    return bowl + lip + ej, np.clip(1.25 - q, 0, 1), np.clip(1.0 - (q - 1.0) / 1.2, 0, 1) * (q > 0.9)


def polyline_frame(pts, X, Y):
    """distance along (s), signed lateral offset (q) and distance (d) of each point to a polyline (nearest segment); and its length"""
    P = np.asarray(pts, float)
    best = np.full(X.shape, np.inf); S = np.zeros(X.shape); Q = np.zeros(X.shape)
    cum = 0.0
    for a, b in zip(P[:-1], P[1:]):
        ab = b - a; L = math.hypot(*ab)
        if L < 1e-6: continue
        u = ab / L
        rx, ry = X - a[0], Y - a[1]
        t = np.clip(rx * u[0] + ry * u[1], 0, L)
        q = -rx * u[1] + ry * u[0]
        d = np.hypot(rx - t * u[0], ry - t * u[1])
        m_ = d < best
        best = np.where(m_, d, best); S = np.where(m_, cum + t, S); Q = np.where(m_, q, Q)
        cum += L
    return S, Q, best, cum


def track_path(o, yaw, length, rng, step=16.0):
    """a gently curving path leading back from a vehicle at o facing yaw: where it came from"""
    a = math.radians(yaw) + math.pi
    x, y = o[0] + math.cos(a) * 150.0, o[1] + math.sin(a) * 150.0
    k = rng.uniform(-0.0009, 0.0009)
    pts = [(x, y)]
    for i in range(int(length / step)):
        a += k * step + rng.normal(0, 0.004)
        x += math.cos(a) * step; y += math.sin(a) * step
        pts.append((x, y))
    return pts


def short(mdl): return mdl.rsplit('/', 1)[-1].replace('.vmdl', '')


def window(cx, cy, R_):
    i0, i1 = max(0, li(cx - R_)), min(NX - 1, li(cx + R_)); j0, j1 = max(0, lj(cy - R_)), min(NY - 1, lj(cy + R_))
    return slice(i0, i1 + 1), slice(j0, j1 + 1)


def at(A, x, y):
    i, j = li(x), lj(y)
    return A[i, j] if 0 <= i < NX and 0 <= j < NY else 0


def corridor(X, Y, pts, reach):
    """lattice window around a polyline and its frame there"""
    P = np.asarray(pts, float)
    si, sj = window((P[:, 0].min() + P[:, 0].max()) / 2, (P[:, 1].min() + P[:, 1].max()) / 2,
                    max(P[:, 0].max() - P[:, 0].min(), P[:, 1].max() - P[:, 1].min()) / 2 + reach)
    S, Q, D_, L = polyline_frame(P, X[si, sj], Y[si, sj])
    return si, sj, S, Q, D_, L


TANKS = ('tank_a7v', 'tank_renault', 'wreck_tank')


def tank_tracks(sc, seed, hard):
    """for each tank in no man's land, the track it left: of 40 candidate curves leading back from it (within 70 deg of straight back),
    the one whose two treads cross the least protected ground (a track under a protected prop or pool would be cut off there)"""
    out = []
    for p in sorted(sc['props'], key=lambda q: q['i']):
        if not any(k in p['model'] for k in TANKS) or abs(p['o'][0]) > 1450 or p['o'][2] < -1000: continue
        half = 30.0 if 'renault' in p['model'] else 50.0
        rng = np.random.RandomState(seed + 7 + int(p['i']))
        best = None
        for k in range(40):
            trk = track_path(p['o'], p['yaw'] + rng.uniform(-70, 70), 1100.0, rng)
            P = np.asarray(trk); dx = np.gradient(P[:, 0]); dy = np.gradient(P[:, 1]); L = np.hypot(dx, dy) + 1e-9
            score = 0.0
            for c in (-half, half):
                qx = P[:, 0] - dy / L * c; qy = P[:, 1] + dx / L * c
                ii = np.round((qx - X0) / CELL).astype(int); jj = np.round((qy - Y0) / CELL).astype(int)
                ok = (ii >= 0) & (ii < NX) & (jj >= 0) & (jj < NY) & (np.abs(qx) < 1380)
                free = np.zeros(len(qx)); free[ok] = ~hard[ii[ok], jj[ok]]
                score += free[:int(len(free) * 0.7)].sum()
            if best is None or score > best[0]: best = (score, trk)
        out.append((p, best[1], half))
    return out


def rut_lines():
    """the four lorry tracks along the airfield edges: (side, edge, points)"""
    out = []
    for s in (-1, 1):
        for e in (-1, 1):
            xs = np.arange(4700.0, 6580.0 + 1, 16.0) * s
            yc = e * (1100.0 + 8.0 * fbm(xs, np.full(xs.shape, 77.0 * e), 600, 41, 3))
            out.append((s, e, list(zip(xs.tolist(), yc.tolist()))))
    return out


def build_detail(H, w, Rdist, rmap, seamd, sc, seed, log, hard, quick=False):
    X, Y = lat_xy()
    rng = np.random.RandomState(seed)
    ax, ay = np.abs(X), np.abs(Y)
    nml = (1 - TI.smoothstep(1300, 1480, ax)) * (1 - TI.smoothstep(3500, 3900, ay))
    rear = TI.smoothstep(2250, 2450, ax) * (1 - TI.smoothstep(4300, 4500, ax)) * (1 - TI.smoothstep(4500, 4800, ay))
    flank = (1 - TI.smoothstep(2200, 2400, ax)) * TI.smoothstep(3300, 3600, ay) * (1 - TI.smoothstep(5200, 5600, ay))
    battle = np.maximum(np.maximum(nml, rear), flank)
    forest = 1 - battle
    F = np.zeros((NX, NY)); mud = np.zeros((NX, NY)); wet = np.zeros((NX, NY)); dirt = np.zeros((NX, NY))
    rec = dict(craters=[], puddles=[], tracks=[], ruts=[])
    # ---- fresh shell craters: no man's land thick, the rear and the flanks thinner (counter-battery fire near the mortar line)
    zones = [('nml', (-1420, 1420), (-3450, 2700), (24.0, 64.0), (0.26, 0.36), 330),
             ('rear', (2380, 4250), (-4500, 4500), (30.0, 90.0), (0.24, 0.34), 120),
             ('flank', (-2250, 2250), (-5400, -3500), (60.0, 130.0), (0.22, 0.32), 40),
             ('flank', (-2250, 2250), (4600, 5400), (60.0, 130.0), (0.22, 0.32), 20)]
    placed = []
    for zone, xr, yr, rr, dr, want in zones:
        n = 0
        for _ in range(want * 40):
            if n >= want: break
            x = rng.uniform(*xr); y = rng.uniform(*yr)
            if zone == 'rear': x *= rng.choice([-1, 1])
            r = math.exp(rng.uniform(math.log(rr[0]), math.log(rr[1])))
            res = at(rmap, x, y)
            if res == 0 or r < 1.55 * res: continue
            if at(Rdist, x, y) < 1.15 * r or at(seamd, x, y) < 1.4 * r: continue
            if any(math.hypot(x - px, y - py) < 0.75 * (r + pr) for px, py, pr in placed): continue
            dep = rng.uniform(*dr)
            si, sj = window(x, y, 2.3 * r)
            dz, bowl, ej = crater_shape(X[si, sj], Y[si, sj], x, y, r, dep * r, rng.uniform(0, 6.28))
            F[si, sj] += dz
            mud[si, sj] = np.maximum(mud[si, sj], np.maximum(bowl, 0.7 * ej))
            wet[si, sj] = np.maximum(wet[si, sj], 0.6 * np.clip((bowl - 0.55) / 0.45, 0, 1))
            placed.append((x, y, r)); rec['craters'].append(dict(zone=zone, x=round(x, 1), y=round(y, 1), r=round(r, 1), depth=round(dep * r, 1)))
            n += 1
    log('craters: %d placed (%s)' % (len(placed), ', '.join('%s %d' % (z, sum(c['zone'] == z for c in rec['craters'])) for z in ('nml', 'rear', 'flank'))))
    # ---- tank-track mud ruts leading back from the tanks in no man's land
    for p, trk, half in tank_tracks(sc, seed, hard):
        si, sj, s_, q_, d_, L = corridor(X, Y, trk, half + 80)
        along = TI.smoothstep(0, 140, s_) * (1 - TI.smoothstep(0.65 * L, L, s_)) * (0.55 + 0.45 * np.clip(fbm(X[si, sj], Y[si, sj], 160, 31) * 1.6 + 0.5, 0, 1))
        dz = np.zeros(s_.shape); tr = np.zeros(s_.shape)
        for c in (-half, half):
            g = np.exp(-((q_ - c) / 14.0) ** 2)
            dz += -4.8 * g + 1.3 * np.exp(-((np.abs(q_ - c) - 25.0) / 8.0) ** 2)
            tr = np.maximum(tr, g)
        on = (d_ < half + 60) * along
        F[si, sj] += dz * on; mud[si, sj] = np.maximum(mud[si, sj], 0.9 * tr * on); wet[si, sj] = np.maximum(wet[si, sj], 0.45 * tr * on)
        rec['tracks'].append(dict(model=short(p['model']), o=[round(v) for v in p['o'][:2]], length=round(L), gauge=2 * half, pts=[[round(a_), round(b_)] for a_, b_ in trk[::8]]))
    log('tank tracks: %d' % len(rec['tracks']))
    # ---- lorry ruts along the airfield edges (inside the clearing, outside the runway box)
    for s, e, pts in rut_lines():
        si, sj, s_, q_, d_, L = corridor(X, Y, pts, 90)
        along = TI.smoothstep(0, 180, s_) * (1 - TI.smoothstep(L - 180, L, s_))
        pd = np.clip((fbm(X[si, sj], Y[si, sj], 140, 43, 2) - 0.25) * 3.0, 0, 1)
        dz = np.zeros(s_.shape); gr = np.zeros(s_.shape)
        for c in (-32.0, 32.0):
            g = np.exp(-((q_ - c) / 11.0) ** 2)
            dz += -(3.6 + 1.8 * pd) * g + 0.9 * np.exp(-((np.abs(q_ - c) - 20.0) / 7.0) ** 2)
            gr = np.maximum(gr, g)
        on = along * (d_ < 80)
        F[si, sj] += dz * on
        dirt[si, sj] = np.maximum(dirt[si, sj], on * np.maximum(0.95 * gr, 0.45 * np.exp(-(q_ / 32.0) ** 2)))
        wet[si, sj] = np.maximum(wet[si, sj], on * gr * pd * 0.8)
        rec['ruts'].append(dict(side='ct' if s > 0 else 't', edge='north' if e > 0 else 'south', x=[round(pts[0][0]), round(pts[-1][0])],
                                y=round(float(np.mean([q[1] for q in pts]))), length=round(L), pts=[[round(a_), round(b_)] for a_, b_ in pts[::8]]))
    log('airfield ruts: %d' % len(rec['ruts']))
    # ---- puddle basins in the low spots of the churned ground
    cav = TI.cavity(H + F, CELL, 160.0)
    cand = np.argwhere((cav > 0.22) & (battle > 0.5) & (w > 0.9))
    rng.shuffle(cand)
    pud = []
    for i, j in cand[:6000]:
        if len(pud) >= 110: break
        x, y = X[i, j], Y[i, j]
        r = rng.uniform(40, 110)
        if r < 1.8 * rmap[i, j] or Rdist[i, j] < 0.6 * r or seamd[i, j] < 1.4 * r: continue
        if any(math.hypot(x - px, y - py) < pr + r + 40 for px, py, pr in pud): continue
        if any(math.hypot(x - px, y - py) < pr * 0.9 + r for px, py, pr in placed): continue
        d = rng.uniform(2.0, 4.5)
        si, sj = window(x, y, 1.3 * r)
        rho = np.hypot(X[si, sj] - x, Y[si, sj] - y) / (r * (1 + 0.15 * fbm(X[si, sj], Y[si, sj], r * 0.7, 51, 2)))
        b = 1 - TI.smoothstep(0.5, 1.0, rho)
        F[si, sj] += -d * b
        wet[si, sj] = np.maximum(wet[si, sj], b); mud[si, sj] = np.maximum(mud[si, sj], b)
        pud.append((x, y, r)); rec['puddles'].append(dict(x=round(float(x)), y=round(float(y)), r=round(r), depth=round(d, 1)))
    log('puddle basins: %d' % len(pud))
    # ---- subtle noise: churn in the battle zone, long swells in the woods
    F += battle * (1.4 * fbm(X, Y, 150, 61) + 2.2 * fbm(X, Y, 480, 62, 3)) + forest * 3.0 * fbm(X, Y, 700, 63, 3)
    # ---- erosion over all of it (create/terrain_img.py): rills and slumped crater lips; protect = 1 - free weight
    Fe = TI.Field(H + F, (X0, Y0, X1, Y1), CELL)
    recipe = dict(gully_depth=0.0 if quick else 5.0, gully_passes=2, gully_area0=6.0, gully_area1=600.0, gully_slope0=3.0, gully_slope1=14.0,
                  gully_wander=0.0, drops=0.0 if quick else 0.6, drop_steps=40, drop_capacity=4.0, drop_erosion=0.2, drop_deposition=0.3,
                  drop_highpass=6.0, drop_steep=[34.0, 44.0], drop_steep_cut=0.6, outcrop_height=0.0, thermal_talus=38.0, thermal_iters=12,
                  max_cut=8.0, max_fill=6.0, terrace_step=0.0, seed=seed)
    t0 = time.time()
    De, info = TI.detail(Fe, protect=1.0 - w, recipe=recipe, log=lambda *a: log('  erosion: ' + ' '.join(str(x) for x in a)))
    log('erosion layer: %.1f .. %.1f u (%.0f s)' % (De.Z.min(), De.Z.max(), time.time() - t0))
    D = F + De.Z
    mud = np.maximum(mud, np.clip(-De.Z / 3.0, 0, 1) * 0.6)
    # ---- soft limits, the high-frequency part faded at grid-size seams, then zero on everything protected
    D = np.where(D < 0, MAX_CUT * np.tanh(D / MAX_CUT), MAX_FILL * np.tanh(D / MAX_FILL))
    low = TI.blur(D, 4.0)
    sf = TI.smoothstep(16.0, 112.0, seamd)
    D = (low + (D - low) * sf) * w
    paint = dict(mud=np.clip(mud * w, 0, 1), wet=np.clip(wet * w, 0, 1), dirt=np.clip(dirt * w, 0, 1))
    rec['erosion'] = dict(min=round(float(De.Z.min()), 2), max=round(float(De.Z.max()), 2))
    return D, paint, rec


def vertex_layers(D, w):
    """per grid size: the layer as vertices of that size sample it (anti-aliased), multiplied by the free weight again so it is exactly 0
    on the frozen region"""
    return {r: ((TI.blur(D, 0.42 * r / CELL) if r > 16 else D) * w) for r in (16, 32, 64, 128)}


# ================================================================ which tiles get the 16-u grid
def dense_candidates(tiles, sc, seed, hard):
    """no man's land tiles (32 u, |x| <= 1536, y -3072 .. 2560) -> 0.40, and every tile a tank track or an airfield rut runs over -> 0.10:
    {(tx, ty): the unfrozen share the tile needs at 16 u to be worth re-gridding}"""
    want = {}
    for t in tiles:
        if t['res'] == 32 and -1536 <= t['tx'] and t['tx'] + TILE <= 1536 and -3072 <= t['ty'] and t['ty'] + TILE <= 2560: want[(t['tx'], t['ty'])] = 0.40
    lines = [(trk, half + 60.0) for p, trk, half in tank_tracks(sc, seed, hard)] + [(pts, 60.0) for s, e, pts in rut_lines()]
    for pts, reach in lines:
        P = np.asarray(pts, float)
        for t in tiles:
            cx, cy = t['tx'] + TILE / 2, t['ty'] + TILE / 2
            if (np.maximum(np.abs(P[:, 0] - cx) - TILE / 2, 0) ** 2 + np.maximum(np.abs(P[:, 1] - cy) - TILE / 2, 0) ** 2).min() <= reach ** 2:
                want[(t['tx'], t['ty'])] = 0.10
    return want


def make_plans(tiles, hard, dense_keys, log=print):
    """plans with the 16-u grid on the candidate tiles that keep at least their share (dense_keys value) unfrozen at 16 u"""
    plans = [Plan(t, (t['tx'], t['ty']) in dense_keys and t['full']) for t in tiles]
    R, _ = frozen_region(plans, hard)
    n = int(TILE / CELL)
    keep = []
    for pl in plans:
        if not pl.dense: continue
        i0, j0 = li(pl.t['tx']), lj(pl.t['ty'])
        if 1.0 - R[i0:i0 + n + 1, j0:j0 + n + 1].mean() < dense_keys[(pl.t['tx'], pl.t['ty'])]: keep.append(pl)
    for pl in keep:                                   # too protected to be worth the extra faces: back to its own grid
        pl.__init__(pl.t, False)
    log('16-u grid: %d tiles (%d candidates; %d left on their grid, mostly protected)' % (sum(p.dense for p in plans), len(dense_keys), len(keep)))
    return plans


# ================================================================ applying the layer to the tiles
def neighbours(plans):
    return {(pl.t['tx'], pl.t['ty']): pl for pl in plans}


def vertex_delta(pl, gx, gy, VL, rmap, nb):
    """delta per vertex (world gx, gy arrays) of plan pl; along an edge shared with a coarser tile the vertices between the coarse ones
    follow the straight line between them (the seams stay closed)"""
    ii = np.round((gx - X0) / CELL).astype(int); jj = np.round((gy - Y0) / CELL).astype(int)
    rv = rmap[ii, jj]
    d = np.zeros(len(gx))
    for r in (16, 32, 64, 128):
        s = rv == r
        if s.any(): d[s] = VL[r][ii[s], jj[s]]
    tx, ty = pl.t['tx'], pl.t['ty']
    for (dx, dy, on, along) in ((-1, 0, gx == tx, gy), (1, 0, gx == tx + TILE, gy), (0, -1, gy == ty, gx), (0, 1, gy == ty + TILE, gx)):
        q = nb.get((tx + dx * TILE, ty + dy * TILE))
        if q is None or q.r <= pl.r or not on.any(): continue
        R = q.r
        a = along[on]
        lo_ = np.floor(a / R) * R; hi_ = lo_ + R; f = (a - lo_) / R
        mid = f > 1e-9
        if not mid.any(): continue
        # deltas at the coarse vertices on this edge
        if dx: xa = np.full(lo_.shape, gx[on][0]); ya, yb = lo_, hi_; xb = xa
        else: ya = np.full(lo_.shape, gy[on][0]); xa, xb = lo_, hi_; yb = ya
        def dat(x, y):
            i_ = np.clip(np.round((x - X0) / CELL).astype(int), 0, NX - 1); j_ = np.clip(np.round((y - Y0) / CELL).astype(int), 0, NY - 1)
            out = np.zeros(len(x))
            for r in (16, 32, 64, 128):
                s = rmap[i_, j_] == r
                if s.any(): out[s] = VL[r][i_[s], j_[s]]
            return out
        da, db = dat(xa, ya), dat(xb, yb)
        idx = np.nonzero(on)[0]
        d[idx[mid]] = (da * (1 - f) + db * f)[mid]
    return d


def paint_mod(mat, blend, tint, mud, wet, dirt):
    """new (blend x, tint) per vertex from the old ones: battle blend 0 = mud, forest blend 1 = dirt; wet ground darker"""
    b = np.array(blend, float); t = np.array(tint, float)
    if mat == BLEND_BATTLE:
        b[:, 0] = b[:, 0] * (1 - mud)
    else:
        b[:, 0] = b[:, 0] + (1 - b[:, 0]) * np.maximum(dirt, 0.8 * mud)
    f = 1.0 - 0.26 * wet - 0.07 * mud
    t[:, :3] = t[:, :3] * f[:, None]
    return b, t


def face_loops(m, md):
    fei, evi, nxt = (m.g(md, k) for k in (b'faceEdgeIndices', b'edgeVertexIndices', b'edgeNextIndices'))
    loops = []
    for he in fei:
        hs, h = [], he
        for _ in range(16):
            hs.append(h); h = nxt[h]
            if h == he: break
        loops.append(hs)
    return loops, evi


def newell(P):
    q = np.roll(P, -1, axis=0)
    n = np.array([np.sum((P[:, 1] - q[:, 1]) * (P[:, 2] + q[:, 2])), np.sum((P[:, 2] - q[:, 2]) * (P[:, 0] + q[:, 0])),
                  np.sum((P[:, 0] - q[:, 0]) * (P[:, 1] + q[:, 1]))])
    l = np.linalg.norm(n)
    return n / l if l > 0 else np.array([0, 0, 1.0])


def apply_zonly(m, pl, VL, rmap, nb, PL):
    """heights + paint + normals of a tile that keeps its grid; returns (changed vertices, max |delta|, faces newly steeper than STEEP deg)"""
    t = pl.t; md = t['md']
    vst = streams(m, m.g(md, b'vertexData')); fst = streams(m, m.g(md, b'faceVertexData'))
    pos = sdata(m, vst['position:0'])
    P = np.array(pos[2], float)
    vdi = m.g(md, b'vertexDataIndices')
    d = vertex_delta(pl, P[:, 0], P[:, 1], VL, rmap, nb)
    if not np.any(d): return 0, 0.0, 0
    P2 = P.copy(); P2[:, 2] += d
    pos[2] = [[float(a), float(b), float(c)] for a, b, c in P2]
    loops, evi = face_loops(m, md)
    evd = m.g(md, b'edgeVertexDataIndices')
    nrm = sdata(m, fst['normal:0'])
    nn = [list(map(float, v)) for v in nrm[2]]
    steep = 0
    vi = {}
    for hs in loops:
        vidx = [vdi[evi[h]] for h in hs]
        if not np.any(d[vidx]): continue
        n = newell(P2[vidx])
        if n[2] < COS_STEEP <= newell(P[vidx])[2]: steep += 1
        for h in hs: nn[evd[h]] = [float(n[0]), float(n[1]), float(n[2])]
    nrm[2] = nn
    # paint: every face-vertex takes its vertex's change
    ii = np.round((P[:, 0] - X0) / CELL).astype(int); jj = np.round((P[:, 1] - Y0) / CELL).astype(int)
    r = pl.r
    mud, wet, dirt = (PL[k][r][ii, jj] for k in ('mud', 'wet', 'dirt'))
    if 'VertexPaintBlendParams:0' in fst and 'VertexPaintTintColor:0' in fst:
        bp = sdata(m, fst['VertexPaintBlendParams:0']); tc = sdata(m, fst['VertexPaintTintColor:0'])
        efi = m.g(md, b'edgeFaceIndices')
        hs = [h for h in range(len(evi)) if efi[h] >= 0]
        v_of = np.array([vdi[evi[h]] for h in hs]); fv = [evd[h] for h in hs]
        sel = (mud[v_of] > 1e-4) | (wet[v_of] > 1e-4) | (dirt[v_of] > 1e-4)
        if sel.any():
            B = np.array(bp[2], float); T = np.array(tc[2], float)
            fvs = np.array(fv)[sel]; vs = v_of[sel]
            b2, t2 = paint_mod(t['mat'], B[fvs], T[fvs], mud[vs], wet[vs], dirt[vs])
            B[fvs] = b2; T[fvs] = t2
            bp[2] = B.tolist(); tc[2] = T.tolist()
    return int(np.count_nonzero(d)), float(np.abs(d).max()), steep


def grid_halfedges(nx, ny):
    """half-edge arrays of an open (nx x ny)-cell grid sheet, faces counter-clockwise from +z, in vmesh.polymesh_open's layout
    (opposite = i ^ 1, boundary half-edges with face -1, a boundary vertex points at its outgoing boundary half-edge)"""
    vid = lambda i, j: i * (ny + 1) + j
    faces = []
    for i in range(nx):
        for j in range(ny):
            faces.append([vid(i, j), vid(i + 1, j), vid(i + 1, j + 1), vid(i, j + 1)])
    he_from, he_to, he_face, key, face_first = [], [], [], {}, []
    for f, loop in enumerate(faces):
        face_first.append(len(he_to))
        for k in range(4):
            a, b = loop[k], loop[(k + 1) % 4]
            key[(a, b)] = len(he_to); he_from.append(a); he_to.append(b); he_face.append(f)
    nfh = len(he_to)
    nxt = [0] * nfh
    for f in range(len(faces)):
        s = face_first[f]
        for k in range(4): nxt[s + k] = s + (k + 1) % 4
    for (a, b), i in list(key.items()):
        if (b, a) not in key:
            key[(b, a)] = len(he_to); he_from.append(b); he_to.append(a); he_face.append(-1); nxt.append(-1)
    nhe = len(he_to)
    out_b = {he_from[i]: i for i in range(nfh, nhe)}
    for i in range(nfh, nhe): nxt[i] = out_b.get(he_to[i], i)
    order, done = [], set()
    for i in range(nhe):
        if i in done: continue
        j = key[(he_to[i], he_from[i])]; order += [i, j]; done |= {i, j}
    old = np.array(order)
    remap = np.empty(nhe, np.int64); remap[old] = np.arange(nhe)
    E_dest = np.array(he_to)[old]; E_face = np.array(he_face)[old]; E_next = remap[np.array(nxt)[old]]
    E_opp = np.arange(nhe) ^ 1
    nv = (nx + 1) * (ny + 1)
    v_edge = np.zeros(nv, np.int64)
    src = E_dest[E_opp]
    for i in range(nhe): v_edge[src[i]] = i
    for i in range(nhe):
        if E_face[i] < 0: v_edge[src[i]] = i
    f_edge = remap[np.array(face_first)]
    return dict(faces=faces, E_dest=E_dest, E_face=E_face, E_next=E_next, E_opp=E_opp, v_edge=v_edge, f_edge=f_edge, nhe=nhe, nv=nv)


def set_arr(m, el, name, val):
    a = dmx.geta(m.E[el], name)
    a[2] = val


def apply_dense(m, pl, VL, rmap, nb, PL):
    """re-grid a tile at 16 u: the old surface (00-11 split) reproduced exactly, plus the layer; paint carried over and modified"""
    t = pl.t; md = t['md']; r0 = t['res']
    Zt = tile_grid(t)
    vst = streams(m, m.g(md, b'vertexData')); fst = streams(m, m.g(md, b'faceVertexData'))
    vdi = m.g(md, b'vertexDataIndices'); evi = m.g(md, b'edgeVertexIndices'); evd = m.g(md, b'edgeVertexDataIndices'); efi = m.g(md, b'edgeFaceIndices')
    # old per-vertex paint, texcoord mapping
    nv0 = len(t['P'])
    B0 = np.zeros((nv0, 4)); T0 = np.zeros((nv0, 4)); cnt = np.zeros(nv0)
    bp = sdata(m, fst['VertexPaintBlendParams:0'])[2]; tc = sdata(m, fst['VertexPaintTintColor:0'])[2]; tx_ = sdata(m, fst['texcoord:0'])[2]
    UVx, UVy, UVu, UVv = [], [], [], []
    for h in range(len(evi)):
        if efi[h] < 0: continue
        v = vdi[evi[h]]; B0[v] += bp[evd[h]]; T0[v] += tc[evd[h]]; cnt[v] += 1
        UVx.append(t['P'][v, 0]); UVy.append(t['P'][v, 1]); UVu.append(tx_[evd[h]][0]); UVv.append(tx_[evd[h]][1])
    B0 /= np.maximum(cnt, 1)[:, None]; T0 /= np.maximum(cnt, 1)[:, None]
    A = np.stack([UVx, UVy, np.ones(len(UVx))], 1)
    cu = np.linalg.lstsq(A, np.array(UVu), rcond=None)[0]; cv = np.linalg.lstsq(A, np.array(UVv), rcond=None)[0]
    n0 = TILE // r0
    BG = np.zeros((n0 + 1, n0 + 1, 4)); TG = np.zeros((n0 + 1, n0 + 1, 4))
    BG[t['gi'], t['gj']] = B0; TG[t['gi'], t['gj']] = T0
    # new grid
    n = TILE // 16
    lx = np.arange(n + 1) * 16.0
    LX, LYg = np.meshgrid(lx, lx, indexing='ij')
    Zold = tri_interp(Zt, r0, LX, LYg)
    gx = (t['tx'] + LX).ravel(); gy = (t['ty'] + LYg).ravel()
    d = vertex_delta(pl, gx, gy, VL, rmap, nb)
    Z = Zold.ravel() + d
    def bil(G, x, y):
        u = np.clip(x / r0, 0, n0 - 1e-9); v = np.clip(y / r0, 0, n0 - 1e-9)
        i = u.astype(int); j = v.astype(int); fu = (u - i)[..., None]; fv = (v - j)[..., None]
        return (G[i, j] * (1 - fu) + G[i + 1, j] * fu) * (1 - fv) + (G[i, j + 1] * (1 - fu) + G[i + 1, j + 1] * fu) * fv
    Bv = bil(BG, LX.ravel(), LYg.ravel()); Tv = bil(TG, LX.ravel(), LYg.ravel())
    ii = np.round((gx - X0) / CELL).astype(int); jj = np.round((gy - Y0) / CELL).astype(int)
    mud, wet, dirt = (PL[k][16][ii, jj] for k in ('mud', 'wet', 'dirt'))
    Bv, Tv = paint_mod(t['mat'], Bv, Tv, mud, wet, dirt)
    G = grid_halfedges(n, n)
    P = np.stack([gx, gy, Z], 1)
    nhe, nf, nvx = G['nhe'], len(G['faces']), G['nv']
    tex = np.zeros((nhe, 2)); nrm = np.zeros((nhe, 3)); tan = np.zeros((nhe, 4)); tco = np.zeros((nhe, 4)); bpa = np.zeros((nhe, 4))
    tan0 = next((sdata(m, fst['tangent:0'])[2][evd[h]] for h in range(len(evi)) if efi[h] >= 0), [1.0, 0.0, 0.0, -1.0])
    fn = np.array([newell(P[f]) for f in G['faces']])
    P_old = np.stack([gx, gy, Zold.ravel()], 1)
    fo = np.array([newell(P_old[f]) for f in G['faces']])
    steep = int(np.sum((fn[:, 2] < COS_STEEP) & (fo[:, 2] >= COS_STEEP)))
    fh = G['E_face'] >= 0
    dv = G['E_dest'][fh]
    tex[fh, 0] = cu[0] * P[dv, 0] + cu[1] * P[dv, 1] + cu[2]; tex[fh, 1] = cv[0] * P[dv, 0] + cv[1] * P[dv, 1] + cv[2]
    nrm[fh] = fn[G['E_face'][fh]]; tan[fh] = tan0; tco[fh] = Tv[dv]; bpa[fh] = Bv[dv]
    # write into the existing elements (same element ids: the node keeps its id, nodeID and everything else)
    L = lambda a: [list(map(float, v)) for v in a]
    set_arr(m, md, b'vertexEdgeIndices', G['v_edge'].tolist()); set_arr(m, md, b'vertexDataIndices', list(range(nvx)))
    set_arr(m, md, b'edgeVertexIndices', G['E_dest'].tolist()); set_arr(m, md, b'edgeOppositeIndices', G['E_opp'].tolist())
    set_arr(m, md, b'edgeNextIndices', G['E_next'].tolist()); set_arr(m, md, b'edgeFaceIndices', G['E_face'].tolist())
    set_arr(m, md, b'edgeDataIndices', (np.arange(nhe) >> 1).tolist()); set_arr(m, md, b'edgeVertexDataIndices', list(range(nhe)))
    set_arr(m, md, b'faceEdgeIndices', G['f_edge'].tolist()); set_arr(m, md, b'faceDataIndices', list(range(nf)))
    def fill(arr, n_, values):
        dmx.set_(m.E[arr], b'size', dmx.T_INT, int(n_))
        for nm, s in streams(m, arr).items():
            dd = sdata(m, s)
            if nm in values: dd[2] = values[nm]
            else:                                            # a stream we do not compute: its first value everywhere (one material)
                first = dd[2][0] if dd[2] else 0
                dd[2] = [list(first) if isinstance(first, list) else first for _ in range(n_)]
    fill(m.g(md, b'vertexData'), nvx, {'position:0': L(P)})
    fill(m.g(md, b'faceVertexData'), nhe, {'texcoord:0': L(tex), 'texcoord:1': [[0.0, 0.0]] * nhe, 'normal:0': L(nrm), 'tangent:0': L(tan),
                                         'VertexPaintTintColor:0': L(tco), 'VertexPaintBlendParams:0': L(bpa)})
    fill(m.g(md, b'edgeData'), nhe // 2, {'flags:0': [0] * (nhe // 2)})
    fill(m.g(md, b'faceData'), nf, {'materialindex:0': [0] * nf, 'flags:0': [0] * nf, 'lightmapScaleBias:0': [0] * nf})
    sd = m.g(md, b'subdivisionData')
    if sd is not None and sd >= 0: set_arr(m, sd, b'subdivisionLevels', [0] * nhe)
    return int(np.count_nonzero(d)), float(np.abs(d).max()), steep, nf


# ================================================================ reading the result back
def surface_lattice(m, plans):
    """terrain height on the lattice from the (patched) map's tile meshes, under the 00-11 split"""
    H = np.full((NX, NY), np.nan)
    n = int(TILE / CELL)
    loc = np.arange(n + 1) * CELL
    LX, LYg = np.meshgrid(loc, loc, indexing='ij')
    for pl in plans:
        md = pl.t['md']
        P = np.array(sdata(m, streams(m, m.g(md, b'vertexData'))['position:0'])[2], float)
        r = pl.r
        gi = np.round((P[:, 0] - pl.t['tx']) / r).astype(int); gj = np.round((P[:, 1] - pl.t['ty']) / r).astype(int)
        Z = np.full((TILE // r + 1, TILE // r + 1), np.nan); Z[gi, gj] = P[:, 2]
        h = tri_interp(Z, r, LX, LYg)
        i0, j0 = li(pl.t['tx']), lj(pl.t['ty'])
        blk = H[i0:i0 + n + 1, j0:j0 + n + 1]; ok = np.isfinite(h); blk[ok] = h[ok]
    return H


def surface_at(grids, x, y):
    """exact height of the terrain sheets at world points (00-11 split): grids {(tx, ty): (r, Z)}"""
    out = np.full(len(x), np.nan)
    tx = np.floor(x / TILE) * TILE; ty = np.floor(y / TILE) * TILE
    for key in set(zip(tx.tolist(), ty.tolist())):
        g = grids.get((int(key[0]), int(key[1])))
        if g is None: continue
        s_ = (tx == key[0]) & (ty == key[1])
        out[s_] = tri_interp(g[1], g[0], x[s_] - key[0], y[s_] - key[1])
    return out


def grids_of(m, plans):
    G = {}
    for pl in plans:
        md = pl.t['md']
        P = np.array(sdata(m, streams(m, m.g(md, b'vertexData'))['position:0'])[2], float)
        r = pl.r
        gi = np.round((P[:, 0] - pl.t['tx']) / r).astype(int); gj = np.round((P[:, 1] - pl.t['ty']) / r).astype(int)
        Z = np.full((TILE // r + 1, TILE // r + 1), np.nan); Z[gi, gj] = P[:, 2]
        G[(int(pl.t['tx']), int(pl.t['ty']))] = (r, Z)
    return G


def adjust_lmres(m, Hnew, Hold, log):
    """the battlefield toolslightmapres shell (the generator put its floor 8 u under the lowest ground and its roof 128 u over the highest,
    per 64-u cell): each floor vertex goes down by the deepest cut within 64 u of it, each roof vertex up by the highest fill"""
    best = None
    for n in m.children(m.world):
        if m.type(n) != b'CMapMesh': continue
        md = m.g(n, b'meshData')
        if md is None or md < 0: continue
        mats = [x.decode().lower() for x in m.g(md, b'materials') or []]
        if mats != [LMRES]: continue
        P = np.array(sdata(m, streams(m, m.g(md, b'vertexData'))['position:0'])[2], float)
        if best is None or len(P) > best[1]: best = (n, len(P))
    if best is None: return None
    n = best[0]; md = m.g(n, b'meshData')
    pos = sdata(m, streams(m, m.g(md, b'vertexData'))['position:0'])
    P = np.array(pos[2], float)
    k = int(64 / CELL) * 2 + 1
    dH = np.where(np.isfinite(Hnew) & np.isfinite(Hold), Hnew - Hold, 0.0)
    lo = ndimage.minimum_filter(dH, size=k); hi = ndimage.maximum_filter(dH, size=k)
    ii = np.clip(np.round((P[:, 0] - X0) / CELL).astype(int), 0, NX - 1); jj = np.clip(np.round((P[:, 1] - Y0) / CELL).astype(int), 0, NY - 1)
    key = {}
    for v, (x, y, z) in enumerate(P): key.setdefault((round(x, 2), round(y, 2)), []).append(v)
    P2 = P.copy(); nb = nt = 0
    for (x, y), vs in key.items():
        zs = P[vs, 2]; zb, zt = zs.min(), zs.max()
        for v in vs:
            if len(vs) > 1 and P[v, 2] == zb:
                if lo[ii[v], jj[v]] < -1e-3: P2[v, 2] = P[v, 2] + lo[ii[v], jj[v]]; nb += 1
            elif len(vs) > 1 and P[v, 2] == zt:
                if hi[ii[v], jj[v]] > 1e-3: P2[v, 2] = P[v, 2] + hi[ii[v], jj[v]]; nt += 1
    if nb or nt: pos[2] = [[float(a), float(b), float(c)] for a, b, c in P2]
    log('lightmap shell (mesh %d): %d floor vertices lowered (max %.1f u), %d roof vertices raised' % (n, nb, float((P - P2)[:, 2].max()) if nb else 0.0, nt))
    return dict(node=n, nid=m.g(n, b'nodeID'), lowered=nb, raised=nt) if (nb or nt) else dict(node=n, nid=m.g(n, b'nodeID'), lowered=0, raised=0)


# ================================================================ effects (create/fxkit.py) and the light rig
def add_fx_node(m, el, group):
    """an fxkit / vmaplib entity Element -> a vmapedit entity in this map (class, origin, angles, keys, outputs); returns its id"""
    ep = el.get('entity_properties')
    kv = [(a[0], a[2]) for a in ep.attrs]
    cls = dict(kv)['classname']
    e = m.new_entity(cls, tuple(el.get('origin')), {k: v for k, v in kv if k != 'classname'}, angles=tuple(el.get('angles') or (0, 0, 0)))
    dmx.set_(m.E[e], b'customVisGroup', dmx.T_STR, group.encode())
    for c in (el.get('connectionsData') or []):
        m.add_conn(e, c.get('outputName'), c.get('targetName'), c.get('inputName'), c.get('overrideParam') or '', c.get('delay') or 0.0, c.get('timesToFire'))
    return e


def plan_fx(m, rec, Hnew, log):
    """smoke over a few fresh no man's land shell holes, away from the smoke and fires already there and from the user's explosions"""
    old = [m.origin(e) for e in m.entities() if m.cls(e) in ('info_particle_system', 'env_explosion') and m.origin(e)[2] > -1000]
    cr = sorted([c for c in rec['craters'] if c['zone'] == 'nml' and abs(c['x']) < 1250], key=lambda c: -c['r'])
    pick = []
    for c in cr:
        if any(math.hypot(c['x'] - o[0], c['y'] - o[1]) < 520 for o in old): continue
        if any(math.hypot(c['x'] - p['x'], c['y'] - p['y']) < 1100 for p in pick): continue
        pick.append(c)
        if len(pick) >= 6: break
    out = []
    for k, c in enumerate(pick):
        z = float(Hnew[li(c['x']), lj(c['y'])]) + 6.0
        out.append(dict(name='tw_crater_smoke_%d' % (k + 1), o=(c['x'], c['y'], round(z, 1)), r=c['r']))
    log('crater smoke: %d (%s)' % (len(out), ', '.join('(%d, %d)' % (p['o'][0], p['o'][1]) for p in out)))
    return out


LIGHT_KEYS = {'light_environment': ('color', 'brightness', 'skycolor', 'skyintensity', 'castshadows', 'directlight', 'indirectlight', 'fog', 'fogstrength',
                                    'ambient_occlusion', 'bouncescale', 'angulardiameter'),
              'env_sky': ('skyname', 'tint_color', 'brightnessscale'),
              'env_cubemap_fog': ('cubemapfogstartdistance', 'cubemapfogenddistance', 'cubemapfogmaxopacity', 'cubemapheightfog', 'cubemapfogheightstart', 'cubemapfogheightend'),
              'post_processing_volume': ('postprocessing', 'minexposure', 'maxexposure', 'enableexposure')}


def light_rig(m):
    """the light settings as they are (recorded before / after; the patch does not change them)"""
    out = {}
    for e in m.entities():
        c = m.cls(e)
        if c in LIGHT_KEYS:
            out[c] = {k: m.P(e, k, '') for k in LIGHT_KEYS[c]}
            if c == 'light_environment': out[c]['angles'] = [round(v, 2) for v in m.g(e, b'angles')]
    out['probe_volumes'] = sum(1 for e in m.entities() if m.cls(e) == 'env_combined_light_probe_volume')
    out['lightmapres_meshes'] = sum(1 for n, _ in m.walk() if m.type(n) == b'CMapMesh' and [x.decode().lower() for x in (m.g(m.g(n, b'meshData'), b'materials') or [])] == [LMRES])
    return out


# ================================================================ main
def main(argv=None):
    ap = argparse.ArgumentParser(description='terrain patch (step 7)')
    ap.add_argument('--in', dest='inp', default=os.path.join(OUT, 'mg_trenchwarfare_models.vmap'))
    ap.add_argument('--out', default=os.path.join(OUT, 'mg_trenchwarfare_terrain.vmap'))
    ap.add_argument('--stage', default=os.path.join(OUT, 'addon'))
    ap.add_argument('--seed', type=int, default=1918)
    ap.add_argument('--no-fx', action='store_true')
    ap.add_argument('--no-dense', action='store_true', help='keep every tile on its own grid (heights and paint only)')
    ap.add_argument('--quick', action='store_true', help='skip the erosion passes (for trying things out)')
    ap.add_argument('--targets', default=os.path.join(STEP, 'patch_terrain.targets.json'))
    a = ap.parse_args(argv)
    outp = os.path.abspath(a.out)
    if not safepath.inside(OUT, outp) or os.path.normcase(outp) == os.path.normcase(os.path.abspath(a.inp)):
        sys.exit('patch_terrain: --out must be under %s and not the input' % OUT)
    os.makedirs(STEP, exist_ok=True)
    t0 = time.time()
    lines = []
    def log(s): print(s); lines.append(s)
    raw = open(a.inp, 'rb').read()
    m = V.Map(a.inp, data=raw); m.path = a.inp
    T = dict(input=os.path.abspath(a.inp), input_bytes=len(raw), input_crc32='%08x' % (zlib.crc32(raw) & 0xffffffff), modify={}, remove={}, add=[],
             prefix=[], root=False)
    rig0 = light_rig(m)
    # ---- find and verify the targets: nothing is changed unless every tile reads as a generated tile
    tiles, skipped = find_tiles(m)
    if skipped: sys.exit('patch_terrain: TARGET MISMATCH, nothing written: %s' % skipped[:10])
    if len(tiles) != 672: sys.exit('patch_terrain: expected the 672 generated terrain tiles, found %d (Hammer edits?): nothing written' % len(tiles))
    faces0 = sum(t['nfaces'] for t in tiles); verts0 = sum(len(t['P']) for t in tiles)
    log('terrain tiles: %d (%s), %d vertices, %d faces' % (len(tiles), ', '.join('%d at %d u' % (sum(t['res'] == r for t in tiles), r) for r in (32, 64, 128)), verts0, faces0))
    sc, TP = scene_props(a.inp, a.stage)
    hard, layers = protect_mask(m, sc, tiles, log)
    H, miss = base_lattice(tiles)
    plans = make_plans(tiles, hard, {} if a.no_dense else dense_candidates(tiles, sc, a.seed, hard), log=log)
    R, nfz = frozen_region(plans, hard)
    w = free_weight(R)
    Rdist = ndimage.distance_transform_edt(~R) * CELL
    rmap = res_map(plans)
    seamd = seam_distance(plans)
    log('frozen faces: %d; frozen %.1f %% of the terrain, fully free %.1f %%' % (nfz, 100 * R.mean(), 100 * (w > 0.999).mean()))
    D, paint, rec = build_detail(H, w, Rdist, rmap, seamd, sc, a.seed, log, hard, quick=a.quick)
    VL = vertex_layers(D, w)
    PL = {k: {r: np.clip(v, 0, 1) for r, v in vertex_layers(paint[k], w).items()} for k in paint}
    nb = neighbours(plans)
    # ---- apply
    nchg = ndense = steep = 0; dmax = 0.0; faces1 = 0
    for pl in plans:
        if pl.dense:
            c, dm, st, nf = apply_dense(m, pl, VL, rmap, nb, PL); ndense += 1; faces1 += nf
            T['modify'][str(pl.t['nid'])] = dict(i=pl.t['i'], fields=['mesh'], why='terrain tile (%d, %d) re-gridded 16 u (was %d) + detail layer' % (pl.t['tx'], pl.t['ty'], pl.t['res']))
        else:
            c, dm, st = apply_zonly(m, pl, VL, rmap, nb, PL); faces1 += pl.t['nfaces']
            if c: T['modify'][str(pl.t['nid'])] = dict(i=pl.t['i'], fields=['mesh'], why='terrain tile (%d, %d) %d u: heights, paint, normals' % (pl.t['tx'], pl.t['ty'], pl.t['res']))
        nchg += c; dmax = max(dmax, dm); steep += st
    verts1 = sum(((TILE // 16 + 1) ** 2 if pl.dense else len(pl.t['P'])) for pl in plans)
    log('applied: %d tiles changed (%d re-gridded), %d vertices moved, max |delta| %.1f u, faces newly steeper than %d deg: %d'
        % (len(T['modify']), ndense, nchg, dmax, STEEP, steep))
    log('budget: vertices %d -> %d, faces %d -> %d (triangles %d -> %d)' % (verts0, verts1, faces0, faces1, 2 * faces0, 2 * faces1))
    Hnew = surface_lattice(m, plans)
    # ---- the protected ground must read back exactly
    hard_pts = hard & np.isfinite(Hnew) & ~miss
    dprot = float(np.abs(Hnew - H)[hard_pts].max()) if hard_pts.any() else 0.0
    dfrozen = float(np.abs(Hnew - H)[R & ~miss].max())
    log('read back: max |change| on the protect mask %.6f u (%d lattice points), on the whole frozen region %.6f u' % (dprot, int(hard_pts.sum()), dfrozen))
    # and off the lattice: random points on the protect mask, both surfaces sampled exactly (the old tiles from the input's vertices)
    G0 = {(int(t['tx']), int(t['ty'])): (t['res'], tile_grid(t)) for t in tiles}
    G1 = grids_of(m, plans)
    rs = np.random.RandomState(5)
    hi_, hj_ = np.nonzero(hard & ~miss)
    k = rs.randint(0, len(hi_), 400000)
    px = X0 + (hi_[k] + rs.uniform(-0.5, 0.5, len(k))) * CELL; py = Y0 + (hj_[k] + rs.uniform(-0.5, 0.5, len(k))) * CELL
    z0, z1 = surface_at(G0, px, py), surface_at(G1, px, py)
    okz = np.isfinite(z0) & np.isfinite(z1)
    doff = float(np.abs(z1 - z0)[okz].max())
    log('read back off the lattice: %d random points on the protect mask, max |change| %.6f u' % (int(okz.sum()), doff))
    dprot = max(dprot, doff)
    if dprot > 1e-3 or dfrozen > 1e-3: sys.exit('patch_terrain: the protected ground moved (%.4f / %.4f u): nothing written' % (dprot, dfrozen))
    lm = adjust_lmres(m, Hnew, H, log)
    if lm and (lm['lowered'] or lm['raised']):
        T['modify'][str(lm['nid'])] = dict(i=lm['node'], fields=['mesh'], why='battlefield lightmap-res shell follows the new ground')
    # ---- fx
    fx = []
    if not a.no_fx:
        import fxkit
        for p in plan_fx(m, rec, Hnew, log):
            r = fxkit.effect(SMOKE_FX, p['o'], p['name'], start=True, group='tw_gen')
            add_fx_node(m, r['nodes'][0], 'tw_gen'); fx.append(dict(kind='crater smoke', name=p['name'], o=p['o'], effect=SMOKE_FX))
            T['add'].append(dict(type='CMapEntity', **{'class': 'info_particle_system'}, name=p['name'], why='smoke drifting from a fresh shell hole'))
        # rain over both trench systems, off at the start: tw_rain FireUser1 starts, FireUser2 stops (one relay drives both sides)
        rt = fxkit.weather_tiles(((-2700.0, -3200.0, 0.0), (-1300.0, 3200.0, 700.0)), kind=RAIN_FX, name='tw_rain', tile=1024.0, start=False, group='tw_gen')
        rc = fxkit.weather_tiles(((1300.0, -3200.0, 0.0), (2700.0, 3200.0, 700.0)), kind=RAIN_FX, name='tw_rainct', tile=1024.0, start=False, group='tw_gen')
        relay = rt['nodes'][0]
        import primitives as Pm
        for node in rc['nodes'][1:]:
            nm = node.get('entity_properties').get('targetname')
            Pm.connect(relay, 'OnUser1', nm, 'Start', check_output=False); Pm.connect(relay, 'OnUser2', nm, 'Stop', check_output=False)
        for node in rt['nodes'] + rc['nodes'][1:]:
            add_fx_node(m, node, 'tw_gen')
            ep = node.get('entity_properties')
            T['add'].append(dict(type='CMapEntity', **{'class': ep.get('classname')}, name=ep.get('targetname'), why='rain tiles over the trenches (start off)'))
        fx.append(dict(kind='rain tiles (start off)', relay='tw_rain', tiles=rt['tiles'] + rc['tiles'], effect=RAIN_FX,
                       inputs='ent_fire tw_rain FireUser1 (start) / FireUser2 (stop)'))
        log('rain: %d tiles over the trenches, start off, relay tw_rain' % (rt['tiles'] + rc['tiles']))
        # asset references and the per-class counts in the prefix
        ents = m.entities(); counts = {}
        for e in ents: counts[m.cls(e)] = counts.get(m.cls(e), 0) + 1
        for attrs in m.doc.prefix:
            pre = {x[0]: x for x in attrs}
            if b'map_asset_references' in pre:
                ar = pre[b'map_asset_references'][2]
                for x in (SMOKE_FX, RAIN_FX):
                    if x.encode() not in ar: ar.append(x.encode())
                if 'map_asset_references' not in T['prefix']: T['prefix'].append('map_asset_references')
            if b'map_subasset_reference_names' in pre:
                names = sorted(counts)
                pre[b'map_subasset_reference_types'][2] = [b'entity'] * len(names)
                pre[b'map_subasset_reference_names'][2] = [nm.encode() for nm in names]
                pre[b'map_subasset_reference_counts'][2] = [counts[nm] for nm in names]
                T['prefix'] += [k for k in ('map_subasset_reference_types', 'map_subasset_reference_names', 'map_subasset_reference_counts') if k not in T['prefix']]
    rig1 = light_rig(m)
    nbytes = m.save(outp)
    T['output'] = outp
    json.dump(T, open(a.targets, 'w'), indent=1)
    # ---- report, deploy list, the layer for the renders
    X_, Y_ = lat_xy()
    rep = dict(input=a.inp, output=outp, seed=a.seed, seconds=round(time.time() - t0, 1), tiles=len(tiles), regridded=ndense,
               budget=dict(vertices=[verts0, verts1], faces=[faces0, faces1], triangles=[2 * faces0, 2 * faces1]),
               protect={k: round(100 * float(v.mean()), 2) for k, v in layers.items()}, protect_total=round(100 * float(hard.mean()), 2),
               frozen_pct=round(100 * float(R.mean()), 2), free_pct=round(100 * float((w > 0.999).mean()), 2), feather=FEATHER,
               layer=dict(min=round(float(D.min()), 2), max=round(float(D.max()), 2), rms_free=round(float(np.sqrt((D[w > 0.5] ** 2).mean())), 2) if (w > 0.5).any() else 0),
               max_vertex_delta=round(dmax, 2), new_steep_faces=steep, steep_deg=STEEP, protected_max_change=dprot, frozen_max_change=dfrozen,
               lightmap_shell=lm, fx=fx, light_before=rig0, light_after=rig1, features={k: (len(v) if isinstance(v, list) else v) for k, v in rec.items()},
               log=lines)
    json.dump(dict(rep, features_detail=rec), open(os.path.join(STEP, 'patch_terrain.report.json'), 'w'), indent=1)
    np.savez_compressed(os.path.join(STEP, 'terrain_layers.npz'), H=H.astype(np.float32), Hnew=Hnew.astype(np.float32), D=D.astype(np.float32),
                        hard=hard, R=R, w=w.astype(np.float32), mud=paint['mud'].astype(np.float32), wet=paint['wet'].astype(np.float32),
                        dirt=paint['dirt'].astype(np.float32), dense=np.array([[pl.t['tx'], pl.t['ty']] for pl in plans if pl.dense]).reshape(-1, 2))
    open(os.path.join(STEP, 'deploy_files.txt'), 'w', newline='\n').write(
        '# remaster step 7 (terrain): files to copy into content\\csgo_addons\\mg_trenchwarfare\\ (addon-relative).\n'
        '# Back up the vmap first and close Hammer. The particles are stock CS2 files: nothing else to stage or compile.\n'
        '# If patch_nav runs after this step, deploy its output map instead of this one.\n'
        'maps/mg_trenchwarfare.vmap   <- %s\n' % os.path.relpath(outp, PROJ).replace('\\', '/'))
    log('patched map: %s (%d bytes); targets %s; %d changes, %d additions; %.1f s' % (outp, nbytes, a.targets, len(T['modify']), len(T['add']), time.time() - t0))


if __name__ == '__main__':
    main()
