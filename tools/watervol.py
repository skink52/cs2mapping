"""Stage D pass `water`: CS:GO water -> CS2 func_water + underwater post-processing (skink52's water rules, 29 Oct 2026).

CS2 only treats water as water (swimming, sounds, splashes) inside a func_water entity; a world mesh with a water-looking
material is just a floor you can't stand in (ttt_minecraft). For every water mesh (a material with "water" in its name) in the world
or in a func_water_analog:
- touching water meshes are grouped and each group becomes one func_water (func_water_analog -> func_water, keeping its name);
- a group deep enough to put a player's eyes under (more than 64 u) gets an underwater post_processing_volume over its footprint, from
  16 u under the bottom to UNDER u below the surface (the volume tests the player's feet, so the effect starts when the eyes go
  under): lighting/postprocessing/postprocess_filmic_underwater.vpost (copied from ba_jail_seaside), master 0, exposure 0-0.3,
  fade 0.1, as on ba_jail_seaside;
- a master post_processing_volume is added (stock lighting/postprocessing/filmic_default.vpost) if the map has none.
"""
import os
import dmx
import vmapedit as V

UNDER = 80.0
VPOST = 'lighting/postprocessing/postprocess_filmic_underwater.vpost'
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'box_template.vmap')


def is_water(mat): return 'water' in mat and not mat.startswith('materials/tools/')


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
    par = m.parent_of()
    meshes = []                                   # (node, parent, bounds)
    for n, _ in m.walk():
        if m.type(n) != b'CMapMesh': continue
        mats = [x.decode() for x in m.g(m.g(n, b'meshData'), b'materials') or []]
        if not any(is_water(x) for x in mats): continue
        p = par.get(n)
        if p is None: continue
        pt = m.type(p)
        if pt == b'CMapEntity' and m.cls(p) not in ('func_water_analog', 'func_water'): continue     # water on a door, train, ... left alone
        meshes.append((n, p, m.bounds(n)))
    if not meshes: return 0
    # group touching meshes (union-find on bounds expanded by 1 u)
    idx = list(range(len(meshes)))
    def find(i):
        while idx[i] != i: idx[i] = idx[idx[i]]; i = idx[i]
        return i
    for i in range(len(meshes)):
        for j in range(i + 1, len(meshes)):
            a, b = meshes[i][2], meshes[j][2]
            if all(a[0][k] <= b[1][k] + 1 and b[0][k] <= a[1][k] + 1 for k in range(3)): idx[find(i)] = find(j)
    groups = {}
    for i in range(len(meshes)): groups.setdefault(find(i), []).append(meshes[i])
    tm = V.Map(TEMPLATE); tnode = tm.children(tm.world)[0]
    nwater = npp = 0
    for g in groups.values():
        lo = [min(b[0][k] for _, _, b in g) for k in range(3)]; hi = [max(b[1][k] for _, _, b in g) for k in range(3)]
        owners = {p for _, p, _ in g if m.type(p) == b'CMapEntity'}
        if owners:
            ent = sorted(owners)[0]
            if m.cls(ent) == 'func_water_analog':
                m.setp(ent, 'classname', 'func_water')
                for k in ('WaveHeight', 'startposition', 'speed', 'movedistance', 'movedir'): m.delp(ent, k)
        else:
            ent = m.new_entity('func_water', [(lo[k] + hi[k]) / 2 for k in range(3)], {})
        for n, p, _ in g:
            if p == ent: continue
            src = dmx.geta(m.E[p], b'children'); src[2] = [x for x in src[2] if x != n]
            dmx.geta(m.E[ent], b'children')[2].append(n)
            if m.type(p) == b'CMapEntity' and not any(m.type(x) == b'CMapMesh' for x in m.children(p)): m.remove_node(p)
        nwater += 1
        depth = hi[2] - lo[2]
        if depth > 64:
            top = max(hi[2] - UNDER, lo[2] + 8)
            mn, mx = [lo[0], lo[1], lo[2] - 16], [hi[0], hi[1], top]
            pp = m.new_entity('post_processing_volume', [(mn[k] + mx[k]) / 2 for k in range(3)], {
                'StartDisabled': '0', 'spawnflags': '4097', 'postprocessing': VPOST, 'master': '0', 'minexposure': '0', 'maxexposure': '0.3',
                'enableexposure': '1', 'exposurespeedup': '1', 'exposurespeeddown': '1', 'fadetime': '0.1'})
            dmx.geta(m.E[pp], b'children')[2].append(box(m, tm, tnode, mn, mx, b'materials/tools/toolsnodraw.vmat'))
            npp += 1
    master = [e for e in m.by_class('post_processing_volume') if (m.P(e, 'master', '0') or '0') == '1']
    if not master:
        e = m.new_entity('post_processing_volume', [0, 0, 0], {'StartDisabled': '0', 'spawnflags': '4097', 'master': '1',
            'postprocessing': 'lighting/postprocessing/filmic_default.vpost', 'minexposure': '1.0', 'maxexposure': '1.0', 'enableexposure': '1',
            'exposurespeedup': '1', 'exposurespeeddown': '1', 'fadetime': '1.0'})
        dmx.geta(m.E[e], b'children')[2].append(box(m, tm, tnode, [-8, -8, -8], [8, 8, 8], b'materials/tools/toolsnodraw.vmat'))
    c.needs_underwater_vpost = npp > 0
    c.log.append('water: %d water meshes -> %d func_water; %d underwater post_processing_volumes (%s, top %g u below the surface); %s'
                 % (len(meshes), nwater, npp, VPOST, UNDER, 'master post_processing_volume already there' if master else 'master post_processing_volume added (filmic_default)'))
    return nwater
