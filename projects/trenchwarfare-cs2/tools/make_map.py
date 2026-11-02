"""Writes mg_trenchwarfare.vmap: terrain, trenches, no man's land, mortar pits, airfields, forest, lobby, lighting, fog,
script/HUD entities, teleports, clips and vis hints. Everything generated is in vis group "tw_gen"; re-running on a map
edited in Hammer replaces only that group.

usage: make_map.py <template_or_current.vmap> <out.vmap> <addon_content_out>
"""
import os, sys, json, math, copy
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__))
import dmx
from dmx import T_STRING, T_VEC3
import vmaplib
from vmaplib import ent
import vmesh
import layout as LY
from noise import fbm, hash01

SRC, OUTPATH, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
GROUP = 'tw_gen'
NAME = 'mg_trenchwarfare'
rng = np.random.RandomState(1916)

d = dmx.DMX.load(SRC)
root = d.root
world = root.get('world')
vmaplib.init(d, OUT)

# ---------------------------------------------------------------- Hammer edits to generated objects survive regeneration
# make_map.py <user vmap> <out> <addon> <previous generated vmap>: generated objects the user moved/edited/added are re-tagged "tw_user"
# (kept as they are), and the generated originals they replaced are skipped from now on (out/user_edits.json). Ladders follow the
# generator's rule instead (the user's ladder placement was adopted into it).
USER_GROUP = 'tw_user'
EDITS_JSON = os.path.join(os.path.dirname(__file__), '..', 'out', 'user_edits.json')


def obj_sig(c):
    if c.type == 'CMapEntity':
        ep = c.get('entity_properties')
        return json.dumps(['E', ep.get('classname') or '', ep.get('model') or '', [round(v, 1) for v in c.get('origin')], [round(v, 1) for v in c.get('angles')]])
    if c.type == 'CMapMesh':
        md = c.get('meshData'); o = np.array(c.get('origin') or (0, 0, 0), float)
        names = [a_[0] for a_ in md.attrs]
        mats = list(md.get('materials')) if 'materials' in names else []
        pos = None
        for st in md.get('vertexData').get('streams'):
            if st.get('semanticName') == 'position': pos = np.array(st.get('data'), float)
        bb = [] if pos is None or not len(pos) else np.round(np.concatenate([pos.min(0) + o, pos.max(0) + o]), 0).tolist()
        return json.dumps(['M', mats, bb, len(pos) if pos is not None else 0])
    return None


SKIP_SIGS = set(json.load(open(EDITS_JSON))) if os.path.exists(EDITS_JSON) else set()
if len(sys.argv) > 4:
    prev = [c for c in dmx.DMX.load(sys.argv[4]).root.get('world').get('children') if c.get('customVisGroup', '') == GROUP]
    mine = [c for c in world.get('children') if c.get('customVisGroup', '') == GROUP]
    # tolerant matching (Hammer re-saves floats and normalises angles): same class/model, origin within 0.75, angles within 1 degree
    def _ekey(c):
        ep = c.get('entity_properties'); return (ep.get('classname') or '', ep.get('model') or '')
    pool = {}
    for c in prev:
        if c.type == 'CMapEntity': pool.setdefault(_ekey(c), []).append(c)
    msig = {}
    for c in prev:
        if c.type == 'CMapMesh': msig.setdefault(obj_sig(c), []).append(c)
    used = set()
    def _adiff(a_, b_): return max(abs(((x_ - y_) + 180) % 360 - 180) for x_, y_ in zip(a_, b_))
    for c in mine:
        hit = None
        if c.type == 'CMapEntity':
            o = np.array(c.get('origin')); an = c.get('angles')
            for g_ in pool.get(_ekey(c), ()):
                if id(g_) in used: continue
                if np.abs(np.array(g_.get('origin')) - o).max() < 0.75 and _adiff(an, g_.get('angles')) < 1.0: hit = g_; break
        elif c.type == 'CMapMesh':
            for g_ in msig.get(obj_sig(c), ()):
                if id(g_) not in used: hit = g_; break
        if hit is not None: used.add(id(hit)); continue
        c.attr('customVisGroup')[2] = USER_GROUP
    SKIP_SIGS |= {obj_sig(g_) for g_ in prev if id(g_) not in used}
    json.dump(sorted(SKIP_SIGS), open(EDITS_JSON, 'w'), indent=0)
    print('user edits: %d kept as %s, %d generated objects replaced' % (sum(1 for c in world.get('children') if c.get('customVisGroup', '') == USER_GROUP), USER_GROUP, len(SKIP_SIGS)))

# ---------------------------------------------------------------- template entities to clone (full key sets)
TPL = {}
for c in world.get('children'):
    if c.type == 'CMapEntity':
        cls = c.get('entity_properties').get('classname')
        TPL.setdefault(cls, c)


def clone(cls, origin, angles=(0, 0, 0), **keys):
    e = ent(cls, origin, angles, group=GROUP)
    if cls in TPL:
        src = TPL[cls].get('entity_properties')
        props = e.get('entity_properties')
        have = {a[0] for a in props.attrs}
        for a in src.attrs:
            if a[0] not in have and a[0] != 'targetname': props.attrs.append([a[0], a[1], a[2]])
        for k, v in keys.items():
            props.set(k, T_STRING, str(v))
    return e


def setscale(e, s):
    e.attr('scales')[2] = tuple(float(x) for x in s)


MATS = dict(
    mud_wet='materials/de_ancient/hr_ancient_ground_mud_03_wet.vmat', mud2='materials/de_ancient/hr_ancient_ground_mud_01_wet.vmat',
    mud_base='materials/de_ancient/hr_ancient_ground_mud_03_base.vmat', dirt2='materials/de_ancient/hr_ancient_ground_dirt_02_wet.vmat',
    dirt3='materials/de_ancient/hr_ancient_ground_dirt_03_wet.vmat', dirt1='materials/de_ancient/hr_ancient_ground_dirt_01_base.vmat',
    dirt4='materials/de_ancient/hr_ancient_ground_dirt_04_base.vmat', grass1='materials/de_ancient/hr_ancient_ground_grass_01_base.vmat',
    grass2='materials/de_ancient/hr_ancient_ground_grass_02_wet.vmat', moss='materials/de_ancient/hr_ancient_ground_moss_02_base.vmat',
    grassw='materials/de_ancient/hr_ancient_ground_grass_01_wet.vmat')
NODRAW = 'materials/tools/toolsnodraw.vmat'; PCLIP = 'materials/tools/toolsplayerclip.vmat'; SKY = 'materials/tools/toolsskybox.vmat'
WATER = 'materials/de_aztec/hr_aztec/hr_aztec_water_shallow.vmat'
for m in MATS.values(): vmesh.TEX_SIZE[m] = (1024, 1024)


BLEND_BATTLE = 'materials/de_ancient/hr_ancient_blend_groundmud03-groundgrass_01_wet.vmat'   # A mud, B grass
BLEND_FOREST = 'materials/de_ancient/hr_ancient_blend_groundgrass01-grounddirt01-wet.vmat'    # A grass, B dirt
for m in (BLEND_BATTLE, BLEND_FOREST): vmesh.TEX_SIZE[m] = (1024, 1024)


def in_battle(x, y):
    return (abs(x) < 4096) & (abs(y) < 4608)


# ---------------------------------------------------------------- standing water in the trenches (planned before the terrain so the floor can look wet)
from scipy import ndimage as _ndi
POOLS = []                      # (side, mask (bool, CT raster 8u), level, x0, y0) per pool
WET = {}                        # side -> wetness raster (CT coords, 8u)
WET_IN, WET_FL = {}, {}
def _plan_pools():
    R_ = LY.raster()
    rs = 16.0
    xs = np.arange(LY.RX0, LY.RX1, rs) + rs / 2; ys = np.arange(LY.RY0, LY.RY1, rs) + rs / 2
    X, Y = np.meshgrid(xs, ys, indexing='ij')
    d, _ = R_.sample(X, Y)
    inside = d < -1.0
    prng = np.random.RandomState(77)
    for s_ in (-1, 1):
        fl = LY.ground_low(s_ * X, Y) - LY.DEPTH
        wet = np.zeros(X.shape)
        segs = [sg for sg in LY.segments() if sg[2] in ('fire', 'support', 'comm')]
        made = 0; tries = 0
        while made < 11 and tries < 200:
            tries += 1
            a_, b_, kind = segs[prng.randint(len(segs))]
            t = prng.rand()
            cx, cy = a_[0] + (b_[0] - a_[0]) * t, a_[1] + (b_[1] - a_[1]) * t
            i, j = int((cx - LY.RX0) / rs), int((cy - LY.RY0) / rs)
            if not inside[i, j]: continue
            lvl = fl[i, j] + prng.uniform(1.6, 3.6)
            for _ in range(12):
                lab, _n = _ndi.label(inside & (fl < lvl))
                reg = lab == lab[i, j]
                ii, jj = np.nonzero(reg)
                span = max(ii.max() - ii.min(), jj.max() - jj.min()) * rs
                if span < 900: break
                lvl -= 0.4
            if lab[i, j] == 0 or reg.sum() < 12: continue
            # ankle deep at most, and never on top of another pool (two sheets would z-fight)
            if lvl - fl[reg].min() > 5.0: continue
            if any(p_[0] == s_ and (p_[1] & _ndi.binary_dilation(reg, iterations=3)).any() for p_ in POOLS): continue
            POOLS.append((s_, reg, lvl))
            near = _ndi.binary_dilation(reg, iterations=2)
            wet = np.maximum(wet, near * np.clip((lvl + 3.0 - fl) / 3.0, 0, 1))
            made += 1
        WET[s_] = (wet, xs[0], ys[0], rs); WET_IN[s_] = inside; WET_FL[s_] = fl
_plan_pools()

# ---------------------------------------------------------------- mine tunnels (layout.tunnels): floor/ceiling heights, terrain cut
TUN = LY.tunnels()
def tun_in(x, y, strict=True):
    for (x0, y0, x1, y1, k) in TUN:
        if (x0 < x < x1 and y0 < y < y1) if strict else (x0 <= x <= x1 and y0 <= y <= y1): return k
    return None
def tun_floor(x, y):
    ax = abs(x)
    if LY.TUN_SAP_X[0] <= ax <= LY.TUN_SAP_X[1] and y >= LY.TUN_SAP_Y:
        top = float(LY.ground_low(np.array([math.copysign(LY.TUN_SAP_XC, x)]), np.array([LY.TUN_PORTAL_Y + 24]))[0]) - LY.DEPTH - 12.0
        t = (y - LY.TUN_SAP_Y) / (LY.TUN_PORTAL_Y - LY.TUN_SAP_Y)
        return LY.TUN_FLOOR + t * (top - LY.TUN_FLOOR)
    if abs(x) <= 176 and -3536 <= y <= -3200: return LY.TUN_FLOOR - 6.0
    return LY.TUN_FLOOR + 2.0 * float(fbm(np.array([x / 300.0]), np.array([y / 300.0]), 2.2, 2, seed=61)[0])
def tun_ceil(x, y):
    k = tun_in(x, y, strict=False)
    h = 128.0 if (abs(x) <= 176 and -3536 <= y <= -3200) else 108.0 if (LY.TUN_LANDING[0] <= abs(x) <= LY.TUN_LANDING[2] and LY.TUN_LANDING[1] <= y <= LY.TUN_LANDING[3]) else 92.0
    g = float(LY.ground_low(np.array([x]), np.array([y]))[0])
    return min(tun_floor(x, y) + h, g - 6.0)
def tun_cut(CX, CY, r):
    """terrain cells to drop: inside the sap footprint where any corner of the terrain cell dips below the tunnel roof
    (the parapet layer above covers the opening)"""
    out = np.zeros(CX.shape, bool)
    for (x0, y0, x1, y1, k) in TUN:
        if k != 'sap': continue
        m = (CX > x0) & (CX < x1) & (CY > y0) & (CY < y1)
        if not m.any(): continue
        lo = np.full(m.sum(), 1e9)
        for dx in (-r / 2, r / 2):
            for dy in (-r / 2, r / 2):
                lo = np.minimum(lo, LY.height(CX[m] + dx, CY[m] + dy))
        out[m] = lo < np.array([tun_ceil(x_, y_) for x_, y_ in zip(CX[m], CY[m])]) + 2.0
    return out


def wet_at(X, Y):
    """0..1 wetness of the trench floor around standing water"""
    out = np.zeros(np.shape(X))
    for s_, (wet, x0, y0, rs) in WET.items():
        cx = s_ * np.asarray(X, float)
        fi = (cx - x0) / rs; fj = (np.asarray(Y, float) - y0) / rs
        ok = (fi >= 0) & (fi < wet.shape[0] - 1) & (fj >= 0) & (fj < wet.shape[1] - 1)
        v = _ndi.map_coordinates(wet, [np.clip(fi, 0, wet.shape[0] - 1), np.clip(fj, 0, wet.shape[1] - 1)], order=1)
        out = np.maximum(out, np.where(ok, v, 0))
    return out


def terrain_paint(X, Y, Z, D=None):
    """per-vertex blend weight (x channel) and tint; battle zone: 0 mud -> 1 grass, forest: 0 grass -> 1 dirt"""
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    ax, ay = np.abs(X), np.abs(Y)
    n1 = fbm(X / 900.0, Y / 900.0, 0.3, 4, seed=21); n2 = fbm(X / 220.0, Y / 220.0, 1.3, 3, seed=22)
    # distance outside the churned core (no man's land + trenches + mortar line)
    dx = np.maximum(ax - 2500, 0); dy = np.maximum(ay - 3350, 0)
    core = np.sqrt(dx ** 2 + dy ** 2)
    pits = np.full(X.shape, 1e9)
    for s in (-1, 1):
        for my in LY.MORTAR_Y:
            pits = np.minimum(pits, np.hypot(X - s * LY.MORTAR_X, Y - my))
    g = np.clip(core / 1100.0 + 0.35 * n1 + 0.15 * n2, 0, 1)
    g = g * np.clip((pits - 180) / 300.0, 0, 1)
    g = np.where((ax > 3700) | (ay > 4300), np.maximum(g, np.clip(((np.maximum(ax - 3700, 0) + np.maximum(ay - 4300, 0)) / 300.0), 0, 1)), g)
    if D is not None: g = np.where(D < 48, 0.0, g)
    # forest: dirt patches and tracks, the airfield stays grass
    f = np.clip((n1 - 0.05) * 2.2 + 0.6 * n2, 0, 1)
    air = (ax > 4300) & (ax < 6950) & (ay < 1150)
    f = np.where(air, np.clip(0.25 * n2, 0, 1), f)
    f = np.where((ax < 4400) & (ay < 4900), np.minimum(f, np.clip(((np.maximum(ax - 4096, 0)) + np.maximum(ay - 4608, 0)) / 300.0, 0, 1)), f)
    w = np.where(in_battle(X, Y), g, f)
    t = np.clip(0.86 + 0.12 * n1 + 0.06 * n2, 0.7, 1.0)
    t = np.where(in_battle(X, Y) & (w < 0.3), t * 0.94, t)
    wt = wet_at(X, Y)
    t = t * (1 - 0.32 * wt)                      # dark, wet mud around standing water
    w = np.where(wt > 0.05, w * (1 - wt), w)
    paint = np.stack([w, np.zeros_like(w), np.full(w.shape, 0.35), np.zeros_like(w)], -1)
    tint = np.stack([t, t, t, np.ones_like(t)], -1)
    return paint, tint


# ---------------------------------------------------------------- terrain tiles (open sheets), crack-free LOD seams
TILE = 512
def tile_res(cx, cy):
    ax, ay = abs(cx), abs(cy)
    if ax - TILE / 2 < 2560 and ay - TILE / 2 < 3500: return 32
    for s in (-1, 1):
        for my in LY.MORTAR_Y:
            if abs(cx - s * LY.MORTAR_X) < 520 and abs(cy - my) < 520: return 32
    if ax - TILE / 2 < 4400 and ay - TILE / 2 < 4600: return 64
    return 128

tiles = {}
for tx in range(-LY.MAP_X, LY.MAP_X, TILE):
    for ty in range(-LY.MAP_Y, LY.MAP_Y, TILE):
        tiles[(tx, ty)] = tile_res(tx + TILE / 2, ty + TILE / 2)

nquads = 0
for (tx, ty), r in tiles.items():
    n = TILE // r
    xs = tx + np.arange(n + 1) * r; ys = ty + np.arange(n + 1) * r
    X, Y = np.meshgrid(xs.astype(float), ys.astype(float), indexing='ij')
    Z = LY.height(X, Y)
    # match coarser neighbours along the shared edge (linear between their vertices)
    for (dx, dy, edge) in ((-1, 0, 'x0'), (1, 0, 'x1'), (0, -1, 'y0'), (0, 1, 'y1')):
        nb = tiles.get((tx + dx * TILE, ty + dy * TILE))
        if nb is None or nb <= r: continue
        k = nb // r
        if edge in ('x0', 'x1'):
            i = 0 if edge == 'x0' else n
            col = Z[i].copy()
            for j in range(n + 1):
                j0 = (j // k) * k; j1 = min(j0 + k, n); t = (j - j0) / k if j1 > j0 else 0
                col[j] = Z[i, j0] * (1 - t) + Z[i, j1] * t
            Z[i] = col
        else:
            j = 0 if edge == 'y0' else n
            row = Z[:, j].copy()
            for i in range(n + 1):
                i0 = (i // k) * k; i1 = min(i0 + k, n); t = (i - i0) / k if i1 > i0 else 0
                row[i] = Z[i0, j] * (1 - t) + Z[i1, j] * t
            Z[:, j] = row
    dd, _ = LY.trench_dist(X, Y)
    PA, TI = terrain_paint(X, Y, Z, dd)
    def fm(i, j, X=X, Y=Y):
        cx = (X[i, j] + X[i + 1, j + 1]) / 2; cy = (Y[i, j] + Y[i + 1, j + 1]) / 2
        return BLEND_BATTLE if in_battle(cx, cy) else BLEND_FOREST
    CXc = (X[:-1, :-1] + X[1:, 1:]) / 2; CYc = (Y[:-1, :-1] + Y[1:, 1:]) / 2
    cut = tun_cut(CXc, CYc, r) if (abs(abs(tx + TILE / 2) - LY.TUN_SAP_XC) < 400 and abs(ty + TILE / 2 + 3000) < 400) else None
    verts, faces, mats, (pa, ti) = vmesh.grid_sheet(X, Y, Z, fm, valid=None if cut is None or not cut.any() else ~cut, vert_attr=(PA, TI))
    vmesh.mesh_node(vmesh.polymesh_open(verts, faces, mats, paint=pa, tint=ti), GROUP, bake=True, shadows=True)
    nquads += len(faces)
print('terrain: %d tiles, %d quads' % (len(tiles), nquads))


def surf_z(x, y, pad=24.0):
    """highest terrain-mesh vertex within pad of (x, y): spawn points sit above it so nobody starts inside the earth"""
    best = -1e9
    for qx in (x - pad, x, x + pad):
        for qy in (y - pad, y, y + pad):
            tx = int(math.floor(qx / TILE) * TILE); ty = int(math.floor(qy / TILE) * TILE)
            r = tiles.get((tx, ty))
            if r is None: continue
            x0 = tx + math.floor((qx - tx) / r) * r; y0 = ty + math.floor((qy - ty) / r) * r
            cx_ = np.array([x0, x0 + r, x0, x0 + r], float); cy_ = np.array([y0, y0, y0 + r, y0 + r], float)
            z00, z10, z01, z11 = LY.height(cx_, cy_)
            u, v = (qx - x0) / r, (qy - y0) / r
            zb = z00 * (1 - u) * (1 - v) + z10 * u * (1 - v) + z01 * (1 - u) * v + z11 * u * v
            best = max(best, float(zb) + 0.25 * float(max(z00, z10, z01, z11) - zb))   # quads are split either way
    return best

# ---------------------------------------------------------------- parapet / parados layer over the trench banks
def fix_pinches(valid):
    v = valid.copy()
    for _ in range(4):
        a = v[:-1, :-1]; b = v[1:, :-1]; c = v[:-1, 1:]; dd_ = v[1:, 1:]
        pinch1 = a & dd_ & ~b & ~c
        pinch2 = b & c & ~a & ~dd_
        if not (pinch1.any() or pinch2.any()): break
        ii, jj = np.nonzero(pinch1); v[ii + 1, jj] = True
        ii, jj = np.nonzero(pinch2); v[ii, jj] = True
    return v

pq = 0
for s in (-1, 1):
    for y0 in np.arange(LY.RY0, LY.RY1, 800):
        xs = np.arange(LY.RX0, LY.RX1 + 0.1, 16.0) * s
        ys = np.arange(y0, min(y0 + 800, LY.RY1) + 0.1, 16.0)
        X, Y = np.meshgrid(xs, ys, indexing='ij')
        Z, D = LY.parapet(X, Y)
        ok = (D >= 2) & (D <= 116)
        valid = ok[:-1, :-1] & ok[1:, :-1] & ok[:-1, 1:] & ok[1:, 1:]
        valid = fix_pinches(valid)
        if not valid.any(): continue
        if s < 0:
            # keep counter-clockwise faces when mirrored: flip the x order
            X = X[::-1]; Y = Y[::-1]; Z = Z[::-1]; valid = valid[::-1]
        n2 = fbm(X / 120.0, Y / 120.0, 2.0, 3, seed=23)
        PA = np.stack([np.clip(0.15 + 0.35 * n2, 0, 0.6), np.zeros_like(X), np.full(X.shape, 0.35), np.zeros_like(X)], -1)
        tt = np.clip(0.9 + 0.1 * n2, 0.75, 1.0); TI = np.stack([tt, tt, tt, np.ones_like(tt)], -1)
        verts, faces, mats, (pa, ti) = vmesh.grid_sheet(X, Y, Z, lambda i, j: BLEND_BATTLE, valid, vert_attr=(PA, TI))
        vmesh.mesh_node(vmesh.polymesh_open(verts, faces, mats, paint=pa, tint=ti), GROUP)
        pq += len(faces)
print('parapets: %d quads' % pq)

# ---------------------------------------------------------------- prop helper
props_placed = {}
import placer
PL = placer.Placer()
for _c in world.get('children'):          # the user's own placements are obstacles for generated dressing
    if _c.get('customVisGroup', '') == USER_GROUP and _c.type == 'CMapEntity' and (_c.get('entity_properties').get('model') or '').endswith('.vmdl'):
        _o = _c.get('origin'); PL.add(PL.footprint(_c.get('entity_properties').get('model'), _o[0], _o[1], _o[2], _c.get('angles')[1], tuple(_c.get('scales')), 0.0))
skipped = {}
PROBED_KEYS = ('tree', 'poplar', 'beech', 'maple', 'bush', 'shrub', 'dogwood', 'weed', 'grass', 'leaves', 'viburnum', 'fern', 'ivy',
               'wire_', 'cheval')
def probed(model, scale):
    """foliage, wire and small clutter are light-probed: they would add thousands of lightmap charts (bake charting time) for little gain"""
    if any(k in model for k in PROBED_KEYS): return True
    lo, hi = placer.bounds(model)
    return max((hi[i] - lo[i]) * abs(scale[i]) for i in range(3)) < 40.0
def prop(name, x, y, z, yaw=0.0, pitch=0.0, roll=0.0, scale=(1, 1, 1), stock=None, solid='6', shadows='0', reg=True, check=False, pad=0.0, **kw):
    """reg: record the footprint; check: only place if it touches nothing already recorded (returns None when skipped)"""
    model = stock or 'models/tw/%s/%s.vmdl' % (name, name)
    if reg or check:
        f = PL.footprint(model, x, y, z, yaw, scale, pad)
        if check and PL.hits(f):
            skipped[model] = skipped.get(model, 0) + 1
            return None
        if reg: PL.add(f)
    e = ent('prop_static', (x, y, z), (pitch, yaw, roll), group=GROUP, model=model, rendercolor='255 255 255', skin='default',
            solid=solid, bakelighting='0' if probed(model, scale) else '1', disableshadows=shadows, lodlevel='-1', baketoworld='0', rendertocubemaps='1', **kw)
    if tuple(scale) != (1, 1, 1): setscale(e, scale)
    props_placed[model] = props_placed.get(model, 0) + 1
    return e


EXT = lambda n: 'models/tw/ext/%s/%s.vmdl' % (n, n)


def yaw_for(nx, ny):
    """yaw so the prop's local +y points along -n (into the earth) given the wall's inward normal n"""
    return math.degrees(math.atan2(nx, -ny))


def gz(x, y):
    return LY.ground_at(x, y)


R = LY.raster()
WALLS = R.walls()
RECTS = LY.rects()
# woods skirmish exit: the north wall of the last fire-trench traverse (CT coords; mirrored for T)
_last = max((r_ for r_ in RECTS if r_[4] == 'fire'), key=lambda r_: (r_[3], -r_[0]))
EXIT_Y = float(_last[3]); EXIT_X = float((_last[0] + _last[2]) / 2); EXIT_W = 55.0

def kind_at(x, y):
    """trench kind containing CT-side point"""
    best = None
    for (x0, y0, x1, y1, k) in RECTS:
        if x0 <= x <= x1 and y0 <= y <= y1:
            if k == 'step': return 'step'
            best = best or k
    return best

# ---------------------------------------------------------------- trenches: revetments, fire-steps, duckboards, sandbags, clip
REVETS = ['revet_planks_a'] * 4 + ['revet_planks_b'] * 4 + ['revet_iron'] * 3 + ['revet_planks_broken'] * 2
for s in (-1, 1):
    for (p0, p1, n) in WALLS:
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        if L < 1: continue
        mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
        kin = kind_at(mid[0] + n[0] * 10, mid[1] + n[1] * 10) or 'fire'
        front = n[0] > 0.5            # CT: trench lies at +x of the wall -> earth toward no man's land
        g = float(LY.ground_low(np.array([s * mid[0]]), np.array([mid[1]]))[0])
        floor = g - LY.DEPTH
        top = g + (6 if front else 18)
        base = top - 96
        unit = 128.0 if L >= 96 else 64.0
        cnt = max(1, int(math.ceil(L / unit - 0.15)))
        sc = L / (cnt * unit)
        dx, dy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
        nx, ny = n[0] * s, n[1]
        yaw = yaw_for(nx, ny)
        portal_wall = abs(n[1]) > 0.5 and abs(p0[1] - LY.TUN_PORTAL_Y) < 8 and LY.TUN_SAP_X[0] - 8 <= min(p0[0], p1[0]) and max(p0[0], p1[0]) <= LY.TUN_SAP_X[1] + 8
        for k in range(cnt):
            t = (k + 0.5) * L / cnt
            px, py = p0[0] + dx * t, p0[1] + dy * t
            name = REVETS[rng.randint(len(REVETS))] + ('_128' if unit > 64 else '')
            if kin == 'niche': continue          # the shelter mound lines the niche
            if portal_wall: continue             # the mine sap opens here
            prop(name, s * px, py, base, yaw, scale=(sc * (1.0 + 0.01 * rng.rand()), 1, 1), shadows='0', reg=False)
            at_exit = abs(n[1]) > 0.5 and abs(p0[1] - EXIT_Y) < 8 and abs(px - EXIT_X) < unit / 2 + EXIT_W
            if kin in ('fire', 'step') and L >= 40 and (front or rng.rand() < 0.85) and not at_exit:     # no sandbag scraps on corner stubs
                if unit > 64: sb = 'sandbag_low_128' if front else 'sandbag_wall_128'
                else: sb = 'sandbag_low' if front else ['sandbag_wall_a', 'sandbag_wall_b', 'sandbag_wall_c'][rng.randint(3)]
                prop(sb, s * px - nx * 1.0, py - ny * 1.0, top + 0.5 - (1.5 if front else 0), yaw + rng.uniform(-1.5, 1.5), scale=(sc, 1, 1), reg=False)
        # player clip: a 4-unit slab behind the wall face, from fire-step height up
        cx0, cy0, cx1, cy1 = sorted((p0[0], p1[0])) + sorted((p0[1], p1[1]))
        cx0, cx1 = sorted((p0[0], p1[0])); cy0, cy1 = sorted((p0[1], p1[1]))
        if abs(n[0]) > 0.5:
            xa = p0[0] - n[0] * 4 if n[0] > 0 else p0[0]; xb = p0[0] if n[0] > 0 else p0[0] - n[0] * 4
            box = (xa, cy0, xb, cy1)
        else:
            ya = p0[1] - n[1] * 4 if n[1] > 0 else p0[1]; yb = p0[1] if n[1] > 0 else p0[1] - n[1] * 4
            box = (cx0, ya, cx1, yb)
        boxes = [] if portal_wall else [box]
        if abs(n[1]) > 0.5 and abs(p0[1] - EXIT_Y) < 8 and box[0] < EXIT_X < box[2]:      # gap over the skirmish ladder
            boxes = [b_ for b_ in ((box[0], box[1], EXIT_X - EXIT_W, box[3]), (EXIT_X + EXIT_W, box[1], box[2], box[3])) if b_[2] - b_[0] > 1]
        for (bx0, by0, bx1, by1) in boxes:
            if s < 0: bx0, bx1 = -bx1, -bx0
            vmesh.mesh_node(vmesh.box_mesh(bx0, by0, floor + 38, bx1, by1, g + 110, PCLIP), GROUP, bake=False, shadows=False, visexclude=True)
    # fire-steps
    for (xw, ya, yb) in LY.firesteps():
        L = yb - ya; cnt = max(1, int(round(L / 64.0))); sc = L / (cnt * 64.0)
        g = float(LY.ground_low(np.array([s * xw]), np.array([(ya + yb) / 2]))[0])
        for k in range(cnt):
            y = ya + (k + 0.5) * L / cnt
            prop('firestep', s * xw, y, g - LY.DEPTH, yaw_for(1 * s, 0), scale=(sc, 1, 1))
    # duckboards along the centre lines
    for (a, b, kind) in LY.segments():
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 8: continue
        dx, dy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        yaw = math.degrees(math.atan2(dy, dx * s))
        unit = 128.0 if L >= 96 else 64.0
        cnt = max(1, int(round(L / unit)))
        for k in range(cnt):
            t = (k + 0.5) * L / cnt
            x, y = a[0] + dx * t, a[1] + dy * t
            if kind == 'niche': continue
            g = float(LY.ground_low(np.array([s * x]), np.array([y]))[0])
            prop('duckboard_128' if unit > 64 else 'duckboard', s * x, y, g - LY.DEPTH - 0.5, yaw + rng.uniform(-2, 2), scale=(L / (cnt * unit), 1, 1), reg=False)
    # heal shelters (elephant iron) in the niches, with dressing station dressing
    for k, y in enumerate(LY.SHELTER_Y):
        xs_ = LY.XS + LY.HW + 4 + 48          # arch mouth 4 units clear of the support trench
        g = float(LY.ground_low(np.array([s * xs_]), np.array([y]))[0])
        prop('shelter', s * xs_, y, g - LY.DEPTH, 0 if s > 0 else 180, reg=False)
        prop('crate_medical', s * (xs_ + 30), y, g - LY.DEPTH, rng.uniform(-2, 2))
        prop('stretcher', s * (xs_ - 3), y - 30, g - LY.DEPTH + 0.5, rng.uniform(-2, 2))
        # candle on the medical crate and a warm baked light under the arch
        prop(None, s * (xs_ + 30), y + rng.uniform(-6, 6), g - LY.DEPTH + 18.6, rng.uniform(0, 360),
             stock='models/props/de_ancient/ancient_lighting/ancient_lighting_candle_cluster_01_lit.vmdl', solid='0')
        ent('light_omni2', (s * (xs_ + 10), y, g - LY.DEPTH + 34), (90, 0, 0), group=GROUP, brightness_units='1', brightness_lumens='700', brightness='1',
            color='255 176 96', range='260', directlight='3', castshadows='1', colormode='0', enabled='1', bouncescale='1.0', shape='0')
    # trench signs: posts set hard against the revetment, the painted face turned to the walkway
    def wall_sign(name, x, y, reach=140.0):
        best = None
        for (p0, p1, n) in WALLS:
            L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
            if L < 60: continue
            mx, my = (p0[0] + p1[0]) / 2 + n[0] * 10, (p0[1] + p1[1]) / 2 + n[1] * 10
            if kind_at(mx, my) in ('niche', None): continue
            ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
            t = min(max((x - p0[0]) * ux + (y - p0[1]) * uy, 26.0), L - 26.0)
            wx, wy = p0[0] + ux * t, p0[1] + uy * t
            d = math.hypot(wx - x, wy - y)
            if d < reach and (best is None or d < best[0]): best = (d, wx, wy, n)
        if best is None: return None
        _, wx, wy, n = best
        px, py = wx + n[0] * 3.8, wy + n[1] * 3.8
        yaw = math.degrees(math.atan2(n[1], n[0] * s)) + 90
        return prop(name, s * px, py, float(LY.ground_low(np.array([s * px]), np.array([py]))[0]) - LY.DEPTH, yaw, check=True)
    for k, y in enumerate(LY.SHELTER_Y):
        wall_sign('sign_dressing_gb' if s > 0 else 'sign_dressing_de', LY.XS + 34, y + 60)
    for k, y in enumerate(LY.COMM_Y):
        wall_sign('sign_mortars_gb' if s > 0 else 'sign_mortars_de', LY.XB + 30, y + 40)
        wall_sign('sign_firetrench_gb' if s > 0 else 'sign_firetrench_de', LY.XS - 30, y + 100)
    wall_sign('sign_piccadilly' if s > 0 else 'sign_unter_den_linden', LY.XS - 30, -60)
    # ---- trench dressing: everything stands against a wall, leaves a clear walkway, touches nothing else
    def floor(x, y):
        return float(LY.ground_low(np.array([x]), np.array([y]))[0]) - LY.DEPTH
    def at_wall(model, cx, cy, ux, uy, nx_, ny_, t, side, inset=5.0, yaw_off=0.0, lean=None, dz=0.0, z=None, pad=1.5):
        """place model with its long axis along the trench (u), its back `inset` off the wall on `side`"""
        lo, hi = placer.bounds(model)
        long_x = (hi[0] - lo[0]) >= (hi[1] - lo[1])
        depth = (hi[1] - lo[1]) if long_x else (hi[0] - lo[0])
        off = LY.HW - inset - depth / 2
        px, py = cx + ux * t + nx_ * side * off, cy + uy * t + ny_ * side * off
        yaw = math.degrees(math.atan2(uy, ux * s)) + (0 if long_x else 90) + yaw_off
        # the back must be near a wall and the front well inside the trench (raster check in CT coords)
        # back corners: inside, and earth a few units further; front corners: well inside (exact rect test)
        for e in (-1, 1):
            ex, ey = ux * e * half_len(model), uy * e * half_len(model)
            back = (px + ex + nx_ * side * (depth / 2), py + ey + ny_ * side * (depth / 2))
            wall = (px + ex + nx_ * side * (depth / 2 + inset + 3), py + ey + ny_ * side * (depth / 2 + inset + 3))
            front = (px + ex - nx_ * side * (depth / 2 + 30), py + ey - ny_ * side * (depth / 2 + 30))
            if not (in_trench(*back) and not in_trench(*wall) and in_trench(*front)): return None
        zz = floor(s * px, py) + dz if z is None else z
        return prop(None, s * px, py, zz, yaw, *(lean or (0, 0)), stock=model, solid='6', check=True, pad=pad)
    TW = lambda n: 'models/tw/%s/%s.vmdl' % (n, n)
    RECTS_ = [r_ for r_ in LY.rects()]
    def in_trench(x, y):
        return any(x0 <= x <= x1 and y0 <= y <= y1 for (x0, y0, x1, y1, k) in RECTS_)
    def half_len(model):
        lo, hi = placer.bounds(model)
        return max(hi[0] - lo[0], hi[1] - lo[1]) / 2
    nat = 'gb' if s > 0 else 'de'
    BAY = [(TW('tl_bucket'), 3), (TW('tl_tins'), 3), (TW('crate_long' if s > 0 else 'crate_german'), 2), (TW('crate_shells'), 1), (TW('tl_bagpile'), 2),
           (TW('tl_tools'), 2), (TW('tl_bench'), 1), (TW('casings'), 1), (EXT('field_telephone'), 1), (TW('helmet_brodie' if s > 0 else 'helmet_stahl'), 1),
           (TW('tl_barrel'), 1)]
    SUP = [(TW('tl_barrel'), 3), (TW('tl_planks'), 2), (TW('tl_wirereel'), 2), (TW('crate_shells'), 2), (TW('crate_long' if s > 0 else 'crate_german'), 2),
           (TW('tl_bench'), 2), (TW('tl_brazier'), 1), (TW('tl_bagpile'), 2), (TW('tl_bucket'), 2), (EXT('petrol_can'), 1), (TW('tl_tools'), 1)]
    def pick(lst):
        w = np.array([q[1] for q in lst], float); return lst[rng.choice(len(lst), p=w / w.sum())][0]
    # ladders first (over-the-top ladders lean on the parapet, standing on the fire-step), then periscopes on the step
    for i in range(LY.NBAY):
        ya = LY.Y0 + i * LY.P
        xw = LY.XF - LY.HW - LY.STEP_D
        if rng.rand() < 0.45:
            y = ya + rng.uniform(40, 216)
            prop('ladder', s * (xw + 49), y, floor(s * LY.XF, y) - 7.0, 0 if s > 0 else 180, pitch=-29, check=True)
        if rng.rand() < 0.4:
            y = ya + rng.uniform(30, 226)
            prop('tl_periscope', s * (xw + 6), y, floor(s * LY.XF, y) + 41.2, 0 if s > 0 else 180, check=True)
        for _ in range(rng.randint(0, 3)):
            y = ya + rng.uniform(20, 236)
            prop(['tl_tins', 'casings', 'helmet_brodie' if s > 0 else 'helmet_stahl'][rng.randint(3)], s * (xw + rng.uniform(10, 22)), y,
                 floor(s * LY.XF, y) + 41.2, rng.uniform(0, 360), check=True)
    nb = 0
    for (a, b, kind) in LY.segments():
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if kind == 'niche' or L < 150: continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        nx_, ny_ = -uy, ux
        sides = (1, -1)
        if kind == 'fire':      # never block the fire-step side
            sides = tuple(sd for sd in (1, -1) if nx_ * sd > 0.5) or (1, -1)
        lst = BAY if kind == 'fire' else SUP
        dens = {'fire': 1 / 95.0, 'support': 1 / 120.0, 'comm': 1 / 260.0}[kind]
        n = int(L * dens * rng.uniform(0.7, 1.3))
        for _ in range(n):
            t = rng.uniform(70, L - 70)
            side = sides[rng.randint(len(sides))]
            m = pick(lst)
            lean = None
            if 'tl_tools' in m: lean = (0, 0)
            if at_wall(m, a[0], a[1], ux, uy, nx_, ny_, t, side, inset=5.5 if 'tl_tools' not in m else 3.0) is not None: nb += 1
        # gas-alarm gongs at the ends of long runs
        if kind in ('fire', 'support') and rng.rand() < 0.35:
            at_wall(TW('tl_gong'), a[0], a[1], ux, uy, nx_, ny_, rng.uniform(80, L - 80), sides[0], inset=4.0)
    # lanterns on top of barrels / crates in the support trench
    for f in list(PL.items):
        if f['model'] in (TW('tl_barrel'), TW('crate_long'), TW('crate_german'), TW('crate_shells')) and rng.rand() < 0.3 and abs(f['c'][0]) > LY.XS - 120:
            prop('tl_lantern', f['c'][0] + rng.uniform(-3, 3), f['c'][1] + rng.uniform(-3, 3), f['z'][1], rng.uniform(0, 360), check=True, reg=True)
    print('trench dressing: %d pieces (side %d)' % (nb, s))
# standing water: flat sheets at each pool's level over its region (grown a little; the floor hides the shoreline)
nwp = 0; nfloat = 0
for (s_, reg, lvl) in POOLS:
    wet, x0, y0, rs = WET[s_]
    # one cell past the shoreline so the sheet ends inside the rising floor - except next to a separate (dry) basin lower than the water,
    # where the sheet stops at the shore cell instead of hanging over the dip
    inside_ = WET_IN[s_]; flg = WET_FL[s_]
    ring1 = _ndi.binary_dilation(reg, iterations=1) & ~reg & inside_
    other = inside_ & (flg < lvl) & ~reg
    grow = reg | (ring1 & ~_ndi.binary_dilation(other, iterations=1))
    ring = _ndi.binary_dilation(grow, iterations=1) & ~grow & inside_
    nfloat += int((ring & (flg < lvl - 0.05)).sum())
    ii, jj = np.nonzero(grow)
    i0, i1, j0, j1 = ii.min(), ii.max() + 1, jj.min(), jj.max() + 1
    xs_ = x0 - rs / 2 + np.arange(i0, i1 + 1) * rs; ys_ = y0 - rs / 2 + np.arange(j0, j1 + 1) * rs
    if s_ < 0: xs_ = -xs_[::-1]
    Xw, Yw = np.meshgrid(xs_, ys_, indexing='ij')
    valid = grow[i0:i1, j0:j1]
    if s_ < 0: valid = valid[::-1]
    valid = fix_pinches(valid)
    verts, faces, mats = vmesh.grid_sheet(Xw, Yw, np.full(Xw.shape, lvl), lambda i, j: WATER, valid)
    if faces:
        vmesh.mesh_node(vmesh.polymesh_open(verts, faces, mats), GROUP, bake=False, shadows=False)
        nwp += 1
print('trench water: %d pools, %d rim cells below the water' % (nwp, nfloat))
print('skipped (no room):', {k.split('/')[-1]: v for k, v in sorted(skipped.items(), key=lambda kv: -kv[1])[:12]})
print('trenches: %d walls per side' % len(WALLS))

# ---------------------------------------------------------------- no man's land
def free(x, y, r=90):
    d_, _ = LY.trench_dist(np.array([x]), np.array([y]))
    return d_[0] > r

for s in (-1, 1):
    # wire belts: a fence line and a coil line in front of each fire trench, with gaps cut by shellfire
    for (xw, kind, gap) in ((1390, 'fence', 0.16), (1235, 'coil', 0.25)):
        y = -3100.0
        while y < 3100:
            if rng.rand() > gap:
                x = xw + rng.uniform(-14, 14)
                name = (('wire_fence_a', 'wire_fence_b')[rng.randint(2)]) if kind == 'fence' else 'wire_coil'
                prop(name, s * x, y, gz(s * x, y) - 2, yaw_for(s, 0) + rng.uniform(-7, 7), solid='0')
            y += 128
    for k in range(9):
        x = rng.uniform(1050, 1460); y = rng.uniform(-3000, 3000)
        prop('cheval', s * x, y, gz(s * x, y) - 1, rng.uniform(0, 360), roll=rng.uniform(-6, 6), check=True, pad=4)
wrecks = [('wreck_tank', -380, 860, 34, 7, -5, -14), ('wreck_tank', 520, -1720, 205, -6, 4, -12),
          ('wreck_fieldgun', -880, -620, 300, 0, 7, -3), ('wreck_fieldgun', 1080, 2360, 140, 3, -9, -4),
          ('wreck_wheel', -840, -700, 20, 0, 0, -2), ('wreck_wheel', 300, 2900, 130, 0, 0, -2)]
for (nm, x, y, yaw, pitch, roll, sink) in wrecks:
    prop(nm, x, y, gz(x, y) + sink, yaw, pitch, roll)
# downloaded models (CC-BY, see CREDITS.txt): knocked-out tanks, guns, battlefield clutter
for (nm, x, y, yaw, pitch, roll, sink) in (('tank_a7v', 760, 1420, 70, 5, -7, -16), ('tank_renault_ft', -1040, -2350, 230, -6, 9, -10),
                                           ('gun_75mm', -2660, 900, 20, 0, 3, -3), ('howitzer_bl8', 2700, -2300, 160, 0, 0, -2)):
    prop(None, x, y, gz(x, y) + sink, yaw, pitch, roll, stock=EXT(nm))
scatter_ext = [('stump_burnt', 26, (0, 1500)), ('helmet_brodie_ext', 10, (200, 1450)), ('helmet_stahl_ext', 10, (200, 1450))]
for nm, n, xr in scatter_ext:
    for _ in range(n):
        x = rng.choice([-1, 1]) * rng.uniform(*xr); y = rng.uniform(-3300, 3300)
        if not free(x, y, 90): continue
        sc = rng.uniform(0.8, 1.3) if nm == 'stump_burnt' else 1.0
        prop(None, x, y, gz(x, y) - (6 if nm == 'stump_burnt' else 0.5), rng.uniform(0, 360), rng.uniform(-5, 5), rng.uniform(-5, 5), scale=(sc, sc, sc), stock=EXT(nm), check=True, pad=3)
TREES = ['tree_shattered_a', 'tree_shattered_b', 'tree_shattered_c', 'tree_shattered_d']
placed_pts = []
def scatter(n, xr, yr, names, min_d=110, mirror=True, zoff=-6, tilt=6, wall_clear=110, scale_r=(0.85, 1.2)):
    c = 0; tries = 0
    while c < n and tries < n * 40:
        tries += 1
        x = rng.uniform(*xr); y = rng.uniform(*yr)
        s = (1 if rng.rand() < 0.5 else -1) if mirror else 1
        x *= s
        if not free(x, y, wall_clear): continue
        if any((x - px) ** 2 + (y - py) ** 2 < min_d ** 2 for px, py in placed_pts[-400:]): continue
        sc = rng.uniform(*scale_r)
        if prop(names[rng.randint(len(names))], x, y, gz(x, y) + zoff, rng.uniform(0, 360), rng.uniform(-tilt, tilt), rng.uniform(-tilt, tilt), scale=(sc, sc, sc), check=True, pad=3) is None: continue
        placed_pts.append((x, y))
        c += 1
scatter(46, (0, 1500), (-3400, 3400), TREES, min_d=260)
scatter(70, (1450, 2700), (-3300, 3300), TREES + ['tree_shattered_c'], min_d=200)
scatter(150, (0, 2800), (-3500, 3500), ['stump_a', 'stump_b', 'stump_a'], min_d=120, zoff=-8)
scatter(24, (0, 2600), (-3400, 3400), ['log_fallen'], min_d=300, zoff=-4, tilt=3)
scatter(40, (0, 1450), (-3300, 3300), ['helmet_brodie', 'helmet_stahl'], min_d=60, zoff=-1, tilt=25, wall_clear=60, scale_r=(1, 1))
scatter(14, (0, 1450), (-3300, 3300), ['casings', 'shell_pile', 'crate_shells'], min_d=200, zoff=-2, tilt=8, scale_r=(1, 1))
# muddy water in the bigger craters of no man's land
nw = 0
for (cx, cy, r, dep) in sorted(LY.CRATERS.tolist(), key=lambda c: -c[2]):
    if abs(cx) > 1380 or r < 62 or nw >= 110: continue
    if not free(cx, cy, r + 40): continue
    xs = cx + np.linspace(-r * 0.5, r * 0.5, 9); ys = cy + np.linspace(-r * 0.5, r * 0.5, 9)
    Xg, Yg = np.meshgrid(xs, ys)
    hz = LY.height(Xg, Yg)
    wl = float(hz.min()) + dep * r * 0.28
    rr = r * 0.62
    pts = [(cx + math.cos(a) * rr * (1 + 0.15 * math.sin(a * 3 + cx)), cy + math.sin(a) * rr * (1 + 0.15 * math.cos(a * 2 + cy))) for a in np.linspace(0, 2 * math.pi, 13)[:-1]]
    top = [(px, py, wl) for px, py in pts]; bot = [(px, py, wl - 30) for px, py in pts]
    verts = top + bot; n = len(pts)
    faces = [list(range(n)), list(range(2 * n - 1, n - 1, -1))] + [[(k + 1) % n, k, k + n, (k + 1) % n + n] for k in range(n)]
    # top must face up: pts are counter-clockwise -> fine; sides face out
    fm = [WATER, NODRAW] + [NODRAW] * n
    vmesh.mesh_node(vmesh.polymesh_open(verts, faces, fm), GROUP, bake=True)
    nw += 1
print('no man\'s land: %d puddles' % nw)

# smoke: smouldering wrecks, a couple of burning craters, distant columns behind both lines
for (x, y) in ((-380, 860), (520, -1720), (760, 1420), (-1040, -2350)):
    ent('info_particle_system', (x, y, gz(x, y) + 70), group=GROUP, effect_name='particles/burning_fx/barrel_burning_engine_smoke_dark.vpcf', start_active='1')
for _ in range(3):
    x, y = rng.uniform(-900, 900), rng.uniform(-2800, 2800)
    ent('info_particle_system', (x, y, gz(x, y) + 4), group=GROUP, effect_name='particles/burning_fx/env_fire_small_smoke.vpcf', start_active='1')
for s_ in (-1, 1):
    for y in (-3900, -900, 2600):
        x = s_ * rng.uniform(6500, 6950); yy = y + rng.uniform(-400, 400)
        ent('info_particle_system', (x, yy, gz(x, yy) + 20), group=GROUP, effect_name='particles/ambient_fx/ambient_smokestack.vpcf', start_active='1')

# scattered metal debris across no man's land
DEB = ['models/de_cache_s2/debris/debris_kit_01a/debris_metal_01%s.vmdl' % c for c in 'abcdefgh']
for _ in range(70):
    x = rng.uniform(-1300, 1300); y = rng.uniform(-3300, 3300)
    if not free(x, y, 70): continue
    prop(None, x, y, gz(x, y) - 1, rng.uniform(0, 360), rng.uniform(-10, 10), rng.uniform(-10, 10), stock=DEB[rng.randint(len(DEB))], solid='0', check=True, pad=2)

# ---------------------------------------------------------------- mortar pits
for s in (-1, 1):
    for k, (cx, cy) in enumerate(LY.mortar_pits(s)):
        g = gz(cx + s * 150, cy)
        # breastwork: two courses of sandbag walls and a capping row, staggered, inner face ~185 from the tube
        NB = 17
        for lvl, (rad, dz, names) in enumerate(((194, -3, ['sandbag_wall_a', 'sandbag_wall_b', 'sandbag_wall_c']),
                                                 (192, 15.5, ['sandbag_wall_b', 'sandbag_wall_c', 'sandbag_wall_a']),
                                                 (190, 34.0, ['sandbag_low']))):
            for q in range(NB):
                a = 2 * math.pi * (q + 0.5 * (lvl % 2)) / NB + 0.04 * k
                rx, ry = math.cos(a), math.sin(a)
                x, y = cx + rx * rad, cy + ry * rad
                prop(names[rng.randint(len(names))], x, y, gz(cx + rx * 194, cy + ry * 194) + dz, math.degrees(math.atan2(-rx, ry)) + rng.uniform(-2, 2),
                     scale=(1.0, 1, 1 if lvl < 2 else 1.1))
        st = LY.mortar_stations(s, k)
        tx, ty = st['table']; ax, ay = st['ammo']
        if s > 0: prop(None, cx, cy, gz(cx, cy), 180, stock='models/tw/ext/mortar_58mm/mortar_58mm.vmdl')     # French 58 mm No.2
        else: prop('minenwerfer', cx, cy, gz(cx, cy) - 0.5, 0)                                                       # German 7.58 cm leMW
        prop('plotting_table', tx, ty, gz(tx, ty), 90 if s > 0 else 270)
        prop('ammo_box_mortar', ax, ay, gz(ax, ay), (90 if s > 0 else 270) + rng.uniform(-8, 8))
        # keep the crew's seats and the walks between table, ammo box and tube clear
        sa = (tx + s * 38, ty); sb = (ax + s * 44, ay)
        for (p0, p1) in ((sa, (cx, cy)), (sb, (cx, cy)), (sa, sb)):
            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2; Lr = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
            PL.add(dict(c=(mx, my), h=(Lr / 2, 22), a=math.atan2(p1[1] - p0[1], p1[0] - p0[0]), z=(gz(mx, my), gz(mx, my) + 72), model='reserve'))
        for p_ in (sa, sb):
            PL.add(dict(c=p_, h=(22, 22), a=0.0, z=(gz(*p_), gz(*p_) + 72), model='reserve'))
        # duckboard walk from the ammo box round to the table (under the reserved path, recorded after it)
        for (bx, by, byaw, scl) in ((cx + s * 112, cy - 8, 90, 1.25),):
            prop('duckboard', bx, by, gz(bx, by) - 0.5, byaw + rng.uniform(-3, 3), scale=(scl, 1, 1), reg=False)
        # bombs and stores along the breastwork, never on a walk
        placed = 0
        for j in range(40):
            if placed >= 6: break
            a_ = rng.uniform(0, 2 * math.pi); r_ = rng.uniform(140, 168)
            x, y = cx + math.cos(a_) * r_, cy + math.sin(a_) * r_
            nm = [None, None, 'crate_shells', 'shell_pile', 'casings', 'crate_german' if s < 0 else 'crate_long', 'tl_bucket', 'tl_tins'][rng.randint(8)]
            yaw_ = math.degrees(a_) + 90 + rng.uniform(-8, 8)
            if nm is None:
                ok = prop(None, x, y, gz(x, y), yaw_, stock='models/generic/ammo_artillery_01/ammo_artillery_small_0%s.vmdl' % ('1' if j % 2 else '1b'), check=True, pad=2)
            else:
                ok = prop(nm, x, y, gz(x, y), yaw_, check=True, pad=2)
            if ok is not None: placed += 1
        # crew enclosure
        h = 230; zb = gz(cx, cy) - 60; zt = zb + 220
        for (x0, y0, x1, y1) in ((cx - h, cy - h, cx + h, cy - h + 4), (cx - h, cy + h - 4, cx + h, cy + h), (cx - h, cy - h, cx - h + 4, cy + h), (cx + h - 4, cy - h, cx + h, cy + h)):
            vmesh.mesh_node(vmesh.box_mesh(x0, y0, zb, x1, y1, zt, PCLIP), GROUP, bake=False, shadows=False, visexclude=True)
        ent('info_target', (cx, cy, gz(cx, cy)), group=GROUP, targetname='mortarpit_%s_%d' % ('ct' if s > 0 else 't', k + 1))
        for tag, (px, py) in (('a', (tx + s * 38, ty)), ('b', (ax + s * 44, ay))):
            ang = (0, 180 if s > 0 else 0, 0)
            ent('info_teleport_destination', (px, py, surf_z(px, py, pad=16) + 8), ang, group=GROUP, targetname='mortarcrew_%s_%d_%s' % ('ct' if s > 0 else 't', k + 1, tag))
    prop('sign_mortars_gb' if s > 0 else 'sign_mortars_de', s * (LY.MORTAR_X - 260), -1200, gz(s * (LY.MORTAR_X - 260), -1200), 0 if s > 0 else 180)

# ---------------------------------------------------------------- airfields (biplanes later): hangar, signs, spawn markers

# propellers are separate models (tools/split_props.py) so the script can spin them; hub offsets from out/prop_hubs.json
PROP_HUB = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'prop_hubs.json')))
SK_ = np.random.RandomState(77)
def hub_at(pl, x, y, z, yaw):
    hx, hy, hz = PROP_HUB[pl]; c, s_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return x + hx * c - hy * s_, y + hx * s_ + hy * c, z + hz

for s in (-1, 1):
    hx = s * LY.HANGAR_X
    prop('hangar', hx, 0, gz(hx, 0) - 2, 0 if s > 0 else 180, reg=False)
    prop('sign_airfield_gb' if s > 0 else 'sign_airfield_de', s * (LY.HANGAR_X - 520), 420, gz(s * (LY.HANGAR_X - 520), 420), 0 if s > 0 else 180)
    for j in range(4):
        x, y = s * (LY.HANGAR_X + rng.uniform(-300, 300)), rng.choice([-1, 1]) * rng.uniform(380, 460)
        prop(['crate_long', 'crate_german', 'crate_shells'][rng.randint(3)], x, y, gz(x, y), rng.uniform(0, 360), check=True, pad=3)
    pl = 'plane_spad7' if s > 0 else 'plane_dr1'
    for j, (px, py) in enumerate(((s * (LY.HANGAR_X + 40), -150), (s * (LY.HANGAR_X - 120), 160))):
        yaw_ = (0 if s > 0 else 180) + rng.uniform(-6, 6)
        prop(None, px, py, gz(px, py), yaw_, stock='models/tw/ext/%s/%s.vmdl' % (pl, pl))
        hx, hy, hz = hub_at(pl, px, py, gz(px, py), yaw_)
        prop(None, hx, hy, hz, yaw_, roll=SK_.uniform(0, 180), stock='models/tw/ext/%s/%s_prop.vmdl' % (pl, pl), solid='0', reg=False)
    for j in range(5):
        x, y = s * (LY.HANGAR_X + rng.uniform(-340, 340)), rng.uniform(-280, 280)
        prop(None, x, y, gz(x, y), rng.uniform(0, 360), stock='models/tw/ext/petrol_can/petrol_can.vmdl', check=True, pad=3)
    # airfield stores: fuel drums, pallets, crates, a barrow
    for j in range(7):
        x, y = s * (LY.HANGAR_X + rng.uniform(-300, 300)), rng.choice([-1, 1]) * rng.uniform(420, 520)
        prop(None, x, y, gz(x, y), rng.uniform(0, 360), stock='models/generic/barrel_kit_01/barrel_0%d_a.vmdl' % (1 + rng.randint(3)), solid='6', check=True, pad=2)
    for j in range(3):
        x, y = s * (LY.HANGAR_X + rng.uniform(-250, 250)), rng.choice([-1, 1]) * rng.uniform(440, 520)
        yaw_ = rng.uniform(0, 360)
        if prop(None, x, y, gz(x, y), yaw_, stock='models/de_inferno/wood_pallet_01/inferno_pallet_wood_01.vmdl', solid='6', check=True, pad=3) is not None:
            prop(None, x, y, gz(x, y) + 6, yaw_ + rng.uniform(-10, 10), stock='models/generic/crate_wooden_01/crate_wooden_01_%s.vmdl' % 'abc'[j], solid='6')
    x, y = s * (LY.HANGAR_X - 430), 300
    prop(None, x, y, gz(x, y), rng.uniform(0, 360), stock='models/de_overpass/junk/wheelbarrow01a/wheelbarrow01a.vmdl', solid='6', check=True, pad=3)
    for k, y in enumerate(LY.SHELTER_Y):
        xs_ = LY.XS + LY.HW + 4 + 48
        prop(None, s * (xs_ - 3), y + 29, float(LY.ground_low(np.array([s * xs_]), np.array([y]))[0]) - LY.DEPTH + 0.5, rng.uniform(-2, 2), stock=EXT('stretcher_ext'), check=True)
    # flyable aircraft (prop_dynamic, script-flown): parked on the strip, noses (model +x) toward the front
    dyn = '%s_dyn' % pl
    src = os.path.join(OUT, 'models/tw/ext/%s/%s.vmdl' % (pl, pl))
    if os.path.exists(src):
        open(os.path.join(OUT, 'models/tw/ext/%s/%s.vmdl' % (pl, dyn)), 'w', newline='\n').write(
            open(src).read().replace('model_archetype = "static_prop_model"', 'model_archetype = ""'))
    for i, (px, py) in enumerate(LY.plane_spawns(s)):
        e = ent('prop_dynamic', (px - s * 60, py, gz(px - s * 60, py)), (0, 180 if s > 0 else 0, 0), group=GROUP, targetname='tw_plane_%s_%d' % ('ct' if s > 0 else 't', i + 1),
                model='models/tw/ext/%s/%s.vmdl' % (pl, dyn), solid='6', rendercolor='255 255 255', skin='default', DefaultAnim='', disableshadows='0',
                fademindist='-1', fademaxdist='0', StartDisabled='0', HoldAnimation='0', RandomAnimation='0')
        props_placed['models/tw/ext/%s/%s.vmdl' % (pl, dyn)] = 1
        tg = '%s_%d' % ('ct' if s > 0 else 't', i + 1)
        hx, hy, hz = hub_at(pl, px - s * 60, py, gz(px - s * 60, py), 180 if s > 0 else 0)
        ent('prop_dynamic', (hx, hy, hz), (0, 180 if s > 0 else 0, SK_.uniform(0, 180)), group=GROUP, targetname='tw_prop_' + tg,
            model='models/tw/ext/%s/%s_prop.vmdl' % (pl, pl), solid='0', rendercolor='255 255 255', skin='default', DefaultAnim='', disableshadows='0',
            fademindist='-1', fademaxdist='0', StartDisabled='0', HoldAnimation='0', RandomAnimation='0')
        props_placed['models/tw/ext/%s/%s_prop.vmdl' % (pl, pl)] = 1
        ent('info_particle_system', (px - s * 60, py, gz(px - s * 60, py) + 60), group=GROUP, targetname='tw_plane_smoke_' + tg, parentname='tw_plane_' + tg,
            effect_name='particles/burning_fx/barrel_burning_engine_smoke_dark.vpcf', start_active='0')
        for kind, snd in (('eng', 'tw.plane_engine'), ('gun', 'tw.plane_gun'), ('gun2', 'tw.plane_gun'), ('gun3', 'tw.plane_gun')):
            ent('point_soundevent', (px - s * 60, py, gz(px - s * 60, py) + 60), group=GROUP, targetname='tw_plane_%s_%s' % (kind, tg), soundName=snd,
                startOnSpawn='0', toLocalPlayer='0', stopOnNew='0', saveAndRestore='0')
        # script-driven effects, parked in the void until used: falling bombs, tracer streaks, bomb-sight ring, gun-sight pip
        fx_ = [('tw_bomb', 'tw_bomb_%s_%d' % (tg, k + 1)) for k in range(2)] + [('tw_tracer', 'tw_tracer_%s_%d' % (tg, k + 1)) for k in range(6)] + \
              [('tw_bombsight', 'tw_bombsight_' + tg), ('tw_gunsight', 'tw_gunsight_' + tg)]
        for m_, nm_ in fx_:
            ent('prop_dynamic', (px, py, -3600), (0, 0, 0), group=GROUP, targetname=nm_, model='models/tw/fx/%s/%s.vmdl' % (m_, m_), solid='0',
                rendercolor='255 255 255', skin='default', DefaultAnim='', disableshadows='1', fademindist='-1', fademaxdist='0',
                StartDisabled='0', HoldAnimation='0', RandomAnimation='0')
            props_placed['models/tw/fx/%s/%s.vmdl' % (m_, m_)] = 1
    for i, (px, py) in enumerate(LY.plane_spawns(s)):
        ent('info_teleport_destination', (px, py, surf_z(px, py) + 10), (0, 180 if s > 0 else 0, 0), group=GROUP, targetname='plane_%s_%d' % ('ct' if s > 0 else 't', i + 1))

# ---------------------------------------------------------------- living woodland (stock CS2 foliage) and undergrowth
FULL = ['models/foliage/trees/maple/maple_01/maple_tree_01.vmdl', 'models/foliage/trees/maple/maple_01/maple_tree_02.vmdl',
        'models/foliage/trees/poplar/tree_poplar_mature_01.vmdl', 'models/foliage/trees/poplar/tree_poplar_mature_02.vmdl',
        'models/foliage/trees/poplar/tree_poplar_adult_01.vmdl', 'models/foliage/trees/poplar/tree_poplar_adult_02.vmdl',
        'models/props/de_nuke/hr_nuke/foliage/tree_small_beech_01.vmdl', 'models/props/de_nuke/hr_nuke/foliage/tree_small_beech_03.vmdl',
        'models/props/de_nuke/hr_nuke/foliage/tree_small_beech_05.vmdl']
VISTA = ['models/foliage/trees/poplar/tree_poplar_mature_01_vista.vmdl', 'models/foliage/trees/poplar/tree_poplar_mature_02_vista.vmdl',
         'models/foliage/trees/poplar/tree_poplar_adult_01_vista.vmdl', 'models/foliage/trees/poplar/tree_poplar_adult_02_vista.vmdl']
BUSH = ['models/foliage/bushes/dogwood/dogwood_adult_01.vmdl', 'models/foliage/bushes/dogwood/shrub_dogwood_mature_01.vmdl',
        'models/foliage/bushes/dogwood/shrub_dogwood_juvenile_02.vmdl', 'models/props/de_nuke/hr_nuke/foliage/bushes_viburnum_01.vmdl']
WEED = ['models/props/de_nuke/hr_nuke/foliage/weed_cluster_01.vmdl', 'models/props/de_nuke/hr_nuke/foliage/weed_cluster_03.vmdl',
        'models/props/de_nuke/hr_nuke/foliage/tall_weeds_01.vmdl', 'models/foliage/weeds/ground_tall_grass_01a.vmdl',
        'models/foliage/weeds/ground_mid_grass_01a.vmdl', 'models/foliage/ground/ground_leaves_1.vmdl']


def woodland_ok(x, y):
    ax, ay = abs(x), abs(y)
    if ax < 3550 and ay < 3500: return False                    # battle zone (shattered trees only)
    if 4300 < ax < 6950 and ay < 1150: return False             # airfield clearing
    if abs(ax - LY.MORTAR_X) < 420 and ay < 2000: return False
    return True


def near_play(x, y):
    ax, ay = abs(x), abs(y)
    dx = max(0, ax - 3700); dy = max(0, ay - 3500)
    da = max(0, max(4200 - ax, ax - 7000, 0)) if ay < 1300 else 9999
    return min(math.hypot(dx, dy), da + max(0, ay - 1150))

nt = 0
grid = 230.0
for gx in np.arange(-LY.MAP_X + 100, LY.MAP_X - 100, grid):
    for gy in np.arange(-LY.MAP_Y + 100, LY.MAP_Y - 100, grid):
        x = gx + rng.uniform(-90, 90); y = gy + rng.uniform(-90, 90)
        if not woodland_ok(x, y): continue
        if fbm(x / 1500.0, y / 1500.0, 7.7, 2, seed=31) < -0.35: continue       # glades
        dp = near_play(x, y)
        sc = rng.uniform(0.85, 1.25)
        model = FULL[rng.randint(len(FULL))] if dp < 1400 else VISTA[rng.randint(len(VISTA))]
        prop(None, x, y, gz(x, y) - 4, rng.uniform(0, 360), scale=(sc, sc, sc), stock=model, shadows='0')
        nt += 1
        if dp < 1600 and rng.rand() < 0.45:
            bx, by = x + rng.uniform(-110, 110), y + rng.uniform(-110, 110)
            prop(None, bx, by, gz(bx, by) - 2, rng.uniform(0, 360), stock=BUSH[rng.randint(len(BUSH))], solid='0', check=True)
        if dp < 700 and rng.rand() < 0.6:
            for _ in range(1):
                wx, wy = x + rng.uniform(-115, 115), y + rng.uniform(-115, 115)
                prop(None, wx, wy, gz(wx, wy) - 1, rng.uniform(0, 360), stock=WEED[rng.randint(len(WEED))], solid="0", check=True)
# the battle zone's edge: a few surviving trees and lots of weeds between the mortar line and the trenches
for _ in range(160):
    x = rng.choice([-1, 1]) * rng.uniform(2650, 3550); y = rng.uniform(-3400, 3400)
    if abs(abs(x) - LY.MORTAR_X) < 360 and abs(y) < 2000: continue
    if rng.rand() < 0.3:
        prop(None, x, y, gz(x, y) - 4, rng.uniform(0, 360), stock=FULL[rng.choice([2, 3, 4, 5])], shadows='0')
    else:
        prop(None, x, y, gz(x, y) - 1, rng.uniform(0, 360), stock=WEED[rng.randint(len(WEED))], solid="0", check=True)
for _ in range(160):
    x = rng.choice([-1, 1]) * rng.uniform(1500, 3600); y = rng.uniform(-3500, 3500)
    if not free(x, y, 70): continue
    prop(None, x, y, gz(x, y) - 1, rng.uniform(0, 360), stock=WEED[rng.choice([0, 1, 2])], solid="0", check=True)
print('woodland: %d trees' % nt)

# ---------------------------------------------------------------- fog banks drifting over no man's land
# tw32: off - the fog sprites' overdraw cost the whole frame rate looking across (r_drawparticles 0 fixed it); the mist is height fog
# + volumetric fog now (env_cubemap_fog / tw_vfog below). The rng calls stay so nothing generated after this moves.
FOG_PARTICLES = False
for x in (-1024.0, 0.0, 1024.0):
    for y in np.arange(-3072, 3073, 1024.0):
        r_ = rng.uniform(-120, 120), rng.uniform(-120, 120)
        if x != 0.0 or abs(y) % 2048 != 1024: continue        # thinned: a few banks down the middle only (players must see across, with effort)
        if FOG_PARTICLES: ent('info_particle_system', (x + r_[0], y + r_[1], gz(x, y) - 20), group=GROUP,
            effect_name='particles/maps/gg_vietnam/vietnam_fog_volume_1024.vpcf', start_active='1')
for _ in range(30):
    x = rng.uniform(-1450, 1450); y = rng.uniform(-3300, 3300)
    if _ % 2: continue
    if FOG_PARTICLES: ent('info_particle_system', (x, y, gz(x, y) + 8), group=GROUP, effect_name='particles/maps/gg_vietnam/vietnam_fog_ground.vpcf', start_active='1')

# ---------------------------------------------------------------- infantry spawns (teleport destinations) and heal points
for s in (-1, 1):
    tag = 'ct' if s > 0 else 't'
    for i, (x, y) in enumerate(LY.infantry_spawns(s)):
        z = max(float(LY.ground_low(np.array([x]), np.array([y]))[0]) - LY.DEPTH + 4.5, surf_z(x, y, pad=16)) + 10   # duckboards top out ~4 above the floor
        ent('info_teleport_destination', (x, y, z), (0, 180 if s > 0 else 0, 0), group=GROUP, targetname='trench_%s_%d' % (tag, i + 1))
    for i, (x, y) in enumerate(LY.heal_points(s)):
        z = float(LY.ground_low(np.array([x]), np.array([y]))[0]) - LY.DEPTH
        ent('info_target', (x, y, z + 8), group=GROUP, targetname='heal_%s_%d' % (tag, i + 1))

# ---------------------------------------------------------------- lobby (spawn room) with the briefing banner
LZ = -2900.0
LW, LD, LH = 1536.0, 1152.0, 352.0
WOODW = 'materials/de_ancient/hr_ancient_ceiling_wood_01_base.vmat'
FLOORM = 'materials/cs_italy/wood/wood_boards_worn_1.vmat'
for m in (WOODW, FLOORM): vmesh.TEX_SIZE[m] = (1024, 1024)
vmesh.mesh_node(vmesh.box_mesh(-LW / 2, -LD / 2, LZ, LW / 2, LD / 2, LZ + LH, dict(bottom=FLOORM, top=WOODW, side=WOODW), inward=True), GROUP)
# banner: a picture on the north wall (unlit material made below)
bw, bh = 1100.0, 260.0
by = LD / 2 - 2
verts = [(-bw / 2, by, LZ + 60), (bw / 2, by, LZ + 60), (bw / 2, by, LZ + 60 + bh), (-bw / 2, by, LZ + 60 + bh),
         (-bw / 2, by + 1, LZ + 60), (bw / 2, by + 1, LZ + 60), (bw / 2, by + 1, LZ + 60 + bh), (-bw / 2, by + 1, LZ + 60 + bh)]
BANNER = 'materials/tw/briefing_banner.vmat'
vmesh.TEX_SIZE[BANNER] = (int(bw * 4), int(bh * 4))
bm = vmesh.polymesh_open(verts, [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [2, 3, 7, 6], [1, 2, 6, 5], [3, 0, 4, 7]],
                         [BANNER, NODRAW, NODRAW, NODRAW, NODRAW, NODRAW], scale=0.25)
# exact uv for the banner face: u along x, v down
fvd = bm.get('faceVertexData'); tex = fvd.get('streams')[0].get('data')
E_dest = bm.get('edgeVertexIndices'); E_face = bm.get('edgeFaceIndices')
for i, f in enumerate(E_face):
    if f == 0:
        vx, vy, vz = verts[E_dest[i]]
        tex[i] = ((vx + bw / 2) / bw, 1 - (vz - LZ - 60) / bh)
vmesh.mesh_node(bm, GROUP, bake=False, shadows=False)
for i in range(32):
    x = -560 + (i % 8) * 160; y = -420 + (i // 8) * 80
    ent('info_player_terrorist', (x - 40, y, LZ + 8), (0, 90, 0), group=GROUP, enabled='1', priority='0')
    ent('info_player_counterterrorist', (x + 40, y + 340, LZ + 8), (0, 90, 0), group=GROUP, enabled='1', priority='0')
for (lx, ly) in ((-400, -250), (400, -250), (-400, 250), (400, 250)):
    ent('light_omni2', (lx, ly, LZ + LH - 40), (90, 0, 0), group=GROUP, brightness_units='1', brightness_lumens='9000', brightness='2',
        color='255 214 160', range='1100', directlight='3', castshadows='0', colormode='0', enabled='1', bouncescale='1.0', shape='0')
clone('env_combined_light_probe_volume', (0, 0, LZ + LH / 2), box_mins='%g %g %g' % (-LW / 2, -LD / 2, -LH / 2), box_maxs='%g %g %g' % (LW / 2, LD / 2, LH / 2),
      voxel_size='48.0', targetname='lobby_probe')
for cls, pos, ang in (('counterterrorist_team_intro', (300, 300, LZ + 64), (0, 90, 0)), ('terrorist_team_intro', (-300, 300, LZ + 64), (0, 90, 0)),
                      ('team_select', (0, -300, LZ + 64), (0, 90, 0)), ('end_of_match', (0, 0, LZ + 64), (0, 90, 0))):
    clone(cls, pos, ang)

# ---------------------------------------------------------------- script, HUD and effect pools
SPOT = (0, 0, LZ + 100)
ent('point_script', SPOT, group=GROUP, targetname='tw_script', cs_script='maps/scripts/%s.vjs' % NAME)
ent('custom_hud_layout', (32, 0, LZ + 100), group=GROUP, targetname='tw_hud', layout='panorama/layout/custom_game/%s.vxml' % NAME, observable='1')
ent('info_map_parameters', (-32, 0, LZ + 100), group=GROUP, targetname='tw_params', buying='3', usenormalspawnsfordm='1', disableautogenerateddmspawns='1')
for i in range(12):
    p = (-600 + i * 60, -500, LZ + 120)
    ent('info_particle_system', p, group=GROUP, targetname='tw_boom_fx_%d' % (i + 1), effect_name='particles/explosions_fx/explosion_basic.vpcf', start_active='0')
    ent('info_particle_system', (p[0], p[1] + 30, p[2]), group=GROUP, targetname='tw_dirt_fx_%d' % (i + 1), effect_name='particles/ambient_fx/impact_dirt.vpcf', start_active='0')
    ent('point_soundevent', (p[0], p[1] + 60, p[2]), group=GROUP, targetname='tw_boom_snd_%d' % (i + 1), soundName='tw.mortar_impact',
        startOnSpawn='0', toLocalPlayer='0', stopOnNew='0', saveAndRestore='0')
    ent('point_soundevent', (p[0], p[1] + 90, p[2]), group=GROUP, targetname='tw_whistle_snd_%d' % (i + 1), soundName='tw.mortar_whistle',
        startOnSpawn='0', toLocalPlayer='0', stopOnNew='0', saveAndRestore='0')
    ent('env_shake', (p[0], p[1] + 120, p[2]), group=GROUP, targetname='tw_shake_%d' % (i + 1), amplitude='7', radius='900', duration='1.2', frequency='40', spawnflags='0')
for s in (-1, 1):
    for k, (cx, cy) in enumerate(LY.mortar_pits(s)):
        tag = '%s_%d' % ('ct' if s > 0 else 't', k + 1)
        ent('point_soundevent', (cx, cy, gz(cx, cy) + 30), group=GROUP, targetname='tw_launch_snd_' + tag, soundName='tw.mortar_launch',
            startOnSpawn='0', toLocalPlayer='0', stopOnNew='0', saveAndRestore='0')
        ent('info_particle_system', (cx, cy, gz(cx, cy) + 50), group=GROUP, targetname='tw_launch_fx_' + tag,
            effect_name='particles/ambient_fx/impact_dirt_child_smoke_puff.vpcf', start_active='0')
ent('point_soundevent', (0, 0, LZ + 200), group=GROUP, targetname='tw_ambience', soundName='tw.amb.front', startOnSpawn='1', toLocalPlayer='0', stopOnNew='0', saveAndRestore='0')

# ---------------------------------------------------------------- environment: sun, sky, fog, probes, post, soundscape
clone('light_environment', (0, 0, 2000), (55, 145, 0), targetname='tw_sun', color='196 202 210', brightness='1.6', castshadows='1', directlight='3',
      skycolor='150 160 175', skyintensity='1.6', fog='1', fogstrength='0.6')
clone('env_sky', (64, 0, 2000), targetname='sky', skyname='materials/skybox/sky_overcast_01.vmat', tint_color='190 196 205', brightnessscale='0.9')
clone('env_cubemap_fog', (128, 0, 2000), cubemapfogstartdistance='250', cubemapfogenddistance='7500', cubemapfogfalloffexponent='1.25',
      cubemapheightfog='1', cubemapfogheightstart='300.0', cubemapfogheightend='2600.0', cubemapfogheightexponent='1.0', cubemapfogmaxopacity='0.85',
      cubemapfogskyentity='sky')
ent('env_volumetric_fog_controller', (192, 0, 2000), group=GROUP, targetname='tw_vfog', IsMaster='1', FogStrength='0.8', TintColor='205 210 215',
    DrawDistance='1600', FadeInStart='40', FadeInEnd='300', FadeSpeed='2', IndirectEnabled='1', IndirectStrength='1.0', IndirectVoxelDim='256',
    NoiseSpeed='0.15', NoiseStrength='0.7', NoiseScale='.004 .004 .01', volume_depth_override='0', volume_first_slice_thickness='0')
clone('post_processing_volume', (256, 0, 2000), postprocessing='postprocess/%s.vpost' % NAME, master='1', minexposure='0.6', maxexposure='1.8',
      enableexposure='1', fadetime='1.0', spawnflags='4097')
clone('env_combined_light_probe_volume', (0, 0, 120), box_mins='-3900 -3700 -260', box_maxs='3900 4500 520', voxel_size='64.0', targetname='bf_probe')
# coarse probes for the light-probed trees and clutter outside the battlefield (strips around bf_probe, gaps for the aerodrome probes)
_far = [(-3900, -6300, 3900, -3700), (-3900, 4500, 3900, 6300)]
for s_ in (-1, 1):
    xa, xb = sorted((s_ * 3900, s_ * 7300)); ha, hb = sorted((s_ * (LY.HANGAR_X - 700), s_ * (LY.HANGAR_X + 700)))
    _far += [(xa, -6300, xb, -800), (xa, 800, xb, 6300), (xa, -800, ha, 800), (hb, -800, xb, 800)]
for k_, (x0, y0, x1, y1) in enumerate(_far):
    if x1 - x0 < 50: continue
    clone('env_combined_light_probe_volume', ((x0 + x1) / 2, (y0 + y1) / 2, 380), box_mins='%g %g -520' % (-(x1 - x0) / 2, -(y1 - y0) / 2),
          box_maxs='%g %g 520' % ((x1 - x0) / 2, (y1 - y0) / 2), voxel_size='108.0', targetname='far_probe_%d' % k_)
for s in (-1, 1):
    clone('env_combined_light_probe_volume', (s * LY.HANGAR_X, 0, 200), box_mins='-700 -800 -260', box_maxs='700 800 420', voxel_size='64.0',
          targetname='air_probe_%d' % (s + 1))
clone('env_soundscape', (0, 0, 300), radius='12000', soundscape='Nothing', enablesoundevent='1', soundevent='tw.amb.front')

# ---------------------------------------------------------------- 3D skybox (maps/mg_trenchwarfare_3dskybox.vmap, sky_camera at its origin, scale 16)
ent('skybox_reference', (0, 0, 0), group=GROUP, targetname='tw_skybox', targetMapName='maps/%s_3dskybox.vmap' % NAME,
    fixupNames='1', worldGroupID='skyboxWorldGroup0')

# ---------------------------------------------------------------- sky shell, vis hints, nav seeds, minimap bounds
SX, SY = LY.MAP_X + 256, LY.MAP_Y + 256
vmesh.mesh_node(vmesh.box_mesh(-SX, -SY, LY.SKY_Z0, SX, SY, LY.SKY_Z1, SKY, inward=True), GROUP, bake=False, shadows=False)

def hint(box, kind):
    x0, y0, z0, x1, y1, z1 = box
    c = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2); h = ((x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2)
    ent('visibility_hint', c, group=GROUP, hintType=str(kind), box_mins='%g %g %g' % (-h[0], -h[1], -h[2]), box_maxs='%g %g %g' % (h[0], h[1], h[2]))
for s in (-1, 1):
    a, b = sorted((s * 1290, s * 2620))
    hint((a, -3600, -300, b, 3300, 360), 3)                  # trenches, saps and the landings
    a, b = sorted((s * 1290, s * 1800))
    hint((a, 3300, -120, b, 3560, 360), 3)                   # skirmish track
    a, b = sorted((s * 2900, s * 3500))
    hint((a, -1900, -160, b, 1900, 320), 3)                  # mortar pits
hint((-1280, -3600, -300, 1280, -3150, -122), 3)              # mine galleries
hint((-1280, -3150, -300, 1280, 2900, 460), 8)                # no man's land (Lower: big open space)
hint((-1280, -3600, -121, 1280, -3150, 460), 8)
hint((-1280, 2900, -160, 1280, 4500, 420), 3)                 # woods skirmish clearing
hint((-LW / 2 - 64, -LD / 2 - 64, LZ - 64, LW / 2 + 64, LD / 2 + 64, LZ + LH + 64), 3)
hint((-SX - 64, -SY - 64, LZ - 128, SX + 64, SY + 64, LY.SKY_Z1 + 64), 9)
# no cs_minimap_boundary: with it CS2 renders its own top-down minimap (it showed the lobby) instead of the overview txt + radar png

# ---------------------------------------------------------------- banner and material files
def banner_png():
    W, H = 2048, int(2048 * bh / bw)
    im = Image.new('RGB', (W, H), (34, 31, 26))
    dr = ImageDraw.Draw(im)
    f1 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf', 80)
    f2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf', 36)
    f3 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf', 30)
    f4 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf', 26)
    dr.rectangle((14, 14, W - 15, H - 15), outline=(170, 150, 110), width=6)
    def centre(t, y, f, col):
        bb = dr.textbbox((0, 0), t, font=f); dr.text(((W - (bb[2] - bb[0])) / 2 - bb[0], y), t, fill=col, font=f)
    centre('THE WESTERN FRONT', 26, f1, (224, 210, 176))
    dr.line((W * 0.3, 128, W * 0.7, 128), fill=(170, 150, 110), width=3)
    centre('HOLD THE LINE, PUSH YOUR OPPOSITION INTO THE DIRT', 150, f2, (214, 178, 96))
    centre('EARN REWARDS AND GLORY FOR GOOD PERFORMANCE', 200, f2, (214, 178, 96))
    centre('!ROLES  TO VIEW COMBAT ROLES', 268, f3, (214, 206, 188))
    centre('!SWAP  TO SWITCH BETWEEN UNLOCKED PRIMARIES', 310, f3, (214, 206, 188))
    centre('CREATED FOR SLIME SERVERS', 376, f4, (170, 160, 136))
    centre('DISCORD.GG/SLIMESERVERS', 410, f4, (150, 200, 140))
    arr = np.asarray(im, np.float32)
    yy, xx = np.mgrid[0:H, 0:W]
    grain = fbm(xx / 60.0, yy / 60.0, 1.0, 3, seed=4)[..., None]
    arr = arr * (0.9 + 0.12 * grain)
    p = os.path.join(OUT, 'materials/tw'); os.makedirs(p, exist_ok=True)
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(os.path.join(p, 'briefing_banner_color.png'))
    open(os.path.join(p, 'briefing_banner.vmat'), 'w', newline='\n').write(
        '// mg_trenchwarfare briefing banner (generated)\nLayer0\n{\n\tshader "csgo_unlitgeneric.vfx"\n\tF_BLEND_MODE 0\n'
        '\tTextureColor "materials/tw/briefing_banner_color.png"\n\tg_vColorTint "[1.000000 1.000000 1.000000 0.000000]"\n}\n')
banner_png()

# ---------------------------------------------------------------- mine tunnels: one closed mesh (floor / roof heightfields + walls), timber sets,
# duckboards, lamps, the mine chamber in the middle where both sides' galleries meet (own rng: nothing above shifts)
TN = np.random.RandomState(1915)
T_FLOOR = MATS['mud_wet']; T_WALL = MATS['dirt2']; T_ROOF = 'materials/de_train/hr_train_s2/wood/hrts2_wood_floor_boards_02_wet.vmat'
for m_ in (T_FLOOR, T_WALL): vmesh.TEX_SIZE[m_] = (1024, 1024)
vmesh.TEX_SIZE[T_ROOF] = (1024, 512)
c_ = LY.TUN_CELL
TX_ = max(r_[2] for r_ in TUN)
gx = np.arange(-TX_, TX_ + 1, c_); gy = np.arange(-3536.0, LY.TUN_PORTAL_Y + 1, c_)
nxc, nyc = len(gx) - 1, len(gy) - 1
occ = np.zeros((nxc, nyc), bool)
for i in range(nxc):
    for j in range(nyc):
        occ[i, j] = tun_in((gx[i] + gx[i + 1]) / 2, (gy[j] + gy[j + 1]) / 2) is not None
FZ = np.zeros((nxc + 1, nyc + 1)); CZ = np.zeros((nxc + 1, nyc + 1))
used_v = np.zeros((nxc + 1, nyc + 1), bool)
for i, j in zip(*np.nonzero(occ)):
    used_v[i:i + 2, j:j + 2] = True
for i, j in zip(*np.nonzero(used_v)):
    FZ[i, j] = tun_floor(gx[i], gy[j]); CZ[i, j] = tun_ceil(gx[i], gy[j])
vid = {}; tverts = []
def V(i, j, top):
    k = (i, j, top)
    if k not in vid: vid[k] = len(tverts); tverts.append((gx[i], gy[j], CZ[i, j] if top else FZ[i, j]))
    return vid[k]
tfaces, tmats = [], []
def portal_edge(i, j, side):
    if side != 'y+' or j + 1 != nyc: return False
    xm = (gx[i] + gx[i + 1]) / 2
    return LY.TUN_SAP_X[0] < abs(xm) < LY.TUN_SAP_X[1]
for i, j in zip(*np.nonzero(occ)):
    tfaces.append([V(i, j, 0), V(i + 1, j, 0), V(i + 1, j + 1, 0), V(i, j + 1, 0)]); tmats.append(T_FLOOR)
    tfaces.append([V(i, j, 1), V(i, j + 1, 1), V(i + 1, j + 1, 1), V(i + 1, j, 1)]); tmats.append(T_ROOF)
    for (a_, b_, side, ni, nj) in (((i, j), (i + 1, j), 'y-', i, j - 1), ((i + 1, j), (i + 1, j + 1), 'x+', i + 1, j),
                                   ((i + 1, j + 1), (i, j + 1), 'y+', i, j + 1), ((i, j + 1), (i, j), 'x-', i - 1, j)):
        if 0 <= ni < nxc and 0 <= nj < nyc and occ[ni, nj]: continue
        if portal_edge(i, j, side): continue
        tfaces.append([V(b_[0], b_[1], 0), V(a_[0], a_[1], 0), V(a_[0], a_[1], 1), V(b_[0], b_[1], 1)]); tmats.append(T_WALL)
vmesh.mesh_node(vmesh.polymesh_open(tverts, tfaces, tmats), GROUP, bake=True, shadows=True)
print('mine tunnels: %d cells, %d faces' % (occ.sum(), len(tfaces)))

def tun_lamp(x, y, z, lm, col, rmax=130.0, shadows=False):
    """unshadowed baked lamp (CS2 has 4 shadow slots per overlap); range kept short of the surface and the next gallery"""
    gx, gy = np.meshgrid(np.arange(-rmax, rmax + 1, 16.0), np.arange(-rmax, rmax + 1, 16.0))
    gz_ = LY.ground_low(x + gx.ravel(), y + gy.ravel())
    d = np.sqrt(gx.ravel() ** 2 + gy.ravel() ** 2 + (gz_ - z) ** 2).min()
    r = max(70.0, min(rmax, d - 14.0))
    ent('light_omni2', (x, y, z), (90, 0, 0), group=GROUP, brightness_units='1', brightness_lumens=str(int(lm)), brightness='1',
        color=col, range='%.0f' % r, directlight='3', castshadows='1' if shadows else '0', colormode='0', enabled='1', bouncescale='1.0', shape='0')
    return r
def tun_runs():
    """centre lines of the narrow passages: (x0, y0, x1, y1, width) along their long axis"""
    for (x0, y0, x1, y1, k) in TUN:
        if k in ('chamber', 'landing'): continue
        if (x1 - x0) >= (y1 - y0): yield ((x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2), y1 - y0, k)
        else: yield (((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1), x1 - x0, k)
# clear the trench dressing in front of the sap portals
for c in list(vmaplib.new_children):
    if c.type != 'CMapEntity' or c.get('entity_properties').get('classname') != 'prop_static': continue
    m_ = c.get('entity_properties').get('model') or ''; o = c.get('origin')
    if LY.TUN_SAP_X[0] - 12 < abs(o[0]) < LY.TUN_SAP_X[1] + 12 and LY.TUN_PORTAL_Y - 70 < o[1] < LY.TUN_PORTAL_Y + 96 and not any(k_ in m_ for k_ in ('revet_', 'firestep', 'duckboard', 'sandbag_', 'shelter')):
        vmaplib.new_children.remove(c)
nsets = nlamp = 0
for (A, B, w, k) in tun_runs():
    L_ = math.hypot(B[0] - A[0], B[1] - A[1]); ux, uy = (B[0] - A[0]) / L_, (B[1] - A[1]) / L_
    yaw = math.degrees(math.atan2(uy, ux))
    t_ = 24.0 if k != 'sap' else 40.0
    while t_ < L_ - 16:
        x_, y_ = A[0] + ux * t_, A[1] + uy * t_
        f_, cz_ = tun_floor(x_, y_), tun_ceil(x_, y_)
        prop('tunnel_set', x_, y_, f_, yaw + TN.uniform(-2, 2), roll=TN.uniform(-1.5, 1.5), scale=(1, w / 80.0, max(0.6, (cz_ - f_) / 92.0)), reg=False)
        nsets += 1
        t_ += 48.0 + TN.uniform(-4, 4)
    if k in ('gallery', 'cross'):          # duckboards down the middle
        t_ = 64.0
        while t_ < L_ - 64:
            x_, y_ = A[0] + ux * t_, A[1] + uy * t_
            prop('duckboard_128', x_, y_, tun_floor(x_, y_) + 0.5, yaw + TN.uniform(-1.5, 1.5), reg=False)
            t_ += 128.0
    t_ = 90.0
    while t_ < L_ - 40:                    # lamps hung under the caps
        x_, y_ = A[0] + ux * t_, A[1] + uy * t_
        tun_lamp(x_, y_, tun_ceil(x_, y_) - 16, 340, '255 184 110')
        nlamp += 1
        t_ += 200.0 + TN.uniform(-15, 15)
# the landings at the foot of each sap: winding gear, spoil, timber, tools; the listening posts; the charge in the mine chamber
def tprop(name, x, y, yaw=None, dz=0.0, stock=None, solid='6'):
    return prop(name, x, y, tun_floor(x, y) + dz, TN.uniform(0, 360) if yaw is None else yaw, stock=stock, solid=solid, check=True, pad=2.0)
for s in (-1, 1):
    dx_ = LY.TUN_SAP_XC - 1648.0
    for (nm, x, y, yaw) in (('tl_bagpile', 1690, -3340, 0), ('tl_bagpile', 1660, -3348, 10), ('tl_planks', 1556, -3250, 90), ('tl_tools', 1700, -3260, 0),
                            ('tl_bucket', 1670, -3250, None), ('crate_long' if s > 0 else 'crate_german', 1560, -3345, 0), ('tl_wirereel', 1600, -3346, 0)):
        tprop(nm, s * (x + dx_), y, None if yaw is None else (yaw if s > 0 else 180 - yaw))
    for (x, y) in ((1024, -3200), (464, -3512), (1680, -3200)):           # listening posts: a bench and a telephone
        tprop('tl_bench', s * x, y, 0 if s > 0 else 180)
        tprop(None, s * (x + 14), y + 4, 90, dz=18.0, stock=EXT('field_telephone'))
        tun_lamp(s * x, y, tun_ceil(s * x, y) - 18, 160, '255 170 96', rmax=110.0)
    for (x, y) in ((LY.TUN_SAP_XC - 28, -3300), (900, -3270), (1500, -3460)):
        tprop('tl_lantern', s * x, y)
    wall_sign('sign_sap_gb' if s > 0 else 'sign_sap_de', LY.TUN_SAP_XC, -2760)
    # portal: a heavier set framing the opening
    xp_ = s * LY.TUN_SAP_XC
    fl_ = tun_floor(xp_, LY.TUN_PORTAL_Y - 6)
    prop('tunnel_set', xp_, LY.TUN_PORTAL_Y - 6, fl_, 90, scale=(1.3, 1.2, max(0.6, (tun_ceil(xp_, LY.TUN_PORTAL_Y - 6) - fl_) / 92.0)), reg=False)
# the mine chamber: tamped charge of ammonal boxes, sandbag tamping, the firing cable and the officer's table
for (nm, x, y, yaw, dz) in (('crate_shells', -24, -3380, 0, 0), ('crate_shells', 24, -3380, 0, 0), ('crate_shells', 0, -3380, 0, 12.6),
                            ('crate_shells', -24, -3352, 0, 0), ('crate_shells', 24, -3352, 0, 0), ('crate_shells', 0, -3352, 0, 12.6),
                            ('sandbag_low', 0, -3420, 0, 0), ('sandbag_low', 0, -3312, 0, 0), ('tl_wirereel', -110, -3470, 90, 0), ('tl_wirereel', 110, -3260, 90, 0)):
    prop(nm, x, y, tun_floor(x, y) + dz, yaw, check=True, pad=1.0)
for (x, y) in ((0, -3300), (0, -3440)):            # the chamber keeps two shadowed lamps (only the sun overlaps them)
    tun_lamp(x, y, tun_ceil(x, y) - 18, 600, '255 180 104', rmax=150.0, shadows=True)
clone('env_combined_light_probe_volume', (0, -3216, -200), box_mins='-2260 -340 -90', box_maxs='2260 400 120', voxel_size='32.0', targetname='tunnel_probe')
print('mine tunnels: %d timber sets, %d lamps' % (nsets, nlamp))

# ---------------------------------------------------------------- woods skirmish: a ladder out of the north end of each fire trench,
# a fenced track through the shell-holes and a fenced clearing in the wood where both sides meet (own rng: nothing above shifts)
SK = np.random.RandomState(1918)
LADDER_TOOL = 'materials/tools/toolsinvisibleladder_wood.vmat'
vmesh.TEX_SIZE[LADDER_TOOL] = (64, 64)


def gs(x, y):
    """walkable surface: the terrain, or the parapet/parados layer where it covers the trench banks"""
    Z, D_ = LY.parapet(np.array([float(x)]), np.array([float(y)]))
    h = float(LY.height(np.array([float(x)]), np.array([float(y)]))[0])
    return max(h, float(Z[0])) if 2 <= D_[0] <= 116 else h


def _isect(p, d, q, e):
    """intersection of lines p + t d and q + u e"""
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-9: return q
    t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
    return (p[0] + d[0] * t, p[1] + d[1] * t)


def _offset_path(pts, w):
    """polyline offset by w to the left (mitred corners)"""
    out = []
    for i in range(len(pts)):
        segs = []
        if i > 0: segs.append((pts[i - 1], pts[i]))
        if i < len(pts) - 1: segs.append((pts[i], pts[i + 1]))
        lines = []
        for a_, b_ in segs:
            dx, dy = b_[0] - a_[0], b_[1] - a_[1]; L_ = math.hypot(dx, dy); dx, dy = dx / L_, dy / L_
            lines.append(((a_[0] - dy * w, a_[1] + dx * w), (dx, dy)))
        if len(lines) == 1:
            (o, dd) = lines[0]; t_ = 0 if i == 0 else 1
            base = pts[i]; out.append((base[0] - dd[1] * w, base[1] + dd[0] * w))
        else:
            out.append(_isect(lines[0][0], lines[0][1], lines[1][0], lines[1][1]))
    return out


B_ = (1080.0, 3560.0)
spine = [(EXIT_X, EXIT_Y), (EXIT_X, EXIT_Y + 95.0), B_]                      # CT half; walking out of the trench
left = _offset_path(spine, EXIT_W)                                            # west / south-west wall
right = _offset_path(spine, -EXIT_W)                                          # east / north-east wall
arena_e = [(1185, 3700), (1210, 3950), (1130, 4205), (905, 4350), (455, 4415), (0, 4395)]       # CT half of the clearing's rim
arena_s = [(850, 3478), (450, 3452), (0, 3472)]
ct_loop = [right[0], right[1], right[2]] + arena_e                             # trench exit -> north-east wall -> rim to x = 0 (north)
south_ct = [left[0], left[1], left[2]] + arena_s                               # trench exit -> south-west wall -> south rim to x = 0
mir = lambda P: [(-p[0], p[1]) for p in P]
OUTLINE = ct_loop + mir(ct_loop)[::-1][1:] + mir(south_ct) + south_ct[::-1][1:] + [ct_loop[0]]


def _jag(P, step=150.0, amp=22.0):
    """subdivide and wobble the rim so it reads as a hand-built fence line (the trench-exit edges stay straight)"""
    out = [P[0]]
    for a_, b_ in zip(P[:-1], P[1:]):
        L_ = math.hypot(b_[0] - a_[0], b_[1] - a_[1]); n_ = max(1, int(L_ / step))
        nx_, ny_ = -(b_[1] - a_[1]) / max(L_, 1e-6), (b_[0] - a_[0]) / max(L_, 1e-6)
        exitish = a_[1] < EXIT_Y + 120 and b_[1] < EXIT_Y + 120
        for k in range(1, n_ + 1):
            t_ = k / n_; q = (a_[0] + (b_[0] - a_[0]) * t_, a_[1] + (b_[1] - a_[1]) * t_)
            if k < n_ and not exitish:
                j = SK.uniform(-amp, amp); q = (q[0] + nx_ * j, q[1] + ny_ * j)
            out.append(q)
    return out
OUTLINE = _jag(OUTLINE)


def inside_skirmish(x, y):
    c = False
    for (x1, y1), (x2, y2) in zip(OUTLINE[:-1], OUTLINE[1:]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def clip_slab(p, q, z0, z1, t=4.0):
    dx, dy = q[0] - p[0], q[1] - p[1]; L_ = math.hypot(dx, dy)
    if L_ < 1: return
    nx_, ny_ = -dy / L_ * t, dx / L_ * t
    ring = [(p[0] - nx_, p[1] - ny_), (q[0] - nx_, q[1] - ny_), (q[0] + nx_, q[1] + ny_), (p[0] + nx_, p[1] + ny_)]
    v = [(x_, y_, z0) for x_, y_ in ring] + [(x_, y_, z1) for x_, y_ in ring]
    faces = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [2, 3, 7, 6], [1, 2, 6, 5], [3, 0, 4, 7]]
    vmesh.mesh_node(vmesh.polymesh_open(v, faces, [PCLIP] * 6, scale=0.25), GROUP, bake=False, shadows=False, visexclude=True)


# clear the track, the clearing's entrances and the foot of each exit ladder of anything generated earlier
def _near_track(x, y):
    for sx in (1, -1):
        for p_, q_ in zip(spine[:-1], spine[1:]):
            P0 = (sx * p_[0], p_[1]); P1 = (sx * q_[0], q_[1])
            dx, dy = P1[0] - P0[0], P1[1] - P0[1]; L2 = dx * dx + dy * dy
            t_ = max(0, min(1, ((x - P0[0]) * dx + (y - P0[1]) * dy) / L2))
            if math.hypot(x - P0[0] - dx * t_, y - P0[1] - dy * t_) < EXIT_W + 30: return True
        if math.hypot(x - sx * B_[0], y - B_[1]) < 190: return True
    return False
STRUCT = ('revet_', 'firestep', 'duckboard', 'sandbag_', 'shelter')
_drop = 0
for c in list(vmaplib.new_children):
    if c.type != 'CMapEntity' or c.get('entity_properties').get('classname') != 'prop_static': continue
    m_ = c.get('entity_properties').get('model') or ''
    o = c.get('origin')
    at_foot = abs(abs(o[0]) - EXIT_X) < 75 and EXIT_Y - 80 < o[1] < EXIT_Y + 2 and not any(k_ in m_ for k_ in STRUCT)
    on_track = o[1] > EXIT_Y + 2 and _near_track(o[0], o[1])
    if at_foot or on_track:
        vmaplib.new_children.remove(c); _drop += 1

nfence = 0; nclip = 0
for a_, b_ in zip(OUTLINE[:-1], OUTLINE[1:]):
    if a_[1] <= EXIT_Y + 1 and b_[1] <= EXIT_Y + 1: continue                  # the open side onto the ladder
    zs = [gs(a_[0] + (b_[0] - a_[0]) * t_, a_[1] + (b_[1] - a_[1]) * t_) for t_ in np.linspace(0, 1, 6)]
    clip_slab(a_, b_, min(zs) - 96, max(zs) + 128); nclip += 1
    # the visible fence: barbed-wire panels on pickets, gaps and leans where shellfire got it
    L_ = math.hypot(b_[0] - a_[0], b_[1] - a_[1]); yaw = math.degrees(math.atan2(b_[1] - a_[1], b_[0] - a_[0]))
    nseg = max(1, int(round(L_ / 128.0)))
    for k in range(nseg):
        if SK.rand() < 0.22: continue
        t_ = (k + 0.5) / nseg; x_, y_ = a_[0] + (b_[0] - a_[0]) * t_, a_[1] + (b_[1] - a_[1]) * t_
        prop(['wire_fence_a', 'wire_fence_b'][SK.randint(2)], x_, y_, gs(x_, y_) - 2, yaw + SK.uniform(-4, 4), roll=SK.uniform(-8, 8),
             scale=(L_ / nseg / 128.0, 1, 1), solid='0', reg=False)
        nfence += 1
# ladders up the trench end: a leaning ladder to look at, an invisible ladder volume to climb (solid off on the visual one)
for s in (-1, 1):
    fl_ = float(LY.ground_low(np.array([s * EXIT_X]), np.array([EXIT_Y - 30]))[0]) - LY.DEPTH
    g_ = max(gs(s * EXIT_X, EXIT_Y + 6), gs(s * EXIT_X, EXIT_Y + 30))
    prop('ladder', s * EXIT_X, EXIT_Y - 13, fl_ - 10.0, 270 + SK.uniform(-1, 1), pitch=-4, solid='0', reg=False)   # near-vertical (user's placement)
    # the climb volume is the user's own toolsinvisibleladder mesh in the vmap (outside tw_gen)
    prop('sign_wood_gb' if s > 0 else 'sign_wood_de', s * (EXIT_X - 72), EXIT_Y - 4.6, fl_, 0, check=True)
# the clearing: cover from logs, stumps, broken trees, scraped-up sandbag scrapes and dumped stores, placed in mirrored pairs
cover = [('log_fallen', 5), ('stump_a', 3), ('stump_b', 3), ('tree_shattered_a', 1), ('tree_shattered_c', 1), ('tree_shattered_d', 1),
         ('sandbag_low', 4), ('tl_bagpile', 2), ('crate_long', 1), ('crate_german', 1), ('wire_coil', 2), ('tl_planks', 1)]
ncover = 0
for name, cnt in cover:
    for _ in range(cnt):
        for attempt in range(25):
            x_, y_ = SK.uniform(90, 1120), SK.uniform(3560, 4330)
            if not inside_skirmish(x_, y_) or math.hypot(x_ - B_[0], y_ - B_[1]) < 170: continue
            yaw = SK.uniform(0, 360)
            ok = True
            for sx in (1, -1):
                f = PL.footprint('models/tw/%s/%s.vmdl' % (name, name), sx * x_, y_, gs(sx * x_, y_), yaw if sx > 0 else 180 - yaw, (1, 1, 1), 4.0)
                if PL.hits(f): ok = False
            if not ok: continue
            for sx in (1, -1):
                prop(name, sx * x_, y_, gs(sx * x_, y_) - (3 if 'log' in name or 'stump' in name else 0.5), yaw if sx > 0 else 180 - yaw,
                     solid='0' if name == 'wire_coil' else '6', pad=2.0)
            ncover += 2
            break
print('woods skirmish: exit at x=+-%.0f y=%.0f, %d clip walls, %d fence panels, %d cover props, %d trees/bushes cleared' % (EXIT_X, EXIT_Y, nclip, nfence, ncover, _drop))

# ---------------------------------------------------------------- lightmap player-space volumes (tools/lightmapres): the compiler gives
# surfaces near these meshes more lightmap texels. Walkable band over the trenches, no man's land, the skirmish wood, mortar pits;
# the mine galleries and the lobby as boxes.
LMRES = 'materials/tools/toolslightmapres.vmat'
vmesh.TEX_SIZE[LMRES] = (64, 64)
from matplotlib.path import Path as _MPath
LC = 64.0
lgx = np.arange(-3456.0, 3456.0 + 1, LC); lgy = np.arange(-3072.0, 4480.0 + 1, LC)
lnx, lny = len(lgx) - 1, len(lgy) - 1
LX0, LY0_ = np.meshgrid(lgx[:-1], lgy[:-1], indexing='ij'); LX1, LY1_ = LX0 + LC, LY0_ + LC
locc = (np.abs(LX0 + LC / 2) < 1600) & (LY0_ + LC / 2 > -2990) & (LY0_ + LC / 2 < 2990)        # no man's land
for s in (-1, 1):
    for (x0, y0, x1, y1, k) in LY.rects():
        a, b = sorted((s * x0, s * x1))
        locc |= (LX1 > a) & (LX0 < b) & (LY1_ > y0) & (LY0_ < y1)
    for my in LY.MORTAR_Y:
        locc |= (LX1 > s * LY.MORTAR_X - 230) & (LX0 < s * LY.MORTAR_X + 230) & (LY1_ > my - 230) & (LY0_ < my + 230)
_sk = _MPath(np.array(OUTLINE))
for dx_ in (0.1, 0.5, 0.9):
    for dy_ in (0.1, 0.5, 0.9):
        locc |= _sk.contains_points(np.stack([(LX0 + dx_ * LC).ravel(), (LY0_ + dy_ * LC).ravel()], 1)).reshape(locc.shape)
ci, cj = np.nonzero(locc)
off = np.arange(0.0, LC + 1, 16.0)
ox, oy = np.meshgrid(off, off, indexing='ij'); ox = ox.ravel(); oy = oy.ravel()
PX = (lgx[ci][:, None] + ox[None, :]).ravel(); PY = (lgy[cj][:, None] + oy[None, :]).ravel()
HZ = LY.height(PX, PY); PZ, PD = LY.parapet(PX, PY)
TOPZ = np.where((PD >= 2) & (PD <= 116), np.maximum(HZ, PZ), HZ)
cb = HZ.reshape(len(ci), -1).min(1) - 8.0; ct = TOPZ.reshape(len(ci), -1).max(1) + 128.0
LB = np.full((lnx + 1, lny + 1), 1e9); LT = np.full((lnx + 1, lny + 1), -1e9)
for (di, dj) in ((0, 0), (1, 0), (0, 1), (1, 1)):
    np.minimum.at(LB, (ci + di, cj + dj), cb); np.maximum.at(LT, (ci + di, cj + dj), ct)
lv = {}; lverts = []; lfaces = []
def _LV(i, j, top):
    k = (i, j, top)
    if k not in lv: lv[k] = len(lverts); lverts.append((lgx[i], lgy[j], LT[i, j] if top else LB[i, j]))
    return lv[k]
for i, j in zip(ci, cj):
    lfaces.append([_LV(i, j, 0), _LV(i + 1, j, 0), _LV(i + 1, j + 1, 0), _LV(i, j + 1, 0)][::-1])
    lfaces.append([_LV(i, j, 1), _LV(i + 1, j, 1), _LV(i + 1, j + 1, 1), _LV(i, j + 1, 1)])
    for (a_, b_, ni, nj) in (((i, j), (i + 1, j), i, j - 1), ((i + 1, j), (i + 1, j + 1), i + 1, j),
                             ((i + 1, j + 1), (i, j + 1), i, j + 1), ((i, j + 1), (i, j), i - 1, j)):
        if 0 <= ni < lnx and 0 <= nj < lny and locc[ni, nj]: continue
        lfaces.append([_LV(a_[0], a_[1], 0), _LV(b_[0], b_[1], 0), _LV(b_[0], b_[1], 1), _LV(a_[0], a_[1], 1)])
vmesh.mesh_node(vmesh.polymesh_open(lverts, lfaces, [LMRES] * len(lfaces)), GROUP, bake=False, shadows=False, visexclude=True)
nlm = 1
for (x0, y0, x1, y1, k) in TUN:
    xs_ = np.linspace(x0, x1, 5); ys_ = np.linspace(y0, y1, 5)
    fz = min(tun_floor(a, b) for a in xs_ for b in ys_); cz = max(tun_ceil(a, b) for a in xs_ for b in ys_)
    vmesh.mesh_node(vmesh.box_mesh(x0 + 2, y0 + 2, fz + 2, x1 - 2, y1 - 2, cz - 2, LMRES), GROUP, bake=False, shadows=False, visexclude=True)
    nlm += 1
vmesh.mesh_node(vmesh.box_mesh(-LW / 2 + 16, -LD / 2 + 16, LZ + 8, LW / 2 - 16, LD / 2 - 16, LZ + LH - 16, LMRES), GROUP, bake=False, shadows=False, visexclude=True)
print('lightmap player space: %d cells (%d faces) + %d boxes' % (len(ci), len(lfaces), nlm))

# ---------------------------------------------------------------- swap into the world
kids = world.attr('children')
kept = []
for c in kids[2]:
    if c.get('customVisGroup', '') == GROUP: continue
    if c.type in ('CMapMesh',) and not c.get('customVisGroup', ''): continue          # template sample geometry
    if c.type == 'CMapEntity':
        cls = c.get('entity_properties').get('classname')
        if cls in ('point_worldtext', 'func_buyzone', 'info_player_start', 'light_environment', 'env_sky', 'env_cubemap_fog', 'env_combined_light_probe_volume',
                   'post_processing_volume', 'env_soundscape', 'counterterrorist_team_intro', 'terrorist_team_intro', 'team_select', 'end_of_match',
                   'cs_minimap_boundary', 'point_nav_walkable', 'info_player_terrorist', 'info_player_counterterrorist'):
            continue
    kept.append(c)
newc = [c for c in vmaplib.new_children if not SKIP_SIGS or obj_sig(c) not in SKIP_SIGS]
# user copies that the generator now reproduces itself (their edit was adopted into the rules) are dropped
def _ek(c):
    ep = c.get('entity_properties'); return (ep.get('classname') or '', ep.get('model') or '')
_gen_idx = {}
for c in newc:
    if c.type == 'CMapEntity': _gen_idx.setdefault(_ek(c), []).append(c)
_adopt = 0
for c in list(kept):
    if c.get('customVisGroup', '') != USER_GROUP or c.type != 'CMapEntity': continue
    o = np.array(c.get('origin')); an = c.get('angles')
    for g_ in _gen_idx.get(_ek(c), ()):
        if np.abs(np.array(g_.get('origin')) - o).max() < 12 and max(abs(((p - q) + 180) % 360 - 180) for p, q in zip(an, g_.get('angles'))) < 8:
            kept.remove(c); _adopt += 1; break
print('user edits now produced by the generator (user copy dropped): %d' % _adopt)
print('skipped %d generated objects the user replaced' % (len(vmaplib.new_children) - len(newc)))
kids[2] = kept + newc
counts = {}
for c in kids[2]:
    if c.type == 'CMapEntity':
        cls = c.get('entity_properties').get('classname'); counts[cls] = counts.get(cls, 0) + 1
pre = {a[0]: a for a in d.prefix[0]}
refs = pre['map_asset_references'][2]
for m in list(vmaplib.materials_used) + sorted(props_placed):
    if m not in refs: refs.append(m)
names = sorted(counts)
if 'map_subasset_reference_types' in pre:
    pre['map_subasset_reference_types'][2] = ['entity'] * len(names)
    pre['map_subasset_reference_names'][2] = names
    pre['map_subasset_reference_counts'][2] = [counts[n] for n in names]
# interpenetration audit of everything with a recorded footprint
from collections import Counter as _C
pairs = PL.audit()
cnt = _C(tuple(sorted((PL.items[i]['model'].split('/')[-1][:-5], PL.items[j]['model'].split('/')[-1][:-5]))) for i, j in pairs)
print('overlaps: %d pairs' % len(pairs), cnt.most_common(25))
json.dump([dict(a=PL.items[i]['model'], b=PL.items[j]['model'], ca=PL.items[i]['c'], cb=PL.items[j]['c']) for i, j in pairs],
          open(os.path.join(os.path.dirname(__file__), '..', 'out', 'overlaps.json'), 'w'), indent=0)
d.elements = [root]
d.save(OUTPATH)
print('vmap: %d entities (%d prop_static), %d meshes -> %s (%.1f MB)' % (sum(counts.values()), counts.get('prop_static', 0),
      sum(1 for c in kids[2] if c.type == 'CMapMesh'), OUTPATH, os.path.getsize(OUTPATH) / 1e6))
json.dump({k: v for k, v in sorted(props_placed.items())}, open(os.path.join(os.path.dirname(OUTPATH), 'props_used.json'), 'w'), indent=1)
