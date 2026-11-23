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
            # in chunks: an open exterior can be ~90M voxels, and building every point at once needed > 6 GB
            # (mg_nature_multigames ran out of memory, 9 Nov 2026). Same order and seed as before, so the same sample.
            flat = np.flatnonzero(lab == r)
            spots = [np.array(m.origin(e), float) for e in m.by_class('info_player_terrorist', 'info_player_counterterrorist', 'info_teleport_destination')]
            keep = []
            for s in range(0, len(flat), 4000000):
                f = flat[s:s + 4000000]
                p = lo + (np.stack(np.unravel_index(f, lab.shape), axis=1) + 0.5) * vs
                nr = np.zeros(len(f), bool)
                for q in spots: nr |= np.linalg.norm(p - q, axis=1) < 2048
                keep.append(f[nr])
            sel = np.concatenate(keep) if keep else flat[:0]
            if not len(sel): sel = flat
            if len(sel) > 4000: sel = sel[np.random.RandomState(r).choice(len(sel), 4000, replace=False)]
            pts_r = lo + (np.stack(np.unravel_index(sel, lab.shape), axis=1) + 0.5) * vs
            centres[r] = pts_r
            offs[r] = (len(all_samples), len(all_samples) + len(pts_r))
            all_samples = np.concatenate([all_samples, pts_r]); overlap = np.concatenate([overlap, np.zeros(len(pts_r), np.int32)])
            for e in already:
                p = np.array(m.origin(e)); rg = float(m.P(e, 'range', '512') or 512)
                overlap[-len(pts_r):] += (np.linalg.norm(pts_r - p, axis=1) < rg)
    unlit = [r for r in play if r and r not in exterior and r not in by_region and sizes[r] >= 8]     # sealed or open to sky
    tmpl = next(iter(m.by_class('light_omni2')), None)
    def _leg(e):
        try: v = float(m.P(e, 'brightness_legacy', '') or 'nan'); return v if math.isfinite(v) and v > 0 else None
        except ValueError: return None
    _legs = sorted(x for x in (_leg(e) for e in m.by_class('light_omni2')) if x)
    med_leg = _legs[len(_legs) // 2] if _legs else None     # added lights get the map's median brightness, not whatever the first light had
    added = 0
    for r in unlit:
        idx = np.argwhere(lab == r)
        want = np.array([idx[:, 0].mean(), idx[:, 1].mean(), idx[:, 2].max() - 1])
        v = idx[np.argmin(((idx - want) ** 2).sum(1))]
        p = lo + (v + 0.5) * vs
        rg = float(np.linalg.norm((idx - v) * vs, axis=1).max()) + 64
        while rg > 128 and (overlap[np.linalg.norm(all_samples - p, axis=1) < rg] >= MAX_OVERLAP).any(): rg *= 0.85
        props = {a[0].decode(): a[2].decode() for a in m.props(tmpl)['attrs'] if a[0] not in (b'classname', b'targetname')} if tmpl else {}
        props.update({'directlight': '3', 'range': '%.0f' % rg, 'enabled': '1', 'color': '255 255 255', 'colormode': '0', 'castshadows': '0',
                      'light_style': '', 'targetname': ''})
        if med_leg: props.update({'brightness_legacy': '%g' % round(med_leg, 6), 'brightness': '%g' % round(math.log2(med_leg), 6),
                                  'brightness_lumens': '%d' % round(1000 * med_leg), 'brightness_candelas': '%d' % round(1000 * med_leg / (4 * math.pi)),
                                  'brightness_nits': '%d' % round(9816 * med_leg)})
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


# Source 1 light style presets (a = dark, m = normal, z = double); from cs2-slop-porting rebuild_lighting.py (MIT)
LIGHT_STYLES = {1: 'mmnmmommommnonmmonqnmmo', 2: 'abcdefghijklmnopqrstuvwxyzyxwvutsrqponmlkjihgfedcba', 3: 'mmmmmaaaaammmmmaaaaaabcdefgabcdefg',
                4: 'mamamamamama', 5: 'jklmnopqrstuvwxyzyxwvutsrqponmlkj', 6: 'nmonqnmomnmomomno', 7: 'mmmaaaabcdefgmmmmaaaammmaamm',
                8: 'mmmaaammmaaammmabcdefaaaammmmabcdefmmmaaaa', 9: 'aaaaaaaazzzzzzzz', 10: 'mmamammmmammamamaaamammma',
                11: 'abcdefghijklmnopqrrqponmlkjihgfedcba'}


def vmf_light(e):
    """VMF light -> (r, g, b normalised to 255, effective intensity), using the HDR values CS2 renders: _lightHDR "-1 -1 -1 s" means
    _light times s, otherwise it replaces colour and intensity; times _lightscaleHDR; times (max rgb/255)^2.2 because the colour is normalised."""
    def fl(v, d):
        try: return float(v)
        except (TypeError, ValueError): return d
    lv = [fl(x, 255.0) for x in (e.get('_light') or '255 255 255 200').split()[:4]]
    if len(lv) == 1: lv = lv * 3
    r, g, b = (lv + [255.0] * 3)[:3]
    inten = lv[3] if len(lv) > 3 else 255.0
    hdr = ([fl(x, -1.0) for x in (e.get('_lightHDR') or '-1 -1 -1 1').split()] + [-1.0, -1.0, -1.0, 1.0])[:4]
    if min(hdr[:3]) >= 0:
        r, g, b = hdr[:3]; inten = hdr[3] if hdr[3] > 0 else inten
    elif hdr[3] > 0:
        inten *= hdr[3]
    sc = fl(e.get('_lightscaleHDR'), 1.0)
    inten *= sc if sc > 0 else 1.0
    mx = max(r, g, b)
    if mx <= 0: return 255.0, 255.0, 255.0, 0.0
    return r * 255.0 / mx, g * 255.0 / mx, b * 255.0 / mx, inten * (mx / 255.0) ** 2.2


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
    targeted = {(cn.get(k) or '').split(',')[0].split('\x1b')[0].lower() for e in root.ch if e.name == 'entity'
                for cn in e.ch if cn.name == 'connections' for k, _ in cn.kv}
    targeted.discard('')
    sunspread = 0.0
    for e in root.ch:
        cls = (e.get('classname') or '').lower()
        if e.name == 'entity' and cls == 'light_environment':
            try: sunspread = float(e.get('SunSpreadAngle') or 0)
            except ValueError: pass
        if e.name != 'entity' or cls not in ('light', 'light_spot') or not e.get('origin'): continue
        r, g, b, ieff = vmf_light(e)
        ratio = falloff_ratio(e)
        try: style = int(float(e.get('style') or 0))
        except ValueError: style = 0
        try: dark = int(float(e.get('spawnflags') or 0)) & 1
        except ValueError: dark = 0
        name = (e.get('targetname') or '').lower()
        src.append((cls, [float(x) for x in e.get('origin').split()], ieff * ratio, ratio != 1.0,
                    '%d %d %d' % (round(r), round(g), round(b)), style, dark, bool(name and name in targeted)))
    lights = [(e, m.origin(e)) for e in m.by_class('light_omni2', 'light_barn')]
    used = set(); fixed = nan = nspecial = ndyn = nstyle = 0
    for cls, o, ieff, special, col, style, dark, switched in src:
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
        m.setp(e, 'color', col); m.setp(e, 'colormode', '0')     # the importer writes a 6600 K white (colour temperature)
        if dark: m.setp(e, 'enabled', '0')
        if style in LIGHT_STYLES: m.setp(e, 'light_style', LIGHT_STYLES[style]); nstyle += 1
        if (dark or switched or style) and m.P(e, 'directlight') not in ('2', '3'):
            m.setp(e, 'directlight', '2'); ndyn += 1             # a Static (baked) light cannot be switched or flicker
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
    if ndyn: c.log.append('%d switched / start-dark / styled lights set to Dynamic (directlight 2)' % ndyn)
    if nstyle: c.todo.append('%d lights got a CS:GO light style pattern in light_style: check they flicker in game' % nstyle)
    if sunspread > 0:
        for e in m.by_class('light_environment'):
            try: cur = float(m.P(e, 'angulardiameter', '0') or 0)
            except ValueError: cur = 0.0
            if cur == 0: m.setp(e, 'angulardiameter', '%g' % sunspread)


# ------------------------------------------------------------------ relight: delete every light and rebuild it from the VMF
# Hammer-saved light_omni2 / light_barn properties (from cs2-slop-porting rebuild_lighting.py, MIT); everything not set from the VMF
_LIGHT_COMMON = {
    'vscripts': '', 'parentname': '', 'parentAttachmentName': '', 'useLocalOffset': '0', 'local.origin': '', 'local.angles': '', 'local.scales': '',
    'clientSideEntity': '1', 'brightness_units': '1', 'enabled': '1', 'directlight': '1', 'colormode': '0', 'colortemperature': '6600',
    'skirt': '0', 'bouncelight': '1', 'bouncescale': '1.0', 'lightcookie': '', 'bakespeculartocubemaps': '0', 'minroughness': '0', 'castshadows': '2',
    'shadowmapsize': '-1', 'shadowpriority': '-1', 'pvs_modify_entity': '0', 'shadowfade_size_start': '.10', 'shadowfade_size_end': '.05',
    'brightnessscale': '1.0', 'rendertocubemaps': '1', 'fade_size_start': '.05', 'fade_size_end': '.025', 'light_style': '',
    'light_style_output_event0': '', 'light_style_output_event1': '', 'light_style_output_event2': '', 'light_style_output_event3': '',
    'light_style_target0': '', 'light_style_target1': '', 'light_style_target2': '', 'light_style_target3': '',
    'bakespeculartocubemaps_scale': '1.0', 'transmit_always': '0'}
OMNI_DEFAULTS = dict(_LIGHT_COMMON, shape='0', size_params='2.0 24.0 0.15', outer_angle='180.0', inner_angle='180.0', showlight='0')
BARN_DEFAULTS = dict(_LIGHT_COMMON, skirt_near='0', luminaire_shape='1', luminaire_size='4', luminaire_anisotropy='0', shape='1', shear='0.0 0.0',
                     bakespeculartocubemaps_size='6.0 6.0 0.0', forceshadowsenabled='0')
DELETE_LIGHTS = ('light_omni2', 'light_barn', 'light_rect', 'light_capsule', 'light_omni', 'light_ortho', 'light_spot', 'light')
OMNI_RANGE_K = 3.3856e6      # range^2 = legacy x K for a quadratic light with no _distance (fits the importer: I=200 -> 1598)


def _cone_solid_angle(outer_deg):
    t = math.tan(math.radians(min(max(outer_deg, 1.0), 89.0))); s2 = t * t / (1.0 + t * t)
    return 4.0 * math.asin(min(s2, 1.0))


def relight(m, c, vmfpath, scale=1.0):
    """Stage D pass `relight`: the importer's lights are wrong in several ways at once (nan brightness, 6600 K white, HDR ignored, switched lights
    Static, spot cones approximated), so throw every point/spot light away and build each one again from the VMF: light -> light_omni2,
    light_spot -> light_barn (cone -> size/softness, pitch / target entity -> direction), real colour, HDR intensity with our CS:GO falloff fit,
    range from _zero_percent_distance / _distance, start-dark / switched / styled lights Dynamic. light_environment is kept. Lights the stationary
    pass or ventlight added are deleted too, so run `lights` (and `ventlight` if used) afterwards. Method from cs2-slop-porting rebuild_lighting.py (MIT)."""
    import vmf as vmfmod
    if not os.path.exists(vmfpath):
        c.todo.append('relight: no VMF at %s - lights left as imported' % vmfpath); return 0
    root = vmfmod.parse(open(vmfpath, encoding='utf-8', errors='replace').read())
    ents = [e for e in root.ch if e.name == 'entity']
    targeted = {(cn.get(k) or '').split(',')[0].split('\x1b')[0].lower() for e in ents for cn in e.ch if cn.name == 'connections' for k, _ in cn.kv}
    targeted.discard('')
    by_name = {(e.get('targetname') or '').lower(): e for e in ents if e.get('targetname')}
    gone = 0
    for e in [e for e in m.entities() if m.cls(e) in DELETE_LIGHTS]:
        m.remove_node(e); gone += 1
    def fv(s, n=3):
        try: return ([float(x) for x in (s or '').split()] + [0.0] * n)[:n]
        except ValueError: return [0.0] * n
    def fl(s, d=0.0):
        try: return float(s)
        except (TypeError, ValueError): return d
    n_omni = n_barn = n_dyn = n_style = n_tgt = n_skip = n_fit = 0
    for e in ents:
        cls = (e.get('classname') or '').lower()
        if cls not in ('light', 'light_spot') or not e.get('origin'): continue
        o = fv(e.get('origin'))
        r, g, b, inten = vmf_light(e)
        if inten <= 0: n_skip += 1; continue
        ratio = falloff_ratio(e)
        leg = max(inten * ratio / 265.0 * scale, 1e-4)
        zero, dist = fl(e.get('_zero_percent_distance')), fl(e.get('_distance'))
        if ratio != 1.0: rng = max(256.0, RANGE_Q * math.sqrt(leg)); n_fit += 1
        elif zero > 0: rng = zero
        elif dist > 0: rng = dist
        else: rng = math.sqrt(leg * OMNI_RANGE_K)
        name = e.get('targetname') or ''
        dark = int(fl(e.get('spawnflags'))) & 1
        style = int(fl(e.get('style')))
        switched = bool(name and name.lower() in targeted)
        p = dict(OMNI_DEFAULTS if cls == 'light' else BARN_DEFAULTS)
        p.update({'targetname': name, 'parentname': e.get('parentname') or '', 'color': '%d %d %d' % (round(r), round(g), round(b)),
                  'range': '%g' % round(rng, 1), 'brightness_legacy': '%g' % round(leg, 6), 'brightness': '%g' % round(math.log2(leg), 6),
                  'enabled': '0' if dark else '1'})
        ang = (0.0, 0.0, 0.0)
        if cls == 'light':
            lum = 1000.0 * leg
            p.update({'brightness_lumens': '%d' % max(1, round(lum)), 'brightness_candelas': '%d' % max(1, round(lum / (4 * math.pi))),
                      'brightness_nits': '%d' % max(1, round(9816 * leg))})
            n_omni += 1
        else:
            outer = min(max(fl(e.get('_cone'), 45.0), 1.0), 89.0); inner = fl(e.get('_inner_cone'), 30.0)
            t_out = math.tan(math.radians(outer)); soft = 1.0 - math.tan(math.radians(min(inner, outer))) / t_out
            p.update({'brightness_lumens': '%d' % max(1, round(leg * 1000.0 / (4 * math.pi) * _cone_solid_angle(outer))),
                      'size_params': '1.000000 1.000000 %.6f' % t_out, 'soft_x': '%.6f' % max(0.0, min(1.0, soft)), 'soft_y': '%.6f' % max(0.0, min(1.0, soft))})
            a = fv(e.get('angles'))
            pitch = -fl(e.get('pitch')) if (e.get('pitch') or '') != '' else a[0]     # the pitch key is negative-down, angles positive-down
            yaw, roll = a[1], a[2]
            t = by_name.get((e.get('target') or '').lower())
            if t is not None and t.get('origin'):
                d = [x - y for x, y in zip(fv(t.get('origin')), o)]
                if any(d):
                    pitch = math.degrees(math.atan2(-d[2], math.hypot(d[0], d[1]))); yaw = math.degrees(math.atan2(d[1], d[0])); n_tgt += 1
            ang = (pitch, yaw, roll); n_barn += 1
        if style in LIGHT_STYLES: p['light_style'] = LIGHT_STYLES[style]; n_style += 1
        if dark or switched or style: p['directlight'] = '2'; n_dyn += 1
        m.new_entity('light_omni2' if cls == 'light' else 'light_barn', o, p, angles=ang)
    for e in ents:
        if (e.get('classname') or '').lower() == 'light_environment' and fl(e.get('SunSpreadAngle')) > 0:
            for le in m.by_class('light_environment'):
                if fl(m.P(le, 'angulardiameter', '0')) == 0: m.setp(le, 'angulardiameter', '%g' % fl(e.get('SunSpreadAngle')))
    c.log.append('relight: deleted %d imported lights; rebuilt from the VMF %d light -> light_omni2, %d light_spot -> light_barn (colour, HDR intensity, '
                 'range, cone%s); %d Dynamic (start dark / switched / style)%s%s%s'
                 % (gone, n_omni, n_barn, ', %d aimed at their target' % n_tgt if n_tgt else '', n_dyn,
                    '; %d with linear / fifty-percent falloff fitted to CS:GO at %d u' % (n_fit, FIT_DIST) if n_fit else '',
                    '; %d zero-intensity lights skipped' % n_skip if n_skip else '', '; all scaled by %g' % scale if scale != 1.0 else ''))
    if n_style: c.todo.append('relight: %d lights got a CS:GO light style pattern in light_style - check they flicker in game' % n_style)
    c.todo.append('relight: brightness scale (1000 lumens per 265 _light) is not checked against a real CS2 bake - compare a few rooms with CS:GO')
    return n_omni + n_barn


# ------------------------------------------------------------------ lightcal: brightness from the compiled light list + line traces (opt-in)
# From CS2-Porter lighting.py (MIT, copyright bcanusar), adapted. What we took: the falloff constants vrad really used (the BSP's
# light list, not a re-derivation from the keys), and matching each light over the distances to the surfaces round it (line traces
# through the BSP tree) instead of one fixed distance. What we kept of ours, and why:
#   - the brightness scale (1000 lumens = legacy 1 = a 265 _light at 100 u, the importer's own conversion where it doesn't write nan);
#     CS2-Porter anchors 1000 lumens to a 200 _light because that is what the importer writes for the nan lights, which is
#     Hammer's legacy-1 fallback, not a conversion. So a quadratic light gets the same value from lightcal as from relight.
#   - spot cones: lumens times the cone's share of the sphere (cs2-slop-porting); CS2-Porter says a light_barn of N lumens is as
#     bright as a light_omni2 of N. Neither is checked in game: open question.
#   - no overbright cap on HDR maps (CS2-Porter caps at 4); the LDR cap of 2 (8-bit lightmaps can't show more) is taken.
# Checked against the compiled light list: vrad's _fifty_percent_distance falloff is 2/65.25 x (1 + x/D + 63.25 (x/D)^2), i.e. the
# 50% point traded half-way to a straight line; ttt_cg_skyscraper_2017_b1's 50 such lights all have c = 0.03065. falloff_ratio's
# linear fallback (relight / lightbright) makes them ~8x too bright at 128 u; lightcal fixes that, opt-in until seen in game.
CAL_RAYS = 64
CAL_TRACE = 4096.0
CAL_NEAR = 48.0           # surfaces closer than this are left out (full white in both games) unless too few are further away
CAL_MIN_HITS = 8
CAL_CAP_LDR = 2.0         # an LDR-compiled map's lightmaps hold at most 2x full brightness (overbright)
CAL_DEFAULT_D = (128.0, 256.0, 384.0)
S1_LEGACY1 = 1e4 * 265.0 / 255.0   # vrad intensity of a quadratic 265 _light (white): legacy 1 on our scale
CAL_MATCH = 4.0           # vmap light within this of a compiled light = the same light


class BspTracer:
    """Line traces against the solid leaves of a compiled map's BSP tree (displacements are not in the tree: rays pass through
    them to the brush underneath). From CS2-Porter lighting.py BspTracer (MIT, copyright bcanusar), adapted."""

    def __init__(s, b):
        import struct, texlights as T
        planes = b.lump(T.LUMP_PLANES)
        s.planes = [struct.unpack_from('<4f', planes, o) for o in range(0, len(planes) - 19, 20)]
        nodes = b.lump(T.LUMP_NODES)
        s.nodes = [struct.unpack_from('<3i', nodes, o) for o in range(0, len(nodes) - 31, 32)]
        leafs = b.lump(T.LUMP_LEAFS); size = 56 if b.version(T.LUMP_LEAFS) == 0 else 32
        s.solid = [bool(struct.unpack_from('<i', leafs, o)[0] & 1) for o in range(0, len(leafs) - size + 1, size)]
        models = b.lump(T.LUMP_MODELS)
        s.head = struct.unpack_from('<i', models, 36)[0] if len(models) >= 48 else 0

    def _hit(s, node, f0, f1, p0, p1):
        while node >= 0:
            pn, c0, c1 = s.nodes[node]
            nx, ny, nz, dist = s.planes[pn]
            d0 = nx * p0[0] + ny * p0[1] + nz * p0[2] - dist
            d1 = nx * p1[0] + ny * p1[1] + nz * p1[2] - dist
            if d0 >= 0 and d1 >= 0: node = c0; continue
            if d0 < 0 and d1 < 0: node = c1; continue
            frac = d0 / (d0 - d1); fm = f0 + (f1 - f0) * frac
            pm = (p0[0] + (p1[0] - p0[0]) * frac, p0[1] + (p1[1] - p0[1]) * frac, p0[2] + (p1[2] - p0[2]) * frac)
            near, far = (c0, c1) if d0 >= 0 else (c1, c0)
            hit = s._hit(near, f0, fm, p0, pm)
            if hit is not None: return hit
            node, f0, p0 = far, fm, pm
        leaf = -node - 1
        return f0 if 0 <= leaf < len(s.solid) and s.solid[leaf] else None

    def trace(s, start, d, length=CAL_TRACE):
        """distance to the first solid along the ray, None when nothing is hit within length"""
        end = (start[0] + d[0] * length, start[1] + d[1] * length, start[2] + d[2] * length)
        try: f = s._hit(s.head, 0.0, 1.0, tuple(start), end)
        except RecursionError: f = None
        return None if f is None else f * length


def _sphere(n):
    g = math.pi * (3.0 - math.sqrt(5.0)); out = []
    for i in range(n):
        z = 1.0 - 2.0 * (i + 0.5) / n; r = math.sqrt(max(0.0, 1.0 - z * z)); a = g * i
        out.append((r * math.cos(a), r * math.sin(a), z))
    return out


_DIRS = _sphere(CAL_RAYS)
_DIRS_DENSE = _sphere(CAL_RAYS * 8)


def _solve3(x1, y1, x2, y2, x3, y3):
    det = (x1 - x2) * (x1 - x3) * (x2 - x3)
    if det == 0: return None
    a = (x3 * (-y1 + y2) + x2 * (y1 - y3) + x1 * (-y2 + y3)) / det
    b = (x3 * x3 * (y1 - y2) + x1 * x1 * (y2 - y3) + x2 * x2 * (-y1 + y3)) / det
    c = (x1 * x3 * (-x1 + x3) * y2 + x2 * x2 * (x3 * y1 - x1 * y3) + x2 * (-(x3 * x3 * y1) + x1 * x1 * y3)) / det
    return a, b, c


def vrad_falloff(e):
    """VMF light -> the compiled-light dict world_lights() gives ('intensity' peak channel only, 'c', 'l', 'q', 'radius', 'type',
    'normal', 'stopdot2'), worked out as vrad does, for lights missing from the BSP. _fifty_percent_distance: quadratic through
    (0,1) (d50,y2) (d0,256); while it isn't monotonic, y2 moves towards the straight line in 1% steps (for the usual d0 = 2 x d50
    this lands half-way, y2 = 65.25, as the compiled constants show); scaled so the value at d50 is 2; intensity NOT normalised to
    100 u. Other falloffs: constant / linear / quadratic as given (all 0 -> constant 1), intensity x attn(100)."""
    def fl(k, d=0.0):
        try: return float(e.get(k) or d)
        except ValueError: return d
    _r, _g, _b, inten = vmf_light(e)
    peak = inten / 255.0
    d50 = fl('_fifty_percent_distance'); radius = 0.0
    if d50 > 0:
        d0 = fl('_zero_percent_distance')
        if d0 < d50: d0 = 2.0 * d50
        lin = 1.0 + (256.0 - 1.0) * d50 / d0
        abc = None
        for t in range(0, 101):
            y2 = 2.0 + (lin - 2.0) * t / 100.0
            abc = _solve3(0.0, 1.0, d50, y2, d0, 256.0)
            if abc and abc[0] >= 0 and abc[1] >= 0: break
        a, bb, cc = abc if abc else (0.0, 1.0, 0.0)
        v50 = cc + d50 * (bb + d50 * a); k = 2.0 / v50 if v50 > 0 else 1.0
        cc, l, q = cc * k, bb * k, a * k
    else:
        cc, l, q = max(fl('_constant_attn'), 0.0), max(fl('_linear_attn'), 0.0), max(fl('_quadratic_attn'), 0.0)
        radius = fl('_distance')
        if cc < 1e-4 and l < 1e-4 and q < 1e-4: cc = 1.0
        peak *= cc + 100.0 * l + 1e4 * q
    cone = fl('_cone', 45.0)
    return {'type': 2 if (e.get('classname') or '').lower() == 'light_spot' else 1, 'intensity': (peak, peak, peak), 'c': cc, 'l': l, 'q': q,
            'radius': radius, 'normal': None, 'stopdot2': math.cos(math.radians(cone))}


def s1_brightness(wl, d):
    """Source 1 brightness d units from a compiled light (peak channel; 1 = the texture at full brightness)"""
    if wl.get('radius') and d > wl['radius']: return 0.0
    att = wl['c'] + wl['l'] * d + wl['q'] * d * d
    return max(wl['intensity']) / att if att > 0 else 0.0


def _directions(wl):
    if wl['type'] != 2 or not wl.get('normal'): return _DIRS
    n = wl['normal']
    return [d for d in _DIRS_DENSE if d[0] * n[0] + d[1] * n[1] + d[2] * n[2] >= wl['stopdot2']] or [tuple(n)]


def match_legacy(wl, dists, cap=None):
    """legacy brightness (our scale) of a CS2 inverse-square light that gives the surfaces at `dists` the Source 1 light of wl
    (geometric mean of brightness x d^2, brightness counted up to cap). None when nothing is lit."""
    hits = [d for d in dists if d is not None]
    use = [d for d in hits if d >= CAL_NEAR]
    if len(use) < CAL_MIN_HITS: use = [max(d, 16.0) for d in hits] or list(CAL_DEFAULT_D)
    logs = []
    for d in use:
        s = s1_brightness(wl, d)
        if cap: s = min(s, cap)
        if s > 0: logs.append(math.log(s * d * d))
    if not logs: return None
    return math.exp(sum(logs) / len(logs)) / S1_LEGACY1


def _set_legacy(m, e, leg, quadratic, radius=0.0):
    old_leg = 1.0
    try: old_leg = float(m.P(e, 'brightness_legacy', '1') or 1)
    except ValueError: pass
    if not math.isfinite(old_leg) or old_leg <= 0: old_leg = 1.0
    leg = max(leg, 1e-4)
    m.setp(e, 'brightness_legacy', '%g' % round(leg, 6)); m.setp(e, 'brightness', '%g' % round(math.log2(leg), 6))
    if not quadratic:
        rng = max(256.0, RANGE_Q * math.sqrt(leg))
        m.setp(e, 'range', '%.0f' % (min(rng, radius) if radius > 0 else rng))
    if m.cls(e) == 'light_omni2':
        m.setp(e, 'brightness_lumens', '%d' % max(1, round(1000 * leg)))
        m.setp(e, 'brightness_candelas', '%d' % max(1, round(1000 * leg / (4 * math.pi))))
        m.setp(e, 'brightness_nits', '%d' % max(1, round(9816 * leg)))
    else:
        try: base = float(m.P(e, 'brightness_lumens', '1000') or 1000) / old_leg
        except ValueError: base = 1000.0
        m.setp(e, 'brightness_lumens', '%d' % max(1, round(base * leg)))


def lightmap_check(b, tracer, comp, limit=40):
    """How well the compiled falloff predicts what CS:GO baked: for floor points straight under up to `limit` point lights, the
    compiled lightmap luxel (style 0, peak channel, 1 = full brightness) over the sum of every listed light's direct light there
    (cosine-weighted, lights behind a wall left out, no bounce). Returns (median ratio, samples) or (None, 0). mg_antique_course (HDR): 0.92 over 60."""
    import struct, statistics, texlights as T
    hdr = T.hdr_lit(b)
    lm = b.lump(T.LUMP_LIGHTING_HDR if hdr else T.LUMP_LIGHTING)
    fdata = b.lump(T.LUMP_FACES_HDR) if hdr and b.size(T.LUMP_FACES_HDR) else b.lump(T.LUMP_FACES)
    if not lm or not fdata: return None, 0
    ti, vdata, edata, sdata, pdata = (b.lump(i) for i in (T.LUMP_TEXINFO, T.LUMP_VERTEXES, T.LUMP_EDGES, T.LUMP_SURFEDGES, T.LUMP_PLANES))
    floors = []
    for o in range(0, len(fdata) - 55, 56):
        pn, side, _on, first, num, tix = struct.unpack_from('<HBBihh', fdata, o)
        lofs, = struct.unpack_from('<i', fdata, o + 20)
        if lofs < 0 or tix < 0 or fdata[o + 16] == 255: continue
        n = struct.unpack_from('<3f', pdata, pn * 20)
        if side: n = tuple(-x for x in n)
        if n[2] < 0.9: continue
        pts = []
        for k in range(num):
            se = struct.unpack_from('<i', sdata, (first + k) * 4)[0]
            a, c2 = struct.unpack_from('<2H', edata, abs(se) * 4)
            pts.append(struct.unpack_from('<3f', vdata, (a if se >= 0 else c2) * 12))
        floors.append((pts, n, lofs, struct.unpack_from('<2i', fdata, o + 28), struct.unpack_from('<2i', fdata, o + 36), struct.unpack_from('<8f', ti, tix * 72 + 32)))
    def luxel(p):
        for pts, n, lofs, mins, size, lv in floors:
            if abs(sum((p[k] - pts[0][k]) * n[k] for k in range(3))) > 1.0 or not T._inside(p, pts, n): continue
            s_ = min(max(int(round(sum(p[k] * lv[k] for k in range(3)) + lv[3] - mins[0])), 0), size[0])
            t_ = min(max(int(round(sum(p[k] * lv[4 + k] for k in range(3)) + lv[7] - mins[1])), 0), size[1])
            i = lofs + 4 * (t_ * (size[0] + 1) + s_)
            if i + 4 > len(lm): return None
            r, g, bb, e = struct.unpack_from('<BBBb', lm, i)
            return max(r, g, bb) * 2.0 ** e / 255.0
        return None
    ratios = []
    for w in [w for w in comp if w['type'] == T.EMIT_POINT and w['style'] == 0][:limit]:
        o = w['origin']; h = tracer.trace(o, (0.0, 0.0, -1.0), 2048.0)
        if not h or h < 16: continue
        p = (o[0], o[1], o[2] - h)
        meas = luxel(p)
        q = (p[0], p[1], p[2] + 1.0); pred = 0.0
        for v in comp:
            if v['type'] != T.EMIT_POINT or v['origin'][2] <= q[2]: continue
            d = max(math.dist(v['origin'], p), 1.0); s = s1_brightness(v, d); cos = (v['origin'][2] - p[2]) / d
            if s * cos < 1e-4: continue
            dq = max(math.dist(v['origin'], q), 1.0)
            hit = tracer.trace(q, tuple((v['origin'][k] - q[k]) / dq for k in range(3)), dq)   # traced from 1 u above the floor
            if hit is not None and hit < dq - 2.0: continue              # wall in between: no direct light
            pred += s * cos
        if meas and pred > 0: ratios.append(meas / pred)
    return (statistics.median(ratios), len(ratios)) if ratios else (None, 0)


def relight_legacy(e):
    """the legacy brightness relight / lightbright give a VMF light (our CS:GO falloff fit at FIT_DIST)"""
    _r, _g, _b, inten = vmf_light(e)
    return max(inten * falloff_ratio(e) / 265.0, 1e-4)


def calibrate(m, c, bsp, apply=False, vmfpath=None, cap_hdr=None, check=True):
    """Stage step / pass `lightcal` (opt-in; report only unless apply): every light_omni2 / light_barn at the place of a compiled
    CS:GO light gets the brightness that gives the surfaces round it (64 line traces through the BSP tree; spots: inside the
    cone) the same light as the compiled falloff did. Lights the BSP doesn't list use vrad_falloff on the VMF entity at that
    place when vmfpath is given.
    The report compares with two things: the vmap's current value (which on a map never relit is still the importer's: ~8x too
    bright for _fifty_percent_distance lights, so a large ratio there is the importer, not lightcal) and, with the VMF, what
    relight would give. check=True also measures the compiled lightmaps against the compiled falloff (lightmap_check), the
    evidence that the model behind lightcal is right for this map.
    Returns [(name or origin, class, current legacy, calibrated legacy, relight legacy or None)]."""
    import texlights as T
    b = T.Bsp(bsp) if isinstance(bsp, str) else bsp
    tracer = BspTracer(b)
    hdr = T.hdr_lit(b)
    cap = cap_hdr if hdr else CAL_CAP_LDR
    comp = [w for w in T.world_lights(b) if w['type'] in (T.EMIT_POINT, T.EMIT_SPOT)]
    vents = []
    if vmfpath and os.path.exists(vmfpath):
        import vmf as vmfmod
        root = vmfmod.parse(open(vmfpath, encoding='utf-8', errors='replace').read())
        vents = [e for e in root.ch if e.name == 'entity' and (e.get('classname') or '').lower() in ('light', 'light_spot') and e.get('origin')]
    def vmf_at(o, cls):
        best, bd = None, CAL_MATCH ** 2
        for v in vents:
            if (v.get('classname') or '').lower() != cls: continue
            try: d2 = sum((float(a) - bb) ** 2 for a, bb in zip(v.get('origin').split(), o))
            except ValueError: continue
            if d2 <= bd: best, bd = v, d2
        return best
    rows = []; changed = unmatched = nfifty = 0
    for e in m.by_class('light_omni2', 'light_barn'):
        o = m.origin(e); want = T.EMIT_POINT if m.cls(e) == 'light_omni2' else T.EMIT_SPOT
        cand = [(sum((a - bb) ** 2 for a, bb in zip(w['origin'], o)), w) for w in comp if w['type'] == want]
        best = min(cand, key=lambda x: x[0]) if cand else None
        wl = best[1] if best and best[0] <= CAL_MATCH ** 2 else None
        v = vmf_at(o, 'light' if want == T.EMIT_POINT else 'light_spot') if vents else None
        if wl is None and v is not None:
            wl = vrad_falloff(v)
            if wl['type'] == 2: wl = None      # no aim direction for an unlisted spot: leave it
        if wl is None: unmatched += 1; continue
        dists = [tracer.trace(o, d) for d in _directions(wl)]
        leg = match_legacy(wl, dists, cap)
        if leg is None: continue
        try: old = float(m.P(e, 'brightness_legacy', '1') or 1)
        except ValueError: old = float('nan')
        quadratic = wl['c'] == 0 and wl['l'] == 0
        nfifty += wl['c'] > 0 and wl['q'] > 0
        rows.append((m.name(e) or '%.0f %.0f %.0f' % tuple(o), m.cls(e), old, leg, relight_legacy(v) if v is not None else None))
        if apply:
            _set_legacy(m, e, leg, quadratic, wl.get('radius') or 0.0); changed += 1
    def med(pairs):
        r = sorted(a / b_ for a, b_ in pairs if b_ and math.isfinite(b_) and b_ > 0)
        return (r[len(r) // 2], sum(1 for x in r if x > 2 or x < 0.5), len(r)) if r else (None, 0, 0)
    cur = med((r[3], r[2]) for r in rows)
    rel = med((r[3], r[4]) for r in rows if r[4] is not None)
    raw = med((r[2], r[4]) for r in rows if r[4] is not None)          # current / relight: ~1 when the map was relit
    parts = ['lightcal: %d lights matched to the compiled CS:GO light list (%s, cap %s; %d with _fifty_percent_distance falloff)' % (len(rows), 'HDR' if hdr else 'LDR', cap, nfifty)]
    if cur[0] is not None: parts.append('calibrated / current vmap value: median x%.2f, %d more than 2x off' % cur[:2])
    if rel[0] is not None: parts.append('calibrated / what relight gives: median x%.2f, %d more than 2x off' % rel[:2])
    if raw[0] is not None and (raw[0] > 1.5 or raw[0] < 0.67):
        parts.append('the current values are x%.2f of relight\'s, so this map was never relit (importer values): compare against relight, not current' % raw[0])
    if check:
        lc, n = lightmap_check(b, tracer, comp)
        if lc is not None:
            parts.append('compiled lightmap / compiled-falloff prediction under %d lights: median %.2f%s' % (n, lc, '' if hdr else ' (LDR lightmaps: rough)'))
            if (lc < 0.5 or lc > 2.0) and n >= 10:
                c.todo.append('lightcal: on this map the baked CS:GO lightmap is x%.2f of what the compiled light list predicts under its lights '
                              '(other light: sky, bounce, spots or unlisted lights), so lightcal_apply may over- or under-correct here' % lc)
    if unmatched: parts.append('%d lights not in the light list (left as they are)' % unmatched)
    c.log.append('; '.join(parts) + ('; APPLIED' if apply else ' (report only)'))
    if apply and changed:
        c.todo.append('lightcal: %d lights re-set from the compiled CS:GO falloff + line traces: not in-game verified, compare a few rooms with CS:GO' % changed)
    return rows


def fifty_percent_note(c, vmfpath):
    """TO CHECK line when the VMF has _fifty_percent_distance lights: relight / lightbright fit them with a linear falloff that the
    compiled light list shows is wrong (~8x too bright at 128 u); lightcal (opt-in) uses the compiled constants."""
    import re
    try: txt = open(vmfpath, encoding='utf-8', errors='replace').read()
    except OSError: return 0
    n = len([v for v in re.findall(r'"_fifty_percent_distance"\s+"([^"]*)"', txt) if v.strip() not in ('', '0')])
    if n:
        c.todo.append('%d lights use _fifty_percent_distance: vrad compiled them as 2/65.25 x (1 + d/D + 63.25 (d/D)^2), not the linear falloff '
                      'relight / lightbright assume (~8x too bright at 128 u). If rooms lit by them look too bright, stage the BSP and run the '
                      'opt-in lightcal step' % n)
    return n
