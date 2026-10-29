"""Stage D pass `probefill`: env_combined_light_probe_volumes over the whole play space.

Players, weapons, viewmodels, doors and other moving brushes take their light from probe volumes only. A map with probe volumes just
around a few static brushes (stage D `probecover`) leaves players black everywhere else (ttt_minecraft: hands and weapons almost
unlit). Play space = clusters of spawns, teleport targets, weapons, lights and movers (linked within LINK units), each boxed with padding
and cut into tiles of at most TILE units (no overlap, no edge fade between tiles). Existing volumes are kept (probecover's ones give static
brushes finer, even lighting, voxel 32) and get Priority High (indoor_outdoor_level 1) so they win over the tiles (Normal, 0): per Valve's
wiki the highest-priority volume containing an object lights it; volumes don't blend.
"""
import numpy as np

LINK = 1536.0
TILE = 2048.0
PAD_XY, PAD_DOWN, PAD_UP = 192.0, 64.0, 320.0
CLASSES = ('info_player_terrorist', 'info_player_counterterrorist', 'info_player_start', 'info_teleport_destination', 'point_teleport',
           'light_omni2', 'light_spot', 'light_barn', 'func_door', 'func_door_rotating', 'func_button', 'func_physbox', 'trigger_teleport')


def _clusters(P):
    n = len(P); lab = list(range(n))
    def f(i):
        while lab[i] != i: lab[i] = lab[lab[i]]; i = lab[i]
        return i
    for i in range(n):
        d = np.abs(P[i + 1:] - P[i]).max(1)
        for j in np.nonzero(d < LINK)[0] + i + 1:
            a, b = f(i), f(j)
            if a != b: lab[a] = b
    groups = {}
    for i in range(n): groups.setdefault(f(i), []).append(i)
    return [P[g] for g in groups.values()]


def run(m, c):
    pts = [m.origin(e) for e in m.entities() if (m.P(e, 'classname') or '').startswith('weapon_') or m.P(e, 'classname') in CLASSES]
    P = np.array([p for p in pts if p], float)
    tiles = []
    for g in _clusters(P):
        lo = g.min(0) - [PAD_XY, PAD_XY, PAD_DOWN]; hi = g.max(0) + [PAD_XY, PAD_XY, PAD_UP]
        nx, ny = int(np.ceil((hi[0] - lo[0]) / TILE)), int(np.ceil((hi[1] - lo[1]) / TILE))
        xs = np.linspace(lo[0], hi[0], nx + 1); ys = np.linspace(lo[1], hi[1], ny + 1)
        for i in range(nx):
            for j in range(ny):
                tiles.append((np.array([xs[i], ys[j], lo[2]]), np.array([xs[i + 1], ys[j + 1], hi[2]])))
    kept = 0
    for e in m.by_class('env_combined_light_probe_volume'):
        m.setp(e, 'indoor_outdoor_level', '1'); m.delp(e, 'priority'); kept += 1
    for a, b in tiles:
        o = (a + b) / 2; size = b - a
        vox = 64.0 if size.prod() > 1.5e9 else 48.0
        props = dict(StartDisabled=0, cubemaptexture='', bakenearz='2.0', bakefarz='4096.0', lightgroup='', moveable=0, lightprobetexture='',
                     box_mins='%f %f %f' % tuple(a - o), box_maxs='%f %f %f' % tuple(b - o), voxel_size='%.1f' % vox, flood_fill=1, voxelize=1,
                     light_probe_volume_from_cubemap=0, storage=-1, indoor_outdoor_level=0, edge_fade_dists='0 0 0', clientSideEntity=1)
        m.new_entity('env_combined_light_probe_volume', o.tolist(), props)
    c.log.append('probefill: %d light probe volumes over the play space (%d entity clusters, tiles <= %d u, Priority Normal), %d existing volumes kept at Priority High (indoor_outdoor_level 1): %s'
                 % (len(tiles), len(_clusters(P)), TILE, kept, '; '.join('%s..%s' % (a.round().astype(int).tolist(), b.round().astype(int).tolist()) for a, b in tiles)))
    return len(tiles)


# ---------------------------------------------------------------- detail: finer nested volumes where people stand
CELL = 128.0          # floor/ceiling grid
BLOCK = 512.0         # detail volumes are cut on this xy grid; height spans merged per block, so no overlap within a priority
VOX_OUT, VOX_IN = 32.0, 24.0
PRI_TILE, PRI_OUT, PRI_IN, PRI_OLD = -1, 0, 1, 2


def _solid_faces(m):
    from lighting import mesh_polys
    out = []
    def walk(n):
        for ch in m.children(n):
            t = m.type(ch)
            if t == b'CMapMesh':
                for mat, loop in mesh_polys(m, ch):
                    if '/tools/' in mat or 'moondome' in mat or 'skybox' in mat: continue
                    out.append(np.array(loop, float))
            elif t == b'CMapGroup': walk(ch)
            elif t == b'CMapEntity':
                cn = m.P(ch, 'classname') or ''
                if cn in ('func_brush', 'func_breakable', 'func_detail', 'func_wall') or cn.startswith('func_door'): walk(ch)
    walk(m.world)
    return out


def tiles_of(m):
    """the play tiles probefill added (voxel 48/64, no edge fade) as (mins, maxs)"""
    out = []
    for e in m.by_class('env_combined_light_probe_volume'):
        if m.P(e, 'edge_fade_dists') == '0 0 0' and m.P(e, 'voxel_size') in ('48.0', '64.0'):
            o = np.array(m.origin(e)); out.append((o + [float(x) for x in m.P(e, 'box_mins').split()], o + [float(x) for x in m.P(e, 'box_maxs').split()]))
    return out


def detail(m, c, tiles):
    """finer volumes over the walkable floors inside the play tiles: voxel 32 outdoors, 24 under a ceiling (within 384 u above the floor).
    Priority (indoor_outdoor_level): tiles Low (-1) < outdoor detail Normal (0) < indoor detail High (1) < earlier small volumes Highest (2)."""
    floors = {}; ceils = {}
    for P in _solid_faces(m):
        n = np.cross(P[1] - P[0], P[2] - P[0]); ln = np.linalg.norm(n)
        if ln < 1e-6 or abs(n[2] / ln) < 0.7: continue
        lo, hi = P.min(0), P.max(0)
        tgt = floors if n[2] > 0 else ceils
        for ix in range(int(np.floor(lo[0] / CELL)), int(np.floor((hi[0] - 0.01) / CELL)) + 1):
            for iy in range(int(np.floor(lo[1] / CELL)), int(np.floor((hi[1] - 0.01) / CELL)) + 1):
                tgt.setdefault((ix, iy), []).append(float(P[:, 2].mean()))
    def in_tiles(x, y, z): return any(a[0] <= x <= b[0] and a[1] <= y <= b[1] and a[2] <= z <= b[2] for a, b in tiles)
    spans = {}
    for (ix, iy), zs in floors.items():
        x, y = (ix + .5) * CELL, (iy + .5) * CELL
        cz = sorted(ceils.get((ix, iy), []))
        for fz in set(round(z) for z in zs):
            if not in_tiles(x, y, fz): continue
            above = [z for z in cz if fz + 64 < z <= fz + 384]
            indoor = bool(above)
            top = min(above) if indoor else fz + 160
            spans.setdefault((indoor, int(np.floor(x / BLOCK)), int(np.floor(y / BLOCK))), []).append((fz - 16, top, x, y))
    boxes = []
    for (indoor, _, _), sp in spans.items():
        sp.sort(); cur = None
        for z0, z1, x, y in sp:
            if cur and z0 <= cur[1][2]:
                cur[0] = [min(cur[0][0], x - CELL / 2), min(cur[0][1], y - CELL / 2), cur[0][2]]
                cur[1] = [max(cur[1][0], x + CELL / 2), max(cur[1][1], y + CELL / 2), max(cur[1][2], z1)]
            else:
                if cur: boxes.append((indoor, cur))
                cur = [[x - CELL / 2, y - CELL / 2, z0], [x + CELL / 2, y + CELL / 2, z1]]
        if cur: boxes.append((indoor, cur))
    for e in m.by_class('env_combined_light_probe_volume'):
        m.setp(e, 'indoor_outdoor_level', str(PRI_TILE if (m.P(e, 'indoor_outdoor_level') or '0') == '0' else PRI_OLD))
    nprobe = {True: 0, False: 0}; nvol = {True: 0, False: 0}
    for indoor, (a, b) in boxes:
        a = np.array(a); b = np.array(b); o = (a + b) / 2; vox = VOX_IN if indoor else VOX_OUT
        props = dict(StartDisabled=0, cubemaptexture='', bakenearz='2.0', bakefarz='4096.0', lightgroup='', moveable=0, lightprobetexture='',
                     box_mins='%f %f %f' % tuple(a - o), box_maxs='%f %f %f' % tuple(b - o), voxel_size='%.1f' % vox, flood_fill=1, voxelize=1,
                     light_probe_volume_from_cubemap=0, storage=-1, indoor_outdoor_level=PRI_IN if indoor else PRI_OUT,
                     edge_fade_dists='0 0 0', clientSideEntity=1)
        m.new_entity('env_combined_light_probe_volume', o.tolist(), props)
        nvol[indoor] += 1; nprobe[indoor] += int(np.prod(np.ceil((b - a) / vox)))
    c.log.append('probefill detail: %d outdoor volumes (voxel %d, Priority Normal, ~%d probes) and %d indoor volumes (voxel %d, Priority High, ~%d probes) over the '
                 'walkable floors; play tiles set to Low, earlier small volumes to Highest' % (nvol[False], VOX_OUT, nprobe[False], nvol[True], VOX_IN, nprobe[True]))
