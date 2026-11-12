"""mg_monsoon gameplay checks on the generated vmap (offline; "simulated" in the words of docs/reference/compatibility.md).

usage: check_play.py <map.vmap> [--json out.json] [--only 1,2,...] [--verbose] [--nav-plan]

The scene is rebuilt from the vmap itself, not from layout.py: terrain tiles, world meshes (terraces, stairs, ramps, berms, boulders,
karst, the tunnel), player clips, water sheets, and every solid prop's physics hulls (the *_hull*.smd files the .vmdl compiles;
stock trees = a trunk cylinder, other stock models = their measured bounds). Everything is rasterised on a 16-u grid into
  surfaces  up-facing faces: where feet can be (several layers per cell: ground, deck, tunnel floor, roof)
  blockers  walls and undersides, widened by 12 u (a player is 32 wide): z intervals a body cannot overlap
and a directed walk graph is built over it (step up 18 u per cell, drops allowed, body 18..68 u above the feet must be free).

 1 walkability   both base spawn rings in one strongly connected component; every flag, kit station, rack, board seat, mount seat,
                 pad, tunnel portal, flag spawn reachable on foot and back; stuck pockets (places a player can get into from the
                 walkable world and never out of, > 200 u2) with and without a jump (54 u)
1b routes        walking distance (on the walk graph) from each base's spawn ring to each flag; mirror balance A-D, C-E, B-B
 2 sightlines    no line of sight between enemy base spawns; flag-to-flag exposure table; per flag the share of the ground within
                 2500 u that sees it (hard = solid only, soft = with tree crowns and tall grass) and the worst overlook
 3 cover         head-height (>= 62 u) cover pieces within 600 u of each flag, minimum 14 (crouch-height listed)
 4 helicopters   pad cylinder (rotor radius + 60, up to 600 u) free of anything taller than 24 u; approach lanes (30-degree glide to
                 1800 u, at least 3 of 8); karst landing crowns flat (< 10 deg), wide enough and free of nest props
 5 spawn safety  no base / flag spawn in line of sight of an enemy (or neutral) mounted gun or gun pit within 900 u
 6 clipping      props buried (> 35 % of their bounds under the ground / inside world geometry), floating (> 6 u over any support),
                 tree crowns through buildings, non-solid dressing inside solid props, props under water that are not water props
 7 water         sheet edges above the ground (visible edge), sheets overlapping at the same height (z-fight), deep spots
 8 terrain       road / trail slope < 20 deg and cross fall, gullies across roads, bridge ramps meet the banks within 4 u, no ground
                 through walk-in floors, terrain holes covered underneath
 9 nav           seeds on walkable ground; NONAV boxes over no road, flag, spawn or station (walk-on surfaces outside the nav plan,
                 the waterfall shelf, excepted); nav estimate: the walk graph flooded from the seeds and base spawns with the nodes in
                 NONAV boxes taken out (16-u cells, m2, and nav areas projected linearly from a compile: NAV_CAL); every flag,
                 spawn, flag spawn, kit, rack, board seat, mount seat and tunnel portal on that nav; bots route from both spawn rings to
                 every flag and back on it (fails otherwise); warns over NAV_TARGET areas or a nav route NAV_DETOUR x the walking one
    --nav-plan   check 9 with the NONAV boxes mv_entities.nonav_boxes() would write now instead of the vmap's (before a regenerate)
Exit code 1 when a check fails. Numbers go to out/check_play.json (before / after tables in docs/REVIEW_WORLD_*.md).
"""
import os, sys, json, math, glob, re, time, pickle
from collections import Counter, defaultdict
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..', '..', 'tools')))
import layout as L
import mv_stock as S
import mv_models as M
import placer

OUT = os.path.normpath(os.path.join(HERE, '..', 'out'))
ADDON = os.path.join(OUT, 'addon')
CELL = 16.0
PADW = 12.0                    # blockers are widened by this (player half width 16, a little slack for doorways)
STEP, JUMP, BODY0, BODY1 = 18.0, 54.0, 18.5, 68.0
LANE_GLIDE = 30.0               # approach lanes: nothing within 40 u of a line rising this steeply from 60 u over the pad
MOUNT_CONE = 30.0               # CONFIG.MOUNT.CONE in src/00_config.js: a mounted gun traverses this far either side of its rest yaw
MARG = 320.0
X0, Y0 = -(L.MAP_X + MARG), -(L.MAP_Y + MARG)
NX, NY = int(2 * (L.MAP_X + MARG) / CELL), int(2 * (L.MAP_Y + MARG) / CELL)
NC = NX * NY
K_TERRAIN, K_WORLD, K_CLIP, K_HULL, K_WATER, K_TRUNK = 0, 1, 2, 3, 4, 5
WATER_OK = ('reeds', 'rice_clump', 'sampan', 'pbr', 'mangrove', 'nypa', 'fish_trap', 'water_wall', 'dead_tree', 'bridge_pier', 'truss_span')
FOLIAGE = ('foliage', 'palm', 'weeds', 'grass', 'rice_clump', 'reeds', 'bamboo', 'rubber_tree', 'dead_tree', 'vine', 'root', 'ext/rs_', 'banyan', 'fern',
           'taro', 'yucca', 'tropical', 'ground_', 'hosta', 'generic_leaf')
TREES = ('banyan', 'palm_tree_0', 'palm_tree_hr', 'palm_tree_small', 'rubber_tree', 'dead_tree', 'rs_jungle_tree', 'rs_jungle_palm', 'rs_coconut_palm', 'generic_tree', 'rs_mangrove',
         'rs_bamboo_bundle', 'bamboo_clump', 'rs_nypa')         # pass 3: the nypa palm is a tree here as in the placer (crown from the trunk)
BUILDINGS = ('hooch', 'camp_hut', 'school', 'gp_tent', 'fdc_bunker', 'bunker_', 'guard_tower', 'checkpoint', 'french_bunker', 'khmer_tower', 'khmer_gate',
             'c123_fuselage', 'conex', 'market_stall', 'latrine', 'shrine')
# walk-in props: local floor rectangles (x0, y0, x1, y1, z) the ground must stay under
FLOORS = {'camp_hut': (-126, -82, 136, 82, 10), 'school': (-144, -94, 144, 94, 0), 'khmer_tower': (-70, -70, 70, 70, 20), 'french_bunker': (-82, -67, 82, 67, 1),
          'c123_fuselage': (-66, -340, 66, 340, 12), 'checkpoint': (-35, 87, 35, 149, 3), 'fdc_bunker': (44, -50, 176, 50, 0)}


def short(m):
    return m.split('/')[-1][:-5] if m.endswith('.vmdl') else m


# ================================================================ geometry sources
_SMD = {}


def smd_tris(path):
    """triangles of an SMD in Hammer model space: (N, 3, 3) positions and (N, 3) mean vertex normals"""
    if path in _SMD: return _SMD[path]
    V = []; Nn = []
    for l in open(path):
        q = l.split()
        if len(q) >= 9 and q[0].lstrip('-').isdigit():
            try:
                V.append((-float(q[2]), float(q[1]), float(q[3]))); Nn.append((-float(q[5]), float(q[4]), float(q[6])))
            except ValueError: pass
    n = len(V) // 3
    T = np.array(V[:n * 3], float).reshape(n, 3, 3); N = np.array(Nn[:n * 3], float).reshape(n, 3, 3).mean(1)
    fn = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    flip = (fn * N).sum(1) < 0                     # make the winding agree with the stored normals (outward)
    T[flip] = T[flip][:, ::-1]
    _SMD[path] = T
    return T


def box_tris(lo, hi):
    x0, y0, z0 = lo; x1, y1, z1 = hi
    c = np.array([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], float)
    q = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return np.array([[c[a], c[b], c[d]] for (a, b, d_, e) in q for (a, b, d) in ((a, b, d_), (a, d_, e))])


_HULL = {}


def model_hull(model, B):
    """-> ('tris', (N,3,3) model space) | ('trunk', radius, height) | None (no collision)"""
    if model in _HULL: return _HULL[model]
    name = short(model); r = None
    if model.startswith('models/mv/ext/'):
        base = name[:-4] if name.endswith('_dyn') else name
        d = os.path.dirname(os.path.join(ADDON, model.replace('/', os.sep)))
        fs = glob.glob(os.path.join(d, base + '_hull*.smd')) or glob.glob(os.path.join(d, '*_hull*.smd'))
        if model in M.TRUNK: r = ('trunk', M.TRUNK[model], B(model)[1][2])
        elif fs and not any(k in model for k in ('ext/rs_',)): r = ('tris', np.concatenate([smd_tris(f) for f in fs]))
    elif model.startswith('models/mv/'):
        fs = glob.glob(os.path.join(ADDON, 'models', 'mv', name, name + '_hull*.smd'))
        if fs: r = ('tris', np.concatenate([smd_tris(f) for f in fs]))
    elif model in S.TRUNK: r = ('trunk', S.TRUNK[model], B(model)[1][2])
    elif model == S.APACHE['model']: r = ('tris', box_tris((-250, -50, 0), (230, 50, 150)))
    elif any(k in model for k in ('aztec_wall', 'rock')):
        lo, hi = B(model); cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
        r = ('tris', box_tris((cx + (lo[0] - cx) * 0.8, cy + (lo[1] - cy) * 0.8, lo[2]), (cx + (hi[0] - cx) * 0.8, cy + (hi[1] - cy) * 0.8, lo[2] + (hi[2] - lo[2]) * 0.85)))
    _HULL[model] = r
    return r


def rot_matrix(ang):
    p, y, r = (math.radians(a) for a in ang)
    cp, sp, cy, sy, cr, sr = math.cos(p), math.sin(p), math.cos(y), math.sin(y), math.cos(r), math.sin(r)
    return np.array([[cp * cy, sp * sr * cy - cr * sy, sp * cr * cy + sr * sy], [cp * sy, sp * sr * sy + cr * cy, sp * cr * sy - sr * cy], [-sp, cp * sr, cp * cr]])


def load_scene(path, verbose=False):
    """entities + triangle soup of the vmap, cached in out/cache by the vmap's size and time"""
    st = os.stat(path); key = '%d_%d' % (st.st_size, int(st.st_mtime))
    cp = os.path.join(OUT, 'cache', 'play_scene_%s.pkl' % key)
    if os.path.exists(cp):
        return pickle.load(open(cp, 'rb'))
    import vmapedit as V
    t0 = time.time()
    m = V.Map(path)
    table, built = S.bounds_table(os.path.join(OUT, 'props.json'))
    B = placer.Bounds(props_json=os.path.join(OUT, 'props.json'), out=ADDON, prefix='mv', table=table)
    ents = []
    for e in m.entities():
        o = m.origin(e)
        ents.append(dict(cls=m.cls(e), name=m.name(e), model=m.P(e, 'model', '') or '', o=tuple(float(v) for v in o), a=tuple(float(v) for v in m.g(e, b'angles', [0, 0, 0])),
                         s=tuple(float(v) for v in (m.g(e, b'scales', None) or (1, 1, 1))), solid=str(m.P(e, 'solid', '') or ''), msg=m.P(e, 'message', '') or '',
                         nav=m.P(e, 'navProperty_NavGen', '') or ''))
    # ---- world meshes
    tris = []; kinds = []; srcs = []; meshes = []; ladders = []; navboxes = []
    par = m.parent_of()
    for n, _ in m.walk():
        if m.type(n) != b'CMapMesh': continue
        md = m.g(n, b'meshData')
        if md is None or md < 0: continue
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
        P = np.array(pos, float) * np.array(sc, float)
        if any(a): P = P @ rot_matrix(a).T
        P = P + np.array(o, float)
        if P[:, 2].max() < L.LOBBY_Z + 1500: continue                       # the lobby
        mat0 = mats[0] if mats else ''
        if 'toolsnavattribute' in mat0:
            p_ = par.get(n); prop = m.P(p_, 'navProperty_NavGen', '') if p_ is not None else ''
            navboxes.append((prop, m.name(p_) if p_ is not None else '', P.min(0).tolist() + P.max(0).tolist())); continue
        if 'toolsinvisibleladder' in mat0: ladders.append(P.min(0).tolist() + P.max(0).tolist()); continue
        if any(k in mat0 for k in ('toolstrigger', 'toolslightmapres', 'toolsskybox', 'toolsnodraw', 'briefing')): continue
        kind = K_CLIP if 'toolsplayerclip' in mat0 else K_WATER if 'water' in mat0 else K_TERRAIN if 'groundmud03-groundgrass' in mat0 else K_WORLD
        mid = len(meshes); meshes.append(dict(kind=kind, mat=mat0, lo=P.min(0).tolist(), hi=P.max(0).tolist(), mats=mats))
        for f, he in enumerate(fei):
            loop = []; h = he
            for _ in range(64):
                loop.append(vdi[evi[h]]); h = nxt[h]
                if h == he: break
            for k in range(1, len(loop) - 1):
                tris.append((P[loop[0]], P[loop[k]], P[loop[k + 1]])); kinds.append(kind); srcs.append(-1 - mid)
    if verbose: print('  meshes: %d (%d tris) %.1fs' % (len(meshes), len(tris), time.time() - t0))
    # ---- props: hull triangles, trunks, visual bounds
    props = []; trunks = []
    for i, r in enumerate(ents):
        if r['cls'] not in ('prop_static', 'prop_dynamic') or not r['model'].endswith('.vmdl') or r['o'][2] < L.LOBBY_Z + 1500: continue
        lo, hi = B(r['model']); R = rot_matrix(r['a']); sc = np.array(r['s'])
        c8 = np.array([(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])], float) * sc
        w8 = c8 @ R.T + np.array(r['o'])
        solid = not (r['cls'] == 'prop_static' and r['solid'] == '0') and not (r['cls'] == 'prop_dynamic' and r['solid'] in ('0', ''))
        p = dict(i=i, model=r['model'], name=r['name'], o=r['o'], yaw=r['a'][1], s=r['s'], lo=w8.min(0).tolist(), hi=w8.max(0).tolist(), solid=solid, cls=r['cls'],
                 mlo=list(lo), mhi=list(hi), poly=[(w8[k][0], w8[k][1]) for k in (0, 4, 6, 2)], hull=None)
        if solid:
            h = model_hull(r['model'], B)
            if h is not None and h[0] == 'tris':
                T = (h[1] * sc) @ R.T + np.array(r['o'])
                p['hull'] = 'tris'
                for t in T: tris.append((t[0], t[1], t[2])); kinds.append(K_HULL); srcs.append(len(props))
            elif h is not None:
                p['hull'] = 'trunk'; trunks.append((r['o'][0], r['o'][1], r['o'][2] - 10.0, r['o'][2] + h[2] * r['s'][2], h[1] * r['s'][0], len(props)))
        props.append(p)
    sc_ = dict(ents=ents, tris=np.array(tris, float), kinds=np.array(kinds, np.int8), srcs=np.array(srcs, np.int64), meshes=meshes, props=props, trunks=trunks,
               ladders=ladders, navboxes=navboxes, key=key)
    os.makedirs(os.path.dirname(cp), exist_ok=True)
    for old in glob.glob(os.path.join(OUT, 'cache', 'play_scene_*.pkl')):
        try: os.remove(old)
        except OSError: pass
    pickle.dump(sc_, open(cp, 'wb'), protocol=4)
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
    for k in (1, 2, 4, 8, 16, 32, 64, 128, 256, 1024):
        sel = np.nonzero(ok & (size <= k) & (size > k // 2 if k > 1 else True))[0]
        if not len(sel): continue
        per = max(1, chunk // (k * k))
        for c0 in range(0, len(sel), per):
            s = sel[c0:c0 + per]
            dx = np.arange(k)[None, :, None]; dy = np.arange(k)[None, None, :]
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
    """grid cell index, -1 outside the grid (12 Nov review: a point past the y edge wrapped into the next column, so trees beyond
    the map edge were measured against ground 1/2 a map away and read as floating 170 u)"""
    i = int((x - X0) // CELL); j = int((y - Y0) // CELL)
    return i * NY + j if 0 <= i < NX and 0 <= j < NY else -1


def cell_xy(c):
    return X0 + (c // NY + 0.5) * CELL, Y0 + (c % NY + 0.5) * CELL


class Grid:
    """surfaces, blockers and the walk graph"""
    def __init__(self, sc, verbose=False):
        t0 = time.time()
        T = sc['tris']; kinds = sc['kinds']; srcs = sc['srcs']
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
            rr = r + PADW; i0 = int((x - rr - X0) // CELL); i1 = int((x + rr - X0) // CELL); j0 = int((y - rr - Y0) // CELL); j1 = int((y + rr - Y0) // CELL)
            ii, jj = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1), indexing='ij')
            ok = (np.hypot(X0 + (ii + 0.5) * CELL - x, Y0 + (jj + 0.5) * CELL - y) <= rr) & (ii >= 0) & (ii < NX) & (jj >= 0) & (jj < NY)
            c = (ii[ok] * NY + jj[ok]).astype(np.int64)
            if not len(c): c = np.array([cell_of(x, y)], np.int64)
            b_cell.append(c); b_lo.append(np.full(len(c), z0)); b_hi.append(np.full(len(c), z1)); b_src.append(np.full(len(c), pi)); b_kind.append(np.full(len(c), K_TRUNK, np.int8))
        self.b_cell = np.concatenate(b_cell); self.b_lo = np.concatenate(b_lo); self.b_hi = np.concatenate(b_hi); self.b_src = np.concatenate(b_src); self.b_kind = np.concatenate(b_kind)
        # water level per cell
        wt = kinds == K_WATER
        ti, cl, zc, _, _ = raster(T[wt], 0.0)
        self.water = np.full(NC, -1e9); np.maximum.at(self.water, cl, zc)
        self.w_cell, self.w_z, self.w_src = cl, zc, srcs[np.nonzero(wt)[0][ti]]
        # terrain top per cell (the mesh, not layout.height)
        self.terr = np.full(NC, -1e9); tm = self.s_kind == K_TERRAIN
        np.maximum.at(self.terr, self.s_cell[tm], self.s_z[tm])
        # ---- nodes: cluster the surfaces of each cell by height (12 u), highest first
        o = np.lexsort((-self.s_z, self.s_cell)); c = self.s_cell[o]; z = self.s_z[o]; kd = self.s_kind[o]; sr = self.s_src[o]; nzz = self.s_nz[o]
        keep = np.ones(len(o), bool); layer = np.zeros(len(o), np.int64)
        last_c = -1; last_z = 0.0; lay = 0
        cl_ = c.tolist(); zl_ = z.tolist()
        for i in range(len(cl_)):
            if cl_[i] != last_c: last_c = cl_[i]; last_z = zl_[i]; lay = 0
            elif last_z - zl_[i] > 12.0: last_z = zl_[i]; lay += 1
            else: keep[i] = False
            layer[i] = lay
        self.K = K = int(min(layer[keep].max() + 1, 8))
        k_ = keep & (layer < K)
        self.Z = np.full((K, NC), -np.inf); self.Z[layer[k_], c[k_]] = z[k_]
        self.kind = np.full((K, NC), -1, np.int8); self.kind[layer[k_], c[k_]] = kd[k_]
        self.src = np.full((K, NC), 0, np.int64); self.src[layer[k_], c[k_]] = sr[k_]
        self.nz = np.zeros((K, NC)); self.nz[layer[k_], c[k_]] = nzz[k_]
        self.exists = np.isfinite(self.Z)
        # ---- blocked nodes
        bl = np.zeros((K, NC), bool); self.blk_src = np.full((K, NC), -10 ** 9, np.int64)
        for k in range(K):
            zk = self.Z[k, self.b_cell]
            hit = (self.b_lo < zk + BODY1) & (self.b_hi > zk + BODY0)
            bl[k, self.b_cell[hit]] = True; self.blk_src[k, self.b_cell[hit]] = self.b_src[hit]
            for j in range(k):
                d = self.Z[j] - self.Z[k]
                cz = self.exists[k] & (d > BODY0) & (d < BODY1)
                bl[k] |= cz; self.blk_src[k][cz & (self.blk_src[k] == -10 ** 9)] = self.src[j][cz & (self.blk_src[k] == -10 ** 9)]
        self.blocked = bl
        self.walk = self.graph(STEP); self.jump = None
        blj = np.zeros((K, NC), bool)                    # for the jump graph: only what a 54-u jump cannot clear blocks
        for k in range(K):
            zk = self.Z[k, self.b_cell]
            hit = (self.b_lo < zk + BODY1) & (self.b_hi > zk + JUMP + 0.5)
            blj[k, self.b_cell[hit]] = True
            for j in range(k):
                d = self.Z[j] - self.Z[k]
                blj[k] |= self.exists[k] & (d > JUMP + 0.5) & (d < BODY1)
        self.blocked_jump = blj
        if verbose: print('  grid: %d surface samples, %d blocker samples, %d layers, %d nodes, %.1fs' % (len(self.s_z), len(self.b_cell), K, int(self.exists.sum()), time.time() - t0))

    def target(self, k1, di, dj, up):
        """for every node of layer k1: (valid, target layer) of the move to the neighbour cell (di, dj)"""
        K = self.K
        Zs = self.Z[k1].reshape(NX, NY)
        tgt = np.full((NX, NY), -1, np.int64); zt = np.full((NX, NY), -np.inf)
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
        for k2 in range(K):                              # a surface in the way at body height (a step too high to take) stops the move: no falling through it
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
        # stepping off a ledge past the 12-u strip beside its own wall (a crate top, a tank deck, a roof): two cells out and down, when
        # nothing in the cell between reaches body height
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
                        m = v2 & (t2 == k2)
                        ii, jj = np.nonzero(m)
                        zt[ii, jj] = self.Z[k2].reshape(NX, NY)[ii + nn * di, jj + nn * dj]
                    v = v2 & ok & (Zs - zt > STEP)
                    ii, jj = np.nonzero(v)
                    rows.append(k1 * NC + base[ii, jj]); cols.append(t2[ii, jj] * NC + base[ii + nn * di, jj + nn * dj])
        # ladders: every node beside a ladder volume is joined to every other one
        for (x0, y0, z0, x1, y1, z1) in self.sc['ladders']:
            ids = []
            for i in range(int((x0 - 28 - X0) // CELL), int((x1 + 28 - X0) // CELL) + 1):
                for j in range(int((y0 - 28 - Y0) // CELL), int((y1 + 28 - Y0) // CELL) + 1):
                    for k in range(self.K):
                        zz = self.Z[k, i * NY + j]
                        if np.isfinite(zz) and z0 - 24 <= zz <= z1 + 24 and not self.blocked[k, i * NY + j]: ids.append(k * NC + i * NY + j)
            for a in ids:
                for b in ids:
                    if a != b: rows.append(np.array([a])); cols.append(np.array([b]))
        r = np.concatenate(rows); c = np.concatenate(cols)
        n = self.K * NC
        return sparse.csr_matrix((np.ones(len(r), np.int8), (r, c)), shape=(n, n))

    def nodes_near(self, x, y, z, rxy=40.0, rz=40.0):
        out = []
        n = int(math.ceil(rxy / CELL))
        ci = int((x - X0) // CELL); cj = int((y - Y0) // CELL)
        for i in range(ci - n, ci + n + 1):
            for j in range(cj - n, cj + n + 1):
                if not (0 <= i < NX and 0 <= j < NY): continue
                if math.hypot(X0 + (i + 0.5) * CELL - x, Y0 + (j + 0.5) * CELL - y) > rxy: continue
                for k in range(self.K):
                    zz = self.Z[k, i * NY + j]
                    if np.isfinite(zz) and abs(zz - z) <= rz and not self.blocked[k, i * NY + j]: out.append(k * NC + i * NY + j)
        return out

    def top(self, x, y):
        """highest surface at a point"""
        c = cell_of(x, y)
        return float(self.Z[0, c]) if 0 <= c < NC else -np.inf

    def ground(self, x, y, zref):
        """highest surface at or below zref + 12 at a point (the support under something)"""
        c = cell_of(x, y)
        if not 0 <= c < NC: return -np.inf
        zs = self.Z[:, c]; zs = zs[np.isfinite(zs) & (zs <= zref + 12.0)]
        return float(zs.max()) if len(zs) else -np.inf


def reach(g, start, reverse=False):
    from scipy.sparse import csgraph
    n = g.shape[0]
    gg = g.T.tocsr() if reverse else g
    seen = np.zeros(n, bool)
    from scipy import sparse
    # one virtual source joined to every start node
    aug = sparse.vstack([sparse.hstack([gg, sparse.csr_matrix((n, 1), dtype=np.int8)]),
                         sparse.csr_matrix((np.ones(len(start), np.int8), (np.zeros(len(start), np.int64), np.array(start))), shape=(1, n + 1))]).tocsr()
    order = csgraph.breadth_first_order(aug, n, directed=True, return_predecessors=False)
    seen[order[order < n]] = True
    return seen


# ================================================================ nav estimate (check 9)
# Calibration: two compiles of 12 Nov 2026. Stage 2 (vmap kept as out/review/p3/mg_monsoon_s2.vmap): 378,891 flooded cells,
# "Nav mesh (v36/1) loaded with 33661 nav areas" (0.089 areas per cell). Pass 3 (the NONAV plan of mv_entities.nonav_boxes):
# 115,469 cells, 15,033 areas (0.130 per cell): what bots keep (bases, village, props, roads) is cut into smaller areas than the
# open valley that was taken out, so the pass 3 point is used. Linear in the flooded cells, good to about 1.5x for a very
# different markup; the cell count is the solid number. Pass 4 (flag discs 600, road margins 64, base discs to the wire): 90,815
# cells, estimated ~11,823 on the pass 3 point, compiled 12,597 areas (0.139 per cell: the open rims taken out were cut into larger
# areas than the average kept cell). The pass 4 point is used now.
NAV_CAL = dict(areas=12597, cells=90815)
NAV_TARGET = 15000             # areas: warn above this (the first compile's approach-area pass took 26 min at 33,661)
NAV_DETOUR = 1.35              # warn when a bot's nav route to a flag is this much longer than the walking route (1b)


def nonav_nodes(G, boxes):
    """bool (K, NC): nodes whose feet are inside a NONAV box (nav generation makes no area there and cannot cross it)"""
    out = np.zeros((G.K, NX, NY), bool); Z = G.Z.reshape(G.K, NX, NY)
    for (x0, y0, z0, x1, y1, z1) in boxes:
        i0 = max(0, int(math.floor((x0 - X0) / CELL - 0.5)) + 1); i1 = min(NX, int(math.ceil((x1 - X0) / CELL - 0.5)))
        j0 = max(0, int(math.floor((y0 - Y0) / CELL - 0.5)) + 1); j1 = min(NY, int(math.ceil((y1 - Y0) / CELL - 0.5)))
        if i1 <= i0 or j1 <= j0: continue
        zz = Z[:, i0:i1, j0:j1]
        out[:, i0:i1, j0:j1] |= (zz >= z0) & (zz <= z1)
    return out.reshape(G.K, NC)


def nav_estimate(G, sc, ents, boxes=None, seeds=None):
    """flood the walk graph from the WALKABLESEED boxes and the base spawns with the nodes inside NONAV boxes taken out: the nodes
    the nav mesh would cover (island removal drops the rest). -> dict(cells, area_m2, areas, nav (bool per node), Wn (nav graph))"""
    from scipy import sparse
    if boxes is None: boxes = [b for p, n, b in sc['navboxes'] if p == 'NONAV']
    if seeds is None: seeds = [b for p, n, b in sc['navboxes'] if p == 'WALKABLESEED' and b[2] > L.LOBBY_Z + 1500]
    walkable = (G.exists & ~G.blocked).ravel()
    ok = walkable & ~nonav_nodes(G, boxes).ravel()
    start = []
    for b in seeds: start += G.nodes_near((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, b[2] - 2.0, 40.0, 16.0)
    for e in ents:
        if re.fullmatch(r'mv_spawn_(ct|t)_\d+', e['name']): start += G.nodes_near(e['o'][0], e['o'][1], e['o'][2] - 8.0, 40.0, 40.0)
    start = sorted(set(i for i in start if ok[i]))
    D = sparse.diags(ok.astype(np.int8)); Wn = (D @ G.walk @ D).tocsr(); Wn.eliminate_zeros()
    nav = reach((Wn + Wn.T).tocsr(), start) if start else np.zeros(len(ok), bool)
    Dw = sparse.diags(walkable.astype(np.int8)); Wa = (Dw @ G.walk @ Dw).tocsr()
    allw = reach((Wa + Wa.T).tocsr(), start) if start else np.zeros(len(ok), bool)
    cells = int(nav.sum())
    areas = int(round(cells * NAV_CAL['areas'] / NAV_CAL['cells'])) if NAV_CAL['cells'] else None
    return dict(cells=cells, area_m2=round(cells * (CELL * 0.0254) ** 2), areas=areas, unmarked_cells=int(allw.sum()), boxes=len(boxes), seeds=len(seeds),
                nav=nav, Wn=Wn, start=start)


def planned_navboxes(sc):
    """--nav-plan: the vmap's own WALKABLESEED boxes with the NONAV boxes mv_entities.nonav_boxes() would write now (layout + the
    vmap's seeds + out/world_sites.json waypoints): the effect of a nav markup change measured before the map is regenerated"""
    import mv_entities as ME
    ws = json.load(open(os.path.join(OUT, 'world_sites.json'))) if os.path.exists(os.path.join(OUT, 'world_sites.json')) else {}
    seeds = [b for b in sc['navboxes'] if b[0] == 'WALKABLESEED']
    sites = dict(waypoints=ws.get('waypoints', []), seeds=[((b[0] + b[3]) / 2, (b[1] + b[4]) / 2) for p, n, b in seeds])
    return seeds + [('NONAV', 'plan_%d' % (k + 1), list(b)) for k, b in enumerate(ME.nonav_boxes(None, sites=sites))]


# ================================================================ line of sight (2.5D)
class Sight:
    def __init__(self, G, sc):
        self.G = G
        hs = np.where(G.terr > -1e8, G.terr, G.Z[0])
        hs = np.where(np.isfinite(hs), hs, -500.0)
        solid = hs.copy()
        m = (G.s_kind == K_WORLD) | (G.s_kind == K_HULL)
        np.maximum.at(solid, G.s_cell[m], G.s_z[m])
        m = (G.b_kind == K_WORLD) | (G.b_kind == K_HULL) | (G.b_kind == K_TRUNK)
        np.maximum.at(solid, G.b_cell[m], G.b_hi[m])
        # tunnels and other things under the ground never lower it; tall thin things (masts, poles) are ignored below
        self.hard = solid.reshape(NX, NY)
        soft = solid.copy(); vis = solid.copy()
        for p in sc['props']:
            nm = short(p['model'])
            fol = any(k in p['model'] for k in FOLIAGE)
            ex = max(p['hi'][0] - p['lo'][0], p['hi'][1] - p['lo'][1]); hgt = p['hi'][2] - p['lo'][2]
            # everything visible counts for the helicopter grid; foliage taller than 60 u for the soft sight grid
            r = ex * (0.30 if any(k in p['model'] for k in TREES) else 0.42)
            cx, cy = (p['lo'][0] + p['hi'][0]) / 2, (p['lo'][1] + p['hi'][1]) / 2
            i0 = int((cx - r - X0) // CELL); i1 = int((cx + r - X0) // CELL); j0 = int((cy - r - Y0) // CELL); j1 = int((cy + r - Y0) // CELL)
            if i1 < 0 or j1 < 0 or i0 >= NX or j0 >= NY: continue
            ii, jj = np.meshgrid(np.arange(max(i0, 0), min(i1, NX - 1) + 1), np.arange(max(j0, 0), min(j1, NY - 1) + 1), indexing='ij')
            ok = np.hypot(X0 + (ii + 0.5) * CELL - cx, Y0 + (jj + 0.5) * CELL - cy) <= max(r, CELL * 0.6)
            c = (ii[ok] * NY + jj[ok]).astype(np.int64)
            if not len(c): continue
            np.maximum.at(vis, c, p['hi'][2])
            if fol and hgt >= 60.0: np.maximum.at(soft, c, p['hi'][2] - (0.12 * hgt if hgt > 200 else 0.0))
        self.soft = soft.reshape(NX, NY); self.vis = vis.reshape(NX, NY)

    def los(self, A, B, soft=False, skip=48.0):
        """A, B: (N, 3) eye / target points -> bool (N): nothing between them rises above the line (the first / last `skip` u are free)"""
        H = self.soft if soft else self.hard
        A = np.asarray(A, float); B = np.asarray(B, float)
        d = np.hypot(B[:, 0] - A[:, 0], B[:, 1] - A[:, 1]); n = int(max(2, d.max() / CELL))
        vis = np.ones(len(A), bool)
        for s in range(1, n):
            t = s / n
            dd = d * t
            x = A[:, 0] + (B[:, 0] - A[:, 0]) * t; y = A[:, 1] + (B[:, 1] - A[:, 1]) * t; z = A[:, 2] + (B[:, 2] - A[:, 2]) * t
            i = np.clip(((x - X0) // CELL).astype(np.int64), 0, NX - 1); j = np.clip(((y - Y0) // CELL).astype(np.int64), 0, NY - 1)
            vis &= (H[i, j] <= z) | (dd < skip) | (d - dd < skip)
        return vis


# ================================================================ the checks
def main(path, only=None, out_json=None, verbose=False, nav_plan=False):
    t0 = time.time()
    sc = load_scene(path, verbose)
    if nav_plan: sc = dict(sc, navboxes=planned_navboxes(sc))
    G = Grid(sc, verbose)
    ents = sc['ents']; props = sc['props']
    by = {e['name']: e for e in ents if e['name']}
    res = {}; fails = []; warn = []
    def want(k): return only is None or k in only
    def node_ids(e, rxy=40.0, rz=40.0, dz=-8.0): return G.nodes_near(e['o'][0], e['o'][1], e['o'][2] + dz, rxy, rz)
    inplay = lambda x, y: abs(x) <= L.MAP_X + 200 and abs(y) <= L.MAP_Y + 200

    # ---------------------------------------------------------------- 1 walkability
    from scipy.sparse import csgraph
    ct_sp = [e for e in ents if re.fullmatch(r'mv_spawn_ct_\d+', e['name'])]; t_sp = [e for e in ents if re.fullmatch(r'mv_spawn_t_\d+', e['name'])]
    start = sorted(set(sum((node_ids(e) for e in ct_sp), [])))
    ncomp, lab = csgraph.connected_components(G.walk, directed=True, connection='strong')
    home = Counter(lab[start].tolist()).most_common(1)[0][0] if start else -1
    R = lab == home                                     # the walkable world: mutually reachable with the CT spawn ring
    G.R = R
    if want(1):
        t_ok = sum(1 for e in t_sp if any(R[i] for i in node_ids(e))); c_ok = sum(1 for e in ct_sp if any(R[i] for i in node_ids(e)))
        targets = []
        for e in ents:
            n = e['name']
            if re.fullmatch(r'mv_(flag|kit|rack|board|boardseat|mountseat|pad|tunnel|flagspawn|spawn)_.+', n) and e['cls'] in ('info_target', 'info_teleport_destination'):
                targets.append(e)
        unreach = []
        for e in targets:
            kit = re.match(r'mv_(kit|rack|board|flag|pad)_', e['name']) and not e['name'].startswith('mv_flagspawn')
            pad = e['name'].startswith('mv_pad_')            # the parked helicopter stands on it: anywhere a door can be reached from
            ids = G.nodes_near(e['o'][0], e['o'][1], e['o'][2] - (30.0 if kit else 8.0), 220.0 if pad else 72.0 if kit else 40.0, 60.0 if kit else 40.0)
            if not any(R[i] for i in ids): unreach.append(e['name'])
        ws = json.load(open(os.path.join(OUT, 'world_sites.json'))) if os.path.exists(os.path.join(OUT, 'world_sites.json')) else {}
        for (nm, x, y, z) in ws.get('waypoints', []):
            if not any(R[i] for i in G.nodes_near(x, y, z, 60.0, 30.0)): unreach.append('waypoint: ' + nm)
        targets += ws.get('waypoints', [])
        fwd = reach(G.walk, np.nonzero(R)[0]); back = reach(G.walk, np.nonzero(R)[0], reverse=True)
        stuck = fwd & ~back
        walk_blocked = G.blocked; G.blocked = G.blocked_jump
        G.jump = G.graph(JUMP); G.blocked = walk_blocked
        backj = reach(G.jump, np.nonzero(R)[0], reverse=True)
        from scipy import ndimage
        pockets = []
        st2 = stuck.reshape(G.K, NX, NY).any(0)
        labp, npk = ndimage.label(st2, structure=np.ones((3, 3)))
        hardstuck = (stuck & ~backj).reshape(G.K, NX, NY).any(0)
        if npk:
            sizes = ndimage.sum(st2, labp, np.arange(1, npk + 1)); com = ndimage.center_of_mass(st2, labp, np.arange(1, npk + 1))
            hs = ndimage.sum(hardstuck, labp, np.arange(1, npk + 1))
            for k in range(npk):
                x = X0 + (com[k][0] + 0.5) * CELL; y = Y0 + (com[k][1] + 0.5) * CELL
                if not inplay(x, y): continue
                c = cell_of(x, y)
                pockets.append(dict(x=round(x), y=round(y), z=round(float(G.Z[0, c])) if np.isfinite(G.Z[0, c]) else None, area=int(sizes[k] * CELL * CELL), no_jump_out=int(hs[k] * CELL * CELL)))
        pockets.sort(key=lambda p: -p['area'])
        big = [p for p in pockets if p['area'] > 200]
        hard = [p for p in big if p['no_jump_out'] > 200]
        res['1'] = dict(ct_spawns_ok=c_ok, t_spawns_ok=t_ok, targets=len(targets), unreachable=unreach, walkable_cells=int(R.sum()), pockets=len(big), pockets_no_jump=len(hard),
                        pocket_area=int(sum(p['area'] for p in big)), pocket_list=big[:60])
        print('1 walkability: CT spawns %d/%d, T spawns %d/%d in one walkable world (%d cells); %d targets, %d unreachable; stuck pockets %d (%d u2), %d of them not escapable by a jump'
              % (c_ok, len(ct_sp), t_ok, len(t_sp), int(R.sum()), len(targets), len(unreach), len(big), res['1']['pocket_area'], len(hard)))
        for n in unreach[:30]: print('    unreachable:', n, [round(v) for v in by[n]['o']] if n in by else '')
        for p in big[:25 if verbose else 12]: print('    pocket at (%d, %d, %s): %d u2%s' % (p['x'], p['y'], p['z'], p['area'], '' if p['no_jump_out'] > 200 else ' (a jump gets out)'))
        if c_ok < len(ct_sp) or t_ok < len(t_sp) or unreach or hard: fails.append('walkability')

    # ---------------------------------------------------------------- 1b walking routes base -> flag (along the walk graph)
    if want(1) or want(10):
        from scipy.sparse import csgraph as _cg
        W_ = G.walk.tocoo(); ca = W_.row % NC; cb = W_.col % NC
        wgt = CELL * np.hypot(ca // NY - cb // NY, ca % NY - cb % NY) + 0.01
        from scipy import sparse as _sp
        Gw = _sp.csr_matrix((wgt, (W_.row, W_.col)), shape=W_.shape)
        t_start = sorted(set(sum((node_ids(e) for e in t_sp), [])))
        dct = _cg.dijkstra(Gw, indices=start, min_only=True); dt_ = _cg.dijkstra(Gw, indices=t_start, min_only=True)
        routes = {}
        for l in 'abcde':
            e = by.get('mv_flag_' + l)
            if e is None: continue
            ids = [i for i in G.nodes_near(e['o'][0], e['o'][1], e['o'][2] - 8.0, 120.0, 80.0)]
            a_ = min((dct[i] for i in ids), default=np.inf); b_ = min((dt_[i] for i in ids), default=np.inf)
            routes[l] = dict(ct=round(float(a_)), t=round(float(b_)), ratio=round(float(a_ / b_), 3) if np.isfinite(a_) and np.isfinite(b_) and b_ > 0 else None)
        # the layout is point-symmetric for distances: A mirrors D, C mirrors E, B mirrors itself. A flag's CT/T ratio should be the
        # inverse of its mirror's (B: 1) within about 15 %
        bal = {}
        for (p_, q_) in (('a', 'd'), ('c', 'e'), ('b', 'b')):
            rp, rq = routes.get(p_, {}).get('ratio'), routes.get(q_, {}).get('ratio')
            if rp and rq: bal[p_ + q_] = round(rp if p_ == q_ else rp * rq, 3)     # 1.0 = balanced pair (B: its own ratio)
        res['1b'] = dict(routes=routes, mirror_products=bal)
        print('1b routes (walking distance base spawns -> flag, CT / T, ratio): ' + ', '.join('%s %d / %d %.2f' % (l.upper(), v['ct'], v['t'], v['ratio'] or 0) for l, v in routes.items()))
        print('    mirror balance (ratio x mirror ratio, 1.00 = even; A-D, C-E, B-B): ' + ', '.join('%s %.2f' % (k.upper(), v) for k, v in bal.items()))
        if any(abs(v - 1.0) > 0.15 for v in bal.values()): warn.append('route balance off by more than 15 %%: %s' % ', '.join('%s %.2f' % kv for kv in bal.items() if abs(kv[1] - 1.0) > 0.15))

    # ---------------------------------------------------------------- 2 sightlines
    SG = Sight(G, sc)
    eye = lambda e, h=64.0: (e['o'][0], e['o'][1], e['o'][2] - 8.0 + h)
    flags = {l: by['mv_flag_' + l] for l in 'abcde'}
    fsp = {l: [by['mv_flagspawn_%s_%d' % (l, i)] for i in range(1, 9)] for l in 'abcde'}
    if want(2):
        A = np.array([eye(a) for a in ct_sp for b in t_sp]); Bq = np.array([eye(b, 40.0) for a in ct_sp for b in t_sp])
        base_los = int(SG.los(A, Bq).sum())
        tab = {}
        for a in 'abcde':
            for b in 'abcde':
                if a >= b: continue
                P = np.array([eye(p) for p in fsp[a] for q in fsp[b]]); Q = np.array([eye(q, 40.0) for p in fsp[a] for q in fsp[b]])
                d = math.hypot(flags[a]['o'][0] - flags[b]['o'][0], flags[a]['o'][1] - flags[b]['o'][1])
                tab[a + b] = dict(dist=round(d), hard=round(float(SG.los(P, Q).mean()), 3), soft=round(float(SG.los(P, Q, soft=True, skip=96.0).mean()), 3))
        # viewshed of each flag: walkable ground within 2500 u
        expo = {}
        Rtop = R.reshape(G.K, NX, NY)
        for l in 'abcde':
            fx, fy, fz = flags[l]['o']
            i0 = int((fx - 2500 - X0) // CELL); j0 = int((fy - 2500 - Y0) // CELL)
            pts = []
            for i in range(max(i0, 0), min(i0 + int(5000 // CELL), NX), 6):
                for j in range(max(j0, 0), min(j0 + int(5000 // CELL), NY), 6):
                    d = math.hypot(X0 + (i + 0.5) * CELL - fx, Y0 + (j + 0.5) * CELL - fy)
                    if d > 2500 or d < 350: continue
                    for k in range(G.K):
                        if Rtop[k, i, j]: pts.append((X0 + (i + 0.5) * CELL, Y0 + (j + 0.5) * CELL, float(G.Z[k, i * NY + j]) + 64.0)); break
            pts = np.array(pts); tg = np.array([eye(p, 40.0) for p in fsp[l]] + [(fx, fy, fz + 40.0)])
            seen_h = np.zeros(len(pts)); seen_s = np.zeros(len(pts))
            for q in tg:
                Q = np.repeat(q[None], len(pts), 0)
                seen_h += SG.los(pts, Q); seen_s += SG.los(pts, Q, soft=True, skip=96.0)
            seen_h /= len(tg); seen_s /= len(tg)
            far = np.hypot(pts[:, 0] - fx, pts[:, 1] - fy) > 700
            # the worst overlook: the 300-u block of ground beyond 700 u that sees most of the flag's spawn points (soft)
            blk = defaultdict(list)
            for p, s_, h_ in zip(pts[far], seen_s[far], seen_h[far]): blk[(int(p[0] // 300), int(p[1] // 300))].append((s_, h_, p[2]))
            worst = max(((np.mean([v[0] for v in vs]), np.mean([v[1] for v in vs]), k, np.mean([v[2] for v in vs])) for k, vs in blk.items() if len(vs) >= 4), default=None)
            expo[l] = dict(ground_pts=len(pts), hard=round(float(seen_h.mean()), 3), soft=round(float(seen_s.mean()), 3), far_hard=round(float(seen_h[far].mean()), 3),
                           far_soft=round(float(seen_s[far].mean()), 3),
                           overlook=None if worst is None else dict(x=worst[2][0] * 300 + 150, y=worst[2][1] * 300 + 150, soft=round(float(worst[0]), 2), hard=round(float(worst[1]), 2),
                                                                    dz=round(float(worst[3] - 64.0 - fz))))
        res['2'] = dict(base_spawn_los_pairs=base_los, flag_pairs=tab, exposure=expo)
        print('2 sightlines: %d of %d base spawn pairs see each other' % (base_los, len(A)))
        print('    flag pair exposure (share of spawn-point pairs with a clear line, hard / soft): ' + ', '.join('%s %d u %.2f/%.2f' % (k.upper(), v['dist'], v['hard'], v['soft']) for k, v in tab.items() if v['hard'] > 0 or v['soft'] > 0) or 'none')
        for l in 'abcde':
            e = expo[l]; o = e['overlook']
            print('    %s: seen from %.0f %% (soft %.0f %%) of the ground within 2500 u; beyond 700 u %.0f %% (soft %.0f %%)%s' % (
                l.upper(), 100 * e['hard'], 100 * e['soft'], 100 * e['far_hard'], 100 * e['far_soft'],
                '' if o is None else '; worst overlook (%d, %d) %+d u sees %.0f %% soft' % (o['x'], o['y'], o['dz'], 100 * o['soft'])))
        if base_los: fails.append('base sightline')
        for l in 'abcde':
            if expo[l]['far_soft'] > 0.30: warn.append('flag %s is a shooting gallery (%.0f %% of the far ground sees it)' % (l.upper(), 100 * expo[l]['far_soft']))

    # ---------------------------------------------------------------- 3 cover density
    if want(3):
        cover = {}
        so3 = np.argsort(G.s_cell, kind='stable'); c3 = G.s_cell[so3]; z3 = G.s_z[so3]; r3 = G.s_src[so3]
        for n_, p in enumerate(props): p['_n'] = n_
        def support(p, x, y, zref):
            # the highest surface under a point at or below zref that is not the prop's own hull
            c = cell_of(x, y)
            if not 0 <= c < NC: return -np.inf
            i0, i1 = np.searchsorted(c3, c, 'left'), np.searchsorted(c3, c, 'right')
            zz = z3[i0:i1][(r3[i0:i1] != p['_n']) & (z3[i0:i1] <= zref)]
            return float(zz.max()) if len(zz) else -np.inf
        for l in 'abcde':
            fx, fy, fz = flags[l]['o']; head = set(); crouch = set(); bags = {}
            for pi, p in enumerate(props):
                if not p['solid'] or p['hull'] is None: continue
                cx, cy = (p['lo'][0] + p['hi'][0]) / 2, (p['lo'][1] + p['hi'][1]) / 2
                if math.hypot(cx - fx, cy - fy) > 600: continue
                base = support(p, cx, cy, p['lo'][2] + 20.0)
                if not np.isfinite(base): base = p['lo'][2]
                h = p['hi'][2] - max(base, p['lo'][2]) if p['hull'] == 'tris' else p['hi'][2] - base
                wdt = max(p['mhi'][0] - p['mlo'][0], p['mhi'][1] - p['mlo'][1]) * p['s'][0]
                if p['hull'] == 'trunk':
                    wdt = 2 * (S.TRUNK.get(p['model'], S.TRUNK_MV.get(short(p['model']), M.TRUNK.get(p['model'], 10.0)))) * p['s'][0]
                if wdt < 28.0 or abs(base - fz) > 160: continue
                if short(p['model']).startswith('flag_pole'): continue
                # stacked sandbag courses count as one wall piece per 96 u of length (the staggered courses fall in one column)
                if 'sandbag' in p['model']:        # a stacked wall: measure the whole column (each course stands on the one below)
                    key = ('bag', round(cx / 96), round(cy / 96)); b0, b1 = bags.get(key, (1e9, -1e9))
                    bags[key] = (min(b0, support(p, cx, cy, p['lo'][2] + 6.0)), max(b1, p['hi'][2])); continue
                key = pi
                top = p['hi'][2] - base
                if top >= 62.0: head.add(key)
                elif top >= 36.0: crouch.add(key)
            for key, (b0, b1) in bags.items():
                if not np.isfinite(b0) or abs(b0 - fz) > 160: continue
                if b1 - b0 >= 62.0: head.add(key)
                elif b1 - b0 >= 36.0: crouch.add(key)
            # world geometry (terrace edges, berms, boulders, abutments): one piece per mesh within range that stands 62 u over the ground beside it
            for mi, ms in enumerate(sc['meshes']):
                if ms['kind'] != K_WORLD or 'groundrock' in ms['mat'] and ms['hi'][2] - ms['lo'][2] > 600: continue
                cx, cy = (ms['lo'][0] + ms['hi'][0]) / 2, (ms['lo'][1] + ms['hi'][1]) / 2
                if math.hypot(max(ms['lo'][0] - fx, 0, fx - ms['hi'][0]), max(ms['lo'][1] - fy, 0, fy - ms['hi'][1])) > 600: continue
                g = min(G.terr[cell_of(x, y)] for x in (ms['lo'][0] - 24, ms['hi'][0] + 24) for y in (ms['lo'][1] - 24, ms['hi'][1] + 24) if 0 <= cell_of(x, y) < NC)
                if g < -1e8: continue
                if ms['hi'][2] - g >= 62.0: head.add(('mesh', mi))
                elif ms['hi'][2] - g >= 36.0: crouch.add(('mesh', mi))
            cover[l] = dict(head=len(head), crouch=len(crouch))
        res['3'] = cover
        print('3 cover within 600 u (head-height / crouch-height pieces): ' + ', '.join('%s %d / %d' % (l.upper(), v['head'], v['crouch']) for l, v in cover.items()))
        if min(v['head'] for v in cover.values()) < 14: fails.append('cover')

    # ---------------------------------------------------------------- 4 helicopters
    if want(4):
        lay = json.load(open(os.path.join(OUT, 'layout.json'))) if os.path.exists(os.path.join(OUT, 'layout.json')) else {}
        pads = []; bad_pad = []
        heli_parts = re.compile(r'mv_(heli|rotor|tail|pad|flagpole)_')
        for tg in ('ct', 't'):
            for i in (1, 2, 3):
                e = by.get('mv_pad_%s_%d' % (tg, i)); hb = by.get('mv_heli_%s_%d' % (tg, i))
                if e is None: continue
                kind = M.HELI_ON_PAD[tg][i - 1]; h = M.apache(OUT) if kind == 'apache' else M.pick(kind)
                rr = float(h['rotor_r']) + 60.0; yaw = math.radians(e['a'][1])
                hx = e['o'][0] + math.cos(yaw) * h['hub'][0] - math.sin(yaw) * h['hub'][1]; hy = e['o'][1] + math.sin(yaw) * h['hub'][0] + math.cos(yaw) * h['hub'][1]
                pz = e['o'][2]; hits = []
                for p in props:
                    if heli_parts.match(p['name'] or '') or 'psp_pad' in p['model']: continue
                    if p['hi'][2] <= pz + 24.0 or p['lo'][2] >= pz + 600.0: continue
                    # distance from the hub to the prop's footprint rectangle
                    px = np.array(p['poly']); d = min(_seg_d(hx, hy, px[k], px[(k + 1) % 4]) for k in range(4))
                    if _inside(hx, hy, px): d = 0.0
                    if any(k in p['model'] for k in TREES):      # crown radius from the model's own bounds (the world box of a turned tree is up to 1.4x wider)
                        d = max(0.0, math.hypot(p['o'][0] - hx, p['o'][1] - hy) - 0.3 * max(p['mhi'][0] - p['mlo'][0], p['mhi'][1] - p['mlo'][1]) * p['s'][0])
                    if d < rr: hits.append((round(d), short(p['model']), round(p['hi'][2] - pz)))
                # the pad's own windsock post, if any, counts
                for p in props:
                    if 'psp_pad' in p['model'] and math.hypot(p['o'][0] - e['o'][0], p['o'][1] - e['o'][1]) < 50 and p['hi'][2] > pz + 24:
                        c_, s_ = math.cos(math.radians(p['yaw'])), math.sin(math.radians(p['yaw'])); k_ = p['s'][0]
                        wx, wy = p['o'][0] + (280 * c_ - 280 * s_) * k_, p['o'][1] + (280 * s_ + 280 * c_) * k_
                        d = math.hypot(wx - hx, wy - hy)
                        if d < rr: hits.append((round(d), 'psp_pad windsock post', round(p['hi'][2] - pz)))
                # ground and world geometry inside the cylinder
                n = int(rr // CELL); ci = int((hx - X0) // CELL); cj = int((hy - Y0) // CELL); gmax = -1e9
                for a in range(-n, n + 1):
                    for b in range(-n, n + 1):
                        if math.hypot(a, b) * CELL > rr: continue
                        zz = SG.hard[ci + a, cj + b] if False else G.terr[(ci + a) * NY + cj + b]
                        gmax = max(gmax, zz)
                if gmax > pz + 24.0: hits.append((0, 'ground', round(gmax - pz)))
                wm = (G.s_kind == K_WORLD) & (G.s_z > pz + 24.0) & (G.s_z < pz + 600.0)
                wx = X0 + (G.s_cell[wm] // NY + 0.5) * CELL; wy = Y0 + (G.s_cell[wm] % NY + 0.5) * CELL
                wd = np.hypot(wx - hx, wy - hy)
                if (wd < rr).any(): hits.append((round(float(wd.min())), 'world geometry (berm / wall)', round(float(G.s_z[wm][wd < rr].max() - pz))))
                # approach lanes: 8 directions, a LANE_GLIDE line from 60 u over the pad out to 1800 u, 40 u clear of everything visible
                lanes = 0; lane_dirs = []; lane_block = []
                for a8 in range(8):
                    an = a8 * math.pi / 4; okl = True
                    for d in np.arange(rr, 1800.0, CELL):
                        x = hx + math.cos(an) * d; y = hy + math.sin(an) * d
                        i_ = int((x - X0) // CELL); j_ = int((y - Y0) // CELL)
                        if not (0 <= i_ < NX and 0 <= j_ < NY): break
                        if SG.vis[i_, j_] + 40.0 > pz + 60.0 + math.tan(math.radians(LANE_GLIDE)) * d:
                            okl = False; lane_block.append((a8 * 45, round(x), round(y), round(float(SG.vis[i_, j_] - pz)))); break
                    lanes += okl; lane_dirs.append(int(okl))
                pads.append(dict(pad='%s_%d' % (tg, i), heli=kind, clear_r=round(rr), obstacles=hits[:12], lanes=lanes, lane_dirs=lane_dirs, lane_block=lane_block))
                if hits or lanes < 3: bad_pad.append('%s_%d' % (tg, i))
        # karst crowns
        kr = []; bad_k = []
        need = 150.0                                   # landing disc radius: the Mi-8's wheels are 170 x 180 apart (circumradius 110); the Apache's tail wheel may overhang
        for (kx, ky, r, hh, ks) in L.KARST:
            if ks not in L.KARST_LANDABLE: continue
            top = G.top(kx, ky)
            best = None
            ws_ = json.load(open(os.path.join(OUT, 'world_sites.json'))).get('landing', []) if os.path.exists(os.path.join(OUT, 'world_sites.json')) else []
            spots = [(l_[0] - kx, l_[1] - ky) for l_ in ws_ if l_[3] == ks] or [(ox, oy) for ox in range(-160, 161, 40) for oy in range(-160, 161, 40)]
            for (ox, oy) in spots:
                for _one in (0,):
                    cx, cy = kx + ox, ky + oy; zs = []
                    for a in range(0, 360, 20):
                        for rr_ in (need * 0.5, need):
                            zs.append(G.top(cx + rr_ * math.cos(math.radians(a)), cy + rr_ * math.sin(math.radians(a))))
                    zs.append(G.top(cx, cy)); zs = np.array(zs)
                    if (zs < top - 300).any(): continue
                    slope = math.degrees(math.atan((zs.max() - zs.min()) / (2 * need)))
                    # props on the disc
                    obst = [short(p['model']) for p in props if p['hi'][2] > zs.min() + 10 and p['lo'][2] < top + 300 and math.hypot((p['lo'][0] + p['hi'][0]) / 2 - cx, (p['lo'][1] + p['hi'][1]) / 2 - cy) < need
                            and 'flag' not in p['model']]
                    score = (len(obst), slope)
                    if best is None or score < best[0]: best = (score, cx, cy, slope, obst, float(zs.max() - zs.min()))
            if best is None: kr.append(dict(karst=ks, ok=False, why='no disc of radius %d on the crown' % need)); bad_k.append(ks); continue
            okk = not best[4] and best[3] < 10.0
            kr.append(dict(karst=ks, x=best[1], y=best[2], top=round(top), slope=round(best[3], 1), relief=round(best[5], 1), obstacles=dict(Counter(best[4])), ok=okk))
            if not okk: bad_k.append(ks)
        res['4'] = dict(pads=pads, karst=kr)
        print('4 helicopters: %d pads, %d with something in the rotor cylinder or fewer than 3 approach lanes; %d karst crowns, %d without a clear flat landing disc' % (len(pads), len(bad_pad), len(kr), len(bad_k)))
        for p in pads:
            if p['obstacles'] or p['lanes'] < 3 or verbose: print('    pad %s (%s, clear radius %d): lanes %d/8 %s, obstacles %s' % (p['pad'], p['heli'], p['clear_r'], p['lanes'], p['lane_dirs'], p['obstacles'][:6]))
            if p['lanes'] < 3: print('        first blocker per closed lane (dir, x, y, height over the pad):', p['lane_block'])
        for k in kr:
            if not k['ok'] or verbose: print('    karst %s: %s' % (k['karst'], {a: b for a, b in k.items() if a != 'karst'}))
        if bad_pad or bad_k: fails.append('helicopter clearance')

    # ---------------------------------------------------------------- 5 spawn safety
    if want(5):
        mounts = []
        for e in ents:
            if re.fullmatch(r'mv_mountinfo_\d+', e['name']):
                kind, team = e['msg'].split(':'); mounts.append((e['name'], team, tuple(e['o']) + (e['a'][1],)))
        pits = [('mv_gun_ct_%d' % i, 'ct', tuple(by['mv_gun_ct_%d' % i]['o']) + (0.0,)) for i in (1, 2, 3)] + [('mv_gun_t_%d' % i, 't', tuple(by['mv_gun_t_%d' % i]['o']) + (0.0,)) for i in (1, 2, 3, 4)]
        bad = []
        def test(sp, team_of_spawn, label):
            for (mn, team, mo) in mounts + pits:
                if team_of_spawn is not None and team == team_of_spawn: continue
                if team_of_spawn is not None and team == 'any': continue
                d = math.hypot(sp['o'][0] - mo[0], sp['o'][1] - mo[1])
                if d > 900: continue
                if mn.startswith('mv_mountinfo') and abs((math.degrees(math.atan2(sp['o'][1] - mo[1], sp['o'][0] - mo[0])) - mo[3] + 180) % 360 - 180) > MOUNT_CONE + 10.0: continue
                a = np.array([[mo[0], mo[1], mo[2] + 20.0]]); b = np.array([eye(sp, 40.0)])
                if SG.los(a, b, skip=40.0)[0]: bad.append((sp['name'], mn, round(d), label))
        for e in ct_sp: test(e, 'ct', 'base')
        for e in t_sp: test(e, 't', 'base')
        for l in 'abcde':
            for e in fsp[l]: test(e, None, 'flag')
        base_bad = [b for b in bad if b[3] == 'base']; flag_bad = [b for b in bad if b[3] == 'flag']
        res['5'] = dict(base=base_bad, flag=flag_bad)
        print('5 spawn safety: %d base spawns and %d flag spawns in the line of fire of a mounted gun / pit within 900 u' % (len(base_bad), len(flag_bad)))
        for b in (base_bad + flag_bad)[:16]: print('    %s seen by %s at %d u' % b[:3])
        if base_bad or flag_bad: fails.append('spawn safety')

    # ---------------------------------------------------------------- 6 prop clipping
    if want(6):
        sites = json.load(open(os.path.join(OUT, 'world_sites.json'))) if os.path.exists(os.path.join(OUT, 'world_sites.json')) else {}
        tag = {}
        for e in sites.get('exceptions', []): tag[(e[0], round(e[1]), round(e[2]))] = e[4]
        buried = []; floating = []; inwater = []; crown = []; inside = []
        # support heights: surfaces of terrain / world meshes / hulls
        bld = [p for p in props if any(k in p['model'] for k in BUILDINGS) and p['solid']]
        solids = [p for p in props if p['solid'] and p['hull'] == 'tris' and not short(p['model']).startswith(('psp_pad', 'flag_pole'))]
        sgrid = defaultdict(list)
        for n_, p in enumerate(props): p['_n'] = n_
        o_ = np.argsort(sc['srcs'], kind='stable'); ss = sc['srcs'][o_]
        hull_idx = (o_, ss)
        for p in solids:
            for i in range(int(p['lo'][0] // 256), int(p['hi'][0] // 256) + 1):
                for j in range(int(p['lo'][1] // 256), int(p['hi'][1] // 256) + 1): sgrid[(i, j)].append(p)
        # every raw surface per cell (the walk layers merge surfaces within 12 u: a bag sunk 10 u into a crown hid the crown)
        so_ = np.argsort(G.s_cell, kind='stable'); s_c = G.s_cell[so_]; s_zz = G.s_z[so_]; s_sr = G.s_src[so_]
        for p in props:
            if p['cls'] != 'prop_static': continue
            nm = short(p['model']); zlo, zhi = p['lo'][2], p['hi'][2]; h = max(zhi - zlo, 1.0)
            cx, cy = (p['lo'][0] + p['hi'][0]) / 2, (p['lo'][1] + p['hi'][1]) / 2
            px = np.array(p['poly']); c0 = px.mean(0)
            samp = [tuple(c0)] + [tuple(c0 + (q - c0) * 0.6) for q in px]
            if any(k in p['model'] for k in TREES): samp = [(p['o'][0], p['o'][1])]       # a tree stands on its trunk, not on its crown's shadow
            t = next((tag[k_] for k_ in ((p['model'], round(p['o'][0]) + i_, round(p['o'][1]) + j_) for i_ in (0, -1, 1) for j_ in (0, -1, 1)) if k_ in tag), None)   # x.5 rounds either way
            fr = []; gaps = []
            for (x, y) in samp:
                c = cell_of(x, y)
                if not 0 <= c < NC: continue
                zs = G.Z[:, c]; kd = G.kind[:, c]
                tw = zs[np.isfinite(zs) & ((kd == K_TERRAIN) | (kd == K_WORLD))]
                tw = tw[tw < zhi + 60.0]                       # ground far overhead (a tunnel roof) does not bury it
                fr.append(float(np.clip((tw.max() - zlo) / h, 0, 1)) if len(tw) else 0.0)
                i0_, i1_ = np.searchsorted(s_c, c, 'left'), np.searchsorted(s_c, c, 'right')
                zr_ = s_zz[i0_:i1_][s_sr[i0_:i1_] != p['_n']]
                sup = zr_[zr_ <= zlo + 12.0]
                gaps.append(zlo - float(sup.max()) if len(sup) else -1e9)       # nothing under it within reach: it is sunk in, not floating
            if not fr: continue
            fol = any(k in p['model'] for k in FOLIAGE)
            rock = p['model'] in S.ROCKS or p['model'] in getattr(S, 'RUBBLE', ())      # boulders are set into the ground on purpose
            if np.mean(fr) > 0.35 and t not in ('rock', 'water') and not rock and not fol and 'bridge_pier' not in nm and 'water_wall' not in nm:
                buried.append((round(float(np.mean(fr)), 2), nm, round(p['o'][0]), round(p['o'][1]), round(p['o'][2]), t or ''))
            lim = 6.0
            if min(gaps) > lim and t not in ('water', 'bridge') and 'vine' not in nm and 'water_wall' not in nm and 'parachute' not in nm:
                floating.append((round(min(gaps), 1), nm, round(p['o'][0]), round(p['o'][1]), round(p['o'][2]), t or ''))
            # under water
            c = cell_of(p['o'][0], p['o'][1])
            if 0 <= c < NC and G.water[c] > -1e8 and G.terr[c] > -1e8 and G.water[c] - max(G.terr[c], p['o'][2]) > 8.0 and not any(k in p['model'] for k in WATER_OK) and t != 'water':
                inwater.append((round(float(G.water[c] - G.terr[c]), 1), nm, round(p['o'][0]), round(p['o'][1])))
            # tree crowns through buildings: the crown core (60 % of the bounds, from 40 % of the height up) against a building's box
            if any(k in p['model'] for k in TREES) and '_roots' not in p['model']:      # roots are meant to grip the ruins
                ex = 0.3 * max(p['mhi'][0] - p['mlo'][0], p['mhi'][1] - p['mlo'][1]) * p['s'][0]; cz0 = zlo + 0.4 * h
                for b in bld:
                    if b['hi'][2] < cz0 + 10: continue
                    bx = np.array(b['poly'])
                    d = 0.0 if _inside(p['o'][0], p['o'][1], bx) else min(_seg_d(p['o'][0], p['o'][1], bx[k], bx[(k + 1) % 4]) for k in range(4))
                    if d < ex * 0.8: crown.append((short(p['model']), short(b['model']), round(p['o'][0]), round(p['o'][1]), round(d)))
            # non-solid dressing whose origin is inside a solid prop's hull box (not just touching)
            if not p['solid'] and h > 12:
                for b in sgrid.get((int(p['o'][0] // 256), int(p['o'][1] // 256)), ()):
                    if b is p or b['hi'][2] < p['o'][2] + 6 or b['lo'][2] > p['o'][2] + 0.5 * h: continue
                    if any(k in b['model'] for k in ('truss_span', 'camo_net', 'c123_fuselage', 'checkpoint', 'school', 'camp_hut', 'french_bunker', 'khmer', 'guard_tower')): continue
                    if not (b['lo'][0] < p['o'][0] < b['hi'][0] and b['lo'][1] < p['o'][1] < b['hi'][1]): continue
                    if _in_hull(sc, hull_idx, b['_n'], p['o'][0], p['o'][1], p['o'][2] + min(10.0, 0.4 * h)):
                        inside.append((nm, short(b['model']), round(p['o'][0]), round(p['o'][1]))); break
        buried.sort(reverse=True); floating.sort(reverse=True)
        res['6'] = dict(buried=len(buried), floating=len(floating), in_water=len(inwater), crown_in_building=len(crown), dressing_inside_solid=len(inside),
                        buried_list=buried[:80], floating_list=floating[:80], in_water_list=inwater[:40], crown_list=crown[:40], inside_list=inside[:60])
        print('6 clipping: %d buried > 35 %%, %d floating > 6 u, %d under water, %d tree crowns through buildings, %d dressing props inside solids' % (len(buried), len(floating), len(inwater), len(crown), len(inside)))
        for label, lst in (('buried', buried), ('floating', floating), ('under water', inwater), ('crown', crown), ('inside', inside)):
            cnt = Counter(b[1] if label in ('buried', 'floating', 'under water') else b[0] + ' in ' + b[1] for b in lst)
            if cnt: print('    %s: %s' % (label, ', '.join('%s x%d' % kv for kv in cnt.most_common(10))))
            for b in lst[:6 if not verbose else 30]: print('       ', b)
        if buried or floating or inwater or crown or inside: fails.append('clipping')

    # ---------------------------------------------------------------- 7 water
    if want(7):
        T = sc['tris']; wt = np.nonzero(sc['kinds'] == K_WATER)[0]
        edges = defaultdict(int); eg = {}
        for ti in wt:
            t = T[ti]
            for k in range(3):
                a = tuple(np.round(t[k], 1)); b = tuple(np.round(t[(k + 1) % 3], 1)); key = (min(a, b), max(a, b)); edges[key] += 1; eg[key] = sc['srcs'][ti]
        exposed = []; npts = 0
        for (a, b), n in edges.items():
            if n != 1: continue
            ln = math.hypot(b[0] - a[0], b[1] - a[1]); m = max(1, int(ln // 16))
            for s in range(m + 1):
                x = a[0] + (b[0] - a[0]) * s / m; y = a[1] + (b[1] - a[1]) * s / m; z = a[2]
                if not inplay(x, y) or abs(x) > L.MAP_X or abs(y) > L.MAP_Y: continue
                c = cell_of(x, y); npts += 1
                # the ground at the edge: the terrain mesh nearby (worst of the cell and its neighbours' lowest)
                if abs(x - L.FALL_X) < 40.0: continue           # the lip of the fall: the water wall hangs from it
                g = mesh_z(x, y) if G.terr[c] > -1e8 else -1e9
                if g < z - 0.05:
                    # another sheet at the same height continues past this edge (the river into the marsh): not an edge
                    cont = False
                    for d in (1, -1, NY, -NY, NY + 1, NY - 1, -NY + 1, -NY - 1):
                        cc = c + d
                        if 0 <= cc < NC:
                            mm = G.w_cell == cc
                            if mm.any() and (np.abs(G.w_z[mm] - z) < 2).any() and (G.w_src[mm] != eg[(a, b)]).any(): cont = True; break
                    if not cont: exposed.append((round(x), round(y), round(z, 1), round(float(z - g), 1)))
        # z-fight: cells covered by two different sheets within 1.5 u of each other
        o = np.lexsort((G.w_z, G.w_cell)); c = G.w_cell[o]; z = G.w_z[o]; s = G.w_src[o]
        zf = (c[1:] == c[:-1]) & (np.abs(z[1:] - z[:-1]) < 1.5) & (s[1:] != s[:-1])
        zcells = np.unique(c[1:][zf]); zcells = [cc for cc in zcells if G.terr[cc] < G.water[cc] - 0.5]
        deep = int(((G.water - G.terr > 60.0) & (G.terr > -1e8) & R.reshape(G.K, NC).any(0)).sum())
        # cluster the exposed points
        ex_cl = _cluster([(e[0], e[1]) for e in exposed], 200.0)
        res['7'] = dict(edge_points=npts, exposed_points=len(exposed), exposed_places=len(ex_cl), zfight_cells=len(zcells), deep_walkable_cells=deep,
                        exposed_list=[dict(x=round(cx), y=round(cy), n=n) for cx, cy, n in ex_cl[:40]], exposed_points_list=exposed[:60], zfight_list=[[round(v) for v in cell_xy(cc)] for cc in zcells[:20]])
        print('7 water: %d sheet edge points, %d above the ground in %d places; %d cells where two sheets overlap at one height above the ground; %d walkable cells deeper than 60 u'
              % (npts, len(exposed), len(ex_cl), len(zcells), deep))
        for cx, cy, n in ex_cl[:10]: print('    exposed edge near (%d, %d): %d points' % (cx, cy, n))
        for cc in zcells[:6]: print('    z-fight at', [round(v) for v in cell_xy(cc)])
        if exposed or zcells: fails.append('water')

    # ---------------------------------------------------------------- 8 terrain
    if want(8):
        tz = lambda x, y: float(G.terr[cell_of(x, y)]) if 0 <= cell_of(x, y) < NC else -1e9
        road = []; worst_s = 0.0; worst_x = 0.0; steep = []; cross = []; gul = []
        for k, (hw, pts) in enumerate(L.ROADS):
            Pp = np.array(pts, float); seg = np.linalg.norm(np.diff(Pp, axis=0), axis=1)
            for a, b, d in zip(Pp[:-1], Pp[1:], seg):
                u = (b - a) / d; nr = np.array([-u[1], u[0]])
                for s in np.arange(0.0, d - 48.0, 32.0):
                    p = a + u * s; q = p + u * 64.0
                    for off in (0.0, hw * 0.5, -hw * 0.5):
                        z0 = tz(*(p + nr * off)); z1 = tz(*(q + nr * off))
                        if z0 < -1e8 or z1 < -1e8: continue
                        sl = math.degrees(math.atan(abs(z1 - z0) / 64.0))
                        if sl > worst_s: worst_s = sl
                        if sl >= 20.0: steep.append((k, round(p[0]), round(p[1]), round(sl, 1)))
                    zl = tz(*(p + nr * hw * 0.8)); zr = tz(*(p - nr * hw * 0.8)); zc = tz(*p)
                    if min(zl, zr, zc) > -1e8:
                        cf = max(abs(zl - zc), abs(zr - zc))
                        worst_x = max(worst_x, cf)
                        if cf > 14.0: cross.append((k, round(p[0]), round(p[1]), round(cf, 1)))
                        dt = float(abs(L.detail(np.array([p[0]]), np.array([p[1]]))[0]))
                        if dt > 1.0: gul.append((k, round(p[0]), round(p[1]), round(dt, 1)))
        # bridge: the foot of each ramp against the ground, the head against the deck
        bx, by_ = L.BRIDGE_X, L.BRIDGE_Y; half = L.BRIDGE_LEN / 2; bridge = {}
        for s, nm in ((-1, 'south'), (1, 'north')):
            yo = by_ + s * (half + L.BRIDGE_RAMP)
            dz = []
            for x in np.arange(bx - 72, bx + 73, 16.0):
                wedge = G.top(x, yo - s * 10.0); gr = tz(x, yo + s * 14.0)
                dz.append(wedge - gr)
            # deck joint: deck surface each side of the span end
            jd = [abs(G.top(x, by_ + s * (half - 10.0)) - G.top(x, by_ + s * (half + 10.0))) for x in (bx - 40, bx, bx + 40)]
            bridge[nm] = dict(foot_step_max=round(float(np.max(np.abs(dz))), 1), foot_step=[round(float(v), 1) for v in dz], deck_joint=round(float(max(jd)), 1))
        # ground through walk-in floors
        poke = []
        for p in props:
            f = FLOORS.get(short(p['model']))
            if f is None: continue
            c_, s_ = math.cos(math.radians(p['yaw'])), math.sin(math.radians(p['yaw']))
            worst = -1e9
            for lx in np.linspace(f[0] + 6, f[2] - 6, 9):
                for ly in np.linspace(f[1] + 6, f[3] - 6, 9):
                    x = p['o'][0] + c_ * lx - s_ * ly; y = p['o'][1] + s_ * lx + c_ * ly
                    cc = cell_of(x, y); zs = G.Z[:, cc]; kd = G.kind[:, cc]
                    tw = zs[np.isfinite(zs) & ((kd == K_TERRAIN) | (kd == K_WORLD))]
                    tw = tw[tw < p['o'][2] + f[4] + 200.0]
                    if len(tw): worst = max(worst, float(tw.max()) - (p['o'][2] + f[4]))
            if worst > 0.5: poke.append((round(worst, 1), short(p['model']), round(p['o'][0]), round(p['o'][1])))
        # terrain holes: cells inside the terrain's extent with no terrain surface; each needs a floor (world or hull) under it
        tm = (G.terr > -1e8).reshape(NX, NY)
        from scipy import ndimage
        hole = ~tm & ndimage.binary_fill_holes(tm)
        hole_cells = np.nonzero(hole.ravel())[0]
        open_gap = []
        kcut = np.zeros(NC, bool)
        for (kx, ky, r, hh, ks) in L.KARST:
            for cc in hole_cells:
                x, y = cell_xy(cc)
                if math.hypot(x - kx, y - ky) < r: kcut[cc] = True
        for cc in hole_cells:
            if kcut[cc]: continue
            zs = G.Z[:, cc]; kd = G.kind[:, cc]
            if not (np.isfinite(zs) & ((kd == K_WORLD) | (kd == K_HULL))).any(): open_gap.append(cc)
        gap_cl = _cluster([cell_xy(cc) for cc in open_gap], 100.0)
        res['8'] = dict(road_max_slope=round(worst_s, 1), road_steep=len(steep), road_cross_fall_max=round(worst_x, 1), road_cross=len(cross), road_detail=len(gul), bridge=bridge,
                        floor_poke=poke, hole_cells=int(len(hole_cells) - kcut.sum()), hole_uncovered=len(open_gap),
                        steep_list=steep[:40], cross_list=cross[:40], hole_gap_list=[dict(x=round(a), y=round(b), n=n) for a, b, n in gap_cl[:20]])
        print('8 terrain: roads max slope %.1f deg (%d samples >= 20), max cross fall %.1f u (%d > 14), %d road samples with erosion detail; bridge foot step S %.1f N %.1f, deck joint S %.1f N %.1f; '
              'ground through %d walk-in floors; %d hole cells, %d with nothing under them'
              % (worst_s, len(steep), worst_x, len(cross), len(gul), bridge['south']['foot_step_max'], bridge['north']['foot_step_max'], bridge['south']['deck_joint'], bridge['north']['deck_joint'],
                 len(poke), res['8']['hole_cells'], len(open_gap)))
        for s_ in _cluster([(s[1], s[2]) for s in steep], 250.0)[:8]: print('    steep road near (%d, %d): %d samples' % s_)
        for s_ in _cluster([(s[1], s[2]) for s in cross], 250.0)[:8]: print('    road cross fall near (%d, %d): %d samples' % s_)
        for p in poke[:10]: print('    ground %.1f u through the floor of %s at (%d, %d)' % p)
        for a, b, n in gap_cl[:8]: print('    uncovered hole near (%d, %d): %d cells' % (a, b, n))
        if steep or gul or poke or open_gap or max(bridge['south']['foot_step_max'], bridge['north']['foot_step_max']) > 4.0 or max(bridge['south']['deck_joint'], bridge['north']['deck_joint']) > 4.0:
            fails.append('terrain')
        if cross: warn.append('%d road samples with a cross fall over 14 u' % len(cross))

    # ---------------------------------------------------------------- 9 nav markup
    if want(9):
        seeds = [b for b in sc['navboxes'] if b[0] == 'WALKABLESEED']; nonav = [b for b in sc['navboxes'] if b[0] == 'NONAV']
        bad_seed = []
        for prop, name, b in seeds:
            if b[2] < L.LOBBY_Z + 1500: continue
            ids = G.nodes_near((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, b[2] - 2.0, 30.0, 16.0)
            if not any(R[i] for i in ids): bad_seed.append((name, [round(v) for v in b[:3]]))
        pts = []
        for k, (hw, rp) in enumerate(L.ROADS):
            Pp = np.array(rp, float)
            for a, b in zip(Pp[:-1], Pp[1:]):
                n = max(1, int(np.linalg.norm(b - a) // 32))
                for s in range(n + 1):
                    p = a + (b - a) * s / n; pts.append(('road %d' % k, p[0], p[1], G.top(p[0], p[1]) if abs(p[0]) < 1 and False else float(G.terr[cell_of(p[0], p[1])])))
        for e in ents:
            if re.fullmatch(r'mv_(flag|kit|rack|board|boardseat|mountseat|pad|tunnel|flagspawn|spawn)_.+', e['name']) and e['cls'] in ('info_target', 'info_teleport_destination'):
                pts.append((e['name'], e['o'][0], e['o'][1], e['o'][2] - 8.0))
        for y in np.arange(L.BRIDGE_Y - L.BRIDGE_LEN / 2 - L.BRIDGE_RAMP + 16, L.BRIDGE_Y + L.BRIDGE_LEN / 2 + L.BRIDGE_RAMP, 32.0):
            pts.append(('bridge', L.BRIDGE_X, float(y), G.top(L.BRIDGE_X, float(y))))
        import mv_entities as ME
        for (x0_, y0_, x1_, y1_, zt) in json.load(open(os.path.join(OUT, 'world_sites.json'))).get('surfaces', []):
            # pass 3: a walk-on surface outside the places bots use (the shelf behind the waterfall) is NONAV by design
            if not ME.nav_play_mask(np.array([(x0_ + x1_) / 2]), np.array([(y0_ + y1_) / 2]))[0]: continue
            for x in np.arange(x0_ + 24, x1_, 96.0):
                for y in np.arange(y0_ + 24, y1_, 96.0): pts.append(('surface', float(x), float(y), zt))
        covered = []
        for (nm, x, y, z) in pts:
            for prop, name, b in nonav:
                if b[0] < x < b[3] and b[1] < y < b[4] and b[2] < z + 36.0 and b[5] > z: covered.append((nm, round(x), round(y), name)); break
        cc = Counter(c[0] for c in covered)
        res['9'] = dict(seeds=len(seeds), bad_seeds=bad_seed, nonav=len(nonav), covered=len(covered), covered_by=dict(cc.most_common(20)))
        print('9 nav: %d seeds, %d not on walkable ground; %d NONAV boxes cover %d road / station points%s' % (len(seeds), len(bad_seed), len(nonav), len(covered),
              ' (boxes from the nav plan, not the vmap)' if nav_plan else ''))
        for b in bad_seed[:8]: print('    seed', b)
        for c in covered[:10]: print('    NONAV over', c)
        if bad_seed or covered: fails.append('nav')
        # pass 3: the nav the compile would make (estimate), every station on it, every flag reachable by bots from both bases
        ne = nav_estimate(G, sc, ents, boxes=[b for p, n, b in nonav], seeds=[b for p, n, b in seeds if b[2] > L.LOBBY_Z + 1500])
        nav = ne['nav']
        print('    nav estimate: %d walk cells of 16 u (%d m2) flooded from %d seeds + the base spawns, %d without the NONAV boxes; ~%s nav areas '
              '(linear in cells, calibrated on the pass 4 compile: %d cells = %d areas)' % (ne['cells'], ne['area_m2'], ne['seeds'], ne['unmarked_cells'],
              ne['areas'], NAV_CAL['cells'], NAV_CAL['areas']))
        need = []
        for e in ents:
            n_ = e['name']
            if not (re.fullmatch(r'mv_(flag|kit|rack|boardseat|mountseat|tunnel|flagspawn|spawn)_.+', n_) and e['cls'] in ('info_target', 'info_teleport_destination')): continue
            kit = re.match(r'mv_(kit|rack|flag)_', n_) and not n_.startswith('mv_flagspawn')
            ids = G.nodes_near(e['o'][0], e['o'][1], e['o'][2] - (30.0 if kit else 8.0), 72.0 if kit else 48.0, 60.0 if kit else 40.0)
            if not any(nav[i] for i in ids): need.append(n_)
        wp_off = [w[0] for w in json.load(open(os.path.join(OUT, 'world_sites.json'))).get('waypoints', []) if not any(nav[i] for i in G.nodes_near(w[1], w[2], w[3], 60.0, 30.0))]
        # bot routes: the nav graph (directed walk graph inside the nav) from each base's spawn ring to each flag and back
        from scipy.sparse import csgraph as _cg
        from scipy import sparse as _sp
        Wn = ne['Wn'].tocoo(); ca = Wn.row % NC; cb = Wn.col % NC
        Gn = _sp.csr_matrix((CELL * np.hypot(ca // NY - cb // NY, ca % NY - cb % NY) + 0.01, (Wn.row, Wn.col)), shape=Wn.shape)
        sp_ = {tg: sorted(set(i for e in ents if re.fullmatch(r'mv_spawn_%s_\d+' % tg, e['name']) for i in node_ids(e) if nav[i])) for tg in ('ct', 't')}
        broute = {}; lost = []; detour = []
        for tg in ('ct', 't'):
            if not sp_[tg]: lost.append('%s spawns have no nav' % tg); continue
            dd = _cg.dijkstra(Gn, indices=sp_[tg], min_only=True); back = reach(ne['Wn'], sp_[tg], reverse=True)
            for l in 'abcde':
                e = by.get('mv_flag_' + l)
                if e is None: continue
                ids = [i for i in G.nodes_near(e['o'][0], e['o'][1], e['o'][2] - 8.0, 120.0, 80.0) if nav[i]]
                d_ = min((dd[i] for i in ids), default=np.inf)
                broute.setdefault(l, {})[tg] = round(float(d_)) if np.isfinite(d_) else None
                if not np.isfinite(d_): lost.append('%s -> %s' % (tg, l.upper()))
                elif not any(back[i] for i in ids): lost.append('%s -> %s (no way back)' % (tg, l.upper()))
                walk_ = res.get('1b', {}).get('routes', {}).get(l, {}).get(tg)
                if walk_ and np.isfinite(d_) and d_ > NAV_DETOUR * walk_: detour.append('%s -> %s nav %d vs walk %d' % (tg, l.upper(), d_, walk_))
        res['9'].update(nav_cells=ne['cells'], nav_m2=ne['area_m2'], nav_areas_est=ne['areas'], unmarked_cells=ne['unmarked_cells'], stations_off_nav=need,
                        waypoints_off_nav=wp_off, bot_routes=broute, bot_routes_lost=lost, bot_detours=detour, nav_plan=bool(nav_plan))
        print('    bot routes on the nav (base spawns -> flag, CT / T): ' + ', '.join('%s %s / %s' % (l.upper(), v.get('ct'), v.get('t')) for l, v in broute.items()))
        print('    stations off the nav: %d%s; waypoints off the nav: %s' % (len(need), (' ' + ', '.join(need[:12])) if need else '', ', '.join(wp_off) or 'none'))
        for x_ in lost: print('    bots cannot route', x_)
        if need or lost: fails.append('nav')
        if detour: warn.append('bot nav detours over %.2f x the walking route: %s' % (NAV_DETOUR, '; '.join(detour)))
        if ne['areas'] and ne['areas'] > NAV_TARGET: warn.append('nav estimate ~%d areas (target under %d)' % (ne['areas'], NAV_TARGET))

    res['fails'] = fails; res['warnings'] = warn
    for w in warn: print('WARNING ' + w)
    json.dump(res, open(out_json or os.path.join(OUT, 'check_play.json'), 'w'), indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
    print('RESULT: %s  (%.0f s)' % ('clean (9 checks)' if not fails else 'FAILED: ' + ', '.join(fails), time.time() - t0))
    return 1 if fails else 0


_TT = None


def mesh_z(x, y):
    """height of the terrain MESH at a point (bilinear in its tile cell: the tiles are 32 / 64 / 128-u grids of layout.height)"""
    global _TT
    if _TT is None:
        import vmapgen, mv_terrain
        _TT = vmapgen.Terrain(L.height, -L.TERRAIN_X, -L.TERRAIN_Y, L.TERRAIN_X, L.TERRAIN_Y, tile=512, res=mv_terrain.tile_res)
    T = _TT.tile; tx = int(math.floor(x / T) * T); ty = int(math.floor(y / T) * T)
    r = _TT.tiles.get((tx, ty))
    if r is None: return -1e9
    cx0 = tx + math.floor((x - tx) / r) * r; cy0 = ty + math.floor((y - ty) / r) * r
    z00, z10, z01, z11 = np.asarray(L.height(np.array([cx0, cx0 + r, cx0, cx0 + r], float), np.array([cy0, cy0, cy0 + r, cy0 + r], float)), float)
    u, v = (x - cx0) / r, (y - cy0) / r
    return float(z00 * (1 - u) * (1 - v) + z10 * u * (1 - v) + z01 * (1 - u) * v + z11 * u * v)


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


def _to_local(x, y, p):
    c, s = math.cos(math.radians(p['yaw'])), math.sin(math.radians(p['yaw']))
    dx, dy = x - p['o'][0], y - p['o'][1]
    return dx * c + dy * s, -dx * s + dy * c


def _cluster(pts, r):
    """greedy clusters of points: [(cx, cy, n)] largest first"""
    out = []
    for (x, y) in pts:
        for c in out:
            if math.hypot(c[0] / c[2] - x, c[1] / c[2] - y) < r: c[0] += x; c[1] += y; c[2] += 1; break
        else: out.append([x, y, 1])
    return sorted(((c[0] / c[2], c[1] / c[2], c[2]) for c in out), key=lambda c: -c[2])


if __name__ == '__main__':
    if len(sys.argv) < 2: print(__doc__); sys.exit(2)
    only = None; oj = None
    if '--only' in sys.argv: only = set(int(v) for v in sys.argv[sys.argv.index('--only') + 1].split(','))
    if '--json' in sys.argv: oj = sys.argv[sys.argv.index('--json') + 1]
    sys.exit(main(sys.argv[1], only, oj, '--verbose' in sys.argv, '--nav-plan' in sys.argv))
