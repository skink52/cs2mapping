"""Writes build/freedm.vmf (reference copy for the test harness; the real map is written by vmap.py): every entity the game needs plus the lobby and the pawn booth, for Hammer's VMF import."""
import os, sys, json
OUT = sys.argv[1]
props = json.load(open(os.path.join(OUT, '_gen/props.json')))
sprites = json.load(open(os.path.join(OUT, '_gen/sprite_models.json')))
SOUNDS = [l.split('"')[1][4:] for l in open(os.path.join(OUT, 'soundevents/soundevents_addon.vsndevts')) if l.strip().startswith('"fdm.') and 'base' not in l]

ids = [0]
def nid():
    ids[0] += 1; return ids[0]

def kv(d):
    return ''.join('\t"%s" "%s"\n' % (k, v) for k, v in d.items())

ents = []
def ent(classname, origin, **keys):
    d = {'id': nid(), 'classname': classname, 'origin': '%g %g %g' % tuple(origin)}
    d.update(keys)
    ents.append('entity\n{\n' + kv(d) + '}\n')

# ---------------------------------------------------------------- brushes
solids = []
def box(x0, y0, z0, x1, y1, z1, mat):
    # plane point order copied from the VMF reference brush (valid winding for Hammer)
    planes = [
        ((x0, y0, z1), (x0, y1, z1), (x1, y1, z1), '[1 0 0 0] 0.25', '[0 -1 0 0] 0.25'),
        ((x0, y1, z0), (x0, y0, z0), (x1, y0, z0), '[1 0 0 0] 0.25', '[0 -1 0 0] 0.25'),
        ((x0, y0, z0), (x0, y1, z0), (x0, y1, z1), '[0 1 0 0] 0.25', '[0 0 -1 0] 0.25'),
        ((x1, y1, z0), (x1, y0, z0), (x1, y0, z1), '[0 1 0 0] 0.25', '[0 0 -1 0] 0.25'),
        ((x0, y1, z0), (x1, y1, z0), (x1, y1, z1), '[1 0 0 0] 0.25', '[0 0 -1 0] 0.25'),
        ((x1, y0, z0), (x0, y0, z0), (x0, y0, z1), '[1 0 0 0] 0.25', '[0 0 -1 0] 0.25'),
    ]
    out = '\tsolid\n\t{\n\t\t"id" "%d"\n' % nid()
    for a, b, c, u, v in planes:
        out += ('\t\tside\n\t\t{\n\t\t\t"id" "%d"\n\t\t\t"plane" "(%g %g %g) (%g %g %g) (%g %g %g)"\n'
                '\t\t\t"material" "%s"\n\t\t\t"uaxis" "%s"\n\t\t\t"vaxis" "%s"\n\t\t\t"rotation" "0"\n'
                '\t\t\t"lightmapscale" "16"\n\t\t\t"smoothing_groups" "0"\n\t\t}\n') % (nid(), *a, *b, *c, mat, u, v)
    out += '\t}\n'
    solids.append(out)

def room(cx, cy, z, sx, sy, sz, wall, floor, ceil, t=16):
    x0, x1, y0, y1 = cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2
    box(x0 - t, y0 - t, z - t, x1 + t, y1 + t, z, floor)
    box(x0 - t, y0 - t, z + sz, x1 + t, y1 + t, z + sz + t, ceil)
    box(x0 - t, y0 - t, z, x0, y1 + t, z + sz, wall)
    box(x1, y0 - t, z, x1 + t, y1 + t, z + sz, wall)
    box(x0, y0 - t, z, x1, y0, z + sz, wall)
    box(x0, y1, z, x1, y1 + t, z + sz, wall)

LZ = -12000
WALL, FLOOR, CEIL = 'fdm/lobby_wall', 'fdm/lobby_floor', 'fdm/lobby_ceil'
room(0, 0, LZ, 1536, 1536, 384, WALL, FLOOR, CEIL)            # lobby
room(0, 2600, LZ, 800, 800, 256, WALL, FLOOR, CEIL)           # pawn booth (sealed)
room(0, 4200, LZ, 2048, 1024, 256, WALL, FLOOR, CEIL)         # model cache (sealed)

# ---------------------------------------------------------------- entities
for i in range(32):
    x = -640 + (i % 8) * 180; y = -620 + (i // 8) * 90
    ent('info_player_terrorist', (x, y, LZ + 8), angles='0 90 0', enabled='1')
    ent('info_player_counterterrorist', (x, y + 900, LZ + 8), angles='0 270 0', enabled='1')
ent('light_omni2', (0, 0, LZ + 300), color='255 255 255', brightness='3', range='2000', castshadows='0', directlight='2')
ent('info_target', (0, 2600, LZ), targetname='fdm_booth')
ent('info_map_parameters', (-32, 0, LZ + 64), targetname='fdm_map_params', buying='3', usenormalspawnsfordm='1')
ent('point_script', (0, 0, LZ + 64), targetname='fdm_script', cs_script='scripts/freedm.vjs')
ent('custom_hud_layout', (32, 0, LZ + 64), targetname='fdm_hud', layoutfile='panorama/layout/custom_game/freedm.vxml')
ent('env_sky', (64, 0, LZ + 64), targetname='fdm_sky', skyname='materials/fdm/sky/sky.vmat', tint_color='255 255 255', brightnessscale='1.0', StartDisabled='0')
ent('env_fog_controller', (96, 0, LZ + 64), targetname='fdm_fog', fogenable='1', fogcolor='0 0 0', fogcolor2='0 0 0',
    fogstart='256', fogend='3000', fogmaxdensity='0.85', farz='-1', fogblend='0')
# prop template for everything the script draws
ent('prop_dynamic', (0, 2600, LZ + 32), targetname='fdm_src_prop', model='models/fdm/null.vmdl', solid='0',
    DisableBoneFollowers='1', disableshadows='1', fademindist='-1', fadescale='0')
ent('point_template', (0, 2600, LZ + 48), targetname='fdm_tpl_prop', Template01='fdm_src_prop', spawnflags='0')
# every sprite model once, so the script can switch props to any of them
for k, key in enumerate(sorted(sprites)):
    x = -960 + (k % 30) * 64; y = 4200 - 448 + (k // 30) * 128
    ent('prop_dynamic', (x, y, LZ + 8), targetname='fdm_cache_%s' % key.lower(), model='models/fdm/spr/%s.vmdl' % key.lower(), solid='0', disableshadows='1')
# sounds
for k, s in enumerate(SOUNDS):
    ent('point_soundevent', (-700 + (k % 20) * 64, 700, LZ + 64), targetname='fdm_snd_' + s, soundName='fdm.' + s,
        startOnSpawn='0', toLocalPlayer='0', stopOnNew='0')
mj = os.path.join(OUT, '_gen/music.json')
for k, t in enumerate(json.load(open(mj)) if os.path.exists(mj) else []):
    ent('point_soundevent', (-700 + k * 64, 400, LZ + 64), targetname='fdm_mus_' + t['id'], soundName='fdm_music.' + t['id'],
        startOnSpawn='0', toLocalPlayer='0', stopOnNew='0')
# level geometry and movers
for p in props:
    o = p['origin']
    if p['mover'] or p.get('anim'):
        ent('prop_dynamic', o, targetname=p['name'], model=p['model'], solid='0', disableshadows='1', fademindist='-1')
    else:
        ent('prop_static', o, model=p['model'], solid='0', disableshadows='1', fademindist='-1')

world = ('world\n{\n\t"id" "%d"\n\t"mapversion" "1"\n\t"classname" "worldspawn"\n\t"skyname" "materials/fdm/sky/sky.vmat"\n'
         '\t"maxpropscreenwidth" "-1"\n\t"detailvbsp" "detail.vbsp"\n\t"detailmaterial" "detail/detailsprites"\n%s}\n') % (nid(), ''.join(solids))
head = 'versioninfo\n{\n\t"editorversion" "400"\n\t"editorbuild" "8000"\n\t"mapversion" "1"\n\t"formatversion" "100"\n\t"prefab" "0"\n}\n'
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'build', 'freedm.vmf'), 'w', newline='\n').write(head + world + ''.join(ents))
print('vmf: %d entities, %d brushes' % (len(ents), len(solids)))
