"""Stationary (dynamic) light pass.

CS:GO lights import as Static (directlight 1, baked only), so weapons / players render black. This picks a minimal set of lights
per sealed compartment and switches them to directlight 3 (Stationary: dynamic direct light, baked shadows; max 4 may overlap), with ranges trimmed so no point in the map is
inside more than MAX_OVERLAP stationary lights. Compartments come from voxelising the world geometry and flood-filling
the empty space. Compartments open to the sky get at least one stationary light as well: light_environment alone leaves weapons and
players flat (skink52's rule, 29 Oct 2026: a room with no roof needs a dynamic light source on top of the light_environment).
"""
import collections, math, os
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
    # the importer makes light_environment Static (directlight 1, baked only): outdoors players and weapons then get no sun at all
    for env in m.by_class('light_environment'):
        if (m.P(env, 'directlight', '1') or '1') == '1':
            m.setp(env, 'directlight', '3'); c.log.append('light_environment: Static -> Stationary (directlight 3), so the sun lights players and weapons')
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
    # a map open to the void (no sky shell) puts its outdoor play space in the exterior region: treat that like open sky when players are in it
    open_ext = {r for r in play if r and r in exterior}
    sky_labels = sky_labels | open_ext
    exterior = exterior - open_ext
    for r in open_ext:
        if r not in centres:
            idx = np.argwhere(lab == r)
            pts_r = lo + (idx + 0.5) * vs
            near = np.zeros(len(pts_r), bool)
            for e in m.by_class('info_player_terrorist', 'info_player_counterterrorist', 'info_teleport_destination'):
                near |= np.linalg.norm(pts_r - np.array(m.origin(e)), axis=1) < 2048
            pts_r = pts_r[near] if near.any() else pts_r
            if len(pts_r) > 4000: pts_r = pts_r[np.random.RandomState(r).choice(len(pts_r), 4000, replace=False)]
            centres[r] = pts_r
            offs[r] = (len(all_samples), len(all_samples) + len(pts_r))
            all_samples = np.concatenate([all_samples, pts_r]); overlap = np.concatenate([overlap, np.zeros(len(pts_r), np.int32)])
            for e in already:
                p = np.array(m.origin(e)); rg = float(m.P(e, 'range', '512') or 512)
                overlap[-len(pts_r):] += (np.linalg.norm(pts_r - p, axis=1) < rg)
    unlit = [r for r in play if r and r not in exterior and r not in by_region and sizes[r] >= 8]     # sealed or open to sky
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
    skipped_sky = sum(1 for r in regions if r in sky_labels)    # open-to-sky compartments: one stationary light each (no top-up)
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
        while report[r] and report[r] < (3 if r in sky_labels else 6) and covered[r].mean() < 0.85:
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
                 % (len(chosen), len(lights), len(report), MAX_OVERLAP, '; %d of the compartments are open to sky (one stationary light each, on top of light_environment)' % skipped_sky if skipped_sky else ''))
    weak = [x for x in report if x[3] < 0.6 and x[0] not in sky_labels]
    if weak: c.todo.append('%d compartments only partly covered by stationary light (overlap cap) - check weapons are lit there' % len(weak))
    return report


# ------------------------------------------------------------------ light brightness (importer NaN bug)
def fix_nan_brightness(m, c):
    """Valve's importer writes brightness = nan for most CS:GO lights (see fix_brightness). Set those to 0 / legacy 1, which is
    what Hammer itself does when it re-saves the map, so a command-line build sees the same values as a Hammer build."""
    import math
    n = 0
    for e in m.by_class('light_omni2', 'light_barn', 'light_rect', 'light_capsule'):
        try: ok = math.isfinite(float(m.P(e, 'brightness', '0') or 0))
        except ValueError: ok = False
        if not ok: m.setp(e, 'brightness', '0'); m.setp(e, 'brightness_legacy', '1'); n += 1
    if n: c.log.append('%d lights had brightness = nan from the importer: set to 0 (as a Hammer save does); stage_d lightbright rebuilds real values from the VMF' % n)

FIT_DIST = 128.0          # distance at which non-quadratic CS:GO lights are matched (room scale)
RANGE_Q = 1600.0          # the importer's range for a legacy-1 quadratic light


def falloff_ratio(e):
    """CS:GO illuminance at FIT_DIST relative to a quadratic light of the same _light value (1.0 for quadratic lights)"""
    def f(k):
        try: return float(e.get(k) or 0)
        except ValueError: return 0.0
    d = FIT_DIST
    if f('_fifty_percent_distance') > 0:
        d50 = f('_fifty_percent_distance'); d0 = f('_zero_percent_distance')
        if d0 < d50: d0 = 2.0 * d50
        # vrad SolveInverseQuadraticMonotonic(0,1, d50,2, d0,256): quadratic through the three points; fall back to linear if it dips
        A = [[0, 0, 1], [d50 * d50, d50, 1], [d0 * d0, d0, 1]]
        import numpy as _np
        try: a, b, cc = _np.linalg.solve(_np.array(A, float), _np.array([1.0, 2.0, 256.0]))
        except Exception: a, b, cc = 0.0, 1.0, 0.0
        if b < 0 or a < 0: a, b, cc = 0.0, 1.0, 0.0          # not monotonic on [0, d0]
        s = 2.0 / (cc + d50 * (b + d50 * a)); a, b, cc = a * s, b * s, cc * s
        attn = lambda x: cc + b * x + a * x * x
        return (attn(100.0) / attn(d)) / (1e4 / (d * d))
    q, l, k = f('_quadratic_attn'), f('_linear_attn'), f('_constant_attn')
    if q == 0 and l == 0 and k == 0: q = 1.0
    if l == 0 and k == 0: return 1.0
    attn = lambda x: k + l * x + q * x * x
    return (attn(100.0) / attn(d)) / (1e4 / (d * d))


def fix_brightness(m, c, vmfpath):
    """Valve's importer stores log2(intensity/265) in brightness_legacy and then log2 of that in brightness, so every CS:GO light
    dimmer than ~265 (3-value _light, linear attenuation, most maps) gets brightness = nan, which crashes the server on map load,
    and brighter ones come out too dim. Rebuild from the VMF: I = _light 4th value (255 when only r g b), times (max rgb/255)^2.2
    because the importer normalises the colour; legacy = I/265 (linear), brightness = log2(legacy), lumens/candelas/nits from it.
    CS:GO's _light brightness is the value at 100 units for every falloff (vrad scales the intensity by attn(100)). Quadratic lights
    match CS2's inverse square as above. Lights with _fifty_percent_distance (or linear/constant attenuation) fall off differently:
    vrad's quadratic solve for 1 / 50% / 1/256 at 0 / d50 / d0 is never monotonic for the default d0 = 2 x d50, so it falls back to
    linear falloff, I x 100 / d. The importer gave those ~8x the brightness and a 9,000-17,000 unit range (ttt_cg_skyscraper_2017's
    lower floors far brighter than in CS:GO). They are matched to CS:GO at FIT_DIST units instead: legacy = I x f(FIT_DIST) x FIT_DIST^2
    / (265 x 10^4) with f the CS:GO falloff relative to 100 units, and range = RANGE_Q x sqrt(legacy)."""
    import re, math, vmf as vmfmod
    if not os.path.exists(vmfpath): return
    root = vmfmod.parse(open(vmfpath, encoding='utf-8', errors='replace').read())
    src = []
    for e in root.ch:
        cls = (e.get('classname') or '').lower()
        if e.name != 'entity' or cls not in ('light', 'light_spot') or not e.get('origin'): continue
        lv = [float(x) for x in (e.get('_light') or '255 255 255 200').split()[:4]]
        if len(lv) == 1: lv = lv * 3
        sc = lv[3] if len(lv) > 3 else 255.0
        mx = max(lv[:3]) or 1.0
        ieff = sc * (mx / 255.0) ** 2.2
        ratio = falloff_ratio(e)
        src.append((cls, [float(x) for x in e.get('origin').split()], ieff * ratio, ratio != 1.0))
    lights = [(e, m.origin(e)) for e in m.by_class('light_omni2', 'light_barn')]
    used = set(); fixed = nan = nspecial = 0
    for cls, o, ieff, special in src:
        want = 'light_omni2' if cls == 'light' else 'light_barn'
        cand = [(sum((a - b) ** 2 for a, b in zip(p, o)), e) for e, p in lights if m.cls(e) == want and e not in used]
        if not cand: continue
        d2, e = min(cand, key=lambda x: x[0])
        if d2 > 64 ** 2: continue
        used.add(e)
        def num(k, d):
            try:
                v = float(m.P(e, k, '') or d); return v if math.isfinite(v) else d
            except ValueError: return d
        if not math.isfinite(num('brightness', float('nan'))): nan += 1
        old_leg = num('brightness_legacy', 1.0)
        leg = max(ieff / 265.0, 1e-4)
        m.setp(e, 'brightness_legacy', '%g' % round(leg, 6)); m.setp(e, 'brightness', '%g' % round(math.log2(leg), 6))
        if special:
            m.setp(e, 'range', '%.0f' % max(256.0, RANGE_Q * math.sqrt(leg))); nspecial += 1
        if m.cls(e) == 'light_omni2':
            m.setp(e, 'brightness_lumens', '%d' % max(1, round(1000 * leg)))
            m.setp(e, 'brightness_candelas', '%d' % max(1, round(1000 * leg / (4 * math.pi))))
            m.setp(e, 'brightness_nits', '%d' % max(1, round(9816 * leg)))
        else:   # barn: lumens scale with the cone; the importer's lumens were for its own (log) legacy value
            base = num('brightness_lumens', 1000.0) / (old_leg if old_leg > 0 else 1.0)
            m.setp(e, 'brightness_lumens', '%d' % max(1, round(base * leg)))
        fixed += 1
    def finite(s):
        try: return math.isfinite(float(s))
        except (TypeError, ValueError): return False
    left = [e for e, _ in lights if not finite(m.P(e, 'brightness', '0'))]
    for e in left:   # no VMF match: neutral brightness so nothing is left as nan
        m.setp(e, 'brightness', '0'); m.setp(e, 'brightness_legacy', '1')
    c.log.append('light brightness rebuilt from the CS:GO _light values for %d lights (%d had brightness = nan from the importer, which crashes CS2 on map load)%s%s'
                 % (fixed, nan, '; %d unmatched lights set to brightness 0' % len(left) if left else '',
                    '; %d lights with _fifty_percent_distance / linear falloff matched to CS:GO at %d units, range %d x sqrt(legacy)' % (nspecial, FIT_DIST, RANGE_Q) if nspecial else ''))
