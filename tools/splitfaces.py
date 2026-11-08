"""Stage C step / stage D pass `splitfaces`: split very large lit faces of a .vmap into tiles.

From github.com/Ninja-Chris/cs2-slop-porting 3.5 (MIT; Ninja-Chris and skink52), 2 Nov 2026. run(m, c) is ours: faces over 512x512 cut on a
512 world grid, kept in one mesh ("faces" mode: one mesh per tile showed seams); water, liquids, sky and every tool material never split.

Why: in CS2 a face is one lightmap chart, and a mesh (CMapMesh) gets one probe / cubemap for the whole mesh. A huge floor
therefore bakes blotchy and reflects the wrong place.  This cuts faces over `limit` square units on a world-aligned grid
(`cell` units) and, optionally, gives every grid cell its own copy of the mesh.

All geometry is rebuilt from polygons: vertices are welded by position, every undirected edge gets two half-edges (the twin of
a boundary edge has face -1), and the corner data (texcoord / normal / tangent / vertex paint) is interpolated along cut edges.
Open edges where separate fans of faces meet at one corner are linked fan to fan, as the importer writes them (link_bowties: linked
back to their own fan, the mesh crashes Hammer on load; from cs2-slop-porting 2026-11-08g, MIT, 8 Nov 2026).
Meshes with subdivision data (importer displacements) and non-convex faces are left alone.
"""
import numpy as np

EPS = 0.01          # a point this close to a cut plane counts as on it
WELD = 3            # vertex welding, decimals


# ----------------------------------------------------------------------------------------------------------- reading
def _streams(m, node, part):
    """-> {stream name: (element index, data list)} for meshData.<part>"""
    md = m.g(node, b'meshData')
    pd = m.g(md, part)
    return {m.E[st]['name'].decode(): (st, m.g(st, b'data')) for st in (m.g(pd, b'streams') or [])}


def mesh_has_subdivision(m, node):
    sd = m.g(m.g(node, b'meshData'), b'subdivisionData')
    return bool(sd is not None and m.g(sd, b'streams'))


def mesh_read(m, node):
    """-> (polys, materials).  poly = {'attrs': {faceData stream: value}, 'corners': [{'pos': ndarray(3), 'fvd': {stream: ndarray}}]}"""
    md = m.g(node, b'meshData')
    dest, nxt = m.g(md, b'edgeVertexIndices'), m.g(md, b'edgeNextIndices')
    fe, fd = m.g(md, b'faceEdgeIndices'), m.g(md, b'faceDataIndices')
    evd, vdi = m.g(md, b'edgeVertexDataIndices'), m.g(md, b'vertexDataIndices')
    pos = _streams(m, node, b'vertexData')['position:0'][1]
    fvd = {k: v[1] for k, v in _streams(m, node, b'faceVertexData').items()}
    fdat = {k: v[1] for k, v in _streams(m, node, b'faceData').items()}
    polys = []
    for f, h0 in enumerate(fe):
        corners, h = [], h0
        for _ in range(len(dest) + 1):
            corners.append({'pos': np.array(pos[vdi[dest[h]]], float),
                            'fvd': {k: np.array(v[evd[h]], float) for k, v in fvd.items()}})
            h = nxt[h]
            if h == h0:
                break
        polys.append({'attrs': {k: v[fd[f]] for k, v in fdat.items()}, 'corners': corners})
    return polys, [x.decode('utf-8', 'replace') if isinstance(x, (bytes, bytearray)) else x for x in m.g(md, b'materials')]


# ------------------------------------------------------------------------------------------------------------ geometry
def poly_area(corners):
    P = np.array([c['pos'] for c in corners])
    n = np.zeros(3)
    for i in range(1, len(P) - 1):
        n += np.cross(P[i] - P[0], P[i + 1] - P[0])
    return float(np.linalg.norm(n) / 2)


def is_convex(corners, tol=1e-6):
    P = np.array([c['pos'] for c in corners])
    n = np.zeros(3)
    for i in range(1, len(P) - 1):
        n += np.cross(P[i] - P[0], P[i + 1] - P[0])
    ln = np.linalg.norm(n)
    if ln < 1e-9:
        return False
    n /= ln
    for i in range(len(P)):
        c = np.dot(np.cross(P[(i + 1) % len(P)] - P[i], P[(i + 2) % len(P)] - P[(i + 1) % len(P)]), n)
        if c < -tol * max(1.0, ln):
            return False
    return True


def _lerp(a, b, t):
    out = {'pos': a['pos'] + (b['pos'] - a['pos']) * t, 'fvd': {}}
    for k in a['fvd']:
        v = a['fvd'][k] + (b['fvd'][k] - a['fvd'][k]) * t
        if k.startswith('normal'):
            ln = np.linalg.norm(v)
            if ln > 1e-9:
                v = v / ln
        out['fvd'][k] = v
    return out


def _edge_key(p, q):
    a, b = tuple(np.round(p, WELD)), tuple(np.round(q, WELD))
    return (a, b) if a <= b else (b, a)


def clip_poly(corners, axis, c):
    """Cut a convex polygon with the plane  pos[axis] = c  -> (below, above) corner lists (either may be empty)."""
    lo, hi = [], []
    n = len(corners)
    for i in range(n):
        a, b = corners[i], corners[(i + 1) % n]
        sa, sb = a['pos'][axis] - c, b['pos'][axis] - c
        sa0, sb0 = abs(sa) < EPS, abs(sb) < EPS
        if sa0:
            lo.append(a)
            hi.append(a)
        elif sa < 0:
            lo.append(a)
        else:
            hi.append(a)
        if not sa0 and not sb0 and (sa < 0) != (sb < 0):
            if tuple(np.round(a['pos'], WELD)) <= tuple(np.round(b['pos'], WELD)):
                p = _lerp(a, b, sa / (sa - sb))
            else:                                   # always interpolate from the same end, so both faces sharing the edge agree
                p = _lerp(b, a, sb / (sb - sa))
            p['pos'][axis] = c                      # exactly on the plane, so both sides weld
            lo.append(p)
            hi.append(p)
    return lo, hi


def _usable(corners):
    return len(corners) >= 3 and poly_area(corners) > 1e-4


# ----------------------------------------------------------------------------------------------------------- cutting
def cut_polys(polys, limit, cell, candidate, min_piece=None):
    """Cut every candidate poly with area >= limit on the grid.  -> (new polys, cut count, skipped [(reason, area)])"""
    min_piece = cell / 64.0 if min_piece is None else min_piece
    plan, skipped = {}, []
    for i, p in enumerate(polys):
        if not candidate(p):
            continue
        area = poly_area(p['corners'])
        if area <= limit * 1.0001:                  # a tile of exactly cell x cell is fine
            continue
        if not is_convex(p['corners']):
            skipped.append(('not convex', area))
            continue
        P = np.array([c['pos'] for c in p['corners']])
        planes = []
        for axis in range(3):
            lo, hi = P[:, axis].min(), P[:, axis].max()
            if hi - lo <= cell:
                continue
            k = int(np.ceil((lo + EPS) / cell))
            while k * cell < hi - EPS:
                c = k * cell
                if c - lo >= min_piece and hi - c >= min_piece:
                    planes.append((axis, float(c)))
                k += 1
        if planes:
            plan[i] = planes
    # points where the planes cross the edges of cut faces: the neighbours across those edges need the same points
    edge_pts = {}
    for i, planes in plan.items():
        cs = polys[i]['corners']
        for j in range(len(cs)):
            a, b = cs[j], cs[(j + 1) % len(cs)]
            for axis, c in planes:
                sa, sb = a['pos'][axis] - c, b['pos'][axis] - c
                if abs(sa) >= EPS and abs(sb) >= EPS and (sa < 0) != (sb < 0):
                    if tuple(np.round(a['pos'], WELD)) <= tuple(np.round(b['pos'], WELD)):
                        p = a['pos'] + (b['pos'] - a['pos']) * (sa / (sa - sb))
                    else:
                        p = b['pos'] + (a['pos'] - b['pos']) * (sb / (sb - sa))
                    p[axis] = c
                    edge_pts.setdefault(_edge_key(a['pos'], b['pos']), {})[tuple(np.round(p, WELD))] = p
    out, cut = [], 0
    for i, p in enumerate(polys):
        cs = p['corners']
        if edge_pts:
            ncs = []
            for j in range(len(cs)):
                a, b = cs[j], cs[(j + 1) % len(cs)]
                pts = edge_pts.get(_edge_key(a['pos'], b['pos']))
                if pts:
                    L = np.linalg.norm(b['pos'] - a['pos'])
                    ts = sorted(((float(np.dot(q - a['pos'], b['pos'] - a['pos']) / (L * L)), q) for q in pts.values()), key=lambda x: x[0])
                    mids = [_lerp(a, b, t) for t, _ in ts]
                    for mid, (_, q) in zip(mids, ts):
                        mid['pos'] = q.copy()
                    ncs.extend(mids)
                ncs.append(b)                       # corner j+1 (so the list starts at corner 1; rotated back below)
            cs = ncs[-1:] + ncs[:-1]                # restore the original starting corner
        if i in plan:
            pieces = [cs]
            for axis, c in plan[i]:
                nxt = []
                for pc in pieces:
                    lo, hi = clip_poly(pc, axis, c)
                    nxt += [x for x in (lo, hi) if _usable(x)]
                pieces = nxt
            for pc in pieces:
                out.append({'attrs': p['attrs'], 'corners': pc, 'cut': True})
            cut += 1
        else:
            out.append({'attrs': p['attrs'], 'corners': cs})
    return out, cut, skipped


# ----------------------------------------------------------------------------------------------------------- writing
def mesh_write(m, node, polys):
    """Rebuild the half-edge arrays and data streams of `node` from polygons.  Returns an error string or None (mesh untouched on error)."""
    import dmx
    md = m.g(node, b'meshData')
    verts, vidx = [], {}

    def vid(p):
        k = tuple(np.round(p, WELD))
        if k not in vidx:
            vidx[k] = len(verts)
            verts.append(p)
        return vidx[k]

    faces = []
    for p in polys:
        pairs = []
        for c in p['corners']:
            k = vid(c['pos'])
            if pairs and pairs[-1][0] == k:
                continue                            # two corners welded together: drop the repeat
            pairs.append((k, c))
        if len(pairs) > 1 and pairs[0][0] == pairs[-1][0]:
            pairs.pop()
        ids = [k for k, _ in pairs]
        if len(ids) < 3 or len(set(ids)) != len(ids):
            return 'degenerate or pinched face after welding'
        faces.append(({'attrs': p['attrs'], 'corners': [c for _, c in pairs]}, ids))
    half = {}                                       # directed (origin, destination) -> half-edge index
    dest, face_of, corner_of, edge_of, opp, nxt, fedge = [], [], [], [], [], [], []
    for f, (p, ids) in enumerate(faces):
        n = len(ids)
        hs = []
        for j in range(n):
            u, v = ids[j - 1], ids[j]               # the half-edge into corner j runs from the previous corner to this one
            h = half.get((u, v))
            if h is None:                           # new edge: face side 2k, boundary twin 2k+1
                k = len(dest) // 2
                h = 2 * k
                dest += [v, u]
                face_of += [-1, -1]
                corner_of += [None, None]
                edge_of += [k, k]
                opp += [h + 1, h]
                nxt += [-1, -1]
                half[(u, v)] = h
                half[(v, u)] = h + 1
            elif face_of[h] != -1:
                return 'non-manifold edge (two faces use the same direction)'
            face_of[h] = f
            corner_of[h] = (f, j)
            hs.append(h)
        for j in range(n):
            nxt[hs[j]] = hs[(j + 1) % n]
        fedge.append(hs[0])
    H = len(dest)
    # boundary loops: next boundary half-edge starts where this one ends
    out_b = {}
    for h in range(H):
        if face_of[h] == -1:
            origin = dest[opp[h]]
            out_b.setdefault(origin, []).append(h)
    for h in range(H):
        if face_of[h] == -1:
            lst = out_b.get(dest[h], [])
            nxt[h] = lst.pop(0) if lst else opp[h]
    nv = len(verts)
    vedge = [-1] * nv
    for h in range(H):
        o = dest[opp[h]]
        if vedge[o] == -1 or (face_of[h] != -1 and face_of[vedge[o]] == -1):
            vedge[o] = h
    if -1 in vedge:
        return 'unused vertex'
    nf = len(faces)
    # ---- write
    def setv(el, name, val):
        a = dmx.geta(m.E[el], name)
        a[2] = val

    setv(md, b'vertexEdgeIndices', vedge)
    setv(md, b'vertexDataIndices', list(range(nv)))
    setv(md, b'edgeVertexIndices', dest)
    setv(md, b'edgeOppositeIndices', opp)
    setv(md, b'edgeNextIndices', nxt)
    setv(md, b'edgeFaceIndices', face_of)
    setv(md, b'edgeDataIndices', edge_of)
    setv(md, b'edgeVertexDataIndices', list(range(H)))
    setv(md, b'faceEdgeIndices', fedge)
    setv(md, b'faceDataIndices', list(range(nf)))
    ne = H // 2

    def resize(part, size, fill):
        pd = m.g(md, part)
        setv(pd, b'size', size)
        for st in m.g(pd, b'streams') or []:
            name = m.E[st]['name'].decode()
            setv(st, b'data', fill(name))

    resize(b'vertexData', nv, lambda name: [list(map(float, v)) for v in verts])
    zero = {}
    for k, (st, data) in _streams(m, node, b'faceVertexData').items():
        zero[k] = [0.0] * len(data[0]) if data else [0.0]

    def fvd_fill(name):
        arr = [list(zero[name]) for _ in range(H)]
        for h in range(H):
            if corner_of[h] is not None:
                f, j = corner_of[h]
                arr[h] = [float(x) for x in faces[f][0]['corners'][j]['fvd'][name]]
        return arr

    # (zero template is taken from the old data before it is overwritten)
    resize(b'faceVertexData', H, fvd_fill)
    resize(b'edgeData', ne, lambda name: [0] * ne)
    resize(b'faceData', nf, lambda name: [faces[f][0]['attrs'][name] for f in range(nf)])
    sd = m.g(md, b'subdivisionData')
    if sd is not None:
        setv(sd, b'subdivisionLevels', [0] * H)
    link_bowties(m, node)
    return None


def link_bowties(m, node):
    """Open edges at a bowtie corner (separate fans of faces meeting at one vertex) linked fan to fan: each fan's incoming open edge ->
    the NEXT fan's outgoing open edge, the way Valve's importer writes them (all 4,453 such corners in 6 ported maps, 8 Nov 2026; this
    changes none of them). mesh_write's boundary pass picks the outgoing edge by index, which links most of them back to their own fan
    (ttt_island 73 of 75, mg_n64_goldeneye 1,096 of 1,116 when re-written), and a mesh linked that way crashes Hammer on load (hammer.dll
    null write; cs2-slop-porting 2026-11-08g found it on mg_divine / mg_hellz, MIT). Only edgeNextIndices of those open edges change.
    -> links changed (0 if none), -1 if a fan has no open edge (left as it was)"""
    import dmx
    md = m.g(node, b'meshData')
    if md is None:
        return 0
    dest, opp, face = m.g(md, b'edgeVertexIndices'), m.g(md, b'edgeOppositeIndices'), m.g(md, b'edgeFaceIndices')
    na = dmx.geta(m.E[md], b'edgeNextIndices')
    if not dest or na is None:
        return 0
    nxt = na[2]
    H = len(dest)
    inc = {}
    for h in range(H):
        if face[h] == -1:
            inc.setdefault(dest[h], []).append(h)
    if all(len(v) < 2 for v in inc.values()):
        return 0
    prev = [0] * H
    for h in range(H):
        prev[nxt[h]] = h
    plan = []
    for v, hs in inc.items():
        if len(hs) < 2:
            continue
        pairs = []
        for h in hs:                                # h runs into v along an open edge; turn about v through h's fan to its outgoing open edge
            x, own = opp[h], None
            for _ in range(H):
                if face[x] == -1:
                    own = x
                    break
                x = opp[prev[x]]
            if own is None:
                return -1
            pairs.append((h, own))
        plan += [(h, pairs[(i + 1) % len(pairs)][1]) for i, (h, _) in enumerate(pairs)]
    changed = 0
    for h, want in plan:
        if nxt[h] != want:
            nxt[h] = want
            changed += 1
    return changed


# ----------------------------------------------------------------------------------------------------------- checking
def mesh_check(m, node):
    """Structural check of the half-edge arrays.  -> list of problems (empty = fine)"""
    md = m.g(node, b'meshData')
    g = lambda k: m.g(md, k)
    dest, opp, nxt, face = g(b'edgeVertexIndices'), g(b'edgeOppositeIndices'), g(b'edgeNextIndices'), g(b'edgeFaceIndices')
    fe, vedge = g(b'faceEdgeIndices'), g(b'vertexEdgeIndices')
    evd, edi = g(b'edgeVertexDataIndices'), g(b'edgeDataIndices')
    bad = []
    H = len(dest)
    if not (len(opp) == len(nxt) == len(face) == len(evd) == len(edi) == H):
        return ['array lengths differ']
    if sorted(evd) != list(range(len(evd))):
        bad.append('edgeVertexDataIndices is not a permutation')
    for h in range(H):
        if opp[opp[h]] != h:
            bad.append('opposite of opposite of %d' % h)
        if dest[opp[h]] == dest[h]:
            bad.append('half-edge %d is a loop' % h)
        if dest[h] != dest[opp[nxt[h]]] and False:
            pass
        if dest[opp[nxt[h]]] != dest[h]:
            bad.append('next of %d does not start where it ends' % h)
        if face[h] != -1 and face[nxt[h]] != face[h]:
            bad.append('next of %d leaves the face' % h)
    for f, h0 in enumerate(fe):
        h, seen = h0, 0
        while True:
            if face[h] != f:
                bad.append('face %d loop has a foreign half-edge' % f)
                break
            h = nxt[h]
            seen += 1
            if h == h0 or seen > H:
                break
        if seen > H:
            bad.append('face %d loop does not close' % f)
    for v, h in enumerate(vedge):
        if dest[opp[h]] != v:
            bad.append('vertexEdge of %d does not start at it' % v)
    dm = m.g(m.g(node, b'meshData'), b'vertexData')
    for st in m.g(dm, b'streams'):
        if len(m.g(st, b'data')) != m.g(dm, b'size'):
            bad.append('vertexData stream length')
    return bad[:10]


# ----------------------------------------------------------------------------------------------------------- whole-map pass
def _identity_xform(m, node):
    o = m.g(node, b'origin', [0, 0, 0]); a = m.g(node, b'angles', [0, 0, 0]); sc = m.g(node, b'scales', [1, 1, 1])
    ok = all(abs(x) < 1e-4 for x in a) and all(abs(x - 1) < 1e-4 for x in sc)
    return ok, np.array(o, dtype=float)


def split_large(m, limit, cell, mode, skip_mat, log):
    """Cut every lit face over `limit` sq units on a world grid of `cell`.  mode 'faces' keeps one mesh; 'meshes' also moves the
    pieces into one mesh per grid cell (a cubemap / probe is assigned per mesh).  -> dict of counts + list of skipped notes"""
    res = dict(meshes=0, faces=0, pieces=0, new_meshes=0, skipped=[])
    owner = {}

    def walk(n, label, cls):
        for c in m.children(n):
            t = m.type(c)
            if t == b'CMapMesh':
                owner[c] = (n, label, cls)
            elif t == b'CMapEntity':
                walk(c, '%s %s' % (m.cls(c), m.name(c) or '-'), m.cls(c))
            else:
                walk(c, label, cls)
    walk(m.world, 'world', 'world')
    for node, (parent, label, cls) in list(owner.items()):
        if m.g(node, b'meshData') is None:
            continue
        if cls.startswith('func_water') or cls.startswith('trigger_'):
            continue
        ent_nodes = [e for e in m.entities() if m.cls(e) == cls and '%s %s' % (cls, m.name(e) or '-') == label] if cls != 'world' else []
        if ent_nodes and m.P(ent_nodes[0], 'lightmapstatic', '1') == '0':
            continue
        try:
            polys, mats = mesh_read(m, node)
        except Exception:
            continue
        cand = lambda p: not any(x in mats[p['attrs']['materialindex:0']] for x in skip_mat)
        big = [p for p in polys if cand(p) and poly_area(p['corners']) > limit * 1.0001]
        if not big:
            continue
        if mesh_has_subdivision(m, node):
            res['skipped'].append('%s (mesh %d): %d large face(s) in a displacement / subdivision mesh, not touched' % (label, node, len(big)))
            continue
        ok, org = _identity_xform(m, node)
        if not ok:
            res['skipped'].append('%s (mesh %d): %d large face(s), mesh is rotated or scaled, not touched' % (label, node, len(big)))
            continue
        for p in polys:
            p['corners'] = [{'pos': c['pos'] + org, 'fvd': c['fvd']} for c in p['corners']]
        newp, cut, sk = cut_polys(polys, limit, cell, cand)
        for kind, area in sk:
            res['skipped'].append('%s (mesh %d): face of %d sq units %s, not cut' % (label, node, area, kind))
        if not cut:
            continue
        for p in newp:                              # corner dicts can be shared between pieces, so copy rather than shift in place
            p['corners'] = [{'pos': c['pos'] - org, 'fvd': c['fvd']} for c in p['corners']]
        groups = {}
        rest = []
        if mode == 'meshes':
            for p in newp:
                if p.get('cut'):
                    ctr = np.mean([c['pos'] for c in p['corners']], axis=0) + org
                    groups.setdefault(tuple(int(x) for x in np.floor(ctr / cell)), []).append(p)
                else:
                    rest.append(p)
        else:
            rest = newp
        if len(groups) <= 1 and not rest:
            groups = {}
            rest = newp
        if len(groups) > 0 and rest:
            pass
        # write the original mesh first; if it has nothing left, it takes the first group
        keys = sorted(groups)
        first = rest if rest else groups[keys.pop(0)] if groups else newp
        err = mesh_write(m, node, first)
        if err:
            res['skipped'].append('%s (mesh %d): %s, not touched' % (label, node, err))
            continue
        made = []
        failed = False
        for k in keys:
            nid = [m.next_node_id()]
            new = m.import_subtree(m, node, {}, nid)
            e = mesh_write(m, new, groups[k])
            if e:
                failed = True
                res['skipped'].append('%s (mesh %d): tile %s: %s' % (label, node, k, e))
                break
            made.append(new)
        if failed:                                  # put every piece back in the original mesh
            mesh_write(m, node, newp)
            continue
        if made:
            from dmx import geta
            arr = geta(m.E[parent], b'children')
            arr[2].extend(made)
        res['meshes'] += 1
        res['faces'] += cut
        res['pieces'] += sum(1 for p in newp if p.get('cut'))
        res['new_meshes'] += len(made)
        log.append('%s (mesh %d): cut %d large face(s) into %d pieces%s' % (label, node, cut, sum(1 for p in newp if p.get('cut')), ', %d new mesh(es)' % len(made) if made else ''))
    return res


SKIP_MAT = ('materials/tools', 'toolsnodraw', 'sky', 'moondome', 'water', 'materials/liquids/')
LIMIT, CELL = 512.0 * 512.0, 512.0


def run(m, c, mode='faces'):
    notes = []
    res = split_large(m, LIMIT, CELL, mode, SKIP_MAT, notes)
    if res['faces']:
        c.log.append('splitfaces: %d lit faces over 512x512 in %d meshes cut into %d pieces on a %g grid (one lightmap chart / probe sample per face: big floors baked blotchy)'
                     % (res['faces'], res['meshes'], res['pieces'], CELL))
        c.todo.append('splitfaces: check the cut floors / ramps for seams after the bake')
    if res['skipped']: c.todo.append('splitfaces: not split: %s' % '; '.join(res['skipped'])[:600])
    return res['faces']
