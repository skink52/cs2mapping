"""Read-only gameplay sanity checks of a .vmap: spawns, floors and headroom, sun / sky, light probes, lightmap resolution, nav seeds, buyzones.

  python mapsanity.py <map.vmap> [--json] [--mode classic|minigame|course|story]

Never writes the map. Exit 0 = no errors, 1 = errors. Lines are SEVERITY<tab>CODE<tab>text.

  error    spawn_missing        no enabled info_player_terrorist and no info_player_counterterrorist (nobody can join)
  error    spawn_in_floor       a spawn origin on or under the floor plane (cs2-map-mcp found CS2 rejects it: "all teams are full")
  warning  spawn_low            a spawn origin 0.05-2 u above the floor (imported spawns sit at 0.6-0.8 and play; 8 is the safe height)
  warning  team_missing         one team has no spawns (fine for one-team course maps; not reported with --mode story)
  warning  spawn_not_on_floor   no solid face within 130 u under a spawn (players drop, or spawn in the void)
  warning  spawn_headroom       something solid less than 72 u above a spawn's 32 x 32 footprint (player stuck)
  warning  spawn_too_close      two same-team spawns closer than 32 u (CS2 skips blocked spawns, so the team holds fewer players)
  warning  spawn_count          fewer spawns per team than --min-spawns (default 10 for minigame, 5 otherwise)
  warning  sun_missing          no light_environment (only matters for outdoor / baked light)
  warning  sky_missing          no env_sky and no sky material on any mesh
  warning  probe_missing        no light probe volume (players and weapons render near black)
  warning  probe_uncovered      spawns outside every light probe volume
  info     lightmapres_missing  no toolslightmapres volume (the bake picks a default resolution)
  info     nav_seed_missing     no point_nav_walkable / func_nav_markup WALKABLESEED (bots get no nav mesh)
  info     buyzone_uncovered    a func_buyzone exists but some spawns of its team stand outside every buyzone
  info     bombsite_missing     classic mode only: no func_bomb_target and no hostage entity

Floors and headroom are measured on solid mesh faces: world meshes and brush entities, minus trigger / volume classes, meshes with
physicsType none, and tool materials that don't collide (trigger, lightmapres, hint, skip, nav, fog, areaportal, skybox ...).

The checks follow check_map in cs2-map-mcp by Rmgs123 (github.com/Rmgs123/cs2-map-mcp, MIT), re-implemented on skink52's vmapedit with
thresholds from the ports (spawn spacing 32, minigame spawn counts).
"""
import argparse, collections, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vmapedit as V

NONSOLID_CLASSES = ('trigger_', 'func_buyzone', 'func_bomb_target', 'func_hostage_rescue', 'func_nav_', 'post_processing_volume',
                    'env_', 'func_water', 'func_illusionary', 'fog_volume', 'func_clip_vphysics', 'func_ladder', 'func_precipitation',
                    'func_dustmotes', 'func_smokevolume', 'func_no_defuse', 'func_nav_markup', 'point_')
NONSOLID_MATS = ('toolstrigger', 'toolslightmapres', 'toolshint', 'toolsskip', 'toolsnavattribute', 'toolsfog', 'toolsareaportal',
                 'toolsskybox', 'toolsblocklight', 'toolsoccluder', 'toolsbuyzone', 'toolsaudio', 'toolsnoportal', 'toolsclip_vphysics',
                 'toolsdotted', 'toolsbullet', 'toolsblockbullets', 'toolswater')
PROBE_CLASSES = ('env_light_probe_volume', 'env_combined_light_probe_volume')
SPAWN_CLASSES = {2: 'info_player_terrorist', 3: 'info_player_counterterrorist'}
SEV = {'spawn_missing': 'error', 'spawn_in_floor': 'error', 'spawn_low': 'warning', 'team_missing': 'warning', 'spawn_not_on_floor': 'warning', 'spawn_headroom': 'warning',
       'spawn_too_close': 'warning', 'spawn_count': 'warning', 'sun_missing': 'warning', 'sky_missing': 'warning',
       'probe_missing': 'warning', 'probe_uncovered': 'warning', 'lightmapres_missing': 'info', 'nav_seed_missing': 'info',
       'buyzone_uncovered': 'info', 'bombsite_missing': 'info'}
CELL = 64.0


def _vec(s, default=(0.0, 0.0, 0.0)):
    try:
        p = [float(x) for x in str(s).replace(',', ' ').split()]
        return p[:3] if len(p) >= 3 else list(default)
    except ValueError:
        return list(default)


def _streams(m, md, part):
    pd = m.g(md, part)
    return {m.E[st]['name'].decode('utf-8', 'replace'): m.g(st, b'data') for st in (m.g(pd, b'streams') or [])} if pd is not None else {}


def mesh_faces(m, node):
    """-> [(material, [world xyz, ...])] for every face of a CMapMesh"""
    md = m.g(node, b'meshData')
    if md is None: return []
    dest, nxt = m.g(md, b'edgeVertexIndices') or [], m.g(md, b'edgeNextIndices') or []
    fe = m.g(md, b'faceEdgeIndices') or []
    fdi = m.g(md, b'faceDataIndices') or []
    vdi = m.g(md, b'vertexDataIndices') or []
    mats = [x.decode('utf-8', 'replace') if isinstance(x, (bytes, bytearray)) else str(x) for x in (m.g(md, b'materials') or [])]
    vs = _streams(m, md, b'vertexData')
    pos = next((v for k, v in vs.items() if k.startswith('position')), None)
    if not pos: return []
    fs = _streams(m, md, b'faceData')
    mi = next((v for k, v in fs.items() if k.startswith('materialindex')), None)
    o = m.g(node, b'origin', [0, 0, 0]); ang = m.g(node, b'angles', [0, 0, 0]); sc = m.g(node, b'scales', [1, 1, 1])
    world = [V.xform([p[0] * sc[0], p[1] * sc[1], p[2] * sc[2]], o, ang) for p in pos]
    out = []
    for f, h0 in enumerate(fe):
        loop, h = [], h0
        for _ in range(len(dest) + 1):
            loop.append(world[vdi[dest[h]]] if vdi else world[dest[h]])
            h = nxt[h]
            if h == h0: break
        mat = mats[mi[fdi[f]]] if (mi and fdi and mats and mi[fdi[f]] < len(mats)) else (mats[0] if mats else '')
        out.append((mat, loop))
    return out


def solid_triangles(m, keep_xy=None):
    """triangles of solid faces; keep_xy(set of cells) limits them to those over the given 64-unit cells"""
    tris = []
    def visit(node, owner_cls):
        t = m.type(node)
        if t == b'CMapEntity':
            owner_cls = m.cls(node).lower()
        if t == b'CMapMesh':
            phys = m.g(node, b'physicsType', b'default')
            phys = phys.decode() if isinstance(phys, (bytes, bytearray)) else str(phys)
            if phys.lower() != 'none' and not (owner_cls and owner_cls.startswith(NONSOLID_CLASSES)):
                for mat, loop in mesh_faces(m, node):
                    if any(x in mat.lower() for x in NONSOLID_MATS) or len(loop) < 3: continue
                    for i in range(1, len(loop) - 1):
                        tri = (loop[0], loop[i], loop[i + 1])
                        if keep_xy is not None:
                            x0 = int(math.floor(min(p[0] for p in tri) / CELL)); x1 = int(math.floor(max(p[0] for p in tri) / CELL))
                            y0 = int(math.floor(min(p[1] for p in tri) / CELL)); y1 = int(math.floor(max(p[1] for p in tri) / CELL))
                            if (x1 - x0 + 1) * (y1 - y0 + 1) <= 64:
                                if not any((cx, cy) in keep_xy for cx in range(x0, x1 + 1) for cy in range(y0, y1 + 1)): continue
                            elif not any(x0 <= cx <= x1 and y0 <= cy <= y1 for cx, cy in keep_xy): continue
                        tris.append(tri)
        for c in m.children(node): visit(c, owner_cls)
    visit(m.world, '')
    return tris


def z_at(tri, x, y):
    """z of the triangle's plane at (x, y) when (x, y) is inside its xy projection, else None"""
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = tri
    d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(d) < 1e-9: return None
    l1 = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / d
    l2 = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / d
    l3 = 1 - l1 - l2
    if min(l1, l2, l3) < -1e-6: return None
    return l1 * az + l2 * bz + l3 * cz


def floor_below(tris, p, start=2.0, drop=130.0):
    best = None
    for t in tris:
        z = z_at(t, p[0], p[1])
        if z is not None and z <= p[2] + start and z >= p[2] - drop and (best is None or z > best): best = z
    return best


def ceiling_above(tris, p, foot=18.0, height=72.0):
    """lowest solid surface between step height (18) and head (72) over the 32 x 32 footprint (9 sample columns)"""
    low = None
    for dx in (-15, 0, 15):
        for dy in (-15, 0, 15):
            x, y = p[0] + dx, p[1] + dy
            for t in tris:
                z = z_at(t, x, y)
                if z is not None and p[2] + foot < z < p[2] + height and (low is None or z < low): low = z
    return low


def _box_of(m, e):
    """world box of a volume entity: its mesh bounds, else origin + box_mins / box_maxs"""
    b = m.bounds(e)
    if b: return b
    o = m.origin(e)
    lo = _vec(m.P(e, 'box_mins', '-64 -64 -64')); hi = _vec(m.P(e, 'box_maxs', '64 64 64'))
    return [o[i] + lo[i] for i in range(3)], [o[i] + hi[i] for i in range(3)]


def _inside(p, box, pad=0.0):
    return all(box[0][i] - pad <= p[i] <= box[1][i] + pad for i in range(3))


def check(m, mode='minigame', min_spawns=None):
    found = []
    def add(code, text, e=None):
        f = {'severity': SEV[code], 'code': code, 'text': text}
        if e is not None: f['node'] = m.g(e, b'nodeID'); f['at'] = [round(x, 1) for x in m.origin(e)]
        found.append(f)
    ents = m.entities()
    by_cls = collections.defaultdict(list)
    for e in ents: by_cls[m.cls(e).lower()].append(e)
    min_spawns = min_spawns or (10 if mode == 'minigame' else 5)

    spawns = {team: [(e, m.origin(e)) for e in by_cls[c] if m.P(e, 'enabled', '1') != '0'] for team, c in SPAWN_CLASSES.items()}
    cells = {(int(math.floor((p[0] + dx) / CELL)), int(math.floor((p[1] + dy) / CELL)))
             for team in spawns for _, p in spawns[team] for dx in (-16, 16) for dy in (-16, 16)}
    tris = solid_triangles(m, cells) if cells else []
    buckets = collections.defaultdict(list)
    for t in tris:
        x0 = int(math.floor(min(p[0] for p in t) / CELL)); x1 = int(math.floor(max(p[0] for p in t) / CELL))
        y0 = int(math.floor(min(p[1] for p in t) / CELL)); y1 = int(math.floor(max(p[1] for p in t) / CELL))
        for c in cells:
            if x0 <= c[0] <= x1 and y0 <= c[1] <= y1: buckets[c].append(t)
    def near(p):
        out = {}
        for dx in (-16, 0, 16):
            for dy in (-16, 0, 16):
                for t in buckets.get((int(math.floor((p[0] + dx) / CELL)), int(math.floor((p[1] + dy) / CELL))), ()): out[id(t)] = t
        return list(out.values())

    for team, cls in SPAWN_CLASSES.items():
        sp = spawns[team]
        if not sp:
            other = spawns[5 - team]
            if not other:
                if team == 2: add('spawn_missing', 'no enabled info_player_terrorist or info_player_counterterrorist: nobody can join')
            elif mode != 'story':
                add('team_missing', 'no enabled %s: nobody can join %s (fine for a one-team map)' % (cls, 'T' if team == 2 else 'CT'))
            continue
        if len(sp) < min_spawns:
            add('spawn_count', '%d %s (fewer than %d)' % (len(sp), cls, min_spawns), sp[0][0])
        for e, p in sp:
            ts = near(p)
            fz = floor_below(ts, p)
            if fz is None:
                add('spawn_not_on_floor', '%s at %s: no solid floor within 130 u below' % (cls, ' '.join('%g' % round(x, 1) for x in p)), e)
            elif p[2] - fz < 2.0:
                add('spawn_in_floor' if p[2] - fz < 0.05 else 'spawn_low', '%s at %s: origin %.1f u above the floor at z %g; raise it to %g'
                    % (cls, ' '.join('%g' % round(x, 1) for x in p), p[2] - fz, round(fz, 2), round(fz + 8, 2)), e)
            ceil = ceiling_above(ts, p)
            if ceil is not None:
                add('spawn_headroom', '%s at %s: solid surface %.1f u above the feet (player is 72 tall)' % (cls, ' '.join('%g' % round(x, 1) for x in p), ceil - p[2]), e)
        close = 0
        for i in range(len(sp)):
            for j in range(i + 1, len(sp)):
                if math.dist(sp[i][1][:2], sp[j][1][:2]) < 32 and abs(sp[i][1][2] - sp[j][1][2]) < 72:
                    close += 1
                    if close <= 10:
                        add('spawn_too_close', '%s at %s and %s are %.1f u apart' % (cls, ' '.join('%g' % round(x, 1) for x in sp[i][1]), ' '.join('%g' % round(x, 1) for x in sp[j][1]), math.dist(sp[i][1], sp[j][1])), sp[i][0])

    if not by_cls['light_environment']: add('sun_missing', 'no light_environment')
    sky_mat = any('sky' in mat.lower() for n, _ in m.walk() if m.type(n) == b'CMapMesh' for mat in _mats(m, n))
    if not by_cls['env_sky'] and not sky_mat: add('sky_missing', 'no env_sky and no sky material on any mesh')
    probes = [e for c in PROBE_CLASSES for e in by_cls[c]]
    if not probes:
        add('probe_missing', 'no env_light_probe_volume / env_combined_light_probe_volume: players and weapons render near black')
    else:
        boxes = [_box_of(m, e) for e in probes]
        out = [p for team in spawns for _, p in spawns[team] if not any(_inside(p, b, 1.0) for b in boxes)]
        if out: add('probe_uncovered', '%d of %d spawns are outside every light probe volume (first at %s)' % (len(out), sum(len(v) for v in spawns.values()), ' '.join('%g' % round(x) for x in out[0])))
    if not any('toolslightmapres' in mat.lower() for n, _ in m.walk() if m.type(n) == b'CMapMesh' for mat in _mats(m, n)):
        add('lightmapres_missing', 'no toolslightmapres volume')
    seeds = by_cls['point_nav_walkable'] + [e for e in by_cls['func_nav_markup'] if 'walkableseed' in m.P(e, 'navProperty_NavGen', '').lower()]
    if not seeds: add('nav_seed_missing', 'no point_nav_walkable or func_nav_markup WALKABLESEED: bots get no nav mesh')
    if by_cls['func_buyzone']:
        zones = [(m.P(e, 'TeamNum', '0'), m.bounds(e)) for e in by_cls['func_buyzone']]
        for team, sp in spawns.items():
            boxes = [b for t, b in zones if b and t in ('0', '', str(team))]
            outside = [p for _, p in sp if not any(_inside(p, b, 1.0) for b in boxes)]
            if outside and boxes: add('buyzone_uncovered', '%d %s outside every buyzone of their team' % (len(outside), SPAWN_CLASSES[team]))
    if mode == 'classic' and not by_cls['func_bomb_target'] and not (by_cls['hostage_entity'] or by_cls['info_hostage_spawn']):
        add('bombsite_missing', 'no func_bomb_target and no hostages')
    return found


def _mats(m, n):
    md = m.g(n, b'meshData')
    if md is None: return []
    return [x.decode('utf-8', 'replace') if isinstance(x, (bytes, bytearray)) else str(x) for x in (m.g(md, b'materials') or [])]


def run(path, mode='minigame', min_spawns=None):
    m = V.Map(path)
    found = check(m, mode, min_spawns)
    c = collections.Counter('%s/%s' % (f['severity'], f['code']) for f in found)
    return {'map': os.path.basename(path), 'mode': mode, 'errors': sum(f['severity'] == 'error' for f in found),
            'warnings': sum(f['severity'] == 'warning' for f in found), 'counts': dict(sorted(c.items())), 'findings': found}


def main(argv=None):
    ap = argparse.ArgumentParser(description='Read-only gameplay sanity checks of a .vmap')
    ap.add_argument('vmap'); ap.add_argument('--json', action='store_true')
    ap.add_argument('--mode', default='minigame', choices=['classic', 'minigame', 'course', 'story'])
    ap.add_argument('--min-spawns', type=int)
    a = ap.parse_args(argv)
    try:
        res = run(a.vmap, a.mode, a.min_spawns)
    except (OSError, ValueError, AssertionError, StopIteration) as ex:
        print('cannot read %s: %s' % (a.vmap, ex), file=sys.stderr); return 2
    if isinstance(res, dict):
        # a read of the .vmap file only: it finds problems, it cannot show the map works (docs/reference/compatibility.md)
        res.setdefault('level', 'untested'); res.setdefault('manual_check_required', True); res.setdefault('checked', 'the .vmap file, offline')
    if a.json: print(json.dumps(res, indent=1))
    else:
        for f in res['findings']: print('%s\t%s\t%s' % (f['severity'], f['code'], f['text']))
        print('# %s (%s): %d errors, %d warnings; %s' % (res['map'], res['mode'], res['errors'], res['warnings'],
                                                       ', '.join('%s %d' % kv for kv in res['counts'].items()) or 'clean'))
    return 1 if res['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
