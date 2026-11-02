"""Helpers for writing Hammer map nodes (entities, meshes) into a binary DMX vmap. See vmap.py / vmap_env.py."""
import os, random
from PIL import Image
from dmx import Element, T_ELEMENT, T_INT, T_FLOAT, T_BOOL, T_STRING, T_COLOR, T_VEC2, T_VEC3, T_VEC4, T_QANGLE, T_UINT64, ARRAY

# ---------------------------------------------------------------- node ids
def walk(e, seen):
    if e is None or id(e) in seen: return
    seen.add(id(e)); yield e
    for a in e.attrs:
        if a[1] == T_ELEMENT: yield from walk(a[2], seen)
        elif a[1] == T_ELEMENT + ARRAY:
            for x in a[2]: yield from walk(x, seen)
next_node = [1]
rng = random.Random(1337)
OUT = ''
new_children = []
counts = {}
materials_used = []

def init(d, out):
    global OUT
    OUT = out
    root = d.root
    next_node[0] = max([e.get('nodeID', 0) for e in walk(root, set()) if isinstance(e.get('nodeID', 0), int)] + [1]) + 1
    new_children.clear(); counts.clear(); materials_used.clear()
def node_id():
    v = next_node[0]; next_node[0] += 1; return v

def transform_pin():
    p = Element('DmElement', 'transformPin')
    p.attrs = [['referenceName', T_STRING, ''], ['targetReferenceID', T_UINT64, 0],
               ['offsetOrigin', T_VEC3, (0.0, 0.0, 0.0)], ['offsetAngles', T_QANGLE, (0.0, 0.0, 0.0)],
               ['pinAngles', T_BOOL, 1], ['twoWay', T_BOOL, 0]]
    return p

def node_head(type_):
    e = Element(type_, '')
    e.attrs = [['nodeID', T_INT, node_id()], ['referenceID', T_UINT64, rng.getrandbits(64)],
               ['children', T_ELEMENT + ARRAY, []], ['variableTargetKeys', T_STRING + ARRAY, []],
               ['variableNames', T_STRING + ARRAY, []]]
    return e

def node_tail(e, origin, angles=(0, 0, 0), group=''):
    e.attrs += [['origin', T_VEC3, tuple(float(x) for x in origin)], ['angles', T_QANGLE, tuple(float(x) for x in angles)],
                ['scales', T_VEC3, (1.0, 1.0, 1.0)], ['transformLocked', T_BOOL, 0], ['transformPin', T_ELEMENT, transform_pin()],
                ['force_hidden', T_BOOL, 0], ['editorOnly', T_BOOL, 0], ['customVisGroup', T_STRING, group],
                ['randomSeed', T_INT, rng.randrange(1 << 30)]]

# ---------------------------------------------------------------- entities
def ent(classname, origin, angles=(0, 0, 0), group='', **keys):
    e = node_head('CMapEntity')
    plugs = Element('DmePlugList', '')
    plugs.attrs = [['names', T_STRING + ARRAY, []], ['dataTypes', T_INT + ARRAY, []],
                   ['plugTypes', T_INT + ARRAY, []], ['descriptions', T_STRING + ARRAY, []]]
    props_ = Element('EditGameClassProps', '')
    props_.attrs = [['classname', T_STRING, classname]] + [[k, T_STRING, str(v)] for k, v in keys.items()]
    e.attrs += [['relayPlugData', T_ELEMENT, plugs], ['connectionsData', T_ELEMENT + ARRAY, []],
                ['entity_properties', T_ELEMENT, props_], ['hitNormal', T_VEC3, (0.0, 0.0, 1.0)],
                ['isProceduralEntity', T_BOOL, 0]]
    node_tail(e, origin, angles, group)
    new_children.append(e)
    counts[classname] = counts.get(classname, 0) + 1
    return e

# ---------------------------------------------------------------- meshes (closed boxes seen from inside)
def tex_size(mat):
    try:
        return Image.open(os.path.join(OUT, 'materials', mat.replace('.vmat', '_color.png').split('materials/', 1)[1])).size
    except Exception:
        return (512, 512)

def stream(name, typ, data, flags):
    s = Element('CDmePolygonMeshDataStream', name + ':0')
    s.attrs = [['standardAttributeName', T_STRING, name], ['semanticName', T_STRING, name], ['semanticIndex', T_INT, 0],
               ['vertexBufferLocation', T_INT, 0], ['dataStateFlags', T_INT, flags], ['subdivisionBinding', T_ELEMENT, None],
               ['data', typ + ARRAY, data]]
    return s

def data_array(size, streams):
    a = Element('CDmePolygonMeshDataArray', '')
    a.attrs = [['size', T_INT, size], ['streams', T_ELEMENT + ARRAY, streams]]
    return a

def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def norm(a):
    l = dot(a, a) ** 0.5; return (a[0] / l, a[1] / l, a[2] / l)

def polymesh(verts, faces, face_mats, scale=0.25):
    """verts: list of xyz; faces: list of vertex index loops, counter-clockwise seen from the visible side."""
    mats = sorted(set(face_mats))
    for m in mats:
        if m not in materials_used: materials_used.append(m)
    he_dest, he_face, he_next, opp = [], [], [], []
    key = {}
    face_first = []
    for f, loop in enumerate(faces):
        first = len(he_dest); n = len(loop)
        for k in range(n):
            a, b = loop[k], loop[(k + 1) % n]
            idx = len(he_dest)
            he_dest.append(b); he_face.append(f); he_next.append(first + (k + 1) % n)
            key[(a, b)] = idx
        face_first.append(first)
    nhe = len(he_dest)
    # pair half-edges into edges (closed meshes only)
    order = []; done = set()
    for (a, b), i in sorted(key.items(), key=lambda kv: kv[1]):
        if i in done: continue
        j = key[(b, a)]
        order += [i, j]; done |= {i, j}
    remap = {old: new for new, old in enumerate(order)}
    E_dest = [0] * nhe; E_face = [0] * nhe; E_next = [0] * nhe
    for old in range(nhe):
        new = remap[old]
        E_dest[new] = he_dest[old]; E_face[new] = he_face[old]; E_next[new] = remap[he_next[old]]
    E_opp = [i ^ 1 for i in range(nhe)]
    v_edge = [0] * len(verts)
    for i in range(nhe):
        v_edge[E_dest[E_opp[i]]] = i     # half-edge i leaves the vertex its opposite points to
    f_edge = [remap[face_first[f]] for f in range(len(faces))]
    # per-face texture axes (world aligned, like Hammer's defaults)
    fnorm, fu, fv = [], [], []
    for loop in faces:
        p0, p1, p2 = verts[loop[0]], verts[loop[1]], verts[loop[2]]
        nrm = norm(cross(sub(p1, p0), sub(p2, p0)))
        ax = max(range(3), key=lambda k: abs(nrm[k]))
        if ax == 2: u, v = (1.0, 0.0, 0.0), (0.0, -1.0, 0.0)
        elif ax == 0: u, v = (0.0, 1.0, 0.0), (0.0, 0.0, -1.0)
        else: u, v = (1.0, 0.0, 0.0), (0.0, 0.0, -1.0)
        fnorm.append(nrm); fu.append(u); fv.append(v)
    tex, nrm_, tan = [], [], []
    for i in range(nhe):
        f = E_face[i]; p = verts[E_dest[i]]
        tw, th = tex_size(face_mats[f])
        tex.append((dot(p, fu[f]) / (tw * scale), dot(p, fv[f]) / (th * scale)))
        nrm_.append(fnorm[f])
        w = -1.0 if dot(cross(fnorm[f], fu[f]), fv[f]) < 0 else 1.0
        tan.append(fu[f] + (w,))
    m = Element('CDmePolygonMesh', 'meshData')
    nf = len(faces)
    m.attrs = [
        ['vertexEdgeIndices', T_INT + ARRAY, v_edge],
        ['vertexDataIndices', T_INT + ARRAY, list(range(len(verts)))],
        ['edgeVertexIndices', T_INT + ARRAY, E_dest],
        ['edgeOppositeIndices', T_INT + ARRAY, E_opp],
        ['edgeNextIndices', T_INT + ARRAY, E_next],
        ['edgeFaceIndices', T_INT + ARRAY, E_face],
        ['edgeDataIndices', T_INT + ARRAY, [i >> 1 for i in range(nhe)]],
        ['edgeVertexDataIndices', T_INT + ARRAY, list(range(nhe))],
        ['faceEdgeIndices', T_INT + ARRAY, f_edge],
        ['faceDataIndices', T_INT + ARRAY, list(range(nf))],
        ['materials', T_STRING + ARRAY, mats],
        ['vertexData', T_ELEMENT, data_array(len(verts), [stream('position', T_VEC3, [tuple(map(float, v)) for v in verts], 3)])],
        ['faceVertexData', T_ELEMENT, data_array(nhe, [stream('texcoord', T_VEC2, tex, 1), stream('normal', T_VEC3, nrm_, 1),
                                                      stream('tangent', T_VEC4, tan, 1)])],
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

def mesh_node(mesh, group='', attach=True):
    e = node_head('CMapMesh')
    e.attrs.append(['meshData', T_ELEMENT, mesh])
    node_tail(e, (0, 0, 0))
    e.attr('customVisGroup')[2] = group
    e.attrs += [['disableShadows', T_INT, 1], ['bakelighting', T_BOOL, 0], ['cubeMapName', T_STRING, ''],
                ['emissiveLightingEnabled', T_BOOL, 0], ['emissiveLightingBoost', T_FLOAT, 1.0], ['lightingDummy', T_BOOL, 0],
                ['bakeLightDoubleSided', T_BOOL, 0], ['steamaudioGeometryMode', T_INT, 0], ['visexclude', T_BOOL, 0],
                ['disablemerging', T_BOOL, 0], ['renderwithdynamic', T_BOOL, 0], ['renderToCubemaps', T_BOOL, 0],
                ['keep_vertices', T_BOOL, 0], ['fademindist', T_FLOAT, -1.0], ['fademaxdist', T_FLOAT, 0.0],
                ['disableHeightDisplacement', T_BOOL, 0], ['smoothingAngle', T_FLOAT, 40.0],
                ['tintColor', T_COLOR, (255, 255, 255, 255)], ['renderAmt', T_INT, 255], ['physicsType', T_STRING, 'default'],
                ['physicsCollisionProperty', T_STRING, ''], ['physicsGroup', T_STRING, ''], ['physicsInteractsAs', T_STRING, ''],
                ['physicsInteractsWith', T_STRING, ''], ['physicsInteractsExclude', T_STRING, ''],
                ['physicsIncludedDetailLayers', T_ELEMENT + ARRAY, []], ['physicsMissingDetailLayers', T_ELEMENT + ARRAY, []],
                ['physicsSimplificationOverride', T_BOOL, 0], ['physicsSimplificationError', T_FLOAT, 0.0]]
    if attach: new_children.append(e)
    return e



def box_faces(x0, y0, z0, x1, y1, z1, inward=True):
    """8 corners and 6 quads of an axis-aligned box; inward=True faces the inside (a room / dome)."""
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [[0, 1, 2, 3], [4, 7, 6, 5], [0, 4, 5, 1], [2, 6, 7, 3], [1, 5, 6, 2], [3, 7, 4, 0]]
    if not inward: faces = [f[::-1] for f in faces]
    return v, faces
