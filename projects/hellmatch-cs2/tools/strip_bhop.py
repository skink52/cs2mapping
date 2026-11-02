"""One-off (17 Oct): takes the lobby bhop minigame out of Zach's map and puts the lobby room back to its original size.

usage: strip_bhop.py <in.vmap> <out.vmap> <addon_out_dir>

Removes: every entity named bhop*, the trigger_teleports that send players to bhop*, the bhop platforms and their
player clips, the course walls, ladder, trigger leftovers and the finish platform (all in the lobby extension east of
x=768), the invisibility-sphere and tree props out there, the small jump-test block by the west wall, and the
sv_bhop_time_window command from logic_auto. Keeps everything else (torches, logic_auto's other settings, light,
nav data, the booth and cache rooms).
"""
import os, sys, math
sys.path.insert(0, os.path.dirname(__file__))
import dmx
from vmaplib import *
import vmaplib

SRC, DST, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
d = dmx.DMX.load(SRC)
vmaplib.init(d, OUT)
kids = d.root.get('world').attr('children')

def bbox(k):
    md = k.get('meshData'); o = k.get('origin'); ang = k.get('angles') or (0, 0, 0)
    pos = [s.get('data') for s in md.get('vertexData').get('streams') if (s.get('name') or s.name).startswith('position')][0]
    yaw = math.radians(ang[1]); c, s = math.cos(yaw), math.sin(yaw)
    w = [(p[0] * c - p[1] * s + o[0], p[0] * s + p[1] * c + o[1], p[2] + o[2]) for p in pos]
    return [min(v[i] for v in w) for i in range(3)], [max(v[i] for v in w) for i in range(3)]

LOBBY_Z = (-12100, -11500)
removed = {}
def drop(k, why):
    removed[why] = removed.get(why, 0) + 1

kept = []
lobby_room = None
for k in kids[2]:
    if k.get('customVisGroup', '') == 'fdm_env':
        kept.append(k); continue
    if k.type == 'CMapEntity':
        ep = k.get('entity_properties'); cls = ep.get('classname'); name = ep.get('targetname') or ''
        o = k.get('origin')
        if 'bhop' in name: drop(k, cls + ' (bhop*)'); continue
        if cls == 'trigger_teleport' and (ep.get('target') or '').startswith('bhop'): drop(k, 'trigger_teleport -> bhop'); continue
        if cls == 'prop_static' and (ep.get('model') or '').startswith('models/fdm/spr/') and o[0] > 768 and LOBBY_Z[0] < o[2] < LOBBY_Z[1]:
            drop(k, 'prop_static in the bhop area'); continue
        if cls == 'logic_auto':
            cd = k.attr('connectionsData')
            before = len(cd[2])
            cd[2] = [c for c in cd[2] if 'bhop' not in str(dict((a[0], a[2]) for a in c.attrs).get('overrideParam', ''))]
            if len(cd[2]) != before: removed['logic_auto bhop command'] = before - len(cd[2])
        kept.append(k); continue
    if k.type == 'CMapMesh':
        mn, mx = bbox(k)
        if LOBBY_Z[0] < mn[2] and mx[2] < LOBBY_Z[1]:
            if mn[0] < -760 and mx[0] > 1000 and mx[1] - mn[1] > 1500:
                lobby_room = k; continue                   # the stretched lobby room: rebuilt below
            if mn[0] >= 700: drop(k, 'mesh in the bhop area'); continue
            if mx[0] - mn[0] < 40 and mx[1] - mn[1] < 40 and mx[2] - mn[2] <= 40 and mn[0] < -600:
                drop(k, 'small jump-test block'); continue
        kept.append(k); continue
    kept.append(k)

# lobby room back to 1536 x 1536 x 384, with the textures Zach chose (lobby_ceil on the floor and ceiling)
assert lobby_room is not None, 'lobby room not found'
WALL, CEIL = 'materials/fdm/lobby_wall.vmat', 'materials/fdm/lobby_ceil.vmat'
x0, x1, y0, y1, z0, z1 = -768, 768, -768, 768, -12000, -11616
v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
faces = [[0, 1, 2, 3], [4, 7, 6, 5], [0, 4, 5, 1], [2, 6, 7, 3], [1, 5, 6, 2], [3, 7, 4, 0]]
room = mesh_node(polymesh(v, faces, [CEIL, CEIL, WALL, WALL, WALL, WALL]), '', attach=False)
kept.insert(kids[2].index(lobby_room) if lobby_room in kids[2] else 0, room)
kids[2] = kept

left = [k for k in kids[2] if k.type == 'CMapEntity' and 'bhop' in str([a[2] for a in k.get('entity_properties').attrs])]
assert not left, 'still references bhop: %d' % len(left)
d.elements = [d.root]
d.save(DST)
for why, n in sorted(removed.items()): print('  removed %3d  %s' % (n, why))
print('lobby room rebuilt at 1536 x 1536; %d nodes kept -> %s' % (len(kids[2]), DST))
