"""Writes every FreeDM entity and the lobby rooms straight into the user's Hammer map (binary DMX .vmap).

usage: vmap.py <template.vmap> <out.vmap> <addon_out_dir>

The template is the user's own Hammer map. Its root, world settings and nav settings are kept;
Hammer's sample entities and the default box mesh are replaced with FreeDM content.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
import dmx
from vmaplib import *
import vmaplib

TEMPLATE, OUTPATH, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
SCRIPT_PATH = 'maps/scripts/freedm.vjs'
HUD_PATH = 'panorama/layout/custom_game/freedm.vxml'

props = json.load(open(os.path.join(OUT, '_gen/props.json')))
sprites = json.load(open(os.path.join(OUT, '_gen/sprite_models.json')))
SOUNDS = [l.split('"')[1][4:] for l in open(os.path.join(OUT, 'soundevents/soundevents_addon.vsndevts'))
          if l.strip().startswith('"fdm.') and 'base' not in l]

d = dmx.DMX.load(TEMPLATE)
root = d.root
world = root.get('world')
vmaplib.init(d, OUT)

WALL, FLOOR, CEIL = 'materials/fdm/lobby_wall.vmat', 'materials/fdm/lobby_floor.vmat', 'materials/fdm/lobby_ceil.vmat'
def room(cx, cy, z, sx, sy, sz):
    x0, x1, y0, y1, z0, z1 = cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, z, z + sz
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    # inward-facing: counter-clockwise when seen from inside the room
    faces = [[0, 1, 2, 3],          # floor, normal +z
             [4, 7, 6, 5],          # ceiling, normal -z
             [0, 4, 5, 1],          # y0 wall, normal +y
             [2, 6, 7, 3],          # y1 wall, normal -y
             [1, 5, 6, 2],          # x1 wall, normal -x
             [3, 7, 4, 0]]          # x0 wall, normal +x
    mesh_node(polymesh(v, faces, [FLOOR, CEIL, WALL, WALL, WALL, WALL]), 'fdm_lobby')

LZ = -12000
room(0, 0, LZ, 1536, 1536, 384)        # lobby
room(0, 2600, LZ, 800, 800, 256)       # pawn booth (sealed)
room(0, 4200, LZ, 2048, 1024, 256)     # model cache (sealed)

for i in range(32):
    x = -640 + (i % 8) * 180; y = -620 + (i // 8) * 90
    ent('info_player_terrorist', (x, y, LZ + 8), (0, 90, 0), enabled='1', priority='0')
    ent('info_player_counterterrorist', (x, y + 900, LZ + 8), (0, 270, 0), enabled='1', priority='0')
ent('info_target', (0, 2600, LZ), targetname='fdm_booth')
ent('point_script', (0, 0, LZ + 64), targetname='fdm_script', cs_script=SCRIPT_PATH)
ent('custom_hud_layout', (32, 0, LZ + 64), targetname='fdm_hud', layout=HUD_PATH, observable='1')
ent('env_sky', (64, 0, LZ + 64), targetname='fdm_sky', skyname='materials/fdm/sky/sky.vmat', tint_color='255 255 255',
    brightnessscale='1.0', StartDisabled='0')
ent('env_gradient_fog', (96, 0, LZ + 64), targetname='fdm_fog', fogcolor='0 0 0', fogstrength='1.0', fogmaxopacity='0.85',
    fogstart='256', fogend='3000', fogfalloffexponent='1.0', heightfog='0', fogstartheight='0', fogendheight='4000',
    fogverticalexponent='2.0', fadetime='0', farz='-1', StartDisabled='0')
ent('prop_dynamic', (0, 2600, LZ + 32), targetname='fdm_src_prop', model='models/fdm/null.vmdl', solid='0',
    disableshadows='1', fademindist='-1', fademaxdist='0', skin='default', rendercolor='255 255 255', renderamt='255')
ent('point_template', (0, 2600, LZ + 48), targetname='fdm_tpl_prop', Template01='fdm_src_prop', spawnflags='2',
    asynchronous='0', timeoutInterval='0', spawnGroupType='INSERT_INTO_POINT_TEMPLATE_SPAWN_GROUP',
    clientOnlyEntityBehavior='CREATE_FOR_CURRENTLY_CONNECTED_CLIENTS_ONLY')
for k, key in enumerate(sorted(sprites)):
    x = -960 + (k % 30) * 64; y = 4200 - 448 + (k // 30) * 128
    ent('prop_dynamic', (x, y, LZ + 8), targetname='fdm_cache_%s' % key.lower(), model='models/fdm/spr/%s.vmdl' % key.lower(),
        solid='0', disableshadows='1')
for k, s in enumerate(SOUNDS):
    ent('point_soundevent', (-700 + (k % 20) * 64, 700 + (k // 20) * 64, LZ + 64), targetname='fdm_snd_' + s, soundName='fdm.' + s,
        startOnSpawn='0', toLocalPlayer='0', stopOnNew='0', saveAndRestore='0')
for p in props:
    o = p['origin']
    if p['mover'] or p.get('anim'):
        ent('prop_dynamic', o, targetname=p['name'], model=p['model'], solid='0', disableshadows='1', fademindist='-1')
    else:
        ent('prop_static', o, model=p['model'], solid='0', disableshadows='1', fademindist='-1', fademaxdist='0',
            rendertocubemaps='0', bakelighting='0', visoccluder='0')

# ---------------------------------------------------------------- swap content into the world
SAMPLE = {'point_script', 'custom_hud_layout', 'point_soundevent', 'point_template', 'prop_dynamic'}
kids = world.attr('children')
kept = []
for c in kids[2]:
    if c.type == 'CMapMesh': continue                     # Hammer's default box
    if c.type == 'CMapEntity':
        cls = c.get('entity_properties').get('classname')
        if cls in SAMPLE and not c.get('entity_properties').get('targetname'): continue
    kept.append(c)
kids[2] = kept + new_children
# entities kept from the template count too
for c in kept:
    if c.type == 'CMapEntity':
        cls = c.get('entity_properties').get('classname'); counts[cls] = counts.get(cls, 0) + 1

# asset-browser metadata in the header (Hammer rewrites this on save)
pre = {a[0]: a for a in d.prefix[0]}
pre['map_asset_references'][2] = list(materials_used)
names = sorted(counts)
pre['map_subasset_reference_types'][2] = ['entity'] * len(names)
pre['map_subasset_reference_names'][2] = names
pre['map_subasset_reference_counts'][2] = [counts[n] for n in names]

d.elements = [root]       # save() re-collects everything reachable from the root
d.save(OUTPATH)
print('vmap: %d entities, %d meshes, %d elements -> %s' % (sum(counts.values()), 3, len(d.elements), OUTPATH))
