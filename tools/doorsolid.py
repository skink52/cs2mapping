"""Stage D pass `doorsolid`: CS:GO doors flagged "Non-solid to Player" (spawnflags 4) are solid in CS2.

ttt_minecraft's hut doors (func_door_rotating, 36 wide in a 36-wide frame) were non-solid in CS:GO; solid in CS2, the open door
panel leaves 32 units, too narrow to pass (skink52, 29 Oct 2026). Same look, CS:GO behaviour:
- the door's meshes move to a never-solid func_brush `<door>_vis` parented to the door, so it swings exactly as before;
- the door itself keeps only a 2-unit toolsnodraw cube on its hinge (func_door_rotating) or at its centre (func_door), so it still
  moves and fires its outputs but blocks nothing.
func_door / func_door_rotating without the flag are left alone. Unnamed doors get a name (port_door_<n>) so the brush can follow; the second
of two doors sharing a name gets <name>_2 and copies of every output aimed at the shared name.
"""
import os
import dmx
import vmapedit as V

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'box_template.vmap')
NODRAW = b'materials/tools/toolsnodraw.vmat'


def box(m, tm, tnode, mn, mx, mat):
    j = m.import_subtree(tm, tnode, {}, [m.next_node_id()])
    md = m.g(j, b'meshData')
    dmx.set_(m.E[md], b'materials', dmx.ARR + dmx.T_STR, [mat])
    dmx.set_(m.E[j], b'origin', dmx.T_V3, [0.0, 0.0, 0.0])
    for st in m.g(m.g(md, b'vertexData'), b'streams'):
        if m.E[st]['name'].startswith(b'position'):
            a = dmx.geta(m.E[st], b'data'); pts = a[2]
            ctr = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
            a[2] = [[mx[k] if p[k] > ctr[k] else mn[k] for k in range(3)] for p in pts]
    return j


def run(m, c):
    doors = [e for e in m.by_class('func_door', 'func_door_rotating') if int(float(m.P(e, 'spawnflags', '0') or 0)) & 4]
    if not doors: return 0
    tm = V.Map(TEMPLATE); tnode = tm.children(tm.world)[0]
    taken = {m.name(e).lower() for e in m.entities() if m.name(e)}
    k = 0; done = []
    for d in doors:
        meshes = [ch for ch in m.children(d) if m.type(ch) == b'CMapMesh']
        if not meshes: continue
        name = m.name(d)
        if not name:
            while 'port_door_%d' % k in taken: k += 1
            name = 'port_door_%d' % k; taken.add(name); m.setp(d, 'targetname', name)
        elif name in done:
            # two doors share a name (a double door): parenting by name would hang both brushes on the first one, so this one gets
            # its own name and every output aimed at the shared name is copied to it
            new = name; i = 2
            while new.lower() in taken: new = '%s_%d' % (name, i); i += 1
            taken.add(new.lower()); m.setp(d, 'targetname', new)
            for e, cn in list(m.all_conns()):
                o, t, inp, p, dl, times = m.conn_tuple(cn)
                if t.lower() == name.lower(): m.add_conn(e, o, new, inp, p, dl, times)
            name = new
        o = m.origin(d)
        if m.cls(d) == 'func_door':
            b = m.bounds(d); o = [(b[0][i] + b[1][i]) / 2 for i in range(3)]
        vis = m.new_entity('func_brush', m.origin(d), {'targetname': name + '_vis', 'parentname': name, 'Solidity': '1', 'solidbsp': '0',
                                                     'spawnflags': '2', 'StartDisabled': '0', 'rendermode': m.P(d, 'rendermode', 'kRenderNormal') or 'kRenderNormal',
                                                     'renderamt': m.P(d, 'renderamt', '255') or '255', 'rendercolor': m.P(d, 'rendercolor', '255 255 255') or '255 255 255',
                                                     'disableshadows': m.P(d, 'disableshadows', '0') or '0'})
        dch = dmx.geta(m.E[d], b'children')
        dch[2] = [x for x in dch[2] if x not in meshes]
        dmx.geta(m.E[vis], b'children')[2].extend(meshes)
        dch[2].append(box(m, tm, tnode, [o[0] - 1, o[1] - 1, o[2] - 1], [o[0] + 1, o[1] + 1, o[2] + 1], NODRAW))
        done.append(name)
    c.log.append('doorsolid: %d doors flagged Non-solid to Player (solid in CS2): meshes moved to never-solid func_brush <door>_vis parented to the door, '
                 'door left with a 2-unit nodraw cube on its hinge: %s' % (len(done), ', '.join(sorted(set(done)))))
    return len(done)
