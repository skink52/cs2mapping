"""Vis compile time: hint boxes fitted to the play space, and sky shells out of vis where nothing needs them.

The CS2 vis compile (VIS3) spends most of its time clustering, sampling line of sight and merging clusters down to the 4,096 cap.
How many clusters it starts with depends on the visibility_hint that governs each part of the map (where hints overlap, the
highest resolution wins). So hints should only be fine where players can actually stand.

1. Playable air: empty space at VS-unit voxels (world meshes that block players, incl. clips, detail and sky shells) connected
   to a spawn or teleport destination, plus sealed compartments that hold gameplay entities (buttons, doors, triggers, trains,
   weapons). The open void around the map never counts.
2. Walkable band: playable air up to BAND units above something to stand on (world or entity meshes).
3. Hints, on a 256-unit grid so they line up with the Lowest regions, Low and Lower never overlapping:
     Low    (hintType 3, 64-unit grid)                         cells holding walkable band
     Lower  (hintType 8, 64-unit grid, fewer initial clusters)  other playable air next to geometry (high ceilings, shafts)
     Lowest (hintType 9, 256-unit grid)                         one box over the whole map: void, sealed-off rooms, open sky
   Open sky far above an outdoor area gets no box of its own, so it falls to Lowest. all_lower=True makes the Low cells Lower too
   (for maps whose vis merge stalls, e.g. mg_egypt_course). lean=True (stage D visfit_lean) goes further: only the walkable band gets a
   box, as Lower, and all other playable air (high ceilings, shafts) falls to Lowest (mg_n64_goldeneye: 620k initial clusters). Boxes are merged while at least 75% (then 60%, 50%) of a box is its
   own cells, aiming for at most 100 boxes.
4. Sky shells (all-moondome / all-toolsskybox meshes) get Exclude from Vis unless they border playable air that is open once
   every sky shell is gone. That test uses only vis-relevant geometry: Valve's docs say toolsnodraw is ignored by vis and by
   its inside/outside test, and clips, triggers and meshes already excluded from vis don't count either.
5. Optional extra_visex_box (world box): every world mesh entirely inside it is excluded from vis too (an unreachable
   ex-3D-skybox, for example).
Existing visibility_hint entities are replaced.
"""
import collections
import numpy as np
from scipy import ndimage
import dmx
from lighting import mesh_polys

PLAY = ('info_player_counterterrorist', 'info_player_terrorist', 'info_player_start', 'info_teleport_destination')
ACTIVE = ('func_button', 'func_rot_button', 'func_door', 'func_door_rotating', 'func_movelinear', 'trigger_multiple', 'trigger_once',
          'trigger_teleport', 'game_player_equip', 'point_teleport', 'func_tracktrain', 'func_rotating', 'func_physbox')
PHYS_PASS = ('materials/tools/toolstrigger', 'materials/tools/toolshint', 'materials/tools/toolsskip', 'materials/tools/toolsfog',
             'materials/tools/toolslight', 'materials/tools/toolsblocklight', 'materials/tools/toolsblock_los', 'materials/tools/toolsbuyzone',
             'materials/tools/toolsbombsite', 'materials/tools/toolsareaportal', 'materials/tools/toolsoccluder', 'materials/tools/toolsvisblocker')
CELL = 256.0
BAND = 160.0
CODE = {'Low': '3', 'Lower': '8', 'Lowest': '9'}

def is_shell(mats):
    return bool(mats) and all('moondome' in x or x == 'materials/tools/toolsskybox.vmat' for x in mats)

def vis_relevant(mat):
    if 'moondome' in mat: return True
    if mat.startswith('materials/tools/'):
        return mat.startswith(('materials/tools/toolsskybox', 'materials/tools/toolssolidblocklight', 'materials/tools/toolsvisblocker'))
    return True

def meshes(m):
    par = {n: p for n, p in m.walk()}
    def in_ent(n):
        p = par.get(n)
        while p is not None:
            if m.type(p) == b'CMapEntity': return p
            p = par.get(p)
        return None
    out = []
    for n, _ in m.walk():
        if m.type(n) != b'CMapMesh': continue
        pl = mesh_polys(m, n); mats = {x for x, _ in pl}
        a = dmx.geta(m.E[n], b'visexclude')
        out.append(dict(n=n, ent=in_ent(n), polys=pl, mats=mats, shell=is_shell(mats), visex=bool(a and a[2])))
    return out

def raster(polys, lo, shape, vs, grid):
    for L in polys:
        L = np.asarray(L, np.float64)
        if (np.floor((L.max(0) - lo) / vs) < 0).any() or (np.floor((L.min(0) - lo) / vs) >= shape).any(): continue
        for i in range(1, len(L) - 1):
            a, b, c = L[0], L[i], L[i + 1]
            k = int(max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b)) / (vs * 0.4)) + 2
            u, w = np.meshgrid(np.linspace(0, 1, k), np.linspace(0, 1, k)); s = (u + w) <= 1
            q = a + np.outer(u[s], b - a) + np.outer(w[s], c - a)
            idx = np.floor((q - lo) / vs).astype(int)
            idx = idx[((idx >= 0) & (idx < shape)).all(1)]
            grid[idx[:, 0], idx[:, 1], idx[:, 2]] = True

def _border(lab):
    return set(np.unique(np.concatenate([lab[0].ravel(), lab[-1].ravel(), lab[:, 0].ravel(), lab[:, -1].ravel(),
                                         lab[:, :, 0].ravel(), lab[:, :, -1].ravel()]))) - {0}

def boxes_from_cells(cells):
    left = set(cells); out = []
    while left:
        i, j, k = min(left)
        x1 = i
        while (x1 + 1, j, k) in left: x1 += 1
        y1 = j
        while all((x, y1 + 1, k) in left for x in range(i, x1 + 1)): y1 += 1
        z1 = k
        while all((x, y, z1 + 1) in left for x in range(i, x1 + 1) for y in range(j, y1 + 1)): z1 += 1
        for x in range(i, x1 + 1):
            for y in range(j, y1 + 1):
                for z in range(k, z1 + 1): left.discard((x, y, z))
        out.append(((i, j, k), (x1 + 1, y1 + 1, z1 + 1)))
    return out

def merge_boxes(boxes, own, other, fill=0.75):
    """join boxes whose union is mostly own cells and holds none of the other hint type's cells (boxes stay disjoint)"""
    boxes = [(tuple(a), tuple(b)) for a, b in boxes]
    if len(boxes) < 2: return boxes
    allc = np.array(list(own | other))
    o = allc.min(0); sz = allc.max(0) - o + 1
    def cum(cs):
        g = np.zeros(sz + 1, np.int32)
        for c in cs: g[tuple(np.array(c) - o + 1)] = 1
        return g.cumsum(0).cumsum(1).cumsum(2)
    O, T = cum(own), cum(other)
    def cnt(S, a, b):
        x0, y0, z0 = np.array(a) - o; x1, y1, z1 = np.array(b) - o
        return int(S[x1, y1, z1] - S[x0, y1, z1] - S[x1, y0, z1] - S[x1, y1, z0] + S[x0, y0, z1] + S[x0, y1, z0] + S[x1, y0, z0] - S[x0, y0, z0])
    while len(boxes) > 1:
        A = np.array([bx[0] for bx in boxes]); B = np.array([bx[1] for bx in boxes])
        best = None
        for i in range(len(boxes)):
            ua = np.minimum(A[i], A[i + 1:]); ub = np.maximum(B[i], B[i + 1:])
            for a, b in zip(ua, ub):
                v = int(np.prod(b - a))
                if v > 4096: continue
                n = cnt(O, a, b)
                if n / v < fill or (best and n / v <= best[0]) or cnt(T, a, b): continue
                ins = np.all((A >= a) & (B <= b), 1); ovl = np.all((A < b) & (B > a), 1)
                if (ovl & ~ins).any(): continue
                best = (n / v, tuple(a), tuple(b), ins)
        if not best: break
        _, a, b, ins = best
        boxes = [bx for k, bx in enumerate(boxes) if not ins[k]] + [(a, b)]
    return boxes

def plan(m, all_lower=False, extra_visex_box=None, vs=None, margin=256.0, lean=False):
    ms = meshes(m)
    world = [x for x in ms if x['ent'] is None]
    allp = np.array([p for x in world for _, l in x['polys'] for p in l])
    lo = allp.min(0) - margin; hi = allp.max(0) + margin
    if vs is None:     # keep the grids within the cloud workspace's memory
        vs = next(v for v in (16.0, 24.0, 32.0, 48.0) if np.prod(np.ceil((hi - lo) / v)) < 1.2e8)
    shape = np.array([int(v) for v in np.ceil((hi - lo) / vs)])
    phys = np.zeros(shape, bool); visg = np.zeros(shape, bool); ent = np.zeros(shape, bool); sh = np.zeros(shape, np.int32)
    raster([l for x in world for mt, l in x['polys'] if not mt.startswith(PHYS_PASS)], lo, shape, vs, phys)
    raster([l for x in world if not x['visex'] and not x['shell'] for mt, l in x['polys'] if vis_relevant(mt)], lo, shape, vs, visg)
    raster([l for x in ms if x['ent'] is not None for mt, l in x['polys'] if not mt.startswith(PHYS_PASS)], lo, shape, vs, ent)
    shells = [x for x in world if x['shell']]
    for si, x in enumerate(shells, 1):
        g = np.zeros(shape, bool); raster([l for _, l in x['polys']], lo, shape, vs, g); sh[g] = si
    lab, _ = ndimage.label(~(phys | (sh > 0)))
    def comp_at(p, r=3):
        i = np.floor((np.array(p, float) - lo) / vs).astype(int)
        for rr in range(r + 1):
            v = lab[tuple(slice(max(0, i[k] - rr), i[k] + rr + 1) for k in range(3))]; v = v[v > 0]
            if v.size: return int(np.bincount(v).argmax())
        return 0
    seeds = {comp_at(np.array(m.origin(e), float) + [0, 0, 36]) for e in m.by_class(*PLAY)} - {0}
    act = {comp_at(m.origin(e), 2) for e in m.entities() if m.cls(e) in ACTIVE or m.cls(e).startswith('weapon_')} - {0}
    border = _border(lab)
    comps = (seeds | act) - border
    P = np.isin(lab, list(comps))
    del lab
    solid = phys | (sh > 0) | ent
    band = np.zeros(shape, bool)
    for k in range(1, int(BAND / vs) + 1):
        band[:, :, k:] |= solid[:, :, :-k]
    band &= P
    del solid
    def cells_of(mask):
        idx = np.argwhere(mask)
        return set(map(tuple, np.floor((lo + (idx + 0.5) * vs) / CELL).astype(int)))
    pc, bc = cells_of(P), cells_of(band)
    geo = cells_of((phys & (sh == 0)) | visg | ent)
    low = set(bc); lower = (pc - low) & geo
    if all_lower: lower |= low; low = set()
    if lean: lower = set(low) | (lower & bc); low = set()      # only the walkable band gets a box (Lower); all other air falls to Lowest
    for fill in (0.75, 0.6, 0.5):
        hints = [('Low', a, b) for a, b in merge_boxes(boxes_from_cells(low), low, lower, fill)] + \
                [('Lower', a, b) for a, b in merge_boxes(boxes_from_cells(lower), lower, low, fill)]
        if len(hints) <= 100: break
    hints = [(t, np.array(a) * CELL, np.array(b) * CELL) for t, a, b in hints]
    hints.append(('Lowest', np.floor(allp.min(0) / 256) * 256 - 256, np.ceil(allp.max(0) / 256) * 256 + 256))
    # sky shells: keep the ones bordering playable air that is open once all sky shells are gone
    vl, _ = ndimage.label(~visg)
    leaky = P & np.isin(vl, list(_border(vl)))
    del vl
    near_leak = ndimage.binary_dilation(leaky, iterations=2)
    keep_ids = set(np.unique(sh[near_leak & (sh > 0)])) - {0}
    exclude = [x for si, x in enumerate(shells, 1) if si not in keep_ids and not x['visex']]
    extra = []
    if extra_visex_box is not None:
        a, b = np.array(extra_visex_box[0], float), np.array(extra_visex_box[1], float)
        for x in world:
            if x['visex'] or x['shell']: continue
            bb = m.bounds(x['n'])
            if bb and (np.array(bb[0]) >= a).all() and (np.array(bb[1]) <= b).all(): extra.append(x)
    stats = dict(vs=vs, play=P.sum() * vs ** 3 / 1e9, band=band.sum() * vs ** 3 / 1e9, shells=len(shells), kept=len(shells) - len(exclude),
                 hints=dict(collections.Counter(h[0] for h in hints)))
    return dict(hints=hints, exclude=exclude, extra=extra, stats=stats)

def apply(m, pl):
    for e in m.by_class('visibility_hint'): m.remove_node(e)
    for t, mn, mx in pl['hints']:
        o = (mn + mx) / 2
        m.new_entity('visibility_hint', o, {'box_mins': ' '.join('%g' % v for v in mn - o), 'box_maxs': ' '.join('%g' % v for v in mx - o),
                                            'hintType': CODE[t]})
    for x in pl['exclude'] + pl['extra']:
        a = dmx.geta(m.E[x['n']], b'visexclude')
        if a: a[2] = True
        else: dmx.set_(m.E[x['n']], b'visexclude', dmx.T_BOOL, True)

def run(m, c, all_lower=False, extra_visex_box=None, lean=False):
    old = collections.Counter({'3': 'Low', '8': 'Lower', '9': 'Lowest', '2': 'Medium', '0': 'High', '1': 'Normal', '10': 'Reduced'}
                              .get(m.P(e, 'hintType', ''), '?') for e in m.by_class('visibility_hint'))
    pl = plan(m, all_lower, extra_visex_box, lean=lean)
    apply(m, pl)
    s = pl['stats']; h = s['hints']
    c.log.append('visfit (%g-unit voxels): %.1f billion cubic units of playable air, %.1f of it walkable band; hints %d Low, %d Lower, %d Lowest%s'
                 % (s['vs'], s['play'], s['band'], h.get('Low', 0), h.get('Lower', 0), h.get('Lowest', 0),
                    (' (replacing ' + ', '.join('%d %s' % (v, k) for k, v in old.items()) + ')') if old else ''))
    if s['shells']:
        c.log.append('visfit: %d of %d sky shell meshes set to Exclude from Vis, %d kept because they close playable air'
                     % (len(pl['exclude']), s['shells'], s['kept']))
    if pl['extra']: c.log.append('visfit: %d meshes inside %s set to Exclude from Vis' % (len(pl['extra']), extra_visex_box))
    c.todo.append('vis: if anything pops in or out of view where players stand, change the nearest Lower hint to Low (or Low to Medium)')
    return pl
