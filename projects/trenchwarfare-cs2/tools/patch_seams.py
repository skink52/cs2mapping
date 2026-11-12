"""Seam patch (12 Nov 2026): closes the gaps tools/check_seams.py finds in the generated geometry, as one guarded delta patch.
Reads the input map (never writes it); writes the patched copy, the guard's target list and a report under out/.

usage: python tools/patch_seams.py [--in V] [--out V] [--targets T] [--report R] [--no-guard]
  defaults: --in out/step9/chain/3_terrain.vmap, --out out/mg_trenchwarfare_seams.vmap, --targets <out>.targets.json,
            --report <out>.report.json (also the user's sap benches: share of each inside the earth before / after; never moved)
  then (here unless --no-guard): python tools/patch_guard.py <in> <out> <targets> --strict
Chain: patch_world_1 -> patch_models -> patch_terrain -> patch_seams -> patch_sounds -> patch_nav (each takes --in / --out).

What it changes (generated geometry only: vis group tw_gen; the user's objects, tw_user or ungrouped, are never touched):
  siding caps  the slot between the top of every generated revetment (revet_*, the "wood siding" and iron) and the parapet / parados
               sheet behind it (the generator lays the sheet from 16 u behind the wall, the terrain under it is carved to the floor):
               a ground strip per parapet sheet, welded to the sheet's inner boundary vertices (the same positions, so no crack) and
               tucked 1 u under the siding top 1 u behind the wall face (the earth backing and posts stand through it; seen from the
               trench it is culled). The cap edge follows each siding's own frame (sidings moved off the wall line); where two tops of
               different height meet, a step face closes the opening under the higher edge; sheet vertices pinched against a wall
               corner are raised to the cap edge and welded. Also behind the user's static, unnamed sidings (new ground, the siding
               untouched); never behind a removable blocker (a named / dynamic user siding). Paint and planar UV continue the sheet's.
  plugs        what the caps leave (wall ends, corners, niche mouths): a 2-u heightfield patch per hole, read back from the capped map,
               0.4 u under the ground meshes around it with its outer ring 6 u lower where it overlaps them; never over the trench or
               on a prop.
  sheet lips   the outer edges of the parapet / parados sheets (in no man's land, between the trenches, toward the mortar pits) stand
               0.05-16 u over the terrain they end on, a slit you see under: the open boundary vertices are lowered onto the terrain
               (0.3 u under it, exact terrain triangles), every sheet sharing the vertex alike. Only those boundary vertices move.
  sap mouths   (REVIEW_WORLD_2 "Proposed seam patch") per side: the tunnel floor rows at the portal ramp up to the trench floor (the
               12-u riser closed: the portal row welded onto the terrain's floor edge, the next three rows at 3/4, 1/2, 1/4 of the
               rise); a lintel face from the tunnel roof's portal edge up to the ground and a ground cap over the cut in the terrain
               above the mouth (x +-2080..2208, y -2880..-2816, a 4-u grid 0.3 u over the parapet, its rim 0.3 u under it). The roof
               is not lifted:
               the user's upper benches (tl_bench, tw_user) set the head room at the mouth (57-62 u), so entry stays crouched while they
               stand; the benches are not moved.
Terrain tiles are not modified at all (the step 7 protect mask stays exact: trench floors, posts, pits, spawns, runways).
Every target is verified before anything is written (the tunnel mesh, the parapet sheets: tw_gen, origin 0); a re-run on its own
output finds nothing open and stops: TARGET MISMATCH, nothing written. Level: "simulated" (check_seams, patch_guard --strict).
AI-generated (Claude) for skink52.
"""
import argparse, json, math, os, subprocess, sys, time, zlib
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REPO = os.path.normpath(os.path.join(PROJ, '..', '..'))
OUT = os.path.join(PROJ, 'out')
_spec = importlib.util.spec_from_file_location('tw_check_seams', os.path.join(HERE, 'check_seams.py'))
CS = importlib.util.module_from_spec(_spec); sys.modules['tw_check_seams'] = CS; _spec.loader.exec_module(CS)   # sets sys.path (repo readers)
import vmapedit as V      # noqa: E402
import dmx                # noqa: E402
import safepath           # noqa: E402
import numpy as np        # noqa: E402
LY = CS.LY

GROUP = 'tw_gen'
CAP_IN, CAP_DOWN = 1.0, 1.0          # cap edge: 1 u behind the wall face, 1 u under the siding top
CAP_REACH = 30.0                     # a sheet edge this close to a wall (true distance) can be bridged
SNAP_UNDER = 0.3
SAP_RISE_ROWS = (1.0, 0.75, 0.5, 0.25)
SAP_Y = LY.TUN_PORTAL_Y
SAP_CAP = (2080.0, 2208.0, -2880.0, -2816.0)          # |x| range and y range of the terrain cut over the mouth


class Mismatch(Exception): pass


# ================================================================ mesh writing (the layout of create/vmesh.polymesh_open)
def split_pinches(verts, faces, attrs):
    """give each face fan around a vertex its own vertex (two fans touching at a corner cannot be one half-edge vertex)"""
    parent = {}
    def find(c):
        while parent[c] != c:
            parent[c] = parent[parent[c]]; c = parent[c]
        return c
    by_edge = {}
    for f, loop in enumerate(faces):
        n = len(loop)
        for k in range(n):
            c = (f, k); parent[c] = c
            v = loop[k]
            for x in (loop[k - 1], loop[(k + 1) % n]):
                by_edge.setdefault((v, min(v, x), max(v, x)), []).append(c)
    for cs in by_edge.values():
        for c in cs[1:]:
            a, b = find(cs[0]), find(c)
            if a != b: parent[b] = a
    fans = {}
    for f, loop in enumerate(faces):
        for k, v in enumerate(loop):
            fans.setdefault(v, {}).setdefault(find((f, k)), []).append((f, k))
    new = [list(l) for l in faces]; extra = []
    for v, groups in fans.items():
        for g in list(groups.values())[1:]:
            nv = len(verts) + len(extra); extra.append(v)
            for f, k in g: new[f][k] = nv
    if extra:
        verts = np.vstack([verts, verts[extra]])
        attrs = {k: np.vstack([a, a[extra]]) for k, a in attrs.items()}
    return verts, new, attrs


def halfedges(faces, nv):
    """half-edge arrays of an open mesh (faces CCW from the visible side): opposite = i ^ 1, boundary half-edges face -1"""
    he_from, he_to, he_face, key, face_first = [], [], [], {}, []
    for f, loop in enumerate(faces):
        face_first.append(len(he_to))
        for k in range(len(loop)):
            a, b = loop[k], loop[(k + 1) % len(loop)]
            if (a, b) in key: raise Mismatch('non-manifold cap mesh: edge %s twice' % ((a, b),))
            key[(a, b)] = len(he_to); he_from.append(a); he_to.append(b); he_face.append(f)
    nfh = len(he_to)
    nxt = [0] * nfh
    for f, loop in enumerate(faces):
        s = face_first[f]
        for k in range(len(loop)): nxt[s + k] = s + (k + 1) % len(loop)
    for (a, b), i in list(key.items()):
        if (b, a) not in key:
            key[(b, a)] = len(he_to); he_from.append(b); he_to.append(a); he_face.append(-1); nxt.append(-1)
    nhe = len(he_to)
    out_b = {}
    for i in range(nfh, nhe):
        if he_from[i] in out_b: raise Mismatch('pinched boundary vertex %d' % he_from[i])
        out_b[he_from[i]] = i
    for i in range(nfh, nhe): nxt[i] = out_b.get(he_to[i], i)
    order, done = [], set()
    for i in range(nhe):
        if i in done: continue
        j = key[(he_to[i], he_from[i])]; order += [i, j]; done |= {i, j}
    old = np.array(order)
    remap = np.empty(nhe, np.int64); remap[old] = np.arange(nhe)
    E_dest = np.array(he_to)[old]; E_face = np.array(he_face)[old]; E_next = remap[np.array(nxt)[old]]
    E_opp = np.arange(nhe) ^ 1
    v_edge = np.zeros(nv, np.int64)
    src = E_dest[E_opp]
    for i in range(nhe): v_edge[src[i]] = i
    for i in range(nhe):
        if E_face[i] < 0: v_edge[src[i]] = i
    f_edge = remap[np.array(face_first)]
    return dict(E_dest=E_dest, E_face=E_face, E_next=E_next, E_opp=E_opp, v_edge=v_edge, f_edge=f_edge, nhe=nhe, nv=nv)


def streams(m, arr): return {m.E[s]['name'].decode(): s for s in (m.g(arr, b'streams') or [])}
def sdata(m, s): return dmx.geta(m.E[s], b'data')
def set_arr(m, el, name, val): dmx.geta(m.E[el], name)[2] = val


def newell(P):
    q = np.roll(P, -1, axis=0)
    n = np.array([np.sum((P[:, 1] - q[:, 1]) * (P[:, 2] + q[:, 2])), np.sum((P[:, 2] - q[:, 2]) * (P[:, 0] + q[:, 0])),
                  np.sum((P[:, 0] - q[:, 0]) * (P[:, 1] + q[:, 1]))])
    l = np.linalg.norm(n)
    return n / l if l > 0 else np.array([0, 0, 1.0])


def mesh_info(m, n):
    """a mesh node's arrays: positions, face loops (vertex ids), per face-vertex paint / uv, the planar uv fit"""
    md = m.g(n, b'meshData')
    vst = streams(m, m.g(md, b'vertexData')); fst = streams(m, m.g(md, b'faceVertexData'))
    P = np.array(sdata(m, vst['position:0'])[2], float)
    vdi = m.g(md, b'vertexDataIndices'); evi = m.g(md, b'edgeVertexIndices'); evd = m.g(md, b'edgeVertexDataIndices')
    efi = m.g(md, b'edgeFaceIndices'); nxt = m.g(md, b'edgeNextIndices'); fei = m.g(md, b'faceEdgeIndices')
    return dict(md=md, vst=vst, fst=fst, P=P, vdi=vdi, evi=evi, evd=evd, efi=efi, nxt=nxt, fei=fei)


def vertex_paint(m, mi):
    """per vertex average of the face-vertex paint / tint, the uv fit (u, v = a x + b y + c) and the first tangent"""
    P, fst = mi['P'], mi['fst']
    nv = len(P)
    B = np.zeros((nv, 4)); T = np.zeros((nv, 4)); c = np.zeros(nv)
    bp = sdata(m, fst['VertexPaintBlendParams:0'])[2] if 'VertexPaintBlendParams:0' in fst else None
    tc = sdata(m, fst['VertexPaintTintColor:0'])[2] if 'VertexPaintTintColor:0' in fst else None
    tx = sdata(m, fst['texcoord:0'])[2]
    A, U, Vv = [], [], []
    for h in range(len(mi['evi'])):
        if mi['efi'][h] < 0: continue
        v = mi['vdi'][mi['evi'][h]]
        if bp is not None: B[v] += bp[mi['evd'][h]]
        if tc is not None: T[v] += tc[mi['evd'][h]]
        c[v] += 1
        A.append((P[v, 0], P[v, 1], 1.0)); U.append(tx[mi['evd'][h]][0]); Vv.append(tx[mi['evd'][h]][1])
    B /= np.maximum(c, 1)[:, None]; T /= np.maximum(c, 1)[:, None]
    if bp is None: B[:] = [0, 0, 0, 0]
    if tc is None: T[:] = [1, 1, 1, 1]
    A = np.array(A)
    cu = np.linalg.lstsq(A, np.array(U), rcond=None)[0]; cv = np.linalg.lstsq(A, np.array(Vv), rcond=None)[0]
    tan0 = next((sdata(m, fst['tangent:0'])[2][mi['evd'][h]] for h in range(len(mi['evi'])) if mi['efi'][h] >= 0), [1.0, 0.0, 0.0, -1.0])
    return B, T, cu, cv, tan0


def write_mesh(m, md, P, faces, Bv, Tv, cu, cv, tan0, vertical=None):
    """overwrite a meshData with a new open mesh (P world = local: the node sits at origin 0); vertical: per face, True for a wall face
    (texture axes x / -z instead of the planar x / -y)"""
    P = np.asarray(P, float)
    P, faces, at = split_pinches(P, faces, dict(B=np.asarray(Bv, float), T=np.asarray(Tv, float)))
    Bv, Tv = at['B'], at['T']
    G = halfedges(faces, len(P))
    nhe, nf, nvx = G['nhe'], len(faces), G['nv']
    vertical = list(vertical) if vertical is not None else [False] * nf
    fn = np.array([newell(P[f]) for f in faces])
    fh = G['E_face'] >= 0
    dv = G['E_dest'][fh]; ff = G['E_face'][fh]
    tex = np.zeros((nhe, 2)); nrm = np.zeros((nhe, 3)); tan = np.zeros((nhe, 4)); tco = np.zeros((nhe, 4)); bpa = np.zeros((nhe, 4))
    vf = np.array(vertical, bool)[ff]
    ku = abs(cu[0]) if abs(cu[0]) > 1e-9 else abs(cu[1]); kv = abs(cv[1]) if abs(cv[1]) > 1e-9 else abs(cv[0])
    tex[fh, 0] = np.where(vf, cu[0] * P[dv, 0] + cu[1] * P[dv, 1] + cu[2], cu[0] * P[dv, 0] + cu[1] * P[dv, 1] + cu[2])
    tex[fh, 1] = np.where(vf, -kv * P[dv, 2], cv[0] * P[dv, 0] + cv[1] * P[dv, 1] + cv[2])
    nrm[fh] = fn[ff]; tan[fh] = tan0; tco[fh] = Tv[dv]; bpa[fh] = Bv[dv]
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
            else:
                first = dd[2][0] if dd[2] else 0
                dd[2] = [list(first) if isinstance(first, list) else first for _ in range(n_)]
    fill(m.g(md, b'vertexData'), nvx, {'position:0': L(P)})
    fill(m.g(md, b'faceVertexData'), nhe, {'texcoord:0': L(tex), 'texcoord:1': [[0.0, 0.0]] * nhe, 'normal:0': L(nrm), 'tangent:0': L(tan),
                                         'VertexPaintTintColor:0': L(tco), 'VertexPaintBlendParams:0': L(bpa)})
    fill(m.g(md, b'edgeData'), nhe // 2, {'flags:0': [0] * (nhe // 2)})
    fd = m.g(md, b'faceData')
    fs = streams(m, fd)
    first = {k: (sdata(m, s)[2][0] if sdata(m, s)[2] else None) for k, s in fs.items()}
    vals = {'materialindex:0': [0] * nf, 'flags:0': [0] * nf, 'lightmapScaleBias:0': [0] * nf}
    if 'textureAxisV:0' in fs and first['textureAxisV:0'] is not None:
        vals['textureAxisV:0'] = [[0.0, 0.0, -1.0, 0.0] if vertical[f] else list(first['textureAxisV:0']) for f in range(nf)]
    fill(fd, nf, vals)
    sd = m.g(md, b'subdivisionData')
    if sd is not None and sd >= 0: set_arr(m, sd, b'subdivisionLevels', [0] * nhe)
    return nf


def clone_mesh_node(m, src, node_id):
    """a copy of a mesh node (its node attributes: vis group, lighting, physics), appended to the world; -> (node, meshData)"""
    memo = {}
    e = m.import_subtree(m, src, memo, node_id)
    dmx.set_(m.E[e], b'referenceID', dmx.T_U64, int.from_bytes(os.urandom(8), 'little') >> 1)
    dmx.geta(m.E[m.world], b'children')[2].append(e)
    return e, m.g(e, b'meshData')


def update_positions(m, mi, newP, changed):
    """write moved vertex positions and the normals of every face touching a moved vertex"""
    sdata(m, mi['vst']['position:0'])[2] = [[float(a), float(b), float(c)] for a, b, c in newP]
    nrm = sdata(m, mi['fst']['normal:0'])
    nn = [list(map(float, v)) for v in nrm[2]]
    ch = set(int(v) for v in changed)
    for he in mi['fei']:
        hs, h = [], he
        for _ in range(512):
            hs.append(h); h = mi['nxt'][h]
            if h == he: break
        vids = [mi['vdi'][mi['evi'][x]] for x in hs]
        if not ch.intersection(vids): continue
        n = newell(newP[vids])
        for x in hs: nn[mi['evd'][x]] = [float(n[0]), float(n[1]), float(n[2])]
    nrm[2] = nn


# ================================================================ terrain height (exact triangles)
class Surface:
    def __init__(s, sc, kinds=('terrain',), bin_=32.0):
        TT = []
        for me in sc['meshes']:
            if me['kind'] in kinds:
                T, _ = CS.tris_of(me)
                if len(T): TT.append(T)
        s.T = np.concatenate(TT); s.bin = bin_
        lo = s.T.min(1); hi = s.T.max(1)
        s.bins = {}
        for t in range(len(s.T)):
            for i in range(int(math.floor(lo[t, 0] / bin_)), int(math.floor(hi[t, 0] / bin_)) + 1):
                for j in range(int(math.floor(lo[t, 1] / bin_)), int(math.floor(hi[t, 1] / bin_)) + 1):
                    s.bins.setdefault((i, j), []).append(t)

    def z(s, x, y, below=None):
        """the highest surface z at (x, y) (under `below` when given), nan when none"""
        c = s.bins.get((int(math.floor(x / s.bin)), int(math.floor(y / s.bin))))
        if not c: return float('nan')
        T = s.T[c]
        a, b, cc = T[:, 0], T[:, 1], T[:, 2]
        den = (b[:, 1] - cc[:, 1]) * (a[:, 0] - cc[:, 0]) + (cc[:, 0] - b[:, 0]) * (a[:, 1] - cc[:, 1])
        ok = np.abs(den) > 1e-9
        den = np.where(ok, den, 1.0)
        l1 = ((b[:, 1] - cc[:, 1]) * (x - cc[:, 0]) + (cc[:, 0] - b[:, 0]) * (y - cc[:, 1])) / den
        l2 = ((cc[:, 1] - a[:, 1]) * (x - cc[:, 0]) + (a[:, 0] - cc[:, 0]) * (y - cc[:, 1])) / den
        l3 = 1 - l1 - l2
        e = -1e-7
        inn = ok & (l1 >= e) & (l2 >= e) & (l3 >= e)
        if not inn.any(): return float('nan')
        z = (l1 * a[:, 2] + l2 * b[:, 2] + l3 * cc[:, 2])[inn]
        if below is not None:
            z = z[z <= below]
            if not len(z): return float('nan')
        return float(z.max())


# ================================================================ walls and siding tops
def wall_segments():
    """world wall lines of both trench systems: (p0, p1) 2-d"""
    segs = []
    for s in (1, -1):
        for (p0, p1, n) in LY.raster().walls():
            segs.append(((s * p0[0], p0[1]), (s * p1[0], p1[1])))
    return np.array(segs, float)


def closest_on_walls(W, p, reach):
    A, B = W[:, 0], W[:, 1]
    d = B - A
    L2 = (d ** 2).sum(1)
    t = np.clip(((p[None, :] - A) * d).sum(1) / np.maximum(L2, 1e-9), 0, 1)
    Q = A + d * t[:, None]
    dist = np.hypot(*(Q - p[None, :]).T)
    k = int(np.argmin(dist))
    return (Q[k], float(dist[k])) if dist[k] <= reach else (None, float(dist[k]))


Sidings = CS.Sidings


# ================================================================ the plan
def plan(m, sc, log=print):
    """-> dict of planned changes; raises Mismatch when the targets are not what this patch was written for"""
    meshes = sc['meshes']
    by_nid = {me['nid']: me for me in meshes}
    node_of = {}
    for n, p in m.walk():
        if m.type(n) == b'CMapMesh': node_of[m.g(n, b'nodeID')] = n
    tun = [me for me in meshes if me['kind'] == 'tunnel']
    if len(tun) != 1 or tun[0]['vg'] != GROUP: raise Mismatch('want one generated tunnel mesh, found %s' % [(t['nid'], t['vg']) for t in tun])
    parapets = [me for me in meshes if me['kind'] == 'parapet']
    for me in parapets:
        n = node_of[me['nid']]
        if me['vg'] != GROUP: raise Mismatch('parapet sheet %d is not in %s' % (me['nid'], GROUP))
        if list(m.g(n, b'origin')) != [0.0, 0.0, 0.0] or any(m.g(n, b'angles')) or list(m.g(n, b'scales')) != [1.0, 1.0, 1.0]:
            raise Mismatch('parapet sheet %d is moved / rotated / scaled' % me['nid'])
    rasters = {sg: CS.build_raster(sc, sg, log) for sg in (1, -1)}
    W = wall_segments()
    SD = Sidings(sc)
    terr = Surface(sc, ('terrain',))
    plan_ = dict(caps={}, snaps={}, sap={}, user_walls=[], skipped=[])

    # ---- 1. sheet lips: open outer boundary vertices of parapet sheets standing over the terrain
    cracks, st = CS.mesh_cracks(sc, list(rasters.values()), log)
    snap = {}                                   # rounded position -> new z
    for c in cracks:
        if c['mesh']['kind'] != 'parapet' or c['other']['kind'] != 'terrain' or c['owner'] != 'generated': continue
        for (k, a, b) in c['edges']:
            me = meshes[k]
            A, B = me['P'][a], me['P'][b]
            za, zb = terr.z(A[0], A[1]), terr.z(B[0], B[1])
            zm = terr.z((A[0] + B[0]) / 2, (A[1] + B[1]) / 2)
            if not (np.isfinite(za) and np.isfinite(zb) and np.isfinite(zm)): continue
            na, nb = min(A[2], za - SNAP_UNDER), min(B[2], zb - SNAP_UNDER)
            over = (na + nb) / 2 - (zm - SNAP_UNDER)
            if over > 0: na -= over; nb -= over
            for P_, nz in ((A, na), (B, nb)):
                key = tuple(np.round(P_[:2], 2))
                if nz < P_[2] - 1e-4:
                    snap[key] = min(snap.get(key, P_[2]), nz)
    plan_['snaps'] = snap
    log('sheet lips: %d parapet / terrain crack instances, %d sheet edge vertices to lower' % (
        sum(1 for c in cracks if c['mesh']['kind'] == 'parapet' and c['other']['kind'] == 'terrain'), len(snap)))

    # ---- 2. siding caps: parapet inner boundary edges across an open slot from a generated siding
    ncap = 0
    raise_ = {}
    for me in parapets:
        sg = 1 if me['lo'][0] > 0 else -1
        R = rasters[sg]
        d, g, ins = CS.footprint(R, sg)
        top_m = R.mesh
        quads = []
        for a, b, f in me['bnd']:
            A, B = me['P'][a], me['P'][b]
            ws = []
            for P_ in (A, B):
                w, dist = closest_on_walls(W, P_[:2], CAP_REACH)
                ws.append(w)
            if ws[0] is None or ws[1] is None: continue
            # the slot: the ground between the wall and the sheet edge is far under the bank (carved to the floor)
            openish = 0
            for t in (0.35, 0.65):
                q = (ws[0] + ws[1]) / 2 * (1 - t) + (A[:2] + B[:2]) / 2 * t
                i, j = R.cell(q[0], q[1])
                if 0 <= i < R.nx and 0 <= j < R.ny and top_m[i, j] < g[i, j] - CS.HOLE_DZ: openish += 1
            if not openish: continue
            tops = [SD.tops(w) for w in ws]
            if any(not t for t in tops):
                plan_['skipped'].append(dict(why='no siding at the wall', x=round(float(A[0]), 1), y=round(float(A[1]), 1)))
                continue
            if any(not any(tt[2] for tt in t) for t in tops):     # only a removable / named user siding there (a blocker): leave it
                plan_['user_walls'].append(dict(x=round(float(A[0]), 1), y=round(float(A[1]), 1), z=round(float(A[2]), 1)))
                continue
            if any(tt[1] == "user" for t in tops for tt in t): plan_['user_backed'] = plan_.get('user_backed', 0) + 1
            # the cap meets the highest siding top over each wall point; where a lower one meets it (a corner of two wall heights) a
            # step face closes the opening between the lower top and the cap's edge
            sel = []
            for k in range(2):
                cap_ = [tt for tt in tops[k] if tt[2]]
                hi_ = max(cap_)
                sel.append((np.array(hi_[3]), hi_[0], min(tt[0] for tt in cap_)))
            quads.append(((a, b), sel))
        if not quads: continue
        # vertices: the sheet's boundary vertices as they are (after the lip snaps) + the inner edge, shared by position
        verts, vid = [], {}
        def V_(key, p):
            if key not in vid: vid[key] = len(verts); verts.append(np.asarray(p, float))
            return vid[key]
        faces, src_v, steps = [], [], {}
        for (a, b), wt in quads:
            ids = []
            for v, (w, zt, zlo) in zip((a, b), wt):
                P_ = me['P'][v].copy()
                k2 = tuple(np.round(P_[:2], 2))
                if k2 in snap: P_[2] = snap[k2]
                inner = np.array([w[0], w[1], zt - CAP_DOWN])            # 1 u behind the siding's face, 1 u under its top
                if np.hypot(*(P_[:2] - inner[:2])) < 4.0:
                    # a sheet vertex pinched against the wall (a bank corner): it is raised to the cap's edge and is the edge itself
                    P_[2] = inner[2]; raise_[k2] = inner[2]
                    bi = V_(('s', int(v)), P_); verts[bi] = P_
                    ids.append((bi, bi, v)); continue
                ki = ('w',) + tuple(np.round(inner[:2], 1))
                ids.append((V_(('s', int(v)), P_), V_(ki, inner), v))
                steps[vid[ki]] = min(steps.get(vid[ki], zlo - CAP_DOWN), zlo - CAP_DOWN)
            (b1, i1, va), (b2, i2, vb) = ids
            loop = [b1, b2, i2, i1]
            loop = [x for k_, x in enumerate(loop) if x not in loop[:k_]]
            if len(loop) < 3: continue
            Pl = np.array([verts[x] for x in loop])
            if newell(Pl)[2] < 0: loop = loop[::-1]
            if abs(newell(np.array([verts[x] for x in loop]))[2]) < 0.2: continue       # a sliver standing on edge: skip
            faces.append(loop); src_v.append((va, vb))
        # weld: an inner vertex within 2 u of one of the sheet's boundary vertices (a bank corner pinched against the wall) takes that
        # vertex's position, and the sheet vertex is raised to the cap edge's height
        bv = sorted({int(v) for a_, b_, f_ in me['bnd'] for v in (a_, b_)})
        if bv:
            from scipy.spatial import cKDTree
            kd = cKDTree(me['P'][bv][:, :2])
            remap = {}
            for key_, i_ in list(vid.items()):
                if key_[0] != 'w': continue
                dd_, jj_ = kd.query(verts[i_][:2])
                if dd_ > 2.0: continue
                v_ = bv[int(jj_)]
                k2 = tuple(np.round(me['P'][v_][:2], 2))
                zt_ = float(verts[i_][2])
                raise_[k2] = max(raise_.get(k2, -1e9), zt_)
                if ('s', v_) in vid:
                    j_ = vid[('s', v_)]; verts[j_][2] = raise_[k2]; remap[i_] = j_
                else:
                    verts[i_][:2] = me['P'][v_][:2]; verts[i_][2] = raise_[k2]
            if remap:
                nf_, nsv = [], []
                for f, sv in zip(faces, src_v):
                    f2 = [remap.get(x, x) for x in f]
                    f2 = [x for k_, x in enumerate(f2) if x not in f2[:k_]]
                    if len(f2) >= 3: nf_.append(f2); nsv.append(sv)
                faces, src_v = nf_, nsv
                steps = {k_: v_ for k_, v_ in steps.items() if k_ not in remap}     # a welded corner gets no step face
        # step faces: below an inner edge whose end stands over a lower siding top, a wall face down to 1 u under that top, facing the
        # trench (away from the sheet)
        edges_in = {}
        for f in faces:
            for k in range(len(f)):
                x0_, x1_ = f[k], f[(k + 1) % len(f)]
                if x0_ in steps and x1_ in steps: edges_in[(x0_, x1_)] = edges_in.get((x0_, x1_), 0) + 1
        sheet_xy = me['P'][sorted({int(v) for a_, b_, f_ in me['bnd'] for v in (a_, b_)})][:, :2]
        def on_sheet(x_):
            return bool(len(sheet_xy)) and float(np.min(np.hypot(*(sheet_xy - np.asarray(verts[x_])[:2]).T))) < 0.5
        for (x0_, x1_), cnt in list(edges_in.items()):
            if (x1_, x0_) in edges_in: continue                           # interior edge of the strip
            if on_sheet(x0_) or on_sheet(x1_): continue                   # a corner welded to the sheet: no step face
            h0 = verts[x0_][2] - steps[x0_]; h1 = verts[x1_][2] - steps[x1_]
            if max(h0, h1) < 1.5: continue
            lo_ = []
            for x_, h_ in ((x1_, h1), (x0_, h0)):
                if h_ < 0.5: lo_.append(x_)
                else:
                    q = verts[x_].copy(); q[2] = steps[x_]
                    lo_.append(V_(('lo', x_), q))
            # the strip runs x0 -> x1 along this boundary edge; the wall face hangs under it: x1, x0, lo(x0), lo(x1)
            quad = [x1_, x0_, lo_[1], lo_[0]]
            quad = [q for k_, q in enumerate(quad) if q not in quad[:k_]]
            if len(quad) < 3: continue
            faces.append(quad); src_v.append(None)
        vertical = [sv is None for sv in src_v]
        # a face that would repeat a directed edge (two sheet vertices behind one stretch of a corner) overlaps one already made: drop it
        used, keep = set(), []
        for k_, f in enumerate(faces):
            de_ = [(f[i_], f[(i_ + 1) % len(f)]) for i_ in range(len(f))]
            if any(e_ in used for e_ in de_): continue
            used.update(de_); keep.append(k_)
        faces = [faces[k_] for k_ in keep]; vertical = [vertical[k_] for k_ in keep]; src_v = [src_v[k_] for k_ in keep]
        if faces:
            plan_['caps'][me['nid']] = dict(verts=np.array(verts), faces=faces, src=me['nid'], vertical=vertical,
                                            src_of={vid[k]: k[1] for k in vid if k[0] == 's'})
            ncap += len(faces)
    snap.update(raise_)                                  # pinched sheet vertices at bank corners: raised to the cap edge
    plan_['raised'] = len(raise_)
    log('siding caps: %d strips (%d sheets; %d against user sidings); %d pinched sheet vertices raised; %d sheet edges behind a '
        'removable user blocker left open; %d with no siding at the wall' % (ncap, len(plan_['caps']), plan_.get('user_backed', 0), len(raise_),
                                                                            len(plan_['user_walls']), len(plan_['skipped'])))

    # ---- 3. the sap mouths
    tP = tun[0]['P']
    for s in (1, -1):
        xs = [s * x for x in np.arange(LY.TUN_SAP_X[0], LY.TUN_SAP_X[1] + 0.1, LY.TUN_CELL)]
        rows = [SAP_Y - k * LY.TUN_CELL for k in range(len(SAP_RISE_ROWS))]
        floor_v, roof_edge = {}, []
        for x in xs:
            for y in rows:
                ids = np.nonzero((np.abs(tP[:, 0] - x) < 0.01) & (np.abs(tP[:, 1] - y) < 0.01))[0]
                if len(ids) < 2: raise Mismatch('tunnel vertices at (%.0f, %.0f): %d' % (x, y, len(ids)))
                zs = tP[ids, 2]
                fl = ids[zs < zs.min() + 0.01]; rf = ids[zs > zs.max() - 0.01]
                floor_v[(x, y)] = fl
                if y == SAP_Y: roof_edge.append((x, int(rf[0]), float(zs.max())))
        # the trench floor edge of the terrain at the portal (the terrain's cut over the sap starts there)
        rise = {}
        for x in xs:
            zt = terr.z(x, SAP_Y + 0.05)
            if not np.isfinite(zt): raise Mismatch('no terrain floor at the %s sap portal x %.0f' % ('ct' if s > 0 else 't', x))
            z0 = float(tP[floor_v[(x, SAP_Y)][0], 2])
            if not (6.0 < zt - z0 < 18.0): raise Mismatch('%s sap riser at x %.0f is %.1f u (expected about 12: patched already?)' % ('ct' if s > 0 else 't', x, zt - z0))
            rise[x] = zt - z0
        moves = {}
        for x in xs:
            for k, y in enumerate(rows):
                for v in floor_v[(x, y)]: moves[int(v)] = float(tP[v, 2] + rise[x] * SAP_RISE_ROWS[k])
        # lintel + cap: a 4-u grid over the terrain cut, 0.3 u over the parapet where that reaches (and over the parapet's open edges
        # there, interpolated from them), its outer ring 0.3 u under the parapet so it comes out from under it; the lintel stands on
        # the roof's portal edge and meets the cap's portal row
        cx0, cx1, cy0, cy1 = SAP_CAP
        gx = [s * x for x in np.arange(cx0, cx1 + 0.1, 4.0)]
        gy = list(np.arange(cy0, cy1 + 0.1, 4.0))
        par = Surface(sc, ('parapet',))
        pbv = []
        for me in parapets:
            for a, b, f in me['bnd']:
                for v in (a, b):
                    q = me['P'][v]
                    if min(abs(q[0] - g_) for g_ in (gx[0], gx[-1])) < 200 and cy0 - 60 < q[1] < cy1 + 60: pbv.append(q)
        pbv = np.unique(np.round(np.array(pbv), 3), axis=0)
        Zc = np.full((len(gx), len(gy)), np.nan)
        for i, x in enumerate(gx):
            for j, y in enumerate(gy):
                zp = par.z(x, y)
                d_ = np.hypot(pbv[:, 0] - x, pbv[:, 1] - y)
                nn = np.argsort(d_)[:4]
                w_ = 1.0 / np.maximum(d_[nn], 0.5) ** 2
                zi = float((pbv[nn, 2] * w_).sum() / w_.sum())
                border = i in (0, len(gx) - 1) or j == 0
                z = zp if np.isfinite(zp) else zi
                Zc[i, j] = z - 0.3 if (border and np.isfinite(zp)) else z + 0.3
        plan_['sap'][s] = dict(moves=moves, rise=rise, roof_edge=roof_edge, gx=gx, gy=gy, Zc=Zc)
        log('sap %s: floor ramp %d vertices (riser %.1f-%.1f u), lintel over %d roof edge vertices, cap %d x %d (4 u)' % (
            'ct' if s > 0 else 't', len(moves), min(rise.values()), max(rise.values()), len(roof_edge), len(gx), len(gy)))
    return plan_, node_of


def apply(m, sc, P, node_of, T, log=print):
    meshes = sc['meshes']
    by_nid = {me['nid']: me for me in meshes}
    node_id = [m.next_node_id()]
    rep = dict(caps=[], snapped_sheets=0, snapped_vertices=0, sap={})
    # 1. lips: every parapet sheet with a vertex at a snapped position
    snap = P['snaps']
    for me in meshes:
        if me['kind'] != 'parapet': continue
        n = node_of[me['nid']]
        mi = mesh_info(m, n)
        keys = [tuple(np.round(p[:2], 2)) for p in mi['P']]
        ch = [v for v, k in enumerate(keys) if k in snap and abs(mi['P'][v, 2] - me['P'][v, 2]) < 1e-6]
        if not ch: continue
        newP = mi['P'].copy()
        for v in ch: newP[v, 2] = snap[keys[v]]
        update_positions(m, mi, newP, ch)
        T['modify'][str(me['nid'])] = dict(i=n, fields=['mesh'], why='sheet edge lowered onto the terrain (%d vertices)' % len(ch))
        rep['snapped_sheets'] += 1; rep['snapped_vertices'] += len(ch)
    # 2. caps: a copy of the sheet's node rewritten as the strip
    for nid, cp in P['caps'].items():
        src = node_of[nid]
        mi = mesh_info(m, src)
        Bv, Tv, cu, cv, tan0 = vertex_paint(m, mi)
        # paint: the strip's sheet-side vertices carry the sheet vertex's paint, the inner ones the paint of the vertex they hang from
        nv = len(cp['verts'])
        Bs = np.zeros((nv, 4)); Ts = np.ones((nv, 4))
        srcv = cp['src_of']
        for f in cp['faces']:
            sv = [srcv[x] for x in f if x in srcv]
            for x in f:
                v0 = srcv.get(x, sv[0] if sv else None)
                if v0 is not None: Bs[x] = Bv[v0]; Ts[x] = Tv[v0]
        e, md = clone_mesh_node(m, src, node_id)
        for f, vt in zip(cp['faces'], cp['vertical']):            # step faces take the paint of the cap edge they hang from
            if vt:
                for x in f:
                    if not Bs[x].any(): Bs[x] = Bs[f[0]]; Ts[x] = Ts[f[0]]
        nf = write_mesh(m, md, cp['verts'], cp['faces'], Bs, Ts, cu, cv, tan0, vertical=cp['vertical'])
        T['add'].append(dict(type='CMapMesh', why='ground cap over the siding-top slot along sheet %d (%d faces)' % (nid, nf)))
        rep['caps'].append(dict(sheet=nid, faces=nf, node=m.g(e, b'nodeID')))
    # 3. sap: tunnel floor ramp + lintel / cap per side
    tme = [me for me in meshes if me['kind'] == 'tunnel'][0]
    tn = node_of[tme['nid']]
    mi = mesh_info(m, tn)
    newP = mi['P'].copy()
    moved = []
    for s, sp in P['sap'].items():
        for v, z in sp['moves'].items():
            if abs(mi['P'][v, 2] - tme['P'][v, 2]) > 1e-6: raise Mismatch('tunnel vertex %d not where the scene read it' % v)
            newP[v, 2] = z; moved.append(v)
    if moved:
        update_positions(m, mi, newP, moved)
        T['modify'][str(tme['nid'])] = dict(i=tn, fields=['mesh'], why='sap mouths: floor rows at the portals ramp up to the trench floor')
    par_src = None
    for s, sp in P['sap'].items():
        # the parapet sheet nearest the mouth gives the node attributes, paint and texture mapping
        cands = [me for me in meshes if me['kind'] == 'parapet' and me['lo'][0] * s > 0]
        mid = np.array([s * 2144.0, SAP_Y - 30.0])
        best = min(cands, key=lambda me: np.min(np.hypot(*(me['P'][:, :2] - mid).T)))
        src = node_of[best['nid']]
        mi2 = mesh_info(m, src)
        Bv, Tv, cu, cv, tan0 = vertex_paint(m, mi2)
        gx, gy, Zc = sp['gx'], sp['gy'], sp['Zc']
        from scipy.spatial import cKDTree
        kd = cKDTree(best['P'][:, :2])
        verts, faces, vert_flag = [], [], []
        idx = {}
        for i, x in enumerate(gx):
            for j, y in enumerate(gy):
                idx[(i, j)] = len(verts); verts.append((x, y, Zc[i, j]))
        for i in range(len(gx) - 1):
            for j in range(len(gy) - 1):
                loop = [idx[(i, j)], idx[(i + 1, j)], idx[(i + 1, j + 1)], idx[(i, j + 1)]]
                Pl = np.array([verts[x] for x in loop])
                if newell(Pl)[2] < 0: loop = loop[::-1]
                faces.append(loop); vert_flag.append(False)
        # lintel: from the roof's portal edge (exact vertices) up to the cap's portal row (the cap row at y = SAP_Y), facing the trench
        jtop = len(gy) - 1
        assert abs(gy[jtop] - SAP_Y) < 1e-6
        roof = sorted(sp['roof_edge'], key=lambda r: r[0] * s)
        bottom = []
        for (x, v, z) in roof:
            bottom.append(len(verts)); verts.append((x, SAP_Y, z))
        top = []
        for (x, v, z) in roof:
            i = int(np.argmin([abs(gx_ - x) for gx_ in gx]))
            if abs(gx[i] - x) < 1e-6: top.append(idx[(i, jtop)])
            else:
                top.append(len(verts)); verts.append((x, SAP_Y, float(np.interp(x * s, [g_ * s for g_ in gx], Zc[:, jtop]))))
        for k in range(len(roof) - 1):
            loop = [bottom[k], bottom[k + 1], top[k + 1], top[k]]
            Pl = np.array([verts[x] for x in loop])
            if newell(Pl)[1] < 0: loop = loop[::-1]          # facing +y: toward the trench
            faces.append(loop); vert_flag.append(True)
        nv = len(verts)
        _, nearest = kd.query(np.array(verts, float)[:, :2])
        e, md = clone_mesh_node(m, src, node_id)
        nf = write_mesh(m, md, np.array(verts, float), faces, Bv[nearest], Tv[nearest], cu, cv, tan0, vertical=vert_flag)
        T['add'].append(dict(type='CMapMesh', why='%s sap mouth: lintel over the portal + ground cap over the terrain cut (%d faces)' % ('ct' if s > 0 else 't', nf)))
        rep['sap']['ct' if s > 0 else 't'] = dict(node=m.g(e, b'nodeID'), faces=nf, ramp_vertices=len(sp['moves']),
                                                    riser=[round(v, 2) for v in sp['rise'].values()])
    return rep


# ================================================================ plugs: whatever bank hole is left once the caps are in
PLUG_CELL = 2.0


def plan_plugs(sc, log=print):
    """bank cells (outside the dug trench, 0.5-112 u behind a wall) whose generated top surface is still 8 u under the bank base after
    the caps (wall ends, corners, sidings moved off the wall line): a 2-u heightfield patch per hole, 0.4 u under whatever closes it
    around (the ground meshes: sheets, caps), so its edges sit under them; inside it, and next to sidings, the height is interpolated"""
    out = {}
    for sg in (1, -1):
        R = CS.build_raster(sc, sg, log)
        d, g, ins = CS.footprint(R, sg)
        top = R.top(False)
        hole = (d > CS.D_IN) & (d < CS.D_OUT) & (top < g - CS.HOLE_DZ)
        from scipy import ndimage
        lab, n = ndimage.label(hole, structure=np.ones((3, 3), bool))
        sizes = ndimage.sum(hole, lab, range(1, n + 1))
        keep = np.isin(lab, [k + 1 for k, sz in enumerate(sizes) if sz >= 2])
        if not keep.any(): continue
        occupied = np.maximum(R.gen, R.user) > np.maximum(R.mesh, g - CS.HOLE_DZ)    # a prop stands there (a siding, sandbags, the user's)
        cov = ndimage.binary_dilation(keep, iterations=3) & (d > 0.5) & (~occupied | keep)   # never over the dug trench or on a prop
        bs = int(PLUG_CELL / R.res)
        nbx, nby = R.nx // bs, R.ny // bs
        blk = cov[:nbx * bs, :nby * bs].reshape(nbx, bs, nby, bs).any(axis=(1, 3))
        closed = ~hole & (R.mesh > g - CS.HOLE_DZ)             # ground meshes only: a prop's top (a siding, sandbags) would make spikes
        verts, vid, faces = [], {}, []
        zt = np.where(closed, R.mesh, np.inf)
        for bi, bj in zip(*np.nonzero(blk)):
            loop = []
            for (ci, cj) in ((bi, bj), (bi + 1, bj), (bi + 1, bj + 1), (bi, bj + 1)):
                if (ci, cj) not in vid:
                    i0, j0 = ci * bs, cj * bs                     # the raster cell corner of this vertex
                    win = zt[max(0, i0 - 2):i0 + 2, max(0, j0 - 2):j0 + 2]
                    z = float(win.min() - 0.4) if np.isfinite(win).any() else np.nan
                    vid[(ci, cj)] = len(verts); verts.append([R.x0 + i0 * R.res, R.y0 + j0 * R.res, z])
                loop.append(vid[(ci, cj)])
            faces.append(loop)
        V_ = np.array(verts, float)
        known = np.isfinite(V_[:, 2])
        known0 = known.copy()
        if not known.any(): continue
        from scipy.spatial import cKDTree
        kd = cKDTree(V_[known, :2])
        for k in np.nonzero(~known)[0]:
            dd, ii = kd.query(V_[k, :2], k=min(6, int(known.sum())))
            w_ = 1.0 / np.maximum(np.atleast_1d(dd), 0.5) ** 2
            V_[k, 2] = float((V_[known][np.atleast_1d(ii), 2] * w_).sum() / w_.sum())
        # skirt: the patch's outer ring drops 6 u, so its edge lies under the ground / sidings it overlaps instead of on them
        use = np.zeros(len(V_), int)
        for f in faces:
            for x in f: use[x] += 1
        V_[(use < 4) & known0, 2] -= 6.0                     # only where it overlaps ground meshes (not against a prop or the trench)
        out[sg] = dict(verts=V_, faces=faces, cells=int(keep.sum()), holes=int(sum(1 for sz in sizes if sz >= 2)))
        log('plugs %s: %d holes (%d cells) left after the caps, %d patch faces' % ('ct' if sg > 0 else 't', out[sg]['holes'], out[sg]['cells'], len(faces)))
    return out


def apply_plugs(m, sc, PL, node_of, T, rep):
    node_id = [m.next_node_id()]
    for sg, pl in PL.items():
        cands = [me for me in sc['meshes'] if me['kind'] == 'parapet' and me['lo'][0] * sg > 0 and me['nid'] in node_of]
        mid = pl['verts'][:, :2].mean(0)
        best = min(cands, key=lambda me: np.min(np.hypot(*(me['P'][:, :2] - mid).T)))
        src = node_of[best['nid']]
        mi = mesh_info(m, src)
        Bv, Tv, cu, cv, tan0 = vertex_paint(m, mi)
        from scipy.spatial import cKDTree
        allp = np.concatenate([me['P'][:, :2] for me in cands]); allB = []; allT = []
        for me in cands:
            mi2 = mesh_info(m, node_of[me['nid']]); b_, t_, _, _, _ = vertex_paint(m, mi2); allB.append(b_); allT.append(t_)
        allB = np.concatenate(allB); allT = np.concatenate(allT)
        _, nn = cKDTree(allp).query(pl['verts'][:, :2])
        e, md = clone_mesh_node(m, src, node_id)
        nf = write_mesh(m, md, pl['verts'], pl['faces'], allB[nn], allT[nn], cu, cv, tan0)
        T['add'].append(dict(type='CMapMesh', why='%s bank plugs: %d holes left after the caps (wall ends, corners) (%d faces)' % ('ct' if sg > 0 else 't', pl['holes'], nf)))
        rep.setdefault('plugs', {})['ct' if sg > 0 else 't'] = dict(node=m.g(e, b'nodeID'), faces=nf, holes=pl['holes'], cells=pl['cells'])


def benches(sc_in, sc_out, log=print):
    """the user's sap benches against the ground before and after the patch: the share of each bench that is inside the earth (under
    the ground surface and not in the tunnel, or under a floor); fully buried / floating ones are listed (never moved)"""
    def state(sc):
        ground = Surface(sc, ('terrain', 'parapet'))          # the caps read as parapet sheets
        tun = Surface(sc, ('tunnel',))
        out = {}
        for pr in sc['props']:
            if 'tl_bench' not in pr['model'] or pr['owner'] != 'user': continue
            if not (abs(abs(pr['o'][0]) - LY.TUN_SAP_XC) < 120 and SAP_Y - 60 < pr['o'][1] < SAP_Y + 40): continue
            T = CS.model_tris(pr['model'])
            Pw = CS.sample_tris(T, 2.0) @ pr['R'].T + pr['o']
            inside = 0
            for q in Pw:
                g_ = ground.z(q[0], q[1])
                zs = CS._vert_hits(tun.T[tun.bins.get((int(math.floor(q[0] / tun.bin)), int(math.floor(q[1] / tun.bin))), [])], q[0], q[1])                     if tun.bins.get((int(math.floor(q[0] / tun.bin)), int(math.floor(q[1] / tun.bin)))) else np.zeros(0)
                in_tunnel = len(zs) >= 2 and zs.min() < q[2] < zs.max()
                below_ground = np.isfinite(g_) and q[2] < g_
                if below_ground and not in_tunnel: inside += 1
            out[pr['nid']] = dict(o=[round(float(v), 1) for v in pr['o']], zmin=round(float(Pw[:, 2].min()), 1), zmax=round(float(Pw[:, 2].max()), 1),
                                  in_earth=round(inside / max(len(Pw), 1), 2))
        return out
    a, b = state(sc_in), state(sc_out)
    res = []
    for nid, v in b.items():
        st = 'fully buried' if v['in_earth'] > 0.98 else 'floating' if v['in_earth'] < 0.01 and v['zmin'] > -60 and False else 'ok'
        res.append(dict(nid=nid, **v, in_earth_before=a.get(nid, {}).get('in_earth'), state=st))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description='seam patch: siding caps, sheet lips, sap mouths')
    ap.add_argument('--in', dest='inp', default=os.path.join(OUT, 'step9', 'chain', '3_terrain.vmap'))
    ap.add_argument('--out', default=os.path.join(OUT, 'mg_trenchwarfare_seams.vmap'))
    ap.add_argument('--targets', default=None)
    ap.add_argument('--report', default=None)
    ap.add_argument('--no-guard', action='store_true')
    a = ap.parse_args(argv)
    for st_ in (sys.stdout, sys.stderr):
        if hasattr(st_, 'reconfigure'): st_.reconfigure(encoding='utf-8', errors='replace')
    inp, outp = os.path.abspath(a.inp), os.path.abspath(a.out)
    if not safepath.inside(OUT, outp) or os.path.normcase(outp) == os.path.normcase(inp):
        sys.exit('patch_seams: --out must be under %s and not the input' % OUT)
    tp = a.targets or os.path.splitext(outp)[0] + '.targets.json'
    rp = a.report or os.path.splitext(outp)[0] + '.report.json'
    t0 = time.time()
    raw = open(inp, 'rb').read()
    m = V.Map(inp, data=raw); m.path = inp
    sc = CS.load_scene(inp)
    T = dict(input=inp, input_bytes=len(raw), input_crc32='%08x' % (zlib.crc32(raw) & 0xffffffff), modify={}, remove={}, add=[], prefix=[], root=False)
    try:
        P, node_of = plan(m, sc)
        if not (P['caps'] or P['snaps'] or P['sap']): raise Mismatch('nothing open to close (patched already?)')
        rep = apply(m, sc, P, node_of, T)
        # second pass: what the caps left open, read back from the capped map
        tmp = os.path.splitext(outp)[0] + '.caps.vmap'
        m.save(tmp)
        sc_c = CS.load_scene(tmp)
        PL = plan_plugs(sc_c)
        node_of2 = {}
        for n_, p_ in m.walk():
            if m.type(n_) == b'CMapMesh': node_of2[m.g(n_, b'nodeID')] = n_
        if PL: apply_plugs(m, sc_c, PL, node_of2, T, rep)
        os.remove(tmp)
    except Mismatch as ex:
        sys.exit('patch_seams: TARGET MISMATCH, nothing written: %s' % ex)
    n = m.save(outp)
    T['output'] = outp
    os.makedirs(os.path.dirname(os.path.abspath(tp)), exist_ok=True)
    json.dump(T, open(tp, 'w'), indent=1)
    # the user's benches against the new sap floor
    sc2 = CS.load_scene(outp)
    rep['benches'] = benches(sc, sc2)
    rep['user_walls_left_open'] = P['user_walls']; rep['no_siding'] = P['skipped']
    rep.update(input=inp, output=outp, input_crc32=T['input_crc32'], seconds=round(time.time() - t0, 1))
    json.dump(rep, open(rp, 'w'), indent=1, default=float)
    bad = [b for b in rep['benches'] if b['state'] == 'fully buried']
    print('patched map: %s (%d bytes); %d sheet edges lowered (%d vertices), %d cap strips, sap %s; benches %d checked, %d buried; %.1f s'
          % (outp, n, rep['snapped_sheets'], rep['snapped_vertices'], len(rep['caps']), ', '.join('%s %d faces' % (k, v['faces']) for k, v in rep['sap'].items()),
             len(rep['benches']), len(bad), time.time() - t0))
    if not a.no_guard:
        r = subprocess.run([sys.executable, os.path.join(HERE, 'patch_guard.py'), inp, outp, tp, '--strict', '--report',
                            os.path.splitext(outp)[0] + '.guard.json'], capture_output=True, text=True)
        print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-400:])
        if r.returncode: sys.exit('patch_seams: GUARD FAILED')


if __name__ == '__main__':
    main()
