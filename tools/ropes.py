"""CS:GO move_rope / keyframe_rope -> CS2 cable_dynamic, the way skink52 rebuilt ba_jail_keimusho's rope by hand (2 Nov 2026).

CS2 can't spawn the CS:GO rope entities and the importer drops them. Each rope segment (an entity and its NextKey) becomes a cable_dynamic
(CMapCable) through path_node_cable points: world-space origins, smooth interpolation, the template's 8 sides and texture scale.
  - material: CS:GO cable/rope* -> stock materials/de_overpass/construction/rope/rope_braid_1.vmat; cable/cable -> stock materials/cable/cable.vmat
  - radius: CS:GO Width / 4 (keimusho: Width 2 -> radius 0.5)
  - sag: Slack becomes a parabola with the same extra length, scaled by how level the rope is (a hanging rope stays straight)
  - ropes (not electrical cables) get a grapplinghook_rope_end_01 prop at each free end, tinted 240 179 94, its axis along the rope pointing
    inward. The cap goes at the rope's end point, where it meets the surface; a cable that runs a little into terrain is left as it is.
Re-runnable: earlier port_rope_* cables and caps are replaced.

CS2's own path_particle_rope (a CMapPath with path_node_generic children; a particle cable, no collision, flat lit) is rebuilt the same way
(particle_ropes): one cable_dynamic through the same node positions, its RopeMaterial mapped as above (cable/cable -> cable.vmat), radius from
its own radius key (already a CS2 cable radius; Width / 4 if only a width is given, else 0.5), each node's radius_scale kept, sag from slack per
segment, the targetname kept, straight paths stay linear. The original is removed. No end caps (de_nuketown, 3 Nov 2026). Stage C / D `ropes`
run it too, with or without a .vmf.

  python3 ropes.py <vmap in> <vmap out>                 path_particle_rope -> cable_dynamic in an installed map (Hammer closed, vmap backed up)
  python3 ropes.py --make-template <vmap with one hand-made cable_dynamic> <out cable_template.vmap>   (how tools/cable_template.vmap was made)
"""
import math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dmx, vmapedit as V, vmf as vmfmod

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, 'cable_template.vmap')
ROPE_MAT = 'materials/de_overpass/construction/rope/rope_braid_1.vmat'
CABLE_MAT = 'materials/cable/cable.vmat'
END_MODEL = 'models/generic/grapplinghook_01/grapplinghook_rope_end_01.vmdl'
END_TINT = '240 179 94 255'
NODE_STEP = 48.0

def ropes_in(vmfpath):
    if not vmfpath or not os.path.exists(vmfpath): return []
    root = vmfmod.parse(open(vmfpath, encoding='utf-8', errors='replace').read())
    out = []
    for e in root.ch:
        if e.name != 'entity': continue
        d = {k.lower(): v for k, v in e.kv}
        if d.get('classname') in ('move_rope', 'keyframe_rope'): out.append(d)
    return out

def segments(rs):
    """(start, end) entity pairs along NextKey, each pair once (rope3 <-> rope4 point at each other)"""
    by = {r.get('targetname', '').lower(): r for r in rs if r.get('targetname')}
    seen = set(); out = []; broken = []
    for r in rs:
        t = by.get((r.get('nextkey') or '').lower())
        if not r.get('nextkey'): continue
        if t is None: broken.append(r.get('targetname') or r.get('origin')); continue
        k = frozenset((r.get('origin'), t.get('origin')))
        if k in seen or len(k) < 2: continue
        seen.add(k); out.append((r, t))
    return out, broken

def pos(d): return np.array([float(x) for x in d.get('origin', '0 0 0').split()[:3]])

def points(a, b, slack):
    v = b - a; L = float(np.linalg.norm(v)); level = float(np.hypot(v[0], v[1])) / L if L else 0
    sag = math.sqrt(3 * L * max(slack, 0) / 8) * level      # parabola whose length is L + slack
    n = 2 if sag < 1 else max(3, int(math.ceil(L / NODE_STEP)) + 1)
    t = np.linspace(0, 1, n)
    return [a + v * x - np.array([0, 0, sag * 4 * x * (1 - x)]) for x in t], sag

def material(name):
    n = (name or '').lower().replace('\\', '/')
    if 'rope' in n: return ROPE_MAT, True, False
    if 'cable' in n: return CABLE_MAT, False, False
    return ROPE_MAT, True, True

def cap_angles(inward):
    """angles that turn the cap model's +Z axis to point along the rope (pitch p, yaw y: up = (sin p cos y, sin p sin y, cos p))"""
    d = inward / (np.linalg.norm(inward) or 1)
    p = math.degrees(math.acos(max(-1.0, min(1.0, d[2]))))
    y = math.degrees(math.atan2(d[1], d[0])) if math.hypot(d[0], d[1]) > 1e-6 else 0.0
    return (p, y, 0.0)

def run(m, c, vmfpath):
    particle_ropes(m, c)
    rs = ropes_in(vmfpath)
    if not rs: return
    for n in list(m.children(m.world)):   # a rerun replaces what an earlier run made
        if m.type(n) in (b'CMapCable', b'CMapEntity') and (m.name(n) or '').startswith('port_rope_'): m.remove_node(n)
    segs, broken = segments(rs)
    tm = V.Map(TEMPLATE); tcab = tm.children(tm.world)[0]; tnode = tm.children(tcab)[0]
    nid = [m.next_node_id()]
    ends = {}
    for r, t in segs:
        for e in (r, t): ends[e.get('origin')] = ends.get(e.get('origin'), 0) + 1
    made = 0; caps = 0; odd = set(); sags = []
    for i, (r, t) in enumerate(segs):
        mat, is_rope, unknown = material(r.get('ropematerial'))
        if unknown: odd.add(r.get('ropematerial') or '(none)')
        a, b = pos(r), pos(t)
        pts, sag = points(a, b, float(r.get('slack', '0') or 0)); sags.append(sag)
        j = m.import_subtree(tm, tcab, {}, nid)
        nodes = [m.import_subtree(tm, tnode, {}, nid) for _ in pts]
        for nd, p in zip(nodes, pts): dmx.set_(m.E[nd], b'origin', dmx.T_V3, [float(x) for x in p])
        dmx.geta(m.E[j], b'children')[2] = nodes
        dmx.set_(m.E[j], b'origin', dmx.T_V3, [float(x) for x in pts[0]])
        dmx.set_(m.E[j], b'materialName', dmx.T_STR, mat.encode())
        dmx.set_(m.E[j], b'radius', dmx.T_FLOAT, max(0.25, float(r.get('width', '2') or 2) / 4))
        m.setp(j, 'targetname', 'port_rope_%d' % i)
        dmx.geta(m.E[m.world], b'children')[2].append(j); made += 1
        if not is_rope: continue
        for end, other in ((a, pts[1]), (b, pts[-2])):
            key = r.get('origin') if end is a else t.get('origin')
            if ends.get(key, 0) > 1: continue        # a joint in the middle of a chain, not a free end
            m.new_entity('prop_static', end, {'targetname': 'port_rope_end_%d' % caps, 'model': END_MODEL, 'rendercolor': END_TINT, 'solid': '6'},
                         angles=cap_angles(other - end))
            caps += 1
    c.log.append('%d move_rope / keyframe_rope (CS2 drops them) -> %d cable_dynamic (rope_braid_1 for ropes, cable.vmat for cables, radius = Width / 4, '
                 'sag from Slack up to %.0f u) + %d rope end caps' % (len(rs), made, max(sags or [0]), caps))
    c.todo.append('ropes rebuilt as cable_dynamic (%d): check the sag, and that each end cap sits where the rope meets a surface' % made)
    if odd: c.todo.append('rope materials with no CS2 match, drawn as rope_braid_1: %s' % ', '.join(sorted(odd)))
    if broken: c.todo.append('ropes whose NextKey target is missing, not rebuilt: %s' % ', '.join(sorted(map(str, broken))))

def particle_ropes(m, c=None):
    """every path_particle_rope (CMapPath) -> one cable_dynamic (CMapCable) through the same nodes; returns how many"""
    paths = [(n, p) for n, p in m.walk() if m.type(n) == b'CMapPath' and m.P(n, 'classname') == 'path_particle_rope']
    if not paths: return 0
    tm = V.Map(TEMPLATE); tcab = tm.children(tm.world)[0]; tnode = tm.children(tcab)[0]
    nid = [m.next_node_id()]; odd = set(); sags = []; made = 0
    for i, (n, parent) in enumerate(paths):
        kids = [k for k in m.children(n) if m.type(k) == b'CMapPathNode']
        if len(kids) < 2: continue
        mat, _, unknown = material(m.P(n, 'RopeMaterial'))
        if unknown: odd.add(m.P(n, 'RopeMaterial') or '(none)')
        slack = float(m.P(n, 'slack', '0') or 0)
        r = m.P(n, 'radius'); w = m.P(n, 'width')
        radius = float(r) if r else (float(w) / 4 if w else 0.5)
        pts = []; srcs = []; sag = 0.0           # srcs: the source node at each point, None for the sag points in between
        for a, b in zip(kids, kids[1:]):
            seg, sg = points(np.array(m.origin(a)), np.array(m.origin(b)), slack); sag = max(sag, sg)
            if pts: seg = seg[1:]                 # the joint is already there
            pts += seg; srcs += [None] * (len(seg) - 1) + [b]
        srcs[0] = kids[0]; sags.append(sag)
        j = m.import_subtree(tm, tcab, {}, nid)
        nodes = [m.import_subtree(tm, tnode, {}, nid) for _ in pts]
        scale = '1'
        for nd, p, src in zip(nodes, pts, srcs):
            dmx.set_(m.E[nd], b'origin', dmx.T_V3, [float(x) for x in p])
            if src is not None: scale = m.P(src, 'radius_scale', '1')
            m.setp(nd, 'radius_scale', scale)         # sag points carry the joint before them
            if src is None: continue
            if sag < 1:    # a straight path keeps its corners: the source's tangent types, not the template's smooth ones
                for k in (b'inTangentType', b'outTangentType'): dmx.set_(m.E[nd], k, dmx.T_INT, int(m.g(src, k, 0)))
        dmx.geta(m.E[j], b'children')[2] = nodes
        dmx.set_(m.E[j], b'origin', dmx.T_V3, [float(x) for x in pts[0]])
        if sag < 1: dmx.set_(m.E[j], b'interpolationType', dmx.T_INT, int(m.g(n, b'interpolationType', 0)))
        dmx.set_(m.E[j], b'materialName', dmx.T_STR, mat.encode())
        dmx.set_(m.E[j], b'radius', dmx.T_FLOAT, max(0.25, radius))
        m.setp(j, 'targetname', m.P(n, 'targetname') or 'port_rope_p%d' % i)
        ch = dmx.geta(m.E[parent], b'children')[2]
        ch[ch.index(n)] = j; made += 1       # same parent and position in the tree as the path it replaces
    if c is not None:
        c.log.append('%d path_particle_rope (CS2 particle cables) -> %d cable_dynamic (%s, radius and node radius_scale kept, sag from slack up to %.0f u), '
                     'originals removed' % (len(paths), made, 'cable.vmat' if not odd else 'material mapped', max(sags or [0])))
        if odd: c.todo.append('path_particle_rope materials with no CS2 match, drawn as rope_braid_1: %s' % ', '.join(sorted(odd)))
    return made

def make_template(src, out):
    s = V.Map(src); cab = next(n for n, _ in s.walk() if s.type(n) == b'CMapCable')
    t = V.Map(os.path.join(HERE, 'laser_template.vmap'))
    w = dmx.geta(t.E[t.world], b'children'); w[2] = []
    j = t.import_subtree(s, cab, {}, [t.next_node_id()])
    dmx.geta(t.E[j], b'children')[2] = dmx.geta(t.E[j], b'children')[2][:1]   # one path node is enough as the copy source
    w[2].append(j); t.prune(); t.save(out)
    print('wrote', out)

class _Log:
    def __init__(s): s.log = []; s.todo = []

if __name__ == '__main__':
    if sys.argv[1:2] == ['--make-template']: make_template(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3:
        m = V.Map(sys.argv[1]); c = _Log(); n = particle_ropes(m, c)
        if n: print('pruned %d orphaned elements' % m.prune()); m.save(sys.argv[2]); print('wrote', sys.argv[2])
        else: print('no path_particle_rope in', sys.argv[1])
        for l in c.log: print(l)
        for t in c.todo: print('TO CHECK:', t)
    else: print(__doc__)
