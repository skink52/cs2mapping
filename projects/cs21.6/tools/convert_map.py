"""Builds maps/mg_cs16.vmap: CS 1.6 de_dust2 and de_train side by side in one CS2 map.

usage: python3 tools/convert_map.py <template.vmap> <cstrike dir> <valve dir> <addon out dir> [out.vmap]

  template.vmap  the addon's Hammer template map (keeps its lighting entities, team intro, end of match, nav settings)
  cstrike dir    Half-Life/cstrike (maps, WADs, gfx/env skies); valve dir: Half-Life/valve (halflife.wad, decals.wad)

Writes the vmap, the 1.6 textures as materials under materials/cs16, the two skies, and _gen/maps.json (spawns,
bomb sites and buy zones per map, read by the game script build).
Nothing from the 1.6 install goes into the repo: everything lands in the addon output folder.
"""
import re, os, sys, json, math, subprocess
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'goldsrc'))
import dmx9
from dmx9 import T_STRING, T_VEC3, T_QANGLE
from bsp import BSP
import textures as TX
import vishints as VH
import meshlib as ML
from meshlib import Face, polymesh, mapmesh, entity, box_faces

TEMPLATE, CSTRIKE, VALVE, OUT = sys.argv[1:5]
OUT_VMAP = sys.argv[5] if len(sys.argv) > 5 else os.path.join(OUT, 'maps', 'mg_cs16.vmap')
BUILD = os.path.join(os.path.dirname(HERE), 'build')
os.makedirs(BUILD, exist_ok=True)

MAPS = [
    {'key': 'dust2', 'bsp': 'de_dust2', 'offset': (0, 0, 0), 'title': 'de_dust2', 'credit': 'Dust II by David Johnston (DaveJ)'},
    {'key': 'train', 'bsp': 'de_train', 'offset': (5632, 0, 0), 'title': 'de_train', 'credit': 'Train by Chris Auty'},
    {'key': 'nuke', 'bsp': 'de_nuke', 'offset': (2048, -5120, 0), 'title': 'de_nuke', 'credit': 'Nuke by Jo Bieg'},
]
ENV_DIRS = None    # set below once the install folders are known
SPAWNS_PER_TEAM = 32
CHUNK = 1024
GROUP = 'cs16_gen'                 # vis group of everything this script adds (re-running replaces only these)
TOOLS = {'trigger': 'materials/tools/toolstrigger.vmat', 'skybox': 'materials/tools/toolsskybox.vmat',
         'playerclip': 'materials/tools/toolsplayerclip.vmat', 'clip': 'materials/tools/toolsclip.vmat',
         'ladder': 'materials/tools/toolsinvisibleladder.vmat', 'nodraw': 'materials/tools/toolsnodraw.vmat'}

ENV_DIRS = [os.path.join(CSTRIKE, 'gfx', 'env'), os.path.join(VALVE, 'gfx', 'env')]
wads = [os.path.join(CSTRIKE, f) for f in sorted(os.listdir(CSTRIKE)) if f.lower().endswith('.wad')]
wads += [os.path.join(VALVE, f) for f in ('halflife.wad', 'decals.wad', 'liquids.wad', 'xeno.wad')]
pool = TX.TexturePool(wads)
written = {}


def mat_for(name):
    k = name.lower()
    if k in TX.INVISIBLE: return TOOLS['clip']
    if k not in written: written[k] = pool.write(k, OUT)
    return written[k]


# ------------------------------------------------------------------ template
dm = dmx9.DMX.load(TEMPLATE)
root = dm.root
world = root['world']
children = world['children']


def all_nodes(e, out):
    for c in e.get('children', []) or []:
        out.append(c); all_nodes(c, out)
    return out


ML.set_first_node(max([n.get('nodeID', 0) for n in all_nodes(world, [])] + [world['nodeID']]) + 10)


def cls_of(c):
    return c['entity_properties']['classname'] if c.type == 'CMapEntity' else None


DROP = {'func_bomb_target', 'func_buyzone', 'point_worldtext', 'info_player_terrorist', 'info_player_counterterrorist',
        'env_soundscape', 'env_combined_light_probe_volume', 'visibility_hint', 'light_omni2', 'point_script', 'custom_hud_layout',
        'point_soundevent', 'func_brush', 'func_breakable', 'light_spot', 'info_target'}
keep = []
for c in children:
    if c.type == 'CMapMesh': continue                      # template sample geometry, and our own meshes from a previous run
    if c.type == 'CMapEntity' and cls_of(c) in DROP: continue
    try:
        if c.get('customVisGroup', '') == GROUP: continue   # everything a previous run added (the template can be our own output)
    except Exception:
        pass
    keep.append(c)
children[:] = keep
if 'visbility' in root.attrs:
    root['visbility']['nodes'] = []; root['visbility']['hiddenFlags'] = []
if 'nodeInstanceData' in root.attrs:
    root['nodeInstanceData'] = []


def find(cls):
    return [c for c in children if cls_of(c) == cls]


def setp(ent, **kv):
    ep = ent['entity_properties']
    for k, v in kv.items():
        k = k.replace('__', '.')
        if k in ep: ep[k] = str(v)
        else: ep.set(k, T_STRING, str(v))


PROBE_PROTO = None
tmpl = dmx9.DMX.load(TEMPLATE)
for c in tmpl.root['world']['children']:
    if cls_of(c) == 'env_combined_light_probe_volume':
        PROBE_PROTO = {k: v[1] for k, v in c['entity_properties'].attrs.items()}
        break


def add(*items):
    for it in items: children.append(it)


# ------------------------------------------------------------------ helpers
def vec(s):
    return np.array([float(x) for x in s.split()[:3]])


def face_uv(b, fi, P, off):
    """texture coords of face corners (P = original 1.6 positions) and the editing axes in the shifted world"""
    f = b.faces[fi]; ti = b.texinfo[f['texinfo']]
    name = b.textures[ti['miptex']][0]
    w, h = pool.size(name)
    s = ti['s'].astype(np.float64); t = ti['t'].astype(np.float64)
    uv = [((np.dot(p, s[:3]) + s[3]) / w, (np.dot(p, t[:3]) + t[3]) / h) for p in P]
    ls, lt = np.linalg.norm(s[:3]) or 1, np.linalg.norm(t[:3]) or 1
    o = np.array(off, np.float64)
    axes = (tuple(s[:3] / ls), s[3] - np.dot(o, s[:3]), 1 / ls, tuple(t[:3] / lt), t[3] - np.dot(o, t[:3]), 1 / lt)
    return uv, axes


def tex_name(b, fi):
    return b.textures[b.texinfo[b.faces[fi]['texinfo']]['miptex']][0].lower()


def face_poly(b, fi, off):
    """vertex loop CCW from the front (BSP stores them clockwise), original and shifted"""
    V = b.face_verts(fi)[::-1]
    return V, V + np.array(off, np.float64)


def model_faces(b, mi):
    m = b.models[mi]
    return range(m['firstface'], m['firstface'] + m['numfaces'])


def faces_for(b, fis, off, override=None, ent=None):
    """faces of a brush model. ent: the 1.6 entity, for its render mode (2 = see-through texture at renderamt)"""
    out = []
    amt = 255
    if ent is not None and ent.get('rendermode') == '2':
        amt = int(float(ent.get('renderamt', '255') or 255))
    for fi in fis:
        name = tex_name(b, fi)
        P0, P = face_poly(b, fi, off)
        if override:
            out.append(Face([tuple(p) for p in P], override))
            continue
        if name in TX.SKIP or name == TX.SKY: continue
        uv, axes = face_uv(b, fi, P0, off)
        mat = mat_for(name)
        if 0 < amt < 255 and mat.startswith(TX.MAT_DIR):
            key = (mat, amt)
            if key not in written: written[key] = TX.write_translucent(OUT, mat, max(24, amt))
            mat = written[key]
        if amt == 0 and ent is not None and ent.get('rendermode') == '2':
            continue        # fully invisible in 1.6
        out.append(Face([tuple(p) for p in P], mat, uv, axes))
    return out


DRAWN_BRUSH = ('func_wall', 'func_illusionary', 'func_breakable', 'func_door', 'func_door_rotating')


def see_through(b, mi, e):
    """1.6 brush entity drawn see-through: masked ({) textures or a translucent render mode"""
    return e.get('rendermode', '0') in ('1', '2', '3', '5') or any(tex_name(b, fi).startswith('{') for fi in model_faces(b, mi))


def mesh_from(faces, physics='default', castshadows=True, islands=False):
    if not faces: return None
    P = np.array([p for f in faces for p in f.loop])
    o = tuple(np.round((P.min(0) + P.max(0)) / 2))
    md = polymesh(faces, o, islands=islands)
    if md is None: return None
    ML.check_mesh(md)
    return mapmesh(md, o, physics=physics, group=GROUP, castshadows=castshadows)


def chunked(faces, size=CHUNK):
    groups = {}
    for f in faces:
        c = np.mean(f.loop, axis=0)
        groups.setdefault((int(c[0] // size), int(c[1] // size)), []).append(f)
    return [groups[k] for k in sorted(groups)]


def rest_origin(b, o, maxdrop=96):
    """1.6 player origin -> resting origin (lowered until the standing hull touches the floor); None if it can't stand"""
    p = np.array(o, np.float64)
    if b.point_contents(p, 1) != -1:
        for dz in range(1, 24):               # a spawn slightly inside the floor: lift it
            q = p + (0, 0, dz)
            if b.point_contents(q, 1) == -1: p = q; break
        else:
            return None
    for _ in range(maxdrop):
        q = p - (0, 0, 1)
        if b.point_contents(q, 1) != -1: return p
        p = q
    return None


def walk_ok(b, a, c, step=8):
    """straight walk from resting origin a to c: hull stays clear and floor stays under it (no drops over 20 units)"""
    d = c - a; n = max(1, int(np.linalg.norm(d[:2]) / step))
    for k in range(1, n + 1):
        p = a + d * (k / n)
        p[2] = max(a[2], c[2]) + 18
        if b.point_contents(p, 1) != -1: return False
        r = rest_origin(b, p, 40)
        if r is None: return False
    return True


def extra_spawns(b, base, others, inside, want):
    """base: [(rest origin, yaw)] of one team. Adds points on a 64-unit grid around them until there are `want`."""
    pts = [np.array(o) for o, _ in base]
    taken = [p.copy() for p in pts] + [np.array(o) for o in others]
    out = list(base)
    centre = np.mean(pts, axis=0)
    cands = []
    for p0, yaw in base:
        for dx in range(-384, 385, 48):
            for dy in range(-384, 385, 48):
                if dx == 0 and dy == 0: continue
                q = np.array(p0) + (dx, dy, 0)
                cands.append((np.linalg.norm(q[:2] - centre[:2]) + 0.2 * math.hypot(dx, dy), q, np.array(p0), yaw))
    cands.sort(key=lambda c: c[0])
    for _, q, p0, yaw in cands:
        if len(out) >= want: break
        r = rest_origin(b, q + (0, 0, 8), 64)
        if r is None or abs(r[2] - p0[2]) > 40: continue
        if any(np.linalg.norm(r[:2] - t[:2]) < 56 and abs(r[2] - t[2]) < 72 for t in taken): continue
        if inside is not None and not inside(r): continue
        if not walk_ok(b, p0, r): continue
        taken.append(r); out.append((tuple(r), yaw))
    return out


def box_of(b, mi, off):
    m = b.models[mi]
    return (np.array(m['mins'], np.float64) + off, np.array(m['maxs'], np.float64) + off)


# ------------------------------------------------------------------ per map
mapdata = []
sky_done = {}
first_env = None
stats = {}
for M in MAPS:
    key, off = M['key'], np.array(M['offset'], np.float64)
    b = BSP(os.path.join(CSTRIKE, 'maps', M['bsp'] + '.bsp'))
    pool.add_bsp(b)
    ws = b.worldspawn
    skyname = ws.get('skyname', 'desert')
    if skyname.lower() not in sky_done:
        sky_done[skyname.lower()] = TX.write_sky(OUT, ENV_DIRS, skyname)
    sky_vmat, moondome = sky_done[skyname.lower()]
    st = stats.setdefault(key, {})
    # ---- world geometry
    world_faces, sky_faces, sky_shell, texlights, vis_polys = [], [], [], [], []
    grid = VH.Grid(b)
    drawn = [fi for fi in model_faces(b, 0) if tex_name(b, fi) not in TX.SKIP]
    # sky faces looking into the inside of a sky brush that no open air can see into: drawn by nobody, but most of the sky
    # surface CS2's vis would have to work through
    unseen_sky = VH.unseen_sky(b, grid, drawn, [fi for fi in drawn if tex_name(b, fi) == TX.SKY])
    for fi in drawn:
        name = tex_name(b, fi)
        P0, P = face_poly(b, fi, off)
        n = b.face_normal(fi)
        if name == TX.SKY:
            if fi in unseen_sky: continue
            sky_faces.append(Face([tuple(p) for p in P], moondome))
            sky_shell.append(Face([tuple(p + n * 1.0) for p in P], TOOLS['skybox']))
            vis_polys.append(P + n)
            continue
        vis_polys.append(P + n)
        uv, axes = face_uv(b, fi, P0, off)
        world_faces.append(Face([tuple(p) for p in P], mat_for(name), uv, axes))
        if '~' in name:
            texlights.append((name, P, b.face_normal(fi)))
    for grp in chunked(world_faces):
        m = mesh_from(grp)
        if m: add(m)
    # sky: each face on its own (the faces left after the unseen ones go would otherwise meet only at corners in places,
    # which Hammer's mesh loader tries to repair on load and crashes)
    for grp in chunked(sky_faces, 4096):
        m = mesh_from(grp, castshadows=False, islands=True)
        if m: add(m)
    for grp in chunked(sky_shell, 4096):
        m = mesh_from(grp, castshadows=False, islands=True)
        if m: add(m)
    st['world faces'] = len(world_faces); st['sky faces'] = '%d (+%d hidden inside sky brushes, left out)' % (len(sky_faces), len(unseen_sky))
    # ---- player clips recovered from the collision hulls
    clip_txt = os.path.join(BUILD, 'clip_%s.txt' % M['bsp'])
    exe = os.path.join(BUILD, 'cliphull')
    if not os.path.exists(exe):
        subprocess.check_call(['gcc', '-O2', '-o', exe, os.path.join(HERE, 'goldsrc', 'cliphull.c')])
    if not os.path.exists(clip_txt):
        subprocess.check_call([exe, os.path.join(CSTRIKE, 'maps', M['bsp'] + '.bsp'), '8', clip_txt])
    boxes = np.loadtxt(clip_txt).reshape(-1, 6)
    clip_faces = []
    for x0, y0, z0, x1, y1, z1 in boxes:
        clip_faces += box_faces(x0 + off[0], y0 + off[1], z0 + off[2], x1 + off[0], y1 + off[1], z1 + off[2], TOOLS['playerclip'])
    for grp in chunked(clip_faces, 2048):
        m = mesh_from(grp, castshadows=False)
        if m:
            m['visexclude'] = 1
            add(m)
    st['clip boxes'] = len(boxes)
    # ---- entities
    spawns = {'T': [], 'CT': []}
    sites, buyzones, buyspots = [], [], []
    lights = []
    env = None
    breakables = {}
    decals = []
    for e in b.entities[1:]:
        cl = e.get('classname', '')
        mdl = e.get('model', '')
        mi = int(mdl[1:]) if mdl.startswith('*') else None
        if cl in ('info_player_start', 'info_player_deathmatch'):
            r = rest_origin(b, vec(e['origin']))
            if r is None: print('WARNING %s spawn %s cannot stand' % (key, e['origin'])); continue
            yaw = float(e.get('angles', '0 0 0').split()[1]) if 'angles' in e else float(e.get('angle', 0))
            spawns['CT' if cl == 'info_player_start' else 'T'].append((tuple(r), yaw))
        elif cl == 'func_wall' and mi:
            fs = faces_for(b, model_faces(b, mi), off, ent=e)
            m = mesh_from(fs)
            if m:
                if see_through(b, mi, e): m['visexclude'] = 1     # fences, grates, glass: must not hide what's behind
                add(m)
        elif cl == 'func_illusionary' and mi:
            fs = faces_for(b, model_faces(b, mi), off, ent=e)
            m = mesh_from(fs)
            if m:
                c = np.array(m['origin'])
                add(entity('func_brush', c, props={'targetname': '', 'Solidity': '1', 'spawnflags': '2', 'renderamt': '255', 'rendercolor': '255 255 255',
                           'disableshadows': '0', 'StartDisabled': '0'}, kids=[m], group=GROUP))
        elif cl == 'func_breakable' and mi:
            fs = faces_for(b, model_faces(b, mi), off, ent=e)
            m = mesh_from(fs)
            if m:
                tn = e.get('targetname', '')
                name = 'cs16_%s_%s' % (key, tn) if tn else ''
                if tn: breakables.setdefault(tn, []).append(name)
                trig_only = int(e.get('spawnflags', '0')) & 1
                add(entity('func_breakable', np.array(m['origin']), props={'targetname': name, 'spawnflags': '1' if trig_only else '0',
                           'health': str(max(1, int(float(e.get('health', '1') or 1)))), 'propdata': '0', 'PerformanceMode': 'PM_NORMAL',
                           'renderamt': '255', 'rendercolor': '255 255 255'}, kids=[m], group=GROUP))
        elif cl in ('func_door', 'func_door_rotating') and mi:
            fs = faces_for(b, model_faces(b, mi), off, ent=e)
            m = mesh_from(fs)
            if m:
                sf16 = int(e.get('spawnflags', '0'))
                tn = e.get('targetname', '')
                sf = 0
                if sf16 & 32: sf |= 32                          # toggle (no auto return)
                if not tn: sf |= 1024 | (0 if sf16 & 256 else 0)  # untargeted 1.6 doors open on touch
                if not tn: sf |= 256                            # and on +use
                props = {'targetname': 'cs16_%s_%s' % (key, tn) if tn else '', 'speed': e.get('speed', '100'), 'wait': e.get('wait', '4'),
                         'lip': e.get('lip', '0'), 'dmg': e.get('dmg', '0'), 'spawnflags': str(sf), 'spawnpos': '0',
                         'renderamt': '255', 'rendercolor': '255 255 255', 'noise1': '', 'noise2': ''}
                if cl == 'func_door':
                    a = e.get('angle')
                    yaw = float(a) if a is not None else float(e.get('angles', '0 0 0').split()[1])
                    props['movedir'] = '-90 0 0' if yaw == -1 else '90 0 0' if yaw == -2 else '0 %g 0' % yaw
                    origin = np.array(m['origin'])
                else:
                    props['distance'] = e.get('distance', '90')
                    if sf16 & 2: props['spawnflags'] = str(sf | 2)
                    origin = vec(e['origin']) + off if 'origin' in e else np.array(m['origin'])
                add(entity(cl, origin, props=props, kids=[m], group=GROUP))
        elif cl == 'trigger_multiple' and mi and e.get('target'):
            door_targets = {x.get('targetname') for x in b.entities if x.get('classname', '').startswith('func_door')}
            if e['target'] in door_targets:
                fs = faces_for(b, model_faces(b, mi), off, override=TOOLS['trigger'])
                m = mesh_from(fs, physics='none', castshadows=False)
                if m:
                    add(entity('trigger_multiple', np.array(m['origin']), props={'targetname': '', 'spawnflags': '1', 'wait': e.get('wait', '1'),
                               'StartDisabled': '0'}, kids=[m], conns=[('OnTrigger', 'cs16_%s_%s' % (key, e['target']), 'Open', '', 0)], group=GROUP))
        elif cl == 'func_ladder' and mi:
            fs = faces_for(b, model_faces(b, mi), off, override=TOOLS['ladder'])
            m = mesh_from(fs, castshadows=False)
            if m:
                m['visexclude'] = 1
                add(m)
        elif cl == 'func_buyzone' and mi:
            lo, hi = box_of(b, mi, off)
            team = 2 if e.get('team') == '1' else 3
            buyzones.append({'team': team, 'mins': lo.tolist(), 'maxs': hi.tolist()})
            fs = faces_for(b, model_faces(b, mi), off, override=TOOLS['trigger'])
            m = mesh_from(fs, physics='none', castshadows=False)
            add(entity('func_buyzone', np.array(m['origin']), props={'targetname': 'cs16_%s_buy_%s' % (key, 't' if team == 2 else 'ct'), 'TeamNum': str(team)},
                       kids=[m], group=GROUP))
        elif cl == 'func_bomb_target' and mi:
            lo, hi = box_of(b, mi, off)
            sites.append({'target': e.get('target', ''), 'mins': lo.tolist(), 'maxs': hi.tolist(), 'mi': mi})
        elif cl == 'light':
            lights.append(('omni', vec(e['origin']) + off, e))
        elif cl == 'light_spot':
            lights.append(('spot', vec(e['origin']) + off, e))
        elif cl == 'light_environment' and env is None:
            env = e
        elif cl == 'infodecal' and e.get('texture'):
            decals.append(e)
    # decals (bomb site marks and the like): a quad on the nearest face, aligned with that face's texture axes
    dfaces = []
    for e in decals:
        O = vec(e['origin']); best = None
        for fi in model_faces(b, 0):
            n = b.face_normal(fi); V = b.face_verts(fi)
            dist = float(np.dot(O - V[0], n))
            if abs(dist) > 12 or (best and abs(dist) >= best[0]): continue
            P = O - n * dist
            inside = True
            for i in range(len(V)):
                ed = V[(i + 1) % len(V)] - V[i]
                if np.dot(np.cross(ed, P - V[i]), n) > 2.0 * np.linalg.norm(ed): inside = False; break
            if inside: best = (abs(dist), fi, P, n)
        if not best: print('WARNING %s decal %s at %s: no surface' % (key, e['texture'], e['origin'])); continue
        _, fi, P, n = best
        tname = e['texture'].lower()
        if ('decal', tname) not in written: written[('decal', tname)] = TX.write_decal(OUT, wads, tname)
        dm_ = written[('decal', tname)]
        if dm_ is None: print('WARNING %s decal %s: no texture' % (key, tname)); continue
        dmat, w_, h_ = dm_
        ti = b.texinfo[b.faces[fi]['texinfo']]
        su = ti['s'][:3].astype(np.float64); sv = ti['t'][:3].astype(np.float64)
        su -= n * np.dot(su, n); sv -= n * np.dot(sv, n)
        su /= np.linalg.norm(su); sv /= np.linalg.norm(sv)
        c = P + n * 0.6 + off
        corners = [c - su * w_ / 2 - sv * h_ / 2, c + su * w_ / 2 - sv * h_ / 2, c + su * w_ / 2 + sv * h_ / 2, c - su * w_ / 2 + sv * h_ / 2]
        uvs = [(0, 0), (1, 0), (1, 1), (0, 1)]
        if np.dot(np.cross(corners[1] - corners[0], corners[2] - corners[0]), n) < 0:
            corners = corners[::-1]; uvs = uvs[::-1]
        dfaces.append(Face([tuple(p) for p in corners], dmat, uvs, None))
    if dfaces:
        m = mesh_from(dfaces, castshadows=False)
        add(entity('func_brush', np.array(m['origin']), props={'targetname': '', 'Solidity': '1', 'spawnflags': '2', 'renderamt': '255',
                   'rendercolor': '255 255 255', 'disableshadows': '1', 'StartDisabled': '0'}, kids=[m], group=GROUP))
    st['decals'] = len(dfaces)
    # bomb site letters: dust2 names them tgt_a / tgt_b; train's lower site is B
    if key == 'dust2':
        for s in sites: s['letter'] = 'A' if s['target'].endswith('a') else 'B'
    else:
        lowest = min(sites, key=lambda s: s['mins'][2])
        for s in sites: s['letter'] = 'B' if s is lowest else 'A'
    sites.sort(key=lambda s: s['letter'])
    for s in sites:
        fs = faces_for(b, model_faces(b, s['mi']), off, override=TOOLS['trigger'])
        m = mesh_from(fs, physics='none', castshadows=False)
        targets = breakables.get(s['target'], [])
        conns = [('BombExplode', t, 'Break', '', 0) for t in sorted(set(targets))]
        conns.append(('BombPlanted', 'cs16_script', 'RunScriptInput', 'Planted_%s_%s' % (key, s['letter']), 0))
        s['name'] = 'cs16_%s_site_%s' % (key, s['letter'].lower())
        add(entity('func_bomb_target', np.array(m['origin']), props={'targetname': s['name'], 'heistbomb': '0', 'bomb_mount_target': '',
                   'bomb_site_designation': '0' if s['letter'] == 'A' else '1', 'bomb_damage_power': '500'}, kids=[m], conns=conns, group=GROUP))
        del s['mi']
    # spawns: fill each team up to SPAWNS_PER_TEAM
    for team, ent_cls in (('T', 'info_player_terrorist'), ('CT', 'info_player_counterterrorist')):
        tz = 2 if team == 'T' else 3
        zones = [z for z in buyzones if z['team'] == tz]
        orig = [np.array(o) for o, _ in spawns[team]]
        if zones:
            def inside(p, zones=zones):
                return any(all(z['mins'][k] - 1 <= p[k] + off[k] <= z['maxs'][k] + 1 for k in range(2)) for z in zones)
        else:
            # 1.6 without func_buyzone: you can buy within 200 units of your team's spawn points
            buyspots.append({'team': tz, 'radius': 200, 'points': [[round(x, 1) for x in (o + off).tolist()] for o in orig]})
            def inside(p, orig=orig):
                return any(np.linalg.norm(p - o) < 190 for o in orig)
        other = [o for o, _ in spawns['CT' if team == 'T' else 'T']]
        before = len(spawns[team])
        spawns[team] = extra_spawns(b, spawns[team], other, inside, SPAWNS_PER_TEAM)
        if len(spawns[team]) < SPAWNS_PER_TEAM:      # not enough room inside the buy zone: allow outside it
            spawns[team] = extra_spawns(b, spawns[team], other, None, SPAWNS_PER_TEAM)
        st['%s spawns' % team] = '%d (+%d)' % (len(spawns[team]), len(spawns[team]) - before)
        for i, (o, yaw) in enumerate(spawns[team]):
            feet = np.array(o) + off - (0, 0, 36)
            add(entity(ent_cls, feet + (0, 0, 1), (0, yaw, 0), {'targetname': 'cs16_%s_%s_%d' % (key, team.lower(), i), 'priority': '0',
                       'enabled': '1'}, group=GROUP))
    # lights
    LB = {'clientSideEntity': '1', 'brightness_units': '1', 'enabled': '1', 'directlight': '1', 'colormode': '0', 'colortemperature': '6600',
          'skirt': '0.1', 'bouncelight': '-1', 'bouncescale': '1.0', 'shape': '0', 'size_params': '2.0 24.0 0.15', 'castshadows': '1',
          'shadowpriority': '-1', 'brightnessscale': '1.0', 'fademindist': '-250', 'fademaxdist': '1250', 'renderdiffuse': '1',
          'renderspecular': '1', 'rendertransmissive': '1', 'indirectlight': '1', 'baked_light_indexing': '1'}
    def light_ent(p, color, intensity, angles=(90, 0, 0), cone=180, inner=180):
        lumens = min(20000.0, 34.0 * intensity)
        rng = float(np.clip(42 * math.sqrt(intensity), 256, 1600))
        props = dict(LB)
        props.update({'targetname': '', 'color': '%d %d %d 255' % tuple(color), 'brightness_lumens': '%.0f' % lumens,
                      'brightness': '%.4f' % (lumens / 2560), 'brightness_legacy': '%.3f' % (lumens / 1000), 'range': '%.0f' % rng,
                      'outer_angle': '%.1f' % cone, 'inner_angle': '%.1f' % inner})
        return entity('light_omni2', p, angles, props, group=GROUP)
    for kind, p, e in lights:
        v = [float(x) for x in e.get('_light', '255 255 255 200').split()]
        col, inten = v[:3], (v[3] if len(v) > 3 else 200)
        if kind == 'omni':
            add(light_ent(p, col, inten))
        else:
            yaw = float(e.get('angles', '0 0 0').split()[1])
            pitch = -float(e.get('pitch', '-90'))
            add(light_ent(p, col, inten, (pitch, yaw, 0), float(e.get('_cone2', 45)), float(e.get('_cone', 30))))
    # texture lights (the compiler's lights.rad): one light per cluster of light-texture faces
    tl = []
    for name, P, n in texlights:
        c = P.mean(0) + n * 10
        area = 0.5 * np.linalg.norm(sum(np.cross(P[i], P[(i + 1) % len(P)]) for i in range(len(P))))
        for t in tl:
            if t[0] == name and np.linalg.norm(t[1] / t[2] - c) < 96:
                t[1] += c * area; t[2] += area; break
        else:
            tl.append([name, c * area, area])
    for name, cs, area in tl:
        col = np.array(pool.average_color(name), np.float64)
        col = col / max(1, col.max()) * 255
        add(light_ent(cs / area, col, min(400.0, 60 + area / 40)))
    st['lights'] = len(lights); st['texture lights'] = len(tl)
    if first_env is None: first_env = env
    # probe volume and vis hints over the map
    mins = np.array(b.models[0]['mins'], np.float64) + off; maxs = np.array(b.models[0]['maxs'], np.float64) + off
    c = (mins + maxs) / 2; h = (maxs - mins) / 2 + 16
    pp = dict(PROBE_PROTO or {})
    pp.update({'targetname': 'cs16_%s_probes' % key, 'box_mins': '%g %g %g' % tuple(-h), 'box_maxs': '%g %g %g' % tuple(h), 'voxel_size': '48.0'})
    pp.pop('classname', None)
    add(entity('env_combined_light_probe_volume', c, props=pp, group=GROUP))
    # vis: Low over every 256-unit cell holding air players can reach or a drawn face; the rest (solid, the void) is left to
    # the Lowest box over everything below. Same resolution as one Low box over the whole map wherever there's anything to see.
    for e in b.entities[1:]:
        mdl = e.get('model', '')
        if mdl.startswith('*') and e.get('classname') in DRAWN_BRUSH:
            vis_polys += [face_poly(b, fi, off)[1] + b.face_normal(fi) for fi in model_faces(b, int(mdl[1:])) if tex_name(b, fi) not in TX.SKIP]
    cells = VH.air_cells(grid, off, [o for t in spawns for o, _ in spawns[t]]) | VH.face_cells(vis_polys)
    hint_boxes = VH.low_boxes(cells)
    for lo, hi in hint_boxes:
        add(entity('visibility_hint', (lo + hi) / 2, props={'hintType': '3', 'box_mins': '%g %g %g' % tuple((lo - hi) / 2),
                   'box_maxs': '%g %g %g' % tuple((hi - lo) / 2)}, group=GROUP))
    st['vis'] = '%d Low boxes, %d cells of 256 units (whole map: %d)' % (len(hint_boxes), len(cells), int(np.prod(np.ceil(2 * h / VH.CELL))))
    sp = spawns['T'][0][0]
    add(entity('point_nav_walkable', np.array(sp) + off - (0, 0, 20), props={'targetname': ''}, group=GROUP))
    bombradius = next((float(x.get('bombradius', 500)) for x in b.entities if x.get('classname') == 'info_map_parameters'), 500.0)
    mapdata.append({'key': key, 'title': M['title'], 'credit': M['credit'], 'offset': off.tolist(), 'bombradius': bombradius,
                    'bounds': [mins.tolist(), maxs.tolist()], 'sky': skyname,
                    'spawns': {t: [[round(x, 1) for x in (np.array(o) + off - (0, 0, 36)).tolist()] + [yaw] for o, yaw in spawns[t]] for t in spawns},
                    'sites': [{k: s[k] for k in ('letter', 'name', 'mins', 'maxs')} for s in sites],
                    'buyzones': buyzones, 'buyspots': buyspots})

# ------------------------------------------------------------------ map-wide entities
allmin = np.min([m['bounds'][0] for m in mapdata], axis=0); allmax = np.max([m['bounds'][1] for m in mapdata], axis=0)
c = (allmin + allmax) / 2; h = (allmax - allmin) / 2 + 512
add(entity('visibility_hint', c, props={'hintType': '9', 'box_mins': '%g %g %g' % tuple(-h), 'box_maxs': '%g %g %g' % tuple(h)}, group=GROUP))
for mb, o in zip(find('cs_minimap_boundary'), [(allmin[0] - 64, allmax[1] + 64, allmax[2] + 64), (allmax[0] + 64, allmin[1] - 64, allmin[2] - 64)]):
    mb['origin'] = tuple(map(float, o))
le = find('light_environment')[0]
v = [float(x) for x in first_env.get('_light', '255 255 128 70').split()]
pitch = -float(first_env.get('pitch', '-60')); yaw = float(first_env.get('angle', first_env.get('angles', '0 0 0').split()[1]))
le['angles'] = (pitch, yaw, 0.0)
le['origin'] = tuple(map(float, np.array(mapdata[0]['bounds'][1]) - (256, 256, 0)))
setp(le, color='255 240 200', brightness='2.6', skycolor='170 200 240', skyintensity='1.0', castshadows='1', directlight='3')
sky = find('env_sky')[0]
setp(sky, skyname=sky_done[mapdata[0]['sky'].lower()][0], brightnessscale='1.0')
sky['origin'] = tuple(map(float, np.array(le['origin']) + (0, 0, 32)))
for f in find('env_cubemap_fog'): f['origin'] = tuple(map(float, np.array(le['origin']) + (0, 64, 0)))
mp = find('info_map_parameters')[0]
setp(mp, targetname='cs16_map_params', buying='3', bombradius='500')
d2 = mapdata[0]
tsp, ctsp = d2['spawns']['T'][0], d2['spawns']['CT'][0]
for e, p in [(find('info_player_start'), tsp), (find('team_select'), tsp), (find('terrorist_team_intro'), tsp),
             (find('counterterrorist_team_intro'), ctsp), (find('end_of_match'), ctsp)]:
    for x in e:
        x['origin'] = (float(p[0]), float(p[1]), float(p[2]))
for x in find('post_processing_volume') + find('point_nav_walkable'):
    x['origin'] = (float(tsp[0]), float(tsp[1]), float(tsp[2]) + 48)
add(entity('point_script', (tsp[0], tsp[1], tsp[2] + 64), props={'targetname': 'cs16_script', 'cs_script': 'maps/scripts/cs16.vjs'}, group=GROUP))
add(entity('custom_hud_layout', (tsp[0] + 32, tsp[1], tsp[2] + 64), props={'targetname': 'cs16_hud', 'layout': 'panorama/layout/custom_game/cs16.vxml',
           'observable': '1'}, group=GROUP))
# the CS2 agents the script puts on players for the 1.6 classes (src/cs2/00_config.js): hidden props far under the first
# map so the models are loaded with the map
cfg_js = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'cs2', '00_config.js')
if os.path.exists(cfg_js):
    mdls = re.findall(r"'((?:characters/models|models/player/cs16)/[^']+\.vmdl)'", open(cfg_js).read())
    mdls += [m.replace('.vmdl', '_pack.vmdl') for m in mdls if m.startswith('models/player/cs16/')]   # with the bomb pack / defuse kit
    for i, mdl in enumerate(mdls):
        add(entity('prop_dynamic', (tsp[0] + 48 * i, tsp[1], tsp[2] - 2400), props={'targetname': 'cs16_cache_%d' % i, 'model': mdl, 'solid': '0',
                   'disableshadows': '1', 'DefaultAnim': ''}, group=GROUP))
# point_soundevents for the script (sound names from _gen/sounds.json when the sound tool has run)
snd_json = os.path.join(OUT, '_gen', 'sounds.json')
if os.path.exists(snd_json):
    for i, name in enumerate(json.load(open(snd_json))):
        add(entity('point_soundevent', (tsp[0] + 64 + 8 * (i % 16), tsp[1] + 8 * (i // 16), tsp[2] + 96),
                   props={'targetname': 'cs16_snd_' + name.split('.', 1)[1], 'soundName': name, 'sourceEntityName': '', 'startOnSpawn': '0',
                          'toLocalPlayer': '0', 'stopOnNew': '0', 'saveAndRestore': '0', 'sourceEntityAttachment': '', 'entityIndexSelection': '0'},
                   group=GROUP))
cam = root['defaultcamera']
cam['position'] = (float(tsp[0]), float(tsp[1]) - 300.0, float(tsp[2]) + 200.0); cam['lookat'] = (float(tsp[0]), float(tsp[1]), float(tsp[2]))

os.makedirs(os.path.dirname(OUT_VMAP), exist_ok=True)
dm.save(OUT_VMAP)
os.makedirs(os.path.join(OUT, '_gen'), exist_ok=True)
json.dump({'maps': mapdata}, open(os.path.join(OUT, '_gen', 'maps.json'), 'w'), indent=1)
print('saved', OUT_VMAP)
print('materials', len(written), 'missing textures', sorted(pool.missing))
for k, v in stats.items(): print(k, v)
