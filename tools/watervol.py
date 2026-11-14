"""Stage D pass `water`: CS:GO water -> CS2 func_water + underwater post-processing (skink52's water rules, 29 Oct 2026).

CS2 only treats water as water (swimming, sounds, splashes) inside a func_water entity; a world mesh with a water-looking
material is just a floor you can't stand in (ttt_minecraft). For every water mesh (a material with "water" in its name) in the world
or in a func_water_analog:
- touching water meshes are grouped and each group becomes one func_water (func_water_analog -> func_water, keeping its name);
- a group deep enough to put a player's eyes under (more than 64 u) gets an underwater post_processing_volume over its footprint, from
  16 u under the bottom to UNDER u below the surface (the volume tests the player's feet, so the effect starts when the eyes go
  under): lighting/postprocessing/postprocess_filmic_underwater.vpost (copied from ba_jail_seaside), master 0, exposure 0-0.3,
  fade 0.1, as on ba_jail_seaside;
- a master post_processing_volume is added (stock lighting/postprocessing/filmic_default.vpost) if the map has none;
- every func_water mesh wider than CELL is cut into pieces no wider than CELL, one mesh each (split_volumes, also the pass `watersplit`).

Why the cut (14 Nov 2026): resourcecompiler gives a func_water mesh over about 500 u across no physics hull ("ExtrudeReplaceHull failed to
build new convex hull" / "Failed to create physics hulls for one or more meshes", and the compile still says OK), so there is no water to swim
in. In the ported maps' build logs 85 of 107 func_water meshes over 500 u failed, plain six-face boxes included; none of 41 at 448 u or less
did (mg_monsoon's test compiles: 256 / 384 boxes pass, a single 512 box fails). docs/reference/cs2-gotchas.md has the rule.
"""
import math
import os
import numpy as np
import dmx
import vmapedit as V
import splitfaces as SF

UNDER = 80.0
CELL = 384.0           # widest func_water piece (x and y); each mesh is cut into equal pieces no wider than this
NODRAW = 'materials/tools/toolsnodraw.vmat'
VPOST = 'lighting/postprocessing/postprocess_filmic_underwater.vpost'
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'box_template.vmap')


def is_water(mat): return 'water' in mat and not mat.startswith('materials/tools/')


def box(m, tm, tnode, mn, mx, mat):
    j = m.import_subtree(tm, tnode, {}, [m.next_node_id()])
    md = m.g(j, b'meshData')
    dmx.set_(m.E[md], b'materials', dmx.ARR + dmx.T_STR, [mat])
    dmx.set_(m.E[j], b'origin', dmx.T_V3, [0.0, 0.0, 0.0])
    for st in m.g(m.g(md, b'vertexData'), b'streams'):
        if m.E[st]['name'].startswith(b'position'):
            a = dmx.geta(m.E[st], b'data'); pts = a[2]
            ctr = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
            a[2] = [[mx[k] if p[k] > ctr[k] else mn[k] for k in range(3)] for p in pts]
    return j


def underwater_lights(m, lo, hi, step0=640.0, cap=16):
    """Source 1 water was lit by the lightmap; a CS2 water volume with no light inside is dark underwater. Put a sparse grid of dim
    unshadowed lights ~128 u below the surface where no existing light reaches. Method from cs2-slop-porting rebuild_lighting.py (MIT)."""
    import math
    if (hi[0] - lo[0]) < 64 or (hi[1] - lo[1]) < 64: return 0
    lights = []
    for e in m.by_class('light_omni2', 'light_barn', 'light_spot', 'light_rect', 'light_capsule'):
        try: rg = float(m.P(e, 'range', '512') or 512)
        except ValueError: rg = 512.0
        lights.append((m.origin(e), rg))
    legs = []
    for e in m.by_class('light_omni2'):
        try:
            v = float(m.P(e, 'brightness_legacy', '') or 'nan')
            if math.isfinite(v) and v > 0: legs.append(v)
        except ValueError: pass
    legs.sort()
    tmpl = next(iter(m.by_class('light_omni2')), None)
    leg = max(0.06, min(legs[len(legs) // 2] if legs else 0.15, 0.25))
    z = lo[2] + min(128.0, (hi[2] - lo[2]) * 0.5)
    step = max(step0, math.sqrt((hi[0] - lo[0]) * (hi[1] - lo[1]) / cap))
    nx, ny = max(1, math.ceil((hi[0] - lo[0]) / step)), max(1, math.ceil((hi[1] - lo[1]) / step))
    placed = 0
    for ix in range(nx):
        for iy in range(ny):
            p = (lo[0] + (ix + 0.5) * (hi[0] - lo[0]) / nx, lo[1] + (iy + 0.5) * (hi[1] - lo[1]) / ny, z)
            if any(lo[0] - 64 <= q[0] <= hi[0] + 64 and lo[1] - 64 <= q[1] <= hi[1] + 64 and lo[2] - 64 <= q[2] <= hi[2] + 64
                   and math.dist(p, q) < min(r, step * 0.9) for q, r in lights): continue
            if placed >= cap: break
            props = {a[0].decode(): a[2].decode() for a in m.props(tmpl)['attrs'] if a[0] not in (b'classname', b'targetname', b'parentname')} if tmpl else {}
            props.update({'light_style': '', 'parentname': '', 'targetname': ''})
            props.update({'color': '255 255 255', 'colormode': '0', 'range': '512', 'castshadows': '0', 'directlight': '1',
                'enabled': '1', 'brightness_legacy': '%g' % round(leg, 6), 'brightness': '%g' % round(math.log2(leg), 6),
                'brightness_lumens': '%d' % round(1000 * leg), 'brightness_candelas': '%d' % round(1000 * leg / (4 * math.pi)),
                'brightness_nits': '%d' % round(9816 * leg)})
            m.new_entity('light_omni2', list(p), props)
            lights.append((p, 512.0)); placed += 1
    return placed


def _key(p): return tuple(np.round(p, SF.WELD))


def _cap(polys, axis, c, outward, attrs):
    """The face closing a piece on the cut plane pos[axis] = c: the open edges the clipped faces left on that plane, walked the other way.
    -> poly or None (the edges do not make one loop)"""
    nxt = {}
    for p in polys:
        cs = p['corners']
        for j in range(len(cs)):
            a, b = cs[j], cs[(j + 1) % len(cs)]
            if abs(a['pos'][axis] - c) < SF.EPS and abs(b['pos'][axis] - c) < SF.EPS and _key(a['pos']) != _key(b['pos']):
                nxt[_key(b['pos'])] = (_key(a['pos']), a)              # reversed: the cap runs b -> a
    if len(nxt) < 3: return None
    start = next(iter(nxt)); k, loop = start, []
    for _ in range(len(nxt)):
        t, a = nxt[k]; loop.append(a); k = t
        if k == start: break
    if k != start or len(loop) != len(nxt): return None
    n = [0.0, 0.0, 0.0]; n[axis] = outward
    corners = []
    for a in loop:
        f = {kk: (np.array(n) if kk.startswith('normal') else np.array(v, float)) for kk, v in a['fvd'].items()}
        corners.append({'pos': a['pos'].copy(), 'fvd': f})
    return {'attrs': attrs, 'corners': corners}


def _pieces_convex(polys, cuts, attrs):
    """A closed convex mesh cut into grid cells: every face clipped to the cell, each cut plane closed with a nodraw cap."""
    out = []
    xs, ys = cuts
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            planes = [(0, xs[i], -1.0, i > 0), (0, xs[i + 1], 1.0, i < len(xs) - 2), (1, ys[j], -1.0, j > 0), (1, ys[j + 1], 1.0, j < len(ys) - 2)]
            piece = [{'attrs': p['attrs'], 'corners': p['corners']} for p in polys]
            for axis, c, side, cut in planes:                    # clip, then close that plane before the next (its cap gets clipped too)
                if not cut: continue
                nxt = []
                for p in piece:
                    lo, hi = SF.clip_poly(p['corners'], axis, c)
                    keep = lo if side > 0 else hi
                    if SF._usable(keep): nxt.append({'attrs': p['attrs'], 'corners': keep})
                piece = nxt
                if not piece: break
                cap = _cap(piece, axis, c, side, attrs)
                if cap is None: return None
                piece.append(cap)
            if not piece: continue
            out.append(piece)
    return out


def _pieces_prism(polys, mats, cuts, attrs, zbot):
    """Fallback for a mesh that is not a closed convex volume: each upward water face, clipped to the grid cells, extruded down to zbot
    (top in its own material, bottom and walls nodraw), as mg_monsoon's water_volume(pieces=True). -> pieces or None"""
    xs, ys = cuts
    tops = []
    for p in polys:
        nz = np.mean([c['fvd'].get('normal:0', np.zeros(3))[2] for c in p['corners']])
        if nz > 0.5 and 'water' in mats[p['attrs']['materialindex:0']]:
            if not SF.is_convex(p['corners']): return None
            tops.append(p)
    if not tops: return None
    out = []
    for p in tops:
        cells = [p['corners']]
        for axis, cs in ((0, xs[1:-1]), (1, ys[1:-1])):
            for c in cs:
                nxt = []
                for pc in cells:
                    lo, hi = SF.clip_poly(pc, axis, c)
                    nxt += [x for x in (lo, hi) if SF._usable(x)]
                cells = nxt
        for top in cells:
            if min(c['pos'][2] for c in top) - zbot < 1.0: continue
            bot = [{'pos': np.array([c['pos'][0], c['pos'][1], zbot]), 'fvd': {k: (np.array([0.0, 0.0, -1.0]) if k.startswith('normal') else v) for k, v in c['fvd'].items()}} for c in top]
            piece = [{'attrs': p['attrs'], 'corners': top}, {'attrs': attrs, 'corners': bot[::-1]}]
            k = len(top)
            for j in range(k):
                a, b, ab, bb = top[j], top[(j + 1) % k], bot[j], bot[(j + 1) % k]
                d = b['pos'] - a['pos']; n = np.array([d[1], -d[0], 0.0]); ln = np.linalg.norm(n)
                n = n / ln if ln > 1e-9 else n
                wall = [{'pos': x['pos'], 'fvd': {kk: (n if kk.startswith('normal') else vv) for kk, vv in x['fvd'].items()}} for x in (b, a, ab, bb)]
                piece.append({'attrs': attrs, 'corners': wall})
            out.append(piece)
    return out


def split_volumes(m, c, cell=CELL):
    """Cut every func_water mesh wider than `cell` (x or y) into equal pieces no wider than `cell`, one mesh per piece in the same entity.
    A closed convex mesh (a CS:GO water brush) is cut exactly; anything else becomes one prism per upward water face and cell. Flat sheets
    (no depth) are cut but stay sheets. -> number of meshes cut"""
    cut = pieces = 0
    notes, sheets = [], []
    for ent in m.by_class('func_water'):
        label = 'func_water %s' % (m.name(ent) or '-')
        for node in [n for n in m.children(ent) if m.type(n) == b'CMapMesh']:
            md = m.g(node, b'meshData')
            if md is None: continue
            b = m.bounds(node)
            if b is None or max(b[1][0] - b[0][0], b[1][1] - b[0][1]) <= cell + SF.EPS: continue
            if SF.mesh_has_subdivision(m, node):
                notes.append('%s (mesh %d): subdivision mesh, not cut' % (label, node)); continue
            ok, _ = SF._identity_xform(m, node)
            if not ok:
                notes.append('%s (mesh %d): rotated or scaled mesh, not cut' % (label, node)); continue
            polys, mats = SF.mesh_read(m, node)
            P = np.array([cr['pos'] for p in polys for cr in p['corners']])
            lo, hi = P.min(0), P.max(0)
            cuts = []
            for k in range(2):
                n = max(1, math.ceil((hi[k] - lo[k]) / cell - 1e-6))
                cuts.append([float(lo[k] + (hi[k] - lo[k]) * i / n) for i in range(n)] + [float(hi[k])])
            marr = dmx.geta(m.E[md], b'materials')
            if NODRAW not in mats:
                marr[2].append(NODRAW.encode() if isinstance(marr[2][0], (bytes, bytearray)) else NODRAW); mats = mats + [NODRAW]
            ni = mats.index(NODRAW)
            src = next((p for p in polys if p['attrs']['materialindex:0'] == ni), polys[0])
            attrs = dict(src['attrs']); attrs['materialindex:0'] = ni
            closed = -1 not in (m.g(md, b'edgeFaceIndices') or [-1])
            convex = closed and all(SF.is_convex(p['corners']) for p in polys)
            if convex:                                           # every vertex on or behind every face plane (normals point out)
                for p in polys:
                    Q = np.array([cr['pos'] for cr in p['corners']]); nrm = np.zeros(3)
                    for i in range(1, len(Q) - 1): nrm += np.cross(Q[i] - Q[0], Q[i + 1] - Q[0])
                    nrm /= np.linalg.norm(nrm) or 1.0
                    if np.dot(nrm, np.mean([cr['fvd'].get('normal:0', nrm) for cr in p['corners']], 0)) < 0: nrm = -nrm
                    if ((P - Q.mean(0)) @ nrm).max() > 0.05: convex = False; break
            if hi[2] - lo[2] < 1.0:                               # a flat sheet: cut it, it has no volume to close
                kind = 'sheet'
                out = []
                for i in range(len(cuts[0]) - 1):
                    for j in range(len(cuts[1]) - 1):
                        cur = [(p['attrs'], p['corners']) for p in polys]
                        for axis, cc, keep_lo in ((0, cuts[0][i], False), (0, cuts[0][i + 1], True), (1, cuts[1][j], False), (1, cuts[1][j + 1], True)):
                            nc = []
                            for at, cs in cur:
                                l_, h_ = SF.clip_poly(cs, axis, cc)
                                x = l_ if keep_lo else h_
                                if SF._usable(x): nc.append((at, x))
                            cur = nc
                        if cur: out.append([{'attrs': at, 'corners': cs} for at, cs in cur])
                sheets.append('%s (mesh %d)' % (label, node))
            elif convex:
                kind = 'convex'; out = _pieces_convex(polys, cuts, attrs)
            else:
                kind = 'prisms'; out = _pieces_prism(polys, mats, cuts, attrs, float(lo[2]))
            if not out:
                notes.append('%s (mesh %d, %d x %d u): %s cut failed, not cut' % (label, node, hi[0] - lo[0], hi[1] - lo[1], kind)); continue
            backup = SF.mesh_read(m, node)[0]
            made, err = [], None
            for piece in out[1:]:
                new = m.import_subtree(m, node, {}, [m.next_node_id()])
                err = SF.mesh_write(m, new, piece) or (SF.mesh_check(m, new) or [None])[0]
                if err: break
                made.append(new)
            if not err: err = SF.mesh_write(m, node, out[0]) or (SF.mesh_check(m, node) or [None])[0]
            if err:
                SF.mesh_write(m, node, backup)
                notes.append('%s (mesh %d): %s, not cut' % (label, node, err)); continue
            dmx.geta(m.E[ent], b'children')[2].extend(made)
            cut += 1; pieces += len(out)
            c.log.append('watersplit: %s mesh %d (%d x %d x %d u, %s) -> %d pieces (func_water meshes over ~500 u get no physics hull)'
                         % (label, node, hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2], kind, len(out)))
    if sheets: c.todo.append('watersplit: flat func_water sheets with no depth (no volume to swim in; the CS:GO brush depth was lost on import): %s' % ', '.join(sheets)[:600])
    if notes: c.todo.append('watersplit: %s' % '; '.join(notes)[:600])
    return cut


def run(m, c):
    par = m.parent_of()
    meshes = []                                   # (node, parent, bounds)
    for n, _ in m.walk():
        if m.type(n) != b'CMapMesh': continue
        mats = [x.decode() for x in m.g(m.g(n, b'meshData'), b'materials') or []]
        if not any(is_water(x) for x in mats): continue
        p = par.get(n)
        if p is None: continue
        pt = m.type(p)
        if pt == b'CMapEntity' and m.cls(p) not in ('func_water_analog', 'func_water'): continue     # water on a door, train, ... left alone
        meshes.append((n, p, m.bounds(n)))
    if not meshes: return 0
    # group touching meshes (union-find on bounds expanded by 1 u)
    idx = list(range(len(meshes)))
    def find(i):
        while idx[i] != i: idx[i] = idx[idx[i]]; i = idx[i]
        return i
    for i in range(len(meshes)):
        for j in range(i + 1, len(meshes)):
            a, b = meshes[i][2], meshes[j][2]
            if all(a[0][k] <= b[1][k] + 1 and b[0][k] <= a[1][k] + 1 for k in range(3)): idx[find(i)] = find(j)
    groups = {}
    for i in range(len(meshes)): groups.setdefault(find(i), []).append(meshes[i])
    tm = V.Map(TEMPLATE); tnode = tm.children(tm.world)[0]
    nwater = npp = nlight = 0
    for g in groups.values():
        lo = [min(b[0][k] for _, _, b in g) for k in range(3)]; hi = [max(b[1][k] for _, _, b in g) for k in range(3)]
        owners = {p for _, p, _ in g if m.type(p) == b'CMapEntity'}
        if owners:
            ent = sorted(owners)[0]
            if m.cls(ent) == 'func_water_analog':
                m.setp(ent, 'classname', 'func_water')
                for k in ('WaveHeight', 'startposition', 'speed', 'movedistance', 'movedir'): m.delp(ent, k)
        else:
            ent = m.new_entity('func_water', [(lo[k] + hi[k]) / 2 for k in range(3)], {})
        for n, p, _ in g:
            if p == ent: continue
            src = dmx.geta(m.E[p], b'children'); src[2] = [x for x in src[2] if x != n]
            dmx.geta(m.E[ent], b'children')[2].append(n)
            if m.type(p) == b'CMapEntity' and not any(m.type(x) == b'CMapMesh' for x in m.children(p)): m.remove_node(p)
        nwater += 1
        depth = hi[2] - lo[2]
        if depth > 64:
            top = max(hi[2] - UNDER, lo[2] + 8)
            mn, mx = [lo[0], lo[1], lo[2] - 16], [hi[0], hi[1], top]
            pp = m.new_entity('post_processing_volume', [(mn[k] + mx[k]) / 2 for k in range(3)], {
                'StartDisabled': '0', 'spawnflags': '4097', 'postprocessing': VPOST, 'master': '0', 'minexposure': '0', 'maxexposure': '0.3',
                'enableexposure': '1', 'exposurespeedup': '1', 'exposurespeeddown': '1', 'fadetime': '0.1'})
            dmx.geta(m.E[pp], b'children')[2].append(box(m, tm, tnode, mn, mx, b'materials/tools/toolsnodraw.vmat'))
            npp += 1
        if depth >= 48: nlight += underwater_lights(m, lo, hi)
    master = [e for e in m.by_class('post_processing_volume') if (m.P(e, 'master', '0') or '0') == '1']
    if not master:
        e = m.new_entity('post_processing_volume', [0, 0, 0], {'StartDisabled': '0', 'spawnflags': '4097', 'master': '1',
            'postprocessing': 'lighting/postprocessing/filmic_default.vpost', 'minexposure': '1.0', 'maxexposure': '1.0', 'enableexposure': '1',
            'exposurespeedup': '1', 'exposurespeeddown': '1', 'fadetime': '1.0'})
        dmx.geta(m.E[e], b'children')[2].append(box(m, tm, tnode, [-8, -8, -8], [8, 8, 8], b'materials/tools/toolsnodraw.vmat'))
    c.needs_underwater_vpost = npp > 0
    split_volumes(m, c)
    c.log.append('water: %d water meshes -> %d func_water; %d underwater post_processing_volumes (%s, top %g u below the surface); %s'
                 % (len(meshes), nwater, npp, VPOST, UNDER, 'master post_processing_volume already there' if master else 'master post_processing_volume added (filmic_default)'))
    if nlight:
        c.log.append('water: %d underwater light_omni2 (map median brightness, range 512, no shadows) in water with no light inside' % nlight)
        c.todo.append('underwater lights are a heuristic (Source water was lightmap-lit, CS2 water needs lights): check the water areas after the bake')
    return nwater
