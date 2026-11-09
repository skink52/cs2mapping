"""Hammer CMapMesh writer supporting open meshes (boundary half-edges with face -1, as Valve's own maps use)."""
import numpy as np
from dmx import Element, T_ELEMENT, T_INT, T_FLOAT, T_BOOL, T_STRING, T_COLOR, T_VEC2, T_VEC3, T_VEC4, T_UINT64, ARRAY
import vmaplib
from vmaplib import stream, data_array, node_head, node_tail

TEX_SIZE = {}   # material -> (w, h) pixels; default 1024


def polymesh_open(verts, faces, face_mats, scale=0.25, tex_axes=None, paint=None, tint=None):
    """verts (n,3); faces: list of index loops CCW seen from the visible side; open boundaries allowed (manifold)."""
    verts = np.asarray(verts, float)
    mats = sorted(set(face_mats))
    for m in mats:
        if m not in vmaplib.materials_used: vmaplib.materials_used.append(m)
    he_from, he_to, he_face = [], [], []
    key = {}
    face_first = []
    for f, loop in enumerate(faces):
        face_first.append(len(he_to))
        n = len(loop)
        for k in range(n):
            a, b = loop[k], loop[(k + 1) % n]
            if (a, b) in key: raise ValueError('non-manifold edge %s' % ((a, b),))
            key[(a, b)] = len(he_to)
            he_from.append(a); he_to.append(b); he_face.append(f)
    nfh = len(he_to)
    # next within faces
    nxt = [0] * nfh
    for f, loop in enumerate(faces):
        s = face_first[f]; n = len(loop)
        for k in range(n): nxt[s + k] = s + (k + 1) % n
    # boundary half-edges
    for (a, b), i in list(key.items()):
        if (b, a) not in key:
            key[(b, a)] = len(he_to)
            he_from.append(b); he_to.append(a); he_face.append(-1); nxt.append(-1)
    nhe = len(he_to)
    # boundary next: the boundary half-edge leaving the vertex this one points to
    out_b = {}
    for i in range(nfh, nhe): out_b[he_from[i]] = i
    for i in range(nfh, nhe):
        nxt[i] = out_b.get(he_to[i], i)
    # pair up: order so opposite = i ^ 1
    order = []; done = set()
    for i in range(nhe):
        if i in done: continue
        j = key[(he_to[i], he_from[i])]
        order += [i, j]; done |= {i, j}
    remap = np.empty(nhe, np.int64); remap[np.array(order)] = np.arange(nhe)
    E_dest = np.empty(nhe, np.int64); E_face = np.empty(nhe, np.int64); E_next = np.empty(nhe, np.int64)
    old = np.array(order)
    E_dest[:] = np.array(he_to)[old]; E_face[:] = np.array(he_face)[old]; E_next[:] = remap[np.array(nxt)[old]]
    E_opp = np.arange(nhe) ^ 1
    v_edge = np.zeros(len(verts), np.int64)
    # prefer the outgoing boundary half-edge for boundary vertices
    src = E_dest[E_opp]
    for i in range(nhe):
        v_edge[src[i]] = i
    for i in range(nhe):
        if E_face[i] < 0: v_edge[src[i]] = i
    f_edge = [int(remap[face_first[f]]) for f in range(len(faces))]
    # per-face normals (Newell) and world-aligned axes
    fn, fu, fv = [], [], []
    for loop in faces:
        p = verts[loop]
        q = np.roll(p, -1, axis=0)
        nrm = np.array([np.sum((p[:, 1] - q[:, 1]) * (p[:, 2] + q[:, 2])), np.sum((p[:, 2] - q[:, 2]) * (p[:, 0] + q[:, 0])),
                        np.sum((p[:, 0] - q[:, 0]) * (p[:, 1] + q[:, 1]))])
        l = np.linalg.norm(nrm); nrm = nrm / l if l > 0 else np.array([0, 0, 1.0])
        ax = int(np.argmax(np.abs(nrm)))
        if ax == 2: u, v = (1.0, 0.0, 0.0), (0.0, -1.0, 0.0)
        elif ax == 0: u, v = (0.0, 1.0, 0.0), (0.0, 0.0, -1.0)
        else: u, v = (1.0, 0.0, 0.0), (0.0, 0.0, -1.0)
        fn.append(tuple(nrm)); fu.append(u); fv.append(v)
    tex = np.zeros((nhe, 2)); nrm_ = np.zeros((nhe, 3)); tan = np.zeros((nhe, 4))
    for i in range(nhe):
        f = E_face[i]
        if f < 0: continue
        p = verts[E_dest[i]]
        tw, th = TEX_SIZE.get(face_mats[f], (1024, 1024))
        tex[i] = (np.dot(p, fu[f]) / (tw * scale), np.dot(p, fv[f]) / (th * scale))
        nrm_[i] = fn[f]
        w = -1.0 if np.dot(np.cross(fn[f], fu[f]), fv[f]) < 0 else 1.0
        tan[i] = fu[f] + (w,)
    nf = len(faces)
    m = Element('CDmePolygonMesh', 'meshData')
    m.attrs = [
        ['vertexEdgeIndices', T_INT + ARRAY, v_edge.tolist()],
        ['vertexDataIndices', T_INT + ARRAY, list(range(len(verts)))],
        ['edgeVertexIndices', T_INT + ARRAY, E_dest.tolist()],
        ['edgeOppositeIndices', T_INT + ARRAY, E_opp.tolist()],
        ['edgeNextIndices', T_INT + ARRAY, E_next.tolist()],
        ['edgeFaceIndices', T_INT + ARRAY, E_face.tolist()],
        ['edgeDataIndices', T_INT + ARRAY, (np.arange(nhe) >> 1).tolist()],
        ['edgeVertexDataIndices', T_INT + ARRAY, list(range(nhe))],
        ['faceEdgeIndices', T_INT + ARRAY, f_edge],
        ['faceDataIndices', T_INT + ARRAY, list(range(nf))],
        ['materials', T_STRING + ARRAY, mats],
        ['vertexData', T_ELEMENT, data_array(len(verts), [stream('position', T_VEC3, [tuple(map(float, v)) for v in verts], 3)])],
        ['faceVertexData', T_ELEMENT, data_array(nhe, [stream('texcoord', T_VEC2, [tuple(t) for t in tex], 1),
                                                      stream('normal', T_VEC3, [tuple(t) for t in nrm_], 1),
                                                      stream('tangent', T_VEC4, [tuple(t) for t in tan], 1)] + paint_streams(E_dest, E_face, nhe, paint, tint))],
        ['edgeData', T_ELEMENT, data_array(nhe // 2, [stream('flags', T_INT, [0] * (nhe // 2), 3)])],
        ['faceData', T_ELEMENT, data_array(nf, [
            stream('textureScale', T_VEC2, [(scale, scale)] * nf, 0),
            stream('textureAxisU', T_VEC4, [fu[f] + (0.0,) for f in range(nf)], 0),
            stream('textureAxisV', T_VEC4, [fv[f] + (0.0,) for f in range(nf)], 0),
            stream('materialindex', T_INT, [mats.index(face_mats[f]) for f in range(nf)], 8),
            stream('flags', T_INT, [0] * nf, 3),
            stream('lightmapScaleBias', T_INT, [0] * nf, 1)])],
    ]
    sd = Element('CDmePolygonMeshSubdivisionData', '')
    sd.attrs = [['subdivisionLevels', T_INT + ARRAY, [0] * nhe], ['streams', T_ELEMENT + ARRAY, []]]
    m.attrs.append(['subdivisionData', T_ELEMENT, sd])
    return m


def paint_stream(name, data):
    st = Element('CDmePolygonMeshDataStream', name + ':0')
    st.attrs = [['standardAttributeName', T_STRING, ''], ['semanticName', T_STRING, name], ['semanticIndex', T_INT, 0],
                ['vertexBufferLocation', T_INT, 1], ['dataStateFlags', T_INT, 1], ['subdivisionBinding', T_ELEMENT, None],
                ['data', T_VEC4 + ARRAY, data]]
    return st


def paint_streams(E_dest, E_face, nhe, paint, tint):
    """Hammer's vertex paint (as Valve's own maps store it): per face-vertex VertexPaintTintColor + VertexPaintBlendParams"""
    out = []
    if paint is None and tint is None: return out
    face = np.asarray(E_face) >= 0
    dest = np.asarray(E_dest)
    if tint is None: tint = np.ones((int(dest.max()) + 1, 4))
    t = np.zeros((nhe, 4)); t[face] = np.asarray(tint)[dest[face]]
    out.append(paint_stream('VertexPaintTintColor', [tuple(map(float, v)) for v in t]))
    if paint is not None:
        p = np.zeros((nhe, 4)); p[face] = np.asarray(paint)[dest[face]]
        out.append(paint_stream('VertexPaintBlendParams', [tuple(map(float, v)) for v in p]))
    return out


def mesh_node(mesh, group='', attach=True, bake=True, shadows=True, visexclude=False, smoothing=40.0, physics='default'):
    e = node_head('CMapMesh')
    e.attrs.append(['meshData', T_ELEMENT, mesh])
    node_tail(e, (0, 0, 0))
    e.attr('customVisGroup')[2] = group
    e.attrs += [['disableShadows', T_INT, 0 if shadows else 1], ['bakelighting', T_BOOL, 1 if bake else 0], ['cubeMapName', T_STRING, ''],
                ['emissiveLightingEnabled', T_BOOL, 0], ['emissiveLightingBoost', T_FLOAT, 1.0], ['lightingDummy', T_BOOL, 0],
                ['visexclude', T_BOOL, 1 if visexclude else 0], ['disablemerging', T_BOOL, 0], ['renderwithdynamic', T_BOOL, 0],
                ['renderToCubemaps', T_BOOL, 1], ['keep_vertices', T_BOOL, 0], ['fademindist', T_FLOAT, -1.0], ['fademaxdist', T_FLOAT, 0.0],
                ['disableHeightDisplacement', T_BOOL, 0], ['smoothingAngle', T_FLOAT, smoothing],
                ['tintColor', T_COLOR, (255, 255, 255, 255)], ['renderAmt', T_INT, 255], ['physicsType', T_STRING, physics],
                ['physicsCollisionProperty', T_STRING, ''], ['physicsGroup', T_STRING, ''], ['physicsInteractsAs', T_STRING, ''],
                ['physicsInteractsWith', T_STRING, ''], ['physicsInteractsExclude', T_STRING, ''],
                ['physicsSimplificationOverride', T_BOOL, 0], ['physicsSimplificationError', T_FLOAT, 0.0]]
    if attach: vmaplib.new_children.append(e)
    return e


def box_mesh(x0, y0, z0, x1, y1, z1, mats, inward=False):
    """closed box; mats: single material or dict(top, bottom, side)"""
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [2, 3, 7, 6], [1, 2, 6, 5], [3, 0, 4, 7]]
    if inward: faces = [f[::-1] for f in faces]
    if isinstance(mats, str): fm = [mats] * 6
    else: fm = [mats.get('bottom', mats['side']), mats.get('top', mats['side'])] + [mats['side']] * 4
    return polymesh_open(v, faces, fm, scale=0.25)


def oriented_box_mesh(center, half, R, mats):
    c = np.asarray(center, float); h = np.asarray(half, float); R = np.asarray(R, float)
    v = []
    for z in (-1, 1):
        for (x, y) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            v.append(c + R @ (np.array([x, y, z]) * h))
    faces = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [2, 3, 7, 6], [1, 2, 6, 5], [3, 0, 4, 7]]
    fm = [mats] * 6 if isinstance(mats, str) else mats
    return polymesh_open(v, faces, fm, scale=0.25)


def grid_sheet(X, Y, Z, face_mat, valid=None, vert_attr=None):
    """heightfield sheet over a regular grid (nx+1, ny+1); valid: (nx, ny) bool cell mask; face_mat(i,j)->material"""
    nx, ny = X.shape[0] - 1, X.shape[1] - 1
    if valid is None: valid = np.ones((nx, ny), bool)
    used = np.zeros((nx + 1, ny + 1), bool)
    ci, cj = np.nonzero(valid)
    for di in (0, 1):
        for dj in (0, 1): used[ci + di, cj + dj] = True
    idx = -np.ones((nx + 1, ny + 1), np.int64)
    idx[used] = np.arange(used.sum())
    verts = np.stack([X[used], Y[used], Z[used]], 1)
    extra = None
    if vert_attr is not None: extra = [a[used] for a in vert_attr]
    faces = []; mats = []
    for i, j in zip(ci, cj):
        a, b, c, d = idx[i, j], idx[i + 1, j], idx[i + 1, j + 1], idx[i, j + 1]
        faces.append([a, b, c, d]); mats.append(face_mat(i, j))
    if vert_attr is not None: return verts, faces, mats, extra
    return verts, faces, mats
