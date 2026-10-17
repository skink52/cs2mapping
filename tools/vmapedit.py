"""Edit Hammer 5 .vmap files (binary DMX) without Hammer."""
import os, random, math, copy
import dmx
from dmx import T_ELEM, T_INT, T_FLOAT, T_BOOL, T_STR, T_V3, T_QANG, T_U64, ARR

def guid(): return bytes(random.getrandbits(8) for _ in range(16))

class Map:
    def __init__(s, path=None, data=None):
        s.path = path
        raw = data if data is not None else open(path, 'rb').read()
        if b'encoding keyvalues2' in raw[:80]:
            import kv2; s.doc = kv2.loads(raw)
        else:
            s.doc = dmx.loads(raw)
        s.E = s.doc.elements
        s.root = next(i for i, e in enumerate(s.E) if e['type'] == b'CMapRootElement')
        s.world = dmx.get(s.E[s.root], b'world')

    # ---------- basic element access ----------
    def g(s, i, k, d=None): return dmx.get(s.E[i], k, d)
    def type(s, i): return s.E[i]['type']
    def children(s, i): return s.g(i, b'children') or []
    def walk(s, i=None, parent=None):
        """yield (node, parent) for every node under i (default world), depth first"""
        i = s.world if i is None else i
        for c in s.children(i):
            yield c, i
            yield from s.walk(c, i)
    def entities(s):
        return [n for n, _ in s.walk() if s.type(n) == b'CMapEntity']
    def parent_of(s):
        return {n: p for n, p in s.walk()}

    # ---------- entity properties ----------
    def props(s, i): return s.E[s.g(i, b'entity_properties')]
    def P(s, i, k, d=None):
        v = dmx.get(s.props(i), k.encode() if isinstance(k, str) else k)
        return d if v is None else v.decode('utf-8', 'replace')
    def setp(s, i, k, v):
        k = k.encode() if isinstance(k, str) else k
        v = v.encode() if isinstance(v, str) else v
        dmx.set_(s.props(i), k, T_STR, v)
    def delp(s, i, k): dmx.delete(s.props(i), k.encode() if isinstance(k, str) else k)
    def cls(s, i): return s.P(i, 'classname', '')
    def name(s, i): return s.P(i, 'targetname', '')
    def origin(s, i): return list(s.g(i, b'origin', [0, 0, 0]))
    def by_class(s, *c): return [e for e in s.entities() if s.cls(e) in c]

    # ---------- connections ----------
    def conns(s, i): return [s.E[c] for c in s.g(i, b'connectionsData') or []]
    def conn_tuple(s, c):
        return (dmx.get(c, b'outputName').decode(), dmx.get(c, b'targetName').decode(), dmx.get(c, b'inputName').decode(),
                dmx.get(c, b'overrideParam').decode(), round(dmx.get(c, b'delay'), 3), dmx.get(c, b'timesToFire'))
    def add_conn(s, i, out, target, inp, param='', delay=0.0, times=-1):
        c = s.new_el(b'DmeConnectionData', [
            [b'outputName', T_STR, out.encode()], [b'targetType', T_INT, 7], [b'targetName', T_STR, target.encode()],
            [b'inputName', T_STR, inp.encode()], [b'overrideParam', T_STR, param.encode()],
            [b'delay', T_FLOAT, float(delay)], [b'timesToFire', T_INT, int(times)]])
        dmx.geta(s.E[i], b'connectionsData')[2].append(c)
        return c
    def all_conns(s):
        for e in s.entities():
            for c in s.conns(e): yield e, c

    # ---------- creation ----------
    def new_el(s, typ, attrs, name=b''):
        s.E.append({'type': typ, 'name': name, 'guid': guid(), 'attrs': attrs}); return len(s.E) - 1
    def next_node_id(s):
        m = 0
        for e in s.E:
            v = dmx.get(e, b'nodeID')
            if isinstance(v, int) and v > m: m = v
        return m + 1
    def new_entity(s, classname, origin, props, angles=(0, 0, 0), parent=None):
        pin = s.new_el(b'DmElement', [[b'referenceName', T_STR, b''], [b'targetReferenceID', T_U64, 0], [b'offsetOrigin', T_V3, [0.0, 0.0, 0.0]],
                                     [b'offsetAngles', T_QANG, [0.0, 0.0, 0.0]], [b'pinAngles', T_BOOL, True], [b'twoWay', T_BOOL, False]])
        plug = s.new_el(b'DmePlugList', [[b'names', 37, []], [b'dataTypes', 34, []], [b'plugTypes', 34, []], [b'descriptions', 37, []]])
        pr = [[b'classname', T_STR, classname.encode()]] + [[k.encode(), T_STR, str(v).encode()] for k, v in props.items()]
        pe = s.new_el(b'EditGameClassProps', pr)
        e = s.new_el(b'CMapEntity', [
            [b'nodeID', T_INT, s.next_node_id()], [b'referenceID', T_U64, random.getrandbits(63)], [b'children', ARR + T_ELEM, []],
            [b'variableTargetKeys', ARR + T_STR, []], [b'variableNames', ARR + T_STR, []], [b'relayPlugData', T_ELEM, plug],
            [b'connectionsData', ARR + T_ELEM, []], [b'entity_properties', T_ELEM, pe], [b'hitNormal', T_V3, [0.0, 0.0, 1.0]],
            [b'isProceduralEntity', T_BOOL, False], [b'origin', T_V3, [float(x) for x in origin]], [b'angles', T_QANG, [float(x) for x in angles]],
            [b'scales', T_V3, [1.0, 1.0, 1.0]], [b'transformLocked', T_BOOL, False], [b'transformPin', T_ELEM, pin],
            [b'force_hidden', T_BOOL, False], [b'editorOnly', T_BOOL, False], [b'customVisGroup', T_STR, b''],
            [b'randomSeed', T_INT, random.randint(1, 2**31 - 1)]])
        dmx.geta(s.E[parent if parent is not None else s.world], b'children')[2].append(e)
        return e
    def remove_node(s, i):
        for n, p in list(s.walk()):
            if n == i:
                a = dmx.geta(s.E[p], b'children'); a[2] = [x for x in a[2] if x != i]; return True
        return False

    # ---------- copying between maps ----------
    def import_subtree(s, other, i, memo, node_id):
        """deep-copy element i (and everything it references) from Map `other` into this map"""
        if i in memo: return memo[i]
        src = other.E[i]
        if src['type'] in (b'CMapRootElement', b'CMapWorld'):
            raise ValueError('refusing to copy root/world')
        j = len(s.E); memo[i] = j
        s.E.append({'type': src['type'], 'name': src['name'], 'guid': guid(), 'attrs': []})
        attrs = []
        for name, t, v in src['attrs']:
            if t == T_ELEM and isinstance(v, int) and v >= 0: v = s.import_subtree(other, v, memo, node_id)
            elif t == ARR + T_ELEM: v = [s.import_subtree(other, x, memo, node_id) if isinstance(x, int) and x >= 0 else x for x in v]
            elif name == b'nodeID' and t == T_INT: v = node_id[0]; node_id[0] += 1
            elif isinstance(v, list): v = list(v)
            attrs.append([name, t, v])
        s.E[j]['attrs'] = attrs
        return j

    # ---------- bounds ----------
    def mesh_points(s, mesh_node):
        """world-space vertex positions of a CMapMesh (mesh nodes keep local verts + node origin)"""
        md = s.g(mesh_node, b'meshData')
        if md is None: return []
        vdata = s.g(md, b'vertexData')
        o = s.g(mesh_node, b'origin', [0, 0, 0]); ang = s.g(mesh_node, b'angles', [0, 0, 0]); sc = s.g(mesh_node, b'scales', [1, 1, 1])
        pts = []
        for st in s.g(vdata, b'streams') or []:
            if s.E[st]['name'].startswith(b'position'):
                for p in s.g(st, b'data'):
                    pts.append(xform([p[0] * sc[0], p[1] * sc[1], p[2] * sc[2]], o, ang))
        return pts
    def bounds(s, node):
        pts = []
        stack = [node]
        while stack:
            n = stack.pop()
            if s.type(n) == b'CMapMesh': pts += s.mesh_points(n)
            stack += s.children(n)
        if not pts: return None
        return [min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)]

    # ---------- save ----------
    def prune(s):
        """drop elements no longer reachable from the root / prefix; returns how many were removed"""
        keep = set(); stack = [s.root]
        stack += [i for i, e in enumerate(s.E) if e['type'] == b'$prefix_element$']
        while stack:
            i = stack.pop()
            if i in keep: continue
            keep.add(i)
            for _, t, v in s.E[i]['attrs']:
                if t == T_ELEM and isinstance(v, int) and v >= 0: stack.append(v)
                elif t == ARR + T_ELEM: stack += [x for x in v if isinstance(x, int) and x >= 0]
        order = [i for i in range(len(s.E)) if i in keep]
        remap = {o: n for n, o in enumerate(order)}
        newE = []
        for i in order:
            e = s.E[i]; attrs = []
            for name, t, v in e['attrs']:
                if t == T_ELEM and isinstance(v, int) and v >= 0: v = remap[v]
                elif t == ARR + T_ELEM: v = [remap[x] if isinstance(x, int) and x >= 0 else x for x in v]
                attrs.append([name, t, v])
            newE.append({**e, 'attrs': attrs})
        removed = len(s.E) - len(newE)
        s.doc.elements = s.E = newE; s.root = remap[s.root]; s.world = remap[s.world]
        return removed
    def dumps(s):
        out = dmx.dumps(s.doc); dmx.loads(out); return out
    def save(s, path):
        out = s.dumps(); os.makedirs(os.path.dirname(path), exist_ok=True); open(path, 'wb').write(out); return len(out)

# ---------- math ----------
def rot_matrix(ang):
    p, y, r = [math.radians(a) for a in ang]
    sp, cp, sy, cy, sr, cr = math.sin(p), math.cos(p), math.sin(y), math.cos(y), math.sin(r), math.cos(r)
    # Source QAngle (pitch, yaw, roll) -> forward/left/up columns
    return [[cp * cy, sr * sp * cy - cr * sy, cr * sp * cy + sr * sy],
            [cp * sy, sr * sp * sy + cr * cy, cr * sp * sy - sr * cy],
            [-sp, sr * cp, cr * cp]]
def xform(p, o, ang):
    if not any(ang): return [p[0] + o[0], p[1] + o[1], p[2] + o[2]]
    m = rot_matrix(ang)
    return [m[r][0] * p[0] + m[r][1] * p[1] + m[r][2] * p[2] + o[r] for r in range(3)]
def angle_fwd(ang):
    m = rot_matrix(ang); return [m[0][0], m[1][0], m[2][0]]
