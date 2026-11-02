"""Hammer (.vmap) element builders: polygon meshes (open or closed), map meshes and entities.

Half-edge layout follows Valve's own files: half-edges come in pairs (h, h ^ 1), boundary half-edges have face -1 and
link to the next boundary half-edge leaving their destination vertex, and a boundary vertex points at its boundary
out-edge. Faces are vertex loops, counter-clockwise seen from the front.
"""
import math, random
from dmx9 import Element, T_ELEMENT, T_INT, T_FLOAT, T_BOOL, T_STRING, T_COLOR, T_VEC2, T_VEC3, T_VEC4, T_QANGLE, T_UINT64, ARRAY

_next_node = [1000]
_rng = random.Random(16)


def set_first_node(n):
    _next_node[0] = n


def nid():
    _next_node[0] += 1
    return _next_node[0]


def rid():
    return _rng.getrandbits(63)


def stream(name, attr, sem, data, t, loc=0, flags=1):
    s = Element("CDmePolygonMeshDataStream", name)
    s.set("standardAttributeName", T_STRING, attr); s.set("semanticName", T_STRING, sem); s.set("semanticIndex", T_INT, 0)
    s.set("vertexBufferLocation", T_INT, loc); s.set("dataStateFlags", T_INT, flags); s.set("subdivisionBinding", T_ELEMENT, None)
    s.set("data", t | ARRAY, data)
    return s


def data_array(size, streams):
    a = Element("CDmePolygonMeshDataArray", "")
    a.set("size", T_INT, size); a.set("streams", T_ELEMENT | ARRAY, streams)
    return a


def newell(P):
    n = [0.0, 0.0, 0.0]
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2]); n[1] += (a[2] - b[2]) * (a[0] + b[0]); n[2] += (a[0] - b[0]) * (a[1] + b[1])
    l = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]) or 1.0
    return (n[0] / l, n[1] / l, n[2] / l)


def default_axes(n):
    ax = max(range(3), key=lambda i: abs(n[i]))
    if ax == 2: return (1.0, 0.0, 0.0), (0.0, -1.0, 0.0)
    if ax == 0: return (0.0, 1.0, 0.0), (0.0, 0.0, -1.0)
    return (1.0, 0.0, 0.0), (0.0, 0.0, -1.0)


class Face:
    """loop: world-space vertex positions (CCW from the front). mat: material path.
    uv: optional list of (u, v) per vertex (already divided by the texture size).
    axes: optional (axisU(xyz), offsetU, scaleU, axisV(xyz), offsetV, scaleV) kept for editing in Hammer."""
    __slots__ = ("loop", "mat", "uv", "axes")

    def __init__(self, loop, mat, uv=None, axes=None):
        self.loop, self.mat, self.uv, self.axes = loop, mat, uv, axes


def polymesh(faces, origin, weld=1e-3, texsize=512.0, islands=False):
    """faces: [Face]. Returns CDmePolygonMesh with vertices relative to origin.
    islands: every face gets its own vertices (no shared edges at all), for loose sets of faces such as sky shells."""
    q = 1.0 / weld
    vkey = {}
    verts = []

    def vid(k, p):
        i = vkey.get(k)
        if i is None:
            i = len(verts); vkey[k] = i; verts.append((p[0] - origin[0], p[1] - origin[1], p[2] - origin[2]))
        return i

    loops, origs = [], []
    for fi, f in enumerate(faces):
        K = [((round(p[0] * q), round(p[1] * q), round(p[2] * q)), p, j) for j, p in enumerate(f.loop)]
        if islands: K = [(k + (fi,), p, j) for k, p, j in K]
        # drop repeated consecutive vertices (welding can merge neighbours)
        M = []
        for kp in K:
            if not M or M[-1][0] != kp[0]: M.append(kp)
        while len(M) > 1 and M[0][0] == M[-1][0]: M.pop()
        if len(M) < 3 or len(set(k for k, _, _ in M)) != len(M):
            loops.append([]); origs.append([]); continue
        loops.append([vid(k, p) for k, p, _ in M]); origs.append([j for _, _, j in M])

    he = {}            # (a, b) -> half-edge index, for half-edges in use by a face or reserved as an opposite
    used = set()       # half-edges that belong to a face
    ev, ef, en = [], [], []
    def half(a, b):
        h = he.get((a, b))
        if h is None:
            h = len(ev); ev.extend([b, a]); ef.extend([-1, -1]); en.extend([-1, -1])
            he[(a, b)] = h; he[(b, a)] = h + 1
        return h

    face_loops = []    # per kept face: list of half-edges
    kept, kept_orig = [], []
    for fi, L in enumerate(loops):
        if len(L) < 3 or len(set(L)) != len(L):
            continue
        # non-manifold: a directed edge already used by another face -> give this face its own vertices
        if any(he.get((L[i], L[(i + 1) % len(L)])) in used for i in range(len(L))):
            L2 = []
            for i in L:
                verts.append(verts[i]); L2.append(len(verts) - 1)
            L = L2
        hs = [half(L[i], L[(i + 1) % len(L)]) for i in range(len(L))]
        fidx = len(kept)
        for i, h in enumerate(hs):
            ef[h] = fidx; en[h] = hs[(i + 1) % len(hs)]; used.add(h)
        face_loops.append(hs); kept.append(faces[fi]); kept_orig.append(origs[fi])
    nh = len(ev)
    if not kept:
        return None
    # drop vertices no kept face uses (faces skipped as degenerate, or re-vertexed as non-manifold)
    usedv = sorted(set(ev))
    if len(usedv) != len(verts):
        remap = {o: n for n, o in enumerate(usedv)}
        verts = [verts[o] for o in usedv]
        ev = [remap[v] for v in ev]
    src = [ev[h ^ 1] for h in range(nh)]
    prev = [-1] * nh
    for hs in face_loops:
        for i, h in enumerate(hs): prev[h] = hs[i - 1]
    # boundary next: rotate around the destination vertex through the faces until a boundary half-edge leaves it
    for h in range(nh):
        if ef[h] != -1: continue
        g = h ^ 1                       # leaves v = ev[h], belongs to a face
        for _ in range(4096):
            g = prev[g] ^ 1             # next half-edge leaving v (clockwise)
            if ef[g] == -1: break
        en[h] = g
    # a vertex where faces meet only at a corner (two separate fans): one vertex per fan, so every vertex is manifold
    # (Hammer otherwise "repairs" such vertices when it opens the map, and can crash doing it)
    outs = {}
    for h in range(nh): outs.setdefault(src[h], []).append(h)
    for v, hs in list(outs.items()):
        left = set(hs); first = True
        while left:
            g0 = min(left); fan = []; g = g0
            for _ in range(len(hs) + 1):
                fan.append(g); left.discard(g); g = en[g ^ 1]
                if g == g0: break
            if first: first = False; continue
            nv = len(verts); verts.append(verts[v])
            for g in fan: ev[g ^ 1] = nv
    src = [ev[h ^ 1] for h in range(nh)]
    vedge = [-1] * len(verts)
    for h in range(nh):
        s = src[h]
        if ef[h] == -1 or vedge[s] == -1: vedge[s] = h
    for i, v in enumerate(vedge):
        if v == -1: raise ValueError("unused vertex %d" % i)
    # corner data
    tex = [(0.0, 0.0)] * nh; nor = [(0.0, 0.0, 1.0)] * nh; tan = [(1.0, 0.0, 0.0, -1.0)] * nh
    fscale, fu, fv, fmat = [], [], [], []
    matlist = []
    for fidx, (f, hs, oi) in enumerate(zip(kept, face_loops, kept_orig)):
        if f.mat not in matlist: matlist.append(f.mat)
        P = [(verts[ev[h]][0] + origin[0], verts[ev[h]][1] + origin[1], verts[ev[h]][2] + origin[2]) for h in hs]
        n = newell(P)
        if f.axes:
            U, ou, su, V, ov, sv = f.axes
        else:
            U, V = default_axes(n); ou = ov = 0.0; su = sv = 0.25
        fscale.append((float(su), float(sv))); fu.append(tuple(map(float, U)) + (float(ou),)); fv.append(tuple(map(float, V)) + (float(ov),))
        fmat.append(matlist.index(f.mat))
        # the uv list is per original loop vertex; the loop starts at hs[0]'s source, so the corner at hs[i]'s destination is loop[i+1]
        for i, h in enumerate(hs):
            if f.uv:
                tex[h] = tuple(map(float, f.uv[oi[(i + 1) % len(hs)]]))
            else:
                p = P[i]
                tex[h] = ((p[0] * U[0] + p[1] * U[1] + p[2] * U[2]) / su / texsize, (p[0] * V[0] + p[1] * V[1] + p[2] * V[2]) / sv / texsize)
            nor[h] = n
            w = -1.0 if (n[1] * U[2] - n[2] * U[1]) * V[0] + (n[2] * U[0] - n[0] * U[2]) * V[1] + (n[0] * U[1] - n[1] * U[0]) * V[2] < 0 else 1.0
            tan[h] = (float(U[0]), float(U[1]), float(U[2]), w)
    md = Element("CDmePolygonMesh", "meshData")
    md.set("vertexEdgeIndices", T_INT | ARRAY, vedge); md.set("vertexDataIndices", T_INT | ARRAY, list(range(len(verts))))
    md.set("edgeVertexIndices", T_INT | ARRAY, ev); md.set("edgeOppositeIndices", T_INT | ARRAY, [h ^ 1 for h in range(nh)])
    md.set("edgeNextIndices", T_INT | ARRAY, en); md.set("edgeFaceIndices", T_INT | ARRAY, ef)
    md.set("edgeDataIndices", T_INT | ARRAY, [h // 2 for h in range(nh)]); md.set("edgeVertexDataIndices", T_INT | ARRAY, list(range(nh)))
    md.set("faceEdgeIndices", T_INT | ARRAY, [hs[0] for hs in face_loops]); md.set("faceDataIndices", T_INT | ARRAY, list(range(len(kept))))
    md.set("materials", T_STRING | ARRAY, matlist)
    md.set("vertexData", T_ELEMENT, data_array(len(verts), [stream("position:0", "position", "position", [tuple(map(float, v)) for v in verts], T_VEC3, flags=3)]))
    md.set("faceVertexData", T_ELEMENT, data_array(nh, [
        stream("texcoord:0", "texcoord", "texcoord", tex, T_VEC2), stream("normal:0", "normal", "normal", nor, T_VEC3),
        stream("tangent:0", "tangent", "tangent", tan, T_VEC4), stream("PerVertexLighting:0", "", "PerVertexLighting", [(1.0, 1.0, 1.0, 0.0)] * nh, T_VEC4, loc=1)]))
    md.set("edgeData", T_ELEMENT, data_array(nh // 2, [stream("flags:0", "flags", "flags", [0] * (nh // 2), T_INT, flags=3)]))
    nf = len(kept)
    md.set("faceData", T_ELEMENT, data_array(nf, [
        stream("textureScale:0", "textureScale", "textureScale", fscale, T_VEC2, flags=0),
        stream("textureAxisU:0", "textureAxisU", "textureAxisU", fu, T_VEC4, flags=0),
        stream("textureAxisV:0", "textureAxisV", "textureAxisV", fv, T_VEC4, flags=0),
        stream("materialindex:0", "materialindex", "materialindex", fmat, T_INT, flags=8),
        stream("flags:0", "flags", "flags", [0] * nf, T_INT, flags=3),
        stream("lightmapScaleBias:0", "lightmapScaleBias", "lightmapScaleBias", [0] * nf, T_INT, flags=1)]))
    sub = Element("CDmePolygonMeshSubdivisionData", "")
    sub.set("subdivisionLevels", T_INT | ARRAY, [0] * nh); sub.set("streams", T_ELEMENT | ARRAY, [])
    md.set("subdivisionData", T_ELEMENT, sub)
    return md


def mapmesh(md, origin, physics="default", visexclude=False, group="", castshadows=True, bakelighting=True):
    m = Element("CMapMesh", "")
    for k, t, v in [("nodeID", T_INT, nid()), ("referenceID", T_UINT64, rid()), ("children", T_ELEMENT | ARRAY, []),
                    ("variableTargetKeys", T_STRING | ARRAY, []), ("variableNames", T_STRING | ARRAY, []),
                    ("cubeMapName", T_STRING, ""), ("lightGroup", T_STRING, ""), ("visexclude", T_BOOL, int(visexclude)), ("disablemerging", T_BOOL, 0),
                    ("renderwithdynamic", T_BOOL, 0), ("disableHeightDisplacement", T_BOOL, 0), ("fademindist", T_FLOAT, -1.0), ("fademaxdist", T_FLOAT, 0.0),
                    ("bakelighting", T_BOOL, int(bakelighting)), ("precomputelightprobes", T_BOOL, 1), ("renderToCubemaps", T_BOOL, 1), ("emissiveLightingEnabled", T_BOOL, 1),
                    ("emissiveLightingBoost", T_FLOAT, 1.0), ("disableShadows", T_INT, 0 if castshadows else 1), ("lightingDummy", T_BOOL, 0), ("smoothingAngle", T_FLOAT, 40.0),
                    ("tintColor", T_COLOR, (255, 255, 255, 255)), ("renderAmt", T_INT, 255), ("physicsType", T_STRING, physics), ("physicsGroup", T_STRING, ""),
                    ("physicsInteractsAs", T_STRING, ""), ("physicsInteractsWith", T_STRING, ""), ("physicsInteractsExclude", T_STRING, ""),
                    ("meshData", T_ELEMENT, md), ("physicsSimplificationOverride", T_BOOL, 0), ("physicsSimplificationError", T_FLOAT, 0.0),
                    ("origin", T_VEC3, tuple(map(float, origin))), ("angles", T_QANGLE, (0.0, 0.0, 0.0)), ("scales", T_VEC3, (1.0, 1.0, 1.0)),
                    ("transformLocked", T_BOOL, 0), ("force_hidden", T_BOOL, 0), ("editorOnly", T_BOOL, 0)]:
        m.set(k, t, v)
    if group:
        m.set("customVisGroup", T_STRING, group)
    return m


def box_faces(x0, y0, z0, x1, y1, z1, mat):
    """closed box, faces pointing out"""
    c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    loops = [(4, 5, 6, 7), (0, 3, 2, 1), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (3, 0, 4, 7)]
    return [Face([c[i] for i in L], mat) for L in loops]


def entity(cls, origin, angles=(0, 0, 0), props=None, scales=(1, 1, 1), kids=(), conns=(), group=""):
    e = Element("CMapEntity", "")
    e.set("nodeID", T_INT, nid()); e.set("referenceID", T_UINT64, rid())
    e.set("children", T_ELEMENT | ARRAY, list(kids))
    e.set("variableTargetKeys", T_STRING | ARRAY, []); e.set("variableNames", T_STRING | ARRAY, [])
    plug = Element("DmePlugList", "")
    plug.set("names", T_STRING | ARRAY, []); plug.set("dataTypes", T_INT | ARRAY, []); plug.set("plugTypes", T_INT | ARRAY, []); plug.set("descriptions", T_STRING | ARRAY, [])
    e.set("relayPlugData", T_ELEMENT, plug)
    cl = []
    for (out, target, inp, param, delay) in conns:
        c = Element("DmeConnectionData", "")
        c.set("outputName", T_STRING, out); c.set("targetType", T_INT, 7); c.set("targetName", T_STRING, target)
        c.set("inputName", T_STRING, inp); c.set("overrideParam", T_STRING, param); c.set("delay", T_FLOAT, float(delay)); c.set("timesToFire", T_INT, -1)
        cl.append(c)
    e.set("connectionsData", T_ELEMENT | ARRAY, cl)
    ep = Element("EditGameClassProps", "")
    ep.set("classname", T_STRING, cls)
    for k, v in (props or {}).items(): ep.set(k.replace("__", "."), T_STRING, str(v))
    e.set("entity_properties", T_ELEMENT, ep)
    e.set("hitNormal", T_VEC3, (0.0, 0.0, 1.0)); e.set("isProceduralEntity", T_BOOL, 0)
    e.set("origin", T_VEC3, tuple(float(v) for v in origin)); e.set("angles", T_QANGLE, tuple(float(v) for v in angles))
    e.set("scales", T_VEC3, tuple(float(v) for v in scales))
    e.set("transformLocked", T_BOOL, 0); e.set("force_hidden", T_BOOL, 0); e.set("editorOnly", T_BOOL, 0)
    if group:
        e.set("customVisGroup", T_STRING, group)
    return e


def check_mesh(md):
    """structural self-check, mirrors what Valve's files satisfy"""
    ev, eo, en, ef = md["edgeVertexIndices"], md["edgeOppositeIndices"], md["edgeNextIndices"], md["edgeFaceIndices"]
    ve = md["vertexEdgeIndices"]
    nh = len(ev)
    src = [ev[eo[h]] for h in range(nh)]
    assert all(eo[eo[h]] == h for h in range(nh))
    assert all(src[en[h]] == ev[h] for h in range(nh)), "next must leave the destination"
    assert all(ef[en[h]] == ef[h] for h in range(nh)), "next stays on the same face / boundary"
    assert all(src[ve[v]] == v for v in range(len(ve)))
    # every face loop closes
    for f, h0 in enumerate(md["faceEdgeIndices"]):
        h = h0
        for _ in range(1000):
            assert ef[h] == f
            h = en[h]
            if h == h0: break
        else:
            raise AssertionError("face loop doesn't close")
    return True
