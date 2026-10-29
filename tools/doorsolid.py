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


def hinge_box(m, d, panel_bounds):
    """2-unit cube for a door's hinge, pushed 2 units away from the panel so it sits inside the frame instead of the doorway
    (ttt_minecraft: a cube centred on the hinge stuck 1-3 units into a 36-unit doorway and snagged players)"""
    o = m.origin(d)
    if m.cls(d) == 'func_door' or not panel_bounds:
        if m.cls(d) == 'func_door' and panel_bounds:
            b = panel_bounds; o = [(b[0][i] + b[1][i]) / 2 for i in range(3)]
        return [o[0] - 1, o[1] - 1, o[2] - 1], [o[0] + 1, o[1] + 1, o[2] + 1]
    ctr = [(panel_bounds[0][i] + panel_bounds[1][i]) / 2 for i in range(2)]
    dx, dy = ctr[0] - o[0], ctr[1] - o[1]; ln = (dx * dx + dy * dy) ** 0.5 or 1.0
    cx, cy = o[0] - 2 * dx / ln, o[1] - 2 * dy / ln
    return [cx - 1, cy - 1, o[2] - 1], [cx + 1, cy + 1, o[2] + 1]


def rebury(m, c):
    """maps already through doorsolid: move each door's hinge cube into the frame (see hinge_box)"""
    n = 0
    for d in m.by_class('func_door_rotating'):
        vis = [e for e in m.by_class('func_brush') if m.name(e) == (m.name(d) or '#') + '_vis']
        cubes = [ch for ch in m.children(d) if m.type(ch) == b'CMapMesh']
        if not vis or len(cubes) != 1: continue
        mn, mx = hinge_box(m, d, m.bounds(vis[0]))
        md = m.g(cubes[0], b'meshData')
        dmx.set_(m.E[cubes[0]], b'origin', dmx.T_V3, [0.0, 0.0, 0.0])
        for st in m.g(m.g(md, b'vertexData'), b'streams'):
            if m.E[st]['name'].startswith(b'position'):
                a = dmx.geta(m.E[st], b'data'); pts = a[2]
                ctr = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
                a[2] = [[mx[k] if p[k] > ctr[k] else mn[k] for k in range(3)] for p in pts]
        n += 1
    c.log.append('doorsolid: %d door hinge cubes moved 2 units into the door frame (out of the doorway)' % n)
    return n


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
        pb = m.bounds(d)
        vis = m.new_entity('func_brush', m.origin(d), {'targetname': name + '_vis', 'parentname': name, 'Solidity': '1', 'solidbsp': '0',
                                                     'spawnflags': '2', 'StartDisabled': '0', 'rendermode': m.P(d, 'rendermode', 'kRenderNormal') or 'kRenderNormal',
                                                     'renderamt': m.P(d, 'renderamt', '255') or '255', 'rendercolor': m.P(d, 'rendercolor', '255 255 255') or '255 255 255',
                                                     'disableshadows': m.P(d, 'disableshadows', '0') or '0'})
        dch = dmx.geta(m.E[d], b'children')
        dch[2] = [x for x in dch[2] if x not in meshes]
        dmx.geta(m.E[vis], b'children')[2].extend(meshes)
        mn, mx = hinge_box(m, d, pb)
        dch[2].append(box(m, tm, tnode, mn, mx, NODRAW))
        done.append(name)
    c.log.append('doorsolid: %d doors flagged Non-solid to Player (solid in CS2): meshes moved to never-solid func_brush <door>_vis parented to the door, '
                 'door left with a 2-unit nodraw cube on its hinge: %s' % (len(done), ', '.join(sorted(set(done)))))
    return len(done)
