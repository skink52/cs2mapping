"""Writes the whole Space Racer map into a Hammer map (binary DMX .vmap): the eight track props in their boxes in the
void (two layers of 2 x 2), a moondome (pixel-art sky shell, one per track theme) around each box, vis hints (Low along
the roads, Lowest everywhere else), the lobby, the pawn booth,
the model cache room, spawns and every entity the script needs.

usage: vmap.py <template_or_current.vmap> <out.vmap> <addon_out_dir> [script_name]

Everything written is tagged with the vis group "spr_env", so running it again on a map you have edited in Hammer
replaces only its own work and keeps your changes. Hammer's sample entities (unnamed point_script etc.) and the
default box are dropped the first time.
"""
import os, sys, json, math
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import dmx
from vmaplib import *
import vmaplib

SRC, OUTPATH, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
NAME = sys.argv[4] if len(sys.argv) > 4 else 'space_racer'
GROUP = 'spr_env'
SCRIPT_PATH = 'maps/scripts/%s.vjs' % NAME
HUD_PATH = 'panorama/layout/custom_game/%s.vxml' % NAME
TOOLSSKY = 'materials/tools/toolsskybox.vmat'
HINT_LOWEST, HINT_LOW = 9, 3
LZ = -12000

tracks = json.load(open(os.path.join(OUT, '_gen/track_props.json')))
cars = json.load(open(os.path.join(OUT, '_gen/car_models.json')))
SOUNDS = [l.split('"')[1][4:] for l in open(os.path.join(OUT, 'soundevents/soundevents_addon.vsndevts')) if l.strip().startswith('"spr.')]

d = dmx.DMX.load(SRC)
root = d.root
world = root.get('world')
vmaplib.init(d, OUT)

# ---------------------------------------------------------------- skies: a pixel-art panorama per track theme (tools/skies.py)
import skies
from theme import NEON, defs
THEMES, DEFS = defs().THEMES, defs().TRACKS
import retro
DEF = {t['id']: t for t in DEFS}
def sky_files(key, img):
    dd = os.path.join(OUT, 'materials/spr/sky'); os.makedirs(dd, exist_ok=True)
    Image.fromarray(img).save(os.path.join(dd, 'sky_%s_color.png' % key))
    open(os.path.join(dd, 'moondome_%s.vmat' % key), 'w', newline='\n').write('''// Space Racer moondome (%s): mesh material that shows the sky panorama, unlit, no shadows, no fog
Layer0
{
	shader "csgo_moondome.vfx"
	F_DO_NOT_CAST_SHADOWS 1
	g_vColorTint "[1.000000 1.000000 1.000000 0.000000]"
	TextureColor "materials/spr/sky/moondome_color.png"
	g_flCubeParallax "0.000"
	g_bFogEnabled "0"
	TextureCubeMap "materials/spr/sky/sky_%s_color.png"
}
''' % (key, key))
    return 'materials/spr/sky/moondome_%s.vmat' % key
def sky():
    dd = os.path.join(OUT, 'materials/spr/sky'); os.makedirs(dd, exist_ok=True)
    Image.new('RGB', (16, 16), (255, 255, 255)).save(os.path.join(dd, 'moondome_color.png'))
    mats = {}
    for k, t in enumerate(DEFS):
        img = skies.make_sky(t['theme'], THEMES[t['theme']], t['scenery'], k + 5)
        mats[t['id']] = sky_files(t['id'], img)
        if k == 0:
            Image.fromarray(img).save(os.path.join(dd, 'sky_color.png'))
    open(os.path.join(dd, 'sky.vmat'), 'w', newline='\n').write('// Space Racer sky\nLayer0\n{\n\tshader "sky.vfx"\n\tF_TEXTURE_FORMAT2 1\n\tSkyTexture "materials/spr/sky/sky_color.png"\n\tg_flBrightnessExposureBias "0.000"\n}\n')
    return mats
SKY_MATS = sky()

# lobby materials (dark panels with a thin light line)
def lobby_mats():
    """retro panels: dark tiles with a neon grid line, dithered"""
    dd = os.path.join(OUT, 'materials/spr'); os.makedirs(dd, exist_ok=True)
    for name, col, line in (('lobby_wall', retro.INK, retro.TEAL), ('lobby_floor', retro.BLACK, retro.MAGENTA), ('lobby_ceil', retro.INK, retro.PLUM)):
        img = np.zeros((32, 32, 3), np.float32); img[:] = col
        img[0, :] = line; img[:, 0] = line
        img[1:3, :] = np.array(line, np.float32) * 0.35 + np.array(col, np.float32) * 0.65
        img = retro.up(retro.quantize(img, 24), 8)
        Image.fromarray(img).save(os.path.join(dd, name + '_color.png'))
        open(os.path.join(dd, name + '.vmat'), 'w', newline='\n').write('// Space Racer lobby\nLayer0\n{\n\tshader "csgo_unlitgeneric.vfx"\n\tF_BLEND_MODE 0\n\tTextureColor "materials/spr/%s_color.png"\n\tg_vColorTint "[1.000000 1.000000 1.000000 0.000000]"\n}\n' % name)
lobby_mats()
WALL, FLOOR, CEIL = 'materials/spr/lobby_wall.vmat', 'materials/spr/lobby_floor.vmat', 'materials/spr/lobby_ceil.vmat'

def room(cx, cy, z, sx, sy, sz):
    x0, x1, y0, y1, z0, z1 = cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, z, z + sz
    v, faces = box_faces(x0, y0, z0, x1, y1, z1)
    mesh_node(polymesh(v, faces, [FLOOR, CEIL, WALL, WALL, WALL, WALL]), GROUP)

def shell(box, mat, inset):
    x0, y0, z0, x1, y1, z1 = box
    v, faces = box_faces(x0 + inset, y0 + inset, z0 + inset, x1 - inset, y1 - inset, z1 - inset)
    mesh_node(polymesh(v, faces, [mat] * 6, scale=1.0), GROUP)

def hint(box, kind):
    x0, y0, z0, x1, y1, z1 = box
    c = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2); h = ((x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2)
    ent('visibility_hint', c, group=GROUP, hintType=str(kind), box_mins='%g %g %g' % (-h[0], -h[1], -h[2]), box_maxs='%g %g %g' % (h[0], h[1], h[2]))

# ---------------------------------------------------------------- the tracks in their boxes
boxes = []
for tp in tracks:
    ox, oy, oz = tp['off']
    ent('prop_static', (ox, oy, oz), group=GROUP, model=tp['model'], solid='0', disableshadows='1', fademindist='-1', fademaxdist='0',
        rendertocubemaps='0', bakelighting='0', visoccluder='0')
    hb = tp['half']
    box = (ox - hb, oy - hb, oz + tp['floor'] - 500, ox + hb, oy + hb, oz + tp['zmax'] + 4800)   # tall enough for the lobby's overview camera
    boxes.append(box)
    shell(box, SKY_MATS[tp['id']], 0)      # the track's own sky; no toolsskybox shell (it would show the one env_sky instead)
# vis: nothing inside a track box blocks sight (track and scenery are props that don't occlude), so fine vis buys
# nothing there: the whole map is one Lowest hint and only the sealed lobby rooms get Low. (Until 28 Oct a chain of
# Low hints ran along every road; Neon Racer's vis then made 3.7 million clusters and took far too long.)
TRACKDATA = {t['id']: t for t in json.load(open(os.path.join(OUT, '_gen/tracks.json')))}
CHUNK, PAD_XY, PAD_DOWN, PAD_UP = 40, 900, 350, 1100
ROAD_HINTS = os.environ.get('SPR_ROAD_HINTS') == '1'       # the old Low band along the roads, if ever needed again
band_hints = 0
for tp, box in zip(tracks if ROAD_HINTS else [], boxes):
    T = TRACKDATA[tp['id']]
    ox, oy, oz = tp['off']
    n = T['n']
    for a0 in range(0, n, CHUNK):
        idx = [(a0 + k) % n for k in range(CHUNK + 1)]
        xs = [T['x'][i] for i in idx]; ys = [T['y'][i] for i in idx]; zs = [T['z'][i] for i in idx]
        hw = max(T['hw'][i] for i in idx)
        b = (max(box[0] + 8, ox + min(xs) - hw - PAD_XY), max(box[1] + 8, oy + min(ys) - hw - PAD_XY), max(box[2] + 8, oz + min(zs) - PAD_DOWN),
             min(box[3] - 8, ox + max(xs) + hw + PAD_XY), min(box[4] - 8, oy + max(ys) + hw + PAD_XY), min(box[5] - 8, oz + max(zs) + PAD_UP))
        hint(b, HINT_LOW); band_hints += 1
for i, a in enumerate(boxes):
    for b in boxes[i + 1:]:
        assert a[3] <= b[0] or b[3] <= a[0] or a[4] <= b[1] or b[4] <= a[1] or a[5] <= b[2] or b[5] <= a[2], (a, b)

# ---------------------------------------------------------------- lobby, booth, model cache
room(0, 0, LZ, 1536, 1536, 384)        # lobby (CS2 spawn room)
room(0, 2600, LZ, 800, 800, 256)       # pawn booth (sealed)
room(0, 4200, LZ, 2048, 1024, 256)     # model cache (sealed)
lobby_boxes = [(-768 - 64, -768 - 64, LZ - 64, 768 + 64, 768 + 64, LZ + 384 + 64),
               (-400 - 64, 2600 - 400 - 64, LZ - 64, 400 + 64, 2600 + 400 + 64, LZ + 256 + 64),
               (-1024 - 64, 4200 - 512 - 64, LZ - 64, 1024 + 64, 4200 + 512 + 64, LZ + 256 + 64)]
for b in lobby_boxes: hint(b, HINT_LOW)
allb = boxes + lobby_boxes
whole = (min(b[0] for b in allb) - 256, min(b[1] for b in allb) - 256, min(b[2] for b in allb) - 256,
         max(b[3] for b in allb) + 256, max(b[4] for b in allb) + 256, max(b[5] for b in allb) + 256)
hint(whole, HINT_LOWEST)

for i in range(32):
    x = -640 + (i % 8) * 180; y = -620 + (i // 8) * 90
    ent('info_player_terrorist', (x, y, LZ + 8), (0, 90, 0), group=GROUP, enabled='1', priority='0')
    ent('info_player_counterterrorist', (x, y + 900, LZ + 8), (0, 270, 0), group=GROUP, enabled='1', priority='0')
ent('info_target', (0, 2600, LZ), group=GROUP, targetname='spr_booth')
ent('point_script', (0, 0, LZ + 64), group=GROUP, targetname='spr_script', cs_script=SCRIPT_PATH)
ent('custom_hud_layout', (32, 0, LZ + 64), group=GROUP, targetname='spr_hud', layout=HUD_PATH, observable='1')
ent('env_sky', (64, 0, LZ + 64), group=GROUP, targetname='spr_sky', skyname='materials/spr/sky/sky.vmat', tint_color='255 255 255',
    brightnessscale='1.0', StartDisabled='0')
ent('info_map_parameters', (-32, 0, LZ + 64), group=GROUP, targetname='spr_map_params', buying='3', usenormalspawnsfordm='1', disableautogenerateddmspawns='1')
ent('prop_dynamic', (0, 2600, LZ + 32), group=GROUP, targetname='spr_src_prop', model=cars['fx']['null'], solid='0', disableshadows='1',
    fademindist='-1', fademaxdist='0', skin='default', rendercolor='255 255 255', renderamt='255')
ent('point_template', (0, 2600, LZ + 48), group=GROUP, targetname='spr_tpl_prop', Template01='spr_src_prop', spawnflags='2',
    asynchronous='0', timeoutInterval='0', spawnGroupType='INSERT_INTO_POINT_TEMPLATE_SPAWN_GROUP',
    clientOnlyEntityBehavior='CREATE_FOR_CURRENTLY_CONNECTED_CLIENTS_ONLY')
# every model the script may SetModel to must be in the map: one prop per model in the cache room
models = []
for key, m in cars['cars'].items(): models += [m['base'], m['boost'], m['pad']]
models += [v for k, v in cars['fx'].items() if k != 'null']
for k, mpath in enumerate(models):
    x = -900 + (k % 16) * 120; y = 4200 - 380 + (k // 16) * 160
    ent('prop_dynamic', (x, y, LZ + 8), group=GROUP, targetname='spr_cache_%d' % k, model=mpath, solid='0', disableshadows='1')
for k, s in enumerate(SOUNDS):
    ent('point_soundevent', (-600 + (k % 12) * 100, 600 + (k // 12) * 100, LZ + 64), group=GROUP, targetname='spr_snd_' + s, soundName='spr.' + s,
        startOnSpawn='0', toLocalPlayer='0', stopOnNew='1' if s.startswith('mus_') else '0', saveAndRestore='0')
# bots need a walkable seed for nav generation
seed = ent('func_nav_markup', (0, 0, 0), group=GROUP, navProperty_NavGen='WALKABLESEED', flags='1')
v, faces = box_faces(-704, -704, LZ + 1, 704, 704, LZ + 40, inward=False)
seed.attr('children')[2].append(mesh_node(polymesh(v, faces, ['materials/tools/toolsnavattribute.vmat'] * 6, scale=1.0), GROUP, attach=False))

# ---------------------------------------------------------------- swap into the world: drop our old nodes, Hammer samples, the default box
SAMPLE = {'point_script', 'custom_hud_layout', 'point_soundevent', 'point_template', 'prop_dynamic'}
kids = world.attr('children')
first_run = not any(c.get('customVisGroup', '') == GROUP for c in kids[2])
kept = []
for c in kids[2]:
    if c.get('customVisGroup', '') == GROUP: continue
    if c.type == 'CMapMesh' and first_run and not c.get('customVisGroup', ''): continue    # Hammer's default box
    if c.type == 'CMapEntity':
        ep = c.get('entity_properties'); cls = ep.get('classname')
        if cls in SAMPLE and not ep.get('targetname'): continue
    kept.append(c)
removed = len(kids[2]) - len(kept)
kids[2] = kept + vmaplib.new_children
for c in kept:
    if c.type == 'CMapEntity':
        cls = c.get('entity_properties').get('classname'); counts[cls] = counts.get(cls, 0) + 1

pre = {a[0]: a for a in d.prefix[0]}
refs = pre['map_asset_references'][2]
refs[:] = [r for r in refs if r != TOOLSSKY]          # older builds put a toolsskybox shell in every box
for m in list(materials_used) + ['materials/tools/toolsnavattribute.vmat']:
    if m not in refs: refs.append(m)
names = sorted(counts)
pre['map_subasset_reference_types'][2] = ['entity'] * len(names)
pre['map_subasset_reference_names'][2] = names
pre['map_subasset_reference_counts'][2] = [counts[n] for n in names]

d.elements = [root]
d.save(OUTPATH)
# a plain list for the test harness
ents = []
for c in kids[2]:
    if c.type != 'CMapEntity': continue
    ep = c.get('entity_properties')
    ents.append(dict(classname=ep.get('classname'), targetname=ep.get('targetname', ''), origin=list(c.get('origin'))))
os.makedirs('build', exist_ok=True)
json.dump(ents, open('build/entities.json', 'w'))
print('vmap: %d Low vis hints along the roads (SPR_ROAD_HINTS=1 for the old band)' % band_hints)
print('vmap: %d entities, %d track boxes, replaced %d old nodes, world %s..%s -> %s' % (
    sum(counts.values()), len(boxes), removed, tuple(int(x) for x in whole[:3]), tuple(int(x) for x in whole[3:]), OUTPATH))
