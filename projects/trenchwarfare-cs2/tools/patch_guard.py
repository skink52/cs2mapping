"""Guard for delta patches on the user's vmap (remaster rule: patch only, never regenerate). Compares an input and an output vmap node by
node and FAILS (exit 1) when anything changed, appeared or disappeared that the patch did not declare. Reads both maps; writes only
the report.

usage: python tools/patch_guard.py <input.vmap> <output.vmap> <targets.json> [--report out.json] [--strict]
       python tools/patch_guard.py <input.vmap> --selftest        (plants undeclared changes in memory; every one must be caught)

What is compared. Every node under the world (CMapEntity, CMapMesh, groups, prefabs, nav data ...), keyed by its nodeID (stable across
Hammer saves and element pruning; the element index "i" of mapdigest / vmapedit is reported alongside):
  type, parent    the node's class of element and the nodeID of its parent
  class, kv:<key> entity keyvalues (each key separately; a key added or removed counts as a change of kv:<key>)
  origin, angles, scales, vg (customVisGroup)
  conns           the I/O connections (output, target, input, param, delay, times)
  mesh            hash of the whole meshData subtree (vertices, faces, materials, UVs ...)
  other           hash of every remaining attribute and the element subtrees it points at (transformPin, relayPlugData ...);
                  a pointer to another node is hashed as its nodeID, so a change in one node never shows up in another
Outside the world: the root's other attributes (visibility manager, map variables, cameras, selection sets) as one hash, and each
prefix attribute (map_asset_references, map_subasset_reference_*), which the patch must declare by name.

targets.json (the patch writes it next to its output):
  {"modify": {"<nodeID>": {"i": 3651, "fields": ["class", "kv:model", "kv:targetname", ...] | ["*"], "why": "..."}},
   "remove": {"<nodeID>": {"i": 7, "why": "..."}},
   "add":    [{"type": "CMapEntity", "class": "...", "name": "...", "why": "..."}],
   "prefix": ["map_asset_references", ...], "root": false}
  A "kv:*" field allows any keyvalue change on that node. An added node matches one "add" entry by type, class and name.
Declared targets that did not change are listed as warnings (errors with --strict).
"""
import hashlib, json, os, struct, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_TOOLS = os.path.normpath(os.path.join(HERE, '..', '..', '..', 'tools'))
# the project's tools/ has its own dmx.py; the repo readers need the repo's
sys.path[:] = [REPO_TOOLS] + [p for p in sys.path if os.path.normcase(os.path.abspath(p or '.')) != os.path.normcase(HERE)]
import vmapedit as V      # noqa: E402
import dmx                # noqa: E402

T_ELEM, ARR_ELEM = dmx.T_ELEM, dmx.ARR + dmx.T_ELEM
OWN = {b'origin', b'angles', b'scales', b'customVisGroup', b'entity_properties', b'meshData', b'connectionsData', b'children', b'nodeID'}


def _hv(h, v):
    if isinstance(v, (bytes, bytearray)): h.update(b'b'); h.update(struct.pack('<I', len(v))); h.update(v)
    elif isinstance(v, str): _hv(h, v.encode())
    elif isinstance(v, bool): h.update(b'T' if v else b'F')
    elif isinstance(v, int): h.update(b'i' + str(v).encode())
    elif isinstance(v, float): h.update(b'f' + repr(round(v, 5)).encode())
    elif isinstance(v, (list, tuple)):
        if v and not isinstance(v[0], (bytes, bytearray, str)):
            h.update(b'L' + repr(v).encode())        # numbers / vectors: exact repr (the reader gives the same floats every time)
        else:
            h.update(b'[' + str(len(v)).encode())
            for x in v: _hv(h, x)
    else: h.update(repr(v).encode())


class Snap:
    """per-node records of one map"""
    def __init__(s, path=None, m=None):
        s.m = m or V.Map(path)
        s.memo = {}
        s.nodes = {}
        m = s.m
        for n, p in m.walk():
            nid = m.g(n, b'nodeID')
            if nid in s.nodes: raise ValueError('duplicate nodeID %s (elements %d and %d)' % (nid, s.nodes[nid]['i'], n))
            s.nodes[nid] = s.record(n, p)
        s.root = s.root_hash()
        s.prefix = {}
        for attrs in m.doc.prefix:
            for name, t, v in attrs:
                h = hashlib.sha1(); _hv(h, v); s.prefix[name.decode()] = h.hexdigest()

    def is_node(s, i):
        return any(a[0] == b'nodeID' for a in s.m.E[i]['attrs'])

    def deep(s, i, top=False):
        """hash of element i and the elements it points at; a pointer to another node is its nodeID"""
        if not top and i in s.memo: return s.memo[i]
        e = s.m.E[i]
        h = hashlib.sha1(); h.update(e['type']); h.update(e['name'] or b'')
        if not top and s.is_node(i):
            h.update(b'node' + str(s.m.g(i, b'nodeID')).encode()); r = h.hexdigest(); s.memo[i] = r; return r
        if not top: s.memo[i] = 'cycle'
        for name, t, v in e['attrs']:
            if top and name in OWN: continue
            h.update(name); h.update(bytes([t & 255]))
            if t == T_ELEM: h.update((s.deep(v) if isinstance(v, int) and v >= 0 else 'null').encode())
            elif t == ARR_ELEM:
                for x in v: h.update((s.deep(x) if isinstance(x, int) and x >= 0 else 'null').encode())
            else: _hv(h, v)
        r = h.hexdigest()
        if not top: s.memo[i] = r
        return r

    def record(s, n, p):
        m = s.m
        r = dict(i=n, type=m.type(n).decode(), parent=m.g(p, b'nodeID'))
        for k in (b'origin', b'angles', b'scales'):
            v = m.g(n, k)
            if v is not None: r[k.decode()] = [round(float(x), 4) for x in v]
        vg = m.g(n, b'customVisGroup')
        r['vg'] = vg.decode() if isinstance(vg, bytes) else (vg or '')
        if m.g(n, b'entity_properties') is not None:
            kv = {}
            for name, t, v in m.props(n)['attrs']:
                kv[name.decode()] = v.decode('utf-8', 'replace') if isinstance(v, bytes) else repr(v)
            r['class'] = kv.pop('classname', ''); r['kv'] = kv
            r['conns'] = [list(m.conn_tuple(c)) for c in m.conns(n)]
        md = m.g(n, b'meshData')
        if md is not None: r['mesh'] = s.deep(md) if md >= 0 else 'null'
        r['other'] = s.deep(n, top=True)
        return r

    def root_hash(s):
        m = s.m; h = hashlib.sha1()
        for name, t, v in m.E[m.root]['attrs']:
            if name == b'world': continue
            h.update(name)
            if t == T_ELEM: h.update((s.deep(v) if isinstance(v, int) and v >= 0 else 'null').encode())
            elif t == ARR_ELEM:
                for x in v: h.update((s.deep(x) if isinstance(x, int) and x >= 0 else 'null').encode())
            else: _hv(h, v)
        return h.hexdigest()


def diff_fields(a, b):
    out = []
    for k in ('type', 'parent', 'class', 'origin', 'angles', 'scales', 'vg', 'conns', 'mesh', 'other'):
        if a.get(k) != b.get(k): out.append(k)
    ka, kb = a.get('kv') or {}, b.get('kv') or {}
    for k in sorted(set(ka) | set(kb)):
        if ka.get(k) != kb.get(k): out.append('kv:' + k)
    return out


def label(r):
    return '%s i=%d %s%s%s vg=%s' % (r['type'], r['i'], r.get('class', ''), (' ' + r['kv'].get('targetname', '')) if r.get('kv', {}).get('targetname') else '',
                                    (' ' + r['kv']['model'].split('/')[-1]) if r.get('kv', {}).get('model') else '', r['vg'] or 'ungrouped')


def compare(A, B, T):
    """-> (violations, warnings, changes)"""
    viol, warn, changes = [], [], []
    mod = {int(k): v for k, v in (T.get('modify') or {}).items()}
    rem = {int(k): v for k, v in (T.get('remove') or {}).items()}
    adds = list(T.get('add') or [])
    seen_mod, seen_rem = set(), set()
    for nid, a in A.nodes.items():
        b = B.nodes.get(nid)
        if b is None:
            changes.append(('removed', nid, label(a)))
            if nid in rem: seen_rem.add(nid)
            else: viol.append('UNDECLARED removal: node %d (%s)' % (nid, label(a)))
            continue
        f = diff_fields(a, b)
        if not f: continue
        changes.append(('modified', nid, label(a), f))
        d = mod.get(nid)
        if d is None:
            viol.append('UNDECLARED change: node %d (%s): %s' % (nid, label(a), ', '.join(f))); continue
        seen_mod.add(nid)
        allow = set(d.get('fields') or [])
        if '*' in allow: continue
        bad = [x for x in f if x not in allow and not (x.startswith('kv:') and 'kv:*' in allow)]
        if bad: viol.append('UNDECLARED fields on node %d (%s): %s (declared %s)' % (nid, label(a), ', '.join(bad), sorted(allow)))
    for nid, b in B.nodes.items():
        if nid in A.nodes: continue
        changes.append(('added', nid, label(b)))
        hit = next((k for k, d in enumerate(adds) if d.get('type', b['type']) == b['type'] and d.get('class', b.get('class')) == b.get('class')
                    and d.get('name', b.get('kv', {}).get('targetname')) == b.get('kv', {}).get('targetname')), None)
        if hit is None: viol.append('UNDECLARED new node %d (%s)' % (nid, label(b)))
        else: adds.pop(hit)
    for nid in mod:
        if nid not in seen_mod: warn.append('declared change did not happen: node %d (i=%s)' % (nid, mod[nid].get('i')))
    for nid in rem:
        if nid not in seen_rem: warn.append('declared removal did not happen: node %d (i=%s)' % (nid, rem[nid].get('i')))
    for d in adds: warn.append('declared new node not found: %s' % d)
    if A.root != B.root:
        changes.append(('root', None, 'root attributes'))
        if not T.get('root'): viol.append('UNDECLARED change in the root attributes (visibility manager, map variables, cameras ...)')
    pre = set(T.get('prefix') or [])
    for k in sorted(set(A.prefix) | set(B.prefix)):
        if A.prefix.get(k) != B.prefix.get(k):
            changes.append(('prefix', None, k))
            if k not in pre: viol.append('UNDECLARED change in prefix attribute %s' % k)
    return viol, warn, changes


def selftest(path):
    """plant undeclared changes in a copy of the input in memory; each must be caught, and an unchanged copy must pass"""
    A = Snap(path)
    m = A.m
    ok = True
    def run(name, mutate, expect):
        nonlocal ok
        m2 = V.Map(path)                      # a fresh copy each time
        mutate(m2)
        B = Snap(m=m2)
        viol, warn, ch = compare(A, B, {})
        got = bool(viol)
        good = got == expect
        print('  %-48s %s %s' % (name, 'caught' if got else 'clean', 'OK' if good else 'FAIL') + ('' if not viol else '  <- ' + viol[0][:110]))
        ok &= good
    ents = m.entities()
    prop = next(e for e in ents if m.cls(e) == 'prop_static')
    def mv(m2): m2.E[prop]['attrs'] = [[k, t, ([v[0] + 0.5, v[1], v[2]] if k == b'origin' else v)] for k, t, v in m2.E[prop]['attrs']]
    def kv(m2): m2.setp(prop, 'solid', '0')
    def kvadd(m2): m2.setp(prop, 'targetname', 'sneaky')
    nm = next(e for e in ents if m.name(e))
    def drop(m2): m2.remove_node(nm)
    def add(m2): m2.new_entity('info_target', (1, 2, 3), {'targetname': 'planted'})
    mesh = next(n for n, _ in m.walk() if m.type(n) == b'CMapMesh')
    def vert(m2):
        md = m2.g(mesh, b'meshData'); vd = m2.g(md, b'vertexData')
        st = next(s_ for s_ in m2.g(vd, b'streams') if m2.E[s_]['name'].startswith(b'position'))
        a = dmx.geta(m2.E[st], b'data'); a[2] = [list(p) for p in a[2]]; a[2][0][2] += 1.0
    def vg(m2): dmx.set_(m2.E[prop], b'customVisGroup', dmx.T_STR, b'moved_group')
    def pre(m2): m2.doc.prefix[0] = [[k, t, (list(v) + ['models/x.vmdl'] if k == b'map_asset_references' else v)] for k, t, v in m2.doc.prefix[0]]
    def conn(m2):
        src = next(e for e in ents if m.conns(e))
        c = m2.conns(src)[0]; dmx.set_(c, b'delay', dmx.T_FLOAT, 9.0)
    run('unchanged copy', lambda m2: None, False)
    for name, f in (('origin: move a prop 0.5 u', mv), ('kv:solid changed', kv), ('kv:targetname added', kvadd), ('removal of a named entity', drop),
                    ('new node', add), ('mesh: one vertex 1 u up', vert), ('vg changed', vg), ('prefix asset list', pre), ('conns: delay changed', conn)):
        run(name, f, True)
    print('selftest:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ('-h', '--help'): print(__doc__); return 2
    if '--selftest' in argv: return selftest(argv[0])
    rep = argv[argv.index('--report') + 1] if '--report' in argv else None
    strict = '--strict' in argv
    pos = [a for a in argv if not a.startswith('--') and a != rep]
    if len(pos) != 3: print(__doc__); return 2
    t0 = time.time()
    T = json.load(open(pos[2]))
    A, B = Snap(pos[0]), Snap(pos[1])
    viol, warn, changes = compare(A, B, T)
    if strict: viol += warn; warn = []
    kinds = {}
    for c in changes: kinds[c[0]] = kinds.get(c[0], 0) + 1
    print('patch_guard: %d nodes in, %d out; changes %s' % (len(A.nodes), len(B.nodes), kinds or 'none'))
    short = lambda f: ', '.join(f[:6]) + (' ... (%d fields)' % len(f) if len(f) > 6 else '')
    for c in changes[:80]: print('   ', c[0], c[1] if c[1] is not None else '', c[2], short(c[3]) if len(c) > 3 else '')
    if len(changes) > 80: print('    ... %d more' % (len(changes) - 80))
    for w in warn: print('WARNING ' + w)
    for v in viol: print('VIOLATION ' + v)
    res = dict(input=pos[0], output=pos[1], targets=pos[2], nodes_in=len(A.nodes), nodes_out=len(B.nodes), changes=[list(c) for c in changes],
               warnings=warn, violations=viol, result='PASS' if not viol else 'FAIL', seconds=round(time.time() - t0, 1))
    if rep:
        os.makedirs(os.path.dirname(os.path.abspath(rep)), exist_ok=True)
        json.dump(res, open(rep, 'w'), indent=1)
    print('RESULT: %s (%d declared targets; %d violations, %d warnings; %.1f s)' % (res['result'], len(T.get('modify') or {}) + len(T.get('remove') or {}) + len(T.get('add') or []),
                                                                                  len(viol), len(warn), time.time() - t0))
    return 1 if viol else 0


if __name__ == '__main__':
    sys.exit(main())
