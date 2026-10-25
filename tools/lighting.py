"""Stationary (dynamic) light pass.

CS:GO lights import as Static (directlight 1, baked only), so weapons / players render black. This picks a minimal set of lights
per sealed compartment and switches them to directlight 3 (Stationary: dynamic direct light, baked shadows; max 4 may overlap), with ranges trimmed so no point in the map is
inside more than MAX_OVERLAP stationary lights. Compartments come from voxelising the world geometry and flood-filling
the empty space; compartments that see sky (moondome / skybox) count as lit by light_environment when the map has one.
"""
import collections, math
import numpy as np
import dmx

TOOL_PASS = ('materials/tools/toolstrigger', 'materials/tools/toolsclip', 'materials/tools/toolsplayerclip', 'materials/tools/toolsnpcclip',
             'materials/tools/toolsinvisible', 'materials/tools/toolsinvisibleladder', 'materials/tools/toolsareaportal', 'materials/tools/toolsoccluder',
             'materials/tools/toolshint', 'materials/tools/toolsskip', 'materials/tools/toolsfog', 'materials/tools/toolslight', 'materials/tools/toolsblocklight',
             'materials/tools/toolsblock_los', 'materials/tools/toolsbuyzone', 'materials/tools/toolsbombsite')
MAX_OVERLAP = 4
LIGHT_CLASSES = ('light_omni2', 'light_spot', 'light_barn', 'light_rect', 'light_capsule', 'light_omni', 'light_ortho')

def mesh_polys(m, node):
    """[(material, [p0, p1, ...])] for a CMapMesh, world space"""
    md = m.g(node, b'meshData')
    if md is None: return []
    E = m.E
    get = lambda k: dmx.get(E[md], k)
    vdi, evi, eni, fei, fdi = get(b'vertexDataIndices'), get(b'edgeVertexIndices'), get(b'edgeNextIndices'), get(b'faceEdgeIndices'), get(b'faceDataIndices')
    mats = [x.decode().lower() for x in get(b'materials') or []]
    pos = None; matidx = None
    for st in dmx.get(E[get(b'vertexData')], b'streams'):
        if E[st]['name'].startswith(b'position'): pos = dmx.get(E[st], b'data')
    for st in dmx.get(E[get(b'faceData')], b'streams'):
        if E[st]['name'].startswith(b'materialindex'): matidx = dmx.get(E[st], b'data')
    if pos is None or not fei: return []
    o = m.g(node, b'origin', [0, 0, 0])
    out = []
    for f, e0 in enumerate(fei):
        loop = []; e = e0
        for _ in range(4096):                       # big ground faces can have hundreds of vertices; a truncated loop drew wedges
            v = evi[e]; p = pos[vdi[v]]; loop.append((p[0] + o[0], p[1] + o[1], p[2] + o[2]))
            e = eni[e]
            if e == e0: break
        mi = matidx[fdi[f]] if matidx else 0
        out.append((mats[mi] if mi < len(mats) else '', loop))
    return out

def world_polys(m):
    """polygons of world geometry (meshes not inside entities)"""
    polys = []
    def walk(n):
        for c in m.children(n):
            t = m.type(c)
            if t == b'CMapMesh': polys.extend(mesh_polys(m, c))
            elif t == b'CMapGroup': walk(c)
    walk(m.world)
    return polys

def voxelise(polys, vs):
    pts_all = np.array([p for _, l in polys for p in l], np.float64)
    lo = pts_all.min(0) - 2 * vs; hi = pts_all.max(0) + 2 * vs
    shape = tuple(int(x) for x in np.ceil((hi - lo) / vs))
    solid = np.zeros(shape, np.uint8)   # 1 wall, 2 sky
    for mat, loop in polys:
        if mat.startswith(TOOL_PASS): continue
        kind = 2 if ('moondome' in mat or 'toolsskybox' in mat) else 1
        P = np.array(loop, np.float64)
        for i in range(1, len(P) - 1):
            a, b, c = P[0], P[i], P[i + 1]
            n = int(max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b)) / (vs * 0.4)) + 2
            u, w = np.meshgrid(np.linspace(0, 1, n), np.linspace(0, 1, n))
            k = (u + w) <= 1
            q = a + np.outer(u[k], b - a) + np.outer(w[k], c - a)
            idx = np.floor((q - lo) / vs).astype(int)
            idx = np.clip(idx, 0, np.array(shape) - 1)
            cur = solid[idx[:, 0], idx[:, 1], idx[:, 2]]
            solid[idx[:, 0], idx[:, 1], idx[:, 2]] = np.maximum(cur, kind)
    return solid, lo

def label_empty(solid):
    from scipy import ndimage
    lab, n = ndimage.label(solid == 0)
    return lab, n

def run(m, c, vs=32.0):
    lights = m.by_class(*LIGHT_CLASSES)
    if not lights: return
    polys = world_polys(m)
    if not polys: return
    solid, lo = voxelise(polys, vs)
    lab, n = label_empty(solid)
    shape = np.array(solid.shape)
    exterior = set(np.unique(np.concatenate([lab[0].ravel(), lab[-1].ravel(), lab[:, 0].ravel(), lab[:, -1].ravel(), lab[:, :, 0].ravel(), lab[:, :, -1].ravel()])))
    from scipy import ndimage
    sky = ndimage.binary_dilation(solid == 2)
    sky_labels = set(np.unique(lab[sky & (lab > 0)]))
    has_env = bool(m.by_class('light_environment'))
    def vox(p): return tuple(np.clip(np.floor((np.array(p) - lo) / vs).astype(int), 0, shape - 1))
    def region_of(p):
        i = vox(p)
        if lab[i]: return lab[i]
        # light sits in a wall voxel: nearest empty voxel within 2 cells
        best = None
        for d in [(dx, dy, dz) for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2) for dz in (-2, -1, 0, 1, 2)]:
            j = tuple(np.clip(np.array(i) + d, 0, shape - 1))
            if lab[j] and (best is None or sum(x * x for x in d) < best[0]): best = (sum(x * x for x in d), lab[j])
        return best[1] if best else 0
    by_region = collections.defaultdict(list)
    for e in lights:
        by_region[region_of(m.origin(e))].append(e)
    # region voxel centres (subsampled) for coverage / overlap checks
    sizes = ndimage.sum(np.ones_like(lab), lab, index=np.arange(n + 1))
    centres = {}
    for r in by_region:
        if r == 0 or r in exterior: continue
        idx = np.argwhere(lab == r)
        if len(idx) > 4000: idx = idx[np.random.RandomState(r).choice(len(idx), 4000, replace=False)]
        centres[r] = lo + (idx + 0.5) * vs
    chosen = []            # (entity, pos, range)
    all_samples = np.concatenate(list(centres.values())) if centres else np.zeros((0, 3))
    overlap = np.zeros(len(all_samples), np.int32)
    offs = {}; k = 0
    for r, pts in centres.items(): offs[r] = (k, k + len(pts)); k += len(pts)
    already = [e for e in lights if m.P(e, 'directlight') in ('2', '3')]
    for e in already:
        p = np.array(m.origin(e)); rg = float(m.P(e, 'range', '512') or 512)
        overlap += (np.linalg.norm(all_samples - p, axis=1) < rg)
    # rooms players can reach (spawns / teleport targets) with no light at all get a new stationary light first
    play = collections.Counter(region_of(m.origin(e)) for e in m.by_class('info_player_terrorist', 'info_player_counterterrorist', 'info_teleport_destination'))
    unlit = [r for r in play if r and r not in exterior and r not in by_region and sizes[r] >= 8]
    tmpl = next(iter(m.by_class('light_omni2')), None)
    added = 0
    for r in unlit:
        idx = np.argwhere(lab == r)
        want = np.array([idx[:, 0].mean(), idx[:, 1].mean(), idx[:, 2].max() - 1])
        v = idx[np.argmin(((idx - want) ** 2).sum(1))]
        p = lo + (v + 0.5) * vs
        rg = float(np.linalg.norm((idx - v) * vs, axis=1).max()) + 64
        while rg > 128 and (overlap[np.linalg.norm(all_samples - p, axis=1) < rg] >= MAX_OVERLAP).any(): rg *= 0.85
        props = {a[0].decode(): a[2].decode() for a in m.props(tmpl)['attrs'] if a[0] not in (b'classname', b'targetname')} if tmpl else {}
        props.update({'directlight': '3', 'range': '%.0f' % rg, 'enabled': '1', 'color': '255 255 255'})
        m.new_entity('light_omni2', p, props); added += 1
        overlap += (np.linalg.norm(all_samples - p, axis=1) < rg)
    if added: c.log.append('added %d stationary light_omni2 to sealed rooms with spawns / teleport destinations that had no light at all' % added)
    report = {}; skipped_sky = 0
    MIN_VOX = 64                                          # smaller pockets (lamp housings, vents) don't count as rooms
    regions = [r for r in by_region if r and r not in exterior and r in centres and sizes[r] >= MIN_VOX]
    if has_env: skipped_sky = sum(1 for r in regions if r in sky_labels); regions = [r for r in regions if r not in sky_labels]
    regions = [r for r in regions if not any(e in already for e in by_region[r])]
    covered = {r: np.zeros(len(centres[r]), bool) for r in regions}
    def fit(p, rg):
        while rg >= 128:
            if not (overlap[np.linalg.norm(all_samples - p, axis=1) < rg] >= MAX_OVERLAP).any(): return rg
            rg *= 0.85
        return None
    def take(r, e, p, rg):
        nonlocal overlap
        chosen.append((e, p, rg)); overlap += (np.linalg.norm(all_samples - p, axis=1) < rg)
        covered[r] |= np.linalg.norm(centres[r] - p, axis=1) < rg
    # pass 1: every room gets one light, smallest rooms first so the big ones can't crowd them out
    for r in sorted(regions, key=lambda r: sizes[r]):
        pts = centres[r]; best = None
        for e in by_region[r]:
            p = np.array(m.origin(e)); rg0 = float(m.P(e, 'range', '512') or 512)
            d = np.linalg.norm(pts - p, axis=1)
            rg = fit(p, max(min(rg0, float(np.percentile(d, 95)) + 64), 192.0))
            if rg is None: continue
            gain = int((d < rg).sum())
            if best is None or gain > best[0]: best = (gain, e, p, rg)
        if best: take(r, best[1], best[2], best[3])
        report[r] = 1 if best else 0
    # pass 2: top up rooms that are still mostly uncovered
    for r in sorted(regions, key=lambda r: covered[r].mean()):
        pts = centres[r]
        while report[r] and report[r] < 6 and covered[r].mean() < 0.85:
            best = None
            for e in by_region[r]:
                if any(e is x[0] for x in chosen): continue
                p = np.array(m.origin(e)); rg0 = float(m.P(e, 'range', '512') or 512)
                d = np.linalg.norm(pts - p, axis=1); left = d[~covered[r]]
                if not len(left): continue
                rg = fit(p, max(min(rg0, float(np.percentile(left, 90)) + 64), 192.0))
                if rg is None: continue
                gain = int(((d < rg) & ~covered[r]).sum())
                if best is None or gain > best[0]: best = (gain, e, p, rg)
            if best is None or best[0] < 0.08 * len(pts): break
            take(r, best[1], best[2], best[3]); report[r] += 1
    report = [(r, len(by_region[r]), report[r], round(float(covered[r].mean()), 2)) for r in regions]
    for e, p, rg in chosen:
        m.setp(e, 'directlight', '3')
        old = float(m.P(e, 'range', '0') or 0)
        if rg < old - 1: m.setp(e, 'range', '%.0f' % rg)
    none = [x for x in report if x[2] == 0]
    if none: c.todo.append('%d compartments could not get a stationary light without going over %d overlapping - check them' % (len(none), MAX_OVERLAP))
    c.log.append('stationary lights: %d of %d lights switched Static -> Stationary (directlight 3) across %d sealed compartments, ranges trimmed so no spot is inside more than %d%s'
                 % (len(chosen), len(lights), len(report), MAX_OVERLAP, '; %d compartments open to sky left to light_environment' % skipped_sky if skipped_sky else ''))
    weak = [x for x in report if x[3] < 0.6]
    if weak: c.todo.append('%d compartments only partly covered by stationary light (overlap cap) - check weapons are lit there' % len(weak))
    return report
