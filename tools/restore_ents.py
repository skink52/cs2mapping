"""restore_ents.py: put back entities the importer dropped (e.g. 1-unit tool-brush func_buttons), from the decompiled VMF.
Clones a same-class entity already in the CS2 map as the template (full key set, mesh settings), copies the VMF keys the
template has, the outputs and the brush box (one box per entity: the bounds of its solids).
usage: restore_btns.py <in.vmap> <map.vmf> <out.vmap> <name> [<name> ...]"""
import sys, re
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import vmapedit as V, vmf as vmfmod, dmx
src, vmfp, out, names = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
m = V.Map(src)
root = vmfmod.parse(open(vmfp, encoding='utf-8', errors='replace').read())
VE = {e.get('targetname'): e for e in root.ch if e.name == 'entity' and e.get('targetname') in names}
have = {m.name(e) for e in m.entities()}
for n in names:
    if n in have: print('already there:', n); continue
    ve = VE[n]; cls = ve.get('classname')
    tmpl = next(e for e in m.by_class(cls) if any(m.type(k) == b'CMapMesh' for k in m.children(e)))
    memo = {}; nid = [m.next_node_id()]
    j = m.import_subtree(m, tmpl, memo, nid)
    dmx.geta(m.E[m.world], b'children')[2].append(j)
    # keys: every VMF key the template entity also has, plus targetname
    for k, v in ve.kv if hasattr(ve, 'kv') else []:
        if k in ('origin', 'classname', 'id', 'hammerid'): continue
        if m.P(j, k) is not None or k in ('targetname', 'wait', 'spawnflags', 'speed', 'lip', 'health', 'locked_sound', 'unlocked_sound', 'sounds'):
            m.setp(j, k, v)
    o = [float(x) for x in ve.get('origin').split()]
    dmx.set_(m.E[j], b'origin', V.T_V3, o)
    dmx.geta(m.E[j], b'connectionsData')[2] = []
    for c in ve.ch:
        if c.name != 'connections': continue
        for out_name, v in (c.kv if hasattr(c, 'kv') else []):
            p = v.split('\x1b') if '\x1b' in v else v.split(',')
            m.add_conn(j, out_name, p[0], p[1], p[2], float(p[3] or 0), int(p[4] or -1))
    # mesh: the brush box
    pts = []
    for so in ve.ch:
        if so.name != 'solid': continue
        for sd in so.ch:
            if sd.name == 'side': pts += [[float(x) for x in t.split()] for t in re.findall(r'\(([^)]*)\)', sd.get('plane'))]
    mn = [min(p[k] for p in pts) for k in range(3)]; mx = [max(p[k] for p in pts) for k in range(3)]
    ctr = [(a + b) / 2 for a, b in zip(mn, mx)]
    for k in m.children(j):
        if m.type(k) != b'CMapMesh': continue
        dmx.set_(m.E[k], b'origin', V.T_V3, ctr)
        md = m.g(k, b'meshData')
        for st in m.g(m.g(md, b'vertexData'), b'streams'):
            if m.E[st]['name'].startswith(b'position'):
                a = dmx.geta(m.E[st], b'data'); P = a[2]
                c0 = [sum(p[i] for p in P) / len(P) for i in range(3)]
                a[2] = [[(mx[i] - ctr[i]) if p[i] > c0[i] else (mn[i] - ctr[i]) for i in range(3)] for p in P]
    print('restored %s (%s) at %s, box %s..%s, %d outputs' % (n, cls, o, mn, mx, len(m.conns(j))))
m.prune(); m.save(out)
