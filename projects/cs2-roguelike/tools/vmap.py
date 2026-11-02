"""Writes the Nanite Temple map onto the addon template (or the mapper's latest Hammer save): sealed rooms in the void with their
floor at z = 0, the vault pool, staging buy rooms, the arena, a cache room, lighting, probes, lightmap-res shells, vis hints,
spawns, teleport targets, the script entity and its prop pool. Everything is tagged with the vis group nt_gen, so a re-run
replaces only its own nodes and keeps whatever was placed by hand in Hammer.

usage: vmap.py <source.vmap> <out.vmap> <addon_out_dir> [--layout out.json]
"""
import os, sys, math, json
HERE = os.path.dirname(os.path.abspath(__file__))
CREATE = os.environ.get('CREATE', os.path.join(HERE, '..', '..', '..', 'create'))
sys.path.insert(0, CREATE); sys.path.insert(0, HERE)
import dmx, vmaplib, vmesh, voxel, fx_models
import vmapgen as G
from vmaplib import ent
import names as N
import layout as LY
import dress

SRC, OUTPATH, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
LAYOUT_JSON = sys.argv[sys.argv.index('--layout') + 1] if '--layout' in sys.argv else os.path.join(OUT, '_gen', 'layout.json')
GROUP = N.GROUP

# ---------------------------------------------------------------- materials (stock Ancient stone + our own self-lit strips)
FLOOR = 'materials/de_ancient/hr_ancient_ground_paver_02_base.vmat'
FLOOR_CARVED = 'materials/de_ancient/hr_ancient_ground_carvings_01_base.vmat'
WALL = 'materials/de_ancient/hr_ancient_wall_stone_03_grey_base.vmat'
WALL_DARK = 'materials/de_ancient/hr_ancient_wall_stone_05_grey_wet.vmat'
CEIL = 'materials/de_ancient/hr_ancient_roof_stone_01_grey_base.vmat'
BLOCK = 'materials/de_ancient/hr_ancient_wall_stone_04_grey_wet.vmat'
TRIGGER = 'materials/tools/toolstrigger.vmat'
for m in (FLOOR, FLOOR_CARVED, WALL, WALL_DARK, CEIL, BLOCK): vmesh.TEX_SIZE[m] = (1024, 1024)
vmesh.TEX_SIZE[TRIGGER] = (64, 64)

os.makedirs(os.path.join(OUT, '_gen'), exist_ok=True)
FX_DIR = 'materials/models/%s/fx' % N.PREFIX
CYAN = fx_models.emissive(OUT, FX_DIR, 'nt_cyan', (40, 225, 255), 10.0, 'Nanite Temple: data conduit glow (AI-generated)')
AMBER = fx_models.emissive(OUT, FX_DIR, 'nt_amber', (255, 170, 40), 10.0, 'Nanite Temple: exit plate glow (AI-generated)')
MAGENTA = fx_models.emissive(OUT, FX_DIR, 'nt_magenta', (255, 60, 200), 10.0, 'Nanite Temple: hazard glow (AI-generated)')
BLACK = fx_models.emissive(OUT, FX_DIR, 'nt_black', (4, 4, 6), 0.0, 'Nanite Temple: invisible pool prop (AI-generated)')
for m in (CYAN, AMBER, MAGENTA, BLACK): vmesh.TEX_SIZE[m] = (4, 4)
voxel.null_model(OUT, 'models/%s' % N.PREFIX, BLACK, name='null')
NULL_MODEL = 'models/%s/null.vmdl' % N.PREFIX

# stock models (measured with create/s2/prop_mesh.mjs)
PILLAR_BASE = 'models/anubis/structures/pillar02_base01.vmdl'     # 96 x 96 x 16
PILLAR_128 = 'models/anubis/structures/pillar02_128.vmdl'         # r 35, 128 tall
TRIM = 'models/anubis/trims/trim02_128.vmdl'                      # 12 deep (+x), 128 long (+y), 28 tall
WALL_PANEL = 'models/anubis/structures/wall_detail01_192.vmdl'    # 21 deep (+x), 192 wide (y +-96), 160 tall (z +-80)
BLOCK_PROP = 'models/anubis/structures/pillar_block01.vmdl'       # 96 x 96 x 65, centred (z -32 .. 33)
STATUE = 'models/anubis/structures/statue01.vmdl'                 # 51 x 66 x 130
STATUE_HEAD = 'models/anubis/structures/statue01_head.vmdl'
GOLEM = 'models/generic/stone_statue_01/stone_statue_01.vmdl'
SERVER = 'models/props/de_train/hr_t/server_a/server_a.vmdl'      # 35 x 54 x 96, centred in z
EXHIBIT_LIGHT = 'models/anubis/lights/anubis_exhibit_light01.vmdl'
# models the script SetModel()s pooled props to (enemies, gates, effects): one cache prop each
HOLO_PANEL = 'models/anubis/signs/anubis_exhibition_panel_01.vmdl'
TOWER_RUIN = 'models/anubis/structures/tower01_destroyed.vmdl'
FXM = ['models/nt/fx/nt_%s/nt_%s.vmdl' % (k, k) for k in ('shard', 'bolt', 'dome', 'beacon', 'spark')]   # tools/fx.py
POOL_MODELS = [STATUE_HEAD, STATUE, HOLO_PANEL, TOWER_RUIN, GOLEM, BLOCK_PROP, PILLAR_128, SERVER, NULL_MODEL] + FXM   # must match ENEMIES in src/core/20_classes.js

W = LY.world()
d = G.open_map(SRC, OUT)


# ---------------------------------------------------------------- helpers
def mesh(m, bake=True, shadows=True, visexclude=False):
    return vmesh.mesh_node(m, GROUP, bake=bake, shadows=shadows, visexclude=visexclude)


def room_shell(b, floor=FLOOR, wall=WALL, ceil=CEIL):
    x0, y0, z0, x1, y1, z1 = b
    mesh(vmesh.box_mesh(x0, y0, z0, x1, y1, z1, dict(bottom=floor, top=ceil, side=wall), inward=True))


def block(b, mats):
    mesh(vmesh.box_mesh(*b, mats))


def prop(model, origin, yaw=0.0, solid='6', bake='0', shadows='0', **kw):
    keys = dict(model=model, solid=solid, disableshadows=shadows, fademindist='-1', fademaxdist='0', rendertocubemaps='1',
                bakelighting=bake, visoccluder='0', skin='default', rendercolor='255 255 255', renderamt='255')
    keys.update(kw)
    return ent('prop_static', origin, (0, yaw, 0), group=GROUP, **keys)


def lamp(origin, lumens, rng, color='255 200 150', shadows=False, baked_only=False):
    # baked_only: Static (directlight 1), no runtime cost: accents and small fill lights; the rest Stationary (3)
    return ent('light_omni2', origin, (90, 0, 0), group=GROUP, brightness_units='1', brightness_lumens=str(int(lumens)), brightness='1',
               color=color, range='%.0f' % rng, directlight='1' if baked_only else '3', castshadows='1' if shadows else '0', colormode='0', enabled='1',
               bouncescale='1.0', shape='0')


def quad(verts, mat, uvs):
    """one static-overlay face (a decal, a puddle) with explicit 0..1 UVs per corner; not in vis, casts nothing"""
    vmesh.TEX_SIZE.setdefault(mat, (512, 512))
    m = vmesh.polymesh_open(verts, [[0, 1, 2, 3]], [mat], scale=1.0)
    ev = m.get('edgeVertexIndices'); ef = m.get('edgeFaceIndices')
    for st in m.get('faceVertexData').get('streams'):
        if st.get('semanticName') == 'texcoord':
            data = st.attr('data')[2]
            for i in range(len(data)):
                if ef[i] >= 0: data[i] = (float(uvs[ev[i]][0]), float(uvs[ev[i]][1]))
    return vmesh.mesh_node(m, GROUP, bake=True, shadows=False, visexclude=True)


DRESS = dress.Ctx(prop, lamp, quad, OUT)


def pad_plate(center, mat, half=LY.PAD):
    x, y, z = center
    block((x - half, y - half, z, x + half, y + half, z + 4), dict(top=mat, side=BLOCK, bottom=BLOCK))


def pillar(x, y, z=0.0, height=272.0):
    prop(PILLAR_BASE, (x, y, z))
    h = z + 16
    while h + 128 <= z + height + 0.5:
        prop(PILLAR_128, (x, y, h)); h += 128


def wall_runs(b):
    """(origin of the first segment, yaw, step vector) for each wall of a box, walking the wall with the room on the prop's +x side.
    Props built along +y from their origin (trim02_128) line the wall when placed at these."""
    x0, y0, z0, x1, y1, z1 = b
    return [((x0, y0, z0), 0, (0, 1)), ((x1, y1, z0), 180, (0, -1)), ((x1, y0, z0), 90, (-1, 0)), ((x0, y1, z0), 270, (1, 0))]


def trims(b, seg=128.0):
    x0, y0, z0, x1, y1, z1 = b
    for (ox, oy, oz), yaw, (sx, sy) in wall_runs(b):
        L = (y1 - y0) if sx == 0 else (x1 - x0)
        for k in range(int(L // seg)):
            prop(TRIM, (ox + sx * k * seg, oy + sy * k * seg, oz), yaw, solid='0')


def wall_panels(b, offsets=(-256.0, 256.0), z=160.0):
    """carved stone panels centred on each wall at the given offsets from the wall's middle"""
    x0, y0, z0, x1, y1, z1 = b
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for o in offsets:
        prop(WALL_PANEL, (x0, cy + o, z), 0, solid='0'); prop(WALL_PANEL, (x1, cy - o, z), 180, solid='0')
        prop(WALL_PANEL, (cx - o, y0, z), 90, solid='0'); prop(WALL_PANEL, (cx + o, y1, z), 270, solid='0')


def conduit(b, z=48.0, glow=CYAN):
    """the carved data channel: two stone lips with a recessed self-lit strip between, along every wall, above the trim"""
    x0, y0, z0, x1, y1, z1 = b
    lip, deep = 10.0, 4.0
    for (wx0, wy0, wx1, wy1, nx, ny) in ((x0, y0, x0, y1, 1, 0), (x1, y0, x1, y1, -1, 0), (x0, y0, x1, y0, 0, 1), (x0, y1, x1, y1, 0, -1)):
        def strip(zz0, zz1, depth, mat):
            if nx: block((min(wx0, wx0 + nx * depth), wy0, zz0, max(wx0, wx0 + nx * depth), wy1, zz1), mat)
            else: block((wx0, min(wy0, wy0 + ny * depth), zz0, wx1, max(wy0, wy0 + ny * depth), zz1), mat)
        strip(z - 8, z, lip, WALL_DARK)
        strip(z, z + 16, deep, glow)
        strip(z + 16, z + 24, lip, WALL_DARK)


def room_lighting(b, warm=2200, accent='60 220 255', shadow_centre=True, z_off=32):
    x0, y0, z0, x1, y1, z1 = b
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hx, hy = (x1 - x0) / 2, (y1 - y0) / 2
    for sx in (-1, 1):
        for sy in (-1, 1):
            lamp((cx + sx * (hx - 160), cy + sy * (hy - 160), z1 - z_off), warm, max(hx, hy) * 1.1)
    lamp((cx, cy, z1 - z_off), warm * 1.3, max(hx, hy) * 1.4, shadows=shadow_centre)
    for (lx, ly) in ((x0 + 24, cy), (x1 - 24, cy), (cx, y0 + 24), (cx, y1 - 24)):
        lamp((lx, ly, 56), 320, 150, color=accent, baked_only=True)


def room_support(b, voxel=48):
    G.probe_volume(b, voxel=voxel, group=GROUP)
    G.lmres_box(b, group=GROUP)
    x0, y0, z0, x1, y1, z1 = b
    G.hint((x0 - 16, y0 - 16, z0 - 16, x1 + 16, y1 + 16, z1 + 16), 'Low', group=GROUP)


def tele(name, origin, yaw=0):
    return ent('info_teleport_destination', (origin[0], origin[1], origin[2] + 8), (0, yaw, 0), group=GROUP, targetname=name)


def buyzone(b, team):
    e = ent('func_buyzone', (0, 0, 0), group=GROUP, TeamNum=str(team))
    x0, y0, z0, x1, y1, z1 = b
    e.attr('children')[2].append(vmesh.mesh_node(vmesh.box_mesh(x0 + 4, y0 + 4, z0, x1 - 4, y1 - 4, z1 - 4, TRIGGER), GROUP, attach=False,
                                                 bake=False, shadows=False, visexclude=True, physics='default'))
    return e


# ---------------------------------------------------------------- lobby
L = W['lobby']; lb = L['box']
room_shell(lb, floor=FLOOR_CARVED)
trims(lb); conduit(lb); wall_panels(lb, offsets=(-384.0, 0.0, 384.0))
room_lighting(lb, warm=3200)
room_support(lb, voxel=48)
for sx in (-1, 1):
    pillar(L['cx'] + sx * 512, L['cy'] - 512, height=L['h']); pillar(L['cx'] + sx * 512, L['cy'] + 512, height=L['h'])
for i in range(32):
    x = L['cx'] - 560 + (i % 8) * 160; y = L['cy'] - 600 + (i // 8) * 96
    ent('info_player_terrorist', (x, y, 8), (0, 90, 0), group=GROUP, enabled='1', priority='0')
    ent('info_player_counterterrorist', (x, L['cy'] + 600 - (i // 8) * 96, 8), (0, 270, 0), group=GROUP, enabled='1', priority='0')
tele(L['name'], (L['cx'], L['cy'], 0))
dress.lobby(DRESS, L, [(L['cx'] - 560 + (i % 8) * 160, L['cy'] + s * (600 - (i // 8) * 96)) for i in range(32) for s in (-1, 1)])
G.nav_seed((L['cx'] - 512, L['cy'] - 256, 1, L['cx'] + 512, L['cy'] + 256, 40), group=GROUP)
G.map_params((L['cx'] - 64, L['cy'], 64), name='%s_map_params' % N.PREFIX, group=GROUP)
ent('point_script', (L['cx'], L['cy'], 64), group=GROUP, targetname='%s_script' % N.PREFIX, cs_script=N.SCRIPT_PATH)
ent('custom_hud_layout', (L['cx'] + 32, L['cy'], 64), group=GROUP, targetname='%s_hud' % N.PREFIX, layout=N.HUD_PATH, observable='1')
G.template_pool('%s_tpl_prop' % N.PREFIX, (L['cx'] + 64, L['cy'], 8), NULL_MODEL, group=GROUP)
for cls, pos, yaw in (('counterterrorist_team_intro', (L['cx'] + 300, L['cy'] + 300, 64), 90), ('terrorist_team_intro', (L['cx'] - 300, L['cy'] + 300, 64), 90),
                      ('team_select', (L['cx'], L['cy'] - 300, 64), 90), ('end_of_match', (L['cx'], L['cy'], 64), 90)):
    G.clone(d, cls, pos, (0, yaw, 0), group=GROUP)
G.clone(d, 'post_processing_volume', (L['cx'], L['cy'], 200), group=GROUP, master='1', minexposure='0.7', maxexposure='1.6', enableexposure='1',
        fadetime='1.0', spawnflags='4097')
G.clone(d, 'env_soundscape', (L['cx'], L['cy'], 200), group=GROUP, radius='-1', soundscape='Nothing', enablesoundevent='0', soundevent='')
ent('env_gradient_fog', (L['cx'] + 96, L['cy'], 64), group=GROUP, targetname='%s_fog' % N.PREFIX, fogcolor='4 8 12', fogstrength='1.0',
    fogmaxopacity='0.6', fogstart='512', fogend='3200', fogfalloffexponent='1.0', heightfog='0', fogstartheight='0', fogendheight='4000',
    fogverticalexponent='2.0', fadetime='0', farz='-1', StartDisabled='0')

# ---------------------------------------------------------------- sounds: one point_soundevent per event (the script picks sources), ambience loops per area
SOUNDS = json.load(open(os.path.join(OUT, '_gen', 'sounds.json')))
HOT = ('enemy_hit', 'enemy_die', 'sentinel_shot', 'bolt_hit', 'drone_lunge')
snd_names = ['nt.' + s for s in SOUNDS['sfx']] + ['nt.ui.' + s for s in SOUNDS['ui']]
G.sound_events(d, snd_names, (L['cx'] - 700, L['cy'] + 200, 72), prefix='%s_snd_' % N.PREFIX, group=GROUP, cols=12, step=48)
k = 0
for s_ in HOT:
    for suf in ('_b', '_c'):
        ent('point_soundevent', (L['cx'] - 700 + (k % 12) * 48, L['cy'] + 400 + (k // 12) * 48, 72), group=GROUP, targetname='%s_snd_nt_%s%s' % (N.PREFIX, s_, suf),
            soundName='nt.' + s_, startOnSpawn='0', toLocalPlayer='0', stopOnNew='0', saveAndRestore='0'); k += 1
def ambience(name, origin, kind):
    ent('point_soundevent', origin, group=GROUP, targetname=name, soundName=SOUNDS['amb'][kind], startOnSpawn='1', toLocalPlayer='0', stopOnNew='0', saveAndRestore='0')
ambience('%s_amb_lobby' % N.PREFIX, (L['cx'], L['cy'], 160), 'lobby')

# ---------------------------------------------------------------- vault pool
for rm in W['rooms']:
    b = rm['box']
    room_shell(b)
    trims(b); conduit(b); wall_panels(b)
    for i, (x, y) in enumerate(rm['pillars']):
        if rm['kind'] == 'ruin' and i % 2: prop(PILLAR_BASE, (x, y, 0)); prop(dress.PILLAR_BROKEN, (x, y, 16), 37 * i)
        else: pillar(x, y)
    for (x, y) in rm['blocks']: prop(BLOCK_PROP, (x, y, 32.5))
    if rm['dais']:
        D = rm['dais']
        block((D['cx'] - D['half'], D['cy'] - D['half'], 0, D['cx'] + D['half'], D['cy'] + D['half'], D['h']), dict(top=FLOOR_CARVED, side=BLOCK, bottom=BLOCK))
    for (x, y) in rm['statues']:
        z = rm['dais']['h'] if rm['dais'] else 0.0
        prop(STATUE, (x, y, z), 180)
    pad_plate(rm['entry'], CYAN); pad_plate(rm['exit'], AMBER)
    tele(rm['name'] + '_in', rm['entry'], 0)
    dress.vault(DRESS, rm, rm['pillars'])
    ambience('%s_amb_%s' % (N.PREFIX, rm['name']), (rm['cx'], rm['cy'], 140), 'vault')
    room_lighting(b)
    room_support(b)

# ---------------------------------------------------------------- staging buy rooms
for st in W['stagings']:
    b = st['box']
    room_shell(b, wall=WALL_DARK)
    trims(b); conduit(b, glow=AMBER)
    x0, y0, z0, x1, y1, z1 = b
    prop(SERVER, (x0 + 30, y0 + 64, 48), 0, solid='6'); prop(SERVER, (x0 + 30, y1 - 64, 48), 0, solid='6')
    room_lighting(b, warm=1400, accent='255 170 40', shadow_centre=False)
    room_support(b, voxel=32)
    buyzone(b, 2); buyzone(b, 3)
    tele(st['name'], st['pad'], 90)
    dress.staging(DRESS, st)
    ambience('%s_amb_%s' % (N.PREFIX, st['name']), (st['cx'], st['cy'], 128), 'staging')

# ---------------------------------------------------------------- arena
A = W['arena']; ab = A['box']
room_shell(ab, floor=FLOOR, ceil=CEIL)
trims(ab); conduit(ab, glow=MAGENTA); wall_panels(ab, offsets=(-1152.0, -384.0, 384.0, 1152.0), z=200.0)
block(A['tier1'], dict(top=FLOOR_CARVED, side=BLOCK, bottom=BLOCK))
block(A['dais'], dict(top=FLOOR_CARVED, side=BLOCK, bottom=BLOCK))
for s in A['steps']: block(s, dict(top=FLOOR, side=BLOCK, bottom=BLOCK))
for (x, y) in A['dais_pillars']: pillar(x, y, z=LY.DAIS_H, height=ab[5] - LY.DAIS_H)
for (x, y) in A['blocks']: prop(BLOCK_PROP, (x, y, 32.5))
for bal in A['balconies']:
    block(bal['box'], dict(top=FLOOR_CARVED, side=BLOCK, bottom=BLOCK))
    tele(bal['name'], bal['pad'], bal['yaw'])
    bx0, by0, bz0, bx1, by1, bz1 = bal['box']
    lamp(((bx0 + bx1) / 2, (by0 + by1) / 2, LY.BALCONY_H + 120), 900, 320, color='255 60 200')
ax0, ay0, az0, ax1, ay1, az1 = ab
for sx in (-1, 1):
    for sy in (-1, 1):
        lamp((A['cx'] + sx * 1200, A['cy'] + sy * 1200, az1 - 40), 6000, 1700)
lamp((A['cx'], A['cy'], az1 - 40), 9000, 2400, shadows=True)
dress.arena(DRESS, A)
ambience('%s_amb_arena' % N.PREFIX, (A['cx'], A['cy'], 300), 'arena')
G.probe_volume(ab, voxel=64, group=GROUP)
G.lmres_box(ab, group=GROUP)
G.hint((ax0 - 16, ay0 - 16, az0 - 16, ax1 + 16, ay1 + 16, az1 + 16), 'Low', group=GROUP)

# ---------------------------------------------------------------- cache room (one prop per script model, never seen)
C = W['cache']; cb = C['box']
room_shell(cb)
lamp((C['cx'], C['cy'], cb[5] - 32), 800, 600)
G.cache_room(d, POOL_MODELS, (C['cx'], C['cy'], 0), size=(C['w'], C['d']), step=(128, 128), prefix='%s_cache_' % N.PREFIX, group=GROUP)
G.probe_volume(cb, voxel=64, group=GROUP)

# ---------------------------------------------------------------- vis: Lowest over everything
bb = LY.all_boxes(W)
G.assert_no_overlap(bb)
whole = (min(b[0] for b in bb) - 256, min(b[1] for b in bb) - 256, min(b[2] for b in bb) - 256,
         max(b[3] for b in bb) + 256, max(b[4] for b in bb) + 256, max(b[5] for b in bb) + 256)
G.hint(whole, 'Lowest', group=GROUP)

# ---------------------------------------------------------------- write
# the template's own content sits where its default box was (the void now): drop those classes, keep sky + sun (harmless point entities)
DROP = ('info_player_terrorist', 'info_player_counterterrorist', 'info_player_start', 'func_bomb_target', 'point_worldtext', 'func_buyzone',
        'env_combined_light_probe_volume', 'post_processing_volume', 'env_soundscape', 'counterterrorist_team_intro', 'terrorist_team_intro',
        'team_select', 'end_of_match', 'cs_minimap_boundary', 'point_nav_walkable', 'env_cubemap_fog', 'info_map_parameters')
json.dump(W, open(LAYOUT_JSON, 'w'), indent=0)
counts = G.finish(d, OUTPATH, group=GROUP, drop_classes=DROP, extra_refs=(G.NAVATTR, G.LMRES, TRIGGER),
                  entities_json=os.path.join(os.path.dirname(LAYOUT_JSON), 'entities.json'))
print('layout -> %s; map spans %s .. %s' % (LAYOUT_JSON, tuple(int(x) for x in whole[:3]), tuple(int(x) for x in whole[3:])))
