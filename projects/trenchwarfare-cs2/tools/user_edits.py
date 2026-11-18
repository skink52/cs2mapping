"""The user's Hammer edits, kept across regenerations (18 Nov 2026).

The map is regenerated from the tw34 delivery on every chain run (tools/deploy_tw.py --chain), so a change saved in Hammer on the
deployed map would be lost on the next deploy. This tool records those changes as a list (user_edits.json, in git) and replays them
as the chain's last stage, so the user's edits always win over what the generator places.

The user (18 Nov 2026): "Changed some small things on map too so make sure any future map adjustments read my changes".

usage:
  python tools/user_edits.py capture [--map <addon vmap>] [--deployed <vmap>] [--dry-run]
      compares the addon's map (the user's save) with the map the last deploy wrote, node by node (nodeIDs survive a Hammer save),
      and appends what changed to user_edits.json as one capture: entities moved / rotated / scaled / keyvalues changed, removed,
      added. Exit 0 also when the save is already captured or has no entity changes. Exit 3 (nothing written) when the save changes
      something this tool cannot replay: world geometry (a mesh added, removed or reshaped), vertex paint or visible texture
      alignment, a brush entity, or I/O connections. --deployed defaults to the map whose sha256 the newest deploy record wrote
      (out/step9/deployed_map.vmap, else the chain's stage outputs).
  python tools/user_edits.py apply --in <vmap> --out <vmap> [--targets T] [--report R]
      the chain stage 9_user: every recorded edit in order, matched by class, model, name and position (within 2 u); the guard
      targets are written for tools/patch_guard.py --strict. An edit that matches nothing (the generator moved or dropped that
      object) stops the stage: re-place it by hand or drop it from user_edits.json, never silently.
  python tools/user_edits.py list
      prints the recorded edits.

What is not replayed: invisible tool-texture alignment (Hammer re-aligns nav / lightmap-resolution tool faces on save; these do not
render). Level: "simulated" (patch_guard --strict); AI-generated (Claude) for skink52.
"""
import argparse, glob, hashlib, json, math, os, sys, time, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REPO = os.path.normpath(os.path.join(PROJ, '..', '..'))
OUT = os.path.join(PROJ, 'out')
STEP9 = os.path.join(OUT, 'step9')
EDITS = os.path.join(PROJ, 'user_edits.json')
USER_VMAP = r'C:\source1\links\content_addons\mg_trenchwarfare\maps\mg_trenchwarfare.vmap'
sys.path[:] = [os.path.join(REPO, 'tools')] + [p for p in sys.path if os.path.normcase(os.path.abspath(p or '.')) != os.path.normcase(HERE)]
import vmapedit as V      # noqa: E402
import dmx                # noqa: E402
import safepath           # noqa: E402

TOL = 2.0                 # u: how far a recorded object may be from where the edit expects it
SKIP_KEYS = {'origin', 'angles', 'scales'}


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def rnd(v, n=2):
    return [round(float(x), n) for x in v]


def ang_eq(a, b, tol=0.05):
    return all(abs(((x - y) + 180.0) % 360.0 - 180.0) <= tol for x, y in zip(a, b))


def props(m, i):
    pe = m.props(i)
    return {k.decode('utf-8', 'replace'): (v.decode('utf-8', 'replace') if isinstance(v, bytes) else v)
            for k, t, v in pe['attrs'] if t == dmx.T_STR}


def node_id(m, i):
    return m.g(i, b'nodeID')


def mesh_sig(m, i):
    """positions in world space + materials; vertex paint and texture streams (set 0) of visible materials. Not compared: tools/*
    faces and the lightmap UV set (:1), which Hammer re-aligns / recomputes on every save and which are not the user's edits"""
    md = m.g(i, b'meshData')
    if md is None: return ('none',)
    mats = [x.decode('utf-8', 'replace') if isinstance(x, bytes) else x for x in (m.g(md, b'materials') or [])]
    pts = sorted(tuple(round(c, 1) for c in p) for p in m.mesh_points(i))
    vis = [x for x in mats if not x.startswith('materials/tools/')]
    streams = []
    if vis:
        for arr in (b'faceVertexData', b'faceData', b'vertexData'):
            for st in m.g(m.g(md, arr), b'streams') or []:
                nm = m.E[st]['name']
                if nm.startswith(b'position') or not nm.endswith(b':0'): continue      # :1 = lightmap UVs, recomputed on every save
                d = m.g(st, b'data') or []
                if nm.startswith(b'VertexPaint') and len(set(map(repr, d))) <= 1: continue    # Hammer adds default paint on save
                streams.append((arr, nm, hashlib.md5(repr([tuple(round(c, 2) for c in x) if isinstance(x, (list, tuple)) else
                                                            (round(x, 2) if isinstance(x, float) else x) for x in d]).encode()).hexdigest()))
    return (tuple(pts), tuple(mats), tuple(sorted(streams)))


def centre(m, i):
    pts = m.mesh_points(i)
    return [round(sum(p[k] for p in pts) / max(1, len(pts)), 1) for k in range(3)] if pts else None


def index(m):
    ents, meshes = {}, {}
    for n, _ in m.walk():
        t = m.type(n)
        if t == b'CMapEntity': ents[node_id(m, n)] = n
        elif t == b'CMapMesh': meshes[node_id(m, n)] = n
    return ents, meshes


def describe(m, i):
    p = props(m, i)
    return dict(cls=p.get('classname', ''), model=p.get('model', ''), name=p.get('targetname', ''), at=rnd(m.origin(i)),
                angles=rnd(m.g(i, b'angles', [0, 0, 0])), scales=rnd(m.g(i, b'scales', [1, 1, 1]), 3))


def brushy(m, i):
    return any(m.type(c) == b'CMapMesh' for c in m.children(i))


def find_deployed():
    recs = sorted(glob.glob(os.path.join(STEP9, 'deploy', 'mg_trenchwarfare_deploy_*.json')), reverse=True)
    want = None
    for rp in recs:
        for e in json.load(open(rp, encoding='utf-8')).get('files', []):
            if e.get('rel', '').endswith('maps/mg_trenchwarfare.vmap') and e.get('after'): want = e['after']; break
        if want: break
    if not want: return None, None
    for p in [os.path.join(STEP9, 'deployed_map.vmap')] + sorted(glob.glob(os.path.join(STEP9, 'chain', '*.vmap')), key=os.path.getmtime, reverse=True):
        if os.path.isfile(p) and sha(p) == want: return p, want
    return None, want


def load_edits():
    if not os.path.isfile(EDITS): return dict(about='The user\'s Hammer edits, replayed by tools/user_edits.py apply (chain stage 9_user).', captures=[])
    return json.load(open(EDITS, encoding='utf-8'))


def capture(a):
    t0 = time.time()
    src = a.map
    if not os.path.isfile(src): sys.exit('user_edits: no map at %s' % src)
    s_sha = sha(src)
    E = load_edits()
    if any(c.get('from_sha256') == s_sha for c in E['captures']):
        print('user_edits: this save (sha256 %s) is already captured' % s_sha[:12]); return 0
    dep, want = (a.deployed, sha(a.deployed)) if a.deployed else find_deployed()
    if not dep:
        sys.exit('user_edits: the map the last deploy wrote (sha256 %s) is not on disk (out/step9/deployed_map.vmap or out/step9/chain/*.vmap): '
                 'cannot tell what was changed' % (want or '?')[:12])
    if s_sha == want:
        print('user_edits: the addon map is the deployed map; nothing to capture'); return 0
    A = V.Map(dep); B = V.Map(src)
    ea, ma = index(A); eb, mb = index(B)
    edits, refuse = [], []
    # world geometry
    for nid in sorted(set(ma) | set(mb), key=lambda x: (x is None, x)):
        if nid not in mb: refuse.append('mesh removed near %s' % centre(A, ma[nid])); continue
        if nid not in ma: refuse.append('mesh added near %s' % centre(B, mb[nid])); continue
        if mesh_sig(A, ma[nid]) != mesh_sig(B, mb[nid]): refuse.append('mesh changed (shape, material, paint or texture) near %s' % centre(B, mb[nid]))
    # entities
    for nid in sorted(set(ea) | set(eb), key=lambda x: (x is None, x)):
        if nid not in eb:
            i = ea[nid]
            if brushy(A, i): refuse.append('brush entity removed: %s' % describe(A, i)); continue
            edits.append(dict(op='remove', match=describe(A, i))); continue
        if nid not in ea:
            i = eb[nid]
            if brushy(B, i): refuse.append('brush entity added: %s' % describe(B, i)); continue
            if B.conns(i): refuse.append('added entity has I/O connections: %s' % describe(B, i)); continue
            d = describe(B, i)
            edits.append(dict(op='add', keys={k: v for k, v in props(B, i).items()}, at=d['at'], angles=d['angles'], scales=d['scales'],
                              vg=(B.g(i, b'customVisGroup') or b'').decode('utf-8', 'replace'))); continue
        i, j = ea[nid], eb[nid]
        da, db = describe(A, i), describe(B, j)
        pa, pb = props(A, i), props(B, j)
        keys = {k: pb.get(k) for k in pa if k not in SKIP_KEYS and pa.get(k) != pb.get(k)}     # a key only in the save = a Hammer default
        if pa.get('brightness_units', '0') != '0' and all(pa.get(k) == pb.get(k) for k in ('brightness_units', 'brightness_lumens', 'brightness_candelas', 'brightness_nits') if k in pa):
            keys.pop('brightness', None)     # Hammer re-derives 'brightness' (EV) from the lumens on save: not the user's edit
        moved = (math.dist(da['at'], db['at']) > 0.05 or not ang_eq(da['angles'], db['angles']) or
                 any(abs(x - y) > 0.001 for x, y in zip(da['scales'], db['scales'])))
        if [A.conn_tuple(c) for c in A.conns(i)] != [B.conn_tuple(c) for c in B.conns(j)]:
            refuse.append('I/O connections changed on %s' % db); continue
        if not (moved or keys): continue
        if brushy(A, i): refuse.append('brush entity changed: %s' % db); continue
        e = dict(op='edit', match=da)
        if moved: e.update(to=db['at'], to_angles=db['angles'], to_scales=db['scales'])
        if keys: e['keys'] = keys
        edits.append(e)
    print('user_edits: %s vs deployed %s: %d entity edits, %d not replayable (%.0f s)'
          % (os.path.basename(src), os.path.relpath(dep, PROJ), len(edits), len(refuse), time.time() - t0))
    for e in edits:
        m = e.get('match') or dict(cls=e['keys'].get('classname'), model=e['keys'].get('model', ''), at=e['at'])
        print('  %-6s %s %s at %s%s' % (e['op'], m['cls'], os.path.basename(m.get('model') or '') or m.get('name', ''), m['at'],
              (' -> %s ang %s' % (e['to'], e['to_angles'])) if 'to' in e else '') + (' keys %s' % e['keys'] if e['op'] == 'edit' and e.get('keys') else ''))
    for r in refuse: print('  NOT REPLAYABLE: %s' % r)
    if refuse:
        print('user_edits: nothing written. These changes cannot be replayed onto a regenerated map yet; teach the generator '
              '(make_map.py / a patch stage) or extend this tool.'); return 3
    if a.dry_run or not edits:
        if not edits: print('user_edits: no entity changes (a re-save)')
        if a.dry_run: return 0
    E['captures'].append(dict(date=time.strftime('%Y-%m-%d %H:%M'), from_sha256=s_sha, against_sha256=want, edits=edits))
    tmp = EDITS + '.part'
    json.dump(E, open(tmp, 'w', encoding='utf-8', newline='\n'), indent=1); os.replace(tmp, EDITS)
    print('user_edits: capture %d written to %s' % (len(E['captures']), os.path.relpath(EDITS, PROJ)))
    return 0


def find(m, cand, d):
    best = None
    for i in cand:
        p = props(m, i)
        if p.get('classname', '') != d['cls'] or p.get('model', '') != d.get('model', '') or p.get('targetname', '') != d.get('name', ''): continue
        dist = math.dist(m.origin(i), d['at'])
        if dist <= TOL and (best is None or dist < best[0]): best = (dist, i)
    return best[1] if best else None


def apply(a):
    outp = os.path.abspath(a.out)
    if not safepath.inside(OUT, outp) or os.path.normcase(outp) == os.path.normcase(os.path.abspath(a.inp)):
        sys.exit('user_edits: --out must be under %s and not the input' % OUT)
    tp = a.targets or os.path.splitext(outp)[0] + '.targets.json'
    rp = a.report or os.path.splitext(outp)[0] + '.report.json'
    raw = open(a.inp, 'rb').read()
    m = V.Map(a.inp, data=raw); m.path = a.inp
    V.random.seed('user_edits:%08x:%d' % (zlib.crc32(raw) & 0xffffffff, len(raw)))
    T = dict(input=os.path.abspath(a.inp), input_bytes=len(raw), input_crc32='%08x' % (zlib.crc32(raw) & 0xffffffff), modify={}, remove={}, add=[],
             prefix=[], root=False)
    E = load_edits()
    rep = dict(tool='tools/user_edits.py apply', captures=len(E['captures']), applied=[], missing=[])
    live = set(m.entities())
    added = {}
    for ci, c in enumerate(E['captures']):
        for e in c['edits']:
            tag = 'capture %d (%s)' % (ci + 1, c['date'])
            if e['op'] == 'add':
                k = dict(e['keys']); cls = k.pop('classname')
                i = m.new_entity(cls, e['at'], k, angles=e['angles'])
                dmx.set_(m.E[i], b'scales', dmx.T_V3, [float(x) for x in e.get('scales', [1, 1, 1])])
                if e.get('vg'): dmx.set_(m.E[i], b'customVisGroup', dmx.T_STR, e['vg'].encode())
                ent = dict(type='CMapEntity', **{'class': cls}, why='user edit, ' + tag)
                if k.get('targetname'): ent['name'] = k['targetname']      # the guard matches a missing name to an unnamed node
                T['add'].append(ent); live.add(i); added[i] = ent
                rep['applied'].append(dict(op='add', cls=cls, model=k.get('model', ''), at=e['at'])); continue
            d = e['match']
            i = find(m, live, d)
            if i is None:
                rep['missing'].append(dict(op=e['op'], tag=tag, **d)); continue
            nid = str(node_id(m, i))
            if e['op'] == 'remove':
                m.remove_node(i); live.discard(i)
                if i in added: T['add'].remove(added.pop(i))           # added by an earlier capture, removed by a later one: net nothing
                else: T['remove'][nid] = dict(i=i, why='user edit, ' + tag)
                rep['applied'].append(dict(op='remove', cls=d['cls'], model=d.get('model', ''), at=d['at'])); continue
            fields = []
            if 'to' in e:
                dmx.set_(m.E[i], b'origin', dmx.T_V3, [float(x) for x in e['to']])
                dmx.set_(m.E[i], b'angles', dmx.T_QANG, [float(x) for x in e['to_angles']])
                dmx.set_(m.E[i], b'scales', dmx.T_V3, [float(x) for x in e['to_scales']])
                fields += ['origin', 'angles', 'scales']
            for k, v in (e.get('keys') or {}).items():
                if v is None: m.delp(i, k)
                else: m.setp(i, k, v)
                fields.append('kv:' + k)
            if i not in added:
                f = T['modify'].setdefault(nid, dict(i=i, fields=[], why='user edit, ' + tag))
                f['fields'] = sorted(set(f['fields']) | set(fields))
            rep['applied'].append(dict(op='edit', cls=d['cls'], model=d.get('model', ''), at=d['at'], to=e.get('to')))
    if rep['missing']:
        json.dump(rep, open(rp, 'w'), indent=1)
        for x in rep['missing']: print('  NOT FOUND: %s %s %s at %s (%s)' % (x['op'], x['cls'], os.path.basename(x.get('model', '')), x['at'], x['tag']))
        sys.exit('user_edits: %d recorded edits match nothing in this map (the generator moved or dropped those objects); nothing written. '
                 'Re-place them, or drop them from user_edits.json with the user\'s OK.' % len(rep['missing']))
    if T['remove'] or T['add']:
        counts = {}
        for x in m.entities(): counts[m.cls(x)] = counts.get(m.cls(x), 0) + 1
        for attrs in m.doc.prefix:
            pre = {x[0]: x for x in attrs}
            if b'map_subasset_reference_names' in pre:
                names = sorted(counts)
                pre[b'map_subasset_reference_types'][2] = [b'entity'] * len(names)
                pre[b'map_subasset_reference_names'][2] = [nm.encode() for nm in names]
                pre[b'map_subasset_reference_counts'][2] = [counts[nm] for nm in names]
                T['prefix'] += ['map_subasset_reference_counts', 'map_subasset_reference_names', 'map_subasset_reference_types']
        m.prune()
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    n = m.save(outp)
    T['output'] = outp
    json.dump(T, open(tp, 'w'), indent=1)
    json.dump(rep, open(rp, 'w'), indent=1)
    ops = {}
    for x in rep['applied']: ops[x['op']] = ops.get(x['op'], 0) + 1
    print('patched map: %s (%d bytes); user edits from %d captures: %s' % (outp, n, len(E['captures']),
          ', '.join('%d %s' % (v, k) for k, v in sorted(ops.items())) or 'none'))
    return 0


def main():
    ap = argparse.ArgumentParser(description='the user\'s Hammer edits, kept across regenerations')
    sp = ap.add_subparsers(dest='cmd', required=True)
    c = sp.add_parser('capture'); c.add_argument('--map', default=USER_VMAP); c.add_argument('--deployed'); c.add_argument('--dry-run', action='store_true')
    p = sp.add_parser('apply'); p.add_argument('--in', dest='inp', required=True); p.add_argument('--out', required=True)
    p.add_argument('--targets'); p.add_argument('--report'); p.add_argument('--no-guard', action='store_true')
    sp.add_parser('list')
    a = ap.parse_args()
    if a.cmd == 'capture': return capture(a)
    if a.cmd == 'apply': return apply(a)
    E = load_edits()
    for ci, c in enumerate(E['captures']):
        print('capture %d, %s (save %s): %d edits' % (ci + 1, c['date'], c['from_sha256'][:12], len(c['edits'])))
        for e in c['edits']:
            d = e.get('match') or dict(cls=e['keys'].get('classname'), model=e['keys'].get('model', ''), at=e['at'])
            print('  %-6s %s %s at %s%s' % (e['op'], d['cls'], os.path.basename(d.get('model') or ''), d['at'], (' -> %s' % e['to']) if 'to' in e else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
